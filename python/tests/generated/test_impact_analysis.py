"""Generated test suite from impact_analysis.tla via Bridge (Phase 5).

Mechanically generated from bridge artifacts by run_impact_loop.py.
Verifiers: ValidState, BoundedExecution, ReverseClosureComplete, LeafHasNoImpact, DirectDependentsIncluded, MonotonicGrowth

TLC verification: 624,466 states, 337,346 distinct, 0 violations.
"""

import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Node, Edge, EdgeType, ImpactResult


class TestImpactAnalysisInvariants:
    """Tests mechanically derived from impact_analysis.tla bridge verifiers."""

    def _make_chain_dag(self):
        """a -> b -> c -> d (linear chain)."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        return dag

    def _make_diamond_dag(self):
        """a -> b, a -> c, b -> d, c -> d (diamond)."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("a", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "d", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        return dag

    def _check_invariant(self, name):
        """Dispatch invariant check by name."""
        method = getattr(self, f"_verify_{name}", None)
        if method:
            method()

    # -- Invariant verification methods (one per bridge verifier) --

    def _verify_ReverseClosureComplete(self):
        """Every node in affected has a forward path to target."""
        dag = self._make_chain_dag()
        result = dag.query_impact("d")
        for node in result.affected:
            assert "d" in dag.closure.get(node, set()), \
                f"ReverseClosureComplete: {node} in affected but no path to d"

    def _verify_LeafHasNoImpact(self):
        """If no node depends on target, affected is empty."""
        dag = self._make_chain_dag()
        result = dag.query_impact("a")  # a is root, nothing depends on it
        assert result.affected == set(), \
            f"LeafHasNoImpact: expected empty, got {result.affected}"

    def _verify_DirectDependentsIncluded(self):
        """Direct dependents are a subset of affected."""
        dag = self._make_diamond_dag()
        result = dag.query_impact("d")
        assert result.direct_dependents <= result.affected, \
            f"DirectDependentsIncluded: {result.direct_dependents} not subset of {result.affected}"

    def _verify_ValidState(self):
        """query_impact returns a valid ImpactResult."""
        dag = self._make_chain_dag()
        result = dag.query_impact("c")
        assert isinstance(result, ImpactResult)
        assert result.target == "c"

    def _verify_BoundedExecution(self):
        """Result is finite (bounded by node count)."""
        dag = self._make_chain_dag()
        result = dag.query_impact("d")
        assert len(result.affected) <= dag.node_count

    def _verify_MonotonicGrowth(self):
        """Adding edges can only grow the affected set, not shrink it."""
        dag = RegistryDag()
        for nid in ("a", "b", "c"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "c", EdgeType.DEPENDS_ON))
        before = dag.query_impact("c").affected
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        after = dag.query_impact("c").affected
        assert before <= after, \
            f"MonotonicGrowth: {before} not subset of {after}"

    def _verify_TerminalStates(self):
        """Terminal states are reachable (done/failed)."""
        # The spec ensures termination; implementation always returns.
        dag = self._make_chain_dag()
        result = dag.query_impact("b")
        assert result is not None

    def test_validstate(self):
        """Verifier ValidState: ValidState violation: current_state /in StateSet"""
        # Bridge condition: current_state /in StateSet
        # Applies to: current_state
        self._check_invariant("ValidState")

    def test_boundedexecution(self):
        """Verifier BoundedExecution: BoundedExecution violation: step_count <= MaxSteps"""
        # Bridge condition: step_count <= MaxSteps
        # Applies to: step_count
        self._check_invariant("BoundedExecution")

    def test_reverseclosurecomplete(self):
        """Verifier ReverseClosureComplete: ReverseClosureComplete violation: (current_state = 'done' // target # 0) =>     """
        # Bridge condition: current_state = 'done' AND target # 0) =>     /A n /in reverse_set :     /E path_len /in 1..NumNodes :     /E path /in [
        # Applies to: adjacency, current_state, reverse_set, target
        self._check_invariant("ReverseClosureComplete")

    def test_leafhasnoimpact(self):
        """Verifier LeafHasNoImpact: LeafHasNoImpact violation: (current_state = 'done' // target # 0) =>     ((/A n """
        # Bridge condition: current_state = 'done' AND target # 0) =>     ((/A n /in 1..NumNodes : target /notin adjacency[n]) => reverse_set = {}
        # Applies to: adjacency, current_state, reverse_set, target
        self._check_invariant("LeafHasNoImpact")

    def test_directdependentsincluded(self):
        """Verifier DirectDependentsIncluded: DirectDependentsIncluded violation: (current_state = 'done' // target # 0) => di"""
        # Bridge condition: current_state = 'done' AND target # 0) => direct_dependents /subseteq reverse_set
        # Applies to: current_state, direct_dependents, reverse_set, target
        self._check_invariant("DirectDependentsIncluded")

    def test_monotonicgrowth(self):
        """Verifier MonotonicGrowth: MonotonicGrowth violation: TRUE"""
        # Bridge condition: dirty = TRUE // TRUE
        # Applies to: dirty
        self._check_invariant("MonotonicGrowth")

    # -- Additional invariant-derived tests --

    def test_reverse_closure_chain(self):
        """ReverseClosureComplete: impact(d) in a->b->c->d = {a,b,c}."""
        dag = self._make_chain_dag()
        result = dag.query_impact("d")
        assert result.affected == {"a", "b", "c"}

    def test_reverse_closure_diamond(self):
        """ReverseClosureComplete: impact(d) in diamond = {a,b,c}."""
        dag = self._make_diamond_dag()
        result = dag.query_impact("d")
        assert result.affected == {"a", "b", "c"}

    def test_leaf_isolated_node(self):
        """LeafHasNoImpact: isolated node has empty impact."""
        dag = RegistryDag()
        dag.add_node(Node.resource("x", "isolated", description="test"))
        result = dag.query_impact("x")
        assert result.affected == set()

    def test_direct_dependents_diamond(self):
        """DirectDependentsIncluded: b,c are direct dependents of d in diamond."""
        dag = self._make_diamond_dag()
        result = dag.query_impact("d")
        assert "b" in result.direct_dependents
        assert "c" in result.direct_dependents

    def test_target_not_in_affected(self):
        """Target itself is never in affected set."""
        dag = self._make_chain_dag()
        result = dag.query_impact("d")
        assert "d" not in result.affected

    def test_missing_node_raises(self):
        """NodeNotFoundError for missing node."""
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.query_impact("nonexistent")

    def test_wide_fan_in(self):
        """Multiple direct dependents all appear."""
        dag = RegistryDag()
        dag.add_node(Node.resource("t", "target", description="test"))
        for i in range(5):
            nid = f"dep-{i}"
            dag.add_node(Node.resource(nid, f"dep_{i}", description="test"))
            dag.add_edge(Edge(nid, "t", EdgeType.DEPENDS_ON))
        result = dag.query_impact("t")
        assert result.affected == {f"dep-{i}" for i in range(5)}
        assert result.direct_dependents == result.affected
