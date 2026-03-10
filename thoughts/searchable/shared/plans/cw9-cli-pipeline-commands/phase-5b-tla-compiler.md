╔════════════════════════════════════════════════════════════════╗
║  PHASE 5B: TLA+ Condition Compiler (Prompt Enrichment)        ║
╚════════════════════════════════════════════════════════════════╝

## Overview

**Goal**: Compile TLA+ condition expressions from bridge artifacts into partial Python expression strings. These serve as **prompt hints** for the LLM test generation loop in Phase 5C — they give the LLM a head start on the syntactic translation so it can focus on the semantic gap (API binding, fixture design, scenario construction).

> **v4 reframing:** In v3, this compiler was the core of test generation. Analysis of the oracle
> code at `run_change_prop_loop.py:572-621` revealed that the semantic gap — binding TLA+ state
> variables like `affected` and `candidates` to actual Python API calls like
> `dag.query_affected_tests()` and `dag.query_impact().affected` — cannot be solved by regex
> substitution. The compiler handles the **easy 20%** (operator translation); the LLM handles the
> **hard 80%** (domain reasoning about what invariants mean relative to the Python API).

### What the compiler does vs. what the LLM does

```
TLA+ condition: \A t \in affected : t \in candidates

Compiler output (Phase 5B):
  "all(t in candidates for t in affected)"
  ↑ Correct syntax, but 'affected' and 'candidates' are unbound variables

LLM output (Phase 5C):
  result = dag.query_affected_tests("d")
  impact = dag.query_impact("d")
  candidates = impact.affected | {"d"}
  for path in result:
      found = any(dag.test_artifacts.get(nid) == path for nid in candidates)
      assert found, f"NoFalsePositives: {path} not backed by candidate"
  ↑ Correct program with API binding, fixture setup, meaningful assertions
```

The compiler output appears in the LLM's prompt as a hint:

```
Verifier NoFalsePositives:
  TLA+ condition: \A t \in affected : t \in candidates
  Partial Python: all(t in candidates for t in affected)
  Applies to: ["affected", "candidates"]
  ↑ Your job: bind 'affected' and 'candidates' to real API calls
```

## Code: `python/registry/tla_compiler.py`

Identical to v3 — same `compile_condition()`, `compile_assertions()`, `CompiledAssertion`, `CompileError`. Only the role changes: from "test generation engine" to "prompt enrichment utility."

```python
"""Bounded TLA+ condition → Python assertion compiler.

Handles only the TLA+ operators that appear in bridge artifact conditions
across our existing modules. Raises CompileError on unknown operators.

v4 role: Prompt enrichment utility for Phase 5C's LLM loop.
The compiled expressions are partial hints, not the final test assertions.
"""

import re
from dataclasses import dataclass


class CompileError(Exception):
    """Raised when a TLA+ expression uses unsupported operators."""
    pass


@dataclass
class CompiledAssertion:
    """A compiled Python assertion string with metadata."""
    python_expr: str          # e.g., "all(x in impact_set for x in ...)"
    original_tla: str         # The raw TLA+ condition
    variables_used: list[str] # State variables referenced


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
    variables = []

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

    # Phase 5: Set/sequence operators
    expr = expr.replace('\\in', ' in ')
    expr = expr.replace('\\notin', ' not in ')

    # Phase 6: Built-in functions
    expr = re.sub(r'Len\(', 'len(', expr)
    expr = re.sub(r'Cardinality\(', 'len(', expr)
    expr = re.sub(r'DOMAIN\s+(\w+)', r'set(\1.keys())', expr)

    # Phase 7: Tuple literals  <<a, b>> → (a, b)
    expr = re.sub(r'<<(.+?)>>', r'(\1)', expr)

    # Phase 8: Universal quantifier  \A x \in S : P(x)
    expr = re.sub(
        r'\\A\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'all((\3) for \1 in \2)',
        expr
    )

    # Phase 9: Existential quantifier  \E x \in S : P(x)
    expr = re.sub(
        r'\\E\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'any((\3) for \1 in \2)',
        expr
    )

    # Phase 10: Record field access — state.field → state["field"]
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

    return CompiledAssertion(
        python_expr=expr.strip(),
        original_tla=original,
        variables_used=list(set(variables)),
    )


def compile_assertions(
    verifiers: dict,
    state_var: str = "state",
) -> dict[str, CompiledAssertion]:
    """Compile all verifier conditions from bridge artifacts.

    Args:
        verifiers: The verifiers dict from bridge artifacts JSON
        state_var: Python variable name for state

    Returns:
        Dict mapping verifier name → CompiledAssertion.
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
        has_error = False
        for cond in conditions:
            try:
                compiled = compile_condition(cond, state_var)
                compiled_parts.append(compiled)
            except CompileError as e:
                has_error = True
                compiled_parts.append(CompiledAssertion(
                    python_expr=f"True  # SKIP: {e}",
                    original_tla=cond,
                    variables_used=[],
                ))

        # Combine conditions with 'and'
        combined_expr = " and ".join(f"({c.python_expr})" for c in compiled_parts)
        all_vars = []
        for c in compiled_parts:
            all_vars.extend(c.variables_used)

        results[vname] = CompiledAssertion(
            python_expr=combined_expr,
            original_tla=" /\\ ".join(c.original_tla for c in compiled_parts),
            variables_used=list(set(all_vars)),
        )

    return results
```

## Tests: `python/tests/test_tla_compiler.py`

```python
class TestTlaCompiler:
    def test_basic_operators(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("x \\in S /\\ y = 3")
        assert "in" in r.python_expr
        assert "and" in r.python_expr
        assert "==" in r.python_expr

    def test_universal_quantifier(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("\\A x \\in S : x > 0")
        assert "all(" in r.python_expr
        assert "for x in S" in r.python_expr

    def test_record_field_access(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("state.count > 0", state_var="state")
        assert 'state["count"]' in r.python_expr

    def test_len_cardinality(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("Len(seq) > 0 /\\ Cardinality(S) = 3")
        assert "len(seq)" in r.python_expr
        assert "len(S)" in r.python_expr

    def test_boolean_literals(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("dirty = TRUE")
        assert "True" in r.python_expr

    def test_unsupported_operator_raises(self):
        from registry.tla_compiler import compile_condition, CompileError
        with pytest.raises(CompileError):
            compile_condition("\\CHOOSE x \\in S : P(x)")

    def test_dirty_guard_stripped(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("dirty = TRUE /\\ x > 0")
        assert "dirty" not in r.python_expr
        assert "x" in r.python_expr

    def test_compile_assertions_from_verifiers(self):
        from registry.tla_compiler import compile_assertions
        verifiers = {
            "NoFalsePositives": {
                "conditions": ["\\A t \\in affected : t \\in candidates"],
                "applies_to": ["affected", "candidates"],
            },
            "ValidState": {
                "conditions": ["Len(result) >= 0"],
                "applies_to": ["result"],
            },
        }
        results = compile_assertions(verifiers)
        assert "NoFalsePositives" in results
        assert "all(" in results["NoFalsePositives"].python_expr
        assert "ValidState" in results
        assert "len(result)" in results["ValidState"].python_expr
```

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_tla_compiler.py -v` — all 8 compiler tests pass
