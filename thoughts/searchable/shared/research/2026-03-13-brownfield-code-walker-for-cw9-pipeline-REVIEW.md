---
title: "Plan Review: Brownfield Code Walker for CW9 Pipeline"
date: 2026-03-13
tags: [review, brownfield, code-walker, in-do-out, pipeline]
status: resolved
reviewed_plan: thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md
resolution: All issues addressed in plan update on 2026-03-13. Plan status changed to "reviewed".
---

# Plan Review Report: Brownfield Code Walker for CW9 Pipeline

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 5 issues |
| Interfaces | ⚠️ | 4 issues |
| Promises | ❌ | 6 issues |
| Data Models | ⚠️ | 5 issues |
| APIs | ⚠️ | 4 issues |

---

## Contract Review

### Well-Defined:

- ✅ **IN:DO:OUT schema** — Clear input/output specification with `InSource`, `OutKind`, `DispatchKind` enums and full `FnRecord`/`AxRecord`/`MapNote` models
- ✅ **SQLite schema** — Thorough DDL with foreign keys, check constraints, indexes, and views. Staleness CTE is well-specified
- ✅ **Skeleton output contract** — `Skeleton` model clearly defines pre-pass output (name, params, return type, line number, file hash)
- ✅ **Entry point detection** — `EntryPoint` model with `EntryType` enum, per-codebase-type detection heuristics table
- ✅ **dag.json ↔ crawl.db bridge** — Post-crawl step clearly specifies: records → RESOURCE nodes, deps → CALLS edges, entry_points → HANDLES/IMPORTS edges
- ✅ **Test isolation** — `TestReference` model clearly separates test data from production crawl data

### Missing or Unclear:

- ❌ **crawl.db ↔ dag.json sync contract** — The plan specifies a post-crawl bridge step (§"Connection to dag.json") but does not define what happens on **incremental re-ingest**. When a function is re-extracted (stale hash), do we: (a) delete and recreate the corresponding dag.json RESOURCE node, (b) update it in place, or (c) leave dag.json untouched and rely on UUID lookup into crawl.db? If (a), existing GWT→RESOURCE edges in dag.json may break. If (b), the `RegistryDag` has no `update_node()` method — only `add_node()` which will raise `DuplicateNodeError` (dag.py:37-41). If (c), dag.json accumulates stale data.

- ⚠️ **Error contract for LLM extraction failures** — What happens when the LLM produces invalid IN:DO:OUT for a function? The plan says "Pydantic validates the output" but doesn't specify: How many retries? What error is recorded if all retries fail? Is a partial record stored? Is the function skipped and its dependents left with broken `source_uuid` references? This is the most common failure mode in practice.

- ⚠️ **UUID generation strategy** — `FnRecord.uuid` is validated as a UUID but the generation strategy is unspecified. Options: (a) `uuid4()` — random, loses identity across re-ingests; (b) deterministic from `(file_path, function_name)` — stable across re-ingests but collides on function renames; (c) deterministic from `(file_path, function_name, src_hash)` — changes on every code edit. CW8.1 used `RR_UUID` with a prefix (`rr-`) — the plan should specify which approach and why.

- ⚠️ **Pydantic vs dataclass contract** — The plan proposes Pydantic `BaseModel` subclasses with `field_validator` decorators (lines 1051-1063), but the **entire existing codebase uses only `@dataclass`** — zero Pydantic models exist. This is a fundamental architectural decision that affects: dependency footprint (Pydantic is not currently a dependency), validation patterns, serialization approach, and developer mental model. The plan should explicitly justify introducing Pydantic or adapt to use dataclasses.

- ⚠️ **`ContextBundle.cards` field contract** — The plan proposes adding `cards: list[FnRecord]` to `ContextBundle` (line 976) and says `query_context()` should look up crawl.db by UUID. But `format_prompt_context()` already silently drops `bundle.schemas` (populated but never rendered in the prompt). The rendering contract for `cards` is unspecified: what format? How verbose? What fields from `FnRecord` are included vs omitted?

### Recommendations:

1. Specify incremental re-ingest sync behavior explicitly: recommend deterministic UUIDs from `(file_path, function_name)` with an `update_or_replace` method on `RegistryDag`
2. Add a "Crawl Error Handling" section specifying retry count, partial-record policy, and how broken `source_uuid` references are handled
3. Decide Pydantic vs dataclass upfront and document the rationale
4. Specify the `format_prompt_context()` additions for card rendering

---

## Interface Review

### Well-Defined:

- ✅ **CLI interface** — `cw9 ingest`, `cw9 stale`, `cw9 show --card` follow existing argparse patterns exactly (positional `target_dir`, `--lang` choices, `--entry` path, `--incremental` flag)
- ✅ **SQLite views** — `deps`, `stale_candidates`, `ambiguous_dispatch`, `test_coverage` views provide clean query interfaces
- ✅ **Per-language scanner interface** — All scanners share the `Skeleton` output model but have independent implementations (~100-200 lines each)
- ✅ **GWT authoring interface** — `cw9 gwt-author --research=<path>` with JSON output suitable for `cw9 register`

### Missing or Unclear:

- ❌ **`Node` dataclass has no `metadata` field** — The plan's "IN:DO:OUT Schema for CW9" section (lines 297-348) proposes storing IN:DO:OUT as `metadata: {...}` on RESOURCE nodes in dag.json. But `Node` (types.py:44-87) has these fields: `id`, `kind`, `name`, `description`, `schema`, `path`, `source_schema`, `source_key`, `version`, `given`, `when`, `then`, `text`. There is no `metadata` dict. Either: (a) the plan should add a `metadata: dict | None` field to `Node`, or (b) the plan should clarify that this metadata schema is for crawl.db only and dag.json RESOURCE nodes carry only `(id, kind, name, description)` — which is what the "Connection to dag.json" section (line 960-967) actually says. These two sections contradict each other.

- ⚠️ **`RegistryDag` mutation interface gap** — The plan requires updating dag.json nodes on re-ingest, but `RegistryDag` has no `update_node()` or `remove_node()` method. `add_node()` (dag.py:36-41) raises an error if the node already exists. The plan should specify whether to: (a) add `update_node()` and `remove_node()` to `RegistryDag`, (b) use `merge_registered_nodes()` (which only handles `gwt-`/`req-` prefixes), or (c) rebuild dag.json from scratch on every ingest.

- ⚠️ **Crawl store Python interface** — The SQLite schema is well-specified but the Python API for interacting with `crawl.db` is not. The plan needs a `CrawlStore` class (or equivalent) interface definition: `insert_record(FnRecord)`, `get_record(uuid)`, `mark_stale(uuids)`, `get_stale()`, `get_subgraph(function_name)`, etc. Without this, implementers must infer the interface from raw SQL.

- ⚠️ **Scanner interface contract** — Each scanner is described as "~100-200 lines" but the actual interface is implicit. Should be explicit: `def scan(file_path: str) -> list[Skeleton]` or `def scan_directory(dir_path: str) -> list[Skeleton]`? Does the scanner handle one file at a time or walk a directory? Does it need file filtering (skip `__pycache__`, `node_modules`, `.git`)? What about encoding detection (UTF-8 vs Latin-1)?

### Recommendations:

1. Resolve the metadata contradiction: remove the IN:DO:OUT-in-dag.json section (lines 297-348) since the "Connection to dag.json" section (lines 960-967) correctly says dag.json carries only graph structure
2. Design `CrawlStore` Python API before implementation — use the same `@dataclass` pattern as existing code
3. Define explicit scanner interface: `scan_file(path: Path) -> list[Skeleton]` + `scan_directory(root: Path, excludes: list[str]) -> list[Skeleton]`
4. Either add `upsert_node()` to `RegistryDag` or specify the rebuild approach

---

## Promise Review

### Well-Defined:

- ✅ **Staleness propagation** — Clear guarantee: if a file hash changes, all transitive dependents are marked stale via recursive CTE. `query_impact()` already provides the reverse traversal.
- ✅ **DFS cycle safety** — "DFS with visited set (cycle-safe)" specified. Cycles in call graphs (mutual recursion) won't cause infinite traversal.
- ✅ **Incremental crawl** — Clear promise: `--incremental` only re-extracts stale functions, skipping up-to-date ones.

### Missing or Unclear:

- ❌ **LLM failure/retry strategy** — The plan specifies no retry count, backoff, or failure policy for per-function LLM extraction. In practice, LLMs produce invalid output ~5-15% of the time for structured extraction tasks. Without a retry strategy, a 500-function crawl will have 25-75 failures. Specify: max retries per function (3?), exponential backoff, what to record on exhausted retries (skip the function? store a skeleton-only record?).

- ❌ **Crawl resumability** — No promise about interrupted crawls. If `cw9 ingest` is killed mid-crawl (Ctrl+C, OOM, timeout), what state is the database in? Are completed records preserved? Is the crawl_runs record left with `completed_at = NULL`? Can `cw9 ingest --incremental` resume from where it stopped? Since SQLite with WAL mode provides ACID guarantees per-transaction, the answer is "yes if records are committed per-function" — but this needs to be stated as a design decision.

- ❌ **Resource bounds** — No specification of memory or time bounds. A large codebase (10,000 functions) with DFS traversal + LLM calls per function could take hours and consume significant API budget. The plan should specify: expected cost per function (tokens in/out), estimated total for a reference codebase size, and whether there's a max-functions limit or cost cap.

- ⚠️ **File hash granularity** — The plan says `src_hash` is a "SHA-256 of source file" but functions are tracked per-function. If two functions live in the same file and one changes, both get marked stale even if only one's body changed. CW8.1 had the same limitation. This is acceptable but should be acknowledged as a design trade-off, since the alternative (per-function-body hashing) requires accurate function body extraction, which depends on the scanner working correctly.

- ⚠️ **Ordering guarantee for DFS** — The DFS traversal order affects which functions get extracted first and whether `source_uuid` references can be resolved eagerly. If function A calls function B, and we visit A first, A's `InField` for the call to B won't have a `source_uuid` yet (B hasn't been extracted). The plan should specify: are `source_uuid` references back-filled after the crawl completes, or are they left as `None` with `source_function` as the lookup key?

- ⚠️ **Concurrency** — No mention of whether the DFS crawl can be parallelized (multiple LLM calls in flight for independent subtrees). The plan implies sequential execution but doesn't state this explicitly. For large codebases, parallelism could reduce crawl time 5-10x.

### Recommendations:

1. Add "Crawl Error & Retry Policy" section: 3 retries per function, exponential backoff, skeleton-only record on exhaustion, `crawl_runs.records_failed` counter
2. State "records are committed per-function, crawl is resumable after interruption" as an explicit design decision
3. Add resource estimation: ~2K tokens in + ~1K tokens out per function, ~$0.01-0.03 per function, ~$5-15 for a 500-function codebase
4. Specify `source_uuid` back-fill pass after DFS completion
5. Acknowledge file-level hash granularity trade-off
6. Consider a `--max-functions` flag for cost control

---

## Data Model Review

### Well-Defined:

- ✅ **SQLite schema** — Complete DDL with all tables, columns, types, constraints, foreign keys, indexes, and views. Schema version tracking via `schema_version` column. WAL mode specified.
- ✅ **Pydantic/dataclass models** — `FnRecord`, `AxRecord`, `MapNote`, `EntryPoint`, `TestReference`, `Skeleton` are fully specified with all fields and types
- ✅ **Enum definitions** — `InSource`, `OutKind`, `DispatchKind`, `EntryType` are exhaustive and well-justified
- ✅ **Edge types** — CALLS, DEPENDS_ON, IMPORTS are already defined in `EdgeType` enum (types.py:20-41). No new edge types needed.

### Missing or Unclear:

- ❌ **Pydantic dependency** — The codebase has zero Pydantic usage. `pyproject.toml` does not list Pydantic as a dependency. Introducing it adds: (a) a new dependency (`pydantic>=2.0` plus `pydantic-core`), (b) a different validation paradigm, (c) different serialization (`.model_dump()` vs `dataclasses.asdict()`). The plan should either: justify Pydantic (validation is genuinely needed for LLM output), or convert all models to `@dataclass` with manual validation functions (matching existing patterns).

  **My recommendation**: Use Pydantic for `FnRecord` and LLM-facing models only (they genuinely need validation of LLM output). Keep everything else as `@dataclass`. This creates a clean boundary: Pydantic at the LLM extraction boundary, dataclasses everywhere else.

- ⚠️ **`InField.source_file` validator** — The `internal_call_needs_source` validator (line 1058-1063) requires `source_file` for `internal_call` sources, but during DFS traversal, when we first encounter a call to an un-visited function, we may know `source_function` (from the call site text) but not `source_file` (we haven't found it yet). The validator should allow `source_file=None` during the extraction phase and enforce it only after the back-fill pass.

- ⚠️ **`records` table UNIQUE constraint** — `UNIQUE(file_path, function_name)` (line 752 of the plan) will fail for overloaded/same-name functions in different scopes (e.g., two classes in the same file both having a `__init__` method, or nested functions with the same name). Python allows this commonly. The constraint should be `UNIQUE(file_path, function_name, line_number)` or use a qualified name (`ClassName.method_name`).

- ⚠️ **`outs.name` CHECK constraint** — `CHECK(name IN ('ok','err','side_effect','mutation'))` matches `OutKind` enum values. But the Pydantic model defines `name: OutKind` while the SQL column is just `TEXT`. If the enum values ever change, the CHECK constraint becomes a silent data integrity issue. Consider: either remove the CHECK (rely on application-level validation) or add a `schema_version` gate.

- ⚠️ **Missing `records.class_name` column** — Functions in Python/TypeScript/Go can be methods on classes/structs. The plan mentions qualified names ("function_name @ file_path") but doesn't store the class/struct name separately. This matters for: dispatch resolution (`self.repo.save` → need to know `repo`'s class), method vs function distinction, and the UNIQUE constraint issue above. Adding `class_name TEXT` (nullable, NULL for top-level functions) solves multiple problems.

### Recommendations:

1. Add Pydantic as an optional dependency, used only for LLM-boundary models (`FnRecord`, `InField`, `OutField`)
2. Relax `internal_call_needs_source` validator to allow `source_file=None` initially
3. Change UNIQUE constraint to `UNIQUE(file_path, function_name, line_number)` or add `class_name` column and use `UNIQUE(file_path, class_name, function_name)`
4. Add `class_name TEXT` column to `records` table
5. Document the Pydantic vs dataclass boundary explicitly

---

## API Review

### Well-Defined:

- ✅ **`cw9 ingest` CLI** — Clear invocation: `cw9 ingest <path> [--lang=...] [--entry=...] [--incremental] [--with-tests]`
- ✅ **`cw9 stale` CLI** — Output: list of stale nodes
- ✅ **`cw9 show <node-id> --card`** — Card rendering from crawl.db
- ✅ **`cw9 gwt-author --research=<path>`** — JSON output for `cw9 register`
- ✅ **SQL query API** — Staleness CTE, subgraph extraction CTE, card rendering query all specified

### Missing or Unclear:

- ⚠️ **`cw9 ingest` output format** — What does the command print? A summary table? JSON? The plan should specify output for: (a) normal completion (records created/updated/skipped counts), (b) partial failure (which functions failed), (c) `--incremental` with nothing stale.

- ⚠️ **`cw9 pipeline` integration** — The plan shows `cw9 ingest` as a standalone command but doesn't specify how it integrates with the existing `cw9 pipeline` orchestration flow. Should `cmd_pipeline` call `cmd_ingest` in Phase 0 alongside `cmd_init` and `cmd_extract`? Or is ingest always manual? If manual, how does the pipeline know whether to use crawl.db context or schema-derived context?

- ⚠️ **`cw9 gwt-author` → `cw9 register` pipe** — The plan says `gwt-author` produces JSON "suitable for `cw9 register`" but doesn't specify whether the output is: (a) piped to stdin (`cw9 gwt-author | cw9 register`), (b) written to a file, or (c) directly invoked by `gwt-author`. Existing `cmd_register` reads from stdin (test_register.py shows `monkeypatch.setattr("sys.stdin", ...)`), so (a) would work — but the JSON schema of the output should match `cmd_register`'s expected input format, which the plan doesn't cross-reference.

- ⚠️ **`--lang` auto-detection vs flag** — The plan specifies entry point auto-detection based on framework detection (checking `requirements.txt`, `package.json`, `go.mod`), but `--lang` is a separate argument. What happens if `--lang=python` is passed but `go.mod` is found? Does auto-detection override the flag? Does the flag override auto-detection? The plan should state: `--lang` is authoritative when provided; auto-detection is the fallback.

### Recommendations:

1. Specify `cw9 ingest` output format: human-readable summary with `--json` flag for machine output
2. Clarify: `cw9 ingest` is standalone (not part of `cw9 pipeline`), and `query_context()` auto-detects crawl.db presence to include cards
3. Specify: `cw9 gwt-author` writes JSON to stdout, pipe to `cw9 register` via stdin
4. State: `--lang` overrides auto-detection when provided

---

## Critical Issues (Must Address Before Implementation)

### 1. **Node metadata contradiction** (Interface)

The plan has two conflicting specifications for how IN:DO:OUT data lives in dag.json:
- Section "IN:DO:OUT Schema for CW9" (lines 297-348) proposes a `metadata: {...}` dict on RESOURCE nodes
- Section "Connection to dag.json" (lines 960-967) says dag.json carries "only the graph structure" and full cards are in SQLite

The `Node` dataclass has no `metadata` field. These two sections must be reconciled.

**Impact:** Implementers will build the wrong bridge, either bloating dag.json or missing the metadata field.

**Recommendation:** Remove lines 297-348 (the metadata schema). The SQLite-only approach in lines 960-967 is correct and consistent with the dual-store decision.

### 2. **Pydantic vs dataclass decision** (Data Model)

Introducing Pydantic into a zero-Pydantic codebase is a consequential architectural decision that affects dependency management, developer onboarding, and code consistency.

**Impact:** If unresolved, implementers will either introduce Pydantic without discussion (creating inconsistency) or convert to dataclasses ad-hoc (losing validation benefits).

**Recommendation:** Use Pydantic for LLM-boundary validation only (`FnRecord`, `InField`, `OutField`). All other models (`Skeleton`, `EntryPoint`, `MapNote`, `TestReference`) should be `@dataclass` to match existing patterns. Add `pydantic>=2.0` as a dependency gated behind `[crawl]` extras.

### 3. **No LLM failure/retry specification** (Promise)

The plan's core value proposition depends on reliable per-function LLM extraction, but specifies no error handling.

**Impact:** A 500-function crawl will have 25-75 extraction failures with no recovery strategy, leaving the crawl DB in an inconsistent state (missing records, broken source_uuid references).

**Recommendation:** Add a dedicated "Crawl Error Handling" section specifying: 3 retries with exponential backoff, skeleton-only stub record on exhaustion, `source_uuid` back-fill pass after full crawl, `crawl_runs.records_failed` counter.

### 4. **`RegistryDag` has no update/remove node API** (Interface)

Incremental re-ingest needs to update existing RESOURCE nodes in dag.json, but `RegistryDag` only supports `add_node()` (raises on duplicate).

**Impact:** Incremental ingest will crash on the dag.json bridge step for any previously-ingested function.

**Recommendation:** Add `upsert_node(node: Node)` to `RegistryDag` that replaces an existing node with the same ID, preserving existing edges. This is a small, safe change (~10 lines).

---

## Suggested Plan Amendments

```diff
# In Section "IN:DO:OUT Schema for CW9" (lines 297-348):

- Remove the entire metadata-in-dag.json schema
+ Replace with: "The IN:DO:OUT detail lives exclusively in crawl.db.
+  dag.json RESOURCE nodes carry only: id, kind=RESOURCE,
+  name='function_name @ file_path', description=operational_claim."

# In Section "Updated Pydantic Models" (lines 982-1139):

- class FnRecord(BaseModel):
+ class FnRecord(BaseModel):  # Pydantic — validates LLM output
+     """NOTE: This is one of the few Pydantic models in CW9.
+     Most types use @dataclass. Pydantic is used here because
+     FnRecord is populated from LLM output that needs validation."""

- class Skeleton(BaseModel):
+ @dataclass
+ class Skeleton:  # Standard dataclass — deterministic scanner output

- class EntryPoint(BaseModel):
+ @dataclass
+ class EntryPoint:  # Standard dataclass — deterministic detection output

- class MapNote(BaseModel):
+ @dataclass
+ class MapNote:  # Standard dataclass — deterministic computation

- class TestReference(BaseModel):
+ @dataclass
+ class TestReference:  # Standard dataclass — deterministic extraction

# In Section "Three-Phase Pipeline" (lines 212-235):

+ Add new subsection "Crawl Error Handling":
+ - Max 3 retries per function with exponential backoff (1s, 4s, 16s)
+ - On exhausted retries: store skeleton-only record with
+   do_description="EXTRACTION_FAILED", empty ins/outs
+ - After full DFS: source_uuid back-fill pass resolves
+   source_function → source_uuid using records table lookup
+ - crawl_runs tracks: records_created, records_updated,
+   records_skipped, records_failed (new counter)

# In Section "Storage Decision" (line 358):

+ Add subsection "Incremental Re-ingest Sync Protocol":
+ 1. UUID generation: deterministic uuid5(NAMESPACE_URL, f"{file_path}::{function_name}")
+    - Stable across re-ingests for unchanged function names
+    - Handles renames via delete-old + create-new
+ 2. crawl.db: UPSERT (INSERT OR REPLACE) per function
+ 3. dag.json: RegistryDag.upsert_node() — new method, replaces
+    node with same ID, preserves edges
+ 4. Deleted functions: detected by comparing scan results
+    against existing records; orphan nodes removed from both stores

# In records table schema (line 752):

- UNIQUE(file_path, function_name)
+ class_name      TEXT,                    -- NULL for top-level functions
+ UNIQUE(file_path, COALESCE(class_name, ''), function_name)

# Add new section "CrawlStore Python API":

+ class CrawlStore:
+     def __init__(self, db_path: Path): ...
+     def insert_record(self, record: FnRecord) -> None: ...
+     def upsert_record(self, record: FnRecord) -> None: ...
+     def get_record(self, uuid: str) -> FnRecord | None: ...
+     def get_records_for_file(self, file_path: str) -> list[FnRecord]: ...
+     def get_stale_records(self, current_hashes: dict[str, str]) -> list[str]: ...
+     def get_transitive_stale(self, direct_stale: list[str]) -> list[str]: ...
+     def get_subgraph(self, function_name: str) -> list[FnRecord]: ...
+     def get_card_text(self, uuid: str) -> str: ...
+     def record_crawl_run(self, ...) -> int: ...
```

---

## Review Checklist

### Contracts
- [x] Component boundaries are clearly defined (crawl.db vs dag.json)
- [ ] Input/output contracts are specified (LLM extraction failure case missing)
- [x] Error contracts enumerate all failure modes (SQLite schema is thorough)
- [ ] Preconditions and postconditions are documented (incremental sync preconditions missing)
- [x] Invariants are identified (staleness propagation, cycle safety)

### Interfaces
- [x] All public methods are defined with signatures (CLI is complete)
- [x] Naming follows codebase conventions (argparse, cmd_* pattern)
- [ ] Interface matches existing patterns (Pydantic vs dataclass mismatch)
- [ ] Extension points are considered (no CrawlStore API specified)
- [x] Visibility modifiers are appropriate (N/A for Python)

### Promises
- [x] Behavioral guarantees are documented (staleness, DFS cycle safety)
- [ ] Async operations have timeout/cancellation handling (LLM calls unspecified)
- [ ] Resource cleanup is specified (interrupted crawl behavior unspecified)
- [ ] Idempotency requirements are addressed (incremental sync not fully specified)
- [ ] Ordering guarantees are documented where needed (source_uuid back-fill timing)

### Data Models
- [x] All fields have types (complete for all models)
- [x] Required vs optional is clear (defaults specified)
- [x] Relationships are documented (foreign keys in SQL, UUIDs in models)
- [ ] Migration strategy is defined (schema_version column exists but no migration logic)
- [x] Serialization format is specified (JSON for Pydantic, SQL for storage)

### APIs
- [x] All endpoints are defined (CLI commands complete)
- [ ] Request/response formats are specified (output format unspecified)
- [x] Error responses are documented (partially — CLI exit codes implied)
- [x] Authentication requirements are clear (N/A — local tool)
- [ ] Versioning strategy is defined (schema_version column but no migration)

---

## Approval Status

- [ ] **Ready for Implementation** — No critical issues
- [x] **Needs Minor Revision** — Address 4 critical issues before proceeding
- [ ] **Needs Major Revision** — Critical issues must be resolved first

**Assessment:** The plan is architecturally sound and well-researched. The CW8.1 prior art provides strong foundations. The four critical issues are all resolvable with targeted amendments (estimated 1-2 hours of plan revision). The most impactful change is specifying the LLM error handling strategy — this is the highest-risk area in practice. The Pydantic vs dataclass decision should be made explicitly rather than discovered during implementation. After these amendments, the plan is ready for Phase 1 (Python skeleton scanner + SQLite store) implementation.
