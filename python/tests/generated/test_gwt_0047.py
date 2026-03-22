import textwrap
import pytest
from pathlib import Path

from pathlib import Path
from registry.scanner_python import scan_file as _scan_file

def scan_file(path):
    return _scan_file(Path(path) if isinstance(path, str) else path)

_NESTED_SOURCE = textwrap.dedent("""\
    class A:
        def f(self):
            pass
        class B:
            def g(self):
                pass

    def h():
        pass
    """)


def _get(skeleton, key):
    if isinstance(skeleton, dict):
        return skeleton[key]
    return getattr(skeleton, key)


def _skeletons_by_name(skeletons):
    return {_get(s, "function_name"): s for s in skeletons}


def _assert_all_defs_recorded(skeletons):
    names = {_get(s, "function_name") for s in skeletons}
    assert "f" in names, "skeleton for 'f' missing"
    assert "g" in names, "skeleton for 'g' missing"
    assert "h" in names, "skeleton for 'h' missing"


def _assert_top_level_have_none(skeletons):
    for s in skeletons:
        if _get(s, "def_indent") == 0:
            cn = _get(s, "class_name")
            assert cn is None, (
                f"top-level '{_get(s, 'func_name')}' should have class_name=None, got {cn!r}"
            )


def _assert_nested_have_class_name(skeletons):
    for s in skeletons:
        if _get(s, "def_indent") > 0:
            cn = _get(s, "class_name")
            assert cn is not None, (
                f"nested '{_get(s, 'func_name')}' should have a class_name, got None"
            )


def _assert_depth_consistency(skeletons):
    for s in skeletons:
        cn = _get(s, "class_name")
        assert cn is None or isinstance(cn, str), (
            f"class_name must be None or str, got {type(cn)} for '{_get(s, 'func_name')}'"
        )


def _assert_all_invariants(skeletons):
    _assert_top_level_have_none(skeletons)
    _assert_nested_have_class_name(skeletons)
    _assert_depth_consistency(skeletons)


def _assert_final_state(skeletons):
    assert len(skeletons) == 3, f"expected 3 skeletons, got {len(skeletons)}"
    by_name = _skeletons_by_name(skeletons)

    assert "f" in by_name
    assert _get(by_name["f"], "def_indent") == 1
    assert _get(by_name["f"], "class_name") == "A"

    assert "g" in by_name
    assert _get(by_name["g"], "def_indent") == 2
    assert _get(by_name["g"], "class_name") == "B"

    assert "h" in by_name
    assert _get(by_name["h"], "def_indent") == 0
    assert _get(by_name["h"], "class_name") is None


@pytest.fixture
def nested_file(tmp_path):
    p = tmp_path / "nested.py"
    p.write_text(_NESTED_SOURCE)
    return p


@pytest.fixture
def empty_file(tmp_path):
    p = tmp_path / "empty.py"
    p.write_text("")
    return p


@pytest.fixture
def top_level_only_file(tmp_path):
    src = textwrap.dedent("""\
        def alpha():
            pass

        def beta():
            pass
        """)
    p = tmp_path / "top_level.py"
    p.write_text(src)
    return p


@pytest.fixture
def single_class_file(tmp_path):
    src = textwrap.dedent("""\
        class MyClass:
            def method_one(self):
                pass

            def method_two(self):
                pass
        """)
    p = tmp_path / "single_class.py"
    p.write_text(src)
    return p


@pytest.fixture
def deeply_nested_file(tmp_path):
    src = textwrap.dedent("""\
        class Outer:
            class Inner:
                def deep_method(self):
                    pass
            def shallow_method(self):
                pass

        def standalone():
            pass
        """)
    p = tmp_path / "deep.py"
    p.write_text(src)
    return p


def test_trace_1_nested_depth_full_scan(nested_file):
    skeletons = scan_file(nested_file)
    _assert_final_state(skeletons)
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_2_nested_depth_full_scan(nested_file):
    skeletons = scan_file(nested_file)
    _assert_final_state(skeletons)
    _assert_all_defs_recorded(skeletons)
    _assert_top_level_have_none(skeletons)
    _assert_nested_have_class_name(skeletons)
    _assert_depth_consistency(skeletons)


def test_trace_3_nested_depth_full_scan(nested_file):
    skeletons_a = scan_file(nested_file)
    skeletons_b = scan_file(nested_file)
    _assert_final_state(skeletons_a)
    _assert_final_state(skeletons_b)
    _assert_all_defs_recorded(skeletons_a)
    _assert_all_defs_recorded(skeletons_b)
    _assert_all_invariants(skeletons_a)
    _assert_all_invariants(skeletons_b)


def test_trace_4_all_defs_recorded(nested_file):
    skeletons = scan_file(nested_file)
    names = {_get(s, "function_name") for s in skeletons}
    assert names == {"f", "g", "h"}, f"unexpected name set: {names}"
    _assert_all_defs_recorded(skeletons)
    _assert_depth_consistency(skeletons)


def test_trace_5_top_level_have_none(nested_file):
    skeletons = scan_file(nested_file)
    by_name = _skeletons_by_name(skeletons)
    assert _get(by_name["h"], "def_indent") == 0
    assert _get(by_name["h"], "class_name") is None
    _assert_top_level_have_none(skeletons)
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_6_nested_have_class_name(nested_file):
    skeletons = scan_file(nested_file)
    by_name = _skeletons_by_name(skeletons)
    assert _get(by_name["f"], "class_name") == "A"
    assert _get(by_name["g"], "class_name") == "B"
    _assert_nested_have_class_name(skeletons)
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_7_class_stack_cleared_at_top_level_def(nested_file):
    skeletons = scan_file(nested_file)
    by_name = _skeletons_by_name(skeletons)
    assert _get(by_name["h"], "class_name") is None
    assert _get(by_name["f"], "class_name") == "A"
    assert _get(by_name["g"], "class_name") == "B"
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_8_def_indent_values_match_trace(nested_file):
    skeletons = scan_file(nested_file)
    by_name = _skeletons_by_name(skeletons)
    assert _get(by_name["f"], "def_indent") == 1
    assert _get(by_name["g"], "def_indent") == 2
    assert _get(by_name["h"], "def_indent") == 0
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_9_skeleton_count_equals_def_event_count(nested_file):
    skeletons = scan_file(nested_file)
    assert len(skeletons) == 3
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


def test_trace_10_full_state_reconstruction(nested_file):
    skeletons = scan_file(nested_file)
    expected = {
        "f": {"def_indent": 1, "class_name": "A"},
        "g": {"def_indent": 2, "class_name": "B"},
        "h": {"def_indent": 0, "class_name": None},
    }
    assert len(skeletons) == len(expected)
    by_name = _skeletons_by_name(skeletons)
    for func_name, attrs in expected.items():
        assert func_name in by_name, f"missing skeleton for '{func_name}'"
        for field, value in attrs.items():
            actual = _get(by_name[func_name], field)
            assert actual == value, (
                f"skeleton '{func_name}': expected {field}={value!r}, got {actual!r}"
            )
    _assert_all_defs_recorded(skeletons)
    _assert_all_invariants(skeletons)


class TestDepthConsistency:

    def test_nested_source(self, nested_file):
        skeletons = scan_file(nested_file)
        _assert_depth_consistency(skeletons)

    def test_top_level_only(self, top_level_only_file):
        skeletons = scan_file(top_level_only_file)
        _assert_depth_consistency(skeletons)

    def test_single_class(self, single_class_file):
        skeletons = scan_file(single_class_file)
        _assert_depth_consistency(skeletons)

    def test_deeply_nested(self, deeply_nested_file):
        skeletons = scan_file(deeply_nested_file)
        _assert_depth_consistency(skeletons)


class TestAllDefsRecorded:

    def test_nested_source_has_three_defs(self, nested_file):
        skeletons = scan_file(nested_file)
        _assert_all_defs_recorded(skeletons)
        assert len(skeletons) == 3

    def test_top_level_only_has_two_defs(self, top_level_only_file):
        skeletons = scan_file(top_level_only_file)
        names = {_get(s, "function_name") for s in skeletons}
        assert "alpha" in names
        assert "beta" in names
        assert len(skeletons) == 2

    def test_single_class_has_two_methods(self, single_class_file):
        skeletons = scan_file(single_class_file)
        names = {_get(s, "function_name") for s in skeletons}
        assert "method_one" in names
        assert "method_two" in names
        assert len(skeletons) == 2

    def test_deeply_nested_records_all_defs(self, deeply_nested_file):
        skeletons = scan_file(deeply_nested_file)
        names = {_get(s, "function_name") for s in skeletons}
        assert "deep_method" in names
        assert "shallow_method" in names
        assert "standalone" in names
        assert len(skeletons) == 3


class TestTopLevelHaveNone:

    def test_nested_source_h_is_none(self, nested_file):
        skeletons = scan_file(nested_file)
        _assert_top_level_have_none(skeletons)
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["h"], "class_name") is None

    def test_all_top_level_are_none(self, top_level_only_file):
        skeletons = scan_file(top_level_only_file)
        _assert_top_level_have_none(skeletons)
        for s in skeletons:
            assert _get(s, "class_name") is None

    def test_deeply_nested_standalone_is_none(self, deeply_nested_file):
        skeletons = scan_file(deeply_nested_file)
        _assert_top_level_have_none(skeletons)
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["standalone"], "class_name") is None


class TestNestedHaveClassName:

    def test_nested_source_f_and_g_have_class_name(self, nested_file):
        skeletons = scan_file(nested_file)
        _assert_nested_have_class_name(skeletons)
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["f"], "class_name") is not None
        assert _get(by_name["g"], "class_name") is not None

    def test_single_class_methods_have_class_name(self, single_class_file):
        skeletons = scan_file(single_class_file)
        _assert_nested_have_class_name(skeletons)
        for s in skeletons:
            assert _get(s, "class_name") is not None

    def test_deeply_nested_methods_have_class_name(self, deeply_nested_file):
        skeletons = scan_file(deeply_nested_file)
        _assert_nested_have_class_name(skeletons)
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["deep_method"], "class_name") is not None
        assert _get(by_name["shallow_method"], "class_name") is not None


class TestEdgeCases:

    def test_empty_file_returns_no_skeletons(self, empty_file):
        skeletons = scan_file(empty_file)
        assert list(skeletons) == []

    def test_class_with_no_methods(self, tmp_path):
        src = textwrap.dedent("""\
            class Empty:
                pass
            """)
        p = tmp_path / "empty_class.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert list(skeletons) == []

    def test_top_level_function_only(self, tmp_path):
        src = "def solo():\n    pass\n"
        p = tmp_path / "solo.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert len(skeletons) == 1
        s = skeletons[0]
        assert _get(s, "function_name") == "solo"
        assert _get(s, "def_indent") == 0
        assert _get(s, "class_name") is None
        _assert_all_invariants(skeletons)

    def test_sibling_classes_do_not_bleed(self, tmp_path):
        src = textwrap.dedent("""\
            class Foo:
                def foo_method(self):
                    pass

            class Bar:
                def bar_method(self):
                    pass
            """)
        p = tmp_path / "siblings.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert len(skeletons) == 2
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["foo_method"], "class_name") == "Foo"
        assert _get(by_name["bar_method"], "class_name") == "Bar"
        _assert_all_invariants(skeletons)

    def test_interleaved_top_level_and_class_methods(self, tmp_path):
        src = textwrap.dedent("""\
            def before():
                pass

            class MyClass:
                def inside(self):
                    pass

            def after():
                pass
            """)
        p = tmp_path / "interleaved.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert len(skeletons) == 3
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["before"], "class_name") is None
        assert _get(by_name["inside"], "class_name") == "MyClass"
        assert _get(by_name["after"], "class_name") is None
        _assert_all_invariants(skeletons)

    def test_deeply_nested_class_resolves_innermost(self, tmp_path):
        src = textwrap.dedent("""\
            class L0:
                class L1:
                    class L2:
                        def deep(self):
                            pass
            """)
        p = tmp_path / "triple_nest.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert len(skeletons) == 1
        s = skeletons[0]
        assert _get(s, "function_name") == "deep"
        assert _get(s, "class_name") == "L2"
        assert _get(s, "def_indent") == 3
        _assert_all_invariants(skeletons)

    def test_def_immediately_after_nested_class_uses_outer(self, tmp_path):
        src = textwrap.dedent("""\
            class L0:
                class Inner:
                    def inner_method(self):
                        pass
                def outer_method(self):
                    pass
            """)
        p = tmp_path / "back_out.py"
        p.write_text(src)
        skeletons = scan_file(p)
        assert len(skeletons) == 2
        by_name = _skeletons_by_name(skeletons)
        assert _get(by_name["inner_method"], "class_name") == "Inner"
        assert _get(by_name["outer_method"], "class_name") == "L0"
        _assert_all_invariants(skeletons)

    def test_no_false_skeletons_for_class_nodes(self, nested_file):
        skeletons = scan_file(nested_file)
        names = {_get(s, "function_name") for s in skeletons}
        assert "A" not in names, "class 'A' must not be recorded as a skeleton"
        assert "B" not in names, "class 'B' must not be recorded as a skeleton"

    def test_path_as_string_accepted(self, nested_file):
        skeletons_from_path = scan_file(nested_file)
        skeletons_from_str = scan_file(str(nested_file))
        assert len(skeletons_from_path) == len(skeletons_from_str)
        by_name_path = _skeletons_by_name(skeletons_from_path)
        by_name_str = _skeletons_by_name(skeletons_from_str)
        for name in ("f", "g", "h"):
            assert _get(by_name_path[name], "class_name") == _get(by_name_str[name], "class_name")
            assert _get(by_name_path[name], "def_indent") == _get(by_name_str[name], "def_indent")