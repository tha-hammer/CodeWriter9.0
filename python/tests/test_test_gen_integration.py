"""Integration tests: sim traces → test_gen_loop → working test file.

Tests that real TLC simulation traces (from the fixed file-format parser)
flow correctly through the test generation pipeline:
  bridge_artifacts + sim_traces → build_test_plan_prompt → mock LLM → verify_test_file

Uses actual pipeline output from /tmp/cw9-pipeline-* when available,
falls back to inline fixtures for CI.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from registry.test_gen_loop import (
    TestGenContext,
    build_codegen_prompt,
    build_compiler_hints,
    build_retry_prompt,
    build_review_prompt,
    build_test_plan_prompt,
    run_test_gen_loop,
)
from registry.traces import SimulationTrace, format_traces_for_prompt, load_simulation_traces


# ---------------------------------------------------------------------------
# Inline fixture: gwt-0003 (simplest GWT from silmari pipeline)
# ---------------------------------------------------------------------------

GWT_0003_BRIDGE = {
    "gwt_id": "gwt-0003",
    "module_name": "AllocateFreshChallengeForDispatch",
    "data_structures": {
        "ChallengeState": {
            "function_id": "ChallengeState",
            "fields": {
                "challengePool": {"type": "shared/data_types/set"},
                "activeChallenge": {"type": "shared/data_types/mapping"},
                "challengeStatus": {"type": "shared/data_types/mapping"},
            },
        },
    },
    "operations": {
        "ChallengeIssue": {
            "function_id": "ChallengeIssue",
            "parameters": {"dispatch_id": "str", "challenge_pool": "set"},
            "returns": "tuple[str, str]",
        },
        "Finish": {
            "function_id": "Finish",
            "parameters": {},
            "returns": "None",
        },
    },
    "verifiers": {
        "AtMostOneOpenChallengePerDispatch": {
            "conditions": [
                "\\A d \\in DispatchIds : Cardinality({c \\in ChallengeIds : "
                "activeChallenge[d] = c /\\ challengeStatus[c] = \"open\"}) <= 1"
            ],
            "applies_to": ["activeChallenge", "challengeStatus"],
        },
        "AllocatedChallengesInDomain": {
            "conditions": [
                "\\A d \\in DispatchIds : activeChallenge[d] # \"none\" "
                "=> activeChallenge[d] \\in ChallengeIds"
            ],
            "applies_to": ["activeChallenge"],
        },
        "PoolAndActiveMutuallyExclusive": {
            "conditions": [
                "\\A d \\in DispatchIds : activeChallenge[d] # \"none\" "
                "=> activeChallenge[d] \\notin challengePool"
            ],
            "applies_to": ["activeChallenge", "challengePool"],
        },
    },
    "assertions": {
        "assert_AtMostOneOpen": {
            "condition": "len(open_challenges_for(d)) <= 1",
            "message": "Dispatch has more than one open challenge",
        },
        "assert_InDomain": {
            "condition": "active in challenge_ids or active == 'none'",
            "message": "Active challenge not in domain",
        },
        "assert_MutuallyExclusive": {
            "condition": "active not in pool",
            "message": "Active challenge still in pool",
        },
    },
    "test_scenarios": [
        {
            "name": "issue_challenge",
            "setup": "pool={c1,c2}, dispatches={d1,d2}, all inactive",
            "steps": ["issue_challenge(d1)"],
            "expected_outcome": "d1 gets a challenge from pool",
            "invariant_tested": "PostConditionHolds",
        },
    ],
    "simulation_traces": [
        [
            {
                "state_num": 1, "label": "Init",
                "vars": {
                    "challengePool": "{ChallengeIds_1, ChallengeIds_2}",
                    "pc": "(\"main\" :> \"ChallengeIssue\")",
                    "activeChallenge": "(DispatchIds_1 :> \"none\" @@ DispatchIds_2 :> \"none\")",
                    "issued_challenge": "\"none\"",
                    "issued_dispatch": "\"none\"",
                    "challengeStatus": "(ChallengeIds_1 :> \"available\" @@ ChallengeIds_2 :> \"available\")",
                },
            },
            {
                "state_num": 2, "label": "ChallengeIssue",
                "vars": {
                    "challengePool": "{ChallengeIds_2}",
                    "pc": "(\"main\" :> \"Finish\")",
                    "activeChallenge": "(DispatchIds_1 :> ChallengeIds_1 @@ DispatchIds_2 :> \"none\")",
                    "issued_challenge": "ChallengeIds_1",
                    "issued_dispatch": "DispatchIds_1",
                    "challengeStatus": "(ChallengeIds_1 :> \"open\" @@ ChallengeIds_2 :> \"available\")",
                },
            },
            {
                "state_num": 3, "label": "Finish",
                "vars": {
                    "challengePool": "{ChallengeIds_2}",
                    "pc": "(\"main\" :> \"Done\")",
                    "activeChallenge": "(DispatchIds_1 :> ChallengeIds_1 @@ DispatchIds_2 :> \"none\")",
                    "issued_challenge": "ChallengeIds_1",
                    "issued_dispatch": "DispatchIds_1",
                    "challengeStatus": "(ChallengeIds_1 :> \"open\" @@ ChallengeIds_2 :> \"available\")",
                },
            },
        ],
    ],
}

GWT_0003_SPEC_TEXT = textwrap.dedent("""\
    ---- MODULE AllocateFreshChallengeForDispatch ----
    EXTENDS Integers, FiniteSets
    CONSTANTS DispatchIds, ChallengeIds
    (* --algorithm ChallengeIssue ... end algorithm; *)
    ====
""")


# ---------------------------------------------------------------------------
# Tests: Sim traces → prompt construction
# ---------------------------------------------------------------------------

class TestSimTracesInPrompt:
    """Real sim traces flow through build_test_plan_prompt correctly."""

    def _make_ctx(self, **overrides) -> TestGenContext:
        defaults = dict(
            gwt_id="gwt-0003",
            gwt_text={
                "given": "a dispatch mapping with no open challenges",
                "when": "a fresh challenge is allocated for a dispatch",
                "then": "exactly one open challenge exists for that dispatch",
            },
            module_name="AllocateFreshChallengeForDispatch",
            bridge_artifacts=GWT_0003_BRIDGE,
            compiler_hints=build_compiler_hints(GWT_0003_BRIDGE),
            api_context="from registry.dag import RegistryDag\n",
            test_scenarios=GWT_0003_BRIDGE["test_scenarios"],
            simulation_traces=GWT_0003_BRIDGE["simulation_traces"],
            tla_spec_text=GWT_0003_SPEC_TEXT,
            output_dir=Path("/tmp"),
            source_dir=Path("/tmp"),
        )
        defaults.update(overrides)
        return TestGenContext(**defaults)

    def test_prompt_contains_all_trace_states(self):
        """All 3 states from the sim trace appear in the prompt."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        assert "Init" in prompt
        assert "ChallengeIssue" in prompt
        assert "Finish" in prompt

    def test_prompt_contains_trace_variables(self):
        """TLA+ variable values from traces appear in the prompt."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        assert "challengePool" in prompt
        assert "activeChallenge" in prompt
        assert "ChallengeIds_1" in prompt

    def test_prompt_traces_rank_above_api(self):
        """Traces appear before API context in the prompt."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        traces_pos = prompt.find("Concrete Verified Scenarios")
        api_pos = prompt.find("Available Python API")
        assert traces_pos < api_pos

    def test_prompt_includes_verifier_names(self):
        """Verifier names from bridge artifacts appear in the prompt."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        assert "AtMostOneOpenChallengePerDispatch" in prompt
        assert "PoolAndActiveMutuallyExclusive" in prompt

    def test_prompt_includes_tla_spec(self):
        """The full TLA+ spec text is included."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        assert "MODULE AllocateFreshChallengeForDispatch" in prompt

    def test_prompt_includes_translate_instructions(self):
        """When traces exist, prompt instructs LLM to translate (not invent)."""
        ctx = self._make_ctx()
        prompt = build_test_plan_prompt(ctx)
        assert "Translate each trace" in prompt
        assert "Do NOT invent topologies" in prompt

    def test_codegen_prompt_references_verifiers(self):
        """The codegen prompt references verifiers for the LLM to implement."""
        ctx = self._make_ctx()
        reviewed_plan = "Test plan: test_challenge_issue tests PostConditionHolds"
        prompt = build_codegen_prompt(reviewed_plan, ctx)
        assert "gwt-0003" in prompt
        assert "verifier" in prompt.lower()

    def test_review_prompt_includes_bridge_verifiers(self):
        """The review prompt includes verifier conditions as ground truth."""
        ctx = self._make_ctx()
        test_plan = "Plan: test one invariant"
        prompt = build_review_prompt(test_plan, ctx)
        assert "AtMostOneOpenChallengePerDispatch" in prompt


class TestSimTracesFromRealPipeline:
    """Load real bridge artifacts from the pipeline run if available."""

    PIPELINE_DIR = Path("/tmp/cw9-pipeline-5ul0qwc2")

    @pytest.fixture
    def real_bridge(self):
        artifact_path = self.PIPELINE_DIR / ".cw9/bridge/gwt-0003_bridge_artifacts.json"
        if not artifact_path.exists():
            pytest.skip("No real pipeline artifacts available")
        return json.loads(artifact_path.read_text())

    def test_real_traces_load_as_simulation_traces(self, real_bridge):
        """Real sim traces from the pipeline parse into SimulationTrace objects."""
        traces = load_simulation_traces(
            real_bridge["simulation_traces"],
            list(real_bridge["verifiers"].keys()),
        )
        assert len(traces) == 10
        assert all(isinstance(t, SimulationTrace) for t in traces)
        assert traces[0].step_count >= 2

    def test_real_traces_format_for_prompt(self, real_bridge):
        """Real traces format correctly for the LLM prompt."""
        traces = load_simulation_traces(
            real_bridge["simulation_traces"],
            list(real_bridge["verifiers"].keys()),
        )
        formatted = format_traces_for_prompt(
            traces, list(real_bridge["verifiers"].keys()),
        )
        assert "Concrete Verified Scenarios" in formatted
        assert "Trace 1" in formatted
        assert "Init" in formatted

    def test_real_prompt_builds_without_error(self, real_bridge):
        """build_test_plan_prompt succeeds with real pipeline data."""
        ctx = TestGenContext(
            gwt_id="gwt-0003",
            gwt_text={"given": "g", "when": "w", "then": "t"},
            module_name=real_bridge["module_name"],
            bridge_artifacts=real_bridge,
            compiler_hints=build_compiler_hints(real_bridge),
            api_context="# real api\n",
            test_scenarios=real_bridge.get("test_scenarios", []),
            simulation_traces=real_bridge["simulation_traces"],
            output_dir=Path("/tmp"),
            source_dir=Path("/tmp"),
        )
        prompt = build_test_plan_prompt(ctx)
        assert len(prompt) > 500  # Non-trivial prompt
        assert "Trace 1" in prompt


# ---------------------------------------------------------------------------
# Integration: run_test_gen_loop with mock LLM
# ---------------------------------------------------------------------------

class TestRunTestGenLoopIntegration:
    """End-to-end test: sim traces → mock LLM → verify test file."""

    # A minimal but valid test file the mock LLM "generates"
    MOCK_TEST_CODE = textwrap.dedent('''\
        """Tests for AllocateFreshChallengeForDispatch (gwt-0003).

        Derived from TLC simulation traces verifying:
        - AtMostOneOpenChallengePerDispatch
        - AllocatedChallengesInDomain
        - PoolAndActiveMutuallyExclusive
        """


        def test_challenge_issue_from_pool():
            """Trace 1: Init → ChallengeIssue → Finish.

            After issuing a challenge:
            - The issued challenge is removed from the pool
            - The dispatch's active challenge is set
            - The challenge status is 'open'
            """
            pool = {"c1", "c2"}
            active = {"d1": None, "d2": None}

            # ChallengeIssue action
            challenge = "c1"
            dispatch = "d1"
            active[dispatch] = challenge
            pool.discard(challenge)
            status = {challenge: "open"}

            # PostConditionHolds
            assert active[dispatch] == challenge
            assert challenge not in pool
            assert status[challenge] == "open"

            # AtMostOneOpenChallengePerDispatch
            open_for_d1 = [c for c in ["c1", "c2"] if active.get("d1") == c and status.get(c) == "open"]
            assert len(open_for_d1) <= 1


        def test_pool_and_active_mutually_exclusive():
            """PoolAndActiveMutuallyExclusive: active challenge not in pool."""
            pool = {"c1", "c2"}
            active = {"d1": None}

            # Issue
            active["d1"] = "c1"
            pool.discard("c1")

            assert active["d1"] not in pool


        def test_allocated_in_domain():
            """AllocatedChallengesInDomain: active challenge is from ChallengeIds."""
            challenge_ids = {"c1", "c2"}
            active = {"d1": "c1"}

            for d, c in active.items():
                if c is not None:
                    assert c in challenge_ids
    ''')

    @pytest.fixture
    def gen_ctx(self, tmp_path):
        output_dir = tmp_path / "tests" / "generated"
        output_dir.mkdir(parents=True)
        return TestGenContext(
            gwt_id="gwt-0003",
            gwt_text={
                "given": "a dispatch mapping with no open challenges",
                "when": "a fresh challenge is allocated for a dispatch",
                "then": "exactly one open challenge exists for that dispatch",
            },
            module_name="AllocateFreshChallengeForDispatch",
            bridge_artifacts=GWT_0003_BRIDGE,
            compiler_hints=build_compiler_hints(GWT_0003_BRIDGE),
            api_context="# minimal api context\n",
            test_scenarios=GWT_0003_BRIDGE["test_scenarios"],
            simulation_traces=GWT_0003_BRIDGE["simulation_traces"],
            tla_spec_text=GWT_0003_SPEC_TEXT,
            output_dir=output_dir,
            source_dir=tmp_path,
        )

    @pytest.mark.asyncio
    async def test_full_loop_with_mock_llm(self, gen_ctx, tmp_path):
        """Mock LLM returns a valid test file; pipeline verifies it passes."""
        call_count = 0

        async def mock_llm(prompt: str, system_prompt: str | None = None) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "Test plan: 3 tests covering the 3 verifiers"
            elif call_count == 2:
                return "Reviewed: plan looks good, no changes"
            else:
                return self.MOCK_TEST_CODE

        result = await run_test_gen_loop(
            gen_ctx, mock_llm, max_attempts=1,
            session_dir=tmp_path / "sessions",
        )

        # The mock test file should compile and pass pytest
        assert result.passed, f"Test verification failed: {result.errors}"
        assert result.stage == "run"
        assert call_count == 3  # plan + review + codegen

    @pytest.mark.asyncio
    async def test_loop_saves_session_artifacts(self, gen_ctx, tmp_path):
        """Session dir gets plan and review files."""
        async def mock_llm(prompt: str, system_prompt: str | None = None) -> str:
            if "plan" in prompt.lower()[:100]:
                return "Test plan here"
            elif "review" in prompt.lower()[:100]:
                return "Reviewed plan here"
            else:
                return self.MOCK_TEST_CODE

        session_dir = tmp_path / "sessions"
        await run_test_gen_loop(
            gen_ctx, mock_llm, max_attempts=1,
            session_dir=session_dir,
        )

        assert (session_dir / "gwt-0003_plan.txt").exists()
        assert (session_dir / "gwt-0003_review.txt").exists()

    @pytest.mark.asyncio
    async def test_loop_retries_on_syntax_error(self, gen_ctx, tmp_path):
        """If first codegen has syntax error, loop retries with corrected code."""
        call_count = 0

        async def mock_llm(prompt: str, system_prompt: str | None = None) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # plan + review
                return "plan/review"
            elif call_count == 3:
                # First codegen: broken
                return "def test_broken(:\n    pass\n"
            else:
                # Retry: fixed
                return self.MOCK_TEST_CODE

        result = await run_test_gen_loop(
            gen_ctx, mock_llm, max_attempts=3,
            session_dir=tmp_path / "sessions",
        )

        assert result.passed
        assert result.attempt == 2  # First attempt failed, second succeeded

    @pytest.mark.asyncio
    async def test_prompt_sent_to_llm_contains_traces(self, gen_ctx, tmp_path):
        """The actual prompt sent to the LLM contains simulation trace data."""
        captured_prompts = []

        async def mock_llm(prompt: str, system_prompt: str | None = None) -> str:
            captured_prompts.append(prompt)
            if len(captured_prompts) <= 2:
                return "plan/review"
            return self.MOCK_TEST_CODE

        await run_test_gen_loop(gen_ctx, mock_llm, max_attempts=1)

        # First prompt (plan) should contain traces
        plan_prompt = captured_prompts[0]
        assert "Concrete Verified Scenarios" in plan_prompt
        assert "ChallengeIssue" in plan_prompt
        assert "ChallengeIds_1" in plan_prompt

    @pytest.mark.asyncio
    async def test_generated_test_file_exists(self, gen_ctx, tmp_path):
        """The test file is written to the output directory."""
        async def mock_llm(prompt: str, system_prompt: str | None = None) -> str:
            return self.MOCK_TEST_CODE

        await run_test_gen_loop(gen_ctx, mock_llm, max_attempts=1)

        test_path = gen_ctx.output_dir / "test_gwt_0003.py"
        assert test_path.exists()
        content = test_path.read_text()
        assert "test_challenge_issue_from_pool" in content
