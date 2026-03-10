"""Tests for cw9 packaging as a global binary."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PYTHON_DIR = Path(__file__).resolve().parent.parent  # python/


def _build_wheel(tmp_path):
    """Helper: build wheel and return path.

    Tries `python -m build` first, falls back to `pip wheel`.
    """
    # Try python -m build first
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        capture_output=True, text=True, cwd=str(PYTHON_DIR),
    )
    if result.returncode != 0:
        # Fallback: use pip wheel
        result = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps",
             "--wheel-dir", str(tmp_path), str(PYTHON_DIR)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"
    wheels = list(tmp_path.glob("*.whl"))
    assert wheels
    return wheels[0]


# ── Phase 0: Wheel build and contents ──────────────────────────────────


class TestWheelBuild:
    def test_wheel_builds_successfully(self, tmp_path):
        """pyproject.toml has valid build-system; wheel builds."""
        wheel = _build_wheel(tmp_path)
        assert wheel.exists()
        assert wheel.suffix == ".whl"


class TestWheelContents:
    def test_wheel_contains_tla2tools_jar(self, tmp_path):
        """tla2tools.jar is bundled in the wheel."""
        wheel = _build_wheel(tmp_path)
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
            jar_files = [n for n in names if n.endswith("tla2tools.jar")]
            assert jar_files, f"tla2tools.jar not found in wheel. Contents:\n{names[:20]}"

    def test_wheel_contains_pluscal_templates(self, tmp_path):
        """PlusCal templates are bundled in the wheel."""
        wheel = _build_wheel(tmp_path)
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
            tla_files = [n for n in names if "templates/pluscal" in n and n.endswith(".tla")]
            assert len(tla_files) >= 4, f"Expected >=4 .tla templates, got {tla_files}"

    def test_wheel_contains_schema_templates(self, tmp_path):
        """Starter schema templates are bundled in the wheel."""
        wheel = _build_wheel(tmp_path)
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
            json_files = [n for n in names if "templates/schema" in n and n.endswith(".json")]
            assert len(json_files) >= 5, f"Expected >=5 schema templates, got {json_files}"


class TestDependencies:
    def test_claude_agent_sdk_declared(self):
        """claude_agent_sdk is in project dependencies."""
        import tomllib
        with open(PYTHON_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        deps = config["project"]["dependencies"]
        sdk_deps = [d for d in deps if "claude-agent-sdk" in d]
        assert sdk_deps, f"claude-agent-sdk not in dependencies: {deps}"


class TestModuleEntryPoint:
    def test_python_m_registry_shows_help(self):
        """`python -m registry --help` works."""
        result = subprocess.run(
            [sys.executable, "-m", "registry", "--help"],
            capture_output=True, text=True, cwd=str(PYTHON_DIR),
        )
        assert result.returncode == 0
        assert "cw9" in result.stdout.lower() or "codewriter" in result.stdout.lower()


# ── Phase 1: _resources module ──────────────────────────────────────────


class TestResources:
    def test_get_data_path_tla2tools(self):
        """get_data_path resolves tla2tools.jar to a real file."""
        from registry._resources import get_data_path
        jar = get_data_path("tools/tla2tools.jar")
        assert jar.exists(), f"JAR not found at {jar}"
        assert jar.stat().st_size > 1_000_000, "JAR suspiciously small"

    def test_get_template_dir_pluscal(self):
        """get_template_dir('pluscal') returns dir with .tla files."""
        from registry._resources import get_template_dir
        d = get_template_dir("pluscal")
        tla_files = list(d.glob("*.tla"))
        assert len(tla_files) >= 4, f"Expected >=4 .tla files in {d}"

    def test_get_template_dir_schema(self):
        """get_template_dir('schema') returns dir with .json files."""
        from registry._resources import get_template_dir
        d = get_template_dir("schema")
        json_files = list(d.glob("*.json"))
        assert len(json_files) >= 5, f"Expected >=5 .json files in {d}"

    def test_get_data_path_missing_raises(self):
        """get_data_path raises FileNotFoundError for missing files."""
        from registry._resources import get_data_path
        with pytest.raises(FileNotFoundError):
            get_data_path("nonexistent/file.txt")


class TestInstalledMode:
    def test_is_installed_mode_false_in_repo(self):
        """In repo checkout, is_installed_mode() returns False."""
        from registry._resources import is_installed_mode
        # We're running tests from the repo, so this should be False
        assert is_installed_mode() is False

    def test_is_installed_mode_uses_templates_dir_heuristic(self):
        """Heuristic checks for ENGINE_ROOT/templates/ directory."""
        from registry import _resources
        # Verify the heuristic target exists in our repo
        engine_root = _resources._REPO_ENGINE_ROOT
        assert (engine_root / "templates").is_dir()


# ── Phase 4: tla2tools resolution ──────────────────────────────────────


class TestTla2toolsResolution:
    def test_find_tla2tools_from_package_resources(self, tmp_path, monkeypatch):
        """_find_tla2tools falls back to package resources."""
        from registry.one_shot_loop import _find_tla2tools
        # Set cwd to tmp_path (no tools/ here) and clear env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TLA2TOOLS_JAR", raising=False)
        # Call with no tools_dir
        jar_path = _find_tla2tools(tools_dir=None)
        assert Path(jar_path).exists()
        assert jar_path.endswith("tla2tools.jar")

    def test_find_tla2tools_prefers_explicit_dir(self, tmp_path):
        """Explicit tools_dir takes priority over package resources."""
        from registry.one_shot_loop import _find_tla2tools
        jar = tmp_path / "tla2tools.jar"
        jar.write_bytes(b"fake")
        result = _find_tla2tools(tools_dir=str(tmp_path))
        assert result == str(jar)


# ── Phase 5: Integration tests (slow) ──────────────────────────────────


def _install_into_venv(tmp_path):
    """Create a uv venv and install cw9 into it. Returns (venv_path, env_dict)."""
    venv = tmp_path / "venv"
    subprocess.run(
        ["uv", "venv", str(venv)],
        check=True, capture_output=True,
    )
    # Use uv pip install (uv venv doesn't include pip by default)
    import os
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv)
    result = subprocess.run(
        ["uv", "pip", "install", str(PYTHON_DIR)],
        check=True, capture_output=True, text=True,
        env=env,
    )
    return venv, env


@pytest.mark.slow
class TestGlobalInstall:
    def test_uv_tool_install_and_init(self, tmp_path):
        """Full integration: uv venv + uv pip install → cw9 init → cw9 extract."""
        if not shutil.which("uv"):
            pytest.skip("uv not installed")

        venv, env = _install_into_venv(tmp_path)
        cw9_bin = str(venv / "bin" / "cw9")

        # Test cw9 --help
        result = subprocess.run(
            [cw9_bin, "--help"], capture_output=True, text=True,
        )
        assert result.returncode == 0, f"cw9 --help failed:\n{result.stderr}"

        # Test cw9 init
        project = tmp_path / "test-project"
        project.mkdir()
        result = subprocess.run(
            [cw9_bin, "init", str(project)], capture_output=True, text=True,
        )
        assert result.returncode == 0, f"cw9 init failed:\n{result.stderr}"

        # Verify .cw9/ structure
        assert (project / ".cw9" / "config.toml").exists()
        assert (project / ".cw9" / "dag.json").exists()
        schemas = list((project / ".cw9" / "schema").glob("*.json"))
        assert len(schemas) >= 5

        # Test cw9 extract
        result = subprocess.run(
            [cw9_bin, "extract", str(project)], capture_output=True, text=True,
        )
        assert result.returncode == 0, f"cw9 extract failed:\n{result.stderr}"

    def test_python_m_registry_in_venv(self, tmp_path):
        """python -m registry works in installed venv."""
        if not shutil.which("uv"):
            pytest.skip("uv not installed")

        venv, env = _install_into_venv(tmp_path)
        python_in_venv = str(venv / "bin" / "python")

        result = subprocess.run(
            [python_in_venv, "-m", "registry", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
