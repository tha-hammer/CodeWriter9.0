---
date: 2026-03-09T11:52:27-04:00
researcher: claude-opus
git_commit: 3872907
branch: master
repository: CodeWriter9.0
topic: "Phase 3 Complete → Phase 4 The Bridge (Single Piece Flow)"
tags: [implementation, tla-plus, pluscal, one-shot-loop, bridge, spec-to-code, phase-4, single-piece-flow]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 3 Complete → Phase 4 The Bridge

## Task(s)

### Completed
1. **Phase 0: Extract the Graph** — Rust + Python DAG, all tests passing.
2. **Phase 1: First Templates** — 4 PlusCal templates, TLC verified, self-registered.
3. **Phase 2: Composition Engine** — `compose(spec_a, spec_b)`, TLC verified (1,553 states, 7 invariants).
4. **Phase 3: One-Shot Loop** — All deliverables met:
   - One-shot loop state machine (`one_shot_loop.tla`): 11 states, TLC verified (3,105 states, 6 invariants, 0 violations)
   - Composed spec (`loop_compose_composed.tla`): loop + composition engine as concurrent processes, TLC verified (34,081 states, 10 invariants, 0 violations)
   - `OneShotLoop` class in Python: context query, PlusCal extraction, compile→compose→TLC pipeline, counterexample translator, pass/retry/fail router
   - Phase 3 self-registered: 8 new nodes, 16 new edges
   - DAG totals: 66 nodes, 90 edges, 11 components
   - All 96 tests passing (35 loop + 26 composer + 10 DAG + 25 extractor)

### Next Step (Single Piece Flow)
**Phase 4: The Bridge.** This is the first phase where we CAN use the one-shot loop. Build mechanical spec-to-code translators. See `BOOTSTRAP.md:535-567`.

## Critical References
- `BOOTSTRAP.md:535-567` — Phase 4 section defines Bridge deliverables and bootstrap act
- `python/registry/one_shot_loop.py` — The `OneShotLoop` class that Phase 4 will use for the first time

## Recent changes
- Created: `python/registry/one_shot_loop.py` — 5 pipeline components + `OneShotLoop` orchestrator class
- Created: `python/tests/test_one_shot_loop.py` — 35 tests
- Created: `templates/pluscal/instances/one_shot_loop.tla` — 11-state loop lifecycle spec
- Created: `templates/pluscal/instances/one_shot_loop.cfg` — TLC config (MaxRetries=1, MaxSteps=15)
- Created: `templates/pluscal/instances/loop_compose_composed.tla` — Two-process composed spec
- Created: `templates/pluscal/instances/loop_compose_composed.cfg` — TLC config
- Updated: `python/registry/extractor.py:594-679` — Phase 3 self-registration (8 nodes, 16 edges)
- Updated: `schema/registry_dag.json` — Re-extracted (66 nodes, 90 edges)
- Updated: `BOOTSTRAP.md:458-481` — Phase 3 completion details

## Learnings

### OneShotLoop does NOT call the LLM
The `OneShotLoop` class handles context preparation and response processing. The caller handles LLM interaction. This allows testing without LLM and swapping backends. Key API: `loop.query(behavior_id)` → `loop.format_prompt()` → (caller calls LLM) → `loop.process_response(llm_response, ...)`. See `python/registry/one_shot_loop.py:555-644`.

### Concurrent composition invariant: guard on START, not FINISH
The composed spec discovered that the engine can complete compose before the loop enters composing — this is fine. The real safety property is that the engine cannot START a new compose while `compose_busy=TRUE`. Naive invariants confuse "engine already finished" with "engine actively composing." See `templates/pluscal/instances/loop_compose_composed.tla:251`.

### PlusCal extraction tries 4 patterns in specificity order
1. Fenced `tla`/`pluscal` marker blocks
2. Generic fenced blocks containing `--algorithm`
3. Bare `--algorithm ... end algorithm` blocks
4. PlusCal comment wrappers `(* ... *)`
See `python/registry/one_shot_loop.py:174-218`.

### Two-failure limit is stateless
Router depends only on `TLCResult.success` + `consecutive_failures`. No history needed. `MaxRetries=1` in the spec maps directly to the Python router logic. See `python/registry/one_shot_loop.py:511-548`.

### Pipeline commands (unchanged)
```
java -cp tools/tla2tools.jar pcal.trans <file>.tla
java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning
cd python && python3 -m pytest tests/ -v
```

### DAG re-extraction
```python
from registry.extractor import SchemaExtractor
e = SchemaExtractor(schema_dir='/home/maceo/Dev/CodeWriter9.0/schema/')
dag = e.extract()
dag.save('/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json')
```

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/BOOTSTRAP.md` — Updated through Phase 3 (lines 458-481)
- `/home/maceo/Dev/CodeWriter9.0/python/registry/one_shot_loop.py` — One-shot loop implementation (644 lines)
- `/home/maceo/Dev/CodeWriter9.0/python/tests/test_one_shot_loop.py` — 35 tests
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/one_shot_loop.tla` — Loop lifecycle spec (TLC verified)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/one_shot_loop.cfg` — TLC config
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/loop_compose_composed.tla` — Composed spec (TLC verified)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/loop_compose_composed.cfg` — TLC config
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Phase 3 self-registration (lines 594-679)
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — DAG (66 nodes, 90 edges)
- `/home/maceo/Dev/CodeWriter9.0/python/registry/composer.py` — Composition engine (Phase 2)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/state_machine.tla` — State machine template
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/handoffs/general/2026-03-09_11-45-05_phase3-complete-phase4-next.md` — Implementation LLM's handoff

## Action Items & Next Steps

### IMMEDIATE: Phase 4 — The Bridge (Single Piece Flow)

From `BOOTSTRAP.md:535-567`:

**This is the first phase where we CAN use the one-shot loop.** The bootstrap act is: describe bridge requirements in plain language → run through the loop → loop uses registry for context, generates PlusCal specs, compiles, composes, verifies.

**Deliverables — 4 mechanical spec-to-code translators:**
1. **TLA+ state variables → data model / schema generator** — Translates state vars into `data_structures` shape (fields, types, validation)
2. **TLA+ actions → function signature generator** — Translates actions into `processors.operations` shape (params, returns, errors)
3. **TLA+ invariants → test assertion generator** — Translates invariants into `verifiers` shape and `testing.assertions` shape (conditions, message)
4. **TLC traces → scenario test generator** — Translates traces into concrete test scenarios

**Step-by-step:**
1. Register the bridge's GWT behaviors in the registry
2. Describe the bridge requirements in plain language
3. Run them through `OneShotLoop` — this is the FIRST real use of the loop
4. The loop queries registry context (transitive deps of bridge GWTs)
5. Generate PlusCal specs for the bridge
6. Compile → compose → TLC verify
7. Implement the 4 translators conforming to existing schema shapes
8. Activate `fs-y3q2` (plan_artifact_store) for generated plans
9. Self-register Phase 4 components in the DAG

**Key constraint:** The bridge translates TLA+ specs into artifacts that conform to EXISTING schema shapes. The schemas define the target — the bridge must produce `data_structures`, `processors.operations`, `verifiers`, and `testing.assertions` shapes exactly as defined.

### THEN: Phase 5+
After the Bridge, we have the full pipeline from requirements → specs → verified code artifacts.

## Other Notes

### Uncommitted Phase 3 work
Phase 3 work is uncommitted on master. Last commit is `3872907` (Phase 1). The user committed Phase 2 (but git log now shows it may have been rebased/squashed). Check `git status` before starting.

### Tech stack
- Rust core DAG engine: `crates/registry-core/`
- Python orchestration: `python/registry/`
- PlusCal templates: `templates/pluscal/`
- TLA+ toolbox: `tools/tla2tools.jar` (Java 21 required)

### One-shot loop API surface
```python
from registry.one_shot_loop import OneShotLoop, query_context, format_prompt_context
from registry.one_shot_loop import extract_pluscal, compile_compose_verify
from registry.one_shot_loop import parse_counterexample, translate_counterexample, route_result

# High-level orchestrator
loop = OneShotLoop(dag=dag, project_root='/home/maceo/Dev/CodeWriter9.0')
loop.query(behavior_id='gwt-0005')
prompt = loop.format_prompt()
# ... caller sends prompt to LLM, gets response ...
status = loop.process_response(llm_response, module_name='bridge_data_model', cfg_text='...')
# status.result is LoopResult.PASS / RETRY / FAIL
```

### Composition engine API surface
```python
from registry.composer import compose, compose_from_files, parse_tla, parse_tla_file
```

### The flywheel acceleration
Phase 4 is the **third turn of the flywheel**. Each phase uses tools built in previous phases:
- Phase 1 used Phase 0 (registry) to register templates
- Phase 2 used Phase 0+1 (registry + templates) to build composition engine
- Phase 3 used Phase 0+1+2 (registry + templates + composition) to build the loop
- **Phase 4 uses Phase 0+1+2+3 (registry + templates + composition + LOOP)** — first real use of the loop to generate its own bridge components
