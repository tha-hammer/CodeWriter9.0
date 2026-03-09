---
date: 2026-03-09T10:40:51-04:00
researcher: claude-opus
git_commit: (no commits yet — master branch, uncommitted)
branch: master
repository: CodeWriter9.0
topic: "Phase 1: First Templates — CRUD PlusCal Template for Registry"
tags: [implementation, tla-plus, pluscal, crud-template, bootstrap, phase-1, single-piece-flow]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 0 Complete → Phase 1 First Templates

## Task(s)

### Completed
1. **Phase 0: Extract the Graph** — Fully implemented in Rust and Python.
   - Rust core DAG engine (`crates/registry-core/`) with cycle rejection, transitive closure, connected components, query_relevant, JSON serialization. 10 tests pass.
   - Python DAG + extractor (`python/registry/`) with schema parsing from all 4 schema files, edge extraction per BOOTSTRAP.md map, self-description. 35 tests pass.
   - Extracted DAG saved to `schema/registry_dag.json`: 50 nodes, 48 edges, 15 connected components.
   - Self-description: req-0001, gwt-0001..0004, res-0001..0004 all registered with correct edges.
   - BOOTSTRAP.md updated with Phase 0 completion status and implementation details.

### Next Step (Single Piece Flow)
**Phase 1: First Templates.** Build the CRUD PlusCal template and apply it to the registry's own GWT behaviors (gwt-0001..0004). Compile PlusCal → TLA+, run TLC model checker. This is the flywheel's first real turn: a tool we build (CRUD template) verifies a tool we built earlier (registry).

## Critical References
- `BOOTSTRAP.md` — Phase 1 section (lines ~246-303) defines CRUD template structure, the bootstrap act (apply to registry), and expected TLC invariants
- `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — TLA+ composition mechanics, PlusCal/TLA+ layer separation, template library design (lines ~594-667)

## Recent changes
- Created: `crates/registry-core/src/types.rs` — Rust type definitions (NodeId, Node, Edge, EdgeType, etc.)
- Created: `crates/registry-core/src/dag.rs` — Rust DAG engine with full test suite
- Created: `crates/registry-core/src/error.rs` — Error types
- Created: `crates/registry-core/src/lib.rs` — Public API
- Created: `crates/registry-core/Cargo.toml` — Crate config
- Created: `Cargo.toml` — Workspace root
- Created: `python/registry/types.py` — Python type dataclasses
- Created: `python/registry/dag.py` — Python DAG implementation
- Created: `python/registry/extractor.py` — Schema edge extractor
- Created: `python/registry/__init__.py` — Package init
- Created: `python/pyproject.toml` — Python project config
- Created: `python/tests/test_dag.py` — 14 DAG unit tests
- Created: `python/tests/test_extractor.py` — 21 extractor integration tests
- Created: `schema/registry_dag.json` — Extracted DAG output
- Updated: `BOOTSTRAP.md` — Phase 0 checklist marked complete, implementation details added after Phase 0 section

## Learnings

### The extracted graph is real and substantial
The largest connected component (component-10) has 26 members spanning all 4 schema layers (backend, frontend, middleware, shared). Cross-layer edges are working: frontend data_loaders reference backend endpoints, middleware interceptors implement shared interfaces, processors import shared types. The graph is acyclic (verified by test).

### Edge type distribution
48 edges break down as: imports(13), references(14), calls(2), chains(2), validates(4), decomposes(4), contains(1), depends_on(1), filters(1), guards(1), handles(1), implements_interface(1), loads(1), transforms_from(1), transforms_to(1). Imports and references dominate because the schemas are templates showing structural patterns.

### Schema files are templates, not instances
The 4 schema files define resource TYPE shapes (e.g., "ProcessorName", "EndpointName" as placeholders). Edge extraction works at the type level — we extract that "a processor imports shared types" as an edge from db-b7r2 → cfg-f7s8. Instance-level edges (specific processor A imports specific type B) will come when real project data populates these schemas.

### Python test runner
Use `python3` (not `python`) on this system. Tests run from `python/` directory: `python3 -m pytest tests/ -v`.

### Rust workspace
Workspace root at project root (`Cargo.toml`), single member `crates/registry-core`. Run `cargo test` from project root.

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/BOOTSTRAP.md` — Updated with Phase 0 completion (lines ~243-270 for implementation details)
- `/home/maceo/Dev/CodeWriter9.0/crates/registry-core/src/types.rs` — Rust types
- `/home/maceo/Dev/CodeWriter9.0/crates/registry-core/src/dag.rs` — Rust DAG engine + 10 tests
- `/home/maceo/Dev/CodeWriter9.0/crates/registry-core/src/error.rs` — Error types
- `/home/maceo/Dev/CodeWriter9.0/crates/registry-core/src/lib.rs` — Public API
- `/home/maceo/Dev/CodeWriter9.0/python/registry/types.py` — Python types
- `/home/maceo/Dev/CodeWriter9.0/python/registry/dag.py` — Python DAG
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Edge extractor
- `/home/maceo/Dev/CodeWriter9.0/python/tests/test_dag.py` — DAG tests
- `/home/maceo/Dev/CodeWriter9.0/python/tests/test_extractor.py` — Extractor tests
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — Extracted DAG (50 nodes, 48 edges)
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — Full architectural plan
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/the-insight.md` — Core vision document

## Action Items & Next Steps

### IMMEDIATE: Phase 1 — First Templates (Single Piece Flow)

The next agent should execute Phase 1 from `BOOTSTRAP.md`. Here is the single piece flow:

**Step 1: Build the CRUD PlusCal template.**
From BOOTSTRAP.md lines ~276-292, the CRUD template applied to the registry should have:
- State: set of nodes, set of edges
- Actions: AddNode(id, kind, content), AddEdge(from, to, type), RemoveEdge(from, to), QueryContext(resource_id)
- Invariants: AcyclicGraph, ClosureCorrect, ComponentsValid, UUIDFormat
Write this as a PlusCal algorithm with fill-in markers where domain-specific parameters go.

**Step 2: Fill in the template for the registry.**
Apply the CRUD template to gwt-0001 through gwt-0004 (the registry's own behaviors). The behaviors are already in the DAG at `schema/registry_dag.json` and defined in `python/registry/extractor.py:_self_describe()`.

**Step 3: Compile PlusCal → TLA+.**
Use the TLA+ toolbox's `pcal` translator. The project already has `silmari verify-path` and `.claude/commands/extract_tlaplus_model.md` (288 lines) as reference for TLA+ workflow.

**Step 4: Run TLC model checker.**
Bounded checking (depth 5) for interactive speed. Verify AcyclicGraph, ClosureCorrect, ComponentsValid invariants hold under all interleavings of AddNode/AddEdge.

**Step 5: Activate `fs-x7p6` (tla_artifact_store).**
Move it from `conditional_resources` to `resources` in the registry. Store the generated TLA+ specs there.

**Step 6: Register Phase 1's own components.**
The CRUD template, the PlusCal compiler step, and the TLC runner should be registered as nodes in the DAG, continuing the self-description pattern.

### THEN: Phase 2 — Composition Engine
After Phase 1 is solid, build `compose(spec_a, spec_b)` and verify it via state machine template. See `BOOTSTRAP.md` Phase 2.

## Other Notes

### Tech stack decisions
- **Rust + Python dual implementation** — Rust for core graph engine performance, Python for schema parsing/orchestration
- **Claude Agent SDK** for LLM orchestration (needed starting Phase 3 for the one-shot loop)
- No commits have been made yet — all work is uncommitted on master branch

### TLA+ tooling references
- `.claude/commands/extract_tlaplus_model.md` — Existing 288-line command for extracting TLA+ from code
- `.claude/commands/plan_path.md` — Path planning with resource registry references
- `silmari verify-path` — TLA+ verification command
- `.silmari/` directory exists for checkpoint/history storage

### The 4 PlusCal templates (from plan)
1. **CRUD** ← modeled after `data_structures` + `data_access_objects` — Phase 1 target
2. **State machine** ← modeled after `execution_patterns` — Phase 2 target
3. **Queue/pipeline** ← modeled after `process_chains` — Phase 3
4. **Auth/session** ← modeled after `security` + `access_controls` — Phase 3

### Key architectural principle for Phase 1
LLM writes PlusCal ONLY. The system handles compilation to TLA+ and composition. Counterexamples translate back up to PlusCal-level language. The template should have clear fill-in markers that separate what the LLM fills (domain parameters) from what the system handles (syntax, composition).
