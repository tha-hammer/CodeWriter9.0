"""Tests for cw9 pipeline subcommand."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from registry.cli import main


def _make_cw7_db(db_path, session_id="session-test"):
    """Create a minimal CW7 SQLite database for testing."""
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


# ── B3: DB Required, No Fallback ──────────────────────────────────────


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
        with patch("registry.cli._run_loop_core") as mock_loop:
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
        with patch("registry.cli._run_bridge_core") as mock_bridge:
            mock_bridge.return_value = 0
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 0


# ── B4: Full Pipeline ─────────────────────────────────────────────────


class TestPipelineFullRun:
    def test_full_pipeline_setup_loop_bridge(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        def fake_loop(target, gwt_id, **kw):
            specs = target / ".cw9" / "specs"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / f"{gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(target, gwt_id):
            bd = target / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(gwt_id)))
            return 0

        with patch("registry.cli._run_loop_core", fake_loop), \
             patch("registry.cli._run_bridge_core", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])

        assert rc == 0
        assert (project / ".cw9" / "dag.json").exists()
        dag_data = json.loads((project / ".cw9" / "dag.json").read_text())
        gwt_nodes = [n for n in dag_data["nodes"] if n.startswith("gwt-")]
        assert len(gwt_nodes) >= 1

    def test_pipeline_calls_loop_per_gwt(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        loop_gwts = []

        def fake_loop(target, gwt_id, **kw):
            loop_gwts.append(gwt_id)
            specs = target / ".cw9" / "specs"
            specs.mkdir(parents=True, exist_ok=True)
            (specs / f"{gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(target, gwt_id):
            bd = target / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(gwt_id)))
            return 0

        with patch("registry.cli._run_loop_core", fake_loop), \
             patch("registry.cli._run_bridge_core", fake_bridge):
            main(["pipeline", str(project),
                  "--db", str(db), "--session", "session-test"])

        assert len(loop_gwts) == 2


# ── B5: Mode Flags ────────────────────────────────────────────────────


class TestPipelineModeFlags:
    def test_loop_only_skips_bridge(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        bridge_called = []

        def fake_loop(target, gwt_id, **kw):
            return 0

        def fake_bridge(target, gwt_id):
            bridge_called.append(gwt_id)
            return 0

        with patch("registry.cli._run_loop_core", fake_loop), \
             patch("registry.cli._run_bridge_core", fake_bridge):
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

        def fake_bridge(target, gwt_id):
            bd = target / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(gwt_id)))
            return 0

        with patch("registry.cli._run_loop_core") as mock_loop, \
             patch("registry.cli._run_bridge_core", fake_bridge):
            mock_loop.side_effect = lambda target, gwt_id, **kw: loop_called.append(1) or 0
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 0
        assert loop_called == []

    def test_skip_setup_uses_existing_project(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        main(["extract", str(project)])

        def fake_loop(target, gwt_id, **kw):
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
            rc = main(["pipeline", str(project),
                        "--skip-setup", "--gwt", "gwt-0001", "--loop-only"])
        assert rc == 0


# ── B6: GWT Targeting and Context Files ───────────────────────────────


class TestPipelineGwtTargeting:
    def test_explicit_gwts_processed(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        loop_gwts = []

        def fake_loop(target, gwt_id, **kw):
            loop_gwts.append(gwt_id)
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
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

        def fake_loop(target, gwt_id, **kw):
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
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

        loop_kwargs_captured = []

        def fake_loop(target, gwt_id, **kw):
            loop_kwargs_captured.append(kw)
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
            main(["pipeline", str(project), "--db", str(db),
                  "--session", "session-test",
                  "--plan-path-dir", str(pp_dir), "--loop-only"])

        ctx_files = [kw.get("context_file") for kw in loop_kwargs_captured if kw.get("context_file")]
        assert len(ctx_files) >= 1


# ── B7: Session Inference ─────────────────────────────────────────────


class TestPipelineSessionInference:
    def test_session_inferred_from_plan_path_dir(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db", session_id="session-xyz789")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "session-xyz789"
        pp_dir.mkdir()

        def fake_loop(target, gwt_id, **kw):
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
            rc = main(["pipeline", str(project), "--db", str(db),
                        "--plan-path-dir", str(pp_dir), "--loop-only"])
        assert rc == 0

    def test_explicit_session_overrides_inference(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db", session_id="session-explicit")
        project = tmp_path / "proj"
        project.mkdir()
        pp_dir = tmp_path / "session-wrong"
        pp_dir.mkdir()

        def fake_loop(target, gwt_id, **kw):
            return 0

        with patch("registry.cli._run_loop_core", fake_loop):
            rc = main(["pipeline", str(project), "--db", str(db),
                        "--session", "session-explicit",
                        "--plan-path-dir", str(pp_dir), "--loop-only"])
        assert rc == 0


# ── B8: Exit Codes ────────────────────────────────────────────────────


class TestPipelineExitCodes:
    def test_all_pass_returns_0(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        def fake_loop(target, gwt_id, **kw):
            s = target / ".cw9" / "specs"
            s.mkdir(parents=True, exist_ok=True)
            (s / f"{gwt_id}.tla").write_text("---- MODULE T ----\n====")
            return 0

        def fake_bridge(target, gwt_id):
            bd = target / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(gwt_id)))
            return 0

        with patch("registry.cli._run_loop_core", fake_loop), \
             patch("registry.cli._run_bridge_core", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])
        assert rc == 0

    def test_loop_failure_returns_1(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()

        with patch("registry.cli._run_loop_core", return_value=1):
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

        with patch("registry.cli._run_bridge_core", return_value=1):
            rc = main(["pipeline", str(project),
                        "--bridge-only", "--gwt", "gwt-0001"])
        assert rc == 1

    def test_partial_failure_bridge_runs_for_passed_gwts(self, tmp_path):
        db = _make_cw7_db(tmp_path / "test.db")
        project = tmp_path / "proj"
        project.mkdir()
        bridge_gwts = []
        call_count = [0]

        def fake_loop(target, gwt_id, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                s = target / ".cw9" / "specs"
                s.mkdir(parents=True, exist_ok=True)
                (s / f"{gwt_id}.tla").write_text("---- MODULE T ----\n====")
                return 0
            return 1

        def fake_bridge(target, gwt_id):
            bridge_gwts.append(gwt_id)
            bd = target / ".cw9" / "bridge"
            bd.mkdir(parents=True, exist_ok=True)
            (bd / f"{gwt_id}_bridge_artifacts.json").write_text(
                json.dumps(_make_bridge_artifacts(gwt_id)))
            return 0

        with patch("registry.cli._run_loop_core", fake_loop), \
             patch("registry.cli._run_bridge_core", fake_bridge):
            rc = main(["pipeline", str(project),
                        "--db", str(db), "--session", "session-test"])

        assert len(bridge_gwts) == 1
        assert rc == 1

    def test_no_gwts_found_returns_1(self, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        main(["init", str(project)])
        rc = main(["pipeline", str(project), "--skip-setup"])
        assert rc == 1
