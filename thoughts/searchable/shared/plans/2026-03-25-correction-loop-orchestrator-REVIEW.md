---
date: 2026-03-25T00:00:00Z
researcher: FuchsiaRaven
topic: "Correction Loop Orchestrator TDD Plan — CW9 Review"
tags: [review, cw9, orchestrator, correction-loop]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-25-tdd-correction-loop-orchestrator.md
---

# CW9 Plan Review: Correction Loop Orchestrator

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | **WARNING** | 1 — gwt-0098 missing sim traces |
| Status consistency | **WARNING** | 1 — plan says gwt-0098 "Verified" but traces missing |
| UUID validity | PASS | 0 — no UUIDs claimed (cli.py not in crawl.db) |
| Context file quality | PASS | 0 — all 20 files have Test Interface + Anti-Patterns |
| Bridge artifact match | PASS | 0 — pending full count validation (subagent) |
| Test-to-verifier mapping | **WARNING** | 2 gaps in plan's test specifications |
| Simulation trace coverage | **WARNING** | 1 — gwt-0098 has no traces to check |
| TLA+ invariant coverage | **WARNING** | 3 invariants not explicitly covered by plan tests |
| Dead code / scope | PASS | 0 — plan preserves existing code, only adds |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Context | Plan Says | Actual |
|-----|------|--------|--------|---------|-----------|--------|
| gwt-0080 | Y | Y | Y | Y | Verified | Verified |
| gwt-0081 | Y | Y | Y | Y | Verified | Verified |
| gwt-0082 | Y | Y | Y | Y | Verified | Verified |
| gwt-0083 | Y | Y | Y | Y | Verified | Verified |
| gwt-0084 | Y | Y | Y | Y | Verified | Verified |
| gwt-0085 | Y | Y | Y | Y | Verified | Verified |
| gwt-0086 | Y | Y | Y | Y | Verified | Verified |
| gwt-0087 | Y | Y | Y | Y | Verified | Verified |
| gwt-0088 | Y | Y | Y | Y | Verified | Verified |
| gwt-0089 | Y | Y | Y | Y | Verified | Verified |
| gwt-0090 | Y | Y | Y | Y | Verified | Verified |
| gwt-0091 | Y | Y | Y | Y | Verified | Verified |
| gwt-0092 | Y | Y | Y | Y | Verified | Verified |
| gwt-0093 | Y | Y | Y | Y | Verified | Verified |
| gwt-0094 | Y | Y | Y | Y | Verified | Verified |
| gwt-0095 | Y | Y | Y | Y | Verified | Verified |
| gwt-0096 | Y | Y | Y | Y | Verified | Verified |
| gwt-0097 | Y | Y | Y | Y | Verified | Verified |
| gwt-0098 | Y | **N** | Y | Y | Verified | **Partial** |
| gwt-0099 | Y | Y | Y | Y | Verified | Verified |
| gwt-0100 | Y | Y | Y | Y | Verified | Verified |
| gwt-0101 | Y | Y | Y | Y | Verified | Verified |
| gwt-0102 | N | N | N | Y | Failed | Failed |
| gwt-0103 | N | N | N | Y | Failed | Failed |
| gwt-0104 | N | N | N | Y | Failed | Failed |

## UUID Validity

No `depends_on` UUIDs in any registered GWT — cli.py functions are not in crawl.db (0 records). This is consistent with the plan's statement but is a **latent gap**: without crawl.db bindings, gwt-author cannot verify that GWTs map to real code. Not blocking for this plan since the target file (cli.py:2099-2400) was read directly during research.

## TLA+ Invariant Coverage

### gwt-0090: FAIL triggers correction (Step 4)

| Invariant | TLC Checked | Plan Test? | Notes |
|-----------|-------------|------------|-------|
| ValidVerdict | Y | Implicit | Verdict type checks |
| ValidPhase | Y | Implicit | Phase transition checks |
| CorrectionCountInvariant | Y | Yes | "correction agent only spawned when attempt < max_retries" |
| AttemptGuard | Y | Yes | "Retry loop respects max_retries bound" |
| FindingsExtractedBeforeCorrection | Y | **WEAK** | Plan mentions "findings" but no explicit test that extraction happens BEFORE correction |
| CorrectionRequiresAutoFix | Y | Yes | "verdict is FAIL" requirement |
| NoCorrectionOnLastAttempt | Y | Yes | "Pass exhausts retries" test |
| SequentialOrder | Y | Implicit | Loop structure enforces this |
| NoSpuriousCorrections | Y | **NO** | No explicit test that correction count matches expected pattern |

### gwt-0093: Dependency blocking (Step 1)

| Invariant | TLC Checked | Plan Test? | Notes |
|-----------|-------------|------------|-------|
| DirectBlockInvariant | Y | Yes | Direct blocking tested |
| BlockedNeverRan | Y | Implicit | Blocked passes skipped |
| NeverRunBlocked | Y | Yes | "Dependents skipped" |
| ScheduledOnlySatisfied | Y | Yes | Gate logic tested |
| PartialSuccessInvariant | Y | Implicit | Mixed results tested |
| BlockedDistinctFromFail | Y | **NO** | Plan doesn't explicitly test that blocked != FAIL semantics differ |
| FinalAllResolved | Y | Implicit | All passes reach terminal |
| TransitiveBlockWitness | Y | Yes | "Transitive" cascade tested |

### gwt-0095: Parallel dispatch (Step 4)

| Invariant | TLC Checked | Plan Test? | Notes |
|-----------|-------------|------------|-------|
| ArtifactsGate | Y | Yes | Artifacts must pass first |
| PhaseBarrier | Y | Yes | coverage+interaction before abstraction_gap |
| BudgetNonNegative | Y | Implicit | Budget can't go negative |
| AttemptBounded | Y | Yes | max_retries bound |
| CoverageGated | Y | Yes | Coverage depends on artifacts |
| InteractionGated | Y | Yes | Interaction depends on artifacts |
| ImportsAfterPhase3 | Y | Yes | Imports last |
| ConcurrentUnblockInvariant | Y | Yes | "dispatched concurrently" |
| IndependentBudgetBounds | Y | Yes | "independent retry budgets" |

### gwt-0098: Aggregate with blocked (Step 6)

| Invariant | TLC Checked | Plan Test? | Notes |
|-----------|-------------|------------|-------|
| BlockedImpliesFail | Y | Yes | "blocked treated as fail for overall" |
| FailImpliesFail | Y | Yes | Standard |
| BucketPartition | Y | Yes | "Three-bucket summary" |
| BucketDisjoint | Y | Implicit | Partition implies disjoint |
| BlockedNotStuckOn | Y | Yes | "blocked doesn't generate new stuck_on" |
| FailIsStuckOn | Y | Yes | Root FAIL is stuck_on |
| StuckOnExactlyFails | Y | Implicit | |
| WarningInPassed | Y | Implicit | |
| PassInPassed | Y | Implicit | |
| FailInFailed | Y | Implicit | |
| BlockedInBlocked | Y | Implicit | |
| NoFailOrBlockedMeansPassOrWarning | Y | Implicit | |
| OverallIsValid | Y | Implicit | |
| BucketsSubsetPasses | Y | Implicit | |

### gwt-0082: CLI dispatch (Step 5)

| Invariant | TLC Checked | Plan Test? | Notes |
|-----------|-------------|------------|-------|
| ValidDispatchTarget | Y | Yes | Dispatch to correct function |
| ValidPhase | Y | Implicit | |
| ValidCalledFunction | Y | Yes | |
| DefaultDispatch | Y | Yes | "no --auto-fix = identical behavior" |
| NoCorrection | Y | Yes | No correction agents without --auto-fix |
| BackwardCompatible | Y | Yes | Explicit backward compat test |
| NoCorrectionFunctionDispatched | Y | Yes | |
| CorrectExitCode | Y | Yes | Exit code mapping |
| BoundedExecution | Y | Implicit | |

## Issues

### Critical (must fix before implementation)

None.

### Warnings (should fix)

1. **Missing sim traces for gwt-0098**: The `gwt-0098_sim_traces.json` file does not exist. The TLA+ spec and bridge artifacts exist, so TLC verified the invariants, but without simulation traces, `cw9 gen-tests` cannot generate concrete test scenarios for the aggregation-with-blocked behavior. The bridge artifacts alone provide verifier names, but traces provide the concrete state transitions.
   - Impact: Test generation for Step 6 (`_aggregate_verdicts()` update) will lack concrete examples
   - Fix: Re-run `cw9 loop gwt-0098 . --context-file .cw9/context/gwt-0098.md` to regenerate traces, or hand-write tests from the 14 bridge verifiers

2. **FindingsExtractedBeforeCorrection invariant not explicitly tested**: gwt-0090's TLA+ spec verifies that findings must be extracted BEFORE correction is spawned (a critical ordering constraint). The plan's Step 4 mentions findings but doesn't have an explicit test that `_extract_findings()` is called before `_run_correction_pass()`.
   - Impact: Implementation could accidentally swap the ordering
   - Fix: Add explicit test: "Given FAIL verdict, verify _extract_findings() is called, THEN _run_correction_pass() receives its output"

3. **NoSpuriousCorrections invariant not tested**: gwt-0090 verifies that correction counts match the expected pattern (no corrections fire that aren't needed). The plan has no explicit test for this.
   - Impact: Implementation could accidentally spawn correction agents for non-FAIL verdicts
   - Fix: Add test: "Given a run where pass 1 = PASS, pass 2 = FAIL+retry→PASS, verify exactly 1 correction was spawned total"

4. **BlockedDistinctFromFail not explicitly tested**: gwt-0093 verifies that "blocked" is semantically distinct from "FAIL" (blocked means "didn't run because upstream failed"). The plan's Step 6 mentions three buckets but doesn't test the semantic distinction.
   - Impact: Implementation might conflate blocked and failed verdicts
   - Fix: Add test: "Given artifacts=FAIL, verify coverage result has verdict='blocked' (not 'fail')"

5. **No crawl.db UUIDs for target functions**: cli.py functions aren't in crawl.db, so GWT `depends_on` fields are empty. This means gwt-author couldn't verify function existence.
   - Impact: Low — the code was read directly during research. But future re-verification (`cw9 stale`) won't detect code drift.
   - Fix: Run `cw9 crawl python/registry/cli.py .` to ingest the functions, then update GWT `depends_on` fields

### Cosmetic (nice to fix)

1. **Plan frontmatter git_commit is stale**: The plan says `git_commit: bfdf819` but the actual commit with artifacts is `40fe81c`. Not blocking but should be updated for traceability.
   - Fix: Update frontmatter to `git_commit: 40fe81c`

2. **Artifact paths use self-hosting layout but plan review template expects external layout**: The plan correctly uses `templates/pluscal/instances/` and `python/tests/generated/`, which is the self-hosting convention. The review template expected `.cw9/specs/` and `.cw9/bridge/`. This is not an error in the plan — it's a template mismatch for self-hosting projects.

3. **gwt-0080 and gwt-0081 context files were overwritten**: The subagents that wrote context files also overwrote the pre-existing gwt-0080 and gwt-0081 context files with expanded content. This is likely fine (expanded is better than sparse) but should be noted.

## Approval Status

- [ ] **Ready for `/cw9_implement`** — no critical issues
- [x] **Needs minor revision** — 4 warnings about test gaps and 1 missing trace file
- [ ] **Needs major revision**
- [ ] **Needs re-pipeline** — artifacts missing or stale

### Recommended Actions Before Implementation

1. **Re-run gwt-0098 pipeline** to generate sim traces: `cw9 loop gwt-0098 . --context-file .cw9/context/gwt-0098.md`
2. **Add 3 explicit test specifications** to the plan for invariants: FindingsExtractedBeforeCorrection, NoSpuriousCorrections, BlockedDistinctFromFail
3. **Update plan frontmatter** git_commit to 40fe81c
4. **(Optional)** Ingest cli.py to crawl.db for future stale detection
