"""
pytest test suite for the ArtifactsGate (gwt-0078) TLA+ model.

All 10 TLC-verified simulation traces are translated into concrete tests.
The ArtifactsGate PlusCal algorithm is re-implemented in Python
(simulate_artifacts_gate) as a faithful step-for-step translation.
RegistryDag / Node / Edge / EdgeType are the ONLY API imports used.

GWT (gwt-0078):
  Given: the artifacts review pass returns verdict 'fail'
  When:  _orchestrate_reviews() checks the artifacts gate
  Then:  no further passes execute; the function returns
         status='blocked' with blocked_by='artifacts' and
         only the artifacts result in results

NOTE – SUT GAP: these tests verify the TLA+ *model* via simulate_artifacts_gate,
which is a faithful Python translation of the PlusCal spec.  They do NOT call
_orchestrate_reviews() directly.  A separate integration test layer is required
to bind this model to the production implementation.

Invariants verified (all 7, at every final state):
  GateBlocking, GatePassthrough, BlockedStatus, CostAccuracy,
  OnlyArtifactsWhenBlocked, NoExtraPassesWhenBlocked, TypeOK
"""
from __future__ import annotations

import json
import pytest
from registry.types import Edge, EdgeType, Node
from registry.dag import RegistryDag

# ---------------------------------------------------------------------------
# Module-level constants (match TLA+ spec values verbatim)
# ---------------------------------------------------------------------------

ARTIFACTS_COST: int = 10
PARALLEL_COST: int = 10          # 5 (coverage) + 5 (security)
TOTAL_COST_ALL: int = ARTIFACTS_COST + PARALLEL_COST

VALID_VERDICTS: frozenset[str] = frozenset({"pass", "fail", "warning", "unknown"})
VALID_STATUSES: frozenset[str] = frozenset({"none", "blocked", "pass", "fail", "warning"})
ALL_PASSES: frozenset[str] = frozenset({"artifacts", "coverage", "security"})


# ---------------------------------------------------------------------------
# Python translation of the ArtifactsGate TLA+ PlusCal algorithm
# ---------------------------------------------------------------------------

def simulate_artifacts_gate(artifacts_verdict: str) -> tuple[dict, set[str], bool]:
    """Faithful step-for-step translation of the ArtifactsGate PlusCal algorithm."""
    passes_started: set[str] = {"artifacts"}
    gate_checked: bool = True

    if artifacts_verdict == "fail":
        final_result: dict = {
            "status": "blocked",
            "blocked_by": "artifacts",
            "results": {
                "artifacts": {
                    "name":     "artifacts",
                    "verdict":  artifacts_verdict,
                    "cost_usd": ARTIFACTS_COST,
                }
            },
            "total_cost": ARTIFACTS_COST,
        }
        return final_result, passes_started, gate_checked

    passes_started = passes_started | {"coverage", "security"}
    status = "warning" if artifacts_verdict == "warning" else "pass"

    final_result = {
        "status":     status,
        "blocked_by": "none",
        "results": {
            "artifacts": {
                "name":     "artifacts",
                "verdict":  artifacts_verdict,
                "cost_usd": ARTIFACTS_COST,
            },
            "coverage": {
                "name":     "coverage",
                "verdict":  "pass",
                "cost_usd": 5,
            },
            "security": {
                "name":     "security",
                "verdict":  "pass",
                "cost_usd": 5,
            },
        },
        "total_cost": TOTAL_COST_ALL,
    }

    return final_result, passes_started, gate_checked


# ---------------------------------------------------------------------------
# DAG fixture builder
# ---------------------------------------------------------------------------

def _build_dag(*, artifacts_verdict: str) -> RegistryDag:
    dag = RegistryDag()

    dag.add_node(Node.resource("plan", "Review Plan"))
    dag.add_node(Node.resource("pass_artifacts", "Artifacts Review Pass"))
    dag.add_node(Node.resource("pass_coverage", "Coverage Review Pass"))
    dag.add_node(Node.resource("pass_security", "Security Review Pass"))

    dag.add_edge(Edge("plan", "pass_artifacts", EdgeType.IMPORTS))
    dag.add_edge(Edge("plan", "pass_coverage",  EdgeType.IMPORTS))
    dag.add_edge(Edge("plan", "pass_security",  EdgeType.IMPORTS))

    # Store test metadata as a plain dict attribute
    dag.__dict__["test_artifacts"] = {"artifacts_verdict": artifacts_verdict}
    return dag


def _run_from_dag(dag: RegistryDag) -> tuple[dict, set[str], bool]:
    return simulate_artifacts_gate(dag.__dict__["test_artifacts"]["artifacts_verdict"])


# ---------------------------------------------------------------------------
# AllInvariants assertion helper
# ---------------------------------------------------------------------------

def assert_all_invariants(
    final_result: dict,
    passes_started: set[str],
    gate_checked: bool,
    artifacts_verdict: str,
) -> None:
    status     = final_result["status"]
    results    = final_result["results"]
    total_cost = final_result["total_cost"]

    # TypeOK
    assert isinstance(gate_checked, bool), (
        f"TypeOK: gate_checked must be bool, got {type(gate_checked)}"
    )
    assert passes_started.issubset(ALL_PASSES), (
        f"TypeOK: passes_started={passes_started!r} contains unknown passes"
    )
    assert artifacts_verdict in VALID_VERDICTS, (
        f"TypeOK: artifacts_verdict={artifacts_verdict!r} not in {VALID_VERDICTS}"
    )
    assert status in VALID_STATUSES, (
        f"TypeOK: status={status!r} not in {VALID_STATUSES}"
    )

    # GateBlocking
    if gate_checked and artifacts_verdict == "fail":
        assert set(results.keys()) == {"artifacts"}, (
            f"GateBlocking: results keys must be {{'artifacts'}}, "
            f"got {set(results.keys())}"
        )
        assert passes_started == {"artifacts"}, (
            f"GateBlocking: passes_started must be {{'artifacts'}}, "
            f"got {passes_started!r}"
        )

    # GatePassthrough
    if status in {"pass", "warning"}:
        assert ALL_PASSES.issubset(passes_started), (
            f"GatePassthrough: expected {ALL_PASSES!r} ⊆ passes_started, "
            f"got {passes_started!r}"
        )

    # BlockedStatus
    if status == "blocked":
        assert gate_checked and artifacts_verdict == "fail", (
            "BlockedStatus(→): status='blocked' requires gate_checked=True "
            "and artifacts_verdict='fail'"
        )
    if gate_checked and artifacts_verdict == "fail":
        assert status == "blocked", (
            f"BlockedStatus(←): gate_checked=True + verdict='fail' must "
            f"yield status='blocked', got {status!r}"
        )

    # CostAccuracy
    if status == "blocked":
        assert total_cost == ARTIFACTS_COST, (
            f"CostAccuracy: expected total_cost={ARTIFACTS_COST}, "
            f"got {total_cost}"
        )

    # OnlyArtifactsWhenBlocked
    if status == "blocked":
        assert set(results.keys()) == {"artifacts"}, (
            f"OnlyArtifactsWhenBlocked: expected only 'artifacts' in results, "
            f"got {set(results.keys())}"
        )

    # NoExtraPassesWhenBlocked
    if status == "blocked":
        assert passes_started == {"artifacts"}, (
            f"NoExtraPassesWhenBlocked: expected {{'artifacts'}}, "
            f"got {passes_started!r}"
        )


# ============================================================================
# Trace-derived tests
# ============================================================================


class TestTrace1:
    """Trace 1 (5 steps): SelectVerdict=fail → blocked."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="fail")

    def test_dag_structure(self, dag: RegistryDag) -> None:
        assert dag.node_count == 4
        assert dag.edge_count == 3

    def test_status_is_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "blocked"

    def test_blocked_by_artifacts(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["blocked_by"] == "artifacts"

    def test_total_cost_equals_artifacts_cost(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == ARTIFACTS_COST

    def test_only_artifacts_in_results(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert set(result["results"].keys()) == {"artifacts"}

    def test_artifacts_result_shape(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        art = result["results"]["artifacts"]
        assert art["name"]     == "artifacts"
        assert art["verdict"]  == "fail"
        assert art["cost_usd"] == ARTIFACTS_COST

    def test_passes_started_only_artifacts(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert passes_started == {"artifacts"}

    def test_gate_checked_true(self, dag: RegistryDag) -> None:
        _, _, gate_checked = _run_from_dag(dag)
        assert gate_checked is True

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace2:
    """Trace 2 (5 steps): verdict='fail' — confirms determinism of the gate."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="fail")

    def test_dag_structure(self, dag: RegistryDag) -> None:
        assert dag.node_count == 4
        assert dag.edge_count == 3

    def test_status_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "blocked"

    def test_blocked_by_artifacts(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["blocked_by"] == "artifacts"

    def test_total_cost(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == ARTIFACTS_COST

    def test_only_artifacts_result(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert set(result["results"].keys()) == {"artifacts"}

    def test_no_parallel_passes_started(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert "coverage" not in passes_started
        assert "security" not in passes_started

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace3:
    """Trace 3 (6 steps): SelectVerdict=warning → gate passes → RunParallel."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="warning")

    def test_dag_structure(self, dag: RegistryDag) -> None:
        assert dag.node_count == 4
        assert dag.edge_count == 3

    def test_status_is_warning(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "warning"

    def test_not_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] != "blocked"
        assert result["blocked_by"] == "none"

    def test_all_three_passes_in_results(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert set(result["results"].keys()) == {"artifacts", "coverage", "security"}

    def test_total_cost_is_twenty(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == TOTAL_COST_ALL

    def test_artifacts_result_carries_warning(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["results"]["artifacts"]["verdict"] == "warning"
        assert result["results"]["artifacts"]["cost_usd"] == ARTIFACTS_COST

    def test_parallel_passes_all_pass(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["results"]["coverage"]["verdict"] == "pass"
        assert result["results"]["security"]["verdict"] == "pass"

    def test_passes_started_contains_all(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert passes_started == {"artifacts", "coverage", "security"}

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace4:
    """Trace 4 (6 steps): SelectVerdict=pass → gate passes → RunParallel."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="pass")

    def test_dag_structure(self, dag: RegistryDag) -> None:
        assert dag.node_count == 4
        assert dag.edge_count == 3

    def test_status_is_pass(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "pass"

    def test_not_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] != "blocked"
        assert result["blocked_by"] == "none"

    def test_all_three_passes_in_results(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert set(result["results"].keys()) == {"artifacts", "coverage", "security"}

    def test_total_cost_is_twenty(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == TOTAL_COST_ALL

    def test_artifacts_result_carries_pass(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["results"]["artifacts"]["verdict"] == "pass"

    def test_passes_started_contains_all(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert passes_started == {"artifacts", "coverage", "security"}

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace5:
    """Trace 5 (6 steps): second independent TLC execution with verdict=warning."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="warning")

    def test_status_is_warning(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "warning"

    def test_parallel_passes_ran(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert {"coverage", "security"}.issubset(passes_started)

    def test_coverage_result_shape(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        cov = result["results"]["coverage"]
        assert cov["name"]     == "coverage"
        assert cov["verdict"]  == "pass"
        assert cov["cost_usd"] == 5

    def test_security_result_shape(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        sec = result["results"]["security"]
        assert sec["name"]     == "security"
        assert sec["verdict"]  == "pass"
        assert sec["cost_usd"] == 5

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace6:
    """Trace 6 (5 steps): third independent TLC execution confirming the fail path."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="fail")

    def test_status_is_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "blocked"

    def test_coverage_never_started(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert "coverage" not in passes_started

    def test_security_never_started(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert "security" not in passes_started

    def test_cost_not_inflated(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == ARTIFACTS_COST
        assert result["total_cost"] < TOTAL_COST_ALL

    def test_artifacts_result_verdict_is_fail(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["results"]["artifacts"]["verdict"] == "fail"

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace7:
    """Trace 7 (6 steps): SelectVerdict=unknown → gate passes → status='pass'."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="unknown")

    def test_status_is_pass(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "pass"

    def test_not_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] != "blocked"

    def test_all_three_passes_ran(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert passes_started == {"artifacts", "coverage", "security"}

    def test_artifacts_verdict_preserved(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["results"]["artifacts"]["verdict"] == "unknown"

    def test_total_cost_full(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == TOTAL_COST_ALL

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace8:
    """Trace 8 (6 steps): second independent TLC execution with verdict=unknown."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="unknown")

    def test_status_is_pass(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "pass"

    def test_passes_started_all_three(self, dag: RegistryDag) -> None:
        _, passes_started, _ = _run_from_dag(dag)
        assert ALL_PASSES == passes_started

    def test_blocked_by_none(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["blocked_by"] == "none"

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace9:
    """Trace 9 (6 steps): third independent TLC execution with verdict=warning."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="warning")

    def test_status_is_warning(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "warning"

    def test_all_passes_in_results(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert ALL_PASSES == set(result["results"].keys())

    def test_total_cost_twenty(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == TOTAL_COST_ALL

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


class TestTrace10:
    """Trace 10 (5 steps): fourth independent TLC execution with verdict=fail."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _build_dag(artifacts_verdict="fail")

    def test_status_blocked(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["status"] == "blocked"

    def test_blocked_by_artifacts(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["blocked_by"] == "artifacts"

    def test_results_single_key(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert len(result["results"]) == 1
        assert "artifacts" in result["results"]

    def test_total_cost_not_inflated(self, dag: RegistryDag) -> None:
        result, _, _ = _run_from_dag(dag)
        assert result["total_cost"] == ARTIFACTS_COST

    def test_all_invariants(self, dag: RegistryDag) -> None:
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert_all_invariants(result, passes_started, gate_checked,
                               dag.__dict__["test_artifacts"]["artifacts_verdict"])


# ============================================================================
# Per-invariant verifiers
# ============================================================================


class TestInvariantGateBlocking:
    """GateBlocking: gate_checked ∧ verdict='fail'  ⟹
    DOMAIN results = {"artifacts"} ∧ passes_started = {"artifacts"}.
    """

    def test_fail_verdict_blocks_exactly_artifacts(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert gate_checked is True
        assert set(result["results"].keys()) == {"artifacts"}
        assert passes_started == {"artifacts"}
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_non_fail_verdicts_do_not_trigger_gate_blocking(self) -> None:
        for verdict in ("pass", "warning", "unknown"):
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert passes_started != {"artifacts"}, (
                f"verdict={verdict!r}: expected parallel passes to run, "
                f"got passes_started={passes_started!r}"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)

    def test_fail_results_contains_artifacts_pass_detail(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        art = result["results"]["artifacts"]
        assert art["name"] == "artifacts"
        assert art["verdict"] == "fail"
        assert art["cost_usd"] == ARTIFACTS_COST
        assert_all_invariants(result, passes_started, gate_checked, "fail")


class TestInvariantGatePassthrough:
    """GatePassthrough: status ∈ {"pass","warning"}  ⟹
    {"artifacts","coverage","security"} ⊆ passes_started.
    """

    def test_warning_verdict_runs_all_passes(self) -> None:
        dag = _build_dag(artifacts_verdict="warning")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "warning"
        assert ALL_PASSES.issubset(passes_started)
        assert_all_invariants(result, passes_started, gate_checked, "warning")

    def test_pass_verdict_runs_all_passes(self) -> None:
        dag = _build_dag(artifacts_verdict="pass")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "pass"
        assert ALL_PASSES.issubset(passes_started)
        assert_all_invariants(result, passes_started, gate_checked, "pass")

    def test_unknown_verdict_also_runs_all_passes(self) -> None:
        dag = _build_dag(artifacts_verdict="unknown")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "pass"
        assert ALL_PASSES.issubset(passes_started)
        assert_all_invariants(result, passes_started, gate_checked, "unknown")


class TestInvariantBlockedStatus:
    """BlockedStatus: status='blocked'  ⟺  gate_checked ∧ verdict='fail'."""

    def test_forward_fail_implies_blocked(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert gate_checked is True
        assert result["status"] == "blocked"
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_reverse_non_fail_never_blocked(self) -> None:
        for verdict in ("pass", "warning", "unknown"):
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert result["status"] != "blocked", (
                f"BlockedStatus(←): verdict={verdict!r} must NOT yield blocked"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)

    def test_biconditional_exhaustive_all_verdicts(self) -> None:
        expected = {"pass": "pass", "warning": "warning",
                    "fail": "blocked", "unknown": "pass"}
        for verdict, expected_status in expected.items():
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert result["status"] == expected_status, (
                f"verdict={verdict!r}: expected {expected_status!r}, "
                f"got {result['status']!r}"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)


class TestInvariantCostAccuracy:
    """CostAccuracy: status='blocked'  ⟹  total_cost = ARTIFACTS_COST (10)."""

    def test_blocked_total_cost_is_artifacts_cost_only(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert result["total_cost"] == ARTIFACTS_COST
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_unblocked_total_cost_is_full_amount(self) -> None:
        for verdict in ("pass", "warning"):
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert result["total_cost"] == TOTAL_COST_ALL, (
                f"verdict={verdict!r}: expected total={TOTAL_COST_ALL}, "
                f"got {result['total_cost']}"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)

    def test_blocked_cost_not_zero(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["total_cost"] > 0
        assert_all_invariants(result, passes_started, gate_checked, "fail")


class TestInvariantOnlyArtifactsWhenBlocked:
    """OnlyArtifactsWhenBlocked: status='blocked'  ⟹  DOMAIN results = {"artifacts"}."""

    def test_blocked_has_single_result_key(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert set(result["results"].keys()) == {"artifacts"}
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_unblocked_has_multiple_result_keys(self) -> None:
        for verdict in ("pass", "warning", "unknown"):
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert len(result["results"]) == 3, (
                f"verdict={verdict!r}: expected 3 result keys"
            )
            assert "coverage" in result["results"]
            assert "security" in result["results"]
            assert_all_invariants(result, passes_started, gate_checked, verdict)

    def test_blocked_result_has_no_coverage_or_security_key(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert "coverage" not in result["results"]
        assert "security" not in result["results"]
        assert_all_invariants(result, passes_started, gate_checked, "fail")


class TestInvariantNoExtraPassesWhenBlocked:
    """NoExtraPassesWhenBlocked: status='blocked'  ⟹  passes_started = {"artifacts"}."""

    def test_fail_verdict_starts_only_artifacts(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert passes_started == {"artifacts"}
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_non_fail_starts_all_passes(self) -> None:
        for verdict in ("pass", "warning", "unknown"):
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert passes_started == ALL_PASSES, (
                f"verdict={verdict!r}: expected passes_started={ALL_PASSES!r}, "
                f"got {passes_started!r}"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)


class TestInvariantTypeOK:
    """TypeOK: all state variables have the correct types and domain membership."""

    def test_gate_checked_is_bool_when_blocked(self) -> None:
        dag = _build_dag(artifacts_verdict="fail")
        _, _, gate_checked = _run_from_dag(dag)
        assert isinstance(gate_checked, bool)
        assert gate_checked is True

    def test_gate_checked_is_bool_when_passing(self) -> None:
        for verdict in ("pass", "warning"):
            dag = _build_dag(artifacts_verdict=verdict)
            _, _, gate_checked = _run_from_dag(dag)
            assert isinstance(gate_checked, bool)
            assert gate_checked is True

    def test_passes_started_subset_of_all_passes_for_every_verdict(self) -> None:
        for verdict in VALID_VERDICTS:
            dag = _build_dag(artifacts_verdict=verdict)
            _, passes_started, _ = _run_from_dag(dag)
            assert passes_started.issubset(ALL_PASSES), (
                f"verdict={verdict!r}: passes_started={passes_started!r} "
                f"has values outside {ALL_PASSES!r}"
            )

    def test_artifacts_verdict_in_valid_verdicts(self) -> None:
        for verdict in VALID_VERDICTS:
            dag = _build_dag(artifacts_verdict=verdict)
            assert dag.__dict__["test_artifacts"]["artifacts_verdict"] in VALID_VERDICTS

    def test_status_in_valid_statuses_for_every_verdict(self) -> None:
        expected_statuses = {
            "pass":    "pass",
            "fail":    "blocked",
            "warning": "warning",
            "unknown": "pass",
        }
        for verdict, expected in expected_statuses.items():
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert result["status"] in VALID_STATUSES
            assert result["status"] == expected
            assert_all_invariants(result, passes_started, gate_checked, verdict)


# ============================================================================
# Edge-case tests
# ============================================================================


class TestEdgeCases:

    def test_empty_dag_with_fail_verdict_still_blocks(self) -> None:
        """Isolated-node topology: gate logic is self-contained regardless of DAG shape."""
        dag = RegistryDag()
        dag.add_node(Node.resource("plan", "Minimal Plan"))
        dag.__dict__["test_artifacts"] = {"artifacts_verdict": "fail"}
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert passes_started == {"artifacts"}
        assert result["total_cost"] == ARTIFACTS_COST
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_empty_dag_with_pass_verdict_runs_parallel(self) -> None:
        """Isolated node: gate opens and parallel passes execute."""
        dag = RegistryDag()
        dag.add_node(Node.resource("plan", "Minimal Plan"))
        dag.__dict__["test_artifacts"] = {"artifacts_verdict": "pass"}
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "pass"
        assert passes_started == ALL_PASSES
        assert_all_invariants(result, passes_started, gate_checked, "pass")

    def test_diamond_topology_fail_verdict(self) -> None:
        """Diamond pattern: gate blocking is topology-independent."""
        dag = RegistryDag()
        for nid, name in [("plan",      "Plan"),
                          ("artifacts", "Artifacts"),
                          ("coverage",  "Coverage"),
                          ("security",  "Security"),
                          ("summary",   "Summary")]:
            dag.add_node(Node.resource(nid, name))
        dag.add_edge(Edge("plan",      "artifacts", EdgeType.IMPORTS))
        dag.add_edge(Edge("artifacts", "coverage",  EdgeType.IMPORTS))
        dag.add_edge(Edge("artifacts", "security",  EdgeType.IMPORTS))
        dag.add_edge(Edge("coverage",  "summary",   EdgeType.IMPORTS))
        dag.add_edge(Edge("security",  "summary",   EdgeType.IMPORTS))
        dag.__dict__["test_artifacts"] = {"artifacts_verdict": "fail"}
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert set(result["results"].keys()) == {"artifacts"}
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_diamond_topology_warning_verdict(self) -> None:
        """Diamond pattern: gate opens for 'warning', all passes run."""
        dag = RegistryDag()
        for nid, name in [("plan",      "Plan"),
                          ("artifacts", "Artifacts"),
                          ("coverage",  "Coverage"),
                          ("security",  "Security"),
                          ("summary",   "Summary")]:
            dag.add_node(Node.resource(nid, name))
        dag.add_edge(Edge("plan",      "artifacts", EdgeType.IMPORTS))
        dag.add_edge(Edge("artifacts", "coverage",  EdgeType.IMPORTS))
        dag.add_edge(Edge("artifacts", "security",  EdgeType.IMPORTS))
        dag.add_edge(Edge("coverage",  "summary",   EdgeType.IMPORTS))
        dag.add_edge(Edge("security",  "summary",   EdgeType.IMPORTS))
        dag.__dict__["test_artifacts"] = {"artifacts_verdict": "warning"}
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "warning"
        assert passes_started == ALL_PASSES
        assert result["total_cost"] == TOTAL_COST_ALL
        assert_all_invariants(result, passes_started, gate_checked, "warning")

    def test_all_verdicts_produce_distinct_expected_statuses(self) -> None:
        """Exhaustive verdict→status mapping: each verdict hits the correct branch."""
        mapping = {
            "pass":    "pass",
            "fail":    "blocked",
            "warning": "warning",
            "unknown": "pass",
        }
        for verdict, expected_status in mapping.items():
            dag = _build_dag(artifacts_verdict=verdict)
            result, passes_started, gate_checked = _run_from_dag(dag)
            assert result["status"] == expected_status, (
                f"verdict={verdict!r}: expected {expected_status!r}, "
                f"got {result['status']!r}"
            )
            assert_all_invariants(result, passes_started, gate_checked, verdict)

    def test_blocked_result_is_json_serialisable(self) -> None:
        """final_result must contain only JSON-safe scalar types when blocked."""
        dag = _build_dag(artifacts_verdict="fail")
        result, _, _ = _run_from_dag(dag)
        payload = json.dumps(result)
        decoded = json.loads(payload)
        assert decoded["status"] == "blocked"
        assert decoded["blocked_by"] == "artifacts"
        assert set(decoded["results"].keys()) == {"artifacts"}

    def test_unblocked_result_is_json_serialisable(self) -> None:
        """Full results dict must also be JSON-safe when gate opens."""
        dag = _build_dag(artifacts_verdict="pass")
        result, _, _ = _run_from_dag(dag)
        payload = json.dumps(result)
        decoded = json.loads(payload)
        assert decoded["status"] == "pass"
        assert set(decoded["results"].keys()) == {"artifacts", "coverage", "security"}

    def test_dag_structural_integrity_after_gate_check(self) -> None:
        """DAG node/edge counts are unaffected by the gate simulation result."""
        dag = _build_dag(artifacts_verdict="fail")
        assert dag.node_count == 4
        assert dag.edge_count == 3
        result, passes_started, gate_checked = _run_from_dag(dag)
        assert result["status"] == "blocked"
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_cost_components_sum_correctly_when_unblocked(self) -> None:
        """Individual pass costs must add up to total_cost (no phantom cost)."""
        dag = _build_dag(artifacts_verdict="pass")
        result, passes_started, gate_checked = _run_from_dag(dag)
        individual_sum = sum(r["cost_usd"] for r in result["results"].values())
        assert individual_sum == result["total_cost"]
        assert result["total_cost"] == TOTAL_COST_ALL
        assert_all_invariants(result, passes_started, gate_checked, "pass")

    def test_cost_components_sum_correctly_when_blocked(self) -> None:
        """When blocked, only artifacts cost should be present and sum must match."""
        dag = _build_dag(artifacts_verdict="fail")
        result, passes_started, gate_checked = _run_from_dag(dag)
        individual_sum = sum(r["cost_usd"] for r in result["results"].values())
        assert individual_sum == result["total_cost"]
        assert result["total_cost"] == ARTIFACTS_COST
        assert_all_invariants(result, passes_started, gate_checked, "fail")

    def test_blocked_cost_strictly_less_than_full_cost(self) -> None:
        """Gate blocking saves cost: ARTIFACTS_COST < TOTAL_COST_ALL."""
        dag_blocked   = _build_dag(artifacts_verdict="fail")
        dag_unblocked = _build_dag(artifacts_verdict="pass")
        result_blocked,   _, _ = _run_from_dag(dag_blocked)
        result_unblocked, _, _ = _run_from_dag(dag_unblocked)
        assert result_blocked["total_cost"] < result_unblocked["total_cost"]
        assert result_blocked["total_cost"]   == ARTIFACTS_COST
        assert result_unblocked["total_cost"] == TOTAL_COST_ALL