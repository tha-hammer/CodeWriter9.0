---
date: 2026-03-13
researcher: claude-opus
branch: feature/brownfield-code-walker
repository: CodeWriter9.0
topic: "TDD Plan: Brownfield Code Walker — Remaining Implementation"
tags: [tdd, plan, brownfield, crawler, scanner, gwt-author, typescript, go, rust, javascript]
status: draft
type: tdd-plan
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

| # | Component | New File(s) | Test File(s) |
|---|-----------|-------------|--------------|
| 1 | DFS crawl orchestrator (LLM extraction) | `python/registry/crawl_orchestrator.py` | `python/tests/test_crawl_orchestrator.py` |
| 2 | `cw9 gwt-author` command | `python/registry/gwt_author.py` + cli.py extension | `python/tests/test_gwt_author.py` |
| 3 | TypeScript skeleton scanner | `python/registry/scanner_typescript.py` | `python/tests/test_scanner_typescript.py` |
| 4 | Go skeleton scanner | `python/registry/scanner_go.py` | `python/tests/test_scanner_go.py` |
| 5 | Rust skeleton scanner | `python/registry/scanner_rust.py` | `python/tests/test_scanner_rust.py` |
| 6 | JavaScript skeleton scanner | `python/registry/scanner_javascript.py` | `python/tests/test_scanner_javascript.py` |

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

---

## Component 1: DFS Crawl Orchestrator (LLM Extraction)

**New file**: `python/registry/crawl_orchestrator.py`
**Test file**: `python/tests/test_crawl_orchestrator.py`

The orchestrator takes a populated CrawlStore (skeleton-only records from Phase 0) and entry points, then performs a DFS crawl using an LLM to extract full IN:DO:OUT for each function. The LLM is injected as a callable — the orchestrator never imports an LLM client directly.

### Behavior 1.1: Orchestrator accepts extract function and CrawlStore

**Given**: A CrawlStore with skeleton-only records and a list of entry point function names
**When**: `CrawlOrchestrator(store, entry_points, extract_fn)` is constructed
**Then**: The orchestrator holds references to the store, entry points, and extract function

#### 🔴 Red: Write Failing Test

**File**: `python/tests/test_crawl_orchestrator.py`
```python
"""Tests for the DFS crawl orchestrator (LLM extraction)."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.crawl_orchestrator import CrawlOrchestrator
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


def _make_skeleton(fn_name="handler", file_path="src/main.py", class_name=None) -> Skeleton:
    return Skeleton(
        function_name=fn_name,
        file_path=file_path,
        line_number=10,
        class_name=class_name,
        params=[SkeletonParam(name="request", type="Request")],
        return_type="Response",
        file_hash="abc123",
    )


def _make_fn_record_from_skeleton(skel: Skeleton, **overrides) -> FnRecord:
    uid = make_record_uuid(skel.file_path, skel.function_name, skel.class_name)
    defaults = dict(
        uuid=uid,
        function_name=skel.function_name,
        class_name=skel.class_name,
        file_path=skel.file_path,
        line_number=skel.line_number,
        src_hash=skel.file_hash,
        ins=[InField(name="request", type_str="Request", source=InSource.PARAMETER)],
        do_description="Handles incoming request",
        do_steps=["Parse request", "Return response"],
        outs=[OutField(name=OutKind.OK, type_str="Response", description="Success")],
        operational_claim="Handles request and returns response",
        skeleton=skel,
    )
    defaults.update(overrides)
    return FnRecord(**defaults)


def _fake_extract(skeleton: Skeleton, body: str) -> FnRecord:
    """Deterministic fake LLM extraction."""
    return _make_fn_record_from_skeleton(skeleton)


class TestOrchestratorInit:
    def test_construction(self, tmp_path: Path):
        with CrawlStore(tmp_path / "crawl.db") as store:
            orch = CrawlOrchestrator(store=store, entry_points=["handler"], extract_fn=_fake_extract)
            assert orch.store is store
            assert orch.entry_points == ["handler"]
```

#### 🟢 Green: Minimal Implementation

**File**: `python/registry/crawl_orchestrator.py`
```python
"""DFS crawl orchestrator — drives LLM extraction over skeleton-only records.

The orchestrator walks the CrawlStore's skeleton records depth-first from
entry points, calling an injected extract_fn for each function to produce
full IN:DO:OUT FnRecords.
"""
from __future__ import annotations

from typing import Callable, Protocol

from registry.crawl_store import CrawlStore
from registry.crawl_types import FnRecord, Skeleton


class CrawlOrchestrator:
    def __init__(
        self,
        store: CrawlStore,
        entry_points: list[str],
        extract_fn: Callable[[Skeleton, str], FnRecord],
    ) -> None:
        self.store = store
        self.entry_points = entry_points
        self.extract_fn = extract_fn
```

### Behavior 1.2: Single function extraction succeeds and stores result

**Given**: A CrawlStore with one skeleton-only record and a source file on disk
**When**: `orch.extract_one(uuid)` is called
**Then**: The extract_fn is invoked with the skeleton and function body text, and the resulting FnRecord is upserted into the store

```python
class TestExtractOne:
    def test_extracts_and_stores(self, tmp_path: Path):
        # Write a source file
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    return Response(200)\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Insert skeleton-only record
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))

            extracted = []
            def tracking_extract(skeleton, body):
                rec = _fake_extract(skeleton, body)
                extracted.append((skeleton, body))
                return rec

            orch = CrawlOrchestrator(store, ["handler"], tracking_extract)
            orch.extract_one(uid)

            # Verify the record is no longer skeleton-only
            rec = store.get_record(uid)
            assert rec.do_description != "SKELETON_ONLY"
            assert len(extracted) == 1
            assert "def handler" in extracted[0][1]
```

### Behavior 1.3: Extraction failure retries up to 3 times with error feedback

**Given**: An extract_fn that raises `ValidationError` on the first 2 calls then succeeds
**When**: `orch.extract_one(uuid)` is called
**Then**: The function is called 3 times total, the third result is stored

```python
class TestRetry:
    def test_retries_on_validation_error(self, tmp_path: Path):
        from pydantic import ValidationError

        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        call_count = 0
        def failing_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Invalid output (attempt {call_count})")
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], failing_extract)
            orch.extract_one(uid)

            assert call_count == 3
            rec = store.get_record(uid)
            assert rec.do_description != "SKELETON_ONLY"
```

### Behavior 1.4: Exhausted retries store EXTRACTION_FAILED stub

**Given**: An extract_fn that always raises errors
**When**: `orch.extract_one(uuid)` is called
**Then**: After 3 retries, a stub record with `do_description="EXTRACTION_FAILED"` is stored

```python
    def test_exhausted_retries_store_stub(self, tmp_path: Path):
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        def always_fail(skeleton, body, error_feedback=None):
            raise ValueError("Cannot extract")

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], always_fail)
            orch.extract_one(uid)

            rec = store.get_record(uid)
            assert rec.do_description == "EXTRACTION_FAILED"
            assert "LLM extraction failed" in rec.failure_modes[0]
```

### Behavior 1.5: DFS crawl traverses from entry points following internal_call sources

**Given**: A CrawlStore with records for `handler` (calls `validate`) and `validate` (no calls)
**When**: `orch.run()` is called
**Then**: Both functions are extracted in DFS order (handler first, then validate)

```python
class TestDFSCrawl:
    def test_dfs_follows_internal_calls(self, tmp_path: Path):
        # Write source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            "def handler(request):\n    result = validate(request)\n    return result\n"
        )
        (src_dir / "validate.py").write_text(
            "def validate(data):\n    return data is not None\n"
        )

        handler_skel = _make_skeleton("handler", str(src_dir / "main.py"))
        validate_skel = _make_skeleton("validate", str(src_dir / "validate.py"))
        handler_uid = make_record_uuid(str(src_dir / "main.py"), "handler")
        validate_uid = make_record_uuid(str(src_dir / "validate.py"), "validate")

        extraction_order = []

        def ordering_extract(skeleton, body, error_feedback=None):
            extraction_order.append(skeleton.function_name)
            rec = _make_fn_record_from_skeleton(skeleton)
            if skeleton.function_name == "handler":
                # handler has an internal_call to validate
                rec = _make_fn_record_from_skeleton(skeleton, ins=[
                    InField(name="request", type_str="Request", source=InSource.PARAMETER),
                    InField(
                        name="result", type_str="bool", source=InSource.INTERNAL_CALL,
                        source_function="validate",
                        source_file=str(src_dir / "validate.py"),
                    ),
                ])
            return rec

        with CrawlStore(tmp_path / "crawl.db") as store:
            for skel, uid in [(handler_skel, handler_uid), (validate_skel, validate_uid)]:
                store.insert_record(FnRecord(
                    uuid=uid, function_name=skel.function_name, file_path=skel.file_path,
                    line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                    outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["handler"], ordering_extract)
            result = orch.run()

            assert extraction_order == ["handler", "validate"]
            assert result["extracted"] == 2
```

### Behavior 1.6: DFS visited set prevents cycles

**Given**: Functions A and B that call each other
**When**: `orch.run()` is called starting from A
**Then**: Each function is extracted exactly once

```python
    def test_visited_set_prevents_cycles(self, tmp_path: Path):
        src = tmp_path / "cycle.py"
        src.write_text("def a():\n    b()\ndef b():\n    a()\n")

        skel_a = _make_skeleton("a", str(src))
        skel_b = _make_skeleton("b", str(src))
        uid_a = make_record_uuid(str(src), "a")
        uid_b = make_record_uuid(str(src), "b")

        call_counts: dict[str, int] = {}

        def counting_extract(skeleton, body, error_feedback=None):
            call_counts[skeleton.function_name] = call_counts.get(skeleton.function_name, 0) + 1
            rec = _make_fn_record_from_skeleton(skeleton)
            other = "b" if skeleton.function_name == "a" else "a"
            return _make_fn_record_from_skeleton(skeleton, ins=[
                InField(
                    name="result", type_str="None", source=InSource.INTERNAL_CALL,
                    source_function=other, source_file=str(src),
                ),
            ])

        with CrawlStore(tmp_path / "crawl.db") as store:
            for skel, uid in [(skel_a, uid_a), (skel_b, uid_b)]:
                store.insert_record(FnRecord(
                    uuid=uid, function_name=skel.function_name, file_path=skel.file_path,
                    line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                    outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["a"], counting_extract)
            orch.run()

            assert call_counts == {"a": 1, "b": 1}
```

### Behavior 1.7: External calls create AX boundary records

**Given**: A function that calls an external library function (e.g. `redis.get`)
**When**: The extract_fn returns an InField with `source=InSource.EXTERNAL`
**Then**: An AxRecord is created for the external boundary (never traversed)

```python
    def test_external_calls_create_ax_records(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    data = redis.get('key')\n    return data\n")
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        def ext_extract(skeleton, body, error_feedback=None):
            return _make_fn_record_from_skeleton(skeleton, ins=[
                InField(
                    name="data", type_str="bytes", source=InSource.EXTERNAL,
                    source_function="redis.get", source_file="redis",
                ),
            ])

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], ext_extract)
            result = orch.run()

            assert result["ax_records"] >= 1
            # External records should exist in the store
            all_uuids = store.get_all_uuids()
            assert len(all_uuids) >= 2  # handler + redis.get AX record
```

### Behavior 1.8: --max-functions limits DFS scope

**Given**: A CrawlStore with 10 skeleton records and `max_functions=3`
**When**: `orch.run()` is called
**Then**: At most 3 functions are extracted

```python
    def test_max_functions_limits_scope(self, tmp_path: Path):
        src = tmp_path / "big.py"
        funcs = "\n".join(f"def func_{i}():\n    pass\n" for i in range(10))
        src.write_text(funcs)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(10):
                skel = _make_skeleton(f"func_{i}", str(src))
                uid = make_record_uuid(str(src), f"func_{i}")
                store.insert_record(FnRecord(
                    uuid=uid, function_name=f"func_{i}", file_path=str(src),
                    line_number=i * 3 + 1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(
                store, [f"func_{i}" for i in range(10)],
                _fake_extract, max_functions=3,
            )
            result = orch.run()
            assert result["extracted"] == 3
```

### Behavior 1.9: run() returns summary counters

**Given**: A crawl with mixed outcomes (success, retry, failure)
**When**: `orch.run()` completes
**Then**: The return dict contains `extracted`, `failed`, `skipped`, `ax_records` counters

```python
    def test_run_returns_counters(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    pass\n")
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], _fake_extract)
            result = orch.run()

            assert "extracted" in result
            assert "failed" in result
            assert "skipped" in result
            assert "ax_records" in result
            assert result["extracted"] == 1
```

### Behavior 1.10: Incremental crawl skips records with matching hash

**Given**: A CrawlStore with a fully-extracted record whose src_hash matches the current file
**When**: `orch.run()` is called with `incremental=True`
**Then**: The record is skipped (not re-extracted)

```python
    def test_incremental_skips_up_to_date(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    pass\n")
        import hashlib
        file_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        call_count = 0
        def counting_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Insert a FULLY extracted record (not SKELETON_ONLY)
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash=file_hash,
                ins=[InField(name="x", type_str="int", source=InSource.PARAMETER)],
                do_description="Already extracted",
                outs=[OutField(name=OutKind.OK, type_str="None", description="ok")],
                skeleton=skel,
            ))

            orch = CrawlOrchestrator(store, ["handler"], counting_extract, incremental=True)
            result = orch.run()

            assert call_count == 0
            assert result["skipped"] == 1
```

### Success Criteria — Component 1

**Automated:**
- [x] All tests in `test_crawl_orchestrator.py` pass
- [x] All existing tests still pass: `python -m pytest tests/ -x`
- [x] No import errors: `python -c "from registry.crawl_orchestrator import CrawlOrchestrator"`

---

## Component 2: `cw9 gwt-author` Command

**New file**: `python/registry/gwt_author.py`
**Test file**: `python/tests/test_gwt_author.py`
**Modified file**: `python/registry/cli.py` (add `cmd_gwt_author` subcommand)

This command reads research notes, queries crawl.db for relevant IN:DO:OUT cards,
constructs an LLM prompt, parses the LLM output into a register-compatible JSON payload
with `depends_on` UUIDs, and prints it to stdout.

### Behavior 2.1: Extract function mentions from research notes

**Given**: A research notes file mentioning `get_user`, `validate_input`, `src/handlers/user.py`
**When**: `extract_mentions(text)` is called
**Then**: Returns `{"functions": ["get_user", "validate_input"], "files": ["src/handlers/user.py"]}`

```python
"""Tests for the GWT authoring bridge."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from registry.gwt_author import extract_mentions, build_gwt_prompt, parse_gwt_response
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


class TestExtractMentions:
    def test_finds_function_names(self):
        text = "We need to modify get_user() and validate_input() to support the new auth flow."
        result = extract_mentions(text)
        assert "get_user" in result["functions"]
        assert "validate_input" in result["functions"]

    def test_finds_file_paths(self):
        text = "The handler lives in src/handlers/user.py and the model in src/models/user.py."
        result = extract_mentions(text)
        assert "src/handlers/user.py" in result["files"]
        assert "src/models/user.py" in result["files"]

    def test_empty_text_returns_empty(self):
        result = extract_mentions("")
        assert result["functions"] == []
        assert result["files"] == []
```

### Behavior 2.2: Query crawl.db for matching records and their subgraph

**Given**: A CrawlStore with records and a set of function name mentions
**When**: `query_relevant_cards(store, mentions)` is called
**Then**: Returns the mentioned records plus their transitive dependencies

```python
class TestQueryRelevantCards:
    def test_finds_mentioned_functions(self, tmp_path: Path):
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            uid = make_record_uuid("src/user.py", "get_user")
            store.insert_record(FnRecord(
                uuid=uid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc",
                ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
                do_description="Fetches user", outs=[
                    OutField(name=OutKind.OK, type_str="User", description="found"),
                ],
            ))

            cards = query_relevant_cards(store, {"functions": ["get_user"], "files": []})
            assert len(cards) >= 1
            assert any(c.function_name == "get_user" for c in cards)

    def test_returns_empty_for_no_matches(self, tmp_path: Path):
        from registry.gwt_author import query_relevant_cards

        with CrawlStore(tmp_path / "crawl.db") as store:
            cards = query_relevant_cards(store, {"functions": ["nonexistent"], "files": []})
            assert cards == []
```

### Behavior 2.3: Build LLM prompt from research notes and cards

**Given**: Research notes text and a list of FnRecords
**When**: `build_gwt_prompt(research_text, cards)` is called
**Then**: Returns a prompt string containing both the research notes and rendered IN:DO:OUT cards

```python
class TestBuildGwtPrompt:
    def test_includes_research_and_cards(self):
        uid = make_record_uuid("src/user.py", "get_user")
        cards = [FnRecord(
            uuid=uid, function_name="get_user", file_path="src/user.py",
            line_number=10, src_hash="abc",
            ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
            do_description="Fetches user",
            outs=[OutField(name=OutKind.OK, type_str="User", description="found")],
            operational_claim="Returns user by ID",
        )]
        prompt = build_gwt_prompt("Add admin role check to get_user", cards)
        assert "Add admin role check" in prompt
        assert "get_user" in prompt
        assert uid in prompt
        assert "IN:" in prompt or "Fetches user" in prompt
```

### Behavior 2.4: Parse LLM response into register payload with depends_on

**Given**: An LLM response containing GWT JSON with depends_on UUIDs
**When**: `parse_gwt_response(response)` is called
**Then**: Returns a dict matching the `cw9 register` payload schema

```python
class TestParseGwtResponse:
    def test_parses_valid_response(self):
        uid = make_record_uuid("src/user.py", "get_user")
        response = json.dumps({
            "gwts": [{
                "criterion_id": "crawl-gwt-001",
                "given": "a user exists with ID 42",
                "when": "get_user(42) is called with admin role",
                "then": "the user profile includes admin fields",
                "depends_on": [uid],
            }]
        })
        payload = parse_gwt_response(response)
        assert len(payload["gwts"]) == 1
        assert payload["gwts"][0]["depends_on"] == [uid]
        assert payload["gwts"][0]["given"] == "a user exists with ID 42"

    def test_extracts_json_from_markdown_fences(self):
        response = '```json\n{"gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}]}\n```'
        payload = parse_gwt_response(response)
        assert len(payload["gwts"]) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            parse_gwt_response("not json at all")
```

### Behavior 2.5: Validate depends_on UUIDs against crawl.db

**Given**: A register payload with depends_on UUIDs, some valid, some invalid
**When**: `validate_depends_on(payload, store)` is called
**Then**: Invalid UUIDs are removed and logged as warnings

```python
class TestValidateDependsOn:
    def test_filters_invalid_uuids(self, tmp_path: Path):
        from registry.gwt_author import validate_depends_on

        uid_valid = make_record_uuid("src/user.py", "get_user")
        uid_invalid = "00000000-0000-0000-0000-000000000000"

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid_valid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc", ins=[], do_description="test", outs=[],
            ))

            payload = {"gwts": [{
                "criterion_id": "c1", "given": "g", "when": "w", "then": "t",
                "depends_on": [uid_valid, uid_invalid],
            }]}
            warnings = validate_depends_on(payload, store)

            assert payload["gwts"][0]["depends_on"] == [uid_valid]
            assert len(warnings) == 1
            assert uid_invalid in warnings[0]
```

### Behavior 2.6: CLI integration — cmd_gwt_author outputs to stdout

**Given**: A .cw9 project with a populated crawl.db and a research notes file
**When**: `main(["gwt-author", "--research", "notes.md", project_path])` is called with a mocked LLM
**Then**: Valid JSON is printed to stdout matching the register payload format

```python
class TestCmdGwtAuthor:
    def test_outputs_valid_json(self, tmp_path: Path, capsys, monkeypatch):
        from registry.cli import main

        # Set up project
        project = tmp_path / "project"
        project.mkdir()
        (project / ".cw9").mkdir()

        # Write a research file
        notes = tmp_path / "notes.md"
        notes.write_text("We need to modify get_user to add admin checks.")

        # Populate crawl.db
        uid = make_record_uuid("src/user.py", "get_user")
        with CrawlStore(project / ".cw9" / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="get_user", file_path="src/user.py",
                line_number=10, src_hash="abc",
                ins=[InField(name="uid", type_str="int", source=InSource.PARAMETER)],
                do_description="Fetches user",
                outs=[OutField(name=OutKind.OK, type_str="User", description="found")],
                operational_claim="Returns user by ID",
            ))

        # Mock LLM to return predictable GWTs
        mock_response = json.dumps({
            "gwts": [{
                "criterion_id": "crawl-gwt-001",
                "given": "user exists",
                "when": "get_user called",
                "then": "user returned",
                "depends_on": [uid],
            }]
        })
        monkeypatch.setattr(
            "registry.gwt_author._call_llm",
            lambda prompt: mock_response,
        )

        rc = main(["gwt-author", "--research", str(notes), str(project)])
        assert rc == 0

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "gwts" in payload
```

### Success Criteria — Component 2

**Automated:**
- [x] All tests in `test_gwt_author.py` pass
- [x] All existing tests still pass
- [x] `cw9 gwt-author --help` displays usage
- [x] Pipe test: `echo '...' | cw9 register .` accepts gwt-author output format

---

## Component 3: TypeScript Skeleton Scanner

**New file**: `python/registry/scanner_typescript.py`
**Test file**: `python/tests/test_scanner_typescript.py`

Follows the same interface as `scanner_python.py`: `scan_file(path) -> list[Skeleton]` and
`scan_directory(root, excludes) -> list[Skeleton]`. Uses line-by-line text scanning with
brace-depth counting for function boundaries.

### Behavior 3.1: scan_file extracts simple function declarations

**Given**: A TypeScript file with `function greet(name: string): string { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="greet", params, return_type="string"

```python
"""Tests for the TypeScript skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_typescript import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "greet.ts"
        src.write_text("function greet(name: string): string {\n  return `Hello ${name}`;\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "greet"
        assert s.params[0].name == "name"
        assert s.params[0].type == "string"
        assert s.return_type == "string"
        assert s.file_path == str(src)
        assert s.line_number == 1
```

### Behavior 3.2: scan_file extracts exported functions

**Given**: `export function fetchUser(id: number): Promise<User> { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with visibility="public" (export implies public)

```python
    def test_exported_function(self, tmp_path: Path):
        src = tmp_path / "user.ts"
        src.write_text("export function fetchUser(id: number): Promise<User> {\n  return db.get(id);\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchUser"
        assert skels[0].visibility == "public"
        assert skels[0].return_type == "Promise<User>"
```

### Behavior 3.3: scan_file extracts async functions

**Given**: `async function loadData(): Promise<Data[]> { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with is_async=True

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "data.ts"
        src.write_text("async function loadData(): Promise<Data[]> {\n  return await fetch('/api');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "loadData"
```

### Behavior 3.4: scan_file extracts class methods

**Given**: A TypeScript class with public and private methods
**When**: `scan_file(path)` is called
**Then**: Returns Skeletons with correct class_name, one method per entry

```python
    def test_class_methods(self, tmp_path: Path):
        src = tmp_path / "service.ts"
        src.write_text(
            "class UserService {\n"
            "  constructor(private db: Database) {}\n"
            "\n"
            "  async getUser(id: number): Promise<User> {\n"
            "    return this.db.find(id);\n"
            "  }\n"
            "\n"
            "  private validate(user: User): boolean {\n"
            "    return user.isActive;\n"
            "  }\n"
            "}\n"
        )
        skels = scan_file(src)
        methods = [s for s in skels if s.class_name == "UserService"]
        assert len(methods) >= 2
        names = {s.function_name for s in methods}
        assert "getUser" in names
        assert "validate" in names

        validate = next(s for s in methods if s.function_name == "validate")
        assert validate.visibility == "private"
```

### Behavior 3.5: scan_file extracts arrow functions assigned to const/let

**Given**: `export const handler = (req: Request): Response => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler"

```python
    def test_arrow_function(self, tmp_path: Path):
        src = tmp_path / "handler.ts"
        src.write_text(
            "export const handler = (req: Request, res: Response): void => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "req"
        assert skels[0].params[0].type == "Request"
```

### Behavior 3.6: scan_file handles multiline signatures

**Given**: A function with parameters split across multiple lines
**When**: `scan_file(path)` is called
**Then**: All parameters are captured

```python
    def test_multiline_signature(self, tmp_path: Path):
        src = tmp_path / "multi.ts"
        src.write_text(
            "function createUser(\n"
            "  name: string,\n"
            "  email: string,\n"
            "  age: number\n"
            "): User {\n"
            "  return { name, email, age };\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[2].name == "age"
        assert skels[0].params[2].type == "number"
```

### Behavior 3.7: scan_file computes file hash

**Given**: A TypeScript file
**When**: `scan_file(path)` is called twice on the same file
**Then**: The file_hash is identical and is a valid SHA-256 hex string

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.ts"
        src.write_text("function foo(): void {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64  # SHA-256 hex
```

### Behavior 3.8: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.ts"
        src.write_text("")
        assert scan_file(src) == []
```

### Behavior 3.9: scan_file handles export default function

```python
    def test_export_default_function(self, tmp_path: Path):
        src = tmp_path / "default.ts"
        src.write_text("export default function main(): void {\n  console.log('hi');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "main"
```

### Behavior 3.10: scan_directory walks .ts and .tsx files, excludes node_modules

```python
class TestScanDirectory:
    def test_walks_ts_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.ts").write_text("function a(): void {}\n")
        (tmp_path / "src" / "b.tsx").write_text("function B(): JSX.Element { return <div/>; }\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "a" in names
        assert "B" in names

    def test_excludes_node_modules(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.ts").write_text("function app(): void {}\n")
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.ts").write_text("function internal(): void {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "internal" not in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.ts").write_text("function vendored(): void {}\n")
        (tmp_path / "app.ts").write_text("function app(): void {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names
```

### Success Criteria — Component 3

**Automated:**
- [x] All tests in `test_scanner_typescript.py` pass
- [x] All existing tests still pass
- [x] `from registry.scanner_typescript import scan_file, scan_directory` works

---

## Component 4: Go Skeleton Scanner

**New file**: `python/registry/scanner_go.py`
**Test file**: `python/tests/test_scanner_go.py`

Same interface as the Python and TypeScript scanners. Go-specific:
brace-depth counting, method receivers, multiple return values, exported
(capitalized) vs unexported visibility.

### Behavior 4.1: scan_file extracts simple func declarations

```python
"""Tests for the Go skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_go import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "main.go"
        src.write_text("package main\n\nfunc Hello(name string) string {\n\treturn \"Hello \" + name\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "Hello"
        assert s.params[0].name == "name"
        assert s.params[0].type == "string"
        assert s.return_type == "string"
        assert s.visibility == "public"  # capitalized = exported
```

### Behavior 4.2: scan_file extracts method receivers

**Given**: `func (s *UserService) GetUser(id int) (*User, error) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with class_name="UserService", params excluding receiver

```python
    def test_method_receiver(self, tmp_path: Path):
        src = tmp_path / "service.go"
        src.write_text(
            "package service\n\n"
            "func (s *UserService) GetUser(id int) (*User, error) {\n"
            "\treturn s.db.Find(id)\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "GetUser"
        assert s.class_name == "UserService"
        assert s.params[0].name == "id"
        assert s.params[0].type == "int"
        assert s.return_type == "(*User, error)"
```

### Behavior 4.3: scan_file handles multiple return values

```python
    def test_multiple_returns(self, tmp_path: Path):
        src = tmp_path / "multi.go"
        src.write_text(
            "package main\n\n"
            "func Divide(a, b float64) (float64, error) {\n"
            "\tif b == 0 { return 0, fmt.Errorf(\"division by zero\") }\n"
            "\treturn a / b, nil\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].return_type == "(float64, error)"
```

### Behavior 4.4: scan_file detects exported vs unexported

**Given**: Functions `GetUser` (exported) and `validateInput` (unexported)
**When**: `scan_file(path)` is called
**Then**: Visibility is "public" for exported, "private" for unexported

```python
    def test_exported_vs_unexported(self, tmp_path: Path):
        src = tmp_path / "api.go"
        src.write_text(
            "package api\n\n"
            "func GetUser(id int) *User {\n\treturn nil\n}\n\n"
            "func validateInput(data []byte) error {\n\treturn nil\n}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        get_user = next(s for s in skels if s.function_name == "GetUser")
        validate = next(s for s in skels if s.function_name == "validateInput")
        assert get_user.visibility == "public"
        assert validate.visibility == "private"
```

### Behavior 4.5: scan_file handles named return values

```python
    def test_named_returns(self, tmp_path: Path):
        src = tmp_path / "named.go"
        src.write_text(
            "package main\n\n"
            "func ParseConfig(path string) (cfg *Config, err error) {\n"
            "\treturn nil, nil\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        # Named returns are still captured as return type
        assert "Config" in skels[0].return_type
        assert "error" in skels[0].return_type
```

### Behavior 4.6: scan_file handles parameters with shared types

**Given**: `func Add(a, b int) int`  (Go shorthand: `a, b int` means both are int)
**When**: `scan_file(path)` is called
**Then**: Both params have type "int"

```python
    def test_shared_type_params(self, tmp_path: Path):
        src = tmp_path / "math.go"
        src.write_text("package main\n\nfunc Add(a, b int) int {\n\treturn a + b\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "a"
        assert skels[0].params[0].type == "int"
        assert skels[0].params[1].name == "b"
        assert skels[0].params[1].type == "int"
```

### Behavior 4.7: scan_file computes file hash

```python
    def test_file_hash(self, tmp_path: Path):
        src = tmp_path / "hash.go"
        src.write_text("package main\n\nfunc Foo() {}\n")
        skels = scan_file(src)
        assert len(skels[0].file_hash) == 64
```

### Behavior 4.8: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.go"
        src.write_text("package main\n")
        assert scan_file(src) == []
```

### Behavior 4.9: scan_file handles interface methods (skips them — no body)

```python
    def test_skips_interface_methods(self, tmp_path: Path):
        src = tmp_path / "iface.go"
        src.write_text(
            "package api\n\n"
            "type Repository interface {\n"
            "\tFind(id int) (*User, error)\n"
            "\tSave(user *User) error\n"
            "}\n\n"
            "func Concrete(x int) int {\n\treturn x + 1\n}\n"
        )
        skels = scan_file(src)
        # Only the concrete function, not interface method signatures
        assert len(skels) == 1
        assert skels[0].function_name == "Concrete"
```

### Behavior 4.10: scan_directory walks .go files, excludes vendor and _test.go

```python
class TestScanDirectory:
    def test_walks_go_files(self, tmp_path: Path):
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "handler.go").write_text("package pkg\n\nfunc Handle() {}\n")
        (tmp_path / "pkg" / "util.go").write_text("package pkg\n\nfunc Util() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Handle" in names
        assert "Util" in names

    def test_excludes_vendor(self, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n\nfunc Main() {}\n")
        vendor = tmp_path / "vendor" / "lib"
        vendor.mkdir(parents=True)
        (vendor / "lib.go").write_text("package lib\n\nfunc Vendored() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Main" in names
        assert "Vendored" not in names

    def test_excludes_test_files(self, tmp_path: Path):
        (tmp_path / "handler.go").write_text("package main\n\nfunc Handler() {}\n")
        (tmp_path / "handler_test.go").write_text("package main\n\nfunc TestHandler() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "Handler" in names
        assert "TestHandler" not in names
```

### Success Criteria — Component 4

**Automated:**
- [x] All tests in `test_scanner_go.py` pass
- [x] All existing tests still pass
- [x] `from registry.scanner_go import scan_file, scan_directory` works

---

## Component 5: Rust Skeleton Scanner

**New file**: `python/registry/scanner_rust.py`
**Test file**: `python/tests/test_scanner_rust.py`

Same interface as the Python/TypeScript/Go scanners. Rust-specific: `impl` blocks
for class context (brace-depth stack), `trait` blocks skipped (like Go interfaces),
visibility via `pub`/`pub(crate)` keywords, lifetime annotations and generics in
signatures, `where` clauses for multi-line signatures, `&self`/`&mut self` params.

**Design decisions:**
- `pub` = "public", no `pub` = "private", `pub(crate)`/`pub(super)` = "private" (crate-internal)
- `#[cfg(test)]` module functions are **ingested** (not skipped) — used as confirmatory first pass
- `trait` blocks are skipped entirely (abstract method signatures, no body)
- Lifetime annotations stripped from param types for cleaner Skeleton output
- `where` clauses handled: return type is between `->` and `where`/`{`

### Regex Patterns (design reference)

```python
# fn hello(name: &str) -> String {
# pub fn hello(name: &str) -> String {
# pub(crate) fn process(data: Vec<u8>) -> Result<(), Error> {
# async fn fetch(url: &str) -> Result<Response, Error> {
# pub async unsafe fn raw_ptr(p: *const u8) -> u8 {
# pub(super) const fn max_size() -> usize {
_FUNC_RE = re.compile(
    r"^(\s*)"                                    # leading whitespace
    r"(pub(?:\s*\([^)]*\))?\s+)?"               # optional pub/pub(crate)/pub(super)
    r"(?:default\s+)?"                           # optional default (trait impl)
    r"(?:const\s+)?"                             # optional const
    r"(async\s+)?"                               # optional async
    r"(?:unsafe\s+)?"                            # optional unsafe
    r"(?:extern\s+\"[^\"]*\"\s+)?"              # optional extern "C"
    r"fn\s+(\w+)"                                # fn keyword + name
    r"\s*(?:<[^{(]*?>)?"                         # optional generic params <T, U>
    r"\s*\("                                     # opening paren
)

# impl UserService {
# impl<T: Clone> Repository<T> {
# impl<'a> Decoder<'a> for MyDecoder {
_IMPL_RE = re.compile(
    r"^(\s*)impl\b"                              # impl keyword
    r"(?:\s*<[^{]*?>)?"                          # optional generic params
    r"\s+(\w+)"                                  # type name
)

# trait Repository {
# pub trait Handler<T> {
_TRAIT_RE = re.compile(
    r"^(\s*)(?:pub(?:\s*\([^)]*\))?\s+)?trait\s+(\w+)"
)
```

### Behavior 5.1: scan_file extracts simple fn declarations

**Given**: A Rust file with `fn hello(name: &str) -> String { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="hello", params, return_type="String"

```python
"""Tests for the Rust skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_rust import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "lib.rs"
        src.write_text('fn hello(name: &str) -> String {\n    format!("Hello {}", name)\n}\n')
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "hello"
        assert s.params[0].name == "name"
        assert s.params[0].type == "&str"
        assert s.return_type == "String"
        assert s.visibility == "private"  # no pub = private
        assert s.file_path == str(src)
        assert s.line_number == 1
```

### Behavior 5.2: scan_file detects pub visibility

**Given**: Functions with `pub fn`, `pub(crate) fn`, `pub(super) fn`, and bare `fn`
**When**: `scan_file(path)` is called
**Then**: `pub fn` = "public", all others = "private"

```python
    def test_pub_visibility(self, tmp_path: Path):
        src = tmp_path / "vis.rs"
        src.write_text(
            "pub fn exported(x: i32) -> i32 { x }\n\n"
            "fn internal(x: i32) -> i32 { x }\n\n"
            "pub(crate) fn crate_only(x: i32) -> i32 { x }\n\n"
            "pub(super) fn parent_only(x: i32) -> i32 { x }\n"
        )
        skels = scan_file(src)
        assert len(skels) == 4
        by_name = {s.function_name: s for s in skels}
        assert by_name["exported"].visibility == "public"
        assert by_name["internal"].visibility == "private"
        assert by_name["crate_only"].visibility == "private"
        assert by_name["parent_only"].visibility == "private"
```

### Behavior 5.3: scan_file detects async fn

**Given**: `pub async fn fetch(url: &str) -> Result<Response, Error>`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with is_async=True

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "net.rs"
        src.write_text(
            "pub async fn fetch(url: &str) -> Result<Response, Error> {\n"
            "    reqwest::get(url).await\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "fetch"
        assert skels[0].visibility == "public"
```

### Behavior 5.4: scan_file extracts impl block methods with class_name

**Given**: An `impl UserService { ... }` block with methods
**When**: `scan_file(path)` is called
**Then**: Methods have class_name="UserService"

```python
    def test_impl_block_methods(self, tmp_path: Path):
        src = tmp_path / "service.rs"
        src.write_text(
            "struct UserService;\n\n"
            "impl UserService {\n"
            "    pub fn new() -> Self {\n"
            "        UserService\n"
            "    }\n\n"
            "    pub fn get_user(&self, id: u64) -> Option<User> {\n"
            "        self.db.find(id)\n"
            "    }\n\n"
            "    fn validate(&self, user: &User) -> bool {\n"
            "        user.is_active()\n"
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        for s in skels:
            assert s.class_name == "UserService"
        by_name = {s.function_name: s for s in skels}
        assert by_name["new"].visibility == "public"
        assert by_name["get_user"].visibility == "public"
        assert by_name["validate"].visibility == "private"
```

### Behavior 5.5: scan_file handles &self and &mut self params

**Given**: Methods with `&self`, `&mut self`, `self`, `mut self`
**When**: `scan_file(path)` is called
**Then**: Self params have is_self=True and are included in the params list

```python
    def test_self_params(self, tmp_path: Path):
        src = tmp_path / "methods.rs"
        src.write_text(
            "struct Foo;\n\n"
            "impl Foo {\n"
            "    fn by_ref(&self) -> i32 { 0 }\n"
            "    fn by_mut_ref(&mut self, val: i32) { self.x = val; }\n"
            "    fn by_value(self) -> Foo { self }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 3
        by_name = {s.function_name: s for s in skels}

        ref_params = by_name["by_ref"].params
        assert ref_params[0].is_self is True
        assert ref_params[0].name == "self"

        mut_params = by_name["by_mut_ref"].params
        assert mut_params[0].is_self is True
        assert mut_params[1].name == "val"
        assert mut_params[1].type == "i32"

        val_params = by_name["by_value"].params
        assert val_params[0].is_self is True
```

### Behavior 5.6: scan_file skips trait blocks

**Given**: A file with a `trait` definition and a concrete function
**When**: `scan_file(path)` is called
**Then**: Only the concrete function is returned, trait method signatures are skipped

```python
    def test_skips_trait_blocks(self, tmp_path: Path):
        src = tmp_path / "traits.rs"
        src.write_text(
            "pub trait Repository {\n"
            "    fn find(&self, id: u64) -> Option<Entity>;\n"
            "    fn save(&mut self, entity: Entity) -> Result<(), Error>;\n"
            "}\n\n"
            "fn concrete(x: i32) -> i32 {\n"
            "    x + 1\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "concrete"
```

### Behavior 5.7: scan_file handles generic functions and lifetime annotations

**Given**: Functions with generics `<T>`, lifetimes `<'a>`, and trait bounds
**When**: `scan_file(path)` is called
**Then**: Function name is captured; generic params don't pollute param list

```python
    def test_generic_function(self, tmp_path: Path):
        src = tmp_path / "generic.rs"
        src.write_text(
            "fn first<T>(items: &[T]) -> Option<&T> {\n"
            "    items.first()\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "first"
        assert skels[0].params[0].name == "items"
        assert skels[0].params[0].type == "&[T]"

    def test_lifetime_annotation(self, tmp_path: Path):
        src = tmp_path / "lifetime.rs"
        src.write_text(
            "fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {\n"
            "    if x.len() > y.len() { x } else { y }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "longest"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "x"
        assert skels[0].return_type == "&'a str"
```

### Behavior 5.8: scan_file handles where clauses

**Given**: A function with a `where` clause spanning multiple lines
**When**: `scan_file(path)` is called
**Then**: Return type is captured correctly (between `->` and `where`)

```python
    def test_where_clause(self, tmp_path: Path):
        src = tmp_path / "where_fn.rs"
        src.write_text(
            "fn display_all<T>(items: Vec<T>) -> String\n"
            "where\n"
            "    T: Display + Debug,\n"
            "{\n"
            "    items.iter().map(|i| format!(\"{}\", i)).collect()\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "display_all"
        assert skels[0].return_type == "String"
        assert skels[0].params[0].name == "items"
        assert skels[0].params[0].type == "Vec<T>"
```

### Behavior 5.9: scan_file handles multiline parameter lists

**Given**: A function with parameters split across multiple lines
**When**: `scan_file(path)` is called
**Then**: All parameters are captured

```python
    def test_multiline_params(self, tmp_path: Path):
        src = tmp_path / "multi.rs"
        src.write_text(
            "pub fn create_user(\n"
            "    name: String,\n"
            "    email: String,\n"
            "    age: u32,\n"
            ") -> Result<User, Error> {\n"
            "    Ok(User { name, email, age })\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[0].name == "name"
        assert skels[0].params[0].type == "String"
        assert skels[0].params[2].name == "age"
        assert skels[0].params[2].type == "u32"
        assert skels[0].return_type == "Result<User, Error>"
```

### Behavior 5.10: scan_file handles unsafe, const, extern fn modifiers

```python
    def test_unsafe_function(self, tmp_path: Path):
        src = tmp_path / "unsafe_fn.rs"
        src.write_text(
            "pub unsafe fn deref_raw(ptr: *const u8) -> u8 {\n"
            "    *ptr\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "deref_raw"
        assert skels[0].visibility == "public"

    def test_const_function(self, tmp_path: Path):
        src = tmp_path / "const_fn.rs"
        src.write_text(
            "pub const fn max_size() -> usize {\n"
            "    1024\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "max_size"

    def test_extern_function(self, tmp_path: Path):
        src = tmp_path / "ffi.rs"
        src.write_text(
            'pub extern "C" fn ffi_init(ctx: *mut Context) -> i32 {\n'
            "    0\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "ffi_init"
```

### Behavior 5.11: scan_file ingests functions inside #[cfg(test)] modules

**Given**: A file with a `#[cfg(test)] mod tests { ... }` block containing test functions
**When**: `scan_file(path)` is called
**Then**: Test functions are included in the output (ingested, not skipped)

```python
    def test_cfg_test_functions_ingested(self, tmp_path: Path):
        src = tmp_path / "with_tests.rs"
        src.write_text(
            "pub fn add(a: i32, b: i32) -> i32 {\n"
            "    a + b\n"
            "}\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::*;\n\n"
            "    #[test]\n"
            "    fn test_add() {\n"
            "        assert_eq!(add(2, 3), 5);\n"
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        names = {s.function_name for s in skels}
        assert "add" in names
        assert "test_add" in names
        assert len(skels) == 2
```

### Behavior 5.12: scan_file handles impl-for-trait blocks

**Given**: `impl Display for UserService { fn fmt(&self, f: &mut Formatter) -> Result { ... } }`
**When**: `scan_file(path)` is called
**Then**: Method has class_name="UserService" (the concrete type, not the trait)

```python
    def test_impl_for_trait(self, tmp_path: Path):
        src = tmp_path / "display.rs"
        src.write_text(
            "use std::fmt;\n\n"
            "struct UserService;\n\n"
            "impl fmt::Display for UserService {\n"
            "    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {\n"
            '        write!(f, "UserService")\n'
            "    }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fmt"
        assert skels[0].class_name == "UserService"
```

### Behavior 5.13: scan_file computes file hash

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.rs"
        src.write_text("fn foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64  # SHA-256 hex
```

### Behavior 5.14: scan_file returns empty list for empty/no-function files

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.rs"
        src.write_text("")
        assert scan_file(src) == []

    def test_struct_only_file(self, tmp_path: Path):
        src = tmp_path / "types.rs"
        src.write_text(
            "pub struct User {\n"
            "    pub name: String,\n"
            "    pub email: String,\n"
            "}\n"
        )
        assert scan_file(src) == []
```

### Behavior 5.15: scan_file handles nested impl blocks correctly

**Given**: Multiple impl blocks for different types in the same file
**When**: `scan_file(path)` is called
**Then**: Each method gets the correct class_name from its enclosing impl block

```python
    def test_multiple_impl_blocks(self, tmp_path: Path):
        src = tmp_path / "multi_impl.rs"
        src.write_text(
            "struct Foo;\n"
            "struct Bar;\n\n"
            "impl Foo {\n"
            "    fn do_foo(&self) -> i32 { 1 }\n"
            "}\n\n"
            "impl Bar {\n"
            "    fn do_bar(&self) -> i32 { 2 }\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        by_name = {s.function_name: s for s in skels}
        assert by_name["do_foo"].class_name == "Foo"
        assert by_name["do_bar"].class_name == "Bar"
```

### Behavior 5.16: scan_directory walks .rs files, excludes target/

```python
class TestScanDirectory:
    def test_walks_rs_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn lib_fn() {}\n")
        (tmp_path / "src" / "main.rs").write_text("fn main() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "lib_fn" in names
        assert "main" in names

    def test_excludes_target(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn app() {}\n")
        target = tmp_path / "target" / "debug"
        target.mkdir(parents=True)
        (target / "build.rs").write_text("fn build_artifact() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "build_artifact" not in names

    def test_does_not_skip_test_files(self, tmp_path: Path):
        """Rust test files are ingested for confirmatory/first-pass use."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.rs").write_text("pub fn add(a: i32, b: i32) -> i32 { a + b }\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "integration_test.rs").write_text(
            "fn test_add() {\n    assert_eq!(add(1, 2), 3);\n}\n"
        )
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "add" in names
        assert "test_add" in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.rs").write_text("fn vendored() {}\n")
        (tmp_path / "app.rs").write_text("fn app() {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names
```

### Success Criteria — Component 5

**Automated:**
- [ ] All tests in `test_scanner_rust.py` pass
- [ ] All existing tests still pass: `python -m pytest tests/ -x`
- [ ] `from registry.scanner_rust import scan_file, scan_directory` works

---

## Component 6: JavaScript Skeleton Scanner

**New file**: `python/registry/scanner_javascript.py`
**Test file**: `python/tests/test_scanner_javascript.py`

Fully independent scanner for JavaScript (not a wrapper around the TypeScript
scanner). Same interface: `scan_file(path) -> list[Skeleton]` and
`scan_directory(root, excludes) -> list[Skeleton]`. JavaScript-specific: no type
annotations, CommonJS `module.exports`/`exports.name` patterns, `.js`/`.jsx` extensions.

**Design decisions:**
- Fully independent regex set (not importing from scanner_typescript)
- No type annotations → simpler param parsing (just param names)
- CommonJS patterns detected: `module.exports = function name(...)`, `exports.name = function(...)`,
  `module.exports = (...)  =>`, `exports.name = (...) =>`
- `module.exports = function(...)` without a name → function_name derived as "default_export"
- `module.exports = (...)  =>` → function_name = "default_export"
- Class methods detected via same brace-depth approach as TypeScript
- File extensions: `*.js`, `*.jsx`
- Skip `.min.js` minified files
- Don't skip test files (matches TS scanner convention)

### Regex Patterns (design reference)

```python
# function greet(name) {
# export function greet(name) {
# export default function main() {
# async function loadData() {
_FUNC_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(async\s+)?"                      # optional async
    r"function\s+(\w+)"                 # function keyword + name
    r"\s*\("                            # opening paren
)

# const handler = (req, res) => {
# export const handler = async (req) => {
# let processor = function(data) {
_ARROW_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(?:const|let|var)\s+(\w+)"        # binding keyword + name
    r"\s*=\s*"                          # assignment
    r"(async\s+)?"                      # optional async
    r"(?:function\s*)?(?:\w+\s*)?"      # optional function keyword + name (function expression)
    r"\("                               # opening paren
)

# class UserService {
# export class UserService extends Base {
_CLASS_RE = re.compile(
    r"^(\s*)"
    r"(?:export\s+)?(?:default\s+)?"
    r"class\s+(\w+)"
)

# Method inside a class (must be indented):
#   async getUser(id) {
#   #privateMethod(data) {
_METHOD_RE = re.compile(
    r"^(\s+)"                           # must be indented
    r"(?:static\s+)?(?:get\s+|set\s+)?"  # optional static/getter/setter
    r"(async\s+)?"                      # optional async
    r"(#?\w+)"                          # method name (# for private fields)
    r"\s*\("                            # opening paren
)

# module.exports = function handler(req, res) {
# module.exports = function(req, res) {
# module.exports = (req, res) => {
# module.exports = async (req) => {
_MODULE_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"module\.exports\s*=\s*"
    r"(async\s+)?"
    r"(?:function\s+(\w+)\s*)?"         # optional function + name
    r"\("                               # opening paren
)

# exports.handler = function(req, res) {
# exports.handler = (req, res) => {
# exports.handler = async function process(req) {
_NAMED_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"exports\.(\w+)\s*=\s*"            # exports.name =
    r"(async\s+)?"                      # optional async
    r"(?:function\s*(?:\w+\s*)?)?"      # optional function keyword + optional name
    r"\("                               # opening paren
)
```

### Behavior 6.1: scan_file extracts simple function declarations

**Given**: A JavaScript file with `function greet(name) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns one Skeleton with function_name="greet", params=[name], no return type

```python
"""Tests for the JavaScript skeleton scanner."""
from __future__ import annotations

from pathlib import Path

import pytest

from registry.scanner_javascript import scan_file, scan_directory
from registry.crawl_types import Skeleton


class TestScanFile:
    def test_simple_function(self, tmp_path: Path):
        src = tmp_path / "greet.js"
        src.write_text("function greet(name) {\n  return `Hello ${name}`;\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        s = skels[0]
        assert s.function_name == "greet"
        assert s.params[0].name == "name"
        assert s.params[0].type == ""  # no type annotations in JS
        assert s.return_type is None
        assert s.file_path == str(src)
        assert s.line_number == 1
```

### Behavior 6.2: scan_file extracts exported functions

**Given**: `export function fetchUser(id) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with visibility="public"

```python
    def test_exported_function(self, tmp_path: Path):
        src = tmp_path / "user.js"
        src.write_text("export function fetchUser(id) {\n  return db.get(id);\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchUser"
        assert skels[0].visibility == "public"

    def test_export_default_function(self, tmp_path: Path):
        src = tmp_path / "default.js"
        src.write_text("export default function main() {\n  console.log('hi');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "main"
        assert skels[0].visibility == "public"
```

### Behavior 6.3: scan_file extracts async functions

```python
    def test_async_function(self, tmp_path: Path):
        src = tmp_path / "data.js"
        src.write_text("async function loadData() {\n  return await fetch('/api');\n}\n")
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].is_async is True
        assert skels[0].function_name == "loadData"
```

### Behavior 6.4: scan_file extracts arrow functions assigned to const/let/var

**Given**: `export const handler = (req, res) => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler"

```python
    def test_arrow_function(self, tmp_path: Path):
        src = tmp_path / "handler.js"
        src.write_text(
            "export const handler = (req, res) => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "req"
        assert skels[0].params[1].name == "res"
        assert skels[0].visibility == "public"  # export

    def test_async_arrow_function(self, tmp_path: Path):
        src = tmp_path / "async_arrow.js"
        src.write_text(
            "const fetchData = async (url) => {\n"
            "  return await fetch(url);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetchData"
        assert skels[0].is_async is True
```

### Behavior 6.5: scan_file extracts function expressions

**Given**: `const processor = function processData(data) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="processor" (the binding name)

```python
    def test_function_expression(self, tmp_path: Path):
        src = tmp_path / "expr.js"
        src.write_text(
            "const processor = function processData(data) {\n"
            "  return data.map(x => x * 2);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "processor"
        assert skels[0].params[0].name == "data"
```

### Behavior 6.6: scan_file extracts class methods

**Given**: A JavaScript class with methods
**When**: `scan_file(path)` is called
**Then**: Methods have correct class_name

```python
    def test_class_methods(self, tmp_path: Path):
        src = tmp_path / "service.js"
        src.write_text(
            "class UserService {\n"
            "  constructor(db) {\n"
            "    this.db = db;\n"
            "  }\n\n"
            "  async getUser(id) {\n"
            "    return this.db.find(id);\n"
            "  }\n\n"
            "  #validate(user) {\n"
            "    return user.isActive;\n"
            "  }\n"
            "}\n"
        )
        skels = scan_file(src)
        methods = [s for s in skels if s.class_name == "UserService"]
        assert len(methods) >= 2
        names = {s.function_name for s in methods}
        assert "getUser" in names
        # Private field methods (# prefix) detected
        assert "#validate" in names or "validate" in names
```

### Behavior 6.7: scan_file extracts module.exports function

**Given**: `module.exports = function handler(req, res) { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeleton with function_name="handler", visibility="public"

```python
    def test_module_exports_named_function(self, tmp_path: Path):
        src = tmp_path / "server.js"
        src.write_text(
            "module.exports = function handler(req, res) {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "handler"
        assert skels[0].visibility == "public"

    def test_module_exports_anonymous_function(self, tmp_path: Path):
        src = tmp_path / "anon.js"
        src.write_text(
            "module.exports = function(data) {\n"
            "  return process(data);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "default_export"
        assert skels[0].visibility == "public"

    def test_module_exports_arrow(self, tmp_path: Path):
        src = tmp_path / "arrow_export.js"
        src.write_text(
            "module.exports = (req, res) => {\n"
            "  res.send('ok');\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "default_export"
        assert skels[0].visibility == "public"
```

### Behavior 6.8: scan_file extracts exports.name patterns

**Given**: `exports.handler = function(req, res) { ... }` and `exports.validate = (data) => { ... }`
**When**: `scan_file(path)` is called
**Then**: Returns Skeletons with function names from the exports property

```python
    def test_named_exports_function(self, tmp_path: Path):
        src = tmp_path / "routes.js"
        src.write_text(
            "exports.getUser = function(id) {\n"
            "  return db.find(id);\n"
            "};\n\n"
            "exports.createUser = (name, email) => {\n"
            "  return db.insert({ name, email });\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        names = {s.function_name for s in skels}
        assert "getUser" in names
        assert "createUser" in names
        for s in skels:
            assert s.visibility == "public"

    def test_exports_async_function(self, tmp_path: Path):
        src = tmp_path / "async_exports.js"
        src.write_text(
            "exports.fetch = async function fetchData(url) {\n"
            "  return await get(url);\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].function_name == "fetch"
        assert skels[0].is_async is True
```

### Behavior 6.9: scan_file handles multiline signatures

```python
    def test_multiline_params(self, tmp_path: Path):
        src = tmp_path / "multi.js"
        src.write_text(
            "function createUser(\n"
            "  name,\n"
            "  email,\n"
            "  age\n"
            ") {\n"
            "  return { name, email, age };\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 3
        assert skels[0].params[2].name == "age"
```

### Behavior 6.10: scan_file handles destructured and rest parameters

```python
    def test_rest_params(self, tmp_path: Path):
        src = tmp_path / "rest.js"
        src.write_text(
            "function collect(first, ...rest) {\n"
            "  return [first, ...rest];\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert len(skels[0].params) == 2
        assert skels[0].params[0].name == "first"
        assert skels[0].params[1].name == "rest"

    def test_default_params(self, tmp_path: Path):
        src = tmp_path / "defaults.js"
        src.write_text(
            "function greet(name = 'World') {\n"
            "  return `Hello ${name}`;\n"
            "}\n"
        )
        skels = scan_file(src)
        assert len(skels) == 1
        assert skels[0].params[0].name == "name"
```

### Behavior 6.11: scan_file computes file hash

```python
    def test_file_hash_deterministic(self, tmp_path: Path):
        src = tmp_path / "hash.js"
        src.write_text("function foo() {}\n")
        skels1 = scan_file(src)
        skels2 = scan_file(src)
        assert skels1[0].file_hash == skels2[0].file_hash
        assert len(skels1[0].file_hash) == 64
```

### Behavior 6.12: scan_file returns empty list for empty file

```python
    def test_empty_file(self, tmp_path: Path):
        src = tmp_path / "empty.js"
        src.write_text("")
        assert scan_file(src) == []
```

### Behavior 6.13: scan_file handles mixed CommonJS and ES module patterns

**Given**: A file mixing `exports.name = ...` and `function` declarations
**When**: `scan_file(path)` is called
**Then**: All functions are captured without duplicates

```python
    def test_mixed_patterns(self, tmp_path: Path):
        src = tmp_path / "mixed.js"
        src.write_text(
            "function validate(data) {\n"
            "  return data != null;\n"
            "}\n\n"
            "exports.handler = function(req, res) {\n"
            "  if (validate(req.body)) {\n"
            "    res.send('ok');\n"
            "  }\n"
            "};\n"
        )
        skels = scan_file(src)
        assert len(skels) == 2
        names = {s.function_name for s in skels}
        assert "validate" in names
        assert "handler" in names
```

### Behavior 6.14: scan_directory walks .js and .jsx files

```python
class TestScanDirectory:
    def test_walks_js_files(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("function app() {}\n")
        (tmp_path / "src" / "Button.jsx").write_text(
            "function Button(props) {\n  return <button>{props.label}</button>;\n}\n"
        )
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "Button" in names

    def test_excludes_node_modules(self, tmp_path: Path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("function app() {}\n")
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("function internal() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "internal" not in names

    def test_excludes_min_js(self, tmp_path: Path):
        (tmp_path / "app.js").write_text("function app() {}\n")
        (tmp_path / "bundle.min.js").write_text("function minified() {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "minified" not in names

    def test_custom_excludes(self, tmp_path: Path):
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.js").write_text("function vendored() {}\n")
        (tmp_path / "app.js").write_text("function app() {}\n")
        skels = scan_directory(tmp_path, excludes=["vendor"])
        names = {s.function_name for s in skels}
        assert "app" in names
        assert "vendored" not in names

    def test_does_not_scan_ts_files(self, tmp_path: Path):
        """JavaScript scanner only handles .js/.jsx, not .ts/.tsx."""
        (tmp_path / "app.js").write_text("function jsApp() {}\n")
        (tmp_path / "app.ts").write_text("function tsApp(): void {}\n")
        skels = scan_directory(tmp_path)
        names = {s.function_name for s in skels}
        assert "jsApp" in names
        assert "tsApp" not in names
```

### Success Criteria — Component 6

**Automated:**
- [ ] All tests in `test_scanner_javascript.py` pass
- [ ] All existing tests still pass: `python -m pytest tests/ -x`
- [ ] `from registry.scanner_javascript import scan_file, scan_directory` works

---

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
