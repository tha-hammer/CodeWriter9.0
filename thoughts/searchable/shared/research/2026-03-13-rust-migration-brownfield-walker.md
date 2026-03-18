---
date: 2026-03-13T18:00:00-05:00
researcher: claude-opus
git_commit: 66c4f88
branch: feature/brownfield-code-walker
repository: CodeWriter9.0
topic: "Rust Migration: Brownfield Walker File & Database Operations"
tags: [research, rust, pyo3, sqlite, scanner, crawl-store, migration, brownfield]
status: complete
last_updated: 2026-03-13
last_updated_by: claude-opus
---

```
┌───────────────────────────────────────────────────────────────────┐
│       Rust Migration: Brownfield Walker File & DB Operations      │
│                    Status: COMPLETE | 2026-03-13                  │
└───────────────────────────────────────────────────────────────────┘
```

# Research: Moving Brownfield Walker File & DB Operations to Rust

**Date**: 2026-03-13T18:00:00-05:00
**Researcher**: claude-opus
**Git Commit**: `66c4f88`
**Branch**: `feature/brownfield-code-walker`
**Repository**: CodeWriter9.0

## Research Question

The brownfield code walker TDD plan (`2026-03-13-tdd-brownfield-walker-remaining.md`) was implemented entirely in Python. Can the file and database operations be moved to Rust for performance and correctness? Is there an existing pattern in `~/Dev/CodeWriter8.1` to model or re-use?

## Summary

**CW8.1 has no PyO3, no SQLite, and no Python-Rust bridge.** It is a pure Rust CLI binary (`silmari`) that uses JSON persistence and hand-rolled source parsing. There is no existing FFI pattern to re-use.

**CW9 already has a Rust workspace** with a single crate (`registry-core`) providing the DAG engine, but no PyO3 bridge exists. The crate uses `serde`, `serde_json`, and `thiserror` — no database or file-walking dependencies.

The Python brownfield walker has two clear categories of operations suitable for Rust migration:

| Category | Python Source | Hot Path? | Rust Benefit |
|---|---|---|---|
| **File scanning** | `scanner_python.py` (dir walk, regex parse, SHA-256) | Yes — runs on every file | 5-20x throughput on large codebases |
| **SQLite store** | `crawl_store.py` (CRUD, recursive CTE, staleness) | Yes — per-function I/O | Compile-time SQL safety, connection pooling |
| **Body reading** | `crawl_orchestrator.py:_read_function_body` | Yes — per-extraction | Minimal gain (single `read_to_string`) |

---

## Detailed Findings

### 1. CW8.1: No Reusable Bridge Pattern

<details>
<summary>Full CW8.1 analysis</summary>

CodeWriter8.1 (`silmari`) is a **pure Rust binary**. The Cargo.toml has zero FFI-related dependencies:

```toml
# ~/Dev/CodeWriter8.1/Cargo.toml — no pyo3, no rusqlite
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
thiserror = "2"
uuid = { version = "1", features = ["v4", "serde"] }
reqwest = { version = "0.12", features = ["json", "blocking"] }
clap = { version = "4", features = ["derive"] }
dotenvy = "0.15"
regex = "1.12.3"
```

| Feature | Status |
|---|---|
| PyO3 / `#[pyfunction]` | **Not present** |
| SQLite (rusqlite / diesel / sqlx) | **Not present** — JSON files only |
| Tree-sitter | **Not present** — hand-rolled brace-depth parser |
| Maturin / setuptools-rust | **Not present** |
| Python calling into Rust | **Not present** |

**Reusable patterns** (structural, not code-level):

1. **Hand-rolled source parsing** — `parse_source_code.rs` uses brace-depth tracking and keyword dispatch tables. CW9's `scanner_python.py` uses the same approach (indent tracking, regex matching). A Rust port would follow the same shape.

2. **Atomic file writes** — `persistence.rs:76-90` writes to `.tmp` then renames. Worth adopting for `crawl_store.py` journal safety.

3. **Recursive dir walk** — `python_emitter.rs:472-486` uses raw `std::fs::read_dir` with manual recursion. A Rust port should prefer `walkdir` crate instead.

</details>

---

### 2. CW9: Existing Rust Infrastructure

The workspace at `/home/maceo/Dev/CodeWriter9.0/Cargo.toml` has one member crate:

```
crates/registry-core/
├── Cargo.toml          # serde, serde_json, thiserror — no pyo3
└── src/
    ├── lib.rs          # Re-exports RegistryDag + types
    ├── types.rs        # NodeId, NodeKind, Node, Edge, EdgeType, QueryResult
    ├── dag.rs          # RegistryDag (BTreeMap-backed DAG with closure + components)
    └── error.rs        # RegistryError enum via thiserror
```

The `RegistryDag` is the same DAG that `crawl_bridge.py` populates from the crawl store's `deps` view. Currently, the Python side uses its own JSON-file-backed DAG class (`python/registry/dag.py`), not the Rust crate. The Rust crate is standalone with no Python integration.

---

### 3. Python Operations Targeted for Migration

#### 3a. File Scanner (`scanner_python.py`)

**What it does**: Walks `*.py` files via `Path.rglob`, reads each with `read_text`, computes SHA-256, and emits `Skeleton` objects using three compiled regexes (`_DEF_RE`, `_CLASS_RE`, `_RETURN_TYPE_RE`).

**Operations for Rust**:

| Operation | Python Implementation | Rust Equivalent |
|---|---|---|
| Directory walk | `Path.rglob("*.py")` | `walkdir` crate with extension filter |
| File read | `path.read_text(encoding="utf-8", errors="replace")` | `std::fs::read_to_string` + lossy UTF-8 |
| SHA-256 hash | `hashlib.sha256(text.encode()).hexdigest()` | `sha2` crate (or `ring`) |
| Regex scanning | 3 compiled `re` patterns, line-by-line | `regex` crate (already in CW8.1) |
| Indent/class tracking | Manual `class_stack` with indent levels | Same logic, stack of `(String, usize)` |
| Parameter parsing | Bracket-depth comma splitting | Same logic, byte-level scan |

**Data returned**: `Vec<Skeleton>` — a flat list of function metadata. This is pure data, no database involvement.

**Estimated gain**: For a codebase with 1000+ Python files, the Rust scanner would be 5-20x faster due to:
- No Python GIL for file I/O
- Regex compiled once at startup (Rust `regex` is already very fast)
- SHA-256 via native instructions
- Zero-copy string slicing

#### 3b. Crawl Store (`crawl_store.py`)

**What it does**: Full SQLite CRUD for the `records`, `ins`, `outs`, `maps`, `test_refs`, `entry_points`, and `crawl_runs` tables. Includes recursive CTE queries for staleness and subgraph traversal.

**Schema** (7 tables, 4 views, 9 indexes):

| Table | Key Operations |
|---|---|
| `records` | insert, upsert (delete+insert), get by UUID, get by file, get all |
| `ins` | insert with ordinal, join for deps view |
| `outs` | insert with ordinal |
| `maps` | insert or replace |
| `test_refs` | insert or replace |
| `entry_points` | insert or replace |
| `crawl_runs` | start/finish lifecycle |

**Critical queries**:

1. **`backfill_source_uuids()`** — single UPDATE with scalar subquery resolving function names to UUIDs
2. **`get_transitive_stale()`** — recursive CTE walking the dependency graph forward
3. **`get_forward_subgraph()` / `get_reverse_subgraph()`** — recursive CTEs on `ins.source_uuid`
4. **`validate_completeness()`** — finds unresolved `internal_call` references

**Rust options for SQLite**:

| Crate | Approach | Trade-off |
|---|---|---|
| `rusqlite` | Direct C binding, raw SQL strings | Fastest, most control, no compile-time SQL checks |
| `sqlx` | Async, compile-time verified SQL | Better safety, but async adds complexity for PyO3 |
| `diesel` | ORM with compile-time schema | Heavy, probably overkill for this use case |

**Recommendation**: `rusqlite` — it mirrors the current Python `sqlite3` usage most closely, and the recursive CTEs translate directly.

#### 3c. Function Body Reader (`crawl_orchestrator.py:_read_function_body`)

**What it does**: `Path(file_path).read_text()` then slices from `line_number`. Single function, ~15 lines.

**Rust benefit**: Minimal. This is a single file read per extraction — the LLM call that follows dominates by orders of magnitude. Not worth migrating independently; it would naturally come along if the orchestrator moves.

---

### 4. Bridge Architecture: PyO3 + Maturin

Since CW8.1 has no existing bridge pattern, a new one must be established. The standard approach:

```
┌─────────────────────────┐
│   Python (orchestrator)  │  crawl_orchestrator.py — DFS logic, LLM injection
│   calls into Rust via    │  gwt_author.py — LLM-dependent
│   native extension       │  cli.py — argument parsing
├─────────────────────────┤
│   PyO3 Bridge Layer      │  New: crates/crawl-core/src/py_bridge.rs
│   #[pyclass] + #[pyfn]   │  Exposes: scan_directory(), CrawlDb, Skeleton
├─────────────────────────┤
│   Pure Rust Core         │  New: crates/crawl-core/src/{scanner,store,types}.rs
│   rusqlite + walkdir     │  File I/O, SQLite, hashing — no Python dependency
│   + sha2 + regex         │
└─────────────────────────┘
```

#### Proposed Crate: `crawl-core`

```toml
# crates/crawl-core/Cargo.toml
[package]
name = "crawl-core"
version = "0.1.0"
edition = "2021"

[lib]
name = "crawl_core"
crate-type = ["cdylib", "rlib"]   # cdylib for Python extension, rlib for Rust tests

[dependencies]
pyo3 = { version = "0.23", features = ["extension-module"] }
rusqlite = { version = "0.33", features = ["bundled"] }
walkdir = "2"
sha2 = "0.10"
regex = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2"
uuid = { version = "1", features = ["v4", "v5"] }

[dev-dependencies]
tempfile = "3"
```

#### PyO3 Bridge Surface

```rust
// Conceptual — what Python calls

#[pyclass]
struct Skeleton { ... }              // Mirrors crawl_types.Skeleton

#[pyclass]
struct CrawlDb { ... }               // Wraps rusqlite::Connection

#[pyfunction]
fn scan_directory(root: &str, excludes: Vec<String>) -> Vec<Skeleton>;

#[pymethods]
impl CrawlDb {
    #[new]
    fn new(path: &str) -> PyResult<Self>;
    fn insert_record(&self, ...) -> PyResult<()>;
    fn upsert_record(&self, ...) -> PyResult<()>;
    fn get_record(&self, uuid: &str) -> PyResult<Option<FnRecord>>;
    fn get_stale_records(&self, hashes: HashMap<String, String>) -> PyResult<Vec<String>>;
    fn get_transitive_stale(&self, stale: Vec<String>) -> PyResult<Vec<String>>;
    fn backfill_source_uuids(&self) -> PyResult<u64>;
    // ... etc
}
```

#### Build Integration

```toml
# pyproject.toml addition
[tool.maturin]
module-name = "registry._crawl_core"
features = ["pyo3/extension-module"]
```

Python import:
```python
from registry._crawl_core import scan_directory, CrawlDb, Skeleton
```

---

### 5. Migration Strategy: Phases

```
╔═══════════════════════════════════════════════════════╗
║  Phase A: Scanner Only (lowest risk, highest gain)    ║
╚═══════════════════════════════════════════════════════╝
```

Move `scan_file()` and `scan_directory()` to Rust. Python `scanner_python.py` becomes a thin wrapper that calls into the Rust extension. All existing tests pass unchanged — the `Skeleton` dataclass is replaced with a PyO3 `#[pyclass]`.

**Why start here**: No database involvement, pure function (path in, skeletons out), easy to verify, biggest perf win.

```
╔═══════════════════════════════════════════════════════╗
║  Phase B: CrawlStore (higher complexity)              ║
╚═══════════════════════════════════════════════════════╝
```

Move the SQLite layer to `rusqlite`. The `CrawlStore` context manager becomes a `#[pyclass]` with `__enter__`/`__exit__` mapped to `connect()`/`close()`. All 7 tables and 4 views migrate. Recursive CTEs translate directly to rusqlite prepared statements.

**Key risk**: `FnRecord` is a Pydantic model used for LLM output validation. The Rust `#[pyclass]` version cannot use Pydantic validators. Options:
1. Keep `FnRecord` as Pydantic in Python, convert at the bridge boundary
2. Add validation logic in Rust (field validators as methods)
3. Accept raw dicts from Rust and validate in Python before storing

Option 1 is safest — the LLM-facing code stays in Python, only the storage layer moves.

```
╔═══════════════════════════════════════════════════════╗
║  Phase C: RegistryDag unification (optional)          ║
╚═══════════════════════════════════════════════════════╝
```

The existing `registry-core` Rust crate already implements `RegistryDag`. Currently the Python side has its own `dag.py`. Phase C would expose `registry-core` via PyO3 so that `crawl_bridge.py` populates the Rust DAG directly, eliminating the Python DAG duplicate.

---

## Code References

| Component | File | Key Lines |
|---|---|---|
| Python scanner | `python/registry/scanner_python.py` | `scan_file:112`, `scan_directory:210` |
| Python crawl store | `python/registry/crawl_store.py` | Schema DDL `:28`, `insert_record:250`, recursive CTEs `:400-450` |
| Python orchestrator body read | `python/registry/crawl_orchestrator.py` | `_read_function_body:32` |
| Python crawl types | `python/registry/crawl_types.py` | `Skeleton:70`, `FnRecord:134`, `make_record_uuid:21` |
| CW9 Rust DAG | `crates/registry-core/src/dag.rs` | `RegistryDag:8`, `add_edge:41` |
| CW9 Rust types | `crates/registry-core/src/types.rs` | `Node:57`, `Edge:226` |
| CW8.1 source parser | `~/Dev/CodeWriter8.1/src/codegen/parse_source_code.rs` | `parse_source_code:7`, `extract_brace_body:63` |
| CW8.1 persistence | `~/Dev/CodeWriter8.1/src/persistence.rs` | `save_schema:37` (atomic write pattern) |
| CW8.1 dir walk | `~/Dev/CodeWriter8.1/src/codegen/python_emitter.rs` | `find_py_files:472` |

## Architecture Documentation

### Current State
```
Python-only pipeline:
  scanner_python.py  ──→  crawl_store.py (SQLite)  ──→  crawl_orchestrator.py
       ↓                        ↓                              ↓
  Skeleton objects         FnRecord CRUD              LLM extraction + DFS
                           recursive CTEs
                           staleness checks
```

### Proposed State (after Phase A+B)
```
Python orchestration layer:
  crawl_orchestrator.py  ──→  gwt_author.py  ──→  cli.py
       ↓ (calls into Rust)          ↓ (pure Python, LLM-facing)
  ┌────────────────────────────────────────────────┐
  │  Rust extension (crawl-core via PyO3/maturin)  │
  │  scan_directory()  →  CrawlDb  →  Skeleton     │
  │  walkdir + regex   │  rusqlite │  #[pyclass]    │
  │  sha2              │  CTEs     │                │
  └────────────────────────────────────────────────┘
```

## Historical Context (from thoughts/)

- `thoughts/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md` — Original research document establishing the brownfield walker design. Section "Prior Art: CW8.1 Brownfield Crawl" references CW8.1's `parse_source_code.rs` as inspiration for the scanner approach.
- `thoughts/shared/plans/2026-03-13-tdd-brownfield-walker-remaining.md` — TDD plan for the four remaining Python components (orchestrator, gwt-author, TS scanner, Go scanner). Explicitly defers "Rust skeleton scanner" as out-of-scope.

## Open Questions

1. **TypeScript/Go scanners too?** The TDD plan includes `scanner_typescript.py` and `scanner_go.py`. If the Python scanner moves to Rust, should the TS/Go scanners be born in Rust directly? (Likely yes — the `regex` crate handles all three languages.)

2. **Maturin vs setuptools-rust?** Maturin is simpler and more modern. The project already uses `pyproject.toml`. Maturin is the recommended choice.

3. **tree-sitter alternative?** Neither CW8.1 nor CW9 uses tree-sitter. The hand-rolled regex+indent approach works for skeleton extraction (function signatures only, not full AST). Tree-sitter would be more robust for complex nesting but adds a build dependency per language grammar. Worth evaluating for Phase A if accuracy issues emerge.

4. **Async rusqlite?** The crawl orchestrator is currently synchronous. If it becomes async (for parallel crawl), `rusqlite` works fine from a sync context called by `tokio::task::spawn_blocking`. No need for `sqlx` unless the orchestrator itself moves to Rust.

5. **Pydantic at the boundary?** `FnRecord` uses Pydantic `@field_validator` decorators for UUID and enum validation. These cannot run inside Rust. The cleanest boundary is: Rust returns dicts, Python validates via Pydantic before the LLM loop, Rust stores the validated result as raw fields.
