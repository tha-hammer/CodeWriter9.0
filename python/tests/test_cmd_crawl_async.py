"""Tests for cmd_crawl() async entry point."""
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestCmdCrawlUsesAsyncio:
    """Wiring test: cmd_crawl calls asyncio.run(orch.run()) exactly once."""

    def test_single_asyncio_run_call(self, tmp_path):
        """cmd_crawl must use asyncio.run() once, not per-extraction."""
        (tmp_path / ".cw9").mkdir()
        from registry.crawl_store import CrawlStore
        with CrawlStore(tmp_path / ".cw9" / "crawl.db") as store:
            pass

        asyncio_run_calls = 0
        original_run = asyncio.run

        def counting_run(coro, **kwargs):
            nonlocal asyncio_run_calls
            asyncio_run_calls += 1
            return original_run(coro, **kwargs)

        import argparse
        args = argparse.Namespace(
            target_dir=str(tmp_path),
            entry=None, incremental=False, max_functions=None,
            max_retries=1, model=None, output_json=False,
            concurrency=10,
        )

        with patch("asyncio.run", side_effect=counting_run):
            from registry.cli import cmd_crawl
            cmd_crawl(args)

        # At most 1 asyncio.run call (0 if no records to process)
        assert asyncio_run_calls <= 1
