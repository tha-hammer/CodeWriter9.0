import os
import tempfile
import pytest
from scanner_rust_line_ranges import scan_file
from registry.types import Node, Edge, EdgeType

# ---------------------------------------------------------------------------
# TLA+ model constants
# Lines == << "ImplOpen", "Fn", "CloseBrace", "TraitOpen", "Fn", "CloseBrace", "Fn" >>
# N == 7
# ---------------------------------------------------------------------------

LINES = ["ImplOpen", "Fn", "CloseBrace", "TraitOpen", "Fn", "CloseBrace", "Fn"]
N = 7

RUST_SOURCE_CANONICAL = (
    "impl Foo {\n"
    "fn free_fn() {}\n"
    "}\n"
    "trait MyTrait {\n"
    "fn trait_method();\n"
    "}\n"
    "fn standalone() {}\n"
)

EXPECTED_LINE_NUMBERS_CANONICAL = {2, 7}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_rust_file(content: str) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".rs", delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


def _in_trait(k: int, lines: list) -> bool:
    """TLA+ InTrait(k): true iff line k sits inside an open trait block."""
    for j in range(1, k):
        if lines[j - 1] == "TraitOpen":
            has_close = any(
                lines[m - 1] == "CloseBrace"
                for m in range(j + 1, k)
            )
            if not has_close:
                return True
    return False


def _verify_line_number_correct(skeletons, lines: list, n: int) -> None:
    for s in skeletons:
        assert 1 <= s.line_number <= n, (
            f"LineNumberCorrect: line_number {s.line_number} not in [1..{n}]"
        )
        assert lines[s.line_number - 1] == "Fn", (
            f"LineNumberCorrect: line {s.line_number} is "
            f"'{lines[s.line_number - 1]}', expected 'Fn'"
        )


def _verify_trait_exclusion(skeletons, lines: list) -> None:
    for s in skeletons:
        assert not _in_trait(s.line_number, lines), (
            f"TraitExclusion: skeleton at line {s.line_number} is inside a trait"
        )


def _verify_no_gaps(skeletons, lines: list, n: int) -> None:
    found = {s.line_number for s in skeletons}
    for k in range(1, n + 1):
        if lines[k - 1] == "Fn" and not _in_trait(k, lines):
            assert k in found, (
                f"NoGaps: non-trait Fn at line {k} has no skeleton"
            )


def _verify_cursor_bounded(skeletons, n: int) -> None:
    for s in skeletons:
        assert s.line_number <= n, (
            f"CursorBounded: line_number {s.line_number} > N={n}"
        )


def _verify_all_invariants(skeletons, lines: list, n: int) -> None:
    _verify_line_number_correct(skeletons, lines, n)
    _verify_trait_exclusion(skeletons, lines)
    _verify_no_gaps(skeletons, lines, n)
    _verify_cursor_bounded(skeletons, n)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_rust_file():
    path = _write_rust_file(RUST_SOURCE_CANONICAL)
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Trace 1 – 10
# ---------------------------------------------------------------------------

def test_trace_1_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_2_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_3_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_4_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_5_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_6_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_7_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_8_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_9_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


def test_trace_10_final_state_and_invariants(canonical_rust_file):
    skeletons = scan_file(canonical_rust_file)
    actual = {s.line_number for s in skeletons}
    assert actual == EXPECTED_LINE_NUMBERS_CANONICAL
    _verify_all_invariants(skeletons, LINES, N)


# ---------------------------------------------------------------------------
# Explicit invariant-verifier tests
# ---------------------------------------------------------------------------

class TestInvariantLineNumberCorrect:

    def test_topology_canonical_seven_lines(self, canonical_rust_file):
        skeletons = scan_file(canonical_rust_file)
        _verify_line_number_correct(skeletons, LINES, N)
        actual = {s.line_number for s in skeletons}
        assert actual == {2, 7}

    def test_topology_single_fn_at_line_1(self):
        lines = ["Fn"]
        src = _write_rust_file("fn only() {}\n")
        try:
            skeletons = scan_file(src)
            _verify_line_number_correct(skeletons, lines, n=1)
            assert {s.line_number for s in skeletons} == {1}
        finally:
            os.unlink(src)

    def test_topology_two_consecutive_free_fns(self):
        lines = ["Fn", "Fn"]
        src = _write_rust_file("fn alpha() {}\nfn beta() {}\n")
        try:
            skeletons = scan_file(src)
            _verify_line_number_correct(skeletons, lines, n=2)
            assert {s.line_number for s in skeletons} == {1, 2}
        finally:
            os.unlink(src)


class TestInvariantTraitExclusion:

    def test_topology_canonical_trait_fn_excluded(self, canonical_rust_file):
        skeletons = scan_file(canonical_rust_file)
        _verify_trait_exclusion(skeletons, LINES)
        assert 5 not in {s.line_number for s in skeletons}

    def test_topology_trait_only_produces_no_skeletons(self):
        lines = ["TraitOpen", "Fn", "Fn", "CloseBrace"]
        src = _write_rust_file("trait T {\nfn a();\nfn b();\n}\n")
        try:
            skeletons = scan_file(src)
            _verify_trait_exclusion(skeletons, lines)
            assert len(skeletons) == 0
        finally:
            os.unlink(src)

    def test_topology_trait_then_free_fn(self):
        lines = ["TraitOpen", "Fn", "CloseBrace", "Fn"]
        src = _write_rust_file("trait T {\nfn tm();\n}\nfn free() {}\n")
        try:
            skeletons = scan_file(src)
            _verify_trait_exclusion(skeletons, lines)
            assert {s.line_number for s in skeletons} == {4}
        finally:
            os.unlink(src)


class TestInvariantNoGaps:

    def test_topology_canonical_both_free_fns_captured(self, canonical_rust_file):
        skeletons = scan_file(canonical_rust_file)
        _verify_no_gaps(skeletons, LINES, N)

    def test_topology_three_consecutive_free_fns(self):
        lines = ["Fn", "Fn", "Fn"]
        src = _write_rust_file("fn a() {}\nfn b() {}\nfn c() {}\n")
        try:
            skeletons = scan_file(src)
            _verify_no_gaps(skeletons, lines, n=3)
            assert {s.line_number for s in skeletons} == {1, 2, 3}
        finally:
            os.unlink(src)

    def test_topology_interleaved_impl_and_free_fn(self):
        lines = ["ImplOpen", "Fn", "CloseBrace", "Fn"]
        src = _write_rust_file(
            "impl Bar {\n"
            "fn impl_method() {}\n"
            "}\n"
            "fn free() {}\n"
        )
        try:
            skeletons = scan_file(src)
            _verify_no_gaps(skeletons, lines, n=4)
            actual = {s.line_number for s in skeletons}
            assert actual == {2, 4}
        finally:
            os.unlink(src)


class TestInvariantCursorBounded:

    def test_topology_canonical_no_line_number_exceeds_n(self, canonical_rust_file):
        skeletons = scan_file(canonical_rust_file)
        _verify_cursor_bounded(skeletons, N)

    def test_topology_single_line_file(self):
        src = _write_rust_file("fn f() {}\n")
        try:
            skeletons = scan_file(src)
            _verify_cursor_bounded(skeletons, n=1)
            assert all(s.line_number == 1 for s in skeletons)
        finally:
            os.unlink(src)

    def test_topology_five_line_mixed_file(self):
        lines = ["ImplOpen", "Fn", "CloseBrace", "TraitOpen", "CloseBrace"]
        src = _write_rust_file(
            "impl A {\n"
            "fn m() {}\n"
            "}\n"
            "trait T {\n"
            "}\n"
        )
        try:
            skeletons = scan_file(src)
            _verify_cursor_bounded(skeletons, n=5)
            _verify_line_number_correct(skeletons, lines, n=5)
        finally:
            os.unlink(src)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_edge_empty_file():
    src = _write_rust_file("")
    try:
        skeletons = scan_file(src)
        assert len(skeletons) == 0
        _verify_line_number_correct(skeletons, [], n=0)
        _verify_trait_exclusion(skeletons, [])
        _verify_no_gaps(skeletons, [], n=0)
        _verify_cursor_bounded(skeletons, n=0)
    finally:
        os.unlink(src)


def test_edge_no_fn_keywords():
    src = _write_rust_file("struct Foo;\nimpl Foo {}\n// just a comment\n")
    try:
        skeletons = scan_file(src)
        assert len(skeletons) == 0
    finally:
        os.unlink(src)


def test_edge_fn_on_first_line():
    lines = ["Fn"]
    src = _write_rust_file("fn first() {}\n")
    try:
        skeletons = scan_file(src)
        assert len(skeletons) == 1
        assert skeletons[0].line_number == 1
        _verify_all_invariants(skeletons, lines, n=1)
    finally:
        os.unlink(src)


def test_edge_fn_on_last_line():
    lines = ["ImplOpen", "CloseBrace", "Fn"]
    src = _write_rust_file("impl X {\n}\nfn last() {}\n")
    try:
        skeletons = scan_file(src)
        assert {s.line_number for s in skeletons} == {3}
        _verify_all_invariants(skeletons, lines, n=3)
    finally:
        os.unlink(src)


def test_edge_nested_trait_does_not_bleed_into_later_fn():
    lines = ["TraitOpen", "Fn", "CloseBrace", "Fn"]
    src = _write_rust_file(
        "trait T {\n"
        "fn inner();\n"
        "}\n"
        "fn outer() {}\n"
    )
    try:
        skeletons = scan_file(src)
        actual = {s.line_number for s in skeletons}
        assert actual == {4}
        assert 2 not in actual
        _verify_all_invariants(skeletons, lines, n=4)
    finally:
        os.unlink(src)


def test_edge_multiple_trait_blocks_then_free_fn():
    lines = ["TraitOpen", "Fn", "CloseBrace", "TraitOpen", "Fn", "CloseBrace", "Fn"]
    src = _write_rust_file(
        "trait A {\n"
        "fn a();\n"
        "}\n"
        "trait B {\n"
        "fn b();\n"
        "}\n"
        "fn free() {}\n"
    )
    try:
        skeletons = scan_file(src)
        actual = {s.line_number for s in skeletons}
        assert actual == {7}
        assert 2 not in actual
        assert 5 not in actual
        _verify_all_invariants(skeletons, lines, n=7)
    finally:
        os.unlink(src)


def test_edge_canonical_trace_skeleton_count():
    src = _write_rust_file(RUST_SOURCE_CANONICAL)
    try:
        skeletons = scan_file(src)
        assert len(skeletons) == 2, (
            f"Expected exactly 2 skeletons, got {len(skeletons)}"
        )
        line_numbers = [s.line_number for s in skeletons]
        assert len(set(line_numbers)) == len(line_numbers)
        _verify_all_invariants(skeletons, LINES, N)
    finally:
        os.unlink(src)