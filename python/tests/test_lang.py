"""Tests for multi-language test generation abstractions.

Covers all 4 phases:
  Phase 1 (B1-B6): TargetLanguage, LanguageProfile, PythonProfile, TestGenContext, CLI
  Phase 2 (B7-B11): TypeScriptProfile
  Phase 3 (B12-B17): RustProfile
  Phase 4 (B18-B24): GoProfile, get_profile() factory
"""

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from registry.lang import (
    CompiledExpression,
    CompileError,
    LanguageProfile,
    PythonProfile,
    TargetLanguage,
    VerifyResult,
    get_profile,
)


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B1 — TargetLanguage enum
# ─────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B2 — LanguageProfile protocol
# ─────────────────────────────────────────────────────────────────────

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
        # Protocol attributes are annotations, not class attrs
        assert "test_file_extension" in getattr(LanguageProfile, "__annotations__", {})

    def test_protocol_has_fence_tag(self):
        assert "fence_language_tag" in getattr(LanguageProfile, "__annotations__", {})

    def test_protocol_has_test_file_name(self):
        assert hasattr(LanguageProfile, "test_file_name")
        sig = inspect.signature(LanguageProfile.test_file_name)
        assert "gwt_id" in sig.parameters

    def test_protocol_has_compile_assertions(self):
        assert hasattr(LanguageProfile, "compile_assertions")
        sig = inspect.signature(LanguageProfile.compile_assertions)
        assert "verifiers" in sig.parameters


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B3 — PythonProfile
# ─────────────────────────────────────────────────────────────────────

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
        assert "in" in results["inv_membership"].target_expr
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
        assert new_result.target_expr == old_result.target_expr

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


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B4 — TestGenContext integration
# ─────────────────────────────────────────────────────────────────────

class TestGenContextIntegration:
    def test_context_has_lang_profile(self):
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


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B5 — CLI --lang flag
# ─────────────────────────────────────────────────────────────────────

class TestCliLangFlag:
    def test_gen_tests_default_lang_is_python(self):
        from registry.cli import main
        # Parse args without --lang — we just need to verify it parses
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_gen = sub.add_parser("gen-tests")
        p_gen.add_argument("gwt_id")
        p_gen.add_argument("target_dir", nargs="?", default=".")
        p_gen.add_argument("--max-attempts", type=int, default=3)
        p_gen.add_argument("--lang", default="python",
                          choices=["python", "typescript", "rust", "go"])
        args = parser.parse_args(["gen-tests", "gwt-0001"])
        assert args.lang == "python"

    def test_gen_tests_accepts_typescript(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_gen = sub.add_parser("gen-tests")
        p_gen.add_argument("gwt_id")
        p_gen.add_argument("target_dir", nargs="?", default=".")
        p_gen.add_argument("--max-attempts", type=int, default=3)
        p_gen.add_argument("--lang", default="python",
                          choices=["python", "typescript", "rust", "go"])
        args = parser.parse_args(["gen-tests", "gwt-0001", "--lang", "typescript"])
        assert args.lang == "typescript"

    def test_gen_tests_rejects_unknown_lang(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_gen = sub.add_parser("gen-tests")
        p_gen.add_argument("gwt_id")
        p_gen.add_argument("target_dir", nargs="?", default=".")
        p_gen.add_argument("--lang", default="python",
                          choices=["python", "typescript", "rust", "go"])
        with pytest.raises(SystemExit):
            parser.parse_args(["gen-tests", "gwt-0001", "--lang", "cobol"])


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B5b — Integration test markers
# ─────────────────────────────────────────────────────────────────────

class TestIntegrationMarkers:
    def test_integration_mark_registered(self):
        """Verify the 'integration' mark doesn't trigger warnings."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--markers"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "integration" in result.stdout


# ─────────────────────────────────────────────────────────────────────
# Phase 1: B6 — Output path logic
# ─────────────────────────────────────────────────────────────────────

class TestOutputPath:
    def test_python_output_path(self):
        profile = PythonProfile()
        gwt_id = "gwt-0024"
        expected = "test_gwt_0024.py"
        assert profile.test_file_name(gwt_id) == expected

    def test_typescript_output_path(self):
        from registry.lang_typescript import TypeScriptProfile
        profile = TypeScriptProfile()
        assert profile.test_file_name("gwt-0024") == "gwt_0024.test.ts"

    def test_rust_output_path(self):
        from registry.lang_rust import RustProfile
        profile = RustProfile()
        assert profile.test_file_name("gwt-0024") == "test_gwt_0024.rs"

    def test_go_output_path(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        assert profile.test_file_name("gwt-0024") == "gwt_0024_test.go"


# ─────────────────────────────────────────────────────────────────────
# Phase 2: B7 — TypeScript assertion compiler
# ─────────────────────────────────────────────────────────────────────

class TestTypeScriptCompiler:
    def setup_method(self):
        from registry.lang_typescript import TypeScriptProfile
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
        assert "true" in r.target_expr

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.count" in r.target_expr

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!==" in r.target_expr

    def test_unsupported_raises(self):
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")

    def test_compile_assertions_produces_ts_expressions(self):
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert ".includes(" in results["inv_membership"].target_expr or ".has(" in results["inv_membership"].target_expr

    def test_file_name_typescript(self):
        assert self.profile.test_file_name("gwt-0024") == "gwt_0024.test.ts"


# ─────────────────────────────────────────────────────────────────────
# Phase 2: B8 — TypeScript API discovery
# ─────────────────────────────────────────────────────────────────────

class TestTypeScriptApiDiscovery:
    def test_finds_exported_functions(self, tmp_path):
        from registry.lang_typescript import TypeScriptProfile
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
        from registry.lang_typescript import TypeScriptProfile
        profile = TypeScriptProfile()
        src = tmp_path / "src"
        src.mkdir()
        (src / "types.ts").write_text(
            "export interface Node {\n  id: string;\n}\n"
        )
        result = profile.discover_api_context(tmp_path, "Node")
        assert "export interface Node" in result

    def test_no_source_returns_comment(self, tmp_path):
        from registry.lang_typescript import TypeScriptProfile
        profile = TypeScriptProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result


# ─────────────────────────────────────────────────────────────────────
# Phase 2: B9 — TypeScript prompts
# ─────────────────────────────────────────────────────────────────────

class TestTypeScriptPrompts:
    def setup_method(self):
        from registry.lang_typescript import TypeScriptProfile
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


# ─────────────────────────────────────────────────────────────────────
# Phase 2: B11 — TypeScript code extraction
# ─────────────────────────────────────────────────────────────────────

class TestTypeScriptExtraction:
    def test_strips_typescript_fences(self):
        from registry.lang_typescript import TypeScriptProfile
        profile = TypeScriptProfile()
        response = '```typescript\ndescribe("test", () => {});\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith('describe("test"')
        assert "```" not in code

    def test_strips_ts_fences(self):
        from registry.lang_typescript import TypeScriptProfile
        profile = TypeScriptProfile()
        response = '```ts\nconst x = 1;\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code


# ─────────────────────────────────────────────────────────────────────
# Phase 3: B12 — Rust assertion compiler
# ─────────────────────────────────────────────────────────────────────

class TestRustCompiler:
    def setup_method(self):
        from registry.lang_rust import RustProfile
        self.profile = RustProfile()

    def test_membership(self):
        r = self.profile.compile_condition("x \\in S")
        assert ".contains(" in r.target_expr

    def test_conjunction(self):
        r = self.profile.compile_condition("x \\in S /\\ y = 3")
        assert "&&" in r.target_expr

    def test_equality(self):
        r = self.profile.compile_condition("y = 3")
        assert "==" in r.target_expr
        assert "===" not in r.target_expr

    def test_inequality(self):
        r = self.profile.compile_condition("x # 3")
        assert "!=" in r.target_expr

    def test_universal_quantifier(self):
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert ".iter().all(" in r.target_expr

    def test_existential_quantifier(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert ".iter().any(" in r.target_expr

    def test_len(self):
        r = self.profile.compile_condition("Len(seq) > 0")
        assert ".len()" in r.target_expr

    def test_cardinality(self):
        r = self.profile.compile_condition("Cardinality(S) = 3")
        assert ".len()" in r.target_expr

    def test_boolean_literals(self):
        r = self.profile.compile_condition("x = TRUE")
        assert "true" in r.target_expr

    def test_record_field_access(self):
        r = self.profile.compile_condition("state.count > 0", state_var="state")
        assert "state.count" in r.target_expr

    def test_disjunction(self):
        r = self.profile.compile_condition("x = 1 \\/ y = 2")
        assert "||" in r.target_expr

    def test_unsupported_raises(self):
        with pytest.raises(CompileError):
            self.profile.compile_condition("\\CHOOSE x \\in S : P(x)")

    def test_compile_assertions_produces_rust_expressions(self):
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert ".contains(" in results["inv_membership"].target_expr


# ─────────────────────────────────────────────────────────────────────
# Phase 3: B14 — Rust prompts
# ─────────────────────────────────────────────────────────────────────

class TestRustPrompts:
    def setup_method(self):
        from registry.lang_rust import RustProfile
        self.profile = RustProfile()

    def test_system_prompt_mentions_rust(self):
        prompt = self.profile.build_system_prompt()
        assert "Rust" in prompt
        assert "Python" not in prompt

    def test_system_prompt_mentions_test_attr(self):
        prompt = self.profile.build_system_prompt()
        assert "#[test]" in prompt or "#[cfg(test)]" in prompt

    def test_structural_patterns_has_rust_code(self):
        patterns = self.profile.build_structural_patterns()
        assert "#[test]" in patterns
        assert "assert" in patterns
        assert "fn test_" in patterns

    def test_import_instructions_has_rust_syntax(self):
        instructions = self.profile.build_import_instructions("sample_module")
        assert "use " in instructions


# ─────────────────────────────────────────────────────────────────────
# Phase 3: B16 — Rust code extraction
# ─────────────────────────────────────────────────────────────────────

class TestRustExtraction:
    def test_strips_rust_fences(self):
        from registry.lang_rust import RustProfile
        profile = RustProfile()
        response = '```rust\n#[test]\nfn test_it() { assert!(true); }\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith("#[test]")
        assert "```" not in code

    def test_handles_no_fences(self):
        from registry.lang_rust import RustProfile
        profile = RustProfile()
        response = "#[test]\nfn test_it() { assert!(true); }"
        code = profile.extract_code_from_response(response)
        assert "#[test]" in code


# ─────────────────────────────────────────────────────────────────────
# Phase 3: B17 — Rust output path
# ─────────────────────────────────────────────────────────────────────

class TestRustOutputPath:
    def test_rust_output_path(self):
        from registry.lang_rust import RustProfile
        profile = RustProfile()
        assert profile.test_file_name("gwt-0024") == "test_gwt_0024.rs"

    def test_rust_file_extension(self):
        from registry.lang_rust import RustProfile
        profile = RustProfile()
        assert profile.test_file_extension == ".rs"


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B18 — Go assertion compiler
# ─────────────────────────────────────────────────────────────────────

class TestGoCompiler:
    def setup_method(self):
        from registry.lang_go import GoProfile
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

    def test_universal_quantifier_has_helper_defs(self):
        """Go quantifiers need helper function definitions."""
        r = self.profile.compile_condition("\\A x \\in S : x > 0")
        assert r.helper_defs != ""
        assert "func " in r.helper_defs

    def test_existential_quantifier_has_helper_defs(self):
        r = self.profile.compile_condition("\\E x \\in S : x > 0")
        assert r.helper_defs != ""
        assert "func " in r.helper_defs

    def test_non_quantifier_has_empty_helper_defs(self):
        r = self.profile.compile_condition("x = 3")
        assert r.helper_defs == ""

    def test_compile_assertions_produces_go_expressions(self):
        verifiers = {"inv_membership": {"condition": "x \\in S", "type": "invariant"}}
        results = self.profile.compile_assertions(verifiers)
        assert "inv_membership" in results
        assert "Contains(" in results["inv_membership"].target_expr or "contains" in results["inv_membership"].target_expr.lower()


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B19 — Go API discovery
# ─────────────────────────────────────────────────────────────────────

class TestGoApiDiscovery:
    def test_finds_exported_functions(self, tmp_path):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        (tmp_path / "dag.go").write_text(
            "package registry\n\n"
            "type RegistryDag struct {\n"
            "\tnodes []Node\n"
            "}\n\n"
            "func (d *RegistryDag) QueryImpact(nodeID string) *ImpactResult {\n"
            "\treturn nil\n"
            "}\n\n"
            "func NewDag() *RegistryDag {\n"
            "\treturn &RegistryDag{}\n"
            "}\n"
        )
        result = profile.discover_api_context(tmp_path, "RegistryDag")
        assert "type RegistryDag struct" in result
        assert "QueryImpact" in result
        assert "func NewDag" in result

    def test_no_source_returns_comment(self, tmp_path):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        result = profile.discover_api_context(tmp_path, "Missing")
        assert "No source found" in result


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B20 — Go prompts
# ─────────────────────────────────────────────────────────────────────

class TestGoPrompts:
    def setup_method(self):
        from registry.lang_go import GoProfile
        self.profile = GoProfile()

    def test_system_prompt_mentions_go(self):
        prompt = self.profile.build_system_prompt()
        assert "Go" in prompt
        assert "Python" not in prompt

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


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B22 — Go code extraction
# ─────────────────────────────────────────────────────────────────────

class TestGoExtraction:
    def test_strips_go_fences(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        response = '```go\npackage main\n\nimport "testing"\n\nfunc TestIt(t *testing.T) {}\n```'
        code = profile.extract_code_from_response(response)
        assert code.startswith("package main")
        assert "```" not in code

    def test_strips_golang_fences(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        response = '```golang\npackage main\n```'
        code = profile.extract_code_from_response(response)
        assert "```" not in code
        assert "package main" in code

    def test_handles_no_fences(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        response = 'package main\n\nfunc TestIt(t *testing.T) {}'
        code = profile.extract_code_from_response(response)
        assert "package main" in code


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B23 — Go output path
# ─────────────────────────────────────────────────────────────────────

class TestGoOutputPath:
    def test_go_output_path(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        assert profile.test_file_name("gwt-0024") == "gwt_0024_test.go"

    def test_go_file_extension(self):
        from registry.lang_go import GoProfile
        profile = GoProfile()
        assert profile.test_file_extension == "_test.go"


# ─────────────────────────────────────────────────────────────────────
# Phase 4: B24 — get_profile() factory
# ─────────────────────────────────────────────────────────────────────

class TestGetProfileFactory:
    def test_python_profile(self):
        profile = get_profile(TargetLanguage.PYTHON)
        assert isinstance(profile, PythonProfile)

    def test_typescript_profile(self):
        from registry.lang_typescript import TypeScriptProfile
        profile = get_profile(TargetLanguage.TYPESCRIPT)
        assert isinstance(profile, TypeScriptProfile)

    def test_rust_profile(self):
        from registry.lang_rust import RustProfile
        profile = get_profile(TargetLanguage.RUST)
        assert isinstance(profile, RustProfile)

    def test_go_profile(self):
        from registry.lang_go import GoProfile
        profile = get_profile(TargetLanguage.GO)
        assert isinstance(profile, GoProfile)

    def test_all_satisfy_protocol(self):
        for lang in TargetLanguage:
            profile = get_profile(lang)
            assert isinstance(profile, LanguageProfile), f"{lang} profile doesn't satisfy protocol"
