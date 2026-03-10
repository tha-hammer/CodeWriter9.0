╔════════════════════════════════════════════════════════════════╗
║  PHASE 5A: Connect the Trace Pipeline                         ║
╚════════════════════════════════════════════════════════════════╝

## Overview

**Goal**: Make `CounterexampleTrace` → `TlcTrace` conversion work so `translate_traces()` can populate `test_scenarios`. **Additionally (v5):** Load and format TLC simulation traces as the primary context for Phase 5C test generation.

## Changes Required

### 1. `python/registry/bridge.py` — `counterexample_to_tlc_trace()`

```python
def counterexample_to_tlc_trace(ce: "CounterexampleTrace") -> "TlcTrace | None":
    """Convert a CounterexampleTrace from one_shot_loop to a TlcTrace for bridge.

    CounterexampleTrace.states is list[dict] with keys:
        state_num: int, label: str, vars: dict[str, str]
    TlcTrace expects:
        invariant_violated: str, states: list[dict[str, str]]

    Returns None if the counterexample has no states or no violated invariant.
    """
    from registry.one_shot_loop import CounterexampleTrace

    if not ce.states or not ce.violated_invariant:
        return None

    # Flatten: CounterexampleTrace.states[i]["vars"] → TlcTrace.states[i]
    tlc_states = []
    for state in ce.states:
        vars_dict = state.get("vars", {})
        # TlcTrace.states expects dict[str, str] — already in that form
        tlc_states.append(vars_dict)

    return TlcTrace(
        invariant_violated=ce.violated_invariant,
        states=tlc_states,
    )
```

### 2. `python/registry/loop_runner.py` — Collect traces during loop

After a successful TLC pass, also try to generate example traces using TLC's `-simulate` flag. On TLC failures (retries), collect the counterexample traces.

```python
# In run_loop(), after process_response():
collected_traces: list[TlcTrace] = []

# ... inside the retry branch:
if status.counterexample is not None:
    from registry.bridge import counterexample_to_tlc_trace
    tlc_trace = counterexample_to_tlc_trace(status.counterexample)
    if tlc_trace is not None:
        collected_traces.append(tlc_trace)

# ... on PASS, save collected traces alongside the spec:
if collected_traces:
    import json
    traces_path = ctx.spec_dir / f"{gwt_id}_traces.json"
    traces_data = [{"invariant_violated": t.invariant_violated, "states": t.states}
                   for t in collected_traces]
    traces_path.write_text(json.dumps(traces_data, indent=2))
```

### 3. `python/registry/cli.py` — `cmd_bridge()` update

Update `cmd_bridge()` to load traces and pass them to `run_bridge()`:

```python
# In cmd_bridge(), before run_bridge():

# Load counterexample traces (from retry failures)
traces_path = ctx.spec_dir / f"{gwt_id}_traces.json"
traces = []
if traces_path.exists():
    from registry.bridge import TlcTrace
    traces_data = json.loads(traces_path.read_text())
    traces = [TlcTrace(**td) for td in traces_data]

result = run_bridge(tla_text, traces=traces)

# Add test_scenarios to artifacts output:
artifacts["test_scenarios"] = [
    {"name": s.name, "setup": s.setup, "steps": s.steps,
     "expected_outcome": s.expected_outcome, "invariant_tested": s.invariant_tested}
    for s in result.test_scenarios
]

# v5: Load simulation traces (primary context for gen-tests)
sim_traces_path = ctx.spec_dir / f"{gwt_id}_sim_traces.json"
if sim_traces_path.exists():
    artifacts["simulation_traces"] = json.loads(sim_traces_path.read_text())
else:
    artifacts["simulation_traces"] = []
```

### 4. `python/registry/traces.py` (new, v5) — Simulation trace types and prompt formatting

> **v5 addition:** Structured types for simulation traces and a formatter that produces
> the ranked-context prompt section. Simulation traces are the PRIMARY input for Phase 5C —
> they shift the LLM's job from "design test scenarios" to "translate verified traces."

```python
"""Simulation trace types and prompt formatting for test generation.

v5: TLC simulation traces are pre-verified concrete execution paths through
the state space. Each trace says: "starting from THIS state, applying THESE
actions, produces THIS result, and ALL invariants hold at every step."
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationTrace:
    """A TLC simulation trace — verified concrete scenario.

    Unlike CounterexampleTrace (which represents a violation), simulation
    traces represent VALID executions where all invariants hold.
    """
    states: list[dict[str, Any]]  # [{state_num, label, vars: {name: value}}]
    invariants_verified: list[str] = field(default_factory=list)

    @property
    def init_state(self) -> dict[str, str]:
        """The initial state — defines the test fixture."""
        return self.states[0]["vars"] if self.states else {}

    @property
    def final_state(self) -> dict[str, str]:
        """The final state — defines expected assertions."""
        return self.states[-1]["vars"] if self.states else {}

    @property
    def actions(self) -> list[str]:
        """The action sequence (labels after Init) — defines API calls."""
        return [s["label"] for s in self.states[1:]]

    @property
    def step_count(self) -> int:
        return len(self.states)


def format_traces_for_prompt(
    traces: list[SimulationTrace],
    invariant_names: list[str],
) -> str:
    """Format simulation traces as concrete verified scenarios for LLM prompt.

    This is the HIGHEST-RANKED context in the test generation prompt stack.
    Each trace is a pre-verified test case — the LLM translates (not invents).

    Context stack ranking (see Phase 5C):
      1. THIS — simulation traces (the WHAT)
      2. Python API signatures (the HOW)
      3. GWT + bridge artifacts + compiler hints (the WHY)
      4. Verified TLA+ spec (the FULL PICTURE)
      5. Structural patterns (the FORM)
    """
    sections = ["## Concrete Verified Scenarios\n"]
    sections.append(
        "Each trace below was generated by TLC from the verified model. "
        "ALL invariants hold at EVERY state. These are your test cases — "
        "translate each trace into Python API calls.\n"
    )

    for i, trace in enumerate(traces, 1):
        sections.append(
            f"### Trace {i} ({trace.step_count} steps, "
            f"tests {', '.join(invariant_names)})"
        )
        sections.append(f"Actions: {' → '.join(trace.actions)}\n")

        for state in trace.states:
            sections.append(f"State {state['state_num']}: <{state['label']}>")
            for var, val in state["vars"].items():
                sections.append(f"  /\\ {var} = {val}")
            sections.append("")

    return "\n".join(sections)


def load_simulation_traces(
    traces_data: list[list[dict[str, Any]]],
    invariant_names: list[str] | None = None,
) -> list[SimulationTrace]:
    """Load simulation traces from JSON data (as saved by cw9 loop).

    Args:
        traces_data: Raw JSON — list of traces, each a list of state dicts
        invariant_names: Names of invariants verified by the spec
    """
    return [
        SimulationTrace(
            states=trace_states,
            invariants_verified=invariant_names or [],
        )
        for trace_states in traces_data
    ]
```

## Tests

### Tests for trace conversion

```python
class TestTraceConversion:
    def test_counterexample_to_tlc_trace(self):
        from registry.one_shot_loop import CounterexampleTrace
        from registry.bridge import counterexample_to_tlc_trace

        ce = CounterexampleTrace(
            raw_trace="...",
            states=[
                {"state_num": 1, "label": "Init", "vars": {"x": "0", "dirty": "FALSE"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1", "dirty": "TRUE"}},
            ],
            violated_invariant="ValidState",
        )
        tlc = counterexample_to_tlc_trace(ce)
        assert tlc is not None
        assert tlc.invariant_violated == "ValidState"
        assert len(tlc.states) == 2
        assert tlc.states[0] == {"x": "0", "dirty": "FALSE"}

    def test_empty_counterexample_returns_none(self):
        from registry.one_shot_loop import CounterexampleTrace
        from registry.bridge import counterexample_to_tlc_trace

        ce = CounterexampleTrace(raw_trace="", states=[], violated_invariant=None)
        assert counterexample_to_tlc_trace(ce) is None
```

### Tests for simulation traces (v5)

```python
class TestSimulationTraces:
    """v5: Tests for SimulationTrace and format_traces_for_prompt."""

    def test_trace_properties(self):
        from registry.traces import SimulationTrace
        trace = SimulationTrace(
            states=[
                {"state_num": 1, "label": "Init", "vars": {"x": "0", "y": "{}"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1", "y": "{a}"}},
                {"state_num": 3, "label": "Done", "vars": {"x": "2", "y": "{a, b}"}},
            ],
            invariants_verified=["Inv1", "Inv2"],
        )
        assert trace.init_state == {"x": "0", "y": "{}"}
        assert trace.final_state == {"x": "2", "y": "{a, b}"}
        assert trace.actions == ["Step", "Done"]
        assert trace.step_count == 3

    def test_format_traces_for_prompt(self):
        from registry.traces import SimulationTrace, format_traces_for_prompt
        traces = [
            SimulationTrace(
                states=[
                    {"state_num": 1, "label": "Init", "vars": {"nodes": "{a,b,c}"}},
                    {"state_num": 2, "label": "Query", "vars": {"affected": "{a,b}"}},
                ],
            ),
        ]
        result = format_traces_for_prompt(traces, ["NoFalsePositives", "ValidState"])
        assert "Concrete Verified Scenarios" in result
        assert "Trace 1" in result
        assert "Init → Query" in result  # action label is from state 2
        assert "NoFalsePositives" in result
        assert "/\\ nodes = {a,b,c}" in result

    def test_load_simulation_traces(self):
        from registry.traces import load_simulation_traces
        raw = [
            [
                {"state_num": 1, "label": "Init", "vars": {"x": "0"}},
                {"state_num": 2, "label": "Step", "vars": {"x": "1"}},
            ],
            [
                {"state_num": 1, "label": "Init", "vars": {"x": "0"}},
            ],
        ]
        traces = load_simulation_traces(raw, invariant_names=["Inv1"])
        assert len(traces) == 2
        assert traces[0].step_count == 2
        assert traces[1].step_count == 1
        assert traces[0].invariants_verified == ["Inv1"]

    def test_empty_trace(self):
        from registry.traces import SimulationTrace
        trace = SimulationTrace(states=[])
        assert trace.init_state == {}
        assert trace.final_state == {}
        assert trace.actions == []
        assert trace.step_count == 0
```

## Success Criteria

### Automated:
- [x] `python3 -m pytest tests/test_trace_conversion.py -v` — trace pipeline tests pass
- [x] `python3 -m pytest tests/test_simulation_traces.py -v` — 4 simulation trace type tests pass (v5)
