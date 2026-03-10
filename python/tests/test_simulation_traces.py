"""Tests for SimulationTrace types and prompt formatting (Phase 5A v5)."""

from registry.traces import SimulationTrace, format_traces_for_prompt, load_simulation_traces


class TestSimulationTraces:
    def test_trace_properties(self):
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
        assert "Query" in result  # actions are labels after Init
        assert "NoFalsePositives" in result
        assert "/\\ nodes = {a,b,c}" in result

    def test_load_simulation_traces(self):
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
        trace = SimulationTrace(states=[])
        assert trace.init_state == {}
        assert trace.final_state == {}
        assert trace.actions == []
        assert trace.step_count == 0
