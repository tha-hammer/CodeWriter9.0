# CW9 Plan Review (Self-Hosting)

Review a CW9 TDD plan BEFORE implementation, validating pipeline artifacts, test-to-verifier mappings, and status consistency. This is the self-hosting variant — artifacts live at CW9's own paths, not `.cw9/`.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the review — don't run out of context window before writing the report.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

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

## Process

### Step 1: Read Plan and Research

1. **Read the plan FULLY** — no partial reads
2. **Read the research document** referenced in the plan's frontmatter
3. **Extract all GWT IDs** referenced in the plan (gwt-NNNN)
4. **Check GWT ID range** — self-hosting IDs gwt-0001..0063 are allocated. New work should be gwt-0064+

### Step 2: Artifact Existence Check

Every referenced artifact must exist on disk at the **self-hosting paths**:

```bash
# For each gwt-id in the plan:
ls templates/pluscal/instances/gwt-NNNN.tla                           # verified spec
ls templates/pluscal/instances/gwt-NNNN_sim_traces.json               # simulation traces
ls python/tests/generated/gwt-NNNN_bridge_artifacts.json              # bridge artifacts
```

For each GWT, record:
- Spec exists? yes/no
- Traces exist? yes/no
- Bridge artifacts exist? yes/no

**Flag any GWT the plan references where artifacts are missing.** If the plan says "verified" but the file doesn't exist, that's critical.

**Path mismatch flag**: If the plan references `.cw9/specs/` or `.cw9/bridge/` paths, the plan was written with external-repo paths. Flag this as a cosmetic issue — the CLI routes correctly, but the plan's path references are misleading.

### Step 3: Status Consistency Check

Cross-reference plan claims against actual artifacts:

- If `templates/pluscal/instances/gwt-NNNN.tla` exists → the GWT is verified
- If the plan says "pending" but the artifact exists → **stale status** — flag it
- If the plan says "verified" but the artifact is missing → **false claim** — flag as critical

### Step 4: Context File Check

For each GWT, verify the context file exists and has a Test Interface section:

```bash
ls .cw9/context/gwt-NNNN.md
# Check for Test Interface section:
grep -l "## Test Interface" .cw9/context/gwt-NNNN.md
```

Flag:
- Missing context file → test gen will hallucinate (~60% failure rate)
- Context file without Test Interface section → same problem
- Test Interface with wrong import paths → check against actual `python/registry/` modules

### Step 5: Bridge Artifact Validation

For each GWT with bridge artifacts, read the JSON and cross-reference against the plan:

```bash
cat python/tests/generated/gwt-NNNN_bridge_artifacts.json | python3 -m json.tool
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

**Flag any verifier that has no corresponding test assertion.** These are formally verified invariants the tests don't check.

### Step 7: Simulation Trace Coverage

Read the simulation traces for each GWT:

```bash
cat templates/pluscal/instances/gwt-NNNN_sim_traces.json | python3 -m json.tool | head -200
```

Check:
1. **Happy path covered**: At least one test following the happy-path trace?
2. **Error paths covered**: Traces with failure scenarios tested?
3. **Edge cases from traces**: Interesting state transitions not in the plan's tests?

**Flag any trace pattern with no corresponding test.**

### Step 8: TLA+ Invariant Review

Read the verified spec's `define` block:

```bash
cat templates/pluscal/instances/gwt-NNNN.tla
```

Check:
1. **Are all invariants reflected in tests?** Each invariant is formally verified — should map to test assertions.
2. **Helper predicates vs standalone invariants**: Helpers used inside other invariants don't need their own test.
3. **Liveness properties**: If the spec has `THEOREM Spec => <>Property`, is there a test for eventuality?

### Step 9: Existing GWT Interaction Check (Self-Hosting Specific)

New GWTs may interact with existing verified behavior. Check:

1. **DAG edge conflicts**: Load `dag.json` and check if new GWT nodes connect to existing ones in unexpected ways
2. **Module overlap**: If the new GWT touches a module already covered by existing GWTs (gwt-0001..0063), verify the new behavior is additive, not contradictory
3. **Import path conflicts**: New generated tests shouldn't import from modules that existing tests already cover differently

### Step 10: Generate Review Report

Write to: `thoughts/searchable/shared/plans/YYYY-MM-DD-description-REVIEW.md`

````markdown
---
date: [ISO timestamp]
researcher: [name]
topic: "[Plan Name] — CW9 Review"
tags: [review, cw9, self-hosting, relevant-tags]
status: complete
reviewed_plan: [path to plan]
---

# CW9 Plan Review: [Plan Name]

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Artifact existence | pass/fail | N |
| Status consistency | pass/fail | N |
| Context file quality | pass/fail | N |
| Bridge artifact match | pass/fail | N |
| Test-to-verifier mapping | pass/fail | N gaps |
| Simulation trace coverage | pass/fail | N gaps |
| TLA+ invariant coverage | pass/fail | N gaps |
| Existing GWT interaction | pass/fail | N |
| Path correctness | pass/fail | N (wrong path references?) |

## Pipeline Artifact Status

| GWT | Spec | Traces | Bridge | Context | Plan Says | Actual |
|-----|------|--------|--------|---------|-----------|--------|
| gwt-NNNN | exists/missing | exists/missing | exists/missing | exists/missing | verified/pending | verified/missing |

Note: Self-hosting paths used — spec at `templates/pluscal/instances/`, bridge at `python/tests/generated/`

## Context File Quality

| GWT | File Exists | Test Interface | Import Paths Correct |
|-----|------------|----------------|---------------------|
| gwt-NNNN | yes/no | yes/no | yes/no |

## Verifier Coverage

### gwt-NNNN: [name]

| Verifier | Test Assertion | Covered? |
|----------|---------------|----------|
| VerifierName | `assert result.field == value` | yes |
| [MissingVerifier] | — | **NO** |

## Trace Coverage

### gwt-NNNN: [name]

| Trace Pattern | Test? | Notes |
|---|---|---|
| Happy path | yes | Step N main test |
| Error path | yes | Step N error test |
| [Uncovered pattern] | **NO** | Trace shows [description] |

## Existing GWT Interactions

| New GWT | Touches Module | Existing GWTs in Module | Conflict? |
|---------|---------------|------------------------|-----------|
| gwt-NNNN | registry/module.py | gwt-00XX, gwt-00YY | no/yes |

## Issues

### Critical (must fix before implementation)

1. **[Category]**: [description]
   - Impact: [what breaks]
   - Fix: [recommendation]

### Warnings (should fix)

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
- Link to existing plan issue: `bd dep add <review-id> <plan-id>`

## Guidelines

- **Most checks are automatable.** Use bash + file existence checks before doing manual analysis.
- **Bridge verifiers are the gold standard.** Every verifier is a formally verified invariant.
- **Check self-hosting paths, not `.cw9/` paths.** Specs at `templates/pluscal/instances/`, bridge at `python/tests/generated/`.
- **Context file quality matters.** Bad Test Interface → 60% hallucination rate in gen-tests.
- **Existing GWT interaction** is self-hosting-specific. External repos don't have 63 pre-existing verified GWTs to worry about.
- **Test command**: `cd python && python3 -m pytest tests/ -x`
