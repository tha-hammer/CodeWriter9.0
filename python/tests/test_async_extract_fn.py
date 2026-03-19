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
