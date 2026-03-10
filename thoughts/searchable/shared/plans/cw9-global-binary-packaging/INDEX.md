# Package `cw9` as a Globally Installable Binary — TDD Plan

**Status:** IMPLEMENTED
**Date:** 2026-03-10
**Packaging method:** `uv tool install .` (primary) / `pipx install .` (fallback)

## Overview

Package the `cw9` CLI so it can be installed globally via `uv tool install .` or `pipx install .` and invoked as `cw9` from any directory. The core challenge is that the current code resolves bundled data files (templates, tools/tla2tools.jar) via filesystem-relative `ENGINE_ROOT` — which breaks when the package is installed into a venv's `site-packages/`.

## Current State Analysis

### What works today
- `pip install -e .` from `python/` → `cw9` works in development
- `[project.scripts]` entry point: `cw9 = "registry.cli:main"`
- All 346 tests pass

### What breaks on global install
1. **`cli.py:20`** — `ENGINE_ROOT = Path(__file__).parent.parent.parent` resolves to `<venv>/lib/python3.x/` instead of the repo root
2. **`context.py:80`** — same hardcoded fallback in `from_target()`
3. **`context.py:89-109`** — `external()` derives `template_dir` and `tools_dir` from `engine_root`, which doesn't exist when installed
4. **`cli.py:64-67`** — `cw9 init` writes `engine_root = "<absolute path>"` into `config.toml`, but there's no engine_root directory after global install
5. **No `[build-system]`** in pyproject.toml — can't build a wheel
6. **No `package-data`** declared — templates and tools/jar not included in wheel
7. **`claude_agent_sdk`** imported but not declared as dependency

### Key Decisions (pre-resolved)
- **tla2tools.jar** (4.0 MB): BUNDLE in-package. Under 5MB threshold, simplest approach.
- **claude_agent_sdk**: Required dependency. It's on PyPI (v0.1.48), pip-installable.
- **self_hosting mode**: Continues to use engine_root from repo checkout. Only external mode needs importlib.resources fallback.

### Two categories of ENGINE_ROOT paths

| Path | Category | Resolution when installed |
|------|----------|--------------------------|
| `template_dir` (templates/pluscal) | Bundled asset | `importlib.resources` |
| `tools_dir` (tools/) | Bundled asset | `importlib.resources` |
| `python_dir` (python/) | Repo structure | Resolves to `target_root` in installed mode (project being operated on) |
| `schema_dir`, `spec_dir`, etc. | Project state | `.cw9/` directory on target — already works |

## Desired End State

```bash
# Install globally (no repo checkout needed)
uv tool install git+https://github.com/user/CodeWriter9.0#subdirectory=python
# or from local checkout:
uv tool install ./python

# Works from any directory
cw9 init /path/to/myapp
cw9 extract /path/to/myapp
cw9 loop gwt-0024 /path/to/myapp
cw9 bridge gwt-0024 /path/to/myapp
cw9 gen-tests gwt-0024 /path/to/myapp
cw9 test /path/to/myapp

# Also works as module
python -m registry --help
```

## What We're NOT Doing
- PyInstaller/Nuitka single binary
- Docker packaging
- Cross-platform CI builds
- Download-on-first-use for tla2tools.jar (bundling instead)
- Changing the self-hosting mode behavior

## File Impact Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `python/pyproject.toml` | MODIFY | Add build-system, dependencies, package-data |
| `python/registry/_data/` | CREATE | Bundled data directory (templates, tools) |
| `python/registry/_resources.py` | CREATE | importlib.resources helpers |
| `python/registry/context.py` | MODIFY | Resolve bundled assets from package resources when engine_root absent |
| `python/registry/cli.py` | MODIFY | Remove ENGINE_ROOT constant; use _resources for init templates |
| `python/registry/one_shot_loop.py` | MODIFY | `_find_tla2tools()` gains importlib.resources fallback |
| `python/registry/loop_runner.py` | MODIFY | Lazy import of claude_agent_sdk (already works, just needs fallback error) |
| `python/registry/__main__.py` | CREATE | `python -m registry` entry point |
| `python/tests/test_packaging.py` | CREATE | All packaging-related tests |

## Phase List

| Phase | File | Description |
|-------|------|-------------|
| [Phase 0](phase-0-pyproject-and-wheel.md) | pyproject.toml, _data/, __main__.py | Build infrastructure — wheel builds with all data files |
| [Phase 1](phase-1-resources-module.md) | _resources.py | importlib.resources helper module |
| [Phase 2](phase-2-context-refactor.md) | context.py | ProjectContext resolves bundled assets when engine_root absent |
| [Phase 3](phase-3-cli-init-fix.md) | cli.py | `cw9 init` uses package resources for templates |
| [Phase 4](phase-4-tla2tools-resolution.md) | one_shot_loop.py | `_find_tla2tools()` gains package resource fallback |
| [Phase 5](phase-5-integration-verify.md) | test_packaging.py | End-to-end: `uv tool install .` → `cw9 init` → `cw9 extract` |
