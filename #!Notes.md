#!Notes

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
