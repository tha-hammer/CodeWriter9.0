---
date: 2026-03-18T15:30:00Z
researcher: Claude Code (claude-opus-4-6)
git_commit: 3b62041b15cb4633a02c8164f52ab74efea2aead
branch: hosted-system-pipeline
repository: CodeWriter9.0
topic: "Hosted System Pipeline — mapping CLI to a 3-plane hosted architecture"
tags: [research, cw9, hosted, architecture, api, worker, pipeline]
status: complete
last_updated: 2026-03-18
last_updated_by: Claude Code (claude-opus-4-6)
cw9_project: python/registry
---

# Research: Hosted System Pipeline

## Research Question

Map the current CLI pipeline (`cw9 init/extract/loop/bridge/gen-tests/test`) into a hosted 3-plane system (control plane, execution plane, data plane) where extract, loop, bridge, and gen-tests become asynchronous jobs backed by Postgres metadata, object storage artifacts, and a job queue.

## Codebase Overview

The CW9 CLI lives entirely in `python/registry/`. It implements 14 subcommands organized around two tracks:

- **Greenfield track**: `init → extract → register → loop → bridge → gen-tests → test`
- **Brownfield track**: `ingest → crawl → gwt-author → register`

The `pipeline` command (`cli.py:600`) orchestrates the greenfield track end-to-end.

### File Inventory

| Directory | Files | Role |
|-----------|-------|------|
| `python/registry/` | 25+ modules | Core pipeline: CLI, DAG, loop, bridge, lang runners, crawl, scanners |
| `templates/pluscal/` | TLA+ templates | PlusCal structural template for LLM prompt |
| `tools/` | `tla2tools.jar` | Java TLC toolchain |
| `schema/` | JSON schemas | Backend schema definitions |
| `crates/registry-core/` | Rust crate | (Future Rust core — not yet integrated into pipeline) |

### Current State Storage (`.cw9/` directory)

```
.cw9/
├── config.toml                          # engine root + project settings
├── dag.json                             # Registry DAG (nodes, edges, closure)
├── criterion_bindings.json              # idempotency map: cw7-id → gwt/req IDs
├── crawl.db                             # SQLite: records, ins, outs, entry_points
├── schema/*.json                        # input schemas
├── specs/{gwt_id}.tla                   # verified TLA+ specs
├── specs/{gwt_id}.cfg                   # TLC config files
├── specs/{gwt_id}_traces.json           # counterexample traces from retry attempts
├── specs/{gwt_id}_sim_traces.json       # TLC -simulate traces
├── bridge/{gwt_id}_bridge_artifacts.json # bridge output
├── sessions/{gwt_id}_attempt{N}.txt     # raw LLM response per attempt
├── sessions/{gwt_id}_result.json        # {gwt_id, result, attempts, error}
└── context/{criterion_id}.md            # optional plan-path context
```

No extraction status from cw9 — analyzed from source directly.

## Key Functions

### cmd_init()
- **File**: python/registry/cli.py:57
- **Role**: Creates `.cw9/` directory structure, writes `config.toml`, seeds `dag.json`, copies starter schemas
- **Calls**: filesystem operations only
- **Called by**: CLI `cw9 init`, `cmd_pipeline` (with `--ensure`)
- **Hosted mapping**: Becomes part of "create project" API endpoint. Creates Postgres project record + object storage prefix.

### cmd_extract()
- **File**: python/registry/cli.py:197
- **Role**: Rebuilds `dag.json` from `.cw9/schema/*.json` files. Merges registered nodes from old DAG.
- **Calls**: `SchemaExtractor.extract()`, `RegistryDag.load/save()`, `CrawlStore.get_all_uuids()`
- **Called by**: CLI `cw9 extract`, `cmd_pipeline`
- **Worker class**: light — pure Python, no LLM, no subprocess. Reads schemas from object storage, writes DAG back.

### cmd_loop()
- **File**: python/registry/cli.py:252
- **Role**: Runs LLM→PlusCal→TLC verification loop for one GWT. Up to `max_retries` (default 8) attempts.
- **Calls**: `run_loop()` in loop_runner.py
- **Called by**: CLI `cw9 loop <gwt-id>`, `cmd_pipeline`
- **Worker class**: **heavy-tla** — invokes Claude Agent SDK + Java TLC. Memory-hungry, long-running (up to 300s per TLC check × 8 retries).

### run_loop()
- **File**: python/registry/loop_runner.py:220
- **Role**: Async retry loop. Creates one `ClaudeSDKClient` per GWT, reused across retries. Builds prompt from DAG + crawl.db cards + template. Processes each LLM response through `OneShotLoop.process_response()`.
- **Calls**: `_make_client()`, `_call_llm_with_client()`, `OneShotLoop.query()/.process_response()`, `run_tlc_simulate()`, `write_result_file()`
- **Reads**: `.cw9/dag.json`, `templates/pluscal/state_machine.tla`, `.cw9/crawl.db` (optional), `.cw9/context/*.md` (optional)
- **Writes**: `.cw9/sessions/*`, `.cw9/specs/*`
- **External tools**: Claude Agent SDK (`claude-sonnet-4-6`), `java pcal.trans` (60s), `java tlc2.TLC` (300s), `java tlc2.TLC -simulate` (300s)

### OneShotLoop.process_response()
- **File**: python/registry/one_shot_loop.py:867
- **Role**: Stateless processing pipeline: extract PlusCal → compile → TLC verify → parse counterexample → route result
- **Calls**: `extract_pluscal()`, `compile_compose_verify()`, `parse_counterexample()`, `translate_counterexample()`, `route_result()`

### compile_compose_verify()
- **File**: python/registry/one_shot_loop.py:597
- **Role**: Writes PlusCal to temp dir, compiles with `pcal.trans`, runs TLC model checking
- **Writes**: `/tmp/cw9_XXXX/{ModuleName}.tla`, `/tmp/cw9_XXXX/{ModuleName}.cfg`
- **External tools**: `java pcal.trans` (60s timeout), `java tlc2.TLC` (300s timeout)

### cmd_bridge()
- **File**: python/registry/cli.py:282
- **Role**: Parses verified `.tla` spec into structured bridge artifact JSON. Pure Python regex parser — no LLM, no subprocess.
- **Calls**: `run_bridge()` in bridge.py
- **Reads**: `.cw9/specs/{gwt_id}.tla`, `_traces.json`, `_sim_traces.json`
- **Writes**: `.cw9/bridge/{gwt_id}_bridge_artifacts.json`
- **Worker class**: light — pure Python, fast.

### run_bridge()
- **File**: python/registry/bridge.py:692
- **Role**: Main bridge entry. TLA+ text → `BridgeResult` containing `data_structures`, `operations`, `verifiers`, `assertions`, `test_scenarios`.
- **Calls**: `parse_spec()`, `translate_state_vars()`, `translate_actions()`, `translate_invariants_to_verifiers()`, `translate_invariants_to_assertions()`, `translate_traces()`

### cmd_gen_tests()
- **File**: python/registry/cli.py:343
- **Role**: LLM-generates test file from bridge artifacts. 3-pass prompt: plan → review → codegen, then retry loop.
- **Calls**: `run_test_gen_loop()` in test_gen_loop.py, `call_llm()` from loop_runner.py
- **Reads**: `.cw9/bridge/{gwt_id}_bridge_artifacts.json`, `.cw9/dag.json`, `.cw9/specs/*`
- **Writes**: `{target}/tests/generated/test_{gwt_id}.py` (or lang-specific equivalent)
- **Worker class**: **heavy-lang** — invokes Claude Agent SDK + language toolchains (pytest/npx/cargo/go)

### run_test_gen_loop()
- **File**: python/registry/test_gen_loop.py:322
- **Role**: Async entry point for test generation. 3-pass LLM + verify + retry loop.
- **Calls**: `build_test_plan_prompt()`, `build_review_prompt()`, `build_codegen_prompt()`, `profile.verify_test_file()`, `profile.extract_code_from_response()`

### LanguageProfile Protocol
- **File**: python/registry/lang.py:93
- **Role**: Defines interface for language-specific test generation. Four implementations.
- **Implementations**: `PythonProfile` (lang.py:152), `TypeScriptProfile` (lang_typescript.py), `RustProfile` (lang_rust.py), `GoProfile` (lang_go.py)

### verify_test_file() — per language
- **PythonProfile**: `lang.py:228` — `compile()` built-in → `pytest --collect-only` → `pytest -x -v`
- **TypeScriptProfile**: `lang_typescript.py:200` — `npx tsc --noEmit` → `npx jest --listTests` → `npx jest --no-coverage`
- **RustProfile**: `lang_rust.py:196` — `cargo check` → `cargo test --no-run` → `cargo test`
- **GoProfile**: `lang_go.py:255` — `go vet ./...` → `go test -list .` → `go test -v`

### cmd_pipeline()
- **File**: python/registry/cli.py:600
- **Role**: Orchestrates: init → extract → register → loop(per GWT) → bridge(per verified GWT)
- **Calls**: `cmd_init`, `cmd_extract`, `_register_payload`, `cmd_loop` per GWT, `cmd_bridge` per verified GWT

### _resolve_gwt_ids()
- **File**: python/registry/cli.py:563
- **Role**: Determines which GWTs to process. Resolution: explicit --gwt flags → register output → dag.json scan → empty list.
- **Called by**: `cmd_pipeline` at line 658

### cmd_ingest()
- **File**: python/registry/cli.py:811
- **Role**: Scans external source code via language-specific scanners → skeleton `FnRecord` entries in crawl.db + RESOURCE nodes in dag.json
- **Worker class**: light — filesystem scan + SQLite writes, no LLM

### cmd_crawl()
- **File**: python/registry/cli.py:956
- **Role**: DFS LLM extraction over skeleton records in crawl.db. Fills IN:DO:OUT behavioral data.
- **Worker class**: heavy-tla (uses Claude Agent SDK, one call per function)
- **External tools**: Claude Agent SDK (claude-sonnet-4-6)

### cmd_gwt_author()
- **File**: python/registry/cli.py:1414
- **Role**: Generates GWT JSON from research notes + crawl.db context. Single LLM call.
- **Worker class**: light-to-medium — one LLM call, fast return

### CrawlStore
- **File**: python/registry/crawl_store.py
- **Role**: SQLite wrapper for crawl.db. Context-manager scoped (connection per command). WAL mode, foreign keys ON.
- **Tables**: `records`, `ins`, `outs`, `source_links`, `ax_records`, `map_notes`, `test_refs`, `entry_points`, `crawl_runs`
- **Hosted mapping**: Migrates to Postgres tables. Same schema, different backend.

### RegistryDag
- **File**: python/registry/dag.py:26
- **Role**: In-memory graph loaded from/saved to `dag.json`. Holds nodes, edges, closure, components, test_artifacts.
- **Hosted mapping**: `dag.json` becomes a Postgres-stored JSON document or normalized tables. Object storage for large snapshots.

### ProjectContext
- **File**: python/registry/context.py:22
- **Role**: Frozen dataclass holding all derived paths. Three modes: self_hosting, external, installed.
- **Hosted mapping**: Needs a `hosted()` factory that resolves paths to object storage prefixes + temp workspace paths.

## Call Graph

```
cmd_pipeline (cli.py:600)
  ├── cmd_init (cli.py:57)
  │     └── filesystem: create .cw9/ dirs, write config.toml, dag.json
  │
  ├── cmd_extract (cli.py:197)
  │     ├── SchemaExtractor.extract() (extractor.py)
  │     ├── RegistryDag.load/save/merge_registered_nodes (dag.py)
  │     └── CrawlStore.get_all_uuids() (crawl_store.py)
  │
  ├── _register_payload (cli.py:439)
  │     ├── RegistryDag.load/save (dag.py)
  │     └── load_bindings/save_bindings (bindings.py)
  │
  ├── FOR EACH gwt_id:
  │   └── cmd_loop (cli.py:252)
  │         └── run_loop (loop_runner.py:220)
  │               ├── RegistryDag.load (dag.py)
  │               ├── query_context (one_shot_loop.py:114)
  │               │     ├── dag.query_relevant (dag.py)
  │               │     └── CrawlStore.get_record (crawl_store.py)
  │               ├── _make_client (loop_runner.py:54) → ClaudeSDKClient
  │               ├── FOR attempt 1..max_retries:
  │               │   ├── _call_llm_with_client → LLM response
  │               │   └── OneShotLoop.process_response (one_shot_loop.py:867)
  │               │         ├── extract_pluscal (one_shot_loop.py:243)
  │               │         ├── compile_compose_verify (one_shot_loop.py:597)
  │               │         │     ├── SUBPROCESS: java pcal.trans (60s)
  │               │         │     └── SUBPROCESS: java tlc2.TLC (300s)
  │               │         ├── parse_counterexample (one_shot_loop.py:675)
  │               │         └── route_result (one_shot_loop.py:783)
  │               └── ON PASS: run_tlc_simulate (one_shot_loop.py:1043)
  │                             └── SUBPROCESS: java tlc2.TLC -simulate (300s)
  │
  └── FOR EACH verified gwt_id:
      └── cmd_bridge (cli.py:282)
            └── run_bridge (bridge.py:692)
                  ├── parse_spec (bridge.py:99)
                  ├── translate_state_vars (bridge.py:291)
                  ├── translate_actions (bridge.py:377)
                  ├── translate_invariants_to_verifiers (bridge.py:475)
                  ├── translate_invariants_to_assertions (bridge.py:511)
                  └── translate_traces (bridge.py:613)

cmd_gen_tests (cli.py:343)
  └── run_test_gen_loop (test_gen_loop.py:322)
        ├── build_test_plan_prompt → call_llm (Pass 1: Plan)
        ├── build_review_prompt → call_llm (Pass 2: Review)
        ├── build_codegen_prompt → call_llm (Pass 3: Codegen)
        ├── profile.extract_code_from_response → write test file
        ├── profile.verify_test_file → VerifyResult
        │     └── SUBPROCESS: pytest/npx/cargo/go (per language)
        └── RETRY LOOP: build_retry_prompt → call_llm → extract → verify
```

## Findings

### 1. Pipeline is Already Stage-Based — Clean Job Boundaries

Each CLI command is a self-contained stage with explicit file-based inputs and outputs. No state persists between commands except through `.cw9/` files. This maps directly to the proposed job DAG:

| CLI Stage | Job Type | Worker Class | Inputs (from object storage) | Outputs (to object storage) |
|-----------|----------|--------------|------------------------------|----------------------------|
| `init` | N/A (API-side) | — | — | project record in DB |
| `extract` | `extract` | light | `schema/*.json`, `dag.json` | `dag.json` |
| `register` | `register` | light | `dag.json`, `criterion_bindings.json`, JSON payload | `dag.json`, `criterion_bindings.json` |
| `loop` | `loop` | heavy-tla | `dag.json`, `crawl.db`, templates, context | `specs/*.tla`, `specs/*.cfg`, `specs/*_traces.json`, `specs/*_sim_traces.json`, `sessions/*` |
| `bridge` | `bridge` | light | `specs/{gwt_id}.tla`, `*_traces.json`, `*_sim_traces.json` | `bridge/{gwt_id}_bridge_artifacts.json` |
| `gen-tests` | `gen-tests` | heavy-lang | `bridge/*_bridge_artifacts.json`, `dag.json`, `specs/*`, source code | `tests/generated/test_*.py` (or lang equivalent) |
| `ingest` | `ingest` | light | source code tree | `crawl.db`, `dag.json` |
| `crawl` | `crawl` | heavy-tla | `crawl.db` (skeletons) | `crawl.db` (with IN:DO:OUT) |

### 2. No Persistent Connections — Stateless Workers Are Natural

- `CrawlStore` (SQLite) uses context-manager scoping — connection opened and closed per command
- `RegistryDag` loads from JSON, mutates in memory, saves back — no live connection
- `ClaudeSDKClient` is created per-GWT in loop, per-call in crawl/gwt-author — no connection pooling
- No thread pools, no caches, no globals survive between commands
- `ProjectContext` is a frozen dataclass constructed fresh per command

This means workers can reconstruct all state from object storage + DB without any warm-up or session affinity.

### 3. External Tool Dependencies Define Worker Classes

| Worker Class | Tools Required | Resource Profile |
|-------------|----------------|-----------------|
| **light** | Python only | Low CPU, low memory, fast (<10s) |
| **heavy-tla** | Java JRE + `tla2tools.jar` + Claude Agent SDK | High memory (TLC), long-running (up to 40min per GWT with 8 retries × 300s) |
| **heavy-lang** | Claude Agent SDK + one of: pytest, npx+tsc+jest, cargo, go | Medium memory, medium duration |

### 4. State That Must Move to Postgres

| Current Location | Content | Size Profile | Access Pattern |
|-----------------|---------|-------------|----------------|
| `dag.json` | DAG graph (nodes, edges, closure) | 10KB–1MB | Read-heavy, write-on-mutation |
| `crawl.db` | FnRecord table + relations | 100KB–50MB | Read-heavy during loop, write during crawl |
| `criterion_bindings.json` | Idempotency map | <10KB | Read-modify-write |
| `*_result.json` | Job outcomes | <1KB each | Write-once, read-many |
| `config.toml` | Project config | <1KB | Read-only after init |

### 5. State That Must Move to Object Storage

| Current Location | Content | Size Profile | Access Pattern |
|-----------------|---------|-------------|----------------|
| `schema/*.json` | Input schemas | 1KB–100KB each | Read-only after upload |
| `specs/*.tla` | Verified TLA+ specs | 5KB–50KB each | Write-once per GWT, read by bridge |
| `specs/*.cfg` | TLC config | <1KB each | Write-once, read by bridge |
| `specs/*_traces.json` | Counterexample traces | 1KB–100KB | Write-once, read by bridge |
| `specs/*_sim_traces.json` | Simulation traces | 1KB–500KB | Write-once, read by gen-tests |
| `bridge/*_bridge_artifacts.json` | Bridge output | 5KB–50KB each | Write-once, read by gen-tests |
| `sessions/*_attempt*.txt` | LLM response logs | 5KB–100KB each | Write-once, read for debugging |
| `context/*.md` | Plan path docs | 1KB–50KB | Read-only |

### 6. ProjectContext Needs a Hosted Mode

`ProjectContext.from_target()` (`context.py:68`) currently dispatches between `self_hosting()`, `external()`, and `installed()`. A fourth mode is needed:

```python
@classmethod
def hosted(cls, project_id: str, workspace: Path, storage_client) -> "ProjectContext":
    """Ephemeral worker context — paths point to temp workspace, artifacts go to object storage."""
```

This would:
- Set `state_root` to `/workspace/.cw9/` (ephemeral)
- Provide a `storage_client` for downloading inputs and uploading outputs
- Keep `template_dir` and `tools_dir` pointing to baked-in container paths

### 7. Job State Machine

From the existing `LoopState` enum (`one_shot_loop.py:50`) and pipeline behavior:

```
PENDING → QUEUED → RUNNING → {PASSED | FAILED | RETRYING}
                                                    ↓
                                              RUNNING (next attempt)
```

The `LoopResult` enum (`one_shot_loop.py:44`) already has `PASS`, `RETRY`, `FAIL` — these map cleanly to job state transitions.

### 8. Claude Agent SDK Session Management

Key detail for hosted workers: `run_loop()` creates **one** `ClaudeSDKClient` per GWT and reuses it across all retry attempts (`loop_runner.py:265-274`). The client maintains conversation context — each retry sees the full history of previous attempts.

This means a `loop` worker must:
- Create the SDK client at job start
- Keep it alive across all retries within the same job
- Disconnect in `finally` (already done via `safe_disconnect()` at `loop_runner.py:357`)

The client is **not** shared across GWTs, so different GWT jobs are fully independent.

### 9. Temp Directory Usage

`compile_compose_verify()` creates temp dirs (`/tmp/cw9_XXXX/`) for PlusCal compilation and TLC execution. In a containerized worker:
- These stay as-is — they're already ephemeral
- The container's `/tmp` is isolated per job
- On job completion, upload the verified `.tla` and `.cfg` to object storage before container exits

### 10. The LLM Helper Factory Pattern

Two patterns exist for LLM calls:
- `_build_llm_fn(model, system_prompt)` (`cli.py:1115`) — builds a sync callable wrapping async Agent SDK. Used by crawl and gwt-author.
- `_make_client(system_prompt)` (`loop_runner.py:54`) — creates a persistent client for multi-turn loop conversations.

Both pop the `CLAUDECODE` env var before SDK init. Workers need the SDK credentials injected via environment, not inherited from a parent CLI process.

## Proposed Changes

### API Service (Control Plane)

New module: `python/registry/api/` or separate service.

Endpoints needed (derived from CLI commands):
- `POST /projects` — replaces `cmd_init`
- `POST /projects/{id}/upload` — upload schemas, source code
- `POST /projects/{id}/runs` — create a run (triggers job DAG)
- `GET /projects/{id}/runs/{run_id}` — status (replaces `cmd_status`)
- `GET /projects/{id}/runs/{run_id}/artifacts/{path}` — download specs, bridge artifacts, test files
- `POST /projects/{id}/ingest` — trigger brownfield ingest
- `POST /projects/{id}/crawl` — trigger LLM extraction
- `POST /projects/{id}/gwt-author` — trigger GWT authoring

### Worker Service (Execution Plane)

Wraps existing functions with job lifecycle:
1. Dequeue job from queue
2. Download inputs from object storage to `/workspace/.cw9/`
3. Call existing function (e.g., `run_loop()`, `run_bridge()`)
4. Upload outputs to object storage
5. Update job status in Postgres
6. Exit

Key functions to wrap (no modification needed to these — just call them):
- `run_loop()` (`loop_runner.py:220`)
- `run_bridge()` (`bridge.py:692`)
- `run_test_gen_loop()` (`test_gen_loop.py:322`)
- `SchemaExtractor.extract()` (`extractor.py`)
- `_register_payload()` (`cli.py:439`)
- Crawl orchestration (`crawl_orchestrator.py`)

### Data Layer Changes

- `CrawlStore` → Postgres adapter with same interface
- `RegistryDag.load/save` → Postgres JSON column or object storage
- `write_result_file()` → DB update + object storage for logs
- `criterion_bindings.json` → DB table

### ProjectContext Enhancement

Add `ProjectContext.hosted()` factory that:
- Sets workspace paths to ephemeral container dirs
- Provides object storage download/upload hooks
- Points `tools_dir` to container-baked Java/TLC tools

## CW9 Mention Summary
Functions: cmd_init(), cmd_extract(), cmd_loop(), cmd_bridge(), cmd_gen_tests(), cmd_pipeline(), cmd_ingest(), cmd_crawl(), cmd_gwt_author(), run_loop(), run_bridge(), run_test_gen_loop(), compile_compose_verify(), extract_pluscal(), route_result(), parse_counterexample(), translate_counterexample(), run_tlc_simulate(), compile_pluscal(), run_tlc(), generate_cfg(), classify_tlc_error(), query_context(), format_prompt_context(), _build_prompt(), build_retry_prompt(), _make_client(), _call_llm_with_client(), call_llm(), _register_payload(), _resolve_gwt_ids(), _build_llm_fn(), _build_extract_fn(), write_result_file(), gather_status(), parse_spec(), translate_state_vars(), translate_actions(), translate_invariants_to_verifiers(), translate_invariants_to_assertions(), translate_traces(), build_test_plan_prompt(), build_review_prompt(), build_codegen_prompt(), build_compiler_hints(), discover_api_context(), get_profile(), verify_test_file()
Files: python/registry/cli.py, python/registry/loop_runner.py, python/registry/one_shot_loop.py, python/registry/bridge.py, python/registry/test_gen_loop.py, python/registry/lang.py, python/registry/lang_typescript.py, python/registry/lang_rust.py, python/registry/lang_go.py, python/registry/tla_compiler.py, python/registry/context.py, python/registry/types.py, python/registry/status.py, python/registry/dag.py, python/registry/extractor.py, python/registry/crawl_store.py, python/registry/crawl_types.py, python/registry/crawl_orchestrator.py, python/registry/crawl_bridge.py, python/registry/gwt_author.py, python/registry/traces.py, python/registry/bindings.py, python/registry/_resources.py, python/registry/composer.py
Directories: python/registry/, templates/pluscal/, tools/, schema/
