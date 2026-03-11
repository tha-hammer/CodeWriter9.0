"""Target language definitions for multi-language test generation.

Defines the TargetLanguage enum, LanguageProfile protocol, and PythonProfile
(the default/first implementation via strangler-fig refactor).

Cross-cutting design decisions:
  - VerifyResult lives here (not test_gen_loop.py) to prevent circular imports
  - CompiledExpression replaces CompiledAssertion (language-neutral naming)
  - _extract_code_by_fence_tag() is shared by all profiles
  - compile_assertions() is in the protocol (replaces tla_compiler.compile_assertions)
  - test_file_name() is in the protocol
  - Profiles are stateless -- get_profile() creates a new instance per call
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable


class TargetLanguage(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"


class CompileError(Exception):
    """Raised when a TLA+ expression uses unsupported operators."""
    pass


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
    attempt: int = 0


def _extract_code_by_fence_tag(response: str, fence_tag: str) -> str:
    """Shared extraction logic parameterized by language fence tag.

    Extracts the largest fenced code block matching the given fence tag,
    or returns unfenced code as-is. All 4 profiles delegate
    extract_code_from_response() to this function.
    """
    text = response.strip()

    # If there are markdown fences, extract the largest fenced block
    fenced = re.findall(rf"```(?:{fence_tag})?\n(.*?)```", text, re.DOTALL)
    if fenced:
        text = max(fenced, key=len).strip()
    else:
        # Strip single opening/closing fences
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Deduplicate: if the code is exactly repeated, take just the first copy
    half = len(text) // 2
    if half > 100:  # Only for substantial code
        first_half = text[:half].rstrip()
        second_half = text[half:].lstrip()
        if first_half == second_half:
            text = first_half

    return text


@runtime_checkable
class LanguageProfile(Protocol):
    """Protocol for language-specific test generation backends.

    Implementations MUST be stateless -- get_profile() creates a new instance
    per call. Do not cache or store mutable state on profile instances.
    """

    test_file_extension: str       # e.g., ".py", ".test.ts", "_test.go"
    fence_language_tag: str        # e.g., "python", "typescript|ts", "go|golang"

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
        match the target language.
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
        """Three-stage verification: syntax -> discovery -> execution."""
        ...

    def extract_code_from_response(self, response: str) -> str:
        """Extract target-language code from LLM response."""
        ...

    def test_file_name(self, gwt_id: str) -> str:
        """Return the output test file name for a given GWT ID."""
        ...


class PythonProfile:
    """Python test generation profile -- wraps existing code (strangler fig).

    Each method delegates to the existing functions in tla_compiler.py and
    test_gen_loop.py, producing byte-identical output.
    """

    test_file_extension: str = ".py"
    fence_language_tag: str = "python"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        from registry.tla_compiler import compile_condition as _compile
        result = _compile(tla_expr, state_var)
        return CompiledExpression(
            target_expr=result.target_expr,
            original_tla=result.original_tla,
            variables_used=result.variables_used,
        )

    def compile_assertions(
        self, verifiers: dict, state_var: str = "state",
    ) -> dict[str, CompiledExpression]:
        """Batch-compile all verifier conditions to Python expressions."""
        results = {}
        for name, verifier in verifiers.items():
            if not isinstance(verifier, dict):
                continue
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
            "You use ONLY the real API imports provided -- never create mock classes "
            "or re-implement the API. Output ONLY Python code, no markdown fencing "
            "or explanation."
        )

    def build_structural_patterns(self) -> str:
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

    def verify_test_file(
        self, test_path: Path, source_dir: Path,
        collect_timeout: int = 30, run_timeout: int = 120,
    ) -> VerifyResult:
        import subprocess
        import sys

        code = test_path.read_text()

        # Stage 1: Compile
        try:
            compile(code, str(test_path), "exec")
        except SyntaxError as e:
            return VerifyResult(
                passed=False, stage="compile",
                errors=[f"SyntaxError: {e.msg} (line {e.lineno})"],
            )

        # Stage 2: Collect
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "--collect-only", "-q"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="collect",
                errors=[f"pytest --collect-only failed (rc={result.returncode})"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 3: Run
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-x", "-v"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="run",
                errors=[f"pytest -x failed (rc={result.returncode})"],
                stdout=result.stdout, stderr=result.stderr,
            )

        return VerifyResult(passed=True, stage="run", stdout=result.stdout)

    def extract_code_from_response(self, response: str) -> str:
        return _extract_code_by_fence_tag(response, self.fence_language_tag)

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"test_{safe_id}.py"


def get_profile(lang: TargetLanguage) -> LanguageProfile:
    """Factory: return the appropriate LanguageProfile for the given language.

    Profiles are stateless -- each call creates a new instance.
    """
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
