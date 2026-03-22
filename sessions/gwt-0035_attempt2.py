import json
import pytest
from pathlib import Path
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Node, NodeKind


# ─────────────────────────────────────────────────────────────────────────────
# TLA+ model constants
# ─────────────────────────────────────────────────────────────────────────────
CRITERION_1 = "InputCriteria_1"
CRITERION_2 = "InputCriteria_2"
INPUT_CRITERIA = frozenset({CRITERION_1, CRITERION_2})
MAX_STEPS = 7  # BoundedExecution: step_count <= MaxSteps


# ─────────────────────────────────────────────────────────────────────────────
# System Under Test  (models 'cw9 register' behaviour)
# ─────────────────────────────────────────────────────────────────────────────

def _load_bindings(path: Path) -> dict:
    """Load criterion → gwt_id mapping from .cw9/criterion_bindings.json."""
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_bindings(path: Path, data: dict) -> None:
    """Persist criterion → gwt_id mapping to .cw9/criterion_bindings.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def register_criterion(dag: RegistryDag, criterion_id: str, bindings_path: Path) -> str:
    """
    Idempotent criterion registration — the Python realisation of 'cw9 register'.

    First call for a given criterion_id:
      • Calls dag.register_gwt() to allocate a gwt_id.
      • Persists {criterion_id: gwt_id} to bindings_path.
      • Returns the new gwt_id.

    Subsequent calls for the same criterion_id:
      • Reads the previously-persisted gwt_id from bindings_path.
      • Returns it WITHOUT calling dag.register_gwt() again.
    """
    bindings = _load_bindings(bindings_path)
    if criterion_id in bindings:
        return bindings[criterion_id]
    gwt_id = dag.register_gwt(
        given=f"a {criterion_id} criterion exists",
        when="cw9 register is called",
        then=f"{criterion_id} is allocated a stable gwt_id",
        name=criterion_id,
    )
    bindings[criterion_id] = gwt_id
    _save_bindings(bindings_path, bindings)
    return gwt_id


# ─────────────────────────────────────────────────────────────────────────────
# TLA+ invariant verifiers
# ─────────────────────────────────────────────────────────────────────────────

def chk_idempotent_allocation(b_save: dict, b_done: dict) -> None:
    """
    IdempotentAllocation:
      phase = "done" => forall c in InputCriteria: bindings[c] = bindings_at_save[c]
    """
    for c in INPUT_CRITERIA:
        assert c in b_done, (
            f"IdempotentAllocation: {c!r} absent from final bindings"
        )
        assert b_done[c] == b_save[c], (
            f"IdempotentAllocation violated for {c!r}: "
            f"saved={b_save[c]!r}, final={b_done[c]!r}"
        )


def chk_no_duplicate_nodes(dag: RegistryDag, bindings: dict) -> None:
    """
    NoDuplicateNodes:
      Cardinality(dag_nodes) = Cardinality(DOMAIN bindings)

    Verified in two parts:
      1. All gwt_ids in bindings are distinct — no two criteria share a node.
      2. Every gwt_id in bindings resolves to an actual node in the DAG —
         Cardinality(dag_nodes) >= Cardinality(DOMAIN bindings).
    Together these ensure the DAG node set and the bindings domain have the
    same cardinality, as required by the TLA+ invariant.
    """
    gwt_ids = list(bindings.values())
    assert len(set(gwt_ids)) == len(gwt_ids), (
        f"NoDuplicateNodes: duplicate gwt_ids detected in bindings {bindings}"
    )
    for gwt_id in gwt_ids:
        try:
            dag.query_relevant(gwt_id)
        except NodeNotFoundError:
            pytest.fail(
                f"NoDuplicateNodes: gwt_id {gwt_id!r} not found in DAG — "
                f"Cardinality(dag_nodes) < Cardinality(DOMAIN bindings)"
            )


def chk_binding_stable(b_save: dict, b_after: dict) -> None:
    """
    BindingStable:
      forall c in DOMAIN bindings_at_save:
        c in DOMAIN bindings => bindings[c] = bindings_at_save[c]
    """
    for c, v in b_save.items():
        assert c in b_after, (
            f"BindingStable: {c!r} vanished from bindings after second invocation"
        )
        assert b_after[c] == v, (
            f"BindingStable: {c!r} drifted: was {v!r}, now {b_after[c]!r}"
        )


def chk_second_call_skips(cc_save: int, cc_final: int) -> None:
    """
    SecondCallSkipsAllocate:
      phase = "done" => call_count = call_count_at_save
    """
    assert cc_final == cc_save, (
        f"SecondCallSkipsAllocate: call_count was {cc_save} at save, "
        f"but reached {cc_final} at done"
    )


def chk_bounded(steps: int) -> None:
    """BoundedExecution: step_count <= MaxSteps"""
    assert steps <= MAX_STEPS, (
        f"BoundedExecution: step_count={steps} exceeds MaxSteps={MAX_STEPS}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Core trace driver
# ─────────────────────────────────────────────────────────────────────────────

def _run_trace(
    dag: RegistryDag,
    bp: Path,
    first_order: list,
    second_order: list,
) -> dict:
    """
    Execute the TLA+ algorithm for one trace, verifying all five invariants
    at every state transition.

    Models:
      StartFirst → ProcessFirstLoop* → SaveFirst → ProcessSecondLoop* → Finish

    Step accounting (matches TLA+ step_count increments):
      StartFirst      +1
      ProcessFirstLoop: +1 per item processed (not on empty-set exit)
      SaveFirst       +1
      ProcessSecondLoop: +1 per item processed (not on empty-set exit)
      Finish          +1
    Total for |InputCriteria|=2: 1 + 2 + 1 + 2 + 1 = 7 == MAX_STEPS

    Returns a dict of collected TLA+ state variables for final assertions.
    """
    call_count = [0]
    _orig = dag.register_gwt

    def _spy(*args, **kwargs):
        call_count[0] += 1
        return _orig(*args, **kwargs)

    dag.register_gwt = _spy
    steps = 0
    b_save: dict = {}
    cc_save: int = 0
    gwt_first: dict = {}
    gwt_second: dict = {}
    b_done: dict = {}

    try:
        # ── State 1→2  StartFirst ─────────────────────────────────────────
        # TLA+ Init: bindings={}, dag_nodes={}, call_count=0, step_count=0
        steps += 1                                          # step_count = 1
        chk_bounded(steps)
        assert _load_bindings(bp) == {}, "Init: bindings must be empty"

        # ── States 2→N  ProcessFirstLoop ─────────────────────────────────
        for crit in first_order:
            gid = register_criterion(dag, crit, bp)
            gwt_first[crit] = gid
            steps += 1                                      # +1 per item
            b_cur = _load_bindings(bp)
            chk_no_duplicate_nodes(dag, b_cur)              # NoDuplicateNodes at every step
            chk_bounded(steps)
        # (empty to_process: loop exits without incrementing step_count)

        # ── State N→SaveFirst  SaveFirst ──────────────────────────────────
        b_save = dict(_load_bindings(bp))
        cc_save = call_count[0]
        steps += 1                                          # step_count += 1
        chk_no_duplicate_nodes(dag, b_save)
        chk_binding_stable(b_save, b_save)                  # trivially stable at save
        chk_bounded(steps)

        # ── States SaveFirst→M  ProcessSecondLoop ────────────────────────
        for crit in second_order:
            pre = call_count[0]
            gid = register_criterion(dag, crit, bp)
            gwt_second[crit] = gid
            # Core assertion: second loop must NOT call register_gwt
            assert call_count[0] == pre, (
                f"register_gwt was called during second loop for {crit!r} "
                f"(call_count {pre} → {call_count[0]})"
            )
            steps += 1                                      # +1 per item
            b_cur = _load_bindings(bp)
            chk_no_duplicate_nodes(dag, b_cur)
            chk_binding_stable(b_save, b_cur)
            chk_bounded(steps)
        # (empty to_process: loop exits without incrementing step_count)

        # ── State M→Done  Finish (phase = "done") ────────────────────────
        steps += 1
        b_done = _load_bindings(bp)
        chk_idempotent_allocation(b_save, b_done)           # IdempotentAllocation
        chk_no_duplicate_nodes(dag, b_done)                 # NoDuplicateNodes
        chk_binding_stable(b_save, b_done)                  # BindingStable
        chk_second_call_skips(cc_save, call_count[0])       # SecondCallSkipsAllocate
        chk_bounded(steps)                                  # BoundedExecution

    finally:
        dag.register_gwt = _orig  # restore original method

    return {
        "bindings_at_save": b_save,
        "bindings_done": b_done,
        "call_count_at_save": cc_save,
        "call_count_final": call_count[0],
        "step_count": steps,
        "gwt_ids_first": gwt_first,
        "gwt_ids_second": gwt_second,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def dag():
    """Fresh RegistryDag — TLA+ Init: dag_nodes={}, bindings={}."""
    return RegistryDag()


@pytest.fixture
def bp(tmp_path):
    """Bindings file path — TLA+ Init: bindings_at_save={}, file absent."""
    return tmp_path / ".cw9" / "criterion_bindings.json"


# ─────────────────────────────────────────────────────────────────────────────
# Trace Tests 1–10  (one parametrised test per TLC-verified trace)
# ─────────────────────────────────────────────────────────────────────────────

_TRACE_PARAMS = [
    ([CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1],  1),
    ([CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2],  2),
    ([CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2],  3),
    ([CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2],  4),
    ([CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1],  5),
    ([CRITERION_1, CRITERION_2], [CRITERION_1, CRITERION_2],  6),
    ([CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2],  7),
    ([CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2],  8),
    ([CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1],  9),
    ([CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1], 10),
]


@pytest.mark.parametrize(
    "first_order,second_order,trace_id",
    _TRACE_PARAMS,
    ids=[f"trace_{t[2]}" for t in _TRACE_PARAMS],
)
def test_trace(dag, bp, first_order, second_order, trace_id):
    """
    TLC-verified two-invocation scenario for all five invariants.

    Expected TLA+ final state (State 10 of every trace):
      phase            = "done"
      call_count       = call_count_at_save = 2
      dag_nodes        = {id_first, id_second}   (exactly 2 distinct nodes)
      bindings         = {C1: gid_a, C2: gid_b}  (stable from save)
      step_count       = 7
      registered       = {InputCriteria_1, InputCriteria_2}
    """
    state = _run_trace(dag, bp, first_order, second_order)

    assert state["step_count"] == MAX_STEPS, (
        f"Trace {trace_id}: step_count={state['step_count']}, want {MAX_STEPS}"
    )

    assert state["call_count_at_save"] == len(INPUT_CRITERIA), (
        f"Trace {trace_id}: expected {len(INPUT_CRITERIA)} allocations "
        f"in first invocation, got {state['call_count_at_save']}"
    )
    assert state["call_count_final"] == len(INPUT_CRITERIA), (
        f"Trace {trace_id}: call_count grew during second invocation — "
        f"SecondCallSkipsAllocate violated"
    )

    assert set(state["gwt_ids_first"].keys()) == INPUT_CRITERIA
    assert set(state["gwt_ids_second"].keys()) == INPUT_CRITERIA

    for c in INPUT_CRITERIA:
        assert state["gwt_ids_first"][c] == state["gwt_ids_second"][c], (
            f"Trace {trace_id}: gwt_id changed for {c!r} between invocations: "
            f"{state['gwt_ids_first'][c]!r} != {state['gwt_ids_second'][c]!r}"
        )

    gwt_vals = list(state["bindings_done"].values())
    assert len(set(gwt_vals)) == 2, (
        f"Trace {trace_id}: expected 2 distinct gwt_ids, got {gwt_vals}"
    )

    gid_a = state["gwt_ids_first"][first_order[0]]
    gid_b = state["gwt_ids_first"][first_order[1]]
    assert gid_a != gid_b, (
        f"Trace {trace_id}: both criteria received the same gwt_id {gid_a!r}"
    )

    assert state["bindings_at_save"] == state["bindings_done"], (
        f"Trace {trace_id}: bindings mutated between save and done: "
        f"{state['bindings_at_save']} vs {state['bindings_done']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dedicated invariant tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotentAllocation:
    """
    TLA+: phase = "done" => forall c in InputCriteria: bindings[c] = bindings_at_save[c]
    """

    def test_topology_a_c2_registered_first(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        chk_idempotent_allocation(s["bindings_at_save"], s["bindings_done"])

    def test_topology_b_c1_registered_first(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_1, CRITERION_2])
        chk_idempotent_allocation(s["bindings_at_save"], s["bindings_done"])

    def test_reversed_second_loop_order_still_idempotent(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_2, CRITERION_1])
        chk_idempotent_allocation(s["bindings_at_save"], s["bindings_done"])

    def test_bindings_at_save_dict_equals_bindings_done_dict(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2])
        assert s["bindings_at_save"] == s["bindings_done"]

    def test_each_criterion_maps_to_same_gwt_id_in_both_invocations(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        for c in INPUT_CRITERIA:
            assert s["gwt_ids_first"][c] == s["gwt_ids_second"][c], (
                f"gwt_id for {c!r} changed between invocations"
            )


class TestNoDuplicateNodes:
    """
    TLA+: Cardinality(dag_nodes) = Cardinality(DOMAIN bindings)
    """

    def test_two_criteria_produce_two_distinct_gwt_ids_topology_a(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2])
        chk_no_duplicate_nodes(dag, s["bindings_done"])
        assert len(s["bindings_done"]) == 2

    def test_two_criteria_produce_two_distinct_gwt_ids_topology_b(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_1, CRITERION_2])
        chk_no_duplicate_nodes(dag, s["bindings_done"])
        assert len(s["bindings_done"]) == 2

    def test_gwt_ids_are_distinct_values(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        gid1 = s["bindings_done"][CRITERION_1]
        gid2 = s["bindings_done"][CRITERION_2]
        assert gid1 != gid2, f"NoDuplicateNodes: both criteria got same gwt_id {gid1!r}"

    def test_all_gwt_ids_exist_as_queryable_dag_nodes(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        for gwt_id in s["bindings_done"].values():
            try:
                dag.query_relevant(gwt_id)
            except NodeNotFoundError:
                pytest.fail(f"NoDuplicateNodes: gwt_id {gwt_id!r} missing from DAG")

    def test_second_invocation_adds_no_new_dag_nodes(self, dag, bp):
        gid1 = register_criterion(dag, CRITERION_1, bp)
        gid2 = register_criterion(dag, CRITERION_2, bp)
        b_after_first = _load_bindings(bp)

        gid1_again = register_criterion(dag, CRITERION_1, bp)
        gid2_again = register_criterion(dag, CRITERION_2, bp)
        b_after_second = _load_bindings(bp)

        chk_no_duplicate_nodes(dag, b_after_second)
        assert b_after_first == b_after_second
        assert gid1_again == gid1
        assert gid2_again == gid2


class TestBindingStable:
    """
    TLA+: forall c in DOMAIN bindings_at_save:
            c in DOMAIN bindings => bindings[c] = bindings_at_save[c]
    """

    def test_file_not_mutated_during_second_loop_topology_a(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2])
        chk_binding_stable(s["bindings_at_save"], s["bindings_done"])

    def test_file_not_mutated_during_second_loop_topology_b(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_2, CRITERION_1])
        chk_binding_stable(s["bindings_at_save"], s["bindings_done"])

    def test_multiple_disk_reads_return_same_bindings(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        first_read = _load_bindings(bp)
        second_read = _load_bindings(bp)
        chk_binding_stable(first_read, second_read)
        assert first_read == second_read

    def test_criterion_gwt_id_same_in_memory_and_on_disk(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_1, CRITERION_2])
        on_disk = _load_bindings(bp)
        for c in INPUT_CRITERIA:
            assert s["gwt_ids_second"][c] == on_disk[c], (
                f"In-memory gwt_id for {c!r} doesn't match file: "
                f"{s['gwt_ids_second'][c]!r} vs {on_disk[c]!r}"
            )


class TestSecondCallSkipsAllocate:
    """
    TLA+: phase = "done" => call_count = call_count_at_save
    """

    def test_register_gwt_frozen_after_save_topology_a(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        chk_second_call_skips(s["call_count_at_save"], s["call_count_final"])
        assert s["call_count_at_save"] == 2

    def test_register_gwt_frozen_after_save_topology_b(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_1, CRITERION_2])
        chk_second_call_skips(s["call_count_at_save"], s["call_count_final"])
        assert s["call_count_at_save"] == 2

    def test_total_allocations_equals_criteria_count(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_2, CRITERION_1])
        assert s["call_count_final"] == len(INPUT_CRITERIA)

    def test_second_invocation_register_gwt_never_called_per_criterion(self, dag, bp):
        register_criterion(dag, CRITERION_1, bp)
        register_criterion(dag, CRITERION_2, bp)

        second_phase_calls = []
        orig = dag.register_gwt

        def spy_second(*args, **kwargs):
            second_phase_calls.append(args)
            return orig(*args, **kwargs)

        dag.register_gwt = spy_second
        try:
            register_criterion(dag, CRITERION_1, bp)
            register_criterion(dag, CRITERION_2, bp)
        finally:
            dag.register_gwt = orig

        assert second_phase_calls == [], (
            f"register_gwt was called {len(second_phase_calls)} times "
            f"during second invocation: {second_phase_calls}"
        )


class TestBoundedExecution:
    """TLA+: step_count <= MaxSteps  (MaxSteps = 7)"""

    def test_step_count_exactly_seven_topology_a(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_1, CRITERION_2])
        assert s["step_count"] == MAX_STEPS

    def test_step_count_exactly_seven_topology_b(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_1, CRITERION_2], [CRITERION_2, CRITERION_1])
        assert s["step_count"] == MAX_STEPS

    def test_bounded_never_exceeded_at_any_intermediate_state(self, dag, bp):
        s = _run_trace(dag, bp, [CRITERION_2, CRITERION_1], [CRITERION_2, CRITERION_1])
        chk_bounded(s["step_count"])


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases: single criterion, pre-populated bindings, empty DAG, repeated calls."""

    def test_single_criterion_allocates_once_returns_same_id(self, dag, bp):
        call_count = [0]
        orig = dag.register_gwt

        def spy(*a, **kw):
            call_count[0] += 1
            return orig(*a, **kw)

        dag.register_gwt = spy
        try:
            gid_first = register_criterion(dag, CRITERION_1, bp)
            assert call_count[0] == 1

            for i in range(4):
                gid_repeat = register_criterion(dag, CRITERION_1, bp)
                assert gid_repeat == gid_first, (
                    f"Call {i + 2}: gwt_id changed to {gid_repeat!r}"
                )

            assert call_count[0] == 1, (
                f"register_gwt called {call_count[0]} times; expected exactly 1"
            )
        finally:
            dag.register_gwt = orig

    def test_pre_existing_bindings_file_prevents_re_allocation(self, dag, bp):
        sentinel = "gwt-pre-existing-sentinel"
        _save_bindings(bp, {CRITERION_1: sentinel})

        call_count = [0]
        orig = dag.register_gwt

        def spy(*a, **kw):
            call_count[0] += 1
            return orig(*a, **kw)

        dag.register_gwt = spy
        try:
            returned = register_criterion(dag, CRITERION_1, bp)
            assert returned == sentinel, (
                f"Expected sentinel {sentinel!r}, got {returned!r}"
            )
            assert call_count[0] == 0, (
                "register_gwt must not be called when binding already exists"
            )
        finally:
            dag.register_gwt = orig

    def test_absent_bindings_file_is_created_on_first_registration(self, dag, bp):
        assert not bp.exists(), "Pre-condition: bindings file must not exist"
        gid = register_criterion(dag, CRITERION_1, bp)
        assert bp.exists(), "bindings file must be created on first registration"
        assert _load_bindings(bp) == {CRITERION_1: gid}

    def test_partial_bindings_only_unbound_criteria_cause_allocation(self, dag, bp):
        gid_c1 = register_criterion(dag, CRITERION_1, bp)

        call_count = [0]
        orig = dag.register_gwt

        def spy(*a, **kw):
            call_count[0] += 1
            return orig(*a, **kw)

        dag.register_gwt = spy
        try:
            returned_c1 = register_criterion(dag, CRITERION_1, bp)
            assert returned_c1 == gid_c1
            assert call_count[0] == 0, "C1 already bound; register_gwt must not fire"

            gid_c2 = register_criterion(dag, CRITERION_2, bp)
            assert call_count[0] == 1, "C2 is new; register_gwt must be called once"
            assert gid_c2 != gid_c1, "C2 must receive a different gwt_id than C1"

            chk_no_duplicate_nodes(dag, _load_bindings(bp))
        finally:
            dag.register_gwt = orig

    def test_empty_json_object_in_file_treated_as_no_registrations(self, dag, bp):
        bp.parent.mkdir(parents=True, exist_ok=True)
        bp.write_text("{}")
        gid = register_criterion(dag, CRITERION_1, bp)
        assert gid is not None
        assert _load_bindings(bp) == {CRITERION_1: gid}

    def test_repeated_registrations_never_produce_duplicate_gwt_ids(self, dag, bp):
        ids_seen: set = set()
        for _ in range(5):
            gid1 = register_criterion(dag, CRITERION_1, bp)
            gid2 = register_criterion(dag, CRITERION_2, bp)
            ids_seen.add(gid1)
            ids_seen.add(gid2)

        assert len(ids_seen) == 2, (
            f"Expected exactly 2 distinct gwt_ids across 10 calls, got {ids_seen}"
        )

    def test_empty_dag_raises_node_not_found_for_unknown_gwt_id(self, dag):
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("gwt-nonexistent-0000")

    def test_bindings_file_deterministic_across_interleaved_disk_reads(self, dag, bp):
        register_criterion(dag, CRITERION_1, bp)
        register_criterion(dag, CRITERION_2, bp)

        first_read = _load_bindings(bp)
        second_read = _load_bindings(bp)
        chk_binding_stable(first_read, second_read)
        assert first_read == second_read