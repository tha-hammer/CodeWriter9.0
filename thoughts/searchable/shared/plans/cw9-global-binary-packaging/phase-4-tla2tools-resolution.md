# Phase 4: `_find_tla2tools()` Gains Package Resource Fallback

## Problem

`one_shot_loop.py:248-269` defines `_find_tla2tools()` which searches:
1. `tools_dir / "tla2tools.jar"` (from ProjectContext)
2. `Path("tools") / "tla2tools.jar"` (cwd fallback)
3. `TLA2TOOLS_JAR` environment variable

When installed globally, `tools_dir` comes from `_resources.get_data_path("tools")` (set up in Phase 2), so this should already work. But `_find_tla2tools()` should also have a direct package-resource fallback as a safety net.

## Behaviors

### Behavior 4.1: `_find_tla2tools()` finds jar from package resources
**Given** `tools_dir=None` and no jar in cwd and no env var
**When** we call `_find_tla2tools()`
**Then** it finds the jar from `registry._data.tools` via importlib.resources

### Behavior 4.2: `_find_tla2tools()` still prefers explicit tools_dir
**Given** `tools_dir="/custom/path"` with a jar present
**When** we call `_find_tla2tools("/custom/path")`
**Then** it returns the custom path (existing behavior unchanged)

---

## TDD Cycle

### 4.1: Package resource fallback

#### Red: Write Failing Test
**File**: `python/tests/test_packaging.py` (append)
```python
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
```

#### Green: Modify `one_shot_loop.py`

Add a package-resource fallback to `_find_tla2tools()`:

```python
def _find_tla2tools(tools_dir: str | Path | None = None) -> str:
    """Locate the tla2tools.jar file.

    Checks in order: tools_dir, cwd/tools, TLA2TOOLS_JAR env var,
    package resources (installed mode).
    """
    if tools_dir:
        jar = Path(tools_dir) / _TLA2TOOLS_JAR_NAME
        if jar.exists():
            return str(jar)

    # Try relative to cwd (legacy fallback)
    jar = Path("tools") / _TLA2TOOLS_JAR_NAME
    if jar.exists():
        return str(jar)

    # Try environment variable
    env_jar = os.environ.get("TLA2TOOLS_JAR")
    if env_jar and Path(env_jar).exists():
        return env_jar

    # Try package resources (installed mode)
    try:
        from registry._resources import get_data_path
        jar = get_data_path(f"tools/{_TLA2TOOLS_JAR_NAME}")
        if jar.exists():
            return str(jar)
    except (ImportError, FileNotFoundError):
        pass

    raise FileNotFoundError(
        f"Cannot find {_TLA2TOOLS_JAR_NAME}. "
        f"Set TLA2TOOLS_JAR env var or install cw9 with bundled tools."
    )
```

---

## Success Criteria

**Automated:**
- [x] `_find_tla2tools(None)` finds jar from package resources
- [x] `_find_tla2tools("/custom")` still prefers explicit path
- [x] All existing TLC-related tests pass
- [x] All 346+ tests pass
