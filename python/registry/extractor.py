"""Extract dependency edges from the 4 schema files into the registry DAG.

This implements Phase 0 of BOOTSTRAP.md: "Extract the Graph."
The extraction map is defined in BOOTSTRAP.md under "Schema-to-Registry Edge Map".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


# Maps (source_schema, source_key_prefix) -> resource UUID from resource_registry.generic.json
# These are the resource TYPE UUIDs, not instance UUIDs.
RESOURCE_TYPE_MAP: dict[tuple[str, str], str] = {
    # Backend
    ("backend_schema.json", "processors"): "db-b7r2",
    ("backend_schema.json", "data_access_objects"): "db-d3w8",
    ("backend_schema.json", "data_structures"): "db-f8n5",
    ("backend_schema.json", "services"): "db-h2s4",
    ("backend_schema.json", "verifiers"): "db-j6x9",
    ("backend_schema.json", "error_definitions"): "db-l1c3",
    ("backend_schema.json", "endpoints"): "api-m5g7",
    ("backend_schema.json", "request_handlers"): "api-n8k2",
    ("backend_schema.json", "filters"): "api-p3e6",
    ("backend_schema.json", "process_chains"): "mq-r4z8",
    ("backend_schema.json", "settings"): "cfg-m2z6",
    ("backend_schema.json", "logging"): "cfg-q9c5",
    # Frontend
    ("frontend_schema.json", "modules"): "ui-v3n6",
    ("frontend_schema.json", "components"): "ui-w8p2",
    ("frontend_schema.json", "access_controls"): "ui-x1r9",
    ("frontend_schema.json", "data_loaders"): "ui-y5t3",
    ("frontend_schema.json", "utility_modules"): "ui-z2w7",
    ("frontend_schema.json", "api_contracts"): "api-q7v1",
    ("frontend_schema.json", "verifiers"): "ui-a4y1",
    ("frontend_schema.json", "settings"): "cfg-n7a3",
    ("frontend_schema.json", "logging"): "cfg-r3d7",
    # Middleware
    ("middleware_schema.json", "interceptors"): "mq-s9b4",
    ("middleware_schema.json", "execution_patterns"): "mq-t2f7",
    ("middleware_schema.json", "process_chains"): "mq-u6j3",
    # Shared
    ("shared_objects_schema.json", "utilities"): "cfg-b8m6",
    ("shared_objects_schema.json", "common_structures"): "cfg-d2q3",
    ("shared_objects_schema.json", "data_types"): "cfg-f7s8",
    ("shared_objects_schema.json", "verifiers"): "cfg-g1u4",
    ("shared_objects_schema.json", "transformers"): "cfg-h5v9",
    ("shared_objects_schema.json", "error_definitions"): "cfg-j9w2",
    ("shared_objects_schema.json", "constants"): "cfg-k3x7",
    ("shared_objects_schema.json", "settings"): "cfg-l8y1",
    ("shared_objects_schema.json", "logging"): "cfg-p4b8",
    ("shared_objects_schema.json", "testing"): "cfg-s6e2",
    ("shared_objects_schema.json", "interceptor_interfaces"): "mq-c1g5",
}

# Maps import path prefixes to resource type UUIDs
PATH_TO_RESOURCE: dict[str, str] = {
    "backend/processors": "db-b7r2",
    "backend/data_access_objects": "db-d3w8",
    "backend/data_structures": "db-f8n5",
    "backend/services": "db-h2s4",
    "backend/verifiers": "db-j6x9",
    "backend/error_definitions": "db-l1c3",
    "backend/endpoints": "api-m5g7",
    "backend/request_handlers": "api-n8k2",
    "backend/filters": "api-p3e6",
    "backend/process_chains": "mq-r4z8",
    "backend/settings": "cfg-m2z6",
    "frontend/modules": "ui-v3n6",
    "frontend/components": "ui-w8p2",
    "frontend/access_controls": "ui-x1r9",
    "frontend/data_loaders": "ui-y5t3",
    "frontend/utility_modules": "ui-z2w7",
    "frontend/api_contracts": "api-q7v1",
    "frontend/verifiers": "ui-a4y1",
    "frontend/settings": "cfg-n7a3",
    "frontend/templates": "ui-w8p2",  # templates belong to components
    "middleware/interceptors": "mq-s9b4",
    "middleware/execution_patterns": "mq-t2f7",
    "middleware/process_chains": "mq-u6j3",
    "shared/utilities": "cfg-b8m6",
    "shared/common_structures": "cfg-d2q3",
    "shared/data_types": "cfg-f7s8",
    "shared/verifiers": "cfg-g1u4",
    "shared/transformers": "cfg-h5v9",
    "shared/error_definitions": "cfg-j9w2",
    "shared/constants": "cfg-k3x7",
    "shared/settings": "cfg-l8y1",
    "shared/logging": "cfg-p4b8",
    "shared/testing": "cfg-s6e2",
    "shared/interceptor_interfaces": "mq-c1g5",
}


def _resolve_path(path: str) -> str | None:
    """Resolve an import path like 'backend/other_module' or 'shared/data_types' to a resource UUID."""
    # Try exact match first
    if path in PATH_TO_RESOURCE:
        return PATH_TO_RESOURCE[path]
    # Try prefix match (e.g. 'backend/endpoints/EndpointName' -> 'backend/endpoints')
    for prefix, uuid in sorted(PATH_TO_RESOURCE.items(), key=lambda x: -len(x[0])):
        if path.startswith(prefix):
            return uuid
    return None


def _resolve_call_target(call_ref: str, schema_name: str) -> str | None:
    """Resolve a call reference like 'DataAccessObjectName.functionName' to a resource UUID.

    In backend_schema:
    - services.functions.calls -> 'DAOName.funcName' targets data_access_objects
    - request_handlers.functions.operation -> 'ProcessorName.opName' targets processors
    """
    # The call target is the part before the dot
    target_name = call_ref.split(".")[0] if "." in call_ref else call_ref

    # In service calls, the target is a DAO
    if schema_name == "backend_schema.json":
        # Could be DAO or processor depending on context - caller disambiguates
        pass

    return None  # Caller handles disambiguation


class SchemaExtractor:
    """Extracts dependency edges from the 4 schema files into a RegistryDag.

    Usage:
        extractor = SchemaExtractor(schema_dir="schema/")
        dag = extractor.extract()
    """

    def __init__(self, schema_dir: str | Path, registry_path: str | Path | None = None):
        self.schema_dir = Path(schema_dir)
        self.registry_path = Path(registry_path) if registry_path else self.schema_dir / "resource_registry.generic.json"

    def extract(self) -> RegistryDag:
        """Run the full extraction pipeline: load registry, load schemas, extract edges."""
        dag = RegistryDag()

        # Step 1: Load existing resources as nodes
        registry = self._load_json(self.registry_path)
        self._load_resources(dag, registry)

        # Step 2: Extract edges from each schema file
        for schema_file in [
            "backend_schema.json",
            "frontend_schema.json",
            "middleware_schema.json",
            "shared_objects_schema.json",
        ]:
            path = self.schema_dir / schema_file
            if path.exists():
                schema = self._load_json(path)
                self._extract_schema_edges(dag, schema, schema_file)

        # Step 3: Self-describe the registry (Phase 0 bootstrap act)
        self._self_describe(dag)

        return dag

    def _load_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text())

    def _load_resources(self, dag: RegistryDag, registry: dict[str, Any]) -> None:
        """Load all resources from resource_registry.generic.json as DAG nodes."""
        for section in ("resources", "conditional_resources"):
            for uid, res in registry.get(section, {}).items():
                node = Node(
                    id=uid,
                    kind=NodeKind.RESOURCE,
                    name=res.get("name", ""),
                    description=res.get("description", ""),
                    schema=res.get("schema"),
                    path=res.get("path"),
                    source_schema=res.get("source_schema"),
                    source_key=res.get("source_key"),
                )
                dag.add_node(node)

    def _extract_schema_edges(self, dag: RegistryDag, schema: dict[str, Any], schema_file: str) -> None:
        """Extract edges from a single schema file."""
        if schema_file == "backend_schema.json":
            self._extract_backend(dag, schema)
        elif schema_file == "frontend_schema.json":
            self._extract_frontend(dag, schema)
        elif schema_file == "middleware_schema.json":
            self._extract_middleware(dag, schema)
        elif schema_file == "shared_objects_schema.json":
            self._extract_shared(dag, schema)

    def _add_edge_safe(self, dag: RegistryDag, from_id: str, to_id: str, edge_type: EdgeType) -> None:
        """Add an edge, silently skipping if nodes don't exist or it would create a cycle."""
        if from_id not in dag.nodes or to_id not in dag.nodes:
            return
        if from_id == to_id:
            return
        try:
            dag.add_edge(Edge(from_id=from_id, to_id=to_id, edge_type=edge_type))
        except Exception:
            pass  # Skip cycles or duplicates

    def _extract_imports(self, dag: RegistryDag, from_id: str, imports: dict[str, Any]) -> None:
        """Extract edges from an imports block (internal, external, shared, backend)."""
        for category in ("internal", "shared", "backend"):
            for imp in imports.get(category, []):
                path = imp.get("path", "")
                target = _resolve_path(path)
                if target:
                    self._add_edge_safe(dag, from_id, target, EdgeType.IMPORTS)

    # ── Backend extraction ──

    def _extract_backend(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        src = "db-b7r2"  # processor

        # processors.imports -> imports edges
        for _name, proc in schema.get("processors", {}).items():
            if isinstance(proc, dict) and "imports" in proc:
                self._extract_imports(dag, src, proc["imports"])
            # processors.dependencies -> depends_on (named, can't resolve to UUID without instances)

        # services.functions.calls -> calls DAO
        svc = "db-h2s4"
        dao = "db-d3w8"
        for _name, service in schema.get("services", {}).items():
            if not isinstance(service, dict):
                continue
            for _fname, func in service.get("functions", {}).items():
                if isinstance(func, dict):
                    for call in func.get("calls", []):
                        # calls format: "DataAccessObjectName.functionName"
                        self._add_edge_safe(dag, svc, dao, EdgeType.CALLS)

        # endpoints.handler -> handles request_handler
        ep = "api-m5g7"
        rh = "api-n8k2"
        flt = "api-p3e6"
        for _name, endpoint in schema.get("endpoints", {}).items():
            if not isinstance(endpoint, dict):
                continue
            if "handler" in endpoint:
                self._add_edge_safe(dag, ep, rh, EdgeType.HANDLES)
            for _f in endpoint.get("filters", []):
                self._add_edge_safe(dag, ep, flt, EdgeType.FILTERS)

        # request_handlers.dependencies -> depends_on service
        for _name, handler in schema.get("request_handlers", {}).items():
            if not isinstance(handler, dict):
                continue
            for _dep in handler.get("dependencies", []):
                self._add_edge_safe(dag, rh, svc, EdgeType.DEPENDS_ON)
            # request_handlers.functions.operation -> calls processor
            for _fname, func in handler.get("functions", {}).items():
                if isinstance(func, dict) and "operation" in func:
                    self._add_edge_safe(dag, rh, src, EdgeType.CALLS)

        # process_chains.steps -> chains processor operations
        pc = "mq-r4z8"
        for _name, chain in schema.get("process_chains", {}).items():
            if not isinstance(chain, dict):
                continue
            for _step in chain.get("steps", []):
                self._add_edge_safe(dag, pc, src, EdgeType.CHAINS)

        # data_structures.relations -> relates_to other data structures
        ds = "db-f8n5"
        for _name, structure in schema.get("data_structures", {}).items():
            if not isinstance(structure, dict):
                continue
            for _rname, rel in structure.get("relations", {}).items():
                if isinstance(rel, dict):
                    self._add_edge_safe(dag, ds, ds, EdgeType.RELATES_TO)
                    # Note: self-edge skipped, which is correct for type-level

        # verifiers.applies_to -> validates structures/operations
        ver = "db-j6x9"
        for _name, verifier in schema.get("verifiers", {}).items():
            if not isinstance(verifier, dict):
                continue
            for target in verifier.get("applies_to", []):
                # targets are structure names or operation names
                self._add_edge_safe(dag, ver, ds, EdgeType.VALIDATES)

        # logging.format references shared logging
        if "logging" in schema:
            log_src = "cfg-q9c5"
            log_shared = "cfg-p4b8"
            fmt = schema["logging"].get("format", "")
            if "shared/logging" in str(fmt):
                self._add_edge_safe(dag, log_src, log_shared, EdgeType.REFERENCES)

    # ── Frontend extraction ──

    def _extract_frontend(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        mod_id = "ui-v3n6"
        comp_id = "ui-w8p2"
        ac_id = "ui-x1r9"
        dl_id = "ui-y5t3"
        ep_id = "api-m5g7"
        contract_id = "api-q7v1"

        # modules.imports -> imports edges
        for _name, module in schema.get("modules", {}).items():
            if not isinstance(module, dict):
                continue
            if "imports" in module:
                self._extract_imports(dag, mod_id, module["imports"])

            # modules.components -> contains
            for _comp in module.get("components", []):
                self._add_edge_safe(dag, mod_id, comp_id, EdgeType.CONTAINS)

            # modules.navigation.*.data_loaders -> loads
            for _nav_name, nav in module.get("navigation", {}).items():
                if not isinstance(nav, dict):
                    continue
                for _dl in nav.get("data_loaders", []):
                    self._add_edge_safe(dag, mod_id, dl_id, EdgeType.LOADS)
                for _ac in nav.get("access_controls", []):
                    self._add_edge_safe(dag, mod_id, ac_id, EdgeType.GUARDS)

        # data_loaders.api_reference -> references backend endpoint
        for _name, loader in schema.get("data_loaders", {}).items():
            if not isinstance(loader, dict):
                continue
            ref = loader.get("api_reference", "")
            if ref and "backend/endpoints" in ref:
                self._add_edge_safe(dag, dl_id, ep_id, EdgeType.REFERENCES)

        # api_contracts.reference -> references backend endpoint
        for _name, contract in schema.get("api_contracts", {}).items():
            if not isinstance(contract, dict):
                continue
            ref = contract.get("reference", "")
            if ref and "backend/endpoints" in ref:
                self._add_edge_safe(dag, contract_id, ep_id, EdgeType.REFERENCES)

        # verifiers.rules.applies_to -> validates components/utilities
        ver_id = "ui-a4y1"
        for _name, verifier in schema.get("verifiers", {}).items():
            if not isinstance(verifier, dict):
                continue
            for _rname, rule in verifier.get("rules", {}).items():
                if isinstance(rule, dict):
                    for target in rule.get("applies_to", []):
                        # Could be component or utility module
                        self._add_edge_safe(dag, ver_id, comp_id, EdgeType.VALIDATES)
                        self._add_edge_safe(dag, ver_id, "ui-z2w7", EdgeType.VALIDATES)

        # logging.format references shared logging
        if "logging" in schema:
            fmt = schema["logging"].get("format", "")
            if "shared/logging" in str(fmt):
                self._add_edge_safe(dag, "cfg-r3d7", "cfg-p4b8", EdgeType.REFERENCES)

    # ── Middleware extraction ──

    def _extract_middleware(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        int_id = "mq-s9b4"
        iface_id = "mq-c1g5"
        chain_id = "mq-u6j3"

        # interceptors.base_interface -> implements_interface shared interface
        for _name, interceptor in schema.get("interceptors", {}).items():
            if not isinstance(interceptor, dict):
                continue
            base = interceptor.get("base_interface", "")
            if base and "shared/interceptor_interfaces" in base:
                self._add_edge_safe(dag, int_id, iface_id, EdgeType.IMPLEMENTS_INTERFACE)
            if "imports" in interceptor:
                self._extract_imports(dag, int_id, interceptor["imports"])

        # process_chains.interceptors -> chains interceptor
        for _name, chain in schema.get("process_chains", {}).items():
            if not isinstance(chain, dict):
                continue
            for _iname in chain.get("interceptors", []):
                self._add_edge_safe(dag, chain_id, int_id, EdgeType.CHAINS)

    # ── Shared extraction ──

    def _extract_shared(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        transformer_id = "cfg-h5v9"
        dt_id = "cfg-f7s8"
        ver_id = "cfg-g1u4"
        struct_id = "cfg-d2q3"

        # transformers.input_type / output_type -> transforms_from/to data_type
        for _name, transformer in schema.get("transformers", {}).items():
            if not isinstance(transformer, dict):
                continue
            if "input_type" in transformer:
                self._add_edge_safe(dag, transformer_id, dt_id, EdgeType.TRANSFORMS_FROM)
            if "output_type" in transformer:
                self._add_edge_safe(dag, transformer_id, dt_id, EdgeType.TRANSFORMS_TO)

        # verifiers.rules.applies_to -> validates structures/fields
        for _name, verifier in schema.get("verifiers", {}).items():
            if not isinstance(verifier, dict):
                continue
            for _rname, rule in verifier.get("rules", {}).items():
                if isinstance(rule, dict):
                    for _target in rule.get("applies_to", []):
                        self._add_edge_safe(dag, ver_id, struct_id, EdgeType.VALIDATES)

    # ── Self-description (Phase 0 bootstrap act) ──

    def _self_describe(self, dag: RegistryDag) -> None:
        """Register the registry's own components in itself.

        From BOOTSTRAP.md:
        - req-0001: System needs a dependency-tracking DAG
        - gwt-0001: Closure updates on register
        - gwt-0002: Component detection
        - gwt-0003: Context query returns transitive deps
        - gwt-0004: Cycle rejection
        - res-0001: nodes map
        - res-0002: edges list
        - res-0003: closure table
        - res-0004: components map
        """
        # Requirement
        dag.add_node(Node.requirement(
            "req-0001",
            "System needs a dependency-tracking DAG over existing resource registry",
        ))

        # Behaviors (GWT)
        dag.add_node(Node.behavior(
            "gwt-0001", "closure_update",
            "a new resource is registered",
            "the resource is added to the DAG",
            "transitive closure updates to include all reachable resources",
        ))
        dag.add_node(Node.behavior(
            "gwt-0002", "component_detection",
            "two resources share a dependency",
            "connected components are computed",
            "both appear in the same component",
        ))
        dag.add_node(Node.behavior(
            "gwt-0003", "context_query",
            "a resource ID is provided",
            "context is queried",
            "all transitive dependencies and their contracts are returned",
        ))
        dag.add_node(Node.behavior(
            "gwt-0004", "cycle_rejection",
            "an edge that would create a cycle is proposed",
            "the edge is added",
            "the edge is rejected with an error",
        ))

        # Resources (the registry's own data structures)
        dag.add_node(Node.resource(
            "res-0001", "nodes",
            "Map<UUID, ResourceEntry> — the node map of the registry DAG",
        ))
        dag.add_node(Node.resource(
            "res-0002", "edges",
            "List<{from, to, type}> — the edge list of the registry DAG",
        ))
        dag.add_node(Node.resource(
            "res-0003", "closure",
            "Map<UUID, Set<UUID>> — transitive closure table",
        ))
        dag.add_node(Node.resource(
            "res-0004", "components",
            "Map<ComponentID, Set<UUID>> — connected components",
        ))

        # Edges: requirement decomposes into behaviors
        for gwt in ("gwt-0001", "gwt-0002", "gwt-0003", "gwt-0004"):
            self._add_edge_safe(dag, "req-0001", gwt, EdgeType.DECOMPOSES)

        # Behaviors reference resources
        # gwt-0001 (closure update) references nodes, edges, closure
        self._add_edge_safe(dag, "gwt-0001", "res-0001", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0001", "res-0002", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0001", "res-0003", EdgeType.REFERENCES)

        # gwt-0002 (component detection) references edges, components
        self._add_edge_safe(dag, "gwt-0002", "res-0002", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0002", "res-0004", EdgeType.REFERENCES)

        # gwt-0003 (context query) references all four
        self._add_edge_safe(dag, "gwt-0003", "res-0001", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0003", "res-0002", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0003", "res-0003", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0003", "res-0004", EdgeType.REFERENCES)

        # gwt-0004 (cycle rejection) references edges
        self._add_edge_safe(dag, "gwt-0004", "res-0002", EdgeType.REFERENCES)
