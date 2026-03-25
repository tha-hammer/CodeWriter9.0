import sys
import os
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node
from registry.cli import _aggregate_verdicts, _parse_verdict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_PASSES = 3
VALID_STATUSES = {"pass", "fail", "warning"}


# ---------------------------------------------------------------------------
# Adapter functions: map DAG-with-test_artifacts to aggregation calls
# ---------------------------------------------------------------------------

def _orchestrate_reviews(dag: RegistryDag) -> str:
    """Extract verdicts from dag.test_artifacts and aggregate to overall status."""
    results = {
        name: {"verdict": verdict}
        for name, verdict in getattr(dag, "test_artifacts", {}).items()
    }
    status, _ = _aggregate_verdicts(results)
    return status


def cmd_plan_review(dag: RegistryDag) -> int:
    """Extract verdicts from dag.test_artifacts and return exit code."""
    results = {
        name: {"verdict": verdict}
        for name, verdict in getattr(dag, "test_artifacts", {}).items()
    }
    _, exit_code = _aggregate_verdicts(results)
    return exit_code

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_review_dag(verdicts: list[str]) -> RegistryDag:
    dag = RegistryDag()
    artifacts: dict[str, str] = {}
    for i, verdict in enumerate(verdicts):
        nid = f"review_pass_{i}"
        dag.add_node(Node.behavior(nid, f"Review Pass {i}", "given", "when", "then"))
        artifacts[nid] = verdict
    dag.test_artifacts = artifacts
    return dag


def _make_diamond_dag(
    root_v: str,
    branch_a_v: str,
    branch_b_v: str,
    merge_v: str,
) -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior("root",     "Root Review",     "given", "when", "then"))
    dag.add_node(Node.behavior("branch_a", "Branch A Review", "given", "when", "then"))
    dag.add_node(Node.behavior("branch_b", "Branch B Review", "given", "when", "then"))
    dag.add_node(Node.behavior("merge",    "Merge Review",    "given", "when", "then"))
    dag.add_edge(Edge("root",     "branch_a", EdgeType.IMPORTS))
    dag.add_edge(Edge("root",     "branch_b", EdgeType.IMPORTS))
    dag.add_edge(Edge("branch_a", "merge",    EdgeType.IMPORTS))
    dag.add_edge(Edge("branch_b", "merge",    EdgeType.IMPORTS))
    dag.test_artifacts = {
        "root":     root_v,
        "branch_a": branch_a_v,
        "branch_b": branch_b_v,
        "merge":    merge_v,
    }
    return dag


def _make_fan_dag(root_v: str, left_v: str, right_v: str) -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior("root",  "Root",  "g", "w", "t"))
    dag.add_node(Node.behavior("left",  "Left",  "g", "w", "t"))
    dag.add_node(Node.behavior("right", "Right", "g", "w", "t"))
    dag.add_edge(Edge("root", "left",  EdgeType.IMPORTS))
    dag.add_edge(Edge("root", "right", EdgeType.IMPORTS))
    dag.test_artifacts = {
        "root":  root_v,
        "left":  left_v,
        "right": right_v,
    }
    return dag


def _make_isolated_dag(node_id: str, label: str, verdict: str) -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior(node_id, label, "g", "w", "t"))
    dag.test_artifacts = {node_id: verdict}
    return dag

# ---------------------------------------------------------------------------
# Invariant assertion helpers
# ---------------------------------------------------------------------------

def _assert_fail_dominates(verdicts: list[str], status: str, phase: str) -> None:
    if phase == "done" and any(v == "fail" for v in verdicts):
        assert status == "fail", (
            f"FailDominates violated: verdicts={verdicts!r}, status={status!r}"
        )

def _assert_warning_second(verdicts: list[str], status: str, phase: str) -> None:
    if (
        phase == "done"
        and not any(v == "fail" for v in verdicts)
        and any(v == "warning" for v in verdicts)
    ):
        assert status == "warning", (
            f"WarningSecond violated: verdicts={verdicts!r}, status={status!r}"
        )

def _assert_exit_code_mapping(status: str, exit_code: int, phase: str) -> None:
    if phase == "done":
        if status in ("pass", "warning"):
            assert exit_code == 0, (
                f"ExitCodeMapping violated: status={status!r} expected exit_code=0, got {exit_code}"
            )
        elif status == "fail":
            assert exit_code == 1, (
                f"ExitCodeMapping violated: status={status!r} expected exit_code=1, got {exit_code}"
            )

def _assert_status_is_valid(status: str, phase: str) -> None:
    if phase == "done":
        assert status in VALID_STATUSES, (
            f"StatusIsValid violated: status={status!r} not in {VALID_STATUSES}"
        )

def _assert_verdict_length_bound(verdicts: list[str]) -> None:
    assert len(verdicts) <= NUM_PASSES, (
        f"VerdictLengthBound violated: len(verdicts)={len(verdicts)} > {NUM_PASSES}"
    )

def _assert_all_invariants(
    verdicts: list[str],
    status: str,
    exit_code: int,
    phase: str = "done",
) -> None:
    _assert_fail_dominates(verdicts, status, phase)
    _assert_warning_second(verdicts, status, phase)
    _assert_exit_code_mapping(status, exit_code, phase)
    _assert_status_is_valid(status, phase)
    _assert_verdict_length_bound(verdicts)

# ---------------------------------------------------------------------------
# Trace 1 – ["pass", "pass", "fail"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace1_PassPassFail:
    """Trace 1: verdicts=['pass','pass','fail'] → status='fail', exit_code=1.
    A single 'fail' at the end dominates two 'pass' verdicts.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["pass", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["pass", "pass", "fail"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["pass", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 2 – ["unknown", "unknown", "fail"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace2_UnknownUnknownFail:
    """Trace 2: verdicts=['unknown','unknown','fail'] → status='fail', exit_code=1.
    'fail' dominates two 'unknown' verdicts.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["unknown", "unknown", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["unknown", "unknown", "fail"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["unknown", "unknown", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 3 – ["unknown", "unknown", "warning"] → status="warning", exit_code=0
# ---------------------------------------------------------------------------

class TestTrace3_UnknownUnknownWarning:
    """Trace 3: verdicts=['unknown','unknown','warning'] → status='warning', exit_code=0.
    No 'fail' present; single 'warning' elevates status.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["unknown", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "warning", f"Expected 'warning', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["unknown", "unknown", "warning"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 0, f"Expected exit_code=0, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["unknown", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 4 – ["warning", "warning", "fail"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace4_WarningWarningFail:
    """Trace 4: verdicts=['warning','warning','fail'] → status='fail', exit_code=1.
    'fail' dominates two 'warning' verdicts (FailDominates > WarningSecond).
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["warning", "warning", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["warning", "warning", "fail"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["warning", "warning", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 5 – ["pass", "warning", "warning"] → status="warning", exit_code=0
# ---------------------------------------------------------------------------

class TestTrace5_PassWarningWarning:
    """Trace 5: verdicts=['pass','warning','warning'] → status='warning', exit_code=0.
    Two 'warning' verdicts with one 'pass'; no 'fail' → WarningSecond applies.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["pass", "warning", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "warning", f"Expected 'warning', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["pass", "warning", "warning"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 0, f"Expected exit_code=0, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["pass", "warning", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 6 – ["fail", "pass", "fail"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace6_FailPassFail:
    """Trace 6: verdicts=['fail','pass','fail'] → status='fail', exit_code=1.
    Multiple 'fail' verdicts interspersed with 'pass' still produce 'fail'.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["fail", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["fail", "pass", "fail"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["fail", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 7 – ["warning", "unknown", "warning"] → status="warning", exit_code=0
# ---------------------------------------------------------------------------

class TestTrace7_WarningUnknownWarning:
    """Trace 7: verdicts=['warning','unknown','warning'] → status='warning', exit_code=0.
    Two 'warning' verdicts with 'unknown' in between; no 'fail' → WarningSecond.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["warning", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "warning", f"Expected 'warning', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["warning", "unknown", "warning"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 0, f"Expected exit_code=0, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["warning", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 8 – ["pass", "fail", "pass"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace8_PassFailPass:
    """Trace 8: verdicts=['pass','fail','pass'] → status='fail', exit_code=1.
    Single 'fail' in the middle of two 'pass' verdicts still dominates.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["pass", "fail", "pass"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["pass", "fail", "pass"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["pass", "fail", "pass"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 9 – ["warning", "warning", "unknown"] → status="warning", exit_code=0
# ---------------------------------------------------------------------------

class TestTrace9_WarningWarningUnknown:
    """Trace 9: verdicts=['warning','warning','unknown'] → status='warning', exit_code=0.
    Trailing 'unknown' does not suppress the two 'warning' verdicts.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["warning", "warning", "unknown"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "warning", f"Expected 'warning', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["warning", "warning", "unknown"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 0, f"Expected exit_code=0, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["warning", "warning", "unknown"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Trace 10 – ["fail", "fail", "warning"] → status="fail", exit_code=1
# ---------------------------------------------------------------------------

class TestTrace10_FailFailWarning:
    """Trace 10: verdicts=['fail','fail','warning'] → status='fail', exit_code=1.
    'fail' dominates 'warning' even when multiple 'fail' verdicts are present.
    """

    def test_orchestrate_reviews_status(self):
        verdicts = ["fail", "fail", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        assert status == "fail", f"Expected 'fail', got {status!r}"

    def test_cmd_plan_review_exit_code(self):
        verdicts = ["fail", "fail", "warning"]
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert exit_code == 1, f"Expected exit_code=1, got {exit_code}"

    def test_all_invariants(self):
        verdicts = ["fail", "fail", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_all_invariants(verdicts, status, exit_code)

# ---------------------------------------------------------------------------
# Dedicated invariant verifier: FailDominates
# ---------------------------------------------------------------------------

class TestInvariant_FailDominates:
    """FailDominates: when phase='done' and any verdict is 'fail', status must be 'fail'.
    Exercised across four distinct trace-derived topologies.
    """

    def test_fail_dominates_trailing_fail_among_passes(self):
        verdicts = ["pass", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_fail_dominates(verdicts, status, "done")
        assert status == "fail", f"Trace 1: expected 'fail', got {status!r}"

    def test_fail_dominates_over_multiple_warnings(self):
        verdicts = ["warning", "warning", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_fail_dominates(verdicts, status, "done")
        assert status == "fail", f"Trace 4: expected 'fail', got {status!r}"

    def test_fail_dominates_over_unknowns(self):
        verdicts = ["unknown", "unknown", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_fail_dominates(verdicts, status, "done")
        assert status == "fail", f"Trace 2: expected 'fail', got {status!r}"

    def test_fail_dominates_multiple_fails_with_warning(self):
        verdicts = ["fail", "fail", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_fail_dominates(verdicts, status, "done")
        assert status == "fail", f"Trace 10: expected 'fail', got {status!r}"

# ---------------------------------------------------------------------------
# Dedicated invariant verifier: WarningSecond
# ---------------------------------------------------------------------------

class TestInvariant_WarningSecond:
    """WarningSecond: when done and no 'fail' but any 'warning', status must be 'warning'.
    Exercised across four distinct trace-derived topologies.
    """

    def test_warning_second_trailing_warning_among_unknowns(self):
        verdicts = ["unknown", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_warning_second(verdicts, status, "done")
        assert status == "warning", f"Trace 3: expected 'warning', got {status!r}"

    def test_warning_second_warnings_with_pass(self):
        verdicts = ["pass", "warning", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_warning_second(verdicts, status, "done")
        assert status == "warning", f"Trace 5: expected 'warning', got {status!r}"

    def test_warning_second_warnings_flanking_unknown(self):
        verdicts = ["warning", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_warning_second(verdicts, status, "done")
        assert status == "warning", f"Trace 7: expected 'warning', got {status!r}"

    def test_warning_second_warnings_with_trailing_unknown(self):
        verdicts = ["warning", "warning", "unknown"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_warning_second(verdicts, status, "done")
        assert status == "warning", f"Trace 9: expected 'warning', got {status!r}"

# ---------------------------------------------------------------------------
# Dedicated invariant verifier: ExitCodeMapping
# ---------------------------------------------------------------------------

class TestInvariant_ExitCodeMapping:
    """ExitCodeMapping: pass/warning→exit_code=0; fail→exit_code=1.
    Exercised across four distinct topologies.
    """

    def test_exit_code_0_for_warning_status(self):
        verdicts = ["unknown", "unknown", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_exit_code_mapping(status, exit_code, "done")
        assert exit_code == 0, f"Trace 3: expected exit_code=0, got {exit_code}"

    def test_exit_code_1_for_fail_status(self):
        verdicts = ["pass", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_exit_code_mapping(status, exit_code, "done")
        assert exit_code == 1, f"Trace 1: expected exit_code=1, got {exit_code}"

    def test_exit_code_0_for_all_pass(self):
        verdicts = ["pass", "pass", "pass"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "pass", f"All-pass: expected status='pass', got {status!r}"
        _assert_exit_code_mapping(status, exit_code, "done")
        assert exit_code == 0, f"All-pass: expected exit_code=0, got {exit_code}"

    def test_exit_code_1_when_fail_dominates_warning(self):
        verdicts = ["warning", "warning", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        _assert_exit_code_mapping(status, exit_code, "done")
        assert exit_code == 1, f"Trace 4: expected exit_code=1, got {exit_code}"

# ---------------------------------------------------------------------------
# Dedicated invariant verifier: StatusIsValid
# ---------------------------------------------------------------------------

class TestInvariant_StatusIsValid:
    """StatusIsValid: when done, status must be in {pass, fail, warning}.
    Exercised across four topologies including an all-unknown edge case.
    """

    def test_status_valid_fail_dominant(self):
        verdicts = ["pass", "pass", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_status_is_valid(status, "done")

    def test_status_valid_warning_second(self):
        verdicts = ["pass", "warning", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_status_is_valid(status, "done")

    def test_status_valid_all_unknown_defaults_to_pass(self):
        verdicts = ["unknown", "unknown", "unknown"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_status_is_valid(status, "done")
        assert status == "pass", (
            f"All-unknown: expected fallthrough to 'pass', got {status!r}"
        )

    def test_status_valid_multiple_fails_with_warning(self):
        verdicts = ["fail", "fail", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        _assert_status_is_valid(status, "done")

# ---------------------------------------------------------------------------
# Dedicated invariant verifier: VerdictLengthBound
# ---------------------------------------------------------------------------

class TestInvariant_VerdictLengthBound:
    """VerdictLengthBound: len(verdicts) <= NUM_PASSES (3).
    Verified for all 10 traces and sub-full counts.
    """

    def test_single_verdict_within_bound(self):
        verdicts = ["fail"]
        _assert_verdict_length_bound(verdicts)
        dag = _make_review_dag(verdicts)
        assert len(dag.test_artifacts) <= NUM_PASSES

    def test_two_verdicts_within_bound(self):
        verdicts = ["warning", "pass"]
        _assert_verdict_length_bound(verdicts)
        dag = _make_review_dag(verdicts)
        assert len(dag.test_artifacts) <= NUM_PASSES

    def test_three_verdicts_at_exact_bound(self):
        verdicts = ["pass", "warning", "fail"]
        _assert_verdict_length_bound(verdicts)
        dag = _make_review_dag(verdicts)
        assert len(dag.test_artifacts) <= NUM_PASSES

    def test_all_traces_satisfy_bound(self):
        all_trace_verdicts = [
            ["pass", "pass", "fail"],
            ["unknown", "unknown", "fail"],
            ["unknown", "unknown", "warning"],
            ["warning", "warning", "fail"],
            ["pass", "warning", "warning"],
            ["fail", "pass", "fail"],
            ["warning", "unknown", "warning"],
            ["pass", "fail", "pass"],
            ["warning", "warning", "unknown"],
            ["fail", "fail", "warning"],
        ]
        for verdicts in all_trace_verdicts:
            _assert_verdict_length_bound(verdicts)
            dag = _make_review_dag(verdicts)
            assert len(dag.test_artifacts) <= NUM_PASSES, (
                f"dag.test_artifacts exceeds bound for verdicts={verdicts!r}"
            )

# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty DAGs, all-homogeneous verdict sets,
    diamond topologies, isolated nodes, and sub-bound verdict counts.
    """

    def test_empty_dag_no_verdicts_defaults_to_pass(self):
        dag_s = RegistryDag()
        dag_s.test_artifacts = {}
        dag_e = RegistryDag()
        dag_e.test_artifacts = {}
        status = _orchestrate_reviews(dag_s)
        exit_code = cmd_plan_review(dag_e)
        assert status == "pass", f"Empty dag: expected 'pass', got {status!r}"
        assert exit_code == 0,   f"Empty dag: expected exit_code=0, got {exit_code}"

    def test_all_pass_verdicts(self):
        verdicts = ["pass", "pass", "pass"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "pass", f"All-pass: expected 'pass', got {status!r}"
        assert exit_code == 0,   f"All-pass: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_all_fail_verdicts(self):
        verdicts = ["fail", "fail", "fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "fail", f"All-fail: expected 'fail', got {status!r}"
        assert exit_code == 1,   f"All-fail: expected exit_code=1, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_all_warning_verdicts(self):
        verdicts = ["warning", "warning", "warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "warning", f"All-warning: expected 'warning', got {status!r}"
        assert exit_code == 0,      f"All-warning: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_all_unknown_verdicts_defaults_to_pass(self):
        verdicts = ["unknown", "unknown", "unknown"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "pass", f"All-unknown: expected 'pass', got {status!r}"
        assert exit_code == 0,   f"All-unknown: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_single_fail_verdict(self):
        verdicts = ["fail"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "fail", f"Single fail: expected 'fail', got {status!r}"
        assert exit_code == 1,   f"Single fail: expected exit_code=1, got {exit_code}"
        _assert_verdict_length_bound(verdicts)
        _assert_all_invariants(verdicts, status, exit_code)

    def test_single_warning_verdict(self):
        verdicts = ["warning"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "warning", f"Single warning: expected 'warning', got {status!r}"
        assert exit_code == 0,      f"Single warning: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_single_pass_verdict(self):
        verdicts = ["pass"]
        status = _orchestrate_reviews(_make_review_dag(verdicts))
        exit_code = cmd_plan_review(_make_review_dag(verdicts))
        assert status == "pass", f"Single pass: expected 'pass', got {status!r}"
        assert exit_code == 0,   f"Single pass: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(verdicts, status, exit_code)

    def test_diamond_pattern_fail_dominates(self):
        all_verdicts = ["pass", "fail", "warning", "pass"]
        assert "fail" in all_verdicts
        status = _orchestrate_reviews(
            _make_diamond_dag("pass", "fail", "warning", "pass")
        )
        exit_code = cmd_plan_review(
            _make_diamond_dag("pass", "fail", "warning", "pass")
        )
        assert status == "fail", f"Diamond-fail: expected 'fail', got {status!r}"
        assert exit_code == 1,   f"Diamond-fail: expected exit_code=1, got {exit_code}"
        _assert_fail_dominates(all_verdicts, status, "done")
        _assert_exit_code_mapping(status, exit_code, "done")
        _assert_status_is_valid(status, "done")

    def test_diamond_pattern_warning_dominates_pass(self):
        all_verdicts = ["pass", "warning", "pass"]
        assert "warning" in all_verdicts
        assert "fail" not in all_verdicts
        status = _orchestrate_reviews(_make_fan_dag("pass", "warning", "pass"))
        exit_code = cmd_plan_review(_make_fan_dag("pass", "warning", "pass"))
        assert status == "warning", f"Fan-warning: expected 'warning', got {status!r}"
        assert exit_code == 0,      f"Fan-warning: expected exit_code=0, got {exit_code}"
        _assert_warning_second(all_verdicts, status, "done")
        _assert_exit_code_mapping(status, exit_code, "done")
        _assert_status_is_valid(status, "done")

    def test_isolated_node_single_fail_review(self):
        status = _orchestrate_reviews(_make_isolated_dag("solo", "Solo Review", "fail"))
        exit_code = cmd_plan_review(_make_isolated_dag("solo", "Solo Review", "fail"))
        assert status == "fail", f"Isolated-fail: expected 'fail', got {status!r}"
        assert exit_code == 1,   f"Isolated-fail: expected exit_code=1, got {exit_code}"
        _assert_all_invariants(["fail"], status, exit_code)

    def test_isolated_node_single_warning_review(self):
        status = _orchestrate_reviews(
            _make_isolated_dag("solo_warn", "Solo Warning Review", "warning")
        )
        exit_code = cmd_plan_review(
            _make_isolated_dag("solo_warn", "Solo Warning Review", "warning")
        )
        assert status == "warning", f"Isolated-warning: expected 'warning', got {status!r}"
        assert exit_code == 0,      f"Isolated-warning: expected exit_code=0, got {exit_code}"
        _assert_all_invariants(["warning"], status, exit_code)