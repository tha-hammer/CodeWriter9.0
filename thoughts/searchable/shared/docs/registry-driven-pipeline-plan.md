# Registry-Driven Pipeline: Implementation Plan

## The Problem in One Sentence

TLA+ models are isolated per-GWT, so cross-behavior inconsistencies go undetected,
and dependency discovery requires nested loops that don't converge.

## The Solution in One Sentence

A central resource_registry DAG makes every dependency explicit, enabling TLA+ model
composition and reducing the LLM's job to one-shot decisions with deterministic verification.

---

## What Exists Today

```
User prompt
    |
    v
 Gate 1 ──> Parse requirements ──> JSON
    |            |
    |            v
    |       Decompose each requirement into GWT behaviors
    |       (labels: Gate 1 - GWT: F-1.1 (3/9))
    |            |
    v            v
 Gate 2 ──> Determine techstack (3 options)
    |
    v
 User Review ──> "Review GWT Criteria"
    |              approve all / approve-reject individual
    v
 "Start Planning"
    |
    v
 [isolated TLA+ models per GWT]  <── THE PROBLEM
    |                                  models can't see each other
    v                                  dependencies discovered late
 Implementation                        nested loops to reconcile
```

**What breaks:** When GWT-A and GWT-B both touch "user session" but their TLA+
models don't know about each other, you discover the conflict during implementation.
Fixing A-for-B breaks A-for-C. This is O(n^2) stochastic search with no
convergence guarantee.

---

## What We're Building

```
User prompt
    |
    v
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: INGEST                                            │
│                                                             │
│  Single LLM call produces:                                  │
│    - Requirements (what the user wants)                     │
│    - Behaviors (GWT decomposition)                          │
│    - Techstack constraints (language, framework, infra)     │
│    - Resource identification (shared state, APIs, stores)   │
│                                                             │
│  ALL become nodes in the resource_registry with edges.      │
└─────────────────────┬───────────────────────────────────────┘
                      |
                      v
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: COMPOSE                                           │
│                                                             │
│  Registry dependency graph -> connected components.         │
│  Each component gets a composed TLA+ spec.                  │
│  Independent components verified in parallel.               │
│                                                             │
│  One-shot-with-replay: if TLC rejects, counterexample       │
│  goes back to LLM for exactly one retry.                    │
│  Two failures = requirements inconsistency (not a bug).     │
└─────────────────────┬───────────────────────────────────────┘
                      |
                      v
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: REVIEW                                            │
│                                                             │
│  User sees invariants in plain English:                     │
│    "Your system guarantees:                                 │
│     - Account balance is never negative                     │
│     - No access without valid session                       │
│     - Every queued job is eventually processed"             │
│                                                             │
│  Approve/reject properties, not raw GWT.                    │
│  One checkpoint, not multiple gates.                        │
└─────────────────────┬───────────────────────────────────────┘
                      |
                      v
┌─────────────────────────────────────────────────────────────┐
│  STAGE 4: BRIDGE                                            │
│                                                             │
│  Mechanical translation (NO LLM):                           │
│    TLA+ state vars   --> data model / schema                │
│    TLA+ actions      --> function signatures                │
│    TLA+ invariants   --> test assertions + runtime checks   │
│                                                             │
│  Output: TDD plan with test oracles from the spec.          │
└─────────────────────┬───────────────────────────────────────┘
                      |
                      v
┌─────────────────────────────────────────────────────────────┐
│  STAGE 5: IMPLEMENT                                         │
│                                                             │
│  Code written to pass tests.                                │
│  Independent modules built in parallel.                     │
│  Each module = 1 LLM call.                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## The Resource Registry: The Spine of Everything

### What It Is

A directed acyclic graph (DAG) that is the single source of truth for the project.
Every artifact is a node. Every relationship is an edge. The project state is always
the current graph.

### Node Types

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Requirement  │   │  Behavior    │   │  Resource     │
│              │   │  (GWT)       │   │  (shared      │
│ natural lang │   │  given/when/ │   │   state)      │
│ user intent  │   │  then        │   │              │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       |                  |                  |
       | decomposes       | references       |
       v                  v                  v
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Constraint   │   │    Spec      │   │    Test      │
│              │   │  (TLA+       │   │  (assertion  │
│ techstack,   │   │   fragment)  │   │   from spec) │
│ perf, sec    │   │              │   │              │
└──────────────┘   └──────┬───────┘   └──────┬───────┘
                          |                  |
                          | models           | verifies
                          v                  v
                   ┌──────────────┐
                   │   Module     │
                   │  (impl code) │
                   │              │
                   └──────────────┘
```

### Edge Types

| Edge          | From         | To          | Meaning                                  |
|---------------|--------------|-------------|------------------------------------------|
| decomposes    | Requirement  | Behavior    | "this requirement breaks into these GWTs" |
| references    | Behavior     | Resource    | "this behavior reads/writes this state"   |
| constrains    | Constraint   | Behavior    | "this techstack choice limits this GWT"   |
| models        | Spec         | Behavior    | "this TLA+ fragment formalizes this GWT"  |
| verifies      | Test         | Spec        | "this test checks this spec property"     |
| implements    | Module       | Test        | "this code satisfies this test"           |

### Key Properties

1. **Monotonic growth.** Nodes are never deleted, only superseded. Once a spec
   passes verification, later behaviors cannot invalidate it.

2. **Transitive closure table.** For each node, the set of all reachable nodes
   is pre-computed. O(1) to answer "does A transitively depend on B?"

3. **Composed specs cache.** Indexed by connected component. When a new behavior
   joins a component, the cache updates incrementally (composition is associative).

### Registry Data Structure (JSON)

```
{
  "nodes": {
    "req-0001": {
      "kind": "requirement",
      "text": "Users can transfer money between accounts",
      "version": 1
    },
    "gwt-0001": {
      "kind": "behavior",
      "given": "User has account with sufficient balance",
      "when": "User initiates transfer",
      "then": "Source debited, destination credited, total unchanged",
      "version": 1
    },
    "res-0001": {
      "kind": "resource",
      "name": "account_balances",
      "type": "state_variable",
      "schema": "Map<AccountId, NonNegativeInt>"
    },
    "spec-0001": {
      "kind": "spec",
      "tla_module": "Transfer",
      "variables": ["balances"],
      "invariants": ["BalanceNonNeg", "Conservation"],
      "actions": ["Transfer"]
    }
  },
  "edges": [
    {"from": "req-0001", "to": "gwt-0001", "type": "decomposes"},
    {"from": "gwt-0001", "to": "res-0001", "type": "references"},
    {"from": "spec-0001", "to": "gwt-0001", "type": "models"}
  ],
  "closure": {
    "req-0001": ["gwt-0001", "res-0001", "spec-0001"]
  },
  "composed_specs": {
    "component-1": {
      "members": ["spec-0001"],
      "tla_source": "..."
    }
  }
}
```

---

## How TLA+ Composition Works

### The GWT-to-TLA+ Mapping

```
 Given                        When                         Then
 "user has balance >= 100"    "user transfers 50"          "balance decreases by 50"
       |                           |                            |
       v                           v                            v
 Init predicate              Action in Next               Invariant
 balances["alice"] >= 100    Transfer(from, to, amt):      BalanceNonNeg ==
                               /\ balances[from] >= amt      \A a \in Accounts:
                               /\ balances' = ...              balances[a] >= 0
```

### Isolated vs Composed Models

**Isolated (current problem):**

```
  Spec_A (Transfer)           Spec_B (CreateAccount)
  ┌─────────────────┐         ┌─────────────────────┐
  │ vars: balances   │         │ vars: accounts       │
  │ Init: ...        │         │ Init: ...            │
  │ Next: Transfer   │         │ Next: CreateAccount  │
  │ Inv: NonNeg      │         │ Inv: UniqueEmail     │
  └─────────────────┘         └─────────────────────┘
       |                            |
       |  INVISIBLE TO EACH OTHER   |
       |  Can't detect:             |
       |  - Transfer to nonexistent |
       |    account                 |
       |  - CreateAccount breaks    |
       |    balance invariant       |
```

**Composed (what registry enables):**

```
  Registry detects: Transfer.references("account_balances")
                    CreateAccount.references("accounts")
                    "accounts" and "account_balances" share key space
                    --> same connected component
                    --> MUST compose

  Composed Spec:
  ┌─────────────────────────────────────────────────┐
  │ vars: <<balances, accounts>>                     │
  │                                                  │
  │ Init: Init_Transfer /\ Init_CreateAccount        │
  │                                                  │
  │ Next: \/ (Transfer /\ UNCHANGED accounts)        │
  │       \/ (CreateAccount /\ UNCHANGED balances)    │
  │                                                  │
  │ Inv: BalanceNonNeg                               │
  │   /\ UniqueEmail                                 │
  │   /\ TransferTargetExists   <── CROSS-BEHAVIOR   │
  │      (can only transfer to                       │
  │       existing account)                          │
  └─────────────────────────────────────────────────┘

  TLC checks ALL interleavings of Transfer and
  CreateAccount. Finds bugs like: "transfer to
  account that hasn't been created yet."
```

### Why Composition is Associative (and Why That Matters)

```
  compose(A, B) then compose with C:

  Init: (Init_A /\ Init_B) /\ Init_C  =  Init_A /\ Init_B /\ Init_C
  Next: (Next_AB) \/ Next_C           =  Next_A \/ Next_B \/ Next_C
  Inv:  (Inv_AB) /\ Inv_C             =  Inv_A /\ Inv_B /\ Inv_C

  Same result regardless of order.
  --> You NEVER recompose from scratch.
  --> Adding behavior N is O(1), not O(N).
```

---

## The One-Shot-With-Replay Loop

This is the core algorithm. It replaces the nested loops.

```
                    ┌──────────────────────────┐
                    │  New behavior B_i        │
                    │  (GWT from Ingest)       │
                    └────────────┬─────────────┘
                                 |
                                 v
                    ┌──────────────────────────┐
                    │  Query registry for      │
                    │  relevant context:       │
                    │  - shared resources      │
                    │  - existing contracts    │
                    │  - existing invariants   │
                    │  - dependency subgraph   │
                    │  - composed spec so far  │
                    └────────────┬─────────────┘
                                 |
                                 v
                    ┌──────────────────────────┐
                    │  LLM generates TLA+      │
                    │  fragment for B_i        │◄──── ONE SHOT
                    │  (constrained by context)│      (not a conversation)
                    └────────────┬─────────────┘
                                 |
                                 v
                    ┌──────────────────────────┐
                    │  TLC checks:             │
                    │  compose(existing,        │
                    │         new_fragment)     │
                    └──────┬───────────┬───────┘
                           |           |
                      PASS |           | FAIL
                           |           |
                           v           v
                    ┌──────────┐  ┌─────────────────────┐
                    │ Register │  │ Extract counter-     │
                    │ in DAG   │  │ example trace:       │
                    │          │  │ "In state 3,         │
                    │ Update   │  │  Transfer sets       │
                    │ closure  │  │  balance to -5,      │
                    │ table    │  │  violating NonNeg"   │
                    │          │  └──────────┬───────────┘
                    │ Update   │             |
                    │ composed │             v
                    │ spec     │  ┌─────────────────────┐
                    │ cache    │  │ LLM retries with    │
                    └──────────┘  │ context + counter-  │◄── ONE MORE SHOT
                                  │ example             │
                                  └──────────┬──────────┘
                                             |
                                        ┌────┴────┐
                                   PASS |         | FAIL
                                        v         v
                                  ┌──────────┐ ┌──────────────────┐
                                  │ Register │ │ REQUIREMENTS     │
                                  │ in DAG   │ │ INCONSISTENCY    │
                                  └──────────┘ │                  │
                                               │ Surface to user: │
                                               │ "GWT-3 conflicts │
                                               │  with GWT-1 on   │
                                               │  resource X"     │
                                               └──────────────────┘
```

### The Conform-or-Die Rule

Registered behaviors are settled law. New behaviors must conform to all existing
commitments or they are rejected. Existing behaviors are NEVER revised to
accommodate newcomers.

```
  Behavior A registered, verified, committed.
  Behavior B arrives.
  TLC finds: interleaving A's actions with B's actions violates Invariant_B.

  Q: "But A didn't account for B's invariant!"
  A: That's B's problem, not A's.

  Two possibilities:

  1. Invariant_B is incompatible with the existing system.
     --> REQUIREMENTS INCONSISTENCY. Surface to user.
     --> "Your new requirement conflicts with existing guarantee X."
     --> User fixes B's requirements. A is not touched.

  2. B's actions are wrong (Invariant_B is valid but B's
     transitions create the violation).
     --> ONE RETRY: LLM gets the counterexample, fixes B's actions.
     --> B conforms to its own invariant AND all existing invariants.
     --> Or B dies.

  In NEITHER case is A revised.
  A was verified. A is committed. A is settled law.
```

This is the monotonic growth property enforcing its contract. Without it,
you're back to the nested loop: revise A for B, which breaks A for C,
which requires revising C... The conform-or-die rule is what makes the
registry a ratchet that only moves forward.

The ordering matters and that's correct. Earlier behaviors establish ground
truth. Later behaviors conform. This mirrors real systems: you don't
redesign your auth system every time you add a feature. You make the
feature work within auth's guarantees.

**Not all inputs are valid.** The system's job is to catch invalid inputs
early (during Compose) rather than late (during implementation). A rejected
behavior with a clear conflict message is a better outcome than a behavior
that silently destabilizes existing guarantees.

### Why This Converges

The counterexample is a **concrete execution trace**, not an abstract error.
It converts a search problem into an editing problem:

- Search: "find any valid TLA+ fragment" (unbounded)
- Edit: "fix this specific state transition so it doesn't violate this specific
  invariant" (targeted)

Search may loop. Targeted editing converges.

### What the LLM Sees on Each Shot

```
  PROMPT STRUCTURE:
  ┌─────────────────────────────────────────────────────────────┐
  │ [FIXED]                                                     │
  │   The GWT behavior to formalize                             │
  │   TLA+ spec templates (CRUD, state machine, queue, auth)    │
  │                                                             │
  │ [FROM REGISTRY]                                             │
  │   Tier 0: Direct dependency interfaces (always)             │
  │   Tier 1: Invariants of direct dependencies (always)        │
  │   Tier 2: Full module bodies (only on retry, only implicated│
  │           modules)                                          │
  │   Tier 3: Transitive deps (one-line summaries only)         │
  │                                                             │
  │ [ON RETRY ONLY]                                             │
  │   Previous attempt                                          │
  │   Counterexample trace in natural language                  │
  │   The specific invariant that was violated                  │
  └─────────────────────────────────────────────────────────────┘
```

---

## The Bridge: Spec to Code (No LLM)

This stage is mechanical. The LLM's stochasticity is a liability here.

```
  TLA+ Spec                         Generated Artifacts
  ─────────                         ───────────────────

  VARIABLES                         DATA MODEL
  balances \in                 -->  class AccountStore:
    [Accounts -> Nat]                 balances: dict[str, int]

  ACTIONS                           FUNCTION SIGNATURES
  Transfer(from, to, amt) ==   -->  def transfer(from_id: str,
    /\ balances[from] >= amt                    to_id: str,
    /\ balances' = ...                          amount: int) -> Result:

  INVARIANTS                        TEST ASSERTIONS
  BalanceNonNeg ==             -->  def test_balance_non_negative(state):
    \A a \in Accounts:                assert all(b >= 0 for b in
      balances[a] >= 0                  state.balances.values())

  Conservation ==              -->  def test_conservation(state):
    SumOf(balances) =                 assert sum(state.balances.values())
      INITIAL_TOTAL                     == INITIAL_TOTAL

  TLC TRACES                        TEST SCENARIOS
  State 0 -> State 1 ->       -->  def test_transfer_sequence():
    State 2 -> ...                    # exercise the exact trace TLC
                                      # found interesting
```

### The Translation Rules (Deterministic)

| TLA+ Construct          | Code Artifact              | Test Artifact                |
|--------------------------|---------------------------|------------------------------|
| State variable           | Field / column / key       | State fixture                |
| Type domain              | Type annotation            | Type assertion               |
| Named action             | Function with guard clause | Test method per action       |
| Action precondition      | Guard clause / assertion   | Test: rejected when unmet    |
| Action effect            | Function body              | Test: state changes correctly|
| Safety invariant         | Runtime assertion (opt.)   | After-every-action check     |
| TLC trace (interesting)  | --                         | Scenario test                |

---

## Handling Late-Discovered Dependencies

```
  BEFORE: Two isolated components

  Component 1              Component 2
  ┌─────────────┐          ┌─────────────┐
  │ GWT-A       │          │ GWT-C       │
  │ GWT-B       │          │ GWT-D       │
  │ res: users  │          │ res: orders │
  └─────────────┘          └─────────────┘
  Verified separately       Verified separately


  DISCOVERY: GWT-D references "user_id" in orders
             --> orders depends on users
             --> new edge: GWT-D --> res:users


  AFTER: Merged component

  Component 1 (merged)
  ┌──────────────────────────────┐
  │ GWT-A                       │
  │ GWT-B                       │
  │ GWT-C                       │
  │ GWT-D                       │
  │ res: users, orders          │
  │                             │
  │ NEW cross-invariant:        │
  │   OrderUserExists ==        │
  │     \A o \in orders:        │
  │       o.user_id \in users   │
  └──────────────────────────────┘

  Only the MERGED component is re-verified.
  GWT-A and GWT-B's existing tests still pass.
  You're only checking new interactions.
```

---

## Verification Spectrum

Not all checks need full TLC. Use a fail-fast pipeline:

```
  LLM output
      |
      v
  Layer 0: Parse  ──────────> ~10ms
  Does it parse as valid      catches 60% of failures
  TLA+ / valid JSON?
      |
      v
  Layer 1: Types  ──────────> ~100ms
  Do interfaces match         catches 25% of failures
  registry contracts?
      |
      v
  Layer 2: Bounded TLC ─────> ~1-5s
  Check all traces up to      catches 14% of failures
  depth 5. Small model
  hypothesis: most bugs
  manifest in small instances.
      |
      v
  Layer 3: Deep TLC ────────> ~30s (async)
  Depth 20. Run in            catches ~1% of remaining
  background, notify
  on failure.
      |
      v
  Layer 4: Full TLC ────────> minutes+ (CI only)
  Complete state space.        the last fraction
  Nightly build.
```

Interactive use: Layers 0-2 (~1-5 seconds total).
Everything else runs async and notifies on failure.

---

## Practical TLA+ Strategy

### Don't Write Full TLA+ From Scratch

Use templates. The LLM fills in parameters, not syntax.

```
  Template Library:
  ┌──────────────────────────────────────────────────┐
  │                                                  │
  │  CRUD Template                                   │
  │    state = set of records                        │
  │    actions = create/read/update/delete            │
  │    invariants = referential integrity             │
  │                                                  │
  │  State Machine Template                          │
  │    state = enum                                  │
  │    actions = transitions with guards             │
  │    invariants = no illegal transitions           │
  │                                                  │
  │  Queue/Pipeline Template                         │
  │    state = sequence of items                     │
  │    actions = enqueue/dequeue/process             │
  │    invariants = no item loss, ordering preserved │
  │                                                  │
  │  Auth/Session Template                           │
  │    state = session map                           │
  │    actions = login/logout/expire/refresh         │
  │    invariants = no access without valid session  │
  │                                                  │
  └──────────────────────────────────────────────────┘

  LLM's job: pick the template, fill in domain-specific
  parameters, add domain-specific invariants.
```

### Layer Separation: LLM Writes PlusCal, System Composes TLA+

The LLM never sees or touches the composition layer. It operates entirely
in PlusCal (state machine level thinking). The system handles everything
below that mechanically.

```
  ┌───────────────────────────────────────────────────────────────┐
  │ LLM's world: PlusCal only                                    │
  │                                                               │
  │  Templates are PlusCal with fill-in markers.                  │
  │  LLM picks a template, fills in:                              │
  │    - state variables (domain-specific names and types)        │
  │    - process bodies (transitions with guards)                 │
  │    - domain-specific invariants (as define statements)        │
  │                                                               │
  │  The LLM thinks in state machines. It never writes raw TLA+. │
  └──────────────────────────┬────────────────────────────────────┘
                             |
                             | PlusCal source
                             v
  ┌───────────────────────────────────────────────────────────────┐
  │ Deterministic machinery (no LLM)                              │
  │                                                               │
  │  1. PlusCal compiler (pcal → TLA+)                            │
  │     Deterministic. Ships with TLA+ toolbox.                   │
  │                                                               │
  │  2. Composition engine (operates on TLA+ output only)         │
  │     Joins modules that share variables:                       │
  │       Init_composed = Init_A ∧ Init_B                         │
  │       Next_composed = Next_A ∨ Next_B (with UNCHANGED)        │
  │       Inv_composed  = Inv_A ∧ Inv_B ∧ Inv_cross              │
  │                                                               │
  │  3. TLC model checker (runs on composed spec)                 │
  │                                                               │
  │  4. Counterexample translator (TLA+ trace → PlusCal language) │
  │     On failure, translates back UP to the LLM's level:        │
  │     "Your Transfer action allows a negative balance when      │
  │      called after CreateAccount with zero initial balance."   │
  │                                                               │
  │  The LLM never sees the composed TLA+. It only sees           │
  │  PlusCal-level feedback.                                      │
  └───────────────────────────────────────────────────────────────┘
```

This is the same principle as the Bridge stage: keep the LLM's job narrow
(fill in a PlusCal template) and the deterministic machinery's job broad
(compile, compose, verify, translate counterexamples). The LLM understands
one layer. The system handles the rest.

### The 80/20 of TLA+ for Code Generation

| Feature             | Value for codegen | Use it? |
|---------------------|-------------------|---------|
| PlusCal state machines | Very high      | Always  |
| Safety invariants      | Very high      | Always  |
| Type invariants        | High           | Always  |
| Bounded model checking | High           | Always  |
| Action composition     | High           | When shared state exists |
| Liveness properties    | Medium         | Only for queues/async    |
| Fairness conditions    | Low            | Only for distributed     |
| Full temporal logic    | Low            | Rarely                   |

---

## Implementation Sequence

### What to build, in what order

**Phase 1: The Registry** (foundation, everything depends on this)

Build the resource_registry as a JSON-backed DAG with:
- Node CRUD (add, query by kind, query by ID)
- Edge CRUD (add, query by type, query by endpoint)
- Transitive closure computation (update on edge add)
- Connected component detection
- Query: "given behavior B, return all relevant context"

This is a standalone data structure. No LLM, no TLA+, no UI.
Can be tested in isolation with unit tests.

**Phase 2: The Ingest Stage** (connects user input to registry)

Modify the existing Gate 1 + Gate 2 commands to:
- Produce registry nodes instead of standalone JSON
- Register resources explicitly (not just behaviors)
- Detect shared resources across behaviors on registration
- Output: populated registry, not separate GWT + techstack artifacts

**Phase 3: TLA+ Templates + Composition Engine**

- Build the 4 core templates (CRUD, state machine, queue, auth)
- Build the composition function: given two TLA+ modules that share
  variables, produce the composed module
- Build the TLC runner (shell out to `tlc` with bounded depth)
- Build counterexample-to-natural-language translator

**Phase 4: The One-Shot Loop**

- Wire together: registry query -> LLM prompt assembly -> TLA+ generation
  -> TLC verification -> pass/retry/fail routing
- This is the core algorithm. It replaces the current nested loop.
- The loop itself is simple; the complexity is in the registry query
  and prompt assembly.

**Phase 5: The Bridge**

- Build the mechanical translators: TLA+ -> data model, function sigs,
  test assertions
- These are template-based string transformations, not LLM calls
- Output: a TDD plan identical in format to what `/create_tdd_plan`
  currently produces, but derived from verified specs

**Phase 6: UI Integration**

- Replace the Gate 1 / Gate 2 / Review GWT flow with the 5-stage pipeline
- The review screen shows invariants in plain English, not raw GWT
- Progress indicators map to registry state (how many behaviors registered,
  how many specs verified, how many tests generated)

---

## What Changes in the Existing Commands

| Command                    | Current                        | After                           |
|----------------------------|-------------------------------|---------------------------------|
| Gate 1 (requirements)      | Standalone JSON output        | Produces registry nodes         |
| Gate 2 (techstack)         | Separate phase                | Merged into Ingest              |
| GWT Review                 | User reviews raw GWT          | User reviews invariants         |
| `/extract_tlaplus_model`   | Isolated per-function model   | Registers in DAG, auto-composes |
| `/plan_path`               | Reads resource_registry.json  | Reads the unified registry DAG  |
| `/create_tdd_plan`         | LLM-generated test plan       | Mechanically derived from spec  |

---

## Risk Assessment

| Risk                                      | Mitigation                                    |
|-------------------------------------------|-----------------------------------------------|
| TLC too slow for interactive use          | Bounded checking (depth 5) is ~1s             |
| LLM can't generate valid TLA+ fragments  | Templates reduce it to parameter-filling      |
| Registry gets too large for LLM context  | Tiered context (interfaces only, not bodies)  |
| Requirements are genuinely inconsistent  | Two-failure rule surfaces this to user early   |
| Composition blows up state space         | Only compose connected components, not all    |
| Late dependencies invalidate prior work  | Monotonic growth: re-verify subgraph only     |

---

## Success Criteria

1. **No nested loops.** The one-shot-with-replay pattern processes each behavior
   in at most 2 LLM calls.

2. **Cross-behavior bugs caught before implementation.** TLC finds "transfer to
   nonexistent account" type bugs during Compose, not during coding.

3. **Deterministic test derivation.** Tests come from verified specs, not LLM
   improvisation. Same spec always produces same tests.

4. **Incremental.** Adding behavior N+1 doesn't re-verify behaviors 1 through N.

5. **User reviews properties, not internals.** The review screen shows "your system
   guarantees X" not "GWT: F-1.1 given/when/then."
