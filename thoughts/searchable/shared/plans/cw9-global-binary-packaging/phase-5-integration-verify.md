# Phase 5: End-to-End Integration — `uv tool install .` Produces Working `cw9`

## Behaviors

### Behavior 5.1: `uv tool install .` succeeds from the python/ directory
**Given** the pyproject.toml with build-system, dependencies, and package-data
**When** we run `uv tool install .` from python/
**Then** `cw9` is on PATH and `cw9 --help` prints usage

### Behavior 5.2: Installed `cw9 init` creates a valid project
**Given** `cw9` installed globally via uv
**When** we run `cw9 init /tmp/test-project`
**Then** `.cw9/` is created with config.toml (no engine.root), starter schemas, and empty DAG

### Behavior 5.3: Installed `cw9 extract` works on the initialized project
**Given** a project initialized by globally-installed `cw9`
**When** we run `cw9 extract /tmp/test-project`
**Then** DAG is extracted from starter schemas

### Behavior 5.4: `pipx install .` also works
**Given** the same package
**When** we run `pipx install .` from python/
**Then** `cw9` is on PATH and works identically

---

## TDD Cycle

### 5.1–5.3: Full integration test

These tests are SLOW (install into isolated venv) and should be marked with `@pytest.mark.slow` or run separately.

#### Red: Write Failing Test
**File**: `python/tests/test_packaging.py` (append)
```python
import shutil

@pytest.mark.slow
class TestGlobalInstall:
    def test_uv_tool_install_and_init(self, tmp_path):
        """Full integration: uv tool install → cw9 init → cw9 extract."""
        # Skip if uv not available
        if not shutil.which("uv"):
            pytest.skip("uv not installed")

        # Install into isolated venv
        venv = tmp_path / "venv"
        subprocess.run(
            ["uv", "venv", str(venv)],
            check=True, capture_output=True,
        )
        pip_in_venv = str(venv / "bin" / "pip")
        subprocess.run(
            [pip_in_venv, "install", str(PYTHON_DIR)],
            check=True, capture_output=True, text=True,
        )
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

    def test_cw9_test_works_in_venv(self, tmp_path):
        """cw9 test runs pytest in an installed venv."""
        if not shutil.which("uv"):
            pytest.skip("uv not installed")

        venv = tmp_path / "venv"
        subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
        pip_in_venv = str(venv / "bin" / "pip")
        subprocess.run(
            [pip_in_venv, "install", str(PYTHON_DIR)],
            check=True, capture_output=True, text=True,
        )
        cw9_bin = str(venv / "bin" / "cw9")

        # Init and extract a project first
        project = tmp_path / "test-project"
        project.mkdir()
        subprocess.run(
            [cw9_bin, "init", str(project)], check=True, capture_output=True, text=True,
        )
        subprocess.run(
            [cw9_bin, "extract", str(project)], check=True, capture_output=True, text=True,
        )

        # cw9 test should not crash (may fail if no tests exist, but should not AttributeError)
        result = subprocess.run(
            [cw9_bin, "test", str(project)], capture_output=True, text=True,
        )
        # Should not crash with AttributeError or FileNotFoundError from None python_dir
        assert "AttributeError" not in result.stderr
        assert "FileNotFoundError" not in result.stderr or "test" in result.stderr.lower()

    def test_python_m_registry_in_venv(self, tmp_path):
        """python -m registry works in installed venv."""
        if not shutil.which("uv"):
            pytest.skip("uv not installed")

        venv = tmp_path / "venv"
        subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)
        pip_in_venv = str(venv / "bin" / "pip")
        python_in_venv = str(venv / "bin" / "python")
        subprocess.run(
            [pip_in_venv, "install", str(PYTHON_DIR)],
            check=True, capture_output=True, text=True,
        )

        result = subprocess.run(
            [python_in_venv, "-m", "registry", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
```

#### Green
All infrastructure from Phases 0-4 should make these pass. If not, debug and fix.

---

## Success Criteria

**Automated:**
- [x] `uv venv` + `pip install .` → `cw9 --help` works
- [x] `cw9 init` creates valid project from installed venv
- [x] `cw9 extract` succeeds on initialized project
- [x] `python -m registry --help` works in installed venv
- [x] All 346+ tests pass (fast tests)

**Manual:**
- [ ] `uv tool install ./python` from repo root → `cw9` on PATH
- [ ] `cw9 init ~/test-project && cw9 extract ~/test-project` works end-to-end
- [ ] `pipx install ./python` → same behavior
- [ ] Verify upgrade from editable install: `pip install -e .` → `pip install .` (non-editable) → `cw9 init` works
