# Phase 2: ProjectContext Resolves Bundled Assets When engine_root Absent

This is the deepest refactor. The key insight from the review:

> ProjectContext.external() should resolve template_dir and tools_dir from package
> resources, NOT from engine_root. The engine_root concept should become optional/absent
> for installed mode.

## Design

**Two modes of `from_target()`:**

1. **Repo checkout** (engine_root on disk) — current behavior, unchanged
2. **Installed mode** (no engine_root) — bundled assets from `_resources`, project state from `.cw9/`

**`config.toml` change (Option B — backwards-compatible):**
- `engine_root` becomes optional in config.toml
- When absent, `from_target()` uses `_resources` for bundled assets
- Existing `.cw9/config.toml` files with engine_root continue to work

## Behaviors

### Behavior 2.1: `from_target()` works when config.toml has no engine_root
**Given** a `.cw9/config.toml` with no `[engine]` section
**When** we call `ProjectContext.from_target(target)`
**Then** `template_dir` and `tools_dir` resolve via `_resources`, and `schema_dir`/`spec_dir`/etc. resolve under `.cw9/`

### Behavior 2.2: `from_target()` still works with existing engine_root in config
**Given** a `.cw9/config.toml` with `engine.root = "/some/path"`
**When** we call `ProjectContext.from_target(target)` and that path exists
**Then** behavior is unchanged — template_dir and tools_dir derive from engine_root

### Behavior 2.3: `from_target()` falls back to _resources when engine_root path doesn't exist
**Given** a `.cw9/config.toml` with `engine.root = "/deleted/path"` (stale)
**When** we call `ProjectContext.from_target(target)`
**Then** it falls back to `_resources` instead of crashing

### Behavior 2.4: self_hosting() mode is unchanged
**Given** code running from repo checkout where `target_root == engine_root`
**When** we call `ProjectContext.from_target(engine_root)`
**Then** returns `self_hosting()` with original ENGINE_ROOT-based paths

### Behavior 2.5: `installed()` classmethod uses target_root for python_dir
**Given** installed mode (no engine_root)
**When** we call `ProjectContext.installed(target_root=...)`
**Then** template_dir and tools_dir come from `_resources`, python_dir resolves to target_root (the project being operated on)

---

## TDD Cycle

### 2.1: from_target() without engine_root

#### Red: Write Failing Test
**File**: `python/tests/test_context.py` (append to existing)
```python
class TestInstalledModeContext:
    def test_from_target_no_engine_root_in_config(self, tmp_path):
        """from_target works when config.toml has no engine section."""
        # Create minimal .cw9/ structure
        cw9 = tmp_path / ".cw9"
        cw9.mkdir()
        (cw9 / "config.toml").write_text("[project]\n")
        (cw9 / "schema").mkdir()
        (cw9 / "specs").mkdir()
        (cw9 / "bridge").mkdir()
        (cw9 / "sessions").mkdir()

        ctx = ProjectContext.from_target(tmp_path)

        # State paths resolve under .cw9/
        assert ctx.state_root == cw9
        assert ctx.schema_dir == cw9 / "schema"
        assert ctx.spec_dir == cw9 / "specs"

        # Bundled asset paths are real directories with files
        assert ctx.template_dir.is_dir()
        assert ctx.tools_dir.is_dir()
        assert (ctx.tools_dir / "tla2tools.jar").exists()

    def test_from_target_no_engine_root_template_dir_has_tla_files(self, tmp_path):
        """template_dir from package resources contains .tla files."""
        cw9 = tmp_path / ".cw9"
        cw9.mkdir()
        (cw9 / "config.toml").write_text("[project]\n")
        for d in ["schema", "specs", "bridge", "sessions"]:
            (cw9 / d).mkdir()

        ctx = ProjectContext.from_target(tmp_path)
        tla_files = list(ctx.template_dir.glob("*.tla"))
        assert len(tla_files) >= 4
```

#### Green: Modify `context.py`

**Key changes to `context.py`:**

```python
from registry._resources import get_template_dir, get_data_path, is_installed_mode

@classmethod
def from_target(cls, target_root: Path, engine_root: Path | None = None) -> ProjectContext:
    target_root = Path(target_root).resolve()

    if engine_root is None:
        # Try config.toml first
        config_path = target_root / ".cw9" / "config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            engine_root_str = config.get("engine", {}).get("root")
            if engine_root_str:
                candidate = Path(engine_root_str).resolve()
                if candidate.is_dir():
                    engine_root = candidate
                # else: stale path, fall through to installed-mode

        # Fallback: repo auto-detection (only if templates/ exists there)
        if engine_root is None:
            candidate = Path(__file__).resolve().parent.parent.parent
            if (candidate / "templates").is_dir():
                engine_root = candidate

    else:
        engine_root = Path(engine_root).resolve()

    # Route to appropriate constructor
    if engine_root is not None and target_root == engine_root:
        return cls.self_hosting(engine_root)
    elif engine_root is not None:
        return cls.external(engine_root, target_root)
    else:
        return cls.installed(target_root)

@classmethod
def installed(cls, target_root: Path) -> ProjectContext:
    """Installed mode — bundled assets from package resources."""
    target_root = Path(target_root).resolve()
    state_root = target_root / ".cw9"
    return cls(
        engine_root=None,         # No engine_root in installed mode
        target_root=target_root,
        state_root=state_root,
        # Bundled assets via _resources
        template_dir=get_template_dir("pluscal"),
        tools_dir=get_data_path("tools"),
        python_dir=target_root,   # Use target project root as working directory
        # State paths (.cw9 layout)
        schema_dir=state_root / "schema",
        spec_dir=state_root / "specs",
        artifact_dir=state_root / "bridge",
        session_dir=state_root / "sessions",
        # Target paths
        test_output_dir=target_root / "tests" / "generated",
    )
```

**NOTE**: The `frozen=True` dataclass needs `engine_root` to accept `None`. `python_dir` stays as `Path` (resolves to `target_root` in installed mode, avoiding None-dereference bugs at 10+ callsites). Change type annotation for `engine_root` only:

```python
@dataclass(frozen=True)
class ProjectContext:
    engine_root: Path | None     # None in installed mode
    target_root: Path
    state_root: Path
    template_dir: Path
    tools_dir: Path
    python_dir: Path             # target_root in installed mode (unchanged type)
    schema_dir: Path
    spec_dir: Path
    artifact_dir: Path
    session_dir: Path
    test_output_dir: Path
```

### 2.2–2.3: Backwards compatibility and stale paths

#### Red: Write Failing Test
```python
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
        cw9 = target / ".cw9"
        cw9.mkdir()
        (cw9 / "config.toml").write_text(
            f'[engine]\nroot = "{engine}"\n'
        )
        for d in ["schema", "specs", "bridge", "sessions"]:
            (cw9 / d).mkdir()

        ctx = ProjectContext.from_target(target)
        assert ctx.engine_root == engine
        assert ctx.template_dir == engine / "templates" / "pluscal"

    def test_from_target_stale_engine_root_falls_back(self, tmp_path):
        """Stale engine_root in config falls back to installed mode."""
        target = tmp_path / "project"
        target.mkdir()
        cw9 = target / ".cw9"
        cw9.mkdir()
        (cw9 / "config.toml").write_text(
            '[engine]\nroot = "/nonexistent/deleted/path"\n'
        )
        for d in ["schema", "specs", "bridge", "sessions"]:
            (cw9 / d).mkdir()

        ctx = ProjectContext.from_target(target)
        # Should fall back to installed mode, not crash
        assert ctx.tools_dir.is_dir()
        assert (ctx.tools_dir / "tla2tools.jar").exists() or not is_installed_mode()
```

#### Green
Already handled by the `candidate.is_dir()` check in the modified `from_target()`.

### 2.4: self_hosting unchanged

#### Red: Verify existing tests still pass
The existing `test_context.py` tests for self_hosting mode must continue to pass unchanged.

```python
    def test_self_hosting_uses_engine_root(self):
        """self_hosting() still uses repo ENGINE_ROOT paths."""
        from registry.context import ProjectContext
        engine = Path(__file__).resolve().parent.parent.parent.parent
        ctx = ProjectContext.self_hosting(engine)
        assert ctx.engine_root == engine
        assert ctx.template_dir == engine / "templates" / "pluscal"
```

---

## Success Criteria

**Automated:**
- [x] `from_target()` works with no engine section in config.toml
- [x] `from_target()` works with valid engine_root (backwards-compat)
- [x] `from_target()` handles stale engine_root gracefully
- [x] `self_hosting()` behavior unchanged
- [x] `installed()` resolves template_dir to a dir with .tla files
- [x] `installed()` resolves tools_dir to a dir with tla2tools.jar
- [x] `engine_root` accepts None; `python_dir` is always a valid Path (target_root in installed mode)
- [x] All 346 existing tests still pass
