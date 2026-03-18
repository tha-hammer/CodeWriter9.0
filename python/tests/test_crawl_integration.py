"""Integration tests for crawl CLI commands and context query with cards."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from registry.cli import main
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    EntryPoint,
    EntryType,
    FnRecord,
    InField,
    InSource,
    OutField,
    OutKind,
    make_record_uuid,
)
from registry.dag import RegistryDag
from registry.one_shot_loop import ContextBundle, format_prompt_context, query_context
from registry.types import Edge, EdgeType, Node, NodeKind


def _setup_cw9_project(tmp_path: Path) -> Path:
    """Create a minimal .cw9/ project."""
    project = tmp_path / "project"
    project.mkdir()
    cw9 = project / ".cw9"
    cw9.mkdir()
    # Create a minimal dag.json
    dag = RegistryDag()
    dag.save(cw9 / "dag.json")
    return project


def _make_fn(fn_name: str, file_path: str, **kw) -> FnRecord:
    uid = make_record_uuid(file_path, fn_name)
    defaults = dict(
        uuid=uid, function_name=fn_name, file_path=file_path,
        line_number=1, src_hash="hash", ins=[], do_description=f"{fn_name} does stuff",
        outs=[OutField(name=OutKind.OK, type_str="None", description="ok")],
        operational_claim=f"{fn_name} claim",
    )
    defaults.update(kw)
    return FnRecord(**defaults)


class TestCmdIngest:
    def test_ingest_python_codebase(self, tmp_path: Path):
        project = _setup_cw9_project(tmp_path)

        # Create a target codebase to ingest
        target = tmp_path / "target_repo"
        target.mkdir()
        (target / "app.py").write_text(
            "def main():\n    pass\n\ndef helper(x: int) -> str:\n    return str(x)\n"
        )

        result = main(["ingest", str(target), str(project)])
        assert result == 0

        # Verify crawl.db was created
        assert (project / ".cw9" / "crawl.db").exists()

        # Verify records in crawl.db
        with CrawlStore(project / ".cw9" / "crawl.db") as store:
            records = store.get_all_records()
            assert len(records) >= 2
            names = {r.function_name for r in records}
            assert "main" in names
            assert "helper" in names

        # Verify dag.json was updated
        dag = RegistryDag.load(project / ".cw9" / "dag.json")
        assert dag.node_count >= 2

    def test_ingest_incremental(self, tmp_path: Path):
        project = _setup_cw9_project(tmp_path)
        target = tmp_path / "target_repo"
        target.mkdir()
        (target / "app.py").write_text("def func(): pass\n")

        # First ingest
        main(["ingest", str(target), str(project)])

        # Second ingest (incremental) — should skip existing
        result = main(["ingest", str(target), str(project), "--incremental"])
        assert result == 0


class TestCmdStale:
    def test_no_crawl_db(self, tmp_path: Path):
        project = _setup_cw9_project(tmp_path)
        result = main(["stale", str(project)])
        assert result == 1

    def test_no_stale_records(self, tmp_path: Path, capsys):
        project = _setup_cw9_project(tmp_path)
        target = tmp_path / "target_repo"
        target.mkdir()
        (target / "app.py").write_text("def func(): pass\n")
        main(["ingest", str(target), str(project)])

        result = main(["stale", str(project)])
        assert result == 0
        assert "No stale" in capsys.readouterr().out


class TestCmdShow:
    def test_show_card(self, tmp_path: Path, capsys):
        project = _setup_cw9_project(tmp_path)
        target = tmp_path / "target_repo"
        target.mkdir()
        (target / "app.py").write_text("def hello(): pass\n")
        main(["ingest", str(target), str(project)])

        # Get the UUID for the hello function
        with CrawlStore(project / ".cw9" / "crawl.db") as store:
            records = store.get_all_records()
            uid = records[0].uuid

        result = main(["show", uid, str(project), "--card"])
        assert result == 0
        output = capsys.readouterr().out
        assert "hello" in output

    def test_show_dag_node(self, tmp_path: Path, capsys):
        project = _setup_cw9_project(tmp_path)
        target = tmp_path / "target_repo"
        target.mkdir()
        (target / "app.py").write_text("def func(): pass\n")
        main(["ingest", str(target), str(project)])

        with CrawlStore(project / ".cw9" / "crawl.db") as store:
            records = store.get_all_records()
            uid = records[0].uuid

        result = main(["show", uid, str(project)])
        assert result == 0
        output = capsys.readouterr().out
        assert "RESOURCE" in output.lower() or "resource" in output


class TestQueryContextWithCards:
    def test_cards_loaded_from_crawl_db(self, tmp_path: Path):
        state_root = tmp_path / ".cw9"
        state_root.mkdir()

        # Create crawl.db with a record
        crawl_db = state_root / "crawl.db"
        rec = _make_fn("handler", "src/api.py")
        with CrawlStore(crawl_db) as store:
            store.insert_record(rec)

        # Create dag.json with GWT -> RESOURCE edge
        dag = RegistryDag()
        dag.add_node(Node.resource(rec.uuid, "handler @ src/api.py"))
        gwt_id = dag.register_gwt("given", "when", "then")
        dag.add_edge(Edge(gwt_id, rec.uuid, EdgeType.DEPENDS_ON))
        dag.save(state_root / "dag.json")

        # Query context with state_root
        bundle = query_context(dag, gwt_id, state_root=state_root)

        assert len(bundle.cards) == 1
        assert bundle.cards[0].function_name == "handler"

    def test_cards_rendered_in_prompt(self, tmp_path: Path):
        state_root = tmp_path / ".cw9"
        state_root.mkdir()

        rec = _make_fn("process_order", "src/orders.py",
                       do_description="Processes an order",
                       do_steps=["Validate input", "Save to DB"],
                       ins=[InField(name="order_id", type_str="int", source=InSource.PARAMETER)])
        crawl_db = state_root / "crawl.db"
        with CrawlStore(crawl_db) as store:
            store.insert_record(rec)

        dag = RegistryDag()
        dag.add_node(Node.resource(rec.uuid, "process_order"))
        gwt_id = dag.register_gwt("given order", "when processed", "then saved")
        dag.add_edge(Edge(gwt_id, rec.uuid, EdgeType.DEPENDS_ON))
        dag.save(state_root / "dag.json")

        bundle = query_context(dag, gwt_id, state_root=state_root)
        text = format_prompt_context(bundle)

        assert "## Existing Code Behavior" in text
        assert "process_order" in text
        assert "Processes an order" in text
        assert "order_id" in text

    def test_no_crawl_db_no_cards(self, tmp_path: Path):
        state_root = tmp_path / ".cw9"
        state_root.mkdir()

        dag = RegistryDag()
        dag.add_node(Node.resource("r1", "resource"))
        gwt_id = dag.register_gwt("given", "when", "then")
        dag.add_edge(Edge(gwt_id, "r1", EdgeType.DEPENDS_ON))
        dag.save(state_root / "dag.json")

        bundle = query_context(dag, gwt_id, state_root=state_root)
        assert len(bundle.cards) == 0

    def test_backwards_compatible_without_state_root(self):
        """query_context without state_root works as before."""
        dag = RegistryDag()
        dag.add_node(Node.resource("r1", "resource"))
        gwt_id = dag.register_gwt("given", "when", "then")
        dag.add_edge(Edge(gwt_id, "r1", EdgeType.DEPENDS_ON))

        # No state_root — should work without cards
        bundle = query_context(dag, gwt_id)
        assert len(bundle.cards) == 0
        assert len(bundle.transitive_deps) == 1
