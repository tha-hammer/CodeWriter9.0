---
date: "2026-03-12T16:55:07-04:00"
researcher: DustyForge
git_commit: a4c18b9f86908b816fabdaf2a779bfd1099a68c1
branch: master
repository: CodeWriter9.0
topic: "Wiring run_loop_bridge.py into the CW9 application bundle"
tags: [research, codebase, run_loop_bridge, packaging, cli, pipeline, cw7-integration]
status: complete
last_updated: "2026-03-12"
last_updated_by: DustyForge
---

# Research: Wiring run_loop_bridge.py into the CW9 Application Bundle

**Date**: 2026-03-12T16:55:07-04:00
**Researcher**: DustyForge
**Git Commit**: `a4c18b9`
**Branch**: `master`
**Repository**: CodeWriter9.0

## Research Question

How does `run_loop_bridge.py` need to be wired into the application bundle? What exists today, what's missing, and what are the integration surfaces?

## Summary

`run_loop_bridge.py` is currently a **standalone developer script** in `python/tools/` — it is not part of the installed `cw9` package. It orchestrates the full CW9 pipeline (setup → loop → bridge) by importing and calling `registry.cli:main` as a Python function. The `python/tools/` directory has **no `__init__.py`**, is **not declared in `pyproject.toml`**, and has **no entry point**. The file bootstraps itself onto `sys.path` at runtime to make `registry` importable.

To wire it into the bundle, the pipeline orchestrator needs to become a new `cw9` subcommand (e.g., `cw9 pipeline`) following the established `cmd_*` function pattern in `registry/cli.py`, with its CW7 extraction dependency (`cw7_extract.py`) either moved into `registry/` or left as an optional import.

## Detailed Findings

### 📦 Current Packaging State

**File**: `python/pyproject.toml`

| Aspect | Current State |
|---|---|
| Package name | `codewriter-registry` v0.3.0 |
| Entry point | `cw9 = "registry.cli:main"` (sole console script) |
| Installed package | `registry/` only |
| `tools/` in package? | **No** — not declared anywhere in pyproject.toml |
| `tools/__init__.py`? | **No** — namespace package via sys.path hack |
| Bundled data | `registry/_data/` (jar, templates) via `[tool.setuptools.package-data]` |

### 🔌 Current run_loop_bridge.py Integration Points

**File**: `python/tools/run_loop_bridge.py`

The script depends on these internal modules:

| Import | Source | How Imported |
|---|---|---|
| `registry.cli.main` | Installed package | `from registry.cli import main as cw9_main` |
| `tools.cw7_extract.extract` | Peer tool script | `from tools.cw7_extract import extract as cw7_extract` (deferred) |
| `tools.cw7_extract.copy_context_files` | Peer tool script | `from tools.cw7_extract import copy_context_files, build_plan_path_map` (deferred) |

The bootstrap hack at **lines 44-47**:
```python
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))
```

### 🏗️ CLI Subcommand Pattern (What to Match)

**File**: `python/registry/cli.py`

Every subcommand follows this exact pattern:

**1. Handler function** (`cli.py` various lines):
```python
def cmd_<name>(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1
    # ... deferred imports, business logic ...
    return 0  # or 1
```

**2. Subparser registration** (`cli.py:572-621`):
```python
p_<name> = sub.add_parser("<name>", help="...")
p_<name>.add_argument("target_dir", nargs="?", default=".")
# additional args...
```

**3. Dispatch branch** (`cli.py:624-642`):
```python
elif args.command == "<name>":
    return cmd_<name>(args)
```

### 🔗 Existing Subcommands (8 total)

| Subcommand | Handler | Line |
|---|---|---|
| `init` | `cmd_init()` | 56 |
| `status` | `cmd_status()` | 137 |
| `extract` | `cmd_extract()` | 173 |
| `loop` | `cmd_loop()` | 220 |
| `bridge` | `cmd_bridge()` | 250 |
| `gen-tests` | `cmd_gen_tests()` | 311 |
| `register` | `cmd_register()` | 407 |
| `test` | `cmd_test()` | 516 |

### 📂 python/tools/ Directory Contents

| File | Purpose | Imported Outside tools/? |
|---|---|---|
| `cw7_extract.py` | CW7 DB → register JSON + context file copy | Only by other tools/ scripts |
| `run_loop_bridge.py` | Production pipeline orchestrator (real LLM) | Only by `tests/test_run_loop_bridge.py` |
| `test_loop_bridge.py` | Test/validation harness (synthetic-spec capable) | Not imported anywhere |

### 🧩 What run_loop_bridge.py Does That cli.py Doesn't

`run_loop_bridge.py` composes existing subcommands into a pipeline and adds CW7-specific orchestration:

1. **Phase 0 — Setup**: `init` → `extract` → CW7 DB extract → `register` (with stdin/stdout mocking)
2. **Phase 1 — Loop**: Iterates GWTs, calls `loop` per-GWT with context file mapping
3. **Phase 2 — Bridge**: Iterates verified GWTs, calls `bridge` per-GWT, validates artifacts
4. **CW7 DB integration**: Reads from a SQLite DB (`cw7_extract.py`), builds plan-path ID mappings
5. **Session inference**: Detects session ID from `--plan-path-dir` directory name
6. **Context file routing**: Maps `gwt_id → criterion_id → plan_path_id → .md file`

### 🎯 Integration Surfaces for Wiring

The key surfaces where `run_loop_bridge.py` needs to connect:

| Surface | Current | For Bundle |
|---|---|---|
| `cw7_extract.extract()` | `from tools.cw7_extract import extract` | Needs to move to `registry/` or become optional import |
| `cw7_extract.build_plan_path_map()` | Peer import | Same as above |
| `cw7_extract.copy_context_files()` | Peer import | Same as above |
| Pipeline phases | Direct calls to `cw9_main([...])` | Should call `cmd_*` functions directly |
| `sys.stdin`/`sys.stdout` mock for register | `unittest.mock.patch` | Should use internal register API instead |
| Hardcoded CW7 DB path | `~/Dev/CodeWriter7/.cw7/gate-outputs.db` | Should use env var or arg only |
| `_inline_fixture()` | Fallback when DB missing | May stay as-is for dev convenience |

### 📋 Related Beads Issues

- **CodeWriter9.0-59h** (P2, open): "Package cw9 as globally installable binary" — tracks the overall packaging work
- **CodeWriter9.0-5bc** (P1, open): "CW9 CLI Pipeline Commands" — parent epic for all CLI subcommands

### 🔍 Packaging Test Infrastructure

**File**: `python/tests/test_packaging.py` (236 lines)

Existing packaging tests cover:
- Wheel build verification
- Bundled data file presence (jar, templates, schemas)
- `_resources.get_data_path()` and `get_template_dir()` resolution
- `is_installed_mode()` heuristic
- Global install integration test (`uv venv` + `uv pip install` + `cw9 --help/init/extract`)

## Code References

- `python/tools/run_loop_bridge.py:1-490` — Full pipeline orchestrator
- `python/tools/cw7_extract.py:1-184` — CW7 database extraction + context file utilities
- `python/registry/cli.py:567-646` — `main()` function with subparser setup + dispatch
- `python/registry/cli.py:220-247` — `cmd_loop()` — example handler pattern
- `python/registry/cli.py:250-308` — `cmd_bridge()` — example handler pattern
- `python/registry/_resources.py:22-27` — `is_installed_mode()` detection
- `python/pyproject.toml:17-18` — Console script entry point declaration
- `python/tests/test_packaging.py` — Packaging test suite
- `python/tests/test_run_loop_bridge.py` — 44 tests for run_loop_bridge (just written)

## Architecture Documentation

### Current Architecture: tools/ as Standalone Scripts

```
User Shell
    │
    ├── cw9 init/extract/loop/bridge/...   (installed binary)
    │       │
    │       └── registry/cli.py:main()
    │               └── cmd_*(args)
    │
    └── python tools/run_loop_bridge.py    (standalone script, NOT installed)
            │
            ├── sys.path hack → import registry
            ├── from tools.cw7_extract import ...
            └── cw9_main(["init", ...])  ← calls cli.main() as function
                cw9_main(["loop", ...])
                cw9_main(["bridge", ...])
```

### Dual-Mode Resource Resolution

```
is_installed_mode()?
    │
    ├── True  → importlib.resources.files("registry._data")
    │           (wheel/venv/site-packages layout)
    │
    └── False → ENGINE_ROOT / "tools/tla2tools.jar"
                ENGINE_ROOT / "templates/..."
                (dev repo checkout layout)
```

## Open Questions

1. Should `cw7_extract.py` move into `registry/` as a proper module, or remain external with the pipeline command doing an optional/deferred import?
2. Should the new `cw9 pipeline` command call `cmd_*` functions directly instead of going through `main([...])`? This would eliminate the stdin/stdout mock hack for `register`.
3. Should `_inline_fixture()` remain as a dev fallback, or should it be removed when the command is an installed subcommand?
4. Does the `--plan-path-dir` session inference belong in the CLI arg parsing or should it stay as pipeline-level logic?
