"""Tests for gwt-0069: behavioral_contracts_checked.

Bridge verifiers: CountConsistency, ViolationComplete, NoFalsePositives,
NoMatchNoViolation, EmptyEdgesImpliesEmptyReport, ZeroViolationsWhenAllCompliant,
NoMatchNoCount.
"""

import pytest

from registry.crawl_types import (
    BehavioralReport,
    BehavioralViolation,
    CrossCuttingRule,
    FnRecord,
    InField,
    InSource,
    OutField,
    OutKind,
)
from registry.seam_checker import check_behavioral_contracts


def _make_fn(uuid, name, file_path="src/mod.py", outs=None, ins=None,
             is_external=False, boundary_contract=None):
    """Helper to build minimal FnRecord for testing."""
    return FnRecord(
        uuid=uuid,
        function_name=name,
        file_path=file_path,
        class_name=None,
        line_number=1,
        src_hash="test",
        is_external=is_external,
        do_description="test",
        outs=outs or [],
        ins=ins or [],
        failure_modes=[],
        operational_claim="",
    )


class TestCheckBehavioralContracts:
    """Trace-derived tests for check_behavioral_contracts()."""

    def test_violation_detected(self, tmp_path) -> None:
        """Trace: 2 edges, rule matches callee, callee missing required OUT → violation."""
        from registry.crawl_store import CrawlStore

        db_path = tmp_path / "crawl.db"
        with CrawlStore(db_path) as store:
            # Callee: database function missing audit_event out
            callee = _make_fn(
                "00000000-0000-0000-0000-000000000001",
                "save_record",
                file_path="src/db/store.py",
                outs=[OutField(name=OutKind.OK, type_str="dict", description="result")],
                is_external=False,
            )
            store.upsert_record(callee)

            # Caller that depends on callee
            caller = _make_fn(
                "00000000-0000-0000-0000-000000000002",
                "process_batch",
                file_path="src/pipeline.py",
                outs=[OutField(name=OutKind.OK, type_str="list", description="results")],
                ins=[InField(
                    name="db_result", type_str="dict",
                    source=InSource.INTERNAL_CALL,
                    source_uuid="00000000-0000-0000-0000-000000000001",
                )],
            )
            store.upsert_record(caller)

            rules = [CrossCuttingRule(
                resource_type="database",
                required_outs=["audit_event"],
                position="wrap",
            )]
            report = check_behavioral_contracts(store, rules)

        assert isinstance(report, BehavioralReport)
        # CountConsistency: total_checked == satisfied + len(violations)
        assert report.total_checked == report.satisfied + len(report.violations)
        assert len(report.violations) >= 1
        v = report.violations[0]
        assert v.missing_contract == "audit_event"
        assert v.rule_resource_type == "database"

    def test_empty_edges_empty_report(self, tmp_path) -> None:
        """Verifier EmptyEdgesImpliesEmptyReport: no edges → empty report."""
        from registry.crawl_store import CrawlStore

        db_path = tmp_path / "crawl.db"
        with CrawlStore(db_path) as store:
            rules = [CrossCuttingRule("database", ["audit_event"], "wrap")]
            report = check_behavioral_contracts(store, rules)

        assert report.total_checked == 0
        assert report.satisfied == 0
        assert len(report.violations) == 0

    def test_all_compliant_zero_violations(self, tmp_path) -> None:
        """Verifier ZeroViolationsWhenAllCompliant: all outs present → 0 violations."""
        from registry.crawl_store import CrawlStore

        db_path = tmp_path / "crawl.db"
        with CrawlStore(db_path) as store:
            # Callee HAS the required audit_event out
            callee = _make_fn(
                "00000000-0000-0000-0000-000000000003",
                "save_record",
                file_path="src/db/store.py",
                outs=[
                    OutField(name=OutKind.OK, type_str="dict", description="result"),
                    OutField(name=OutKind.SIDE_EFFECT, type_str="audit_event", description="audit"),
                ],
            )
            store.upsert_record(callee)

            caller = _make_fn(
                "00000000-0000-0000-0000-000000000004",
                "process",
                ins=[InField(
                    name="db_result", type_str="dict",
                    source=InSource.INTERNAL_CALL,
                    source_uuid="00000000-0000-0000-0000-000000000003",
                )],
            )
            store.upsert_record(caller)

            rules = [CrossCuttingRule("database", ["audit_event"], "wrap")]
            report = check_behavioral_contracts(store, rules)

        assert len(report.violations) == 0
        assert report.total_checked == report.satisfied + len(report.violations)

    def test_no_match_no_count(self, tmp_path) -> None:
        """Verifier NoMatchNoCount: rules that match no functions → total_checked == 0."""
        from registry.crawl_store import CrawlStore

        db_path = tmp_path / "crawl.db"
        with CrawlStore(db_path) as store:
            # A normal function that doesn't match "database" resource_type
            callee = _make_fn(
                "00000000-0000-0000-0000-000000000005",
                "compute",
                file_path="src/utils.py",
                outs=[OutField(name=OutKind.OK, type_str="int", description="sum")],
            )
            store.upsert_record(callee)

            caller = _make_fn(
                "00000000-0000-0000-0000-000000000006",
                "orchestrate",
                ins=[InField(
                    name="val", type_str="int",
                    source=InSource.INTERNAL_CALL,
                    source_uuid="00000000-0000-0000-0000-000000000005",
                )],
            )
            store.upsert_record(caller)

            rules = [CrossCuttingRule("database", ["audit_event"], "wrap")]
            report = check_behavioral_contracts(store, rules)

        assert report.total_checked == 0
        assert report.satisfied == 0
        assert len(report.violations) == 0

    def test_no_false_positives(self, tmp_path) -> None:
        """Verifier NoFalsePositives: callee has all required outs → no violation."""
        from registry.crawl_store import CrawlStore

        db_path = tmp_path / "crawl.db"
        with CrawlStore(db_path) as store:
            # External API callee with all required outs
            callee = _make_fn(
                "00000000-0000-0000-0000-000000000007",
                "call_api",
                file_path="src/api_client.py",
                outs=[
                    OutField(name=OutKind.OK, type_str="dict", description="response"),
                    OutField(name=OutKind.SIDE_EFFECT, type_str="span_id", description="span"),
                    OutField(name=OutKind.SIDE_EFFECT, type_str="trace_context", description="trace"),
                ],
                is_external=True,
            )
            store.upsert_record(callee)

            caller = _make_fn(
                "00000000-0000-0000-0000-000000000008",
                "do_work",
                ins=[InField(
                    name="api_result", type_str="dict",
                    source=InSource.INTERNAL_CALL,
                    source_uuid="00000000-0000-0000-0000-000000000007",
                )],
            )
            store.upsert_record(caller)

            rules = [CrossCuttingRule("external_api", ["span_id", "trace_context"], "pre")]
            report = check_behavioral_contracts(store, rules)

        assert len(report.violations) == 0
        assert report.satisfied >= 1
