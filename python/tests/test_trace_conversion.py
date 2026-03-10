"""Tests for CounterexampleTrace → TlcTrace conversion (Phase 5A)."""

import pytest

from registry.one_shot_loop import CounterexampleTrace
from registry.bridge import counterexample_to_tlc_trace


class TestTraceConversion:
    def test_counterexample_to_tlc_trace(self):
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
        ce = CounterexampleTrace(raw_trace="", states=[], violated_invariant=None)
        assert counterexample_to_tlc_trace(ce) is None
