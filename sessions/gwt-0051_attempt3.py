import pytest
from registry.dag import RegistryDag
from registry.types import Node

# ── TLA+ Events[1..4] from the verified spec ──────────────────────────────────
_EVENTS = [
    {"func_name": "Hello",    "class_name": "None",  "has_recv": False, "cap": True,  "visibility": "public"},
    {"func_name": "GetUser",  "class_name": "Svc",   "has_recv": True,  "cap": True,  "visibility": "public"},
    {"func_name": "distance", "class_name": "Point", "has_recv": True,  "cap": False, "visibility": "private"},
    {"func_name": "helper",   "class_name": "None",  "has_recv": False, "cap": False, "visibility": "private"},
]
_N = len(_EVENTS)

# Expected final skeleton set — State 15 of every trace
_EXPECTED_SKELETONS = frozenset({
    ("Hello",    "None",  False, True,  "public"),
    ("GetUser",  "Svc",   True,  True,  "public"),
    ("distance", "Point", True,  False, "private"),
    ("helper",   "None",  False, False, "private"),
})


# ── invariant verifiers ────────────────────────────────────────────────────────

def _assert_receiver_resolution(skeletons):
    """ReceiverResolution: class_name=='None' iff has_recv==False."""
    for s in skeletons:
        if s["class_name"] == "None":
            assert s["has_recv"] is False, (
                f"ReceiverResolution: {s['func_name']!r} "
                f"class_name='None' but has_recv={s['has_recv']}"
            )
        else:
            assert s["has_recv"] is True, (
                f"ReceiverResolution: {s['func_name']!r} "
                f"class_name={s['class_name']!r} but has_recv={s['has_recv']}"
            )


def _assert_visibility_correct(skeletons):
    """VisibilityCorrect: visibility=='public' iff cap==True."""
    for s in skeletons:
        if s["cap"] is True:
            assert s["visibility"] == "public", (
                f"VisibilityCorrect: {s['func_name']!r} cap=True "
                f"but visibility={s['visibility']!r}"
            )
        else:
            assert s["visibility"] == "private", (
                f"VisibilityCorrect: {s['func_name']!r} cap=False "
                f"but visibility={s['visibility']!r}"
            )


def _assert_all_recorded(cursor, skeletons, events):
    """AllRecorded: cursor > N => every event name is present in skeletons."""
    n = len(events)
    if cursor > n:
        recorded = {s["func_name"] for s in skeletons}
        for ev in events:
            assert ev["func_name"] in recorded, (
                f"AllRecorded: {ev['func_name']!r} missing after cursor={cursor}"
            )


def _assert_all_invariants(skeletons, cursor, events):
    """Conjunction of all three TLA+ invariants checked at every reachable state."""
    _assert_receiver_resolution(skeletons)
    _assert_visibility_correct(skeletons)
    _assert_all_recorded(cursor, skeletons, events)


# ── scan simulation (models TLA+ ScanLoop→ProcessEvent→Advance×N→Finish) ──────

def _simulate_scan(events):
    """
    Execute the TLA+ scanner algorithm step by step.
    Invariants are verified at EVERY intermediate state, not just the final one,
    matching the TLA+ requirement that all invariants hold in every reachable state.
    Returns (dag, skeletons, cursor_after_finish).
    """
    dag = RegistryDag()
    skeletons = []
    cursor = 1  # Init: cursor=1, skeletons={}

    # Verify invariants on the Init state
    _assert_all_invariants(skeletons, cursor, events)

    for ev in events:
        # ScanLoop: cursor <= N, transition to ProcessEvent
        _assert_all_invariants(skeletons, cursor, events)

        # ProcessEvent: add skeleton and corresponding DAG node
        node_id = f"fn_{ev['func_name'].lower()}"
        dag.add_node(Node.resource(
            id=node_id,
            name=ev["func_name"],
            description=ev["class_name"],
        ))
        skeleton = {
            "func_name":  ev["func_name"],
            "class_name": ev["class_name"],
            "has_recv":   ev["has_recv"],
            "cap":        ev["cap"],
            "visibility": ev["visibility"],
        }
        skeletons.append(skeleton)

        # Verify invariants after ProcessEvent
        _assert_all_invariants(skeletons, cursor, events)

        # Advance: cursor += 1
        cursor += 1

        # Verify invariants after Advance
        _assert_all_invariants(skeletons, cursor, events)

    # ScanLoop guard fails (cursor > N) → Finish then Done
    _assert_all_invariants(skeletons, cursor, events)

    return dag, skeletons, cursor


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def empty_dag():
    """Init state: skeletons={}, cursor=1, pc=ScanLoop."""
    return RegistryDag()


@pytest.fixture
def scanned_dag():
    """Final state (State 15): all 4 events processed, pc=Done."""
    dag, skeletons, cursor = _simulate_scan(_EVENTS)
    return dag, skeletons, cursor


# ── negative tests for the invariant verifiers themselves ─────────────────────

class TestInvariantVerifiers:
    """Verify that the verifier helpers detect every possible violation."""

    def test_receiver_resolution_raises_for_none_class_with_recv(self):
        """class_name='None' but has_recv=True must be rejected."""
        bad = [{"func_name": "X", "class_name": "None", "has_recv": True,
                "cap": True, "visibility": "public"}]
        with pytest.raises(AssertionError, match="ReceiverResolution"):
            _assert_receiver_resolution(bad)

    def test_receiver_resolution_raises_for_class_set_without_recv(self):
        """class_name='Svc' but has_recv=False must be rejected."""
        bad = [{"func_name": "X", "class_name": "Svc", "has_recv": False,
                "cap": True, "visibility": "public"}]
        with pytest.raises(AssertionError, match="ReceiverResolution"):
            _assert_receiver_resolution(bad)

    def test_receiver_resolution_accepts_valid_none_class(self):
        """class_name='None' with has_recv=False is valid — must not raise."""
        good = [{"func_name": "X", "class_name": "None", "has_recv": False,
                 "cap": True, "visibility": "public"}]
        _assert_receiver_resolution(good)

    def test_receiver_resolution_accepts_valid_receiver(self):
        """class_name='Svc' with has_recv=True is valid — must not raise."""
        good = [{"func_name": "X", "class_name": "Svc", "has_recv": True,
                 "cap": True, "visibility": "public"}]
        _assert_receiver_resolution(good)

    def test_receiver_resolution_raises_for_second_bad_skeleton_in_list(self):
        """Violation in the second element of a list must still be caught."""
        skeletons = [
            {"func_name": "Good", "class_name": "None", "has_recv": False,
             "cap": False, "visibility": "private"},
            {"func_name": "Bad",  "class_name": "None", "has_recv": True,
             "cap": True,  "visibility": "public"},
        ]
        with pytest.raises(AssertionError, match="ReceiverResolution"):
            _assert_receiver_resolution(skeletons)

    def test_visibility_correct_raises_for_cap_true_private(self):
        """cap=True but visibility='private' must be rejected."""
        bad = [{"func_name": "X", "class_name": "None", "has_recv": False,
                "cap": True, "visibility": "private"}]
        with pytest.raises(AssertionError, match="VisibilityCorrect"):
            _assert_visibility_correct(bad)

    def test_visibility_correct_raises_for_cap_false_public(self):
        """cap=False but visibility='public' must be rejected."""
        bad = [{"func_name": "x", "class_name": "None", "has_recv": False,
                "cap": False, "visibility": "public"}]
        with pytest.raises(AssertionError, match="VisibilityCorrect"):
            _assert_visibility_correct(bad)

    def test_visibility_correct_accepts_cap_true_public(self):
        """cap=True with visibility='public' is valid — must not raise."""
        good = [{"func_name": "X", "class_name": "None", "has_recv": False,
                 "cap": True, "visibility": "public"}]
        _assert_visibility_correct(good)

    def test_visibility_correct_accepts_cap_false_private(self):
        """cap=False with visibility='private' is valid — must not raise."""
        good = [{"func_name": "x", "class_name": "None", "has_recv": False,
                 "cap": False, "visibility": "private"}]
        _assert_visibility_correct(good)

    def test_visibility_correct_raises_for_second_bad_skeleton_in_list(self):
        """Violation in the second element of a list must still be caught."""
        skeletons = [
            {"func_name": "Good", "class_name": "None", "has_recv": False,
             "cap": True,  "visibility": "public"},
            {"func_name": "Bad",  "class_name": "None", "has_recv": False,
             "cap": False, "visibility": "public"},
        ]
        with pytest.raises(AssertionError, match="VisibilityCorrect"):
            _assert_visibility_correct(skeletons)

    def test_all_recorded_raises_when_cursor_past_n_and_name_missing(self):
        """cursor > N but a function name is absent from skeletons must fail."""
        events = [
            {"func_name": "A", "class_name": "None", "has_recv": False,
             "cap": True, "visibility": "public"},
            {"func_name": "B", "class_name": "None", "has_recv": False,
             "cap": False, "visibility": "private"},
        ]
        skeletons = [{"func_name": "A", "class_name": "None", "has_recv": False,
                      "cap": True, "visibility": "public"}]
        with pytest.raises(AssertionError, match="AllRecorded"):
            _assert_all_recorded(3, skeletons, events)

    def test_all_recorded_does_not_raise_when_cursor_equals_n(self):
        """cursor == N is not strictly greater; verifier must be vacuous."""
        events = [
            {"func_name": "A", "class_name": "None", "has_recv": False,
             "cap": True, "visibility": "public"},
            {"func_name": "B", "class_name": "None", "has_recv": False,
             "cap": False, "visibility": "private"},
        ]
        _assert_all_recorded(2, [{"func_name": "A"}], events)

    def test_all_recorded_does_not_raise_when_cursor_less_than_n(self):
        """cursor < N: verifier is vacuous regardless of skeleton contents."""
        _assert_all_recorded(1, [], _EVENTS)

    def test_all_recorded_raises_for_empty_skeletons_after_completion(self):
        """cursor > N with zero skeletons must fail immediately."""
        events = [{"func_name": "A", "class_name": "None", "has_recv": False,
                   "cap": True, "visibility": "public"}]
        with pytest.raises(AssertionError, match="AllRecorded"):
            _assert_all_recorded(2, [], events)


# ── trace tests ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_produces_correct_final_skeleton_set(trace_id):
    dag, skeletons, cursor = _simulate_scan(_EVENTS)

    assert dag.node_count == _N, (
        f"[trace {trace_id}] expected {_N} nodes, got {dag.node_count}"
    )

    actual = frozenset(
        (s["func_name"], s["class_name"], s["has_recv"], s["cap"], s["visibility"])
        for s in skeletons
    )
    assert actual == _EXPECTED_SKELETONS, (
        f"[trace {trace_id}] skeleton set mismatch\n"
        f"  expected: {_EXPECTED_SKELETONS}\n"
        f"  got:      {actual}"
    )

    assert cursor == _N + 1, (
        f"[trace {trace_id}] cursor should be {_N + 1}, got {cursor}"
    )

    _assert_all_invariants(skeletons, cursor, _EVENTS)


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_receiver_methods_carry_class_name(trace_id):
    _, skeletons, _ = _simulate_scan(_EVENTS)
    by_name = {s["func_name"]: s for s in skeletons}

    for fn in ("Hello", "helper"):
        s = by_name[fn]
        assert s["class_name"] == "None", (
            f"[trace {trace_id}] {fn!r}: package function has class_name={s['class_name']!r}"
        )
        assert s["has_recv"] is False, (
            f"[trace {trace_id}] {fn!r}: package function has has_recv=True"
        )

    assert by_name["GetUser"]["class_name"] == "Svc", (
        f"[trace {trace_id}] GetUser class_name should be 'Svc'"
    )
    assert by_name["GetUser"]["has_recv"] is True

    assert by_name["distance"]["class_name"] == "Point", (
        f"[trace {trace_id}] distance class_name should be 'Point'"
    )
    assert by_name["distance"]["has_recv"] is True


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_visibility_derived_from_capitalisation(trace_id):
    _, skeletons, _ = _simulate_scan(_EVENTS)
    for s in skeletons:
        expected = "public" if s["cap"] else "private"
        assert s["visibility"] == expected, (
            f"[trace {trace_id}] {s['func_name']!r}: cap={s['cap']} "
            f"but visibility={s['visibility']!r} (expected {expected!r})"
        )


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_all_four_functions_recorded(trace_id):
    _, skeletons, cursor = _simulate_scan(_EVENTS)
    assert cursor > _N
    recorded = {s["func_name"] for s in skeletons}
    for ev in _EVENTS:
        assert ev["func_name"] in recorded, (
            f"[trace {trace_id}] {ev['func_name']!r} missing after full scan"
        )


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_invariants_hold_at_every_intermediate_state(trace_id):
    dag, skeletons, cursor = _simulate_scan(_EVENTS)
    assert dag.node_count == _N
    assert cursor == _N + 1


# ── dedicated invariant-verifier tests ────────────────────────────────────────

class TestReceiverResolution:

    def test_all_package_functions(self):
        events = [
            {"func_name": "Alpha", "class_name": "None", "has_recv": False, "cap": True,  "visibility": "public"},
            {"func_name": "beta",  "class_name": "None", "has_recv": False, "cap": False, "visibility": "private"},
        ]
        dag = RegistryDag()
        skeletons = []
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
        _assert_receiver_resolution(skeletons)
        for s in skeletons:
            assert s["class_name"] == "None"
            assert s["has_recv"] is False

    def test_all_receiver_methods(self):
        events = [
            {"func_name": "GetUser",  "class_name": "Svc",   "has_recv": True, "cap": True,  "visibility": "public"},
            {"func_name": "distance", "class_name": "Point", "has_recv": True, "cap": False, "visibility": "private"},
        ]
        dag = RegistryDag()
        skeletons = []
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
        _assert_receiver_resolution(skeletons)
        for s in skeletons:
            assert s["class_name"] != "None"
            assert s["has_recv"] is True

    def test_mixed_topology_from_spec(self):
        _, skeletons, _ = _simulate_scan(_EVENTS)
        _assert_receiver_resolution(skeletons)

    def test_empty_skeletons(self):
        _assert_receiver_resolution([])

    def test_incremental_invariant_after_each_event(self):
        dag = RegistryDag()
        skeletons = []
        for ev in _EVENTS:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
            _assert_receiver_resolution(skeletons)

    def test_two_methods_on_same_struct(self):
        events = [
            {"func_name": "GetUser",  "class_name": "Svc", "has_recv": True, "cap": True, "visibility": "public"},
            {"func_name": "PostUser", "class_name": "Svc", "has_recv": True, "cap": True, "visibility": "public"},
        ]
        dag = RegistryDag()
        skeletons = []
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
        _assert_receiver_resolution(skeletons)
        for s in skeletons:
            assert s["class_name"] == "Svc"


class TestVisibilityCorrect:

    def test_all_public(self):
        events = [
            {"func_name": "Hello",   "class_name": "None", "has_recv": False, "cap": True, "visibility": "public"},
            {"func_name": "GetUser", "class_name": "Svc",  "has_recv": True,  "cap": True, "visibility": "public"},
        ]
        dag = RegistryDag()
        skeletons = [dict(ev) for ev in events]
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
        _assert_visibility_correct(skeletons)
        for s in skeletons:
            assert s["visibility"] == "public"

    def test_all_private(self):
        events = [
            {"func_name": "distance", "class_name": "Point", "has_recv": True,  "cap": False, "visibility": "private"},
            {"func_name": "helper",   "class_name": "None",  "has_recv": False, "cap": False, "visibility": "private"},
        ]
        dag = RegistryDag()
        skeletons = [dict(ev) for ev in events]
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
        _assert_visibility_correct(skeletons)
        for s in skeletons:
            assert s["visibility"] == "private"

    def test_mixed_visibility_from_spec(self):
        _, skeletons, _ = _simulate_scan(_EVENTS)
        _assert_visibility_correct(skeletons)
        by_name = {s["func_name"]: s for s in skeletons}
        assert by_name["Hello"]["visibility"]    == "public"
        assert by_name["GetUser"]["visibility"]  == "public"
        assert by_name["distance"]["visibility"] == "private"
        assert by_name["helper"]["visibility"]   == "private"

    def test_empty_skeletons(self):
        _assert_visibility_correct([])

    def test_incremental_invariant_after_each_event(self):
        dag = RegistryDag()
        skeletons = []
        for ev in _EVENTS:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
            _assert_visibility_correct(skeletons)


class TestAllRecorded:

    def test_full_scan_satisfies_all_recorded(self):
        _, skeletons, cursor = _simulate_scan(_EVENTS)
        assert cursor > _N
        _assert_all_recorded(cursor, skeletons, _EVENTS)

    def test_vacuous_before_completion_cursor_1(self):
        partial = [dict(_EVENTS[0])]
        _assert_all_recorded(1, partial, _EVENTS)

    def test_vacuous_at_boundary_cursor_equals_n(self):
        partial = [dict(ev) for ev in _EVENTS[:3]]
        _assert_all_recorded(_N, partial, _EVENTS)

    def test_fires_at_cursor_n_plus_1(self):
        _, skeletons, cursor = _simulate_scan(_EVENTS)
        assert cursor == _N + 1
        _assert_all_recorded(cursor, skeletons, _EVENTS)
        recorded = {s["func_name"] for s in skeletons}
        for ev in _EVENTS:
            assert ev["func_name"] in recorded

    def test_single_event_scan(self):
        single = [{"func_name": "Hello", "class_name": "None",
                   "has_recv": False, "cap": True, "visibility": "public"}]
        dag = RegistryDag()
        dag.add_node(Node.resource(id="fn_hello", name="Hello", description="None"))
        skeletons = [dict(single[0])]
        _assert_all_recorded(2, skeletons, single)

    def test_reversed_event_order_all_recorded(self):
        _, skeletons, cursor = _simulate_scan(list(reversed(_EVENTS)))
        assert cursor > _N
        _assert_all_recorded(cursor, skeletons, list(reversed(_EVENTS)))
        recorded = {s["func_name"] for s in skeletons}
        for ev in _EVENTS:
            assert ev["func_name"] in recorded


# ── edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dag_init_state(self):
        dag = RegistryDag()
        assert dag.node_count == 0
        _assert_all_invariants([], 1, _EVENTS)

    def test_single_package_function_node(self):
        ev = {"func_name": "Hello", "class_name": "None",
              "has_recv": False, "cap": True, "visibility": "public"}
        dag = RegistryDag()
        dag.add_node(Node.resource(id="fn_hello", name="Hello", description="None"))
        skeletons = [dict(ev)]
        assert dag.node_count == 1
        _assert_all_invariants(skeletons, 2, [ev])

    def test_single_private_package_function_node(self):
        ev = {"func_name": "helper", "class_name": "None",
              "has_recv": False, "cap": False, "visibility": "private"}
        dag = RegistryDag()
        dag.add_node(Node.resource(id="fn_helper", name="helper", description="None"))
        skeletons = [dict(ev)]
        assert dag.node_count == 1
        _assert_all_invariants(skeletons, 2, [ev])
        assert skeletons[0]["class_name"] == "None"
        assert skeletons[0]["has_recv"] is False

    def test_single_public_receiver_method_node(self):
        ev = {"func_name": "GetUser", "class_name": "Svc",
              "has_recv": True, "cap": True, "visibility": "public"}
        dag = RegistryDag()
        dag.add_node(Node.resource(id="fn_getuser", name="GetUser", description="Svc"))
        skeletons = [dict(ev)]
        assert dag.node_count == 1
        _assert_all_invariants(skeletons, 2, [ev])
        assert skeletons[0]["class_name"] == "Svc"
        assert skeletons[0]["has_recv"] is True

    def test_single_private_receiver_method_node(self):
        ev = {"func_name": "distance", "class_name": "Point",
              "has_recv": True, "cap": False, "visibility": "private"}
        dag = RegistryDag()
        dag.add_node(Node.resource(id="fn_distance", name="distance", description="Point"))
        skeletons = [dict(ev)]
        assert dag.node_count == 1
        _assert_all_invariants(skeletons, 2, [ev])
        assert skeletons[0]["class_name"] == "Point"
        assert skeletons[0]["visibility"] == "private"

    def test_node_count_increments_per_process_event(self):
        dag = RegistryDag()
        for i, ev in enumerate(_EVENTS):
            dag.add_node(Node.resource(
                id=f"fn_{ev['func_name'].lower()}",
                name=ev["func_name"],
                description=ev["class_name"],
            ))
            assert dag.node_count == i + 1

    def test_scan_order_independence(self):
        dag_fwd, sk_fwd, cur_fwd = _simulate_scan(_EVENTS)
        dag_rev, sk_rev, cur_rev = _simulate_scan(list(reversed(_EVENTS)))

        set_fwd = frozenset(
            (s["func_name"], s["class_name"], s["has_recv"], s["cap"], s["visibility"])
            for s in sk_fwd
        )
        set_rev = frozenset(
            (s["func_name"], s["class_name"], s["has_recv"], s["cap"], s["visibility"])
            for s in sk_rev
        )
        assert set_fwd == set_rev
        assert dag_fwd.node_count == dag_rev.node_count == _N
        assert cur_fwd == cur_rev == _N + 1

    def test_each_individual_event_satisfies_all_invariants(self):
        for ev in _EVENTS:
            skeletons = [dict(ev)]
            _assert_receiver_resolution(skeletons)
            _assert_visibility_correct(skeletons)
            _assert_all_recorded(2, skeletons, [ev])

    def test_two_functions_same_receiver_different_visibility(self):
        events = [
            {"func_name": "GetUser", "class_name": "Svc", "has_recv": True, "cap": True,  "visibility": "public"},
            {"func_name": "setUser", "class_name": "Svc", "has_recv": True, "cap": False, "visibility": "private"},
        ]
        dag = RegistryDag()
        skeletons = []
        for ev in events:
            dag.add_node(Node.resource(id=f"fn_{ev['func_name'].lower()}",
                                       name=ev["func_name"],
                                       description=ev["class_name"]))
            skeletons.append(dict(ev))
        assert dag.node_count == 2
        _assert_all_invariants(skeletons, len(events) + 1, events)
        by_name = {s["func_name"]: s for s in skeletons}
        assert by_name["GetUser"]["visibility"] == "public"
        assert by_name["setUser"]["visibility"] == "private"
        assert by_name["GetUser"]["class_name"] == by_name["setUser"]["class_name"] == "Svc"

    def test_full_scan_dag_edge_count_zero(self):
        dag, _, _ = _simulate_scan(_EVENTS)
        assert dag.edge_count == 0