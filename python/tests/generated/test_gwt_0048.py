import pytest
from pathlib import Path
from registry.scanner_typescript import scan_file as _scan_file

def scan_file(path):
    return _scan_file(Path(path) if isinstance(path, str) else path)
from registry.crawl_types import Skeleton


FIXTURE_LINES = [
    "function alpha() {",
    "  return 1;",
    "class MyClass {",
    "  method() {",
    "  arrow = () => {",
    "  }",
    "function beta() {",
]

EXPECTED_LINE_NUMBERS = {1, 4, 5, 7}


def write_fixture(tmp_path, lines):
    f = tmp_path / "test_fixture.ts"
    f.write_text("\n".join(lines) + "\n")
    return str(f)


def write_named_fixture(tmp_path, name, lines):
    f = tmp_path / name
    f.write_text("\n".join(lines) + "\n")
    return str(f)


class TestTrace01_FinalState:
    """Verifies the final state of scan_file matches the expected skeleton set."""

    def test_final_state_line_numbers(self, tmp_path):
        """TLA+ final state: skeletons == {s | Lines[s.line_num] in {Func,Arrow,Method}}."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert isinstance(result, list)
        found = {s.line_number for s in result}
        assert found == EXPECTED_LINE_NUMBERS

    def test_result_count(self, tmp_path):
        """Final state contains exactly 4 skeletons for the standard fixture."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert len(result) == 4


class TestTrace02_OneIndexed:
    """Verifies TLA+ invariant OneIndexed: ∀ s ∈ skeletons : s.line_num >= 1."""

    def test_one_indexed_standard_fixture(self, tmp_path):
        """OneIndexed holds on the standard 7-line fixture."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        for s in result:
            assert s.line_number >= 1

    def test_one_indexed_single_func(self, tmp_path):
        """OneIndexed holds when only one Func line exists."""
        lines = ["function solo() {", "  return 0;", "}"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        for s in result:
            assert s.line_number >= 1


class TestTrace03_LineNumberCorrect:
    """Verifies TLA+ invariant LineNumberCorrect: 1 <= s.line_num <= N and Lines[s.line_num] in {Func,Arrow,Method}."""

    def test_only_func_arrow_method_captured(self, tmp_path):
        """Other and ClassOpen lines (2, 3, 6) must not appear in results."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 2 not in found
        assert 3 not in found
        assert 6 not in found

    def test_line_number_within_bounds(self, tmp_path):
        """LineNumberCorrect: every s.line_number satisfies 1 <= s.line_number <= N."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        n = len(FIXTURE_LINES)
        for s in result:
            assert 1 <= s.line_number <= n

    def test_classopen_not_captured(self, tmp_path):
        """ClassOpen (line 3) is excluded by the scanner — not a Func/Arrow/Method."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 3 not in found


class TestTrace04_NoGaps:
    """Verifies TLA+ invariant NoGaps: every Func/Arrow/Method line has a matching skeleton."""

    def test_no_gaps_standard_fixture(self, tmp_path):
        """NoGaps: all expected line numbers are present in results."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        for ln in EXPECTED_LINE_NUMBERS:
            assert ln in found

    def test_no_duplicate_line_numbers(self, tmp_path):
        """NoGaps set semantics: no two skeletons share the same line number."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        line_numbers = [s.line_number for s in result]
        assert len(line_numbers) == len(set(line_numbers))

    def test_no_gaps_two_adjacent_funcs(self, tmp_path):
        """NoGaps: cursor must not skip when two Func lines are adjacent."""
        lines = ["function first() {", "function second() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 in found
        assert 2 in found


class TestTrace05_CursorBounded:
    """Verifies TLA+ invariant CursorBounded: i <= N+1 (observable as termination + line_number <= N)."""

    def test_scan_terminates(self, tmp_path):
        """CursorBounded: scan_file returns (cursor reached N+1) on standard fixture."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert result is not None

    def test_no_out_of_range_line_numbers(self, tmp_path):
        """CursorBounded observable proxy: no skeleton has line_number > N."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        n = len(FIXTURE_LINES)
        for s in result:
            assert s.line_number <= n

    def test_scan_terminates_on_large_file(self, tmp_path):
        """CursorBounded stress: 50-line all-Func file terminates with valid line numbers."""
        lines = ["function f{}() {{".format(i) for i in range(50)]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        assert result is not None
        for s in result:
            assert 1 <= s.line_number <= 50


class TestTrace06_FuncLines:
    """Verifies that Func-typed lines are captured at the correct positions."""

    def test_func_line1_captured(self, tmp_path):
        """Func at line 1 (alpha) is captured."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 in found

    def test_func_line7_captured(self, tmp_path):
        """Func at line 7 (beta) is captured."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 7 in found

    def test_func_at_last_line_captured(self, tmp_path):
        """Func at last line (line 3) is not missed — CursorBounded corner case."""
        lines = ["  // comment", "  let x = 1;", "function lastLine() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 3 in found


class TestTrace07_ArrowMethod:
    """Verifies that Arrow and Method lines are captured at the correct positions."""

    def test_method_line4_captured(self, tmp_path):
        """Method at line 4 (method()) is captured."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 4 in found

    def test_arrow_line5_captured(self, tmp_path):
        """Arrow at line 5 (arrow = () => {) is captured."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 5 in found

    def test_arrow_and_method_both_present(self, tmp_path):
        """Both Arrow (5) and Method (4) are present — NoGaps for inner class body."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert {4, 5}.issubset(found)


class TestTrace08_OtherLinesExcluded:
    """Verifies that Other and ClassOpen lines produce no skeleton entries."""

    def test_other_lines_excluded(self, tmp_path):
        """LineNumberCorrect: Other lines {2, 3, 6} are disjoint from results."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        other_lines = {2, 3, 6}
        assert found.isdisjoint(other_lines)

    def test_no_extra_skeletons(self, tmp_path):
        """LineNumberCorrect: result set is a subset of EXPECTED_LINE_NUMBERS."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        unexpected = found - EXPECTED_LINE_NUMBERS
        assert not unexpected


class TestTrace09_SkeletonAttributes:
    """Verifies the Skeleton datatype contract: line_number attribute exists and is int."""

    def test_skeleton_has_line_number_attribute(self, tmp_path):
        """Every Skeleton instance exposes a line_number attribute."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert len(result) > 0
        for s in result:
            assert hasattr(s, "line_number")

    def test_line_number_is_int(self, tmp_path):
        """Skeleton.line_number is a Python int (maps to TLA+ integer line index)."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        for s in result:
            assert isinstance(s.line_number, int)

    def test_skeleton_instances(self, tmp_path):
        """scan_file returns Skeleton instances, not plain dicts or tuples."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        for s in result:
            assert isinstance(s, Skeleton)


class TestTrace10_CompleteInvariantCheck:
    """Combined invariant check: OneIndexed ∧ LineNumberCorrect ∧ NoGaps ∧ set semantics."""

    def test_all_invariants(self, tmp_path):
        """All four TLA+ invariants hold simultaneously on the standard fixture."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        n = len(FIXTURE_LINES)
        for s in result:
            assert s.line_number >= 1                          # OneIndexed
        for s in result:
            assert 1 <= s.line_number <= n                     # LineNumberCorrect
        found = {s.line_number for s in result}
        assert found == EXPECTED_LINE_NUMBERS                  # NoGaps
        line_numbers = [s.line_number for s in result]
        assert len(line_numbers) == len(set(line_numbers))     # set semantics
        assert 3 not in found                                  # ClassOpen excluded


class TestInvariantOneIndexed:
    """Three structural topologies verifying OneIndexed: ∀ s ∈ skeletons : s.line_num >= 1."""

    def test_topology_standard(self, tmp_path):
        """OneIndexed on standard mixed fixture (Func/Other/ClassOpen/Method/Arrow)."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        for s in result:
            assert s.line_number >= 1

    def test_topology_only_methods(self, tmp_path):
        """OneIndexed on method-only class topology."""
        lines = ["class A {", "  foo() {", "  bar() {", "}"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        for s in result:
            assert s.line_number >= 1

    def test_topology_mixed_arrows_funcs(self, tmp_path):
        """OneIndexed on mixed Arrow/Func topology without class wrapper."""
        lines = ["const a = () => {", "function b() {", "const c = () => {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        for s in result:
            assert s.line_number >= 1


class TestInvariantLineNumberCorrect:
    """Three structural topologies verifying LineNumberCorrect: 1 <= s.line_num <= N."""

    def test_topology_standard_bounds(self, tmp_path):
        """LineNumberCorrect on standard fixture: all line numbers in [1, 7]."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        n = len(FIXTURE_LINES)
        for s in result:
            assert 1 <= s.line_number <= n

    def test_topology_func_only(self, tmp_path):
        """LineNumberCorrect on Func-only topology: both functions captured within bounds."""
        lines = ["function x() {", "  return 42;", "}", "function y() {", "  return 99;", "}"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        n = len(lines)
        for s in result:
            assert 1 <= s.line_number <= n
        found = {s.line_number for s in result}
        assert 1 in found
        assert 4 in found

    def test_topology_no_other_lines_captured(self, tmp_path):
        """LineNumberCorrect on comment-prefixed topology: lines 1–2 are Other, only line 3 captured."""
        lines = ["// just a comment", "const x = 5;", "function z() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 not in found
        assert 2 not in found
        assert 3 in found


class TestInvariantNoGaps:
    """Three structural topologies verifying NoGaps: every Func/Arrow/Method line has a matching skeleton."""

    def test_topology_standard_no_gaps(self, tmp_path):
        """NoGaps on standard fixture: EXPECTED_LINE_NUMBERS ⊆ found."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert EXPECTED_LINE_NUMBERS.issubset(found)

    def test_topology_adjacent_declarations_no_gaps(self, tmp_path):
        """NoGaps on adjacent-declarations topology: cursor must not skip any consecutive Func."""
        lines = ["function a() {", "function b() {", "function c() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert {1, 2, 3}.issubset(found)

    def test_topology_sparse_declarations_no_gaps(self, tmp_path):
        """NoGaps on sparse topology: Func at lines 1 and 5, three Other lines between."""
        lines = [
            "function start() {",
            "  const x = 1;",
            "  const y = 2;",
            "  const z = 3;",
            "function end() {",
        ]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 in found
        assert 5 in found
        assert len(found) == 2


class TestInvariantCursorBounded:
    """Three structural topologies verifying CursorBounded: i <= N+1 (via termination + line_number <= N)."""

    def test_topology_standard_terminates(self, tmp_path):
        """CursorBounded on standard fixture: terminates and all line numbers <= N."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert result is not None
        n = len(FIXTURE_LINES)
        for s in result:
            assert s.line_number <= n

    def test_topology_single_line_file_terminates(self, tmp_path):
        """CursorBounded on single-line file: cursor goes from 1 to 2 (= N+1) and stops."""
        lines = ["function only() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        assert result is not None
        for s in result:
            assert s.line_number <= 1

    def test_topology_empty_file_terminates(self, tmp_path):
        """CursorBounded on empty file: N=0, i starts at 1 > N, immediate termination."""
        path = write_named_fixture(tmp_path, "empty.ts", [])
        result = scan_file(path)
        assert result is not None
        assert result == []


class TestEdgeCases:
    """Edge case coverage: empty, single, last-line, adjacent, no-declarations, nonexistent, all-Func/Arrow, methods."""

    def test_empty_file(self, tmp_path):
        """Empty file yields empty skeleton list."""
        path = write_named_fixture(tmp_path, "empty.ts", [])
        result = scan_file(path)
        assert result == []

    def test_single_function(self, tmp_path):
        """Single Func line produces exactly skeleton at line 1."""
        lines = ["function solo() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert found == {1}

    def test_function_at_last_line(self, tmp_path):
        """Func at last line (line 3) is captured; Other lines 1–2 are excluded."""
        lines = ["  // preamble", "  const x = 0;", "function atEnd() {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 3 in found
        assert 1 not in found
        assert 2 not in found

    def test_adjacent_declarations(self, tmp_path):
        """Three adjacent declarations (Func/Func/Arrow) all captured without gaps."""
        lines = ["function a() {", "function b() {", "const c = () => {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert found == {1, 2, 3}

    def test_classopen_not_captured(self, tmp_path):
        """ClassOpen (class Foo {) is excluded; Method inside class is captured."""
        lines = ["class Foo {", "  bar() {", "}"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 not in found
        assert 2 in found

    def test_no_declaration_file(self, tmp_path):
        """File with only const/let/comment lines yields empty skeleton list."""
        lines = ["  const x = 1;", "  // comment", "  let y = 2;"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        assert result == []

    def test_nonexistent_file_raises(self, tmp_path):
        """scan_file raises an exception for a path that does not exist."""
        bad_path = str(tmp_path / "does_not_exist.ts")
        with pytest.raises(Exception):
            scan_file(bad_path)

    def test_all_func_lines(self, tmp_path):
        """All-Func topology: every line captured, found == {1..5}."""
        lines = [
            "function a() {",
            "function b() {",
            "function c() {",
            "function d() {",
            "function e() {",
        ]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert found == {1, 2, 3, 4, 5}

    def test_all_arrow_lines(self, tmp_path):
        """All-Arrow topology: every line captured, found == {1..3}."""
        lines = ["const a = () => {", "const b = () => {", "const c = () => {"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert found == {1, 2, 3}

    def test_method_inside_class_captured(self, tmp_path):
        """ClassOpen excluded, both Methods (lines 2, 3) captured inside class body."""
        lines = ["class MyClass {", "  methodOne() {", "  methodTwo() {", "}"]
        path = write_fixture(tmp_path, lines)
        result = scan_file(path)
        found = {s.line_number for s in result}
        assert 1 not in found
        assert 2 in found
        assert 3 in found

    def test_mixed_topology_matches_spec(self, tmp_path):
        """Full spec check on standard fixture: type, count, line numbers, and all invariants."""
        path = write_fixture(tmp_path, FIXTURE_LINES)
        result = scan_file(path)
        assert isinstance(result, list)
        found = {s.line_number for s in result}
        assert found == EXPECTED_LINE_NUMBERS
        assert len(result) == 4
        for s in result:
            assert isinstance(s, Skeleton)
            assert isinstance(s.line_number, int)
            assert s.line_number >= 1
            assert s.line_number <= len(FIXTURE_LINES)