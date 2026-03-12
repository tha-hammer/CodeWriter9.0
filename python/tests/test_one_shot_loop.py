"""Tests for the One-Shot Loop (Phase 3)."""

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

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
    TLCErrorClass,
    TLCResult,
    classify_tlc_error,
    extract_module_name,
    extract_pluscal,
    format_prompt_context,
    generate_cfg,
    parse_counterexample,
    parse_simulation_traces,
    query_context,
    route_result,
    run_tlc_simulate,
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
        self.extractor = SchemaExtractor(schema_dir=schema_dir, self_host=True)
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
        """Phase 8 adds 5 nodes (1 req + 3 GWT + 1 resource) and 22 edges over Phase 7 (91/176)."""
        assert self.dag.node_count == 96
        assert self.dag.edge_count == 198


# ---------------------------------------------------------------------------
# extract_module_name tests
# ---------------------------------------------------------------------------

class TestExtractModuleName:
    """Tests for extract_module_name() — parse MODULE name from TLA+ text."""

    def test_standard_module_header(self):
        spec = "---- MODULE FooBar ----\nEXTENDS Integers\n===="
        assert extract_module_name(spec) == "FooBar"

    def test_long_dashes(self):
        spec = "---------- MODULE MySpec ----------\nEXTENDS Naturals\n===="
        assert extract_module_name(spec) == "MySpec"

    def test_returns_none_for_no_module(self):
        assert extract_module_name("just some text") is None

    def test_returns_none_for_empty(self):
        assert extract_module_name("") is None

    def test_module_name_with_underscores(self):
        spec = "---- MODULE Control_Plane_Lifecycle ----\n===="
        assert extract_module_name(spec) == "Control_Plane_Lifecycle"

    def test_module_name_with_numbers(self):
        spec = "---- MODULE Phase1Changes ----\n===="
        assert extract_module_name(spec) == "Phase1Changes"


# ---------------------------------------------------------------------------
# generate_cfg tests
# ---------------------------------------------------------------------------

class TestGenerateCfg:
    """Tests for generate_cfg() — TLC .cfg auto-generation from TLA+ module text."""

    FULL_SPEC = textwrap.dedent("""\
        ---- MODULE TestSpec ----
        EXTENDS Integers, TLC

        CONSTANTS
            MaxSteps,
            MaxAttempts

        ASSUME MaxSteps \\in Nat /\\ MaxSteps > 0

        (* --algorithm TestAlgo

        variables phase = "idle", count = 0;

        define

            AllPhases ==
                {"idle", "running", "done"}

            TerminalPhases == {"done"}

            TypeInvariant ==
                /\\ phase \\in AllPhases
                /\\ count \\in 0..MaxSteps

            BoundedExecution == count <= MaxSteps

            SafetyGate ==
                phase = "done" => count > 0

        end define;

        fair process P = "p"
        begin L: skip;
        end process;

        end algorithm; *)

        ====
    """)

    SPEC_WITH_STANDARD_OPS = textwrap.dedent("""\
        ---- MODULE WithStandard ----
        EXTENDS Integers

        (* --algorithm Foo

        variables x = 0;

        define

            Init == x = 0

            Next == x' = x + 1

            Spec == Init /\\ [][Next]_x

            vars == <<x>>

            Fairness == WF_vars(Next)

            Termination == <>(x = 5)

            Liveness == []<>(x > 0)

            RealInvariant ==
                x >= 0

        end define;

        begin L: x := x + 1;

        end algorithm; *)

        ====
    """)

    BARE_SPEC = textwrap.dedent("""\
        ---- MODULE Bare ----
        EXTENDS Integers

        (* --algorithm Simple

        variables x = 0;

        begin L: x := 1;

        end algorithm; *)

        ====
    """)

    SPEC_NO_DEFINE = textwrap.dedent("""\
        ---- MODULE NoDefine ----
        EXTENDS Integers

        CONSTANTS N

        ASSUME N > 0

        (* --algorithm NoDef

        variables x = 0;

        begin L: x := 1;

        end algorithm; *)

        ====
    """)

    def test_constants_and_invariants_from_full_spec(self):
        """CONSTANTS get default values; invariants extracted, sets skipped."""
        cfg = generate_cfg(self.FULL_SPEC)
        assert "SPECIFICATION Spec" in cfg
        assert "CONSTANT MaxSteps = 10" in cfg
        assert "CONSTANT MaxAttempts = 10" in cfg
        assert "INVARIANT TypeInvariant" in cfg
        assert "INVARIANT BoundedExecution" in cfg
        assert "INVARIANT SafetyGate" in cfg
        # Set definitions must NOT appear as invariants
        assert "INVARIANT AllPhases" not in cfg
        assert "INVARIANT TerminalPhases" not in cfg

    def test_standard_tla_names_excluded(self):
        """Init, Next, Spec, vars, Fairness, Liveness, Termination must not be invariants."""
        cfg = generate_cfg(self.SPEC_WITH_STANDARD_OPS)
        for name in ("Init", "Next", "Spec", "vars", "Fairness", "Liveness", "Termination"):
            assert f"INVARIANT {name}" not in cfg, f"{name} should be excluded"
        # The real invariant should still be present
        assert "INVARIANT RealInvariant" in cfg

    def test_no_constants_produces_no_constant_lines(self):
        """Spec without CONSTANTS should have no CONSTANT lines in cfg."""
        cfg = generate_cfg(self.BARE_SPEC)
        assert "SPECIFICATION Spec" in cfg
        assert "CONSTANT" not in cfg.replace("SPECIFICATION", "")

    def test_constants_without_define_block(self):
        """CONSTANTS extracted even when there's no define block."""
        cfg = generate_cfg(self.SPEC_NO_DEFINE)
        assert "CONSTANT N = 10" in cfg
        assert "INVARIANT" not in cfg

    def test_no_define_no_constants_produces_bare_cfg(self):
        """A minimal spec produces only SPECIFICATION Spec."""
        cfg = generate_cfg(self.BARE_SPEC)
        assert cfg.strip() == "SPECIFICATION Spec"

    def test_custom_default_constant_value(self):
        """default_constant_value parameter is respected."""
        cfg = generate_cfg(self.FULL_SPEC, default_constant_value=5)
        assert "CONSTANT MaxSteps = 5" in cfg
        assert "CONSTANT MaxAttempts = 5" in cfg

    # -- Set-typed constant classification --

    SPEC_WITH_SET_CONSTANTS = textwrap.dedent("""\
        ---- MODULE SetConsts ----
        EXTENDS Integers, FiniteSets

        CONSTANTS
            NodeIds,
            MaxRetries

        ASSUME NodeIds /= {}
        ASSUME MaxRetries \\in Nat /\\ MaxRetries > 0

        (* --algorithm SetTest

        variables processed = {};

        define

            TypeInvariant ==
                /\\ processed \\subseteq NodeIds
                /\\ Cardinality(processed) <= Cardinality(NodeIds)

            BoundedRetries == MaxRetries > 0

        end define;

        fair process worker \\in NodeIds
        begin Work: processed := processed \\union {self};
        end process;

        end algorithm; *)

        ====
    """)

    def test_set_constant_gets_model_values(self):
        """Constants with ASSUME X /= {} should get model value sets."""
        cfg = generate_cfg(self.SPEC_WITH_SET_CONSTANTS)
        assert "CONSTANT NodeIds = {NodeIds_1, NodeIds_2}" in cfg
        assert "CONSTANT MaxRetries = 10" in cfg

    SPEC_WITH_ITERATOR_SET = textwrap.dedent("""\
        ---- MODULE IterSet ----
        EXTENDS Integers

        CONSTANTS
            Workers,
            Limit

        ASSUME Limit > 0

        (* --algorithm Iter

        variables count = 0;

        define
            SafeCount == count <= Limit
        end define;

        fair process w \\in Workers
        begin Step: count := count + 1;
        end process;

        end algorithm; *)

        ====
    """)

    def test_iterator_range_constant_gets_model_values(self):
        """Constants used as \\in X iterator range should get model value sets."""
        cfg = generate_cfg(self.SPEC_WITH_ITERATOR_SET)
        assert "CONSTANT Workers = {Workers_1, Workers_2}" in cfg
        assert "CONSTANT Limit = 10" in cfg

    # -- Umbrella invariant detection --

    SPEC_WITH_UMBRELLA = textwrap.dedent("""\
        ---- MODULE Umbrella ----
        EXTENDS Integers

        CONSTANTS MaxSteps

        ASSUME MaxSteps \\in Nat /\\ MaxSteps > 0

        (* --algorithm UmbrellaTest

        variables phase = "idle", count = 0;

        define

            TypeInvariant ==
                /\\ phase \\in {"idle", "running", "done"}
                /\\ count \\in 0..MaxSteps

            BoundedExecution == count <= MaxSteps

            SafetyGate ==
                phase = "done" => count > 0

            AllInvariants ==
                /\\ TypeInvariant
                /\\ BoundedExecution
                /\\ SafetyGate

        end define;

        fair process P = "p"
        begin L: skip;
        end process;

        end algorithm; *)

        ====
    """)

    def test_umbrella_invariant_used_as_single_invariant(self):
        """When an operator is a conjunction of 3+ other ops, use it as sole INVARIANT."""
        cfg = generate_cfg(self.SPEC_WITH_UMBRELLA)
        assert "INVARIANT AllInvariants" in cfg
        # Individual invariants should NOT appear
        assert "INVARIANT TypeInvariant" not in cfg
        assert "INVARIANT BoundedExecution" not in cfg
        assert "INVARIANT SafetyGate" not in cfg

    # -- Progress condition filtering --

    SPEC_WITH_PROGRESS = textwrap.dedent("""\
        ---- MODULE Progress ----
        EXTENDS Integers, FiniteSets

        CONSTANTS NodeIds

        ASSUME NodeIds /= {}

        (* --algorithm ProgressTest

        variables processed = {};

        define

            TypeInvariant ==
                processed \\subseteq NodeIds

            AllProcessed == processed = NodeIds

        end define;

        fair process w \\in NodeIds
        begin Work: processed := processed \\union {self};
        end process;

        end algorithm; *)

        ====
    """)

    def test_progress_condition_excluded(self):
        """Simple X = Y equality (progress condition) should be excluded from invariants."""
        cfg = generate_cfg(self.SPEC_WITH_PROGRESS)
        assert "INVARIANT TypeInvariant" in cfg
        assert "INVARIANT AllProcessed" not in cfg


# ---------------------------------------------------------------------------
# run_tlc_simulate filename-mismatch bug tests
# ---------------------------------------------------------------------------

class TestRunTlcSimulateFilenameFix:
    """Tests that run_tlc_simulate handles filename/module name mismatch.

    TLC requires the .tla filename to match the MODULE name inside the file.
    When a spec is saved as e.g. gwt-0002.tla but contains MODULE FooBar,
    run_tlc_simulate must create a temp file named FooBar.tla before invoking TLC.
    """

    SPEC_TEXT = textwrap.dedent("""\
        ---- MODULE IssueChallengeCreatesOpenDispatchMapping ----
        EXTENDS Integers

        (* --algorithm IssueChallenge

        variables x = 0;

        begin
            L: x := 1;

        end algorithm; *)

        ====
    """)

    CFG_TEXT = "SPECIFICATION Spec\n"

    @pytest.fixture(autouse=True)
    def setup_files(self, tmp_path):
        """Create a .tla file whose filename does NOT match its MODULE name."""
        self.tla_file = tmp_path / "gwt-0002.tla"
        self.tla_file.write_text(self.SPEC_TEXT)
        self.cfg_file = tmp_path / "gwt-0002.cfg"
        self.cfg_file.write_text(self.CFG_TEXT)
        self.tmp_path = tmp_path

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_tlc_invoked_with_correct_module_filename(self, mock_run, mock_jar):
        """TLC must be called with a .tla path whose stem matches the MODULE name."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(self.tla_file, self.cfg_file)

        # Extract the tla_path argument passed to TLC
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        # Find the .tla argument in the command
        tla_arg = [arg for arg in cmd if arg.endswith(".tla")][0]
        assert Path(tla_arg).stem == "IssueChallengeCreatesOpenDispatchMapping", \
            f"TLC was called with {tla_arg} but should use MODULE-matching filename"

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_cfg_also_renamed_to_match_module(self, mock_run, mock_jar):
        """The .cfg file passed to TLC must also match the MODULE name."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(self.tla_file, self.cfg_file)

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        # Find the -config argument
        config_idx = cmd.index("-config")
        cfg_arg = cmd[config_idx + 1]
        assert Path(cfg_arg).stem == "IssueChallengeCreatesOpenDispatchMapping", \
            f"TLC config was {cfg_arg} but should use MODULE-matching filename"

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_matching_filename_not_renamed(self, mock_run, mock_jar):
        """When filename already matches MODULE name, no rename needed."""
        matching_tla = self.tmp_path / "IssueChallengeCreatesOpenDispatchMapping.tla"
        matching_tla.write_text(self.SPEC_TEXT)

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(matching_tla)

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        tla_arg = [arg for arg in cmd if arg.endswith(".tla")][0]
        # Should use the original file directly
        assert tla_arg == str(matching_tla)

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_temp_file_contains_same_content(self, mock_run, mock_jar):
        """The renamed temp file must contain the same spec content."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(self.tla_file, self.cfg_file)

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        tla_arg = [arg for arg in cmd if arg.endswith(".tla")][0]
        assert Path(tla_arg).read_text() == self.SPEC_TEXT

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_no_module_header_uses_original_path(self, mock_run, mock_jar):
        """If MODULE name can't be extracted, use the original file path."""
        no_module = self.tmp_path / "weird.tla"
        no_module.write_text("(* just some PlusCal without module header *)")

        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(no_module)

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        tla_arg = [arg for arg in cmd if arg.endswith(".tla")][0]
        assert tla_arg == str(no_module)


# ---------------------------------------------------------------------------
# TLC Error Classification Tests (Bug 1: smarter retries)
# ---------------------------------------------------------------------------

class TestTLCErrorClassification:
    """Tests for classify_tlc_error() — regex-based TLC error signal extraction."""

    def test_classify_pluscal_syntax_error(self):
        """PlusCal compilation failure → SYNTAX_ERROR."""
        raw = "PlusCal compilation failed: Unrecoverable error at line 42, column 5."
        result = classify_tlc_error(raw, pluscal_compile_failed=True)
        assert result == TLCErrorClass.SYNTAX_ERROR

    def test_classify_tlc_parse_error(self):
        """TLC parsing/semantic analysis failure → PARSE_ERROR."""
        raw = (
            "Error: Parsing or semantic analysis failed.\n"
            "Was expecting 'Expression'\n"
            "Encountered 'Bogus' at line 10, column 1"
        )
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.PARSE_ERROR

    def test_classify_type_error(self):
        """TLC type mismatch → TYPE_ERROR."""
        raw = (
            "Error: Attempted to apply the operator overridden by "
            "the Java method public static tlc2.value.impl.Value "
            "tlc2.module.Integers.Plus(tlc2.value.impl.Value, "
            "tlc2.value.impl.Value) to the non-integer arguments:\n"
            '"hello"\n1'
        )
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.TYPE_ERROR

    def test_classify_invariant_violation(self):
        """Invariant violation → INVARIANT_VIOLATION."""
        raw = (
            "Error: Invariant SafetyInvariant is violated.\n"
            "Error: The behavior up to this point is:\n"
            "State 1: <Initial predicate>\n"
            "/\\ x = 0\n"
            "State 2: <Step line 42>\n"
            "/\\ x = -1"
        )
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.INVARIANT_VIOLATION

    def test_classify_deadlock(self):
        """Deadlock → DEADLOCK."""
        raw = (
            "Error: Deadlock reached.\n"
            "Error: The behavior up to this point is:\n"
            "State 1: <Initial predicate>\n"
            "/\\ x = 0"
        )
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.DEADLOCK

    def test_classify_constant_mismatch(self):
        """Unknown operator (missing CONSTANT) → CONSTANT_MISMATCH."""
        raw = (
            "Error: Unknown operator: `MaxRetries'.\n"
            "line 15, col 10 to line 15, col 19 of module TestSpec"
        )
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.CONSTANT_MISMATCH

    def test_classify_unknown_error(self):
        """Unrecognized error format → UNKNOWN."""
        raw = "Something went terribly wrong but in an unexpected way."
        result = classify_tlc_error(raw)
        assert result == TLCErrorClass.UNKNOWN

    def test_empty_output_classifies_as_unknown(self):
        """Empty output → UNKNOWN."""
        result = classify_tlc_error("")
        assert result == TLCErrorClass.UNKNOWN

    def test_syntax_error_takes_priority_over_content(self):
        """When pluscal_compile_failed=True, always SYNTAX_ERROR regardless of content."""
        raw = "Error: Invariant Foo is violated."
        result = classify_tlc_error(raw, pluscal_compile_failed=True)
        assert result == TLCErrorClass.SYNTAX_ERROR


class TestTLCResultErrorClass:
    """Tests that TLCResult carries error_class field."""

    def test_tlc_result_has_error_class_field(self):
        """TLCResult should have an error_class field defaulting to None."""
        r = TLCResult(success=True)
        assert r.error_class is None

    def test_tlc_result_accepts_error_class(self):
        """TLCResult should accept an explicit error_class."""
        r = TLCResult(success=False, error_class=TLCErrorClass.DEADLOCK)
        assert r.error_class == TLCErrorClass.DEADLOCK

    def test_run_tlc_sets_error_class_on_failure(self):
        """run_tlc should set error_class when verification fails."""
        raw_output = (
            "Error: Invariant TypeInvariant is violated.\n"
            "Error: The behavior up to this point is:\n"
            "State 1: <Initial predicate>\n/\\ x = 0\n"
        )
        with patch("registry.one_shot_loop._find_tla2tools", return_value="/fake.jar"), \
             patch("registry.one_shot_loop.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=raw_output, stderr="", returncode=12,
            )
            from registry.one_shot_loop import run_tlc
            result = run_tlc("/fake/spec.tla")
            assert result.error_class == TLCErrorClass.INVARIANT_VIOLATION

    def test_run_tlc_sets_none_on_success(self):
        """run_tlc should leave error_class as None on success."""
        raw_output = "Model checking completed. No error has been found.\n42 states generated, 20 distinct."
        with patch("registry.one_shot_loop._find_tla2tools", return_value="/fake.jar"), \
             patch("registry.one_shot_loop.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=raw_output, stderr="", returncode=0,
            )
            from registry.one_shot_loop import run_tlc
            result = run_tlc("/fake/spec.tla")
            assert result.error_class is None


# ---------------------------------------------------------------------------
# Build Retry Prompt with Error Classification Tests (Bug 1 continued)
# ---------------------------------------------------------------------------

class TestBuildRetryPromptClassified:
    """Tests that build_retry_prompt uses error classification for targeted instructions."""

    def test_syntax_error_retry_prompt(self):
        """SYNTAX_ERROR → tells LLM to fix PlusCal syntax, not semantics."""
        from registry.loop_runner import build_retry_prompt
        status = LoopStatus(
            error="PlusCal compilation failed: line 42, col 5",
            tlc_result=TLCResult(
                success=False,
                raw_output="Unrecoverable error at line 42",
                error_message="PlusCal compilation failed",
                error_class=TLCErrorClass.SYNTAX_ERROR,
            ),
        )
        prompt = build_retry_prompt("original prompt", 1, status)
        # Must mention it's a syntax error
        assert "syntax" in prompt.lower() or "SYNTAX" in prompt
        # Must NOT talk about invariants or state space
        assert "invariant" not in prompt.lower().split("previous attempt")[0]

    def test_invariant_violation_retry_prompt(self):
        """INVARIANT_VIOLATION → tells LLM to fix logic, structure is correct."""
        from registry.loop_runner import build_retry_prompt
        trace = CounterexampleTrace(
            raw_trace="State 1: ...",
            violated_invariant="SafetyInvariant",
            pluscal_summary="Step 1: x=0, Step 2: x=-1",
        )
        status = LoopStatus(
            error="TLC verification failed",
            counterexample=trace,
            tlc_result=TLCResult(
                success=False,
                raw_output="Invariant SafetyInvariant is violated",
                error_message="Invariant SafetyInvariant is violated",
                error_class=TLCErrorClass.INVARIANT_VIOLATION,
            ),
        )
        prompt = build_retry_prompt("original prompt", 1, status)
        # Must tell LLM the structure compiled correctly
        assert "compil" in prompt.lower()  # "compiled" or "compilation"
        # Must focus on invariant/logic fix
        assert "invariant" in prompt.lower()

    def test_deadlock_retry_prompt(self):
        """DEADLOCK → tells LLM to add termination or fix process structure."""
        from registry.loop_runner import build_retry_prompt
        status = LoopStatus(
            error="Deadlock reached",
            tlc_result=TLCResult(
                success=False,
                raw_output="Error: Deadlock reached.",
                error_message="Deadlock reached",
                error_class=TLCErrorClass.DEADLOCK,
            ),
        )
        prompt = build_retry_prompt("original prompt", 1, status)
        assert "deadlock" in prompt.lower()

    def test_type_error_retry_prompt(self):
        """TYPE_ERROR → tells LLM about type mismatch."""
        from registry.loop_runner import build_retry_prompt
        status = LoopStatus(
            error="Type mismatch",
            tlc_result=TLCResult(
                success=False,
                raw_output="Attempted to apply the operator overridden by...",
                error_message="Type mismatch",
                error_class=TLCErrorClass.TYPE_ERROR,
            ),
        )
        prompt = build_retry_prompt("original prompt", 1, status)
        assert "type" in prompt.lower()

    def test_constant_mismatch_retry_prompt(self):
        """CONSTANT_MISMATCH → tells LLM about missing constant definition."""
        from registry.loop_runner import build_retry_prompt
        status = LoopStatus(
            error="Unknown operator",
            tlc_result=TLCResult(
                success=False,
                raw_output="Error: Unknown operator: `MaxRetries'.",
                error_message="Unknown operator: MaxRetries",
                error_class=TLCErrorClass.CONSTANT_MISMATCH,
            ),
        )
        prompt = build_retry_prompt("original prompt", 1, status)
        assert "constant" in prompt.lower() or "CONSTANT" in prompt


# ---------------------------------------------------------------------------
# Simulation Trace File Reading Tests (Bug 2)
# ---------------------------------------------------------------------------

class TestRunTlcSimulateFileOutput:
    """Tests that run_tlc_simulate reads traces from files, not stdout."""

    SPEC_TEXT = textwrap.dedent("""\
        ---- MODULE SimTest ----
        EXTENDS Integers

        (* --algorithm Simple
        variables x = 0;
        begin L: x := 1;
        end algorithm; *)

        ====
    """)

    @pytest.fixture(autouse=True)
    def setup_files(self, tmp_path):
        self.tla_file = tmp_path / "SimTest.tla"
        self.tla_file.write_text(self.SPEC_TEXT)
        self.cfg_file = tmp_path / "SimTest.cfg"
        self.cfg_file.write_text("SPECIFICATION Spec\n")
        self.tmp_path = tmp_path

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_simulate_cmd_includes_file_param(self, mock_run, mock_jar):
        """The -simulate flag must include file=<path> to capture trace files."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        run_tlc_simulate(self.tla_file, self.cfg_file)

        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1]["args"]
        # Find the -simulate argument
        sim_args = [arg for arg in cmd if "-simulate" in str(arg) or "file=" in str(arg)]
        sim_str = " ".join(str(a) for a in cmd)
        assert "file=" in sim_str, \
            f"Expected 'file=' in simulate args, got cmd: {cmd}"

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_simulate_reads_trace_files(self, mock_run, mock_jar, tmp_path):
        """After TLC runs, should read trace files from disk, not parse stdout."""
        # Simulate TLC writing trace files
        trace_content = textwrap.dedent("""\
            State 1: <Initial predicate>
            /\\ x = 0

            State 2: <L line 6>
            /\\ x = 1
        """)

        def side_effect(cmd, **kwargs):
            # Figure out where traces should be written
            sim_str = " ".join(str(a) for a in cmd)
            import re
            file_match = re.search(r'file=([^\s,]+)', sim_str)
            if file_match:
                base_path = file_match.group(1)
                # TLC creates files like traces_0_0, traces_0_1, etc.
                Path(f"{base_path}_0_0").write_text(trace_content)
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        traces = run_tlc_simulate(self.tla_file, self.cfg_file)

        # Should have found the trace from the file, not from empty stdout
        assert len(traces) >= 1, "Should have read at least one trace from files"
        assert traces[0][0]["vars"]["x"] == "0"

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_simulate_returns_empty_when_no_trace_files(self, mock_run, mock_jar):
        """If TLC produces no trace files, return empty list."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

        traces = run_tlc_simulate(self.tla_file, self.cfg_file)
        assert traces == []

    @patch("registry.one_shot_loop._find_tla2tools", return_value="/fake/tla2tools.jar")
    @patch("registry.one_shot_loop.subprocess.run")
    def test_simulate_reads_multiple_trace_files(self, mock_run, mock_jar):
        """Multiple trace files should produce multiple traces."""
        trace1 = "State 1: <Initial predicate>\n/\\ x = 0\n\nState 2: <L line 6>\n/\\ x = 1\n"
        trace2 = "State 1: <Initial predicate>\n/\\ x = 0\n\nState 2: <L line 6>\n/\\ x = 2\n"

        def side_effect(cmd, **kwargs):
            sim_str = " ".join(str(a) for a in cmd)
            import re
            file_match = re.search(r'file=([^\s,]+)', sim_str)
            if file_match:
                base_path = file_match.group(1)
                Path(f"{base_path}_0_0").write_text(trace1)
                Path(f"{base_path}_0_1").write_text(trace2)
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        traces = run_tlc_simulate(self.tla_file, self.cfg_file)

        assert len(traces) == 2
        # First trace ends with x=1, second with x=2
        assert traces[0][-1]["vars"]["x"] == "1"
        assert traces[1][-1]["vars"]["x"] == "2"
