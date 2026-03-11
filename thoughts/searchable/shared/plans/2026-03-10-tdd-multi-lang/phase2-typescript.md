---
date: 2026-03-10
parent: INDEX.md
phase: 2
title: "Phase 2: TypeScript Implementation"
behaviors: [B7, B8, B9, B10, B11]
status: draft
---

# Phase 2: TypeScript Implementation

## Behavior 7: TypeScript assertion compiler

### Test Specification
**Given**: TLA+ condition `x \in S /\ y = 3`
**When**: Compiling for TypeScript
**Then**: Produces `S.includes(x) && y === 3`

**Given**: `\A x \in S : x > 0`
**When**: Compiling for TypeScript
**Then**: Produces `S.every((x) => x > 0)`

**Given**: `Len(seq) > 0`
**When**: Compiling for TypeScript
**Then**: Produces `seq.length > 0`

**Given**: `Cardinality(S) = 3`
**When**: Compiling for TypeScript
**Then**: Produces `S.size === 3` (Set) or `S.length === 3` (Array)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
class TestTypeScriptCompiler:
    def setup_method(self):
        self.profile = TypeScriptProfile()

    def test_membership(self):
        r = self.profile.compile_condition("x \\in S")
        assert ".includes(x)" in r.target_expr or "S.has(x)" in r.target_expr

    def test_conjunction(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "&&" in r.target_expr

    def test_equality(self):
        r = self.profile.compile_condition("y = 3")
        assert "===" in r.target_expr

    def test_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert ".every(" in r.target_expr

    def test_existential_quantifier(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert ".some(" in r.target_expr

    def test_len(self):
        r = self.profile.compile_condition("Len(seq) > 0")
        assert ".length" in r.target_expr

    def test_cardinality(self):
        r = self.profile.compile_condition("Cardinality(S) = 3")
        assert ".size" in r.target_expr or ".length" in r.target_expr

    def test_boolean_literals(self):
        r = self.profile.compile_condition("x = TRUE")
        assert "true" in r.target_expr  # lowercase JS booleans

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.count" in r.target_expr  # JS uses dot access natively

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!==" in r.target_expr

    def test_unsupported_raises(self):
        from registry.lang import CompileError
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")

    # --- compile_assertions (batch) ---

    def test_compile_assertions_produces_ts_expressions(self):
        """Verifies compiler hints use TypeScript, not Python."""
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        # Must produce TS syntax (.includes), not Python (in)
        assert ".includes(" in results["inv_membership"].target_expr or ".has(" in results["inv_membership"].target_expr

    # --- test_file_name ---

    def test_file_name_typescript(self):
        assert self.profile.test_file_name("gwt-0024") == "gwt_0024.test.ts"
```

#### Green
**File**: `python/registry/lang_typescript.py`
```python
class TypeScriptProfile:
    test_file_extension = ".test.ts"
    fence_language_tag = "typescript|ts"  # regex alternation for fence extraction

    def compile_condition(self, tla_expr, state_var="state"):
        # TypeScript-specific TLA+ → JS/TS expression compilation
        ...

    def compile_assertions(self, verifiers, state_var="state"):
        # Default: loop over verifiers, call compile_condition() per condition
        results = {}
        for name, v in verifiers.items():
            if condition := v.get("condition", ""):
                results[name] = self.compile_condition(condition, state_var)
        return results

    def test_file_name(self, gwt_id):
        safe_id = gwt_id.replace("-", "_")
        return f"{safe_id}.test.ts"

    def extract_code_from_response(self, response):
        return _extract_code_by_fence_tag(response, self.fence_language_tag)
```

Implements the mapping:
| TLA+ | TypeScript |
|------|-----------|
| `\in` | `.includes()` or `.has()` |
| `/\` | `&&` |
| `\/` | `\|\|` |
| `=` | `===` |
| `#` | `!==` |
| `\A x \in S : P` | `S.every((x) => P)` |
| `\E x \in S : P` | `S.some((x) => P)` |
| `Len(x)` | `x.length` |
| `Cardinality(S)` | `S.size` |
| `TRUE/FALSE` | `true/false` |
| `state.field` | `state.field` (no change needed) |

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestTypeScriptCompiler` passes
- [x] Full suite still passes

---

## Behavior 8: TypeScript API context discovery

### Test Specification
**Given**: A directory with `.ts` files containing `export function`, `export class`, `export interface`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the exported signatures

### TDD Cycle

#### Red: Write Failing Test
```python
class TestTypeScriptApiDiscovery:
    def test_finds_exported_functions(self, tmp_path):
        profile = TypeScriptProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "dag.ts").write_text(
            "export class RegistryDag {\n"
            "  queryImpact(nodeId: string): ImpactResult { }\n"
            "}\n"
            "export function loadDag(path: string): RegistryDag { }\n"
        )
        result = profile.discover_api_context(tmp_path, "RegistryDag")
        assert "export class RegistryDag" in result
        assert "export function loadDag" in result

    def test_finds_interfaces(self, tmp_path):
        profile = TypeScriptProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "types.ts").write_text(
            "export interface Node {\n  id: string;\n}\n"
        )
        result = profile.discover_api_context(tmp_path, "Node")
        assert "export interface Node" in result

    def test_no_source_returns_comment(self, tmp_path):
        profile = TypeScriptProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result
```

#### Green
Implement `TypeScriptProfile.discover_api_context()`:
- Glob for `*.ts` files matching module name (camelCase and kebab-case)
- Extract lines starting with `export function`, `export class`, `export interface`, `export type`, `import`

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestTypeScriptApiDiscovery` passes

---

## Behavior 9: TypeScript prompts and structural patterns

### Test Specification
**Given**: `TypeScriptProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions TypeScript, Jest/Vitest, not Python/pytest

**When**: Calling `build_structural_patterns()`
**Then**: Contains `describe(`, `it(`, `expect(`, TypeScript import syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains `import { ... } from` syntax

### TDD Cycle

#### Red: Write Failing Test
```python
class TestTypeScriptPrompts:
    def setup_method(self):
        self.profile = TypeScriptProfile()

    def test_system_prompt_mentions_typescript(self):
        prompt = self.profile.build_system_prompt()
        assert "TypeScript" in prompt
        assert "Python" not in prompt

    def test_system_prompt_mentions_test_framework(self):
        prompt = self.profile.build_system_prompt()
        assert "jest" in prompt.lower() or "vitest" in prompt.lower()

    def test_structural_patterns_has_ts_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "describe(" in patterns
        assert "expect(" in patterns
        assert "import" in patterns

    def test_import_instructions_has_ts_syntax(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "import {" in instructions or "import type" in instructions
```

#### Green
Implement the three prompt methods with TypeScript-idiomatic code examples.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestTypeScriptPrompts` passes

---

## Behavior 10: TypeScript test file verification

### Test Specification
**Given**: A valid `.test.ts` file
**When**: Calling `verify_test_file()`
**Then**: Runs `tsc --noEmit` → `npx jest --listTests` → `npx jest`

**Given**: A `.test.ts` file with a type error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

### TDD Cycle

#### Red: Write Failing Test
```python
class TestTypeScriptVerification:
    def test_verify_catches_syntax_error(self, tmp_path):
        profile = TypeScriptProfile()
        test_file = tmp_path / "bad.test.ts"
        test_file.write_text("const x: string = 42;")  # type error
        result = profile.verify_test_file(test_file, tmp_path)
        assert not result.passed
        assert result.stage == "compile"

    def test_verify_passes_valid_test(self, tmp_path):
        profile = TypeScriptProfile()
        test_file = tmp_path / "ok.test.ts"
        test_file.write_text(
            'describe("test", () => {\n'
            '  it("works", () => {\n'
            '    expect(1 + 1).toBe(2);\n'
            '  });\n'
            '});\n'
        )
        # This test requires tsc + jest in PATH — mark as integration
        result = profile.verify_test_file(test_file, tmp_path)
        assert result.passed
```

**Note**: Tests that invoke `tsc`/`jest` MUST be marked `@pytest.mark.integration`.
The `conftest.py` auto-skip logic (added in B5b) handles skipping when `npx` isn't installed.

```python
@pytest.mark.integration
class TestTypeScriptVerification:
    ...
```

#### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess, sys
    from registry.lang import VerifyResult

    # Stage 1: Type check
    result = subprocess.run(
        ["npx", "tsc", "--noEmit", str(test_path)],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="compile",
                          errors=[f"tsc failed (rc={result.returncode})"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 2: Test discovery
    result = subprocess.run(
        ["npx", "jest", "--listTests", str(test_path)],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="collect",
                          errors=[f"jest --listTests failed"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 3: Run
    result = subprocess.run(
        ["npx", "jest", str(test_path), "--no-coverage"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="run",
                          errors=[f"jest failed"],
                          stdout=result.stdout, stderr=result.stderr)

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestTypeScriptVerification` passes (with mocked subprocess or integration mark)

---

## Behavior 11: TypeScript code extraction from LLM response

### Test Specification
**Given**: LLM response with `` ```typescript\n...code...\n``` ``
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the TypeScript code without fences

### TDD Cycle

#### Red: Write Failing Test
```python
class TestTypeScriptExtraction:
    def test_strips_typescript_fences(self):
        profile = TypeScriptProfile()
        response = '```typescript\ndescribe("test", () => {});\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith('describe("test"')
        assert "```" not in code

    def test_strips_ts_fences(self):
        profile = TypeScriptProfile()
        response = '```ts\nconst x = 1;\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code
```

#### Green
```python
def extract_code_from_response(self, response: str) -> str:
    # Delegates to shared helper from lang.py (B2 refactor)
    return _extract_code_by_fence_tag(response, self.fence_language_tag)
    # fence_language_tag = "typescript" matches both ```typescript and ```ts via
    # the pattern "typescript|ts" — the shared helper handles this by using
    # fence_language_tag as-is. TypeScriptProfile sets:
    #   fence_language_tag = "typescript|ts"
    # to match both variants.
```

**Note**: `fence_language_tag` for TypeScript is `"typescript|ts"` (regex alternation)
to handle both common fence styles. The shared `_extract_code_by_fence_tag()` uses
this directly in the regex pattern.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestTypeScriptExtraction` passes

---

## Phase 2 Checkpoint

At this point:
- `TypeScriptProfile` fully implements `LanguageProfile`
- `cw9 gen-tests gwt-0024 --lang typescript` produces `.test.ts` files
- Python path is unchanged
- Abstraction is validated by two implementations

**Gate**: `pytest` full suite passes. Manual: `cw9 gen-tests gwt-0024 --lang typescript`
on a project with `.ts` source files.
