import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Edge, EdgeType, Node

# ---------------------------------------------------------------------------
# TLA+ constants – must match the verified Verifiers tuple exactly
# ---------------------------------------------------------------------------
VERIFIER_DEFS = [
    {"name": "inv1", "has_cond": True,  "is_dict": True},
    {"name": "inv2", "has_cond": True,  "is_dict": True},
    {"name": "inv3", "has_cond": False, "is_dict": True},
    {"name": "skip", "has_cond": True,  "is_dict": False},
]
N = len(VERIFIER_DEFS)
EXPECTED_COMPILED = frozenset({"inv1", "inv2"})
VALID_STAGES = frozenset({"idle", "compile_all", "type_check", "discover", "run", "done"})
STAGE_RANK = {
    "idle": 0,
    "compile_all": 1,
    "type_check": 2,
    "discover": 3,
    "run": 4,
    "done": 5,
}


# ---------------------------------------------------------------------------
# VerifierState: mirrors every TLA+ state variable + all 7 invariant predicates
# ---------------------------------------------------------------------------
class VerifierState:
    """
    Simulation state that shadows TLA+ variables:
        cursor, compiled, stage, passed, pc
    Invariant methods return bool so callers can test both polarity and
    call assert_all_invariants() to get a labelled failure message.
    """

    def __init__(self, verifiers=None):
        self.cursor: int = 1
        self.compiled: set = set()
        self.stage: str = "idle"
        self.passed: bool = False
        self.pc: str = "CompileAll"
        self.verifiers: list = list(verifiers) if verifiers is not None else list(VERIFIER_DEFS)

    @property
    def n(self) -> int:
        return len(self.verifiers)

    # --- Invariant predicates (TLA+ -> Python) ---

    def check_batch_consistent(self) -> bool:
        """BatchConsistent: cursor > N => every (is_dict /\ has_cond) verifier is in compiled."""
        if self.cursor <= self.n:
            return True
        for v in self.verifiers:
            if v["is_dict"] and v["has_cond"]:
                if v["name"] not in self.compiled:
                    return False
        return True

    def check_non_dict_skipped(self) -> bool:
        """NonDictSkipped: no non-dict verifier appears in compiled."""
        non_dict = {v["name"] for v in self.verifiers if not v["is_dict"]}
        return self.compiled.isdisjoint(non_dict)

    def check_stage_ordering(self) -> bool:
        """StageOrdering: stage in valid set."""
        return self.stage in VALID_STAGES

    def check_type_check_passed_only_after_compile(self) -> bool:
        """TypeCheckPassedOnlyAfterCompile: passed => stage in {type_check,discover,run,done}."""
        if not self.passed:
            return True
        return self.stage in {"type_check", "discover", "run", "done"}

    def check_compiled_subset_valid(self) -> bool:
        """CompiledSubsetValid: every compiled entry matches a (is_dict /\ has_cond) verifier."""
        valid = {v["name"] for v in self.verifiers if v["is_dict"] and v["has_cond"]}
        return self.compiled <= valid

    def check_terminal_implies_all_checked(self) -> bool:
        """TerminalImpliesAllChecked: stage = 'done' => passed = TRUE."""
        if self.stage == "done":
            return self.passed is True
        return True

    def check_no_duplicate_names(self) -> bool:
        """NoDuplicateNames: no two entries in compiled share the same name."""
        return len(self.compiled) == len(set(self.compiled))

    def assert_all_invariants(self, label: str = "") -> None:
        prefix = f"[{label}] " if label else ""
        assert self.check_batch_consistent(), (
            f"{prefix}BatchConsistent violated: cursor={self.cursor}, compiled={self.compiled}"
        )
        assert self.check_non_dict_skipped(), (
            f"{prefix}NonDictSkipped violated: compiled={self.compiled}"
        )
        assert self.check_stage_ordering(), (
            f"{prefix}StageOrdering violated: stage={self.stage!r}"
        )
        assert self.check_type_check_passed_only_after_compile(), (
            f"{prefix}TypeCheckPassedOnlyAfterCompile violated: "
            f"passed={self.passed}, stage={self.stage!r}"
        )
        assert self.check_compiled_subset_valid(), (
            f"{prefix}CompiledSubsetValid violated: compiled={self.compiled}"
        )
        assert self.check_terminal_implies_all_checked(), (
            f"{prefix}TerminalImpliesAllChecked violated: "
            f"stage={self.stage!r}, passed={self.passed}"
        )
        assert self.check_no_duplicate_names(), (
            f"{prefix}NoDuplicateNames violated: compiled={self.compiled}"
        )


# ---------------------------------------------------------------------------
# run_compile_assertions: faithful translation of TLA+ PlusCal algorithm
# ---------------------------------------------------------------------------
def run_compile_assertions(dag: RegistryDag, verifiers=None) -> VerifierState:
    """
    Execute the full verified action sequence and assert all 7 invariants at
    every intermediate state.  Returns the terminal VerifierState.
    """
    if verifiers is None:
        artifacts = getattr(dag, "test_artifacts", {})
        verifiers = artifacts.get("verifiers", VERIFIER_DEFS)

    state = VerifierState(verifiers)

    # State 1: Init
    state.assert_all_invariants("Init")

    # Action: CompileAll -> State 2
    state.stage = "compile_all"
    state.pc = "ProcessLoop"
    state.assert_all_invariants("CompileAll")

    # Actions: ProcessLoop -> ProcessV -> AdvanceV (repeated for every verifier)
    while state.cursor <= state.n:
        state.pc = "ProcessV"
        state.assert_all_invariants(f"ProcessLoop(cursor={state.cursor})")

        v = state.verifiers[state.cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            state.compiled.add(v["name"])
        state.pc = "AdvanceV"
        state.assert_all_invariants(f"ProcessV(cursor={state.cursor})")

        state.cursor += 1
        state.pc = "ProcessLoop"
        state.assert_all_invariants(f"AdvanceV(cursor={state.cursor})")

    state.pc = "TypeCheck"
    state.assert_all_invariants(f"ProcessLoop->TypeCheck(cursor={state.cursor})")

    # TypeCheck
    state.stage = "type_check"
    state.passed = True
    state.pc = "Discover"
    state.assert_all_invariants("TypeCheck")

    # Discover
    state.stage = "discover"
    state.pc = "Run"
    state.assert_all_invariants("Discover")

    # Run
    state.stage = "run"
    state.pc = "Finish"
    state.assert_all_invariants("Run")

    # Finish
    state.stage = "done"
    state.pc = "Done"
    state.assert_all_invariants("Finish")

    return state


# ---------------------------------------------------------------------------
# DAG fixture builders
# ---------------------------------------------------------------------------
def _build_dag_full(verifiers=None) -> RegistryDag:
    if verifiers is None:
        verifiers = VERIFIER_DEFS
    dag = RegistryDag()
    for v in verifiers:
        dag.add_node(Node.behavior(
            id=v["name"],
            name=v["name"],
            given=f"is_dict={v['is_dict']}",
            when=f"has_cond={v['has_cond']}",
            then="compiled" if (v["is_dict"] and v["has_cond"]) else "skipped",
        ))
    dag.add_edge(Edge("inv1", "inv2", EdgeType.IMPORTS))
    dag.test_artifacts = {
        "verifiers": list(verifiers),
        "expected_compiled": sorted(EXPECTED_COMPILED),
    }
    return dag


def _build_dag_inv1_only() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior("inv1", "inv1", "is_dict=True", "has_cond=True", "compiled"))
    dag.test_artifacts = {
        "verifiers": [{"name": "inv1", "has_cond": True, "is_dict": True}],
        "expected_compiled": ["inv1"],
    }
    return dag


def _build_dag_empty() -> RegistryDag:
    dag = RegistryDag()
    dag.test_artifacts = {"verifiers": [], "expected_compiled": []}
    return dag


# ---------------------------------------------------------------------------
# TypeScript source generation + tsc runner
# ---------------------------------------------------------------------------
_TS_TEMPLATE = """\
// Auto-generated type-check file for compiled assertions: {names}
type AssertionName = {union_type};

const compiledAssertions: ReadonlyArray<AssertionName> = [{list}] as const;

function isValidAssertion(name: string): name is AssertionName {{
    return (compiledAssertions as ReadonlyArray<string>).includes(name);
}}

export {{ compiledAssertions, isValidAssertion }};
"""

_TS_EMPTY = "export const compiledAssertions: ReadonlyArray<never> = [] as const;\n"


def _generate_ts_source(compiled: set) -> str:
    if not compiled:
        return _TS_EMPTY
    names = sorted(compiled)
    return _TS_TEMPLATE.format(
        names=names,
        union_type=" | ".join(f'"{n}"' for n in names),
        list=", ".join(f'"{n}"' for n in names),
    )


def _run_tsc_no_emit(ts_source: str) -> tuple:
    with tempfile.TemporaryDirectory() as tmpdir:
        ts_file = Path(tmpdir) / "assertions.ts"
        ts_file.write_text(ts_source, encoding="utf-8")
        tsconfig = Path(tmpdir) / "tsconfig.json"
        tsconfig.write_text(
            json.dumps({
                "compilerOptions": {
                    "strict": True,
                    "noEmit": True,
                    "target": "ES2020",
                    "module": "ESNext",
                },
                "include": ["assertions.ts"],
            }),
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["tsc", "--project", str(tsconfig)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )
        return proc.returncode, proc.stdout + proc.stderr


def _tsc_available() -> bool:
    try:
        subprocess.run(["tsc", "--version"], capture_output=True, check=True, timeout=10)
        return True
    except Exception:
        return False


requires_tsc = pytest.mark.skipif(not _tsc_available(), reason="tsc not available in PATH")


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def dag_full():
    return _build_dag_full()


@pytest.fixture
def dag_inv1_only():
    return _build_dag_inv1_only()


@pytest.fixture
def dag_empty():
    return _build_dag_empty()


# ---------------------------------------------------------------------------
# Trace-derived tests (Traces 1-10 share identical topology and action sequence)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_action_sequence_and_terminal_state(dag_full, trace_id):
    """
    Traces 1-10 (identical structure):
      Init state:   compiled={}, passed=FALSE, stage='idle', cursor=1
      Final state:  compiled={inv1,inv2}, passed=TRUE, stage='done', cursor=5
    All 7 invariants are asserted at every intermediate state.
    """
    state = run_compile_assertions(dag_full)

    assert state.compiled == EXPECTED_COMPILED, (
        f"Trace {trace_id}: compiled={state.compiled!r} expected {EXPECTED_COMPILED!r}"
    )
    assert state.passed is True, f"Trace {trace_id}: passed must be TRUE"
    assert state.stage == "done", f"Trace {trace_id}: stage must be 'done'"
    assert state.cursor == N + 1, f"Trace {trace_id}: cursor must be {N + 1}"
    assert state.pc == "Done", f"Trace {trace_id}: pc must be 'Done'"


def test_trace_checkpoint_states_match_tla_snapshots():
    """Walk through every named TLA+ state from Trace 1 and assert each snapshot."""
    state = VerifierState()

    # State 1: Init
    assert state.compiled == set()
    assert state.passed is False
    assert state.stage == "idle"
    assert state.cursor == 1
    state.assert_all_invariants("State1-Init")

    # State 2: CompileAll
    state.stage = "compile_all"
    assert state.stage == "compile_all"
    assert state.compiled == set()
    state.assert_all_invariants("State2-CompileAll")

    # State 3: ProcessLoop (cursor=1)
    assert state.cursor == 1
    state.assert_all_invariants("State3-ProcessLoop")

    # State 4: ProcessV (cursor=1, inv1 -> add)
    state.compiled.add("inv1")
    assert state.compiled == {"inv1"}
    state.assert_all_invariants("State4-ProcessV")

    # State 5: AdvanceV
    state.cursor = 2
    state.assert_all_invariants("State5-AdvanceV")

    # State 6: ProcessLoop (cursor=2)
    state.assert_all_invariants("State6-ProcessLoop")

    # State 7: ProcessV (cursor=2, inv2 -> add)
    state.compiled.add("inv2")
    assert state.compiled == {"inv1", "inv2"}
    state.assert_all_invariants("State7-ProcessV")

    # State 8: AdvanceV
    state.cursor = 3
    state.assert_all_invariants("State8-AdvanceV")

    # State 9: ProcessLoop (cursor=3)
    state.assert_all_invariants("State9-ProcessLoop")

    # State 10: ProcessV (cursor=3, inv3: has_cond=False -> skip)
    v = VERIFIER_DEFS[2]
    if v["is_dict"] and v["has_cond"]:
        state.compiled.add(v["name"])
    assert state.compiled == {"inv1", "inv2"}, "inv3 must NOT be compiled"
    state.assert_all_invariants("State10-ProcessV")

    # State 11: AdvanceV
    state.cursor = 4
    state.assert_all_invariants("State11-AdvanceV")

    # State 12: ProcessLoop (cursor=4)
    state.assert_all_invariants("State12-ProcessLoop")

    # State 13: ProcessV (cursor=4, skip: is_dict=False -> skip)
    v = VERIFIER_DEFS[3]
    if v["is_dict"] and v["has_cond"]:
        state.compiled.add(v["name"])
    assert state.compiled == {"inv1", "inv2"}, "'skip' must NOT be compiled"
    state.assert_all_invariants("State13-ProcessV")

    # State 14: AdvanceV
    state.cursor = 5
    assert state.cursor == N + 1
    state.assert_all_invariants("State14-AdvanceV")

    # State 15: ProcessLoop (cursor > N -> route to TypeCheck)
    state.assert_all_invariants("State15-ProcessLoop-exit")

    # State 16: TypeCheck
    state.stage = "type_check"
    state.passed = True
    assert state.passed is True
    assert state.stage == "type_check"
    state.assert_all_invariants("State16-TypeCheck")

    # State 17: Discover
    state.stage = "discover"
    state.assert_all_invariants("State17-Discover")

    # State 18: Run
    state.stage = "run"
    state.assert_all_invariants("State18-Run")

    # State 19: Finish
    state.stage = "done"
    assert state.stage == "done"
    assert state.passed is True
    assert state.compiled == EXPECTED_COMPILED
    state.assert_all_invariants("State19-Finish")


def test_trace_compiled_set_unchanged_after_type_check():
    state = run_compile_assertions(_build_dag_full())
    assert frozenset(state.compiled) == EXPECTED_COMPILED


def test_trace_passed_false_during_entire_compile_phase():
    state = VerifierState()
    state.stage = "compile_all"
    for i, v in enumerate(VERIFIER_DEFS):
        state.cursor = i + 1
        if v["is_dict"] and v["has_cond"]:
            state.compiled.add(v["name"])
        assert state.passed is False, (
            f"passed became True during compile_all at cursor={state.cursor}"
        )
        state.assert_all_invariants(f"compile_phase_cursor={state.cursor}")


# ---------------------------------------------------------------------------
# Dedicated invariant tests
# ---------------------------------------------------------------------------

class TestBatchConsistent:

    def test_vacuous_cursor_eq_1(self):
        s = VerifierState()
        s.cursor = 1
        s.compiled = set()
        assert s.check_batch_consistent()

    def test_vacuous_cursor_eq_2_partial_compiled(self):
        s = VerifierState()
        s.cursor = 2
        s.compiled = {"inv1"}
        assert s.check_batch_consistent()

    def test_satisfied_terminal_state(self):
        s = VerifierState()
        s.cursor = N + 1
        s.compiled = set(EXPECTED_COMPILED)
        assert s.check_batch_consistent()

    def test_violated_when_inv2_absent_after_full_scan(self):
        s = VerifierState()
        s.cursor = N + 1
        s.compiled = {"inv1"}
        assert not s.check_batch_consistent()

    def test_violated_when_inv1_absent_after_full_scan(self):
        s = VerifierState()
        s.cursor = N + 1
        s.compiled = {"inv2"}
        assert not s.check_batch_consistent()

    def test_end_to_end_full_dag(self):
        state = run_compile_assertions(_build_dag_full())
        assert state.check_batch_consistent()

    def test_end_to_end_inv1_only_dag(self):
        verifiers = [{"name": "inv1", "has_cond": True, "is_dict": True}]
        state = run_compile_assertions(_build_dag_inv1_only(), verifiers)
        assert state.check_batch_consistent()


class TestNonDictSkipped:

    def test_empty_compiled(self):
        s = VerifierState()
        assert s.check_non_dict_skipped()

    def test_only_qualifying_names(self):
        s = VerifierState()
        s.compiled = {"inv1", "inv2"}
        assert s.check_non_dict_skipped()

    def test_skip_present_violates(self):
        s = VerifierState()
        s.compiled = {"inv1", "skip"}
        assert not s.check_non_dict_skipped()

    def test_inv1_only_mid_trace(self):
        s = VerifierState()
        s.compiled = {"inv1"}
        assert s.check_non_dict_skipped()

    def test_end_to_end_skip_never_compiled(self):
        state = run_compile_assertions(_build_dag_full())
        assert "skip" not in state.compiled
        assert state.check_non_dict_skipped()

    def test_end_to_end_all_non_dict_dag(self):
        verifiers = [
            {"name": "a", "has_cond": True, "is_dict": False},
            {"name": "b", "has_cond": True, "is_dict": False},
        ]
        dag = RegistryDag()
        for v in verifiers:
            dag.add_node(Node.behavior(v["name"], v["name"], "g", "w", "t"))
        dag.test_artifacts = {"verifiers": verifiers, "expected_compiled": []}
        state = run_compile_assertions(dag, verifiers)
        assert state.check_non_dict_skipped()
        assert state.compiled == set()


class TestStageOrdering:

    @pytest.mark.parametrize("stage", sorted(VALID_STAGES))
    def test_each_valid_stage(self, stage):
        s = VerifierState()
        s.stage = stage
        assert s.check_stage_ordering()

    def test_invalid_stage_rejected(self):
        s = VerifierState()
        s.stage = "ILLEGAL_STAGE"
        assert not s.check_stage_ordering()

    def test_empty_string_rejected(self):
        s = VerifierState()
        s.stage = ""
        assert not s.check_stage_ordering()

    def test_stage_rank_strictly_monotone(self):
        seq = ["idle", "compile_all", "type_check", "discover", "run", "done"]
        for i in range(len(seq) - 1):
            assert STAGE_RANK[seq[i]] < STAGE_RANK[seq[i + 1]]

    def test_full_trace_all_stages_valid(self):
        seen_stages = []

        class _Spy(VerifierState):
            def assert_all_invariants(self_, label=""):
                seen_stages.append(self_.stage)
                super().assert_all_invariants(label)

        spy = _Spy()
        spy.stage = "idle"
        seen_stages.append(spy.stage)
        for stage in ["compile_all", "type_check", "discover", "run", "done"]:
            spy.stage = stage
            seen_stages.append(spy.stage)
            assert spy.check_stage_ordering()

        for st in seen_stages:
            assert st in VALID_STAGES


class TestTypeCheckPassedOnlyAfterCompile:

    def test_passed_false_every_valid_stage(self):
        for stage in VALID_STAGES:
            s = VerifierState()
            s.stage = stage
            s.passed = False
            assert s.check_type_check_passed_only_after_compile()

    def test_passed_true_post_compile_stages_ok(self):
        for stage in ["type_check", "discover", "run", "done"]:
            s = VerifierState()
            s.stage = stage
            s.passed = True
            assert s.check_type_check_passed_only_after_compile()

    def test_passed_true_pre_compile_violated(self):
        for stage in ["idle", "compile_all"]:
            s = VerifierState()
            s.stage = stage
            s.passed = True
            assert not s.check_type_check_passed_only_after_compile()

    def test_topology_compile_all_passed_false(self):
        s = VerifierState()
        s.stage = "compile_all"
        s.passed = False
        assert s.check_type_check_passed_only_after_compile()

    def test_topology_done_passed_true(self):
        s = VerifierState()
        s.stage = "done"
        s.passed = True
        assert s.check_type_check_passed_only_after_compile()

    def test_end_to_end_invariant_at_every_state(self):
        state = run_compile_assertions(_build_dag_full())
        assert state.check_type_check_passed_only_after_compile()


class TestCompiledSubsetValid:

    def test_empty_compiled(self):
        s = VerifierState()
        assert s.check_compiled_subset_valid()

    def test_inv1_and_inv2_valid(self):
        s = VerifierState()
        s.compiled = {"inv1", "inv2"}
        assert s.check_compiled_subset_valid()

    def test_inv3_violates_no_cond(self):
        s = VerifierState()
        s.compiled = {"inv1", "inv3"}
        assert not s.check_compiled_subset_valid()

    def test_skip_violates_not_dict(self):
        s = VerifierState()
        s.compiled = {"inv1", "skip"}
        assert not s.check_compiled_subset_valid()

    def test_unknown_name_violates(self):
        s = VerifierState()
        s.compiled = {"inv1", "phantom"}
        assert not s.check_compiled_subset_valid()

    def test_inv1_only_mid_trace(self):
        s = VerifierState()
        s.compiled = {"inv1"}
        assert s.check_compiled_subset_valid()

    def test_end_to_end_full_dag(self):
        state = run_compile_assertions(_build_dag_full())
        assert state.check_compiled_subset_valid()


class TestTerminalImpliesAllChecked:

    def test_done_passed_true(self):
        s = VerifierState()
        s.stage = "done"
        s.passed = True
        assert s.check_terminal_implies_all_checked()

    def test_done_passed_false_violates(self):
        s = VerifierState()
        s.stage = "done"
        s.passed = False
        assert not s.check_terminal_implies_all_checked()

    def test_non_done_stages_either_passed_value(self):
        for stage in ["idle", "compile_all", "type_check", "discover", "run"]:
            for passed in [True, False]:
                s = VerifierState()
                s.stage = stage
                s.passed = passed
                assert s.check_terminal_implies_all_checked()

    def test_run_passed_true_pre_terminal(self):
        s = VerifierState()
        s.stage = "run"
        s.passed = True
        assert s.check_terminal_implies_all_checked()

    def test_end_to_end_terminal_state(self):
        state = run_compile_assertions(_build_dag_full())
        assert state.stage == "done"
        assert state.passed is True
        assert state.check_terminal_implies_all_checked()


class TestNoDuplicateNames:

    def test_empty_compiled(self):
        s = VerifierState()
        assert s.check_no_duplicate_names()

    def test_two_distinct_names(self):
        s = VerifierState()
        s.compiled = {"inv1", "inv2"}
        assert s.check_no_duplicate_names()

    def test_set_inherently_deduplicates(self):
        s = VerifierState()
        for _ in range(10):
            s.compiled.add("inv1")
        assert len(s.compiled) == 1
        assert s.check_no_duplicate_names()

    def test_adding_same_name_idempotent(self):
        s = VerifierState()
        s.compiled.add("inv1")
        size_before = len(s.compiled)
        s.compiled.add("inv1")
        assert len(s.compiled) == size_before

    def test_end_to_end_no_duplicates(self):
        state = run_compile_assertions(_build_dag_full())
        assert len(state.compiled) == len(set(state.compiled))
        assert len(state.compiled) == len(EXPECTED_COMPILED)

    def test_violation_probe_list_representation(self):
        s = VerifierState()
        s.compiled = ["inv1", "inv1"]
        assert not s.check_no_duplicate_names()


# ---------------------------------------------------------------------------
# TypeScript type-check integration tests
# ---------------------------------------------------------------------------
@requires_tsc
def test_ts_compiled_assertions_pass_tsc():
    ts_source = _generate_ts_source({"inv1", "inv2"})
    rc, output = _run_tsc_no_emit(ts_source)
    assert rc == 0, f"tsc --noEmit failed for compiled={{inv1,inv2}}:\n{output}"


@requires_tsc
def test_ts_empty_compiled_passes_tsc():
    ts_source = _generate_ts_source(set())
    rc, output = _run_tsc_no_emit(ts_source)
    assert rc == 0, f"tsc --noEmit failed for empty compiled:\n{output}"


@requires_tsc
def test_ts_type_check_only_attempted_after_compile_stage_completes():
    dag = _build_dag_full()
    state = run_compile_assertions(dag)
    assert state.stage == "done"
    assert state.passed is True
    ts_source = _generate_ts_source(state.compiled)
    rc, output = _run_tsc_no_emit(ts_source)
    assert rc == 0, f"tsc --noEmit failed:\n{output}"


@requires_tsc
def test_ts_single_compiled_verifier_passes_tsc():
    ts_source = _generate_ts_source({"inv1"})
    rc, output = _run_tsc_no_emit(ts_source)
    assert rc == 0, f"tsc --noEmit failed for compiled={{inv1}}:\n{output}"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------
def test_empty_verifier_list_compiled_is_empty():
    state = run_compile_assertions(_build_dag_empty(), verifiers=[])
    assert state.compiled == set()
    assert state.passed is True
    assert state.stage == "done"
    assert state.cursor == 1


def test_all_non_dict_verifiers_produce_empty_compiled():
    verifiers = [
        {"name": "a", "has_cond": True, "is_dict": False},
        {"name": "b", "has_cond": True, "is_dict": False},
    ]
    dag = RegistryDag()
    for v in verifiers:
        dag.add_node(Node.behavior(v["name"], v["name"], "g", "w", "t"))
    dag.test_artifacts = {"verifiers": verifiers, "expected_compiled": []}
    state = run_compile_assertions(dag, verifiers)
    assert state.compiled == set()
    assert state.passed is True
    assert state.check_non_dict_skipped()


def test_all_missing_cond_verifiers_produce_empty_compiled():
    verifiers = [
        {"name": "x", "has_cond": False, "is_dict": True},
        {"name": "y", "has_cond": False, "is_dict": True},
    ]
    dag = RegistryDag()
    for v in verifiers:
        dag.add_node(Node.behavior(v["name"], v["name"], "g", "w", "t"))
    dag.test_artifacts = {"verifiers": verifiers, "expected_compiled": []}
    state = run_compile_assertions(dag, verifiers)
    assert state.compiled == set()
    assert state.passed is True
    assert state.check_compiled_subset_valid()


def test_single_qualifying_verifier_compiled():
    verifiers = [{"name": "inv1", "has_cond": True, "is_dict": True}]
    state = run_compile_assertions(_build_dag_inv1_only(), verifiers)
    assert state.compiled == {"inv1"}
    assert state.passed is True
    state.assert_all_invariants("single_qualifying")


def test_dag_node_not_found_raises_error():
    dag = RegistryDag()
    with pytest.raises(NodeNotFoundError):
        dag.query_relevant("nonexistent_node_id")


def test_dag_node_count_equals_verifier_count(dag_full):
    assert dag_full.node_count == N


def test_dag_extract_subgraph_includes_inv1(dag_full):
    result = dag_full.extract_subgraph("inv1")
    assert result is not None
    node_ids = {n.id for n in result.nodes}
    assert "inv1" in node_ids


def test_dag_extract_subgraph_inv1_reaches_inv2(dag_full):
    result = dag_full.extract_subgraph("inv1")
    node_ids = {n.id for n in result.nodes}
    assert "inv2" in node_ids


def test_dag_query_impact_on_compiled_node(dag_full):
    result = dag_full.query_impact("inv1")
    assert result is not None


def test_dag_query_relevant_on_compiled_node(dag_full):
    result = dag_full.query_relevant("inv1")
    assert result is not None


def test_diamond_topology_all_qualifying():
    verifiers = [
        {"name": "inv_a", "has_cond": True, "is_dict": True},
        {"name": "inv_b", "has_cond": True, "is_dict": True},
        {"name": "inv_c", "has_cond": True, "is_dict": True},
        {"name": "inv_d", "has_cond": True, "is_dict": True},
    ]
    dag = RegistryDag()
    for v in verifiers:
        dag.add_node(Node.behavior(v["name"], v["name"], "g", "w", "t"))
    dag.add_edge(Edge("inv_a", "inv_b", EdgeType.IMPORTS))
    dag.add_edge(Edge("inv_a", "inv_c", EdgeType.IMPORTS))
    dag.add_edge(Edge("inv_b", "inv_d", EdgeType.IMPORTS))
    dag.add_edge(Edge("inv_c", "inv_d", EdgeType.IMPORTS))
    dag.test_artifacts = {
        "verifiers": verifiers,
        "expected_compiled": sorted(v["name"] for v in verifiers),
    }
    state = run_compile_assertions(dag, verifiers)
    assert state.compiled == {"inv_a", "inv_b", "inv_c", "inv_d"}
    assert state.passed is True
    state.assert_all_invariants("diamond_terminal")


def test_isolated_non_dict_node_never_compiled():
    verifiers = [{"name": "isolated_skip", "has_cond": True, "is_dict": False}]
    dag = RegistryDag()
    dag.add_node(Node.behavior("isolated_skip", "isolated_skip", "g", "w", "t"))
    dag.test_artifacts = {"verifiers": verifiers, "expected_compiled": []}
    state = run_compile_assertions(dag, verifiers)
    assert "isolated_skip" not in state.compiled
    assert state.check_non_dict_skipped()
    assert state.check_compiled_subset_valid()


def test_setting_passed_true_during_compile_all_violates_invariant():
    s = VerifierState()
    s.stage = "compile_all"
    s.passed = True
    assert not s.check_type_check_passed_only_after_compile()


def test_setting_done_with_passed_false_violates_invariant():
    s = VerifierState()
    s.stage = "done"
    s.passed = False
    assert not s.check_terminal_implies_all_checked()


def test_compiled_set_never_shrinks_during_processing():
    state = VerifierState()
    snapshots = []
    state.stage = "compile_all"
    while state.cursor <= state.n:
        v = state.verifiers[state.cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            state.compiled.add(v["name"])
        snapshots.append(frozenset(state.compiled))
        state.cursor += 1

    for i in range(len(snapshots) - 1):
        assert snapshots[i] <= snapshots[i + 1], (
            f"compiled shrank between step {i} and {i + 1}: "
            f"{snapshots[i]} -> {snapshots[i + 1]}"
        )


def test_stage_never_goes_backwards():
    stage_sequence = []

    class _TrackingState(VerifierState):
        def assert_all_invariants(self_, label=""):
            stage_sequence.append(self_.stage)
            super().assert_all_invariants(label)

    state = _TrackingState()
    state.assert_all_invariants("Init")
    state.stage = "compile_all"
    state.assert_all_invariants("CompileAll")
    state.stage = "type_check"
    state.passed = True
    state.assert_all_invariants("TypeCheck")
    state.stage = "discover"
    state.assert_all_invariants("Discover")
    state.stage = "run"
    state.assert_all_invariants("Run")
    state.stage = "done"
    state.assert_all_invariants("Finish")

    for i in range(len(stage_sequence) - 1):
        assert STAGE_RANK[stage_sequence[i]] <= STAGE_RANK[stage_sequence[i + 1]], (
            f"Stage went backwards: {stage_sequence[i]!r} -> {stage_sequence[i + 1]!r}"
        )