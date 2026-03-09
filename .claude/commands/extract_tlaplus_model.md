# Extract TLA+ Model from Existing Code

Analyze existing code, extract a formal behavioral model, and produce a TLA+ path spec that captures current behavior. The verified model then flows directly into TDD planning — the TLA+ properties become test oracles, and each path step becomes a testable behavior.

**Pipeline:** `/extract_tlaplus_model` → `silmari verify-path` → `CreateImplementationPlan` (BAML) → TDD execution

Use Haiku subagents for file searches, grep, and file discovery.
Use up to 10 Sonnet subagents for analyzing code behavior and tracing state transitions.
Keep the main context for synthesis and model writing.

## Initial Response

**If parameters provided** (file paths, function names, or a change description):
- Read all mentioned files FULLY (no partial reads)
- Begin analysis immediately

**If no parameters:**
```
I'll extract a TLA+ behavioral model from existing code. The model captures what the code does today, gets formally verified, and then drives TDD planning — each verified property becomes a test oracle.

Please provide:
1. **What you want to change** — brief description of the modification
2. **Entry points** — file paths, function names, or module names affected
3. **Scope boundary** (optional) — how deep to trace

Example: `/extract_tlaplus_model "Add retry logic to http_post" src/api/client.rs`
```

Then wait for the user's input.

## Process

### Step 1: Scope the Extraction

1. **Read all mentioned files FULLY** using the Read tool
   - DO NOT spawn sub-tasks before reading these files yourself

2. **Identify the change boundary:**
   - Functions to modify/extend
   - Callers (what depends on these functions)
   - Callees (what these functions depend on)
   - Boundary — what to model vs. treat as opaque

3. **Present the scope for confirmation:**
```
**Extraction Scope:**

Change: [what the user wants to do]

Functions to model (will be TLA+ steps):
- `function_a()` in file.rs:45 — [brief role]
- `function_b()` in file.rs:112 — [brief role]

Callers (triggers/terminal condition observers):
- `caller_x()` in other.rs:30 — expects [contract]

Callees (opaque steps):
- `db.query()` — returns [type], can fail with [errors]

Boundary: [what's inside vs outside the model]

Does this scope capture the right slice?
```

### Step 2: Extract State Machine

Spawn parallel subagents to analyze each function in the scope.

**For each function, extract:**

1. **States** — Entry, processing, terminal (success + error variants)
2. **Transitions** — What input/condition causes each state change
3. **Invariants** — What must ALWAYS be true:
   - Type contracts (in/out types at each boundary)
   - Ordering constraints (A before B)
   - Resource contracts (acquired → must release)
   - Error propagation (propagated vs. swallowed)
4. **Caller expectations** — Return types, error handling, side effects

### Step 3: Synthesize the Behavioral Model

Combine subagent findings. Reconcile conflicts. Present in plain language:

```
**Behavioral Model: [scope name]**

States:
1. idle → 2. validating → 3. executing → {success, error}

Transitions:
- idle → validating: called with (args)
- validating → executing: validation passes
- validating → error: validation fails → ValidationError
- executing → success: → Result<T>
- executing → error: → OperationError

Invariants:
1. [INV-1] Every call terminates — file.rs:45
2. [INV-2] Errors propagate to caller — file.rs:67
3. [INV-3] Resource X released on all paths — file.rs:89

**Proposed change impact:**
Change "[description]" affects transitions [X → Y], may interact with [INV-N].

Does this model accurately capture the current behavior?
```

### Step 4: Generate the TLA+ Path Spec

**Mapping rules — these are precise, not guidelines:**

| Code construct | Path spec element | TLA+ property |
|---|---|---|
| Each function state | Step (Input/Process/Output/Error) | — |
| Type contract at boundary | TypeInvariant assertion | TypeInvariant |
| Ordering constraint | Step sequence | Reachability |
| Error propagation rule | Error field on step | ErrorConsistency |
| Resource acquire/release | Two steps with invariant | TypeInvariant |
| Caller expectation | Terminal condition | Reachability |

**These same TLA+ properties become test oracles downstream:**

| TLA+ Property    | What It Proves (model level)              | Test Oracle (code level)                         |
|------------------|-------------------------------------------|--------------------------------------------------|
| Reachability     | Every step reachable from trigger          | Code path exercisable from trigger to terminal   |
| TypeInvariant    | Types consistent at every step boundary    | Input/output types match at every function call   |
| ErrorConsistency | Error branches produce valid error states  | Error conditions produce correct error returns    |

**Write the path spec** to `specs/orchestration/<scope-name>-model.md`:

```markdown
# PATH: <scope-name>-model

**Layer:** 3 (Function Path)
**Priority:** P1
**Version:** 1
**Source:** Extracted from existing code — [files analyzed]

## Purpose

Behavioral model of [functions] extracted from existing codebase.
Current behavior captured as a verifiable baseline. Proposed changes
must preserve invariants unless explicitly relaxed.

## Trigger

[What activates this code path]

## Resource References

| UUID | Name | Role in this path |
|------|------|-------------------|
| `cfg-a1b2` | config_store | [role] |

**UUID format (parser rejects anything else):**
- Backtick-wrapped: `` `xx-xxxx` `` or `` `xxx-xxxx` ``
- Prefix: 2-3 lowercase letters (`cfg`, `api`, `db`, `fn`, `ui`, `fs`, `mq`)
- Hyphen separator
- Suffix: exactly 4 alphanumeric characters
- Examples: `cfg-a1b2`, `api-q7v1`, `db-a3f7`

## Steps

1. **[State name]**
   - Input: [what enters this state]
   - Process: [transformation — WHAT not HOW]
   - Output: [what this state produces]
   - Error: [failure modes] -> [error handling]

## Terminal Condition

[What callers observe on success]

## Feedback Loops

[Existing retry/loop behavior, or "None — strictly linear."]

## Extracted Invariants

| ID | Invariant | Source | TLA+ Property | Test Oracle |
|----|-----------|--------|---------------|-------------|
| INV-1 | [description] | [file:line] | Reachability | [test assertion] |
| INV-2 | [description] | [file:line] | TypeInvariant | [test assertion] |
| INV-3 | [description] | [file:line] | ErrorConsistency | [test assertion] |

## Change Impact Analysis

**Proposed change:** [description]
**Affected steps:** [which steps change]
**Affected invariants:** [which INV-* might be impacted]
**Risk:** [what could break]
**Recommendation:** [how to extend the model safely]
```

### Step 5: Verify the Extracted Model

```bash
silmari verify-path specs/orchestration/<scope-name>-model.md
```

**Interpret results:**
- **All pass** → Model is internally consistent. Properties become test oracles.
- **Reachability fails** → Unreachable state. Dead code or modeling error.
- **TypeInvariant fails** → Data flow inconsistency. Possible real bug.
- **ErrorConsistency fails** → Error paths don't terminate. Possible real bug.

Present results and confirm with user before proceeding.

### Step 6: Handoff to TDD Planning

The verified model flows directly into `CreateImplementationPlan` (BAML function in the CW7 pipeline). The connection is:

1. Each **path step** becomes a testable behavior in the TDD plan
2. Each **TLA+ property** becomes a test assertion (see oracle table above)
3. Each **invariant** becomes a specific test case with the source file:line as context
4. **Single piece flow**: step 1 test → step 1 impl → step 2 test → step 2 impl

```
**Verified model ready:** specs/orchestration/<scope-name>-model.md
- [N] steps, [N] invariants, all TLA+ properties pass

The model flows into TDD planning:
- Path steps → testable behaviors (1:1)
- TLA+ properties → test oracles (Reachability, TypeInvariant, ErrorConsistency)
- Invariants → specific test assertions with source traceability

Next steps:
1. Run through CW7 pipeline (plan_path → verify → CreateImplementationPlan)
2. Or: `/create_tdd_plan` with this model as the behavioral spec
3. Or: Extend the model first — add proposed changes, re-verify, then plan

Recommended: Option 3 if changing existing behavior. Option 1 for new paths.
```

### Step 7: Beads Integration

1. `bd list --status=open` — check for existing issues
2. Create tracking issue:
   ```bash
   bd create --title="TLA+ model: <scope-name>" --description="Extracted from [files]. [N] invariants. Change: [description]" --type=task --priority=2
   ```
3. Link dependencies if related to other tracked work

## Guidelines

### What Makes a Good Extraction

- **Right granularity** — Functions being changed + one level of callers/callees
- **Explicit invariants** — Every invariant cites source file:line AND specifies the test oracle
- **Honest uncertainty** — Flag ambiguous behavior as `[AMBIGUOUS]` rather than guessing
- **Minimal states** — Readable by a human in under 2 minutes

### Common Patterns

| Code Pattern | Path Spec Model |
|---|---|
| Sequential calls | Linear step chain: A → B → C |
| If/else branch | Single step with success/error outputs |
| Try/catch with retry | Feedback loop (bounded) |
| Resource acquire/release | Two steps + INV: acquired → must release |
| Callback/event | Trigger step with async terminal condition |
| Explicit state machine | Direct mapping — each state becomes a step |

### When NOT to Extract

- **Pure functions** — Test directly, no model needed
- **Trivial CRUD** — Model adds no insight
- **Code being replaced entirely** — Model the interface contract only
- **Third-party internals** — Opaque; model what you call and what returns

### Relationship to Other Commands

| Command | When |
|---|---|
| `/research_codebase` | Understand code without planning changes |
| `/extract_tlaplus_model` | Plan to change code, verify you don't break it |
| `/plan_path` | Greenfield — new path from user story |
| `/create_tdd_plan` | After extraction — model becomes behavioral spec for TDD |

### Important Rules

- Read all files COMPLETELY before spawning sub-tasks
- Wait for ALL sub-agents before synthesizing
- The model is a contract, not documentation — imprecision becomes bugs
- Always verify with `silmari verify-path` before handoff
- Flag ambiguities explicitly — wrong invariant > missing invariant
- User confirms: scope (step 1), model (step 3), verification (step 5)
