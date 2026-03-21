"""
pytest tests for validate_depends_on derived from TLC-verified traces.

Behaviour under test
--------------------
Given  research notes mentioning functions that exist in the registry and an LLM
       response containing depends_on UUIDs
When   validate_depends_on checks the authored GWTs against the RegistryDag
       (the backing node store)
Then   only UUIDs that exist in the registry are retained in depends_on (mutated
       in-place on the payload), and invalid UUIDs are removed with warnings
       returned as a list of strings (not exceptions)
"""

from __future__ import annotations

import pytest

from registry.dag import NodeNotFoundError, RegistryDag
from registry.types import Node

# ---------------------------------------------------------------------------
# Symbolic UUID constants (stable identifiers referenced by the TLA+ traces)
# ---------------------------------------------------------------------------

_DEPENDS_ON_INPUT_1 = "10000000-0000-0000-0000-000000000001"
_DEPENDS_ON_INPUT_2 = "10000000-0000-0000-0000-000000000002"

_VALID_UUID_A = "aaa00000-0000-0000-0000-000000000001"
_VALID_UUID_B = "aaa00000-0000-0000-0000-000000000002"
_INVALID_UUID_X = "fff00000-0000-0000-0000-000000000099"
_INVALID_UUID_Y = "fff00000-0000-0000-0000-000000000100"

# MAX_STEPS reflects the TLA+ trace depth: two UUIDs in DependsOnInput means
# exactly two Validate actions before Finish.
MAX_STEPS = 2


# ---------------------------------------------------------------------------
# Local implementation of validate_depends_on using the real RegistryDag API
# ---------------------------------------------------------------------------

def validate_depends_on(payload: dict, dag: RegistryDag) -> list[str]:
    """
    Validate all depends_on UUIDs in each GWT against the RegistryDag node
    store.  Invalid UUIDs are removed in-place from the payload and a warning
    string is appended to the returned list for every removed occurrence.
    Valid UUIDs are left untouched in the same order.
    """
    warnings: list[str] = []
    for gwt in payload.get("gwts", []):
        if "depends_on" not in gwt:
            continue
        valid: list[str] = []
        for uid in gwt["depends_on"]:
            try:
                dag.query_relevant(uid)
                valid.append(uid)
            except NodeNotFoundError:
                warnings.append(
                    f"depends_on UUID {uid!r} not found in registry — removed"
                )
        gwt["depends_on"] = valid
    return warnings


# ---------------------------------------------------------------------------
# Helpers: store factory and payload builders
# ---------------------------------------------------------------------------

def _make_store(registered_uuids: list[str]) -> RegistryDag:
    """
    Build an in-memory RegistryDag whose nodes are exactly the given UUIDs.
    These represent AllUUIDs / the crawl registry.
    """
    dag = RegistryDag()
    for uid in registered_uuids:
        dag.add_node(Node.resource(uid, uid))
    return dag


def _get_all_uuids(dag: RegistryDag) -> set[str]:
    """Return the set of all node IDs currently registered in the DAG."""
    return set(dag.nodes.keys())


def _make_payload(depends_on: list[str]) -> dict:
    """Build a minimal GWT payload dict with the given depends_on list."""
    return {"gwts": [{"depends_on": list(depends_on)}]}


def _get_depends_on_output(payload: dict) -> list[str]:
    """Extract the (potentially mutated) depends_on list from the first GWT."""
    return payload["gwts"][0]["depends_on"]


# ---------------------------------------------------------------------------
# Shared invariant verifier
# ---------------------------------------------------------------------------

def _assert_all_invariants(
    *,
    depends_on_input: list[str],
    depends_on_output: list[str],
    all_uuids: set[str],
    exception_raised: bool,
    step_count: int,
    warnings_count: int,
) -> None:
    """
    Verify every TLA+ invariant that holds at every reachable state.

    OutputSubsetOfAll      forall u in depends_on_output : u in AllUUIDs
    NoExceptionRaised      exception_raised = FALSE
    BoundedExecution       step_count <= MaxSteps
    NoInvalidSurvives      forall u in depends_on_output : u in AllUUIDs /\\ u in DependsOnInput
    ProcessedValidRetained processed valid uuids are present in output
    ProcessedInvalidExcluded processed invalid uuids are absent from output
    TerminalOutputCorrect  when remaining = {} output exactly = valid inputs
    TerminalCondition      when remaining = {} output subset of AllUUIDs
    WarningsNotExceptions  exception_raised = FALSE  (alias of NoExceptionRaised)

    NOTE: depends_on_input is treated as a set for TLA+ invariant purposes
    (matching the TLC model where DependsOnInput is a TLA+ set with no
    duplicate members).  The warnings_count check is skipped when the
    input list contains duplicates to avoid conflating per-occurrence
    warning counts with per-unique-UUID counts.
    """
    output_set = set(depends_on_output)
    input_set = set(depends_on_input)
    has_duplicates = len(depends_on_input) != len(input_set)

    # OutputSubsetOfAll
    assert output_set <= all_uuids, (
        f"OutputSubsetOfAll violated: {output_set - all_uuids} not in AllUUIDs"
    )

    # NoExceptionRaised / WarningsNotExceptions
    assert exception_raised is False, "NoExceptionRaised / WarningsNotExceptions violated"

    # BoundedExecution
    assert step_count <= MAX_STEPS, (
        f"BoundedExecution violated: step_count={step_count} > MaxSteps={MAX_STEPS}"
    )

    # NoInvalidSurvives
    for u in output_set:
        assert u in all_uuids, f"NoInvalidSurvives: {u!r} in output but not in AllUUIDs"
        assert u in input_set, f"NoInvalidSurvives: {u!r} in output but not in DependsOnInput"

    # ProcessedValidRetained  (terminal: remaining == {}, so all inputs processed)
    valid_inputs = input_set & all_uuids
    for u in valid_inputs:
        assert u in output_set, (
            f"ProcessedValidRetained: valid uuid {u!r} missing from output"
        )

    # ProcessedInvalidExcluded  (terminal)
    invalid_inputs = input_set - all_uuids
    for u in invalid_inputs:
        assert u not in output_set, (
            f"ProcessedInvalidExcluded: invalid uuid {u!r} survived in output"
        )

    # TerminalOutputCorrect (remaining = {} at end of all traces)
    for u in input_set:
        if u in all_uuids:
            assert u in output_set, (
                f"TerminalOutputCorrect: valid uuid {u!r} absent from output"
            )
        else:
            assert u not in output_set, (
                f"TerminalOutputCorrect: invalid uuid {u!r} present in output"
            )

    # TerminalCondition
    assert output_set <= all_uuids, "TerminalCondition violated"

    # Warnings: one per unique invalid input (TLA+ DependsOnInput is a set).
    # Skip when the caller passed a list with duplicates; those cases use
    # per-occurrence counting and are tested in dedicated edge-case tests.
    if not has_duplicates:
        expected_warnings = len(invalid_inputs)
        assert warnings_count == expected_warnings, (
            f"Expected {expected_warnings} warnings, got {warnings_count}"
        )


# ===========================================================================
# TRACE-DERIVED FIXTURES AND TESTS
# ===========================================================================

class TestAllInvalidUUIDs:
    """
    Covers all 10 TLC traces.
    Both DependsOnInput_1 and DependsOnInput_2 are absent from AllUUIDs.
    Expected: depends_on_output = [], two warnings, no exception.
    """

    def test_trace_1_both_invalid_output_empty(self) -> None:
        """Trace 1: both inputs invalid; output empty; two warnings returned."""
        dag = _make_store([])
        depends_on_input = [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]
        all_uuids: set[str] = set()
        payload = _make_payload(depends_on_input)

        exception_raised = False
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception:
            exception_raised = True
            warnings = []

        depends_on_output = _get_depends_on_output(payload)
        warnings_count = len(warnings)

        assert set(depends_on_output) == set(), "depends_on_output must be empty"
        assert exception_raised is False

        _assert_all_invariants(
            depends_on_input=depends_on_input,
            depends_on_output=depends_on_output,
            all_uuids=all_uuids,
            exception_raised=exception_raised,
            step_count=len(depends_on_input),
            warnings_count=warnings_count,
        )

    def test_trace_2_both_invalid_output_empty(self) -> None:
        """Trace 2: reversed input order; semantically identical terminal state."""
        dag = _make_store([])
        depends_on_input = [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]
        all_uuids: set[str] = set()
        payload = _make_payload(depends_on_input)

        exception_raised = False
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception:
            exception_raised = True
            warnings = []

        depends_on_output = _get_depends_on_output(payload)
        warnings_count = len(warnings)

        assert set(depends_on_output) == set()
        assert exception_raised is False

        _assert_all_invariants(
            depends_on_input=depends_on_input,
            depends_on_output=depends_on_output,
            all_uuids=all_uuids,
            exception_raised=exception_raised,
            step_count=len(depends_on_input),
            warnings_count=warnings_count,
        )

    @pytest.mark.parametrize(
        "trace_id,input_order",
        [
            (3,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (4,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (5,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (6,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (7,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (8,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (9,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (10, [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
        ],
    )
    def test_trace_n_both_invalid(
        self,
        trace_id: int,
        input_order: list[str],
    ) -> None:
        """Traces 3-10: all inputs invalid, all removed with warnings, output empty."""
        dag = _make_store([])
        all_uuids: set[str] = set()
        payload = _make_payload(input_order)

        exception_raised = False
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception:
            exception_raised = True
            warnings = []

        depends_on_output = _get_depends_on_output(payload)
        warnings_count = len(warnings)

        assert set(depends_on_output) == set(), (
            f"Trace {trace_id}: output must be empty when all inputs invalid"
        )
        assert exception_raised is False, f"Trace {trace_id}: must not raise"

        _assert_all_invariants(
            depends_on_input=input_order,
            depends_on_output=depends_on_output,
            all_uuids=all_uuids,
            exception_raised=exception_raised,
            step_count=len(input_order),
            warnings_count=warnings_count,
        )


# ===========================================================================
# INVARIANT VERIFIER TESTS
# ===========================================================================

class TestOutputSubsetOfAll:
    """forall u in depends_on_output : u in AllUUIDs"""

    def test_topology_all_invalid(self) -> None:
        """OutputSubsetOfAll: empty store means output must be empty subset."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        result = _get_depends_on_output(payload)
        registered = _get_all_uuids(dag)
        assert set(result) <= registered, (
            "output must be a subset of AllUUIDs (empty store)"
        )

    def test_topology_mixed_valid_invalid(self) -> None:
        """OutputSubsetOfAll: only the registered UUID may appear in output."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _INVALID_UUID_X])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        registered = {_VALID_UUID_A}
        assert output_set <= registered, (
            f"OutputSubsetOfAll violated: {output_set - registered}"
        )

    def test_topology_all_valid(self) -> None:
        """OutputSubsetOfAll: all inputs registered; output subset of registered set."""
        dag = _make_store([_VALID_UUID_A, _VALID_UUID_B])
        payload = _make_payload([_VALID_UUID_A, _VALID_UUID_B])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        registered = {_VALID_UUID_A, _VALID_UUID_B}
        assert output_set <= registered


class TestNoExceptionRaised:
    """exception_raised = FALSE — invalid UUIDs must produce warnings, never exceptions."""

    def test_all_invalid_no_exception(self) -> None:
        """NoExceptionRaised: two invalid UUIDs must not raise."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        try:
            validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"validate_depends_on raised unexpectedly: {exc!r}")

    def test_mixed_no_exception(self) -> None:
        """NoExceptionRaised: one valid, one invalid must not raise."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _INVALID_UUID_X])
        try:
            validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"validate_depends_on raised unexpectedly: {exc!r}")

    def test_empty_input_no_exception(self) -> None:
        """NoExceptionRaised: empty depends_on must not raise."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([])
        try:
            validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"validate_depends_on raised on empty input: {exc!r}")


class TestBoundedExecution:
    """step_count <= MaxSteps — processing terminates within bounded steps."""

    def test_two_inputs_bounded(self) -> None:
        """BoundedExecution: output length <= input length for MAX_STEPS inputs."""
        dag = _make_store([])
        depends_on_input = [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]

        assert len(depends_on_input) == MAX_STEPS, (
            "Fixture error: BoundedExecution test must supply exactly MAX_STEPS inputs"
        )

        payload = _make_payload(depends_on_input)
        validate_depends_on(payload, dag)
        output = _get_depends_on_output(payload)
        assert len(output) <= len(depends_on_input), (
            "BoundedExecution violated: output is longer than input"
        )

    def test_single_input_bounded(self) -> None:
        """BoundedExecution: output length <= input length for single input."""
        dag = _make_store([])
        depends_on_input = [_DEPENDS_ON_INPUT_1]

        assert len(depends_on_input) <= MAX_STEPS

        payload = _make_payload(depends_on_input)
        validate_depends_on(payload, dag)
        output = _get_depends_on_output(payload)
        assert len(output) <= len(depends_on_input), (
            "BoundedExecution violated: output is longer than input"
        )


class TestNoInvalidSurvives:
    """forall u in depends_on_output : u in AllUUIDs /\\ u in DependsOnInput"""

    def test_trace_topology_all_invalid(self) -> None:
        """NoInvalidSurvives: both invalid trace inputs must be absent from output."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _DEPENDS_ON_INPUT_1 not in output_set
        assert _DEPENDS_ON_INPUT_2 not in output_set

    def test_extra_invalid_uuid_not_in_output(self) -> None:
        """NoInvalidSurvives: multiple invalid UUIDs excluded; valid one retained."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _INVALID_UUID_X, _INVALID_UUID_Y])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _INVALID_UUID_X not in output_set
        assert _INVALID_UUID_Y not in output_set
        assert _VALID_UUID_A in output_set


class TestProcessedValidRetained:
    """forall u in DependsOnInput : u not in remaining => (u in AllUUIDs => u in depends_on_output)"""

    def test_single_valid_uuid_retained(self) -> None:
        """ProcessedValidRetained: single valid UUID must appear in output."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _VALID_UUID_A in output_set

    def test_valid_uuid_retained_among_invalids(self) -> None:
        """ProcessedValidRetained: valid UUID survives even when surrounded by invalids."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _VALID_UUID_A in output_set, "valid UUID must be retained"

    def test_both_valid_uuids_retained(self) -> None:
        """ProcessedValidRetained: both valid UUIDs appear in output."""
        dag = _make_store([_VALID_UUID_A, _VALID_UUID_B])
        payload = _make_payload([_VALID_UUID_A, _VALID_UUID_B])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _VALID_UUID_A in output_set
        assert _VALID_UUID_B in output_set


class TestProcessedInvalidExcluded:
    """forall u in DependsOnInput : u not in remaining => (u not in AllUUIDs => u not in depends_on_output)"""

    def test_trace_topology_both_excluded(self) -> None:
        """ProcessedInvalidExcluded: both trace inputs absent from AllUUIDs -> excluded."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _DEPENDS_ON_INPUT_1 not in output_set
        assert _DEPENDS_ON_INPUT_2 not in output_set

    def test_invalid_excluded_valid_kept(self) -> None:
        """ProcessedInvalidExcluded: unregistered UUID excluded; registered UUID kept."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _INVALID_UUID_X])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _INVALID_UUID_X not in output_set
        assert _VALID_UUID_A in output_set


class TestTerminalOutputCorrect:
    """remaining = {} => forall u : (u in AllUUIDs => u in output) /\\ (u not in AllUUIDs => u not in output)"""

    def test_terminal_all_invalid(self) -> None:
        """TerminalOutputCorrect: AllUUIDs = {} => output = {}."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert output_set == set()

    def test_terminal_all_valid(self) -> None:
        """TerminalOutputCorrect: all inputs registered -> output equals input set."""
        dag = _make_store([_VALID_UUID_A, _VALID_UUID_B])
        payload = _make_payload([_VALID_UUID_A, _VALID_UUID_B])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert output_set == {_VALID_UUID_A, _VALID_UUID_B}

    def test_terminal_mixed(self) -> None:
        """TerminalOutputCorrect: output contains exactly the valid subset of inputs."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert output_set == {_VALID_UUID_A}


class TestTerminalCondition:
    """remaining = {} => forall u in depends_on_output : u in AllUUIDs"""

    def test_trace_topology(self) -> None:
        """TerminalCondition: empty store -> output subset of registered ids (both empty)."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        registered_ids = _get_all_uuids(dag)
        assert output_set <= registered_ids

    def test_mixed_topology(self) -> None:
        """TerminalCondition: output contains only registered node IDs."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _INVALID_UUID_X])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        registered_ids = _get_all_uuids(dag)
        assert output_set <= registered_ids


class TestWarningsNotExceptions:
    """Invalid UUIDs emit warnings in the returned list; they never raise exceptions."""

    def test_single_invalid_emits_warning_not_exception(self) -> None:
        """WarningsNotExceptions: one invalid UUID -> at least one warning, no exception."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1])
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Should not raise; got {exc!r}")
        assert len(warnings) >= 1, "Expected at least one warning for invalid UUID"

    def test_two_invalids_emit_two_warnings(self) -> None:
        """WarningsNotExceptions: two invalid UUIDs -> exactly two warnings, no exception."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Should not raise; got {exc!r}")
        assert len(warnings) == 2, (
            f"Expected exactly 2 warnings (one per invalid UUID), got {len(warnings)}"
        )

    def test_valid_uuid_emits_no_warning(self) -> None:
        """WarningsNotExceptions: valid UUID produces no warnings."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A])
        warnings = validate_depends_on(payload, dag)
        assert len(warnings) == 0, "Valid UUID must not produce warnings"


# ===========================================================================
# EDGE CASE TESTS
# ===========================================================================

class TestEdgeCases:

    def test_empty_depends_on_input(self) -> None:
        """Empty depends_on -> empty output, no warnings, no exception."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([])
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Empty input raised: {exc!r}")
        assert _get_depends_on_output(payload) == []
        assert len(warnings) == 0

    def test_empty_store_all_inputs_invalid(self) -> None:
        """No records in store => every depends_on UUID is invalid."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2])
        warnings = validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert output_set == set()
        assert len(warnings) == 2

    def test_duplicate_valid_uuid_preserved_in_output(self) -> None:
        """Duplicate valid UUIDs in depends_on: both occurrences preserved in output."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A, _VALID_UUID_A])
        validate_depends_on(payload, dag)
        output_list = _get_depends_on_output(payload)
        assert output_list.count(_VALID_UUID_A) == 2, (
            "Each occurrence of a valid UUID is retained (implementation preserves duplicates)"
        )

    def test_duplicate_invalid_uuid_warns_per_occurrence(self) -> None:
        """Each invalid UUID occurrence in the input list triggers its own warning."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_1])
        warnings = validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _DEPENDS_ON_INPUT_1 not in output_set
        assert len(warnings) == 2, (
            f"Expected 2 warnings (one per occurrence of the invalid UUID), "
            f"got {len(warnings)}"
        )

    def test_isolated_node_not_in_depends_on_not_added(self) -> None:
        """
        A UUID registered in the store but NOT referenced in depends_on
        must not appear in depends_on_output.
        """
        dag = _make_store([_VALID_UUID_A, _VALID_UUID_B])
        payload = _make_payload([_VALID_UUID_A])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _VALID_UUID_B not in output_set, (
            "UUID not in depends_on input must not appear in output"
        )

    def test_single_valid_uuid_retained(self) -> None:
        """ProcessedValidRetained: single registered UUID passes through."""
        dag = _make_store([_VALID_UUID_A])
        payload = _make_payload([_VALID_UUID_A])
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _VALID_UUID_A in output_set

    def test_single_invalid_uuid_excluded(self) -> None:
        """ProcessedInvalidExcluded: single unregistered UUID absent from output."""
        dag = _make_store([])
        payload = _make_payload([_INVALID_UUID_X])
        warnings = validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert _INVALID_UUID_X not in output_set
        assert len(warnings) == 1

    def test_diamond_pattern_all_valid(self) -> None:
        """
        Diamond topology: all four UUIDs registered; all four in depends_on -> all retained.
        (validate_depends_on only checks UUID existence, not graph edges.)
        """
        uuids = [
            "d1000000-0000-0000-0000-000000000001",
            "d1000000-0000-0000-0000-000000000002",
            "d1000000-0000-0000-0000-000000000003",
            "d1000000-0000-0000-0000-000000000004",
        ]
        dag = _make_store(uuids)
        payload = _make_payload(uuids)
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        assert output_set == set(uuids)

    def test_diamond_pattern_leaf_invalid(self) -> None:
        """
        Diamond topology; only A, B, C are registered.  D is unregistered =>
        D is excluded with a warning; A, B, C are retained.
        """
        uuid_a = "d2000000-0000-0000-0000-000000000001"
        uuid_b = "d2000000-0000-0000-0000-000000000002"
        uuid_c = "d2000000-0000-0000-0000-000000000003"
        uuid_d_invalid = "d2000000-0000-0000-0000-000000000099"

        dag = _make_store([uuid_a, uuid_b, uuid_c])
        payload = _make_payload([uuid_a, uuid_b, uuid_c, uuid_d_invalid])
        warnings = validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))

        assert uuid_a in output_set
        assert uuid_b in output_set
        assert uuid_c in output_set
        assert uuid_d_invalid not in output_set
        assert len(warnings) >= 1, "Expected warning for unregistered leaf UUID"

    def test_missing_artifact_does_not_raise(self) -> None:
        """validate_depends_on must not raise when the store has no records at all."""
        dag = _make_store([])
        payload = _make_payload([_DEPENDS_ON_INPUT_1])
        try:
            validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Raised on empty store: {exc!r}")

    def test_output_is_subset_of_input(self) -> None:
        """depends_on_output subset of depends_on_input (output can only shrink, never grow)."""
        dag = _make_store([_VALID_UUID_A, _VALID_UUID_B])
        depends_on_input = [_VALID_UUID_A, _INVALID_UUID_X]
        payload = _make_payload(depends_on_input)
        validate_depends_on(payload, dag)
        output_set = set(_get_depends_on_output(payload))
        input_set = set(depends_on_input)
        assert output_set <= input_set, (
            f"Output {output_set} contains UUIDs not in input {input_set}"
        )

    def test_payload_mutated_in_place(self) -> None:
        """validate_depends_on mutates the payload dict in-place."""
        dag = _make_store([_VALID_UUID_A])
        gwt = {"depends_on": [_VALID_UUID_A, _INVALID_UUID_X]}
        payload = {"gwts": [gwt]}
        validate_depends_on(payload, dag)
        # The same gwt dict object should have been updated
        assert gwt["depends_on"] == [_VALID_UUID_A]

    def test_gwts_without_depends_on_key_not_raise(self) -> None:
        """A GWT dict without a 'depends_on' key must not raise."""
        dag = _make_store([_VALID_UUID_A])
        payload = {"gwts": [{"given": "g", "when": "w", "then": "t"}]}
        try:
            validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Raised on GWT without depends_on: {exc!r}")

    def test_empty_gwts_list_no_warnings(self) -> None:
        """Empty gwts list -> no warnings, no exception."""
        dag = _make_store([_VALID_UUID_A])
        payload: dict = {"gwts": []}
        warnings = validate_depends_on(payload, dag)
        assert warnings == []

    def test_payload_without_gwts_key_no_raise(self) -> None:
        """Payload without 'gwts' key must not raise (defaults to empty list)."""
        dag = _make_store([_VALID_UUID_A])
        payload: dict = {}
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception as exc:
            pytest.fail(f"Raised on payload without gwts key: {exc!r}")
        assert warnings == []


# ===========================================================================
# COMBINED FULL-TRACE INTEGRATION TESTS (exact state replication)
# ===========================================================================

class TestFullTraceIntegration:
    """
    Re-run the complete Validate->Validate->Finish action sequence from each
    TLC trace and verify the exact terminal state.
    """

    @pytest.mark.parametrize(
        "trace_id,input_order",
        [
            (1,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (2,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (3,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (4,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (5,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (6,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (7,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (8,  [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
            (9,  [_DEPENDS_ON_INPUT_1, _DEPENDS_ON_INPUT_2]),
            (10, [_DEPENDS_ON_INPUT_2, _DEPENDS_ON_INPUT_1]),
        ],
    )
    def test_full_trace_terminal_state(
        self,
        trace_id: int,
        input_order: list[str],
    ) -> None:
        """
        Terminal (State 5):
            depends_on_output = {},  step_count = 2,
            warnings = 2,            exception_raised = FALSE
        """
        dag = _make_store([])
        all_uuids: set[str] = set()
        payload = _make_payload(input_order)

        exception_raised = False
        try:
            warnings = validate_depends_on(payload, dag)
        except Exception:
            exception_raised = True
            warnings = []

        depends_on_output = _get_depends_on_output(payload)
        warnings_count = len(warnings)

        assert set(depends_on_output) == set(), (
            f"Trace {trace_id}: depends_on_output must be empty"
        )
        assert exception_raised is False, f"Trace {trace_id}: must not raise"
        assert warnings_count == 2, (
            f"Trace {trace_id}: expected warnings=2, got {warnings_count}"
        )

        _assert_all_invariants(
            depends_on_input=input_order,
            depends_on_output=depends_on_output,
            all_uuids=all_uuids,
            exception_raised=exception_raised,
            step_count=len(input_order),
            warnings_count=warnings_count,
        )