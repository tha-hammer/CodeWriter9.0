---
date: 2026-03-10T17:24:16-04:00
researcher: claude-opus
git_commit: 458acdf4f879057f8e3b7f0f0618e8a9ed508ccd
branch: master
repository: CodeWriter9.0
topic: "How-to: CW9 CLI Pipeline Commands"
tags: [documentation, howto, cli, pipeline, cw9]
status: complete
last_updated: 2026-03-10
last_updated_by: claude-opus
type: howto
---

# How to Run the CW9 Formal Verification Pipeline on an External Project

## Introduction

This guide walks through using the `cw9` CLI to initialize a project, extract a registry DAG from schemas, run the LLM→PlusCal→TLC verification loop, generate bridge artifacts, produce pytest files, and run tests with smart targeting. Each step produces artifacts that the next step consumes.

## Prerequisites

- Python 3.11+ (required for `tomllib`)
- CodeWriter9 engine installed (the `python/registry/` package)
- TLA+ tools in `<engine_root>/tools/` (tla2tools.jar)
- Claude Agent SDK configured (for `cw9 loop` and `cw9 gen-tests`)
- Project schemas in JSON format (or use the starter templates)

# Install globally (your machine)                                                         
                                                                                          
## Option A: uv (recommended)                                                            
  uv tool install ./python                                                                
                                                                  
## Option B: pipx
  pipx install ./python

## Option C: pip (into current environment)
  pip install ./python

  After any of these, cw9 is on your PATH globally.

  Build for distribution

  cd /home/maceo/Dev/CodeWriter9.0/python
  python -m build

  This produces two files in python/dist/:
  - codewriter_registry-0.1.0.tar.gz (source)
  - codewriter_registry-0.1.0-py3-none-any.whl (wheel)

  Distribute

  From git (no PyPI needed):
  uv tool install git+https://github.com/user/CodeWriter9.0#subdirectory=python

  Via PyPI (public):
  pip install twine
  twine upload dist/*
  # Then anyone can: uv tool install codewriter-registry

  Via private registry or direct wheel:
  pip install codewriter_registry-0.1.0-py3-none-any.whl



## Step 1: Initialize the Project

Create the `.cw9/` directory structure in your project:

```bash
cw9 init /path/to/your/project
```

This creates:

```
your-project/
  .cw9/
    config.toml           # engine_root path
    dag.json              # empty DAG
    schema/               # starter schemas copied from engine templates
      backend_schema.json
      frontend_schema.json
      middleware_schema.json
      shared_objects_schema.json
      resource_registry.generic.json
    specs/                # TLA+ specs (populated by cw9 loop)
    bridge/               # bridge artifacts (populated by cw9 bridge)
    sessions/             # LLM session logs
```

To reinitialize an existing project (preserves user schemas):

```bash
cw9 init /path/to/your/project --force
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `target_dir` | `.` | Project directory to initialize |
| `--force` | off | Reinitialize existing `.cw9/` |

## Step 2: Edit Schemas

Edit the JSON schema files in `.cw9/schema/` to describe your project's architecture. Each schema file maps to a layer:

- `backend_schema.json` — processors, endpoints, data access
- `frontend_schema.json` — UI modules, components
- `middleware_schema.json` — interceptors, middleware
- `shared_objects_schema.json` — data types, utilities, error definitions
- `resource_registry.generic.json` — maps resource UUIDs to schema entries

The `resource_registry.generic.json` is the central index. Each resource has a unique UUID and references its source schema.

## Step 3: Extract the DAG

Build the registry DAG from your schemas:

```bash
cw9 extract /path/to/your/project
```

Output:
```
DAG updated: 42 nodes (+42), 87 edges (+87)
```

On re-extract, registered GWTs and requirements are preserved:

```
DAG updated: 45 nodes (+3), 92 edges (+5)
  (preserved 3 registered node(s) from previous DAG)
```

## Step 4: Register GWT Behaviors

GWT (Given-When-Then) behaviors are registered via the library API, not the CLI. Upstream systems call `RegistryDag.register_gwt()` programmatically:

```python
from registry.dag import RegistryDag
from registry.context import ProjectContext

ctx = ProjectContext.from_target("/path/to/your/project")
dag = RegistryDag.load(ctx.state_root / "dag.json")

gwt_id = dag.register_gwt(
    given="a user submits a registration form",
    when="validation runs on the submitted data",
    then="validation errors are displayed inline",
    parent_req="req-0008",  # optional
)

dag.save(ctx.state_root / "dag.json")
print(f"Registered: {gwt_id}")  # e.g., "gwt-0024"
```

See the [Library API guide](howto-cw9-library-api.md) for details.

## Step 5: Run the Verification Loop

Generate a formally verified PlusCal/TLA+ spec for a GWT behavior:

```bash
cw9 loop gwt-0024 /path/to/your/project
```

The loop:
1. Loads the DAG and finds the GWT node
2. Builds a prompt from GWT text + registry context
3. Calls the LLM to generate PlusCal
4. Compiles PlusCal and runs TLC model checker
5. On PASS: saves the verified spec + runs TLC `-simulate` for traces
6. On FAIL: retries with counterexample feedback (up to `--max-retries`)

Output on success:
```
Attempt 1/5
PASS — verified spec saved: .cw9/specs/gwt-0024.tla
```

### Artifacts produced

| File | Description |
|------|-------------|
| `.cw9/specs/<gwt-id>.tla` | Verified TLA+ spec |
| `.cw9/specs/<gwt-id>.cfg` | TLC configuration |
| `.cw9/specs/<gwt-id>_sim_traces.json` | TLC simulation traces (concrete state sequences) |
| `.cw9/specs/<gwt-id>_traces.json` | Counterexample traces from retry attempts |
| `.cw9/sessions/<gwt-id>_attempt{N}.txt` | Raw LLM responses per attempt |

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `gwt_id` | required | GWT behavior ID (e.g., `gwt-0024`) |
| `target_dir` | `.` | Project directory |
| `--max-retries` | `5` | Maximum TLC verification attempts |

## Step 6: Generate Bridge Artifacts

Translate the verified spec into structured Python-domain data:

```bash
cw9 bridge gwt-0024 /path/to/your/project
```

Output:
```
Bridge artifacts saved: .cw9/bridge/gwt-0024_bridge_artifacts.json
  data_structures: 1
  operations: 12
  verifiers: 5
  assertions: 5
```

The bridge reads the `.tla` spec and produces a JSON file containing:
- **data_structures** — state variables with types, defaults, validation
- **operations** — TLA+ actions mapped to function signatures
- **verifiers** — invariants with conditions and `applies_to` fields
- **assertions** — invariants translated to assertion format
- **test_scenarios** — state traces from TLC counterexamples
- **simulation_traces** — concrete state sequences from TLC `-simulate`

## Step 7: Generate Tests

Produce a pytest file from bridge artifacts using an LLM-in-the-loop:

```bash
cw9 gen-tests gwt-0024 /path/to/your/project
```

The test generation loop runs three LLM passes:
1. **Test plan** — uses TLC simulation traces (primary context) + API signatures + compiler hints to plan fixtures, assertions, and scenarios
2. **Review** — checks the plan against bridge verifiers for correctness
3. **Code generation** — emits the pytest file from the reviewed plan

The generated file is verified mechanically: `compile()` → `pytest --collect-only` → `pytest -x`. On failure, the loop retries with error feedback.

Output:
```
Generated: tests/generated/test_gwt_0024.py (2 attempt(s))
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `gwt_id` | required | GWT behavior ID |
| `target_dir` | `.` | Project directory |
| `--max-attempts` | `3` | Maximum generation attempts |

## Step 8: Run Tests

Run all generated tests:

```bash
cw9 test /path/to/your/project
```

Run only tests affected by a specific node change (smart targeting):

```bash
cw9 test --node cfg-f7s8 /path/to/your/project
```

Smart targeting uses `query_affected_tests()` to trace the impact of a node change through the DAG and run only the relevant test files.

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `target_dir` | `.` | Project directory |
| `--node` | none | Only run tests affected by this node ID |

## Full Pipeline Example

```bash
# Initialize
cw9 init /path/to/myapp

# Edit schemas in .cw9/schema/ ...

# Build DAG
cw9 extract /path/to/myapp

# Register a GWT (via Python script or upstream system)
python3 -c "
from registry.dag import RegistryDag
from registry.context import ProjectContext
ctx = ProjectContext.from_target('/path/to/myapp')
dag = RegistryDag.load(ctx.state_root / 'dag.json')
gwt_id = dag.register_gwt(
    given='a user submits a form',
    when='validation runs',
    then='errors are displayed inline',
)
dag.save(ctx.state_root / 'dag.json')
print(f'Registered: {gwt_id}')
"

# Run the pipeline
cw9 loop gwt-0024 /path/to/myapp
cw9 bridge gwt-0024 /path/to/myapp
cw9 gen-tests gwt-0024 /path/to/myapp
cw9 test /path/to/myapp
```

## Checking Project Status

View the current state of a CW9 project:

```bash
cw9 status /path/to/your/project
```

Output:
```
CodeWriter9 project: /path/to/your/project
  engine: /path/to/CodeWriter9.0

  DAG: 45 nodes, 92 edges
  Schemas: 5
  Specs: 3
```

## Artifact Locations Summary

| Artifact | Path | Created by |
|----------|------|------------|
| Config | `.cw9/config.toml` | `cw9 init` |
| DAG | `.cw9/dag.json` | `cw9 extract` / `register_gwt()` |
| Schemas | `.cw9/schema/*.json` | `cw9 init` (templates) / user |
| TLA+ specs | `.cw9/specs/<gwt-id>.tla` | `cw9 loop` |
| TLC config | `.cw9/specs/<gwt-id>.cfg` | `cw9 loop` |
| Simulation traces | `.cw9/specs/<gwt-id>_sim_traces.json` | `cw9 loop` |
| Bridge artifacts | `.cw9/bridge/<gwt-id>_bridge_artifacts.json` | `cw9 bridge` |
| Generated tests | `tests/generated/test_<gwt_id>.py` | `cw9 gen-tests` |
| Session logs | `.cw9/sessions/<gwt-id>_attempt{N}.txt` | `cw9 loop` / `cw9 gen-tests` |

## Next Steps

- For the library API (`register_gwt`, `query_impact`, `extract_subgraph`, etc.), see [How to Use the CW9 Library API](howto-cw9-library-api.md).
- For the full list of CLI arguments and return codes, consult the CLI Reference.
- For schema format details, consult the Schema Reference.
