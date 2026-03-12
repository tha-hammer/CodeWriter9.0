"""Tests for run_loop_bridge.py — the full CW9 pipeline orchestrator.

Tests each phase (setup, loop, bridge) and the orchestration logic
in isolation using mocks, plus integration tests with real init/extract/register.
"""

from __future__ import annotations

import io
import json
import sqlite3
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure registry is importable (mirrors run_loop_bridge.py's own path hack)
import sys
import os

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = SCRIPT_DIR.parent
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from tools.run_loop_bridge import (
    _inline_fixture,
    _validate_bridge_artifacts,
    log,
    main,
    resolve_gwt_ids,
    run_bridge_phase,
    run_loop_phase,
    setup_project,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cw7_db(db_path: Path, session_id: str = "session-test") -> Path:
    """Create a minimal CW7 SQLite database for testing."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY)"
    )
    conn.execute("INSERT INTO sessions VALUES (?)", (session_id,))
    conn.execute(
        "CREATE TABLE requirements ("
        "  requirement_id TEXT, session_id TEXT, description TEXT"
        ")"
    )
    conn.execute(
        "INSERT INTO requirements VALUES (?, ?, ?)",
        ("REQ-001", session_id, "Counter starts at 0"),
    )
    conn.execute(
        "INSERT INTO requirements VALUES (?, ?, ?)",
        ("REQ-002", session_id, "Increment adds 1"),
    )
    conn.execute(
        "CREATE TABLE acceptance_criteria ("
        "  id INTEGER PRIMARY KEY, session_id TEXT, requirement_id TEXT,"
        "  format TEXT, given_clause TEXT, when_clause TEXT, then_clause TEXT"
        ")"
    )
    conn.execute(
        "INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, session_id, "REQ-001", "gwt",
         "the app loads", "the counter renders", "counter shows 0"),
    )
    conn.execute(
        "INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, session_id, "REQ-002", "gwt",
         "counter is 5", "user clicks increment", "counter becomes 6"),
    )
    conn.execute(
        "CREATE TABLE plan_paths ("
        "  id INTEGER PRIMARY KEY, session_id TEXT,"
        "  acceptance_criterion_id INTEGER"
        ")"
    )
    conn.execute(
        "INSERT INTO plan_paths VALUES (?, ?, ?)",
        (1001, session_id, 1),
    )
    conn.execute(
        "INSERT INTO plan_paths VALUES (?, ?, ?)",
        (1002, session_id, 2),
    )
    conn.commit()
    conn.close()
    return db_path


def _make_bridge_artifacts(gwt_id: str = "gwt-0001") -> dict:
    """Minimal valid bridge artifacts dict."""
    return {
        "gwt_id": gwt_id,
        "module_name": "TestModule",
        "data_structures": {
            "State": {
                "function_id": "State",
                "fields": {
                    "counter": {"type": "shared/data_types/integer"},
                },
            },
        },
        "operations": {
            "Increment": {
                "function_id": "Increment",
                "parameters": {"value": "int"},
                "returns": "int",
            },
        },
        "verifiers": {
            "CounterNonNegative": {
                "conditions": ["counter >= 0"],
                "applies_to": ["counter"],
            },
        },
        "assertions": {
            "assert_non_negative": {
                "condition": "counter >= 0",
                "message": "Counter went negative",
            },
        },
        "test_scenarios": [
            {
                "name": "increment_from_zero",
                "setup": "counter=0",
                "steps": ["increment()"],
                "expected_outcome": "counter=1",
            },
        ],
    }


def _init_project(tmp_path: Path) -> Path:
    """Create a project dir and run cw9 init + extract."""
    from registry.cli import main as cw9_main
    project = tmp_path / "proj"
    project.mkdir()
    cw9_main(["init", str(project)])
    cw9_main(["extract", str(project)])
    return project


# ---------------------------------------------------------------------------
# Tests: _inline_fixture
# ---------------------------------------------------------------------------

class TestInlineFixture:
    def test_has_requirements_and_gwts(self):
        data = _inline_fixture()
        assert "requirements" in data
        assert "gwts" in data
        assert len(data["requirements"]) >= 1
        assert len(data["gwts"]) >= 1

    def test_gwts_have_required_fields(self):
        data = _inline_fixture()
        for gwt in data["gwts"]:
            assert "criterion_id" in gwt
            assert "given" in gwt
            assert "when" in gwt
            assert "then" in gwt
            assert "parent_req" in gwt

    def test_requirements_have_required_fields(self):
        data = _inline_fixture()
        for req in data["requirements"]:
            assert "id" in req
            assert "text" in req


# ---------------------------------------------------------------------------
# Tests: _validate_bridge_artifacts
# ---------------------------------------------------------------------------

class TestValidateBridgeArtifacts:
    def test_valid_artifacts_pass(self):
        """No assertion raised for well-formed artifacts."""
        _validate_bridge_artifacts(_make_bridge_artifacts())

    def test_missing_gwt_id_fails(self):
        data = _make_bridge_artifacts()
        data["gwt_id"] = ""
        with pytest.raises(AssertionError, match="gwt_id"):
            _validate_bridge_artifacts(data)

    def test_missing_module_name_fails(self):
        data = _make_bridge_artifacts()
        data["module_name"] = ""
        with pytest.raises(AssertionError, match="module_name"):
            _validate_bridge_artifacts(data)

    def test_field_type_must_be_schema_path(self):
        data = _make_bridge_artifacts()
        data["data_structures"]["State"]["fields"]["counter"]["type"] = "int"
        with pytest.raises(AssertionError, match="not a schema path"):
            _validate_bridge_artifacts(data)

    def test_missing_data_structure_function_id(self):
        data = _make_bridge_artifacts()
        del data["data_structures"]["State"]["function_id"]
        with pytest.raises(AssertionError, match="function_id"):
            _validate_bridge_artifacts(data)

    def test_missing_operation_parameters(self):
        data = _make_bridge_artifacts()
        del data["operations"]["Increment"]["parameters"]
        with pytest.raises(AssertionError, match="missing parameters"):
            _validate_bridge_artifacts(data)

    def test_empty_verifier_conditions(self):
        data = _make_bridge_artifacts()
        data["verifiers"]["CounterNonNegative"]["conditions"] = []
        with pytest.raises(AssertionError, match="empty conditions"):
            _validate_bridge_artifacts(data)

    def test_missing_assertion_message(self):
        data = _make_bridge_artifacts()
        del data["assertions"]["assert_non_negative"]["message"]
        with pytest.raises(AssertionError, match="missing message"):
            _validate_bridge_artifacts(data)

    def test_missing_test_scenario_name(self):
        data = _make_bridge_artifacts()
        del data["test_scenarios"][0]["name"]
        with pytest.raises(AssertionError, match="missing name"):
            _validate_bridge_artifacts(data)


# ---------------------------------------------------------------------------
# Tests: resolve_gwt_ids
# ---------------------------------------------------------------------------

class TestResolveGwtIds:
    def test_explicit_gwts_returned_directly(self, tmp_path):
        result = resolve_gwt_ids(tmp_path, None, ["gwt-0001", "gwt-0002"])
        assert result == ["gwt-0001", "gwt-0002"]

    def test_explicit_gwts_override_register_output(self, tmp_path):
        register_out = {"gwts": [{"gwt_id": "gwt-0099"}]}
        result = resolve_gwt_ids(tmp_path, register_out, ["gwt-0001"])
        assert result == ["gwt-0001"]

    def test_from_register_output(self, tmp_path):
        register_out = {
            "gwts": [
                {"gwt_id": "gwt-0001"},
                {"gwt_id": "gwt-0002"},
            ],
        }
        result = resolve_gwt_ids(tmp_path, register_out, None)
        assert result == ["gwt-0001", "gwt-0002"]

    def test_from_dag_file(self, tmp_path):
        cw9_dir = tmp_path / ".cw9"
        cw9_dir.mkdir()
        dag = {
            "nodes": {
                "gwt-0003": {},
                "gwt-0001": {},
                "req-0001": {},
            },
            "edges": [],
        }
        (cw9_dir / "dag.json").write_text(json.dumps(dag))
        result = resolve_gwt_ids(tmp_path, None, None)
        assert result == ["gwt-0001", "gwt-0003"]  # sorted

    def test_dag_file_excludes_non_gwt_nodes(self, tmp_path):
        cw9_dir = tmp_path / ".cw9"
        cw9_dir.mkdir()
        dag = {"nodes": {"req-0001": {}, "res-0001": {}}, "edges": []}
        (cw9_dir / "dag.json").write_text(json.dumps(dag))
        result = resolve_gwt_ids(tmp_path, None, None)
        assert result == []

    def test_no_sources_returns_empty(self, tmp_path):
        result = resolve_gwt_ids(tmp_path, None, None)
        assert result == []

    def test_empty_register_output_falls_through_to_dag(self, tmp_path):
        cw9_dir = tmp_path / ".cw9"
        cw9_dir.mkdir()
        dag = {"nodes": {"gwt-0005": {}}, "edges": []}
        (cw9_dir / "dag.json").write_text(json.dumps(dag))
        register_out = {"gwts": []}
        result = resolve_gwt_ids(tmp_path, register_out, None)
        assert result == ["gwt-0005"]


# ---------------------------------------------------------------------------
# Tests: setup_project
# ---------------------------------------------------------------------------

class TestSetupProject:
    def test_setup_with_cw7_db(self, tmp_path):
        """Full setup: init → extract → register from a real CW7 DB."""
        project = tmp_path / "proj"
        project.mkdir()
        db_path = _make_cw7_db(tmp_path / "test.db")

        result = setup_project(project, db_path, session_id="session-test")

        assert "gwts" in result
        assert len(result["gwts"]) == 2
        assert all(g["gwt_id"].startswith("gwt-") for g in result["gwts"])
        assert (project / ".cw9").is_dir()
        assert (project / ".cw9" / "dag.json").exists()

    def test_setup_with_inline_fixture_when_db_missing(self, tmp_path):
        """Falls back to inline fixture when DB doesn't exist."""
        project = tmp_path / "proj"
        project.mkdir()
        fake_db = tmp_path / "nonexistent.db"

        result = setup_project(project, fake_db)

        assert "gwts" in result
        assert len(result["gwts"]) >= 1

    def test_setup_copies_context_files(self, tmp_path):
        """Context files are copied when plan_path_dir is provided."""
        project = tmp_path / "proj"
        project.mkdir()
        db_path = _make_cw7_db(tmp_path / "test.db")

        # Create plan_path files matching the plan_path_ids (1001, 1002)
        pp_dir = tmp_path / "plan_paths"
        pp_dir.mkdir()
        (pp_dir / "1001-counter-display.md").write_text("# Plan for display")
        (pp_dir / "1002-counter-increment.md").write_text("# Plan for increment")

        result = setup_project(
            project, db_path, session_id="session-test",
            plan_path_dir=pp_dir,
        )

        context_dir = project / ".cw9" / "context"
        assert context_dir.is_dir()
        # Files are named by criterion_id, not plan_path_id
        context_files = list(context_dir.glob("*.md"))
        assert len(context_files) >= 1

    def test_setup_session_id_auto_detected(self, tmp_path):
        """When only one session exists, it is auto-detected."""
        project = tmp_path / "proj"
        project.mkdir()
        db_path = _make_cw7_db(tmp_path / "test.db")

        # No session_id passed — should auto-detect "session-test"
        result = setup_project(project, db_path)
        assert len(result["gwts"]) == 2


# ---------------------------------------------------------------------------
# Tests: run_loop_phase
# ---------------------------------------------------------------------------

class TestRunLoopPhase:
    def test_loop_calls_cw9_main_for_each_gwt(self, tmp_path):
        """cw9 loop is called once per GWT ID."""
        calls = []

        def fake_main(args):
            calls.append(args)
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_loop_phase(tmp_path, ["gwt-0001", "gwt-0002"], max_retries=3)

        assert len(calls) == 2
        assert calls[0][0] == "loop"
        assert "gwt-0001" in calls[0]
        assert calls[1][0] == "loop"
        assert "gwt-0002" in calls[1]

    def test_loop_passes_max_retries(self, tmp_path):
        calls = []

        def fake_main(args):
            calls.append(args)
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            run_loop_phase(tmp_path, ["gwt-0001"], max_retries=7)

        assert "--max-retries" in calls[0]
        idx = calls[0].index("--max-retries")
        assert calls[0][idx + 1] == "7"

    def test_loop_records_pass_fail(self, tmp_path):
        """Results dict reflects per-GWT pass/fail from return codes."""
        call_count = 0

        def fake_main(args):
            nonlocal call_count
            call_count += 1
            return 0 if call_count == 1 else 1  # first passes, second fails

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_loop_phase(tmp_path, ["gwt-0001", "gwt-0002"], max_retries=1)

        assert results["gwt-0001"] is True
        assert results["gwt-0002"] is False

    def test_loop_with_context_files(self, tmp_path):
        """When gwt_to_criterion is provided, context file is passed if it exists."""
        context_dir = tmp_path / ".cw9" / "context"
        context_dir.mkdir(parents=True)
        (context_dir / "cw7-crit-100.md").write_text("# context")

        calls = []

        def fake_main(args):
            calls.append(args)
            return 0

        gwt_to_crit = {"gwt-0001": "cw7-crit-100"}

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            run_loop_phase(tmp_path, ["gwt-0001"], max_retries=1,
                           gwt_to_criterion=gwt_to_crit)

        assert "--context-file" in calls[0]
        ctx_idx = calls[0].index("--context-file")
        assert calls[0][ctx_idx + 1].endswith("cw7-crit-100.md")

    def test_loop_no_context_when_file_missing(self, tmp_path):
        """No --context-file arg when the context file doesn't exist."""
        # context dir exists but no matching file
        context_dir = tmp_path / ".cw9" / "context"
        context_dir.mkdir(parents=True)

        calls = []

        def fake_main(args):
            calls.append(args)
            return 0

        gwt_to_crit = {"gwt-0001": "cw7-crit-999"}

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            run_loop_phase(tmp_path, ["gwt-0001"], max_retries=1,
                           gwt_to_criterion=gwt_to_crit)

        assert "--context-file" not in calls[0]

    def test_loop_reads_sim_trace_count_on_pass(self, tmp_path):
        """On pass, loop checks for sim trace file."""
        specs_dir = tmp_path / ".cw9" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE Test ----\n====")
        (specs_dir / "gwt-0001_sim_traces.json").write_text(
            json.dumps([{"trace": 1}, {"trace": 2}])
        )

        def fake_main(args):
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_loop_phase(tmp_path, ["gwt-0001"], max_retries=1)

        assert results["gwt-0001"] is True


# ---------------------------------------------------------------------------
# Tests: run_bridge_phase
# ---------------------------------------------------------------------------

class TestRunBridgePhase:
    def test_bridge_skips_missing_specs(self, tmp_path):
        """GWTs without a verified spec are skipped."""
        specs_dir = tmp_path / ".cw9" / "specs"
        specs_dir.mkdir(parents=True)

        results = run_bridge_phase(tmp_path, ["gwt-0001"])
        assert results["gwt-0001"] is False

    def test_bridge_calls_cw9_main_for_existing_specs(self, tmp_path):
        """cw9 bridge is called when a spec file exists."""
        specs_dir = tmp_path / ".cw9" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE Test ----\n====")

        calls = []

        def fake_main(args):
            calls.append(args)
            return 1  # fail so we don't need artifacts

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_bridge_phase(tmp_path, ["gwt-0001"])

        assert len(calls) == 1
        assert calls[0] == ["bridge", "gwt-0001", str(tmp_path)]
        assert results["gwt-0001"] is False

    def test_bridge_reads_artifacts_on_success(self, tmp_path):
        """On success, bridge reads and validates the artifact file."""
        specs_dir = tmp_path / ".cw9" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE Test ----\n====")

        bridge_dir = tmp_path / ".cw9" / "bridge"
        bridge_dir.mkdir(parents=True)
        artifacts = _make_bridge_artifacts("gwt-0001")
        (bridge_dir / "gwt-0001_bridge_artifacts.json").write_text(
            json.dumps(artifacts)
        )

        def fake_main(args):
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_bridge_phase(tmp_path, ["gwt-0001"])

        assert results["gwt-0001"] is True

    def test_bridge_mixed_results(self, tmp_path):
        """Multiple GWTs: some pass, some fail, some skipped."""
        specs_dir = tmp_path / ".cw9" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE Test ----\n====")
        (specs_dir / "gwt-0002.tla").write_text("---- MODULE Test2 ----\n====")
        # gwt-0003 has no spec — will be skipped

        bridge_dir = tmp_path / ".cw9" / "bridge"
        bridge_dir.mkdir(parents=True)
        (bridge_dir / "gwt-0001_bridge_artifacts.json").write_text(
            json.dumps(_make_bridge_artifacts("gwt-0001"))
        )

        def fake_main(args):
            gwt_id = args[1]
            return 0 if gwt_id == "gwt-0001" else 1

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            results = run_bridge_phase(
                tmp_path, ["gwt-0001", "gwt-0002", "gwt-0003"]
            )

        assert results["gwt-0001"] is True
        assert results["gwt-0002"] is False
        assert results["gwt-0003"] is False


# ---------------------------------------------------------------------------
# Tests: main() CLI argument parsing and orchestration
# ---------------------------------------------------------------------------

class TestMainOrchestration:
    def _run_main(self, args: list[str]) -> int:
        """Run main() with the given CLI args."""
        with patch("sys.argv", ["run_loop_bridge.py"] + args):
            return main()

    def test_full_pipeline_with_cw7_db(self, tmp_path):
        """Full pipeline: setup → loop → bridge with a real CW7 DB."""
        db_path = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"

        # Mock cw9_main so loop/bridge succeed without real LLM
        real_cw9_main = None

        def selective_main(args):
            """Real init/extract/register, fake loop/bridge."""
            from registry.cli import main as real_main
            cmd = args[0]
            if cmd in ("init", "extract", "register"):
                return real_main(args)
            elif cmd == "loop":
                # Simulate loop success: create spec file
                gwt_id = args[1]
                project_dir = Path(args[2])
                specs_dir = project_dir / ".cw9" / "specs"
                specs_dir.mkdir(parents=True, exist_ok=True)
                (specs_dir / f"{gwt_id}.tla").write_text(
                    f"---- MODULE TestSpec ----\n====\n"
                )
                return 0
            elif cmd == "bridge":
                # Simulate bridge success: create artifact file
                gwt_id = args[1]
                project_dir = Path(args[2])
                bridge_dir = project_dir / ".cw9" / "bridge"
                bridge_dir.mkdir(parents=True, exist_ok=True)
                (bridge_dir / f"{gwt_id}_bridge_artifacts.json").write_text(
                    json.dumps(_make_bridge_artifacts(gwt_id))
                )
                return 0
            return 1

        with patch("tools.run_loop_bridge.cw9_main", selective_main):
            rc = self._run_main([
                "--db", str(db_path),
                "--project-dir", str(project),
                "--session", "session-test",
            ])

        assert rc == 0

    def test_loop_only_mode(self, tmp_path):
        """--loop-only skips bridge phase."""
        db_path = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        calls = []

        def selective_main(args):
            from registry.cli import main as real_main
            calls.append(args[0])
            if args[0] in ("init", "extract", "register"):
                return real_main(args)
            return 0  # loop succeeds

        with patch("tools.run_loop_bridge.cw9_main", selective_main):
            rc = self._run_main([
                "--db", str(db_path),
                "--project-dir", str(project),
                "--session", "session-test",
                "--loop-only",
            ])

        assert rc == 0
        assert "bridge" not in calls

    def test_bridge_only_mode(self, tmp_path):
        """--bridge-only skips setup and loop, runs bridge on existing specs."""
        project = tmp_path / "proj"
        project.mkdir()

        # Pre-create project structure with specs
        from registry.cli import main as real_main
        real_main(["init", str(project)])
        real_main(["extract", str(project)])

        specs_dir = project / ".cw9" / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        (specs_dir / "gwt-0001.tla").write_text("---- MODULE Test ----\n====")

        bridge_dir = project / ".cw9" / "bridge"
        bridge_dir.mkdir(parents=True, exist_ok=True)

        calls = []

        def fake_main(args):
            calls.append(args[0])
            if args[0] == "bridge":
                gwt_id = args[1]
                (bridge_dir / f"{gwt_id}_bridge_artifacts.json").write_text(
                    json.dumps(_make_bridge_artifacts(gwt_id))
                )
                return 0
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            rc = self._run_main([
                "--bridge-only",
                "--skip-setup",
                "--project-dir", str(project),
                "--gwt", "gwt-0001",
            ])

        assert rc == 0
        assert "init" not in calls
        assert "loop" not in calls
        assert "bridge" in calls

    def test_skip_setup_flag(self, tmp_path):
        """--skip-setup skips init/extract/register."""
        project = tmp_path / "proj"
        project.mkdir()

        # Pre-initialize
        from registry.cli import main as real_main
        real_main(["init", str(project)])
        real_main(["extract", str(project)])

        calls = []

        def fake_main(args):
            calls.append(args[0])
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            rc = self._run_main([
                "--skip-setup",
                "--project-dir", str(project),
                "--gwt", "gwt-0001",
                "--loop-only",
            ])

        assert rc == 0
        assert "init" not in calls
        assert "extract" not in calls
        assert "register" not in calls

    def test_no_gwts_returns_error(self, tmp_path):
        """If no GWT IDs can be resolved, main returns 1."""
        project = tmp_path / "proj"
        project.mkdir()
        from registry.cli import main as real_main
        real_main(["init", str(project)])

        with patch("tools.run_loop_bridge.cw9_main") as mock:
            mock.return_value = 0
            rc = self._run_main([
                "--skip-setup",
                "--project-dir", str(project),
            ])

        assert rc == 1

    def test_session_inferred_from_plan_path_dir(self, tmp_path):
        """Session ID is inferred from plan-path-dir name."""
        db_path = _make_cw7_db(tmp_path / "test.db", session_id="session-abc123")
        project = tmp_path / "proj"
        pp_dir = tmp_path / "session-abc123"
        pp_dir.mkdir()

        def selective_main(args):
            from registry.cli import main as real_main
            if args[0] in ("init", "extract", "register"):
                return real_main(args)
            return 0

        with patch("tools.run_loop_bridge.cw9_main", selective_main):
            rc = self._run_main([
                "--db", str(db_path),
                "--project-dir", str(project),
                "--plan-path-dir", str(pp_dir),
                "--loop-only",
            ])

        assert rc == 0

    def test_max_retries_passed_through(self, tmp_path):
        """--max-retries value flows through to run_loop_phase."""
        project = tmp_path / "proj"
        project.mkdir()
        from registry.cli import main as real_main
        real_main(["init", str(project)])

        calls = []

        def fake_main(args):
            calls.append(args)
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            self._run_main([
                "--skip-setup",
                "--project-dir", str(project),
                "--gwt", "gwt-0001",
                "--max-retries", "9",
                "--loop-only",
            ])

        loop_calls = [c for c in calls if c[0] == "loop"]
        assert len(loop_calls) == 1
        idx = loop_calls[0].index("--max-retries")
        assert loop_calls[0][idx + 1] == "9"

    def test_temp_dir_used_when_no_project_dir(self, tmp_path):
        """Without --project-dir, a temp directory is created."""
        db_path = _make_cw7_db(tmp_path / "test.db")

        created_dirs = []

        def selective_main(args):
            from registry.cli import main as real_main
            if args[0] == "init":
                # Capture the project dir from the init call
                created_dirs.append(args[1])
                return real_main(args)
            if args[0] in ("extract", "register"):
                return real_main(args)
            return 0

        with patch("tools.run_loop_bridge.cw9_main", selective_main):
            rc = self._run_main([
                "--db", str(db_path),
                "--session", "session-test",
                "--loop-only",
            ])

        assert rc == 0
        assert len(created_dirs) == 1
        assert "cw9-pipeline-" in created_dirs[0]

    def test_exit_code_reflects_loop_failures(self, tmp_path):
        """If any loop GWT fails, exit code is 1."""
        project = tmp_path / "proj"
        project.mkdir()
        from registry.cli import main as real_main
        real_main(["init", str(project)])

        def fake_main(args):
            if args[0] == "loop":
                return 1  # all loops fail
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            rc = self._run_main([
                "--skip-setup",
                "--project-dir", str(project),
                "--gwt", "gwt-0001",
                "--loop-only",
            ])

        assert rc == 1

    def test_exit_code_reflects_bridge_failures(self, tmp_path):
        """If bridge fails, exit code is 1 even if loop passed."""
        project = tmp_path / "proj"
        project.mkdir()
        from registry.cli import main as real_main
        real_main(["init", str(project)])

        specs_dir = project / ".cw9" / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)

        def fake_main(args):
            if args[0] == "loop":
                gwt_id = args[1]
                proj = Path(args[2])
                (proj / ".cw9" / "specs" / f"{gwt_id}.tla").write_text(
                    "---- MODULE T ----\n===="
                )
                return 0
            if args[0] == "bridge":
                return 1
            return 0

        with patch("tools.run_loop_bridge.cw9_main", fake_main):
            rc = self._run_main([
                "--skip-setup",
                "--project-dir", str(project),
                "--gwt", "gwt-0001",
            ])

        assert rc == 1


# ---------------------------------------------------------------------------
# Tests: log helper
# ---------------------------------------------------------------------------

class TestLog:
    def test_log_writes_to_stderr(self, capsys):
        log("test message")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "test message" in captured.err
