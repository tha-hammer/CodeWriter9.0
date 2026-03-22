"""
pytest test suite for ContextStackRanking – section-ordering invariants.

Derived directly from 10 TLC-verified simulation traces.
Every invariant that holds at every TLA+ state is re-checked in Python:
  StrictlyIncreasing, ValidRanks, NoDuplicates, SimTracesFirst,
  Rank1Iff, Rank2Iff, Rank3Iff, Rank4Iff, Rank5Always, FallbackIff,
  TypeOK, OrderingInvariant, GWTInvariant.

API surface used:
  RegistryDag, Node, Edge, EdgeType   (registry/dag.py / registry/types.py)
  build_test_plan_prompt              (context_stack_ranking.py – function under test)
"""

from __future__ import annotations

import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node
from context_stack_ranking import build_test_plan_prompt


# ---------------------------------------------------------------------------
# Artifact-bundle helpers
# ---------------------------------------------------------------------------

_SIM_TRACE_TEXT = "## Simulation Traces\nstate1 -> state2"
_API_CONTEXT_TEXT = "## API Source\ndef build_test_plan_prompt(): ..."
_GWT_TEXT = "Given … When … Then …"
_VERIFIER_TEXT = "## Verifiers\nassert invariant_holds()"
_TLA_SPEC_TEXT = "---- MODULE M ----\nINVARIANT Foo\n===="
_SCENARIO_TEXT = "## Test Scenarios\n- scenario A"
_STRUCTURAL_TEXT = "## Structural Patterns\n- pattern X"


def _artifacts(
    *,
    has_sim_traces: bool,
    has_api_context: bool,
    has_verifiers: bool,
    has_tla_spec: bool,
    has_test_scenarios: bool,
) -> dict:
    """Build the artifact dict that mirrors the TLA+ Init state variables."""
    return {
        "sim_traces": _SIM_TRACE_TEXT if has_sim_traces else None,
        "api_context": _API_CONTEXT_TEXT if has_api_context else None,
        "gwt_text": _GWT_TEXT if has_api_context else None,
        "verifiers": _VERIFIER_TEXT if has_verifiers else None,
        "tla_spec": _TLA_SPEC_TEXT if has_tla_spec else None,
        "test_scenarios": _SCENARIO_TEXT if has_test_scenarios else None,
        "structural_patterns": _STRUCTURAL_TEXT,
    }


def _make_dag(
    *,
    has_sim_traces: bool,
    has_api_context: bool,
    has_verifiers: bool,
    has_tla_spec: bool,
    has_test_scenarios: bool,
) -> RegistryDag:
    """
    Construct a RegistryDag whose topology reflects the Init state of a trace.
    One resource node per present context section; edges wire them in rank order.
    """
    dag = RegistryDag()

    nodes_in_order: list[str] = []

    if has_sim_traces:
        dag.add_node(Node.resource("ctx_rank1", "SimulationTraces",
                                   "TLC simulation traces (rank 1)"))
        nodes_in_order.append("ctx_rank1")

    if has_api_context:
        dag.add_node(Node.resource("ctx_rank2", "APIContext",
                                   "API source + GWT text (rank 2)"))
        nodes_in_order.append("ctx_rank2")

    if has_verifiers:
        dag.add_node(Node.resource("ctx_rank3", "Verifiers",
                                   "Verifiers and compiler hints (rank 3)"))
        nodes_in_order.append("ctx_rank3")

    if has_tla_spec:
        dag.add_node(Node.resource("ctx_rank4", "TLASpec",
                                   "TLA+ spec text (rank 4)"))
        nodes_in_order.append("ctx_rank4")

    dag.add_node(Node.resource("ctx_rank5", "StructuralPatterns",
                               "Structural patterns (rank 5, always present)"))
    nodes_in_order.append("ctx_rank5")

    for src, dst in zip(nodes_in_order, nodes_in_order[1:]):
        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))

    dag.test_artifacts = _artifacts(
        has_sim_traces=has_sim_traces,
        has_api_context=has_api_context,
        has_verifiers=has_verifiers,
        has_tla_spec=has_tla_spec,
        has_test_scenarios=has_test_scenarios,
    )
    return dag


# ---------------------------------------------------------------------------
# Invariant helpers (direct Python translation of TLA+ predicates)
#
# Index note: TLA+ uses 1-based indexing; Python uses 0-based.
# Every comparison of the form "order[1] = 1" (TLA+) becomes
# "order[0] == 1" here, and "i > 1" (TLA+) becomes "i > 0" (Python).
# ---------------------------------------------------------------------------

def _strictly_increasing(order: list[int]) -> bool:
    """TLA+ StrictlyIncreasing: forall i in 0..Len(order)-2: order[i] < order[i+1]."""
    return all(order[i] < order[i + 1] for i in range(len(order) - 1))


def _valid_ranks(order: list[int]) -> bool:
    """TLA+ TypeOK: every element of section_order is an integer in 1..5."""
    return all(isinstance(r, int) and not isinstance(r, bool) and 1 <= r <= 5
               for r in order)


def _no_duplicates(order: list[int]) -> bool:
    """TLA+ NoDuplicates: all rank values in section_order are distinct."""
    return len(order) == len(set(order))


def _sim_traces_first(order: list[int], has_sim_traces: bool) -> bool:
    """TLA+ SimTracesFirst: has_sim_traces => order[0] = 1 (0-based Python)."""
    if has_sim_traces and len(order) >= 1:
        return order[0] == 1
    return True


def _contains_rank(order: list[int], r: int) -> bool:
    """Helper: rank r is present in section_order."""
    return r in order


def _rank1_iff(order: list[int], has_sim_traces: bool) -> bool:
    """TLA+ Rank1Iff: (1 in section_order) iff has_sim_traces."""
    return _contains_rank(order, 1) == has_sim_traces


def _rank2_iff(order: list[int], has_api_context: bool) -> bool:
    """TLA+ Rank2Iff: (2 in section_order) iff has_api_context."""
    return _contains_rank(order, 2) == has_api_context


def _rank3_iff(order: list[int], has_verifiers: bool) -> bool:
    """TLA+ Rank3Iff: (3 in section_order) iff has_verifiers."""
    return _contains_rank(order, 3) == has_verifiers


def _rank4_iff(order: list[int], has_tla_spec: bool) -> bool:
    """TLA+ Rank4Iff: (4 in section_order) iff has_tla_spec."""
    return _contains_rank(order, 4) == has_tla_spec


def _rank5_always(order: list[int]) -> bool:
    """TLA+ Rank5Always: 5 in section_order always."""
    return _contains_rank(order, 5)


def _fallback_iff(fallback_appended: bool,
                  has_sim_traces: bool,
                  has_test_scenarios: bool) -> bool:
    """TLA+ FallbackIff: fallback_appended iff (NOT has_sim_traces AND has_test_scenarios)."""
    expected = (not has_sim_traces) and has_test_scenarios
    return fallback_appended == expected


def _gwt_invariant(order: list[int],
                   has_sim_traces: bool,
                   has_api_context: bool,
                   has_verifiers: bool,
                   has_tla_spec: bool) -> bool:
    """
    TLA+ GWTInvariant: full causal-ordering predicate over the assembled ranks.
    """
    if has_sim_traces:
        if not (len(order) >= 1 and order[0] == 1):
            return False

    if has_api_context:
        found = False
        for i, r in enumerate(order):
            if r == 2:
                if not has_sim_traces or i > 0:
                    found = True
                    break
        if not found:
            return False

    if has_verifiers:
        found = False
        for i, r in enumerate(order):
            if r == 3:
                if not has_api_context or any(order[j] == 2 for j in range(i)):
                    found = True
                    break
        if not found:
            return False

    if has_tla_spec:
        found = False
        for i, r in enumerate(order):
            if r == 4:
                if not has_verifiers or any(order[j] == 3 for j in range(i)):
                    found = True
                    break
        if not found:
            return False

    found_5 = False
    for i, r in enumerate(order):
        if r == 5:
            if not has_tla_spec or any(order[j] == 4 for j in range(i)):
                found_5 = True
                break
    return found_5


def _assert_all_invariants(
    order: list[int],
    fallback_appended: bool,
    built: bool,
    has_sim_traces: bool,
    has_api_context: bool,
    has_verifiers: bool,
    has_tla_spec: bool,
    has_test_scenarios: bool,
) -> None:
    """Assert every TLA+ invariant that must hold once built=TRUE."""
    assert built is True

    assert isinstance(has_sim_traces, bool)
    assert isinstance(has_api_context, bool)
    assert isinstance(has_verifiers, bool)
    assert isinstance(has_tla_spec, bool)
    assert isinstance(has_test_scenarios, bool)
    assert isinstance(fallback_appended, bool)
    assert isinstance(built, bool)
    assert _valid_ranks(order), f"ValidRanks failed: {order}"

    assert _strictly_increasing(order), f"StrictlyIncreasing failed: {order}"

    assert _no_duplicates(order), f"NoDuplicates failed: {order}"

    assert _sim_traces_first(order, has_sim_traces), \
        f"SimTracesFirst failed: {order}, has_sim_traces={has_sim_traces}"

    assert _rank1_iff(order, has_sim_traces), \
        f"Rank1Iff failed: {order}, has_sim_traces={has_sim_traces}"
    assert _rank2_iff(order, has_api_context), \
        f"Rank2Iff failed: {order}, has_api_context={has_api_context}"
    assert _rank3_iff(order, has_verifiers), \
        f"Rank3Iff failed: {order}, has_verifiers={has_verifiers}"
    assert _rank4_iff(order, has_tla_spec), \
        f"Rank4Iff failed: {order}, has_tla_spec={has_tla_spec}"
    assert _rank5_always(order), f"Rank5Always failed: {order}"

    assert _fallback_iff(fallback_appended, has_sim_traces, has_test_scenarios), \
        (f"FallbackIff failed: fallback_appended={fallback_appended}, "
         f"has_sim_traces={has_sim_traces}, has_test_scenarios={has_test_scenarios}")

    assert _gwt_invariant(order, has_sim_traces, has_api_context,
                          has_verifiers, has_tla_spec), \
        f"GWTInvariant failed: {order}"


# ---------------------------------------------------------------------------
# Trace 1 – has_sim_traces=T, has_api_context=T, has_verifiers=F,
#           has_tla_spec=T, has_test_scenarios=T
#  Final section_order = [1, 2, 4, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace1:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=True,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 1: all invariants hold for section_order=[1,2,4,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [1, 2, 4, 5], f"Expected [1,2,4,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=True,
        )

    def test_dag_topology_reflects_rank_order(self, dag):
        """
        Verifies Rank3Iff (rank 3 absent when has_verifiers=False) directly
        through build_test_plan_prompt rather than relying on undeclared exception-
        raising semantics of query_relevant for absent nodes.
        """
        result_rank1 = dag.query_relevant("ctx_rank1")
        assert result_rank1 is not None

        prompt_result = build_test_plan_prompt(dag)
        assert 3 not in prompt_result["section_order"], (
            "Rank3Iff violated: rank 3 present but has_verifiers=False"
        )

    def test_subgraph_starts_at_rank1(self, dag):
        """
        extract_subgraph returns a SubgraphResult whose declared interface
        exposes reachable node identifiers via .node_ids (a set[str]).
        """
        sg = dag.extract_subgraph("ctx_rank1")
        assert "ctx_rank1" in sg.node_ids


# ---------------------------------------------------------------------------
# Trace 2 – has_sim_traces=T, has_api_context=T, has_verifiers=F,
#           has_tla_spec=F, has_test_scenarios=T
#  Final section_order = [1, 2, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace2:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 2: all invariants hold for section_order=[1,2,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [1, 2, 5], f"Expected [1,2,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_rank4_absent_when_no_tla_spec(self, dag):
        """Rank4Iff: rank 4 must be absent when has_tla_spec=False."""
        result = build_test_plan_prompt(dag)
        assert 4 not in result["section_order"]


# ---------------------------------------------------------------------------
# Trace 3 – has_sim_traces=F, has_api_context=T, has_verifiers=T,
#           has_tla_spec=F, has_test_scenarios=F
#  Final section_order = [2, 3, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace3:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=False,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 3: all invariants hold for section_order=[2,3,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [2, 3, 5], f"Expected [2,3,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=False,
        )

    def test_rank1_absent_when_no_sim_traces(self, dag):
        """Rank1Iff: rank 1 must be absent when has_sim_traces=False."""
        result = build_test_plan_prompt(dag)
        assert 1 not in result["section_order"]

    def test_no_fallback_when_no_test_scenarios(self, dag):
        """FallbackIff: no fallback when has_test_scenarios=False."""
        result = build_test_plan_prompt(dag)
        assert result["fallback_appended"] is False


# ---------------------------------------------------------------------------
# Trace 4 – has_sim_traces=F, has_api_context=T, has_verifiers=T,
#           has_tla_spec=F, has_test_scenarios=T
#  Final section_order = [2, 3, 5], fallback_appended=True
# ---------------------------------------------------------------------------

class TestTrace4:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 4: all invariants hold for section_order=[2,3,5], fallback=True."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [2, 3, 5], f"Expected [2,3,5] got {order}"
        assert fallback is True, "Fallback must be appended: no sim_traces + has_test_scenarios"
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_fallback_triggered_no_sim_with_scenarios(self, dag):
        """FallbackIff: fallback triggered when no sim_traces but has_test_scenarios."""
        result = build_test_plan_prompt(dag)
        assert result["fallback_appended"] is True


# ---------------------------------------------------------------------------
# Trace 5 – has_sim_traces=F, has_api_context=T, has_verifiers=F,
#           has_tla_spec=F, has_test_scenarios=T
#  Final section_order = [2, 5], fallback_appended=True
# ---------------------------------------------------------------------------

class TestTrace5:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 5: all invariants hold for section_order=[2,5], fallback=True."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [2, 5], f"Expected [2,5] got {order}"
        assert fallback is True
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_minimal_order_with_only_api_and_structural(self, dag):
        """Only ranks 2 and 5 present when only api_context and structural are available."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert 1 not in order
        assert 3 not in order
        assert 4 not in order
        assert 2 in order
        assert 5 in order


# ---------------------------------------------------------------------------
# Trace 6 – has_sim_traces=F, has_api_context=T, has_verifiers=F,
#           has_tla_spec=T, has_test_scenarios=F
#  Final section_order = [2, 4, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace6:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 6: all invariants hold for section_order=[2,4,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [2, 4, 5], f"Expected [2,4,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )

    def test_tla_spec_included_without_verifiers(self, dag):
        """Rank4Iff + GWTInvariant: rank 4 present without rank 3, rank 4 before rank 5."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert 4 in order
        assert 3 not in order
        assert order.index(4) < order.index(5)


# ---------------------------------------------------------------------------
# Trace 7 – has_sim_traces=T, has_api_context=T, has_verifiers=F,
#           has_tla_spec=T, has_test_scenarios=F
#  Final section_order = [1, 2, 4, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace7:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 7: all invariants hold for section_order=[1,2,4,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [1, 2, 4, 5], f"Expected [1,2,4,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )

    def test_sim_traces_first_position(self, dag):
        """SimTracesFirst: rank 1 must occupy index 0 when has_sim_traces=True."""
        result = build_test_plan_prompt(dag)
        assert result["section_order"][0] == 1


# ---------------------------------------------------------------------------
# Trace 8 – has_sim_traces=F, has_api_context=T, has_verifiers=F,
#           has_tla_spec=T, has_test_scenarios=T
#  Final section_order = [2, 4, 5], fallback_appended=True
# ---------------------------------------------------------------------------

class TestTrace8:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=True,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 8: all invariants hold for section_order=[2,4,5], fallback=True."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [2, 4, 5], f"Expected [2,4,5] got {order}"
        assert fallback is True
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=False,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=True,
        )

    def test_api_before_tla_spec(self, dag):
        """GWTInvariant: rank 2 (api_context) must precede rank 4 (tla_spec)."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order.index(2) < order.index(4)


# ---------------------------------------------------------------------------
# Trace 9 – has_sim_traces=T, has_api_context=T, has_verifiers=F,
#           has_tla_spec=T, has_test_scenarios=F
#  (Same flag combo as Trace 7; distinct trace ID confirms determinism)
#  Final section_order = [1, 2, 4, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace9:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )

    def test_section_order_deterministic(self, dag):
        """build_test_plan_prompt must be deterministic: two calls yield identical results."""
        r1 = build_test_plan_prompt(dag)
        r2 = build_test_plan_prompt(dag)
        assert r1["section_order"] == r2["section_order"]
        assert r1["fallback_appended"] == r2["fallback_appended"]

    def test_section_order_and_invariants(self, dag):
        """Trace 9: determinism confirmation; all invariants hold for [1,2,4,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [1, 2, 4, 5]
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=True,
            has_test_scenarios=False,
        )


# ---------------------------------------------------------------------------
# Trace 10 – has_sim_traces=T, has_api_context=T, has_verifiers=T,
#            has_tla_spec=F, has_test_scenarios=F
#  Final section_order = [1, 2, 3, 5], fallback_appended=False
# ---------------------------------------------------------------------------

class TestTrace10:
    @pytest.fixture
    def dag(self):
        return _make_dag(
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=False,
        )

    def test_section_order_and_invariants(self, dag):
        """Trace 10: all invariants hold for section_order=[1,2,3,5]."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        assert order == [1, 2, 3, 5], f"Expected [1,2,3,5] got {order}"
        assert fallback is False
        assert built is True

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=False,
            has_test_scenarios=False,
        )

    def test_verifiers_before_structural(self, dag):
        """GWTInvariant: rank 3 (verifiers) must precede rank 5 (structural)."""
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order.index(3) < order.index(5)


# ---------------------------------------------------------------------------
# Dedicated invariant verifiers
# ---------------------------------------------------------------------------

class TestStrictlyIncreasing:
    """Rank sequence must always be strictly ascending – no ties, no reversals."""

    @pytest.mark.parametrize("kwargs,expected_order", [
        (dict(has_sim_traces=True, has_api_context=True, has_verifiers=False,
              has_tla_spec=True, has_test_scenarios=True), [1, 2, 4, 5]),
        (dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
              has_tla_spec=False, has_test_scenarios=False), [2, 3, 5]),
        (dict(has_sim_traces=True, has_api_context=True, has_verifiers=True,
              has_tla_spec=False, has_test_scenarios=False), [1, 2, 3, 5]),
        (dict(has_sim_traces=False, has_api_context=True, has_verifiers=False,
              has_tla_spec=True, has_test_scenarios=False), [2, 4, 5]),
    ])
    def test_strictly_increasing(self, kwargs, expected_order):
        """StrictlyIncreasing: section_order values form a strictly ascending sequence."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order == expected_order
        assert _strictly_increasing(order), f"Not strictly increasing: {order}"


class TestValidRanks:
    """Every rank value in section_order must be in 1..5."""

    @pytest.mark.parametrize("kwargs", [
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=False,
             has_tla_spec=True, has_test_scenarios=True),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=True),
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
    ])
    def test_valid_ranks(self, kwargs):
        """TypeOK: all rank integers are in the closed range [1, 5]."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        assert _valid_ranks(result["section_order"]), \
            f"Out-of-range rank: {result['section_order']}"


class TestNoDuplicates:
    """No rank value may appear twice in section_order."""

    @pytest.mark.parametrize("kwargs", [
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=False,
             has_tla_spec=True, has_test_scenarios=True),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=True),
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
    ])
    def test_no_duplicates(self, kwargs):
        """NoDuplicates: every rank value occurs at most once in section_order."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        assert _no_duplicates(result["section_order"]), \
            f"Duplicate rank: {result['section_order']}"


class TestSimTracesFirst:
    """When has_sim_traces=True, rank 1 must occupy position 0."""

    def test_sim_traces_first_with_all_present(self):
        """SimTracesFirst: rank 1 at index 0 when all context sections present."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=True,
            has_tla_spec=True, has_test_scenarios=True,
        )
        result = build_test_plan_prompt(dag)
        assert result["section_order"][0] == 1

    def test_sim_traces_first_minimal(self):
        """SimTracesFirst: rank 1 at index 0 in minimal Trace 2 topology."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=True,
        )
        result = build_test_plan_prompt(dag)
        assert result["section_order"][0] == 1

    def test_sim_traces_absent_rank1_not_in_order(self):
        """Rank1Iff complement: rank 1 absent from order when has_sim_traces=False."""
        dag = _make_dag(
            has_sim_traces=False, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=True,
        )
        result = build_test_plan_prompt(dag)
        assert 1 not in result["section_order"]


class TestRank1Iff:
    """Rank 1 appears in section_order iff has_sim_traces=True."""

    @pytest.mark.parametrize("has_sim_traces,expect_rank1", [
        (True, True),
        (False, False),
    ])
    def test_rank1_iff(self, has_sim_traces, expect_rank1):
        """Rank1Iff biconditional: both directions exercised independently."""
        dag = _make_dag(
            has_sim_traces=has_sim_traces, has_api_context=True,
            has_verifiers=False, has_tla_spec=False, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        assert (1 in result["section_order"]) == expect_rank1


class TestRank2Iff:
    """Rank 2 appears iff has_api_context=True; absent iff has_api_context=False."""

    @pytest.mark.parametrize("has_sim_traces,has_api_context,expect_rank2", [
        (True,  True,  True),
        (False, True,  True),
        (False, False, False),
    ])
    def test_rank2_iff(self, has_sim_traces, has_api_context, expect_rank2):
        """Rank2Iff biconditional: rank 2 present iff has_api_context."""
        dag = _make_dag(
            has_sim_traces=has_sim_traces, has_api_context=has_api_context,
            has_verifiers=False, has_tla_spec=False, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        assert (2 in result["section_order"]) == expect_rank2, (
            f"Rank2Iff failed: expect rank2={expect_rank2}, "
            f"order={result['section_order']}, has_api_context={has_api_context}"
        )


class TestRank3Iff:
    """Rank 3 appears iff has_verifiers=True."""

    @pytest.mark.parametrize("has_verifiers,expect_rank3", [
        (True, True),
        (False, False),
    ])
    def test_rank3_iff(self, has_verifiers, expect_rank3):
        """Rank3Iff biconditional: both directions verified."""
        dag = _make_dag(
            has_sim_traces=False, has_api_context=True,
            has_verifiers=has_verifiers, has_tla_spec=False, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        assert (3 in result["section_order"]) == expect_rank3


class TestRank4Iff:
    """Rank 4 appears iff has_tla_spec=True."""

    @pytest.mark.parametrize("has_tla_spec,expect_rank4", [
        (True, True),
        (False, False),
    ])
    def test_rank4_iff(self, has_tla_spec, expect_rank4):
        """Rank4Iff biconditional: both directions verified."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True,
            has_verifiers=False, has_tla_spec=has_tla_spec, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        assert (4 in result["section_order"]) == expect_rank4


class TestRank5Always:
    """Rank 5 (structural patterns) must appear in every completed build."""

    @pytest.mark.parametrize("kwargs", [
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=False,
             has_tla_spec=True, has_test_scenarios=True),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=False,
             has_tla_spec=False, has_test_scenarios=True),
        dict(has_sim_traces=True, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
    ])
    def test_rank5_always_present(self, kwargs):
        """Rank5Always: structural patterns rank 5 present in every output."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        assert 5 in result["section_order"], \
            f"Rank 5 missing: {result['section_order']}"


class TestFallbackIff:
    """fallback_appended iff (NOT has_sim_traces AND has_test_scenarios)."""

    @pytest.mark.parametrize(
        "has_sim_traces,has_test_scenarios,expect_fallback",
        [
            (True,  True,  False),
            (True,  False, False),
            (False, False, False),
            (False, True,  True),
        ],
    )
    def test_fallback_iff(self, has_sim_traces, has_test_scenarios, expect_fallback):
        """FallbackIff biconditional: all four truth-table rows verified."""
        dag = _make_dag(
            has_sim_traces=has_sim_traces, has_api_context=True,
            has_verifiers=False, has_tla_spec=False,
            has_test_scenarios=has_test_scenarios,
        )
        result = build_test_plan_prompt(dag)
        assert result["fallback_appended"] == expect_fallback, (
            f"fallback_appended={result['fallback_appended']}, "
            f"expected={expect_fallback} for "
            f"has_sim_traces={has_sim_traces}, has_test_scenarios={has_test_scenarios}"
        )


class TestGWTInvariant:
    """Full GWT ordering invariant across multiple trace topologies."""

    @pytest.mark.parametrize("kwargs,expected_order", [
        (dict(has_sim_traces=True, has_api_context=True, has_verifiers=False,
              has_tla_spec=True, has_test_scenarios=True),   [1, 2, 4, 5]),
        (dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
              has_tla_spec=False, has_test_scenarios=False),  [2, 3, 5]),
        (dict(has_sim_traces=True, has_api_context=True, has_verifiers=True,
              has_tla_spec=False, has_test_scenarios=False),  [1, 2, 3, 5]),
        (dict(has_sim_traces=False, has_api_context=True, has_verifiers=False,
              has_tla_spec=True, has_test_scenarios=False),   [2, 4, 5]),
        (dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
              has_tla_spec=False, has_test_scenarios=True),   [2, 3, 5]),
    ])
    def test_gwt_ordering_invariant(self, kwargs, expected_order):
        """GWTInvariant: causal ordering predicate holds for all five topologies."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order == expected_order
        assert _gwt_invariant(
            order,
            kwargs["has_sim_traces"],
            kwargs["has_api_context"],
            kwargs["has_verifiers"],
            kwargs["has_tla_spec"],
        ), f"GWTInvariant violated: {order}"


class TestOrderingInvariant:
    """OrderingInvariant = conjunction of all ordering sub-invariants, post-build."""

    @pytest.mark.parametrize("kwargs", [
        dict(has_sim_traces=True,  has_api_context=True, has_verifiers=False,
             has_tla_spec=True,  has_test_scenarios=True),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=True),
        dict(has_sim_traces=True,  has_api_context=True, has_verifiers=True,
             has_tla_spec=False, has_test_scenarios=False),
        dict(has_sim_traces=False, has_api_context=True, has_verifiers=False,
             has_tla_spec=True,  has_test_scenarios=True),
        dict(has_sim_traces=True,  has_api_context=True, has_verifiers=False,
             has_tla_spec=True,  has_test_scenarios=False),
    ])
    def test_full_ordering_invariant(self, kwargs):
        """OrderingInvariant: conjunction of every sub-invariant checked post-build."""
        dag = _make_dag(**kwargs)
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        fallback = result["fallback_appended"]
        built = result["built"]

        _assert_all_invariants(
            order=order,
            fallback_appended=fallback,
            built=built,
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_no_context_artifacts_returns_rank5_only(self):
        """
        Boundary condition: api_context=False, so Rank2Iff requires rank 2 absent.
        Rank5Always requires rank 5 present.
        """
        dag = RegistryDag()
        dag.add_node(Node.resource("ctx_rank5", "StructuralPatterns",
                                   "Structural patterns (rank 5)"))
        dag.test_artifacts = _artifacts(
            has_sim_traces=False,
            has_api_context=False,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert 5 in order
        assert 1 not in order
        assert 2 not in order
        assert 3 not in order
        assert 4 not in order
        assert _strictly_increasing(order)
        assert _no_duplicates(order)

    def test_isolated_node_does_not_affect_rank_ordering(self):
        """An orphan node in the DAG must not corrupt section ordering."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=False,
        )
        dag.add_node(Node.resource("orphan_42", "OrphanNode", "unrelated"))
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order == [1, 2, 5]
        assert _strictly_increasing(order)

    def test_diamond_topology_does_not_duplicate_ranks(self):
        """
        Diamond dependency pattern: two paths to the same context node.
        NoDuplicates must still hold; rank must appear exactly once.
        """
        dag = RegistryDag()
        dag.add_node(Node.resource("ctx_rank1", "SimulationTraces", ""))
        dag.add_node(Node.resource("ctx_rank2", "APIContext", ""))
        dag.add_node(Node.resource("ctx_rank5", "StructuralPatterns", ""))
        dag.add_node(Node.resource("ctx_via_a", "ViaA", ""))
        dag.add_node(Node.resource("ctx_via_b", "ViaB", ""))
        dag.add_edge(Edge("ctx_rank1", "ctx_via_a", EdgeType.IMPORTS))
        dag.add_edge(Edge("ctx_rank1", "ctx_via_b", EdgeType.IMPORTS))
        dag.add_edge(Edge("ctx_via_a", "ctx_rank5", EdgeType.IMPORTS))
        dag.add_edge(Edge("ctx_via_b", "ctx_rank5", EdgeType.IMPORTS))
        dag.add_edge(Edge("ctx_rank1", "ctx_rank2", EdgeType.IMPORTS))
        dag.add_edge(Edge("ctx_rank2", "ctx_rank5", EdgeType.IMPORTS))
        dag.test_artifacts = _artifacts(
            has_sim_traces=True, has_api_context=True,
            has_verifiers=False, has_tla_spec=False, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert _no_duplicates(order), f"Diamond produced duplicates: {order}"
        assert _strictly_increasing(order)

    def test_missing_sim_traces_artifact_triggers_fallback_when_scenarios_present(self):
        """FallbackIff: derived from Traces 4, 5, 8 – no sim_traces + test_scenarios -> fallback."""
        for has_tla_spec, has_verifiers in ((False, True), (False, False), (True, False)):
            dag = _make_dag(
                has_sim_traces=False, has_api_context=True,
                has_verifiers=has_verifiers, has_tla_spec=has_tla_spec,
                has_test_scenarios=True,
            )
            result = build_test_plan_prompt(dag)
            assert result["fallback_appended"] is True, (
                f"Expected fallback for has_tla_spec={has_tla_spec}, "
                f"has_verifiers={has_verifiers}"
            )

    def test_all_sections_present_full_order(self):
        """All flags True -> section_order must be the complete sequence [1,2,3,4,5]."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=True,
            has_tla_spec=True, has_test_scenarios=True,
        )
        result = build_test_plan_prompt(dag)
        assert result["section_order"] == [1, 2, 3, 4, 5]
        assert result["fallback_appended"] is False
        assert result["built"] is True
        _assert_all_invariants(
            order=result["section_order"],
            fallback_appended=result["fallback_appended"],
            built=result["built"],
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=True,
            has_tla_spec=True,
            has_test_scenarios=True,
        )

    def test_built_flag_set_after_prompt_assembled(self):
        """TypeOK: result['built'] must be boolean True for every completed assembly."""
        dag = _make_dag(
            has_sim_traces=False, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=False,
        )
        result = build_test_plan_prompt(dag)
        assert result["built"] is True

    def test_register_gwt_node_and_prompt_order(self):
        """
        RegistryDag.register_gwt must return a non-None GWT id and must not
        corrupt section ordering.
        """
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=True,
        )
        gwt_id = dag.register_gwt(
            given="a context bundle with simulation traces, API source, and GWT text",
            when="the test plan prompt is assembled",
            then="simulation traces appear first (rank 1)",
        )
        assert gwt_id is not None

        result = build_test_plan_prompt(dag)
        order = result["section_order"]
        assert order == [1, 2, 5]
        assert result["fallback_appended"] is False
        _assert_all_invariants(
            order=order,
            fallback_appended=result["fallback_appended"],
            built=result["built"],
            has_sim_traces=True,
            has_api_context=True,
            has_verifiers=False,
            has_tla_spec=False,
            has_test_scenarios=True,
        )

    def test_validate_edge_between_adjacent_ranks(self):
        """Adjacent rank nodes must form a valid IMPORTS edge (no cycle, valid types)."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=False,
        )
        validation = dag.validate_edge("ctx_rank1", "ctx_rank2", EdgeType.IMPORTS)
        assert validation.is_valid is True

    def test_query_affected_tests_from_rank1_node(self):
        """query_affected_tests on a known node must return a list without error."""
        dag = _make_dag(
            has_sim_traces=True, has_api_context=True, has_verifiers=False,
            has_tla_spec=False, has_test_scenarios=False,
        )
        affected = dag.query_affected_tests("ctx_rank1")
        assert isinstance(affected, list)