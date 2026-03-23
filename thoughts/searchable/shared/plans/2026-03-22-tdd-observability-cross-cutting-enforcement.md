---
date: 2026-03-22T00:00:00Z
researcher: DustyForge
git_commit: 3de9d36
branch: master
repository: CodeWriter9.0
topic: "Observability Cross-Cutting Enforcement TDD Plan"
tags: [plan, tdd, cw9, observability, seam-checker, cross-cutting, templates]
status: revised
last_updated: 2026-03-22
last_updated_by: DustyForge
cw9_project: /home/maceo/Dev/CodeWriter9.0
research_doc: thoughts/searchable/shared/research/2026-03-22-observability-cross-cutting-enforcement.md
---

# Observability Cross-Cutting Enforcement — TDD Implementation Plan

## Overview

Extend the seam checker to verify behavioral contracts (Option E) and add an observability-aware TLA+ template variant for service boundary specs (Option D selective). This delivers cross-cutting observability enforcement with ~5 GWTs, avoiding the 14-17 GWT cost of the full hybrid approach (A/B/C).

**Why E first**: The seam checker is already verified (gwt-0064..0067), deployed, and running. Extending it with behavioral contract rules is non-invasive — no bridge or gen-tests changes. Rules can be added/changed without re-running the pipeline.

**Why D selectively**: Formally verifying trace propagation at service boundaries (API endpoints, message queue consumers) is high value. Internal utility functions don't need it. A template variant keeps authoring cost low.

**What we're NOT doing**: Options A (bridge interceptor weaving), B (schema annotation rules consumed by bridge), and C (interceptor chain materialization) are deferred. The 10% extraction coverage problem (Finding #8) makes C impractical now, and A/B require bridge architecture changes.

## Research Reference

- Research doc: `thoughts/searchable/shared/research/2026-03-22-observability-cross-cutting-enforcement.md`
- CW9 project: `/home/maceo/Dev/CodeWriter9.0`
- Beads: `bd show cosmic-hr-3ctw`

## Verified Specs and Traces

### gwt-0068: cross_cutting_rules_loaded
- **Given**: a JSON file at the configured rules path containing an array of rule objects, each with resource_type (string), required_outs (array of strings), and position (one of pre/post/wrap)
- **When**: load_cross_cutting_rules(path) is called
- **Then**: returns a list of CrossCuttingRule dataclasses with fields populated from JSON; raises ValueError on missing fields, invalid position values, or malformed JSON; raises FileNotFoundError if file absent
- **Verified spec**: `templates/pluscal/instances/gwt-0068.tla` (attempt 4/8, TLC 0 violations)
- **Simulation traces**: `templates/pluscal/instances/gwt-0068_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-0068_bridge_artifacts.json`
  - data_structures: 1 — CrossCuttingRulesLoaderState
  - operations: 10 — ChooseFileExists, ChooseJsonValid, ChooseSchema, ReadFile, ParseJSON, ValidateRules, CheckPositions, BuildResult, RaisedError, Finish
  - verifiers: 9 — NoPartialResults, ValidPositionOnly, CompleteFields, FileAbsentImpliesError, MalformedImpliesError, InvalidSchemaImpliesError, SafeResult, EmptyRulesValid, (type invariant)

### gwt-0069: behavioral_contracts_checked
- **Given**: a list of CrossCuttingRule objects and a CrawlStore with dependency edges where some callees match a rule's resource_type but lack required OUT fields
- **When**: check_behavioral_contracts(store, rules) is called
- **Then**: returns a BehavioralReport listing each violated rule-edge pair (with rule name, callee UUID, and missing contract), counting compliant edges as satisfied, and reporting zero violations when no edges match any rule or all matching edges are compliant
- **Verified spec**: `templates/pluscal/instances/gwt-0069.tla` (attempt 3/8, TLC 0 violations)
- **Simulation traces**: `templates/pluscal/instances/gwt-0069_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-0069_bridge_artifacts.json`
  - data_structures: 1 — BehavioralContractsState
  - operations: 6 — PickEdge, CheckRules, CheckOuts, FinalizeEdge, AfterCheckedCount, Finish
  - verifiers: 8 — CountConsistency, ViolationComplete, NoFalsePositives, NoMatchNoViolation, EmptyEdgesImpliesEmptyReport, ZeroViolationsWhenAllCompliant, NoMatchNoCount, (type invariant)

### gwt-0070: cross_cutting_cli_integrated
- **Given**: cmd_seams() is invoked with --cross-cutting flag and a valid rules file exists
- **When**: cmd_seams() executes
- **Then**: output includes both the standard seam report and a behavioral report section; with --json the output includes a behavioral_violations array; without --cross-cutting the output is unchanged from existing behavior; with --cross-cutting but missing rules file, prints error to stderr and exits non-zero
- **Verified spec**: `templates/pluscal/instances/gwt-0070.tla` (attempt 1/8, TLC 0 violations)
- **Simulation traces**: `templates/pluscal/instances/gwt-0070_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-0070_bridge_artifacts.json`
  - data_structures: 1 — CrossCuttingCLIState
  - operations: 6 — ParseFlags, LoadRules, RunSeamCheck, RunBehavioralCheck, FormatOutput, Finish
  - verifiers: 8 — BackwardCompatible, FlagEnablesBehavioral, JsonIncludesBehavioral, MissingRulesError, BothReportsPresent, SeamReportAlwaysPresent, NoSpuriousBehavioralOnError, ExitCodeCleanOnSuccess

### gwt-0071: observability_template_structure
- **Given**: templates/pluscal/observability_state_machine.tla exists with trace_log and audit_log VARIABLES and TraceComplete/AuditComplete invariants
- **When**: a PlusCal algorithm instantiated from this template omits a trace_log append in any action
- **Then**: TLC reports a TraceComplete invariant violation identifying the action that failed to extend trace_log; similarly AuditComplete violations fire for state mutations missing audit_log appends
- **Verified spec**: `templates/pluscal/instances/gwt-0071.tla` (attempt 2/8, TLC 0 violations)
- **Simulation traces**: `templates/pluscal/instances/gwt-0071_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-0071_bridge_artifacts.json`
  - data_structures: 1 — observability_state_machineState
  - operations: 2 — RunLoop, Terminate
  - verifiers: 7 — ValidState, BoundedExecution, TraceComplete, AuditComplete, TraceLogMonotonic, AuditLogMonotonic, BasePreserved

### gwt-0072: template_selected_by_annotation
- **Given**: a GWT node with metadata field template set to 'observability_state_machine'
- **When**: run_loop() processes that GWT node
- **Then**: loads observability_state_machine.tla instead of state_machine.tla for prompt construction; falls back to state_machine.tla when template field is absent; raises FileNotFoundError for unknown template names
- **Verified spec**: `templates/pluscal/instances/gwt-0072.tla` (attempt 6/8, TLC 0 violations)
- **Simulation traces**: `templates/pluscal/instances/gwt-0072_sim_traces.json`
- **Bridge artifacts**: `python/tests/generated/gwt-0072_bridge_artifacts.json`
  - data_structures: 1 — TemplateSelectedByAnnotationState
  - operations: 7 — ChooseInput, ReadMeta, CheckFile, MaybeLoad, LoadContent, BuildPrompt, Terminate
  - verifiers: 8 — TypeOK, DefaultFallback, AnnotationRespected, NoSilentFallback, PromptBuiltOnlyIfLoaded, ErrorMeansNoPrompt, UnknownTemplateImpliesError, KnownTemplateNeverErrors

## What We're NOT Doing

- **Options A/B/C**: Bridge interceptor weaving, schema annotation rules consumed by bridge, interceptor chain materialization — deferred until extraction coverage improves
- **Universal observability specs**: Not retrofitting existing GWT specs with trace_log/audit_log. Template variant is for new service-boundary specs only
- **Metrics/telemetry**: No counters, gauges, histograms — deferred (schema resources don't exist yet)
- **Health check/readiness probes**: Deferred to separate feature work

## Implementation Steps

### Step 0: Cross-Cutting Rules Configuration File

**Not TLC-verified** (configuration, not behavioral). Create the initial rules file before any code — Step 1 tests use this as a fixture.

**Target file:** `schema/cross_cutting_rules.json`

```json
{
  "rules": [
    {
      "resource_type": "database",
      "required_outs": ["audit_event"],
      "position": "wrap"
    },
    {
      "resource_type": "external_api",
      "required_outs": ["span_id", "trace_context"],
      "position": "pre"
    },
    {
      "resource_type": "external_api",
      "required_outs": ["span_id", "trace_context"],
      "position": "post"
    },
    {
      "resource_type": "message_queue",
      "required_outs": ["trace_context"],
      "position": "pre"
    }
  ]
}
```

**Note:** `external_api` uses two separate rules (one `"pre"`, one `"post"`) instead of `"pre_post"`, because gwt-0068's `ValidPositionOnly` invariant validates `position ∈ {"pre", "post", "wrap"}`. This avoids re-pipelining gwt-0068.

This file is consumed by `load_cross_cutting_rules()` (Step 2) and validated by tests from gwt-0068.

---

### Step 1: CrossCuttingRule + BehavioralViolation + BehavioralReport Dataclasses

**CW9 Binding:**
- GWT: gwt-0068 (data_structures), gwt-0069 (data_structures)
- Bridge artifact: `data_structures[0]` from both artifacts

**What to implement:**

Add to `python/registry/crawl_types.py`:

```python
@dataclass
class CrossCuttingRule:
    resource_type: str          # e.g., "database", "external_api", "cache"
    required_outs: list[str]    # e.g., ["audit_event", "span_id"]
    position: str               # "pre" | "post" | "wrap"

@dataclass
class BehavioralViolation:
    rule_resource_type: str
    callee_uuid: str
    callee_function: str
    missing_contract: str
    caller_uuid: str
    caller_function: str

@dataclass
class BehavioralReport:
    violations: list[BehavioralViolation]
    satisfied: int
    total_checked: int
```

**Target files:**
- Test: `python/tests/generated/test_gwt_0068.py`, `python/tests/generated/test_gwt_0069.py`
- Implementation: `python/registry/crawl_types.py`

**Success Criteria:**
- [x] Dataclasses importable from `registry.crawl_types`
- [x] CrossCuttingRule validates position ∈ {"pre", "post", "wrap"}
- [x] BehavioralReport.total_checked == satisfied + len(violations)

---

### Step 2: load_cross_cutting_rules()

**CW9 Binding:**
- GWT: gwt-0068
- Bridge artifact: operations (ReadFile, ParseJSON, ValidateRules, CheckPositions, BuildResult, RaisedError)
- Verifiers: NoPartialResults, ValidPositionOnly, CompleteFields, FileAbsentImpliesError, MalformedImpliesError, InvalidSchemaImpliesError, SafeResult, EmptyRulesValid

**Test Specification (from simulation traces):**
- Given: valid rules file → When: load → Then: list of CrossCuttingRule with correct fields
- Given: missing file → When: load → Then: FileNotFoundError
- Given: malformed JSON → When: load → Then: ValueError
- Given: invalid position → When: load → Then: ValueError
- Given: missing required field → When: load → Then: ValueError
- Given: empty rules array → When: load → Then: empty list (no error)

**Target files:**
- Test: `python/tests/generated/test_gwt_0068.py`
- Implementation: `python/registry/seam_checker.py`

**Success Criteria:**
- [x] Tests fail for right reason (Red) — function doesn't exist yet
- [x] Tests pass (Green) — all 6 trace paths covered
- [x] NoPartialResults invariant: error ⇒ empty result, never partial

---

### Step 3: check_behavioral_contracts()

**CW9 Binding:**
- GWT: gwt-0069
- Bridge artifact: operations (PickEdge, CheckRules, CheckOuts, FinalizeEdge, AfterCheckedCount, Finish)
- Verifiers: CountConsistency, ViolationComplete, NoFalsePositives, NoMatchNoViolation, EmptyEdgesImpliesEmptyReport, ZeroViolationsWhenAllCompliant, NoMatchNoCount

**Test Specification (from simulation traces):**
- Given: 2 edges, 2 rules, one callee missing required OUT → When: check → Then: 1 violation, 1 satisfied, total_checked=2
- Given: 0 dependency edges → When: check → Then: 0 violations, 0 satisfied, 0 total_checked
- Given: all callees compliant → When: check → Then: 0 violations, N satisfied
- Given: rules with non-matching resource_type → When: check → Then: 0 violations, 0 satisfied (no edges matched)

**Resource-type matching strategy (transitional):**

The `records` table has no `resource_type` column. Until a schema migration adds one (separate prerequisite GWT), use existing fields as proxies:

- **`"external_api"`**: Match callees where `records.is_external = TRUE` (the `is_external` flag is set during extraction for external calls). Additionally, the `ins` table has `source = 'external'` for inputs sourced from external calls, and `boundary_contract` is populated on `AxRecord` entries for external boundaries.
- **`"database"`**: Match callees where `records.boundary_contract` contains `"database"` or `"db"` (case-insensitive), or where `records.file_path` matches `**/db/**` or `**/*_store.*`.
- **`"message_queue"`**: Match callees where `records.boundary_contract` contains `"queue"` or `"mq"` (case-insensitive).

This is encapsulated in a `matches_resource_type(record, rule) -> bool` helper that can be swapped for a column lookup once the schema migration lands. The TLA+ spec abstracts matching as a boolean function, so this approach is spec-compatible.

**Implementation notes:**
- Reuses `store.get_dependency_edges()` (same as `check_all_seams()`)
- For each edge, loads the callee record via `store.get_record(callee_uuid)` and checks `matches_resource_type(callee_record, rule)` for each rule
- Checks `callee.outs` for required OUT field names

**Target files:**
- Test: `python/tests/generated/test_gwt_0069.py`
- Implementation: `python/registry/seam_checker.py`

**Success Criteria:**
- [x] CountConsistency: total_checked == satisfied + len(violations)
- [x] NoFalsePositives: violation only when required OUT is genuinely absent
- [x] NoMatchNoCount: rules that match no functions → total_checked == 0
- [x] Empty edges → empty report (no errors)

---

### Step 4: CLI --cross-cutting Integration

**CW9 Binding:**
- GWT: gwt-0070
- Bridge artifact: operations (ParseFlags, LoadRules, RunSeamCheck, RunBehavioralCheck, FormatOutput, Finish)
- Verifiers: BackwardCompatible, FlagEnablesBehavioral, JsonIncludesBehavioral, MissingRulesError, BothReportsPresent, SeamReportAlwaysPresent, NoSpuriousBehavioralOnError, ExitCodeCleanOnSuccess

**Test Specification (from simulation traces):**
- Given: no --cross-cutting → When: cmd_seams → Then: output unchanged from current behavior (BackwardCompatible)
- Given: --cross-cutting + valid rules → When: cmd_seams → Then: both seam report + behavioral report in output
- Given: --cross-cutting + --json → When: cmd_seams → Then: JSON includes `behavioral` key with violations array
- Given: --cross-cutting + missing rules → When: cmd_seams → Then: stderr error, exit code 1, NO behavioral report in output (NoSpuriousBehavioralOnError)
- Given: --cross-cutting + valid rules + no violations → When: cmd_seams → Then: exit code 0 (ExitCodeCleanOnSuccess)

**Implementation notes:**
- Add `--cross-cutting` argument to seams subparser (at `p_seams` definition in CLI parser setup)
- In `cmd_seams()` function, conditionally load rules and run behavioral check
- Extend `seam_report_to_json()` to optionally include behavioral report
- Add `render_behavioral_report()` text formatter

**Target files:**
- Test: `python/tests/generated/test_gwt_0070.py`
- Implementation: `python/registry/cli.py`, `python/registry/seam_checker.py`

**Success Criteria:**
- [x] Without --cross-cutting, output byte-for-byte identical to current
- [x] With --cross-cutting, behavioral violations appear in output
- [x] Missing rules file → stderr error, exit 1, no behavioral report in output
- [x] Successful run with no violations → exit code 0

---

### Step 5: Observability TLA+ Template

**CW9 Binding:**
- GWT: gwt-0071
- Bridge artifact: operations (RunLoop, Terminate), verifiers (TraceComplete, AuditComplete, TraceLogMonotonic, AuditLogMonotonic, ValidState, BoundedExecution, BasePreserved)

**What to create:**
- New file: `templates/pluscal/observability_state_machine.tla`
- Extends state_machine.tla pattern with:
  - `trace_log` variable (sequence of span records)
  - `audit_log` variable (sequence of mutation records)
  - `TraceComplete` invariant: step_count > 0 ⇒ Len(trace_log) >= step_count
  - `AuditComplete` invariant: Len(history) > 0 ⇒ Len(audit_log) >= Len(history)

**Test Specification (from simulation traces):**
- Given: 3-state machine (init→processing→done) with trace/audit appends → When: TLC checks → Then: all invariants hold
- Given: action that skips trace_log append → When: TLC checks → Then: TraceComplete violation

**Target files:**
- Test: `python/tests/generated/test_gwt_0071.py` (structural test — file exists, contains expected elements)
- Implementation: `templates/pluscal/observability_state_machine.tla`

**Success Criteria:**
- [x] Template file exists and contains trace_log, audit_log, TraceComplete, AuditComplete
- [x] Template preserves all base state_machine constructs (ValidState, BoundedExecution)
- [ ] A PlusCal spec using this template that omits trace appends fails TLC

---

### Step 6: Template Selection by GWT Annotation

**CW9 Binding:**
- GWT: gwt-0072
- Bridge artifact: operations (ChooseInput, ReadMeta, CheckFile, MaybeLoad, LoadContent, BuildPrompt, Terminate)
- Verifiers: DefaultFallback, AnnotationRespected, NoSilentFallback, PromptBuiltOnlyIfLoaded, ErrorMeansNoPrompt, UnknownTemplateImpliesError, KnownTemplateNeverErrors

**Test Specification (from simulation traces):**
- Given: GWT metadata has template="observability_state_machine" → When: run_loop resolves template → Then: loads observability_state_machine.tla
- Given: GWT metadata is None/absent → When: run_loop resolves template → Then: loads state_machine.tla (default)
- Given: GWT metadata has template="nonexistent" → When: run_loop resolves template → Then: FileNotFoundError raised (no silent fallback)

**Implementation notes:**
- Extract a `resolve_template_name(gwt_node, template_dir) -> tuple[str, Path]` function in `loop_runner.py`
- Replace hardcoded `state_machine.tla` in `run_loop()` with a call to `resolve_template_name()`
- `resolve_template_name()` checks `gwt_node.metadata.get("template", "state_machine")`, validates the file exists, raises `FileNotFoundError` if not
- Node.metadata dict is already supported in dag.py

**Target files:**
- Test: `python/tests/generated/test_gwt_0072.py`
- Implementation: `python/registry/loop_runner.py`

**Success Criteria:**
- [x] Default behavior preserved when no metadata.template
- [x] Named template loaded when metadata.template is set
- [x] Unknown template raises FileNotFoundError (NoSilentFallback)

## Integration Testing

After all steps are implemented:

1. **End-to-end seam check with behavioral contracts:**
   ```bash
   cw9 seams . --cross-cutting
   cw9 seams . --cross-cutting --json
   ```
   Verify both human-readable and JSON output contain behavioral violations.

2. **Template selection integration:**
   - Register a test GWT with `metadata: {"template": "observability_state_machine"}`
   - Run `cw9 loop <test-gwt> .` and verify the observability template is used in the prompt

3. **Regression: existing seam checker unchanged:**
   ```bash
   cw9 seams .  # no --cross-cutting flag
   ```
   Output must match pre-implementation behavior exactly.

## Verification

After implementation, re-verify:
```bash
cd python && python3 -m pytest tests/ -x
cw9 status . --json  # confirm gwt-0068..0072 still verified
cw9 seams . --cross-cutting  # smoke test the new feature
```

## References

- Research: `thoughts/searchable/shared/research/2026-03-22-observability-cross-cutting-enforcement.md`
- Verified specs: `templates/pluscal/instances/gwt-006{8,9}.tla`, `gwt-007{0,1,2}.tla`
- Bridge artifacts: `python/tests/generated/gwt-006{8,9}_bridge_artifacts.json`, `gwt-007{0,1,2}_bridge_artifacts.json`
- Existing seam checker: `python/registry/seam_checker.py` (gwt-0064..0067)
- Beads: `bd show cosmic-hr-3ctw`
