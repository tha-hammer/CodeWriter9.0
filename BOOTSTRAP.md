# BOOTSTRAP: Building the Machine That Builds the Machine

## The Flywheel Principle

Every component we build becomes a tool for building the next component.
The system earns the right to participate in its own construction by
proving itself on real work — its own.

```
  Build registry by hand
       |
       v
  Register the registry's own behaviors IN the registry
       |
       v
  Build TLA+ templates by hand
       |
       v
  Use registry to detect dependencies between templates
       |
       v
  Build composition engine
       |
       v
  Use composition engine to verify the composition engine's own spec
       |
       v
  Build the one-shot loop
       |
       v
  Use the one-shot loop to generate the bridge translators
       |
       v
  Use the bridge to derive tests for everything built so far
       |
       v
  Use the full pipeline on the next feature request
       |
       v
  ┌──────────────────────────────────────┐
  │          THE FLYWHEEL TURNS          │
  │                                      │
  │  Every improvement to the system     │
  │  improves the system's ability       │
  │  to improve itself.                  │
  └──────────────────────────────────────┘
```

---

## What We Already Have

We are NOT starting from zero. The existing schema system provides the
foundation for the registry's resource layer.

### Existing Assets

```
  schema/
  ├── resource_registry.generic.json   41 resources, 6 schema prefixes
  │                                    UUID format: <schema:2>-<suffix:4>
  │                                    Stable, greppable identifiers
  │
  ├── backend_schema.json              processors, endpoints, handlers,
  │                                    DAOs, services, filters, data
  │                                    structures, verifiers, errors,
  │                                    process chains
  │
  ├── frontend_schema.json             modules, components, access controls,
  │                                    data loaders, utility modules,
  │                                    API contracts, verifiers
  │
  ├── middleware_schema.json           interceptors, execution patterns,
  │                                    process chains
  │
  └── shared_objects_schema.json       utilities, common structures, data
                                       types, verifiers, transformers,
                                       errors, constants, settings, logging,
                                       security, caching, i18n, testing,
                                       interceptor interfaces
```

### What the Schemas Already Give Us

**1. Resource identity (solved).** 41 resources with stable UUIDs across 6
schema prefixes (`db-*`, `api-*`, `mq-*`, `ui-*`, `cfg-*`, `fs-*`). The
UUID format and naming conventions are established.

**2. Resource shapes (solved).** Each schema file defines the internal
structure of its resource types — fields, types, validation rules,
function signatures. These are the NODE CONTENTS of the DAG.

**3. Dependency information (exists but unstructured).** The schemas already
encode dependencies, but they're embedded in the resource definitions,
not extracted into a graph:

```
  backend_schema.json:
    processors.imports.internal    --> what other backend modules it uses
    processors.imports.shared      --> what shared modules it uses
    processors.dependencies        --> named dependencies
    services.functions.calls       --> "DataAccessObjectName.functionName"
    endpoints.handler              --> "RequestHandlerName"
    endpoints.filters              --> ["FilterName"]
    request_handlers.dependencies  --> ["ServiceName"]
    request_handlers.functions.operation --> "ProcessorName.operationName"

  frontend_schema.json:
    modules.imports.backend        --> backend endpoints, structures, errors
    modules.imports.shared         --> shared types, errors, constants
    data_loaders.api_reference     --> "backend/endpoints/EndpointName"
    api_contracts.reference        --> "backend/endpoints/EndpointName"

  middleware_schema.json:
    interceptors.imports.shared    --> shared interfaces, types, errors
    interceptors.base_interface    --> "shared/interceptor_interfaces/..."
    process_chains.interceptors    --> ["InterceptorName"]

  shared_objects_schema.json:
    verifiers.rules.applies_to     --> ["StructureName", "fieldName"]
    transformers.input_type/output_type --> type references
```

**4. Traceability hooks (solved).** Every item has `function_id` and
`acceptance_criteria_id`. These are ready-made slots for linking to
GWT behaviors and TLA+ specs.

**5. Conditional resources (solved).** Security, caching, i18n,
documentation, TLA+ artifact store, plan artifact store — activated
only when needed. The `fs-x7p6` (tla_artifact_store) and `fs-y3q2`
(plan_artifact_store) are directly relevant to bootstrap.

### What's Missing: The Graph Layer

The existing registry is FLAT — resources exist, but relationships
between them are implicit in the schema definitions. The bootstrap
adds the DAG:

```
  EXISTING (flat)                 NEEDED (graph)
  ┌──────────────────────┐       ┌──────────────────────────────────┐
  │                      │       │                                  │
  │  db-b7r2: processor  │       │  db-b7r2: processor              │
  │  db-d3w8: dao        │       │    |                             │
  │  db-h2s4: service    │       │    | calls ──> db-d3w8: dao      │
  │  api-m5g7: endpoint  │       │    | uses  ──> cfg-f7s8: type    │
  │  cfg-f7s8: type      │       │                                  │
  │                      │       │  db-h2s4: service                │
  │  (no edges)          │       │    | calls ──> db-d3w8: dao      │
  │  (no closure)        │       │    | depends ──> db-b7r2: proc   │
  │  (no components)     │       │                                  │
  │                      │       │  api-m5g7: endpoint              │
  └──────────────────────┘       │    | handler ──> api-n8k2        │
                                 │    | filter ──> api-p3e6         │
                                 │                                  │
                                 │  + closure table                 │
                                 │  + connected components          │
                                 │  + composed_specs cache          │
                                 └──────────────────────────────────┘
```

---

## Bootstrap Phases

### Phase 0: Extract the Graph

**What we have:** Flat registry + 4 schema files with embedded deps.
**How we build:** Extract dependency edges from schemas into the registry.
**What we produce:** The registry DAG — the flat registry gains edges,
transitive closure, and connected components.

```
  Tools available: text editor, LLM (manual), brain,
                   EXISTING SCHEMAS (41 resources, stable UUIDs)
  Tools after:     + REGISTRY DAG (edges, closure, components)
```

Deliverables:
- Edge extraction: parse `imports`, `dependencies`, `calls`,
  `api_reference`, `handler`, `filters`, `base_interface`,
  `applies_to` from the 4 schema files → registry edges
- Edge types matching the schema relationships:
  `calls`, `imports`, `handles`, `filters`, `validates`,
  `references`, `implements_interface`
- Transitive closure computation
- Connected component detection
- `registry.query_relevant(resource_id)` — the context query

```
  Extraction map (schema field → edge type):

  processors.imports.internal       →  imports
  processors.imports.shared         →  imports
  processors.dependencies           →  depends_on
  services.functions.calls           →  calls
  endpoints.handler                  →  handles
  endpoints.filters                  →  filters
  request_handlers.dependencies      →  depends_on
  request_handlers.functions.operation → calls
  modules.imports.backend            →  imports
  data_loaders.api_reference         →  references
  api_contracts.reference            →  references
  interceptors.base_interface        →  implements_interface
  process_chains.interceptors        →  chains
  verifiers.rules.applies_to         →  validates
  transformers.input_type            →  transforms_from
  transformers.output_type           →  transforms_to
```

Validation: unit tests, written by hand. Pure graph logic.

**The bootstrap act:** Register the registry's own components in itself.
The DAG's first real entries describe the DAG.

```
  New registry nodes (the registry describing itself):

  req-0001: "System needs a dependency-tracking DAG over existing
             resource registry"

  gwt-0001: "Given a new resource, when registered, then transitive
             closure updates to include all reachable resources"
  gwt-0002: "Given two resources sharing a dependency, when components
             are computed, then both appear in the same component"
  gwt-0003: "Given a resource ID, when context is queried, then all
             transitive dependencies and their contracts are returned"
  gwt-0004: "Given an edge that would create a cycle, when added,
             then the edge is rejected"

  res-0001: "nodes" (Map<UUID, ResourceEntry>)
             — maps to the existing resources section
  res-0002: "edges" (List<{from, to, type}>)
             — the new graph layer
  res-0003: "closure" (Map<UUID, Set<UUID>>)
             — transitive closure table
  res-0004: "components" (Map<ComponentID, Set<UUID>>)
             — connected components
```

This is the registry's first test: can it describe itself using its own
schema? If it can't, it can't describe anything.

#### Phase 0 Implementation (COMPLETE — 2026-03-09)

Dual Rust + Python implementation. All deliverables met.

```
  crates/registry-core/src/
  ├── lib.rs           public API
  ├── types.rs         NodeId, Node, Edge, EdgeType, NodeKind, QueryResult
  ├── dag.rs           RegistryDag (add_node, add_edge, closure, components,
  │                    query_relevant, cycle rejection, JSON serialization)
  └── error.rs         RegistryError (NodeNotFound, CycleDetected)

  python/registry/
  ├── types.py         Python dataclasses matching Rust types
  ├── dag.py           Pure Python RegistryDag (same interface)
  └── extractor.py     SchemaExtractor — parses all 4 schema files,
                       extracts edges per extraction map, self-describes

  schema/registry_dag.json   Extracted DAG (serialized output)
```

Results:
- **50 nodes** (41 resources + 9 self-description)
- **48 edges** across 15 edge types
- **15 connected components** — largest has 26 members spanning all 4 layers
- Self-description component: 9 nodes (req-0001, gwt-0001..0004, res-0001..0004)
- **45 tests** (10 Rust + 35 Python) — all passing
- Cycle rejection, closure correctness, component merging, context query,
  JSON roundtrip, full extraction from live schema files all verified

---

### Phase 1: First Templates

The CRUD template isn't just for verifying the registry — it's the first
reusable template in a library that will generate code for external projects.
The registry bootstrap is just the first customer.

**What we have:** Registry DAG with its own behaviors registered. Existing
schema structures that define what each resource type looks like.
**How we build:** By hand, but the registry + schemas tell us what to build.
**What we produce:** PlusCal templates + PlusCal-to-TLA+ compilation step.

```
  Tools available: text editor, LLM (manual), brain,
                   REGISTRY DAG, EXISTING SCHEMAS
  Tools after:     + PLUSCAL TEMPLATES, + PCAL COMPILER STEP
```

Deliverables:
- 4 PlusCal templates: CRUD, state machine, queue/pipeline, auth/session
- Fill-in marker format (what the LLM sees, what it fills in)
- Compilation step: PlusCal source -> TLA+ module (using TLA+ toolbox)
- Activate `fs-x7p6` (tla_artifact_store) for generated specs

The existing schemas directly inform template design:
- **CRUD template** ← modeled after `data_structures` + `data_access_objects`
  (fields, relations, queries — these are the CRUD operations)
- **State machine template** ← modeled 
after `execution_patterns`
  (conditions, rules, bypass_conditions — these are state guards)
- **Queue/pipeline template** ← modeled after `process_chains`
  (ordered steps, conditions — these are queue operations)
- **Auth/session template** ← modeled after `security` + `access_controls`
  (strategies, roles, permissions, conditions — these are session operations)

**The bootstrap act:** The registry is a CRUD data structure. Apply the
CRUD template to the registry's own GWT behaviors.

```
  CRUD Template applied to the registry:

  state = set of nodes, set of edges
  actions:
    AddNode(id, kind, content)
    AddEdge(from, to, type)
    RemoveEdge(from, to)   -- only before verification; monotonic after
    QueryContext(resource_id) -> relevant_set
  invariants:
    AcyclicGraph    == no cycles in edges
    ClosureCorrect  == closure matches actual transitive reachability
    ComponentsValid == components are a valid partition of connected nodes
    UUIDFormat      == all IDs match <schema:2-3>-<suffix:4> pattern
```

Compile this PlusCal to TLA+. Run TLC against it.
If TLC passes: the registry's design is formally verified.
If TLC fails: we have a bug in our registry design. Fix it now,
not after building 5 more layers on top.

**This is the flywheel's first real turn.** A tool we just built
(CRUD template) verified a tool we built earlier (registry), using
resource shapes already defined in the existing schemas.

#### Phase 1 Implementation (COMPLETE — 2026-03-09)

All deliverables met. Templates are reusable for external projects.

```
  templates/pluscal/
  ├── crud.tla              CRUD template — set-based state, CRUD actions
  ├── state_machine.tla     State machine template — enum states, guards, bypass
  ├── queue_pipeline.tla    Queue/pipeline template — FIFO, no-item-loss
  ├── auth_session.tla      Auth/session template — login/logout/expire/RBAC
  └── instances/
      ├── registry_crud.tla First instantiation — registry DAG verification
      └── registry_crud.cfg TLC model checking configuration

  tools/
  └── tla2tools.jar         TLA+ toolbox (PlusCal compiler + TLC checker)
```

Results:
- **4 PlusCal templates** with `{{FILL:...}}` markers for LLM parameterization
- **TLC verified** registry CRUD: 7 invariants, 12,245 states, 0 violations
- **`fs-x7p6`** (tla_artifact_store) activated in resource registry
- **6 new DAG nodes** registered: tpl-0001..0005, fs-x7p6
- **17 new edges**: templates model schemas, registry spec verifies GWTs
- **DAG totals**: 55 nodes, 65 edges, 11 connected components
- **45 tests** still passing (10 Rust + 35 Python)

Key design decision: Two-phase action model (mutate → update derived).
TLA+ evaluates primed variables simultaneously, so derived state
(closure, components) must be recomputed in a separate step. Invariants
on derived state are gated with `dirty = TRUE \/` to allow the
intermediate state between phases.

Template design: Each template maps to schema patterns:
- CRUD ← `data_structures` + `data_access_objects`
- State machine ← `execution_patterns` (conditions, rules, bypass)
- Queue/pipeline ← `process_chains` (steps[], order[], conditions[])
- Auth/session ← `security` + `access_controls` (roles, permissions, guards)

---

### Phase 2: Composition Engine

**What we have:** Registry DAG (verified by its own template). PlusCal
templates. Existing schemas defining cross-layer dependencies.
**How we build:** By hand, but now with formal specs guiding us.
**What we produce:** The TLA+ composition engine.

```
  Tools available: text editor, LLM (manual), brain, REGISTRY DAG,
                   EXISTING SCHEMAS, PLUSCAL TEMPLATES, PCAL COMPILER
  Tools after:     + COMPOSITION ENGINE
```

Deliverables:
- `compose(spec_a, spec_b)` — given two TLA+ modules sharing variables,
  produce the composed module
- Variable unification (detect shared state from registry edges)
- Cross-invariant generation (from registry dependency edges)
- Composed spec cache (indexed by connected component)

The existing schemas show us where composition is needed:
- Frontend `api_contracts` reference backend `endpoints` → cross-layer
- Middleware `interceptors` reference shared `interceptor_interfaces` → cross-layer
- Backend `services` call `data_access_objects` → intra-layer
- Shared `verifiers` apply to backend `data_structures` → cross-layer

These are the connected components the composition engine will operate on.

**The bootstrap act:** Apply the state machine template to the composition
engine's own lifecycle:

```
  State Machine Template applied to composition:

  states = {empty, partial, composed, verified, failed}
  transitions:
    empty -> partial:    first spec registered
    partial -> composed: compose() called
    composed -> verified: TLC passes
    composed -> failed:   TLC rejects
    failed -> partial:    spec revised (conform-or-die on the NEW spec)
    partial -> composed:  new spec added, recompose
  invariants:
    MonotonicGrowth    == verified specs are never removed
    AssociativityHolds == compose order doesn't change result
```

Run TLC. Verify the composition engine's own state machine before
trusting it to compose other people's specs.

#### Phase 2 Completion

All deliverables met:

**Composition Engine State Machine** (bootstrap act):
- Instantiated `state_machine.tla` template for the composition lifecycle
- States: `{empty, partial, composed, verified, failed}`
- 7 invariants: ValidState, MonotonicGrowth, NoEmptyCompose,
  AssociativityHolds, BoundedExecution, ValidSpecs, DerivedConsistency
- TLC verified: 1,553 distinct states, 0 violations

**`compose(spec_a, spec_b)`** — `python/registry/composer.py`:
- TLA+ module parser (EXTENDS, CONSTANTS, VARIABLES, Init, Next, invariants)
- Variable unification: name intersection + DAG edge inference
- Composed module generation:
  - `Init_composed = Init_A ∧ Init_B`
  - `Next_composed = Next_A ∨ Next_B (with UNCHANGED)`
  - `Inv_composed = Inv_A ∧ Inv_B ∧ Inv_cross`
- Cross-invariant generation from registry dependency edges
- Composed spec cache indexed by connected component
- High-level API: `compose_from_files()`, `compose_component()`

**Self-registration:**
- 3 new nodes: `tpl-0006` (composition engine spec), `comp-0001` (composer),
  `comp-0002` (spec cache)
- 9 new edges (IMPLEMENTS, REFERENCES, COMPOSES, DEPENDS_ON)
- DAG totals: 58 nodes, 74 edges, 11 components
- All 61 tests passing (26 composer + 35 existing)

**Phase 3 — The One-Shot Loop** completed:

**`one_shot_loop.py`** — `python/registry/one_shot_loop.py`:
- Registry context query: given a GWT behavior ID, returns all transitive deps (schemas, templates, existing specs) assembled into a prompt context bundle
- PlusCal fragment extraction: parses LLM response for algorithm blocks (fenced code blocks with tla/pluscal markers, bare --algorithm blocks)
- Compile → compose → TLC pipeline: writes PlusCal to temp file, compiles with `pcal.trans`, optionally composes with composition engine, runs TLC, captures results
- Counterexample translator: parses TLC counterexample traces, extracts states/variables/violated invariant, translates to PlusCal-level concepts (labels, variable names) rather than TLA+ internals
- Pass/retry/fail router: deterministic routing based on TLC result + failure count — pass → done, first failure → retry with counterexample, second consecutive failure → requirements inconsistency (not retried)
- `OneShotLoop` orchestrator class: manages lifecycle states (idle → querying_context → prompting_llm → extracting_fragment → compiling → composing → verifying → translating_error → routing → done | failed)

**TLA+ verification:**
- `one_shot_loop.tla` — state machine spec (instantiates `state_machine.tla` template), TLC verified: 3,105 states, 1,790 distinct, 6 invariants (ValidState, MutualExclusionOnCompose, TwoFailureLimit, DeterministicRouting, BoundedExecution, DerivedConsistency)
- `loop_compose_composed.tla` — composed spec (loop + composition engine as two concurrent processes), TLC verified: 34,081 states, 10,624 distinct, 10 invariants including cross-invariant MutualExclusionOnComposedSpecs
- Key finding: TLC discovered that the engine's compose can complete before the loop enters composing state — the `compose_busy` guard on EngineCompose prevents the engine from starting a NEW compose while the loop is composing

**Self-registration:**
- 3 new GWT behaviors: `gwt-0005` (transitive deps), `gwt-0006` (counterexample translation), `gwt-0007` (failure routing)
- 1 requirement: `req-0002` (one-shot loop)
- 1 spec node: `tpl-0007` (one-shot loop state machine)
- 3 resource nodes: `loop-0001` (orchestrator), `loop-0002` (counterexample translator), `loop-0003` (router)
- 16 new edges (IMPLEMENTS, VERIFIES, REFERENCES, DEPENDS_ON, DECOMPOSES)
- DAG totals: 66 nodes, 90 edges, 11 components
- All 96 tests passing (35 one-shot loop + 26 composer + 10 DAG + 25 extractor)

**Phase 4 — The Bridge (Single Piece Flow)** completed:

**`bridge.py`** — `python/registry/bridge.py`:
- TLA+ spec parser: extracts module name, variables (with type inference), actions (with guard/assignment extraction), invariants (from define blocks), constants
- Translator 1 — State vars → `data_structures` shape: maps TLA+ variables to backend_schema fields with types, defaults, validation rules
- Translator 2 — Actions → `processors.operations` shape: maps TLA+ actions to operations with parameters, returns, error_types
- Translator 3 — Invariants → `verifiers` + `testing.assertions` shapes: maps invariants to verifier conditions and test assertions
- Translator 4 — TLC traces → test scenarios: maps counterexample traces to concrete test scenarios with setup, steps, expected outcomes
- `run_bridge()` pipeline: parse spec → translate all 4 → produce `BridgeResult` with schema-conforming artifacts

**TLA+ verification:**
- `bridge_translator.tla` — state machine spec (instantiates `state_machine.tla` template), TLC verified: 702 states, 407 distinct, 6 invariants (ValidState, BoundedExecution, OutputConformsToSchema, TranslationOrder, NoPartialOutput, InputPreserved)
- `bridge_loop_composed.tla` — composed spec (bridge + one-shot loop), composition engine identified 6 shared variables

**The bootstrap act — first real use of the one-shot loop:**
- `OneShotLoop.query('gwt-0008')` → context bundle with 30 transitive deps (schemas, templates, loop, composer)
- `OneShotLoop.format_prompt()` → rich context prompt for LLM
- `OneShotLoop.process_response(bridge_pluscal, ...)` → PlusCal extraction → compilation → TLC verification → PASS
- Bridge then runs on the verified spec to produce schema-conforming artifacts

**Self-registration:**
- 4 new GWT behaviors: `gwt-0008` (state var translation), `gwt-0009` (action translation), `gwt-0010` (invariant translation), `gwt-0011` (trace translation)
- 1 requirement: `req-0003` (bridge translators)
- 1 spec node: `tpl-0008` (bridge translator state machine)
- 4 resource nodes: `bridge-0001` through `bridge-0004` (4 translators)
- `fs-y3q2` (plan_artifact_store) activated — bridge outputs reference it
- 32 new edges (IMPLEMENTS, VERIFIES, REFERENCES, DEPENDS_ON, DECOMPOSES)
- DAG totals: 76 nodes, 122 edges, 9 components
- All 144 tests passing (43 bridge + 5 loop-bridge integration + 35 one-shot loop + 26 composer + 10 DAG + 25 extractor)

---

### Phase 3: The One-Shot Loop

**What we have:** Registry, templates, composition engine — all verified.
**How we build:** This is where the flywheel accelerates.
**What we produce:** The core algorithm.

```
  Tools available: REGISTRY DAG, EXISTING SCHEMAS, TEMPLATES,
                   PCAL COMPILER, COMPOSITION ENGINE
  Tools after:     + ONE-SHOT LOOP
```

Deliverables:
- Registry context query -> LLM prompt assembly
- LLM response -> PlusCal fragment extraction
- Fragment -> compile -> compose -> TLC pipeline
- Counterexample -> natural language translator
- Pass/retry/fail routing

The existing schema `acceptance_criteria_id` fields become the link
between GWT behaviors and the specs that verify them. The `function_id`
fields link specs to implementation.

**The bootstrap act:** Use the existing tools to specify the one-shot
loop itself.

1. Register the loop's behaviors in the registry:
   - gwt: "Given a new GWT, when context is queried from registry,
           then all transitive deps are included"
   - gwt: "Given a TLC counterexample, when translated to natural
           language, then it references PlusCal-level concepts only"
   - gwt: "Given two consecutive failures, when routing, then
           requirements inconsistency is reported (not retried)"

2. Detect dependencies: the loop references the registry (for context),
   the composition engine (for compose), TLC (for verify). The registry
   shows these as a connected component.

3. Compose the specs. The loop's spec joins with the composition engine's
   spec on the `composed_specs` variable. TLC checks the interleaving:
   can the loop call compose while compose is mid-operation? (It shouldn't.
   TLC will find this if the spec allows it.)

4. TLC passes or we fix the design.

**This is the second turn of the flywheel.** The loop is specified and
verified using the registry + templates + composition engine — the very
tools it will orchestrate in production.

---

### Phase 4: The Bridge

**What we have:** The full verification pipeline (registry through one-shot loop).
**How we build:** This is the first phase where we CAN use the one-shot loop.
**What we produce:** Mechanical spec-to-code translators.

```
  Tools available: REGISTRY DAG, EXISTING SCHEMAS, TEMPLATES,
                   COMPOSITION, ONE-SHOT LOOP
  Tools after:     + BRIDGE (spec -> data model, signatures, tests)
```

Deliverables:
- TLA+ state variables -> data model / schema generator
- TLA+ actions -> function signature generator
- TLA+ invariants -> test assertion generator
- TLC traces -> scenario test generator
- Activate `fs-y3q2` (plan_artifact_store) for generated plans

The existing schemas define the TARGET SHAPES the bridge must produce.
The bridge translates TLA+ specs into artifacts that conform to these
schemas:
- TLA+ state vars → `data_structures` shape (fields, types, validation)
- TLA+ actions → `processors.operations` shape (params, returns, errors)
- TLA+ invariants → `verifiers` shape (conditions, message, applies_to)
- TLA+ invariants → `testing.assertions` shape (condition, message)

**The bootstrap act:** Use the one-shot loop for real. Claude Agent SDK Only.

1. Describe the bridge's requirements in plain language.
2. Run them through the one-shot loop.
3. The loop uses the registry for context, generates PlusCal specs,
   compiles, composes, verifies with TLC.
4. The verified specs define exactly what the bridge translators must do.
5. Write the translators to satisfy the specs.

This is the first time the system builds a component of itself without
manual TLA+ writing. The flywheel is self-sustaining.

**Then immediately:** run the bridge on ALL existing specs (registry,
templates, composition engine, one-shot loop). This retroactively
generates TDD test suites for everything built by hand in Phases 0-3.

```
  Phase 0-3 code (hand-built, manually tested)
       |
       | bridge translates existing specs
       v
  Generated test suites for Phases 0-3
       |
       | run tests
       v
  Either: all pass (hand-built code was correct)
  Or:     failures found (bugs in foundation — fix now)
```

This is the flywheel's most important turn. It retroactively validates
the foundation.

---

### Phase 5: Self-Hosting

**What we have:** The complete pipeline, verified, with generated tests.
**How we build:** Using the pipeline itself.
**What we produce:** Any new feature.

```
  Tools available: THE FULL PIPELINE
  Tools after:     + WHATEVER WE WANT
```

From this point forward, every new feature goes through:

```
  Plain language requirement
       |
       v
  Ingest (registry population)
       |
       v
  Compose (TLA+ verification)
       |
       v
  Review (user approves invariants)
       |
       v
  Bridge (mechanical test generation)
       |
       v
  Implement (code to pass tests)
```

The system is self-hosting. It uses itself to build itself.

**First self-hosted feature:** UI integration (Phase 6 from the plan).
The pipeline specifies, verifies, and generates tests for its own UI.

---

## The Flywheel Diagram

```
  Phase 0         Phase 1          Phase 2          Phase 3
  ┌──────┐       ┌──────┐        ┌──────┐        ┌──────┐
  │EXTRACT│       │BUILD │        │BUILD │        │BUILD │
  │graph  │       │templ-│        │compo-│        │one-  │
  │from   │       │ates  │        │sition│        │shot  │
  │schemas│       │      │        │engine│        │loop  │
  └──┬───┘       └──┬───┘        └──┬───┘        └──┬───┘
     |              |               |               |
     v              v               v               v
  ┌──────┐       ┌──────┐        ┌──────┐        ┌──────┐
  │VERIFY│       │VERIFY│        │VERIFY│        │VERIFY│
  │DAG   │       │regis-│        │compo-│        │loop  │
  │via   │       │try   │        │sition│        │using │
  │self- │       │via   │        │via   │        │regis-│
  │descr-│       │CRUD  │        │state │        │try + │
  │iption│       │templ-│        │mach. │        │comp. │
  │      │       │ate   │        │templ.│        │engine│
  └──┬───┘       └──┬───┘        └──┬───┘        └──┬───┘
     |              |               |               |
     |   ┌──────────┘               |    ┌──────────┘
     |   |    ┌─────────────────────┘    |
     v   v    v                          v
  ┌──────────────────┐            ┌──────────────────┐
  │ Phase 4: BRIDGE  │            │ Phase 5: SELF-   │
  │                  │            │ HOSTING           │
  │ First component  │            │                  │
  │ built BY the     │───────────>│ Pipeline builds  │
  │ pipeline         │            │ itself from here │
  │                  │            │                  │
  │ ALSO: retro-     │            │ Every new feature│
  │ actively tests   │            │ goes through the │
  │ Phases 0-3       │            │ pipeline it      │
  │                  │            │ helped build     │
  └──────────────────┘            └──────────────────┘
```

---

## Schema-to-Registry Edge Map

The dependency information already encoded in the schemas drives the
graph extraction in Phase 0. This is the complete extraction map:

```
  BACKEND SCHEMA
  ──────────────
  processors.imports.internal[].path     ──imports──>     backend/*
  processors.imports.shared[].path       ──imports──>     shared/*
  processors.imports.external[].package  ──imports──>     (external, tracked)
  processors.dependencies[]              ──depends_on──>  (by name)
  services.functions.calls[]             ──calls──>       dao.function
  services.dependencies[]                ──depends_on──>  (by name)
  endpoints.handler                      ──handles──>     request_handler
  endpoints.filters[]                    ──filters──>     filter
  request_handlers.functions.operation   ──calls──>       processor.operation
  request_handlers.dependencies[]        ──depends_on──>  service
  process_chains.steps[]                 ──chains──>      processor.operation
  data_structures.relations[].target     ──relates_to──>  data_structure
  verifiers.applies_to[]                 ──validates──>   structure/operation

  FRONTEND SCHEMA
  ───────────────
  modules.imports.backend[].path         ──imports──>     backend/*
  modules.imports.shared[].path          ──imports──>     shared/*
  modules.components[]                   ──contains──>    component
  modules.navigation.data_loaders[]      ──loads──>       data_loader
  modules.navigation.access_controls[]   ──guards──>      access_control
  data_loaders.api_reference             ──references──>  backend/endpoint
  api_contracts.reference                ──references──>  backend/endpoint
  verifiers.rules.applies_to[]           ──validates──>   component/utility

  MIDDLEWARE SCHEMA
  ─────────────────
  interceptors.base_interface            ──implements──>  shared/interface
  interceptors.imports.shared[].path     ──imports──>     shared/*
  process_chains.interceptors[]          ──chains──>      interceptor

  SHARED SCHEMA
  ─────────────
  verifiers.rules.applies_to[]           ──validates──>   structure/field
  transformers.input_type                ──transforms──>  data_type
  transformers.output_type               ──transforms──>  data_type
```

This map is exhaustive. Every cross-reference in the 4 schema files
becomes an edge in the registry DAG. No dependency is implicit.

---

## Ground Rules

1. **Each phase validates the previous phase.** Phase 1 templates verify
   Phase 0 registry. Phase 2 composition verifies Phase 1 templates.
   Phase 4 bridge retroactively generates tests for Phases 0-3. No phase
   is "done" until the next phase has verified it.

2. **No phase skipping.** The flywheel only works if each layer is solid
   before the next layer builds on it. The registry must work before
   templates use it. Templates must work before composition uses them.

3. **Self-description is the first test.** Every component's first act
   is to describe itself in the registry. If a component can't describe
   its own behavior as GWT entries with TLA+ specs, it's not well-defined
   enough to build.

4. **Hand-built code is temporary.** Phases 0-3 are built by hand. Phase 4
   retroactively generates test suites for all of them. Phase 5 can
   regenerate any of them through the pipeline. Hand-built code is scaffolding,
   not architecture.

5. **The conform-or-die rule applies to bootstrap too.** Each phase's specs
   are settled law for all subsequent phases. If Phase 3 (one-shot loop)
   can't conform to Phase 2's (composition engine) verified spec, Phase 3's
   design is wrong, not Phase 2's.

6. **Use existing schemas, don't reinvent.** The 4 schema files define the
   shapes of things. The registry DAG adds relationships between things.
   Don't duplicate what the schemas already specify — reference it.

7. **Activate conditional resources as needed.** `fs-x7p6` (TLA+ artifacts)
   activates in Phase 1. `fs-y3q2` (plan artifacts) activates in Phase 4.
   `cfg-t5h9` (security) activates when a project needs auth. Don't activate
   what you don't need yet.

---

## What "Done" Looks Like

The bootstrap is complete when:

- [x] Edge extraction from 4 schema files produces a valid DAG (Phase 0)
- [x] The registry describes itself as nodes in its own graph (Phase 0)
- [x] TLC verifies the registry's own spec via CRUD template (Phase 1)
- [x] `fs-x7p6` activated, TLA+ artifacts stored there (Phase 1)
- [x] TLC verifies the composition engine via state machine template (Phase 2)
- [x] Cross-layer dependencies (frontend→backend, middleware→shared) are
      composed and verified (Phase 2)
- [x] The one-shot loop is verified against composed specs of registry +
      composition engine (Phase 3)
- [x] The bridge generates test suites for Phases 0-3 from their specs (Phase 4)
- [x] `fs-y3q2` activated, plan artifacts stored there (Phase 4)
- [x] All generated tests pass against hand-built code (Phase 4 validation)
- [x] First feature built entirely through the pipeline (Phase 5)
      Impact analysis query: GWT behaviors → LLM-generated PlusCal spec →
      TLC verified (624,466 states, 337,346 distinct, 0 violations) →
      bridge artifacts → generated tests → query_impact() implementation

At that point, the system is self-hosting. The flywheel is turning under
its own power.
