"""Tests for ProjectContext — path resolution for self-hosting vs external projects."""

from pathlib import Path

import pytest

from registry.context import ProjectContext


ENGINE_ROOT = Path(__file__).parent.parent.parent


class TestSelfHosting:
    def test_all_roots_same(self):
        ctx = ProjectContext.self_hosting(ENGINE_ROOT)
        assert ctx.engine_root == ctx.target_root == ctx.state_root

    def test_schema_dir_is_legacy(self):
        ctx = ProjectContext.self_hosting(ENGINE_ROOT)
        assert ctx.schema_dir == ENGINE_ROOT / "schema"

    def test_spec_dir_is_legacy(self):
        ctx = ProjectContext.self_hosting(ENGINE_ROOT)
        assert ctx.spec_dir == ENGINE_ROOT / "templates" / "pluscal" / "instances"

    def test_tools_dir(self):
        ctx = ProjectContext.self_hosting(ENGINE_ROOT)
        assert ctx.tools_dir == ENGINE_ROOT / "tools"


class TestExternal:
    def test_three_roots_distinct(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.engine_root == ENGINE_ROOT
        assert ctx.target_root == target
        assert ctx.state_root == target / ".cw9"

    def test_schema_dir_under_cw9(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.schema_dir == target / ".cw9" / "schema"

    def test_spec_dir_under_cw9(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.spec_dir == target / ".cw9" / "specs"

    def test_artifact_dir_under_cw9(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.artifact_dir == target / ".cw9" / "bridge"

    def test_session_dir_under_cw9(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.session_dir == target / ".cw9" / "sessions"

    def test_test_output_dir_under_target(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.test_output_dir == target / "tests" / "generated"

    def test_engine_paths_point_to_engine(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        assert ctx.template_dir == ENGINE_ROOT / "templates" / "pluscal"
        assert ctx.tools_dir == ENGINE_ROOT / "tools"
        assert ctx.python_dir == ENGINE_ROOT / "python"


class TestFromTarget:
    def test_detects_self_hosting(self):
        ctx = ProjectContext.from_target(ENGINE_ROOT)
        assert ctx.engine_root == ctx.target_root

    def test_detects_external(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.from_target(target, ENGINE_ROOT)
        assert ctx.engine_root != ctx.target_root
        assert ctx.state_root == target / ".cw9"

    def test_auto_detects_engine_root(self, tmp_path):
        """from_target with engine_root=None should auto-detect from __file__."""
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.from_target(target)
        assert ctx.engine_root == ENGINE_ROOT

    def test_resolves_relative_paths(self):
        ctx = ProjectContext.from_target(Path("."), ENGINE_ROOT)
        assert ctx.target_root.is_absolute()
        assert ctx.engine_root.is_absolute()

    def test_frozen(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        with pytest.raises(AttributeError):
            ctx.engine_root = tmp_path
