"""Common loop runner — LLM → PlusCal → TLC pipeline."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

os.environ.pop("CLAUDECODE", None)
import claude_agent_sdk

from registry.context import ProjectContext
from registry.one_shot_loop import (
    OneShotLoop, query_context, format_prompt_context,
    LoopResult, LoopStatus, extract_pluscal,
)


async def call_llm(prompt: str, system_prompt: str | None = None) -> str:
    """Single-turn LLM call via Claude Agent SDK (account-level auth).

    NOTE: No per-call timeout — matches existing run_*_loop.py pattern.
    Could hang if API is unresponsive. Known limitation.
    """
    options = claude_agent_sdk.ClaudeAgentOptions(
        allowed_tools=[],
        system_prompt=system_prompt or (
            "You are a TLA+/PlusCal expert. Generate formally verifiable "
            "PlusCal specifications from behavioral requirements."
        ),
        max_turns=1,
        model="claude-sonnet-4-20250514",
    )
    result_text = []
    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        if isinstance(message, claude_agent_sdk.AssistantMessage):
            for block in message.content:
                if isinstance(block, claude_agent_sdk.TextBlock):
                    result_text.append(block.text)
        elif isinstance(message, claude_agent_sdk.ResultMessage):
            if message.result:
                result_text.append(message.result)
    return "\n".join(result_text)


def build_retry_prompt(
    initial_prompt: str,
    attempt: int,
    status: LoopStatus,
) -> str:
    """Build a retry prompt from the LoopStatus counterexample and error.

    Follows the pattern from existing run_*_loop.py scripts:
    original prompt + error context + counterexample trace.
    """
    parts = [initial_prompt, "\n\n## RETRY — Previous Attempt Failed\n"]

    parts.append(f"Attempt {attempt} failed.")

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

    parts.append("\n\nPlease fix the specification to satisfy all invariants.")
    return "\n".join(parts)


async def run_loop(
    ctx: ProjectContext,
    gwt_id: str,
    max_retries: int = 5,
    log_fn=print,
) -> tuple[LoopResult, Path | None]:
    """Run the LLM → PlusCal → TLC loop for a GWT behavior.

    The GWT must already exist in the DAG (via register_gwt() or extract).

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

    initial_prompt = _build_prompt(gwt_node, prompt_ctx, template_text)
    current_prompt = initial_prompt

    # Derive module_name from GWT name (e.g., "validation_runs" -> "ValidationRuns")
    module_name = "".join(w.capitalize() for w in gwt_node.name.split("_"))
    if not module_name:
        module_name = gwt_id.replace("-", "_")

    # Default cfg_text for TLC configuration
    cfg_text = "SPECIFICATION Spec\n"

    # Collect counterexample traces during retries
    collected_traces = []

    for attempt in range(1, max_retries + 1):
        log_fn(f"Attempt {attempt}/{max_retries}")

        response = await call_llm(current_prompt)

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

            current_prompt = build_retry_prompt(initial_prompt, attempt, status)
            log_fn(f"RETRY — {status.error}")

    log_fn(f"Exhausted {max_retries} attempts")
    return LoopResult.FAIL, None


def _build_prompt(gwt_node: Any, prompt_ctx: str, template_text: str) -> str:
    """Build the initial LLM prompt from GWT node + registry context."""
    return f"""Generate a PlusCal specification for the following behavior:

Given: {gwt_node.given}
When: {gwt_node.when}
Then: {gwt_node.then}

## Registry Context
{prompt_ctx}

## PlusCal Template
Use this as a structural reference:
{template_text}

Generate a complete PlusCal algorithm wrapped in a TLA+ module.
Include invariants that verify the "Then" condition holds.
"""
