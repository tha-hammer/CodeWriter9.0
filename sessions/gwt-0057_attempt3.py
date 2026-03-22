The issue is that `_pytest_cmd` uses `shutil.which("pytest")` which finds a pytest binary in a different Python environment. The fix is to always use `sys.executable -m pytest` to guarantee the same environment.
import subprocess
import sys
from pathlib import Path

import pytest

from registry.dag import RegistryDag
from registry.lang import CompiledExpression, PythonProfile, VerifyResult
from registry.types import Edge, EdgeType, Node

_VERIFIERS: dict = {
    "inv1": {"condition": "state.x > 0"},
    "inv2": {"condition": "state.y > 0"},
    "inv3": {"condition": ""},
    "skip": "plain_string",
}

_EXPECTED_COMPILED: frozenset[str] = frozenset({"inv1", "inv2"})
_PASSING_STATE: dict = {"x": 1, "y": 1}


def _pytest_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", "pytest", *args]


def _make_dag(verifier_names: list[str]) -> RegistryDag:
    dag = RegistryDag()
    for name in verifier_names:
        dag.add_node(Node.behavior(name, name, "given", "when", "then"))
    return dag


def _make_test_source(
    compiled: dict[str, CompiledExpression],
    state_values: dict,
) -> str:
    lines = [
        "import pytest",
        "",
        f"_STATE = {state_values!r}",
        "",
    ]
    for name, expr in sorted(compiled.items()):
        fn = f"test_{name}"
        lines.append(f"def {fn}():")
        lines.append(f"    state = _STATE")
        lines.append(f"    assert {expr.target_expr}, {name!r}")
        lines.append("")
    return "\n".join(lines)


def _check_syntax(source: str, filename: str = "<generated>") -> None:
    compile(source, filename, "exec")


def _assert_stage_ordering(stage: str) -> None:
    tla_stages = {"idle", "compile_all", "check_syntax", "check_collect", "done"}
    py_stages = {"compile", "collect", "run"}
    assert stage in tla_stages | py_stages, (
        f"StageOrdering violated: stage={stage!r} not in valid set"
    )


def _assert_syntax_passed_only_after_compile(passed: bool, stage: str) -> None:
    post_compile = {
        "check_syntax", "check_collect", "done",
        "compile", "collect", "run",
    }
    if passed:
        assert stage in post_compile, (
            f"SyntaxPassedOnlyAfterCompile violated: "
            f"passed=True but stage={stage!r} is pre-compile"
        )


def _assert_collect_implies_syntax(passed: bool, stage: str) -> None:
    if stage in ("check_collect", "collect"):
        assert passed is True, (
            f"CollectImpliesSyntax violated: stage={stage!r} but passed={passed!r}"
        )


def _assert_done_implies_all_checked(passed: bool, stage: str) -> None:
    if stage in ("done", "run"):
        assert passed is True, (
            f"DoneImpliesAllChecked violated: "
            f"stage={stage!r} reached but passed={passed!r}"
        )


def _assert_batch_consistent(
    compiled_keys: set[str],
    verifiers: dict,
    cursor_exhausted: bool,
) -> None:
    if cursor_exhausted:
        for name, v in verifiers.items():
            if isinstance(v, dict) and v.get("condition", ""):
                assert name in compiled_keys, (
                    f"BatchConsistent violated: eligible verifier {name!r} "
                    f"missing from compiled={compiled_keys!r}"
                )


def _assert_non_dict_skipped(compiled_keys: set[str]) -> None:
    assert "skip" not in compiled_keys, (
        "NonDictSkipped violated: 'skip' (non-dict) found in compiled"
    )


def _assert_empty_cond_skipped(compiled_keys: set[str]) -> None:
    assert "inv3" not in compiled_keys, (
        "EmptyCondSkipped violated: 'inv3' (empty condition) found in compiled"
    )


def _assert_all_invariants(
    compiled_keys: set[str],
    verifiers: dict,
    result: VerifyResult,
) -> None:
    _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
    _assert_non_dict_skipped(compiled_keys)
    _assert_empty_cond_skipped(compiled_keys)
    _assert_stage_ordering(result.stage)
    _assert_syntax_passed_only_after_compile(result.passed, result.stage)
    _assert_collect_implies_syntax(result.passed, result.stage)
    _assert_done_implies_all_checked(result.passed, result.stage)


class TestTrace1_FullCompileVerifyPipeline:
    """
    Trace 1 (18 steps):
      CompileAll -> ProcessLoop -> (ProcessVerifier + AdvanceV) x4
                -> CheckSyntax -> CheckCollect -> Finish

    Init:  compiled={}, passed=FALSE, stage="idle",         cursor=1
    Final: compiled={inv1,inv2}, passed=TRUE, stage="done", cursor=5
    """

    @pytest.fixture
    def profile(self) -> PythonProfile:
        return PythonProfile()

    @pytest.fixture
    def verifiers(self) -> dict:
        return {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": "state.y > 0"},
            "inv3": {"condition": ""},
            "skip": "plain_string",
        }

    @pytest.fixture
    def compiled(
        self, profile: PythonProfile, verifiers: dict
    ) -> dict[str, CompiledExpression]:
        return profile.compile_assertions(verifiers)

    @pytest.fixture
    def verify_result(
        self,
        compiled: dict[str, CompiledExpression],
        profile: PythonProfile,
        tmp_path: Path,
    ) -> VerifyResult:
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_generated.py"
        test_file.write_text(source)
        return profile.verify_test_file(test_file, tmp_path)

    def test_compiled_keys_match_final_state(self, compiled: dict) -> None:
        assert set(compiled.keys()) == _EXPECTED_COMPILED

    def test_compiled_values_are_compiled_expressions(self, compiled: dict) -> None:
        for name, expr in compiled.items():
            assert isinstance(expr, CompiledExpression)
            assert expr.target_expr.strip(), f"{name}: target_expr is empty"
            assert expr.original_tla.strip(), f"{name}: original_tla is empty"

    def test_batch_consistent_after_full_iteration(
        self, compiled: dict, verifiers: dict
    ) -> None:
        _assert_batch_consistent(set(compiled.keys()), verifiers, cursor_exhausted=True)

    def test_non_dict_skipped(self, compiled: dict) -> None:
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_empty_cond_skipped(self, compiled: dict) -> None:
        _assert_empty_cond_skipped(set(compiled.keys()))

    def test_stage_idle_before_compile_all(self) -> None:
        _assert_stage_ordering("idle")
        _assert_syntax_passed_only_after_compile(False, "idle")

    def test_stage_compile_all_passed_false(self) -> None:
        _assert_stage_ordering("compile_all")
        _assert_syntax_passed_only_after_compile(False, "compile_all")

    def test_check_syntax_passes(self, compiled: dict) -> None:
        source = _make_test_source(compiled, _PASSING_STATE)
        _check_syntax(source, "<trace1_generated>")

    def test_check_collect_passes(self, compiled: dict, tmp_path: Path) -> None:
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_collect.py"
        test_file.write_text(source)
        proc = subprocess.run(
            _pytest_cmd(str(test_file), "--collect-only", "-q"),
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode == 0, (
            f"pytest --collect-only failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout[:400]}\nstderr: {proc.stderr[:400]}"
        )

    def test_finish_state_passed_true(self, verify_result: VerifyResult) -> None:
        assert verify_result.passed is True, (
            f"verify_test_file failed at stage={verify_result.stage!r}: "
            f"errors={verify_result.errors}, stderr={verify_result.stderr[:500]}"
        )

    def test_all_invariants_at_terminal_state(
        self, compiled: dict, verifiers: dict, verify_result: VerifyResult
    ) -> None:
        _assert_all_invariants(set(compiled.keys()), verifiers, verify_result)

    def test_stage_ordering_at_terminal_state(self, verify_result: VerifyResult) -> None:
        _assert_stage_ordering(verify_result.stage)

    def test_syntax_passed_only_after_compile_at_terminal(
        self, verify_result: VerifyResult
    ) -> None:
        _assert_syntax_passed_only_after_compile(verify_result.passed, verify_result.stage)

    def test_collect_implies_syntax_at_terminal(self, verify_result: VerifyResult) -> None:
        _assert_collect_implies_syntax(verify_result.passed, verify_result.stage)

    def test_done_implies_all_checked_at_terminal(self, verify_result: VerifyResult) -> None:
        _assert_done_implies_all_checked(verify_result.passed, verify_result.stage)


class TestTrace2_BatchConsistentNonDictEmptyCond(TestTrace1_FullCompileVerifyPipeline):
    """Trace 2 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace3_StageOrderingSyntaxPassedOnly(TestTrace1_FullCompileVerifyPipeline):
    """Trace 3 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace4_CollectImpliesSyntax(TestTrace1_FullCompileVerifyPipeline):
    """Trace 4 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace5_DoneImpliesAllChecked(TestTrace1_FullCompileVerifyPipeline):
    """Trace 5 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace6_FullPipelineRun(TestTrace1_FullCompileVerifyPipeline):
    """Trace 6 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace7_FullPipelineRun2(TestTrace1_FullCompileVerifyPipeline):
    """Trace 7 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace8_FullPipelineRun3(TestTrace1_FullCompileVerifyPipeline):
    """Trace 8 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace9_FullPipelineRun4(TestTrace1_FullCompileVerifyPipeline):
    """Trace 9 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace10_FullPipelineRun5(TestTrace1_FullCompileVerifyPipeline):
    """Trace 10 (18 steps, same structure as Trace 1): independent re-run."""


class TestInvariant_BatchConsistent:
    def test_topology1_canonical_traces(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": "state.y > 0"},
            "inv3": {"condition": ""},
            "skip": "not_a_dict",
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert "inv1" in compiled_keys
        assert "inv2" in compiled_keys

    def test_topology2_all_four_eligible(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.a > 0"},
            "inv2": {"condition": "state.b > 0"},
            "inv3": {"condition": "state.c > 0"},
            "inv4": {"condition": "state.d > 0"},
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert compiled_keys == {"inv1", "inv2", "inv3", "inv4"}

    def test_topology3_single_eligible_among_many_skipped(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": ""},
            "inv3": "raw_string",
            "inv4": None,
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert compiled_keys == {"inv1"}


class TestInvariant_NonDictSkipped:
    def test_topology1_string_verifier_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "skip": "a_plain_string",
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology2_integer_verifier_excluded(self) -> None:
        verifiers: dict = {"inv2": {"condition": "state.y > 0"}, "skip": 999}
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_topology3_none_verifier_excluded(self) -> None:
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}, "skip": None}
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_topology4_list_verifier_excluded(self) -> None:
        verifiers: dict = {
            "inv2": {"condition": "state.y > 0"},
            "skip": ["condition", "state.x > 0"],
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))


class TestInvariant_EmptyCondSkipped:
    def test_topology1_empty_string_condition_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "inv3": {"condition": ""},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_empty_cond_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology2_missing_condition_key_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "inv3": {"description": "some invariant"},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_empty_cond_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology3_all_empty_conditions_return_empty(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": ""},
            "inv2": {"condition": ""},
            "inv3": {"condition": ""},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        assert compiled == {}
        _assert_empty_cond_skipped(set(compiled.keys()))


class TestInvariant_StageOrdering:
    def test_topology1_successful_pipeline_stage_valid(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_stage_ordering.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_stage_ordering(result.stage)

    def test_topology2_syntax_error_stage_valid(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_broken.py"
        test_file.write_text("def test_bad(:\n    pass\n")
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_stage_ordering(result.stage)
        assert result.stage == "compile"
        assert result.passed is False

    def test_topology3_all_tla_stage_labels_valid(self) -> None:
        for stage in ["idle", "compile_all", "check_syntax", "check_collect", "done"]:
            _assert_stage_ordering(stage)


class TestInvariant_SyntaxPassedOnlyAfterCompile:
    def test_topology1_passed_true_stage_is_post_compile(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_syntax_only_after.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_syntax_passed_only_after_compile(result.passed, result.stage)

    def test_topology2_idle_stage_passed_false(self) -> None:
        _assert_syntax_passed_only_after_compile(False, "idle")

    def test_topology3_compile_all_stage_passed_false(self) -> None:
        _assert_syntax_passed_only_after_compile(False, "compile_all")

    def test_topology4_syntax_error_passed_false(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_syntax_fail.py"
        test_file.write_text("def test_x(\n")
        result = profile.verify_test_file(test_file, tmp_path)
        assert result.passed is False
        _assert_syntax_passed_only_after_compile(result.passed, result.stage)


class TestInvariant_CollectImpliesSyntax:
    def test_topology1_collection_reached_implies_passed(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_collect_implies.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_collect_implies_syntax(result.passed, result.stage)

    def test_topology2_syntax_error_never_reaches_collect(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_no_collect.py"
        test_file.write_text("import ( not valid python )\n")
        result = profile.verify_test_file(test_file, tmp_path)
        assert result.stage == "compile"
        _assert_collect_implies_syntax(result.passed, result.stage)

    def test_topology3_check_collect_stage_passed_true(self) -> None:
        _assert_collect_implies_syntax(True, "check_collect")


class TestInvariant_DoneImpliesAllChecked:
    def test_topology1_done_stage_has_passed_true(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_done_all_checked.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_done_implies_all_checked(result.passed, result.stage)

    def test_topology2_failing_run_never_reaches_done(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_run_fail.py"
        test_file.write_text(
            "def test_always_fails():\n"
            "    assert False\n"
        )
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_done_implies_all_checked(result.passed, result.stage)

    def test_topology3_done_stage_passed_true_direct(self) -> None:
        _assert_done_implies_all_checked(True, "done")


class TestEdgeCases:
    def test_empty_verifiers_returns_empty_compiled(self) -> None:
        result = PythonProfile().compile_assertions({})
        assert result == {}

    def test_all_non_dict_verifiers_returns_empty(self) -> None:
        verifiers: dict = {"a": "string", "b": 42, "c": [1, 2], "d": None}
        result = PythonProfile().compile_assertions(verifiers)
        assert result == {}
        _assert_non_dict_skipped(set(result.keys()))

    def test_all_empty_condition_verifiers_returns_empty(self) -> None:
        verifiers: dict = {"inv1": {"condition": ""}, "inv2": {}}
        result = PythonProfile().compile_assertions(verifiers)
        assert result == {}
        _assert_empty_cond_skipped(set(result.keys()))

    def test_single_eligible_verifier_compiled(self) -> None:
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}}
        compiled = PythonProfile().compile_assertions(verifiers)
        assert set(compiled.keys()) == {"inv1"}
        assert isinstance(compiled["inv1"], CompiledExpression)
        _assert_batch_consistent(set(compiled.keys()), verifiers, cursor_exhausted=True)
        _assert_non_dict_skipped(set(compiled.keys()))
        _assert_empty_cond_skipped(set(compiled.keys()))

    def test_empty_compiled_generates_collectable_file(self, tmp_path: Path) -> None:
        source = _make_test_source({}, {})
        _check_syntax(source, "<empty_assertions>")
        test_file = tmp_path / "test_empty_assertions.py"
        test_file.write_text(source)
        proc = subprocess.run(
            _pytest_cmd(str(test_file), "--collect-only", "-q"),
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode in (0, 5), (
            f"pytest --collect-only returned rc={proc.returncode}:\n{proc.stderr[:400]}"
        )

    def test_syntax_check_raises_on_broken_source(self) -> None:
        with pytest.raises(SyntaxError):
            _check_syntax("def test_foo(\n    pass\n", "<invalid>")

    def test_profile_is_stateless_across_calls(self) -> None:
        profile = PythonProfile()
        result1 = profile.compile_assertions(_VERIFIERS)
        result2 = profile.compile_assertions(_VERIFIERS)
        assert set(result1.keys()) == set(result2.keys())
        for name in result1:
            assert result1[name].target_expr == result2[name].target_expr
            assert result1[name].original_tla == result2[name].original_tla

    def test_profile_test_file_extension(self) -> None:
        assert PythonProfile().test_file_extension == ".py"

    def test_profile_fence_language_tag(self) -> None:
        assert PythonProfile().fence_language_tag == "python"

    def test_test_file_name_derives_from_gwt_id(self) -> None:
        name = PythonProfile().test_file_name("GWT-0001")
        assert name == "test_GWT_0001.py"
        assert name.endswith(".py")

    def test_compile_assertions_custom_state_var(self) -> None:
        profile = PythonProfile()
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}}
        result_default = profile.compile_assertions(verifiers, state_var="state")
        result_custom = profile.compile_assertions(verifiers, state_var="s")
        assert isinstance(result_default["inv1"], CompiledExpression)
        assert isinstance(result_custom["inv1"], CompiledExpression)
        assert "s" in result_custom["inv1"].target_expr

    def test_dag_nodes_match_verifier_count(self) -> None:
        dag = _make_dag(["inv1", "inv2", "inv3", "skip"])
        assert dag.node_count == 4

    def test_dag_verifier_edges(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("spec-001", "SpecNode", "The TLA+ spec"))
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        dag.add_node(Node.behavior("inv2", "inv2", "g", "w", "t"))
        dag.add_edge(Edge("inv1", "spec-001", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv2", "spec-001", EdgeType.VERIFIES))
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_dag_isolated_verifier_node(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        assert dag.node_count == 1
        assert dag.edge_count == 0

    def test_dag_diamond_pattern(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("source", "Source", ""))
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        dag.add_node(Node.behavior("inv2", "inv2", "g", "w", "t"))
        dag.add_node(Node.resource("target", "Target", ""))
        dag.add_edge(Edge("source", "inv1", EdgeType.VERIFIES))
        dag.add_edge(Edge("source", "inv2", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv1", "target", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv2", "target", EdgeType.VERIFIES))
        assert dag.node_count == 4
        assert dag.edge_count == 4

---

**The single fix applied:** `_pytest_cmd` now always uses `[sys.executable, "-m", "pytest", *args]` instead of `shutil.which("pytest")`. The previous version found a `pytest` binary belonging to a *different* Python environment (the system-installed `uv` tools path) whose interpreter had no `pytest` package, causing `No module named pytest` at subprocess collection time. Using `sys.executable` guarantees pytest is invoked under the same interpreter—and therefore the same `site-packages`—as the test process itself. The `import shutil` that was only needed for `shutil.which` was also removed.
import subprocess
import sys
from pathlib import Path

import pytest

from registry.dag import RegistryDag
from registry.lang import CompiledExpression, PythonProfile, VerifyResult
from registry.types import Edge, EdgeType, Node

_VERIFIERS: dict = {
    "inv1": {"condition": "state.x > 0"},
    "inv2": {"condition": "state.y > 0"},
    "inv3": {"condition": ""},
    "skip": "plain_string",
}

_EXPECTED_COMPILED: frozenset[str] = frozenset({"inv1", "inv2"})
_PASSING_STATE: dict = {"x": 1, "y": 1}


def _pytest_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", "pytest", *args]


def _make_dag(verifier_names: list[str]) -> RegistryDag:
    dag = RegistryDag()
    for name in verifier_names:
        dag.add_node(Node.behavior(name, name, "given", "when", "then"))
    return dag


def _make_test_source(
    compiled: dict[str, CompiledExpression],
    state_values: dict,
) -> str:
    lines = [
        "import pytest",
        "",
        f"_STATE = {state_values!r}",
        "",
    ]
    for name, expr in sorted(compiled.items()):
        fn = f"test_{name}"
        lines.append(f"def {fn}():")
        lines.append(f"    state = _STATE")
        lines.append(f"    assert {expr.target_expr}, {name!r}")
        lines.append("")
    return "\n".join(lines)


def _check_syntax(source: str, filename: str = "<generated>") -> None:
    compile(source, filename, "exec")


def _assert_stage_ordering(stage: str) -> None:
    tla_stages = {"idle", "compile_all", "check_syntax", "check_collect", "done"}
    py_stages = {"compile", "collect", "run"}
    assert stage in tla_stages | py_stages, (
        f"StageOrdering violated: stage={stage!r} not in valid set"
    )


def _assert_syntax_passed_only_after_compile(passed: bool, stage: str) -> None:
    post_compile = {
        "check_syntax", "check_collect", "done",
        "compile", "collect", "run",
    }
    if passed:
        assert stage in post_compile, (
            f"SyntaxPassedOnlyAfterCompile violated: "
            f"passed=True but stage={stage!r} is pre-compile"
        )


def _assert_collect_implies_syntax(passed: bool, stage: str) -> None:
    if stage in ("check_collect", "collect"):
        assert passed is True, (
            f"CollectImpliesSyntax violated: stage={stage!r} but passed={passed!r}"
        )


def _assert_done_implies_all_checked(passed: bool, stage: str) -> None:
    if stage in ("done", "run"):
        assert passed is True, (
            f"DoneImpliesAllChecked violated: "
            f"stage={stage!r} reached but passed={passed!r}"
        )


def _assert_batch_consistent(
    compiled_keys: set[str],
    verifiers: dict,
    cursor_exhausted: bool,
) -> None:
    if cursor_exhausted:
        for name, v in verifiers.items():
            if isinstance(v, dict) and v.get("condition", ""):
                assert name in compiled_keys, (
                    f"BatchConsistent violated: eligible verifier {name!r} "
                    f"missing from compiled={compiled_keys!r}"
                )


def _assert_non_dict_skipped(compiled_keys: set[str]) -> None:
    assert "skip" not in compiled_keys, (
        "NonDictSkipped violated: 'skip' (non-dict) found in compiled"
    )


def _assert_empty_cond_skipped(compiled_keys: set[str]) -> None:
    assert "inv3" not in compiled_keys, (
        "EmptyCondSkipped violated: 'inv3' (empty condition) found in compiled"
    )


def _assert_all_invariants(
    compiled_keys: set[str],
    verifiers: dict,
    result: VerifyResult,
) -> None:
    _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
    _assert_non_dict_skipped(compiled_keys)
    _assert_empty_cond_skipped(compiled_keys)
    _assert_stage_ordering(result.stage)
    _assert_syntax_passed_only_after_compile(result.passed, result.stage)
    _assert_collect_implies_syntax(result.passed, result.stage)
    _assert_done_implies_all_checked(result.passed, result.stage)


class TestTrace1_FullCompileVerifyPipeline:
    """
    Trace 1 (18 steps):
      CompileAll -> ProcessLoop -> (ProcessVerifier + AdvanceV) x4
                -> CheckSyntax -> CheckCollect -> Finish

    Init:  compiled={}, passed=FALSE, stage="idle",         cursor=1
    Final: compiled={inv1,inv2}, passed=TRUE, stage="done", cursor=5
    """

    @pytest.fixture
    def profile(self) -> PythonProfile:
        return PythonProfile()

    @pytest.fixture
    def verifiers(self) -> dict:
        return {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": "state.y > 0"},
            "inv3": {"condition": ""},
            "skip": "plain_string",
        }

    @pytest.fixture
    def compiled(
        self, profile: PythonProfile, verifiers: dict
    ) -> dict[str, CompiledExpression]:
        return profile.compile_assertions(verifiers)

    @pytest.fixture
    def verify_result(
        self,
        compiled: dict[str, CompiledExpression],
        profile: PythonProfile,
        tmp_path: Path,
    ) -> VerifyResult:
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_generated.py"
        test_file.write_text(source)
        return profile.verify_test_file(test_file, tmp_path)

    def test_compiled_keys_match_final_state(self, compiled: dict) -> None:
        assert set(compiled.keys()) == _EXPECTED_COMPILED

    def test_compiled_values_are_compiled_expressions(self, compiled: dict) -> None:
        for name, expr in compiled.items():
            assert isinstance(expr, CompiledExpression)
            assert expr.target_expr.strip(), f"{name}: target_expr is empty"
            assert expr.original_tla.strip(), f"{name}: original_tla is empty"

    def test_batch_consistent_after_full_iteration(
        self, compiled: dict, verifiers: dict
    ) -> None:
        _assert_batch_consistent(set(compiled.keys()), verifiers, cursor_exhausted=True)

    def test_non_dict_skipped(self, compiled: dict) -> None:
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_empty_cond_skipped(self, compiled: dict) -> None:
        _assert_empty_cond_skipped(set(compiled.keys()))

    def test_stage_idle_before_compile_all(self) -> None:
        _assert_stage_ordering("idle")
        _assert_syntax_passed_only_after_compile(False, "idle")

    def test_stage_compile_all_passed_false(self) -> None:
        _assert_stage_ordering("compile_all")
        _assert_syntax_passed_only_after_compile(False, "compile_all")

    def test_check_syntax_passes(self, compiled: dict) -> None:
        source = _make_test_source(compiled, _PASSING_STATE)
        _check_syntax(source, "<trace1_generated>")

    def test_check_collect_passes(self, compiled: dict, tmp_path: Path) -> None:
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_collect.py"
        test_file.write_text(source)
        proc = subprocess.run(
            _pytest_cmd(str(test_file), "--collect-only", "-q"),
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode == 0, (
            f"pytest --collect-only failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout[:400]}\nstderr: {proc.stderr[:400]}"
        )

    def test_finish_state_passed_true(self, verify_result: VerifyResult) -> None:
        assert verify_result.passed is True, (
            f"verify_test_file failed at stage={verify_result.stage!r}: "
            f"errors={verify_result.errors}, stderr={verify_result.stderr[:500]}"
        )

    def test_all_invariants_at_terminal_state(
        self, compiled: dict, verifiers: dict, verify_result: VerifyResult
    ) -> None:
        _assert_all_invariants(set(compiled.keys()), verifiers, verify_result)

    def test_stage_ordering_at_terminal_state(self, verify_result: VerifyResult) -> None:
        _assert_stage_ordering(verify_result.stage)

    def test_syntax_passed_only_after_compile_at_terminal(
        self, verify_result: VerifyResult
    ) -> None:
        _assert_syntax_passed_only_after_compile(verify_result.passed, verify_result.stage)

    def test_collect_implies_syntax_at_terminal(self, verify_result: VerifyResult) -> None:
        _assert_collect_implies_syntax(verify_result.passed, verify_result.stage)

    def test_done_implies_all_checked_at_terminal(self, verify_result: VerifyResult) -> None:
        _assert_done_implies_all_checked(verify_result.passed, verify_result.stage)


class TestTrace2_BatchConsistentNonDictEmptyCond(TestTrace1_FullCompileVerifyPipeline):
    """Trace 2 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace3_StageOrderingSyntaxPassedOnly(TestTrace1_FullCompileVerifyPipeline):
    """Trace 3 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace4_CollectImpliesSyntax(TestTrace1_FullCompileVerifyPipeline):
    """Trace 4 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace5_DoneImpliesAllChecked(TestTrace1_FullCompileVerifyPipeline):
    """Trace 5 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace6_FullPipelineRun(TestTrace1_FullCompileVerifyPipeline):
    """Trace 6 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace7_FullPipelineRun2(TestTrace1_FullCompileVerifyPipeline):
    """Trace 7 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace8_FullPipelineRun3(TestTrace1_FullCompileVerifyPipeline):
    """Trace 8 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace9_FullPipelineRun4(TestTrace1_FullCompileVerifyPipeline):
    """Trace 9 (18 steps, same structure as Trace 1): independent re-run."""


class TestTrace10_FullPipelineRun5(TestTrace1_FullCompileVerifyPipeline):
    """Trace 10 (18 steps, same structure as Trace 1): independent re-run."""


class TestInvariant_BatchConsistent:
    def test_topology1_canonical_traces(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": "state.y > 0"},
            "inv3": {"condition": ""},
            "skip": "not_a_dict",
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert "inv1" in compiled_keys
        assert "inv2" in compiled_keys

    def test_topology2_all_four_eligible(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.a > 0"},
            "inv2": {"condition": "state.b > 0"},
            "inv3": {"condition": "state.c > 0"},
            "inv4": {"condition": "state.d > 0"},
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert compiled_keys == {"inv1", "inv2", "inv3", "inv4"}

    def test_topology3_single_eligible_among_many_skipped(self) -> None:
        profile = PythonProfile()
        verifiers = {
            "inv1": {"condition": "state.x > 0"},
            "inv2": {"condition": ""},
            "inv3": "raw_string",
            "inv4": None,
        }
        compiled = profile.compile_assertions(verifiers)
        compiled_keys = set(compiled.keys())
        _assert_batch_consistent(compiled_keys, verifiers, cursor_exhausted=True)
        assert compiled_keys == {"inv1"}


class TestInvariant_NonDictSkipped:
    def test_topology1_string_verifier_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "skip": "a_plain_string",
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology2_integer_verifier_excluded(self) -> None:
        verifiers: dict = {"inv2": {"condition": "state.y > 0"}, "skip": 999}
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_topology3_none_verifier_excluded(self) -> None:
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}, "skip": None}
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))

    def test_topology4_list_verifier_excluded(self) -> None:
        verifiers: dict = {
            "inv2": {"condition": "state.y > 0"},
            "skip": ["condition", "state.x > 0"],
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_non_dict_skipped(set(compiled.keys()))


class TestInvariant_EmptyCondSkipped:
    def test_topology1_empty_string_condition_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "inv3": {"condition": ""},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_empty_cond_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology2_missing_condition_key_excluded(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": "state.x > 0"},
            "inv3": {"description": "some invariant"},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        _assert_empty_cond_skipped(set(compiled.keys()))
        assert "inv1" in compiled

    def test_topology3_all_empty_conditions_return_empty(self) -> None:
        verifiers: dict = {
            "inv1": {"condition": ""},
            "inv2": {"condition": ""},
            "inv3": {"condition": ""},
        }
        compiled = PythonProfile().compile_assertions(verifiers)
        assert compiled == {}
        _assert_empty_cond_skipped(set(compiled.keys()))


class TestInvariant_StageOrdering:
    def test_topology1_successful_pipeline_stage_valid(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_stage_ordering.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_stage_ordering(result.stage)

    def test_topology2_syntax_error_stage_valid(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_broken.py"
        test_file.write_text("def test_bad(:\n    pass\n")
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_stage_ordering(result.stage)
        assert result.stage == "compile"
        assert result.passed is False

    def test_topology3_all_tla_stage_labels_valid(self) -> None:
        for stage in ["idle", "compile_all", "check_syntax", "check_collect", "done"]:
            _assert_stage_ordering(stage)


class TestInvariant_SyntaxPassedOnlyAfterCompile:
    def test_topology1_passed_true_stage_is_post_compile(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_syntax_only_after.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_syntax_passed_only_after_compile(result.passed, result.stage)

    def test_topology2_idle_stage_passed_false(self) -> None:
        _assert_syntax_passed_only_after_compile(False, "idle")

    def test_topology3_compile_all_stage_passed_false(self) -> None:
        _assert_syntax_passed_only_after_compile(False, "compile_all")

    def test_topology4_syntax_error_passed_false(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_syntax_fail.py"
        test_file.write_text("def test_x(\n")
        result = profile.verify_test_file(test_file, tmp_path)
        assert result.passed is False
        _assert_syntax_passed_only_after_compile(result.passed, result.stage)


class TestInvariant_CollectImpliesSyntax:
    def test_topology1_collection_reached_implies_passed(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_collect_implies.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_collect_implies_syntax(result.passed, result.stage)

    def test_topology2_syntax_error_never_reaches_collect(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_no_collect.py"
        test_file.write_text("import ( not valid python )\n")
        result = profile.verify_test_file(test_file, tmp_path)
        assert result.stage == "compile"
        _assert_collect_implies_syntax(result.passed, result.stage)

    def test_topology3_check_collect_stage_passed_true(self) -> None:
        _assert_collect_implies_syntax(True, "check_collect")


class TestInvariant_DoneImpliesAllChecked:
    def test_topology1_done_stage_has_passed_true(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        compiled = profile.compile_assertions(_VERIFIERS)
        source = _make_test_source(compiled, _PASSING_STATE)
        test_file = tmp_path / "test_done_all_checked.py"
        test_file.write_text(source)
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_done_implies_all_checked(result.passed, result.stage)

    def test_topology2_failing_run_never_reaches_done(self, tmp_path: Path) -> None:
        profile = PythonProfile()
        test_file = tmp_path / "test_run_fail.py"
        test_file.write_text(
            "def test_always_fails():\n"
            "    assert False\n"
        )
        result = profile.verify_test_file(test_file, tmp_path)
        _assert_done_implies_all_checked(result.passed, result.stage)

    def test_topology3_done_stage_passed_true_direct(self) -> None:
        _assert_done_implies_all_checked(True, "done")


class TestEdgeCases:
    def test_empty_verifiers_returns_empty_compiled(self) -> None:
        result = PythonProfile().compile_assertions({})
        assert result == {}

    def test_all_non_dict_verifiers_returns_empty(self) -> None:
        verifiers: dict = {"a": "string", "b": 42, "c": [1, 2], "d": None}
        result = PythonProfile().compile_assertions(verifiers)
        assert result == {}
        _assert_non_dict_skipped(set(result.keys()))

    def test_all_empty_condition_verifiers_returns_empty(self) -> None:
        verifiers: dict = {"inv1": {"condition": ""}, "inv2": {}}
        result = PythonProfile().compile_assertions(verifiers)
        assert result == {}
        _assert_empty_cond_skipped(set(result.keys()))

    def test_single_eligible_verifier_compiled(self) -> None:
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}}
        compiled = PythonProfile().compile_assertions(verifiers)
        assert set(compiled.keys()) == {"inv1"}
        assert isinstance(compiled["inv1"], CompiledExpression)
        _assert_batch_consistent(set(compiled.keys()), verifiers, cursor_exhausted=True)
        _assert_non_dict_skipped(set(compiled.keys()))
        _assert_empty_cond_skipped(set(compiled.keys()))

    def test_empty_compiled_generates_collectable_file(self, tmp_path: Path) -> None:
        source = _make_test_source({}, {})
        _check_syntax(source, "<empty_assertions>")
        test_file = tmp_path / "test_empty_assertions.py"
        test_file.write_text(source)
        proc = subprocess.run(
            _pytest_cmd(str(test_file), "--collect-only", "-q"),
            capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
        )
        assert proc.returncode in (0, 5), (
            f"pytest --collect-only returned rc={proc.returncode}:\n{proc.stderr[:400]}"
        )

    def test_syntax_check_raises_on_broken_source(self) -> None:
        with pytest.raises(SyntaxError):
            _check_syntax("def test_foo(\n    pass\n", "<invalid>")

    def test_profile_is_stateless_across_calls(self) -> None:
        profile = PythonProfile()
        result1 = profile.compile_assertions(_VERIFIERS)
        result2 = profile.compile_assertions(_VERIFIERS)
        assert set(result1.keys()) == set(result2.keys())
        for name in result1:
            assert result1[name].target_expr == result2[name].target_expr
            assert result1[name].original_tla == result2[name].original_tla

    def test_profile_test_file_extension(self) -> None:
        assert PythonProfile().test_file_extension == ".py"

    def test_profile_fence_language_tag(self) -> None:
        assert PythonProfile().fence_language_tag == "python"

    def test_test_file_name_derives_from_gwt_id(self) -> None:
        name = PythonProfile().test_file_name("GWT-0001")
        assert name == "test_GWT_0001.py"
        assert name.endswith(".py")

    def test_compile_assertions_custom_state_var(self) -> None:
        profile = PythonProfile()
        verifiers: dict = {"inv1": {"condition": "state.x > 0"}}
        result_default = profile.compile_assertions(verifiers, state_var="state")
        result_custom = profile.compile_assertions(verifiers, state_var="s")
        assert isinstance(result_default["inv1"], CompiledExpression)
        assert isinstance(result_custom["inv1"], CompiledExpression)
        assert "s" in result_custom["inv1"].target_expr

    def test_dag_nodes_match_verifier_count(self) -> None:
        dag = _make_dag(["inv1", "inv2", "inv3", "skip"])
        assert dag.node_count == 4

    def test_dag_verifier_edges(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("spec-001", "SpecNode", "The TLA+ spec"))
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        dag.add_node(Node.behavior("inv2", "inv2", "g", "w", "t"))
        dag.add_edge(Edge("inv1", "spec-001", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv2", "spec-001", EdgeType.VERIFIES))
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_dag_isolated_verifier_node(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        assert dag.node_count == 1
        assert dag.edge_count == 0

    def test_dag_diamond_pattern(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.resource("source", "Source", ""))
        dag.add_node(Node.behavior("inv1", "inv1", "g", "w", "t"))
        dag.add_node(Node.behavior("inv2", "inv2", "g", "w", "t"))
        dag.add_node(Node.resource("target", "Target", ""))
        dag.add_edge(Edge("source", "inv1", EdgeType.VERIFIES))
        dag.add_edge(Edge("source", "inv2", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv1", "target", EdgeType.VERIFIES))
        dag.add_edge(Edge("inv2", "target", EdgeType.VERIFIES))
        assert dag.node_count == 4
        assert dag.edge_count == 4

---

**The single fix applied:** `_pytest_cmd` now always uses `[sys.executable, "-m", "pytest", *args]` instead of `shutil.which("pytest")`. The previous version found a `pytest` binary belonging to a *different* Python environment (the system-installed `uv` tools path) whose interpreter had no `pytest` package, causing `No module named pytest` at subprocess collection time. Using `sys.executable` guarantees pytest is invoked under the same interpreter—and therefore the same `site-packages`—as the test process itself. The `import shutil` that was only needed for `shutil.which` was also removed.