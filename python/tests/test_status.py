"""Tests for cw9 status — pipeline progress reporting."""

import json
import tempfile
from pathlib import Path

import pytest

from registry.status import GWTStatus, ProjectStatus, gather_status


class TestGWTStatus:
    """GWTStatus derivation from on-disk artifacts."""

    def _make_project(self, tmp: Path, gwt_ids: list[str]):
        """Create a minimal .cw9 directory with GWT nodes in dag.json."""
        state = tmp / ".cw9"
        for d in ("schema", "specs", "sessions", "bridge"):
            (state / d).mkdir(parents=True)
        nodes = {gid: {"kind": "gwt"} for gid in gwt_ids}
        (state / "dag.json").write_text(json.dumps({
            "nodes": nodes, "edges": [], "test_artifacts": {},
        }))
        return state

    def test_pending_no_attempts(self, tmp_path):
        """GWT with no attempt files and no spec → pending."""
        self._make_project(tmp_path, ["gwt-0001"])
        status = gather_status(tmp_path)
        gwt = status.gwts["gwt-0001"]
        assert gwt.result == "pending"
        assert gwt.attempts == 0
        assert gwt.bridge_done is False

    def test_pass_with_result_json(self, tmp_path):
        """GWT with result.json showing pass → pass."""
        state = self._make_project(tmp_path, ["gwt-0001"])
        (state / "sessions" / "gwt-0001_result.json").write_text(
            json.dumps({"gwt_id": "gwt-0001", "result": "pass", "attempts": 2, "error": None})
        )
        (state / "specs" / "gwt-0001.tla").write_text("MODULE")
        status = gather_status(tmp_path)
        gwt = status.gwts["gwt-0001"]
        assert gwt.result == "pass"
        assert gwt.attempts == 2

    def test_fail_with_result_json(self, tmp_path):
        """GWT with result.json showing fail → fail."""
        state = self._make_project(tmp_path, ["gwt-0001"])
        (state / "sessions" / "gwt-0001_result.json").write_text(
            json.dumps({
                "gwt_id": "gwt-0001", "result": "fail",
                "attempts": 8, "error": "Exhausted 8 attempts",
            })
        )
        status = gather_status(tmp_path)
        gwt = status.gwts["gwt-0001"]
        assert gwt.result == "fail"
        assert gwt.attempts == 8
        assert gwt.error == "Exhausted 8 attempts"

    def test_in_progress_has_attempts_but_no_result(self, tmp_path):
        """GWT with attempt files but no result.json → in_progress."""
        state = self._make_project(tmp_path, ["gwt-0001"])
        (state / "sessions" / "gwt-0001_attempt1.txt").write_text("response")
        (state / "sessions" / "gwt-0001_attempt2.txt").write_text("response")
        status = gather_status(tmp_path)
        gwt = status.gwts["gwt-0001"]
        assert gwt.result == "in_progress"
        assert gwt.attempts == 2

    def test_bridge_done(self, tmp_path):
        """GWT with bridge artifacts → bridge_done=True."""
        state = self._make_project(tmp_path, ["gwt-0001"])
        (state / "sessions" / "gwt-0001_result.json").write_text(
            json.dumps({"gwt_id": "gwt-0001", "result": "pass", "attempts": 1, "error": None})
        )
        (state / "specs" / "gwt-0001.tla").write_text("MODULE")
        (state / "bridge" / "gwt-0001_bridge_artifacts.json").write_text("{}")
        status = gather_status(tmp_path)
        assert status.gwts["gwt-0001"].bridge_done is True


class TestProjectStatus:
    """Aggregate scoreboard from per-GWT statuses."""

    def _make_project(self, tmp: Path, gwt_ids: list[str]):
        state = tmp / ".cw9"
        for d in ("schema", "specs", "sessions", "bridge"):
            (state / d).mkdir(parents=True)
        nodes = {gid: {"kind": "gwt"} for gid in gwt_ids}
        (state / "dag.json").write_text(json.dumps({
            "nodes": nodes, "edges": [], "test_artifacts": {},
        }))
        return state

    def test_scoreboard_counts(self, tmp_path):
        """Scoreboard tallies verified/failed/pending/in_progress correctly."""
        state = self._make_project(tmp_path, [
            "gwt-0001", "gwt-0002", "gwt-0003", "gwt-0004",
        ])
        # gwt-0001: pass
        (state / "sessions" / "gwt-0001_result.json").write_text(
            json.dumps({"gwt_id": "gwt-0001", "result": "pass", "attempts": 1, "error": None})
        )
        (state / "specs" / "gwt-0001.tla").write_text("MODULE")
        # gwt-0002: fail
        (state / "sessions" / "gwt-0002_result.json").write_text(
            json.dumps({"gwt_id": "gwt-0002", "result": "fail", "attempts": 8, "error": "err"})
        )
        # gwt-0003: in_progress (has attempts, no result)
        (state / "sessions" / "gwt-0003_attempt1.txt").write_text("resp")
        # gwt-0004: pending (nothing)

        status = gather_status(tmp_path)
        assert status.verified == 1
        assert status.failed == 1
        assert status.in_progress == 1
        assert status.pending == 1
        assert status.total == 4

    def test_bridge_count(self, tmp_path):
        """bridge_complete counts only GWTs with bridge artifacts."""
        state = self._make_project(tmp_path, ["gwt-0001", "gwt-0002"])
        for gid in ["gwt-0001", "gwt-0002"]:
            (state / "sessions" / f"{gid}_result.json").write_text(
                json.dumps({"gwt_id": gid, "result": "pass", "attempts": 1, "error": None})
            )
            (state / "specs" / f"{gid}.tla").write_text("MODULE")
        (state / "bridge" / "gwt-0001_bridge_artifacts.json").write_text("{}")
        status = gather_status(tmp_path)
        assert status.bridge_complete == 1
        assert status.verified == 2

    def test_to_dict_is_json_serializable(self, tmp_path):
        """ProjectStatus.to_dict() must be JSON-serializable."""
        self._make_project(tmp_path, ["gwt-0001"])
        status = gather_status(tmp_path)
        d = status.to_dict()
        serialized = json.dumps(d)
        roundtrip = json.loads(serialized)
        assert roundtrip["total"] == 1
        assert "gwt-0001" in roundtrip["gwts"]

    def test_no_cw9_dir_raises(self, tmp_path):
        """gather_status raises FileNotFoundError if .cw9/ missing."""
        with pytest.raises(FileNotFoundError):
            gather_status(tmp_path)

    def test_non_gwt_nodes_excluded(self, tmp_path):
        """Only gwt-* nodes are counted, not req-* or other node types."""
        state = self._make_project(tmp_path, ["gwt-0001"])
        dag_path = state / "dag.json"
        dag = json.loads(dag_path.read_text())
        dag["nodes"]["req-0001"] = {"kind": "requirement"}
        dag_path.write_text(json.dumps(dag))
        status = gather_status(tmp_path)
        assert status.total == 1
        assert "req-0001" not in status.gwts


class TestRunLoopResultFile:
    """run_loop should write a result JSON at completion."""

    def test_result_json_written_on_pass(self, tmp_path):
        """Result file written with result=pass when TLC verifies."""
        result_path = tmp_path / "sessions" / "gwt-0001_result.json"
        # We test the write_result_file helper directly
        from registry.status import write_result_file
        write_result_file(
            session_dir=tmp_path / "sessions",
            gwt_id="gwt-0001",
            result="pass",
            attempts=3,
            error=None,
        )
        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["result"] == "pass"
        assert data["attempts"] == 3
        assert data["error"] is None

    def test_result_json_written_on_fail(self, tmp_path):
        """Result file written with result=fail when retries exhausted."""
        from registry.status import write_result_file
        write_result_file(
            session_dir=tmp_path / "sessions",
            gwt_id="gwt-0001",
            result="fail",
            attempts=8,
            error="Exhausted 8 attempts",
        )
        result_path = tmp_path / "sessions" / "gwt-0001_result.json"
        data = json.loads(result_path.read_text())
        assert data["result"] == "fail"
        assert data["error"] == "Exhausted 8 attempts"
