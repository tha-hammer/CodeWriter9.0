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

        # --- Phase 1: PlusCal template library (self-registration) ---

        # The 4 PlusCal templates
        dag.add_node(Node(
            id="tpl-0001", kind=NodeKind.SPEC, name="crud_template",
            description="CRUD PlusCal template — set-based state, create/read/update/delete actions, structural invariants",
            path="templates/pluscal/crud.tla",
        ))
        dag.add_node(Node(
            id="tpl-0002", kind=NodeKind.SPEC, name="state_machine_template",
            description="State machine PlusCal template — enum states, guarded transitions, bypass conditions",
            path="templates/pluscal/state_machine.tla",
        ))
        dag.add_node(Node(
            id="tpl-0003", kind=NodeKind.SPEC, name="queue_pipeline_template",
            description="Queue/pipeline PlusCal template — ordered processing, FIFO, no-item-loss invariant",
            path="templates/pluscal/queue_pipeline.tla",
        ))
        dag.add_node(Node(
            id="tpl-0004", kind=NodeKind.SPEC, name="auth_session_template",
            description="Auth/session PlusCal template — login/logout/expire, role-based access, session timeout",
            path="templates/pluscal/auth_session.tla",
        ))

        # The registry CRUD instance (first customer of the template)
        dag.add_node(Node(
            id="tpl-0005", kind=NodeKind.SPEC, name="registry_crud_spec",
            description="Registry CRUD instantiation — verifies gwt-0001..0004 via TLC model checker",
            path="templates/pluscal/instances/registry_crud.tla",
        ))

        # The TLA+ artifact store resource
        dag.add_node(Node(
            id="fs-x7p6", kind=NodeKind.RESOURCE, name="tla_artifact_store",
            description="Filesystem location for generated TLA+ specs and TLC output",
            path="templates/pluscal",
        ))

        # Templates model schema patterns
        self._add_edge_safe(dag, "tpl-0001", "db-f8n5", EdgeType.MODELS)   # CRUD ← data_structures
        self._add_edge_safe(dag, "tpl-0001", "db-d3w8", EdgeType.MODELS)   # CRUD ← data_access_objects
        self._add_edge_safe(dag, "tpl-0002", "mq-t2f7", EdgeType.MODELS)   # state machine ← execution_patterns
        self._add_edge_safe(dag, "tpl-0003", "mq-r4z8", EdgeType.MODELS)   # queue ← process_chains (backend)
        self._add_edge_safe(dag, "tpl-0003", "mq-u6j3", EdgeType.MODELS)   # queue ← process_chains (middleware)
        self._add_edge_safe(dag, "tpl-0004", "cfg-t5h9", EdgeType.MODELS)  # auth ← security
        self._add_edge_safe(dag, "tpl-0004", "ui-x1r9", EdgeType.MODELS)   # auth ← access_controls

        # Registry spec instantiates the CRUD template
        self._add_edge_safe(dag, "tpl-0005", "tpl-0001", EdgeType.IMPLEMENTS)

        # Registry spec verifies the 4 GWT behaviors
        for gwt in ("gwt-0001", "gwt-0002", "gwt-0003", "gwt-0004"):
            self._add_edge_safe(dag, "tpl-0005", gwt, EdgeType.VERIFIES)

        # All templates stored in the artifact store
        for tpl in ("tpl-0001", "tpl-0002", "tpl-0003", "tpl-0004", "tpl-0005"):
            self._add_edge_safe(dag, tpl, "fs-x7p6", EdgeType.REFERENCES)

        # ── Phase 2: Composition Engine self-registration ──

        # Composition engine state machine spec (instantiates state_machine template)
        dag.add_node(Node.resource(
            "tpl-0006", "composition_engine_spec",
            description="State machine spec for the composition engine lifecycle (TLC verified)",
            path="templates/pluscal/instances/composition_engine.tla",
        ))
        # Composition engine Python module
        dag.add_node(Node.resource(
            "comp-0001", "composer",
            description="TLA+ composition engine: compose(spec_a, spec_b) with variable unification",
            path="python/registry/composer.py",
        ))
        # Spec cache
        dag.add_node(Node.resource(
            "comp-0002", "spec_cache",
            description="Composed spec cache indexed by connected component",
            path="python/registry/composer.py",
        ))

        # Composition engine spec instantiates state_machine template
        self._add_edge_safe(dag, "tpl-0006", "tpl-0002", EdgeType.IMPLEMENTS)
        # Composition engine spec stored in artifact store
        self._add_edge_safe(dag, "tpl-0006", "fs-x7p6", EdgeType.REFERENCES)
        # Composer implements the composition engine spec
        self._add_edge_safe(dag, "comp-0001", "tpl-0006", EdgeType.IMPLEMENTS)
        # Composer uses the DAG for variable unification
        self._add_edge_safe(dag, "comp-0001", "db-f8n5", EdgeType.REFERENCES)  # data_structures
        # Composer composes templates
        for tpl in ("tpl-0001", "tpl-0002", "tpl-0003", "tpl-0004"):
            self._add_edge_safe(dag, "comp-0001", tpl, EdgeType.COMPOSES)
        # Spec cache references composer
        self._add_edge_safe(dag, "comp-0002", "comp-0001", EdgeType.DEPENDS_ON)

        # ── Phase 3: One-Shot Loop self-registration ──

        # 3 GWT behaviors for the one-shot loop
        dag.add_node(Node.behavior(
            "gwt-0005", "context_transitive_deps",
            "a new GWT",
            "context is queried from registry",
            "all transitive deps are included",
        ))
        dag.add_node(Node.behavior(
            "gwt-0006", "counterexample_translation",
            "a TLC counterexample",
            "translated to natural language",
            "it references PlusCal-level concepts only",
        ))
        dag.add_node(Node.behavior(
            "gwt-0007", "failure_routing",
            "two consecutive failures",
            "routing",
            "requirements inconsistency is reported (not retried)",
        ))

        # One-shot loop state machine spec (instantiates state_machine template)
        dag.add_node(Node(
            id="tpl-0007", kind=NodeKind.SPEC, name="one_shot_loop_spec",
            description="State machine spec for the one-shot loop lifecycle (TLC verified)",
            path="templates/pluscal/instances/one_shot_loop.tla",
        ))

        # One-shot loop Python module
        dag.add_node(Node.resource(
            "loop-0001", "one_shot_loop",
            description="One-shot loop: registry context → LLM → PlusCal → compile → compose → TLC → route",
            path="python/registry/one_shot_loop.py",
        ))

        # Counterexample translator component
        dag.add_node(Node.resource(
            "loop-0002", "counterexample_translator",
            description="Translates TLC counterexample traces to PlusCal-level concepts",
            path="python/registry/one_shot_loop.py",
        ))

        # Pass/retry/fail router component
        dag.add_node(Node.resource(
            "loop-0003", "pass_retry_fail_router",
            description="Routes TLC results: pass → done, first fail → retry, second fail → requirements inconsistency",
            path="python/registry/one_shot_loop.py",
        ))

        # One-shot loop spec instantiates state_machine template
        self._add_edge_safe(dag, "tpl-0007", "tpl-0002", EdgeType.IMPLEMENTS)
        # One-shot loop spec stored in artifact store
        self._add_edge_safe(dag, "tpl-0007", "fs-x7p6", EdgeType.REFERENCES)
        # One-shot loop spec verifies the 3 GWT behaviors
        for gwt in ("gwt-0005", "gwt-0006", "gwt-0007"):
            self._add_edge_safe(dag, "tpl-0007", gwt, EdgeType.VERIFIES)

        # One-shot loop module implements its spec
        self._add_edge_safe(dag, "loop-0001", "tpl-0007", EdgeType.IMPLEMENTS)
        # One-shot loop uses the registry (DAG) for context query
        self._add_edge_safe(dag, "loop-0001", "res-0001", EdgeType.REFERENCES)  # nodes
        self._add_edge_safe(dag, "loop-0001", "res-0003", EdgeType.REFERENCES)  # closure
        # One-shot loop uses the composition engine
        self._add_edge_safe(dag, "loop-0001", "comp-0001", EdgeType.DEPENDS_ON)
        # One-shot loop uses the spec cache
        self._add_edge_safe(dag, "loop-0001", "comp-0002", EdgeType.REFERENCES)

        # Counterexample translator is part of loop
        self._add_edge_safe(dag, "loop-0002", "loop-0001", EdgeType.DEPENDS_ON)
        # Router is part of loop
        self._add_edge_safe(dag, "loop-0003", "loop-0001", EdgeType.DEPENDS_ON)

        # GWT behaviors reference the loop components
        self._add_edge_safe(dag, "gwt-0005", "res-0003", EdgeType.REFERENCES)  # transitive deps → closure
        self._add_edge_safe(dag, "gwt-0006", "loop-0002", EdgeType.REFERENCES)  # counterexample → translator
        self._add_edge_safe(dag, "gwt-0007", "loop-0003", EdgeType.REFERENCES)  # routing → router

        # Requirement for the one-shot loop
        dag.add_node(Node.requirement(
            "req-0002",
            "System needs a one-shot loop that queries registry context, prompts LLM, extracts PlusCal, compiles, composes, verifies with TLC, and routes pass/retry/fail",
        ))
        # Requirement decomposes into the 3 behaviors
        for gwt in ("gwt-0005", "gwt-0006", "gwt-0007"):
            self._add_edge_safe(dag, "req-0002", gwt, EdgeType.DECOMPOSES)

        # ── Phase 4: The Bridge self-registration ──

        # Requirement: spec-to-code bridge
        dag.add_node(Node.requirement(
            "req-0003",
            "System needs mechanical translators that convert TLA+ specs into code artifacts conforming to existing schema shapes (data_structures, processors.operations, verifiers, testing.assertions)",
        ))

        # 4 GWT behaviors — one per translator
        dag.add_node(Node.behavior(
            "gwt-0008", "state_var_translation",
            "a TLA+ spec with declared state variables",
            "the state variable translator processes it",
            "a data_structures artifact is produced with fields, types, and validation conforming to backend_schema",
        ))
        dag.add_node(Node.behavior(
            "gwt-0009", "action_translation",
            "a TLA+ spec with defined actions",
            "the action translator processes it",
            "a processors.operations artifact is produced with parameters, returns, and error_types conforming to backend_schema",
        ))
        dag.add_node(Node.behavior(
            "gwt-0010", "invariant_translation",
            "a TLA+ spec with invariants",
            "the invariant translator processes it",
            "verifiers and testing.assertions artifacts are produced conforming to backend and shared schemas",
        ))
        dag.add_node(Node.behavior(
            "gwt-0011", "trace_translation",
            "a TLC counterexample trace with state transitions",
            "the trace translator processes it",
            "concrete test scenarios are generated with setup, steps, and expected outcomes for each state",
        ))

        # Requirement decomposes into the 4 bridge behaviors
        for gwt in ("gwt-0008", "gwt-0009", "gwt-0010", "gwt-0011"):
            self._add_edge_safe(dag, "req-0003", gwt, EdgeType.DECOMPOSES)

        # Bridge translator resource nodes
        dag.add_node(Node.resource(
            "bridge-0001", "state_var_translator",
            description="Translates TLA+ state variables into data_structures shape (fields, types, validation)",
            path="python/registry/bridge.py",
        ))
        dag.add_node(Node.resource(
            "bridge-0002", "action_translator",
            description="Translates TLA+ actions into processors.operations shape (params, returns, errors)",
            path="python/registry/bridge.py",
        ))
        dag.add_node(Node.resource(
            "bridge-0003", "invariant_translator",
            description="Translates TLA+ invariants into verifiers and testing.assertions shapes",
            path="python/registry/bridge.py",
        ))
        dag.add_node(Node.resource(
            "bridge-0004", "trace_translator",
            description="Translates TLC counterexample traces into concrete test scenarios",
            path="python/registry/bridge.py",
        ))

        # Bridge translator spec (instantiates state_machine template)
        dag.add_node(Node(
            id="tpl-0008", kind=NodeKind.SPEC, name="bridge_translator_spec",
            description="State machine spec for the bridge translator pipeline (TLC verified: 702 states, 6 invariants)",
            path="templates/pluscal/instances/bridge_translator.tla",
        ))
        # Bridge spec instantiates state_machine template
        self._add_edge_safe(dag, "tpl-0008", "tpl-0002", EdgeType.IMPLEMENTS)
        # Bridge spec stored in artifact store
        self._add_edge_safe(dag, "tpl-0008", "fs-x7p6", EdgeType.REFERENCES)
        # Bridge spec verifies the 4 GWT behaviors
        for gwt in ("gwt-0008", "gwt-0009", "gwt-0010", "gwt-0011"):
            self._add_edge_safe(dag, "tpl-0008", gwt, EdgeType.VERIFIES)

        # GWT behaviors reference the target schema shapes they produce
        self._add_edge_safe(dag, "gwt-0008", "db-f8n5", EdgeType.REFERENCES)    # → data_structures
        self._add_edge_safe(dag, "gwt-0009", "db-b7r2", EdgeType.REFERENCES)    # → processors
        self._add_edge_safe(dag, "gwt-0010", "db-j6x9", EdgeType.REFERENCES)    # → backend verifiers
        self._add_edge_safe(dag, "gwt-0010", "cfg-g1u4", EdgeType.REFERENCES)   # → shared verifiers
        self._add_edge_safe(dag, "gwt-0010", "cfg-s6e2", EdgeType.REFERENCES)   # → testing
        self._add_edge_safe(dag, "gwt-0011", "cfg-s6e2", EdgeType.REFERENCES)   # → testing

        # GWT behaviors reference the loop (bridge uses the loop)
        self._add_edge_safe(dag, "gwt-0008", "loop-0001", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0009", "loop-0001", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0010", "loop-0001", EdgeType.REFERENCES)
        self._add_edge_safe(dag, "gwt-0011", "loop-0001", EdgeType.REFERENCES)

        # Bridge translators implement their behaviors
        self._add_edge_safe(dag, "bridge-0001", "gwt-0008", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "bridge-0002", "gwt-0009", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "bridge-0003", "gwt-0010", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "bridge-0004", "gwt-0011", EdgeType.IMPLEMENTS)

        # Bridge translators depend on the one-shot loop
        for br in ("bridge-0001", "bridge-0002", "bridge-0003", "bridge-0004"):
            self._add_edge_safe(dag, br, "loop-0001", EdgeType.DEPENDS_ON)

        # Bridge outputs stored in plan artifact store (activating fs-y3q2)
        for br in ("bridge-0001", "bridge-0002", "bridge-0003", "bridge-0004"):
            self._add_edge_safe(dag, br, "fs-y3q2", EdgeType.REFERENCES)

        # ── Phase 5: Self-Hosting — Impact Analysis (first pipeline-built feature) ──

        # Requirement: reverse dependency / impact analysis query
        dag.add_node(Node.requirement(
            "req-0004",
            "System needs an impact analysis query: given a node, find all nodes that transitively depend on it (reverse closure), enabling change-impact assessment",
        ))

        # 3 GWT behaviors for impact analysis
        dag.add_node(Node.behavior(
            "gwt-0012", "reverse_closure_complete",
            "a registry DAG with nodes A→B→C (A depends on B depends on C)",
            "query_impact(C) is called",
            "the result contains both A and B as affected nodes (full transitive reverse closure)",
        ))
        dag.add_node(Node.behavior(
            "gwt-0013", "leaf_has_no_impact",
            "a registry DAG where node X has no dependents (nothing points to X)",
            "query_impact(X) is called",
            "the affected set is empty (leaf nodes have zero impact radius)",
        ))
        dag.add_node(Node.behavior(
            "gwt-0014", "direct_dependents_included",
            "a registry DAG where nodes D and E both directly depend on node F",
            "query_impact(F) is called",
            "D and E both appear in the affected set and in direct_dependents",
        ))

        # Requirement decomposes into the 3 impact analysis behaviors
        for gwt in ("gwt-0012", "gwt-0013", "gwt-0014"):
            self._add_edge_safe(dag, "req-0004", gwt, EdgeType.DECOMPOSES)

        # GWT behaviors reference the DAG core resources (nodes, edges, closure)
        for gwt in ("gwt-0012", "gwt-0013", "gwt-0014"):
            self._add_edge_safe(dag, gwt, "res-0001", EdgeType.REFERENCES)  # → nodes
            self._add_edge_safe(dag, gwt, "res-0002", EdgeType.REFERENCES)  # → edges
            self._add_edge_safe(dag, gwt, "res-0003", EdgeType.REFERENCES)  # → closure

        # Impact analysis resource node (the implementation we'll write)
        dag.add_node(Node.resource(
            "impact-0001", "impact_analysis",
            description="Reverse dependency query — finds all nodes transitively depending on a target",
            path="python/registry/dag.py",
        ))

        # Impact analysis implements its behaviors
        self._add_edge_safe(dag, "impact-0001", "gwt-0012", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "impact-0001", "gwt-0013", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "impact-0001", "gwt-0014", EdgeType.IMPLEMENTS)

        # Impact analysis depends on the DAG engine
        self._add_edge_safe(dag, "impact-0001", "res-0001", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "impact-0001", "res-0002", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "impact-0001", "res-0003", EdgeType.DEPENDS_ON)

        # ── Phase 6: Self-Hosting — Dependency Validation (second pipeline-built feature) ──

        # Requirement: pre-check edge validity before add_edge()
        dag.add_node(Node.requirement(
            "req-0005",
            "System needs an edge validation pre-check: given a proposed edge, determine whether adding it would maintain all DAG invariants (acyclicity, no duplicates, node-kind compatibility) without actually mutating the DAG",
        ))

        # 3 GWT behaviors for dependency validation
        dag.add_node(Node.behavior(
            "gwt-0015", "valid_edge_accepted",
            "a registry DAG with compatible node kinds and no existing path from target to source",
            "validate_edge(source, target, edge_type) is called",
            "validation passes with valid=True and empty reason",
        ))
        dag.add_node(Node.behavior(
            "gwt-0016", "cycle_creating_edge_rejected",
            "a registry DAG where node Y can already reach node X through existing edges",
            "validate_edge(X, Y, edge_type) is called (which would create a cycle)",
            "validation fails with valid=False and reason containing 'cycle'",
        ))
        dag.add_node(Node.behavior(
            "gwt-0017", "kind_incompatible_edge_rejected",
            "a registry DAG where a behavior node B exists and a test node T exists",
            "validate_edge(B, T, 'depends_on') is called (behavior depending on test)",
            "validation fails with valid=False and reason containing 'kind'",
        ))

        # Requirement decomposes into the 3 validation behaviors
        for gwt in ("gwt-0015", "gwt-0016", "gwt-0017"):
            self._add_edge_safe(dag, "req-0005", gwt, EdgeType.DECOMPOSES)

        # GWT behaviors reference the DAG core resources
        for gwt in ("gwt-0015", "gwt-0016", "gwt-0017"):
            self._add_edge_safe(dag, gwt, "res-0001", EdgeType.REFERENCES)  # → nodes
            self._add_edge_safe(dag, gwt, "res-0002", EdgeType.REFERENCES)  # → edges
            self._add_edge_safe(dag, gwt, "res-0003", EdgeType.REFERENCES)  # → closure

        # Dependency validation resource node
        dag.add_node(Node.resource(
            "depval-0001", "dependency_validation",
            description="Edge validation pre-check — determines if a proposed edge maintains DAG invariants",
            path="python/registry/dag.py",
        ))

        # Dependency validation implements its behaviors
        self._add_edge_safe(dag, "depval-0001", "gwt-0015", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "depval-0001", "gwt-0016", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "depval-0001", "gwt-0017", EdgeType.IMPLEMENTS)

        # Dependency validation depends on DAG engine (nodes, edges, closure)
        self._add_edge_safe(dag, "depval-0001", "res-0001", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "depval-0001", "res-0002", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "depval-0001", "res-0003", EdgeType.DEPENDS_ON)

        # ── Phase 7: Self-Hosting — Subgraph Extraction (third pipeline-built feature) ──

        # Requirement: extract the minimal subgraph needed to understand a node
        dag.add_node(Node.requirement(
            "req-0006",
            "System needs a subgraph extraction query: given a node, return its forward closure (descendants), reverse closure (ancestors), and all edges where both endpoints are in that set",
        ))

        # 3 GWT behaviors for subgraph extraction
        dag.add_node(Node.behavior(
            "gwt-0018", "chain_subgraph_complete",
            "a node in a chain (has ancestors and descendants)",
            "extract_subgraph(node_id) is called",
            "the result contains all ancestors AND all descendants of the node",
        ))
        dag.add_node(Node.behavior(
            "gwt-0019", "isolated_node_subgraph",
            "an isolated node with no edges",
            "extract_subgraph(node_id) is called",
            "the result contains only that node and no edges",
        ))
        dag.add_node(Node.behavior(
            "gwt-0020", "no_dangling_edges",
            "any subgraph result from extract_subgraph",
            "the edges in the result are inspected",
            "every edge has both endpoints in the node set (no dangling edges)",
        ))

        # Requirement decomposes into the 3 subgraph behaviors
        for gwt in ("gwt-0018", "gwt-0019", "gwt-0020"):
            self._add_edge_safe(dag, "req-0006", gwt, EdgeType.DECOMPOSES)

        # GWT behaviors reference the DAG core resources
        for gwt in ("gwt-0018", "gwt-0019", "gwt-0020"):
            self._add_edge_safe(dag, gwt, "res-0001", EdgeType.REFERENCES)  # → nodes
            self._add_edge_safe(dag, gwt, "res-0002", EdgeType.REFERENCES)  # → edges
            self._add_edge_safe(dag, gwt, "res-0003", EdgeType.REFERENCES)  # → closure

        # Subgraph extraction resource node
        dag.add_node(Node.resource(
            "subgraph-0001", "subgraph_extraction",
            description="Subgraph extraction query — returns minimal subgraph to understand a node",
            path="python/registry/dag.py",
        ))

        # Subgraph extraction implements its behaviors
        self._add_edge_safe(dag, "subgraph-0001", "gwt-0018", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "subgraph-0001", "gwt-0019", EdgeType.IMPLEMENTS)
        self._add_edge_safe(dag, "subgraph-0001", "gwt-0020", EdgeType.IMPLEMENTS)

        # Subgraph extraction depends on DAG engine (nodes, edges, closure)
        self._add_edge_safe(dag, "subgraph-0001", "res-0001", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "subgraph-0001", "res-0002", EdgeType.DEPENDS_ON)
        self._add_edge_safe(dag, "subgraph-0001", "res-0003", EdgeType.DEPENDS_ON)
