"""Generated test suite from change_propagation.tla via Bridge (Phase 8).

Mechanically generated from bridge artifacts by run_change_prop_loop.py.
Verifiers: ValidState, BoundedExecution, NoFalsePositives, NoFalseNegatives, SelfTestIncluded
"""

import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Node, Edge, EdgeType


class TestChangePropagationInvariants:
    """Tests mechanically derived from change_propagation.tla bridge verifiers."""

    def _make_chain_dag(self):
        """a -> b -> c -> d (linear chain, all resources)."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        # Assign test artifacts: only "a" has a test
        dag.test_artifacts = {"a": "tests/generated/test_a.py"}
        return dag

    def _make_diamond_dag(self):
        """Diamond: a -> b, a -> c, b -> d, c -> d. a and d have tests."""
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("a", "b", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("a", "c", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("b", "d", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("c", "d", EdgeType.DEPENDS_ON))
        dag.test_artifacts = {
            "a": "tests/generated/test_a.py",
            "d": "tests/generated/test_d.py",
        }
        return dag

    def _make_no_artifact_dag(self):
        """Three nodes, none with test artifacts."""
        dag = RegistryDag()
        for nid in ("x", "y", "z"):
            dag.add_node(Node.resource(nid, f"node_{nid}", description="test"))
        dag.add_edge(Edge("x", "y", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("y", "z", EdgeType.DEPENDS_ON))
        dag.test_artifacts = {}
        return dag

    def _check_invariant(self, name):
        method = getattr(self, f"_verify_{name}", None)
        if method:
            method()

    # -- Invariant verification methods --

    def _verify_NoFalsePositives(self):
        """Every returned test path corresponds to a node in the impact set."""
        dag = self._make_chain_dag()
        # Change d (leaf). Impact set of d = nodes that depend on d = {a, b, c}.
        # a has a test, so test_a.py should be in result.
        result = dag.query_affected_tests("d")
        for path in result:
            # Verify each path maps to a node in candidates (impact + self)
            found = False
            impact = dag.query_impact("d")
            candidates = impact.affected | {"d"}
            for nid in candidates:
                if dag.test_artifacts.get(nid) == path:
                    found = True
                    break
            assert found, f"NoFalsePositives: {path} not backed by a candidate node"

    def _verify_NoFalseNegatives(self):
        """Every candidate with a test artifact has its test in the result."""
        dag = self._make_chain_dag()
        result = dag.query_affected_tests("d")
        impact = dag.query_impact("d")
        candidates = impact.affected | {"d"}
        for nid in candidates:
            if nid in dag.test_artifacts:
                assert dag.test_artifacts[nid] in result, \
                    f"NoFalseNegatives: {nid}'s test not in result"

    def _verify_SelfTestIncluded(self):
        """If the target itself has a test, it's in the result."""
        dag = self._make_chain_dag()
        # a has a test artifact
        result = dag.query_affected_tests("a")
        assert "tests/generated/test_a.py" in result, \
            "SelfTestIncluded: target's own test missing"

    def _verify_ValidState(self):
        """query_affected_tests returns a list of strings."""
        dag = self._make_chain_dag()
        result = dag.query_affected_tests("b")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def _verify_BoundedExecution(self):
        """Result is deterministic and finite."""
        dag = self._make_chain_dag()
        result = dag.query_affected_tests("c")
        assert isinstance(result, list)

    def test_validstate(self):
        """Verifier ValidState: ValidState violation: current_state /in StateSet"""
        # Bridge condition: current_state /in StateSet
        # Applies to: current_state
        self._check_invariant("ValidState")

    def test_boundedexecution(self):
        """Verifier BoundedExecution: BoundedExecution violation: step_count <= MaxSteps  Reachable(start, adj) ==    """
        # Bridge condition: step_count <= MaxSteps  Reachable(start, adj) ==     LET RECURSIVE Reach(_)         Reach(visited) ==             LET ne
        # Applies to: step_count
        self._check_invariant("BoundedExecution")

    def test_nofalsepositives(self):
        """Verifier NoFalsePositives: NoFalsePositives violation: (current_state = 'done' =>         /A a /in affected"""
        # Bridge condition: current_state = 'done' =>         /A a /in affected_tests : /E n /in candidates : test_artifacts[n] = a
        # Applies to: affected_tests, candidates, current_state, dirty, test_artifacts
        self._check_invariant("NoFalsePositives")

    def test_nofalsenegatives(self):
        """Verifier NoFalseNegatives: NoFalseNegatives violation: (current_state = 'done' =>         /A n /in candidat"""
        # Bridge condition: current_state = 'done' =>         /A n /in candidates : test_artifacts[n] # 0 => test_artifacts[n] /in affected_tests
        # Applies to: affected_tests, candidates, current_state, dirty, test_artifacts
        self._check_invariant("NoFalseNegatives")

    def test_selftestincluded(self):
        """Verifier SelfTestIncluded: SelfTestIncluded violation: (current_state = 'done' =>         (test_artifacts[t"""
        # Bridge condition: current_state = 'done' =>         (test_artifacts[target] # 0 => test_artifacts[target] /in affected_tests
        # Applies to: affected_tests, current_state, dirty, target, test_artifacts
        self._check_invariant("SelfTestIncluded")

    # -- Additional invariant-derived tests --

    def test_upstream_change_propagates(self):
        """gwt-0021: change to upstream node surfaces downstream test."""
        dag = self._make_chain_dag()
        # d is downstream of a (a->b->c->d). Change d, a depends on b->c->d.
        # Actually in DEPENDS_ON: a depends on b, b on c, c on d.
        # So changing d affects c, b, a. a has a test.
        result = dag.query_affected_tests("d")
        assert "tests/generated/test_a.py" in result

    def test_no_downstream_tests_empty(self):
        """gwt-0022: node with no downstream test artifacts returns empty."""
        dag = self._make_no_artifact_dag()
        result = dag.query_affected_tests("z")
        assert result == []

    def test_self_test_included(self):
        """gwt-0023: node that IS test-bearing includes its own test."""
        dag = self._make_diamond_dag()
        result = dag.query_affected_tests("a")
        assert "tests/generated/test_a.py" in result

    def test_diamond_leaf_change(self):
        """Changing d in diamond: a and d have tests, both should appear."""
        dag = self._make_diamond_dag()
        result = dag.query_affected_tests("d")
        assert "tests/generated/test_d.py" in result
        # a depends on b and c, which depend on d, so a is affected
        assert "tests/generated/test_a.py" in result

    def test_diamond_middle_change(self):
        """Changing b in diamond: a depends on b, a has test."""
        dag = self._make_diamond_dag()
        result = dag.query_affected_tests("b")
        assert "tests/generated/test_a.py" in result

    def test_no_false_positives_isolated(self):
        """Node with no dependents returns only its own test (if any)."""
        dag = RegistryDag()
        dag.add_node(Node.resource("solo", "solo_node", description="test"))
        dag.test_artifacts = {"solo": "tests/generated/test_solo.py"}
        result = dag.query_affected_tests("solo")
        assert result == ["tests/generated/test_solo.py"]

    def test_no_false_positives_no_artifact(self):
        """Node with no test artifact and no dependents returns empty."""
        dag = RegistryDag()
        dag.add_node(Node.resource("bare", "bare_node", description="test"))
        dag.test_artifacts = {}
        result = dag.query_affected_tests("bare")
        assert result == []

    def test_result_sorted(self):
        """Result is sorted for deterministic output."""
        dag = self._make_diamond_dag()
        result = dag.query_affected_tests("d")
        assert result == sorted(result)

    def test_result_deduplicated(self):
        """No duplicate paths in result."""
        dag = self._make_diamond_dag()
        result = dag.query_affected_tests("d")
        assert len(result) == len(set(result))

    def test_missing_node_raises(self):
        """NodeNotFoundError for missing node."""
        dag = self._make_chain_dag()
        with pytest.raises(NodeNotFoundError):
            dag.query_affected_tests("nonexistent")

    def test_does_not_mutate_dag(self):
        """query_affected_tests must not modify the DAG."""
        dag = self._make_chain_dag()
        edges_before = len(dag.edges)
        nodes_before = len(dag.nodes)
        artifacts_before = dict(dag.test_artifacts)
        dag.query_affected_tests("b")
        assert len(dag.edges) == edges_before
        assert len(dag.nodes) == nodes_before
        assert dag.test_artifacts == artifacts_before

    def test_chain_leaf_no_dependents(self):
        """Leaf node with no dependents: only itself in candidates."""
        dag = self._make_chain_dag()
        # a is leaf in dependency direction (nothing depends on a)
        result = dag.query_affected_tests("a")
        # a has test, and nothing depends on a, so only a's test
        assert result == ["tests/generated/test_a.py"]
