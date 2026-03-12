---
date: "2026-03-12T15:21:59-04:00"
researcher: DustyForge
git_commit: 833a539aeb3e4f5fbab1454752aa724d8788fd0a
branch: master
repository: CodeWriter9.0
topic: "How-to guide for run_loop_bridge.py — wiring CW9 into the CW7 pipeline"
tags: [howto, cw7-integration, run_loop_bridge, pipeline, documentation]
status: complete
last_updated: "2026-03-12"
last_updated_by: DustyForge
---

# How to Run the CW9 Pipeline Against a CW7 Database

## Introduction

`run_loop_bridge.py` orchestrates the full CW9 pipeline: it reads requirements and
GWT acceptance criteria from a CW7 SQLite database, registers them in the CW9 DAG,
generates formally verified TLA+ specifications via an LLM loop, and produces bridge
artifacts for downstream test generation. At the end of a successful run, each GWT
has a verified `.tla` spec, simulation traces, and a structured
`_bridge_artifacts.json` ready for `cw9 gen-tests`.

**File:** `python/tools/run_loop_bridge.py`

## Prerequisites

- A completed CW7 session with data in `gate-outputs.db`
- Java runtime (required by TLC model checker)
- `tla2tools.jar` present at `tools/tla2tools.jar` in the CodeWriter9.0 tree
- The `claude_agent_sdk` Python package installed (for LLM calls in the loop phase)
- A terminal session **outside** Claude Code (the SDK cannot connect nested inside a
  Claude Code session)

## Step 1: Run the Full Pipeline Against a CW7 Session

The simplest invocation points at a plan-path directory from a CW7 session. The
session ID and database path are auto-detected:

```bash
cd ~/Dev/silmari-zero-knowledge
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --plan-path-dir specs/orchestration/session-1773188666564
```

This executes three phases in sequence:

| Phase | What happens | Subcommands called |
|-------|-------------|--------------------|
| Phase 0: Setup | `cw9 init`, `cw9 extract`, `cw9 register` | Creates `.cw9/` tree, builds DAG, registers CW7 requirements and GWTs |
| Phase 1: Loop | `cw9 loop` per GWT | LLM generates PlusCal, TLC verifies, retries on failure, saves sim traces |
| Phase 2: Bridge | `cw9 bridge` per verified GWT | Parses verified spec into structured artifacts JSON |

Output goes to a temp directory (printed at startup):

```
Project:     /tmp/cw9-pipeline-5ul0qwc2
```

## Step 2: Point at a Specific CW7 Database

By default, the script reads from `~/Dev/CodeWriter7/.cw7/gate-outputs.db`. To use a
different database:

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --db /path/to/other/gate-outputs.db \
  --session session-1773188666564 \
  --plan-path-dir /path/to/plan-path-files/
```

The `--session` flag selects which CW7 session to extract. If omitted and
`--plan-path-dir` is given, the session ID is inferred from the directory name when
it starts with `session-`.

Alternatively, set the `CW7_FIXTURE_DB` environment variable:

```bash
export CW7_FIXTURE_DB=/path/to/gate-outputs.db
```

If no database is found at the resolved path, the script falls back to a built-in
counter-app fixture (4 requirements, 4 GWTs) for testing purposes.

## Step 3: Use a Persistent Project Directory

By default, a temp directory is created. To use a fixed location (e.g., for
incremental re-runs):

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --project-dir /path/to/my-project \
  --plan-path-dir specs/orchestration/session-1773188666564
```

The `--ensure` flag on `cw9 init` makes this idempotent: if `.cw9/` already exists,
init is a no-op.

## Step 4: Target Specific GWTs

To run only a subset of GWTs instead of all 55:

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --plan-path-dir specs/orchestration/session-1773188666564 \
  --gwt gwt-0001 --gwt gwt-0003 --gwt gwt-0010
```

The `--gwt` flag is repeatable. If omitted, all registered GWTs are processed.

## Step 5: Control Retry Behavior

The LLM loop retries up to 5 times by default when TLC verification fails. Each
retry receives a classified error message (syntax error, type error, invariant
violation, deadlock, or constant mismatch) with targeted fix instructions.

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --plan-path-dir specs/orchestration/session-1773188666564 \
  --max-retries 3
```

## Step 6: Run Individual Phases

### Loop only (skip bridge)

Useful when you want specs but not bridge artifacts yet:

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --plan-path-dir specs/orchestration/session-1773188666564 \
  --loop-only
```

### Bridge only (skip setup and loop)

Useful when specs already exist and you want to regenerate bridge artifacts:

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --project-dir /tmp/cw9-pipeline-5ul0qwc2 \
  --bridge-only
```

Requires that `.tla` spec files already exist in `.cw9/specs/`.

### Skip setup (re-run loop on existing project)

```bash
python3 ~/Dev/CodeWriter9.0/python/tools/run_loop_bridge.py \
  --project-dir /tmp/cw9-pipeline-5ul0qwc2 \
  --skip-setup
```

## Step 7: Run Test Generation on Bridge Artifacts

After the pipeline completes, each verified GWT has a
`.cw9/bridge/{gwt_id}_bridge_artifacts.json` file. Generate tests with:

```bash
python3 -m registry gen-tests gwt-0003 /tmp/cw9-pipeline-5ul0qwc2
```

This must be run from a standalone terminal (not nested in Claude Code) because it
calls the LLM via `claude_agent_sdk`.

## How Context Files Flow Through the Pipeline

When `--plan-path-dir` is given, CW7 plan-path markdown files are copied into the
CW9 project as context for the LLM:

1. `build_plan_path_map()` queries the `plan_paths` table to map
   `acceptance_criteria.id` to `plan_paths.id`
2. `copy_context_files()` globs `{plan_path_id}-*.md` from the plan-path directory
3. Each matched file is written to `.cw9/context/{criterion_id}.md`
4. During the loop phase, the context file for each GWT is passed as
   `--context-file` to `cw9 loop`

The context file provides the LLM with detailed specification text that guides the
PlusCal generation beyond what the GWT given/when/then alone conveys.

## How the CW7 Database Is Queried

The extraction step (`cw7_extract.extract()`) runs three queries against
`gate-outputs.db`:

| Query | Table | Returns |
|-------|-------|---------|
| Session resolution | `sessions` | Auto-selects the single session, or errors if ambiguous |
| Requirements | `requirements` | `{id, text}` per requirement |
| GWT criteria | `acceptance_criteria` (where `format = 'gwt'`) | `{criterion_id, given, when, then, parent_req, name}` per GWT |

A fourth query (`build_plan_path_map`) is run only when `--plan-path-dir` is
provided, mapping `acceptance_criteria.id` to `plan_paths.id` for context file
lookup.

## Idempotent Registration via Criterion Bindings

`cw9 register` maintains `.cw9/criterion_bindings.json` — a mapping from CW7 IDs to
CW9-allocated IDs:

- `"req:{cw7_requirement_id}"` maps to `"req-NNNN"`
- `"gwt:{criterion_id}"` maps to `"gwt-NNNN"`

Re-running `register` with the same CW7 data reuses existing CW9 IDs rather than
allocating new ones. This means the pipeline can be re-run incrementally without
creating duplicate nodes in the DAG.

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

### Phase 3 — gen-tests (per GWT, separate invocation)

| Artifact | Path |
|----------|------|
| Generated test file | `tests/generated/test_{gwt_id}.py` |
| Plan transcript | `.cw9/sessions/{gwt_id}_plan.txt` |
| Review transcript | `.cw9/sessions/{gwt_id}_review.txt` |

## CLI Reference Summary

| Flag | Default | Description |
|------|---------|-------------|
| `--db` | `~/Dev/CodeWriter7/.cw7/gate-outputs.db` | CW7 SQLite database path |
| `--session` | auto-detected | CW7 session ID |
| `--project-dir` | temp directory | Target project directory |
| `--plan-path-dir` | none | Directory of CW7 plan-path `.md` files |
| `--gwt` | all registered | GWT ID to process (repeatable) |
| `--max-retries` | `5` | Max LLM retry attempts per GWT |
| `--skip-setup` | `false` | Skip Phase 0 |
| `--loop-only` | `false` | Run Phase 1 only |
| `--bridge-only` | `false` | Run Phase 2 only |

## Exit Codes

| Condition | Code |
|-----------|------|
| All targeted GWTs passed their phases | `0` |
| Any GWT failed loop or bridge | `1` |
| No GWT IDs resolved | `1` |
| Phase 0 assertion failure (init/extract/register) | non-zero (unhandled) |

## Next Steps

- For the full `cw9` subcommand reference, consult `howto-cw9-cli-pipeline.md`
- For the library API, consult `howto-cw9-library-api.md`
