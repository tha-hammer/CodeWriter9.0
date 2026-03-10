"""Tests for the cw9 CLI (init, status)."""

import json
from pathlib import Path

import pytest

from registry.cli import main, ENGINE_ROOT


@pytest.fixture
def target_dir(tmp_path):
    """Create a temporary directory to use as an external project."""
    project = tmp_path / "myproject"
    project.mkdir()
    return project


class TestInit:
    def test_creates_cw9_directory(self, target_dir):
        rc = main(["init", str(target_dir)])
        assert rc == 0
        assert (target_dir / ".cw9").is_dir()

    def test_creates_subdirectories(self, target_dir):
        main(["init", str(target_dir)])
        for subdir in ("schema", "specs", "bridge", "sessions"):
            assert (target_dir / ".cw9" / subdir).is_dir()

    def test_writes_config_toml(self, target_dir):
        main(["init", str(target_dir)])
        config = (target_dir / ".cw9" / "config.toml").read_text()
        assert "[engine]" in config
        assert str(ENGINE_ROOT) in config

    def test_writes_empty_dag(self, target_dir):
        main(["init", str(target_dir)])
        dag = json.loads((target_dir / ".cw9" / "dag.json").read_text())
        assert dag["nodes"] == {}
        assert dag["edges"] == []

    def test_copies_starter_schemas(self, target_dir):
        main(["init", str(target_dir)])
        schema_dir = target_dir / ".cw9" / "schema"
        schemas = list(schema_dir.glob("*.json"))
        assert len(schemas) >= 4
        names = {s.name for s in schemas}
        assert "backend_schema.json" in names
        assert "frontend_schema.json" in names
        assert "middleware_schema.json" in names
        assert "shared_objects_schema.json" in names
        assert "resource_registry.generic.json" in names

    def test_refuses_reinit_without_force(self, target_dir):
        main(["init", str(target_dir)])
        rc = main(["init", str(target_dir)])
        assert rc == 1

    def test_force_reinit(self, target_dir):
        main(["init", str(target_dir)])
        rc = main(["init", str(target_dir), "--force"])
        assert rc == 0

    def test_nonexistent_dir_fails(self, tmp_path):
        rc = main(["init", str(tmp_path / "nonexistent")])
        assert rc == 1

    def test_does_not_overwrite_existing_schemas(self, target_dir):
        """If user already has schemas, init --force should not clobber them."""
        main(["init", str(target_dir)])
        # Write a custom schema
        custom = target_dir / ".cw9" / "schema" / "custom.json"
        custom.write_text('{"name": "custom"}')
        main(["init", str(target_dir), "--force"])
        # Custom schema should still be there
        assert custom.exists()
        assert json.loads(custom.read_text())["name"] == "custom"


class TestStatus:
    def test_status_after_init(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["status", str(target_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        assert str(target_dir) in out
        assert "DAG:" in out
        assert "Schemas:" in out

    def test_status_shows_schema_count(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["status", str(target_dir)])
        assert rc == 0
        out = capsys.readouterr().out
        # Should show 5 schemas (4 schema files + resource_registry)
        assert "Schemas: 5" in out

    def test_status_no_cw9_fails(self, target_dir):
        rc = main(["status", str(target_dir)])
        assert rc == 1

    def test_status_shows_zero_dag(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["status", str(target_dir)])
        out = capsys.readouterr().out
        assert "0 nodes" in out
        assert "0 edges" in out
