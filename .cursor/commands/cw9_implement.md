# CW9 Implement

Implement an approved CW9 TDD plan using verified specs, simulation traces, and bridge artifacts produced by the pipeline.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for implementation — don't run out of context before writing code.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, ask.

## CW9 CLI Reference

```
cw9 show <node-id> <project> --card                      # print IN:DO:OUT card
cw9 pipeline --skip-setup --gwt <id> <project>            # verify GWT → spec + traces + bridge
cw9 gen-tests <gwt-id> <project> [--lang X]               # generate tests from simulation traces
cw9 stale <project>                                       # check for outdated records
cw9 ingest <path> <project> --incremental                 # re-scan after code changes
cw9 crawl <project> --incremental                         # re-extract after code changes
```

## Pipeline Artifacts (produced during /cw9_plan)

| Artifact | Path | Use |
|---|---|---|
| Verified TLA+ spec | `.cw9/specs/<gwt-id>.tla` | Formal model — read to understand invariants |
| Simulation traces | `.cw9/specs/<gwt-id>_sim_traces.json` | Primary test context — concrete execution paths |
| Bridge artifacts | `.cw9/bridge/<gwt-id>_bridge_artifacts.json` | Implementation guide — data_structures, operations, verifiers, assertions |

## Process

### Step 1: Read Plan and Artifacts

1. **Read the plan completely** — check for existing checkmarks (`- [x]`)
2. **Read the research document** referenced in the plan
3. **Read bridge artifacts** for each GWT:
   ```bash
   cat <project>/.cw9/bridge/gwt-0001_bridge_artifacts.json | python3 -m json.tool
   ```
   The bridge tells you exactly what to build:
   - `data_structures` — types, models, state shapes
   - `operations` — functions/methods with their signatures
   - `verifiers` — invariant checks that must hold
   - `assertions` — specific conditions from the formal model

4. **Read simulation traces** for each GWT:
   ```bash
   cat <project>/.cw9/specs/gwt-0001_sim_traces.json | python3 -m json.tool | head -200
   ```
   Each trace is a sequence of states. The variable assignments at each state become concrete test values.

5. **Read the verified TLA+ spec** to understand invariants:
   ```bash
   cat <project>/.cw9/specs/gwt-0001.tla
   ```
   The `define` block contains the invariants your code must satisfy. These are formally verified — they represent real constraints.

6. If there are existing checkmarks, trust completed work and pick up from the first unchecked item

### Step 2: Beads Setup

- Run `bd list --status=open` to find the tracked issue for this plan
- Update status: `bd update <id> --status=in_progress`
- If no issue exists: `bd create --title="Implement: [feature]" --type=task --priority=2`

### Step 3: Generate Tests from Traces

For each GWT, generate test scaffolds from simulation traces:

```bash
cw9 gen-tests gwt-0001 <project>
```

`gen-tests` uses simulation traces as its primary context — each trace's state transitions become test setup, action, and assertion values. Review the generated tests. They should map to the trace patterns identified in the plan.

If `gen-tests` isn't available or the output needs adjustment, write tests manually using the traces:
- Each trace's initial state → test setup (Given)
- Each trace's state transitions → test actions (When)
- Each trace's final state → test assertions (Then)
- Different traces represent different execution paths (happy path, retry, failure, etc.)

### Step 4: Implement Each Step

For each step in the plan, follow Red-Green-Refactor:

#### Red: Confirm Failing Test

- If `gen-tests` produced the test, run it and confirm it fails for the right reason
- If writing manually, follow the plan's test specification
- The test should fail because the implementation doesn't exist yet, not because the test is wrong

#### Green: Write Minimal Code

- Write the minimum code to make the test pass
- Use the bridge artifacts to guide what to build:
  - `data_structures` → define types/models
  - `operations` → implement functions with the specified signatures
  - `verifiers` → add invariant checks
- Use `cw9 show <uuid> --card` to understand functions you're modifying — the IN:DO:OUT contract tells you what inputs, behavior, and outputs to preserve
- Run the test and confirm it passes
- Run the full test suite to check for regressions

#### Refactor

- Improve the code while keeping all tests green
- Run full test suite after refactoring

#### Check Off

- Update the plan: mark the step's success criteria checkboxes with `- [x]`

### Step 5: Re-verify

After all steps are implemented, re-ingest and re-verify:

```bash
# Update crawl.db with your changes
cw9 ingest <path> <project> --incremental
cw9 crawl <project> --incremental

# Check nothing went stale unexpectedly
cw9 stale <project>

# Re-run pipeline to verify the model still holds with updated cards
cw9 pipeline --skip-setup --gwt gwt-0001 <project>
```

If the pipeline fails after your changes:
1. Read the counterexample trace from the output
2. The trace shows a concrete sequence of states that violates an invariant
3. Your implementation has a bug that the formal model caught — fix it
4. Re-run the pipeline

### Step 6: Final Verification

```bash
# Full test suite passes
pytest tests/ -x  # or npm test, cargo test, go test, etc.

# No stale records
cw9 stale <project>

# All GWTs verified
cw9 status <project> --json
```

### Step 7: Beads Wrap-up

- Update beads: `bd update <id> --status=done`
- Close the issue: `bd close <id>`
- Check for unblocked work: `bd blocked`
- Sync: `bd dolt push && bd dolt pull`

## Handling Mismatches

When the plan doesn't match reality:

```
Issue in Step [N]:
Expected: [what the plan says]
Found: [actual situation]
Why this matters: [explanation]

How should I proceed?
```

Do NOT silently deviate from the plan. If the codebase has changed since the plan was written, surface it.

If bridge artifacts don't match what the codebase needs:
- The formal model may need updating — re-run `/cw9_plan` to regenerate
- Or the mismatch reveals something the model didn't capture — surface it to the user

## Guidelines

- **Artifacts drive implementation.** Bridge artifacts tell you what to build. Simulation traces tell you how to test it. The verified spec tells you what invariants must hold. Don't ignore them.
- `cw9 show <uuid> --card` before modifying any function — understand the contract first.
- Re-ingest and re-crawl (`--incremental`) after writing code so crawl.db reflects your changes.
- Run `cw9 stale` periodically — if you changed a function that others depend on, those callers are now stale.
- The `depends_on` UUIDs in each GWT tell you exactly which functions a behavior touches. If you need to change a function NOT in `depends_on`, the plan may need updating.
- If `cw9 pipeline` fails with a TLC counterexample after your implementation, that's a real bug in your code, not a false positive. The formal model was verified before you started — your code introduced the violation.
- The TLA+ `define` block invariants are your strongest guide. Every invariant was proven to hold in the model. If your code violates one, the code is wrong.
