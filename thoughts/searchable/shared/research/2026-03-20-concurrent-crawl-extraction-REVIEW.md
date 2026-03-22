---
date: 2026-03-20T00:00:00Z
reviewer: DustyForge
git_commit: 80b5a7d
branch: master
repository: CodeWriter9.0
topic: "Plan review: Concurrent crawl extraction pipeline"
tags: [review, cw9, performance, concurrency, crawl-pipeline]
status: complete
reviewed_plan: thoughts/searchable/shared/research/2026-03-19-concurrent-crawl-extraction.md
---

# Plan Review Report: Concurrent Crawl Extraction Pipeline

## Critical Meta-Finding: Plan Describes Already-Implemented Work

The research document (`2026-03-19-concurrent-crawl-extraction.md`) was written
at commit `b0af29b`. The current codebase at commit `80b5a7d` has **already
implemented all four proposed changes**:

| Proposed Change | Status | Current Location |
|---|---|---|
| Change 1: `_build_async_extract_fn()` using standalone `query()` | **Done** | `cli.py:1387–1495` |
| Change 2: Async `_sweep_remaining()` with `Semaphore` + `gather` | **Done** | `crawl_orchestrator.py:370–395` |
| Change 3: Async-first orchestrator (`async def run/extract_one/dfs_extract`) | **Done** | `crawl_orchestrator.py:108–368` |
| Change 4: `--concurrency` CLI flag | **Done** | `cli.py:1703–1719`, default=10 |

The intervening commits (`d900881`, `727b582`, `9b89082`, `6dc8ad8`, `80b5a7d`)
converted the pipeline to async-native with semaphore-bounded concurrency, fixed
SQLite corruption issues, and added graceful shutdown.

**Recommendation**: Update the research document's `status` to `implemented` and
add a note referencing the implementing commits. The document remains valuable as
architectural rationale but should not be treated as a forward-looking plan.

---

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ✅ | 0 critical, 1 warning |
| Interfaces | ✅ | 0 critical, 1 warning |
| Promises | ⚠️ | 0 critical, 2 warnings |
| Data Models | ✅ | 0 critical, 0 warnings |
| APIs | ✅ | 0 critical, 1 warning |

---

## Contract Review

### Well-Defined

- ✅ **`extract_fn` contract** — `(skeleton: Skeleton, body: str, error_feedback: str | None = None) -> FnRecord | Coroutine[FnRecord]`. The orchestrator handles both sync and async callables via `asyncio.iscoroutine()` check at `crawl_orchestrator.py:144`. The placeholder UUID (`00000000-...`) is overwritten at line 147.

- ✅ **`upsert_record()` atomicity** — Uses `BEGIN IMMEDIATE` with try/rollback at `crawl_store.py:288–301`. Four-step atomic sequence: NULL reverse FK refs → DELETE record (cascades) → INSERT record + ins + outs → COMMIT. No `await` inside, so it completes in a single event-loop turn under asyncio.

- ✅ **Error feedback contract** — Only the most recent exception string is passed as `error_feedback`. Tests at `test_concurrent_extraction.py:222–265` (`test_error_feedback_is_only_from_last_failure`) prove this with escalating errors A→B→C, asserting each retry sees only its predecessor's error.

- ✅ **Context isolation** — Standalone `query()` in `_build_async_extract_fn()` creates a fresh session per call. No `ClaudeSDKClient` is instantiated. Test suite (`TestIndependentExtractions`, `TestSweepPhaseIndependence`) verifies no cross-contamination between extractions.

- ✅ **Retry exhaustion contract** — After `max_retries` failures, `extract_one()` stores an `EXTRACTION_FAILED` stub record with `failure_modes` containing the last error string, then returns `None`. This ensures the record is never silently lost.

### Warning

- ⚠️ **`_build_extract_fn()` / `_build_llm_fn()` are dead code** — The legacy sync factories at `cli.py:1188–1384` are no longer called by `cmd_crawl()` (which uses `_build_async_extract_fn()` at line 1141). They increase maintenance surface and could confuse future developers.
  - **Recommendation**: Remove or mark as deprecated. If kept for testing, add a `# LEGACY:` comment.

---

## Interface Review

### Well-Defined

- ✅ **`CrawlOrchestrator.__init__` signature** — Clean constructor at `crawl_orchestrator.py:77–106` with all parameters typed and defaulted. `concurrency` defaults to 10, `max_retries` defaults to `MAX_RETRIES=5`, `on_progress` defaults to no-op lambda.

- ✅ **`run()` return value** — Returns `dict[str, int]` with keys `extracted`, `failed`, `skipped`, `ax_records`. Consumed by `cmd_crawl()` at `cli.py:1158–1184` for summary output.

- ✅ **`_on_progress` callback interface** — `(event: str, **kwargs) -> None`. Four event strings: `"extracted"`, `"retry"`, `"failed"`, `"skipped"`. Each with documented kwargs (function_name, file_path, attempt, etc.).

- ✅ **CLI argument interface** — Seven arguments with sensible defaults. `--concurrency` validated by `_positive_int`. `--entry` uses `action="append"` for multiple values.

### Warning

- ⚠️ **`_on_progress("skipped")` not fired in sweep phase** — `_dfs_extract()` fires `"skipped"` at line 307, but `_sweep_remaining._extract_bounded()` increments `self._skipped` at line 385 without firing the progress event. This means the progress callback is incomplete during sweep.
  - **Impact**: Users see no output for skipped records in sweep phase (only the counter in the final summary is correct).
  - **Recommendation**: Add `self._on_progress("skipped", function_name=..., file_path=...)` in `_extract_bounded` after the skip check.

---

## Promise Review

### Well-Defined

- ✅ **Context isolation guarantee** — Standalone `query()` creates a fresh session per call. No accumulated context between cards. Verified by `test_sweep_extractions_dont_share_state` and `test_concurrent_simulation_no_cross_contamination`.

- ✅ **Graceful shutdown** — Signal handlers for SIGINT/SIGTERM registered via asyncio-safe `loop.add_signal_handler()` at `crawl_orchestrator.py:332–341`. Removed in `finally` block. `_shutdown_requested` checked at DFS entry, sweep entry, and before each extraction.

- ✅ **Failure isolation in sweep** — `asyncio.gather(*tasks, return_exceptions=True)` at `crawl_orchestrator.py:395` prevents one task's exception from canceling the batch.

- ✅ **CrawlStore safety under asyncio** — Single-threaded event loop means `check_same_thread=True` (default) is not violated. Synchronous SQLite calls complete atomically within each event-loop turn. `BEGIN IMMEDIATE` in `upsert_record()` serializes multi-statement writes.

### Warnings

- ⚠️ **`max_functions` overshoot** — The check at `_extract_bounded` line 382 runs outside the semaphore. Up to `concurrency - 1` extra extractions can slip through when `_extracted` is near the limit. The research document acknowledges this as acceptable.
  - **Impact**: With `--concurrency=10 --max-functions=100`, up to 109 functions could be extracted.
  - **Recommendation**: If strict enforcement matters, move the check inside `async with sem:` or use an `asyncio.Event` to signal early stop. Otherwise, document the behavior.

- ⚠️ **`safe_disconnect()` not needed on current active path, but no fallback if `query()` hangs** — The active `_build_async_extract_fn()` uses standalone `query()` which manages its own lifecycle — no `connect()`/`disconnect()` calls. The `safe_disconnect()` pattern (10s timeout + `_tg` cancel) exists in `loop_runner.py:39–52` and `tdd_implement_plan.py:42–72` but is not used by the crawl pipeline. If the standalone `query()` async generator itself hangs, there is no timeout wrapper.
  - **Impact**: A hung `query()` call would block a semaphore slot indefinitely.
  - **Recommendation**: Consider wrapping each `query()` iteration in `asyncio.wait_for()` with a generous timeout (e.g., 120s for LLM response). This mirrors the `safe_disconnect` pattern but at the query level.

---

## Data Model Review

### Well-Defined

- ✅ **`FnRecord` / `AxRecord` / `Skeleton` types** — Defined in `crawl_types.py`. `FnRecord` has typed `ins: list[InField]`, `outs: list[OutField]`. `InSource` and `OutKind` are enums with exhaustive variants.

- ✅ **SQLite schema** — `_SCHEMA_SQL` in `crawl_store.py:29+` uses `CREATE TABLE IF NOT EXISTS` (idempotent). WAL mode + `PRAGMA foreign_keys = ON`. `ON DELETE CASCADE` on `ins`/`outs` tables. `records.uuid` is `PRIMARY KEY`.

- ✅ **`do_description` sentinel values** — Two sentinel strings drive the pipeline state machine: `"SKELETON_ONLY"` (needs extraction) and `"EXTRACTION_FAILED"` (retry exhausted). `get_pending_uuids()` selects exactly these two values.

- ✅ **UUID determinism** — `make_record_uuid(file_path, function_name, class_name)` produces deterministic UUID5 values. Tests use the same function for fixture UUIDs.

---

## API Review

### Well-Defined

- ✅ **CLI `crawl` subcommand** — Fully specified at `cli.py:1703–1719`. Seven arguments with types, defaults, and help text. `target_dir` is positional-optional (defaults to `.`).

- ✅ **`cmd_crawl` exit codes** — Returns `1` on missing `crawl.db` or no entry points found. Returns `0` on success. Machine-readable output via `--json`.

- ✅ **Entry point resolution** — Three-tier fallback: `--entry` args → `store.get_entry_points()` → all `SKELETON_ONLY` records. Documented via code flow at `cli.py:1047–1064`.

### Warning

- ⚠️ **`--model` default discrepancy** — Argparse default is `None` (`cli.py:1714`), then `cmd_crawl` resolves `args.model or "claude-sonnet-4-6"` at line 1069. Meanwhile `_build_async_extract_fn` has its own default `model="claude-sonnet-4-6"`. If anyone calls `_build_async_extract_fn()` without passing model, it uses its own default regardless of CLI. The double-default is a maintenance risk.
  - **Recommendation**: Remove the default from `_build_async_extract_fn` signature and always pass explicitly from `cmd_crawl`.

---

## Critical Issues (Must Address Before Implementation)

**None.** All proposed changes are already implemented.

---

## Non-Critical Issues (Recommended Cleanup)

1. **Dead code**: `_build_extract_fn()` and `_build_llm_fn()` at `cli.py:1188–1384` are unreachable from the active crawl path. Remove or mark deprecated.

2. **Missing progress event**: `_sweep_remaining._extract_bounded()` does not fire `"skipped"` progress event (line 385 increments counter but no callback).

3. **`max_functions` overshoot**: Up to `concurrency - 1` extra extractions possible. Document or fix.

4. **No timeout on `query()` calls**: Standalone `query()` has no timeout wrapper. A hung LLM call blocks a semaphore slot indefinitely.

5. **Double model default**: Both `cmd_crawl` and `_build_async_extract_fn` default to `"claude-sonnet-4-6"` independently.

6. **Research document status**: `2026-03-19-concurrent-crawl-extraction.md` should be updated to `status: implemented`.

---

## Suggested Plan Amendments

```diff
# In the research document frontmatter:

- status: complete
+ status: implemented
+ implemented_by: commits d900881..80b5a7d

# In the Proposed Changes section:

+ NOTE: All four proposed changes were implemented between commits
+ d900881 ("Convert crawl pipeline to async-native with semaphore-bounded
+ concurrency") and 80b5a7d ("Fix cmd_crawl to use ProjectContext for
+ state_root resolution"). The descriptions below match the current
+ codebase implementation.
```

---

## Approval Status

- [x] **Already Implemented** — All proposed changes exist in the current codebase
- [ ] ~~Ready for Implementation~~
- [ ] ~~Needs Minor Revision~~
- [ ] ~~Needs Major Revision~~

The research document is architecturally sound. The implementation matches the
design. The non-critical issues above are cleanup items, not blockers.
