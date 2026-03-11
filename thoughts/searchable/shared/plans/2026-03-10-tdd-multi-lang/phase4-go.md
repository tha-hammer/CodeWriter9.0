---
date: 2026-03-10
parent: INDEX.md
phase: 4
title: "Phase 4: Go Implementation"
behaviors: [B18, B19, B20, B21, B22, B23, B24]
status: draft
---

# Phase 4: Go Implementation

## Behavior 18: Go assertion compiler

### Test Specification
**Given**: TLA+ condition `x \in S /\ y = 3`
**When**: Compiling for Go
**Then**: Produces `slices.Contains(s, x) && y == 3`

**Given**: `\A x \in S : x > 0`
**When**: Compiling for Go
**Then**: Produces a for-loop with assertion (Go lacks iterator methods)

**Given**: `Len(seq) > 0`
**When**: Compiling for Go
**Then**: Produces `len(seq) > 0`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_go.py`
```python
import pytest
from registry.lang import GoProfile, CompileError


class TestGoCompiler:
    def setup_method(self):
        self.profile = GoProfile()

    def test_membership(self):
        r = self.profile.compile_condition("x \\in S")
        assert "slices.Contains(" in r.target_expr or "Contains(" in r.target_expr

    def test_conjunction(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "&&" in r.target_expr

    def test_equality(self):
        r = self.profile.compile_condition("y = 3")
        assert "==" in r.target_expr

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!=" in r.target_expr

    def test_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        # Go uses for-range loops, not iterator methods
        expr = r.target_expr
        assert "for" in expr or "allSatisfy" in expr

    def test_existential_quantifier(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        expr = r.target_expr
        assert "for" in expr or "anySatisfy" in expr

    def test_len(self):
        r = self.profile.compile_condition("Len(seq) > 0")
        assert "len(seq)" in r.target_expr or "len(" in r.target_expr

    def test_cardinality(self):
        r = self.profile.compile_condition("Cardinality(S) = 3")
        assert "len(" in r.target_expr

    def test_boolean_literals(self):
        r = self.profile.compile_condition("x = TRUE")
        assert "true" in r.target_expr

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.Count" in r.target_expr or "state.count" in r.target_expr

    def test_disjunction(self):
        r = self.profile.compile_condition("x = 1 \\/ y = 2")
        assert "||" in r.target_expr

    def test_unsupported_raises(self):
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")

    # --- helper_defs for quantifiers (C4 resolution) ---

    def test_universal_quantifier_has_helper_defs(self):
        """Go quantifiers need helper function definitions (unlike Python/TS/Rust)."""
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert r.helper_defs != ""  # Must provide preamble code
        assert "func " in r.helper_defs  # Contains a Go function definition
        assert "allSatisfy" in r.target_expr or "for" in r.target_expr

    def test_existential_quantifier_has_helper_defs(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert r.helper_defs != ""
        assert "func " in r.helper_defs
        assert "anySatisfy" in r.target_expr or "for" in r.target_expr

    def test_non_quantifier_has_empty_helper_defs(self):
        """Simple conditions don't need helper functions."""
        r = self.profile.compile_condition("x = 3")
        assert r.helper_defs == ""

    # --- compile_assertions (batch) ---

    def test_compile_assertions_produces_go_expressions(self):
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert "Contains(" in results["inv_membership"].target_expr or "contains" in results["inv_membership"].target_expr.lower()
```

#### Green
**File**: `python/registry/lang_go.py`

Implements the mapping:
| TLA+ | Go |
|------|-----|
| `\in` | `slices.Contains(s, x)` |
| `/\` | `&&` |
| `\/` | `\|\|` |
| `=` | `==` |
| `#` | `!=` |
| `\A x \in S : P` | `for _, x := range s { assert P }` (helper func) |
| `\E x \in S : P` | `for _, x := range s { if P { found = true } }` (helper func) |
| `Len(x)` | `len(x)` |
| `Cardinality(S)` | `len(s)` |
| `TRUE/FALSE` | `true/false` |
| `state.field` | `state.Field` (exported/capitalized) |

**Go quantifier compilation strategy** (addresses review issue C4):

Go lacks expression-level iterator methods (`all()`, `.every()`, `.iter().all()`).
Quantifiers compile to **helper function references** that are emitted as `helper_defs`.
The `CompiledExpression.helper_defs` field (added in B2) carries the required preamble:

```python
# Example: \A x \in S : x > 0
CompiledExpression(
    target_expr="allSatisfy(s, func(x int) bool { return x > 0 })",
    original_tla="\\A x \\in S : x > 0",
    variables_used=["s", "x"],
    helper_defs=(
        "func allSatisfy[T any](s []T, pred func(T) bool) bool {\n"
        "\tfor _, x := range s {\n"
        "\t\tif !pred(x) { return false }\n"
        "\t}\n"
        "\treturn true\n"
        "}\n"
    ),
)
```

Compiled expressions are **prompt hints** — they enrich the LLM's context, they are
not eval'd. The helper_defs are included in the prompt alongside the assertion
expression so the LLM sees both the helper signature and its usage.

For Python/TS/Rust where quantifiers are single expressions, `helper_defs` is empty
(the default `""`). Only Go needs it.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoCompiler` passes
- [x] Full suite still passes

---

## Behavior 19: Go API context discovery

### Test Specification
**Given**: A directory with `.go` files containing `func `, `type ... struct`, `type ... interface`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the exported signatures

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_go.py` (append)
```python
class TestGoApiDiscovery:
    def test_finds_exported_functions(self, tmp_path):
        profile = GoProfile()
        (tmp_path / "dag.go").write_text(
            "package registry\n\n"
            "// RegistryDag manages the dependency graph.\n"
            "type RegistryDag struct {\n"
            "\tnodes []Node\n"
            "}\n\n"
            "// QueryImpact returns impacted nodes.\n"
            "func (d *RegistryDag) QueryImpact(nodeID string) *ImpactResult {\n"
            "\treturn nil\n"
            "}\n\n"
            "// NewDag creates a new RegistryDag.\n"
            "func NewDag() *RegistryDag {\n"
            "\treturn &RegistryDag{}\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "RegistryDag")
        assert "type RegistryDag struct" in result
        assert "func (d *RegistryDag) QueryImpact" in result or "QueryImpact" in result
        assert "func NewDag" in result

    def test_finds_interfaces(self, tmp_path):
        profile = GoProfile()
        (tmp_path / "types.go").write_text(
            "package registry\n\n"
            "type Queryable interface {\n"
            "\tQuery(id string) (*Node, error)\n"
            "}\n\n"
            "type EdgeType int\n\n"
            "const (\n"
            "\tImports EdgeType = iota\n"
            "\tExports\n"
            ")\n"
        )
        result = profile.discover_api_context(tmp_path, "Queryable")
        assert "type Queryable interface" in result

    def test_no_source_returns_comment(self, tmp_path):
        profile = GoProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result
```

#### Green
Implement `GoProfile.discover_api_context()`:
- Glob for `*.go` files (excluding `*_test.go`)
- Extract lines with `func `, `type ... struct`, `type ... interface`, `const`, `var`
- Include doc comments (`//`) preceding exported items

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoApiDiscovery` passes

---

## Behavior 20: Go prompts and structural patterns

### Test Specification
**Given**: `GoProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions Go, `testing` package, not Python/Rust/TS

**When**: Calling `build_structural_patterns()`
**Then**: Contains `func Test`, `t.Run(`, `t.Errorf`, Go import syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains Go `import` statements

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_go.py` (append)
```python
class TestGoPrompts:
    def setup_method(self):
        self.profile = GoProfile()

    def test_system_prompt_mentions_go(self):
        prompt = self.profile.build_system_prompt()
        assert "Go" in prompt
        assert "Python" not in prompt
        assert "Rust" not in prompt

    def test_system_prompt_mentions_testing_package(self):
        prompt = self.profile.build_system_prompt()
        assert "testing" in prompt

    def test_structural_patterns_has_go_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "func Test" in patterns
        assert "t.Run(" in patterns or "t.Errorf(" in patterns or "t.Fatal" in patterns

    def test_structural_patterns_has_import(self):
        patterns = self.profile.build_structural_patterns()
        assert "import" in patterns

    def test_import_instructions_has_go_syntax(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "import" in instructions
```

#### Green
```python
class GoProfile:
    def build_system_prompt(self) -> str:
        return (
            "You are a Go test generation expert. You generate complete, runnable "
            "Go test files from formal specifications and API documentation. "
            "You use ONLY the real package imports provided — never create mock structs "
            "or re-implement the API. Use the standard testing package with table-driven "
            "tests where appropriate. Output ONLY Go code, no markdown fencing or explanation."
        )

    def build_structural_patterns(self) -> str:
        return (
            "```go\n"
            "package registry_test\n\n"
            "import (\n"
            "\t\"testing\"\n\n"
            "\t\"example.com/project/registry\"\n"
            ")\n\n"
            "// Pattern: fixture construction from trace Init state\n"
            "func makeDag(t *testing.T, nodes []string, edges [][2]string) *registry.RegistryDag {\n"
            "\tt.Helper()\n"
            "\tdag := registry.NewDag()\n"
            "\tfor _, nid := range nodes {\n"
            "\t\tdag.AddNode(registry.NewBehaviorNode(nid, nid, \"g\", \"w\", \"t\"))\n"
            "\t}\n"
            "\tfor _, e := range edges {\n"
            "\t\tdag.AddEdge(registry.NewEdge(e[0], e[1], registry.Imports))\n"
            "\t}\n"
            "\treturn dag\n"
            "}\n\n"
            "func TestInvariant(t *testing.T) {\n"
            "\tdag := makeDag(t, []string{\"a\", \"b\"}, [][2]string{{\"a\", \"b\"}})\n"
            "\tresult := dag.QueryImpact(\"a\")\n"
            "\tif len(result) == 0 {\n"
            "\t\tt.Fatal(\"expected non-empty impact result\")\n"
            "\t}\n"
            "}\n\n"
            "// Pattern: table-driven test\n"
            "func TestEdgeCases(t *testing.T) {\n"
            "\ttests := []struct {\n"
            "\t\tname   string\n"
            "\t\tinput  string\n"
            "\t\twantErr bool\n"
            "\t}{\n"
            "\t\t{\"empty input\", \"\", true},\n"
            "\t\t{\"valid node\", \"a\", false},\n"
            "\t}\n"
            "\tfor _, tt := range tests {\n"
            "\t\tt.Run(tt.name, func(t *testing.T) {\n"
            "\t\t\t// test body\n"
            "\t\t})\n"
            "\t}\n"
            "}\n"
            "```\n"
        )

    def build_import_instructions(self, module_name: str) -> str:
        return (
            f"- CRITICAL: Use EXACT import paths from the API Context section above.\n"
            f"  Use `import \"{module_name}/registry\"` for the main package\n"
            f"- Test files must use `package registry_test` (external test package)\n"
            f"  or `package registry` (internal/white-box test)\n"
            f"- Use `testing` package — do NOT import testify unless it's in the project\n"
        )
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoPrompts` passes

---

## Behavior 21: Go test file verification

### Test Specification
**Given**: A valid `_test.go` file
**When**: Calling `verify_test_file()`
**Then**: Runs `go vet` → `go test -list .` → `go test -v`

**Given**: A `_test.go` file with a compile error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_go.py` (append)
```python
class TestGoVerification:
    def test_verify_catches_compile_error(self, tmp_path):
        profile = GoProfile()
        test_file = tmp_path / "bad_test.go"
        test_file.write_text("package main\n\nfunc Test() { x := }")
        result = profile.verify_test_file(test_file, tmp_path)
        assert not result.passed
        assert result.stage == "compile"

    def test_verify_passes_valid_test(self, tmp_path):
        """Integration test — requires go in PATH."""
        profile = GoProfile()
        # Set up minimal Go module
        (tmp_path / "go.mod").write_text(
            "module testmod\n\ngo 1.21\n"
        )
        (tmp_path / "main.go").write_text(
            "package testmod\n\nfunc Add(a, b int) int { return a + b }\n"
        )
        (tmp_path / "main_test.go").write_text(
            "package testmod\n\n"
            "import \"testing\"\n\n"
            "func TestAdd(t *testing.T) {\n"
            "\tif Add(2, 3) != 5 {\n"
            "\t\tt.Fatal(\"expected 5\")\n"
            "\t}\n"
            "}\n"
        )
        result = profile.verify_test_file(tmp_path / "main_test.go", tmp_path)
        assert result.passed
```

**Note**: Tests that invoke `go` MUST be marked `@pytest.mark.integration`.
The `conftest.py` auto-skip logic (added in B5b) handles skipping when `go` isn't installed.

```python
@pytest.mark.integration
class TestGoVerification:
    ...
```

#### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess
    from registry.lang import VerifyResult

    # Stage 1: Vet (includes compile check)
    result = subprocess.run(
        ["go", "vet", "./..."],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="compile",
                          errors=[f"go vet failed (rc={result.returncode})"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 2: Test discovery
    result = subprocess.run(
        ["go", "test", "-list", ".", "./..."],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="collect",
                          errors=[f"go test -list failed"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 3: Run tests
    result = subprocess.run(
        ["go", "test", "-v", "./..."],
        capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="run",
                          errors=[f"go test failed"],
                          stdout=result.stdout, stderr=result.stderr)

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoVerification` passes (with mocked subprocess or integration mark)

---

## Behavior 22: Go code extraction from LLM response

### Test Specification
**Given**: LLM response with `` ```go\n...code...\n``` ``
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the Go code without fences

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang_go.py` (append)
```python
class TestGoExtraction:
    def test_strips_go_fences(self):
        profile = GoProfile()
        response = '```go\npackage main\n\nimport "testing"\n\nfunc TestIt(t *testing.T) {}\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith("package main")
        assert "```" not in code

    def test_strips_golang_fences(self):
        profile = GoProfile()
        response = '```golang\npackage main\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code
        assert "package main" in code

    def test_handles_no_fences(self):
        profile = GoProfile()
        response = 'package main\n\nfunc TestIt(t *testing.T) {}'
        code = profile.extract_code_from_response(response)
        assert "package main" in code
```

#### Green
```python
def extract_code_from_response(self, response: str) -> str:
    # Delegates to shared helper from lang.py (B2 refactor)
    return _extract_code_by_fence_tag(response, self.fence_language_tag)
    # fence_language_tag = "go|golang" matches both ```go and ```golang
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoExtraction` passes

---

## Behavior 23: Go output file naming

### Test Specification
**Given**: `GoProfile` and a gwt_id
**When**: Calling `test_file_name(gwt_id)`
**Then**: Returns Go-idiomatic test file name (`_test.go` suffix)

### TDD Cycle

#### Red: Write Failing Test
```python
class TestGoOutputPath:
    def test_go_output_path(self):
        profile = GoProfile()
        gwt_id = "gwt-0024"
        expected = "gwt_0024_test.go"
        assert profile.test_file_name(gwt_id) == expected

    def test_go_file_extension(self):
        profile = GoProfile()
        assert profile.test_file_extension == "_test.go"

    def test_go_fence_tag(self):
        profile = GoProfile()
        assert profile.fence_language_tag == "go"
```

#### Green
```python
class GoProfile:
    test_file_extension: str = "_test.go"
    fence_language_tag: str = "go|golang"  # regex alternation for fence extraction

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"{safe_id}_test.go"

    def compile_assertions(self, verifiers, state_var="state"):
        results = {}
        for name, v in verifiers.items():
            if condition := v.get("condition", ""):
                results[name] = self.compile_condition(condition, state_var)
        return results

    def extract_code_from_response(self, response):
        return _extract_code_by_fence_tag(response, self.fence_language_tag)
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang_go.py::TestGoOutputPath` passes

---

## Phase 4 Checkpoint

At this point:
- `GoProfile` fully implements `LanguageProfile`
- `cw9 gen-tests gwt-0024 --lang go` produces `_test.go` files
- All four language paths work: Python, TypeScript, Rust, Go
- Four implementations prove the `LanguageProfile` abstraction generalizes

**Gate**: `pytest` full suite passes. Manual: `cw9 gen-tests gwt-0024 --lang go`
on a project with `.go` source files.

---

## Behavior 24: get_profile() factory returns all four profiles

### Test Specification
**Given**: `get_profile(TargetLanguage.RUST)`
**When**: Called
**Then**: Returns a `RustProfile` instance

**Given**: `get_profile(TargetLanguage.GO)`
**When**: Called
**Then**: Returns a `GoProfile` instance

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
class TestGetProfileFactory:
    def test_python_profile(self):
        from registry.lang import get_profile, TargetLanguage, PythonProfile
        profile = get_profile(TargetLanguage.PYTHON)
        assert isinstance(profile, PythonProfile)

    def test_typescript_profile(self):
        from registry.lang import get_profile, TargetLanguage
        from registry.lang_typescript import TypeScriptProfile
        profile = get_profile(TargetLanguage.TYPESCRIPT)
        assert isinstance(profile, TypeScriptProfile)

    def test_rust_profile(self):
        from registry.lang import get_profile, TargetLanguage
        from registry.lang_rust import RustProfile
        profile = get_profile(TargetLanguage.RUST)
        assert isinstance(profile, RustProfile)

    def test_go_profile(self):
        from registry.lang import get_profile, TargetLanguage
        from registry.lang_go import GoProfile
        profile = get_profile(TargetLanguage.GO)
        assert isinstance(profile, GoProfile)

    def test_all_satisfy_protocol(self):
        from registry.lang import get_profile, TargetLanguage, LanguageProfile
        for lang in TargetLanguage:
            profile = get_profile(lang)
            assert isinstance(profile, LanguageProfile), f"{lang} profile doesn't satisfy protocol"
```

#### Green
Update `get_profile()` in `lang.py`:
```python
def get_profile(lang: TargetLanguage) -> LanguageProfile:
    if lang == TargetLanguage.PYTHON:
        return PythonProfile()
    elif lang == TargetLanguage.TYPESCRIPT:
        from registry.lang_typescript import TypeScriptProfile
        return TypeScriptProfile()
    elif lang == TargetLanguage.RUST:
        from registry.lang_rust import RustProfile
        return RustProfile()
    elif lang == TargetLanguage.GO:
        from registry.lang_go import GoProfile
        return GoProfile()
    raise ValueError(f"Unknown language: {lang}")
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestGetProfileFactory` passes
- [x] No `NotImplementedError` for any `TargetLanguage` value
- [x] Full suite: `pytest`
