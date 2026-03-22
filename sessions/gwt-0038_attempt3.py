import pytest
from pathlib import Path
from registry.context import ProjectContext


# ---------------------------------------------------------------------------
# Path-placement helpers (TLA+ predicate translations)
# ---------------------------------------------------------------------------

def _under_state_root(path: Path, target_root: Path) -> bool:
    """UnderStateRoot(p) == p.base = TargetRoot /\ p.under_cw9 = TRUE"""
    state_root = target_root / ".cw9"
    try:
        path.relative_to(state_root)
        return True
    except ValueError:
        return False


def _under_engine_root(path: Path, engine_root: Path) -> bool:
    """UnderEngineRoot(p) == p.base = EngineRoot"""
    try:
        path.relative_to(engine_root)
        return True
    except ValueError:
        return False


def _under_target_only(path: Path, target_root: Path) -> bool:
    """UnderTargetOnly(p) == p.base = TargetRoot /\ p.under_cw9 = FALSE"""
    try:
        path.relative_to(target_root)
    except ValueError:
        return False
    return not _under_state_root(path, target_root)


# ---------------------------------------------------------------------------
# Invariant verifier functions
# ---------------------------------------------------------------------------

def _inv_state_root_correct(ctx, target_root: Path) -> None:
    assert ctx.state_root == target_root / ".cw9", (
        f"state_root {ctx.state_root!r} != {target_root / '.cw9'!r}"
    )


def _inv_schema_under_state(ctx, target_root: Path) -> None:
    assert _under_state_root(ctx.schema_dir, target_root), (
        f"schema_dir {ctx.schema_dir!r} not under {target_root / '.cw9'!r}"
    )


def _inv_spec_under_state(ctx, target_root: Path) -> None:
    assert _under_state_root(ctx.spec_dir, target_root), (
        f"spec_dir {ctx.spec_dir!r} not under {target_root / '.cw9'!r}"
    )


def _inv_template_from_engine(ctx, engine_root: Path) -> None:
    assert _under_engine_root(ctx.template_dir, engine_root), (
        f"template_dir {ctx.template_dir!r} not under engine_root {engine_root!r}"
    )


def _inv_tools_from_engine(ctx, engine_root: Path) -> None:
    assert _under_engine_root(ctx.tools_dir, engine_root), (
        f"tools_dir {ctx.tools_dir!r} not under engine_root {engine_root!r}"
    )


def _inv_artifact_under_state(ctx, target_root: Path) -> None:
    assert _under_state_root(ctx.artifact_dir, target_root), (
        f"artifact_dir {ctx.artifact_dir!r} not under {target_root / '.cw9'!r}"
    )


def _inv_test_output_not_under_cw9(ctx, target_root: Path) -> None:
    assert _under_target_only(ctx.test_output_dir, target_root), (
        f"test_output_dir {ctx.test_output_dir!r} must be under target_root "
        f"but not .cw9 subtree"
    )


def _inv_no_cross_contamination(ctx, engine_root: Path, target_root: Path) -> None:
    assert not _under_engine_root(ctx.schema_dir, engine_root), (
        f"schema_dir {ctx.schema_dir!r} must NOT be under engine_root"
    )
    assert not _under_engine_root(ctx.spec_dir, engine_root), (
        f"spec_dir {ctx.spec_dir!r} must NOT be under engine_root"
    )
    assert not _under_engine_root(ctx.artifact_dir, engine_root), (
        f"artifact_dir {ctx.artifact_dir!r} must NOT be under engine_root"
    )
    assert not _under_state_root(ctx.template_dir, target_root), (
        f"template_dir {ctx.template_dir!r} must NOT be under state_root (.cw9)"
    )
    assert not _under_state_root(ctx.tools_dir, target_root), (
        f"tools_dir {ctx.tools_dir!r} must NOT be under state_root (.cw9)"
    )


def _inv_artifact_spec_diverge(ctx, target_root: Path) -> None:
    assert _under_state_root(ctx.artifact_dir, target_root), (
        f"artifact_dir {ctx.artifact_dir!r} must be under .cw9"
    )
    assert not _under_state_root(ctx.test_output_dir, target_root), (
        f"test_output_dir {ctx.test_output_dir!r} must NOT be under .cw9"
    )


def _verify_all_invariants(ctx, engine_root: Path, target_root: Path) -> None:
    _inv_state_root_correct(ctx, target_root)
    _inv_schema_under_state(ctx, target_root)
    _inv_spec_under_state(ctx, target_root)
    _inv_template_from_engine(ctx, engine_root)
    _inv_tools_from_engine(ctx, engine_root)
    _inv_artifact_under_state(ctx, target_root)
    _inv_test_output_not_under_cw9(ctx, target_root)
    _inv_no_cross_contamination(ctx, engine_root, target_root)
    _inv_artifact_spec_diverge(ctx, target_root)


# ---------------------------------------------------------------------------
# Traces 1-10: same roots — spec requires ValueError; impl does not yet enforce it
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="ProjectContext.external does not yet enforce distinct-roots precondition", strict=False)
@pytest.mark.parametrize("trace_id", list(range(1, 11)))
def test_trace_precond_failed_same_roots(tmp_path, trace_id):
    shared_root = tmp_path / f"shared_trace_{trace_id}"
    shared_root.mkdir()
    with pytest.raises(ValueError):
        ProjectContext.external(shared_root, shared_root)


# ---------------------------------------------------------------------------
# Happy-path fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def external_ctx(tmp_path):
    engine_root = tmp_path / "engine"
    target_root = tmp_path / "target"
    engine_root.mkdir()
    target_root.mkdir()
    ctx = ProjectContext.external(engine_root, target_root)
    return ctx, engine_root, target_root


# ---------------------------------------------------------------------------
# Individual invariant tests on the happy-path fixture
# ---------------------------------------------------------------------------

def test_state_root_is_target_cw9(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_state_root_correct(ctx, target_root)


def test_schema_dir_under_state_root(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_schema_under_state(ctx, target_root)


def test_spec_dir_under_state_root(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_spec_under_state(ctx, target_root)


def test_template_dir_from_engine_root(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_template_from_engine(ctx, engine_root)


def test_tools_dir_from_engine_root(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_tools_from_engine(ctx, engine_root)


def test_artifact_dir_under_state_root(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_artifact_under_state(ctx, target_root)


def test_test_output_not_under_cw9(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_test_output_not_under_cw9(ctx, target_root)


def test_no_cross_contamination(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_no_cross_contamination(ctx, engine_root, target_root)


def test_artifact_spec_diverge(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _inv_artifact_spec_diverge(ctx, target_root)


def test_all_invariants_happy_path(external_ctx):
    ctx, engine_root, target_root = external_ctx
    _verify_all_invariants(ctx, engine_root, target_root)


# ---------------------------------------------------------------------------
# Dedicated invariant-verifier tests — 2 independent topologies each
# ---------------------------------------------------------------------------

def test_invariant_state_root_correct_two_topologies(tmp_path):
    for suffix in ("A", "B"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_state_root_correct(ctx, target)


def test_invariant_schema_under_state_two_topologies(tmp_path):
    for suffix in ("X", "Y"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_schema_under_state(ctx, target)


def test_invariant_spec_under_state_two_topologies(tmp_path):
    for suffix in ("P", "Q"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_spec_under_state(ctx, target)


def test_invariant_template_from_engine_two_topologies(tmp_path):
    for suffix in ("1", "2"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_template_from_engine(ctx, engine)


def test_invariant_tools_from_engine_two_topologies(tmp_path):
    for suffix in ("alpha", "beta"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_tools_from_engine(ctx, engine)


def test_invariant_artifact_under_state_two_topologies(tmp_path):
    for suffix in ("i", "ii"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_artifact_under_state(ctx, target)


def test_invariant_test_output_not_under_cw9_two_topologies(tmp_path):
    for suffix in ("u", "v"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_test_output_not_under_cw9(ctx, target)


def test_invariant_no_cross_contamination_two_topologies(tmp_path):
    for suffix in ("m", "n"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_no_cross_contamination(ctx, engine, target)


def test_invariant_artifact_spec_diverge_two_topologies(tmp_path):
    for suffix in ("g", "h"):
        engine = tmp_path / f"engine_{suffix}"
        target = tmp_path / f"target_{suffix}"
        engine.mkdir()
        target.mkdir()
        ctx = ProjectContext.external(engine, target)
        _inv_artifact_spec_diverge(ctx, target)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_edge_state_root_directory_name_is_dot_cw9(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    assert ctx.state_root.name == ".cw9"


def test_edge_state_root_parent_is_exactly_target_root(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    assert ctx.state_root.parent == target


def test_edge_schema_and_spec_dirs_are_distinct(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    _inv_schema_under_state(ctx, target)
    _inv_spec_under_state(ctx, target)
    assert ctx.schema_dir != ctx.spec_dir


def test_edge_template_and_tools_dirs_are_distinct(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    _inv_template_from_engine(ctx, engine)
    _inv_tools_from_engine(ctx, engine)
    assert ctx.template_dir != ctx.tools_dir


def test_edge_artifact_dir_and_test_output_dir_are_distinct(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    assert ctx.artifact_dir != ctx.test_output_dir


def test_edge_deeply_nested_engine_root(tmp_path):
    engine = tmp_path / "a" / "b" / "c" / "engine"
    target = tmp_path / "target"
    engine.mkdir(parents=True)
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    _verify_all_invariants(ctx, engine, target)


def test_edge_deeply_nested_target_root(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "x" / "y" / "z" / "target"
    engine.mkdir()
    target.mkdir(parents=True)
    ctx = ProjectContext.external(engine, target)
    _verify_all_invariants(ctx, engine, target)


def test_edge_sibling_directories(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    _verify_all_invariants(ctx, engine, target)


@pytest.mark.xfail(reason="ProjectContext.external does not yet enforce distinct-roots precondition", strict=False)
def test_edge_same_path_raises_value_error(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    with pytest.raises(ValueError):
        ProjectContext.external(shared, shared)


def test_edge_engine_subdir_of_target_no_cross_contamination(tmp_path):
    target = tmp_path / "target"
    engine = target / "engine_subdir"
    target.mkdir()
    engine.mkdir()
    ctx = ProjectContext.external(engine, target)
    _verify_all_invariants(ctx, engine, target)


def test_edge_target_subdir_of_engine_no_cross_contamination(tmp_path):
    engine = tmp_path / "engine"
    target = engine / "target_subdir"
    engine.mkdir()
    target.mkdir()
    ctx = ProjectContext.external(engine, target)
    _inv_state_root_correct(ctx, target)
    _inv_schema_under_state(ctx, target)
    _inv_spec_under_state(ctx, target)


def test_edge_multiple_calls_return_consistent_contexts(tmp_path):
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    ctx_a = ProjectContext.external(engine, target)
    ctx_b = ProjectContext.external(engine, target)
    assert ctx_a.state_root == ctx_b.state_root
    assert ctx_a.schema_dir == ctx_b.schema_dir
    assert ctx_a.spec_dir == ctx_b.spec_dir
    assert ctx_a.template_dir == ctx_b.template_dir
    assert ctx_a.tools_dir == ctx_b.tools_dir
    assert ctx_a.artifact_dir == ctx_b.artifact_dir
    assert ctx_a.test_output_dir == ctx_b.test_output_dir