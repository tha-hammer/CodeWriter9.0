---
date: 2026-03-22T00:00:00Z
researcher: DustyForge
topic: "Horizontal Contract Verification TDD Plan — CW9 Review"
tags: [review, cw9, seam-checking, type-safety]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-22-tdd-horizontal-contract-verification.md
---

# CW9 Plan Review: Horizontal Contract Verification (cw9 seams)

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | **PASS** | 0 |
| Status consistency | **PASS** | 0 |
| UUID validity | **N/A** | Plan has no `depends_on` UUIDs |
| Context file quality | **PASS** | 0 |
| Bridge artifact match | **PASS** | 0 |
| Test-to-verifier mapping | **WARN** | 5 gaps |
| Simulation trace coverage | **WARN** | 4 gaps |
| TLA+ invariant coverage | **WARN** | 4 gaps |
| Dead code / scope | **PASS** | 0 |
| Line number accuracy | **WARN** | 1 discrepancy |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Context | Plan Says | Actual |
|-----|------|--------|--------|---------|-----------|--------|
| gwt-0064 | exists | exists (10) | exists | exists (w/ Test Interface + Anti-Patterns) | verified | verified |
| gwt-0065 | exists | exists (10) | exists | exists (w/ Test Interface + Anti-Patterns) | verified | verified |
| gwt-0066 | exists | exists (10) | exists | exists (w/ Test Interface + Anti-Patterns) | verified | verified |
| gwt-0067 | exists | exists (10) | exists | exists (w/ Test Interface + Anti-Patterns) | verified | verified |

All 4 GWTs are registered in `.cw9/dag.json` (138 total nodes). No generated test files exist (`python/tests/generated/test_gwt_006{4,5,6,7}.py`) — this is acceptable since the plan hand-writes tests per CLAUDE.md's "pipeline infrastructure" exception.

## UUID Validity

N/A — this plan introduces new functions with no `depends_on` UUIDs referencing crawl.db records.

## Bridge Artifact Match

All operation and verifier names/counts match exactly between the plan and actual bridge artifacts:

| GWT | Plan ops | Actual ops | Plan verifiers | Actual verifiers | Match? |
|-----|----------|------------|----------------|------------------|--------|
| gwt-0064 | 3 (StartCheck, CheckTypes, Finish) | 3 (same) | 5 (CompatPairs, SeverityCorrect, MismatchDetected, MismatchCorrect, NoSpuriousMismatches) | 5 (same) | **yes** |
| gwt-0065 | 4 (Start, CheckSeam, ConfirmCompatible, Finish) | 4 (same) | 4 (PhaseValid, ReflexiveCompatPairs, NoFalsePositive, SeamSatisfied) | 4 (same) | **yes** |
| gwt-0066 | 4 (Iterate, PickInput, CheckInput, Terminate) | 4 (same) | 5 (AllScanned, UnresolvedCorrect, NoFalseUnresolved, UnresolvedNotInMismatches, BoundedCheck) | 5 (same) | **yes** |
| gwt-0067 | 4 (InitReport, Processing, ProcessEdge, FinalizeReport) | 4 (same) | 8 (TotalEdges, CurrentSum, CompletenessHolds, MonotonicProgress, NonNegative, TotalIsN, FinalCorrectness, SeamInvariants) | 8 (same) | **yes** |

## Verifier Coverage

### gwt-0064: seam_mismatch_detected

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| CompatPairs | Helper — tested via `type_compatible` tests (Step 2) | yes (indirect) |
| SeverityCorrect | `assert mismatches[0].severity == "type_mismatch"` (Step 3) | yes |
| MismatchDetected | `assert len(mismatches) == 1` (Step 3) | yes |
| MismatchCorrect | `assert expected_type == "Config"` + `provided_type == "Dict[str, Any]"` (Step 3) | yes |
| NoSpuriousMismatches | `test_satisfied_no_report()` returns empty list (Step 3) | yes (indirect) |

### gwt-0065: seam_satisfied_no_report

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| PhaseValid | — | **NO** (internal state machine phase validation; not observable in Python API) |
| ReflexiveCompatPairs | `test_reflexive()` loop (Step 2) | yes |
| NoFalsePositive | `test_satisfied_no_report()` returns `[]` (Step 3) | yes |
| SeamSatisfied | `assert check_seam(caller, callee) == []` (Step 3) | yes |

### gwt-0066: seam_unresolved_flagged

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| AllScanned | Implicit via completeness test counting (Step 5) | yes (indirect) |
| UnresolvedCorrect | `assert len(report.unresolved) == 1` + `severity == "unresolved"` (Step 5) | yes |
| NoFalseUnresolved | Implicit via `report.satisfied == 1` in completeness test (Step 5) | yes (indirect) |
| UnresolvedNotInMismatches | — | **NO** (plan never asserts disjointness between mismatches and unresolved lists) |
| BoundedCheck | — | **NO** (plan never tests bounding on number of inputs checked) |

### gwt-0067: seam_report_complete

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| TotalEdges | Helper — referenced by completeness assertion | yes (indirect) |
| CurrentSum | Helper — referenced by completeness assertion | yes (indirect) |
| CompletenessHolds | `assert report.total_edges == len(mismatches) + len(unresolved) + report.satisfied` (Step 5) | yes |
| MonotonicProgress | — | **NO** (runtime invariant, not observable in single-shot Python call) |
| NonNegative | — | **NO** (plan never asserts `report.satisfied >= 0` etc.) |
| TotalIsN | `assert report.total_edges == 3` (Step 5) | yes |
| FinalCorrectness | `assert report.satisfied == 1`, `len(mismatches) == 1`, `len(unresolved) == 1` (Step 5) | yes |
| SeamInvariants | Composite — constituent coverage above | partial |

## Trace Coverage

### gwt-0064: seam_mismatch_detected

| Trace Pattern | Test? | Notes |
|---|---|---|
| Type mismatch detected (DictStrAny vs Config) | yes | Step 3 `test_mismatch_detected` |
| Compatible types (no mismatch) | yes | Step 3 `test_satisfied_no_report` — but this is a *different* GWT's concern (gwt-0065) |

All 10 traces are identical (single fixed-constant path). No trace variation to miss.

### gwt-0065: seam_satisfied_no_report

| Trace Pattern | Test? | Notes |
|---|---|---|
| Compatible types (listFnRecord == listFnRecord) | yes | Step 3 `test_satisfied_no_report` |
| **Incompatible types path** | **NO** | Traces don't show this path (spec models only the compatible case), but plan tests it via gwt-0064 |

All 10 traces are identical. Single path covered.

### gwt-0066: seam_unresolved_flagged

| Trace Pattern | Test? | Notes |
|---|---|---|
| Two inputs scanned, order A then B | yes (implicit) | Completeness test |
| Two inputs scanned, order B then A | yes (implicit) | Completeness test |
| **Iteration with mismatch found** | **NO** | Traces show only clean inputs; plan's Step 5 `test_report_completeness` covers this via gwt-0067 integration |
| **Iteration with unresolved found** | yes | Step 5 `test_unresolved_flagged` |

### gwt-0067: seam_report_complete

| Trace Pattern | Test? | Notes |
|---|---|---|
| 30 edges (10 each type) processed in varying order | yes | Step 5 `test_report_completeness` (smaller scale: 3 edges) |
| **Zero-edge degenerate case** | **NO** | Traces don't model empty DB; plan doesn't test empty-DB report |
| **Single-type-only case** (e.g., all satisfied) | **NO** | Traces fix 10/10/10; plan doesn't test single-category scenarios |

## TLA+ Invariant Coverage

### gwt-0064

| Invariant (cfg) | Test? | Notes |
|---|---|---|
| SeverityCorrect | yes | `severity == "type_mismatch"` |
| MismatchDetected | yes | `len(mismatches) == 1` |
| MismatchCorrect | yes | field value assertions |
| NoSpuriousMismatches | yes (indirect) | via gwt-0065 compatible-type test |

### gwt-0065

| Invariant (cfg) | Test? | Notes |
|---|---|---|
| PhaseValid | **NO** | Internal — not testable from Python API |
| ReflexiveCompatPairs | yes | `test_reflexive()` |
| NoFalsePositive | yes | `test_satisfied_no_report()` |
| SeamSatisfied | yes | empty list assertion |

### gwt-0066

| Invariant (cfg) | Test? | Notes |
|---|---|---|
| AllScanned | yes (indirect) | completeness count |
| UnresolvedCorrect | yes | direct assertion |
| NoFalseUnresolved | yes (indirect) | satisfied count |
| UnresolvedNotInMismatches | **NO** | No disjointness assertion in any test |
| BoundedCheck | **NO** | No bounding assertion |

### gwt-0067

| Invariant (cfg) | Test? | Notes |
|---|---|---|
| SeamInvariants (composite) | partial | MonotonicProgress and NonNegative not tested |

## Issues

### Critical (must fix before implementation)

None.

### Warnings (should fix)

1. **Missing disjointness test for `UnresolvedNotInMismatches` (gwt-0066)**: The TLA+ spec verifies that unresolved items never appear in the mismatches list. No plan test asserts this.
   - Fix: Add `assert not set(u.callee_uuid for u in report.unresolved) & set(m.callee_uuid for m in report.mismatches)` to `test_report_completeness` in Step 5.

2. **Missing `NonNegative` test (gwt-0067)**: The spec verifies all counts >= 0. No test checks this.
   - Fix: Add `assert report.satisfied >= 0` and similar assertions to Step 5.

3. **Missing zero-edge / empty-DB test (gwt-0067)**: No test covers `check_all_seams(store)` on an empty crawl.db. The completeness invariant should hold with `total_edges == 0`.
   - Fix: Add `test_empty_report(tmp_path)` that creates an empty CrawlStore and asserts `total_edges == 0, satisfied == 0, mismatches == [], unresolved == []`.

4. **Line number inaccuracy for `_DISPATCH`**: Plan says line 1892, actual is line 1988 (96 lines off). Applies to Step 7.
   - Fix: Update plan to reference line 1988.

5. **gwt-0067 bridge verifiers `TotalEdges` and `CurrentSum` are helpers, not standalone invariants**: The plan lists them as verifiers (count=8) which is technically correct per bridge artifact keys, but the TLA+ cfg only checks the composite `SeamInvariants`. The plan should note that `TotalEdges` and `CurrentSum` are computed expressions, not boolean predicates — they don't need dedicated test assertions.
   - Fix: Add a note in Step 5 clarifying these are helpers.

### Cosmetic (nice to fix)

1. **`CompatPairs` listed as verifier in gwt-0064 plan and bridge**: In the TLA+ spec, `CompatPairs` is a helper set (not in cfg). The bridge artifact includes it as a verifier with its own assertion, but the cfg doesn't check it as an INVARIANT. This is a bridge extraction artifact, not a plan error.

2. **gwt-0065 simulation traces are all identical**: All 10 traces replay the exact same compatible-type scenario. This is correct for validation but means the simulation adds no additional coverage beyond what 1 trace would provide.

3. **Plan Step 3 `test_no_ok_output`**: Tests a case (caller has no `ok` output) that corresponds to no specific bridge verifier. This is good defensive testing but isn't tied to a verified invariant. Consider noting this explicitly.

## Approval Status

- [x] **Ready for `/cw9_implement`** — no critical issues
- [ ] ~~Needs minor revision~~
- [ ] ~~Needs major revision~~
- [ ] ~~Needs re-pipeline~~ — all artifacts exist and are verified

The plan is well-structured, all pipeline artifacts are present and consistent, and the 5 warning-level gaps are minor (defensive assertions that supplement already-verified invariants). The plan can proceed to implementation as-is, with the recommended test additions incorporated during the Green phase.
