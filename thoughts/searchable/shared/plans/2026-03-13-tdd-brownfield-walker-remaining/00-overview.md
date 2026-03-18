---
date: 2026-03-13
researcher: claude-opus
branch: feature/brownfield-code-walker
repository: CodeWriter9.0
topic: "TDD Plan: Brownfield Code Walker — Remaining Implementation"
tags: [tdd, plan, brownfield, crawler, scanner, gwt-author, typescript, go, rust, javascript]
status: draft
type: tdd-plan
epic: replication_ab_bench-e15
---

# Brownfield Code Walker — Remaining Implementation TDD Plan

## Overview

Six components remain unimplemented from the brownfield code walker research
(`thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md`).
This plan specifies each as a TDD sequence of testable behaviors.

**What already exists** (Phase 1–3 commit `66c4f88`):
- `crawl_types.py` — FnRecord, AxRecord, InField, OutField, Skeleton, SkeletonParam, enums
- `crawl_store.py` — full SQLite store with CRUD, staleness, subgraph queries, card rendering
- `crawl_bridge.py` — bridge_crawl_to_dag() with orphan cleanup
- `scanner_python.py` — scan_file(), scan_directory() producing Skeleton objects
- `entry_points.py` — detect_codebase_type(), discover_entry_points() (Python only)
- `one_shot_loop.py` — query_context() loads cards from crawl.db, format_prompt_context() renders them
- `cli.py` — cmd_ingest (skeleton-only, no LLM extraction), cmd_stale, cmd_show
- `dag.py` — merge_registered_nodes(crawl_uuids=), remove_node()
- `lang_typescript.py`, `lang_go.py` — test-gen profiles (not skeleton scanners)

**What's missing** (this plan):

| # | Component | Plan File | New File(s) | Test File(s) |
|---|-----------|-----------|-------------|--------------|
| 1 | DFS crawl orchestrator (LLM extraction) | [01-crawl-orchestrator.md](01-crawl-orchestrator.md) | `python/registry/crawl_orchestrator.py` | `python/tests/test_crawl_orchestrator.py` |
| 2 | `cw9 gwt-author` command | [02-gwt-author.md](02-gwt-author.md) | `python/registry/gwt_author.py` + cli.py extension | `python/tests/test_gwt_author.py` |
| 3 | TypeScript skeleton scanner | [03-scanner-typescript.md](03-scanner-typescript.md) | `python/registry/scanner_typescript.py` | `python/tests/test_scanner_typescript.py` |
| 4 | Go skeleton scanner | [04-scanner-go.md](04-scanner-go.md) | `python/registry/scanner_go.py` | `python/tests/test_scanner_go.py` |
| 5 | Rust skeleton scanner | [05-scanner-rust.md](05-scanner-rust.md) | `python/registry/scanner_rust.py` | `python/tests/test_scanner_rust.py` |
| 6 | JavaScript skeleton scanner | [06-scanner-javascript.md](06-scanner-javascript.md) | `python/registry/scanner_javascript.py` | `python/tests/test_scanner_javascript.py` |

## Current State Analysis

### Key Discoveries

- `cmd_ingest` (cli.py:760-879) stores **SKELETON_ONLY** records — `do_description="SKELETON_ONLY"`, empty ins/outs. Phase 1 LLM extraction is explicitly deferred (cli.py:820 comment).
- The `OneShotLoop` class in `one_shot_loop.py` orchestrates LLM→PlusCal→TLC loops but does **not** handle IN:DO:OUT extraction. The crawl orchestrator is a different loop: LLM→Pydantic→SQLite.
- `CrawlStore` already has `start_crawl_run()`, `finish_crawl_run()`, `upsert_record()`, `backfill_source_uuids()` — the orchestrator can use these directly.
- The research doc §Resolved Q5 specifies `cw9 gwt-author --research=<path>` piping to `cw9 register`. The register payload schema already supports `depends_on` in GWT entries (research doc lines 489-511).
- `scanner_python.py` is the reference implementation for skeleton scanners: ~210 lines of line-by-line text scanning producing `Skeleton` objects. TypeScript and Go scanners follow the same interface.
- Entry point detection (`entry_points.py`) is Python-only. TypeScript/Go entry point detection is out-of-scope for this plan — the scanners produce Skeletons; entry point detection for other languages is a follow-up.

### Existing Test Patterns

All tests follow these conventions (from `test_crawl.py`, `test_scanner_python.py`):
- `_make_*()` module-level builders with `**overrides`
- `@pytest.fixture` defined inline in test files (not conftest)
- `tmp_path` for ephemeral filesystem state
- `class Test<Subject>` grouping one concern per class
- `main([...])` for CLI integration tests with integer return code assertions

## What We're NOT Doing

- **Phase 2 MAP generation** — workflow partitioning from FN cards. Deferred.
- **TypeScript/Go entry point detection** — extending `entry_points.py` for non-Python. Deferred.
- **Parallel crawl** (`--parallel=N`) — sequential DFS only per research doc §Concurrency.
- **Rust skeleton scanner** — ~~CW8.1's `parse_source_code.rs` can be ported later.~~ Now included as Component 5.
- **Test cross-reference scanning** (`--with-tests`) — separate ingestion path, deferred.

## Testing Strategy

- **Framework**: pytest
- **Test Types**: Unit tests for all behaviors; integration tests marked `@pytest.mark.integration` for CLI and LLM-dependent paths
- **LLM Mocking**: The crawl orchestrator accepts an `extract_fn` callable (dependency injection). Tests pass a deterministic fake. No real LLM calls in unit tests.
- **Test run command**: `cd python && python -m pytest tests/test_crawl_orchestrator.py tests/test_gwt_author.py tests/test_scanner_typescript.py tests/test_scanner_go.py tests/test_scanner_rust.py tests/test_scanner_javascript.py -v`

## Implementation Order

```
Component 3 (TypeScript scanner) ─┐
Component 4 (Go scanner) ─────────┤
Component 5 (Rust scanner) ───────┼─→ Component 1 (DFS orchestrator) ──→ Component 2 (gwt-author)
Component 6 (JavaScript scanner) ─┘
```

**Scanners first** (3, 4, 5, 6 can all be parallelized): They have zero dependencies
on other new code. They follow the proven `scanner_python.py` pattern. Each is
~150-250 lines.

**Orchestrator second** (1): Depends on scanners working (to dispatch to the right
scanner based on file extension). Needs `CrawlStore` which is already implemented.

**gwt-author last** (2): Depends on crawl.db being populated by the orchestrator.
Needs the full pipeline working end-to-end.

## Integration Test (End-to-End)

After all 6 components are implemented, add this integration test:

```python
@pytest.mark.integration
class TestBrownfieldE2E:
    def test_ingest_crawl_gwt_author_pipeline(self, tmp_path: Path):
        """Full pipeline: ingest → crawl → gwt-author → register → query_context."""
        # 1. Create a small Python project
        project = tmp_path / "project"
        project.mkdir()
        (project / ".cw9").mkdir()

        target = tmp_path / "target"
        target.mkdir()
        (target / "handler.py").write_text(
            "def handle_request(user_id: int) -> dict:\n"
            "    user = get_user(user_id)\n"
            "    return {'name': user.name}\n\n"
            "def get_user(uid: int) -> User:\n"
            "    return db.query(uid)\n"
        )

        # 2. Ingest (Phase 0 skeletons)
        from registry.cli import main
        rc = main(["ingest", str(target), str(project)])
        assert rc == 0

        # 3. Crawl (Phase 1 LLM extraction — mocked)
        # ... orchestrator with fake extract_fn ...

        # 4. gwt-author (mocked LLM)
        # ... produces register payload ...

        # 5. Register (creates GWT + DEPENDS_ON edges)
        # ... cw9 register ...

        # 6. query_context includes IN:DO:OUT cards
        from registry.one_shot_loop import query_context
        from registry.dag import RegistryDag
        dag = RegistryDag.load(project / ".cw9" / "dag.json")
        # ... verify cards are in context bundle ...
```

## References

- Research: `thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md`
- Multi-lang TDD plan: `thoughts/searchable/shared/plans/2026-03-10-tdd-multi-language-test-gen.md`
- Multi-lang phases: `thoughts/searchable/shared/plans/2026-03-10-tdd-multi-lang/`
- Python scanner reference: `python/registry/scanner_python.py`
- Go scanner reference: `python/registry/scanner_go.py`
- TypeScript scanner reference: `python/registry/scanner_typescript.py`
- Rust migration research: `thoughts/searchable/shared/research/2026-03-13-rust-migration-brownfield-walker.md`
- Existing tests: `python/tests/test_crawl.py`, `test_scanner_python.py`, `test_lang.py`
