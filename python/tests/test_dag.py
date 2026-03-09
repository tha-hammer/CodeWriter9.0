"""Tests for the registry DAG."""

import pytest

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import Edge, EdgeType, Node


def make_node(nid: str) -> Node:
    return Node.resource(nid, nid, f"Test node {nid}")


class TestDagBasics:
    def test_add_nodes_and_edges(self):
        dag = RegistryDag()
        dag.add_node(make_node("db-0001"))
        dag.add_node(make_node("db-0002"))
        dag.add_edge(Edge("db-0001", "db-0002", EdgeType.CALLS))

        assert dag.node_count == 2
        assert dag.edge_count == 1

    def test_node_not_found_on_edge(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))

        with pytest.raises(NodeNotFoundError):
            dag.add_edge(Edge("a", "nonexistent", EdgeType.CALLS))

    def test_duplicate_edge_idempotent(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        assert dag.edge_count == 1


class TestClosure:
    def test_closure_updates_on_edge_add(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_node(make_node("c"))

        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("b", "c", EdgeType.CALLS))

        assert "b" in dag.closure["a"]
        assert "c" in dag.closure["a"]
        assert "c" in dag.closure["b"]
        assert "a" not in dag.closure["b"]
        assert len(dag.closure["c"]) == 0

    def test_closure_diamond(self):
        dag = RegistryDag()
        for n in ("a", "b", "c", "d"):
            dag.add_node(make_node(n))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("a", "c", EdgeType.CALLS))
        dag.add_edge(Edge("b", "d", EdgeType.CALLS))
        dag.add_edge(Edge("c", "d", EdgeType.CALLS))

        assert dag.closure["a"] == {"b", "c", "d"}
        assert dag.closure["b"] == {"d"}
        assert dag.closure["c"] == {"d"}


class TestCycleDetection:
    def test_cycle_rejection(self):
        dag = RegistryDag()
        for n in ("a", "b", "c"):
            dag.add_node(make_node(n))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("b", "c", EdgeType.CALLS))

        with pytest.raises(CycleError) as exc_info:
            dag.add_edge(Edge("c", "a", EdgeType.CALLS))
        assert exc_info.value.from_id == "c"
        assert exc_info.value.to_id == "a"

    def test_self_loop_rejection(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))

        with pytest.raises(CycleError):
            dag.add_edge(Edge("a", "a", EdgeType.CALLS))


class TestComponents:
    def test_separate_components(self):
        dag = RegistryDag()
        for n in ("a", "b", "c", "d"):
            dag.add_node(make_node(n))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("c", "d", EdgeType.CALLS))

        comp_a = dag.component_members("a")
        comp_c = dag.component_members("c")

        assert "a" in comp_a and "b" in comp_a
        assert "c" not in comp_a
        assert "c" in comp_c and "d" in comp_c

    def test_component_merging(self):
        dag = RegistryDag()
        for n in ("a", "b", "c", "d"):
            dag.add_node(make_node(n))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("c", "d", EdgeType.CALLS))

        before = dag.component_count

        dag.add_edge(Edge("b", "c", EdgeType.CALLS))

        comp_a = dag.component_members("a")
        assert "d" in comp_a
        assert dag.component_count < before


class TestQueryRelevant:
    def test_query_returns_transitive_deps(self):
        dag = RegistryDag()
        for n in ("api-0001", "db-0001", "db-0002", "cfg-0001"):
            dag.add_node(make_node(n))

        dag.add_edge(Edge("api-0001", "db-0001", EdgeType.HANDLES))
        dag.add_edge(Edge("db-0001", "db-0002", EdgeType.CALLS))
        dag.add_edge(Edge("db-0001", "cfg-0001", EdgeType.IMPORTS))

        result = dag.query_relevant("api-0001")
        assert result.root == "api-0001"
        assert set(result.transitive_deps) == {"db-0001", "db-0002", "cfg-0001"}
        assert len(result.direct_edges) == 1

    def test_query_nonexistent_node(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("nonexistent")

    def test_query_includes_component(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))

        result = dag.query_relevant("a")
        assert result.component_id is not None


class TestSerialization:
    def test_json_roundtrip(self):
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))

        json_str = dag.to_json()
        restored = RegistryDag.from_json(json_str)

        assert restored.node_count == 2
        assert restored.edge_count == 1
        assert "b" in restored.closure["a"]

    def test_file_roundtrip(self, tmp_path):
        dag = RegistryDag()
        dag.add_node(make_node("x"))
        dag.add_node(make_node("y"))
        dag.add_edge(Edge("x", "y", EdgeType.IMPORTS))

        path = tmp_path / "registry.json"
        dag.save(path)

        restored = RegistryDag.load(path)
        assert restored.node_count == 2
        assert restored.edge_count == 1
