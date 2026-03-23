"""Tests for gwt-0072: template_selected_by_annotation.

Bridge verifiers: DefaultFallback, AnnotationRespected, NoSilentFallback,
PromptBuiltOnlyIfLoaded, ErrorMeansNoPrompt, UnknownTemplateImpliesError,
KnownTemplateNeverErrors.
"""

from pathlib import Path

import pytest

from registry.loop_runner import resolve_template_name
from registry.types import Node, NodeKind


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = PROJECT_ROOT / "templates" / "pluscal"


class TestTemplateSelectedByAnnotation:
    """Trace-derived tests for resolve_template_name()."""

    def test_default_fallback_no_metadata(self) -> None:
        """Verifier DefaultFallback: no metadata → state_machine.tla."""
        gwt_node = Node(id="gwt-test", kind=NodeKind.BEHAVIOR, name="test", metadata=None)
        name, path = resolve_template_name(gwt_node, TEMPLATE_DIR)
        assert name == "state_machine"
        assert path == TEMPLATE_DIR / "state_machine.tla"

    def test_default_fallback_empty_metadata(self) -> None:
        """DefaultFallback: metadata without template key → state_machine.tla."""
        gwt_node = Node(id="gwt-test", kind=NodeKind.BEHAVIOR, name="test", metadata={})
        name, path = resolve_template_name(gwt_node, TEMPLATE_DIR)
        assert name == "state_machine"

    def test_annotation_respected(self) -> None:
        """Verifier AnnotationRespected: template='observability_state_machine' → loads it."""
        gwt_node = Node(
            id="gwt-test", kind=NodeKind.BEHAVIOR, name="test",
            metadata={"template": "observability_state_machine"},
        )
        name, path = resolve_template_name(gwt_node, TEMPLATE_DIR)
        assert name == "observability_state_machine"
        assert path == TEMPLATE_DIR / "observability_state_machine.tla"

    def test_unknown_template_raises_file_not_found(self) -> None:
        """Verifier UnknownTemplateImpliesError + NoSilentFallback: unknown → FileNotFoundError."""
        gwt_node = Node(
            id="gwt-test", kind=NodeKind.BEHAVIOR, name="test",
            metadata={"template": "nonexistent_template"},
        )
        with pytest.raises(FileNotFoundError):
            resolve_template_name(gwt_node, TEMPLATE_DIR)

    def test_known_template_never_errors(self) -> None:
        """Verifier KnownTemplateNeverErrors: existing template never raises."""
        gwt_node = Node(
            id="gwt-test", kind=NodeKind.BEHAVIOR, name="test",
            metadata={"template": "state_machine"},
        )
        name, path = resolve_template_name(gwt_node, TEMPLATE_DIR)
        assert name == "state_machine"
        assert path.exists()
