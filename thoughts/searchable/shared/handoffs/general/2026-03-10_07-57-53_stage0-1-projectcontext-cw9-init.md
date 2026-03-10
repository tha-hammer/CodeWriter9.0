---
date: 2026-03-10T07:57:53-04:00
researcher: claude-opus
git_commit: 846fb1a
branch: master
repository: CodeWriter9.0
topic: "Stage 0-1 Complete — ProjectContext Refactor + cw9 init CLI"
tags: [implementation, refactor, projectcontext, cli, packaging, cw9-init]
status: complete
last_updated: 2026-03-10
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Stage 0-1 Complete — ProjectContext + cw9 init

## Task(s)

### Completed — Stage 0: ProjectContext dataclass (the real work)

Decoupled the three path concerns that were previously all `PROJECT_ROOT`:

1. **engine_root** — where CW9's own code lives (templates, tools, python/registry)
2. **target_root** — where the external project's source code lives
3. **state_root** — where the DAG, schemas, specs, and artifacts live for that project

Created `ProjectContext` frozen dataclass with three factory methods:
- `self_hosting(engine_root)` — CW9 working on itself (all three roots = same dir, legacy paths)
- `external(engine_root, target_root)` — CW9 working on an external project (state_root = target/.cw9)
- `from_target(target_root, engine_root=None)` — auto-detect mode, engine_root defaults from `__file__`

Threaded `ProjectContext` through `one_shot_loop.py` and all 6 loop scripts. Internal functions now use `tools_dir` instead of `project_root`. Backward-compatible `project_root=` parameter still works on `OneShotLoop`.

### Completed — Stage 1: cw9 init CLI

Created `cw9` CLI entry point with two subcommands:
- `cw9 init [target_dir]` — creates `.cw9/` directory structure with config.toml, empty DAG, and subdirectories
- `cw9 status [target_dir]` — shows project context, DAG stats, schema/spec counts

Executable wrapper at project root (`./cw9`) and console_scripts entry in pyproject.toml.

### Not started — Stage 2: cw9 ingest (brownfield)

Deferred per original plan. Currently: "user writes schemas by hand, CW9 validates them."

### Not started — Stage 3: CLI binary

Deferred. Could be Python CLI (click/argparse) or Rust binary later. The entry point structure is in place.

## Critical References
- `BOOTSTRAP.md:626-661` — Phase 5 Self-Hosting definition
- `thoughts/searchable/shared/handoffs/general/2026-03-10_06-51-35_phase8-complete-change-propagation.md` — Previous handoff (Phase 8 complete, context for what preceded this work)

## Recent changes

- `python/registry/context.py` (new) — `ProjectContext` dataclass with `self_hosting()`, `external()`, `from_target()` factories
- `python/registry/cli.py` (new) — `cw9` CLI with `init` and `status` subcommands
- `cw9` (new) — executable wrapper script at project root
- `python/registry/__init__.py:3` — added `ProjectContext` export
- `python/registry/one_shot_loop.py:23` — import `ProjectContext`
- `python/registry/one_shot_loop.py:244-266` — `_find_tla2tools()` now takes `tools_dir` instead of `project_root`
- `python/registry/one_shot_loop.py:269-290` — `compile_pluscal()` uses `tools_dir`
- `python/registry/one_shot_loop.py:293-354` — `run_tlc()` uses `tools_dir`
- `python/registry/one_shot_loop.py:357-405` — `compile_compose_verify()` uses `tools_dir`
- `python/registry/one_shot_loop.py:574-596` — `OneShotLoop` accepts both `ctx` and deprecated `project_root`, `__post_init__` converts
- `python/run_change_prop_loop.py` — all `PROJECT_ROOT / ...` replaced with `ctx.*`
- `python/run_subgraph_loop.py` — same pattern
- `python/run_dep_validation_loop.py` — same pattern
- `python/run_impact_loop.py` — same pattern
- `python/run_bridge_loop.py` — same pattern
- `python/run_bridge_retroactive.py` — same pattern (uses `ctx.spec_dir`, `ctx.artifact_dir`, `ctx.python_dir`)
- `python/pyproject.toml:12` — added `[project.scripts] cw9 = "registry.cli:main"`

## Learnings

### sys.path bootstrap must happen before ProjectContext import
Each `run_*.py` script still defines `PROJECT_ROOT` and does `sys.path.insert(0, str(PROJECT_ROOT / "python"))` before importing `registry.context`. This bootstrap step can't use `ProjectContext` since the import path isn't set up yet. The pattern is: compute PROJECT_ROOT → insert sys.path → import ProjectContext → create ctx.

### one_shot_loop.py only ever needed tools_dir
Every `project_root` usage in `one_shot_loop.py` ultimately resolved to `project_root / "tools" / "tla2tools.jar"`. The refactor simplified this to pass `tools_dir` directly through the internal pipeline (`_find_tla2tools` → `compile_pluscal` → `run_tlc` → `compile_compose_verify`).

### self_hosting() preserves legacy path layout exactly
For backward compatibility, `self_hosting()` maps:
- `schema_dir` → `engine_root/schema` (not `engine_root/.cw9/schema`)
- `spec_dir` → `engine_root/templates/pluscal/instances` (not `engine_root/.cw9/specs`)
- `artifact_dir` and `test_output_dir` → `engine_root/python/tests/generated`
This means running the loop scripts produces identical output to before the refactor.

### session_dir is new for self-hosting
Self-hosting now writes logs/LLM responses to `engine_root/sessions/` instead of the project root. This is a minor behavior change (cleaner than root-level file dumps). The `sessions/` directory is created on first use via `ctx.session_dir.mkdir(parents=True, exist_ok=True)`.

### config.toml uses simple format
The `.cw9/config.toml` currently only stores `engine.root`. It's not parsed back yet — `from_target()` takes engine_root as an explicit parameter. Wiring config.toml loading into `from_target()` is a natural next step.

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/python/registry/context.py` — ProjectContext dataclass
- `/home/maceo/Dev/CodeWriter9.0/python/registry/cli.py` — cw9 CLI
- `/home/maceo/Dev/CodeWriter9.0/cw9` — executable entry point
- `/home/maceo/Dev/CodeWriter9.0/python/registry/one_shot_loop.py` — refactored pipeline functions
- `/home/maceo/Dev/CodeWriter9.0/python/pyproject.toml` — console_scripts entry

## Action Items & Next Steps

### Immediate: Wire config.toml parsing into from_target()
`from_target()` currently requires `engine_root` as a parameter. It should read `engine_root` from `.cw9/config.toml` when present, so external tools don't need to know where CW9 is installed.

### Stage 2: cw9 ingest (brownfield support)
The hard problem. For greenfield projects, users create schemas from scratch. For existing codebases, CW9 needs to ingest existing code structure into schemas. Options:
- Manual: user writes schemas by hand, CW9 validates
- Semi-automated: CW9 scans source code and proposes schemas for review
- The pipeline already handles everything after schemas exist

### Stage 3: Installable binary
- `pip install -e .` already works for the Python package
- `cw9` console_scripts entry is wired in pyproject.toml
- Could add to PATH via symlink or `pip install`
- Rust binary wrapper is future work (the Rust crate has the DAG engine but pipeline is all Python)

### Consider: cw9 extract / cw9 loop / cw9 test
The CLI currently only has `init` and `status`. Natural next commands:
- `cw9 extract` — run SchemaExtractor on target project schemas, build DAG
- `cw9 loop <gwt-id>` — run the one-shot loop for a GWT behavior
- `cw9 test` — run generated tests with `query_affected_tests()` for smart targeting

### Cleanup
- Temp files still in project root: `change_prop_llm_response.txt`, `change_prop_llm_response_attempt2.txt`, `change_prop_loop_output.log`, `subgraph_llm_response.txt`, `subgraph_loop_output.log` — these are from before the sessions/ refactor

## Other Notes

### DAG state
- 96 nodes, 198 edges, 9 connected components (unchanged from Phase 8)
- 250 tests passing (unchanged)

### .cw9/ directory structure for external projects
```
my-project/.cw9/
  config.toml      # engine_root = "/path/to/CodeWriter9.0"
  dag.json          # project's DAG (starts empty)
  schema/           # user-provided JSON schemas
  specs/            # TLA+ instances (generated by loop)
  bridge/           # bridge artifact JSON files
  sessions/         # loop logs and LLM response files
```

### Path mapping reference
| Concern | Self-hosting path | External path |
|---|---|---|
| Templates | `engine_root/templates/pluscal` | `engine_root/templates/pluscal` |
| Tools | `engine_root/tools` | `engine_root/tools` |
| Schemas | `engine_root/schema` | `target/.cw9/schema` |
| Specs | `engine_root/templates/pluscal/instances` | `target/.cw9/specs` |
| Bridge artifacts | `engine_root/python/tests/generated` | `target/.cw9/bridge` |
| Sessions | `engine_root/sessions` | `target/.cw9/sessions` |
| Test output | `engine_root/python/tests/generated` | `target/tests/generated` |

### Pipeline commands (unchanged)
```bash
# Run any loop script
python3 python/run_change_prop_loop.py

# Run all tests
cd python && python3 -m pytest tests/ -v

# Use cw9 CLI
./cw9 init /path/to/project
./cw9 status /path/to/project
```
