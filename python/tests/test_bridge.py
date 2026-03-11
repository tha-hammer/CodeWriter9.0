"""Tests for the Bridge — Phase 4 spec-to-code translators."""

import json
import os
import pytest

from registry.bridge import (
    parse_spec,
    translate_state_vars,
    translate_actions,
    translate_invariants_to_verifiers,
    translate_invariants_to_assertions,
    translate_traces,
    trace_scenarios_to_dict,
    run_bridge,
    TlcTrace,
    ParsedSpec,
    BridgeResult,
)
from registry.extractor import SchemaExtractor
from registry.dag import RegistryDag


# ── Test fixtures ──

SAMPLE_SPEC = """\
------------------------ MODULE sample_spec ------------------------
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    MaxSteps

(* --algorithm SampleSpec

variables
    current_state = "idle",
    count = 0,
    items = {},
    active = FALSE;

define
    ValidState == current_state \\in {"idle", "running", "done"}
    BoundedCount == count <= MaxSteps
    NonNegativeCount == count >= 0
end define;

end algorithm; *)

\\* BEGIN TRANSLATION - placeholder for pcal.trans output
VARIABLES pc, current_state, count, items, active

(* define statement *)
ValidState == current_state \\in {"idle", "running", "done"}
BoundedCount == count <= MaxSteps
NonNegativeCount == count >= 0


vars == << pc, current_state, count, items, active >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\\ current_state = "idle"
        /\\ count = 0
        /\\ items = {}
        /\\ active = FALSE
        /\\ pc = [self \\in ProcSet |-> "Start"]

StartAction == /\\ pc["main"] = "Start"
               /\\ current_state = "idle"
               /\\ current_state' = "running"
               /\\ active' = TRUE
               /\\ count' = count + 1
               /\\ pc' = [pc EXCEPT !["main"] = "Process"]
               /\\ UNCHANGED << items >>

ProcessAction == /\\ pc["main"] = "Process"
                 /\\ current_state = "running"
                 /\\ items' = items \\union {"item_" \\o ToString(count)}
                 /\\ count' = count + 1
                 /\\ pc' = [pc EXCEPT !["main"] = "End"]
                 /\\ UNCHANGED << current_state, active >>

EndAction == /\\ pc["main"] = "End"
             /\\ current_state' = "done"
             /\\ active' = FALSE
             /\\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\\ UNCHANGED << count, items >>

Next == StartAction \\/ ProcessAction \\/ EndAction

Spec == Init /\\ [][Next]_vars

\\* END TRANSLATION

===========================================================================
"""

BRIDGE_SPEC_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'templates', 'pluscal', 'instances', 'bridge_translator.tla'
)


# ── Parsing tests ──


class TestParsing:
    def setup_method(self):
        self.spec = parse_spec(SAMPLE_SPEC)

    def test_module_name(self):
        assert self.spec.module_name == "sample_spec"

    def test_variable_count(self):
        # pc, current_state, count, items, active
        assert len(self.spec.variables) >= 4

    def test_variable_names(self):
        names = {v.name for v in self.spec.variables}
        assert "current_state" in names
        assert "count" in names
        assert "items" in names
        assert "active" in names

    def test_variable_types(self):
        var_map = {v.name: v for v in self.spec.variables}
        assert var_map["count"].type_hint == "integer"
        assert var_map["active"].type_hint == "boolean"
        assert var_map["items"].type_hint == "set"
        assert var_map["current_state"].type_hint == "string"

    def test_invariant_count(self):
        assert len(self.spec.invariants) >= 3

    def test_invariant_names(self):
        names = {i.name for i in self.spec.invariants}
        assert "ValidState" in names
        assert "BoundedCount" in names
        assert "NonNegativeCount" in names

    def test_action_count(self):
        assert len(self.spec.actions) >= 3

    def test_action_names(self):
        names = {a.name for a in self.spec.actions}
        assert "StartAction" in names
        assert "ProcessAction" in names
        assert "EndAction" in names

    def test_constants(self):
        assert "MaxSteps" in self.spec.constants


# ── Translator 1: State vars → data_structures ──


class TestStateVarTranslation:
    def setup_method(self):
        self.spec = parse_spec(SAMPLE_SPEC)
        self.result = translate_state_vars(self.spec)

    def test_produces_structure(self):
        assert len(self.result) == 1
        name = list(self.result.keys())[0]
        assert "sample_spec" in name.lower()

    def test_structure_has_required_keys(self):
        structure = list(self.result.values())[0]
        assert "function_id" in structure
        assert "acceptance_criteria_id" in structure
        assert "fields" in structure
        assert "relations" in structure
        assert "description" in structure

    def test_fields_match_variables(self):
        structure = list(self.result.values())[0]
        fields = structure["fields"]
        var_names = {v.name for v in self.spec.variables}
        for var_name in ("current_state", "count", "items", "active"):
            assert var_name in fields

    def test_field_shape(self):
        structure = list(self.result.values())[0]
        field = structure["fields"]["count"]
        assert "type" in field
        assert "required" in field
        assert "unique" in field
        assert "default" in field
        assert "validation" in field

    def test_field_types_are_schema_paths(self):
        structure = list(self.result.values())[0]
        for field in structure["fields"].values():
            assert field["type"].startswith("shared/data_types/")


# ── Translator 2: Actions → operations ──


class TestActionTranslation:
    def setup_method(self):
        self.spec = parse_spec(SAMPLE_SPEC)
        self.result = translate_actions(self.spec)

    def test_operation_count_matches_actions(self):
        assert len(self.result) == len(self.spec.actions)

    def test_operation_has_required_keys(self):
        for op in self.result.values():
            assert "function_id" in op
            assert "acceptance_criteria_id" in op
            assert "parameters" in op
            assert "returns" in op
            assert "error_types" in op
            assert "error_handling" in op
            assert "description" in op

    def test_parameter_types_are_schema_paths(self):
        for op in self.result.values():
            for param_type in op["parameters"].values():
                assert param_type.startswith("shared/data_types/")

    def test_return_type_is_schema_path(self):
        for op in self.result.values():
            assert op["returns"].startswith("shared/data_types/")


# ── Translator 3: Invariants → verifiers + assertions ──


class TestInvariantTranslation:
    def setup_method(self):
        self.spec = parse_spec(SAMPLE_SPEC)
        self.verifiers = translate_invariants_to_verifiers(self.spec)
        self.assertions = translate_invariants_to_assertions(self.spec)

    def test_verifier_count_matches_invariants(self):
        assert len(self.verifiers) == len(self.spec.invariants)

    def test_assertion_count_matches_invariants(self):
        assert len(self.assertions) == len(self.spec.invariants)

    def test_verifier_has_required_keys(self):
        for v in self.verifiers.values():
            assert "function_id" in v
            assert "acceptance_criteria_id" in v
            assert "conditions" in v
            assert "message" in v
            assert "applies_to" in v
            assert "description" in v

    def test_assertion_has_required_keys(self):
        for a in self.assertions.values():
            assert "condition" in a
            assert "message" in a
            assert "description" in a

    def test_verifier_conditions_are_nonempty(self):
        for v in self.verifiers.values():
            assert len(v["conditions"]) > 0


# ── Translator 4: Traces → scenarios ──


class TestTraceTranslation:
    def test_empty_traces(self):
        spec = parse_spec(SAMPLE_SPEC)
        scenarios = translate_traces([], spec)
        assert scenarios == []

    def test_trace_produces_scenario(self):
        spec = parse_spec(SAMPLE_SPEC)
        trace = TlcTrace(
            invariant_violated="ValidState",
            states=[
                {"current_state": "idle", "count": "0"},
                {"current_state": "running", "count": "1"},
                {"current_state": "invalid", "count": "2"},
            ],
        )
        scenarios = translate_traces([trace], spec)
        assert len(scenarios) == 1
        s = scenarios[0]
        assert s.invariant_tested == "ValidState"
        assert len(s.steps) == 2  # 3 states → 2 transitions
        assert s.setup == {"current_state": "idle", "count": "0"}

    def test_scenario_to_dict(self):
        spec = parse_spec(SAMPLE_SPEC)
        trace = TlcTrace(
            invariant_violated="BoundedCount",
            states=[
                {"count": "0"},
                {"count": "100"},
            ],
        )
        scenarios = translate_traces([trace], spec)
        result = trace_scenarios_to_dict(scenarios)
        assert len(result) == 1
        suite = list(result.values())[0]
        assert "tests" in suite
        assert "description" in suite


# ── Full pipeline ──


class TestBridgePipeline:
    def setup_method(self):
        self.result = run_bridge(SAMPLE_SPEC)

    def test_returns_bridge_result(self):
        assert isinstance(self.result, BridgeResult)

    def test_module_name(self):
        assert self.result.module_name == "sample_spec"

    def test_data_structures_produced(self):
        assert len(self.result.data_structures) == 1

    def test_operations_produced(self):
        assert len(self.result.operations) == len(self.result.parsed_spec.actions)

    def test_verifiers_match_invariants(self):
        """Bridge spec invariant: verifiers_out == invariants_found."""
        assert len(self.result.verifiers) == len(self.result.parsed_spec.invariants)

    def test_assertions_match_invariants(self):
        """Bridge spec invariant: assertions_out == invariants_found."""
        assert len(self.result.assertions) == len(self.result.parsed_spec.invariants)

    def test_all_outputs_json_serializable(self):
        """All outputs must be JSON-serializable for schema conformance."""
        json.dumps(self.result.data_structures)
        json.dumps(self.result.operations)
        json.dumps(self.result.verifiers)
        json.dumps(self.result.assertions)


# ── Bridge on its own spec (self-verification) ──


class TestBridgeOnBridgeSpec:
    """Run the bridge on the bridge_translator.tla spec itself."""

    def setup_method(self):
        if os.path.exists(BRIDGE_SPEC_PATH):
            with open(BRIDGE_SPEC_PATH) as f:
                self.tla_text = f.read()
            self.result = run_bridge(self.tla_text)
        else:
            pytest.skip("bridge_translator.tla not found")

    def test_parses_bridge_spec(self):
        assert self.result.module_name == "bridge_translator"

    def test_data_structures_count(self):
        """1 structure for the bridge state model."""
        assert len(self.result.data_structures) == 1

    def test_verifiers_match_invariants(self):
        assert len(self.result.verifiers) == len(self.result.parsed_spec.invariants)

    def test_assertions_match_invariants(self):
        assert len(self.result.assertions) == len(self.result.parsed_spec.invariants)


# ── DAG registration tests ──


class TestBridgeRegistration:
    def setup_method(self):
        schema_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'schema')
        e = SchemaExtractor(schema_dir=schema_dir, self_host=True)
        self.dag = e.extract()

    def test_bridge_requirement_exists(self):
        assert "req-0003" in self.dag.nodes

    def test_bridge_gwt_nodes_exist(self):
        for gwt in ("gwt-0008", "gwt-0009", "gwt-0010", "gwt-0011"):
            assert gwt in self.dag.nodes
            assert self.dag.nodes[gwt].kind.value == "behavior"

    def test_bridge_resource_nodes_exist(self):
        for br in ("bridge-0001", "bridge-0002", "bridge-0003", "bridge-0004"):
            assert br in self.dag.nodes

    def test_requirement_decomposes_to_gwts(self):
        edges = [e for e in self.dag.edges if e.from_id == "req-0003"]
        targets = {e.to_id for e in edges}
        for gwt in ("gwt-0008", "gwt-0009", "gwt-0010", "gwt-0011"):
            assert gwt in targets

    def test_bridge_depends_on_loop(self):
        for br in ("bridge-0001", "bridge-0002", "bridge-0003", "bridge-0004"):
            edges = [e for e in self.dag.edges if e.from_id == br and e.to_id == "loop-0001"]
            assert len(edges) >= 1

    def test_bridge_references_plan_store(self):
        for br in ("bridge-0001", "bridge-0002", "bridge-0003", "bridge-0004"):
            edges = [e for e in self.dag.edges if e.from_id == br and e.to_id == "fs-y3q2"]
            assert len(edges) >= 1
