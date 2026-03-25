import pytest
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node

# ---------------------------------------------------------------------------
# Domain constants (mirror TLA+ AllPasses)
# ---------------------------------------------------------------------------

ALL_PASSES = frozenset({"artifacts", "coverage", "interaction", "abstraction_gap", "imports"})


# ---------------------------------------------------------------------------
# Pure-logic helpers derived directly from the verified TLA+ spec
# ---------------------------------------------------------------------------

def _phase_mode_passes(phase: str, mode: str) -> frozenset:
    if phase == "post":
        return frozenset({"imports"})
    if phase == "pre":
        if mode == "external":
            return frozenset({"artifacts", "coverage", "abstraction_gap"})
        return frozenset({"artifacts", "coverage", "interaction", "abstraction_gap"})
    # phase == "all"
    if mode == "external":
        return frozenset({"artifacts", "coverage", "abstraction_gap", "imports"})
    return ALL_PASSES


def _expected_passes_for(phase: str, mode: str, artifacts_verdict: str) -> frozenset:
    if phase == "post":
        return frozenset({"imports"})
    if artifacts_verdict == "fail":
        return frozenset({"artifacts"})
    return _phase_mode_passes(phase, mode)


def _should_execute_pass(phase: str, mode: str, artifacts_verdict: str, p: str) -> bool:
    if phase == "post":
        return p == "imports"
    if artifacts_verdict == "fail":
        return p == "artifacts"
    return p in _phase_mode_passes(phase, mode)


# ---------------------------------------------------------------------------
# Invariant checker – applied at *every* intermediate state (mirrors TLA+)
# ---------------------------------------------------------------------------

def _check_all_invariants(
    phase: str,
    mode: str,
    artifacts_verdict: str,
    executed: frozenset,
    orchestration_done: bool,
) -> None:
    # ExecutedSubsetAllPasses
    assert executed <= ALL_PASSES, (
        f"executed {executed!r} contains unknown pass(es)"
    )

    # PreSkipsImports
    if phase == "pre":
        assert "imports" not in executed, (
            f"PreSkipsImports violated: imports in executed={executed!r}"
        )

    # ExternalNoInteraction
    if mode == "external":
        assert "interaction" not in executed, (
            f"ExternalNoInteraction violated: interaction in executed={executed!r}"
        )

    # PreExternalSubset
    if phase == "pre" and mode == "external":
        assert executed <= {"artifacts", "coverage", "abstraction_gap"}, (
            f"PreExternalSubset violated: executed={executed!r}"
        )

    if orchestration_done:
        expected = _expected_passes_for(phase, mode, artifacts_verdict)

        # FinalSetCorrect
        assert executed == expected, (
            f"FinalSetCorrect violated: executed={executed!r} expected={expected!r} "
            f"(phase={phase!r} mode={mode!r} av={artifacts_verdict!r})"
        )

        # PostOnlyImports
        if phase == "post":
            assert executed == {"imports"}, (
                f"PostOnlyImports violated: executed={executed!r}"
            )

        # AllSelfComplete
        if phase == "all" and mode == "self" and artifacts_verdict == "pass":
            assert executed == ALL_PASSES, (
                f"AllSelfComplete violated: executed={executed!r}"
            )

        # AllExternalComplete
        if phase == "all" and mode == "external" and artifacts_verdict == "pass":
            assert executed == {"artifacts", "coverage", "abstraction_gap", "imports"}, (
                f"AllExternalComplete violated: executed={executed!r}"
            )

        # PreSelfComplete
        if phase == "pre" and mode == "self" and artifacts_verdict == "pass":
            assert executed == {"artifacts", "coverage", "interaction", "abstraction_gap"}, (
                f"PreSelfComplete violated: executed={executed!r}"
            )

        # PreExternalComplete
        if phase == "pre" and mode == "external" and artifacts_verdict == "pass":
            assert executed == {"artifacts", "coverage", "abstraction_gap"}, (
                f"PreExternalComplete violated: executed={executed!r}"
            )


# ---------------------------------------------------------------------------
# Orchestration simulator – follows TLA+ PlusCal algorithm exactly
# ---------------------------------------------------------------------------

def _run_orchestration(
    phase: str,
    mode: str,
    artifacts_verdict: str,
    pass_order: list,
) -> frozenset:
    """
    Simulate _orchestrate_reviews() stepping through passes in *pass_order*.

    Invariants are checked after every RunOrSkip step and once more after
    Finish – matching the TLA+ 'ALL invariants hold at EVERY state' guarantee.
    """
    executed: frozenset = frozenset()

    # Init state: check invariants before any action
    _check_all_invariants(phase, mode, artifacts_verdict, executed, False)

    for p in pass_order:
        if _should_execute_pass(phase, mode, artifacts_verdict, p):
            executed = executed | {p}
        _check_all_invariants(phase, mode, artifacts_verdict, executed, False)

    # Finish
    _check_all_invariants(phase, mode, artifacts_verdict, executed, True)
    return executed


# ---------------------------------------------------------------------------
# DAG fixture helper (structural pattern from spec)
# ---------------------------------------------------------------------------

def _make_dag(pass_nodes: list, edges: list, artifacts: dict) -> RegistryDag:
    dag = RegistryDag()
    for nid in pass_nodes:
        dag.add_node(Node.behavior(nid, nid, "given", "when", "then"))
    for src, dst in edges:
        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))
    dag.test_artifacts = artifacts
    return dag


# ---------------------------------------------------------------------------
# Trace 1 – Phase=all, Mode=self, ArtifactsVerdict=fail
# ---------------------------------------------------------------------------

def test_trace_01_all_self_fail():
    phase, mode, av = "all", "self", "fail"
    pass_order = ["imports", "interaction", "artifacts", "abstraction_gap", "coverage"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("artifacts", "imports")],
        artifacts={"ArtifactsVerdict": av},
    )
    assert dag.node_count == len(ALL_PASSES)

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "imports" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 2 – Phase=pre, Mode=self, ArtifactsVerdict=fail
# ---------------------------------------------------------------------------

def test_trace_02_pre_self_fail():
    phase, mode, av = "pre", "self", "fail"
    pass_order = ["interaction", "coverage", "artifacts", "imports", "abstraction_gap"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "imports" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 3 – Phase=all, Mode=external, ArtifactsVerdict=fail
# ---------------------------------------------------------------------------

def test_trace_03_all_external_fail():
    phase, mode, av = "all", "external", "fail"
    pass_order = ["coverage", "imports", "abstraction_gap", "artifacts", "interaction"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("coverage", "artifacts"), ("abstraction_gap", "artifacts")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "interaction" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 4 – Phase=all, Mode=self, ArtifactsVerdict=pass
# ---------------------------------------------------------------------------

def test_trace_04_all_self_pass():
    phase, mode, av = "all", "self", "pass"
    pass_order = ["imports", "artifacts", "abstraction_gap", "coverage", "interaction"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("artifacts", "imports"), ("artifacts", "coverage")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == ALL_PASSES
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 5 – Phase=all, Mode=external, ArtifactsVerdict=fail (alt order)
# ---------------------------------------------------------------------------

def test_trace_05_all_external_fail_alt_order():
    phase, mode, av = "all", "external", "fail"
    pass_order = ["interaction", "coverage", "imports", "abstraction_gap", "artifacts"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "interaction" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 6 – Phase=pre, Mode=self, ArtifactsVerdict=fail (artifacts first)
# ---------------------------------------------------------------------------

def test_trace_06_pre_self_fail_artifacts_first():
    phase, mode, av = "pre", "self", "fail"
    pass_order = ["artifacts", "coverage", "imports", "interaction", "abstraction_gap"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("artifacts", "coverage")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "imports" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 7 – Phase=pre, Mode=self, ArtifactsVerdict=fail (artifacts last)
# ---------------------------------------------------------------------------

def test_trace_07_pre_self_fail_artifacts_last():
    phase, mode, av = "pre", "self", "fail"
    pass_order = ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("abstraction_gap", "coverage")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "imports" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 8 – Phase=all, Mode=external, ArtifactsVerdict=fail (imports first)
# ---------------------------------------------------------------------------

def test_trace_08_all_external_fail_imports_first():
    phase, mode, av = "all", "external", "fail"
    pass_order = ["imports", "coverage", "artifacts", "abstraction_gap", "interaction"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("artifacts", "abstraction_gap"), ("artifacts", "imports")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts"}
    assert "interaction" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 9 – Phase=pre, Mode=external, ArtifactsVerdict=pass
# ---------------------------------------------------------------------------

def test_trace_09_pre_external_pass():
    phase, mode, av = "pre", "external", "pass"
    pass_order = ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[("coverage", "abstraction_gap")],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts", "coverage", "abstraction_gap"}
    assert "imports" not in executed
    assert "interaction" not in executed
    assert executed <= {"artifacts", "coverage", "abstraction_gap"}
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Trace 10 – Phase=pre, Mode=self, ArtifactsVerdict=pass
# ---------------------------------------------------------------------------

def test_trace_10_pre_self_pass():
    phase, mode, av = "pre", "self", "pass"
    pass_order = ["abstraction_gap", "interaction", "artifacts", "coverage", "imports"]

    dag = _make_dag(
        pass_nodes=list(ALL_PASSES),
        edges=[
            ("abstraction_gap", "coverage"),
            ("interaction", "artifacts"),
        ],
        artifacts={"ArtifactsVerdict": av},
    )

    executed = _run_orchestration(phase, mode, av, pass_order)

    assert executed == {"artifacts", "coverage", "interaction", "abstraction_gap"}
    assert "imports" not in executed
    assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Dedicated invariant verifier tests
# ---------------------------------------------------------------------------

class TestPreSkipsImports:
    """PreSkipsImports: Phase='pre' => 'imports' never in executed."""

    @pytest.mark.parametrize("mode,av,order", [
        ("self",     "fail", ["interaction", "coverage", "artifacts", "imports", "abstraction_gap"]),
        ("self",     "fail", ["artifacts", "coverage", "imports", "interaction", "abstraction_gap"]),
        ("external", "pass", ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"]),
        ("self",     "pass", ["abstraction_gap", "interaction", "artifacts", "coverage", "imports"]),
    ])
    def test_imports_never_in_executed(self, mode, av, order):
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": av})
        executed = _run_orchestration("pre", mode, av, order)
        assert "imports" not in executed


class TestExternalNoInteraction:
    """ExternalNoInteraction: Mode='external' => 'interaction' never in executed."""

    @pytest.mark.parametrize("phase,av,order", [
        ("all",  "fail", ["coverage", "imports", "abstraction_gap", "artifacts", "interaction"]),
        ("all",  "fail", ["imports", "coverage", "artifacts", "abstraction_gap", "interaction"]),
        ("pre",  "pass", ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"]),
        ("all",  "fail", ["interaction", "coverage", "imports", "abstraction_gap", "artifacts"]),
        ("all",  "pass", ["interaction", "artifacts", "coverage", "abstraction_gap", "imports"]),
    ])
    def test_interaction_never_in_executed(self, phase, av, order):
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": av})
        executed = _run_orchestration(phase, "external", av, order)
        assert "interaction" not in executed


class TestPreExternalSubset:
    """PreExternalSubset: Phase='pre' & Mode='external' => executed <= {artifacts,coverage,abstraction_gap}."""

    @pytest.mark.parametrize("av,order,expected", [
        (
            "pass",
            ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"],
            {"artifacts", "coverage", "abstraction_gap"},
        ),
        (
            "fail",
            ["coverage", "imports", "abstraction_gap", "interaction", "artifacts"],
            {"artifacts"},
        ),
    ])
    def test_subset_constraint(self, av, order, expected):
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": av})
        executed = _run_orchestration("pre", "external", av, order)
        assert executed <= {"artifacts", "coverage", "abstraction_gap"}
        assert executed == expected


class TestAllSelfComplete:
    """AllSelfComplete: Phase='all', Mode='self', ArtifactsVerdict='pass' => executed==AllPasses."""

    def test_all_self_pass_executes_everything(self):
        order = ["imports", "artifacts", "abstraction_gap", "coverage", "interaction"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("all", "self", "pass", order)
        assert executed == ALL_PASSES

    def test_all_self_pass_reverse_order(self):
        order = ["interaction", "coverage", "abstraction_gap", "artifacts", "imports"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("all", "self", "pass", order)
        assert executed == ALL_PASSES


class TestAllExternalComplete:
    """AllExternalComplete: Phase='all', Mode='external', ArtifactsVerdict='pass'."""

    def test_all_external_pass(self):
        order = ["interaction", "artifacts", "coverage", "abstraction_gap", "imports"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("all", "external", "pass", order)
        assert executed == {"artifacts", "coverage", "abstraction_gap", "imports"}
        assert "interaction" not in executed

    def test_all_external_pass_alt_order(self):
        order = ["imports", "coverage", "interaction", "abstraction_gap", "artifacts"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("all", "external", "pass", order)
        assert executed == {"artifacts", "coverage", "abstraction_gap", "imports"}


class TestPostOnlyImports:
    """PostOnlyImports: Phase='post' & orchestration_done => executed=={'imports'}."""

    def test_post_self_pass(self):
        order = ["artifacts", "coverage", "interaction", "abstraction_gap", "imports"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("post", "self", "pass", order)
        assert executed == {"imports"}

    def test_post_external_pass(self):
        order = ["artifacts", "coverage", "interaction", "abstraction_gap", "imports"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
        executed = _run_orchestration("post", "external", "pass", order)
        assert executed == {"imports"}

    def test_post_external_fail(self):
        order = ["interaction", "abstraction_gap", "coverage", "artifacts", "imports"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        executed = _run_orchestration("post", "external", "fail", order)
        assert executed == {"imports"}

    def test_post_self_fail(self):
        order = ["imports", "artifacts", "coverage", "abstraction_gap", "interaction"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        executed = _run_orchestration("post", "self", "fail", order)
        assert executed == {"imports"}


class TestFinalSetCorrect:
    """FinalSetCorrect: orchestration_done => executed==ExpectedPassesFor(phase,mode,av)."""

    @pytest.mark.parametrize("phase,mode,av,order,expected", [
        (
            "all", "self", "fail",
            ["imports", "interaction", "artifacts", "abstraction_gap", "coverage"],
            frozenset({"artifacts"}),
        ),
        (
            "all", "self", "pass",
            ["imports", "artifacts", "abstraction_gap", "coverage", "interaction"],
            ALL_PASSES,
        ),
        (
            "pre", "external", "pass",
            ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"],
            frozenset({"artifacts", "coverage", "abstraction_gap"}),
        ),
        (
            "pre", "self", "pass",
            ["abstraction_gap", "interaction", "artifacts", "coverage", "imports"],
            frozenset({"artifacts", "coverage", "interaction", "abstraction_gap"}),
        ),
        (
            "post", "self", "pass",
            ["artifacts", "coverage", "interaction", "abstraction_gap", "imports"],
            frozenset({"imports"}),
        ),
    ])
    def test_final_set_correct(self, phase, mode, av, order, expected):
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": av})
        executed = _run_orchestration(phase, mode, av, order)
        assert executed == expected
        assert executed == _expected_passes_for(phase, mode, av)


class TestExecutedSubsetAllPasses:
    """ExecutedSubsetAllPasses: executed <= AllPasses at every state."""

    @pytest.mark.parametrize("phase,mode,av", [
        ("pre",  "self",     "pass"),
        ("pre",  "external", "fail"),
        ("all",  "self",     "pass"),
        ("all",  "external", "fail"),
        ("post", "self",     "pass"),
    ])
    def test_never_exceeds_all_passes(self, phase, mode, av):
        order = ["interaction", "imports", "coverage", "abstraction_gap", "artifacts"]
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": av})
        executed = _run_orchestration(phase, mode, av, order)
        assert executed <= ALL_PASSES


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_dag_phase_all_self_pass(self):
        """Empty DAG: no pass-nodes, no edges – orchestration still produces correct set."""
        dag = _make_dag([], [], {"ArtifactsVerdict": "pass"})
        assert dag.node_count == 0
        order = list(ALL_PASSES)
        executed = _run_orchestration("all", "self", "pass", order)
        assert executed == ALL_PASSES

    def test_isolated_pass_nodes_pre_self_fail(self):
        """All pass-nodes isolated (no edges) – phase=pre, self, fail."""
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        assert dag.edge_count == 0
        order = ["imports", "coverage", "interaction", "abstraction_gap", "artifacts"]
        executed = _run_orchestration("pre", "self", "fail", order)
        assert executed == {"artifacts"}
        assert "imports" not in executed

    def test_diamond_topology_all_external_pass(self):
        """Diamond DAG topology. Phase=all, external, pass."""
        dag = _make_dag(
            list(ALL_PASSES),
            [
                ("artifacts", "coverage"),
                ("artifacts", "interaction"),
                ("coverage", "abstraction_gap"),
                ("interaction", "abstraction_gap"),
            ],
            {"ArtifactsVerdict": "pass"},
        )
        order = ["interaction", "coverage", "artifacts", "abstraction_gap", "imports"]
        executed = _run_orchestration("all", "external", "pass", order)
        assert executed == {"artifacts", "coverage", "abstraction_gap", "imports"}
        assert "interaction" not in executed

    def test_post_phase_overrides_artifacts_verdict(self):
        """post phase with artifacts_verdict=fail still executes ONLY imports, not artifacts."""
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        order = ["artifacts", "coverage", "abstraction_gap", "interaction", "imports"]
        executed = _run_orchestration("post", "self", "fail", order)
        assert executed == {"imports"}
        assert "artifacts" not in executed

    def test_artifacts_verdict_fail_beats_phase_all_self(self):
        """ArtifactsVerdict=fail short-circuits: only artifacts runs even in all/self."""
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        order = ["coverage", "interaction", "imports", "abstraction_gap", "artifacts"]
        executed = _run_orchestration("all", "self", "fail", order)
        assert executed == {"artifacts"}

    def test_pre_external_fail_only_artifacts(self):
        """pre+external+fail: only artifacts, not even coverage or abstraction_gap."""
        dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "fail"})
        order = ["coverage", "abstraction_gap", "imports", "interaction", "artifacts"]
        executed = _run_orchestration("pre", "external", "fail", order)
        assert executed == {"artifacts"}
        assert executed <= {"artifacts", "coverage", "abstraction_gap"}
        assert "interaction" not in executed
        assert "imports" not in executed

    def test_single_pass_dag_coverage_only(self):
        """DAG with only the coverage node; passes still determined by phase logic."""
        dag = _make_dag(["coverage"], [], {"ArtifactsVerdict": "pass"})
        assert dag.node_count == 1
        order = ["coverage", "artifacts", "interaction", "abstraction_gap", "imports"]
        executed = _run_orchestration("pre", "self", "pass", order)
        assert executed == {"artifacts", "coverage", "interaction", "abstraction_gap"}
        assert "imports" not in executed

    def test_all_external_pass_interaction_always_skipped(self):
        """all+external+pass: interaction is skipped regardless of ordering position."""
        for order in [
            ["interaction", "artifacts", "coverage", "abstraction_gap", "imports"],
            ["artifacts", "coverage", "abstraction_gap", "imports", "interaction"],
            ["artifacts", "interaction", "coverage", "abstraction_gap", "imports"],
        ]:
            dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
            executed = _run_orchestration("all", "external", "pass", order)
            assert "interaction" not in executed
            assert executed == {"artifacts", "coverage", "abstraction_gap", "imports"}

    def test_pre_self_pass_imports_always_skipped(self):
        """pre+self+pass: imports is skipped regardless of ordering position."""
        for order in [
            ["imports", "artifacts", "coverage", "interaction", "abstraction_gap"],
            ["artifacts", "coverage", "imports", "interaction", "abstraction_gap"],
            ["artifacts", "coverage", "interaction", "abstraction_gap", "imports"],
        ]:
            dag = _make_dag(list(ALL_PASSES), [], {"ArtifactsVerdict": "pass"})
            executed = _run_orchestration("pre", "self", "pass", order)
            assert "imports" not in executed
            assert executed == {"artifacts", "coverage", "interaction", "abstraction_gap"}

    def test_dag_node_and_edge_counts_preserved(self):
        """Structural sanity: DAG node/edge counts unaffected by orchestration logic."""
        dag = _make_dag(
            list(ALL_PASSES),
            [("artifacts", "coverage"), ("coverage", "abstraction_gap")],
            {"ArtifactsVerdict": "pass"},
        )
        assert dag.node_count == len(ALL_PASSES)
        assert dag.edge_count == 2
        order = list(ALL_PASSES)
        _run_orchestration("all", "self", "pass", order)
        assert dag.node_count == len(ALL_PASSES)
        assert dag.edge_count == 2