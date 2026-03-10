# CodeWriter9.0 Memory

## Project Overview
Registry-driven pipeline for verified code generation using TLA+/PlusCal formal methods.
See `BOOTSTRAP.md` for the flywheel plan (Phases 0-5).

## Implementation Status
- **Phase 0-4** — ALL COMPLETE (DAG, templates, composer, loop, bridge)
- **Phase 5: Self-Hosting** — COMPLETE (first pipeline-built feature: impact analysis)
- **Phase 6: Dependency Validation** — COMPLETE (second pipeline-built feature)
  - `validate_edge()` pre-checks acyclicity, duplicates, node-kind compatibility
  - IDs: req-0005, gwt-0015/0016/0017, depval-0001
- **Phase 7: Subgraph Extraction** — COMPLETE (third pipeline-built feature)
  - `extract_subgraph()` returns forward+reverse closure + induced edges
  - IDs: req-0006, gwt-0018/0019/0020, subgraph-0001
- **Phase 8: Change Propagation** — COMPLETE (fourth pipeline-built feature)
  - DAG: 96 nodes, 198 edges, 9 components
  - Tests: 250 passing (233 prev + 17 generated change propagation)
  - `query_affected_tests()` returns test file paths affected by a node change
  - Uses `test_artifacts: dict[str, str]` on RegistryDag (not a Node field)
  - IDs: req-0007, gwt-0021/0022/0023, chgprop-0001
  - TLC verified attempt 2: 1,349,968 distinct states, 5 invariants

## Key Paths
- Schema files: `schema/*.json` (4 schema files + resource registry + extracted DAG)
- Rust crate: `crates/registry-core/`
- Python package: `python/registry/` (types, dag, extractor, composer, one_shot_loop, bridge)
- Loop scripts: `python/run_impact_loop.py` (template for new features), `python/run_bridge_loop.py`
- Python tests: `python/tests/` (test_dag, test_extractor, test_composer, test_one_shot_loop, test_bridge, test_loop_bridge_integration)
- PlusCal specs: `templates/pluscal/instances/` (registry_crud, composition_engine, one_shot_loop, bridge_translator)
- TLA+ tools: `tools/tla2tools.jar` (Java 21 required)

## Tech Stack
- Rust + Python dual implementation
- Python 3.13, pytest for testing; use `python3` not `python`
- PlusCal → TLA+ → TLC formal verification pipeline
- `java -cp tools/tla2tools.jar pcal.trans <file>.tla` (compile)
- `java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning` (verify)

## Architecture Decisions
- Monotonic growth: nodes never deleted, only superseded
- Conform-or-die: new behaviors must conform to existing specs
- LLM writes PlusCal only; system composes TLA+
- Templates over raw generation (4 templates: CRUD, state machine, queue, auth)
- Bridge is mechanical, not LLM-driven
- OneShotLoop does NOT call LLM — caller handles LLM interaction
- TLA+ module name MUST match filename (TLC constraint)

## Pipeline Ground Rules
- LLM generates specs, not the implementation agent. Never hand-write/fix specs.
- Tests are mechanically generated from bridge artifacts, not hand-written.
- On TLC failure, send errors back through the retry loop (up to 5 attempts).
- Bridge needs compiled TLA+ (after pcal.trans), not raw PlusCal.
- `LoopStatus.compiled_spec_path` exposes the compiled file.

## Single Piece Flow (proven across 4 features)
1. Add GWT behaviors + requirement to `extractor.py:_self_describe()`
2. Clone latest loop script (`run_change_prop_loop.py`), update module/GWT/config/prompt/generate_tests
3. Run loop: `python3 python/run_<feature>_loop.py`
4. Implement feature in `dag.py` to pass generated tests (implementation comes LAST)
5. Wire serialization, populate `test_artifacts`, re-extract DAG, update test totals
Next IDs: req-0008, gwt-0024+.
