# CW9 `register` Subcommand — TDD Implementation Plan

## Overview

Add a `cw9 register <target_dir>` CLI subcommand that accepts JSON on stdin, registers requirements and GWT behaviors into the DAG, and emits JSON on stdout with the allocated IDs. This is the missing machine-to-machine bridge that enables CW7's Node.js `/api/chat` pipeline to register GWTs without a Python bridge script.

## Current State Analysis

### Key Discoveries
- CLI has 7 subcommands (`init`, `status`, `extract`, `loop`, `bridge`, `gen-tests`, `test`): `python/registry/cli.py:443-508`
- GWT registration is library-only via `RegistryDag.register_gwt()`: `python/registry/dag.py:313-352`
- `register_gwt()` raises `NodeNotFoundError` if `parent_req` ID doesn't exist in DAG: `python/registry/dag.py:347-349`
- `to_dict()` serializes only `nodes`, `edges`, `closure`, `components`, `test_artifacts`: `python/registry/dag.py:415-424`
- `from_dict()` ignores unknown keys in `dag.json`: `python/registry/dag.py:430-457`
- `cw9 init --force` overwrites `dag.json` with `_EMPTY_DAG`, destroying registered GWTs: `python/registry/cli.py:89-91`
- `cw9 loop` loads DAG read-only for prompt context building: `python/registry/loop_runner.py:101-118`
- Existing test patterns use `main(["subcommand", ...])` with `target_dir` fixture: `python/tests/test_cli.py`

### Constraints
- CW7 sends criterion IDs from its own DB (e.g., `"cw7-crit-1034"`) — not CW9 `gwt-NNNN` IDs
- CW7's `requirement_id` is a CW7-internal string, not a CW9 `req-NNNN` ID
- Idempotency is required for retries — re-registering the same criterion must return the existing `gwt_id`
- DAG schema (`dag.json`) should not be modified — criterion bindings go in a separate file

## Desired End State

A single new CLI subcommand where:
- `cw9 register <target_dir>` reads JSON from stdin, writes JSON to stdout
- Requirements and GWTs are registered atomically into the DAG
- Criterion-to-GWT ID bindings are persisted in `.cw9/criterion_bindings.json` for idempotency
- Re-registration with the same `criterion_id` returns the existing `gwt_id` (no duplicate nodes)
- `cw9 init` gains `--ensure` flag that is a no-op when `.cw9/` already exists

### Observable Behaviors
1. Given JSON stdin with requirements + GWTs, when `cw9 register` runs, then DAG contains new nodes and stdout has allocated IDs.
2. Given a GWT with `criterion_id` already registered, when `cw9 register` runs again, then the same `gwt_id` is returned without creating a duplicate node.
3. Given a GWT with `parent_req` referencing an ID from the `requirements` array, when registration runs, then the requirement is registered first and the DECOMPOSES edge is wired.
4. Given `cw9 init --ensure`, when `.cw9/` already exists, then exit 0 with no changes.
5. Given `cw9 init --ensure`, when `.cw9/` does not exist, then initialize normally.

## What We're NOT Doing

| Out of scope | What we ARE doing instead |
|---|---|
| Exit code 2 convention (infra vs domain) | Separate follow-up issue |
| `--json` flag on existing subcommands | Future enhancement |
| `--context-file` on `cw9 loop` | Separate follow-up issue |
| Modifying `dag.json` schema | Storing bindings in separate `.cw9/criterion_bindings.json` |
| Concurrent registration safety (file locking) | Sequential execution; document as known limitation |

---

## Smallest Testable Behaviors

1. **Bindings file persistence**: Load/save `.cw9/criterion_bindings.json` round-trips correctly.
2. **`--ensure` flag on init**: No-op when `.cw9/` exists; creates when absent.
3. **Requirement registration via stdin**: Requirements array creates `req-NNNN` nodes; stdout includes mapping.
4. **GWT registration via stdin**: GWTs array creates `gwt-NNNN` nodes with given/when/then; stdout includes mapping.
5. **Parent-req wiring**: GWT's `parent_req` references a requirement from the same payload; DECOMPOSES edge is created.
6. **Idempotent re-registration**: Same `criterion_id` returns same `gwt_id`; DAG node count unchanged.
7. **Error handling**: Missing `.cw9/`, malformed JSON, missing required fields → exit 1 + JSON error on stderr.

## Testing Strategy

- **Framework**: pytest (consistent with `python/tests/test_cli.py`)
- **Pattern**: Call `main(["register", str(target_dir)])` with stdin mock
- **Fixtures**: Reuse existing `target_dir` fixture from `test_cli.py`
- **Stdin mocking**: `monkeypatch.setattr("sys.stdin", io.StringIO(json_input))`

---

## Phase 1: Criterion Bindings File

### Overview
Create a minimal module for loading/saving criterion bindings separate from the DAG.

### Test Specification

**Behavior 1**: Bindings file round-trip

**Given**: An empty `.cw9/` directory.
**When**: Bindings are saved with `{"cw7-crit-1034": "gwt-0001"}` and loaded back.
**Then**: The loaded dict matches the saved dict exactly.

**Given**: No `.cw9/criterion_bindings.json` exists.
**When**: `load_bindings()` is called.
**Then**: Returns empty dict `{}`.

### TDD Cycle

#### Red: Write Failing Tests
**File**: `python/tests/test_register.py`
```python
import json
from pathlib import Path
import pytest
from registry.bindings import load_bindings, save_bindings


@pytest.fixture
def state_root(tmp_path):
    sr = tmp_path / ".cw9"
    sr.mkdir()
    return sr


class TestBindings:
    def test_load_missing_returns_empty(self, state_root):
        result = load_bindings(state_root)
        assert result == {}

    def test_save_and_load_round_trips(self, state_root):
        data = {"cw7-crit-1034": "gwt-0001", "cw7-crit-1035": "gwt-0002"}
        save_bindings(state_root, data)
        assert load_bindings(state_root) == data

    def test_save_overwrites_existing(self, state_root):
        save_bindings(state_root, {"a": "gwt-0001"})
        save_bindings(state_root, {"b": "gwt-0002"})
        assert load_bindings(state_root) == {"b": "gwt-0002"}
```

#### Green: Minimal Implementation
**File**: `python/registry/bindings.py`
```python
"""Criterion-to-GWT ID bindings for idempotent registration."""

from __future__ import annotations

import json
from pathlib import Path

_BINDINGS_FILE = "criterion_bindings.json"


def load_bindings(state_root: Path) -> dict[str, str]:
    path = state_root / _BINDINGS_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_bindings(state_root: Path, bindings: dict[str, str]) -> None:
    path = state_root / _BINDINGS_FILE
    path.write_text(json.dumps(bindings, indent=2) + "\n")
```

#### Refactor
None needed — module is minimal.

### Success Criteria

#### Automated:
- [ ] `cd python && python -m pytest tests/test_register.py::TestBindings -v`

---

## Phase 2: `--ensure` Flag on `cw9 init`

### Overview
Add `--ensure` flag that makes init idempotent — a no-op when `.cw9/` already exists.

### Test Specification

**Behavior 2a**: `--ensure` is no-op when `.cw9/` exists.

**Given**: A project with existing `.cw9/` containing a non-empty DAG.
**When**: `cw9 init --ensure` runs.
**Then**: Exit 0. DAG file is unchanged.

**Behavior 2b**: `--ensure` initializes when `.cw9/` is absent.

**Given**: A project with no `.cw9/` directory.
**When**: `cw9 init --ensure` runs.
**Then**: Exit 0. `.cw9/` is created with standard structure.

**Behavior 2c**: `--ensure` and `--force` are mutually exclusive.

**Given**: Both `--ensure` and `--force` flags.
**When**: `cw9 init --ensure --force` runs.
**Then**: Exit 1 with error message.

### TDD Cycle

#### Red: Write Failing Tests
**File**: `python/tests/test_cli.py` (add to existing `TestInit`)
```python
def test_ensure_is_noop_when_exists(self, target_dir):
    main(["init", str(target_dir)])
    # Modify DAG to prove it's not overwritten
    dag_path = target_dir / ".cw9" / "dag.json"
    dag_path.write_text('{"nodes": {"x": {}}, "edges": [], "test_artifacts": {}}')
    rc = main(["init", str(target_dir), "--ensure"])
    assert rc == 0
    data = json.loads(dag_path.read_text())
    assert "x" in data["nodes"]  # DAG was NOT overwritten

def test_ensure_creates_when_absent(self, target_dir):
    rc = main(["init", str(target_dir), "--ensure"])
    assert rc == 0
    assert (target_dir / ".cw9").is_dir()

def test_ensure_and_force_conflict(self, target_dir):
    rc = main(["init", str(target_dir), "--ensure", "--force"])
    assert rc == 1
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py`

In `cmd_init`, add early return for `--ensure`:
```python
def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()

    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 1

    if getattr(args, 'ensure', False) and getattr(args, 'force', False):
        print("Error: --ensure and --force are mutually exclusive", file=sys.stderr)
        return 1

    state_root = target / ".cw9"

    if getattr(args, 'ensure', False) and state_root.exists():
        return 0

    if state_root.exists() and not args.force:
        print(f".cw9/ already exists in {target}")
        print("Use --force to reinitialize.")
        return 1
    # ... rest unchanged
```

In argparse setup, add `--ensure`:
```python
p_init.add_argument("--ensure", action="store_true",
                     help="No-op if .cw9/ already exists (idempotent init)")
```

### Success Criteria

#### Automated:
- [ ] `cd python && python -m pytest tests/test_cli.py::TestInit -v`

---

## Phase 3: `cw9 register` — Core Registration

### Overview
The main subcommand. Reads JSON stdin, registers requirements + GWTs, writes JSON stdout.

### Stdin Contract

```json
{
  "requirements": [
    {"id": "cw7-req-42", "text": "Shamir 2-of-3 key backup and recovery"}
  ],
  "gwts": [
    {
      "criterion_id": "cw7-crit-1034",
      "given": "an existing encryption key configured for 2-of-3 Shamir",
      "when": "user runs CLI command to initiate key backup",
      "then": "exactly 3 distinct key shares are generated and verified",
      "parent_req": "cw7-req-42",
      "name": "backup_key_shamir"
    }
  ]
}
```

- `requirements` is optional (defaults to `[]`)
- `requirements[].id` is **required** — the CW7-side ID, stored in bindings for cross-reference
- `requirements[].text` is optional — falls back to `id` if omitted
- `gwts[].criterion_id` is required — the CW7-side key for idempotency
- `gwts[].parent_req` is optional — if provided, must reference an `id` from `requirements` array or an already-registered `req-NNNN` in the DAG
- `gwts[].name` is optional — auto-generated from `when` if omitted

### Stdout Contract

```json
{
  "requirements": [
    {"id": "cw7-req-42", "req_id": "req-0001"}
  ],
  "gwts": [
    {"criterion_id": "cw7-crit-1034", "gwt_id": "gwt-0001"}
  ]
}
```

### Processing Order

1. Load DAG and criterion bindings
2. Register requirements first (so GWTs can reference them via `parent_req`)
3. For each requirement: check bindings for existing mapping → reuse or allocate new
4. For each GWT: check bindings for existing mapping → reuse or allocate new
5. Resolve `parent_req`: map CW7 requirement ID → CW9 `req-NNNN` via bindings
6. Save DAG + bindings
7. Emit JSON stdout

### Test Specification

**Behavior 3a**: Register requirements from stdin.

**Given**: JSON stdin with one requirement `{"id": "r1", "text": "Auth system"}`.
**When**: `cw9 register` runs.
**Then**: DAG has a new `req-NNNN` node. Stdout JSON has `{"id": "r1", "req_id": "req-0001"}`. Bindings file maps `"req:r1" → "req-0001"`.

**Behavior 3b**: Register GWTs from stdin.

**Given**: JSON stdin with one GWT `{criterion_id: "c1", given: "g", when: "w", then: "t"}`.
**When**: `cw9 register` runs.
**Then**: DAG has a new `gwt-NNNN` node. Stdout JSON has `{"criterion_id": "c1", "gwt_id": "gwt-0001"}`.

**Behavior 3c**: Parent-req wiring via requirement ID cross-reference.

**Given**: JSON stdin with requirement `{id: "r1", text: "..."}` and GWT `{..., parent_req: "r1"}`.
**When**: `cw9 register` runs.
**Then**: DAG has a DECOMPOSES edge from the `req-NNNN` to the `gwt-NNNN`.

**Behavior 3d**: Idempotent re-registration.

**Given**: First registration created `gwt-0001` for `criterion_id: "c1"`.
**When**: Same JSON stdin is registered again.
**Then**: Stdout returns `gwt_id: "gwt-0001"`. DAG still has exactly one GWT node.

**Behavior 3e**: Mixed fresh + idempotent.

**Given**: First call registered `c1 → gwt-0001`. Second call has `c1` (existing) and `c2` (new).
**When**: `cw9 register` runs.
**Then**: `c1 → gwt-0001` (reused), `c2 → gwt-0002` (new).

**Behavior 3f**: Missing `.cw9/` → exit 1.

**Given**: No `.cw9/` directory.
**When**: `cw9 register` runs.
**Then**: Exit 1. Stderr has JSON error.

**Behavior 3g**: Malformed JSON → exit 1.

**Given**: Invalid JSON on stdin.
**When**: `cw9 register` runs.
**Then**: Exit 1. Stderr has JSON error.

**Behavior 3h**: Missing required `criterion_id` field → exit 1.

**Given**: GWT object without `criterion_id`.
**When**: `cw9 register` runs.
**Then**: Exit 1. Stderr has JSON error listing the missing field.

**Behavior 3i**: Missing required `requirements[].id` field → exit 1.

**Given**: A requirement object without `id` (e.g. `{"text": "no id here"}`).
**When**: `cw9 register` runs.
**Then**: Exit 1. Stderr has JSON error listing the missing field.

### TDD Cycle

#### Red: Write Failing Tests
**File**: `python/tests/test_register.py` (extend)
```python
import io
import json
from pathlib import Path

import pytest

from registry.cli import main
from registry.dag import RegistryDag


@pytest.fixture
def project(tmp_path):
    """Initialized CW9 project with extracted DAG."""
    project = tmp_path / "proj"
    project.mkdir()
    main(["init", str(project)])
    main(["extract", str(project)])
    return project


class TestRegister:
    def _run(self, project, payload, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        import io as _io
        stdout = _io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)
        rc = main(["register", str(project)])
        return rc, json.loads(stdout.getvalue()) if stdout.getvalue() else None

    def test_register_requirement(self, project, monkeypatch):
        rc, out = self._run(project, {
            "requirements": [{"id": "r1", "text": "Auth system"}],
            "gwts": [],
        }, monkeypatch)
        assert rc == 0
        assert len(out["requirements"]) == 1
        assert out["requirements"][0]["id"] == "r1"
        assert out["requirements"][0]["req_id"].startswith("req-")
        # Verify bindings file was written
        from registry.bindings import load_bindings
        bindings = load_bindings(project / ".cw9")
        assert bindings[f"req:r1"] == out["requirements"][0]["req_id"]

    def test_register_gwt(self, project, monkeypatch):
        rc, out = self._run(project, {
            "gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}],
        }, monkeypatch)
        assert rc == 0
        assert len(out["gwts"]) == 1
        assert out["gwts"][0]["criterion_id"] == "c1"
        assert out["gwts"][0]["gwt_id"].startswith("gwt-")

    def test_parent_req_wiring(self, project, monkeypatch):
        rc, out = self._run(project, {
            "requirements": [{"id": "r1", "text": "Auth"}],
            "gwts": [{"criterion_id": "c1", "given": "g", "when": "w",
                       "then": "t", "parent_req": "r1"}],
        }, monkeypatch)
        assert rc == 0
        dag = RegistryDag.load(project / ".cw9" / "dag.json")
        req_id = out["requirements"][0]["req_id"]
        gwt_id = out["gwts"][0]["gwt_id"]
        edges = [e for e in dag.edges
                 if e.from_id == req_id and e.to_id == gwt_id]
        assert len(edges) == 1

    def test_idempotent_reregistration(self, project, monkeypatch):
        payload = {"gwts": [{"criterion_id": "c1", "given": "g",
                              "when": "w", "then": "t"}]}
        rc1, out1 = self._run(project, payload, monkeypatch)
        assert rc1 == 0
        gwt_id = out1["gwts"][0]["gwt_id"]

        rc2, out2 = self._run(project, payload, monkeypatch)
        assert rc2 == 0
        assert out2["gwts"][0]["gwt_id"] == gwt_id

        dag = RegistryDag.load(project / ".cw9" / "dag.json")
        gwt_nodes = [n for n in dag.nodes if n.startswith("gwt-")]
        assert len(gwt_nodes) == 1

    def test_mixed_fresh_and_idempotent(self, project, monkeypatch):
        self._run(project, {
            "gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}],
        }, monkeypatch)

        rc, out = self._run(project, {
            "gwts": [
                {"criterion_id": "c1", "given": "g", "when": "w", "then": "t"},
                {"criterion_id": "c2", "given": "g2", "when": "w2", "then": "t2"},
            ],
        }, monkeypatch)
        assert rc == 0
        ids = [g["gwt_id"] for g in out["gwts"]]
        assert len(set(ids)) == 2  # two distinct IDs

    def test_no_cw9_fails(self, tmp_path, monkeypatch):
        bare = tmp_path / "bare"
        bare.mkdir()
        monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
        rc = main(["register", str(bare)])
        assert rc == 1

    def test_malformed_json_fails(self, project, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        rc = main(["register", str(project)])
        assert rc == 1

    def test_missing_criterion_id_fails(self, project, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
            "gwts": [{"given": "g", "when": "w", "then": "t"}],
        })))
        rc = main(["register", str(project)])
        assert rc == 1

    def test_missing_requirement_id_fails(self, project, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
            "requirements": [{"text": "no id here"}],
        })))
        rc = main(["register", str(project)])
        assert rc == 1
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py`

Add `cmd_register` function and wire into argparse:

```python
def cmd_register(args: argparse.Namespace) -> int:
    """Register requirements + GWT behaviors from JSON stdin. Emit JSON stdout."""
    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(json.dumps({"error": f"No .cw9/ found in {target}"}), file=sys.stderr)
        return 1

    # Read and parse stdin
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    from registry.dag import RegistryDag, NodeNotFoundError
    from registry.bindings import load_bindings, save_bindings

    ctx = ProjectContext.from_target(target)
    dag_path = ctx.state_root / "dag.json"
    dag = RegistryDag.load(dag_path)
    bindings = load_bindings(ctx.state_root)

    requirements = payload.get("requirements", [])
    gwts = payload.get("gwts", [])

    # Validate requirements have id
    for i, req in enumerate(requirements):
        if "id" not in req:
            print(json.dumps({"error": f"requirements[{i}]: missing required field 'id'"}),
                  file=sys.stderr)
            return 1

    # Validate GWTs have criterion_id
    for i, gwt in enumerate(gwts):
        if "criterion_id" not in gwt:
            print(json.dumps({"error": f"gwts[{i}]: missing required field 'criterion_id'"}),
                  file=sys.stderr)
            return 1
        for field in ("given", "when", "then"):
            if field not in gwt:
                print(json.dumps({"error": f"gwts[{i}]: missing required field '{field}'"}),
                      file=sys.stderr)
                return 1

    # Phase 1: Register requirements
    req_output = []
    req_id_map = {}  # CW7 id → CW9 req-NNNN
    for req in requirements:
        cw7_id = req.get("id", "")
        binding_key = f"req:{cw7_id}"

        if binding_key in bindings:
            req_id = bindings[binding_key]
        else:
            req_id = dag.register_requirement(
                text=req.get("text", cw7_id),
                name=req.get("name"),
            )
            bindings[binding_key] = req_id

        req_id_map[cw7_id] = req_id
        req_output.append({"id": cw7_id, "req_id": req_id})

    # Phase 2: Register GWTs
    gwt_output = []
    for gwt in gwts:
        criterion_id = gwt["criterion_id"]
        binding_key = f"gwt:{criterion_id}"

        if binding_key in bindings:
            gwt_id = bindings[binding_key]
        else:
            # Resolve parent_req: CW7 id → CW9 req-NNNN
            parent_req = None
            if gwt.get("parent_req"):
                cw7_req_id = gwt["parent_req"]
                parent_req = req_id_map.get(cw7_req_id)
                if parent_req is None:
                    # Check if it's already a CW9 req-NNNN ID in the DAG
                    if cw7_req_id in dag.nodes:
                        parent_req = cw7_req_id
                    else:
                        # Check bindings from a prior run
                        parent_req = bindings.get(f"req:{cw7_req_id}")

            gwt_id = dag.register_gwt(
                given=gwt["given"],
                when=gwt["when"],
                then=gwt["then"],
                parent_req=parent_req,
                name=gwt.get("name"),
            )
            bindings[binding_key] = gwt_id

        gwt_output.append({"criterion_id": criterion_id, "gwt_id": gwt_id})

    # Save
    dag.save(dag_path)
    save_bindings(ctx.state_root, bindings)

    # Emit JSON stdout
    result = {
        "requirements": req_output,
        "gwts": gwt_output,
    }
    print(json.dumps(result, indent=2))
    return 0
```

Wire into argparse in `main()`:
```python
# register
p_reg = sub.add_parser("register", help="Register requirements + GWTs from JSON stdin")
p_reg.add_argument("target_dir", nargs="?", default=".")
```

Add to dispatch:
```python
elif args.command == "register":
    return cmd_register(args)
```

#### Refactor
- Extract input validation into a helper if it grows
- Consider whether `_run` test helper should be a shared fixture

### Success Criteria

#### Automated:
- [ ] `cd python && python -m pytest tests/test_register.py -v`
- [ ] `cd python && python -m pytest tests/test_cli.py -v` (no regressions)
- [ ] `cd python && python -m pytest -x` (full suite passes)

#### Manual:
- [ ] `echo '{"gwts": [{"criterion_id": "test-1", "given": "g", "when": "w", "then": "t"}]}' | cw9 register /tmp/test-project` produces valid JSON stdout

---

## Phase 4: End-to-End Integration Smoke Test

### Overview
A single integration test that exercises the full CW7→CW9 handoff: init → extract → register → verify DAG state.

### Test Specification

**Given**: A fresh project initialized and extracted.
**When**: `cw9 register` is called with 1 requirement and 2 GWTs (one referencing the requirement as parent).
**Then**: DAG has the requirement node, both GWT nodes, and one DECOMPOSES edge. Bindings file has all three mappings. Stdout JSON has correct IDs. Re-running returns identical output.

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_register.py` (add to end)
```python
class TestRegisterE2E:
    def test_full_handoff_with_idempotent_retry(self, project, monkeypatch):
        """Simulates the CW7 adapter calling register twice."""
        payload = {
            "requirements": [
                {"id": "cw7-req-42", "text": "Shamir backup and recovery"},
            ],
            "gwts": [
                {"criterion_id": "cw7-crit-1034",
                 "given": "encryption key exists",
                 "when": "user initiates backup",
                 "then": "3 shares generated",
                 "parent_req": "cw7-req-42",
                 "name": "backup_shamir"},
                {"criterion_id": "cw7-crit-1035",
                 "given": "2 of 3 shares available",
                 "when": "user initiates recovery",
                 "then": "key is reconstructed"},
            ],
        }

        # First call
        rc1, out1 = self._run(project, payload, monkeypatch)
        assert rc1 == 0
        assert len(out1["requirements"]) == 1
        assert len(out1["gwts"]) == 2

        # Verify DAG
        dag = RegistryDag.load(project / ".cw9" / "dag.json")
        req_id = out1["requirements"][0]["req_id"]
        gwt1_id = out1["gwts"][0]["gwt_id"]
        gwt2_id = out1["gwts"][1]["gwt_id"]

        assert req_id in dag.nodes
        assert gwt1_id in dag.nodes
        assert gwt2_id in dag.nodes
        assert dag.nodes[gwt1_id].given == "encryption key exists"

        # DECOMPOSES edge from req to gwt1 (has parent_req)
        decompose_edges = [e for e in dag.edges
                           if e.from_id == req_id and e.to_id == gwt1_id]
        assert len(decompose_edges) == 1

        # gwt2 has no parent_req → no DECOMPOSES edge
        decompose_edges_2 = [e for e in dag.edges
                              if e.from_id == req_id and e.to_id == gwt2_id]
        assert len(decompose_edges_2) == 0

        # Second call — idempotent
        rc2, out2 = self._run(project, payload, monkeypatch)
        assert rc2 == 0
        assert out2 == out1  # exact same output

        # DAG node count unchanged
        dag2 = RegistryDag.load(project / ".cw9" / "dag.json")
        gwt_count = len([n for n in dag2.nodes if n.startswith("gwt-")])
        req_count = len([n for n in dag2.nodes if n.startswith("req-")])
        assert gwt_count == 2
        assert req_count == 1

    def _run(self, project, payload, monkeypatch):
        """Helper to run register with JSON stdin and capture JSON stdout."""
        import io as _io
        monkeypatch.setattr("sys.stdin", _io.StringIO(json.dumps(payload)))
        stdout = _io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)
        rc = main(["register", str(project)])
        output = stdout.getvalue()
        return rc, json.loads(output) if output.strip() else None
```

#### Green
Should pass with Phase 3 implementation — this is a verification test.

### Success Criteria

#### Automated:
- [ ] `cd python && python -m pytest tests/test_register.py::TestRegisterE2E -v`
- [ ] `cd python && python -m pytest -x` (full suite, no regressions)

---

## Verification Commands

```bash
cd /home/maceo/Dev/CodeWriter9.0/python

# RED phase (expect failures before implementation)
python -m pytest tests/test_register.py -v

# GREEN/REFACTOR validation
python -m pytest tests/test_register.py -v
python -m pytest tests/test_cli.py -v
python -m pytest -x

# Manual smoke test
echo '{"gwts": [{"criterion_id": "smoke-1", "given": "g", "when": "w", "then": "t"}]}' | cw9 register /tmp/cw9-smoke
```

## File Change Summary

| File | Action | Description |
|---|---|---|
| `python/registry/bindings.py` | **Create** | `load_bindings()` / `save_bindings()` for `.cw9/criterion_bindings.json` |
| `python/registry/cli.py` | **Edit** | Add `cmd_register()`, `--ensure` on init, `register` subparser |
| `python/tests/test_register.py` | **Create** | All register + bindings tests |
| `python/tests/test_cli.py` | **Edit** | Add `--ensure` tests to `TestInit` |

## Design Notes

### Concurrent `cw9 loop` is safe
`loop_runner.py:108` loads the DAG read-only. Multiple `cw9 loop` calls on different GWT IDs can run in parallel — they write to separate spec files (`.cw9/specs/<gwt-id>.tla`). However, `cw9 register` writes to `dag.json` and `criterion_bindings.json`, so it must not run concurrently with itself. CW7's adapter should call `register` once per batch, then fan out `loop` calls.

### Bindings key namespace
Bindings use prefixed keys (`req:cw7-id` and `gwt:criterion_id`) to avoid collision between requirement IDs and criterion IDs that happen to share the same string value.

### Stale bindings
Bindings assume DAG nodes are never manually deleted. If a bound node is missing from the DAG (e.g. user manually edited `dag.json`), `register_gwt()` will raise `NodeNotFoundError` when resolving `parent_req`. This is an unsupported edge case — no defensive code is needed.

### `parent_req` resolution order
1. Check `req_id_map` (requirements registered in the same payload)
2. Check if it's a raw CW9 `req-NNNN` ID already in the DAG
3. Check bindings from a prior run (`req:<cw7-id>`)
4. If none found, `parent_req` is set to `None` (no edge wired, GWT still registered)

This permissive resolution means a missing parent_req silently degrades rather than failing. This is deliberate — the GWT is more important than the edge, and the edge can be added later.

## References

- CW7 TDD plan: `/home/maceo/Dev/CodeWriter7/thoughts/searchable/shared/plans/2026-03-10-ENG-0000-tdd-cw9-api-chat-pipeline.md`
- CW7 plan review: `/home/maceo/Dev/CodeWriter7/thoughts/searchable/shared/plans/2026-03-10-ENG-0000-tdd-cw9-api-chat-pipeline-REVIEW.md`
- CW9 library API: `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/howto-cw9-library-api.md`
- CW9 CLI pipeline: `/home/maceo/Dev/CodeWriter9.0/thoughts/searchable/shared/docs/howto-cw9-cli-pipeline.md`
- DAG implementation: `python/registry/dag.py:313-352` (register_gwt), `python/registry/dag.py:415-457` (serialization)
- CLI implementation: `python/registry/cli.py:443-508` (main dispatcher)
- Existing CLI tests: `python/tests/test_cli.py`
