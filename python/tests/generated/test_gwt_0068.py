"""Tests for gwt-0068: cross_cutting_rules_loaded.

Bridge verifiers: NoPartialResults, ValidPositionOnly, CompleteFields,
FileAbsentImpliesError, MalformedImpliesError, InvalidSchemaImpliesError,
SafeResult, EmptyRulesValid.
"""

import json
from pathlib import Path

import pytest

from registry.crawl_types import CrossCuttingRule
from registry.seam_checker import load_cross_cutting_rules


VALID_POSITIONS = {"pre", "post", "wrap"}


class TestLoadCrossCuttingRules:
    """Trace-derived tests for load_cross_cutting_rules()."""

    def test_valid_single_rule(self, tmp_path: Path) -> None:
        """Trace: file_exists=T, json_valid=T, all_fields_present=T -> result with 1 rule."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [
                {"resource_type": "database", "required_outs": ["audit_event"], "position": "wrap"}
            ]
        }))
        result = load_cross_cutting_rules(rules_path)
        assert len(result) == 1
        assert isinstance(result[0], CrossCuttingRule)
        assert result[0].resource_type == "database"
        assert result[0].required_outs == ["audit_event"]
        assert result[0].position == "wrap"

    def test_valid_multiple_rules(self, tmp_path: Path) -> None:
        """Multiple rules parsed correctly."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [
                {"resource_type": "database", "required_outs": ["audit_event"], "position": "wrap"},
                {"resource_type": "external_api", "required_outs": ["span_id", "trace_context"], "position": "pre"},
            ]
        }))
        result = load_cross_cutting_rules(rules_path)
        assert len(result) == 2
        assert result[1].resource_type == "external_api"
        assert result[1].required_outs == ["span_id", "trace_context"]
        assert result[1].position == "pre"

    def test_empty_rules_valid(self, tmp_path: Path) -> None:
        """Verifier EmptyRulesValid: empty rules array -> empty list, no error."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({"rules": []}))
        result = load_cross_cutting_rules(rules_path)
        assert result == []

    def test_file_absent_raises_file_not_found(self) -> None:
        """Verifier FileAbsentImpliesError: missing file -> FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_cross_cutting_rules(Path("/nonexistent/rules.json"))

    def test_malformed_json_raises_value_error(self, tmp_path: Path) -> None:
        """Verifier MalformedImpliesError: bad JSON -> ValueError."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text("not valid json {{{")
        with pytest.raises(ValueError):
            load_cross_cutting_rules(rules_path)

    def test_invalid_position_raises_value_error(self, tmp_path: Path) -> None:
        """Verifier ValidPositionOnly: position not in {pre, post, wrap} -> ValueError."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [{"resource_type": "db", "required_outs": [], "position": "INVALID"}]
        }))
        with pytest.raises(ValueError, match="position"):
            load_cross_cutting_rules(rules_path)

    def test_missing_required_field_raises_value_error(self, tmp_path: Path) -> None:
        """Verifier CompleteFields + InvalidSchemaImpliesError: missing field -> ValueError."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [{"resource_type": "db"}]
        }))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(rules_path)

    def test_missing_rules_key_raises_value_error(self, tmp_path: Path) -> None:
        """Verifier InvalidSchemaImpliesError: no 'rules' key -> ValueError."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({"not_rules": []}))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(rules_path)

    def test_no_partial_results_on_error(self, tmp_path: Path) -> None:
        """Verifier NoPartialResults: error => empty result, never partial.

        First rule valid, second invalid -> entire load fails.
        """
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [
                {"resource_type": "db", "required_outs": ["audit"], "position": "wrap"},
                {"resource_type": "api", "required_outs": [], "position": "BAD"},
            ]
        }))
        with pytest.raises(ValueError):
            load_cross_cutting_rules(rules_path)

    @pytest.mark.parametrize("position", sorted(VALID_POSITIONS))
    def test_all_valid_positions_accepted(self, tmp_path: Path, position: str) -> None:
        """ValidPositionOnly: all three valid positions are accepted."""
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [{"resource_type": "svc", "required_outs": ["log"], "position": position}]
        }))
        result = load_cross_cutting_rules(rules_path)
        assert len(result) == 1
        assert result[0].position == position
