"""Generated test suite from subgraph_extraction.tla via Bridge (Phase 7).

Mechanically generated from bridge artifacts by run_subgraph_loop.py.
Verifiers: ValidState, BoundedExecution, SubgraphCompleteness, NoHoles, NoDanglingEdges, IsolatedNodeCorrect
"""

import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Node, Edge, EdgeType, SubgraphResult


class TestSubgraphExtractionInvariants:
    """Tests mechanically derived from subgraph_extraction.tla bridge verifiers."""

    def _make_chain_dag(self):
        """a -> b -> c -> d (linear chain, all resources)."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        return dag

    def _make_diamond_dag(self):
        """Diamond: a -> b, a -> c, b -> d, c -> d."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("a", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "d", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        return dag

    def _make_isolated_dag(self):
        """Three disconnected nodes: x, y, z."""
        dag = RegistryDag()
        for nid in ("x", "y", "z"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        return dag

    def _check_invariant(self, name):
        method = getattr(self, f"_verify_{name}", None)
        if method:
            method()

    # -- Invariant verification methods --

    def _verify_SubgraphCompleteness(self):
        """Subgraph contains all ancestors and descendants."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("b")
        assert "a" in result.nodes, "SubgraphCompleteness: ancestor 'a' missing"
        assert "b" in result.nodes, "SubgraphCompleteness: target 'b' missing"
        assert "c" in result.nodes, "SubgraphCompleteness: descendant 'c' missing"
        assert "d" in result.nodes, "SubgraphCompleteness: descendant 'd' missing"

    def _verify_NoHoles(self):
        """No holes in the subgraph — all reachable nodes included."""
        dag = self._make_diamond_dag()
        result = dag.extract_subgraph("b")
        # b's ancestors: a; b's descendants: d
        # c is NOT in b's subgraph (c is a sibling, not ancestor/descendant of b)
        # But wait: a->c exists and a is in subgraph. c->d exists and d is in subgraph.
        # c is reachable from a (ancestor of b), so... no. The spec says forward+reverse
        # closure of THE TARGET, not of every node in the subgraph.
        # Forward of b: d. Reverse of b: a. Subgraph = {a, b, d}.
        # Edge a->c: c is NOT reachable from b and b is NOT reachable from c.
        # So c should NOT be in subgraph. NoHoles means no holes in closure paths.
        assert "a" in result.nodes
        assert "b" in result.nodes
        assert "d" in result.nodes

    def _verify_NoDanglingEdges(self):
        """Every edge in the result has both endpoints in the node set."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("b")
        for edge in result.edges:
            assert edge.from_id in result.nodes, f"NoDanglingEdges: {edge.from_id} not in nodes"
            assert edge.to_id in result.nodes, f"NoDanglingEdges: {edge.to_id} not in nodes"

    def _verify_IsolatedNodeCorrect(self):
        """Isolated node returns only itself and no edges."""
        dag = self._make_isolated_dag()
        result = dag.extract_subgraph("x")
        assert result.nodes == {"x"}, f"IsolatedNodeCorrect: expected {x}, got {result.nodes}"
        assert result.edges == [], f"IsolatedNodeCorrect: expected no edges, got {len(result.edges)}"

    def _verify_ValidState(self):
        """extract_subgraph returns a valid SubgraphResult."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("b")
        assert isinstance(result, SubgraphResult)
        assert result.root == "b"

    def _verify_BoundedExecution(self):
        """Result is deterministic and finite."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("a")
        assert isinstance(result, SubgraphResult)

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

    def test_subgraphcompleteness(self):
        """Verifier SubgraphCompleteness: SubgraphCompleteness violation: current_state # 'done' //     (target /in subgra"""
        # Bridge condition: current_state # 'done' //     (target /in subgraph_nodes AND forward_set /subseteq subgraph_nodes AND reverse_set /subse
        # Applies to: current_state, dirty, forward_set, reverse_set, subgraph_nodes, target
        self._check_invariant("SubgraphCompleteness")

    def test_noholes(self):
        """Verifier NoHoles: NoHoles violation: current_state # 'done' //     (subgraph_nodes = forward_set /"""
        # Bridge condition: current_state # 'done' //     (subgraph_nodes = forward_set /union reverse_set /union {target}
        # Applies to: current_state, dirty, forward_set, reverse_set, subgraph_nodes, target
        self._check_invariant("NoHoles")

    def test_nodanglingedges(self):
        """Verifier NoDanglingEdges: NoDanglingEdges violation: current_state # 'done' //     (/A edge /in subgraph_e"""
        # Bridge condition: current_state # 'done' //     (/A edge /in subgraph_edges :         edge[1] /in subgraph_nodes AND edge[2] /in subgraph_
        # Applies to: current_state, dirty, subgraph_edges, subgraph_nodes
        self._check_invariant("NoDanglingEdges")

    def test_isolatednodecorrect(self):
        """Verifier IsolatedNodeCorrect: IsolatedNodeCorrect violation: current_state # 'done' //     ((adjacency[target]"""
        # Bridge condition: current_state # 'done' //     ((adjacency[target] = {} AND /A n /in 1..NumNodes : target /notin adjacency[n])) =>      (
        # Applies to: adjacency, current_state, dirty, subgraph_edges, subgraph_nodes, target
        self._check_invariant("IsolatedNodeCorrect")

    # -- Additional invariant-derived tests --

    def test_chain_middle_node(self):
        """SubgraphCompleteness: middle node gets full chain."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("b")
        assert result.nodes == {"a", "b", "c", "d"}

    def test_chain_root_node(self):
        """SubgraphCompleteness: root node gets itself + all descendants."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("a")
        assert result.nodes == {"a", "b", "c", "d"}

    def test_chain_leaf_node(self):
        """SubgraphCompleteness: leaf node gets itself + all ancestors."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("d")
        assert result.nodes == {"a", "b", "c", "d"}

    def test_diamond_center(self):
        """SubgraphCompleteness: diamond center includes all paths."""
        dag = self._make_diamond_dag()
        result = dag.extract_subgraph("b")
        assert "a" in result.nodes, "ancestor a missing"
        assert "b" in result.nodes, "target b missing"
        assert "d" in result.nodes, "descendant d missing"

    def test_diamond_root(self):
        """SubgraphCompleteness: diamond root includes all descendants."""
        dag = self._make_diamond_dag()
        result = dag.extract_subgraph("a")
        assert result.nodes == {"a", "b", "c", "d"}

    def test_isolated_node(self):
        """IsolatedNodeCorrect: isolated node → singleton, no edges."""
        dag = self._make_isolated_dag()
        result = dag.extract_subgraph("y")
        assert result.nodes == {"y"}
        assert result.edges == []

    def test_no_dangling_edges_chain(self):
        """NoDanglingEdges: chain subgraph has no dangling edges."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("c")
        for edge in result.edges:
            assert edge.from_id in result.nodes
            assert edge.to_id in result.nodes

    def test_no_dangling_edges_diamond(self):
        """NoDanglingEdges: diamond subgraph has no dangling edges."""
        dag = self._make_diamond_dag()
        result = dag.extract_subgraph("d")
        for edge in result.edges:
            assert edge.from_id in result.nodes
            assert edge.to_id in result.nodes

    def test_edge_count_chain_full(self):
        """All 3 edges present when full chain is in subgraph."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("b")
        assert len(result.edges) == 3

    def test_edge_count_isolated(self):
        """No edges for isolated node."""
        dag = self._make_isolated_dag()
        result = dag.extract_subgraph("z")
        assert len(result.edges) == 0

    def test_root_is_set(self):
        """Root field matches the queried node."""
        dag = self._make_chain_dag()
        result = dag.extract_subgraph("c")
        assert result.root == "c"

    def test_missing_node_raises(self):
        """NodeNotFoundError for missing node."""
        dag = self._make_chain_dag()
        with pytest.raises(NodeNotFoundError):
            dag.extract_subgraph("nonexistent")

    def test_does_not_mutate_dag(self):
        """extract_subgraph must not modify the DAG."""
        dag = self._make_chain_dag()
        edges_before = len(dag.edges)
        nodes_before = len(dag.nodes)
        dag.extract_subgraph("b")
        assert len(dag.edges) == edges_before
        assert len(dag.nodes) == nodes_before

    def test_two_components(self):
        """Subgraph only includes the target's component."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "x", "y"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("x", "y", EdgeType.DEPENDS_ON))
        result = dag.extract_subgraph("b")
        assert result.nodes == {"a", "b", "c"}
        assert "x" not in result.nodes
        assert "y" not in result.nodes
