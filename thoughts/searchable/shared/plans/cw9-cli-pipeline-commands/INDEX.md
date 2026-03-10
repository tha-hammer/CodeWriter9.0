```
┌──────────────────────────────────────────────────────────────────────┐
│  CW9 CLI Pipeline Commands — Implementation Plan                     │
│  Status: DRAFT v5  |  Date: 2026-03-10                               │
│  v5 changelog: TLC simulation traces as test case generator          │
│  v4 changelog: Phase 5 LLM loop rewrite (see v4 changelog)          │
└──────────────────────────────────────────────────────────────────────┘
```

# CW9 CLI Pipeline Commands

## Overview

Two-layer architecture for making the CW9 pipeline usable on external projects:

**Layer 1 — Library API** (called by upstream systems, Rust crate, or scripts):
```python
dag.register_gwt(given="...", when="...", then="...", parent_req="req-0008")
```

**Layer 2 — CLI commands** (operate on DAG state, don't care where GWTs came from):
```
cw9 extract → cw9 loop <gwt-id> → cw9 bridge <gwt-id> → cw9 gen-tests <gwt-id> → cw9 test
```

GWTs arrive as natural language (JSON, database, API call) with no IDs, no DAG registration, no PlusCal spec. The library layer assigns IDs, creates DAG nodes, wires edges. The CLI layer picks up from there.

## Plan Files

| File | Phase | Description |
|---|---|---|
COMPLETE | [phase-0-register-gwt.md](phase-0-register-gwt.md) | Phase 0 | Library API — `RegistryDag.register_gwt()` |
COMPLETE | [phase-1-config-toml.md](phase-1-config-toml.md) | Phase 1 | `config.toml` → `from_target()` |
COMPLETE | [phase-2-extract.md](phase-2-extract.md) | Phase 2 | `cw9 extract` with GWT merge |
COMPLETE | [phase-3-loop.md](phase-3-loop.md) | Phase 3 | `cw9 loop <gwt-id>` — LLM → PlusCal → TLC |
COMPLETE | [phase-4-bridge.md](phase-4-bridge.md) | Phase 4 | `cw9 bridge <gwt-id>` — spec → bridge artifacts |
COMPLETE | [phase-5a-trace-pipeline.md](phase-5a-trace-pipeline.md) | Phase 5A | Connect the trace pipeline + simulation trace types |
COMPLETE | [phase-5b-tla-compiler.md](phase-5b-tla-compiler.md) | Phase 5B | TLA+ condition compiler (prompt enrichment) |
COMPLETE | [phase-5c-gen-tests.md](phase-5c-gen-tests.md) | Phase 5C | `cw9 gen-tests <gwt-id>` — LLM test generation loop |
COMPLETE | [phase-6-test.md](phase-6-test.md) | Phase 6 | `cw9 test` — run generated tests |
| [testing-and-meta.md](testing-and-meta.md) | — | Testing strategy, performance, changelogs, references |

## Current State Analysis

- `cw9 init` and `cw9 status` work (292 tests passing)
- `config.toml` is written by init but never read back
- `SchemaExtractor.extract()` works on external schemas (tested)
- `RegistryDag.save()/load()` exist but are never used in production
- GWT IDs are hardcoded in `extractor.py` (`gwt-0001`..`gwt-0023`), next available: `gwt-0024`
- Requirement IDs: `req-0001`..`req-0007`, next available: `req-0008`
- `Node.behavior()` factory at `types.py:64` accepts `(id, name, given, when, then)` — text field left None
- `Node.requirement()` factory at `types.py:72` accepts `(id, text)` — **2 args only, name hardcoded to ""**
- `RegistryDag.add_node()` at `dag.py:36` silently overwrites duplicate IDs (no validation)
- No ID allocator exists — all IDs are hardcoded string literals
- `query_affected_tests()` exists at `dag.py:242` but `test_artifacts` is never persisted
- `process_response()` at `one_shot_loop.py:615` requires **3 positional args**: `(llm_response, module_name, cfg_text)`
- `LoopStatus` at `one_shot_loop.py:84` has **no `retry_prompt` field** — retry prompts are built externally by each `run_*_loop.py` script via standalone `build_retry_prompt()` functions
- `CounterexampleTrace` at `one_shot_loop.py:64` and `TlcTrace` at `bridge.py:52` are **disconnected types** — no converter exists
- `translate_traces()` at `bridge.py:582` is never called with real data — `test_scenarios` is always `[]`

### Key Discoveries

| Finding | Location | Impact |
|---|---|---|
| `tomllib` available (Python 3.11+) | `pyproject.toml:5` | No new deps for config parsing |
| No ID allocator exists | `extractor.py:435-976` | Must build `register_gwt()` with auto-ID |
| `Node.behavior()` doesn't set `text` | `types.py:64-69` | `text` stays None — loop generates PlusCal from GWT strings |
| `Node.requirement()` takes 2 args | `types.py:72-73` | `requirement(id, text)` — name hardcoded to `""` |
| `add_node()` overwrites silently | `dag.py:36-40` | `register_gwt()` must check for duplicates |
| `PATH_TO_RESOURCE` is hardcoded | `extractor.py:62-97` | Known limitation — canonical UUIDs required |
| All LLM calls identical pattern | `run_change_prop_loop.py:293-317` | Extract common `call_llm()` |
| `_self_describe()` is 500+ lines | `extractor.py:414-997` | Self-hosting GWTs stay there; external GWTs use `register_gwt()` |
| `process_response()` needs 3+ args | `one_shot_loop.py:615-622` | `(llm_response, module_name, cfg_text)` — NOT `(response, gwt_id)` |
| No `retry_prompt` on LoopStatus | `one_shot_loop.py:84-93` | Must build retry prompts from `status.counterexample` + `status.error` |
| `extract()` rebuilds from scratch | `extractor.py:142-144` | `RegistryDag()` — fresh DAG, obliterates registered GWTs |
| Bridge `test_scenarios` always empty | `bridge.py:679` | `traces` defaults to `None` → `[]` → no scenarios generated |
| `_invariant_to_condition()` is shallow | `bridge.py:553-565` | 5 text substitutions, not executable Python |
| Generated tests have real logic | `run_change_prop_loop.py:572-621` | 5 `_verify_*` methods with actual DAG queries |

## Desired End State

After implementation:

```
┌─────────────────────────────────────────────────────────┐
│  Upstream System (Rust crate, script, API)              │
│                                                         │
│  dag = RegistryDag.load(ctx.dag_path)                   │
│  gwt_id = dag.register_gwt(                             │
│      given="a user submits a form",                     │
│      when="validation runs",                            │
│      then="errors are displayed inline",                │
│      parent_req="req-0008"                              │
│  )                                                      │
│  dag.save(ctx.dag_path)                                 │
│  # gwt_id == "gwt-0024"                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  CLI Pipeline (operates on DAG state)                   │
│                                                         │
│  cw9 extract        # build DAG from schemas            │
│                     # ↑ MERGES registered GWTs back in  │
│  cw9 loop gwt-0024  # GWT → PlusCal → TLC              │
│  cw9 bridge gwt-0024 # TLC trace → bridge artifacts     │
│  cw9 gen-tests gwt-0024 # artifacts → pytest file       │
│  cw9 test           # run tests (smart targeting)       │
└─────────────────────────────────────────────────────────┘
```

### Artifact Convention

All commands locate artifacts by GWT ID under `.cw9/`:

```
.cw9/
  dag.json                              # saved by: cw9 extract / register_gwt()
  specs/<gwt-id>.tla                    # saved by: cw9 loop
  specs/<gwt-id>.cfg                    # saved by: cw9 loop
  specs/<gwt-id>_sim_traces.json        # saved by: cw9 loop (TLC -simulate output)
  specs/<gwt-id>_traces.json            # saved by: cw9 loop (counterexample traces from retries)
  bridge/<gwt-id>_bridge_artifacts.json # saved by: cw9 bridge
  sessions/<gwt-id>_attempt{N}.txt     # saved by: cw9 loop
```

Test output: `<target>/tests/generated/test_<gwt-id>.py` (saved by `cw9 gen-tests`).

## What We're NOT Doing

| NOT doing | Doing instead |
|---|---|
| Bundled pipeline command (`cw9 run-all`) | Explicit chainable steps |
| ~~Per-module hardcoded test generators~~ | **Phase 5A-C**: trace pipeline (5A) + compiler hints (5B) + LLM test generation loop (5C) |
| Dynamic `PATH_TO_RESOURCE` from registry | Canonical UUID scheme (known limitation) |
| `cw9 ingest` (brownfield code scanning) | Deferred — users write schemas by hand |
| Rust binary wrapper | Python library API + CLI (Rust calls Python) |
| `cw9 register-gwt` CLI command | Library API only — upstream calls `dag.register_gwt()` |
| GWT auto-discovery from code | Explicit registration via API |
| Full TLA+ → Python compiler as test generator | Bounded compiler as prompt enrichment; LLM loop for test generation |
| Few-shot from oracle test files | TLC simulation traces as primary test derivation context |
| TLC as pass/fail gate only | TLC as test case generator via `-simulate` mode |
| LLM invents test topologies from scratch | LLM translates TLC-generated traces into Python API calls |

## Implementation Order

```
Phase 0 (register_gwt) ──→ Phase 1 (config.toml) ──→ Phase 2 (extract + merge)
                                                           │
                                                           ▼
                                     Phase 3 (loop + simulate) ──→ Phase 4 (bridge)
                                         │                             │
                                         │ counterexample              │ bridge artifacts
                                         │ traces                      │ + sim traces (v5)
                                         ▼                             ▼
                              Phase 5A (trace pipe         Phase 5B (TLA+ compiler)
                                + sim trace types [v5])          │
                                    │                            │
                                    └───────┬────────────────────┘
                                            │ prompt context
                                            │ (v5: sim traces = PRIMARY)
                                            ▼
                              Phase 5C (gen-tests LLM loop) → Phase 6 (test)
```

Phase 0 is the library foundation — everything else depends on GWTs being in the DAG.
Phase 1 unlocks ergonomic CLI use for all subsequent phases.
Phase 2 is required by Phase 3 (loop loads saved DAG) — now includes merge logic.
Phases 3→4 are the pipeline chain. **Phase 3 now runs TLC `-simulate` after PASS (v5)**, generating concrete traces that flow through Phase 4 into 5C.
Phase 5A connects the trace type systems (mechanical plumbing). **v5 adds `SimulationTrace` type + `format_traces_for_prompt()`.**
Phase 5B builds the TLA+ compiler as a prompt enrichment utility (same code as v3, reframed role).
Phase 5C is the core test generation — LLM loop consuming **simulation traces (primary, v5)** + 5B hints + Phase 4's bridge artifacts.
Phase 6 is independent but most useful after Phase 5C.
