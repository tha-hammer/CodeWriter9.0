# Testing Strategy, Performance, and Changelogs

## Testing Strategy

### Unit Tests (per phase):
- Phase 0: 11 tests in `test_register_gwt.py` (register_gwt, register_requirement, ID allocation, save/load)
- Phase 1: 3 tests in `test_context.py` (config.toml parsing)
- Phase 2: 6 tests in `test_cli.py::TestExtract` (including 2 merge tests)
- Phase 3: 2 tests in `test_cli.py::TestLoop` (error paths) + 3 tests in `TestSimulationTraceParser` (v5)
- Phase 4: 3 tests in `test_cli.py::TestBridge`
- Phase 5A: 2 tests in `test_trace_conversion.py` + 4 tests in `test_simulation_traces.py` (v5)
- Phase 5B: 8 tests in `test_tla_compiler.py` (compiler unchanged, role reframed as prompt enrichment)
- Phase 5C: 10 tests in `test_cli.py::TestGenTests` (v5: +2 trace prompt tests)
- Phase 6: 2 tests in `test_cli.py::TestTest`
- **Total: ~54 new tests → 346 total** (v5: +9 from simulation trace support)

### New files:
- `python/tests/test_register_gwt.py` — library API tests
- `python/tests/test_tla_compiler.py` — TLA+ → Python compiler tests
- `python/tests/test_trace_conversion.py` — CounterexampleTrace → TlcTrace tests
- `python/tests/test_simulation_traces.py` — SimulationTrace types + prompt formatting (v5)
- `python/registry/tla_compiler.py` — bounded TLA+ condition compiler (prompt enrichment utility)
- `python/registry/test_gen_loop.py` — LLM-in-the-loop test generation loop
- `python/registry/loop_runner.py` — common loop logic with proper retry
- `python/registry/traces.py` — simulation trace types + prompt formatting (v5)

### Integration Tests (manual, requires Claude Agent SDK):
```bash
# 1. Initialize and extract
cw9 init /tmp/testproj
cw9 extract /tmp/testproj

# 2. Register a GWT (library API — via Python script or upstream)
python3 -c "
import sys; sys.path.insert(0, 'python')
from registry.dag import RegistryDag
from registry.context import ProjectContext
ctx = ProjectContext.from_target('/tmp/testproj')
dag = RegistryDag.load(ctx.state_root / 'dag.json')
gwt_id = dag.register_gwt(
    given='a user submits a form',
    when='validation runs',
    then='errors are displayed inline',
)
dag.save(ctx.state_root / 'dag.json')
print(f'Registered: {gwt_id}')
"

# 3. Run pipeline
cw9 loop gwt-0024 /tmp/testproj
cw9 bridge gwt-0024 /tmp/testproj
cw9 gen-tests gwt-0024 /tmp/testproj
cw9 test /tmp/testproj

# 4. Verify re-extract preserves registered GWT
cw9 extract /tmp/testproj  # Should print "preserved 1 registered node(s)"
```

## Performance Considerations

- `cw9 extract` re-extracts full DAG (~0.2s for 96 nodes) + merge scan (~negligible). Acceptable.
- `cw9 loop` bottlenecked by LLM calls (~30s/attempt, up to 5 retries). **v5: adds ~10s for TLC `-simulate num=10` after PASS** — one-time cost per GWT, amortized by vastly better test generation context.
- `register_gwt()` is O(n) for ID scan — negligible at current scale.
- `cw9 test --node` loads DAG + computes closure (~0.1s). Fast.
- `tla_compiler.compile_condition()` is regex-based, O(n) in expression length. Fast.
- `cw9 gen-tests` bottlenecked by LLM calls (~30s/pass × 3 passes + retries). Similar to `cw9 loop`. **v5: simulation traces may reduce retry count by giving LLM concrete scenarios instead of requiring invention.**
- `merge_registered_nodes()` is O(n) in old DAG size. Negligible.
- `parse_simulation_traces()` is O(n) in TLC output length. Negligible for num=10.

## v3 Changelog

| Issue | What was wrong | Fix |
|---|---|---|
| **#1** Node.requirement() sig | Plan called `Node.requirement(req_id, name, text)` — 3 args. Actual factory is `requirement(id, text)` — 2 args. Tests also passed 3 args. | Added optional `name` param to `Node.requirement()` with `""` default. Fixed `register_requirement()` to call `(req_id, text, name)`. Fixed tests. |
| **#2** extract overwrites GWTs | `SchemaExtractor.extract()` starts with fresh `RegistryDag()`. Plan said "future enhancement." | Added `merge_registered_nodes()` to `RegistryDag`. `cmd_extract()` now loads old DAG, extracts fresh, merges back registered nodes. Added 2 tests. |
| **#3** process_response() wrong | Plan called `process_response(response, gwt_id)` — missing `cfg_text`. Used `status.retry_prompt` — field doesn't exist. | Fixed to `process_response(response, module_name, cfg_text)`. Added `build_retry_prompt()` that constructs from `status.counterexample` + `status.error`. |
| **#4** test gen regression | Plan emitted `assert state is not None` stubs. Existing code has real `_verify_*` methods. Bridge data unused. Trace pipeline disconnected. | v3: Rewrote Phase 5 into 4 parts: 5A (trace pipeline), 5B (TLA+ compiler), 5C (fixtures), 5D (scenario tests). v4: see below. |

## v4 Changelog

| Issue | What was wrong in v3 | Fix |
|---|---|---|
| **#5** Compiler can't bridge semantic gap | v3's Phase 5B regex compiler produces correct *expressions* (`all(t in candidates for t in affected)`) but unbound variables — no API binding, no fixture construction, no domain reasoning. The oracle at `run_change_prop_loop.py:572-621` shows that `_verify_NoFalsePositives` requires calling `dag.query_affected_tests()` + `dag.query_impact()` and building candidate sets — semantic work that regex can't do. | Reframed 5B as prompt enrichment utility (same code, different role). Replaced 5C/5D templates with Phase 5C: LLM-in-the-loop test generation, structurally parallel to `cw9 loop`. Bridge artifacts become prompt context; pytest replaces TLC as verifier. |
| **#6** No verification of generated tests | v3's `generate_tests_from_artifacts()` wrote a file and returned — no compile check, no collection check, no runtime check. Broken tests would only be caught at `cw9 test` time. | Added 3-stage `verify_test_file()`: `compile()` → `pytest --collect-only` → `pytest -x`. Retry loop feeds errors back to LLM. |
| **#7** Template ceiling | v3's template approach could produce verifier stubs and scenario tests, but hit a ceiling: operations got `assert state is not None` stubs, verifiers without compilable conditions got stubs, and the "real" assertions were only as good as the regex compiler. No path to improvement without rewriting the compiler. | LLM loop has no ceiling — it can generate arbitrarily complex test logic. The compiler hints give it a head start; the verification loop ensures correctness. Improvement path: better prompts, not more regex. |

## v5 Changelog

> **Key insight:** When TLC verifies a model with N distinct states and passes, it has visited
> every reachable state and confirmed every invariant holds at each one. We previously threw
> all of that away — we captured "pass" and a state count. TLC's `-simulate` mode outputs
> concrete execution traces through the state space on passing models. Each trace IS a test
> case: "starting from THIS state, applying THESE actions, produces THIS result, and ALL
> invariants hold." The LLM's job shifts from "design test scenarios" (creative) to
> "translate this state trace into Python API calls" (mechanical, verifiable).

| Issue | What was wrong in v4 | Fix |
|---|---|---|
| **#8** TLC as pass/fail gate only | After TLC PASS, we saved only the spec and a state count — the entire explored state space was discarded. Simulation traces (concrete verified execution paths) were never generated, so Phase 5C had to rely on the LLM inventing test scenarios from scratch. | Phase 3: after PASS, run `run_tlc_simulate()` with `-simulate num=10`. Parse output with `parse_simulation_traces()` (reuses existing `_STATE_HEADER_RE`/`_VAR_ASSIGN_RE` regexes). Save to `.cw9/specs/<gwt-id>_sim_traces.json`. |
| **#9** LLM invents test topologies | v4's Phase 5C prompt led with bridge artifacts and asked the LLM to "design test scenarios" — a creative task requiring domain reasoning about what interesting topologies look like. The LLM often produced correct-looking but shallow fixtures (linear chains only, no diamonds, no edge cases). | Restructured prompt with ranked context stack: simulation traces PRIMARY (rank 1), API signatures (rank 2), bridge+compiler hints (rank 3), TLA+ spec (rank 4), structural patterns (rank 5). Traces provide concrete Init→Action→Result sequences; LLM translates rather than invents. |
| **#10** No simulation trace types | `CounterexampleTrace` (from failures) was the only trace type. No type for verified execution paths, no formatter for prompt inclusion, no loader from JSON. | Added `python/registry/traces.py`: `SimulationTrace` dataclass with `init_state`/`final_state`/`actions` properties, `format_traces_for_prompt()` for ranked prompt context, `load_simulation_traces()` for JSON deserialization. |
| **#11** `TestGenContext` missing trace fields | v4's `TestGenContext` had no fields for simulation traces or the TLA+ spec text, so `build_test_plan_prompt()` couldn't include them even if they were available. | Added `simulation_traces: list` and `tla_spec_text: str` fields. `cmd_gen_tests()` loads both from `.cw9/specs/` artifacts. Graceful fallback to v4 behavior when traces are unavailable. |
| **#12** Oracle-based few-shot leaked topologies | Analysis showed that passing full oracle test files (e.g., `run_change_prop_loop.py:485-717`) as context caused the LLM to copy specific topologies rather than deriving test cases from the verified state space. | Replaced with structural patterns (rank 5): generic fixture/assertion/error templates that teach FORM without leaking module-specific topology choices. The "NOT doing" table now explicitly prohibits oracle file inclusion. |

## References

- Handoff: `thoughts/searchable/shared/handoffs/general/2026-03-10_07-57-53_stage0-1-projectcontext-cw9-init.md`
- `python/registry/types.py:64-69` — `Node.behavior()` factory
- `python/registry/types.py:72-73` — `Node.requirement()` factory (2 args: id, text)
- `python/registry/dag.py:36-40` — `add_node()` (no duplicate check)
- `python/registry/dag.py:242-259` — `query_affected_tests()`
- `python/registry/extractor.py:142-165` — `SchemaExtractor.extract()` (fresh RegistryDag)
- `python/registry/extractor.py:414-997` — `_self_describe()` (all hardcoded GWT IDs)
- `python/registry/context.py:60-76` — `from_target()`
- `python/registry/bridge.py:52-56` — `TlcTrace` dataclass
- `python/registry/bridge.py:553-565` — `_invariant_to_condition()` (5 text subs)
- `python/registry/bridge.py:582-622` — `translate_traces()` (TlcTrace → TestScenario)
- `python/registry/bridge.py:661-689` — `run_bridge()`, `BridgeResult`
- `python/registry/one_shot_loop.py:64-70` — `CounterexampleTrace` dataclass
- `python/registry/one_shot_loop.py:84-93` — `LoopStatus` (no retry_prompt field)
- `python/registry/one_shot_loop.py:615-622` — `process_response(llm_response, module_name, cfg_text)`
- `python/run_change_prop_loop.py:262-280` — `build_retry_prompt()` (existing pattern)
- `python/run_change_prop_loop.py:293-317` — LLM call pattern (claude_agent_sdk)
- `python/run_change_prop_loop.py:485-717` — `generate_tests()` (oracle for Phase 5)
- `python/registry/one_shot_loop.py:296-358` — `run_tlc()` (v5: model for `run_tlc_simulate()`)
- `python/registry/one_shot_loop.py:424-469` — `parse_counterexample()` (v5: regex patterns reused by `parse_simulation_traces()`)
- `python/registry/traces.py` — v5 new file: `SimulationTrace`, `format_traces_for_prompt()`, `load_simulation_traces()`
