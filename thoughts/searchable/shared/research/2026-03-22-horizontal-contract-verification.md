---
date: 2026-03-22T00:00:00Z
researcher: DustyForge
git_commit: 7325cb2
branch: master
repository: CodeWriter9.0
topic: "Horizontal Contract Verification (Seam Checking)"
tags: [research, cw9, seam-checking, type-safety, crawl-store]
status: complete
last_updated: 2026-03-22
last_updated_by: DustyForge
cw9_project: /home/maceo/Dev/CodeWriter9.0
---

# Research: Horizontal Contract Verification (Seam Checking)

## Research Question

CW9 verifies **vertical contracts** (each function meets its own spec) but not **horizontal contracts** (caller output satisfies callee input). Can we add a `cw9 seams` command that cross-references existing crawl.db data to detect type mismatches at function boundaries?

## Current Repository State (as of 7325cb2)

### GWT ID Allocation

- **Self-hosting DAG** (`.cw9/dag.json`): gwt-0001..0035 + gwt-0046..0063 registered. **Gap at gwt-0036..0045** — context files exist but behaviors never registered in DAG/schema.
- **Crawl DAG** (`dag.json`): gwt-0001..0031 registered. No gaps.
- **Next available self-hosting ID: gwt-0064**
- **No seam-related GWTs registered in either DAG** — zero grep matches for "seam" in both DAGs and all `python/registry/*.py` files.

### crawl.db State

**Self-hosting `.cw9/crawl.db`**: Empty — 0 records, 0 deps, 0 ins.

**Root `crawl.db`** (CW9's own codebase crawl): Contains real data for seam analysis.

| Metric | Count |
|---|---|
| Total internal records | 1,567 |
| Skeletons (not extracted) | 1,409 |
| Fully extracted | 158 |
| Resolved dependency edges (`deps` view) | 39 |
| Total `internal_call` ins | 106 |
| Unresolved `internal_call` ins (`source_uuid IS NULL`) | 67 |

**Key finding**: 63% of internal_call edges are unresolved (67/106). This means `backfill_source_uuids()` has gaps — likely due to ambiguous function names or multi-file dispatch.

### Existing Type Mismatches Found

Querying the root `crawl.db` for cases where caller `ok` output type differs from callee input type reveals **18 concrete mismatches**:

| Caller | Provides | Callee | Expects |
|---|---|---|---|
| `extract_one()` | `FnRecord` | `_dfs_extract()` | `ExtractionResult \| None` |
| `_resolve_uuid_by_name()` | `str` | `_process_extraction_result()` | `str \| None` |
| `_resolve_uuid_by_name()` | `None` | `_process_extraction_result()` | `str \| None` |
| `_find_tla2tools()` | `str` | `run_tlc_simulate()` | `str \| Path` |
| `extract_module_name()` | `str` | `run_tlc_simulate()` | `str \| None` |
| `extract_module_name()` | `None` | `run_tlc_simulate()` | `str \| None` |
| `_find_tla2tools()` | `str` | `run_tlc()` | `str \| Path` |
| `_find_tla2tools()` | `str` | `compile_pluscal()` | `str \| Path` |
| `extract_module_name()` | `None` | `compile_compose_verify()` | `str` |
| `_parse_trace_file_format()` | `list[list[dict[str, Any]]]` | `parse_simulation_traces()` | `Callable[[str], list[list[dict[str, Any]]]]` |
| `_parse_trace_stdout_format()` | `list[list[dict[str, Any]]]` | `parse_simulation_traces()` | `Callable[[str], list[list[dict[str, Any]]]]` |
| `_build_llm_fn()` | `Callable[[str], str]` | `cmd_gwt_author()` | `Callable` |
| `render_card()` | `str` | `format_prompt_context()` | `Callable[[Any], str]` |
| `_get_engine_root()` | `Path` | `cmd_init()` | `Path \| None` |
| `_get_engine_root()` | `None` | `cmd_init()` | `Path \| None` |
| `_register_payload()` | `dict` | `cmd_pipeline()` | `dict \| None` |
| `_find_context_file()` | `Path` | `cmd_pipeline()` | `Path \| None` |
| `_find_context_file()` | `None` | `cmd_pipeline()` | `Path \| None` |

**Analysis of mismatches**: Most are benign (caller provides `str`, callee accepts `str | None` — narrower type satisfies wider union). But some are genuine red flags:
- `extract_one()` → `_dfs_extract()`: provides `FnRecord`, expects `ExtractionResult | None` — different type entirely
- `extract_module_name()` → `compile_compose_verify()`: can provide `None`, callee expects `str` (no union) — potential NoneType error
- `_parse_trace_*()` functions provide a return value but callee expects a `Callable` — the edge is modeling "function reference" not "call result"

This validates the plan: **seam checking on CW9's own codebase will produce real, actionable findings**.

---

## Key Functions (Implementation Targets)

### CrawlStore — `python/registry/crawl_store.py`

- **File**: `python/registry/crawl_store.py`
- **Total public methods**: 26
- **`deps` view**: Defined at line 136 — `SELECT DISTINCT dependent_uuid, dependency_uuid, dispatch, dispatch_candidates FROM ins WHERE source_uuid IS NOT NULL`
- **`ambiguous_dispatch` view**: Defined at line 150 — ins rows where `dispatch != 'direct'`, joined with records
- **Missing methods** (needed for seam checking):
  - `get_dependency_edges()` — no Python wrapper for `deps` view exists
  - `get_unresolved_internal_calls()` — no method returns raw unresolved `ins` rows
- **Existing relevant methods**:
  - `validate_completeness()` (line 577) — returns string descriptions of unresolved `internal_call` ins, but not structured data
  - `backfill_source_uuids()` (line 553) — resolves `source_function` → `source_uuid` FK; uses `LIMIT 1` subquery (ambiguity issue)
  - `get_forward_subgraph()` / `get_reverse_subgraph()` / `get_full_subgraph()` (lines 516–549) — recursive CTE traversal of dependency graph

### crawl_types.py — `python/registry/crawl_types.py`

- **File**: `python/registry/crawl_types.py`
- **SeamMismatch / SeamReport**: Do NOT exist. Must be created.
- **InField** (line 105): Pydantic BaseModel — `name`, `type_str`, `source` (InSource enum), `source_uuid`, `source_file`, `source_function`, `source_description`, `dispatch` (DispatchKind), `dispatch_candidates`
- **OutField** (line 126): Pydantic BaseModel — `name` (OutKind enum: ok/err/side_effect/mutation), `type_str`, `description`
- **FnRecord** (line 135): Pydantic BaseModel — `uuid`, `function_name`, `class_name`, `file_path`, `line_number`, `src_hash`, `is_external`, `ins: list[InField]`, `do_description`, `do_steps`, `do_branches`, `do_loops`, `do_errors`, `outs: list[OutField]`, `failure_modes`, `operational_claim`, `skeleton`, `schema_version`
- **DispatchKind** (line 49): `DIRECT`, `ATTRIBUTE`, `DYNAMIC`, `OVERRIDE`, `CALLBACK`, `PROTOCOL`
- **InSource** (line 34): `PARAMETER`, `STATE`, `LITERAL`, `INTERNAL_CALL`, `EXTERNAL`
- **OutKind** (line 42): `OK`, `ERR`, `SIDE_EFFECT`, `MUTATION`

### CLI — `python/registry/cli.py`

- **File**: `python/registry/cli.py`
- **`cmd_seams`**: Does NOT exist.
- **`_add_crawl_commands()`** (line 1838): Currently registers 5 subcommands: `ingest`, `crawl`, `stale`, `show`, `gwt-author`
- **`_DISPATCH` table** (line 1892): 15 entries total. No `seams` entry.
- **`cmd_stale` pattern** (line 1655): Standard crawl command structure — target resolution → `_require_cw9()` guard → crawl.db check → lazy import CrawlStore → context manager → logic → output → return code. This is the template for `cmd_seams`.

### seam_checker.py — Does NOT Exist

- **File**: `python/registry/seam_checker.py` — not created yet
- Zero "seam" references in any `.py` file in `python/registry/`

---

## Database Schema Detail

### `ins` table (line 55)

```sql
CREATE TABLE IF NOT EXISTS ins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type_str        TEXT NOT NULL,
    source          TEXT NOT NULL CHECK(source IN ('parameter','state','literal','internal_call','external')),
    source_uuid     TEXT REFERENCES records(uuid) ON DELETE SET NULL,
    source_file     TEXT,
    source_function TEXT,
    source_description TEXT,
    dispatch        TEXT NOT NULL DEFAULT 'direct'
                    CHECK(dispatch IN ('direct','attribute','dynamic','override','callback','protocol')),
    dispatch_candidates TEXT,
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);
```

### `outs` table (line 72)

```sql
CREATE TABLE IF NOT EXISTS outs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL CHECK(name IN ('ok','err','side_effect','mutation')),
    type_str        TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);
```

### `deps` view (line 136)

```sql
CREATE VIEW IF NOT EXISTS deps AS
SELECT DISTINCT
    i.record_uuid AS dependent_uuid,
    i.source_uuid AS dependency_uuid,
    i.dispatch,
    i.dispatch_candidates
FROM ins i
WHERE i.source_uuid IS NOT NULL;
```

---

## Findings

### 1. The data model is ready

The `ins` and `outs` tables already carry enough type information for seam checking. The `deps` view provides resolved edges. The `ambiguous_dispatch` view flags polymorphic call sites. No schema changes needed.

### 2. The gap is purely in code

Two missing Python methods on CrawlStore (`get_dependency_edges()`, `get_unresolved_internal_calls()`) and one missing module (`seam_checker.py`). The SQL infrastructure is complete.

### 3. Real mismatches exist in CW9's own codebase

18 type mismatches found across 39 resolved edges. At least 2 are genuine bugs (not just union widening):
- `extract_one()` → `_dfs_extract()`: `FnRecord` vs `ExtractionResult | None`
- `extract_module_name()` → `compile_compose_verify()`: `None` vs `str`

### 4. Unresolved edges are the larger problem

67 of 106 internal_call edges lack `source_uuid`. This means `backfill_source_uuids()` resolves only 37% of edges. The `cw9 seams` command must report these as "unresolved seams" rather than silently ignoring them.

### 5. Extraction coverage is low

Only 158/1567 records are fully extracted (10%). Most records are skeletons. Seam checking quality will improve dramatically as extraction coverage increases — skeleton records have no `ins`/`outs` data to compare.

### 6. All dispatch kinds are `direct`

All 39 resolved deps use `dispatch = 'direct'`. The `ambiguous_dispatch` view captures non-direct patterns but none have resolved `source_uuid` yet. Polymorphic dispatch (attribute, callback, protocol) is a known gap.

### 7. GWT IDs gwt-0064..0067 are available

The next 4 self-hosting IDs are free for the 4 seam-checking GWTs. No conflicts with existing allocations.

### 8. Gap at gwt-0036..0045

Context files exist for Batch 2 GWTs (ProjectContext, LLM Integration, CW7 Bridge, Crawl Bridge) but they were never registered in the DAG or schema. These IDs are allocated-but-empty in the DAG. This is a separate issue from seam checking but worth noting — those 10 GWTs should either be registered or the context files cleaned up.

---

## Proposed Changes (validated against current state)

### New types in `python/registry/crawl_types.py`

```python
@dataclass
class SeamMismatch:
    caller_uuid: str
    callee_uuid: str
    caller_function: str
    callee_function: str
    callee_input_name: str
    expected_type: str       # callee's InField.type_str
    provided_type: str       # best-match caller OutField.type_str
    dispatch: DispatchKind
    severity: str            # "type_mismatch" | "unresolved" | "no_ok_output"

@dataclass
class SeamReport:
    mismatches: list[SeamMismatch]
    unresolved: list[SeamMismatch]
    satisfied: int
    total_edges: int
```

### New CrawlStore methods in `python/registry/crawl_store.py`

```python
def get_dependency_edges(self) -> list[tuple[str, str, str, str | None]]:
    """All (dependent_uuid, dependency_uuid, dispatch, dispatch_candidates) from deps view."""
    # Query: SELECT * FROM deps

def get_unresolved_internal_calls(self) -> list[dict]:
    """ins with source='internal_call' and source_uuid IS NULL."""
    # Query: SELECT i.*, r.function_name FROM ins i JOIN records r ON i.record_uuid = r.uuid
    #        WHERE i.source = 'internal_call' AND i.source_uuid IS NULL
```

**Insertion point**: After `validate_completeness()` (line 577). These are read-only queries following the same pattern.

### New module: `python/registry/seam_checker.py`

| Function | Purpose |
|---|---|
| `check_seam(store, caller_uuid, callee_uuid)` | Compare one caller's outs against callee's ins where `ins.source_uuid == caller_uuid` |
| `check_all_seams(store)` | Query `deps` view, call `check_seam` per edge, collect unresolved ins |
| `type_compatible(provided, expected)` | String-level type compatibility (exact → normalized → structural) |
| `render_seam_report(report, verbose)` | Human-readable output |
| `seam_report_to_json(report)` | Machine-readable JSON output |

### CLI addition in `python/registry/cli.py`

- New `cmd_seams` function following `cmd_stale` pattern (line 1655)
- Registered in `_add_crawl_commands()` at line 1838
- Added to `_DISPATCH` table at line 1892

```
cw9 seams [target_dir] [--json] [--verbose] [--file <path>] [--function <name>]
```

### GWT Registration

4 GWTs at gwt-0064..0067:
1. `seam_mismatch_detected` (gwt-0064)
2. `seam_satisfied_no_report` (gwt-0065)
3. `seam_unresolved_flagged` (gwt-0066)
4. `seam_report_complete` (gwt-0067)

---

## Type Compatibility Design

The `type_compatible(provided, expected)` function models compatibility as a **partial order** with 3 tiers:

1. **Exact match**: `"list[FnRecord]"` == `"list[FnRecord]"` → compatible
2. **Normalized match**: case-insensitive + alias resolution (`Dict` = `dict`, `List` = `list`, `Optional[X]` = `X | None`) → compatible
3. **Structural subtype**: `Any` satisfies anything; `str` satisfies `str | None` (narrower satisfies wider union) → compatible

Real examples from CW9's crawl.db:
- `str` → `str | Path`: compatible (tier 3, narrower satisfies union)
- `str` → `str | None`: compatible (tier 3)
- `None` → `str`: **incompatible** — genuine mismatch
- `FnRecord` → `ExtractionResult | None`: **incompatible** — different type entirely
- `Callable[[str], str]` → `Callable`: compatible (tier 3, specific satisfies generic)

---

## Risks (updated)

- **Type string fuzziness**: LLM-extracted `type_str` values aren't normalized. The 18 mismatches found include both genuine bugs and false positives from union representation differences. Start with conservative 3-tier matching, iterate.
- **source_uuid resolution gaps**: 63% of internal_call edges are unresolved. The unresolved bucket will dominate initial reports. Consider running `backfill_source_uuids()` as a pre-step in `cw9 seams`.
- **Low extraction coverage**: Only 10% of records are fully extracted. Seam reports will be sparse until more crawl extraction is done. Consider suggesting `cw9 crawl --incremental` when skeleton ratio is high.
- **Multiple outs per function**: Functions have ok, err, side_effect, mutation outputs. Initial impl matches callee ins against caller's `ok` outs only; err-path matching is future work.
- **Callable/function-reference edges**: Some "type mismatches" are actually function-reference edges where the callee receives a callable, not a call result. The `_parse_trace_*` → `parse_simulation_traces` examples show this pattern. May need a heuristic to detect callback/reference edges.

---

## Verification Plan

1. `cw9 register` succeeds — GWTs allocated IDs gwt-0064..0067
2. `cw9 loop` per GWT — TLC verified, 0 violations
3. `cw9 bridge` + `cw9 gen-tests` — tests generated
4. `python3 -m pytest python/tests/ -x` — all tests pass (existing + generated)
5. `cw9 seams .` against CW9's own root `crawl.db` — produces meaningful seam report
6. Spot-check: at least 2 type mismatches flagged (from the 18 known), at least 67 unresolved seams reported

---

## CW9 Mention Summary

Functions: check_seam(), check_all_seams(), type_compatible(), render_seam_report(), seam_report_to_json(), get_dependency_edges(), get_unresolved_internal_calls(), validate_completeness(), backfill_source_uuids(), cmd_seams(), cmd_stale(), _add_crawl_commands(), render_card()
Files: python/registry/crawl_types.py, python/registry/crawl_store.py, python/registry/cli.py, python/registry/seam_checker.py, schema/self_hosting.json
Directories: python/registry/, python/tests/generated/

Note: The "CW9 Mention Summary" section is formatted for gwt-author extraction.
Function names MUST include () for mention extraction.
