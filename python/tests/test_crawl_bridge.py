"""Tests for the crawl-to-dag bridge and CLI extensions."""

from __future__ import annotations

from pathlib import Path

import pytest

from registry.crawl_bridge import bridge_crawl_to_dag, _looks_like_uuid
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord,
    InField,
    InSource,
    OutField,
    OutKind,
    make_record_uuid,
)
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


def _make_fn(
    fn_name: str, file_path: str, class_name: str | None = None,
    ins: list | None = None, outs: list | None = None,
) -> FnRecord:
    uid = make_record_uuid(file_path, fn_name, class_name)
    return FnRecord(
        uuid=uid,
        function_name=fn_name,
        class_name=class_name,
        file_path=file_path,
        line_number=1,
        src_hash="hash123",
        ins=ins or [],
        do_description=f"Does {fn_name}",
        outs=outs or [OutField(name=OutKind.OK, type_str="None", description="ok")],
        operational_claim=f"{fn_name} claim",
    )


class TestBridgeCrawlToDag:
    def test_creates_resource_nodes(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("func_a", "src/a.py"))
            store.insert_record(_make_fn("func_b", "src/b.py"))

        dag = RegistryDag()
        result = bridge_crawl_to_dag(db, dag)

        assert result["nodes_added"] == 2
        assert dag.node_count == 2

        ua = make_record_uuid("src/a.py", "func_a")
        assert ua in dag.nodes
        assert dag.nodes[ua].kind == NodeKind.RESOURCE
        assert "func_a" in dag.nodes[ua].name

    def test_creates_calls_edges(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        ub = make_record_uuid("src/b.py", "func_b")
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("func_b", "src/b.py"))
            store.insert_record(_make_fn(
                "func_a", "src/a.py",
                ins=[InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_uuid=ub, source_function="func_b",
                )],
            ))

        dag = RegistryDag()
        result = bridge_crawl_to_dag(db, dag)

        assert result["edges_added"] >= 1
        ua = make_record_uuid("src/a.py", "func_a")
        calls = [e for e in dag.edges if e.from_id == ua and e.to_id == ub]
        assert len(calls) == 1
        assert calls[0].edge_type == EdgeType.CALLS

    def test_orphan_cleanup(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("func_a", "src/a.py"))

        orphan_uuid = make_record_uuid("src/deleted.py", "old_func")
        dag = RegistryDag()
        dag.add_node(Node.resource(orphan_uuid, "old_func"))

        result = bridge_crawl_to_dag(db, dag)

        assert result["orphans_removed"] == 1
        assert orphan_uuid not in dag.nodes

    def test_preserves_gwt_nodes(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("func_a", "src/a.py"))

        dag = RegistryDag()
        dag.add_node(Node.behavior("gwt-0001", "test", "given", "when", "then"))

        bridge_crawl_to_dag(db, dag)

        assert "gwt-0001" in dag.nodes  # GWT preserved

    def test_class_name_in_node_name(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("method", "src/svc.py", class_name="Service"))

        dag = RegistryDag()
        bridge_crawl_to_dag(db, dag)

        uid = make_record_uuid("src/svc.py", "method", "Service")
        assert "Service.method" in dag.nodes[uid].name

    def test_idempotent_rebridge(self, tmp_path: Path):
        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            store.insert_record(_make_fn("func_a", "src/a.py"))

        dag = RegistryDag()
        bridge_crawl_to_dag(db, dag)
        count1 = dag.node_count

        # Bridge again — should not duplicate
        bridge_crawl_to_dag(db, dag)
        assert dag.node_count == count1


class TestLooksLikeUuid:
    def test_valid_uuid(self):
        assert _looks_like_uuid("f47ac10b-58cc-4372-a567-0e02b2c3d479")

    def test_gwt_id(self):
        assert not _looks_like_uuid("gwt-0001")

    def test_req_id(self):
        assert not _looks_like_uuid("req-0003")

    def test_random_string(self):
        assert not _looks_like_uuid("hello-world")

    def test_actual_uuid5(self):
        uid = make_record_uuid("src/main.py", "handler")
        assert _looks_like_uuid(uid)
