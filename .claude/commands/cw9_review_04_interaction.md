# CW9 Review: Existing GWT Interaction Check

Verify that new GWT behaviors don't conflict with the existing verified behavior corpus (gwt-0001..0076). Self-hosting specific — external repos don't have 76 pre-existing verified GWTs.

**Prerequisite**: `/cw9_review_artifacts` must pass.

Use Haiku subagents for DAG reads and grep. Use up to 3 Sonnet subagents for module analysis.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, search `thoughts/searchable/shared/plans/` for recent plans.

## Self-Hosting Paths

| Artifact | Path |
|---|---|
| Self-hosting DAG | `dag.json` (repo root) |
| Source code | `python/registry/` |
| Existing specs | `templates/pluscal/instances/` |
| Existing tests | `python/tests/generated/` |

## Scope

This review answers ONE question: **Do the new GWTs peacefully coexist with the existing 76 verified GWTs?**

It does NOT:
- Check artifact existence (that's `/cw9_review_artifacts`)
- Check formal coverage (that's `/cw9_review_coverage`)
- Assess abstraction gaps (that's `/cw9_review_abstraction_gap`)
- Review implemented code (that's `/cw9_review_imports`)

## Process

### Step 1: Identify New vs Existing GWTs

1. **Read the plan** and extract all new GWT IDs
2. **Load `dag.json`** and list all existing GWT nodes
3. **Classify**: Which GWTs in the plan are new? Which reference existing ones?
4. **Check ID allocation**: New GWTs should be gwt-0077+. Flag any ID reuse or collision.

### Step 2: Module Overlap Analysis

For each new GWT, identify which `python/registry/` modules it touches:

1. **From the plan**: What modules does each implementation step modify?
2. **From the bridge artifacts**: What target module does each operation specify?
3. **From the context file**: What imports does the Test Interface section reference?

Cross-reference against existing GWTs:

```bash
# Find which existing GWTs touch the same modules
grep -l "registry/module_name" python/tests/generated/test_gwt_*.py
grep -l "registry.module_name" python/tests/generated/test_gwt_*.py
```

For each module overlap:
- **Is the new behavior additive?** (new function, new code path) → OK
- **Does it modify existing behavior?** (changed return type, new side effect) → **WARNING**
- **Does it contradict existing behavior?** (breaks existing postcondition) → **CRITICAL**

### Step 3: DAG Edge Conflict Analysis

Check if new GWT nodes create unexpected edges in the DAG:

1. **Read new node definitions** from the plan
2. **Check edges**: Do new nodes connect to existing nodes? How?
3. **Check for cycles**: Would new edges create circular dependencies?
4. **Check supersession**: Does any new node supersede an existing one? If so, is the superseded behavior fully covered by the new spec?

### Step 4: Import Path Conflicts

New generated tests may import from the same modules as existing tests, but with different expectations:

1. **Read import sections** of new test files (or planned test code)
2. **Compare against existing test imports** for the same modules
3. **Flag**: Different constructor signatures, different expected return types, different exception expectations for the same function

```bash
# Compare imports across test files for the same module
grep "from registry.module" python/tests/generated/test_gwt_*.py
```

### Step 5: Invariant Compatibility

If a new GWT adds invariants to a module that existing GWTs also constrain:

1. **List existing invariants** for the shared module (from existing specs)
2. **List new invariants** (from new spec)
3. **Check compatibility**: Can all invariants hold simultaneously?
   - Same state variable constrained by both? Check they don't contradict.
   - New postcondition on a function with existing postconditions? Check they compose.

### Step 6: Generate Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-INTERACTION-REVIEW.md`

```markdown
---
date: [ISO timestamp]
reviewer: [agent name]
topic: "[Plan Name] — Interaction Review"
tags: [review, cw9, interaction, self-hosting]
status: complete
reviewed_plan: [path to plan]
review_type: interaction
---

# Interaction Review: [Plan Name]

## Summary

| Check | Status | Issues |
|-------|--------|--------|
| ID allocation | pass/fail | N conflicts |
| Module overlap | pass/fail | N overlaps |
| DAG edge conflicts | pass/fail | N conflicts |
| Import path conflicts | pass/fail | N conflicts |
| Invariant compatibility | pass/fail | N incompatibilities |

## GWT ID Allocation

| New GWT | ID | Range Check | Collision? |
|---------|-----|-------------|-----------|
| [name] | gwt-NNNN | OK / OUT OF RANGE | none / gwt-XXXX |

## Module Overlap

| Module | New GWTs | Existing GWTs | Relationship |
|--------|----------|---------------|-------------|
| registry/module.py | gwt-NNNN | gwt-00XX, gwt-00YY | additive / modifying / contradictory |

## DAG Edge Analysis

| New Edge | From | To | Type | Conflict? |
|----------|------|----|------|-----------|
| edge-N | gwt-NNNN | gwt-00XX | depends_on | no / yes |

## Import Path Comparison

| Module | New Test Expects | Existing Test Expects | Compatible? |
|--------|-----------------|----------------------|-------------|
| registry.module.func | returns List[str] | returns List[str] | YES |
| registry.module.other | takes 3 args | takes 2 args | **NO** |

## Issues

### Critical
[Contradictory behaviors, import incompatibilities, invariant conflicts]

### Warnings
[Module overlaps that are additive but worth noting, ID range edge cases]

## Verdict

- [ ] **No conflicts** — new GWTs coexist with existing behavior
- [ ] **Additive overlaps only** — new behavior extends existing modules safely
- [ ] **Conflicts found** — resolve before implementation
```

### Step 7: Beads

- If conflicts found: `bd create --title="Interaction Review: [name] — N conflicts" --type=bug --priority=1`
- Link: `bd dep add <review-id> <plan-id>`

## Guidelines

- **Existing GWTs are sacrosanct.** 76 GWTs and 2857+ tests define existing behavior. New code must not break them.
- **Additive is fine.** New functions in existing modules = no conflict. Changed behavior of existing functions = conflict.
- **Check the DAG, not just the code.** Module overlap in code is a hint. DAG edge conflicts are the real issue.
- **Import conflicts predict test failures.** If new tests expect a different signature than existing tests, one of them will break.
- **This review is self-hosting specific.** External repos using CW9 don't have 76 existing GWTs to worry about.
