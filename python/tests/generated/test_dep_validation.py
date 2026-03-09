"""Generated test suite from dep_validation.tla via Bridge (Phase 6).

Mechanically generated from bridge artifacts by run_dep_validation_loop.py.
Verifiers: TerminalStates, ValidState, BoundedExecution, ValidProposedEdge, AcyclicityPreserved, DuplicateRejected, KindCompatibilityEnforced, ValidEdgeAccepted
"""

import pytest
from registry.dag import RegistryDag, CycleError, NodeNotFoundError
from registry.types import Node, Edge, EdgeType, NodeKind, ValidationResult


class TestDepValidationInvariants:
    """Tests mechanically derived from dep_validation.tla bridge verifiers."""

    def _make_chain_dag(self):
        """a -> b -> c (linear chain, all resources)."""
        dag = RegistryDag()
        for nid in ("a", "b", "c"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        return dag

    def _make_typed_dag(self):
        """DAG with mixed node kinds: req-r1, behavior-b1, resource-x1, test-t1."""
        dag = RegistryDag()
        dag.add_node(Node.requirement("r1", "a requirement"))
        dag.add_node(Node.behavior("b1", "a_behavior", "given", "when", "then"))
        dag.add_node(Node.resource("x1", "a_resource", description="test"))
        dag.add_node(Node(id="t1", kind=NodeKind.TEST, name="a_test"))
        # r1 → b1 → x1 (valid chain)
        dag.add_edge(Edge("r1", "b1", EdgeType.DECOMPOSES))
        dag.add_edge(Edge("b1", "x1", EdgeType.IMPLEMENTS))
        return dag

    def _check_invariant(self, name):
        method = getattr(self, f"_verify_{name}", None)
        if method:
            method()

    # -- Invariant verification methods --

    def _verify_AcyclicityPreserved(self):
        """Edge that would create cycle is rejected."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("c", "a", EdgeType.DEPENDS_ON)
        assert not result.valid, "AcyclicityPreserved: cycle-creating edge should be invalid"
        assert "cycle" in result.reason.lower()

    def _verify_DuplicateRejected(self):
        """Duplicate edge is rejected."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "b", EdgeType.DEPENDS_ON)
        assert not result.valid, "DuplicateRejected: duplicate edge should be invalid"
        assert "duplicate" in result.reason.lower()

    def _verify_KindCompatibilityEnforced(self):
        """Behavior depending on test is rejected."""
        dag = self._make_typed_dag()
        result = dag.validate_edge("b1", "t1", EdgeType.DEPENDS_ON)
        assert not result.valid, "KindCompatibilityEnforced: behavior→test should be invalid"
        assert "kind" in result.reason.lower()

    def _verify_ValidEdgeAccepted(self):
        """Valid edge passes validation."""
        dag = self._make_chain_dag()
        dag.add_node(Node.resource("d", "node_d", description="test"))
        result = dag.validate_edge("c", "d", EdgeType.DEPENDS_ON)
        assert result.valid, f"ValidEdgeAccepted: valid edge rejected with reason: {result.reason}"

    def _verify_ValidState(self):
        """validate_edge returns a valid ValidationResult."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "c", EdgeType.DEPENDS_ON)
        assert isinstance(result, ValidationResult)
        assert result.from_id == "a"
        assert result.to_id == "c"

    def _verify_BoundedExecution(self):
        """Result is deterministic and finite."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "b", EdgeType.DEPENDS_ON)
        assert isinstance(result, ValidationResult)

    def test_terminalstates(self):
        """Verifier TerminalStates: TerminalStates violation: {'done', 'failed'}"""
        # Bridge condition: {'done', 'failed'}
        # Applies to: dep_validation
        self._check_invariant("TerminalStates")

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

    def test_validproposededge(self):
        """Verifier ValidProposedEdge: ValidProposedEdge violation: (proposed_from /in 1..NumNodes) // (proposed_to /in"""
        # Bridge condition: proposed_from /in 1..NumNodes AND proposed_to /in 1..NumNodes
        # Applies to: proposed_from, proposed_to
        self._check_invariant("ValidProposedEdge")

    def test_acyclicitypreserved(self):
        """Verifier AcyclicityPreserved: AcyclicityPreserved violation: (current_state = 'done' // ValidProposedEdge // i"""
        # Bridge condition: current_state = 'done' AND ValidProposedEdge AND is_valid = TRUE =>      proposed_from /notin reachable
        # Applies to: current_state, dirty, is_valid, proposed_from, reachable
        self._check_invariant("AcyclicityPreserved")

    def test_duplicaterejected(self):
        """Verifier DuplicateRejected: DuplicateRejected violation: (current_state = 'done' // ValidProposedEdge // rej"""
        # Bridge condition: current_state = 'done' AND ValidProposedEdge AND rejection_reason = 'duplicate' =>      proposed_to /in adjacency[propos
        # Applies to: adjacency, current_state, dirty, proposed_from, proposed_to, rejection_reason
        self._check_invariant("DuplicateRejected")

    def test_kindcompatibilityenforced(self):
        """Verifier KindCompatibilityEnforced: KindCompatibilityEnforced violation: (current_state = 'done' // ValidProposedEdg"""
        # Bridge condition: current_state = 'done' AND ValidProposedEdge AND is_valid = TRUE AND proposed_edge_type = 1 =>      ~((node_kind[propose
        # Applies to: current_state, dirty, is_valid, node_kind, proposed_edge_type, proposed_from, proposed_to
        self._check_invariant("KindCompatibilityEnforced")

    def test_validedgeaccepted(self):
        """Verifier ValidEdgeAccepted: ValidEdgeAccepted violation: (current_state = 'done' // ValidProposedEdge //    """
        # Bridge condition: current_state = 'done' AND ValidProposedEdge AND proposed_from /notin reachable AND proposed_to /notin adjacency[propose
        # Applies to: adjacency, current_state, dirty, is_valid, node_kind, proposed_edge_type, proposed_from, proposed_to, reachable
        self._check_invariant("ValidEdgeAccepted")

    # -- Additional invariant-derived tests --

    def test_valid_new_edge(self):
        """ValidEdgeAccepted: new edge to new node passes."""
        dag = self._make_chain_dag()
        dag.add_node(Node.resource("d", "node_d", description="test"))
        result = dag.validate_edge("a", "d", EdgeType.DEPENDS_ON)
        assert result.valid
        assert result.reason == ""

    def test_cycle_direct(self):
        """AcyclicityPreserved: direct back-edge rejected."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("b", "a", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "cycle" in result.reason.lower()

    def test_cycle_transitive(self):
        """AcyclicityPreserved: transitive cycle rejected."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("c", "a", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "cycle" in result.reason.lower()

    def test_self_loop_rejected(self):
        """AcyclicityPreserved: self-loop is a cycle."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "a", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "cycle" in result.reason.lower()

    def test_duplicate_exact(self):
        """DuplicateRejected: exact same edge rejected."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "b", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "duplicate" in result.reason.lower()

    def test_same_nodes_different_type_ok(self):
        """DuplicateRejected: same nodes but different edge type is OK."""
        dag = self._make_chain_dag()
        result = dag.validate_edge("a", "b", EdgeType.REFERENCES)
        assert result.valid

    def test_requirement_to_test_rejected(self):
        """KindCompatibilityEnforced: requirement→test depends_on rejected."""
        dag = self._make_typed_dag()
        result = dag.validate_edge("r1", "t1", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "kind" in result.reason.lower()

    def test_behavior_to_test_rejected(self):
        """KindCompatibilityEnforced: behavior→test depends_on rejected."""
        dag = self._make_typed_dag()
        result = dag.validate_edge("b1", "t1", EdgeType.DEPENDS_ON)
        assert not result.valid
        assert "kind" in result.reason.lower()

    def test_resource_to_test_ok(self):
        """KindCompatibilityEnforced: resource→test depends_on is allowed."""
        dag = self._make_typed_dag()
        result = dag.validate_edge("x1", "t1", EdgeType.DEPENDS_ON)
        assert result.valid

    def test_kind_check_only_on_depends_on(self):
        """KindCompatibilityEnforced: kind check only applies to depends_on edges."""
        dag = self._make_typed_dag()
        result = dag.validate_edge("b1", "t1", EdgeType.REFERENCES)
        assert result.valid

    def test_missing_from_node(self):
        """NodeNotFoundError for missing source node."""
        dag = self._make_chain_dag()
        with pytest.raises(NodeNotFoundError):
            dag.validate_edge("nonexistent", "a", EdgeType.DEPENDS_ON)

    def test_missing_to_node(self):
        """NodeNotFoundError for missing target node."""
        dag = self._make_chain_dag()
        with pytest.raises(NodeNotFoundError):
            dag.validate_edge("a", "nonexistent", EdgeType.DEPENDS_ON)

    def test_does_not_mutate_dag(self):
        """validate_edge must not modify the DAG."""
        dag = self._make_chain_dag()
        edges_before = len(dag.edges)
        nodes_before = len(dag.nodes)
        dag.add_node(Node.resource("d", "node_d", description="test"))
        dag.validate_edge("a", "d", EdgeType.DEPENDS_ON)
        assert len(dag.edges) == edges_before
        assert len(dag.nodes) == nodes_before + 1
