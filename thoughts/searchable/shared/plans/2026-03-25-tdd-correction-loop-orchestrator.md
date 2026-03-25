---
date: 2026-03-25T00:00:00Z
researcher: FuchsiaRaven
git_commit: bfdf819
branch: master
repository: CodeWriter9.0
topic: "Correction Loop Orchestrator TDD Plan"
tags: [plan, tdd, cw9, orchestrator, correction-loop, iterative-review]
status: draft
last_updated: 2026-03-25
last_updated_by: FuchsiaRaven
cw9_project: /home/maceo/Dev/CodeWriter9.0
research_doc: thoughts/searchable/shared/research/2026-03-25-correction-loop-orchestrator.md
---

# Correction Loop Orchestrator TDD Implementation Plan

## Overview

Add an iterative correction loop to the `cw9 plan-review` orchestrator. Currently, the orchestrator runs all review passes once and aggregates verdicts. The correction loop adds: per-pass retry with bounded retries, automatic correction agent dispatch on failure, dependency-based gating between passes, and structured finding extraction. Activated via `--auto-fix` flag (backward-compatible: off by default).

## Research Reference

- Research doc: `thoughts/searchable/shared/research/2026-03-25-correction-loop-orchestrator.md`
- CW9 project: `/home/maceo/Dev/CodeWriter9.0`
- Target file: `python/registry/cli.py` (lines 2099-2400)
- Beads: `bd show cosmic-hr-d1ij`

## Verified Specs and Traces

### Verification Summary

| GWT Range | Group | Status | Specs | Bridge |
|---|---|---|---|---|
| gwt-0080..0081 | Phase selection & aggregation (pre-existing) | Verified | 2 | 2 |
| gwt-0082..0083 | CLI dispatch routing | Verified | 2 | 2 |
| gwt-0084..0085 | Initialization & arg parsing | Verified | 2 | 2 |
| gwt-0086..0087 | Review pass in auto-fix mode | Verified | 2 | 2 |
| gwt-0088..0089 | PASS/WARNING verdict handling | Verified | 2 | 2 |
| gwt-0090..0092 | Retry loop core (FAIL, correction, exhaustion) | Verified | 3 | 3 |
| gwt-0093..0097 | Dependency gating & cascade blocking | Verified | 5 | 5 |
| gwt-0098 | Aggregation with blocked verdicts | Verified | 1 | 1 |
| gwt-0099..0101 | Correction agent configuration & scope | Verified | 3 | 3 |
| gwt-0102..0104 | Manifest tracking & cost breakdown | **Failed** | 0 | 0 |

**22 of 25 GWTs verified.** The 3 failures (manifest I/O, cost aggregation) are mechanical bookkeeping — implementable with hand-written tests per CLAUDE.md exemption for "bug fixes where the fix is mechanical."

### Detailed GWT Bindings

#### gwt-0082: CLI dispatch (no --auto-fix)
- **Given**: `cw9 plan-review <plan>` invoked without `--auto-fix`
- **When**: `cmd_plan_review()` dispatches to orchestration
- **Then**: `_orchestrate_reviews()` called (not `_orchestrate_reviews_with_correction()`); backward compatible
- **Verified spec**: `templates/pluscal/instances/gwt-0082.tla`
- **Sim traces**: `templates/pluscal/instances/gwt-0082_sim_traces.json`
- **Bridge**: `python/tests/generated/gwt-0082_bridge_artifacts.json` — 1ds, 5ops, 9ver

#### gwt-0083: CLI dispatch (with --auto-fix)
- **Given**: `cw9 plan-review <plan>` invoked with `--auto-fix`
- **When**: `cmd_plan_review()` parses CLI arguments
- **Then**: `_orchestrate_reviews_with_correction()` called instead
- **Verified spec**: `templates/pluscal/instances/gwt-0083.tla`
- **Bridge**: `python/tests/generated/gwt-0083_bridge_artifacts.json` — 1ds, 5ops, 7ver

#### gwt-0084: Default max_retries
- **Given**: `--auto-fix` set, `--max-retries` not provided
- **When**: Correction loop initializes retry budget
- **Then**: `max_retries=2` (3 total attempts per pass)
- **Verified spec**: `templates/pluscal/instances/gwt-0084.tla`
- **Bridge**: `python/tests/generated/gwt-0084_bridge_artifacts.json` — 1ds, 4ops, 8ver

#### gwt-0085: Custom max_retries
- **Given**: `--auto-fix` set, `--max-retries N` provided
- **When**: CLI parses arguments
- **Then**: `max_retries=N`; 0 means single pass; negative rejected
- **Verified spec**: `templates/pluscal/instances/gwt-0085.tla`
- **Bridge**: `python/tests/generated/gwt-0085_bridge_artifacts.json` — 1ds, 7ops, 7ver

#### gwt-0086: Auto-fix forces JSON mode
- **Given**: `--auto-fix` active, review pass executing
- **When**: `_run_review_pass()` constructs `query()` call
- **Then**: `json_mode=True` forced, streaming disabled
- **Verified spec**: `templates/pluscal/instances/gwt-0086.tla`
- **Bridge**: `python/tests/generated/gwt-0086_bridge_artifacts.json` — 1ds, 6ops, 7ver

#### gwt-0087: Finding extraction
- **Given**: Review pass completed with `json_mode=True` in auto-fix
- **When**: `_extract_findings()` called with result text
- **Then**: Returns structured findings; returns empty on parse failure
- **Verified spec**: `templates/pluscal/instances/gwt-0087.tla`
- **Bridge**: `python/tests/generated/gwt-0087_bridge_artifacts.json` — 1ds, 3ops, 7ver

#### gwt-0088: PASS breaks retry loop
- **Given**: `--auto-fix` active, review returns PASS
- **When**: Orchestration loop evaluates verdict
- **Then**: No correction agent; pass recorded; next eligible pass scheduled
- **Verified spec**: `templates/pluscal/instances/gwt-0088.tla`
- **Bridge**: `python/tests/generated/gwt-0088_bridge_artifacts.json` — 1ds, 6ops, 8ver

#### gwt-0089: WARNING breaks retry loop (non-blocking)
- **Given**: `--auto-fix` active, review returns WARNING
- **When**: Orchestration loop evaluates verdict
- **Then**: No correction; WARNING treated as non-blocking; dependents proceed
- **Verified spec**: `templates/pluscal/instances/gwt-0089.tla`
- **Bridge**: `python/tests/generated/gwt-0089_bridge_artifacts.json` — 1ds, 4ops, 8ver

#### gwt-0090: FAIL triggers correction
- **Given**: FAIL verdict, attempt < max_retries
- **When**: `_run_review_pass()` returns FAIL
- **Then**: `_run_correction_pass()` invoked with findings; agent spawned; review re-run
- **Verified spec**: `templates/pluscal/instances/gwt-0090.tla`
- **Bridge**: `python/tests/generated/gwt-0090_bridge_artifacts.json` — 1ds, 7ops, 11ver

#### gwt-0091: Re-review after correction
- **Given**: Correction agent completed
- **When**: `_run_correction_pass()` returns
- **Then**: Same review re-run; attempt counter increments; new verdict/cost tracked
- **Verified spec**: `templates/pluscal/instances/gwt-0091.tla`
- **Bridge**: `python/tests/generated/gwt-0091_bridge_artifacts.json` — 1ds, 2ops, 12ver

#### gwt-0092: Retries exhausted = permanent FAIL
- **Given**: FAIL verdict, attempt == max_retries
- **When**: Inner retry loop exits
- **Then**: Permanently failed; no more correction agents; dependents blocked; summary has `stuck_on` and findings
- **Verified spec**: `templates/pluscal/instances/gwt-0092.tla`
- **Bridge**: `python/tests/generated/gwt-0092_bridge_artifacts.json` — 1ds, 7ops, 8ver

#### gwt-0093: Failed pass blocks dependents (transitive)
- **Given**: Pass permanently FAIL or blocked
- **When**: `_check_dependencies()` evaluated for dependents
- **Then**: Dependents skipped, marked "blocked"; transitive cascade
- **Verified spec**: `templates/pluscal/instances/gwt-0093.tla`
- **Bridge**: `python/tests/generated/gwt-0093_bridge_artifacts.json` — 1ds, 2ops, 8ver

#### gwt-0094: Artifacts failure blocks everything
- **Given**: Artifacts exhausted retries, terminal FAIL
- **When**: Orchestrator tries to schedule downstream passes
- **Then**: coverage, interaction, abstraction_gap, imports all blocked; `stuck_on: "artifacts"`
- **Verified spec**: `templates/pluscal/instances/gwt-0094.tla`
- **Bridge**: `python/tests/generated/gwt-0094_bridge_artifacts.json` — 1ds, 9ops, 6ver

#### gwt-0095: Parallel dispatch after artifacts pass
- **Given**: Artifacts PASS/WARNING, `--auto-fix` active
- **When**: Orchestrator schedules next phase
- **Then**: coverage + interaction dispatched concurrently; independent retry budgets
- **Verified spec**: `templates/pluscal/instances/gwt-0095.tla`
- **Bridge**: `python/tests/generated/gwt-0095_bridge_artifacts.json` — 1ds, 16ops, 9ver

#### gwt-0096: Abstraction gap gating
- **Given**: coverage and interaction both at terminal verdicts
- **When**: `_check_dependencies()` evaluates abstraction_gap
- **Then**: Scheduled only if both PASS/WARNING; otherwise blocked
- **Verified spec**: `templates/pluscal/instances/gwt-0096.tla`
- **Bridge**: `python/tests/generated/gwt-0096_bridge_artifacts.json` — 1ds, 2ops, 7ver

#### gwt-0097: Imports gating
- **Given**: abstraction_gap at terminal verdict
- **When**: `_check_dependencies()` evaluates imports
- **Then**: Scheduled only if abstraction_gap PASS/WARNING; otherwise blocked
- **Verified spec**: `templates/pluscal/instances/gwt-0097.tla`
- **Bridge**: `python/tests/generated/gwt-0097_bridge_artifacts.json` — 1ds, 3ops, 10ver

#### gwt-0098: Aggregation with blocked verdicts
- **Given**: All passes at terminal verdicts, one+ blocked
- **When**: `_aggregate_verdicts()` called
- **Then**: Overall=fail; three buckets (passed/failed/blocked); blocked doesn't generate new `stuck_on`
- **Verified spec**: `templates/pluscal/instances/gwt-0098.tla`
- **Bridge**: `python/tests/generated/gwt-0098_bridge_artifacts.json` — 1ds, 4ops, 14ver

#### gwt-0099: Correction agent fresh context
- **Given**: Correction agent being spawned
- **When**: `_run_correction_pass()` constructs `query()` call
- **Then**: `resume` NOT set; clean context with findings + report path
- **Verified spec**: `templates/pluscal/instances/gwt-0099.tla`
- **Bridge**: `python/tests/generated/gwt-0099_bridge_artifacts.json` — 1ds, 5ops, 7ver

#### gwt-0100: Correction agent options
- **Given**: Correction agent constructed
- **When**: `ClaudeAgentOptions` assembled
- **Then**: `allowed_tools=["Read","Grep","Glob","Bash","Edit","Write"]`; `max_turns=20`; `model="claude-sonnet-4-6"`
- **Verified spec**: `templates/pluscal/instances/gwt-0100.tla`
- **Bridge**: `python/tests/generated/gwt-0100_bridge_artifacts.json` — 1ds, 3ops, 9ver

#### gwt-0101: Correction agent scope constraints
- **Given**: Correction agent executing against `cw9_plan_fix.md`
- **When**: Agent decides modifications
- **Then**: Only context files, plan text, test scaffolding; NOT source/specs/bridge
- **Verified spec**: `templates/pluscal/instances/gwt-0101.tla`
- **Bridge**: `python/tests/generated/gwt-0101_bridge_artifacts.json` — 1ds, 5ops, 12ver

## What We're NOT Doing

- **No `cw9 plan-fix` separate command** — correction is integrated into the orchestrator
- **No structured output from review passes** — we parse findings from result text instead
- **No `--max-cost` flag** — cost tracking is in the summary but not gated
- **No modification to existing `_orchestrate_reviews()`** — it stays as-is for backward compat
- **No gwt-0102..0104** — manifest tracking and cost breakdown implemented as mechanical code with hand-written tests

## Implementation Steps

### Step 1: `PASS_DEPENDENCIES` constant + `_check_dependencies()` helper

**CW9 Binding:**
- GWTs: gwt-0093, gwt-0094, gwt-0096, gwt-0097
- Bridge artifacts: `gwt-0093_bridge_artifacts.json`, `gwt-0094_bridge_artifacts.json`, `gwt-0096_bridge_artifacts.json`, `gwt-0097_bridge_artifacts.json`

**What to build:**
```python
PASS_DEPENDENCIES = {
    "artifacts": [],
    "coverage": ["artifacts"],
    "interaction": ["artifacts"],
    "abstraction_gap": ["coverage", "interaction"],
    "imports": ["abstraction_gap"],
}

def _check_dependencies(pass_name: str, results: dict[str, dict], dependencies: dict = PASS_DEPENDENCIES) -> bool:
    """Return True if all dependencies for pass_name have PASS or WARNING verdicts."""
```

**Test Specification (from simulation traces):**
- artifacts has no deps → always True
- coverage dep on artifacts: PASS/WARNING → True; FAIL/blocked → False
- abstraction_gap dep on both coverage+interaction: both PASS → True; either FAIL → False
- imports dep on abstraction_gap: blocked cascades from upstream
- Transitive: artifacts FAIL → coverage blocked → abstraction_gap blocked → imports blocked

**Target files:**
- Test: `python/tests/generated/test_gwt_0093.py` (+ 0094, 0096, 0097)
- Implementation: `python/registry/cli.py` (new function near line 2144)

**Success Criteria:**
- [ ] Tests fail for right reason (Red)
- [ ] `_check_dependencies` passes all gate scenarios (Green)
- [ ] All existing tests still pass

---

### Step 2: `_extract_findings()` — structured finding parser

**CW9 Binding:**
- GWT: gwt-0087
- Bridge artifact: `gwt-0087_bridge_artifacts.json`

**What to build:**
```python
def _extract_findings(result_text: str) -> dict:
    """Extract structured findings from review result text.
    Returns: {"pass_name": str, "issues": list[dict], "report_path": str}
    Returns empty findings dict on parse failure (no raise).
    """
```

**Test Specification (from simulation traces):**
- Valid result text with issues → structured findings with pass_name, issues list, report_path
- Empty result text → empty findings (no exception)
- Malformed/unparseable text → empty findings (graceful degradation)
- Issues list items contain type (uncovered_verifier, dead_import, etc.) and details

**Target files:**
- Test: `python/tests/generated/test_gwt_0087.py`
- Implementation: `python/registry/cli.py` (new function near line 2142)

**Success Criteria:**
- [ ] Tests fail for right reason (Red)
- [ ] Extraction works for all review types (Green)
- [ ] Graceful degradation on bad input

---

### Step 3: `_run_correction_pass()` — correction agent spawner

**CW9 Binding:**
- GWTs: gwt-0099, gwt-0100, gwt-0101
- Bridge artifacts: `gwt-0099_bridge_artifacts.json`, `gwt-0100_bridge_artifacts.json`, `gwt-0101_bridge_artifacts.json`

**What to build:**
```python
async def _run_correction_pass(
    pass_name: str,
    findings: dict,
    plan_path: str,
    cwd: str,
    correction_prompt_file: str = ".claude/commands/cw9_plan_fix.md",
) -> dict:
    """Spawn a correction agent for a failed review pass.
    Returns: {"name": pass_name, "cost_usd": float, "session_id": str}
    """
```

**Key constraints (from gwt-0099..0101):**
- Fresh context: NO `resume=session_id` from review
- `ClaudeAgentOptions`: allowed_tools=["Read","Grep","Glob","Bash","Edit","Write"], max_turns=20, model="claude-sonnet-4-6"
- Agent reads on-disk report file (not inline conversation text)
- Scope: only context files, plan text, test scaffolding — NOT source code, specs, or bridge artifacts

**Target files:**
- Test: `python/tests/generated/test_gwt_0099.py` (+ 0100, 0101)
- Implementation: `python/registry/cli.py` (new async function)
- New file: `.claude/commands/cw9_plan_fix.md` (correction agent prompt)

**Success Criteria:**
- [ ] Tests verify fresh context (no resume)
- [ ] Tests verify correct ClaudeAgentOptions fields
- [ ] Tests verify scope constraints in prompt

---

### Step 4: `_orchestrate_reviews_with_correction()` — main retry loop

**CW9 Binding:**
- GWTs: gwt-0088, gwt-0089, gwt-0090, gwt-0091, gwt-0092, gwt-0095
- Bridge artifacts: gwt-0088 through gwt-0092, gwt-0095

**What to build:**
```python
async def _orchestrate_reviews_with_correction(
    mode: str,
    plan_path: str,
    cwd: str,
    phase: str,
    json_mode: bool,
    max_retries: int = 2,
) -> dict:
    """Run review passes with correction loop. Same interface as _orchestrate_reviews."""
```

**Core state machine (from verified specs):**
```
for each pass in dependency order:
    if not _check_dependencies(pass): mark "blocked"; continue
    for attempt in range(1 + max_retries):
        result = await _run_review_pass(pass, ..., json_mode=True)  # forced JSON
        if result["verdict"] != "fail": break  # PASS/WARNING exits
        if attempt < max_retries:
            findings = _extract_findings(result["result_text"])
            await _run_correction_pass(pass, findings, ...)
    record result for pass
```

**Test Specification (from simulation traces):**
- All pass on first try → no corrections spawned, same as single-pass
- One pass fails, fixed on retry → correction spawned, re-review passes
- Pass exhausts retries → permanent FAIL, `stuck_on` in summary, dependents blocked
- Coverage + interaction run in parallel after artifacts pass
- Blocked cascade: artifacts FAIL → all others blocked
- `json_mode=True` forced for all review passes in correction mode (gwt-0086)
- WARNING is non-blocking for dependents (gwt-0089)

**Target files:**
- Test: `python/tests/generated/test_gwt_0090.py` (+ 0088, 0089, 0091, 0092, 0095)
- Implementation: `python/registry/cli.py` (new async function near line 2216)

**Success Criteria:**
- [ ] Retry loop respects max_retries bound
- [ ] Correction agent only spawned when attempt < max_retries and verdict is FAIL
- [ ] Parallel dispatch for coverage + interaction
- [ ] Dependency cascade blocking works transitively
- [ ] All existing tests still pass

---

### Step 5: Update `cmd_plan_review()` + `_add_utility_commands()` — CLI args

**CW9 Binding:**
- GWTs: gwt-0082, gwt-0083, gwt-0084, gwt-0085
- Bridge artifacts: gwt-0082 through gwt-0085

**What to build:**
- Add `--auto-fix` flag to `_add_utility_commands()` (store_true, default False)
- Add `--max-retries` arg (int, default 2)
- In `cmd_plan_review()`: if `args.auto_fix`, call `_orchestrate_reviews_with_correction()` else call `_orchestrate_reviews()` (existing)
- Reject negative `--max-retries` with CLI error

**Test Specification (from simulation traces):**
- No `--auto-fix` → `_orchestrate_reviews()` called (backward compat)
- `--auto-fix` → `_orchestrate_reviews_with_correction()` called
- `--auto-fix` without `--max-retries` → max_retries=2 default
- `--auto-fix --max-retries 0` → single pass through correction path
- `--auto-fix --max-retries -1` → CLI error

**Target files:**
- Test: `python/tests/generated/test_gwt_0082.py` (+ 0083, 0084, 0085)
- Implementation: `python/registry/cli.py:2324` (cmd_plan_review) and `cli.py:2354` (_add_utility_commands)

**Success Criteria:**
- [ ] Backward compatibility: no `--auto-fix` = identical behavior
- [ ] `--auto-fix` routes to new orchestration function
- [ ] `--max-retries` validation works

---

### Step 6: `_aggregate_verdicts()` update + `_review_manifest.json` + cost tracking

**CW9 Binding:**
- GWT: gwt-0098 (verified), gwt-0102..0104 (failed verification — hand-written tests)
- Bridge artifact: `gwt-0098_bridge_artifacts.json`

**What to build:**
- Update `_aggregate_verdicts()` to handle "blocked" verdict
  - blocked treated as fail for overall status
  - Summary separates into passed/failed/blocked buckets
  - blocked doesn't generate new `stuck_on` (only the root FAIL does)
- `_review_manifest.json` tracking (mechanical):
  - Append entry after each review pass: pass_name, attempt, verdict, report_path, session_id, cost
  - Created on first entry, appended atomically
- Cost breakdown in final summary:
  - `review_passes` array, `correction_passes` array, `total` sum

**Target files:**
- Test: `python/tests/generated/test_gwt_0098.py` (from pipeline) + hand-written tests for manifest/cost
- Implementation: `python/registry/cli.py:2144` (_aggregate_verdicts update)

**Success Criteria:**
- [ ] "blocked" verdict handled correctly in aggregation
- [ ] Three-bucket summary (passed/failed/blocked)
- [ ] Manifest file written with correct schema
- [ ] Cost breakdown accurate

---

### Step 7: `cw9_plan_fix.md` — correction agent prompt

**CW9 Binding:**
- GWT: gwt-0101 (scope constraints)
- This is a new file, not code

**What to create:**
`.claude/commands/cw9_plan_fix.md` — the prompt the correction agent follows. Key rules:
- ONLY modify: context files, plan text, test scaffolding
- NEVER modify: source code, TLA+ specs, bridge artifacts
- Per review type:
  - **coverage**: add missing assertions from bridge verifier list
  - **abstraction_gap**: copy decision checklist into context files
  - **imports**: remove dead imports, flag wrong abstractions for human review
  - **artifacts**: list pipeline steps to re-run (don't execute them)
- NEVER weaken test assertions or remove invariant checks

**Target file:** `.claude/commands/cw9_plan_fix.md`

---

## Integration Testing

After all steps, run the full orchestrator:

```bash
# Backward compat (no auto-fix)
cw9 plan-review <test-plan> . --json

# Auto-fix mode
cw9 plan-review <test-plan> . --auto-fix --json

# Auto-fix with no retries (single pass through new path)
cw9 plan-review <test-plan> . --auto-fix --max-retries 0 --json
```

Cross-behavior verification:
- Correction loop terminates within max_retries bound
- Dependency cascade blocks correctly
- Cost tracking accumulates across review + correction passes
- `_review_manifest.json` has correct entries after run

## Verification

After implementation, re-verify:
```bash
cw9 stale .
# Re-run verification for any modified behavior
cw9 loop gwt-0082 . --context-file .cw9/context/gwt-0082.md
```

## References

- Research: `thoughts/searchable/shared/research/2026-03-25-correction-loop-orchestrator.md`
- Verified specs: `templates/pluscal/instances/gwt-008[0-9].tla`, `gwt-009[0-9].tla`, `gwt-010[01].tla`
- Bridge artifacts: `python/tests/generated/gwt-008*_bridge_artifacts.json`, `gwt-009*_bridge_artifacts.json`, `gwt-010[01]_bridge_artifacts.json`
- Context files: `.cw9/context/gwt-0080.md` through `.cw9/context/gwt-0104.md`
- Beads: `bd show cosmic-hr-d1ij`
