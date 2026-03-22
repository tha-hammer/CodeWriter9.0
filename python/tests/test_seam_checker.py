"""Tests for seam checker — horizontal contract verification.

Hand-written infrastructure tests per CLAUDE.md rules (pipeline infrastructure).
Maps to gwt-0064 through gwt-0067 verified invariants.
"""

import json

import pytest

# Valid UUID4 constants for test records
UUID_A = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
UUID_B = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
UUID_C = "cccccccc-cccc-4ccc-cccc-cccccccccccc"
UUID_D = "dddddddd-dddd-4ddd-dddd-dddddddddddd"

from registry.seam_checker import (
    check_all_seams,
    check_seam,
    render_seam_report,
    seam_report_to_json,
    type_compatible,
)
from registry.crawl_types import (
    DispatchKind,
    FnRecord,
    InField,
    InSource,
    OutField,
    OutKind,
    SeamMismatch,
    SeamReport,
)


# ── type_compatible (Step 2) ──────────────────────────────────────

class TestTypeCompatible:
    """gwt-0064: CompatPairs, gwt-0065: ReflexiveCompatPairs."""

    # Tier 1: Exact match
    def test_exact_match(self):
        assert type_compatible("list[FnRecord]", "list[FnRecord]") is True

    def test_exact_mismatch(self):
        assert type_compatible("Dict[str, Any]", "Config") is False

    # Tier 2: Normalized match
    def test_case_insensitive(self):
        assert type_compatible("dict[str, Any]", "Dict[str, Any]") is True

    def test_list_alias(self):
        assert type_compatible("List[int]", "list[int]") is True

    def test_optional_alias(self):
        assert type_compatible("Optional[str]", "str | None") is True

    # Tier 3: Structural subtype
    def test_narrower_satisfies_union(self):
        assert type_compatible("str", "str | None") is True

    def test_any_satisfies_anything(self):
        assert type_compatible("Any", "Config") is True

    def test_anything_satisfies_any(self):
        assert type_compatible("Config", "Any") is True

    def test_incompatible(self):
        assert type_compatible("int", "str") is False

    # Reflexivity (gwt-0065: ReflexiveCompatPairs)
    def test_reflexive(self):
        for t in ["str", "int", "list[FnRecord]", "Dict[str, Any]", "None"]:
            assert type_compatible(t, t) is True


# ── check_seam (Step 3) ──────────────────────────────────────────

class TestCheckSeam:
    """gwt-0064: MismatchDetected, gwt-0065: SeamSatisfied."""

    def test_mismatch_detected(self):
        """gwt-0064: type mismatch produces SeamMismatch."""
        caller = FnRecord(
            uuid=UUID_A, function_name="get_config", file_path="a.py",
            src_hash="abc", ins=[], do_description="returns config dict",
            outs=[OutField(name=OutKind.OK, type_str="Dict[str, Any]")]
        )
        callee = FnRecord(
            uuid=UUID_B, function_name="process", file_path="b.py",
            src_hash="def",
            ins=[InField(name="config", type_str="Config", source=InSource.INTERNAL_CALL,
                         source_uuid=UUID_A)],
            do_description="processes config", outs=[]
        )
        mismatches = check_seam(caller, callee)
        assert len(mismatches) == 1
        assert mismatches[0].severity == "type_mismatch"
        assert mismatches[0].expected_type == "Config"
        assert mismatches[0].provided_type == "Dict[str, Any]"

    def test_satisfied_no_report(self):
        """gwt-0065: compatible types produce empty result."""
        caller = FnRecord(
            uuid=UUID_A, function_name="get_records", file_path="a.py",
            src_hash="abc", ins=[], do_description="returns records",
            outs=[OutField(name=OutKind.OK, type_str="list[FnRecord]")]
        )
        callee = FnRecord(
            uuid=UUID_B, function_name="process_records", file_path="b.py",
            src_hash="def",
            ins=[InField(name="records", type_str="list[FnRecord]",
                         source=InSource.INTERNAL_CALL, source_uuid=UUID_A)],
            do_description="processes records", outs=[]
        )
        assert check_seam(caller, callee) == []

    def test_no_ok_output(self):
        """Caller has no ok output — severity is no_ok_output."""
        caller = FnRecord(
            uuid=UUID_A, function_name="do_effect", file_path="a.py",
            src_hash="abc", ins=[], do_description="side effect only",
            outs=[OutField(name=OutKind.SIDE_EFFECT, type_str="None")]
        )
        callee = FnRecord(
            uuid=UUID_B, function_name="use_result", file_path="b.py",
            src_hash="def",
            ins=[InField(name="result", type_str="str",
                         source=InSource.INTERNAL_CALL, source_uuid=UUID_A)],
            do_description="uses result", outs=[]
        )
        mismatches = check_seam(caller, callee)
        assert len(mismatches) == 1
        assert mismatches[0].severity == "no_ok_output"

    def test_no_linked_inputs(self):
        """Callee has no inputs from caller — empty result."""
        caller = FnRecord(
            uuid=UUID_A, function_name="f", file_path="a.py",
            src_hash="abc", ins=[], do_description="x",
            outs=[OutField(name=OutKind.OK, type_str="str")]
        )
        callee = FnRecord(
            uuid=UUID_B, function_name="g", file_path="b.py",
            src_hash="def",
            ins=[InField(name="x", type_str="str", source=InSource.PARAMETER)],
            do_description="y", outs=[]
        )
        assert check_seam(caller, callee) == []


# ── CrawlStore methods (Step 4) ──────────────────────────────────

class TestCrawlStoreMethods:
    """gwt-0066, gwt-0067: dependency edge and unresolved queries."""

    def test_get_dependency_edges(self, tmp_path):
        """Resolved deps view returns all edges with non-NULL source_uuid."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            caller = FnRecord(
                uuid=UUID_A, function_name="caller", file_path="a.py",
                src_hash="a", ins=[], do_description="caller",
                outs=[OutField(name=OutKind.OK, type_str="str")]
            )
            callee = FnRecord(
                uuid=UUID_B, function_name="callee", file_path="b.py",
                src_hash="b",
                ins=[InField(name="x", type_str="str", source=InSource.INTERNAL_CALL,
                             source_uuid=UUID_A)],
                do_description="callee",
                outs=[OutField(name=OutKind.OK, type_str="bool")]
            )
            store.upsert_record(caller)
            store.upsert_record(callee)

            edges = store.get_dependency_edges()
            assert len(edges) == 1
            assert edges[0][0] == UUID_B  # dependent_uuid
            assert edges[0][1] == UUID_A  # dependency_uuid

    def test_get_unresolved_internal_calls(self, tmp_path):
        """Unresolved internal_call ins returned as dicts."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            rec = FnRecord(
                uuid=UUID_B, function_name="callee", file_path="b.py",
                src_hash="b",
                ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                             source_uuid=None, source_function="unknown")],
                do_description="callee",
                outs=[OutField(name=OutKind.OK, type_str="bool")]
            )
            store.upsert_record(rec)

            unresolved = store.get_unresolved_internal_calls()
            assert len(unresolved) == 1
            assert unresolved[0]["name"] == "data"
            assert unresolved[0]["function_name"] == "callee"

    def test_empty_database(self, tmp_path):
        """Both methods return empty lists on empty database."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            assert store.get_dependency_edges() == []
            assert store.get_unresolved_internal_calls() == []


# ── check_all_seams (Step 5) ─────────────────────────────────────

class TestCheckAllSeams:
    """gwt-0066, gwt-0067: full report generation."""

    def test_unresolved_flagged(self, tmp_path):
        """gwt-0066: unresolved internal_call inputs produce unresolved entries."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            rec = FnRecord(
                uuid=UUID_B, function_name="process_data", file_path="b.py",
                src_hash="def",
                ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                             source_uuid=None, source_function="unknown_fn")],
                do_description="processes data",
                outs=[OutField(name=OutKind.OK, type_str="bool")]
            )
            store.upsert_record(rec)

            report = check_all_seams(store)
            assert len(report.unresolved) == 1
            assert report.unresolved[0].severity == "unresolved"
            assert report.unresolved[0].callee_input_name == "data"

    def test_report_completeness(self, tmp_path):
        """gwt-0067: total_edges = mismatches + unresolved + satisfied."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            # Caller A
            store.upsert_record(FnRecord(
                uuid=UUID_A, function_name="get_name", file_path="a.py",
                src_hash="abc", ins=[], do_description="returns name",
                outs=[OutField(name=OutKind.OK, type_str="str")]
            ))
            # Callee B1 — satisfied (str == str)
            store.upsert_record(FnRecord(
                uuid=UUID_B, function_name="use_name", file_path="b.py",
                src_hash="def",
                ins=[InField(name="name", type_str="str", source=InSource.INTERNAL_CALL,
                             source_uuid=UUID_A)],
                do_description="uses name",
                outs=[OutField(name=OutKind.OK, type_str="bool")]
            ))
            # Callee B2 — mismatch (str vs int)
            store.upsert_record(FnRecord(
                uuid=UUID_C, function_name="count_items", file_path="c.py",
                src_hash="ghi",
                ins=[InField(name="count", type_str="int", source=InSource.INTERNAL_CALL,
                             source_uuid=UUID_A)],
                do_description="counts",
                outs=[OutField(name=OutKind.OK, type_str="int")]
            ))
            # Callee B3 — unresolved
            store.upsert_record(FnRecord(
                uuid=UUID_D, function_name="process_data", file_path="d.py",
                src_hash="jkl",
                ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                             source_uuid=None, source_function="unknown")],
                do_description="processes",
                outs=[OutField(name=OutKind.OK, type_str="bool")]
            ))

            report = check_all_seams(store)

            # Completeness invariant (gwt-0067)
            assert report.total_edges == len(report.mismatches) + len(report.unresolved) + report.satisfied
            assert report.total_edges == 3
            assert report.satisfied == 1
            assert len(report.mismatches) == 1
            assert len(report.unresolved) == 1

            # NonNegative invariant (gwt-0067)
            assert report.satisfied >= 0
            assert report.total_edges >= 0

            # UnresolvedNotInMismatches invariant (gwt-0066)
            unresolved_callees = {u.callee_uuid for u in report.unresolved}
            mismatch_callees = {m.callee_uuid for m in report.mismatches}
            assert not unresolved_callees & mismatch_callees

    def test_empty_report(self, tmp_path):
        """gwt-0067: empty crawl.db produces zero-edge report."""
        from registry.crawl_store import CrawlStore

        db = tmp_path / "crawl.db"
        with CrawlStore(db) as store:
            report = check_all_seams(store)
            assert report.total_edges == 0
            assert report.satisfied == 0
            assert report.mismatches == []
            assert report.unresolved == []
            assert report.total_edges == len(report.mismatches) + len(report.unresolved) + report.satisfied


# ── Output formatters (Step 6) ───────────────────────────────────

class TestOutputFormatters:

    def _make_report(self) -> SeamReport:
        return SeamReport(
            mismatches=[
                SeamMismatch(
                    caller_uuid="a", callee_uuid="b",
                    caller_function="get_config", callee_function="process",
                    callee_input_name="config",
                    expected_type="Config", provided_type="Dict[str, Any]",
                    dispatch=DispatchKind.DIRECT, severity="type_mismatch",
                )
            ],
            unresolved=[
                SeamMismatch(
                    caller_uuid="", callee_uuid="c",
                    caller_function="", callee_function="handle",
                    callee_input_name="data",
                    expected_type="dict", provided_type="",
                    dispatch=DispatchKind.DIRECT, severity="unresolved",
                )
            ],
            satisfied=5,
            total_edges=7,
        )

    def test_render_seam_report(self):
        report = self._make_report()
        text = render_seam_report(report)
        assert "7 edges analyzed" in text
        assert "5 satisfied" in text
        assert "1 mismatches" in text
        assert "1 unresolved" in text
        assert "get_config()" in text
        assert "Config" in text

    def test_render_empty_report(self):
        report = SeamReport(mismatches=[], unresolved=[], satisfied=0, total_edges=0)
        text = render_seam_report(report)
        assert "0 edges analyzed" in text

    def test_seam_report_to_json(self):
        report = self._make_report()
        data = seam_report_to_json(report)
        assert data["total_edges"] == 7
        assert data["satisfied"] == 5
        assert len(data["mismatches"]) == 1
        assert len(data["unresolved"]) == 1
        # Verify JSON-serializable
        json.dumps(data)

    def test_json_empty_report(self):
        report = SeamReport(mismatches=[], unresolved=[], satisfied=0, total_edges=0)
        data = seam_report_to_json(report)
        assert data["total_edges"] == 0
        json.dumps(data)
