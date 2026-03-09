---
date: 2026-03-09T11:30:46-04:00
researcher: claude-opus
git_commit: f8273666b4ea7071b1bd7667a4863b096742f131
branch: master
repository: CodeWriter9.0
topic: "Phase 2 Complete → Phase 3 One-Shot Loop"
tags: [implementation, tla-plus, pluscal, composition-engine, one-shot-loop, phase-3, single-piece-flow]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 2 Complete → Phase 3 One-Shot Loop

## Task(s)

### Completed
1. **Phase 0: Extract the Graph** — Rust + Python DAG engine, all tests passing.
2. **Phase 1: First Templates** — 4 PlusCal templates, registry CRUD verified by TLC, self-registered.
3. **Phase 2: Composition Engine** — All deliverables met:
   - Composition engine state machine (`composition_engine.tla`) instantiated from `state_machine.tla` template, TLC verified (1,553 states, 7 invariants, 0 violations)
   - `compose(spec_a, spec_b)` implemented in Python: TLA+ parser, variable unification, module composer, cross-invariant generation, spec cache
   - `COMPOSES` edge type added to type system
   - Phase 2 components self-registered in DAG (3 new nodes, 9 new edges)
   - DAG totals: 58 nodes, 74 edges, 11 connected components
   - All 61 tests passing (26 composer + 10 DAG + 25 extractor)

### Next Step (Single Piece Flow)
**Phase 3: The One-Shot Loop.** Build the core algorithm that queries registry context, assembles LLM prompts, extracts PlusCal fragments, runs compile→compose→TLC pipeline, translates counterexamples, and routes pass/retry/fail. See `BOOTSTRAP.md` lines ~460-507.

## Critical References
- `BOOTSTRAP.md:460-507` — Phase 3 section defines one-shot loop deliverables, bootstrap act, and the 3 GWT behaviors to register
- `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md:640-667` — Layer separation principle (LLM writes PlusCal only, system handles compilation + composition)

## Recent changes
- Created: `templates/pluscal/instances/composition_engine.tla` — State machine instance for composition lifecycle (TLC verified)
- Created: `templates/pluscal/instances/composition_engine.cfg` — TLC config (SpecSet={s1,s2,s3}, MaxSteps=8)
- Created: `python/registry/composer.py` — TLA+ composition engine (parser, variable unifier, composer, cross-invariant generator, spec cache)
- Created: `python/tests/test_composer.py` — 26 tests covering parser, variable detection, composition, cross-invariants, cache
- Updated: `python/registry/types.py:42` — Added `COMPOSES = "composes"` edge type
- Updated: `python/registry/extractor.py:559-585` — Phase 2 self-registration (tpl-0006, comp-0001, comp-0002 + 9 edges)
- Updated: `schema/registry_dag.json` — Re-extracted with Phase 2 components (58 nodes, 74 edges)
- Updated: `BOOTSTRAP.md:429-457` — Phase 2 completion details

## Learnings

### TLA+ parser regex patterns for simple vs compiled modules
The TLA+ parser in `composer.py` handles two formats: (1) simple hand-written modules (single-line EXTENDS/CONSTANTS) and (2) PlusCal-compiled modules (multi-line CONSTANTS blocks, `\* BEGIN TRANSLATION` sections). Key fix: EXTENDS regex must be line-bounded (`[^\n]+`) to prevent greedy matching across the entire file. CONSTANTS regex uses `[,\n]+` splitting to handle both single-line and multi-line formats. See `python/registry/composer.py:67-72`.

### Composition produces valid TLA+ structure
The composed module follows a strict pattern: prefixed definitions (`ModA_DefName`, `ModB_DefName`) to avoid name collisions, Init/Next/Inv are composed at the top level. `UNCHANGED` clauses are critical: when module A takes a step, all B-only variables must be held constant, and vice versa. This is the `Next_composed = (Next_A /\ UNCHANGED b_vars) \/ (Next_B /\ UNCHANGED a_vars)` pattern.

### Two-phase action model carries forward
The dirty-flag two-phase pattern from Phase 1 CRUD template was reused in the composition engine state machine. Same pattern: mutate primary state in the action label, update derived state in `UpdateDerived` label, gate invariants with `dirty = TRUE \/`. This is now a confirmed project-wide convention.

### PlusCal compilation workflow (unchanged from Phase 1)
```
java -cp tools/tla2tools.jar pcal.trans <file>.tla
java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning
```

### Python test runner
`cd python && python3 -m pytest tests/ -v` — runs all 61 tests.

### DAG re-extraction command
```python
from registry.extractor import SchemaExtractor
e = SchemaExtractor(schema_dir='/home/maceo/Dev/CodeWriter9.0/schema/')
dag = e.extract()
dag.save('/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json')
```
Note: first arg is `schema_dir` (directory), NOT the registry file path.

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/BOOTSTRAP.md` — Updated through Phase 2 (lines 429-457)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/composition_engine.tla` — Composition engine state machine (TLC verified)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/composition_engine.cfg` — TLC config
- `/home/maceo/Dev/CodeWriter9.0/python/registry/composer.py` — Composition engine implementation
- `/home/maceo/Dev/CodeWriter9.0/python/tests/test_composer.py` — 26 composition tests
- `/home/maceo/Dev/CodeWriter9.0/python/registry/types.py` — Updated: COMPOSES edge type
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Updated: Phase 2 self-registration (lines 559-585)
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — Re-extracted DAG (58 nodes, 74 edges)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/crud.tla` — CRUD template (Phase 1)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/state_machine.tla` — State machine template (Phase 1)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/queue_pipeline.tla` — Queue/pipeline template (Phase 1)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/auth_session.tla` — Auth/session template (Phase 1)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/registry_crud.tla` — Registry CRUD (Phase 1, TLC verified)
- `/home/maceo/Dev/CodeWriter9.0/tools/tla2tools.jar` — TLA+ toolbox v1.8.0
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — Architectural plan

## Action Items & Next Steps

### IMMEDIATE: Phase 3 — The One-Shot Loop (Single Piece Flow)

From `BOOTSTRAP.md:460-507`:

**Step 1: Register the loop's GWT behaviors in the registry.**
Three new behaviors to add:
1. "Given a new GWT, when context is queried from registry, then all transitive deps are included"
2. "Given a TLC counterexample, when translated to natural language, then it references PlusCal-level concepts only"
3. "Given two consecutive failures, when routing, then requirements inconsistency is reported (not retried)"

**Step 2: Build the pipeline modules:**
- Registry context query → LLM prompt assembly
- LLM response → PlusCal fragment extraction
- Fragment → compile → compose → TLC pipeline
- Counterexample → natural language translator
- Pass/retry/fail routing

**Step 3: Detect dependencies.** The loop references the registry (for context), the composition engine (for compose), TLC (for verify). These form a connected component in the DAG.

**Step 4: Compose the specs.** The loop's spec joins with the composition engine's spec on the `composed_specs` variable. TLC checks the interleaving: can the loop call compose while compose is mid-operation? (It shouldn't.)

**Step 5: TLC passes or fix the design.** This is the second turn of the flywheel — the loop is specified and verified using the very tools it orchestrates.

**Step 6: Self-register Phase 3 components in the DAG.**

### Cross-layer composition targets (from Phase 2 handoff, still relevant)
- Frontend `api_contracts` ↔ backend `endpoints`
- Middleware `interceptors` ↔ shared `interceptor_interfaces`
- Backend `services` ↔ `data_access_objects`
- Shared `verifiers` ↔ backend `data_structures`

### THEN: Integrate Claude Agent SDK
After the one-shot loop is specified and verified, wire up the actual LLM calls using Claude Agent SDK.

## Other Notes

### Uncommitted Phase 2 work
Phase 2 work is uncommitted on master. The last commit is `f827366` (Phase 1 handoff + TLC state exclusion). The user may want to commit Phase 2 before starting Phase 3.

### Tech stack
- Rust core DAG engine: `crates/registry-core/`
- Python orchestration: `python/registry/`
- PlusCal templates: `templates/pluscal/`
- TLA+ toolbox: `tools/tla2tools.jar` (Java 21 required, available on system)

### The 4+1 PlusCal templates
1. **CRUD** (tpl-0001) — verified via registry instantiation (Phase 1)
2. **State machine** (tpl-0002) — verified via composition engine instantiation (Phase 2)
3. **Queue/pipeline** (tpl-0003) — template ready, no instance yet
4. **Auth/session** (tpl-0004) — template ready, no instance yet
5. **Registry CRUD instance** (tpl-0005) — Phase 1 bootstrap act
6. **Composition engine instance** (tpl-0006) — Phase 2 bootstrap act

### Key architectural principle
LLM writes PlusCal ONLY. The system handles compilation to TLA+ and composition. Counterexamples translate back up to PlusCal-level language. Templates have clear fill-in markers that separate what the LLM fills (domain parameters) from what the system handles (syntax, composition).

### Composition engine API surface
```python
from registry.composer import compose, compose_from_files, compose_component, parse_tla, parse_tla_file
```
- `parse_tla(text)` / `parse_tla_file(path)` → `TlaModule`
- `compose(mod_a, mod_b, dag=None, cross_invariants=None)` → `ComposedModule`
- `compose_from_files(path_a, path_b, dag=None)` → `ComposedModule`
- `compose_component(members, paths, dag, component_id)` → `ComposedModule | None`
- `generate_cross_invariants(mod_a, mod_b, dag)` → `list[str]`
- `SpecCache.put(component_id, composed)` / `.get(component_id)` / `.save(directory)`
