---
date: 2026-03-25T00:00:00Z
researcher: FuchsiaRaven
git_commit: 27765af
branch: master
repository: CodeWriter9.0
topic: "cw9 plan-review orchestrator TDD Plan"
tags: [plan, tdd, cw9, plan-review, orchestrator, agent-sdk, cli]
status: implemented
last_updated: 2026-03-25
last_updated_by: FuchsiaRaven
research_doc: thoughts/searchable/shared/research/2026-03-25-plan-review-orchestrator.md
---

# `cw9 plan-review` Orchestrator — TDD Implementation Plan

## Overview

Add a `cw9 plan-review` CLI command that orchestrates the 5 decomposed review passes
(artifacts, coverage, interaction, abstraction_gap, imports) using the Claude Agent SDK's
standalone `query()` function. The orchestrator enforces a dependency graph: artifacts is
a hard gate, coverage and interaction run in parallel, abstraction_gap follows, and imports
is post-implementation only. Supports self-hosting and external project modes with auto-detection,
`--phase` filtering, and both streaming terminal output and `--json` machine-readable output.

## Research Reference

- Research doc: `thoughts/searchable/shared/research/2026-03-25-plan-review-orchestrator.md`
- Beads: `cosmic-hr-szw7`

## SDK API Corrections

The research doc's proposed code references SDK APIs that don't exist in v0.1.49. The
implementation MUST use the actual SDK patterns found in the codebase:

| Research Doc (Wrong) | Actual SDK (Correct) | Codebase Reference |
|---|---|---|
| `StreamEvent` | `AssistantMessage` + `ResultMessage` | `loop_runner.py:83-96` |
| `include_partial_messages` param | Not a real param | — |
| `permission_mode` param | Not a real param | — |
| `cwd` param on `ClaudeAgentOptions` | Not a real param | — |
| `msg.total_cost_usd` on `ResultMessage` | Verify at implementation time | — |
| `msg.session_id` on `ResultMessage` | Verify at implementation time | — |

The codebase pattern for standalone `query()` is at `cli.py:1577-1609`. Use that as the
reference implementation, NOT the research doc's `_run_review_pass()`.

## Verified Specs and Traces

### gwt-0077: plan-review-orchestration-flow
- **Given**: a set of review passes with dependency constraints: artifacts gates all, coverage and interaction are parallel, abstraction_gap follows parallel, imports is post-only
- **When**: `_orchestrate_reviews()` executes with phase='all' and mode='self' and artifacts passes
- **Then**: artifacts runs first; coverage and interaction run concurrently after artifacts passes; abstraction_gap runs only after both parallel passes complete; imports runs last; total_cost_usd accumulates from all passes
- **Verified spec**: `templates/pluscal/instances/gwt-0077.tla` (attempt 5)
- **Simulation traces**: `templates/pluscal/instances/gwt-0077_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0077_bridge_artifacts.json`
  - data_structures: 1 — ReviewOrchestrationState
  - operations: 15 — StartArtifacts, CompleteArtifacts, CheckGate, StartParallel, ChooseParallel, FinishCoverageFirst, FinishInteractionFirst, FinishCoverageSecond, FinishInteractionSecond, StartAbstractionGap, CompleteAbstractionGap, StartImports, CompleteImports, HandleFail, Terminate
  - verifiers: 8 — Passes, DependencyOrder, GateEnforcement, CostMonotonicity, CompletionConsistency, ParallelSafety, BoundedCost, TypeOK

### gwt-0078: plan-review-artifacts-gate
- **Given**: the artifacts review pass returns verdict 'fail'
- **When**: `_orchestrate_reviews()` checks the artifacts gate
- **Then**: no further passes execute; the function returns status='blocked' with blocked_by='artifacts' and only the artifacts result in results
- **Verified spec**: `templates/pluscal/instances/gwt-0078.tla` (attempt 3)
- **Simulation traces**: `templates/pluscal/instances/gwt-0078_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0078_bridge_artifacts.json`
  - data_structures: 1 — ArtifactsGateState
  - operations: 5 — SelectVerdict, RunArtifacts, CheckGate, RunParallel, Terminate
  - verifiers: 7 — GateBlocking, GatePassthrough, BlockedStatus, CostAccuracy, OnlyArtifactsWhenBlocked, NoExtraPassesWhenBlocked, TypeOK

### gwt-0079: plan-review-mode-detection
- **Given**: neither --self nor --external flag is supplied
- **When**: cmd_plan_review() determines the mode
- **Then**: if .cw9/ directory exists under target_dir mode is 'external' (using EXTERNAL_REVIEWS); otherwise mode is 'self' (using SELF_REVIEWS); explicit flags override auto-detection
- **Verified spec**: `templates/pluscal/instances/gwt-0079.tla` (attempt 4)
- **Simulation traces**: `templates/pluscal/instances/gwt-0079_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0079_bridge_artifacts.json`
  - data_structures: 1 — PlanReviewModeDetectionState
  - operations: 2 — DetermineMode, Finish
  - verifiers: 7 — ModeValid, ReviewsValid, ModeReviewConsistency, ExplicitOverrideSelf, ExplicitOverrideExternal, AutoDetectExternal, AutoDetectSelf

### gwt-0080: plan-review-phase-filtering
- **Given**: phase is one of 'pre', 'post', or 'all'
- **When**: `_orchestrate_reviews()` selects which passes to run
- **Then**: phase='pre' runs artifacts+coverage+interaction+abstraction_gap but NOT imports; phase='post' runs ONLY imports; phase='all' runs everything; external mode never includes interaction regardless of phase
- **Verified spec**: `templates/pluscal/instances/gwt-0080.tla` (attempt 3)
- **Simulation traces**: `templates/pluscal/instances/gwt-0080_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0080_bridge_artifacts.json`
  - data_structures: 1 — PlanReviewPhaseFilteringState
  - operations: 3 — Orchestrate, RunOrSkip, Finish
  - verifiers: 10 — PreSkipsImports, ExternalNoInteraction, PreExternalSubset, PostOnlyImports, AllSelfComplete, AllExternalComplete, PreSelfComplete, PreExternalComplete, FinalSetCorrect, ExecutedSubsetAllPasses

### gwt-0081: plan-review-verdict-aggregation
- **Given**: all applicable review passes have completed with individual verdicts
- **When**: `_orchestrate_reviews()` computes the overall status
- **Then**: if any verdict is 'fail' then status='fail'; else if any verdict is 'warning' then status='warning'; else status='pass'; cmd_plan_review returns exit code 0 for pass/warning and 1 for fail
- **Verified spec**: `templates/pluscal/instances/gwt-0081.tla` (attempt 4)
- **Simulation traces**: `templates/pluscal/instances/gwt-0081_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0081_bridge_artifacts.json`
  - data_structures: 1 — PlanReviewVerdictAggregationState
  - operations: 6 — AddVerdicts, PickVerdict, ComputeOverall, SetExitCode, MarkDone, Finish
  - verifiers: 5 — FailDominates, WarningSecond, ExitCodeMapping, StatusIsValid, VerdictLengthBound

## What We're NOT Doing

- No `ClaudeSDKClient` persistent sessions — `query()` standalone calls only (see research doc rationale)
- No `fork_session` or `AgentDefinition` subagents — static dependency graph, no LLM-driven orchestration
- No structured output per review pass — heuristic verdict parsing from result text
- No retry logic per review pass — if a pass fails internally, its verdict reflects that
- No new dependencies — `claude-agent-sdk >= 0.1.0` already declared in pyproject.toml

## Implementation Steps

### Step 1: Review Pass Constants — SELF_REVIEWS and EXTERNAL_REVIEWS

**CW9 Binding:**
- GWT: gwt-0079 (mode detection depends on correct review lists)
- Bridge artifact: `data_structures[0]` (PlanReviewModeDetectionState.reviews_list)

**What to implement:**
Two module-level constants mapping review pass names to their `.md` prompt file paths.
Self-hosting uses `.claude/commands/cw9_review_*.md` (relative to cwd).
External uses `~/.claude/commands/cw9_review_*.md` (tilde-expanded).

```python
SELF_REVIEWS = [
    ("artifacts",       ".claude/commands/cw9_review_01_artifacts.md"),
    ("coverage",        ".claude/commands/cw9_review_02_coverage.md"),
    ("abstraction_gap", ".claude/commands/cw9_review_03_abstraction_gap.md"),
    ("interaction",     ".claude/commands/cw9_review_04_interaction.md"),
    ("imports",         ".claude/commands/cw9_review_05_imports.md"),
]

EXTERNAL_REVIEWS = [
    ("artifacts",       "~/.claude/commands/cw9_review_01_artifacts.md"),
    ("coverage",        "~/.claude/commands/cw9_review_02_coverage.md"),
    ("abstraction_gap", "~/.claude/commands/cw9_review_03_abstraction_gap.md"),
    ("imports",         "~/.claude/commands/cw9_review_04_imports.md"),
]
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0079.py`
- Implementation: `python/registry/cli.py` (new constants near top of plan-review section)

**Success Criteria:**
- [x] SELF_REVIEWS has 5 entries including "interaction"
- [x] EXTERNAL_REVIEWS has 4 entries, no "interaction"
- [x] All paths resolve correctly for their respective modes

---

### Step 2: Mode Detection — `_detect_review_mode()`

**CW9 Binding:**
- GWT: gwt-0079
- Bridge artifact: `operations` DetermineMode, `verifiers` ExplicitOverrideSelf/ExplicitOverrideExternal/AutoDetectExternal/AutoDetectSelf/ModeReviewConsistency

**Test Specification (from simulation traces):**
- Given: self_flag=FALSE, external_flag=FALSE, cw9_dir_exists=TRUE → mode="external", reviews=EXTERNAL_REVIEWS
- Given: self_flag=FALSE, external_flag=FALSE, cw9_dir_exists=FALSE → mode="self", reviews=SELF_REVIEWS
- Given: self_flag=TRUE (any dir state) → mode="self", reviews=SELF_REVIEWS
- Given: external_flag=TRUE (any dir state) → mode="external", reviews=EXTERNAL_REVIEWS
- Edge case (trace 3): both flags TRUE → undefined (implementation should pick one; suggest --self wins)

**What to implement:**
Extract mode detection into a pure function for testability:
```python
def _detect_review_mode(self_flag: bool, external_flag: bool, target_dir: Path) -> tuple[str, list]:
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0079.py`
- Implementation: `python/registry/cli.py`

**Success Criteria:**
- [x] Test fails for right reason (Red)
- [x] All 4 auto-detect/explicit scenarios pass (Green)
- [x] ModeReviewConsistency: mode="self" always pairs with SELF_REVIEWS

---

### Step 3: Verdict Parsing and Aggregation

**CW9 Binding:**
- GWT: gwt-0081
- Bridge artifact: `operations` ComputeOverall/SetExitCode, `verifiers` FailDominates/WarningSecond/ExitCodeMapping

**Test Specification (from simulation traces):**
- Given: verdicts=[pass, pass, fail] → status="fail", exit_code=1
- Given: verdicts=[pass, warning, pass] → status="warning", exit_code=0
- Given: verdicts=[pass, pass, pass] → status="pass", exit_code=0
- Given: verdicts=[unknown] → status="pass", exit_code=0 (unknown does not escalate)

**What to implement:**
Two pure functions:
```python
def _parse_verdict(result_text: str) -> str:
    """Parse PASS/FAIL/WARNING/CRITICAL from result text. Returns verdict string."""

def _aggregate_verdicts(results: dict[str, dict]) -> tuple[str, int]:
    """Compute overall status and exit code from per-pass results."""
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0081.py`
- Implementation: `python/registry/cli.py`

**Success Criteria:**
- [x] FailDominates: any "fail" verdict → overall "fail"
- [x] WarningSecond: "warning" without "fail" → overall "warning"
- [x] ExitCodeMapping: pass/warning → 0, fail → 1

---

### Step 4: Single Review Pass Execution — `_run_review_pass()`

**CW9 Binding:**
- GWT: gwt-0078 (pass execution is a prerequisite for gate logic)
- Bridge artifact: `operations` RunArtifacts

**What to implement:**
Async function that reads a `.md` prompt file, constructs the full prompt with plan_path,
calls `query()` via the SDK, collects the result, and returns a structured dict.

Follow the existing `query()` pattern at `cli.py:1577-1609`:
```python
async def _run_review_pass(
    name: str,
    prompt_file: Path,
    plan_path: str,
    json_mode: bool,
) -> dict:
```

Returns: `{"name": name, "verdict": str, "session_id": str, "cost_usd": float, "result_length": int, "result_text": str}`

**Key design decisions:**
- Use `AssistantMessage`/`TextBlock` for streaming (not `StreamEvent` — that doesn't exist)
- `ClaudeAgentOptions(allowed_tools=["Read", "Grep", "Glob", "Bash"], system_prompt=prompt_text, max_turns=20, model="claude-sonnet-4-6")`
- Stream `TextBlock.text` to stdout when not in json_mode
- Parse verdict via `_parse_verdict()` from Step 3
- Check whether `ResultMessage` actually has `.total_cost_usd` and `.session_id` at implementation time — if not, use defaults

**Target files:**
- Test: `python/tests/generated/test_gwt_0078.py` (mock SDK query)
- Implementation: `python/registry/cli.py`

**Success Criteria:**
- [x] Reads .md file and appends plan_path to prompt
- [x] Returns well-formed result dict with verdict parsed from result text
- [x] Streams to stdout in non-json mode, silent in json mode

---

### Step 5: Artifacts Gate Logic

**CW9 Binding:**
- GWT: gwt-0078
- Bridge artifact: `operations` CheckGate, `verifiers` GateBlocking/GatePassthrough/BlockedStatus/OnlyArtifactsWhenBlocked

**Test Specification (from simulation traces):**
- Trace 1-2: artifacts verdict="fail" → return `{"status": "blocked", "blocked_by": "artifacts", "results": {"artifacts": ...}}`
- Trace 3: artifacts verdict="warning" → continue to parallel passes, results include coverage+
- Key invariant: when blocked, results dict has exactly ONE key ("artifacts")

**What to implement:**
Gate check within `_orchestrate_reviews()`:
```python
if r["verdict"] == "fail":
    return {"status": "blocked", "blocked_by": "artifacts", "results": results, "total_cost_usd": total_cost}
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0078.py`
- Implementation: `python/registry/cli.py` (inside `_orchestrate_reviews`)

**Success Criteria:**
- [x] GateBlocking: fail verdict → immediate return, no further passes
- [x] GatePassthrough: pass/warning → execution continues
- [x] OnlyArtifactsWhenBlocked: blocked result has exactly {"artifacts": ...}

---

### Step 6: Phase Filtering Logic

**CW9 Binding:**
- GWT: gwt-0080
- Bridge artifact: `operations` Orchestrate/RunOrSkip, `verifiers` PreSkipsImports/PostOnlyImports/ExternalNoInteraction/AllSelfComplete/AllExternalComplete

**Test Specification (from simulation traces):**
- Trace 1: phase=all, mode=self, artifacts=fail → executed={"artifacts"} only
- Trace 2: phase=pre, mode=self → executed includes coverage/interaction/abstraction_gap but NOT imports
- External mode: never includes "interaction" regardless of phase

**What to implement:**
Phase and mode filtering within `_orchestrate_reviews()`:
- `phase in ("pre", "all")`: run artifacts → parallel → abstraction_gap
- `phase in ("post", "all")`: run imports
- `mode == "external"`: exclude "interaction" from parallel set

**Target files:**
- Test: `python/tests/generated/test_gwt_0080.py`
- Implementation: `python/registry/cli.py` (inside `_orchestrate_reviews`)

**Success Criteria:**
- [x] PreSkipsImports: phase="pre" → no imports in results
- [x] PostOnlyImports: phase="post" → only imports in results
- [x] ExternalNoInteraction: mode="external" → no interaction in results
- [x] AllSelfComplete: phase="all", mode="self", artifacts passes → 5 results
- [x] AllExternalComplete: phase="all", mode="external", artifacts passes → 4 results

---

### Step 7: Full Orchestration — `_orchestrate_reviews()`

**CW9 Binding:**
- GWT: gwt-0077
- Bridge artifact: all 15 operations, all 8 verifiers

**Test Specification (from simulation traces):**
- Trace 1-3: artifacts fail → blocked, all other passes remain not_run
- Happy path: artifacts pass → coverage+interaction parallel via `asyncio.gather` → abstraction_gap sequential → imports sequential
- DependencyOrder invariant: abstraction_gap never starts before parallel completes
- ParallelSafety: coverage and interaction can be in "running" state simultaneously
- CostMonotonicity: total_cost only increases

**What to implement:**
```python
async def _orchestrate_reviews(
    mode: str,
    plan_path: str,
    cwd: str,
    phase: str,
    json_mode: bool,
) -> dict:
```

This integrates Steps 4-6:
1. Run artifacts (gate — Step 5)
2. Parallel: `asyncio.gather` on coverage [+ interaction if self mode] (Step 6 filtering)
3. Sequential: abstraction_gap
4. Sequential: imports (if phase allows — Step 6 filtering)
5. Aggregate verdicts (Step 3)
6. Return summary dict

**Target files:**
- Test: `python/tests/generated/test_gwt_0077.py`
- Implementation: `python/registry/cli.py`

**Success Criteria:**
- [x] DependencyOrder: abstraction_gap waits for all parallel passes
- [x] GateEnforcement: artifacts fail → immediate return
- [x] ParallelSafety: coverage and interaction are gathered concurrently
- [x] CostMonotonicity: costs accumulate correctly
- [x] CompletionConsistency: all applicable passes have results when done

---

### Step 8: CLI Wiring — `cmd_plan_review()` + Parser + Dispatch

**CW9 Binding:**
- GWT: gwt-0079 (mode detection integration), gwt-0081 (exit code)
- Bridge artifact: ExitCodeMapping verifier

**What to implement:**

1. Add parser in `_add_utility_commands()` (after line 2111):
```python
p_plan_review = sub.add_parser("plan-review", help="Orchestrate plan review passes")
p_plan_review.add_argument("plan_path", help="Path to CW9 TDD plan")
p_plan_review.add_argument("target_dir", nargs="?", default=".")
p_plan_review.add_argument("--self", dest="self_hosting", action="store_true")
p_plan_review.add_argument("--external", action="store_true")
p_plan_review.add_argument("--json", dest="json_output", action="store_true")
p_plan_review.add_argument("--phase", choices=["pre", "post", "all"], default="all")
```

2. Add to `_DISPATCH` (after line 2131):
```python
"plan-review": cmd_plan_review,
```

3. Implement `cmd_plan_review()`:
```python
def cmd_plan_review(args: argparse.Namespace) -> int:
    mode, reviews = _detect_review_mode(args.self_hosting, args.external, Path(args.target_dir).resolve())
    summary = asyncio.run(_orchestrate_reviews(mode, args.plan_path, str(Path(args.target_dir).resolve()), args.phase, args.json_output))
    # Format output (json or terminal summary)
    # Return exit code via _aggregate_verdicts
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0079.py` + `test_gwt_0081.py` (integration)
- Implementation: `python/registry/cli.py` (3 locations: parser, dispatch, handler)

**Success Criteria:**
- [x] `cw9 plan-review --help` works
- [x] Exit code 0 for pass/warning, 1 for fail
- [x] `--json` produces valid JSON to stdout
- [x] Terminal mode shows section headers and verdict icons

---

## Integration Testing

After all steps pass individually, verify cross-behavior integration:

1. **Full self-hosting flow**: `cw9 plan-review <plan> --self --phase all`
   - Covers gwt-0077 (orchestration) + gwt-0079 (mode=self) + gwt-0080 (phase=all) + gwt-0081 (verdicts)
2. **External with gate failure**: mock artifacts to fail
   - Covers gwt-0078 (gate blocks) + gwt-0079 (mode=external) + gwt-0080 (only artifacts runs)
3. **Post-impl only**: `cw9 plan-review <plan> --phase post`
   - Covers gwt-0080 (PostOnlyImports) + gwt-0081 (single verdict aggregation)
4. **JSON output**: `cw9 plan-review <plan> --json | python3 -m json.tool`
   - Covers summary schema validation

## Verification

After implementation, re-verify with the pipeline:
```bash
cd /home/maceo/Dev/CodeWriter9.0/python
python3 -m pytest tests/ -x

# Re-crawl to pick up new functions
cw9 ingest python/registry/cli.py --incremental

# Check for stale records
cw9 stale
```

## References

- Research: `thoughts/searchable/shared/research/2026-03-25-plan-review-orchestrator.md`
- Verified specs: `templates/pluscal/instances/gwt-007{7,8,9}.tla`, `gwt-008{0,1}.tla`
- Bridge artifacts: `python/tests/generated/gwt-007{7,8,9}_bridge_artifacts.json`, `gwt-008{0,1}_bridge_artifacts.json`
- Simulation traces: `templates/pluscal/instances/gwt-007{7,8,9}_sim_traces.json`, `gwt-008{0,1}_sim_traces.json`
- SDK reference pattern: `python/registry/cli.py:1577-1609` (standalone `query()` usage)
- Beads: `bd show cosmic-hr-szw7`
