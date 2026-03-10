```
┌──────────────────────────────────────────────────────────────────────┐
│  CW9 CLI Pipeline Commands — Implementation Plan                     │
│  Status: DRAFT v5  |  Date: 2026-03-10                               │
│  v5 changelog: TLC simulation traces as test case generator          │
│  v4 changelog: Phase 5 LLM loop rewrite (see v4 changelog)          │
└──────────────────────────────────────────────────────────────────────┘
```

# CW9 CLI Pipeline Commands

## Overview

Two-layer architecture for making the CW9 pipeline usable on external projects:

**Layer 1 — Library API** (called by upstream systems, Rust crate, or scripts):
```python
dag.register_gwt(given="...", when="...", then="...", parent_req="req-0008")
```

**Layer 2 — CLI commands** (operate on DAG state, don't care where GWTs came from):
```
cw9 extract → cw9 loop <gwt-id> → cw9 bridge <gwt-id> → cw9 gen-tests <gwt-id> → cw9 test
```

GWTs arrive as natural language (JSON, database, API call) with no IDs, no DAG registration, no PlusCal spec. The library layer assigns IDs, creates DAG nodes, wires edges. The CLI layer picks up from there.

## Current State Analysis

- `cw9 init` and `cw9 status` work (292 tests passing)
- `config.toml` is written by init but never read back
- `SchemaExtractor.extract()` works on external schemas (tested)
- `RegistryDag.save()/load()` exist but are never used in production
- GWT IDs are hardcoded in `extractor.py` (`gwt-0001`..`gwt-0023`), next available: `gwt-0024`
- Requirement IDs: `req-0001`..`req-0007`, next available: `req-0008`
- `Node.behavior()` factory at `types.py:64` accepts `(id, name, given, when, then)` — text field left None
- `Node.requirement()` factory at `types.py:72` accepts `(id, text)` — **2 args only, name hardcoded to ""**
- `RegistryDag.add_node()` at `dag.py:36` silently overwrites duplicate IDs (no validation)
- No ID allocator exists — all IDs are hardcoded string literals
- `query_affected_tests()` exists at `dag.py:242` but `test_artifacts` is never persisted
- `process_response()` at `one_shot_loop.py:615` requires **3 positional args**: `(llm_response, module_name, cfg_text)`
- `LoopStatus` at `one_shot_loop.py:84` has **no `retry_prompt` field** — retry prompts are built externally by each `run_*_loop.py` script via standalone `build_retry_prompt()` functions
- `CounterexampleTrace` at `one_shot_loop.py:64` and `TlcTrace` at `bridge.py:52` are **disconnected types** — no converter exists
- `translate_traces()` at `bridge.py:582` is never called with real data — `test_scenarios` is always `[]`

### 📊 Key Discoveries

| Finding | Location | Impact |
|---|---|---|
| `tomllib` available (Python 3.11+) | `pyproject.toml:5` | No new deps for config parsing |
| No ID allocator exists | `extractor.py:435-976` | Must build `register_gwt()` with auto-ID |
| `Node.behavior()` doesn't set `text` | `types.py:64-69` | `text` stays None — loop generates PlusCal from GWT strings |
| `Node.requirement()` takes 2 args | `types.py:72-73` | `requirement(id, text)` — name hardcoded to `""` |
| `add_node()` overwrites silently | `dag.py:36-40` | `register_gwt()` must check for duplicates |
| `PATH_TO_RESOURCE` is hardcoded | `extractor.py:62-97` | Known limitation — canonical UUIDs required |
| All LLM calls identical pattern | `run_change_prop_loop.py:293-317` | Extract common `call_llm()` |
| `_self_describe()` is 500+ lines | `extractor.py:414-997` | Self-hosting GWTs stay there; external GWTs use `register_gwt()` |
| `process_response()` needs 3+ args | `one_shot_loop.py:615-622` | `(llm_response, module_name, cfg_text)` — NOT `(response, gwt_id)` |
| No `retry_prompt` on LoopStatus | `one_shot_loop.py:84-93` | Must build retry prompts from `status.counterexample` + `status.error` |
| `extract()` rebuilds from scratch | `extractor.py:142-144` | `RegistryDag()` — fresh DAG, obliterates registered GWTs |
| Bridge `test_scenarios` always empty | `bridge.py:679` | `traces` defaults to `None` → `[]` → no scenarios generated |
| `_invariant_to_condition()` is shallow | `bridge.py:553-565` | 5 text substitutions, not executable Python |
| Generated tests have real logic | `run_change_prop_loop.py:572-621` | 5 `_verify_*` methods with actual DAG queries |

## Desired End State

After implementation:

```
┌─────────────────────────────────────────────────────────┐
│  Upstream System (Rust crate, script, API)              │
│                                                         │
│  dag = RegistryDag.load(ctx.dag_path)                   │
│  gwt_id = dag.register_gwt(                             │
│      given="a user submits a form",                     │
│      when="validation runs",                            │
│      then="errors are displayed inline",                │
│      parent_req="req-0008"                              │
│  )                                                      │
│  dag.save(ctx.dag_path)                                 │
│  # gwt_id == "gwt-0024"                                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  CLI Pipeline (operates on DAG state)                   │
│                                                         │
│  cw9 extract        # build DAG from schemas            │
│                     # ↑ MERGES registered GWTs back in  │
│  cw9 loop gwt-0024  # GWT → PlusCal → TLC              │
│  cw9 bridge gwt-0024 # TLC trace → bridge artifacts     │
│  cw9 gen-tests gwt-0024 # artifacts → pytest file       │
│  cw9 test           # run tests (smart targeting)       │
└─────────────────────────────────────────────────────────┘
```

### Artifact Convention

All commands locate artifacts by GWT ID under `.cw9/`:

```
.cw9/
  dag.json                              # saved by: cw9 extract / register_gwt()
  specs/<gwt-id>.tla                    # saved by: cw9 loop
  specs/<gwt-id>.cfg                    # saved by: cw9 loop
  specs/<gwt-id>_sim_traces.json        # saved by: cw9 loop (TLC -simulate output)
  specs/<gwt-id>_traces.json            # saved by: cw9 loop (counterexample traces from retries)
  bridge/<gwt-id>_bridge_artifacts.json # saved by: cw9 bridge
  sessions/<gwt-id>_attempt{N}.txt     # saved by: cw9 loop
```

Test output: `<target>/tests/generated/test_<gwt-id>.py` (saved by `cw9 gen-tests`).

## What We're NOT Doing

| NOT doing | Doing instead |
|---|---|
| Bundled pipeline command (`cw9 run-all`) | Explicit chainable steps |
| ~~Per-module hardcoded test generators~~ | **Phase 5A-C**: trace pipeline (5A) + compiler hints (5B) + LLM test generation loop (5C) |
| Dynamic `PATH_TO_RESOURCE` from registry | Canonical UUID scheme (known limitation) |
| `cw9 ingest` (brownfield code scanning) | Deferred — users write schemas by hand |
| Rust binary wrapper | Python library API + CLI (Rust calls Python) |
| `cw9 register-gwt` CLI command | Library API only — upstream calls `dag.register_gwt()` |
| GWT auto-discovery from code | Explicit registration via API |
| Full TLA+ → Python compiler as test generator | Bounded compiler as prompt enrichment; LLM loop for test generation |
| Few-shot from oracle test files | TLC simulation traces as primary test derivation context |
| TLC as pass/fail gate only | TLC as test case generator via `-simulate` mode |
| LLM invents test topologies from scratch | LLM translates TLC-generated traces into Python API calls |

---

╔══════════════════════════════════════════════════╗
║  PHASE 0: Library API — RegistryDag.register_gwt ║
╚══════════════════════════════════════════════════╝

### Overview

Add `register_gwt()` method to `RegistryDag`. This is the library layer that upstream systems call after persisting GWTs. Handles ID allocation, node creation, edge wiring to parent requirement, and duplicate detection.

### Changes Required

#### 1. `python/registry/types.py` — Add optional `name` param to `Node.requirement()`

> **v3 fix (Issue #1):** `Node.requirement(id, text)` at `types.py:72` accepts only 2 args.
> The plan's `register_requirement()` needs to pass a name. Rather than fight the factory,
> add an optional `name` parameter with the same `""` default.

```python
@classmethod
def requirement(cls, id: str, text: str, name: str = "") -> Node:
    return cls(id=id, kind=NodeKind.REQUIREMENT, name=name, text=text)
```

This is backwards-compatible — all existing 9 call sites pass `(id, text)` positionally and get `name=""` as before.

#### 2. `python/registry/dag.py` — `register_gwt()` and `_next_gwt_id()`

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

#### 3. `python/registry/dag.py` — `register_requirement()`

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

### Tests

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

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_register_gwt.py -v` — all 11 tests pass
- [ ] `python3 -m pytest tests/ -v` — no regressions (292 + 11 = 303)
- [ ] ID allocation continues correctly after `save()/load()` round-trip

---

╔═══════════════════════════════════════╗
║  PHASE 1: config.toml → from_target  ║
╚═══════════════════════════════════════╝

### Overview

Wire `tomllib` parsing into `from_target()` so it reads `engine_root` from `.cw9/config.toml` when present. Removes the need to pass `engine_root` explicitly.

### Changes Required

#### 1. `python/registry/context.py` — `from_target()`

**Current** (lines 60-76): `engine_root` defaults to `Path(__file__).parent.parent.parent` when `None`.

**Change**: Before the `__file__`-based fallback, check for `.cw9/config.toml` and read `engine.root` from it.

```python
import tomllib

@classmethod
def from_target(cls, target_root: Path, engine_root: Path | None = None) -> ProjectContext:
    target_root = Path(target_root).resolve()
    if engine_root is None:
        # Try config.toml first
        config_path = target_root / ".cw9" / "config.toml"
        if config_path.exists():
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            engine_root_str = config.get("engine", {}).get("root")
            if engine_root_str:
                engine_root = Path(engine_root_str).resolve()
        # Fallback to auto-detection from __file__
        if engine_root is None:
            engine_root = Path(__file__).resolve().parent.parent.parent
    else:
        engine_root = Path(engine_root).resolve()

    if target_root == engine_root:
        return cls.self_hosting(engine_root)
    return cls.external(engine_root, target_root)
```

#### 2. `python/registry/cli.py` — Simplify calls

**Current**: `ProjectContext.from_target(target, ENGINE_ROOT)` (lines 80, 115).

**Change**: `ProjectContext.from_target(target)` — let config.toml provide it. Keep `ENGINE_ROOT` for `cmd_init` (which writes the config).

#### 3. Fix `_CONFIG_TEMPLATE` quoting

**Current** (line 27): `root = {engine_root!r}` uses Python `repr()` which produces `'/path'` with single quotes.

**Change**: Use double quotes for valid TOML: `root = "{engine_root}"`.

### Tests

Add to `python/tests/test_context.py`:

```python
class TestConfigTomlParsing:
    def test_from_target_reads_config_toml(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        cw9 = target / ".cw9"
        cw9.mkdir()
        config = cw9 / "config.toml"
        config.write_text(f'[engine]\nroot = "{ENGINE_ROOT}"\n')
        ctx = ProjectContext.from_target(target)  # no engine_root arg
        assert ctx.engine_root == ENGINE_ROOT

    def test_from_target_falls_back_without_config(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        ctx = ProjectContext.from_target(target)
        assert ctx.engine_root == ENGINE_ROOT

    def test_explicit_engine_root_overrides_config(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        cw9 = target / ".cw9"
        cw9.mkdir()
        config = cw9 / "config.toml"
        config.write_text('[engine]\nroot = "/bogus/path"\n')
        ctx = ProjectContext.from_target(target, ENGINE_ROOT)
        assert ctx.engine_root == ENGINE_ROOT
```

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_context.py -v` — all pass including new tests
- [ ] `python3 -m pytest tests/test_cli.py -v` — no regressions

---

╔═══════════════════════════════════════╗
║  PHASE 2: cw9 extract                ║
╚═══════════════════════════════════════╝

### Overview

Runs `SchemaExtractor` on target schemas, builds DAG, saves to `.cw9/dag.json`. Prints minimal diff summary on re-extract. **Merges registered GWTs back into the extracted DAG** so that `register_gwt() → extract → loop` doesn't destroy registered work.

> **v3 fix (Issue #2):** `SchemaExtractor.extract()` at `extractor.py:144` always starts
> with a fresh `RegistryDag()`. Any GWTs registered via `register_gwt()` exist only in
> `dag.json` and are not embedded in schema files. Without merging, re-running `cw9 extract`
> obliterates them. This is now handled in `cmd_extract()`, not deferred to "a future
> enhancement."

### Changes Required

#### 1. `python/registry/dag.py` — `merge_registered_nodes()`

Add a method to merge externally-registered nodes back into a freshly-extracted DAG:

```python
def merge_registered_nodes(self, old_dag: "RegistryDag") -> int:
    """Merge nodes from old_dag that don't exist in self.

    Identifies "registered" nodes as those with gwt- or req- prefixed IDs
    that exist in old_dag but not in the freshly-extracted self.
    Also preserves their edges.

    Returns the number of nodes merged.
    """
    merged = 0
    # IDs in the fresh DAG (from extract)
    fresh_ids = set(self.nodes.keys())

    for nid, node in old_dag.nodes.items():
        if nid in fresh_ids:
            continue  # Already in fresh DAG (from _self_describe or schemas)

        # Only merge nodes that look like registered nodes
        # (gwt-NNNN or req-NNNN with high enough IDs to not be self-hosting)
        prefix = nid.split("-")[0] if "-" in nid else ""
        if prefix not in ("gwt", "req"):
            continue

        self.add_node(node)
        merged += 1

    # Preserve edges involving merged nodes
    merged_ids = set(self.nodes.keys()) - fresh_ids
    for edge in old_dag.edges:
        # Include edge if at least one endpoint was merged
        # and both endpoints exist in the new DAG
        if (edge.from_id in merged_ids or edge.to_id in merged_ids):
            if edge.from_id in self.nodes and edge.to_id in self.nodes:
                self.add_edge(edge)

    return merged
```

#### 2. `python/registry/cli.py` — `cmd_extract()`

```python
def cmd_extract(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    state_root = target / ".cw9"

    if not state_root.exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        print("Run: cw9 init", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    dag_path = state_root / "dag.json"

    # Load old DAG for diff summary AND GWT preservation
    old_dag = None
    old_nodes, old_edges = 0, 0
    if dag_path.exists():
        from registry.dag import RegistryDag
        old_dag = RegistryDag.load(dag_path)
        old_nodes = old_dag.node_count
        old_edges = old_dag.edge_count

    # Extract fresh DAG from schemas
    from registry.extractor import SchemaExtractor
    extractor = SchemaExtractor(schema_dir=str(ctx.schema_dir))
    dag = extractor.extract()

    # Merge registered GWTs from old DAG back in
    merged = 0
    if old_dag is not None:
        merged = dag.merge_registered_nodes(old_dag)

    # Save
    dag.save(dag_path)

    # Diff summary
    new_nodes = dag.node_count
    new_edges = dag.edge_count
    dn = new_nodes - old_nodes
    de = new_edges - old_edges
    sign = lambda x: f"+{x}" if x > 0 else str(x)
    print(f"DAG updated: {new_nodes} nodes ({sign(dn)}), {new_edges} edges ({sign(de)})")
    if merged > 0:
        print(f"  (preserved {merged} registered node(s) from previous DAG)")

    return 0
```

#### 3. Argparse wiring

```python
p_extract = sub.add_parser("extract", help="Extract DAG from schemas")
p_extract.add_argument("target_dir", nargs="?", default=".")
```

### Tests

```python
class TestExtract:
    def test_extract_builds_dag(self, target_dir):
        main(["init", str(target_dir)])
        rc = main(["extract", str(target_dir)])
        assert rc == 0
        dag_data = json.loads((target_dir / ".cw9" / "dag.json").read_text())
        assert len(dag_data["nodes"]) > 0
        assert len(dag_data["edges"]) > 0

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
        assert "+0" in out

    def test_extract_status_shows_nodes(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])
        main(["status", str(target_dir)])
        out = capsys.readouterr().out
        assert "0 nodes" not in out

    def test_extract_preserves_registered_gwts(self, target_dir, capsys):
        """register_gwt() → extract → GWT survives."""
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
```

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_cli.py::TestExtract -v` — all pass (including 2 new merge tests)
- [ ] `cw9 init /tmp/foo && cw9 extract /tmp/foo` — prints node/edge counts

---

╔═══════════════════════════════════════╗
║  PHASE 3: cw9 loop <gwt-id>          ║
╚═══════════════════════════════════════╝

### Overview

Runs the LLM → PlusCal → TLC pipeline for a single GWT behavior. The GWT node must already exist in the DAG (registered via `register_gwt()` or extracted by `cw9 extract`). The loop:

1. Loads the DAG, finds the GWT node
2. Builds a prompt from the GWT's `given`/`when`/`then` + registry context
3. Calls Claude Agent SDK to generate PlusCal
4. Compiles PlusCal → runs TLC model checker
5. On PASS: saves spec to `.cw9/specs/<gwt-id>.tla` + `.cfg`
6. **On PASS: runs TLC `-simulate num=10` to generate concrete execution traces** (v5)
7. On failure: retries with counterexample feedback

> **v5 addition (step 6):** After TLC verifies a model with N distinct states and passes,
> it has visited every reachable state and confirmed every invariant holds at each one.
> We previously captured only "pass" and a state count — throwing away the state space.
> TLC's `-simulate` mode outputs concrete execution traces through the state space on
> passing models. Each trace is a pre-verified test case: "starting from THIS state,
> applying THESE actions, produces THIS result, and ALL invariants hold." These traces
> become the primary input for Phase 5C's test generation loop.

### Changes Required

#### 1. `python/registry/loop_runner.py` (new) — Common loop logic

> **v3 fix (Issue #3):** Three bugs fixed from v2:
> 1. `process_response()` requires `(llm_response, module_name, cfg_text)` — v2 called it
>    with `(response, gwt_id)` missing `cfg_text`.
> 2. `LoopStatus` has no `retry_prompt` field — retry prompts must be built from
>    `status.counterexample` and `status.error`, following the pattern in existing loop scripts.
> 3. The `module_name` should be derived from the GWT's corresponding TLA+ module, not the
>    gwt_id directly. For initial generation it's derived from the GWT name.

```python
"""Common loop runner — LLM → PlusCal → TLC pipeline."""

import asyncio
import os
import shutil
from pathlib import Path

os.environ.pop("CLAUDECODE", None)
import claude_agent_sdk

from registry.context import ProjectContext
from registry.one_shot_loop import (
    OneShotLoop, query_context, format_prompt_context,
    LoopResult, LoopStatus, extract_pluscal,
)


async def call_llm(prompt: str, system_prompt: str | None = None) -> str:
    """Single-turn LLM call via Claude Agent SDK (account-level auth).

    NOTE: No per-call timeout — matches existing run_*_loop.py pattern.
    Could hang if API is unresponsive. Known limitation.
    """
    options = claude_agent_sdk.ClaudeAgentOptions(
        allowed_tools=[],
        system_prompt=system_prompt or (
            "You are a TLA+/PlusCal expert. Generate formally verifiable "
            "PlusCal specifications from behavioral requirements."
        ),
        max_turns=1,
        model="claude-sonnet-4-20250514",
    )
    result_text = []
    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        if isinstance(message, claude_agent_sdk.AssistantMessage):
            for block in message.content:
                if isinstance(block, claude_agent_sdk.TextBlock):
                    result_text.append(block.text)
        elif isinstance(message, claude_agent_sdk.ResultMessage):
            if message.result:
                result_text.append(message.result)
    return "\n".join(result_text)


def build_retry_prompt(
    initial_prompt: str,
    attempt: int,
    status: LoopStatus,
) -> str:
    """Build a retry prompt from the LoopStatus counterexample and error.

    NOTE: Intentionally uses 3-arg (initial_prompt, attempt, LoopStatus) arity
    rather than the 5-arg pattern in existing run_*_loop.py scripts. LoopStatus
    wraps the same information more cleanly.

    Follows the pattern from existing run_*_loop.py scripts:
    original prompt + error context + counterexample trace.
    """
    parts = [initial_prompt, "\n\n## RETRY — Previous Attempt Failed\n"]

    parts.append(f"Attempt {attempt} failed.")

    if status.error:
        parts.append(f"\n### Error\n{status.error}")

    if status.counterexample is not None:
        ce = status.counterexample
        if ce.violated_invariant:
            parts.append(f"\n### Violated Invariant\n`{ce.violated_invariant}`")
        if ce.pluscal_summary:
            parts.append(f"\n### Counterexample Summary\n{ce.pluscal_summary}")
        if ce.states:
            parts.append("\n### State Trace")
            for state in ce.states:
                snum = state.get("state_num", "?")
                label = state.get("label", "unknown")
                parts.append(f"\nState {snum} <{label}>:")
                for var, val in state.get("vars", {}).items():
                    parts.append(f"  /\\ {var} = {val}")

    if status.tlc_result and status.tlc_result.error_message:
        parts.append(f"\n### TLC Output\n{status.tlc_result.error_message}")

    parts.append("\n\nPlease fix the specification to satisfy all invariants.")
    return "\n".join(parts)


async def run_loop(
    ctx: ProjectContext,
    gwt_id: str,
    max_retries: int = 5,
    log_fn=print,
) -> tuple[LoopResult, Path | None]:
    """Run the LLM → PlusCal → TLC loop for a GWT behavior.

    The GWT must already exist in the DAG (via register_gwt() or extract).

    Returns (result, spec_path) where spec_path is the verified .tla
    file path on success, or None on failure.
    """
    from registry.dag import RegistryDag

    # Load DAG
    dag_path = ctx.state_root / "dag.json"
    if not dag_path.exists():
        log_fn(f"Error: No DAG found at {dag_path}. Run: cw9 extract")
        return LoopResult.FAIL, None
    dag = RegistryDag.load(dag_path)

    # Verify GWT exists
    if gwt_id not in dag.nodes:
        log_fn(f"Error: {gwt_id} not found in DAG")
        return LoopResult.FAIL, None

    gwt_node = dag.nodes[gwt_id]

    # Build initial prompt from GWT's given/when/then + registry context
    bundle = query_context(dag, gwt_id)
    prompt_ctx = format_prompt_context(bundle)

    # Read PlusCal template
    template_path = ctx.template_dir / "state_machine.tla"
    template_text = template_path.read_text() if template_path.exists() else ""

    initial_prompt = _build_prompt(gwt_node, prompt_ctx, template_text)
    current_prompt = initial_prompt

    # Derive module_name from GWT name (e.g., "validation_runs" -> "ValidationRuns")
    module_name = "".join(w.capitalize() for w in gwt_node.name.split("_"))
    if not module_name:
        module_name = gwt_id.replace("-", "_")

    # Default cfg_text for TLC configuration
    cfg_text = f"SPECIFICATION Spec\n"

    for attempt in range(1, max_retries + 1):
        log_fn(f"Attempt {attempt}/{max_retries}")

        response = await call_llm(current_prompt)

        # Save LLM response
        ctx.session_dir.mkdir(parents=True, exist_ok=True)
        response_path = ctx.session_dir / f"{gwt_id}_attempt{attempt}.txt"
        response_path.write_text(response)

        # Process through OneShotLoop (compile PlusCal, run TLC)
        loop = OneShotLoop(dag=dag, ctx=ctx)
        loop.query(gwt_id)
        status = loop.process_response(
            llm_response=response,
            module_name=module_name,
            cfg_text=cfg_text,
        )

        if status.result == LoopResult.PASS:
            ctx.spec_dir.mkdir(parents=True, exist_ok=True)
            if status.compiled_spec_path:
                dest_tla = ctx.spec_dir / f"{gwt_id}.tla"
                dest_cfg = ctx.spec_dir / f"{gwt_id}.cfg"
                shutil.copy2(status.compiled_spec_path, dest_tla)
                cfg_src = status.compiled_spec_path.with_suffix(".cfg")
                if cfg_src.exists():
                    shutil.copy2(cfg_src, dest_cfg)
                log_fn(f"PASS — verified spec saved: {dest_tla}")

                # v5: Generate simulation traces from the verified model
                from registry.one_shot_loop import run_tlc_simulate
                sim_traces = run_tlc_simulate(
                    dest_tla, dest_cfg,
                    tools_dir=ctx.engine_root / "tools",
                    num_traces=10,
                )
                if sim_traces:
                    import json
                    traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
                    traces_path.write_text(json.dumps(sim_traces, indent=2))
                    log_fn(f"  {len(sim_traces)} simulation traces saved: {traces_path}")

                return LoopResult.PASS, dest_tla

        elif status.result == LoopResult.FAIL:
            log_fn(f"FAIL — {status.error}")
            return LoopResult.FAIL, None

        else:  # RETRY
            current_prompt = build_retry_prompt(initial_prompt, attempt, status)
            log_fn(f"RETRY — {status.error}")

    log_fn(f"Exhausted {max_retries} attempts")
    return LoopResult.FAIL, None


def _build_prompt(gwt_node, prompt_ctx: str, template_text: str) -> str:
    """Build the initial LLM prompt from GWT node + registry context."""
    return f"""Generate a PlusCal specification for the following behavior:

Given: {gwt_node.given}
When: {gwt_node.when}
Then: {gwt_node.then}

## Registry Context
{prompt_ctx}

## PlusCal Template
Use this as a structural reference:
{template_text}

Generate a complete PlusCal algorithm wrapped in a TLA+ module.
Include invariants that verify the "Then" condition holds.
"""
```

**Note**: The exact prompt construction will be refined during implementation by studying `run_change_prop_loop.py:333-411`. The skeleton above shows the structure.

#### 1b. `python/registry/one_shot_loop.py` — `run_tlc_simulate()` (v5 addition)

> **v5:** After TLC verification passes, run TLC in `-simulate` mode to generate concrete
> execution traces through the verified state space. These traces ARE the test cases for
> Phase 5C. The format is identical to counterexample traces minus the violation header,
> so the same `_STATE_HEADER_RE` and `_VAR_ASSIGN_RE` regexes parse both.

```python
def run_tlc_simulate(
    tla_path: str | Path,
    cfg_path: str | Path | None = None,
    tools_dir: str | Path | None = None,
    num_traces: int = 10,
) -> list[list[dict[str, Any]]]:
    """Run TLC in -simulate mode to generate concrete traces from a passing model.

    Each trace is a sequence of states through the verified state space.
    All invariants hold at every state in every trace.

    Returns list of traces, where each trace is a list of state dicts
    with keys: state_num, label, vars.
    """
    jar = _find_tla2tools(tools_dir)
    tla_path = Path(tla_path)

    cmd = [
        "java", "-XX:+UseParallelGC",
        "-cp", jar,
        "tlc2.TLC",
        str(tla_path),
        "-simulate", f"num={num_traces}",
        "-nowarning",
    ]
    if cfg_path:
        cmd.extend(["-config", str(cfg_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    raw = result.stdout + result.stderr

    return parse_simulation_traces(raw)


def parse_simulation_traces(raw: str) -> list[list[dict[str, Any]]]:
    """Parse TLC -simulate output into structured traces.

    Reuses the same _STATE_HEADER_RE and _VAR_ASSIGN_RE regexes as
    parse_counterexample(). Traces are delimited by the State 1 restart
    pattern — each time we see State 1 after already having states,
    we know a new trace has begun.
    """
    traces: list[list[dict[str, Any]]] = []
    current_trace: list[dict[str, Any]] = []
    current_state: dict[str, Any] | None = None

    for line in raw.split("\n"):
        line = line.strip()

        header_m = _STATE_HEADER_RE.match(line)
        if header_m:
            state_num = int(header_m.group(1))
            # New trace starts at State 1
            if state_num == 1 and current_trace:
                if current_state:
                    current_trace.append(current_state)
                traces.append(current_trace)
                current_trace = []
            elif current_state:
                current_trace.append(current_state)

            current_state = {
                "state_num": state_num,
                "label": header_m.group(2),
                "vars": {},
            }
            continue

        if current_state is not None:
            var_m = _VAR_ASSIGN_RE.match(line)
            if var_m:
                current_state["vars"][var_m.group(1)] = var_m.group(2).strip()

    if current_state:
        current_trace.append(current_state)
    if current_trace:
        traces.append(current_trace)

    return traces
```

#### 2. `python/registry/cli.py` — `cmd_loop()`

```python
def cmd_loop(args: argparse.Namespace) -> int:
    import asyncio

    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    from registry.loop_runner import run_loop
    from registry.one_shot_loop import LoopResult

    ctx = ProjectContext.from_target(target)
    result, spec_path = asyncio.run(run_loop(
        ctx=ctx,
        gwt_id=args.gwt_id,
        max_retries=args.max_retries,
    ))

    if result == LoopResult.PASS:
        print(f"Verified: {spec_path}")
        return 0
    else:
        print("Loop failed.", file=sys.stderr)
        return 1
```

#### 3. Argparse wiring

```python
p_loop = sub.add_parser("loop", help="Run LLM → PlusCal → TLC for a GWT behavior")
p_loop.add_argument("gwt_id", help="GWT behavior ID (e.g., gwt-0024)")
p_loop.add_argument("target_dir", nargs="?", default=".")
p_loop.add_argument("--max-retries", type=int, default=5)
```

### Tests

```python
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
```

Full LLM integration is manual: `cw9 extract && cw9 loop gwt-0024`

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_cli.py::TestLoop -v` — error-path tests pass
- [ ] `python3 -m pytest tests/test_cli.py::TestSimulationTraceParser -v` — 3 trace parser tests pass (v5)
- [ ] No import errors from `registry.loop_runner`

#### Manual:
- [ ] `cw9 loop gwt-0021` — completes TLC verification, saves `.tla`/`.cfg`
- [ ] Session logs appear in `.cw9/sessions/gwt-0021_attempt*.txt`
- [ ] Simulation traces saved to `.cw9/specs/gwt-0021_sim_traces.json` (v5)

---

╔═══════════════════════════════════════╗
║  PHASE 4: cw9 bridge <gwt-id>        ║
╚═══════════════════════════════════════╝

### Overview

Reads a verified `.tla` spec from `.cw9/specs/<gwt-id>.tla`, runs `run_bridge()`, saves bridge artifacts to `.cw9/bridge/<gwt-id>_bridge_artifacts.json`.

### Changes Required

#### 1. `python/registry/cli.py` — `cmd_bridge()`

```python
def cmd_bridge(args: argparse.Namespace) -> int:
    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    gwt_id = args.gwt_id

    spec_path = ctx.spec_dir / f"{gwt_id}.tla"
    if not spec_path.exists():
        print(f"No verified spec found: {spec_path}", file=sys.stderr)
        print(f"Run: cw9 loop {gwt_id}", file=sys.stderr)
        return 1

    from registry.bridge import run_bridge
    tla_text = spec_path.read_text()
    result = run_bridge(tla_text)

    artifacts = {
        "gwt_id": gwt_id,
        "module_name": result.module_name,
        "data_structures": result.data_structures,
        "operations": result.operations,
        "verifiers": result.verifiers,
        "assertions": result.assertions,
    }
    artifact_path = ctx.artifact_dir / f"{gwt_id}_bridge_artifacts.json"
    artifact_path.write_text(json.dumps(artifacts, indent=2) + "\n")

    print(f"Bridge artifacts saved: {artifact_path}")
    print(f"  data_structures: {len(result.data_structures)}")
    print(f"  operations: {len(result.operations)}")
    print(f"  verifiers: {len(result.verifiers)}")
    print(f"  assertions: {len(result.assertions)}")

    return 0
```

#### 2. Argparse wiring

```python
p_bridge = sub.add_parser("bridge", help="Translate verified spec → bridge artifacts")
p_bridge.add_argument("gwt_id", help="GWT behavior ID")
p_bridge.add_argument("target_dir", nargs="?", default=".")
```

### Tests

```python
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
        spec_path.write_text(_MINIMAL_TLA_SPEC)  # defined as test fixture
        rc = main(["bridge", "gwt-test", str(target_dir)])
        assert rc == 0
        artifact_path = target_dir / ".cw9" / "bridge" / "gwt-test_bridge_artifacts.json"
        assert artifact_path.exists()
        data = json.loads(artifact_path.read_text())
        assert data["gwt_id"] == "gwt-test"
```

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_cli.py::TestBridge -v` — all pass

#### Manual:
- [ ] After `cw9 loop gwt-0021`, `cw9 bridge gwt-0021` produces artifact JSON

---

╔════════════════════════════════════════════════════════════════╗
║  PHASE 5: cw9 gen-tests <gwt-id> — LLM Test Generation       ║
║  (Parts A → B → C)                                            ║
╚════════════════════════════════════════════════════════════════╝

### Overview

> **v3 rewrite (Issue #4):** v2 emitted `assert state is not None` stubs — a regression from
> `run_change_prop_loop.py:485-717`'s real `_verify_*` methods. v3 attempted to fix this with
> a bounded TLA+ regex compiler (5B) + template generators (5C/5D).
>
> **v4 rewrite (Issues #5-7):** v3's compiler produces correct *expressions*
> (`all(t in candidates for t in affected)`) but can't bind variables to API calls. The
> semantic gap — knowing that `NoFalsePositives` means "call `dag.query_affected_tests()`,
> walk the impact set, check every returned path" — requires domain reasoning, not regex.
>
> v4 keeps the compiler as a prompt enrichment utility (5B) and replaces templates with an
> LLM-in-the-loop (5C), structurally parallel to `cw9 loop`: bridge artifacts as structured
> input, LLM generates pytest code, pytest verifies mechanically, retry on failure.

### What Exists Today (and Why It Works)

The current generated tests in `run_change_prop_loop.py:485-717` have three layers:

| Layer | Source | What it does | Example |
|---|---|---|---|
| **Stub tests** | Bridge verifier names | `self._check_invariant("ValidState")` → dispatches to `_verify_*` | `test_no_false_positives(self)` |
| **Semantic verifiers** | Hand-written per module | Real Python assertions using DAG queries | `_verify_NoFalsePositives` calls `dag.query_affected_tests()`, walks impact set |
| **Scenario tests** | Hand-written per module | Concrete topologies with expected values | `test_upstream_change_propagates`, `test_diamond_leaf_change` |

Layers 2 and 3 are 100% hardcoded. The bridge gives us rich data (`verifiers.conditions` has partial TLA+, `applies_to` lists state variables) but only verifier *names* are used.

### The Gap: Two Disconnected Type Systems

```
TLA+ Spec ──bridge──→ Bridge Artifacts JSON ──???──→ Python Test Code
                      (conditions, applies_to,        (assertions, fixtures,
                       operations, data_structures)     scenario tests)

CounterexampleTrace ──???──→ TlcTrace ──translate_traces()──→ TestScenario
(one_shot_loop.py:64)        (bridge.py:52)                   (always empty today)
```

- `_invariant_to_condition()` at `bridge.py:553` does 5 text substitutions (`\in` → `in`, etc.) — not executable Python
- `parse_counterexample()` at `one_shot_loop.py:424` produces `CounterexampleTrace`
- `translate_traces()` at `bridge.py:582` expects `TlcTrace` — different type, no converter
- Result: `test_scenarios` is always `[]` because nobody connects them

---

### Phase 5A: Connect the Trace Pipeline

**Goal**: Make `CounterexampleTrace` → `TlcTrace` conversion work so `translate_traces()` can populate `test_scenarios`. **Additionally (v5):** Load and format TLC simulation traces as the primary context for Phase 5C test generation.

#### 1. `python/registry/bridge.py` — `counterexample_to_tlc_trace()`

```python
def counterexample_to_tlc_trace(ce: "CounterexampleTrace") -> "TlcTrace | None":
    """Convert a CounterexampleTrace from one_shot_loop to a TlcTrace for bridge.

    CounterexampleTrace.states is list[dict] with keys:
        state_num: int, label: str, vars: dict[str, str]
    TlcTrace expects:
        invariant_violated: str, states: list[dict[str, str]]

    Returns None if the counterexample has no states or no violated invariant.
    """
    from registry.one_shot_loop import CounterexampleTrace

    if not ce.states or not ce.violated_invariant:
        return None

    # Flatten: CounterexampleTrace.states[i]["vars"] → TlcTrace.states[i]
    tlc_states = []
    for state in ce.states:
        vars_dict = state.get("vars", {})
        # TlcTrace.states expects dict[str, str] — already in that form
        tlc_states.append(vars_dict)

    return TlcTrace(
        invariant_violated=ce.violated_invariant,
        states=tlc_states,
    )
```

#### 2. `python/registry/loop_runner.py` — Collect traces during loop

After a successful TLC pass, also try to generate example traces using TLC's `-simulate` flag. On TLC failures (retries), collect the counterexample traces.

```python
# In run_loop(), after process_response():
collected_traces: list[TlcTrace] = []

# ... inside the retry branch:
if status.counterexample is not None:
    from registry.bridge import counterexample_to_tlc_trace
    tlc_trace = counterexample_to_tlc_trace(status.counterexample)
    if tlc_trace is not None:
        collected_traces.append(tlc_trace)

# ... on PASS, save collected traces alongside the spec:
if collected_traces:
    import json
    traces_path = ctx.spec_dir / f"{gwt_id}_traces.json"
    traces_data = [{"invariant_violated": t.invariant_violated, "states": t.states}
                   for t in collected_traces]
    traces_path.write_text(json.dumps(traces_data, indent=2))
```

#### 3. `python/registry/cli.py` — `cmd_bridge()` update

Update `cmd_bridge()` to load traces and pass them to `run_bridge()`:

```python
# In cmd_bridge(), before run_bridge():

# Load counterexample traces (from retry failures)
traces_path = ctx.spec_dir / f"{gwt_id}_traces.json"
traces = []
if traces_path.exists():
    from registry.bridge import TlcTrace
    traces_data = json.loads(traces_path.read_text())
    traces = [TlcTrace(**td) for td in traces_data]

result = run_bridge(tla_text, traces=traces)

# Add test_scenarios to artifacts output:
artifacts["test_scenarios"] = [
    {"name": s.name, "setup": s.setup, "steps": s.steps,
     "expected_outcome": s.expected_outcome, "invariant_tested": s.invariant_tested}
    for s in result.test_scenarios
]

# v5: Load simulation traces (primary context for gen-tests)
sim_traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
if sim_traces_path.exists():
    artifacts["simulation_traces"] = json.loads(sim_traces_path.read_text())
else:
    artifacts["simulation_traces"] = []
```

#### Tests for 5A

```python
class TestTraceConversion:
    def test_counterexample_to_tlc_trace(self):
        from registry.one_shot_loop import CounterexampleTrace
        from registry.bridge import counterexample_to_tlc_trace

        ce = CounterexampleTrace(
            raw_trace="...",
            states=[
                {"state_num": 1, "label": "Init", "vars": {"x": "0", "dirty": "FALSE"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1", "dirty": "TRUE"}},
            ],
            violated_invariant="ValidState",
        )
        tlc = counterexample_to_tlc_trace(ce)
        assert tlc is not None
        assert tlc.invariant_violated == "ValidState"
        assert len(tlc.states) == 2
        assert tlc.states[0] == {"x": "0", "dirty": "FALSE"}

    def test_empty_counterexample_returns_none(self):
        from registry.one_shot_loop import CounterexampleTrace
        from registry.bridge import counterexample_to_tlc_trace

        ce = CounterexampleTrace(raw_trace="", states=[], violated_invariant=None)
        assert counterexample_to_tlc_trace(ce) is None
```

#### 4. `python/registry/traces.py` (new, v5) — Simulation trace types and prompt formatting

> **v5 addition:** Structured types for simulation traces and a formatter that produces
> the ranked-context prompt section. Simulation traces are the PRIMARY input for Phase 5C —
> they shift the LLM's job from "design test scenarios" to "translate verified traces."

```python
"""Simulation trace types and prompt formatting for test generation.

v5: TLC simulation traces are pre-verified concrete execution paths through
the state space. Each trace says: "starting from THIS state, applying THESE
actions, produces THIS result, and ALL invariants hold at every step."
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationTrace:
    """A TLC simulation trace — verified concrete scenario.

    Unlike CounterexampleTrace (which represents a violation), simulation
    traces represent VALID executions where all invariants hold.
    """
    states: list[dict[str, Any]]  # [{state_num, label, vars: {name: value}}]
    invariants_verified: list[str] = field(default_factory=list)

    @property
    def init_state(self) -> dict[str, str]:
        """The initial state — defines the test fixture."""
        return self.states[0]["vars"] if self.states else {}

    @property
    def final_state(self) -> dict[str, str]:
        """The final state — defines expected assertions."""
        return self.states[-1]["vars"] if self.states else {}

    @property
    def actions(self) -> list[str]:
        """The action sequence (labels after Init) — defines API calls."""
        return [s["label"] for s in self.states[1:]]

    @property
    def step_count(self) -> int:
        return len(self.states)


def format_traces_for_prompt(
    traces: list[SimulationTrace],
    invariant_names: list[str],
) -> str:
    """Format simulation traces as concrete verified scenarios for LLM prompt.

    This is the HIGHEST-RANKED context in the test generation prompt stack.
    Each trace is a pre-verified test case — the LLM translates (not invents).

    Context stack ranking (see Phase 5C):
      1. THIS — simulation traces (the WHAT)
      2. Python API signatures (the HOW)
      3. GWT + bridge artifacts + compiler hints (the WHY)
      4. Verified TLA+ spec (the FULL PICTURE)
      5. Structural patterns (the FORM)
    """
    sections = ["## Concrete Verified Scenarios\n"]
    sections.append(
        "Each trace below was generated by TLC from the verified model. "
        "ALL invariants hold at EVERY state. These are your test cases — "
        "translate each trace into Python API calls.\n"
    )

    for i, trace in enumerate(traces, 1):
        sections.append(
            f"### Trace {i} ({trace.step_count} steps, "
            f"tests {', '.join(invariant_names)})"
        )
        sections.append(f"Actions: {' → '.join(trace.actions)}\n")

        for state in trace.states:
            sections.append(f"State {state['state_num']}: <{state['label']}>")
            for var, val in state["vars"].items():
                sections.append(f"  /\\ {var} = {val}")
            sections.append("")

    return "\n".join(sections)


def load_simulation_traces(
    traces_data: list[list[dict[str, Any]]],
    invariant_names: list[str] | None = None,
) -> list[SimulationTrace]:
    """Load simulation traces from JSON data (as saved by cw9 loop).

    Args:
        traces_data: Raw JSON — list of traces, each a list of state dicts
        invariant_names: Names of invariants verified by the spec
    """
    return [
        SimulationTrace(
            states=trace_states,
            invariants_verified=invariant_names or [],
        )
        for trace_states in traces_data
    ]
```

#### Tests for simulation traces (v5)

```python
class TestSimulationTraces:
    """v5: Tests for SimulationTrace and format_traces_for_prompt."""

    def test_trace_properties(self):
        from registry.traces import SimulationTrace
        trace = SimulationTrace(
            states=[
                {"state_num": 1, "label": "Init", "vars": {"x": "0", "y": "{}"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1", "y": "{a}"}},
                {"state_num": 3, "label": "Done", "vars": {"x": "2", "y": "{a, b}"}},
            ],
            invariants_verified=["Inv1", "Inv2"],
        )
        assert trace.init_state == {"x": "0", "y": "{}"}
        assert trace.final_state == {"x": "2", "y": "{a, b}"}
        assert trace.actions == ["Step", "Done"]
        assert trace.step_count == 3

    def test_format_traces_for_prompt(self):
        from registry.traces import SimulationTrace, format_traces_for_prompt
        traces = [
            SimulationTrace(
                states=[
                    {"state_num": 1, "label": "Init", "vars": {"nodes": "{a,b,c}"}},
                    {"state_num": 2, "label": "Query", "vars": {"affected": "{a,b}"}},
                ],
            ),
        ]
        result = format_traces_for_prompt(traces, ["NoFalsePositives", "ValidState"])
        assert "Concrete Verified Scenarios" in result
        assert "Trace 1" in result
        assert "Init → Query" in result  # action label is from state 2
        assert "NoFalsePositives" in result
        assert "/\\ nodes = {a,b,c}" in result

    def test_load_simulation_traces(self):
        from registry.traces import load_simulation_traces
        raw = [
            [
                {"state_num": 1, "label": "Init", "vars": {"x": "0"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1"}},
            ],
            [
                {"state_num": 1, "label": "Init", "vars": {"x": "0"}},
            ],
        ]
        traces = load_simulation_traces(raw, invariant_names=["Inv1"])
        assert len(traces) == 2
        assert traces[0].step_count == 2
        assert traces[1].step_count == 1
        assert traces[0].invariants_verified == ["Inv1"]

    def test_empty_trace(self):
        from registry.traces import SimulationTrace
        trace = SimulationTrace(states=[])
        assert trace.init_state == {}
        assert trace.final_state == {}
        assert trace.actions == []
        assert trace.step_count == 0
```

### Phase 5B: TLA+ Condition Compiler (Prompt Enrichment Utility)

**Goal**: Compile TLA+ condition expressions from bridge artifacts into partial Python expression strings. These serve as **prompt hints** for the LLM test generation loop in Phase 5C — they give the LLM a head start on the syntactic translation so it can focus on the semantic gap (API binding, fixture design, scenario construction).

> **v4 reframing:** In v3, this compiler was the core of test generation. Analysis of the oracle
> code at `run_change_prop_loop.py:572-621` revealed that the semantic gap — binding TLA+ state
> variables like `affected` and `candidates` to actual Python API calls like
> `dag.query_affected_tests()` and `dag.query_impact().affected` — cannot be solved by regex
> substitution. The compiler handles the **easy 20%** (operator translation); the LLM handles the
> **hard 80%** (domain reasoning about what invariants mean relative to the Python API).

#### What the compiler does vs. what the LLM does

```
TLA+ condition: \A t \in affected : t \in candidates

Compiler output (Phase 5B):
  "all(t in candidates for t in affected)"
  ↑ Correct syntax, but 'affected' and 'candidates' are unbound variables

LLM output (Phase 5C):
  result = dag.query_affected_tests("d")
  impact = dag.query_impact("d")
  candidates = impact.affected | {"d"}
  for path in result:
      found = any(dag.test_artifacts.get(nid) == path for nid in candidates)
      assert found, f"NoFalsePositives: {path} not backed by candidate"
  ↑ Correct program with API binding, fixture setup, meaningful assertions
```

The compiler output appears in the LLM's prompt as a hint:

```
Verifier NoFalsePositives:
  TLA+ condition: \A t \in affected : t \in candidates
  Partial Python: all(t in candidates for t in affected)
  Applies to: ["affected", "candidates"]
  ↑ Your job: bind 'affected' and 'candidates' to real API calls
```

#### Code: `python/registry/tla_compiler.py`

Identical to v3 — same `compile_condition()`, `compile_assertions()`, `CompiledAssertion`, `CompileError`. Only the role changes: from "test generation engine" to "prompt enrichment utility."

<details>
<summary>Full code (unchanged from v3)</summary>

```python
"""Bounded TLA+ condition → Python assertion compiler.

Handles only the TLA+ operators that appear in bridge artifact conditions
across our existing modules. Raises CompileError on unknown operators.

v4 role: Prompt enrichment utility for Phase 5C's LLM loop.
The compiled expressions are partial hints, not the final test assertions.
"""

import re
from dataclasses import dataclass


class CompileError(Exception):
    """Raised when a TLA+ expression uses unsupported operators."""
    pass


@dataclass
class CompiledAssertion:
    """A compiled Python assertion string with metadata."""
    python_expr: str          # e.g., "all(x in impact_set for x in ...)"
    original_tla: str         # The raw TLA+ condition
    variables_used: list[str] # State variables referenced


def compile_condition(tla_expr: str, state_var: str = "state") -> CompiledAssertion:
    """Compile a TLA+ condition expression to a Python assertion string.

    Args:
        tla_expr: The TLA+ condition (from bridge artifacts verifiers.conditions)
        state_var: The Python variable name for the state dict (default: "state")

    Returns:
        CompiledAssertion with executable Python expression

    Raises:
        CompileError: If the expression uses unsupported TLA+ operators
    """
    original = tla_expr
    expr = tla_expr.strip()
    variables = []

    # Phase 1: Strip dirty guard (common in two-phase action models)
    expr = re.sub(r'dirty\s*=\s*TRUE\s*[/\\]+\s*', '', expr)

    # Phase 2: Boolean literals
    expr = expr.replace('TRUE', 'True').replace('FALSE', 'False')

    # Phase 3: Equality/inequality
    expr = re.sub(r'(?<!=)(?<!!)=(?!=)', '==', expr)  # = → == (avoid ==, !=)
    expr = expr.replace('#', '!=')  # TLA+ inequality

    # Phase 4: Logical operators
    expr = expr.replace('/\\', ' and ')
    expr = expr.replace('\\/', ' or ')
    # => (implication) — a => b ≡ (not a) or b
    expr = re.sub(r'(\S+)\s*=>\s*(\S+)', r'(not (\1) or (\2))', expr)

    # Phase 5: Set/sequence operators
    expr = expr.replace('\\in', ' in ')
    expr = expr.replace('\\notin', ' not in ')

    # Phase 6: Built-in functions
    expr = re.sub(r'Len\(', 'len(', expr)
    expr = re.sub(r'Cardinality\(', 'len(', expr)
    expr = re.sub(r'DOMAIN\s+(\w+)', r'set(\1.keys())', expr)

    # Phase 7: Tuple literals  <<a, b>> → (a, b)
    expr = re.sub(r'<<(.+?)>>', r'(\1)', expr)

    # Phase 8: Universal quantifier  \A x \in S : P(x)
    expr = re.sub(
        r'\\A\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'all((\3) for \1 in \2)',
        expr
    )

    # Phase 9: Existential quantifier  \E x \in S : P(x)
    expr = re.sub(
        r'\\E\s+(\w+)\s+\\in\s+(.+?)\s*:\s*(.+)',
        r'any((\3) for \1 in \2)',
        expr
    )

    # Phase 10: Record field access — state.field → state["field"]
    expr = re.sub(
        rf'{state_var}\.(\w+)',
        rf'{state_var}["\1"]',
        expr
    )

    # Extract variable names referenced
    variables = re.findall(rf'{state_var}\["(\w+)"\]', expr)

    # Validation: check for remaining TLA+ operators we don't handle
    remaining_tla = re.findall(r'\\[A-Za-z]+', expr)
    if remaining_tla:
        raise CompileError(
            f"Unsupported TLA+ operators: {remaining_tla} in expression: {original}"
        )

    return CompiledAssertion(
        python_expr=expr.strip(),
        original_tla=original,
        variables_used=list(set(variables)),
    )


def compile_assertions(
    verifiers: dict,
    state_var: str = "state",
) -> dict[str, CompiledAssertion]:
    """Compile all verifier conditions from bridge artifacts.

    Args:
        verifiers: The verifiers dict from bridge artifacts JSON
        state_var: Python variable name for state

    Returns:
        Dict mapping verifier name → CompiledAssertion.
        Verifiers with no conditions or with CompileError are skipped
        with a warning comment in the assertion.
    """
    results = {}
    for vname, vdata in verifiers.items():
        if not isinstance(vdata, dict):
            continue
        conditions = vdata.get("conditions", [])
        if not conditions:
            continue

        compiled_parts = []
        has_error = False
        for cond in conditions:
            try:
                compiled = compile_condition(cond, state_var)
                compiled_parts.append(compiled)
            except CompileError as e:
                has_error = True
                compiled_parts.append(CompiledAssertion(
                    python_expr=f"True  # SKIP: {e}",
                    original_tla=cond,
                    variables_used=[],
                ))

        # Combine conditions with 'and'
        combined_expr = " and ".join(f"({c.python_expr})" for c in compiled_parts)
        all_vars = []
        for c in compiled_parts:
            all_vars.extend(c.variables_used)

        results[vname] = CompiledAssertion(
            python_expr=combined_expr,
            original_tla=" /\\ ".join(c.original_tla for c in compiled_parts),
            variables_used=list(set(all_vars)),
        )

    return results
```

</details>

#### Tests: `python/tests/test_tla_compiler.py` (unchanged from v3)

Same 8 tests — the compiler's behavior is identical regardless of its architectural role.

<details>
<summary>Test code (unchanged from v3)</summary>

```python
class TestTlaCompiler:
    def test_basic_operators(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("x \\in S /\\ y = 3")
        assert "in" in r.python_expr
        assert "and" in r.python_expr
        assert "==" in r.python_expr

    def test_universal_quantifier(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("\\A x \\in S : x > 0")
        assert "all(" in r.python_expr
        assert "for x in S" in r.python_expr

    def test_record_field_access(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("state.count > 0", state_var="state")
        assert 'state["count"]' in r.python_expr

    def test_len_cardinality(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("Len(seq) > 0 /\\ Cardinality(S) = 3")
        assert "len(seq)" in r.python_expr
        assert "len(S)" in r.python_expr

    def test_boolean_literals(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("dirty = TRUE")
        assert "True" in r.python_expr

    def test_unsupported_operator_raises(self):
        from registry.tla_compiler import compile_condition, CompileError
        with pytest.raises(CompileError):
            compile_condition("\\CHOOSE x \\in S : P(x)")

    def test_dirty_guard_stripped(self):
        from registry.tla_compiler import compile_condition
        r = compile_condition("dirty = TRUE /\\ x > 0")
        assert "dirty" not in r.python_expr
        assert "x" in r.python_expr

    def test_compile_assertions_from_verifiers(self):
        from registry.tla_compiler import compile_assertions
        verifiers = {
            "NoFalsePositives": {
                "conditions": ["\\A t \\in affected : t \\in candidates"],
                "applies_to": ["affected", "candidates"],
            },
            "ValidState": {
                "conditions": ["Len(result) >= 0"],
                "applies_to": ["result"],
            },
        }
        results = compile_assertions(verifiers)
        assert "NoFalsePositives" in results
        assert "all(" in results["NoFalsePositives"].python_expr
        assert "ValidState" in results
        assert "len(result)" in results["ValidState"].python_expr
```

</details>

---

### Phase 5C: `cw9 gen-tests <gwt-id>` — LLM Test Generation Loop

**Goal**: Generate semantically meaningful pytest files by running an LLM-in-the-loop that understands the invariant intent relative to the Python API, verified mechanically by pytest.

> **v4 addition (replaces v3's template-based `generate_tests_from_artifacts()`).**
>
> The architecture is structurally isomorphic to `cw9 loop` (GWT → PlusCal → TLC):
>
> | Pipeline step | `cw9 loop` | `cw9 gen-tests` |
> |---|---|---|
> | Structured input | GWT text + schemas | Bridge artifacts + API context |
> | LLM output | PlusCal spec | pytest file |
> | Mechanical verifier | TLC model checker | pytest runner |
> | Retry signal | Counterexample trace | pytest error output |
> | Success condition | TLC PASS (all invariants hold) | pytest PASS (all tests pass) |
>
> **v5 enhancement:** The key insight is that TLC simulation traces shift the LLM's task
> from creative (design test scenarios) to mechanical (translate verified traces to API calls).
> Simulation traces are now the PRIMARY context in the prompt stack, ranked above bridge
> artifacts, compiler hints, and API signatures.

#### Architecture

```
                                                      ┌─ v5: PRIMARY CONTEXT ─┐
TLC sim traces ────┐                                  │ Concrete verified      │
  (v5: primary)    │                                  │ state sequences from   │
                   │                                  │ -simulate. Each is a   │
Bridge artifacts ──┤                                  │ pre-verified test case. │
                   │                                  └────────────────────────┘
TLA+ compiler ─────┤  Prompt          LLM             Verification
  (5B hints)       ├─ context ──→ [3 passes] ──→ pytest file ──→ compile()
                   │                                              │
API signatures ────┤                                    pytest --collect-only
                   │                                              │
GWT text ──────────┤                                     pytest -x (run)
                   │                                              │
TLA+ spec ─────────┘                                     ┌───────┴───────┐
  (v5: full picture)                                     │ PASS          │ FAIL
                                                         │               │
                                                         ▼               ▼
                                                      Done         Retry prompt
                                                                   (errors + code)
                                                                        │
                                                                        └──→ LLM ──→ ...
```

#### v5: Context Stack (ranked by impact on test quality)

| Rank | Context | Role | Why this rank |
|---|---|---|---|
| **1** | TLC simulation traces | THE WHAT — concrete input/output pairs | Each trace IS a test case. The LLM translates, not invents. |
| **2** | Python API source code | THE HOW — method signatures + return types | Binds trace variables to API calls. Without this, LLM guesses at method names. |
| **3** | GWT text + bridge artifacts + compiler hints | THE WHY — intent + starting expressions | Grounds the invariants' meaning. Compiler hints handle the easy 20% of translation. |
| **4** | Verified TLA+ spec | THE FULL PICTURE — complete state machine | Lossless view of the spec. Bridge artifacts are a lossy projection. |
| **5** | Structural patterns (generic) | THE FORM — fixture/assertion templates | Teaches form without leaking module-specific content. |

**What NOT to pass:**
- Full oracle test files — the LLM copies topologies instead of deriving from traces
- The project DAG — fixtures should be self-contained, not coupled to project state
- All bridge artifacts unfiltered — `operations` and `data_structures` are noisy; traces are the better input for scenario design

#### Three-pass generation

Each attempt uses three sequential LLM calls:

| Pass | Input | Output | Why separate |
|---|---|---|---|
| **1. Test plan** | **Simulation traces (primary)** + API signatures + compiler hints | Structured plan: trace-derived fixtures, assertions, scenarios | Reviewable intermediate artifact; forces LLM to reason about *what* to test before *how*. **v5: traces make this plan-from-traces, not plan-from-scratch.** |
| **2. Review** | Test plan + bridge verifiers (ground truth) | Revised plan with corrections | Catches semantic errors before code generation: "this fixture doesn't exercise the invariant", "this assertion tests the wrong variable" |
| **3. Code generation** | Reviewed plan + import context | Complete pytest file | Separates planning from syntax; plan provides specification |

On **retry** (after pytest failure), a single LLM call receives: previous code + error output + specific guidance. No re-planning — the plan is sound, the implementation had a bug.

#### Why 3 passes and not 1

A single "generate tests" prompt works for simple invariants (like `ValidState: Len(result) >= 0`). But for semantic invariants like `NoFalsePositives`, a single pass often produces:
- Correct-looking assertions that don't actually call the API
- Fixtures that compile but don't exercise the right code paths
- Tests that pass trivially (asserting on constants, not API results)

The plan pass forces the LLM to articulate *which API methods* to call and *what the invariant means* before writing code. The review pass checks that articulation against the bridge artifacts. This is chain-of-thought applied to test generation — the same reason the `cw9 loop` pipeline benefits from multi-step reasoning.

For latency-sensitive contexts, passes 1+2 can be collapsed into a single "plan and review" prompt.

#### 1. `python/registry/test_gen_loop.py` (new)

```python
"""LLM-in-the-loop test generation from bridge artifacts.

Parallel to cw9 loop (GWT → PlusCal → TLC):
  Bridge artifacts + API context → LLM → pytest file → pytest verifies → retry

The bridge artifacts constrain the LLM's generation the same way schemas
constrain PlusCal generation. The TLA+ compiler provides partial translations
as prompt hints, but the LLM handles the semantic gap: binding TLA+ invariants
to actual Python API calls.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from registry.tla_compiler import compile_assertions


@dataclass
class TestGenContext:
    """Everything the LLM needs to generate tests.

    v5: Context stack ranked by impact on test quality:
      1. simulation_traces — concrete verified scenarios (PRIMARY)
      2. api_context — method signatures + return types
      3. gwt_text + bridge_artifacts + compiler_hints — intent + starting expressions
      4. tla_spec_text — complete state machine (lossless)
      5. structural patterns — built into prompt templates (not stored here)
    """
    gwt_id: str
    gwt_text: dict          # {"given": ..., "when": ..., "then": ...}
    module_name: str
    bridge_artifacts: dict   # Full bridge JSON
    compiler_hints: dict     # verifier_name → {"python_expr", "original_tla", "variables_used"}
    api_context: str         # Target module imports + class/method signatures
    test_scenarios: list[dict[str, Any]]     # From counterexample trace pipeline (Phase 5A)
    simulation_traces: list[list[dict[str, Any]]]  # v5: From TLC -simulate (PRIMARY context for test generation)
    tla_spec_text: str = ""  # v5: Verified TLA+ spec content (full picture)
    output_dir: Path = Path(".")
    python_dir: Path = Path(".")


@dataclass
class VerifyResult:
    """Result of mechanical test verification."""
    passed: bool
    stage: str               # "compile", "collect", "run"
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    attempt: int = 0


def build_compiler_hints(bridge_artifacts: dict) -> dict:
    """Run the TLA+ compiler on bridge verifier conditions.

    Returns dict mapping verifier name → partial Python expression hint.
    CompileErrors are included as descriptive strings, not suppressed.
    """
    verifiers = bridge_artifacts.get("verifiers", {})
    compiled = compile_assertions(verifiers)
    hints = {}
    for vname, ca in compiled.items():
        hints[vname] = {
            "python_expr": ca.python_expr,
            "original_tla": ca.original_tla,
            "variables_used": ca.variables_used,
        }
    return hints


def discover_api_context(python_dir: Path, module_name: str) -> str:
    """Extract import paths + class/method signatures for the target module.

    Scans python_dir for the module's source files and extracts:
    - Import statements
    - Class definitions with method signatures
    - Public function signatures

    Returns a formatted string suitable for LLM prompt context.
    """
    # Convert TLA+ PascalCase module name to snake_case for Python file matching
    import re
    module_name_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', module_name).lower()
    candidates = list(python_dir.glob(f"registry/*{module_name_snake}*.py"))
    if not candidates:
        candidates = list(python_dir.glob(f"registry/**/*{module_name_snake}*.py"))
    if not candidates:
        return f"# No source found for module '{module_name}' in {python_dir}/registry/"

    lines = [f"# API context for module: {module_name}"]
    for src_path in candidates[:5]:  # Cap at 5 files
        lines.append(f"\n# --- {src_path.name} ---")
        try:
            source = src_path.read_text()
            for line in source.splitlines():
                stripped = line.strip()
                if (stripped.startswith(("import ", "from "))
                    or stripped.startswith(("class ", "def "))
                    or stripped.startswith("@")):
                    lines.append(line)
        except OSError:
            lines.append(f"# Could not read {src_path}")
    return "\n".join(lines)


def build_test_plan_prompt(ctx: TestGenContext) -> str:
    """Pass 1: Generate test plan from simulation traces + API context.

    v5: Context stack ranked by impact on test quality:
      1. TLC simulation traces — concrete verified scenarios (PRIMARY)
      2. Python API signatures — binding targets
      3. GWT text + compiler hints — intent + expression starting points
      4. TLA+ spec — full state machine (if available)
      5. Structural patterns — fixture/assertion templates

    The key shift: with simulation traces, the LLM translates
    verified state sequences into API calls (mechanical, verifiable)
    instead of inventing test scenarios from scratch (creative, error-prone).
    """
    from registry.traces import format_traces_for_prompt, load_simulation_traces

    verifiers = ctx.bridge_artifacts.get("verifiers", {})
    invariant_names = list(verifiers.keys())

    sections = [
        "Generate a test plan for verifying the following behavior.\n",
        "## Behavior (GWT)",
        f"  Given: {ctx.gwt_text.get('given', '')}",
        f"  When:  {ctx.gwt_text.get('when', '')}",
        f"  Then:  {ctx.gwt_text.get('then', '')}\n",
    ]

    # ── RANK 1: SIMULATION TRACES (the WHAT) ──────────────────────────
    # Primary context. Each trace IS a test case. The LLM translates, not invents.
    if ctx.simulation_traces:
        sim = load_simulation_traces(ctx.simulation_traces, invariant_names)
        sections.append(format_traces_for_prompt(sim, invariant_names))
        sections.append(
            "**Your task**: Translate each trace above into a pytest test.\n"
            "- The Init state defines your fixture (nodes, edges, artifacts)\n"
            "- The actions define your API calls\n"
            "- The final state defines your expected assertions\n"
            "- ALL invariants hold at every state — verify them\n"
            "- Do NOT invent topologies from scratch — derive from traces\n"
        )

    # ── RANK 2: PYTHON API (the HOW) ──────────────────────────────────
    # Binds trace variables to actual method calls.
    sections.append(f"## Available Python API\n{ctx.api_context}\n")

    # ── RANK 3: GWT + BRIDGE + COMPILER HINTS (the WHY) ──────────────
    # Intent + starting expressions. Compiler handles the easy 20%.
    if verifiers:
        sections.append("## Invariant Translations (starting points, NOT final assertions)")
        for vname, vdata in verifiers.items():
            conditions = vdata.get("conditions", []) if isinstance(vdata, dict) else []
            applies_to = vdata.get("applies_to", []) if isinstance(vdata, dict) else []
            sections.append(f"  {vname}:")
            sections.append(f"    TLA+ condition: {conditions}")
            sections.append(f"    Applies to: {applies_to}")
            if vname in ctx.compiler_hints:
                hint = ctx.compiler_hints[vname]
                sections.append(f"    Partial Python: {hint['python_expr']}")
                sections.append(
                    f"    ↑ Variables {hint['variables_used']} need binding to real API calls"
                )
        sections.append("")

    # ── RANK 4: TLA+ SPEC (the FULL PICTURE) ─────────────────────────
    # Lossless view. Bridge artifacts are a lossy projection.
    if ctx.tla_spec_text:
        sections.append(f"## Verified TLA+ Spec\n```tla\n{ctx.tla_spec_text}\n```\n")

    # ── RANK 5: STRUCTURAL PATTERNS (the FORM) ───────────────────────
    # Generic templates. NOT full oracle files (which cause copying).
    sections.append(
        "## Structural Patterns\n"
        "```python\n"
        "# Pattern: fixture construction from trace Init state\n"
        "def _make_dag(nodes, edges, artifacts):\n"
        "    dag = RegistryDag()\n"
        "    for nid in nodes:\n"
        "        dag.add_node(Node.behavior(nid, nid, 'g', 'w', 't'))\n"
        "    for src, dst in edges:\n"
        "        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))\n"
        "    dag.test_artifacts = artifacts\n"
        "    return dag\n\n"
        "# Pattern: invariant verification\n"
        "def test_invariant(dag):\n"
        "    result = dag.some_query('node_id')\n"
        "    assert property_of(result)\n\n"
        "# Pattern: error case\n"
        "def test_invalid_input(dag):\n"
        "    with pytest.raises(NodeNotFoundError):\n"
        "        dag.some_query('nonexistent')\n"
        "```\n"
    )

    # Fallback: if no simulation traces, fall back to counterexample scenarios
    if not ctx.simulation_traces and ctx.test_scenarios:
        sections.append("### Trace-derived Scenarios (from TLC counterexamples)")
        for s in ctx.test_scenarios:
            sections.append(f"  - {s.get('name', 'unnamed')}: {s.get('expected_outcome', '')}")
        sections.append("")

    # ── INSTRUCTIONS ──────────────────────────────────────────────────
    if ctx.simulation_traces:
        sections.append(
            "## Instructions\n"
            "Produce a structured test plan with:\n"
            "1. **Trace-derived fixtures**: For each simulation trace, construct a fixture "
            "matching the Init state (specific nodes, edges, test_artifacts).\n"
            "2. **Trace-derived tests**: For each trace, a test that:\n"
            "   - Builds the fixture from Init state variables\n"
            "   - Calls API methods matching the action sequence\n"
            "   - Asserts the result matches the final state\n"
            "   - Verifies ALL invariants hold\n"
            "3. **Invariant verifiers**: For each verifier, a dedicated test method that:\n"
            "   - Exercises the invariant across ≥2 trace-derived topologies\n"
            "   - Binds TLA+ variables to real API calls (see Partial Python hints above)\n"
            "4. **Edge cases**: Isolated nodes, empty DAGs, missing artifacts, diamond patterns\n"
            "   (derive from traces where possible, invent minimally where not)\n"
        )
    else:
        sections.append(
            "## Instructions\n"
            "Produce a structured test plan with:\n"
            "1. **Fixtures**: What DAG topologies or state objects to construct. "
            "Include specific nodes, edges, and test_artifacts mappings.\n"
            "2. **Invariant verifiers**: For each verifier, describe:\n"
            "   - Which API method(s) to call\n"
            "   - How to bind TLA+ state variables to API results\n"
            "   - What assertion to make\n"
            "3. **Scenario tests**: Concrete test cases covering:\n"
            "   - Happy path (invariant holds)\n"
            "   - Edge cases (empty DAG, isolated nodes, diamond topologies)\n"
            "   - Boundary conditions\n"
        )

    return "\n".join(sections)


def build_review_prompt(test_plan: str, ctx: TestGenContext) -> str:
    """Pass 2: Review the test plan for semantic correctness."""
    return (
        "Review this test plan for semantic correctness.\n\n"
        f"## Test Plan\n{test_plan}\n\n"
        f"## Bridge Verifiers (ground truth)\n"
        f"{json.dumps(ctx.bridge_artifacts.get('verifiers', {}), indent=2)}\n\n"
        "## Review Criteria\n"
        "1. Does each verifier test actually verify the TLA+ invariant's *intent*, "
        "not just its syntax? (e.g., NoFalsePositives means 'every returned test path "
        "corresponds to a node in the impact set')\n"
        "2. Are the fixture topologies sufficient to exercise the invariant? "
        "(linear chain alone may not catch diamond-path bugs)\n"
        "3. Are the API bindings correct? (right method, right arguments, right return type)\n"
        "4. Are edge cases covered? (empty set, single node, missing artifacts)\n\n"
        "Output the revised test plan with corrections. If the plan is correct, "
        "output it unchanged with a note that it passed review.\n"
    )


def build_codegen_prompt(reviewed_plan: str, ctx: TestGenContext) -> str:
    """Pass 3: Emit a complete pytest file from the reviewed plan."""
    return (
        f"Generate a complete, runnable pytest file from this test plan.\n\n"
        f"## Reviewed Test Plan\n{reviewed_plan}\n\n"
        f"## API Context\n{ctx.api_context}\n\n"
        f"## Requirements\n"
        f"- Module: {ctx.module_name}, GWT ID: {ctx.gwt_id}\n"
        f"- Use `import pytest` and relevant imports from the API context\n"
        f"- Each verifier becomes a test function or method with a real assertion\n"
        f"- Fixtures construct concrete DAG/state objects (not mocks)\n"
        f"- Include docstrings referencing the TLA+ invariant being tested\n"
        f"- Code must pass `compile()`, `pytest --collect-only`, and `pytest -x`\n"
        f"- Output ONLY the Python code, no markdown fences or explanation\n"
    )


def build_retry_prompt(
    previous_code: str,
    verify_result: VerifyResult,
    ctx: TestGenContext,
) -> str:
    """Build retry prompt from previous attempt's errors."""
    return (
        f"The previous test file failed at the '{verify_result.stage}' stage.\n\n"
        f"## Previous code\n```python\n{previous_code}\n```\n\n"
        f"## Errors\n{chr(10).join(verify_result.errors)}\n\n"
        f"## stderr\n{verify_result.stderr[:2000]}\n\n"
        f"## Instructions\n"
        f"Fix the errors and output the corrected Python file.\n"
        f"Output ONLY the Python code, no markdown fences or explanation.\n"
    )


def verify_test_file(
    test_path: Path, python_dir: Path,
    collect_timeout: int = 30, run_timeout: int = 120,
) -> VerifyResult:
    """Three-stage mechanical verification of a generated test file.

    Stage 1: compile() — syntax check
    Stage 2: pytest --collect-only — test discovery
    Stage 3: pytest -x — run tests (fail fast)
    """
    code = test_path.read_text()

    # Stage 1: Compile
    try:
        compile(code, str(test_path), "exec")
    except SyntaxError as e:
        return VerifyResult(
            passed=False, stage="compile",
            errors=[f"SyntaxError: {e.msg} (line {e.lineno})"],
        )

    # Stage 2: Collect
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "--collect-only", "-q"],
        capture_output=True, text=True, cwd=str(python_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(
            passed=False, stage="collect",
            errors=[f"pytest --collect-only failed (rc={result.returncode})"],
            stdout=result.stdout, stderr=result.stderr,
        )

    # Stage 3: Run
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-x", "-v"],
        capture_output=True, text=True, cwd=str(python_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(
            passed=False, stage="run",
            errors=[f"pytest -x failed (rc={result.returncode})"],
            stdout=result.stdout, stderr=result.stderr,
        )

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)


def _extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response, stripping markdown fences if present."""
    lines = response.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


async def run_test_gen_loop(
    ctx: TestGenContext,
    call_llm,  # async (prompt: str) -> str — injected LLM caller
    max_attempts: int = 3,
    session_dir: Optional[Path] = None,
) -> VerifyResult:
    """Run the LLM test generation loop.

    Args:
        ctx: Test generation context (bridge artifacts, API context, etc.)
        call_llm: Async function that takes a prompt and returns LLM response.
                  Same signature as used in loop_runner.py.
        max_attempts: Maximum generation attempts before giving up.
        session_dir: Optional directory for saving session transcripts.

    Returns:
        VerifyResult with passed=True if tests were generated and verified,
        or passed=False with error details.
    """
    test_path = ctx.output_dir / f"test_{ctx.gwt_id.replace('-', '_')}.py"
    ctx.output_dir.mkdir(parents=True, exist_ok=True)

    # Pass 1: Generate test plan
    plan_prompt = build_test_plan_prompt(ctx)
    test_plan = await call_llm(plan_prompt)

    # Pass 2: Review
    review_prompt = build_review_prompt(test_plan, ctx)
    reviewed_plan = await call_llm(review_prompt)

    # Pass 3: Generate code
    codegen_prompt = build_codegen_prompt(reviewed_plan, ctx)
    code_response = await call_llm(codegen_prompt)
    test_code = _extract_code_from_response(code_response)
    test_path.write_text(test_code)

    if session_dir:
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / f"{ctx.gwt_id}_plan.txt").write_text(test_plan)
        (session_dir / f"{ctx.gwt_id}_review.txt").write_text(reviewed_plan)

    # Verify
    result = verify_test_file(test_path, ctx.python_dir)
    attempt = 1

    # Retry loop
    while not result.passed and attempt < max_attempts:
        attempt += 1
        retry_prompt = build_retry_prompt(test_code, result, ctx)
        code_response = await call_llm(retry_prompt)
        test_code = _extract_code_from_response(code_response)
        test_path.write_text(test_code)

        if session_dir:
            (session_dir / f"{ctx.gwt_id}_attempt{attempt}.py").write_text(test_code)
            (session_dir / f"{ctx.gwt_id}_attempt{attempt}_errors.txt").write_text(
                "\n".join(result.errors) + "\n" + result.stderr
            )

        result = verify_test_file(test_path, ctx.python_dir)

    result.attempt = attempt
    return result
```

#### 2. CLI command — `cmd_gen_tests()`

```python
def cmd_gen_tests(args: argparse.Namespace) -> int:
    import asyncio

    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    gwt_id = args.gwt_id

    # Load bridge artifacts
    artifact_path = ctx.artifact_dir / f"{gwt_id}_bridge_artifacts.json"
    if not artifact_path.exists():
        print(f"No bridge artifacts found: {artifact_path}", file=sys.stderr)
        print(f"Run: cw9 bridge {gwt_id}", file=sys.stderr)
        return 1

    bridge_artifacts = json.loads(artifact_path.read_text())
    module_name = bridge_artifacts.get("module_name", gwt_id)

    # Load GWT text from DAG
    dag_path = ctx.state_root / "dag.json"
    gwt_text = {"given": "", "when": "", "then": ""}
    if dag_path.exists():
        dag = RegistryDag.load(dag_path)
        if gwt_id in dag.nodes:
            node = dag.nodes[gwt_id]
            gwt_text = {
                "given": node.given or "",
                "when": node.when or "",
                "then": node.then or "",
            }

    # Build context
    from registry.test_gen_loop import (
        TestGenContext, build_compiler_hints, discover_api_context,
        run_test_gen_loop,
    )

    compiler_hints = build_compiler_hints(bridge_artifacts)
    api_context = discover_api_context(ctx.python_dir, module_name)
    test_scenarios = bridge_artifacts.get("test_scenarios", [])

    # v5: Load simulation traces (PRIMARY context for test generation)
    simulation_traces = bridge_artifacts.get("simulation_traces", [])
    if not simulation_traces:
        # Fallback: check spec dir directly (in case bridge was run before v5)
        sim_traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
        if sim_traces_path.exists():
            simulation_traces = json.loads(sim_traces_path.read_text())

    # v5: Load TLA+ spec text (full picture, rank 4 context)
    tla_spec_text = ""
    spec_path = ctx.spec_dir / f"{gwt_id}.tla"
    if spec_path.exists():
        tla_spec_text = spec_path.read_text()

    gen_ctx = TestGenContext(
        gwt_id=gwt_id,
        gwt_text=gwt_text,
        module_name=module_name,
        bridge_artifacts=bridge_artifacts,
        compiler_hints=compiler_hints,
        api_context=api_context,
        test_scenarios=test_scenarios,
        simulation_traces=simulation_traces,
        tla_spec_text=tla_spec_text,
        output_dir=ctx.test_output_dir,
        python_dir=ctx.python_dir,
    )

    # LLM caller — same pattern as loop_runner.py
    from registry.loop_runner import call_llm

    session_dir = ctx.state_root / "sessions"
    result = asyncio.run(run_test_gen_loop(
        gen_ctx, call_llm,
        max_attempts=args.max_attempts,
        session_dir=session_dir,
    ))

    if result.passed:
        test_path = ctx.test_output_dir / f"test_{gwt_id.replace('-', '_')}.py"
        print(f"Generated: {test_path} ({result.attempt} attempt(s))")
        return 0
    else:
        print(f"Failed after {result.attempt} attempts", file=sys.stderr)
        for err in result.errors:
            print(f"  {err}", file=sys.stderr)
        return 1
```

#### 3. Argparse wiring

```python
p_gen = sub.add_parser("gen-tests", help="Generate pytest file from bridge artifacts (LLM loop)")
p_gen.add_argument("gwt_id", help="GWT behavior ID")
p_gen.add_argument("target_dir", nargs="?", default=".")
p_gen.add_argument("--max-attempts", type=int, default=3, help="Max generation attempts")
```

#### Tests

```python
class TestGenTests:
    def test_gen_tests_no_artifacts_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        rc = main(["gen-tests", "gwt-0001", str(target_dir)])
        assert rc == 1
        assert "no bridge artifacts" in capsys.readouterr().err.lower()

    def test_verify_catches_syntax_error(self, tmp_path):
        """verify_test_file Stage 1: catches SyntaxError."""
        from registry.test_gen_loop import verify_test_file
        bad = tmp_path / "test_bad.py"
        bad.write_text("def test_broken(:\n    pass\n")
        result = verify_test_file(bad, tmp_path)
        assert not result.passed
        assert result.stage == "compile"
        assert "SyntaxError" in result.errors[0]

    def test_verify_passes_valid_tests(self, tmp_path):
        """verify_test_file Stage 3: valid tests pass all stages."""
        from registry.test_gen_loop import verify_test_file
        good = tmp_path / "test_good.py"
        good.write_text("def test_ok(): assert True\n")
        result = verify_test_file(good, tmp_path)
        assert result.passed
        assert result.stage == "run"

    def test_verify_catches_failing_tests(self, tmp_path):
        """verify_test_file Stage 3: failing test returns stage='run'."""
        from registry.test_gen_loop import verify_test_file
        fail = tmp_path / "test_fail.py"
        fail.write_text("def test_bad(): assert False\n")
        result = verify_test_file(fail, tmp_path)
        assert not result.passed
        assert result.stage == "run"

    def test_build_compiler_hints(self):
        """Compiler hints are generated from bridge verifier conditions."""
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
        assert "all(" in hints["NoFalsePositives"]["python_expr"]

    def test_prompt_includes_compiler_hints(self):
        """Test plan prompt includes compiler hints with binding instructions."""
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
                    "python_expr": "all(t in candidates for t in affected)",
                    "original_tla": "\\A t \\in affected : t \\in candidates",
                    "variables_used": ["affected", "candidates"],
                },
            },
            api_context="from registry.dag import RegistryDag\n",
            test_scenarios=[],
            simulation_traces=[],
            output_dir=Path("/tmp"),
            python_dir=Path("/tmp"),
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
            python_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        # Simulation traces should appear BEFORE API context
        traces_pos = prompt.find("Concrete Verified Scenarios")
        api_pos = prompt.find("Available Python API")
        assert traces_pos != -1, "Simulation traces section missing from prompt"
        assert api_pos != -1, "API section missing from prompt"
        assert traces_pos < api_pos, "Traces must appear before API context"
        # Should include trace content
        assert "Init" in prompt
        assert "QueryAffected" in prompt
        assert "Translate each trace" in prompt
        # Should include structural patterns
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
            simulation_traces=[],  # empty — no traces available
            output_dir=Path("/tmp"),
            python_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        assert "Concrete Verified Scenarios" not in prompt
        assert "Fixtures" in prompt  # falls back to generic instructions

    def test_extract_code_strips_fences(self):
        """LLM responses wrapped in markdown fences are stripped."""
        from registry.test_gen_loop import _extract_code_from_response
        response = "```python\ndef test_x(): pass\n```"
        assert _extract_code_from_response(response) == "def test_x(): pass"

    def test_extract_code_bare_python(self):
        """Bare Python responses are returned unchanged."""
        from registry.test_gen_loop import _extract_code_from_response
        response = "def test_x(): pass"
        assert _extract_code_from_response(response) == "def test_x(): pass"
```

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_tla_compiler.py -v` — all 8 compiler tests pass
- [ ] `python3 -m pytest tests/test_cli.py::TestGenTests -v` — all 10 tests pass (v5: +2 trace prompt tests)
- [ ] `python3 -m pytest tests/test_trace_conversion.py -v` — trace pipeline tests pass
- [ ] `python3 -m pytest tests/test_simulation_traces.py -v` — 4 simulation trace type tests pass (v5)
- [ ] `verify_test_file()` catches syntax errors, collection failures, and test failures

#### Manual (requires LLM access):
- [ ] Run `cw9 gen-tests gwt-0021` on change_propagation — generated tests should be **behaviorally equivalent** to `run_change_prop_loop.py:485-717` output
- [ ] Generated tests include concrete DAG fixtures derived from **TLC simulation traces** — not invented from scratch (v5)
- [ ] Generated `_verify_NoFalsePositives` equivalent calls `dag.query_affected_tests()` and `dag.query_impact()` — not just `all(t in candidates for t in affected)` with unbound variables
- [ ] Retry works: deliberately break an import, verify LLM self-corrects on next attempt
- [ ] With simulation traces available: test fixtures match Init state topologies from TLC output (v5)

### Oracle Validation

The existing `generate_tests()` in `run_change_prop_loop.py:485-717` is the oracle. For each existing module, the LLM-generated tests should:

```
Criterion                        | Oracle example                           | LLM must produce
---------------------------------|------------------------------------------|------------------
Concrete fixture construction    | _make_chain_dag(), _make_diamond_dag()   | Similar topology builders
API-bound invariant verification | _verify_NoFalsePositives calls           | Equivalent API calls
                                 | dag.query_affected_tests() +             |
                                 | dag.query_impact()                       |
Scenario coverage                | test_upstream_change_propagates,         | ≥3 scenario tests
                                 | test_diamond_leaf_change, etc.           | covering chain/diamond/edge
Edge cases                       | test_no_downstream_tests_empty,          | Empty set, missing artifacts,
                                 | test_no_false_positives_no_artifact      | isolated node cases
```

The generated tests need NOT be identical to the oracle — they must be **behaviorally equivalent**: same invariants verified, same API surface exercised, same edge cases covered.

---

╔═══════════════════════════════════════╗
║  PHASE 6: cw9 test                   ║
╚═══════════════════════════════════════╝

### Overview

Runs generated tests. With `--node`, uses `query_affected_tests()` to run only tests affected by that node. Without `--node`, runs all generated tests.

### Changes Required

#### 1. `python/registry/cli.py` — `cmd_test()`

```python
def cmd_test(args: argparse.Namespace) -> int:
    import subprocess

    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    ctx = ProjectContext.from_target(target)
    test_dir = ctx.test_output_dir

    if not test_dir.exists() or not list(test_dir.glob("test_*.py")):
        print(f"No generated tests in {test_dir}", file=sys.stderr)
        print("Run: cw9 gen-tests <gwt-id>", file=sys.stderr)
        return 1

    test_files = []

    if args.node_id:
        from registry.dag import RegistryDag
        dag_path = ctx.state_root / "dag.json"
        if not dag_path.exists():
            print("No DAG found. Run: cw9 extract", file=sys.stderr)
            return 1
        dag = RegistryDag.load(dag_path)

        # Populate test_artifacts from bridge artifact files
        for artifact_file in ctx.artifact_dir.glob("*_bridge_artifacts.json"):
            data = json.loads(artifact_file.read_text())
            gwt_id = data.get("gwt_id", "")
            test_path = test_dir / f"test_{gwt_id.replace('-', '_')}.py"
            if test_path.exists():
                dag.test_artifacts[gwt_id] = str(test_path)

        affected = dag.query_affected_tests(args.node_id)
        if not affected:
            print(f"No tests affected by {args.node_id}")
            return 0
        test_files = affected
        print(f"Running {len(test_files)} affected test(s) for {args.node_id}")
    else:
        test_files = [str(f) for f in sorted(test_dir.glob("test_*.py"))]
        print(f"Running {len(test_files)} generated test(s)")

    result = subprocess.run(
        ["python3", "-m", "pytest"] + test_files + ["-v"],
        cwd=str(ctx.python_dir),
    )
    return result.returncode
```

#### 2. Argparse wiring

```python
p_test = sub.add_parser("test", help="Run generated tests (smart targeting optional)")
p_test.add_argument("--node", dest="node_id", help="Only run tests affected by this node")
p_test.add_argument("target_dir", nargs="?", default=".")
```

### Tests

```python
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
```

### Success Criteria

#### Automated:
- [ ] `python3 -m pytest tests/test_cli.py::TestTest -v` — all pass

#### Manual:
- [ ] Full pipeline: `cw9 extract && cw9 loop gwt-0024 && cw9 bridge gwt-0024 && cw9 gen-tests gwt-0024 && cw9 test`
- [ ] Smart targeting: `cw9 test --node db-b7r2` runs only affected tests

---

## Testing Strategy

### Unit Tests (per phase):
- Phase 0: 11 tests in `test_register_gwt.py` (register_gwt, register_requirement, ID allocation, save/load)
- Phase 1: 3 tests in `test_context.py` (config.toml parsing)
- Phase 2: 6 tests in `test_cli.py::TestExtract` (including 2 merge tests)
- Phase 3: 2 tests in `test_cli.py::TestLoop` (error paths) + 3 tests in `TestSimulationTraceParser` (v5)
- Phase 4: 3 tests in `test_cli.py::TestBridge`
- Phase 5A: 2 tests in `test_trace_conversion.py` + 4 tests in `test_simulation_traces.py` (v5)
- Phase 5B: 8 tests in `test_tla_compiler.py` (compiler unchanged, role reframed as prompt enrichment)
- Phase 5C: 10 tests in `test_cli.py::TestGenTests` (v5: +2 trace prompt tests)
- Phase 6: 2 tests in `test_cli.py::TestTest`
- **Total: ~54 new tests → 346 total** (v5: +9 from simulation trace support)

### New files:
- `python/tests/test_register_gwt.py` — library API tests
- `python/tests/test_tla_compiler.py` — TLA+ → Python compiler tests
- `python/tests/test_trace_conversion.py` — CounterexampleTrace → TlcTrace tests
- `python/tests/test_simulation_traces.py` — SimulationTrace types + prompt formatting (v5)
- `python/registry/tla_compiler.py` — bounded TLA+ condition compiler (prompt enrichment utility)
- `python/registry/test_gen_loop.py` — LLM-in-the-loop test generation loop
- `python/registry/loop_runner.py` — common loop logic with proper retry
- `python/registry/traces.py` — simulation trace types + prompt formatting (v5)

### Integration Tests (manual, requires Claude Agent SDK):
```bash
# 1. Initialize and extract
cw9 init /tmp/testproj
cw9 extract /tmp/testproj

# 2. Register a GWT (library API — via Python script or upstream)
python3 -c "
import sys; sys.path.insert(0, 'python')
from registry.dag import RegistryDag
from registry.context import ProjectContext
ctx = ProjectContext.from_target('/tmp/testproj')
dag = RegistryDag.load(ctx.state_root / 'dag.json')
gwt_id = dag.register_gwt(
    given='a user submits a form',
    when='validation runs',
    then='errors are displayed inline',
)
dag.save(ctx.state_root / 'dag.json')
print(f'Registered: {gwt_id}')
"

# 3. Run pipeline
cw9 loop gwt-0024 /tmp/testproj
cw9 bridge gwt-0024 /tmp/testproj
cw9 gen-tests gwt-0024 /tmp/testproj
cw9 test /tmp/testproj

# 4. Verify re-extract preserves registered GWT
cw9 extract /tmp/testproj  # Should print "preserved 1 registered node(s)"
```

## Implementation Order

```
Phase 0 (register_gwt) ──→ Phase 1 (config.toml) ──→ Phase 2 (extract + merge)
                                                           │
                                                           ▼
                                     Phase 3 (loop + simulate) ──→ Phase 4 (bridge)
                                         │                             │
                                         │ counterexample              │ bridge artifacts
                                         │ traces                      │ + sim traces (v5)
                                         ▼                             ▼
                              Phase 5A (trace pipe         Phase 5B (TLA+ compiler)
                                + sim trace types [v5])          │
                                    │                            │
                                    └───────┬────────────────────┘
                                            │ prompt context
                                            │ (v5: sim traces = PRIMARY)
                                            ▼
                              Phase 5C (gen-tests LLM loop) → Phase 6 (test)
```

Phase 0 is the library foundation — everything else depends on GWTs being in the DAG.
Phase 1 unlocks ergonomic CLI use for all subsequent phases.
Phase 2 is required by Phase 3 (loop loads saved DAG) — now includes merge logic.
Phases 3→4 are the pipeline chain. **Phase 3 now runs TLC `-simulate` after PASS (v5)**, generating concrete traces that flow through Phase 4 into 5C.
Phase 5A connects the trace type systems (mechanical plumbing). **v5 adds `SimulationTrace` type + `format_traces_for_prompt()`.**
Phase 5B builds the TLA+ compiler as a prompt enrichment utility (same code as v3, reframed role).
Phase 5C is the core test generation — LLM loop consuming **simulation traces (primary, v5)** + 5B hints + Phase 4's bridge artifacts.
Phase 6 is independent but most useful after Phase 5C.

## Performance Considerations

- `cw9 extract` re-extracts full DAG (~0.2s for 96 nodes) + merge scan (~negligible). Acceptable.
- `cw9 loop` bottlenecked by LLM calls (~30s/attempt, up to 5 retries). **v5: adds ~10s for TLC `-simulate num=10` after PASS** — one-time cost per GWT, amortized by vastly better test generation context.
- `register_gwt()` is O(n) for ID scan — negligible at current scale.
- `cw9 test --node` loads DAG + computes closure (~0.1s). Fast.
- `tla_compiler.compile_condition()` is regex-based, O(n) in expression length. Fast.
- `cw9 gen-tests` bottlenecked by LLM calls (~30s/pass × 3 passes + retries). Similar to `cw9 loop`. **v5: simulation traces may reduce retry count by giving LLM concrete scenarios instead of requiring invention.**
- `merge_registered_nodes()` is O(n) in old DAG size. Negligible.
- `parse_simulation_traces()` is O(n) in TLC output length. Negligible for num=10.

## v3 Changelog

| Issue | What was wrong | Fix |
|---|---|---|
| **#1** Node.requirement() sig | Plan called `Node.requirement(req_id, name, text)` — 3 args. Actual factory is `requirement(id, text)` — 2 args. Tests also passed 3 args. | Added optional `name` param to `Node.requirement()` with `""` default. Fixed `register_requirement()` to call `(req_id, text, name)`. Fixed tests. |
| **#2** extract overwrites GWTs | `SchemaExtractor.extract()` starts with fresh `RegistryDag()`. Plan said "future enhancement." | Added `merge_registered_nodes()` to `RegistryDag`. `cmd_extract()` now loads old DAG, extracts fresh, merges back registered nodes. Added 2 tests. |
| **#3** process_response() wrong | Plan called `process_response(response, gwt_id)` — missing `cfg_text`. Used `status.retry_prompt` — field doesn't exist. | Fixed to `process_response(response, module_name, cfg_text)`. Added `build_retry_prompt()` that constructs from `status.counterexample` + `status.error`. |
| **#4** test gen regression | Plan emitted `assert state is not None` stubs. Existing code has real `_verify_*` methods. Bridge data unused. Trace pipeline disconnected. | v3: Rewrote Phase 5 into 4 parts: 5A (trace pipeline), 5B (TLA+ compiler), 5C (fixtures), 5D (scenario tests). v4: see below. |

## v4 Changelog

| Issue | What was wrong in v3 | Fix |
|---|---|---|
| **#5** Compiler can't bridge semantic gap | v3's Phase 5B regex compiler produces correct *expressions* (`all(t in candidates for t in affected)`) but unbound variables — no API binding, no fixture construction, no domain reasoning. The oracle at `run_change_prop_loop.py:572-621` shows that `_verify_NoFalsePositives` requires calling `dag.query_affected_tests()` + `dag.query_impact()` and building candidate sets — semantic work that regex can't do. | Reframed 5B as prompt enrichment utility (same code, different role). Replaced 5C/5D templates with Phase 5C: LLM-in-the-loop test generation, structurally parallel to `cw9 loop`. Bridge artifacts become prompt context; pytest replaces TLC as verifier. |
| **#6** No verification of generated tests | v3's `generate_tests_from_artifacts()` wrote a file and returned — no compile check, no collection check, no runtime check. Broken tests would only be caught at `cw9 test` time. | Added 3-stage `verify_test_file()`: `compile()` → `pytest --collect-only` → `pytest -x`. Retry loop feeds errors back to LLM. |
| **#7** Template ceiling | v3's template approach could produce verifier stubs and scenario tests, but hit a ceiling: operations got `assert state is not None` stubs, verifiers without compilable conditions got stubs, and the "real" assertions were only as good as the regex compiler. No path to improvement without rewriting the compiler. | LLM loop has no ceiling — it can generate arbitrarily complex test logic. The compiler hints give it a head start; the verification loop ensures correctness. Improvement path: better prompts, not more regex. |

## v5 Changelog

> **Key insight:** When TLC verifies a model with N distinct states and passes, it has visited
> every reachable state and confirmed every invariant holds at each one. We previously threw
> all of that away — we captured "pass" and a state count. TLC's `-simulate` mode outputs
> concrete execution traces through the state space on passing models. Each trace IS a test
> case: "starting from THIS state, applying THESE actions, produces THIS result, and ALL
> invariants hold." The LLM's job shifts from "design test scenarios" (creative) to
> "translate this state trace into Python API calls" (mechanical, verifiable).

| Issue | What was wrong in v4 | Fix |
|---|---|---|
| **#8** TLC as pass/fail gate only | After TLC PASS, we saved only the spec and a state count — the entire explored state space was discarded. Simulation traces (concrete verified execution paths) were never generated, so Phase 5C had to rely on the LLM inventing test scenarios from scratch. | Phase 3: after PASS, run `run_tlc_simulate()` with `-simulate num=10`. Parse output with `parse_simulation_traces()` (reuses existing `_STATE_HEADER_RE`/`_VAR_ASSIGN_RE` regexes). Save to `.cw9/specs/<gwt-id>_sim_traces.json`. |
| **#9** LLM invents test topologies | v4's Phase 5C prompt led with bridge artifacts and asked the LLM to "design test scenarios" — a creative task requiring domain reasoning about what interesting topologies look like. The LLM often produced correct-looking but shallow fixtures (linear chains only, no diamonds, no edge cases). | Restructured prompt with ranked context stack: simulation traces PRIMARY (rank 1), API signatures (rank 2), bridge+compiler hints (rank 3), TLA+ spec (rank 4), structural patterns (rank 5). Traces provide concrete Init→Action→Result sequences; LLM translates rather than invents. |
| **#10** No simulation trace types | `CounterexampleTrace` (from failures) was the only trace type. No type for verified execution paths, no formatter for prompt inclusion, no loader from JSON. | Added `python/registry/traces.py`: `SimulationTrace` dataclass with `init_state`/`final_state`/`actions` properties, `format_traces_for_prompt()` for ranked prompt context, `load_simulation_traces()` for JSON deserialization. |
| **#11** `TestGenContext` missing trace fields | v4's `TestGenContext` had no fields for simulation traces or the TLA+ spec text, so `build_test_plan_prompt()` couldn't include them even if they were available. | Added `simulation_traces: list` and `tla_spec_text: str` fields. `cmd_gen_tests()` loads both from `.cw9/specs/` artifacts. Graceful fallback to v4 behavior when traces are unavailable. |
| **#12** Oracle-based few-shot leaked topologies | Analysis showed that passing full oracle test files (e.g., `run_change_prop_loop.py:485-717`) as context caused the LLM to copy specific topologies rather than deriving test cases from the verified state space. | Replaced with structural patterns (rank 5): generic fixture/assertion/error templates that teach FORM without leaking module-specific topology choices. The "NOT doing" table now explicitly prohibits oracle file inclusion. |

## References

- Handoff: `thoughts/searchable/shared/handoffs/general/2026-03-10_07-57-53_stage0-1-projectcontext-cw9-init.md`
- `python/registry/types.py:64-69` — `Node.behavior()` factory
- `python/registry/types.py:72-73` — `Node.requirement()` factory (2 args: id, text)
- `python/registry/dag.py:36-40` — `add_node()` (no duplicate check)
- `python/registry/dag.py:242-259` — `query_affected_tests()`
- `python/registry/extractor.py:142-165` — `SchemaExtractor.extract()` (fresh RegistryDag)
- `python/registry/extractor.py:414-997` — `_self_describe()` (all hardcoded GWT IDs)
- `python/registry/context.py:60-76` — `from_target()`
- `python/registry/bridge.py:52-56` — `TlcTrace` dataclass
- `python/registry/bridge.py:553-565` — `_invariant_to_condition()` (5 text subs)
- `python/registry/bridge.py:582-622` — `translate_traces()` (TlcTrace → TestScenario)
- `python/registry/bridge.py:661-689` — `run_bridge()`, `BridgeResult`
- `python/registry/one_shot_loop.py:64-70` — `CounterexampleTrace` dataclass
- `python/registry/one_shot_loop.py:84-93` — `LoopStatus` (no retry_prompt field)
- `python/registry/one_shot_loop.py:615-622` — `process_response(llm_response, module_name, cfg_text)`
- `python/run_change_prop_loop.py:262-280` — `build_retry_prompt()` (existing pattern)
- `python/run_change_prop_loop.py:293-317` — LLM call pattern (claude_agent_sdk)
- `python/run_change_prop_loop.py:485-717` — `generate_tests()` (oracle for Phase 5)
- `python/registry/one_shot_loop.py:296-358` — `run_tlc()` (v5: model for `run_tlc_simulate()`)
- `python/registry/one_shot_loop.py:424-469` — `parse_counterexample()` (v5: regex patterns reused by `parse_simulation_traces()`)
- `python/registry/traces.py` — v5 new file: `SimulationTrace`, `format_traces_for_prompt()`, `load_simulation_traces()`
