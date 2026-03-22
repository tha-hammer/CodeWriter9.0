# Eliminate `_self_describe()` Implementation Plan

## Overview

Replace the 602-line imperative `_self_describe()` method in `extractor.py` (lines 383-984)
with data-driven JSON files loaded by the same mechanisms external projects use. The self-hosting
DAG becomes: "load resources from registry, load behaviors from a static file, load edges from
a static file" — identical in shape to how any external project populates its DAG.

## Current State Analysis

### What `_self_describe()` Creates (56 nodes, ~80 edges)

| Category | Count | IDs | NodeKind |
|---|---|---|---|
| Requirements | 7 | req-0001..0007 | REQUIREMENT |
| GWT behaviors | 23 | gwt-0001..0023 | BEHAVIOR |
| DAG data structures | 4 | res-0001..0004 | RESOURCE |
| PlusCal templates | 4 | tpl-0001..0004 | SPEC |
| Spec instances | 4 | tpl-0005..0008 | SPEC |
| TLA+ artifact store | 1 | fs-x7p6 | RESOURCE (already in conditional_resources — skip) |
| Plan artifact store | 1 | fs-y3q2 | RESOURCE (already in conditional_resources — skip) |
| Composer modules | 2 | comp-0001..0002 | RESOURCE |
| Loop modules | 3 | loop-0001..0003 | RESOURCE |
| Bridge translators | 4 | bridge-0001..0004 | RESOURCE |
| Feature resources | 4 | impact-0001, depval-0001, subgraph-0001, chgprop-0001 | RESOURCE |

Edge types used exclusively by `_self_describe` (not by schema extractors):
- `DECOMPOSES` — requirement → behaviors
- `MODELS` — templates → schema resources (resolved via `_resolve_type()` at runtime)
- `VERIFIES` — spec instances → GWT behaviors
- `IMPLEMENTS` — resources/specs → specs/behaviors
- `COMPOSES` — composer → templates

Plus `REFERENCES` and `DEPENDS_ON` (shared with schema extractors).

### How `_load_resources()` Works Today

Reads `resource_registry.generic.json`, creates all entries as `NodeKind.RESOURCE`, builds
`_type_map` and `_path_map` for edge resolution. Does NOT support a `kind` field — always
hardcodes `NodeKind.RESOURCE`.

### Key Files

- `python/registry/extractor.py:383-984` — the 602 lines to eliminate
- `python/registry/extractor.py:80-116` — `_load_resources()` node loader
- `python/registry/extractor.py:51-75` — `extract()` orchestrator
- `schema/resource_registry.generic.json` — 35 active + 6 conditional resources
- `python/registry/types.py` — Node, Edge, EdgeType, NodeKind definitions
- `python/registry/dag.py:366-381` — `register_requirement()`
- `python/registry/dag.py:325-364` — `register_gwt()`

### Tests That Assert Self-Hosting DAG Shape

| File | Test | What It Checks |
|---|---|---|
| `test_extractor.py:24` | `test_loads_all_resources` | `>= 45` resource nodes |
| `test_extractor.py:31` | `test_self_description_nodes_exist` | req-0001, gwt-0001..0004, res-0001..0004 present |
| `test_extractor.py:43` | `test_self_description_edges` | exactly 4 DECOMPOSES from req-0001 |
| `test_extractor.py:187` | `test_save_and_reload` | node/edge/component counts round-trip |
| `test_one_shot_loop.py:437` | `test_dag_totals` | **exactly 96 nodes, 198 edges** |

## Desired End State

1. `_self_describe()` deleted entirely (602 lines removed)
2. `self_host` flag on `SchemaExtractor.__init__` means "also load `schema/self_hosting.json`"
3. Two new JSON files under `schema/`:
   - Resources added to `resource_registry.generic.json` (with optional `kind` field)
   - `self_hosting.json` — requirements, behaviors, edges, test_artifacts
4. DAG output is **identical** (same 96 nodes, 198 edges, same IDs, same edge types)
5. All existing tests pass without changes to assertions

### Verification

```bash
# Before: extract with old _self_describe, save as reference
cd python && python3 -c "
from registry.extractor import SchemaExtractor
dag = SchemaExtractor('$PWD/../schema', self_host=True).extract()
import json; open('/tmp/dag_before.json','w').write(json.dumps(dag.to_dict(), sort_keys=True, indent=2))
"

# After: extract with new loader, compare
cd python && python3 -c "
from registry.extractor import SchemaExtractor
dag = SchemaExtractor('$PWD/../schema', self_host=True).extract()
import json; open('/tmp/dag_after.json','w').write(json.dumps(dag.to_dict(), sort_keys=True, indent=2))
"

diff /tmp/dag_before.json /tmp/dag_after.json  # Must be empty
python3 -m pytest tests/ -x                     # All tests pass
```

## What We're NOT Doing

| Out of Scope | What We ARE Doing Instead |
|---|---|
| Changing the DAG output | Producing identical output via different mechanism |
| Changing node IDs or edge types | Preserving all IDs exactly |
| Adding new self-hosting nodes | Only migrating existing ones |
| Modifying the 4 schema extractors | Only adding a new loader for self-hosting data |
| Changing `cw9 register` behavior | Self-hosting uses its own loader, not register |
| Modifying `dag.py` API | Using existing `add_node()` and `add_edge()` |
| Removing the `self_host` flag | Repurposing it to load the new JSON file |

---

## Phase 1: Extend `resource_registry.generic.json`

### Overview

Add the 25 CW9-internal nodes (17 RESOURCE + 8 SPEC) that are currently hardcoded in
`_self_describe()`. Add an optional `kind` field to the registry format. Update
`_load_resources()` to read it.

Note: `fs-x7p6` (tla_artifact_store) and `fs-y3q2` (plan_artifact_store) are already
in `conditional_resources` — skip both. That's 25 new entries, not 27.

### Changes Required

#### 1. Add `kind` field support to `_load_resources()`

**File**: `python/registry/extractor.py`
**Lines**: 80-116

Current code always creates `NodeKind.RESOURCE`. Add support for an optional `"kind"` field
that maps to `NodeKind` enum values, defaulting to `"resource"`.

```python
# In _load_resources(), change line ~88-97 from:
#   node = Node(id=uid, kind=NodeKind.RESOURCE, name=..., ...)
# to:
kind_str = res.get("kind", "resource")
kind = NodeKind(kind_str)
node = Node(id=uid, kind=kind, name=..., ...)
```

Only the `Node(...)` constructor call changes. Everything else (type_map, path_map
population) stays the same.

#### 2. Add 21 entries to `resource_registry.generic.json`

**File**: `schema/resource_registry.generic.json`

Add a new `"cw9_internal"` section after `"conditional_resources"` (or add entries directly
to `"resources"`). Each entry follows the existing format with the new optional `kind` field.

New entries (grouped by phase):

**Phase 0 — DAG data structures:**
```json
"res-0001": {
  "kind": "resource",
  "schema": "configuration",
  "name": "nodes",
  "description": "Map<UUID, ResourceEntry> — the node map of the registry DAG",
  "path": "cw9/registry/dag/nodes",
  "source_schema": "self_hosting",
  "source_key": "dag.nodes"
},
"res-0002": { "kind": "resource", "schema": "configuration", "name": "edges", ... },
"res-0003": { "kind": "resource", "schema": "configuration", "name": "closure", ... },
"res-0004": { "kind": "resource", "schema": "configuration", "name": "components", ... }
```

**Phase 1 — Templates (SPEC kind):**
```json
"tpl-0001": {
  "kind": "spec",
  "schema": "filesystem",
  "name": "crud_template",
  "description": "CRUD PlusCal template — set-based state, create/read/update/delete actions, structural invariants",
  "path": "templates/pluscal/crud.tla",
  "source_schema": "self_hosting",
  "source_key": "templates.crud"
},
"tpl-0002": { "kind": "spec", ... "state_machine_template" ... },
"tpl-0003": { "kind": "spec", ... "queue_pipeline_template" ... },
"tpl-0004": { "kind": "spec", ... "auth_session_template" ... },
"tpl-0005": { "kind": "spec", ... "registry_crud_spec" ... },
"tpl-0006": { "kind": "spec", ... "composition_engine_spec" ... },
"tpl-0007": { "kind": "spec", ... "one_shot_loop_spec" ... },
"tpl-0008": { "kind": "spec", ... "bridge_translator_spec" ... }
```

**Phase 2-4 — Implementation resources:**
```json
"comp-0001": { "schema": "configuration", "name": "composer", "path": "python/registry/composer.py", ... },
"comp-0002": { "schema": "configuration", "name": "spec_cache", "path": "python/registry/composer.py", ... },
"loop-0001": { "schema": "configuration", "name": "one_shot_loop", "path": "python/registry/one_shot_loop.py", ... },
"loop-0002": { "schema": "configuration", "name": "counterexample_translator", "path": "python/registry/one_shot_loop.py", ... },
"loop-0003": { "schema": "configuration", "name": "pass_retry_fail_router", "path": "python/registry/one_shot_loop.py", ... },
"bridge-0001": { "schema": "configuration", "name": "state_var_translator", "path": "python/registry/bridge.py", ... },
"bridge-0002": { "schema": "configuration", "name": "action_translator", "path": "python/registry/bridge.py", ... },
"bridge-0003": { "schema": "configuration", "name": "invariant_translator", "path": "python/registry/bridge.py", ... },
"bridge-0004": { "schema": "configuration", "name": "trace_translator", "path": "python/registry/bridge.py", ... }
```

**Phase 5-8 — Feature resources:**
```json
"impact-0001": { "schema": "configuration", "name": "impact_analysis", "path": "python/registry/dag.py", ... },
"depval-0001": { "schema": "configuration", "name": "dependency_validation", "path": "python/registry/dag.py", ... },
"subgraph-0001": { "schema": "configuration", "name": "subgraph_extraction", "path": "python/registry/dag.py", ... },
"chgprop-0001": { "schema": "configuration", "name": "change_propagation", "path": "python/registry/dag.py", ... }
```

All 25 entries use `source_schema: "self_hosting"` to distinguish them from schema-derived resources.

#### 3. Update `_load_resources()` to handle both sections

Currently iterates `resources` and `conditional_resources`. If we add a `"cw9_internal"` section,
add it to the iteration list. OR just add entries directly into `"resources"` — simpler, no code
change needed for section handling.

**Decision**: Add entries directly to `"resources"`. The `_load_resources` code already handles
any entry in that section. Only the `kind` field support needs a code change.

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest python/tests/test_extractor.py::TestExtraction::test_loads_all_resources` passes
- [ ] All 25 new node IDs appear in `dag.nodes` after `_load_resources()`
- [ ] SPEC-kind nodes have `kind=NodeKind.SPEC` (not RESOURCE)
- [ ] Existing 41 resources still load correctly (backward compatibility)

---

## Phase 2: Create `schema/self_hosting.json`

### Overview

Create a single static JSON file containing the 7 requirements, 23 GWT behaviors,
all ~80 semantic edges, and the test_artifacts mapping. This is the behavioral layer
that sits on top of the resource nodes loaded from the registry.

### File Structure

**File**: `schema/self_hosting.json`

```json
{
  "$schema": "self_hosting/v1",
  "description": "Self-hosting behavioral layer: requirements, GWTs, edges, and test artifacts for CW9's own DAG",

  "requirements": [
    {
      "id": "req-0001",
      "text": "System needs a dependency-tracking DAG over existing resource registry",
      "name": "dag_requirement"
    },
    {
      "id": "req-0002",
      "text": "System needs a one-shot loop that queries registry context, prompts LLM, extracts PlusCal, compiles, composes, verifies with TLC, and routes pass/retry/fail"
    },
    ...all 7 requirements...
  ],

  "behaviors": [
    {
      "id": "gwt-0001",
      "name": "closure_update",
      "given": "a new resource is registered",
      "when": "the resource is added to the DAG",
      "then": "transitive closure updates to include all reachable resources"
    },
    ...all 23 behaviors...
  ],

  "edges": [
    {"from": "req-0001", "to": "gwt-0001", "type": "decomposes"},
    {"from": "req-0001", "to": "gwt-0002", "type": "decomposes"},
    {"from": "req-0001", "to": "gwt-0003", "type": "decomposes"},
    {"from": "req-0001", "to": "gwt-0004", "type": "decomposes"},
    {"from": "gwt-0001", "to": "res-0001", "type": "references"},
    {"from": "gwt-0001", "to": "res-0002", "type": "references"},
    ...all ~80 edges...
  ],

  "test_artifacts": {
    "impact-0001": "tests/generated/test_impact_analysis.py",
    "depval-0001": "tests/generated/test_dep_validation.py",
    "subgraph-0001": "tests/generated/test_subgraph_extraction.py",
    "chgprop-0001": "tests/generated/test_change_propagation.py"
  }
}
```

### MODELS Edges — UUID Resolution

The MODELS edges currently use `_resolve_type()` at runtime:
```python
self._add_edge_safe(dag, "tpl-0001", self._resolve_type("backend_schema.json", "data_structures") or "", EdgeType.MODELS)
```

In the static file, we hardcode the resolved UUIDs. These are stable by design:

| Template | Schema Target | Resolved UUID |
|---|---|---|
| tpl-0001 | backend/data_structures | db-f8n5 |
| tpl-0001 | backend/data_access_objects | db-d3w8 |
| tpl-0002 | middleware/execution_patterns | (resolve at extraction time) |
| tpl-0003 | backend/process_chains | (resolve) |
| tpl-0003 | middleware/process_chains | (resolve) |
| tpl-0004 | shared/security | (resolve) |
| tpl-0004 | frontend/access_controls | (resolve) |

**Decision**: For MODELS edges, use a `{"resolve": ["schema_file", "section"]}` syntax
instead of hardcoded UUIDs. The loader calls `_resolve_type()` at load time, keeping the
indirection that makes UUIDs replaceable:

```json
{"from": "tpl-0001", "to": {"resolve": ["backend_schema.json", "data_structures"]}, "type": "models"},
{"from": "tpl-0001", "to": {"resolve": ["backend_schema.json", "data_access_objects"]}, "type": "models"}
```

This keeps exactly 7 MODELS edges using resolution; all other edges use direct IDs.

### Edge Extraction from `_self_describe()`

Extracting all ~80 edges requires careful line-by-line reading of `_self_describe()`. The
implementation step will read lines 383-984 and transcribe every `_add_edge_safe()` call
into the `edges[]` array. Here is the complete edge inventory by phase:

**Phase 0** (lines 447-468): 16 edges
- 4x DECOMPOSES (req-0001 → gwt-0001..0004)
- 3x REFERENCES (gwt-0001 → res-0001, res-0002, res-0003)
- 2x REFERENCES (gwt-0002 → res-0002, res-0004)
- 4x REFERENCES (gwt-0003 → res-0001..0004)
- 1x REFERENCES (gwt-0004 → res-0002)
- 2 additional (gwt-0001 → res-0003 already counted)

**Phase 1** (lines 508-530): 17 edges
- 7x MODELS (tpl-0001..0004 → schema resources via resolve)
- 1x IMPLEMENTS (tpl-0005 → tpl-0001)
- 4x VERIFIES (tpl-0005 → gwt-0001..0004)
- 5x REFERENCES (tpl-0001..0005 → fs-x7p6)

**Phase 2** (lines 553-565): 9 edges
- 1x IMPLEMENTS (tpl-0006 → tpl-0002)
- 1x REFERENCES (tpl-0006 → fs-x7p6)
- 1x IMPLEMENTS (comp-0001 → tpl-0006)
- 1x REFERENCES (comp-0001 → data_structures via resolve... actually this is a direct call)
- 4x COMPOSES (comp-0001 → tpl-0001..0004)
- 1x DEPENDS_ON (comp-0002 → comp-0001)

**Phase 3** (lines 617-652): 17 edges
- 1x IMPLEMENTS (tpl-0007 → tpl-0002)
- 1x REFERENCES (tpl-0007 → fs-x7p6)
- 3x VERIFIES (tpl-0007 → gwt-0005..0007)
- 1x IMPLEMENTS (loop-0001 → tpl-0007)
- 2x REFERENCES (loop-0001 → res-0001, res-0003)
- 1x DEPENDS_ON (loop-0001 → comp-0001)
- 1x REFERENCES (loop-0001 → comp-0002)
- 2x DEPENDS_ON (loop-0002, loop-0003 → loop-0001)
- 1x REFERENCES (gwt-0005 → res-0003)
- 1x REFERENCES (gwt-0006 → loop-0002)
- 1x REFERENCES (gwt-0007 → loop-0003)
- 3x DECOMPOSES (req-0002 → gwt-0005..0007)

**Phase 4** (lines 688-754): ~32 edges
- 4x DECOMPOSES (req-0003 → gwt-0008..0011)
- 1x IMPLEMENTS (tpl-0008 → tpl-0002)
- 1x REFERENCES (tpl-0008 → fs-x7p6)
- 4x VERIFIES (tpl-0008 → gwt-0008..0011)
- ~6x REFERENCES (gwt-0008..0011 → schema resources + loop)
- 4x IMPLEMENTS (bridge-0001..0004 → gwt-0008..0011)
- 4x DEPENDS_ON (bridge-0001..0004 → loop-0001)
- 4x REFERENCES (bridge-0001..0004 → fs-y3q2)

**Phases 5-8** (lines 784-976): Follow identical patterns per phase:
- 3x DECOMPOSES (req → gwts)
- 3-4x REFERENCES per GWT → core resources
- 3x IMPLEMENTS (resource → gwts)
- 3x DEPENDS_ON (resource → core resources)
- Extra: chgprop-0001 → impact-0001 DEPENDS_ON, gwt-0021..0023 → impact-0001 REFERENCES

### Success Criteria

#### Automated:
- [ ] `schema/self_hosting.json` is valid JSON: `python3 -c "import json; json.load(open('schema/self_hosting.json'))"`
- [ ] Contains exactly 7 requirements, 23 behaviors
- [ ] Edge count matches the current _self_describe edge count

---

## Phase 3: Replace `_self_describe()` with `_load_self_hosting()`

### Overview

Write a new ~50-line method `_load_self_hosting(dag)` that reads `self_hosting.json`
and uses existing DAG APIs to add requirements, behaviors, and edges. Then delete
`_self_describe()`.

### Changes Required

#### 1. New method: `_load_self_hosting()`

**File**: `python/registry/extractor.py`
**Location**: Replace lines 383-984

```python
def _load_self_hosting(self, dag: RegistryDag) -> None:
    """Load self-hosting behavioral layer from static JSON.

    Replaces the former _self_describe() method. Reads schema/self_hosting.json
    which contains requirements, GWT behaviors, edges, and test_artifacts.
    Resource nodes are already loaded from resource_registry.generic.json.
    """
    sh_path = os.path.join(self.schema_dir, "self_hosting.json")
    data = self._load_json(sh_path)

    # Requirements
    for req in data.get("requirements", []):
        dag.add_node(Node.requirement(req["id"], req["text"], req.get("name")))

    # Behaviors (GWT)
    for gwt in data.get("behaviors", []):
        dag.add_node(Node.behavior(
            gwt["id"], gwt["name"],
            gwt["given"], gwt["when"], gwt["then"],
        ))

    # Edges
    for edge in data.get("edges", []):
        from_id = edge["from"]
        to_raw = edge["to"]
        # Support {"resolve": ["schema_file", "section"]} for MODELS edges
        if isinstance(to_raw, dict) and "resolve" in to_raw:
            to_id = self._resolve_type(to_raw["resolve"][0], to_raw["resolve"][1]) or ""
        else:
            to_id = to_raw
        edge_type = EdgeType(edge["type"])
        self._add_edge_safe(dag, from_id, to_id, edge_type)

    # Test artifacts
    dag.test_artifacts = data.get("test_artifacts", {})
```

#### 2. Update `extract()` call site

**File**: `python/registry/extractor.py:72-73`

Change:
```python
if self.self_host:
    self._self_describe(dag)
```
To:
```python
if self.self_host:
    self._load_self_hosting(dag)
```

#### 3. Delete `_self_describe()` (lines 383-984)

Remove the entire 602-line method.

### Success Criteria

#### Automated:
- [ ] `diff /tmp/dag_before.json /tmp/dag_after.json` is empty (identical DAG output)
- [ ] `python3 -m pytest python/tests/ -x` — all tests pass
- [ ] `grep -c "_self_describe" python/registry/extractor.py` returns 0

---

## Phase 4: Verify and Update Tests

### Overview

Run the full test suite. If the DAG is truly identical, no test changes should be needed.
Verify edge cases.

### Verification Steps

1. **Snapshot comparison**: Extract DAG before and after, diff JSON output
2. **Full test suite**: `cd python && python3 -m pytest tests/ -x -v`
3. **Specific tests to watch**:
   - `test_extractor.py::TestExtraction::test_self_description_nodes_exist` — still finds req-0001, gwt-0001..0004, res-0001..0004
   - `test_extractor.py::TestExtraction::test_self_description_edges` — still finds 4 DECOMPOSES from req-0001
   - `test_one_shot_loop.py::TestSelfRegistration::test_dag_totals` — still 96 nodes, 198 edges
   - `test_extractor.py::TestExtractedDagSerialization::test_save_and_reload` — round-trip still works

### Potential Issues

1. **Node ordering**: `_self_describe` adds nodes in a specific order. The new loader adds
   resources first (from registry), then requirements and behaviors (from self_hosting.json).
   Since DAG uses a dict, insertion order doesn't affect correctness, but `to_dict()` sorts
   by key, so JSON output should be identical.

2. **fs-x7p6 / fs-y3q2 duplication**: Both are already in `conditional_resources` in the
   registry. `_load_resources()` already loads them as nodes. The self_hosting edges that
   reference them will just work. If descriptions differ between registry and what
   `_self_describe` used, the registry version is source of truth.
   **Action**: Verify descriptions in `conditional_resources` are adequate. Do NOT add
   fs-x7p6 or fs-y3q2 to the new resource entries — they're already loaded.

3. **SPEC kind on tpl-0006**: In `_self_describe`, `tpl-0006` is created via `Node.resource()`
   (RESOURCE kind), not `Node(kind=NodeKind.SPEC)`. The registry entry should match — use
   `"kind": "resource"` for tpl-0006, not `"spec"`. Actually, looking more carefully at the
   code, tpl-0005 through tpl-0008 are created inconsistently:
   - tpl-0005: `Node(kind=NodeKind.SPEC, ...)` — SPEC
   - tpl-0006: `Node.resource(...)` — RESOURCE
   - tpl-0007: `Node(kind=NodeKind.SPEC, ...)` — SPEC
   - tpl-0008: `Node(kind=NodeKind.SPEC, ...)` — SPEC
   The registry entries must match these exact kinds to preserve DAG identity.

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest python/tests/ -x` — 0 failures
- [ ] DAG JSON diff is empty

---

## Phase 5: Clean Up

### Overview

Remove dead code, update documentation.

### Changes

1. **Delete `_self_describe` method** (already done in Phase 3)
2. **Update BOOTSTRAP.md**: Change the "Phase 0 Implementation" section to note that
   self-description now uses `schema/self_hosting.json` instead of `_self_describe()`
3. **Update any comments** in extractor.py that reference `_self_describe`
4. **Verify `cw9 extract`** still works end-to-end:
   ```bash
   cd /home/maceo/Dev/CodeWriter9.0 && cw9 extract
   ```

### Success Criteria

#### Automated:
- [ ] `grep -r "_self_describe" python/` returns no hits
- [ ] `cw9 extract` completes successfully
- [ ] `python3 -m pytest python/tests/ -x` still passes

---

## Implementation Order

```
Phase 1: Extend resource_registry.generic.json
    |
    v
Phase 2: Create schema/self_hosting.json (can be done in parallel with Phase 1)
    |
    v
Phase 3: Replace _self_describe() with _load_self_hosting()
    |
    v
Phase 4: Verify DAG identity + run tests
    |
    v
Phase 5: Clean up docs and dead code
```

Phases 1 and 2 are independent and can be done in parallel. Phase 3 depends on both.
Phase 4 is verification. Phase 5 is cleanup.

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Edge count mismatch | Snapshot DAG before/after, diff JSON |
| Node kind mismatch (SPEC vs RESOURCE) | Carefully match each node's kind from _self_describe source |
| MODELS edge resolution failure | Use `{"resolve": [...]}` syntax, same _resolve_type logic |
| fs-x7p6 description drift | Compare registry vs _self_describe, use registry as source of truth |
| Test breakage from ordering | DAG serialization sorts by key, so order-independent |

## References

- Beads issue: cosmic-hr-myni
- `_self_describe()`: `python/registry/extractor.py:383-984`
- Resource registry: `schema/resource_registry.generic.json`
- Node/Edge types: `python/registry/types.py`
- DAG engine: `python/registry/dag.py`
