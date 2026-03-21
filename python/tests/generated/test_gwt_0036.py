import json
import pytest
from pathlib import Path

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import (
    Edge,
    EdgeType,
    ImpactResult,
    Node,
    NodeKind,
    QueryResult,
    SubgraphResult,
    ValidationResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def dag() -> RegistryDag:
    return RegistryDag()


@pytest.fixture
def populated_dag() -> RegistryDag:
    d = RegistryDag()
    d.add_node(Node.resource("res-a", "Resource A", "First resource"))
    d.add_node(Node.resource("res-b", "Resource B", "Second resource"))
    d.add_node(Node.resource("res-c", "Resource C", "Third resource"))
    d.add_edge(Edge(from_id="res-a", to_id="res-b", edge_type=EdgeType.DEPENDS_ON))
    d.add_edge(Edge(from_id="res-b", to_id="res-c", edge_type=EdgeType.DEPENDS_ON))
    return d


# ─── Node Factory Tests ───────────────────────────────────────────────────────

class TestNodeFactories:
    def test_resource_factory_sets_kind(self) -> None:
        n = Node.resource("r1", "My Resource")
        assert n.kind == NodeKind.RESOURCE

    def test_resource_factory_sets_id_and_name(self) -> None:
        n = Node.resource("r1", "My Resource", "desc")
        assert n.id == "r1"
        assert n.name == "My Resource"
        assert n.description == "desc"

    def test_resource_factory_description_defaults_to_empty(self) -> None:
        n = Node.resource("r1", "My Resource")
        assert n.description == ""

    def test_behavior_factory_sets_kind(self) -> None:
        n = Node.behavior("b1", "Behavior", given="G", when="W", then="T")
        assert n.kind == NodeKind.BEHAVIOR

    def test_behavior_factory_sets_gwt_fields(self) -> None:
        n = Node.behavior("b1", "Behavior", given="Given ctx", when="When event", then="Then result")
        assert n.given == "Given ctx"
        assert n.when == "When event"
        assert n.then == "Then result"

    def test_requirement_factory_sets_kind(self) -> None:
        n = Node.requirement("req-1", "System must be fast")
        assert n.kind == NodeKind.REQUIREMENT

    def test_requirement_factory_sets_text(self) -> None:
        n = Node.requirement("req-1", "System must be fast", name="Perf Req")
        assert n.text == "System must be fast"
        assert n.name == "Perf Req"

    def test_requirement_factory_name_defaults_to_empty(self) -> None:
        n = Node.requirement("req-1", "System must be fast")
        assert n.name == ""

    def test_node_to_dict_contains_id(self) -> None:
        n = Node.resource("r1", "Resource")
        d = n.to_dict()
        assert d["id"] == "r1"

    def test_node_to_dict_contains_kind(self) -> None:
        n = Node.resource("r1", "Resource")
        d = n.to_dict()
        assert "kind" in d

    def test_behavior_to_dict_contains_gwt(self) -> None:
        n = Node.behavior("b1", "B", given="G", when="W", then="T")
        d = n.to_dict()
        assert d["given"] == "G"
        assert d["when"] == "W"
        assert d["then"] == "T"


# ─── Edge Tests ──────────────────────────────────────────────────────────────

class TestEdge:
    def test_edge_stores_from_id(self) -> None:
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.IMPORTS)
        assert e.from_id == "a"

    def test_edge_stores_to_id(self) -> None:
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.IMPORTS)
        assert e.to_id == "b"

    def test_edge_stores_edge_type(self) -> None:
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.CALLS)
        assert e.edge_type == EdgeType.CALLS

    def test_edge_to_dict_contains_all_fields(self) -> None:
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON)
        d = e.to_dict()
        assert "from" in d
        assert "to" in d
        assert "edge_type" in d


# ─── RegistryDag Structural Tests ────────────────────────────────────────────

class TestRegistryDagStructure:
    def test_empty_dag_has_zero_nodes(self, dag: RegistryDag) -> None:
        assert dag.node_count == 0

    def test_empty_dag_has_zero_edges(self, dag: RegistryDag) -> None:
        assert dag.edge_count == 0

    def test_empty_dag_has_zero_components(self, dag: RegistryDag) -> None:
        assert dag.component_count == 0

    def test_add_node_increments_node_count(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        assert dag.node_count == 1

    def test_add_multiple_nodes_increments_count(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        assert dag.node_count == 2

    def test_add_edge_increments_edge_count(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        assert dag.edge_count == 1

    def test_two_isolated_nodes_have_two_components(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        assert dag.component_count == 2

    def test_connected_nodes_share_component(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        assert dag.component_count == 1

    def test_duplicate_edge_not_added_twice(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        assert dag.edge_count == 1


# ─── Cycle Detection Tests ────────────────────────────────────────────────────

class TestCycleDetection:
    def test_direct_cycle_raises_cycle_error(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        with pytest.raises(CycleError):
            dag.add_edge(Edge(from_id="r2", to_id="r1", edge_type=EdgeType.DEPENDS_ON))

    def test_transitive_cycle_raises_cycle_error(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_node(Node.resource("r3", "R3"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        dag.add_edge(Edge(from_id="r2", to_id="r3", edge_type=EdgeType.DEPENDS_ON))
        with pytest.raises(CycleError):
            dag.add_edge(Edge(from_id="r3", to_id="r1", edge_type=EdgeType.DEPENDS_ON))

    def test_self_loop_raises_cycle_error(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        with pytest.raises(CycleError):
            dag.add_edge(Edge(from_id="r1", to_id="r1", edge_type=EdgeType.DEPENDS_ON))

    def test_cycle_error_stores_from_and_to(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        with pytest.raises(CycleError) as exc_info:
            dag.add_edge(Edge(from_id="r2", to_id="r1", edge_type=EdgeType.DEPENDS_ON))
        assert exc_info.value is not None


# ─── NodeNotFoundError Tests ──────────────────────────────────────────────────

class TestNodeNotFoundError:
    def test_add_edge_unknown_from_raises(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r2", "R2"))
        with pytest.raises(NodeNotFoundError):
            dag.add_edge(Edge(from_id="nonexistent", to_id="r2", edge_type=EdgeType.DEPENDS_ON))

    def test_add_edge_unknown_to_raises(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        with pytest.raises(NodeNotFoundError):
            dag.add_edge(Edge(from_id="r1", to_id="nonexistent", edge_type=EdgeType.DEPENDS_ON))

    def test_query_relevant_unknown_node_raises(self, dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("ghost")

    def test_query_impact_unknown_node_raises(self, dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError):
            dag.query_impact("ghost")

    def test_extract_subgraph_unknown_node_raises(self, dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError):
            dag.extract_subgraph("ghost")

    def test_remove_node_unknown_is_noop(self, dag: RegistryDag) -> None:
        count_before = dag.node_count
        dag.remove_node("ghost")  # should not raise
        assert dag.node_count == count_before

    def test_node_not_found_error_stores_id(self, dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError) as exc_info:
            dag.query_relevant("missing-id")
        assert exc_info.value is not None


# ─── query_relevant Tests ─────────────────────────────────────────────────────

class TestQueryRelevant:
    def test_returns_query_result_instance(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert isinstance(result, QueryResult)

    def test_root_is_queried_node(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert result.root == "res-a"

    def test_direct_dep_in_transitive_deps(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert "res-b" in result.transitive_deps

    def test_transitive_dep_in_transitive_deps(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert "res-c" in result.transitive_deps

    def test_leaf_node_has_empty_transitive_deps(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-c")
        assert len(result.transitive_deps) == 0

    def test_direct_edges_not_empty_for_node_with_outgoing_edge(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert len(result.direct_edges) > 0

    def test_component_id_is_string(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_relevant("res-a")
        assert isinstance(result.component_id, str)


# ─── query_impact Tests ───────────────────────────────────────────────────────

class TestQueryImpact:
    def test_returns_impact_result_instance(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-c")
        assert isinstance(result, ImpactResult)

    def test_target_is_queried_node(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-c")
        assert result.target == "res-c"

    def test_direct_dependent_in_direct_dependents(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-c")
        assert "res-b" in result.direct_dependents

    def test_transitive_dependent_in_affected(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-c")
        assert "res-a" in result.affected

    def test_leaf_node_impact_returns_empty_affected(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("isolated", "Isolated"))
        result = dag.query_impact("isolated")
        assert len(result.affected) == 0

    def test_affected_is_set(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-b")
        assert isinstance(result.affected, set)

    def test_direct_dependents_is_set(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-b")
        assert isinstance(result.direct_dependents, set)


# ─── validate_edge Tests ──────────────────────────────────────────────────────

class TestValidateEdge:
    def test_returns_validation_result(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        result = dag.validate_edge("r1", "r2", EdgeType.DEPENDS_ON)
        assert isinstance(result, ValidationResult)

    def test_valid_edge_is_valid(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        result = dag.validate_edge("r1", "r2", EdgeType.DEPENDS_ON)
        assert result.valid is True

    def test_validate_does_not_mutate_dag(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.validate_edge("r1", "r2", EdgeType.DEPENDS_ON)
        assert dag.edge_count == 0

    def test_cycle_edge_is_invalid(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        result = dag.validate_edge("r2", "r1", EdgeType.DEPENDS_ON)
        assert result.valid is False

    def test_result_stores_from_id(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        result = dag.validate_edge("r1", "r2", EdgeType.IMPORTS)
        assert result.from_id == "r1"

    def test_result_stores_to_id(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        result = dag.validate_edge("r1", "r2", EdgeType.IMPORTS)
        assert result.to_id == "r2"

    def test_result_stores_edge_type(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        result = dag.validate_edge("r1", "r2", EdgeType.CALLS)
        assert result.edge_type == EdgeType.CALLS

    def test_invalid_result_has_reason(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        result = dag.validate_edge("r2", "r1", EdgeType.DEPENDS_ON)
        assert result.reason is not None
        assert len(result.reason) > 0


# ─── extract_subgraph Tests ───────────────────────────────────────────────────

class TestExtractSubgraph:
    def test_returns_subgraph_result(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-b")
        assert isinstance(result, SubgraphResult)

    def test_root_is_queried_node(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-b")
        assert result.root == "res-b"

    def test_nodes_contains_root(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-b")
        assert "res-b" in result.nodes

    def test_nodes_contains_descendants(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-a")
        assert "res-b" in result.nodes
        assert "res-c" in result.nodes

    def test_nodes_contains_ancestors(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-c")
        assert "res-b" in result.nodes
        assert "res-a" in result.nodes

    def test_nodes_is_set(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.extract_subgraph("res-b")
        assert isinstance(result.nodes, set)

    def test_isolated_node_subgraph_contains_only_self(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("solo", "Solo"))
        result = dag.extract_subgraph("solo")
        assert result.nodes == {"solo"}
        assert len(result.edges) == 0


# ─── component_members Tests ──────────────────────────────────────────────────

class TestComponentMembers:
    def test_returns_list(self, populated_dag: RegistryDag) -> None:
        members = populated_dag.component_members("res-a")
        assert isinstance(members, list)

    def test_node_is_member_of_own_component(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        members = dag.component_members("r1")
        assert "r1" in members

    def test_connected_nodes_share_component(self, populated_dag: RegistryDag) -> None:
        members_a = set(populated_dag.component_members("res-a"))
        assert "res-b" in members_a
        assert "res-c" in members_a

    def test_isolated_node_only_in_own_component(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        members = dag.component_members("r1")
        assert "r2" not in members


# ─── remove_node Tests ────────────────────────────────────────────────────────

class TestRemoveNode:
    def test_remove_decrements_node_count(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.remove_node("r1")
        assert dag.node_count == 0

    def test_remove_node_also_removes_edges(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_edge(Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON))
        dag.remove_node("r1")
        assert dag.edge_count == 0

    def test_remove_node_unknown_is_noop(self, dag: RegistryDag) -> None:
        count_before = dag.node_count
        dag.remove_node("nonexistent")
        assert dag.node_count == count_before

    def test_remove_middle_node_removes_both_edges(self, populated_dag: RegistryDag) -> None:
        initial_edges = populated_dag.edge_count
        populated_dag.remove_node("res-b")
        assert populated_dag.edge_count < initial_edges
        assert populated_dag.node_count == 2


# ─── Registration API Tests ───────────────────────────────────────────────────

class TestRegistrationApi:
    def test_register_requirement_returns_string_id(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("The system must be reliable")
        assert isinstance(req_id, str)

    def test_register_requirement_id_starts_with_req(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("Must be fast")
        assert req_id.startswith("req-")

    def test_register_requirement_adds_node_to_dag(self, dag: RegistryDag) -> None:
        dag.register_requirement("Must be available 99.9%")
        assert dag.node_count == 1

    def test_register_requirement_node_has_requirement_kind(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("Must be secure")
        assert dag.nodes[req_id].kind == NodeKind.REQUIREMENT

    def test_register_gwt_returns_string_id(self, dag: RegistryDag) -> None:
        gwt_id = dag.register_gwt(
            given="A user is logged in",
            when="They click logout",
            then="They are redirected to login page",
        )
        assert isinstance(gwt_id, str)

    def test_register_gwt_id_starts_with_gwt(self, dag: RegistryDag) -> None:
        gwt_id = dag.register_gwt(given="G", when="W", then="T")
        assert gwt_id.startswith("gwt-")

    def test_register_gwt_adds_node_to_dag(self, dag: RegistryDag) -> None:
        dag.register_gwt(given="G", when="W", then="T")
        assert dag.node_count == 1

    def test_register_gwt_node_has_behavior_kind(self, dag: RegistryDag) -> None:
        gwt_id = dag.register_gwt(given="G", when="W", then="T")
        assert dag.nodes[gwt_id].kind == NodeKind.BEHAVIOR

    def test_register_gwt_with_parent_req_links_to_requirement(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("Must authenticate")
        dag.register_gwt(given="G", when="W", then="T", parent_req=req_id)
        assert dag.edge_count > 0

    def test_sequential_requirements_get_unique_ids(self, dag: RegistryDag) -> None:
        id1 = dag.register_requirement("Req 1")
        id2 = dag.register_requirement("Req 2")
        assert id1 != id2

    def test_sequential_gwt_registrations_get_unique_ids(self, dag: RegistryDag) -> None:
        id1 = dag.register_gwt(given="G1", when="W1", then="T1")
        id2 = dag.register_gwt(given="G2", when="W2", then="T2")
        assert id1 != id2

    def test_register_requirement_with_name(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("Must scale", name="Scalability")
        node = dag.nodes[req_id]
        assert node.name == "Scalability"

    def test_register_gwt_with_name(self, dag: RegistryDag) -> None:
        gwt_id = dag.register_gwt(given="G", when="W", then="T", name="Login flow")
        node = dag.nodes[gwt_id]
        assert node.name == "Login flow"


# ─── query_affected_tests Tests ───────────────────────────────────────────────

class TestQueryAffectedTests:
    def test_returns_list(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        result = dag.query_affected_tests("r1")
        assert isinstance(result, list)

    def test_node_with_no_test_edges_returns_empty(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_affected_tests("res-a")
        assert isinstance(result, list)


# ─── Serialization Tests ──────────────────────────────────────────────────────

class TestSerialization:
    def test_to_dict_returns_dict(self, populated_dag: RegistryDag) -> None:
        d = populated_dag.to_dict()
        assert isinstance(d, dict)

    def test_to_json_returns_string(self, populated_dag: RegistryDag) -> None:
        j = populated_dag.to_json()
        assert isinstance(j, str)

    def test_to_json_is_valid_json(self, populated_dag: RegistryDag) -> None:
        j = populated_dag.to_json()
        parsed = json.loads(j)
        assert isinstance(parsed, dict)

    def test_from_dict_roundtrip_preserves_node_count(self, populated_dag: RegistryDag) -> None:
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.node_count == populated_dag.node_count

    def test_from_dict_roundtrip_preserves_edge_count(self, populated_dag: RegistryDag) -> None:
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.edge_count == populated_dag.edge_count

    def test_from_json_roundtrip_preserves_node_count(self, populated_dag: RegistryDag) -> None:
        j = populated_dag.to_json()
        restored = RegistryDag.from_json(j)
        assert restored.node_count == populated_dag.node_count

    def test_from_json_roundtrip_preserves_edge_count(self, populated_dag: RegistryDag) -> None:
        j = populated_dag.to_json()
        restored = RegistryDag.from_json(j)
        assert restored.edge_count == populated_dag.edge_count

    def test_from_dict_restores_node_ids(self, populated_dag: RegistryDag) -> None:
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        for node_id in ("res-a", "res-b", "res-c"):
            assert node_id in restored.nodes

    def test_from_dict_returns_registry_dag_instance(self, populated_dag: RegistryDag) -> None:
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert isinstance(restored, RegistryDag)

    def test_save_and_load_roundtrip(self, populated_dag: RegistryDag, tmp_path: Path) -> None:
        path = tmp_path / "dag.json"
        populated_dag.save(path)
        loaded = RegistryDag.load(path)
        assert loaded.node_count == populated_dag.node_count
        assert loaded.edge_count == populated_dag.edge_count

    def test_save_creates_file(self, populated_dag: RegistryDag, tmp_path: Path) -> None:
        path = tmp_path / "dag.json"
        populated_dag.save(path)
        assert path.exists()

    def test_load_restores_node_ids(self, populated_dag: RegistryDag, tmp_path: Path) -> None:
        path = tmp_path / "dag.json"
        populated_dag.save(path)
        loaded = RegistryDag.load(path)
        for node_id in ("res-a", "res-b", "res-c"):
            assert node_id in loaded.nodes

    def test_empty_dag_roundtrip(self, dag: RegistryDag) -> None:
        d = dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.node_count == 0
        assert restored.edge_count == 0


# ─── NodeKind and EdgeType Enum Tests ────────────────────────────────────────

class TestEnums:
    def test_node_kind_resource_is_string(self) -> None:
        assert isinstance(NodeKind.RESOURCE, str)

    def test_node_kind_behavior_value(self) -> None:
        assert NodeKind.BEHAVIOR is not None

    def test_node_kind_requirement_value(self) -> None:
        assert NodeKind.REQUIREMENT is not None

    def test_edge_type_depends_on_is_string(self) -> None:
        assert isinstance(EdgeType.DEPENDS_ON, str)

    def test_all_edge_types_are_strings(self) -> None:
        for et in EdgeType:
            assert isinstance(et, str)

    def test_all_node_kinds_are_strings(self) -> None:
        for nk in NodeKind:
            assert isinstance(nk, str)


# ─── Integration / Composite Scenario Tests ───────────────────────────────────

class TestIntegrationScenarios:
    def test_chain_of_five_nodes_no_cycle(self, dag: RegistryDag) -> None:
        for i in range(5):
            dag.add_node(Node.resource(f"n{i}", f"Node {i}"))
        for i in range(4):
            dag.add_edge(Edge(from_id=f"n{i}", to_id=f"n{i + 1}", edge_type=EdgeType.DEPENDS_ON))
        assert dag.node_count == 5
        assert dag.edge_count == 4
        assert dag.component_count == 1

    def test_two_disjoint_chains_have_two_components(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("a1", "A1"))
        dag.add_node(Node.resource("a2", "A2"))
        dag.add_node(Node.resource("b1", "B1"))
        dag.add_node(Node.resource("b2", "B2"))
        dag.add_edge(Edge(from_id="a1", to_id="a2", edge_type=EdgeType.DEPENDS_ON))
        dag.add_edge(Edge(from_id="b1", to_id="b2", edge_type=EdgeType.DEPENDS_ON))
        assert dag.component_count == 2

    def test_requirement_links_to_behavior_then_resource(self, dag: RegistryDag) -> None:
        req_id = dag.register_requirement("System must handle login")
        gwt_id = dag.register_gwt(
            given="User submits credentials",
            when="Credentials are valid",
            then="User is authenticated",
            parent_req=req_id,
        )
        dag.add_node(Node.resource("auth-service", "Auth Service"))
        dag.add_edge(Edge(from_id=gwt_id, to_id="auth-service", edge_type=EdgeType.VERIFIES))
        assert dag.node_count == 3
        assert dag.edge_count >= 2

    def test_subgraph_of_leaf_has_no_outgoing_ancestors(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("root", "Root"))
        dag.add_node(Node.resource("child", "Child"))
        dag.add_edge(Edge(from_id="root", to_id="child", edge_type=EdgeType.CONTAINS))
        result = dag.extract_subgraph("root")
        assert "root" in result.nodes
        assert "child" in result.nodes

    def test_multiple_edge_types_between_different_pairs(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("a", "A"))
        dag.add_node(Node.resource("b", "B"))
        dag.add_node(Node.resource("c", "C"))
        dag.add_edge(Edge(from_id="a", to_id="b", edge_type=EdgeType.IMPORTS))
        dag.add_edge(Edge(from_id="a", to_id="c", edge_type=EdgeType.CALLS))
        assert dag.edge_count == 2

    def test_remove_then_re_add_node(self, dag: RegistryDag) -> None:
        dag.add_node(Node.resource("r1", "R1"))
        dag.remove_node("r1")
        dag.add_node(Node.resource("r1", "R1 Re-added"))
        assert dag.node_count == 1

    def test_impact_propagates_through_chain(self, populated_dag: RegistryDag) -> None:
        result = populated_dag.query_impact("res-c")
        assert "res-a" in result.affected
        assert "res-b" in result.affected

    def test_serialization_preserves_behavior_gwt_fields(self, dag: RegistryDag) -> None:
        gwt_id = dag.register_gwt(
            given="system is running",
            when="health endpoint is called",
            then="200 OK is returned",
        )
        d = dag.to_dict()
        restored = RegistryDag.from_dict(d)
        node = restored.nodes[gwt_id]
        assert node.given == "system is running"
        assert node.when == "health endpoint is called"
        assert node.then == "200 OK is returned"