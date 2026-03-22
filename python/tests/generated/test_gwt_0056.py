from __future__ import annotations

import pytest
from registry.lang import PythonProfile, CompiledExpression
from registry.types import Edge, EdgeType, Node
from registry.dag import RegistryDag


# ─── TLA+ Tokens sequence (N = 11), mirrors the verified TLA+ spec exactly ──

TOKENS = [
    {"tla_op": "In",     "py_op": "in"},
    {"tla_op": "And",    "py_op": "and"},
    {"tla_op": "Or",     "py_op": "or"},
    {"tla_op": "Eq",     "py_op": "=="},
    {"tla_op": "Neq",    "py_op": "!="},
    {"tla_op": "ForAll", "py_op": "all"},
    {"tla_op": "Exists", "py_op": "any"},
    {"tla_op": "Len",    "py_op": "len"},
    {"tla_op": "Card",   "py_op": "len"},
    {"tla_op": "BoolT",  "py_op": "True"},
    {"tla_op": "BoolF",  "py_op": "False"},
]
N = 11  # cardinality of Tokens in the spec


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_dag() -> RegistryDag:
    """Minimal RegistryDag matching Init state: no prior nodes/edges."""
    return RegistryDag()


def _make_profile(dag: Optional[RegistryDag] = None) -> PythonProfile:
    if dag is None:
        dag = _make_dag()
    return PythonProfile(dag)


def _assert_no_error(result: CompiledExpression) -> None:
    """Invariant NoError: ~has_error — compilation must not set an error flag."""
    assert result is not None
    assert result.has_error is False


def _assert_original_preserved(result: CompiledExpression) -> None:
    """Invariant OriginalPreserved: every mapped tla_op must be non-empty."""
    for mapping in result.operator_mappings:
        assert mapping.tla_op != "", (
            f"OriginalPreserved violated: empty tla_op found in {mapping}"
        )


def _assert_all_mapped(result: CompiledExpression, expected_tokens: list) -> None:
    """Invariant AllMapped: cursor > N => all N tokens appear in results.
    After a complete compile_condition call cursor > N, so every token
    in expected_tokens must have a corresponding mapping entry."""
    mapped_tla = {m.tla_op for m in result.operator_mappings}
    for tok in expected_tokens:
        assert tok["tla_op"] in mapped_tla, (
            f"AllMapped violated: tla_op '{tok['tla_op']}' missing from results"
        )
    for tok in expected_tokens:
        match = next(m for m in result.operator_mappings if m.tla_op == tok["tla_op"])
        assert match.py_op == tok["py_op"], (
            f"AllMapped violated: {tok['tla_op']} mapped to '{match.py_op}', "
            f"expected '{tok['py_op']}'"
        )


def _assert_quantifier_before_in(result: CompiledExpression) -> None:
    """Invariant QuantifierBeforeIn: TRUE in the spec — always passes.
    The result must at minimum be a valid CompiledExpression (not None / an
    exception), confirming compile_condition completed successfully."""
    assert isinstance(result, CompiledExpression)


def _assert_all_invariants(result: CompiledExpression, tokens: list) -> None:
    _assert_no_error(result)
    _assert_original_preserved(result)
    _assert_all_mapped(result, tokens)
    _assert_quantifier_before_in(result)


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def profile() -> PythonProfile:
    """Default profile backed by an empty DAG (mirrors Init state)."""
    return _make_profile(_make_dag())


@pytest.fixture
def profile_with_behavior_node() -> PythonProfile:
    dag = _make_dag()
    dag.add_node(Node.behavior("b1", "B1", "given", "when", "then"))
    return _make_profile(dag)


@pytest.fixture
def profile_with_resource_node() -> PythonProfile:
    dag = _make_dag()
    dag.add_node(Node.resource("r1", "R1", "some resource"))
    return _make_profile(dag)


@pytest.fixture
def profile_two_nodes_edge() -> PythonProfile:
    dag = _make_dag()
    dag.add_node(Node.behavior("b1", "B1", "g", "w", "t"))
    dag.add_node(Node.behavior("b2", "B2", "g", "w", "t"))
    dag.add_edge(Edge("b1", "b2", EdgeType.IMPORTS))
    return _make_profile(dag)


# ─── Trace 1: all 11 operators — \in /\ \/ = # \A \E Len Cardinality TRUE FALSE
# Final state: results has all 11 tokens, has_error=FALSE, cursor=12, pc=Done

def test_trace_1_all_operators_full_expression(profile: PythonProfile) -> None:
    """Trace 1 (36 steps): compile expression carrying every standard operator.
    Init: results={}, cursor=1, has_error=FALSE.
    After CompileLoop×11 + Finish: all 11 tokens in results, has_error=FALSE.
    """
    tla_expr = (
        r"x \in S /\ a \/ b = c # d /\ \A x \in S : TRUE /\ \E y \in T : FALSE"
        r" /\ Len(seq) > 0 /\ Cardinality(st) > 0"
    )
    result = profile.compile_condition(tla_expr)

    # Final-state assertion: CompiledExpression returned (pc = Done)
    assert isinstance(result, CompiledExpression)

    # AllMapped: all N=11 tokens must appear in results
    _assert_all_invariants(result, TOKENS)

    # Output expression uses Python operators, not TLA+ syntax.
    # Expression contains both \A and \E so both "all" and "any" must appear.
    py_expr = result.expression
    assert "in" in py_expr
    assert "and" in py_expr
    assert "or" in py_expr
    assert "==" in py_expr
    assert "!=" in py_expr
    assert "all" in py_expr
    assert "any" in py_expr
    assert "len" in py_expr
    assert "True" in py_expr
    assert "False" in py_expr

    # NoError invariant at every state: cursor advanced 11 times without error
    assert result.has_error is False


# ─── Trace 2: same 11-token set, different input phrasing (membership + conjunction)

def test_trace_2_membership_and_conjunction(profile: PythonProfile) -> None:
    """Trace 2 (36 steps): expression leading with membership (\\in) and conjunction (/\\)."""
    tla_expr = (
        r"elem \in collection /\ other \in set2 /\ a \/ b = c # d"
        r" /\ \A z \in Z : TRUE /\ \E w \in W : FALSE"
        r" /\ Len(s) > 0 /\ Cardinality(t) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "in" in result.expression
    assert "and" in result.expression
    assert result.has_error is False


# ─── Trace 3: expression leading with disjunction (\/)

def test_trace_3_disjunction_emphasis(profile: PythonProfile) -> None:
    """Trace 3 (36 steps): expression exercising \\/ (or) prominently."""
    tla_expr = (
        r"a \/ b \/ c /\ x \in S /\ x = y # z"
        r" /\ \A p \in P : TRUE /\ \E q \in Q : FALSE"
        r" /\ Len(seq) > 1 /\ Cardinality(col) > 1"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "or" in result.expression
    assert result.has_error is False


# ─── Trace 4: expression with equality (=)

def test_trace_4_equality_operator(profile: PythonProfile) -> None:
    """Trace 4 (36 steps): expression exercising TLA+ = (maps to Python ==)."""
    tla_expr = (
        r"x = y /\ a \in S \/ b # c"
        r" /\ \A i \in I : TRUE /\ \E j \in J : FALSE"
        r" /\ Len(l) = 3 /\ Cardinality(s) = 3"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "==" in result.expression
    assert result.has_error is False


# ─── Trace 5: expression with inequality (#)

def test_trace_5_inequality_operator(profile: PythonProfile) -> None:
    """Trace 5 (36 steps): expression exercising TLA+ # (maps to Python !=)."""
    tla_expr = (
        r"x # y /\ a \in S \/ b = c"
        r" /\ \A m \in M : TRUE /\ \E n \in N : FALSE"
        r" /\ Len(arr) # 0 /\ Cardinality(bag) # 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "!=" in result.expression
    assert result.has_error is False


# ─── Trace 6: universal quantifier (\A) emphasis

def test_trace_6_universal_quantifier(profile: PythonProfile) -> None:
    """Trace 6 (36 steps): expression foregrounding \\A (ForAll -> all)."""
    tla_expr = (
        r"\A x \in S : x \in T /\ x = x # FALSE"
        r" \/ \E y \in U : TRUE"
        r" /\ Len(s1) > 0 /\ Cardinality(s2) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "all" in result.expression
    assert result.has_error is False


# ─── Trace 7: existential quantifier (\E) emphasis

def test_trace_7_existential_quantifier(profile: PythonProfile) -> None:
    """Trace 7 (36 steps): expression foregrounding \\E (Exists -> any)."""
    tla_expr = (
        r"\E x \in S : x \in T /\ x = x # FALSE"
        r" \/ \A y \in U : TRUE"
        r" /\ Len(s1) > 0 /\ Cardinality(s2) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "any" in result.expression
    assert result.has_error is False


# ─── Trace 8: Len emphasis

def test_trace_8_len_operator(profile: PythonProfile) -> None:
    """Trace 8 (36 steps): expression exercising Len (maps to Python len)."""
    tla_expr = (
        r"Len(s) > 0 /\ Len(t) = 5 /\ x \in S \/ y # z"
        r" /\ \A a \in A : TRUE /\ \E b \in B : FALSE"
        r" /\ Cardinality(c) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "len" in result.expression
    assert result.has_error is False


# ─── Trace 9: Cardinality emphasis

def test_trace_9_cardinality_operator(profile: PythonProfile) -> None:
    """Trace 9 (36 steps): expression exercising Cardinality (maps to Python len)."""
    tla_expr = (
        r"Cardinality(S) > 0 /\ Cardinality(T) = 3 /\ x \in S"
        r" \/ y = z # w /\ \A p \in P : TRUE /\ \E q \in Q : FALSE"
        r" /\ Len(seq) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "len" in result.expression
    assert result.has_error is False


# ─── Trace 10: boolean literal emphasis (TRUE / FALSE)

def test_trace_10_boolean_literals(profile: PythonProfile) -> None:
    """Trace 10 (36 steps): expression exercising TRUE and FALSE literals."""
    tla_expr = (
        r"TRUE /\ FALSE \/ x \in S /\ y = z # w"
        r" /\ \A a \in A : TRUE /\ \E b \in B : FALSE"
        r" /\ Len(l) > 0 /\ Cardinality(c) > 0"
    )
    result = profile.compile_condition(tla_expr)

    assert isinstance(result, CompiledExpression)
    _assert_all_invariants(result, TOKENS)
    assert "True" in result.expression
    assert "False" in result.expression
    assert result.has_error is False


# ─── Invariant verifier: AllMapped across two distinct topologies ─────────────

class TestInvariantAllMapped:
    """AllMapped: after compile_condition, every one of the N=11 tokens
    must appear in result.operator_mappings (cursor > N condition satisfied)."""

    def test_all_mapped_empty_dag(self, profile: PythonProfile) -> None:
        tla_expr = (
            r"x \in S /\ a \/ b = c # d"
            r" /\ \A x \in S : TRUE /\ \E y \in T : FALSE"
            r" /\ Len(l) > 0 /\ Cardinality(c) > 0"
        )
        result = profile.compile_condition(tla_expr)
        _assert_all_mapped(result, TOKENS)

    def test_all_mapped_dag_with_behavior_node(
        self, profile_with_behavior_node: PythonProfile
    ) -> None:
        tla_expr = (
            r"\A p \in P : p \in Q /\ p = r # s \/ TRUE /\ FALSE"
            r" /\ \E q \in Q : TRUE /\ Len(seq) > 0 /\ Cardinality(st) > 0"
        )
        result = profile_with_behavior_node.compile_condition(tla_expr)
        _assert_all_mapped(result, TOKENS)
        # Spot-check each token from the TLA+ Tokens sequence
        mapped = {m.tla_op: m.py_op for m in result.operator_mappings}
        assert mapped["In"]     == "in"
        assert mapped["And"]    == "and"
        assert mapped["Or"]     == "or"
        assert mapped["Eq"]     == "=="
        assert mapped["Neq"]    == "!="
        assert mapped["ForAll"] == "all"
        assert mapped["Exists"] == "any"
        assert mapped["Len"]    == "len"
        assert mapped["Card"]   == "len"
        assert mapped["BoolT"]  == "True"
        assert mapped["BoolF"]  == "False"


# ─── Invariant verifier: OriginalPreserved across two distinct topologies ──────

class TestInvariantOriginalPreserved:
    r"""OriginalPreserved: \A r \in results : r.tla_op # ""
    No mapping entry may have an empty tla_op string."""

    def test_original_preserved_empty_dag(self, profile: PythonProfile) -> None:
        tla_expr = r"x \in S /\ y = z # w \/ TRUE /\ \A a \in A : FALSE /\ Len(l) > 0 /\ Cardinality(c) > 0 /\ \E b \in B : TRUE"
        result = profile.compile_condition(tla_expr)
        _assert_original_preserved(result)

    def test_original_preserved_two_node_dag(
        self, profile_two_nodes_edge: PythonProfile
    ) -> None:
        tla_expr = (
            r"\E x \in S : x \in T /\ x = y # z \/ FALSE /\ \A p \in P : TRUE"
            r" /\ Len(seq) > 0 /\ Cardinality(st) > 0"
        )
        result = profile_two_nodes_edge.compile_condition(tla_expr)
        _assert_original_preserved(result)
        for mapping in result.operator_mappings:
            assert mapping.tla_op != ""
            assert mapping.py_op  != ""


# ─── Invariant verifier: NoError across two distinct topologies ───────────────

class TestInvariantNoError:
    """NoError: ~has_error — compilation of valid TLA+ must never set has_error."""

    def test_no_error_simple_membership(self, profile: PythonProfile) -> None:
        result = profile.compile_condition(r"x \in S")
        _assert_no_error(result)

    def test_no_error_full_operator_set(self, profile: PythonProfile) -> None:
        tla_expr = (
            r"x \in S /\ a \/ b = c # d"
            r" /\ \A x \in S : TRUE /\ \E y \in T : FALSE"
            r" /\ Len(l) > 0 /\ Cardinality(c) > 0"
        )
        result = profile.compile_condition(tla_expr)
        _assert_no_error(result)

    def test_no_error_resource_node_dag(
        self, profile_with_resource_node: PythonProfile
    ) -> None:
        tla_expr = (
            r"\A x \in S : x \in T /\ x = y # z \/ TRUE /\ \E p \in P : FALSE"
            r" /\ Len(l) > 0 /\ Cardinality(c) > 0"
        )
        result = profile_with_resource_node.compile_condition(tla_expr)
        _assert_no_error(result)


# ─── Invariant verifier: QuantifierBeforeIn (TRUE — trivially holds) ──────────

class TestInvariantQuantifierBeforeIn:
    """QuantifierBeforeIn is defined as TRUE in the spec; always satisfied.
    Tests confirm compile_condition completes and returns a CompiledExpression
    — the only falsifiable claim when the invariant condition is TRUE."""

    def test_quantifier_before_in_empty_dag(self, profile: PythonProfile) -> None:
        result = profile.compile_condition(r"\A x \in S : x \in T")
        _assert_quantifier_before_in(result)

    def test_quantifier_before_in_with_exists(self, profile: PythonProfile) -> None:
        result = profile.compile_condition(r"\E y \in U : y \in V")
        _assert_quantifier_before_in(result)


# ─── Operator mapping unit tests (one assertion per token) ───────────────────

class TestIndividualOperatorMappings:
    """Focused tests — each verifies a single TLA+ -> Python operator mapping.
    Derived from the TLA+ Tokens sequence (cursor positions 1-11)."""

    def test_in_maps_to_in(self, profile: PythonProfile) -> None:
        r"""Token 1 (cursor=1): \in -> in"""
        result = profile.compile_condition(r"x \in S")
        assert "in" in result.expression

    def test_and_maps_to_and(self, profile: PythonProfile) -> None:
        r"""Token 2 (cursor=2): /\ -> and"""
        result = profile.compile_condition(r"x \in S /\ y \in T")
        assert "and" in result.expression

    def test_or_maps_to_or(self, profile: PythonProfile) -> None:
        r"""Token 3 (cursor=3): \/ -> or"""
        result = profile.compile_condition(r"x \in S \/ y \in T")
        assert "or" in result.expression

    def test_eq_maps_to_double_equals(self, profile: PythonProfile) -> None:
        """Token 4 (cursor=4): = -> =="""
        result = profile.compile_condition(r"x = y")
        assert "==" in result.expression

    def test_neq_maps_to_not_equals(self, profile: PythonProfile) -> None:
        """Token 5 (cursor=5): # -> !="""
        result = profile.compile_condition(r"x # y")
        assert "!=" in result.expression

    def test_forall_maps_to_all(self, profile: PythonProfile) -> None:
        r"""Token 6 (cursor=6): \A -> all"""
        result = profile.compile_condition(r"\A x \in S : x \in T")
        assert "all" in result.expression

    def test_exists_maps_to_any(self, profile: PythonProfile) -> None:
        r"""Token 7 (cursor=7): \E -> any"""
        result = profile.compile_condition(r"\E x \in S : x \in T")
        assert "any" in result.expression

    def test_len_maps_to_len(self, profile: PythonProfile) -> None:
        """Token 8 (cursor=8): Len -> len"""
        result = profile.compile_condition(r"Len(s) > 0")
        assert "len" in result.expression

    def test_cardinality_maps_to_len(self, profile: PythonProfile) -> None:
        """Token 9 (cursor=9): Cardinality -> len"""
        result = profile.compile_condition(r"Cardinality(S) > 0")
        assert "len" in result.expression

    def test_true_maps_to_python_true(self, profile: PythonProfile) -> None:
        """Token 10 (cursor=10): TRUE -> True"""
        result = profile.compile_condition(r"TRUE")
        assert "True" in result.expression

    def test_false_maps_to_python_false(self, profile: PythonProfile) -> None:
        """Token 11 (cursor=11): FALSE -> False"""
        result = profile.compile_condition(r"FALSE")
        assert "False" in result.expression


# ─── Edge-case tests ──────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases derived from trace Init state (results={}, has_error=FALSE)
    and minimally extended where traces do not cover the scenario."""

    def test_empty_expression_raises_or_returns_error(
        self, profile: PythonProfile
    ) -> None:
        """Empty TLA+ expression: implementation must either raise ValueError
        or return a CompiledExpression with has_error=True."""
        try:
            result = profile.compile_condition("")
            assert result.has_error is True
        except (ValueError, SyntaxError):
            pass  # Raising is also acceptable

    def test_expression_with_only_boolean_true(self, profile: PythonProfile) -> None:
        """Minimal valid expression: single TRUE literal."""
        result = profile.compile_condition(r"TRUE")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False
        assert "True" in result.expression

    def test_expression_with_only_boolean_false(self, profile: PythonProfile) -> None:
        """Minimal valid expression: single FALSE literal."""
        result = profile.compile_condition(r"FALSE")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False
        assert "False" in result.expression

    def test_nested_quantifiers(self, profile: PythonProfile) -> None:
        r"""Nested \A and \E: \A x \in S : \E y \in T : x \in y"""
        result = profile.compile_condition(r"\A x \in S : \E y \in T : x \in y")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False
        assert "all" in result.expression
        assert "any" in result.expression
        assert "in" in result.expression

    def test_both_len_and_cardinality_in_same_expression(
        self, profile: PythonProfile
    ) -> None:
        """Both Len and Cardinality must map to len — no conflict."""
        result = profile.compile_condition(r"Len(s) = Cardinality(T)")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False
        assert result.expression.count("len") >= 2

    def test_conjunction_of_all_comparison_operators(
        self, profile: PythonProfile
    ) -> None:
        """= and # in the same expression both map correctly."""
        result = profile.compile_condition(r"x = y /\ a # b")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False
        assert "==" in result.expression
        assert "!=" in result.expression

    def test_diamond_dependency_dag(self) -> None:
        """DAG with a diamond topology: b1->b2, b1->b3, b2->b4, b3->b4.
        compile_condition must still work correctly (profile does not error)."""
        dag = _make_dag()
        for nid in ("b1", "b2", "b3", "b4"):
            dag.add_node(Node.behavior(nid, nid, "g", "w", "t"))
        dag.add_edge(Edge("b1", "b2", EdgeType.IMPORTS))
        dag.add_edge(Edge("b1", "b3", EdgeType.IMPORTS))
        dag.add_edge(Edge("b2", "b4", EdgeType.IMPORTS))
        dag.add_edge(Edge("b3", "b4", EdgeType.IMPORTS))
        profile = _make_profile(dag)
        tla_expr = (
            r"x \in S /\ y = z # w \/ TRUE /\ \A a \in A : FALSE"
            r" /\ \E b \in B : TRUE /\ Len(l) > 0 /\ Cardinality(c) > 0"
        )
        result = profile.compile_condition(tla_expr)
        assert isinstance(result, CompiledExpression)
        _assert_all_invariants(result, TOKENS)

    def test_isolated_node_dag(self) -> None:
        """DAG with a single isolated node (no edges): compilation unaffected."""
        dag = _make_dag()
        dag.add_node(Node.behavior("isolated", "Isolated", "g", "w", "t"))
        profile = _make_profile(dag)
        result = profile.compile_condition(r"x \in S /\ y = z")
        assert isinstance(result, CompiledExpression)
        assert result.has_error is False

    def test_compile_condition_is_idempotent(self, profile: PythonProfile) -> None:
        """Calling compile_condition twice with the same expression yields
        identical results — no internal state mutation between calls."""
        tla_expr = r"x \in S /\ y = z # w"
        result1 = profile.compile_condition(tla_expr)
        result2 = profile.compile_condition(tla_expr)
        assert result1.expression == result2.expression
        assert result1.has_error == result2.has_error

    def test_compile_condition_preserves_original_expression(
        self, profile: PythonProfile
    ) -> None:
        """OriginalPreserved: the original TLA+ expression is retained
        verbatim on the CompiledExpression object."""
        tla_expr = r"x \in S /\ y = z"
        result = profile.compile_condition(tla_expr)
        assert result.original_expression == tla_expr

    def test_all_operator_names_absent_from_output(
        self, profile: PythonProfile
    ) -> None:
        r"""TLA+ operator tokens (\in, /\, \/) must not appear literally
        in the compiled Python expression."""
        tla_expr = (
            r"x \in S /\ a \/ b = c # d"
            r" /\ \A x \in S : TRUE /\ \E y \in T : FALSE"
            r" /\ Len(l) > 0 /\ Cardinality(c) > 0"
        )
        result = profile.compile_condition(tla_expr)
        py_expr = result.expression
        assert r"\in" not in py_expr
        assert "/\\" not in py_expr
        assert "\\/" not in py_expr
        assert r"\A"  not in py_expr
        assert r"\E"  not in py_expr


# ─── typing import needed for Optional ───────────────────────────────────────
from typing import Optional