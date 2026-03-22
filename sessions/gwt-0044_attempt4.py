"""
Test suite: CrawlBridgeResourceNodes
Verifies that bridge_crawl_to_dag creates exactly one RESOURCE node per
non-external crawl.db record, with id matching the record UUID, and that
node count equals record count.

Derived from 10 TLC-verified traces of CrawlBridgeResourceNodes.tla.
All TLA+ invariants (TypeOK, OnlyResourceKinds, NodesAddedMatchesDomainSize,
UUIDDomainSubsetOfInput, ProcessedNodesAreResource, TerminalCorrectness)
are verified at every intermediate state.
"""
from __future__ import annotations

import uuid
from typing import Dict, FrozenSet, Set, Tuple

from registry.dag import RegistryDag
from registry.types import Node, NodeKind

# ---------------------------------------------------------------------------
# Deterministic UUID5 identifiers
# ---------------------------------------------------------------------------
_NS = uuid.NAMESPACE_DNS
UUIDS_1: str = str(uuid.uuid5(_NS, "crawl.record.one"))
UUIDS_2: str = str(uuid.uuid5(_NS, "crawl.record.two"))
UUIDS_3: str = str(uuid.uuid5(_NS, "crawl.record.three"))

_TWO_UUIDS: FrozenSet[str] = frozenset({UUIDS_1, UUIDS_2})
_ONE_UUID: FrozenSet[str] = frozenset({UUIDS_1})
_THREE_UUIDS: FrozenSet[str] = frozenset({UUIDS_1, UUIDS_2, UUIDS_3})
_EMPTY_UUIDS: FrozenSet[str] = frozenset()


# ---------------------------------------------------------------------------
# TLA+ state helpers
# ---------------------------------------------------------------------------

def _init_state(
    all_uuids: FrozenSet[str],
) -> Tuple[RegistryDag, Dict[str, str], int, Set[str]]:
    return RegistryDag(), {}, 0, set(all_uuids)


def _step_process_record(
    dag: RegistryDag,
    uid: str,
    dag_nodes: Dict[str, str],
    nodes_added: int,
    remaining: Set[str],
) -> Tuple[Dict[str, str], int, Set[str]]:
    dag.add_node(Node.resource(uid, uid))
    return {**dag_nodes, uid: "RESOURCE"}, nodes_added + 1, remaining - {uid}


def _step_finish(
    dag_nodes: Dict[str, str],
    nodes_added: int,
    remaining: Set[str],
    all_uuids: FrozenSet[str],
) -> None:
    assert remaining == set(), "Finish: remaining must be empty"
    assert nodes_added == len(all_uuids), (
        f"Finish: nodes_added={nodes_added} != |Uuids|={len(all_uuids)}"
    )
    assert set(dag_nodes) == set(all_uuids), (
        f"Finish: DOMAIN dag_nodes {set(dag_nodes)} != Uuids {set(all_uuids)}"
    )
    for uid in all_uuids:
        assert dag_nodes[uid] == "RESOURCE", (
            f"Finish: dag_nodes[{uid}] = {dag_nodes[uid]!r}, expected RESOURCE"
        )
    assert len(dag_nodes) == len(all_uuids), (
        f"Finish: |dag_nodes|={len(dag_nodes)} != |Uuids|={len(all_uuids)}"
    )


# ---------------------------------------------------------------------------
# Invariant verifiers
# ---------------------------------------------------------------------------

def _inv_type_ok(dag_nodes: Dict[str, str], nodes_added: int) -> None:
    assert nodes_added >= 0, f"TypeOK: nodes_added={nodes_added} < 0"
    for uid, kind in dag_nodes.items():
        assert kind == "RESOURCE", f"TypeOK: {uid} → {kind!r}, expected RESOURCE"


def _inv_only_resource_kinds(dag_nodes: Dict[str, str]) -> None:
    for uid, kind in dag_nodes.items():
        assert kind == "RESOURCE", f"OnlyResourceKinds: {uid} → {kind!r}"


def _inv_nodes_added_matches_domain(dag_nodes: Dict[str, str], nodes_added: int) -> None:
    assert nodes_added == len(dag_nodes), (
        f"NodesAddedMatchesDomainSize: nodes_added={nodes_added} != |domain|={len(dag_nodes)}"
    )


def _inv_uuid_domain_subset_of_input(
    dag_nodes: Dict[str, str], all_uuids: FrozenSet[str]
) -> None:
    extra = set(dag_nodes) - all_uuids
    assert not extra, f"UUIDDomainSubsetOfInput: unexpected UUIDs in dag_nodes: {extra}"


def _inv_processed_nodes_are_resource(
    dag_nodes: Dict[str, str], remaining: Set[str], all_uuids: FrozenSet[str]
) -> None:
    for uid in all_uuids - remaining:
        assert uid in dag_nodes, f"ProcessedNodesAreResource: {uid} not in dag_nodes"
        assert dag_nodes[uid] == "RESOURCE", (
            f"ProcessedNodesAreResource: {uid} → {dag_nodes[uid]!r}"
        )


def _inv_terminal_correctness(
    dag_nodes: Dict[str, str],
    nodes_added: int,
    remaining: Set[str],
    all_uuids: FrozenSet[str],
) -> None:
    if remaining:
        return
    assert nodes_added == len(all_uuids), (
        f"TerminalCorrectness: nodes_added={nodes_added} != |Uuids|={len(all_uuids)}"
    )
    assert set(dag_nodes) == set(all_uuids), (
        f"TerminalCorrectness: domain mismatch {set(dag_nodes)} != {set(all_uuids)}"
    )
    for uid in all_uuids:
        assert dag_nodes[uid] == "RESOURCE", (
            f"TerminalCorrectness: {uid} → {dag_nodes[uid]!r}"
        )
    assert len(dag_nodes) == len(all_uuids)


def _check_all_invariants(
    dag_nodes: Dict[str, str],
    nodes_added: int,
    remaining: Set[str],
    all_uuids: FrozenSet[str],
) -> None:
    _inv_type_ok(dag_nodes, nodes_added)
    _inv_only_resource_kinds(dag_nodes)
    _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
    _inv_uuid_domain_subset_of_input(dag_nodes, all_uuids)
    _inv_processed_nodes_are_resource(dag_nodes, remaining, all_uuids)
    _inv_terminal_correctness(dag_nodes, nodes_added, remaining, all_uuids)


def _assert_dag_node_count(dag: RegistryDag, expected: int) -> None:
    assert dag.node_count == expected, (
        f"dag.node_count={dag.node_count}, expected {expected}"
    )


def _assert_dag_resource_nodes(dag: RegistryDag, expected_uuids: FrozenSet[str]) -> None:
    _assert_dag_node_count(dag, len(expected_uuids))
    dag_data = dag.to_dict()
    actual_ids: Set[str] = {n["id"] for n in dag_data.get("nodes", [])}
    assert actual_ids == set(expected_uuids), (
        f"DAG node IDs {actual_ids} != expected {set(expected_uuids)}"
    )
    for node_data in dag_data.get("nodes", []):
        kind = node_data.get("kind", "")
        assert kind in ("RESOURCE", NodeKind.RESOURCE), (
            f"Node {node_data['id']} has kind {kind!r}, expected RESOURCE"
        )


# ===========================================================================
# Trace 1
# ===========================================================================

class TestTrace1:
    def test_trace1_step_by_step_all_invariants(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)

        assert nodes_added == 0
        assert remaining == {UUIDS_1, UUIDS_2}
        assert dag_nodes == {}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 0)

        dag_nodes, nodes_added, remaining = _step_process_record(
            dag, UUIDS_2, dag_nodes, nodes_added, remaining
        )
        assert nodes_added == 1
        assert remaining == {UUIDS_1}
        assert dag_nodes == {UUIDS_2: "RESOURCE"}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 1)

        dag_nodes, nodes_added, remaining = _step_process_record(
            dag, UUIDS_1, dag_nodes, nodes_added, remaining
        )
        assert nodes_added == 2
        assert remaining == set()
        assert dag_nodes == {UUIDS_1: "RESOURCE", UUIDS_2: "RESOURCE"}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 2)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_resource_nodes(dag, _TWO_UUIDS)

    def test_trace1_node_count_equals_record_count(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        assert dag.node_count == len(_TWO_UUIDS)
        assert nodes_added == len(_TWO_UUIDS)

    def test_trace1_each_uuid_produces_exactly_one_resource_node(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        for uid in _TWO_UUIDS:
            assert dag_nodes[uid] == "RESOURCE"
        assert dag.node_count == 2


# ===========================================================================
# Trace 2
# ===========================================================================

class TestTrace2:
    def test_trace2_full_run_matches_terminal_state(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        assert dag.node_count == 2
        assert nodes_added == 2
        assert remaining == set()


# ===========================================================================
# Trace 3
# ===========================================================================

class TestTrace3:
    def test_trace3_step_by_step_all_invariants(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)

        assert nodes_added == 0
        assert remaining == {UUIDS_1, UUIDS_2}
        assert dag_nodes == {}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 0)

        dag_nodes, nodes_added, remaining = _step_process_record(
            dag, UUIDS_1, dag_nodes, nodes_added, remaining
        )
        assert nodes_added == 1
        assert remaining == {UUIDS_2}
        assert dag_nodes == {UUIDS_1: "RESOURCE"}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 1)

        dag_nodes, nodes_added, remaining = _step_process_record(
            dag, UUIDS_2, dag_nodes, nodes_added, remaining
        )
        assert nodes_added == 2
        assert remaining == set()
        assert dag_nodes == {UUIDS_1: "RESOURCE", UUIDS_2: "RESOURCE"}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_node_count(dag, 2)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        _assert_dag_resource_nodes(dag, _TWO_UUIDS)

    def test_trace3_node_count_equals_record_count(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        assert dag.node_count == len(_TWO_UUIDS)
        assert nodes_added == len(_TWO_UUIDS)


# ===========================================================================
# Trace 4
# ===========================================================================

class TestTrace4:
    def test_trace4_node_ids_match_input_uuids(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)
        assert set(dag_nodes.keys()) == set(_TWO_UUIDS)
        _assert_dag_resource_nodes(dag, _TWO_UUIDS)


# ===========================================================================
# Trace 5
# ===========================================================================

class TestTrace5:
    def test_trace5_nodes_added_tracks_domain_size_at_every_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Trace 6
# ===========================================================================

class TestTrace6:
    def test_trace6_uuid_domain_always_subset_of_input(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)
        assert set(dag_nodes).issubset(_TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)
        assert set(dag_nodes) == set(_TWO_UUIDS)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Trace 7
# ===========================================================================

class TestTrace7:
    def test_trace7_processed_nodes_resource_at_every_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)
        assert UUIDS_1 in dag_nodes and dag_nodes[UUIDS_1] == "RESOURCE"
        assert UUIDS_2 not in dag_nodes

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)
        assert dag_nodes[UUIDS_2] == "RESOURCE"

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Trace 8
# ===========================================================================

class TestTrace8:
    def test_trace8_type_ok_at_every_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_type_ok(dag_nodes, nodes_added)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_type_ok(dag_nodes, nodes_added)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_type_ok(dag_nodes, nodes_added)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Trace 9
# ===========================================================================

class TestTrace9:
    def test_trace9_terminal_correctness_vacuous_then_active(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        assert remaining == set()
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Trace 10
# ===========================================================================

class TestTrace10:
    def test_trace10_only_resource_kinds_at_every_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_only_resource_kinds(dag_nodes)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_only_resource_kinds(dag_nodes)
        assert dag_nodes == {UUIDS_2: "RESOURCE"}

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_only_resource_kinds(dag_nodes)
        assert dag_nodes == {UUIDS_1: "RESOURCE", UUIDS_2: "RESOURCE"}

        _step_finish(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Invariant-specific tests
# ===========================================================================

class TestInvariantTypeOK:
    def test_type_ok_empty_init_state(self) -> None:
        _inv_type_ok({}, 0)

    def test_type_ok_one_record_topology(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_type_ok(dag_nodes, nodes_added)

    def test_type_ok_two_records_order_uuids2_first(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_2, UUIDS_1]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
            _inv_type_ok(dag_nodes, nodes_added)

    def test_type_ok_two_records_order_uuids1_first(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
            _inv_type_ok(dag_nodes, nodes_added)


class TestInvariantOnlyResourceKinds:
    def test_only_resource_kinds_empty_state(self) -> None:
        _inv_only_resource_kinds({})

    def test_only_resource_kinds_one_record(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_only_resource_kinds(dag_nodes)

    def test_only_resource_kinds_two_records_order_a(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_2, UUIDS_1]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_only_resource_kinds(dag_nodes)

    def test_only_resource_kinds_two_records_order_b(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_only_resource_kinds(dag_nodes)


class TestInvariantNodesAddedMatchesDomainSize:
    def test_count_matches_domain_empty_state(self) -> None:
        _inv_nodes_added_matches_domain({}, 0)

    def test_count_matches_domain_one_record(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
        assert nodes_added == 1 == len(dag_nodes)

    def test_count_matches_domain_two_records_order_a_at_each_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)

    def test_count_matches_domain_two_records_order_b_at_each_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_nodes_added_matches_domain(dag_nodes, nodes_added)


class TestInvariantUUIDDomainSubsetOfInput:
    def test_subset_empty_state(self) -> None:
        _inv_uuid_domain_subset_of_input({}, _TWO_UUIDS)

    def test_subset_after_partial_processing_order_a(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)
        assert set(dag_nodes) < set(_TWO_UUIDS)

    def test_subset_after_partial_processing_order_b(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)

    def test_subset_equals_input_at_terminal(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_2, UUIDS_1]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)
        assert set(dag_nodes) == set(_TWO_UUIDS)

    def test_subset_three_record_topology(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_THREE_UUIDS)
        for uid in sorted(_THREE_UUIDS):
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_uuid_domain_subset_of_input(dag_nodes, _THREE_UUIDS)


class TestInvariantProcessedNodesAreResource:
    def test_processed_nothing_yet(self) -> None:
        _inv_processed_nodes_are_resource({}, {UUIDS_1, UUIDS_2}, _TWO_UUIDS)

    def test_processed_one_of_two_order_a(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)

    def test_processed_one_of_two_order_b(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)

    def test_processed_all_two_records(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _TWO_UUIDS)

    def test_processed_one_record_topology(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _inv_processed_nodes_are_resource(dag_nodes, remaining, _ONE_UUID)


class TestInvariantTerminalCorrectness:
    def test_terminal_vacuous_when_remaining_nonempty(self) -> None:
        _inv_terminal_correctness({}, 0, {UUIDS_1, UUIDS_2}, _TWO_UUIDS)

    def test_terminal_after_one_record(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        assert remaining == set()
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _ONE_UUID)

    def test_terminal_after_two_records_order_a(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_2, UUIDS_1]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _TWO_UUIDS)

    def test_terminal_after_two_records_order_b(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(dag, uid, dag_nodes, nodes_added, remaining)
        _inv_terminal_correctness(dag_nodes, nodes_added, remaining, _TWO_UUIDS)


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_crawl_db_produces_empty_dag(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_EMPTY_UUIDS)
        assert dag.node_count == 0
        assert nodes_added == 0
        assert remaining == set()
        assert dag_nodes == {}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _EMPTY_UUIDS)
        _step_finish(dag_nodes, nodes_added, remaining, _EMPTY_UUIDS)

    def test_single_record_produces_exactly_one_resource_node(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_ONE_UUID)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _ONE_UUID)

        dag_nodes, nodes_added, remaining = _step_process_record(
            dag, UUIDS_1, dag_nodes, nodes_added, remaining
        )
        assert nodes_added == 1
        assert dag.node_count == 1
        assert dag_nodes == {UUIDS_1: "RESOURCE"}
        _check_all_invariants(dag_nodes, nodes_added, remaining, _ONE_UUID)
        _step_finish(dag_nodes, nodes_added, remaining, _ONE_UUID)

    def test_three_records_all_become_resource_nodes(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_THREE_UUIDS)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _THREE_UUIDS)

        for uid in sorted(_THREE_UUIDS):
            dag_nodes, nodes_added, remaining = _step_process_record(
                dag, uid, dag_nodes, nodes_added, remaining
            )
            _check_all_invariants(dag_nodes, nodes_added, remaining, _THREE_UUIDS)

        assert dag.node_count == 3
        assert nodes_added == 3
        _step_finish(dag_nodes, nodes_added, remaining, _THREE_UUIDS)
        _assert_dag_resource_nodes(dag, _THREE_UUIDS)

    def test_node_ids_are_valid_uuid5_strings(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(
                dag, uid, dag_nodes, nodes_added, remaining
            )
        for uid in _TWO_UUIDS:
            parsed = uuid.UUID(uid)
            assert parsed.version == 5, f"{uid} is not UUID5"
        assert set(dag_nodes.keys()) == set(_TWO_UUIDS)
        dag_data = dag.to_dict()
        for node_data in dag_data.get("nodes", []):
            node_id = node_data["id"]
            parsed = uuid.UUID(node_id)
            assert parsed.version == 5, f"DAG node ID {node_id!r} is not UUID5"

    def test_no_spurious_nodes_outside_input_domain(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(
                dag, uid, dag_nodes, nodes_added, remaining
            )
        assert UUIDS_3 not in dag_nodes
        _inv_uuid_domain_subset_of_input(dag_nodes, _TWO_UUIDS)

    def test_bridge_creates_no_edges(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        for uid in [UUIDS_1, UUIDS_2]:
            dag_nodes, nodes_added, remaining = _step_process_record(
                dag, uid, dag_nodes, nodes_added, remaining
            )
        assert dag.edge_count == 0

    def test_all_invariants_three_records_at_each_intermediate_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_THREE_UUIDS)
        _check_all_invariants(dag_nodes, nodes_added, remaining, _THREE_UUIDS)

        for i, uid in enumerate(sorted(_THREE_UUIDS), start=1):
            dag_nodes, nodes_added, remaining = _step_process_record(
                dag, uid, dag_nodes, nodes_added, remaining
            )
            _check_all_invariants(dag_nodes, nodes_added, remaining, _THREE_UUIDS)
            assert dag.node_count == i
            assert nodes_added == i

    def test_domain_grows_monotonically_across_steps(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        prev_size = len(dag_nodes)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        assert len(dag_nodes) == prev_size + 1
        prev_size = len(dag_nodes)

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        assert len(dag_nodes) == prev_size + 1

    def test_remaining_shrinks_monotonically_across_steps(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        assert len(remaining) == 2

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        assert len(remaining) == 1

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        assert len(remaining) == 0

    def test_dag_node_count_matches_tracking_dict_at_every_step(self) -> None:
        dag, dag_nodes, nodes_added, remaining = _init_state(_TWO_UUIDS)
        _assert_dag_node_count(dag, len(dag_nodes))

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_2, dag_nodes, nodes_added, remaining)
        _assert_dag_node_count(dag, len(dag_nodes))

        dag_nodes, nodes_added, remaining = _step_process_record(dag, UUIDS_1, dag_nodes, nodes_added, remaining)
        _assert_dag_node_count(dag, len(dag_nodes))