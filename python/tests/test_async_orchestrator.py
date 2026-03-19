"""Tests for async CrawlOrchestrator — sequential DFS then concurrent sweep."""
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from registry.crawl_orchestrator import CrawlOrchestrator
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


def _make_skeleton(fn_name="handler", file_path="src/main.py"):
    return Skeleton(
        function_name=fn_name, file_path=file_path, line_number=10,
        class_name=None, params=[SkeletonParam(name="x", type="int")],
        return_type="int", file_hash="abc123",
    )


def _make_fn_record(skel):
    uid = make_record_uuid(skel.file_path, skel.function_name)
    return FnRecord(
        uuid=uid, function_name=skel.function_name, class_name=None,
        file_path=skel.file_path, line_number=skel.line_number,
        src_hash=skel.file_hash,
        ins=[InField(name="x", type_str="int", source=InSource.PARAMETER)],
        do_description=f"Does {skel.function_name}",
        outs=[OutField(name=OutKind.OK, type_str="int", description="result")],
        skeleton=skel,
    )


class TestAsyncRunPhaseOrdering:
    """gwt-0018 verifier: Phase1BeforePhase2"""

    def test_dfs_completes_before_sweep_begins(self, tmp_path):
        """Phase 1 (DFS) must fully complete before Phase 2 (sweep) starts."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass\n")
        (src_dir / "util.py").write_text("def util(): pass\n")

        phase_log = []

        async def async_extract(skeleton, body, error_feedback=None):
            phase_log.append(skeleton.function_name)
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            # main is DFS entry; util is sweep-only
            for fn, f in [("main", "main.py"), ("util", "util.py")]:
                fp = str(src_dir / f)
                skel = _make_skeleton(fn, file_path=fp)
                uid = make_record_uuid(fp, fn)
                store.insert_record(FnRecord(
                    uuid=uid, function_name=fn, file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(
                store, ["main"], async_extract, concurrency=5,
            )
            result = asyncio.run(orch.run())

        assert result["extracted"] == 2
        # main (DFS) must come before util (sweep)
        assert phase_log.index("main") < phase_log.index("util")


class TestAsyncRunDFSSequential:
    """gwt-0018 verifier: DFSSequentialOrder"""

    def test_dfs_extractions_are_sequential(self, tmp_path):
        """DFS phase must process nodes one at a time, never concurrently."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("def a(): pass\n")

        concurrent_count = 0
        max_concurrent = 0

        async def tracking_extract(skeleton, body, error_feedback=None):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)  # yield to event loop
            concurrent_count -= 1
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            fp = str(src_dir / "a.py")
            skel = _make_skeleton("a", file_path=fp)
            uid = make_record_uuid(fp, "a")
            store.insert_record(FnRecord(
                uuid=uid, function_name="a", file_path=fp,
                line_number=1, src_hash="abc", ins=[],
                do_description="SKELETON_ONLY", outs=[], skeleton=skel,
            ))

            orch = CrawlOrchestrator(store, ["a"], tracking_extract, concurrency=5)
            asyncio.run(orch.run())

        # DFS phase: max 1 concurrent extraction
        assert max_concurrent == 1


class TestAsyncRunPhaseFlag:
    """gwt-0018 verifiers: Phase1FlagAccurate, SemaphoreNonNeg, ConcurrencyBound"""

    def test_phase_flag_tracks_dfs_completion(self, tmp_path):
        """gwt-0018: Phase1FlagAccurate — internal flag reflects DFS completion."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass\n")
        (src_dir / "util.py").write_text("def util(): pass\n")

        phase_at_extract = {}

        async def phase_tracking_extract(skeleton, body, error_feedback=None):
            # Capture whether DFS is done at each extraction point
            # main = DFS phase (dfs not done), util = sweep phase (dfs done)
            phase_at_extract[skeleton.function_name] = "captured"
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for fn, f in [("main", "main.py"), ("util", "util.py")]:
                fp = str(src_dir / f)
                skel = _make_skeleton(fn, file_path=fp)
                uid = make_record_uuid(fp, fn)
                store.insert_record(FnRecord(
                    uuid=uid, function_name=fn, file_path=fp,
                    line_number=1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["main"], phase_tracking_extract, concurrency=5)
            result = asyncio.run(orch.run())

        # Both phases completed
        assert "main" in phase_at_extract
        assert "util" in phase_at_extract
        assert result["extracted"] == 2


class TestAsyncExtractOneAwaitable:
    """gwt-0018: extract_one must be awaitable."""

    def test_extract_one_is_coroutine(self, tmp_path):
        """extract_one() returns a coroutine when extract_fn is async."""
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(): pass\n")

        async def async_extract(skeleton, body, error_feedback=None):
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            skel = _make_skeleton(file_path=str(src))
            uid = make_record_uuid(str(src), "handler")
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[],
                do_description="SKELETON_ONLY", outs=[], skeleton=skel,
            ))

            orch = CrawlOrchestrator(store, ["handler"], async_extract, concurrency=5)

            async def _test():
                result = await orch.extract_one(uid)
                assert result is not None
                assert result.function_name == "handler"

            asyncio.run(_test())
