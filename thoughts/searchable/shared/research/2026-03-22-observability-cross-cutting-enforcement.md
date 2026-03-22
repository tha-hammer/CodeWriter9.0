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

## Recommended Approach: Hybrid (Options C + D)

### Near-term (Option C): Interceptor Materialization
- Add concrete observability interceptor instances to the schema
- Add binding rules that connect resource types to required interceptors
- Extend the bridge to annotate operations with `required_interceptors`
- gen-tests prompt includes "every operation annotated with tracing must emit a span"

### Long-term (Option D): Verified Observability
- Add a TLA+ template variant that includes `trace_log`/`audit_log` variables
- `cw9 loop` uses this template for specs touching data stores or service boundaries
- TLC verifies that every execution path produces the required observability events
- Bridge translates naturally — no special cross-cutting machinery needed

### Implementation Path

1. **Schema additions**: 5 new observability resources + concrete interceptor instances
2. **Cross-cutting rules file**: `schema/cross_cutting_rules.json` mapping resource types → required interceptors
3. **Bridge extension**: new translator reads rules, annotates operations with `required_interceptors`
4. **gen-tests extension**: new prompt section translates interceptor annotations into test requirements
5. **TLA+ template variant**: observability-aware template for formal verification of cross-cutting concerns

### Estimated Scope

- Schema additions: 5 new resources + 3 concrete interceptor instances → 8 GWTs
- Bridge extension: 1 new translator + 1 rule loader → 2 GWTs
- gen-tests extension: prompt changes + new `TestGenContext` field → 1-2 GWTs
- TLA+ template variant: new template + loop integration → 2-3 GWTs
- **Total: 13-15 new GWTs across the two phases**

## Findings Summary

1. **The schema has the topology but not the instances.** The interceptor infrastructure (`mq-s9b4`, `mq-t2f7`, `mq-u6j3`) models hooks, chains, and patterns — but no concrete observability interceptors are defined.

2. **The bridge is functionally complete but cross-cutting-blind.** It maps TLA+ elements 1:1 to code artifacts. Cross-cutting concerns require N:1 mapping (many operations → one concern), which the current architecture doesn't support.

3. **gen-tests ignores 3 of 6 bridge categories.** `data_structures`, `operations`, and `assertions` are written but never consumed. This is wasted signal that could carry cross-cutting annotations.

4. **The most CW9-native solution is formal verification of observability** — modeling trace/audit logs as TLA+ variables with invariants. This makes observability a verified property, not a bolted-on annotation. But it requires template changes and higher authoring cost.

5. **The pragmatic near-term path is interceptor materialization** — concrete instances + binding rules + bridge annotations. This reuses existing schema infrastructure and requires the least architectural change.

## CW9 Mention Summary
Functions: run_bridge(), translate_state_vars(), translate_actions(), translate_invariants_to_verifiers(), translate_invariants_to_assertions(), translate_traces(), cmd_bridge(), _run_bridge_core(), cmd_gen_tests(), run_test_gen_loop(), build_test_plan_prompt(), build_review_prompt(), build_codegen_prompt(), build_compiler_hints(), build_structural_patterns()
Files: python/registry/bridge.py, python/registry/cli.py, python/registry/test_gen_loop.py, schema/resource_registry.generic.json, python/registry/lang.py
Directories: python/registry/, schema/, templates/pluscal/
