# CW9 Plan Review

Review a CW9 TDD plan BEFORE implementation, validating pipeline artifacts, UUID bindings, test-to-verifier mappings, and status consistency.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the review — don't run out of context window before writing the report.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = path to CW9 TDD plan. If not provided, search `thoughts/searchable/shared/plans/` for recent `*cw9*` plans.

## Process

### Step 1: Read Plan and Research

1. **Read the plan FULLY** — no partial reads
2. **Read the research document** referenced in the plan's frontmatter
3. **Identify the CW9 project path** from the plan's `cw9_project` field
4. **Extract all GWT IDs** referenced in the plan (gwt-NNNN)
5. **Extract all UUIDs** referenced in `depends_on` fields

### Step 2: Artifact Existence Check

Run these checks via bash. Every referenced artifact must exist on disk.

```bash
PROJECT="<cw9_project path>"

# For each gwt-id in the plan:
ls "$PROJECT/.cw9/specs/gwt-NNNN.tla"                    # verified spec
ls "$PROJECT/.cw9/specs/gwt-NNNN_sim_traces.json"         # simulation traces
ls "$PROJECT/.cw9/bridge/gwt-NNNN_bridge_artifacts.json"  # bridge artifacts
```

For each GWT, record:
- Spec exists? yes/no
- Traces exist? yes/no
- Bridge artifacts exist? yes/no

**Flag any GWT the plan references where artifacts are missing.** If the plan says "verified" but the file doesn't exist, that's critical.

### Step 3: Status Consistency Check

The plan may contain status claims like "verified, pass", "pending", "blocked by crawl". Cross-reference against actual artifacts:

- If `.cw9/specs/gwt-NNNN.tla` exists → the GWT is verified (regardless of what the plan text says)
- If the plan says "pending" or "blocked" but the artifact exists → **stale status** — flag it
- If the plan says "verified" but the artifact is missing → **false claim** — flag it as critical

Also check the plan's frontmatter `status` field. If all GWTs are verified and all artifacts exist, the plan should be `review` or `approved`, not `draft`.

### Step 4: UUID Validity Check

Every `depends_on` UUID in the plan must exist in crawl.db:

```bash
# Collect all UUIDs from the plan (short or full form)
# Then verify each one:
sqlite3 "$PROJECT/.cw9/crawl.db" \
  "SELECT uuid, function_name, file_path FROM records WHERE uuid LIKE 'UUID_PREFIX%';"
```

For each UUID, verify:
- Record exists in crawl.db?
- Function name matches what the plan says?
- File path matches what the plan says?
- Is the record a skeleton or fully extracted? (`do_description = 'SKELETON_ONLY'` vs real content)

**Flag any UUID that doesn't exist or points to the wrong function.**

### Step 5: Bridge Artifact Validation

For each GWT with bridge artifacts, read the JSON and cross-reference against the plan:

```bash
cat "$PROJECT/.cw9/bridge/gwt-NNNN_bridge_artifacts.json" | python3 -m json.tool
```

Check:
1. **Operation count matches**: Does the plan's listed operation count match the actual artifact?
2. **Verifier count matches**: Same for verifiers.
3. **Operation names match**: Are the operation names in the plan the same as in the artifact?
4. **Verifier names match**: Same for verifiers.

**Flag any mismatch** — the plan may have been written from an earlier pipeline run.

### Step 6: Test-to-Verifier Mapping

For each implementation step, check that the test assertions map to bridge verifiers:

1. **List all verifiers** from the bridge artifacts for that step's GWT
2. **Read the test code** in the plan's Red phase
3. **Check coverage**: Does each verifier have a corresponding test assertion?

Common patterns:
- `AtMostOneBAMLCall` → `expect(mock).toHaveBeenCalledTimes(1)`
- `PromptContainsCandidateData` → `expect(prompt).toContain('...')`
- `OnDoneNotCalledOnError` → `expect(onDone).not.toHaveBeenCalled()`
- `ToolCallsAlwaysEmpty` → `expect(result.toolCalls).toEqual([])`

**Flag any verifier that has no corresponding test assertion.** These are formally verified invariants that the tests don't check.

### Step 7: Simulation Trace Coverage

Read the simulation traces for each GWT:

```bash
cat "$PROJECT/.cw9/specs/gwt-NNNN_sim_traces.json" | python3 -m json.tool | head -200
```

Check:
1. **Happy path covered**: Is there at least one test that follows the happy-path trace (all steps succeed)?
2. **Error paths covered**: Do the traces include failure scenarios? Are those tested?
3. **Edge cases from traces**: Do any traces show interesting state transitions (retries, partial progress, abort) that aren't in the plan's tests?

**Flag any trace pattern that has no corresponding test in the plan.**

### Step 8: TLA+ Invariant Review

Read the verified spec's `define` block:

```bash
# Extract the define block from the verified spec
cat "$PROJECT/.cw9/specs/gwt-NNNN.tla"
```

The `define` block contains invariants that TLC proved hold for ALL reachable states. Check:
1. **Are all invariants reflected in tests?** Each invariant is a formally verified property — it should map to at least one test assertion.
2. **Helper predicates vs invariants**: If the spec has predicates that are used inside other invariants (not standalone invariants themselves), they don't need their own test — but make sure the containing invariant is tested.
3. **Liveness properties**: If the spec has `THEOREM Spec => <>Property` (eventuality), is there a test that verifies the system eventually reaches that state?

### Step 9: Dead Code and Scope Check

If the plan includes a delete/refactor step:
1. **UUID completeness**: Are all functions being deleted listed with their crawl.db UUIDs?
2. **Caller check**: For each function being deleted, verify no remaining code calls it:
   ```bash
   sqlite3 "$PROJECT/.cw9/crawl.db" \
     "SELECT r.function_name, r.file_path FROM records r JOIN ins i ON r.uuid = i.record_uuid WHERE i.source = 'internal_call' AND i.source_function = 'DELETED_FUNCTION_NAME';"
   ```
3. **Import cleanup**: Does the plan address removing imports for deleted functions?

If the plan has a "What We're NOT Doing" section:
- Verify the exclusions are consistent with the GWT `depends_on` UUIDs (i.e., excluded code shouldn't appear in depends_on)

### Step 10: Generate Review Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-REVIEW.md` (same name as plan + `-REVIEW`)

Use this structure:

````markdown
---
date: [ISO timestamp]
researcher: [name]
topic: "[Plan Name] — CW9 Review"
tags: [review, cw9, relevant-tags]
status: complete
reviewed_plan: [path to plan]
---

# CW9 Plan Review: [Plan Name]

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | pass/fail | N |
| Status consistency | pass/fail | N |
| UUID validity | pass/fail | N |
| Bridge artifact match | pass/fail | N |
| Test-to-verifier mapping | pass/fail | N gaps |
| Simulation trace coverage | pass/fail | N gaps |
| TLA+ invariant coverage | pass/fail | N gaps |
| Dead code / scope | pass/fail | N |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Plan Says | Actual |
|-----|------|--------|--------|-----------|--------|
| gwt-NNNN | exists/missing | exists/missing | exists/missing | verified/pending | verified/missing |

## UUID Validity

| UUID (short) | Plan Says | crawl.db Says | Match? |
|---|---|---|---|
| `c1164b77` | buildSystemPrompt @ chatAgentService.js:20 | [actual] | yes/no |

## Verifier Coverage

### gwt-NNNN: [name]

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| AtMostOneBAMLCall | `expect(mock).toHaveBeenCalledTimes(1)` | yes |
| PromptContainsCandidateData | `expect(prompt).toContain('Alice')` | yes |
| [MissingVerifier] | — | **NO** |

## Trace Coverage

### gwt-NNNN: [name]

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path (all succeed) | yes | Step 2 main test |
| Error during streaming | yes | Step 3 error test |
| [Uncovered pattern] | **NO** | Trace shows [description] |

## TLA+ Invariant Coverage

### gwt-NNNN: [name]

| Invariant | Test? | Notes |
|---|---|---|
| ValidPhase | implicit | Phase transitions tested via happy/error paths |
| CompletedImpliesAllDone | yes | onDone assertion |
| [Uncovered invariant] | **NO** | [what it means] |

## Issues

### Critical (must fix before implementation)

1. **[Category]**: [description]
   - Impact: [what breaks]
   - Fix: [recommendation]

### Warnings (should fix)

1. **[Category]**: [description]
   - Impact: [what could go wrong]
   - Fix: [recommendation]

### Cosmetic (nice to fix)

1. **[Category]**: [description]
   - Fix: [recommendation]

## Approval Status

- [ ] **Ready for `/cw9_implement`** — no critical issues
- [ ] **Needs minor revision** — warnings should be addressed
- [ ] **Needs major revision** — critical issues must be resolved
- [ ] **Needs re-pipeline** — artifacts are missing or stale
````

### Step 11: Beads

- If critical issues found: `bd create --title="Plan Review: [name]" --type=task --priority=1`
- Link to existing plan issue if one exists: `bd dep add <review-id> <plan-id>`
- Sync: `bd dolt push && bd dolt pull`

## Guidelines

- **Most checks are automatable.** Use bash + sqlite3 + file existence checks before doing manual analysis. Don't eyeball what you can verify programmatically.
- **Bridge verifiers are the gold standard.** Every verifier in the bridge artifacts represents a formally verified invariant. If a test doesn't check it, that's a real gap.
- **Stale status is common.** Plans are often written while the pipeline is still running. Status claims go stale fast. Always check the actual artifacts.
- **Short UUIDs are fine.** The plan may use 8-char UUID prefixes (`c1164b77`). Use `LIKE 'prefix%'` in sqlite3 to match.
- **Simulation traces reveal edge cases the plan author may have missed.** Read at least the first 3 traces for each GWT to see if there are interesting execution paths not covered by tests.
- **The TLA+ define block is the strongest signal.** If an invariant is in the define block of a verified spec, it holds for ALL reachable states. If no test checks it, that invariant is unguarded in the implementation.
