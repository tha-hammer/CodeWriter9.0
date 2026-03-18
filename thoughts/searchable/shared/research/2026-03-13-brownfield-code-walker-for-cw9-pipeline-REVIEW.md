---
title: "Plan Review: Brownfield Code Walker for CW9 Pipeline (Post-Phase-3)"
date: 2026-03-13
reviewer: claude-opus
plan: thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md
tags: [review, brownfield, code-walker, in-do-out, pipeline]
status: complete
review_type: post-implementation-validation
implementation_commit: 66c4f88
---

# Plan Review Report: Brownfield Code Walker for CW9 Pipeline

**Scope:** Post-Phase-3 review validating plan assumptions against actual implementation.
Phases 1-3 are implemented (commit 66c4f88). Phases 4-5 remain.

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 3 issues (1 critical) |
| Interfaces | ⚠️ | 4 issues |
| Promises | ⚠️ | 2 issues |
| Data Models | ✅ | 1 minor issue |
| APIs | ⚠️ | 3 issues |

---

## Contract Review

### Well-Defined

- ✅ **crawl.db ↔ dag.json boundary** — Clean ownership correctly implemented. crawl.db owns IN:DO:OUT records (CrawlStore), dag.json owns GWT/requirement/spec/template nodes (RegistryDag). They connect through shared node UUIDs. `bridge_crawl_to_dag()` (crawl_bridge.py:17-75) is the only write bridge; `query_context()` (one_shot_loop.py:151-159) is the only read bridge.
- ✅ **Pydantic at LLM boundary** — `InField`, `OutField`, `FnRecord`, `AxRecord` use Pydantic with `field_validator`; `Skeleton`, `EntryPoint`, `MapNote`, `TestReference` use `@dataclass`. Clean boundary matching the plan's design decision (crawl_types.py).
- ✅ **CrawlStore API** — Single class owns all crawl.db reads/writes. 20 public methods fully implemented with per-function SQLite commits for resumability. No raw SQL outside this class.
- ✅ **UUID generation contract** — Deterministic `uuid5(CRAWL_NAMESPACE, "file_path::class_name::function_name")` at crawl_types.py:21-29. Stable across re-ingests. Verified by 7 tests in `TestMakeRecordUuid`.
- ✅ **merge_registered_nodes(crawl_uuids=)** — dag.py:382-416. Correctly preserves crawl nodes by checking `nid in crawl_uuids`. Edge preservation transfers edges where at least one endpoint is newly merged AND both exist. 3 tests cover all cases.
- ✅ **remove_node()** — dag.py:373-380. Silent no-op on missing ID, removes node + all incident edges, recomputes closure and components. 3 tests confirm.
- ✅ **add_node() is silent upsert** — dag.py:37 is `self.nodes[node.id] = node`, always overwrites. Plan's assumption confirmed.
- ✅ **add_edge() duplicate handling** — dag.py:55-59 silently returns on duplicate (same from/to/type). Different edge types between same pair allowed. Cycle detection via closure check.

### Missing or Unclear

- ❌ **OneShotLoop.query() does not pass state_root to query_context()** — `query_context()` (one_shot_loop.py:114) accepts `state_root: Path | None = None` and only loads cards when provided. `OneShotLoop.query()` (one_shot_loop.py:856) calls `query_context(self.dag, behavior_id)` WITHOUT `state_root`. **Cards are never loaded through the pipeline path.** The entire brownfield→pipeline integration is broken at this junction point. The plan specifies this integration but the implementation has a gap. `OneShotLoop` likely has access to `state_root` via `self.ctx` but doesn't thread it through.

- ⚠️ **backfill_source_uuids() disambiguation** — crawl_store.py:462 uses `LIMIT 1` when multiple records share a `function_name`. For overloaded names across different files, the first row returned by SQLite wins. The plan says "look up source_function in the records table" without specifying collision handling. Could produce incorrect provenance edges.

- ⚠️ **AX record retrieval collapses to FnRecord** — `get_record()` / `_row_to_fn_record()` always returns `FnRecord`, even for `is_external=TRUE` rows. `AxRecord`-specific fields (`source_crate`, `boundary_contract`) are stored in SQL but the read path doesn't return `AxRecord`. Low priority since AX cards are terminal nodes.

### Recommendations

1. **Fix OneShotLoop.query()** — Pass `self.ctx.state_root` as `state_root` to `query_context()`. One-line fix but critical for pipeline integration.
2. **Disambiguate backfill** — Add `WHERE file_path = ?` using the caller's `source_file` when available, or `ORDER BY file_path` for deterministic `LIMIT 1`.

---

## Interface Review

### Well-Defined

- ✅ **CrawlStore public API** — 20 methods covering CRUD, staleness, subgraph, backfill, validation, crawl runs, entry points, test refs, maps. All implemented, no stubs.
- ✅ **RegistryDag extensions** — `remove_node()` and `merge_registered_nodes(crawl_uuids=)` match plan exactly. `add_node()` confirmed as silent upsert.
- ✅ **scanner_python.py interface** — `scan_file(path: Path) -> list[Skeleton]` and `scan_directory(root: Path, excludes: list[str] | None = None) -> list[Skeleton]` match plan's explicit scanner interface. 15 tests for scan_file, 3 for scan_directory.
- ✅ **bridge_crawl_to_dag() interface** — Returns `dict[str, int]` with `nodes_added`, `edges_added`, `orphans_removed`. 6 tests plus 5 for `_looks_like_uuid`.
- ✅ **cmd_register depends_on** — cli.py:508-514 iterates `gwt.get("depends_on", [])` and creates DEPENDS_ON edges. Exceptions silently caught.
- ✅ **cmd_extract preserves crawl nodes** — cli.py:225-229 checks for crawl.db, queries `get_all_uuids()`, passes `crawl_uuids` to `merge_registered_nodes()`.

### Missing or Unclear

- ⚠️ **scan_directory() is not polyglot** — Currently Python-only (`root.rglob("*.py")`). Plan specifies "shared infrastructure that dispatches to appropriate scan_file based on file extension." When TS/Go scanners are added, `scan_directory` needs refactoring from Python-specific to dispatcher. Design the dispatch interface before adding new scanners.

- ⚠️ **Entry point exclude sets diverge from scanner excludes** — `scanner_python.py` uses `DEFAULT_EXCLUDES` (14 patterns: node_modules, .git, .venv, vendor, etc.). `entry_points.py` uses narrower inline check: `part.startswith(".") or part == "__pycache__"`. Entry point discovery will traverse directories the scanner skips, potentially finding false entry points in vendored/dependency code.

- ⚠️ **No IMPORTS edges created** — Plan specifies three edge types during ingestion: CALLS, DEPENDS_ON, IMPORTS. Implementation creates only CALLS edges. Module-level import relationships are never captured. The plan doesn't specify how to extract imports, and the scanner doesn't track them.

- ⚠️ **Entry point edge types (HANDLES/IMPORTS) skipped by bridge** — Plan (research doc line 1213-1214) specifies `HANDLES` for HTTP, `IMPORTS` for CLI. Bridge (crawl_bridge.py:58-59) explicitly skips with comment: "Entry point edges are already captured through CALLS edges from the DFS crawl." Deliberate divergence, but the DAG won't distinguish route handling from function calls.

### Recommendations

1. **Unify exclude sets** — Extract `DEFAULT_EXCLUDES` to a shared constant.
2. **Document the IMPORTS edge decision** — Either implement or explicitly remove from plan.
3. **Plan scan_directory dispatcher** before adding TS/Go scanners.

---

## Promise Review

### Well-Defined

- ✅ **Crawl resumability** — Per-function SQLite commits with WAL mode. Incremental mode (cli.py:814-817) skips records with matching hashes.
- ✅ **Staleness detection** — File-level SHA-256 + recursive CTE for transitive propagation. `get_stale_records()` + `get_transitive_stale()` implement the exact algorithm. 4 tests.
- ✅ **Orphan cleanup** — bridge identifies RESOURCE nodes not in crawl.db and removes via `remove_node()`. `_looks_like_uuid()` prevents accidentally removing gwt/req nodes.
- ✅ **Idempotent re-ingest** — `add_node()` silent upsert, `add_edge()` skips duplicates, `upsert_record()` deletes-then-inserts. Multiple runs produce same result.

### Missing or Unclear

- ⚠️ **Bridge nodes_added counter inflated on re-ingest** — `bridge_crawl_to_dag()` increments `nodes_added` for every record including pre-existing ones (because `add_node()` is silent upsert). Can't distinguish "created" vs "updated". Plan's output format (research doc lines 615-617) shows `289 created, 0 updated` but implementation can't produce separate counts.

- ⚠️ **DFS crawl orchestrator not yet implemented** — Plan's Phase 1 (LLM extraction) is the core value proposition. `cmd_ingest` stores skeleton-only records with `do_description="SKELETON_ONLY"`. TDD plan correctly identifies this as first remaining component. Plan's retry policy (3 retries, exponential backoff), EXTRACTION_FAILED stubs, and source_uuid backfill are well-specified but unimplemented.

### Recommendations

1. **Split bridge counter** — Check `dag.nodes` before `add_node()` to count created vs updated.
2. **Prioritize crawl_orchestrator.py** — Without LLM extraction, cards lack behavioral info.

---

## Data Model Review

### Well-Defined

- ✅ **SQLite schema matches plan exactly** — Every table, view, index, column, type, CHECK constraint, and foreign key from the plan's specification is present in `_SCHEMA_SQL`. Only structural difference: `records` UNIQUE as `CREATE UNIQUE INDEX` vs inline (functionally identical).
- ✅ **Pydantic models match plan** — All enums, Pydantic models, and dataclasses match field-for-field. Validators are correct.
- ✅ **ContextBundle.cards** — `cards: list = field(default_factory=list)` at one_shot_loop.py:95.
- ✅ **Node/Edge/EdgeType** — 21 edge types. `Node.resource()` factory available for RESOURCE nodes.
- ✅ **Serialization** — dag.json round-trips. crawl.db uses JSON arrays for list fields.

### Missing or Unclear

- ⚠️ **TestReference.target_uuid in implementation but not plan's dataclass** — Plan's Python `@dataclass` (research doc lines 807-819) omits `target_uuid`, but SQL schema and store methods reference it. Implementation correctly includes it (crawl_types.py:211). Inconsistency in plan document, not code.

### Recommendations

1. **Update plan's TestReference dataclass** to include `target_uuid`.

---

## API Review (CLI Commands)

### Well-Defined

- ✅ **`cw9 ingest`** — Fully implemented (cli.py:760-879). Supports `--lang`, `--incremental`, `--max-functions`, `--json`. Runs all phases: skeleton pre-pass, entry point discovery, CrawlStore population, dag.json bridge.
- ✅ **`cw9 stale`** — Fully implemented (cli.py:882-923). Computes hashes, identifies direct/transitive stale, prints with annotations.
- ✅ **`cw9 show --card`** — Fully implemented (cli.py:926-979). Renders markdown IN:DO:OUT cards.
- ✅ **`cw9 register` depends_on** — cli.py:508-514 creates DEPENDS_ON edges from `gwt.get("depends_on", [])`.
- ✅ **`cw9 extract` crawl preservation** — cli.py:225-229 queries crawl.db UUIDs and passes to merge.
- ✅ **format_prompt_context() cards** — one_shot_loop.py:193-199 renders `## Existing Code Behavior (IN:DO:OUT Cards)` via `render_card()`.

### Missing or Unclear

- ⚠️ **`--skip-setup` on `cw9 pipeline`** — Plan's modified pipeline flow (research doc line 644) shows `cw9 pipeline --gwt=gwt-0001 --skip-setup`. Not verified whether this flag exists in the argparse registration (cli.py:1063-1073). If missing, brownfield users running `cw9 pipeline` after ingest trigger unnecessary `cmd_extract`.

- ⚠️ **`cw9 gwt-author` not implemented** — Plan specifies this as the critical LLM-assisted bridge from research notes + IN:DO:OUT cards to GWT JSON with `depends_on` UUIDs. Phase 4 item 18. Without it, users must manually construct depends_on UUIDs.

- ⚠️ **Dead code in entry_points.py** — Three items:
  - `_ARGPARSE_ADD_RE` (line 161): compiled regex, never used. Argparse CLIs without decorators won't be detected.
  - `_ROUTE_DECORATORS` list (lines 86-93): assembled but never iterated. Django urlpatterns unreachable.
  - `detect_codebase_type()` annotation `-> str | None` but never returns `None` (always falls to `"library"`).

### Recommendations

1. **Verify `--skip-setup` exists** on pipeline subcommand.
2. **Clean up dead code** in entry_points.py.
3. **Fix `detect_codebase_type()` return annotation** to `-> str`.

---

## Critical Issues (Must Address Before Remaining Phases)

### 1. OneShotLoop.query() Doesn't Pass state_root

**Location:** one_shot_loop.py:856
**Severity:** CRITICAL
**What:** `OneShotLoop.query()` calls `query_context(self.dag, behavior_id)` without `state_root`. Cards are never loaded through the pipeline path.
**Impact:** Running `cw9 pipeline` after `cw9 ingest` produces prompts with zero IN:DO:OUT card context. The LLM sees GWT specs but no behavioral data from the ingested codebase. This defeats the core purpose of the brownfield walker.
**Fix:** Pass `self.ctx.state_root` (or equivalent) as `state_root`. Also verify `loop_runner.py`'s `run_loop()` threads state_root through.

### 2. DFS Crawl Orchestrator Not Implemented

**Location:** Missing file `python/registry/crawl_orchestrator.py`
**Severity:** BLOCKING (for value delivery, not for existing tests)
**What:** Phase 1 LLM extraction doesn't exist. `cmd_ingest` stores skeleton-only records.
**Impact:** All IN:DO:OUT cards are empty shells — no do_steps, no ins with internal_call, no outs. Even with Issue 1 fixed, cards contain no useful behavioral information.
**Fix:** First item in TDD remaining plan. Specification is thorough.

---

## Non-Critical Issues

| # | Issue | Location | Priority |
|---|-------|----------|----------|
| 3 | Dead code: `_compute_file_hash()` | scanner_python.py:32-33 | Low |
| 4 | Dead code: `_ROUTE_DECORATORS`, `_ARGPARSE_ADD_RE` | entry_points.py:86-93, 161 | Low |
| 5 | Exclude set divergence scanner vs entry_points | scanner_python.py / entry_points.py | Medium |
| 6 | Bridge counter can't distinguish created vs updated | crawl_bridge.py | Low |
| 7 | backfill LIMIT 1 nondeterminism | crawl_store.py:462 | Medium |
| 8 | `detect_codebase_type()` return annotation wrong | entry_points.py | Low |
| 9 | No IMPORTS edges (plan specifies, impl doesn't create) | crawl_bridge.py | Medium |

---

## Suggested Plan Amendments

```diff
# In "How This Feeds the Existing CW9 Pipeline" section:

+ Add: "NOTE: OneShotLoop.query() must thread state_root from self.ctx
+  to query_context() for cards to load through the pipeline path.
+  Without this, bundle.cards will be empty."

# In scan_directory specification:

~ Modify: "scan_directory() is currently Python-only. Before adding TS/Go
  scanners, design the polyglot dispatch interface so all scanners
  coexist under a single scan_directory entry point."

# In TestReference dataclass:

+ Add: target_uuid: str | None = None  # matches SQL schema

# In edge types specification:

~ Modify: Either implement IMPORTS edges or explicitly remove from spec.
~ Modify: Acknowledge bridge decision to skip HANDLES/IMPORTS edge types
  in favor of uniform CALLS edges.

# In backfill specification:

+ Add: "When multiple records share a function_name, disambiguate by
  file_path match. Use source_file from the InField when available."

# In entry_points.py specification:

+ Add: "Exclude sets must match scanner_python.py DEFAULT_EXCLUDES
  to avoid false entry points in vendored code."
```

---

## Approval Status

- [x] **Ready for Implementation** — All review findings incorporated into plan
- [ ] ~~**Needs Minor Revision** — Fix the OneShotLoop.query() state_root gap before proceeding~~
- [ ] **Needs Major Revision** — Critical issues must be resolved first

**Rationale:** The plan is exceptionally thorough. Phases 1-3 implementation is high quality with 80+ tests and zero skips. The SQLite schema, data models, CrawlStore API, scanner, entry point discovery, bridge, and DAG extensions all match the plan closely. The critical `state_root` gap is a one-line fix. The crawl orchestrator (Phase 4) is well-specified in the TDD remaining plan. All other issues are minor and addressable during implementation.
