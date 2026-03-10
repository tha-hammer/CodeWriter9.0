---
date: 2026-03-10T17:24:16-04:00
researcher: claude-opus
git_commit: 458acdf4f879057f8e3b7f0f0618e8a9ed508ccd
branch: master
repository: CodeWriter9.0
topic: "How-to: CW9 Library API"
tags: [documentation, howto, api, registry-dag, library]
status: complete
last_updated: 2026-03-10
last_updated_by: claude-opus
type: howto
---

# How to Use the CW9 Library API

## Introduction

This guide covers using the CW9 Python library API to programmatically manage GWT behaviors, query the registry DAG, and integrate with the verification pipeline. The library API is the primary interface for upstream systems (Rust crates, scripts, database-backed pipelines) that feed GWTs into CW9.

## Prerequisites

- Python 3.11+
- `python/registry/` package on your Python path
- An initialized CW9 project (`.cw9/` directory with `dag.json`)

## Loading a Project Context

`ProjectContext` resolves all paths for a CW9 project. Three construction patterns:

### For an external project

```python
from registry.context import ProjectContext

# Auto-detects engine_root from .cw9/config.toml or __file__ location
ctx = ProjectContext.from_target("/path/to/your/project")

# Or explicitly specify engine_root
ctx = ProjectContext.from_target("/path/to/your/project", engine_root="/path/to/CodeWriter9.0")
```

### For CW9 self-hosting

```python
ctx = ProjectContext.self_hosting("/path/to/CodeWriter9.0")
```

### Accessing paths

```python
ctx.engine_root      # CodeWriter9's own code
ctx.target_root      # external project's source
ctx.state_root       # .cw9/ directory

ctx.schema_dir       # .cw9/schema/
ctx.spec_dir         # .cw9/specs/
ctx.artifact_dir     # .cw9/bridge/
ctx.session_dir      # .cw9/sessions/
ctx.test_output_dir  # tests/generated/

ctx.template_dir     # engine templates (PlusCal)
ctx.tools_dir        # engine tools (tla2tools.jar)
ctx.python_dir       # engine Python code
```

`ProjectContext` is a frozen dataclass — paths are immutable after construction.

## Loading and Saving the DAG

```python
from registry.dag import RegistryDag

dag = RegistryDag.load(ctx.state_root / "dag.json")

# ... modify dag ...

dag.save(ctx.state_root / "dag.json")
```

`save()` writes JSON with `nodes` (dict), `edges` (list), and `test_artifacts` (dict). `load()` reconstructs the full `RegistryDag` including closure sets.

## Registering Requirements

```python
req_id = dag.register_requirement("System must handle user authentication")
# req_id == "req-0008" (auto-allocated, continues from existing IDs)
```

With an explicit short name:

```python
req_id = dag.register_requirement(
    "System must handle user authentication",
    name="user_auth",
)
```

ID allocation scans existing `req-NNNN` nodes and increments from the maximum.

## Registering GWT Behaviors

```python
gwt_id = dag.register_gwt(
    given="a registered user exists",
    when="they submit login credentials",
    then="they receive an authenticated session token",
    parent_req="req-0008",  # optional — wires a DECOMPOSES edge
)
# gwt_id == "gwt-0024"
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `given` | `str` | yes | The "Given" precondition |
| `when` | `str` | yes | The "When" action/event |
| `then` | `str` | yes | The "Then" expected outcome |
| `parent_req` | `str \| None` | no | Requirement ID to wire DECOMPOSES edge |
| `name` | `str \| None` | no | Short name (auto-generated from `when` if omitted) |

### Behavior

- Allocates the next `gwt-NNNN` ID by scanning existing nodes
- Creates a `BEHAVIOR` node with `given`, `when`, `then` fields
- If `parent_req` is provided, validates it exists and wires a `DECOMPOSES` edge
- Raises `NodeNotFoundError` if `parent_req` doesn't exist in the DAG

### Registering multiple GWTs under one requirement

```python
req_id = dag.register_requirement("Form validation")

dag.register_gwt("valid data submitted", "validation runs", "form is accepted", parent_req=req_id)
dag.register_gwt("invalid email", "validation runs", "email error shown", parent_req=req_id)
dag.register_gwt("missing required field", "validation runs", "field error shown", parent_req=req_id)

dag.save(ctx.state_root / "dag.json")
```

## Querying Impact Analysis

Find all nodes affected by a change to a given node:

```python
result = dag.query_impact("cfg-f7s8")

result.target          # "cfg-f7s8" — the changed node
result.affected        # set of node IDs transitively affected
result.direct_dependents  # set of immediate dependents only
```

`query_impact()` uses the DAG's closure (precomputed reachability) to find all nodes that transitively depend on the target.

## Extracting Subgraphs

Get the minimal subgraph containing a node and its neighborhood:

```python
result = dag.extract_subgraph("db-b7r2")

result.nodes  # set of node IDs in the subgraph
result.edges  # list of edges within the subgraph
```

The subgraph includes ancestors (dependencies) and descendants (dependents) of the focal node, with no dangling edges.

## Querying Affected Tests

Find test files affected by a node change:

```python
# First, populate test_artifacts mapping
dag.test_artifacts["gwt-0021"] = "tests/generated/test_gwt_0021.py"
dag.test_artifacts["gwt-0022"] = "tests/generated/test_gwt_0022.py"

affected_files = dag.query_affected_tests("cfg-f7s8")
# ["tests/generated/test_gwt_0021.py", "tests/generated/test_gwt_0022.py"]
```

`test_artifacts` maps GWT node IDs to test file paths. `query_affected_tests()` traces the impact of a change through the DAG and returns the test files associated with affected GWT nodes.

## Validating Edges Before Adding

Check whether an edge would create a cycle or violate kind constraints:

```python
from registry.types import Edge, EdgeType

edge = Edge("node-a", "node-b", EdgeType.IMPORTS)
result = dag.validate_edge(edge)

result.valid       # True if the edge is safe to add
result.reason      # explanation string if invalid
```

`validate_edge()` checks for:
- Cycle creation (would the edge introduce a loop?)
- Kind incompatibility (certain node kinds cannot be connected)

## Extracting a DAG from Schemas

Build a fresh DAG from schema files:

```python
from registry.extractor import SchemaExtractor

extractor = SchemaExtractor(schema_dir=str(ctx.schema_dir))
dag = extractor.extract()

dag.node_count  # number of nodes
dag.edge_count  # number of edges
```

### Preserving registered GWTs across re-extraction

`extract()` builds a fresh DAG from schemas, which overwrites any manually registered GWTs. Use `merge_registered_nodes()` to preserve them:

```python
old_dag = RegistryDag.load(dag_path)
new_dag = SchemaExtractor(schema_dir=str(ctx.schema_dir)).extract()

merged_count = new_dag.merge_registered_nodes(old_dag)
# Nodes with gwt- or req- prefixes from old_dag are preserved

new_dag.save(dag_path)
```

This is what `cw9 extract` does internally.

## Running the Bridge

Translate a verified TLA+ spec into structured Python-domain data:

```python
from registry.bridge import run_bridge

tla_text = (ctx.spec_dir / "gwt-0024.tla").read_text()
result = run_bridge(tla_text)

result.module_name       # e.g., "form_validation"
result.data_structures   # state variables with types and defaults
result.operations        # TLA+ actions as function descriptors
result.verifiers         # invariants with conditions and applies_to
result.assertions        # invariants in assertion format
result.test_scenarios    # state traces (from counterexample traces)
```

To include counterexample traces:

```python
from registry.bridge import run_bridge, TlcTrace

traces = [TlcTrace(invariant_violated="NoFalsePositives", states=[...])]
result = run_bridge(tla_text, traces=traces)
# result.test_scenarios is now populated
```

## Working with Simulation Traces

Load TLC simulation traces (generated by `cw9 loop` with `-simulate`):

```python
from registry.traces import load_simulation_traces, format_traces_for_prompt

traces = load_simulation_traces(ctx.spec_dir / "gwt-0024_sim_traces.json")

# Each trace has:
for trace in traces:
    trace.init_state    # first state dict
    trace.final_state   # last state dict
    trace.actions       # list of action labels
    trace.states        # full state sequence

# Format for LLM prompts:
prompt_text = format_traces_for_prompt(traces)
```

## Building Context for the LLM Loop

Query the DAG for context around a GWT behavior:

```python
from registry.one_shot_loop import query_context, format_prompt_context

bundle = query_context(dag, "gwt-0024")
prompt_text = format_prompt_context(bundle)
```

`query_context()` gathers the GWT node, its parent requirement, sibling behaviors, connected resources, and schema context. `format_prompt_context()` renders this into a text block suitable for an LLM prompt.

## Error Handling

```python
from registry.dag import NodeNotFoundError

try:
    dag.register_gwt("g", "w", "t", parent_req="req-9999")
except NodeNotFoundError as e:
    print(f"Missing node: {e.node_id}")  # "req-9999"
```

`NodeNotFoundError` is raised when referencing a node ID that doesn't exist in the DAG (e.g., invalid `parent_req` in `register_gwt()`, or invalid `node_id` in `query_impact()`).

## Next Steps

- For the CLI pipeline commands, see [How to Run the CW9 Pipeline](howto-cw9-cli-pipeline.md).
- For schema format details, consult the Schema Reference.
- For TLA+ spec format and PlusCal templates, consult the Templates Reference.
