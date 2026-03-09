---
date: 2026-03-09T10:15:29-04:00
researcher: claude-opus
git_commit: HEAD
branch: master
repository: CodeWriter9.0
topic: "Registry-Driven Pipeline Bootstrap"
tags: [implementation, strategy, resource-registry, tla-plus, formal-methods, bootstrap, flywheel]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Registry-Driven Pipeline Bootstrap

## Task(s)

### Completed
1. **Deep architectural analysis** — Used 3 Opus subagents to ultrathink the problem: resource registry design, LLM↔TLA+↔verifier feedback loop, and pipeline simplification.
2. **Implementation plan** — Created `registry-driven-pipeline-plan.md` with full diagrams covering the 5-stage pipeline (Ingest→Compose→Review→Bridge→Implement), registry DAG structure, TLA+ composition mechanics, one-shot-with-replay algorithm, verification spectrum, and spec-to-code bridge.
3. **Conform-or-die rule** — Added section formalizing that registered behaviors are settled law; new behaviors must conform or are rejected. No backtracking, no revising existing specs for newcomers.
4. **PlusCal/TLA+ layer separation** — Added section clarifying LLM writes PlusCal only; composition engine operates on compiled TLA+ output; counterexamples translate back up to PlusCal-level language for retry prompts.
5. **Bootstrap plan (BOOTSTRAP.md)** — Created the flywheel document grounded in existing schema assets. Phase 0 is "Extract the Graph" from the 4 existing schema files, not building from scratch.

### Next Step (Single Piece Flow)
**Phase 0: Extract the Graph.** Build the registry DAG by extracting dependency edges from the existing schema files. This is the foundation everything else depends on.

## Critical References
- `BOOTSTRAP.md` — The flywheel plan with phases 0-5, grounded in existing schemas
- `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — Full architectural plan with diagrams
- `thoughts/searchable/shared/docs/the-insight.md` — Core insight document (the original vision)

## Recent changes
- Created: `BOOTSTRAP.md` (project root)
- Created: `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md`
- No code changes — this session was architecture and planning only

## Learnings

### The existing schema system is substantial
The project already has 41 resources with stable UUIDs across 6 schema prefixes. The 4 schema files (`backend_schema.json`, `frontend_schema.json`, `middleware_schema.json`, `shared_objects_schema.json`) already encode dependency information in their `imports`, `dependencies`, `calls`, `handler`, `api_reference`, `base_interface`, `applies_to` fields. Phase 0 is extraction, not invention.

### Key architectural decisions made
1. **Monotonic growth** — Registry nodes are never deleted, only superseded. Earlier behaviors are settled law.
2. **Conform-or-die** — New behaviors must be compatible with all existing specs or are rejected. Two TLC failures = requirements inconsistency (surfaced to user, not retried).
3. **LLM writes PlusCal, system composes TLA+** — Clean layer separation. LLM never touches composition. Counterexamples translate back to PlusCal-level language.
4. **Templates over raw generation** — 4 PlusCal templates (CRUD, state machine, queue/pipeline, auth/session) mapped to existing schema shapes. LLM fills parameters, not syntax.
5. **Bridge is mechanical, not LLM** — Spec-to-code translation is deterministic template-based transformation. Same spec always produces same tests.

### Schema-to-edge extraction map
Complete map documented in `BOOTSTRAP.md` under "Schema-to-Registry Edge Map". Every cross-reference in the 4 schema files is mapped to an edge type (`imports`, `calls`, `handles`, `filters`, `validates`, `references`, `implements_interface`, `chains`, `transforms_from/to`, etc.).

### Conditional resources relevant to bootstrap
- `fs-x7p6` (tla_artifact_store) — activate in Phase 1 for TLA+ specs
- `fs-y3q2` (plan_artifact_store) — activate in Phase 4 for generated plans
- `cfg-t5h9` (security) — activate per-project when auth is needed

### Traceability hooks already exist
Every schema item has `function_id` and `acceptance_criteria_id` fields. These are ready-made slots for linking to GWT behaviors and TLA+ specs.

## Artifacts
- `/home/maceo/Dev/CodeWriter9.0/BOOTSTRAP.md` — Flywheel bootstrap plan (full document)
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md` — Architectural plan with diagrams
- `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/the-insight.md` — Core insight (existed before, referenced throughout)
- `/home/maceo/Dev/CodeWriter9.0/schema/resource_registry.generic.json` — Existing flat registry (41 resources, 6 prefixes)
- `/home/maceo/Dev/CodeWriter9.0/schema/backend_schema.json` — Backend schema (processors, endpoints, handlers, DAOs, services, etc.)
- `/home/maceo/Dev/CodeWriter9.0/schema/frontend_schema.json` — Frontend schema (modules, components, data loaders, API contracts, etc.)
- `/home/maceo/Dev/CodeWriter9.0/schema/middleware_schema.json` — Middleware schema (interceptors, execution patterns, process chains)
- `/home/maceo/Dev/CodeWriter9.0/schema/shared_objects_schema.json` — Shared schema (utilities, types, transformers, verifiers, etc.)

## Action Items & Next Steps

### IMMEDIATE: Phase 0 — Extract the Graph (Single Piece Flow)

The next agent should execute Phase 0 from `BOOTSTRAP.md`. Here is the single piece flow:

**Step 1: Design the extended registry format.**
Take `schema/resource_registry.generic.json` and extend it with:
- `edges` array: `[{from: UUID, to: UUID, type: string}]`
- `closure` map: `{UUID: [UUID, ...]}`
- `components` map: `{component_id: [UUID, ...]}`

**Step 2: Write the edge extractor.**
Parse each of the 4 schema files and extract edges using the map in `BOOTSTRAP.md` under "Schema-to-Registry Edge Map". Each `imports.internal[].path`, `services.functions.calls[]`, `endpoints.handler`, `data_loaders.api_reference`, etc. becomes an edge.

**Step 3: Compute transitive closure and connected components.**
Standard graph algorithms on the extracted edges.

**Step 4: Write the context query function.**
`query_relevant(resource_id)` → returns all transitive dependencies, their schemas, and their contracts.

**Step 5: Self-describe.**
Register the registry's own components (gwt-0001 through gwt-0004, res-0001 through res-0004) as defined in `BOOTSTRAP.md` Phase 0.

**Step 6: Unit test.**
Verify: closure updates on edge add, cycle rejection, component detection, context query returns complete transitive deps.

### THEN: Phase 1 — First Templates
After Phase 0 is solid, build the CRUD PlusCal template and apply it to the registry itself. See `BOOTSTRAP.md` Phase 1.

## Other Notes

### Related documents in thoughts/
- `thoughts/searchable/global/README.md` — Global documentation
- `thoughts/searchable/shared/docs/the-insight.md` — The original vision document that started this work

### Silmari Oracle integration
- Commands reference `silmari verify-path` for TLA+ verification
- `.claude/commands/extract_tlaplus_model.md` — Existing command for extracting TLA+ from code (288 lines, well-defined pipeline)
- `.claude/commands/plan_path.md` — Existing command for path planning with resource registry references
- `.silmari/` directory exists for checkpoint/history storage

### The flywheel principle
Each phase both PRODUCES a tool and VALIDATES the previous phase's tool. Phase 1 templates verify Phase 0 registry. Phase 4 bridge retroactively generates tests for Phases 0-3. This is not optional — it's how the system earns trust in its own foundation.
