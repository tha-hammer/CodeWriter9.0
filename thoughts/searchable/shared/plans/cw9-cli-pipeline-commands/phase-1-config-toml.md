╔═══════════════════════════════════════╗
║  PHASE 1: config.toml → from_target  ║
╚═══════════════════════════════════════╝

## Overview

Wire `tomllib` parsing into `from_target()` so it reads `engine_root` from `.cw9/config.toml` when present. Removes the need to pass `engine_root` explicitly.

## Changes Required

### 1. `python/registry/context.py` — `from_target()`

**Current** (lines 60-76): `engine_root` defaults to `Path(__file__).parent.parent.parent` when `None`.

**Change**: Before the `__file__`-based fallback, check for `.cw9/config.toml` and read `engine.root` from it.

```python
import tomllib

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
                engine_root = Path(engine_root_str).resolve()
        # Fallback to auto-detection from __file__
        if engine_root is None:
            engine_root = Path(__file__).resolve().parent.parent.parent
    else:
        engine_root = Path(engine_root).resolve()

    if target_root == engine_root:
        return cls.self_hosting(engine_root)
    return cls.external(engine_root, target_root)
```

### 2. `python/registry/cli.py` — Simplify calls

**Current**: `ProjectContext.from_target(target, ENGINE_ROOT)` (lines 80, 115).

**Change**: `ProjectContext.from_target(target)` — let config.toml provide it. Keep `ENGINE_ROOT` for `cmd_init` (which writes the config).

### 3. Fix `_CONFIG_TEMPLATE` quoting

**Current** (line 27): `root = {engine_root!r}` uses Python `repr()` which produces `'/path'` with single quotes.

**Change**: Use double quotes for valid TOML: `root = "{engine_root}"`.

## Tests

Add to `python/tests/test_context.py`:

```python
class TestConfigTomlParsing:
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
```

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_context.py -v` — all pass including new tests
- [x] `python3 -m pytest tests/test_cli.py -v` — no regressions
