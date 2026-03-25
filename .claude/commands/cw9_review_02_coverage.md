# CW9 Review: Formal Coverage

Verify that tests fully cover what the TLA+ spec formally proved — bridge verifiers, simulation trace patterns, and spec invariants all map to test assertions. This review reads artifact *contents*, not just existence.

**Prerequisite**: `/cw9_review_artifacts` must pass (all artifacts present).

Use Haiku subagents for file reads. Use up to 5 Sonnet subagents for cross-referencing artifacts against test code.
Have subagents write findings to file to preserve main context window.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, search `thoughts/searchable/shared/plans/` for recent plans.

## Self-Hosting Artifact Paths

| Artifact | Path |
|---|---|
| Verified specs | `templates/pluscal/instances/<gwt-id>.tla` |
| Simulation traces | `templates/pluscal/instances/<gwt-id>_sim_traces.json` |
| Bridge artifacts | `python/tests/generated/<gwt-id>_bridge_artifacts.json` |
| Generated tests | `python/tests/generated/test_<gwt-id>.py` |
| Context files | `.cw9/context/<gwt-id>.md` |

## Scope

This review answers ONE question: **Does every formally verified property have a corresponding test assertion?**

It does NOT:
- Check whether artifacts exist (that's `/cw9_review_artifacts`)
- Evaluate implementation decisions below the model's abstraction (that's `/cw9_review_abstraction_gap`)
- Check DAG conflicts (that's `/cw9_review_interaction`)
- Check whether imports are correct (that's `/cw9_review_imports`)

## Process

### Step 1: Read Plan and Load Artifacts

1. **Read the plan FULLY**
2. **Read bridge artifacts** for each GWT:
   ```bash
   cat python/tests/generated/gwt-NNNN_bridge_artifacts.json | python3 -m json.tool
   ```
3. **Read simulation traces** for each GWT:
   ```bash
   cat templates/pluscal/instances/gwt-NNNN_sim_traces.json | python3 -m json.tool
   ```
4. **Read the TLA+ spec** `define` block for each GWT:
   ```bash
   cat templates/pluscal/instances/gwt-NNNN.tla
   ```
5. **Read the test code** in the plan's Red phase (or generated test files if they exist)

### Step 2: Bridge Verifier → Test Mapping

For each GWT:

1. **List all verifiers** from the bridge artifacts JSON
2. **List all operations** from the bridge artifacts JSON
3. **Cross-reference against plan's test assertions**:
   - Each verifier should have at least one test assertion
   - Each operation should have at least one test exercising it
4. **Check counts match**: Do operation/verifier counts in the plan match the actual bridge JSON?
5. **Check names match**: Are operation/verifier names in the plan the same as in the JSON?

**Flag any verifier with no corresponding test assertion.** These are formally verified invariants the tests don't check.

**Flag any operation count or name mismatch** — the plan may have been written from an earlier pipeline run.

### Step 3: Simulation Trace → Test Coverage

For each GWT's simulation traces:

1. **Categorize traces**:
   - Happy path (normal completion)
   - Error/rejection paths (invariant violations caught)
   - Edge cases (boundary conditions, empty inputs, single-element sets)
2. **Map each trace category to a test**:
   - At least one test following the happy-path trace?
   - Error paths have corresponding error/rejection tests?
   - Interesting state transitions reflected in test assertions?
3. **Extract concrete values**: Variable assignments at each trace state become candidate test values. Are the plan's test values drawn from traces?

**Flag any trace pattern with no corresponding test.**

### Step 4: TLA+ Invariant → Test Assertion Mapping

For each GWT's spec:

1. **Extract the `define` block** — list every named predicate
2. **Classify each predicate**:
   - **Standalone invariant** (listed in the `.cfg` INVARIANT section) → needs its own test assertion
   - **Helper predicate** (used inside other invariants) → does NOT need its own test
   - **Type invariant** (TypeOK) → covered by type checking, usually doesn't need explicit test
3. **Map standalone invariants to test assertions**
4. **Check liveness properties**: If the spec has `THEOREM Spec => <>Property`, is there a test for eventuality?

**Flag any standalone invariant with no corresponding test assertion.**

### Step 5: Generate Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-COVERAGE-REVIEW.md`

```markdown
---
date: [ISO timestamp]
reviewer: [agent name]
topic: "[Plan Name] — Coverage Review"
tags: [review, cw9, coverage, self-hosting]
status: complete
reviewed_plan: [path to plan]
review_type: coverage
---

# Coverage Review: [Plan Name]

## Summary

| Check | Status | Gaps |
|-------|--------|------|
| Bridge verifier coverage | pass/fail | N uncovered verifiers |
| Bridge operation coverage | pass/fail | N uncovered operations |
| Simulation trace coverage | pass/fail | N uncovered patterns |
| TLA+ invariant coverage | pass/fail | N uncovered invariants |
| Artifact count consistency | pass/fail | N mismatches |

## Verifier Coverage

### gwt-NNNN: [name]

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| VerifierName | `assert result.field == value` | YES |
| MissingVerifier | — | **NO** |

## Operation Coverage

### gwt-NNNN: [name]

| Operation | Test Exercising It | Covered? |
|-----------|-------------------|----------|
| OpName | test_function_name | YES |
| MissingOp | — | **NO** |

## Trace Coverage

### gwt-NNNN: [name]

| Trace Pattern | Category | Test? | Notes |
|---|---|---|---|
| Normal completion | happy path | YES | test_X |
| Rejection on invalid input | error path | YES | test_Y |
| Empty candidate set | edge case | **NO** | Trace shows [description] |

## Invariant Coverage

### gwt-NNNN: [name]

| Invariant | Type | Test Assertion | Covered? |
|-----------|------|---------------|----------|
| NoDNCContact | standalone | `assert not contacted_dnc` | YES |
| TypeOK | type invariant | (type system) | SKIP |
| HelperPred | helper | (used by NoDNCContact) | SKIP |
| MissingInvariant | standalone | — | **NO** |

## Issues

### Critical
[Uncovered standalone invariants or verifiers — these are formally proved properties with no test]

### Warnings
[Uncovered trace patterns, count mismatches, missing edge case tests]

## Verdict

- [ ] **Full coverage** — proceed to `/cw9_review_abstraction_gap`
- [ ] **Gaps found** — add missing test assertions before implementation
- [ ] **Artifact mismatch** — re-run bridge/gen-tests before continuing
```

### Step 6: Beads

- If uncovered invariants/verifiers: `bd create --title="Coverage Review: [name] — N uncovered verifiers" --type=bug --priority=1`
- Link: `bd dep add <review-id> <plan-id>`

## Guidelines

- **Verifiers are the gold standard.** Every verifier is a formally verified invariant — missing coverage is always critical.
- **Helper predicates don't need tests.** Only standalone invariants (those in the `.cfg` INVARIANT section) require test assertions.
- **Trace values are test data.** If the plan's test uses values that don't appear in any trace, question where they came from.
- **Count mismatches mean stale plan.** If the bridge has 5 verifiers but the plan says 4, the plan was written against an older pipeline run.
