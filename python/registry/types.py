"""Core types for the registry DAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeKind(str, Enum):
    RESOURCE = "resource"
    REQUIREMENT = "requirement"
    BEHAVIOR = "behavior"
    CONSTRAINT = "constraint"
    SPEC = "spec"
    TEST = "test"
    MODULE = "module"


class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    DEPENDS_ON = "depends_on"
    HANDLES = "handles"
    FILTERS = "filters"
    REFERENCES = "references"
    IMPLEMENTS_INTERFACE = "implements_interface"
    CHAINS = "chains"
    VALIDATES = "validates"
    RELATES_TO = "relates_to"
    TRANSFORMS_FROM = "transforms_from"
    TRANSFORMS_TO = "transforms_to"
    CONTAINS = "contains"
    LOADS = "loads"
    GUARDS = "guards"
    DECOMPOSES = "decomposes"
    MODELS = "models"
    VERIFIES = "verifies"
    IMPLEMENTS = "implements"
    CONSTRAINS = "constrains"
    COMPOSES = "composes"


@dataclass
class Node:
    id: str
    kind: NodeKind
    name: str
    description: str = ""
    schema: str | None = None
    path: str | None = None
    source_schema: str | None = None
    source_key: str | None = None
    version: int = 1
    given: str | None = None
    when: str | None = None
    then: str | None = None
    text: str | None = None

    @classmethod
    def resource(cls, id: str, name: str, description: str = "", **kwargs: Any) -> Node:
        return cls(id=id, kind=NodeKind.RESOURCE, name=name, description=description, **kwargs)

    @classmethod
    def behavior(cls, id: str, name: str, given: str, when: str, then: str) -> Node:
        return cls(
            id=id, kind=NodeKind.BEHAVIOR, name=name,
            given=given, when=when, then=then,
        )

    @classmethod
    def requirement(cls, id: str, text: str) -> Node:
        return cls(id=id, kind=NodeKind.REQUIREMENT, name="", text=text)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }
        for opt in ("schema", "path", "source_schema", "source_key", "given", "when", "then", "text"):
            val = getattr(self, opt)
            if val is not None:
                d[opt] = val
        return d


@dataclass
class Edge:
    from_id: str
    to_id: str
    edge_type: EdgeType

    def to_dict(self) -> dict[str, str]:
        return {"from": self.from_id, "to": self.to_id, "edge_type": self.edge_type.value}


@dataclass
class QueryResult:
    root: str
    transitive_deps: list[str] = field(default_factory=list)
    direct_edges: list[Edge] = field(default_factory=list)
    all_edges: list[Edge] = field(default_factory=list)
    component_id: str | None = None
