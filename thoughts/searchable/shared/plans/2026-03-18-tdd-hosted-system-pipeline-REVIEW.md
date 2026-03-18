---
date: 2026-03-18T18:30:00Z
researcher: Claude Code (claude-opus-4-6)
topic: "Hosted System Pipeline TDD Plan — CW9 Review"
tags: [review, cw9, hosted, pipeline, tdd]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-18-tdd-hosted-system-pipeline.md
reviewed_detail: thoughts/searchable/shared/plans/2026-03-18-tdd-hosted-system-pipeline/step-11-heavy-workers.md
---

# CW9 Plan Review: Hosted System Pipeline TDD Plan

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | **pass** | 0 (gwt-0021 expected missing) |
| Status consistency | **pass** | 0 |
| UUID validity | **warning** | 1 naming mismatch, 6 skeletons |
| Bridge artifact match | **pass** | 0 — all 26 GWTs match exactly |
| Test-to-verifier mapping | **fail** | 70 gaps across step-11 detail |
| Simulation trace coverage | **warning** | 11 edge cases not in tests |
| TLA+ invariant coverage | **fail** | ~55% of invariants uncovered |
| Dead code / scope | **pass** | 0 |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Plan Says | Actual |
|-----|------|--------|--------|-----------|--------|
| gwt-0001 | exists | exists | exists | verified | verified |
| gwt-0002 | exists | exists | exists | verified | verified |
| gwt-0003 | exists | exists | exists | verified | verified |
| gwt-0004 | exists | exists | exists | verified | verified |
| gwt-0005 | exists | exists | exists | verified | verified |
| gwt-0006 | exists | exists | exists | verified | verified |
| gwt-0007 | exists | exists | exists | verified | verified |
| gwt-0008 | exists | exists | exists | verified | verified |
| gwt-0009 | exists | exists | exists | verified | verified |
| gwt-0010 | exists | exists | exists | verified | verified |
| gwt-0011 | exists | exists | exists | verified | verified |
| gwt-0012 | exists | exists | exists | verified | verified |
| gwt-0013 | exists | exists | exists | verified | verified |
| gwt-0014 | exists | exists | exists | verified | verified |
| gwt-0015 | exists | exists | exists | verified | verified |
| gwt-0016 | exists | exists | exists | verified | verified |
| gwt-0017 | exists | exists | exists | verified | verified |
| gwt-0018 | exists | exists | exists | verified | verified |
| gwt-0019 | exists | exists | exists | verified | verified |
| gwt-0020 | exists | exists | exists | verified | verified |
| gwt-0021 | **missing** | **missing** | **missing** | failed (8 attempts) | missing — expected |
| gwt-0022 | exists | exists | exists | verified | verified |
| gwt-0023 | exists | exists | exists | verified | verified |
| gwt-0024 | exists | exists | exists | verified | verified |
| gwt-0025 | exists | exists | exists | verified | verified |
| gwt-0026 | exists | exists | exists | verified | verified |
| gwt-0027 | exists | exists | exists | verified | verified |

All 26 verified GWTs have complete artifact sets. gwt-0021 is correctly marked as failed.

## UUID Validity

| UUID (short) | Plan Says | crawl.db Says | Match? | Extraction |
|---|---|---|---|---|
| `45c95d8c` | run_loop @ loop_runner.py:220 | run_loop @ loop_runner.py | **yes** | SKELETON |
| `924330b9` | write_result_file @ status.py:61 | write_result_file @ status.py | **yes** | SKELETON |
| `1b2e7529` | ProjectContext @ context.py:22 | **from_target** @ context.py | **MISMATCH** | SKELETON |
| `3841686c` | self_hosting @ context.py:47 | self_hosting @ context.py | **yes** | SKELETON |
| `7392f42f` | external @ context.py:108 | external @ context.py | **yes** | SKELETON |
| `9c450f7f` | installed @ context.py:131 | installed @ context.py | **yes** | SKELETON |

### UUID Issues

1. **`1b2e7529` naming mismatch**: Plan claims this is `ProjectContext` (the class at line 22) but crawl.db records it as `from_target` (the classmethod). The UUID is valid and points to the right file, but the function_name in the plan is wrong. Impact: low — the depends_on binding is to the right code region, just mislabeled.

2. **All 6 UUIDs are SKELETON_ONLY**: None of the referenced crawl.db records have been fully extracted (IN:DO:OUT behavioral data is missing). This means the GWT specs were authored with only skeleton context from crawl.db. Impact: medium — the specs are verified regardless, but if the crawl data were richer, the specs might have been more precise.

## Bridge Artifact Validation

All 26 verified GWT bridge artifacts match the plan exactly on all three dimensions:

| GWT | Plan Ops | Actual Ops | Plan Verifiers | Actual Verifiers | Plan Assertions | Actual Assertions | Status |
|---|---|---|---|---|---|---|---|
| gwt-0001 | 7 | 7 | 11 | 11 | 11 | 11 | MATCH |
| gwt-0002 | 6 | 6 | 6 | 6 | 6 | 6 | MATCH |
| gwt-0003 | 2 | 2 | 15 | 15 | 15 | 15 | MATCH |
| gwt-0004 | 6 | 6 | 8 | 8 | 8 | 8 | MATCH |
| gwt-0005 | 9 | 9 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0006 | 9 | 9 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0007 | 0 | 0 | 13 | 13 | 13 | 13 | MATCH |
| gwt-0008 | 7 | 7 | 10 | 10 | 10 | 10 | MATCH |
| gwt-0009 | 0 | 0 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0010 | 6 | 6 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0011 | 6 | 6 | 13 | 13 | 13 | 13 | MATCH |
| gwt-0012 | 6 | 6 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0013 | 12 | 12 | 11 | 11 | 11 | 11 | MATCH |
| gwt-0014 | 7 | 7 | 8 | 8 | 8 | 8 | MATCH |
| gwt-0015 | 7 | 7 | 15 | 15 | 15 | 15 | MATCH |
| gwt-0016 | 15 | 15 | 8 | 8 | 8 | 8 | MATCH |
| gwt-0017 | 5 | 5 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0018 | 8 | 8 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0019 | 6 | 6 | 9 | 9 | 9 | 9 | MATCH |
| gwt-0020 | 8 | 8 | 11 | 11 | 11 | 11 | MATCH |
| gwt-0022 | 5 | 5 | 10 | 10 | 10 | 10 | MATCH |
| gwt-0023 | 9 | 9 | 7 | 7 | 7 | 7 | MATCH |
| gwt-0024 | 6 | 6 | 10 | 10 | 10 | 10 | MATCH |
| gwt-0025 | 8 | 8 | 12 | 12 | 12 | 12 | MATCH |
| gwt-0026 | 6 | 6 | 7 | 7 | 7 | 7 | MATCH |
| gwt-0027 | 9 | 9 | 6 | 6 | 6 | 6 | MATCH |

**Total mismatches: 0.**

## Verifier Coverage — Step 11 Detail File

The step-11 detail file (`step-11-heavy-workers.md`) is the focus of this review. It covers 13 GWTs with 128 total verifiers. The tests in the detail file cover approximately 58 of these verifiers, leaving **70 verifiers without explicit test assertions**.

### gwt-0005: Single Client Per GWT (9 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| TypeOK | — | **NO** |
| AtMostOneClientCreated | `call_log.count("make_client") == 1` | yes |
| ClientHandleConsistent | — | **NO** |
| SingleClientReusedForAllAttempts | `call_log.count("make_client") == 1` (implicit) | partial |
| RetriesBounded | — | **NO** |
| ContextGrowsWithAttempts | `messages_seen is monotonically increasing` | yes |
| SuccessRequiresClient | — | **NO** |
| ExhaustionRequiresClient | — | **NO** |
| JobTerminatedCorrectly | — | **NO** |

**Coverage: 3/9 (33%)**

### gwt-0006: Safe Disconnect Lifetime (9 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| ClientStates | — | **NO** |
| LoopOutcomes | — | **NO** |
| ClientValid | — | **NO** |
| OutcomeValid | — | **NO** |
| RetryBounded | — | **NO** |
| SafeDisconnectGuarantee | `client.safe_disconnect.called` (pass + fail) | yes |
| FinallyAlwaysEntered | `client.safe_disconnect.called` (exception) | yes |
| NoSessionAfterExit | `verify client has no active connection` | yes |
| TypeInvariant | — | **NO** |

**Coverage: 3/9 (33%)**

### gwt-0007: GWT Independence (13 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| WorkerStates | — | **NO** |
| AllStatesValid | — | **NO** |
| NoSharedSDKClient | `clients[0] is not clients[1]` | yes |
| NoSharedDAG | `Worker 2's DAG is unaffected` | yes |
| NoSharedCrawlStore | `Worker 2 doesn't see it` | yes |
| ResourceIdsMonotonicallyGrow | — | **NO** |
| AllocatedClientIds | — | **NO** |
| AllocatedDagIds | — | **NO** |
| AllocatedConnIds | — | **NO** |
| ClientCountConsistent | — | **NO** |
| DagCountConsistent | — | **NO** |
| ConnCountConsistent | — | **NO** |
| IsolationInvariant | implicit (NoSharedSDKClient + NoSharedDAG + NoSharedCrawlStore) | partial |

**Coverage: 3/13 (23%)** — but the 3 core isolation verifiers are covered, and 7 of the uncovered are consistency-count helpers.

### gwt-0008: Credential Injection (10 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| TypeInvariant | — | **NO** |
| BoundedExecution | — | **NO** |
| CredentialsFromInjectedOnly | `it used "test-token-123"` | yes |
| ClientReadyImpliesInjectedEnv | implicit | partial |
| NoClientFromInheritedEnv | — | **NO** |
| NoClientFromMissingEnv | `pytest.raises(EnvironmentError)` | yes |
| InheritedNeverUsedAsCredentials | — | **NO** |
| TaintedEnvBlocksClientInit | — | **NO** |
| MissingEnvBlocksClientInit | `pytest.raises(EnvironmentError)` | yes |
| ClientInitRequiresExclusiveInjectedSource | — | **NO** |

**Coverage: 3/10 (30%)** — Missing the "tainted env" path (inherited-only credentials).

### gwt-0009: TLC Temp Dir Isolation (9 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| AllStates | — | **NO** |
| ValidStates | — | **NO** |
| TempDirIsolation | `unique dir per call` | yes |
| UploadBeforeExit | `storage has the spec files` | yes |
| FilesReadBeforeUpload | implicit (upload after pass) | partial |
| UploadRequiresTempDir | — | **NO** |
| NoUploadOnFail | — | **NO** |
| TempDirOwnedByJob | `unique dir per call` (partial) | partial |
| BoundedExecution | — | **NO** |

**Coverage: 3/9 (33%)** — Missing `NoUploadOnFail` is significant (sim traces show fail→no upload pattern).

### gwt-0011: Simulation Traces on PASS (13 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| SimTracesFile | — | **NO** |
| TypeInvariant | — | **NO** |
| ValidState | — | **NO** |
| BoundedExecution | — | **NO** |
| SimTimeoutBounded | — | **NO** |
| SimCalledOnlyAfterPass | `run_tlc_simulate called` (on PASS) | yes |
| TlaFilePresentWhenSimCalled | — | **NO** |
| TracesWrittenImpliesSimCalled | `check file exists` (implicit) | partial |
| TracesFileCorrect | `specs/{gwt_id}_sim_traces.json` | yes |
| UploadBatchContainsTraces | `upload includes sim_traces` | yes |
| ContainerExitSafety | — | **NO** |
| NonPassSkipsSimulation | `run_tlc_simulate NOT called` | yes |
| OrderingGuarantee | — | **NO** |

**Coverage: 4/13 (31%)**

### gwt-0014: Scheduler Requirements (8 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| HeavyTLANodes | — | **NO** |
| JobStates | — | **NO** |
| ValidState | — | **NO** |
| SchedulerSafetyInvariant | `test_requires_java_jre` + `test_requires_tla2tools` | partial |
| NoNonHeavyTLASelected | implicit | partial |
| TimeoutBudgetRespected | `Timeout >= 8 * (300s + 60s) = 2880s` | yes |
| RetryBound | — | **NO** |
| CompletionImpliesWithinBudget | implicit | partial |

**Coverage: 2/8 (25%)** — Tests are placeholder (`pass` bodies).

### gwt-0015: Gen-Tests Heavy Worker (15 verifiers)

Not explicitly tested in step-11 detail file (covered by gwt-0016 tests).

**Coverage: 0/15 (0%)** in step-11 detail.

### gwt-0016: Gen-Tests 3-Pass Structure (8 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| ValidPhase | — | **NO** |
| PassesAreOrdered | `prompts are plan, review, codegen in order` | yes |
| ExactlyThreeLLMCallsBeforeExtract | `call_count == 3` | yes |
| NoExtraLLMCallsInMainPasses | — | **NO** |
| RetryOnlyAfterVerifyFail | `pass` (placeholder) | **NO** |
| RetryBounded | — | **NO** |
| TerminationMeansSuccessOrExhausted | — | **NO** |
| SuccessImpliesVerified | `pass` (placeholder) | **NO** |

**Coverage: 2/8 (25%)** — Two tests have `pass` bodies (placeholders, not real assertions).

### gwt-0017: Crawl Worker (9 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| AllExtracted | `pass` (placeholder) | **NO** |
| AtMostOneSDKCallPerRecord | `pass` (placeholder) | **NO** |
| ExactlyOneCallForExtractedRecords | — | **NO** |
| UploadOnlyAfterAllExtracted | `pass` (placeholder) | **NO** |
| PassedOnlyAfterUpload | — | **NO** |
| BoundedExecution | — | **NO** |
| CompletionCorrectness | — | **NO** |
| ExactlyOneCallAtCompletion | — | **NO** |
| NoSkeletonRecordLeftBehind | — | **NO** |

**Coverage: 0/9 (0%)** — All three tests are placeholders with `pass` bodies.

### gwt-0025: GWT-Author Worker (12 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| Phases | — | **NO** |
| ValidPhase | — | **NO** |
| LLMNeverExceedsOne | implicit in `test_exactly_one_llm_call` | partial |
| ExactlyOneLLMAtCompletion | `pass` (placeholder) | **NO** |
| PromptBuiltBeforeLLM | — | **NO** |
| ParseBeforeValidation | — | **NO** |
| ValidationBeforeReturn | `pass` (placeholder) | **NO** |
| GwtJsonSetOnSuccess | — | **NO** |
| ReturnedOnSuccess | — | **NO** |
| TimeBound | `pass` (placeholder) | **NO** |
| BoundedElapsed | — | **NO** |
| PhaseOrderRespected | — | **NO** |

**Coverage: 0/12 (0%)** — All three tests are placeholders with `pass` bodies.

### gwt-0026: Loop Context Query (7 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| ValidState | — | **NO** |
| BoundedExecution | — | **NO** |
| PromptBuiltImpliesContextFormatted | — | **NO** |
| ContextFormattedImpliesDAGQueried | implicit in `test_dag_nodes_retrieved` | partial |
| NoCrawlDbMeansNoFnRecords | implicit in `test_no_crawl_db_builds_dag_context_only` | partial |
| NoCrawlDbNoError | `pass` (placeholder) | **NO** |
| PromptReadyIsTerminal | — | **NO** |

**Coverage: 0/7 (0%)** — All three tests are placeholders with `pass` bodies.

### gwt-0027: Retry Prompt Builder (6 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| BoundedExecution | — | **NO** |
| RetryPromptCompleteness | implicit in `test_includes_counterexample_trace` + `test_includes_error_classification` | partial |
| AllHistoryEntriesComplete | — | **NO** |
| SentImpliesNonEmptyHistory | — | **NO** |
| HistoryCountBelowAttemptNo | — | **NO** |
| FullCorrectionHistoryPreserved | `pass` (placeholder) | **NO** |

**Coverage: 0/6 (0%)** — All three tests are placeholders with `pass` bodies.

### Step-11 Verifier Coverage Summary

| GWT | Total Verifiers | Covered | Uncovered | Coverage |
|-----|----------------|---------|-----------|----------|
| gwt-0005 | 9 | 3 | 6 | 33% |
| gwt-0006 | 9 | 3 | 6 | 33% |
| gwt-0007 | 13 | 3 | 10 | 23% |
| gwt-0008 | 10 | 3 | 7 | 30% |
| gwt-0009 | 9 | 3 | 6 | 33% |
| gwt-0011 | 13 | 4 | 9 | 31% |
| gwt-0014 | 8 | 2 | 6 | 25% |
| gwt-0015 | 15 | 0 | 15 | 0% |
| gwt-0016 | 8 | 2 | 6 | 25% |
| gwt-0017 | 9 | 0 | 9 | 0% |
| gwt-0025 | 12 | 0 | 12 | 0% |
| gwt-0026 | 7 | 0 | 7 | 0% |
| gwt-0027 | 6 | 0 | 6 | 0% |
| **TOTAL** | **128** | **23** | **105** | **18%** |

## Trace Coverage

### gwt-0005: Single Client Per GWT

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path (ok on first attempt) | partial | make_client_called_once test covers this |
| Retry then success (fail, fail, ok) | yes | conv_context grows monotonically |
| Exhausted retries (all fail) | **NO** | job_outcome="exhausted" path untested |

### gwt-0006: Safe Disconnect Lifetime

| Trace Pattern | Test? | Notes |
|---|---|---|
| Pass on first attempt | yes | test_disconnect_on_pass |
| Fail on first attempt | yes | test_disconnect_on_fail |
| Exhausted retries (ExhaustCheck loop) | **NO** | ExhaustCheck reaching max without pass/fail untested |

### gwt-0008: Credential Injection

| Trace Pattern | Test? | Notes |
|---|---|---|
| env_missing (no CLAUDECODE) | yes | test_missing_claudecode_aborts |
| env_tainted (inherited only) | **NO** | Traces show this path; no test for inherited-credential rejection |
| Happy path (injected CLAUDECODE) | yes | test_claudecode_from_container_env |
| Both inherited+injected present | **NO** | Trace 10 shows injected wins; untested |

### gwt-0009: TLC Temp Dir Isolation

| Trace Pattern | Test? | Notes |
|---|---|---|
| PCal fails | **NO** | Trace 1 shows pcal_ok=FALSE → CleanupFail; no test for PCal failure path |
| PCal passes, TLC fails | **NO** | Trace 1 Job 2 shows this; untested |
| Both pass → upload | partial | test_verified_files_uploaded_on_pass |

### gwt-0011: Simulation Traces on PASS

| Trace Pattern | Test? | Notes |
|---|---|---|
| FAIL result (no simulation) | yes | test_non_pass_skips_simulation |
| PASS result (simulate + write + batch) | yes | Three tests cover this |
| upload_batch empty on FAIL | **NO** | Traces confirm; not explicitly tested |

### gwt-0014: Scheduler

| Trace Pattern | Test? | Notes |
|---|---|---|
| No qualified node → rejection | **NO** | Traces 1-3 all show rejection; no test |
| Qualified node → success with retries | **NO** | Trace 4 shows 10-retry loop; no test |

### gwt-0016: Gen-Tests 3-Pass

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path (all 3 passes succeed) | yes | test_exactly_three_llm_calls + test_pass_ordering |
| Retry after verify fail | **NO** | Placeholder test body |
| retries_exhausted=TRUE | **NO** | Not in first 3 traces; no test |

### gwt-0027: Retry Prompt Builder

| Trace Pattern | Test? | Notes |
|---|---|---|
| Success on first attempt (no retry) | **NO** | Trace 2 shows this; no test for "no retry prompt sent" |
| Single retry then success | **NO** | Trace 1; placeholder test |
| Double retry then success | **NO** | Trace 7; history grows to 2 entries; untested |

## TLA+ Invariant Coverage

### Key Invariant Categories Across All Step-11 GWTs

**Category 1: TypeOK / ValidState / AllStates** (13 invariants across 13 GWTs)
- These are type-correctness invariants ensuring variables stay within declared domains.
- **None have explicit test assertions.** These are implicitly tested by any test that exercises the state machine, but there's no defense against invalid intermediate states.
- **Recommendation**: Add at least one test per GWT that asserts the final state is in the valid set.

**Category 2: BoundedExecution** (10 invariants across 10 GWTs)
- Ensures step counts / elapsed time / retry counts stay within bounds.
- **None have explicit test assertions.**
- **Recommendation**: For heavy workers (gwt-0005, gwt-0014, gwt-0016, gwt-0017, gwt-0025), add timeout / retry-limit boundary tests.

**Category 3: Ordering / Sequencing** (15 invariants)
- Invariants like `PassesAreOrdered`, `PromptBuiltBeforeLLM`, `ValidationBeforeReturn`, `OrderingGuarantee`.
- **Only 2 are tested** (PassesAreOrdered, ExactlyThreeLLMCallsBeforeExtract in gwt-0016).
- **Recommendation**: These are the strongest invariants — they constrain the implementation order. Each should have a test.

**Category 4: Safety / Isolation** (20 invariants)
- Invariants like `NoSharedSDKClient`, `NoUploadOnFail`, `NonPassSkipsSimulation`, `TaintedEnvBlocksClientInit`.
- **About 8 are tested.** The core isolation invariants (gwt-0007) are covered, but many safety guards are not.
- **Recommendation**: Prioritize `NoUploadOnFail` (gwt-0009), `TaintedEnvBlocksClientInit` (gwt-0008), and `ContainerExitSafety` (gwt-0011).

**Category 5: Completion / Terminal** (12 invariants)
- Invariants like `CompletionCorrectness`, `TerminationMeansSuccessOrExhausted`, `PromptReadyIsTerminal`.
- **0 are tested.**
- **Recommendation**: Add terminal-state assertions to verify the system reaches the correct final state.

## Issues

### Critical (must fix before implementation)

1. **70+ verifiers uncovered in step-11 detail file**: The step-11 detail file covers only ~18% of the 128 bridge verifiers across its 13 GWTs. 8 of the 13 GWTs have 0% verifier coverage because all their tests are placeholder `pass` bodies. These are formally verified invariants that the tests don't check — if the implementation violates them, tests won't catch it.
   - Impact: The primary value of the CW9 pipeline (TLA+ verification → bridge verifiers → tests) is broken for these GWTs.
   - Fix: Expand all placeholder tests with concrete assertions that map to bridge verifiers. For each GWT, every verifier should have at least one test assertion. Start with the 8 GWTs at 0% coverage: gwt-0015, gwt-0017, gwt-0025, gwt-0026, gwt-0027, gwt-0014, gwt-0016.

2. **gwt-0015 has no tests at all in step-11**: The gen-tests heavy-lang worker (15 verifiers) is mentioned in the step-11 header but has no test class in the detail file. Only gwt-0016 (3-pass structure) has tests, but gwt-0015 covers the full worker lifecycle.
   - Impact: 15 verifiers for the gen-tests worker lifecycle are completely untested.
   - Fix: Add `TestGenTestsWorkerLifecycle` class mapping to gwt-0015 bridge verifiers.

### Warnings (should fix)

1. **UUID `1b2e7529` labeled as `ProjectContext` but is `from_target`**: The plan says this UUID maps to `ProjectContext @ context.py:22` but crawl.db records it as `from_target`. The code at line 22 is the `class ProjectContext:` definition, but `from_target` is a classmethod on that class.
   - Impact: Misleading reference in the plan; the depends_on binding still points to the right file.
   - Fix: Update plan Step 2 depends_on to say `from_target @ context.py` instead of `ProjectContext @ context.py:22`.

2. **All 6 referenced UUIDs are SKELETON_ONLY**: None of the crawl.db records referenced in the plan's depends_on fields have been fully extracted (no IN:DO:OUT behavioral data). The GWT specs were authored with skeleton-level context only.
   - Impact: The formal specs are verified regardless, but richer crawl data could have produced more precise GWT specifications.
   - Fix: Consider running `cw9 crawl python/registry` before implementation to fill in behavioral data, then re-check if any GWT specs need updating.

3. **Sim trace edge cases not in tests**: 11 significant trace patterns identified across step-11 GWTs have no corresponding tests:
   - gwt-0005: exhausted retries path
   - gwt-0006: ExhaustCheck reaching max without pass/fail
   - gwt-0008: env_tainted path (inherited-only credentials)
   - gwt-0008: both inherited+injected present
   - gwt-0009: PCal failure path, PCal-pass-TLC-fail path
   - gwt-0011: upload_batch empty on FAIL
   - gwt-0014: node rejection, success with retries
   - gwt-0027: success-on-first-attempt (no retry prompt sent), multi-retry history accumulation
   - Fix: Add test cases for each identified trace pattern.

4. **Main plan step-11 tests are also placeholders**: The main plan's `test_heavy_workers.py` (lines 1512-1551) has 6 tests that are all placeholder `pass` bodies with comments saying "Placeholder — full implementation in Step 11 detail file". The detail file partially fills these in but many remain as comments/pseudocode rather than executable tests.
   - Fix: When implementing, convert all pseudocode comments to real assertions.

### Cosmetic (nice to fix)

1. **Plan status is "draft" but could be "review"**: All 26 verified GWTs have complete artifacts. The plan is comprehensive. Status could be upgraded to "review" since the pipeline is complete.
   - Fix: Update frontmatter `status: draft` → `status: review`.

2. **Step-11 detail file test classes use pseudocode comments**: Several test methods contain comments like `# Assert call_log.count("make_client") == 1` instead of actual assertions. These should be either real code or explicitly marked as implementation notes.
   - Fix: Either make them real `assert` statements or mark them as `# TODO: implement`.

## Approval Status

- [ ] **Ready for `/cw9_implement`** — no critical issues
- [ ] **Needs minor revision** — warnings should be addressed
- [x] **Needs major revision** — critical issues must be resolved: step-11 detail file has 70+ uncovered verifiers and 8 GWTs at 0% test-to-verifier coverage
- [ ] **Needs re-pipeline** — artifacts are missing or stale
