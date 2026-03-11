"""Integration tests for the external project pipeline.

Exercises SchemaExtractor + OneShotLoop on a minimal custom schema set
that is NOT a copy of CW9's own schemas. This validates:
  - SchemaExtractor works on novel schemas (different node/edge counts)
  - OneShotLoop initializes with an external ProjectContext
  - query_context + format_prompt_context produce valid output
"""

import json
from pathlib import Path

import pytest

from registry.context import ProjectContext
from registry.extractor import SchemaExtractor
from registry.one_shot_loop import OneShotLoop, query_context, format_prompt_context


ENGINE_ROOT = Path(__file__).parent.parent.parent


def _write_minimal_schemas(schema_dir: Path) -> None:
    """Write a small but valid schema set with known structure.

    This creates a 2-endpoint backend, 1 frontend module, no middleware,
    and a shared layer — intentionally different from CW9's own schemas.
    """
    schema_dir.mkdir(parents=True, exist_ok=True)

    # Resource registry using a subset of the canonical UUIDs from PATH_TO_RESOURCE.
    # The extractor resolves import paths (e.g. "shared/data_types") to UUIDs via a
    # hardcoded map, so we must use those same UUIDs here. This tests that an external
    # project with fewer resources still produces correct edges.
    registry = {
        "$schema": "resource_registry/v1",
        "description": "Minimal test registry — 6 of 41 canonical resources",
        "resources": {
            "db-b7r2": {
                "schema": "database",
                "name": "processor",
                "description": "User processor",
                "path": "backend/processors/UserProcessor",
                "source_schema": "backend_schema.json",
                "source_key": "processors.UserProcessor",
            },
            "api-m5g7": {
                "schema": "external_api",
                "name": "endpoint",
                "description": "User API endpoint",
                "path": "backend/endpoints/UserEndpoint",
                "source_schema": "backend_schema.json",
                "source_key": "endpoints.UserEndpoint",
            },
            "ui-v3n6": {
                "schema": "ui_state",
                "name": "module",
                "description": "User management UI",
                "path": "frontend/modules/UserView",
                "source_schema": "frontend_schema.json",
                "source_key": "modules.UserView",
            },
            "cfg-f7s8": {
                "schema": "configuration",
                "name": "data_type",
                "description": "User data type",
                "path": "shared/data_types/UserType",
                "source_schema": "shared_objects_schema.json",
                "source_key": "data_types.UserType",
            },
            "cfg-j9w2": {
                "schema": "configuration",
                "name": "shared_error_definitions",
                "description": "User error definitions",
                "path": "shared/error_definitions/UserError",
                "source_schema": "shared_objects_schema.json",
                "source_key": "error_definitions.UserError",
            },
            "cfg-b8m6": {
                "schema": "configuration",
                "name": "shared_utility",
                "description": "Validates user data",
                "path": "shared/utilities/UserValidator",
                "source_schema": "shared_objects_schema.json",
                "source_key": "utilities.UserValidator",
            },
        },
        "conditional_resources": {},
    }

    backend = {
        "name": "backend",
        "type": "directory",
        "processors": {
            "UserProcessor": {
                "function_id": "FUNC-001",
                "acceptance_criteria_id": "AC-001",
                "type": "module",
                "base_interface": "CoreProcessor",
                "exports": ["createUser", "getUser"],
                "imports": {
                    "internal": [],
                    "external": [],
                    "shared": [
                        {"path": "shared/data_types", "exports": ["UserType"]},
                        {"path": "shared/error_definitions", "exports": ["UserError"]},
                    ],
                },
                "dependencies": [],
                "description": "User CRUD processor",
                "path": "backend/processors/UserProcessor",
                "operations": {
                    "createUser": {
                        "function_id": "FUNC-001-01",
                        "acceptance_criteria_id": "AC-001-01",
                        "parameters": {"user": "shared/data_types/UserType"},
                        "returns": "shared/data_types/UserType",
                        "error_types": ["shared/error_definitions/UserError"],
                        "error_handling": "returnError",
                        "description": "Create a new user",
                    }
                },
            }
        },
        "endpoints": {
            "UserEndpoint": {
                "function_id": "FUNC-002",
                "acceptance_criteria_id": "AC-002",
                "path": "/api/users",
                "method": "POST",
                "description": "User API",
            }
        },
    }

    frontend = {
        "name": "frontend",
        "type": "directory",
        "modules": {
            "UserView": {
                "function_id": "FUNC-003",
                "acceptance_criteria_id": "AC-003",
                "type": "module",
                "base_interface": "UIElement",
                "exports": ["UserView"],
                "imports": {
                    "internal": [],
                    "external": [],
                    "backend": [
                        {"path": "backend/endpoints", "exports": ["UserEndpoint"]},
                    ],
                    "shared": [
                        {"path": "shared/data_types", "exports": ["UserType"]},
                    ],
                },
                "dependencies": [],
                "description": "User management view",
                "path": "frontend/modules/UserView",
                "components": [],
            }
        },
    }

    middleware = {
        "name": "middleware",
        "type": "directory",
        "interceptors": {},
    }

    shared = {
        "name": "shared",
        "type": "directory",
        "utilities": {
            "UserValidator": {
                "function_id": "FUNC-004",
                "acceptance_criteria_id": "AC-004",
                "type": "module",
                "base_interface": "GeneralUtility",
                "exports": ["validateUser"],
                "imports": {"internal": [], "external": []},
                "dependencies": [],
                "description": "Validates user data",
                "functions": {
                    "validateUser": {
                        "function_id": "FUNC-004-01",
                        "acceptance_criteria_id": "AC-004-01",
                        "parameters": {"user": "UserType"},
                        "returns": "boolean",
                        "error_types": [],
                        "error_handling": "returnFalse",
                        "description": "Check user validity",
                    }
                },
            }
        },
        "data_types": {
            "UserType": {
                "function_id": "FUNC-005",
                "acceptance_criteria_id": "AC-005",
                "base_type": "object",
                "description": "User data type",
            }
        },
        "error_definitions": {
            "UserError": {
                "message": "User operation failed",
                "code": "USR-001",
                "category": "validation",
                "description": "User validation error",
            }
        },
    }

    for name, data in [
        ("resource_registry.generic.json", registry),
        ("backend_schema.json", backend),
        ("frontend_schema.json", frontend),
        ("middleware_schema.json", middleware),
        ("shared_objects_schema.json", shared),
    ]:
        (schema_dir / name).write_text(json.dumps(data, indent=2))


@pytest.fixture
def external_project(tmp_path):
    """Create a minimal external project with custom schemas."""
    target = tmp_path / "user-service"
    target.mkdir()
    state = target / ".cw9"
    state.mkdir()
    for d in ("schema", "specs", "bridge", "sessions"):
        (state / d).mkdir()
    _write_minimal_schemas(state / "schema")
    return target


@pytest.fixture
def external_ctx(external_project):
    return ProjectContext.from_target(external_project, ENGINE_ROOT)


@pytest.fixture
def external_dag(external_ctx):
    return SchemaExtractor(schema_dir=external_ctx.schema_dir).extract()


class TestExternalExtraction:
    def test_node_count_differs_from_self_hosting(self, external_dag):
        """Custom schemas should produce a different DAG than CW9's own."""
        # 6 resource nodes from fixture's hand-crafted registry;
        # no self-description nodes (gated off for external projects)
        assert len(external_dag.nodes) == 6

    def test_edge_count_differs_from_self_hosting(self, external_dag):
        """Custom schemas should produce different edges."""
        # CW9 has 198 edges
        assert len(external_dag.edges) < 198
        assert len(external_dag.edges) > 0

    def test_resource_nodes_loaded(self, external_dag):
        """All 6 resources should be DAG nodes."""
        for uid in ("db-b7r2", "api-m5g7", "ui-v3n6", "cfg-f7s8", "cfg-j9w2", "cfg-b8m6"):
            assert uid in external_dag.nodes

    def test_import_edges_created(self, external_dag):
        """Backend processor imports shared types → edges should exist."""
        edges_from_processor = [e for e in external_dag.edges if e.from_id == "db-b7r2"]
        to_ids = {e.to_id for e in edges_from_processor}
        assert "cfg-f7s8" in to_ids  # shared/data_types
        assert "cfg-j9w2" in to_ids  # shared/error_definitions

    def test_frontend_imports_backend(self, external_dag):
        """Frontend module imports backend endpoint → edge should exist."""
        edges_from_frontend = [e for e in external_dag.edges if e.from_id == "ui-v3n6"]
        to_ids = {e.to_id for e in edges_from_frontend}
        assert "api-m5g7" in to_ids  # backend/endpoints

    def test_frontend_imports_shared(self, external_dag):
        edges_from_frontend = [e for e in external_dag.edges if e.from_id == "ui-v3n6"]
        to_ids = {e.to_id for e in edges_from_frontend}
        assert "cfg-f7s8" in to_ids  # shared/data_types

    def test_self_description_excluded_from_external(self, external_dag):
        """Self-description nodes should not appear in external project DAGs."""
        assert "req-0001" not in external_dag.nodes

    def test_impact_query(self, external_dag):
        """Changing shared/data_types should impact both processor and frontend."""
        result = external_dag.query_impact("cfg-f7s8")
        # affected may be node IDs (strings) or Node objects
        affected_ids = set()
        for n in result.affected:
            affected_ids.add(n.id if hasattr(n, "id") else n)
        assert "db-b7r2" in affected_ids
        assert "ui-v3n6" in affected_ids

    def test_subgraph_extraction(self, external_dag):
        """Subgraph around processor should include its shared deps."""
        result = external_dag.extract_subgraph("db-b7r2")
        # SubgraphResult.nodes may be node IDs (strings) or Node objects
        node_ids = set()
        for n in result.nodes:
            node_ids.add(n.id if hasattr(n, "id") else n)
        assert "db-b7r2" in node_ids
        assert "cfg-f7s8" in node_ids  # shared dep
        assert "cfg-j9w2" in node_ids  # shared dep


class TestExternalOneShotLoop:
    def test_loop_initializes(self, external_dag, external_ctx):
        """OneShotLoop should accept external ProjectContext."""
        loop = OneShotLoop(dag=external_dag, ctx=external_ctx)
        assert loop._tools_dir == ENGINE_ROOT / "tools"

    def test_query_context_on_resource(self, external_dag):
        """query_context should work on resource nodes."""
        bundle = query_context(external_dag, "db-b7r2")
        assert bundle.behavior_id == "db-b7r2"

    def test_format_prompt_context(self, external_dag):
        """format_prompt_context should produce non-empty text."""
        bundle = query_context(external_dag, "db-b7r2")
        text = format_prompt_context(bundle)
        assert len(text) > 0
        assert "db-b7r2" in text

    def test_template_dir_accessible(self, external_ctx):
        """Engine templates should be accessible from external context."""
        assert external_ctx.template_dir.is_dir()
        # The PlusCal state machine template should exist
        templates = list(external_ctx.template_dir.glob("*.tla"))
        assert len(templates) > 0
