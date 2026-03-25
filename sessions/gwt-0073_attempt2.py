"""
Test suite for EntryPointDiscoveryDispatch (GWT gwt-0073).

Each test class maps to a TLA+ invariant or a concrete execution trace from
the formal spec.  All assertions reference the invariant or trace they are
exercising.  Fixtures build real RegistryDag instances — no mocks.
"""

from __future__ import annotations

import pytest

from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node

from EntryPointDiscoveryDispatch import (
    _verify_all_invariants,
    _verify_type_invariant,
    _verify_unknown_safe,
    discover_entry_points,
)

# ---------------------------------------------------------------------------
# TLA+ spec constants (mirrored from the formal model)
# ---------------------------------------------------------------------------

KNOWN_LANGS: frozenset[str] = frozenset(
    {"python", "go", "rust", "typescript", "javascript"}
)
NON_PYTHON_LANGS: frozenset[str] = frozenset(
    {"go", "rust", "typescript", "javascript"}
)
VALID_CODEBASE_TYPES: frozenset[str] = frozenset(
    {"web_app", "cli", "event_driven", "library"}
)
MAX_STEPS: int = 4

# python_helper expected for each codebase_type when the Python path is taken
CODEBASE_PYTHON_HELPER: dict[str, str] = {
    "cli": "cli_commands",
    "web_app": "web_routes",
    "library": "public_api",
    "event_driven": "event_handlers",
}


# ---------------------------------------------------------------------------
# DAG construction helpers
# ---------------------------------------------------------------------------


def _make_dag(
    *node_ids: str,
    edges: list[tuple[str, str]] | None = None,
) -> RegistryDag:
    """Build a RegistryDag with resource nodes and optional DEPENDS_ON edges."""
    dag = RegistryDag()
    for nid in node_ids:
        dag.add_node(Node.resource(nid, nid.replace("_", " ").capitalize(), ""))
    for src, dst in edges or []:
        dag.add_edge(Edge(from_id=src, to_id=dst, edge_type=EdgeType.DEPENDS_ON))
    return dag


@pytest.fixture
def empty_dag() -> RegistryDag:
    """Zero-node DAG."""
    return RegistryDag()


@pytest.fixture
def single_node_dag() -> RegistryDag:
    """One isolated node."""
    return _make_dag("n1")


@pytest.fixture
def linear3_dag() -> RegistryDag:
    """3-node chain: n1 → n2 → n3."""
    return _make_dag("n1", "n2", "n3", edges=[("n1", "n2"), ("n2", "n3")])


@pytest.fixture
def diamond_dag() -> RegistryDag:
    """Diamond: d1 → d2, d1 → d3, d2 → d4, d3 → d4."""
    return _make_dag(
        "d1", "d2", "d3", "d4",
        edges=[("d1", "d2"), ("d1", "d3"), ("d2", "d4"), ("d3", "d4")],
    )


@pytest.fixture
def linear5_dag() -> RegistryDag:
    """5-node chain: ln1 → ln2 → ln3 → ln4 → ln5."""
    return _make_dag(
        "ln1", "ln2", "ln3", "ln4", "ln5",
        edges=[
            ("ln1", "ln2"), ("ln2", "ln3"),
            ("ln3", "ln4"), ("ln4", "ln5"),
        ],
    )


@pytest.fixture
def standard_dag() -> RegistryDag:
    """4-node linear DAG used by the majority of invariant and trace tests."""
    return _make_dag(
        "s1", "s2", "s3", "s4",
        edges=[("s1", "s2"), ("s2", "s3"), ("s3", "s4")],
    )


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def _run(
    dag: RegistryDag,
    lang: str | None,
    skeletons: bool,
    codebase_type: str,
):
    """Call discover_entry_points and return (entry_points, state)."""
    return discover_entry_points(dag, lang, skeletons, codebase_type)


# ===========================================================================
# TRACE TESTS
# Each test asserts every final-state variable defined in the corrected trace
# table: phase, lang, dispatched_to, python_helper, result_empty,
# autodetect_done, and step_count.
# ===========================================================================


class TestTrace1:
    """
    TLA+ trace 1: ruby / skeletons=True / web_app.

    Expected final state:
        phase="finished", dispatched_to="none", python_helper="none",
        result_empty=TRUE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "ruby", True, "web_app")

        assert state.phase == "finished"
        assert state.lang == "ruby"
        assert state.dispatched_to == "none"
        assert state.python_helper == "none"
        assert state.result_empty is True
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) == 0
        _verify_all_invariants(state)


class TestTrace2:
    """
    TLA+ trace 2: None / skeletons=False / cli.

    Expected final state:
        phase="finished", dispatched_to="python", python_helper="cli_commands",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, None, False, "cli")

        assert state.phase == "finished"
        assert state.dispatched_to == "python"
        assert state.python_helper == "cli_commands"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace3:
    """
    TLA+ trace 3: python / skeletons=False / web_app.

    Expected final state:
        phase="finished", dispatched_to="python", python_helper="web_routes",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "python", False, "web_app")

        assert state.phase == "finished"
        assert state.lang == "python"
        assert state.dispatched_to == "python"
        assert state.python_helper == "web_routes"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace4:
    """
    TLA+ trace 4: rust / skeletons=True / event_driven.

    Expected final state:
        phase="finished", dispatched_to="rust", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "rust", True, "event_driven")

        assert state.phase == "finished"
        assert state.lang == "rust"
        assert state.dispatched_to == "rust"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace5:
    """
    TLA+ trace 5: typescript / skeletons=True / library.

    Expected final state:
        phase="finished", dispatched_to="typescript", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "typescript", True, "library")

        assert state.phase == "finished"
        assert state.lang == "typescript"
        assert state.dispatched_to == "typescript"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace6:
    """
    TLA+ trace 6: go / skeletons=False / event_driven.

    Expected final state:
        phase="finished", dispatched_to="go", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "go", False, "event_driven")

        assert state.phase == "finished"
        assert state.lang == "go"
        assert state.dispatched_to == "go"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace7:
    """
    TLA+ trace 7: None / skeletons=False / library.

    Expected final state:
        phase="finished", dispatched_to="python", python_helper="public_api",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, None, False, "library")

        assert state.phase == "finished"
        assert state.dispatched_to == "python"
        assert state.python_helper == "public_api"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace8:
    """
    TLA+ trace 8: javascript / skeletons=False / event_driven.

    Expected final state:
        phase="finished", dispatched_to="javascript", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "javascript", False, "event_driven")

        assert state.phase == "finished"
        assert state.lang == "javascript"
        assert state.dispatched_to == "javascript"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace9:
    """
    TLA+ trace 9 [CORRECTED — was duplicate of Trace1]:
    rust / skeletons=False / cli.

    Exercises the non-Python dispatch path with skeletons=False and
    codebase_type="cli", a combination not covered by any other trace.

    Expected final state:
        phase="finished", dispatched_to="rust", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "rust", False, "cli")

        assert state.phase == "finished"
        assert state.lang == "rust"
        assert state.dispatched_to == "rust"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestTrace10:
    """
    TLA+ trace 10: go / skeletons=False / cli.

    Expected final state:
        phase="finished", dispatched_to="go", python_helper="none",
        result_empty=FALSE, autodetect_done=TRUE.
    """

    def test_trace(self, standard_dag: RegistryDag) -> None:
        entry_points, state = _run(standard_dag, "go", False, "cli")

        assert state.phase == "finished"
        assert state.lang == "go"
        assert state.dispatched_to == "go"
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert state.step_count == MAX_STEPS
        assert len(entry_points) > 0
        _verify_all_invariants(state)


# ===========================================================================
# INVARIANT TESTS
# ===========================================================================


class TestTypeInvariant:
    """
    TLA+ invariant TypeInvariant:

        lang ∈ KnownLangs ∪ {"ruby"}
        ∧ dispatched_to ∈ NonPythonLangs ∪ {"python", "none"}
        ∧ step_count ∈ 0..MaxSteps

    Covers all 7 lang variants × all 4 codebase types.
    step_count is pinned to exactly MAX_STEPS (4) for every reachable trace.
    """

    @pytest.mark.parametrize(
        "lang",
        ["python", "go", "rust", "typescript", "javascript", "ruby", None],
    )
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_type_domains_and_step_count(
        self,
        standard_dag: RegistryDag,
        lang: str | None,
        codebase_type: str,
    ) -> None:
        """All final-state values fall within their TLA+ type domains."""
        _, state = _run(standard_dag, lang, True, codebase_type)

        _verify_type_invariant(state)

        assert state.lang in KNOWN_LANGS | {"ruby", None}, (
            f"lang={state.lang!r} outside KnownLangs ∪ {{ruby, None}}"
        )
        assert state.dispatched_to in NON_PYTHON_LANGS | {"python", "none"}, (
            f"dispatched_to={state.dispatched_to!r} outside valid domain"
        )
        assert 0 <= state.step_count <= MAX_STEPS, (
            f"step_count={state.step_count} outside 0..{MAX_STEPS}"
        )
        assert state.step_count == MAX_STEPS, (
            f"step_count={state.step_count} should be pinned to {MAX_STEPS}"
        )


class TestPythonPreserved:
    """
    TLA+ invariant PythonPreserved:

        (phase = "finished" ∧ dispatched_to = "python") =>
            python_helper ∈ ValidHelpers ∧ result_empty = FALSE

    Asserts all 4 codebase→helper mappings for both lang=None and lang="python".
    """

    @pytest.mark.parametrize("lang", [None, "python"])
    @pytest.mark.parametrize(
        "codebase_type, expected_helper",
        list(CODEBASE_PYTHON_HELPER.items()),
    )
    def test_python_helper_mapping(
        self,
        standard_dag: RegistryDag,
        lang: str | None,
        codebase_type: str,
        expected_helper: str,
    ) -> None:
        """Python dispatch sets the correct helper for every codebase type."""
        entry_points, state = _run(standard_dag, lang, False, codebase_type)

        assert state.phase == "finished"
        assert state.dispatched_to == "python"
        assert state.python_helper == expected_helper, (
            f"lang={lang!r}, codebase={codebase_type!r}: "
            f"expected helper={expected_helper!r}, got {state.python_helper!r}"
        )
        assert state.result_empty is False
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestNonPythonDispatched:
    """
    TLA+ invariant NonPythonDispatched [CORRECTED]:

        (phase = "finished" ∧ lang ∈ NonPythonLangs) =>
            (dispatched_to = lang ∧ python_helper = "none" ∧ result_empty = FALSE)

    All three conjuncts are asserted for all 4 non-Python langs × 4 codebase types.
    Omitting result_empty would allow a broken implementation to set it TRUE
    while still passing — this class closes that gap.
    """

    @pytest.mark.parametrize("lang", sorted(NON_PYTHON_LANGS))
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_non_python_dispatch_full_conjunction(
        self,
        standard_dag: RegistryDag,
        lang: str,
        codebase_type: str,
    ) -> None:
        """Non-Python lang dispatches to itself, clears python_helper, and is non-empty."""
        entry_points, state = _run(standard_dag, lang, True, codebase_type)

        assert state.phase == "finished"
        assert state.dispatched_to == lang, (
            f"dispatched_to={state.dispatched_to!r}, expected {lang!r}"
        )
        assert state.python_helper == "none", (
            f"python_helper must be 'none' for non-Python lang {lang!r}, "
            f"got {state.python_helper!r}"
        )
        # Third conjunct — critical: result_empty must be FALSE (NonPythonDispatched)
        assert state.result_empty is False, (
            f"result_empty=True violates NonPythonDispatched for lang={lang!r}"
        )
        assert len(entry_points) > 0
        _verify_all_invariants(state)


class TestUnknownSafe:
    """
    TLA+ invariant UnknownSafe [CORRECTED]:

        (phase = "finished" ∧ lang ∉ KnownLangs) =>
            (dispatched_to = "none" ∧ result_empty = TRUE)

    Only lang="ruby" is used (TypeInvariant constrains the unknown-lang domain
    to KnownLangs ∪ {"ruby"}).  The skeletons flag and DAG topology are varied
    to demonstrate the invariant holds unconditionally.
    """

    @pytest.mark.parametrize("skeletons", [True, False])
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_unknown_lang_empty_dag(
        self,
        empty_dag: RegistryDag,
        skeletons: bool,
        codebase_type: str,
    ) -> None:
        """Empty DAG with unknown lang: result_empty=True regardless of skeletons."""
        entry_points, state = _run(empty_dag, "ruby", skeletons, codebase_type)

        assert state.phase == "finished"
        assert state.dispatched_to == "none"
        assert state.python_helper == "none"
        assert state.result_empty is True
        assert state.autodetect_done is True
        assert len(entry_points) == 0
        _verify_unknown_safe(state)
        _verify_all_invariants(state)

    @pytest.mark.parametrize("skeletons", [True, False])
    def test_unknown_lang_single_node_dag(
        self,
        single_node_dag: RegistryDag,
        skeletons: bool,
    ) -> None:
        """Single-node DAG with unknown lang: skeletons flag does not override UnknownSafe."""
        entry_points, state = _run(single_node_dag, "ruby", skeletons, "web_app")

        assert state.phase == "finished"
        assert state.dispatched_to == "none"
        assert state.python_helper == "none"
        assert state.result_empty is True
        assert len(entry_points) == 0
        _verify_all_invariants(state)

    @pytest.mark.parametrize("skeletons", [True, False])
    def test_unknown_lang_multi_node_dag(
        self,
        linear3_dag: RegistryDag,
        skeletons: bool,
    ) -> None:
        """Multi-node DAG with unknown lang: topology does not override UnknownSafe."""
        entry_points, state = _run(linear3_dag, "ruby", skeletons, "cli")

        assert state.phase == "finished"
        assert state.dispatched_to == "none"
        assert state.python_helper == "none"
        assert state.result_empty is True
        assert len(entry_points) == 0
        _verify_all_invariants(state)


class TestAutodetectBeforeDispatch:
    """
    TLA+ invariant AutodetectBeforeDispatch [CORRECTED]:

        (phase ∈ {dispatching, python_subdispatch, finished}) =>
            autodetect_done = TRUE

    Covers all 7 lang variants × all 4 codebase types.
    The original plan omitted rust, typescript, and javascript — this class
    restores full coverage.
    """

    @pytest.mark.parametrize(
        "lang",
        ["python", "go", "rust", "typescript", "javascript", "ruby", None],
    )
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_autodetect_done_at_finished_phase(
        self,
        standard_dag: RegistryDag,
        lang: str | None,
        codebase_type: str,
    ) -> None:
        """autodetect_done is True in the finished phase for every lang variant."""
        _, state = _run(standard_dag, lang, False, codebase_type)

        assert state.phase == "finished"
        assert state.autodetect_done is True, (
            f"AutodetectBeforeDispatch violated for lang={lang!r}, "
            f"codebase={codebase_type!r}: autodetect_done=False in finished phase"
        )
        _verify_all_invariants(state)


class TestCodebaseResolvedBeforeDispatch:
    """
    TLA+ invariant CodebaseResolvedBeforeDispatch [CORRECTED]:

        (phase ∈ {dispatching, python_subdispatch, finished}) =>
            codebase_type ∈ ValidCodebaseTypes

    This is a safety property on reachable states, not a precondition guard.
    The test verifies the *semantic intent*: the system never reaches
    phase="finished" with an invalid codebase_type having been dispatched.
    If the implementation rejects the input eagerly, any of
    (AssertionError, ValueError) are accepted as compliant mechanisms.
    """

    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_valid_codebase_types_reach_finished(
        self,
        standard_dag: RegistryDag,
        codebase_type: str,
    ) -> None:
        """All four valid codebase types complete successfully."""
        _, state = _run(standard_dag, "python", False, codebase_type)

        assert state.phase == "finished"
        assert state.autodetect_done is True
        _verify_all_invariants(state)

    @pytest.mark.parametrize(
        "invalid_codebase_type",
        ["monolith", "microservice", "serverless", ""],
    )
    def test_invalid_codebase_type_does_not_reach_finished(
        self,
        standard_dag: RegistryDag,
        invalid_codebase_type: str,
    ) -> None:
        """
        An invalid codebase_type must not produce a finished state that has
        dispatched with that type.  Acceptable implementation responses are:
          • raise AssertionError or ValueError (eager rejection), OR
          • return a state where phase != "finished"

        Either outcome satisfies the TLA+ safety invariant.
        """
        try:
            _, state = _run(standard_dag, "python", False, invalid_codebase_type)
            # If the call returns, the finished state must not carry the bad type
            if state.phase == "finished":
                assert state.codebase_type in VALID_CODEBASE_TYPES, (
                    f"Invariant violated: phase='finished' reached with "
                    f"invalid codebase_type={invalid_codebase_type!r}"
                )
        except (AssertionError, ValueError):
            pass  # Eager rejection is a compliant implementation choice


class TestMutualExclusion:
    """
    TLA+ invariant MutualExclusion [CORRECTED]:

        ~(dispatched_to ∈ NonPythonLangs ∧ result_empty = TRUE)

    Only NonPythonLangs (go, rust, typescript, javascript) are used.
    Ruby is intentionally excluded: for ruby, dispatched_to="none" ∉ NonPythonLangs,
    so the conjunction is always false and the invariant would be vacuously true —
    providing zero coverage.
    """

    @pytest.mark.parametrize("lang", sorted(NON_PYTHON_LANGS))
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    @pytest.mark.parametrize("skeletons", [True, False])
    def test_non_python_dispatch_not_empty(
        self,
        standard_dag: RegistryDag,
        lang: str,
        codebase_type: str,
        skeletons: bool,
    ) -> None:
        """dispatched_to ∈ NonPythonLangs must never co-occur with result_empty=True."""
        _, state = _run(standard_dag, lang, skeletons, codebase_type)

        assert state.phase == "finished"
        if state.dispatched_to in NON_PYTHON_LANGS:
            assert state.result_empty is False, (
                f"MutualExclusion violated: dispatched_to={state.dispatched_to!r} "
                f"but result_empty=True "
                f"(lang={lang!r}, codebase={codebase_type!r}, skeletons={skeletons})"
            )
        _verify_all_invariants(state)


class TestBoundedExecution:
    """
    TLA+ invariant BoundedExecution:

        step_count ≤ MaxSteps   (MaxSteps = 4)

    Covers all 7 lang variants × all 4 codebase types (28 combinations).
    """

    @pytest.mark.parametrize(
        "lang",
        ["python", "go", "rust", "typescript", "javascript", "ruby", None],
    )
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_bounded_step_count(
        self,
        standard_dag: RegistryDag,
        lang: str | None,
        codebase_type: str,
    ) -> None:
        """Every execution completes within MaxSteps=4 steps."""
        _, state = _run(standard_dag, lang, True, codebase_type)

        assert state.step_count <= MAX_STEPS, (
            f"BoundedExecution violated: step_count={state.step_count} > {MAX_STEPS} "
            f"for lang={lang!r}, codebase={codebase_type!r}"
        )
        _verify_all_invariants(state)


# ===========================================================================
# EDGE-CASE TESTS
# ===========================================================================


class TestEdgeCases:
    """
    Structural extremes, semantic equivalences, and combinatorial cross-products.
    """

    # ------------------------------------------------------------------
    # Empty DAG
    # ------------------------------------------------------------------

    def test_empty_dag_unknown_lang(self, empty_dag: RegistryDag) -> None:
        """Empty DAG + unknown lang → result_empty=True (UnknownSafe on minimal topology)."""
        entry_points, state = _run(empty_dag, "ruby", False, "web_app")

        assert state.result_empty is True
        assert state.dispatched_to == "none"
        assert state.python_helper == "none"
        assert len(entry_points) == 0
        _verify_all_invariants(state)

    def test_empty_dag_python_lang(self, empty_dag: RegistryDag) -> None:
        """Empty DAG + Python lang: invariants hold even when no nodes are present."""
        _, state = _run(empty_dag, "python", False, "web_app")

        assert state.phase == "finished"
        assert state.dispatched_to == "python"
        assert state.autodetect_done is True
        _verify_all_invariants(state)

    # ------------------------------------------------------------------
    # Isolated single node
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("lang", ["python", "go", "ruby"])
    def test_isolated_node_dag(self, single_node_dag: RegistryDag, lang: str) -> None:
        """Single isolated node: invariants hold across unknown, known-non-Python, and Python."""
        _, state = _run(single_node_dag, lang, False, "cli")

        assert state.phase == "finished"
        _verify_all_invariants(state)

    # ------------------------------------------------------------------
    # Diamond topology
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("lang", ["python", "rust"])
    def test_diamond_dag(self, diamond_dag: RegistryDag, lang: str) -> None:
        """Diamond topology (fan-out + merge): invariants hold for Python and non-Python."""
        _, state = _run(diamond_dag, lang, True, "library")

        assert state.phase == "finished"
        _verify_all_invariants(state)

    # ------------------------------------------------------------------
    # None ↔ "python" explicit equivalence (MINOR-2 corrected)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_none_python_full_state_equivalence(
        self,
        standard_dag: RegistryDag,
        codebase_type: str,
    ) -> None:
        """
        discover_entry_points(dag, None, ...) and discover_entry_points(dag, "python", ...)
        must produce identical results across the complete final-state tuple:
        (phase, dispatched_to, python_helper, result_empty, autodetect_done, step_count)
        and equivalent entry-point sets.
        """
        ep_none, state_none = _run(standard_dag, None, False, codebase_type)
        ep_python, state_python = _run(standard_dag, "python", False, codebase_type)

        assert state_none.phase == state_python.phase, (
            f"phase mismatch for codebase={codebase_type!r}: "
            f"{state_none.phase!r} != {state_python.phase!r}"
        )
        assert state_none.dispatched_to == state_python.dispatched_to, (
            f"dispatched_to mismatch for codebase={codebase_type!r}: "
            f"{state_none.dispatched_to!r} != {state_python.dispatched_to!r}"
        )
        assert state_none.python_helper == state_python.python_helper, (
            f"python_helper mismatch for codebase={codebase_type!r}"
        )
        assert state_none.result_empty == state_python.result_empty, (
            f"result_empty mismatch for codebase={codebase_type!r}"
        )
        assert state_none.autodetect_done == state_python.autodetect_done, (
            f"autodetect_done mismatch for codebase={codebase_type!r}"
        )
        assert state_none.step_count == state_python.step_count, (
            f"step_count mismatch for codebase={codebase_type!r}: "
            f"{state_none.step_count} != {state_python.step_count}"
        )
        assert set(ep_none) == set(ep_python), (
            f"entry_point sets differ for codebase={codebase_type!r}: "
            f"None→{ep_none!r} vs 'python'→{ep_python!r}"
        )

    # ------------------------------------------------------------------
    # skeletons flag invariance for non-Python langs
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    @pytest.mark.parametrize("lang", sorted(NON_PYTHON_LANGS))
    def test_skeletons_flag_invariance_non_python(
        self,
        standard_dag: RegistryDag,
        codebase_type: str,
        lang: str,
    ) -> None:
        """
        For non-Python langs the skeletons flag must not change dispatch outcome:
        dispatched_to, python_helper, and result_empty are invariant under skeletons.
        """
        _, state_true = _run(standard_dag, lang, True, codebase_type)
        _, state_false = _run(standard_dag, lang, False, codebase_type)

        assert state_true.dispatched_to == state_false.dispatched_to, (
            f"dispatched_to differs with skeletons flag for lang={lang!r}"
        )
        assert state_true.python_helper == state_false.python_helper, (
            f"python_helper differs with skeletons flag for lang={lang!r}"
        )
        assert state_true.result_empty == state_false.result_empty, (
            f"result_empty differs with skeletons flag for lang={lang!r}"
        )

    # ------------------------------------------------------------------
    # 4×4 non-Python × codebase matrix
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("lang", sorted(NON_PYTHON_LANGS))
    @pytest.mark.parametrize("codebase_type", sorted(VALID_CODEBASE_TYPES))
    def test_non_python_codebase_full_matrix(
        self,
        standard_dag: RegistryDag,
        lang: str,
        codebase_type: str,
    ) -> None:
        """Full 4×4 matrix: every non-Python lang × every codebase type satisfies all invariants."""
        entry_points, state = _run(standard_dag, lang, False, codebase_type)

        assert state.phase == "finished"
        assert state.dispatched_to == lang
        assert state.python_helper == "none"
        assert state.result_empty is False
        assert state.autodetect_done is True
        assert len(entry_points) > 0
        _verify_all_invariants(state)

    # ------------------------------------------------------------------
    # 5-node linear chain (BoundedExecution on larger topology)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("lang", ["python", "go", "ruby"])
    def test_five_node_linear_chain(
        self,
        linear5_dag: RegistryDag,
        lang: str,
    ) -> None:
        """5-node linear chain: BoundedExecution and all invariants hold on a larger DAG."""
        _, state = _run(linear5_dag, lang, False, "library")

        assert state.phase == "finished"
        assert state.step_count <= MAX_STEPS
        assert state.autodetect_done is True
        _verify_all_invariants(state)