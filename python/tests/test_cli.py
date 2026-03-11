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


class TestExtract:
    def test_extract_builds_dag(self, target_dir):
        main(["init", str(target_dir)])
        rc = main(["extract", str(target_dir)])
        assert rc == 0
        dag_data = json.loads((target_dir / ".cw9" / "dag.json").read_text())
        # External projects start with empty templates — 0 nodes is correct
        assert isinstance(dag_data["nodes"], dict)
        assert isinstance(dag_data["edges"], list)

    def test_extract_no_cw9_fails(self, target_dir):
        rc = main(["extract", str(target_dir)])
        assert rc == 1

    def test_extract_prints_diff_on_reextract(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])
        capsys.readouterr()
        main(["extract", str(target_dir)])
        out = capsys.readouterr().out
        assert "DAG updated:" in out
        # On re-extract with no changes, delta is 0
        assert "(0)" in out

    def test_extract_status_shows_dag(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])
        main(["status", str(target_dir)])
        out = capsys.readouterr().out
        # External project with empty templates produces 0 nodes
        assert "DAG:" in out

    def test_extract_preserves_registered_gwts(self, target_dir, capsys):
        """register_gwt() -> extract -> GWT survives."""
        from registry.dag import RegistryDag
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])

        # Register a GWT into the existing DAG
        dag_path = target_dir / ".cw9" / "dag.json"
        dag = RegistryDag.load(dag_path)
        gwt_id = dag.register_gwt("user exists", "login", "dashboard")
        dag.save(dag_path)

        # Re-extract — should preserve the registered GWT
        main(["extract", str(target_dir)])
        out = capsys.readouterr().out
        assert "preserved" in out.lower()

        dag2 = RegistryDag.load(dag_path)
        assert gwt_id in dag2.nodes
        assert dag2.nodes[gwt_id].given == "user exists"

    def test_extract_preserves_registered_req_edges(self, target_dir):
        """Registered requirement + GWT + edge survives re-extract."""
        from registry.dag import RegistryDag
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])

        dag_path = target_dir / ".cw9" / "dag.json"
        dag = RegistryDag.load(dag_path)
        req_id = dag.register_requirement("External auth requirement")
        gwt_id = dag.register_gwt("user", "login", "dash", parent_req=req_id)
        dag.save(dag_path)

        # Re-extract
        main(["extract", str(target_dir)])
        dag2 = RegistryDag.load(dag_path)
        assert req_id in dag2.nodes
        assert gwt_id in dag2.nodes
        edges = [e for e in dag2.edges if e.from_id == req_id and e.to_id == gwt_id]
        assert len(edges) == 1


# A minimal TLA+ spec for bridge testing
_MINIMAL_TLA_SPEC = """\
---- MODULE TestSpec ----
EXTENDS Naturals
VARIABLE x

Init == x = 0
Next == x' = x + 1

Spec == Init /\\ [][Next]_x

ValidState == x >= 0
====
"""


class TestLoop:
    def test_loop_no_cw9_fails(self, target_dir):
        rc = main(["loop", "gwt-0001", str(target_dir)])
        assert rc == 1

    def test_loop_missing_gwt_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])
        rc = main(["loop", "gwt-nonexistent", str(target_dir)])
        assert rc == 1


class TestSimulationTraceParser:
    """v5: Tests for parse_simulation_traces()."""

    def test_parses_single_trace(self):
        from registry.one_shot_loop import parse_simulation_traces
        raw = (
            "State 1: <Init>\n"
            "/\\ current_state = \"idle\"\n"
            "/\\ candidates = {}\n"
            "\n"
            "State 2: <SelectNode>\n"
            "/\\ current_state = \"propagating\"\n"
            "/\\ candidates = {\"a\"}\n"
        )
        traces = parse_simulation_traces(raw)
        assert len(traces) == 1
        assert len(traces[0]) == 2
        assert traces[0][0]["label"] == "Init"
        assert traces[0][0]["vars"]["current_state"] == '"idle"'
        assert traces[0][1]["label"] == "SelectNode"

    def test_parses_multiple_traces(self):
        from registry.one_shot_loop import parse_simulation_traces
        raw = (
            "State 1: <Init>\n"
            "/\\ x = 0\n"
            "State 2: <Step>\n"
            "/\\ x = 1\n"
            "\n"
            "State 1: <Init>\n"
            "/\\ x = 0\n"
            "State 2: <Step>\n"
            "/\\ x = 2\n"
            "State 3: <Done>\n"
            "/\\ x = 3\n"
        )
        traces = parse_simulation_traces(raw)
        assert len(traces) == 2
        assert len(traces[0]) == 2
        assert len(traces[1]) == 3
        assert traces[1][2]["vars"]["x"] == "3"

    def test_empty_output_returns_empty(self):
        from registry.one_shot_loop import parse_simulation_traces
        assert parse_simulation_traces("") == []
        assert parse_simulation_traces("Model checking completed.\n") == []


class TestBridge:
    def test_bridge_no_cw9_fails(self, target_dir):
        rc = main(["bridge", "gwt-0001", str(target_dir)])
        assert rc == 1

    def test_bridge_no_spec_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["bridge", "gwt-0001", str(target_dir)])
        assert rc == 1
        assert "no verified spec" in capsys.readouterr().err.lower()

    def test_bridge_with_spec(self, target_dir):
        main(["init", str(target_dir)])
        spec_dir = target_dir / ".cw9" / "specs"
        spec_dir.mkdir(exist_ok=True)
        spec_path = spec_dir / "gwt-test.tla"
        spec_path.write_text(_MINIMAL_TLA_SPEC)
        rc = main(["bridge", "gwt-test", str(target_dir)])
        assert rc == 0
        artifact_path = target_dir / ".cw9" / "bridge" / "gwt-test_bridge_artifacts.json"
        assert artifact_path.exists()
        data = json.loads(artifact_path.read_text())
        assert data["gwt_id"] == "gwt-test"


class TestGenTests:
    def test_gen_tests_no_artifacts_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["gen-tests", "gwt-0001", str(target_dir)])
        assert rc == 1
        assert "no bridge artifacts" in capsys.readouterr().err.lower()

    def test_verify_catches_syntax_error(self, tmp_path):
        from registry.test_gen_loop import verify_test_file
        bad = tmp_path / "test_bad.py"
        bad.write_text("def test_broken(:\n    pass\n")
        result = verify_test_file(bad, tmp_path)
        assert not result.passed
        assert result.stage == "compile"
        assert "SyntaxError" in result.errors[0]

    def test_verify_passes_valid_tests(self, tmp_path):
        from registry.test_gen_loop import verify_test_file
        good = tmp_path / "test_good.py"
        good.write_text("def test_ok(): assert True\n")
        result = verify_test_file(good, tmp_path)
        assert result.passed
        assert result.stage == "run"

    def test_verify_catches_failing_tests(self, tmp_path):
        from registry.test_gen_loop import verify_test_file
        fail = tmp_path / "test_fail.py"
        fail.write_text("def test_bad(): assert False\n")
        result = verify_test_file(fail, tmp_path)
        assert not result.passed
        assert result.stage == "run"

    def test_build_compiler_hints(self):
        from registry.test_gen_loop import build_compiler_hints
        artifacts = {
            "verifiers": {
                "NoFalsePositives": {
                    "conditions": ["\\A t \\in affected : t \\in candidates"],
                    "applies_to": ["affected", "candidates"],
                },
            },
        }
        hints = build_compiler_hints(artifacts)
        assert "NoFalsePositives" in hints
        assert "all(" in hints["NoFalsePositives"]["target_expr"]

    def test_prompt_includes_compiler_hints(self):
        from registry.test_gen_loop import TestGenContext, build_test_plan_prompt
        ctx = TestGenContext(
            gwt_id="gwt-test",
            gwt_text={"given": "a DAG", "when": "node changes", "then": "tests found"},
            module_name="change_propagation",
            bridge_artifacts={
                "verifiers": {
                    "NoFalsePositives": {
                        "conditions": ["\\A t \\in affected : t \\in candidates"],
                        "applies_to": ["affected", "candidates"],
                    },
                },
            },
            compiler_hints={
                "NoFalsePositives": {
                    "target_expr": "all(t in candidates for t in affected)",
                    "original_tla": "\\A t \\in affected : t \\in candidates",
                    "variables_used": ["affected", "candidates"],
                },
            },
            api_context="from registry.dag import RegistryDag\n",
            test_scenarios=[],
            simulation_traces=[],
            output_dir=Path("/tmp"),
            source_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        assert "NoFalsePositives" in prompt
        assert "all(t in candidates for t in affected)" in prompt
        assert "need binding to real API calls" in prompt

    def test_prompt_leads_with_simulation_traces(self):
        """v5: Simulation traces are the PRIMARY context in the prompt."""
        from registry.test_gen_loop import TestGenContext, build_test_plan_prompt
        ctx = TestGenContext(
            gwt_id="gwt-test",
            gwt_text={"given": "a DAG", "when": "node changes", "then": "tests found"},
            module_name="change_propagation",
            bridge_artifacts={
                "verifiers": {
                    "NoFalsePositives": {
                        "conditions": ["\\A t \\in affected : t \\in candidates"],
                        "applies_to": ["affected", "candidates"],
                    },
                },
            },
            compiler_hints={},
            api_context="from registry.dag import RegistryDag\n",
            test_scenarios=[],
            simulation_traces=[
                [
                    {"state_num": 1, "label": "Init",
                     "vars": {"nodes": "{a,b,c}", "edges": "{a->b, b->c}",
                              "test_artifacts": "{a: test_a.py}"}},
                    {"state_num": 2, "label": "QueryAffected",
                     "vars": {"affected": "{test_a.py}", "start": "c"}},
                ],
            ],
            output_dir=Path("/tmp"),
            source_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        traces_pos = prompt.find("Concrete Verified Scenarios")
        api_pos = prompt.find("Available Python API")
        assert traces_pos != -1, "Simulation traces section missing from prompt"
        assert api_pos != -1, "API section missing from prompt"
        assert traces_pos < api_pos, "Traces must appear before API context"
        assert "Init" in prompt
        assert "QueryAffected" in prompt
        assert "Translate each trace" in prompt
        assert "Structural Patterns" in prompt

    def test_prompt_falls_back_without_traces(self):
        """v5: Without simulation traces, prompt falls back to v4 behavior."""
        from registry.test_gen_loop import TestGenContext, build_test_plan_prompt
        ctx = TestGenContext(
            gwt_id="gwt-test",
            gwt_text={"given": "g", "when": "w", "then": "t"},
            module_name="mod",
            bridge_artifacts={"verifiers": {}},
            compiler_hints={},
            api_context="# no api\n",
            test_scenarios=[],
            simulation_traces=[],
            output_dir=Path("/tmp"),
            source_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        assert "Concrete Verified Scenarios" not in prompt
        assert "Fixtures" in prompt

    def test_extract_code_strips_fences(self):
        from registry.test_gen_loop import _extract_code_from_response
        response = "```python\ndef test_x(): pass\n```"
        assert _extract_code_from_response(response) == "def test_x(): pass"

    def test_extract_code_bare_python(self):
        from registry.test_gen_loop import _extract_code_from_response
        response = "def test_x(): pass"
        assert _extract_code_from_response(response) == "def test_x(): pass"


class TestTest:
    def test_test_no_generated_tests_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["test", str(target_dir)])
        assert rc == 1
        assert "no generated tests" in capsys.readouterr().err.lower()

    def test_test_runs_generated_files(self, target_dir):
        main(["init", str(target_dir)])
        test_dir = target_dir / "tests" / "generated"
        test_dir.mkdir(parents=True)
        (test_dir / "test_sample.py").write_text("def test_pass(): assert True\n")
        rc = main(["test", str(target_dir)])
        assert rc == 0
