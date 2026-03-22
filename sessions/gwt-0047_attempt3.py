import textwrap
import pytest
from pathlib import Path

from registry.scanner_python import scan_file
from registry.crawl_types import Skeleton


# ---------------------------------------------------------------------------
# Canonical source file
# Derived from the TLA+ Events sequence (identical across all 10 traces):
#   [type="Class", name="A"]      – top-level class
#   [type="Def",   name="f"]      – method inside A  → class_name="A"
#   [type="Class", name="B"]      – nested class inside A
#   [type="Def",   name="g"]      – method inside B  → class_name="B"
#   [type="Def",   name="h"]      – top-level def    → class_name=None
# ---------------------------------------------------------------------------

NESTED_SOURCE = textwrap.dedent("""\
    class A:
        def f(self):
            pass
        class B:
            def g(self):
                pass

    def h():
        pass
""")

# Final skeletons expected at State 18 in every trace
EXPECTED_SKELETONS = frozenset([
    ("f", "A"),
    ("g", "B"),
    ("h", None),
])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    """Write the canonical nested-class source to a temp .py file."""
    p = tmp_path / "subject.py"
    p.write_text(NESTED_SOURCE)
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_tuples(skeletons):
    """Normalise scan_file output to (function_name, class_name) tuples."""
    return frozenset(
        (s.function_name, s.class_name)
        for s in skeletons
    )


def _by_name(skeletons, name):
    return next(s for s in skeletons if s.function_name == name)


def _is_nested(s: Skeleton) -> bool:
    """True iff the skeleton belongs to a method inside a class."""
    return s.class_name is not None


def _is_top_level(s: Skeleton) -> bool:
    """True iff the skeleton is a module-level (top-level) function."""
    return s.class_name is None


# ---------------------------------------------------------------------------
# Invariant helpers (translated from TLA+)
# ---------------------------------------------------------------------------

def _assert_all_defs_recorded(skeletons, expected_names):
    """AllDefsRecorded: every Def event must appear in skeletons."""
    names = {s.function_name for s in skeletons}
    for n in expected_names:
        assert n in names, f"Def {n!r} not recorded in skeletons"


def _assert_top_level_have_none(skeletons):
    """TopLevelHaveNone: module-level functions have class_name=None."""
    for s in skeletons:
        if _is_top_level(s):
            assert s.class_name is None, (
                f"Top-level func {s.function_name!r} must have class_name=None, "
                f"got {s.class_name!r}"
            )


def _assert_nested_have_class_name(skeletons):
    """NestedHaveClassName: methods inside a class have non-None class_name."""
    for s in skeletons:
        if _is_nested(s):
            assert s.class_name is not None, (
                f"Nested func {s.function_name!r} must have a non-None class_name"
            )


def _assert_depth_consistency(skeletons):
    """DepthConsistency: class_name is either None or a non-empty string."""
    for s in skeletons:
        if s.class_name is None:
            pass  # top-level: fine
        else:
            assert isinstance(s.class_name, str) and s.class_name, (
                f"func {s.function_name!r}: class_name must be a non-empty string, "
                f"got {s.class_name!r}"
            )


def _assert_all_invariants(skeletons, expected_def_names=("f", "g", "h")):
    _assert_all_defs_recorded(skeletons, expected_def_names)
    _assert_top_level_have_none(skeletons)
    _assert_nested_have_class_name(skeletons)
    _assert_depth_consistency(skeletons)


# ---------------------------------------------------------------------------
# Trace 1 – full final-state verification
# State 18: skeletons = {h/None, f/A, g/B}
# ---------------------------------------------------------------------------

def test_trace_1_full_scan_matches_final_state(source_file):
    skeletons = scan_file(source_file)

    assert len(skeletons) == 3, "Exactly 3 Def events must produce 3 skeletons"

    h = _by_name(skeletons, "h")
    assert h.class_name is None

    f = _by_name(skeletons, "f")
    assert f.class_name == "A"

    g = _by_name(skeletons, "g")
    assert g.class_name == "B"

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 2 – AllDefsRecorded
# State 18: all three Def names appear in skeletons
# ---------------------------------------------------------------------------

def test_trace_2_all_defs_recorded(source_file):
    skeletons = scan_file(source_file)

    names = {s.function_name for s in skeletons}
    assert "f" in names, "Def 'f' must be recorded"
    assert "g" in names, "Def 'g' must be recorded"
    assert "h" in names, "Def 'h' must be recorded"

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 3 – TopLevelHaveNone
# State 18: h is a top-level def with class_name=None
# ---------------------------------------------------------------------------

def test_trace_3_top_level_function_has_none_class(source_file):
    skeletons = scan_file(source_file)

    top_level = [s for s in skeletons if _is_top_level(s)]
    assert len(top_level) == 1
    assert top_level[0].function_name == "h"
    assert top_level[0].class_name is None

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 4 – NestedHaveClassName
# State 18: f and g are both inside classes and have non-None class_name
# ---------------------------------------------------------------------------

def test_trace_4_nested_functions_have_class_name(source_file):
    skeletons = scan_file(source_file)

    nested = [s for s in skeletons if _is_nested(s)]
    assert len(nested) == 2

    for s in nested:
        assert s.class_name is not None, (
            f"Nested func {s.function_name!r} must have a class_name"
        )

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 5 – f assigned to class A (enclosing at indent 0)
# State 6: skeleton {function_name="f", class_name="A"} inserted
# ---------------------------------------------------------------------------

def test_trace_5_f_assigned_to_class_A(source_file):
    skeletons = scan_file(source_file)

    f = _by_name(skeletons, "f")
    assert f.class_name == "A", (
        f"'f' is defined inside class A; expected class_name='A', got {f.class_name!r}"
    )

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 6 – g assigned to class B (innermost enclosing class)
# State 12: skeleton {function_name="g", class_name="B"} inserted
# ---------------------------------------------------------------------------

def test_trace_6_g_assigned_to_class_B(source_file):
    skeletons = scan_file(source_file)

    g = _by_name(skeletons, "g")
    assert g.class_name == "B", (
        f"'g' is defined inside class B; expected class_name='B', got {g.class_name!r}"
    )

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 7 – skeleton count matches Def-event count exactly
# ---------------------------------------------------------------------------

def test_trace_7_skeleton_count_equals_def_count(source_file):
    skeletons = scan_file(source_file)

    # 5 events; 3 are Def events → 3 skeletons
    assert len(skeletons) == 3

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 8 – class events do NOT produce skeletons
# ---------------------------------------------------------------------------

def test_trace_8_class_events_not_in_skeletons(source_file):
    skeletons = scan_file(source_file)

    func_names = {s.function_name for s in skeletons}
    # "A" and "B" are Class events; they must not appear as function_name entries
    assert "A" not in func_names, "Class 'A' must not appear as a skeleton function_name"
    assert "B" not in func_names, "Class 'B' must not appear as a skeleton function_name"
    assert func_names == {"f", "g", "h"}

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 9 – DepthConsistency: class_name is None <=> top-level function
# ---------------------------------------------------------------------------

def test_trace_9_depth_consistency(source_file):
    skeletons = scan_file(source_file)

    for s in skeletons:
        if s.class_name is None:
            # top-level: must not be in any class
            assert _is_top_level(s)
        else:
            # nested: class_name must be a non-empty string
            assert isinstance(s.class_name, str) and s.class_name

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Trace 10 – exact mapping of function_name → class_name
# ---------------------------------------------------------------------------

def test_trace_10_exact_class_name_mapping(source_file):
    skeletons = scan_file(source_file)

    class_map = {s.function_name: s.class_name for s in skeletons}
    assert class_map == {"f": "A", "g": "B", "h": None}, (
        f"Expected exact class_name mapping, got: {class_map}"
    )
    assert _as_tuples(skeletons) == EXPECTED_SKELETONS

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Invariant verifiers – each covers ≥2 distinct trace-derived topologies
# ---------------------------------------------------------------------------

def test_invariant_all_defs_recorded_two_topologies(tmp_path):
    """AllDefsRecorded across canonical topology and flat-only topology."""
    # Topology 1: canonical (Traces 1-10)
    p1 = tmp_path / "canonical.py"
    p1.write_text(NESTED_SOURCE)
    s1 = scan_file(p1)
    _assert_all_defs_recorded(s1, ("f", "g", "h"))

    # Topology 2: two flat top-level functions (no Class events)
    p2 = tmp_path / "flat.py"
    p2.write_text(textwrap.dedent("""\
        def alpha():
            pass
        def beta():
            pass
    """))
    s2 = scan_file(p2)
    _assert_all_defs_recorded(s2, ("alpha", "beta"))


def test_invariant_top_level_have_none_two_topologies(tmp_path):
    """TopLevelHaveNone across canonical topology and a purely flat topology."""
    p1 = tmp_path / "canonical.py"
    p1.write_text(NESTED_SOURCE)
    s1 = scan_file(p1)
    _assert_top_level_have_none(s1)

    p2 = tmp_path / "flat.py"
    p2.write_text(textwrap.dedent("""\
        def standalone_a():
            pass
        def standalone_b():
            pass
    """))
    s2 = scan_file(p2)
    _assert_top_level_have_none(s2)
    for s in s2:
        assert s.class_name is None


def test_invariant_nested_have_class_name_two_topologies(tmp_path):
    """NestedHaveClassName across canonical and single-class topologies."""
    p1 = tmp_path / "canonical.py"
    p1.write_text(NESTED_SOURCE)
    s1 = scan_file(p1)
    _assert_nested_have_class_name(s1)

    p2 = tmp_path / "single_class.py"
    p2.write_text(textwrap.dedent("""\
        class Container:
            def method(self):
                pass
    """))
    s2 = scan_file(p2)
    _assert_nested_have_class_name(s2)
    assert len(s2) == 1
    assert s2[0].class_name == "Container"


def test_invariant_depth_consistency_two_topologies(tmp_path):
    """DepthConsistency across canonical and deep-nesting topologies."""
    p1 = tmp_path / "canonical.py"
    p1.write_text(NESTED_SOURCE)
    s1 = scan_file(p1)
    _assert_depth_consistency(s1)

    # Deeply nested: class_name must be the *innermost* enclosing class
    p2 = tmp_path / "deep.py"
    p2.write_text(textwrap.dedent("""\
        class Outer:
            class Inner:
                def deep_method(self):
                    pass
    """))
    s2 = scan_file(p2)
    _assert_depth_consistency(s2)
    assert len(s2) == 1
    assert s2[0].function_name == "deep_method"
    assert s2[0].class_name == "Inner"   # innermost class wins


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_edge_empty_file(tmp_path):
    """scan_file on an empty file returns zero skeletons."""
    p = tmp_path / "empty.py"
    p.write_text("")
    skeletons = scan_file(p)
    assert len(skeletons) == 0


def test_edge_only_class_declarations(tmp_path):
    """File with only class bodies and no def produces zero skeletons."""
    p = tmp_path / "classes_only.py"
    p.write_text(textwrap.dedent("""\
        class A:
            pass
        class B:
            pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 0


def test_edge_only_top_level_functions(tmp_path):
    """All functions at module level get class_name=None (TopLevelHaveNone)."""
    p = tmp_path / "top_level.py"
    p.write_text(textwrap.dedent("""\
        def alpha():
            pass
        def beta():
            pass
        def gamma():
            pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 3
    for s in skeletons:
        assert s.class_name is None
    _assert_all_invariants(skeletons, ("alpha", "beta", "gamma"))


def test_edge_class_stack_resets_after_top_level_def(tmp_path):
    """After a top-level def the class context clears; subsequent defs are top-level."""
    p = tmp_path / "reset.py"
    p.write_text(textwrap.dedent("""\
        class A:
            def inside(self):
                pass
        def outside():
            pass
    """))
    skeletons = scan_file(p)
    by_name = {s.function_name: s for s in skeletons}
    assert by_name["inside"].class_name == "A"
    assert by_name["outside"].class_name is None
    _assert_all_invariants(skeletons, ("inside", "outside"))


def test_edge_single_class_single_method(tmp_path):
    """Single class / single method: method's class_name equals the class."""
    p = tmp_path / "single.py"
    p.write_text(textwrap.dedent("""\
        class MyClass:
            def my_method(self):
                pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 1
    s = skeletons[0]
    assert s.function_name == "my_method"
    assert s.class_name == "MyClass"
    _assert_all_invariants(skeletons, ("my_method",))


def test_edge_mixed_top_level_and_nested(tmp_path):
    """Mix of top-level and nested functions all satisfy every invariant."""
    p = tmp_path / "mixed.py"
    p.write_text(textwrap.dedent("""\
        def top_one():
            pass
        class Container:
            def method_one(self):
                pass
            def method_two(self):
                pass
        def top_two():
            pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 4
    by_name = {s.function_name: s for s in skeletons}
    assert by_name["top_one"].class_name is None
    assert by_name["top_two"].class_name is None
    assert by_name["method_one"].class_name == "Container"
    assert by_name["method_two"].class_name == "Container"
    _assert_all_invariants(skeletons, ("top_one", "top_two", "method_one", "method_two"))


def test_edge_deeply_nested_class_assigns_innermost(tmp_path):
    """def inside doubly-nested class gets class_name of the innermost class (not outer)."""
    p = tmp_path / "deep.py"
    p.write_text(textwrap.dedent("""\
        class Outer:
            class Inner:
                def deep_method(self):
                    pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 1
    s = skeletons[0]
    assert s.function_name == "deep_method"
    assert s.class_name == "Inner", (
        f"Innermost enclosing class must win; expected 'Inner', got {s.class_name!r}"
    )
    _assert_all_invariants(skeletons, ("deep_method",))


def test_edge_sibling_classes_independent_stacks(tmp_path):
    """Two sibling classes do not bleed class_name across each other."""
    p = tmp_path / "siblings.py"
    p.write_text(textwrap.dedent("""\
        class First:
            def first_method(self):
                pass
        class Second:
            def second_method(self):
                pass
    """))
    skeletons = scan_file(p)
    assert len(skeletons) == 2
    by_name = {s.function_name: s for s in skeletons}
    assert by_name["first_method"].class_name == "First"
    assert by_name["second_method"].class_name == "Second"
    _assert_all_invariants(skeletons, ("first_method", "second_method"))


def test_skeleton_has_file_path_and_line_number(source_file):
    """Each skeleton records the file path and a positive 1-indexed line number."""
    skeletons = scan_file(source_file)
    for s in skeletons:
        assert s.file_path == str(source_file)
        assert isinstance(s.line_number, int) and s.line_number >= 1


def test_skeleton_file_hash_is_consistent(source_file):
    """All skeletons from the same file share the same non-empty file_hash."""
    skeletons = scan_file(source_file)
    hashes = {s.file_hash for s in skeletons}
    assert len(hashes) == 1, "All skeletons from one file must share a single file_hash"
    assert "" not in hashes, "file_hash must not be empty"


def test_skeleton_line_numbers_are_ordered(source_file):
    """Skeletons are returned in source order (ascending line numbers)."""
    skeletons = scan_file(source_file)
    line_numbers = [s.line_number for s in skeletons]
    assert line_numbers == sorted(line_numbers), (
        f"Skeletons must appear in source order; got line numbers {line_numbers}"
    )