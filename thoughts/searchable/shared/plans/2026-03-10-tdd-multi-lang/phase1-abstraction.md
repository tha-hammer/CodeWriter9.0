---
date: 2026-03-10
parent: INDEX.md
phase: 1
title: "Phase 1: Extract the Abstraction (Strangler Fig on Python)"
behaviors: [B1, B2, B3, B4, B5, B6]
status: draft
---

# Phase 1: Extract the Abstraction (Strangler Fig on Python)

## Behavior 1: TargetLanguage enum exists with known values

### Test Specification
**Given**: The `registry.lang` module exists
**When**: Importing `TargetLanguage`
**Then**: `TargetLanguage.PYTHON`, `.TYPESCRIPT`, `.RUST`, `.GO` are valid enum values
**Edge Cases**: String round-trip (`TargetLanguage("python")` works), unknown value raises

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py`
```python
import pytest
from registry.lang import TargetLanguage


class TestTargetLanguage:
    def test_python_exists(self):
        assert TargetLanguage.PYTHON.value == "python"

    def test_typescript_exists(self):
        assert TargetLanguage.TYPESCRIPT.value == "typescript"

    def test_rust_exists(self):
        assert TargetLanguage.RUST.value == "rust"

    def test_go_exists(self):
        assert TargetLanguage.GO.value == "go"

    def test_string_construction(self):
        assert TargetLanguage("python") == TargetLanguage.PYTHON

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            TargetLanguage("cobol")
```

#### Green: Minimal Implementation
**File**: `python/registry/lang.py`
```python
"""Target language definitions for multi-language test generation."""

from enum import Enum


class TargetLanguage(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
```

#### Refactor
None needed — enum is minimal.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py` — Red then Green
- [x] All existing tests still pass: `pytest`

---

## Behavior 2: LanguageProfile protocol defines the abstraction surface

### Test Specification
**Given**: A `LanguageProfile` protocol class
**When**: Checking its required methods
**Then**: It declares: `compile_condition()`, `compile_assertions()`, `discover_api_context()`, `build_system_prompt()`, `build_structural_patterns()`, `build_import_instructions()`, `verify_test_file()`, `extract_code_from_response()`, `test_file_name()`, `test_file_extension`, `fence_language_tag`

**Design note**: `LanguageProfile` implementations MUST be stateless. `get_profile()` creates
a new instance per call; caching or mutable state on profiles is prohibited.

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
from registry.lang import LanguageProfile, TargetLanguage
from registry.tla_compiler import CompiledAssertion
from pathlib import Path
import inspect


class TestLanguageProfile:
    def test_protocol_has_compile_condition(self):
        assert hasattr(LanguageProfile, "compile_condition")
        sig = inspect.signature(LanguageProfile.compile_condition)
        params = list(sig.parameters.keys())
        assert "tla_expr" in params

    def test_protocol_has_discover_api_context(self):
        assert hasattr(LanguageProfile, "discover_api_context")

    def test_protocol_has_build_system_prompt(self):
        assert hasattr(LanguageProfile, "build_system_prompt")

    def test_protocol_has_build_structural_patterns(self):
        assert hasattr(LanguageProfile, "build_structural_patterns")

    def test_protocol_has_build_import_instructions(self):
        assert hasattr(LanguageProfile, "build_import_instructions")

    def test_protocol_has_verify_test_file(self):
        assert hasattr(LanguageProfile, "verify_test_file")

    def test_protocol_has_extract_code(self):
        assert hasattr(LanguageProfile, "extract_code_from_response")

    def test_protocol_has_file_extension(self):
        assert hasattr(LanguageProfile, "test_file_extension")

    def test_protocol_has_fence_tag(self):
        assert hasattr(LanguageProfile, "fence_language_tag")

    def test_protocol_has_test_file_name(self):
        assert hasattr(LanguageProfile, "test_file_name")
        sig = inspect.signature(LanguageProfile.test_file_name)
        assert "gwt_id" in sig.parameters

    def test_protocol_has_compile_assertions(self):
        assert hasattr(LanguageProfile, "compile_assertions")
        sig = inspect.signature(LanguageProfile.compile_assertions)
        assert "verifiers" in sig.parameters
```

#### Green: Minimal Implementation
**File**: `python/registry/lang.py` (extend)
```python
from typing import Protocol, runtime_checkable
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CompiledExpression:
    """Language-agnostic compiled expression (renamed from CompiledAssertion)."""
    target_expr: str
    original_tla: str
    variables_used: list[str]
    helper_defs: str = ""  # Required preamble code (e.g., Go helper functions for quantifiers)


@dataclass
class VerifyResult:
    """Result of three-stage test file verification.

    Moved here from test_gen_loop.py to avoid circular imports when language
    backends need to return verification results.
    """
    passed: bool
    stage: str  # "compile", "collect", or "run"
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


@runtime_checkable
class LanguageProfile(Protocol):
    """Protocol for language-specific test generation backends.

    Implementations MUST be stateless — get_profile() creates a new instance
    per call. Do not cache or store mutable state on profile instances.
    """

    test_file_extension: str       # e.g., ".py", ".test.ts", "_test.go"
    fence_language_tag: str        # e.g., "python", "typescript", "go"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        """Compile a single TLA+ condition to a target-language assertion expression."""
        ...

    def compile_assertions(
        self, verifiers: dict, state_var: str = "state",
    ) -> dict[str, CompiledExpression]:
        """Compile all verifier conditions to target-language expressions.

        This replaces the old tla_compiler.compile_assertions() which was
        hardcoded to Python. build_compiler_hints() calls this method
        instead of the old function, ensuring compiler hints in LLM prompts
        match the target language (e.g., Rust gets `s.iter().all(|x| ...)`,
        not Python `all(x in S for x in ...)`).

        Default implementation loops over verifiers and calls compile_condition()
        per condition — language backends can override for batch optimizations.
        """
        ...

    def discover_api_context(self, source_dir: Path, module_name: str) -> str:
        """Scan source files for public API signatures."""
        ...

    def build_system_prompt(self) -> str:
        """Return the system prompt for the LLM test generation loop."""
        ...

    def build_structural_patterns(self) -> str:
        """Return code example patterns for the target language."""
        ...

    def build_import_instructions(self, module_name: str) -> str:
        """Return import/use/require instructions for the codegen prompt."""
        ...

    def verify_test_file(
        self, test_path: Path, source_dir: Path,
        collect_timeout: int = 30, run_timeout: int = 120,
    ) -> VerifyResult:
        """Three-stage verification: syntax → discovery → execution."""
        ...

    def extract_code_from_response(self, response: str) -> str:
        """Extract target-language code from LLM response.

        Default implementation: extract largest fenced code block matching
        self.fence_language_tag, or return unfenced code as-is. Language
        backends inherit this from _extract_code_by_fence_tag() — only
        override if the language needs custom extraction logic.
        """
        ...

    def test_file_name(self, gwt_id: str) -> str:
        """Return the output test file name for a given GWT ID."""
        ...
```

#### Refactor
1. **`CompiledAssertion` → `CompiledExpression` migration** (explicit, tested):
   - Delete `CompiledAssertion` from `tla_compiler.py`
   - Replace all 8 existing test assertions on `.python_expr` with `.target_expr`
   - Update `tla_compiler.compile_condition()` to return `CompiledExpression`
   - Migration test: `assert compile_condition("x \\in S").target_expr == old_result.python_expr`

2. **Move `VerifyResult` out of `test_gen_loop.py`** into `lang.py`:
   - Update all imports in `test_gen_loop.py` and tests
   - Prevents circular import risk when language backends import `VerifyResult`

3. **Shared `_extract_code_by_fence_tag()` helper**:
   ```python
   def _extract_code_by_fence_tag(response: str, fence_tag: str) -> str:
       """Shared extraction logic parameterized by language fence tag."""
       import re
       text = response.strip()
       fenced = re.findall(rf"```(?:{fence_tag})?\n(.*?)```", text, re.DOTALL)
       if fenced:
           return max(fenced, key=len).strip()
       lines = text.splitlines()
       if lines and lines[0].strip().startswith("```"):
           lines = lines[1:]
       if lines and lines[-1].strip() == "```":
           lines = lines[:-1]
       return "\n".join(lines)
   ```
   All 4 profiles delegate `extract_code_from_response()` to this, passing their
   `fence_language_tag`. Only override if language-specific extraction is needed.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py` — Red then Green
- [x] All existing tests still pass (including `.target_expr` migration)
- [x] `VerifyResult` importable from `registry.lang`

---

## Behavior 3: PythonProfile implements LanguageProfile using existing code

### Test Specification
**Given**: The existing Python-specific code in `tla_compiler.py` and `test_gen_loop.py`
**When**: Creating a `PythonProfile` instance
**Then**: It satisfies `isinstance(profile, LanguageProfile)` and produces identical
output to the current functions for every method

**Key constraint**: This is a strangler-fig refactor. Every PythonProfile method must
produce byte-identical output to the function it replaces, verified by test.

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
from registry.lang import PythonProfile, LanguageProfile


class TestPythonProfile:
    def setup_method(self):
        self.profile = PythonProfile()

    def test_satisfies_protocol(self):
        assert isinstance(self.profile, LanguageProfile)

    def test_file_extension(self):
        assert self.profile.test_file_extension == ".py"

    def test_fence_tag(self):
        assert self.profile.fence_language_tag == "python"

    # --- compile_condition parity ---

    def test_compile_basic_operators(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "in" in r.target_expr
        assert "and" in r.target_expr
        assert "==" in r.target_expr

    def test_compile_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert "all(" in r.target_expr

    def test_compile_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert 'state["count"]' in r.target_expr

    def test_compile_len_cardinality(self):
        r = self.profile.compile_condition("Len(seq) > 0 /\\ Cardinality(S) = 3")
        assert "len(seq)" in r.target_expr
        assert "len(S)" in r.target_expr

    # --- discover_api_context parity ---

    def test_discover_api_context_finds_python_files(self, tmp_path):
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "dag.py").write_text("class RegistryDag:\n    def query(self): pass\n")
        (registry_dir / "types.py").write_text("class Node:\n    pass\n")

        result = self.profile.discover_api_context(tmp_path, "RegistryDag")
        assert "class RegistryDag" in result
        assert "class Node" in result

    # --- system prompt ---

    def test_system_prompt_mentions_python(self):
        prompt = self.profile.build_system_prompt()
        assert "Python" in prompt or "python" in prompt
        assert "pytest" in prompt

    # --- structural patterns ---

    def test_structural_patterns_has_python_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "import pytest" in patterns or "def test_" in patterns
        assert "RegistryDag" in patterns

    # --- import instructions ---

    def test_import_instructions_has_registry_imports(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "from registry" in instructions

    # --- extract_code_from_response ---

    def test_extract_strips_python_fences(self):
        response = '```python\ndef test_foo():\n    assert True\n```'
        code = self.profile.extract_code_from_response(response)
        assert code.startswith("def test_foo")
        assert "```" not in code

    def test_extract_bare_code(self):
        response = "def test_foo():\n    assert True"
        code = self.profile.extract_code_from_response(response)
        assert "def test_foo" in code

    # --- compile_assertions (batch) ---

    def test_compile_assertions_routes_through_profile(self):
        """Ensures build_compiler_hints() will use target-language expressions."""
        verifiers = {
            "inv_membership": {"condition": "x \\in S", "type": "invariant"},
            "inv_count": {"condition": "Len(seq) > 0", "type": "invariant"},
        }
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert "inv_count" in results
        assert "in" in results["inv_membership"].target_expr  # Python: x in S
        assert "len(seq)" in results["inv_count"].target_expr

    # --- test_file_name ---

    def test_file_name_python(self):
        assert self.profile.test_file_name("gwt-0024") == "test_gwt_0024.py"

    # --- CompiledAssertion → CompiledExpression migration parity ---

    def test_compiled_expression_matches_old_compiled_assertion(self):
        """Verify target_expr produces identical output to old python_expr."""
        from registry.tla_compiler import compile_condition as old_compile
        expr = "x \\in S /\\ y = 3"
        old_result = old_compile(expr)
        new_result = self.profile.compile_condition(expr)
        assert new_result.target_expr == old_result.target_expr  # was .python_expr

    # --- verify_test_file ---

    def test_verify_catches_syntax_error(self, tmp_path):
        test_file = tmp_path / "test_bad.py"
        test_file.write_text("def test_bad(\n")
        result = self.profile.verify_test_file(test_file, tmp_path)
        assert not result.passed
        assert result.stage == "compile"

    def test_verify_passes_valid_test(self, tmp_path):
        test_file = tmp_path / "test_ok.py"
        test_file.write_text("def test_ok():\n    assert True\n")
        result = self.profile.verify_test_file(test_file, tmp_path)
        assert result.passed
```

#### Green: Minimal Implementation
**File**: `python/registry/lang.py` (extend with PythonProfile class)

`PythonProfile` wraps the existing functions from `tla_compiler.py` and
`test_gen_loop.py`, delegating to them. Each method is a thin wrapper:

```python
class PythonProfile:
    test_file_extension: str = ".py"
    fence_language_tag: str = "python"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        from registry.tla_compiler import compile_condition as _compile
        result = _compile(tla_expr, state_var)
        return CompiledExpression(
            target_expr=result.target_expr,  # was .python_expr before migration
            original_tla=result.original_tla,
            variables_used=result.variables_used,
        )

    def compile_assertions(
        self, verifiers: dict, state_var: str = "state",
    ) -> dict[str, CompiledExpression]:
        """Batch-compile all verifier conditions to Python expressions.

        Replaces the old tla_compiler.compile_assertions() call in
        build_compiler_hints(). This ensures --lang flag is respected
        for compiler hints in LLM prompts.
        """
        results = {}
        for name, verifier in verifiers.items():
            condition = verifier.get("condition", "")
            if condition:
                results[name] = self.compile_condition(condition, state_var)
        return results

    def discover_api_context(self, source_dir: Path, module_name: str) -> str:
        from registry.test_gen_loop import discover_api_context as _discover
        return _discover(source_dir, module_name)

    def build_system_prompt(self) -> str:
        return (
            "You are a Python test generation expert. You generate complete, runnable "
            "pytest test files from formal specifications and API documentation. "
            "You use ONLY the real API imports provided — never create mock classes "
            "or re-implement the API. Output ONLY Python code, no markdown fencing "
            "or explanation."
        )

    def build_structural_patterns(self) -> str:
        # Extract from test_gen_loop.py lines 176-196
        return (
            "```python\n"
            "# Pattern: fixture construction from trace Init state\n"
            "def _make_dag(nodes, edges, artifacts):\n"
            "    dag = RegistryDag()\n"
            "    for nid in nodes:\n"
            "        dag.add_node(Node.behavior(nid, nid, 'g', 'w', 't'))\n"
            "    for src, dst in edges:\n"
            "        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))\n"
            "    dag.test_artifacts = artifacts\n"
            "    return dag\n\n"
            "# Pattern: invariant verification\n"
            "def test_invariant(dag):\n"
            "    result = dag.some_query('node_id')\n"
            "    assert property_of(result)\n\n"
            "# Pattern: error case\n"
            "def test_invalid_input(dag):\n"
            "    with pytest.raises(NodeNotFoundError):\n"
            "        dag.some_query('nonexistent')\n"
            "```\n"
        )

    def build_import_instructions(self, module_name: str) -> str:
        return (
            f"- CRITICAL: Use EXACT import paths from the API Context section above.\n"
            f"  Use `from registry.dag import RegistryDag` NOT `from {module_name}.dag`\n"
            f"  Use `from registry.types import Node, Edge, EdgeType` for type imports\n"
            f"- Use `import pytest` and relevant imports from the API context\n"
        )

    def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
        from registry.test_gen_loop import verify_test_file as _verify
        return _verify(test_path, source_dir, collect_timeout, run_timeout)

    def extract_code_from_response(self, response: str) -> str:
        return _extract_code_by_fence_tag(response, self.fence_language_tag)

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"test_{safe_id}.py"
```

#### Refactor
- Move prompt text constants OUT of `test_gen_loop.py` into `PythonProfile`
- Make `test_gen_loop.py` import from `PythonProfile` (inversion)
- Delete duplicated code from `test_gen_loop.py`
- Refactor `build_compiler_hints()` to accept `lang_profile` parameter:
  ```python
  def build_compiler_hints(verifiers: dict, lang_profile: LanguageProfile) -> dict[str, CompiledExpression]:
      """Build compiler hints using the target language profile.

      Previously called tla_compiler.compile_assertions() directly (Python-only).
      Now delegates to lang_profile.compile_assertions() so that --lang rust
      produces Rust expressions in the prompt hints, not Python.
      """
      return lang_profile.compile_assertions(verifiers)
  ```
- Update `_extract_code_from_response()` calls → `profile.extract_code_from_response()`
  (delegates to shared `_extract_code_by_fence_tag()`)

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestPythonProfile` — Red then Green
- [x] `pytest tests/test_tla_compiler.py` — still passes (parity)
- [x] `pytest tests/test_cli.py::TestGenTestsCommand` — still passes
- [x] Full suite: `pytest`

---

## Behavior 4: TestGenContext uses LanguageProfile instead of hardcoded Python

### Test Specification
**Given**: A `TestGenContext` with a `lang_profile` field
**When**: Building prompts via `build_test_plan_prompt()`, `build_codegen_prompt()`, etc.
**Then**: Prompts use the profile's methods instead of hardcoded Python strings
**And**: `python_dir` field is renamed to `source_dir` (M6)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
class TestGenContextIntegration:
    def test_context_has_lang_profile(self):
        from registry.test_gen_loop import TestGenContext
        from registry.lang import PythonProfile
        ctx = TestGenContext(
            gwt_id="gwt-0001",
            gwt_text={"given": "g", "when": "w", "then": "t"},
            module_name="test",
            bridge_artifacts={},
            compiler_hints={},
            api_context="",
            test_scenarios=[],
            simulation_traces=[],
            output_dir=Path("."),
            source_dir=Path("."),
            lang_profile=PythonProfile(),
        )
        assert isinstance(ctx.lang_profile, LanguageProfile)

    def test_context_source_dir_replaces_python_dir(self):
        from registry.test_gen_loop import TestGenContext
        assert hasattr(TestGenContext, "__dataclass_fields__")
        fields = TestGenContext.__dataclass_fields__
        assert "source_dir" in fields
        assert "python_dir" not in fields

    def test_lang_profile_default_is_python(self):
        """Default factory ensures backwards compat when lang_profile not passed."""
        from registry.test_gen_loop import TestGenContext
        ctx = TestGenContext(
            gwt_id="gwt-0001",
            gwt_text={"given": "g", "when": "w", "then": "t"},
            module_name="test",
            bridge_artifacts={},
            compiler_hints={},
            api_context="",
            test_scenarios=[],
            simulation_traces=[],
            output_dir=Path("."),
            source_dir=Path("."),
        )
        assert isinstance(ctx.lang_profile, PythonProfile)

    def test_cmd_gen_tests_passes_correct_profile_for_lang_flag(self):
        """CRITICAL: --lang rust must pass RustProfile, NOT default PythonProfile.

        Without this test, the impl LLM might forget to wire get_profile()
        in cmd_gen_tests(), causing everything to silently use Python.
        """
        from registry.lang import get_profile, TargetLanguage
        # Simulate what cmd_gen_tests() must do:
        profile = get_profile(TargetLanguage("rust"))
        assert type(profile).__name__ == "RustProfile"
        # Verify it's NOT PythonProfile
        assert not isinstance(profile, PythonProfile)
```

#### Green
- Rename `TestGenContext.python_dir` → `source_dir`
- Add `lang_profile: LanguageProfile` field with `default_factory=PythonProfile`
- Update all callers (`cli.py`, `test_gen_loop.py`)

#### Refactor
Refactored prompt builders — explicit signatures showing WHERE profile methods are called:

```python
def build_test_plan_prompt(ctx: TestGenContext) -> str:
    """Assemble the test plan prompt. Profile provides structural patterns."""
    # ... bridge artifacts, verifiers, traces (unchanged) ...
    patterns = ctx.lang_profile.build_structural_patterns()  # was: inline Python code
    # ... return assembled prompt ...

def build_codegen_prompt(ctx: TestGenContext, test_plan: str, attempt: int) -> str:
    """Assemble the codegen prompt. Profile provides import instructions."""
    imports = ctx.lang_profile.build_import_instructions(ctx.module_name)  # was: hardcoded Python
    # ... return assembled prompt ...

def build_retry_prompt(ctx: TestGenContext, error_output: str) -> str:
    """Assemble the retry prompt. Same import instructions from profile."""
    imports = ctx.lang_profile.build_import_instructions(ctx.module_name)
    # ... return assembled prompt ...

def build_compiler_hints(ctx: TestGenContext) -> dict[str, CompiledExpression]:
    """Build compiler hints via profile (was: tla_compiler.compile_assertions())."""
    return ctx.lang_profile.compile_assertions(ctx.bridge_artifacts.get("verifiers", {}))

async def run_test_gen_loop(ctx: TestGenContext) -> ...:
    """Main loop — uses profile throughout. No signature change."""
    system_prompt = ctx.lang_profile.build_system_prompt()         # was: _TEST_GEN_SYSTEM_PROMPT
    # ... in response handling:
    code = ctx.lang_profile.extract_code_from_response(response)   # was: _extract_code_from_response()
    result = ctx.lang_profile.verify_test_file(test_path, ctx.source_dir)  # was: verify_test_file()
    output_name = ctx.lang_profile.test_file_name(ctx.gwt_id)     # was: f"test_{gwt_id}.py"
```

**Key**: `run_test_gen_loop()` signature does NOT change — the profile is accessed
via `ctx.lang_profile`. All delegation happens inside the existing functions.

### Success Criteria
**Automated:**
- [x] `pytest tests/test_lang.py::TestGenContextIntegration` passes
- [x] `pytest tests/test_cli.py` — all existing CLI tests still pass
- [x] Full suite: `pytest`

---

## Behavior 5: CLI accepts --lang flag (defaults to python)

### Test Specification
**Given**: `cw9 gen-tests gwt-0024 --lang python`
**When**: Parsing CLI args
**Then**: `args.lang` == `"python"` and pipeline uses `PythonProfile`

**Given**: `cw9 gen-tests gwt-0024` (no flag)
**When**: Parsing CLI args
**Then**: `args.lang` defaults to `"python"`

**Given**: `cw9 gen-tests gwt-0024 --lang cobol`
**When**: Parsing CLI args
**Then**: Error message listing valid languages

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_cli.py` (extend existing TestGenTestsCommand)
```python
def test_gen_tests_default_lang_is_python(self):
    """--lang defaults to python when omitted."""
    # Parse args without --lang
    args = parse_args(["gen-tests", "gwt-0001", str(self.target)])
    assert args.lang == "python"

def test_gen_tests_accepts_typescript(self):
    args = parse_args(["gen-tests", "gwt-0001", "--lang", "typescript", str(self.target)])
    assert args.lang == "typescript"

def test_gen_tests_rejects_unknown_lang(self):
    with pytest.raises(SystemExit):
        parse_args(["gen-tests", "gwt-0001", "--lang", "cobol", str(self.target)])
```

#### Green
**File**: `python/registry/cli.py` (extend gen-tests parser)
```python
p_gen.add_argument(
    "--lang", default="python",
    choices=["python", "typescript", "rust", "go"],
    help="Target language for test generation (default: python)",
)
```

**File**: `python/registry/cli.py:cmd_gen_tests()` (wire profile)
```python
from registry.lang import TargetLanguage, get_profile

lang_profile = get_profile(TargetLanguage(args.lang))
# Pass to TestGenContext
```

#### Refactor
Add `get_profile()` factory in `lang.py`:
```python
def get_profile(lang: TargetLanguage) -> LanguageProfile:
    if lang == TargetLanguage.PYTHON:
        return PythonProfile()
    raise NotImplementedError(f"Language profile not yet implemented: {lang}")
```

### Success Criteria
**Automated:**
- [x] `pytest tests/test_cli.py` — all pass including new tests
- [x] `cw9 gen-tests gwt-0024 --lang python` works identically to `cw9 gen-tests gwt-0024`
- [x] Full suite: `pytest`

---

## Behavior 5b: Integration test markers and tool-availability skips

### Test Specification
**Given**: pytest configuration
**When**: Running tests with `@pytest.mark.integration`
**Then**: No `PytestUnknownMarkWarning` is raised, and tests skip gracefully
when required tools (`npx`, `cargo`, `go`) are not installed.

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_lang.py` (append)
```python
class TestIntegrationMarkers:
    def test_integration_mark_registered(self):
        """Verify the 'integration' mark doesn't trigger warnings."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--markers"],
            capture_output=True, text=True,
        )
        assert "integration" in result.stdout
```

#### Green
**File**: `pyproject.toml` (or `pytest.ini`)
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests requiring external tools (tsc, cargo, go)",
]
```

**File**: `python/tests/conftest.py` (or `python/conftest.py`)
```python
import shutil
import pytest

def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when required tools aren't installed."""
    tool_checks = {
        "typescript": "npx",
        "rust": "cargo",
        "go": "go",
    }
    for item in items:
        if "integration" not in item.keywords:
            continue
        # Infer required tool from test path or marker args
        for lang, tool in tool_checks.items():
            if lang in str(item.fspath) and shutil.which(tool) is None:
                item.add_marker(pytest.mark.skip(
                    reason=f"{tool} not found — install to run {lang} integration tests"
                ))
```

#### Refactor
None needed.

### Success Criteria
**Automated:**
- [x] `pytest --markers` shows "integration"
- [x] Integration tests skip cleanly when tools aren't installed (no errors, just skips)

---

## Behavior 6: Output file uses language-appropriate extension and path

### Test Specification
**Given**: `lang_profile.test_file_extension == ".py"`
**When**: `run_test_gen_loop()` determines output path
**Then**: Output is `test_{gwt_id}.py`

**Given**: `lang_profile.test_file_extension == ".test.ts"`
**When**: `run_test_gen_loop()` determines output path
**Then**: Output is `{gwt_id}.test.ts`

### TDD Cycle

#### Red: Write Failing Test
```python
class TestOutputPath:
    def test_python_output_path(self):
        from registry.lang import PythonProfile
        profile = PythonProfile()
        gwt_id = "gwt-0024"
        expected = f"test_{gwt_id.replace('-', '_')}.py"
        assert profile.test_file_name(gwt_id) == expected

    def test_typescript_output_path(self):
        from registry.lang import TypeScriptProfile
        profile = TypeScriptProfile()
        gwt_id = "gwt-0024"
        expected = f"gwt_0024.test.ts"
        assert profile.test_file_name(gwt_id) == expected
```

#### Green
Add `test_file_name(gwt_id: str) -> str` to `LanguageProfile` protocol and implement.

### Success Criteria
**Automated:**
- [x] Path tests pass
- [x] `run_test_gen_loop()` uses `ctx.lang_profile.test_file_name()` instead of hardcoded f-string

---

## Phase 1 Checkpoint

At this point:
- All Python behavior is unchanged (strangler fig complete)
- `LanguageProfile` protocol is validated by `PythonProfile`
- CLI has `--lang` flag
- All existing tests pass
- No new language is implemented yet

**Gate**: Full test suite passes. Manual smoke test: `cw9 gen-tests gwt-0024` produces
identical output to before the refactor.
