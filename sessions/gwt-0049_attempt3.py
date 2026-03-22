import unittest
import os
import tempfile
from scanner_typescript_nested_depth import scan_file


# ---------------------------------------------------------------------------
# Canonical TypeScript source derived from the TLA+ Events sequence:
#   Events[1]  ClassOpen  "A"       → class A {
#   Events[2]  Method     "getUser" → getUser() {
#   Events[3]  CloseBrace ""        → }         (brace_depth 2→1; A not popped: 1 > A.depth=0)
#   Events[4]  Func       "helper"  → helper() { (class_stack=[A] → helper gets class A)
#   Events[5]  ClassOpen  "B"       → class B {
#   Events[6]  Method     "save"    → save() {
# ---------------------------------------------------------------------------
CANONICAL_TS_SOURCE = """\
class A {
  getUser() {
  }
  helper() {
    class B {
      save() {
"""

# Final-state skeletons expected by all 10 TLC traces (State 21):
#   { func_name: "getUser", class_name: "A", inside_class: True }
#   { func_name: "helper",  class_name: "A", inside_class: True }
#   { func_name: "save",    class_name: "B", inside_class: True }
EXPECTED_FUNC_NAMES = {"getUser", "helper", "save"}
EXPECTED_BY_NAME = {
    "getUser": ("A", True),
    "helper":  ("A", True),
    "save":    ("B", True),
}


# ---------------------------------------------------------------------------
# Attribute accessor (handles both dict-like and object-like skeletons)
# ---------------------------------------------------------------------------

def _get(s, key):
    return getattr(s, key) if hasattr(s, key) else s[key]


# ---------------------------------------------------------------------------
# Invariant verifiers (TLA+ invariants translated to Python assertions)
# ---------------------------------------------------------------------------

def assert_depth_consistency(skeletons, tc):
    """DepthConsistency: class_name is None/"None" iff inside_class is False."""
    for s in skeletons:
        cn = _get(s, "class_name")
        ic = _get(s, "inside_class")
        if cn is None or cn == "None":
            tc.assertIs(ic, False,
                f"DepthConsistency violated: class_name={cn!r} but inside_class={ic!r}")
        else:
            tc.assertIs(ic, True,
                f"DepthConsistency violated: class_name={cn!r} but inside_class={ic!r}")


def assert_methods_have_class(skeletons, tc):
    """MethodsHaveClass: inside_class is True => class_name is not None/'None'."""
    for s in skeletons:
        cn = _get(s, "class_name")
        ic = _get(s, "inside_class")
        if ic is True:
            tc.assertTrue(cn is not None and cn != "None",
                f"MethodsHaveClass violated: inside_class=True but class_name={cn!r}")


def assert_funcs_outside_have_none(skeletons, tc):
    """FuncsOutsideHaveNone: inside_class is False => class_name is None/'None'."""
    for s in skeletons:
        cn = _get(s, "class_name")
        ic = _get(s, "inside_class")
        if ic is False:
            tc.assertTrue(cn is None or cn == "None",
                f"FuncsOutsideHaveNone violated: inside_class=False but class_name={cn!r}")


def assert_all_funcs_recorded(skeletons, expected_names, tc):
    """AllFuncsRecorded: every expected name appears in the skeleton set."""
    recorded = {_get(s, "func_name") for s in skeletons}
    for name in expected_names:
        tc.assertIn(name, recorded,
            f"AllFuncsRecorded violated: {name!r} not in {recorded}")


def assert_all_invariants(skeletons, tc):
    """Run all structural invariants that apply after scan_file returns."""
    sk = list(skeletons)
    assert_depth_consistency(sk, tc)
    assert_methods_have_class(sk, tc)
    assert_funcs_outside_have_none(sk, tc)


# ---------------------------------------------------------------------------
# Shared final-state assertion used by all 10 trace tests
# ---------------------------------------------------------------------------

def _assert_final_state(skeletons, tc):
    """Assert State 21 from all 10 TLC traces."""
    sk = list(skeletons)
    found = {_get(s, "func_name") for s in sk}
    tc.assertEqual(found, EXPECTED_FUNC_NAMES,
        f"Expected func names {EXPECTED_FUNC_NAMES}, got {found}")
    by_name = {_get(s, "func_name"): s for s in sk}
    for fname, (expected_class, expected_inside) in EXPECTED_BY_NAME.items():
        s = by_name[fname]
        tc.assertEqual(_get(s, "class_name"), expected_class,
            f"{fname}.class_name: expected {expected_class!r}, "
            f"got {_get(s, 'class_name')!r}")
        tc.assertIs(_get(s, "inside_class"), expected_inside,
            f"{fname}.inside_class: expected {expected_inside!r}, "
            f"got {_get(s, 'inside_class')!r}")


# ---------------------------------------------------------------------------
# Base test case with temp directory support
# ---------------------------------------------------------------------------

class BaseTS(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self._tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def ts_file(self):
        return self._write("subject.ts", CANONICAL_TS_SOURCE)


# ---------------------------------------------------------------------------
# Trace tests (10 traces)
# ---------------------------------------------------------------------------

class TestTrace1AllSkeletons(BaseTS):
    def test_all_skeletons_correct_and_invariants_hold(self):
        """Trace 1 (21 steps): scan canonical TS; verify final state and all invariants."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        _assert_final_state(sk, self)
        assert_all_funcs_recorded(sk, EXPECTED_FUNC_NAMES, self)
        assert_all_invariants(sk, self)


class TestTrace2DepthConsistency(BaseTS):
    def test_depth_consistency(self):
        """Trace 2 (21 steps): DepthConsistency — class_name xor None matches inside_class."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        assert_depth_consistency(sk, self)
        _assert_final_state(sk, self)
        assert_all_invariants(sk, self)


class TestTrace3MethodsHaveClass(BaseTS):
    def test_methods_have_class(self):
        """Trace 3 (21 steps): MethodsHaveClass — inside_class=True implies class_name set."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        assert_methods_have_class(sk, self)
        _assert_final_state(sk, self)
        assert_all_invariants(sk, self)


class TestTrace4FuncsOutsideHaveNone(BaseTS):
    def test_funcs_outside_have_none(self):
        """Trace 4 (21 steps): FuncsOutsideHaveNone — no bare functions expected here."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        assert_funcs_outside_have_none(sk, self)
        _assert_final_state(sk, self)
        assert_all_invariants(sk, self)


class TestTrace5AllFuncsRecorded(BaseTS):
    def test_all_funcs_recorded(self):
        """Trace 5 (21 steps): AllFuncsRecorded — getUser, helper, save all present."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        assert_all_funcs_recorded(sk, EXPECTED_FUNC_NAMES, self)
        _assert_final_state(sk, self)
        assert_all_invariants(sk, self)


class TestTrace6GetUserClassA(BaseTS):
    def test_getUser_class_A(self):
        """Trace 6 (21 steps): getUser is recorded with class_name='A'."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertIn("getUser", by_name, "getUser skeleton missing")
        self.assertEqual(_get(by_name["getUser"], "class_name"), "A")
        self.assertIs(_get(by_name["getUser"], "inside_class"), True)
        assert_all_invariants(sk, self)


class TestTrace7HelperBelongsToA(BaseTS):
    def test_helper_belongs_to_A_after_close_brace(self):
        """Trace 7 (21 steps): helper's class_name is 'A' — CloseBrace did not pop A."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertIn("helper", by_name, "helper skeleton missing")
        self.assertEqual(_get(by_name["helper"], "class_name"), "A",
            "helper should belong to class A: CloseBrace (depth 2→1) must not pop A "
            "(A was pushed at depth=0 and 1 > 0)")
        self.assertIs(_get(by_name["helper"], "inside_class"), True)
        assert_all_invariants(sk, self)


class TestTrace8SaveBelongsToInnerClassB(BaseTS):
    def test_save_belongs_to_innermost_class_B(self):
        """Trace 8 (21 steps): save's class_name is 'B' — innermost class wins."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertIn("save", by_name, "save skeleton missing")
        self.assertEqual(_get(by_name["save"], "class_name"), "B",
            "save should belong to innermost class B, not outer class A")
        self.assertIs(_get(by_name["save"], "inside_class"), True)
        assert_all_invariants(sk, self)


class TestTrace9SkeletonCount(BaseTS):
    def test_skeleton_count_equals_func_and_method_events(self):
        """Trace 9 (21 steps): exactly 3 skeletons — one per Func/Method event."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        self.assertEqual(len(sk), 3,
            f"Expected 3 skeletons (getUser, helper, save), got {len(sk)}: {sk}")
        assert_all_invariants(sk, self)


class TestTrace10AllSixInvariants(BaseTS):
    def test_all_six_invariants_simultaneously(self):
        """Trace 10 (21 steps): DepthConsistency, AllFuncsRecorded, MethodsHaveClass,
        FuncsOutsideHaveNone, StackDepthNonNeg (proxy), CursorBounded (proxy) all hold."""
        skeletons = scan_file(self.ts_file())
        sk = list(skeletons)
        assert_all_invariants(sk, self)
        assert_all_funcs_recorded(sk, EXPECTED_FUNC_NAMES, self)
        _assert_final_state(sk, self)
        for s in sk:
            self.assertIn(_get(s, "inside_class"), (True, False))
        self.assertEqual(len(sk), 3)


# ---------------------------------------------------------------------------
# Dedicated invariant verifier tests (each exercises >= 2 source topologies)
# ---------------------------------------------------------------------------

class TestInvariantDepthConsistencyTwoTopologies(BaseTS):
    def test_depth_consistency_two_topologies(self):
        """DepthConsistency holds across two distinct source topologies."""
        f1 = self._write("t1.ts", "function standalone() {\n}\n")
        sk1 = list(scan_file(f1))
        self.assertEqual(len(sk1), 1, f"Expected 1 skeleton, got {len(sk1)}")
        self.assertTrue(
            _get(sk1[0], "class_name") is None or _get(sk1[0], "class_name") == "None")
        self.assertIs(_get(sk1[0], "inside_class"), False)
        assert_depth_consistency(sk1, self)

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_depth_consistency(sk2, self)


class TestInvariantMethodsHaveClassTwoTopologies(BaseTS):
    def test_methods_have_class_two_topologies(self):
        """MethodsHaveClass holds for simple and nested class topologies."""
        f1 = self._write("t1.ts", "class Y {\n  bar() {\n  }\n}\n")
        sk1 = list(scan_file(f1))
        assert_methods_have_class(sk1, self)
        self.assertEqual(_get(sk1[0], "class_name"), "Y")
        self.assertIs(_get(sk1[0], "inside_class"), True)

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_methods_have_class(sk2, self)


class TestInvariantFuncsOutsideHaveNoneTwoTopologies(BaseTS):
    def test_funcs_outside_have_none_two_topologies(self):
        """FuncsOutsideHaveNone holds for files with top-level standalone functions."""
        f1 = self._write("t1.ts", "function standalone() {\n}\n")
        sk1 = list(scan_file(f1))
        self.assertEqual(len(sk1), 1, f"Expected 1 skeleton, got {len(sk1)}")
        s = sk1[0]
        self.assertEqual(_get(s, "func_name"), "standalone")
        self.assertTrue(
            _get(s, "class_name") is None or _get(s, "class_name") == "None")
        self.assertIs(_get(s, "inside_class"), False)
        assert_funcs_outside_have_none(sk1, self)

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_funcs_outside_have_none(sk2, self)


class TestInvariantAllFuncsRecordedTwoTopologies(BaseTS):
    def test_all_funcs_recorded_two_topologies(self):
        """AllFuncsRecorded: every Func/Method event produces exactly one skeleton."""
        f1 = self._write("t1.ts", "class Z {\n  alpha() {\n  }\n  beta() {\n  }\n}\n")
        sk1 = list(scan_file(f1))
        assert_all_funcs_recorded(sk1, ["alpha", "beta"], self)

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_all_funcs_recorded(sk2, ["getUser", "helper", "save"], self)


class TestInvariantStackDepthNonNegTwoTopologies(BaseTS):
    def test_stack_depth_nonneg_two_topologies(self):
        """StackDepthNonNegative proxy: consistent skeletons imply depth stayed >= 0."""
        f1 = self._write("t1.ts", "class W {\n  run() {\n  }\n}\n")
        sk1 = list(scan_file(f1))
        assert_depth_consistency(sk1, self)
        self.assertEqual(len(sk1), 1)
        self.assertEqual(_get(sk1[0], "class_name"), "W")

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_depth_consistency(sk2, self)
        self.assertEqual(len(sk2), 3)


class TestInvariantCursorBoundedTwoTopologies(BaseTS):
    def test_cursor_bounded_two_topologies(self):
        """CursorBounded proxy: scan_file consumes all events and returns (no overrun)."""
        f1 = self._write("t1.ts", "function a() {\n}\nfunction b() {\n}\n")
        sk1 = list(scan_file(f1))
        assert_all_funcs_recorded(sk1, ["a", "b"], self)

        f2 = self._write("t2.ts", CANONICAL_TS_SOURCE)
        sk2 = list(scan_file(f2))
        assert_all_funcs_recorded(sk2, ["getUser", "helper", "save"], self)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(BaseTS):
    def test_empty_file(self):
        """Empty TS file: zero skeletons, all invariants trivially hold."""
        f = self._write("empty.ts", "")
        sk = list(scan_file(f))
        self.assertEqual(sk, [], f"Expected no skeletons for empty file, got {sk}")
        assert_all_invariants(sk, self)

    def test_class_with_no_methods(self):
        """Class body with no methods: zero skeletons emitted."""
        f = self._write("nomethod.ts", "class Empty {\n}\n")
        sk = list(scan_file(f))
        self.assertEqual(sk, [], f"Expected no skeletons for method-less class, got {sk}")
        assert_all_invariants(sk, self)

    def test_function_outside_any_class(self):
        """Top-level function: class_name=None, inside_class=False."""
        f = self._write("toplevel.ts", "function topLevel() {\n}\n")
        sk = list(scan_file(f))
        self.assertEqual(len(sk), 1, f"Expected 1 skeleton, got {len(sk)}")
        s = sk[0]
        self.assertEqual(_get(s, "func_name"), "topLevel")
        self.assertTrue(
            _get(s, "class_name") is None or _get(s, "class_name") == "None")
        self.assertIs(_get(s, "inside_class"), False)
        assert_all_invariants(sk, self)

    def test_deeply_nested_classes_innermost_wins(self):
        """Methods in nested classes receive the innermost enclosing class_name."""
        src = (
            "class Outer {\n"
            "  outerMethod() {\n"
            "    class Inner {\n"
            "      innerMethod() {\n"
        )
        f = self._write("nested.ts", src)
        sk = list(scan_file(f))
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertIn("outerMethod", by_name, "outerMethod skeleton missing")
        self.assertIn("innerMethod", by_name, "innerMethod skeleton missing")
        self.assertEqual(_get(by_name["outerMethod"], "class_name"), "Outer")
        self.assertIs(_get(by_name["outerMethod"], "inside_class"), True)
        self.assertEqual(_get(by_name["innerMethod"], "class_name"), "Inner")
        self.assertIs(_get(by_name["innerMethod"], "inside_class"), True)
        assert_all_invariants(sk, self)

    def test_mixed_funcs_and_methods(self):
        """Mix of top-level functions and class methods: each gets correct class_name."""
        src = (
            "function globalFn() {\n"
            "}\n"
            "class MyClass {\n"
            "  classMethod() {\n"
            "  }\n"
            "}\n"
            "function anotherGlobal() {\n"
            "}\n"
        )
        f = self._write("mixed.ts", src)
        sk = list(scan_file(f))
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertEqual(set(by_name), {"globalFn", "classMethod", "anotherGlobal"})

        self.assertTrue(
            _get(by_name["globalFn"], "class_name") is None or
            _get(by_name["globalFn"], "class_name") == "None")
        self.assertIs(_get(by_name["globalFn"], "inside_class"), False)

        self.assertEqual(_get(by_name["classMethod"], "class_name"), "MyClass")
        self.assertIs(_get(by_name["classMethod"], "inside_class"), True)

        self.assertTrue(
            _get(by_name["anotherGlobal"], "class_name") is None or
            _get(by_name["anotherGlobal"], "class_name") == "None")
        self.assertIs(_get(by_name["anotherGlobal"], "inside_class"), False)

        assert_all_invariants(sk, self)

    def test_class_stack_pops_after_full_class_close(self):
        """After a class body is fully closed, subsequent functions have class_name=None."""
        src = (
            "class A {\n"
            "  methodInA() {\n"
            "  }\n"
            "}\n"
            "function afterA() {\n"
            "}\n"
        )
        f = self._write("pop.ts", src)
        sk = list(scan_file(f))
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertEqual(set(by_name), {"methodInA", "afterA"})

        self.assertEqual(_get(by_name["methodInA"], "class_name"), "A")
        self.assertIs(_get(by_name["methodInA"], "inside_class"), True)

        self.assertTrue(
            _get(by_name["afterA"], "class_name") is None or
            _get(by_name["afterA"], "class_name") == "None")
        self.assertIs(_get(by_name["afterA"], "inside_class"), False)

        assert_all_invariants(sk, self)

    def test_close_brace_does_not_pop_outer_class_prematurely(self):
        """CloseBrace only pops a class when brace_depth falls to its push-depth."""
        src = (
            "class A {\n"
            "  getUser() {\n"
            "  }\n"
            "  helper() {\n"
        )
        f = self._write("nodepopearly.ts", src)
        sk = list(scan_file(f))
        by_name = {_get(s, "func_name"): s for s in sk}
        self.assertIn("getUser", by_name)
        self.assertIn("helper", by_name)
        self.assertEqual(_get(by_name["getUser"], "class_name"), "A")
        self.assertEqual(_get(by_name["helper"], "class_name"), "A",
            "helper must still belong to A: the CloseBrace after getUser() reduced "
            "brace_depth to 1, which is > A.push_depth=0, so A must remain on the stack")
        assert_all_invariants(sk, self)


if __name__ == "__main__":
    unittest.main()