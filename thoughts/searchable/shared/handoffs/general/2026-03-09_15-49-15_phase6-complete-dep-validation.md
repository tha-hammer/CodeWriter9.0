---
date: 2026-03-09T15:49:15-04:00
researcher: claude-opus
git_commit: 2fe15a3
branch: master
repository: CodeWriter9.0
topic: "Phase 6 Complete — Dependency Validation (Second Pipeline-Built Feature)"
tags: [implementation, tla-plus, pluscal, dependency-validation, self-hosting, single-piece-flow, phase-6]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 6 Complete — Dependency Validation

## Task(s)

### Completed — Phase 6: Dependency Validation (Second Pipeline-Built Feature)

The second feature built entirely through the self-hosting pipeline is **dependency validation** — an edge pre-check (`validate_edge()`) that answers "can I safely add this edge without violating DAG invariants?"

**Single piece flow executed:**
1. Plain language requirement → 3 GWT behaviors (gwt-0015, gwt-0016, gwt-0017) registered in DAG
2. `run_dep_validation_loop.py` → LLM generated PlusCal spec via `claude-agent-sdk`
3. TLC verified: **762 distinct states, 0 violations, 6 invariants**
4. Bridge produced: 1 data_structure, 21 operations, 8 verifiers, 8 assertions
5. `generate_tests()` mechanically translated bridge artifacts → 21 pytest tests
6. `validate_edge()` implemented in `dag.py` → all 21 generated tests pass
7. Full suite: **213 tests pass** (192 existing + 21 generated)

**Three validation checks (matching the TLA+ spec):**
- **Acyclicity:** self-loops and reachability-based cycle detection
- **Duplicate rejection:** same (from, to, edge_type) triple already exists
- **Node-kind compatibility:** behavior→test and requirement→test `depends_on` edges are forbidden

### Next — Pick the third feature and run the same flow

The flywheel continues. The next agent should build another feature through the pipeline. Suggested features (in order of utility):

1. **Subgraph extraction** — "give me the minimal subgraph needed to understand node X." Combines forward and reverse closure. Useful for context-scoping LLM prompts.

2. **Change propagation** — "if I update the spec for node X, which tests need re-running?" Combines impact analysis with bridge artifact tracking. Requires bridge artifact tracking infrastructure that doesn't exist yet — may need to build that first.

## Critical References
- `BOOTSTRAP.md:626-661` — Phase 5 Self-Hosting definition (applies to all pipeline-built features)
- `python/run_dep_validation_loop.py` — Phase 6 loop script (latest template for future features)
- `python/run_impact_loop.py` — Phase 5 loop script (original template)

## Recent changes
- `python/registry/dag.py:10` — Added `ValidationResult` import
- `python/registry/dag.py:166-212` — Added `validate_edge()` method with `_KIND_INCOMPATIBLE` set
- `python/registry/types.py:117-122` — Added `ValidationResult` dataclass (valid, from_id, to_id, edge_type, reason)
- `python/registry/extractor.py:840-887` — Phase 6 self-registration (req-0005, gwt-0015..0017, depval-0001)
- `python/run_dep_validation_loop.py` — Full loop script: LLM call → TLC → bridge → test generation
- `python/tests/generated/test_dep_validation.py` — 21 mechanically generated tests
- `python/tests/generated/dep_validation_bridge_artifacts.json` — Bridge output
- `templates/pluscal/instances/dep_validation.tla` — LLM-generated, TLC-verified spec
- `templates/pluscal/instances/dep_validation.cfg` — TLC config
- `python/tests/test_one_shot_loop.py:382-385` — Updated DAG totals assertion (86 nodes, 158 edges)
- `schema/registry_dag.json` — Re-extracted DAG (86 nodes, 158 edges, 9 components)

## Learnings

### Spec converged on attempt 2
- Attempt 1: compiled and ran but violated `ValidEdgeAccepted` invariant (the happy-path invariant)
- Attempt 2: LLM self-corrected with counterexample feedback → 762 distinct states, all invariants hold
- The retry mechanism continues to be reliable — no manual intervention needed

### State space was manageable
- Despite the `with kf \in [1..NumNodes -> 0..NumKinds-1]` nondeterminism for kind assignment (3^4 = 81 branches), TLC only explored 762 distinct states with MaxSteps=12, NumNodes=4
- The concern about state space explosion was unfounded for these constants

### Node-kind compatibility is extensible
- `_KIND_INCOMPATIBLE` is a class-level set of `(from_kind, to_kind)` tuples on `RegistryDag`
- Adding new forbidden pairs (e.g., `(CONSTRAINT, TEST)`) is a one-line addition
- The kind check only applies to `depends_on` edges — other edge types are unconstrained

### depval-0001 does NOT depend on impact-0001
- Initial registration included a `depval-0001 → impact-0001` edge — this was removed
- `validate_edge()` uses `_can_reach()` (BFS on adjacency), not `query_impact()` (reverse closure)
- These are independent queries: validation = "is this edge safe?" vs impact = "who is affected?"

### Pipeline ground rules still hold
- LLM generated the spec, not the implementation agent
- Tests were mechanically generated from bridge verifiers
- Implementation was written solely to pass the generated tests

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/python/registry/dag.py` — DAG with `validate_edge()` and `query_impact()`
- `/home/maceo/Dev/CodeWriter9.0/python/registry/types.py` — `ValidationResult` dataclass
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Phase 6 self-registration
- `/home/maceo/Dev/CodeWriter9.0/python/run_dep_validation_loop.py` — Phase 6 loop script
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/test_dep_validation.py` — 21 generated tests
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/dep_validation_bridge_artifacts.json`
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/dep_validation.tla` — Verified spec
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/dep_validation.cfg`
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — 86 nodes, 158 edges

## Action Items & Next Steps

### IMMEDIATE: Pick the third feature and run the single piece flow

**For any feature, follow this exact flow:**
1. Express as 2-4 GWT behaviors
2. Register in `extractor.py:_self_describe()` (next IDs: req-0006, gwt-0018+)
3. Clone `run_dep_validation_loop.py` → `run_<feature>_loop.py`, update:
   - GWT ID to query
   - TLC config (CONSTANTS, INVARIANTS)
   - Prompt text (requirements, transitions, invariants)
   - `generate_tests()` function
4. Run: `python3 python/run_<feature>_loop.py`
5. Implement code to pass generated tests
6. Re-extract DAG, update test counts, commit

### Cleanup
- Temp files in project root can be cleaned: `dep_validation_llm_response*.txt`, `dep_validation_loop_output.log`, and Phase 5 temp files (`impact_llm_response*.txt`, `impact_loop_output.log`, `bridge_llm_response.txt`, `bridge_loop_output.log`)

### Commit pending
- All Phase 6 changes are uncommitted. Run `/commit` to commit before starting the next feature.

## Other Notes

### DAG state
- 86 nodes, 158 edges, 9 connected components
- Phase 6 added: req-0005, gwt-0015..0017, depval-0001 (5 nodes, 18 edges)

### Test counts
- 213 total tests passing
  - 43 bridge, 5 integration, 35 one-shot loop, 26 composer, 10 DAG, 25 extractor
  - 35 retroactive (Phase 4), 13 impact analysis (Phase 5), 21 dep validation (Phase 6)

### Pipeline commands
```bash
# Run any loop script
python3 python/run_dep_validation_loop.py

# Run all tests
cd python && python3 -m pytest tests/ -v

# Re-extract DAG
python3 -c "from registry.extractor import SchemaExtractor; e = SchemaExtractor(schema_dir='../schema/'); d = e.extract(); d.save('../schema/registry_dag.json')"

# Compile PlusCal → TLA+
java -cp tools/tla2tools.jar pcal.trans <file>.tla

# Verify with TLC
java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning
```

### Ground rule reminder
**The LLM generates specs, not the implementation agent.** If the LLM-generated spec fails TLC, send the error back through the retry loop. Never hand-write or hand-fix specs. Tests must be mechanically generated from bridge artifacts, not hand-written by reading JSON.
