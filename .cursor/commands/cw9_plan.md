# CW9 TDD Plan

Create a TDD implementation plan from CW9 research. Register GWTs, run the verification pipeline to produce formally verified specs and simulation traces, then plan implementation around those artifacts.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan — don't run out of context before writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = path to CW9 research document and/or target project path. If not provided, ask.

## CW9 CLI Reference

```
cw9 show <node-id> <project> --card                      # print IN:DO:OUT card
cw9 gwt-author --research <notes.md> <project>            # research -> GWT JSON
cw9 register <project>                                    # pipe GWT JSON to stdin
cw9 pipeline --skip-setup --gwt <id> <project>            # verify GWT → spec + traces + bridge
cw9 stale <project>                                       # check for outdated records
```

Query crawl.db directly with `sqlite3 <project>/.cw9/crawl.db`.

## Pipeline Artifacts

When `cw9 pipeline` succeeds for a GWT, it produces:

| Artifact | Path | Contains |
|---|---|---|
| Verified TLA+ spec | `.cw9/specs/<gwt-id>.tla` | PlusCal algorithm with invariants, verified by TLC |
| Simulation traces | `.cw9/specs/<gwt-id>_sim_traces.json` | 10 concrete execution paths through the model |
| Bridge artifacts | `.cw9/bridge/<gwt-id>_bridge_artifacts.json` | `data_structures`, `operations`, `verifiers`, `assertions` |

The simulation traces are the **primary input for code generation**. Each trace is a sequence of state transitions that represents a valid execution. The bridge artifacts extract what data structures and operations need to exist in code.

## Process

### Step 1: Read Context

1. **Read the research document FULLY** (no partial reads)
2. **Read the "CW9 Mention Summary"** section — these are the functions/files/dirs that gwt-author will match
3. **Query crawl.db** for the mentioned functions to get their UUIDs and IN:DO:OUT cards:
   ```sql
   SELECT uuid, function_name, file_path, line_number, do_description
   FROM records WHERE function_name IN ('func1', 'func2') AND is_external = FALSE;
   ```
4. **Read relevant source files** at the line numbers shown for functions with SKELETON_ONLY cards
5. **Spawn parallel research**: codebase-analyzer on key files, codebase-pattern-finder for test patterns

### Step 2: Beads Setup

- Run `bd list --status=open` to check for existing tracked issues
- If continuing from `/cw9_research`, find that issue and update: `bd update <id> --status=in_progress`
- If new: `bd create --title="Plan: [feature]" --type=feature --priority=2`

### Step 3: Author and Register GWTs

Run gwt-author against the research document and register immediately:

```bash
cw9 gwt-author --research <research-doc.md> <project> | cw9 register <project>
```

Verify registration:
```bash
cw9 status <project> --json
```

Review the registered GWT IDs (gwt-0001, gwt-0002, etc). Each GWT has:
- `criterion_id` — the behavior identifier
- `given` / `when` / `then` — the behavioral spec
- `depends_on` — list of crawl.db UUIDs this behavior touches

If the GWTs look wrong:
- Check that the research doc mentions functions with `()` syntax
- Check that `depends_on` UUIDs exist: `sqlite3 <project>/.cw9/crawl.db "SELECT uuid, function_name FROM records WHERE uuid IN (...)"`
- Adjust the research doc's mention summary and re-register

### Step 4: Run Pipeline — Verify and Simulate

Run the pipeline for each GWT to produce verified specs and simulation traces:

```bash
cw9 pipeline --skip-setup --gwt gwt-0001 <project>
cw9 pipeline --skip-setup --gwt gwt-0002 <project>
```

The pipeline:
1. Builds a prompt from the GWT + IN:DO:OUT cards of dependent functions
2. LLM writes a PlusCal spec modeling the behavior
3. TLC model-checks the spec against invariants
4. On failure: retries with counterexample feedback (up to 8 attempts)
5. On pass: runs 10 simulation traces and extracts bridge artifacts

**If a GWT fails all 8 attempts**, the GWT may be too broad or contradictory. Consider splitting it or adjusting the research notes.

After pipeline completes, read the artifacts:

```bash
# Check what was produced
ls <project>/.cw9/specs/
ls <project>/.cw9/bridge/

# Read bridge artifacts to understand what the verified model requires
cat <project>/.cw9/bridge/gwt-0001_bridge_artifacts.json | python3 -m json.tool

# Read simulation traces to see concrete execution paths
cat <project>/.cw9/specs/gwt-0001_sim_traces.json | python3 -m json.tool | head -100
```

### Step 5: Plan Implementation from Artifacts

Now that you have verified specs and traces, plan the implementation. The bridge artifacts tell you **what to build**:

- `data_structures` — types/models that need to exist
- `operations` — functions/methods to implement
- `verifiers` — invariant checks the code must satisfy
- `assertions` — specific conditions that must hold

The simulation traces tell you **how it behaves** — concrete state transitions that become test scenarios.

Present the breakdown:
```
Implementation Plan (from verified pipeline artifacts):

gwt-0001: [name]
  Verified spec: .cw9/specs/gwt-0001.tla
  Bridge: N data_structures, M operations, K verifiers

  Testable Behaviors (from simulation traces):
  1. [Trace pattern] — [initial state] → [transitions] → [final state]
     Maps to: [which operation/data_structure]

  2. [Trace pattern] — ...

  Implementation Order:
  1. [data structure / type] — needed by everything else
  2. [core operation] — simplest trace path
  3. [edge case operation] — failure/retry traces
  4. [verifier / assertion] — invariant enforcement

Does this breakdown make sense?
```

Wait for user feedback before writing the plan.

### Step 6: Write Plan

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-tdd-description.md`

Or for multi-component plans, create a directory:
`thoughts/searchable/shared/plans/YYYY-MM-DD-tdd-description/`

Use this structure:

````markdown
---
date: [ISO timestamp]
researcher: [name]
git_commit: [hash]
branch: [branch]
repository: [repo]
topic: "[feature] TDD Plan"
tags: [plan, tdd, cw9, relevant-tags]
status: draft
last_updated: [YYYY-MM-DD]
last_updated_by: [name]
cw9_project: [target project path]
research_doc: [path to research document]
---

# [Feature] TDD Implementation Plan

## Overview
[Brief description — what we're building and why]

## Research Reference
- Research doc: `thoughts/searchable/shared/research/YYYY-MM-DD-description.md`
- CW9 project: `<project path>`
- crawl.db records: [count] functions across [count] files

## Verified Specs and Traces

### gwt-0001: [name]
- **Given**: [context]
- **When**: [action]
- **Then**: [result]
- **depends_on**: `uuid1` (functionA @ file.ext:line), `uuid2` (functionB @ file.ext:line)
- **Verified spec**: `.cw9/specs/gwt-0001.tla`
- **Simulation traces**: `.cw9/specs/gwt-0001_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0001_bridge_artifacts.json`
  - data_structures: [count] — [list names]
  - operations: [count] — [list names]
  - verifiers: [count] — [list names]
  - assertions: [count]

### gwt-0002: [name]
[...]

## What We're NOT Doing
[Out-of-scope items]

## Step 1: [Data Structure / Type Name]

### CW9 Binding
- **GWT**: gwt-NNNN
- **Bridge artifact**: `data_structures[N]`
- **depends_on UUIDs**:
  - `uuid` — functionName @ file.ext:line

### Test Specification
**Given**: [Initial state — from simulation trace initial state]
**When**: [Action — from trace transitions]
**Then**: [Expected result — from trace final state]
**Edge Cases**: [from alternative traces]

### TDD Cycle

#### Red: Write Failing Test
**File**: `path/to/test/file.test.ext`
```language
// test derived from simulation trace
```

#### Green: Minimal Implementation
**File**: `path/to/impl/file.ext`
```language
// minimal code to pass — guided by bridge operation
```

#### Refactor
```language
// improved code
```

### Success Criteria
**Automated:**
- [ ] Test fails for right reason (Red)
- [ ] Test passes (Green)
- [ ] All tests pass after refactor

---

## Step 2: [Operation Name]
[Same structure — each step maps to a bridge operation or verifier]

## Integration Testing
[Cross-behavior verification using multi-step simulation traces]

## Verification
After implementation, re-verify:
```bash
cw9 ingest <path> <project> --incremental
cw9 stale <project>
cw9 pipeline --skip-setup --gwt gwt-0001 <project>
```

## References
- Research: `thoughts/searchable/shared/research/YYYY-MM-DD-description.md`
- Verified specs: `.cw9/specs/`
- Bridge artifacts: `.cw9/bridge/`
- Beads: `bd show <id>`
````

### Step 7: Beads and Review

1. Update beads: `bd update <id> --status=review`
2. Present the plan location and ask for review:
   - Pipeline ran successfully for all GWTs?
   - Simulation traces cover the right scenarios?
   - Bridge artifacts correctly mapped to implementation steps?
   - TDD cycles clear?
   - Missing behaviors or edge cases?
3. Iterate based on feedback

## Guidelines

- **Pipeline runs during planning, not implementation.** The verified spec and traces guide what code to write. Don't plan blindly — let the formal model tell you what's needed.
- The bridge artifacts' `data_structures` and `operations` map directly to implementation steps. Each step should correspond to one or more bridge artifacts.
- Simulation traces are concrete test scenarios. Each trace's state transitions become Given/When/Then assertions.
- `cw9 show <uuid> --card` is your friend — use it to understand what a function does before planning changes to it.
- Keep the plan interactive. Get buy-in on the artifact breakdown (Step 5) before writing details (Step 6).
- The plan should be implementable by `/cw9_implement` without needing to re-run the pipeline.
