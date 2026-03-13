"""Common loop runner — LLM → PlusCal → TLC pipeline."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

os.environ.pop("CLAUDECODE", None)
import claude_agent_sdk
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ToolResultBlock, TextBlock, ResultMessage

from registry.context import ProjectContext
from registry.one_shot_loop import (
    OneShotLoop, query_context, format_prompt_context,
    LoopResult, LoopStatus, TLCErrorClass, extract_pluscal,
)

# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------
_DEFAULT_SYSTEM_PROMPT = (
    "You are a TLA+/PlusCal expert. Generate formally verifiable "
    "PlusCal specifications from behavioral requirements. "
    "Output ONLY the raw TLA+ module text — no markdown fencing, "
    "no explanation. Reserved PlusCal labels you must NEVER use: "
    "Done, Error, Loop. Use Finish/Complete/Terminate instead."
)

DISCONNECT_TIMEOUT_SECONDS = 10.0


async def safe_disconnect(client: ClaudeSDKClient, timeout: float = DISCONNECT_TIMEOUT_SECONDS) -> bool:
    """Safely disconnect with timeout to prevent SDK hang bug."""
    try:
        await asyncio.wait_for(client.disconnect(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        if hasattr(client, '_tg') and client._tg:
            try:
                client._tg.cancel_scope.cancel()
            except Exception:
                pass
        return False
    except Exception:
        return False


def _make_client(system_prompt: str | None = None) -> ClaudeSDKClient:
    """Create a fresh ClaudeSDKClient (one per GWT session)."""
    options = ClaudeAgentOptions(
        allowed_tools=[],
        system_prompt=system_prompt or _DEFAULT_SYSTEM_PROMPT,
        max_turns=20,
        model="claude-sonnet-4-6",
    )
    return ClaudeSDKClient(options)


async def _call_llm_with_client(
    client: ClaudeSDKClient,
    prompt: str,
    *,
    connect: bool = False,
) -> str:
    """Send a prompt to an existing client and collect the response.

    Pass connect=True for the first call on a new client.
    """
    if connect:
        await client.connect()

    await client.query(prompt)

    result_text = []
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"\033[94m{block.text}\033[0m\n", end="")
                    result_text.append(block.text)
                elif isinstance(block, ToolResultBlock):
                    print(f"\033[93mTool: {block.content}\033[0m\n")
                elif hasattr(block, "name"):
                    print(f"\033[93mTool: {block.name}\033[0m\n")
        elif isinstance(message, ResultMessage):
            if message.result:
                print(f"\033[94m{message.result}\033[0m\n", end="")
                result_text.append(message.result)
            print(f"\033[92mDone: {message.subtype}\033[0m\n")
    return "\n".join(result_text)


async def call_llm(prompt: str, system_prompt: str | None = None) -> str:
    """One-shot LLM call (creates a fresh client each time).

    For batch usage, prefer run_loop() which creates one client per GWT
    and reuses it across retries for that GWT.
    """
    client = _make_client(system_prompt)
    try:
        return await _call_llm_with_client(client, prompt, connect=True)
    finally:
        await safe_disconnect(client)


_ERROR_CLASS_INSTRUCTIONS: dict[TLCErrorClass, str] = {
    TLCErrorClass.SYNTAX_ERROR: (
        "### Failure Type: PlusCal SYNTAX ERROR\n"
        "Your PlusCal code did not compile. This is a syntax issue, not a logic issue.\n"
        "Focus on fixing PlusCal syntax. Do NOT change your algorithm logic — "
        "only fix the syntax so pcal.trans accepts it.\n\n"
        "Common PlusCal syntax issues:\n"
        "- **Missing label after control flow with goto**: If ANY branch of an "
        "`either/or` or `if/else` contains a `goto`, `call`, or `return`, then "
        "the statement AFTER `end either`/`end if` MUST have a label. Also, within "
        "`either/or`, avoid mixing `skip` with multi-statement `goto` branches — "
        "restructure so each `or` branch is self-contained or extract the goto branch "
        "into a separate labeled step.\n"
        "- Missing semicolons after assignments or `skip`\n"
        "- Mismatched `begin`/`end` or `either`/`end either`\n"
        "- Using reserved words (`Done`, `pc`, `stack`) as labels or variables\n"
        "- Label required: first statement in a process, after `while`, after any "
        "control structure containing `goto`/`call`/`return`"
    ),
    TLCErrorClass.PARSE_ERROR: (
        "### Failure Type: TLA+ PARSE/SEMANTIC ERROR\n"
        "PlusCal compiled but the generated TLA+ has a parse or semantic error.\n"
        "Check for undefined operators, missing EXTENDS, or malformed expressions."
    ),
    TLCErrorClass.TYPE_ERROR: (
        "### Failure Type: TLC TYPE MISMATCH\n"
        "PlusCal compiled successfully. TLC found a type error at runtime.\n"
        "A variable or expression has the wrong type (e.g., applying arithmetic to "
        "a string, or using a set where a number is expected). Fix the type of the "
        "offending variable or expression. The algorithm structure is correct."
    ),
    TLCErrorClass.INVARIANT_VIOLATION: (
        "### Failure Type: INVARIANT VIOLATION (counterexample below)\n"
        "PlusCal compiled successfully and TLC ran, but found a state that violates "
        "an invariant. The spec structure is correct — only the algorithm logic or "
        "invariant definition needs to change. Study the counterexample trace below "
        "to understand which state transition is wrong."
    ),
    TLCErrorClass.DEADLOCK: (
        "### Failure Type: DEADLOCK\n"
        "PlusCal compiled successfully but TLC found a deadlock — a reachable state "
        "with no enabled actions. Common fixes:\n"
        "- Add a termination label with skip (if the process should end)\n"
        "- Add an `either` branch for the stuck case\n"
        "- Check `await` conditions that can never be satisfied"
    ),
    TLCErrorClass.CONSTANT_MISMATCH: (
        "### Failure Type: CONSTANT/OPERATOR MISMATCH\n"
        "TLC cannot find an operator or CONSTANT that the spec references. Either:\n"
        "- Add a CONSTANTS declaration for the missing name\n"
        "- Add the missing operator definition in the `define` block\n"
        "- Check that the .cfg file defines all CONSTANTS"
    ),
}


def build_retry_prompt(
    initial_prompt: str,
    attempt: int,
    status: LoopStatus,
    previous_response: str = "",
) -> str:
    """Build a retry prompt from the LoopStatus counterexample and error.

    Uses error classification to give targeted fix instructions instead of
    dumping raw TLC output and hoping the LLM figures out the failure class.
    """
    parts = [initial_prompt, "\n\n## RETRY — Previous Attempt Failed\n"]

    parts.append(f"Attempt {attempt} failed.")

    # Classified error instructions (the key improvement)
    error_class = (
        status.tlc_result.error_class
        if status.tlc_result and status.tlc_result.error_class
        else None
    )
    if error_class and error_class in _ERROR_CLASS_INSTRUCTIONS:
        parts.append(f"\n{_ERROR_CLASS_INSTRUCTIONS[error_class]}")

    if previous_response:
        parts.append(f"\n### Your Previous Output\n```\n{previous_response}\n```")

    if status.error:
        parts.append(f"\n### Error\n{status.error}")

    if status.counterexample is not None:
        ce = status.counterexample
        if ce.violated_invariant:
            parts.append(f"\n### Violated Invariant\n`{ce.violated_invariant}`")
        if ce.pluscal_summary:
            parts.append(f"\n### Counterexample Summary\n{ce.pluscal_summary}")
        if ce.states:
            parts.append("\n### State Trace")
            for state in ce.states:
                snum = state.get("state_num", "?")
                label = state.get("label", "unknown")
                parts.append(f"\nState {snum} <{label}>:")
                for var, val in state.get("vars", {}).items():
                    parts.append(f"  /\\ {var} = {val}")

    if status.tlc_result and status.tlc_result.error_message:
        parts.append(f"\n### TLC Output\n{status.tlc_result.error_message}")

    parts.append("\n\nFix the specification above to resolve these errors. Output the COMPLETE corrected TLA+ module.")
    return "\n".join(parts)


async def run_loop(
    ctx: ProjectContext,
    gwt_id: str,
    max_retries: int = 5,
    log_fn=print,
    context_text: str = "",
) -> tuple[LoopResult, Path | None]:
    """Run the LLM → PlusCal → TLC loop for a GWT behavior.

    The GWT must already exist in the DAG (via register_gwt() or extract).

    Args:
        context_text: Supplementary context (e.g., plan_path content)
            passed verbatim into the LLM prompt.

    Returns (result, spec_path) where spec_path is the verified .tla
    file path on success, or None on failure.
    """
    from registry.dag import RegistryDag

    # Load DAG
    dag_path = ctx.state_root / "dag.json"
    if not dag_path.exists():
        log_fn(f"Error: No DAG found at {dag_path}. Run: cw9 extract")
        return LoopResult.FAIL, None
    dag = RegistryDag.load(dag_path)

    # Verify GWT exists
    if gwt_id not in dag.nodes:
        log_fn(f"Error: {gwt_id} not found in DAG")
        return LoopResult.FAIL, None

    gwt_node = dag.nodes[gwt_id]

    # Build initial prompt from GWT's given/when/then + registry context
    bundle = query_context(dag, gwt_id)
    prompt_ctx = format_prompt_context(bundle)

    # Read PlusCal template
    template_path = ctx.template_dir / "state_machine.tla"
    template_text = template_path.read_text() if template_path.exists() else ""

    initial_prompt = _build_prompt(gwt_node, prompt_ctx, template_text, context_text)
    current_prompt = initial_prompt

    # One client per GWT — retries share context, different GWTs get fresh sessions
    client = _make_client()

    # Derive module_name from GWT name (e.g., "validation_runs" -> "ValidationRuns")
    module_name = "".join(w.capitalize() for w in gwt_node.name.split("_"))
    if not module_name:
        module_name = gwt_id.replace("-", "_")

    # Default cfg_text for TLC configuration
    cfg_text = "SPECIFICATION Spec\n"

    # Collect counterexample traces during retries
    collected_traces = []

    try:
        for attempt in range(1, max_retries + 1):
            log_fn(f"Attempt {attempt}/{max_retries}")

            response = await _call_llm_with_client(
                client, current_prompt, connect=(attempt == 1),
            )

            # Save LLM response
            ctx.session_dir.mkdir(parents=True, exist_ok=True)
            response_path = ctx.session_dir / f"{gwt_id}_attempt{attempt}.txt"
            response_path.write_text(response)

            # Process through OneShotLoop (compile PlusCal, run TLC)
            loop = OneShotLoop(dag=dag, ctx=ctx)
            loop.query(gwt_id)
            status = loop.process_response(
                llm_response=response,
                module_name=module_name,
                cfg_text=cfg_text,
            )

            if status.result == LoopResult.PASS:
                ctx.spec_dir.mkdir(parents=True, exist_ok=True)
                if status.compiled_spec_path:
                    dest_tla = ctx.spec_dir / f"{gwt_id}.tla"
                    dest_cfg = ctx.spec_dir / f"{gwt_id}.cfg"
                    shutil.copy2(status.compiled_spec_path, dest_tla)
                    cfg_src = status.compiled_spec_path.with_suffix(".cfg")
                    if cfg_src.exists():
                        shutil.copy2(cfg_src, dest_cfg)
                    log_fn(f"PASS — verified spec saved: {dest_tla}")

                    # Save collected counterexample traces
                    if collected_traces:
                        traces_path = ctx.spec_dir / f"{gwt_id}_traces.json"
                        traces_path.write_text(json.dumps(collected_traces, indent=2))

                    # v5: Generate simulation traces from the verified model
                    from registry.one_shot_loop import run_tlc_simulate
                    try:
                        sim_traces = run_tlc_simulate(
                            dest_tla, dest_cfg,
                            tools_dir=ctx.tools_dir,
                            num_traces=10,
                        )
                        if sim_traces:
                            traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
                            traces_path.write_text(json.dumps(sim_traces, indent=2))
                            log_fn(f"  {len(sim_traces)} simulation traces saved: {traces_path}")
                    except Exception as e:
                        log_fn(f"  Warning: simulation trace generation failed: {e}")

                    return LoopResult.PASS, dest_tla

            elif status.result == LoopResult.FAIL:
                log_fn(f"FAIL — {status.error}")
                return LoopResult.FAIL, None

            else:  # RETRY
                # Collect counterexample traces
                if status.counterexample is not None:
                    from registry.bridge import counterexample_to_tlc_trace
                    tlc_trace = counterexample_to_tlc_trace(status.counterexample)
                    if tlc_trace is not None:
                        collected_traces.append({
                            "invariant_violated": tlc_trace.invariant_violated,
                            "states": tlc_trace.states,
                        })

                current_prompt = build_retry_prompt(
                    initial_prompt, attempt, status,
                    previous_response=response,
                )
                log_fn(f"RETRY — {status.error}")

        log_fn(f"Exhausted {max_retries} attempts")
        return LoopResult.FAIL, None
    finally:
        await safe_disconnect(client)


def _build_prompt(gwt_node: Any, prompt_ctx: str, template_text: str,
                  context_text: str = "") -> str:
    """Build the initial LLM prompt from GWT node + registry context."""
    context_section = ""
    if context_text:
        context_section = f"""
## Supplementary Context
The following specification document describes the detailed steps, state variables,
invariants, and terminal conditions for this behavior. Use it as your primary
guide for what the PlusCal specification must model:

{context_text}
"""

    return f"""Generate a PlusCal specification for the following behavior:

Given: {gwt_node.given}
When: {gwt_node.when}
Then: {gwt_node.then}
{context_section}
## Registry Context
{prompt_ctx}

## PlusCal Template
Use this as a structural reference:
{template_text}

Generate a complete PlusCal algorithm wrapped in a TLA+ module.
Include invariants that verify the "Then" condition holds.

## PlusCal Rules (CRITICAL — pcal.trans will reject violations)

- Do NOT use `Done` as a label — it is reserved by pcal.trans. Use `Finish`, `Complete`, or `Terminate` instead.
- Do NOT use decorative comment lines with long runs of = or - signs (like TLA+ comment separators). They confuse the module boundary parser.
- Every `if` with multiple assignments in either branch needs a label at the join point.
- Output ONLY the TLA+ module — no markdown fencing, no explanation text.
"""
