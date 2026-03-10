# Plan Review Report: CW9 CLI Pipeline Commands (v5)

**Plan:** `thoughts/searchable/shared/plans/2026-03-10-cw9-cli-pipeline-commands.md`
**Reviewed:** 2026-03-10
**Reviewer:** DustyForge (automated architectural review)

---

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 3 issues (1 critical, 2 warnings) |
| Interfaces | ⚠️ | 3 issues (1 critical, 2 warnings) |
| Promises | ⚠️ | 2 warnings |
| Data Models | ✅ | 1 minor warning |
| APIs | ⚠️ | 1 critical issue |

---

## Contract Review

### Well-Defined:
- ✅ `register_gwt()` — Clear input/output contract. GWT ID allocation, node creation, edge wiring, duplicate detection via `add_node()` overwrite behavior all correctly specified
- ✅ `register_requirement()` — Correct `Node.requirement(req_id, text, name)` call order matching the proposed 3-arg signature
- ✅ `merge_registered_nodes()` — Preserves nodes absent from fresh DAG, preserves edges where both endpoints exist. Merge-by-absence (not by ID range) is actually correct since `_self_describe()` re-creates all gwt-0001..0023 in every extract
- ✅ `process_response()` call — Plan correctly uses `(llm_response, module_name, cfg_text)` matching actual signature at `one_shot_loop.py:615`
- ✅ `build_retry_prompt()` — Correctly constructs from `status.counterexample` + `status.error` + `status.tlc_result.error_message`, matching the pattern in `run_change_prop_loop.py:262-290`
- ✅ `run_bridge(tla_text, traces=traces)` — Matches actual signature `run_bridge(tla_text: str, traces: list[TlcTrace] | None = None)`
- ✅ `counterexample_to_tlc_trace()` — Correctly maps `CounterexampleTrace.states[i]["vars"]` → `TlcTrace.states[i]` (flattening the nested dict)

### Missing or Unclear:
- ❌ **`node.then_` typo in `cmd_gen_tests()`** — Plan line 2366: `"then": node.then_ or ""`. The `Node` dataclass field is `then: str | None = None` (no trailing underscore). This would raise `AttributeError` at runtime.
- ⚠️ **`_parse_simulation_traces` assumes TLC `-simulate` output matches `_STATE_HEADER_RE`** — The regex `r'State\s+(\d+):\s*<(.+?)>'` was designed for counterexample output. TLC `-simulate` mode may use different formatting (e.g., `State 1: <Initial predicate>` vs `State 1: <Init>`). The plan assumes identical format without citing TLC documentation. This is likely correct but unverified.
- ⚠️ **`build_retry_prompt` in `loop_runner.py` has different arity from existing pattern** — Existing: `build_retry_prompt(original_prompt, attempt, error_msg, tlc_output, counterexample_summary)` (5 explicit args). Plan: `build_retry_prompt(initial_prompt, attempt, status: LoopStatus)` (3 args, wrapping LoopStatus). This is a deliberate simplification and functionally correct, but means the retry prompt structure will differ slightly from the existing 5 loop scripts.

### Recommendations:
- **Fix** `node.then_` → `node.then` in `cmd_gen_tests()` (line 2366)
- **Add** a unit test for `_parse_simulation_traces` using actual TLC `-simulate` output (capture one real trace during development)
- **Document** the retry prompt arity difference as intentional

---

## Interface Review

### Well-Defined:
- ✅ `RegistryDag.register_gwt()` — Complete method signature with types, return value, exception contract
- ✅ `RegistryDag.register_requirement()` — Companion method, consistent naming pattern
- ✅ `Node.requirement()` optional `name` param — Backwards-compatible, all existing 9 call sites unaffected
- ✅ CLI argparse wiring — All 6 commands follow consistent pattern: `gwt_id` positional, `target_dir` optional defaulting to `"."`
- ✅ `TestGenContext` dataclass — Complete field specification for the LLM test generation context
- ✅ `SimulationTrace` dataclass — Clean computed properties (`init_state`, `final_state`, `actions`)
- ✅ `verify_test_file()` — Three-stage verification pipeline (compile → collect → run) with clear `VerifyResult` return type

### Missing or Unclear:
- ❌ **`make_llm_caller` doesn't exist in `loop_runner.py`** — Plan line 2407-2408: `from registry.loop_runner import make_llm_caller` / `call_llm = make_llm_caller(ctx)`. But `loop_runner.py` as specified only defines `call_llm` as a module-level async function, not a factory function `make_llm_caller(ctx)`. This would raise `ImportError`.
- ⚠️ **`cmd_extract` uses unusual import alias** — `from registry.dag import RegistryDag as RD` inside function body (plan line 535). All other code uses `RegistryDag` unaliased. Minor inconsistency, but no functional issue.
- ⚠️ **Private function `_parse_simulation_traces` tested via direct import** — Plan line 1044: `from registry.one_shot_loop import _parse_simulation_traces`. Works in Python but couples tests to private API. Consider making it public or testing via `run_tlc_simulate`.

### Recommendations:
- **Fix** one of: (a) add `make_llm_caller(ctx)` factory to `loop_runner.py` that returns the `call_llm` async function, or (b) change `cmd_gen_tests` to directly import and use `call_llm` from `loop_runner`
- **Use** `RegistryDag` unaliased in `cmd_extract` for consistency
- **Consider** exposing `parse_simulation_traces` as public (no underscore) since it has its own test suite

---

## Promise Review

### Well-Defined:
- ✅ ID allocation is deterministic — `_next_gwt_id()` scans existing nodes, `max(existing, default=0) + 1`. Save/load preserves IDs correctly.
- ✅ `merge_registered_nodes()` is idempotent — merging the same old DAG twice produces the same result (only absent nodes are merged)
- ✅ `verify_test_file()` stages are ordered — compile before collect, collect before run. Early return on failure prevents cascading errors.
- ✅ Retry loop in `run_loop()` always uses `initial_prompt` as base — doesn't accumulate context across retries (matches existing pattern at `run_change_prop_loop.py:409-411`)

### Missing or Unclear:
- ⚠️ **No timeout/cancellation for LLM calls in `run_test_gen_loop`** — The 3-pass generation (plan + review + codegen) makes 3+ LLM calls with no per-call timeout. `call_llm` in `loop_runner.py` also has no timeout. Could hang indefinitely if the API is unresponsive. The existing `run_change_prop_loop.py` has the same gap, so this is pre-existing.
- ⚠️ **`verify_test_file` hardcoded timeouts** — 30s for `pytest --collect-only`, 120s for `pytest -x`. Generated tests importing heavy modules (e.g., the full DAG with 96 nodes) could timeout spuriously during collection. Consider making these configurable or at least documented.

### Recommendations:
- **Add** a comment noting the lack of LLM call timeout as a known limitation (matches existing pattern)
- **Consider** making `verify_test_file` timeouts configurable via `TestGenContext` or kwargs

---

## Data Model Review

### Well-Defined:
- ✅ `SimulationTrace` — Well-structured with `states: list[dict[str, Any]]`, `invariants_verified: list[str]`, computed properties
- ✅ `TestGenContext` — Complete field set including v5 additions (`simulation_traces`, `tla_spec_text`)
- ✅ `VerifyResult` — Clean status reporting with `passed`, `stage`, `errors`, `stdout`, `stderr`, `attempt`
- ✅ `CompiledAssertion` — Carries both `python_expr` and `original_tla` plus `variables_used` metadata
- ✅ Artifact JSON format — Consistent structure across bridge artifacts and trace files

### Missing or Unclear:
- ⚠️ **`TestGenContext` uses bare `list` types** — `simulation_traces: list` and `test_scenarios: list` without type parameters. Actual types flowing through are `list[list[dict[str, Any]]]` and `list[dict[str, Any]]` respectively. Minor typing gap; no runtime impact.

### Recommendations:
- **Parameterize** list types: `simulation_traces: list[list[dict[str, Any]]]`, `test_scenarios: list[dict[str, Any]]`

---

## API Review

### Well-Defined:
- ✅ CLI surface — All 6 commands (`extract`, `loop`, `bridge`, `gen-tests`, `test`) follow consistent argparse pattern
- ✅ Library API — `register_gwt()` and `register_requirement()` are clean programmatic entry points
- ✅ `run_bridge()` interface — Single function, clear inputs (tla_text + optional traces), structured return (BridgeResult)
- ✅ `run_test_gen_loop()` — Dependency injection of `call_llm` makes testing possible without real LLM

### Missing or Unclear:
- ❌ **`discover_api_context` module_name mapping is broken** — The function at plan line 1988 globs `python_dir / f"registry/{module_name}*.py"`. But `module_name` comes from bridge artifacts, which uses the TLA+ module name (e.g., `"ChangePropagation"`). No Python file matches `registry/ChangePropagation*.py`. The existing codebase uses snake_case filenames like `dag.py`, `bridge.py`, `context.py`. The glob would find nothing, falling through to the `"# No source found"` fallback. This means the LLM test generation loop receives no API context — significantly degrading output quality.

### Recommendations:
- **Fix** `discover_api_context` to handle the TLA+ → Python module name mapping. Options:
  1. Store the Python module name in bridge artifacts (add a `python_module` field to `BridgeResult`)
  2. Convert TLA+ PascalCase to snake_case: `"ChangePropagation"` → `"change_propagation"` → glob `registry/change_propagation*.py` or `registry/*change_propagation*.py`
  3. Accept a separate `python_module_name` param in `TestGenContext`
  4. Search more broadly: glob `registry/**/*.py` and filter by content (slower but more robust)

---

## Critical Issues (Must Address Before Implementation)

### 1. **`node.then_` AttributeError** (Contract)
- **Location:** Plan Phase 5C, `cmd_gen_tests()` line 2366
- **Code:** `"then": node.then_ or ""`
- **Impact:** `AttributeError` at runtime when loading GWT text from DAG. `cw9 gen-tests` would crash for any GWT.
- **Fix:** Change to `"then": node.then or ""`

### 2. **`make_llm_caller` ImportError** (Interface)
- **Location:** Plan Phase 5C, `cmd_gen_tests()` lines 2407-2408
- **Code:** `from registry.loop_runner import make_llm_caller` / `call_llm = make_llm_caller(ctx)`
- **Impact:** `ImportError` — function doesn't exist. `cw9 gen-tests` would crash at import time.
- **Fix:** Either (a) add `make_llm_caller(ctx)` factory to `loop_runner.py` that wraps `call_llm` with the proper system prompt, or (b) import `call_llm` directly and use it

### 3. **`discover_api_context` finds nothing** (API)
- **Location:** Plan Phase 5C, `discover_api_context()` lines 1988-2017
- **Code:** `python_dir.glob(f"registry/{module_name}*.py")` where `module_name` is TLA+ PascalCase
- **Impact:** LLM receives `"# No source found"` instead of real API context. Test generation quality severely degraded — the LLM can't bind TLA+ variables to API calls without knowing the API.
- **Fix:** Add PascalCase → snake_case conversion: `module_name_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', module_name).lower()` then glob for that

---

## Suggested Plan Amendments

```diff
# In Phase 5C: cmd_gen_tests()

# Line 2366: Fix AttributeError
-             "then": node.then_ or "",
+             "then": node.then or "",

# Lines 2407-2408: Fix missing function
- from registry.loop_runner import make_llm_caller
- call_llm = make_llm_caller(ctx)
+ from registry.loop_runner import call_llm

# In Phase 5C: discover_api_context()

# Line 1996: Add PascalCase → snake_case conversion
+ import re
+ module_name_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', module_name).lower()
- candidates = list(python_dir.glob(f"registry/{module_name}*.py"))
+ candidates = list(python_dir.glob(f"registry/*{module_name_snake}*.py"))
  if not candidates:
-     candidates = list(python_dir.glob(f"registry/**/{module_name}*.py"))
+     candidates = list(python_dir.glob(f"registry/**/*{module_name_snake}*.py"))

# In Phase 2: cmd_extract() — Use consistent import style
- from registry.dag import RegistryDag as RD
- old_dag = RD.load(dag_path)
+ from registry.dag import RegistryDag
+ old_dag = RegistryDag.load(dag_path)
```

---

## Non-Critical Observations

1. **Plan is exceptionally thorough** — v3/v4/v5 changelogs show iterative refinement against actual codebase. Most API signatures, line numbers, and behavioral descriptions match the codebase exactly.

2. **Test count is comprehensive** — 54 new tests covering all phases, including merge preservation, trace parsing, compiler hints, and prompt construction.

3. **The simulation trace insight (v5) is architecturally sound** — Using TLC `-simulate` traces as primary test generation context shifts the LLM task from creative (invent scenarios) to mechanical (translate verified traces). This should measurably improve test quality.

4. **Separation of concerns is clean** — Library API (`register_gwt`) vs CLI commands, `loop_runner.py` vs `test_gen_loop.py`, `tla_compiler.py` as prompt enrichment utility.

5. **The three-pass generation (plan → review → codegen) is well-motivated** — Chain-of-thought for test generation, with concrete rationale for why single-pass fails on semantic invariants.

---

## Approval Status

- [ ] **Ready for Implementation** — No critical issues
- [x] **Needs Minor Revision** — 3 critical issues must be fixed (all are straightforward 1-line fixes), then ready to implement
- [ ] **Needs Major Revision** — Critical issues must be resolved first

All three critical issues are mechanical bugs (typo, missing function, wrong glob pattern) rather than architectural problems. The plan's architecture, phasing, and test strategy are sound. Fix the three issues and proceed.
