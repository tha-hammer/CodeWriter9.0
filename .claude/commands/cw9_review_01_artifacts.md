# CW9 Review: Artifact Existence & Status Consistency

Verify that all pipeline artifacts referenced by a CW9 TDD plan exist on disk and that the plan's status claims match reality. This is the lightest review pass — almost fully automatable.

Use Haiku subagents for file checks. This review should complete quickly.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, search `thoughts/searchable/shared/plans/` for recent plans.

## Self-Hosting Artifact Paths

| Artifact | Path |
|---|---|
| Verified specs | `templates/pluscal/instances/<gwt-id>.tla` |
| Spec configs | `templates/pluscal/instances/<gwt-id>.cfg` |
| Simulation traces | `templates/pluscal/instances/<gwt-id>_sim_traces.json` |
| Bridge artifacts | `python/tests/generated/<gwt-id>_bridge_artifacts.json` |
| Generated tests | `python/tests/generated/test_<gwt-id>.py` |
| Context files | `.cw9/context/<gwt-id>.md` |
| Self-hosting DAG | `dag.json` (repo root) |

## Scope

This review answers ONE question: **Do the artifacts the plan claims exist actually exist, and are claims consistent with disk?**

It does NOT:
- Read artifact contents (that's `/cw9_review_coverage`)
- Evaluate test quality (that's `/cw9_review_coverage`)
- Assess abstraction gaps (that's `/cw9_review_abstraction_gap`)
- Check DAG conflicts (that's `/cw9_review_interaction`)

## Process

### Step 1: Read Plan and Extract GWT IDs

1. **Read the plan FULLY** — no partial reads
2. **Extract all GWT IDs** referenced in the plan (gwt-NNNN)
3. **Check GWT ID range** — self-hosting IDs gwt-0001..0076 are allocated. New work should be gwt-0077+

### Step 2: Artifact Existence Check

For each GWT ID, check all six artifact types:

```bash
# For each gwt-id in the plan:
ls templates/pluscal/instances/gwt-NNNN.tla                      # verified spec
ls templates/pluscal/instances/gwt-NNNN.cfg                      # spec config
ls templates/pluscal/instances/gwt-NNNN_sim_traces.json          # simulation traces
ls python/tests/generated/gwt-NNNN_bridge_artifacts.json         # bridge artifacts
ls python/tests/generated/test_gwt_NNNN.py                       # generated tests
ls .cw9/context/gwt-NNNN.md                                      # context file
```

Record per GWT:
- Spec: exists / missing
- Config: exists / missing
- Traces: exists / missing
- Bridge: exists / missing
- Tests: exists / missing
- Context: exists / missing

### Step 3: Status Consistency

Cross-reference plan claims against disk:

| Plan Says | Disk State | Verdict |
|---|---|---|
| "verified" | spec exists | Consistent |
| "verified" | spec missing | **CRITICAL: false claim** |
| "pending" | spec exists | **WARNING: stale status** |
| "pending" | spec missing | Consistent |

### Step 4: Context File Minimal Check

For each context file that exists, verify it contains a Test Interface section:

```bash
grep -l "## Test Interface" .cw9/context/gwt-NNNN.md
```

Flag:
- Missing context file entirely → **CRITICAL** (60% hallucination rate in gen-tests)
- Context file without `## Test Interface` → **CRITICAL** (same problem)

Do NOT evaluate the quality of the Test Interface contents here — that's for `/cw9_review_coverage` and `/cw9_review_abstraction_gap`.

### Step 5: Path Reference Check

Scan the plan text for path references. Flag if:
- Plan references `.cw9/specs/` instead of `templates/pluscal/instances/` → cosmetic warning
- Plan references `.cw9/bridge/` instead of `python/tests/generated/` → cosmetic warning
- Plan references wrong project root → may indicate plan was written for external project

### Step 6: Generate Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-ARTIFACTS-REVIEW.md`

```markdown
---
date: [ISO timestamp]
reviewer: [agent name]
topic: "[Plan Name] — Artifact Review"
tags: [review, cw9, artifacts, self-hosting]
status: complete
reviewed_plan: [path to plan]
review_type: artifacts
---

# Artifact Review: [Plan Name]

## Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | pass/fail | N missing |
| Status consistency | pass/fail | N mismatches |
| Context file presence | pass/fail | N missing |
| Path references | pass/fail | N wrong paths |

## Artifact Matrix

| GWT | Spec | Config | Traces | Bridge | Tests | Context | Plan Claims | Actual |
|-----|------|--------|--------|--------|-------|---------|-------------|--------|
| gwt-NNNN | Y/N | Y/N | Y/N | Y/N | Y/N | Y/N | verified/pending | verified/missing |

## Context Files

| GWT | File Exists | Has Test Interface |
|-----|------------|-------------------|
| gwt-NNNN | Y/N | Y/N |

## Issues

### Critical
[List any false status claims or missing context files]

### Warnings
[List any stale statuses or wrong path references]

## Verdict

- [ ] **All artifacts present** — proceed to `/cw9_review_coverage`
- [ ] **Artifacts missing** — run pipeline steps before continuing review
- [ ] **Status inconsistent** — update plan before continuing review
```

### Step 7: Beads

- If critical issues: `bd create --title="Artifact Review: [name] — missing artifacts" --type=bug --priority=1`
- Link to plan issue: `bd dep add <review-id> <plan-id>`

## Guidelines

- **This is a fast gate.** If artifacts are missing, there's no point running deeper reviews.
- **Don't read file contents.** Only check existence. Content analysis is a separate review.
- **Automate aggressively.** Most of this is `ls` and `grep -l`.
- **Path mismatches are cosmetic.** The CLI routes correctly regardless — flag but don't block.
