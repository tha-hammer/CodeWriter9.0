---
date: 2026-03-09T11:12:26-04:00
researcher: claude-opus
git_commit: 4a0c14a9c8332bc5d0b0aad28d46eaf157e8b21c
branch: master
repository: CodeWriter9.0
topic: "Phase 1 Complete → Phase 2 Composition Engine"
tags: [implementation, tla-plus, pluscal, composition-engine, phase-2, single-piece-flow]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 1 Complete → Phase 2 Composition Engine

## Task(s)

### Completed
1. **Phase 0: Extract the Graph** — Rust + Python DAG engine, 50 nodes, 48 edges. All tests passing.
2. **Phase 1: First Templates** — All deliverables met:
   - 4 PlusCal templates (CRUD, state machine, queue/pipeline, auth/session) with `{{FILL:...}}` markers for external project reuse
   - Registry CRUD instantiation verified by TLC (7 invariants, 12,245 states, 0 violations)
   - `fs-x7p6` (tla_artifact_store) activated in resource registry
   - Phase 1 components self-registered in DAG (6 new nodes, 17 new edges)
   - DAG totals: 55 nodes, 65 edges, 11 connected components
   - All 45 tests passing (10 Rust + 35 Python)

### Next Step (Single Piece Flow)
**Phase 2: Composition Engine.** Build `compose(spec_a, spec_b)` that takes two TLA+ modules sharing variables and produces a composed module. Apply the state machine template to the composition engine's own lifecycle. See `BOOTSTRAP.md` lines ~378-430.

## Critical References
- `BOOTSTRAP.md` — Phase 2 section (lines ~378-430) defines composition engine deliverables, bootstrap act, and cross-layer composition targets
- `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — TLA+ composition mechanics (lines ~650-667), layer separation principle

## Recent changes
- Created: `templates/pluscal/crud.tla` — Reusable CRUD template with fill-in markers and two-phase pattern
- Created: `templates/pluscal/state_machine.tla` — State machine template (enum states, guards, bypass)
- Created: `templates/pluscal/queue_pipeline.tla` — Queue/pipeline template (FIFO, no-item-loss)
- Created: `templates/pluscal/auth_session.tla` — Auth/session template (login/logout/expire/RBAC)
- Created: `templates/pluscal/instances/registry_crud.tla` — Registry CRUD instantiation (TLC verified)
- Created: `templates/pluscal/instances/registry_crud.cfg` — TLC model checking config
- Downloaded: `tools/tla2tools.jar` — TLA+ toolbox v1.8.0 (PlusCal compiler + TLC checker)
- Updated: `schema/resource_registry.generic.json` — Moved `fs-x7p6` from conditional to active resources
- Updated: `python/registry/extractor.py:500-548` — Added Phase 1 self-registration (tpl-0001..0005, fs-x7p6, edges)
- Updated: `schema/registry_dag.json` — Re-extracted with Phase 1 components (55 nodes, 65 edges)
- Updated: `BOOTSTRAP.md:276-375` — Phase 1 completion details, template library framing

## Learnings

### Two-phase action model is required for TLA+/PlusCal
TLA+ evaluates all primed variables simultaneously. A macro that sets `closure' := ActualClosure` computes `ActualClosure` using the **unprimed** `nodes`, not `nodes'`. Fix: split each action into two labels — Phase 1 (mutate primary state, set dirty flag) and Phase 2 (recompute derived state, clear dirty flag). Gate derived invariants with `dirty = TRUE \/`. This pattern is documented in the CRUD template and should be followed by all future templates/instances.

### Single-process loop beats multi-process for CRUD model checking
Initial attempt used separate PlusCal processes per action type, each with `\in IdSet` variable initialization. TLC enumerated 3^12 = 531K+ initial states from process variable combinations alone. Fix: single process with `either/or` nondeterministic action selection inside a `while TRUE` loop. State space dropped to 12,245 distinct states.

### Templates are for external projects, not just bootstrap
Key framing from user: "This application will be used to generate code for a variety of projects. We will need to keep templates for those external projects." The CRUD template is the first reusable template in a library. The registry bootstrap is just the first customer. Fill-in markers are the API surface for LLM parameterization.

### PlusCal compilation workflow
```
java -cp tools/tla2tools.jar pcal.trans <file>.tla    # compile PlusCal → TLA+
java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning  # run TLC
```

### Python test runner
Use `python3` (not `python`). Run from `python/` directory: `python3 -m pytest tests/ -v`.

### Schema patterns → template mapping
- execution_patterns: flat arrays (conditions[], rules[], bypass_conditions[]), no states/transitions fields
- process_chains: two variants — backend (steps[] as "Processor.operation") and middleware (interceptors[] + order[])
- security: nested auth/authz structure (strategies[], roles[], permissions[])
- access_controls: per-guard (singular condition, redirect path)

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/BOOTSTRAP.md` — Updated through Phase 1 (lines 276-375)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/crud.tla` — CRUD template
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/state_machine.tla` — State machine template
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/queue_pipeline.tla` — Queue/pipeline template
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/auth_session.tla` — Auth/session template
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/registry_crud.tla` — Registry CRUD (verified)
- `/home/maceo/Dev/CodeWriter9.0/templates/pluscal/instances/registry_crud.cfg` — TLC config
- `/home/maceo/Dev/CodeWriter9.0/tools/tla2tools.jar` — TLA+ toolbox
- `/home/maceo/Dev/CodeWriter9.0/python/registry/extractor.py` — Updated with Phase 1 self-registration (lines 500-548)
- `/home/maceo/Dev/CodeWriter9.0/schema/resource_registry.generic.json` — Updated: fs-x7p6 activated
- `/home/maceo/Dev/CodeWriter9.0/schema/registry_dag.json` — Re-extracted DAG (55 nodes, 65 edges)
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — Architectural plan
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/handoffs/general/2026-03-09_10-40-51_phase1-first-templates.md` — Previous handoff

## Action Items & Next Steps

### IMMEDIATE: Phase 2 — Composition Engine (Single Piece Flow)

From BOOTSTRAP.md lines ~378-430:

**Step 1: Build `compose(spec_a, spec_b)`.** Given two TLA+ modules that share variables (detected from registry edges), produce the composed module:
```
Init_composed = Init_A ∧ Init_B
Next_composed = Next_A ∨ Next_B (with UNCHANGED)
Inv_composed  = Inv_A ∧ Inv_B ∧ Inv_cross
```
See `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md:650-667` for the exact composition mechanics.

**Step 2: Variable unification.** Use registry edges to detect shared state between modules. Cross-layer edges from the DAG (e.g., frontend api_contracts → backend endpoints) indicate where modules share variables.

**Step 3: Cross-invariant generation.** From registry dependency edges, generate invariants that span composed modules.

**Step 4: Apply state machine template to the composition engine itself** (the bootstrap act for Phase 2). The composition engine has a lifecycle: parse → detect shared vars → compose → verify. Model this as a state machine using `templates/pluscal/state_machine.tla`.

**Step 5: Register Phase 2 components in the DAG** (continuing self-description pattern).

### Cross-layer composition targets (from schema edges)
- Frontend `api_contracts` ↔ backend `endpoints`
- Middleware `interceptors` ↔ shared `interceptor_interfaces`
- Backend `services` ↔ `data_access_objects`
- Shared `verifiers` ↔ backend `data_structures`

### THEN: Phase 3 — LLM Orchestration
After Phase 2, integrate Claude Agent SDK for the one-shot code generation loop.

## Other Notes

### No commits yet
All work is uncommitted on master branch (single initial commit `4a0c14a`). The user may want to commit before starting Phase 2.

### Tech stack
- Rust core DAG engine: `crates/registry-core/`
- Python orchestration: `python/registry/`
- PlusCal templates: `templates/pluscal/`
- TLA+ toolbox: `tools/tla2tools.jar` (Java 21 required, available on system)

### The 4 PlusCal templates
1. **CRUD** (tpl-0001) — verified via registry instantiation
2. **State machine** (tpl-0002) — template ready, no instance yet (Phase 2 bootstrap act)
3. **Queue/pipeline** (tpl-0003) — template ready, no instance yet
4. **Auth/session** (tpl-0004) — template ready, no instance yet

### Key architectural principle
LLM writes PlusCal ONLY. The system handles compilation to TLA+ and composition. Counterexamples translate back up to PlusCal-level language. Templates have clear fill-in markers that separate what the LLM fills (domain parameters) from what the system handles (syntax, composition).
