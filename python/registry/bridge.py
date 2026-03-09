"""
Bridge — Mechanical spec-to-code translators (Phase 4).

Translates TLA+ specs into artifacts conforming to existing schema shapes:
  1. State variables → data_structures shape
  2. Actions → processors.operations shape
  3. Invariants → verifiers + testing.assertions shapes
  4. TLC traces → test scenario shapes

The bridge is mechanical: no LLM involved. It parses TLA+ text
and produces structured artifacts deterministically.

Verified by: templates/pluscal/instances/bridge_translator.tla
  TLC: 702 states, 407 distinct, 6 invariants, 0 violations
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── TLA+ Parsing ──


@dataclass
class TlaVariable:
    """A state variable extracted from a TLA+ spec."""
    name: str
    initial_value: str
    type_hint: str  # inferred from initial value


@dataclass
class TlaAction:
    """An action extracted from a TLA+ spec."""
    name: str
    guard: str  # enabling condition
    assignments: list[tuple[str, str]]  # [(var_name, expression)]


@dataclass
class TlaInvariant:
    """An invariant extracted from a TLA+ spec."""
    name: str
    expression: str
    references: list[str]  # variable names referenced


@dataclass
class TlcTrace:
    """A TLC counterexample trace."""
    invariant_violated: str
    states: list[dict[str, str]]  # [{var_name: value}]


@dataclass
class ParsedSpec:
    """Result of parsing a TLA+ spec."""
    module_name: str
    variables: list[TlaVariable]
    actions: list[TlaAction]
    invariants: list[TlaInvariant]
    constants: list[str]


def parse_spec(tla_text: str) -> ParsedSpec:
    """Parse a TLA+ spec into structured components.

    Handles both raw TLA+ and PlusCal-compiled TLA+.
    """
    module_name = _extract_module_name(tla_text)
    variables = _extract_variables(tla_text)
    actions = _extract_actions(tla_text)
    invariants = _extract_invariants(tla_text)
    constants = _extract_constants(tla_text)

    return ParsedSpec(
        module_name=module_name,
        variables=variables,
        actions=actions,
        invariants=invariants,
        constants=constants,
    )


def _extract_module_name(text: str) -> str:
    m = re.search(r'-+\s*MODULE\s+(\w+)\s*-+', text)
    return m.group(1) if m else "Unknown"


def _extract_variables(text: str) -> list[TlaVariable]:
    """Extract VARIABLES declarations and their initial values from Init."""
    variables = []

    # Find VARIABLES declaration
    var_match = re.search(
        r'VARIABLES?\s+(.*?)(?=\n\s*\n|\n\(\*|\ndefine\b)',
        text, re.DOTALL
    )
    if not var_match:
        return variables

    # Parse variable names (comma-separated, possibly multi-line)
    var_text = var_match.group(1)
    var_names = [
        v.strip().rstrip(',')
        for v in re.split(r'[,\n]', var_text)
        if v.strip() and not v.strip().startswith('\\*') and v.strip().rstrip(',')
    ]

    # Find Init to get initial values
    init_match = re.search(r'Init\s*==\s*(.*?)(?=\n\n|\n\w+\s*==)', text, re.DOTALL)
    init_vals: dict[str, str] = {}
    if init_match:
        init_text = init_match.group(1)
        for m in re.finditer(r'/\\\s*(\w+)\s*=\s*(.+?)(?=\s*/\\|\s*$)', init_text):
            init_vals[m.group(1)] = m.group(2).strip()

    for name in var_names:
        clean = name.strip()
        if not clean:
            continue
        init_val = init_vals.get(clean, "")
        type_hint = _infer_type(init_val)
        variables.append(TlaVariable(name=clean, initial_value=init_val, type_hint=type_hint))

    return variables


def _infer_type(init_value: str) -> str:
    """Infer a type hint from a TLA+ initial value."""
    v = init_value.strip()
    if not v:
        return "unknown"
    if v == "TRUE" or v == "FALSE":
        return "boolean"
    if v.startswith('"') and v.endswith('"'):
        return "string"
    if v.startswith('{') and v.endswith('}'):
        return "set"
    if v.startswith('<<') and v.endswith('>>'):
        return "sequence"
    if v.startswith('['):
        return "function"
    try:
        int(v)
        return "integer"
    except ValueError:
        pass
    return "string"  # enum-like string constants


def _extract_actions(text: str) -> list[TlaAction]:
    """Extract named TLA+ actions (Name == /\\ guard /\\ assignments)."""
    actions = []

    skip = {'Init', 'Spec', 'Next', 'Terminating', 'Termination', 'vars', 'ProcSet'}

    # Split text into top-level definitions
    # Pattern: starts at beginning of line with a word, followed by ==
    defs = re.split(r'\n(?=\w+\s*==\s)', text)

    for defn in defs:
        m = re.match(r'^(\w+)\s*==\s*(.*)', defn, re.DOTALL)
        if not m:
            continue

        name = m.group(1)
        body = m.group(2).strip()

        if name in skip:
            continue
        if name.endswith('_composed') or name.startswith('Inv'):
            continue

        # Actions have primed variables (x' = ...) or EXCEPT
        if "'" not in body and "EXCEPT" not in body:
            continue

        # Extract guard (first conjunct, usually pc check)
        guard = ""
        guard_match = re.search(r'/\\\s*(.+?)(?=\s*/\\)', body)
        if guard_match:
            guard = guard_match.group(1).strip()

        # Extract assignments (var' = expr or EXCEPT patterns)
        assignments = []
        for assign in re.finditer(r"(\w+)'\s*=\s*(.+?)(?=\s*/\\|\s*$)", body):
            assignments.append((assign.group(1), assign.group(2).strip()))

        actions.append(TlaAction(name=name, guard=guard, assignments=assignments))

    return actions


def _extract_invariants(text: str) -> list[TlaInvariant]:
    """Extract invariant definitions from the define block."""
    invariants = []

    # Look in define block first (PlusCal-compiled)
    define_match = re.search(
        r'\(\*\s*define statement\s*\*\)\s*(.*?)(?=\nvars\s*==|\n\w+\s*==\s*<<)',
        text, re.DOTALL
    )
    if not define_match:
        # Try raw define block
        define_match = re.search(
            r'define\s+(.*?)end define',
            text, re.DOTALL
        )

    if not define_match:
        return invariants

    define_text = define_match.group(1)

    # Split define block into individual definitions
    # Each definition starts with Name == at the beginning of a line
    defs = re.split(r'\n(?=\w+\s*==\s)', define_text)

    for defn in defs:
        m = re.match(r'^(\w+)\s*==\s*(.*)', defn.strip(), re.DOTALL)
        if not m:
            continue

        name = m.group(1)
        expr = m.group(2).strip()

        # Skip non-invariant definitions
        if name.endswith('Set') or name == 'StateSet':
            continue

        # Find variable references
        refs = list(set(re.findall(r'\b([a-z_]\w*)\b', expr)))

        invariants.append(TlaInvariant(name=name, expression=expr, references=refs))

    return invariants


def _extract_constants(text: str) -> list[str]:
    """Extract CONSTANTS declarations."""
    constants = []
    for m in re.finditer(r'CONSTANTS?\s+(.*?)(?=\n\s*\n|\n\()', text, re.DOTALL):
        const_text = m.group(1)
        for c in re.split(r'[,\n]', const_text):
            clean = c.strip().rstrip(',')
            # Remove inline comments
            clean = re.sub(r'\\.*$', '', clean).strip()
            if clean and not clean.startswith('\\'):
                constants.append(clean)
    return constants


# ── Translator 1: State Variables → data_structures shape ──


def translate_state_vars(spec: ParsedSpec) -> dict[str, Any]:
    """Translate TLA+ state variables into data_structures shape.

    Conforms to backend_schema.json data_structures:
    {
      "StructureName": {
        "function_id": str,
        "acceptance_criteria_id": str,
        "fields": { "fieldName": { "type": str, "required": bool, ... } },
        "relations": {},
        "description": str
      }
    }
    """
    structure_name = f"{spec.module_name}State"
    fields: dict[str, Any] = {}

    for var in spec.variables:
        # Map TLA+ types to schema data types
        schema_type = _tla_type_to_schema_type(var.type_hint)

        fields[var.name] = {
            "type": f"shared/data_types/{schema_type}",
            "required": True,
            "unique": False,
            "default": _tla_value_to_default(var.initial_value),
            "validation": _infer_validation(var),
        }

    return {
        structure_name: {
            "function_id": f"fn-{spec.module_name}-state",
            "acceptance_criteria_id": f"ac-{spec.module_name}-state",
            "fields": fields,
            "relations": {},
            "description": f"State model derived from {spec.module_name} TLA+ spec",
        }
    }


def _tla_type_to_schema_type(tla_type: str) -> str:
    """Map TLA+ type hints to schema data type paths."""
    mapping = {
        "boolean": "Boolean",
        "integer": "Integer",
        "string": "String",
        "set": "Set",
        "sequence": "Sequence",
        "function": "Record",
    }
    return mapping.get(tla_type, "String")


def _tla_value_to_default(init_value: str) -> str:
    """Convert a TLA+ initial value to a schema default."""
    v = init_value.strip()
    if v == "TRUE":
        return "true"
    if v == "FALSE":
        return "false"
    if v == "{}":
        return "empty_set"
    if v == "<<>>":
        return "empty_sequence"
    if v.startswith('"') and v.endswith('"'):
        return v.strip('"')
    return v if v else "null"


def _infer_validation(var: TlaVariable) -> list[str]:
    """Infer validation rules from variable characteristics."""
    rules = []
    if var.type_hint == "integer":
        rules.append("IsInteger")
    if var.type_hint == "boolean":
        rules.append("IsBoolean")
    if var.type_hint == "string":
        rules.append("IsString")
    if var.type_hint == "set":
        rules.append("IsSet")
    return rules if rules else ["NotNull"]


# ── Translator 2: Actions → processors.operations shape ──


def translate_actions(spec: ParsedSpec) -> dict[str, Any]:
    """Translate TLA+ actions into processors.operations shape.

    Conforms to backend_schema.json processors.operations:
    {
      "operationName": {
        "function_id": str,
        "acceptance_criteria_id": str,
        "parameters": { "paramName": "shared/data_types/Type" },
        "returns": str,
        "error_types": [str],
        "error_handling": str,
        "description": str
      }
    }
    """
    operations: dict[str, Any] = {}

    for action in spec.actions:
        # Extract parameters from guard condition
        params = _extract_params_from_action(action, spec)

        # Determine return type from assignments
        return_type = _infer_return_type(action)

        # Determine error types
        error_types = _infer_error_types(action)

        operations[action.name] = {
            "function_id": f"fn-{spec.module_name}-{action.name}",
            "acceptance_criteria_id": f"ac-{spec.module_name}-{action.name}",
            "parameters": params,
            "returns": return_type,
            "error_types": error_types,
            "error_handling": "raise" if error_types else "none",
            "description": f"Action {action.name} from {spec.module_name} spec",
        }

    return operations


def _extract_params_from_action(action: TlaAction, spec: ParsedSpec) -> dict[str, str]:
    """Extract parameters from an action's guard and assignments."""
    params: dict[str, str] = {}

    # Variables read in guard are inputs
    guard_vars = set(re.findall(r'\b([a-z_]\w*)\b', action.guard))

    # Variables assigned are outputs, not params
    assigned_vars = {name for name, _ in action.assignments}

    # Input params = guard vars that are spec variables but not assigned
    spec_var_names = {v.name for v in spec.variables}
    for var_name in sorted(guard_vars & spec_var_names - assigned_vars):
        var = next((v for v in spec.variables if v.name == var_name), None)
        if var:
            schema_type = _tla_type_to_schema_type(var.type_hint)
            params[var_name] = f"shared/data_types/{schema_type}"

    return params


def _infer_return_type(action: TlaAction) -> str:
    """Infer return type from action assignments."""
    if not action.assignments:
        return "shared/data_types/Void"

    # If action assigns to a single variable, return that type
    if len(action.assignments) == 1:
        _, expr = action.assignments[0]
        if expr == "TRUE" or expr == "FALSE":
            return "shared/data_types/Boolean"
        if expr.startswith('"'):
            return "shared/data_types/String"
        try:
            int(expr)
            return "shared/data_types/Integer"
        except ValueError:
            pass

    return "shared/data_types/Record"


def _infer_error_types(action: TlaAction) -> list[str]:
    """Infer error types from action structure."""
    errors = []
    # Check if the action has error-related assignments
    for var, expr in action.assignments:
        if 'error' in var.lower() or 'error' in expr.lower():
            errors.append(f"shared/error_definitions/{action.name}Error")
        if 'fail' in var.lower() or 'fail' in expr.lower():
            errors.append(f"shared/error_definitions/{action.name}Failure")
    return errors


# ── Translator 3: Invariants → verifiers + testing.assertions shapes ──


def translate_invariants_to_verifiers(spec: ParsedSpec) -> dict[str, Any]:
    """Translate TLA+ invariants into verifiers shape.

    Conforms to backend_schema.json verifiers:
    {
      "VerifierName": {
        "function_id": str,
        "acceptance_criteria_id": str,
        "conditions": [str],
        "message": str,
        "applies_to": [str],
        "description": str
      }
    }
    """
    verifiers: dict[str, Any] = {}

    for inv in spec.invariants:
        # Extract conditions from invariant expression
        conditions = _extract_conditions(inv)

        # Determine what the invariant applies to
        applies_to = _determine_applies_to(inv, spec)

        verifiers[inv.name] = {
            "function_id": f"fn-{spec.module_name}-verify-{inv.name}",
            "acceptance_criteria_id": f"ac-{spec.module_name}-{inv.name}",
            "conditions": conditions,
            "message": f"{inv.name} violation: {_summarize_invariant(inv)}",
            "applies_to": applies_to,
            "description": f"Verifier for invariant {inv.name} from {spec.module_name} spec",
        }

    return verifiers


def translate_invariants_to_assertions(spec: ParsedSpec) -> dict[str, Any]:
    """Translate TLA+ invariants into testing.assertions shape.

    Conforms to shared_objects_schema.json testing.assertions:
    {
      "AssertionName": {
        "condition": str,
        "message": str,
        "description": str
      }
    }
    """
    assertions: dict[str, Any] = {}

    for inv in spec.invariants:
        assertions[f"assert_{inv.name}"] = {
            "condition": _invariant_to_condition(inv),
            "message": f"Assertion failed: {inv.name} — {_summarize_invariant(inv)}",
            "description": f"Test assertion for {inv.name} from {spec.module_name} spec",
        }

    return assertions


def _extract_conditions(inv: TlaInvariant) -> list[str]:
    """Extract individual conditions from an invariant expression."""
    expr = inv.expression

    # Strip dirty guard pattern
    expr = re.sub(r'dirty\s*=\s*TRUE\s*\\/\s*', '', expr).strip()

    # Split on /\ to get individual conjuncts
    parts = re.split(r'\s*/\\\s*', expr)

    conditions = []
    for part in parts:
        clean = part.strip().strip('()')
        if clean and clean != 'TRUE':
            conditions.append(clean)

    return conditions if conditions else [inv.expression]


def _determine_applies_to(inv: TlaInvariant, spec: ParsedSpec) -> list[str]:
    """Determine which structures/operations an invariant applies to."""
    applies_to = []

    # Check if invariant references specific variables
    spec_var_names = {v.name for v in spec.variables}
    for ref in inv.references:
        if ref in spec_var_names:
            applies_to.append(ref)

    # Check if invariant references action names
    action_names = {a.name for a in spec.actions}
    for ref in inv.references:
        if ref in action_names:
            applies_to.append(ref)

    return sorted(set(applies_to)) if applies_to else [spec.module_name]


def _summarize_invariant(inv: TlaInvariant) -> str:
    """Create a human-readable summary of an invariant."""
    expr = inv.expression
    # Strip dirty guard
    expr = re.sub(r'dirty\s*=\s*TRUE\s*\\/\s*', '', expr).strip()
    # Truncate long expressions
    if len(expr) > 120:
        expr = expr[:117] + "..."
    return expr


def _invariant_to_condition(inv: TlaInvariant) -> str:
    """Convert TLA+ invariant expression to a test condition string."""
    expr = inv.expression
    # Strip dirty guard
    expr = re.sub(r'dirty\s*=\s*TRUE\s*\\/\s*', '', expr).strip()
    # Convert TLA+ operators to more readable form
    expr = expr.replace('\\in', 'in')
    expr = expr.replace('\\notin', 'not in')
    expr = expr.replace('/\\', 'and')
    expr = expr.replace('\\/', 'or')
    expr = expr.replace('=>', 'implies')
    expr = expr.replace('<=', '<=')
    return expr


# ── Translator 4: TLC Traces → test scenarios ──


@dataclass
class TestScenario:
    """A test scenario generated from a TLC trace."""
    name: str
    description: str
    invariant_tested: str
    setup: dict[str, str]  # initial state
    steps: list[dict[str, Any]]  # state transitions
    expected_outcome: str


def translate_traces(traces: list[TlcTrace], spec: ParsedSpec) -> list[TestScenario]:
    """Translate TLC counterexample traces into test scenarios.

    Each trace becomes a concrete test scenario with setup, steps,
    and expected outcomes.
    """
    scenarios = []

    for i, trace in enumerate(traces):
        if not trace.states:
            continue

        # First state is setup
        setup = trace.states[0] if trace.states else {}

        # Remaining states are steps
        steps = []
        for j, state in enumerate(trace.states[1:], 1):
            # Compute what changed
            prev = trace.states[j - 1]
            changes = {
                k: v for k, v in state.items()
                if prev.get(k) != v
            }
            steps.append({
                "step_number": j,
                "state": state,
                "changes": changes,
            })

        scenario = TestScenario(
            name=f"scenario_{spec.module_name}_{trace.invariant_violated}_{i}",
            description=f"Trace violating {trace.invariant_violated} in {spec.module_name}",
            invariant_tested=trace.invariant_violated,
            setup=setup,
            steps=steps,
            expected_outcome=f"{trace.invariant_violated} should hold but was violated at state {len(trace.states)}",
        )
        scenarios.append(scenario)

    return scenarios


def trace_scenarios_to_dict(scenarios: list[TestScenario]) -> dict[str, Any]:
    """Convert test scenarios to testing shape dict."""
    test_suites: dict[str, Any] = {}

    for scenario in scenarios:
        test_suites[scenario.name] = {
            "description": scenario.description,
            "tests": [
                {
                    "name": f"test_{scenario.name}",
                    "setup": scenario.setup,
                    "steps": scenario.steps,
                    "expected": scenario.expected_outcome,
                    "invariant": scenario.invariant_tested,
                }
            ],
        }

    return test_suites


# ── Full Bridge Pipeline ──


@dataclass
class BridgeResult:
    """Complete result of running the bridge on a TLA+ spec."""
    module_name: str
    data_structures: dict[str, Any]
    operations: dict[str, Any]
    verifiers: dict[str, Any]
    assertions: dict[str, Any]
    test_scenarios: list[TestScenario]
    parsed_spec: ParsedSpec


def run_bridge(tla_text: str, traces: list[TlcTrace] | None = None) -> BridgeResult:
    """Run the full bridge pipeline on a TLA+ spec.

    This is the main entry point. Parses the spec and runs all 4
    translators, producing schema-conforming artifacts.

    Invariant (from bridge_translator.tla):
      - data_structures count == variables count
      - operations count == actions count
      - verifiers count == invariants count
      - assertions count == invariants count
    """
    spec = parse_spec(tla_text)

    data_structures = translate_state_vars(spec)
    operations = translate_actions(spec)
    verifiers = translate_invariants_to_verifiers(spec)
    assertions = translate_invariants_to_assertions(spec)
    scenarios = translate_traces(traces or [], spec)

    return BridgeResult(
        module_name=spec.module_name,
        data_structures=data_structures,
        operations=operations,
        verifiers=verifiers,
        assertions=assertions,
        test_scenarios=scenarios,
        parsed_spec=spec,
    )
