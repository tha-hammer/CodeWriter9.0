# CodeWriter9.0 Memory

## Project Overview
Registry-driven pipeline for verified code generation using TLA+/PlusCal formal methods.
See `BOOTSTRAP.md` for the flywheel plan (Phases 0-5).

## Implementation Status
- **Phase 0: Extract the Graph** — COMPLETE (DAG engine, extractor)
- **Phase 1: First Templates** — COMPLETE (4 PlusCal templates, TLC verified)
- **Phase 2: Composition Engine** — COMPLETE (compose(spec_a, spec_b), TLC verified)
- **Phase 3: One-Shot Loop** — COMPLETE (OneShotLoop orchestrator, TLC verified)
- **Phase 4: The Bridge** — COMPLETE (4 translators, first real loop use, TLC verified)
  - DAG: 76 nodes, 122 edges, 9 components
  - Tests: 144 passing (43 bridge + 5 integration + 96 existing)

## Key Paths
- Schema files: `schema/*.json` (4 schema files + resource registry + extracted DAG)
- Rust crate: `crates/registry-core/`
- Python package: `python/registry/` (types, dag, extractor, composer, one_shot_loop, bridge)
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

## Next: Phase 5+
Full pipeline from requirements → specs → verified code artifacts.
