# BOOTSTRAP: CW9 Verified Code Generation Pipeline

## Architecture

CW9 is a registry-driven pipeline for verified code generation using TLA+/PlusCal formal methods. Every component earns the right to exist by being formally specified and verified before implementation.

```
  Requirement → GWT behaviors → TLA+ spec (LLM + TLC) → Bridge artifacts → Generated tests → Implementation
```

The system is **self-hosting**: it used this pipeline to build itself (Phases 0-8), then retroactively verified all components through the same pipeline (Batches 1-3).

## Pipeline Components

| Component | Module | Purpose |
|---|---|---|
| Registry DAG | `dag.py` | Dependency graph: nodes, edges, closure, components |
| PlusCal Templates | `templates/pluscal/*.tla` | 4 base templates: CRUD, state machine, queue, auth |
| Composition Engine | `composer.py` | Composes TLA+ specs across connected components |
| One-Shot Loop | `one_shot_loop.py` | LLM → PlusCal → compile → TLC verify → route |
| Bridge | `bridge.py` | Spec → data structures, operations, verifiers, test scenarios |
| Test Gen | `test_gen_loop.py` | Bridge artifacts + sim traces → runnable test files |
| Language Profiles | `lang.py`, `lang_*.py` | Python/TS/Go/Rust target compilation |
| Crawl Pipeline | `crawl_*.py`, `scanner_*.py` | Brownfield codebase analysis (IN:DO:OUT cards) |

## Verification Status

**63 GWTs verified, 2857 generated tests, 0 remaining debt.**

| Scope | GWT IDs | Tests | Date |
|---|---|---|---|
| Phases 0-8 (core pipeline) | gwt-0001..0023 | 250 | 2026-03-09 |
| Batch 1: CrawlStore, Orchestrator, CLI | gwt-0024..0035 | 690 | 2026-03-21 |
| Batch 2: Context, LLM, CW7/Crawl Bridge | gwt-0036..0045 | 722 | 2026-03-21 |
| Batch 3: Scanners, Language Profiles | gwt-0046..0063 | 1195 | 2026-03-22 |
| Crawl DAG GWTs | gwt-0001..0031 (crawl) | — | Covered by above |

## The Pipeline (mandatory for new features)

```bash
# 1. Register the behavior
echo '{"requirements": [...], "gwts": [...]}' | cw9 register

# 2. Write context file (MUST include Test Interface section)
vim .cw9/context/<gwt-id>.md

# 3. Run the verification loop
cw9 loop <gwt-id> --context-file .cw9/context/<gwt-id>.md

# 4. Extract bridge artifacts from verified spec
cw9 bridge .cw9/specs/<gwt-id>.tla --gwt <gwt-id>

# 5. Generate tests from bridge artifacts
cw9 gen-tests <gwt-id> --lang python

# 6. Implement to pass the generated tests
# Code comes LAST — tests define the contract
```

## Context File Template (mandatory)

Context files without a Test Interface section cause ~60% test-gen failure rate. With them: <5%.

```markdown
# Context for <gwt-id>: <behavior_name>

## Behavior
Given ..., when ..., then ...

## Concrete Data Shapes
<Full dataclass definitions with field types>

## Key Invariants to Model
- InvariantName: description

## Test Interface (MANDATORY)
\```python
from registry.module_name import function_name
result = function_name(arg)
assert result.field_name == value
\```

## Anti-Patterns (DO NOT USE)
- `obj["field"]` -- WRONG if obj is a dataclass
- `obj.tla_model_field` -- WRONG (use real API field name)
```

## GWT ID Namespaces

Two DAG contexts with independent ID spaces. **IDs collide between contexts.**

**Self-hosting DAG** (`.cw9/dag.json`): gwt-0001..0063 allocated. Next available: gwt-0064+

**Crawl DAG** (`dag.json` at repo root): gwt-0001..0031. Next available: gwt-0032+

## Ground Rules

1. **Code comes LAST.** GWT → spec → verify → bridge → tests → implement.
2. **Conform-or-die.** New code must satisfy existing verified specs. If it can't, the code is wrong, not the spec.
3. **Monotonic growth.** Nodes are never deleted, only superseded.
4. **LLM writes PlusCal only.** The system composes TLA+. Never hand-write TLA+ specs.
5. **Bridge is mechanical.** No LLM involved in translation.
6. **Tests are generated.** Hand-written tests only for pipeline infrastructure itself.
7. **Context files must include Test Interface.** Without it, gen-tests hallucinates ~60% of the time.
8. **Max 3-4 concurrent `cw9 loop` processes.** More exhausts /tmp and causes silent Java failures.
9. **DAG is not safe for concurrent writes.** Only one `cw9 register` at a time.

## Operational Lessons

- **Scaffolding fixes OK, spec-weakening NOT OK.** Test-gen hallucinations (wrong imports, field names) are scaffolding bugs — fix the test. Assertions from the spec are behavioral contracts — fix the code.
- **Partition parallel work by file, never by strategy.** Two LLMs touching the same file guarantees collision.
- **Commit before handoff.** Fixes only in a context window can be destroyed.

## Full History

See `docs/bootstrap_history.md` for the complete phase-by-phase narrative, schema extraction maps, TLC state counts, and self-registration details.
