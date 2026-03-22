import unittest
from pathlib import Path
import tempfile
import os

from scanner_go_line_ranges import scan_file

# ---------------------------------------------------------------------------
# Canonical source fixture
# ---------------------------------------------------------------------------
GO_SOURCE = (
    "func Alpha() {}\n"
    "// other line\n"
    "type MyInterface interface {\n"
    "func InsideIface()\n"
    "}\n"
    "func Beta() {}\n"
    "// trailing comment\n"
)

N = 7


def _write_go_file(tmp_dir: str, name: str, content: str) -> str:
    path = os.path.join(tmp_dir, name)
    with open(path, "w") as f:
        f.write(content)
    return path


def _interface_body_line_numbers(source_lines: list) -> set:
    inside = False
    result = set()
    for idx, raw in enumerate(source_lines, start=1):
        stripped = raw.strip()
        if "interface {" in stripped:
            inside = True
            continue
        if inside and stripped == "}":
            inside = False
            continue
        if inside:
            result.add(idx)
    return result


def _verify_line_number_correct(skeletons, source_lines):
    total = len(source_lines)
    for s in skeletons:
        assert 1 <= s.line_number <= total, (
            f"line_number {s.line_number} out of valid range [1, {total}]"
        )
        assert source_lines[s.line_number - 1].lstrip().startswith("func"), (
            f"line {s.line_number} is not a 'func' line: "
            f"{source_lines[s.line_number - 1]!r}"
        )


def _verify_interface_exclusion(skeletons, source_lines):
    iface_lines = _interface_body_line_numbers(source_lines)
    for s in skeletons:
        assert s.line_number not in iface_lines, (
            f"skeleton at line {s.line_number} is inside an interface block"
        )


def _verify_no_gaps(skeletons, source_lines):
    iface_lines = _interface_body_line_numbers(source_lines)
    expected = {
        idx
        for idx, raw in enumerate(source_lines, start=1)
        if raw.lstrip().startswith("func") and idx not in iface_lines
    }
    actual = {s.line_number for s in skeletons}
    assert expected == actual, (
        f"NoGaps violated – expected skeletons at {expected}, got {actual}"
    )


def _verify_cursor_bounded(skeletons, n):
    for s in skeletons:
        assert s.line_number <= n, (
            f"line_number {s.line_number} exceeds N = {n}"
        )


def _all_invariants(skeletons, source_lines):
    _verify_line_number_correct(skeletons, source_lines)
    _verify_interface_exclusion(skeletons, source_lines)
    _verify_no_gaps(skeletons, source_lines)
    _verify_cursor_bounded(skeletons, len(source_lines))


class TestTrace1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_scan_produces_correct_line_numbers(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertEqual(line_nums, {1, 6})
        self.assertEqual(len(skeletons), 2)
        _all_invariants(skeletons, self.source_lines)


class TestTrace2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_line_number_correct(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertEqual(line_nums, {1, 6})
        _verify_line_number_correct(skeletons, self.source_lines)
        _verify_cursor_bounded(skeletons, N)


class TestTrace3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_interface_exclusion(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertNotIn(4, line_nums,
            "Line 4 is inside the interface block and must not produce a skeleton")
        self.assertEqual(line_nums, {1, 6})
        _verify_interface_exclusion(skeletons, self.source_lines)
        _verify_no_gaps(skeletons, self.source_lines)


class TestTrace4(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_no_gaps(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertEqual(line_nums, {1, 6})
        _verify_no_gaps(skeletons, self.source_lines)
        _verify_line_number_correct(skeletons, self.source_lines)


class TestTrace5(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_cursor_bounded(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertEqual(line_nums, {1, 6})
        _verify_cursor_bounded(skeletons, N)
        _verify_line_number_correct(skeletons, self.source_lines)


class TestTrace6(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_skeleton_count_equals_two(self):
        skeletons = scan_file(self.go_file)
        self.assertEqual(len(skeletons), 2, f"Expected 2 skeletons, got {len(skeletons)}")
        line_nums = {s.line_number for s in skeletons}
        self.assertEqual(line_nums, {1, 6})
        _all_invariants(skeletons, self.source_lines)


class TestTrace7(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_first_skeleton_at_line_1(self):
        skeletons = scan_file(self.go_file)
        sorted_nums = sorted(s.line_number for s in skeletons)
        self.assertEqual(sorted_nums[0], 1,
            f"Expected first skeleton at line 1, got {sorted_nums[0]}")
        _all_invariants(skeletons, self.source_lines)


class TestTrace8(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_second_skeleton_at_line_6(self):
        skeletons = scan_file(self.go_file)
        sorted_nums = sorted(s.line_number for s in skeletons)
        self.assertEqual(sorted_nums[-1], 6,
            f"Expected last skeleton at line 6, got {sorted_nums[-1]}")
        _all_invariants(skeletons, self.source_lines)


class TestTrace9(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_other_lines_produce_no_skeleton(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertNotIn(2, line_nums, "Line 2 (Other) must not produce a skeleton")
        self.assertNotIn(7, line_nums, "Line 7 (Other) must not produce a skeleton")
        self.assertEqual(line_nums, {1, 6})
        _all_invariants(skeletons, self.source_lines)


class TestTrace10(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        self.source_lines = GO_SOURCE.splitlines(keepends=True)

    def test_interface_markers_produce_no_skeleton(self):
        skeletons = scan_file(self.go_file)
        line_nums = {s.line_number for s in skeletons}
        self.assertNotIn(3, line_nums, "Line 3 (InterfaceOpen) must not produce a skeleton")
        self.assertNotIn(5, line_nums, "Line 5 (InterfaceClose) must not produce a skeleton")
        self.assertEqual(line_nums, {1, 6})
        _all_invariants(skeletons, self.source_lines)


class TestLineNumberCorrectInvariant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_topology_canonical_7_lines(self):
        go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        source_lines = GO_SOURCE.splitlines(keepends=True)
        skeletons = scan_file(go_file)
        _verify_line_number_correct(skeletons, source_lines)

    def test_topology_single_func_line_1(self):
        src = "func Solo() {}\n"
        p = _write_go_file(self.tmp, "solo.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_line_number_correct(skeletons, source_lines)
        self.assertEqual({s.line_number for s in skeletons}, {1})

    def test_topology_funcs_at_lines_3_and_5(self):
        src = (
            "package main\n"
            "// comment\n"
            "func A() {}\n"
            "// comment\n"
            "func B() {}\n"
        )
        p = _write_go_file(self.tmp, "multi.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_line_number_correct(skeletons, source_lines)
        self.assertEqual({s.line_number for s in skeletons}, {3, 5})


class TestInterfaceExclusionInvariant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_topology_canonical_7_lines(self):
        go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        source_lines = GO_SOURCE.splitlines(keepends=True)
        skeletons = scan_file(go_file)
        _verify_interface_exclusion(skeletons, source_lines)

    def test_topology_interface_only_file(self):
        src = (
            "type Iface interface {\n"
            "func Method()\n"
            "}\n"
        )
        p = _write_go_file(self.tmp, "iface_only.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_interface_exclusion(skeletons, source_lines)
        self.assertEqual(len(skeletons), 0,
            "No skeletons expected when every func is inside an interface")

    def test_topology_func_before_and_after_interface(self):
        src = (
            "func Before() {}\n"
            "type Iface interface {\n"
            "func Inside()\n"
            "}\n"
            "func After() {}\n"
        )
        p = _write_go_file(self.tmp, "before_after.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_interface_exclusion(skeletons, source_lines)
        self.assertEqual({s.line_number for s in skeletons}, {1, 5})


class TestNoGapsInvariant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_topology_canonical_7_lines(self):
        go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        source_lines = GO_SOURCE.splitlines(keepends=True)
        skeletons = scan_file(go_file)
        _verify_no_gaps(skeletons, source_lines)

    def test_topology_three_consecutive_funcs(self):
        src = (
            "func A() {}\n"
            "func B() {}\n"
            "func C() {}\n"
        )
        p = _write_go_file(self.tmp, "three_funcs.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_no_gaps(skeletons, source_lines)
        self.assertEqual({s.line_number for s in skeletons}, {1, 2, 3})

    def test_topology_no_func_declarations(self):
        src = (
            "package main\n"
            "// just comments\n"
        )
        p = _write_go_file(self.tmp, "no_funcs.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        _verify_no_gaps(skeletons, source_lines)
        self.assertEqual(len(skeletons), 0)


class TestCursorBoundedInvariant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_topology_canonical_7_lines(self):
        go_file = _write_go_file(self.tmp, "subject.go", GO_SOURCE)
        skeletons = scan_file(go_file)
        _verify_cursor_bounded(skeletons, N)
        self.assertTrue(all(s.line_number <= N for s in skeletons))

    def test_topology_single_line_file(self):
        src = "func F() {}\n"
        p = _write_go_file(self.tmp, "single.go", src)
        skeletons = scan_file(p)
        _verify_cursor_bounded(skeletons, 1)
        self.assertEqual({s.line_number for s in skeletons}, {1})

    def test_topology_five_line_file(self):
        src = (
            "func A() {}\n"
            "// c\n"
            "func B() {}\n"
            "// c\n"
            "func C() {}\n"
        )
        p = _write_go_file(self.tmp, "five.go", src)
        skeletons = scan_file(p)
        _verify_cursor_bounded(skeletons, 5)
        self.assertEqual({s.line_number for s in skeletons}, {1, 3, 5})


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_edge_empty_file(self):
        p = _write_go_file(self.tmp, "empty.go", "")
        source_lines = []
        skeletons = scan_file(p)
        self.assertEqual(len(skeletons), 0)
        _all_invariants(skeletons, source_lines)

    def test_edge_file_with_only_comments(self):
        src = "// package doc\n// another comment\n"
        p = _write_go_file(self.tmp, "comments_only.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual(len(skeletons), 0)
        _verify_no_gaps(skeletons, source_lines)

    def test_edge_single_func_declaration(self):
        src = "func Single() {}\n"
        p = _write_go_file(self.tmp, "single_func.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual({s.line_number for s in skeletons}, {1})
        _all_invariants(skeletons, source_lines)

    def test_edge_adjacent_func_declarations(self):
        src = "func A() {}\nfunc B() {}\n"
        p = _write_go_file(self.tmp, "adjacent.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual({s.line_number for s in skeletons}, {1, 2})
        _all_invariants(skeletons, source_lines)

    def test_edge_interface_at_start_of_file(self):
        src = (
            "type StartIface interface {\n"
            "func Method()\n"
            "}\n"
            "func RealFunc() {}\n"
        )
        p = _write_go_file(self.tmp, "iface_start.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual({s.line_number for s in skeletons}, {4})
        _all_invariants(skeletons, source_lines)

    def test_edge_interface_at_end_of_file(self):
        src = (
            "func First() {}\n"
            "type EndIface interface {\n"
            "func Method()\n"
            "}\n"
        )
        p = _write_go_file(self.tmp, "iface_end.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual({s.line_number for s in skeletons}, {1})
        _all_invariants(skeletons, source_lines)

    def test_edge_two_interface_blocks_with_func_between(self):
        src = (
            "type I1 interface {\n"
            "func M1()\n"
            "}\n"
            "func Between() {}\n"
            "type I2 interface {\n"
            "func M2()\n"
            "}\n"
        )
        p = _write_go_file(self.tmp, "two_ifaces.go", src)
        source_lines = src.splitlines(keepends=True)
        skeletons = scan_file(p)
        self.assertEqual({s.line_number for s in skeletons}, {4})
        _all_invariants(skeletons, source_lines)

    def test_edge_no_skeleton_duplicated_for_same_line(self):
        src = "func OnlyOnce() {}\n"
        p = _write_go_file(self.tmp, "once.go", src)
        skeletons = scan_file(p)
        line_nums = [s.line_number for s in skeletons]
        self.assertEqual(len(line_nums), len(set(line_nums)),
            "Duplicate skeleton entries detected for the same line_number")
        self.assertEqual(set(line_nums), {1})


if __name__ == "__main__":
    unittest.main()