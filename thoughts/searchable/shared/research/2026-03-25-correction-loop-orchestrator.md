---
date: 2026-03-25T00:00:00Z
researcher: FuchsiaRaven
git_commit: bfdf819
branch: master
repository: CodeWriter9.0
topic: "Correction loop for plan-review orchestrator"
tags: [research, cw9, orchestrator, correction-loop, iterative-review]
status: complete
last_updated: 2026-03-25
last_updated_by: FuchsiaRaven
cw9_project: /home/maceo/Dev/CodeWriter9.0
---

# Research: Correction Loop for Plan-Review Orchestrator

## Research Question

The current `cw9 plan-review` orchestrator (cli.py:2216) runs all review passes sequentially and aggregates verdicts, but never feeds findings back for correction. It's a single-pass pipeline. The manual workflow is iterative: each review finding triggers a fix cycle (correct -> re-review -> next pass). How should the orchestrator be enhanced to support this correction loop?

## Current State Analysis

### What Exists (cli.py:2099-2400)

The orchestrator has 5 functions:

| Function | Line | Role |
|---|---|---|
| `_detect_review_mode()` | 2119 | Selects self vs external review set |
| `_parse_verdict()` | 2132 | Heuristic PASS/FAIL/WARNING extraction |
| `_aggregate_verdicts()` | 2144 | Reduces per-pass verdicts to overall |
| `_run_review_pass()` | 2163 | Runs one pass via Claude Agent SDK `query()` |
| `_orchestrate_reviews()` | 2216 | Main orchestration: phase ordering + parallelism |
| `cmd_plan_review()` | 2324 | CLI entry point |

### Current Execution Model

```
artifacts (gate) -> [coverage || interaction] -> abstraction_gap -> imports
                    ^                                                  ^
                    parallel                                      post-impl only
```

If artifacts fails, everything stops ("blocked"). Otherwise, all remaining passes run unconditionally. Results are aggregated into a single JSON summary. **No pass's findings influence any subsequent pass's execution.**

### What's Missing

1. **No correction dispatch.** When a pass finds issues, the orchestrator doesn't invoke an implementation agent to fix them.
2. **No re-verification.** After corrections, the failed pass isn't re-run.
3. **No gate-per-pass.** Only artifacts gates. A failing coverage pass doesn't block abstraction_gap.
4. **No finding extraction.** `_parse_verdict()` extracts pass/fail but not the specific findings (which verifiers are uncovered, which imports are dead, etc.).
5. **No report-file awareness.** Each review pass writes a report to `thoughts/searchable/shared/plans/`, but the orchestrator never reads these reports — it only looks at verdict text.

### Manual Workflow (What Humans Do)

In practice, the pipeline is used like this:

```
1. /cw9_plan_review <plan>           # runs all 5 passes
2. Read the review reports           # human reads findings
3. Fix context files, plan, specs    # human or agent corrects
4. Re-run the failing pass           # /cw9_review_02_coverage <plan>
5. Check it passes now               # read new report
6. Move to next failing pass         # repeat 3-5
7. /cw9_implement <plan>             # only after all pass
```

Steps 2-6 are the correction loop. The orchestrator handles step 1, but the human drives 2-6 manually.

## Design Space

### Option A: Per-Pass Gate with Human-in-the-Loop

Each pass that fails blocks the next. The orchestrator returns control to the user/caller after each failure. The user fixes and re-invokes.

```
cw9 plan-review <plan> --phase pre
  -> artifacts: PASS
  -> coverage: FAIL (3 uncovered verifiers)
  -> STOPS. Returns findings.

# User fixes context files
cw9 plan-review <plan> --phase pre --resume-from coverage
  -> coverage: PASS
  -> interaction: PASS
  -> abstraction_gap: WARNING (2 undocumented decisions)
  -> CONTINUES (warning doesn't block)
```

**Pros:** Simple, predictable, cheap. User stays in control.
**Cons:** Multiple invocations. Not autonomous.

### Option B: Autonomous Correction via Implementation Agent

The orchestrator spawns a correction agent after each failing pass. The correction agent reads the review report, makes fixes, and the pass is re-run.

```
cw9 plan-review <plan> --auto-fix
  -> artifacts: PASS
  -> coverage: FAIL
     -> spawn correction agent
     -> agent fixes context files
     -> re-run coverage
     -> coverage: PASS
  -> abstraction_gap: WARNING
     -> spawn correction agent
     -> agent adds decision checklist to context
     -> re-run abstraction_gap
     -> abstraction_gap: PASS
  -> DONE
```

**Pros:** Fully autonomous. Single invocation.
**Cons:** Expensive (each correction is an Agent SDK session). Risk of incorrect fixes cascading. Hard to bound cost. Correction agent may hallucinate fixes.

### Option C: Structured Findings with Correction Instructions

The orchestrator extracts structured findings from each review report and generates a correction manifest. A separate command applies corrections.

```
cw9 plan-review <plan> --json
  -> { findings: [ {pass: "coverage", type: "uncovered_verifier", ...} ] }

cw9 plan-fix <findings.json>       # new command
  -> reads manifest, applies mechanical fixes
  -> context file updates, plan amendments

cw9 plan-review <plan> --json      # re-run
  -> all pass
```

**Pros:** Decoupled. Findings are data, not prose. Mechanical fixes are reliable.
**Cons:** Not all fixes are mechanical. Abstraction gap decisions require judgment. Two-command workflow.

### Option D: Iterative Loop with Max Retries

Hybrid: the orchestrator has a built-in retry loop. Each failing pass gets N retries with a correction agent. If it still fails after N retries, the orchestrator stops and reports.

```python
async def _orchestrate_with_correction(
    mode, plan_path, cwd, phase, json_mode,
    max_retries=2,
    correction_prompt_file=".claude/commands/cw9_plan_fix.md",
):
    for pass_name, prompt_file in ordered_passes:
        for attempt in range(1 + max_retries):
            result = await _run_review_pass(...)
            if result["verdict"] != "fail":
                break
            if attempt < max_retries:
                await _run_correction_pass(
                    pass_name, result, correction_prompt_file, ...)
        if result["verdict"] == "fail":
            return {"status": "fail", "stuck_on": pass_name, ...}
```

**Pros:** Bounded cost (max_retries). Autonomous within bounds. Falls back to human if stuck.
**Cons:** Correction agent quality is the bottleneck. Still expensive per retry.

## Recommended Approach: Option D (Iterative with Max Retries)

### Why

1. **Matches the manual workflow.** The loop structure (review -> fix -> re-review) mirrors what humans do.
2. **Bounded cost.** `max_retries=2` caps each pass at 3 total runs. With 5 passes and $0.02/pass average, worst case is 15 runs = ~$0.30.
3. **Graceful degradation.** If the correction agent can't fix it in 2 tries, the orchestrator stops and returns actionable findings — the human takes over exactly where they would have started.
4. **Incremental adoption.** The existing single-pass mode is `max_retries=0` — full backward compatibility.

### Key Design Decisions

#### 1. Correction Agent Scope

The correction agent should have a **narrow scope**: it reads one review report and makes targeted fixes to context files, the plan, or generated test scaffolding. It should NOT:
- Re-run pipeline steps (cw9 loop, cw9 bridge)
- Modify source code
- Modify verified TLA+ specs
- Change bridge artifacts

What it CAN do:
- Update context files (add Test Interface entries, decision checklists)
- Fix plan status claims
- Remove dead imports from generated test scaffolding
- Add missing assertions to test plans

#### 2. Correction Prompt Design

Each review type needs a correction prompt that translates findings into actions:

| Review | Correction Action | Automatable? |
|---|---|---|
| Artifacts | Run missing pipeline steps (`cw9 loop`, `cw9 bridge`) | Partially — requires LLM for spec generation |
| Coverage | Add missing test assertions to plan/context | Yes — mechanical from bridge verifier list |
| Interaction | Resolve DAG conflicts, update ID ranges | Partially — judgment needed for conflicts |
| Abstraction Gap | Add decision checklist to context files | Yes — checklist is already in the review report |
| Imports | Remove dead imports, flag wrong abstractions | Partially — dead imports are mechanical, wrong abstractions need judgment |

#### 3. Finding Extraction

The current `_parse_verdict()` only extracts pass/fail. The correction loop needs structured findings. Two approaches:

**A. Structured output from review passes:**
Add `output_format` to the review `query()` call to get JSON findings alongside the report. Problem: this changes the review prompt behavior and the SDK can't do streaming + structured output simultaneously.

**B. Parse the review report file:**
Each review writes a markdown report with structured tables. Parse the tables for findings. Problem: fragile markdown parsing.

**C. Second pass for finding extraction:**
After a review fails, make a second `query()` call with structured output to extract findings from the result text. Clean separation but adds cost.

**Recommended: Approach A with `--json` mode.** When in correction loop mode, force `json_mode=True` for review passes and add a `ReviewFindings` schema to `output_format`. The review agent produces both the report and structured findings. This means no streaming during correction loops — acceptable because the loop is meant to be autonomous.

#### 4. Gate Logic Changes

Current: Only artifacts gates.
Proposed: Every pass gates the next in correction mode.

```python
PASS_DEPENDENCIES = {
    "artifacts": [],                          # no deps
    "coverage": ["artifacts"],                 # needs artifacts pass
    "interaction": ["artifacts"],              # needs artifacts pass
    "abstraction_gap": ["coverage", "interaction"],  # needs coverage + interaction
    "imports": ["abstraction_gap"],            # post-impl, needs gap analysis
}
```

If a pass fails and exhausts retries, all dependent passes are skipped and marked "blocked".

#### 5. Report File Location

The correction agent needs to read the review report from the previous attempt. Reports go to `thoughts/searchable/shared/plans/YYYY-MM-DD-description-<TYPE>-REVIEW.md`. The orchestrator must:
1. Know the report path (either parse it from the review result, or construct it deterministically)
2. Pass the report path to the correction agent

**Simplest approach:** Have the orchestrator write a `_review_manifest.json` that tracks report paths per pass per attempt.

### Proposed Architecture

```
_orchestrate_reviews_with_correction()
  │
  ├─ for each pass in dependency order:
  │    │
  │    ├─ check: all dependencies passed?
  │    │   └─ no → skip, mark "blocked"
  │    │
  │    ├─ for attempt in range(1 + max_retries):
  │    │    │
  │    │    ├─ _run_review_pass(pass_name, ...)
  │    │    │   └─ returns { verdict, result_text, findings }
  │    │    │
  │    │    ├─ if verdict != "fail": break
  │    │    │
  │    │    └─ if attempt < max_retries:
  │    │         └─ _run_correction_pass(pass_name, findings, ...)
  │    │             └─ spawns correction agent via query()
  │    │             └─ agent reads review report + plan
  │    │             └─ agent makes targeted fixes
  │    │
  │    └─ record result for this pass
  │
  └─ aggregate and return summary
```

### New CLI Interface

```
cw9 plan-review <plan> [existing flags] [--auto-fix] [--max-retries N]
```

- `--auto-fix`: Enable the correction loop (default: off, single-pass mode)
- `--max-retries N`: Max correction attempts per pass (default: 2)
- When `--auto-fix` is off, behavior is identical to current implementation (backward compatible)

### New Functions Needed

| Function | Purpose |
|---|---|
| `_run_correction_pass()` | Spawns a correction agent for a failed review |
| `_extract_findings()` | Extracts structured findings from review result text |
| `_orchestrate_reviews_with_correction()` | New orchestration function with retry loop |
| `_check_dependencies()` | Evaluates whether a pass's deps have all passed |

### Correction Prompt File

A new `.claude/commands/cw9_plan_fix.md` that the correction agent follows:

```markdown
# CW9 Plan Fix

Given a review report with specific findings, make targeted corrections.

## Inputs
- Review type (artifacts/coverage/abstraction_gap/interaction/imports)
- Review findings (structured JSON or report path)
- Plan path
- Target directory

## Rules
- ONLY modify context files, plan text, and test scaffolding
- NEVER modify source code, specs, or bridge artifacts
- NEVER weaken test assertions
- NEVER remove invariant checks
- For coverage gaps: add assertions from bridge verifiers
- For abstraction gaps: copy decision checklist into context files
- For artifact issues: list which pipeline steps need re-running (don't run them)
- For import issues: remove dead imports, flag wrong abstractions for human review
```

## Key Functions (Current Implementation)

### _orchestrate_reviews()
- **File**: python/registry/cli.py:2216
- **Role**: Main orchestration loop — runs passes in dependency order with parallel coverage+interaction
- **Change needed**: Add retry loop around each pass, spawn correction agent on failure

### _run_review_pass()
- **File**: python/registry/cli.py:2163
- **Role**: Runs one review pass via `query()`. Returns dict with verdict, result_text, session_id, cost
- **Change needed**: Add structured finding extraction to return value

### _parse_verdict()
- **File**: python/registry/cli.py:2132
- **Role**: Extracts PASS/FAIL/WARNING from result text
- **Change needed**: None (still needed for backward compat). New `_extract_findings()` adds to this.

### _aggregate_verdicts()
- **File**: python/registry/cli.py:2144
- **Role**: Reduces per-pass verdicts to overall status
- **Change needed**: Handle "blocked" verdict (pass was skipped due to failed dependency)

### cmd_plan_review()
- **File**: python/registry/cli.py:2324
- **Role**: CLI entry point, parses args, calls _orchestrate_reviews
- **Change needed**: Add --auto-fix and --max-retries args

## SDK Capabilities Relevant to Correction Loop

### `query()` — standalone async function
- Each correction pass is an independent `query()` call
- No session sharing needed between review and correction
- Correction agent gets a clean context window

### `ClaudeAgentOptions` fields
- `allowed_tools=["Read", "Grep", "Glob", "Bash", "Edit", "Write"]` — correction agent needs edit tools
- `max_turns=20` — sufficient for targeted fixes
- `system_prompt` — "You are a CW9 correction agent. Fix the issues found in the review."
- `model="claude-sonnet-4-6"` — same as review agents

### `resume=session_id`
- NOT used. Correction agent doesn't resume the review session.
- Each correction is a fresh context with the findings as input.

### `output_format`
- Could be used for structured finding extraction from review passes
- Mutually exclusive with streaming — acceptable for correction loop mode

## Cost Analysis

| Scenario | Review Passes | Correction Passes | Total Calls | Est. Cost |
|---|---|---|---|---|
| All pass (no correction) | 5 | 0 | 5 | ~$0.10 |
| 1 pass fails, fixed in 1 retry | 6 | 1 | 7 | ~$0.14 |
| 2 passes fail, 1 retry each | 7 | 2 | 9 | ~$0.18 |
| Worst case (all fail, max retries) | 15 | 10 | 25 | ~$0.50 |

Average expected cost for a typical plan with 1-2 issues: ~$0.15-0.20.

## Risks and Mitigations

### Risk: Correction agent makes wrong fixes
**Mitigation:** Narrow scope — only context files, plan text, test scaffolding. No source code changes. If the fix is wrong, the re-review will catch it and it'll exhaust retries, falling back to human.

### Risk: Infinite loops
**Mitigation:** `max_retries` bound. Default 2 means at most 3 runs per pass. Hard cap.

### Risk: Cost explosion
**Mitigation:** Cost tracking per pass. `_orchestrate_reviews_with_correction()` tracks cumulative cost. Could add `--max-cost` flag.

### Risk: Review agent and correction agent disagree
**Mitigation:** They don't share context. The correction agent reads the report file on disk (ground truth), not the review agent's conversation. The re-review is a fresh evaluation.

## Proposed Changes

| File | Change |
|---|---|
| python/registry/cli.py:2163 | Add `_extract_findings()` to parse structured findings |
| python/registry/cli.py:2216 | New `_orchestrate_reviews_with_correction()` with retry loop |
| python/registry/cli.py:2324 | Add `--auto-fix`, `--max-retries` args to cmd_plan_review |
| python/registry/cli.py (new) | `_run_correction_pass()` function |
| python/registry/cli.py (new) | `_check_dependencies()` helper |
| .claude/commands/cw9_plan_fix.md (new) | Correction agent prompt file |

## Implementation Order

1. **`_extract_findings()`** — Parse structured findings from review result text. This is the foundation.
2. **`_check_dependencies()`** — Per-pass gate logic based on dependency graph.
3. **`_run_correction_pass()`** — Spawn correction agent via `query()`.
4. **`_orchestrate_reviews_with_correction()`** — Main loop with retries.
5. **Update `cmd_plan_review()`** — Add CLI args, route to new orchestration function.
6. **Write `cw9_plan_fix.md`** — Correction agent prompt file.
7. **Update `cw9_plan_review.md`** — Document new `--auto-fix` workflow.

## CW9 Mention Summary

Functions: _orchestrate_reviews(), _run_review_pass(), _parse_verdict(), _aggregate_verdicts(), cmd_plan_review(), _detect_review_mode(), _add_utility_commands(), main()
Files: python/registry/cli.py, .claude/commands/cw9_review_01_artifacts.md, .claude/commands/cw9_review_02_coverage.md, .claude/commands/cw9_review_03_abstraction_gap.md, .claude/commands/cw9_review_04_interaction.md, .claude/commands/cw9_review_05_imports.md, .claude/commands/cw9_plan_review.md, .claude/commands/cw9_orchestrate.md, .claude/commands/cw9_implement.md
Directories: python/registry/, .claude/commands/
