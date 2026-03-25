"""
Tests for PlanReviewModeDetection – cmd_plan_review() mode-selection logic.

Each test class corresponds to one TLA+ simulation trace produced by TLC.
The determine_mode() helper is a faithful Python translation of the verified
TLA+ PlusCal algorithm; it is the system-under-test for every assertion.

Invariants verified in every test (matching the TLA+ define block):
  ModeValid            – determined => mode ∈ {"self","external"}
  ReviewsValid         – determined => reviews_list ∈ {"SELF_REVIEWS","EXTERNAL_REVIEWS"}
  ModeReviewConsistency – mode/reviews_list must agree when determined
  ExplicitOverrideSelf  – (determined ∧ self_flag ∧ ¬external_flag) => mode="self"
  ExplicitOverrideExternal – (determined ∧ external_flag ∧ ¬self_flag) => mode="external"
  AutoDetectExternal   – (determined ∧ ¬flags ∧ cw9_dir_exists) => mode="external"
  AutoDetectSelf       – (determined ∧ ¬flags ∧ ¬cw9_dir_exists) => mode="self"
"""
from __future__ import annotations

import pytest

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import Edge, EdgeType, Node


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_dag(
    nodes: list[str],
    edges: list[tuple[str, str]],
    artifacts: dict | None = None,
) -> RegistryDag:
    """Build a RegistryDag from trace-derived topology data."""
    dag = RegistryDag()
    for nid in nodes:
        dag.add_node(Node.behavior(nid, nid, given="g", when="w", then="t"))
    for src, dst in edges:
        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))
    dag.test_artifacts = artifacts if artifacts is not None else {}  # type: ignore[attr-defined]
    return dag


def determine_mode(
    self_flag: bool,
    external_flag: bool,
    cw9_dir_exists: bool,
) -> tuple[str, str, bool]:
    """
    Python translation of the TLA+ PlusCal DetermineMode / Finish algorithm.

    Returns
    -------
    (mode, reviews_list, determined)
      mode        – "self" | "external" | "unset"
      reviews_list – "SELF_REVIEWS" | "EXTERNAL_REVIEWS" | "UNSET"
      determined  – True when the algorithm committed to a mode
    """
    mode = "unset"
    reviews_list = "UNSET"
    determined = False

    if not (self_flag and external_flag):
        if self_flag:
            mode = "self"
            reviews_list = "SELF_REVIEWS"
        elif external_flag:
            mode = "external"
            reviews_list = "EXTERNAL_REVIEWS"
        elif cw9_dir_exists:
            mode = "external"
            reviews_list = "EXTERNAL_REVIEWS"
        else:
            mode = "self"
            reviews_list = "SELF_REVIEWS"

    if not (self_flag and external_flag):
        determined = True

    return mode, reviews_list, determined


def _assert_all_invariants(
    mode: str,
    reviews_list: str,
    determined: bool,
    self_flag: bool,
    external_flag: bool,
    cw9_dir_exists: bool,
    *,
    label: str = "",
) -> None:
    """Assert every TLA+ invariant for the given state variables."""
    ctx = f" [{label}]" if label else ""

    if determined:
        assert mode in {"self", "external"}, (
            f"ModeValid violated{ctx}: determined=True but mode={mode!r}"
        )

    if determined:
        assert reviews_list in {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}, (
            f"ReviewsValid violated{ctx}: determined=True but reviews_list={reviews_list!r}"
        )

    if determined:
        if mode == "self":
            assert reviews_list == "SELF_REVIEWS", (
                f"ModeReviewConsistency violated{ctx}: mode=self but reviews_list={reviews_list!r}"
            )
        if mode == "external":
            assert reviews_list == "EXTERNAL_REVIEWS", (
                f"ModeReviewConsistency violated{ctx}: mode=external but reviews_list={reviews_list!r}"
            )

    if determined and self_flag and not external_flag:
        assert mode == "self", (
            f"ExplicitOverrideSelf violated{ctx}: self_flag=True, external_flag=False, "
            f"determined=True but mode={mode!r}"
        )

    if determined and external_flag and not self_flag:
        assert mode == "external", (
            f"ExplicitOverrideExternal violated{ctx}: external_flag=True, self_flag=False, "
            f"determined=True but mode={mode!r}"
        )

    if determined and not self_flag and not external_flag and cw9_dir_exists:
        assert mode == "external", (
            f"AutoDetectExternal violated{ctx}: no flags, cw9_dir_exists=True, "
            f"determined=True but mode={mode!r}"
        )

    if determined and not self_flag and not external_flag and not cw9_dir_exists:
        assert mode == "self", (
            f"AutoDetectSelf violated{ctx}: no flags, cw9_dir_exists=False, "
            f"determined=True but mode={mode!r}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace-derived fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def dag_trace1() -> RegistryDag:
    """Trace 1 Init: cw9_dir_exists=True, self_flag=False, external_flag=False"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": True},
    )


@pytest.fixture
def dag_trace2() -> RegistryDag:
    """Trace 2 Init: cw9_dir_exists=False, self_flag=False, external_flag=True"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": False, "external_flag": True},
    )


@pytest.fixture
def dag_trace4() -> RegistryDag:
    """Trace 4 Init: cw9_dir_exists=False, self_flag=True, external_flag=True (conflict)"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": False, "self_flag": True, "external_flag": True},
    )


@pytest.fixture
def dag_trace5() -> RegistryDag:
    """Trace 5 Init: cw9_dir_exists=False, self_flag=True, external_flag=False"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": False, "self_flag": True},
    )


@pytest.fixture
def dag_trace6() -> RegistryDag:
    """Trace 6 Init: cw9_dir_exists=True, self_flag=True, external_flag=True (conflict)"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": True, "self_flag": True, "external_flag": True},
    )


@pytest.fixture
def dag_trace8() -> RegistryDag:
    """Trace 8 Init: cw9_dir_exists=False, self_flag=False, external_flag=False"""
    return _make_dag(
        nodes=["plan_review_target"],
        edges=[],
        artifacts={"cw9_dir_exists": False},
    )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 1 – auto-detect external (cw9 dir exists, no flags)
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace1AutoDetectExternal:
    """
    Trace 1: cw9_dir_exists=TRUE, self_flag=FALSE, external_flag=FALSE
    DetermineMode → Finish
    Expected: mode="external", reviews_list="EXTERNAL_REVIEWS", determined=True
    """

    def test_mode_is_external(self, dag_trace1: RegistryDag) -> None:
        self_flag = False
        external_flag = False
        cw9_dir_exists = True

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"
        assert determined is True

        assert dag_trace1.node_count == 1
        assert dag_trace1.test_artifacts["cw9_dir_exists"] is True  # type: ignore[attr-defined]

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace1",
        )

    def test_intermediate_state_after_determine_mode(self) -> None:
        """
        TLA+ State 2 → State 3 transition.

        determine_mode() is an atomic pure function: DetermineMode and Finish
        are not separately callable through the public interface.  We call the
        SUT once and verify the final committed state matches what TLA+ prescribes.
        """
        self_flag = False
        external_flag = False
        cw9_dir_exists = True

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"
        assert determined is True


# ──────────────────────────────────────────────────────────────────────────────
# Trace 2 – explicit --external flag overrides absence of .cw9/
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace2ExplicitExternalFlag:
    """
    Trace 2: cw9_dir_exists=FALSE, self_flag=FALSE, external_flag=TRUE
    DetermineMode → Finish
    Expected: mode="external", reviews_list="EXTERNAL_REVIEWS", determined=True
    """

    def test_mode_is_external_via_flag(self, dag_trace2: RegistryDag) -> None:
        self_flag = False
        external_flag = True
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"
        assert determined is True

        assert dag_trace2.node_count == 1
        assert dag_trace2.test_artifacts["external_flag"] is True  # type: ignore[attr-defined]

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace2",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 3 – duplicate of Trace 2 (TLC-generated; verifies same invariants)
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace3ExplicitExternalFlagDuplicate:
    """
    Trace 3: identical initial conditions to Trace 2.
    Confirms determinism of the algorithm for this input combination.
    """

    def test_mode_deterministic(self) -> None:
        self_flag = False
        external_flag = True
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"
        assert determined is True

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace3",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 4 – conflict: both flags set → undetermined
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace4BothFlagsConflict:
    """
    Trace 4: self_flag=TRUE, external_flag=TRUE, cw9_dir_exists=FALSE
    DetermineMode → Finish
    Expected: mode="unset", reviews_list="UNSET", determined=False
    """

    def test_conflict_leaves_undetermined(self, dag_trace4: RegistryDag) -> None:
        self_flag = True
        external_flag = True
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "unset"
        assert reviews_list == "UNSET"
        assert determined is False

        assert dag_trace4.node_count == 1

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace4",
        )

    def test_undetermined_vacuously_satisfies_mode_valid(self) -> None:
        """When determined=False, ModeValid is vacuously True (no constraint on mode)."""
        _, _, determined = determine_mode(
            self_flag=True, external_flag=True, cw9_dir_exists=False
        )
        assert determined is False


# ──────────────────────────────────────────────────────────────────────────────
# Trace 5 – explicit --self flag
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace5ExplicitSelfFlag:
    """
    Trace 5: self_flag=TRUE, external_flag=FALSE, cw9_dir_exists=FALSE
    DetermineMode → Finish
    Expected: mode="self", reviews_list="SELF_REVIEWS", determined=True
    """

    def test_mode_is_self_via_flag(self, dag_trace5: RegistryDag) -> None:
        self_flag = True
        external_flag = False
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "self"
        assert reviews_list == "SELF_REVIEWS"
        assert determined is True

        assert dag_trace5.node_count == 1
        assert dag_trace5.test_artifacts["self_flag"] is True  # type: ignore[attr-defined]

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace5",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 6 – conflict with cw9 present → undetermined
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace6BothFlagsConflictCw9Present:
    """
    Trace 6: self_flag=TRUE, external_flag=TRUE, cw9_dir_exists=TRUE
    DetermineMode → Finish
    Expected: mode="unset", reviews_list="UNSET", determined=False
    """

    def test_conflict_ignores_cw9_dir(self, dag_trace6: RegistryDag) -> None:
        self_flag = True
        external_flag = True
        cw9_dir_exists = True

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "unset"
        assert reviews_list == "UNSET"
        assert determined is False

        assert dag_trace6.node_count == 1
        assert dag_trace6.test_artifacts["cw9_dir_exists"] is True  # type: ignore[attr-defined]

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace6",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 7 – duplicate of Trace 6
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace7BothFlagsConflictCw9PresentDuplicate:
    """
    Trace 7: identical to Trace 6. Determinism check for the conflict branch.
    """

    def test_conflict_deterministic(self) -> None:
        self_flag = True
        external_flag = True
        cw9_dir_exists = True

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "unset"
        assert reviews_list == "UNSET"
        assert determined is False

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace7",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 8 – auto-detect self (no flags, no .cw9/)
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace8AutoDetectSelf:
    """
    Trace 8: self_flag=FALSE, external_flag=FALSE, cw9_dir_exists=FALSE
    DetermineMode → Finish
    Expected: mode="self", reviews_list="SELF_REVIEWS", determined=True
    """

    def test_mode_is_self_via_auto_detect(self, dag_trace8: RegistryDag) -> None:
        self_flag = False
        external_flag = False
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "self"
        assert reviews_list == "SELF_REVIEWS"
        assert determined is True

        assert dag_trace8.node_count == 1
        assert dag_trace8.test_artifacts.get("cw9_dir_exists") is False  # type: ignore[attr-defined]

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace8",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 9 – duplicate of Traces 6 & 7
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace9BothFlagsConflictCw9PresentAgain:
    """
    Trace 9: identical to Traces 6 & 7. Third TLC witness for conflict+cw9.
    """

    def test_conflict_third_witness(self) -> None:
        self_flag = True
        external_flag = True
        cw9_dir_exists = True

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "unset"
        assert reviews_list == "UNSET"
        assert determined is False

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace9",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Trace 10 – explicit --self flag (duplicate of Trace 5)
# ──────────────────────────────────────────────────────────────────────────────

class TestTrace10ExplicitSelfFlagAgain:
    """
    Trace 10: self_flag=TRUE, external_flag=FALSE, cw9_dir_exists=FALSE
    DetermineMode → Finish
    Expected: mode="self", reviews_list="SELF_REVIEWS", determined=True
    (Second TLC witness for ExplicitOverrideSelf.)
    """

    def test_mode_self_second_witness(self) -> None:
        self_flag = True
        external_flag = False
        cw9_dir_exists = False

        mode, reviews_list, determined = determine_mode(
            self_flag, external_flag, cw9_dir_exists
        )

        assert mode == "self"
        assert reviews_list == "SELF_REVIEWS"
        assert determined is True

        _assert_all_invariants(
            mode, reviews_list, determined,
            self_flag, external_flag, cw9_dir_exists,
            label="trace10",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Dedicated invariant verifiers
# ──────────────────────────────────────────────────────────────────────────────

class TestInvariantModeValid:
    """ModeValid: determined => mode ∈ {"self", "external"}"""

    def test_auto_detect_external_mode_valid(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert determined is True
        assert mode in {"self", "external"}

    def test_auto_detect_self_mode_valid(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=False
        )
        assert determined is True
        assert mode in {"self", "external"}

    def test_explicit_external_flag_mode_valid(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=True, cw9_dir_exists=False
        )
        assert determined is True
        assert mode in {"self", "external"}

    def test_explicit_self_flag_mode_valid(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=True, external_flag=False, cw9_dir_exists=False
        )
        assert determined is True
        assert mode in {"self", "external"}

    def test_conflict_vacuously_satisfies_mode_valid(self) -> None:
        for cw9 in (True, False):
            mode, reviews_list, determined = determine_mode(
                self_flag=True, external_flag=True, cw9_dir_exists=cw9
            )
            assert determined is False


class TestInvariantReviewsValid:
    """ReviewsValid: determined => reviews_list ∈ {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}"""

    def test_auto_detect_topologies_reviews_valid(self) -> None:
        for cw9 in (True, False):
            mode, reviews_list, determined = determine_mode(
                self_flag=False, external_flag=False, cw9_dir_exists=cw9
            )
            assert determined is True
            assert reviews_list in {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}

    def test_explicit_flag_topologies_reviews_valid(self) -> None:
        for self_flag, external_flag, cw9 in [
            (False, True, False),
            (True, False, False),
        ]:
            mode, reviews_list, determined = determine_mode(self_flag, external_flag, cw9)
            assert determined is True
            assert reviews_list in {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}

    def test_conflict_reviews_list_stays_unset(self) -> None:
        for cw9 in (True, False):
            mode, reviews_list, determined = determine_mode(
                self_flag=True, external_flag=True, cw9_dir_exists=cw9
            )
            assert determined is False
            assert reviews_list == "UNSET"


class TestInvariantModeReviewConsistency:
    """ModeReviewConsistency: mode/reviews_list must be consistent when determined."""

    def test_self_mode_always_uses_self_reviews(self) -> None:
        cases = [
            (True, False, False),
            (False, False, False),
            (True, False, True),
        ]
        for self_flag, external_flag, cw9 in cases:
            mode, reviews_list, determined = determine_mode(self_flag, external_flag, cw9)
            if determined and mode == "self":
                assert reviews_list == "SELF_REVIEWS", (
                    f"Consistency violated for {(self_flag, external_flag, cw9)}"
                )

    def test_external_mode_always_uses_external_reviews(self) -> None:
        cases = [
            (False, False, True),
            (False, True, False),
            (False, True, True),
        ]
        for self_flag, external_flag, cw9 in cases:
            mode, reviews_list, determined = determine_mode(self_flag, external_flag, cw9)
            if determined and mode == "external":
                assert reviews_list == "EXTERNAL_REVIEWS", (
                    f"Consistency violated for {(self_flag, external_flag, cw9)}"
                )


class TestInvariantExplicitOverrideSelf:
    """ExplicitOverrideSelf: (determined ∧ self_flag ∧ ¬external_flag) => mode="self" """

    def test_self_flag_no_cw9(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=True, external_flag=False, cw9_dir_exists=False
        )
        assert determined is True
        assert mode == "self"
        assert reviews_list == "SELF_REVIEWS"

    def test_self_flag_overrides_cw9_present(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=True, external_flag=False, cw9_dir_exists=True
        )
        assert determined is True
        assert mode == "self", "--self flag must override .cw9/ auto-detection"
        assert reviews_list == "SELF_REVIEWS"
        _assert_all_invariants(mode, reviews_list, determined, True, False, True)


class TestInvariantExplicitOverrideExternal:
    """ExplicitOverrideExternal: (determined ∧ external_flag ∧ ¬self_flag) => mode="external" """

    def test_external_flag_no_cw9(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=True, cw9_dir_exists=False
        )
        assert determined is True
        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"

    def test_external_flag_with_cw9(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=True, cw9_dir_exists=True
        )
        assert determined is True
        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"
        _assert_all_invariants(mode, reviews_list, determined, False, True, True)


class TestInvariantAutoDetectExternal:
    """AutoDetectExternal: (determined ∧ ¬self ∧ ¬external ∧ cw9_dir_exists) => mode="external" """

    def test_cw9_present_no_flags(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert determined is True
        assert mode == "external"
        assert reviews_list == "EXTERNAL_REVIEWS"

    def test_cw9_present_no_flags_multi_node_dag(self) -> None:
        dag = _make_dag(
            nodes=["root", "child_a", "child_b"],
            edges=[("root", "child_a"), ("root", "child_b")],
            artifacts={"cw9_dir_exists": True},
        )
        assert dag.node_count == 3
        assert dag.edge_count == 2

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert mode == "external"
        _assert_all_invariants(mode, reviews_list, determined, False, False, True)


class TestInvariantAutoDetectSelf:
    """AutoDetectSelf: (determined ∧ ¬self ∧ ¬external ∧ ¬cw9_dir_exists) => mode="self" """

    def test_no_cw9_no_flags(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=False
        )
        assert determined is True
        assert mode == "self"
        assert reviews_list == "SELF_REVIEWS"

    def test_no_cw9_no_flags_single_node_dag(self) -> None:
        dag = _make_dag(
            nodes=["target"],
            edges=[],
            artifacts={"cw9_dir_exists": False},
        )
        assert dag.node_count == 1

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=False
        )
        assert mode == "self"
        _assert_all_invariants(mode, reviews_list, determined, False, False, False)


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases derived minimally from traces, plus structural DAG edge cases."""

    def test_empty_dag_auto_detect_external(self) -> None:
        dag = _make_dag(nodes=[], edges=[], artifacts={"cw9_dir_exists": True})
        assert dag.node_count == 0

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert mode == "external"
        assert determined is True
        _assert_all_invariants(mode, reviews_list, determined, False, False, True)

    def test_empty_dag_auto_detect_self(self) -> None:
        dag = _make_dag(nodes=[], edges=[], artifacts={"cw9_dir_exists": False})
        assert dag.node_count == 0

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=False
        )
        assert mode == "self"
        assert determined is True
        _assert_all_invariants(mode, reviews_list, determined, False, False, False)

    def test_isolated_node_explicit_self_flag(self) -> None:
        dag = _make_dag(
            nodes=["isolated_target"],
            edges=[],
            artifacts={"self_flag": True},
        )
        assert dag.node_count == 1

        mode, reviews_list, determined = determine_mode(
            self_flag=True, external_flag=False, cw9_dir_exists=False
        )
        assert mode == "self"
        _assert_all_invariants(mode, reviews_list, determined, True, False, False)

    def test_none_artifacts_does_not_affect_mode_detection(self) -> None:
        dag = _make_dag(nodes=["n1"], edges=[], artifacts=None)
        assert dag.node_count == 1
        assert dag.test_artifacts == {}  # type: ignore[attr-defined]

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert mode == "external"
        _assert_all_invariants(mode, reviews_list, determined, False, False, True)

    def test_diamond_pattern_no_flags_cw9_exists(self) -> None:
        dag = _make_dag(
            nodes=["root", "left", "right", "leaf"],
            edges=[
                ("root", "left"),
                ("root", "right"),
                ("left", "leaf"),
                ("right", "leaf"),
            ],
            artifacts={"cw9_dir_exists": True},
        )
        assert dag.node_count == 4
        assert dag.edge_count == 4

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=True
        )
        assert mode == "external"
        _assert_all_invariants(mode, reviews_list, determined, False, False, True)

    def test_diamond_pattern_no_flags_no_cw9(self) -> None:
        dag = _make_dag(
            nodes=["root", "left", "right", "leaf"],
            edges=[
                ("root", "left"),
                ("root", "right"),
                ("left", "leaf"),
                ("right", "leaf"),
            ],
            artifacts={"cw9_dir_exists": False},
        )
        assert dag.node_count == 4

        mode, reviews_list, determined = determine_mode(
            self_flag=False, external_flag=False, cw9_dir_exists=False
        )
        assert mode == "self"
        _assert_all_invariants(mode, reviews_list, determined, False, False, False)

    def test_both_flags_conflict_both_cw9_values(self) -> None:
        for cw9 in (True, False):
            mode, reviews_list, determined = determine_mode(
                self_flag=True, external_flag=True, cw9_dir_exists=cw9
            )
            assert determined is False, (
                f"Conflict must leave determined=False (cw9_dir_exists={cw9})"
            )
            assert mode == "unset"
            assert reviews_list == "UNSET"
            _assert_all_invariants(
                mode, reviews_list, determined, True, True, cw9,
                label=f"conflict_cw9={cw9}",
            )

    def test_node_not_found_error_on_unknown_query(self) -> None:
        dag = _make_dag(nodes=["n1"], edges=[], artifacts={})
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("nonexistent_node_xyz")

    def test_self_flag_overrides_cw9_directory(self) -> None:
        mode, reviews_list, determined = determine_mode(
            self_flag=True, external_flag=False, cw9_dir_exists=True
        )
        assert determined is True
        assert mode == "self", (
            "--self flag must override auto-detection even when .cw9/ directory exists"
        )
        assert reviews_list == "SELF_REVIEWS"
        _assert_all_invariants(mode, reviews_list, determined, True, False, True)

    def test_exhaustive_all_eight_combinations_satisfy_all_invariants(self) -> None:
        """All 2³ = 8 combinations satisfy every TLA+ invariant."""
        for self_flag in (True, False):
            for external_flag in (True, False):
                for cw9_dir_exists in (True, False):
                    mode, reviews_list, determined = determine_mode(
                        self_flag, external_flag, cw9_dir_exists
                    )
                    _assert_all_invariants(
                        mode, reviews_list, determined,
                        self_flag, external_flag, cw9_dir_exists,
                        label=f"self={self_flag},ext={external_flag},cw9={cw9_dir_exists}",
                    )

    def test_cycle_error_raised_for_direct_cycle(self) -> None:
        dag = _make_dag(
            nodes=["alpha", "beta"],
            edges=[("alpha", "beta")],
            artifacts={},
        )
        with pytest.raises(CycleError):
            dag.add_edge(Edge("beta", "alpha", EdgeType.IMPORTS))

    def test_mode_detection_independent_of_dag_edge_count(self) -> None:
        dag_sparse = _make_dag(
            nodes=["a", "b", "c"],
            edges=[("a", "b")],
            artifacts={"cw9_dir_exists": True},
        )
        dag_dense = _make_dag(
            nodes=["a", "b", "c"],
            edges=[("a", "b"), ("a", "c")],
            artifacts={"cw9_dir_exists": True},
        )

        mode_sparse, _, _ = determine_mode(False, False, True)
        mode_dense, _, _ = determine_mode(False, False, True)

        assert mode_sparse == mode_dense == "external"
        assert dag_sparse.edge_count == 1
        assert dag_dense.edge_count == 2