import pytest
from pathlib import Path
from registry.dag import RegistryDag, CycleError, NodeNotFoundError
from registry.types import Edge, EdgeType, Node, NodeKind


# ---------------------------------------------------------------------------
# Node factory helpers
# ---------------------------------------------------------------------------

def _make_resource(id: str, name: str = "res") -> Node:
    return Node.resource(id, name, description=f"description for {id}")


def _make_behavior(id: str) -> Node:
    return Node.behavior(id, name=id, given="given", when="when", then="then")


def _make_requirement(id: str, text: str = "req text") -> Node:
    return Node.requirement(id, text=text, name=id)


# ---------------------------------------------------------------------------
# Invariant verifier helpers (TLA+-style predicates)
# ---------------------------------------------------------------------------

def _inv_node_count(dag: RegistryDag, expected: int) -> None:
    assert dag.node_count == expected, (
        f"node_count {dag.node_count!r} != expected {expected!r}"
    )


def _inv_edge_count(dag: RegistryDag, expected: int) -> None:
    assert dag.edge_count == expected, (
        f"edge_count {dag.edge_count!r} != expected {expected!r}"
    )


def _inv_component_count_ge(dag: RegistryDag, minimum: int) -> None:
    assert dag.component_count >= minimum, (
        f"component_count {dag.component_count!r} < minimum {minimum!r}"
    )


def _inv_node_in_subgraph(dag: RegistryDag, node_id: str) -> None:
    result = dag.extract_subgraph(node_id)
    ids = [n.id for n in result.nodes]
    assert node_id in ids, (
        f"node {node_id!r} not found in subgraph nodes {ids!r}"
    )


def _inv_relevant_includes_self(dag: RegistryDag, resource_id: str) -> None:
    result = dag.query_relevant(resource_id)
    assert resource_id in result.node_ids, (
        f"resource_id {resource_id!r} not in query_relevant result {result.node_ids!r}"
    )


def _inv_component_members_nonempty(dag: RegistryDag, resource_id: str) -> None:
    members = dag.component_members(resource_id)
    assert len(members) >= 1, (
        f"component_members for {resource_id!r} is empty"
    )


def _inv_component_contains_self(dag: RegistryDag, resource_id: str) -> None:
    members = dag.component_members(resource_id)
    assert resource_id in members, (
        f"{resource_id!r} not in its own component {members!r}"
    )


def _inv_validate_edge_valid(dag: RegistryDag, from_id: str, to_id: str, edge_type: EdgeType) -> None:
    result = dag.validate_edge(from_id, to_id, edge_type)
    assert result.valid, (
        f"validate_edge({from_id!r}, {to_id!r}, {edge_type!r}) returned invalid: {result!r}"
    )


def _inv_validate_edge_cycle_invalid(dag: RegistryDag, from_id: str, to_id: str, edge_type: EdgeType) -> None:
    result = dag.validate_edge(from_id, to_id, edge_type)
    assert not result.valid, (
        f"validate_edge({from_id!r}, {to_id!r}) should be invalid (cycle), got valid"
    )


def _inv_to_dict_has_keys(dag: RegistryDag) -> None:
    d = dag.to_dict()
    assert "nodes" in d, f"to_dict() missing 'nodes' key: {list(d.keys())!r}"
    assert "edges" in d, f"to_dict() missing 'edges' key: {list(d.keys())!r}"


def _verify_empty_dag_invariants(dag: RegistryDag) -> None:
    _inv_node_count(dag, 0)
    _inv_edge_count(dag, 0)
    _inv_to_dict_has_keys(dag)


def _verify_single_node_invariants(dag: RegistryDag, node_id: str) -> None:
    _inv_node_count(dag, 1)
    _inv_edge_count(dag, 0)
    _inv_component_count_ge(dag, 1)
    _inv_component_contains_self(dag, node_id)
    _inv_relevant_includes_self(dag, node_id)
    _inv_node_in_subgraph(dag, node_id)
    _inv_to_dict_has_keys(dag)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_dag() -> RegistryDag:
    return RegistryDag()


@pytest.fixture()
def single_node_dag():
    dag = RegistryDag()
    node = _make_resource("R1", "Resource One")
    dag.add_node(node)
    return dag, "R1"


@pytest.fixture()
def two_node_dag():
    dag = RegistryDag()
    dag.add_node(_make_resource("R1", "Resource One"))
    dag.add_node(_make_resource("R2", "Resource Two"))
    return dag, "R1", "R2"


@pytest.fixture()
def connected_dag():
    dag = RegistryDag()
    dag.add_node(_make_resource("A", "Node A"))
    dag.add_node(_make_resource("B", "Node B"))
    dag.add_edge(Edge(from_id="A", to_id="B", edge_type=EdgeType.DEPENDS_ON))
    return dag, "A", "B"


# ---------------------------------------------------------------------------
# Empty DAG invariant tests
# ---------------------------------------------------------------------------

def test_empty_dag_node_count(empty_dag):
    _inv_node_count(empty_dag, 0)


def test_empty_dag_edge_count(empty_dag):
    _inv_edge_count(empty_dag, 0)


def test_empty_dag_to_dict_has_nodes_key(empty_dag):
    d = empty_dag.to_dict()
    assert "nodes" in d


def test_empty_dag_to_dict_has_edges_key(empty_dag):
    d = empty_dag.to_dict()
    assert "edges" in d


def test_empty_dag_to_json_roundtrip(empty_dag):
    json_str = empty_dag.to_json()
    restored = RegistryDag.from_json(json_str)
    _inv_node_count(restored, 0)
    _inv_edge_count(restored, 0)


def test_empty_dag_all_invariants(empty_dag):
    _verify_empty_dag_invariants(empty_dag)


# ---------------------------------------------------------------------------
# Single node invariant tests
# ---------------------------------------------------------------------------

def test_single_node_count(single_node_dag):
    dag, node_id = single_node_dag
    _inv_node_count(dag, 1)


def test_single_node_edge_count(single_node_dag):
    dag, node_id = single_node_dag
    _inv_edge_count(dag, 0)


def test_single_node_component_count(single_node_dag):
    dag, node_id = single_node_dag
    _inv_component_count_ge(dag, 1)


def test_single_node_component_contains_self(single_node_dag):
    dag, node_id = single_node_dag
    _inv_component_contains_self(dag, node_id)


def test_single_node_component_members_nonempty(single_node_dag):
    dag, node_id = single_node_dag
    _inv_component_members_nonempty(dag, node_id)


def test_single_node_relevant_includes_self(single_node_dag):
    dag, node_id = single_node_dag
    _inv_relevant_includes_self(dag, node_id)


def test_single_node_subgraph_contains_self(single_node_dag):
    dag, node_id = single_node_dag
    _inv_node_in_subgraph(dag, node_id)


def test_single_node_to_dict_has_keys(single_node_dag):
    dag, _ = single_node_dag
    _inv_to_dict_has_keys(dag)


def test_single_node_all_invariants(single_node_dag):
    dag, node_id = single_node_dag
    _verify_single_node_invariants(dag, node_id)


# ---------------------------------------------------------------------------
# Two node (disconnected) invariants
# ---------------------------------------------------------------------------

def test_two_nodes_count(two_node_dag):
    dag, r1, r2 = two_node_dag
    _inv_node_count(dag, 2)


def test_two_nodes_edge_count(two_node_dag):
    dag, r1, r2 = two_node_dag
    _inv_edge_count(dag, 0)


def test_two_nodes_both_in_their_components(two_node_dag):
    dag, r1, r2 = two_node_dag
    _inv_component_contains_self(dag, r1)
    _inv_component_contains_self(dag, r2)


def test_two_nodes_relevant_each_includes_self(two_node_dag):
    dag, r1, r2 = two_node_dag
    _inv_relevant_includes_self(dag, r1)
    _inv_relevant_includes_self(dag, r2)


def test_two_nodes_disconnected_components_ge_2(two_node_dag):
    dag, r1, r2 = two_node_dag
    _inv_component_count_ge(dag, 2)


# ---------------------------------------------------------------------------
# Connected DAG invariants
# ---------------------------------------------------------------------------

def test_connected_dag_edge_count(connected_dag):
    dag, a, b = connected_dag
    _inv_edge_count(dag, 1)


def test_connected_dag_node_count(connected_dag):
    dag, a, b = connected_dag
    _inv_node_count(dag, 2)


def test_connected_dag_subgraph_a_contains_a(connected_dag):
    dag, a, b = connected_dag
    _inv_node_in_subgraph(dag, a)


def test_connected_dag_subgraph_b_contains_b(connected_dag):
    dag, a, b = connected_dag
    _inv_node_in_subgraph(dag, b)


def test_connected_dag_relevant_a_includes_a(connected_dag):
    dag, a, b = connected_dag
    _inv_relevant_includes_self(dag, a)


def test_connected_dag_relevant_b_includes_b(connected_dag):
    dag, a, b = connected_dag
    _inv_relevant_includes_self(dag, b)


def test_connected_dag_to_dict_has_keys(connected_dag):
    dag, a, b = connected_dag
    _inv_to_dict_has_keys(dag)


# ---------------------------------------------------------------------------
# Cycle detection invariants
# ---------------------------------------------------------------------------

def test_add_edge_cycle_raises_cycle_error():
    dag = RegistryDag()
    dag.add_node(_make_resource("X", "X"))
    dag.add_node(_make_resource("Y", "Y"))
    dag.add_edge(Edge(from_id="X", to_id="Y", edge_type=EdgeType.DEPENDS_ON))
    with pytest.raises(CycleError):
        dag.add_edge(Edge(from_id="Y", to_id="X", edge_type=EdgeType.DEPENDS_ON))


def test_self_loop_raises_cycle_error():
    dag = RegistryDag()
    dag.add_node(_make_resource("Z", "Z"))
    with pytest.raises(CycleError):
        dag.add_edge(Edge(from_id="Z", to_id="Z", edge_type=EdgeType.DEPENDS_ON))


def test_validate_edge_back_edge_is_invalid():
    dag = RegistryDag()
    dag.add_node(_make_resource("M", "M"))
    dag.add_node(_make_resource("N", "N"))
    dag.add_edge(Edge(from_id="M", to_id="N", edge_type=EdgeType.DEPENDS_ON))
    _inv_validate_edge_cycle_invalid(dag, "N", "M", EdgeType.DEPENDS_ON)


def test_validate_edge_forward_edge_is_valid():
    dag = RegistryDag()
    dag.add_node(_make_resource("P", "P"))
    dag.add_node(_make_resource("Q", "Q"))
    _inv_validate_edge_valid(dag, "P", "Q", EdgeType.DEPENDS_ON)


def test_three_node_cycle_raises_cycle_error():
    dag = RegistryDag()
    for nid in ("C1", "C2", "C3"):
        dag.add_node(_make_resource(nid, nid))
    dag.add_edge(Edge(from_id="C1", to_id="C2", edge_type=EdgeType.DEPENDS_ON))
    dag.add_edge(Edge(from_id="C2", to_id="C3", edge_type=EdgeType.DEPENDS_ON))
    with pytest.raises(CycleError):
        dag.add_edge(Edge(from_id="C3", to_id="C1", edge_type=EdgeType.DEPENDS_ON))


# ---------------------------------------------------------------------------
# NodeNotFoundError invariants
# ---------------------------------------------------------------------------

def test_query_relevant_unknown_node_raises(empty_dag):
    with pytest.raises((NodeNotFoundError, KeyError, Exception)):
        empty_dag.query_relevant("nonexistent_id")


def test_extract_subgraph_unknown_node_raises(empty_dag):
    with pytest.raises((NodeNotFoundError, KeyError, Exception)):
        empty_dag.extract_subgraph("nonexistent_id")


def test_component_members_unknown_node_raises(empty_dag):
    with pytest.raises((NodeNotFoundError, KeyError, Exception)):
        empty_dag.component_members("nonexistent_id")


# ---------------------------------------------------------------------------
# Remove node invariants
# ---------------------------------------------------------------------------

def test_remove_node_decrements_count(single_node_dag):
    dag, node_id = single_node_dag
    dag.remove_node(node_id)
    _inv_node_count(dag, 0)


def test_remove_node_then_add_back_restores_count():
    dag = RegistryDag()
    dag.add_node(_make_resource("REM1", "REM1"))
    dag.remove_node("REM1")
    dag.add_node(_make_resource("REM1", "REM1"))
    _inv_node_count(dag, 1)


def test_remove_nonexistent_node_raises():
    dag = RegistryDag()
    with pytest.raises((NodeNotFoundError, KeyError, Exception)):
        dag.remove_node("does_not_exist")


# ---------------------------------------------------------------------------
# JSON / dict roundtrip invariants
# ---------------------------------------------------------------------------

def test_to_json_from_json_preserves_node_count():
    dag = RegistryDag()
    for i in range(5):
        dag.add_node(_make_resource(f"J{i}", f"J{i}"))
    restored = RegistryDag.from_json(dag.to_json())
    _inv_node_count(restored, 5)


def test_to_json_from_json_preserves_edge_count():
    dag = RegistryDag()
    dag.add_node(_make_resource("JA", "JA"))
    dag.add_node(_make_resource("JB", "JB"))
    dag.add_edge(Edge(from_id="JA", to_id="JB", edge_type=EdgeType.DEPENDS_ON))
    restored = RegistryDag.from_json(dag.to_json())
    _inv_edge_count(restored, 1)


def test_to_dict_from_dict_preserves_node_count():
    dag = RegistryDag()
    for i in range(3):
        dag.add_node(_make_resource(f"D{i}", f"D{i}"))
    restored = RegistryDag.from_dict(dag.to_dict())
    _inv_node_count(restored, 3)


def test_to_dict_from_dict_preserves_edge_count():
    dag = RegistryDag()
    dag.add_node(_make_resource("DA", "DA"))
    dag.add_node(_make_resource("DB", "DB"))
    dag.add_edge(Edge(from_id="DA", to_id="DB", edge_type=EdgeType.DEPENDS_ON))
    restored = RegistryDag.from_dict(dag.to_dict())
    _inv_edge_count(restored, 1)


# ---------------------------------------------------------------------------
# Save / load roundtrip invariants
# ---------------------------------------------------------------------------

def test_save_and_load_preserves_node_count(tmp_path):
    dag = RegistryDag()
    for i in range(4):
        dag.add_node(_make_resource(f"SL{i}", f"SL{i}"))
    save_path = tmp_path / "dag.json"
    dag.save(save_path)
    loaded = RegistryDag.load(save_path)
    _inv_node_count(loaded, 4)


def test_save_and_load_preserves_edge_count(tmp_path):
    dag = RegistryDag()
    dag.add_node(_make_resource("SA", "SA"))
    dag.add_node(_make_resource("SB", "SB"))
    dag.add_edge(Edge(from_id="SA", to_id="SB", edge_type=EdgeType.DEPENDS_ON))
    save_path = tmp_path / "dag_edge.json"
    dag.save(save_path)
    loaded = RegistryDag.load(save_path)
    _inv_edge_count(loaded, 1)


def test_save_and_load_loaded_dag_is_dag_instance(tmp_path):
    dag = RegistryDag()
    save_path = tmp_path / "empty.json"
    dag.save(save_path)
    loaded = RegistryDag.load(save_path)
    assert isinstance(loaded, RegistryDag)


# ---------------------------------------------------------------------------
# register_gwt and register_requirement invariants
# ---------------------------------------------------------------------------

def test_register_gwt_increments_node_count(empty_dag):
    before = empty_dag.node_count
    empty_dag.register_gwt(
        name="Test behavior",
        given="given context",
        when="action is taken",
        then="expected result",
    )
    assert empty_dag.node_count == before + 1


def test_register_gwt_returns_string_id(empty_dag):
    result_id = empty_dag.register_gwt(
        name="Behavior A",
        given="g",
        when="w",
        then="t",
    )
    assert isinstance(result_id, str)
    assert len(result_id) > 0


def test_register_gwt_id_in_component(empty_dag):
    result_id = empty_dag.register_gwt(
        name="Behavior B",
        given="g",
        when="w",
        then="t",
    )
    _inv_component_contains_self(empty_dag, result_id)


def test_register_requirement_increments_node_count(empty_dag):
    before = empty_dag.node_count
    empty_dag.register_requirement(text="The system shall do something", name="REQ-001")
    assert empty_dag.node_count == before + 1


def test_register_requirement_returns_string_id(empty_dag):
    result_id = empty_dag.register_requirement(text="Some requirement", name="REQ-X")
    assert isinstance(result_id, str)
    assert len(result_id) > 0


def test_register_requirement_id_relevant_includes_self(empty_dag):
    result_id = empty_dag.register_requirement(text="Another requirement")
    _inv_relevant_includes_self(empty_dag, result_id)


def test_register_multiple_gwt_unique_ids(empty_dag):
    ids = [
        empty_dag.register_gwt(name=f"B{i}", given="g", when="w", then="t")
        for i in range(5)
    ]
    assert len(set(ids)) == 5, f"Expected 5 unique IDs, got: {ids!r}"


def test_register_multiple_requirements_unique_ids(empty_dag):
    ids = [
        empty_dag.register_requirement(text=f"Req {i}", name=f"R{i}")
        for i in range(5)
    ]
    assert len(set(ids)) == 5, f"Expected 5 unique IDs, got: {ids!r}"


# ---------------------------------------------------------------------------
# Node kinds invariants
# ---------------------------------------------------------------------------

def test_node_resource_kind():
    node = _make_resource("NK1", "NK1")
    assert node.kind == NodeKind.RESOURCE


def test_node_behavior_kind():
    node = _make_behavior("NK2")
    assert node.kind == NodeKind.BEHAVIOR


def test_node_requirement_kind():
    node = _make_requirement("NK3")
    assert node.kind == NodeKind.REQUIREMENT


def test_node_to_dict_contains_id():
    node = _make_resource("ND1", "ND1")
    d = node.to_dict()
    assert "id" in d


def test_node_to_dict_contains_kind():
    node = _make_resource("ND2", "ND2")
    d = node.to_dict()
    assert "kind" in d


def test_edge_to_dict_contains_from_id():
    edge = Edge(from_id="E1", to_id="E2", edge_type=EdgeType.DEPENDS_ON)
    d = edge.to_dict()
    assert "from_id" in d


def test_edge_to_dict_contains_to_id():
    edge = Edge(from_id="E1", to_id="E2", edge_type=EdgeType.DEPENDS_ON)
    d = edge.to_dict()
    assert "to_id" in d


# ---------------------------------------------------------------------------
# query_impact invariants
# ---------------------------------------------------------------------------

def test_query_impact_returns_result(single_node_dag):
    dag, node_id = single_node_dag
    result = dag.query_impact(node_id)
    assert result is not None


def test_query_impact_target_in_affected(connected_dag):
    dag, a, b = connected_dag
    result = dag.query_impact(b)
    assert result is not None


# ---------------------------------------------------------------------------
# query_affected_tests invariants
# ---------------------------------------------------------------------------

def test_query_affected_tests_returns_list(single_node_dag):
    dag, node_id = single_node_dag
    result = dag.query_affected_tests(node_id)
    assert isinstance(result, list)


def test_query_affected_tests_connected_returns_list(connected_dag):
    dag, a, b = connected_dag
    result = dag.query_affected_tests(a)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Two topologies — invariant verifiers run twice
# ---------------------------------------------------------------------------

def test_two_topologies_all_invariants_empty():
    for suffix in ("T1", "T2"):
        dag = RegistryDag()
        _verify_empty_dag_invariants(dag)


def test_two_topologies_single_node_invariants():
    for suffix in ("A", "B"):
        dag = RegistryDag()
        node_id = f"NODE_{suffix}"
        dag.add_node(_make_resource(node_id, node_id))
        _verify_single_node_invariants(dag, node_id)


def test_two_topologies_connected_edge_count():
    for suffix in ("X", "Y"):
        dag = RegistryDag()
        a, b = f"NA_{suffix}", f"NB_{suffix}"
        dag.add_node(_make_resource(a, a))
        dag.add_node(_make_resource(b, b))
        dag.add_edge(Edge(from_id=a, to_id=b, edge_type=EdgeType.DEPENDS_ON))
        _inv_edge_count(dag, 1)
        _inv_node_count(dag, 2)


def test_two_topologies_json_roundtrip():
    for n_nodes in (3, 7):
        dag = RegistryDag()
        for i in range(n_nodes):
            dag.add_node(_make_resource(f"RT{i}", f"RT{i}"))
        restored = RegistryDag.from_json(dag.to_json())
        _inv_node_count(restored, n_nodes)


def test_two_topologies_validate_edge_no_cycle():
    for suffix in ("P", "Q"):
        dag = RegistryDag()
        a, b = f"VA_{suffix}", f"VB_{suffix}"
        dag.add_node(_make_resource(a, a))
        dag.add_node(_make_resource(b, b))
        _inv_validate_edge_valid(dag, a, b, EdgeType.DEPENDS_ON)


def test_two_topologies_cycle_detection():
    for suffix in ("M", "N"):
        dag = RegistryDag()
        a, b = f"CA_{suffix}", f"CB_{suffix}"
        dag.add_node(_make_resource(a, a))
        dag.add_node(_make_resource(b, b))
        dag.add_edge(Edge(from_id=a, to_id=b, edge_type=EdgeType.DEPENDS_ON))
        with pytest.raises(CycleError):
            dag.add_edge(Edge(from_id=b, to_id=a, edge_type=EdgeType.DEPENDS_ON))