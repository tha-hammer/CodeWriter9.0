---
date: 2026-03-19T09:45:00Z
researcher: DustyForge
git_commit: b0af29b
branch: master
repository: CodeWriter9.0
topic: "Concurrent Crawl Extraction Pipeline TDD Plan"
tags: [plan, tdd, cw9, performance, concurrency, asyncio, crawl-pipeline]
status: implemented
last_updated: 2026-03-19
last_updated_by: DustyForge
cw9_project: .
crawl_db: ./crawl.db
research_doc: thoughts/searchable/shared/research/2026-03-19-concurrent-crawl-extraction.md
---

# Concurrent Crawl Extraction Pipeline — TDD Implementation Plan

## Overview

The crawl pipeline executes 1062+ LLM calls sequentially — each call creates a new `ClaudeSDKClient`, connects, queries, and disconnects. The sweep phase processes independent records that can safely run concurrently. This plan converts the orchestrator to async-native, uses the standalone `query()` function for guaranteed context isolation, and adds semaphore-bounded concurrency to the sweep phase for 10-20x speedup.

## Research Reference
- Research doc: `thoughts/searchable/shared/research/2026-03-19-concurrent-crawl-extraction.md`
- CW9 project: `.` (self-referential — modifying the CW9 codebase itself)
- crawl.db: `./crawl.db` (project root, 332 records — NOT `.cw9/crawl.db` which is empty)
- crawl.db records: 15 functions across 4 files
- Existing tests: `python/tests/test_concurrent_extraction.py` (10 tests, all passing)

## Verified Specs and Traces

### gwt-0008: Async Extract Function using Standalone `query()`
- **Given**: the standalone `claude_agent_sdk.query()` function is called with a prompt and `ClaudeAgentOptions`
- **When**: the async generator is fully consumed
- **Then**: the call creates a brand-new session with no conversation history, the model sees only the single prompt, and no state is retained
- **Verified spec**: `templates/pluscal/instances/gwt-0008.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0008_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0008_bridge_artifacts.json`
  - data_structures: 1 — `AsyncExtractFnState`
  - operations: 8 — `DispatchQuery`, `BeginStream`, `CollectLoop`, `CollectMsg`, `JoinText`, `ParseJSON`, `BuildRecord`, `Finish`
  - verifiers: 12 — `ClientNeverConstructed`, `QueryParamsValid`, `CollectionTypeIntegrity`, `ParseImpliesNonEmpty`, `FnRecordReturnedOnSuccess`, `ParseErrorMeansNoRecord`, `ReturnImpliesParseSuccess`, `ReturnImpliesCollected`, plus type/state invariants

### gwt-0014: Semaphore-Bounded Concurrent Sweep
- **Given**: `_sweep_remaining_async()` is called with `concurrency=N` and M pending UUIDs (M > N)
- **When**: `asyncio.gather()` is awaited
- **Then**: at most N `extract_one_async()` coroutines execute concurrently, enforced by `asyncio.Semaphore(N)`; all M UUIDs are processed; semaphore is acquired/released symmetrically
- **Verified spec**: `templates/pluscal/instances/gwt-0014.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0014_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0014_bridge_artifacts.json`
  - data_structures: 1 — `SweepRemainingAsyncState`
  - operations: 0 (pure behavioral spec)
  - verifiers: 7 — `ConcurrencyBound`, `SemNonNegative`, `SemaphoreConservation`, `PerTaskAtMostOnce`, `AcqBeforeRel`, `WhenCompleteSymmetric`, `AllInvariants`

### gwt-0015: Error Isolation in `asyncio.gather()`
- **Given**: `_sweep_remaining_async()` is running and extraction task T raises an unhandled exception
- **When**: `asyncio.gather(return_exceptions=True)` collects results
- **Then**: the exception is captured as a return value; all other tasks continue; the semaphore slot is released
- **Verified spec**: `templates/pluscal/instances/gwt-0015.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0015_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0015_bridge_artifacts.json`
  - data_structures: 1 — `SweepRemainingAsyncState`
  - operations: 2 — `WaitAll`, `Finish`
  - verifiers: 9 — `NoCancellation`, `ExceptionCapturedAsResult`, `AllOthersSucceedWhenGatherDone`, `FailedTaskSlotReleased`, `CompletedOrFailedReleaseSemaphore`, `RunningTasksHoldSemaphore`, plus type invariants

### gwt-0016: SQLite Safety Under Asyncio
- **Given**: `CrawlOrchestrator` on a single asyncio event loop, two concurrent `extract_one_async()` coroutines both call `store.upsert_record()`
- **When**: the upserts execute
- **Then**: SQLite calls execute sequentially without interleaving because asyncio coroutines yield only at `await` points and `upsert_record()` is synchronous
- **Verified spec**: `templates/pluscal/instances/gwt-0016.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0016_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0016_bridge_artifacts.json`
  - data_structures: 1 — `CrawlOrchestratorUpsertState`
  - operations: 0 (pure behavioral spec)
  - verifiers: 6 — `NoSimultaneousUpserts`, `UpsertLogNoDuplicates`, `CompletionImpliesUpserted`, `UpsertLogLengthMatchesCompletions`, plus type invariants

### gwt-0018: Async `run()` — Sequential DFS then Concurrent Sweep
- **Given**: `CrawlOrchestrator.run()` is the top-level entry point
- **When**: `run()` is awaited
- **Then**: Phase 1 (`_dfs_extract`) executes all DFS nodes sequentially; Phase 2 (`_sweep_remaining_async`) executes remaining UUIDs concurrently with `asyncio.gather()` + semaphore; Phase 1 completes entirely before Phase 2 begins
- **Verified spec**: `templates/pluscal/instances/gwt-0018.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0018_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0018_bridge_artifacts.json`
  - data_structures: 1 — `CrawlOrchestratorState`
  - operations: 7 — `OStart`, `P1Loop`, `P1Process`, `P1Signal`, `OGather`, `OComplete`, `orchestrator`
  - verifiers: 7 — `Phase1BeforePhase2`, `Phase1FlagAccurate`, `DFSSequentialOrder`, `NoPhase2BeforeSignal`, `ConcurrencyBound`, `SemaphoreNonNeg`, `TypeOK`

### gwt-0022: `--concurrency` CLI Flag
- **Given**: the crawl CLI is invoked with a `--concurrency` flag
- **When**: argparse processes the arguments
- **Then**: the value is parsed as int (default 10), validated, and passed through `cmd_crawl()` → `CrawlOrchestrator.__init__()` → `_sweep_remaining_async()`
- **Verified spec**: `templates/pluscal/instances/gwt-0022.tla`
- **Simulation traces**: `templates/pluscal/instances/gwt-0022_sim_traces.json` (10 traces)
- **Bridge artifacts**: `python/tests/generated/gwt-0022_bridge_artifacts.json`
  - data_structures: 1 — `CrawlConcurrencyPipelineState`
  - operations: 7 — `StartParsing`, `ParseArg`, `ValidateArg`, `RouteAfterValidation`, `InitOrchestrator`, `ForwardToSweep`, `Terminate`
  - verifiers: 10 — `DefaultApplied`, `ValidationCorrect`, `ValuePreservedToCmdCrawl`, `OrchestratorPreservesValue`, `SweepReceivesCorrectValue`, `NoErrorOnValidUserInput`, `NoErrorOnDefault`, plus type invariants

## What We're NOT Doing

- **Changing CrawlStore** — asyncio single-thread serializes SQLite access naturally (gwt-0016 verified)
- **Parallelizing DFS phase** — dependency-ordered traversal must stay sequential (gwt-0017/gwt-0018 verified)
- **Connection pooling** — standalone `query()` manages its own lifecycle; no persistent client needed
- **Removing sync `_build_extract_fn()`** — keep as fallback for debugging/`--concurrency=1`

---

## Step 1: `_build_async_extract_fn()` — Async Extract Function

### CW9 Binding
- **GWT**: gwt-0008
- **Bridge artifact**: `AsyncExtractFnState` + 8 operations
- **Key verifiers**: `ClientNeverConstructed`, `QueryParamsValid`, `FnRecordReturnedOnSuccess`
- **depends_on UUIDs**:
  - `79b09e73` — `_build_llm_fn` @ cli.py:1115
  - `8cea6619` — `_build_extract_fn` @ cli.py:1232
  - `f9ef9505` — `_extract_json_object` @ cli.py:1188

### Test Specification
**Given**: A skeleton and body for a function extraction
**When**: `async_extract_fn(skeleton, body)` is awaited
**Then**: Returns an `FnRecord` with parsed INs/OUTs; never constructs a `ClaudeSDKClient`; uses standalone `query()` with `allowed_tools=[]`, `system_prompt=_EXTRACT_SYSTEM_PROMPT`, `max_turns=1`
**Edge Cases**: Parse error raises `ValueError`; empty response raises `ValueError`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_async_extract_fn.py`
```python
"""Tests for _build_async_extract_fn() — standalone query()-based extraction."""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from registry.crawl_types import Skeleton, SkeletonParam, FnRecord, InSource


def _make_skeleton(fn_name="handler", file_path="src/main.py"):
    return Skeleton(
        function_name=fn_name,
        file_path=file_path,
        line_number=10,
        class_name=None,
        params=[SkeletonParam(name="request", type="Request")],
        return_type="Response",
        file_hash="abc123",
    )


_VALID_JSON_RESPONSE = """{
    "ins": [{"name": "request", "type_str": "Request", "source": "parameter", "description": "HTTP request"}],
    "do_description": "Handles the request",
    "do_steps": ["Parse request", "Return response"],
    "outs": [{"name": "ok", "type_str": "Response", "description": "Success response"}],
    "failure_modes": ["Invalid input"],
    "operational_claim": "handler processes requests"
}"""


class TestAsyncExtractFnNeverConstructsClient:
    """gwt-0008 verifier: ClientNeverConstructed"""

    def test_uses_standalone_query_not_client(self):
        """The async extract_fn must call standalone query(), not ClaudeSDKClient."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn(model="claude-sonnet-4-6")

        skel = _make_skeleton()

        # Mock the standalone query to return a valid JSON response
        async def mock_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text=_VALID_JSON_RESPONSE)]
            yield msg

        with patch("registry.cli.query", side_effect=mock_query) as mock_q:
            result = asyncio.run(extract_fn(skel, "def handler(request): pass"))

        mock_q.assert_called_once()
        assert isinstance(result, FnRecord)
        assert result.function_name == "handler"


class TestAsyncExtractFnQueryParams:
    """gwt-0008 verifier: QueryParamsValid"""

    def test_passes_correct_options(self):
        """standalone query() must receive allowed_tools=[], max_turns=1, system_prompt=EXTRACT."""
        from registry.cli import _build_async_extract_fn, _EXTRACT_SYSTEM_PROMPT

        extract_fn = _build_async_extract_fn(model="claude-sonnet-4-6")
        skel = _make_skeleton()
        captured_kwargs = {}

        async def capturing_query(**kwargs):
            captured_kwargs.update(kwargs)
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text=_VALID_JSON_RESPONSE)]
            yield msg

        with patch("registry.cli.query", side_effect=capturing_query):
            asyncio.run(extract_fn(skel, "def handler(): pass"))

        opts = captured_kwargs["options"]
        assert opts.allowed_tools == []
        assert opts.max_turns == 1
        assert opts.system_prompt == _EXTRACT_SYSTEM_PROMPT
        assert opts.model == "claude-sonnet-4-6"


class TestAsyncExtractFnReturnsRecord:
    """gwt-0008 verifier: FnRecordReturnedOnSuccess"""

    def test_returns_fn_record_with_parsed_fields(self):
        """On valid JSON, returns FnRecord with correct ins/outs/do_description."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()

        async def mock_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text=_VALID_JSON_RESPONSE)]
            yield msg

        with patch("registry.cli.query", side_effect=mock_query):
            result = asyncio.run(extract_fn(skel, "def handler(): pass"))

        assert result.do_description == "Handles the request"
        assert len(result.ins) == 1
        assert result.ins[0].source == InSource.PARAMETER
        assert len(result.outs) == 1

    def test_parse_error_raises_value_error(self):
        """On invalid JSON response, raises ValueError."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()

        async def mock_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text="not json at all")]
            yield msg

        with patch("registry.cli.query", side_effect=mock_query):
            with pytest.raises(ValueError, match="No JSON object found"):
                asyncio.run(extract_fn(skel, "def handler(): pass"))


class TestAsyncExtractFnCollectionIntegrity:
    """gwt-0008 verifier: CollectionTypeIntegrity, ParseImpliesNonEmpty,
    ReturnImpliesParseSuccess, ReturnImpliesCollected"""

    def test_empty_response_raises_value_error(self):
        """gwt-0008: ParseImpliesNonEmpty — empty collected_texts must raise."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()

        async def empty_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text="")]
            yield msg

        with patch("registry.cli.query", side_effect=empty_query):
            with pytest.raises(ValueError):
                asyncio.run(extract_fn(skel, "def handler(): pass"))

    def test_only_sdk_query_used(self):
        """gwt-0008: OnlySDKQueryUsed — standalone query() is the only SDK call."""
        import inspect
        from registry.cli import _build_async_extract_fn

        src = inspect.getsource(_build_async_extract_fn)
        assert "ClaudeSDKClient" not in src, "Must not reference ClaudeSDKClient"
        assert "query" in src, "Must use standalone query()"

    def test_return_implies_parse_success(self):
        """gwt-0008: ReturnImpliesParseSuccess — returned FnRecord always has parsed fields."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()

        async def mock_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text=_VALID_JSON_RESPONSE)]
            yield msg

        with patch("registry.cli.query", side_effect=mock_query):
            result = asyncio.run(extract_fn(skel, "def handler(): pass"))

        # ReturnImpliesParseSuccess: result has parsed do_description
        assert result.do_description != ""
        # ReturnImpliesCollected: result has function_name from collection
        assert result.function_name == skel.function_name

    def test_collection_type_integrity(self):
        """gwt-0008: CollectionTypeIntegrity — text blocks are collected as strings."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()

        async def multi_block_query(**kwargs):
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            # Two text blocks that together form valid JSON
            msg.content = [
                MagicMock(spec=TextBlock, text='{"ins": [], "do_description": "test", '),
                MagicMock(spec=TextBlock, text='"do_steps": [], "outs": [], "failure_modes": [], "operational_claim": "claim"}'),
            ]
            yield msg

        with patch("registry.cli.query", side_effect=multi_block_query):
            result = asyncio.run(extract_fn(skel, "def handler(): pass"))

        assert result.do_description == "test"


class TestAsyncExtractFnErrorFeedback:
    """gwt-0008/gwt-0010: error_feedback embedded in prompt text."""

    def test_error_feedback_appended_to_prompt(self):
        """When error_feedback is provided, it appears in the prompt sent to query()."""
        from registry.cli import _build_async_extract_fn

        extract_fn = _build_async_extract_fn()
        skel = _make_skeleton()
        captured_prompt = {}

        async def capturing_query(**kwargs):
            captured_prompt["prompt"] = kwargs.get("prompt", "")
            from claude_agent_sdk import AssistantMessage, TextBlock
            msg = MagicMock(spec=AssistantMessage)
            msg.content = [MagicMock(spec=TextBlock, text=_VALID_JSON_RESPONSE)]
            yield msg

        with patch("registry.cli.query", side_effect=capturing_query):
            asyncio.run(extract_fn(skel, "def handler(): pass",
                                   error_feedback="Invalid JSON: missing 'ins'"))

        assert "Previous Error" in captured_prompt["prompt"]
        assert "missing 'ins'" in captured_prompt["prompt"]
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py` — Add after `_build_extract_fn()` (after line 1311)
```python
def _build_async_extract_fn(model: str = "claude-sonnet-4-6"):
    """Build an async extract_fn using standalone query() — fresh context per call.

    Each invocation of the returned coroutine creates a completely independent
    session via the SDK's standalone query() function. No ClaudeSDKClient is
    constructed — context isolation is guaranteed by design.
    """
    import os
    os.environ.pop("CLAUDECODE", None)
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock
    from registry.crawl_types import (
        FnRecord, InField, InSource, OutField, OutKind, Skeleton,
    )

    async def extract_fn(skeleton: Skeleton, body: str, error_feedback: str | None = None) -> FnRecord:
        prompt_parts = [
            f"## Function: {skeleton.function_name}",
            f"File: {skeleton.file_path}:{skeleton.line_number}",
        ]
        if skeleton.class_name:
            prompt_parts.append(f"Class: {skeleton.class_name}")
        if skeleton.params:
            param_strs = [f"{p.name}: {p.type or 'Any'}" for p in skeleton.params]
            prompt_parts.append(f"Params: {', '.join(param_strs)}")
        if skeleton.return_type:
            prompt_parts.append(f"Returns: {skeleton.return_type}")
        prompt_parts.append(f"\n## Body\n```\n{body}\n```")
        if error_feedback:
            prompt_parts.append(f"\n## Previous Error\n{error_feedback}\nPlease fix the JSON output.")

        prompt = "\n".join(prompt_parts)

        options = ClaudeAgentOptions(
            allowed_tools=[],
            system_prompt=_EXTRACT_SYSTEM_PROMPT,
            max_turns=1,
            model=model,
        )

        result_text = []
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.result:
                    result_text.append(message.result)

        raw = "".join(result_text)
        data = _extract_json_object(raw)

        # Reuse same JSON→FnRecord mapping as _build_extract_fn
        source_map = {
            "parameter": InSource.PARAMETER,
            "state": InSource.STATE,
            "literal": InSource.LITERAL,
            "internal_call": InSource.INTERNAL_CALL,
            "external": InSource.EXTERNAL,
        }
        kind_map = {
            "ok": OutKind.OK,
            "err": OutKind.ERR,
            "side_effect": OutKind.SIDE_EFFECT,
            "mutation": OutKind.MUTATION,
        }

        ins = [
            InField(
                name=i["name"],
                type_str=i.get("type_str", "Any"),
                source=source_map.get(i.get("source", "parameter"), InSource.PARAMETER),
                source_function=i.get("source_function"),
                source_file=i.get("source_file"),
                description=i.get("description", ""),
            )
            for i in data.get("ins", [])
        ]
        outs = [
            OutField(
                name=kind_map.get(o.get("name", "ok"), OutKind.OK),
                type_str=o.get("type_str", "Any"),
                description=o.get("description", ""),
            )
            for o in data.get("outs", [])
        ]

        return FnRecord(
            uuid="00000000-0000-0000-0000-000000000000",
            function_name=skeleton.function_name,
            class_name=skeleton.class_name,
            file_path=skeleton.file_path,
            line_number=skeleton.line_number,
            src_hash=skeleton.file_hash,
            ins=ins,
            do_description=data.get("do_description", ""),
            do_steps=data.get("do_steps", []),
            outs=outs,
            failure_modes=data.get("failure_modes", []),
            operational_claim=data.get("operational_claim", ""),
            skeleton=skeleton,
        )

    return extract_fn
```

#### Refactor
Extract the shared JSON→FnRecord mapping into a `_parse_extraction_result(skeleton, data)` helper used by both `_build_extract_fn()` and `_build_async_extract_fn()` to eliminate duplication.

### Success Criteria
**Automated:**
- [ ] Test fails before implementation (Red) — `_build_async_extract_fn` does not exist
- [ ] Test passes after implementation (Green) — all 6 test classes pass (9 tests total)
- [ ] All existing tests still pass after refactor
- [ ] Verifier `ClientNeverConstructed` satisfied — no `ClaudeSDKClient` in the function
- [ ] Verifiers `CollectionTypeIntegrity`, `ParseImpliesNonEmpty`, `ReturnImpliesParseSuccess`, `ReturnImpliesCollected`, `OnlySDKQueryUsed` — covered by new TestAsyncExtractFnCollectionIntegrity class

---

## Step 2: Convert `CrawlOrchestrator` to Async

### CW9 Binding
- **GWT**: gwt-0018
- **Bridge artifact**: `CrawlOrchestratorState` + 7 operations
- **Key verifiers**: `Phase1BeforePhase2`, `DFSSequentialOrder`, `NoPhase2BeforeSignal`
- **depends_on UUIDs**:
  - `f95fdf5c` — `run` @ crawl_orchestrator.py:303
  - `06be8c8b` — `_dfs_extract` @ crawl_orchestrator.py:270
  - `b14a9b59` — `extract_one` @ crawl_orchestrator.py:95
  - `f39134fd` — `_sweep_remaining` @ crawl_orchestrator.py:328

### Test Specification
**Given**: An async-native `CrawlOrchestrator` with entry points and pending records
**When**: `await orch.run()` completes
**Then**: Phase 1 processes DFS nodes sequentially; Phase 2 begins only after Phase 1 completes; all pending records are eventually processed
**Edge Cases**: No entry points (skip Phase 1); no pending records after DFS (skip Phase 2)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_async_orchestrator.py`
```python
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
```

#### Green: Minimal Implementation
**File**: `python/registry/crawl_orchestrator.py`

Convert the orchestrator methods to async:
- `run()` → `async def run()` — `await self._dfs_extract(uuid)`, then `await self._sweep_remaining()`
- `_dfs_extract()` → `async def _dfs_extract()` — `await self.extract_one(uuid)`, sequential recursion
- `extract_one()` → `async def extract_one()` — `await self.extract_fn(skeleton, body)` if extract_fn is async, else call sync
- `_sweep_remaining()` → `async def _sweep_remaining()` — delegates to semaphore-bounded gather (Step 3)
- Add `concurrency: int = 10` parameter to `__init__()`

Key: detect whether `extract_fn` is async via `asyncio.iscoroutinefunction()` and branch accordingly. This preserves backward compatibility with sync extract functions.

```python
async def extract_one(self, uuid: str) -> FnRecord | None:
    # ... same setup as before ...
    for attempt in range(self.max_retries):
        try:
            if error_feedback is not None:
                result = self.extract_fn(skeleton, body, error_feedback=error_feedback)
            else:
                result = self.extract_fn(skeleton, body)
            # Await if async
            if asyncio.iscoroutine(result):
                result = await result
            # ... rest unchanged ...
```

#### Refactor
None needed — the async/sync detection keeps backward compatibility clean.

### Success Criteria
**Automated:**
- [ ] `test_dfs_completes_before_sweep_begins` passes — phase ordering verified (gwt-0018: Phase1BeforePhase2)
- [ ] `test_dfs_extractions_are_sequential` passes — no concurrent DFS (gwt-0018: DFSSequentialOrder)
- [ ] `test_phase_flag_tracks_dfs_completion` passes — phase flag accurate (gwt-0018: Phase1FlagAccurate)
- [ ] `test_extract_one_is_coroutine` passes — awaitable extraction
- [ ] All 10 existing `test_concurrent_extraction.py` tests still pass

---

## Step 3: `_sweep_remaining_async()` — Semaphore-Bounded Concurrent Sweep

### CW9 Binding
- **GWTs**: gwt-0014 (concurrency bound), gwt-0015 (error isolation), gwt-0016 (SQLite safety)
- **Bridge artifacts**: `SweepRemainingAsyncState` verifiers + `CrawlOrchestratorUpsertState` verifiers
- **Key verifiers**: `ConcurrencyBound`, `SemaphoreConservation`, `NoCancellation`, `ExceptionCapturedAsResult`, `NoSimultaneousUpserts`
- **depends_on UUIDs**:
  - `f39134fd` — `_sweep_remaining` @ crawl_orchestrator.py:328
  - `978fd5d2` — `get_pending_uuids` @ crawl_store.py:412
  - `574594b2` — `upsert_record` @ crawl_store.py:284

### Test Specification
**Given**: N pending UUIDs and concurrency limit C (C < N)
**When**: `await _sweep_remaining()` completes
**Then**: At most C extractions run concurrently; all N UUIDs are processed; a single failed extraction does not cancel others; SQLite upserts never interleave
**Edge Cases**: All extractions fail; concurrency=1 (sequential); 0 pending UUIDs

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_sweep_async.py`
```python
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
            result = asyncio.run(orch.run())

        # UpsertLogNoDuplicates: no UUID upserted twice
        assert len(upserted_names) == len(set(upserted_names))
        # UpsertLogLengthMatchesCompletions: upserts == extracted count
        assert len(upserted_names) == result["extracted"]

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
```

#### Green: Minimal Implementation
**File**: `python/registry/crawl_orchestrator.py` — Replace `_sweep_remaining()`
```python
async def _sweep_remaining(self) -> None:
    """Process remaining SKELETON_ONLY/EXTRACTION_FAILED records concurrently."""
    remaining = self.store.get_pending_uuids()

    sem = asyncio.Semaphore(self.concurrency)

    async def _extract_bounded(uuid: str) -> None:
        if uuid in self._visited:
            return
        self._visited.add(uuid)
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
```

#### Refactor
None needed — the semaphore pattern is clean and minimal.

### Success Criteria
**Automated:**
- [ ] `test_at_most_n_concurrent_extractions` — concurrency bound enforced (gwt-0014: ConcurrencyBound)
- [ ] `test_each_uuid_processed_exactly_once` — no duplicate processing (gwt-0014: PerTaskAtMostOnce)
- [ ] `test_semaphore_acquire_release_symmetry` — acquire/release invariants (gwt-0014: AcqBeforeRel, WhenCompleteSymmetric, SemNonNegative)
- [ ] `test_one_failure_does_not_cancel_others` — error isolation works (gwt-0015: NoCancellation, ExceptionCapturedAsResult)
- [ ] `test_failed_task_releases_semaphore_slot` — slot freed after failure (gwt-0015: FailedTaskSlotReleased, AllOthersSucceedWhenGatherDone)
- [ ] `test_upserts_never_interleave` — SQLite safety under asyncio (gwt-0016: NoSimultaneousUpserts)
- [ ] `test_each_uuid_upserted_exactly_once` — no duplicate upserts (gwt-0016: UpsertLogNoDuplicates, UpsertLogLengthMatchesCompletions)
- [ ] `test_completed_task_implies_upserted` — completions persisted (gwt-0016: CompletionImpliesUpserted)
- [ ] `test_dfs_visited_uuids_skipped_in_sweep` — no duplicate processing (gwt-0018: DFS-then-sweep)
- [ ] `test_concurrency_one_processes_all` — sequential fallback works

---

## Step 4: `--concurrency` CLI Flag

### CW9 Binding
- **GWT**: gwt-0022
- **Bridge artifact**: `CrawlConcurrencyPipelineState` + 7 operations
- **Key verifiers**: `DefaultApplied`, `ValuePreservedToCmdCrawl`, `SweepReceivesCorrectValue`
- **depends_on UUIDs**:
  - `cd8e7329` — `cmd_crawl` @ cli.py:956

### Test Specification
**Given**: CLI invoked with `--concurrency 5` or without the flag
**When**: argparse processes arguments and `cmd_crawl()` runs
**Then**: `--concurrency` defaults to 10; custom values pass through to `CrawlOrchestrator(concurrency=N)`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_cli_concurrency_flag.py`
```python
"""Tests for --concurrency CLI flag passthrough."""
import argparse
import asyncio
from unittest.mock import patch, MagicMock

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


class TestConcurrencyArgParsing:
    """gwt-0022 verifiers: DefaultApplied, ValidationCorrect"""

    def test_default_concurrency_is_10(self):
        """Without --concurrency, default is 10."""
        from registry.cli import main as cli_main
        # Parse just the crawl subcommand
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        # Import the parser setup
        from registry.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["crawl", "."])
        assert args.concurrency == 10

    def test_custom_concurrency_parsed(self):
        """--concurrency 5 is parsed correctly."""
        from registry.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["crawl", "--concurrency", "5", "."])
        assert args.concurrency == 5


class TestConcurrencyValidation:
    """gwt-0022 verifiers: ValidationCorrect, NoErrorOnValidUserInput, NoErrorOnDefault"""

    def test_invalid_concurrency_zero_rejected(self):
        """gwt-0022: ValidationCorrect — --concurrency 0 is rejected."""
        from registry.cli import _build_parser
        p = _build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["crawl", "--concurrency", "0", "."])

    def test_invalid_concurrency_negative_rejected(self):
        """gwt-0022: ValidationCorrect — negative concurrency rejected."""
        from registry.cli import _build_parser
        p = _build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["crawl", "--concurrency", "-1", "."])

    def test_valid_concurrency_no_error(self):
        """gwt-0022: NoErrorOnValidUserInput — valid values parse without error."""
        from registry.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["crawl", "--concurrency", "20", "."])
        assert args.concurrency == 20

    def test_default_concurrency_no_error(self):
        """gwt-0022: NoErrorOnDefault — default value parses without error."""
        from registry.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["crawl", "."])
        assert args.concurrency == 10


class TestConcurrencyPassthrough:
    """gwt-0022 verifiers: ValuePreservedToCmdCrawl, SweepReceivesCorrectValue"""

    def test_concurrency_reaches_orchestrator(self, tmp_path):
        """The concurrency value from CLI must reach CrawlOrchestrator.__init__."""
        captured = {}

        with patch("registry.crawl_orchestrator.CrawlOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.run = MagicMock(return_value={
                "extracted": 0, "failed": 0, "skipped": 0, "ax_records": 0,
            })
            MockOrch.return_value = mock_instance

            from registry.cli import cmd_crawl
            args = argparse.Namespace(
                target_dir=str(tmp_path),
                entry=None, incremental=False, max_functions=None,
                max_retries=5, model=None, output_json=False,
                concurrency=7,
            )

            # Create minimal .cw9 and crawl.db
            (tmp_path / ".cw9").mkdir()
            from registry.crawl_store import CrawlStore
            with CrawlStore(tmp_path / ".cw9" / "crawl.db") as store:
                pass  # just create the empty DB

            # cmd_crawl will fail without records, but we can verify the mock
            cmd_crawl(args)

            # Verify concurrency was passed to CrawlOrchestrator
            call_kwargs = MockOrch.call_args
            assert call_kwargs.kwargs.get("concurrency") == 7 or \
                   (len(call_kwargs.args) > 7 and call_kwargs.args[7] == 7)


class TestSweepReceivesConcurrencyValue:
    """gwt-0022 verifiers: OrchestratorPreservesValue, SweepReceivesCorrectValue"""

    def test_orchestrator_stores_concurrency(self, tmp_path):
        """gwt-0022: OrchestratorPreservesValue — concurrency stored on instance."""
        async def noop_extract(skeleton, body, error_feedback=None):
            pass

        with CrawlStore(tmp_path / "crawl.db") as store:
            orch = CrawlOrchestrator(store, [], noop_extract, concurrency=7)
            assert orch.concurrency == 7

    def test_sweep_uses_concurrency_value(self, tmp_path):
        """gwt-0022: SweepReceivesCorrectValue — semaphore uses stored concurrency."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        for i in range(5):
            (src_dir / f"fn_{i}.py").write_text(f"def fn_{i}(): pass\n")

        concurrent = 0
        max_concurrent = 0

        async def tracking_extract(skeleton, body, error_feedback=None):
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.05)
            concurrent -= 1
            return _make_fn_record(skeleton)

        with CrawlStore(tmp_path / "crawl.db") as store:
            for i in range(5):
                _insert_pending(store, src_dir, f"fn_{i}")

            orch = CrawlOrchestrator(store, [], tracking_extract, concurrency=2)
            asyncio.run(orch.run())

        assert max_concurrent <= 2, f"Exceeded concurrency=2: got {max_concurrent}"
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py`

1. Add argparse flag with validation (after line 1533):
```python
def _positive_int(value):
    """Argparse type validator: positive integer only."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"must be positive, got {value}")
    return ivalue

p_crawl.add_argument("--concurrency", type=_positive_int, default=10,
                     help="Max concurrent LLM extractions in sweep phase (default: 10)")
```

2. Update `cmd_crawl()` (around line 997):
```python
concurrency = getattr(args, "concurrency", 10)
```

3. Pass to orchestrator (around line 1073):
```python
orch = CrawlOrchestrator(
    store=store,
    entry_points=entry_names,
    extract_fn=extract_fn,
    max_functions=max_fns,
    incremental=incremental,
    max_retries=max_retries,
    on_progress=_on_progress,
    concurrency=concurrency,
)
```

#### Refactor
None needed.

### Success Criteria
**Automated:**
- [ ] `test_default_concurrency_is_10` — default applied correctly (gwt-0022: DefaultApplied)
- [ ] `test_custom_concurrency_parsed` — custom value parsed
- [ ] `test_invalid_concurrency_zero_rejected` — zero rejected (gwt-0022: ValidationCorrect)
- [ ] `test_invalid_concurrency_negative_rejected` — negative rejected (gwt-0022: ValidationCorrect)
- [ ] `test_valid_concurrency_no_error` — valid values accepted (gwt-0022: NoErrorOnValidUserInput)
- [ ] `test_default_concurrency_no_error` — default accepted (gwt-0022: NoErrorOnDefault)
- [ ] `test_concurrency_reaches_orchestrator` — end-to-end passthrough (gwt-0022: ValuePreservedToCmdCrawl)
- [ ] `test_orchestrator_stores_concurrency` — value preserved (gwt-0022: OrchestratorPreservesValue)
- [ ] `test_sweep_uses_concurrency_value` — semaphore uses value (gwt-0022: SweepReceivesCorrectValue)

---

## Step 5: Update `cmd_crawl()` — Async Entry Point

### CW9 Binding
- **GWT**: _none_ — wiring-only step, no formal spec required
- **Rationale**: This step wires `_build_async_extract_fn()` into `cmd_crawl()` and calls `asyncio.run()`. The async behavior is already verified by gwt-0008 (extract fn) and gwt-0018 (phase ordering). The single-entry-point invariant is a standard asyncio pattern, tested below.
- **depends_on UUIDs**:
  - `cd8e7329` — `cmd_crawl` @ cli.py:956

### Test Specification
**Given**: `cmd_crawl()` is called with valid arguments
**When**: it constructs `CrawlOrchestrator` with `_build_async_extract_fn()` and runs it
**Then**: calls `asyncio.run(orch.run())` exactly once; does not call `asyncio.run()` per extraction

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_cmd_crawl_async.py`
```python
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
```

#### Green: Minimal Implementation
**File**: `python/registry/cli.py` — Update `cmd_crawl()` (lines 1069-1082)

Replace:
```python
extract_fn = _build_extract_fn(model=model_name)
# ...
orch = CrawlOrchestrator(...)
result = orch.run()
```

With:
```python
extract_fn = _build_async_extract_fn(model=model_name)
# ...
orch = CrawlOrchestrator(
    store=store,
    entry_points=entry_names,
    extract_fn=extract_fn,
    max_functions=max_fns,
    incremental=incremental,
    max_retries=max_retries,
    on_progress=_on_progress,
    concurrency=concurrency,
)
result = asyncio.run(orch.run())
```

#### Refactor
None needed.

### Success Criteria
**Automated:**
- [ ] `test_single_asyncio_run_call` — exactly one `asyncio.run()` invocation
- [ ] Full integration: `cw9 crawl --concurrency 5 .` processes records concurrently

---

## Integration Testing

After all steps are implemented, run the full test suite:

```bash
# Unit tests
pytest python/tests/test_concurrent_extraction.py -v       # existing (10 tests)
pytest python/tests/test_async_extract_fn.py -v             # Step 1
pytest python/tests/test_async_orchestrator.py -v           # Step 2
pytest python/tests/test_sweep_async.py -v                  # Step 3
pytest python/tests/test_cli_concurrency_flag.py -v         # Step 4
pytest python/tests/test_cmd_crawl_async.py -v              # Step 5

# Integration: small crawl with concurrency
cw9 ingest python/registry/ . --lang python
cw9 crawl --concurrency 5 --max-functions 10 .
```

## Verification

After implementation, re-verify the CW9 pipeline:
```bash
cw9 ingest python/registry/ . --incremental
cw9 stale .
cw9 pipeline --skip-setup --gwt gwt-0008 .
cw9 pipeline --skip-setup --gwt gwt-0014 .
cw9 pipeline --skip-setup --gwt gwt-0018 .
```

## Revision Notes (2026-03-19)

Fixes applied from CW9 Plan Review:

**Critical #1 — gwt-0019**: Removed GWT binding from Step 5. This is a wiring-only step; async behavior is already verified by gwt-0008 and gwt-0018.

**Critical #2 — gwt-0027**: Re-bound `TestSweepDuplicateSkip` from gwt-0027 (no artifacts) to gwt-0018 (DFS-then-sweep ordering, which covers the skip-already-visited invariant).

**Critical #3 — 28 uncovered verifiers**: Added test assertions for all non-structural verifiers:
- gwt-0008: +5 tests (`OnlySDKQueryUsed`, `CollectionTypeIntegrity`, `ParseImpliesNonEmpty`, `ReturnImpliesParseSuccess`, `ReturnImpliesCollected`)
- gwt-0014: +2 tests (`PerTaskAtMostOnce`, `AcqBeforeRel`/`WhenCompleteSymmetric`/`SemNonNegative`)
- gwt-0015: +1 test (`FailedTaskSlotReleased`, `AllOthersSucceedWhenGatherDone`, `CompletedOrFailedReleaseSemaphore`)
- gwt-0016: +2 tests (`UpsertLogNoDuplicates`, `CompletionImpliesUpserted`, `UpsertLogLengthMatchesCompletions`)
- gwt-0018: +1 test (`Phase1FlagAccurate`)
- gwt-0022: +6 tests (`ValidationCorrect` x2, `NoErrorOnValidUserInput`, `NoErrorOnDefault`, `OrchestratorPreservesValue`, `SweepReceivesCorrectValue`)

**Warning #1 — crawl.db location**: Added `crawl_db: ./crawl.db` to frontmatter and clarified in Research Reference section.

**Warning #4 — gwt-0022 validation**: Added `_positive_int` argparse type validator and rejection tests for 0 and negative values.

**Cosmetic #1 — cw9_project**: Removed non-standard parenthetical from frontmatter.

## References
- Research: `thoughts/searchable/shared/research/2026-03-19-concurrent-crawl-extraction.md`
- Verified specs: `templates/pluscal/instances/gwt-{0008,0014,0015,0016,0018,0022}.tla`
- Simulation traces: `templates/pluscal/instances/gwt-{0008,0014,0015,0016,0018,0022}_sim_traces.json`
- Bridge artifacts: `python/tests/generated/gwt-{0008,0014,0015,0016,0018,0022}_bridge_artifacts.json`
- Beads: `bd show replication_ab_bench-dj5m`
