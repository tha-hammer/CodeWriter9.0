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

    def test_from_target_reads_config_toml(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        cw9 = target / ".cw9"
        cw9.mkdir()
        config = cw9 / "config.toml"
        config.write_text(f'[engine]\nroot = "{ENGINE_ROOT}"\n')
        ctx = ProjectContext.from_target(target)  # no engine_root arg
        assert ctx.engine_root == ENGINE_ROOT

    def test_from_target_falls_back_without_config(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.from_target(target)
        assert ctx.engine_root == ENGINE_ROOT

    def test_explicit_engine_root_overrides_config(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        cw9 = target / ".cw9"
        cw9.mkdir()
        config = cw9 / "config.toml"
        config.write_text('[engine]\nroot = "/bogus/path"\n')
        ctx = ProjectContext.from_target(target, ENGINE_ROOT)
        assert ctx.engine_root == ENGINE_ROOT

    def test_frozen(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.external(ENGINE_ROOT, target)
        with pytest.raises(AttributeError):
            ctx.engine_root = tmp_path


class TestInstalledModeContext:
    def _make_cw9_dir(self, tmp_path, config_text="[project]\n"):
        """Create minimal .cw9/ structure."""
        cw9 = tmp_path / ".cw9"
        cw9.mkdir()
        (cw9 / "config.toml").write_text(config_text)
        for d in ["schema", "specs", "bridge", "sessions"]:
            (cw9 / d).mkdir()
        return cw9

    def test_from_target_no_engine_root_in_config(self, tmp_path):
        """from_target works when config.toml has no engine section."""
        cw9 = self._make_cw9_dir(tmp_path)
        ctx = ProjectContext.from_target(tmp_path)

        # State paths resolve under .cw9/
        assert ctx.state_root == cw9
        assert ctx.schema_dir == cw9 / "schema"
        assert ctx.spec_dir == cw9 / "specs"

        # Note: in repo checkout, from_target auto-detects engine_root
        # so template_dir and tools_dir will point to ENGINE_ROOT
        assert ctx.template_dir.is_dir()
        assert ctx.tools_dir.is_dir()

    def test_from_target_no_engine_root_template_dir_has_tla_files(self, tmp_path):
        """template_dir contains .tla files."""
        self._make_cw9_dir(tmp_path)
        ctx = ProjectContext.from_target(tmp_path)
        tla_files = list(ctx.template_dir.glob("*.tla"))
        assert len(tla_files) >= 4

    def test_from_target_with_valid_engine_root(self, tmp_path):
        """Existing config.toml with valid engine_root works unchanged."""
        engine = tmp_path / "engine"
        engine.mkdir()
        (engine / "templates").mkdir()
        (engine / "templates" / "pluscal").mkdir()
        (engine / "tools").mkdir()
        (engine / "python").mkdir()

        target = tmp_path / "project"
        target.mkdir()
        self._make_cw9_dir(target, f'[engine]\nroot = "{engine}"\n')

        ctx = ProjectContext.from_target(target)
        assert ctx.engine_root == engine
        assert ctx.template_dir == engine / "templates" / "pluscal"

    def test_from_target_stale_engine_root_falls_back(self, tmp_path):
        """Stale engine_root in config falls back gracefully."""
        target = tmp_path / "project"
        target.mkdir()
        self._make_cw9_dir(target, '[engine]\nroot = "/nonexistent/deleted/path"\n')

        ctx = ProjectContext.from_target(target)
        # Should fall back (to auto-detection in repo, or installed mode),
        # not crash
        assert ctx.tools_dir.is_dir()

    def test_installed_mode_uses_resources(self, tmp_path):
        """installed() resolves template_dir and tools_dir from _resources."""
        ctx = ProjectContext.installed(tmp_path)
        assert ctx.engine_root is None
        assert ctx.template_dir.is_dir()
        assert ctx.tools_dir.is_dir()
        tla_files = list(ctx.template_dir.glob("*.tla"))
        assert len(tla_files) >= 4
        assert (ctx.tools_dir / "tla2tools.jar").exists()

    def test_installed_python_dir_is_target_root(self, tmp_path):
        """In installed mode, python_dir resolves to target_root."""
        ctx = ProjectContext.installed(tmp_path)
        assert ctx.python_dir == tmp_path.resolve()

    def test_self_hosting_uses_engine_root(self):
        """self_hosting() still uses repo ENGINE_ROOT paths."""
        ctx = ProjectContext.self_hosting(ENGINE_ROOT)
        assert ctx.engine_root == ENGINE_ROOT
        assert ctx.template_dir == ENGINE_ROOT / "templates" / "pluscal"
