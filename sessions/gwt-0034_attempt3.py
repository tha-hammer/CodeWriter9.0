from __future__ import annotations

import pytest
from registry.dag import RegistryDag
from registry.types import Node

GWT_1 = "gwt_1"
GWT_2 = "gwt_2"
GWT_IDS = {GWT_1, GWT_2}
MAX_STEPS = 10


class PipelineState:
    def __init__(self, gwt_ids: set) -> None:
        self.gwt_ids: set = set(gwt_ids)
        self.phase: str = "setup"
        self.setup_result: str = "pending"
        self.loop_done: set = set()
        self.loop_passed: set = set()
        self.bridge_attempted: set = set()
        self.bridge_done: set = set()
        self.exit_code: int = 0
        self.step_count: int = 0

    def check_setup_before_loop(self) -> None:
        """TLA+ invariant: SetupBeforeLoop — phase=loop implies setup_result=pass."""
        if self.phase == "loop":
            assert self.setup_result == "pass", (
                f"phase=loop but setup_result={self.setup_result!r}"
            )

    def check_loop_before_bridge(self) -> None:
        """TLA+ invariant: LoopBeforeBridge — phase=bridge implies loop_done=gwt_ids."""
        if self.phase == "bridge":
            assert self.loop_done == self.gwt_ids, (
                f"phase=bridge but loop_done={self.loop_done} != gwt_ids={self.gwt_ids}"
            )

    def check_bridge_only_verified(self) -> None:
        """TLA+ invariant: BridgeOnlyVerified — bridge_done ⊆ loop_passed (always)."""
        assert self.bridge_done <= self.loop_passed, (
            f"bridge_done={self.bridge_done} not subset of loop_passed={self.loop_passed}"
        )

    def check_early_exit_on_setup_fail(self) -> None:
        """TLA+ invariant: EarlyExitOnSetupFail — setup_result=fail implies phase=done."""
        if self.setup_result == "fail":
            assert self.phase == "done", (
                f"setup_result=fail but phase={self.phase!r}"
            )

    def check_all_gwts_attempted(self) -> None:
        """TLA+ invariant: AllGwtsAttempted — phase≠loop ∧ setup_result=pass implies loop_done=gwt_ids."""
        if self.phase != "loop" and self.setup_result == "pass":
            assert self.loop_done == self.gwt_ids, (
                f"phase={self.phase!r}, setup_result=pass but loop_done={self.loop_done} != gwt_ids={self.gwt_ids}"
            )

    def check_exit_code_correct(self) -> None:
        """TLA+ invariant: ExitCodeCorrect — biconditional split into two one-sided assertions."""
        if self.phase == "done" and self.setup_result == "pass":
            expected_zero = (self.loop_passed == self.gwt_ids and self.bridge_done == self.loop_passed)
            if expected_zero:
                assert self.exit_code == 0, (
                    f"all passed but exit_code={self.exit_code}"
                )
            else:
                assert self.exit_code != 0, (
                    f"not all passed but exit_code={self.exit_code}"
                )

    def check_bounded_execution(self) -> None:
        """TLA+ invariant: BoundedExecution — step_count ≤ MAX_STEPS."""
        assert self.step_count <= MAX_STEPS, (
            f"step_count={self.step_count} > MAX_STEPS={MAX_STEPS}"
        )

    def check_all_invariants(self) -> None:
        """Fire all seven TLA+ invariant checkers at the current state."""
        self.check_setup_before_loop()
        self.check_loop_before_bridge()
        self.check_bridge_only_verified()
        self.check_early_exit_on_setup_fail()
        self.check_all_gwts_attempted()
        self.check_exit_code_correct()
        self.check_bounded_execution()


def _make_dag_with_gwts(gwt_ids) -> RegistryDag:
    dag = RegistryDag()
    for gid in gwt_ids:
        dag.add_node(Node.behavior(gid, gid, given="given", when="when", then="then"))
    return dag


def do_setup_init(dag: RegistryDag, state: PipelineState, gwt_ids: set, fail: bool = False) -> None:
    if fail:
        state.setup_result = "fail"
        state.phase = "done"
        state.exit_code = 1
        state.step_count += 1
    else:
        for gid in gwt_ids:
            dag.query_relevant(gid)
        state.step_count += 1
    state.check_all_invariants()


def do_setup_extract(dag: RegistryDag, state: PipelineState, gwt_ids: set, fail: bool = False) -> None:
    if fail:
        state.setup_result = "fail"
        state.phase = "done"
        state.exit_code = 1
        state.step_count += 1
    else:
        for gid in gwt_ids:
            dag.extract_subgraph(gid)
        state.step_count += 1
    state.check_all_invariants()


def do_after_extract(state: PipelineState) -> None:
    if state.phase != "done":
        state.setup_result = "pass"
        state.phase = "loop"
    state.check_all_invariants()


def do_loop_phase(dag: RegistryDag, state: PipelineState, loop_pass_set: set) -> None:
    assert state.phase == "loop"
    while state.loop_done != state.gwt_ids:
        remaining = state.gwt_ids - state.loop_done
        current = sorted(remaining)[0]
        state.check_all_invariants()
        state.loop_done.add(current)
        if current in loop_pass_set:
            state.loop_passed.add(current)
        dag.query_impact(current)
        state.check_all_invariants()
        state.step_count += 1
        state.check_all_invariants()
    state.phase = "bridge"
    state.check_all_invariants()


def do_bridge_phase(dag: RegistryDag, state: PipelineState, bridge_pass_set: set) -> None:
    assert state.phase == "bridge"
    while state.bridge_attempted != state.loop_passed:
        remaining = state.loop_passed - state.bridge_attempted
        current = sorted(remaining)[0]
        state.check_all_invariants()
        state.bridge_attempted.add(current)
        if current in bridge_pass_set:
            state.bridge_done.add(current)
        dag.query_affected_tests(current)
        state.check_all_invariants()
        state.step_count += 1
        state.check_all_invariants()
    state.exit_code = 0 if (state.loop_passed == state.gwt_ids and state.bridge_done == state.loop_passed) else 1
    state.check_all_invariants()
    state.phase = "done"
    state.check_all_invariants()


@pytest.fixture
def dag_two_gwts() -> RegistryDag:
    return _make_dag_with_gwts([GWT_1, GWT_2])


@pytest.fixture
def state_two_gwts() -> PipelineState:
    return PipelineState({GWT_1, GWT_2})


class TestTrace1_SetupExtractFails:
    def test_pipeline_extract_fail_exits_early(self, dag_two_gwts, state_two_gwts):
        """Trace: setup-init succeeds, setup-extract fails → immediate done, exit 1."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        assert state.step_count == 1
        assert state.phase == "setup"
        assert state.setup_result == "pending"
        do_setup_extract(dag, state, GWT_IDS, fail=True)
        assert state.phase == "done"
        assert state.setup_result == "fail"
        assert state.exit_code == 1
        assert state.loop_done == set()
        assert state.loop_passed == set()
        assert state.bridge_attempted == set()
        assert state.bridge_done == set()
        assert state.step_count == 2
        state.check_all_invariants()


class TestTrace2_SetupInitFails:
    def test_pipeline_init_fail_exits_immediately(self, dag_two_gwts, state_two_gwts):
        """Trace: setup-init fails → immediate done at step 1, exit 1, no loop or bridge work."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=True)
        assert state.phase == "done"
        assert state.setup_result == "fail"
        assert state.exit_code == 1
        assert state.loop_done == set()
        assert state.loop_passed == set()
        assert state.bridge_attempted == set()
        assert state.bridge_done == set()
        assert state.step_count == 1
        state.check_all_invariants()


class TestTrace3_LoopPartialPassBridgeFails:
    def test_partial_loop_pass_bridge_fail(self, dag_two_gwts, state_two_gwts):
        """Trace: only GWT_2 passes loop, bridge receives no passes → exit 1."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        assert state.phase == "loop"
        assert state.setup_result == "pass"
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        assert state.loop_done == {GWT_1, GWT_2}
        assert state.loop_passed == {GWT_2}
        do_bridge_phase(dag, state, bridge_pass_set=set())
        assert state.phase == "done"
        assert state.setup_result == "pass"
        assert state.exit_code == 1
        assert state.loop_done == {GWT_1, GWT_2}
        assert state.loop_passed == {GWT_2}
        assert state.bridge_attempted == {GWT_2}
        assert state.bridge_done == set()


class TestTrace4_LoopPartialPassBridgePassesSubset:
    def test_partial_loop_pass_bridge_success_still_fails(self, dag_two_gwts, state_two_gwts):
        """Trace: only GWT_2 passes loop and bridge → exit 1 because GWT_1 never passed loop."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_2})
        assert state.phase == "done"
        assert state.exit_code == 1
        assert state.loop_passed == {GWT_2}
        assert state.bridge_attempted == {GWT_2}
        assert state.bridge_done == {GWT_2}


class TestTrace5_BothLoopPassPartialBridgeDone:
    def test_both_loop_pass_partial_bridge_done(self, dag_two_gwts, state_two_gwts):
        """Trace: both GWTs pass loop, only GWT_1 passes bridge → exit 1."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        assert state.loop_passed == {GWT_1, GWT_2}
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1})
        assert state.phase == "done"
        assert state.loop_passed == {GWT_1, GWT_2}
        assert state.bridge_attempted == {GWT_1, GWT_2}
        assert state.bridge_done == {GWT_1}
        assert state.exit_code == 1


class TestInvariantSetupBeforeLoop:
    def test_loop_phase_requires_setup_pass(self, dag_two_gwts, state_two_gwts):
        """TLA+ SetupBeforeLoop: after successful setup, entering loop phase has setup_result=pass."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        assert state.phase == "loop"
        assert state.setup_result == "pass"
        state.check_setup_before_loop()

    def test_setup_fail_never_reaches_loop(self, dag_two_gwts, state_two_gwts):
        """TLA+ SetupBeforeLoop: setup failure must not leave state in loop phase."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=True)
        assert state.phase == "done"
        assert state.phase != "loop"
        state.check_setup_before_loop()


class TestInvariantLoopBeforeBridge:
    def test_all_gwts_in_loop_done_before_bridge(self, dag_two_gwts, state_two_gwts):
        """TLA+ LoopBeforeBridge: bridge phase is entered only after loop_done equals gwt_ids (all pass)."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        assert state.phase == "bridge"
        assert state.loop_done == state.gwt_ids
        state.check_loop_before_bridge()

    def test_partial_loop_still_has_all_in_loop_done_at_bridge(self, dag_two_gwts, state_two_gwts):
        """TLA+ LoopBeforeBridge: even with partial loop_passed, loop_done must cover all gwt_ids."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        assert state.phase == "bridge"
        assert state.loop_done == {GWT_1, GWT_2}
        assert state.loop_passed == {GWT_2}
        state.check_loop_before_bridge()


class TestInvariantBridgeOnlyVerified:
    def test_bridge_done_subset_of_loop_passed(self, dag_two_gwts, state_two_gwts):
        """TLA+ BridgeOnlyVerified: bridge_done ⊆ loop_passed when only GWT_2 passed loop."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_2})
        assert state.bridge_done <= state.loop_passed
        state.check_bridge_only_verified()

    def test_bridge_done_subset_when_both_pass(self, dag_two_gwts, state_two_gwts):
        """TLA+ BridgeOnlyVerified: bridge_done ⊆ loop_passed when both pass loop, one passes bridge."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1})
        assert state.bridge_done == {GWT_1}
        assert state.bridge_done <= state.loop_passed
        state.check_bridge_only_verified()


class TestInvariantEarlyExitOnSetupFail:
    def test_init_fail_goes_to_done(self, dag_two_gwts, state_two_gwts):
        """TLA+ EarlyExitOnSetupFail: setup-init failure immediately transitions phase to done."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=True)
        assert state.setup_result == "fail"
        assert state.phase == "done"
        state.check_early_exit_on_setup_fail()

    def test_extract_fail_goes_to_done(self, dag_two_gwts, state_two_gwts):
        """TLA+ EarlyExitOnSetupFail: setup-extract failure immediately transitions phase to done."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=True)
        assert state.setup_result == "fail"
        assert state.phase == "done"
        state.check_early_exit_on_setup_fail()


class TestInvariantAllGwtsAttempted:
    def test_all_gwts_in_loop_done_after_loop_phase(self, dag_two_gwts, state_two_gwts):
        """TLA+ AllGwtsAttempted: after loop phase completes, loop_done equals gwt_ids."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        assert state.phase == "bridge"
        assert state.loop_done == state.gwt_ids
        state.check_all_gwts_attempted()

    def test_all_gwts_attempted_at_done(self, dag_two_gwts, state_two_gwts):
        """TLA+ AllGwtsAttempted: at terminal done phase with setup pass, loop_done equals gwt_ids."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1, GWT_2})
        assert state.phase == "done"
        assert state.loop_done == state.gwt_ids
        state.check_all_gwts_attempted()


class TestInvariantExitCodeCorrect:
    def test_exit_zero_when_all_pass_all_bridge(self, dag_two_gwts, state_two_gwts):
        """TLA+ ExitCodeCorrect (zero arm): loop_passed=gwt_ids ∧ bridge_done=loop_passed → exit_code=0."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1, GWT_2})
        assert state.phase == "done"
        assert state.exit_code == 0
        state.check_exit_code_correct()

    def test_exit_nonzero_when_loop_partial(self, dag_two_gwts, state_two_gwts):
        """TLA+ ExitCodeCorrect (nonzero arm): loop_passed ≠ gwt_ids → exit_code ≠ 0."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_2})
        assert state.phase == "done"
        assert state.exit_code == 1
        state.check_exit_code_correct()

    def test_exit_nonzero_when_bridge_partial(self, dag_two_gwts, state_two_gwts):
        """TLA+ ExitCodeCorrect (nonzero arm): bridge_done ≠ loop_passed → exit_code ≠ 0."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1})
        assert state.phase == "done"
        assert state.exit_code == 1
        state.check_exit_code_correct()


class TestInvariantBoundedExecution:
    def test_step_count_within_bounds_full_pipeline(self, dag_two_gwts, state_two_gwts):
        """TLA+ BoundedExecution: step_count stays at or below MAX_STEPS through a full happy-path run."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1, GWT_2})
        assert state.step_count <= MAX_STEPS
        state.check_bounded_execution()

    def test_step_count_within_bounds_early_exit(self, dag_two_gwts, state_two_gwts):
        """TLA+ BoundedExecution: early exit from setup-init failure uses exactly 1 step."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=True)
        assert state.step_count == 1
        assert state.step_count <= MAX_STEPS
        state.check_bounded_execution()


class TestEdgeCases:
    def test_empty_loop_passed_means_no_bridge_work(self, dag_two_gwts, state_two_gwts):
        """Edge case: no GWTs pass the loop phase — bridge phase does nothing, exit 1."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set=set())
        assert state.loop_passed == set()
        assert state.phase == "bridge"
        do_bridge_phase(dag, state, bridge_pass_set=set())
        assert state.bridge_attempted == set()
        assert state.exit_code == 1
        assert state.phase == "done"

    def test_single_gwt_full_pass(self):
        """Edge case: single-GWT pipeline where all phases succeed → exit 0."""
        gwt_only = "gwt_only"
        dag = _make_dag_with_gwts([gwt_only])
        state = PipelineState({gwt_only})
        do_setup_init(dag, state, {gwt_only}, fail=False)
        do_setup_extract(dag, state, {gwt_only}, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={gwt_only})
        do_bridge_phase(dag, state, bridge_pass_set={gwt_only})
        assert state.exit_code == 0
        assert state.loop_passed == {gwt_only}
        assert state.bridge_done == {gwt_only}
        assert state.phase == "done"

    def test_single_gwt_loop_fail(self):
        """Edge case: single-GWT pipeline where loop fails → bridge skipped, exit 1."""
        gwt_only = "gwt_only"
        dag = _make_dag_with_gwts([gwt_only])
        state = PipelineState({gwt_only})
        do_setup_init(dag, state, {gwt_only}, fail=False)
        do_setup_extract(dag, state, {gwt_only}, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set=set())
        do_bridge_phase(dag, state, bridge_pass_set=set())
        assert state.exit_code == 1
        assert state.bridge_done == set()
        assert state.bridge_attempted == set()

    def test_bridge_only_receives_loop_passed_gwts(self, dag_two_gwts, state_two_gwts):
        """Edge case: GWT_1 fails loop so it must not appear in bridge_attempted or bridge_done."""
        dag = dag_two_gwts
        state = state_two_gwts
        do_setup_init(dag, state, GWT_IDS, fail=False)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        do_after_extract(state)
        do_loop_phase(dag, state, loop_pass_set={GWT_2})
        do_bridge_phase(dag, state, bridge_pass_set={GWT_2})
        assert GWT_1 not in state.bridge_attempted
        assert GWT_1 not in state.bridge_done

    @pytest.mark.parametrize("fail_on_init", [True, False])
    def test_setup_fail_produces_nonzero_exit_code(self, fail_on_init):
        """Edge case: setup failure (either init or extract) always yields exit_code=1 and phase=done."""
        dag = _make_dag_with_gwts([GWT_1, GWT_2])
        state = PipelineState({GWT_1, GWT_2})
        if fail_on_init:
            do_setup_init(dag, state, GWT_IDS, fail=True)
        else:
            do_setup_init(dag, state, GWT_IDS, fail=False)
            do_setup_extract(dag, state, GWT_IDS, fail=True)
        assert state.exit_code == 1
        assert state.phase == "done"

    def test_step_count_increases_monotonically(self, dag_two_gwts, state_two_gwts):
        """Edge case: step_count must never decrease across any pipeline transition."""
        dag = dag_two_gwts
        state = state_two_gwts
        counts: list[int] = []
        do_setup_init(dag, state, GWT_IDS, fail=False)
        counts.append(state.step_count)
        do_setup_extract(dag, state, GWT_IDS, fail=False)
        counts.append(state.step_count)
        do_after_extract(state)
        counts.append(state.step_count)
        do_loop_phase(dag, state, loop_pass_set={GWT_1, GWT_2})
        counts.append(state.step_count)
        do_bridge_phase(dag, state, bridge_pass_set={GWT_1, GWT_2})
        counts.append(state.step_count)
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1], (
                f"step_count decreased: counts[{i-1}]={counts[i-1]}, counts[{i}]={counts[i]}"
            )