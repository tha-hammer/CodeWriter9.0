# CW9 TDD Plan (Self-Hosting)

Create a TDD implementation plan for CW9's own pipeline. This is the self-hosting variant — CW9 building itself.

## OUTPUT

**This command produces a PLAN DOCUMENT, not code.** You will:
1. Register GWT behaviors
2. Write context files
3. Run the verification pipeline (TLC model checking)
4. Write a plan document from the verified artifacts

**You do NOT write implementation code. You do NOT write tests. You do NOT modify `python/registry/`.** The plan document is the deliverable. Implementation happens later via `/cw9_implement`.

## Subagent Strategy

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan — don't run out of context before writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = path to CW9 research document. If not provided, ask.

## Self-Hosting Artifact Paths

The CLI routes automatically via `ProjectContext.self_hosting()`. When you pass `.` as the target:

| Artifact | Path |
|---|---|
| Verified specs | `templates/pluscal/instances/<gwt-id>.tla` |
| Spec configs | `templates/pluscal/instances/<gwt-id>.cfg` |
| Simulation traces | `templates/pluscal/instances/<gwt-id>_sim_traces.json` |
| Bridge artifacts | `python/tests/generated/<gwt-id>_bridge_artifacts.json` |
| Generated tests | `python/tests/generated/test_<gwt-id>.py` |
| Context files | `.cw9/context/<gwt-id>.md` |
| Self-hosting DAG | `dag.json` (repo root) |
| Schema files | `schema/` |
| Sessions | `sessions/` |

**GWT ID namespace**: gwt-0001..0063 allocated. Next available: **gwt-0064+**. Check `dag.json` for the actual latest.

## CW9 CLI Reference (Self-Hosting)

All commands use `.` as the target directory for self-hosting:

```
cw9 show <node-id> . --card                          # print IN:DO:OUT card
cw9 gwt-author --research <notes.md> .                # research -> GWT JSON
cw9 register .                                        # pipe GWT JSON to stdin
cw9 loop <gwt-id> . --context-file .cw9/context/<gwt-id>.md  # verify one GWT
cw9 bridge <spec-path> --gwt <gwt-id> .               # extract bridge artifacts
cw9 gen-tests <gwt-id> .                              # generate tests from traces
cw9 status . --json                                   # pipeline status
cw9 loop-status .                                     # live progress of running loops
cw9 loop-status . --json                              # machine-readable loop progress
```

---

## Phase A: Gather Context (Steps 1-2)

### Step 1: Read Context

1. **Read the research document FULLY** (no partial reads)
2. **Read the "CW9 Mention Summary"** section — these are the functions/files/dirs that gwt-author will match
3. **Check existing coverage**: read relevant context files in `.cw9/context/` and specs in `templates/pluscal/instances/` for existing GWTs that touch the same area
4. **Read relevant source files** in `python/registry/`
5. **Spawn parallel research**: codebase-analyzer on key files, codebase-pattern-finder for test patterns

### Step 2: Beads Setup

- Run `bd list --status=open` to check for existing tracked issues
- If continuing from `/cw9_research`, find that issue and update: `bd update <id> --status=in_progress`
- If new: `bd create --title="Plan: [feature]" --type=feature --priority=2`

---

## Phase B: Register and Prepare (Steps 3-4)

### Step 3: Author and Register GWTs

Run gwt-author against the research document and register:

```bash
cw9 gwt-author --research <research-doc.md> . | cw9 register .
```

Verify registration:
```bash
cw9 status . --json
```

Check the assigned GWT IDs — they should be gwt-0064+ (or whatever's next in `dag.json`). If IDs collide with existing allocations, something went wrong.

Review each registered GWT's:
- `criterion_id` — the behavior identifier
- `given` / `when` / `then` — the behavioral spec
- `depends_on` — list of crawl.db UUIDs this behavior touches

### Step 4: Write Context Files (MANDATORY — DO NOT SKIP)

For each registered GWT, write a context file at `.cw9/context/<gwt-id>.md`. Without a Test Interface section, `cw9 gen-tests` hallucinates wrong API ~60% of the time.

Use existing context files as reference — there are 63 of them in `.cw9/context/`.

```markdown
# Context for <gwt-id>: <behavior_name>

## Behavior
Given ..., when ..., then ...

## Concrete Data Shapes
<Full dataclass definitions from python/registry/ with field types and defaults>

## Key Invariants to Model
- InvariantName: description

## Modeling Approach
- CONSTANTS, Variables, Actions, Invariants

## Test Interface (MANDATORY)
\```python
from registry.module_name import ClassName, function_name

# Constructor with actual args
obj = ClassName(arg1="value", arg2=42)

# Method call with actual return type
result = obj.method_name(input_data)

# Attribute access with actual field names
assert result.field_name == expected_value
\```

## Anti-Patterns (DO NOT USE)
- `obj["field"]` -- WRONG if obj is a dataclass (use obj.field)
- `from registry.wrong_module import ...` -- check actual module name
- Constructor args that don't match the real __init__ signature
```

**CHECKPOINT: Before proceeding to Phase C, verify:**
- [ ] All GWTs registered (check `cw9 status . --json`)
- [ ] Context file exists for every registered GWT
- [ ] Every context file has a `## Test Interface` section
- [ ] Test Interface imports match actual module paths in `python/registry/`

**If any checkpoint fails, fix it before proceeding. Do NOT skip ahead.**

---

## Phase C: Run Verification Pipeline (Step 5)

**This is the core of the planning process.** The pipeline produces the artifacts that drive the plan.

### Step 5: Run Pipeline — Verify and Simulate

Run the pipeline for each GWT. **Max 3-4 concurrent processes** — more exhausts /tmp and causes silent Java failures.

```bash
cw9 loop gwt-0064 . --context-file .cw9/context/gwt-0064.md
cw9 loop gwt-0065 . --context-file .cw9/context/gwt-0065.md
```

The pipeline:
1. Builds a prompt from the GWT + IN:DO:OUT cards of dependent functions
2. LLM writes a PlusCal spec modeling the behavior
3. TLC model-checks the spec against invariants
4. On failure: retries with counterexample feedback (up to 8 attempts)
5. On pass: produces verified spec + simulation traces

**Monitor progress** while loops run (instead of ad-hoc file checking):

```bash
cw9 loop-status .          # human-readable summary
cw9 loop-status . --json   # machine-readable for scripting
```

This shows attempt count, current phase (llm_call, compiling, tlc_done, sim_traces), elapsed time, and whether the process is still alive. **Do NOT use strace, sleep loops, or manual file polling** — use `cw9 loop-status`.

After pipeline completes, check the self-hosting artifact locations:

```bash
# Verified specs
ls templates/pluscal/instances/gwt-0064.tla

# Simulation traces
ls templates/pluscal/instances/gwt-0064_sim_traces.json
```

Then extract bridge artifacts and check them:

```bash
cw9 bridge templates/pluscal/instances/gwt-0064.tla --gwt gwt-0064 .

# Bridge artifacts land here for self-hosting:
cat python/tests/generated/gwt-0064_bridge_artifacts.json | python3 -m json.tool
```

**If a GWT fails all 8 attempts**, the GWT may be too broad or contradictory. Consider splitting it or adjusting the context file's modeling approach.

**CHECKPOINT: Before proceeding to Phase D, verify:**
- [ ] Every GWT has a verified spec at `templates/pluscal/instances/<gwt-id>.tla`
- [ ] Every GWT has simulation traces at `templates/pluscal/instances/<gwt-id>_sim_traces.json`
- [ ] Every GWT has bridge artifacts at `python/tests/generated/<gwt-id>_bridge_artifacts.json`

**If any artifact is missing, the pipeline failed for that GWT. Fix it before writing the plan.**

---

## Phase D: Write the Plan Document (Steps 6-8)

**Reminder: You are writing a PLAN DOCUMENT. Do not write code or tests.**

### Step 6: Present Artifact Breakdown to User

Read the bridge artifacts and simulation traces. Present a summary to the user:

```
Verified Pipeline Artifacts:

gwt-0064: [name]
  Verified spec: templates/pluscal/instances/gwt-0064.tla
  Bridge: python/tests/generated/gwt-0064_bridge_artifacts.json
  N data_structures, M operations, K verifiers

  Testable Behaviors (from simulation traces):
  1. [Trace pattern] — [initial state] → [transitions] → [final state]
     Maps to: [which operation/data_structure]

  Suggested Implementation Order:
  1. [data structure / type] — needed by everything else
  2. [core operation] — simplest trace path
  3. [edge case operation] — failure/retry traces
  4. [verifier / assertion] — invariant enforcement

Does this breakdown make sense?
```

**Wait for user feedback before writing the plan.**

### Step 7: Write Plan Document

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-tdd-description.md`

````markdown
---
date: [ISO timestamp]
researcher: [name]
git_commit: [hash]
branch: [branch]
repository: CodeWriter9.0
topic: "[feature] TDD Plan"
tags: [plan, tdd, cw9, self-hosting, relevant-tags]
status: draft
last_updated: [YYYY-MM-DD]
last_updated_by: [name]
research_doc: [path to research document]
---

# [Feature] TDD Implementation Plan

## Overview
[Brief description — what we're building and why]

## Research Reference
- Research doc: `thoughts/searchable/shared/research/YYYY-MM-DD-description.md`
- GWT ID range: gwt-NNNN..gwt-NNNN

## Verified Specs and Traces

### gwt-NNNN: [name]
- **Given**: [context]
- **When**: [action]
- **Then**: [result]
- **Verified spec**: `templates/pluscal/instances/gwt-NNNN.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-NNNN_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-NNNN_bridge_artifacts.json`
  - data_structures: [count] — [list names]
  - operations: [count] — [list names]
  - verifiers: [count] — [list names]
  - assertions: [count]

## What We're NOT Doing
[Out-of-scope items]

## Implementation Steps

### Step 1: [Data Structure / Type Name]

**CW9 Binding:**
- GWT: gwt-NNNN
- Bridge artifact: `data_structures[N]`

**Test Specification (from simulation traces):**
- Given: [from trace initial state]
- When: [from trace transitions]
- Then: [from trace final state]
- Edge cases: [from alternative traces]

**Target files:**
- Test: `python/tests/generated/test_gwt_NNNN.py`
- Implementation: `python/registry/module.py`

**Success Criteria:**
- [ ] Test fails for right reason (Red)
- [ ] Test passes (Green)
- [ ] `cd python && python3 -m pytest tests/ -x` — all tests pass after refactor

---

### Step 2: [Next component]
[Same structure]

## Integration Testing
[Cross-behavior verification]

## Verification
After implementation, run full suite:
```bash
cd python && python3 -m pytest tests/ -x
```

## References
- Research: `thoughts/searchable/shared/research/...`
- Verified specs: `templates/pluscal/instances/`
- Bridge artifacts: `python/tests/generated/`
````

### Step 8: Beads and Review

1. Update beads: `bd update <id> --status=review`
2. Present the plan location and ask for review:
   - Pipeline ran successfully for all GWTs?
   - Simulation traces cover the right scenarios?
   - Bridge artifacts correctly mapped to implementation steps?
   - Implementation steps clear?
   - Missing behaviors or edge cases?
3. Iterate based on feedback
4. Tell the user: **run `/cw9_implement <plan-path>` to begin implementation**

---

## Guidelines

- **This command produces a plan, not code.** If you find yourself writing implementation code or test code, STOP. That's `/cw9_implement`'s job.
- **Pipeline runs during planning, not implementation.** The verified spec and traces guide what code to write.
- **Check existing GWTs.** Your new feature may interact with the 63 existing verified behaviors. Read relevant context files.
- **Self-hosting test command**: `cd python && python3 -m pytest tests/ -x`
- Bridge artifacts' `data_structures` and `operations` map directly to implementation steps.
- Simulation traces are concrete test scenarios — state transitions become Given/When/Then.
- Keep the plan interactive. Get buy-in on the artifact breakdown (Step 6) before writing details (Step 7).
- The plan should be implementable by `/cw9_implement` without needing to re-run the pipeline.
- **Max 3-4 concurrent `cw9 loop` processes.** More exhausts /tmp.
- **DAG is not safe for concurrent writes.** Only one `cw9 register` at a time.
