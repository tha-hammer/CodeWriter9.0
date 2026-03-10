# Validation Report: CW9 CLI Pipeline Commands

**Date:** 2026-03-10 (re-validated)
**Plan:** `cw9-cli-pipeline-commands/INDEX.md` (DRAFT v5)
**Validator:** Claude Code automated validation (independent re-validation)

---

## Implementation Status

| Phase | Name | Status | Plan Checks | Code Verified |
|-------|------|--------|-------------|---------------|
| Phase 0 | Library API -- `register_gwt()` | ✓ Fully implemented | 10/10 | dag.py:291-401, types.py:72-73 |
| Phase 1 | `config.toml` -> `from_target()` | ✓ Fully implemented | 8/8 | context.py:71-80 |
| Phase 2 | `cw9 extract` with GWT merge | ✓ Fully implemented | 8/8 | cli.py:154-184 |
| Phase 3 | `cw9 loop <gwt-id>` -- LLM -> PlusCal -> TLC | ✓ Fully implemented | 12/12 | loop_runner.py:88-210, one_shot_loop.py:682-760 |
| Phase 4 | `cw9 bridge <gwt-id>` -- spec -> bridge artifacts | ✓ Fully implemented | 9/9 | cli.py:215-273 |
| Phase 5A | Trace pipeline + simulation trace types | ✓ Fully implemented | 17/17 | traces.py:15-92 |
| Phase 5B | TLA+ condition compiler (prompt enrichment) | ✓ Fully implemented | 5/5 | tla_compiler.py:1-158 |
| Phase 5C | `cw9 gen-tests <gwt-id>` -- LLM test gen loop | ✓ Fully implemented | 11/11 + 10/10 tests | test_gen_loop.py:25-457, cli.py:276-366 |
| Phase 6 | `cw9 test` -- run generated tests | ✓ Fully implemented | 6/6 | cli.py:386-415 |

---

## Automated Verification Results

| Check | Result | Details |
|-------|--------|---------|
| `python3 -m pytest tests/ -v` | **346 passed in 4.48s** | Zero failures, zero errors, zero skips |
| Test count matches plan | **346/346** | 292 original + 54 new tests |
| `import registry.loop_runner` | PASS | No import errors |
| `import registry.tla_compiler` | PASS | No import errors |
| `import registry.test_gen_loop` | PASS | No import errors |
| `import registry.traces` | PASS | No import errors |

### Test Breakdown by Phase

| File | Phase | Tests | Status |
|------|-------|-------|--------|
| `test_register_gwt.py` | 0 | 11 | PASS |
| `test_context.py` (config tests) | 1 | 3 (of 19 total) | PASS |
| `test_cli.py::TestExtract` | 2 | 6 | PASS |
| `test_cli.py::TestLoop` | 3 | 2 | PASS |
| `test_cli.py::TestSimulationTraceParser` | 3 (v5) | 3 | PASS |
| `test_cli.py::TestBridge` | 4 | 3 | PASS |
| `test_trace_conversion.py` | 5A | 2 | PASS |
| `test_simulation_traces.py` | 5A (v5) | 4 | PASS |
| `test_tla_compiler.py` | 5B | 8 | PASS |
| `test_cli.py::TestGenTests` | 5C | 10 | PASS |
| `test_cli.py::TestTest` | 6 | 2 | PASS |
| **Total new tests** | | **54** | |

---

## Code Review Findings (Line-Level Verification)

### Phase 0: register_gwt() — dag.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `register_gwt(self, given, when, then, parent_req=None)` | dag.py:313-352 | ✓ Exact signature + optional `name` param |
| `_next_gwt_id()` scans existing nodes | dag.py:291-299 | ✓ Finds max gwt-NNNN, increments |
| `_next_req_id()` scans existing nodes | dag.py:301-309 | ✓ Finds max req-NNNN, increments |
| `register_requirement()` with auto ID | dag.py:354-369 | ✓ Calls `_next_req_id()`, creates node |
| `Node.requirement(id, text, name="")` | types.py:72-73 | ✓ Optional name param added |
| `merge_registered_nodes()` preserves gwt/req | dag.py:373-401 | ✓ Filters by prefix, preserves edges |

### Phase 1: config.toml — context.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `from_target()` reads config.toml via tomllib | context.py:71-77 | ✓ |
| Fallback to `__file__` auto-detection | context.py:79-80 | ✓ |

### Phase 2: extract + merge — cli.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `cmd_extract()` loads old DAG | cli.py:154-161 | ✓ |
| Extracts fresh DAG | cli.py:164-166 | ✓ |
| Calls `merge_registered_nodes()` | cli.py:170-171 | ✓ |
| Prints diff of preserved nodes | cli.py:182-184 | ✓ |

### Phase 3: loop + v5 simulate — loop_runner.py, one_shot_loop.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `run_loop()` main async function | loop_runner.py:88-210 | ✓ |
| `process_response(llm_response, module_name, cfg_text)` 3 args | loop_runner.py:152-156 | ✓ |
| `build_retry_prompt()` from counterexample + error | loop_runner.py:49-85 | ✓ |
| `run_tlc_simulate()` with `-simulate num=10` | one_shot_loop.py:729-760 | ✓ |
| `parse_simulation_traces()` reuses regex patterns | one_shot_loop.py:682-726 | ✓ Uses `_STATE_HEADER_RE` (415) + `_VAR_ASSIGN_RE` (416) |
| Saves sim traces to `{gwt_id}_sim_traces.json` | loop_runner.py:174-187 | ✓ |

### Phase 4: bridge — cli.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `cmd_bridge()` checks spec exists | cli.py:224-228 | ✓ |
| Calls `run_bridge()` | cli.py:240 | ✓ |
| Saves artifact JSON | cli.py:264-265 | ✓ |
| Prints summary | cli.py:267-271 | ✓ |

### Phase 5A: traces.py (v5 new file)

| Requirement | Location | Status |
|-------------|----------|--------|
| `SimulationTrace` dataclass | traces.py:15-42 | ✓ |
| `init_state` property | traces.py:25-27 | ✓ |
| `final_state` property | traces.py:30-32 | ✓ |
| `actions` property | traces.py:35-37 | ✓ |
| `format_traces_for_prompt()` | traces.py:44-73 | ✓ |
| `load_simulation_traces()` | traces.py:76-92 | ✓ |

### Phase 5B: tla_compiler.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `compile_condition()` with regex phases | tla_compiler.py (158 lines) | ✓ |
| `compile_assertions()` | tla_compiler.py | ✓ |
| `CompileError`, `CompiledAssertion` types | tla_compiler.py | ✓ |

### Phase 5C: test_gen_loop.py — LLM test generation loop

| Requirement | Location | Status |
|-------------|----------|--------|
| `run_test_gen_loop()` 3-pass (plan→review→codegen) | test_gen_loop.py:392-457, passes at 417-428 | ✓ |
| `verify_test_file()` 3-stage (compile→collect→run) | test_gen_loop.py:301-346 | ✓ |
| `TestGenContext.simulation_traces` (v5) | test_gen_loop.py:43 | ✓ `list[list[dict]]` |
| `TestGenContext.tla_spec_text` (v5) | test_gen_loop.py:44 | ✓ `str` |
| Ranked context: sim traces = RANK 1 PRIMARY | test_gen_loop.py:137-148 | ✓ |
| `cmd_gen_tests()` loads all 5 artifact types | cli.py:276-366, traces at 321-326 | ✓ |

### Phase 6: test — cli.py

| Requirement | Location | Status |
|-------------|----------|--------|
| `cmd_test()` with `--node` smart targeting | cli.py:386, 458 | ✓ |
| Populates `test_artifacts` from bridge | cli.py:395-400 | ✓ |
| `query_affected_tests()` for smart targeting | cli.py:402 | ✓ |
| Subprocess pytest invocation | cli.py:412-415 | ✓ |

### New Files Created (all 8 verified present and non-empty)

| File | Lines | Phase | Purpose |
|------|-------|-------|---------|
| `python/registry/loop_runner.py` | 230 | 3 | Common LLM loop logic with retry |
| `python/registry/tla_compiler.py` | 158 | 5B | TLA+ condition -> Python compiler |
| `python/registry/test_gen_loop.py` | 457 | 5C | LLM-in-the-loop test generation |
| `python/registry/traces.py` | 92 | 5A (v5) | Simulation trace types + prompt formatting |
| `python/tests/test_register_gwt.py` | 92 | 0 | Library API tests |
| `python/tests/test_tla_compiler.py` | 57 | 5B | Compiler tests |
| `python/tests/test_trace_conversion.py` | 27 | 5A | Trace conversion tests |
| `python/tests/test_simulation_traces.py` | 58 | 5A (v5) | SimulationTrace type tests |

### Minor Observations (non-blocking)

1. ~~**Phase 5B `compile_condition()` phase numbering:** Regex phases numbered 1-8, then 10 (skipping 9).~~ **FIXED** — Renumbered Phase 10 → Phase 9 (tla_compiler.py:87). Phases now sequential 1-9.

### Deviations from Plan

**None found.** All phases match specifications. v3 fixes (#1-#4), v4 changes (#5-#7), and v5 enhancements (#8-#12) all applied.

---

## Plan Checkbox Status (from phase files)

| Phase | Checkboxes | Status | Notes |
|-------|-----------|--------|-------|
| Phase 0 | 3/3 | COMPLETE | All automated criteria checked |
| Phase 1 | 2/2 | COMPLETE | Both automated criteria checked |
| Phase 2 | 2/2 | COMPLETE | Both automated criteria checked |
| Phase 3 | 2/4 | PARTIAL | 2 manual items remain (require Claude Agent SDK) |
| Phase 4 | 1/2 | PARTIAL | 1 manual item remains (requires loop output) |
| Phase 5A | 2/2 | COMPLETE | Both automated criteria checked |
| Phase 5B | 1/1 | COMPLETE | Automated criteria checked |
| Phase 5C | 4/4 | COMPLETE | All criteria checked |
| Phase 6 | 1/2 | PARTIAL | 1 manual item remains (full pipeline test) |
| **Total** | **18/22** | | **4 outstanding = all manual/integration** |

---

## Manual Testing Required

These items require LLM access (Claude Agent SDK) and cannot be verified automatically:

### Phase 3
- [ ] `cw9 loop gwt-0021` -- completes TLC verification, saves `.tla`/`.cfg`
- [ ] Session logs appear in `.cw9/sessions/gwt-0021_attempt*.txt`
- [ ] Simulation traces saved to `.cw9/specs/gwt-0021_sim_traces.json` (v5)

### Phase 4
- [ ] After `cw9 loop gwt-0021`, `cw9 bridge gwt-0021` produces artifact JSON

### Phase 5C
- [ ] `cw9 gen-tests gwt-0021` generates behaviorally equivalent tests to oracle
- [ ] Generated fixtures derived from TLC simulation traces (v5)
- [ ] Generated `_verify_NoFalsePositives` equivalent calls real API methods
- [ ] Retry self-correction works when import is broken
- [ ] Test fixtures match Init state topologies from TLC output (v5)

### Phase 6
- [ ] Full pipeline: `cw9 extract && cw9 loop gwt-0024 && cw9 bridge gwt-0024 && cw9 gen-tests gwt-0024 && cw9 test`
- [ ] Smart targeting: `cw9 test --node db-b7r2` runs only affected tests

---

## Recommendations

1. **No blockers found** -- all automated success criteria pass.
2. **Manual integration testing** is the primary remaining gap. The full pipeline (`extract -> loop -> bridge -> gen-tests -> test`) should be exercised end-to-end with a real GWT.
3. ~~The Phase 5B phase numbering gap is cosmetic and does not affect functionality.~~ **FIXED.**

---

## Verdict: **PASS**

All 9 phases are fully implemented as specified. 346/346 tests pass (4.48s). All 8 new files exist with substantive content. All 4 new modules import cleanly. No regressions. No deviations from plan. 18/22 plan checkboxes complete; remaining 4 are manual integration tests requiring Claude Agent SDK.
