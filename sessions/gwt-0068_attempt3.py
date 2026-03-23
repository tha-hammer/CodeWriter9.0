import json
import pytest
from pathlib import Path
from cross_cutting_rules_loader import load_cross_cutting_rules, CrossCuttingRule

# ---------------------------------------------------------------------------
# Constants mirroring the TLA+ spec
# ---------------------------------------------------------------------------
VALID_POSITIONS = {"pre", "post", "wrap"}

GOOD_RULE = {
    "resource_type": "database",
    "required_outs": ["audit_event"],
    "position": "wrap",
}

BAD_POSITION_RULE = {
    "resource_type": "database",
    "required_outs": ["audit_event"],
    "position": "INVALID",
}

# ---------------------------------------------------------------------------
# Invariant helpers (TLA+ invariants expressed as Python assertions)
# ---------------------------------------------------------------------------

def assert_no_partial_results(rules: list, error_raised: bool) -> None:
    """NoPartialResults: error /= '' => result = {}"""
    if error_raised:
        assert rules == [], (
            "NoPartialResults violated: error was raised but result is non-empty"
        )


def assert_valid_position_only(rules: list) -> None:
    """ValidPositionOnly: forall r in result : r.position in ValidPositions"""
    for rule in rules:
        assert rule.position in VALID_POSITIONS, (
            f"ValidPositionOnly violated: position '{rule.position}' not in {VALID_POSITIONS}"
        )


def assert_complete_fields(rules: list) -> None:
    """CompleteFields: forall r in result : resource_type, required_outs, position all present"""
    for rule in rules:
        assert hasattr(rule, "resource_type"), "CompleteFields violated: missing resource_type"
        assert hasattr(rule, "required_outs"), "CompleteFields violated: missing required_outs"
        assert hasattr(rule, "position"),      "CompleteFields violated: missing position"


def assert_safe_result(rules: list, error_raised: bool) -> None:
    """SafeResult: in terminal phase -> either (no error and all positions valid) or (error and empty result)"""
    if error_raised:
        assert rules == [], (
            "SafeResult violated: error raised but result non-empty"
        )
    else:
        assert_valid_position_only(rules)


def assert_all_invariants(rules: list, error_raised: bool) -> None:
    """Verify all TLA+ invariants simultaneously against a terminal result."""
    assert_no_partial_results(rules, error_raised)
    assert_safe_result(rules, error_raised)
    if not error_raised and rules:
        assert_valid_position_only(rules)
        assert_complete_fields(rules)


# ---------------------------------------------------------------------------
# Trace 1 — file exists, valid JSON, missing required fields -> ValueError
# ---------------------------------------------------------------------------

def test_trace1_missing_fields_raises_value_error(tmp_path: Path) -> None:
    """
    Trace 1: file_exists=TRUE, json_valid=TRUE, all_fields_present=FALSE.
    ValidateRules detects absent required keys and raises ValueError.
    """
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps([{"extra_key": "value"}]))

    error_raised = True
    rules: list = []

    with pytest.raises(ValueError):
        rules = load_cross_cutting_rules(str(rules_file))

    assert_all_invariants(rules, error_raised)


# ---------------------------------------------------------------------------
# Traces 2-3, 5-8, 10 — file does not exist -> FileNotFoundError
# ---------------------------------------------------------------------------

def _assert_file_not_found(path: str) -> None:
    error_raised = True
    rules: list = []
    with pytest.raises(FileNotFoundError):
        rules = load_cross_cutting_rules(path)
    assert_all_invariants(rules, error_raised)


def test_trace2_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 2: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "nonexistent_rules.json"))


def test_trace3_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 3: file_exists=FALSE -> FileNotFoundError (duplicate structural path)."""
    _assert_file_not_found(str(tmp_path / "missing.json"))


def test_trace5_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 5: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "rules_5.json"))


def test_trace6_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 6: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "rules_6.json"))


def test_trace7_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 7: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "rules_7.json"))


def test_trace8_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 8: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "rules_8.json"))


def test_trace10_file_absent_raises_file_not_found_error(tmp_path: Path) -> None:
    """Trace 10: file_exists=FALSE -> FileNotFoundError."""
    _assert_file_not_found(str(tmp_path / "rules_10.json"))


# ---------------------------------------------------------------------------
# Trace 4 — happy path: single valid rule returns populated CrossCuttingRule
# ---------------------------------------------------------------------------

def test_trace4_valid_rule_returns_dataclass(tmp_path: Path) -> None:
    """
    Trace 4: file_exists=TRUE, json_valid=TRUE, all_fields_present=TRUE,
    position="wrap" in ValidPositions -> result contains one CrossCuttingRule.
    """
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps([GOOD_RULE]))

    rules = load_cross_cutting_rules(str(rules_file))
    error_raised = False

    assert isinstance(rules, list)
    assert len(rules) == 1

    rule = rules[0]
    assert isinstance(rule, CrossCuttingRule)
    assert rule.resource_type == "database"
    assert rule.position == "wrap"
    assert "audit_event" in rule.required_outs

    assert_all_invariants(rules, error_raised)


# ---------------------------------------------------------------------------
# Trace 9 — invalid position value -> ValueError
# ---------------------------------------------------------------------------

def test_trace9_invalid_position_raises_value_error(tmp_path: Path) -> None:
    """
    Trace 9: file_exists=TRUE, json_valid=TRUE, all_fields_present=TRUE,
    but position="INVALID" not in ValidPositions -> ValueError.
    """
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps([BAD_POSITION_RULE]))

    error_raised = True
    rules: list = []

    with pytest.raises(ValueError):
        rules = load_cross_cutting_rules(str(rules_file))

    assert_all_invariants(rules, error_raised)


# ---------------------------------------------------------------------------
# Invariant verifier: NoPartialResults
# ---------------------------------------------------------------------------

class TestInvariantNoPartialResults:
    def test_no_partial_results_on_file_not_found(self, tmp_path: Path) -> None:
        """NoPartialResults: FileNotFoundError path."""
        rules: list = []
        with pytest.raises(FileNotFoundError):
            rules = load_cross_cutting_rules(str(tmp_path / "absent.json"))
        assert rules == [], "NoPartialResults: FileNotFoundError must leave result empty"

    def test_no_partial_results_on_invalid_position(self, tmp_path: Path) -> None:
        """NoPartialResults: invalid position path."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([BAD_POSITION_RULE]))
        rules: list = []
        with pytest.raises(ValueError):
            rules = load_cross_cutting_rules(str(f))
        assert rules == [], "NoPartialResults: ValueError must leave result empty"

    def test_no_partial_results_on_missing_fields(self, tmp_path: Path) -> None:
        """NoPartialResults: missing schema fields path."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{"only_one_field": "x"}]))
        rules: list = []
        with pytest.raises(ValueError):
            rules = load_cross_cutting_rules(str(f))
        assert rules == [], "NoPartialResults: schema ValueError must leave result empty"


# ---------------------------------------------------------------------------
# Invariant verifier: ValidPositionOnly
# ---------------------------------------------------------------------------

class TestInvariantValidPositionOnly:
    @pytest.mark.parametrize("position", sorted(VALID_POSITIONS))
    def test_all_valid_positions_accepted(self, tmp_path: Path, position: str) -> None:
        """ValidPositionOnly: forall r in result : r.position in ValidPositions."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{
            "resource_type": "service",
            "required_outs": ["log"],
            "position": position,
        }]))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 1
        assert rules[0].position in VALID_POSITIONS

    def test_invalid_position_rejected(self, tmp_path: Path) -> None:
        """ValidPositionOnly: position not in ValidPositions must raise ValueError."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([BAD_POSITION_RULE]))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))


# ---------------------------------------------------------------------------
# Invariant verifier: CompleteFields
# ---------------------------------------------------------------------------

class TestInvariantCompleteFields:
    def test_single_rule_all_fields_present(self, tmp_path: Path) -> None:
        """CompleteFields: forall r in result : resource_type, required_outs, position all present."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([GOOD_RULE]))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 1
        r = rules[0]
        assert hasattr(r, "resource_type")
        assert hasattr(r, "required_outs")
        assert hasattr(r, "position")

    def test_multiple_rules_all_fields_present(self, tmp_path: Path) -> None:
        """CompleteFields: all rules in a multi-rule file carry complete fields."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([
            {"resource_type": "service", "required_outs": ["span"], "position": "pre"},
            {"resource_type": "queue",   "required_outs": ["ack"],  "position": "post"},
        ]))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 2
        for r in rules:
            assert hasattr(r, "resource_type")
            assert hasattr(r, "required_outs")
            assert hasattr(r, "position")


# ---------------------------------------------------------------------------
# Invariant verifier: FileAbsentImpliesError
# ---------------------------------------------------------------------------

class TestInvariantFileAbsentImpliesError:
    def test_completely_absent_path(self, tmp_path: Path) -> None:
        """FileAbsentImpliesError: file_exists=FALSE => FileNotFoundError raised."""
        with pytest.raises(FileNotFoundError):
            load_cross_cutting_rules(str(tmp_path / "no_such_file.json"))

    def test_absent_nested_path(self, tmp_path: Path) -> None:
        """FileAbsentImpliesError: deeply nested absent path => FileNotFoundError raised."""
        with pytest.raises(FileNotFoundError):
            load_cross_cutting_rules(str(tmp_path / "sub" / "dir" / "rules.json"))


# ---------------------------------------------------------------------------
# Invariant verifier: MalformedImpliesError
# ---------------------------------------------------------------------------

class TestInvariantMalformedImpliesError:
    def test_completely_invalid_json(self, tmp_path: Path) -> None:
        """MalformedImpliesError: json_valid=FALSE (garbage bytes) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text("this is not json {{{{")
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_truncated_json(self, tmp_path: Path) -> None:
        """MalformedImpliesError: json_valid=FALSE (truncated array) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text('[{"resource_type": "db"')
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))


# ---------------------------------------------------------------------------
# Invariant verifier: InvalidSchemaImpliesError
# ---------------------------------------------------------------------------

class TestInvariantInvalidSchemaImpliesError:
    def test_rule_missing_position_field(self, tmp_path: Path) -> None:
        """InvalidSchemaImpliesError: all_fields_present=FALSE (no position) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{"resource_type": "db", "required_outs": ["event"]}]))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_rule_missing_resource_type_field(self, tmp_path: Path) -> None:
        """InvalidSchemaImpliesError: all_fields_present=FALSE (no resource_type) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{"required_outs": ["event"], "position": "pre"}]))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_rule_missing_required_outs_field(self, tmp_path: Path) -> None:
        """InvalidSchemaImpliesError: all_fields_present=FALSE (no required_outs) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{"resource_type": "db", "position": "pre"}]))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_rule_completely_empty_object(self, tmp_path: Path) -> None:
        """InvalidSchemaImpliesError: all_fields_present=FALSE (empty object) => ValueError."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([{}]))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_json_object_not_array(self, tmp_path: Path) -> None:
        """
        InvalidSchemaImpliesError: json_valid=TRUE but loader expects array -> ValueError.
        """
        f = tmp_path / "rules.json"
        f.write_text(json.dumps({"resource_type": "db", "required_outs": [], "position": "pre"}))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))


# ---------------------------------------------------------------------------
# Invariant verifier: SafeResult
# ---------------------------------------------------------------------------

class TestInvariantSafeResult:
    def test_safe_result_on_success(self, tmp_path: Path) -> None:
        """SafeResult: no error => all returned positions are valid."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([GOOD_RULE]))
        rules = load_cross_cutting_rules(str(f))
        assert rules is not None
        for r in rules:
            assert r.position in VALID_POSITIONS

    def test_safe_result_on_error_file_absent(self, tmp_path: Path) -> None:
        """SafeResult: error (FileNotFoundError) => result is empty list."""
        rules: list = []
        with pytest.raises(FileNotFoundError):
            rules = load_cross_cutting_rules(str(tmp_path / "gone.json"))
        assert rules == []

    def test_safe_result_on_error_bad_position(self, tmp_path: Path) -> None:
        """SafeResult: error (ValueError bad position) => result is empty list."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([BAD_POSITION_RULE]))
        rules: list = []
        with pytest.raises(ValueError):
            rules = load_cross_cutting_rules(str(f))
        assert rules == []


# ---------------------------------------------------------------------------
# Invariant verifier: EmptyRulesValid
# ---------------------------------------------------------------------------

class TestInvariantEmptyRulesValid:
    def test_empty_array_returns_empty_list(self, tmp_path: Path) -> None:
        """EmptyRulesValid: empty JSON array is valid input -> returns empty list."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([]))
        rules = load_cross_cutting_rules(str(f))
        assert rules == [], "EmptyRulesValid: empty JSON array must return empty list"

    def test_empty_array_no_error_raised(self, tmp_path: Path) -> None:
        """EmptyRulesValid: empty JSON array must not raise any exception."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([]))
        rules = load_cross_cutting_rules(str(f))
        assert isinstance(rules, list)


# ---------------------------------------------------------------------------
# Invariant verifier: PhaseValid
# ---------------------------------------------------------------------------

class TestInvariantPhaseValid:
    def test_only_file_not_found_or_value_error_on_failure(self, tmp_path: Path) -> None:
        """PhaseValid: only FileNotFoundError or ValueError are valid terminal error types."""
        bad_inputs = [
            (tmp_path / "no_file.json", None),
            (tmp_path / "bad.json",     "not json"),
            (tmp_path / "schema.json",  json.dumps([{"x": 1}])),
            (tmp_path / "pos.json",     json.dumps([BAD_POSITION_RULE])),
        ]
        for path, content in bad_inputs:
            if content is not None:
                path.write_text(content)
            did_raise = False
            try:
                load_cross_cutting_rules(str(path))
            except (FileNotFoundError, ValueError):
                did_raise = True
            except Exception as exc:
                pytest.fail(
                    f"PhaseValid violated: unexpected exception type "
                    f"{type(exc).__name__} for input {path}: {exc}"
                )
            if not did_raise:
                pytest.fail(
                    f"PhaseValid violated: bad input {path} did not raise any "
                    f"exception — expected FileNotFoundError or ValueError"
                )

    def test_success_returns_list_not_other_type(self, tmp_path: Path) -> None:
        """PhaseValid: successful call must return a list, not any other type."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([GOOD_RULE]))
        result = load_cross_cutting_rules(str(f))
        assert isinstance(result, list), (
            f"PhaseValid/returned: expected list, got {type(result).__name__}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_multiple_valid_rules_all_returned(self, tmp_path: Path) -> None:
        """Multiple valid rules -> all returned as CrossCuttingRule instances."""
        data = [
            {"resource_type": "service", "required_outs": ["span"],  "position": "pre"},
            {"resource_type": "db",      "required_outs": ["audit"], "position": "post"},
            {"resource_type": "queue",   "required_outs": ["ack"],   "position": "wrap"},
        ]
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(data))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 3
        for rule in rules:
            assert isinstance(rule, CrossCuttingRule)
            assert rule.position in VALID_POSITIONS

    def test_one_invalid_rule_among_valid_raises(self, tmp_path: Path) -> None:
        """NoPartialResults: if any rule is invalid the whole call raises ValueError."""
        data = [
            {"resource_type": "service", "required_outs": ["span"], "position": "pre"},
            BAD_POSITION_RULE,
        ]
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(data))
        rules: list = []
        with pytest.raises(ValueError):
            rules = load_cross_cutting_rules(str(f))
        assert rules == [], "NoPartialResults: partial results must not be returned"

    def test_required_outs_preserved_as_sequence(self, tmp_path: Path) -> None:
        """required_outs with multiple entries is preserved correctly."""
        rule = {
            "resource_type": "pipeline",
            "required_outs": ["event_a", "event_b", "event_c"],
            "position": "post",
        }
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([rule]))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 1
        assert set(rules[0].required_outs) == {"event_a", "event_b", "event_c"}

    def test_empty_required_outs_list_is_valid(self, tmp_path: Path) -> None:
        """required_outs may be an empty list — field is still present."""
        rule = {"resource_type": "noop", "required_outs": [], "position": "pre"}
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([rule]))
        rules = load_cross_cutting_rules(str(f))
        assert len(rules) == 1
        assert list(rules[0].required_outs) == []

    def test_null_bytes_in_file_raises(self, tmp_path: Path) -> None:
        """MalformedImpliesError: binary/null content is malformed JSON -> ValueError."""
        f = tmp_path / "rules.json"
        f.write_bytes(b"\x00\x01\x02\x03")
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_whitespace_only_file_raises(self, tmp_path: Path) -> None:
        """MalformedImpliesError: whitespace-only content is invalid JSON -> ValueError."""
        f = tmp_path / "rules.json"
        f.write_text("   \n\t  ")
        with pytest.raises(ValueError):
            load_cross_cutting_rules(str(f))

    def test_crosscuttingrule_is_dataclass_with_correct_types(self, tmp_path: Path) -> None:
        """Returned objects are CrossCuttingRule dataclass instances with correct field types."""
        f = tmp_path / "rules.json"
        f.write_text(json.dumps([GOOD_RULE]))
        rules = load_cross_cutting_rules(str(f))
        rule = rules[0]
        assert isinstance(rule, CrossCuttingRule)
        assert isinstance(rule.resource_type, str)
        assert isinstance(rule.position, str)
        assert hasattr(rule.required_outs, "__iter__")