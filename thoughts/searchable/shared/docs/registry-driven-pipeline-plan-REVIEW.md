# Plan Review Report: registry-driven-pipeline-plan

**Reviewed:** 2026-03-09
**Plan:** `thoughts/searchable/shared/docs/registry-driven-pipeline-plan.md`
**Reviewer:** claude-opus-4.6

---

## Review Summary

| Category     | Status | Issues Found |
|-------------|--------|--------------|
| Contracts    | ⚠️     | 3 issues     |
| Interfaces   | ⚠️     | 4 issues     |
| Promises     | ⚠️     | 2 issues     |
| Data Models  | ❌     | 3 issues     |
| APIs         | ⚠️     | 2 issues     |

---

## Contract Review

### Well-Defined:
- ✅ **Monotonic growth contract** — "Nodes are never deleted, only superseded. Once a spec passes verification, later behaviors cannot invalidate it." This is the foundation of the entire architecture and is clearly stated.
- ✅ **One-shot-with-replay contract** — At most 2 LLM calls per behavior. Two failures = requirements inconsistency, surfaced to user. Clean termination guarantee.
- ✅ **Composition associativity** — `Init_A ∧ Init_B`, `Next_A ∨ Next_B`, `Inv_A ∧ Inv_B ∧ Inv_cross`. Mathematically correct and clearly demonstrated.
- ✅ **TLC as deterministic oracle** — The LLM proposes, TLC disposes. No ambiguity about who has authority.

### Missing or Unclear:

- ⚠️ **C1: The "superseded" mechanism is undefined.** The plan says nodes are "never deleted, only superseded" but never defines what supersession means. Is there a `superseded_by` edge? A version field that makes old nodes invisible to queries? A tombstone flag? The JSON example shows `"version": 1` on nodes but no mechanism to mark a node as superseded or to distinguish active from superseded nodes in queries.

  **Impact:** Without this, the registry will accumulate stale nodes that pollute context queries. The LLM will see outdated behaviors alongside current ones.

  **Recommendation:** Define supersession explicitly. Options: (a) `superseded_by: Option<NodeId>` field on every node — queries filter `where superseded_by is null`; (b) separate `active_nodes` index maintained on mutation; (c) version-aware queries that always take the highest-version node for a given semantic identity.

- ⚠️ **C2: Cross-invariant (`Invariant_cross`) authorship is unspecified.** The composition formula includes `Invariant_cross` — the cross-behavior invariants like `TransferTargetExists`. But the plan doesn't say WHO writes these. The LLM? Automatically derived from resource overlap? The user?

  In the `per-path-schema-binding-model.md` specimen from CW8.1, cross-invariants were hand-authored by the LLM during the `/extract_tlaplus_model` command. But in the one-shot-with-replay loop, the LLM generates a TLA+ fragment for a single behavior — where does the cross-invariant get injected?

  **Impact:** This is the most valuable part of composition (catching "transfer to nonexistent account"). If cross-invariants are never generated, composition degrades to just checking that Init predicates don't contradict — which is trivial and misses the interesting bugs.

  **Recommendation:** Make cross-invariant generation an explicit step. When a new behavior B_i joins a connected component, the LLM receives existing invariants + the new behavior's resource overlap, and is asked to produce candidate cross-invariants as part of its fragment. The prompt structure already has a "[FROM REGISTRY] Tier 1: Invariants of direct dependencies" slot — cross-invariant generation should be an explicit output requirement in that prompt, not left implicit.

- ⚠️ **C3: Error contract for Ingest is vague.** The plan says Ingest is "1 LLM call" that produces requirements + behaviors + techstack + resources. What happens when:
  - The LLM produces malformed JSON?
  - The LLM identifies 0 resources (everything looks independent)?
  - The LLM produces duplicate resource names with different schemas?
  - The user's prompt is ambiguous and the LLM produces conflicting GWT behaviors?

  **Recommendation:** Define Ingest's error modes explicitly. At minimum: parse failure → retry with structured error; zero resources → warn user ("no shared state detected — all behaviors are independent"); duplicate resources → merge or reject with explanation.

---

## Interface Review

### Well-Defined:
- ✅ **Registry node/edge CRUD** — "Node CRUD (add, query by kind, query by ID), Edge CRUD (add, query by type, query by endpoint)" — clear operations.
- ✅ **Context query interface** — "given behavior B, return all relevant context" — the tiered prompt structure (Tier 0-3) defines what "relevant" means precisely.
- ✅ **Verification spectrum layers** — Parse → Type → Bounded TLC → Deep TLC → Full TLC. Each layer's input/output is clear.

### Missing or Unclear:

- ⚠️ **I1: Connected component detection interface is undefined.** The plan says "Registry dependency graph → connected components" but doesn't define the algorithm or interface. No connected-component detection exists in CW7 or CW8.1 (confirmed by codebase search — the closest is `detect_shared_artifacts_graph` in CW7's `function_loop.py:290-326`, which finds high-degree nodes, not components).

  **Recommendation:** Define: `fn connected_components(registry: &Registry) -> Vec<Component>` where `Component = { members: Vec<NodeId>, shared_resources: Vec<NodeId> }`. Use union-find on the bipartite graph (behaviors ↔ resources). Two behaviors are in the same component if they share any resource transitively.

- ⚠️ **I2: Transitive closure computation interface is undefined.** The plan says "O(1) dependency queries" via a pre-computed closure table. CW8.1 has `DependencyGraph` with `DependencyEdge` structs (`auxiliary_types.rs:154-165`) and Kahn's algorithm for cycle detection, but no transitive closure computation exists in either codebase.

  **Recommendation:** Define: `fn update_closure(registry: &mut Registry, new_edge: Edge)` that incrementally updates the closure table using the formula: `closure[a] = closure[a] ∪ {b} ∪ closure[b]` for each ancestor `a` of the edge's source. For the JSON representation, the `closure` field in the example is correct — it needs an implementation.

- ⚠️ **I3: Composed specs cache invalidation is undefined.** "When a new behavior joins a component, the cache updates incrementally." But what happens when two previously independent components merge (late-discovered dependency)? The cache entry for each old component must be deleted and a new combined entry created. The plan's "Handling Late-Discovered Dependencies" section shows the merge but doesn't address cache invalidation.

  **Recommendation:** Define: `fn merge_components(registry: &mut Registry, comp_a: ComponentId, comp_b: ComponentId) -> ComponentId` that creates a new component, moves all members, deletes old cache entries, and triggers re-verification of the merged component.

- ❌ **I4: The Bridge translation interface has no implementable specification.** The plan says "TLA+ state vars → data model, TLA+ actions → function signatures, TLA+ invariants → test assertions" with a clean mapping table. But the actual `TlaModel` struct in CW8.1 (`src/tlaplus/types.rs:98-106`) contains:
  - Variables: `pc` (program counter), `error_state` (boolean), `step_N_out` (opaque string tokens `"step_N_result"`)
  - Actions: guard strings + assignment strings in TLA+ syntax
  - Properties: raw TLA+ formula strings

  **There is no type information in `TlaModel`.** The variable `step_3_out = "step_3_result"` tells you nothing about the data model. The action `Transfer(from, to, amt)` tells you parameter names but not types. The invariant `balances[a] >= 0` implies `balances` maps to non-negative integers but this inference requires parsing TLA+ expressions into typed artifacts — which is a non-trivial compiler pass, not a template substitution.

  **This is the plan's most critical gap.** The Bridge stage assumes TLA+ specs contain enough information for mechanical code derivation. Currently, they don't. The plan's own example shows typed TLA+ (`balances \in [Accounts -> Nat]`) that carries type information — but the existing `TlaModel` IR discards this, reducing everything to opaque string tokens.

  **Impact:** Without a typed TLA+ representation, Bridge cannot be mechanical. It becomes either: (a) another LLM call (defeating the purpose), or (b) a manual step.

  **Recommendation:** The plan must specify a **new, richer TLA+ IR** that preserves type information. The Spec nodes in the registry should carry:
  ```
  {
    "variables": [
      {"name": "balances", "tla_type": "[Accounts -> Nat]", "code_type": "Map<AccountId, u64>"}
    ],
    "actions": [
      {"name": "Transfer", "params": [{"name": "from", "tla_type": "Accounts", "code_type": "AccountId"}, ...]}
    ],
    "invariants": [
      {"name": "BalanceNonNeg", "formula": "\\A a \\in Accounts: balances[a] >= 0",
       "test_expression": "state.balances.values().all(|b| *b >= 0)"}
    ]
  }
  ```
  This dual representation (TLA+ type + target-language type) is what makes mechanical translation possible. The LLM produces both during Compose; Bridge consumes the target-language side.

---

## Promise Review

### Well-Defined:
- ✅ **Convergence guarantee** — "Search may loop; targeted editing converges." The counterexample-as-editing-context pattern is well-justified. The two-failure hard stop prevents unbounded retry.
- ✅ **Incremental composition** — "Adding behavior N+1 doesn't re-verify behaviors 1 through N." This holds because of the CONFORM OR DIE principle — the new behavior must pass against the existing composed spec.
- ✅ **Parallel verification** — "Independent components verified in parallel." Correct — disconnected components have no shared variables, so their verifications are independent.

### Missing or Unclear:

- ⚠️ **P1: Ordering guarantee within a connected component is unspecified.** When a component has behaviors B1, B2, B3, and all arrive from Ingest simultaneously, what order are they composed? The plan's one-shot loop processes behaviors sequentially (`for each behavior B_i`), but doesn't specify the ordering.

  Does ordering matter? Possibly. If B1 and B2 both introduce the same resource with different schemas, whichever goes first "wins" (it's in the composed spec), and the other must conform. Different orderings could lead to different "winners."

  **Impact:** Non-deterministic ordering means the same input could produce different specs depending on processing order.

  **Recommendation:** Either (a) define a canonical ordering (e.g., by requirement priority, or by dependency depth — leaf behaviors first), or (b) explicitly state that ordering doesn't matter because the Ingest stage already resolved resource schemas before Compose begins. Option (b) is cleaner but requires Ingest to produce fully-resolved resource schemas, not just identifications.

- ⚠️ **P2: The "re-verify only the affected subgraph" promise needs qualification.** When two components merge, the plan says "Only the MERGED component is re-verified." But what does re-verify mean? Re-run TLC on the composed spec? That's potentially expensive if both components were large. The existing individual specs still hold for their respective properties — you only need to check NEW cross-invariants from the merge.

  **Recommendation:** Clarify: re-verification of a merged component means (a) compose the two existing specs (mechanical), (b) generate cross-invariants for the newly-shared resources (LLM call), (c) run TLC on the composed spec with the new cross-invariants. Existing individual invariants are inherited and don't need re-derivation.

---

## Data Model Review

### Well-Defined:
- ✅ **Node types** — 7 kinds (Requirement, Behavior, Resource, Constraint, Spec, Test, Module) with clear semantics.
- ✅ **Edge types** — 6 relationships (decomposes, references, constrains, models, verifies, implements) with clear from/to types.
- ✅ **JSON representation** — The example registry JSON is concrete and parseable.

### Missing or Unclear:

- ❌ **D1: The Resource node schema is critically underspecified.** The plan's example shows:
  ```json
  "res-0001": {
    "kind": "resource",
    "name": "account_balances",
    "type": "state_variable",
    "schema": "Map<AccountId, NonNegativeInt>"
  }
  ```

  But `"schema": "Map<AccountId, NonNegativeInt>"` is a string. What language is this type in? TLA+? The target language? A custom DSL? How does the composition engine know that `account_balances` in Spec_A is the same shared variable as `account_balances` in Spec_B? By name matching? By UUID?

  CW8.1's `ResourceEntry` (`schema_store.rs:494-515`) has `resource_id`, `name`, `category`, `type_ref`, `source_schema`, `source_key`, `predicates`, `codepaths` — significantly more structure. The plan's Resource node carries less information than what already exists.

  **Impact:** Resource schema is the linchpin of composition. If two specs share a resource but describe it with incompatible schemas, composition will silently produce an inconsistent model.

  **Recommendation:** Resource nodes need at minimum:
  - `tla_type: String` — the TLA+ type expression (e.g., `[Accounts -> Nat]`)
  - `code_type: String` — the target-language type (e.g., `Map<AccountId, u64>`)
  - `predicates: Vec<Predicate>` — named boolean conditions (from CW8.1's existing model)
  - `access_modes: Map<BehaviorId, AccessMode>` — R/W/RW/X per behavior (from CW8.1's formalization doc)

  When a new behavior references an existing resource, its declared schema must be compatible (unifiable) with the resource's existing schema. If not, reject the behavior.

- ❌ **D2: The Spec node doesn't carry enough information for Bridge.** The example shows:
  ```json
  "spec-0001": {
    "kind": "spec",
    "tla_module": "Transfer",
    "variables": ["balances"],
    "invariants": ["BalanceNonNeg", "Conservation"],
    "actions": ["Transfer"]
  }
  ```

  These are just names — string identifiers. The actual TLA+ source is in `composed_specs[component].tla_source`. But the Bridge stage needs TYPED representations of each variable, action, and invariant (see I4 above). The Spec node must either carry the typed IR directly or the `tla_source` must be parseable into one.

  **Impact:** Without typed Spec nodes, Phase 5 (Bridge) cannot be implemented as described.

  **Recommendation:** The Spec node should carry the full typed IR described in I4's recommendation. The `tla_source` string is the authoritative TLA+ text for TLC verification; the typed IR is the authoritative input for Bridge translation. Both are produced by the LLM during Compose and stored on the Spec node.

- ⚠️ **D3: No serialization format specified for persistence.** The plan shows JSON examples but doesn't specify: file-backed vs. SQLite? Atomic writes? Concurrent access? CW8.1 uses atomic JSON writes (`persistence.rs` — write to `.tmp`, rename). CW7 uses SQLite with savepoint transactions (`persist.py`). Which pattern does CW9.0 follow?

  **Impact:** Low for Phase 1 (standalone data structure), but becomes important in Phase 6 (UI integration) when concurrent reads/writes are possible.

  **Recommendation:** Start with atomic JSON (simpler, matches CW8.1 pattern, good for debugging). Migrate to SQLite if concurrent access becomes necessary. Define the interface (`save`/`load`) abstractly so the backend can change.

---

## API Review

### Well-Defined:
- ✅ **Registry CRUD operations** — Clearly enumerated in Phase 1: add, query by kind, query by ID, edge operations, closure computation, component detection.
- ✅ **TLC integration** — CW8.1's `run_tlc.rs` already handles TLC discovery (PATH → java → auto-download), timeout, and output capture. This can be reused directly.
- ✅ **Counterexample extraction** — CW8.1's `interpret_results.rs` already parses `State N:` blocks and `/\ var = val` lines into structured `CounterexampleStep` records.

### Missing or Unclear:

- ⚠️ **A1: The context query API ("given behavior B, return all relevant context") needs a contract.** The tiered prompt structure (Tier 0-3) defines what to include, but not the query interface. What function signature? What return type? How is "direct dependency" defined — one hop in the DAG? Through resource edges only? Through all edge types?

  **Recommendation:** Define:
  ```
  fn query_context(registry: &Registry, behavior_id: NodeId) -> BehaviorContext {
    tier_0: Vec<InterfaceSpec>,     // direct dependency interfaces (1-hop via 'references' edges)
    tier_1: Vec<InvariantSpec>,     // invariants of direct dependencies
    tier_2: Vec<ModuleBody>,        // full bodies of implicated modules (empty on first shot)
    tier_3: Vec<OneLinerSummary>,   // transitive deps (via closure table)
    composed_spec: Option<String>,  // existing composed TLA+ for the component this behavior will join
  }
  ```

- ⚠️ **A2: The counterexample-to-natural-language translator is listed in Phase 3 but not specified.** CW8.1's `CounterexampleStep` gives `state_number`, `action_name`, `path_step_name`, `variable_values: Vec<(String, String)>`. Converting this to "In state 3, Transfer sets balance to -5, violating NonNeg" requires mapping opaque variable names and values to domain concepts. Who does this mapping — template substitution using Spec node metadata? An LLM call?

  **Recommendation:** If the Spec node carries the typed IR (per I4/D2 recommendations), then counterexample translation is mechanical: substitute variable names with their human-readable descriptions, format values using their declared types. If the Spec node is just string identifiers, this becomes yet another LLM call.

---

## Critical Issues (Must Address Before Implementation)

1. **Bridge Stage Feasibility (I4 + D2):** The plan's central promise — "mechanical translation from TLA+ to code, no LLM" — requires a typed TLA+ intermediate representation that does not exist in any current codebase. The existing `TlaModel` carries only opaque string tokens. Without designing the typed IR first, Phase 5 (Bridge) is unimplementable as described, and the entire pipeline's value proposition (deterministic test derivation) falls apart.

   **Impact:** If Bridge requires an LLM call, it becomes Implement-lite, not a deterministic gate. The claim "same spec always produces same tests" becomes false.

   **Recommendation:** Design the typed IR before Phase 1. It doesn't need to be built in Phase 1, but its shape constrains the Spec node schema, which constrains the registry data model, which IS Phase 1. Designing it after Phase 1 means reworking the registry.

2. **Cross-Invariant Authorship (C2):** The most valuable output of composition — invariants that span behaviors — has no defined authorship mechanism. Without explicit cross-invariant generation, composition catches only Init contradictions and type mismatches, missing the "transfer to nonexistent account" class of bugs that motivates the entire design.

   **Impact:** Composition without cross-invariants is composition without teeth.

   **Recommendation:** Add an explicit cross-invariant generation step to the one-shot loop. When composing, the LLM receives: "these behaviors share resource X. Here are A's actions on X and B's actions on X. What invariants must hold across both?" The output is `Invariant_cross`, added to the composed spec before TLC runs.

3. **Resource Schema as Composition Anchor (D1):** Resource nodes need typed schemas, not just name strings. Two specs can only compose on a shared resource if their declarations of that resource's type are compatible. The plan shows this working (`"schema": "Map<AccountId, NonNegativeInt>"`) but doesn't define compatibility checking or what happens on mismatch.

   **Impact:** Without resource schema compatibility checking, composition is unsound — TLC could check a composed spec where the two behaviors disagree on the resource's type domain.

   **Recommendation:** Resource schema compatibility is a Phase 1 concern (it's a registry-level check). Define: `fn register_resource(registry: &mut Registry, resource: Resource) -> Result<NodeId, SchemaConflict>` that rejects a resource if its schema conflicts with an existing resource of the same identity.

---

## Suggested Plan Amendments

```diff
# Phase 1: The Registry

+ Add: Typed IR design document before implementation begins.
+       The Spec node schema must include variable types, action parameter types,
+       and test expression strings — not just name lists.

+ Add: Resource schema compatibility checking on registration.
+       Resources are the composition joints; their schemas must be authoritative.

+ Add: Supersession mechanism definition (C1).
+       Either superseded_by pointer, version filtering, or tombstone flag.

+ Add: Connected component detection algorithm specification (I1).
+       Union-find on behavior↔resource bipartite graph.

# Phase 3: TLA+ Templates + Composition Engine

+ Add: Cross-invariant generation as an explicit step in composition.
+       The LLM produces Invariant_cross when composing behaviors on shared resources.

+ Add: Typed TLA+ IR (dual representation: TLA+ type + target-language type)
+       as the Spec node's payload. This is what Bridge consumes.

# Phase 4: The One-Shot Loop

~ Modify: Define canonical ordering for behaviors within a component (P1).
~         Leaf behaviors (no resource dependencies) first, then by depth.

# Phase 5: The Bridge

~ Modify: Bridge consumes the typed IR from Spec nodes, not raw TLA+ text.
~         The translation rules map code_type fields to target-language types,
~         not TLA+ type expressions.

+ Add: Counterexample-to-natural-language translation specification (A2).
+       Mechanical if typed IR exists; LLM call if not.
```

---

## What the Plan Gets Right (Strengths Worth Preserving)

1. **The CSP framing is precise and correct.** The nested loop IS arc-consistency propagation on a CSP, and the registry-as-precomputed-constraints IS the correct elimination strategy.

2. **The one-shot-with-replay pattern is sound.** Counterexample-guided repair is a well-understood technique (CEGAR — counterexample-guided abstraction refinement). The two-failure hard stop converts an unbounded process into a bounded one.

3. **The CONFORM OR DIE principle is the right call.** Later behaviors conform to the existing composed spec or get rejected. The existing spec is law. This eliminates the re-verification cascade that plagued the nested-loop design.

4. **The verification spectrum is pragmatic.** Layered fail-fast checking (parse → type → bounded TLC → deep TLC) means interactive responsiveness without sacrificing thoroughness.

5. **The template strategy limits LLM variability.** "Pick the template, fill in domain-specific parameters, add domain-specific invariants" is dramatically more constrained than "write TLA+ from scratch." This is the right way to use an LLM — as a parameter filler within a deterministic structure, not as a free-form author.

6. **The philosophical point is exactly right.** The TLA+ spec IS the understanding. The registry contains specs annotated with their natural-language origins, not requirements that get translated to specs. This inversion is the design's core insight.

---

## Approval Status

- [ ] **Ready for Implementation** — No critical issues
- [x] **Needs Minor Revision** — Address critical issues 1-3 before beginning Phase 1
- [ ] **Needs Major Revision** — Critical issues must be resolved first

The plan is architecturally sound. The three critical issues (typed IR, cross-invariant authorship, resource schema compatibility) are all solvable within the existing architecture — they are specification gaps, not design flaws. Addressing them before Phase 1 will prevent rework.
