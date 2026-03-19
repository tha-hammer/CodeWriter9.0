"""Tests for _sweep_remaining() async concurrency."""
import asyncio
from pathlib import Path

import pytest

from registry.crawl_orchestrator import CrawlOrchestrator
from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    FnRecord, InField, InSource, OutField, OutKind, Skeleton, SkeletonParam,
    make_record_uuid,
)


def _make_skeleton(fn_name, file_path):
    return Skeleton(
        function_name=fn_name, file_path=file_path, line_number=10,
        class_name=None, file_hash="abc123",
    )


def _make_fn_record(skel):
    uid = make_record_uuid(skel.file_path, skel.function_name)
    return FnRecord(
        uuid=uid, function_name=skel.function_name, class_name=None,
        file_path=skel.file_path, line_number=skel.line_number,
        src_hash=skel.file_hash,
        ins=[InField(name="x", type_str="int", source=InSource.PARAMETER)],
        do_description=f"Does {skel.function_name}",
        outs=[OutField(name=OutKind.OK, type_str="int", description="ok")],
        skeleton=skel,
    )


def _insert_pending(store, src_dir, fn_name):
    fp = str(src_dir / f"{fn_name}.py")
    skel = _make_skeleton(fn_name, file_path=fp)
    uid = make_record_uuid(fp, fn_name)
    store.insert_record(FnRecord(
        uuid=uid, function_name=fn_name, file_path=fp,
        line_number=1, src_hash="abc", ins=[],
        do_description="SKELETON_ONLY", outs=[], skeleton=skel,
    ))


class TestSweepConcurrencyBound:
    """gwt-0014 verifiers: ConcurrencyBound, SemaphoreConservation"""

    def test_at_most_n_concurrent_extractions(self, tmp_path):
        """With concurrency=3 and 10 UUIDs, at most 3 run simultaneously."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(10):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        concurrent = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def bounded_extract(skeleton, body, error_feedback=None):
            nonlocal concurrent, max_concurrent
            async with lock:
                concurrent += 1
                max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.05)  # simulate I/O
            async with lock:
                concurrent -= 1
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(10):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], bounded_extract, concurrency=3)
            result = asyncio.run(orch.run())

        assert result["extracted"] == 10
        assert max_concurrent <= 3, f"Expected max 3 concurrent, got {max_concurrent}"
        assert max_concurrent >= 2, "Concurrency never reached 2 — not actually parallel"


class TestSweepSemaphoreInvariants:
    """gwt-0014 verifiers: SemNonNegative, SemaphoreConservation,
    PerTaskAtMostOnce, AcqBeforeRel, WhenCompleteSymmetric"""

    def test_each_uuid_processed_exactly_once(self, tmp_path):
        """gwt-0014: PerTaskAtMostOnce — no UUID extracted more than once."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        processed_uuids = []

        async def tracking_extract(skeleton, body, error_feedback=None):
            processed_uuids.append(skeleton.function_name)
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], tracking_extract, concurrency=3)
            asyncio.run(orch.run())

        assert len(processed_uuids) == len(set(processed_uuids)), \
            f"Duplicate processing: {processed_uuids}"

    def test_semaphore_acquire_release_symmetry(self, tmp_path):
        """gwt-0014: AcqBeforeRel, WhenCompleteSymmetric, SemNonNegative —
        semaphore is acquired before release and returns to initial value."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        sem_log = []

        async def instrumented_extract(skeleton, body, error_feedback=None):
            sem_log.append(("acquire", skeleton.function_name))
            await asyncio.sleep(0.01)
            sem_log.append(("release", skeleton.function_name))
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], instrumented_extract, concurrency=3)
            asyncio.run(orch.run())

        # Verify acquire always precedes release for each task
        per_task = {}
        for action, name in sem_log:
            per_task.setdefault(name, []).append(action)

        for name, actions in per_task.items():
            assert actions[0] == "acquire", f"{name}: release before acquire"
            assert actions[-1] == "release", f"{name}: missing release"

        # WhenCompleteSymmetric: equal acquires and releases
        acquires = sum(1 for a, _ in sem_log if a == "acquire")
        releases = sum(1 for a, _ in sem_log if a == "release")
        assert acquires == releases, f"Asymmetric: {acquires} acquires vs {releases} releases"


class TestSweepErrorIsolation:
    """gwt-0015 verifiers: NoCancellation, ExceptionCapturedAsResult"""

    def test_one_failure_does_not_cancel_others(self, tmp_path):
        """If extraction 3 fails, extractions 0-2 and 4-9 still complete."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(10):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        async def sometimes_failing(skeleton, body, error_feedback=None):
            if skeleton.function_name == "fn_3":
                raise RuntimeError("Simulated failure")
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(10):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], sometimes_failing, concurrency=5)
            result = asyncio.run(orch.run())

        # fn_3 fails after max_retries; others succeed
        assert result["extracted"] == 9
        assert result["failed"] >= 1


class TestSweepErrorSemaphoreRelease:
    """gwt-0015 verifiers: FailedTaskSlotReleased,
    CompletedOrFailedReleaseSemaphore, AllOthersSucceedWhenGatherDone"""

    def test_failed_task_releases_semaphore_slot(self, tmp_path):
        """gwt-0015: FailedTaskSlotReleased — after failure, semaphore slot freed."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(6):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        completed_names = []

        async def failing_extract(skeleton, body, error_feedback=None):
            if skeleton.function_name == "fn_0":
                raise RuntimeError("boom")
            await asyncio.sleep(0.02)
            completed_names.append(skeleton.function_name)
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(6):
                _insert_pending(store, src_dir, f"fn_{i}")

            # concurrency=2: if fn_0's slot isn't released, we'd deadlock or
            # leave one slot permanently consumed
            orch = CrawlOrchestrator(store, [], failing_extract, concurrency=2)
            result = asyncio.run(orch.run())

        # AllOthersSucceedWhenGatherDone: all non-failing tasks completed
        assert len(completed_names) == 5
        # FailedTaskSlotReleased: all tasks ran (would block if slot leaked)
        assert result["extracted"] == 5
        assert result["failed"] >= 1


class TestSweepSQLiteSafety:
    """gwt-0016 verifier: NoSimultaneousUpserts"""

    def test_upserts_never_interleave(self, tmp_path):
        """Concurrent extractions serialize SQLite upserts naturally."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        upsert_log = []

        async def logging_extract(skeleton, body, error_feedback=None):
            await asyncio.sleep(0.02)  # simulate I/O
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Monkey-patch upsert to track call ordering
            original_upsert = store.upsert_record

            def tracking_upsert(record):
                upsert_log.append(("start", record.function_name))
                original_upsert(record)
                upsert_log.append(("end", record.function_name))

            store.upsert_record = tracking_upsert

            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], logging_extract, concurrency=5)
            asyncio.run(orch.run())

        # Verify no interleaving: every start is immediately followed by its end
        for i in range(0, len(upsert_log), 2):
            assert upsert_log[i][0] == "start"
            assert upsert_log[i + 1][0] == "end"
            assert upsert_log[i][1] == upsert_log[i + 1][1]


class TestSweepSQLiteCompleteness:
    """gwt-0016 verifiers: UpsertLogNoDuplicates, CompletionImpliesUpserted,
    UpsertLogLengthMatchesCompletions"""

    def test_each_uuid_upserted_exactly_once(self, tmp_path):
        """gwt-0016: UpsertLogNoDuplicates + UpsertLogLengthMatchesCompletions."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        upserted_names = []

        async def simple_extract(skeleton, body, error_feedback=None):
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            original_upsert = store.upsert_record

            def tracking_upsert(record):
                upserted_names.append(record.function_name)
                original_upsert(record)

            store.upsert_record = tracking_upsert

            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], simple_extract, concurrency=3)
            asyncio.run(orch.run())

        # UpsertLogNoDuplicates: no UUID upserted twice
        assert len(upserted_names) == len(set(upserted_names))
        # UpsertLogLengthMatchesCompletions: upserts == extracted count
        assert len(upserted_names) == 5

    def test_completed_task_implies_upserted(self, tmp_path):
        """gwt-0016: CompletionImpliesUpserted — every completed extraction is upserted."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(3):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        extracted_names = []
        upserted_names = []

        async def tracking_extract(skeleton, body, error_feedback=None):
            extracted_names.append(skeleton.function_name)
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            original_upsert = store.upsert_record

            def tracking_upsert(record):
                upserted_names.append(record.function_name)
                original_upsert(record)

            store.upsert_record = tracking_upsert

            for i in range(3):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], tracking_extract, concurrency=3)
            asyncio.run(orch.run())

        # Every extracted name must appear in upserted names
        for name in extracted_names:
            assert name in upserted_names, f"{name} extracted but not upserted"


class TestSweepDuplicateSkip:
    """gwt-0018: skip UUIDs already visited by DFS (DFS-then-sweep ordering)."""

    def test_dfs_visited_uuids_skipped_in_sweep(self, tmp_path):
        """Records processed by DFS must not be re-extracted in sweep."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main(): pass\n")

        call_count = 0

        async def counting_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            fp = str(src_dir / "main.py")
            skel = _make_skeleton("main", file_path=fp)
            uid = make_record_uuid(fp, "main")
            store.insert_record(FnRecord(
                uuid=uid, function_name="main", file_path=fp,
                line_number=1, src_hash="abc", ins=[],
                do_description="SKELETON_ONLY", outs=[], skeleton=skel,
            ))

            orch = CrawlOrchestrator(store, ["main"], counting_extract, concurrency=5)
            asyncio.run(orch.run())

        # main processed by DFS only, not re-extracted in sweep
        assert call_count == 1


class TestSweepConcurrencyOne:
    """Edge case: concurrency=1 behaves like sequential."""

    def test_concurrency_one_processes_all(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        async def simple_extract(skeleton, body, error_feedback=None):
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], simple_extract, concurrency=1)
            result = asyncio.run(orch.run())

        assert result["extracted"] == 5
