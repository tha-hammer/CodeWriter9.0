"""pytest tests for LoopWritesSpecOnPass — verified by TLC.

Behavior (GWT):
  Given: a GWT ID and a successful TLC verification (LoopResult.PASS)
         with a compiled spec at a temporary path
  When:  run_loop() completes the verification
  Then:  the verified .tla file is copied to ctx.spec_dir/<gwt-id>.tla,
         the .cfg file is copied alongside it if present, and
         simulation traces are written to ctx.spec_dir/<gwt-id>_sim_traces.json
         (only when run_tlc_simulate returns a non-empty list)

Each test function below is a direct translation of one TLC simulation trace.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Pre-mock claude_agent_sdk so registry.loop_runner can be imported in test
# environments that do not have the Anthropic SDK installed.
# All real SDK usage is patched out before any test runs.
# ---------------------------------------------------------------------------
if "claude_agent_sdk" not in sys.modules:
    import types as _types

    class _FlexStub:
        """Stub class: stores kwargs, returns AsyncMock for unknown attrs."""
        def __init__(self, *a, **kw):
            for k, v in kw.items():
                object.__setattr__(self, k, v)
        def __getattr__(self, name):
            am = AsyncMock()
            object.__setattr__(self, name, am)
            return am

    _sdk_mod = _types.ModuleType("claude_agent_sdk")
    _sdk_mod.__spec__ = None
    # _FlexStub is a real class so MagicMock(spec=_FlexStub) works in Python 3.13
    for _attr in (
        "ClaudeSDKClient", "ClaudeAgentOptions", "AssistantMessage",
        "ToolResultBlock", "TextBlock", "ResultMessage",
    ):
        setattr(_sdk_mod, _attr, _FlexStub)
    _sdk_mod.query = AsyncMock()
    sys.modules["claude_agent_sdk"] = _sdk_mod

import pytest

from registry.context import ProjectContext
from registry.dag import RegistryDag
from registry.loop_runner import run_loop
from registry.one_shot_loop import LoopResult, LoopStatus
from registry.types import Node


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_STEPS = 5  # TLA+ MaxSteps — BoundedExecution invariant bound

# Canonical simulation traces returned by the mock run_tlc_simulate
_FAKE_SIM_TRACES = [
    {"trace_id": 0, "states": [{"step": 1, "phase": "run_loop"}]},
    {"trace_id": 1, "states": [{"step": 2, "phase": "check_result"}]},
]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: Path) -> ProjectContext:
    """Build a fully-formed ProjectContext using temporary directories."""
    spec_dir = tmp_path / "specs"
    session_dir = tmp_path / "sessions"
    state_root = tmp_path / "state"
    template_dir = tmp_path / "templates"
    tools_dir = tmp_path / "tools"
    for d in (spec_dir, session_dir, state_root, template_dir, tools_dir):
        d.mkdir(parents=True, exist_ok=True)
    return ProjectContext(
        engine_root=None,
        target_root=tmp_path,
        state_root=state_root,
        template_dir=template_dir,
        tools_dir=tools_dir,
        python_dir=tmp_path,
        schema_dir=state_root / "schema",
        spec_dir=spec_dir,
        artifact_dir=state_root / "bridge",
        session_dir=session_dir,
        test_output_dir=tmp_path / "tests" / "generated",
    )


def _register_gwt_and_save(state_root: Path, gwt_id: str) -> Path:
    """Create a RegistryDag with one GWT behavior node and persist it."""
    dag = RegistryDag()
    node = Node.behavior(
        gwt_id,
        "test_behavior",
        "given a condition exists",
        "when an action is taken",
        "then a result is produced",
    )
    dag.add_node(node)
    dag_path = state_root / "dag.json"
    dag.save(dag_path)
    return dag_path


def _make_compiled_spec(tmp_path: Path, gwt_id: str, *, cfg_exists: bool) -> Path:
    """Write a dummy compiled .tla (and optionally .cfg) at a temp location.

    Returns the path to the .tla file — mirrors status.compiled_spec_path.
    """
    compiled_dir = tmp_path / "compiled"
    compiled_dir.mkdir(parents=True, exist_ok=True)
    tla_path = compiled_dir / f"{gwt_id}.tla"
    tla_path.write_text(
        f"---- MODULE {gwt_id.replace('-', '_')} ----\nSPECIFICATION Spec\n====\n"
    )
    if cfg_exists:
        cfg_path = compiled_dir / f"{gwt_id}.cfg"
        cfg_path.write_text("SPECIFICATION Spec\nINVARIANT Invariant\n")
    return tla_path


@contextmanager
def _patch_run_loop(loop_status: LoopStatus, *, sim_traces: list | None = None):
    """Patch every I/O-bound dependency of run_loop().

    Substitutes:
      - _make_client          → MagicMock (no real SDK client created)
      - _call_llm_with_client → AsyncMock returning "fake llm response"
      - safe_disconnect       → AsyncMock (no-op)
      - OneShotLoop           → MagicMock class whose instances return loop_status
      - query_context         → MagicMock (bundle content irrelevant)
      - format_prompt_context → returns empty string
      - write_result_file     → no-op
      - run_tlc_simulate      → returns sim_traces (patched on source module so
                                the lazy `from registry.one_shot_loop import …`
                                inside the PASS branch picks up the mock)
    """
    if sim_traces is None:
        sim_traces = _FAKE_SIM_TRACES

    mock_loop_inst = MagicMock()
    mock_loop_inst.process_response.return_value = loop_status
    mock_loop_class = MagicMock(return_value=mock_loop_inst)

    with ExitStack() as stack:
        stack.enter_context(
            patch("registry.loop_runner._make_client", return_value=MagicMock())
        )
        stack.enter_context(
            patch(
                "registry.loop_runner._call_llm_with_client",
                new_callable=AsyncMock,
                return_value="fake llm response text",
            )
        )
        stack.enter_context(
            patch("registry.loop_runner.safe_disconnect", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch("registry.loop_runner.OneShotLoop", mock_loop_class)
        )
        stack.enter_context(
            patch("registry.loop_runner.query_context", return_value=MagicMock())
        )
        stack.enter_context(
            patch("registry.loop_runner.format_prompt_context", return_value="")
        )
        stack.enter_context(patch("registry.loop_runner.write_result_file"))
        stack.enter_context(
            patch(
                "registry.one_shot_loop.run_tlc_simulate",
                return_value=sim_traces,
            )
        )
        yield


def _check_all_invariants(
    *,
    loop_result: LoopResult,
    spec_dir: Path,
    gwt_id: str,
    cfg_exists: bool,
    phase_done: bool = True,
    traces_written: bool | None = None,
) -> None:
    """Assert every TLA+ invariant at the final state.

    TLA+ variable → Python mapping:
      spec_dir_has_tla    → (spec_dir / f"{gwt_id}.tla").exists()
      spec_dir_has_cfg    → (spec_dir / f"{gwt_id}.cfg").exists()
      spec_dir_has_traces → (spec_dir / f"{gwt_id}_sim_traces.json").exists()
      loop_result         → LoopResult enum value
      cfg_exists          → boolean fixture flag
      phase = "done"      → always True after run_loop() returns (phase_done=True)

    traces_written: when None (default) the TracesOnPass invariant is derived
      from whether sim_traces were non-empty (the implementation only writes
      the file when run_tlc_simulate returns a non-empty list).  Pass an
      explicit True/False to override.
    """
    tla_exists = (spec_dir / f"{gwt_id}.tla").exists()
    cfg_dest_exists = (spec_dir / f"{gwt_id}.cfg").exists()
    traces_exist = (spec_dir / f"{gwt_id}_sim_traces.json").exists()

    # PassImpliesWrite: phase = "done" /\ loop_result = "pass" => spec_dir_has_tla
    if phase_done and loop_result == LoopResult.PASS:
        assert tla_exists, (
            "PassImpliesWrite violated: PASS but .tla absent from spec_dir"
        )

    # FailImpliesNoWrite: phase = "done" /\ loop_result = "fail" => ~spec_dir_has_tla
    if phase_done and loop_result == LoopResult.FAIL:
        assert not tla_exists, (
            "FailImpliesNoWrite violated: FAIL but .tla present in spec_dir"
        )

    # CfgConditional: spec_dir_has_cfg = TRUE => cfg_exists = TRUE
    if cfg_dest_exists:
        assert cfg_exists, (
            "CfgConditional violated: .cfg in spec_dir but cfg_exists=FALSE"
        )

    # TracesOnPass: only asserted when the caller confirms traces should be present.
    # The implementation writes sim_traces only when run_tlc_simulate returns a
    # non-empty list; passing traces_written=True asserts the file is present.
    if traces_written is True:
        assert traces_exist, (
            "TracesOnPass violated: expected _sim_traces.json but it is absent"
        )
    elif traces_written is False:
        assert not traces_exist, (
            "TracesOnPass violated: unexpected _sim_traces.json present"
        )

    # BoundedExecution: step_count <= MaxSteps
    # Structural guarantee — run_loop with max_retries=1 never exceeds MAX_STEPS=5


# ---------------------------------------------------------------------------
# Trace 1 — 9 steps, PASS, cfg_exists=FALSE
# Actions: Start → RunLoop(pass) → CheckResult → AfterCheck →
#          WriteTla → WriteCfg(skip) → WriteTraces → Finish
# Final: spec_dir_has_tla=TRUE, spec_dir_has_cfg=FALSE, spec_dir_has_traces=TRUE
# ---------------------------------------------------------------------------

def test_trace1_pass_no_cfg(tmp_path):
    """Trace 1: PASS with no .cfg file — .tla and sim_traces written, .cfg absent."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-001"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    # --- final-state assertions (mirrors State 9 of Trace 1) ---
    assert result == LoopResult.PASS
    assert spec_path == ctx.spec_dir / f"{gwt_id}.tla"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()              # spec_dir_has_tla = TRUE
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()          # spec_dir_has_cfg = FALSE
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()  # spec_dir_has_traces = TRUE

    written = json.loads((ctx.spec_dir / f"{gwt_id}_sim_traces.json").read_text())
    assert written == _FAKE_SIM_TRACES

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 2 — 5 steps, FAIL, cfg_exists=FALSE
# Actions: Start → RunLoop(fail) → CheckResult → Finish
# Final: spec_dir_has_tla=FALSE, spec_dir_has_cfg=FALSE, spec_dir_has_traces=FALSE
# ---------------------------------------------------------------------------

def test_trace2_fail_no_cfg(tmp_path):
    """Trace 2: FAIL with no .cfg — nothing written to spec_dir."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-001"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(
        result=LoopResult.FAIL,
        error="invariant violation detected",
        compiled_spec_path=None,
    )
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    # --- final-state assertions (mirrors State 5 of Trace 2) ---
    assert result == LoopResult.FAIL
    assert spec_path is None
    assert not (ctx.spec_dir / f"{gwt_id}.tla").exists()              # spec_dir_has_tla = FALSE
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()              # spec_dir_has_cfg = FALSE
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()  # spec_dir_has_traces = FALSE

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=False,
    )


# ---------------------------------------------------------------------------
# Trace 3 — 9 steps, PASS, cfg_exists=FALSE (second PASS/no-cfg instance)
# ---------------------------------------------------------------------------

def test_trace3_pass_no_cfg(tmp_path):
    """Trace 3: PASS, cfg_exists=FALSE — independent topology, same outcome as Trace 1."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-002"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert spec_path == ctx.spec_dir / f"{gwt_id}.tla"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 4 — 5 steps, FAIL, cfg_exists=TRUE
# Actions: Start → RunLoop(fail) → CheckResult → Finish
# Final: spec_dir_has_tla=FALSE, spec_dir_has_cfg=FALSE, spec_dir_has_traces=FALSE
# Note: cfg_exists=TRUE at source but FAIL prevents any copying
# ---------------------------------------------------------------------------

def test_trace4_fail_with_cfg(tmp_path):
    """Trace 4: FAIL even though .cfg exists at source — nothing written to spec_dir."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-001"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    _make_compiled_spec(tmp_path, gwt_id, cfg_exists=True)  # cfg_exists=TRUE in env

    status = LoopStatus(
        result=LoopResult.FAIL,
        error="deadlock detected",
        compiled_spec_path=None,
    )
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    # --- final-state assertions (mirrors State 5 of Trace 4) ---
    assert result == LoopResult.FAIL
    assert spec_path is None
    assert not (ctx.spec_dir / f"{gwt_id}.tla").exists()              # spec_dir_has_tla = FALSE
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()              # spec_dir_has_cfg = FALSE
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()  # spec_dir_has_traces = FALSE

    # CfgConditional: spec_dir_has_cfg=FALSE is consistent even when cfg_exists=TRUE
    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=True,
        traces_written=False,
    )


# ---------------------------------------------------------------------------
# Trace 5 — 9 steps, PASS, cfg_exists=FALSE (third PASS/no-cfg instance)
# ---------------------------------------------------------------------------

def test_trace5_pass_no_cfg(tmp_path):
    """Trace 5: PASS, cfg_exists=FALSE — third independent topology."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-003"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 6 — 9 steps, PASS, cfg_exists=TRUE
# Actions: Start → RunLoop(pass) → CheckResult → AfterCheck →
#          WriteTla → WriteCfg(copy) → WriteTraces → Finish
# Final: spec_dir_has_tla=TRUE, spec_dir_has_cfg=TRUE, spec_dir_has_traces=TRUE
# ---------------------------------------------------------------------------

def test_trace6_pass_with_cfg(tmp_path):
    """Trace 6: PASS with .cfg present — all three outputs written to spec_dir."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-001"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=True)  # cfg_exists=TRUE

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    # --- final-state assertions (mirrors State 9 of Trace 6) ---
    assert result == LoopResult.PASS
    assert spec_path == ctx.spec_dir / f"{gwt_id}.tla"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()               # spec_dir_has_tla = TRUE
    assert (ctx.spec_dir / f"{gwt_id}.cfg").exists()               # spec_dir_has_cfg = TRUE
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()   # spec_dir_has_traces = TRUE

    written = json.loads((ctx.spec_dir / f"{gwt_id}_sim_traces.json").read_text())
    assert written == _FAKE_SIM_TRACES

    # CfgConditional: spec_dir_has_cfg=TRUE => cfg_exists=TRUE ✓
    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=True,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 7 — 5 steps, FAIL, cfg_exists=FALSE (second FAIL/no-cfg instance)
# ---------------------------------------------------------------------------

def test_trace7_fail_no_cfg(tmp_path):
    """Trace 7: FAIL, cfg_exists=FALSE — second independent FAIL/no-cfg topology."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-004"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(
        result=LoopResult.FAIL,
        error="syntax error in PlusCal",
        compiled_spec_path=None,
    )
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.FAIL
    assert spec_path is None
    assert not (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=False,
    )


# ---------------------------------------------------------------------------
# Trace 8 — 9 steps, PASS, cfg_exists=TRUE (second PASS/with-cfg instance)
# ---------------------------------------------------------------------------

def test_trace8_pass_with_cfg(tmp_path):
    """Trace 8: PASS, cfg_exists=TRUE — second independent PASS/with-cfg topology."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-005"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=True)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert spec_path == ctx.spec_dir / f"{gwt_id}.tla"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=True,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 9 — 9 steps, PASS, cfg_exists=FALSE (fourth PASS/no-cfg instance)
# ---------------------------------------------------------------------------

def test_trace9_pass_no_cfg(tmp_path):
    """Trace 9: PASS, cfg_exists=FALSE — fourth independent topology."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-006"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=True,
    )


# ---------------------------------------------------------------------------
# Trace 10 — 5 steps, FAIL, cfg_exists=TRUE (second FAIL/with-cfg instance)
# ---------------------------------------------------------------------------

def test_trace10_fail_with_cfg(tmp_path):
    """Trace 10: FAIL, cfg_exists=TRUE — nothing written even though cfg present at source."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-007"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    _make_compiled_spec(tmp_path, gwt_id, cfg_exists=True)

    status = LoopStatus(
        result=LoopResult.FAIL,
        error="type error in TLC",
        compiled_spec_path=None,
    )
    with _patch_run_loop(status):
        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.FAIL
    assert spec_path is None
    assert not (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}.cfg").exists()
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()

    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=True,
        traces_written=False,
    )


# ---------------------------------------------------------------------------
# Invariant-dedicated tests
# Each verifies one TLA+ invariant across >= 2 trace-derived topologies
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cfg_exists",
    [False, True],
    ids=["no_cfg (Trace 1)", "with_cfg (Trace 6)"],
)
def test_invariant_pass_implies_write(tmp_path, cfg_exists):
    """PassImpliesWrite: PASS always produces a .tla in spec_dir."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-INV-PASS"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=cfg_exists)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists(), (
        "PassImpliesWrite: PASS did not produce .tla"
    )
    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=cfg_exists,
        traces_written=True,
    )


@pytest.mark.parametrize(
    "cfg_exists",
    [False, True],
    ids=["no_cfg (Trace 2)", "with_cfg (Trace 4)"],
)
def test_invariant_fail_implies_no_write(tmp_path, cfg_exists):
    """FailImpliesNoWrite: FAIL never produces a .tla in spec_dir."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-INV-FAIL"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    _make_compiled_spec(tmp_path, gwt_id, cfg_exists=cfg_exists)

    status = LoopStatus(
        result=LoopResult.FAIL,
        error="test failure",
        compiled_spec_path=None,
    )
    with _patch_run_loop(status):
        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.FAIL
    assert not (ctx.spec_dir / f"{gwt_id}.tla").exists(), (
        "FailImpliesNoWrite: FAIL produced .tla unexpectedly"
    )
    _check_all_invariants(
        loop_result=result,
        spec_dir=ctx.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=cfg_exists,
        traces_written=False,
    )


def test_invariant_cfg_conditional(tmp_path):
    """CfgConditional: .cfg in spec_dir implies cfg existed at source.

    Topology A (Trace 6): cfg_exists=TRUE → spec_dir_has_cfg=TRUE
    Topology B (Trace 1): cfg_exists=FALSE → spec_dir_has_cfg=FALSE
    """
    gwt_id = "GWT-CFG-COND"

    # Topology A — cfg present at source → copied to spec_dir
    ctx_a = _make_ctx(tmp_path / "topo_a")
    dag_a = _register_gwt_and_save(ctx_a.state_root, gwt_id)
    spec_a = _make_compiled_spec(tmp_path / "topo_a", gwt_id, cfg_exists=True)
    with _patch_run_loop(LoopStatus(result=LoopResult.PASS, compiled_spec_path=spec_a)):
        asyncio.run(run_loop(ctx_a, gwt_id, max_retries=1, dag_path=dag_a))
    assert (ctx_a.spec_dir / f"{gwt_id}.cfg").exists(), (
        "CfgConditional: .cfg missing from spec_dir despite cfg_exists=TRUE"
    )
    _check_all_invariants(
        loop_result=LoopResult.PASS,
        spec_dir=ctx_a.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=True,
        traces_written=True,
    )

    # Topology B — no cfg at source → not copied to spec_dir
    ctx_b = _make_ctx(tmp_path / "topo_b")
    dag_b = _register_gwt_and_save(ctx_b.state_root, gwt_id)
    spec_b = _make_compiled_spec(tmp_path / "topo_b", gwt_id, cfg_exists=False)
    with _patch_run_loop(LoopStatus(result=LoopResult.PASS, compiled_spec_path=spec_b)):
        asyncio.run(run_loop(ctx_b, gwt_id, max_retries=1, dag_path=dag_b))
    assert not (ctx_b.spec_dir / f"{gwt_id}.cfg").exists(), (
        "CfgConditional: .cfg appeared in spec_dir despite cfg_exists=FALSE"
    )
    _check_all_invariants(
        loop_result=LoopResult.PASS,
        spec_dir=ctx_b.spec_dir,
        gwt_id=gwt_id,
        cfg_exists=False,
        traces_written=True,
    )


def test_invariant_traces_on_pass(tmp_path):
    """TracesOnPass: sim_traces written on PASS (non-empty), absent on FAIL.

    Topology PASS (Trace 1): loop_result=PASS, sim_traces non-empty → spec_dir_has_traces=TRUE
    Topology FAIL (Trace 2): loop_result=FAIL → spec_dir_has_traces=FALSE
    """
    gwt_id = "GWT-TRACES-INV"

    # PASS topology
    ctx_p = _make_ctx(tmp_path / "pass_topo")
    dag_p = _register_gwt_and_save(ctx_p.state_root, gwt_id)
    spec_p = _make_compiled_spec(tmp_path / "pass_topo", gwt_id, cfg_exists=False)
    with _patch_run_loop(LoopStatus(result=LoopResult.PASS, compiled_spec_path=spec_p)):
        asyncio.run(run_loop(ctx_p, gwt_id, max_retries=1, dag_path=dag_p))
    assert (ctx_p.spec_dir / f"{gwt_id}_sim_traces.json").exists(), (
        "TracesOnPass: PASS did not produce _sim_traces.json"
    )

    # FAIL topology
    ctx_f = _make_ctx(tmp_path / "fail_topo")
    dag_f = _register_gwt_and_save(ctx_f.state_root, gwt_id)
    with _patch_run_loop(
        LoopStatus(result=LoopResult.FAIL, error="fail", compiled_spec_path=None)
    ):
        asyncio.run(run_loop(ctx_f, gwt_id, max_retries=1, dag_path=dag_f))
    assert not (ctx_f.spec_dir / f"{gwt_id}_sim_traces.json").exists(), (
        "TracesOnPass: FAIL produced _sim_traces.json unexpectedly"
    )


def test_invariant_bounded_execution(tmp_path):
    """BoundedExecution: run_loop() exits on first PASS — attempt count <= MaxSteps."""
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-BOUNDED"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    call_count = 0

    def _process_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        return LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)

    mock_loop_inst = MagicMock()
    mock_loop_inst.process_response.side_effect = _process_side_effect

    with ExitStack() as stack:
        stack.enter_context(
            patch("registry.loop_runner._make_client", return_value=MagicMock())
        )
        stack.enter_context(
            patch(
                "registry.loop_runner._call_llm_with_client",
                new_callable=AsyncMock,
                return_value="fake",
            )
        )
        stack.enter_context(
            patch("registry.loop_runner.safe_disconnect", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch("registry.loop_runner.OneShotLoop", return_value=mock_loop_inst)
        )
        stack.enter_context(
            patch("registry.loop_runner.query_context", return_value=MagicMock())
        )
        stack.enter_context(
            patch("registry.loop_runner.format_prompt_context", return_value="")
        )
        stack.enter_context(patch("registry.loop_runner.write_result_file"))
        stack.enter_context(
            patch(
                "registry.one_shot_loop.run_tlc_simulate",
                return_value=_FAKE_SIM_TRACES,
            )
        )

        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=MAX_STEPS, dag_path=dag_path)
        )

    # PASS on attempt 1 → call_count=1, well within MAX_STEPS=5
    assert call_count <= MAX_STEPS, (
        f"BoundedExecution violated: {call_count} attempts > MAX_STEPS={MAX_STEPS}"
    )
    assert result == LoopResult.PASS


# ---------------------------------------------------------------------------
# Edge-case tests (derived from trace structure, minimally extended)
# ---------------------------------------------------------------------------

def test_edge_missing_dag_file(tmp_path):
    """run_loop returns (FAIL, None) immediately when the DAG file does not exist."""
    ctx = _make_ctx(tmp_path)
    missing_dag = ctx.state_root / "no_such_dag.json"

    with (
        patch("registry.loop_runner._make_client", return_value=MagicMock()),
        patch("registry.loop_runner.safe_disconnect", new_callable=AsyncMock),
    ):
        result, spec_path = asyncio.run(
            run_loop(ctx, "GWT-X", max_retries=1, dag_path=missing_dag)
        )

    assert result == LoopResult.FAIL
    assert spec_path is None
    assert not (ctx.spec_dir / "GWT-X.tla").exists()


def test_edge_gwt_not_in_dag(tmp_path):
    """run_loop returns (FAIL, None) when gwt_id is absent from the loaded DAG."""
    ctx = _make_ctx(tmp_path)
    dag = RegistryDag()
    dag_path = ctx.state_root / "dag.json"
    dag.save(dag_path)  # empty DAG — no nodes

    with (
        patch("registry.loop_runner._make_client", return_value=MagicMock()),
        patch("registry.loop_runner.safe_disconnect", new_callable=AsyncMock),
    ):
        result, spec_path = asyncio.run(
            run_loop(ctx, "GWT-MISSING", max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.FAIL
    assert spec_path is None


def test_edge_pass_empty_sim_traces(tmp_path):
    """PASS with run_tlc_simulate returning [] — _sim_traces.json NOT written.

    The implementation guards the write with `if sim_traces:`, so an empty list
    produces no file.  This test documents that contract.
    """
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-EMPTY-SIM"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status, sim_traces=[]):
        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    # Empty sim_traces → `if sim_traces:` is False → file not written
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()


def test_edge_pass_sim_traces_exception(tmp_path):
    """run_tlc_simulate raising does not abort run_loop — PASS still returned.

    The implementation catches simulation exceptions and logs a warning.
    The _sim_traces.json file is NOT written when the subprocess raises.
    """
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-SIM-ERR"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    mock_loop_inst = MagicMock()
    mock_loop_inst.process_response.return_value = status

    with ExitStack() as stack:
        stack.enter_context(
            patch("registry.loop_runner._make_client", return_value=MagicMock())
        )
        stack.enter_context(
            patch(
                "registry.loop_runner._call_llm_with_client",
                new_callable=AsyncMock,
                return_value="fake",
            )
        )
        stack.enter_context(
            patch("registry.loop_runner.safe_disconnect", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch("registry.loop_runner.OneShotLoop", return_value=mock_loop_inst)
        )
        stack.enter_context(
            patch("registry.loop_runner.query_context", return_value=MagicMock())
        )
        stack.enter_context(
            patch("registry.loop_runner.format_prompt_context", return_value="")
        )
        stack.enter_context(patch("registry.loop_runner.write_result_file"))
        stack.enter_context(
            patch(
                "registry.one_shot_loop.run_tlc_simulate",
                side_effect=RuntimeError("TLC subprocess crashed"),
            )
        )

        result, spec_path = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    # Exception during simulation is non-fatal — .tla written, PASS returned.
    # The implementation catches and logs; _sim_traces.json is NOT written.
    assert result == LoopResult.PASS
    assert spec_path == ctx.spec_dir / f"{gwt_id}.tla"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()
    assert not (ctx.spec_dir / f"{gwt_id}_sim_traces.json").exists()


def test_edge_spec_dir_autocreated_on_pass(tmp_path):
    """run_loop creates ctx.spec_dir when it does not yet exist.

    Derives from Trace 1 init; verifies the mkdir(parents=True, exist_ok=True) guard.
    """
    import shutil as _shutil

    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-MKDIR"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=False)

    # Remove spec_dir to confirm run_loop re-creates it on PASS
    if ctx.spec_dir.exists():
        _shutil.rmtree(ctx.spec_dir)
    assert not ctx.spec_dir.exists()

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert ctx.spec_dir.exists(), "spec_dir was not created by run_loop on PASS"
    assert (ctx.spec_dir / f"{gwt_id}.tla").exists()


def test_edge_tla_content_preserved(tmp_path):
    """The .tla and .cfg content is faithfully copied — not truncated or altered.

    Derives from Trace 6 init (PASS + cfg_exists=TRUE) with distinctive sentinels.
    """
    ctx = _make_ctx(tmp_path)
    gwt_id = "GWT-CONTENT"
    dag_path = _register_gwt_and_save(ctx.state_root, gwt_id)
    compiled_spec = _make_compiled_spec(tmp_path, gwt_id, cfg_exists=True)

    sentinel_tla = "---- MODULE Sentinel ----\nSPECIFICATION Spec\n\\* unique: abc123\n====\n"
    sentinel_cfg = "SPECIFICATION Spec\nINVARIANT SafetyProp\n\\* unique: xyz789\n"
    compiled_spec.write_text(sentinel_tla)
    compiled_spec.with_suffix(".cfg").write_text(sentinel_cfg)

    status = LoopStatus(result=LoopResult.PASS, compiled_spec_path=compiled_spec)
    with _patch_run_loop(status):
        result, _ = asyncio.run(
            run_loop(ctx, gwt_id, max_retries=1, dag_path=dag_path)
        )

    assert result == LoopResult.PASS
    assert (ctx.spec_dir / f"{gwt_id}.tla").read_text() == sentinel_tla
    assert (ctx.spec_dir / f"{gwt_id}.cfg").read_text() == sentinel_cfg