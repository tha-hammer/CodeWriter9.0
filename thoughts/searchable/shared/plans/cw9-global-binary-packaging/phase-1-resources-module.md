# Phase 1: `_resources.py` — importlib.resources Helper Module

## Behaviors

### Behavior 1.1: `get_data_path()` returns real filesystem path for bundled files
**Given** data files bundled in `registry/_data/`
**When** we call `get_data_path("tools/tla2tools.jar")`
**Then** it returns a `Path` to a readable file on disk

### Behavior 1.2: `get_template_dir()` returns path to PlusCal templates
**Given** templates bundled in `registry/_data/templates/pluscal/`
**When** we call `get_template_dir("pluscal")`
**Then** it returns a `Path` to a directory containing `*.tla` files

### Behavior 1.3: `get_schema_template_dir()` returns path to starter schemas
**Given** schemas bundled in `registry/_data/templates/schema/`
**When** we call `get_template_dir("schema")`
**Then** it returns a `Path` to a directory containing `*.json` files

### Behavior 1.4: `is_installed_mode()` detects whether running from installed package vs repo
**Given** the CLI is running
**When** we call `is_installed_mode()`
**Then** it returns `True` when installed via pip/uv (no repo ENGINE_ROOT) and `False` when running from repo checkout

---

## TDD Cycle

### 1.1–1.3: Data path resolution

#### Red: Write Failing Test
**File**: `python/tests/test_packaging.py` (append)
```python
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
        import pytest
        with pytest.raises(FileNotFoundError):
            get_data_path("nonexistent/file.txt")
```

#### Green: Minimal Implementation
**File**: `python/registry/_resources.py`
```python
"""Resolve bundled data files for the cw9 CLI.

When installed via pip/uv/pipx, data files live inside the package at
registry/_data/. When running from a repo checkout, they live at
ENGINE_ROOT/templates/ and ENGINE_ROOT/tools/.

This module provides a uniform API that works in both modes.
"""
from __future__ import annotations

from importlib.resources import files, as_file
from pathlib import Path


# The _data package anchor for importlib.resources
_DATA_ANCHOR = "registry._data"

# Repo-layout ENGINE_ROOT (only valid in dev mode)
_REPO_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent


def is_installed_mode() -> bool:
    """Detect whether running from installed package vs repo checkout.

    Heuristic: if _REPO_ENGINE_ROOT / "templates" exists, we're in repo mode.
    """
    return not (_REPO_ENGINE_ROOT / "templates").is_dir()


def get_data_path(relative_path: str) -> Path:
    """Resolve a bundled data file to a real filesystem path.

    Args:
        relative_path: Path relative to _data/, e.g. "tools/tla2tools.jar"

    Returns:
        Absolute Path to the file on disk.

    Raises:
        FileNotFoundError: If the file doesn't exist in either location.
    """
    if not is_installed_mode():
        # Repo checkout: map _data/ paths back to ENGINE_ROOT layout
        repo_path = _map_to_repo_path(relative_path)
        if repo_path.exists():
            return repo_path

    # Installed mode: resolve from package data
    parts = relative_path.split("/")
    resource = files(_DATA_ANCHOR)
    for part in parts:
        resource = resource.joinpath(part)

    # files() returns a Traversable; we need a real Path.
    # NOTE: This uses Path(str(resource)) which requires extracted (non-zip)
    # package layout. uv tool install and pipx install always extract.
    # Zip-based imports (zipapp, --target with zip) are not supported.
    resolved = Path(str(resource))
    if resolved.exists():
        return resolved

    raise FileNotFoundError(
        f"Bundled data file not found: {relative_path}\n"
        f"  Checked package: {resource}\n"
        f"  Checked repo: {_map_to_repo_path(relative_path)}\n"
        f"  If you installed cw9 via pip/uv and see this error, "
        f"try reinstalling: `uv tool install --force .`"
    )


def get_template_dir(kind: str) -> Path:
    """Get the directory for a template kind ('pluscal' or 'schema').

    Returns:
        Path to the template directory.
    """
    return get_data_path(f"templates/{kind}")


def _map_to_repo_path(relative_path: str) -> Path:
    """Map a _data/-relative path back to the repo ENGINE_ROOT layout.

    _data/tools/tla2tools.jar → ENGINE_ROOT/tools/tla2tools.jar
    _data/templates/pluscal/x.tla → ENGINE_ROOT/templates/pluscal/x.tla
    """
    return _REPO_ENGINE_ROOT / relative_path
```

### 1.4: Installed mode detection

#### Red: Write Failing Test
```python
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
```

#### Green
Already satisfied by the implementation above.

---

## Success Criteria

**Automated:**
- [x] `get_data_path("tools/tla2tools.jar")` returns a valid path
- [x] `get_template_dir("pluscal")` contains >=4 .tla files
- [x] `get_template_dir("schema")` contains >=5 .json files
- [x] `get_data_path("nonexistent")` raises FileNotFoundError
- [x] `is_installed_mode()` returns False in repo checkout
- [x] All 346 existing tests still pass
