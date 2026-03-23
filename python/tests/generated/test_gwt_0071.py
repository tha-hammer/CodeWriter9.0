"""Tests for gwt-0071: observability_template_structure.

Bridge verifiers: ValidState, BoundedExecution, TraceComplete, AuditComplete,
TraceLogMonotonic, AuditLogMonotonic, BasePreserved.
"""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = PROJECT_ROOT / "templates" / "pluscal" / "observability_state_machine.tla"


class TestObservabilityTemplateStructure:
    """Structural tests: template file exists and contains required elements."""

    def test_template_file_exists(self) -> None:
        assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"

    def test_contains_trace_log_variable(self) -> None:
        content = TEMPLATE_PATH.read_text()
        assert "trace_log" in content

    def test_contains_audit_log_variable(self) -> None:
        content = TEMPLATE_PATH.read_text()
        assert "audit_log" in content

    def test_contains_trace_complete_invariant(self) -> None:
        content = TEMPLATE_PATH.read_text()
        assert "TraceComplete" in content

    def test_contains_audit_complete_invariant(self) -> None:
        content = TEMPLATE_PATH.read_text()
        assert "AuditComplete" in content

    def test_preserves_base_constructs(self) -> None:
        """Verifier BasePreserved: base state_machine concepts present."""
        content = TEMPLATE_PATH.read_text()
        assert "current_state" in content
        assert "history" in content
        assert "step_count" in content

    def test_preserves_valid_state_invariant(self) -> None:
        """Verifier ValidState must be in the template."""
        content = TEMPLATE_PATH.read_text()
        assert "ValidState" in content

    def test_preserves_bounded_execution_invariant(self) -> None:
        """Verifier BoundedExecution must be in the template."""
        content = TEMPLATE_PATH.read_text()
        assert "BoundedExecution" in content

    def test_contains_fill_markers(self) -> None:
        """Template must have fill-in markers for customization."""
        content = TEMPLATE_PATH.read_text()
        assert "{{FILL:" in content
