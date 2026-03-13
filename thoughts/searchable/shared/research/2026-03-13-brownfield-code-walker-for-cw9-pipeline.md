---
title: "Brownfield Code Walker for CW9 Pipeline"
date: 2026-03-13
tags: [brownfield, code-walker, in-do-out, resource-registry, pipeline, plan]
status: reviewed
review: thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline-REVIEW.md
review_date: 2026-03-13
---

# Brownfield Code Walker for CW9 Pipeline

## Problem Statement

The current brownfield workflow for adding features to an existing external codebase is:

```
research_codebase skill (~65% context consumed by MCP servers + skill overhead)
    -> manual TDD plan (with remaining ~35% context)
    -> code generation (debugging surprises from missed far-reaching effects)
```

The bottleneck is that `research_codebase` tries to discover **and** hold the entire relevant slice of a foreign codebase in a single LLM context window. As codebase complexity grows, the LLM misses far-reaching effects — not because it's incapable, but because the relevant code simply doesn't fit. This manifests as:

1. **Debugging in spite of TDD** — the TDD plan was generated from incomplete context, so tests pass but integration breaks
2. **Multiple research runs** — expanding research risks hallucinations and unnecessary scope creep
3. **Multiple TDD/review runs** — inefficient, each run re-discovers what the previous missed

The core insight: **the LLM is doing grunt-work (tracing call chains, mapping dependencies) that should be done deterministically and stored persistently, so the LLM can focus on what it's actually good at — behavioral specification and code generation.**

## Prior Art: CW8.1 Brownfield Crawl

CW8.1 designed and partially implemented exactly this capability. The full spec lives at:

- **Primary spec**: `~/Dev/CodeWriter8.1/specs/brownfield/brownfield-tlaplus-crawl.md`
- **Path docs**: `~/Dev/CodeWriter8.1/paths/brownfield-crawl-*` (6+ paths)
- **DFS traversal paths**: `~/Dev/CodeWriter8.1/paths/depth-first-provenance-*`

### CW8.1 Architecture (What Worked)

The brownfield pipeline **inverted** the greenfield pipeline:

```
Greenfield:   spec -> path -> verify -> plan -> implement -> code
Brownfield:   code -> crawl -> FN cards -> MAP -> synthesize -> path -> verify
                                                                  ^
                                                        same verify-path gate
```

**Three knowledge objects:**

1. **FN Cards** (Behavior Cards) — one per internal function, containing:
   - `RR_UUID`: permanent identity
   - `IN:` — every input with provenance (`parameter`, `state`, `literal`, `internal_call`, `external`)
   - `DO:` — step-by-step description of what the function does (line-by-line, no inference)
   - `OUT:` — every output (`ok`, `err`, `side_effect`, `mutation`)
   - `FAILURE_MODES:` — explicit list of what can go wrong
   - `DEPS:` — UUIDs of functions this one depends on
   - `OPERATIONAL_CLAIM:` — 1-2 sentence correctness condition

2. **AX Cards** (Axiom Cards) — one per external dependency boundary, with `DO: "Assume crate behavior per documented contract"`. Terminal nodes — never traversed.

3. **MAP Notes** — workflow structure linking FN cards into end-to-end paths. Persists the architectural partitioning so the LLM doesn't rediscover it each time.

**Three-phase execution:**

- **Pre-pass**: Lightweight skeleton extraction (function signatures only — name, params, return type, line number, file hash). No body analysis. Provides ground truth to the LLM so it can't hallucinate signatures.
- **Pass 1**: Depth-first provenance crawl. For each function, the LLM reads the body line-by-line and produces IN:DO:OUT. Results validated through strict Pydantic models, stored in SQLite (source of truth), with markdown cards as generated views.
- **Pass 2**: Behavior graph -> TLA+ path specs via multi-turn LLM session. MAP notes define the workflow partitioning; FN cards provide the behavioral content.

**Storage**: SQLite is the source of truth (tables: `records`, `ins`, `outs`, `maps`, plus `deps` and `stale_records` views). Markdown cards are read-only projections — re-generable from DB at any time.

**Staleness detection**: SHA-256 file hash (`SRC_HASH`) per function + recursive CTE for transitive staleness propagation through the dependency graph.

### CW8.1 Data Structures

```python
# Core Pydantic models from CW8.1
class InSource(str, Enum):
    PARAMETER = "parameter"      # function parameter
    STATE = "state"              # read from self/state
    LITERAL = "literal"          # hardcoded value
    INTERNAL_CALL = "internal_call"  # returned by another function
    EXTERNAL = "external"        # from external crate/package

class OutKind(str, Enum):
    OK = "ok"                    # normal return
    ERR = "err"                  # error return
    SIDE_EFFECT = "side_effect"  # I/O, messages, etc.
    MUTATION = "mutation"        # state mutation

class InField(BaseModel):
    name: str
    type_str: str
    source: InSource
    source_uuid: str | None       # UUID of the source function
    source_file: str | None       # file path of the source
    source_function: str | None   # name of the source function
    source_description: str | None

class OutField(BaseModel):
    name: OutKind
    type_str: str
    description: str

class FnRecord(BaseModel):
    uuid: str
    function_name: str
    file_path: str
    line_number: int | None
    src_hash: str
    is_external: bool
    ins: list[InField]
    do_description: str
    do_steps: list[str]
    do_branches: str | None
    do_loops: str | None
    do_errors: str | None
    outs: list[OutField]
    failure_modes: list[str]
    operational_claim: str
    skeleton: Skeleton | None
```

### CW8.1 Rust Infrastructure

CW8.1 also had Rust-side structures for the dependency graph:

```rust
// auxiliary_types.rs
pub struct DependencyEdge {
    pub from_node_id: String,
    pub to_node_id: String,
    pub edge_type: String,  // "requires", "contains-by-value", "resource-type-ref"
}

pub struct DependencyGraph {
    pub nodes: Vec<String>,
    pub edges: Vec<DependencyEdge>,
}
```

The `SchemaStore::dependency_graph()` method computed three kinds of edges: interface `requires` relationships, struct field containment (`contains-by-value`), and resource linkage edges. Cycle detection used Kahn's algorithm in `validator.rs`.

The `parse_source_code()` function at `codegen/parse_source_code.rs` did **line-by-line text scanning** — not AST-based. It used brace-depth counting, string matching for `pub struct`, `pub fn`, `pub trait`, `impl`, and manual parameter splitting. This was intentionally low-level and robust — it didn't need a full parser, just structural landmarks.

## Why Not AST / Tree-Sitter

The user's experience and my research confirm: AST parsers and tree-sitter **choke on real-world code**. Specific failure modes:

1. **Tree-sitter**: Chokes on relatively small files. Parse failures on valid code. Grammar maintenance burden per language.
2. **AST (`ast` module in Python, `syn` in Rust)**: Gives you a syntax tree but not behavioral semantics. You get "this function takes X and returns Y" but not "this function reads from the database, transforms the result, and writes to a cache." The abstraction is too mathematical — it models syntax, not behavior.
3. **Both approaches miss what matters**: A developer hand-walking code traces **data flow**, not syntax. They follow the value of `user_id` from the HTTP handler through the service layer into the database query and back. AST gives you the tree; you need the **path through the tree that data actually travels**.

CW8.1 got this right: `parse_source_code()` was a line-by-line scanner, and the actual behavioral extraction was done by the LLM reading the function body with ground-truth skeleton context. The skeleton (via `syn`) was used **only** for the function header — params, return type, line number — not for understanding what the function does.

### The Developer's Actual Process

When a developer hand-walks code to understand it, they:

1. **Start at an entry point** (HTTP handler, CLI command, event listener)
2. **Read line by line**, not jumping to definitions unless a call is made
3. **Follow every call site** — "this calls `validate(input)`, let me go read `validate`"
4. **Track data flow** — "the return value of `validate` gets passed to `process`, so `process.input` comes from `validate.output`"
5. **Note branches** — "if validation fails, we return early; if it passes, we continue to step 3"
6. **Note loops** — "this iterates over `items`, calling `transform` on each"
7. **Note side effects** — "this writes to the database here, sends an event there"
8. **Draw diagrams** — connecting all the call sites, data flows, and branches into a complete picture
9. **Mark boundaries** — "this calls `redis.get()`, that's external, I trust the contract"

This is **exactly** what the IN:DO:OUT crawl does. It's not fancy math — it's automating the grunt-work of tracing every path, recording every connection, and building the complete picture so the developer (or LLM) doesn't have to hold it all in their head.

## Mapping CW8.1 Concepts to CW9

### What CW9 Already Has

CW9's `RegistryDag` (`python/registry/dag.py`) already provides:

| CW8.1 Concept | CW9 Equivalent | Status |
|---|---|---|
| DependencyGraph/DependencyEdge | RegistryDag with 21 edge types | Implemented |
| UUID-based resource identity | Node IDs (gwt-NNNN, req-NNNN, resource UUIDs) | Implemented |
| Transitive closure | BFS-computed closure on every edge add | Implemented |
| Cycle detection | validate_edge() acyclicity check | Implemented |
| Forward dependency query | query_relevant() | Implemented |
| Reverse impact analysis | query_impact() | Implemented |
| Minimal subgraph extraction | extract_subgraph() | Implemented |
| Affected test discovery | query_affected_tests() | Implemented |
| GWT behavioral specs | register_gwt() with BEHAVIOR nodes | Implemented |
| Schema-based resource extraction | extractor.py from JSON schema files | Implemented (greenfield only) |

### What CW9 Needs (The Gap)

| CW8.1 Concept | CW9 Status | What's Needed |
|---|---|---|
| Brownfield code ingestion | Not implemented ("Stage 2 FUTURE" in roadmap) | `cw9 ingest` command |
| IN:DO:OUT extraction per function | Not implemented | LLM crawl with Pydantic validation |
| FN Cards (behavior records) | Not implemented | New node kind or metadata format |
| AX Cards (external boundaries) | Not implemented | External boundary handling |
| MAP Notes (workflow structure) | Not implemented | Workflow partitioning |
| SRC_HASH staleness detection | Not implemented | File hash tracking + transitive propagation |
| Pre-pass skeleton extraction | Not implemented | Lightweight signature extractor |
| SQLite behavior store | Not implemented (CW9 uses dag.json) | Either extend dag.json or add SQLite |
| Depth-first provenance crawl | Not implemented | Crawl orchestrator |
| Pass 2: behavior graph -> TLA+ synthesis | Partially exists (loop_runner.py does GWT -> TLA+) | Extend to consume FN cards |

## Proposed Architecture: `cw9 ingest`

### Design Principle

**Do what a developer does, but automatically and persistently.** No fancy math. No abstract syntax trees for behavioral understanding. Line-by-line code reading via LLM, with deterministic skeleton extraction for ground truth, and persistent storage in the resource registry so the knowledge survives across sessions.

### Three-Phase Pipeline

```
Phase 0: Skeleton Pre-Pass (deterministic, no LLM)
  - Enumerate source files in target repo
  - Extract function/method/class signatures via lightweight parsing
  - Compute file hashes for staleness detection
  - Output: signature index with file hashes

Phase 1: Depth-First IN:DO:OUT Crawl (LLM-assisted)
  - Start from entry points (CLI handlers, HTTP routes, event listeners, main())
  - For each function:
    a. Pre-computed skeleton provides ground truth (params, return type, line)
    b. LLM reads the body line-by-line, produces IN:DO:OUT
    c. Pydantic validates the output (FnRecord/InField/OutField — LLM boundary)
    d. Store in crawl.db via CrawlStore (committed per-function for resumability)
    e. Queue all internal_call sources for traversal
    f. On validation failure: retry up to 3x with exponential backoff (1s, 4s, 16s)
    g. On exhausted retries: store skeleton-only stub record (EXTRACTION_FAILED)
  - DFS with visited set (cycle-safe)
  - External calls become AX boundary nodes (never traversed)
  - Post-crawl: source_uuid back-fill pass resolves source_function → source_uuid
  - Post-crawl: dag.json bridge creates RESOURCE nodes + CALLS/DEPENDS_ON/IMPORTS edges
  - Output: populated crawl.db + dag.json graph structure

Phase 2: Workflow MAP Generation (deterministic or LLM-assisted)
  - Partition FN cards into workflows based on entry points
  - Record shared subsystems (functions appearing in multiple workflows)
  - Output: MAP notes stored in crawl.db maps table
```

### Crawl Error Handling

**LLM extraction failure is the most common failure mode.** LLMs produce invalid structured output ~5-15% of the time for extraction tasks. Without explicit handling, a 500-function crawl will have 25-75 failures.

**Per-function retry policy:**

1. **Max 3 retries** with exponential backoff: 1s, 4s, 16s
2. **On each retry**: re-send the same prompt with the Pydantic validation error appended as feedback
3. **On exhausted retries**: store a **skeleton-only stub record**:
   - `do_description = "EXTRACTION_FAILED"`
   - `ins` and `outs` are empty lists
   - `failure_modes = ["LLM extraction failed after 3 retries"]`
   - The skeleton (pre-pass data) is still stored, so the function's signature is known
4. **`crawl_runs` tracking**: `records_failed` counter increments for each exhausted-retry function

**`source_uuid` back-fill pass:**

During DFS, when function A calls function B, function B may not have been visited yet. The `InField` for A's call to B will have `source_function = "B"` but `source_uuid = None`. After the full DFS completes:

1. Query all `ins` rows where `source_uuid IS NULL AND source IN ('internal_call')`
2. For each, look up `source_function` in the `records` table
3. If found, update `source_uuid` to the matching record's UUID
4. If not found (function was never reached by DFS), leave as NULL and log a warning

This is a single SQL UPDATE with a subquery — not LLM-assisted.

### Crawl Resumability

**Design decision: records are committed per-function.** Each successful IN:DO:OUT extraction is committed to SQLite in its own transaction immediately. This guarantees:

- If `cw9 ingest` is killed mid-crawl (Ctrl+C, OOM, timeout), all completed records are preserved
- `crawl_runs` will have `completed_at = NULL`, indicating an interrupted crawl
- `cw9 ingest --incremental` can resume from where it stopped: it checks which functions already have up-to-date records (hash match) and skips them

SQLite with WAL mode provides the ACID guarantees that make this work.

### Resource Estimation

**Per-function cost:**
- Input: skeleton (~200 tokens) + function body (~500 tokens avg) + extraction prompt (~300 tokens) = ~1,000 tokens in
- Output: IN:DO:OUT JSON (~500 tokens avg) = ~500 tokens out
- Estimated cost: ~$0.01-0.03 per function (depending on model and function complexity)

**Reference codebase sizes:**

| Codebase Size | Functions | Estimated Time | Estimated Cost |
|---|---|---|---|
| Small (single module) | 50-100 | 5-15 min | $0.50-3 |
| Medium (typical service) | 200-500 | 30-90 min | $2-15 |
| Large (monolith) | 1,000-5,000 | 2-8 hours | $10-150 |

**Cost control:** `cw9 ingest --max-functions=N` limits the DFS to N functions. Functions beyond the limit are queued but not extracted. This lets users do a targeted crawl (e.g., start from one entry point, limit to 200 functions) before committing to a full crawl.

### Concurrency

**Design decision: sequential DFS by default.** The DFS crawl processes one function at a time. This simplifies:
- SQLite write contention (WAL allows one writer)
- DFS ordering (guarantee parents are visited before children when possible)
- Error attribution (clear which function caused which failure)

**Future optimization:** `--parallel=N` flag for N concurrent LLM calls on independent subtrees. This requires: (a) identifying subtree independence from the DFS frontier, (b) batching SQLite writes, (c) thread-safe visited set. Deferred to after the sequential implementation is proven.

### How This Feeds the Existing CW9 Pipeline

```
                    BROWNFIELD INGESTION (new)
                    ==========================
Target repo  -->  cw9 ingest <path>
                      |
                      v
                  crawl.db has FnRecord rows with IN:DO:OUT
                  dag.json has RESOURCE nodes + CALLS/DEPENDS_ON edges
                      |
                      v
                  EXISTING CW9 PIPELINE
                  =====================
User writes GWTs  -->  cw9 register (wire GWTs to RESOURCE nodes)
                          |
                          v
                      query_context() pulls minimal subgraph
                      (only the RESOURCE nodes relevant to this GWT)
                          |
                          v
                      LLM sees: GWT + relevant IN:DO:OUT cards + edges
                      (compact, focused, no 65% context bloat)
                          |
                          v
                      loop (PlusCal generation + TLC verification)
                          |
                          v
                      bridge (mechanical TLA+ -> code artifacts)
                          |
                          v
                      gen-tests (test generation from verified specs)
```

**The key insight**: `extract_subgraph(gwt_id)` already gives the minimal ancestor+descendant subgraph for a given GWT. Once the registry is populated from real code via `ingest`, this subgraph contains exactly the IN:DO:OUT context the LLM needs — no more, no less. The 65% context bloat disappears because the research is already done and stored.

### Pre-Pass: Skeleton Extraction Without AST

CW8.1's `parse_source_code()` approach — line-by-line text scanning with brace-depth counting — is more robust than AST parsing for this purpose. For CW9, the pre-pass needs to be polyglot (Python, TypeScript, Go at minimum).

**Approach**: Language-specific lightweight scanners that extract only:
- Function/method name
- Parameter names and types (where available)
- Return type (where available)
- File path and line number
- File hash (SHA-256)

These scanners use **pattern matching and brace/indent counting**, not full parsing. They need to handle:
- Python: `def`/`async def` with type hints, `class` with methods
- TypeScript/JavaScript: `function`, arrow functions, class methods, `export`
- Go: `func` declarations, method receivers
- Rust: `fn`/`pub fn`, `impl` blocks (CW8.1 already has this)

For each language, the scanner is ~100-200 lines of straightforward text processing. It doesn't need to understand the language fully — just enough to find function boundaries and extract headers.

**Explicit scanner interface:**

```python
def scan_file(path: Path) -> list[Skeleton]:
    """Extract function/method/class skeletons from a single source file."""

def scan_directory(root: Path, excludes: list[str] | None = None) -> list[Skeleton]:
    """Walk a directory tree, scan all files for the detected language.

    Default excludes: __pycache__, node_modules, .git, .venv, vendor, target, build.
    Files are read as UTF-8 with errors='replace' (no encoding detection).
    """
```

Each language scanner implements `scan_file`. `scan_directory` is shared infrastructure that dispatches to the appropriate `scan_file` based on file extension.

### IN:DO:OUT Data Model

**The IN:DO:OUT detail lives exclusively in `crawl.db`.** dag.json RESOURCE nodes carry only: `id`, `kind=RESOURCE`, `name="function_name @ file_path"`, `description=operational_claim`. The `Node` dataclass (types.py) has no `metadata` field and does not need one — full behavioral data is retrieved from `crawl.db` by UUID when needed.

**Example of a complete FnRecord as stored in crawl.db:**

```python
FnRecord(
    uuid="a1b2c3d4-...",                     # deterministic uuid5 from file_path::class::function_name
    function_name="get_user_profile",
    class_name="UserHandler",                 # NULL for top-level functions
    file_path="src/handlers/user.py",
    line_number=42,
    src_hash="a3f7c9...",                     # SHA-256 of source file
    is_external=False,
    ins=[
        InField(name="user_id", type_str="int", source="parameter"),
        InField(name="db_result", type_str="UserRow", source="internal_call",
                source_function="get_user_by_id", source_uuid="e5f6...",  # back-filled post-crawl
                dispatch="direct"),
    ],
    do_description="Fetches user by ID, validates permissions, returns profile",
    do_steps=[
        "Call get_user_by_id(user_id) to fetch from database",
        "Check if user.is_active, return 404 if not",
        "Call check_permissions(user, request.auth) for authorization",
        "Build UserProfile from user fields",
        "Return UserProfile",
    ],
    do_branches="404 if user not found or inactive; 403 if unauthorized",
    do_errors="DatabaseError from get_user_by_id; PermissionDenied from check_permissions",
    outs=[
        OutField(name="ok", type_str="UserProfile", description="Complete user profile"),
        OutField(name="err", type_str="404", description="User not found or inactive"),
        OutField(name="err", type_str="403", description="Insufficient permissions"),
        OutField(name="err", type_str="500", description="Database connection failure"),
    ],
    failure_modes=[
        "Database connection timeout",
        "User exists but is_active=False (soft delete)",
        "Auth token expired between permission check and response",
    ],
    operational_claim="Returns a complete UserProfile for any active user the requester has permission to view, or an appropriate error code.",
)
```

Edges created during ingestion (stored in dag.json via the post-crawl bridge):
- `CALLS` — function A calls function B (from `internal_call` sources in IN)
- `DEPENDS_ON` — function A depends on the output of function B
- `IMPORTS` — module-level import relationships

### Storage Decision

CW8.1 used SQLite. CW9 currently uses `dag.json`. Options:

1. **Extend dag.json** — Store IN:DO:OUT as node metadata. Pro: single data model, existing tooling works. Con: dag.json gets large for big codebases, no efficient querying, staleness detection is painful without SQL.
2. **Add SQLite alongside dag.json** — Pro: efficient querying, proven in CW8.1, staleness detection via recursive CTEs. Con: two data stores to keep in sync.
3. **Migrate dag.json to SQLite** — Pro: unified, scalable. Con: breaks existing tooling.

**Decision: Option 2 — SQLite (`crawl.db`) for behavioral extraction, dag.json stays for pipeline orchestration.** See "Resolved Questions §6" below for the full rationale. The two stores have clean ownership boundaries: `crawl.db` owns IN:DO:OUT records, `dag.json` owns GWT/requirement/spec/template nodes. They connect through shared node UUIDs. Full schema specification is in the "SQLite Schema Specification" section.

### UUID Generation Strategy

**Decision: Deterministic `uuid5` from `(file_path, class_name, function_name)`.**

```python
import uuid

CRAWL_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")  # fixed namespace for crawl records

def make_record_uuid(file_path: str, function_name: str, class_name: str | None = None) -> str:
    qualified = f"{file_path}::{class_name or ''}::{function_name}"
    return str(uuid.uuid5(CRAWL_NAMESPACE, qualified))
```

**Why deterministic:**
- **Stable across re-ingests**: The same function at the same path produces the same UUID. This means `source_uuid` references, dag.json edges, and GWT→RESOURCE wiring all survive incremental re-ingest without rebinding.
- **Handles renames**: If a function is renamed, it gets a new UUID. The old UUID becomes an orphan, detected and cleaned up during the post-crawl bridge step.
- **Handles moves**: If a function moves to a different file, it gets a new UUID. Same orphan cleanup.

**Trade-off:** Two functions with the same name in the same class in the same file (impossible in Python/Go/Rust, possible in JS via shadowing) would collide. This is acceptable — such cases are pathological and the scanner should warn.

### Incremental Re-ingest Sync Protocol

When `cw9 ingest --incremental` runs:

1. **crawl.db (UPSERT):** For each function, use `INSERT OR REPLACE` keyed on UUID. Since UUIDs are deterministic from `(file_path, class_name, function_name)`, unchanged functions keep their UUID and are skipped (hash match). Changed functions get their record replaced in place.

2. **dag.json (add_node):** The post-crawl bridge step calls `RegistryDag.add_node(node)`. **No new method is needed** — `add_node()` already silently overwrites existing nodes with the same ID (dag.py:37 — `self.nodes[node.id] = node` is a dict assignment). This means `add_node()` IS an upsert. Edges are preserved because they reference nodes by string ID, not by `Node` instance.

3. **Orphan cleanup:** After the full re-ingest, compare the set of UUIDs in `crawl.db` against the set of crawl-originated RESOURCE nodes in dag.json. Any dag.json node whose UUID is no longer in `crawl.db` (function was deleted or renamed) is removed along with its edges. This requires a new `remove_node()` method:

```python
def remove_node(self, node_id: str) -> None:
    """Remove a node and all edges referencing it."""
    if node_id not in self.nodes:
        return
    del self.nodes[node_id]
    self.edges = [e for e in self.edges if e.from_id != node_id and e.to_id != node_id]
    self._recompute_closure()
    self._recompute_components()
```

### GWT→RESOURCE Edge Wiring (Critical Integration Point)

**Problem discovered during integration analysis:** In the existing CW9 pipeline, GWT nodes have **zero outgoing edges**. `query_relevant(gwt_id)` returns an empty `transitive_deps` because `closure[gwt_id]` is `set()`. The greenfield pipeline works anyway because the LLM gets its context from `context_text` (plan files), not from DAG-derived RESOURCE data.

For the brownfield pipeline, we need `transitive_deps` to include the ingested RESOURCE nodes so `query_context()` can look up their IN:DO:OUT cards from crawl.db. **This requires edges from GWT nodes to RESOURCE nodes.**

**Solution: Extend `cmd_register` to accept `depends_on` edges.**

The register payload schema gains a new optional field on GWT entries:

```json
{
  "gwts": [
    {
      "criterion_id": "...",
      "given": "...",
      "when": "...",
      "then": "...",
      "parent_req": "...",
      "depends_on": ["uuid-of-fn-1", "uuid-of-fn-2"]
    }
  ]
}
```

In `_register_payload()`, after creating the GWT node, iterate `depends_on` and create `DEPENDS_ON` edges:

```python
# After register_gwt() returns gwt_id:
for dep_uuid in gwt_entry.get("depends_on", []):
    if dep_uuid in dag.nodes:
        dag.add_edge(Edge(gwt_id, dep_uuid, EdgeType.DEPENDS_ON))
```

**Direction:** `gwt-NNNN` → `RESOURCE-UUID` via `DEPENDS_ON`. This means `closure[gwt_id]` will include the RESOURCE node AND all its transitive CALLS/DEPENDS_ON dependencies. `query_context()` will then find these RESOURCE UUIDs in `transitive_deps` and look them up in crawl.db.

**Who provides `depends_on`?** The `cw9 gwt-author` command. It reads the research notes, queries crawl.db for relevant cards, generates GWTs, and includes `depends_on` UUIDs for the functions each GWT touches. This is the LLM-assisted bridge step described in Resolved Questions §5.

**Validation:** `depends_on` UUIDs are checked against `dag.nodes` — if a UUID doesn't exist (function not ingested, or hallucination), the edge is silently skipped (matching `_add_edge_safe` behavior).

### Surviving `cw9 extract` (The Merge Problem)

**Problem:** `cmd_extract()` (cli.py:197-241) creates a **fresh** DAG from `SchemaExtractor.extract()` and calls `merge_registered_nodes(old_dag)` which only preserves nodes with `gwt-` or `req-` prefixes (dag.py:388-389). Crawl-originated RESOURCE nodes have UUID-format IDs — they would be **silently dropped**.

This means: running `cw9 pipeline` (which calls `cmd_extract` in Phase 0) after `cw9 ingest` would **destroy all ingested RESOURCE nodes** and their edges.

**Solution: Extend `merge_registered_nodes()` to preserve crawl-originated nodes.**

The method needs to recognize crawl-originated nodes. Two approaches:

**Option A (Recommended): Check crawl.db for membership.**

```python
def merge_registered_nodes(self, old_dag: "RegistryDag",
                           crawl_uuids: set[str] | None = None) -> int:
    merged = 0
    fresh_ids = set(self.nodes.keys())

    for nid, node in old_dag.nodes.items():
        if nid in fresh_ids:
            continue
        prefix = nid.split("-")[0] if "-" in nid else ""
        is_registered = prefix in ("gwt", "req")
        is_crawl = crawl_uuids is not None and nid in crawl_uuids
        if not (is_registered or is_crawl):
            continue
        self.add_node(node)
        merged += 1

    # Preserve edges involving merged nodes (existing logic unchanged)
    ...
```

`cmd_extract` passes `crawl_uuids` by checking if `.cw9/crawl.db` exists and querying all record UUIDs:

```python
crawl_uuids = None
crawl_db = state_root / "crawl.db"
if crawl_db.exists():
    store = CrawlStore(crawl_db)
    store.connect()
    crawl_uuids = set(r.uuid for r in store.get_all_records())
    store.close()

merged = dag.merge_registered_nodes(old_dag, crawl_uuids=crawl_uuids)
```

**Option B: Use a prefix convention.**

Give crawl node IDs a recognizable prefix like `fn-` and add `"fn"` to the merge whitelist. But this conflicts with the UUID generation strategy (uuid5 produces standard UUID format, not `fn-` prefixed strings).

**Decision: Option A.** It's more robust, doesn't constrain the ID format, and the CrawlStore query is cheap (single `SELECT uuid FROM records`).

### Staleness Detection

Same approach as CW8.1:
- Store `src_hash` (SHA-256 of source file) per function node
- On re-ingest, compare current file hash against stored hash
- Transitively mark dependents as stale via the DAG's closure
- Only re-extract stale functions (incremental crawl)

CW9 already has `query_impact(target_id)` which gives all nodes that transitively depend on a target — this is exactly the transitive staleness propagation query.

**Hash granularity trade-off:** `src_hash` is a file-level hash, not a per-function-body hash. If two functions live in the same file and one changes, both get marked stale. This is conservative (may re-extract unchanged functions) but correct (never misses a change). Per-function-body hashing would require the scanner to extract exact function boundaries including all nested content — fragile for languages with significant whitespace or complex nesting. File-level hashing is simpler and CW8.1 proved it works in practice.

## Integration with CW9 Pipeline Commands

### New CLI Commands

```bash
# Ingest an external codebase into the registry
cw9 ingest <path> [--lang=python|typescript|go|rust] [--entry=src/main.py] [--max-functions=N]

# Check which ingested nodes are stale
cw9 stale

# Re-ingest only stale nodes
cw9 ingest <path> --incremental

# Ingest with test cross-references
cw9 ingest <path> --with-tests

# Show the IN:DO:OUT card for a specific node
cw9 show <node-id> --card
```

**Flag precedence:** `--lang` overrides auto-detection when provided. If `--lang=python` is specified but a `go.mod` is found, the `--lang` flag wins. Auto-detection is the fallback when `--lang` is omitted.

**Output format:** `cw9 ingest` prints a human-readable summary to stderr and returns exit code 0 on success:

```
Ingesting /path/to/repo (python, detected: fastapi web app)
Entry points: 12 (HTTP routes)
Phase 0: 347 skeletons extracted (42 files)
Phase 1: 289/347 functions extracted, 3 failed, 55 skipped (external)
Phase 2: 4 workflow MAPs generated
Bridge: 289 RESOURCE nodes + 1,204 edges written to dag.json

Summary: 289 created, 0 updated, 55 skipped, 3 failed
```

For machine consumption: `cw9 ingest --json` outputs a JSON object to stdout with all counters.

**Pipeline integration:** `cw9 ingest` is a **standalone command**, not part of `cw9 pipeline`. The pipeline command calls `cmd_extract` (schema-based) in Phase 0, which is the greenfield path. Brownfield users run `cw9 ingest` manually before `cw9 pipeline`.

**Surviving `cw9 extract`:** `cmd_extract` creates a fresh DAG and calls `merge_registered_nodes()` which must preserve crawl-originated RESOURCE nodes (see "Surviving cw9 extract" section above). The extended `merge_registered_nodes(old_dag, crawl_uuids=...)` parameter makes this work. Without this fix, `cw9 pipeline` Phase 0 would destroy all ingested nodes.

**`query_context()` auto-detection:** When `.cw9/crawl.db` exists, `query_context()` opens a `CrawlStore` and looks up each RESOURCE UUID found in `transitive_deps`. If a matching `FnRecord` exists, it's appended to `bundle.cards`. This is the **only** code path that crosses the crawl.db ↔ dag.json boundary at query time. If `crawl.db` doesn't exist (greenfield project), no cards are loaded and behavior is unchanged.

### Modified Pipeline Flow

```bash
# 1. Initialize CW9 project targeting the external repo
cw9 init --target=/path/to/external/repo

# 2. Ingest the codebase (populates crawl.db + dag.json RESOURCE nodes)
cw9 ingest /path/to/external/repo --entry=src/main.py

# 3. Generate GWTs from research notes (produces depends_on edges)
cw9 gwt-author --research=notes.md | cw9 register .
#    This creates GWT nodes + DEPENDS_ON edges to ingested RESOURCE nodes

# 4. Run the pipeline — LLM gets focused context:
#    query_context(gwt_id) follows DEPENDS_ON edges to RESOURCE nodes,
#    loads IN:DO:OUT cards from crawl.db, renders them in the prompt
cw9 pipeline --gwt=gwt-0001 --skip-setup
#    NOTE: --skip-setup skips cmd_extract Phase 0 (already done by ingest)

# 5. After code changes, check staleness
cw9 stale

# 6. Incrementally re-ingest changed files
cw9 ingest /path/to/external/repo --incremental
```

## Context Budget Analysis

**Current state** (research_codebase approach):
- MCP servers: ~65% of context
- Research skill overhead: ~10%
- Available for actual reasoning: ~25%

**Proposed state** (ingest + extract_subgraph):
- MCP servers: ~65% of context (unchanged)
- Subgraph context (only relevant IN:DO:OUT cards): ~10-15%
- Available for actual reasoning: ~20-25%

The improvement isn't in the raw numbers — it's in the **quality** of the context. Instead of the LLM using 25% of context to both discover and reason about code, it uses 10-15% on pre-computed, validated, focused behavioral descriptions. The remaining context is pure reasoning about the GWT and PlusCal generation.

For the ingest phase itself, the LLM operates **per-function** with a focused prompt (skeleton + function body), so context is never a bottleneck during crawling.

## Resolved Questions

### 1. Polyglot Pre-Pass: Separate Scanners Per Language

**Answer: Language-specific separate scanners. No shared regex engine.**

Each language has fundamentally different function boundary markers. Trying to unify them into a single regex-based scanner with language-specific pattern tables is a false generalization — it creates a framework that's harder to maintain than the individual scanners, and the "shared" code (regex dispatch, brace counting) is trivial compared to the language-specific rules.

**What each scanner does (and only this):**
- Find function/method/class boundaries
- Extract: name, parameters (with types where available), return type, line number
- Compute file SHA-256
- Output: JSON array of `Skeleton` objects

**Per-language specifics:**

| Language | Boundary markers | Scoping | Complications |
|---|---|---|---|
| **Python** | `def`/`async def`, `class` + indent level | Indentation-based — track indent depth, function ends when indent returns to or below the `def` line's level | Decorators (`@app.route`, `@click.command`) are entry point hints. Type hints are optional. Nested functions exist. |
| **TypeScript/JS** | `function`, `=>`, `class` methods, `export` | Brace-depth counting from `{` after signature | Arrow functions can be single-expression (no braces). `export default` wrapping. Destructured params. |
| **Go** | `func` keyword, optional receiver `(r *Type)` | Brace-depth counting | Method receivers. Multiple return values. Named returns. |
| **Rust** | `fn`/`pub fn`, `impl` blocks | Brace-depth counting (CW8.1 already has this via `parse_source_code.rs`) | `impl` blocks nest functions. Lifetime annotations in signatures. `async fn`. |

Each scanner is ~100-200 lines of straightforward text processing. The cost of having 4 separate scanners (~600 lines total) is dramatically less than the cost of debugging a "unified" scanner that handles edge cases across 4 languages through configuration. The scanners share a common output format (`Skeleton` Pydantic model) but not implementation.

**Implementation order:** Python first (most immediate need), then TypeScript, then Go. Rust reuses CW8.1's `parse_source_code.rs` approach directly.

---

### 2. Entry Point Discovery: Know What You're Looking At

**Answer: Don't generalize. Look at what the codebase actually is and find the right entry points for that kind of thing.**

Generalization is a weakness here. The correct approach is: **detect the codebase type, then apply the specific entry point discovery strategy for that type.** Each strategy is its own ~30-line function. They don't share logic because they're looking for fundamentally different things.

**Detection heuristics (checked in order):**

| Codebase Type | How to Detect | Entry Points to Extract |
|---|---|---|
| **Web app (Python)** | `requirements.txt`/`pyproject.toml` contains `flask`/`django`/`fastapi`/`starlette` | Route decorators: `@app.route`, `@router.get/post/put/delete`, `@api_view`, Django `urlpatterns` entries. Each decorated function is an entry point. |
| **Web app (TS/JS)** | `package.json` contains `express`/`fastify`/`koa`/`next`/`hono` | Route registrations: `app.get/post/put/delete(path, handler)`, Next.js `pages/` or `app/` directory file-based routing, controller decorators in NestJS. |
| **Web app (Go)** | `go.mod` contains `net/http`, `gin-gonic`, `chi`, `echo`, `fiber` | `http.HandleFunc`, `r.GET/POST`, handler registrations. `main()` is also an entry point. |
| **CLI app** | Python: `argparse`/`click`/`typer` imports, `console_scripts` in setup.py/pyproject.toml. Go: `cobra` or `flag` imports. TS: `commander`/`yargs` imports. | The CLI entrypoint: `main()`, `cli()`, the function registered in `console_scripts`, or `cobra.Command` `Run` fields. |
| **Library** | No web framework, no CLI framework, has `__init__.py` with `__all__`, or `index.ts` with exports, or exported package functions | Public API surface: everything in `__all__`, all `export`ed functions/classes from index files, all `pub fn` in `lib.rs`. |
| **Event-driven** | `celery`/`dramatiq`/`rq` imports, `@task` decorators, SQS/Kafka consumer patterns | Task functions decorated with `@app.task`, `@dramatiq.actor`, consumer handler registrations. |

**The `--entry` flag is a manual override**, not the primary mechanism. If the user knows the entry point, they specify it. If they don't, the scanner detects the codebase type and finds entry points automatically. The detection is not magic — it's reading `package.json`/`requirements.txt`/`go.mod` and checking for known framework imports. This is the kind of grunt work that should be deterministic, not LLM-assisted.

**What happens after detection:** The entry point discovery function returns a list of `EntryPoint` objects:

```python
@dataclass
class EntryPoint:
    file_path: str
    function_name: str
    entry_type: EntryType  # HTTP_ROUTE, CLI_COMMAND, PUBLIC_API, EVENT_HANDLER, MAIN, TEST
    route: str | None      # "/api/users" for HTTP, None otherwise
    method: str | None     # "GET"/"POST" for HTTP, None otherwise
```

These become the initial seed for the DFS queue.

---

### 3. Dynamic Dispatch: Record the Ambiguity in the Scanner

**Answer: The language-specific scanner records dispatch ambiguity as a first-class field in the IN:DO:OUT schema.**

When the LLM reads `self.handler.process()` line-by-line, it can see this is a dispatch through an attribute — it doesn't know the concrete type at static analysis time. The scanner doesn't resolve this; it **records** it. The ambiguity is data, not an error.

**New field in `InField`:**

```python
class DispatchKind(str, Enum):
    DIRECT = "direct"              # foo() — unambiguous call
    ATTRIBUTE = "attribute"        # self.handler.process() — attribute dispatch
    DYNAMIC = "dynamic"            # getattr(obj, method_name)() — fully dynamic
    OVERRIDE = "override"          # super().method() or overridden method
    CALLBACK = "callback"          # fn passed as argument, called later
    PROTOCOL = "protocol"          # duck typing / protocol conformance

class InField(BaseModel):
    name: str
    type_str: str
    source: InSource
    source_uuid: str | None = None
    source_file: str | None = None
    source_function: str | None = None
    source_description: str | None = None
    dispatch: DispatchKind = DispatchKind.DIRECT       # NEW
    dispatch_candidates: list[str] | None = None       # NEW — possible concrete targets
```

**How the LLM populates this:**

The LLM prompt for IN:DO:OUT extraction includes explicit instructions:

> For each function call in the body:
> - If the call target is unambiguous (e.g., `validate(input)`), set `dispatch: "direct"`.
> - If the call goes through an attribute (e.g., `self.repo.save(user)`), set `dispatch: "attribute"` and list the type hint of `self.repo` in `dispatch_candidates` if visible. If the type is `UserRepository`, record `["UserRepository.save"]`.
> - If the call is fully dynamic (e.g., `getattr(self, action)()`), set `dispatch: "dynamic"`. Record what you can see about the possible targets in `dispatch_candidates`.
> - If the call is through a callback parameter (e.g., `on_complete(result)` where `on_complete` was passed in), set `dispatch: "callback"`.

**How this helps downstream:** When `extract_subgraph()` pulls context for a GWT, ambiguous dispatch edges are visible. The LLM generating PlusCal can see "this call might go to any of [A, B, C]" and model it as nondeterministic choice (`either/or` in PlusCal), which is exactly what TLA+ is designed to verify.

**The scanner's role:** The language-specific scanner contributes to dispatch resolution by recognizing patterns statically:

- **Python scanner**: When parsing a `class`, record all methods. When parsing `__init__`, record attribute assignments with type hints (`self.repo: UserRepository = repo`). This lets the scanner pre-populate `dispatch_candidates` for `self.repo.method()` calls without needing the LLM.
- **TypeScript scanner**: Record class fields with types, constructor parameter properties (`constructor(private repo: UserRepository)`). Same purpose.
- **Go scanner**: Method receivers are explicit — `func (s *Service) Handle()` is unambiguous. Interface dispatch through a field typed as an interface — record the interface name.

The scanner doesn't resolve inheritance hierarchies or do type inference — it records what's visible at the declaration site. The LLM does the rest during the IN:DO:OUT pass.

---

### 4. Test Isolation: Separate Path, Confirmation Signal, Lower Overhead

**Answer: Tests are a separate ingestion path. They are NOT entry points for the main crawl. They serve two purposes: confirming the crawl's accuracy, and capturing behavioral data with less overhead.**

**Why separate:**
- Tests exercise the same code the crawl traverses, but from a different angle. Mixing test entry points with production entry points pollutes the workflow MAP — tests don't represent production data flow, they represent verification of production data flow.
- Test files have different structure: `setup/teardown`, assertion patterns, fixtures, mocks. Treating them as regular functions produces noisy IN:DO:OUT cards that don't help with PlusCal generation.

**Two uses for test data:**

1. **Confirmation signal.** After the main crawl produces IN:DO:OUT cards, a lightweight test scan can cross-reference:
   - "The crawl says `create_user()` has OUT `err: DuplicateEmail`" — do any tests exercise this error path? If yes, higher confidence. If no test covers it, flag it as unverified.
   - This is a simple grep/match operation, not a full IN:DO:OUT extraction. The test scanner looks for assertion patterns (`assert`, `expect`, `assertEqual`) and maps them to the functions they call.

2. **Lower-overhead behavioral capture.** Tests are often simpler than production code — a test for `create_user()` shows you exactly what inputs produce what outputs, without the surrounding framework noise. For functions where the LLM struggles to extract clean IN:DO:OUT from the production code (deeply nested, lots of framework magic), the test can provide a cleaner signal:
   - Input: the test's setup/arrange section
   - Expected output: the test's assertions
   - This is cheaper than a full LLM IN:DO:OUT pass — it might even be deterministic (regex-based assertion extraction).

**Implementation:**

```python
@dataclass
class TestReference:
    """Deterministic extraction from test files — @dataclass, not Pydantic."""
    test_file: str
    test_function: str
    target_function: str         # the function under test
    target_file: str
    inputs_observed: list[str]   # values/fixtures passed to the target
    outputs_asserted: list[str]  # assertion descriptions
    covers_error_path: bool      # does it test an error case?

# Stored in SQLite as a separate table, not mixed into records/ins/outs
```

```sql
CREATE TABLE test_refs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_file       TEXT NOT NULL,
    test_function   TEXT NOT NULL,
    target_uuid     TEXT REFERENCES records(uuid),
    target_function TEXT NOT NULL,
    target_file     TEXT NOT NULL,
    inputs_observed TEXT,         -- JSON array
    outputs_asserted TEXT,        -- JSON array
    covers_error_path BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**CLI:** `cw9 ingest <path> --tests` runs only the test scanner. `cw9 ingest <path>` (default) ignores test files. `cw9 ingest <path> --with-tests` runs both the main crawl and the test scanner in sequence.

---

### 5. GWT Authoring from IN:DO:OUT: LLM-Assisted Bridge

**Answer: Yes, this is an LLM-assisted step. The LLM reads the research notes, reads the relevant IN:DO:OUT cards, and produces GWTs wired to the correct ingested resources.**

This is the critical bridge between "I know what I want to build" and "here's a formally verifiable specification." The existing CW9 pipeline already has `cw9 register` for GWT ingestion — the gap is producing the GWTs in the first place when working against a brownfield codebase.

**Critical context:** In the existing greenfield pipeline, GWT nodes have **zero outgoing edges** — `query_relevant(gwt_id)` returns empty `transitive_deps`. The greenfield pipeline works because context comes from `context_text` (plan files), not from DAG-derived RESOURCE data. For brownfield, we need `depends_on` edges from GWTs to ingested RESOURCE nodes so `query_context()` can find and render their IN:DO:OUT cards.

**The workflow:**

```
Research notes (what to build)
    +
IN:DO:OUT cards (what exists)
    |
    v
LLM-assisted GWT generation (produces depends_on UUIDs)
    |
    v
cw9 register (EXTENDED: creates GWTs + DEPENDS_ON edges to RESOURCE nodes)
    |
    v
query_context(gwt_id) → closure includes RESOURCE nodes → cards loaded from crawl.db
    |
    v
cw9 pipeline (LLM sees GWT + IN:DO:OUT cards + edges)
```

**The LLM prompt structure:**

```
You are generating GWT (Given/When/Then) behavioral specifications for a new feature
in an existing codebase. You have two inputs:

1. RESEARCH NOTES — what the user wants to build:
{research_notes}

2. EXISTING BEHAVIOR CARDS — what the codebase currently does:
{relevant_indoout_cards}

For each behavioral change or addition described in the research notes:

a. Identify which existing functions are affected (by UUID from the cards)
b. Write a GWT triple that specifies the new behavior
c. List which existing RESOURCE nodes this GWT should be wired to (DEPENDS_ON edges)
d. If the feature requires a new function, describe it as a new RESOURCE node
   with placeholder IN:DO:OUT

Output format (matches extended cw9 register payload):
{
    "gwts": [
        {
            "criterion_id": "crawl-gwt-001",  // stable ID for bindings.json
            "given": "...",
            "when": "...",
            "then": "...",
            "depends_on": ["res-uuid-1", "res-uuid-2"],  // → DEPENDS_ON edges in dag.json
            "modifies": ["res-uuid-3"],  // existing functions that change
            "creates": [                  // new functions needed
                {
                    "name": "new_function @ path",
                    "description": "...",
                    "ins": [...],
                    "outs": [...]
                }
            ]
        }
    ]
}
```

**Which IN:DO:OUT cards to include:** Not all of them. The LLM generating GWTs doesn't need every function in the codebase. Selection strategy:

1. Parse the research notes for function/file/module names mentioned
2. Look up those names in the `records` table
3. Pull those records + their transitive dependencies (via `deps` view recursive CTE)
4. Pull their transitive dependents (reverse direction — who calls them)
5. That subgraph is the relevant context

This is the same `extract_subgraph` principle, but keyed on text mentions rather than a GWT node ID.

**CLI:** `cw9 gwt-author --research=<path-to-notes>` — reads the research file, queries the crawl DB for relevant cards, runs the LLM, writes a JSON payload to stdout. The output format matches what `cw9 register` expects on stdin, so the two commands compose via pipe:

```bash
cw9 gwt-author --research=notes.md | cw9 register .
```

**Validation:** The GWT output goes through the same Pydantic validation as manually authored GWTs. The `depends_on` UUIDs are checked against the crawl DB — if a UUID doesn't exist, it's a hallucination and gets flagged.

---

### 6. DAG Size: SQLite Now

**Answer: Use SQLite from the start. Don't wait for dag.json to become a bottleneck — spec the schema now.**

The arguments for "extend dag.json first" were:
- Single data model
- Existing tooling works
- Metadata per node is modest

These are outweighed by:

1. **The crawl DB is already SQLite.** CW8.1 proved this works. The IN:DO:OUT data has relational structure (records → ins → outs, with foreign keys between records via `source_uuid`). JSON flattening of this structure loses queryability.

2. **Staleness detection needs SQL.** The recursive CTE for transitive staleness propagation is natural in SQL and painful in JSON. Computing "all records transitively affected by this file change" against a flat JSON file means loading the entire file, building an in-memory graph, running BFS, then serializing back. SQLite does this with a single query.

3. **dag.json is already showing scaling strain.** The current `RegistryDag.from_dict()` loads the entire file, recomputes transitive closure (O(V × E) BFS), and recomputes connected components (O(V × E) union-find) on every load. For 200 greenfield resources this is fine. For 2000 brownfield functions with 5000+ edges, this becomes a measurable startup cost.

4. **Two data stores is acceptable when they have clear ownership.** The crawl DB owns behavioral extraction data (records, ins, outs, maps, test_refs). The RegistryDag owns pipeline orchestration data (GWTs, requirements, specs, templates, test artifacts). They connect through RESOURCE nodes — each crawl record UUID appears as a node ID in dag.json with an edge wiring it to the relevant GWT. This is a clean boundary, not a synchronization nightmare.

5. **Query patterns are relational.** "Give me all functions that call `get_user_by_id`" is `SELECT record_uuid FROM ins WHERE source_function = 'get_user_by_id'`. "Give me all functions in file X that are stale" is a join + hash comparison. These are SQL's bread and butter.

**Decision: SQLite for the crawl store. dag.json stays for the pipeline DAG.** They connect through node IDs.

---

## SQLite Schema Specification: `crawl.db`

### Location

```
.cw9/crawl.db
```

Same directory as `dag.json`. WAL mode enabled on connection: `PRAGMA journal_mode=WAL`.

### Schema

```sql
-- ============================================================
-- crawl.db — Brownfield IN:DO:OUT behavioral extraction store
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ----- Core tables -----

CREATE TABLE IF NOT EXISTS records (
    uuid            TEXT PRIMARY KEY,
    function_name   TEXT NOT NULL,
    class_name      TEXT,                    -- NULL for top-level functions, set for methods
    file_path       TEXT NOT NULL,
    line_number     INTEGER,
    src_hash        TEXT NOT NULL,           -- SHA-256 of source file at extraction time
    is_external     BOOLEAN NOT NULL DEFAULT FALSE,
    do_description  TEXT NOT NULL DEFAULT '',
    do_steps        TEXT,                    -- JSON array of step strings
    do_branches     TEXT,                    -- prose description of branches
    do_loops        TEXT,                    -- prose description of loops
    do_errors       TEXT,                    -- prose description of error handling
    failure_modes   TEXT,                    -- JSON array of failure mode strings
    operational_claim TEXT DEFAULT '',
    skeleton_json   TEXT,                    -- full Skeleton model dump (JSON)
    source_crate    TEXT,                    -- AX cards only: external package name
    boundary_contract TEXT,                  -- AX cards only: assumed contract
    schema_version  INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(file_path, COALESCE(class_name, ''), function_name)
);

CREATE TABLE IF NOT EXISTS ins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type_str        TEXT NOT NULL,
    source          TEXT NOT NULL CHECK(source IN ('parameter','state','literal','internal_call','external')),
    source_uuid     TEXT REFERENCES records(uuid),  -- NULL until provenance resolved
    source_file     TEXT,
    source_function TEXT,
    source_description TEXT,
    dispatch        TEXT NOT NULL DEFAULT 'direct'
                    CHECK(dispatch IN ('direct','attribute','dynamic','override','callback','protocol')),
    dispatch_candidates TEXT,               -- JSON array of possible concrete targets
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);

CREATE TABLE IF NOT EXISTS outs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_uuid     TEXT NOT NULL REFERENCES records(uuid) ON DELETE CASCADE,
    name            TEXT NOT NULL CHECK(name IN ('ok','err','side_effect','mutation')),
    type_str        TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    ordinal         INTEGER NOT NULL,
    UNIQUE(record_uuid, ordinal)
);

-- ----- Workflow structure (populated in Phase 2) -----

CREATE TABLE IF NOT EXISTS maps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name   TEXT NOT NULL UNIQUE,
    entry_uuid      TEXT NOT NULL REFERENCES records(uuid),
    path_uuids      TEXT NOT NULL,           -- JSON array of UUIDs in traversal order
    shared_uuids    TEXT,                    -- JSON array of shared subsystem UUIDs
    properties      TEXT,                    -- JSON array of property names for TLA+
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ----- Test cross-references (populated by --with-tests) -----

CREATE TABLE IF NOT EXISTS test_refs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_file       TEXT NOT NULL,
    test_function   TEXT NOT NULL,
    target_uuid     TEXT REFERENCES records(uuid),
    target_function TEXT NOT NULL,
    target_file     TEXT NOT NULL,
    inputs_observed TEXT,                    -- JSON array of input descriptions
    outputs_asserted TEXT,                   -- JSON array of assertion descriptions
    covers_error_path BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(test_file, test_function, target_function)
);

-- ----- Entry points (populated during Phase 0) -----

CREATE TABLE IF NOT EXISTS entry_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT NOT NULL,
    function_name   TEXT NOT NULL,
    entry_type      TEXT NOT NULL CHECK(entry_type IN (
                        'http_route','cli_command','public_api',
                        'event_handler','main','test'
                    )),
    route           TEXT,                    -- HTTP path, e.g. "/api/users"
    method          TEXT,                    -- HTTP method, e.g. "GET"
    record_uuid     TEXT REFERENCES records(uuid),  -- linked after crawl
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(file_path, function_name)
);

-- ----- Crawl metadata -----

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_path     TEXT NOT NULL,           -- path to the ingested repo
    language        TEXT NOT NULL,            -- python, typescript, go, rust
    codebase_type   TEXT,                    -- web_app, cli, library, event_driven
    started_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    records_created INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,       -- already up-to-date (hash match)
    records_failed  INTEGER DEFAULT 0,       -- LLM extraction exhausted retries
    is_incremental  BOOLEAN NOT NULL DEFAULT FALSE
);

-- ----- Derived views -----

-- Dependency graph: which record depends on which
CREATE VIEW IF NOT EXISTS deps AS
SELECT DISTINCT
    i.record_uuid AS dependent_uuid,
    i.source_uuid AS dependency_uuid,
    i.dispatch,
    i.dispatch_candidates
FROM ins i
WHERE i.source_uuid IS NOT NULL;

-- All non-external records for staleness checking
CREATE VIEW IF NOT EXISTS stale_candidates AS
SELECT r.uuid, r.function_name, r.file_path, r.src_hash
FROM records r
WHERE r.is_external = FALSE;

-- Functions with ambiguous dispatch (need human/LLM review)
CREATE VIEW IF NOT EXISTS ambiguous_dispatch AS
SELECT
    r.uuid,
    r.function_name,
    r.file_path,
    i.name AS input_name,
    i.dispatch,
    i.dispatch_candidates,
    i.source_function
FROM ins i
JOIN records r ON i.record_uuid = r.uuid
WHERE i.dispatch != 'direct';

-- Test coverage per function
CREATE VIEW IF NOT EXISTS test_coverage AS
SELECT
    r.uuid,
    r.function_name,
    r.file_path,
    COUNT(t.id) AS test_count,
    SUM(CASE WHEN t.covers_error_path THEN 1 ELSE 0 END) AS error_path_tests
FROM records r
LEFT JOIN test_refs t ON t.target_uuid = r.uuid
WHERE r.is_external = FALSE
GROUP BY r.uuid;

-- ----- Indexes -----

CREATE INDEX IF NOT EXISTS idx_ins_record ON ins(record_uuid);
CREATE INDEX IF NOT EXISTS idx_ins_source ON ins(source_uuid);
CREATE INDEX IF NOT EXISTS idx_ins_source_fn ON ins(source_function);
CREATE INDEX IF NOT EXISTS idx_outs_record ON outs(record_uuid);
CREATE INDEX IF NOT EXISTS idx_records_file ON records(file_path);
CREATE INDEX IF NOT EXISTS idx_records_name ON records(function_name);
CREATE INDEX IF NOT EXISTS idx_test_refs_target ON test_refs(target_uuid);
CREATE INDEX IF NOT EXISTS idx_entry_points_record ON entry_points(record_uuid);
```

### Key Queries

**Transitive staleness propagation** (given a set of directly stale UUIDs):

```sql
WITH RECURSIVE stale(uuid) AS (
    -- Seed: directly stale records (hash mismatch)
    SELECT uuid FROM records WHERE uuid IN (?, ?, ...)
    UNION
    -- Propagate: any record that consumes output from a stale record
    SELECT i.record_uuid
    FROM ins i
    JOIN stale s ON i.source_uuid = s.uuid
)
SELECT DISTINCT uuid FROM stale;
```

**Subgraph extraction for GWT authoring** (given a function name mentioned in research):

```sql
-- Forward: everything this function depends on
WITH RECURSIVE forward(uuid) AS (
    SELECT uuid FROM records WHERE function_name = ?
    UNION
    SELECT i.source_uuid
    FROM ins i
    JOIN forward f ON i.record_uuid = f.uuid
    WHERE i.source_uuid IS NOT NULL
)
SELECT * FROM records WHERE uuid IN (SELECT uuid FROM forward);

-- Reverse: everything that depends on this function
WITH RECURSIVE reverse(uuid) AS (
    SELECT uuid FROM records WHERE function_name = ?
    UNION
    SELECT i.record_uuid
    FROM ins i
    JOIN reverse r ON i.source_uuid = r.uuid
)
SELECT * FROM records WHERE uuid IN (SELECT uuid FROM reverse);
```

**Card rendering** (generate markdown from DB):

```sql
SELECT
    r.*,
    json_group_array(json_object(
        'name', i.name, 'type', i.type_str, 'source', i.source,
        'dispatch', i.dispatch, 'source_function', i.source_function
    )) AS ins_json,
    (SELECT json_group_array(json_object(
        'kind', o.name, 'type', o.type_str, 'description', o.description
    )) FROM outs o WHERE o.record_uuid = r.uuid) AS outs_json
FROM records r
LEFT JOIN ins i ON i.record_uuid = r.uuid
WHERE r.uuid = ?
GROUP BY r.uuid;
```

### Connection to dag.json

The bridge between `crawl.db` and `dag.json` is the `cw9 ingest` command's post-crawl step:

1. For each `records` row, call `dag.add_node(Node(kind=RESOURCE, id=<uuid>, name="<function_name> @ <file_path>", description=<operational_claim>))` — `add_node()` already works as upsert (silently overwrites on duplicate ID), so incremental re-ingest works without errors
2. For each `deps` view row, create an `Edge(from_id=dependent_uuid, to_id=dependency_uuid, edge_type=CALLS)` in dag.json (duplicate edges are silently skipped by `add_edge`)
3. For each `entry_points` row, create an `Edge(from_id=entry_uuid, to_id=record_uuid, edge_type=HANDLES)` if HTTP, `IMPORTS` if CLI, etc.
4. Orphan cleanup: remove dag.json RESOURCE nodes whose UUIDs no longer appear in `crawl.db` (via `remove_node`)

The IN:DO:OUT detail stays in SQLite. dag.json carries only the graph structure needed for `extract_subgraph()` and `query_context()`. When the pipeline needs the full card for a node, it queries `crawl.db` by UUID.

**How the DAG-level data reaches the LLM:** For each RESOURCE node in `transitive_deps`, `format_prompt_context()` renders:
```
- {node.id} ({node.kind.value}): {node.name} — {node.description}
```
This means `node.description` = `operational_claim` is the **summary** that appears in the `## Transitive Dependencies` section. The full IN:DO:OUT card (from `bundle.cards`) provides the **detail** in a separate `## Existing Code Behavior` section. Together they give the LLM both a quick overview and full behavioral data.

**Pre-existing gap note:** `bundle.schemas` is populated by `query_context()` but never rendered by `format_prompt_context()` — there is no `## Schemas` section. This is a greenfield-era gap. The `bundle.cards` rendering (specified below) must not repeat this pattern — it has explicit rendering code.

This means `ContextBundle` gains one new field:

```python
@dataclass
class ContextBundle:
    # ... existing fields ...
    cards: list[FnRecord] = field(default_factory=list)  # NEW: populated from crawl.db
```

And `query_context()` adds a step: after collecting `transitive_deps` from the DAG, check if `.cw9/crawl.db` exists. If so, open a `CrawlStore` and look up each dep's UUID — attach the full `FnRecord` if it exists. This is the **only** code path that crosses the crawl.db ↔ dag.json boundary at query time.

**`format_prompt_context()` additions** for card rendering:

```python
# In format_prompt_context(), after the existing sections:
if bundle.cards:
    parts.append("## Existing Code Behavior (IN:DO:OUT Cards)\n")
    for card in bundle.cards:
        parts.append(f"### {card.function_name}")
        if card.class_name:
            parts.append(f" ({card.class_name})")
        parts.append(f" @ {card.file_path}:{card.line_number}\n")
        parts.append(f"**Claim:** {card.operational_claim}\n")
        if card.ins:
            parts.append("**IN:**\n")
            for inp in card.ins:
                dispatch_note = f" [{inp.dispatch}]" if inp.dispatch != "direct" else ""
                parts.append(f"- {inp.name}: {inp.type_str} ({inp.source}{dispatch_note})\n")
        parts.append(f"**DO:** {card.do_description}\n")
        if card.do_steps:
            for i, step in enumerate(card.do_steps, 1):
                parts.append(f"  {i}. {step}\n")
        if card.outs:
            parts.append("**OUT:**\n")
            for out in card.outs:
                parts.append(f"- {out.name}: {out.type_str} — {out.description}\n")
        if card.failure_modes:
            parts.append("**FAILURE MODES:** " + "; ".join(card.failure_modes) + "\n")
        parts.append("\n")
```

This renders each card as a compact, LLM-readable block. The format mirrors CW8.1's proven FN card layout.

---

## Data Models for CW9

### Design Decision: Pydantic vs Dataclass Boundary

The existing CW9 codebase uses `@dataclass` exclusively — zero Pydantic models exist. Introducing Pydantic everywhere would create inconsistency. However, **LLM output validation genuinely benefits from Pydantic**: the structured extraction prompts produce JSON that needs type coercion, field validation, and clear error messages for retry feedback.

**Decision:** Use Pydantic `BaseModel` **only** for models populated from LLM output: `InField`, `OutField`, `FnRecord`, `AxRecord`. All other models use `@dataclass` to match existing CW9 patterns. This creates a clean boundary: Pydantic at the LLM extraction boundary, dataclasses everywhere else.

**Dependency:** Add `pydantic>=2.0` to `pyproject.toml` under `[project.optional-dependencies]` as `crawl = ["pydantic>=2.0"]`. The crawl feature is the only consumer.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field as PydField, field_validator
import uuid as uuid_mod

# --- Enums (shared, standard library) ---

class InSource(str, Enum):
    PARAMETER = "parameter"
    STATE = "state"
    LITERAL = "literal"
    INTERNAL_CALL = "internal_call"
    EXTERNAL = "external"

class OutKind(str, Enum):
    OK = "ok"
    ERR = "err"
    SIDE_EFFECT = "side_effect"
    MUTATION = "mutation"

class DispatchKind(str, Enum):
    DIRECT = "direct"
    ATTRIBUTE = "attribute"
    DYNAMIC = "dynamic"
    OVERRIDE = "override"
    CALLBACK = "callback"
    PROTOCOL = "protocol"

class EntryType(str, Enum):
    HTTP_ROUTE = "http_route"
    CLI_COMMAND = "cli_command"
    PUBLIC_API = "public_api"
    EVENT_HANDLER = "event_handler"
    MAIN = "main"
    TEST = "test"

# --- Skeleton (pre-pass output, deterministic — @dataclass) ---

@dataclass
class SkeletonParam:
    name: str
    type: str = ""
    is_self: bool = False

@dataclass
class Skeleton:
    """Output of the language-specific scanner. Deterministic, no LLM involved."""
    function_name: str
    file_path: str
    line_number: int
    class_name: str | None = None    # NULL for top-level functions
    visibility: str = "public"
    is_async: bool = False
    params: list[SkeletonParam] = field(default_factory=list)
    return_type: str | None = None
    file_hash: str = ""

# --- IN:DO:OUT fields (LLM boundary — Pydantic BaseModel) ---

class InField(BaseModel):
    """Populated from LLM output. Pydantic validates structured extraction."""
    name: str
    type_str: str
    source: InSource
    source_uuid: str | None = None       # NULL during DFS, back-filled post-crawl
    source_file: str | None = None       # NULL allowed during extraction phase
    source_function: str | None = None
    source_description: str | None = None
    dispatch: DispatchKind = DispatchKind.DIRECT
    dispatch_candidates: list[str] | None = None

    @field_validator("source_uuid")
    @classmethod
    def validate_uuid_format(cls, v):
        if v is not None:
            uuid_mod.UUID(v)
        return v

    # NOTE: source_file is NOT validated as required for internal_call during
    # the extraction phase. The back-fill pass populates it after the full DFS.
    # Enforcement happens at CrawlStore.validate_completeness() post-crawl.

class OutField(BaseModel):
    """Populated from LLM output. Pydantic validates structured extraction."""
    name: OutKind
    type_str: str
    description: str = ""

# --- Core records (LLM boundary — Pydantic BaseModel) ---

class FnRecord(BaseModel):
    """Internal function behavioral record. Populated from LLM extraction.
    Pydantic is used here because this is the primary LLM output target
    and needs validation + clear error messages for retry feedback."""
    uuid: str
    function_name: str
    class_name: str | None = None        # NULL for top-level functions
    file_path: str
    line_number: int | None = None
    src_hash: str
    is_external: bool = False
    ins: list[InField]
    do_description: str
    do_steps: list[str] = PydField(default_factory=list)
    do_branches: str | None = None
    do_loops: str | None = None
    do_errors: str | None = None
    outs: list[OutField]
    failure_modes: list[str] = PydField(default_factory=list)
    operational_claim: str = ""
    skeleton: Skeleton | None = None
    schema_version: int = 1

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        uuid_mod.UUID(v)
        return v

class AxRecord(BaseModel):
    """External boundary record. Populated from LLM extraction for external calls."""
    uuid: str
    function_name: str
    file_path: str
    src_hash: str
    is_external: bool = True
    source_crate: str
    ins: list[InField]
    outs: list[OutField]
    boundary_contract: str
    schema_version: int = 1

# --- Non-LLM models (deterministic — @dataclass) ---

@dataclass
class MapNote:
    """Workflow structure linking FN cards into end-to-end paths.
    Deterministic computation, no LLM involved."""
    workflow_name: str
    entry_uuid: str
    path_uuids: list[str] = field(default_factory=list)
    shared_uuids: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)

@dataclass
class EntryPoint:
    """Entry point detected by the language-specific scanner.
    Deterministic detection, no LLM involved."""
    file_path: str
    function_name: str
    entry_type: EntryType
    route: str | None = None
    method: str | None = None

@dataclass
class TestReference:
    """Cross-reference between a test and the function it tests.
    Deterministic extraction from test files."""
    test_file: str
    test_function: str
    target_function: str
    target_file: str
    target_uuid: str | None = None
    inputs_observed: list[str] = field(default_factory=list)
    outputs_asserted: list[str] = field(default_factory=list)
    covers_error_path: bool = False
```

---

## CrawlStore Python API

The Python interface for `crawl.db`. This is the **only** code path that reads or writes crawl data — no raw SQL outside this class.

```python
from pathlib import Path
import sqlite3

class CrawlStore:
    """Python API for the crawl.db SQLite store.

    All methods operate within transactions. Records are committed
    per-function for crawl resumability.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open connection, enable WAL + foreign keys, create schema if needed."""

    def close(self) -> None:
        """Close the database connection."""

    # --- Record CRUD ---

    def insert_record(self, record: FnRecord) -> None:
        """Insert a new FnRecord. Raises on duplicate UUID."""

    def upsert_record(self, record: FnRecord) -> None:
        """Insert or replace a FnRecord by UUID. Used for incremental re-ingest."""

    def get_record(self, uuid: str) -> FnRecord | None:
        """Fetch a single record by UUID, with its ins and outs."""

    def get_records_for_file(self, file_path: str) -> list[FnRecord]:
        """Fetch all records for a given source file."""

    def get_all_records(self) -> list[FnRecord]:
        """Fetch all non-external records."""

    # --- Staleness ---

    def get_stale_records(self, current_hashes: dict[str, str]) -> list[str]:
        """Compare current file hashes against stored src_hash.
        Returns UUIDs of directly stale records (hash mismatch)."""

    def get_transitive_stale(self, direct_stale: list[str]) -> list[str]:
        """Propagate staleness transitively via the deps view recursive CTE.
        Returns all UUIDs that are stale (direct + transitive)."""

    # --- Subgraph extraction ---

    def get_forward_subgraph(self, function_name: str) -> list[FnRecord]:
        """Everything this function depends on (forward recursive CTE)."""

    def get_reverse_subgraph(self, function_name: str) -> list[FnRecord]:
        """Everything that depends on this function (reverse recursive CTE)."""

    def get_full_subgraph(self, function_name: str) -> list[FnRecord]:
        """Forward + reverse subgraph (complete neighborhood)."""

    # --- Back-fill ---

    def backfill_source_uuids(self) -> int:
        """Post-crawl pass: resolve source_function → source_uuid for all
        ins rows where source_uuid IS NULL AND source = 'internal_call'.
        Returns number of rows updated."""

    # --- Card rendering ---

    def get_card_text(self, uuid: str) -> str:
        """Render a markdown IN:DO:OUT card for a single record."""

    # --- Validation ---

    def validate_completeness(self) -> list[str]:
        """Post-crawl check: find internal_call ins with NULL source_file
        or NULL source_uuid. Returns list of warning messages."""

    # --- Crawl run tracking ---

    def start_crawl_run(self, target_path: str, language: str,
                        codebase_type: str | None, is_incremental: bool) -> int:
        """Record a new crawl run, return its ID."""

    def finish_crawl_run(self, run_id: int, created: int, updated: int,
                         skipped: int, failed: int) -> None:
        """Mark a crawl run as complete with counters."""

    # --- Entry points ---

    def insert_entry_point(self, ep: EntryPoint) -> None:
        """Insert an entry point record."""

    def get_entry_points(self) -> list[EntryPoint]:
        """Fetch all entry points."""

    # --- Test references ---

    def insert_test_ref(self, ref: TestReference) -> None:
        """Insert a test cross-reference."""

    def get_test_coverage(self) -> list[dict]:
        """Query the test_coverage view."""
```

## Next Steps

### Phase 1: Core Infrastructure
1. **Add `pydantic>=2.0` optional dependency** (`crawl` extras in pyproject.toml)
2. **Implement data models** (enums, Skeleton dataclass, InField/OutField/FnRecord Pydantic models, EntryPoint/MapNote/TestReference dataclasses, ~200 lines)
3. **Implement CrawlStore** (SQLite schema creation, all CRUD/query methods, ~300 lines)
4. **Add `remove_node()` to RegistryDag** (~10 lines in dag.py — `add_node` already upserts, no change needed)
5. **Extend `merge_registered_nodes()`** to accept `crawl_uuids` parameter (~15 lines in dag.py)
6. **Extend `cmd_register`/`_register_payload`** to accept `depends_on` edges on GWT entries (~20 lines in cli.py)

### Phase 2: Python Ingestion
7. **Implement the Python skeleton scanner** (`scan_file` + `scan_directory`, ~150 lines, pattern matching + indent tracking + class_name extraction)
8. **Implement entry point discovery for Python** (detect Flask/Django/FastAPI/Click/argparse/main, ~100 lines)
9. **Implement the DFS crawl orchestrator** (queue + visited set + LLM query loop + retry policy + source_uuid back-fill, ~400 lines)
10. **Implement the dag.json bridge** (crawl.db records → dag.json RESOURCE nodes + edges via `add_node`, ~100 lines)

### Phase 3: CLI + Pipeline Integration
11. **Wire `cw9 ingest` CLI command** (argparse subcommand, calls scanner → crawl → bridge, ~100 lines)
12. **Wire `cw9 stale` CLI command** (~30 lines)
13. **Wire `cw9 show --card` CLI command** (~30 lines)
14. **Extend `query_context()`** to load FnRecord cards from crawl.db for RESOURCE nodes in transitive_deps (~30 lines)
15. **Extend `format_prompt_context()`** to render `## Existing Code Behavior` section from `bundle.cards` (~40 lines)
16. **Update `cmd_extract`** to pass `crawl_uuids` to `merge_registered_nodes()` (~10 lines)

### Phase 4: Validation & GWT Authoring
17. **Prototype on a small target repo** (validate the full ingest → gwt-author → register → pipeline flow end-to-end)
18. **Implement `cw9 gwt-author`** (research notes + crawl.db → GWT JSON with `depends_on` piped to `cw9 register`, ~150 lines)

### Phase 5: Additional Languages
19. **Add TypeScript scanner** (after Python is proven)
20. **Add Go scanner** (after TypeScript)

## References

- CW8.1 brownfield spec: `~/Dev/CodeWriter8.1/specs/brownfield/brownfield-tlaplus-crawl.md`
- CW8.1 crawl paths: `~/Dev/CodeWriter8.1/paths/brownfield-crawl-*`
- CW8.1 DFS traversal: `~/Dev/CodeWriter8.1/paths/depth-first-provenance-crawl-record-indo-triples/v1.md`
- CW8.1 data structures: `~/Dev/CodeWriter8.1/src/auxiliary_types.rs`, `~/Dev/CodeWriter8.1/src/types.rs`
- CW8.1 source parser: `~/Dev/CodeWriter8.1/src/codegen/parse_source_code.rs`
- CW9 registry DAG: `~/Dev/CodeWriter9.0/python/registry/dag.py`
- CW9 pipeline: `~/Dev/CodeWriter9.0/python/registry/cli.py`
- CW9 context scoping: `~/Dev/CodeWriter9.0/python/registry/one_shot_loop.py` (query_context / ContextBundle)
- CW9 insight doc: `~/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/the-insight.md`
- CW9 brownfield roadmap mention: `~/Dev/CodeWriter9.0/thoughts/searchable/shared/handoffs/general/2026-03-10_07-54-05_projectcontext-refactor-and-flywheel-features.md`
