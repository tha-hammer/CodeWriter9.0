# Extract TLA+ Model from Existing Code

Analyze existing code, extract a formal behavioral model, and produce:

1. Path spec markdown for human traceability
2. TLA+ module (`.tla`) authored directly by the LLM
3. TLC config (`.cfg`) authored directly by the LLM

Then run TLC directly via `silmari run-tlc --json` and use the result to drive TDD planning.

**Pipeline:** `/extract_tlaplus_model` -> `silmari run-tlc --json` -> `CreateImplementationPlan` (BAML) -> TDD execution

Use Haiku subagents for file searches, grep, and file discovery.
Use up to 10 Sonnet subagents for behavior analysis and state-transition tracing.
Keep the main context for synthesis and model authoring.

## Initial Response

**If parameters provided** (file paths, function names, or a change description):
- Read all mentioned files FULLY (no partial reads)
- Begin analysis immediately

**If no parameters:**
```
I'll extract a formal behavioral model from the current code and produce:
- a path-spec markdown for traceability
- a .tla spec
- a matching .cfg file

Then I'll run TLC directly with `silmari run-tlc --json` so the result can feed TDD planning.

Please provide:
1. What you want to change (briefly)
2. Entry points (files/functions/modules)
3. Optional scope boundary (how deep to trace)

Example: /extract_tlaplus_model "Add retry logic to http_post" src/api/client.rs
```

Then wait for user input.

## Process

### Step 1: Scope the Extraction

1. Read all mentioned files FULLY using the Read tool
   - Do not spawn sub-tasks before reading these files yourself

2. Identify the change boundary:
   - Functions to modify/extend
   - Callers (dependencies on these functions)
   - Callees (dependencies these functions rely on)
   - Boundary: what to model vs. treat as opaque

3. Present scope for confirmation:
```
**Extraction Scope**

Change: [what the user wants to do]

Functions to model:
- `function_a()` in file.rs:45 — [role]
- `function_b()` in file.rs:112 — [role]

Callers:
- `caller_x()` in other.rs:30 — expects [contract]

Callees (opaque):
- `db.query()` — returns [type], can fail with [errors]

Boundary: [inside vs outside model]

Does this scope capture the right slice?
```

### Step 2: Extract State Machine

Spawn parallel subagents to analyze each scoped function.

For each function, extract:

1. States: entry, processing, terminal (success + error variants)
2. Transitions: input/condition for each state change
3. Invariants:
   - Type/data contracts
   - Ordering constraints
   - Resource lifecycle rules
   - Error propagation rules
4. Caller expectations:
   - Return values
   - Error semantics
   - Side effects

### Step 3: Synthesize the Behavioral Model

Combine subagent findings, reconcile conflicts, present summary:

```
**Behavioral Model: [scope-name]**

States:
1. idle -> 2. validating -> 3. executing -> {success, error}

Transitions:
- idle -> validating: called with [args]
- validating -> executing: validation passes
- validating -> error: validation fails
- executing -> success: returns [type]
- executing -> error: returns [error]

Invariants:
- [INV-1] [description] — file:line
- [INV-2] [description] — file:line
- [INV-3] [description] — file:line

Proposed change impact:
"[description]" affects transitions [X -> Y], may interact with [INV-*].

Does this accurately capture current behavior?
```

### Step 4: Generate Three Outputs

#### Output A: Path Spec Markdown (Documentation)

Write to: `specs/orchestration/<scope-name>-model.md`

This is for human traceability. It is not the source of truth for model generation.

Use this template:

```markdown
# PATH: <scope-name>-model

**Layer:** 3 (Function Path)
**Priority:** P1
**Version:** 1
**Source:** Extracted from existing code — [files analyzed]

## Purpose

Behavioral model of [functions] extracted from current code.

## Trigger

[Activation event]

## Resource References

| UUID | Name | Role in this path |
|------|------|-------------------|
| `cfg-a1b2` | config_store | [role] |

## Steps

1. **[State name]**
   - Input: [data entering state]
   - Process: [transformation]
   - Output: [produced result]
   - Error: [failure modes] -> [error handling]

## Terminal Condition

[What callers observe on completion]

## Feedback Loops

[Retry/loop details or "None — strictly linear."]

## Extracted Invariants

| ID | Invariant | Source | TLA+ Property | Test Oracle |
|----|-----------|--------|---------------|-------------|
| INV-1 | [description] | [file:line] | [PropertyName] | [assertion] |

## Change Impact Analysis

**Proposed change:** [description]
**Affected steps:** [steps]
**Affected invariants:** [INV-*]
**Risk:** [what could break]
**Recommendation:** [safe extension path]
```

#### Output B: TLA+ Module (`.tla`) (Formal Source of Truth)

Write to: `artifacts/tlaplus/<scope-name>/<ScopeName>.tla`

#### Output C: TLC Config (`.cfg`)

Write to: `artifacts/tlaplus/<scope-name>/<ScopeName>.cfg`

### Baseline Properties (always include these three)

| Property | Kind | What It Proves |
|----------|------|----------------|
| Reachability | Temporal | Every run reaches done or error |
| TypeInvariant | Invariant | State remains within valid domains |
| ErrorConsistency | Invariant | Error state implies error-handling path |

### Domain-Specific Properties (add as many as needed)

For each extracted invariant, define a domain-specific property, for example:
- `ResourceSafety == acquired => <>released`
- `MonotonicProgress == step_number' >= step_number`
- `BalanceNonNegative == balance >= 0`
- `RetryBound == retry_count <= MAX_RETRIES`

The three baseline properties are a minimum floor, not a ceiling.

### TLA+ Writing Constraints

1. Module name matches filename (PascalCase, no hyphens)
2. `EXTENDS Naturals, Sequences, FiniteSets` at minimum
3. All variables appear in `Init` and every action's `UNCHANGED` handling
4. `Spec == Init /\ [][Next]_vars /\ WF_vars(Next)` for liveness
5. Every constant declared in `.tla` has assignment in `.cfg`
6. `.cfg` `INVARIANTS` names operators defined in `.tla`
7. `.cfg` `PROPERTIES` names temporal formulas defined in `.tla`
8. Do not use TLAPS proof obligations
9. Keep state space finite (bounded sets/counters)

### Step 5: Verify with `run-tlc`

Run:

```bash
silmari run-tlc artifacts/tlaplus/<scope-name>/<ScopeName>.tla --config artifacts/tlaplus/<scope-name>/<ScopeName>.cfg --json
```

Interpret `RawVerificationReport` outcome:

- `AllPassed`: model checks passed
- `PropertyViolated`: meaningful counterexample found
- `Timeout`: state space/time bound issue
- `Error`: parse/type/config/runtime problem in model

If outcome is `Error`, perform fix-and-retry (max 3 attempts):

1. Read `raw_stderr`
2. Identify parse/type/config issue
3. Patch `.tla`/`.cfg`
4. Re-run `silmari run-tlc --json`

If outcome is `PropertyViolated`, do not auto-fix the model; report the violated property and counterexample to user as meaningful verification signal.

### Step 6: Handoff to TDD Planning

The verified artifacts flow into planning:

1. Path steps -> testable behaviors
2. TLA+ properties (baseline + domain-specific) -> test oracles
3. Invariants + file:line evidence -> concrete test assertions

Summarize handoff:

```
Verified artifacts ready:
- specs/orchestration/<scope-name>-model.md
- artifacts/tlaplus/<scope-name>/<ScopeName>.tla
- artifacts/tlaplus/<scope-name>/<ScopeName>.cfg

Verification result: [AllPassed | PropertyViolated | Timeout | Error]
Relevant properties: [list]
Counterexample summary: [if any]
```

### Step 7: Beads Integration

1. `bd list --status=open` to find existing related work
2. Create/update tracking issue:
   ```bash
   bd create --title="TLA+ model: <scope-name>" --description="Extracted from [files]. Includes baseline + domain-specific properties. Change: [description]" --type=task --priority=2
   ```
3. Link dependencies if related to tracked work

## Guidelines

### Good Extraction Traits

- Right granularity: changed functions + one level of callers/callees
- Explicit invariants: each mapped to source `file:line`
- Honest uncertainty: mark `[AMBIGUOUS]` when behavior is not provable from code
- Minimal state model: human-readable in under 2 minutes

### Common Patterns

| Code Pattern | Model Shape |
|---|---|
| Sequential calls | Linear step chain |
| If/else branch | Guarded transition |
| Retry loops | Bounded counter + fairness |
| Resource lifecycle | acquire/release invariants |
| Async callback | Trigger + eventual terminal condition |

### When Not to Extract

- Pure functions where direct tests are enough
- Trivial CRUD where formal model adds no value
- Code being fully replaced (model interface contract only)
- Third-party internals (model call boundary only)

### Relationship to Other Commands

| Command | Use Case |
|---|---|
| `/research_codebase` | Understanding only |
| `/extract_tlaplus_model` | Brownfield behavior modeling + formal verification |
| `/plan_path` | Greenfield path synthesis |
| `/create_tdd_plan` | Build test-first implementation plan from model |

### Important Rules

- Read all relevant files completely before spawning subagents
- Wait for all subagent results before synthesis
- `.tla` + `.cfg` are the formal truth; path spec is narrative traceability
- Always run `silmari run-tlc --json` before handoff
- Explicitly flag ambiguities instead of guessing
- Confirm with user at scope, model, and verification checkpoints
