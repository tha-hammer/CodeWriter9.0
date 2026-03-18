"""Tests for RegistryDag.register_gwt() and register_requirement()."""

import pytest

from registry.dag import NodeNotFoundError, RegistryDag
from registry.types import EdgeType, Node, NodeKind


class TestRegisterGwt:
    def test_allocates_sequential_ids(self):
        dag = RegistryDag()
        id1 = dag.register_gwt("given1", "when1", "then1")
        id2 = dag.register_gwt("given2", "when2", "then2")
        assert id1 == "gwt-0001"
        assert id2 == "gwt-0002"

    def test_continues_from_existing_ids(self):
        """If DAG already has gwt-0023, next should be gwt-0024."""
        dag = RegistryDag()
        # Simulate existing self-hosting GWTs
        for i in range(1, 24):
            dag.add_node(Node.behavior(f"gwt-{i:04d}", f"b{i}", "g", "w", "t"))
        new_id = dag.register_gwt("given", "when", "then")
        assert new_id == "gwt-0024"

    def test_creates_behavior_node(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("a user exists", "they log in", "they see dashboard")
        node = dag.nodes[gwt_id]
        assert node.kind == NodeKind.BEHAVIOR
        assert node.given == "a user exists"
        assert node.when == "they log in"
        assert node.then == "they see dashboard"

    def test_wires_parent_requirement(self):
        dag = RegistryDag()
        req_id = dag.register_requirement("System needs auth")
        gwt_id = dag.register_gwt("user exists", "login", "dashboard", parent_req=req_id)
        edges = [e for e in dag.edges if e.from_id == req_id and e.to_id == gwt_id]
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.DECOMPOSES

    def test_missing_parent_raises(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.register_gwt("g", "w", "t", parent_req="req-9999")

    def test_auto_generates_name(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("given", "validation runs on submit", "errors shown")
        assert dag.nodes[gwt_id].name == "validation_runs_on_submit"

    def test_api_path_in_when_clause_sanitized(self):
        """Regression: '/' and ':' in API paths must not create directory separators."""
        dag = RegistryDag()
        gwt_id = dag.register_gwt(
            "given", "GET /api/v1/requisitions/:id is called", "then"
        )
        name = dag.nodes[gwt_id].name
        assert "/" not in name
        assert ":" not in name
        assert name == "get_api_v1_requisitions_id_is_called"

    def test_explicit_name(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("g", "w", "t", name="custom_name")
        assert dag.nodes[gwt_id].name == "custom_name"

    def test_save_load_preserves_registered_gwts(self, tmp_path):
        dag = RegistryDag()
        req_id = dag.register_requirement("Auth requirement")
        gwt_id = dag.register_gwt("user", "login", "dashboard", parent_req=req_id)
        dag.save(tmp_path / "dag.json")

        dag2 = RegistryDag.load(tmp_path / "dag.json")
        assert gwt_id in dag2.nodes
        assert dag2.nodes[gwt_id].given == "user"
        # Next ID should continue from where we left off
        next_id = dag2.register_gwt("g2", "w2", "t2")
        assert next_id == "gwt-0002"


class TestRegisterRequirement:
    def test_allocates_sequential_ids(self):
        dag = RegistryDag()
        id1 = dag.register_requirement("First requirement")
        id2 = dag.register_requirement("Second requirement")
        assert id1 == "req-0001"
        assert id2 == "req-0002"

    def test_continues_from_existing(self):
        dag = RegistryDag()
        for i in range(1, 8):
            dag.add_node(Node.requirement(f"req-{i:04d}", f"text{i}"))
        new_id = dag.register_requirement("New requirement")
        assert new_id == "req-0008"

    def test_creates_requirement_node(self):
        dag = RegistryDag()
        req_id = dag.register_requirement("System must handle auth")
        node = dag.nodes[req_id]
        assert node.kind == NodeKind.REQUIREMENT
        assert node.text == "System must handle auth"
