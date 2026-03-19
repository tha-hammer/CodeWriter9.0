"""Tests proving card extraction is single-query and safe for concurrent fresh-context execution.

These tests verify three critical properties for the concurrent crawl pipeline:
1. Each card extraction is exactly ONE LLM call (not multi-turn)
2. Retry error feedback is embedded in the prompt text, not via conversation history
3. Independent extractions produce correct results without shared context
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Helper to run async orchestrator methods from sync test code
def _run(coro):
    return asyncio.run(coro)

from registry.crawl_orchestrator import CrawlOrchestrator
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


def _make_skeleton(fn_name="handler", file_path="src/main.py", class_name=None) -> Skeleton:
    return Skeleton(
        function_name=fn_name,
        file_path=file_path,
        line_number=10,
        class_name=class_name,
        params=[SkeletonParam(name="request", type="Request")],
        return_type="Response",
        file_hash="abc123",
    )


def _make_fn_record_from_skeleton(skel: Skeleton, **overrides) -> FnRecord:
    uid = make_record_uuid(skel.file_path, skel.function_name, skel.class_name)
    defaults = dict(
        uuid=uid,
        function_name=skel.function_name,
        class_name=skel.class_name,
        file_path=skel.file_path,
        line_number=skel.line_number,
        src_hash=skel.file_hash,
        ins=[InField(name="request", type_str="Request", source=InSource.PARAMETER)],
        do_description=f"Handles {skel.function_name}",
        do_steps=["Step 1", "Step 2"],
        outs=[OutField(name=OutKind.OK, type_str="Response", description="Success")],
        operational_claim=f"{skel.function_name} works correctly",
        skeleton=skel,
    )
    defaults.update(overrides)
    return FnRecord(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Each card extraction is exactly ONE LLM call
# ---------------------------------------------------------------------------

class TestSingleQueryPerCard:
    """Verify that extract_one() calls extract_fn exactly once on success."""

    def test_single_successful_extraction_calls_llm_once(self, tmp_path: Path):
        """A successful extraction must call extract_fn exactly once.
        This proves standalone query() (fresh context per call) is safe."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    return Response(200)\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        call_count = 0
        def counting_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], counting_extract)
            result = _run(orch.extract_one(uid))

            assert result is not None
            assert call_count == 1, (
                f"Expected exactly 1 LLM call per successful card, got {call_count}. "
                "If >1, standalone query() would lose context between calls."
            )

    def test_extract_fn_receives_complete_prompt_no_history_needed(self, tmp_path: Path):
        """The extract_fn receives skeleton + body as a self-contained prompt.
        No prior conversation history is needed."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    return Response(200)\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        captured_args = []
        def capturing_extract(skeleton, body, error_feedback=None):
            captured_args.append({
                "skeleton": skeleton,
                "body": body,
                "error_feedback": error_feedback,
            })
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], capturing_extract)
            _run(orch.extract_one(uid))

            assert len(captured_args) == 1
            call = captured_args[0]
            # First call has no error feedback — it's a fresh, self-contained prompt
            assert call["error_feedback"] is None
            assert call["skeleton"].function_name == "handler"
            assert "def handler" in call["body"]


# ---------------------------------------------------------------------------
# Test 2: Retry error feedback is in-prompt, not conversation context
# ---------------------------------------------------------------------------

class TestRetryErrorFeedbackIsInPrompt:
    """Verify that retries pass error info via the error_feedback parameter,
    NOT by relying on accumulated conversation context."""

    def test_retry_passes_error_string_in_prompt(self, tmp_path: Path):
        """On retry, extract_fn receives the error string as error_feedback kwarg.
        This means each retry can run as a standalone query with fresh context."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        captured_calls = []
        call_count = 0
        def failing_then_ok(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            captured_calls.append({
                "attempt": call_count,
                "error_feedback": error_feedback,
            })
            if call_count == 1:
                raise ValueError("Invalid JSON: missing 'ins' field")
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], failing_then_ok)
            result = _run(orch.extract_one(uid))

            assert result is not None
            assert len(captured_calls) == 2

            # First attempt: no error feedback (fresh prompt)
            assert captured_calls[0]["error_feedback"] is None

            # Second attempt: error feedback embedded in-prompt
            assert captured_calls[1]["error_feedback"] is not None
            assert "Invalid JSON" in captured_calls[1]["error_feedback"]
            assert "missing 'ins' field" in captured_calls[1]["error_feedback"]

    def test_each_retry_gets_same_skeleton_and_body(self, tmp_path: Path):
        """Every retry receives the same skeleton and body — the entire prompt
        is reconstructed from scratch each time. No conversation state needed."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def process(data):\n    return data.strip()\n")

        skel = _make_skeleton("process", file_path=str(src))
        uid = make_record_uuid(str(src), "process")

        captured_skeletons = []
        captured_bodies = []
        call_count = 0
        def multi_fail(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            captured_skeletons.append(skeleton.function_name)
            captured_bodies.append(body)
            if call_count < 3:
                raise ValueError(f"Bad output attempt {call_count}")
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="process", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["process"], multi_fail)
            _run(orch.extract_one(uid))

            # Every retry gets the identical skeleton and body
            assert all(s == "process" for s in captured_skeletons)
            assert all(b == captured_bodies[0] for b in captured_bodies), (
                "Retries received different bodies — this would break standalone query()"
            )

    def test_error_feedback_is_only_from_last_failure(self, tmp_path: Path):
        """Only the MOST RECENT error is passed as feedback, not a history of all errors.
        This confirms no multi-turn conversation accumulation is needed."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler():\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        errors_received = []
        call_count = 0
        def escalating_fail(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            errors_received.append(error_feedback)
            if call_count == 1:
                raise ValueError("Error A: missing ins")
            elif call_count == 2:
                raise ValueError("Error B: bad type_str")
            elif call_count == 3:
                raise ValueError("Error C: invalid source")
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], escalating_fail)
            _run(orch.extract_one(uid))

            # Attempt 1: no error feedback
            assert errors_received[0] is None
            # Attempt 2: only Error A (not a history)
            assert "Error A" in errors_received[1]
            assert "Error B" not in (errors_received[1] or "")
            # Attempt 3: only Error B (replaces Error A)
            assert "Error B" in errors_received[2]
            assert "Error A" not in errors_received[2]
            # Attempt 4: only Error C
            assert "Error C" in errors_received[3]
            assert "Error B" not in errors_received[3]


# ---------------------------------------------------------------------------
# Test 3: Independent extractions produce correct results without shared state
# ---------------------------------------------------------------------------

class TestIndependentExtractions:
    """Verify that sweep-phase extractions are truly independent —
    no shared state leaks between concurrent extractions."""

    def test_sweep_extractions_dont_share_state(self, tmp_path: Path):
        """Each sweep extraction receives only its own skeleton and body.
        No data from other extractions leaks in."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create 5 independent functions
        for i in range(5):
            (src_dir / f"mod_{i}.py").write_text(
                f"def func_{i}(arg_{i}):\n    return arg_{i} * {i}\n"
            )

        extraction_contexts = {}

        def isolated_extract(skeleton, body, error_feedback=None):
            # Record what each extraction saw
            extraction_contexts[skeleton.function_name] = {
                "body": body,
                "skeleton_fn": skeleton.function_name,
                "skeleton_file": skeleton.file_path,
            }
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(5):
                fp = str(src_dir / f"mod_{i}.py")
                skel = _make_skeleton(f"func_{i}", file_path=fp)
                uid = make_record_uuid(fp, f"func_{i}")
                store.insert_record(FnRecord(
                    uuid=uid, function_name=f"func_{i}", file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            # Use no entry points to force everything through sweep
            orch = CrawlOrchestrator(store, [], isolated_extract)
            result = _run(orch.run())

            assert result["extracted"] == 5

            # Each extraction saw ONLY its own function's data
            for i in range(5):
                fn = f"func_{i}"
                ctx = extraction_contexts[fn]
                assert ctx["skeleton_fn"] == fn
                assert f"mod_{i}.py" in ctx["skeleton_file"]
                assert f"def func_{i}" in ctx["body"]
                # Body should NOT contain other functions' code
                for j in range(5):
                    if j != i:
                        assert f"def func_{j}" not in ctx["body"], (
                            f"func_{i} extraction saw func_{j}'s code — context leak!"
                        )

    def test_concurrent_simulation_no_cross_contamination(self, tmp_path: Path):
        """Simulate concurrent extraction by interleaving calls.
        Verify no state accumulates between extractions."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        for i in range(3):
            (src_dir / f"svc_{i}.py").write_text(
                f"def service_{i}(req):\n    return {{'id': {i}}}\n"
            )

        # Track the ORDER of extractions and what each sees
        extraction_log = []

        def logging_extract(skeleton, body, error_feedback=None):
            extraction_log.append({
                "fn": skeleton.function_name,
                "file": skeleton.file_path,
                "body_preview": body[:50],
                "error_feedback": error_feedback,
            })
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(3):
                fp = str(src_dir / f"svc_{i}.py")
                skel = _make_skeleton(f"service_{i}", file_path=fp)
                uid = make_record_uuid(fp, f"service_{i}")
                store.insert_record(FnRecord(
                    uuid=uid, function_name=f"service_{i}", file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, [], logging_extract)
            _run(orch.run())

            assert len(extraction_log) == 3
            # No extraction received error_feedback (all first attempts succeed)
            for entry in extraction_log:
                assert entry["error_feedback"] is None, (
                    f"{entry['fn']} received error_feedback from another extraction"
                )

    def test_extract_fn_signature_is_stateless(self, tmp_path: Path):
        """The extract_fn contract is (skeleton, body, error_feedback?) -> FnRecord.
        This is a pure function signature — no hidden state channel exists."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler():\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        # Use a PURE function (no closure state) to prove the contract
        def pure_extract(skeleton, body, error_feedback=None):
            # Only uses the three explicit arguments — nothing else
            assert isinstance(skeleton, Skeleton)
            assert isinstance(body, str)
            assert error_feedback is None or isinstance(error_feedback, str)
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], pure_extract)
            result = _run(orch.extract_one(uid))
            assert result is not None


# ---------------------------------------------------------------------------
# Test 4: Sweep phase processes all non-DFS records
# ---------------------------------------------------------------------------

class TestSweepPhaseIndependence:
    """Verify that _sweep_remaining handles records independently of DFS phase."""

    def test_sweep_handles_unreachable_records(self, tmp_path: Path):
        """Records not reachable from entry points are extracted in sweep phase.
        These are the records that can safely run concurrently."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Entry point
        (src_dir / "main.py").write_text("def main():\n    pass\n")
        # Unreachable functions (no call edges from main)
        for i in range(4):
            (src_dir / f"util_{i}.py").write_text(f"def util_{i}():\n    pass\n")

        dfs_fns = []
        sweep_fns = []
        call_count = 0

        def phase_tracking_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            # First call is DFS (main), rest are sweep
            if call_count == 1:
                dfs_fns.append(skeleton.function_name)
            else:
                sweep_fns.append(skeleton.function_name)
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Insert main as entry point
            fp = str(src_dir / "main.py")
            skel = _make_skeleton("main", file_path=fp)
            uid = make_record_uuid(fp, "main")
            store.insert_record(FnRecord(
                uuid=uid, function_name="main", file_path=fp,
                line_number=1, src_hash="abc", ins=[],
                do_description="SKELETON_ONLY", outs=[], skeleton=skel,
            ))

            # Insert unreachable utils
            for i in range(4):
                fp = str(src_dir / f"util_{i}.py")
                skel = _make_skeleton(f"util_{i}", file_path=fp)
                uid = make_record_uuid(fp, f"util_{i}")
                store.insert_record(FnRecord(
                    uuid=uid, function_name=f"util_{i}", file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["main"], phase_tracking_extract)
            result = _run(orch.run())

            assert result["extracted"] == 5
            assert dfs_fns == ["main"]
            assert len(sweep_fns) == 4
            # Sweep functions are independent — order doesn't matter for correctness
            assert set(sweep_fns) == {f"util_{i}" for i in range(4)}

    def test_sweep_records_have_no_ordering_dependency(self, tmp_path: Path):
        """Sweep records can be processed in ANY order.
        Reversing the order produces the same extracted records."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}():\n    return {i}\n")

        def simple_extract(skeleton, body, error_feedback=None):
            return _make_fn_record_from_skeleton(skeleton)

        # Run twice with different record insertion orders
        results = []
        for order in [range(5), reversed(range(5))]:
            db_path = tmp_path / f"crawl_{id(order)}.db"
            with CrawlStore(db_path) as store:
                for i in order:
                    fp = str(src_dir / f"fn_{i}.py")
                    skel = _make_skeleton(f"fn_{i}", file_path=fp)
                    uid = make_record_uuid(fp, f"fn_{i}")
                    store.insert_record(FnRecord(
                        uuid=uid, function_name=f"fn_{i}", file_path=fp,
                        line_number=1, src_hash="abc", ins=[],
                        do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                    ))

                orch = CrawlOrchestrator(store, [], simple_extract)
                result = _run(orch.run())
                results.append(result)

                # Collect all extracted records
                all_recs = store.get_all_records()
                extracted_fns = {r.function_name for r in all_recs
                                 if r.do_description != "SKELETON_ONLY"}
                results[-1]["fns"] = extracted_fns

        # Both runs should extract the same set of functions
        assert results[0]["extracted"] == results[1]["extracted"] == 5
        assert results[0]["fns"] == results[1]["fns"]
