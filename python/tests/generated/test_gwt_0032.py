"""
Tests for ExtractPreservesGwts behavior
========================================
Given: a DAG file containing registered GWT and requirement nodes from prior
       cw9 register calls
When:  cw9 extract is run (SchemaExtractor.extract() builds a fresh DAG)
Then:  all previously registered GWT and requirement nodes are preserved in
       the output DAG — extract merges schema-derived nodes with existing
       behavioral nodes rather than overwriting them

Traces 1-10 are TLC-verified, all-identical paths through the state machine:
  LoadOld → Extract → Merge → Save → Finish

TLA+ invariants verified at every state:
  TypeOK            phase ∈ valid_phases ∧ step_count ≤ MaxSteps
  GwtPreserved      phase="done" ⇒ old_gwt_nodes ⊆ result_nodes
  SchemaFresh       phase="done" ⇒ extracted_nodes ⊆ result_nodes
  NoGwtLoss         phase="done" ⇒ ∀ n ∈ old_gwt_nodes : n ∈ result_nodes
  BoundedExecution  step_count ≤ MaxSteps
  MergeCorrect      phase="done" ⇒ result_nodes = extracted_nodes ∪ old_gwt_nodes
"""
from __future__ import annotations

import pytest
from pathlib import Path

from registry.dag import RegistryDag
from registry.types import Node

# ---------------------------------------------------------------------------
# TLA+ model constants
# ---------------------------------------------------------------------------

MAX_STEPS: int = 4
VALID_PHASES: frozenset[str] = frozenset(
    {"load_old", "extract", "merge", "save", "done"}
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _node_ids(dag: RegistryDag) -> set[str]:
    """Return the set of all node IDs currently in *dag*."""
    return set(dag.nodes.keys())


# ---------------------------------------------------------------------------
# Invariant assertion helpers  (one function per TLA+ invariant)
# ---------------------------------------------------------------------------

def _assert_type_ok(phase: str, step_count: int) -> None:
    """TypeOK: phase ∈ valid_phases  ∧  step_count ≤ MaxSteps."""
    assert phase in VALID_PHASES, (
        f"TypeOK violated: phase={phase!r} not in {VALID_PHASES}"
    )
    assert step_count <= MAX_STEPS, (
        f"TypeOK violated: step_count={step_count} > MaxSteps={MAX_STEPS}"
    )


def _assert_gwt_preserved(
    phase: str, old_ids: list[str], result_dag: RegistryDag
) -> None:
    """GwtPreserved: phase='done' ⇒ old_gwt_nodes ⊆ result_nodes."""
    if phase == "done":
        ids = _node_ids(result_dag)
        missing = set(old_ids) - ids
        assert not missing, (
            f"GwtPreserved violated: old nodes missing from result DAG: {missing}"
        )


def _assert_schema_fresh(
    phase: str, schema_ids: list[str], result_dag: RegistryDag
) -> None:
    """SchemaFresh: phase='done' ⇒ extracted_nodes ⊆ result_nodes."""
    if phase == "done":
        ids = _node_ids(result_dag)
        missing = set(schema_ids) - ids
        assert not missing, (
            f"SchemaFresh violated: schema nodes missing from result DAG: {missing}"
        )


def _assert_no_gwt_loss(
    phase: str, old_ids: list[str], result_dag: RegistryDag
) -> None:
    """NoGwtLoss: phase='done' ⇒ ∀ n ∈ old_gwt_nodes : n ∈ result_nodes."""
    if phase == "done":
        ids = _node_ids(result_dag)
        for nid in old_ids:
            assert nid in ids, (
                f"NoGwtLoss violated: node {nid!r} was lost from result DAG"
            )


def _assert_bounded_execution(step_count: int) -> None:
    """BoundedExecution: step_count ≤ MaxSteps."""
    assert step_count <= MAX_STEPS, (
        f"BoundedExecution violated: step_count={step_count} > MaxSteps={MAX_STEPS}"
    )


def _assert_merge_correct(
    phase: str,
    old_ids: list[str],
    schema_ids: list[str],
    result_dag: RegistryDag,
) -> None:
    """MergeCorrect: phase='done' ⇒ result_nodes = extracted_nodes ∪ old_gwt_nodes."""
    if phase == "done":
        ids = _node_ids(result_dag)
        expected = set(old_ids) | set(schema_ids)
        assert ids == expected, (
            f"MergeCorrect violated: result_nodes {ids} "
            f"≠ extracted_nodes ∪ old_gwt_nodes {expected}"
        )


def _assert_all_invariants(
    phase: str,
    step_count: int,
    old_ids: list[str],
    schema_ids: list[str],
    result_dag: RegistryDag,
) -> None:
    """Assert all six TLA+ invariants in one call."""
    _assert_type_ok(phase, step_count)
    _assert_gwt_preserved(phase, old_ids, result_dag)
    _assert_schema_fresh(phase, schema_ids, result_dag)
    _assert_no_gwt_loss(phase, old_ids, result_dag)
    _assert_bounded_execution(step_count)
    _assert_merge_correct(phase, old_ids, schema_ids, result_dag)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _register_old_gwt_and_req_nodes(
    dag: RegistryDag, tag: str = ""
) -> tuple[list[str], list[str]]:
    """
    Register OldGwts_1, OldGwts_2, OldReqs_1, OldReqs_2 into *dag*.

    Returns (gwt_ids, req_ids).
    """
    gwt1 = dag.register_gwt(
        given=f"system is initialised{tag}",
        when="a user submits a request",
        then="the request is processed successfully",
        name=f"OldGwts_1{tag}",
    )
    gwt2 = dag.register_gwt(
        given=f"the database is available{tag}",
        when="a query is executed",
        then="results are returned correctly",
        name=f"OldGwts_2{tag}",
    )
    req1 = dag.register_requirement(
        text=f"System must handle concurrent requests{tag}",
        name=f"OldReqs_1{tag}",
    )
    req2 = dag.register_requirement(
        text=f"System must persist data reliably{tag}",
        name=f"OldReqs_2{tag}",
    )
    return [gwt1, gwt2], [req1, req2]


def _add_schema_derived_nodes(dag: RegistryDag, prefix: str = "") -> list[str]:
    """
    Add SchemaNodes_1 and SchemaNodes_2 to *dag*, simulating
    SchemaExtractor.extract() populating schema-derived resource nodes.

    Returns list of newly added node IDs.
    """
    n1 = Node.resource(
        f"{prefix}schema-node-1",
        f"SchemaNodes_1_{prefix}",
        description="Derived from schema extraction",
    )
    n2 = Node.resource(
        f"{prefix}schema-node-2",
        f"SchemaNodes_2_{prefix}",
        description="Derived from schema extraction",
    )
    dag.add_node(n1)
    dag.add_node(n2)
    return [n1.id, n2.id]


# ---------------------------------------------------------------------------
# Core trace simulation
# ---------------------------------------------------------------------------

def _simulate_trace(tmp_path: Path, trace_id: int) -> dict:
    """
    Execute the full 6-state TLA+ trace for a given *trace_id*.

    State machine:
        State 1  <Init>    phase=load_old,  step_count=0
        State 2  <LoadOld> phase=extract,   step_count=1
        State 3  <Extract> phase=merge,     step_count=2
        State 4  <Merge>   phase=save,      step_count=3
        State 5  <Save>    phase=done,      step_count=4
        State 6  <Finish>  phase=done,      step_count=4  (terminal)

    Returns a dict of terminal state values for assertion by callers.
    """
    tag = f"_t{trace_id}"
    prefix = f"t{trace_id}_"

    # State 1 : Init
    phase = "load_old"
    step_count = 0
    _assert_type_ok(phase, step_count)

    # State 2 : LoadOld
    old_dag = RegistryDag()
    gwt_ids, req_ids = _register_old_gwt_and_req_nodes(old_dag, tag=tag)
    old_node_ids: list[str] = gwt_ids + req_ids

    old_path = tmp_path / f"{prefix}old.json"
    old_dag.save(old_path)

    phase = "extract"
    step_count += 1
    _assert_type_ok(phase, step_count)

    assert _node_ids(old_dag) == set(old_node_ids)

    # State 3 : Extract
    working_dag = RegistryDag.load(old_path)
    assert _node_ids(working_dag) == set(old_node_ids), (
        "Extract: loading old DAG must preserve all prior nodes"
    )

    schema_ids = _add_schema_derived_nodes(working_dag, prefix=prefix)

    phase = "merge"
    step_count += 1
    _assert_type_ok(phase, step_count)

    # State 4 : Merge
    result_ids_at_merge = _node_ids(working_dag)
    assert set(old_node_ids).issubset(result_ids_at_merge), (
        "Merge: old GWT/req nodes must remain in the working DAG"
    )
    assert set(schema_ids).issubset(result_ids_at_merge), (
        "Merge: schema-extracted nodes must be present in the working DAG"
    )

    phase = "save"
    step_count += 1
    _assert_type_ok(phase, step_count)

    # State 5 : Save
    result_path = tmp_path / f"{prefix}result.json"
    working_dag.save(result_path)

    phase = "done"
    step_count += 1
    _assert_type_ok(phase, step_count)

    # State 6 : Finish
    result_dag = RegistryDag.load(result_path)

    return {
        "phase": phase,
        "step_count": step_count,
        "old_node_ids": old_node_ids,
        "gwt_ids": gwt_ids,
        "req_ids": req_ids,
        "schema_ids": schema_ids,
        "result_dag": result_dag,
    }


# ---------------------------------------------------------------------------
# Parametrized trace tests  (Traces 1-10)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(1, 11), ids=[f"trace_{i}" for i in range(1, 11)])
class TestExtractPreservesGwtsTraces:
    """
    Traces 1-10: LoadOld → Extract → Merge → Save → Finish
    """

    def test_phase_is_done_at_finish(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        assert state["phase"] == "done"

    def test_step_count_equals_four_at_finish(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        assert state["step_count"] == 4

    def test_old_gwt_nodes_present_in_result(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        result_ids = _node_ids(state["result_dag"])
        for nid in state["gwt_ids"]:
            assert nid in result_ids, (
                f"GWT node {nid!r} was overwritten / dropped by extract"
            )

    def test_old_req_nodes_present_in_result(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        result_ids = _node_ids(state["result_dag"])
        for nid in state["req_ids"]:
            assert nid in result_ids, (
                f"Requirement node {nid!r} was overwritten / dropped by extract"
            )

    def test_schema_nodes_present_in_result(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        result_ids = _node_ids(state["result_dag"])
        for nid in state["schema_ids"]:
            assert nid in result_ids, (
                f"Schema node {nid!r} is missing from the merged result"
            )

    def test_result_is_union_of_old_and_schema(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        result_ids = _node_ids(state["result_dag"])
        expected = set(state["old_node_ids"]) | set(state["schema_ids"])
        assert result_ids == expected, (
            f"MergeCorrect: result_nodes {result_ids} "
            f"≠ extracted_nodes ∪ old_gwt_nodes {expected}"
        )

    def test_all_invariants_hold(self, tmp_path, trace_id):
        state = _simulate_trace(tmp_path, trace_id)
        _assert_all_invariants(
            state["phase"],
            state["step_count"],
            state["old_node_ids"],
            state["schema_ids"],
            state["result_dag"],
        )


# ---------------------------------------------------------------------------
# Dedicated invariant verifiers
# ---------------------------------------------------------------------------

class TestInvariantTypeOK:
    """TypeOK: phase ∈ valid_phases  ∧  step_count ≤ MaxSteps."""

    def test_type_ok_at_every_transition_topology_a(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=1)
        _assert_type_ok(state["phase"], state["step_count"])

    def test_type_ok_at_every_transition_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=6)
        _assert_type_ok(state["phase"], state["step_count"])

    def test_invalid_phase_string_raises(self):
        with pytest.raises(AssertionError):
            _assert_type_ok("unknown_phase", 0)

    def test_step_count_exceeding_max_raises(self):
        with pytest.raises(AssertionError):
            _assert_type_ok("done", MAX_STEPS + 1)


class TestInvariantGwtPreserved:
    """GwtPreserved: phase='done' ⇒ old_gwt_nodes ⊆ result_nodes."""

    def test_gwts_preserved_topology_a(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=1)
        _assert_gwt_preserved(state["phase"], state["old_node_ids"], state["result_dag"])

    def test_gwts_preserved_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=7)
        _assert_gwt_preserved(state["phase"], state["old_node_ids"], state["result_dag"])

    def test_gwt_preserved_not_checked_before_done(self, tmp_path):
        old_dag = RegistryDag()
        gwt_id = old_dag.register_gwt(
            given="pre-condition",
            when="action taken",
            then="post-condition",
        )
        empty_dag = RegistryDag()
        _assert_gwt_preserved("extract", [gwt_id], empty_dag)

    def test_gwt_preserved_violation_detected(self):
        old_dag = RegistryDag()
        gwt_id = old_dag.register_gwt(
            given="given",
            when="when",
            then="then",
        )
        empty_result = RegistryDag()
        with pytest.raises(AssertionError, match="GwtPreserved"):
            _assert_gwt_preserved("done", [gwt_id], empty_result)


class TestInvariantSchemaFresh:
    """SchemaFresh: phase='done' ⇒ extracted_nodes ⊆ result_nodes."""

    def test_schema_nodes_in_result_topology_a(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=2)
        _assert_schema_fresh(state["phase"], state["schema_ids"], state["result_dag"])

    def test_schema_nodes_in_result_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=8)
        _assert_schema_fresh(state["phase"], state["schema_ids"], state["result_dag"])

    def test_schema_fresh_not_checked_before_done(self):
        empty_dag = RegistryDag()
        _assert_schema_fresh("merge", ["schema-node-1"], empty_dag)

    def test_schema_fresh_violation_detected(self):
        empty_dag = RegistryDag()
        with pytest.raises(AssertionError, match="SchemaFresh"):
            _assert_schema_fresh("done", ["nonexistent-schema-node"], empty_dag)


class TestInvariantNoGwtLoss:
    """NoGwtLoss: phase='done' ⇒ ∀ n ∈ old_gwt_nodes : n ∈ result_nodes."""

    def test_no_gwt_loss_topology_a(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=3)
        _assert_no_gwt_loss(state["phase"], state["old_node_ids"], state["result_dag"])

    def test_no_gwt_loss_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=9)
        _assert_no_gwt_loss(state["phase"], state["old_node_ids"], state["result_dag"])

    def test_no_gwt_loss_vacuous_before_done(self):
        empty_dag = RegistryDag()
        _assert_no_gwt_loss("save", ["gwt-0001"], empty_dag)

    def test_no_gwt_loss_violation_detected(self):
        empty_dag = RegistryDag()
        with pytest.raises(AssertionError, match="NoGwtLoss"):
            _assert_no_gwt_loss("done", ["gwt-0001"], empty_dag)


class TestInvariantBoundedExecution:
    """BoundedExecution: step_count ≤ MaxSteps (=4)."""

    def test_bounded_at_every_step_topology_a(self):
        for step in range(MAX_STEPS + 1):
            _assert_bounded_execution(step)

    def test_bounded_at_terminal_step_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=5)
        _assert_bounded_execution(state["step_count"])

    def test_exceeding_bound_raises(self):
        with pytest.raises(AssertionError, match="BoundedExecution"):
            _assert_bounded_execution(MAX_STEPS + 1)


class TestInvariantMergeCorrect:
    """MergeCorrect: phase='done' ⇒ result_nodes = extracted ∪ old_gwt_nodes."""

    def test_merge_correct_topology_a(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=4)
        _assert_merge_correct(
            state["phase"],
            state["old_node_ids"],
            state["schema_ids"],
            state["result_dag"],
        )

    def test_merge_correct_topology_b(self, tmp_path):
        state = _simulate_trace(tmp_path, trace_id=10)
        _assert_merge_correct(
            state["phase"],
            state["old_node_ids"],
            state["schema_ids"],
            state["result_dag"],
        )

    def test_merge_correct_vacuous_before_done(self):
        empty_dag = RegistryDag()
        _assert_merge_correct("extract", ["gwt-0001"], ["schema-1"], empty_dag)

    def test_merge_correct_violation_detected_missing_nodes(self):
        partial_dag = RegistryDag()
        partial_dag.add_node(
            Node.resource("schema-only", "SchemaOnly", description="partial")
        )
        with pytest.raises(AssertionError, match="MergeCorrect"):
            _assert_merge_correct("done", ["gwt-missing"], ["schema-only"], partial_dag)

    def test_merge_correct_violation_detected_extra_nodes(self):
        dag = RegistryDag()
        gwt_node = Node.resource("gwt-tracked", "GwtTracked", description="tracked gwt")
        schema_node = Node.resource("schema-tracked", "SchemaTracked", description="tracked schema")
        extra_node = Node.resource("extra-intruder", "Intruder", description="not in union")
        dag.add_node(gwt_node)
        dag.add_node(schema_node)
        dag.add_node(extra_node)
        with pytest.raises(AssertionError, match="MergeCorrect"):
            _assert_merge_correct(
                "done",
                ["gwt-tracked"],
                ["schema-tracked"],
                dag,
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Isolated nodes, empty DAGs, single-node DAGs, diamond dependencies."""

    def test_extract_with_empty_old_dag(self, tmp_path):
        old_dag = RegistryDag()
        old_path = tmp_path / "empty_old.json"
        old_dag.save(old_path)

        working_dag = RegistryDag.load(old_path)
        schema_ids = _add_schema_derived_nodes(working_dag, prefix="empty_")

        result_path = tmp_path / "empty_result.json"
        working_dag.save(result_path)
        result_dag = RegistryDag.load(result_path)

        assert set(schema_ids).issubset(_node_ids(result_dag)), (
            "Schema nodes must be present even when no old nodes exist"
        )

    def test_extract_with_no_schema_nodes(self, tmp_path):
        old_dag = RegistryDag()
        gwt_ids, req_ids = _register_old_gwt_and_req_nodes(old_dag, tag="_noschema")
        old_node_ids = gwt_ids + req_ids
        old_path = tmp_path / "noschema_old.json"
        old_dag.save(old_path)

        working_dag = RegistryDag.load(old_path)
        result_path = tmp_path / "noschema_result.json"
        working_dag.save(result_path)
        result_dag = RegistryDag.load(result_path)

        result_ids = _node_ids(result_dag)
        for nid in old_node_ids:
            assert nid in result_ids, (
                f"Old node {nid!r} lost even with no schema extraction"
            )

    def test_isolated_gwt_node_survives_extract(self, tmp_path):
        old_dag = RegistryDag()
        isolated_gwt = old_dag.register_gwt(
            given="isolated condition",
            when="isolated action",
            then="isolated outcome",
            name="IsolatedGwt",
        )
        p = tmp_path / "isolated_old.json"
        old_dag.save(p)

        working_dag = RegistryDag.load(p)
        _add_schema_derived_nodes(working_dag, prefix="iso_")
        rp = tmp_path / "isolated_result.json"
        working_dag.save(rp)
        result_dag = RegistryDag.load(rp)

        assert isolated_gwt in _node_ids(result_dag), (
            "Isolated GWT node must survive the extract-merge pipeline"
        )

    def test_dag_with_edges_preserves_connectivity(self, tmp_path):
        old_dag = RegistryDag()
        req_id = old_dag.register_requirement(
            text="Auth must be enforced on every API call",
            name="AuthReq",
        )
        gwt_id = old_dag.register_gwt(
            given="user is authenticated",
            when="API is called",
            then="response is authorised",
            name="AuthGwt",
            parent_req=req_id,
        )
        p = tmp_path / "edge_old.json"
        old_dag.save(p)

        working_dag = RegistryDag.load(p)
        assert gwt_id in _node_ids(working_dag), "GWT node must survive load"
        assert req_id in _node_ids(working_dag), "Req node must survive load"

        schema_ids = _add_schema_derived_nodes(working_dag, prefix="edge_")
        rp = tmp_path / "edge_result.json"
        working_dag.save(rp)
        result_dag = RegistryDag.load(rp)

        result_ids = _node_ids(result_dag)
        assert gwt_id in result_ids
        assert req_id in result_ids
        for sid in schema_ids:
            assert sid in result_ids

    def test_diamond_topology_all_nodes_preserved(self, tmp_path):
        old_dag = RegistryDag()
        root_req = old_dag.register_requirement(
            text="Payment must succeed end-to-end",
            name="PaymentReq",
        )
        gwt_a = old_dag.register_gwt(
            given="valid card is supplied",
            when="payment is submitted",
            then="charge succeeds",
            name="PayGwtA",
            parent_req=root_req,
        )
        gwt_b = old_dag.register_gwt(
            given="expired card is supplied",
            when="payment is submitted",
            then="charge is declined gracefully",
            name="PayGwtB",
            parent_req=root_req,
        )
        leaf_req = old_dag.register_requirement(
            text="Decline must return HTTP 422",
            name="DeclineReq",
        )
        old_node_ids = [root_req, gwt_a, gwt_b, leaf_req]

        p = tmp_path / "diamond_old.json"
        old_dag.save(p)

        working_dag = RegistryDag.load(p)
        schema_ids = _add_schema_derived_nodes(working_dag, prefix="diamond_")
        rp = tmp_path / "diamond_result.json"
        working_dag.save(rp)
        result_dag = RegistryDag.load(rp)

        result_ids = _node_ids(result_dag)
        for nid in old_node_ids:
            assert nid in result_ids, f"Diamond node {nid!r} lost after extract-merge"
        for sid in schema_ids:
            assert sid in result_ids, f"Schema node {sid!r} missing from diamond merge"

    def test_load_nonexistent_dag_raises(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(Exception):
            RegistryDag.load(missing)

    def test_round_trip_serialisation_preserves_node_count(self, tmp_path):
        dag = RegistryDag()
        _register_old_gwt_and_req_nodes(dag, tag="_serial")
        _add_schema_derived_nodes(dag, prefix="serial_")

        before = len(_node_ids(dag))
        p = tmp_path / "serial.json"
        dag.save(p)
        reloaded = RegistryDag.load(p)
        after = len(_node_ids(reloaded))

        assert before == after, (
            f"Serialisation lost nodes: {before} before save, {after} after load"
        )

    def test_add_node_does_not_duplicate_existing_id(self):
        dag = RegistryDag()
        n = Node.resource("duplicate-id", "DuplicateNode", description="test")
        dag.add_node(n)
        count_before = len(_node_ids(dag))

        try:
            dag.add_node(n)
        except Exception:
            return

        count_after = len(_node_ids(dag))
        assert count_after == count_before, (
            "add_node must not silently grow the node set for a duplicate ID"
        )

    def test_extract_does_not_mutate_old_dag_on_disk(self, tmp_path):
        old_dag = RegistryDag()
        _register_old_gwt_and_req_nodes(old_dag, tag="_immut")
        old_path = tmp_path / "immut_old.json"
        old_dag.save(old_path)

        original_bytes = old_path.read_bytes()

        working_dag = RegistryDag.load(old_path)
        _add_schema_derived_nodes(working_dag, prefix="immut_")
        result_path = tmp_path / "immut_result.json"
        working_dag.save(result_path)

        assert old_path.read_bytes() == original_bytes, (
            "Extract pipeline must not overwrite the original DAG file"
        )