# CW9 Review: Abstraction Gap Analysis

Identify every concrete implementation decision that the TLA+ spec leaves unspecified, and verify that the plan or context file provides explicit guidance for each. This is the review that catches "LLM chose the wrong function because the spec didn't constrain the choice."

**Prerequisite**: `/cw9_review_artifacts` must pass. Best run after `/cw9_review_coverage`.

Use up to 5 Sonnet subagents for reading specs, bridge artifacts, and target modules in parallel.
Have subagents write findings to file to preserve main context window.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, search `thoughts/searchable/shared/plans/` for recent plans.

## Self-Hosting Artifact Paths

| Artifact | Path |
|---|---|
| Verified specs | `templates/pluscal/instances/<gwt-id>.tla` |
| Bridge artifacts | `python/tests/generated/<gwt-id>_bridge_artifacts.json` |
| Context files | `.cw9/context/<gwt-id>.md` |
| Source code | `python/registry/` |

## Scope

This review answers ONE question: **For every decision the implementation LLM must make that the spec does NOT constrain, is the correct choice documented?**

The TLA+ model is at the right abstraction level — this review does NOT ask for more detailed specs. It asks for a **decision checklist** that bridges the gap between abstract model and concrete code.

It does NOT:
- Check artifact existence (that's `/cw9_review_artifacts`)
- Check formal coverage (that's `/cw9_review_coverage`)
- Check DAG conflicts (that's `/cw9_review_interaction`)
- Review implemented code (that's `/cw9_review_imports`)

## Why This Review Exists

TLA+ models abstract away implementation details by design. A spec that says `remaining := CandidateIDs` doesn't specify how candidates are fetched. The model is correct — it shouldn't care. But the implementation LLM MUST make that choice, and without explicit guidance it will:

1. Scan available module exports
2. Pick the function whose name looks most relevant
3. Possibly pick the WRONG function (e.g., `getCampaignsForRecruiter` when it needs all campaigns)
4. Possibly bypass its own import with raw SQL/queries
5. Leave the unused import as dead code

This review prevents step 2 from going wrong by making step 1 unnecessary.

## Process

### Step 1: Read Spec and Identify Abstraction Boundaries

For each GWT, read the TLA+ spec and identify every point where the model introduces state "from nowhere" — variables that appear fully formed without the spec modeling how they're obtained.

Common patterns:

| Spec Pattern | What It Abstracts Away | Implementation Must Decide |
|---|---|---|
| `variable := SomeSet` | Data fetching | Which function/query populates this? |
| `IF Condition THEN ...` | Condition evaluation | What concrete check? Which module? |
| `Send(message, target)` | Message delivery | Which transport? Which API? |
| `result \in ResultSet` | Nondeterministic choice | Which selection strategy? |
| `UNCHANGED <<vars>>` | No-op paths | What error handling on the no-op path? |

For each identified boundary, record:
- **Spec location**: line number and action name
- **What the spec says**: the abstract operation
- **What the spec omits**: the concrete decision needed
- **Category**: data-access / import-selection / resource-lifecycle / concurrency-strategy / error-handling

### Step 2: Read Target Modules and Catalog Available Choices

For each abstraction boundary, identify which modules the implementation LLM will encounter:

1. **Read the target module** (from the context file or bridge artifact's target path)
2. **List all exports/public functions** that could plausibly satisfy the abstract operation
3. **Identify the CORRECT choice** and WHY alternatives are wrong

Example from the motivating case:
```
Abstraction: "CandidateIDs" — the set of all candidates to process
Target module: campaign_db.js
Available exports:
  - getCampaignsForRecruiter(recruiterId) → WRONG: scoped to one recruiter
  - pool.query("SELECT * FROM campaigns WHERE status = 'active'") → CORRECT: global scope
Decision: The orchestrator processes ALL active campaigns, not one recruiter's.
The spec says "CandidateIDs" (all of them), not "CandidatesForRecruiter".
```

### Step 3: Read Bridge Artifacts for Unstated Dependencies

Bridge artifacts list operations and data structures. For each operation:

1. **Check `depends_on`**: If empty or missing, the operation has no formally specified dependency — the implementation LLM picks its own imports
2. **Check data structure fields**: If a field type is abstract (e.g., `Set` without specifying the backing store), the implementation must choose the concrete type
3. **Check operation signatures**: If a parameter is abstractly typed, the implementation must decide the concrete source

### Step 4: Cross-Reference Against Context File

Read each GWT's context file (`.cw9/context/gwt-NNNN.md`) and check whether it provides guidance for each identified decision:

| Decision | Documented in Context? | Where? |
|---|---|---|
| Data access for CandidateIDs | YES — "Use global campaign query" in Test Interface | Line N |
| Error handling for failed sends | NO — context file only shows happy path | **GAP** |
| Connection pool lifecycle | NO — not mentioned | **GAP** |

### Step 5: Cross-Reference Against Plan

Check the plan's implementation steps for any guidance on identified decisions:

- Does the plan specify which imports to use?
- Does the plan specify which query/function for each data access?
- Does the plan address resource lifecycle?
- Does the plan address the concurrency strategy?

### Step 6: Generate Decision Checklist

This is the key output. For each identified gap, produce an explicit decision with the correct answer:

```markdown
## Decision Checklist for gwt-NNNN

### DC-1: How are active campaigns fetched?
- **Spec says**: `remaining := CandidateIDs` (all candidates, abstract set)
- **Available choices**:
  - `getCampaignsForRecruiter(id)` from `campaign_db.js` — WRONG (recruiter-scoped)
  - `pool.query("SELECT * FROM campaigns WHERE status = 'active'")` — CORRECT (global)
- **Correct choice**: Global query. The spec models all candidates, not a subset.
- **Action**: Add to context file Test Interface section.

### DC-2: What happens when a send fails?
- **Spec says**: `UNCHANGED <<vars>>` on the failure branch
- **Available choices**:
  - Silently skip — matches spec literally but loses observability
  - Log and skip — preserves spec semantics with observability
  - Retry — NOT modeled in spec, would need spec amendment
- **Correct choice**: Log and skip. Matches spec semantics.
- **Action**: Add error handling note to context file.
```

### Step 7: Generate Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-ABSTRACTION-REVIEW.md`

```markdown
---
date: [ISO timestamp]
reviewer: [agent name]
topic: "[Plan Name] — Abstraction Gap Review"
tags: [review, cw9, abstraction-gap, self-hosting]
status: complete
reviewed_plan: [path to plan]
review_type: abstraction_gap
---

# Abstraction Gap Review: [Plan Name]

## Summary

| GWT | Abstraction Boundaries | Documented | Undocumented Gaps |
|-----|----------------------|------------|-------------------|
| gwt-NNNN | N | N | N |

Total decisions needed: N
Documented in context/plan: N
**Undocumented gaps: N**

## Abstraction Boundaries by GWT

### gwt-NNNN: [name]

| ID | Category | Spec Says | Implementation Must Decide | Documented? |
|----|----------|-----------|---------------------------|-------------|
| DC-1 | data-access | `remaining := CandidateIDs` | Which query fetches candidates? | NO |
| DC-2 | import-selection | Uses `Send` action | Which send function from which module? | YES (context) |
| DC-3 | error-handling | `UNCHANGED` on failure | Log? Skip? Retry? | NO |
| DC-4 | resource-lifecycle | Implicit pool | Who creates/closes the connection pool? | NO |
| DC-5 | concurrency | `\A c \in remaining` | Sequential loop? Promise.all? Batched? | YES (plan) |

## Decision Checklist

[Full decision checklist as generated in Step 6 — this section is designed to be
copy-pasted into the context file or appended to the plan as implementation guidance]

### gwt-NNNN: [name]

#### DC-1: [Decision title]
- **Spec says**: [abstract operation]
- **Available choices**: [concrete options with rationale]
- **Correct choice**: [answer]
- **Action**: [what to update — context file, plan, or both]

[Repeat for each undocumented gap]

## Module Export Analysis

For transparency, list what the implementation LLM will see when it reads each target module:

### [module_path]
| Export | Purpose | Correct Use For This Feature? |
|--------|---------|------------------------------|
| functionA | [description] | YES — use for DC-1 |
| functionB | [description] | NO — wrong scope |
| functionC | [description] | NO — deprecated |

## Issues

### Critical (must resolve before `/cw9_implement`)
[Undocumented decisions where the wrong choice would violate spec intent]

### Warnings (should resolve)
[Undocumented decisions where wrong choice is suboptimal but not spec-violating]

## Required Context File Updates

List the exact additions needed for each context file:

### .cw9/context/gwt-NNNN.md

```markdown
## Implementation Decisions (from Abstraction Gap Review)

- **DC-1**: [concise directive for the implementation LLM]
- **DC-2**: [concise directive]
```

## Verdict

- [ ] **All gaps documented** — proceed to `/cw9_implement`
- [ ] **Gaps found, checklist produced** — update context files with checklist, then proceed
- [ ] **Spec-level ambiguity found** — the spec itself is ambiguous about intent, needs `/cw9_loop` re-run with clarified context
```

### Step 8: Beads

- If critical gaps: `bd create --title="Abstraction Gap: [name] — N undocumented decisions" --type=task --priority=1`
- Link: `bd dep add <review-id> <plan-id>`

## Guidelines

- **The spec is NOT wrong.** The model is at the right abstraction level. This review does not ask for more detailed specs — it asks for documented decisions at the implementation level.
- **Read the target modules.** You can't identify the wrong import if you don't know what imports exist. Always read the module the implementation LLM will read.
- **Name the wrong choices explicitly.** "Don't use getCampaignsForRecruiter" is more useful than "use the correct function." The LLM needs to know what NOT to do.
- **The decision checklist is the deliverable.** The report is for humans. The checklist is for the implementation LLM — it gets added to the context file.
- **Categories matter.** Data-access gaps cause wrong queries. Import-selection gaps cause dead imports. Resource-lifecycle gaps cause leaks. Concurrency gaps cause race conditions. Each is a distinct failure mode.
- **When in doubt, it's a gap.** If you have to reason about which function is correct, so will the implementation LLM — and it might reason differently. Document the choice.
