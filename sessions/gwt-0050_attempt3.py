import pytest
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


@pytest.fixture
def tmp_dir():
    return tempfile.mkdtemp()


@pytest.fixture
def canonical_go_file(tmp_dir):
    return _write_go_file(tmp_dir, "subject.go", GO_SOURCE)


@pytest.fixture
def canonical_source_lines():
    return GO_SOURCE.splitlines(keepends=True)


# ---------------------------------------------------------------------------
# Trace tests
# ---------------------------------------------------------------------------

def test_trace1_scan_produces_correct_line_numbers(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert line_nums == {1, 6}
    assert len(skeletons) == 2
    _all_invariants(skeletons, canonical_source_lines)


def test_trace2_line_number_correct(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert line_nums == {1, 6}
    _verify_line_number_correct(skeletons, canonical_source_lines)
    _verify_cursor_bounded(skeletons, N)


def test_trace3_interface_exclusion(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert 4 not in line_nums, "Line 4 is inside the interface block and must not produce a skeleton"
    assert line_nums == {1, 6}
    _verify_interface_exclusion(skeletons, canonical_source_lines)
    _verify_no_gaps(skeletons, canonical_source_lines)


def test_trace4_no_gaps(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert line_nums == {1, 6}
    _verify_no_gaps(skeletons, canonical_source_lines)
    _verify_line_number_correct(skeletons, canonical_source_lines)


def test_trace5_cursor_bounded(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert line_nums == {1, 6}
    _verify_cursor_bounded(skeletons, N)
    _verify_line_number_correct(skeletons, canonical_source_lines)


def test_trace6_skeleton_count_equals_two(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    assert len(skeletons) == 2, f"Expected 2 skeletons, got {len(skeletons)}"
    line_nums = {s.line_number for s in skeletons}
    assert line_nums == {1, 6}
    _all_invariants(skeletons, canonical_source_lines)


def test_trace7_first_skeleton_at_line_1(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    sorted_nums = sorted(s.line_number for s in skeletons)
    assert sorted_nums[0] == 1, f"Expected first skeleton at line 1, got {sorted_nums[0]}"
    _all_invariants(skeletons, canonical_source_lines)


def test_trace8_second_skeleton_at_line_6(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    sorted_nums = sorted(s.line_number for s in skeletons)
    assert sorted_nums[-1] == 6, f"Expected last skeleton at line 6, got {sorted_nums[-1]}"
    _all_invariants(skeletons, canonical_source_lines)


def test_trace9_other_lines_produce_no_skeleton(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert 2 not in line_nums, "Line 2 (Other) must not produce a skeleton"
    assert 7 not in line_nums, "Line 7 (Other) must not produce a skeleton"
    assert line_nums == {1, 6}
    _all_invariants(skeletons, canonical_source_lines)


def test_trace10_interface_markers_produce_no_skeleton(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    line_nums = {s.line_number for s in skeletons}
    assert 3 not in line_nums, "Line 3 (InterfaceOpen) must not produce a skeleton"
    assert 5 not in line_nums, "Line 5 (InterfaceClose) must not produce a skeleton"
    assert line_nums == {1, 6}
    _all_invariants(skeletons, canonical_source_lines)


# ---------------------------------------------------------------------------
# LineNumberCorrect invariant tests
# ---------------------------------------------------------------------------

def test_line_number_correct_canonical_7_lines(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    _verify_line_number_correct(skeletons, canonical_source_lines)


def test_line_number_correct_single_func_line_1(tmp_dir):
    src = "func Solo() {}\n"
    p = _write_go_file(tmp_dir, "solo.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_line_number_correct(skeletons, source_lines)
    assert {s.line_number for s in skeletons} == {1}


def test_line_number_correct_funcs_at_lines_3_and_5(tmp_dir):
    src = (
        "package main\n"
        "// comment\n"
        "func A() {}\n"
        "// comment\n"
        "func B() {}\n"
    )
    p = _write_go_file(tmp_dir, "multi.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_line_number_correct(skeletons, source_lines)
    assert {s.line_number for s in skeletons} == {3, 5}


# ---------------------------------------------------------------------------
# InterfaceExclusion invariant tests
# ---------------------------------------------------------------------------

def test_interface_exclusion_canonical_7_lines(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    _verify_interface_exclusion(skeletons, canonical_source_lines)


def test_interface_exclusion_interface_only_file(tmp_dir):
    src = (
        "type Iface interface {\n"
        "func Method()\n"
        "}\n"
    )
    p = _write_go_file(tmp_dir, "iface_only.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_interface_exclusion(skeletons, source_lines)
    assert len(skeletons) == 0, "No skeletons expected when every func is inside an interface"


def test_interface_exclusion_func_before_and_after_interface(tmp_dir):
    src = (
        "func Before() {}\n"
        "type Iface interface {\n"
        "func Inside()\n"
        "}\n"
        "func After() {}\n"
    )
    p = _write_go_file(tmp_dir, "before_after.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_interface_exclusion(skeletons, source_lines)
    assert {s.line_number for s in skeletons} == {1, 5}


# ---------------------------------------------------------------------------
# NoGaps invariant tests
# ---------------------------------------------------------------------------

def test_no_gaps_canonical_7_lines(canonical_go_file, canonical_source_lines):
    skeletons = scan_file(canonical_go_file)
    _verify_no_gaps(skeletons, canonical_source_lines)


def test_no_gaps_three_consecutive_funcs(tmp_dir):
    src = (
        "func A() {}\n"
        "func B() {}\n"
        "func C() {}\n"
    )
    p = _write_go_file(tmp_dir, "three_funcs.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_no_gaps(skeletons, source_lines)
    assert {s.line_number for s in skeletons} == {1, 2, 3}


def test_no_gaps_no_func_declarations(tmp_dir):
    src = (
        "package main\n"
        "// just comments\n"
    )
    p = _write_go_file(tmp_dir, "no_funcs.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    _verify_no_gaps(skeletons, source_lines)
    assert len(skeletons) == 0


# ---------------------------------------------------------------------------
# CursorBounded invariant tests
# ---------------------------------------------------------------------------

def test_cursor_bounded_canonical_7_lines(canonical_go_file):
    skeletons = scan_file(canonical_go_file)
    _verify_cursor_bounded(skeletons, N)
    assert all(s.line_number <= N for s in skeletons)


def test_cursor_bounded_single_line_file(tmp_dir):
    src = "func F() {}\n"
    p = _write_go_file(tmp_dir, "single.go", src)
    skeletons = scan_file(p)
    _verify_cursor_bounded(skeletons, 1)
    assert {s.line_number for s in skeletons} == {1}


def test_cursor_bounded_five_line_file(tmp_dir):
    src = (
        "func A() {}\n"
        "// c\n"
        "func B() {}\n"
        "// c\n"
        "func C() {}\n"
    )
    p = _write_go_file(tmp_dir, "five.go", src)
    skeletons = scan_file(p)
    _verify_cursor_bounded(skeletons, 5)
    assert {s.line_number for s in skeletons} == {1, 3, 5}


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

def test_edge_empty_file(tmp_dir):
    p = _write_go_file(tmp_dir, "empty.go", "")
    source_lines = []
    skeletons = scan_file(p)
    assert len(skeletons) == 0
    _all_invariants(skeletons, source_lines)


def test_edge_file_with_only_comments(tmp_dir):
    src = "// package doc\n// another comment\n"
    p = _write_go_file(tmp_dir, "comments_only.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert len(skeletons) == 0
    _verify_no_gaps(skeletons, source_lines)


def test_edge_single_func_declaration(tmp_dir):
    src = "func Single() {}\n"
    p = _write_go_file(tmp_dir, "single_func.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert {s.line_number for s in skeletons} == {1}
    _all_invariants(skeletons, source_lines)


def test_edge_adjacent_func_declarations(tmp_dir):
    src = "func A() {}\nfunc B() {}\n"
    p = _write_go_file(tmp_dir, "adjacent.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert {s.line_number for s in skeletons} == {1, 2}
    _all_invariants(skeletons, source_lines)


def test_edge_interface_at_start_of_file(tmp_dir):
    src = (
        "type StartIface interface {\n"
        "func Method()\n"
        "}\n"
        "func RealFunc() {}\n"
    )
    p = _write_go_file(tmp_dir, "iface_start.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert {s.line_number for s in skeletons} == {4}
    _all_invariants(skeletons, source_lines)


def test_edge_interface_at_end_of_file(tmp_dir):
    src = (
        "func First() {}\n"
        "type EndIface interface {\n"
        "func Method()\n"
        "}\n"
    )
    p = _write_go_file(tmp_dir, "iface_end.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert {s.line_number for s in skeletons} == {1}
    _all_invariants(skeletons, source_lines)


def test_edge_two_interface_blocks_with_func_between(tmp_dir):
    src = (
        "type I1 interface {\n"
        "func M1()\n"
        "}\n"
        "func Between() {}\n"
        "type I2 interface {\n"
        "func M2()\n"
        "}\n"
    )
    p = _write_go_file(tmp_dir, "two_ifaces.go", src)
    source_lines = src.splitlines(keepends=True)
    skeletons = scan_file(p)
    assert {s.line_number for s in skeletons} == {4}
    _all_invariants(skeletons, source_lines)


def test_edge_no_skeleton_duplicated_for_same_line(tmp_dir):
    src = "func OnlyOnce() {}\n"
    p = _write_go_file(tmp_dir, "once.go", src)
    skeletons = scan_file(p)
    line_nums = [s.line_number for s in skeletons]
    assert len(line_nums) == len(set(line_nums)), \
        "Duplicate skeleton entries detected for the same line_number"
    assert set(line_nums) == {1}