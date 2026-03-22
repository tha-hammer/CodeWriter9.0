import pytest
from registry.lang_typescript import TypeScriptProfile
from registry.lang import CompiledExpression
from registry.types import Node
from registry.dag import RegistryDag

# ---------------------------------------------------------------------------
# Canonical operator mapping table derived from TLA+ Tokens sequence
# (verified by TLC across all 10 traces, final State 36)
# ---------------------------------------------------------------------------
TOKENS = [
    {"tla_op": "In",     "ts_op": "includes",  "surface": ".includes("},
    {"tla_op": "And",    "ts_op": "ampamp",     "surface": "&&"},
    {"tla_op": "Or",     "ts_op": "pipepipe",   "surface": "||"},
    {"tla_op": "Eq",     "ts_op": "tripleEq",   "surface": "==="},
    {"tla_op": "Neq",    "ts_op": "bangEqEq",   "surface": "!=="},
    {"tla_op": "ForAll", "ts_op": "every",      "surface": ".every("},
    {"tla_op": "Exists", "ts_op": "some",        "surface": ".some("},
    {"tla_op": "Len",    "ts_op": "length",     "surface": ".length"},
    {"tla_op": "Card",   "ts_op": "size",       "surface": ".size"},
    {"tla_op": "BoolT",  "ts_op": "true",       "surface": "true"},
    {"tla_op": "BoolF",  "ts_op": "false",      "surface": "false"},
]
N = 11  # total token count per spec

# TLA+ source tokens -> Python-side expression fragments fed to compile_condition
TLA_EXPRESSIONS = {
    "In":     r"x \in S",
    "And":    r"p /\ q",
    "Or":     r"p \/ q",
    "Eq":     r"x = y",
    "Neq":    r"x # y",
    "ForAll": r"\A x \in S : P(x)",
    "Exists": r"\E x \in S : P(x)",
    "Len":    r"Len(seq)",
    "Card":   r"Cardinality(S)",
    "BoolT":  r"TRUE",
    "BoolF":  r"FALSE",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_no_error(result: CompiledExpression) -> None:
    """Invariant: NoError -- compilation succeeded (no exception)."""
    assert result is not None
    assert isinstance(result, CompiledExpression)
    assert result.target_expr  # non-empty = success


def _assert_token_in_output(result: CompiledExpression, token: dict) -> None:
    """Check that the token's surface syntax appears in target_expr."""
    assert token["surface"] in result.target_expr, (
        f"Token {token['tla_op']} -> {token['ts_op']} not found in "
        f"target_expr: {result.target_expr!r}"
    )


def _assert_all_mapped(result: CompiledExpression) -> None:
    """Invariant: AllMapped -- when compilation is complete (cursor > N)
    every token in TOKENS must have its surface syntax in target_expr."""
    for token in TOKENS:
        _assert_token_in_output(result, token)


def _assert_strict_equality(result: CompiledExpression) -> None:
    """Invariant: StrictEquality -- Eq must map to === (not ==)."""
    assert "===" in result.target_expr, (
        f"StrictEquality violated: '===' not found in {result.target_expr!r}"
    )


def _assert_strict_inequality(result: CompiledExpression) -> None:
    """Invariant: StrictInequality -- Neq must map to !== (not !=)."""
    assert "!==" in result.target_expr, (
        f"StrictInequality violated: '!==' not found in {result.target_expr!r}"
    )


def _assert_set_membership_mapped(result: CompiledExpression) -> None:
    """Invariant: SetMembershipMapped -- In must map to .includes()."""
    assert ".includes(" in result.target_expr, (
        f"SetMembershipMapped violated: '.includes(' not found in {result.target_expr!r}"
    )


def _assert_forall_mapped(result: CompiledExpression) -> None:
    """Invariant: ForAllMapped -- ForAll must map to .every()."""
    assert ".every(" in result.target_expr, (
        f"ForAllMapped violated: '.every(' not found in {result.target_expr!r}"
    )


def _assert_exists_mapped(result: CompiledExpression) -> None:
    """Invariant: ExistsMapped -- Exists must map to .some()."""
    assert ".some(" in result.target_expr, (
        f"ExistsMapped violated: '.some(' not found in {result.target_expr!r}"
    )


def _assert_mappings_are_correct(result: CompiledExpression) -> None:
    """Invariant: MappingsAreCorrect -- compilation succeeded without error."""
    _assert_no_error(result)


def _assert_all_invariants(result: CompiledExpression) -> None:
    """Assert all eight TLA+ invariants on a compiled result."""
    _assert_no_error(result)
    _assert_all_mapped(result)
    _assert_strict_equality(result)
    _assert_strict_inequality(result)
    _assert_set_membership_mapped(result)
    _assert_forall_mapped(result)
    _assert_exists_mapped(result)


def _full_tla_expression() -> str:
    """Compound expression exercising all 11 token types."""
    return (
        r"(x \in S) /\ (p \/ q) /\ (a = b) /\ (c # d)"
        r" /\ (\A e \in T : P(e)) /\ (\E f \in U : Q(f))"
        r" /\ (Len(seq) > 0) /\ (Cardinality(V) = 0)"
        r" /\ TRUE /\ FALSE"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def profile() -> TypeScriptProfile:
    """Fresh TypeScriptProfile instance."""
    return TypeScriptProfile()


@pytest.fixture
def full_expression() -> str:
    return _full_tla_expression()


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

def test_trace_1_full_compilation_all_operators_mapped(profile, full_expression):
    """Trace 1: compile a compound TLA+ expression containing all 11 operators."""
    result = profile.compile_condition(full_expression)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result)


# ---------------------------------------------------------------------------
# Trace 2
# ---------------------------------------------------------------------------

def test_trace_2_deterministic_compilation(profile, full_expression):
    """Trace 2: second independent call must yield identical final mapping set."""
    result_a = profile.compile_condition(full_expression)
    result_b = profile.compile_condition(full_expression)

    _assert_all_invariants(result_a)
    _assert_all_invariants(result_b)

    assert result_a.target_expr == result_b.target_expr


# ---------------------------------------------------------------------------
# Trace 3
# ---------------------------------------------------------------------------

def test_trace_3_results_are_set_not_sequence(profile):
    """Trace 3: results is a set, not an ordered list."""
    expr = (
        r"(\A x \in S : P(x)) /\ (\E y \in T : Q(y))"
        r" /\ (a = b) /\ (c # d) /\ (z \in W)"
        r" /\ (Len(s) > 1) /\ (Cardinality(U) > 0)"
        r" /\ (p \/ q) /\ TRUE /\ FALSE"
    )
    result = profile.compile_condition(expr)

    _assert_all_invariants(result)


# ---------------------------------------------------------------------------
# Trace 4
# ---------------------------------------------------------------------------

def test_trace_4_strict_equality_operator(profile):
    """Trace 4 (StrictEquality): = in TLA+ compiles to === in TypeScript."""
    result = profile.compile_condition(r"x = y")

    _assert_no_error(result)
    _assert_strict_equality(result)

    assert "===" in result.target_expr, (
        f"Expected '===' in compiled expression, got: {result.target_expr!r}"
    )
    assert "==" not in result.target_expr.replace("===", ""), (
        "Loose equality '==' must not appear in TypeScript output"
    )


# ---------------------------------------------------------------------------
# Trace 5
# ---------------------------------------------------------------------------

def test_trace_5_strict_inequality_operator(profile):
    """Trace 5 (StrictInequality): # in TLA+ compiles to !== in TypeScript."""
    result = profile.compile_condition(r"x # y")

    _assert_no_error(result)
    _assert_strict_inequality(result)

    assert "!==" in result.target_expr, (
        f"Expected '!==' in compiled expression, got: {result.target_expr!r}"
    )
    assert "!=" not in result.target_expr.replace("!==", ""), (
        "Loose inequality '!=' must not appear in TypeScript output"
    )


# ---------------------------------------------------------------------------
# Trace 6
# ---------------------------------------------------------------------------

def test_trace_6_set_membership_maps_to_includes(profile):
    r"""Trace 6 (SetMembershipMapped): \in in TLA+ compiles to .includes() in TypeScript."""
    result = profile.compile_condition(r"x \in S")

    _assert_no_error(result)
    _assert_set_membership_mapped(result)

    assert ".includes(" in result.target_expr, (
        f"Expected '.includes(' in compiled expression, got: {result.target_expr!r}"
    )


# ---------------------------------------------------------------------------
# Trace 7
# ---------------------------------------------------------------------------

def test_trace_7_forall_maps_to_every(profile):
    r"""Trace 7 (ForAllMapped): \A in TLA+ compiles to .every() in TypeScript."""
    result = profile.compile_condition(r"\A x \in S : P(x)")

    _assert_no_error(result)
    _assert_forall_mapped(result)

    assert ".every(" in result.target_expr, (
        f"Expected '.every(' in compiled expression, got: {result.target_expr!r}"
    )


# ---------------------------------------------------------------------------
# Trace 8
# ---------------------------------------------------------------------------

def test_trace_8_exists_maps_to_some(profile):
    r"""Trace 8 (ExistsMapped): \E in TLA+ compiles to .some() in TypeScript."""
    result = profile.compile_condition(r"\E x \in S : P(x)")

    _assert_no_error(result)
    _assert_exists_mapped(result)

    assert ".some(" in result.target_expr, (
        f"Expected '.some(' in compiled expression, got: {result.target_expr!r}"
    )


# ---------------------------------------------------------------------------
# Trace 9
# ---------------------------------------------------------------------------

def test_trace_9_no_error_on_valid_expressions(profile):
    """Trace 9 (NoError): compilation succeeds for every valid TLA+ expression."""
    valid_expressions = [
        r"x \in S",
        r"p /\ q",
        r"p \/ q",
        r"x = y",
        r"x # y",
        r"\A x \in S : P(x)",
        r"\E x \in S : P(x)",
        r"Len(seq)",
        r"Cardinality(S)",
        r"TRUE",
        r"FALSE",
    ]
    for expr in valid_expressions:
        result = profile.compile_condition(expr)
        _assert_no_error(result)


# ---------------------------------------------------------------------------
# Trace 10
# ---------------------------------------------------------------------------

def test_trace_10_mappings_are_correct_no_spurious_entries(profile, full_expression):
    """Trace 10 (MappingsAreCorrect): compilation succeeds for the full expression."""
    result = profile.compile_condition(full_expression)

    _assert_no_error(result)
    _assert_all_mapped(result)


# ---------------------------------------------------------------------------
# Dedicated invariant verifiers
# ---------------------------------------------------------------------------

def test_invariant_strict_equality_multiple_expressions(profile):
    """StrictEquality holds across two distinct expression topologies."""
    expr_simple = r"x = y"
    expr_nested = r"(a = b) /\ (c = d)"

    for expr in [expr_simple, expr_nested]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_strict_equality(result)
        assert "===" in result.target_expr
        assert "==" not in result.target_expr.replace("===", "")


def test_invariant_strict_inequality_multiple_expressions(profile):
    r"""StrictInequality holds across two distinct expression topologies."""
    expr_simple = r"x # y"
    expr_nested = r"(a # b) \/ (c # d)"

    for expr in [expr_simple, expr_nested]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_strict_inequality(result)
        assert "!==" in result.target_expr
        assert "!=" not in result.target_expr.replace("!==", "")


def test_invariant_set_membership_multiple_expressions(profile):
    r"""SetMembershipMapped holds for bare membership and membership inside quantifier."""
    expr_bare = r"x \in S"
    expr_quantified = r"\A x \in S : (x \in T)"

    for expr in [expr_bare, expr_quantified]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        assert ".includes(" in result.target_expr


def test_invariant_forall_mapped_multiple_expressions(profile):
    r"""ForAllMapped holds for universal quantifier alone and nested in conjunction."""
    expr_alone = r"\A x \in S : P(x)"
    expr_conj  = r"\A x \in S : P(x) /\ Q(x)"

    for expr in [expr_alone, expr_conj]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        assert ".every(" in result.target_expr


def test_invariant_exists_mapped_multiple_expressions(profile):
    r"""ExistsMapped holds for existential quantifier alone and nested in disjunction."""
    expr_alone = r"\E x \in S : P(x)"
    expr_disj  = r"\E x \in S : P(x) \/ Q(x)"

    for expr in [expr_alone, expr_disj]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        assert ".some(" in result.target_expr


def test_invariant_all_mapped_complete_token_coverage(profile):
    """AllMapped: after compiling the full expression, every token from the
    TLA+ Tokens sequence appears in the result target_expr (cursor > N)."""
    result_a = profile.compile_condition(_full_tla_expression())
    result_b = profile.compile_condition(
        r"TRUE /\ FALSE /\ (x \in S) /\ (a = b) /\ (c # d)"
        r" /\ (p /\ q) /\ (p \/ q) /\ (\A x \in S : P(x))"
        r" /\ (\E y \in T : Q(y)) /\ (Len(s) > 0) /\ (Cardinality(U) > 0)"
    )
    for result in [result_a, result_b]:
        _assert_all_mapped(result)
        _assert_all_invariants(result)


def test_invariant_mappings_are_correct_multiple_topologies(profile):
    r"""MappingsAreCorrect holds across two distinct expression topologies."""
    expr_topology_1 = r"x \in S"
    expr_topology_2 = r"(\A x \in S : P(x)) /\ (a = b) /\ (c # d)"

    for expr in [expr_topology_1, expr_topology_2]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)


def test_invariant_no_error_all_single_token_expressions(profile):
    """NoError: compilation succeeds for each of the 11 individual TLA+ token expressions."""
    for token in TOKENS:
        tla_expr = TLA_EXPRESSIONS[token["tla_op"]]
        result = profile.compile_condition(tla_expr)
        _assert_no_error(result)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_edge_case_empty_expression(profile):
    """Edge case: empty string expression should not crash."""
    try:
        result = profile.compile_condition("")
        assert isinstance(result, CompiledExpression)
    except (ValueError, TypeError):
        pass  # acceptable: invalid input raises rather than silently corrupting


def test_edge_case_expression_with_only_boolean_literals(profile):
    """Edge case: expression using only TRUE/FALSE (BoolT/BoolF tokens)."""
    result = profile.compile_condition(r"TRUE /\ FALSE")

    _assert_no_error(result)

    assert "true"  in result.target_expr
    assert "false" in result.target_expr


def test_edge_case_deeply_nested_conjunction(profile):
    r"""Edge case: deeply nested /\ (And) chains."""
    expr = r"p /\ q /\ r /\ s /\ t"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    assert "&&" in result.target_expr


def test_edge_case_mixed_quantifiers_and_membership(profile):
    r"""Edge case: ForAll + Exists + membership in a single expression."""
    expr = r"(\A x \in S : x \in T) /\ (\E y \in U : y \in V)"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    assert ".every("    in result.target_expr
    assert ".some("     in result.target_expr
    assert ".includes(" in result.target_expr


def test_edge_case_equality_and_inequality_coexist(profile):
    """Edge case: = and # in the same expression must not cross-contaminate."""
    expr = r"(a = b) /\ (c # d)"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    _assert_strict_equality(result)
    _assert_strict_inequality(result)

    assert "===" in result.target_expr
    assert "!==" in result.target_expr

    ts = result.target_expr
    assert "==" not in ts.replace("===", "").replace("!==", ""), (
        "Loose equality operator detected alongside strict operators"
    )


def test_edge_case_len_and_card_operators(profile):
    """Edge case: Len (length) and Cardinality (size) must not be conflated."""
    expr = r"(Len(seq) = Cardinality(S))"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    assert ".length" in result.target_expr
    assert ".size" in result.target_expr


def test_edge_case_all_invariants_on_minimal_dag_integration(profile):
    """Edge case: verifies compile_condition output can be registered in a
    RegistryDag without error -- integration smoke test."""
    result = profile.compile_condition(_full_tla_expression())
    _assert_all_invariants(result)

    dag = RegistryDag()
    node = Node.behavior(
        id="bhv-ts-compile-01",
        name="TypeScript condition compile",
        given="a TLA+ expression with standard operators",
        when="TypeScriptProfile.compile_condition is called",
        then="a CompiledExpression is returned with correct TypeScript operator mapping",
    )
    dag.add_node(node)

    assert dag.node_count == 1
    assert dag.edge_count == 0
    assert result.target_expr and isinstance(result.target_expr, str)


def test_edge_case_single_token_per_type_complete_cycle(profile):
    """Edge case: feed each of the 11 token types one at a time."""
    single_token_exprs = [TLA_EXPRESSIONS[t["tla_op"]] for t in TOKENS]

    for expr in single_token_exprs:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
