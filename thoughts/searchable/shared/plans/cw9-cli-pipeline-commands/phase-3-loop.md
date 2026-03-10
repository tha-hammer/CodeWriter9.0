╔═══════════════════════════════════════╗
║  PHASE 3: cw9 loop <gwt-id>          ║
╚═══════════════════════════════════════╝

## Overview

Runs the LLM → PlusCal → TLC pipeline for a single GWT behavior. The GWT node must already exist in the DAG (registered via `register_gwt()` or extracted by `cw9 extract`). The loop:

1. Loads the DAG, finds the GWT node
2. Builds a prompt from the GWT's `given`/`when`/`then` + registry context
3. Calls Claude Agent SDK to generate PlusCal
4. Compiles PlusCal → runs TLC model checker
5. On PASS: saves spec to `.cw9/specs/<gwt-id>.tla` + `.cfg`
6. **On PASS: runs TLC `-simulate num=10` to generate concrete execution traces** (v5)
7. On failure: retries with counterexample feedback

> **v5 addition (step 6):** After TLC verifies a model with N distinct states and passes,
> it has visited every reachable state and confirmed every invariant holds at each one.
> We previously captured only "pass" and a state count — throwing away the state space.
> TLC's `-simulate` mode outputs concrete execution traces through the state space on
> passing models. Each trace is a pre-verified test case: "starting from THIS state,
> applying THESE actions, produces THIS result, and ALL invariants hold." These traces
> become the primary input for Phase 5C's test generation loop.

## Changes Required

### 1. `python/registry/loop_runner.py` (new) — Common loop logic

> **v3 fix (Issue #3):** Three bugs fixed from v2:
> 1. `process_response()` requires `(llm_response, module_name, cfg_text)` — v2 called it
>    with `(response, gwt_id)` missing `cfg_text`.
> 2. `LoopStatus` has no `retry_prompt` field — retry prompts must be built from
>    `status.counterexample` and `status.error`, following the pattern in existing loop scripts.
> 3. The `module_name` should be derived from the GWT's corresponding TLA+ module, not the
>    gwt_id directly. For initial generation it's derived from the GWT name.

```python
"""Common loop runner — LLM → PlusCal → TLC pipeline."""

import asyncio
import os
import shutil
from pathlib import Path

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

    NOTE: Intentionally uses 3-arg (initial_prompt, attempt, LoopStatus) arity
    rather than the 5-arg pattern in existing run_*_loop.py scripts. LoopStatus
    wraps the same information more cleanly.

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
    cfg_text = f"SPECIFICATION Spec\n"

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

                # v5: Generate simulation traces from the verified model
                from registry.one_shot_loop import run_tlc_simulate
                sim_traces = run_tlc_simulate(
                    dest_tla, dest_cfg,
                    tools_dir=ctx.engine_root / "tools",
                    num_traces=10,
                )
                if sim_traces:
                    import json
                    traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
                    traces_path.write_text(json.dumps(sim_traces, indent=2))
                    log_fn(f"  {len(sim_traces)} simulation traces saved: {traces_path}")

                return LoopResult.PASS, dest_tla

        elif status.result == LoopResult.FAIL:
            log_fn(f"FAIL — {status.error}")
            return LoopResult.FAIL, None

        else:  # RETRY
            current_prompt = build_retry_prompt(initial_prompt, attempt, status)
            log_fn(f"RETRY — {status.error}")

    log_fn(f"Exhausted {max_retries} attempts")
    return LoopResult.FAIL, None


def _build_prompt(gwt_node, prompt_ctx: str, template_text: str) -> str:
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
```

**Note**: The exact prompt construction will be refined during implementation by studying `run_change_prop_loop.py:333-411`. The skeleton above shows the structure.

### 1b. `python/registry/one_shot_loop.py` — `run_tlc_simulate()` (v5 addition)

> **v5:** After TLC verification passes, run TLC in `-simulate` mode to generate concrete
> execution traces through the verified state space. These traces ARE the test cases for
> Phase 5C. The format is identical to counterexample traces minus the violation header,
> so the same `_STATE_HEADER_RE` and `_VAR_ASSIGN_RE` regexes parse both.

```python
def run_tlc_simulate(
    tla_path: str | Path,
    cfg_path: str | Path | None = None,
    tools_dir: str | Path | None = None,
    num_traces: int = 10,
) -> list[list[dict[str, Any]]]:
    """Run TLC in -simulate mode to generate concrete traces from a passing model.

    Each trace is a sequence of states through the verified state space.
    All invariants hold at every state in every trace.

    Returns list of traces, where each trace is a list of state dicts
    with keys: state_num, label, vars.
    """
    jar = _find_tla2tools(tools_dir)
    tla_path = Path(tla_path)

    cmd = [
        "java", "-XX:+UseParallelGC",
        "-cp", jar,
        "tlc2.TLC",
        str(tla_path),
        "-simulate", f"num={num_traces}",
        "-nowarning",
    ]
    if cfg_path:
        cmd.extend(["-config", str(cfg_path)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    raw = result.stdout + result.stderr

    return parse_simulation_traces(raw)


def parse_simulation_traces(raw: str) -> list[list[dict[str, Any]]]:
    """Parse TLC -simulate output into structured traces.

    Reuses the same _STATE_HEADER_RE and _VAR_ASSIGN_RE regexes as
    parse_counterexample(). Traces are delimited by the State 1 restart
    pattern — each time we see State 1 after already having states,
    we know a new trace has begun.
    """
    traces: list[list[dict[str, Any]]] = []
    current_trace: list[dict[str, Any]] = []
    current_state: dict[str, Any] | None = None

    for line in raw.split("\n"):
        line = line.strip()

        header_m = _STATE_HEADER_RE.match(line)
        if header_m:
            state_num = int(header_m.group(1))
            # New trace starts at State 1
            if state_num == 1 and current_trace:
                if current_state:
                    current_trace.append(current_state)
                traces.append(current_trace)
                current_trace = []
            elif current_state:
                current_trace.append(current_state)

            current_state = {
                "state_num": state_num,
                "label": header_m.group(2),
                "vars": {},
            }
            continue

        if current_state is not None:
            var_m = _VAR_ASSIGN_RE.match(line)
            if var_m:
                current_state["vars"][var_m.group(1)] = var_m.group(2).strip()

    if current_state:
        current_trace.append(current_state)
    if current_trace:
        traces.append(current_trace)

    return traces
```

### 2. `python/registry/cli.py` — `cmd_loop()`

```python
def cmd_loop(args: argparse.Namespace) -> int:
    import asyncio

    target = Path(args.target_dir).resolve()
    if not (target / ".cw9").exists():
        print(f"No .cw9/ found in {target}", file=sys.stderr)
        return 1

    from registry.loop_runner import run_loop
    from registry.one_shot_loop import LoopResult

    ctx = ProjectContext.from_target(target)
    result, spec_path = asyncio.run(run_loop(
        ctx=ctx,
        gwt_id=args.gwt_id,
        max_retries=args.max_retries,
    ))

    if result == LoopResult.PASS:
        print(f"Verified: {spec_path}")
        return 0
    else:
        print("Loop failed.", file=sys.stderr)
        return 1
```

### 3. Argparse wiring

```python
p_loop = sub.add_parser("loop", help="Run LLM → PlusCal → TLC for a GWT behavior")
p_loop.add_argument("gwt_id", help="GWT behavior ID (e.g., gwt-0024)")
p_loop.add_argument("target_dir", nargs="?", default=".")
p_loop.add_argument("--max-retries", type=int, default=5)
```

## Tests

```python
class TestLoop:
    def test_loop_no_cw9_fails(self, target_dir):
        rc = main(["loop", "gwt-0001", str(target_dir)])
        assert rc == 1

    def test_loop_missing_gwt_fails(self, target_dir, capsys):
        main(["init", str(target_dir)])
        main(["extract", str(target_dir)])
        rc = main(["loop", "gwt-nonexistent", str(target_dir)])
        assert rc == 1


class TestSimulationTraceParser:
    """v5: Tests for parse_simulation_traces()."""

    def test_parses_single_trace(self):
        from registry.one_shot_loop import parse_simulation_traces
        raw = (
            "State 1: <Init>\n"
            "/\\ current_state = \"idle\"\n"
            "/\\ candidates = {}\n"
            "\n"
            "State 2: <SelectNode>\n"
            "/\\ current_state = \"propagating\"\n"
            "/\\ candidates = {\"a\"}\n"
        )
        traces = parse_simulation_traces(raw)
        assert len(traces) == 1
        assert len(traces[0]) == 2
        assert traces[0][0]["label"] == "Init"
        assert traces[0][0]["vars"]["current_state"] == '"idle"'
        assert traces[0][1]["label"] == "SelectNode"

    def test_parses_multiple_traces(self):
        from registry.one_shot_loop import parse_simulation_traces
        raw = (
            "State 1: <Init>\n"
            "/\\ x = 0\n"
            "State 2: <Step>\n"
            "/\\ x = 1\n"
            "\n"
            "State 1: <Init>\n"
            "/\\ x = 0\n"
            "State 2: <Step>\n"
            "/\\ x = 2\n"
            "State 3: <Done>\n"
            "/\\ x = 3\n"
        )
        traces = parse_simulation_traces(raw)
        assert len(traces) == 2
        assert len(traces[0]) == 2
        assert len(traces[1]) == 3
        assert traces[1][2]["vars"]["x"] == "3"

    def test_empty_output_returns_empty(self):
        from registry.one_shot_loop import parse_simulation_traces
        assert parse_simulation_traces("") == []
        assert parse_simulation_traces("Model checking completed.\n") == []
```

Full LLM integration is manual: `cw9 extract && cw9 loop gwt-0024`

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_cli.py::TestLoop -v` — error-path tests pass
- [x] `python3 -m pytest tests/test_cli.py::TestSimulationTraceParser -v` — 3 trace parser tests pass (v5)
- [x] No import errors from `registry.loop_runner`

### Manual:
- [ ] `cw9 loop gwt-0021` — completes TLC verification, saves `.tla`/`.cfg`
- [ ] Session logs appear in `.cw9/sessions/gwt-0021_attempt*.txt`
- [ ] Simulation traces saved to `.cw9/specs/gwt-0021_sim_traces.json` (v5)
