"""Tests for the One-Shot Loop (Phase 3)."""

import textwrap

import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind
from registry.one_shot_loop import (
    ContextBundle,
    CounterexampleTrace,
    LoopResult,
    LoopState,
    LoopStatus,
    OneShotLoop,
    TLCResult,
    extract_pluscal,
    format_prompt_context,
    parse_counterexample,
    query_context,
    route_result,
    translate_counterexample,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_dag() -> RegistryDag:
    """Create a small DAG with behavior nodes and transitive deps."""
    dag = RegistryDag()
    # Behavior
    dag.add_node(Node.behavior(
        "gwt-test-1", "test_behavior",
        "a test condition",
        "something happens",
        "result is correct",
    ))
    # Resources that the behavior depends on
    dag.add_node(Node.resource("res-a", "resource_a", description="Resource A"))
    dag.add_node(Node.resource("res-b", "resource_b", description="Resource B"))
    dag.add_node(Node(
        id="tpl-test", kind=NodeKind.SPEC, name="test_template",
        description="A test template", path="templates/pluscal/test.tla",
    ))
    dag.add_node(Node.resource(
        "schema-test", "test_schema",
        description="A test schema", schema="test_schema.json",
    ))
    # Edges: behavior -> resources -> transitive deps
    dag.add_edge(Edge("gwt-test-1", "res-a", EdgeType.REFERENCES))
    dag.add_edge(Edge("res-a", "res-b", EdgeType.DEPENDS_ON))
    dag.add_edge(Edge("res-a", "tpl-test", EdgeType.REFERENCES))
    dag.add_edge(Edge("res-b", "schema-test", EdgeType.DEPENDS_ON))
    return dag


# ---------------------------------------------------------------------------
# Context Query Tests
# ---------------------------------------------------------------------------

class TestContextQuery:
    """Tests for registry context query with transitive deps."""

    def test_query_returns_behavior_node(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        assert bundle.behavior is not None
        assert bundle.behavior.id == "gwt-test-1"
        assert bundle.behavior.given == "a test condition"

    def test_query_returns_transitive_deps(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        dep_ids = [n.id for n in bundle.transitive_deps]
        # gwt-test-1 -> res-a -> res-b -> schema-test
        #                      -> tpl-test
        assert "res-a" in dep_ids
        assert "res-b" in dep_ids
        assert "tpl-test" in dep_ids
        assert "schema-test" in dep_ids

    def test_query_returns_templates(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        assert "templates/pluscal/test.tla" in bundle.templates

    def test_query_returns_schemas(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        assert "test_schema.json" in bundle.schemas

    def test_query_returns_edges(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        assert len(bundle.edges) > 0

    def test_query_unknown_behavior_raises(self):
        dag = _make_dag()
        with pytest.raises(ValueError, match="not found"):
            query_context(dag, "nonexistent")

    def test_format_prompt_context(self):
        dag = _make_dag()
        bundle = query_context(dag, "gwt-test-1")
        prompt = format_prompt_context(bundle)
        assert "gwt-test-1" in prompt
        assert "a test condition" in prompt
        assert "Transitive Dependencies" in prompt


# ---------------------------------------------------------------------------
# PlusCal Extraction Tests
# ---------------------------------------------------------------------------

class TestPlusCalExtraction:
    """Tests for extracting PlusCal from various LLM response formats."""

    def test_extract_from_fenced_tla_block(self):
        response = textwrap.dedent("""\
            Here's the PlusCal spec:

            ```tla
            (* --algorithm TestAlgo
            variables x = 0;
            begin
                Step1:
                    x := x + 1;
            end algorithm; *)
            ```

            This models the behavior...
        """)
        fragment = extract_pluscal(response)
        assert fragment is not None
        assert "--algorithm TestAlgo" in fragment
        assert "end algorithm" in fragment

    def test_extract_from_fenced_pluscal_block(self):
        response = textwrap.dedent("""\
            ```pluscal
            (* --algorithm Another
            variables y = 0;
            begin
                Loop:
                    y := y + 1;
            end algorithm; *)
            ```
        """)
        fragment = extract_pluscal(response)
        assert fragment is not None
        assert "--algorithm Another" in fragment

    def test_extract_from_generic_fenced_block(self):
        response = textwrap.dedent("""\
            Here is the algorithm:

            ```
            (* --algorithm Generic
            variables z = 0;
            begin
                Start:
                    z := z + 1;
            end algorithm; *)
            ```
        """)
        fragment = extract_pluscal(response)
        assert fragment is not None
        assert "--algorithm Generic" in fragment

    def test_extract_bare_algorithm(self):
        response = textwrap.dedent("""\
            The specification follows. Note the two-phase model.

            (* --algorithm Bare
            variables state = "init";
            begin
                Init:
                    state := "running";
            end algorithm; *)

            This satisfies the invariant.
        """)
        fragment = extract_pluscal(response)
        assert fragment is not None
        assert "--algorithm Bare" in fragment

    def test_extract_returns_none_for_no_pluscal(self):
        response = "This response contains no PlusCal code at all."
        fragment = extract_pluscal(response)
        assert fragment is None

    def test_extract_returns_none_for_partial_algorithm(self):
        response = "Here is --algorithm but no closing marker present."
        fragment = extract_pluscal(response)
        assert fragment is None


# ---------------------------------------------------------------------------
# Counterexample Translation Tests
# ---------------------------------------------------------------------------

class TestCounterexampleTranslation:
    """Tests for translating TLC counterexamples to PlusCal concepts."""

    SAMPLE_COUNTEREXAMPLE = textwrap.dedent("""\
        Error: Invariant SafetyInvariant is violated.
        Error: The behavior up to this point is:
        State 1: <Initial predicate>
        /\\ current_state = "idle"
        /\\ pc = [self \\in ProcSet |-> "MainLoop"]
        /\\ step_count = 0

        State 2: <MainLoop line 100>
        /\\ current_state = "running"
        /\\ pc = [self \\in ProcSet |-> "Step1"]
        /\\ step_count = 1

        State 3: <Step1 line 110>
        /\\ current_state = "error"
        /\\ pc = [self \\in ProcSet |-> "Done"]
        /\\ step_count = 2
    """)

    def test_parse_counterexample_extracts_states(self):
        trace = parse_counterexample(self.SAMPLE_COUNTEREXAMPLE)
        assert len(trace.states) == 3

    def test_parse_counterexample_extracts_invariant(self):
        trace = parse_counterexample(self.SAMPLE_COUNTEREXAMPLE)
        assert trace.violated_invariant == "SafetyInvariant"

    def test_parse_counterexample_extracts_variables(self):
        trace = parse_counterexample(self.SAMPLE_COUNTEREXAMPLE)
        assert trace.states[0]["vars"]["current_state"] == '"idle"'
        assert trace.states[1]["vars"]["step_count"] == "1"

    def test_translate_counterexample_produces_summary(self):
        trace = parse_counterexample(self.SAMPLE_COUNTEREXAMPLE)
        summary = translate_counterexample(trace)
        assert "INVARIANT VIOLATED: SafetyInvariant" in summary
        assert "Step 1:" in summary
        assert "Step 2:" in summary
        assert "Step 3:" in summary

    def test_translate_with_variable_descriptions(self):
        trace = parse_counterexample(self.SAMPLE_COUNTEREXAMPLE)
        var_desc = {"current_state": "lifecycle phase"}
        summary = translate_counterexample(trace, var_desc)
        assert "lifecycle phase" in summary

    def test_translate_empty_trace(self):
        trace = CounterexampleTrace(raw_trace="")
        summary = translate_counterexample(trace)
        assert "No states" in summary


# ---------------------------------------------------------------------------
# Pass/Retry/Fail Routing Tests
# ---------------------------------------------------------------------------

class TestRouting:
    """Tests for pass/retry/fail routing logic."""

    def test_pass_on_success(self):
        tlc = TLCResult(success=True, states_found=100, states_distinct=50)
        result, msg = route_result(tlc, consecutive_failures=0)
        assert result == LoopResult.PASS
        assert "passed" in msg.lower()

    def test_pass_resets_failures(self):
        tlc = TLCResult(success=True, states_found=100, states_distinct=50)
        result, _ = route_result(tlc, consecutive_failures=5)
        # Even with prior failures, a pass is a pass
        assert result == LoopResult.PASS

    def test_retry_on_first_failure(self):
        tlc = TLCResult(
            success=False,
            counterexample="State 1: ...",
            error_message="Invariant X violated",
        )
        result, msg = route_result(tlc, consecutive_failures=0)
        assert result == LoopResult.RETRY
        assert "attempt 1" in msg

    def test_fail_on_second_consecutive_failure(self):
        tlc = TLCResult(
            success=False,
            error_message="Invariant X violated",
        )
        result, msg = route_result(tlc, consecutive_failures=1)
        assert result == LoopResult.FAIL
        assert "inconsistency" in msg.lower()

    def test_fail_on_third_consecutive_failure(self):
        tlc = TLCResult(success=False, error_message="err")
        result, msg = route_result(tlc, consecutive_failures=2)
        assert result == LoopResult.FAIL
        assert "not retry" in msg.lower()

    def test_routing_is_deterministic(self):
        """Same inputs always produce same outputs."""
        tlc = TLCResult(success=False, error_message="err")
        r1, m1 = route_result(tlc, 0)
        r2, m2 = route_result(tlc, 0)
        assert r1 == r2
        assert m1 == m2

    def test_two_failures_then_requirements_inconsistency(self):
        """The key GWT: two consecutive failures -> requirements inconsistency."""
        tlc_fail = TLCResult(success=False, error_message="inv violated")

        # First failure -> retry
        r1, _ = route_result(tlc_fail, consecutive_failures=0)
        assert r1 == LoopResult.RETRY

        # Second failure -> fail (requirements inconsistency)
        r2, msg = route_result(tlc_fail, consecutive_failures=1)
        assert r2 == LoopResult.FAIL
        assert "inconsistency" in msg.lower()


# ---------------------------------------------------------------------------
# Integration: DAG self-registration Tests
# ---------------------------------------------------------------------------

class TestSelfRegistration:
    """Verify Phase 3 nodes and edges exist in the extracted DAG."""

    @pytest.fixture(autouse=True)
    def setup_dag(self):
        from registry.extractor import SchemaExtractor
        import os
        schema_dir = os.path.join(os.path.dirname(__file__), "..", "..", "schema")
        self.extractor = SchemaExtractor(schema_dir=schema_dir)
        self.dag = self.extractor.extract()

    def test_phase3_gwt_nodes_exist(self):
        assert "gwt-0005" in self.dag.nodes
        assert "gwt-0006" in self.dag.nodes
        assert "gwt-0007" in self.dag.nodes

    def test_phase3_spec_node_exists(self):
        assert "tpl-0007" in self.dag.nodes
        node = self.dag.nodes["tpl-0007"]
        assert "one_shot_loop" in node.name

    def test_phase3_module_nodes_exist(self):
        assert "loop-0001" in self.dag.nodes
        assert "loop-0002" in self.dag.nodes
        assert "loop-0003" in self.dag.nodes

    def test_phase3_requirement_exists(self):
        assert "req-0002" in self.dag.nodes
        node = self.dag.nodes["req-0002"]
        assert "one-shot loop" in node.text

    def test_spec_implements_template(self):
        edges = [e for e in self.dag.edges
                 if e.from_id == "tpl-0007" and e.to_id == "tpl-0002"]
        assert any(e.edge_type == EdgeType.IMPLEMENTS for e in edges)

    def test_spec_verifies_gwt_behaviors(self):
        for gwt in ("gwt-0005", "gwt-0006", "gwt-0007"):
            edges = [e for e in self.dag.edges
                     if e.from_id == "tpl-0007" and e.to_id == gwt]
            assert any(e.edge_type == EdgeType.VERIFIES for e in edges), \
                f"tpl-0007 should verify {gwt}"

    def test_loop_depends_on_composer(self):
        edges = [e for e in self.dag.edges
                 if e.from_id == "loop-0001" and e.to_id == "comp-0001"]
        assert any(e.edge_type == EdgeType.DEPENDS_ON for e in edges)

    def test_transitive_deps_include_all(self):
        """gwt-0005 should transitively reach closure (res-0003)."""
        result = self.dag.query_relevant("gwt-0005")
        assert "res-0003" in result.transitive_deps

    def test_dag_totals(self):
        """Phase 3 should add 8 nodes and 16 edges over Phase 2 (58/74)."""
        assert self.dag.node_count == 66
        assert self.dag.edge_count == 90
