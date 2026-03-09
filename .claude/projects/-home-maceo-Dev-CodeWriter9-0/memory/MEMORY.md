# CodeWriter9.0 Memory

## Project Overview
Registry-driven pipeline for verified code generation using TLA+/PlusCal formal methods.
See `BOOTSTRAP.md` for the flywheel plan (Phases 0-5).

## Implementation Status
- **Phase 0: Extract the Graph** — COMPLETE
  - Rust core: `crates/registry-core/` (DAG engine, 10 tests pass)
  - Python: `python/registry/` (DAG + extractor, 35 tests pass)
  - Extracted DAG: `schema/registry_dag.json` (50 nodes, 48 edges, 15 components)
  - Self-description: req-0001, gwt-0001..0004, res-0001..0004 registered

## Key Paths
- Schema files: `schema/*.json` (4 schema files + resource registry + extracted DAG)
- Rust crate: `crates/registry-core/` (types, dag, error modules)
- Python package: `python/registry/` (types, dag, extractor modules)
- Python tests: `python/tests/` (test_dag.py, test_extractor.py)
- Architecture docs: `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md`
- Vision doc: `thoughts/searchable/shared/docs/the-insight.md`

## Tech Stack
- Rust + Python dual implementation
- Claude Agent SDK for LLM orchestration (Phase 3+)
- Python 3.13, pytest for testing
- Use `python3` not `python` on this system

## Architecture Decisions
- Monotonic growth: nodes never deleted, only superseded
- Conform-or-die: new behaviors must conform to existing specs
- LLM writes PlusCal only; system composes TLA+
- Templates over raw generation (4 templates: CRUD, state machine, queue, auth)
- Bridge is mechanical, not LLM-driven

## Next: Phase 1 — First Templates
Build CRUD PlusCal template, apply to registry's own GWT behaviors, verify with TLC.
