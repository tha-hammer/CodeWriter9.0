---
date: 2026-03-22T12:00:00Z
researcher: DustyForge
topic: "Observability Cross-Cutting Enforcement TDD Plan — CW9 Review"
tags: [review, cw9, observability, cross-cutting, seam-checker, templates]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-22-tdd-observability-cross-cutting-enforcement.md
---

# CW9 Plan Review: Observability Cross-Cutting Enforcement

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | **PASS** | 0 — all specs, traces, bridge artifacts, context files present |
| Status consistency | **PASS** | 0 — plan says "draft", artifacts are verified, no contradictions |
| UUID validity | **N/A** | 0 — plan references no crawl.db UUIDs (new feature, not refactor) |
| Context file quality | **WARN** | 3 — gwt-0069, gwt-0070, gwt-0072 have incomplete Test Interface snippets |
| Bridge artifact match | **WARN** | 3 — count mismatches between plan overview and actual bridge files |
| Test-to-verifier mapping | **FAIL** | 4 verifiers missing from implementation steps |
| Simulation trace coverage | **WARN** | 3 GWTs with thin scenario coverage |
| TLA+ invariant coverage | **PASS** | 0 — all invariants accounted for in bridge verifiers |
| Dead code / scope | **PASS** | 0 — additive feature, no deletions |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Context | Plan Says | Actual |
|-----|------|--------|--------|---------|-----------|--------|
| gwt-0068 | exists | exists (10 traces) | exists | exists | verified (attempt 4/8) | verified |
| gwt-0069 | exists | exists (10 traces) | exists | exists | verified (attempt 3/8) | verified |
| gwt-0070 | exists | exists (10 traces) | exists | exists | verified (attempt 1/8) | verified |
| gwt-0071 | exists | exists (10 traces) | exists | exists | verified (attempt 2/8) | verified |
| gwt-0072 | exists | exists (10 traces) | exists | exists | verified (attempt 6/8) | verified |

**Generated tests:** ALL MISSING (test_gwt_0068.py through test_gwt_0072.py). This is expected — `cw9 gen-tests` runs during implementation, not during planning.

**Implementation targets:** `observability_state_machine.tla` and `cross_cutting_rules.json` do not exist yet. Expected — they're created during implementation.

## Bridge Artifact Validation

### gwt-0068: CrossCuttingRulesLoader

| Field | Plan Says | Actual | Match? |
|---|---|---|---|
| data_structures | 1 | 1 | yes |
| operations | 10 | 10 | yes |
| verifiers | 9 | 9 | yes |

**Plan overview names 8 verifiers + "(type invariant)"**. Actual 9th verifier is `PhaseValid`. Match.

**Operations (actual):** ChooseFileExists, ChooseJsonValid, ChooseSchema, ReadFile, ParseJSON, ValidateRules, CheckPositions, BuildResult, RaisedError, Finish — matches plan.

### gwt-0069: BehavioralContracts

| Field | Plan Says | Actual | Match? |
|---|---|---|---|
| data_structures | 1 | 1 | yes |
| operations | 6 | 6 | yes |
| verifiers | 8 | 8 | yes |

**Verifier name discrepancy:** Plan overview lists "CountConsistency, ViolationComplete, NoFalsePositives, NoMatchNoViolation, EmptyEdgesImpliesEmptyReport, ZeroViolationsWhenAllCompliant, NoMatchNoCount, (type invariant)". Actual bridge has `ViolatedEdges` instead of a type invariant — `ViolatedEdges` is a helper set definition used by `CountConsistency`, but the bridge lists it as a verifier.

**Step 3 verifier gap:** Step 3 only lists 6 of the 8 verifiers. Missing: `ViolatedEdges`, `NoMatchNoCount`.

### gwt-0070: CrossCuttingCLI

| Field | Plan Says | Actual | Match? |
|---|---|---|---|
| data_structures | 1 | 1 | yes |
| operations | 6 | 6 | yes |
| verifiers | 8 | 8 | yes |

**Plan overview says "8" including "2 type invariants"**. Actual bridge has 8 named verifiers: BackwardCompatible, FlagEnablesBehavioral, JsonIncludesBehavioral, MissingRulesError, BothReportsPresent, SeamReportAlwaysPresent, NoSpuriousBehavioralOnError, ExitCodeCleanOnSuccess.

**Step 4 verifier gap:** Step 4 only lists 6 of the 8 verifiers. Missing: `NoSpuriousBehavioralOnError`, `ExitCodeCleanOnSuccess`.

### gwt-0071: observability_state_machine

| Field | Plan Says | Actual | Match? |
|---|---|---|---|
| data_structures | 1 | 1 | yes |
| operations | 2 | 2 | yes |
| verifiers | 7 | 7 | yes |

All verifier names match: ValidState, BoundedExecution, TraceComplete, AuditComplete, TraceLogMonotonic, AuditLogMonotonic, BasePreserved.

### gwt-0072: TemplateSelectedByAnnotation

| Field | Plan Says | Actual | Match? |
|---|---|---|---|
| data_structures | 1 | 1 | yes |
| operations | 7 | 7 | yes |
| verifiers | 8 | 8 | yes |

All verifier names match: TypeOK, DefaultFallback, AnnotationRespected, NoSilentFallback, PromptBuiltOnlyIfLoaded, ErrorMeansNoPrompt, UnknownTemplateImpliesError, KnownTemplateNeverErrors.

## Verifier Coverage

### gwt-0068

| Verifier | In Step? | Notes |
|----------|----------|-------|
| NoPartialResults | Step 2 | yes |
| ValidPositionOnly | Step 2 | yes |
| CompleteFields | Step 2 | yes |
| FileAbsentImpliesError | Step 2 | yes |
| MalformedImpliesError | Step 2 | yes |
| InvalidSchemaImpliesError | Step 2 | yes |
| SafeResult | Step 2 | yes |
| EmptyRulesValid | Step 2 | yes |
| PhaseValid | — | **NOT in Step 2** (type invariant, implicit) |

### gwt-0069

| Verifier | In Step? | Notes |
|----------|----------|-------|
| ViolatedEdges | — | **NOT in Step 3** (helper set, used by CountConsistency) |
| CountConsistency | Step 3 | yes |
| ViolationComplete | Step 3 | yes |
| NoFalsePositives | Step 3 | yes |
| NoMatchNoViolation | Step 3 | yes |
| EmptyEdgesImpliesEmptyReport | Step 3 | yes |
| ZeroViolationsWhenAllCompliant | Step 3 | yes |
| NoMatchNoCount | — | **NOT in Step 3** — explicitly listed in plan overview but dropped from implementation step |

### gwt-0070

| Verifier | In Step? | Notes |
|----------|----------|-------|
| BackwardCompatible | Step 4 | yes |
| FlagEnablesBehavioral | Step 4 | yes |
| JsonIncludesBehavioral | Step 4 | yes |
| MissingRulesError | Step 4 | yes |
| BothReportsPresent | Step 4 | yes |
| SeamReportAlwaysPresent | Step 4 | yes |
| NoSpuriousBehavioralOnError | — | **NOT in Step 4** — if --cross-cutting + missing rules, behavioral report must NOT appear |
| ExitCodeCleanOnSuccess | — | **NOT in Step 4** — successful run must exit 0 |

### gwt-0071

All 7 verifiers covered in Step 5.

### gwt-0072

All 8 verifiers covered in Step 6.

## Trace Coverage

### gwt-0068

| Trace Pattern | Seen? | Notes |
|---|---|---|
| file_exists=FALSE → FileNotFoundError | yes | 8 of 10 traces |
| file_exists=TRUE, json_valid=TRUE, schema missing → ValueError | yes | 1 trace |
| file_exists=TRUE, json_valid=TRUE, valid rule → success | yes | 1 trace |
| file_exists=TRUE, json_valid=FALSE → ValueError | **NO** | Spec supports it (ChooseJsonValid), simulation didn't sample it |
| file_exists=TRUE, valid but position="INVALID" → ValueError | **NO** | Spec supports it (ChooseSchema), simulation didn't sample it |
| empty rules_data → empty list success | **NO** | Spec supports it, plan mentions it in Step 2 test spec, but not in sim traces |

Plan's Step 2 test spec includes all 6 paths. The simulation traces only cover 3 of 6, but the plan tests cover all — **no gap in plan coverage**, just thin simulation sampling.

### gwt-0069

| Trace Pattern | Seen? | Notes |
|---|---|---|
| No-match (zero violations) | yes | All 10 traces show no-match path |
| Match with violation (callee missing required OUT) | **NO** | Not in simulation traces |
| All compliant (match, no violations) | **NO** | Not in simulation traces |

Plan's Step 3 test spec covers 4 scenarios including the violation and all-compliant paths. **Simulation traces are thin** — only the no-match scenario was sampled. The `cw9 gen-tests` step should still produce correct tests from bridge artifacts, but implementer should verify the match/violation scenarios manually.

### gwt-0070

| Trace Pattern | Seen? | Notes |
|---|---|---|
| cross_cutting=FALSE → backward compat | yes | 4 traces |
| cross_cutting=TRUE, rules exist → both reports | yes | 2 traces |
| cross_cutting=TRUE, json=TRUE, rules exist → JSON includes behavioral | yes | 1 trace |
| cross_cutting=TRUE, rules missing → error exit | yes | 3 traces |

All 8 boolean combinations covered. Good coverage.

### gwt-0071

All 10 traces are identical (deterministic 3-state machine). No violation traces exist in simulation — the spec models the *correct* behavior only. The failing case (omitted trace_log append) is tested by TLC's exhaustive model checking, not simulation.

### gwt-0072

| Trace Pattern | Seen? | Notes |
|---|---|---|
| NoMetadata → DefaultFallback | yes | 2 traces |
| DefaultTmpl → success | yes | 1 trace |
| ObsTmpl → success | yes | 2 traces |
| UnknownTmpl → error | yes | 5 traces |

All 4 input values covered. Good coverage.

## TLA+ Invariant Coverage

All invariants in all 5 specs are accounted for in the bridge verifiers. No invariants exist in specs that aren't represented in the bridge artifacts.

## Issues

### Critical (must fix before implementation)

1. **`resource_type` column does not exist in crawl.db**
   - The user's review answer #2 says to match on `callee.resource_type` in crawl.db, but the `records` table has no `resource_type` column. Available columns: `uuid, function_name, class_name, file_path, line_number, src_hash, is_external, do_description, do_steps, do_branches, do_loops, do_errors, failure_modes, operational_claim, skeleton_json, source_crate, boundary_contract, schema_version, created_at, updated_at`.
   - The plan's original approach (line 185: path pattern matching) won't work either per user feedback.
   - **Impact:** `check_behavioral_contracts()` (Step 3) has no way to determine which functions "touch" a resource_type without a matching strategy.
   - **Fix options:** (a) Add a `resource_type` column to the `records` table and populate it during extraction — this requires a schema migration and extractor change (pipeline work). (b) Use `boundary_contract` or `operational_claim` text fields with keyword matching as a heuristic. (c) Use `ins.source` = `EXTERNAL` as a proxy for "external_api" and other `source` enum values for other types. (d) Add `resource_type` as a new field to the extraction schema and backfill incrementally.
   - **Recommendation:** This is a design decision that must be resolved before Step 3 implementation. If `resource_type` is the right long-term answer, it should be a separate prerequisite GWT (schema migration + extractor change), and Step 3 should depend on it.

2. **`"pre_post"` position value not in TLA+ spec's valid set**
   - The user's review answer #3 says to add `"pre_post"` as a valid position. The plan's `cross_cutting_rules.json` (Step 7) uses `"position": "pre_post"` for external_api. But gwt-0068's `ValidPositionOnly` invariant validates `position ∈ {"pre", "post", "wrap"}`.
   - **Impact:** Loading a rules file with `"pre_post"` will raise a ValueError, or if the code doesn't validate, it'll violate the verified spec's invariant.
   - **Fix:** Re-run `cw9 loop gwt-0068` with updated context allowing `"pre_post"` (or `"pre_and_post"`), then re-bridge and re-gen-tests. The spec, bridge artifacts, and generated tests must all be updated together.

3. **Step 3 missing 2 verifiers from implementation list**
   - `NoMatchNoCount` is in the plan overview but dropped from Step 3's verifier list. This means gen-tests might not produce a test for it, or the implementer might miss testing it.
   - **Fix:** Add `NoMatchNoCount` to Step 3 verifier list. `ViolatedEdges` is a helper (not testable independently), so its omission is acceptable.

4. **Step 4 missing 2 verifiers from implementation list**
   - `NoSpuriousBehavioralOnError` and `ExitCodeCleanOnSuccess` are in the bridge but not in Step 4's verifier list.
   - `NoSpuriousBehavioralOnError` is important: when --cross-cutting + missing rules file, the behavioral report must NOT appear in output.
   - `ExitCodeCleanOnSuccess` is important: ensures exit code 0 on success.
   - **Fix:** Add both to Step 4 verifier list and ensure corresponding test assertions exist.

### Warnings (should fix)

1. **Step 7 ordering: config file should move to Step 1**
   - Per user's review answer #1: `load_cross_cutting_rules()` tests (Step 2) need a fixture file. Using the real `cross_cutting_rules.json` as the canonical fixture avoids test/schema drift.
   - **Fix:** Move Step 7 to Step 1 (or Step 0). It's just a JSON file with no behavioral code.

2. **Context file quality — gwt-0069 Test Interface incomplete**
   - `CrawlStore` setup is a comment, not working code. Gen-tests may hallucinate the store construction pattern.
   - **Fix:** Add a complete working fixture showing `CrawlStore(":memory:")` with inserted records and edges.

3. **Context file quality — gwt-0070 Test Interface has no asserts**
   - Only comments describing expected behavior, no actual `assert` statements.
   - **Fix:** Add concrete assert statements for exit_code, output content checks.

4. **Context file quality — gwt-0072 Test Interface tests inline logic, not run_loop()**
   - The snippet resolves template names inline rather than calling `run_loop()`. Gen-tests may produce unit tests of the resolution logic rather than integration tests of the actual function.
   - **Fix:** Show a mock-based test that calls `run_loop()` or the template resolution function directly.

5. **gwt-0069 simulation traces are thin**
   - All 10 traces show the no-match scenario. The match-with-violation and all-compliant paths aren't represented.
   - **Impact:** Low — the plan's test spec covers these scenarios, and bridge verifiers are the authoritative source.
   - **Fix:** Re-run TLC simulation with different constant instantiation to sample violation/compliant paths.

### Cosmetic (nice to fix)

1. **gwt-0071 simulation traces are degenerate**
   - All 10 traces are identical (deterministic spec, no nondeterminism). This is expected for a template structural test but worth noting.

2. **Plan line references for CLI modifications may drift**
   - Plan says "add --cross-cutting at cli.py:1905-1909" and "cmd_seams at cli.py:1697". Line numbers will change if other work is committed before implementation.
   - **Fix:** Reference function names rather than line numbers.

3. **Unused CLI args --file and --function**
   - `cmd_seams` parser accepts `--file` and `--function` but the handler never reads them. Not caused by this plan, but implementer should be aware.

## User Review Answers — Integration

The user provided three review answers that affect the plan:

### Answer 1: Implementation order
- **Accepted with adjustment:** Step 7 (config file) → Step 1. The plan should reorder.
- **Impact:** Low — just JSON file creation, no code dependencies change.

### Answer 2: Resource type matching via crawl.db metadata
- **Blocked:** `resource_type` column doesn't exist in crawl.db. The user's intent is correct (data-driven matching is better than path patterns), but the column needs to be added first.
- **Impact:** High — Step 3 cannot be implemented as described until matching strategy is resolved.
- **Recommendation:** Add a prerequisite GWT for the schema migration, or define a transitional matching strategy using existing fields.

### Answer 3: Add "pre_post" as valid position
- **Requires re-pipeline:** gwt-0068's `ValidPositionOnly` invariant must be updated to include "pre_post". This means re-running `cw9 loop gwt-0068`, then `cw9 bridge`, then `cw9 gen-tests`.
- **Impact:** Medium — one spec re-verification, but straightforward.

## Approval Status

- [ ] **Ready for `/cw9_implement`** — no critical issues
- [ ] **Needs minor revision**
- [x] **Needs major revision** — 2 critical design issues must be resolved
- [ ] **Needs re-pipeline** — artifacts missing or stale

### Before implementation can proceed:

1. **Resolve resource_type matching strategy** — either add column to crawl.db (new GWT) or define transitional approach using existing fields
2. **Re-pipeline gwt-0068** with "pre_post" added to valid positions, or change the rules file to use two separate rules (one "pre", one "post") for external_api
3. **Add missing verifiers** to Steps 3 and 4
4. **Reorder Step 7 → Step 1**
5. **Improve context files** for gwt-0069, gwt-0070, gwt-0072
