import pytest
from typescript_profile_condition_compile import TypeScriptProfile, CompiledExpression
from registry.types import Node
from registry.dag import RegistryDag

# ---------------------------------------------------------------------------
# Canonical operator mapping table derived from TLA+ Tokens sequence
# (verified by TLC across all 10 traces, final State 36)
# ---------------------------------------------------------------------------
TOKENS = [
    {"tla_op": "In",     "ts_op": "includes"},
    {"tla_op": "And",    "ts_op": "ampamp"},
    {"tla_op": "Or",     "ts_op": "pipepipe"},
    {"tla_op": "Eq",     "ts_op": "tripleEq"},
    {"tla_op": "Neq",    "ts_op": "bangEqEq"},
    {"tla_op": "ForAll", "ts_op": "every"},
    {"tla_op": "Exists", "ts_op": "some"},
    {"tla_op": "Len",    "ts_op": "length"},
    {"tla_op": "Card",   "ts_op": "size"},
    {"tla_op": "BoolT",  "ts_op": "true"},
    {"tla_op": "BoolF",  "ts_op": "false"},
]
N = 11  # total token count per spec

# Symbolic ts_op names -> real TypeScript surface syntax
TS_OP_SURFACE = {
    "includes":  ".includes(",
    "ampamp":    "&&",
    "pipepipe":  "||",
    "tripleEq":  "===",
    "bangEqEq":  "!==",
    "every":     ".every(",
    "some":      ".some(",
    "length":    ".length",
    "size":      ".size",
    "true":      "true",
    "false":     "false",
}

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
    """Invariant: NoError -- has_error must be False."""
    assert result.has_error is False, (
        f"NoError invariant violated: has_error={result.has_error}"
    )


def _assert_mappings_are_correct(result: CompiledExpression) -> None:
    """Invariant: MappingsAreCorrect -- every mapping in results corresponds
    to an entry in TOKENS."""
    known = {(t["tla_op"], t["ts_op"]) for t in TOKENS}
    for mapping in result.mappings:
        pair = (mapping["tla_op"], mapping["ts_op"])
        assert pair in known, (
            f"MappingsAreCorrect violated: unexpected mapping {pair}"
        )


def _assert_all_mapped(result: CompiledExpression) -> None:
    """Invariant: AllMapped -- when compilation is complete (cursor > N)
    every token in TOKENS must appear in results with BOTH its tla_op AND
    its correct ts_op."""
    mapped_pairs = {(m["tla_op"], m["ts_op"]) for m in result.mappings}
    for token in TOKENS:
        expected_pair = (token["tla_op"], token["ts_op"])
        assert expected_pair in mapped_pairs, (
            f"AllMapped violated: token '{token['tla_op']}' -> '{token['ts_op']}' "
            f"missing from results (found tla_op mappings: "
            f"{[m['tla_op'] for m in result.mappings]})"
        )


def _assert_strict_equality(result: CompiledExpression) -> None:
    """Invariant: StrictEquality -- Eq must map to tripleEq (===)."""
    for m in result.mappings:
        if m["tla_op"] == "Eq":
            assert m["ts_op"] == "tripleEq", (
                f"StrictEquality violated: Eq mapped to '{m['ts_op']}', expected 'tripleEq'"
            )


def _assert_strict_inequality(result: CompiledExpression) -> None:
    """Invariant: StrictInequality -- Neq must map to bangEqEq (!==)."""
    for m in result.mappings:
        if m["tla_op"] == "Neq":
            assert m["ts_op"] == "bangEqEq", (
                f"StrictInequality violated: Neq mapped to '{m['ts_op']}', expected 'bangEqEq'"
            )


def _assert_set_membership_mapped(result: CompiledExpression) -> None:
    """Invariant: SetMembershipMapped -- In must map to includes."""
    for m in result.mappings:
        if m["tla_op"] == "In":
            assert m["ts_op"] == "includes", (
                f"SetMembershipMapped violated: In mapped to '{m['ts_op']}', expected 'includes'"
            )


def _assert_forall_mapped(result: CompiledExpression) -> None:
    """Invariant: ForAllMapped -- ForAll must map to every."""
    for m in result.mappings:
        if m["tla_op"] == "ForAll":
            assert m["ts_op"] == "every", (
                f"ForAllMapped violated: ForAll mapped to '{m['ts_op']}', expected 'every'"
            )


def _assert_exists_mapped(result: CompiledExpression) -> None:
    """Invariant: ExistsMapped -- Exists must map to some."""
    for m in result.mappings:
        if m["tla_op"] == "Exists":
            assert m["ts_op"] == "some", (
                f"ExistsMapped violated: Exists mapped to '{m['ts_op']}', expected 'some'"
            )


def _assert_all_invariants(result: CompiledExpression) -> None:
    """Assert all eight TLA+ invariants on a compiled result."""
    _assert_no_error(result)
    _assert_mappings_are_correct(result)
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
    assert len(result.mappings) == N


# ---------------------------------------------------------------------------
# Trace 2
# ---------------------------------------------------------------------------

def test_trace_2_deterministic_compilation(profile, full_expression):
    """Trace 2: second independent call must yield identical final mapping set."""
    result_a = profile.compile_condition(full_expression)
    result_b = profile.compile_condition(full_expression)

    _assert_all_invariants(result_a)
    _assert_all_invariants(result_b)

    mappings_a = frozenset((m["tla_op"], m["ts_op"]) for m in result_a.mappings)
    mappings_b = frozenset((m["tla_op"], m["ts_op"]) for m in result_b.mappings)
    assert mappings_a == mappings_b


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

    mapped_ops = [m["tla_op"] for m in result.mappings]
    for token in TOKENS:
        assert token["tla_op"] in mapped_ops


# ---------------------------------------------------------------------------
# Trace 4
# ---------------------------------------------------------------------------

def test_trace_4_strict_equality_operator(profile):
    """Trace 4 (StrictEquality): = in TLA+ compiles to === in TypeScript."""
    result = profile.compile_condition(r"x = y")

    _assert_no_error(result)
    _assert_strict_equality(result)

    assert "===" in result.expression, (
        f"Expected '===' in compiled expression, got: {result.expression!r}"
    )
    assert "==" not in result.expression.replace("===", ""), (
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

    assert "!==" in result.expression, (
        f"Expected '!==' in compiled expression, got: {result.expression!r}"
    )
    assert "!=" not in result.expression.replace("!==", ""), (
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

    assert ".includes(" in result.expression, (
        f"Expected '.includes(' in compiled expression, got: {result.expression!r}"
    )


# ---------------------------------------------------------------------------
# Trace 7
# ---------------------------------------------------------------------------

def test_trace_7_forall_maps_to_every(profile):
    r"""Trace 7 (ForAllMapped): \A in TLA+ compiles to .every() in TypeScript."""
    result = profile.compile_condition(r"\A x \in S : P(x)")

    _assert_no_error(result)
    _assert_forall_mapped(result)

    assert ".every(" in result.expression, (
        f"Expected '.every(' in compiled expression, got: {result.expression!r}"
    )


# ---------------------------------------------------------------------------
# Trace 8
# ---------------------------------------------------------------------------

def test_trace_8_exists_maps_to_some(profile):
    r"""Trace 8 (ExistsMapped): \E in TLA+ compiles to .some() in TypeScript."""
    result = profile.compile_condition(r"\E x \in S : P(x)")

    _assert_no_error(result)
    _assert_exists_mapped(result)

    assert ".some(" in result.expression, (
        f"Expected '.some(' in compiled expression, got: {result.expression!r}"
    )


# ---------------------------------------------------------------------------
# Trace 9
# ---------------------------------------------------------------------------

def test_trace_9_no_error_on_valid_expressions(profile):
    """Trace 9 (NoError): has_error stays FALSE for every valid TLA+ expression."""
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
        _assert_mappings_are_correct(result)


# ---------------------------------------------------------------------------
# Trace 10
# ---------------------------------------------------------------------------

def test_trace_10_mappings_are_correct_no_spurious_entries(profile, full_expression):
    """Trace 10 (MappingsAreCorrect): every entry in results must correspond
    to a known (tla_op, ts_op) pair from the canonical TOKENS table."""
    result = profile.compile_condition(full_expression)

    _assert_no_error(result)
    _assert_mappings_are_correct(result)

    known_ts_ops = {t["ts_op"] for t in TOKENS}
    for m in result.mappings:
        assert m["ts_op"] in known_ts_ops, (
            f"Spurious ts_op '{m['ts_op']}' not in canonical mapping table"
        )


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
        assert "===" in result.expression
        assert "==" not in result.expression.replace("===", "")


def test_invariant_strict_inequality_multiple_expressions(profile):
    r"""StrictInequality holds across two distinct expression topologies."""
    expr_simple = r"x # y"
    expr_nested = r"(a # b) \/ (c # d)"

    for expr in [expr_simple, expr_nested]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_strict_inequality(result)
        assert "!==" in result.expression
        assert "!=" not in result.expression.replace("!==", "")


def test_invariant_set_membership_multiple_expressions(profile):
    r"""SetMembershipMapped holds for bare membership and membership inside quantifier."""
    expr_bare = r"x \in S"
    expr_quantified = r"\A x \in S : (x \in T)"

    for expr in [expr_bare, expr_quantified]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_set_membership_mapped(result)
        assert ".includes(" in result.expression


def test_invariant_forall_mapped_multiple_expressions(profile):
    r"""ForAllMapped holds for universal quantifier alone and nested in conjunction."""
    expr_alone = r"\A x \in S : P(x)"
    expr_conj  = r"(\A x \in S : P(x)) /\ (\A y \in T : Q(y))"

    for expr in [expr_alone, expr_conj]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_forall_mapped(result)
        assert ".every(" in result.expression


def test_invariant_exists_mapped_multiple_expressions(profile):
    r"""ExistsMapped holds for existential quantifier alone and nested in disjunction."""
    expr_alone = r"\E x \in S : P(x)"
    expr_disj  = r"(\E x \in S : P(x)) \/ (\E y \in T : Q(y))"

    for expr in [expr_alone, expr_disj]:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_exists_mapped(result)
        assert ".some(" in result.expression


def test_invariant_all_mapped_complete_token_coverage(profile):
    """AllMapped: after compiling the full expression, every token from the
    TLA+ Tokens sequence appears in the result mappings (cursor > N)."""
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
        _assert_mappings_are_correct(result)


def test_invariant_no_error_all_single_token_expressions(profile):
    """NoError: has_error=FALSE for each of the 11 individual TLA+ token expressions."""
    for token in TOKENS:
        tla_expr = TLA_EXPRESSIONS[token["tla_op"]]
        result = profile.compile_condition(tla_expr)
        _assert_no_error(result)
        _assert_mappings_are_correct(result)


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
    _assert_mappings_are_correct(result)

    for m in result.mappings:
        if m["tla_op"] == "BoolT":
            assert m["ts_op"] == "true"
        if m["tla_op"] == "BoolF":
            assert m["ts_op"] == "false"

    assert "true"  in result.expression
    assert "false" in result.expression


def test_edge_case_deeply_nested_conjunction(profile):
    r"""Edge case: deeply nested /\ (And) chains."""
    expr = r"p /\ q /\ r /\ s /\ t"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    _assert_mappings_are_correct(result)

    for m in result.mappings:
        if m["tla_op"] == "And":
            assert m["ts_op"] == "ampamp"

    assert "&&" in result.expression


def test_edge_case_mixed_quantifiers_and_membership(profile):
    r"""Edge case: ForAll + Exists + membership in a single expression."""
    expr = r"(\A x \in S : x \in T) /\ (\E y \in U : y \in V)"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    _assert_set_membership_mapped(result)
    _assert_forall_mapped(result)
    _assert_exists_mapped(result)
    _assert_mappings_are_correct(result)

    assert ".every("    in result.expression
    assert ".some("     in result.expression
    assert ".includes(" in result.expression


def test_edge_case_equality_and_inequality_coexist(profile):
    """Edge case: = and # in the same expression must not cross-contaminate."""
    expr = r"(a = b) /\ (c # d)"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    _assert_strict_equality(result)
    _assert_strict_inequality(result)

    assert "===" in result.expression
    assert "!==" in result.expression

    ts = result.expression
    assert "==" not in ts.replace("===", "").replace("!==", ""), (
        "Loose equality operator detected alongside strict operators"
    )


def test_edge_case_len_and_card_operators(profile):
    """Edge case: Len (length) and Cardinality (size) must not be conflated."""
    expr = r"(Len(seq) = Cardinality(S))"
    result = profile.compile_condition(expr)

    _assert_no_error(result)
    _assert_mappings_are_correct(result)

    ts_ops = {m["ts_op"] for m in result.mappings}

    if "Len" in {m["tla_op"] for m in result.mappings}:
        assert "length" in ts_ops, "Len must map to 'length'"

    if "Card" in {m["tla_op"] for m in result.mappings}:
        assert "size" in ts_ops, "Cardinality must map to 'size'"

    for m in result.mappings:
        if m["tla_op"] == "Len":
            assert m["ts_op"] == "length", f"Len mapped to {m['ts_op']!r}, expected 'length'"
        if m["tla_op"] == "Card":
            assert m["ts_op"] == "size", f"Card mapped to {m['ts_op']!r}, expected 'size'"


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
    assert result.expression and isinstance(result.expression, str)


def test_edge_case_single_token_per_type_complete_cycle(profile):
    """Edge case: feed each of the 11 token types one at a time."""
    single_token_exprs = [TLA_EXPRESSIONS[t["tla_op"]] for t in TOKENS]

    for expr in single_token_exprs:
        result = profile.compile_condition(expr)
        _assert_no_error(result)
        _assert_mappings_are_correct(result)
        _assert_strict_equality(result)
        _assert_strict_inequality(result)
        _assert_set_membership_mapped(result)
        _assert_forall_mapped(result)
        _assert_exists_mapped(result)