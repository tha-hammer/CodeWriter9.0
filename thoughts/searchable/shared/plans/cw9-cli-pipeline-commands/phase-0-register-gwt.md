╔══════════════════════════════════════════════════╗
║  PHASE 0: Library API — RegistryDag.register_gwt ║
╚══════════════════════════════════════════════════╝

## Overview

Add `register_gwt()` method to `RegistryDag`. This is the library layer that upstream systems call after persisting GWTs. Handles ID allocation, node creation, edge wiring to parent requirement, and duplicate detection.

## Changes Required

### 1. `python/registry/types.py` — Add optional `name` param to `Node.requirement()`

> **v3 fix (Issue #1):** `Node.requirement(id, text)` at `types.py:72` accepts only 2 args.
> The plan's `register_requirement()` needs to pass a name. Rather than fight the factory,
> add an optional `name` parameter with the same `""` default.

```python
@classmethod
def requirement(cls, id: str, text: str, name: str = "") -> Node:
    return cls(id=id, kind=NodeKind.REQUIREMENT, name=name, text=text)
```

This is backwards-compatible — all existing 9 call sites pass `(id, text)` positionally and get `name=""` as before.

### 2. `python/registry/dag.py` — `register_gwt()` and `_next_gwt_id()`

```python
def _next_gwt_id(self) -> str:
    """Allocate the next gwt-NNNN ID based on existing nodes."""
    existing = [
        int(nid.split("-")[1])
        for nid in self.nodes
        if nid.startswith("gwt-") and nid.split("-")[1].isdigit()
    ]
    next_num = max(existing, default=0) + 1
    return f"gwt-{next_num:04d}"

def register_gwt(
    self,
    given: str,
    when: str,
    then: str,
    parent_req: str | None = None,
    name: str | None = None,
) -> str:
    """Register a new GWT behavior in the DAG.

    Allocates a gwt-NNNN ID, creates the behavior node,
    and optionally wires a DECOMPOSES edge from parent_req.

    Args:
        given: The "Given" precondition
        when: The "When" action/event
        then: The "Then" expected outcome
        parent_req: Optional requirement ID (e.g., "req-0008") to wire DECOMPOSES edge
        name: Optional short name (defaults to auto-generated from 'when' clause)

    Returns:
        The allocated GWT ID (e.g., "gwt-0024")

    Raises:
        NodeNotFoundError: If parent_req is given but doesn't exist in the DAG
    """
    gwt_id = self._next_gwt_id()

    if name is None:
        # Auto-generate name from 'when' clause: "validation runs" -> "validation_runs"
        name = when.lower().replace(" ", "_")[:40]

    node = Node.behavior(gwt_id, name, given, when, then)
    self.add_node(node)

    if parent_req is not None:
        if parent_req not in self.nodes:
            raise NodeNotFoundError(f"Parent requirement {parent_req} not in DAG")
        self.add_edge(Edge(parent_req, gwt_id, EdgeType.DECOMPOSES))

    return gwt_id
```

### 3. `python/registry/dag.py` — `register_requirement()`

Companion method for creating requirement nodes (upstream may need to create these too):

```python
def _next_req_id(self) -> str:
    """Allocate the next req-NNNN ID based on existing nodes."""
    existing = [
        int(nid.split("-")[1])
        for nid in self.nodes
        if nid.startswith("req-") and nid.split("-")[1].isdigit()
    ]
    next_num = max(existing, default=0) + 1
    return f"req-{next_num:04d}"

def register_requirement(self, text: str, name: str | None = None) -> str:
    """Register a new requirement in the DAG.

    Args:
        text: The requirement text
        name: Optional short name

    Returns:
        The allocated requirement ID (e.g., "req-0008")
    """
    req_id = self._next_req_id()
    if name is None:
        name = text[:40].lower().replace(" ", "_")
    node = Node.requirement(req_id, text, name)
    self.add_node(node)
    return req_id
```

> **v3 fix (Issue #1):** Now calls `Node.requirement(req_id, text, name)` which matches the
> updated 3-arg signature. The positional order is `(id, text, name)` — not `(id, name, text)`.

## Tests

Add `python/tests/test_register_gwt.py`:

```python
"""Tests for RegistryDag.register_gwt() and register_requirement()."""

import pytest

from registry.dag import NodeNotFoundError, RegistryDag
from registry.types import EdgeType, NodeKind


class TestRegisterGwt:
    def test_allocates_sequential_ids(self):
        dag = RegistryDag()
        id1 = dag.register_gwt("given1", "when1", "then1")
        id2 = dag.register_gwt("given2", "when2", "then2")
        assert id1 == "gwt-0001"
        assert id2 == "gwt-0002"

    def test_continues_from_existing_ids(self):
        """If DAG already has gwt-0023, next should be gwt-0024."""
        dag = RegistryDag()
        from registry.types import Node
        # Simulate existing self-hosting GWTs
        for i in range(1, 24):
            dag.add_node(Node.behavior(f"gwt-{i:04d}", f"b{i}", "g", "w", "t"))
        new_id = dag.register_gwt("given", "when", "then")
        assert new_id == "gwt-0024"

    def test_creates_behavior_node(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("a user exists", "they log in", "they see dashboard")
        node = dag.nodes[gwt_id]
        assert node.kind == NodeKind.BEHAVIOR
        assert node.given == "a user exists"
        assert node.when == "they log in"
        assert node.then == "they see dashboard"

    def test_wires_parent_requirement(self):
        dag = RegistryDag()
        req_id = dag.register_requirement("System needs auth")
        gwt_id = dag.register_gwt("user exists", "login", "dashboard", parent_req=req_id)
        edges = [e for e in dag.edges if e.from_id == req_id and e.to_id == gwt_id]
        assert len(edges) == 1
        assert edges[0].edge_type == EdgeType.DECOMPOSES

    def test_missing_parent_raises(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.register_gwt("g", "w", "t", parent_req="req-9999")

    def test_auto_generates_name(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("given", "validation runs on submit", "errors shown")
        assert dag.nodes[gwt_id].name == "validation_runs_on_submit"

    def test_explicit_name(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt("g", "w", "t", name="custom_name")
        assert dag.nodes[gwt_id].name == "custom_name"

    def test_save_load_preserves_registered_gwts(self, tmp_path):
        dag = RegistryDag()
        req_id = dag.register_requirement("Auth requirement")
        gwt_id = dag.register_gwt("user", "login", "dashboard", parent_req=req_id)
        dag.save(tmp_path / "dag.json")

        dag2 = RegistryDag.load(tmp_path / "dag.json")
        assert gwt_id in dag2.nodes
        assert dag2.nodes[gwt_id].given == "user"
        # Next ID should continue from where we left off
        next_id = dag2.register_gwt("g2", "w2", "t2")
        assert next_id == "gwt-0002"


class TestRegisterRequirement:
    def test_allocates_sequential_ids(self):
        dag = RegistryDag()
        id1 = dag.register_requirement("First requirement")
        id2 = dag.register_requirement("Second requirement")
        assert id1 == "req-0001"
        assert id2 == "req-0002"

    def test_continues_from_existing(self):
        dag = RegistryDag()
        from registry.types import Node
        for i in range(1, 8):
            dag.add_node(Node.requirement(f"req-{i:04d}", f"text{i}"))
        new_id = dag.register_requirement("New requirement")
        assert new_id == "req-0008"

    def test_creates_requirement_node(self):
        dag = RegistryDag()
        req_id = dag.register_requirement("System must handle auth")
        node = dag.nodes[req_id]
        assert node.kind == NodeKind.REQUIREMENT
        assert node.text == "System must handle auth"
```

> **v3 fix (Issue #1):** Test at `test_continues_from_existing` now uses
> `Node.requirement(f"req-{i:04d}", f"text{i}")` — 2 args matching the original signature.
> The old plan had 3 args: `Node.requirement(f"req-{i:04d}", f"r{i}", f"text{i}")`.

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_register_gwt.py -v` — all 11 tests pass
- [x] `python3 -m pytest tests/ -v` — no regressions (292 + 11 = 303)
- [x] ID allocation continues correctly after `save()/load()` round-trip
