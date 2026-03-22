import pytest
from pathlib import Path

from registry.context import ProjectContext


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_engine_tree(root: Path) -> None:
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "pluscal").mkdir(exist_ok=True)
    (root / "templates" / "pluscal" / "instances").mkdir(exist_ok=True)
    (root / "python").mkdir(exist_ok=True)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def engine_root(tmp_path: Path) -> Path:
    _make_engine_tree(tmp_path)
    return tmp_path


@pytest.fixture
def ctx(engine_root: Path) -> ProjectContext:
    return ProjectContext.self_hosting(engine_root)


# ─── Invariant Tests ─────────────────────────────────────────────────────────

def test_roots_aligned_target_equals_engine_root(ctx: ProjectContext, engine_root: Path) -> None:
    assert ctx.target_root == engine_root.resolve()


def test_roots_aligned_state_equals_engine_root(ctx: ProjectContext, engine_root: Path) -> None:
    assert ctx.state_root == engine_root.resolve()


def test_engine_root_attribute_is_set(ctx: ProjectContext, engine_root: Path) -> None:
    assert ctx.engine_root == engine_root.resolve()


def test_spec_dir_equals_instances_path(ctx: ProjectContext, engine_root: Path) -> None:
    expected = engine_root.resolve() / "templates" / "pluscal" / "instances"
    assert ctx.spec_dir == expected


def test_spec_dir_not_cw9_specs_path(ctx: ProjectContext, engine_root: Path) -> None:
    cw9_specs = engine_root.resolve() / ".cw9" / "specs"
    assert ctx.spec_dir != cw9_specs


def test_is_self_hosting_is_true(ctx: ProjectContext) -> None:
    assert ctx.is_self_hosting is True


def test_paths_equal_consistent(ctx: ProjectContext) -> None:
    paths_equal = (ctx.target_root == ctx.engine_root) and (ctx.state_root == ctx.engine_root)
    assert paths_equal is True


def test_type_invariant_roots_are_path_instances(ctx: ProjectContext) -> None:
    assert isinstance(ctx.engine_root, Path)
    assert isinstance(ctx.target_root, Path)
    assert isinstance(ctx.state_root, Path)


def test_type_invariant_spec_dir_is_path_instance(ctx: ProjectContext) -> None:
    assert isinstance(ctx.spec_dir, Path)


def test_type_invariant_is_self_hosting_is_bool(ctx: ProjectContext) -> None:
    assert isinstance(ctx.is_self_hosting, bool)


# ─── Scenario Tests ───────────────────────────────────────────────────────────

def test_self_hosting_correct_composite(ctx: ProjectContext, engine_root: Path) -> None:
    root = engine_root.resolve()
    assert ctx.target_root == root
    assert ctx.state_root == root
    assert ctx.spec_dir == root / "templates" / "pluscal" / "instances"
    assert ctx.spec_dir != root / ".cw9" / "specs"
    assert ctx.is_self_hosting is True
    assert (ctx.target_root == root) and (ctx.state_root == root)


def test_self_hosting_resolves_path_to_absolute(tmp_path: Path) -> None:
    _make_engine_tree(tmp_path)
    result = ProjectContext.self_hosting(tmp_path)
    assert result.engine_root.is_absolute()
    assert result.target_root.is_absolute()
    assert result.state_root.is_absolute()
    assert result.spec_dir.is_absolute()


def test_spec_dir_is_descendant_of_engine_root(ctx: ProjectContext) -> None:
    assert ctx.engine_root in ctx.spec_dir.parents


def test_all_engine_derived_paths_descend_from_engine_root(ctx: ProjectContext) -> None:
    root = ctx.engine_root
    assert root in ctx.spec_dir.parents, (
        f"spec_dir={ctx.spec_dir!r} is not a descendant of engine_root {root!r}"
    )
    informal_attrs = ("template_dir", "python_dir", "artifact_dir")
    missing = [attr for attr in informal_attrs if not hasattr(ctx, attr)]
    if missing:
        pytest.skip(
            f"Informal attrs not present on ProjectContext, skipping: {', '.join(missing)}"
        )
    for attr in informal_attrs:
        derived: Path = getattr(ctx, attr)
        assert root in derived.parents, (
            f"{attr}={derived!r} is not a descendant of engine_root {root!r}"
        )


def test_two_calls_yield_independent_contexts(tmp_path: Path) -> None:
    root_a = tmp_path / "project_a"
    root_b = tmp_path / "project_b"
    for root in (root_a, root_b):
        root.mkdir()
        _make_engine_tree(root)
    ctx_a = ProjectContext.self_hosting(root_a)
    ctx_b = ProjectContext.self_hosting(root_b)
    assert ctx_a.engine_root != ctx_b.engine_root
    assert ctx_a.target_root != ctx_b.target_root
    assert ctx_a.state_root != ctx_b.state_root
    assert ctx_a.spec_dir != ctx_b.spec_dir


def test_is_self_hosting_false_for_external_context(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    _make_engine_tree(engine)
    external_ctx = ProjectContext.external(engine, target)
    assert external_ctx.is_self_hosting is False


def test_self_hosting_spec_dir_differs_from_external_spec_dir(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()
    _make_engine_tree(engine)
    self_ctx = ProjectContext.self_hosting(engine)
    ext_ctx = ProjectContext.external(engine, target)
    assert self_ctx.spec_dir != ext_ctx.spec_dir
    assert "instances" in str(self_ctx.spec_dir)
    assert ".cw9" in str(ext_ctx.spec_dir)


def test_context_is_frozen_rejects_mutation(ctx: ProjectContext, engine_root: Path) -> None:
    with pytest.raises((AttributeError, TypeError)):
        ctx.target_root = engine_root / "mutated"  # type: ignore[misc]


def test_constructor_terminates_and_returns_context(tmp_path: Path) -> None:
    _make_engine_tree(tmp_path)
    result = ProjectContext.self_hosting(tmp_path)
    assert result is not None
    assert isinstance(result, ProjectContext)