"""Rust language profile for multi-language test generation.

Compiles TLA+ conditions to Rust expressions and provides Rust-specific
prompt patterns, API discovery, and verification via cargo.
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


class RustProfile:
    """Rust test generation profile.

    Uses #[test] attribute and cargo test for verification.
    """

    test_file_extension: str = ".rs"
    fence_language_tag: str = "rust|rs"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        """Compile a TLA+ condition to a Rust expression.

        Mapping:
          \\in       -> .contains(&x)
          /\\        -> &&
          \\/        -> ||
          =          -> ==
          #          -> !=
          \\A x \\in S : P  -> s.iter().all(|x| P)
          \\E x \\in S : P  -> s.iter().any(|x| P)
          Len(x)     -> x.len()
          Cardinality(S) -> s.len()
          TRUE/FALSE -> true/false
          state.field -> state.field (struct dot access)
        """
        original = tla_expr
        expr = tla_expr.strip()

        # Phase 1: Strip dirty guard
        expr = re.sub(r'dirty\s*=\s*TRUE\s*[/\\]+\s*', '', expr)

        # Phase 2: Boolean literals
        expr = expr.replace('TRUE', 'true').replace('FALSE', 'false')

        # Phase 5: Quantifiers (MUST run before \\in replacement)
        # Universal: \A x \in S : P(x) -> S.iter().all(|x| P(x))
        expr = re.sub(
            r'\\A\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)',
            r'\2.iter().all(|\1| \3)',
            expr
        )
        # Existential: \E x \in S : P(x) -> S.iter().any(|x| P(x))
        expr = re.sub(
            r'\\E\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)',
            r'\2.iter().any(|\1| \3)',
            expr
        )

        # Phase 6: Set/sequence operators (after quantifiers)
        expr = re.sub(r'(\w+)\s+\\in\s+(\w+)', r'\2.contains(&\1)', expr)
        expr = re.sub(r'(\w+)\s+\\notin\s+(\w+)', r'!\2.contains(&\1)', expr)

        # Phase 3: Equality/inequality
        expr = re.sub(r'(?<!=)(?<!!)=(?!=)', '==', expr)
        expr = expr.replace('#', '!=')

        # Phase 4: Logical operators
        expr = expr.replace('/\\', ' && ')
        expr = expr.replace('\\/', ' || ')

        # Phase 7: Built-in functions
        expr = re.sub(r'Len\((\w+)\)', r'\1.len()', expr)
        expr = re.sub(r'Cardinality\((\w+)\)', r'\1.len()', expr)
        expr = re.sub(r'DOMAIN\s+(\w+)', r'\1.keys()', expr)

        # Phase 8: Tuple literals  <<a, b>> -> (a, b)
        expr = re.sub(r'<<(.+?)>>', r'(\1)', expr)

        # No record field access transformation — Rust uses dot access for struct fields

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
        """Scan Rust source files for public signatures."""
        candidates = list(source_dir.glob("src/**/*.rs"))
        candidates.extend(source_dir.glob("*.rs"))
        # Exclude test files
        candidates = [f for f in candidates if not f.name.startswith("test_")]

        if not candidates:
            return f"// No source found for module '{module_name}' in {source_dir}"

        lines = [f"// API context for module: {module_name}"]
        for src_path in candidates[:7]:
            lines.append(f"\n// --- {src_path.name} ---")
            try:
                source = src_path.read_text()
                for line in source.splitlines():
                    stripped = line.strip()
                    if (stripped.startswith(("pub fn", "pub struct", "pub trait",
                                           "pub enum", "pub type", "pub const",
                                           "impl ", "use "))
                        or stripped.startswith("///")
                        or stripped.startswith("@")):
                        lines.append(line)
            except OSError:
                lines.append(f"// Could not read {src_path}")
        return "\n".join(lines)

    def build_system_prompt(self) -> str:
        return (
            "You are a Rust test generation expert. You generate complete, runnable "
            "Rust test modules from formal specifications and API documentation. "
            "You use ONLY the real crate imports provided -- never create mock structs "
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

    def verify_test_file(
        self, test_path: Path, source_dir: Path,
        collect_timeout: int = 30, run_timeout: int = 120,
    ) -> VerifyResult:
        import subprocess

        # Stage 1: Compile check
        result = subprocess.run(
            ["cargo", "check"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="compile",
                errors=[f"cargo check failed (rc={result.returncode})"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 2: Test discovery
        result = subprocess.run(
            ["cargo", "test", "--no-run"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="collect",
                errors=["cargo test --no-run failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 3: Run tests
        result = subprocess.run(
            ["cargo", "test"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="run",
                errors=["cargo test failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        return VerifyResult(passed=True, stage="run", stdout=result.stdout)

    def extract_code_from_response(self, response: str) -> str:
        return _extract_code_by_fence_tag(response, self.fence_language_tag)

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"test_{safe_id}.rs"
