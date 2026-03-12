---
date: 2026-03-11T12:00:00-05:00
researcher: DustyForge
git_commit: 35a5a57ae1d910be081083b3a2120a7e9e397474
branch: master
repository: CodeWriter9.0
topic: "Init pipeline pollution: CW9 self-referencing schemas shipped as starter templates"
tags: [research, codebase, init, extract, self-hosting, bootstrapping, bug]
status: complete
last_updated: 2026-03-11
last_updated_by: DustyForge
related_issue: CodeWriter9.0-7oz
---

```
┌──────────────────────────────────────────────────────────────────────┐
│  RESEARCH: Init Pipeline Self-Referencing Schema Pollution           │
│  Status: ✅ Complete  │  Date: 2026-03-11  │  Issue: CW9-7oz        │
└──────────────────────────────────────────────────────────────────────┘
```

# Research: Init Pipeline Self-Referencing Schema Pollution

**Date**: 2026-03-11
**Researcher**: DustyForge
**Git Commit**: `35a5a57`
**Branch**: `master`
**Repository**: CodeWriter9.0

## 📋 Research Question

CW9's `cw9 init` command ships starter templates that describe CW9 itself rather than providing empty/minimal stubs for new projects. The `cw9 extract` command then parses these self-referencing schemas into 96 nodes (7 requirements + 23 GWTs) describing CW9's own architecture. Where exactly is the pollution, how does it flow, and what are its boundaries?

## 📊 Summary

The pollution has **two independent sources** that combine during `cw9 extract`:

| Source | Location | Pollution Type | Node Count |
|--------|----------|----------------|------------|
| Template schemas | `templates/schema/*.json` + `resource_registry.generic.json` | 41 resource nodes extracted from CW9's own schema patterns | ~41 |
| `_self_describe()` | `python/registry/extractor.py:414-998` | 7 reqs + 23 GWTs + ~25 resource/spec nodes hardcoded about CW9 internals | ~55 |
| **Total** | | | **~96** |

Both sources are baked into the extraction pipeline — **every** `cw9 extract` on **any** project produces these CW9 self-hosting nodes.

## 🔍 Detailed Findings

### Source 1: Template Schema Files (the "baseline" pollution)

**Files** (copied during `cw9 init`):
- `templates/schema/backend_schema.json` — Generic but structured as CW9's own backend shape
- `templates/schema/frontend_schema.json` — CW9's frontend schema structure
- `templates/schema/middleware_schema.json` — CW9's middleware schema structure
- `templates/schema/shared_objects_schema.json` — CW9's shared objects structure
- `templates/schema/resource_registry.generic.json` — **35 resources + 6 conditional resources** with CW9-specific UUIDs

**How init copies them** (`cli.py:101-105`):
```python
schema_templates_dir = get_template_dir("schema")
if schema_templates_dir.is_dir() and not list((state_root / "schema").glob("*.json")):
    for tmpl in schema_templates_dir.glob("*.json"):
        shutil.copy2(tmpl, state_root / "schema" / tmpl.name)
```

The resource registry file contains 41 entries with stable UUIDs like `db-f8n5` (data_structure), `mq-t2f7` (execution_patterns), `cfg-t5h9` (security), etc. These are generic *category* names (not CW9-specific module names), but the **UUIDs are hardcoded** and the extraction pipeline treats them as real project resources.

**Impact**: When `cw9 extract` loads these schemas, `_load_resources()` (extractor.py:170-179) creates DAG nodes for all 41 resources, and `_extract_schema_edges()` creates edges between them based on the schema structure.

### Source 2: `_self_describe()` Method (the "7+23" pollution)

**Location**: `python/registry/extractor.py:414-998` (~584 lines of hardcoded self-hosting nodes)

This method is called unconditionally at `extractor.py:163`:
```python
def extract(self) -> RegistryDag:
    dag = RegistryDag()
    self._load_resources(dag, registry)        # Step 1: schema resources
    self._extract_schema_edges(dag, ...)       # Step 2: schema edges
    self._self_describe(dag)                    # Step 3: ALWAYS runs ← problem
    return dag
```

**Self-describing nodes registered by phase:**

| Phase | Requirement | GWTs | Other Nodes | Description |
|-------|-------------|------|-------------|-------------|
| 0: DAG bootstrap | req-0001 | gwt-0001..0004 | res-0001..0004 | CW9's dependency-tracking DAG |
| 1: PlusCal templates | — | — | tpl-0001..0006, fs-x7p6 | CW9's TLA+ template library |
| 2: Composition engine | — | — | tpl-0006, comp-0001..0002 | CW9's spec composition engine |
| 3: One-shot loop | req-0002 | gwt-0005..0007 | tpl-0007, loop-0001..0003 | CW9's LLM verification loop |
| 4: Bridge | req-0003 | gwt-0008..0011 | tpl-0008, bridge-0001..0004 | CW9's spec-to-code translators |
| 5: Impact analysis | req-0004 | gwt-0012..0014 | impact-0001 | CW9's reverse dep query |
| 6: Dep validation | req-0005 | gwt-0015..0017 | depval-0001 | CW9's edge validation pre-check |
| 7: Subgraph extraction | req-0006 | gwt-0018..0020 | subgraph-0001 | CW9's subgraph extraction |
| 8: Change propagation | req-0007 | gwt-0021..0023 | chgprop-0001 | CW9's test impact analysis |

**Totals from `_self_describe()`**: 7 requirements, 23 GWTs, ~25 resource/spec nodes, ~127 edges

### The Interaction Between Both Sources

The `_self_describe()` method **cross-references** the template schema resource UUIDs. For example:
- `gwt-0008` (state_var_translation) → references `db-f8n5` (data_structures from template registry)
- `tpl-0001` (crud_template) → MODELS `db-f8n5` and `db-d3w8` (from template registry)
- `tpl-0004` (auth_session_template) → MODELS `cfg-t5h9` and `ui-x1r9` (from template registry)

This means **both pollution sources are coupled** — the self-describe nodes have edges pointing to the template resource nodes. Removing one without the other would leave dangling edges.

### Packaged Copy Locations

The template schemas exist in **three locations** that all need updating:

| Location | Purpose |
|----------|---------|
| `templates/schema/` | Source-of-truth (repo layout) |
| `python/registry/_data/templates/schema/` | Packaged into wheel via `importlib.resources` |
| `python/build/lib/registry/_data/templates/schema/` | Build artifact (auto-generated) |

The `_resources.py` module (`get_schema_template_dir()`) bridges init to the packaged data at runtime.

### Test Coverage Implications

Several tests depend on the current self-hosting node counts:

| Test File | What It Checks |
|-----------|----------------|
| `test_external_pipeline.py:250` | Notes CW9 self-hosting has 96 nodes |
| `test_register_gwt.py:18` | Expects next ID after gwt-0023 is gwt-0024 |
| `test_cli.py:19-93` | `TestInit` class — starter schema copy behavior |
| `test_packaging.py:191` | Full `init → extract` integration flow |

## 📁 Code References

- `python/registry/cli.py:56-131` — `cmd_init()`: creates `.cw9/` and copies template schemas
- `python/registry/cli.py:101-105` — The actual `shutil.copy2` loop for starter schemas
- `python/registry/cli.py:170-214` — `cmd_extract()`: calls `SchemaExtractor.extract()`
- `python/registry/extractor.py:142-165` — `extract()`: the 3-step pipeline (load → edges → self-describe)
- `python/registry/extractor.py:414-998` — `_self_describe()`: 584 lines of hardcoded CW9 nodes
- `python/registry/_resources.py` — `get_schema_template_dir()` and `get_data_path()`
- `templates/schema/resource_registry.generic.json` — 41 resource entries with stable UUIDs
- `templates/schema/backend_schema.json` — Template with placeholder names but CW9 structure

## 🏗️ Architecture Documentation

### Flow Diagram

```
cw9 init <target>
    │
    ├── Creates .cw9/{schema,specs,bridge,sessions}/
    ├── Writes config.toml
    ├── Writes empty dag.json (0 nodes, 0 edges)
    └── Copies templates/schema/*.json → .cw9/schema/   ← POLLUTION SOURCE 1
                                                          (41 resource UUIDs)

cw9 extract <target>
    │
    ├── SchemaExtractor(schema_dir=.cw9/schema/)
    │   ├── _load_resources()     → 41 nodes from resource_registry
    │   ├── _extract_schema_edges() → edges from 4 schema files
    │   └── _self_describe()      → 7 reqs + 23 GWTs + ~25 nodes   ← POLLUTION SOURCE 2
    │                               (584 lines, hardcoded, unconditional)
    │
    └── Saves dag.json with ~96 nodes, ~198 edges
        (ALL describing CW9 itself, regardless of target project)
```

### Key Architectural Observations

1. **`_self_describe()` is unconditional** — there is no flag, env var, or config to skip it
2. **Template schemas use placeholder names** (e.g., "ProcessorName", "StructureName") but have **real UUIDs** that are cross-referenced by `_self_describe()`
3. **The coupling is bidirectional**: self-describe nodes reference template UUIDs, and template UUIDs were designed to match CW9's own schema categories
4. **`merge_registered_nodes()`** preserves externally-registered GWTs across re-extracts, meaning CW9 self-hosting nodes persist even if a user adds their own

## 📚 Historical Context (from thoughts/)

- `thoughts/shared/handoffs/general/2026-03-09_15-14-04_phase5-complete-bootstrap-done.md` — Documents when bootstrap was declared "done" and self-hosting was complete
- `thoughts/shared/handoffs/general/2026-03-09_13-31-00_phase4-complete-phase5-self-hosting.md` — Phase where CW9 started self-describing
- `thoughts/shared/docs/registry-driven-pipeline-plan.md` — Original plan for the registry-driven bootstrap approach
- `thoughts/shared/plans/cw9-global-binary-packaging/phase-3-cli-init-fix.md` — Plan for fixing init's schema copying behavior (focused on ENGINE_ROOT path resolution, not content pollution)
- `thoughts/shared/handoffs/general/2026-03-10_07-57-53_stage0-1-projectcontext-cw9-init.md` — Handoff covering init implementation

## 🔗 Related Research

- No prior research documents found in `thoughts/searchable/shared/research/` (this is the first)

## ❓ Open Questions

1. **Should `_self_describe()` be removed entirely, or gated behind a `--self-host` flag?** — It was essential for bootstrapping CW9 itself but has no purpose for external projects
2. **What should the empty stub schemas look like?** — The current templates have the right *shape* (structure is correct for the 4-schema format) but wrong *content* (CW9's own UUIDs and categories). Options:
   - Truly empty schemas (just the top-level keys with empty objects)
   - Minimal example schemas (one example processor, one example data structure) with fresh UUIDs
3. **How to handle `BOOTSTRAP.md` and the persisted `schema/registry_dag.json`?** — These track CW9's self-hosting milestones and DAG growth. They should remain for CW9's own development but not ship to users
4. **Test suite impact** — Several tests assert node counts (96) or specific IDs (gwt-0023). These will need updating alongside the fix
