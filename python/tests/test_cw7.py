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
        assert result == {1: 1001, 2: 1002}


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
