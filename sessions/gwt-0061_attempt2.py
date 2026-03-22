"""
pytest tests for go_profile_file_validity — generated from TLC-verified traces.

Covers:
  - All 10 TLC traces (structurally identical; parametrised)
  - All 6 invariants: BatchConsistent, HelperIncluded, StageOrdering,
    VetPassedWhenDone, CompiledOnlyEligible, HelperNeededIffQuantUsed
  - Go-tool validation: go vet ./... and go test -list . ./...
  - Edge cases: empty DAG, isolated node, diamond pattern, no-quant verifiers,
    ineligible-only verifiers, cursor-at-boundary, missing artifacts
"""

from __future__ import annotations

import os
import subprocess
import tempfile

import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node

# ---------------------------------------------------------------------------
# Fixed verifier sequence from TLA+ spec (Verifiers[1..4])
# ---------------------------------------------------------------------------
VERIFIERS = [
    {"name": "inv1", "has_cond": True,  "is_dict": True,  "uses_quant": False},
    {"name": "inv2", "has_cond": True,  "is_dict": True,  "uses_quant": True},
    {"name": "inv3", "has_cond": False, "is_dict": True,  "uses_quant": False},
    {"name": "skip", "has_cond": True,  "is_dict": False, "uses_quant": False},
]
N = 4  # len(VERIFIERS)


# ---------------------------------------------------------------------------
# Algorithm: direct Python translation of the TLA+ PlusCal algorithm
# ---------------------------------------------------------------------------

def compile_assertions(verifiers: list[dict]) -> tuple[frozenset[str], bool]:
    compiled: set[str] = set()
    helper_needed = False
    for v in verifiers:
        if v["is_dict"] and v["has_cond"]:
            compiled.add(v["name"])
            if v["uses_quant"]:
                helper_needed = True
    return frozenset(compiled), helper_needed


# ---------------------------------------------------------------------------
# Invariant checkers
# ---------------------------------------------------------------------------

def check_batch_consistent(
    compiled: frozenset[str],
    cursor: int,
    verifiers: list[dict],
    n: int,
) -> None:
    if cursor > n:
        for v in verifiers:
            if v["is_dict"] and v["has_cond"]:
                assert v["name"] in compiled, (
                    f"BatchConsistent violated: eligible verifier {v['name']!r} "
                    f"missing from compiled={compiled}"
                )


def check_helper_included(
    helper_needed: bool,
    stage: str,
    passed: bool,
) -> None:
    if helper_needed and stage in {"vet", "list", "run", "done"}:
        assert passed is True, (
            f"HelperIncluded violated: helper_needed=True, stage={stage!r}, "
            f"passed={passed}"
        )


def check_stage_ordering(stage: str) -> None:
    valid = {"idle", "compile_all", "vet", "list", "run", "done"}
    assert stage in valid, (
        f"StageOrdering violated: stage={stage!r} not in {valid}"
    )


def check_vet_passed_when_done(stage: str, passed: bool) -> None:
    if stage == "done":
        assert passed is True, (
            f"VetPassedWhenDone violated: stage='done' but passed={passed}"
        )


def check_compiled_only_eligible(
    compiled: frozenset[str],
    verifiers: list[dict],
) -> None:
    eligible = frozenset(
        v["name"] for v in verifiers if v["is_dict"] and v["has_cond"]
    )
    for name in compiled:
        assert name in eligible, (
            f"CompiledOnlyEligible violated: {name!r} is not an eligible verifier "
            f"(eligible={eligible})"
        )


def check_helper_needed_iff_quant_used(
    helper_needed: bool,
    cursor: int,
    verifiers: list[dict],
    n: int,
) -> None:
    if cursor > n:
        quant_used = any(
            v["is_dict"] and v["has_cond"] and v["uses_quant"] for v in verifiers
        )
        assert helper_needed == quant_used, (
            f"HelperNeededIffQuantUsed violated: helper_needed={helper_needed} but "
            f"quant_used={quant_used}"
        )


def check_all_invariants(
    compiled: frozenset[str],
    cursor: int,
    stage: str,
    passed: bool,
    helper_needed: bool,
    verifiers: list[dict],
    n: int,
) -> None:
    check_stage_ordering(stage)
    check_vet_passed_when_done(stage, passed)
    check_compiled_only_eligible(compiled, verifiers)
    check_batch_consistent(compiled, cursor, verifiers, n)
    check_helper_included(helper_needed, stage, passed)
    check_helper_needed_iff_quant_used(helper_needed, cursor, verifiers, n)


# ---------------------------------------------------------------------------
# Go test-file writer
# ---------------------------------------------------------------------------

def _write_go_test_package(
    tmpdir: str,
    compiled_names: frozenset[str],
    helper_needed: bool,
) -> None:
    with open(os.path.join(tmpdir, "go.mod"), "w") as fh:
        fh.write("module example.com/verifiertest\n\ngo 1.21\n")

    needs_testing_import = bool(compiled_names) or helper_needed

    lines: list[str] = [
        "package verifiertest_test",
        "",
    ]

    if needs_testing_import:
        lines += ['import "testing"', ""]

    if helper_needed:
        lines += [
            "func helperExists(t *testing.T, names []string, pred func(string) bool) bool {",
            "\tt.Helper()",
            "\tfor _, n := range names {",
            "\t\tif pred(n) {",
            "\t\t\treturn true",
            "\t\t}",
            "\t}",
            "\treturn false",
            "}",
            "",
        ]

    for name in sorted(compiled_names):
        func_name = "Test_" + name[0].upper() + name[1:]
        lines += [
            f"func {func_name}(t *testing.T) {{",
            f'\tt.Log("assertion {name} verified")',
            "}",
            "",
        ]

    with open(os.path.join(tmpdir, "assertions_test.go"), "w") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def standard_dag() -> RegistryDag:
    dag = RegistryDag()
    for v in VERIFIERS:
        dag.add_node(
            Node.resource(
                v["name"],
                v["name"],
                f"verifier {v['name']}",
                has_cond=v["has_cond"],
                is_dict=v["is_dict"],
                uses_quant=v["uses_quant"],
            )
        )
    dag.test_artifacts = list(VERIFIERS)
    return dag


@pytest.fixture
def no_quant_dag() -> RegistryDag:
    verifiers = [
        {"name": "c1", "has_cond": True,  "is_dict": True,  "uses_quant": False},
        {"name": "c2", "has_cond": True,  "is_dict": True,  "uses_quant": False},
        {"name": "nx", "has_cond": False, "is_dict": True,  "uses_quant": False},
    ]
    dag = RegistryDag()
    for v in verifiers:
        dag.add_node(
            Node.resource(
                v["name"],
                v["name"],
                has_cond=v["has_cond"],
                is_dict=v["is_dict"],
                uses_quant=v["uses_quant"],
            )
        )
    dag.test_artifacts = verifiers
    return dag


# ---------------------------------------------------------------------------
# Go-tool availability guard
# ---------------------------------------------------------------------------

def _go_available() -> bool:
    try:
        r = subprocess.run(["go", "version"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


requires_go = pytest.mark.skipif(
    not _go_available(), reason="Go toolchain not available"
)


# ===========================================================================
# Traces 1-10
# ===========================================================================

@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_full_pipeline(trace_id: int, standard_dag: RegistryDag) -> None:
    verifiers: list[dict] = standard_dag.test_artifacts

    compiled: frozenset[str] = frozenset()
    passed = False
    helper_needed = False
    cursor = 1
    stage = "idle"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "compile_all"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    for _ in range(N):
        assert cursor <= N
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled = compiled | frozenset([v["name"]])
            if v["uses_quant"]:
                helper_needed = True
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

        cursor += 1
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    assert cursor == 5
    assert cursor > N

    stage = "vet"
    passed = True
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "list"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "run"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "done"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    assert compiled == frozenset({"inv1", "inv2"}), (
        f"Trace {trace_id}: expected compiled={{'inv1','inv2'}}, got {set(compiled)}"
    )
    assert passed is True,         f"Trace {trace_id}: expected passed=True"
    assert helper_needed is True,  f"Trace {trace_id}: expected helper_needed=True"
    assert cursor == 5,            f"Trace {trace_id}: expected cursor=5"
    assert stage == "done",        f"Trace {trace_id}: expected stage='done'"

    assert "inv3" not in compiled, f"Trace {trace_id}: inv3 must not appear in compiled"
    assert "skip" not in compiled, f"Trace {trace_id}: skip must not appear in compiled"

    quant_eligible = [
        v for v in verifiers if v["is_dict"] and v["has_cond"] and v["uses_quant"]
    ]
    assert len(quant_eligible) == 1 and quant_eligible[0]["name"] == "inv2"


# ===========================================================================
# Invariant: BatchConsistent
# ===========================================================================

class TestBatchConsistent:
    def test_vacuously_true_before_loop_ends(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        for cursor in range(1, N + 1):
            check_batch_consistent(frozenset(), cursor, verifiers, N)

    def test_after_loop_all_eligible_present(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        compiled, _ = compile_assertions(verifiers)
        check_batch_consistent(compiled, N + 1, verifiers, N)

    def test_partial_compile_at_cursor_boundary(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        check_batch_consistent(frozenset({"inv1"}), N, verifiers, N)

    def test_missing_eligible_after_loop_raises(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        with pytest.raises(AssertionError, match="BatchConsistent"):
            check_batch_consistent(frozenset({"inv1"}), N + 1, verifiers, N)

    def test_no_quant_dag_after_loop(self, no_quant_dag: RegistryDag) -> None:
        verifiers = no_quant_dag.test_artifacts
        n = len(verifiers)
        compiled, _ = compile_assertions(verifiers)
        check_batch_consistent(compiled, n + 1, verifiers, n)


# ===========================================================================
# Invariant: HelperIncluded
# ===========================================================================

class TestHelperIncluded:
    def test_helper_false_unconstrained(self, standard_dag: RegistryDag) -> None:
        for stage in ["idle", "compile_all", "vet", "list", "run", "done"]:
            check_helper_included(False, stage, False)
            check_helper_included(False, stage, True)

    def test_helper_true_compile_all_no_constraint(self) -> None:
        check_helper_included(True, "compile_all", False)
        check_helper_included(True, "compile_all", True)

    def test_helper_true_vet_requires_passed(self) -> None:
        check_helper_included(True, "vet", True)

    def test_helper_true_done_requires_passed(self) -> None:
        check_helper_included(True, "done", True)

    @pytest.mark.parametrize("stage", ["vet", "list", "run", "done"])
    def test_helper_true_constrained_stage_passed_false_raises(
        self, stage: str
    ) -> None:
        with pytest.raises(AssertionError, match="HelperIncluded"):
            check_helper_included(True, stage, False)

    def test_full_trace_helper_included_at_all_stages(
        self, standard_dag: RegistryDag
    ) -> None:
        verifiers = standard_dag.test_artifacts
        _, helper_needed = compile_assertions(verifiers)
        assert helper_needed is True

        timeline = [
            ("idle",         False, False),
            ("compile_all",  False, True),
            ("vet",          True,  True),
            ("list",         True,  True),
            ("run",          True,  True),
            ("done",         True,  True),
        ]
        for stage, passed, hn in timeline:
            check_helper_included(hn, stage, passed)

    def test_no_quant_dag_helper_included(self, no_quant_dag: RegistryDag) -> None:
        _, helper_needed = compile_assertions(no_quant_dag.test_artifacts)
        assert helper_needed is False
        for stage in ["vet", "list", "run", "done"]:
            check_helper_included(helper_needed, stage, False)


# ===========================================================================
# Invariant: StageOrdering
# ===========================================================================

class TestStageOrdering:
    @pytest.mark.parametrize(
        "stage",
        ["idle", "compile_all", "vet", "list", "run", "done"],
    )
    def test_each_valid_stage_accepted(self, stage: str) -> None:
        check_stage_ordering(stage)

    @pytest.mark.parametrize("bad", ["", "start", "DONE", "compile", "vetted"])
    def test_invalid_stage_raises(self, bad: str) -> None:
        with pytest.raises(AssertionError, match="StageOrdering"):
            check_stage_ordering(bad)

    def test_full_trace_stage_sequence(self, standard_dag: RegistryDag) -> None:
        trace_stages = [
            "idle",
            "compile_all",
            "vet",
            "list",
            "run",
            "done",
        ]
        for s in trace_stages:
            check_stage_ordering(s)


# ===========================================================================
# Invariant: VetPassedWhenDone
# ===========================================================================

class TestVetPassedWhenDone:
    def test_done_with_passed_true_ok(self) -> None:
        check_vet_passed_when_done("done", True)

    def test_done_with_passed_false_raises(self) -> None:
        with pytest.raises(AssertionError, match="VetPassedWhenDone"):
            check_vet_passed_when_done("done", False)

    @pytest.mark.parametrize(
        "stage", ["idle", "compile_all", "vet", "list", "run"]
    )
    def test_non_done_stages_unconstrained(self, stage: str) -> None:
        check_vet_passed_when_done(stage, False)
        check_vet_passed_when_done(stage, True)

    def test_trace_state_sequence(self, standard_dag: RegistryDag) -> None:
        state_pairs = [
            ("idle",        False),
            ("compile_all", False),
            ("compile_all", False),
            ("vet",         True),
            ("list",        True),
            ("run",         True),
            ("done",        True),
        ]
        for stage, passed in state_pairs:
            check_vet_passed_when_done(stage, passed)

    def test_no_quant_dag_done_state(self, no_quant_dag: RegistryDag) -> None:
        check_vet_passed_when_done("done", True)


# ===========================================================================
# Invariant: CompiledOnlyEligible
# ===========================================================================

class TestCompiledOnlyEligible:
    def test_empty_compiled_trivially_ok(self, standard_dag: RegistryDag) -> None:
        check_compiled_only_eligible(frozenset(), standard_dag.test_artifacts)

    def test_inv1_inv2_eligible(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        check_compiled_only_eligible(frozenset({"inv1", "inv2"}), verifiers)

    def test_inv3_not_eligible_raises(self, standard_dag: RegistryDag) -> None:
        with pytest.raises(AssertionError, match="CompiledOnlyEligible"):
            check_compiled_only_eligible(
                frozenset({"inv1", "inv3"}), standard_dag.test_artifacts
            )

    def test_skip_not_eligible_raises(self, standard_dag: RegistryDag) -> None:
        with pytest.raises(AssertionError, match="CompiledOnlyEligible"):
            check_compiled_only_eligible(
                frozenset({"skip"}), standard_dag.test_artifacts
            )

    def test_compile_assertions_produces_only_eligible(
        self, standard_dag: RegistryDag
    ) -> None:
        verifiers = standard_dag.test_artifacts
        compiled, _ = compile_assertions(verifiers)
        check_compiled_only_eligible(compiled, verifiers)

    def test_no_quant_dag_compile_only_eligible(
        self, no_quant_dag: RegistryDag
    ) -> None:
        verifiers = no_quant_dag.test_artifacts
        compiled, _ = compile_assertions(verifiers)
        check_compiled_only_eligible(compiled, verifiers)


# ===========================================================================
# Invariant: HelperNeededIffQuantUsed
# ===========================================================================

class TestHelperNeededIffQuantUsed:
    def test_vacuous_before_loop_completes(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        for cursor in range(1, N + 1):
            check_helper_needed_iff_quant_used(False, cursor, verifiers, N)
            check_helper_needed_iff_quant_used(True,  cursor, verifiers, N)

    def test_standard_dag_after_loop(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        _, helper_needed = compile_assertions(verifiers)
        assert helper_needed is True
        check_helper_needed_iff_quant_used(helper_needed, N + 1, verifiers, N)

    def test_no_quant_dag_after_loop(self, no_quant_dag: RegistryDag) -> None:
        verifiers = no_quant_dag.test_artifacts
        n = len(verifiers)
        _, helper_needed = compile_assertions(verifiers)
        assert helper_needed is False
        check_helper_needed_iff_quant_used(helper_needed, n + 1, verifiers, n)

    def test_helper_needed_false_but_quant_used_raises(
        self, standard_dag: RegistryDag
    ) -> None:
        verifiers = standard_dag.test_artifacts
        with pytest.raises(AssertionError, match="HelperNeededIffQuantUsed"):
            check_helper_needed_iff_quant_used(False, N + 1, verifiers, N)

    def test_helper_needed_true_but_no_quant_raises(
        self, no_quant_dag: RegistryDag
    ) -> None:
        verifiers = no_quant_dag.test_artifacts
        n = len(verifiers)
        with pytest.raises(AssertionError, match="HelperNeededIffQuantUsed"):
            check_helper_needed_iff_quant_used(True, n + 1, verifiers, n)


# ===========================================================================
# Go-tool tests
# ===========================================================================

@requires_go
def test_go_vet_passes_compiled_assertions(standard_dag: RegistryDag) -> None:
    verifiers = standard_dag.test_artifacts
    compiled, helper_needed = compile_assertions(verifiers)

    assert compiled == frozenset({"inv1", "inv2"})
    assert helper_needed is True

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_go_test_package(tmpdir, compiled, helper_needed)
        result = subprocess.run(
            ["go", "vet", "./..."],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"go vet ./... failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@requires_go
def test_go_test_list_enumerates_compiled_functions(
    standard_dag: RegistryDag,
) -> None:
    verifiers = standard_dag.test_artifacts
    compiled, helper_needed = compile_assertions(verifiers)

    assert compiled == frozenset({"inv1", "inv2"})

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_go_test_package(tmpdir, compiled, helper_needed)
        result = subprocess.run(
            ["go", "test", "-list", ".", "./..."],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"go test -list failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        for name in compiled:
            func_name = "Test_" + name[0].upper() + name[1:]
            assert func_name in result.stdout, (
                f"Expected {func_name!r} in 'go test -list' output:\n{result.stdout}"
            )


@requires_go
def test_go_full_pipeline_matches_all_trace_final_states(
    standard_dag: RegistryDag,
) -> None:
    verifiers: list[dict] = standard_dag.test_artifacts

    compiled: frozenset[str] = frozenset()
    passed = False
    helper_needed = False
    cursor = 1
    stage = "idle"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "compile_all"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    while cursor <= N:
        v = verifiers[cursor - 1]
        if v["is_dict"] and v["has_cond"]:
            compiled = compiled | frozenset([v["name"]])
            if v["uses_quant"]:
                helper_needed = True
        cursor += 1
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    assert cursor == N + 1

    with tempfile.TemporaryDirectory() as tmpdir:
        _write_go_test_package(tmpdir, compiled, helper_needed)

        vet = subprocess.run(
            ["go", "vet", "./..."],
            cwd=tmpdir, capture_output=True, text=True, timeout=60,
        )
        assert vet.returncode == 0, (
            f"go vet failed\nstdout:{vet.stdout}\nstderr:{vet.stderr}"
        )
        stage = "vet"
        passed = True
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

        lst = subprocess.run(
            ["go", "test", "-list", ".", "./..."],
            cwd=tmpdir, capture_output=True, text=True, timeout=60,
        )
        assert lst.returncode == 0, (
            f"go test -list failed\nstdout:{lst.stdout}\nstderr:{lst.stderr}"
        )
        stage = "list"
        check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "run"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    stage = "done"
    check_all_invariants(compiled, cursor, stage, passed, helper_needed, verifiers, N)

    assert compiled == frozenset({"inv1", "inv2"})
    assert passed is True
    assert helper_needed is True
    assert cursor == 5
    assert stage == "done"


@requires_go
def test_go_vet_empty_compiled_set() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_go_test_package(tmpdir, frozenset(), False)
        result = subprocess.run(
            ["go", "vet", "./..."],
            cwd=tmpdir, capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, (
            f"go vet failed on empty compiled\nstderr:{result.stderr}"
        )


@requires_go
def test_go_vet_no_helper_needed() -> None:
    verifiers_no_quant = [
        {"name": "onlyA", "has_cond": True, "is_dict": True, "uses_quant": False},
    ]
    compiled, helper_needed = compile_assertions(verifiers_no_quant)
    assert helper_needed is False
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_go_test_package(tmpdir, compiled, helper_needed)
        result = subprocess.run(
            ["go", "vet", "./..."],
            cwd=tmpdir, capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_empty_dag(self) -> None:
        dag = RegistryDag()
        assert dag.node_count == 0
        assert dag.edge_count == 0

    def test_isolated_node(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("iso", "iso", "isolated verifier"))
        assert dag.node_count == 1
        assert dag.edge_count == 0

    def test_diamond_pattern(self) -> None:
        dag = RegistryDag()
        for nid in ("a", "b", "c", "d"):
            dag.add_node(Node.resource(nid, nid))
        dag.add_edge(Edge("a", "b", EdgeType.IMPORTS))
        dag.add_edge(Edge("a", "c", EdgeType.IMPORTS))
        dag.add_edge(Edge("b", "d", EdgeType.IMPORTS))
        dag.add_edge(Edge("c", "d", EdgeType.IMPORTS))
        assert dag.node_count == 4
        assert dag.edge_count == 4

    def test_partial_artifacts_in_dag(self) -> None:
        dag = RegistryDag()
        for v in VERIFIERS[:2]:
            dag.add_node(Node.resource(v["name"], v["name"]))
        dag.test_artifacts = VERIFIERS[:2]
        assert dag.node_count == 2

    def test_empty_verifiers_all_invariants(self) -> None:
        verifiers: list[dict] = []
        n = 0
        compiled, helper_needed = compile_assertions(verifiers)
        assert compiled == frozenset()
        assert helper_needed is False
        cursor = n + 1
        check_all_invariants(compiled, cursor, "done", True, helper_needed, verifiers, n)

    def test_all_ineligible_verifiers(self) -> None:
        verifiers = [
            {"name": "a", "has_cond": False, "is_dict": True,  "uses_quant": False},
            {"name": "b", "has_cond": True,  "is_dict": False, "uses_quant": False},
        ]
        n = len(verifiers)
        compiled, helper_needed = compile_assertions(verifiers)
        assert compiled == frozenset()
        assert helper_needed is False
        check_all_invariants(compiled, n + 1, "done", True, helper_needed, verifiers, n)

    def test_single_eligible_no_quant(self) -> None:
        verifiers = [
            {"name": "only", "has_cond": True, "is_dict": True, "uses_quant": False}
        ]
        n = 1
        compiled, helper_needed = compile_assertions(verifiers)
        assert compiled == frozenset({"only"})
        assert helper_needed is False
        check_all_invariants(compiled, n + 1, "done", True, helper_needed, verifiers, n)

    def test_single_eligible_with_quant(self) -> None:
        verifiers = [
            {"name": "qv", "has_cond": True, "is_dict": True, "uses_quant": True}
        ]
        n = 1
        compiled, helper_needed = compile_assertions(verifiers)
        assert compiled == frozenset({"qv"})
        assert helper_needed is True
        check_all_invariants(compiled, n + 1, "done", True, helper_needed, verifiers, n)

    def test_cursor_exactly_at_n_batch_consistent_vacuous(
        self, standard_dag: RegistryDag
    ) -> None:
        verifiers = standard_dag.test_artifacts
        check_batch_consistent(frozenset({"inv1"}), N, verifiers, N)
        check_helper_needed_iff_quant_used(False, N, verifiers, N)

    def test_pre_vet_state_passed_may_be_false(
        self, standard_dag: RegistryDag
    ) -> None:
        verifiers = standard_dag.test_artifacts
        check_all_invariants(
            frozenset({"inv1", "inv2"}), 5,
            "compile_all", False, True,
            verifiers, N,
        )

    def test_mid_loop_partial_compile(self, standard_dag: RegistryDag) -> None:
        verifiers = standard_dag.test_artifacts
        check_all_invariants(
            frozenset({"inv1"}), 2,
            "compile_all", False, False,
            verifiers, N,
        )