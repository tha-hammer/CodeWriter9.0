import pytest
from registry.types import Node, Edge, EdgeType, NodeKind
from registry.dag import RegistryDag, CycleError, NodeNotFoundError

MAX_ATTEMPTS = 10
PASS_VALUES   = {"NONE", "PLAN", "REVIEW", "CODEGEN"}
STAGE_VALUES  = {"NONE", "COMPILE", "COLLECT", "RUN"}


class PipelineState:
    def __init__(self, max_attempts: int = MAX_ATTEMPTS) -> None:
        self.max_attempts        = max_attempts
        self.pass_completed      = "NONE"
        self.verification_stage  = "NONE"
        self.verification_passed = False
        self.attempt             = 1
        self.file_written        = False
        self.pipeline_done       = False
        self.vfailed             = False

    def run_plan(self) -> None:
        self.pass_completed = "PLAN"

    def run_review(self) -> None:
        assert self.pass_completed == "PLAN", (
            f"RunReview precondition failed: pass_completed={self.pass_completed!r}"
        )
        self.pass_completed = "REVIEW"

    def do_codegen(self) -> None:
        assert self.pass_completed in {"REVIEW", "CODEGEN"}, (
            f"DoCodegen precondition failed: pass_completed={self.pass_completed!r}"
        )
        self.pass_completed     = "CODEGEN"
        self.file_written       = True
        self.verification_stage = "NONE"
        self.vfailed            = False

    def do_compile(self, *, fail: bool = False) -> None:
        assert self.file_written, "DoCompile requires file_written=TRUE"
        self.verification_stage = "COMPILE"
        if fail:
            self.vfailed = True

    def do_collect(self, *, fail: bool = False) -> None:
        if not self.vfailed:
            self.verification_stage = "COLLECT"
            if fail:
                self.vfailed = True

    def do_run(self, *, fail: bool = False) -> None:
        if not self.vfailed:
            self.verification_stage = "RUN"
            if fail:
                self.vfailed = True
            else:
                self.verification_passed = True
                self.pipeline_done       = True

    def check_retry(self) -> None:
        if self.vfailed:
            if self.attempt < self.max_attempts:
                self.attempt            += 1
                self.pass_completed      = "REVIEW"
                self.file_written        = False
                self.verification_stage  = "NONE"
            else:
                self.pipeline_done = True

    def assert_type_ok(self) -> None:
        assert self.pass_completed      in PASS_VALUES,  \
            f"TypeOK: pass_completed={self.pass_completed!r}"
        assert self.verification_stage  in STAGE_VALUES, \
            f"TypeOK: verification_stage={self.verification_stage!r}"
        assert isinstance(self.verification_passed, bool), \
            "TypeOK: verification_passed must be bool"
        assert 1 <= self.attempt <= self.max_attempts, \
            f"TypeOK: attempt={self.attempt} out of [1,{self.max_attempts}]"
        assert isinstance(self.file_written,   bool), "TypeOK: file_written must be bool"
        assert isinstance(self.pipeline_done,  bool), "TypeOK: pipeline_done must be bool"

    def assert_file_written_only_after_codegen(self) -> None:
        if self.file_written:
            assert self.pass_completed == "CODEGEN", (
                f"FileWrittenOnlyAfterCodegen violated: "
                f"file_written=TRUE but pass_completed={self.pass_completed!r}"
            )

    def assert_verification_requires_file(self) -> None:
        if self.verification_stage != "NONE":
            assert self.file_written, (
                f"VerificationRequiresFile violated: "
                f"stage={self.verification_stage!r} but file_written=FALSE"
            )

    def assert_verification_requires_codegen(self) -> None:
        if self.verification_stage != "NONE":
            assert self.pass_completed == "CODEGEN", (
                f"VerificationRequiresCodegen violated: "
                f"stage={self.verification_stage!r} but pass={self.pass_completed!r}"
            )

    def assert_verification_passed_requires_run(self) -> None:
        if self.verification_passed:
            assert self.verification_stage == "RUN", (
                f"VerificationPassedRequiresRun violated: "
                f"passed=TRUE but stage={self.verification_stage!r}"
            )

    def assert_verification_passed_requires_codegen(self) -> None:
        if self.verification_passed:
            assert self.file_written, \
                "VerificationPassedRequiresCodegen violated: file_written=FALSE"
            assert self.pass_completed == "CODEGEN", (
                f"VerificationPassedRequiresCodegen violated: "
                f"pass={self.pass_completed!r}"
            )

    def assert_retry_never_below_review(self) -> None:
        if not self.pipeline_done and self.pass_completed == "REVIEW":
            assert not self.file_written, (
                "RetryNeverBelowReview violated: "
                "file_written=TRUE while pass=REVIEW and not done"
            )

    def assert_attempt_bounded(self) -> None:
        assert 1 <= self.attempt <= self.max_attempts, (
            f"AttemptBounded violated: attempt={self.attempt}"
        )

    def assert_termination_sound(self) -> None:
        if self.pipeline_done:
            assert self.verification_passed or self.attempt == self.max_attempts, (
                f"TerminationSound violated: done=TRUE but "
                f"passed={self.verification_passed}, attempt={self.attempt}"
            )

    def assert_all_invariants(self) -> None:
        self.assert_type_ok()
        self.assert_file_written_only_after_codegen()
        self.assert_verification_requires_file()
        self.assert_verification_requires_codegen()
        self.assert_verification_passed_requires_run()
        self.assert_verification_passed_requires_codegen()
        self.assert_retry_never_below_review()
        self.assert_attempt_bounded()
        self.assert_termination_sound()


def _make_bridge_dag() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.resource(
        "lang_profile", "Python Language Profile",
        "Python 3.12 test language profile",
    ))
    dag.add_node(Node.behavior(
        "gwt_spec", "TestGenPipeline Behavior",
        given="bridge artifacts containing verifiers and a language profile",
        when="the test generation pipeline executes its three passes",
        then="each pass consumes the prior pass output in strict sequence",
    ))
    dag.add_node(Node.resource("verifier_compile", "Compile Verifier",
                               "Python AST parse / syntax check"))
    dag.add_node(Node.resource("verifier_collect", "Collect Verifier",
                               "pytest --collect-only"))
    dag.add_node(Node.resource("verifier_run", "Run Verifier",
                               "pytest -x -v"))
    dag.add_edge(Edge("gwt_spec",         "lang_profile",      EdgeType.IMPORTS))
    dag.add_edge(Edge("gwt_spec",         "verifier_compile",  EdgeType.IMPORTS))
    dag.add_edge(Edge("gwt_spec",         "verifier_collect",  EdgeType.IMPORTS))
    dag.add_edge(Edge("gwt_spec",         "verifier_run",      EdgeType.IMPORTS))
    dag.add_edge(Edge("verifier_collect", "verifier_compile",  EdgeType.IMPORTS))
    dag.add_edge(Edge("verifier_run",     "verifier_collect",  EdgeType.IMPORTS))
    return dag


def _run_codegen_loop(
    ps: PipelineState,
    attempts_spec: list,
) -> PipelineState:
    ps.assert_all_invariants()

    ps.run_plan()
    ps.assert_all_invariants()

    ps.run_review()
    ps.assert_all_invariants()

    for compile_fail, collect_fail, run_fail in attempts_spec:
        if ps.pipeline_done:
            break

        ps.do_codegen()
        ps.assert_all_invariants()

        ps.do_compile(fail=compile_fail)
        ps.assert_all_invariants()

        ps.do_collect(fail=collect_fail)
        ps.assert_all_invariants()

        ps.do_run(fail=run_fail)
        ps.assert_all_invariants()

        ps.check_retry()
        ps.assert_all_invariants()

    return ps


@pytest.fixture
def bridge_dag() -> RegistryDag:
    return _make_bridge_dag()


@pytest.fixture
def empty_dag() -> RegistryDag:
    return RegistryDag()


@pytest.fixture
def single_node_dag() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.resource("solo", "Isolated Node", "no edges, no component peers"))
    return dag


@pytest.fixture
def diamond_dag() -> RegistryDag:
    dag = RegistryDag()
    for nid in ("A", "B", "C", "D"):
        dag.add_node(Node.resource(nid, nid, ""))
    dag.add_edge(Edge("A", "B", EdgeType.IMPORTS))
    dag.add_edge(Edge("A", "C", EdgeType.IMPORTS))
    dag.add_edge(Edge("B", "D", EdgeType.IMPORTS))
    dag.add_edge(Edge("C", "D", EdgeType.IMPORTS))
    return dag


class TestTrace1:
    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), [
            (False, False, False),
        ])
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 1
        assert ps.vfailed             is False

    def test_dag_structural_integrity(self, bridge_dag: RegistryDag) -> None:
        qr = bridge_dag.query_relevant("gwt_spec")
        assert qr is not None
        # Edge already exists in the DAG — verify it's present
        edges = [e for e in bridge_dag.edges
                 if e.from_id == "gwt_spec" and e.to_id == "verifier_compile"]
        assert len(edges) == 1


class TestTrace2:
    _ATTEMPTS = [
        (True,  False, False),
        (False, True,  False),
        (True,  False, False),
        (False, True,  False),
        (False, True,  False),
        (True,  False, False),
        (False, False, True),
        (True,  False, False),
        (False, True,  False),
        (True,  False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "COMPILE"
        assert ps.file_written        is True
        assert ps.verification_passed is False
        assert ps.pipeline_done       is True
        assert ps.attempt             == MAX_ATTEMPTS
        assert ps.vfailed             is True

    def test_termination_sound_on_exhaustion(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_termination_sound()
        assert not ps.verification_passed
        assert ps.attempt == MAX_ATTEMPTS


class TestTrace3:
    _ATTEMPTS = [
        (False, True,  False),
        (True,  False, False),
        (False, False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 3
        assert ps.vfailed             is False

    def test_passed_implies_run_stage(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_verification_passed_requires_run()
        ps.assert_verification_passed_requires_codegen()


class TestTrace4:
    _ATTEMPTS = [
        (False, True,  False),
        (True,  False, False),
        (True,  False, False),
        (True,  False, False),
        (False, False, True),
        (False, True,  False),
        (True,  False, False),
        (False, False, True),
        (False, False, True),
        (False, True,  False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "COLLECT"
        assert ps.file_written        is True
        assert ps.verification_passed is False
        assert ps.pipeline_done       is True
        assert ps.attempt             == MAX_ATTEMPTS
        assert ps.vfailed             is True

    def test_termination_sound_collect_exhausted(self) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_termination_sound()


class TestTrace5:
    _ATTEMPTS = [
        (False, True,  False),
        (True,  False, False),
        (True,  False, False),
        (True,  False, False),
        (False, True,  False),
        (False, True,  False),
        (False, False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 7
        assert ps.vfailed             is False

    def test_dag_impact_at_success(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.verification_passed
        impact = bridge_dag.query_impact("lang_profile")
        assert impact is not None


class TestTrace6:
    _ATTEMPTS = [
        (True,  False, False),
        (False, False, True),
        (True,  False, False),
        (False, True,  False),
        (False, False, True),
        (False, False, True),
        (True,  False, False),
        (False, False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 8
        assert ps.vfailed             is False

    def test_all_invariants_hold_at_terminal_state(self) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_all_invariants()


class TestTrace7:
    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), [
            (False, False, False),
        ])
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 1
        assert ps.vfailed             is False

    def test_verifier_chain_subgraph(self, bridge_dag: RegistryDag) -> None:
        sg = bridge_dag.extract_subgraph("verifier_run")
        assert sg is not None

    def test_language_profile_impact(self, bridge_dag: RegistryDag) -> None:
        impact = bridge_dag.query_impact("lang_profile")
        assert impact is not None


class TestTrace8:
    _ATTEMPTS = [
        (False, False, True),
        (True,  False, False),
        (True,  False, False),
        (False, True,  False),
        (False, True,  False),
        (True,  False, False),
        (False, True,  False),
        (False, False, True),
        (False, False, True),
        (True,  False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "COMPILE"
        assert ps.file_written        is True
        assert ps.verification_passed is False
        assert ps.pipeline_done       is True
        assert ps.attempt             == MAX_ATTEMPTS
        assert ps.vfailed             is True

    def test_termination_sound_run_then_compile_exhausted(self) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_termination_sound()


class TestTrace9:
    _ATTEMPTS = [
        (True,  False, False),
        (False, False, True),
        (True,  False, False),
        (True,  False, False),
        (False, False, True),
        (False, True,  False),
        (True,  False, False),
        (True,  False, False),
        (False, False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 9
        assert ps.vfailed             is False

    def test_all_invariants_hold_at_terminal_state(self) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_all_invariants()


class TestTrace10:
    _ATTEMPTS = [
        (True,  False, False),
        (True,  False, False),
        (False, False, False),
    ]

    def test_final_state(self, bridge_dag: RegistryDag) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        assert ps.pass_completed      == "CODEGEN"
        assert ps.verification_stage  == "RUN"
        assert ps.file_written        is True
        assert ps.verification_passed is True
        assert ps.pipeline_done       is True
        assert ps.attempt             == 3
        assert ps.vfailed             is False

    def test_passed_state_invariants(self) -> None:
        ps = _run_codegen_loop(PipelineState(), self._ATTEMPTS)
        ps.assert_verification_passed_requires_run()
        ps.assert_verification_passed_requires_codegen()
        ps.assert_termination_sound()


class TestInvariantPassValues:
    def _collect_pass_completed_history(self, attempts_spec):
        ps = PipelineState()
        history = [ps.pass_completed]
        ps.run_plan();   history.append(ps.pass_completed)
        ps.run_review(); history.append(ps.pass_completed)
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        history.append(ps.pass_completed)
            ps.do_compile(fail=cf); history.append(ps.pass_completed)
            ps.do_collect(fail=lf); history.append(ps.pass_completed)
            ps.do_run(fail=rf);     history.append(ps.pass_completed)
            ps.check_retry();       history.append(ps.pass_completed)
        return history

    def test_single_attempt_success(self):
        for v in self._collect_pass_completed_history([(False, False, False)]):
            assert v in PASS_VALUES

    def test_three_attempt_mixed_failure(self):
        for v in self._collect_pass_completed_history([
            (True, False, False), (False, True, False), (False, False, False),
        ]):
            assert v in PASS_VALUES


class TestInvariantStageValues:
    def _step_and_check(self, attempts_spec):
        ps = PipelineState()
        assert ps.verification_stage in STAGE_VALUES
        ps.run_plan();   assert ps.verification_stage in STAGE_VALUES
        ps.run_review(); assert ps.verification_stage in STAGE_VALUES
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        assert ps.verification_stage in STAGE_VALUES
            ps.do_compile(fail=cf); assert ps.verification_stage in STAGE_VALUES
            ps.do_collect(fail=lf); assert ps.verification_stage in STAGE_VALUES
            ps.do_run(fail=rf);     assert ps.verification_stage in STAGE_VALUES
            ps.check_retry();       assert ps.verification_stage in STAGE_VALUES

    def test_topology_trace1(self):
        self._step_and_check([(False, False, False)])

    def test_topology_trace2_first_three_attempts(self):
        self._step_and_check([
            (True, False, False), (False, True, False), (True, False, False),
        ])


class TestInvariantTypeOK:
    def test_single_attempt_success_topology(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(False, False, False)])
        ps.assert_type_ok()

    def test_ten_attempt_exhaust_topology(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * 10)
        ps.assert_type_ok()

    def test_compile_then_run_failure_topology(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [
            (True,  False, False),
            (False, False, True),
            (False, False, False),
        ])
        ps.assert_type_ok()


class TestInvariantFileWrittenOnlyAfterCodegen:
    def _assert_at_every_step(self, attempts_spec):
        ps = PipelineState()
        ps.assert_file_written_only_after_codegen()
        ps.run_plan();   ps.assert_file_written_only_after_codegen()
        ps.run_review(); ps.assert_file_written_only_after_codegen()
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        ps.assert_file_written_only_after_codegen()
            ps.do_compile(fail=cf); ps.assert_file_written_only_after_codegen()
            ps.do_collect(fail=lf); ps.assert_file_written_only_after_codegen()
            ps.do_run(fail=rf);     ps.assert_file_written_only_after_codegen()
            ps.check_retry();       ps.assert_file_written_only_after_codegen()

    def test_immediate_success(self):
        self._assert_at_every_step([(False, False, False)])

    def test_retry_resets_file_written_before_next_codegen(self):
        self._assert_at_every_step([
            (True, False, False),
            (False, False, False),
        ])

    def test_exhausted_retries_still_satisfy(self):
        self._assert_at_every_step([(True, False, False)] * MAX_ATTEMPTS)


class TestInvariantVerificationRequiresFile:
    def _assert_at_every_step(self, attempts_spec):
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        ps.assert_verification_requires_file()
            ps.do_compile(fail=cf); ps.assert_verification_requires_file()
            ps.do_collect(fail=lf); ps.assert_verification_requires_file()
            ps.do_run(fail=rf);     ps.assert_verification_requires_file()
            ps.check_retry();       ps.assert_verification_requires_file()

    def test_topology_immediate_success(self):
        self._assert_at_every_step([(False, False, False)])

    def test_topology_run_failure_then_success(self):
        self._assert_at_every_step([
            (False, False, True),
            (False, False, False),
        ])

    def test_topology_compile_and_collect_failures(self):
        self._assert_at_every_step([
            (True,  False, False),
            (False, True,  False),
            (False, False, False),
        ])


class TestInvariantVerificationRequiresCodegen:
    def _assert_at_every_step(self, attempts_spec):
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        ps.assert_verification_requires_codegen()
            ps.do_compile(fail=cf); ps.assert_verification_requires_codegen()
            ps.do_collect(fail=lf); ps.assert_verification_requires_codegen()
            ps.do_run(fail=rf);     ps.assert_verification_requires_codegen()
            ps.check_retry();       ps.assert_verification_requires_codegen()

    def test_topology_trace7_immediate_success(self):
        self._assert_at_every_step([(False, False, False)])

    def test_topology_trace3_two_failures_then_success(self):
        self._assert_at_every_step([
            (False, True,  False),
            (True,  False, False),
            (False, False, False),
        ])


class TestInvariantVerificationPassedRequiresRun:
    def test_passed_only_after_run_stage_single_attempt(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(False, False, False)])
        assert ps.verification_passed is True
        ps.assert_verification_passed_requires_run()
        assert ps.verification_stage == "RUN"

    def test_passed_only_after_run_stage_seventh_attempt(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [
            (False, True,  False),
            (True,  False, False),
            (True,  False, False),
            (True,  False, False),
            (False, True,  False),
            (False, True,  False),
            (False, False, False),
        ])
        assert ps.verification_passed is True
        ps.assert_verification_passed_requires_run()

    def test_not_passed_when_exhausted(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * MAX_ATTEMPTS)
        assert ps.verification_passed is False
        ps.assert_verification_passed_requires_run()


class TestInvariantVerificationPassedRequiresCodegen:
    def test_success_first_attempt(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(False, False, False)])
        ps.assert_verification_passed_requires_codegen()
        if ps.verification_passed:
            assert ps.file_written
            assert ps.pass_completed == "CODEGEN"

    def test_success_after_compile_failures(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [
            (True,  False, False),
            (True,  False, False),
            (False, False, False),
        ])
        ps.assert_verification_passed_requires_codegen()
        assert ps.verification_passed
        assert ps.file_written
        assert ps.pass_completed == "CODEGEN"

    def test_not_passed_vacuously_holds(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * MAX_ATTEMPTS)
        assert not ps.verification_passed
        ps.assert_verification_passed_requires_codegen()


class TestInvariantRetryNeverBelowReview:
    def _check_after_each_retry(self, attempts_spec):
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen()
            ps.do_compile(fail=cf)
            ps.do_collect(fail=lf)
            ps.do_run(fail=rf)
            ps.check_retry()
            ps.assert_retry_never_below_review()

    def test_single_retry_compile_failure(self):
        self._check_after_each_retry([(True, False, False), (False, False, False)])

    def test_multiple_retries_various_failures(self):
        self._check_after_each_retry([
            (False, True,  False),
            (True,  False, False),
            (False, False, True),
            (False, False, False),
        ])

    def test_all_retries_exhausted(self):
        self._check_after_each_retry([(True, False, False)] * MAX_ATTEMPTS)


class TestInvariantAttemptBounded:
    def _check_at_every_step(self, attempts_spec):
        ps = PipelineState()
        assert 1 <= ps.attempt <= MAX_ATTEMPTS
        ps.run_plan();   assert 1 <= ps.attempt <= MAX_ATTEMPTS
        ps.run_review(); assert 1 <= ps.attempt <= MAX_ATTEMPTS
        for cf, lf, rf in attempts_spec:
            if ps.pipeline_done:
                break
            ps.do_codegen();        ps.assert_attempt_bounded()
            ps.do_compile(fail=cf); ps.assert_attempt_bounded()
            ps.do_collect(fail=lf); ps.assert_attempt_bounded()
            ps.do_run(fail=rf);     ps.assert_attempt_bounded()
            ps.check_retry();       ps.assert_attempt_bounded()

    def test_single_success_stays_at_1(self):
        self._check_at_every_step([(False, False, False)])

    def test_ten_failures_stays_at_max(self):
        self._check_at_every_step([(True, False, False)] * MAX_ATTEMPTS)
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * MAX_ATTEMPTS)
        assert ps.attempt == MAX_ATTEMPTS

    def test_never_exceeds_max(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * (MAX_ATTEMPTS + 5))
        assert ps.attempt <= MAX_ATTEMPTS


class TestInvariantTerminationSound:
    def test_sound_on_first_attempt_success(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(False, False, False)])
        assert ps.pipeline_done
        ps.assert_termination_sound()
        assert ps.verification_passed

    def test_sound_on_exhausted_retries(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [(True, False, False)] * MAX_ATTEMPTS)
        assert ps.pipeline_done
        ps.assert_termination_sound()
        assert ps.attempt == MAX_ATTEMPTS

    def test_sound_on_late_success(self):
        ps = PipelineState()
        _run_codegen_loop(ps, [
            (True,  False, False),
            (False, True,  False),
            (False, False, False),
        ])
        assert ps.pipeline_done
        ps.assert_termination_sound()
        assert ps.verification_passed

    def test_not_done_before_final_step(self):
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        assert not ps.pipeline_done


class TestEdgeCases:

    def test_empty_dag_pipeline_state_machine_still_runs(self, empty_dag: RegistryDag) -> None:
        assert empty_dag.node_count == 0
        assert empty_dag.edge_count == 0
        ps = PipelineState()
        _run_codegen_loop(ps, [(False, False, False)])
        assert ps.verification_passed
        assert ps.pipeline_done

    def test_isolated_node_has_no_crash_on_query(self, single_node_dag: RegistryDag) -> None:
        dag = single_node_dag
        assert dag.node_count == 1
        assert dag.edge_count == 0
        result = dag.query_relevant("solo")
        assert result is not None
        sg = dag.extract_subgraph("solo")
        assert sg is not None

    def test_missing_node_raises(self, empty_dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError):
            empty_dag.query_relevant("ghost")

    def test_diamond_dag_no_cycle(self, diamond_dag: RegistryDag) -> None:
        dag = diamond_dag
        assert dag.node_count == 4
        assert dag.edge_count == 4
        impact = dag.query_impact("A")
        assert impact is not None
        sg = dag.extract_subgraph("D")
        assert sg is not None

    def test_cycle_detection_raises(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("x", "X", ""))
        dag.add_node(Node.resource("y", "Y", ""))
        dag.add_edge(Edge("x", "y", EdgeType.IMPORTS))
        with pytest.raises(CycleError):
            dag.add_edge(Edge("y", "x", EdgeType.IMPORTS))

    def test_max_attempts_boundary_exact_exhaustion(self) -> None:
        ps = _run_codegen_loop(PipelineState(), [(True, False, False)] * MAX_ATTEMPTS)
        assert ps.pipeline_done
        assert not ps.verification_passed
        assert ps.attempt == MAX_ATTEMPTS
        ps.assert_termination_sound()

    def test_success_on_last_attempt(self) -> None:
        attempts = [(True, False, False)] * (MAX_ATTEMPTS - 1) + [(False, False, False)]
        ps = _run_codegen_loop(PipelineState(), attempts)
        assert ps.pipeline_done
        assert ps.verification_passed
        assert ps.attempt == MAX_ATTEMPTS
        ps.assert_termination_sound()

    def test_plan_review_ordering_enforced(self) -> None:
        ps = PipelineState()
        ps.run_plan()
        assert ps.pass_completed == "PLAN"
        assert not ps.file_written
        ps.assert_all_invariants()
        ps.run_review()
        assert ps.pass_completed == "REVIEW"
        assert not ps.file_written
        ps.assert_all_invariants()
        ps.do_codegen()
        assert ps.pass_completed == "CODEGEN"
        assert ps.file_written
        ps.assert_all_invariants()

    def test_compile_failure_skips_collect_and_run(self) -> None:
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        ps.do_codegen()
        ps.do_compile(fail=True)
        assert ps.vfailed is True
        assert ps.verification_stage == "COMPILE"
        ps.do_collect(fail=False)
        assert ps.verification_stage == "COMPILE"
        ps.do_run(fail=False)
        assert ps.verification_stage == "COMPILE"
        assert ps.verification_passed is False
        assert ps.pipeline_done is False
        ps.assert_all_invariants()

    def test_collect_failure_skips_run(self) -> None:
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        ps.do_codegen()
        ps.do_compile(fail=False)
        assert ps.verification_stage == "COMPILE"
        assert ps.vfailed is False
        ps.do_collect(fail=True)
        assert ps.verification_stage == "COLLECT"
        assert ps.vfailed is True
        ps.do_run(fail=False)
        assert ps.verification_stage == "COLLECT"
        assert ps.verification_passed is False
        ps.assert_all_invariants()

    def test_bridge_dag_structural_integrity(self, bridge_dag: RegistryDag) -> None:
        dag = bridge_dag
        assert dag.node_count == 5
        assert dag.edge_count == 6
        assert dag.component_count >= 1
        # Verify edges exist in the DAG
        for dep in ("lang_profile", "verifier_compile", "verifier_collect", "verifier_run"):
            edges = [e for e in dag.edges if e.from_id == "gwt_spec" and e.to_id == dep]
            assert len(edges) == 1, f"Expected edge gwt_spec->{dep}"
        chain = [e for e in dag.edges
                 if e.from_id == "verifier_collect" and e.to_id == "verifier_compile"]
        assert len(chain) == 1

    def test_register_gwt_and_requirement(self, bridge_dag: RegistryDag) -> None:
        dag = bridge_dag
        gwt_id = dag.register_gwt(
            given="a verifier is present",
            when="compilation fails",
            then="the pipeline retries up to MaxAttempts times",
            name="RetryOnCompileFailure",
        )
        assert gwt_id is not None
        assert isinstance(gwt_id, str)
        assert len(gwt_id) > 0

        req_id = dag.register_requirement(
            text="Pipeline must retry codegen on any verification failure",
            name="RetryRequirement",
        )
        assert req_id is not None
        assert isinstance(req_id, str)
        assert len(req_id) > 0

    def test_attempt_never_decrements(self) -> None:
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        prev_attempt = ps.attempt
        for cf, lf, rf in [(True, False, False)] * 5:
            if ps.pipeline_done:
                break
            ps.do_codegen()
            ps.do_compile(fail=cf)
            ps.do_collect(fail=lf)
            ps.do_run(fail=rf)
            ps.check_retry()
            assert ps.attempt >= prev_attempt, \
                f"attempt decremented: {prev_attempt} -> {ps.attempt}"
            prev_attempt = ps.attempt

    def test_retry_resets_to_exactly_review_not_plan(self) -> None:
        ps = PipelineState()
        ps.run_plan()
        ps.run_review()
        ps.do_codegen()
        ps.do_compile(fail=True)
        ps.do_collect()
        ps.do_run()
        ps.check_retry()
        assert ps.pass_completed == "REVIEW"
        assert ps.attempt == 2
        assert not ps.file_written
        assert ps.verification_stage == "NONE"
        ps.assert_all_invariants()