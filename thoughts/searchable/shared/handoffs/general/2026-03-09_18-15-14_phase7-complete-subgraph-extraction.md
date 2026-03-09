---
date: 2026-03-09T18:15:14-04:00
researcher: claude-opus
git_commit: 6fd3e69
branch: master
repository: CodeWriter9.0
topic: "Phase 7 Complete — Subgraph Extraction; Next: Change Propagation (Phase 8)"
tags: [implementation, tla-plus, pluscal, subgraph-extraction, change-propagation, self-hosting, single-piece-flow, phase-7, phase-8]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 7 Complete — Subgraph Extraction; Next: Change Propagation

## Task(s)

### Completed — Phase 7: Subgraph Extraction (Third Pipeline-Built Feature)

The third feature built through the self-hosting pipeline is **subgraph extraction** — `extract_subgraph(node_id) → SubgraphResult` returning the minimal subgraph (forward closure + reverse closure + self + induced edges) needed to understand a node.

**Single piece flow executed:**
1. Plain language requirement → 3 GWT behaviors (gwt-0018, gwt-0019, gwt-0020) registered in DAG
2. `run_subgraph_loop.py` → LLM generated PlusCal spec via `claude-agent-sdk`
3. TLC verified on **attempt 1**: **324,247 states (180,280 distinct), 0 violations, 6 invariants**
4. Bridge produced: 1 data_structure, 21 operations, 6 verifiers, 6 assertions
5. `generate_tests()` mechanically translated bridge artifacts → 20 pytest tests
6. `extract_subgraph()` implemented in `dag.py` → all 20 generated tests pass
7. Full suite: **233 tests pass** (213 existing + 20 generated)

### Uncommitted — All Phase 7 changes need committing before starting Phase 8

### Next — Phase 8: Change Propagation (`query_affected_tests`)

Build `query_affected_tests(node_id) → list[str]` through the same single piece flow. Returns file paths of test files affected by a change to the target node.

## Critical References
- `BOOTSTRAP.md:626-661` — Phase 5 Self-Hosting definition (applies to all pipeline-built features)
- `python/run_subgraph_loop.py` — Latest loop script template (Phase 7)
- `python/run_dep_validation_loop.py` — Alternative template reference

## Recent changes (all uncommitted)
- `python/registry/dag.py:10` — Added `SubgraphResult` import
- `python/registry/dag.py:166-188` — Added `extract_subgraph()` method (forward + reverse closure + edge filter)
- `python/registry/types.py:128-132` — Added `SubgraphResult` dataclass (root, nodes, edges)
- `python/registry/extractor.py:894-940` — Phase 7 self-registration (req-0006, gwt-0018..0020, subgraph-0001)
- `python/run_subgraph_loop.py` — Full loop script: LLM call → TLC → bridge → test generation
- `python/tests/generated/test_subgraph_extraction.py` — 20 mechanically generated tests
- `python/tests/generated/subgraph_bridge_artifacts.json` — Bridge output
- `templates/pluscal/instances/subgraph_extraction.tla` — LLM-generated, TLC-verified spec
- `templates/pluscal/instances/subgraph_extraction.cfg` — TLC config
- `python/tests/test_one_shot_loop.py:382-385` — Updated DAG totals assertion (91 nodes, 176 edges)
- `schema/registry_dag.json` — Re-extracted DAG (91 nodes, 176 edges, 9 components)

## Learnings

### Spec converged on attempt 1
- First time a pipeline feature's spec verified on the first try
- The subgraph extraction problem was well-suited to TLC — BFS is deterministic once the graph is built
- 180,280 distinct states is significantly larger than dep validation (762), but TLC handled it fine

### extract_subgraph() is ~15 lines using existing primitives
- Forward closure: `self.closure[node_id]` (already computed)
- Reverse closure: iterate `self.closure`, collect nodes where `node_id in reachable`
- Edge filter: `[e for e in self.edges if e.from_id in nodes and e.to_id in nodes]`
- No dependency on `query_impact()` or `validate_edge()` — only uses raw closure + edges

### Subgraph extraction does NOT depend on impact-0001
- An early draft included `subgraph-0001 → impact-0001` edge — this was removed
- Both use the same underlying closure data, but subgraph does forward+reverse while impact does reverse-only
- Keeping them independent is correct per the DAG's separation of concerns

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/python/registry/dag.py` — DAG with `extract_subgraph()`, `validate_edge()`, `query_impact()`
- `/home/maceo/Dev/CodeWriter9.0/python/registry/types.py` — `SubgraphResult` dataclass
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Phase 7 self-registration
- `/home/maceo/Dev/CodeWriter9.0/python/run_subgraph_loop.py` — Phase 7 loop script
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/test_subgraph_extraction.py` — 20 generated tests
- `/home/maceo/Dev/CodeWriter9.0/python/tests/generated/subgraph_bridge_artifacts.json`
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/subgraph_extraction.tla` — Verified spec
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/subgraph_extraction.cfg`
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — 91 nodes, 176 edges

## Action Items & Next Steps

### IMMEDIATE: Commit Phase 7 changes, then start Phase 8

**1. Commit Phase 7** (all changes listed in "Recent changes" above)

**2. Build Phase 8: Change Propagation through the single piece flow**

The user specified this feature tightly:

**Query:** `query_affected_tests(node_id) → list[str]` — returns file paths of test files affected by a change to the target node. Nothing else. No test runner, no caching, no incremental execution.

**Design decision (user-specified):** Use a **separate mapping dict on RegistryDag** rather than adding a `test_artifact` field to `Node`. Cleaner separation, no schema change.

The mapping dict approach:
- Add `test_artifacts: dict[str, str]` to `RegistryDag` — maps node_id → test file path
- Populate it for existing pipeline features:
  - `impact-0001` → `tests/generated/test_impact_analysis.py`
  - `depval-0001` → `tests/generated/test_dep_validation.py`
  - `subgraph-0001` → `tests/generated/test_subgraph_extraction.py`
- `query_affected_tests(X)` does:
  1. `query_impact(X)` to get all affected node IDs
  2. For each affected node (+ X itself), check `test_artifacts` dict
  3. Return deduplicated list of paths

**GWT behaviors (user-specified):**
- `gwt-0021`: Given a node that a test-bearing node depends on, when `query_affected_tests` is called, then the test path is in the result
- `gwt-0022`: Given a node with no downstream test artifacts, when `query_affected_tests` is called, then the result is empty
- `gwt-0023`: Given a node that IS a test-bearing node, when `query_affected_tests` is called, then its own test path is included

**TLC invariant:** Every returned test path corresponds to a node in the impact set. No false positives, no false negatives.

**IDs for registration:** req-0007, gwt-0021/0022/0023, chgprop-0001

**Single piece flow steps:**
1. Add GWT behaviors to `extractor.py:_self_describe()`
2. Clone `run_subgraph_loop.py` → `run_change_prop_loop.py`, update:
   - GWT ID to `gwt-0021`
   - Module name to `change_propagation`
   - TLC config (CONSTANTS, INVARIANTS) — model a graph with node-to-test-artifact mappings
   - Prompt text (requirements: given impact set + artifact mapping, return affected test paths)
   - `generate_tests()` function
3. Run: `python3 python/run_change_prop_loop.py`
4. Implement `query_affected_tests()` in `dag.py` + add `test_artifacts` dict
5. Wire up `test_artifacts` in serialization (`to_dict`/`from_dict`) and `_self_describe()`
6. Re-extract DAG, update test counts, commit

### Cleanup
- Temp file in project root: `subgraph_llm_response.txt`, `subgraph_loop_output.log`

## Other Notes

### DAG state
- 91 nodes, 176 edges, 9 connected components
- Phase 7 added: req-0006, gwt-0018..0020, subgraph-0001 (5 nodes, 18 edges)

### Test counts
- 233 total tests passing
  - 43 bridge, 5 integration, 35 one-shot loop, 26 composer, 10 DAG, 25 extractor
  - 35 retroactive (Phase 4), 13 impact analysis (Phase 5), 21 dep validation (Phase 6), 20 subgraph (Phase 7)

### Existing test artifact mapping (for populating `test_artifacts` dict)
- `impact-0001` → `tests/generated/test_impact_analysis.py`
- `depval-0001` → `tests/generated/test_dep_validation.py`
- `subgraph-0001` → `tests/generated/test_subgraph_extraction.py`
- (Phase 4 retroactive tests exist at `tests/generated/test_retroactive_phase0_3.py` but map to multiple nodes — could register against `res-0001`/`res-0002`/`res-0003` or skip)

### Key structural facts for Feature 2 implementation
- `query_impact()` returns `ImpactResult` with `target: str`, `affected: set[str]`, `direct_dependents: set[str]` — see `dag.py:241-267`
- `Node` has no `test_artifact` field — the user explicitly chose a separate dict over modifying Node
- The `to_dict`/`from_dict` methods on `RegistryDag` (`dag.py:281-319`) will need to handle `test_artifacts` serialization
- `Node.path` field on resource nodes points to implementation code, not tests

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
**The LLM generates specs, not the implementation agent.** If the LLM-generated spec fails TLC, send the error back through the retry loop. Never hand-write or hand-fix specs. Tests must be mechanically generated from bridge artifacts, not hand-written by reading JSON.
