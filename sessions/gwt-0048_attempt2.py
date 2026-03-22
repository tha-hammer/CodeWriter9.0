import os
import tempfile
import textwrap
import pytest
from scanner_typescript_line_ranges import scan_file

# ---------------------------------------------------------------------------
# Ten TypeScript source variants — all satisfy the TLA+ model:
#   Lines == << "Func", "Other", "ClassOpen", "Method", "Arrow", "Other", "Func" >>
#   N     == 7
#
# Expected skeletons (final state of every trace):
#   {line_num |-> 1, line_num |-> 4, line_num |-> 5, line_num |-> 7}
#
# Variants use only universally safe TypeScript patterns (plain `function`
# keyword, standard method syntax, const-arrow assignment) so the scanner's
# pattern matching is exercised across diverse but unambiguous identifier names.
# ---------------------------------------------------------------------------

# Variant 1 — original fixture (plain function / class / method / arrow)
TS_V1 = textwrap.dedent("""\
    function alpha(x: number): number {
      return x;
    class MyClass {
      myMethod(): void {
      const arrowFn = (): void => {
      }
    function beta(): string {
""")

# Variant 2 — compute / Calculator domain
TS_V2 = textwrap.dedent("""\
    function compute(n: number): number {
      return n;
    class Calculator {
      calculate(): void {
      const transform = (): void => {
      }
    function display(): string {
""")

# Variant 3 — initialise / Manager domain
TS_V3 = textwrap.dedent("""\
    function initialize(cfg: string): string {
      return cfg;
    class Manager {
      manage(): void {
      const delegate = (): void => {
      }
    function finalize(): string {
""")

# Variant 4 — build / Builder domain
TS_V4 = textwrap.dedent("""\
    function build(src: string): string {
      return src;
    class Builder {
      assemble(): void {
      const construct = (): void => {
      }
    function deploy(): string {
""")

# Variant 5 — parse / Parser domain
TS_V5 = textwrap.dedent("""\
    function parseInput(input: string): string {
      return input;
    class Parser {
      tokenize(): void {
      const lexer = (): void => {
      }
    function serialize(): string {
""")

# Variant 6 — load / Loader domain
TS_V6 = textwrap.dedent("""\
    function loadResource(path: string): string {
      return path;
    class Loader {
      fetchData(): void {
      const binder = (): void => {
      }
    function unload(): string {
""")

# Variant 7 — open / Connection domain
TS_V7 = textwrap.dedent("""\
    function openConnection(name: string): string {
      return name;
    class Connection {
      connectSocket(): void {
      const bindPort = (): void => {
      }
    function closeConnection(): string {
""")

# Variant 8 — start / Runner domain
TS_V8 = textwrap.dedent("""\
    function startProcess(id: number): number {
      return id;
    class Runner {
      runTask(): void {
      const executeStep = (): void => {
      }
    function stopProcess(): string {
""")

# Variant 9 — encode / Codec domain
TS_V9 = textwrap.dedent("""\
    function encodeData(data: string): string {
      return data;
    class Codec {
      encodeChunk(): void {
      const compressBlock = (): void => {
      }
    function decodeData(): string {
""")

# Variant 10 — validate / Validator domain
TS_V10 = textwrap.dedent("""\
    function validateInput(val: string): string {
      return val;
    class Validator {
      checkConstraints(): void {
      const applyRule = (): void => {
      }
    function sanitizeOutput(): string {
""")

# Alias used by the class-level and edge-case tests (keeps their bodies unchanged)
TS_SOURCE_7LINES = TS_V1

EXPECTED_LINE_NUMBERS = {1, 4, 5, 7}
N = 7
FUNC_LINES = {1, 4, 5, 7}   # lines whose declaration type is Func/Method/Arrow

ALL_VARIANTS = [TS_V1, TS_V2, TS_V3, TS_V4, TS_V5,
                TS_V6, TS_V7, TS_V8, TS_V9, TS_V10]


@pytest.fixture
def ts_file(tmp_path):
    """Write the 7-line TypeScript fixture (V1) to a temporary file and return its path."""
    p = tmp_path / "subject.ts"
    p.write_text(TS_V1)
    return str(p)


# ---------------------------------------------------------------------------
# Helper: verify all four TLA+ invariants against a list of Skeleton objects.
# ---------------------------------------------------------------------------

def _assert_invariants(skeletons, *, n=N, func_lines=FUNC_LINES):
    skeletons = list(skeletons)
    line_numbers = {s.line_number for s in skeletons}

    for s in skeletons:
        assert s.line_number >= 1, (
            f"OneIndexed violated: line_number={s.line_number} is < 1"
        )

    for s in skeletons:
        assert 1 <= s.line_number <= n, (
            f"LineNumberCorrect violated: line_number={s.line_number} outside [1..{n}]"
        )
        assert s.line_number in func_lines, (
            f"LineNumberCorrect violated: line_number={s.line_number} is not a Func/Arrow/Method line"
        )

    for k in func_lines:
        assert k in line_numbers, (
            f"NoGaps violated: no skeleton found for declaration line {k}"
        )

    assert len(line_numbers) <= n, (
        f"CursorBounded sanity: more skeletons ({len(line_numbers)}) than lines ({n})"
    )


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

def test_trace_1(tmp_path):
    """TLA+ trace 1: V1 source — plain function/class/method/arrow identifiers."""
    p = tmp_path / "v1.ts"
    p.write_text(TS_V1)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 1 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_2(tmp_path):
    """TLA+ trace 2: V2 source — compute/Calculator domain identifiers."""
    p = tmp_path / "v2.ts"
    p.write_text(TS_V2)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 2 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_3(tmp_path):
    """TLA+ trace 3: V3 source — initialize/Manager domain identifiers."""
    p = tmp_path / "v3.ts"
    p.write_text(TS_V3)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 3 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_4(tmp_path):
    """TLA+ trace 4: V4 source — build/Builder domain identifiers."""
    p = tmp_path / "v4.ts"
    p.write_text(TS_V4)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 4 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_5(tmp_path):
    """TLA+ trace 5: V5 source — parse/Parser domain identifiers."""
    p = tmp_path / "v5.ts"
    p.write_text(TS_V5)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 5 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_6(tmp_path):
    """TLA+ trace 6: V6 source — load/Loader domain identifiers."""
    p = tmp_path / "v6.ts"
    p.write_text(TS_V6)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 6 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_7(tmp_path):
    """TLA+ trace 7: V7 source — open/Connection domain identifiers."""
    p = tmp_path / "v7.ts"
    p.write_text(TS_V7)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 7 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_8(tmp_path):
    """TLA+ trace 8: V8 source — start/Runner domain identifiers."""
    p = tmp_path / "v8.ts"
    p.write_text(TS_V8)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 8 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_9(tmp_path):
    """TLA+ trace 9: V9 source — encode/Codec domain identifiers."""
    p = tmp_path / "v9.ts"
    p.write_text(TS_V9)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 9 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


def test_trace_10(tmp_path):
    """TLA+ trace 10: V10 source — validate/Validator domain identifiers."""
    p = tmp_path / "v10.ts"
    p.write_text(TS_V10)
    skeletons = list(scan_file(str(p)))
    line_numbers = {s.line_number for s in skeletons}
    assert line_numbers == EXPECTED_LINE_NUMBERS, (
        f"Trace 10 final state mismatch: expected {EXPECTED_LINE_NUMBERS}, got {line_numbers}"
    )
    _assert_invariants(skeletons)


# ===========================================================================
# Dedicated invariant verifiers
# ===========================================================================

class TestOneIndexed:
    """OneIndexed TLA+ invariant: forall s in skeletons : s.line_number >= 1."""

    def test_one_indexed_trace_topology(self, tmp_path):
        p = tmp_path / "a.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        for s in skeletons:
            assert s.line_number >= 1, f"OneIndexed violated: {s.line_number}"

    def test_one_indexed_single_func_first_line(self, tmp_path):
        p = tmp_path / "b.ts"
        p.write_text("function solo(): void {\n}\n")
        skeletons = list(scan_file(str(p)))
        assert len(skeletons) >= 1
        for s in skeletons:
            assert s.line_number >= 1

    def test_one_indexed_functions_not_on_line_zero(self, tmp_path):
        p = tmp_path / "c.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        line_numbers = [s.line_number for s in skeletons]
        assert 0 not in line_numbers, "OneIndexed violated: line_number 0 found"


class TestLineNumberCorrect:
    """LineNumberCorrect TLA+ invariant: every skeleton points to a Func/Arrow/Method line within [1..N]."""

    def test_line_number_correct_trace_topology(self, tmp_path):
        p = tmp_path / "a.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        for s in skeletons:
            assert 1 <= s.line_number <= N
            assert s.line_number in FUNC_LINES, (
                f"skeleton at line {s.line_number} does not correspond to a declaration line"
            )

    def test_line_number_correct_non_declaration_lines_absent(self, tmp_path):
        p = tmp_path / "b.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        non_decl = {2, 3, 6}
        line_numbers = {s.line_number for s in skeletons}
        overlap = line_numbers & non_decl
        assert not overlap, (
            f"LineNumberCorrect violated: skeletons found for non-declaration lines {overlap}"
        )

    def test_line_number_correct_within_bounds(self, tmp_path):
        p = tmp_path / "c.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        file_line_count = len(TS_SOURCE_7LINES.splitlines())
        for s in skeletons:
            assert s.line_number <= file_line_count, (
                f"LineNumberCorrect violated: line_number {s.line_number} > file length {file_line_count}"
            )


class TestNoGaps:
    """NoGaps TLA+ invariant: after scan completes, every declaration line has a corresponding skeleton."""

    def test_no_gaps_all_four_declarations_present(self, tmp_path):
        p = tmp_path / "a.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        missing = EXPECTED_LINE_NUMBERS - line_numbers
        assert not missing, f"NoGaps violated: declaration lines {missing} have no skeleton"

    def test_no_gaps_exact_count(self, tmp_path):
        p = tmp_path / "b.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        line_numbers = [s.line_number for s in skeletons]
        assert len(line_numbers) == len(set(line_numbers)), (
            f"NoGaps / uniqueness violated: duplicate line_numbers found in {line_numbers}"
        )
        assert len(skeletons) == len(EXPECTED_LINE_NUMBERS), (
            f"NoGaps violated: expected {len(EXPECTED_LINE_NUMBERS)} skeletons, got {len(skeletons)}"
        )

    def test_no_gaps_second_topology_all_funcs(self, tmp_path):
        source = "\n".join(
            f"function f{i}(): void {{}}" for i in range(1, 5)
        ) + "\n"
        p = tmp_path / "c.ts"
        p.write_text(source)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        for k in range(1, 5):
            assert k in line_numbers, f"NoGaps violated: declaration line {k} missing"


class TestCursorBounded:
    """CursorBounded TLA+ invariant: i <= N + 1 throughout scanning; verified via correct termination."""

    def test_cursor_bounded_scan_terminates(self, tmp_path):
        p = tmp_path / "a.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        assert isinstance(skeletons, list), (
            "CursorBounded: scan_file result could not be materialised to a list"
        )
        assert len(skeletons) <= N, (
            f"CursorBounded: returned {len(skeletons)} skeletons for an {N}-line file"
        )

    def test_cursor_bounded_no_extra_skeletons_beyond_file(self, tmp_path):
        p = tmp_path / "b.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        for s in skeletons:
            assert s.line_number <= N, (
                f"CursorBounded violated: skeleton at line {s.line_number} > N={N}"
            )

    def test_cursor_bounded_single_line_file(self, tmp_path):
        p = tmp_path / "c.ts"
        p.write_text("function only(): void {}\n")
        skeletons = list(scan_file(str(p)))
        assert len(skeletons) >= 1
        for s in skeletons:
            assert s.line_number == 1
            assert s.line_number <= 1, "CursorBounded violated for N=1"


# ===========================================================================
# Edge-case tests
# ===========================================================================

class TestEdgeCases:

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.ts"
        p.write_text("")
        result = list(scan_file(str(p)))
        assert result == [], f"Expected [] for empty file, got {result}"

    def test_no_declarations(self, tmp_path):
        source = "// just a comment\nconst x = 1;\nconst y = 2;\n"
        p = tmp_path / "nodecl.ts"
        p.write_text(source)
        result = list(scan_file(str(p)))
        assert result == [], (
            f"Expected no skeletons for file with no declarations, "
            f"got {[s.line_number for s in result]}"
        )

    def test_single_function_at_line_1(self, tmp_path):
        source = "function single(): void {}\nconst x = 1;\n"
        p = tmp_path / "single.ts"
        p.write_text(source)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        assert 1 in line_numbers, "Expected skeleton at line 1"
        for s in skeletons:
            assert s.line_number >= 1

    def test_adjacent_declarations_lines_4_and_5(self, tmp_path):
        source = textwrap.dedent("""\
            // line 1 other
            // line 2 other
            // line 3 other
            myMethod(): void {
            const arrowFn = (): void => {
            // line 6 other
            // line 7 other
        """)
        p = tmp_path / "adjacent.ts"
        p.write_text(source)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        assert 4 in line_numbers, "NoGaps: expected skeleton at line 4"
        assert 5 in line_numbers, "NoGaps: expected skeleton at line 5"

    def test_declaration_only_at_last_line(self, tmp_path):
        source = "// other\n// other\nfunction last(): void {}\n"
        p = tmp_path / "last.ts"
        p.write_text(source)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        assert 3 in line_numbers, "Expected skeleton at final line 3"
        for s in skeletons:
            assert s.line_number >= 1

    def test_all_lines_are_declarations(self, tmp_path):
        source = textwrap.dedent("""\
            function f1(): void {}
            function f2(): void {}
            function f3(): void {}
        """)
        p = tmp_path / "alldecl.ts"
        p.write_text(source)
        skeletons = list(scan_file(str(p)))
        line_numbers = {s.line_number for s in skeletons}
        for k in (1, 2, 3):
            assert k in line_numbers, f"NoGaps violated: line {k} missing"

    def test_idempotent_repeated_calls(self, tmp_path):
        p = tmp_path / "idem.ts"
        p.write_text(TS_SOURCE_7LINES)
        first = {s.line_number for s in list(scan_file(str(p)))}
        second = {s.line_number for s in list(scan_file(str(p)))}
        assert first == second, (
            f"scan_file is not idempotent: first={first}, second={second}"
        )

    def test_line_numbers_are_integers(self, tmp_path):
        p = tmp_path / "types.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        for s in skeletons:
            assert isinstance(s.line_number, int), (
                f"Expected int line_number, got {type(s.line_number)} for value {s.line_number}"
            )

    def test_no_duplicate_line_numbers(self, tmp_path):
        p = tmp_path / "nodup.ts"
        p.write_text(TS_SOURCE_7LINES)
        skeletons = list(scan_file(str(p)))
        line_numbers = [s.line_number for s in skeletons]
        assert len(line_numbers) == len(set(line_numbers)), (
            f"Duplicate line_numbers found: {line_numbers}"
        )