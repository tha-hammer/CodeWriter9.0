"""Pure Python DAG implementation for the registry."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from registry.types import Edge, EdgeType, ImpactResult, Node, NodeKind, QueryResult


class CycleError(Exception):
    def __init__(self, from_id: str, to_id: str):
        self.from_id = from_id
        self.to_id = to_id
        super().__init__(f"adding edge {from_id} -> {to_id} would create a cycle")


class NodeNotFoundError(Exception):
    def __init__(self, node_id: str):
        self.node_id = node_id
        super().__init__(f"node not found: {node_id}")


class RegistryDag:
    """DAG-based resource registry with transitive closure and connected components."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.closure: dict[str, set[str]] = {}
        self.components: dict[str, list[str]] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        if node.id not in self.closure:
            self.closure[node.id] = set()
        self._recompute_components()

    def add_edge(self, edge: Edge) -> None:
        if edge.from_id not in self.nodes:
            raise NodeNotFoundError(edge.from_id)
        if edge.to_id not in self.nodes:
            raise NodeNotFoundError(edge.to_id)
        if edge.from_id == edge.to_id:
            raise CycleError(edge.from_id, edge.to_id)

        # Check if adding this edge creates a cycle
        if self._can_reach(edge.to_id, edge.from_id):
            raise CycleError(edge.from_id, edge.to_id)

        # Deduplicate
        for existing in self.edges:
            if (existing.from_id == edge.from_id
                    and existing.to_id == edge.to_id
                    and existing.edge_type == edge.edge_type):
                return

        self.edges.append(edge)
        self._recompute_closure()
        self._recompute_components()

    def _can_reach(self, from_id: str, to_id: str) -> bool:
        if from_id in self.closure and to_id in self.closure[from_id]:
            return True
        # BFS fallback
        visited: set[str] = set()
        queue: deque[str] = deque([from_id])
        adj = self._build_adjacency()
        while queue:
            current = queue.popleft()
            if current == to_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            for succ in adj.get(current, []):
                queue.append(succ)
        return False

    def _build_adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            adj[edge.from_id].append(edge.to_id)
        return adj

    def _recompute_closure(self) -> None:
        adj = self._build_adjacency()
        self.closure.clear()
        for node_id in self.nodes:
            reachable: set[str] = set()
            queue: deque[str] = deque()
            for succ in adj.get(node_id, []):
                queue.append(succ)
            while queue:
                current = queue.popleft()
                if current in reachable:
                    continue
                reachable.add(current)
                for succ in adj.get(current, []):
                    if succ not in reachable:
                        queue.append(succ)
            self.closure[node_id] = reachable

    def _recompute_components(self) -> None:
        # Union-Find on undirected edges
        parent: dict[str, str] = {nid: nid for nid in self.nodes}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for edge in self.edges:
            union(edge.from_id, edge.to_id)

        groups: dict[str, list[str]] = defaultdict(list)
        for nid in self.nodes:
            groups[find(nid)].append(nid)

        self.components = {
            f"component-{i}": sorted(members)
            for i, members in enumerate(sorted(groups.values(), key=lambda m: m[0]))
        }

    def query_relevant(self, resource_id: str) -> QueryResult:
        if resource_id not in self.nodes:
            raise NodeNotFoundError(resource_id)

        transitive_deps = sorted(self.closure.get(resource_id, set()))
        direct_edges = [e for e in self.edges if e.from_id == resource_id]

        relevant_nodes = set(transitive_deps) | {resource_id}
        all_edges = [
            e for e in self.edges
            if e.from_id in relevant_nodes and e.to_id in relevant_nodes
        ]

        component_id = None
        for comp_id, members in self.components.items():
            if resource_id in members:
                component_id = comp_id
                break

        return QueryResult(
            root=resource_id,
            transitive_deps=transitive_deps,
            direct_edges=direct_edges,
            all_edges=all_edges,
            component_id=component_id,
        )

    def component_members(self, resource_id: str) -> list[str]:
        for members in self.components.values():
            if resource_id in members:
                return list(members)
        return []

    def query_impact(self, target_id: str) -> ImpactResult:
        """Reverse dependency query: find all nodes that transitively depend on target.

        Uses the forward closure to compute the reverse: a node N is in the
        affected set iff target_id is in N's transitive closure.
        """
        if target_id not in self.nodes:
            raise NodeNotFoundError(target_id)

        affected: set[str] = set()
        direct_dependents: set[str] = set()

        # Direct dependents: nodes with a direct edge TO target
        for edge in self.edges:
            if edge.to_id == target_id:
                direct_dependents.add(edge.from_id)

        # Reverse closure: any node whose forward closure contains target
        for node_id, reachable in self.closure.items():
            if node_id != target_id and target_id in reachable:
                affected.add(node_id)

        return ImpactResult(
            target=target_id,
            affected=affected,
            direct_dependents=direct_dependents,
        )

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def component_count(self) -> int:
        return len(self.components)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in sorted(self.nodes.items())},
            "edges": [e.to_dict() for e in self.edges],
            "closure": {nid: sorted(deps) for nid, deps in sorted(self.closure.items())},
            "components": dict(sorted(self.components.items())),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegistryDag:
        dag = cls()
        for nid, ndata in data.get("nodes", {}).items():
            dag.nodes[nid] = Node(
                id=nid,
                kind=NodeKind(ndata["kind"]),
                name=ndata.get("name", ""),
                description=ndata.get("description", ""),
                schema=ndata.get("schema"),
                path=ndata.get("path"),
                source_schema=ndata.get("source_schema"),
                source_key=ndata.get("source_key"),
                version=ndata.get("version", 1),
                given=ndata.get("given"),
                when=ndata.get("when"),
                then=ndata.get("then"),
                text=ndata.get("text"),
            )
        for edata in data.get("edges", []):
            dag.edges.append(Edge(
                from_id=edata["from"],
                to_id=edata["to"],
                edge_type=EdgeType(edata["edge_type"]),
            ))
        dag._recompute_closure()
        dag._recompute_components()
        return dag

    @classmethod
    def from_json(cls, json_str: str) -> RegistryDag:
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json())

    @classmethod
    def load(cls, path: str | Path) -> RegistryDag:
        return cls.from_json(Path(path).read_text())
