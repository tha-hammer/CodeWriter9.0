"""DFS crawl orchestrator — drives LLM extraction over skeleton-only records.

The orchestrator walks the CrawlStore's skeleton records depth-first from
entry points, calling an injected extract_fn for each function to produce
full IN:DO:OUT FnRecords. The sweep phase runs remaining extractions
concurrently with semaphore-bounded asyncio.gather().
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Callable

from registry.crawl_store import CrawlStore
from registry.crawl_types import (
    AxRecord,
    FnRecord,
    InSource,
    Skeleton,
    make_record_uuid,
)

logger = logging.getLogger(__name__)

# Type for the extract function injected by the caller
ExtractFn = Callable  # (skeleton: Skeleton, body: str, error_feedback: str | None) -> FnRecord
ProgressFn = Callable  # (event: str, **kwargs) -> None

MAX_RETRIES = 5


def _read_function_body(
    file_path: str,
    function_name: str,
    line_number: int | None,
    project_root: Path | None = None,
) -> str:
    """Read the source file and return a best-effort function body.

    If line_number is available, reads from that line onward looking for
    the function body. If line_number is past EOF (stale after file edit),
    falls back to searching for the function name in the file.
    """
    try:
        path = Path(file_path)
        if not path.is_absolute() and project_root is not None:
            path = project_root / path
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return ""

    if line_number is None:
        return text

    lines = text.splitlines()
    start = max(0, line_number - 1)  # 1-indexed to 0-indexed

    if start < len(lines):
        return "\n".join(lines[start:])

    # Line number is past EOF — file was modified after ingest.
    # Search for the function name as a fallback.
    for i, line in enumerate(lines):
        if function_name in line:
            return "\n".join(lines[i:])

    # Function not found — return entire file so LLM has some context.
    return text


class CrawlOrchestrator:
    """Walks CrawlStore records depth-first, invoking extract_fn for each."""

    def __init__(
        self,
        store: CrawlStore,
        entry_points: list[str],
        extract_fn: ExtractFn,
        max_functions: int | None = None,
        incremental: bool = False,
        max_retries: int | None = None,
        on_progress: ProgressFn | None = None,
        concurrency: int = 10,
        project_root: Path | None = None,
    ) -> None:
        self.store = store
        self.entry_points = entry_points
        self.extract_fn = extract_fn
        self.max_functions = max_functions
        self.incremental = incremental
        self.max_retries = max_retries if max_retries is not None else MAX_RETRIES
        self._on_progress = on_progress or (lambda event, **kw: None)
        self.concurrency = concurrency
        self.project_root = project_root

        # Counters
        self._extracted = 0
        self._failed = 0
        self._skipped = 0
        self._ax_records = 0

        # DFS visited set
        self._visited: set[str] = set()

    async def extract_one(self, uuid: str) -> FnRecord | None:
        """Extract a single function by UUID, with retries on failure.

        Returns the extracted FnRecord, or None if extraction failed
        after all retries (in which case an EXTRACTION_FAILED stub is stored).
        """
        record = self.store.get_record(uuid)
        if record is None:
            return None

        skeleton = record.skeleton
        if skeleton is None:
            # Build a minimal skeleton from the record
            skeleton = Skeleton(
                function_name=record.function_name,
                file_path=record.file_path,
                line_number=record.line_number or 0,
                class_name=record.class_name,
                file_hash=record.src_hash,
            )

        body = _read_function_body(
            record.file_path,
            record.function_name,
            record.line_number,
            project_root=self.project_root,
        )

        error_feedback = None
        for attempt in range(self.max_retries):
            try:
                if error_feedback is not None:
                    result = self.extract_fn(skeleton, body, error_feedback=error_feedback)
                else:
                    result = self.extract_fn(skeleton, body)
                # Await if async
                if asyncio.iscoroutine(result):
                    result = await result
                # Ensure UUID matches
                result.uuid = uuid  # type: ignore[assignment]
                self.store.upsert_record(result)
                self._on_progress(
                    "extracted",
                    function_name=record.function_name,
                    file_path=record.file_path,
                    attempt=attempt + 1,
                    ins=len(result.ins),
                    outs=len(result.outs),
                )
                return result
            except (KeyboardInterrupt, asyncio.CancelledError):
                raise
            except Exception as e:
                if self._shutdown_requested:
                    return None
                error_feedback = str(e)
                self._on_progress(
                    "retry",
                    function_name=record.function_name,
                    file_path=record.file_path,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    error=str(e),
                )
                logger.debug(
                    "Extraction attempt %d/%d failed for %s: %s",
                    attempt + 1, self.max_retries, record.function_name, e,
                )

        # All retries exhausted — store EXTRACTION_FAILED stub
        self._on_progress(
            "failed",
            function_name=record.function_name,
            file_path=record.file_path,
            error=error_feedback,
        )
        stub = FnRecord(
            uuid=uuid,
            function_name=record.function_name,
            class_name=record.class_name,
            file_path=record.file_path,
            line_number=record.line_number,
            src_hash=record.src_hash,
            ins=[],
            do_description="EXTRACTION_FAILED",
            outs=[],
            failure_modes=[f"LLM extraction failed after {self.max_retries} attempts: {error_feedback}"],
            skeleton=skeleton,
        )
        self.store.upsert_record(stub)
        return None

    def _should_skip(self, uuid: str) -> bool:
        """Check if a record should be skipped (incremental mode)."""
        if not self.incremental:
            return False

        record = self.store.get_record(uuid)
        if record is None:
            return False

        # Skip if already fully extracted (not SKELETON_ONLY)
        if record.do_description not in ("SKELETON_ONLY", "EXTRACTION_FAILED"):
            # Also check if the file hash is still current
            try:
                path = Path(record.file_path)
                if not path.is_absolute() and self.project_root is not None:
                    path = self.project_root / path
                current_hash = hashlib.sha256(
                    path.read_text(encoding="utf-8", errors="replace").encode("utf-8")
                ).hexdigest()
                if current_hash == record.src_hash:
                    return True
            except (OSError, PermissionError):
                pass

        return False

    def _resolve_uuid_by_name(self, function_name: str, source_file: str | None = None) -> str | None:
        """Look up a UUID by function name in the store."""
        # Try exact match with file path first
        if source_file:
            records = self.store.get_records_for_file(source_file)
            for rec in records:
                if rec.function_name == function_name:
                    return rec.uuid

        # Fall back to searching all records
        all_records = self.store.get_all_records()
        for rec in all_records:
            if rec.function_name == function_name:
                return rec.uuid

        return None

    def _create_ax_record(self, source_function: str, source_file: str | None) -> None:
        """Create an AxRecord for an external boundary call."""
        file_str = source_file or "external"
        ax_uuid = make_record_uuid(file_str, source_function)

        # Check if already exists
        existing = self.store.get_record(ax_uuid)
        if existing is not None:
            return

        ax = AxRecord(
            uuid=ax_uuid,
            function_name=source_function,
            file_path=file_str,
            src_hash="external",
            source_crate=file_str.split(".")[0] if source_file else source_function.split(".")[0],
            ins=[],
            outs=[],
            boundary_contract=f"External call to {source_function}",
        )
        self.store.insert_record(ax)
        self._ax_records += 1

    def _process_extraction_result(self, result: FnRecord) -> list[str]:
        """Process extracted record — find internal calls to follow and create AX records.

        Returns list of UUIDs to visit next (DFS children).
        """
        next_uuids: list[str] = []

        for in_field in result.ins:
            if in_field.source == InSource.INTERNAL_CALL:
                # Try to resolve the target UUID
                target_uuid = self._resolve_uuid_by_name(
                    in_field.source_function or "",
                    in_field.source_file,
                )
                if target_uuid and target_uuid not in self._visited:
                    next_uuids.append(target_uuid)

            elif in_field.source == InSource.EXTERNAL:
                # Create AX record for external boundary
                if in_field.source_function:
                    self._create_ax_record(
                        in_field.source_function,
                        in_field.source_file,
                    )

        return next_uuids

    async def _dfs_extract(self, uuid: str) -> None:
        """DFS extraction from a single starting UUID."""
        if uuid in self._visited:
            return

        if getattr(self, "_shutdown_requested", False):
            return

        if self.max_functions is not None and self._extracted >= self.max_functions:
            return

        self._visited.add(uuid)

        # Check incremental skip
        if self._should_skip(uuid):
            self._skipped += 1
            record = self.store.get_record(uuid)
            if record:
                self._on_progress(
                    "skipped",
                    function_name=record.function_name,
                    file_path=record.file_path,
                )
            return

        # Extract the function
        result = await self.extract_one(uuid)
        if result is not None:
            self._extracted += 1
            # Follow internal calls (DFS)
            next_uuids = self._process_extraction_result(result)
            for next_uuid in next_uuids:
                await self._dfs_extract(next_uuid)
        else:
            self._failed += 1

    async def run(self) -> dict[str, int]:
        """Run the full DFS crawl from all entry points, then sweep remaining.

        Returns a summary dict with counters.
        """
        import signal

        self._shutdown_requested = False

        def _request_shutdown():
            if not self._shutdown_requested:
                self._shutdown_requested = True
                logger.info("Shutdown requested — finishing current extraction(s)...")

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _request_shutdown)

        try:
            # Phase 1: DFS from entry points (sequential)
            for ep_name in self.entry_points:
                if self._shutdown_requested:
                    break
                uuid = self._resolve_uuid_by_name(ep_name)
                if uuid is not None:
                    await self._dfs_extract(uuid)
                else:
                    logger.warning("Entry point not found in store: %s", ep_name)

            # Phase 2: Sweep any records the DFS didn't reach (concurrent)
            if not self._shutdown_requested and (
                self.max_functions is None or self._extracted < self.max_functions
            ):
                await self._sweep_remaining()
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

        return {
            "extracted": self._extracted,
            "failed": self._failed,
            "skipped": self._skipped,
            "ax_records": self._ax_records,
        }

    async def _sweep_remaining(self) -> None:
        """Process remaining SKELETON_ONLY/EXTRACTION_FAILED records concurrently."""
        remaining = self.store.get_pending_uuids()

        sem = asyncio.Semaphore(self.concurrency)

        async def _extract_bounded(uuid: str) -> None:
            if uuid in self._visited:
                return
            self._visited.add(uuid)
            if self._shutdown_requested:
                return
            if self.max_functions is not None and self._extracted >= self.max_functions:
                return
            if self._should_skip(uuid):
                self._skipped += 1
                return
            async with sem:
                result = await self.extract_one(uuid)
                if result is not None:
                    self._extracted += 1
                else:
                    self._failed += 1

        tasks = [_extract_bounded(u) for u in remaining]
        await asyncio.gather(*tasks, return_exceptions=True)
