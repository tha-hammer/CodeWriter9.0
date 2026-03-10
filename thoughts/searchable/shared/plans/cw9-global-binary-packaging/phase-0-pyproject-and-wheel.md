# Phase 0: Build Infrastructure — Wheel Builds with All Data Files

## Behaviors

### Behavior 0.1: pyproject.toml declares a valid build-system
**Given** the current pyproject.toml with no `[build-system]` section
**When** we add setuptools build-system and build a wheel
**Then** `python -m build` produces a `.whl` file without errors

### Behavior 0.2: Built wheel contains bundled data files
**Given** data files copied to `registry/_data/` and declared in `[tool.setuptools.package-data]`
**When** we build the wheel and inspect its contents
**Then** the wheel contains `registry/_data/tools/tla2tools.jar`, `registry/_data/templates/pluscal/*.tla`, and `registry/_data/templates/schema/*.json`

### Behavior 0.3: claude_agent_sdk is a declared dependency
**Given** `loop_runner.py` imports `claude_agent_sdk` at module level
**When** the package is installed from the wheel
**Then** `claude_agent_sdk` is installed as a dependency

### Behavior 0.4: `python -m registry` invokes the CLI
**Given** a `registry/__main__.py` that calls `main()`
**When** we run `python -m registry --help`
**Then** the CLI help text is printed

---

## TDD Cycle

### 0.1: pyproject.toml build-system

#### Red: Write Failing Test
**File**: `python/tests/test_packaging.py`
```python
"""Tests for cw9 packaging as a global binary."""
import subprocess
import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent  # python/


class TestWheelBuild:
    def test_wheel_builds_successfully(self, tmp_path):
        """pyproject.toml has valid build-system; wheel builds."""
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
            capture_output=True, text=True, cwd=str(PYTHON_DIR),
        )
        assert result.returncode == 0, f"Wheel build failed:\n{result.stderr}"
        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) == 1, f"Expected 1 wheel, got {len(wheels)}"
```

#### Green: Minimal Implementation
**File**: `python/pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "codewriter-registry"
version = "0.1.0"
description = "DAG-based resource registry for CodeWriter"
requires-python = ">=3.11"
dependencies = [
    "claude-agent-sdk>=0.1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "build"]

[project.scripts]
cw9 = "registry.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### 0.2: Bundled data files in wheel

#### Red: Write Failing Test
**File**: `python/tests/test_packaging.py` (append)
```python
import zipfile

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


def _build_wheel(tmp_path):
    """Helper: build wheel and return path."""
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        capture_output=True, text=True, cwd=str(PYTHON_DIR),
    )
    assert result.returncode == 0, f"Build failed:\n{result.stderr}"
    wheels = list(tmp_path.glob("*.whl"))
    assert wheels
    return wheels[0]
```

#### Green: Minimal Implementation

1. Create the `_data/` directory structure inside the package:
```bash
mkdir -p python/registry/_data/tools
mkdir -p python/registry/_data/templates/pluscal
mkdir -p python/registry/_data/templates/schema

# Copy data files
cp tools/tla2tools.jar python/registry/_data/tools/
cp templates/pluscal/*.tla python/registry/_data/templates/pluscal/
cp templates/schema/*.json python/registry/_data/templates/schema/
```

2. Add package-data to pyproject.toml:
```toml
[tool.setuptools.package-data]
registry = [
    "_data/tools/*.jar",
    "_data/templates/pluscal/*.tla",
    "_data/templates/schema/*.json",
]
```

3. Add `_data/__init__.py` (empty, marks as package for importlib.resources):
```python
# Bundled data files for cw9 CLI.
# Access via registry._resources module.
```

### 0.3: claude_agent_sdk dependency

#### Red: Write Failing Test
```python
class TestDependencies:
    def test_claude_agent_sdk_declared(self):
        """claude_agent_sdk is in project dependencies."""
        import tomllib
        with open(PYTHON_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        deps = config["project"]["dependencies"]
        sdk_deps = [d for d in deps if "claude-agent-sdk" in d]
        assert sdk_deps, f"claude-agent-sdk not in dependencies: {deps}"
```

#### Green
Already satisfied by the pyproject.toml changes in 0.1.

### 0.4: `python -m registry` entry point

#### Red: Write Failing Test
```python
class TestModuleEntryPoint:
    def test_python_m_registry_shows_help(self):
        """`python -m registry --help` works."""
        result = subprocess.run(
            [sys.executable, "-m", "registry", "--help"],
            capture_output=True, text=True, cwd=str(PYTHON_DIR),
        )
        assert result.returncode == 0
        assert "cw9" in result.stdout.lower() or "codewriter" in result.stdout.lower()
```

#### Green: Create `__main__.py`
**File**: `python/registry/__main__.py`
```python
"""Allow running as `python -m registry`."""
import sys
from registry.cli import main

sys.exit(main())
```

---

## Success Criteria

**Automated:**
- [x] `python -m build --wheel` succeeds
- [x] Wheel contains `_data/tools/tla2tools.jar`
- [x] Wheel contains 4+ PlusCal templates
- [x] Wheel contains 5+ schema templates
- [x] `claude-agent-sdk` in declared dependencies
- [x] `python -m registry --help` prints usage
- [x] All 346 existing tests still pass

**Manual:**
- [ ] `pip install dist/*.whl` into a fresh venv succeeds
