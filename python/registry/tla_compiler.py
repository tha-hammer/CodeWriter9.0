"""Bounded TLA+ condition → Python assertion compiler.

Handles only the TLA+ operators that appear in bridge artifact conditions
across our existing modules. Raises CompileError on unknown operators.

v4 role: Prompt enrichment utility for Phase 5C's LLM loop.
The compiled expressions are partial hints, not the final test assertions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from registry.lang import CompileError, CompiledExpression


# Backwards-compatible aliases
CompiledAssertion = CompiledExpression


def compile_condition(tla_expr: str, state_var: str = "state") -> CompiledAssertion:
    """Compile a TLA+ condition expression to a Python assertion string.

    Args:
        tla_expr: The TLA+ condition (from bridge artifacts verifiers.conditions)
        state_var: The Python variable name for the state dict (default: "state")

    Returns:
        CompiledAssertion with executable Python expression

    Raises:
        CompileError: If the expression uses unsupported TLA+ operators
    """
    original = tla_expr
    expr = tla_expr.strip()

    # Phase 1: Strip dirty guard (common in two-phase action models)
    expr = re.sub(r'dirty\s*=\s*TRUE\s*[/\\]+\s*', '', expr)

    # Phase 2: Boolean literals
    expr = expr.replace('TRUE', 'True').replace('FALSE', 'False')

    # Phase 3: Equality/inequality
    expr = re.sub(r'(?<!=)(?<!!)=(?!=)', '==', expr)  # = → == (avoid ==, !=)
    expr = expr.replace('#', '!=')  # TLA+ inequality

    # Phase 4: Logical operators
    expr = expr.replace('/\\', ' and ')
    expr = expr.replace('\\/', ' or ')
    # => (implication) — a => b ≡ (not a) or b
    expr = re.sub(r'(\S+)\s*=>\s*(\S+)', r'(not (\1) or (\2))', expr)

    # Phase 5: Quantifiers (MUST run before \\in replacement)
    # Universal quantifier  \A x \in S : P(x)
    expr = re.sub(
        r'\\A\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'all((\3) for \1 in \2)',
        expr
    )
    # Existential quantifier  \E x \in S : P(x)
    expr = re.sub(
        r'\\E\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'any((\3) for \1 in \2)',
        expr
    )

    # Phase 6: Set/sequence operators
    expr = expr.replace('\\in', ' in ')
    expr = expr.replace('\\notin', ' not in ')

    # Phase 7: Built-in functions
    expr = re.sub(r'Len\(', 'len(', expr)
    expr = re.sub(r'Cardinality\(', 'len(', expr)
    expr = re.sub(r'DOMAIN\s+(\w+)', r'set(\1.keys())', expr)

    # Phase 8: Tuple literals  <<a, b>> → (a, b)
    expr = re.sub(r'<<(.+?)>>', r'(\1)', expr)

    # Phase 9: Record field access — state.field → state["field"]
    expr = re.sub(
        rf'{state_var}\.(\w+)',
        rf'{state_var}["\1"]',
        expr
    )

    # Extract variable names referenced
    variables = re.findall(rf'{state_var}\["(\w+)"\]', expr)

    # Validation: check for remaining TLA+ operators we don't handle
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
    verifiers: dict,
    state_var: str = "state",
) -> dict[str, CompiledExpression]:
    """Compile all verifier conditions from bridge artifacts.

    Args:
        verifiers: The verifiers dict from bridge artifacts JSON
        state_var: Python variable name for state

    Returns:
        Dict mapping verifier name → CompiledExpression.
        Verifiers with no conditions or with CompileError are skipped
        with a warning comment in the assertion.
    """
    results = {}
    for vname, vdata in verifiers.items():
        if not isinstance(vdata, dict):
            continue
        conditions = vdata.get("conditions", [])
        if not conditions:
            continue

        compiled_parts = []
        for cond in conditions:
            try:
                compiled = compile_condition(cond, state_var)
                compiled_parts.append(compiled)
            except CompileError as e:
                compiled_parts.append(CompiledExpression(
                    target_expr=f"True  # SKIP: {e}",
                    original_tla=cond,
                    variables_used=[],
                ))

        # Combine conditions with 'and'
        combined_expr = " and ".join(f"({c.target_expr})" for c in compiled_parts)
        all_vars: list[str] = []
        for c in compiled_parts:
            all_vars.extend(c.variables_used)

        results[vname] = CompiledExpression(
            target_expr=combined_expr,
            original_tla=" /\\ ".join(c.original_tla for c in compiled_parts),
            variables_used=list(set(all_vars)),
        )

    return results
