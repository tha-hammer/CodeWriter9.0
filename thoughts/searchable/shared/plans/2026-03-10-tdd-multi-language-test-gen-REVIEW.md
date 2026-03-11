# Plan Review Report: Multi-Language Test Generation (TDD)

**Reviewed by:** DustyForge (Orchestration LLM)
**Date:** 2026-03-10
**Plan:** `thoughts/searchable/shared/plans/2026-03-10-tdd-multi-language-test-gen.md`

---

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 4 issues |
| Interfaces | ⚠️ | 3 issues |
| Promises | ⚠️ | 2 issues |
| Data Models | ⚠️ | 3 issues |
| APIs | ✅ | 0 issues |

---

## Contract Review

### Well-Defined:
- ✅ **Strangler-fig phasing** — Python refactor first (Phase 1), then TS (Phase 2), Rust (Phase 3), Go (Phase 4). Each phase has a checkpoint gate. This directly addresses drift risks D1-D2 from the orchestration assessment.
- ✅ **`LanguageProfile` protocol** — `@runtime_checkable`, so `isinstance()` checks work. Protocol methods cover all 6 coupling points identified in the orchestration assessment (M1-M6).
- ✅ **TDD cycle structure** — Red/Green/Refactor for every behavior. 24 behaviors total. Tests exist before implementation.
- ✅ **`get_profile()` factory** — lazy imports per language backend, single dispatch point. Addresses drift risk D3.
- ✅ **Error contract for compilers** — `CompileError` already exists at `tla_compiler.py:16`, plan reuses it for all language compilers.

### Missing or Unclear:

- ❌ **C1: `compile_assertions()` not in protocol** — The `LanguageProfile` protocol defines `compile_condition(tla_expr, state_var)` for a *single* expression. But `build_compiler_hints()` in `test_gen_loop.py:337` calls `compile_assertions(verifiers)` which iterates all verifier conditions and returns `dict[str, CompiledAssertion]`. The plan never shows how `build_compiler_hints()` is refactored to use the profile. Either:
  - Add `compile_assertions(verifiers: dict) -> dict[str, CompiledExpression]` to the protocol, OR
  - Refactor `build_compiler_hints()` to loop over verifiers and call `profile.compile_condition()` per condition (making the batch function profile-aware)

  **Impact:** Without this, the compiler hints in prompts will still use the old `tla_compiler.compile_assertions()` hardcoded to Python, even when `--lang rust` is passed.

- ⚠️ **C2: `CompiledExpression` vs `CompiledAssertion` dual types** — Plan introduces `CompiledExpression(target_expr, original_tla, variables_used)` in `lang.py` alongside the existing `CompiledAssertion(python_expr, original_tla, variables_used)` in `tla_compiler.py`. Plan says "backwards-compat alias in tla_compiler.py during transition" but doesn't specify HOW. Options:
  - Make `CompiledAssertion` a type alias for `CompiledExpression` with a `python_expr` property
  - Have `CompiledAssertion` inherit from `CompiledExpression` with a renamed field
  - Delete `CompiledAssertion` and update all 8 existing tests that assert on `.python_expr`

  **Impact:** Without a clear migration path, the impl LLM will likely leave both types alive indefinitely.

- ⚠️ **C3: `VerifyResult` location** — All 4 language profiles import `VerifyResult` from `test_gen_loop.py`. This couples every backend to the Python test gen module. Consider moving `VerifyResult` to `lang.py` or a shared `types` module.

  **Impact:** Circular import risk if `test_gen_loop.py` ever needs to import from language backend modules.

- ⚠️ **C4: Go quantifier compilation produces statements, not expressions** — `compile_condition()` returns a `CompiledExpression` with a `target_expr: str` field. The plan says Go quantifiers compile to `for _, x := range s { assert P }` — but that's a *statement block*, not an expression. Python uses `all(... for x in ...)` (expression), TS uses `.every((x) => ...)` (expression), Rust uses `.iter().all(|x| ...)` (expression). Go breaks this pattern.

  **Impact:** The `target_expr` field cannot hold a for-loop. Either:
  - Go quantifiers emit helper function calls: `allSatisfy(s, func(x T) bool { return P })` — requires emitting helper function definitions alongside
  - Change `CompiledExpression` to have both `target_expr` (inline expression) and `helper_defs` (required preamble code)
  - Accept that Go compiled assertions are hints, not executable code (matches how `python_expr` is actually used — as prompt enrichment, not eval'd code)

### Recommendations:
1. Add `compile_assertions()` to `LanguageProfile` protocol or refactor `build_compiler_hints()` to be profile-aware
2. Specify the `CompiledAssertion` → `CompiledExpression` migration as an explicit behavior with tests
3. Move `VerifyResult` out of `test_gen_loop.py` into a shared location
4. Document that Go quantifiers compile to helper function references, add `helper_defs: str = ""` to `CompiledExpression` if needed

---

## Interface Review

### Well-Defined:
- ✅ **`LanguageProfile` protocol surface** — 7 methods + 2 properties covers all coupling points
- ✅ **`PythonProfile` delegates to existing code** — thin wrappers around `tla_compiler.compile_condition()`, `test_gen_loop.discover_api_context()`, etc. Zero behavior change.
- ✅ **CLI `--lang` flag** — `choices=["python", "typescript", "rust", "go"]`, defaults to `"python"`. Backwards-compatible.
- ✅ **Per-language file organization** — `lang.py` (protocol + Python), `lang_typescript.py`, `lang_rust.py`, `lang_go.py`. Clean separation.

### Missing or Unclear:

- ❌ **I1: `test_file_name()` not in protocol** — Behavior 6 tests assert `profile.test_file_name(gwt_id)`, and Behaviors 17/23 test it on Rust/Go profiles. But the `LanguageProfile` protocol definition in Behavior 2 (lines 229-264) does NOT include `test_file_name()`. It's tested but not declared.

  **Impact:** `isinstance(profile, LanguageProfile)` will pass even without `test_file_name()`, since it's not in the protocol. Callers won't get type safety.

- ⚠️ **I2: `extract_code_from_response()` is near-identical across all 4 backends** — The implementations for Python, TS, Rust, Go only differ in the regex language tag (`python`, `typescript|ts`, `rust|rs`, `go|golang`). This is a clear case for a base implementation parameterized by `fence_language_tag`:
  ```python
  def extract_code_from_response(self, response: str) -> str:
      tag = self.fence_language_tag
      fenced = re.findall(rf"```(?:{tag})?\n(.*?)```", text, re.DOTALL)
      ...
  ```
  The plan's approach creates 4 copies of the same 10-line function.

  **Impact:** Not blocking, but the impl LLM should be told to extract a shared base method.

- ⚠️ **I3: Prompt builders have implicit contract with `run_test_gen_loop()`** — The plan refactors `build_test_plan_prompt()`, `build_codegen_prompt()`, and `build_retry_prompt()` to delegate to the profile. But these are module-level functions in `test_gen_loop.py` that take `ctx: TestGenContext` as a parameter. The plan's Behavior 4 says "Update build_test_plan_prompt() to call ctx.lang_profile.build_structural_patterns()" but doesn't show the full refactored signature. Does `run_test_gen_loop()` change? Does it pass the profile through?

  **Impact:** The impl LLM needs clear guidance on WHERE in the prompt-building chain the profile methods are called.

### Recommendations:
1. Add `test_file_name(gwt_id: str) -> str` to the `LanguageProfile` protocol definition
2. Provide a default `extract_code_from_response()` implementation (mixin or base class) parameterized by `fence_language_tag`
3. Show the refactored `build_test_plan_prompt()` and `build_codegen_prompt()` signatures explicitly

---

## Promise Review

### Well-Defined:
- ✅ **Backwards compatibility** — Phase 1 strangler-fig: `cw9 gen-tests gwt-0024` (no flag) produces identical output to today. Gate check at Phase 1 checkpoint.
- ✅ **TDD invariant** — Every behavior has Red→Green→Refactor. No code written without a failing test first.
- ✅ **Full test suite must pass at each phase checkpoint** — explicit gates at Phase 1/2/3/4.
- ✅ **Async compatibility** — `run_test_gen_loop()` is async, plan doesn't change this.

### Missing or Unclear:

- ⚠️ **P1: Integration test markers not configured** — Plan mentions `@pytest.mark.integration` for TS/Rust/Go verification tests (lines 918, 1366, 1875) but doesn't show:
  - How to register the `integration` mark in `pytest.ini` / `pyproject.toml`
  - How to skip these tests when tools aren't installed (e.g., `skipIf(shutil.which("cargo") is None)`)
  - Whether CI runs integration tests or only unit tests

  **Impact:** Without configuration, pytest will emit `PytestUnknownMarkWarning`. Tests will fail in environments without TS/Rust/Go toolchains.

- ⚠️ **P2: No idempotency guarantee for profile construction** — `get_profile()` creates a new instance on every call. For the current stateless profiles this is fine, but if profiles ever cache state (e.g., discovered API context), this becomes a problem.

  **Impact:** Low risk, but worth documenting that profiles should be stateless.

### Recommendations:
1. Add a behavior for pytest mark registration and tool-availability skip decorators
2. Document that `LanguageProfile` implementations must be stateless

---

## Data Model Review

### Well-Defined:
- ✅ **`TargetLanguage` enum** — `str` enum with 4 values. String round-trip works. Clean.
- ✅ **`TestGenContext` field rename** — `python_dir` → `source_dir`. All callers listed.
- ✅ **Bridge artifacts remain untouched** — language-neutral JSON, no changes needed.

### Missing or Unclear:

- ⚠️ **D1: `CompiledExpression` duplicates `CompiledAssertion`** — (See C2 above) Two dataclasses with the same 3 fields but different names. Need explicit migration behavior.

- ⚠️ **D2: `TestGenContext.lang_profile` default** — Plan says `default_factory=PythonProfile`. This means every existing `TestGenContext(...)` construction site (including tests) doesn't need updating. But it also means `lang_profile` is always `PythonProfile` unless explicitly overridden. Verify this is the intended behavior for `cmd_gen_tests()` — the profile should come from `get_profile(TargetLanguage(args.lang))`, not the default.

  **Impact:** If the impl LLM forgets to pass the profile in `cmd_gen_tests()`, everything silently uses Python even with `--lang rust`.

- ⚠️ **D3: `ProjectContext.python_dir` field name unchanged** — The plan renames `TestGenContext.python_dir` → `source_dir` but leaves `ProjectContext.python_dir` as-is (line C9 in plan). Since `cli.py:338` passes `ctx.python_dir` to `discover_api_context()`, this is a semantic mismatch: the context field is still called `python_dir` but the profile may be discovering TypeScript or Rust sources.

  **Impact:** Confusing but not functionally broken — `python_dir` in installed mode resolves to `target_root`, which works for any language. Consider renaming to `source_dir` on `ProjectContext` too, or at least adding a comment.

### Recommendations:
1. Make the `CompiledAssertion` → `CompiledExpression` migration an explicit TDD behavior
2. Add a test that `cmd_gen_tests(..., --lang rust)` passes a `RustProfile` (not `PythonProfile`) to `TestGenContext`
3. Consider renaming `ProjectContext.python_dir` → `source_dir` in a follow-up

---

## API Review

### Well-Defined:
- ✅ **CLI API** — `cw9 gen-tests <gwt-id> [target_dir] --lang {python,typescript,rust,go} --max-attempts N`. Backwards-compatible, `--lang` defaults to `python`.
- ✅ **Library API** — `get_profile(TargetLanguage) -> LanguageProfile`. Clean factory pattern.
- ✅ **No external API changes** — bridge artifacts, DAG JSON, schema format all unchanged.

### Recommendations:
- None. API surface is clean.

---

## Critical Issues (Must Address Before Implementation)

### 1. **`compile_assertions()` not routed through profile** (C1)
- **Impact:** Compiler hints in LLM prompts will always be Python expressions regardless of `--lang` flag. The LLM generating Rust tests will see `all(x in S for x in impact_set)` instead of `s.iter().all(|x| S.contains(&x))`.
- **Recommendation:** Add `compile_assertions(verifiers: dict) -> dict[str, CompiledExpression]` to `LanguageProfile`, or refactor `build_compiler_hints()` to accept a profile and call `profile.compile_condition()` per condition.

### 2. **`test_file_name()` missing from protocol** (I1)
- **Impact:** Type checker won't catch missing implementations. Runtime `AttributeError` when `run_test_gen_loop()` calls `ctx.lang_profile.test_file_name(gwt_id)`.
- **Recommendation:** Add to the `LanguageProfile` protocol definition in Behavior 2.

### 3. **Go quantifier compilation is statement-level** (C4)
- **Impact:** `target_expr` field expects a string expression, but Go quantifiers require for-loops (statements). Impl LLM will either produce broken Go or skip quantifier compilation entirely.
- **Recommendation:** Document that compiled expressions are *prompt hints* not executable code. If needed, add `helper_defs: str = ""` to `CompiledExpression`.

---

## Suggested Plan Amendments

```diff
# In Behavior 2: LanguageProfile protocol

+ Add test_file_name(gwt_id: str) -> str to protocol definition
+ Add compile_assertions(verifiers: dict, state_var: str = "state") -> dict[str, CompiledExpression]
  OR document that build_compiler_hints() will be refactored to use compile_condition() per condition

# In Behavior 3: PythonProfile

+ Add explicit behavior for CompiledAssertion → CompiledExpression migration
+ Include test: assert compile_condition("x \\in S").target_expr == old_compile_condition("x \\in S").python_expr

# In Behavior 4: TestGenContext refactor

+ Add test: cmd_gen_tests with --lang rust passes RustProfile (not default PythonProfile)
~ Clarify: build_compiler_hints() must accept lang_profile parameter

# In Phase 2 (TypeScript) — new behavior

+ Add: Register pytest "integration" mark in conftest.py or pyproject.toml
+ Add: skipIf decorator for tool availability (shutil.which("npx"), "cargo", "go")

# Cross-cutting

+ Extract base extract_code_from_response() implementation parameterized by fence_language_tag
+ Move VerifyResult to lang.py or a shared types module
```

---

## Drift Risk Assessment (Orchestrator Perspective)

Cross-referencing with orchestration assessment (msg #555):

| Drift Risk | Plan Mitigation | Status |
|------------|-----------------|--------|
| D1: All 4 backends simultaneously | Phase 1-4 sequencing with gates | ✅ Mitigated |
| D2: ABC without Python refactor | Phase 1 = strangler-fig on Python | ✅ Mitigated |
| D3: Parallel code paths (if/elif) | `get_profile()` single dispatch | ✅ Mitigated |
| D4: Missing `discover_api_context()` | Included as protocol method | ✅ Mitigated |
| D5: No TDD for compilers | Every behavior has Red→Green→Refactor | ✅ Mitigated |
| D6: Cosmetic prompt refactor | 3 prompt builders delegate to profile | ✅ Mitigated |
| **NEW D7:** `compile_assertions()` bypass | Not addressed in plan | ❌ **Gap** |
| **NEW D8:** `test_file_name()` not in protocol | Missing from Behavior 2 | ❌ **Gap** |

---

## Approval Status

- [x] **Ready for Implementation** — All critical issues resolved
- [ ] **Needs Minor Revision** — Address C1 (`compile_assertions` routing), I1 (`test_file_name` in protocol), and C4 (Go quantifier documentation) before proceeding
- [ ] **Needs Major Revision** — Critical issues must be resolved first

**Verdict:** Plan revised 2026-03-10. All review findings addressed:
- ✅ C1: `compile_assertions()` added to protocol, `build_compiler_hints()` refactored to use profile
- ✅ I1: `test_file_name()` added to protocol definition in B2
- ✅ C4: Go quantifier strategy documented — helper functions via `CompiledExpression.helper_defs`
- ✅ C2: `CompiledAssertion` → `CompiledExpression` migration explicitly tested in B3
- ✅ C3: `VerifyResult` moved to `lang.py`
- ✅ I2: Shared `_extract_code_by_fence_tag()` replaces 4 duplicate implementations
- ✅ I3: Prompt builder signatures shown explicitly in B4 refactor
- ✅ P1: Integration mark registered, auto-skip conftest added in B5b
- ✅ P2: Statelessness documented on protocol
- ✅ D2: Test added that `--lang rust` passes `RustProfile` (not default `PythonProfile`)
- ✅ D3: `ProjectContext.python_dir` noted for follow-up rename (not blocking)
