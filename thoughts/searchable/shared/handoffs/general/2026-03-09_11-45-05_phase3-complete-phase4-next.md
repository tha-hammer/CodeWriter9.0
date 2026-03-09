---
date: 2026-03-09T11:45:05-04:00
researcher: claude-opus
git_commit: pending
branch: master
repository: CodeWriter9.0
topic: "Phase 3 Complete → Phase 4 The Bridge"
tags: [implementation, tla-plus, pluscal, one-shot-loop, phase-4, single-piece-flow]
status: complete
last_updated: 2026-03-09
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: Phase 3 Complete → Phase 4 The Bridge

## Task(s)

### Completed
1. **Phase 0: Extract the Graph** — Rust + Python DAG engine, all tests passing.
2. **Phase 1: First Templates** — 4 PlusCal templates, registry CRUD verified by TLC, self-registered.
3. **Phase 2: Composition Engine** — `compose(spec_a, spec_b)`, TLC verified, self-registered.
4. **Phase 3: The One-Shot Loop** — All deliverables met:
   - One-shot loop state machine (`one_shot_loop.tla`) instantiated from `state_machine.tla` template, TLC verified (3,105 states, 6 invariants, 0 violations)
   - Composed spec (`loop_compose_composed.tla`) with two concurrent processes (loop + engine), TLC verified (34,081 states, 10 invariants, 0 violations)
   - `one_shot_loop.py` implemented: registry context query, PlusCal extraction, compile/compose/TLC pipeline, counterexample translator, pass/retry/fail router, OneShotLoop orchestrator
   - 3 GWT behaviors registered: context transitive deps, counterexample translation, failure routing
   - Phase 3 components self-registered in DAG (8 new nodes, 16 new edges)
   - DAG totals: 66 nodes, 90 edges, 11 connected components
   - All 96 tests passing (35 one-shot loop + 26 composer + 10 DAG + 25 extractor)

### Next Step (Single Piece Flow)
**Phase 4: The Bridge.** Build mechanical spec-to-code translators. This is the first phase where we CAN use the one-shot loop. See `BOOTSTRAP.md` lines ~510+.

## Critical References
- `BOOTSTRAP.md:510+` — Phase 4 section defines Bridge deliverables
- `python/registry/one_shot_loop.py` — The core algorithm (all 5 pipeline components)
- `templates/pluscal/instances/one_shot_loop.tla` — State machine spec (TLC verified)
- `templates/pluscal/instances/loop_compose_composed.tla` — Composed spec with composition engine (TLC verified)

## Recent changes
- Created: `python/registry/one_shot_loop.py` — One-shot loop pipeline (context query, PlusCal extraction, compile/compose/TLC, counterexample translator, router, orchestrator)
- Created: `python/tests/test_one_shot_loop.py` — 35 tests (context query, extraction, counterexample, routing, self-registration)
- Created: `templates/pluscal/instances/one_shot_loop.tla` — State machine spec for loop lifecycle (11 states, 6 invariants)
- Created: `templates/pluscal/instances/one_shot_loop.cfg` — TLC config (MaxSteps=12, MaxRetries=1)
- Created: `templates/pluscal/instances/loop_compose_composed.tla` — Two-process composed spec (loop + engine)
- Created: `templates/pluscal/instances/loop_compose_composed.cfg` — TLC config (MaxSteps=8, MaxRetries=1)
- Updated: `python/registry/extractor.py:595-660` — Phase 3 self-registration (gwt-0005..0007, req-0002, tpl-0007, loop-0001..0003 + 16 edges)
- Updated: `schema/registry_dag.json` — Re-extracted with Phase 3 components (66 nodes, 90 edges)
- Updated: `BOOTSTRAP.md:458-485` — Phase 3 completion details

## Learnings

### Concurrent composition requires careful invariant formulation
The composed spec (loop + engine) found genuine interleaving issues via TLC. The engine can complete its compose step before the loop enters composing — this means `compose_busy` and `engine_state="composed"` can coexist, which is not a safety violation but looks like one in a naive invariant. The real safety property is: the engine cannot START a new compose while the loop holds the compose lock (`compose_busy=TRUE`), enforced by a guard condition. The invariant must distinguish between "engine completed compose earlier" vs "engine is actively composing now."

### PlusCal label atomicity per process, not globally
In a multi-process PlusCal spec, each label is atomic within its process, but two labels in different processes can interleave. This means dirty flags from two-phase actions in separate processes can both be TRUE simultaneously during the interleaving. Cross-process invariants must account for this by either: (1) checking only when both processes are at "ready" state (dirty=FALSE), or (2) expressing the invariant in terms of structural properties (like monotonicity) rather than temporal exclusion.

### PlusCal fragment extraction needs multiple patterns
LLM responses format PlusCal in at least 4 ways: (1) fenced code blocks with `tla`/`pluscal` language marker, (2) generic fenced blocks containing algorithm markers, (3) bare algorithm blocks, (4) algorithm blocks with PlusCal comment wrappers `(* ... *)`. The extractor tries patterns in order of specificity (most structured first).

### Two-failure limit is a clean routing boundary
The pass/retry/fail router is deterministic and stateless (depends only on TLC result + consecutive failure count). This matches the state machine spec exactly: `consecutive_failures > MaxRetries => state in {"failed", "routing"}`. MaxRetries=1 means: first failure retries, second failure reports requirements inconsistency.

## Architecture Decisions

### Loop does NOT call LLM directly
The `OneShotLoop` class prepares context and processes responses, but the caller is responsible for the actual LLM interaction. This separation means the loop can be tested without an LLM and composed with different LLM backends.

### Counterexample translator operates on PlusCal concepts only
The translator maps TLC counterexample traces to PlusCal-level variable names and process labels, stripping TLA+ internal names (ProcSet, generated pc functions). This aligns with BOOTSTRAP.md's "LLM writes PlusCal ONLY" principle — error feedback should also be in PlusCal terms.

### compose_busy as a semaphore
The `compose_busy` boolean acts as a simple semaphore for the compose operation. In the single-process one_shot_loop.tla spec, it prevents re-entering compose. In the two-process composed spec, it prevents the engine from starting a new compose while the loop is composing. The guard is on EngineCompose: `compose_busy = FALSE`.
