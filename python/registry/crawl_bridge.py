"""Bridge between crawl.db and dag.json.

Post-crawl step: creates RESOURCE nodes and CALLS/DEPENDS_ON edges
in the RegistryDag from crawl.db records.
"""

from __future__ import annotations

from pathlib import Path

from registry.crawl_store import CrawlStore
from registry.crawl_types import EntryType
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


def bridge_crawl_to_dag(
    crawl_db_path: Path,
    dag: RegistryDag,
) -> dict[str, int]:
    """Populate dag.json RESOURCE nodes and edges from crawl.db.

    Returns counters: {"nodes_added", "edges_added", "orphans_removed"}.
    """
    counters = {"nodes_added": 0, "edges_added": 0, "orphans_removed": 0}

    with CrawlStore(crawl_db_path) as store:
        records = store.get_all_records()
        crawl_uuids = store.get_all_uuids()

        # Step 1: Create RESOURCE nodes for each record
        for rec in records:
            name = f"{rec.function_name} @ {rec.file_path}"
            if rec.class_name:
                name = f"{rec.class_name}.{rec.function_name} @ {rec.file_path}"
            node = Node.resource(
                id=rec.uuid,
                name=name,
                description=rec.operational_claim,
            )
            dag.add_node(node)  # add_node is upsert (silently overwrites)
            counters["nodes_added"] += 1

        # Step 2: Create CALLS edges from deps view
        deps_rows = store.conn.execute(
            "SELECT dependent_uuid, dependency_uuid FROM deps"
        ).fetchall()
        for row in deps_rows:
            from_id = row["dependent_uuid"]
            to_id = row["dependency_uuid"]
            if from_id in dag.nodes and to_id in dag.nodes:
                try:
                    dag.add_edge(Edge(from_id, to_id, EdgeType.CALLS))
                    counters["edges_added"] += 1
                except Exception:
                    pass  # skip cycles, duplicates

        # Step 3: Entry point edges are already captured through CALLS edges
        # from the DFS crawl. No additional wiring needed here.

        # Step 4: Orphan cleanup — remove dag.json RESOURCE nodes
        # whose UUIDs are no longer in crawl.db
        orphan_ids = []
        for nid, node in list(dag.nodes.items()):
            if node.kind == NodeKind.RESOURCE and nid not in crawl_uuids:
                # Check if it's a crawl-originated node (UUID format, not gwt-/req- prefix)
                prefix = nid.split("-")[0] if "-" in nid else ""
                if prefix not in ("gwt", "req") and _looks_like_uuid(nid):
                    orphan_ids.append(nid)

        for nid in orphan_ids:
            dag.remove_node(nid)
            counters["orphans_removed"] += 1

    return counters


def _looks_like_uuid(s: str) -> bool:
    """Check if a string looks like a UUID (8-4-4-4-12 hex format)."""
    parts = s.split("-")
    if len(parts) != 5:
        return False
    expected_lens = [8, 4, 4, 4, 12]
    return all(
        len(p) == exp and all(c in "0123456789abcdef" for c in p)
        for p, exp in zip(parts, expected_lens)
    )
