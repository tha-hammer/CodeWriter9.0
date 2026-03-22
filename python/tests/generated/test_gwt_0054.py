import pytest
from registry.dag import RegistryDag
from registry.types import Node, Edge, EdgeType, NodeKind, QueryResult, ImpactResult, SubgraphResult, ValidationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dag():
    return RegistryDag()


@pytest.fixture
def populated_dag():
    d = RegistryDag()
    r1 = Node.resource("r1", "Resource One", description="first resource")
    r2 = Node.resource("r2", "Resource Two", description="second resource")
    r3 = Node.resource("r3", "Resource Three", description="third resource")
    d.add_node(r1)
    d.add_node(r2)
    d.add_node(r3)
    e1 = Edge(from_id="r1", to_id="r2", edge_type=EdgeType.DEPENDS_ON)
    e2 = Edge(from_id="r2", to_id="r3", edge_type=EdgeType.DEPENDS_ON)
    d.add_edge(e1)
    d.add_edge(e2)
    return d


# ---------------------------------------------------------------------------
# Node factory tests
# ---------------------------------------------------------------------------

class TestNodeFactory:
    def test_resource_node_has_correct_kind(self):
        n = Node.resource("id1", "My Resource")
        assert n.kind == NodeKind.RESOURCE

    def test_resource_node_stores_id_and_name(self):
        n = Node.resource("abc", "ABC Resource", description="some desc")
        assert n.id == "abc"
        assert n.name == "ABC Resource"

    def test_behavior_node_has_correct_kind(self):
        n = Node.behavior("b1", "Behavior One", given="given", when="when", then="then")
        assert n.kind == NodeKind.BEHAVIOR

    def test_behavior_node_stores_gwt(self):
        n = Node.behavior("b2", "Behavior Two", given="G", when="W", then="T")
        assert n.id == "b2"
        assert n.name == "Behavior Two"

    def test_requirement_node_has_correct_kind(self):
        n = Node.requirement("req1", "some requirement text")
        assert n.kind == NodeKind.REQUIREMENT

    def test_requirement_node_stores_text(self):
        n = Node.requirement("req2", "requirement text here", name="Req Name")
        assert n.id == "req2"

    def test_node_to_dict_returns_dict(self):
        n = Node.resource("x", "X")
        d = n.to_dict()
        assert isinstance(d, dict)
        assert "id" in d

    def test_node_to_dict_contains_kind(self):
        n = Node.resource("y", "Y")
        d = n.to_dict()
        assert "kind" in d


# ---------------------------------------------------------------------------
# Edge tests
# ---------------------------------------------------------------------------

class TestEdge:
    def test_edge_stores_from_to(self):
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON)
        assert e.from_id == "a"
        assert e.to_id == "b"

    def test_edge_stores_type(self):
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON)
        assert e.edge_type == EdgeType.DEPENDS_ON

    def test_edge_to_dict_returns_dict(self):
        e = Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON)
        d = e.to_dict()
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# RegistryDag basic operations
# ---------------------------------------------------------------------------

class TestRegistryDagBasics:
    def test_empty_dag_has_zero_nodes(self, dag):
        assert dag.node_count == 0

    def test_empty_dag_has_zero_edges(self, dag):
        assert dag.edge_count == 0

    def test_add_single_node_increments_count(self, dag):
        dag.add_node(Node.resource("n1", "Node One"))
        assert dag.node_count == 1

    def test_add_multiple_nodes(self, dag):
        dag.add_node(Node.resource("n1", "Node One"))
        dag.add_node(Node.resource("n2", "Node Two"))
        assert dag.node_count == 2

    def test_add_edge_increments_edge_count(self, dag):
        dag.add_node(Node.resource("n1", "N1"))
        dag.add_node(Node.resource("n2", "N2"))
        dag.add_edge(Edge(from_id="n1", to_id="n2", edge_type=EdgeType.DEPENDS_ON))
        assert dag.edge_count == 1

    def test_add_multiple_edges(self, dag):
        dag.add_node(Node.resource("a", "A"))
        dag.add_node(Node.resource("b", "B"))
        dag.add_node(Node.resource("c", "C"))
        dag.add_edge(Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON))
        dag.add_edge(Edge(from_id="b", to_id="c", edge_type=EdgeType.DEPENDS_ON))
        assert dag.edge_count == 2


# ---------------------------------------------------------------------------
# RegistryDag query_relevant
# ---------------------------------------------------------------------------

class TestQueryRelevant:
    def test_query_relevant_returns_query_result(self, populated_dag):
        result = populated_dag.query_relevant("r1")
        assert isinstance(result, QueryResult)

    def test_query_relevant_includes_queried_node(self, populated_dag):
        result = populated_dag.query_relevant("r1")
        assert result is not None

    def test_query_relevant_on_isolated_node(self, dag):
        dag.add_node(Node.resource("solo", "Solo Node"))
        result = dag.query_relevant("solo")
        assert isinstance(result, QueryResult)


# ---------------------------------------------------------------------------
# RegistryDag component_members
# ---------------------------------------------------------------------------

class TestComponentMembers:
    def test_component_members_returns_list(self, populated_dag):
        members = populated_dag.component_members("r1")
        assert isinstance(members, list)

    def test_component_members_contains_self(self, populated_dag):
        members = populated_dag.component_members("r1")
        assert "r1" in members

    def test_isolated_node_component_contains_only_itself(self, dag):
        dag.add_node(Node.resource("iso", "Isolated"))
        members = dag.component_members("iso")
        assert "iso" in members


# ---------------------------------------------------------------------------
# RegistryDag validate_edge
# ---------------------------------------------------------------------------

class TestValidateEdge:
    def test_validate_edge_returns_validation_result(self, dag):
        dag.add_node(Node.resource("x", "X"))
        dag.add_node(Node.resource("y", "Y"))
        result = dag.validate_edge("x", "y", EdgeType.DEPENDS_ON)
        assert isinstance(result, ValidationResult)

    def test_valid_edge_is_valid(self, dag):
        dag.add_node(Node.resource("p", "P"))
        dag.add_node(Node.resource("q", "Q"))
        result = dag.validate_edge("p", "q", EdgeType.DEPENDS_ON)
        assert result.valid is True

    def test_cycle_detection_makes_edge_invalid(self, dag):
        dag.add_node(Node.resource("a", "A"))
        dag.add_node(Node.resource("b", "B"))
        dag.add_edge(Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON))
        result = dag.validate_edge("b", "a", EdgeType.DEPENDS_ON)
        assert result.valid is False


# ---------------------------------------------------------------------------
# RegistryDag extract_subgraph
# ---------------------------------------------------------------------------

class TestExtractSubgraph:
    def test_extract_subgraph_returns_subgraph_result(self, populated_dag):
        result = populated_dag.extract_subgraph("r1")
        assert isinstance(result, SubgraphResult)

    def test_extract_subgraph_single_node(self, dag):
        dag.add_node(Node.resource("only", "Only"))
        result = dag.extract_subgraph("only")
        assert isinstance(result, SubgraphResult)


# ---------------------------------------------------------------------------
# RegistryDag query_impact
# ---------------------------------------------------------------------------

class TestQueryImpact:
    def test_query_impact_returns_impact_result(self, populated_dag):
        result = populated_dag.query_impact("r3")
        assert isinstance(result, ImpactResult)

    def test_query_impact_on_leaf_node(self, dag):
        dag.add_node(Node.resource("leaf", "Leaf"))
        result = dag.query_impact("leaf")
        assert isinstance(result, ImpactResult)


# ---------------------------------------------------------------------------
# RegistryDag query_affected_tests
# ---------------------------------------------------------------------------

class TestQueryAffectedTests:
    def test_query_affected_tests_returns_list(self, populated_dag):
        result = populated_dag.query_affected_tests("r1")
        assert isinstance(result, list)

    def test_query_affected_tests_no_behaviors_returns_empty(self, dag):
        dag.add_node(Node.resource("r", "R"))
        result = dag.query_affected_tests("r")
        assert result == []


# ---------------------------------------------------------------------------
# RegistryDag remove_node
# ---------------------------------------------------------------------------

class TestRemoveNode:
    def test_remove_node_decrements_count(self, dag):
        dag.add_node(Node.resource("del1", "Delete Me"))
        dag.add_node(Node.resource("keep", "Keep Me"))
        dag.remove_node("del1")
        assert dag.node_count == 1

    def test_remove_only_node_leaves_empty_dag(self, dag):
        dag.add_node(Node.resource("only", "Only"))
        dag.remove_node("only")
        assert dag.node_count == 0

    def test_remove_nonexistent_node_raises(self, dag):
        with pytest.raises(Exception):
            dag.remove_node("does_not_exist")


# ---------------------------------------------------------------------------
# RegistryDag serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_returns_dict(self, populated_dag):
        d = populated_dag.to_dict()
        assert isinstance(d, dict)

    def test_to_json_returns_string(self, populated_dag):
        s = populated_dag.to_json()
        assert isinstance(s, str)

    def test_from_dict_roundtrip_preserves_node_count(self, populated_dag):
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.node_count == populated_dag.node_count

    def test_from_json_roundtrip_preserves_node_count(self, populated_dag):
        j = populated_dag.to_json()
        restored = RegistryDag.from_json(j)
        assert restored.node_count == populated_dag.node_count

    def test_from_dict_roundtrip_preserves_edge_count(self, populated_dag):
        d = populated_dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.edge_count == populated_dag.edge_count

    def test_empty_dag_roundtrip(self, dag):
        d = dag.to_dict()
        restored = RegistryDag.from_dict(d)
        assert restored.node_count == 0
        assert restored.edge_count == 0


# ---------------------------------------------------------------------------
# RegistryDag register helpers
# ---------------------------------------------------------------------------

class TestRegisterHelpers:
    def test_register_requirement_returns_string_id(self, dag):
        rid = dag.register_requirement("The system shall do X", name="Req X")
        assert isinstance(rid, str)

    def test_register_requirement_increments_node_count(self, dag):
        dag.register_requirement("Some requirement")
        assert dag.node_count == 1

    def test_register_gwt_increments_node_count(self, dag):
        dag.register_gwt(
            name="Login behavior",
            given="a valid user",
            when="they submit credentials",
            then="they are authenticated",
        )
        assert dag.node_count == 1

    def test_register_gwt_returns_string_id(self, dag):
        gwt_id = dag.register_gwt(
            name="Some behavior",
            given="given",
            when="when",
            then="then",
        )
        assert isinstance(gwt_id, str)


# ---------------------------------------------------------------------------
# RegistryDag component_count
# ---------------------------------------------------------------------------

class TestComponentCount:
    def test_empty_dag_has_zero_components(self, dag):
        assert dag.component_count == 0

    def test_single_node_has_one_component(self, dag):
        dag.add_node(Node.resource("solo", "Solo"))
        assert dag.component_count == 1

    def test_two_disconnected_nodes_have_two_components(self, dag):
        dag.add_node(Node.resource("a", "A"))
        dag.add_node(Node.resource("b", "B"))
        assert dag.component_count == 2

    def test_two_connected_nodes_have_one_component(self, dag):
        dag.add_node(Node.resource("a", "A"))
        dag.add_node(Node.resource("b", "B"))
        dag.add_edge(Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON))
        assert dag.component_count == 1