---
date: 2026-03-22T00:00:00Z
researcher: DustyForge
git_commit: 7325cb2
branch: master
repository: CodeWriter9.0
topic: "Observability enforcement as cross-cutting concern in bridge and schema"
tags: [research, cw9, observability, bridge, interceptors, cross-cutting, schema]
status: complete
last_updated: 2026-03-22
last_updated_by: DustyForge
revision_history:
  - date: 2026-03-22
    author: DustyForge
    change: "Added Section: Horizontal Contract Tracing (Seam Checker) — new Option E and updated recommendations"
cw9_project: /home/maceo/Dev/CodeWriter9.0
---

# Research: Observability Enforcement as Cross-Cutting Concern

## Research Question

Logging configuration exists as a schema resource, but observability and traceability are not enforced as cross-cutting behavioral concerns in generated code. How can the pipeline enforce that every operation emits structured traces, every state mutation writes an audit record, and every service boundary propagates trace context?

## Current State Analysis

### Schema Resources: What Exists (Passive Configuration Only)

The schema (`schema/resource_registry.generic.json`) has 66 resources across 6 types. The observability-related resources are:

| ID | Name | Path | Role |
|---|---|---|---|
| `cfg-p4b8` | `shared_logging` | `shared/logging` | Cross-layer log format, levels, outputs, aggregation, filters |
| `cfg-q9c5` | `backend_logging` | `backend/logging` | Processing layer log format, levels, outputs |
| `cfg-r3d7` | `frontend_logging` | `frontend/logging` | Interface layer log format, levels, outputs |
| `db-l1c3` | `backend_error_definitions` | `backend/error_definitions/ErrorType` | Error codes, messages, categories |
| `cfg-j9w2` | `shared_error_definitions` | `shared/error_definitions/ErrorType` | Cross-layer error codes, categories, severity |

These are **configuration** resources — they define *what* logging looks like but not *where* or *when* it must happen.

### Interceptor Infrastructure: The Natural Hook Points

Four resources define an execution pipeline model:

| ID | Name | Path | Role |
|---|---|---|---|
| `mq-s9b4` | `interceptor` | `middleware/interceptors/InterceptorName` | Hooks into execution stages with priority and conditions |
| `mq-t2f7` | `execution_pattern` | `middleware/execution_patterns/PatternName` | Trigger conditions, rules, bypass logic |
| `mq-u6j3` | `middleware_process_chain` | `middleware/process_chains/ChainName` | Ordered interceptor chain with pre/post processing stages |
| `mq-c1g5` | `interceptor_interface` | `shared/interceptor_interfaces/` | Contract defining interceptor method signatures |

Plus supplementary:
- `api-p3e6` (filter) — request/response pipeline interceptor with conditions
- `mq-r4z8` (backend_process_chain) — ordered sequence of processor operations

**Key insight**: The interceptor model already has the right topology — ordered chains with priority, conditions, and pre/post stages. But nothing connects "this interceptor exists" to "generated code must invoke it at every matching execution point."

### What's Absent from the Schema

No resources exist for:
- **Metrics / telemetry** — no counters, gauges, histograms, or metric emission points
- **Audit trail / event journal** — no structured event recording for state mutations
- **Health check / readiness probe** — no liveness or readiness endpoints
- **Trace context / correlation ID / span** — no distributed tracing primitives
- **Structured event** — no typed event envelope for observability data

## Bridge Architecture: The Enforcement Gap

### What the Bridge Produces (6 Categories)

The bridge (`python/registry/bridge.py:692`) translates TLA+ specs into:

| Category | Translator | Source | Purpose |
|---|---|---|---|
| `data_structures` | `translate_state_vars()` (:291) | VARIABLES + Init | State shape |
| `operations` | `translate_actions()` (:377) | Named actions with primed vars | Behavioral contracts |
| `verifiers` | `translate_invariants_to_verifiers()` (:475) | Invariants in define block | Validation rules |
| `assertions` | `translate_invariants_to_assertions()` (:511) | Same invariants, different shape | Test assertions |
| `test_scenarios` | `translate_traces()` (:613) | TLC counterexample traces | Concrete test cases |
| `simulation_traces` | (raw file passthrough) | `_sim_traces.json` | Primary test context |

### What gen-tests Actually Consumes

Of the 6 categories, `cmd_gen_tests()` (`cli.py:360`) uses only:

1. **`verifiers`** — compiled into invariant translations for test plan prompt (`test_gen_loop.py:138,167-180`) and review ground truth (`test_gen_loop.py:242`)
2. **`simulation_traces`** — primary test generation context (`test_gen_loop.py:150`)
3. **`test_scenarios`** — secondary fallback context (`test_gen_loop.py:195`)

**`data_structures`, `operations`, and `assertions` are written to the artifact file but never read by gen-tests.**

### The Structural Gap

The bridge is a **functional translator**: it maps TLA+ model elements (variables → data, actions → operations, invariants → verifiers). Cross-cutting concerns are inherently **non-functional** — they cut across all operations rather than mapping to any single TLA+ element.

There is no bridge output category for:
- "every operation must emit a structured trace"
- "every state mutation writes an audit record"
- "this is a service boundary, therefore propagate trace context"

## Injection Points for Cross-Cutting Enforcement

### Option A: New Bridge Translator (Interceptor Weaving)

Add a 5th mechanical translator that reads interceptor/middleware resources from the schema and weaves them into the operations category. Touches:

1. `bridge.py:680-689` — add `cross_cutting` field to `BridgeResult`
2. `bridge.py:692-720` — new translator: `translate_cross_cutting(spec, schema_resources)`
3. `cli.py:319-331` — add to artifact dict assembly
4. `cli.py:403-433` — extract in gen-tests context assembly
5. `test_gen_loop.py:31-53` — add field to `TestGenContext`
6. `test_gen_loop.py:126-233` — add prompt section in `build_test_plan_prompt()`
7. `test_gen_loop.py:236-251` — optionally add to review ground truth

**Challenge**: The bridge currently takes only `tla_text` and `traces` as input. It has no access to the schema. Making it schema-aware would break the "bridge is mechanical" principle unless the schema information is pre-resolved.

### Option B: Schema-Level Observability Resources + Bridge Annotation Rules

Two-phase approach:

**Phase 1 — Schema additions** (new resources in `resource_registry.generic.json`):
- `cfg-NEW1` `trace_context`: correlation_id, span_id, parent_span, baggage
- `cfg-NEW2` `metrics_definition`: counter/gauge/histogram definitions, labels, emission points
- `cfg-NEW3` `audit_event`: event_type, entity, action, actor, timestamp, payload_schema
- `cfg-NEW4` `health_probe`: endpoint, checks, timeout, dependencies
- `cfg-NEW5` `structured_event_envelope`: event schema, routing, serialization

**Phase 2 — Annotation rules** (new file, e.g., `schema/cross_cutting_rules.json`):
```json
{
  "rules": [
    {
      "trigger": "operation_touches_resource_type",
      "resource_types": ["database", "external_api"],
      "inject": ["audit_event", "trace_context"],
      "position": "wrap"
    },
    {
      "trigger": "service_boundary",
      "patterns": ["endpoint", "message_queue"],
      "inject": ["trace_context", "metrics_definition"],
      "position": "pre_post"
    }
  ]
}
```

The bridge would load these rules and annotate each operation with which cross-cutting concerns apply, based on the operation's parameter types and the resources it touches.

### Option C: Interceptor Chain Materialization

Use the existing interceptor infrastructure (`mq-s9b4`, `mq-t2f7`, `mq-u6j3`) as the enforcement mechanism:

1. Define concrete interceptor instances for observability (tracing interceptor, audit interceptor, metrics interceptor)
2. Define execution patterns that bind interceptors to operation categories
3. Add a bridge step that materializes the interceptor chain for each operation, producing a `required_interceptors` annotation

This is the most architecturally aligned option because interceptors are already modeled as execution pipeline hooks. The gap is: no concrete instances exist, no binding rules exist, and the bridge doesn't read them.

### Option D: TLA+ Model-Level Observability (Verify the Cross-Cutting Concern)

The most CW9-native approach: model observability as a **verified behavioral property**.

1. Add `trace_log` and `audit_log` as TLA+ variables in specs
2. Add invariants like: `AuditComplete == \A op \in executed_ops : \E entry \in audit_log : entry.op = op`
3. The TLC verifier then **proves** that every operation path produces an audit entry
4. The bridge translates these naturally: `trace_log` → data_structure, audit invariant → verifier

**Advantage**: This is the only option where observability is **formally verified**, not just injected.
**Challenge**: It requires every GWT spec to include observability variables, which is a significant authoring burden. Could be mitigated by a TLA+ template that includes observability variables by default.

### Option E: Seam Checker as Cross-Cutting Enforcement (NEW — post-440f184)

Since the original research, the **horizontal contract verification** system (`cw9 seams`) was implemented and formally verified (gwt-0064..0067, req-0017). This fundamentally changes the cross-cutting enforcement landscape.

#### What Exists Now

| Component | Location | Purpose |
|---|---|---|
| `seam_checker.py` | `python/registry/seam_checker.py` | Core seam analysis: `check_seam()`, `check_all_seams()`, `render_seam_report()`, `seam_report_to_json()` |
| `SeamMismatch` | `python/registry/crawl_types.py:219` | Dataclass: caller/callee UUIDs, functions, type info, dispatch kind, severity |
| `SeamReport` | `python/registry/crawl_types.py:233` | Aggregate: mismatches, unresolved edges, satisfied count, total edges |
| `CrawlStore.get_dependency_edges()` | `python/registry/crawl_store.py:594` | Reads `deps` view — all resolved caller→callee edges |
| `CrawlStore.get_unresolved_internal_calls()` | `python/registry/crawl_store.py:602` | Finds `internal_call` ins with no resolved `source_uuid` |
| `cmd_seams()` | `python/registry/cli.py:1697` | CLI command: `cw9 seams [target] [--json] [--verbose]` |
| `type_compatible()` | `python/registry/seam_checker.py:42` | 3-tier type matching: exact → normalized → structural subtype |

#### How Seam Checking Works

The seam checker compares **caller outputs** against **callee inputs** at every resolved dependency edge in `crawl.db`:

1. Query the `deps` view for all `(caller_uuid, callee_uuid)` edges
2. For each edge, find callee inputs sourced from the caller (`ins.source == 'internal_call' AND ins.source_uuid == caller_uuid`)
3. Compare caller's `ok` output type against callee's expected input type using `type_compatible()`
4. Report mismatches (type incompatibility), unresolved edges (no `source_uuid`), and satisfied seams

Severity levels:
- `type_mismatch` — caller provides type X, callee expects type Y, incompatible
- `no_ok_output` — caller has no `ok` output but callee expects one
- `unresolved` — `internal_call` edge with no resolved `source_uuid`

#### How This Applies to Observability Enforcement

The seam checker currently verifies **type contracts** at function boundaries. The same edge-walking infrastructure can verify **behavioral contracts** — including observability requirements:

1. **Trace propagation at service boundaries**: If a function is tagged as a service boundary (via schema annotation or interceptor binding), the seam checker can verify that its callers/callees include trace context in their IN/OUT contracts. A callee that expects `trace_id: str` as an input but whose caller doesn't produce one is a seam mismatch — the same way a type mismatch is detected today.

2. **Audit record emission**: If an operation touches a data store resource, the seam checker can verify that its OUT contract includes an `audit_event` side effect. Missing audit emission becomes a `no_ok_output`-class mismatch.

3. **Interceptor chain enforcement**: Rather than the bridge annotating operations with `required_interceptors` (Option A/C), the seam checker can verify post-hoc that interceptor contracts are satisfied. If an interceptor's IN contract specifies `source = 'internal_call'` from a specific operation, the seam checker validates the edge exists and types match.

#### Key Advantage Over Options A-D

Options A-D propose **injecting** cross-cutting concerns into the pipeline (bridge annotations, TLA+ variables, interceptor bindings). Option E **verifies** them after the fact using the same crawl.db infrastructure that already tracks all function boundaries. This is:

- **Non-invasive**: No bridge changes, no TLA+ template changes, no gen-tests prompt changes
- **Already verified**: The seam checker itself is formally verified (gwt-0064..0067, TLC-verified, 0 violations)
- **Compositional**: New cross-cutting rules are just new IN/OUT contract expectations to check — the `check_seam()` algorithm doesn't change
- **Actionable today**: `cw9 seams` already runs against any crawl.db and produces structured reports

#### What's Missing for Option E

1. **Behavioral contract categories**: The seam checker only compares type strings. Cross-cutting concerns need richer matching — e.g., "callee must have an OUT with `name = 'side_effect'` whose `description` mentions 'audit'" or "caller must propagate a specific named input to callee."
2. **Schema-aware rules**: The seam checker doesn't know about schema resources. It needs a way to say "functions touching resource type X must satisfy contract Y" — similar to Option B's annotation rules, but consumed by the seam checker rather than the bridge.
3. **Dispatch-aware checking**: All 39 currently resolved edges use `dispatch = 'direct'`. Cross-cutting concerns like interceptors use `attribute`, `callback`, and `protocol` dispatch. The seam checker handles these but the crawl extraction doesn't resolve them yet.

## Recommended Approach: Hybrid (Options C + D + E)

### Immediate (Option E): Seam Checker Enforcement (NEW)
- Define cross-cutting contract rules in `schema/cross_cutting_rules.json`
- Extend `check_seam()` to verify behavioral contracts (not just type strings)
- `cw9 seams --cross-cutting` flag to run behavioral contract checks alongside type checks
- Seam report surfaces "function X touches data store but has no audit side_effect in OUT"
- **No bridge or gen-tests changes required** — enforcement is post-hoc via crawl.db

### Near-term (Option C): Interceptor Materialization
- Add concrete observability interceptor instances to the schema
- Add binding rules that connect resource types to required interceptors
- Seam checker verifies interceptor contracts are satisfied (replaces bridge annotation from original proposal)
- gen-tests prompt includes "every operation annotated with tracing must emit a span"

### Long-term (Option D): Verified Observability
- Add a TLA+ template variant that includes `trace_log`/`audit_log` variables
- `cw9 loop` uses this template for specs touching data stores or service boundaries
- TLC verifies that every execution path produces the required observability events
- Bridge translates naturally — no special cross-cutting machinery needed

### Implementation Path (revised)

1. **Cross-cutting rules file**: `schema/cross_cutting_rules.json` mapping resource types → required behavioral contracts (e.g., "functions touching `database` resources must have `audit_event` in outs")
2. **Seam checker extension**: `check_behavioral_contracts(store, rules)` — walks edges and verifies behavioral rules, reusing the existing `check_all_seams()` infrastructure
3. **Schema additions**: 5 new observability resources + concrete interceptor instances
4. **Interceptor binding**: Connect interceptor instances to operation categories via execution patterns
5. **gen-tests extension**: prompt section translates interceptor annotations into test requirements
6. **TLA+ template variant**: observability-aware template for formal verification of cross-cutting concerns

### Estimated Scope (revised)

- Cross-cutting rules + seam checker extension: 2-3 GWTs (rules loader + behavioral contract check + CLI flag)
- Schema additions: 5 new resources + 3 concrete interceptor instances → 8 GWTs
- gen-tests extension: prompt changes + new `TestGenContext` field → 1-2 GWTs
- TLA+ template variant: new template + loop integration → 2-3 GWTs
- **Total: 14-17 new GWTs across three phases** (but Phase 1 delivers value immediately with ~3 GWTs)

## Findings Summary

1. **The schema has the topology but not the instances.** The interceptor infrastructure (`mq-s9b4`, `mq-t2f7`, `mq-u6j3`) models hooks, chains, and patterns — but no concrete observability interceptors are defined.

2. **The bridge is functionally complete but cross-cutting-blind.** It maps TLA+ elements 1:1 to code artifacts. Cross-cutting concerns require N:1 mapping (many operations → one concern), which the current architecture doesn't support.

3. **gen-tests ignores 3 of 6 bridge categories.** `data_structures`, `operations`, and `assertions` are written but never consumed. This is wasted signal that could carry cross-cutting annotations.

4. **The most CW9-native solution is formal verification of observability** — modeling trace/audit logs as TLA+ variables with invariants. This makes observability a verified property, not a bolted-on annotation. But it requires template changes and higher authoring cost.

5. **The pragmatic near-term path is interceptor materialization** — concrete instances + binding rules + bridge annotations. This reuses existing schema infrastructure and requires the least architectural change.

6. **(NEW) The seam checker provides an immediate enforcement path.** The `cw9 seams` command (commit `440f184`, formally verified gwt-0064..0067) already walks every dependency edge in crawl.db and compares caller outputs against callee inputs. Extending `check_seam()` to verify behavioral contracts (not just type strings) would give cross-cutting enforcement with **zero bridge or gen-tests changes**. The seam checker's edge-walking infrastructure is the natural place for "every function touching resource type X must satisfy behavioral contract Y" rules.

7. **(NEW) Seam checking shifts enforcement from generation-time to verification-time.** Options A-D inject cross-cutting concerns during code generation. Option E verifies them after the fact. This is architecturally preferable because: (a) the crawl.db already contains the full call graph, (b) verification is idempotent and re-runnable (`cw9 seams` can run any time), and (c) rules can be added/changed without re-running the entire pipeline. The tradeoff: verification-time enforcement catches violations but doesn't prevent them — generated code may still lack observability until the seam report is acted on.

8. **(NEW) Extraction coverage limits seam checking effectiveness.** As noted in the horizontal contract verification research, only 158/1567 records (10%) had full IN:DO:OUT cards at the time of analysis. Seam checking quality — including cross-cutting behavioral verification — scales directly with extraction coverage. Running `cw9 crawl --incremental` to fill out skeleton records is a prerequisite for meaningful cross-cutting enforcement.

## CW9 Mention Summary
Functions: run_bridge(), translate_state_vars(), translate_actions(), translate_invariants_to_verifiers(), translate_invariants_to_assertions(), translate_traces(), cmd_bridge(), _run_bridge_core(), cmd_gen_tests(), run_test_gen_loop(), build_test_plan_prompt(), build_review_prompt(), build_codegen_prompt(), build_compiler_hints(), build_structural_patterns(), check_seam(), check_all_seams(), type_compatible(), render_seam_report(), seam_report_to_json(), cmd_seams(), get_dependency_edges(), get_unresolved_internal_calls()
Files: python/registry/bridge.py, python/registry/cli.py, python/registry/test_gen_loop.py, schema/resource_registry.generic.json, python/registry/lang.py, python/registry/seam_checker.py, python/registry/crawl_store.py, python/registry/crawl_types.py
Directories: python/registry/, schema/, templates/pluscal/
