---
date: 2026-03-10T06:51:35-04:00
researcher: claude-opus
git_commit: 650d82b
branch: master
repository: CodeWriter9.0
topic: "Phase 8 Complete — Change Propagation; Single Piece Flow Fully Operational"
tags: [implementation, tla-plus, pluscal, change-propagation, self-hosting, single-piece-flow, phase-8]
status: complete
last_updated: 2026-03-10
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 8 Complete — Change Propagation (`query_affected_tests`)

## Task(s)

### Completed — Phase 8: Change Propagation (Fourth Pipeline-Built Feature)

The fourth feature built through the self-hosting pipeline is **change propagation** — `query_affected_tests(node_id) → list[str]` returning the file paths of test files affected by a change to the target node.

**Single piece flow executed:**
1. Plain language requirement → 3 GWT behaviors (gwt-0021, gwt-0022, gwt-0023) registered in DAG
2. `run_change_prop_loop.py` → LLM generated PlusCal spec via `claude-agent-sdk`
3. TLC verified on **attempt 2** (attempt 1 failed: label inside `with`): **2,312,842 states (1,349,968 distinct), 0 violations, 5 invariants**
4. Bridge produced: 1 data_structure, 18 operations, 5 verifiers, 5 assertions
5. `generate_tests()` mechanically translated bridge artifacts → 17 pytest tests
6. `query_affected_tests()` implemented in `dag.py` → all 17 generated tests pass
7. Full suite: **250 tests pass** (233 existing + 17 generated)

### Critical process learning — correct pipeline order

The implementation agent initially tried to implement `query_affected_tests()` and `test_artifacts` dict **before** running the LLM loop. The user corrected this:

**Correct order:** GWT registration → loop script → run loop (LLM → TLC → bridge → test gen) → **then** implement to pass the generated tests. The implementation comes last, driven by the tests, not the other way around.

## Critical References
- `BOOTSTRAP.md:626-661` — Phase 5 Self-Hosting definition (applies to all pipeline-built features)
- `python/run_change_prop_loop.py` — Phase 8 loop script (latest template)
- `thoughts/searchable/shared/handoffs/general/2026-03-09_18-15-14_phase7-complete-subgraph-extraction.md` — Previous handoff

## Recent changes

- `python/registry/dag.py:30` — Added `test_artifacts: dict[str, str]` to `RegistryDag.__init__`
- `python/registry/dag.py:241-257` — Added `query_affected_tests()` method (impact set + artifact lookup)
- `python/registry/dag.py:298-301` — Wired `test_artifacts` into `to_dict()` serialization
- `python/registry/dag.py:335` — Wired `test_artifacts` into `from_dict()` deserialization
- `python/registry/extractor.py:949-999` — Phase 8 self-registration (req-0007, gwt-0021..0023, chgprop-0001)
- `python/registry/extractor.py:1001-1006` — `test_artifacts` mapping populated for all 4 pipeline features
- `python/tests/test_one_shot_loop.py:382-385` — Updated DAG totals assertion (96 nodes, 198 edges)
- `schema/registry_dag.json` — Re-extracted DAG (96 nodes, 198 edges, 9 components)

## Learnings

### Spec failed attempt 1 with "label in `with`" — common PlusCal pitfall
- The LLM placed a label inside a `with` statement on attempt 1
- Retry prompt with the pcal.trans error was sufficient — attempt 2 passed
- The prompt already warns about this, but it still happens ~50% of the time

### query_affected_tests() is ~10 lines using query_impact()
- Calls `query_impact(node_id)` to get all affected node IDs
- Forms `candidates = impact.affected | {node_id}` (self-inclusive)
- Filters through `test_artifacts` dict, returns `sorted(paths)` for determinism
- No new data structures needed beyond the `test_artifacts: dict[str, str]` mapping

### test_artifacts is a separate dict, not a Node field
- User explicitly chose this design: `test_artifacts: dict[str, str]` on `RegistryDag`
- Cleaner separation — no schema change to `Node`, no migration
- Serialized conditionally: only appears in `to_dict()` output when non-empty

### TLC state space grows with artifacts dimension
- Phase 7 (subgraph): 180,280 distinct states
- Phase 8 (change prop): 1,349,968 distinct states (~7.5x larger)
- The `MaxArtifacts = 3` constant adds a significant combinatorial dimension
- Still completes in reasonable time with `-workers auto`

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/python/registry/dag.py` — DAG with `query_affected_tests()`, `test_artifacts`
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Phase 8 self-registration + artifact mapping
- `/home/maceo/Dev/CodeWriter9.0/python/run_change_prop_loop.py` — Phase 8 loop script
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/test_change_propagation.py` — 17 generated tests
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/change_prop_bridge_artifacts.json`
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/change_propagation.tla` — TLC-verified spec
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/change_propagation.cfg`
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — 96 nodes, 198 edges

## Action Items & Next Steps

### Phase 8 is complete. Possible next phases:

**Option A: Phase 9 — Another pipeline feature**
The pipeline has now successfully built 4 features (impact analysis, dep validation, subgraph extraction, change propagation). Each one validates the single piece flow. Potential next features:
- Schema migration / versioning queries
- Conflict detection (overlapping edges from different features)
- DAG diff (compare two DAG snapshots)

**Option B: Use `query_affected_tests()` to build targeted test running**
Now that we can query which tests are affected by a node change, we could build a "smart test runner" that only runs affected tests. This would use the pipeline's own output operationally.

**Option C: Pipeline improvements**
- Add `chgprop-0001` test artifact mapping for itself (recursive self-reference — it already maps to its own test file)
- Improve retry prompts (the "label in with" error is predictable — could add a pre-check)
- Consider reducing TLC state space for faster verification

### Cleanup
- Temp files in project root: `change_prop_llm_response.txt`, `change_prop_llm_response_attempt2.txt`, `change_prop_loop_output.log`, `subgraph_llm_response.txt`, `subgraph_loop_output.log`

## Other Notes

### DAG state
- 96 nodes, 198 edges, 9 connected components
- Phase 8 added: req-0007, gwt-0021..0023, chgprop-0001 (5 nodes, 22 edges)

### Test counts
- 250 total tests passing
  - 43 bridge, 5 integration, 35 one-shot loop, 26 composer, 10 DAG, 25 extractor
  - 35 retroactive (Phase 4), 13 impact analysis (Phase 5), 21 dep validation (Phase 6), 20 subgraph (Phase 7), 17 change propagation (Phase 8)

### Test artifact mapping (current state)
- `impact-0001` → `tests/generated/test_impact_analysis.py`
- `depval-0001` → `tests/generated/test_dep_validation.py`
- `subgraph-0001` → `tests/generated/test_subgraph_extraction.py`
- `chgprop-0001` → `tests/generated/test_change_propagation.py`

### Pipeline single piece flow (proven across 4 features)
1. Add GWT behaviors + requirement to `extractor.py:_self_describe()`
2. Clone latest loop script (currently `run_change_prop_loop.py`), update module name, GWT ID, TLC config, prompt, `generate_tests()`
3. Run loop: `python3 python/run_<feature>_loop.py`
4. Implement feature in `dag.py` to pass generated tests
5. Wire serialization (`to_dict`/`from_dict`), populate `test_artifacts`, re-extract DAG, update test totals

### Pipeline commands
```bash
# Run any loop script
python3 python/run_change_prop_loop.py

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
**The LLM generates specs, not the implementation agent.** If the LLM-generated spec fails TLC, send the error back through the retry loop. Never hand-write or hand-fix specs. Tests must be mechanically generated from bridge artifacts, not hand-written by reading JSON. **Implementation comes AFTER test generation, not before.**
