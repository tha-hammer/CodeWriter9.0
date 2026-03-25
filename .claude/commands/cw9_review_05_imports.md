# CW9 Review: Post-Implementation Import & Abstraction Audit

Audit every file touched during implementation for dead imports, wrong-abstraction-level function calls, and LLM residue. This is a post-implementation review — run AFTER `/cw9_implement`, BEFORE `/validate_plan`.

**Prerequisite**: Implementation is complete (code written, tests passing).

Use Haiku subagents for grep/file reads. Use up to 3 Sonnet subagents for analyzing whether an import is the right abstraction.

## Arguments

$ARGUMENTS = path to CW9 TDD plan, or a git ref range (e.g., `HEAD~3..HEAD`). If not provided, use `git diff --name-only HEAD~1..HEAD` to find recently changed files.

## Scope

This review answers THREE questions:
1. **Is every import actually used?**
2. **Is every external function call the right abstraction for the use case?**
3. **Does any raw operation bypass a purpose-built helper?**

It does NOT:
- Validate pipeline artifacts (that's `/cw9_review_artifacts`)
- Check formal coverage (that's `/cw9_review_coverage`)
- Identify abstraction gaps pre-implementation (that's `/cw9_review_abstraction_gap`)
- Check DAG conflicts (that's `/cw9_review_interaction`)

## Why This Review Exists

LLMs writing implementation code exhibit a characteristic pattern:
1. **Speculative importing**: Import everything that looks relevant from a module
2. **Implementation divergence**: Realize the actual solution needs a different approach
3. **Skip cleanup**: Forget to remove the imports that were never used
4. **Wrong abstraction**: Use a function that's close-but-not-right (e.g., `getCampaignsForRecruiter` when you need all campaigns)

This review catches all four failure modes with a narrow, mechanical scope.

## Process

### Step 1: Identify Files to Audit

Determine which files were touched by the implementation:

```bash
# From plan: read implementation steps and extract file paths
# OR from git:
git diff --name-only <base>..HEAD
# OR if no ref range:
git diff --name-only HEAD~1..HEAD
```

Filter to implementation files only (not test files, not config, not specs):
- Include: `*.py`, `*.js`, `*.ts`, `*.go`, `*.rs` (source files)
- Include: test files too — they can have dead imports
- Exclude: `*.tla`, `*.cfg`, `*.json`, `*.md`, `*.toml`

### Step 2: Dead Import Detection

For each file, extract all imports and verify each is used:

#### Python
```bash
# Extract imports
grep -n "^import \|^from " python/registry/module.py

# For each imported name, check if it's used in the file body
# (excluding the import line itself)
```

For each import:
1. Extract the imported name(s)
2. Search the rest of the file for usage of each name
3. If a name appears ONLY on the import line → **DEAD IMPORT**

#### JavaScript/TypeScript
```bash
# Extract imports
grep -n "^import " src/module.js
grep -n "const .* = require" src/module.js
```

Same process: extract names, search for usage, flag unused.

### Step 3: Wrong Abstraction Detection

For each external function call in the implementation:

1. **Identify the call**: What function is being called? From which module?
2. **Read the source module**: What does this function actually do?
3. **Check fit**: Does the function's purpose match how it's being used?

Red flags:
- **Function is scoped differently than the use case**: e.g., `getXForUser(userId)` called where you need all X's globally
- **Function returns more than needed and caller destructures/filters**: May need a more specific function
- **Function parameters are partially hardcoded or nulled**: e.g., `getItems(null, null, true)` — the function wasn't designed for this call pattern

### Step 4: Raw Operation Bypass Detection

Check for cases where the implementation uses raw operations that bypass existing helpers:

```bash
# Python: raw SQL when ORM/helper exists
grep -n "cursor.execute\|\.query(" python/registry/module.py

# Python: raw file I/O when helper exists
grep -n "open(\|Path(" python/registry/module.py

# JavaScript: raw SQL when helper exists
grep -n "pool.query\|\.execute(" src/module.js
```

For each raw operation:
1. **Check if a helper exists** for this operation in the codebase
2. **If yes**: Is the helper wrong for this use case, or did the LLM just not find it?
3. **If the helper is wrong**: That's fine — document why the raw operation is correct
4. **If the helper is right**: Flag as **WRONG ABSTRACTION** — should use the helper

### Step 5: Cross-Reference Against Abstraction Gap Checklist

If `/cw9_review_abstraction_gap` was run and produced a decision checklist:

1. **Read the checklist** from the abstraction gap review report
2. **Verify each decision was followed**: Did the implementation use the correct choice?
3. **Flag any deviation** from the checklist

This is the closed-loop check: abstraction gap review said "use X, not Y" → did the implementation actually use X?

### Step 6: Generate Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-IMPORTS-REVIEW.md`

```markdown
---
date: [ISO timestamp]
reviewer: [agent name]
topic: "[Plan Name] — Import & Abstraction Audit"
tags: [review, cw9, imports, post-implementation]
status: complete
reviewed_plan: [path to plan]
review_type: imports
---

# Import & Abstraction Audit: [Plan Name]

## Summary

| Check | Status | Issues |
|-------|--------|--------|
| Dead imports | pass/fail | N dead imports |
| Wrong abstraction | pass/fail | N wrong-level calls |
| Raw operation bypass | pass/fail | N bypasses |
| Decision checklist compliance | pass/fail | N deviations |

## Files Audited

| File | Dead Imports | Wrong Abstraction | Raw Bypass |
|------|-------------|-------------------|------------|
| path/to/file.py | 0 | 0 | 0 |
| path/to/other.py | 1 | 0 | 1 |

## Dead Imports

| File:Line | Import | Used? | Action |
|-----------|--------|-------|--------|
| module.py:3 | `from campaign_db import getCampaignsForRecruiter` | NO | Remove |
| module.py:5 | `from utils import format_date` | NO | Remove |

## Wrong Abstraction Calls

| File:Line | Call | Expected Purpose | Actual Use | Correct Alternative |
|-----------|------|-----------------|------------|-------------------|
| module.py:29 | `getCampaignsForRecruiter(id)` | Get one recruiter's campaigns | Get all campaigns | `pool.query("SELECT * FROM campaigns WHERE status = 'active'")` |

## Raw Operation Bypasses

| File:Line | Raw Operation | Helper Available? | Should Use Helper? | Reason |
|-----------|--------------|-------------------|-------------------|--------|
| module.py:31 | `pool.query("SELECT *...")` | `getAllActiveCampaigns()` exists | YES | Helper does the same query with proper error handling |
| module.py:45 | `cursor.execute(...)` | No helper | NO | Novel query, helper doesn't exist |

## Decision Checklist Compliance

| Decision | Prescribed Choice | Actual Implementation | Compliant? |
|----------|------------------|----------------------|------------|
| DC-1: Campaign fetching | Global query | Global query | YES |
| DC-2: Error handling | Log and skip | Silent skip | **NO** |

## Fixes Required

### Must Fix (code correctness)
1. **[file:line]**: [description of wrong abstraction or decision deviation]
   - Current: [what the code does]
   - Should be: [what it should do]

### Should Fix (code hygiene)
1. **[file:line]**: Remove dead import `[name]`

### Informational (acceptable deviations)
1. **[file:line]**: Raw operation used because [reason helper is wrong]

## Verdict

- [ ] **Clean** — no issues found
- [ ] **Hygiene only** — dead imports to remove, no correctness issues
- [ ] **Correctness issues** — wrong abstractions or decision deviations must be fixed before merge
```

### Step 7: Auto-Fix Dead Imports (Optional)

If the only issues are dead imports and the user approves:

```bash
# Python: remove unused import on line N
# Use Edit tool to remove the specific import line
```

Only auto-fix dead imports. Never auto-fix wrong abstractions — those require understanding intent.

### Step 8: Beads

- If correctness issues: `bd create --title="Import Audit: [name] — N wrong abstractions" --type=bug --priority=1`
- If hygiene only: `bd create --title="Import Audit: [name] — N dead imports" --type=task --priority=3`
- Link: `bd dep add <review-id> <impl-id>`

## Guidelines

- **Dead imports are always wrong.** There is no valid reason for an unused import in production code. Remove them.
- **Wrong abstraction is the critical find.** A dead import is cosmetic. Using the wrong function is a bug — it means the code does something different than intended.
- **Read the source module.** You can't judge whether `getCampaignsForRecruiter` is wrong for this use case without reading what it actually does.
- **Raw operations are sometimes correct.** If no helper exists, or the helper doesn't fit, raw SQL/IO is fine. The question is whether a BETTER abstraction was available and ignored.
- **The decision checklist is the strongest signal.** If `/cw9_review_abstraction_gap` produced a checklist and the implementation violated it, that's a clear bug — no judgment needed.
- **This review is fast.** It's mostly grep and file reads. Don't over-analyze — if an import is used, it's fine. If a function call matches the function's purpose, it's fine. Only flag clear mismatches.
- **Test files get audited too.** Dead imports in tests are less critical but still indicate the LLM was confused about what to use.
