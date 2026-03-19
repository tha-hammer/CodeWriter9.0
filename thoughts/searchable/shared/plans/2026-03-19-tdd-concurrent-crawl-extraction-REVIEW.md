---
date: 2026-03-19T14:00:00Z
researcher: DustyForge
topic: "Concurrent Crawl Extraction Pipeline TDD Plan — CW9 Review"
tags: [review, cw9, concurrency, asyncio, crawl-pipeline]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-19-tdd-concurrent-crawl-extraction.md
---

# CW9 Plan Review: Concurrent Crawl Extraction Pipeline

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | **pass** | 0 |
| Status consistency | **warn** | 2 |
| UUID validity | **pass** | 0 |
| Bridge artifact match | **pass** | 0 |
| Test-to-verifier mapping | **fail** | 28 gaps |
| Simulation trace coverage | **warn** | 2 gaps |
| TLA+ invariant coverage | **fail** | 28 gaps |
| Dead code / scope | **pass** | 0 |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Plan Says | Actual |
|-----|------|--------|--------|-----------|--------|
| gwt-0008 | exists | exists (10) | exists | verified | verified |
| gwt-0014 | exists | exists (10) | exists | verified | verified |
| gwt-0015 | exists | exists (10) | exists | verified | verified |
| gwt-0016 | exists | exists (10) | exists | verified | verified |
| gwt-0018 | exists | exists (10) | exists | verified | verified |
| gwt-0022 | exists | exists (10) | exists | verified | verified |
| gwt-0019 | **MISSING** | **MISSING** | **MISSING** | referenced in Step 5 | **no artifacts** |
| gwt-0027 | **MISSING** | **MISSING** | **MISSING** | referenced in TestSweepDuplicateSkip | **no artifacts** |

## UUID Validity

All 10 `depends_on` UUIDs exist in `./crawl.db` with correct function names and file paths. All are `SKELETON_ONLY` (pre-extraction).

| UUID (short) | Plan Says | crawl.db Says | Match? |
|---|---|---|---|
| `79b09e73` | `_build_llm_fn` @ cli.py:1115 | `_build_llm_fn` @ cli.py | **yes** |
| `8cea6619` | `_build_extract_fn` @ cli.py:1232 | `_build_extract_fn` @ cli.py | **yes** |
| `f9ef9505` | `_extract_json_object` @ cli.py:1188 | `_extract_json_object` @ cli.py | **yes** |
| `f95fdf5c` | `run` @ crawl_orchestrator.py:303 | `run` @ crawl_orchestrator.py | **yes** |
| `06be8c8b` | `_dfs_extract` @ crawl_orchestrator.py:270 | `_dfs_extract` @ crawl_orchestrator.py | **yes** |
| `b14a9b59` | `extract_one` @ crawl_orchestrator.py:95 | `extract_one` @ crawl_orchestrator.py | **yes** |
| `f39134fd` | `_sweep_remaining` @ crawl_orchestrator.py:328 | `_sweep_remaining` @ crawl_orchestrator.py | **yes** |
| `978fd5d2` | `get_pending_uuids` @ crawl_store.py:412 | `get_pending_uuids` @ crawl_store.py | **yes** |
| `574594b2` | `upsert_record` @ crawl_store.py:284 | `upsert_record` @ crawl_store.py | **yes** |
| `cd8e7329` | `cmd_crawl` @ cli.py:956 | `cmd_crawl` @ cli.py | **yes** |

**Note**: The crawl.db is at `./crawl.db` (project root), not `.cw9/crawl.db` (which has 0 records). The plan's `cw9_project` says `. (this IS the cw9 codebase)` — this is consistent, but the `.cw9/crawl.db` being empty while `./crawl.db` has 332 records suggests the CW9 data directory may need clarification.

## Verifier Coverage

### gwt-0008: Async Extract Function (12 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| AllStates | — | implicit (state enum, not testable) |
| TerminalStates | — | implicit |
| ValidState | — | implicit |
| ClientNeverConstructed | `mock_q.assert_called_once()` (no Client) | **yes** |
| OnlySDKQueryUsed | — | **NO** — no test verifies `query` import is used exclusively |
| QueryParamsValid | `assert opts.allowed_tools == []`, etc. | **yes** |
| CollectionTypeIntegrity | — | **NO** — no test checks text block collection logic |
| ParseImpliesNonEmpty | — | **NO** — no test checks `raw` is non-empty before parse |
| FnRecordReturnedOnSuccess | `assert isinstance(result, FnRecord)` | **yes** |
| ParseErrorMeansNoRecord | `pytest.raises(ValueError)` | **yes** |
| ReturnImpliesParseSuccess | — | **NO** — no test explicitly checks parse succeeded when record returned |
| ReturnImpliesCollected | — | **NO** — no test verifies collection happened before return |

**5 uncovered verifiers** (excluding 3 type/state invariants that are structural).

### gwt-0014: Semaphore-Bounded Concurrent Sweep (7 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| ConcurrencyBound | `assert max_concurrent <= 3` | **yes** |
| SemNonNegative | — | **NO** — no test checks semaphore count stays >= 0 |
| SemaphoreConservation | — | **NO** — no test verifies acquire/release symmetry |
| PerTaskAtMostOnce | — | **NO** — no test checks each UUID processed exactly once |
| AcqBeforeRel | — | **NO** — no test verifies acquire always precedes release |
| WhenCompleteSymmetric | — | **NO** — no test verifies final semaphore value = initial |
| AllInvariants | — | composite (not directly testable) |

**5 uncovered verifiers**.

### gwt-0015: Error Isolation (9 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| SemaphoreValid | — | **NO** |
| SemaphoreConsistent | — | **NO** |
| NoCancellation | `assert result["extracted"] == 9` (others completed) | **yes** |
| ExceptionCapturedAsResult | `assert result["failed"] >= 1` | **yes** |
| AllOthersSucceedWhenGatherDone | — | **NO** — test checks count but not that all-others explicitly succeeded |
| GatherRequiresAllTasksDone | — | **NO** |
| FailedTaskSlotReleased | — | **NO** — no test verifies semaphore released after failure |
| CompletedOrFailedReleaseSemaphore | — | **NO** |
| RunningTasksHoldSemaphore | — | **NO** |

**7 uncovered verifiers**.

### gwt-0016: SQLite Safety (6 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| Phases | — | **NO** (structural) |
| TypeInvariant | — | **NO** (structural) |
| NoSimultaneousUpserts | start/end log pairing check | **yes** |
| UpsertLogNoDuplicates | — | **NO** — no test checks a UUID is upserted exactly once |
| CompletionImpliesUpserted | — | **NO** — no test checks that completed tasks had their record upserted |
| UpsertLogLengthMatchesCompletions | — | **NO** — no test verifies total upserts = total completions |

**3 uncovered verifiers** (excluding 2 structural).

### gwt-0018: Async Run Phase Ordering (7 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| TypeOK | — | **NO** (structural) |
| Phase1BeforePhase2 | `assert phase_log.index("main") < phase_log.index("util")` | **yes** |
| Phase1FlagAccurate | — | **NO** — no test checks the internal phase flag |
| SemaphoreNonNeg | — | **NO** |
| ConcurrencyBound | — | **NO** — covered in gwt-0014 tests, but not in gwt-0018 tests |
| DFSSequentialOrder | `assert max_concurrent == 1` | **yes** |
| NoPhase2BeforeSignal | — | partially (implied by Phase1BeforePhase2 test) |

**3 uncovered verifiers** (excluding 1 structural).

### gwt-0022: CLI Concurrency Flag (10 verifiers)

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| ValidStages | — | **NO** (structural) |
| TypeInvariant | — | **NO** (structural) |
| BoundedExecution | — | **NO** (structural) |
| DefaultApplied | `assert args.concurrency == 10` | **yes** |
| ValidationCorrect | — | **NO** — no test for invalid values (e.g., --concurrency 0 or -1) |
| ValuePreservedToCmdCrawl | `MockOrch.call_args` check | **yes** |
| OrchestratorPreservesValue | — | **NO** — tested indirectly via passthrough |
| SweepReceivesCorrectValue | — | **NO** — no test verifies sweep actually uses the concurrency value |
| NoErrorOnValidUserInput | — | **NO** — no test verifies no error on valid custom input |
| NoErrorOnDefault | — | **NO** — no test verifies no error on default |

**5 uncovered verifiers** (excluding 3 structural).

## Trace Coverage

### gwt-0008: Async Extract Function

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path (all 10 traces: Returned, parse_success=TRUE) | **yes** | All 3 success tests |
| Parse error path (modeled in spec: ParseError state) | **yes** | `test_parse_error_raises_value_error` |
| Empty response path | **NO** | Spec models it but no trace or test for empty collected_texts |

### gwt-0014: Semaphore-Bounded Concurrent Sweep

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path (10 tasks, all complete) | **yes** | `test_at_most_n_concurrent_extractions` |
| Various interleaving orderings | implicit | 10 traces show different task orderings |
| No blocking (sem never reaches 0) | **NO** | All traces have sem=task count, so no task blocks — plan tests use concurrency=3 with 10 tasks, which does exercise blocking |

### gwt-0015: Error Isolation

| Trace Pattern | Test? | Notes |
|---|---|---|
| One task fails, others succeed | **yes** | `test_one_failure_does_not_cancel_others` |
| All traces show task 10 as exception | — | Only one failure pattern modeled |

### gwt-0016: SQLite Safety

| Trace Pattern | Test? | Notes |
|---|---|---|
| Two coroutines, sequential upserts | **yes** | `test_upserts_never_interleave` |

### gwt-0018: Async Run Phase Ordering

| Trace Pattern | Test? | Notes |
|---|---|---|
| DFS then sweep, all complete | **yes** | `test_dfs_completes_before_sweep_begins` |

### gwt-0022: CLI Concurrency Flag

| Trace Pattern | Test? | Notes |
|---|---|---|
| Default value flow | **yes** | `test_default_concurrency_is_10` |
| Custom value flow (valid, e.g. 10) | **yes** | `test_custom_concurrency_parsed` |
| Invalid value flow (e.g. 5, 0) | **NO** | 6 of 10 traces end in Error stage — plan has no validation error test |
| Default overrides raw value | **NO** | Trace 6 shows `user_provided=FALSE` with `raw_concurrency=5` → `parsed_value=10` |

**Note**: The `.cfg` sets `MIN_CONCURRENCY=MAX_CONCURRENCY=DEFAULT_CONCURRENCY=10`, so "valid" means exactly 10. Values 0 and 5 fail validation. 6 of 10 traces exercise the error path, yet the plan has zero error/validation tests.

## TLA+ Invariant Coverage

All invariants in all 6 specs are properly wired to TLC via `.cfg` `INVARIANT` directives — they were all checked during model checking. The bridge verifiers map 1:1 to TLA+ `define` block invariants.

**Note**: gwt-0008 also has `THEOREM` assertions in-spec; the other 5 specs rely solely on `.cfg` directives (both approaches are valid for TLC).

Coverage gaps are identical to the Verifier Coverage section above.

### gwt-0022 cfg concern

The `.cfg` sets `MIN_CONCURRENCY = 10`, `MAX_CONCURRENCY = 10`, `DEFAULT_CONCURRENCY = 10` — all equal. This means TLC only checked the invariants for the case where min/max/default are all 10. The `ValidationCorrect` invariant (valid range check) was only verified for a single-value range. This reduces confidence that the validation logic generalizes correctly.

## Issues

### Critical (must fix before implementation)

1. **Missing gwt-0019 artifacts**: Step 5 references gwt-0019 for the async entry point, but no spec, traces, or bridge artifacts exist. Either run the pipeline for gwt-0019 or remove the GWT reference and treat Step 5 as a wiring-only step that doesn't need formal verification.
   - Impact: Step 5 has no verified invariant backing the "single asyncio.run() call" claim
   - Fix: Run `cw9 pipeline --gwt gwt-0019 .` or remove the GWT binding from Step 5

2. **Missing gwt-0027 artifacts**: TestSweepDuplicateSkip references gwt-0027 but no artifacts exist.
   - Impact: The "skip UUIDs already visited by DFS" behavior has no verified spec
   - Fix: Run `cw9 pipeline --gwt gwt-0027 .` or change the docstring to reference an existing GWT (e.g., gwt-0018 which models DFS-then-sweep ordering)

3. **28 uncovered bridge verifiers across 6 GWTs**: Formally verified invariants without test assertions. Most significant gaps:
   - `PerTaskAtMostOnce` (gwt-0014) — no test verifies each UUID is extracted exactly once
   - `FailedTaskSlotReleased` (gwt-0015) — no test verifies semaphore release after failure
   - `CompletionImpliesUpserted` (gwt-0016) — no test verifies completed tasks are upserted
   - `ValidationCorrect` (gwt-0022) — no test for invalid `--concurrency` values
   - Impact: These invariants are proven to hold in the TLA+ model but are unguarded in implementation
   - Fix: Add test assertions for at least the non-structural verifiers (exclude AllStates/TypeOK/etc.)

### Warnings (should fix)

1. **crawl.db location ambiguity**: `.cw9/crawl.db` has 0 records; `./crawl.db` has 332 records. The plan says `cw9_project: .` but doesn't clarify which DB the pipeline should use.
   - Impact: Future pipeline runs may target the wrong DB
   - Fix: Clarify in the plan that `./crawl.db` is the active database

2. **gwt-0008 simulation traces lack error path**: All 10 traces end in `state="Returned", parse_success=TRUE`. The spec models `ParseError` states, but no simulation trace demonstrates this path.
   - Impact: Low — TLC model checking covers all reachable states anyway
   - Fix: Re-run simulation with a configuration that exercises the parse error branch, or accept that model checking already covers it

3. **All depends_on records are SKELETON_ONLY**: Every UUID in the plan points to a skeleton record. The plan is modifying these functions, but if they haven't been fully extracted yet, the spec was written against skeleton information only.
   - Impact: Medium — the spec may not capture nuances that a full extraction would reveal
   - Fix: Run a full extraction pass before implementation, or accept the risk

4. **gwt-0022 model checking used degenerate constants**: `.cfg` sets `MIN_CONCURRENCY = MAX_CONCURRENCY = DEFAULT_CONCURRENCY = 10`. TLC verified invariants for a single-value range only. `ValidationCorrect` wasn't exercised for actual range boundaries.
   - Impact: Medium — validation logic generalization untested by model checker
   - Fix: Re-run TLC with `MIN_CONCURRENCY=1`, `MAX_CONCURRENCY=100`, `DEFAULT_CONCURRENCY=10`

### Cosmetic (nice to fix)

1. **Plan frontmatter `cw9_project: . (this IS the cw9 codebase)`**: The parenthetical is non-standard. Should be just `.`.
   - Fix: `cw9_project: .`

2. **Bridge artifact count format**: The plan lists counts with names in a custom format (`operations: 8 — DispatchQuery, ...`). The bridge JSON uses dict keys. Counts match but the format could be standardized.

## Approval Status

- [ ] **Ready for `/cw9_implement`** — no critical issues
- [ ] **Needs minor revision** — warnings should be addressed
- [x] **Needs major revision** — critical issues must be resolved
- [ ] **Needs re-pipeline** — artifacts are missing or stale

**Recommendation**: Fix Critical #1 and #2 (run pipeline for gwt-0019 and gwt-0027, or remove references). Address Critical #3 by adding tests for at minimum: `PerTaskAtMostOnce`, `FailedTaskSlotReleased`, `CompletionImpliesUpserted`, `ValidationCorrect`, and `SweepReceivesCorrectValue`. The remaining structural/composite verifiers can be deprioritized.
