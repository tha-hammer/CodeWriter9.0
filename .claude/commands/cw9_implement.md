# CW9 Implement (Self-Hosting)

Implement an approved CW9 TDD plan using verified specs, simulation traces, and bridge artifacts. This is the self-hosting variant — you're modifying CW9's own code in `python/registry/`.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for implementation — don't run out of context before writing code.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, ask.

## Self-Hosting Artifact Paths

| Artifact | Path |
|---|---|
| Verified specs | `templates/pluscal/instances/<gwt-id>.tla` |
| Simulation traces | `templates/pluscal/instances/<gwt-id>_sim_traces.json` |
| Bridge artifacts | `python/tests/generated/<gwt-id>_bridge_artifacts.json` |
| Generated tests | `python/tests/generated/test_<gwt-id>.py` |
| Context files | `.cw9/context/<gwt-id>.md` |
| Source code | `python/registry/` |
| Test suite | `python/tests/` |
| Self-hosting DAG | `dag.json` (repo root) |

## CW9 CLI Reference (Self-Hosting)

```
cw9 loop <gwt-id> . --context-file .cw9/context/<gwt-id>.md   # re-verify a GWT
cw9 bridge <spec-path> --gwt <gwt-id> .                       # re-extract bridge
cw9 gen-tests <gwt-id> .                                      # generate tests from traces
cw9 show <node-id> . --card                                   # print IN:DO:OUT card
cw9 stale .                                                   # check for outdated records
cw9 ingest python/registry . --incremental                    # re-scan after code changes
cw9 crawl . --incremental                                     # re-extract after code changes
```

## Process

### Step 1: Read Plan and Artifacts

1. **Read the plan completely** — check for existing checkmarks (`- [x]`)
2. **Read the research document** referenced in the plan
3. **Read bridge artifacts** for each GWT:
   ```bash
   cat python/tests/generated/gwt-NNNN_bridge_artifacts.json | python3 -m json.tool
   ```
   The bridge tells you what to build:
   - `data_structures` → types, models, state shapes → define in `python/registry/`
   - `operations` → functions/methods with signatures
   - `verifiers` → invariant checks that must hold
   - `assertions` → specific conditions from the formal model

4. **Read simulation traces** for each GWT:
   ```bash
   cat templates/pluscal/instances/gwt-NNNN_sim_traces.json | python3 -m json.tool | head -200
   ```
   Variable assignments at each state become concrete test values.

5. **Read the verified TLA+ spec** for invariants:
   ```bash
   cat templates/pluscal/instances/gwt-NNNN.tla
   ```
   The `define` block invariants are formally verified — they represent real constraints.

6. If there are existing checkmarks, trust completed work and pick up from the first unchecked item

### Step 2: Beads Setup

- Run `bd list --status=open` to find the tracked issue
- Update status: `bd update <id> --status=in_progress`
- If no issue exists: `bd create --title="Implement: [feature]" --type=task --priority=2`

### Step 3: Generate Tests from Traces

For each GWT, generate test scaffolds:

```bash
cw9 gen-tests gwt-NNNN .
```

Generated tests land at `python/tests/generated/test_gwt_NNNN.py`.

Review the generated tests — they should:
- Import from `registry.*` (not absolute paths)
- Use correct constructor signatures (match `python/registry/` source)
- Have assertions derived from simulation trace final states

If `gen-tests` output needs adjustment, fix scaffolding issues (wrong imports, field names) but **never weaken assertions** — those come from the verified spec.

### Step 4: Implement Each Step

For each step in the plan, follow Red-Green-Refactor:

#### Red: Confirm Failing Test

```bash
cd python && python3 -m pytest tests/generated/test_gwt_NNNN.py -x -v
```

The test should fail because the implementation doesn't exist yet, not because the test is wrong.

#### Green: Write Minimal Code

- Write minimal code in `python/registry/` to make the test pass
- Use bridge artifacts to guide what to build
- Read existing source files before modifying — understand the contract first
- Run the test:
  ```bash
  cd python && python3 -m pytest tests/generated/test_gwt_NNNN.py -x -v
  ```

#### Check for Regressions

After each green step, run the FULL test suite:

```bash
cd python && python3 -m pytest tests/ -x
```

This catches cases where your new code breaks existing verified behavior (gwt-0001..0063).

#### Refactor

- Improve code while keeping all tests green
- Run full suite again after refactoring

#### Check Off

- Update the plan: mark the step's success criteria checkboxes with `- [x]`

### Step 5: Final Verification

```bash
# Full test suite passes (2857+ tests)
cd python && python3 -m pytest tests/ -x

# Optional: re-verify the formal model still holds with updated code
cw9 ingest python/registry . --incremental
cw9 stale .
```

If `cw9 stale` shows stale records for functions you changed:
1. The functions you modified are depended on by other GWTs
2. This may require re-running `cw9 loop` for those GWTs
3. Surface this to the user — it's a scope expansion

### Step 6: Beads Wrap-up

- Close the issue: `bd close <id>`
- Check for unblocked work: `bd blocked`

## Handling Mismatches

When the plan doesn't match reality:

```
Issue in Step [N]:
Expected: [what the plan says]
Found: [actual situation]
Why this matters: [explanation]

How should I proceed?
```

Do NOT silently deviate from the plan. Common self-hosting mismatches:

- **Path references**: Plan says `.cw9/specs/` but self-hosting uses `templates/pluscal/instances/` — cosmetic, the CLI routes correctly
- **Import paths**: Generated test imports don't match actual module structure — scaffolding fix, update the test
- **Existing behavior conflict**: New code breaks existing GWT tests — this is a real issue, the new code must conform to existing specs
- **Constructor signature**: Bridge artifact says one signature, real code has another — check which is current, fix the test scaffolding

## Guidelines

- **Artifacts drive implementation.** Bridge = what to build. Traces = how to test. Spec = invariants that must hold.
- **Test command is always `cd python && python3 -m pytest tests/ -x`** for the full suite.
- **Existing GWTs are sacrosanct.** 63 GWTs and 2857 tests define existing behavior. Your new code must not break them.
- **Scaffolding fixes OK, spec-weakening NOT OK.** Wrong imports = fix the test. Wrong assertions from the spec = fix the code.
- **Commit checkpoints.** Commit after each logical group of steps passes. Work only in a context window is one crash from lost.
- The `define` block invariants in the TLA+ spec are your strongest guide. Every invariant was proven to hold in the model.
