---
date: "2026-03-12T20:37:48-04:00"
researcher: DustyForge
git_commit: fda7099bd6a6c4f51a759510b9453583bd8ed5c1
branch: master
repository: CodeWriter9.0
topic: "How-to: cw9 pipeline — batch CW7-to-CW9 pipeline"
tags: [howto, cw7-integration, pipeline, cw9, batch-mode]
status: complete
last_updated: "2026-03-12"
last_updated_by: DustyForge
---

# How to Run the CW9 Pipeline Against a CW7 Database

## Introduction

`cw9 pipeline` orchestrates the full CW9 pipeline in a single command: it reads
requirements and GWT acceptance criteria from a CW7 SQLite database, registers them
in the CW9 DAG, generates formally verified TLA+ specifications via an LLM loop, and
produces bridge artifacts for downstream test generation. At the end of a successful
run, each GWT has a verified `.tla` spec, simulation traces, and a structured
`_bridge_artifacts.json` ready for `cw9 gen-tests`.

**Implementation:** `python/registry/cli.py` (`cmd_pipeline()`)
**CW7 adapter:** `python/registry/cw7.py` (`extract`, `build_plan_path_map`, `copy_context_files`)

## Prerequisites

- A completed CW7 session with data in a SQLite database (e.g., `gate-outputs.db`)
- Java runtime (required by TLC model checker)
- `tla2tools.jar` present at `tools/tla2tools.jar` in the CodeWriter9.0 tree
- The `claude_agent_sdk` Python package installed (for LLM calls in the loop phase)
- A terminal session **outside** Claude Code (the SDK cannot connect nested inside a
  Claude Code session)

## Step 1: Run the Full Pipeline Against a CW7 Session

The simplest invocation points at a plan-path directory from a CW7 session. The
session ID is inferred from the directory name:

```bash
cw9 pipeline /path/to/project \
  --db ~/Dev/CodeWriter7/.cw7/gate-outputs.db \
  --plan-path-dir specs/orchestration/session-1773188666564
```

This executes three phases in sequence:

| Phase | What happens | Subcommands called internally |
|-------|-------------|-------------------------------|
| Phase 0: Setup | `init --ensure`, `extract`, CW7 extract, `_register_payload()` | Creates `.cw9/` tree, builds DAG, registers CW7 requirements and GWTs |
| Phase 1: Loop | `cmd_loop()` per GWT | LLM generates PlusCal, TLC verifies, retries on failure, saves sim traces |
| Phase 2: Bridge | `cmd_bridge()` per verified GWT | Parses verified spec into structured artifacts JSON |

## Step 2: Point at a Specific CW7 Database

The `--db` flag is required when setup runs. Alternatively, set the `CW7_DB`
environment variable:

```bash
export CW7_DB=/path/to/gate-outputs.db
cw9 pipeline /path/to/project
```

The `--session` flag selects which CW7 session to extract. If omitted and
`--plan-path-dir` is given, the session ID is inferred from the directory name when
it starts with `session-`. If the database has exactly one session, it is
auto-detected.

```bash
cw9 pipeline /path/to/project \
  --db /path/to/other/gate-outputs.db \
  --session session-1773188666564 \
  --plan-path-dir /path/to/plan-path-files/
```

Missing or nonexistent `--db` is a hard error (rc=1) — there is no inline fixture
fallback.

## Step 3: Target Specific GWTs

To run only a subset of GWTs instead of all registered:

```bash
cw9 pipeline /path/to/project --db /path/to/cw7.db \
  --gwt gwt-0001 --gwt gwt-0003 --gwt gwt-0010
```

The `--gwt` flag is repeatable. GWT ID resolution follows a priority chain:

1. Explicit `--gwt` args (if provided)
2. GWT IDs from the register output (setup phase)
3. All `gwt-*` nodes in the DAG (sorted, fallback)

## Step 4: Control Retry Behavior

The LLM loop retries up to 5 times by default when TLC verification fails. Each
retry receives a classified error message with targeted fix instructions.

```bash
cw9 pipeline /path/to/project --db /path/to/cw7.db --max-retries 3
```

## Step 5: Run Individual Phases

### Loop only (skip bridge)

Useful when you want specs but not bridge artifacts yet:

```bash
cw9 pipeline /path/to/project --db /path/to/cw7.db --loop-only
```

### Bridge only (skip setup and loop)

Useful when specs already exist and you want to regenerate bridge artifacts:

```bash
cw9 pipeline /path/to/project --bridge-only --gwt gwt-0001
```

Requires that `.tla` spec files already exist in `.cw9/specs/`. The `--db` flag is
not required.

### Skip setup (re-run loop on existing project)

```bash
cw9 pipeline /path/to/project --skip-setup --gwt gwt-0001
```

The `--db` flag is not required when setup is skipped.

### Mode flag interactions

| Flag combination | Setup | Loop | Bridge |
|-----------------|-------|------|--------|
| (none) | runs | runs | runs |
| `--skip-setup` | skipped | runs | runs |
| `--loop-only` | runs | runs | skipped |
| `--bridge-only` | skipped | skipped | runs |
| `--skip-setup --loop-only` | skipped | runs | skipped |

## Step 6: Supply Context Files from CW7 Plan Paths

When `--plan-path-dir` is given, CW7 plan-path markdown files are copied into the
CW9 project as context for the LLM:

1. `build_plan_path_map()` queries the `plan_paths` table to map
   `acceptance_criteria.id` to `plan_paths.id`
2. `copy_context_files()` globs `{plan_path_id}-*.md` from the plan-path directory
3. Each matched file is written to `.cw9/context/{criterion_id}.md`
4. During the loop phase, the context file for each GWT is passed as
   `context_file` to `cmd_loop()`

The context file provides the LLM with detailed specification text that guides the
PlusCal generation beyond what the GWT given/when/then alone conveys.

## Step 7: Run Test Generation on Bridge Artifacts

After the pipeline completes, each verified GWT has a
`.cw9/bridge/{gwt_id}_bridge_artifacts.json` file. Generate tests with:

```bash
cw9 gen-tests gwt-0003 /path/to/project
```

This must be run from a standalone terminal (not nested in Claude Code) because it
calls the LLM via `claude_agent_sdk`.

## How the CW7 Database Is Queried

The extraction step (`registry.cw7.extract()`) runs three queries against the CW7
SQLite database:

| Query | Table | Returns |
|-------|-------|---------|
| Session resolution | `sessions` | Auto-selects the single session, or raises `ValueError` if ambiguous |
| Requirements | `requirements` | `{id, text}` per requirement |
| GWT criteria | `acceptance_criteria` (where `format = 'gwt'`) | `{criterion_id, given, when, then, parent_req, name}` per GWT |

A fourth query (`build_plan_path_map`) is run only when `--plan-path-dir` is
provided, mapping `acceptance_criteria.id` to `plan_paths.id` for context file
lookup.

## Idempotent Registration via Criterion Bindings

`_register_payload()` maintains `.cw9/criterion_bindings.json` — a mapping from CW7
IDs to CW9-allocated IDs:

- `"req:{cw7_requirement_id}"` maps to `"req-NNNN"`
- `"gwt:{criterion_id}"` maps to `"gwt-NNNN"`

Re-running the pipeline with the same CW7 data reuses existing CW9 IDs rather than
allocating new ones. The pipeline can be re-run incrementally without creating
duplicate nodes in the DAG.

## Partial Failure Behavior

If GWT-1's loop passes but GWT-2's loop fails:

- Bridge still runs for GWT-1 (the passing GWT)
- The final exit code is `1` because not all GWTs passed

This allows maximum forward progress even when some GWTs fail.

## Artifacts Produced on Disk

All paths are relative to the project directory.

### Phase 0 — Setup

| Artifact | Path |
|----------|------|
| Engine config | `.cw9/config.toml` |
| DAG | `.cw9/dag.json` |
| Starter schemas | `.cw9/schema/*.json` |
| Criterion bindings | `.cw9/criterion_bindings.json` |
| Context files | `.cw9/context/{criterion_id}.md` |

### Phase 1 — Loop (per GWT)

| Artifact | Path |
|----------|------|
| LLM response per attempt | `.cw9/sessions/{gwt_id}_attempt{N}.txt` |
| Verified TLA+ spec | `.cw9/specs/{gwt_id}.tla` |
| TLC config | `.cw9/specs/{gwt_id}.cfg` |
| Counterexample traces | `.cw9/specs/{gwt_id}_traces.json` |
| Simulation traces | `.cw9/specs/{gwt_id}_sim_traces.json` |

### Phase 2 — Bridge (per verified GWT)

| Artifact | Path |
|----------|------|
| Bridge artifacts | `.cw9/bridge/{gwt_id}_bridge_artifacts.json` |

The bridge artifact JSON contains: `gwt_id`, `module_name`, `data_structures`,
`operations`, `verifiers`, `assertions`, `test_scenarios`, `simulation_traces`.

## CLI Reference Summary

| Flag | Default | Description |
|------|---------|-------------|
| `target_dir` | `.` | Project directory (positional) |
| `--db` | none | CW7 SQLite database path (or set `CW7_DB` env var) |
| `--session` | auto-detected | CW7 session ID |
| `--plan-path-dir` | none | Directory of CW7 plan-path `.md` files |
| `--gwt` | all registered | GWT ID to process (repeatable) |
| `--max-retries` | `5` | Max LLM retry attempts per GWT |
| `--skip-setup` | off | Skip Phase 0 |
| `--loop-only` | off | Run Phase 1 only |
| `--bridge-only` | off | Run Phase 2 only |

## Exit Codes

| Condition | Code |
|-----------|------|
| All targeted GWTs passed their phases | `0` |
| Any GWT failed loop or bridge | `1` |
| `--db` missing or nonexistent (when setup runs) | `1` |
| No GWT IDs resolved | `1` |

## Migration from `run_loop_bridge.py`

The standalone `python/tools/run_loop_bridge.py` script is superseded by
`cw9 pipeline`. The key differences:

| `run_loop_bridge.py` | `cw9 pipeline` |
|---------------------|----------------|
| `--project-dir /tmp/foo` | `cw9 pipeline /tmp/foo` (positional arg) |
| Falls back to inline fixture if DB missing | Hard error if `--db` missing |
| `from tools.cw7_extract import ...` | `from registry.cw7 import ...` |
| Mocks `sys.stdin`/`sys.stdout` to call `cw9 register` | Calls `_register_payload()` directly |
| Standalone script with `sys.path` hack | Installed package, available as `cw9 pipeline` |

## Next Steps

- For the full `cw9` subcommand reference, consult `howto-cw9-cli-pipeline.md`
- For the library API, consult `howto-cw9-library-api.md`
