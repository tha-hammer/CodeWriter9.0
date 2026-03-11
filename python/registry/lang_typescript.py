"""TypeScript language profile for multi-language test generation.

Compiles TLA+ conditions to TypeScript/JavaScript expressions and provides
TypeScript-specific prompt patterns, API discovery, and verification.
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


class TypeScriptProfile:
    """TypeScript test generation profile.

    Uses Jest/Vitest as the test framework. Code fence extraction handles
    both ```typescript and ```ts variants.
    """

    test_file_extension: str = ".test.ts"
    fence_language_tag: str = "typescript|ts"

    def compile_condition(self, tla_expr: str, state_var: str = "state") -> CompiledExpression:
        """Compile a TLA+ condition to a TypeScript expression.

        Mapping:
          \\in       -> .includes(x) or S.has(x)
          /\\        -> &&
          \\/        -> ||
          =          -> ===
          #          -> !==
          \\A x \\in S : P  -> S.every((x) => P)
          \\E x \\in S : P  -> S.some((x) => P)
          Len(x)     -> x.length
          Cardinality(S) -> S.size
          TRUE/FALSE -> true/false
          state.field -> state.field (native dot access)
        """
        original = tla_expr
        expr = tla_expr.strip()

        # Phase 1: Strip dirty guard
        expr = re.sub(r'dirty\s*=\s*TRUE\s*[/\\]+\s*', '', expr)

        # Phase 2: Boolean literals (before equality to avoid TRUE -> true issues)
        expr = expr.replace('TRUE', 'true').replace('FALSE', 'false')

        # Phase 5: Quantifiers (MUST run before \\in replacement)
        # Universal: \A x \in S : P(x) -> S.every((x) => P(x))
        expr = re.sub(
            r'\\A\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)',
            r'\2.every((\1) => \3)',
            expr
        )
        # Existential: \E x \in S : P(x) -> S.some((x) => P(x))
        expr = re.sub(
            r'\\E\s+(\w+)\s+\\in\s+(\w+)\s*:\s*(.+)',
            r'\2.some((\1) => \3)',
            expr
        )

        # Phase 6: Set/sequence operators (after quantifiers)
        # \in -> .includes()
        expr = re.sub(r'(\w+)\s+\\in\s+(\w+)', r'\2.includes(\1)', expr)
        expr = re.sub(r'(\w+)\s+\\notin\s+(\w+)', r'!\2.includes(\1)', expr)

        # Phase 3: Equality/inequality (after \\in to avoid mangling)
        expr = re.sub(r'(?<!=)(?<!!)=(?!=)', '===', expr)
        expr = expr.replace('#', '!==')

        # Phase 4: Logical operators
        expr = expr.replace('/\\', ' && ')
        expr = expr.replace('\\/', ' || ')

        # Phase 7: Built-in functions
        expr = re.sub(r'Len\((\w+)\)', r'\1.length', expr)
        expr = re.sub(r'Cardinality\((\w+)\)', r'\1.size', expr)
        expr = re.sub(r'DOMAIN\s+(\w+)', r'Object.keys(\1)', expr)

        # Phase 8: Tuple literals  <<a, b>> -> [a, b]
        expr = re.sub(r'<<(.+?)>>', r'[\1]', expr)

        # No record field access transformation needed — JS/TS uses dot access natively

        # Extract variable names referenced
        variables = re.findall(rf'{state_var}\.(\w+)', expr)

        # Validation: check for remaining TLA+ operators
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
        """Scan TypeScript source files for exported signatures."""
        # Search in src/ subdirectory and root
        candidates = list(source_dir.glob("src/**/*.ts"))
        candidates.extend(source_dir.glob("*.ts"))
        # Filter out test files and node_modules
        candidates = [
            f for f in candidates
            if "node_modules" not in str(f)
            and not f.name.endswith(".test.ts")
            and not f.name.endswith(".spec.ts")
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
                    if (stripped.startswith(("export function", "export class",
                                           "export interface", "export type",
                                           "export const", "export enum",
                                           "import "))
                        or stripped.startswith("@")):
                        lines.append(line)
            except OSError:
                lines.append(f"// Could not read {src_path}")
        return "\n".join(lines)

    def build_system_prompt(self) -> str:
        return (
            "You are a TypeScript test generation expert. You generate complete, runnable "
            "Jest/Vitest test files from formal specifications and API documentation. "
            "You use ONLY the real API imports provided -- never create mock classes "
            "or re-implement the API. Output ONLY TypeScript code, no markdown fencing "
            "or explanation."
        )

    def build_structural_patterns(self) -> str:
        return (
            "```typescript\n"
            "import { RegistryDag, Node, Edge, EdgeType } from './registry';\n\n"
            "// Pattern: fixture construction from trace Init state\n"
            "function makeDag(nodes: string[], edges: [string, string][]): RegistryDag {\n"
            "  const dag = new RegistryDag();\n"
            "  for (const nid of nodes) {\n"
            "    dag.addNode(Node.behavior(nid, nid, 'g', 'w', 't'));\n"
            "  }\n"
            "  for (const [src, dst] of edges) {\n"
            "    dag.addEdge(new Edge(src, dst, EdgeType.IMPORTS));\n"
            "  }\n"
            "  return dag;\n"
            "}\n\n"
            "describe('invariant verification', () => {\n"
            "  it('should maintain invariant', () => {\n"
            "    const dag = makeDag(['a', 'b'], [['a', 'b']]);\n"
            "    const result = dag.queryImpact('a');\n"
            "    expect(result).toBeDefined();\n"
            "    expect(result.length).toBeGreaterThan(0);\n"
            "  });\n\n"
            "  it('should throw on invalid input', () => {\n"
            "    const dag = makeDag([], []);\n"
            "    expect(() => dag.queryImpact('nonexistent')).toThrow();\n"
            "  });\n"
            "});\n"
            "```\n"
        )

    def build_import_instructions(self, module_name: str) -> str:
        return (
            f"- CRITICAL: Use EXACT import paths from the API Context section above.\n"
            f"  Use `import {{ RegistryDag }} from './registry'` for the main type\n"
            f"  Use `import type {{ Node, Edge, EdgeType }} from './types'` for type imports\n"
            f"- Use `import {{ describe, it, expect }} from '@jest/globals'` if needed\n"
        )

    def verify_test_file(
        self, test_path: Path, source_dir: Path,
        collect_timeout: int = 30, run_timeout: int = 120,
    ) -> VerifyResult:
        import subprocess

        # Stage 1: Type check
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", str(test_path)],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="compile",
                errors=[f"tsc failed (rc={result.returncode})"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 2: Test discovery
        result = subprocess.run(
            ["npx", "jest", "--listTests", str(test_path)],
            capture_output=True, text=True, cwd=str(source_dir), timeout=collect_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="collect",
                errors=["jest --listTests failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        # Stage 3: Run
        result = subprocess.run(
            ["npx", "jest", str(test_path), "--no-coverage"],
            capture_output=True, text=True, cwd=str(source_dir), timeout=run_timeout,
        )
        if result.returncode != 0:
            return VerifyResult(
                passed=False, stage="run",
                errors=["jest failed"],
                stdout=result.stdout, stderr=result.stderr,
            )

        return VerifyResult(passed=True, stage="run", stdout=result.stdout)

    def extract_code_from_response(self, response: str) -> str:
        return _extract_code_by_fence_tag(response, self.fence_language_tag)

    def test_file_name(self, gwt_id: str) -> str:
        safe_id = gwt_id.replace("-", "_")
        return f"{safe_id}.test.ts"
