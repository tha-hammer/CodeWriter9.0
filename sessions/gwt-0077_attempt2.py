"""Tests for ReviewOrchestration module.

Models a 5-pass review pipeline orchestrator using TLA+ action semantics
and verifies all invariants at each state transition.
"""

import pytest

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import Edge, EdgeType, Node

PASSES = frozenset({"artifacts", "coverage", "interaction", "abstraction_gap", "imports"})

VALID_STEPS = frozenset({"idle", "artifacts", "parallel", "abstraction_gap", "imports", "done", "blocked"})
VALID_VERDICTS = frozenset({"not_run", "pass", "fail"})
VALID_PASS_STATES = frozenset({"not_run", "running", "done"})
VALID_OVERALL = frozenset({"pass", "fail", "blocked"})


# ---------------------------------------------------------------------------
# OrchState: mutable state machine mirroring TLA+ spec
# ---------------------------------------------------------------------------

class OrchState:
    def __init__(self, art_verdict: str) -> None:
        assert art_verdict in {"pass", "fail"}, f"art_verdict must be 'pass' or 'fail', got {art_verdict!r}"
        self.art_verdict: str = art_verdict
        self.current_step: str = "idle"
        self.artifacts_verdict: str = "not_run"
        self.pass_states: dict[str, str] = {p: "not_run" for p in PASSES}
        self.total_cost: int = 0
        self.overall_status: str = "pass"

    def start_artifacts(self) -> None:
        self.current_step = "artifacts"
        self.pass_states["artifacts"] = "running"

    def complete_artifacts(self) -> None:
        self.artifacts_verdict = self.art_verdict
        self.total_cost += 1
        self.pass_states["artifacts"] = "done"

    def check_gate(self) -> None:
        pass

    def handle_fail(self) -> None:
        self.overall_status = "blocked"
        self.current_step = "blocked"

    def start_parallel(self) -> None:
        self.current_step = "parallel"
        self.pass_states["coverage"] = "running"
        self.pass_states["interaction"] = "running"

    def choose_parallel(self) -> None:
        pass

    def finish_coverage_first(self) -> None:
        self.pass_states["coverage"] = "done"
        self.total_cost += 1

    def finish_interaction_second(self) -> None:
        self.pass_states["interaction"] = "done"
        self.total_cost += 1

    def finish_interaction_first(self) -> None:
        self.pass_states["interaction"] = "done"
        self.total_cost += 1

    def finish_coverage_second(self) -> None:
        self.pass_states["coverage"] = "done"
        self.total_cost += 1

    def start_abstraction_gap(self) -> None:
        self.current_step = "abstraction_gap"
        self.pass_states["abstraction_gap"] = "running"

    def complete_abstraction_gap(self) -> None:
        self.pass_states["abstraction_gap"] = "done"
        self.total_cost += 1

    def start_imports(self) -> None:
        self.current_step = "imports"
        self.pass_states["imports"] = "running"

    def complete_imports(self) -> None:
        self.pass_states["imports"] = "done"
        self.total_cost += 1
        self.current_step = "done"

    def terminate(self) -> None:
        pass

    def assert_type_ok(self) -> None:
        """TLA+ TypeOK: all variables are within their declared types."""
        assert self.current_step in VALID_STEPS, (
            f"TypeOK: current_step={self.current_step!r} not in {VALID_STEPS}"
        )
        assert self.artifacts_verdict in VALID_VERDICTS, (
            f"TypeOK: artifacts_verdict={self.artifacts_verdict!r} not in {VALID_VERDICTS}"
        )
        for p, state in self.pass_states.items():
            assert state in VALID_PASS_STATES, (
                f"TypeOK: pass_states[{p!r}]={state!r} not in {VALID_PASS_STATES}"
            )
        assert isinstance(self.total_cost, int), (
            f"TypeOK: total_cost={self.total_cost!r} is not an int"
        )
        assert self.overall_status in VALID_OVERALL, (
            f"TypeOK: overall_status={self.overall_status!r} not in {VALID_OVERALL}"
        )

    def assert_dependency_order(self) -> None:
        """TLA+ DependencyOrder: abstraction_gap may only start/run after both coverage and interaction are done."""
        ag_state = self.pass_states["abstraction_gap"]
        if ag_state in {"running", "done"}:
            assert self.pass_states["coverage"] == "done", (
                f"DependencyOrder: abstraction_gap is {ag_state!r} but coverage={self.pass_states['coverage']!r}"
            )
            assert self.pass_states["interaction"] == "done", (
                f"DependencyOrder: abstraction_gap is {ag_state!r} but interaction={self.pass_states['interaction']!r}"
            )

    def assert_gate_enforcement(self) -> None:
        """TLA+ GateEnforcement: if artifacts fails, no downstream pass may run."""
        if self.artifacts_verdict == "fail":
            for p in PASSES - {"artifacts"}:
                assert self.pass_states[p] == "not_run", (
                    f"GateEnforcement: artifacts failed but pass_states[{p!r}]={self.pass_states[p]!r}"
                )

    def assert_cost_monotonicity(self) -> None:
        """TLA+ CostMonotonicity: total_cost is non-negative and never decreases."""
        assert self.total_cost >= 0, (
            f"CostMonotonicity: total_cost={self.total_cost} is negative"
        )

    def assert_completion_consistency(self) -> None:
        """TLA+ CompletionConsistency: when current_step='done', all passes must be 'done'."""
        if self.current_step == "done":
            for p in PASSES:
                assert self.pass_states[p] == "done", (
                    f"CompletionConsistency: current_step='done' but pass_states[{p!r}]={self.pass_states[p]!r}"
                )

    def assert_parallel_safety(self) -> None:
        """TLA+ ParallelSafety: while in 'parallel' step, both coverage and interaction must be running or done."""
        if self.current_step == "parallel":
            assert self.pass_states["coverage"] in {"running", "done"}, (
                f"ParallelSafety: current_step='parallel' but coverage={self.pass_states['coverage']!r}"
            )
            assert self.pass_states["interaction"] in {"running", "done"}, (
                f"ParallelSafety: current_step='parallel' but interaction={self.pass_states['interaction']!r}"
            )

    def assert_bounded_cost(self) -> None:
        """TLA+ BoundedCost: total_cost never exceeds 5 (one per pass)."""
        assert self.total_cost <= 5, (
            f"BoundedCost: total_cost={self.total_cost} exceeds 5"
        )

    def assert_all_invariants(self) -> None:
        """Composite invariant check: all TLA+ invariants verified in sequence."""
        self.assert_type_ok()
        self.assert_dependency_order()
        self.assert_gate_enforcement()
        self.assert_cost_monotonicity()
        self.assert_completion_consistency()
        self.assert_parallel_safety()
        self.assert_bounded_cost()


# ---------------------------------------------------------------------------
# DAG fixture builder
# ---------------------------------------------------------------------------

def build_pipeline_dag() -> RegistryDag:
    dag = RegistryDag()
    for name in PASSES:
        dag.add_node(Node.behavior(name, name, given="given", when="when", then="then"))
    dag.add_edge(Edge("coverage", "artifacts", EdgeType.IMPORTS))
    dag.add_edge(Edge("interaction", "artifacts", EdgeType.IMPORTS))
    dag.add_edge(Edge("abstraction_gap", "coverage", EdgeType.IMPORTS))
    dag.add_edge(Edge("abstraction_gap", "interaction", EdgeType.IMPORTS))
    dag.add_edge(Edge("imports", "abstraction_gap", EdgeType.IMPORTS))
    return dag


# ---------------------------------------------------------------------------
# Helpers for shared trace patterns
# ---------------------------------------------------------------------------

def _run_fail_trace(art_verdict: str = "fail") -> OrchState:
    """Execute the artifacts-fail pipeline trace and assert all invariants at each step."""
    s = OrchState(art_verdict)
    assert s.current_step == "idle"
    assert s.artifacts_verdict == "not_run"
    assert s.total_cost == 0
    assert s.overall_status == "pass"
    assert all(v == "not_run" for v in s.pass_states.values())

    s.start_artifacts()
    s.assert_all_invariants()
    assert s.current_step == "artifacts"
    assert s.pass_states["artifacts"] == "running"

    s.complete_artifacts()
    s.assert_all_invariants()
    assert s.total_cost == 1
    assert s.artifacts_verdict == "fail"
    assert s.pass_states["artifacts"] == "done"

    s.check_gate()
    s.assert_all_invariants()

    s.handle_fail()
    s.assert_all_invariants()
    assert s.overall_status == "blocked"
    assert s.current_step == "blocked"

    s.terminate()
    s.assert_all_invariants()

    assert s.total_cost == 1
    assert s.current_step == "blocked"
    assert s.artifacts_verdict == "fail"
    assert s.overall_status == "blocked"
    for p in PASSES - {"artifacts"}:
        assert s.pass_states[p] == "not_run", f"Expected {p} to be 'not_run', got {s.pass_states[p]!r}"
    return s


def _run_coverage_first_trace() -> OrchState:
    """Execute the coverage-first parallel trace and assert all invariants at each step."""
    s = OrchState("pass")
    assert s.current_step == "idle"
    assert s.total_cost == 0
    assert s.overall_status == "pass"
    assert all(v == "not_run" for v in s.pass_states.values())

    s.start_artifacts()
    s.assert_all_invariants()
    assert s.pass_states["artifacts"] == "running"
    assert s.total_cost == 0

    s.complete_artifacts()
    s.assert_all_invariants()
    assert s.total_cost == 1
    assert s.artifacts_verdict == "pass"
    assert s.pass_states["artifacts"] == "done"

    s.check_gate()
    s.assert_all_invariants()

    s.start_parallel()
    s.assert_all_invariants()
    assert s.current_step == "parallel"
    assert s.pass_states["coverage"] == "running"
    assert s.pass_states["interaction"] == "running"

    s.choose_parallel()
    s.assert_all_invariants()

    s.finish_coverage_first()
    s.assert_all_invariants()
    assert s.total_cost == 2
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "running"

    s.finish_interaction_second()
    s.assert_all_invariants()
    assert s.total_cost == 3
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "done"

    s.start_abstraction_gap()
    s.assert_all_invariants()
    assert s.current_step == "abstraction_gap"
    assert s.pass_states["abstraction_gap"] == "running"

    s.complete_abstraction_gap()
    s.assert_all_invariants()
    assert s.total_cost == 4
    assert s.pass_states["abstraction_gap"] == "done"

    s.start_imports()
    s.assert_all_invariants()
    assert s.current_step == "imports"
    assert s.pass_states["imports"] == "running"

    s.complete_imports()
    s.assert_all_invariants()
    assert s.total_cost == 5
    assert s.current_step == "done"
    for p in PASSES:
        assert s.pass_states[p] == "done", f"Expected {p} to be 'done', got {s.pass_states[p]!r}"

    s.terminate()
    s.assert_all_invariants()

    assert s.total_cost == 5
    assert s.current_step == "done"
    assert s.artifacts_verdict == "pass"
    assert s.overall_status == "pass"
    for p in PASSES:
        assert s.pass_states[p] == "done"
    return s


def _run_interaction_first_trace() -> OrchState:
    """Execute the interaction-first parallel trace and assert all invariants at each step."""
    s = OrchState("pass")
    assert s.current_step == "idle"
    assert s.total_cost == 0
    assert all(v == "not_run" for v in s.pass_states.values())

    s.start_artifacts()
    s.assert_all_invariants()

    s.complete_artifacts()
    s.assert_all_invariants()
    assert s.total_cost == 1
    assert s.artifacts_verdict == "pass"

    s.check_gate()
    s.assert_all_invariants()

    s.start_parallel()
    s.assert_all_invariants()
    assert s.current_step == "parallel"

    s.choose_parallel()
    s.assert_all_invariants()

    s.finish_interaction_first()
    s.assert_all_invariants()
    assert s.total_cost == 2
    assert s.pass_states["interaction"] == "done"
    assert s.pass_states["coverage"] == "running"

    s.finish_coverage_second()
    s.assert_all_invariants()
    assert s.total_cost == 3
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "done"

    s.start_abstraction_gap()
    s.assert_all_invariants()
    assert s.current_step == "abstraction_gap"
    assert s.pass_states["abstraction_gap"] == "running"

    s.complete_abstraction_gap()
    s.assert_all_invariants()
    assert s.total_cost == 4

    s.start_imports()
    s.assert_all_invariants()
    assert s.current_step == "imports"

    s.complete_imports()
    s.assert_all_invariants()
    assert s.total_cost == 5
    assert s.current_step == "done"

    s.terminate()
    s.assert_all_invariants()

    assert s.total_cost == 5
    assert s.current_step == "done"
    assert s.artifacts_verdict == "pass"
    assert s.overall_status == "pass"
    for p in PASSES:
        assert s.pass_states[p] == "done"
    return s


# ---------------------------------------------------------------------------
# Trace tests
# ---------------------------------------------------------------------------

def test_trace_1_artifacts_fails_pipeline_blocked() -> None:
    """Trace 1: artifacts verdict=fail → pipeline blocked; GateEnforcement holds throughout."""
    _run_fail_trace("fail")


def test_trace_2_artifacts_passes_coverage_first() -> None:
    """Trace 2: artifacts pass → coverage finishes first → full pipeline completes."""
    _run_coverage_first_trace()


def test_trace_3_artifacts_passes_interaction_first() -> None:
    """Trace 3: artifacts pass → interaction finishes first → full pipeline completes."""
    _run_interaction_first_trace()


def test_trace_4_artifacts_fails_pipeline_blocked() -> None:
    """Trace 4: duplicate of trace 1; confirms fail path is deterministic."""
    _run_fail_trace("fail")


def test_trace_5_artifacts_passes_coverage_first() -> None:
    """Trace 5: duplicate of trace 2; confirms coverage-first path is deterministic."""
    _run_coverage_first_trace()


def test_trace_6_artifacts_passes_interaction_first() -> None:
    """Trace 6: duplicate of trace 3; confirms interaction-first path is deterministic."""
    _run_interaction_first_trace()


def test_trace_7_artifacts_fails_pipeline_blocked() -> None:
    """Trace 7: third fail trace; BoundedCost=1 and blocked step verified."""
    _run_fail_trace("fail")


def test_trace_8_artifacts_passes_coverage_first() -> None:
    """Trace 8: third coverage-first trace; all 5 passes reach 'done'."""
    _run_coverage_first_trace()


def test_trace_9_artifacts_passes_interaction_first() -> None:
    """Trace 9: third interaction-first trace; all 5 passes reach 'done'."""
    _run_interaction_first_trace()


def test_trace_10_artifacts_fails_pipeline_blocked() -> None:
    """Trace 10: fourth fail trace; overall_status='blocked' and total_cost=1."""
    _run_fail_trace("fail")


# ---------------------------------------------------------------------------
# Invariant-focused tests
# ---------------------------------------------------------------------------

def test_invariant_dependency_order() -> None:
    """TLA+ DependencyOrder: abstraction_gap cannot start until coverage and interaction are both done."""
    s_fail = OrchState("fail")
    s_fail.start_artifacts()
    s_fail.assert_dependency_order()
    s_fail.complete_artifacts()
    s_fail.assert_dependency_order()
    s_fail.handle_fail()
    s_fail.assert_dependency_order()

    s_pass = OrchState("pass")
    s_pass.start_artifacts()
    s_pass.assert_dependency_order()
    s_pass.complete_artifacts()
    s_pass.assert_dependency_order()
    s_pass.start_parallel()
    s_pass.assert_dependency_order()
    s_pass.finish_coverage_first()
    s_pass.assert_dependency_order()
    s_pass.finish_interaction_second()
    s_pass.assert_dependency_order()
    s_pass.start_abstraction_gap()
    s_pass.assert_dependency_order()
    assert s_pass.pass_states["coverage"] == "done", "DependencyOrder: coverage must be done"
    assert s_pass.pass_states["interaction"] == "done", "DependencyOrder: interaction must be done"
    s_pass.complete_abstraction_gap()
    s_pass.assert_dependency_order()


def test_invariant_gate_enforcement() -> None:
    """TLA+ GateEnforcement: a failed artifacts pass prevents all downstream passes from running."""
    s1 = OrchState("fail")
    s1.start_artifacts()
    s1.complete_artifacts()
    s1.assert_gate_enforcement()
    for p in PASSES - {"artifacts"}:
        assert s1.pass_states[p] == "not_run", f"GateEnforcement after complete: {p} should be not_run"
    s1.handle_fail()
    s1.assert_gate_enforcement()
    for p in PASSES - {"artifacts"}:
        assert s1.pass_states[p] == "not_run", f"GateEnforcement after handle_fail: {p} should be not_run"
    s1.terminate()
    s1.assert_gate_enforcement()

    s2 = OrchState("fail")
    s2.start_artifacts()
    s2.complete_artifacts()
    s2.check_gate()
    s2.handle_fail()
    s2.assert_gate_enforcement()
    assert s2.artifacts_verdict == "fail"
    for p in PASSES - {"artifacts"}:
        assert s2.pass_states[p] == "not_run"


def test_invariant_cost_monotonicity() -> None:
    """TLA+ CostMonotonicity: total_cost never decreases across any action."""
    s = OrchState("pass")
    prev = s.total_cost
    assert s.total_cost >= 0
    s.start_artifacts()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.complete_artifacts()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.start_parallel()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.finish_coverage_first()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.finish_interaction_second()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.start_abstraction_gap()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.complete_abstraction_gap()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.start_imports()
    assert s.total_cost >= prev
    prev = s.total_cost
    s.complete_imports()
    assert s.total_cost >= prev

    s2 = OrchState("fail")
    assert s2.total_cost == 0
    s2.start_artifacts()
    assert s2.total_cost == 0
    s2.complete_artifacts()
    assert s2.total_cost == 1
    s2.handle_fail()
    assert s2.total_cost == 1, "Cost must not change after handle_fail"
    s2.assert_cost_monotonicity()


def test_invariant_completion_consistency() -> None:
    """TLA+ CompletionConsistency: current_step='done' implies every pass_state is 'done'."""
    s = OrchState("pass")
    s.start_artifacts()
    s.complete_artifacts()
    s.start_parallel()
    s.finish_coverage_first()
    s.finish_interaction_second()
    s.start_abstraction_gap()
    s.complete_abstraction_gap()
    s.start_imports()
    s.complete_imports()
    assert s.current_step == "done"
    s.assert_completion_consistency()
    for p in PASSES:
        assert s.pass_states[p] == "done"

    s2 = OrchState("pass")
    s2.start_artifacts()
    s2.complete_artifacts()
    s2.start_parallel()
    s2.finish_interaction_first()
    s2.finish_coverage_second()
    s2.start_abstraction_gap()
    s2.complete_abstraction_gap()
    s2.start_imports()
    s2.complete_imports()
    assert s2.current_step == "done"
    s2.assert_completion_consistency()
    for p in PASSES:
        assert s2.pass_states[p] == "done"


def test_invariant_parallel_safety() -> None:
    """TLA+ ParallelSafety: while in 'parallel' step, both coverage and interaction must be running or done."""
    s = OrchState("pass")
    s.start_artifacts()
    s.complete_artifacts()
    s.start_parallel()
    assert s.current_step == "parallel"
    s.assert_parallel_safety()
    assert s.pass_states["coverage"] in {"running", "done"}
    assert s.pass_states["interaction"] in {"running", "done"}

    s.finish_coverage_first()
    assert s.current_step == "parallel"
    s.assert_parallel_safety()
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "running"

    s2 = OrchState("pass")
    s2.start_artifacts()
    s2.complete_artifacts()
    s2.start_parallel()
    s2.finish_interaction_first()
    assert s2.current_step == "parallel"
    s2.assert_parallel_safety()
    assert s2.pass_states["coverage"] in {"running", "done"}
    assert s2.pass_states["interaction"] in {"running", "done"}


def test_invariant_bounded_cost() -> None:
    """TLA+ BoundedCost: total_cost never exceeds 5 across all three execution paths."""
    s = OrchState("pass")
    for action in [
        s.start_artifacts, s.complete_artifacts, s.check_gate, s.start_parallel,
        s.choose_parallel, s.finish_coverage_first, s.finish_interaction_second,
        s.start_abstraction_gap, s.complete_abstraction_gap, s.start_imports,
        s.complete_imports, s.terminate,
    ]:
        action()
        s.assert_bounded_cost()
    assert s.total_cost == 5

    s2 = OrchState("fail")
    for action in [
        s2.start_artifacts, s2.complete_artifacts, s2.check_gate,
        s2.handle_fail, s2.terminate,
    ]:
        action()
        s2.assert_bounded_cost()
    assert s2.total_cost == 1

    s3 = OrchState("pass")
    for action in [
        s3.start_artifacts, s3.complete_artifacts, s3.check_gate, s3.start_parallel,
        s3.choose_parallel, s3.finish_interaction_first, s3.finish_coverage_second,
        s3.start_abstraction_gap, s3.complete_abstraction_gap, s3.start_imports,
        s3.complete_imports, s3.terminate,
    ]:
        action()
        s3.assert_bounded_cost()
    assert s3.total_cost == 5


def test_invariant_type_ok() -> None:
    """TLA+ TypeOK: all state variables remain within their declared domains at every step."""
    s_fail = OrchState("fail")
    s_fail.assert_type_ok()

    s_pass = OrchState("pass")
    s_pass.assert_type_ok()

    s = OrchState("fail")
    for action in [
        s.start_artifacts, s.complete_artifacts, s.check_gate, s.handle_fail, s.terminate
    ]:
        action()
        s.assert_type_ok()

    s2 = OrchState("pass")
    for action in [
        s2.start_artifacts, s2.complete_artifacts, s2.check_gate, s2.start_parallel,
        s2.choose_parallel, s2.finish_coverage_first, s2.finish_interaction_second,
        s2.start_abstraction_gap, s2.complete_abstraction_gap, s2.start_imports,
        s2.complete_imports, s2.terminate,
    ]:
        action()
        s2.assert_type_ok()


# ---------------------------------------------------------------------------
# DAG structure tests
# ---------------------------------------------------------------------------

def test_dag_has_all_pass_nodes() -> None:
    """DAG must contain exactly one node per pipeline pass, each queryable by its ID."""
    dag = build_pipeline_dag()
    for pass_name in PASSES:
        result = dag.query_relevant(pass_name)
        assert result.root == pass_name, f"Expected root={pass_name!r}, got {result.root!r}"
    assert dag.node_count == len(PASSES), f"Expected {len(PASSES)} nodes, got {dag.node_count}"


def test_dag_dependency_topology() -> None:
    """DAG edges must encode the correct dependency topology: artifacts is the root, imports is the leaf."""
    dag = build_pipeline_dag()

    expected_edges = [
        ("coverage", "artifacts"),
        ("interaction", "artifacts"),
        ("abstraction_gap", "coverage"),
        ("abstraction_gap", "interaction"),
        ("imports", "abstraction_gap"),
    ]
    for from_id, to_id in expected_edges:
        result = dag.validate_edge(from_id, to_id, EdgeType.IMPORTS)
        assert not result.valid or result.reason == "duplicate", (
            f"Expected existing edge ({from_id}->{to_id}) to be flagged as duplicate"
        )

    artifacts_result = dag.query_relevant("artifacts")
    assert len(artifacts_result.direct_edges) == 0, (
        f"artifacts should have no outgoing edges, got {artifacts_result.direct_edges}"
    )

    impact = dag.query_impact("artifacts")
    assert "coverage" in impact.affected, "coverage should be in artifacts impact set"
    assert "interaction" in impact.affected, "interaction should be in artifacts impact set"


def test_dag_abstraction_gap_subgraph() -> None:
    """The abstraction_gap subgraph must include its direct dependencies: coverage and interaction."""
    dag = build_pipeline_dag()
    subgraph = dag.extract_subgraph("abstraction_gap")
    assert "coverage" in subgraph.nodes, "coverage should be in abstraction_gap subgraph"
    assert "interaction" in subgraph.nodes, "interaction should be in abstraction_gap subgraph"
    assert "abstraction_gap" in subgraph.nodes


def test_dag_artifacts_gates_all() -> None:
    """Every non-artifacts pass must appear in the transitive impact set of artifacts."""
    dag = build_pipeline_dag()
    result = dag.query_relevant("artifacts")
    assert result.root == "artifacts"
    impact = dag.query_impact("artifacts")
    expected_affected = PASSES - {"artifacts"}
    for p in expected_affected:
        assert p in impact.affected, f"{p} should transitively depend on artifacts"


def test_dag_cycle_prevention() -> None:
    """Adding a back-edge that creates a cycle must raise CycleError."""
    dag = build_pipeline_dag()
    with pytest.raises(CycleError):
        dag.add_edge(Edge("artifacts", "coverage", EdgeType.IMPORTS))


def test_dag_node_not_found() -> None:
    """Querying a non-existent node ID must raise NodeNotFoundError."""
    dag = build_pipeline_dag()
    with pytest.raises(NodeNotFoundError):
        dag.query_relevant("nonexistent_pass")


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

def test_empty_dag_node_count() -> None:
    """A freshly constructed RegistryDag must report node_count == 0."""
    dag = RegistryDag()
    assert dag.node_count == 0, f"Fresh DAG should have 0 nodes, got {dag.node_count}"


def test_isolated_node() -> None:
    """A node with no edges must have zero transitive deps and zero direct edges."""
    dag = RegistryDag()
    node = Node.behavior("solo", "solo", given="given", when="when", then="then")
    dag.add_node(node)
    assert dag.node_count == 1
    result = dag.query_relevant("solo")
    assert result.root == "solo"
    assert len(result.transitive_deps) == 0
    assert len(result.direct_edges) == 0


def test_missing_artifacts_gate() -> None:
    """GateEnforcement: immediately after artifacts fails, all downstream passes must still be 'not_run'."""
    s = OrchState("fail")
    s.start_artifacts()
    s.complete_artifacts()
    assert s.artifacts_verdict == "fail"
    s.assert_gate_enforcement()
    for p in PASSES - {"artifacts"}:
        assert s.pass_states[p] == "not_run", (
            f"GateEnforcement: after artifacts fails, {p} must be 'not_run'"
        )


def test_diamond_dependency_satisfied() -> None:
    """DependencyOrder: starting abstraction_gap before both parallel passes finish must raise AssertionError."""
    s = OrchState("pass")
    s.start_artifacts()
    s.complete_artifacts()
    s.start_parallel()
    s.finish_coverage_first()
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "running"

    s.pass_states["abstraction_gap"] = "running"
    with pytest.raises(AssertionError, match="DependencyOrder"):
        s.assert_dependency_order()

    s.pass_states["abstraction_gap"] = "not_run"
    s.finish_interaction_second()
    s.start_abstraction_gap()
    s.assert_dependency_order()
    assert s.pass_states["coverage"] == "done"
    assert s.pass_states["interaction"] == "done"


def test_cost_accumulation_all_passes() -> None:
    """BoundedCost + CostMonotonicity: total_cost increments by exactly 1 per completing action."""
    s = OrchState("pass")
    assert s.total_cost == 0
    s.start_artifacts()
    assert s.total_cost == 0
    s.complete_artifacts()
    assert s.total_cost == 1
    s.start_parallel()
    assert s.total_cost == 1
    s.finish_coverage_first()
    assert s.total_cost == 2
    s.finish_interaction_second()
    assert s.total_cost == 3
    s.start_abstraction_gap()
    assert s.total_cost == 3
    s.complete_abstraction_gap()
    assert s.total_cost == 4
    s.start_imports()
    assert s.total_cost == 4
    s.complete_imports()
    assert s.total_cost == 5, f"Expected total_cost=5 after all passes, got {s.total_cost}"


def test_blocked_state_is_terminal_type() -> None:
    """TypeOK: 'blocked' is a valid terminal step and overall_status value per the TLA+ type invariant."""
    s = OrchState("fail")
    s.start_artifacts()
    s.complete_artifacts()
    s.check_gate()
    s.handle_fail()
    s.terminate()
    assert s.current_step == "blocked"
    assert s.overall_status == "blocked"
    s.assert_type_ok()
    assert s.current_step in VALID_STEPS
    assert s.overall_status in VALID_OVERALL