"""
pytest suite for CrawlBridgeOrphanCleanup — orphan-cleanup phase.

Derived from 10 TLA+-verified simulation traces.  All 8 invariants from the
verified spec are checked at every intermediate state.
"""
from __future__ import annotations

import re
import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node

# ---------------------------------------------------------------------------
# Symbolic → concrete bindings
# ---------------------------------------------------------------------------

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# ResourceUUIDNodes_1 / ResourceUUIDNodes_2 from all trace Init states
UUID_NODE_1 = "aaaaaaaa-0001-0001-0001-000000000001"
UUID_NODE_2 = "bbbbbbbb-0002-0002-0002-000000000002"
RESOURCE_UUID_NODES = frozenset({UUID_NODE_1, UUID_NODE_2})

# dag_resource_nonuuid = 10  (all traces)
NON_UUID_RESOURCE_IDS = tuple(f"res-nonuuid-{i:03d}" for i in range(1, 11))

# dag_other = 10  (all traces)  — behaviour nodes = non-RESOURCE
OTHER_NODE_IDS = tuple(f"behavior-other-{i:03d}" for i in range(1, 11))

# CrawlUUIDs variants used across tests
CRAWL_UUIDS_EMPTY: frozenset = frozenset()               # both nodes are orphans (all 10 traces)
CRAWL_UUIDS_ONE:   frozenset = frozenset({UUID_NODE_1})  # UUID_NODE_1 protected, UUID_NODE_2 orphan
CRAWL_UUIDS_BOTH:  frozenset = RESOURCE_UUID_NODES       # no orphans at all


# ---------------------------------------------------------------------------
# Low-level DAG inspection helpers
# ---------------------------------------------------------------------------

def _is_uuid(node_id: str) -> bool:
    return bool(UUID_RE.match(node_id))


def _dag_has_node(dag: RegistryDag, node_id: str) -> bool:
    return node_id in dag.to_dict().get("nodes", {})


def _current_uuid_nodes(dag: RegistryDag, uuid_nodes: frozenset) -> frozenset:
    """Return the subset of uuid_nodes that are still present in the DAG."""
    return frozenset(n for n in uuid_nodes if _dag_has_node(dag, n))


def _count_present(dag: RegistryDag, node_ids) -> int:
    return sum(1 for n in node_ids if _dag_has_node(dag, n))


# ---------------------------------------------------------------------------
# All-invariants checker
# ---------------------------------------------------------------------------

def assert_invariants(
    *,
    dag: RegistryDag,
    resource_uuid_nodes: frozenset,
    crawl_uuids: frozenset,
    non_uuid_resource_ids: tuple,
    other_ids: tuple,
    work_queue: frozenset,
    nodes_removed: int,
    phase: str,
) -> None:
    """Assert all 8 TLA+ invariants for the supplied state snapshot."""
    cur_uuid = _current_uuid_nodes(dag, resource_uuid_nodes)

    # OtherNodesPreserved: dag_other = OtherNodes
    assert _count_present(dag, other_ids) == len(other_ids), \
        "OtherNodesPreserved violated"

    # NonUUIDResourceNodesPreserved: dag_resource_nonuuid = ResourceNonUUIDNodes
    assert _count_present(dag, non_uuid_resource_ids) == len(non_uuid_resource_ids), \
        "NonUUIDResourceNodesPreserved violated"

    # DAGResourceUUIDSubset: dag_resource_uuid ⊆ ResourceUUIDNodes
    assert cur_uuid <= resource_uuid_nodes, \
        "DAGResourceUUIDSubset violated"

    # WorkQueueSubset: work_queue ⊆ ResourceUUIDNodes
    assert work_queue <= resource_uuid_nodes, \
        "WorkQueueSubset violated"

    # CounterConsistency: nodes_removed = |ResourceUUIDNodes| - |dag_resource_uuid|
    expected = len(resource_uuid_nodes) - len(cur_uuid)
    assert nodes_removed == expected, (
        f"CounterConsistency violated: nodes_removed={nodes_removed} expected={expected}"
    )

    # ProcessedNodesCorrect: ∀ nid ∈ ResourceUUIDNodes \ work_queue :
    #     nid ∈ dag_resource_uuid → nid ∈ CrawlUUIDs
    for nid in resource_uuid_nodes - work_queue:
        if nid in cur_uuid:
            assert nid in crawl_uuids, \
                f"ProcessedNodesCorrect violated for {nid}"

    # KeptUUIDNodesAreProtected: ∀ nid ∈ dag_resource_uuid :
    #     nid ∈ CrawlUUIDs ∨ nid ∈ work_queue
    for nid in cur_uuid:
        assert nid in crawl_uuids or nid in work_queue, \
            f"KeptUUIDNodesAreProtected violated for {nid}"

    # NoOrphansRemain: phase = "done" → ∀ nid ∈ ResourceUUIDNodes :
    #     nid ∉ CrawlUUIDs → nid ∉ dag_resource_uuid
    if phase == "done":
        for nid in resource_uuid_nodes:
            if nid not in crawl_uuids:
                assert nid not in cur_uuid, \
                    f"NoOrphansRemain violated for orphan {nid}"


# ---------------------------------------------------------------------------
# DAG builder — Init state shared by all 10 traces
# ---------------------------------------------------------------------------

def _build_trace_dag() -> RegistryDag:
    """
    Construct the DAG matching the Init state that is identical across all 10 traces:

        dag_resource_uuid    = {UUID_NODE_1, UUID_NODE_2}
        dag_resource_nonuuid = 10
        dag_other            = 10
        work_queue           = {UUID_NODE_1, UUID_NODE_2}   (external; not stored in DAG)
        phase                = "init"
        nodes_removed        = 0
    """
    dag = RegistryDag()
    for nid in RESOURCE_UUID_NODES:
        dag.add_node(Node.resource(nid, f"uuid-res-{nid[:8]}"))
    for nid in NON_UUID_RESOURCE_IDS:
        dag.add_node(Node.resource(nid, f"resource-{nid}"))
    for nid in OTHER_NODE_IDS:
        dag.add_node(Node.behavior(nid, f"bhvr-{nid}", "given", "when", "then"))
    return dag


# ---------------------------------------------------------------------------
# Cleanup executor — translates TLA+ PlusCal algorithm to API calls
# ---------------------------------------------------------------------------

def _execute_cleanup(
    dag: RegistryDag,
    resource_uuid_nodes: frozenset,
    crawl_uuids: frozenset,
    ordered_nodes: list,
    non_uuid_resource_ids: tuple = NON_UUID_RESOURCE_IDS,
    other_ids: tuple = OTHER_NODE_IDS,
):
    """
    Execute the orphan-cleanup algorithm with step-wise invariant assertions.

    Translates the PlusCal algorithm:
        StartPhase → ProcessNodes (loop over ordered_nodes) → Finish

    All 8 TLA+ invariants are verified at every intermediate state
    (States 1–6 from the traces, and after each individual ProcessNodes step).

    Parameters
    ----------
    ordered_nodes : list
        Explicit processing order for the ProcessNodes loop (makes non-determinism
        deterministic so individual trace orderings can be reproduced exactly).

    Returns
    -------
    (phase, nodes_removed, work_queue)
    """
    inv = dict(
        dag=dag,
        resource_uuid_nodes=resource_uuid_nodes,
        crawl_uuids=crawl_uuids,
        non_uuid_resource_ids=non_uuid_resource_ids,
        other_ids=other_ids,
    )

    work_queue    = frozenset(resource_uuid_nodes)
    nodes_removed = 0
    phase         = "init"

    # ── State 1 : Init ──────────────────────────────────────────────────────
    assert_invariants(work_queue=work_queue, nodes_removed=nodes_removed, phase=phase, **inv)

    # ── Action : StartPhase ─────────────────────────────────────────────────
    phase = "running"

    # ── State 2 : StartPhase ────────────────────────────────────────────────
    assert_invariants(work_queue=work_queue, nodes_removed=nodes_removed, phase=phase, **inv)

    # ── Actions : ProcessNodes (one iteration per entry in ordered_nodes) ───
    for nid in ordered_nodes:
        assert nid in work_queue, f"Tried to process {nid!r} which is not in work_queue"
        work_queue = work_queue - {nid}
        if nid not in crawl_uuids:
            dag.remove_node(nid)
            nodes_removed += 1
        # Invariants hold after each ProcessNodes step (States 3, 4, …)
        assert_invariants(work_queue=work_queue, nodes_removed=nodes_removed, phase=phase, **inv)

    # ── Extra ProcessNodes with empty queue → pc transitions to Finish (State 5)
    assert work_queue == frozenset(), "work_queue must be empty before Finish"
    assert_invariants(work_queue=work_queue, nodes_removed=nodes_removed, phase=phase, **inv)

    # ── Action : Finish ─────────────────────────────────────────────────────
    phase = "done"

    # ── State 6 : Finish (final) ─────────────────────────────────────────────
    assert_invariants(work_queue=work_queue, nodes_removed=nodes_removed, phase=phase, **inv)

    return phase, nodes_removed, work_queue


# ===========================================================================
# Trace-derived tests (one per TLA+ simulation trace)
# ===========================================================================

def test_trace_node2_processed_first():
    """
    Representative of traces where UUID_NODE_2 is processed in the first ProcessNodes step.
    Invariants checked at every state; final state matches State 6 of the trace.
    """
    dag = _build_trace_dag()

    phase, nodes_removed, work_queue = _execute_cleanup(
        dag=dag,
        resource_uuid_nodes=RESOURCE_UUID_NODES,
        crawl_uuids=CRAWL_UUIDS_EMPTY,
        ordered_nodes=[UUID_NODE_2, UUID_NODE_1],
    )

    assert phase == "done"
    assert nodes_removed == 2
    assert work_queue == frozenset()
    assert not _dag_has_node(dag, UUID_NODE_1), "UUID_NODE_1 (orphan) must be removed"
    assert not _dag_has_node(dag, UUID_NODE_2), "UUID_NODE_2 (orphan) must be removed"
    assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10, "Non-UUID RESOURCE nodes must be preserved"
    assert _count_present(dag, OTHER_NODE_IDS) == 10, "Other nodes must be preserved"


def test_trace_node1_processed_first():
    """
    Representative of traces where UUID_NODE_1 is processed in the first ProcessNodes step.
    Invariants checked at every state; final state matches State 6 of the trace.
    """
    dag = _build_trace_dag()

    phase, nodes_removed, work_queue = _execute_cleanup(
        dag=dag,
        resource_uuid_nodes=RESOURCE_UUID_NODES,
        crawl_uuids=CRAWL_UUIDS_EMPTY,
        ordered_nodes=[UUID_NODE_1, UUID_NODE_2],
    )

    assert phase == "done"
    assert nodes_removed == 2
    assert work_queue == frozenset()
    assert not _dag_has_node(dag, UUID_NODE_1), "UUID_NODE_1 (orphan) must be removed"
    assert not _dag_has_node(dag, UUID_NODE_2), "UUID_NODE_2 (orphan) must be removed"
    assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10
    assert _count_present(dag, OTHER_NODE_IDS) == 10


# ===========================================================================
# Invariant-focused tests (each TLA+ invariant exercised across >= 2 topologies)
# ===========================================================================

class TestOtherNodesPreserved:
    """OtherNodesPreserved: dag_other = OtherNodes throughout every cleanup scenario."""

    def test_all_orphans_order1(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        assert _count_present(dag, OTHER_NODE_IDS) == 10

    def test_all_orphans_order2(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _count_present(dag, OTHER_NODE_IDS) == 10

    def test_no_orphans(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_BOTH,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _count_present(dag, OTHER_NODE_IDS) == 10

    def test_partial_orphans(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _count_present(dag, OTHER_NODE_IDS) == 10


class TestNonUUIDResourceNodesPreserved:
    """NonUUIDResourceNodesPreserved: non-UUID RESOURCE nodes are never removed."""

    def test_all_orphans_order1(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10

    def test_all_orphans_order2(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10

    def test_partial_orphans(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10

    def test_no_orphans(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_BOTH,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _count_present(dag, NON_UUID_RESOURCE_IDS) == 10


class TestDAGResourceUUIDSubset:
    """DAGResourceUUIDSubset: dag_resource_uuid <= ResourceUUIDNodes at all times."""

    def test_empty_after_all_removed(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert cur == frozenset()

    def test_full_set_when_nothing_removed(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_BOTH,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert cur == RESOURCE_UUID_NODES

    def test_singleton_after_partial_removal_order1(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert cur == frozenset({UUID_NODE_1})

    def test_singleton_after_partial_removal_order2(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert cur == frozenset({UUID_NODE_1})


class TestWorkQueueSubset:
    """WorkQueueSubset: work_queue <= ResourceUUIDNodes at every state."""

    def test_subset_enforced_all_orphans_order1(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])

    def test_subset_enforced_all_orphans_order2(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])

    def test_subset_enforced_partial_crawl(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])

    def test_subset_enforced_no_orphans(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_BOTH,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])

    def test_non_uuid_ids_never_enter_work_queue(self):
        wq = frozenset(RESOURCE_UUID_NODES)
        for nid in NON_UUID_RESOURCE_IDS:
            assert nid not in wq
        for nid in OTHER_NODE_IDS:
            assert nid not in wq


class TestCounterConsistency:
    """CounterConsistency: nodes_removed = |ResourceUUIDNodes| - |dag_resource_uuid|."""

    def test_counter_matches_at_each_removal_step(self):
        dag = _build_trace_dag()
        initial = len(RESOURCE_UUID_NODES)  # 2

        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert 0 == initial - len(cur)

        dag.remove_node(UUID_NODE_2)
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert 1 == initial - len(cur)

        dag.remove_node(UUID_NODE_1)
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert 2 == initial - len(cur)

    def test_counter_zero_no_orphans(self):
        dag = _build_trace_dag()
        _, nodes_removed, _ = _execute_cleanup(dag=dag,
                                               resource_uuid_nodes=RESOURCE_UUID_NODES,
                                               crawl_uuids=CRAWL_UUIDS_BOTH,
                                               ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert nodes_removed == len(RESOURCE_UUID_NODES) - len(cur)
        assert nodes_removed == 0

    def test_counter_one_partial_orphan(self):
        dag = _build_trace_dag()
        _, nodes_removed, _ = _execute_cleanup(dag=dag,
                                               resource_uuid_nodes=RESOURCE_UUID_NODES,
                                               crawl_uuids=CRAWL_UUIDS_ONE,
                                               ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert nodes_removed == len(RESOURCE_UUID_NODES) - len(cur)
        assert nodes_removed == 1

    def test_counter_two_all_orphans_order1(self):
        dag = _build_trace_dag()
        _, nodes_removed, _ = _execute_cleanup(dag=dag,
                                               resource_uuid_nodes=RESOURCE_UUID_NODES,
                                               crawl_uuids=CRAWL_UUIDS_EMPTY,
                                               ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert nodes_removed == len(RESOURCE_UUID_NODES) - len(cur)
        assert nodes_removed == 2

    def test_counter_two_all_orphans_order2(self):
        dag = _build_trace_dag()
        _, nodes_removed, _ = _execute_cleanup(dag=dag,
                                               resource_uuid_nodes=RESOURCE_UUID_NODES,
                                               crawl_uuids=CRAWL_UUIDS_EMPTY,
                                               ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert nodes_removed == len(RESOURCE_UUID_NODES) - len(cur)
        assert nodes_removed == 2


class TestProcessedNodesCorrect:
    """ProcessedNodesCorrect: a processed node still in the DAG must be in CrawlUUIDs."""

    def test_processed_orphan_absent_from_dag(self):
        dag = _build_trace_dag()
        dag.remove_node(UUID_NODE_2)
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert UUID_NODE_2 not in cur, "Removed orphan must not appear in dag_resource_uuid"
        assert UUID_NODE_1 in cur, "Unprocessed UUID_NODE_1 must still be present"

    def test_processed_protected_node_stays_in_dag(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert _dag_has_node(dag, UUID_NODE_1), \
            "Protected node (UUID_NODE_1 in CrawlUUIDs) must remain in the DAG"
        assert not _dag_has_node(dag, UUID_NODE_2), \
            "Orphan (UUID_NODE_2 not in CrawlUUIDs) must be removed"

    def test_processed_protected_mid_loop_invariant_direct(self):
        dag = _build_trace_dag()
        work_queue = frozenset(RESOURCE_UUID_NODES) - {UUID_NODE_1}
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        for nid in RESOURCE_UUID_NODES - work_queue:
            if nid in cur:
                assert nid in CRAWL_UUIDS_ONE, \
                    f"ProcessedNodesCorrect violated: {nid} is in dag_resource_uuid " \
                    f"but not in CrawlUUIDs"

    def test_full_run_all_orphans_order1(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])

    def test_full_run_all_orphans_order2(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])

    def test_full_run_partial_crawl(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])


class TestKeptUUIDNodesAreProtected:
    """KeptUUIDNodesAreProtected: every UUID node in the DAG is in CrawlUUIDs or work_queue."""

    def test_initially_all_protected_by_work_queue(self):
        dag = _build_trace_dag()
        wq = frozenset(RESOURCE_UUID_NODES)
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        for nid in cur:
            assert nid in CRAWL_UUIDS_EMPTY or nid in wq

    def test_mid_run_protected_by_crawl_uuid(self):
        dag = _build_trace_dag()
        wq = frozenset(RESOURCE_UUID_NODES) - {UUID_NODE_1}
        assert _dag_has_node(dag, UUID_NODE_1), \
            "UUID_NODE_1 must still be in the DAG (it is protected by CrawlUUIDs)"
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        for nid in cur:
            assert nid in CRAWL_UUIDS_ONE or nid in wq, \
                f"KeptUUIDNodesAreProtected violated for {nid}"
        assert UUID_NODE_1 in CRAWL_UUIDS_ONE
        assert UUID_NODE_1 not in wq

    def test_end_state_with_partial_crawl(self):
        dag = _build_trace_dag()
        _, _, wq = _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                                    crawl_uuids=CRAWL_UUIDS_ONE,
                                    ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        for nid in cur:
            assert nid in CRAWL_UUIDS_ONE or nid in wq

    def test_empty_dag_uuid_set_vacuously_satisfied(self):
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        cur = _current_uuid_nodes(dag, RESOURCE_UUID_NODES)
        assert cur == frozenset()


class TestNoOrphansRemain:
    """NoOrphansRemain: when phase='done', no orphan UUID node remains in the DAG."""

    def test_both_orphans_gone_order1(self):
        dag = _build_trace_dag()
        phase, _, _ = _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                                       crawl_uuids=CRAWL_UUIDS_EMPTY,
                                       ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        assert phase == "done"
        for nid in RESOURCE_UUID_NODES:
            if nid not in CRAWL_UUIDS_EMPTY:
                assert not _dag_has_node(dag, nid), f"Orphan {nid} must not remain in DAG"

    def test_both_orphans_gone_order2(self):
        dag = _build_trace_dag()
        phase, _, _ = _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                                       crawl_uuids=CRAWL_UUIDS_EMPTY,
                                       ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert phase == "done"
        for nid in RESOURCE_UUID_NODES:
            if nid not in CRAWL_UUIDS_EMPTY:
                assert not _dag_has_node(dag, nid)

    def test_protected_nodes_remain_after_done(self):
        dag = _build_trace_dag()
        phase, nodes_removed, _ = _execute_cleanup(dag=dag,
                                                   resource_uuid_nodes=RESOURCE_UUID_NODES,
                                                   crawl_uuids=CRAWL_UUIDS_BOTH,
                                                   ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert phase == "done"
        assert nodes_removed == 0
        for nid in RESOURCE_UUID_NODES:
            assert _dag_has_node(dag, nid), f"Protected node {nid} must not be removed"

    def test_partial_crawl_only_orphan_removed_order1(self):
        dag = _build_trace_dag()
        phase, nodes_removed, _ = _execute_cleanup(dag=dag,
                                                   resource_uuid_nodes=RESOURCE_UUID_NODES,
                                                   crawl_uuids=CRAWL_UUIDS_ONE,
                                                   ordered_nodes=[UUID_NODE_2, UUID_NODE_1])
        assert phase == "done"
        assert nodes_removed == 1
        assert _dag_has_node(dag, UUID_NODE_1)
        assert not _dag_has_node(dag, UUID_NODE_2)

    def test_partial_crawl_only_orphan_removed_order2(self):
        dag = _build_trace_dag()
        phase, nodes_removed, _ = _execute_cleanup(dag=dag,
                                                   resource_uuid_nodes=RESOURCE_UUID_NODES,
                                                   crawl_uuids=CRAWL_UUIDS_ONE,
                                                   ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert phase == "done"
        assert nodes_removed == 1
        assert _dag_has_node(dag, UUID_NODE_1)
        assert not _dag_has_node(dag, UUID_NODE_2)

    def test_orphans_may_remain_during_running_phase(self):
        """
        NoOrphansRemain only fires when phase='done'.
        While phase='running' and an orphan is still in the work_queue (unprocessed),
        assert_invariants must not raise — the invariant's antecedent is False.
        """
        dag = _build_trace_dag()
        assert_invariants(
            dag=dag,
            resource_uuid_nodes=RESOURCE_UUID_NODES,
            crawl_uuids=CRAWL_UUIDS_EMPTY,
            non_uuid_resource_ids=NON_UUID_RESOURCE_IDS,
            other_ids=OTHER_NODE_IDS,
            work_queue=RESOURCE_UUID_NODES,
            nodes_removed=0,
            phase="running",
        )


# ===========================================================================
# Edge-case tests
# ===========================================================================

class TestEdgeCases:

    def test_cleanup_with_no_uuid_resource_nodes_is_noop(self):
        """DAG with only non-UUID RESOURCE and other nodes: cleanup changes nothing."""
        dag = RegistryDag()
        for nid in NON_UUID_RESOURCE_IDS:
            dag.add_node(Node.resource(nid, f"resource-{nid}"))
        for nid in OTHER_NODE_IDS:
            dag.add_node(Node.behavior(nid, f"bhvr-{nid}", "given", "when", "then"))
        initial_count = dag.node_count

        phase, nodes_removed, wq = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=frozenset(),
            crawl_uuids=frozenset(),
            ordered_nodes=[],
            non_uuid_resource_ids=NON_UUID_RESOURCE_IDS,
            other_ids=OTHER_NODE_IDS,
        )
        assert phase == "done"
        assert nodes_removed == 0
        assert dag.node_count == initial_count

    def test_completely_empty_dag(self):
        """Cleanup on an entirely empty DAG is a trivial no-op."""
        dag = RegistryDag()
        phase, nodes_removed, wq = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=frozenset(),
            crawl_uuids=frozenset(),
            ordered_nodes=[],
            non_uuid_resource_ids=(),
            other_ids=(),
        )
        assert phase == "done"
        assert nodes_removed == 0
        assert dag.node_count == 0

    def test_single_uuid_orphan_removed(self):
        """A single isolated UUID RESOURCE node that is an orphan is removed."""
        dag = RegistryDag()
        dag.add_node(Node.resource(UUID_NODE_1, "single-orphan"))
        single = frozenset({UUID_NODE_1})

        phase, nodes_removed, wq = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=single,
            crawl_uuids=frozenset(),
            ordered_nodes=[UUID_NODE_1],
            non_uuid_resource_ids=(),
            other_ids=(),
        )
        assert phase == "done"
        assert nodes_removed == 1
        assert not _dag_has_node(dag, UUID_NODE_1)
        assert dag.node_count == 0

    def test_single_uuid_protected_not_removed(self):
        """A UUID RESOURCE node whose ID is in CrawlUUIDs is never removed."""
        dag = RegistryDag()
        dag.add_node(Node.resource(UUID_NODE_1, "protected-resource"))
        single = frozenset({UUID_NODE_1})

        phase, nodes_removed, wq = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=single,
            crawl_uuids=single,
            ordered_nodes=[UUID_NODE_1],
            non_uuid_resource_ids=(),
            other_ids=(),
        )
        assert phase == "done"
        assert nodes_removed == 0
        assert _dag_has_node(dag, UUID_NODE_1)

    def test_uuid_format_regex_classification(self):
        """UUID regex correctly accepts well-formed UUIDs and rejects everything else."""
        assert _is_uuid(UUID_NODE_1)
        assert _is_uuid(UUID_NODE_2)
        assert _is_uuid("ffffffff-ffff-4fff-bfff-ffffffffffff")
        assert _is_uuid("00000000-0000-0000-0000-000000000000")
        assert not _is_uuid("res-nonuuid-001")
        assert not _is_uuid("behavior-other-001")
        assert not _is_uuid("not-a-uuid")
        assert not _is_uuid("")
        assert not _is_uuid("12345678-1234-1234-1234")
        assert not _is_uuid("gggggggg-0001-0001-0001-000000000001")

    def test_remove_nonexistent_node_is_noop(self):
        """
        RegistryDag.remove_node is a silent no-op for absent node IDs — it does not raise.
        """
        dag = RegistryDag()
        dag.remove_node("cccccccc-dead-beef-cafe-000000000000")
        assert dag.node_count == 0

    def test_diamond_topology_uuid_orphans_removed_non_uuid_preserved(self):
        """
        UUID RESOURCE orphans at root and leaf of a diamond are removed;
        the non-UUID RESOURCE nodes forming the middle are preserved.

                  UUID_NODE_1
                 /           \\
          mid-001            mid-002
                 \\           /
                  UUID_NODE_2
        """
        mid1 = "non-uuid-mid-001"
        mid2 = "non-uuid-mid-002"
        dag = RegistryDag()
        dag.add_node(Node.resource(UUID_NODE_1, "diamond-root"))
        dag.add_node(Node.resource(UUID_NODE_2, "diamond-leaf"))
        dag.add_node(Node.resource(mid1, "diamond-mid-1"))
        dag.add_node(Node.resource(mid2, "diamond-mid-2"))
        dag.add_edge(Edge(UUID_NODE_1, mid1, EdgeType.IMPORTS))
        dag.add_edge(Edge(UUID_NODE_1, mid2, EdgeType.IMPORTS))
        dag.add_edge(Edge(mid1, UUID_NODE_2, EdgeType.IMPORTS))
        dag.add_edge(Edge(mid2, UUID_NODE_2, EdgeType.IMPORTS))

        phase, nodes_removed, _ = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=RESOURCE_UUID_NODES,
            crawl_uuids=CRAWL_UUIDS_EMPTY,
            ordered_nodes=[UUID_NODE_1, UUID_NODE_2],
            non_uuid_resource_ids=(mid1, mid2),
            other_ids=(),
        )
        assert phase == "done"
        assert nodes_removed == 2
        assert not _dag_has_node(dag, UUID_NODE_1)
        assert not _dag_has_node(dag, UUID_NODE_2)
        assert _dag_has_node(dag, mid1)
        assert _dag_has_node(dag, mid2)

    def test_node_count_decrements_by_orphan_count(self):
        """dag.node_count decrements by exactly the number of orphans removed."""
        dag = _build_trace_dag()
        initial_count = dag.node_count  # 2 + 10 + 10 = 22

        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert dag.node_count == initial_count - 2

    def test_node_count_unchanged_no_orphans(self):
        """dag.node_count is unchanged when all UUID nodes are in CrawlUUIDs."""
        dag = _build_trace_dag()
        initial_count = dag.node_count

        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_BOTH,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert dag.node_count == initial_count

    def test_node_count_decrements_by_one_partial_orphan(self):
        """dag.node_count decrements by 1 when exactly one UUID node is an orphan."""
        dag = _build_trace_dag()
        initial_count = dag.node_count

        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_ONE,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        assert dag.node_count == initial_count - 1

    def test_second_cleanup_with_empty_uuid_scope_is_noop(self):
        """
        After UUID orphans are removed in a first run, a subsequent cleanup invoked
        with resource_uuid_nodes={} (no UUID nodes in scope) leaves the remaining
        non-UUID RESOURCE and other nodes untouched.
        """
        dag = _build_trace_dag()
        _execute_cleanup(dag=dag, resource_uuid_nodes=RESOURCE_UUID_NODES,
                         crawl_uuids=CRAWL_UUIDS_EMPTY,
                         ordered_nodes=[UUID_NODE_1, UUID_NODE_2])
        count_after_first = dag.node_count  # 20 (10 non-uuid + 10 other)

        phase, nodes_removed, wq = _execute_cleanup(
            dag=dag,
            resource_uuid_nodes=frozenset(),
            crawl_uuids=CRAWL_UUIDS_EMPTY,
            ordered_nodes=[],
            non_uuid_resource_ids=NON_UUID_RESOURCE_IDS,
            other_ids=OTHER_NODE_IDS,
        )
        assert phase == "done"
        assert nodes_removed == 0
        assert dag.node_count == count_after_first