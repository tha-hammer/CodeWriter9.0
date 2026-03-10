╔═══════════════════════════════════════╗
║  PHASE 2: cw9 extract                ║
╚═══════════════════════════════════════╝

## Overview

Runs `SchemaExtractor` on target schemas, builds DAG, saves to `.cw9/dag.json`. Prints minimal diff summary on re-extract. **Merges registered GWTs back into the extracted DAG** so that `register_gwt() → extract → loop` doesn't destroy registered work.

> **v3 fix (Issue #2):** `SchemaExtractor.extract()` at `extractor.py:144` always starts
> with a fresh `RegistryDag()`. Any GWTs registered via `register_gwt()` exist only in
> `dag.json` and are not embedded in schema files. Without merging, re-running `cw9 extract`
> obliterates them. This is now handled in `cmd_extract()`, not deferred to "a future
> enhancement."

## Changes Required

### 1. `python/registry/dag.py` — `merge_registered_nodes()`

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

### 2. `python/registry/cli.py` — `cmd_extract()`

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

### 3. Argparse wiring

```python
p_extract = sub.add_parser("extract", help="Extract DAG from schemas")
p_extract.add_argument("target_dir", nargs="?", default=".")
```

## Tests

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

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_cli.py::TestExtract -v` — all pass (including 2 new merge tests)
- [x] `cw9 init /tmp/foo && cw9 extract /tmp/foo` — prints node/edge counts
