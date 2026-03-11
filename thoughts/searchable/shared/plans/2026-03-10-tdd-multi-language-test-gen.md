---
date: 2026-03-10
researcher: claude-opus
branch: master
repository: CodeWriter9.0
topic: "TDD Plan: Multi-Language Test Generation (Strangler Fig)"
tags: [tdd, plan, multi-language, typescript, rust, go, bridge, test-gen]
status: draft
type: tdd-plan
---

# Multi-Language Test Generation — TDD Implementation Plan

## Overview

Extend the CW9 test generation pipeline to emit tests in TypeScript, Rust, and Go
in addition to Python. The bridge artifacts are already language-neutral JSON; all
Python coupling lives downstream in 4 files. We use a strangler-fig approach:
refactor Python to use the new abstraction first, then add TypeScript, Rust, and
Go as successive implementations — TypeScript validates the abstraction, Rust and
Go prove it generalizes.

## Current State Analysis

### Python Coupling Points (6 total, 4 files)

| # | Location | What's coupled | Line(s) |
|---|----------|----------------|---------|
| C1 | `tla_compiler.py` | Compiles TLA+ → **Python** expressions (`all()`, `len()`, `==`) | 29-108 |
| C2 | `test_gen_loop.py:discover_api_context()` | Globs `*.py`, reads `import/class/def` lines | 74-111 |
| C3 | `test_gen_loop.py:build_test_plan_prompt()` | Hardcoded Python code examples (RegistryDag, pytest.raises) | 176-196 |
| C3b | `test_gen_loop.py:build_codegen_prompt()` | `from registry.dag import`, `pass compile()` | 260-277 |
| C3c | `test_gen_loop.py:build_retry_prompt()` | Same Python import instructions | 280-298 |
| C4 | `test_gen_loop.py:verify_test_file()` | `compile()` → `pytest --collect-only` → `pytest -x` | 301-346 |
| C5 | `test_gen_loop.py:_extract_code_from_response()` | ````python` fence pattern | 349-380 |
| C6 | `test_gen_loop.py:_TEST_GEN_SYSTEM_PROMPT` | "Python test generation expert" | 383-389 |
| C7 | `test_gen_loop.py:TestGenContext.python_dir` | Field name leaks Python | 46 |
| C8 | `cli.py:cmd_gen_tests()` | No `--lang` flag, hardcodes pytest path | 296-375, 471-474 |
| C9 | `context.py:ProjectContext.python_dir` | Field semantically means "source dir" | 30 |

### What's Already Language-Neutral

- `bridge.py` — all 4 translators produce abstract schema paths (`shared/data_types/String`)
- `traces.py` — simulation trace loading/formatting
- `one_shot_loop.py` — GWT → PlusCal → TLC loop
- `dag.py`, `types.py`, `extractor.py` — core DAG infrastructure
- Bridge artifact JSON format — `data_structures`, `operations`, `verifiers`, `assertions`

### Key Discoveries

- `_tla_type_to_schema_type()` in `bridge.py:331` maps to abstract types, not Python types
- `CompiledAssertion` dataclass has `python_expr` field — needs renaming to `target_expr`
- `verify_test_file()` has a clean 3-stage pattern (syntax → collect → run) that maps
  well to other languages: `cargo check`/`tsc --noEmit` → `cargo test --no-run`/`jest --listTests` → `cargo test`/`jest`
- `ProjectContext.python_dir` is used by both `discover_api_context()` and `verify_test_file()` — semantically "source root"

## Desired End State

A `TargetLanguage` protocol/enum that selects:
- Assertion compiler (TLA+ → target language expressions)
- API context discovery (scan source files for public signatures)
- Prompt builders (system prompt + structural patterns + code examples)
- Test file verification (syntax check → test discovery → test execution)
- Code extraction from LLM response (language-specific fence patterns)
- Output file extension and path

Python remains the default. TypeScript validates the abstraction. Rust and Go
are implemented using the same interface, proving the protocol generalizes
across compiled, systems, and GC'd languages.

### Observable Behaviors

1. `cw9 gen-tests gwt-0024 --lang python` produces identical output to today
2. `cw9 gen-tests gwt-0024 --lang typescript` produces a `.test.ts` file
3. `cw9 gen-tests gwt-0024 --lang rust` produces a `.rs` test file
4. `cw9 gen-tests gwt-0024 --lang go` produces a `_test.go` file
5. `cw9 gen-tests gwt-0024` (no flag) defaults to `python` (backwards compatible)
6. Each language's compiler transforms TLA+ conditions into idiomatic expressions
7. Each language's verifier uses the correct toolchain (`pytest`/`jest`/`cargo test`/`go test`)

## What We're NOT Doing

- Changing the bridge — it's already language-neutral
- Changing the TLA+/PlusCal loop — language-independent
- Changing the DAG, extractor, or schema format
- Multi-language in a single project (one `--lang` per `gen-tests` invocation)

## Testing Strategy

- **Framework**: pytest (our test harness is Python regardless of target language)
- **Unit tests**: Each behavior gets its own test class mirroring existing patterns
- **Integration**: CLI flag wiring, end-to-end prompt assembly
- **No mocks for core types**: Use real `ParsedSpec`, `BridgeResult`, etc.

---

## Phase 1: Extract the Abstraction (Strangler Fig on Python)

### Behavior 1: TargetLanguage enum exists with known values

#### Test Specification
**Given**: The `registry.lang` module exists
**When**: Importing `TargetLanguage`
**Then**: `TargetLanguage.PYTHON`, `.TYPESCRIPT`, `.RUST`, `.GO` are valid enum values
**Edge Cases**: String round-trip (`TargetLanguage("python")` works), unknown value raises

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green: Minimal Implementation
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

##### Refactor
None needed — enum is minimal.

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py` — Red then Green
- [ ] All existing tests still pass: `pytest`

---

### Behavior 2: LanguageProfile protocol defines the abstraction surface

#### Test Specification
**Given**: A `LanguageProfile` protocol class
**When**: Checking its required methods
**Then**: It declares: `compile_condition()`, `discover_api_context()`, `build_system_prompt()`, `build_structural_patterns()`, `build_import_instructions()`, `verify_test_file()`, `extract_code_from_response()`, `test_file_extension`, `fence_language_tag`

#### TDD Cycle

##### Red: Write Failing Test
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
```

##### Green: Minimal Implementation
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


@runtime_checkable
class LanguageProfile(Protocol):
    """Protocol for language-specific test generation backends."""

    test_file_extension: str       # e.g., ".py", ".test.ts", "_test.go"
    fence_language_tag: str        # e.g., "python", "typescript", "go"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        """Compile a TLA+ condition to a target-language assertion expression."""
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
    ) -> "VerifyResult":
        """Three-stage verification: syntax → discovery → execution."""
        ...

    def extract_code_from_response(self, response: str) -> str:
        """Extract target-language code from LLM response."""
        ...
```

##### Refactor
Rename `CompiledAssertion.python_expr` → `CompiledExpression.target_expr` across codebase
(backwards-compat alias in `tla_compiler.py` during transition).

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py` — Red then Green
- [ ] All existing tests still pass

---

### Behavior 3: PythonProfile implements LanguageProfile using existing code

#### Test Specification
**Given**: The existing Python-specific code in `tla_compiler.py` and `test_gen_loop.py`
**When**: Creating a `PythonProfile` instance
**Then**: It satisfies `isinstance(profile, LanguageProfile)` and produces identical
output to the current functions for every method

**Key constraint**: This is a strangler-fig refactor. Every PythonProfile method must
produce byte-identical output to the function it replaces, verified by test.

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green: Minimal Implementation
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
            target_expr=result.python_expr,
            original_tla=result.original_tla,
            variables_used=result.variables_used,
        )

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
        from registry.test_gen_loop import _extract_code_from_response as _extract
        return _extract(response)
```

##### Refactor
- Move prompt text constants OUT of `test_gen_loop.py` into `PythonProfile`
- Make `test_gen_loop.py` import from `PythonProfile` (inversion)
- Delete duplicated code from `test_gen_loop.py`

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestPythonProfile` — Red then Green
- [ ] `pytest tests/test_tla_compiler.py` — still passes (parity)
- [ ] `pytest tests/test_cli.py::TestGenTestsCommand` — still passes
- [ ] Full suite: `pytest`

---

### Behavior 4: TestGenContext uses LanguageProfile instead of hardcoded Python

#### Test Specification
**Given**: A `TestGenContext` with a `lang_profile` field
**When**: Building prompts via `build_test_plan_prompt()`, `build_codegen_prompt()`, etc.
**Then**: Prompts use the profile's methods instead of hardcoded Python strings
**And**: `python_dir` field is renamed to `source_dir` (M6)

#### TDD Cycle

##### Red: Write Failing Test
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
```

##### Green
- Rename `TestGenContext.python_dir` → `source_dir`
- Add `lang_profile: LanguageProfile` field with `default_factory=PythonProfile`
- Update all callers (`cli.py`, `test_gen_loop.py`)

##### Refactor
- Update `build_test_plan_prompt()` to call `ctx.lang_profile.build_structural_patterns()`
  instead of inline Python code
- Update `build_codegen_prompt()` to call `ctx.lang_profile.build_import_instructions()`
- Update `_TEST_GEN_SYSTEM_PROMPT` usage to call `ctx.lang_profile.build_system_prompt()`
- Update `verify_test_file()` calls to use `ctx.lang_profile.verify_test_file()`
- Update `_extract_code_from_response()` calls to use `ctx.lang_profile.extract_code_from_response()`

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestGenContextIntegration` passes
- [ ] `pytest tests/test_cli.py` — all existing CLI tests still pass
- [ ] Full suite: `pytest`

---

### Behavior 5: CLI accepts --lang flag (defaults to python)

#### Test Specification
**Given**: `cw9 gen-tests gwt-0024 --lang python`
**When**: Parsing CLI args
**Then**: `args.lang` == `"python"` and pipeline uses `PythonProfile`

**Given**: `cw9 gen-tests gwt-0024` (no flag)
**When**: Parsing CLI args
**Then**: `args.lang` defaults to `"python"`

**Given**: `cw9 gen-tests gwt-0024 --lang cobol`
**When**: Parsing CLI args
**Then**: Error message listing valid languages

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
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

##### Refactor
Add `get_profile()` factory in `lang.py`:
```python
def get_profile(lang: TargetLanguage) -> LanguageProfile:
    if lang == TargetLanguage.PYTHON:
        return PythonProfile()
    raise NotImplementedError(f"Language profile not yet implemented: {lang}")
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_cli.py` — all pass including new tests
- [ ] `cw9 gen-tests gwt-0024 --lang python` works identically to `cw9 gen-tests gwt-0024`
- [ ] Full suite: `pytest`

---

### Behavior 6: Output file uses language-appropriate extension and path

#### Test Specification
**Given**: `lang_profile.test_file_extension == ".py"`
**When**: `run_test_gen_loop()` determines output path
**Then**: Output is `test_{gwt_id}.py`

**Given**: `lang_profile.test_file_extension == ".test.ts"`
**When**: `run_test_gen_loop()` determines output path
**Then**: Output is `{gwt_id}.test.ts`

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
Add `test_file_name(gwt_id: str) -> str` to `LanguageProfile` protocol and implement.

#### Success Criteria
**Automated:**
- [ ] Path tests pass
- [ ] `run_test_gen_loop()` uses `ctx.lang_profile.test_file_name()` instead of hardcoded f-string

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

---

## Phase 2: TypeScript Implementation

### Behavior 7: TypeScript assertion compiler

#### Test Specification
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

#### TDD Cycle

##### Red: Write Failing Test
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
```

##### Green
**File**: `python/registry/lang_typescript.py`
```python
class TypeScriptProfile:
    test_file_extension = ".test.ts"
    fence_language_tag = "typescript"

    def compile_condition(self, tla_expr, state_var="state"):
        # TypeScript-specific TLA+ → JS/TS expression compilation
        ...
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

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestTypeScriptCompiler` passes
- [ ] Full suite still passes

---

### Behavior 8: TypeScript API context discovery

#### Test Specification
**Given**: A directory with `.ts` files containing `export function`, `export class`, `export interface`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the exported signatures

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
Implement `TypeScriptProfile.discover_api_context()`:
- Glob for `*.ts` files matching module name (camelCase and kebab-case)
- Extract lines starting with `export function`, `export class`, `export interface`, `export type`, `import`

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestTypeScriptApiDiscovery` passes

---

### Behavior 9: TypeScript prompts and structural patterns

#### Test Specification
**Given**: `TypeScriptProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions TypeScript, Jest/Vitest, not Python/pytest

**When**: Calling `build_structural_patterns()`
**Then**: Contains `describe(`, `it(`, `expect(`, TypeScript import syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains `import { ... } from` syntax

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
Implement the three prompt methods with TypeScript-idiomatic code examples.

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestTypeScriptPrompts` passes

---

### Behavior 10: TypeScript test file verification

#### Test Specification
**Given**: A valid `.test.ts` file
**When**: Calling `verify_test_file()`
**Then**: Runs `tsc --noEmit` → `npx jest --listTests` → `npx jest`

**Given**: A `.test.ts` file with a type error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

#### TDD Cycle

##### Red: Write Failing Test
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

Note: TypeScript verification tests that invoke `tsc`/`jest` should be marked
`@pytest.mark.integration` and skipped if tools aren't installed.

##### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess, sys
    from registry.test_gen_loop import VerifyResult

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

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestTypeScriptVerification` passes (with mocked subprocess or integration mark)

---

### Behavior 11: TypeScript code extraction from LLM response

#### Test Specification
**Given**: LLM response with ` ```typescript\n...code...\n``` `
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the TypeScript code without fences

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
```python
def extract_code_from_response(self, response: str) -> str:
    import re
    text = response.strip()
    fenced = re.findall(r"```(?:typescript|ts)?\n(.*?)```", text, re.DOTALL)
    if fenced:
        return max(fenced, key=len).strip()
    # Strip bare fences
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestTypeScriptExtraction` passes

---

## Phase 2 Checkpoint

At this point:
- `TypeScriptProfile` fully implements `LanguageProfile`
- `cw9 gen-tests gwt-0024 --lang typescript` produces `.test.ts` files
- Python path is unchanged
- Abstraction is validated by two implementations

**Gate**: `pytest` full suite passes. Manual: `cw9 gen-tests gwt-0024 --lang typescript`
on a project with `.ts` source files.

---

## Phase 3: Rust Implementation

### Behavior 12: Rust assertion compiler

#### Test Specification
**Given**: TLA+ condition `x \in S /\ y = 3`
**When**: Compiling for Rust
**Then**: Produces `s.contains(&x) && y == 3`

**Given**: `\A x \in S : x > 0`
**When**: Compiling for Rust
**Then**: Produces `s.iter().all(|x| x > 0)`

**Given**: `Len(seq) > 0`
**When**: Compiling for Rust
**Then**: Produces `seq.len() > 0`

#### TDD Cycle

##### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py`
```python
import pytest
from registry.lang import RustProfile, CompileError


class TestRustCompiler:
    def setup_method(self):
        self.profile = RustProfile()

    def test_membership(self):
        r = self.profile.compile_condition("x \\in S")
        assert ".contains(&x)" in r.target_expr or ".contains(x)" in r.target_expr

    def test_conjunction(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "&&" in r.target_expr

    def test_equality(self):
        r = self.profile.compile_condition("y = 3")
        assert "==" in r.target_expr
        assert "===" not in r.target_expr  # not JS triple-equals

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!=" in r.target_expr

    def test_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert ".iter().all(|x|" in r.target_expr or ".iter().all(|x| x > 0)" in r.target_expr

    def test_existential_quantifier(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert ".iter().any(|x|" in r.target_expr

    def test_len(self):
        r = self.profile.compile_condition("Len(seq) > 0")
        assert ".len()" in r.target_expr

    def test_cardinality(self):
        r = self.profile.compile_condition("Cardinality(S) = 3")
        assert ".len()" in r.target_expr  # Rust uses .len() for all collections

    def test_boolean_literals(self):
        r = self.profile.compile_condition("x = TRUE")
        assert "true" in r.target_expr

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.count" in r.target_expr  # Rust uses dot access for struct fields

    def test_disjunction(self):
        r = self.profile.compile_condition("x = 1 \\/ y = 2")
        assert "||" in r.target_expr

    def test_unsupported_raises(self):
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")
```

##### Green
**File**: `python/registry/lang_rust.py`

Implements the mapping:
| TLA+ | Rust |
|------|------|
| `\in` | `.contains(&x)` |
| `/\` | `&&` |
| `\/` | `\|\|` |
| `=` | `==` |
| `#` | `!=` |
| `\A x \in S : P` | `s.iter().all(\|x\| P)` |
| `\E x \in S : P` | `s.iter().any(\|x\| P)` |
| `Len(x)` | `x.len()` |
| `Cardinality(S)` | `s.len()` |
| `TRUE/FALSE` | `true/false` |
| `state.field` | `state.field` |

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustCompiler` passes
- [ ] Full suite still passes

---

### Behavior 13: Rust API context discovery

#### Test Specification
**Given**: A directory with `.rs` files containing `pub fn`, `pub struct`, `pub trait`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the public signatures

#### TDD Cycle

##### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustApiDiscovery:
    def test_finds_pub_functions(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "dag.rs").write_text(
            "pub struct RegistryDag {\n"
            "    nodes: Vec<Node>,\n"
            "}\n\n"
            "impl RegistryDag {\n"
            "    pub fn query_impact(&self, node_id: &str) -> ImpactResult {\n"
            "        todo!()\n"
            "    }\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "RegistryDag")
        assert "pub struct RegistryDag" in result
        assert "pub fn query_impact" in result

    def test_finds_traits(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "types.rs").write_text(
            "pub trait Queryable {\n"
            "    fn query(&self, id: &str) -> Option<Node>;\n"
            "}\n\n"
            "pub enum EdgeType {\n"
            "    Imports,\n"
            "    Exports,\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "Queryable")
        assert "pub trait Queryable" in result
        assert "pub enum EdgeType" in result

    def test_finds_impl_blocks(self, tmp_path):
        profile = RustProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "lib.rs").write_text(
            "impl Dag {\n"
            "    pub fn new() -> Self { todo!() }\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "Dag")
        assert "pub fn new" in result

    def test_no_source_returns_comment(self, tmp_path):
        profile = RustProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result
```

##### Green
Implement `RustProfile.discover_api_context()`:
- Glob for `*.rs` files
- Extract lines starting with `pub fn`, `pub struct`, `pub trait`, `pub enum`, `pub type`, `impl`, `use`
- Include doc comments (`///`) preceding public items

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustApiDiscovery` passes

---

### Behavior 14: Rust prompts and structural patterns

#### Test Specification
**Given**: `RustProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions Rust, `#[test]`, not Python/pytest

**When**: Calling `build_structural_patterns()`
**Then**: Contains `#[test]`, `assert!`, `assert_eq!`, Rust `use` syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains `use` statements

#### TDD Cycle

##### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustPrompts:
    def setup_method(self):
        self.profile = RustProfile()

    def test_system_prompt_mentions_rust(self):
        prompt = self.profile.build_system_prompt()
        assert "Rust" in prompt
        assert "Python" not in prompt
        assert "TypeScript" not in prompt

    def test_system_prompt_mentions_test_attr(self):
        prompt = self.profile.build_system_prompt()
        assert "#[test]" in prompt or "#[cfg(test)]" in prompt

    def test_structural_patterns_has_rust_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "#[test]" in patterns
        assert "assert" in patterns  # assert!, assert_eq!
        assert "fn test_" in patterns

    def test_structural_patterns_has_use_statements(self):
        patterns = self.profile.build_structural_patterns()
        assert "use " in patterns

    def test_import_instructions_has_rust_syntax(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "use " in instructions
```

##### Green
Implement the three prompt methods with Rust-idiomatic code examples:
```python
class RustProfile:
    def build_system_prompt(self) -> str:
        return (
            "You are a Rust test generation expert. You generate complete, runnable "
            "Rust test modules from formal specifications and API documentation. "
            "You use ONLY the real crate imports provided — never create mock structs "
            "or re-implement the API. Use #[cfg(test)] modules with #[test] functions. "
            "Output ONLY Rust code, no markdown fencing or explanation."
        )

    def build_structural_patterns(self) -> str:
        return (
            "```rust\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::*;\n\n"
            "    // Pattern: fixture construction from trace Init state\n"
            "    fn make_dag(nodes: &[&str], edges: &[(&str, &str)]) -> RegistryDag {\n"
            "        let mut dag = RegistryDag::new();\n"
            "        for nid in nodes {\n"
            "            dag.add_node(Node::behavior(nid, nid, \"g\", \"w\", \"t\"));\n"
            "        }\n"
            "        for (src, dst) in edges {\n"
            "            dag.add_edge(Edge::new(src, dst, EdgeType::Imports));\n"
            "        }\n"
            "        dag\n"
            "    }\n\n"
            "    #[test]\n"
            "    fn test_invariant() {\n"
            "        let dag = make_dag(&[\"a\", \"b\"], &[(\"a\", \"b\")]);\n"
            "        let result = dag.query_impact(\"a\");\n"
            "        assert!(!result.is_empty());\n"
            "    }\n\n"
            "    #[test]\n"
            "    #[should_panic(expected = \"not found\")]\n"
            "    fn test_invalid_input() {\n"
            "        let dag = make_dag(&[], &[]);\n"
            "        dag.query_impact(\"nonexistent\");\n"
            "    }\n"
            "}\n"
            "```\n"
        )

    def build_import_instructions(self, module_name: str) -> str:
        return (
            f"- CRITICAL: Use EXACT crate/module paths from the API Context section above.\n"
            f"  Use `use {module_name}::dag::RegistryDag;` for the main type\n"
            f"  Use `use {module_name}::types::{{Node, Edge, EdgeType}};` for type imports\n"
            f"- Place tests in a `#[cfg(test)] mod tests` block with `use super::*;`\n"
        )
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustPrompts` passes

---

### Behavior 15: Rust test file verification

#### Test Specification
**Given**: A valid Rust test file
**When**: Calling `verify_test_file()`
**Then**: Runs `cargo check` → `cargo test --no-run` → `cargo test`

**Given**: A `.rs` file with a compile error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

#### TDD Cycle

##### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustVerification:
    def test_verify_catches_compile_error(self, tmp_path):
        profile = RustProfile()
        test_file = tmp_path / "test_bad.rs"
        test_file.write_text("fn main() { let x: i32 = \"not a number\"; }")
        result = profile.verify_test_file(test_file, tmp_path)
        assert not result.passed
        assert result.stage == "compile"

    def test_verify_passes_valid_test(self, tmp_path):
        """Integration test — requires cargo in PATH."""
        profile = RustProfile()
        # Set up minimal Cargo project
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "test_proj"\nversion = "0.1.0"\nedition = "2021"\n'
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "lib.rs").write_text(
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    #[test]\n"
            "    fn it_works() {\n"
            "        assert_eq!(2 + 2, 4);\n"
            "    }\n"
            "}\n"
        )
        result = profile.verify_test_file(src / "lib.rs", tmp_path)
        assert result.passed
```

Note: Tests that invoke `cargo` should be marked `@pytest.mark.integration`
and skipped if `cargo` isn't installed.

##### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess
    from registry.test_gen_loop import VerifyResult

    # Stage 1: Compile check
    result = subprocess.run(
        ["cargo", "check"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="compile",
                          errors=[f"cargo check failed (rc={result.returncode})"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 2: Test discovery (compile tests without running)
    result = subprocess.run(
        ["cargo", "test", "--no-run"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="collect",
                          errors=[f"cargo test --no-run failed"],
                          stdout=result.stdout, stderr=result.stderr)

    # Stage 3: Run tests
    result = subprocess.run(
        ["cargo", "test"],
        capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(passed=False, stage="run",
                          errors=[f"cargo test failed"],
                          stdout=result.stdout, stderr=result.stderr)

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustVerification` passes (with mocked subprocess or integration mark)

---

### Behavior 16: Rust code extraction from LLM response

#### Test Specification
**Given**: LLM response with ` ```rust\n...code...\n``` `
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the Rust code without fences

#### TDD Cycle

##### Red: Write Failing Test
**File**: `python/tests/test_lang_rust.py` (append)
```python
class TestRustExtraction:
    def test_strips_rust_fences(self):
        profile = RustProfile()
        response = '```rust\n#[test]\nfn test_it() { assert!(true); }\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith("#[test]")
        assert "```" not in code

    def test_strips_bare_fences(self):
        profile = RustProfile()
        response = '```\nfn main() {}\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code
        assert "fn main" in code

    def test_handles_no_fences(self):
        profile = RustProfile()
        response = "#[test]\nfn test_it() { assert!(true); }"
        code = profile.extract_code_from_response(response)
        assert "#[test]" in code
```

##### Green
```python
def extract_code_from_response(self, response: str) -> str:
    import re
    text = response.strip()
    fenced = re.findall(r"```(?:rust|rs)?\n(.*?)```", text, re.DOTALL)
    if fenced:
        return max(fenced, key=len).strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustExtraction` passes

---

### Behavior 17: Rust output file naming

#### Test Specification
**Given**: `RustProfile` and a gwt_id
**When**: Calling `test_file_name(gwt_id)`
**Then**: Returns idiomatic Rust test file name

#### TDD Cycle

##### Red: Write Failing Test
```python
class TestRustOutputPath:
    def test_rust_output_path(self):
        profile = RustProfile()
        gwt_id = "gwt-0024"
        expected = "test_gwt_0024.rs"
        assert profile.test_file_name(gwt_id) == expected

    def test_rust_file_extension(self):
        profile = RustProfile()
        assert profile.test_file_extension == ".rs"

    def test_rust_fence_tag(self):
        profile = RustProfile()
        assert profile.fence_language_tag == "rust"
```

##### Green
```python
class RustProfile:
    test_file_extension: str = ".rs"
    fence_language_tag: str = "rust"

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"test_{safe_id}.rs"
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_rust.py::TestRustOutputPath` passes

---

## Phase 3 Checkpoint

At this point:
- `RustProfile` fully implements `LanguageProfile`
- `cw9 gen-tests gwt-0024 --lang rust` produces `.rs` test files
- Python and TypeScript paths are unchanged
- Three implementations validate the abstraction

**Gate**: `pytest` full suite passes. Manual: `cw9 gen-tests gwt-0024 --lang rust`
on a project with `.rs` source files.

---

## Phase 4: Go Implementation

### Behavior 18: Go assertion compiler

#### Test Specification
**Given**: TLA+ condition `x \in S /\ y = 3`
**When**: Compiling for Go
**Then**: Produces `slices.Contains(s, x) && y == 3`

**Given**: `\A x \in S : x > 0`
**When**: Compiling for Go
**Then**: Produces a for-loop with assertion (Go lacks iterator methods)

**Given**: `Len(seq) > 0`
**When**: Compiling for Go
**Then**: Produces `len(seq) > 0`

#### TDD Cycle

##### Red: Write Failing Test
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
```

##### Green
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

**Note**: Go's lack of generics-based iterator methods means quantifiers compile
to helper functions or inline loops. The compiler should emit helper function
definitions alongside assertions when quantifiers are used.

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoCompiler` passes
- [ ] Full suite still passes

---

### Behavior 19: Go API context discovery

#### Test Specification
**Given**: A directory with `.go` files containing `func `, `type ... struct`, `type ... interface`
**When**: Calling `profile.discover_api_context(source_dir, module_name)`
**Then**: Returns a string containing the exported signatures

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
Implement `GoProfile.discover_api_context()`:
- Glob for `*.go` files (excluding `*_test.go`)
- Extract lines with `func `, `type ... struct`, `type ... interface`, `const`, `var`
- Include doc comments (`//`) preceding exported items

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoApiDiscovery` passes

---

### Behavior 20: Go prompts and structural patterns

#### Test Specification
**Given**: `GoProfile`
**When**: Calling `build_system_prompt()`
**Then**: Mentions Go, `testing` package, not Python/Rust/TS

**When**: Calling `build_structural_patterns()`
**Then**: Contains `func Test`, `t.Run(`, `t.Errorf`, Go import syntax

**When**: Calling `build_import_instructions("sample_module")`
**Then**: Contains Go `import` statements

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
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

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoPrompts` passes

---

### Behavior 21: Go test file verification

#### Test Specification
**Given**: A valid `_test.go` file
**When**: Calling `verify_test_file()`
**Then**: Runs `go vet` → `go test -list .` → `go test -v`

**Given**: A `_test.go` file with a compile error
**When**: Calling `verify_test_file()`
**Then**: Returns `VerifyResult(passed=False, stage="compile")`

#### TDD Cycle

##### Red: Write Failing Test
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

Note: Tests that invoke `go` should be marked `@pytest.mark.integration`
and skipped if `go` isn't installed.

##### Green
```python
def verify_test_file(self, test_path, source_dir, collect_timeout=30, run_timeout=120):
    import subprocess
    from registry.test_gen_loop import VerifyResult

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

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoVerification` passes (with mocked subprocess or integration mark)

---

### Behavior 22: Go code extraction from LLM response

#### Test Specification
**Given**: LLM response with ` ```go\n...code...\n``` `
**When**: Calling `extract_code_from_response()`
**Then**: Returns just the Go code without fences

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
```python
def extract_code_from_response(self, response: str) -> str:
    import re
    text = response.strip()
    fenced = re.findall(r"```(?:go|golang)?\n(.*?)```", text, re.DOTALL)
    if fenced:
        return max(fenced, key=len).strip()
    lines = text.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoExtraction` passes

---

### Behavior 23: Go output file naming

#### Test Specification
**Given**: `GoProfile` and a gwt_id
**When**: Calling `test_file_name(gwt_id)`
**Then**: Returns Go-idiomatic test file name (`_test.go` suffix)

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
```python
class GoProfile:
    test_file_extension: str = "_test.go"
    fence_language_tag: str = "go"

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"{safe_id}_test.go"
```

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang_go.py::TestGoOutputPath` passes

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

### Behavior 24: get_profile() factory returns all four profiles

#### Test Specification
**Given**: `get_profile(TargetLanguage.RUST)`
**When**: Called
**Then**: Returns a `RustProfile` instance

**Given**: `get_profile(TargetLanguage.GO)`
**When**: Called
**Then**: Returns a `GoProfile` instance

#### TDD Cycle

##### Red: Write Failing Test
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

##### Green
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

#### Success Criteria
**Automated:**
- [ ] `pytest tests/test_lang.py::TestGetProfileFactory` passes
- [ ] No `NotImplementedError` for any `TargetLanguage` value
- [ ] Full suite: `pytest`

---

## Implementation Order

```
Phase 1 (Strangler Fig):
  B1: TargetLanguage enum ................ ~15 min
  B2: LanguageProfile protocol ........... ~30 min
  B3: PythonProfile (wrap existing) ...... ~1 hr
  B4: TestGenContext refactor ............ ~1 hr
  B5: CLI --lang flag .................... ~30 min
  B6: Output path logic .................. ~15 min
  ── Checkpoint: all tests pass, Python unchanged ──

Phase 2 (TypeScript):
  B7:  TS assertion compiler ............. ~1 hr
  B8:  TS API discovery .................. ~30 min
  B9:  TS prompts ....................... ~30 min
  B10: TS verification ................... ~1 hr
  B11: TS code extraction ................ ~15 min
  ── Checkpoint: --lang typescript works ──

Phase 3 (Rust):
  B12: Rust assertion compiler ........... ~1 hr
  B13: Rust API discovery ................ ~30 min
  B14: Rust prompts ...................... ~30 min
  B15: Rust verification ................. ~1 hr
  B16: Rust code extraction .............. ~15 min
  B17: Rust output file naming ........... ~15 min
  ── Checkpoint: --lang rust works ──

Phase 4 (Go):
  B18: Go assertion compiler ............. ~1 hr
  B19: Go API discovery .................. ~30 min
  B20: Go prompts ........................ ~30 min
  B21: Go verification ................... ~1 hr
  B22: Go code extraction ................ ~15 min
  B23: Go output file naming ............. ~15 min
  B24: get_profile() factory complete .... ~15 min
  ── Checkpoint: --lang go works, all 4 languages complete ──
```

## References

- Bridge implementation: `python/registry/bridge.py`
- TLA+ compiler: `python/registry/tla_compiler.py`
- Test gen loop: `python/registry/test_gen_loop.py`
- CLI: `python/registry/cli.py`
- Context: `python/registry/context.py`
- Existing bridge tests: `python/tests/test_bridge.py`
- Existing compiler tests: `python/tests/test_tla_compiler.py`
- Existing CLI tests: `python/tests/test_cli.py`
- Pipeline plan review (typed IR gap): `thoughts/searchable/shared/docs/registry-driven-pipeline-plan-REVIEW.md`
