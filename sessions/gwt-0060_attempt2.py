import pytest
from go_profile_condition_compile import GoProfile, CompiledExpression
from registry.types import Node
from registry.dag import RegistryDag


# ---------------------------------------------------------------------------
# Token table — direct transcription from the verified TLA+ spec
# ---------------------------------------------------------------------------

TOKENS = [
    {"tla_op": "In",     "go_op": "slicesContains", "go_expr_token": "slices.Contains", "needs_helper": False},
    {"tla_op": "And",    "go_op": "ampamp",          "go_expr_token": "&&",              "needs_helper": False},
    {"tla_op": "Or",     "go_op": "pipepipe",        "go_expr_token": "||",              "needs_helper": False},
    {"tla_op": "Eq",     "go_op": "doubleEq",        "go_expr_token": "==",              "needs_helper": False},
    {"tla_op": "Neq",    "go_op": "bangEq",          "go_expr_token": "!=",              "needs_helper": False},
    {"tla_op": "ForAll", "go_op": "allSatisfy",      "go_expr_token": "allSatisfy",      "needs_helper": True},
    {"tla_op": "Exists", "go_op": "anySatisfy",      "go_expr_token": "anySatisfy",      "needs_helper": True},
    {"tla_op": "Len",    "go_op": "len",             "go_expr_token": "len(",            "needs_helper": False},
    {"tla_op": "Card",   "go_op": "len",             "go_expr_token": "len(",            "needs_helper": False},
    {"tla_op": "BoolT",  "go_op": "true",            "go_expr_token": "true",            "needs_helper": False},
    {"tla_op": "BoolF",  "go_op": "false",           "go_expr_token": "false",           "needs_helper": False},
]

QUANTIFIER_GO_OPS = {"allSatisfy", "anySatisfy"}

EXPR_IN     = r"x \in S"
EXPR_AND    = r"A /\ B"
EXPR_OR     = r"A \/ B"
EXPR_EQ     = "x = y"
EXPR_NEQ    = "x /= y"
EXPR_FORALL = r"\A x \in S : P(x)"
EXPR_EXISTS = r"\E x \in S : P(x)"
EXPR_LEN    = "Len(s)"
EXPR_CARD   = "Cardinality(S)"
EXPR_BOOLT  = "TRUE"
EXPR_BOOLF  = "FALSE"

EXPR_FULL = (
    r"x \in S /\ A \/ B = C /= D"
    r" /\ (\A x \in S : P(x))"
    r" /\ (\E x \in S : Q(x))"
    r" /\ Len(s) = Cardinality(T)"
    r" /\ TRUE /\ FALSE"
)


# ---------------------------------------------------------------------------
# Invariant helpers
# ---------------------------------------------------------------------------

def _token_present(result: CompiledExpression, tok: dict) -> bool:
    return (
        tok["go_expr_token"] in result.go_expr
        or tok["go_op"] in result.go_expr
        or any(tok["go_op"] in hd or tok["go_expr_token"] in hd
               for hd in (result.helper_defs or []))
    )


def check_all_mapped(result: CompiledExpression, tokens: list) -> None:
    for tok in tokens:
        assert _token_present(result, tok), (
            f"AllMapped violated: tla_op={tok['tla_op']!r} "
            f"go_op={tok['go_op']!r} not found in compiled output"
        )


def check_helper_emitted(result: CompiledExpression) -> None:
    quantifier_in_output = any(
        op in result.go_expr
        or any(op in hd for hd in (result.helper_defs or []))
        for op in QUANTIFIER_GO_OPS
    )
    if quantifier_in_output:
        assert result.helper_defs, (
            "HelperEmitted violated: quantifier operator present "
            "but helper_defs is empty"
        )


def check_no_quantifier_no_helper(result: CompiledExpression) -> None:
    quantifier_in_output = any(
        op in result.go_expr
        or any(op in hd for hd in (result.helper_defs or []))
        for op in QUANTIFIER_GO_OPS
    )
    if not quantifier_in_output:
        assert not result.helper_defs, (
            "NoQuantifierNoHelper violated: no quantifier operator present "
            "but helper_defs is non-empty"
        )


def check_no_error(result: CompiledExpression) -> None:
    assert not getattr(result, "error", None), (
        f"NoError violated: error={getattr(result, 'error', None)!r}"
    )


def check_all_invariants(result: CompiledExpression, tokens: list) -> None:
    check_all_mapped(result, tokens)
    check_helper_emitted(result)
    check_no_quantifier_no_helper(result)
    check_no_error(result)


def assert_final_state_all_traces(result: CompiledExpression) -> None:
    check_no_error(result)
    check_all_mapped(result, TOKENS)
    assert result.helper_defs, (
        "HelperEmitted: ForAll and Exists in full expr => helper_defs must be non-empty"
    )
    assert any("allSatisfy" in hd for hd in result.helper_defs), (
        "HelperEmitted: allSatisfy helper def missing for ForAll"
    )
    assert any("anySatisfy" in hd for hd in result.helper_defs), (
        "HelperEmitted: anySatisfy helper def missing for Exists"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def profile() -> GoProfile:
    return GoProfile()


@pytest.fixture
def dag_full() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior(
        "gwt-compile-condition-full",
        "compile condition with all operators",
        given="a TLA+ expression with all 11 standard operators",
        when="GoProfile.compile_condition is called",
        then=(
            "a CompiledExpression is returned with a valid Go expression; "
            r"\in => slices.Contains, quantifiers emit helper_defs "
            "with allSatisfy/anySatisfy functions"
        ),
    ))
    return dag


@pytest.fixture
def dag_quantifier_only() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior(
        "gwt-compile-quantifier",
        "compile quantifier expression",
        given=r"a TLA+ expression with \A or \E",
        when="GoProfile.compile_condition is called",
        then="CompiledExpression has non-empty helper_defs",
    ))
    return dag


@pytest.fixture
def dag_no_quantifier() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior(
        "gwt-compile-no-quantifier",
        "compile non-quantifier expression",
        given=r"a TLA+ expression without \A or \E",
        when="GoProfile.compile_condition is called",
        then="CompiledExpression has empty helper_defs",
    ))
    return dag


# ---------------------------------------------------------------------------
# Trace tests
# ---------------------------------------------------------------------------

def test_trace_1_full_operator_set(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_2_full_operator_set_is_deterministic(profile):
    r1 = profile.compile_condition(EXPR_FULL)
    r2 = profile.compile_condition(EXPR_FULL)
    assert r1.go_expr == r2.go_expr, (
        "Determinism violated: go_expr differs between two compilations of EXPR_FULL"
    )
    assert r1.helper_defs == r2.helper_defs, (
        "Determinism violated: helper_defs differs between two compilations of EXPR_FULL"
    )
    assert_final_state_all_traces(r1)
    check_all_invariants(r1, TOKENS)


def test_trace_3_slices_contains_emitted_for_in(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert "slices.Contains" in result.go_expr or "slicesContains" in result.go_expr, (
        r"Trace 3: \in must compile to slices.Contains"
    )
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_4_logical_operators_emitted(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert "&&" in result.go_expr,  "Trace 4: And => &&"
    assert "||" in result.go_expr,  "Trace 4: Or  => ||"
    assert "==" in result.go_expr,  "Trace 4: Eq  => =="
    assert "!=" in result.go_expr,  "Trace 4: Neq => !="
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_5_helper_emitted_at_forall_token(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert any("allSatisfy" in hd for hd in result.helper_defs), (
        "Trace 5: ForAll (token 6) must emit allSatisfy helper def"
    )
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_6_helper_retained_after_exists_token(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert any("allSatisfy" in hd for hd in result.helper_defs)
    assert any("anySatisfy" in hd for hd in result.helper_defs)
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_7_len_appears_twice_for_len_and_card(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert result.go_expr.count("len(") >= 2, (
        "Trace 7: Len and Card both map to len() => must appear >=2 times"
    )
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_8_boolean_literals_emitted(profile):
    result = profile.compile_condition(EXPR_FULL)
    assert "true"  in result.go_expr, "Trace 8: BoolT => true"
    assert "false" in result.go_expr, "Trace 8: BoolF => false"
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_9_cursor_advances_to_12_at_finish(profile):
    result = profile.compile_condition(EXPR_FULL)
    check_all_mapped(result, TOKENS)
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


def test_trace_10_no_error_throughout(profile):
    result = profile.compile_condition(EXPR_FULL)
    check_no_error(result)
    assert_final_state_all_traces(result)
    check_all_invariants(result, TOKENS)


# ---------------------------------------------------------------------------
# AllMapped invariant
# ---------------------------------------------------------------------------

class TestAllMappedInvariant:

    def test_all_11_tokens_full_expression(self, profile):
        result = profile.compile_condition(EXPR_FULL)
        check_all_mapped(result, TOKENS)

    def test_in_only(self, profile):
        result = profile.compile_condition(EXPR_IN)
        check_all_mapped(result, [TOKENS[0]])

    def test_and_only(self, profile):
        result = profile.compile_condition(EXPR_AND)
        check_all_mapped(result, [TOKENS[1]])

    def test_or_only(self, profile):
        result = profile.compile_condition(EXPR_OR)
        check_all_mapped(result, [TOKENS[2]])

    def test_eq_only(self, profile):
        result = profile.compile_condition(EXPR_EQ)
        check_all_mapped(result, [TOKENS[3]])

    def test_neq_only(self, profile):
        result = profile.compile_condition(EXPR_NEQ)
        check_all_mapped(result, [TOKENS[4]])

    def test_forall_only(self, profile):
        result = profile.compile_condition(EXPR_FORALL)
        check_all_mapped(result, [TOKENS[5]])

    def test_exists_only(self, profile):
        result = profile.compile_condition(EXPR_EXISTS)
        check_all_mapped(result, [TOKENS[6]])

    def test_len_only(self, profile):
        result = profile.compile_condition(EXPR_LEN)
        check_all_mapped(result, [TOKENS[7]])

    def test_card_only(self, profile):
        result = profile.compile_condition(EXPR_CARD)
        check_all_mapped(result, [TOKENS[8]])

    def test_boolt_only(self, profile):
        result = profile.compile_condition(EXPR_BOOLT)
        check_all_mapped(result, [TOKENS[9]])

    def test_boolf_only(self, profile):
        result = profile.compile_condition(EXPR_BOOLF)
        check_all_mapped(result, [TOKENS[10]])

    @pytest.mark.parametrize("tla_expr,tok_idx", [
        (EXPR_IN,     0),
        (EXPR_AND,    1),
        (EXPR_OR,     2),
        (EXPR_EQ,     3),
        (EXPR_NEQ,    4),
        (EXPR_FORALL, 5),
        (EXPR_EXISTS, 6),
        (EXPR_LEN,    7),
        (EXPR_CARD,   8),
        (EXPR_BOOLT,  9),
        (EXPR_BOOLF,  10),
    ])
    def test_each_individual_token_mapped(self, profile, tla_expr, tok_idx):
        result = profile.compile_condition(tla_expr)
        check_all_mapped(result, [TOKENS[tok_idx]])
        check_no_error(result)


# ---------------------------------------------------------------------------
# HelperEmitted invariant
# ---------------------------------------------------------------------------

class TestHelperEmittedInvariant:

    def test_forall_emits_all_satisfy_helper(self, profile, dag_quantifier_only):
        result = profile.compile_condition(EXPR_FORALL)
        check_helper_emitted(result)
        assert result.helper_defs, "ForAll must emit helper"
        assert any("allSatisfy" in hd for hd in result.helper_defs)
        check_no_error(result)

    def test_exists_emits_any_satisfy_helper(self, profile, dag_quantifier_only):
        result = profile.compile_condition(EXPR_EXISTS)
        check_helper_emitted(result)
        assert result.helper_defs, "Exists must emit helper"
        assert any("anySatisfy" in hd for hd in result.helper_defs)
        check_no_error(result)

    def test_forall_and_exists_both_emit_helpers(self, profile):
        expr = r"(\A x \in S : P(x)) /\ (\E x \in S : Q(x))"
        result = profile.compile_condition(expr)
        check_helper_emitted(result)
        assert any("allSatisfy" in hd for hd in result.helper_defs)
        assert any("anySatisfy" in hd for hd in result.helper_defs)
        check_no_error(result)

    def test_full_expression_helper_emitted(self, profile):
        result = profile.compile_condition(EXPR_FULL)
        check_helper_emitted(result)
        assert result.helper_defs

    def test_non_quantifier_does_not_falsely_emit_helper(self, profile, dag_no_quantifier):
        result = profile.compile_condition(EXPR_IN)
        check_helper_emitted(result)
        check_no_quantifier_no_helper(result)
        check_no_error(result)

    def test_mixed_quantifier_and_non_quantifier(self, profile):
        expr = r"x \in S /\ (\A y \in T : P(y))"
        result = profile.compile_condition(expr)
        check_helper_emitted(result)
        assert result.helper_defs


# ---------------------------------------------------------------------------
# NoQuantifierNoHelper invariant
# ---------------------------------------------------------------------------

class TestNoQuantifierNoHelperInvariant:

    def test_in_only_no_helper(self, profile, dag_no_quantifier):
        result = profile.compile_condition(EXPR_IN)
        check_no_quantifier_no_helper(result)
        assert not result.helper_defs
        check_no_error(result)

    def test_logical_ops_no_helper(self, profile, dag_no_quantifier):
        expr = r"A /\ B \/ C = D /= E"
        result = profile.compile_condition(expr)
        check_no_quantifier_no_helper(result)
        assert not result.helper_defs
        check_no_error(result)

    def test_len_and_card_no_helper(self, profile, dag_no_quantifier):
        result = profile.compile_condition("Len(s) = Cardinality(T)")
        check_no_quantifier_no_helper(result)
        assert not result.helper_defs
        check_no_error(result)

    def test_boolean_literals_no_helper(self, profile, dag_no_quantifier):
        result = profile.compile_condition(r"TRUE /\ FALSE")
        check_no_quantifier_no_helper(result)
        assert not result.helper_defs
        check_no_error(result)

    def test_all_non_quantifier_tokens_no_helper(self, profile, dag_no_quantifier):
        expr = (
            r"x \in S /\ A \/ B = C /= D"
            r" /\ Len(s) = Cardinality(T)"
            r" /\ TRUE /\ FALSE"
        )
        result = profile.compile_condition(expr)
        check_no_quantifier_no_helper(result)
        assert not result.helper_defs
        check_no_error(result)

    def test_quantifier_overrides_no_helper_constraint(self, profile):
        result = profile.compile_condition(EXPR_FORALL)
        quantifier_present = any(
            op in result.go_expr
            or any(op in hd for hd in (result.helper_defs or []))
            for op in QUANTIFIER_GO_OPS
        )
        assert quantifier_present, (
            "EXPR_FORALL must produce allSatisfy in go_expr or helper_defs"
        )
        assert result.helper_defs, (
            "ForAll must emit helper_defs; NoQuantifierNoHelper does not apply here"
        )
        check_no_quantifier_no_helper(result)
        check_no_error(result)


# ---------------------------------------------------------------------------
# NoError invariant
# ---------------------------------------------------------------------------

class TestNoErrorInvariant:

    def test_no_error_in_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_IN))

    def test_no_error_and_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_AND))

    def test_no_error_or_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_OR))

    def test_no_error_eq_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_EQ))

    def test_no_error_neq_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_NEQ))

    def test_no_error_forall_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_FORALL))

    def test_no_error_exists_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_EXISTS))

    def test_no_error_len_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_LEN))

    def test_no_error_card_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_CARD))

    def test_no_error_boolt_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_BOOLT))

    def test_no_error_boolf_operator(self, profile):
        check_no_error(profile.compile_condition(EXPR_BOOLF))

    def test_no_error_full_expression(self, profile):
        check_no_error(profile.compile_condition(EXPR_FULL))


# ---------------------------------------------------------------------------
# Operator-mapping unit tests
# ---------------------------------------------------------------------------

class TestOperatorMappings:

    def test_in_maps_to_slices_contains(self, profile):
        result = profile.compile_condition(EXPR_IN)
        assert (
            "slices.Contains" in result.go_expr
            or "slicesContains" in result.go_expr
        ), r"\in must compile to slices.Contains"
        assert not result.helper_defs
        check_no_error(result)

    def test_and_maps_to_ampamp(self, profile):
        result = profile.compile_condition(EXPR_AND)
        assert "&&" in result.go_expr, r"/\ must compile to &&"
        assert not result.helper_defs
        check_no_error(result)

    def test_or_maps_to_pipepipe(self, profile):
        result = profile.compile_condition(EXPR_OR)
        assert "||" in result.go_expr, r"\/ must compile to ||"
        assert not result.helper_defs
        check_no_error(result)

    def test_eq_maps_to_double_eq(self, profile):
        result = profile.compile_condition(EXPR_EQ)
        assert "==" in result.go_expr, "= must compile to =="
        assert not result.helper_defs
        check_no_error(result)

    def test_neq_maps_to_bang_eq(self, profile):
        result = profile.compile_condition(EXPR_NEQ)
        assert "!=" in result.go_expr, "/= must compile to !="
        assert not result.helper_defs
        check_no_error(result)

    def test_forall_maps_to_all_satisfy_with_helper(self, profile):
        result = profile.compile_condition(EXPR_FORALL)
        assert (
            "allSatisfy" in result.go_expr
            or any("allSatisfy" in hd for hd in result.helper_defs)
        ), r"\A must compile to allSatisfy"
        assert result.helper_defs, r"\A must emit helper_defs"
        check_no_error(result)

    def test_exists_maps_to_any_satisfy_with_helper(self, profile):
        result = profile.compile_condition(EXPR_EXISTS)
        assert (
            "anySatisfy" in result.go_expr
            or any("anySatisfy" in hd for hd in result.helper_defs)
        ), r"\E must compile to anySatisfy"
        assert result.helper_defs, r"\E must emit helper_defs"
        check_no_error(result)

    def test_len_maps_to_len(self, profile):
        result = profile.compile_condition(EXPR_LEN)
        assert "len(" in result.go_expr, "Len must compile to len()"
        assert not result.helper_defs
        check_no_error(result)

    def test_card_maps_to_len(self, profile):
        result = profile.compile_condition(EXPR_CARD)
        assert "len(" in result.go_expr, "Cardinality must compile to len()"
        assert not result.helper_defs
        check_no_error(result)

    def test_boolt_maps_to_true(self, profile):
        result = profile.compile_condition(EXPR_BOOLT)
        assert "true" in result.go_expr, "TRUE must compile to true"
        assert not result.helper_defs
        check_no_error(result)

    def test_boolf_maps_to_false(self, profile):
        result = profile.compile_condition(EXPR_BOOLF)
        assert "false" in result.go_expr, "FALSE must compile to false"
        assert not result.helper_defs
        check_no_error(result)

    def test_card_and_len_share_go_op_len(self, profile):
        result = profile.compile_condition("Len(s) = Cardinality(T)")
        assert result.go_expr.count("len(") >= 2, (
            "Len and Cardinality must both emit len() in go_expr"
        )
        assert not result.helper_defs
        check_no_error(result)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_compile_condition_returns_compiled_expression_type(self, profile):
        result = profile.compile_condition(EXPR_FULL)
        assert isinstance(result, CompiledExpression)

    def test_compile_condition_full_is_deterministic(self, profile):
        r1 = profile.compile_condition(EXPR_FULL)
        r2 = profile.compile_condition(EXPR_FULL)
        assert r1.go_expr == r2.go_expr, (
            "Determinism violated: go_expr differs between compilations"
        )
        assert sorted(r1.helper_defs) == sorted(r2.helper_defs), (
            "Determinism violated: helper_defs content differs between compilations"
        )

    def test_single_in_isolated(self, profile):
        result = profile.compile_condition(EXPR_IN)
        assert "slices.Contains" in result.go_expr or "slicesContains" in result.go_expr
        assert not result.helper_defs
        check_all_invariants(result, [TOKENS[0]])

    def test_single_forall_isolated(self, profile):
        result = profile.compile_condition(EXPR_FORALL)
        assert result.helper_defs
        assert any("allSatisfy" in hd for hd in result.helper_defs)
        check_all_invariants(result, [TOKENS[5]])

    def test_single_exists_isolated(self, profile):
        result = profile.compile_condition(EXPR_EXISTS)
        assert result.helper_defs
        assert any("anySatisfy" in hd for hd in result.helper_defs)
        check_all_invariants(result, [TOKENS[6]])

    def test_quantifier_followed_by_non_quantifier_helper_preserved(self, profile):
        expr = r"(\A x \in S : P(x)) /\ Len(s) = TRUE"
        result = profile.compile_condition(expr)
        assert result.helper_defs, (
            "helper_defs must remain non-empty after non-quantifier tokens "
            "follow a quantifier"
        )
        check_helper_emitted(result)
        check_no_error(result)

    def test_non_quantifier_tokens_never_set_helper(self, profile):
        expr = (
            r"x \in S /\ A \/ B = C /= D"
            r" /\ Len(s) = Cardinality(T) /\ TRUE /\ FALSE"
        )
        result = profile.compile_condition(expr)
        assert not result.helper_defs, (
            "NoQuantifierNoHelper: 9 non-quantifier tokens must not emit helper_defs"
        )
        check_no_quantifier_no_helper(result)
        check_no_error(result)

    def test_all_invariants_on_full_expression_one_shot(self, profile, dag_full):
        result = profile.compile_condition(EXPR_FULL)
        check_all_invariants(result, TOKENS)
        assert isinstance(result, CompiledExpression)
        assert dag_full.node_count >= 1

    def test_helper_defs_are_valid_go_functions(self, profile):
        result = profile.compile_condition(EXPR_FORALL)
        assert result.helper_defs
        for hd in result.helper_defs:
            assert "func" in hd or "allSatisfy" in hd or "anySatisfy" in hd, (
                f"helper_def does not appear to be a Go function: {hd!r}"
            )

    def test_go_expr_is_non_empty_string(self, profile):
        for expr in [EXPR_IN, EXPR_FORALL, EXPR_BOOLT, EXPR_FULL]:
            result = profile.compile_condition(expr)
            assert isinstance(result.go_expr, str), "go_expr must be a str"
            assert result.go_expr.strip(), f"go_expr must be non-empty for expr={expr!r}"

    def test_helper_defs_is_list(self, profile):
        for expr in [EXPR_IN, EXPR_FORALL, EXPR_FULL]:
            result = profile.compile_condition(expr)
            assert isinstance(result.helper_defs, list), (
                f"helper_defs must be a list; got {type(result.helper_defs)} "
                f"for expr={expr!r}"
            )

    @pytest.mark.parametrize("expr,desc", [
        (EXPR_IN,    "In only"),
        (EXPR_AND,   "And only"),
        (EXPR_BOOLT, "BoolT only"),
        (EXPR_FULL,  "all 11 tokens"),
    ])
    def test_no_error_parametrized(self, profile, expr, desc):
        result = profile.compile_condition(expr)
        check_no_error(result)