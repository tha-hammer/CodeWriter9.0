#!Notes



# Help me think ahead. There are 2 common use cases: 1. greenfield project, external to   
this repo and 2. brownfield project, external to this project.                            
We will need a way to "point" CW9 at the external repo, maintain state, persist sessions, 
 and write code from this repo - or - we package a globally available binary to invoke in 
 the target repo.  The CW9 code will also need to be able to locate files in the external 
 repo.                                                                                    
                                                                                          
● Good timing to think about this. Let me break it down.                                  
                                                                                          
  The Core Problem                                                                        
   
  Right now CW9 is solipsistic — every path, every schema, every DAG reference assumes    
  it's operating on itself. To work on external repos, you need to solve five things:

  1. Project root — where is the target code?
  2. CW9 state — where do schemas, DAG, specs, bridge artifacts live?
  3. Session continuity — handoffs, pipeline history, retry context
  4. Code targeting — generated tests and implementations land in the right place
  5. Codebase ingestion — how does the DAG get populated for a foreign project?

  Two Deployment Models

  Model A: "Point At" (CW9 stays home)

  CW9 repo is the tool. External project is a target path. State lives in CW9 under
  something like projects/<name>/.

  CodeWriter9.0/
    projects/
      my-saas-app/
        schema/          ← schemas for the external project
        registry_dag.json
        templates/pluscal/instances/
        bridge_artifacts/
        sessions/
      another-project/
        ...
    python/registry/     ← CW9 engine code

  Pros: Single source of truth, easy to compare projects, no installation step.
  Cons: Path management nightmare. Every tool (extractor.py, one_shot_loop.py, bridge.py)
  takes project_root today but assumes schemas are in that root. You'd need to split
  "where is CW9 engine code" from "where is the target project" from "where is CW9 state
  for this project." That's three roots, not one.

  Model B: CLI binary, state in target repo

  CW9 packages as a CLI tool. Target repo gets a .cw9/ directory (like .git/). The tool
  runs in the target repo's context.

  my-saas-app/              ← target repo
    .cw9/
      schema/               ← project schemas
      dag.json              ← registry DAG
      specs/                ← TLA+ instances
      bridge/               ← bridge artifacts
      sessions/             ← handoffs, loop history
      config.toml           ← project-level settings
    src/                    ← their code
    tests/                  ← where generated tests land

  Pros: Clean separation. State travels with the project. Multiple developers can use CW9
  on the same repo. Standard CLI ergonomics (cw9 init, cw9 extract, cw9 verify, cw9
  bridge).
  Cons: Packaging and distribution. The Rust crate helps here — crates/registry-core/
  could become the binary, with Python as an embedded runtime or subprocess.

  My Recommendation: Model B, but staged

  Model B is the right end state, but you don't need to package a binary to start. The
  staging:

  Stage 1 — Decouple paths (do this now, in-repo). Every component that uses PROJECT_ROOT
  or hardcoded paths needs a config object:

  @dataclass
  class ProjectContext:
      target_root: Path      # where the external code lives
      state_root: Path       # where .cw9/ state lives (usually target_root/.cw9)
      schema_dir: Path       # state_root/schema
      spec_dir: Path         # state_root/specs
      artifact_dir: Path     # state_root/bridge
      test_output_dir: Path  # target_root/tests/generated (or configurable)

  This is the foundational refactor. Currently SchemaExtractor, OneShotLoop,
  run_*_loop.py, and bridge.py all assume paths relative to a single root.

  Stage 2 — cw9 init for greenfield. Creates .cw9/ in target repo, generates starter
  schemas from a template. The 4 schema files (backend, frontend, middleware, shared) get
  created with empty structures. User fills them in, or an ingestion step helps.

  Stage 3 — cw9 ingest for brownfield. This is the hard one. You need to scan an existing
  codebase and populate schemas. Options:
  - LLM-assisted: point at a directory, LLM reads code, proposes schema entries
  - Convention-based: scan for known patterns (Express routes → endpoints, SQLAlchemy
  models → data structures)
  - Manual: user writes schemas by hand, CW9 validates

  Stage 4 — Package as CLI. Rust binary wraps the Python engine. cargo install cw9 or a
  standalone binary.

  The Greenfield vs Brownfield Split

  Greenfield is easier — the pipeline works as-is. User writes requirements in plain
  language, pipeline generates specs, verifies, generates tests, user implements. The only
   missing piece is ProjectContext so files land in the right place.

  Brownfield is fundamentally different. You're not building forward from requirements —
  you're building backward from existing code. The pipeline's Phase 0 (extraction)
  currently reads schemas that describe the code. For a brownfield project, someone has to
   create those schemas from the existing codebase. That's either a manual effort or a
  separate ingestion pipeline.

  What to Build Next

  The ProjectContext refactor is the prerequisite for both use cases and both deployment
  models. It's also a good pipeline candidate — you could express it as GWT behaviors
  ("given a project context pointing to an external directory, when extract is called,
  then schemas are read from the state root, not the CW9 root").

  Want to scope that as the next pipeline feature, or think through the
  packaging/distribution question more first?

# Here is the scope:
The coupling surface is narrower than the LLM suggested — it's essentially one    
  anchor (PROJECT_ROOT) with known relative paths below it. Here's how I'd scope          
  packaging:                                                                              
                                                                                          
  Packaging Scope: What You Actually Need                                                 
                                                                                          
  The path analysis shows three distinct path concerns, not five:                         
                                                                                          
  1. Engine root — where CW9's own code lives (templates, tla2tools.jar, bridge logic)    
  2. Target root — where the external project's source code lives
  3. State root — where the DAG, schemas, specs, and artifacts live for that project

  Today all three are the same directory. Decoupling them is the prerequisite for
  everything.

  Staged Plan

  Stage 0: ProjectContext dataclass (the real work)

  @dataclass
  class ProjectContext:
      engine_root: Path   # CW9 install location (templates, tools, python/registry)
      target_root: Path   # external project's root
      state_root: Path    # target_root/.cw9 by default

      # Derived (all under state_root)
      schema_dir: Path
      spec_dir: Path
      artifact_dir: Path
      session_dir: Path

      # Under target_root
      test_output_dir: Path

  What changes:
  - SchemaExtractor.__init__ — already takes schema_dir, just pass ctx.schema_dir
  - OneShotLoop — takes project_root, split into ctx.engine_root (for template reads) and
  ctx.state_root (for spec writes)
  - _find_tla2tools — looks in ctx.engine_root / "tools" instead of PROJECT_ROOT / "tools"
  - Loop scripts — the big surface area (all those PROJECT_ROOT / ... joins). Each gets a
  ProjectContext instead of computing PROJECT_ROOT
  - Node path= strings in _self_describe — these are metadata for CW9's own DAG, leave
  them as-is. External projects get their own DAG with their own paths.

  What doesn't change:
  - dag.py, bridge.py, composer.py, types.py — no hardcoded paths, already clean
  - Rust crate — no paths at all
  - pyproject.toml — stays as-is, pytest config is per-project

  This is ~6 files touched, mostly the 5 loop scripts + one_shot_loop.py. The registry
  core is already decoupled.

  Stage 1: cw9 init

  A script (not yet a binary) that creates .cw9/ in a target directory:

  cw9 init /path/to/my-project

  Creates:
  my-project/.cw9/
    config.toml      # engine_root = "/path/to/CodeWriter9.0"
    schema/           # empty starter schemas
    dag.json          # empty DAG
    specs/            # TLA+ instances will go here
    bridge/           # bridge artifacts will go here
    sessions/         # handoffs and loop logs

  Greenfield starts here. User writes schemas (or Stage 2 helps them).

  Stage 2: cw9 ingest (brownfield)

  This is the hard problem and can be deferred. For now, brownfield = "user writes schemas
   by hand, CW9 validates them." The pipeline already handles everything after schemas
  exist.

  Stage 3: CLI binary

  Wrap with a thin entry point. Could be a Python CLI (click or argparse) first, Rust
  binary later. The Rust crate already has the DAG engine — but the pipeline (LLM calls,
  TLC invocation, bridge) is all Python today, so a Python CLI is the pragmatic first
  step.

  What I'd Build Next

  Stage 0 only. The ProjectContext refactor. It's a pipeline candidate — you can express
  it as GWT behaviors:

  - gwt-0024: Given a ProjectContext pointing to an external directory, when
  SchemaExtractor runs, schemas are read from state_root/schema
  - gwt-0025: Given a ProjectContext, when the loop runs, specs are written to
  state_root/specs, not engine_root
  - gwt-0026: Given a ProjectContext, when bridge generates tests, they land in
  target_root/tests/generated

  That's req-0008, 3 GWT behaviors, one pipeline run. The implementation is a refactor of
  existing code, not new functionality — but it's verified refactoring.

  Stage 1 (cw9 init) follows naturally once ProjectContext exists. Stages 2-3 are separate
   decisions.

















What's Correct
                                                                                          
  The CSP framing is right. The nested loop problem IS arc-consistency propagation. CW7's
  current architecture — verify path A, verify path B, discover A conflicts with B,
  re-verify A, discover that breaks C — has no convergence guarantee. The
  buildDependencyContext() function in CW7's path-reviewer.ts tries to surface sibling
  path info, but it's textual and informational only. The LLM reviewer can see "path-B
  also uses db-5kft" but can't enforce consistency. This is exactly stochastic local
  search on a CSP.

  The O(n²) → O(n) claim is correct IF the monotonic growth property holds. More on this
  below.

  The TLA+ composition formula is mechanically correct. Init_composed = Init_A ∧ Init_B,
  Next_composed as interleaved disjunction with UNCHANGED private vars — this is standard
  TLA+ composition. The per-path-schema-binding-model.md already demonstrates this
  pattern: it models PATHS={p1,p2,p3} with MutualExclusionInv and RegistryMonotonic as
  cross-path invariants. 4,840 states, 3,337 distinct, all 10 properties passed. That's a
  working proof-of-concept.

  The one-shot-with-replay pattern matches the existing cage architecture. Your
  formalization doc already describes the 3-layer cage (locked signature → drift
  correction → compile+test). This output extends the same pattern to TLA+ authorship:
  one-shot, deterministic check, counterexample-as-editing-context on failure. The dhe/9v8
   epic tracks exactly this shift.

  The GWT → TLA+ mapping is clean. Given → Init, When → Action, Then → Invariant. This is
  sound and matches how per-path-schema-binding-model.md was built.

  What Needs Scrutiny

  1. "Monotonic growth — nodes are never deleted, only superseded. Once a behavior's spec
  passes, it's never invalidated by later behaviors."

  This is the central claim and it's not unconditionally true. The
  per-path-schema-binding-model.md proves this for a specific case: RegistryMonotonic
  (INV-9) guarantees |registry'| >= |registry|. But monotonic growth of the registry is
  not the same as monotonic validity of composed specs.

  Consider: behavior A passes against the composed spec. Behavior B is added. B introduces
   a new resource constraint. The composed spec now includes Invariant_B. It's possible
  that the interleaving of A's actions with B's actions violates Invariant_B — even though
   A passed before B existed.

  The document says "compose(compose(A,B), C) = compose(A, compose(B,C))" — associativity.
   This is true for the syntactic composition (Init/Next/Invariant conjunction). But TLC
  satisfaction is NOT associative in the same way. A passing compose(A,B) and B passing
  compose(B,C) does NOT guarantee A passes compose(A,B,C). The new invariant from C might
  constrain A's state space.

  The fix is straightforward but must be stated explicitly: when a new behavior joins a
  connected component, re-verify the entire component's composed spec, not just the new
  behavior against the existing composition. The document's "Handling Late-Discovered
  Dependencies" section says "re-verify only the affected subgraph" — this is correct, but
   the affected subgraph is the entire connected component, not just the new edges.

  2. "Gates 1 and 2 collapse into Ingest."

  This is aspirational, not yet real. CW7's Gate 1 (requirement decomposition into GWT)
  and Gate 2 (techstack selection) produce structured JSON that downstream gates consume.
  CW8.1's equivalent is the session loop (parse_prompt → GWT → schema mutations) plus
  silmari.toml config. Collapsing these into a single LLM call means that single call must
   produce:
  - Parsed requirements
  - GWT decomposition per requirement
  - Techstack decisions
  - Resource identification with UUIDs
  - Registry edges (decomposes, references, constrains)

  That's a lot of structured output for one shot. The current system uses 4 parallel
  extractors (extract_entities, extract_operations, extract_relationships,
  extract_constraints) because splitting improves accuracy. A single ingest call would
  need to be rigorously tested against the same quality bar.

  3. "Bridge — Mechanical translation, no LLM."

  This is the constrained-domain promise: if the spec is complete (all 6 axes determined),
   the translation is mechanical. Your formalization doc's completeness formula covers
  this. But today, CW8.1's fill_function_bodies() still uses the LLM for function body
  generation — because function bodies are the one place where the spec isn't fully
  determined (it specifies contracts, not implementations).

  The Bridge stage as described would need to produce: data models (mechanical from
  types), function signatures (mechanical from schema), and test assertions (mechanical
  from invariants + contracts). This is achievable. But the Implement stage still needs
  the LLM for bodies. The document correctly shows "1 per module" LLM calls at Implement.
  So the claim isn't "no LLM after Bridge" — it's "no LLM at Bridge." That's accurate.

  4. "Don't use full TLA+. Use PlusCal state machines."

  Pragmatically sound for the 80% case. But there's a tension: PlusCal compiles to TLA+
  and the composition formula (Init_A ∧ Init_B, interleaved Next) operates at the TLA+
  level, not PlusCal. You can't compose two PlusCal algorithms directly — you compose
  their TLA+ translations. This means the LLM needs to understand both layers, or the
  templates need to handle composition at the TLA+ level while the LLM fills in
  PlusCal-level state machines. The per-path-schema-binding-model.md example was authored
  directly in TLA+ concepts, not PlusCal. The templates approach could bridge this, but
  it's a design decision that needs to be made explicit.

  5. The verification spectrum timing estimates are optimistic.

  "Bounded TLC (depth 5) ~1s" — this depends entirely on state space. The
  per-path-schema-binding-model.md with 3 paths, 3 resources, MAX_PROPOSED=2 produced
  4,840 states. That's trivial. But 55+ paths share db-5kft. Even with connected-component
   decomposition, a component with 10 paths and 5 shared resources at depth 5 could blow
  up. The funnel architecture from your formalization doc (static classification →
  predicate composition → composed TLC) is the right mitigation, but the timing claims
  need to come from measurement, not estimation.

  What's Missing From This Output

  The connected-component extraction algorithm. The document says "Registry dependency
  graph → connected components → each gets a composed TLA+ spec." But the resource
  registry today doesn't track which paths share which resources in a way that produces
  connected components. The history.jsonl tracks resources per path, and paths reference
  resources by UUID — so the data exists to build the bipartite graph (paths ↔ resources)
  and extract connected components. But no code does this yet.

  The template library. "CRUD, state machine, queue/pipeline, auth/session patterns that
  the LLM fills in rather than writing from scratch" — this is referenced but not defined.
   The /extract_tlaplus_model command gives example invariant patterns (ResourceSafety,
  MonotonicProgress, BalanceNonNegative, RetryBound) but not full composable templates.
  This is a concrete deliverable that would need to be built.

  The transitive closure table. "O(1) dependency queries" requires materialized transitive
   closure. CW8.1's schema_store.rs builds a dependency graph (858 lines) and runs Kahn's
  algorithm for cycle detection, but doesn't precompute transitive closure. SQLite's
  recursive CTEs could do this (WITH RECURSIVE), but it's not implemented.

  Bottom Line

  The architecture described here is sound and represents a genuine simplification over
  CW7's 9-gate pipeline. The key risk is the monotonic validity assumption — you need
  full-component re-verification when new behaviors join, not just incremental checking.
  The one-shot-with-replay pattern is the right LLM interaction model. The philosophical
  point at the end — "the TLA+ spec IS the understanding" — is the correct framing and
  aligns with your constrained-domain thesis.

  The most valuable next step would be building the connected-component extractor from the
   existing resource registry data, because that's the structural prerequisite for
  everything else in this pipeline.
