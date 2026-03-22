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

    def __init__(self, schema_dir: str | Path, registry_path: str | Path | None = None, self_host: bool = False):
        self.schema_dir = Path(schema_dir)
        self.registry_path = Path(registry_path) if registry_path else self.schema_dir / "resource_registry.generic.json"
        self.self_host = self_host
        # Built at load time from resource_registry.generic.json fields
        self._type_map: dict[tuple[str, str], str] = {}   # (source_schema, section_key) → uuid
        self._path_map: dict[str, str] = {}                # path_prefix → uuid

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

        # Step 3: Load self-hosting behavioral layer (requirements, GWTs, edges)
        if self.self_host:
            self._load_self_hosting(dag)

        return dag

    def _load_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text())

    def _load_resources(self, dag: RegistryDag, registry: dict[str, Any]) -> None:
        """Load all resources from resource_registry.generic.json as DAG nodes.

        Also builds _type_map and _path_map from each resource's source_schema,
        source_key, and path fields for runtime UUID resolution.
        """
        for section in ("resources", "conditional_resources"):
            for uid, res in registry.get(section, {}).items():
                kind = NodeKind(res["kind"]) if "kind" in res else NodeKind.RESOURCE
                node = Node(
                    id=uid,
                    kind=kind,
                    name=res.get("name", ""),
                    description=res.get("description", ""),
                    schema=res.get("schema"),
                    path=res.get("path"),
                    source_schema=res.get("source_schema"),
                    source_key=res.get("source_key"),
                )
                dag.add_node(node)

                # Build _type_map: (source_schema, section_name) → uuid
                source_schema = res.get("source_schema", "")
                source_key = res.get("source_key", "")
                if source_schema and source_key:
                    # source_key is "section_name.InstancePlaceholder" or just "section_name"
                    section_name = source_key.split(".")[0]
                    self._type_map[(source_schema, section_name)] = uid

                # Build _path_map: path_prefix → uuid
                path = res.get("path", "")
                if path:
                    # path is "layer/section_name/InstancePlaceholder" or "layer/section_name"
                    # Strip the instance placeholder to get the prefix
                    parts = path.split("/")
                    if len(parts) >= 2:
                        prefix = "/".join(parts[:2])
                        self._path_map[prefix] = uid

    def _resolve_path(self, path: str) -> str | None:
        """Resolve an import path like 'backend/services' or 'shared/data_types' to a resource UUID."""
        if path in self._path_map:
            return self._path_map[path]
        # Prefix match (e.g. 'backend/endpoints/EndpointName' -> 'backend/endpoints')
        for prefix, uuid in sorted(self._path_map.items(), key=lambda x: -len(x[0])):
            if path.startswith(prefix):
                return uuid
        return None

    def _resolve_type(self, schema_file: str, section_key: str) -> str | None:
        """Resolve a (schema_file, section_key) pair to a resource UUID."""
        return self._type_map.get((schema_file, section_key))

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
                target = self._resolve_path(path)
                if target:
                    self._add_edge_safe(dag, from_id, target, EdgeType.IMPORTS)

    # ── Backend extraction ──

    def _extract_backend(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        _s = "backend_schema.json"
        src = self._resolve_type(_s, "processors")
        svc = self._resolve_type(_s, "services")
        dao = self._resolve_type(_s, "data_access_objects")
        ep = self._resolve_type(_s, "endpoints")
        rh = self._resolve_type(_s, "request_handlers")
        flt = self._resolve_type(_s, "filters")
        pc = self._resolve_type(_s, "process_chains")
        ds = self._resolve_type(_s, "data_structures")
        ver = self._resolve_type(_s, "verifiers")
        log_src = self._resolve_type(_s, "logging")
        log_shared = self._resolve_type("shared_objects_schema.json", "logging")

        # processors.imports -> imports edges
        if src:
            for _name, proc in schema.get("processors", {}).items():
                if isinstance(proc, dict) and "imports" in proc:
                    self._extract_imports(dag, src, proc["imports"])

        # services.functions.calls -> calls DAO
        if svc and dao:
            for _name, service in schema.get("services", {}).items():
                if not isinstance(service, dict):
                    continue
                for _fname, func in service.get("functions", {}).items():
                    if isinstance(func, dict):
                        for call in func.get("calls", []):
                            self._add_edge_safe(dag, svc, dao, EdgeType.CALLS)

        # endpoints.handler -> handles request_handler
        if ep:
            for _name, endpoint in schema.get("endpoints", {}).items():
                if not isinstance(endpoint, dict):
                    continue
                if "handler" in endpoint and rh:
                    self._add_edge_safe(dag, ep, rh, EdgeType.HANDLES)
                if flt:
                    for _f in endpoint.get("filters", []):
                        self._add_edge_safe(dag, ep, flt, EdgeType.FILTERS)

        # request_handlers.dependencies -> depends_on service
        if rh:
            for _name, handler in schema.get("request_handlers", {}).items():
                if not isinstance(handler, dict):
                    continue
                if svc:
                    for _dep in handler.get("dependencies", []):
                        self._add_edge_safe(dag, rh, svc, EdgeType.DEPENDS_ON)
                if src:
                    for _fname, func in handler.get("functions", {}).items():
                        if isinstance(func, dict) and "operation" in func:
                            self._add_edge_safe(dag, rh, src, EdgeType.CALLS)

        # process_chains.steps -> chains processor operations
        if pc and src:
            for _name, chain in schema.get("process_chains", {}).items():
                if not isinstance(chain, dict):
                    continue
                for _step in chain.get("steps", []):
                    self._add_edge_safe(dag, pc, src, EdgeType.CHAINS)

        # data_structures.relations -> relates_to other data structures
        if ds:
            for _name, structure in schema.get("data_structures", {}).items():
                if not isinstance(structure, dict):
                    continue
                for _rname, rel in structure.get("relations", {}).items():
                    if isinstance(rel, dict):
                        self._add_edge_safe(dag, ds, ds, EdgeType.RELATES_TO)

        # verifiers.applies_to -> validates structures/operations
        if ver and ds:
            for _name, verifier in schema.get("verifiers", {}).items():
                if not isinstance(verifier, dict):
                    continue
                for target in verifier.get("applies_to", []):
                    self._add_edge_safe(dag, ver, ds, EdgeType.VALIDATES)

        # logging.format references shared logging
        if "logging" in schema and log_src and log_shared:
            fmt = schema["logging"].get("format", "")
            if "shared/logging" in str(fmt):
                self._add_edge_safe(dag, log_src, log_shared, EdgeType.REFERENCES)

    # ── Frontend extraction ──

    def _extract_frontend(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        _f = "frontend_schema.json"
        mod_id = self._resolve_type(_f, "modules")
        comp_id = self._resolve_type(_f, "components")
        ac_id = self._resolve_type(_f, "access_controls")
        dl_id = self._resolve_type(_f, "data_loaders")
        ep_id = self._resolve_type("backend_schema.json", "endpoints")
        contract_id = self._resolve_type(_f, "api_contracts")
        ver_id = self._resolve_type(_f, "verifiers")
        util_id = self._resolve_type(_f, "utility_modules")
        log_src = self._resolve_type(_f, "logging")
        log_shared = self._resolve_type("shared_objects_schema.json", "logging")

        # modules.imports -> imports edges
        if mod_id:
            for _name, module in schema.get("modules", {}).items():
                if not isinstance(module, dict):
                    continue
                if "imports" in module:
                    self._extract_imports(dag, mod_id, module["imports"])

                # modules.components -> contains
                if comp_id:
                    for _comp in module.get("components", []):
                        self._add_edge_safe(dag, mod_id, comp_id, EdgeType.CONTAINS)

                # modules.navigation.*.data_loaders -> loads
                for _nav_name, nav in module.get("navigation", {}).items():
                    if not isinstance(nav, dict):
                        continue
                    if dl_id:
                        for _dl in nav.get("data_loaders", []):
                            self._add_edge_safe(dag, mod_id, dl_id, EdgeType.LOADS)
                    if ac_id:
                        for _ac in nav.get("access_controls", []):
                            self._add_edge_safe(dag, mod_id, ac_id, EdgeType.GUARDS)

        # data_loaders.api_reference -> references backend endpoint
        if dl_id and ep_id:
            for _name, loader in schema.get("data_loaders", {}).items():
                if not isinstance(loader, dict):
                    continue
                ref = loader.get("api_reference", "")
                if ref and "backend/endpoints" in ref:
                    self._add_edge_safe(dag, dl_id, ep_id, EdgeType.REFERENCES)

        # api_contracts.reference -> references backend endpoint
        if contract_id and ep_id:
            for _name, contract in schema.get("api_contracts", {}).items():
                if not isinstance(contract, dict):
                    continue
                ref = contract.get("reference", "")
                if ref and "backend/endpoints" in ref:
                    self._add_edge_safe(dag, contract_id, ep_id, EdgeType.REFERENCES)

        # verifiers.rules.applies_to -> validates components/utilities
        if ver_id and comp_id:
            for _name, verifier in schema.get("verifiers", {}).items():
                if not isinstance(verifier, dict):
                    continue
                for _rname, rule in verifier.get("rules", {}).items():
                    if isinstance(rule, dict):
                        for target in rule.get("applies_to", []):
                            self._add_edge_safe(dag, ver_id, comp_id, EdgeType.VALIDATES)
                            if util_id:
                                self._add_edge_safe(dag, ver_id, util_id, EdgeType.VALIDATES)

        # logging.format references shared logging
        if "logging" in schema and log_src and log_shared:
            fmt = schema["logging"].get("format", "")
            if "shared/logging" in str(fmt):
                self._add_edge_safe(dag, log_src, log_shared, EdgeType.REFERENCES)

    # ── Middleware extraction ──

    def _extract_middleware(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        _m = "middleware_schema.json"
        int_id = self._resolve_type(_m, "interceptors")
        iface_id = self._resolve_type("shared_objects_schema.json", "interceptor_interfaces")
        chain_id = self._resolve_type(_m, "process_chains")

        # interceptors.base_interface -> implements_interface shared interface
        if int_id:
            for _name, interceptor in schema.get("interceptors", {}).items():
                if not isinstance(interceptor, dict):
                    continue
                base = interceptor.get("base_interface", "")
                if base and "shared/interceptor_interfaces" in base and iface_id:
                    self._add_edge_safe(dag, int_id, iface_id, EdgeType.IMPLEMENTS_INTERFACE)
                if "imports" in interceptor:
                    self._extract_imports(dag, int_id, interceptor["imports"])

        # process_chains.interceptors -> chains interceptor
        if chain_id and int_id:
            for _name, chain in schema.get("process_chains", {}).items():
                if not isinstance(chain, dict):
                    continue
                for _iname in chain.get("interceptors", []):
                    self._add_edge_safe(dag, chain_id, int_id, EdgeType.CHAINS)

    # ── Shared extraction ──

    def _extract_shared(self, dag: RegistryDag, schema: dict[str, Any]) -> None:
        _sh = "shared_objects_schema.json"
        transformer_id = self._resolve_type(_sh, "transformers")
        dt_id = self._resolve_type(_sh, "data_types")
        ver_id = self._resolve_type(_sh, "verifiers")
        struct_id = self._resolve_type(_sh, "common_structures")

        # transformers.input_type / output_type -> transforms_from/to data_type
        if transformer_id and dt_id:
            for _name, transformer in schema.get("transformers", {}).items():
                if not isinstance(transformer, dict):
                    continue
                if "input_type" in transformer:
                    self._add_edge_safe(dag, transformer_id, dt_id, EdgeType.TRANSFORMS_FROM)
                if "output_type" in transformer:
                    self._add_edge_safe(dag, transformer_id, dt_id, EdgeType.TRANSFORMS_TO)

        # verifiers.rules.applies_to -> validates structures/fields
        if ver_id and struct_id:
            for _name, verifier in schema.get("verifiers", {}).items():
                if not isinstance(verifier, dict):
                    continue
                for _rname, rule in verifier.get("rules", {}).items():
                    if isinstance(rule, dict):
                        for _target in rule.get("applies_to", []):
                            self._add_edge_safe(dag, ver_id, struct_id, EdgeType.VALIDATES)

    # ── Self-hosting behavioral layer (loaded from schema/self_hosting.json) ──

    def _load_self_hosting(self, dag: RegistryDag) -> None:
        """Load self-hosting behavioral layer from static JSON.

        Resource and spec nodes are already loaded from resource_registry.generic.json.
        This adds requirements, GWT behaviors, semantic edges, and test_artifacts.
        """
        sh_path = self.schema_dir / "self_hosting.json"
        data = self._load_json(sh_path)

        # Requirements
        for req in data.get("requirements", []):
            dag.add_node(Node.requirement(req["id"], req["text"], req.get("name", "")))

        # Behaviors (GWT)
        for gwt in data.get("behaviors", []):
            dag.add_node(Node.behavior(
                gwt["id"], gwt["name"],
                gwt["given"], gwt["when"], gwt["then"],
            ))

        # Edges (direct IDs or {"resolve": [schema, section]} for runtime resolution)
        for edge in data.get("edges", []):
            from_id = edge["from"]
            to_raw = edge["to"]
            if isinstance(to_raw, dict) and "resolve" in to_raw:
                to_id = self._resolve_type(to_raw["resolve"][0], to_raw["resolve"][1]) or ""
            else:
                to_id = to_raw
            edge_type = EdgeType(edge["type"])
            self._add_edge_safe(dag, from_id, to_id, edge_type)

        # Test artifact mapping (for query_affected_tests)
        dag.test_artifacts = data.get("test_artifacts", {})

