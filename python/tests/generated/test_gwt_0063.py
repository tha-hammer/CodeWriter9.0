import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Edge, EdgeType, Node

# ---------------------------------------------------------------------------
# TLA+ constants reproduced verbatim from the verified spec
# ---------------------------------------------------------------------------

VERIFIERS = [
    {"name": "inv1", "has_cond": True,  "is_dict": True},
    {"name": "inv2", "has_cond": True,  "is_dict": True},
    {"name": "inv3", "has_cond": False, "is_dict": True},
    {"name": "skip", "has_cond": True,  "is_dict": False},
]
N = 4
VALID_STAGES = {"idle", "compile_all", "cargo_check", "compile_test", "run", "done"}

# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

def _make_dag(node_ids, edges, artifacts):
    dag = RegistryDag()
    for nid in node_ids:
        dag.add_node(Node.behavior(nid, nid, "given", "when", "then"))
    for src, dst in edges:
        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))
    dag._test_artifacts = artifacts
    return dag


# ---------------------------------------------------------------------------
# compile_assertions: simulation of the TLA+ PlusCal algorithm
# ---------------------------------------------------------------------------

def _compile_assertions(verifiers):
    compiled = set()
    passed = False
    cursor = 1
    stage = "compile_all"

    while cursor <= len(verifiers):
        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
        cursor += 1

    stage = "cargo_check"
    passed = True
    stage = "compile_test"
    stage = "run"
    stage = "done"

    return compiled, stage, passed, cursor


# ---------------------------------------------------------------------------
# Invariant checkers
# ---------------------------------------------------------------------------

def check_batch_consistent(compiled, cursor, verifiers, n):
    if cursor > n:
        for v in verifiers:
            if v["is_dict"] and v["has_cond"]:
                assert v["name"] in compiled, (
                    f"BatchConsistent violated: '{v['name']}' missing from compiled "
                    f"after cursor={cursor} > N={n}"
                )


def check_non_dict_skipped(compiled):
    assert "skip" not in compiled, (
        "NonDictSkipped violated: 'skip' (is_dict=False) must never appear in compiled"
    )


def check_empty_cond_skipped(compiled):
    assert "inv3" not in compiled, (
        "EmptyCondSkipped violated: 'inv3' (has_cond=False) must never appear in compiled"
    )


def check_no_helper_needed():
    pass


def check_stage_ordering(stage):
    assert stage in VALID_STAGES, (
        f"StageOrdering violated: '{stage}' is not a valid stage"
    )


def check_cargo_check_passed_only_after_compile(passed, stage):
    if passed:
        assert stage in {"cargo_check", "compile_test", "run", "done"}, (
            f"CargoCheckPassedOnlyAfterCompile violated: "
            f"passed=True but stage='{stage}'"
        )


def check_compiled_subset_valid(compiled, verifiers):
    valid_names = {v["name"] for v in verifiers if v["is_dict"] and v["has_cond"]}
    for name in compiled:
        assert name in valid_names, (
            f"CompiledSubsetValid violated: '{name}' is not an eligible verifier "
            f"(must have is_dict=True and has_cond=True)"
        )


def check_test_file_valid(stage, passed):
    if stage == "done":
        assert passed, "TestFileValid violated: stage='done' but passed=False"


def check_all_invariants(compiled, cursor, stage, passed, verifiers, n):
    check_batch_consistent(compiled, cursor, verifiers, n)
    check_non_dict_skipped(compiled)
    check_empty_cond_skipped(compiled)
    check_no_helper_needed()
    check_stage_ordering(stage)
    check_cargo_check_passed_only_after_compile(passed, stage)
    check_compiled_subset_valid(compiled, verifiers)
    check_test_file_valid(stage, passed)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def standard_dag():
    return _make_dag(
        node_ids=["inv1", "inv2", "inv3", "skip"],
        edges=[("inv1", "inv2"), ("inv2", "inv3")],
        artifacts=VERIFIERS,
    )


@pytest.fixture
def minimal_two_verifier_dag():
    verifiers = [
        {"name": "inv1", "has_cond": True, "is_dict": True},
        {"name": "inv2", "has_cond": True, "is_dict": True},
    ]
    return _make_dag(["inv1", "inv2"], [("inv1", "inv2")], verifiers)


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

class TestTrace1:

    def test_full_pipeline_step_by_step(self, standard_dag):
        dag = standard_dag
        verifiers = dag._test_artifacts
        n = len(verifiers)

        compiled, cursor, stage, passed = set(), 1, "idle", False
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        stage = "compile_all"
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
        assert compiled == {"inv1"}
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        cursor += 1
        assert cursor == 2
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
        assert compiled == {"inv1", "inv2"}
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        cursor += 1
        assert cursor == 3
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
        assert compiled == {"inv1", "inv2"}
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        cursor += 1
        assert cursor == 4
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
        assert compiled == {"inv1", "inv2"}
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        cursor += 1
        assert cursor == 5
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        stage = "cargo_check"
        passed = True
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        stage = "compile_test"
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        stage = "run"
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        stage = "done"
        check_all_invariants(compiled, cursor, stage, passed, verifiers, n)

        assert compiled == {"inv1", "inv2"}
        assert passed is True
        assert stage == "done"
        assert cursor == 5


# ---------------------------------------------------------------------------
# Traces 2-10
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(2, 11))
def test_trace_parametrized(trace_id, standard_dag):
    dag = standard_dag
    verifiers = dag._test_artifacts
    n = len(verifiers)

    compiled, stage, passed, cursor = _compile_assertions(verifiers)

    assert compiled == {"inv1", "inv2"}, (
        f"Trace {trace_id}: compiled set wrong: {compiled}"
    )
    assert passed is True, f"Trace {trace_id}: passed must be True at done"
    assert stage == "done",  f"Trace {trace_id}: final stage must be 'done'"
    assert cursor == n + 1,  f"Trace {trace_id}: cursor must be N+1={n+1}"

    check_all_invariants(compiled, cursor, stage, passed, verifiers, n)


# ---------------------------------------------------------------------------
# Dedicated invariant tests
# ---------------------------------------------------------------------------

class TestBatchConsistent:

    def test_standard_topology_after_full_loop(self, standard_dag):
        verifiers = standard_dag._test_artifacts
        n = len(verifiers)
        compiled, _, _, cursor = _compile_assertions(verifiers)
        assert cursor > n
        check_batch_consistent(compiled, cursor, verifiers, n)

    def test_mid_loop_not_triggered(self):
        check_batch_consistent(set(), 1, VERIFIERS, N)
        check_batch_consistent(set(), 3, VERIFIERS, N)

    def test_second_topology_all_eligible(self):
        verifiers2 = [
            {"name": "a", "has_cond": True, "is_dict": True},
            {"name": "b", "has_cond": True, "is_dict": True},
        ]
        compiled, _, _, cursor = _compile_assertions(verifiers2)
        check_batch_consistent(compiled, cursor, verifiers2, len(verifiers2))
        assert compiled == {"a", "b"}

    def test_violation_detected_when_eligible_entry_missing(self):
        verifiers = [{"name": "x", "has_cond": True, "is_dict": True}]
        with pytest.raises(AssertionError, match="BatchConsistent"):
            check_batch_consistent(set(), 2, verifiers, 1)


class TestNonDictSkipped:

    def test_standard_topology(self, standard_dag):
        compiled, _, _, _ = _compile_assertions(standard_dag._test_artifacts)
        check_non_dict_skipped(compiled)
        assert "skip" not in compiled

    def test_all_non_dict_topology(self):
        verifiers = [
            {"name": "x", "has_cond": True, "is_dict": False},
            {"name": "y", "has_cond": True, "is_dict": False},
        ]
        compiled, _, _, _ = _compile_assertions(verifiers)
        assert compiled == set()
        check_non_dict_skipped(compiled)

    def test_invariant_at_every_intermediate_step(self):
        compiled = set()
        for v in VERIFIERS:
            if v["is_dict"] and v["has_cond"]:
                compiled.add(v["name"])
            check_non_dict_skipped(compiled)

    def test_violation_detected(self):
        with pytest.raises(AssertionError, match="NonDictSkipped"):
            check_non_dict_skipped({"skip"})


class TestEmptyCondSkipped:

    def test_standard_topology(self, standard_dag):
        compiled, _, _, _ = _compile_assertions(standard_dag._test_artifacts)
        check_empty_cond_skipped(compiled)
        assert "inv3" not in compiled

    def test_all_no_cond_topology(self):
        verifiers = [
            {"name": "p", "has_cond": False, "is_dict": True},
            {"name": "q", "has_cond": False, "is_dict": True},
        ]
        compiled, _, _, _ = _compile_assertions(verifiers)
        assert compiled == set()
        check_empty_cond_skipped(compiled)

    def test_invariant_at_every_intermediate_step(self):
        compiled = set()
        for v in VERIFIERS:
            if v["is_dict"] and v["has_cond"]:
                compiled.add(v["name"])
            check_empty_cond_skipped(compiled)

    def test_violation_detected(self):
        with pytest.raises(AssertionError, match="EmptyCondSkipped"):
            check_empty_cond_skipped({"inv3"})


class TestNoHelperNeeded:

    def test_no_helper_needed_standard_topology(self, standard_dag):
        check_no_helper_needed()

    def test_no_helper_needed_minimal_topology(self, minimal_two_verifier_dag):
        check_no_helper_needed()

    def test_no_helper_needed_always_passes(self):
        for _ in range(5):
            check_no_helper_needed()


class TestStageOrdering:

    def test_all_valid_stages(self, standard_dag):
        for s in VALID_STAGES:
            check_stage_ordering(s)

    def test_stage_sequence_during_trace(self, standard_dag):
        expected_sequence = (
            ["idle"]
            + ["compile_all"] * 14
            + ["cargo_check", "compile_test", "run", "done"]
        )
        assert len(expected_sequence) == 19
        for s in expected_sequence:
            check_stage_ordering(s)

    def test_invalid_stage_raises(self):
        with pytest.raises(AssertionError, match="StageOrdering"):
            check_stage_ordering("unknown_stage")

    def test_empty_string_stage_raises(self):
        with pytest.raises(AssertionError, match="StageOrdering"):
            check_stage_ordering("")

    def test_second_topology_stage_sequence(self, minimal_two_verifier_dag):
        compiled, stage, passed, cursor = _compile_assertions(minimal_two_verifier_dag._test_artifacts)
        check_stage_ordering(stage)
        assert stage == "done"


class TestCargoCheckPassedOnlyAfterCompile:

    def test_passed_false_before_cargo_check(self, standard_dag):
        check_cargo_check_passed_only_after_compile(False, "idle")
        check_cargo_check_passed_only_after_compile(False, "compile_all")

    def test_passed_true_only_in_late_stages(self):
        for stage in ("cargo_check", "compile_test", "run", "done"):
            check_cargo_check_passed_only_after_compile(True, stage)

    def test_passed_true_in_idle_raises(self):
        with pytest.raises(AssertionError, match="CargoCheckPassedOnlyAfterCompile"):
            check_cargo_check_passed_only_after_compile(True, "idle")

    def test_passed_true_in_compile_all_raises(self):
        with pytest.raises(AssertionError, match="CargoCheckPassedOnlyAfterCompile"):
            check_cargo_check_passed_only_after_compile(True, "compile_all")

    def test_invariant_across_full_trace(self, standard_dag):
        verifiers = standard_dag._test_artifacts
        compiled = set()
        cursor = 1
        passed = False

        check_cargo_check_passed_only_after_compile(passed, "idle")
        for v in verifiers:
            if v["is_dict"] and v["has_cond"]:
                compiled.add(v["name"])
            cursor += 1
            check_cargo_check_passed_only_after_compile(passed, "compile_all")
        passed = True
        check_cargo_check_passed_only_after_compile(passed, "cargo_check")
        for stage in ("compile_test", "run", "done"):
            check_cargo_check_passed_only_after_compile(passed, stage)

    def test_second_topology(self, minimal_two_verifier_dag):
        compiled, stage, passed, cursor = _compile_assertions(minimal_two_verifier_dag._test_artifacts)
        check_cargo_check_passed_only_after_compile(passed, stage)


class TestCompiledSubsetValid:

    def test_standard_topology_subset_valid(self, standard_dag):
        verifiers = standard_dag._test_artifacts
        compiled, _, _, _ = _compile_assertions(verifiers)
        check_compiled_subset_valid(compiled, verifiers)
        assert compiled == {"inv1", "inv2"}

    def test_only_eligible_entries_compiled(self, standard_dag):
        verifiers = standard_dag._test_artifacts
        compiled, _, _, _ = _compile_assertions(verifiers)
        assert "inv3" not in compiled
        assert "skip" not in compiled

    def test_second_topology_mixed_eligibility(self):
        verifiers2 = [
            {"name": "a", "has_cond": True,  "is_dict": True},
            {"name": "b", "has_cond": False, "is_dict": True},
            {"name": "c", "has_cond": True,  "is_dict": False},
        ]
        compiled, _, _, _ = _compile_assertions(verifiers2)
        assert compiled == {"a"}
        check_compiled_subset_valid(compiled, verifiers2)

    def test_violation_detected_when_ineligible_entry_present(self):
        with pytest.raises(AssertionError, match="CompiledSubsetValid"):
            check_compiled_subset_valid({"inv3"}, VERIFIERS)

    def test_violation_detected_skip_in_compiled(self):
        with pytest.raises(AssertionError, match="CompiledSubsetValid"):
            check_compiled_subset_valid({"skip"}, VERIFIERS)


class TestTestFileValid:

    def test_done_implies_passed_standard_topology(self, standard_dag):
        verifiers = standard_dag._test_artifacts
        compiled, stage, passed, cursor = _compile_assertions(verifiers)
        assert stage == "done"
        check_test_file_valid(stage, passed)

    def test_non_done_stages_do_not_require_passed(self):
        for stage in ("idle", "compile_all", "cargo_check", "compile_test", "run"):
            check_test_file_valid(stage, False)

    def test_done_with_passed_false_raises(self):
        with pytest.raises(AssertionError, match="TestFileValid"):
            check_test_file_valid("done", False)

    def test_second_topology_final_state(self, minimal_two_verifier_dag):
        compiled, stage, passed, cursor = _compile_assertions(minimal_two_verifier_dag._test_artifacts)
        check_test_file_valid(stage, passed)
        assert stage == "done" and passed is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_verifiers_list(self):
        dag = _make_dag([], [], [])
        verifiers = dag._test_artifacts
        compiled, stage, passed, cursor = _compile_assertions(verifiers)
        assert compiled == set()
        assert stage == "done"
        assert passed is True
        assert cursor == 1
        check_all_invariants(compiled, cursor, stage, passed, verifiers, 0)

    def test_all_non_dict_verifiers(self):
        verifiers = [
            {"name": "a", "has_cond": True, "is_dict": False},
            {"name": "b", "has_cond": True, "is_dict": False},
        ]
        dag = _make_dag(["a", "b"], [], verifiers)
        compiled, stage, passed, cursor = _compile_assertions(dag._test_artifacts)
        assert compiled == set()
        check_non_dict_skipped(compiled)
        check_all_invariants(compiled, cursor, stage, passed, verifiers, len(verifiers))

    def test_all_no_cond_verifiers(self):
        verifiers = [
            {"name": "p", "has_cond": False, "is_dict": True},
            {"name": "q", "has_cond": False, "is_dict": True},
        ]
        dag = _make_dag(["p", "q"], [], verifiers)
        compiled, stage, passed, cursor = _compile_assertions(dag._test_artifacts)
        assert compiled == set()
        check_empty_cond_skipped(compiled)
        check_all_invariants(compiled, cursor, stage, passed, verifiers, len(verifiers))

    def test_single_eligible_verifier(self):
        verifiers = [{"name": "only", "has_cond": True, "is_dict": True}]
        dag = _make_dag(["only"], [], verifiers)
        compiled, stage, passed, cursor = _compile_assertions(dag._test_artifacts)
        assert compiled == {"only"}
        assert passed is True
        assert stage == "done"
        check_all_invariants(compiled, cursor, stage, passed, verifiers, len(verifiers))

    def test_isolated_node_in_dag(self):
        dag = _make_dag(["isolated"], [], VERIFIERS)
        assert dag.node_count >= 1
        compiled, stage, passed, cursor = _compile_assertions(dag._test_artifacts)
        assert compiled == {"inv1", "inv2"}
        check_all_invariants(compiled, cursor, stage, passed, VERIFIERS, N)

    def test_diamond_topology_dag(self):
        dag = _make_dag(
            ["A", "B", "C", "D"],
            [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
            VERIFIERS,
        )
        assert dag.node_count == 4
        assert dag.edge_count == 4
        compiled, stage, passed, cursor = _compile_assertions(dag._test_artifacts)
        assert compiled == {"inv1", "inv2"}
        check_all_invariants(compiled, cursor, stage, passed, VERIFIERS, N)

    def test_node_not_found_error_on_query(self):
        dag = _make_dag(["inv1", "inv2"], [], VERIFIERS)
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("nonexistent_node_xyz")

    def test_empty_dag_metrics(self):
        dag = RegistryDag()
        assert dag.node_count == 0
        assert dag.edge_count == 0

    def test_passed_remains_false_through_compile_all(self):
        compiled = set()
        cursor = 1
        passed = False

        check_cargo_check_passed_only_after_compile(passed, "idle")
        for v in VERIFIERS:
            if v["is_dict"] and v["has_cond"]:
                compiled.add(v["name"])
            cursor += 1
            check_cargo_check_passed_only_after_compile(passed, "compile_all")

        passed = True
        check_cargo_check_passed_only_after_compile(passed, "cargo_check")

    def test_stage_vocabulary_complete_and_invalid_rejected(self):
        for s in ["idle", "compile_all", "cargo_check", "compile_test", "run", "done"]:
            check_stage_ordering(s)
        with pytest.raises(AssertionError, match="StageOrdering"):
            check_stage_ordering("pre_compile")

    def test_batch_consistent_after_mixed_eligibility_loop(self):
        verifiers = [
            {"name": "e1", "has_cond": True,  "is_dict": True},
            {"name": "e2", "has_cond": False, "is_dict": True},
            {"name": "e3", "has_cond": True,  "is_dict": False},
            {"name": "e4", "has_cond": True,  "is_dict": True},
        ]
        compiled, _, _, cursor = _compile_assertions(verifiers)
        assert compiled == {"e1", "e4"}
        check_batch_consistent(compiled, cursor, verifiers, len(verifiers))
        check_compiled_subset_valid(compiled, verifiers)