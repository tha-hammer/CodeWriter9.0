The Core Insight                                                                        
                                                                                          
  Your instinct is correct: the resource_registry as a dependency DAG eliminates the
  nested loop problem entirely. Here's why, formalized:

  The nested loop exists because of partial information. When you check GWT-A against
  GWT-B in isolation, you don't account for GWT-C's constraints. Fixing A-for-B breaks
  A-for-C. This is arc-consistency propagation in a constraint satisfaction problem — and
  stochastic local search on CSPs has no convergence guarantee.

  The registry pre-computes the constraints. When the LLM generates behavior B_i, it sees
  the entire transitive dependency context via the registry. Its output must compose with
  everything already registered. If it passes TLC verification against the composed spec,
  it is by construction compatible with all existing behaviors. No backtracking needed.

  This transforms O(n²) pairwise consistency checking into O(n) incremental composition.

  ---
  The Simplified Pipeline (5 stages, not 9)

  ┌───────────┬──────────────────────────────────────────────────────────┬────────────┐
  │   Stage   │                       What happens                       │ LLM calls  │
  ├───────────┼──────────────────────────────────────────────────────────┼────────────┤
  │           │ One LLM call produces requirements + behaviors +         │            │
  │ Ingest    │ techstack + resource identification. All become registry │ 1          │
  │           │  nodes with edges.                                       │            │
  ├───────────┼──────────────────────────────────────────────────────────┼────────────┤
  │           │ Registry dependency graph → connected components → each  │ 1 per      │
  │ Compose   │ gets a composed TLA+ spec from templates. Independent    │ component  │
  │           │ components verified in parallel.                         │            │
  ├───────────┼──────────────────────────────────────────────────────────┼────────────┤
  │           │ User reviews invariants in natural language ("your       │            │
  │ Review    │ system guarantees these properties"), not raw GWT. One   │ 0          │
  │           │ checkpoint, not multiple gates.                          │            │
  ├───────────┼──────────────────────────────────────────────────────────┼────────────┤
  │ Bridge    │ Verified specs → data models, function signatures, test  │ 0          │
  │           │ assertions. Mechanical translation, no LLM.              │            │
  ├───────────┼──────────────────────────────────────────────────────────┼────────────┤
  │ Implement │ Code written to pass tests. Independent modules in       │ 1 per      │
  │           │ parallel.                                                │ module     │
  └───────────┴──────────────────────────────────────────────────────────┴────────────┘

  Gates 1 and 2 collapse into Ingest. The review checkpoint moves downstream to where it
  matters: "are these the properties you want guaranteed?"

  ---
  Registry Data Structure

  Registry = DAG where:
    Nodes: {Requirement, Behavior, Resource, Constraint, Spec, Test, Module}
    Edges: {decomposes, references, constrains, models, verifies, implements}

    + transitive closure table (O(1) dependency queries)
    + composed_specs cache (indexed by connected component)

  Key property: monotonic growth. Nodes are never deleted, only superseded. This means
  once a behavior's spec passes, it's never invalidated by later behaviors. The registry
  is an append-only knowledge base.

  ---
  TLA+ Composition (the mechanical detail)

  When behaviors A and B share a resource, their specs compose via:

  - Init_composed = Init_A ∧ Init_B (contradictions = inconsistent requirements, caught
  immediately)
  - Next_composed = (Next_A ∧ UNCHANGED vars_B_private) ∨ (Next_B ∧ UNCHANGED
  vars_A_private)
  - Invariant_composed = Invariant_A ∧ Invariant_B ∧ Invariant_cross

  This composition is associative — so incremental addition works: compose(compose(A,B),
  C) = compose(A, compose(B,C)). You never recompose from scratch.

  ---
  The One-Shot-With-Replay Pattern

  for each behavior B_i:
      context = registry.query_relevant(B_i)     # interfaces + invariants + dependency
  subgraph
      fragment = LLM(B_i, context)               # one shot
      result = TLC(compose(existing, fragment))   # deterministic check

      if fail:
          fragment' = LLM(B_i, context, result.counterexample)  # one retry with concrete
  trace
          if still fail: REPORT REQUIREMENTS INCONSISTENCY       # it's the spec, not the
  process

      registry.add(fragment)

  Why this converges: The counterexample converts a search problem into an editing
  problem. The LLM sees exactly which state transition violated which invariant. It
  doesn't need to search — it needs to patch. Search may loop; targeted editing converges.

  ---
  Practical TLA+ (80/20)

  Don't use full TLA+. Use:

  1. PlusCal state machines — enumerate states + transitions, let TLC find deadlocks
  2. Safety invariants — "balance never negative", "no access without auth"
  3. Templates — CRUD, state machine, queue/pipeline, auth/session patterns that the LLM
  fills in rather than writing from scratch

  The GWT mapping is clean:
  - Given → Init (initial state predicate)
  - When → Named action in Next (state transition)
  - Then → Invariant checked across ALL interleavings (this is where formal methods exceed
   unit testing)

  ---
  The Verification Spectrum (for interactive speed)

  ┌────────────────────────┬──────────┬───────────────────────────┐
  │         Layer          │   Time   │      What it catches      │
  ├────────────────────────┼──────────┼───────────────────────────┤
  │ Syntax/parse           │ ~10ms    │ Structural errors         │
  ├────────────────────────┼──────────┼───────────────────────────┤
  │ Type/interface         │ ~100ms   │ Contract mismatches       │
  ├────────────────────────┼──────────┼───────────────────────────┤
  │ Bounded TLC (depth 5)  │ ~1s      │ Most bugs                 │
  ├────────────────────────┼──────────┼───────────────────────────┤
  │ Bounded TLC (depth 20) │ ~30s     │ Subtle interleavings      │
  ├────────────────────────┼──────────┼───────────────────────────┤
  │ Full TLC               │ minutes+ │ Everything (run async/CI) │
  └────────────────────────┴──────────┴───────────────────────────┘

  Interactive use runs layers 0-2. Deeper checks run asynchronously.

  ---
  Handling Late-Discovered Dependencies

  1. Register new Resource node + edges to existing behaviors
  2. Registry detects merged connected component
  3. Re-verify only the affected subgraph (not everything)
  4. Existing passing tests still pass — you're only checking new interactions

  ---
  The Philosophical Point

  Stop treating formal methods as a separate phase and start treating them as the
  representation layer.

  The TLA+ spec isn't something you build after understanding requirements. It is the
  understanding, expressed precisely enough to verify. The registry doesn't contain
  requirements that get translated to specs — it contains specs annotated with their
  natural-language origins.
