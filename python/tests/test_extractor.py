"""Tests for the schema edge extractor."""

import sys
from pathlib import Path

import pytest

from registry.extractor import SchemaExtractor
from registry.types import EdgeType


# The schema directory is at the project root
SCHEMA_DIR = Path(__file__).parent.parent.parent / "schema"


@pytest.fixture
def dag():
    """Extract the full DAG from the actual schema files."""
    extractor = SchemaExtractor(schema_dir=SCHEMA_DIR)
    return extractor.extract()


class TestExtraction:
    def test_loads_all_resources(self, dag):
        """All 41 resources from the registry should be loaded as nodes."""
        # 41 resources + 8 self-description nodes (req-0001, gwt-0001..0004, res-0001..0004)
        resource_nodes = [n for n in dag.nodes.values() if n.kind.value == "resource"]
        # 41 from registry + 4 res-* self-description
        assert len(resource_nodes) >= 41 + 4

    def test_self_description_nodes_exist(self, dag):
        """Phase 0 bootstrap: registry describes itself."""
        assert "req-0001" in dag.nodes
        assert "gwt-0001" in dag.nodes
        assert "gwt-0002" in dag.nodes
        assert "gwt-0003" in dag.nodes
        assert "gwt-0004" in dag.nodes
        assert "res-0001" in dag.nodes
        assert "res-0002" in dag.nodes
        assert "res-0003" in dag.nodes
        assert "res-0004" in dag.nodes

    def test_self_description_edges(self, dag):
        """req-0001 should decompose into gwt-0001..0004."""
        decompose_edges = [
            e for e in dag.edges
            if e.from_id == "req-0001" and e.edge_type == EdgeType.DECOMPOSES
        ]
        assert len(decompose_edges) == 4
        targets = {e.to_id for e in decompose_edges}
        assert targets == {"gwt-0001", "gwt-0002", "gwt-0003", "gwt-0004"}

    def test_has_edges(self, dag):
        """Extraction should produce edges."""
        assert dag.edge_count > 0

    def test_backend_service_calls_dao(self, dag):
        """services (db-h2s4) should call data_access_objects (db-d3w8)."""
        calls = [
            e for e in dag.edges
            if e.from_id == "db-h2s4" and e.to_id == "db-d3w8" and e.edge_type == EdgeType.CALLS
        ]
        assert len(calls) > 0

    def test_endpoint_handles_request_handler(self, dag):
        """endpoints (api-m5g7) should handle request_handlers (api-n8k2)."""
        handles = [
            e for e in dag.edges
            if e.from_id == "api-m5g7" and e.to_id == "api-n8k2" and e.edge_type == EdgeType.HANDLES
        ]
        assert len(handles) > 0

    def test_endpoint_filters(self, dag):
        """endpoints (api-m5g7) should filter through filters (api-p3e6)."""
        filters = [
            e for e in dag.edges
            if e.from_id == "api-m5g7" and e.to_id == "api-p3e6" and e.edge_type == EdgeType.FILTERS
        ]
        assert len(filters) > 0

    def test_request_handler_depends_on_service(self, dag):
        """request_handlers (api-n8k2) should depend on services (db-h2s4)."""
        deps = [
            e for e in dag.edges
            if e.from_id == "api-n8k2" and e.to_id == "db-h2s4" and e.edge_type == EdgeType.DEPENDS_ON
        ]
        assert len(deps) > 0

    def test_request_handler_calls_processor(self, dag):
        """request_handlers (api-n8k2) should call processors (db-b7r2)."""
        calls = [
            e for e in dag.edges
            if e.from_id == "api-n8k2" and e.to_id == "db-b7r2" and e.edge_type == EdgeType.CALLS
        ]
        assert len(calls) > 0

    def test_frontend_data_loader_references_endpoint(self, dag):
        """data_loaders (ui-y5t3) should reference endpoints (api-m5g7)."""
        refs = [
            e for e in dag.edges
            if e.from_id == "ui-y5t3" and e.to_id == "api-m5g7" and e.edge_type == EdgeType.REFERENCES
        ]
        assert len(refs) > 0

    def test_api_contract_references_endpoint(self, dag):
        """api_contracts (api-q7v1) should reference endpoints (api-m5g7)."""
        refs = [
            e for e in dag.edges
            if e.from_id == "api-q7v1" and e.to_id == "api-m5g7" and e.edge_type == EdgeType.REFERENCES
        ]
        assert len(refs) > 0

    def test_interceptor_implements_interface(self, dag):
        """interceptors (mq-s9b4) should implement interceptor_interfaces (mq-c1g5)."""
        impls = [
            e for e in dag.edges
            if e.from_id == "mq-s9b4" and e.to_id == "mq-c1g5"
            and e.edge_type == EdgeType.IMPLEMENTS_INTERFACE
        ]
        assert len(impls) > 0

    def test_middleware_chain_chains_interceptors(self, dag):
        """middleware process_chains (mq-u6j3) should chain interceptors (mq-s9b4)."""
        chains = [
            e for e in dag.edges
            if e.from_id == "mq-u6j3" and e.to_id == "mq-s9b4" and e.edge_type == EdgeType.CHAINS
        ]
        assert len(chains) > 0

    def test_transformer_transforms(self, dag):
        """transformers (cfg-h5v9) should transform from/to data_types (cfg-f7s8)."""
        from_edges = [
            e for e in dag.edges
            if e.from_id == "cfg-h5v9" and e.edge_type == EdgeType.TRANSFORMS_FROM
        ]
        to_edges = [
            e for e in dag.edges
            if e.from_id == "cfg-h5v9" and e.edge_type == EdgeType.TRANSFORMS_TO
        ]
        assert len(from_edges) > 0
        assert len(to_edges) > 0

    def test_module_contains_components(self, dag):
        """modules (ui-v3n6) should contain components (ui-w8p2)."""
        contains = [
            e for e in dag.edges
            if e.from_id == "ui-v3n6" and e.to_id == "ui-w8p2" and e.edge_type == EdgeType.CONTAINS
        ]
        assert len(contains) > 0

    def test_processor_imports_shared(self, dag):
        """processors (db-b7r2) should import shared modules."""
        imports = [
            e for e in dag.edges
            if e.from_id == "db-b7r2" and e.edge_type == EdgeType.IMPORTS
        ]
        assert len(imports) > 0

    def test_no_cycles(self, dag):
        """The extracted DAG should be acyclic."""
        # Verify closure is consistent (no self-references)
        for nid, reachable in dag.closure.items():
            assert nid not in reachable, f"Node {nid} can reach itself — cycle detected"


class TestQueryOnExtractedDag:
    def test_query_endpoint(self, dag):
        """Querying an endpoint should return handler and filter deps."""
        result = dag.query_relevant("api-m5g7")
        assert "api-n8k2" in result.transitive_deps  # handler
        assert "api-p3e6" in result.transitive_deps  # filter

    def test_query_self_description(self, dag):
        """Querying req-0001 should return all GWT and resource nodes."""
        result = dag.query_relevant("req-0001")
        for gwt in ("gwt-0001", "gwt-0002", "gwt-0003", "gwt-0004"):
            assert gwt in result.transitive_deps
        for res in ("res-0001", "res-0002", "res-0003", "res-0004"):
            assert res in result.transitive_deps

    def test_components_exist(self, dag):
        """There should be connected components."""
        assert dag.component_count > 0


class TestExtractedDagSerialization:
    def test_save_and_reload(self, dag, tmp_path):
        """The full extracted DAG should survive a JSON roundtrip."""
        path = tmp_path / "registry_dag.json"
        dag.save(path)

        restored = type(dag).load(path)
        assert restored.node_count == dag.node_count
        assert restored.edge_count == dag.edge_count
        assert restored.component_count == dag.component_count
