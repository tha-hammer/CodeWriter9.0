from __future__ import annotations

import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Edge, EdgeType, Node


# ===========================================================================
# TLA+ model constants
# ===========================================================================
TARGET    = "uuid_target"   # UUIDs_1 / TargetUUID
OTHER     = "uuid_other"    # UUIDs_2 / OtherUUID
MAX_STEPS = 5               # TLA+ MaxSteps (all traces end at step_count == 5)


# ===========================================================================
# Utilities
# ===========================================================================

def _node_exists(dag: RegistryDag, node_id: str) -> bool:
    """Return True iff *node_id* is a live node in *dag*."""
    try:
        dag.query_relevant(node_id)
        return True
    except NodeNotFoundError:
        return False


def _make_init_dag_and_state():
    """
    Construct a RegistryDag + logical-state dicts matching the TLA+ Init state
    (identical across all 10 traces):

        c_records = {TARGET, OTHER}
        c_ins     = {TARGET: {"old_in"},  OTHER: {"other_in"}}
        c_outs    = {TARGET: {"old_out"}, OTHER: set()}
        c_refs    = {TARGET: {OTHER},     OTHER: set()}
        txn_state          = "idle"
        reader_saw_partial = False
        step_count         = 0

    The RegistryDag is the *committed* store.  The ref edge
    Edge(TARGET, OTHER, IMPORTS) encodes c_refs[TARGET] = {OTHER}.
    Working-state mutations are tracked exclusively in Python dicts until
    Commit, which then atomically promotes them into the DAG.
    """
    dag = RegistryDag()
    dag.add_node(Node.resource(TARGET, "Target Record", "TargetUUID"))
    dag.add_node(Node.resource(OTHER,  "Other Record",  "OtherUUID"))
    dag.add_edge(Edge(TARGET, OTHER, EdgeType.IMPORTS))   # c_refs[TARGET] = {OTHER}

    c_records = {TARGET, OTHER}
    c_ins  = {TARGET: {"old_in"},  OTHER: {"other_in"}}
    c_outs = {TARGET: {"old_out"}, OTHER: set()}
    c_refs = {TARGET: {OTHER},     OTHER: set()}
    return dag, c_records, c_ins, c_outs, c_refs


# ===========================================================================
# Invariant verifier  (assert at every state in a trace)
# ===========================================================================

def _assert_invariants(
    c_records,
    c_ins,
    c_outs,
    c_refs,
    txn_state,
    reader_saw_partial,
    step_count,
    label: str = "",
):
    """
    Assert all eight TLA+ invariants against the current committed state.

    NOTE: CommitCompleteness and RollbackPreservation are conditional on
    txn_state being "committed" / "rolled_back" respectively.  When this
    function is called with intermediate txn states ("begun", "nullified",
    "deleted", "inserted") those two invariants evaluate vacuously True —
    they are only meaningfully exercised by _assert_commit_final and
    _assert_rollback_final at the terminal states.
    """
    ctx = f" [{label}]" if label else ""

    # NoOrphanedIns: c_ins[u] != {} => u in c_records
    for u, ins in c_ins.items():
        if ins:
            assert u in c_records, (
                f"NoOrphanedIns{ctx}: {u} has ins={ins} but absent from c_records"
            )

    # NoOrphanedOuts: c_outs[u] != {} => u in c_records
    for u, outs in c_outs.items():
        if outs:
            assert u in c_records, (
                f"NoOrphanedOuts{ctx}: {u} has outs={outs} but absent from c_records"
            )

    # RefIntegrity: forall u, forall t in c_refs[u] => t in c_records
    for u, refs in c_refs.items():
        for t in refs:
            assert t in c_records, (
                f"RefIntegrity{ctx}: {u} refs {t!r} which is absent from c_records"
            )

    # AtomicityHolds: reader_saw_partial = FALSE
    assert reader_saw_partial is False, (
        f"AtomicityHolds{ctx}: reader_saw_partial is True"
    )

    # BoundedExecution: step_count <= MaxSteps
    assert step_count <= MAX_STEPS, (
        f"BoundedExecution{ctx}: step_count={step_count} exceeds MAX_STEPS={MAX_STEPS}"
    )

    # CommitCompleteness: txn_state = "committed" => TARGET has new state
    if txn_state == "committed":
        assert TARGET in c_records, f"CommitCompleteness{ctx}: TARGET absent from c_records"
        assert c_ins[TARGET]  == {"new_in"},  f"CommitCompleteness{ctx}: c_ins[T]={c_ins[TARGET]}"
        assert c_outs[TARGET] == {"new_out"}, f"CommitCompleteness{ctx}: c_outs[T]={c_outs[TARGET]}"
        assert c_refs[TARGET] == set(),       f"CommitCompleteness{ctx}: c_refs[T]={c_refs[TARGET]}"

    # RollbackPreservation: txn_state = "rolled_back" => TARGET has old state
    if txn_state == "rolled_back":
        assert TARGET in c_records, f"RollbackPreservation{ctx}: TARGET absent from c_records"
        assert c_ins[TARGET]  == {"old_in"},  f"RollbackPreservation{ctx}: c_ins[T]={c_ins[TARGET]}"
        assert c_outs[TARGET] == {"old_out"}, f"RollbackPreservation{ctx}: c_outs[T]={c_outs[TARGET]}"
        assert c_refs[TARGET] == {OTHER},     f"RollbackPreservation{ctx}: c_refs[T]={c_refs[TARGET]}"

    # OtherUUIDUnaffected: c_ins[OTHER] = {"other_in"} always
    assert c_ins[OTHER] == {"other_in"}, (
        f"OtherUUIDUnaffected{ctx}: c_ins[OTHER]={c_ins[OTHER]}"
    )


# ===========================================================================
# Reader simulation
# ===========================================================================

def _simulate_readloop(c_records, c_ins, c_outs) -> bool:
    """
    Execute one ReadLoop observation against the committed state.

    Mirrors the TLA+ ReadLoop guard exactly:
      Case 1 — TARGET present but both ins AND outs cleared:
        if TARGET in c_records and c_ins[TARGET]=={} and c_outs[TARGET]=={} -> partial
      Case 2 — TARGET absent but stale ins or outs remain:
        if TARGET not in c_records and (c_ins[TARGET]!={} or c_outs[TARGET]!={}) -> partial

    The AND condition in Case 1 is intentional: the atomic-commit model guarantees
    the committed view can only hold (old_in ∧ old_out) or (new_in ∧ new_out).
    The asymmetric state (one side empty, other non-empty) is unreachable in the
    committed store and is therefore outside the scope of this detector.

    Returns True iff a partial state is visible (forbidden by AtomicityHolds).
    """
    if TARGET in c_records:
        ins_empty  = not c_ins.get(TARGET)   # True for None or set()
        outs_empty = not c_outs.get(TARGET)
        return ins_empty and outs_empty
    else:
        return bool(c_ins.get(TARGET)) or bool(c_outs.get(TARGET))


# ===========================================================================
# Pure-functional upsert action helpers
# (The RegistryDag is mutated ONLY inside _do_commit)
# ===========================================================================

def _do_begin_upsert(c_records, c_ins, c_outs, c_refs, step_count):
    """Snapshot committed state to working state.  step_count += 1."""
    return (
        set(c_records),
        {k: set(v) for k, v in c_ins.items()},
        {k: set(v) for k, v in c_outs.items()},
        {k: set(v) for k, v in c_refs.items()},
        step_count + 1,
        "begun",
    )


def _do_nullify_refs(w_refs, step_count):
    """Clear TARGET's refs in the working copy.  step_count += 1."""
    new_refs = {k: set(v) for k, v in w_refs.items()}
    new_refs[TARGET] = set()
    return new_refs, step_count + 1, "nullified"


def _do_delete_old(w_records, w_ins, w_outs, step_count):
    """Remove TARGET from working copy.  step_count += 1."""
    nr = set(w_records)
    nr.discard(TARGET)
    ni = {k: set(v) for k, v in w_ins.items()}
    ni[TARGET] = set()
    no = {k: set(v) for k, v in w_outs.items()}
    no[TARGET] = set()
    return nr, ni, no, step_count + 1, "deleted"


def _do_insert_new(w_records, w_ins, w_outs, step_count):
    """Re-insert TARGET with new data in the working copy.  step_count += 1."""
    nr = set(w_records)
    nr.add(TARGET)
    ni = {k: set(v) for k, v in w_ins.items()}
    ni[TARGET] = {"new_in"}
    no = {k: set(v) for k, v in w_outs.items()}
    no[TARGET] = {"new_out"}
    return nr, ni, no, step_count + 1, "inserted"


def _do_commit(dag, w_records, w_ins, w_outs, w_refs, step_count):
    """
    Atomically promote working state to committed and update the DAG.
    remove_node(TARGET) drops the old node and all its edges (incl. ref to OTHER).
    The new node is added without a ref edge since w_refs[TARGET] == {}.
    step_count += 1.

    FIX (A1): Node.resource called with the same three-argument form used in
    _make_init_dag_and_state to maintain a consistent description field
    ("TargetUUID") across the node's lifecycle.
    """
    nc_records = set(w_records)
    nc_ins     = {k: set(v) for k, v in w_ins.items()}
    nc_outs    = {k: set(v) for k, v in w_outs.items()}
    nc_refs    = {k: set(v) for k, v in w_refs.items()}
    dag.remove_node(TARGET)
    dag.add_node(Node.resource(TARGET, "Target Record (committed)", "TargetUUID"))
    return nc_records, nc_ins, nc_outs, nc_refs, step_count + 1, "committed"


def _do_rollback(step_count):
    """Discard working state; committed state and DAG are both unchanged.  step_count += 1."""
    return step_count + 1, "rolled_back"


# ===========================================================================
# Shared backbone runner
# ===========================================================================

def _run_backbone(dag, c_r, c_i, c_o, c_f, reader_saw_partial: bool, *, commit: bool):
    """
    Execute the deterministic upsert backbone:
      BeginUpsert -> NullifyRefs -> DeleteOld -> InsertNew -> DecideOutcome ->
      Commit (commit=True) | RollbackOp (commit=False)

    Invariant-checking note: _assert_invariants is called after every action.
    For intermediate txn states ("begun", "nullified", "deleted", "inserted"),
    the committed store c_r/c_i/c_o/c_f is unchanged, so NoOrphanedIns,
    NoOrphanedOuts, RefIntegrity, AtomicityHolds, BoundedExecution, and
    OtherUUIDUnaffected all hold.  CommitCompleteness and RollbackPreservation
    are vacuously satisfied at those states; they are only meaningfully
    exercised at the terminal Commit / RollbackOp checkpoint.

    Returns (c_records, c_ins, c_outs, c_refs, step_count, txn_state).
    """
    sc, txn = 0, "idle"
    rsp = reader_saw_partial
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "Init")

    w_r, w_i, w_o, w_f, sc, txn = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "BeginUpsert")
    assert sc == 1 and txn == "begun"

    w_f, sc, txn = _do_nullify_refs(w_f, sc)
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "NullifyRefs")
    assert sc == 2 and txn == "nullified"
    assert w_f[TARGET] == set()

    w_r, w_i, w_o, sc, txn = _do_delete_old(w_r, w_i, w_o, sc)
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "DeleteOld")
    assert sc == 3 and txn == "deleted"
    assert TARGET not in w_r

    w_r, w_i, w_o, sc, txn = _do_insert_new(w_r, w_i, w_o, sc)
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "InsertNew")
    assert sc == 4 and txn == "inserted"
    assert TARGET in w_r
    assert w_i[TARGET] == {"new_in"} and w_o[TARGET] == {"new_out"}

    # DecideOutcome: no state change in committed view; step_count unchanged per TLA+
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "DecideOutcome")

    if commit:
        c_r, c_i, c_o, c_f, sc, txn = _do_commit(dag, w_r, w_i, w_o, w_f, sc)
        _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "Commit")
    else:
        sc, txn = _do_rollback(sc)
        _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "RollbackOp")

    assert sc == MAX_STEPS
    return c_r, c_i, c_o, c_f, sc, txn


# ===========================================================================
# Terminal-state assertion helpers
# ===========================================================================

def _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp):
    assert txn == "committed"
    assert sc  == MAX_STEPS
    assert rsp is False
    assert c_r == {TARGET, OTHER}
    assert c_i == {TARGET: {"new_in"},  OTHER: {"other_in"}}
    assert c_o == {TARGET: {"new_out"}, OTHER: set()}
    assert c_f == {TARGET: set(),       OTHER: set()}
    assert _node_exists(dag, TARGET)
    assert _node_exists(dag, OTHER)
    assert dag.edge_count == 0   # ref edge was removed atomically at commit


def _assert_rollback_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp):
    assert txn == "rolled_back"
    assert sc  == MAX_STEPS
    assert rsp is False
    assert c_r == {TARGET, OTHER}
    assert c_i == {TARGET: {"old_in"},  OTHER: {"other_in"}}
    assert c_o == {TARGET: {"old_out"}, OTHER: set()}
    assert c_f == {TARGET: {OTHER},     OTHER: set()}
    assert _node_exists(dag, TARGET)
    assert _node_exists(dag, OTHER)
    # NOTE (G1): edge_count == 1 relies on _make_init_dag_and_state creating
    # exactly one edge (TARGET->OTHER).  Update this constant if the fixture grows.
    assert dag.edge_count == 1   # original ref edge TARGET->OTHER still present


# ===========================================================================
# Trace tests — one per TLC-verified execution
# ===========================================================================

def test_trace_1_commit_readloop_between_commit_and_upsertdone():
    """
    Trace 1 – Commit path.
    Actions: BeginUpsert->NullifyRefs->DeleteOld->InsertNew->DecideOutcome
             ->Commit->ReadLoop->UpsertDone->ReaderDone
    ReadLoop fires AFTER Commit but BEFORE UpsertDone.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    # ReadLoop: reader observes post-commit committed state
    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False, "Reader must not see partial state"
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")

    # UpsertDone and ReaderDone are no-ops
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_2_commit_upsertdone_then_readloop():
    """
    Trace 2 – Commit path.
    Actions: BeginUpsert->...->Commit->UpsertDone->ReadLoop->ReaderDone
    UpsertDone fires before ReadLoop.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_3_commit_upsertdone_readloop_readerdone_second_instance():
    """
    Trace 3 – Commit path (same interleaving as Trace 2; found by TLC independently).
    Actions: BeginUpsert->...->Commit->UpsertDone->ReadLoop->ReaderDone
    Validates consistency across duplicate TLC-generated paths.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_4_rollback_upsertdone_readloop_readerdone():
    """
    Trace 4 – Rollback path.
    Actions: BeginUpsert->...->RollbackOp->UpsertDone->ReadLoop->ReaderDone
    Committed state must be fully preserved; reader sees old consistent view.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=False)
    assert txn == "rolled_back"

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False, "Reader must not see partial state after rollback"
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_rollback_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_5_commit_readloop_readerdone_then_upsertdone():
    """
    Trace 5 – Commit path.
    Actions: BeginUpsert->...->Commit->ReadLoop->ReaderDone->UpsertDone
    Reader completes before UpsertDone marks the upsert process done.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_6_commit_upsertdone_readloop_readerdone_third_instance():
    """
    Trace 6 – Commit path (TLC variant of Traces 2/3).
    Actions: BeginUpsert->...->Commit->UpsertDone->ReadLoop->ReaderDone
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_7_commit_readloop_upsertdone_readerdone():
    """
    Trace 7 – Commit path.
    Actions: BeginUpsert->...->Commit->ReadLoop->UpsertDone->ReaderDone
    ReadLoop fires after Commit; UpsertDone fires after ReadLoop but before ReaderDone.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_8_rollback_upsertdone_readloop_readerdone_second_instance():
    """
    Trace 8 – Rollback path (TLC variant of Trace 4).
    Actions: BeginUpsert->...->RollbackOp->UpsertDone->ReadLoop->ReaderDone
    Verifies rollback consistency independently of Trace 4.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=False)
    assert txn == "rolled_back"

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_rollback_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_9_commit_readloop_readerdone_upsertdone_variant():
    """
    Trace 9 – Commit path (TLC variant of Trace 5).
    Actions: BeginUpsert->...->Commit->ReadLoop->ReaderDone->UpsertDone
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


def test_trace_10_commit_upsertdone_readloop_readerdone_final():
    """
    Trace 10 – Commit path (TLC variant of Traces 2/3/6).
    Actions: BeginUpsert->...->Commit->UpsertDone->ReadLoop->ReaderDone
    Final TLC-verified trace; confirms committed terminal state.
    Tests: NoOrphanedIns, NoOrphanedOuts, RefIntegrity, AtomicityHolds,
           BoundedExecution, CommitCompleteness, RollbackPreservation,
           OtherUUIDUnaffected

    FIX (B1): Body was truncated at '_assert_invariants(c_' causing a
    SyntaxError that prevented the entire module from being collected.
    Completed body matches the interleaving described in the docstring and
    identical to traces 2, 3, 6.
    """
    dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
    rsp = False
    c_r, c_i, c_o, c_f, sc, txn = _run_backbone(dag, c_r, c_i, c_o, c_f, rsp, commit=True)

    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "UpsertDone")

    rsp = _simulate_readloop(c_r, c_i, c_o)
    assert rsp is False
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReadLoop")
    _assert_invariants(c_r, c_i, c_o, c_f, txn, rsp, sc, "ReaderDone")

    _assert_commit_final(dag, c_r, c_i, c_o, c_f, sc, txn, rsp)


# ===========================================================================
# Dedicated invariant verifier tests (>= 2 trace-derived topologies each)
# ===========================================================================

class TestNoOrphanedIns:
    """NoOrphanedIns: c_ins[u] != {} => u in c_records, at every state."""

    def test_no_orphaned_ins_after_commit(self):
        """NoOrphanedIns holds across all keys post-commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        for u, ins in c_i.items():
            if ins:
                assert u in c_r, f"NoOrphanedIns post-commit: {u} has ins but absent"

    def test_no_orphaned_ins_after_rollback(self):
        """NoOrphanedIns holds across all keys post-rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        for u, ins in c_i.items():
            if ins:
                assert u in c_r, f"NoOrphanedIns post-rollback: {u} has ins but absent"

    def test_other_uuid_ins_never_orphaned_commit_and_rollback(self):
        """OTHER always stays in c_records, so other_in is never orphaned."""
        for commit_flag in (True, False):
            dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
            assert OTHER in c_r and c_i[OTHER] == {"other_in"}
            c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
                dag, c_r, c_i, c_o, c_f, False, commit=commit_flag
            )
            assert OTHER in c_r
            assert c_i[OTHER] == {"other_in"}

    def test_target_new_in_not_orphaned_after_commit(self):
        """After commit, c_ins[TARGET]={"new_in"} and TARGET is in c_records."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_i[TARGET] == {"new_in"}
        assert TARGET in c_r


class TestNoOrphanedOuts:
    """NoOrphanedOuts: c_outs[u] != {} => u in c_records, at every state."""

    def test_no_orphaned_outs_after_commit(self):
        """NoOrphanedOuts holds across all keys post-commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        for u, outs in c_o.items():
            if outs:
                assert u in c_r, f"NoOrphanedOuts post-commit: {u} has outs but absent"

    def test_no_orphaned_outs_after_rollback(self):
        """NoOrphanedOuts holds across all keys post-rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        for u, outs in c_o.items():
            if outs:
                assert u in c_r, f"NoOrphanedOuts post-rollback: {u} has outs but absent"

    def test_old_out_replaced_atomically_at_commit(self):
        """old_out is replaced by new_out atomically; no intermediate orphan."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        assert c_o[TARGET] == {"old_out"} and TARGET in c_r
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_o[TARGET] == {"new_out"}
        assert TARGET in c_r

    def test_old_out_preserved_after_rollback(self):
        """old_out is unchanged and TARGET remains in c_records after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert c_o[TARGET] == {"old_out"}
        assert TARGET in c_r


class TestRefIntegrity:
    """RefIntegrity: forall u, forall t in c_refs[u] => t in c_records."""

    def test_ref_integrity_at_init(self):
        """RefIntegrity holds at the TLA+ Init state."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        for u, refs in c_f.items():
            for t in refs:
                assert t in c_r

    def test_ref_cleared_after_commit_integrity_holds_vacuously(self):
        """After commit refs are empty; RefIntegrity holds vacuously."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_f[TARGET] == set()
        assert c_f.get(OTHER, set()) == set()
        for u, refs in c_f.items():
            for t in refs:
                assert t in c_r

    def test_ref_preserved_and_valid_after_rollback(self):
        """After rollback c_refs[TARGET]=={OTHER}; OTHER is still in c_records."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert c_f[TARGET] == {OTHER}
        assert OTHER in c_r
        for u, refs in c_f.items():
            for t in refs:
                assert t in c_r

    def test_dag_edge_removed_at_commit_matches_empty_refs(self):
        """After commit, DAG has no edge TARGET->OTHER; c_refs[TARGET]=={} agrees."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=True)
        assert dag.edge_count == 0

    def test_dag_edge_present_at_rollback_matches_refs(self):
        """After rollback, DAG still has Edge(TARGET->OTHER); c_refs[TARGET]=={OTHER}."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=False)
        assert dag.edge_count == 1


class TestAtomicityHolds:
    """AtomicityHolds: reader_saw_partial = False at every state."""

    def test_no_partial_observed_at_every_step_commit_path(self):
        """ReadLoop returns False at every committed-state checkpoint on the commit path."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        sc = 0

        assert _simulate_readloop(c_r, c_i, c_o) is False          # Init

        w_r, w_i, w_o, w_f, sc, txn = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # BeginUpsert

        w_f, sc, txn = _do_nullify_refs(w_f, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # NullifyRefs

        w_r, w_i, w_o, sc, txn = _do_delete_old(w_r, w_i, w_o, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # DeleteOld

        w_r, w_i, w_o, sc, txn = _do_insert_new(w_r, w_i, w_o, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # InsertNew

        c_r, c_i, c_o, c_f, sc, txn = _do_commit(dag, w_r, w_i, w_o, w_f, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # Post-commit

    def test_no_partial_observed_at_every_step_rollback_path(self):
        """ReadLoop returns False at every committed-state checkpoint on the rollback path."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        sc = 0

        assert _simulate_readloop(c_r, c_i, c_o) is False

        w_r, w_i, w_o, w_f, sc, txn = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False

        w_f, sc, txn = _do_nullify_refs(w_f, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False

        w_r, w_i, w_o, sc, txn = _do_delete_old(w_r, w_i, w_o, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False

        w_r, w_i, w_o, sc, txn = _do_insert_new(w_r, w_i, w_o, sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False

        sc, txn = _do_rollback(sc)
        assert _simulate_readloop(c_r, c_i, c_o) is False          # Post-rollback


class TestBoundedExecution:
    """BoundedExecution: step_count <= MAX_STEPS at every state."""

    def test_step_count_within_bound_after_commit(self):
        """
        BoundedExecution: step_count == MAX_STEPS at backbone completion (commit path).

        FIX (E1): The original plan asserted sc == MAX_STEPS then sc <= MAX_STEPS;
        the second assertion is a tautology once equality holds and has been removed.
        """
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert sc == MAX_STEPS

    def test_step_count_within_bound_after_rollback(self):
        """
        BoundedExecution: step_count == MAX_STEPS at backbone completion (rollback path).

        FIX (E1): Redundant tautological assertion removed.
        """
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert sc == MAX_STEPS

    def test_step_count_increments_correctly_per_action(self):
        """Each mutating action increments step_count by exactly 1."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        sc = 0
        w_r, w_i, w_o, w_f, sc, _ = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
        assert sc == 1
        w_f, sc, _ = _do_nullify_refs(w_f, sc)
        assert sc == 2
        w_r, w_i, w_o, sc, _ = _do_delete_old(w_r, w_i, w_o, sc)
        assert sc == 3
        w_r, w_i, w_o, sc, _ = _do_insert_new(w_r, w_i, w_o, sc)
        assert sc == 4
        # DecideOutcome does not increment (matches TLA+ UNCHANGED step_count)
        _, _, _, _, sc, _ = _do_commit(dag, w_r, w_i, w_o, w_f, sc)
        assert sc == 5

    def test_decide_outcome_does_not_increment_step_count(self):
        """step_count stays at 4 through DecideOutcome (TLA+ UNCHANGED); Commit brings it to 5."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        sc = 0
        w_r, w_i, w_o, w_f, sc, _ = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
        w_f, sc, _ = _do_nullify_refs(w_f, sc)
        w_r, w_i, w_o, sc, _ = _do_delete_old(w_r, w_i, w_o, sc)
        w_r, w_i, w_o, sc, _ = _do_insert_new(w_r, w_i, w_o, sc)
        assert sc == 4
        _, _, _, _, sc_after, _ = _do_commit(dag, w_r, w_i, w_o, w_f, sc)
        assert sc_after == sc + 1 == 5


class TestCommitCompleteness:
    """CommitCompleteness: txn_state=="committed" => TARGET in records, new_in, new_out, empty refs."""

    def test_commit_sets_new_in_for_target(self):
        """CommitCompleteness: c_ins[TARGET] == {"new_in"} after commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert txn == "committed"
        assert c_i[TARGET] == {"new_in"}

    def test_commit_sets_new_out_for_target(self):
        """CommitCompleteness: c_outs[TARGET] == {"new_out"} after commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_o[TARGET] == {"new_out"}

    def test_commit_clears_refs_for_target(self):
        """CommitCompleteness: c_refs[TARGET] == set() after commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_f[TARGET] == set()

    def test_commit_keeps_target_and_other_in_records(self):
        """CommitCompleteness: both TARGET and OTHER remain in c_records after commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert TARGET in c_r and OTHER in c_r

    def test_commit_reflects_target_in_dag(self):
        """After commit the DAG has the new TARGET node (2 nodes) and no ref edges."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=True)
        assert _node_exists(dag, TARGET)
        assert _node_exists(dag, OTHER)
        assert dag.node_count == 2
        assert dag.edge_count == 0


class TestRollbackPreservation:
    """RollbackPreservation: txn_state=="rolled_back" => old_in, old_out, {OTHER} refs."""

    def test_rollback_preserves_old_in_for_target(self):
        """RollbackPreservation: c_ins[TARGET] == {"old_in"} after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert txn == "rolled_back"
        assert c_i[TARGET] == {"old_in"}

    def test_rollback_preserves_old_out_for_target(self):
        """RollbackPreservation: c_outs[TARGET] == {"old_out"} after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert c_o[TARGET] == {"old_out"}

    def test_rollback_preserves_ref_to_other(self):
        """RollbackPreservation: c_refs[TARGET] == {OTHER} and OTHER in c_records after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert c_f[TARGET] == {OTHER}
        assert OTHER in c_r

    def test_rollback_does_not_mutate_dag(self):
        """The DAG (committed store) must be completely unchanged after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        nodes_before = dag.node_count
        edges_before = dag.edge_count
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=False)
        assert dag.node_count == nodes_before
        assert dag.edge_count == edges_before

    def test_rollback_target_still_exists_in_dag(self):
        """Both TARGET and OTHER are still queryable in the DAG after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=False)
        assert _node_exists(dag, TARGET)
        assert _node_exists(dag, OTHER)


class TestOtherUUIDUnaffected:
    """OtherUUIDUnaffected: c_ins[OTHER] = {"other_in"} always."""

    def test_other_uuid_ins_unchanged_after_commit(self):
        """OtherUUIDUnaffected: c_ins[OTHER] is identical before and after commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        before = frozenset(c_i[OTHER])
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert c_i[OTHER] == before == {"other_in"}

    def test_other_uuid_ins_unchanged_after_rollback(self):
        """OtherUUIDUnaffected: c_ins[OTHER] is identical before and after rollback."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        before = frozenset(c_i[OTHER])
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=False
        )
        assert c_i[OTHER] == before == {"other_in"}

    def test_other_uuid_in_records_at_every_working_step(self):
        """OTHER stays in c_records (committed) through all working-state phases."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        sc = 0
        assert OTHER in c_r                                             # Init

        w_r, w_i, w_o, w_f, sc, _ = _do_begin_upsert(c_r, c_i, c_o, c_f, sc)
        assert OTHER in c_r                                             # committed c_r unchanged
        assert OTHER in w_r                                             # also in working copy

        w_f, sc, _ = _do_nullify_refs(w_f, sc)
        assert OTHER in c_r

        w_r, w_i, w_o, sc, _ = _do_delete_old(w_r, w_i, w_o, sc)
        assert OTHER in c_r                                             # committed still intact
        assert OTHER in w_r                                             # working copy has OTHER

        w_r, w_i, w_o, sc, _ = _do_insert_new(w_r, w_i, w_o, sc)
        assert OTHER in c_r

        c_r, c_i, c_o, c_f, sc, _ = _do_commit(dag, w_r, w_i, w_o, w_f, sc)
        assert OTHER in c_r                                             # promoted committed state

    def test_other_uuid_outs_always_empty(self):
        """c_outs[OTHER] is {} throughout both commit and rollback paths."""
        for commit_flag in (True, False):
            dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
            assert c_o[OTHER] == set()
            c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
                dag, c_r, c_i, c_o, c_f, False, commit=commit_flag
            )
            assert c_o[OTHER] == set()


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_dag_raises_node_not_found_on_query(self):
        """NodeNotFoundError is raised when querying an absent node."""
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("does-not-exist")

    def test_empty_dag_zero_counts(self):
        """A freshly constructed RegistryDag has node_count==0 and edge_count==0."""
        dag = RegistryDag()
        assert dag.node_count == 0
        assert dag.edge_count == 0

    def test_remove_node_drops_its_incident_edges(self):
        """remove_node(TARGET) also removes Edge(TARGET->OTHER); TARGET becomes absent."""
        dag, *_ = _make_init_dag_and_state()
        assert dag.edge_count >= 1
        dag.remove_node(TARGET)
        assert dag.edge_count == 0
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant(TARGET)

    def test_remove_node_leaves_other_node_intact(self):
        """Removing TARGET leaves OTHER queryable and node_count==1."""
        dag, *_ = _make_init_dag_and_state()
        dag.remove_node(TARGET)
        assert _node_exists(dag, OTHER)
        assert dag.node_count == 1

    def test_readloop_flags_absent_node_with_leftover_ins(self):
        """Partial-state detector: TARGET absent from records but c_ins non-empty -> True."""
        c_r = {OTHER}
        c_i = {TARGET: {"stale_in"}, OTHER: {"other_in"}}
        c_o = {TARGET: set(),        OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is True

    def test_readloop_flags_present_node_with_no_ins_and_no_outs(self):
        """Partial-state detector: TARGET in records but both ins and outs empty -> True."""
        c_r = {TARGET, OTHER}
        c_i = {TARGET: set(),       OTHER: {"other_in"}}
        c_o = {TARGET: set(),       OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is True

    def test_readloop_does_not_flag_consistent_committed_new_state(self):
        """new_in + new_out + TARGET in records is a consistent committed state -> False."""
        c_r = {TARGET, OTHER}
        c_i = {TARGET: {"new_in"},  OTHER: {"other_in"}}
        c_o = {TARGET: {"new_out"}, OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is False

    def test_readloop_does_not_flag_consistent_committed_old_state(self):
        """old_in + old_out + TARGET in records is a consistent committed state -> False."""
        c_r = {TARGET, OTHER}
        c_i = {TARGET: {"old_in"},  OTHER: {"other_in"}}
        c_o = {TARGET: {"old_out"}, OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is False

    def test_readloop_does_not_flag_absent_node_with_empty_ins_and_outs(self):
        """TARGET absent AND c_ins[TARGET]=={} AND c_outs[TARGET]=={}: not partial -> False."""
        c_r = {OTHER}
        c_i = {TARGET: set(), OTHER: {"other_in"}}
        c_o = {TARGET: set(), OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is False

    def test_readloop_does_not_flag_node_with_ins_but_no_outs(self):
        """
        Per the TLA+ ReadLoop guard, the partial condition for TARGET-in-records is
        c_ins[TARGET]=={} AND c_outs[TARGET]=={}.  If ins is non-empty but outs is
        empty, the AND condition is False — not flagged as partial.

        This is correct for the atomic-commit model: the committed view can only
        hold (old_in ^ old_out) or (new_in ^ new_out); the asymmetric case is
        unreachable in committed state, so the detector need not handle it.

        Coverage (D3): documents the AND-condition boundary.
        """
        c_r = {TARGET, OTHER}
        c_i = {TARGET: {"old_in"}, OTHER: {"other_in"}}
        c_o = {TARGET: set(),      OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is False

    def test_readloop_does_not_flag_node_with_outs_but_no_ins(self):
        """
        Symmetric to the above: outs non-empty, ins empty, TARGET in records.
        The AND condition evaluates to False — not flagged as partial per spec.

        Coverage (D3): documents the AND-condition boundary for the outs-only case.
        """
        c_r = {TARGET, OTHER}
        c_i = {TARGET: set(),       OTHER: {"other_in"}}
        c_o = {TARGET: {"old_out"}, OTHER: set()}
        assert _simulate_readloop(c_r, c_i, c_o) is False

    def test_isolated_nodes_no_edges_valid(self):
        """Two nodes with no edges are valid; query_relevant works for each."""
        dag = RegistryDag()
        dag.add_node(Node.resource("node-a", "Node A"))
        dag.add_node(Node.resource("node-b", "Node B"))
        assert dag.node_count == 2
        assert dag.edge_count == 0
        assert _node_exists(dag, "node-a")
        assert _node_exists(dag, "node-b")

    def test_single_record_upsert_no_refs(self):
        """Upsert on a single-record DAG (no OTHER reference) commits correctly."""
        dag = RegistryDag()
        dag.add_node(Node.resource(TARGET, "Sole Record"))
        c_r = {TARGET}
        c_i = {TARGET: {"solo_in"}}
        c_o = {TARGET: {"solo_out"}}
        c_f = {TARGET: set()}   # no ref to OTHER in this topology

        w_r, w_i, w_o, w_f, sc, txn = _do_begin_upsert(c_r, c_i, c_o, c_f, 0)
        w_f, sc, txn = _do_nullify_refs(w_f, sc)        # no-op: refs already empty
        w_r, w_i, w_o, sc, txn = _do_delete_old(w_r, w_i, w_o, sc)
        w_r, w_i, w_o, sc, txn = _do_insert_new(w_r, w_i, w_o, sc)
        c_r, c_i, c_o, c_f, sc, txn = _do_commit(dag, w_r, w_i, w_o, w_f, sc)

        assert txn == "committed"
        assert TARGET in c_r
        assert c_i[TARGET] == {"new_in"}
        assert c_o[TARGET] == {"new_out"}
        assert c_f[TARGET] == set()
        assert _node_exists(dag, TARGET)

    def test_single_record_upsert_rollback_preserves_state(self):
        """Single-record DAG: rollback leaves the original state and DAG intact."""
        dag = RegistryDag()
        dag.add_node(Node.resource(TARGET, "Sole Record"))
        c_r = {TARGET}
        c_i = {TARGET: {"solo_in"}}
        c_o = {TARGET: {"solo_out"}}
        c_f = {TARGET: set()}
        nodes_before = dag.node_count

        w_r, w_i, w_o, w_f, sc, txn = _do_begin_upsert(c_r, c_i, c_o, c_f, 0)
        w_f, sc, txn = _do_nullify_refs(w_f, sc)
        w_r, w_i, w_o, sc, txn = _do_delete_old(w_r, w_i, w_o, sc)
        w_r, w_i, w_o, sc, txn = _do_insert_new(w_r, w_i, w_o, sc)
        sc, txn = _do_rollback(sc)

        assert txn == "rolled_back"
        assert c_i[TARGET] == {"solo_in"}
        assert c_o[TARGET] == {"solo_out"}
        assert TARGET in c_r
        assert dag.node_count == nodes_before

    def test_concurrent_overshoot_bound_gwt(self):
        """
        GWT (gwt-0024): Given max_functions=M=1 and concurrency=N=2,
        When the single commit completes (M-th extraction) and an additional
             in-flight reader also finishes (the N-1 overshoot),
        Then both observations see a consistent state and
             step_count remains within [M, M+N-1] which is covered by MAX_STEPS.
        """
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        c_r, c_i, c_o, c_f, sc, txn = _run_backbone(
            dag, c_r, c_i, c_o, c_f, False, commit=True
        )
        assert txn == "committed"
        assert sc <= MAX_STEPS

        # Simulate N-1=1 additional in-flight reader completing after limit reached
        overshoot_partial = _simulate_readloop(c_r, c_i, c_o)
        assert overshoot_partial is False   # overshoot reader sees consistent state

        # A second reader (worst-case overshoot) also sees consistent state
        second_reader_partial = _simulate_readloop(c_r, c_i, c_o)
        assert second_reader_partial is False

        # Final step count stays within the accepted overshoot bound
        assert 1 <= sc <= MAX_STEPS

    def test_validate_edge_between_two_existing_nodes(self):
        """validate_edge returns a ValidationResult (no exception) for two live nodes."""
        dag, *_ = _make_init_dag_and_state()
        result = dag.validate_edge(OTHER, TARGET, EdgeType.IMPORTS)
        assert result is not None

    def test_add_node_then_query_relevant_succeeds(self):
        """A freshly-added node is immediately queryable via query_relevant."""
        dag = RegistryDag()
        dag.add_node(Node.resource("fresh-node", "Fresh"))
        result = dag.query_relevant("fresh-node")
        assert result is not None

    def test_extract_subgraph_target_after_commit(self):
        """extract_subgraph on TARGET after commit returns a SubgraphResult."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=True)
        result = dag.extract_subgraph(TARGET)
        assert result is not None

    def test_extract_subgraph_other_unaffected_after_commit(self):
        """OTHER's subgraph is still accessible after a TARGET commit."""
        dag, c_r, c_i, c_o, c_f = _make_init_dag_and_state()
        _run_backbone(dag, c_r, c_i, c_o, c_f, False, commit=True)
        result = dag.extract_subgraph(OTHER)
        assert result is not None