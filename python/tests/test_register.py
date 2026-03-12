"""Tests for cw9 register subcommand and criterion bindings."""

import io
import json
from pathlib import Path

import pytest

from registry.bindings import load_bindings, save_bindings
from registry.cli import main
from registry.dag import RegistryDag


@pytest.fixture
def state_root(tmp_path):
    sr = tmp_path / ".cw9"
    sr.mkdir()
    return sr


@pytest.fixture
def project(tmp_path):
    """Initialized CW9 project with extracted DAG."""
    project = tmp_path / "proj"
    project.mkdir()
    main(["init", str(project)])
    main(["extract", str(project)])
    return project


# ── Phase 1: Bindings file persistence ──────────────────────────


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


# ── Phase 3: Register subcommand ────────────────────────────────


class TestRegister:
    def _run(self, project, payload, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        stdout = io.StringIO()
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

        # Count GWT nodes after first registration
        dag1 = RegistryDag.load(project / ".cw9" / "dag.json")
        count_after_first = len([n for n in dag1.nodes if n.startswith("gwt-")])

        rc2, out2 = self._run(project, payload, monkeypatch)
        assert rc2 == 0
        assert out2["gwts"][0]["gwt_id"] == gwt_id

        dag2 = RegistryDag.load(project / ".cw9" / "dag.json")
        count_after_second = len([n for n in dag2.nodes if n.startswith("gwt-")])
        assert count_after_second == count_after_first  # no new nodes created

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


# ── Phase 4: End-to-end integration ─────────────────────────────


class TestRegisterE2E:
    def _run(self, project, payload, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)
        rc = main(["register", str(project)])
        output = stdout.getvalue()
        return rc, json.loads(output) if output.strip() else None

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

        # gwt2 has no parent_req — no DECOMPOSES edge
        decompose_edges_2 = [e for e in dag.edges
                              if e.from_id == req_id and e.to_id == gwt2_id]
        assert len(decompose_edges_2) == 0

        # Second call — idempotent
        rc2, out2 = self._run(project, payload, monkeypatch)
        assert rc2 == 0
        assert out2 == out1  # exact same output

        # DAG node count unchanged after idempotent retry
        dag2 = RegistryDag.load(project / ".cw9" / "dag.json")
        gwt_count_2 = len([n for n in dag2.nodes if n.startswith("gwt-")])
        req_count_2 = len([n for n in dag2.nodes if n.startswith("req-")])
        gwt_count_1 = len([n for n in dag.nodes if n.startswith("gwt-")])
        req_count_1 = len([n for n in dag.nodes if n.startswith("req-")])
        assert gwt_count_2 == gwt_count_1
        assert req_count_2 == req_count_1
