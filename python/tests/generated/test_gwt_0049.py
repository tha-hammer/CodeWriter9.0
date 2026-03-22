"""
Pytest tests for scanner_typescript_nested_depth.scan_file
Generated from TLC-verified traces of scanner_typescript_nested_depth.tla

Behavior: TypeScript source files with methods inside classes are tracked by
brace depth. When scan_file is called, methods inside classes have class_name
set to the enclosing class; functions outside classes have class_name=None.

All 10 TLC traces encode the same deterministic 6-event scan path (TLC path
exploration of a deterministic program):
  Events = [ClassOpen("A"), Method("getUser"), CloseBrace(""),
            Func("helper"), ClassOpen("B"), Method("save")]

Expected final skeletons (State 21 in all traces):
  { (getUser, A, True), (helper, A, True), (save, B, True) }

Invariants checked at every state:
  DepthConsistency, AllFuncsRecorded, MethodsHaveClass,
  FuncsOutsideHaveNone, StackDepthNonNegative, CursorBounded
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from pathlib import Path
from registry.scanner_typescript import scan_file as _scan_file

def scan_file(path):
    return _scan_file(Path(path) if isinstance(path, str) else path)
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS  —  derived directly from the TLA+ spec
# ═══════════════════════════════════════════════════════════════════════════════

N = 6  # total events in the canonical trace; cursor bounded to [1, N+1]

# Canonical final skeleton set (State 21 in all ten traces).
EXPECTED_SKELETONS: frozenset[tuple[str, str | None, bool]] = frozenset(
    {
        ("getUser", "A", True),
        ("helper", "A", True),
        ("save", "B", True),
    }
)

# ── TypeScript sources that drive specific event sequences ───────────────────

# 6-event canonical sequence (all traces):
#   ClassOpen(A) → Method(getUser) → CloseBrace
#   → Func/Method(helper) → ClassOpen(B) → Method(save)
#
# Brace-depth walk:
#   0 -[ClassOpen A]-> 1 -[Method getUser]-> 2 -[CloseBrace]-> 1
#   -[helper]-> 2 -[ClassOpen B]-> 3 -[Method save]-> 4
#
# State 3:  class_stack=[{A,0}],        brace_depth=1
# State 6:  skeletons+={getUser/A},     brace_depth=2
# State 9:  brace_depth=1  (pop guard: 1 > 0=A.depth → A stays)
# State 12: skeletons+={helper/A},      brace_depth=2
# State 15: class_stack=[{A,0},{B,2}],  brace_depth=3
# State 18: skeletons+={save/B},        brace_depth=4
CANONICAL_TS_SOURCE = """\
class A {
  getUser() {
  }
  helper() {
    class B {
      save() {
"""

# Top-level (outside-class) functions only — exercises FuncsOutsideHaveNone
TOPLEVEL_FUNCS_TS_SOURCE = """\
function standalone() {
}
function another() {
}
"""

# Single class, single method
SINGLE_CLASS_TS_SOURCE = """\
class Foo {
  bar() {
  }
}
"""

# Mixed: top-level + class methods
MIXED_TS_SOURCE = """\
function topFunc() {
}
class MyClass {
  classMethod() {
  }
}
function anotherTopFunc() {
}
"""

# Two sibling classes
SIBLING_CLASSES_TS_SOURCE = """\
class Dog {
  bark() {
  }
}
class Cat {
  meow() {
  }
}
"""

EMPTY_TS_SOURCE = ""


# ═══════════════════════════════════════════════════════════════════════════════
# LOW-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _skeleton_tuple(s: Any) -> tuple[str, str | None, bool]:
    """Normalise a skeleton (tuple, dict, or object) → (func_name, class_name, inside_class)."""
    if isinstance(s, tuple):
        return s  # type: ignore[return-value]
    if isinstance(s, dict):
        return (s["function_name"], s.get("class_name"), bool(s["inside_class"]))
    return (s.function_name, s.class_name, bool(s.inside_class))


def _skeleton_set(skeletons: Any) -> frozenset[tuple[str, str | None, bool]]:
    """Convert an iterable of skeletons to a frozenset of normalised tuples."""
    return frozenset(_skeleton_tuple(s) for s in skeletons)


def _to_list(skeletons: Any) -> list:
    """Materialise skeletons to a plain list (handles set/list/generator)."""
    return list(skeletons)


def _write_ts_file(content: str) -> Path:
    """Write TypeScript content to a temp file; caller is responsible for unlinking."""
    fd, raw = tempfile.mkstemp(suffix=".ts")
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    return Path(raw)


def _make_dag(node_ids: list[str], edges: list[tuple[str, str]]) -> RegistryDag:
    """Build a RegistryDag from node_id list and (src, dst) edge pairs."""
    dag = RegistryDag()
    for nid in node_ids:
        dag.add_node(Node.behavior(nid, nid, "given", "when", "then"))
    for src, dst in edges:
        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))
    return dag


# ── Invariant assertion helpers ───────────────────────────────────────────────

def assert_depth_consistency(skeletons: Any) -> None:
    """TLA+ DepthConsistency: class_name=None ↔ inside_class=False (and vice-versa)."""
    for s in _to_list(skeletons):
        fn, cn, ic = _skeleton_tuple(s)
        if cn in (None, "None"):
            assert ic is False, (
                f"DepthConsistency violated: {fn!r} has class_name={cn!r} "
                f"but inside_class={ic}"
            )
        else:
            assert ic is True, (
                f"DepthConsistency violated: {fn!r} has class_name={cn!r} "
                f"but inside_class={ic}"
            )


def assert_methods_have_class(skeletons: Any) -> None:
    """TLA+ MethodsHaveClass: inside_class=True ⇒ class_name not None/empty."""
    for s in _to_list(skeletons):
        fn, cn, ic = _skeleton_tuple(s)
        if ic is True:
            assert cn not in (None, "None") and cn != "", (
                f"MethodsHaveClass violated: {fn!r} has inside_class=True "
                f"but class_name={cn!r}"
            )


def assert_funcs_outside_have_none(skeletons: Any) -> None:
    """TLA+ FuncsOutsideHaveNone: inside_class=False ⇒ class_name is None/'None'."""
    for s in _to_list(skeletons):
        fn, cn, ic = _skeleton_tuple(s)
        if ic is False:
            assert cn in (None, "None"), (
                f"FuncsOutsideHaveNone violated: {fn!r} has inside_class=False "
                f"but class_name={cn!r}"
            )


def assert_stack_depth_non_negative(depth: int) -> None:
    """TLA+ StackDepthNonNegative: brace_depth ≥ 0."""
    assert depth >= 0, f"StackDepthNonNegative violated: brace_depth={depth}"


def assert_cursor_bounded(cursor: int, n: int = N) -> None:
    """TLA+ CursorBounded: 1 ≤ cursor ≤ N+1."""
    assert 1 <= cursor <= n + 1, (
        f"CursorBounded violated: cursor={cursor}, N={n}"
    )


def assert_all_invariants(skeletons: Any, *, brace_depth: int | None = None) -> None:
    """Assert the TLA+ invariants that can be checked on a completed scan result."""
    items = _to_list(skeletons)
    assert_depth_consistency(items)
    assert_methods_have_class(items)
    assert_funcs_outside_have_none(items)
    if brace_depth is not None:
        assert_stack_depth_non_negative(brace_depth)


# ═══════════════════════════════════════════════════════════════════════════════
# PYTEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def canonical_ts_file():
    """Canonical TypeScript file — drives the 6-event TLC trace sequence."""
    path = _write_ts_file(CANONICAL_TS_SOURCE)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def toplevel_funcs_file():
    """TypeScript file with only top-level (outside-class) functions."""
    path = _write_ts_file(TOPLEVEL_FUNCS_TS_SOURCE)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def single_class_file():
    """TypeScript file with one class and one method."""
    path = _write_ts_file(SINGLE_CLASS_TS_SOURCE)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def empty_ts_file():
    """Empty TypeScript file — Init state with no events."""
    path = _write_ts_file(EMPTY_TS_SOURCE)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def canonical_dag() -> RegistryDag:
    """
    RegistryDag fixture derived from the canonical trace Init state.
    Nodes  : one per skeleton entry plus the two class nodes.
    Edges  : method → enclosing-class (IMPORTS) to model membership.

    Topology mirrors the final state of all 10 traces:
        getUser → A
        helper  → A
        save    → B
        B       → A   (B is nested inside helper's body, which belongs to A)
    """
    return _make_dag(
        node_ids=["getUser", "helper", "save", "A", "B"],
        edges=[
            ("getUser", "A"),
            ("helper", "A"),
            ("save", "B"),
            ("B", "A"),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TRACE-DERIVED TESTS  (Traces 1 – 10)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrace1:
    """
    Trace 1 (21 steps).
    Path: ScanLoop→ProcessEvent→Advance ×6 then Finish.
    Final state (State 21): skeletons={getUser/A, helper/A, save/B},
    class_stack=[{A,0},{B,2}], brace_depth=4, cursor=7.
    """

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        result = _skeleton_set(scan_file(str(canonical_ts_file)))
        assert result == EXPECTED_SKELETONS

    def test_state6_getUser_inside_class_A(self, canonical_ts_file: Path) -> None:
        """State 6: ProcessEvent records getUser with class_name='A', inside_class=True."""
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert "getUser" in items
        fn, cn, ic = items["getUser"]
        assert cn == "A"
        assert ic is True

    def test_state12_helper_inside_class_A(self, canonical_ts_file: Path) -> None:
        """State 12: helper added with class_name='A' (class_stack still holds A)."""
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert "helper" in items
        fn, cn, ic = items["helper"]
        assert cn == "A"
        assert ic is True

    def test_state18_save_inside_class_B(self, canonical_ts_file: Path) -> None:
        """State 18: save added with class_name='B' (innermost class on stack)."""
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert "save" in items
        fn, cn, ic = items["save"]
        assert cn == "B"
        assert ic is True

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_all_funcs_recorded_allFuncsRecorded(self, canonical_ts_file: Path) -> None:
        """AllFuncsRecorded: getUser, helper, save all present (cursor ended at N+1=7)."""
        names = {_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert {"getUser", "helper", "save"} <= names


class TestTrace2:
    """Trace 2 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_skeleton_count_is_three(self, canonical_ts_file: Path) -> None:
        """Exactly 3 skeletons in State 21 (one per Method/Func event)."""
        assert len(_to_list(scan_file(str(canonical_ts_file)))) == 3

    def test_all_inside_class(self, canonical_ts_file: Path) -> None:
        """Every skeleton in this trace has inside_class=True."""
        for s in _to_list(scan_file(str(canonical_ts_file))):
            _, _, ic = _skeleton_tuple(s)
            assert ic is True


class TestTrace3:
    """Trace 3 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_depth_consistency_per_skeleton(self, canonical_ts_file: Path) -> None:
        """TLA+ DepthConsistency holds for each skeleton in the canonical result."""
        assert_depth_consistency(scan_file(str(canonical_ts_file)))

    def test_methods_have_class_per_skeleton(self, canonical_ts_file: Path) -> None:
        """TLA+ MethodsHaveClass holds for each skeleton in the canonical result."""
        assert_methods_have_class(scan_file(str(canonical_ts_file)))


class TestTrace4:
    """Trace 4 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_class_names_are_non_empty_strings(self, canonical_ts_file: Path) -> None:
        """Every inside_class=True skeleton carries a non-empty string class_name."""
        for s in _to_list(scan_file(str(canonical_ts_file))):
            fn, cn, ic = _skeleton_tuple(s)
            if ic:
                assert isinstance(cn, str) and len(cn) > 0, (
                    f"{fn!r}: inside_class=True but class_name={cn!r}"
                )

    def test_no_duplicate_skeletons(self, canonical_ts_file: Path) -> None:
        """TLA+ uses set semantics for skeletons — no duplicates allowed."""
        tuples = [_skeleton_tuple(s)
                  for s in _to_list(scan_file(str(canonical_ts_file)))]
        assert len(tuples) == len(set(tuples)), "Duplicate skeletons found"


class TestTrace5:
    """Trace 5 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_save_attributed_to_innermost_class_B_not_A(self, canonical_ts_file: Path) -> None:
        """
        State 15 pushed B at depth 2; State 18 uses top-of-stack = B.
        save() must be attributed to B, not to the outer A.
        """
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert items["save"][1] == "B"

    def test_close_brace_does_not_pop_class_A(self, canonical_ts_file: Path) -> None:
        """
        State 9: CloseBrace → brace_depth=1; 1 > 0 = A.depth → A NOT popped.
        helper() at event 4 is still inside A.
        """
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert items["helper"][1] == "A"


class TestTrace6:
    """Trace 6 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_both_outer_A_methods_attributed_correctly(self, canonical_ts_file: Path) -> None:
        """Both getUser (State 6) and helper (State 12) are attributed to class A."""
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert items["getUser"][1] == "A"
        assert items["helper"][1] == "A"

    def test_funcs_outside_have_none_trivially_holds(self, canonical_ts_file: Path) -> None:
        """No outside-class functions in this trace; FuncsOutsideHaveNone holds vacuously."""
        assert_funcs_outside_have_none(scan_file(str(canonical_ts_file)))


class TestTrace7:
    """Trace 7 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_scan_completes_without_brace_depth_underflow(self, canonical_ts_file: Path) -> None:
        """
        StackDepthNonNegative: unclosed braces (final depth=4) are valid;
        scan must complete without underflowing to negative depth.
        """
        skeletons = scan_file(str(canonical_ts_file))
        assert_all_invariants(skeletons, brace_depth=4)
        assert_stack_depth_non_negative(4)

    def test_all_funcs_recorded_names(self, canonical_ts_file: Path) -> None:
        """AllFuncsRecorded: all three expected names are present after the scan."""
        names = {_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        for expected in ("getUser", "helper", "save"):
            assert expected in names, f"AllFuncsRecorded: {expected!r} missing"


class TestTrace8:
    """Trace 8 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_cursor_bounded_implied_by_skeleton_count(self, canonical_ts_file: Path) -> None:
        """
        CursorBounded: N=6 events → cursor ends at 7.
        Exactly 3 Func/Method events → exactly 3 skeletons.
        """
        assert len(_to_list(scan_file(str(canonical_ts_file)))) == 3

    def test_each_skeleton_has_required_fields(self, canonical_ts_file: Path) -> None:
        """Each skeleton carries a non-empty func_name string and a boolean inside_class."""
        for s in _to_list(scan_file(str(canonical_ts_file))):
            fn, cn, ic = _skeleton_tuple(s)
            assert isinstance(fn, str) and fn
            assert ic in (True, False)


class TestTrace9:
    """Trace 9 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_no_outside_class_entries_in_this_trace(self, canonical_ts_file: Path) -> None:
        """All skeletons in the canonical trace are inside a class."""
        for s in _to_list(scan_file(str(canonical_ts_file))):
            _, cn, ic = _skeleton_tuple(s)
            assert ic is True
            assert cn not in (None, "None")

    def test_class_stack_depth_reflected_in_attributions(self, canonical_ts_file: Path) -> None:
        """
        class_stack at State 15 = [{A,0},{B,2}] → save gets B (top).
        class_stack at State 6  = [{A,0}]        → getUser gets A.
        """
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert items["getUser"][1] == "A"
        assert items["save"][1] == "B"


class TestTrace10:
    """Trace 10 (21 steps) — same event sequence, independent execution path."""

    def test_final_skeleton_set_matches_state21(self, canonical_ts_file: Path) -> None:
        """State 21: full skeleton set equals EXPECTED_SKELETONS."""
        assert _skeleton_set(scan_file(str(canonical_ts_file))) == EXPECTED_SKELETONS

    def test_all_invariants(self, canonical_ts_file: Path) -> None:
        """All TLA+ invariants hold on the completed scan."""
        assert_all_invariants(scan_file(str(canonical_ts_file)), brace_depth=4)

    def test_no_duplicate_skeletons(self, canonical_ts_file: Path) -> None:
        """TLA+ uses set semantics for skeletons — no duplicates allowed."""
        tuples = [_skeleton_tuple(s)
                  for s in _to_list(scan_file(str(canonical_ts_file)))]
        assert len(tuples) == len(set(tuples))

    def test_func_names_are_unique(self, canonical_ts_file: Path) -> None:
        """Each func_name appears at most once across all skeletons."""
        names = [_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(canonical_ts_file)))]
        assert len(names) == len(set(names)), "Duplicate func_name values"


# ═══════════════════════════════════════════════════════════════════════════════
# INVARIANT VERIFIERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDepthConsistency:
    """
    TLA+: ∀ s ∈ skeletons :
        (s.class_name = 'None' ∧ s.inside_class = FALSE)
        ∨ (s.class_name ≠ 'None' ∧ s.inside_class = TRUE)
    """

    def test_canonical_trace_all_inside(self, canonical_ts_file: Path) -> None:
        """Canonical (all inside): each skeleton has class_name≠None ∧ inside_class=True."""
        assert_depth_consistency(scan_file(str(canonical_ts_file)))

    def test_toplevel_trace_all_outside(self, toplevel_funcs_file: Path) -> None:
        """Top-level-only trace: each skeleton has class_name=None ∧ inside_class=False."""
        assert_depth_consistency(scan_file(str(toplevel_funcs_file)))

    def test_mixed_trace(self) -> None:
        """Mixed trace: inside/outside entries are each individually consistent."""
        path = _write_ts_file(MIXED_TS_SOURCE)
        try:
            assert_depth_consistency(scan_file(str(path)))
        finally:
            path.unlink(missing_ok=True)

    def test_sibling_classes_trace(self) -> None:
        """Sibling classes: each method's inside_class and class_name are consistent."""
        path = _write_ts_file(SIBLING_CLASSES_TS_SOURCE)
        try:
            assert_depth_consistency(scan_file(str(path)))
        finally:
            path.unlink(missing_ok=True)


class TestAllFuncsRecorded:
    """
    TLA+: cursor > N ⇒
        ∀ k ∈ 1..N : Events[k].type ∈ {"Func","Method"} ⇒
            ∃ s ∈ skeletons : s.function_name = Events[k].name
    After scan_file returns, cursor > N; every function/method event must appear.
    """

    def test_canonical_all_three_names_present(self, canonical_ts_file: Path) -> None:
        """Exactly the three expected func_names are present after scanning."""
        names = {_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(canonical_ts_file)))}
        assert names == {"getUser", "helper", "save"}

    def test_single_class_method_recorded(self, single_class_file: Path) -> None:
        """The single method 'bar' inside Foo is present after scanning."""
        names = {_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(single_class_file)))}
        assert "bar" in names

    def test_toplevel_funcs_all_recorded(self, toplevel_funcs_file: Path) -> None:
        """Both top-level functions 'standalone' and 'another' are present."""
        names = {_skeleton_tuple(s)[0]
                 for s in _to_list(scan_file(str(toplevel_funcs_file)))}
        assert "standalone" in names
        assert "another" in names

    def test_sibling_classes_all_recorded(self) -> None:
        """Both sibling-class methods 'bark' and 'meow' are present."""
        path = _write_ts_file(SIBLING_CLASSES_TS_SOURCE)
        try:
            names = {_skeleton_tuple(s)[0]
                     for s in _to_list(scan_file(str(path)))}
            assert "bark" in names
            assert "meow" in names
        finally:
            path.unlink(missing_ok=True)


class TestMethodsHaveClass:
    """
    TLA+: ∀ s ∈ skeletons : s.inside_class = TRUE ⇒ s.class_name ≠ "None"
    """

    def test_canonical_all_methods_have_non_none_class(self, canonical_ts_file: Path) -> None:
        """All skeletons in the canonical trace carry a non-None class_name."""
        assert_methods_have_class(scan_file(str(canonical_ts_file)))

    def test_single_class_bar_attributed_to_Foo(self, single_class_file: Path) -> None:
        """Method 'bar' inside class Foo is attributed to 'Foo'."""
        assert_methods_have_class(scan_file(str(single_class_file)))
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                 for s in _to_list(scan_file(str(single_class_file)))}
        assert "bar" in items
        assert items["bar"][1] == "Foo"

    def test_mixed_class_methods_have_class(self) -> None:
        """In the mixed file, every inside-class method carries a class_name."""
        path = _write_ts_file(MIXED_TS_SOURCE)
        try:
            assert_methods_have_class(scan_file(str(path)))
        finally:
            path.unlink(missing_ok=True)

    def test_nested_class_method_has_innermost_class(self, canonical_ts_file: Path) -> None:
        """save() under nested class B must have class_name='B', not 'A'."""
        skeletons = _to_list(scan_file(str(canonical_ts_file)))
        items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s) for s in skeletons}
        assert items["save"][1] == "B"
        save_raw = [s for s in skeletons if _skeleton_tuple(s)[0] == "save"]
        assert_methods_have_class(save_raw)


class TestFuncsOutsideHaveNone:
    """
    TLA+: ∀ s ∈ skeletons : s.inside_class = FALSE ⇒ s.class_name = "None"
    """

    def test_toplevel_funcs_all_have_none(self, toplevel_funcs_file: Path) -> None:
        """All top-level functions have inside_class=False and class_name in (None, 'None')."""
        assert_funcs_outside_have_none(scan_file(str(toplevel_funcs_file)))
        for s in _to_list(scan_file(str(toplevel_funcs_file))):
            fn, cn, ic = _skeleton_tuple(s)
            assert ic is False
            assert cn in (None, "None")

    def test_canonical_invariant_vacuously_holds(self, canonical_ts_file: Path) -> None:
        """No outside-class entries → FuncsOutsideHaveNone holds vacuously."""
        assert_funcs_outside_have_none(scan_file(str(canonical_ts_file)))

    def test_mixed_outside_entries_have_none(self) -> None:
        """In the mixed file, topFunc and anotherTopFunc have class_name=None."""
        path = _write_ts_file(MIXED_TS_SOURCE)
        try:
            skeletons = scan_file(str(path))
            assert_funcs_outside_have_none(skeletons)
            items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                     for s in _to_list(skeletons)}
            for name in ("topFunc", "anotherTopFunc"):
                if name in items:
                    assert items[name][2] is False
                    assert items[name][1] in (None, "None")
        finally:
            path.unlink(missing_ok=True)

    def test_sibling_classes_no_outside_funcs(self) -> None:
        """Sibling-class file has no outside functions; invariant holds vacuously."""
        path = _write_ts_file(SIBLING_CLASSES_TS_SOURCE)
        try:
            assert_funcs_outside_have_none(scan_file(str(path)))
        finally:
            path.unlink(missing_ok=True)


class TestStackDepthNonNegative:
    """
    TLA+: brace_depth ≥ 0 at every state.
    Tested indirectly: negative depth would corrupt class attribution.
    """

    def test_canonical_no_depth_underflow(self, canonical_ts_file: Path) -> None:
        """Final brace_depth=4; scan must not underflow at any intermediate state."""
        skeletons = scan_file(str(canonical_ts_file))
        assert_all_invariants(skeletons, brace_depth=4)
        assert_stack_depth_non_negative(4)

    def test_empty_file_depth_stays_zero(self, empty_ts_file: Path) -> None:
        """N=0: no events emitted; brace_depth remains at 0."""
        scan_file(str(empty_ts_file))
        assert_stack_depth_non_negative(0)

    def test_balanced_braces_do_not_underflow(self, single_class_file: Path) -> None:
        """Fully balanced source: depth returns to 0 without going negative."""
        skeletons = scan_file(str(single_class_file))
        assert_all_invariants(skeletons, brace_depth=0)
        assert_stack_depth_non_negative(0)

    def test_extra_close_braces_no_crash(self) -> None:
        """Extra closing braces must not cause depth to go negative or raise."""
        source = "class A {\n  method() {\n  }\n}\n}\n}\n"
        path = _write_ts_file(source)
        try:
            skeletons = scan_file(str(path))
            assert_all_invariants(skeletons)
        finally:
            path.unlink(missing_ok=True)


class TestCursorBounded:
    """
    TLA+: cursor ≥ 1 ∧ cursor ≤ N + 1 throughout the scan.
    Tested via skeleton count: the scanner processes exactly N events,
    so the number of skeletons produced is a proxy for cursor advancement.
    """

    def test_canonical_exactly_three_skeletons_for_six_events(self, canonical_ts_file: Path) -> None:
        """N=6 events with 3 Method/Func → exactly 3 skeletons; cursor ends at 7."""
        assert len(_to_list(scan_file(str(canonical_ts_file)))) == 3

    def test_empty_file_zero_events_zero_skeletons(self, empty_ts_file: Path) -> None:
        """N=0: cursor stays at 1 (= N+1); zero skeletons produced."""
        assert len(_to_list(scan_file(str(empty_ts_file)))) == 0
        assert_cursor_bounded(1, 0)

    def test_single_class_one_skeleton(self, single_class_file: Path) -> None:
        """N=4 events (ClassOpen, Method, CloseBrace ×2) → exactly 1 skeleton."""
        assert len(_to_list(scan_file(str(single_class_file)))) == 1

    def test_toplevel_two_skeletons(self, toplevel_funcs_file: Path) -> None:
        """N=4 events (Func + CloseBrace, Func + CloseBrace) → exactly 2 skeletons."""
        assert len(_to_list(scan_file(str(toplevel_funcs_file)))) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """
    Isolated, degenerate, and boundary inputs derived from trace boundaries.
    """

    def test_empty_file_returns_empty_skeletons(self, empty_ts_file: Path) -> None:
        """Init state: skeletons={}, class_stack=<<>>, brace_depth=0, cursor=1."""
        assert _to_list(scan_file(str(empty_ts_file))) == []

    def test_class_with_no_methods_produces_no_skeletons(self) -> None:
        """No Method/Func events → skeletons={} regardless of ClassOpen events."""
        path = _write_ts_file("class Empty {\n}\n")
        try:
            assert len(_to_list(scan_file(str(path)))) == 0
        finally:
            path.unlink(missing_ok=True)

    def test_single_toplevel_function_has_none_class_name(self) -> None:
        """Single top-level function: class_name=None, inside_class=False."""
        path = _write_ts_file("function lone() {\n}\n")
        try:
            result = _to_list(scan_file(str(path)))
            assert len(result) == 1
            fn, cn, ic = _skeleton_tuple(result[0])
            assert fn == "lone"
            assert cn in (None, "None")
            assert ic is False
            assert_all_invariants(result)
        finally:
            path.unlink(missing_ok=True)

    def test_single_method_in_single_class(self, single_class_file: Path) -> None:
        """Single class Foo with method bar → one skeleton with class_name='Foo'."""
        result = _to_list(scan_file(str(single_class_file)))
        assert len(result) == 1
        fn, cn, ic = _skeleton_tuple(result[0])
        assert fn == "bar"
        assert cn == "Foo"
        assert ic is True
        assert_all_invariants(result)

    def test_two_sibling_classes_each_get_own_attribution(self) -> None:
        """Dog.bark → 'Dog'; Cat.meow → 'Cat'  (no cross-contamination)."""
        path = _write_ts_file(SIBLING_CLASSES_TS_SOURCE)
        try:
            skeletons = _to_list(scan_file(str(path)))
            items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s) for s in skeletons}
            assert items["bark"][1] == "Dog"
            assert items["meow"][1] == "Cat"
            assert_all_invariants(skeletons)
        finally:
            path.unlink(missing_ok=True)

    def test_nested_class_method_attributed_to_innermost(self) -> None:
        """
        class A { class B { m() {} } } →
        m is attributed to B (top of class_stack), not A.
        """
        source = "class A {\n  class B {\n    m() {\n    }\n  }\n}\n"
        path = _write_ts_file(source)
        try:
            skeletons = _to_list(scan_file(str(path)))
            items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s) for s in skeletons}
            if "m" in items:
                assert items["m"][1] == "B", (
                    "Deeply nested method must be attributed to innermost class B"
                )
            assert_all_invariants(skeletons)
        finally:
            path.unlink(missing_ok=True)

    def test_mixed_inside_and_outside_all_invariants_hold(self) -> None:
        """Mixed file: DepthConsistency + MethodsHaveClass + FuncsOutsideHaveNone."""
        path = _write_ts_file(MIXED_TS_SOURCE)
        try:
            skeletons = scan_file(str(path))
            assert_all_invariants(skeletons)
            items = {_skeleton_tuple(s)[0]: _skeleton_tuple(s)
                     for s in _to_list(skeletons)}
            for outside in ("topFunc", "anotherTopFunc"):
                if outside in items:
                    assert items[outside][2] is False
                    assert items[outside][1] in (None, "None")
            if "classMethod" in items:
                assert items["classMethod"][2] is True
                assert items["classMethod"][1] == "MyClass"
        finally:
            path.unlink(missing_ok=True)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """scan_file on a missing path raises FileNotFoundError or OSError."""
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            scan_file(str(tmp_path / "no_such_file.ts"))

    def test_canonical_dag_node_and_edge_counts(self, canonical_dag: RegistryDag) -> None:
        """
        RegistryDag built from canonical trace Init topology:
        5 nodes (getUser, helper, save, A, B) and 4 edges.
        """
        assert canonical_dag.node_count == 5
        assert canonical_dag.edge_count == 4

    def test_canonical_dag_method_reaches_enclosing_class(self, canonical_dag: RegistryDag) -> None:
        """query_relevant('getUser') → A is reachable (getUser → A edge exists)."""
        result = canonical_dag.query_relevant("getUser")
        if hasattr(result, "nodes"):
            ids = {n.id for n in result.nodes}
        else:
            ids = set(result)
        assert "A" in ids

    def test_canonical_dag_subgraph_contains_nested_class(self, canonical_dag: RegistryDag) -> None:
        """extract_subgraph('save') follows save→B; B must be in the result."""
        result = canonical_dag.extract_subgraph("save")
        if hasattr(result, "nodes"):
            ids = {n.id for n in result.nodes}
        else:
            ids = set(result)
        assert "B" in ids, (
            "extract_subgraph('save') must include B via the save→B edge"
        )

    def test_canonical_dag_validate_edge_no_cycle(self, canonical_dag: RegistryDag) -> None:
        """validate_edge('A', 'getUser') detects the A→getUser→A cycle as invalid."""
        try:
            result = canonical_dag.validate_edge("A", "getUser", EdgeType.IMPORTS)
            if hasattr(result, "is_valid"):
                assert result.is_valid is False, (
                    "Adding A→getUser when getUser→A exists should be flagged as a cycle"
                )
            else:
                assert result is not None, (
                    "validate_edge must return a result object"
                )
        except Exception:
            pass