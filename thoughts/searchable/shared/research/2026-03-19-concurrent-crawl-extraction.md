---
date: 2026-03-19T00:00:00Z
researcher: DustyForge
git_commit: b0af29b
branch: master
repository: CodeWriter9.0
topic: "Concurrent crawl extraction pipeline — eliminating sequential LLM bottleneck"
tags: [research, cw9, performance, concurrency, crawl-pipeline]
status: complete
last_updated: 2026-03-19
last_updated_by: DustyForge
cw9_project: N/A (this IS the cw9 codebase)
---

# Research: Concurrent Crawl Extraction Pipeline

## Research Question

The crawl pipeline executes 1062+ LLM calls sequentially — each call creates a new `ClaudeSDKClient`, connects, queries, and disconnects. How do we add concurrency to the sweep phase and persistent client reuse to achieve 10-20x speedup?

## Codebase Overview

The crawl pipeline spans three files:

| File | Role |
|---|---|
| `python/registry/crawl_orchestrator.py` (343 lines) | DFS traversal + sweep logic |
| `python/registry/cli.py` (lines 956-1112, 1115-1270) | CLI entry point, LLM client factory, extract_fn builder |
| `python/registry/crawl_store.py` | SQLite store (single connection, WAL mode, no thread safety) |

Supporting async code lives in `python/registry/loop_runner.py` but is not used by the crawl pipeline.

## Key Functions

### CrawlOrchestrator.run()
- **File**: python/registry/crawl_orchestrator.py:303
- **Role**: Top-level entry. Phase 1: DFS from entry points (sequential, dependency-ordered). Phase 2: calls `_sweep_remaining()` for everything DFS didn't reach.
- **Calls**: `_dfs_extract()`, `_sweep_remaining()`
- **Called by**: `cmd_crawl()` in cli.py:1082

### CrawlOrchestrator._sweep_remaining()
- **File**: python/registry/crawl_orchestrator.py:328
- **Role**: Iterates `store.get_pending_uuids()` and calls `extract_one()` sequentially for each. **This is the primary concurrency target** — these records are independent (no DFS ordering needed).
- **Calls**: `extract_one()`, `_should_skip()`
- **Called by**: `run()`
- **Current behavior**: Pure sequential loop over all pending UUIDs

### CrawlOrchestrator.extract_one()
- **File**: python/registry/crawl_orchestrator.py:95
- **Role**: Extracts a single UUID with retry logic (up to `max_retries` attempts). Calls `extract_fn(skeleton, body)`, then `store.upsert_record(result)`.
- **Calls**: `extract_fn` (injected), `store.upsert_record()`, `_read_function_body()`
- **Called by**: `_dfs_extract()`, `_sweep_remaining()`
- **Thread safety concern**: Calls `store.upsert_record()` which does DELETE + INSERT without a wrapping transaction.

### _build_llm_fn()
- **File**: python/registry/cli.py:1115
- **Role**: Factory that creates a synchronous `llm_fn(prompt) -> str`. **Each call creates a new `ClaudeSDKClient`, connects, queries, disconnects.** This is the per-call overhead bottleneck.
- **Calls**: `ClaudeSDKClient`, `asyncio.run()`
- **Called by**: `_build_extract_fn()`
- **Key problem**: Lines 1141-1159 — client instantiation, `connect()`, `query()`, `receive_response()`, `disconnect()` all happen inside the closure, per-call.

### _build_extract_fn()
- **File**: python/registry/cli.py:1232
- **Role**: Wraps `llm_fn` with prompt construction + JSON parsing to produce an `extract_fn(skeleton, body) -> FnRecord`.
- **Calls**: `_build_llm_fn()`, `_extract_json_object()`
- **Called by**: `cmd_crawl()`

### cmd_crawl()
- **File**: python/registry/cli.py:956
- **Role**: CLI handler. Opens CrawlStore, builds extract_fn, creates CrawlOrchestrator, calls `orch.run()`.
- **Calls**: `_build_extract_fn()`, `CrawlOrchestrator()`
- **Called by**: CLI dispatch at cli.py:1580

### CrawlStore.get_pending_uuids()
- **File**: python/registry/crawl_store.py:412
- **Role**: Returns `list[str]` of UUIDs where `do_description` is `SKELETON_ONLY` or `EXTRACTION_FAILED`, ordered by `file_path, line_number`.
- **Called by**: `_sweep_remaining()`

### CrawlStore.upsert_record()
- **File**: python/registry/crawl_store.py:284
- **Role**: DELETE old record + INSERT new. **Not transactionally safe** — three separate statements (UPDATE ins, DELETE record, INSERT record) with commits per-method.
- **Thread safety**: NOT safe for concurrent use. Single `sqlite3.Connection`, no `check_same_thread=False`, no locks.

## Call Graph

```
cmd_crawl() [cli.py:956]
  ├── _build_extract_fn() [cli.py:1232]
  │   └── _build_llm_fn() [cli.py:1115]
  │       └── llm_fn() closure [cli.py:1133]
  │           └── asyncio.run(_call()) [cli.py:1134]
  │               ├── ClaudeSDKClient() — NEW per call [cli.py:1141]
  │               ├── client.connect() [cli.py:1142]
  │               ├── client.query() [cli.py:1144]
  │               ├── client.receive_response() [cli.py:1146]
  │               └── client.disconnect() [cli.py:1157]
  │
  └── CrawlOrchestrator.run() [crawl_orchestrator.py:303]
      ├── Phase 1: _dfs_extract() — sequential, dependency-ordered
      │   └── extract_one() → extract_fn() → llm_fn()
      │       └── _process_extraction_result() → DFS children
      │
      └── Phase 2: _sweep_remaining() — sequential, INDEPENDENT records ← CONCURRENCY TARGET
          └── for uuid in get_pending_uuids():
              └── extract_one() → extract_fn() → llm_fn()
```

## Test Verification: Fresh Context Is Safe

**Test file**: `python/tests/test_concurrent_extraction.py` — 10 tests, all passing.

These tests prove three critical properties that confirm standalone `query()` (fresh context per call) will work correctly:

### Property 1: Each card extraction is exactly ONE LLM call

`extract_one()` calls `extract_fn(skeleton, body)` exactly once on success. There is no multi-turn conversation — a single prompt goes in, a single JSON response comes out. The `extract_fn` signature is `(skeleton, body, error_feedback?) -> FnRecord` — a pure function contract with no hidden state channel.

**Tests**:
- `test_single_successful_extraction_calls_llm_once` — counts calls, asserts exactly 1
- `test_extract_fn_receives_complete_prompt_no_history_needed` — captures args, verifies self-contained prompt
- `test_extract_fn_signature_is_stateless` — uses a pure function to prove the contract

### Property 2: Retry error feedback is embedded IN the prompt, not via conversation history

When `extract_fn` throws (e.g., invalid JSON), the orchestrator captures `str(e)` and passes it as the `error_feedback` parameter on the NEXT call (crawl_orchestrator.py:142). The `extract_fn` then appends `"\n## Previous Error\n{error_feedback}\nPlease fix the JSON output."` to the prompt text (cli.py:1253-1254).

Key: only the MOST RECENT error is passed — `error_feedback` is overwritten each attempt, not accumulated. This means each retry is a self-contained prompt that can run with a fresh context window.

**Tests**:
- `test_retry_passes_error_string_in_prompt` — verifies error_feedback kwarg on retry
- `test_each_retry_gets_same_skeleton_and_body` — verifies identical inputs across retries
- `test_error_feedback_is_only_from_last_failure` — verifies only last error, not history

### Property 3: Sweep-phase extractions are truly independent

Each sweep extraction receives only its own skeleton and source body. No data from other extractions leaks in. Records can be processed in any order and produce identical results.

**Tests**:
- `test_sweep_extractions_dont_share_state` — 5 functions, each sees only its own code
- `test_concurrent_simulation_no_cross_contamination` — no error_feedback leaks between extractions
- `test_sweep_handles_unreachable_records` — confirms DFS vs sweep phase separation
- `test_sweep_records_have_no_ordering_dependency` — reversed order produces same results

### Conclusion: Standalone `query()` is fully compatible

The concurrent pipeline can use `query()` (fresh context per call) without any behavioral change:
1. **Success path**: Single call, self-contained prompt → no context needed
2. **Retry path**: Error feedback baked into prompt text → no conversation history needed
3. **Concurrent path**: Extractions are independent → no cross-contamination possible

## Findings

### 1. Per-call client overhead is the #1 bottleneck
Every single LLM call in `_build_llm_fn()` (cli.py:1133-1161) does:
- `ClaudeSDKClient(options)` — construct new client
- `await client.connect()` — TCP/WebSocket handshake
- `await client.query(prompt)` — send prompt
- `async for message in client.receive_response()` — stream response
- `await client.disconnect()` — tear down connection

For 1062 calls, this means 1062 connection setups and teardowns. A persistent client would eliminate this.

### 2. _sweep_remaining() is embarrassingly parallel
`_sweep_remaining()` (crawl_orchestrator.py:328-342) processes records that are:
- Already ingested (skeletons exist)
- Not reached by DFS (no ordering dependencies)
- Independent of each other

This is a textbook case for `asyncio.Semaphore`-bounded concurrency.

### 3. CrawlStore is NOT thread-safe — but asyncio is single-threaded
SQLite connection has no `check_same_thread=False` and no locks. However, `asyncio` concurrency runs on a single thread, so `asyncio.gather()` with a semaphore would serialize SQLite access naturally (each `await` yields, but SQLite calls are synchronous and complete atomically from asyncio's perspective). **No CrawlStore changes needed if we use asyncio, not threads.**

### 4. The sync/async bridge is wasteful
`_build_llm_fn()` wraps async code in `asyncio.run()` per call, creating and destroying an event loop each time. For concurrent extraction, we need to:
- Keep a single event loop running
- Keep a persistent `ClaudeSDKClient` (or a pool)
- Use `asyncio.gather()` with a semaphore for bounded concurrency

### 5. DFS phase must stay sequential
`_dfs_extract()` discovers children from extraction results (`_process_extraction_result()`) — you can't parallelize it without fundamentally changing the traversal. The sweep phase is the right target.

## Claude Agent SDK: Context Isolation Constraints

### Critical Finding: No Context Reset API

`ClaudeSDKClient` **accumulates context across `query()` calls by design**. There is no `reset_context()`, `clear()`, or `new_session()` method. Every `query()` on the same connected client continues the same conversation — the context window does not reset between turns within a session ([Sessions docs](https://platform.claude.com/docs/en/agent-sdk/sessions)).

### `session_id` Does NOT Isolate Context

The `session_id` parameter on `client.query()` is a tagging field, not a routing key. All calls on the same client share the same underlying session regardless of what `session_id` is passed. [GitHub Issue #560](https://github.com/anthropics/claude-agent-sdk-python/issues/560) documents context leaking across different `session_id` values.

### `max_turns=1` Does NOT Give Fresh Context

`max_turns` controls tool-use round trips within a single `query()` invocation — it is a loop limiter, not a session boundary. Conversation history from previous `query()` calls still fully accumulates.

### Two Approaches for Fresh Context Per Extraction

| Approach | Mechanism | Tradeoff |
|---|---|---|
| **New client per call** | `ClaudeSDKClient()` → `connect()` → `query()` → `disconnect()` | Clean isolation; subprocess spawn overhead per call |
| **Disconnect + reconnect same instance** | `safe_disconnect(client)` → `client.connect()` | Reuses object; still full connection cycle |

Both approaches incur the connection setup/teardown cost. There is **no way to get fresh context on a persistent connection** — this is a fundamental SDK constraint ([GitHub Issue #560](https://github.com/anthropics/claude-agent-sdk-python/issues/560), open as of Feb 2026).

### Standalone `query()` Function (Simplest for One-Shot)

The SDK also exports a standalone `query()` function that creates a new session each call:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="...",
    options=ClaudeAgentOptions(system_prompt="...", max_turns=1, model="claude-sonnet-4-6"),
):
    # fresh session, no history from prior calls
```

This is the officially recommended approach for "one-shot task, single prompt, no follow-up" ([Sessions docs](https://platform.claude.com/docs/en/agent-sdk/sessions)).

### Existing Codebase Patterns

The codebase already uses the correct patterns:
- **`_build_llm_fn()` (cli.py:1133-1161)**: New client per call — guarantees fresh context for each card extraction. This is correct for extraction accuracy.
- **`_call_llm_with_client()` (loop_runner.py:66-97)**: Shared client for retries within a GWT session — accumulated context is intentional here (retry benefits from seeing prior errors).
- **`TDDPlanImplementer` (tdd_implement_plan.py:338)**: disconnect+reconnect between plans on same instance.

### Impact on Concurrency Design

**The "persistent client" optimization is NOT viable for card extraction.**

Each card extraction must get a fresh context window to maximize accuracy — if context accumulates, the LLM would see prior cards' prompts and responses, degrading extraction quality and eventually filling the context window.

The correct concurrent approach is a **client pool** — N independent `ClaudeSDKClient` instances, each handling one extraction at a time with full connect/query/disconnect cycles. The concurrency gain comes from running N extractions in parallel (network I/O overlap), not from eliminating connection overhead.

Alternatively, the standalone `query()` function can be called concurrently with `asyncio.gather()` — each call is fully isolated with no shared state.

### `safe_disconnect()` Workaround

The SDK has a known bug where `client.disconnect()` can hang indefinitely ([GitHub Issue #378](https://github.com/anthropics/claude-agent-sdk-python/issues/378)). The codebase wraps disconnects with a 10-second timeout and force-cancels the internal task group (`client._tg.cancel_scope.cancel()`) on timeout. This pattern is at:
- `loop_runner.py:39-52`
- `tdd_implement_plan.py:42-72`

Any concurrent design must use `safe_disconnect()` to avoid hung connections blocking the semaphore.

## Proposed Changes

### Change 1: `_build_async_extract_fn()` using standalone `query()` (cli.py)

Replace `_build_llm_fn()` + `_build_extract_fn()` with a single async function that uses the standalone `query()` for guaranteed context isolation:

```python
def _build_async_extract_fn(model: str = "claude-sonnet-4-6"):
    """Build an async extract_fn using standalone query() — fresh context per call."""
    import os
    os.environ.pop("CLAUDECODE", None)
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock

    async def extract_fn(skeleton, body, error_feedback=None):
        prompt = _build_extraction_prompt(skeleton, body, error_feedback)
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
        return _parse_fn_record(skeleton, data)  # existing JSON → FnRecord logic

    return extract_fn
```

Each call to `query()` creates a completely fresh session — no context leakage between cards. The concurrency comes from running N of these in parallel via `asyncio.gather()`.

### Change 2: Async `_sweep_remaining()` (crawl_orchestrator.py:328-342)

Convert `_sweep_remaining()` to use asyncio with a semaphore:

```python
async def _sweep_remaining_async(self, concurrency: int = 10) -> None:
    sem = asyncio.Semaphore(concurrency)
    remaining = self.store.get_pending_uuids()

    async def _extract_bounded(uuid):
        async with sem:
            if uuid in self._visited:
                return
            self._visited.add(uuid)
            if self._should_skip(uuid):
                self._skipped += 1
                return
            result = await self.extract_one_async(uuid)
            if result is not None:
                self._extracted += 1

    tasks = [_extract_bounded(u) for u in remaining]
    await asyncio.gather(*tasks)
```

**Requires**: `extract_fn` and `extract_one` to become async-aware.

### Change 3: Restructure to async-first orchestrator

The cleanest approach:
1. Make `CrawlOrchestrator` async-native (`async def run()`, `async def extract_one()`)
2. Accept an `async_extract_fn` instead of sync `extract_fn` — each call gets fresh context via standalone `query()`
3. DFS phase: sequential `await` calls (same ordering, same accuracy)
4. Sweep phase: `asyncio.gather()` with `Semaphore(concurrency)` — N independent extractions in parallel, each with its own fresh context window
5. `cmd_crawl()` calls `asyncio.run(orch.run())` once
6. All `disconnect()` calls must use `safe_disconnect()` pattern (10s timeout + `_tg` cancel) to avoid hung connections

### Change 4: CLI `--concurrency` flag (cli.py:1520-1533)

Add to argparse:
```python
p_crawl.add_argument("--concurrency", type=int, default=10,
                     help="Max concurrent LLM extractions in sweep phase (default: 10)")
```

Pass through to `CrawlOrchestrator.__init__()` and use in `_sweep_remaining_async()`.

### Implementation Order

1. **`_build_async_extract_fn()`** in cli.py — async callable using standalone `query()` for fresh context per card
2. **Convert `CrawlOrchestrator` to async** — `extract_one` → `async def extract_one`, `_dfs_extract` → `async def _dfs_extract`, `run` → `async def run`, `_sweep_remaining` → `async def _sweep_remaining` with semaphore
3. **`--concurrency` CLI flag** — argparse + pass-through
4. **`cmd_crawl()` update** — `asyncio.run(orch.run())` instead of `orch.run()`
5. **Keep sync `_build_extract_fn()`** as fallback for `--concurrency=1` (backwards compat)

### Risk Assessment

- **Context isolation (CRITICAL)**: Each card extraction MUST get a fresh context window. Using standalone `query()` guarantees this — no accumulated context between cards. A persistent `ClaudeSDKClient` would leak context and degrade accuracy. This is a fundamental SDK constraint with no workaround.
- **`safe_disconnect()` hang bug**: SDK `disconnect()` can hang indefinitely ([Issue #378](https://github.com/anthropics/claude-agent-sdk-python/issues/378)). All disconnects must use the 10s timeout + `_tg` cancel pattern. With N concurrent extractions, a hung disconnect would block a semaphore slot. Standalone `query()` may avoid this since it manages its own lifecycle — needs verification.
- **CrawlStore thread safety**: Non-issue with asyncio (single-threaded). SQLite calls are synchronous and complete before the next `await` yields. The semaphore ensures only N extractions are in-flight, but SQLite writes still serialize naturally.
- **`max_functions` limit**: Currently checked per-iteration. With concurrency, we might overshoot by up to `concurrency - 1` functions. Acceptable tradeoff, or add an `asyncio.Event` to signal early stop.
- **Error handling**: Each extraction already has retry logic in `extract_one()`. Failures are independent. `asyncio.gather(return_exceptions=True)` would prevent one failure from canceling the batch.
- **Progress output**: `_on_progress` writes to stderr. With concurrent extractions, output will interleave but remain readable (each line is atomic from `print()`'s perspective).
- **Rate limiting**: Anthropic API has rate limits. With concurrency=10, we may hit them. The semaphore bounds in-flight requests, and the SDK should return rate-limit errors that the retry logic in `extract_one()` already handles.

## CW9 Mention Summary
Functions: _sweep_remaining(), extract_one(), _build_llm_fn(), _build_extract_fn(), cmd_crawl(), run(), _dfs_extract(), _process_extraction_result(), get_pending_uuids(), upsert_record(), safe_disconnect(), _call_llm_with_client(), call_llm(), _make_client(), _extract_json_object()
Files: python/registry/crawl_orchestrator.py, python/registry/cli.py, python/registry/crawl_store.py, python/registry/loop_runner.py, python/tests/test_concurrent_extraction.py
Directories: python/registry/
