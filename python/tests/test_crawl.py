"""Tests for the brownfield crawl infrastructure (Phase 1).

Covers: crawl_types, crawl_store, dag.py remove_node/merge extensions.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from registry.crawl_types import (
    AxRecord,
    CRAWL_NAMESPACE,
    DispatchKind,
    EntryPoint,
    EntryType,
    FnRecord,
    InField,
    InSource,
    MapNote,
    OutField,
    OutKind,
    Skeleton,
    SkeletonParam,
    TestReference,
    make_record_uuid,
)
from registry.crawl_store import CrawlStore, render_card
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


# ── Helpers ───────────────────────────────────────────────────────

def _make_uuid(file_path: str = "src/main.py", fn: str = "handler", cls: str | None = None) -> str:
    return make_record_uuid(file_path, fn, cls)


def _make_fn_record(
    fn_name: str = "get_user",
    file_path: str = "src/handlers/user.py",
    class_name: str | None = None,
    **overrides,
) -> FnRecord:
    uid = make_record_uuid(file_path, fn_name, class_name)
    defaults = dict(
        uuid=uid,
        function_name=fn_name,
        class_name=class_name,
        file_path=file_path,
        line_number=42,
        src_hash="abc123def456",
        is_external=False,
        ins=[
            InField(name="user_id", type_str="int", source=InSource.PARAMETER),
        ],
        do_description="Fetches user by ID",
        do_steps=["Call db.get(user_id)", "Return result"],
        outs=[
            OutField(name=OutKind.OK, type_str="User", description="The user"),
            OutField(name=OutKind.ERR, type_str="404", description="Not found"),
        ],
        failure_modes=["DB timeout"],
        operational_claim="Returns user or 404",
    )
    defaults.update(overrides)
    return FnRecord(**defaults)


def _make_ax_record(fn_name: str = "redis_get", **overrides) -> AxRecord:
    uid = make_record_uuid("redis", fn_name)
    defaults = dict(
        uuid=uid,
        function_name=fn_name,
        file_path="redis",
        src_hash="external",
        is_external=True,
        source_crate="redis",
        ins=[InField(name="key", type_str="str", source=InSource.PARAMETER)],
        outs=[OutField(name=OutKind.OK, type_str="bytes", description="cached value")],
        boundary_contract="Redis GET per documented contract",
    )
    defaults.update(overrides)
    return AxRecord(**defaults)


# ── crawl_types tests ─────────────────────────────────────────────

class TestMakeRecordUuid:
    def test_deterministic(self):
        u1 = make_record_uuid("src/main.py", "handler")
        u2 = make_record_uuid("src/main.py", "handler")
        assert u1 == u2

    def test_different_function_different_uuid(self):
        u1 = make_record_uuid("src/main.py", "handler")
        u2 = make_record_uuid("src/main.py", "other")
        assert u1 != u2

    def test_different_file_different_uuid(self):
        u1 = make_record_uuid("src/a.py", "handler")
        u2 = make_record_uuid("src/b.py", "handler")
        assert u1 != u2

    def test_class_name_matters(self):
        u1 = make_record_uuid("src/main.py", "__init__", "ClassA")
        u2 = make_record_uuid("src/main.py", "__init__", "ClassB")
        assert u1 != u2

    def test_none_class_same_as_no_class(self):
        u1 = make_record_uuid("src/main.py", "func", None)
        u2 = make_record_uuid("src/main.py", "func")
        assert u1 == u2

    def test_is_valid_uuid(self):
        u = make_record_uuid("src/main.py", "func")
        uuid.UUID(u)  # should not raise

    def test_uses_uuid5_with_crawl_namespace(self):
        qualified = "src/main.py::::handler"
        expected = str(uuid.uuid5(CRAWL_NAMESPACE, qualified))
        assert make_record_uuid("src/main.py", "handler") == expected


class TestInField:
    def test_valid_internal_call(self):
        f = InField(
            name="result", type_str="User", source=InSource.INTERNAL_CALL,
            source_function="get_user",
        )
        assert f.dispatch == DispatchKind.DIRECT

    def test_invalid_source_uuid_rejected(self):
        with pytest.raises(Exception):
            InField(
                name="x", type_str="int", source=InSource.PARAMETER,
                source_uuid="not-a-uuid",
            )

    def test_valid_source_uuid_accepted(self):
        uid = str(uuid.uuid4())
        f = InField(name="x", type_str="int", source=InSource.PARAMETER, source_uuid=uid)
        assert f.source_uuid == uid

    def test_dispatch_candidates(self):
        f = InField(
            name="result", type_str="User", source=InSource.INTERNAL_CALL,
            dispatch=DispatchKind.ATTRIBUTE,
            dispatch_candidates=["UserRepo.save", "MockRepo.save"],
        )
        assert len(f.dispatch_candidates) == 2


class TestFnRecord:
    def test_valid_record(self):
        r = _make_fn_record()
        assert r.function_name == "get_user"
        uuid.UUID(r.uuid)

    def test_invalid_uuid_rejected(self):
        with pytest.raises(Exception):
            FnRecord(
                uuid="bad", function_name="f", file_path="x.py",
                src_hash="abc", ins=[], do_description="", outs=[],
            )

    def test_skeleton_attached(self):
        skel = Skeleton(
            function_name="get_user", file_path="src/user.py",
            line_number=10, params=[SkeletonParam(name="self", is_self=True)],
        )
        r = _make_fn_record(skeleton=skel)
        assert r.skeleton is not None
        assert r.skeleton.function_name == "get_user"


class TestAxRecord:
    def test_valid_external(self):
        r = _make_ax_record()
        assert r.is_external is True
        assert r.source_crate == "redis"


class TestSkeleton:
    def test_to_dict(self):
        skel = Skeleton(
            function_name="handler", file_path="src/main.py", line_number=1,
            class_name="App", is_async=True,
            params=[SkeletonParam(name="self", is_self=True), SkeletonParam(name="request", type="Request")],
            return_type="Response", file_hash="abc123",
        )
        d = skel.to_dict()
        assert d["function_name"] == "handler"
        assert d["class_name"] == "App"
        assert d["is_async"] is True
        assert len(d["params"]) == 2
        assert d["params"][0]["is_self"] is True


class TestEntryPoint:
    def test_http_route(self):
        ep = EntryPoint(
            file_path="src/api.py", function_name="get_users",
            entry_type=EntryType.HTTP_ROUTE, route="/api/users", method="GET",
        )
        assert ep.entry_type == EntryType.HTTP_ROUTE
        assert ep.route == "/api/users"


# ── CrawlStore tests ─────────────────────────────────────────────

@pytest.fixture
def store(tmp_path: Path) -> CrawlStore:
    s = CrawlStore(tmp_path / "crawl.db")
    s.connect()
    yield s
    s.close()


class TestCrawlStoreBasic:
    def test_connect_creates_schema(self, store: CrawlStore):
        tables = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "records" in names
        assert "ins" in names
        assert "outs" in names
        assert "maps" in names
        assert "entry_points" in names
        assert "crawl_runs" in names
        assert "test_refs" in names

    def test_context_manager(self, tmp_path: Path):
        with CrawlStore(tmp_path / "ctx.db") as s:
            tables = s.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            assert len(tables) > 0

    def test_connect_required(self, tmp_path: Path):
        s = CrawlStore(tmp_path / "no.db")
        with pytest.raises(RuntimeError, match="not connected"):
            s.conn


class TestCrawlStoreRecordCrud:
    def test_insert_and_get(self, store: CrawlStore):
        rec = _make_fn_record()
        store.insert_record(rec)
        got = store.get_record(rec.uuid)
        assert got is not None
        assert got.function_name == "get_user"
        assert got.file_path == "src/handlers/user.py"
        assert got.line_number == 42
        assert len(got.ins) == 1
        assert got.ins[0].name == "user_id"
        assert got.ins[0].source == InSource.PARAMETER
        assert len(got.outs) == 2
        assert got.do_description == "Fetches user by ID"
        assert got.do_steps == ["Call db.get(user_id)", "Return result"]
        assert got.failure_modes == ["DB timeout"]
        assert got.operational_claim == "Returns user or 404"

    def test_get_missing_returns_none(self, store: CrawlStore):
        assert store.get_record("nonexistent") is None

    def test_upsert_replaces(self, store: CrawlStore):
        rec = _make_fn_record()
        store.insert_record(rec)
        updated = _make_fn_record(do_description="Updated description")
        store.upsert_record(updated)
        got = store.get_record(rec.uuid)
        assert got is not None
        assert got.do_description == "Updated description"

    def test_insert_ax_record(self, store: CrawlStore):
        ax = _make_ax_record()
        store.insert_record(ax)
        got = store.get_record(ax.uuid)
        assert got is not None
        assert got.is_external is True

    def test_get_records_for_file(self, store: CrawlStore):
        r1 = _make_fn_record("func_a", "src/main.py")
        r2 = _make_fn_record("func_b", "src/main.py")
        r3 = _make_fn_record("func_c", "src/other.py")
        store.insert_record(r1)
        store.insert_record(r2)
        store.insert_record(r3)
        records = store.get_records_for_file("src/main.py")
        assert len(records) == 2
        names = {r.function_name for r in records}
        assert names == {"func_a", "func_b"}

    def test_get_all_records(self, store: CrawlStore):
        store.insert_record(_make_fn_record("a", "x.py"))
        store.insert_record(_make_fn_record("b", "y.py"))
        store.insert_record(_make_ax_record())
        records = store.get_all_records()
        assert len(records) == 2  # external excluded

    def test_get_all_uuids(self, store: CrawlStore):
        r1 = _make_fn_record("a", "x.py")
        r2 = _make_ax_record()
        store.insert_record(r1)
        store.insert_record(r2)
        uuids = store.get_all_uuids()
        assert r1.uuid in uuids
        assert r2.uuid in uuids
        assert len(uuids) == 2

    def test_skeleton_round_trip(self, store: CrawlStore):
        skel = Skeleton(
            function_name="handler", file_path="src/main.py", line_number=10,
            class_name="App", is_async=True,
            params=[SkeletonParam("self", is_self=True), SkeletonParam("req", "Request")],
            return_type="Response", file_hash="abc",
        )
        rec = _make_fn_record(skeleton=skel)
        store.insert_record(rec)
        got = store.get_record(rec.uuid)
        assert got is not None
        assert got.skeleton is not None
        assert got.skeleton.class_name == "App"
        assert got.skeleton.is_async is True
        assert len(got.skeleton.params) == 2
        assert got.skeleton.params[0].is_self is True

    def test_dispatch_fields_round_trip(self, store: CrawlStore):
        rec = _make_fn_record(
            ins=[
                InField(
                    name="result", type_str="User", source=InSource.INTERNAL_CALL,
                    source_function="find_user",
                    dispatch=DispatchKind.ATTRIBUTE,
                    dispatch_candidates=["UserRepo.find", "CachedRepo.find"],
                ),
            ],
        )
        store.insert_record(rec)
        got = store.get_record(rec.uuid)
        assert got is not None
        assert got.ins[0].dispatch == DispatchKind.ATTRIBUTE
        assert got.ins[0].dispatch_candidates == ["UserRepo.find", "CachedRepo.find"]

    def test_class_name_uniqueness(self, store: CrawlStore):
        """Two methods with same name in different classes should coexist."""
        r1 = _make_fn_record("__init__", "src/main.py", class_name="ClassA")
        r2 = _make_fn_record("__init__", "src/main.py", class_name="ClassB")
        store.insert_record(r1)
        store.insert_record(r2)
        assert store.get_record(r1.uuid) is not None
        assert store.get_record(r2.uuid) is not None
        assert r1.uuid != r2.uuid


class TestCrawlStoreStaleness:
    def test_stale_detection(self, store: CrawlStore):
        rec = _make_fn_record(src_hash="old_hash")
        store.insert_record(rec)
        stale = store.get_stale_records({"src/handlers/user.py": "new_hash"})
        assert rec.uuid in stale

    def test_not_stale_when_hash_matches(self, store: CrawlStore):
        rec = _make_fn_record(src_hash="same_hash")
        store.insert_record(rec)
        stale = store.get_stale_records({"src/handlers/user.py": "same_hash"})
        assert len(stale) == 0

    def test_transitive_staleness(self, store: CrawlStore):
        # A calls B: if B is stale, A should be transitively stale
        b_uuid = make_record_uuid("src/b.py", "func_b")
        a = _make_fn_record(
            "func_a", "src/a.py",
            ins=[
                InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_uuid=b_uuid, source_function="func_b",
                ),
            ],
        )
        b = _make_fn_record("func_b", "src/b.py", src_hash="old_hash")
        store.insert_record(b)
        store.insert_record(a)

        direct_stale = [b.uuid]
        transitive = store.get_transitive_stale(direct_stale)
        assert b.uuid in transitive
        assert a.uuid in transitive

    def test_transitive_empty_input(self, store: CrawlStore):
        assert store.get_transitive_stale([]) == []


class TestCrawlStoreBackfill:
    def test_backfill_resolves_source_uuid(self, store: CrawlStore):
        b = _make_fn_record("func_b", "src/b.py")
        a = _make_fn_record(
            "func_a", "src/a.py",
            ins=[
                InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_function="func_b",
                    # source_uuid is None — will be back-filled
                ),
            ],
        )
        store.insert_record(b)
        store.insert_record(a)

        count = store.backfill_source_uuids()
        assert count == 1

        got = store.get_record(a.uuid)
        assert got is not None
        assert got.ins[0].source_uuid == b.uuid


class TestCrawlStoreValidation:
    def test_completeness_warnings(self, store: CrawlStore):
        rec = _make_fn_record(
            ins=[
                InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_function="nonexistent_fn",
                ),
            ],
        )
        store.insert_record(rec)
        warnings = store.validate_completeness()
        assert len(warnings) == 1
        assert "nonexistent_fn" in warnings[0]


class TestCrawlStoreCrawlRuns:
    def test_start_and_finish(self, store: CrawlStore):
        run_id = store.start_crawl_run("/path/to/repo", "python", "web_app", False)
        assert run_id is not None
        store.finish_crawl_run(run_id, created=10, updated=2, skipped=5, failed=1)
        row = store.conn.execute(
            "SELECT * FROM crawl_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["completed_at"] is not None
        assert row["records_created"] == 10
        assert row["records_failed"] == 1


class TestCrawlStoreEntryPoints:
    def test_insert_and_get(self, store: CrawlStore):
        ep = EntryPoint(
            file_path="src/api.py", function_name="get_users",
            entry_type=EntryType.HTTP_ROUTE, route="/api/users", method="GET",
        )
        store.insert_entry_point(ep)
        eps = store.get_entry_points()
        assert len(eps) == 1
        assert eps[0].route == "/api/users"
        assert eps[0].entry_type == EntryType.HTTP_ROUTE


class TestCrawlStoreTestRefs:
    def test_insert_and_coverage(self, store: CrawlStore):
        rec = _make_fn_record()
        store.insert_record(rec)
        ref = TestReference(
            test_file="tests/test_user.py",
            test_function="test_get_user",
            target_function="get_user",
            target_file="src/handlers/user.py",
            target_uuid=rec.uuid,
            inputs_observed=["user_id=1"],
            outputs_asserted=["returns User"],
            covers_error_path=False,
        )
        store.insert_test_ref(ref)
        coverage = store.get_test_coverage()
        assert len(coverage) >= 1
        found = [c for c in coverage if c["uuid"] == rec.uuid]
        assert found[0]["test_count"] == 1


class TestCrawlStoreMaps:
    def test_insert_and_get(self, store: CrawlStore):
        rec = _make_fn_record()
        store.insert_record(rec)
        m = MapNote(
            workflow_name="user_flow",
            entry_uuid=rec.uuid,
            path_uuids=[rec.uuid],
            shared_uuids=[],
            properties=["safety"],
        )
        store.insert_map(m)
        maps = store.get_maps()
        assert len(maps) == 1
        assert maps[0].workflow_name == "user_flow"
        assert maps[0].properties == ["safety"]


class TestCrawlStoreSubgraph:
    def test_forward_subgraph(self, store: CrawlStore):
        b = _make_fn_record("func_b", "src/b.py")
        b_uuid = b.uuid
        a = _make_fn_record(
            "func_a", "src/a.py",
            ins=[
                InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_uuid=b_uuid, source_function="func_b",
                ),
            ],
        )
        store.insert_record(b)
        store.insert_record(a)
        subgraph = store.get_forward_subgraph("func_a")
        uuids = {r.uuid for r in subgraph}
        assert a.uuid in uuids
        assert b.uuid in uuids

    def test_reverse_subgraph(self, store: CrawlStore):
        b = _make_fn_record("func_b", "src/b.py")
        b_uuid = b.uuid
        a = _make_fn_record(
            "func_a", "src/a.py",
            ins=[
                InField(
                    name="result", type_str="int", source=InSource.INTERNAL_CALL,
                    source_uuid=b_uuid, source_function="func_b",
                ),
            ],
        )
        store.insert_record(b)
        store.insert_record(a)
        subgraph = store.get_reverse_subgraph("func_b")
        uuids = {r.uuid for r in subgraph}
        assert b.uuid in uuids
        assert a.uuid in uuids


class TestRenderCard:
    def test_basic_rendering(self):
        rec = _make_fn_record()
        text = render_card(rec)
        assert "get_user" in text
        assert "src/handlers/user.py:42" in text
        assert "**IN:**" in text
        assert "user_id: int (parameter)" in text
        assert "**DO:** Fetches user by ID" in text
        assert "**OUT:**" in text
        assert "ok: User" in text
        assert "DB timeout" in text

    def test_dispatch_note_in_card(self):
        rec = _make_fn_record(
            ins=[
                InField(
                    name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                    dispatch=DispatchKind.ATTRIBUTE,
                ),
            ],
        )
        text = render_card(rec)
        assert "[attribute]" in text


# ── RegistryDag extension tests ──────────────────────────────────

class TestRegistryDagRemoveNode:
    def test_remove_existing_node(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("r1", "Resource 1"))
        dag.add_node(Node.resource("r2", "Resource 2"))
        dag.add_edge(Edge("r1", "r2", EdgeType.DEPENDS_ON))
        assert dag.node_count == 2
        assert dag.edge_count == 1

        dag.remove_node("r2")
        assert dag.node_count == 1
        assert dag.edge_count == 0
        assert "r2" not in dag.nodes
        assert "r2" not in dag.closure

    def test_remove_nonexistent_is_noop(self):
        dag = RegistryDag()
        dag.remove_node("nonexistent")  # should not raise

    def test_remove_preserves_unrelated_edges(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("r1", "R1"))
        dag.add_node(Node.resource("r2", "R2"))
        dag.add_node(Node.resource("r3", "R3"))
        dag.add_edge(Edge("r1", "r2", EdgeType.DEPENDS_ON))
        dag.add_edge(Edge("r1", "r3", EdgeType.DEPENDS_ON))

        dag.remove_node("r2")
        assert dag.edge_count == 1
        assert dag.edges[0].to_id == "r3"


class TestRegistryDagMergeWithCrawlUuids:
    def test_merge_preserves_crawl_nodes(self):
        old_dag = RegistryDag()
        crawl_uuid = make_record_uuid("src/main.py", "handler")
        old_dag.add_node(Node.resource(crawl_uuid, "handler @ src/main.py"))
        old_dag.add_node(Node.resource("gwt-0001", "test gwt"))

        new_dag = RegistryDag()
        new_dag.add_node(Node.resource("r1", "Fresh resource"))

        merged = new_dag.merge_registered_nodes(old_dag, crawl_uuids={crawl_uuid})
        assert merged == 2  # crawl node + gwt node
        assert crawl_uuid in new_dag.nodes
        assert "gwt-0001" in new_dag.nodes

    def test_merge_without_crawl_uuids_skips_crawl_nodes(self):
        old_dag = RegistryDag()
        crawl_uuid = make_record_uuid("src/main.py", "handler")
        old_dag.add_node(Node.resource(crawl_uuid, "handler @ src/main.py"))

        new_dag = RegistryDag()
        merged = new_dag.merge_registered_nodes(old_dag)
        assert merged == 0
        assert crawl_uuid not in new_dag.nodes

    def test_merge_preserves_crawl_edges(self):
        old_dag = RegistryDag()
        u1 = make_record_uuid("src/a.py", "func_a")
        u2 = make_record_uuid("src/b.py", "func_b")
        old_dag.add_node(Node.resource(u1, "func_a"))
        old_dag.add_node(Node.resource(u2, "func_b"))
        old_dag.add_edge(Edge(u1, u2, EdgeType.CALLS))

        new_dag = RegistryDag()
        new_dag.merge_registered_nodes(old_dag, crawl_uuids={u1, u2})
        assert new_dag.edge_count == 1
        assert new_dag.edges[0].from_id == u1
        assert new_dag.edges[0].to_id == u2
