"""Go language profile for multi-language test generation.

Compiles TLA+ conditions to Go expressions and provides Go-specific
prompt patterns, API discovery, and verification via go test.

Go quantifier compilation strategy:
  Go lacks expression-level iterator methods (all(), .every(), .iter().all()).
  Quantifiers compile to helper function references emitted as helper_defs.
  The CompiledExpression.helper_defs field carries the required preamble code.
"""

from __future__ import annotations

import re
from pathlib import Path

from registry.lang import (
    CompiledExpression,
    CompileError,
    VerifyResult,
    _extract_code_by_fence_tag,
)


# Go quantifier helper templates
_ALL_SATISFY_HELPER = (
    "func allSatisfy[T any](s []T, pred func(T) bool) bool {\n"
    "\tfor _, x := range s {\n"
    "\t\tif !pred(x) { return false }\n"
    "\t}\n"
    "\treturn true\n"
    "}\n"
)

_ANY_SATISFY_HELPER = (
    "func anySatisfy[T any](s []T, pred func(T) bool) bool {\n"
    "\tfor _, x := range s {\n"
    "\t\tif pred(x) { return true }\n"
    "\t}\n"
    "\treturn false\n"
    "}\n"
)


class GoProfile:
    """Go test generation profile.

    Uses the standard testing package with table-driven tests.
    Code fence extraction handles both ```go and ```golang variants.
    """

    test_file_extension: str = "_test.go"
    fence_language_tag: str = "go|golang"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        """Compile a TLA+ condition to a Go expression.

        Mapping:
          \\in       -> slices.Contains(s, x)
          /\\        -> &&
          \\/        -> ||
          =          -> ==
          #          -> !=
          \\A x \\in S : P  -> allSatisfy(S, func(x T) bool { return P })
          \\E x \\in S : P  -> anySatisfy(S, func(x T) bool { return P })
          Len(x)     -> len(x)
          Cardinality(S) -> len(s)
          TRUE/FALSE -> true/false
          state.field -> state.Field (exported/capitalized)
        """
        original = tla_expr
        expr = tla_expr.strip()
        helper_defs = ""

        # Phase 1: Strip dirty guard
        expr = re.sub(r'dirty\s*=\s*TRUE\s*[/\\]+\s*', '', expr)

        # Phase 2: Boolean literals
        expr = expr.replace('TRUE', 'true').replace('FALSE', 'false')

        # Phase 5: Quantifiers (MUST run before \\in replacement)
        # Universal: \A x \in S : P(x) -> allSatisfy(S, func(x int) bool { return P(x) })
        m_all = re.search(r'\\A\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)', expr)
        if m_all:
            var, collection, predicate = m_all.group(1), m_all.group(2), m_all.group(3)
            # Clean up the predicate
            pred_clean = predicate.strip()
            expr = re.sub(
                r'\\A\s+\w+\s+\\in\s+\w+\s*:\s*.+',
                f'allSatisfy({collection}, func({var} int) bool {{ return {pred_clean} }})',
                expr
            )
            helper_defs = _ALL_SATISFY_HELPER

        m_any = re.search(r'\\E\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)', expr)
        if m_any:
            var, collection, predicate = m_any.group(1), m_any.group(2), m_any.group(3)
            pred_clean = predicate.strip()
            expr = re.sub(
                r'\\E\s+\w+\s+\\in\s+\w+\s*:\s*.+',
                f'anySatisfy({collection}, func({var} int) bool {{ return {pred_clean} }})',
                expr
            )
            helper_defs = _ANY_SATISFY_HELPER

        # Phase 6: Set/sequence operators (after quantifiers)
        expr = re.sub(r'(\w+)\s+\\in\s+(\w+)', r'slices.Contains(\2, \1)', expr)
        expr = re.sub(r'(\w+)\s+\\notin\s+(\w+)', r'!slices.Contains(\2, \1)', expr)

        # Phase 3: Equality/inequality
        expr = re.sub(r'(?<!=)(?<!!)=(?!=)', '==', expr)
        expr = expr.replace('#', '!=')

        # Phase 4: Logical operators
        expr = expr.replace('/\\', ' && ')
        expr = expr.replace('\\/', ' || ')

        # Phase 7: Built-in functions
        expr = re.sub(r'Len\((\w+)\)', r'len(\1)', expr)
        expr = re.sub(r'Cardinality\((\w+)\)', r'len(\1)', expr)

        # Phase 8: Tuple literals  <<a, b>> -> [2]interface{}{a, b}
        expr = re.sub(r'<<(.+?)>>', r'[]interface{}{\1}', expr)

        # Phase 9: Record field access — capitalize for Go exported fields
        expr = re.sub(
            rf'{state_var}\.(\w+)',
            lambda m: f'{state_var}.{m.group(1)[0].upper()}{m.group(1)[1:]}',
            expr
        )

        # Extract variable names referenced
        variables = re.findall(rf'{state_var}\.(\w+)', expr)

        # Validation
        remaining_tla = re.findall(r'\\[A-Za-z]+', expr)
        if remaining_tla:
            raise CompileError(
                f"Unsupported TLA+ operators: {remaining_tla} in expression: {original}"
            )

        return CompiledExpression(
            target_expr=expr.strip(),
            original_tla=original,
            variables_used=list(set(variables)),
            helper_defs=helper_defs,
        )

    def compile_assertions(
        self, verifiers: dict, state_var: str = "state",
    ) -> dict[str, CompiledExpression]:
        results = {}
        for name, v in verifiers.items():
            if not isinstance(v, dict):
                continue
            condition = v.get("condition", "")
            if condition:
                results[name] = self.compile_condition(condition, state_var)
        return results

    def discover_api_context(self, source_dir: Path, module_name: str) -> str:
        """Scan Go source files for exported signatures."""
        candidates = list(source_dir.glob("**/*.go"))
        # Exclude test files and vendor
        candidates = [
            f for f in candidates
            if not f.name.endswith("_test.go")
            and "vendor" not in str(f)
        ]

        if not candidates:
            return f"// No source found for module '{module_name}' in {source_dir}"

        lines = [f"// API context for module: {module_name}"]
        for src_path in candidates[:7]:
            lines.append(f"\n// --- {src_path.name} ---")
            try:
                source = src_path.read_text()
                for line in source.splitlines():
                    stripped = line.strip()
                    if (stripped.startswith(("func ", "type ", "const ", "var ",
                                           "import ", "package "))
                        or stripped.startswith("//")):
                        lines.append(line)
            except OSError:
                lines.append(f"// Could not read {src_path}")
        return "\n".join(lines)

    def build_system_prompt(self) -> str:
        return (
            "You are a Go test generation expert. You generate complete, runnable "
            "Go test files from formal specifications and API documentation. "
            "You use ONLY the real package imports provided -- never create mock structs "
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
            "\t\tname    string\n"
            "\t\tinput   string\n"
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
            f"- Use `testing` package -- do NOT import testify unless it's in the project\n"
        )

    def verify_test_file(
        self, test_path: Path, source_dir: Path,
        collect_timeout: int = 30, run_timeout: int = 120,
    ) -> VerifyResult:
        import subprocess

        # Stage 1: Vet (includes compile check)
        result = subprocess.run(
            ["go", "vet", "./..."],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="compile",
                errors=[f"go vet failed (rc={result.returncode})"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 2: Test discovery
        result = subprocess.run(
            ["go", "test", "-list", ".", "./..."],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="collect",
                errors=["go test -list failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 3: Run tests
        result = subprocess.run(
            ["go", "test", "-v", "./..."],
            capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="run",
                errors=["go test failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        return VerifyResult(passed=True, stage="run", stdout=result.stdout)

    def extract_code_from_response(self, response: str) -> str:
        return _extract_code_by_fence_tag(response, self.fence_language_tag)

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"{safe_id}_test.go"
