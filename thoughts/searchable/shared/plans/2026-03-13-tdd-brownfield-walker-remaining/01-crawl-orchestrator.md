---
component: 1
title: "DFS Crawl Orchestrator (LLM Extraction)"
new_files: ["python/registry/crawl_orchestrator.py"]
test_files: ["python/tests/test_crawl_orchestrator.py"]
behaviors: 10
beads: ["replication_ab_bench-6vo", "replication_ab_bench-279", "replication_ab_bench-ykn", "replication_ab_bench-1wv", "replication_ab_bench-0zm", "replication_ab_bench-ait", "replication_ab_bench-5uv", "replication_ab_bench-3y7", "replication_ab_bench-526", "replication_ab_bench-szz"]
depends_on: [3, 4, 5, 6]
---

## Component 1: DFS Crawl Orchestrator (LLM Extraction)

**New file**: `python/registry/crawl_orchestrator.py`
**Test file**: `python/tests/test_crawl_orchestrator.py`

The orchestrator takes a populated CrawlStore (skeleton-only records from Phase 0) and entry points, then performs a DFS crawl using an LLM to extract full IN:DO:OUT for each function. The LLM is injected as a callable — the orchestrator never imports an LLM client directly.

### Behavior 1.1: Orchestrator accepts extract function and CrawlStore

**Given**: A CrawlStore with skeleton-only records and a list of entry point function names
**When**: `CrawlOrchestrator(store, entry_points, extract_fn)` is constructed
**Then**: The orchestrator holds references to the store, entry points, and extract function

#### 🔴 Red: Write Failing Test

**File**: `python/tests/test_crawl_orchestrator.py`
```python
"""Tests for the DFS crawl orchestrator (LLM extraction)."""
from __future__ import annotations

from pathlib import Path

import pytest

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
        do_description="Handles incoming request",
        do_steps=["Parse request", "Return response"],
        outs=[OutField(name=OutKind.OK, type_str="Response", description="Success")],
        operational_claim="Handles request and returns response",
        skeleton=skel,
    )
    defaults.update(overrides)
    return FnRecord(**defaults)


def _fake_extract(skeleton: Skeleton, body: str) -> FnRecord:
    """Deterministic fake LLM extraction."""
    return _make_fn_record_from_skeleton(skeleton)


class TestOrchestratorInit:
    def test_construction(self, tmp_path: Path):
        with CrawlStore(tmp_path / "crawl.db") as store:
            orch = CrawlOrchestrator(store=store, entry_points=["handler"], extract_fn=_fake_extract)
            assert orch.store is store
            assert orch.entry_points == ["handler"]
```

#### 🟢 Green: Minimal Implementation

**File**: `python/registry/crawl_orchestrator.py`
```python
"""DFS crawl orchestrator — drives LLM extraction over skeleton-only records.

The orchestrator walks the CrawlStore's skeleton records depth-first from
entry points, calling an injected extract_fn for each function to produce
full IN:DO:OUT FnRecords.
"""
from __future__ import annotations

from typing import Callable, Protocol

from registry.crawl_store import CrawlStore
from registry.crawl_types import FnRecord, Skeleton


class CrawlOrchestrator:
    def __init__(
        self,
        store: CrawlStore,
        entry_points: list[str],
        extract_fn: Callable[[Skeleton, str], FnRecord],
    ) -> None:
        self.store = store
        self.entry_points = entry_points
        self.extract_fn = extract_fn
```

### Behavior 1.2: Single function extraction succeeds and stores result

**Given**: A CrawlStore with one skeleton-only record and a source file on disk
**When**: `orch.extract_one(uuid)` is called
**Then**: The extract_fn is invoked with the skeleton and function body text, and the resulting FnRecord is upserted into the store

```python
class TestExtractOne:
    def test_extracts_and_stores(self, tmp_path: Path):
        # Write a source file
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    return Response(200)\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Insert skeleton-only record
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))

            extracted = []
            def tracking_extract(skeleton, body):
                rec = _fake_extract(skeleton, body)
                extracted.append((skeleton, body))
                return rec

            orch = CrawlOrchestrator(store, ["handler"], tracking_extract)
            orch.extract_one(uid)

            # Verify the record is no longer skeleton-only
            rec = store.get_record(uid)
            assert rec.do_description != "SKELETON_ONLY"
            assert len(extracted) == 1
            assert "def handler" in extracted[0][1]
```

### Behavior 1.3: Extraction failure retries up to 3 times with error feedback

**Given**: An extract_fn that raises `ValidationError` on the first 2 calls then succeeds
**When**: `orch.extract_one(uuid)` is called
**Then**: The function is called 3 times total, the third result is stored

```python
class TestRetry:
    def test_retries_on_validation_error(self, tmp_path: Path):
        from pydantic import ValidationError

        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        call_count = 0
        def failing_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Invalid output (attempt {call_count})")
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], failing_extract)
            orch.extract_one(uid)

            assert call_count == 3
            rec = store.get_record(uid)
            assert rec.do_description != "SKELETON_ONLY"
```

### Behavior 1.4: Exhausted retries store EXTRACTION_FAILED stub

**Given**: An extract_fn that always raises errors
**When**: `orch.extract_one(uuid)` is called
**Then**: After 3 retries, a stub record with `do_description="EXTRACTION_FAILED"` is stored

```python
    def test_exhausted_retries_store_stub(self, tmp_path: Path):
        src = tmp_path / "src" / "main.py"
        src.parent.mkdir(parents=True)
        src.write_text("def handler(request):\n    pass\n")

        skel = _make_skeleton(file_path=str(src))
        uid = make_record_uuid(str(src), "handler")

        def always_fail(skeleton, body, error_feedback=None):
            raise ValueError("Cannot extract")

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], always_fail)
            orch.extract_one(uid)

            rec = store.get_record(uid)
            assert rec.do_description == "EXTRACTION_FAILED"
            assert "LLM extraction failed" in rec.failure_modes[0]
```

### Behavior 1.5: DFS crawl traverses from entry points following internal_call sources

**Given**: A CrawlStore with records for `handler` (calls `validate`) and `validate` (no calls)
**When**: `orch.run()` is called
**Then**: Both functions are extracted in DFS order (handler first, then validate)

```python
class TestDFSCrawl:
    def test_dfs_follows_internal_calls(self, tmp_path: Path):
        # Write source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text(
            "def handler(request):\n    result = validate(request)\n    return result\n"
        )
        (src_dir / "validate.py").write_text(
            "def validate(data):\n    return data is not None\n"
        )

        handler_skel = _make_skeleton("handler", str(src_dir / "main.py"))
        validate_skel = _make_skeleton("validate", str(src_dir / "validate.py"))
        handler_uid = make_record_uuid(str(src_dir / "main.py"), "handler")
        validate_uid = make_record_uuid(str(src_dir / "validate.py"), "validate")

        extraction_order = []

        def ordering_extract(skeleton, body, error_feedback=None):
            extraction_order.append(skeleton.function_name)
            rec = _make_fn_record_from_skeleton(skeleton)
            if skeleton.function_name == "handler":
                # handler has an internal_call to validate
                rec = _make_fn_record_from_skeleton(skeleton, ins=[
                    InField(name="request", type_str="Request", source=InSource.PARAMETER),
                    InField(
                        name="result", type_str="bool", source=InSource.INTERNAL_CALL,
                        source_function="validate",
                        source_file=str(src_dir / "validate.py"),
                    ),
                ])
            return rec

        with CrawlStore(tmp_path / "crawl.db") as store:
            for skel, uid in [(handler_skel, handler_uid), (validate_skel, validate_uid)]:
                store.insert_record(FnRecord(
                    uuid=uid, function_name=skel.function_name, file_path=skel.file_path,
                    line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                    outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["handler"], ordering_extract)
            result = orch.run()

            assert extraction_order == ["handler", "validate"]
            assert result["extracted"] == 2
```

### Behavior 1.6: DFS visited set prevents cycles

**Given**: Functions A and B that call each other
**When**: `orch.run()` is called starting from A
**Then**: Each function is extracted exactly once

```python
    def test_visited_set_prevents_cycles(self, tmp_path: Path):
        src = tmp_path / "cycle.py"
        src.write_text("def a():\n    b()\ndef b():\n    a()\n")

        skel_a = _make_skeleton("a", str(src))
        skel_b = _make_skeleton("b", str(src))
        uid_a = make_record_uuid(str(src), "a")
        uid_b = make_record_uuid(str(src), "b")

        call_counts: dict[str, int] = {}

        def counting_extract(skeleton, body, error_feedback=None):
            call_counts[skeleton.function_name] = call_counts.get(skeleton.function_name, 0) + 1
            rec = _make_fn_record_from_skeleton(skeleton)
            other = "b" if skeleton.function_name == "a" else "a"
            return _make_fn_record_from_skeleton(skeleton, ins=[
                InField(
                    name="result", type_str="None", source=InSource.INTERNAL_CALL,
                    source_function=other, source_file=str(src),
                ),
            ])

        with CrawlStore(tmp_path / "crawl.db") as store:
            for skel, uid in [(skel_a, uid_a), (skel_b, uid_b)]:
                store.insert_record(FnRecord(
                    uuid=uid, function_name=skel.function_name, file_path=skel.file_path,
                    line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                    outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(store, ["a"], counting_extract)
            orch.run()

            assert call_counts == {"a": 1, "b": 1}
```

### Behavior 1.7: External calls create AX boundary records

**Given**: A function that calls an external library function (e.g. `redis.get`)
**When**: The extract_fn returns an InField with `source=InSource.EXTERNAL`
**Then**: An AxRecord is created for the external boundary (never traversed)

```python
    def test_external_calls_create_ax_records(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    data = redis.get('key')\n    return data\n")
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        def ext_extract(skeleton, body, error_feedback=None):
            return _make_fn_record_from_skeleton(skeleton, ins=[
                InField(
                    name="data", type_str="bytes", source=InSource.EXTERNAL,
                    source_function="redis.get", source_file="redis",
                ),
            ])

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], ext_extract)
            result = orch.run()

            assert result["ax_records"] >= 1
            # External records should exist in the store
            all_uuids = store.get_all_uuids()
            assert len(all_uuids) >= 2  # handler + redis.get AX record
```

### Behavior 1.8: --max-functions limits DFS scope

**Given**: A CrawlStore with 10 skeleton records and `max_functions=3`
**When**: `orch.run()` is called
**Then**: At most 3 functions are extracted

```python
    def test_max_functions_limits_scope(self, tmp_path: Path):
        src = tmp_path / "big.py"
        funcs = "\n".join(f"def func_{i}():\n    pass\n" for i in range(10))
        src.write_text(funcs)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(10):
                skel = _make_skeleton(f"func_{i}", str(src))
                uid = make_record_uuid(str(src), f"func_{i}")
                store.insert_record(FnRecord(
                    uuid=uid, function_name=f"func_{i}", file_path=str(src),
                    line_number=i * 3 + 1, src_hash="abc", ins=[],
                    do_description="SKELETON_ONLY", outs=[], skeleton=skel,
                ))

            orch = CrawlOrchestrator(
                store, [f"func_{i}" for i in range(10)],
                _fake_extract, max_functions=3,
            )
            result = orch.run()
            assert result["extracted"] == 3
```

### Behavior 1.9: run() returns summary counters

**Given**: A crawl with mixed outcomes (success, retry, failure)
**When**: `orch.run()` completes
**Then**: The return dict contains `extracted`, `failed`, `skipped`, `ax_records` counters

```python
    def test_run_returns_counters(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    pass\n")
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        with CrawlStore(tmp_path / "crawl.db") as store:
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash="abc", ins=[], do_description="SKELETON_ONLY",
                outs=[], skeleton=skel,
            ))
            orch = CrawlOrchestrator(store, ["handler"], _fake_extract)
            result = orch.run()

            assert "extracted" in result
            assert "failed" in result
            assert "skipped" in result
            assert "ax_records" in result
            assert result["extracted"] == 1
```

### Behavior 1.10: Incremental crawl skips records with matching hash

**Given**: A CrawlStore with a fully-extracted record whose src_hash matches the current file
**When**: `orch.run()` is called with `incremental=True`
**Then**: The record is skipped (not re-extracted)

```python
    def test_incremental_skips_up_to_date(self, tmp_path: Path):
        src = tmp_path / "main.py"
        src.write_text("def handler():\n    pass\n")
        import hashlib
        file_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        skel = _make_skeleton("handler", str(src))
        uid = make_record_uuid(str(src), "handler")

        call_count = 0
        def counting_extract(skeleton, body, error_feedback=None):
            nonlocal call_count
            call_count += 1
            return _make_fn_record_from_skeleton(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            # Insert a FULLY extracted record (not SKELETON_ONLY)
            store.insert_record(FnRecord(
                uuid=uid, function_name="handler", file_path=str(src),
                line_number=1, src_hash=file_hash,
                ins=[InField(name="x", type_str="int", source=InSource.PARAMETER)],
                do_description="Already extracted",
                outs=[OutField(name=OutKind.OK, type_str="None", description="ok")],
                skeleton=skel,
            ))

            orch = CrawlOrchestrator(store, ["handler"], counting_extract, incremental=True)
            result = orch.run()

            assert call_count == 0
            assert result["skipped"] == 1
```

### Success Criteria — Component 1

**Automated:**
- [x] All tests in `test_crawl_orchestrator.py` pass
- [x] All existing tests still pass: `python -m pytest tests/ -x`
- [x] No import errors: `python -c "from registry.crawl_orchestrator import CrawlOrchestrator"`

---
