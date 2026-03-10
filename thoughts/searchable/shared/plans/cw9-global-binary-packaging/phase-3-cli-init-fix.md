# Phase 3: `cw9 init` Uses Package Resources for Templates

## Problem

`cli.py:20` defines `ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent` and uses it at line 74-77 to find starter schema templates:

```python
schema_templates_dir = ENGINE_ROOT / "templates" / "schema"
```

And at line 65-67 to write the engine path into config.toml:

```python
_CONFIG_TEMPLATE = """...\nroot = "{engine_root}"\n..."""
config_path.write_text(_CONFIG_TEMPLATE.format(engine_root=str(ENGINE_ROOT)))
```

Both break when installed.

## Behaviors

### Behavior 3.1: `cw9 init` copies starter schemas from package resources
**Given** `cw9` is installed globally (no repo ENGINE_ROOT on disk)
**When** we run `cw9 init /tmp/myproject`
**Then** starter schemas are copied from `registry._data.templates.schema`, not from `ENGINE_ROOT/templates/schema`

### Behavior 3.2: `cw9 init` writes config.toml without engine_root when installed
**Given** installed mode (no ENGINE_ROOT)
**When** we run `cw9 init /tmp/myproject`
**Then** config.toml has `[project]` section but no `[engine]` section with a root path

### Behavior 3.3: `cw9 init` still writes engine_root when running from repo
**Given** dev mode (ENGINE_ROOT on disk)
**When** we run `cw9 init /tmp/myproject`
**Then** config.toml includes `engine.root = "<repo path>"` as before

### Behavior 3.4: Remove the module-level ENGINE_ROOT constant
**Given** cli.py line 20 defines ENGINE_ROOT at import time
**When** we refactor to use `_resources`
**Then** the constant is removed; engine_root is resolved per-invocation via `_resources.is_installed_mode()`

---

## TDD Cycle

### 3.1–3.2: Init with package resources

#### Red: Write Failing Test
**File**: `python/tests/test_cli.py` (append to existing TestInit class or new class)
```python
class TestInitInstalledMode:
    def test_init_copies_schemas_from_package_resources(self, tmp_path, monkeypatch):
        """cw9 init copies starter schemas even without ENGINE_ROOT."""
        # Simulate installed mode by monkeypatching
        import registry._resources as res
        monkeypatch.setattr(res, "is_installed_mode", lambda: True)

        target = tmp_path / "myproject"
        target.mkdir()
        result = main(["init", str(target)])
        assert result == 0

        schema_dir = target / ".cw9" / "schema"
        schemas = list(schema_dir.glob("*.json"))
        assert len(schemas) >= 5, f"Expected >=5 starter schemas, got {schemas}"

    def test_init_config_no_engine_root_installed_mode(self, tmp_path, monkeypatch):
        """In installed mode, config.toml omits engine.root."""
        import registry._resources as res
        monkeypatch.setattr(res, "is_installed_mode", lambda: True)

        target = tmp_path / "myproject"
        target.mkdir()
        main(["init", str(target)])

        config = (target / ".cw9" / "config.toml").read_text()
        assert "engine" not in config.lower() or "root" not in config
```

#### Green: Modify `cli.py`

Replace:
```python
ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent
```

With usage of `_resources`:
```python
from registry._resources import is_installed_mode, get_template_dir

def _get_engine_root() -> Path | None:
    """Get ENGINE_ROOT if running from repo checkout, else None."""
    if is_installed_mode():
        return None
    return Path(__file__).resolve().parent.parent.parent
```

Replace the schema copy logic in `cmd_init()`:
```python
# Copy starter schema templates
from registry._resources import get_template_dir
schema_templates_dir = get_template_dir("schema")
if schema_templates_dir.is_dir() and not list((state_root / "schema").glob("*.json")):
    for tmpl in schema_templates_dir.glob("*.json"):
        shutil.copy2(tmpl, state_root / "schema" / tmpl.name)
```

Replace config.toml generation:
```python
engine_root = _get_engine_root()
if engine_root:
    config_text = f'[engine]\nroot = "{engine_root}"\n\n[project]\n'
else:
    config_text = "# Installed mode — bundled assets from package\n\n[project]\n"
config_path.write_text(config_text)
```

And the `ctx = ProjectContext.from_target(target, ENGINE_ROOT)` call:
```python
ctx = ProjectContext.from_target(target, _get_engine_root())
```

### 3.3: Dev mode backwards-compat

#### Red: Verify existing init tests still pass
Existing `test_cli.py::TestInit` tests must continue to pass — they run in repo checkout mode.

---

## Success Criteria

**Automated:**
- [x] `cw9 init` copies schemas from package resources in installed mode
- [x] Config.toml omits engine.root in installed mode
- [x] Config.toml includes engine.root in dev mode
- [x] ENGINE_ROOT module-level constant removed from cli.py
- [x] All existing TestInit tests pass
- [x] All 346+ tests pass
