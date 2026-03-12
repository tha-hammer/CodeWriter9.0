# `cw9 pipeline` Subcommand — TDD Implementation Plan

## Overview

Wire `run_loop_bridge.py` into the installed `cw9` package as `cw9 pipeline`. This moves the CW7→CW9 pipeline orchestrator from a standalone developer script into a first-class CLI subcommand, making it available via `cw9 pipeline --db <path> <target>` after installation.

Three structural moves:
1. `python/tools/cw7_extract.py` → `python/registry/cw7.py` (CW7 input adapter)
2. Extract `_register_payload()` from `cmd_register()` (eliminate mock.patch hack)
3. `run_loop_bridge.py` logic → `cmd_pipeline()` in `registry/cli.py`

**Hard constraint**: `--db` is required when setup runs. Missing DB is an error, not a warning. No `_inline_fixture()` fallback.

## Current State Analysis

### Key Discoveries:
- `run_loop_bridge.py` (`python/tools/run_loop_bridge.py:1-490`) — standalone script, sys.path hack, calls `cw9_main(["..."])` as function
- `cw7_extract.py` (`python/tools/cw7_extract.py:1-184`) — 4 functions: `extract()`, `build_plan_path_map()`, `copy_context_files()`, `_slugify()`. Only deps: `sqlite3`, `pathlib`, `re`
- `cmd_register()` (`python/registry/cli.py:407-513`) — reads stdin JSON, registers into DAG, writes stdout JSON. The pipeline mocks stdin/stdout to call it.
- 8 existing subcommands all follow identical pattern: `cmd_*` handler → subparser → `if/elif` dispatch (`cli.py:567-642`)
- `python/tests/test_run_loop_bridge.py` — 44 existing tests against the script; these need import path updates
- `python/tools/test_loop_bridge.py` — standalone dev script that imports `tools.cw7_extract`; needs import update

### Existing test patterns:
- `test_register.py:54-59` — `monkeypatch.setattr("sys.stdin", ...)` for register
- `test_cli.py:8-21` — `main(["subcommand", str(path)])` direct invocation
- `test_run_loop_bridge.py:43-95` — `_make_cw7_db()` helper creates minimal CW7 SQLite fixture

## Desired End State

```
cw9 pipeline /path/to/project --db /path/to/cw7.db
cw9 pipeline /path/to/project --db /path/to/cw7.db --gwt gwt-0001
cw9 pipeline /path/to/project --db /path/to/cw7.db --loop-only
cw9 pipeline /path/to/project --bridge-only --gwt gwt-0001
cw9 pipeline /path/to/project --skip-setup --gwt gwt-0001
```

### Observable Behaviors:
- `from registry.cw7 import extract` works (installed package)
- `_register_payload(target, payload)` returns result dict without stdin/stdout
- `cw9 pipeline --db <missing.db>` errors with rc=1
- `cw9 pipeline --db <valid.db> <target>` runs setup → loop → bridge
- `--loop-only` / `--bridge-only` / `--skip-setup` control phase execution
- `--gwt` targets specific GWTs, `--plan-path-dir` copies context files
- Exit code 0 only when all attempted phases pass

## What We're NOT Doing
- Not changing existing 8 subcommands' behavior
- Not adding new dependencies to `pyproject.toml` (sqlite3 is stdlib)
- Not removing `tools/test_loop_bridge.py` (stays as dev script)
- Not changing `_validate_bridge_artifacts()` logic (moves as-is)

## Testing Strategy
- **Framework**: pytest (existing)
- **Test Types**: Unit (each function), Integration (full pipeline with mock LLM phases)
- **Mocking**: `patch("registry.cli._cw9_dispatch")` for loop/bridge phases; `_make_cw7_db()` for CW7 fixture
- **Key change**: Tests import from `registry.cw7` and `registry.cli` instead of `tools.*`

---

## Behavior 1: `registry.cw7` Importable Module

### Test Specification
**Given**: `cw7_extract.py` moved to `registry/cw7.py`
**When**: `from registry.cw7 import extract, build_plan_path_map, copy_context_files`
**Then**: All 3 functions are importable and work identically

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_cw7.py`
```python
"""Tests for registry.cw7 — CW7 database extraction."""
import sqlite3
import json
from pathlib import Path

import pytest

from registry.cw7 import extract, build_plan_path_map, copy_context_files


def _make_cw7_db(db_path: Path, session_id: str = "session-test") -> Path:
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO sessions VALUES (?)", (session_id,))
    conn.execute(
        "CREATE TABLE requirements ("
        "  requirement_id TEXT, session_id TEXT, description TEXT)"
    )
    conn.execute("INSERT INTO requirements VALUES (?, ?, ?)",
                 ("REQ-001", session_id, "Counter starts at 0"))
    conn.execute(
        "CREATE TABLE acceptance_criteria ("
        "  id INTEGER PRIMARY KEY, session_id TEXT, requirement_id TEXT,"
        "  format TEXT, given_clause TEXT, when_clause TEXT, then_clause TEXT)"
    )
    conn.execute("INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (1, session_id, "REQ-001", "gwt",
                  "the app loads", "the counter renders", "counter shows 0"))
    conn.execute("INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (2, session_id, "REQ-001", "gwt",
                  "counter is 5", "user clicks increment", "counter becomes 6"))
    conn.execute(
        "CREATE TABLE plan_paths ("
        "  id INTEGER PRIMARY KEY, session_id TEXT,"
        "  acceptance_criterion_id INTEGER)"
    )
    conn.execute("INSERT INTO plan_paths VALUES (?, ?, ?)",
                 (1001, session_id, 1))
    conn.execute("INSERT INTO plan_paths VALUES (?, ?, ?)",
                 (1002, session_id, 2))
    conn.commit()
    conn.close()
    return db_path


class TestExtract:
    def test_extract_returns_requirements_and_gwts(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        result = extract(db, "session-test")
        assert len(result["requirements"]) == 1
        assert len(result["gwts"]) == 2
        assert result["requirements"][0]["id"] == "REQ-001"
        assert result["gwts"][0]["criterion_id"] == "cw7-crit-1"
        assert result["gwts"][1]["criterion_id"] == "cw7-crit-2"

    def test_extract_auto_detects_single_session(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        result = extract(db)  # no session_id
        assert len(result["gwts"]) == 2

    def test_extract_gwt_has_given_when_then(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        result = extract(db, "session-test")
        gwt = result["gwts"][0]
        assert gwt["given"] == "the app loads"
        assert gwt["when"] == "the counter renders"
        assert gwt["then"] == "counter shows 0"

    def test_extract_derives_name_from_when(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        result = extract(db, "session-test")
        assert "name" in result["gwts"][0]
        assert result["gwts"][0]["name"] == "the_counter_renders"

    def test_extract_raises_on_no_sessions(self, tmp_path):
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        with pytest.raises(ValueError, match="No sessions"):
            extract(db_path)

    def test_extract_raises_on_multiple_sessions(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db", session_id="s1")
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO sessions VALUES (?)", ("s2",))
        conn.commit()
        conn.close()
        with pytest.raises(ValueError, match="Multiple sessions"):
            extract(db)


class TestBuildPlanPathMap:
    def test_maps_criterion_to_plan_path_id(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        result = build_plan_path_map(db, "session-test")
        assert result == {1: 1001}


class TestCopyContextFiles:
    def test_copies_matching_files(self, tmp_path):
        pp_dir = tmp_path / "plans"
        pp_dir.mkdir()
        (pp_dir / "1001-counter.md").write_text("# plan")
        ctx_dir = tmp_path / "context"
        gwts = [{"criterion_id": "cw7-crit-1"}]
        pp_map = {1: 1001}
        n = copy_context_files(pp_dir, ctx_dir, gwts, pp_map)
        assert n == 1
        assert (ctx_dir / "cw7-crit-1.md").read_text() == "# plan"

    def test_skips_missing_files(self, tmp_path):
        pp_dir = tmp_path / "plans"
        pp_dir.mkdir()
        ctx_dir = tmp_path / "context"
        gwts = [{"criterion_id": "cw7-crit-999"}]
        n = copy_context_files(pp_dir, ctx_dir, gwts, {999: 9999})
        assert n == 0
```

#### Green: Minimal Implementation
**File**: `python/registry/cw7.py`
- Copy `cw7_extract.py` contents
- Remove `if __name__ == "__main__"` block and `argparse` main
- Remove `sys.exit()` calls in `extract()` — raise `ValueError` instead:
  - `sys.exit("No sessions found")` → `raise ValueError("No sessions found")`
  - `sys.exit(f"Multiple sessions: {sessions}")` → `raise ValueError(f"Multiple sessions: {sessions}")`
  - The `main()` wrapper in `tools/cw7_extract.py` keeps `sys.exit()` for CLI use
- Keep `_slugify()`, `extract()`, `build_plan_path_map()`, `copy_context_files()`

#### Refactor
- Update `tools/cw7_extract.py` to `from registry.cw7 import extract, build_plan_path_map, copy_context_files` (backward compat for standalone use)
- Update `tools/test_loop_bridge.py` import

### Success Criteria
**Automated:**
- [ ] `test_cw7.py` fails before creating `registry/cw7.py` (Red)
- [ ] `test_cw7.py` passes after creating `registry/cw7.py` (Green)
- [ ] All existing tests still pass: `python3 -m pytest python/tests/ -x`

---

## Behavior 2: `_register_payload()` Extracted

### Test Specification
**Given**: `cmd_register()` contains registration logic coupled to stdin/stdout
**When**: `_register_payload(target, payload)` is called with a dict
**Then**: Returns `{"requirements": [...], "gwts": [...]}` without any stdin/stdout IO

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_cli.py` (add to existing file)
```python
class TestRegisterPayload:
    def test_registers_requirements_and_gwts(self, target_dir):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])

        from registry.cli import _register_payload
        payload = {
            "requirements": [{"id": "REQ-1", "text": "Test req"}],
            "gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}],
        }
        result = _register_payload(target_dir, payload)
        assert len(result["requirements"]) == 1
        assert result["requirements"][0]["req_id"].startswith("req-")
        assert len(result["gwts"]) == 1
        assert result["gwts"][0]["gwt_id"].startswith("gwt-")

    def test_idempotent_on_rerun(self, target_dir):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])

        from registry.cli import _register_payload
        payload = {
            "requirements": [{"id": "REQ-1", "text": "Test req"}],
            "gwts": [{"criterion_id": "c1", "given": "g", "when": "w", "then": "t"}],
        }
        r1 = _register_payload(target_dir, payload)
        r2 = _register_payload(target_dir, payload)
        # Same IDs on rerun (bindings persist)
        assert r1["gwts"][0]["gwt_id"] == r2["gwts"][0]["gwt_id"]

    def test_register_via_stdin_still_works(self, target_dir, monkeypatch):
        """cmd_register() thin wrapper still works."""
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])

        import io
        payload = {"requirements": [], "gwts": [
            {"criterion_id": "c1", "given": "g", "when": "w", "then": "t"},
        ]}
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)
        rc = main(["register", str(target_dir)])
        assert rc == 0
        result = json.loads(stdout.getvalue())
        assert result["gwts"][0]["gwt_id"].startswith("gwt-")
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py`
- Extract lines 421-512 from `cmd_register()` into `_register_payload(target: Path, payload: dict) -> dict`
- `cmd_register()` becomes: read stdin → validate → `_register_payload()` → write stdout

```python
def _register_payload(target: Path, payload: dict) -> dict:
    """Register requirements + GWT behaviors from a dict. Returns result dict.

    Returns:
        {"requirements": [{"id": cw7_id, "req_id": req_id}, ...],
         "gwts": [{"criterion_id": criterion_id, "gwt_id": gwt_id}, ...]}

    Raises:
        ValueError: If target has no .cw9/ directory or DAG is missing.
    """
    from registry.dag import RegistryDag
    from registry.bindings import load_bindings, save_bindings

    ctx = ProjectContext.from_target(target)
    dag_path = ctx.state_root / "dag.json"
    dag = RegistryDag.load(dag_path)
    bindings = load_bindings(ctx.state_root)

    requirements = payload.get("requirements", [])
    gwts = payload.get("gwts", [])

    # ... existing registration logic (lines 451-501) ...

    dag.save(dag_path)
    save_bindings(ctx.state_root, bindings)
    return {"requirements": req_output, "gwts": gwt_output}


def cmd_register(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(json.dumps({"error": f"No .cw9/ found in {target}"}), file=sys.stderr)
        return 1
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        return 1

    # Validate (existing validation logic stays here — it's CLI-layer)
    for i, req in enumerate(payload.get("requirements", [])):
        if "id" not in req:
            print(json.dumps({"error": f"requirements[{i}]: missing 'id'"}), file=sys.stderr)
            return 1
    for i, gwt in enumerate(payload.get("gwts", [])):
        if "criterion_id" not in gwt:
            print(json.dumps({"error": f"gwts[{i}]: missing 'criterion_id'"}), file=sys.stderr)
            return 1
        for field in ("given", "when", "then"):
            if field not in gwt:
                print(json.dumps({"error": f"gwts[{i}]: missing '{field}'"}), file=sys.stderr)
                return 1

    result = _register_payload(target, payload)
    print(json.dumps(result, indent=2))
    return 0
```

#### Refactor
- None needed — clean extraction

### Success Criteria
**Automated:**
- [ ] `TestRegisterPayload` tests fail before extraction (Red)
- [ ] Tests pass after extraction (Green)
- [ ] Existing `TestRegister` in `test_register.py` still passes
- [ ] `python3 -m pytest python/tests/ -x`

---

## Behavior 3: `cmd_pipeline()` — DB Required, No Fallback

### Test Specification
**Given**: `cw9 pipeline` subcommand exists
**When**: `--db` points to nonexistent file (and setup is not skipped)
**Then**: Returns error rc=1 with clear message

**Given**: `--db` omitted entirely and `CW7_DB` env var not set
**When**: Pipeline runs with setup
**Then**: Returns error rc=1

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py`
```python
"""Tests for cw9 pipeline subcommand."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from registry.cli import main


# Reuse _make_cw7_db from test_cw7.py or define locally
def _make_cw7_db(db_path, session_id="session-test"):
    # ... same helper ...


class TestPipelineDbRequired:
    def test_missing_db_returns_error(self, tmp_path, capsys):
        project = tmp_path / "proj"
        project.mkdir()
        rc = main(["pipeline", str(project), "--db", str(tmp_path / "nope.db")])
        assert rc == 1
        assert "not found" in capsys.readouterr().err.lower()

    def test_no_db_arg_and_no_env_returns_error(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("CW7_DB", raising=False)
        project = tmp_path / "proj"
        project.mkdir()
        rc = main(["pipeline", str(project)])
        assert rc == 1
        assert "db" in capsys.readouterr().err.lower()

    def test_skip_setup_does_not_require_db(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])
        # --skip-setup + --gwt + --loop-only: no DB needed
        with patch("registry.cli.cmd_loop") as mock_loop:
            mock_loop.return_value = 0
            rc = main(["pipeline", str(project),
                        "--skip-setup", "--gwt", "gwt-0001", "--loop-only"])
        assert rc == 0

    def test_bridge_only_does_not_require_db(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])
        specs_dir = project / ".cw9" / "specs"
        specs_dir.mkdir(exist_ok=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE T ----\n====")
        with patch("registry.cli.cmd_bridge") as mock_bridge:
            mock_bridge.return_value = 0
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 0
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py` — add `cmd_pipeline()` stub + subparser + dispatch

**Subparser registration** (in `main()`, following existing `p_<name>` pattern):
```python
p_pipeline = sub.add_parser("pipeline", help="Run full CW9 pipeline: setup → loop → bridge")
p_pipeline.add_argument("target_dir", nargs="?", default=".")
p_pipeline.add_argument("--db", type=Path, default=None,
                         help="CW7 SQLite database path (or set CW7_DB env var)")
p_pipeline.add_argument("--session", default=None)
p_pipeline.add_argument("--gwt", action="append", dest="gwts", default=None)
p_pipeline.add_argument("--max-retries", type=int, default=5)
p_pipeline.add_argument("--skip-setup", action="store_true")
p_pipeline.add_argument("--loop-only", action="store_true")
p_pipeline.add_argument("--bridge-only", action="store_true")
p_pipeline.add_argument("--plan-path-dir", type=Path, default=None)
```

**Dispatch** (in `main()`'s if/elif chain):
```python
elif args.command == "pipeline":
    return cmd_pipeline(args)
```

**Handler**:
```python
def cmd_pipeline(args: argparse.Namespace) -> int:
    """Run full CW9 pipeline: setup → loop → bridge."""
    target = Path(args.target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    need_setup = not args.skip_setup and not args.bridge_only
    if need_setup:
        db = args.db or Path(os.environ.get("CW7_DB", ""))
        if not db or not str(db):
            print("Error: --db required (or set CW7_DB)", file=sys.stderr)
            return 1
        if not db.exists():
            print(f"Error: CW7 database not found: {db}", file=sys.stderr)
            return 1
        args.db = db  # normalize for downstream use
    # ... rest of pipeline ...
```

**Notes**:
- `target_dir` is the first positional arg (matches desired syntax `cw9 pipeline /path/to/project --db ...`)
- `--gwt` uses `action="append"` and `dest="gwts"` (plural) — tests must reference `args.gwts`
- `--db` falls back to `CW7_DB` env var when not provided
- `--plan-path-dir` is only meaningful when setup phase runs; ignored with `--skip-setup` or `--bridge-only`
- Non-existent `--gwt` IDs are passed through; `cmd_loop` handles the error

### Success Criteria
**Automated:**
- [ ] `TestPipelineDbRequired` fails before adding `cmd_pipeline` (Red)
- [ ] Tests pass after implementation (Green)
- [ ] `python3 -m pytest python/tests/test_pipeline.py -x`

---

## Behavior 4: `cmd_pipeline()` — Full Pipeline

### Test Specification
**Given**: Valid CW7 DB and project directory
**When**: `cw9 pipeline <target> --db <db>`
**Then**: Runs setup (init → extract → register) → loop per-GWT → bridge per-verified-GWT

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py` (add to file)
```python
def _make_bridge_artifacts(gwt_id="gwt-0001"):
    """Minimal valid bridge artifacts."""
    return {
        "gwt_id": gwt_id, "module_name": "TestModule",
        "data_structures": {"S": {"function_id": "S", "fields": {
            "x": {"type": "shared/data_types/integer"}}}},
        "operations": {"Op": {"function_id": "Op", "parameters": {}, "returns": "None"}},
        "verifiers": {"V": {"conditions": ["x >= 0"], "applies_to": ["x"]}},
        "assertions": {"A": {"condition": "x >= 0", "message": "neg"}},
        "test_scenarios": [{"name": "t", "setup": "x=0", "steps": ["op()"]}],
    }


class TestPipelineFullRun:
    def test_full_pipeline_setup_loop_bridge(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        original_cmd_loop = None
        original_cmd_bridge = None

        def fake_loop(args):
            t = Path(args.target_dir).resolve()
            specs = t / ".cw9" / "specs"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / f"{args.gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(args):
            t = Path(args.target_dir).resolve()
            bd = t / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{args.gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(args.gwt_id)))
            return 0

        with patch("registry.cli.cmd_loop", fake_loop), \
             patch("registry.cli.cmd_bridge", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])

        assert rc == 0
        assert (project / ".cw9" / "dag.json").exists()
        # Verify GWTs were registered
        dag_data = json.loads((project / ".cw9" / "dag.json").read_text())
        gwt_nodes = [n for n in dag_data["nodes"] if n.startswith("gwt-")]
        assert len(gwt_nodes) >= 1

    def test_pipeline_calls_loop_per_gwt(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        loop_gwts = []

        def fake_loop(args):
            loop_gwts.append(args.gwt_id)
            t = Path(args.target_dir).resolve()
            specs = t / ".cw9" / "specs"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / f"{args.gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(args):
            t = Path(args.target_dir).resolve()
            bd = t / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{args.gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(args.gwt_id)))
            return 0

        with patch("registry.cli.cmd_loop", fake_loop), \
             patch("registry.cli.cmd_bridge", fake_bridge):
            main(["pipeline", str(project),
                  "--db", str(db), "--session", "session-test"])

        # DB has 2 GWTs
        assert len(loop_gwts) == 2
```

#### Green: Implement setup → loop → bridge orchestration in `cmd_pipeline()`

Uses `_register_payload()` directly (no stdin/stdout mock), calls `cmd_loop()` and `cmd_bridge()` by constructing `argparse.Namespace` objects.

**GWT resolution helper** (private, in `cli.py`):
```python
def _resolve_gwt_ids(project_dir: Path, register_output: dict | None, explicit_gwts: list | None) -> list[str]:
    """Determine which GWT IDs to process.

    Resolution order:
    1. Explicit --gwt args (if provided)
    2. register_output from setup phase (if available)
    3. DAG nodes (fallback)
    """
    if explicit_gwts:
        return explicit_gwts
    if register_output and register_output.get("gwts"):
        return [g["gwt_id"] for g in register_output["gwts"]]
    dag_path = project_dir / ".cw9" / "dag.json"
    if dag_path.exists():
        dag_data = json.loads(dag_path.read_text())
        return sorted(nid for nid in dag_data.get("nodes", {}) if nid.startswith("gwt-"))
    return []
```

**Namespace construction for cmd_loop/cmd_bridge calls**:
```python
# When calling cmd_loop per GWT:
for gwt_id in gwt_ids:
    ctx_file_path = _find_context_file(project_dir, gwt_id)  # Path or None
    loop_ns = argparse.Namespace(
        gwt_id=gwt_id,
        target_dir=str(target),
        max_retries=args.max_retries,
        context_file=ctx_file_path,
    )
    rc = cmd_loop(loop_ns)
    loop_results[gwt_id] = (rc == 0)

# Bridge runs only for verified GWTs (those with .tla specs):
verified_ids = [gid for gid, passed in loop_results.items() if passed]
for gwt_id in verified_ids:
    spec_path = target / ".cw9" / "specs" / f"{gwt_id}.tla"
    if not spec_path.exists():
        continue
    bridge_ns = argparse.Namespace(
        gwt_id=gwt_id,
        target_dir=str(target),
    )
    rc = cmd_bridge(bridge_ns)
    bridge_results[gwt_id] = (rc == 0)
```

**Partial failure behavior**: If GWT-1 loop passes but GWT-2 loop fails, bridge still runs for GWT-1. Final rc=1 because not all GWTs passed.

### Success Criteria
**Automated:**
- [ ] Full pipeline test fails before implementation (Red)
- [ ] Tests pass after implementation (Green)

---

## Behavior 5: `cmd_pipeline()` — Mode Flags

### Test Specification
**Given**: `--loop-only` flag
**When**: Pipeline runs
**Then**: Bridge phase is skipped entirely

**Given**: `--bridge-only` flag
**When**: Pipeline runs
**Then**: Setup and loop are skipped; bridge runs on existing specs

**Given**: `--skip-setup` flag
**When**: Pipeline runs
**Then**: init/extract/register are skipped; loop/bridge run on existing project

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py` (add to file)
```python
class TestPipelineModeFlags:
    def test_loop_only_skips_bridge(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        bridge_called = []

        def fake_loop(args):
            return 0

        def fake_bridge(args):
            bridge_called.append(args.gwt_id)
            return 0

        with patch("registry.cli.cmd_loop", fake_loop), \
             patch("registry.cli.cmd_bridge", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test",
                        "--loop-only"])
        assert rc == 0
        assert bridge_called == []

    def test_bridge_only_skips_setup_and_loop(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])
        specs = project / ".cw9" / "specs"
        specs.mkdir(exist_ok=True)
        (specs / "gwt-0001.tla").write_text("---- MODULE T ----\n====")

        loop_called = []

        def fake_bridge(args):
            t = Path(args.target_dir).resolve()
            bd = t / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{args.gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(args.gwt_id)))
            return 0

        with patch("registry.cli.cmd_loop") as mock_loop, \
             patch("registry.cli.cmd_bridge", fake_bridge):
            mock_loop.side_effect = lambda a: loop_called.append(1) or 0
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 0
        assert loop_called == []

    def test_skip_setup_uses_existing_project(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])

        def fake_loop(args):
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            rc = main(["pipeline", str(project),
                        "--skip-setup", "--gwt", "gwt-0001", "--loop-only"])
        assert rc == 0
```

#### Green: Add flag handling to `cmd_pipeline()`

### Success Criteria
**Automated:**
- [ ] Mode flag tests fail before implementation (Red)
- [ ] Tests pass after implementation (Green)

---

## Behavior 6: `cmd_pipeline()` — GWT Targeting and Context Files

### Test Specification
**Given**: `--gwt gwt-0001 --gwt gwt-0002` flags
**When**: Pipeline runs
**Then**: Only those GWTs are processed

**Given**: `--plan-path-dir` with matching files
**When**: Setup phase runs
**Then**: Context files are copied to `.cw9/context/` and passed to loop via `--context-file`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py` (add to file)
```python
class TestPipelineGwtTargeting:
    def test_explicit_gwts_processed(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        loop_gwts = []

        def fake_loop(args):
            loop_gwts.append(args.gwt_id)
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            main(["pipeline", str(project), "--db", str(db),
                  "--session", "session-test",
                  "--gwt", "gwt-0001", "--loop-only"])

        assert loop_gwts == ["gwt-0001"]

    def test_plan_path_dir_copies_context(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "plans"
        pp_dir.mkdir()
        (pp_dir / "1001-counter.md").write_text("# plan context")

        def fake_loop(args):
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            main(["pipeline", str(project), "--db", str(db),
                  "--session", "session-test",
                  "--plan-path-dir", str(pp_dir), "--loop-only"])

        context_dir = project / ".cw9" / "context"
        assert context_dir.exists()
        assert len(list(context_dir.glob("*.md"))) >= 1

    def test_context_file_passed_to_loop(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "plans"
        pp_dir.mkdir()
        (pp_dir / "1001-counter.md").write_text("# plan")

        loop_args_captured = []

        def fake_loop(args):
            loop_args_captured.append(args)
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            main(["pipeline", str(project), "--db", str(db),
                  "--session", "session-test",
                  "--plan-path-dir", str(pp_dir), "--loop-only"])

        # At least one loop call should have context_file set
        ctx_files = [a.context_file for a in loop_args_captured if a.context_file]
        assert len(ctx_files) >= 1
```

#### Green: Implement GWT targeting and context file routing

### Success Criteria
**Automated:**
- [ ] GWT targeting tests fail before implementation (Red)
- [ ] Tests pass after implementation (Green)

---

## Behavior 7: `cmd_pipeline()` — Session Inference

### Test Specification
**Given**: `--plan-path-dir /path/to/session-abc123` and no `--session`
**When**: Pipeline runs setup
**Then**: Session ID is inferred as `"session-abc123"`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py` (add to file)
```python
class TestPipelineSessionInference:
    def test_session_inferred_from_plan_path_dir(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db", session_id="session-xyz789")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "session-xyz789"
        pp_dir.mkdir()

        def fake_loop(args):
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            rc = main(["pipeline", str(project), "--db", str(db),
                        "--plan-path-dir", str(pp_dir), "--loop-only"])
        assert rc == 0

    def test_explicit_session_overrides_inference(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db", session_id="session-explicit")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "session-wrong"
        pp_dir.mkdir()

        def fake_loop(args):
            return 0

        with patch("registry.cli.cmd_loop", fake_loop):
            rc = main(["pipeline", str(project), "--db", str(db),
                        "--session", "session-explicit",
                        "--plan-path-dir", str(pp_dir), "--loop-only"])
        assert rc == 0
```

#### Green: Add session inference logic to `cmd_pipeline()`

### Success Criteria
**Automated:**
- [ ] Session inference tests fail before implementation (Red)
- [ ] Tests pass after implementation (Green)

---

## Behavior 8: `cmd_pipeline()` — Exit Codes

### Test Specification
**Given**: All GWTs pass loop and bridge
**When**: Pipeline completes
**Then**: Exit code is 0

**Given**: Any GWT fails loop
**When**: Pipeline completes
**Then**: Exit code is 1

**Given**: Loop passes but bridge fails
**When**: Pipeline completes
**Then**: Exit code is 1

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_pipeline.py` (add to file)
```python
class TestPipelineExitCodes:
    def test_all_pass_returns_0(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        def fake_loop(args):
            t = Path(args.target_dir).resolve()
            s = t / ".cw9" / "specs"
            s.mkdir(parents=True, exist_ok=True)
            (s / f"{args.gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(args):
            t = Path(args.target_dir).resolve()
            bd = t / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{args.gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(args.gwt_id)))
            return 0

        with patch("registry.cli.cmd_loop", fake_loop), \
             patch("registry.cli.cmd_bridge", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])
        assert rc == 0

    def test_loop_failure_returns_1(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        with patch("registry.cli.cmd_loop", return_value=1):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test",
                        "--loop-only"])
        assert rc == 1

    def test_bridge_failure_returns_1(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])
        specs = project / ".cw9" / "specs"
        specs.mkdir(exist_ok=True)
        (specs / "gwt-0001.tla").write_text("---- MODULE T ----\n====")

        with patch("registry.cli.cmd_bridge", return_value=1):
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 1

    def test_partial_failure_bridge_runs_for_passed_gwts(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        bridge_gwts = []
        call_count = [0]

        def fake_loop(args):
            call_count[0] += 1
            t = Path(args.target_dir).resolve()
            if call_count[0] == 1:
                # First GWT passes
                s = t / ".cw9" / "specs"
                s.mkdir(parents=True, exist_ok=True)
                (s / f"{args.gwt_id}.tla").write_text("---- MODULE T ----\n====")
                return 0
            return 1  # Second GWT fails

        def fake_bridge(args):
            bridge_gwts.append(args.gwt_id)
            t = Path(args.target_dir).resolve()
            bd = t / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{args.gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(args.gwt_id)))
            return 0

        with patch("registry.cli.cmd_loop", fake_loop), \
             patch("registry.cli.cmd_bridge", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])

        # Bridge ran for the passing GWT
        assert len(bridge_gwts) == 1
        # Overall rc=1 because one GWT failed
        assert rc == 1

    def test_no_gwts_found_returns_1(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        rc = main(["pipeline", str(project), "--skip-setup"])
        assert rc == 1
```

#### Green: Implement exit code logic in `cmd_pipeline()`

### Success Criteria
**Automated:**
- [ ] Exit code tests fail before implementation (Red)
- [ ] Tests pass after implementation (Green)

---

## Behavior 9: Existing `cw9 register` Unchanged

### Test Specification
**Given**: `cmd_register()` refactored to use `_register_payload()`
**When**: `cw9 register` called via stdin/stdout
**Then**: Identical behavior to before

### TDD Cycle

This is a **regression gate** — no new tests needed. Existing `test_register.py` tests must all pass unchanged after the refactor.

### Success Criteria
**Automated:**
- [ ] `python3 -m pytest python/tests/test_register.py -v` — all pass
- [ ] `python3 -m pytest python/tests/test_cli.py -v` — all pass
- [ ] Full suite: `python3 -m pytest python/tests/ -x` — all pass

---

## Implementation Order

```
B1: registry/cw7.py        ← move file, write test_cw7.py
    │
B2: _register_payload()    ← extract from cmd_register, add tests
    │
B3: cmd_pipeline DB guard  ← stub subcommand, test DB requirement
    │
B4: cmd_pipeline full run  ← setup → loop → bridge orchestration
    │
B5: cmd_pipeline modes     ← --loop-only, --bridge-only, --skip-setup
    │
B6: cmd_pipeline targeting ← --gwt, --plan-path-dir, context files
    │
B7: session inference       ← --plan-path-dir dirname → session ID
    │
B8: exit codes              ← 0/1 based on all-pass
    │
B9: regression gate         ← existing tests pass unchanged
```

## Cleanup After All Behaviors Pass

1. **Delete** `python/tools/run_loop_bridge.py` (absorbed into `cmd_pipeline`)
2. **Thin out** `python/tools/cw7_extract.py` to re-export from `registry.cw7`:
   ```python
   """Backward compat — use `from registry.cw7 import ...` instead."""
   from registry.cw7 import extract, build_plan_path_map, copy_context_files, main
   if __name__ == "__main__":
       main()
   ```
3. **Update** `python/tools/test_loop_bridge.py` imports: `from registry.cw7 import ...`
4. **Delete** `python/tests/test_run_loop_bridge.py` (replaced by `test_pipeline.py` + `test_cw7.py`)
5. **Update** howto doc to add `cw9 pipeline` batch mode section

## References

- Research: `thoughts/searchable/shared/research/2026-03-12-run-loop-bridge-wiring.md`
- Howto: `thoughts/searchable/shared/docs/howto-cw9-cli-pipeline.md`
- Source: `python/tools/run_loop_bridge.py:1-490`
- Source: `python/tools/cw7_extract.py:1-184`
- CLI: `python/registry/cli.py:407-513` (cmd_register), `cli.py:567-642` (main/dispatch)
- Tests: `python/tests/test_run_loop_bridge.py` (44 existing tests to migrate)
- Beads: CodeWriter9.0-5bc (CLI Pipeline Commands), CodeWriter9.0-59h (Package as binary)
