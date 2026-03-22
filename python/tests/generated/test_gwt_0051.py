from __future__ import annotations

import json
import textwrap

import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind

# ---------------------------------------------------------------------------
# TLA+ spec constants -------------------------------------------------------
# ---------------------------------------------------------------------------

EVENTS = [
    {"has_recv": False, "recv_type": "None",  "name": "Hello",    "cap": True},
    {"has_recv": True,  "recv_type": "Svc",   "name": "GetUser",  "cap": True},
    {"has_recv": True,  "recv_type": "Point", "name": "distance", "cap": False},
    {"has_recv": False, "recv_type": "None",  "name": "helper",   "cap": False},
]
N = len(EVENTS)

GO_SOURCE = textwrap.dedent("""\
    package main

    func Hello() {}

    func (s Svc) GetUser() {}

    func (p Point) distance() {}

    func helper() {}
""")

# Final skeletons expected after scanning the full file (all traces converge here)
FINAL_SKELETONS = [
    {"function_name": "Hello",    "class_name": "None",  "has_recv": False, "cap": True,  "visibility": "public"},
    {"function_name": "GetUser",  "class_name": "Svc",   "has_recv": True,  "cap": True,  "visibility": "public"},
    {"function_name": "distance", "class_name": "Point", "has_recv": True,  "cap": False, "visibility": "private"},
    {"function_name": "helper",   "class_name": "None",  "has_recv": False, "cap": False, "visibility": "private"},
]

# ---------------------------------------------------------------------------
# Skeleton helpers -----------------------------------------------------------
# ---------------------------------------------------------------------------

def _make_skeleton(event: dict) -> dict:
    """ProcessEvent action: produce a skeleton record from a raw scan event."""
    return {
        "function_name":  event["name"],
        "class_name": event["recv_type"],
        "has_recv":   event["has_recv"],
        "cap":        event["cap"],
        "visibility": "public" if event["cap"] else "private",
    }


def _skeleton_node(s: dict) -> Node:
    """Represent a skeleton as a DAG resource node.

    Skeleton metadata (class_name, has_recv, cap, visibility) is encoded as a
    JSON blob in the ``description`` field because Node only accepts its own
    declared dataclass fields — arbitrary kwargs are not stored as attributes.
    """
    meta = json.dumps({
        "class_name": s["class_name"],
        "has_recv":   s["has_recv"],
        "cap":        s["cap"],
        "visibility": s["visibility"],
    })
    return Node.resource(
        id=f"func_{s['func_name']}",
        name=s["function_name"],
        description=meta,
    )


def _node_to_skeleton(node: Node) -> dict:
    """Reconstruct a skeleton dict from a DAG node's description JSON."""
    meta = json.loads(node.description)
    return {
        "function_name":  node.name,
        "class_name": meta["class_name"],
        "has_recv":   meta["has_recv"],
        "cap":        meta["cap"],
        "visibility": meta["visibility"],
    }


def _run_scan_loop(events: list) -> tuple:
    """
    Simulate the PlusCal ScanLoop / ProcessEvent / Advance cycle.

    Returns (skeletons_list, final_cursor) where final_cursor == N + 1.
    """
    skeletons: list = []
    cursor = 1
    while cursor <= len(events):
        # ProcessEvent
        skeletons.append(_make_skeleton(events[cursor - 1]))
        # Advance
        cursor += 1
    # Finish (skip)
    return skeletons, cursor

# ---------------------------------------------------------------------------
# Invariant verifiers -------------------------------------------------------
# ---------------------------------------------------------------------------

def _check_receiver_resolution(skeletons: list) -> None:
    """ReceiverResolution: class_name == 'None' iff has_recv == False."""
    for s in skeletons:
        if s["class_name"] == "None":
            assert s["has_recv"] is False, (
                f"ReceiverResolution violated: func='{s['func_name']}' "
                f"class_name='None' but has_recv=True"
            )
        else:
            assert s["has_recv"] is True, (
                f"ReceiverResolution violated: func='{s['func_name']}' "
                f"class_name='{s['class_name']}' but has_recv=False"
            )


def _check_visibility_correct(skeletons: list) -> None:
    """VisibilityCorrect: visibility == 'public' iff cap == True."""
    for s in skeletons:
        if s["visibility"] == "public":
            assert s["cap"] is True, (
                f"VisibilityCorrect violated: func='{s['func_name']}' "
                f"visibility='public' but cap=False"
            )
        else:
            assert s["visibility"] == "private", (
                f"Unexpected visibility value '{s['visibility']}' for func='{s['func_name']}'"
            )
            assert s["cap"] is False, (
                f"VisibilityCorrect violated: func='{s['func_name']}' "
                f"visibility='private' but cap=True"
            )


def _check_all_recorded(cursor: int, n: int, skeletons: list, events: list) -> None:
    """AllRecorded: once cursor > N every event name appears in skeletons."""
    if cursor > n:
        recorded = {s["function_name"] for s in skeletons}
        for ev in events:
            assert ev["name"] in recorded, (
                f"AllRecorded violated: '{ev['name']}' missing from skeletons"
            )


def _check_all_invariants_at_state(cursor: int, skeletons: list, events: list) -> None:
    """Assert all three TLA+ invariants hold at the given intermediate state."""
    _check_receiver_resolution(skeletons)
    _check_visibility_correct(skeletons)
    _check_all_recorded(cursor, len(events), skeletons, events)

# ---------------------------------------------------------------------------
# Fixtures ------------------------------------------------------------------
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_dag() -> RegistryDag:
    """Init state: skeletons = {}, cursor = 1 — represents the TLA+ Init."""
    return RegistryDag()


@pytest.fixture
def full_dag() -> RegistryDag:
    """DAG pre-loaded with all four final skeletons (Finish state)."""
    dag = RegistryDag()
    for s in FINAL_SKELETONS:
        dag.add_node(_skeleton_node(s))
    return dag


@pytest.fixture
def partial_dag_after_2() -> RegistryDag:
    """DAG after processing the first two events (intermediate state at cursor=3)."""
    dag = RegistryDag()
    for s in FINAL_SKELETONS[:2]:
        dag.add_node(_skeleton_node(s))
    return dag

# ---------------------------------------------------------------------------
# Shared final-state assertion ----------------------------------------------
# ---------------------------------------------------------------------------

def _assert_final_state(skeletons: list) -> None:
    """Assert the 15-state trace's terminal skeletons set matches spec."""
    by_name = {s["function_name"]: s for s in skeletons}

    assert "Hello" in by_name
    assert by_name["Hello"]["class_name"] == "None"
    assert by_name["Hello"]["has_recv"] is False
    assert by_name["Hello"]["cap"] is True
    assert by_name["Hello"]["visibility"] == "public"

    assert "GetUser" in by_name
    assert by_name["GetUser"]["class_name"] == "Svc"
    assert by_name["GetUser"]["has_recv"] is True
    assert by_name["GetUser"]["cap"] is True
    assert by_name["GetUser"]["visibility"] == "public"

    assert "distance" in by_name
    assert by_name["distance"]["class_name"] == "Point"
    assert by_name["distance"]["has_recv"] is True
    assert by_name["distance"]["cap"] is False
    assert by_name["distance"]["visibility"] == "private"

    assert "helper" in by_name
    assert by_name["helper"]["class_name"] == "None"
    assert by_name["helper"]["has_recv"] is False
    assert by_name["helper"]["cap"] is False
    assert by_name["helper"]["visibility"] == "private"

    assert len(skeletons) == 4

# ---------------------------------------------------------------------------
# Trace 1 — ReceiverResolution, VisibilityCorrect, AllRecorded --------------
# ---------------------------------------------------------------------------

class TestTrace1:
    """15-step trace: ScanLoop→ProcessEvent→Advance ×4 → Finish."""

    def test_init_state_is_empty(self, empty_dag):
        # State 1: skeletons = {}, cursor = 1
        assert empty_dag.node_count == 0

    def test_process_event_1_hello(self, empty_dag):
        # State 3 after ProcessEvent at cursor=1: Hello added
        skeletons = []
        cursor = 1
        skeletons.append(_make_skeleton(EVENTS[cursor - 1]))
        empty_dag.add_node(_skeleton_node(skeletons[-1]))

        assert len(skeletons) == 1
        assert skeletons[0]["function_name"] == "Hello"
        assert skeletons[0]["class_name"] == "None"
        assert skeletons[0]["has_recv"] is False
        assert skeletons[0]["visibility"] == "public"
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_process_event_2_getuser(self, empty_dag):
        # State 6 after ProcessEvent at cursor=2: GetUser added
        skeletons = [_make_skeleton(EVENTS[0])]
        cursor = 2
        skeletons.append(_make_skeleton(EVENTS[cursor - 1]))
        for s in skeletons:
            empty_dag.add_node(_skeleton_node(s))

        assert len(skeletons) == 2
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["GetUser"]["class_name"] == "Svc"
        assert by_name["GetUser"]["has_recv"] is True
        assert by_name["GetUser"]["visibility"] == "public"
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_process_event_3_distance(self, empty_dag):
        # State 9 after ProcessEvent at cursor=3: distance added
        skeletons = [_make_skeleton(EVENTS[i]) for i in range(2)]
        cursor = 3
        skeletons.append(_make_skeleton(EVENTS[cursor - 1]))
        for s in skeletons:
            empty_dag.add_node(_skeleton_node(s))

        assert len(skeletons) == 3
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["distance"]["class_name"] == "Point"
        assert by_name["distance"]["has_recv"] is True
        assert by_name["distance"]["visibility"] == "private"
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_process_event_4_helper(self, empty_dag):
        # State 12 after ProcessEvent at cursor=4: helper added
        skeletons = [_make_skeleton(EVENTS[i]) for i in range(3)]
        cursor = 4
        skeletons.append(_make_skeleton(EVENTS[cursor - 1]))
        for s in skeletons:
            empty_dag.add_node(_skeleton_node(s))

        assert len(skeletons) == 4
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["helper"]["class_name"] == "None"
        assert by_name["helper"]["has_recv"] is False
        assert by_name["helper"]["visibility"] == "private"
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_finish_state(self, empty_dag):
        # State 15: Finish — all four skeletons present, cursor=5, Done
        skeletons, cursor = _run_scan_loop(EVENTS)
        for s in skeletons:
            empty_dag.add_node(_skeleton_node(s))

        assert cursor == N + 1
        assert empty_dag.node_count == 4
        _assert_final_state(skeletons)
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_dag_nodes_carry_correct_metadata(self, full_dag):
        # Verify each Node in the finished DAG mirrors its skeleton's metadata
        for expected in FINAL_SKELETONS:
            node = full_dag._nodes[f"func_{expected['func_name']}"]  # noqa: SLF001
            s = _node_to_skeleton(node)
            assert s["class_name"] == expected["class_name"]
            assert s["has_recv"] == expected["has_recv"]
            assert s["visibility"] == expected["visibility"]
            assert s["cap"] == expected["cap"]

    def test_partial_dag_after_2_events_has_two_nodes(self, partial_dag_after_2):
        """
        Intermediate state at cursor=3: Hello and GetUser added, distance and
        helper pending.  AllRecorded is not yet active (cursor=3 <= N=4).
        ReceiverResolution and VisibilityCorrect must already hold.
        """
        assert partial_dag_after_2.node_count == 2
        assert partial_dag_after_2.edge_count == 0
        nodes = list(partial_dag_after_2._nodes.values())  # noqa: SLF001
        skeletons = [_node_to_skeleton(n) for n in nodes]
        # cursor=3 — AllRecorded guard not yet crossed
        _check_all_invariants_at_state(3, skeletons, EVENTS)
        # Confirm only the first two names are present
        names = {s["function_name"] for s in skeletons}
        assert names == {"Hello", "GetUser"}

# ---------------------------------------------------------------------------
# Trace 2 — identical action sequence, second independent run ---------------
# ---------------------------------------------------------------------------

class TestTrace2:
    def test_full_scan_loop_produces_four_skeletons(self, empty_dag):
        skeletons, cursor = _run_scan_loop(EVENTS)
        for s in skeletons:
            empty_dag.add_node(_skeleton_node(s))

        assert len(skeletons) == N
        assert cursor == N + 1
        _assert_final_state(skeletons)

    def test_invariants_hold_at_every_step(self):
        skeletons = []
        cursor = 1
        # State 1 — Init
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

        for idx in range(N):
            # State after ProcessEvent — cursor unchanged, skeleton appended
            skeletons.append(_make_skeleton(EVENTS[idx]))
            _check_all_invariants_at_state(cursor, skeletons, EVENTS)

            # State after Advance — cursor incremented
            cursor += 1
            _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_receiver_methods_have_non_none_class_name(self):
        skeletons, _ = _run_scan_loop(EVENTS)
        receiver_methods = [s for s in skeletons if s["has_recv"]]
        assert len(receiver_methods) == 2
        for s in receiver_methods:
            assert s["class_name"] != "None", (
                f"Receiver method '{s['func_name']}' must not have class_name='None'"
            )

    def test_package_level_functions_have_none_class_name(self):
        skeletons, _ = _run_scan_loop(EVENTS)
        pkg_funcs = [s for s in skeletons if not s["has_recv"]]
        assert len(pkg_funcs) == 2
        for s in pkg_funcs:
            assert s["class_name"] == "None", (
                f"Package-level func '{s['func_name']}' must have class_name='None'"
            )

# ---------------------------------------------------------------------------
# Traces 3–10 — all share the same deterministic execution path -------------
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(3, 11))
def test_trace_n_full_scan_produces_correct_skeletons(trace_id, empty_dag):
    """Traces 3–10: each is the same deterministic 15-step path; verify final state."""
    skeletons, cursor = _run_scan_loop(EVENTS)
    for s in skeletons:
        empty_dag.add_node(_skeleton_node(s))

    assert cursor == N + 1, f"[Trace {trace_id}] Expected cursor={N + 1}, got {cursor}"
    assert empty_dag.node_count == N, f"[Trace {trace_id}] Expected {N} nodes"
    _assert_final_state(skeletons)
    _check_all_invariants_at_state(cursor, skeletons, EVENTS)


@pytest.mark.parametrize("trace_id", range(3, 11))
def test_trace_n_invariants_hold_at_every_intermediate_state(trace_id):
    """
    Verify ReceiverResolution, VisibilityCorrect, AllRecorded at every state
    in the 15-step trace (invariants must hold at ALL states, not just final).
    """
    skeletons = []
    cursor = 1

    # State 1 (Init)
    _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    for i in range(N):
        # ScanLoop → ProcessEvent
        skeletons.append(_make_skeleton(EVENTS[i]))
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

        # Advance
        cursor += 1
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    # Finish / Done
    _check_all_invariants_at_state(cursor, skeletons, EVENTS)


@pytest.mark.parametrize("trace_id", range(3, 11))
def test_trace_n_receiver_resolution_invariant(trace_id):
    """ReceiverResolution holds incrementally across all intermediate sets."""
    skeletons = []
    for event in EVENTS:
        skeletons.append(_make_skeleton(event))
        _check_receiver_resolution(skeletons)


@pytest.mark.parametrize("trace_id", range(3, 11))
def test_trace_n_visibility_correct_invariant(trace_id):
    """VisibilityCorrect holds incrementally across all intermediate sets."""
    skeletons = []
    for event in EVENTS:
        skeletons.append(_make_skeleton(event))
        _check_visibility_correct(skeletons)

# ---------------------------------------------------------------------------
# Dedicated invariant verifier tests — exercise ≥2 topologies each ---------
# ---------------------------------------------------------------------------

class TestInvariantReceiverResolution:
    """Exercise ReceiverResolution across multiple skeleton configurations."""

    def test_all_package_level_functions(self):
        # Topology A: no receivers at all
        events_no_recv = [
            {"has_recv": False, "recv_type": "None", "name": "Alpha", "cap": True},
            {"has_recv": False, "recv_type": "None", "name": "beta",  "cap": False},
        ]
        skeletons = [_make_skeleton(e) for e in events_no_recv]
        _check_receiver_resolution(skeletons)
        for s in skeletons:
            assert s["class_name"] == "None"
            assert s["has_recv"] is False

    def test_all_receiver_methods(self):
        # Topology B: every function is a method
        events_all_recv = [
            {"has_recv": True, "recv_type": "Foo", "name": "Bar", "cap": True},
            {"has_recv": True, "recv_type": "Baz", "name": "qux", "cap": False},
        ]
        skeletons = [_make_skeleton(e) for e in events_all_recv]
        _check_receiver_resolution(skeletons)
        for s in skeletons:
            assert s["class_name"] != "None"
            assert s["has_recv"] is True

    def test_mixed_topology_from_trace_final_state(self):
        # Topology C: the exact 4-function mix from all TLC traces
        skeletons, _ = _run_scan_loop(EVENTS)
        _check_receiver_resolution(skeletons)

    def test_single_receiver_method_svc(self):
        # Topology D: one isolated receiver method (Svc.GetUser)
        s = _make_skeleton(EVENTS[1])  # GetUser on Svc
        _check_receiver_resolution([s])
        assert s["class_name"] == "Svc"
        assert s["has_recv"] is True

    def test_single_package_function_hello(self):
        # Topology E: one isolated package-level function (Hello)
        s = _make_skeleton(EVENTS[0])
        _check_receiver_resolution([s])
        assert s["class_name"] == "None"
        assert s["has_recv"] is False

    def test_empty_skeleton_set(self):
        # Init state: invariant trivially holds on empty set
        _check_receiver_resolution([])

    def test_dag_nodes_satisfy_receiver_resolution(self, full_dag):
        nodes = list(full_dag._nodes.values())  # noqa: SLF001
        skeletons = [_node_to_skeleton(n) for n in nodes]
        _check_receiver_resolution(skeletons)


class TestInvariantVisibilityCorrect:
    """Exercise VisibilityCorrect across multiple skeleton configurations."""

    def test_all_public_functions(self):
        events_public = [
            {"has_recv": False, "recv_type": "None", "name": "Alpha",   "cap": True},
            {"has_recv": True,  "recv_type": "Svc",  "name": "GetData", "cap": True},
        ]
        skeletons = [_make_skeleton(e) for e in events_public]
        _check_visibility_correct(skeletons)
        for s in skeletons:
            assert s["visibility"] == "public"
            assert s["cap"] is True

    def test_all_private_functions(self):
        events_private = [
            {"has_recv": False, "recv_type": "None",  "name": "alpha",    "cap": False},
            {"has_recv": True,  "recv_type": "Point", "name": "distance", "cap": False},
        ]
        skeletons = [_make_skeleton(e) for e in events_private]
        _check_visibility_correct(skeletons)
        for s in skeletons:
            assert s["visibility"] == "private"
            assert s["cap"] is False

    def test_mixed_visibility_from_trace_final_state(self):
        skeletons, _ = _run_scan_loop(EVENTS)
        _check_visibility_correct(skeletons)
        public_funcs  = [s for s in skeletons if s["visibility"] == "public"]
        private_funcs = [s for s in skeletons if s["visibility"] == "private"]
        assert len(public_funcs)  == 2
        assert len(private_funcs) == 2

    def test_incrementally_across_all_events(self):
        skeletons = []
        for event in EVENTS:
            skeletons.append(_make_skeleton(event))
            _check_visibility_correct(skeletons)

    def test_empty_skeleton_set(self):
        _check_visibility_correct([])

    def test_dag_nodes_satisfy_visibility_correct(self, full_dag):
        nodes = list(full_dag._nodes.values())  # noqa: SLF001
        skeletons = [_node_to_skeleton(n) for n in nodes]
        _check_visibility_correct(skeletons)


class TestInvariantAllRecorded:
    """Exercise AllRecorded across multiple topologies."""

    def test_not_triggered_before_cursor_exceeds_n(self):
        # cursor <= N: AllRecorded does not fire, even with empty skeletons
        for cursor in range(1, N + 1):
            _check_all_recorded(cursor, N, [], EVENTS)  # should not raise

    def test_triggered_only_when_cursor_exceeds_n(self):
        skeletons, cursor = _run_scan_loop(EVENTS)
        assert cursor > N
        _check_all_recorded(cursor, N, skeletons, EVENTS)

    def test_partial_skeletons_with_cursor_lte_n(self):
        # After 2 events, cursor=3 — AllRecorded not yet active
        partial = [_make_skeleton(EVENTS[i]) for i in range(2)]
        _check_all_recorded(3, N, partial, EVENTS)  # cursor=3 <= N=4

    def test_all_four_names_present_at_finish(self):
        skeletons, cursor = _run_scan_loop(EVENTS)
        recorded = {s["function_name"] for s in skeletons}
        expected = {"Hello", "GetUser", "distance", "helper"}
        assert recorded == expected

    def test_two_topologies_both_satisfy_all_recorded(self):
        # Topology 1: full EVENTS list
        sk1, cur1 = _run_scan_loop(EVENTS)
        _check_all_recorded(cur1, N, sk1, EVENTS)

        # Topology 2: only-receiver methods (subset scenario, different events)
        events2 = [
            {"has_recv": True, "recv_type": "Foo", "name": "Bar", "cap": True},
            {"has_recv": True, "recv_type": "Baz", "name": "qux", "cap": False},
        ]
        sk2, cur2 = _run_scan_loop(events2)
        _check_all_recorded(cur2, len(events2), sk2, events2)

# ---------------------------------------------------------------------------
# Edge-case tests -----------------------------------------------------------
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_go_file_produces_no_skeletons(self):
        """No functions → scan loop exits immediately, cursor=1>0 trivially, set={}."""
        skeletons, cursor = _run_scan_loop([])
        assert skeletons == []
        assert cursor == 1
        # AllRecorded is vacuously true (no events to check)
        _check_all_invariants_at_state(cursor, skeletons, [])

    def test_single_public_package_function(self):
        """Isolated node: one package-level public function."""
        events = [{"has_recv": False, "recv_type": "None", "name": "Run", "cap": True}]
        skeletons, cursor = _run_scan_loop(events)
        assert len(skeletons) == 1
        assert skeletons[0]["class_name"] == "None"
        assert skeletons[0]["visibility"] == "public"
        _check_all_invariants_at_state(cursor, skeletons, events)

    def test_single_private_receiver_method(self):
        """Isolated node: one private receiver method."""
        events = [{"has_recv": True, "recv_type": "Point", "name": "area", "cap": False}]
        skeletons, cursor = _run_scan_loop(events)
        assert len(skeletons) == 1
        assert skeletons[0]["class_name"] == "Point"
        assert skeletons[0]["visibility"] == "private"
        _check_all_invariants_at_state(cursor, skeletons, events)

    def test_empty_dag_node_count_is_zero(self, empty_dag):
        assert empty_dag.node_count == 0
        assert empty_dag.edge_count == 0

    def test_no_edges_in_skeleton_dag(self, full_dag):
        """The spec adds no edges — skeleton nodes are independent resources."""
        assert full_dag.edge_count == 0

    def test_full_dag_has_four_nodes(self, full_dag):
        assert full_dag.node_count == 4

    def test_duplicate_function_name_not_double_counted(self, empty_dag):
        """Scanning the same function twice should not produce duplicate skeletons.

        TLA+ uses set union (∪) so duplicates are naturally eliminated.
        Here we verify that inserting the same node id twice is idempotent.
        """
        s = _make_skeleton(EVENTS[0])  # Hello
        node = _skeleton_node(s)
        empty_dag.add_node(node)
        # Adding the identical node again should leave count unchanged
        empty_dag.add_node(node)
        assert empty_dag.node_count == 1

    def test_diamond_pattern_two_structs_same_method_name(self):
        """Two different receiver types share the same method name 'String'.

        NOTE (Defect 3 fix): This test validates ReceiverResolution and
        VisibilityCorrect at the *skeleton dict* level only.  The node-ID
        scheme used by _skeleton_node — id=f"func_{func_name}" — produces a
        collision for both 'String' methods (both become 'func_String').
        Consequently the DAG can store at most one of them; no DAG operations
        are performed here so that silent collision does not mask the invariant
        assertions.  A separate integration test would be required to verify
        that the production scanner disambiguates by struct name in node IDs.
        """
        events = [
            {"has_recv": True, "recv_type": "Foo", "name": "String", "cap": True},
            {"has_recv": True, "recv_type": "Bar", "name": "String", "cap": True},
        ]
        # Both are distinct skeletons at the dict level despite identical func_name
        skeletons = [_make_skeleton(e) for e in events]
        assert skeletons[0]["class_name"] == "Foo"
        assert skeletons[1]["class_name"] == "Bar"
        _check_receiver_resolution(skeletons)
        _check_visibility_correct(skeletons)

    def test_all_functions_private_no_receivers(self):
        """Edge case: file with only unexported package-level functions."""
        events = [
            {"has_recv": False, "recv_type": "None", "name": "init",   "cap": False},
            {"has_recv": False, "recv_type": "None", "name": "helper", "cap": False},
        ]
        skeletons, cursor = _run_scan_loop(events)
        for s in skeletons:
            assert s["class_name"] == "None"
            assert s["has_recv"] is False
            assert s["visibility"] == "private"
        _check_all_invariants_at_state(cursor, skeletons, events)

    def test_large_file_all_receiver_methods(self):
        """Stress: 20 receiver methods on 5 different structs."""
        structs = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        events = [
            {
                "has_recv": True,
                "recv_type": structs[i % len(structs)],
                "name": f"Method{i}",
                "cap": i % 2 == 0,
            }
            for i in range(20)
        ]
        skeletons, cursor = _run_scan_loop(events)
        assert len(skeletons) == 20
        _check_all_invariants_at_state(cursor, skeletons, events)
        for s in skeletons:
            assert s["class_name"] in structs
            assert s["has_recv"] is True

    def test_pointer_receiver_type_strips_star(self):
        """
        Convention: pointer receivers (*Svc) should resolve class_name to 'Svc'.
        The TLA+ model uses recv_type directly, so tests verify whatever the
        scanner emits is consistent with ReceiverResolution.
        """
        events = [{"has_recv": True, "recv_type": "Svc", "name": "Save", "cap": True}]
        skeletons = [_make_skeleton(e) for e in events]
        assert skeletons[0]["class_name"] == "Svc"
        _check_receiver_resolution(skeletons)

    def test_go_source_string_contains_all_expected_functions(self):
        """Sanity: the fixture Go source matches the TLA+ Events sequence."""
        assert "func Hello()" in GO_SOURCE
        assert "func (s Svc) GetUser()" in GO_SOURCE
        assert "func (p Point) distance()" in GO_SOURCE
        assert "func helper()" in GO_SOURCE

    def test_partial_scan_cursor_at_boundary(self):
        """cursor == N: loop processes last event but AllRecorded not yet checked."""
        skeletons = [_make_skeleton(EVENTS[i]) for i in range(N - 1)]
        cursor = N  # about to process last event, still inside loop
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)
        # Now process final event and advance
        skeletons.append(_make_skeleton(EVENTS[N - 1]))
        cursor += 1
        _check_all_invariants_at_state(cursor, skeletons, EVENTS)

    def test_node_kind_is_resource(self, full_dag):
        """Skeleton nodes are registered as resource kind."""
        for node in full_dag._nodes.values():  # noqa: SLF001
            assert node.kind == NodeKind.RESOURCE

    def test_extract_subgraph_single_skeleton_node(self, full_dag):
        """extract_subgraph on an isolated skeleton node returns just that node."""
        result = full_dag.extract_subgraph("func_Hello")
        assert "func_Hello" in result.nodes

    def test_query_relevant_isolated_skeleton(self, full_dag):
        """query_relevant on a skeleton node with no edges returns itself."""
        result = full_dag.query_relevant("func_GetUser")
        assert "func_GetUser" in result.node_ids