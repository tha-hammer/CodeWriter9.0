import os
import textwrap
import tempfile
import pytest

from scanner_python_line_ranges import scan_file, Skeleton


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_from_trace() -> str:
    return textwrap.dedent("""\
        def func1():
            pass
        def func2(
                arg):
        async def func3(
                arg):
        async def func4():
            pass
    """)


def _write_tmp(src: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(src)
    except Exception:
        os.close(fd)
        raise
    return path


def _skeleton_map(skeletons) -> dict:
    return {s.line_number: s.is_async for s in skeletons}


# ---------------------------------------------------------------------------
# Shared expected final state
# ---------------------------------------------------------------------------

EXPECTED_LINE_NUMBERS = {1, 3, 5, 7}

EXPECTED_SKELETONS = {
    1: False,
    3: False,
    5: True,
    7: True,
}

N = 7


# ---------------------------------------------------------------------------
# Invariant helpers
# ---------------------------------------------------------------------------

def assert_one_indexed(skeletons):
    for s in skeletons:
        assert s.line_number >= 1, (
            f"OneIndexed violated: line_number={s.line_number} < 1"
        )


def assert_line_number_correct(skeletons, lines_map: dict):
    for s in skeletons:
        assert 1 <= s.line_number <= N, (
            f"LineNumberCorrect violated: line_number={s.line_number} out of [1,{N}]"
        )
        kind = lines_map[s.line_number]
        assert kind in ("Def", "AsyncDef"), (
            f"LineNumberCorrect violated: line {s.line_number} kind={kind!r}"
        )
        expected_async = kind == "AsyncDef"
        assert s.is_async == expected_async, (
            f"LineNumberCorrect violated: line {s.line_number} "
            f"is_async={s.is_async} but kind={kind!r}"
        )


def assert_multi_line_stable(skeletons, lines_map: dict):
    for s in skeletons:
        assert lines_map.get(s.line_number) in ("Def", "AsyncDef"), (
            f"MultiLineStable violated: line {s.line_number} is not a def line"
        )


def assert_sig_start_valid(skeletons):
    for s in skeletons:
        assert s.line_number >= 1, (
            f"SigStartValid violated: sig_start={s.line_number} < 1"
        )


def assert_no_gaps(skeletons, lines_map: dict, cursor_past_end: bool):
    if not cursor_past_end:
        return
    emitted = {s.line_number for s in skeletons}
    for k, kind in lines_map.items():
        if kind in ("Def", "AsyncDef"):
            assert k in emitted, (
                f"NoGaps violated: def/async-def at line {k} has no skeleton"
            )


def assert_cursor_bounded(cursor: int):
    assert cursor <= N + 1, f"CursorBounded violated: cursor={cursor} > {N+1}"


def assert_all_invariants(skeletons, lines_map: dict, cursor: int):
    assert_one_indexed(skeletons)
    assert_line_number_correct(skeletons, lines_map)
    assert_multi_line_stable(skeletons, lines_map)
    assert_sig_start_valid(skeletons)
    assert_no_gaps(skeletons, lines_map, cursor_past_end=(cursor > N))
    assert_cursor_bounded(cursor)


LINES_MAP = {
    1: "Def",
    2: "Other",
    3: "Def",
    4: "Other",
    5: "AsyncDef",
    6: "Other",
    7: "AsyncDef",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def source_path():
    path = _write_tmp(_source_from_trace())
    yield path
    os.unlink(path)


@pytest.fixture(scope="module")
def scanned(source_path):
    return scan_file(source_path)


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

class TestTrace1:
    def test_skeleton_count(self, scanned):
        assert len(scanned) == 4

    def test_line_numbers_present(self, scanned):
        assert {s.line_number for s in scanned} == EXPECTED_LINE_NUMBERS

    def test_sync_def_line1(self, scanned):
        skel = next(s for s in scanned if s.line_number == 1)
        assert skel.is_async is False

    def test_sync_multiline_def_line3(self, scanned):
        skel = next(s for s in scanned if s.line_number == 3)
        assert skel.is_async is False

    def test_async_multiline_def_line5(self, scanned):
        skel = next(s for s in scanned if s.line_number == 5)
        assert skel.is_async is True

    def test_async_def_line7(self, scanned):
        skel = next(s for s in scanned if s.line_number == 7)
        assert skel.is_async is True

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 2
# ---------------------------------------------------------------------------

class TestTrace2:
    def test_skeleton_count(self, scanned):
        assert len(scanned) == 4

    def test_final_skeleton_map(self, scanned):
        assert _skeleton_map(scanned) == EXPECTED_SKELETONS

    def test_one_indexed(self, scanned):
        assert_one_indexed(scanned)

    def test_line_number_correct(self, scanned):
        assert_line_number_correct(scanned, LINES_MAP)

    def test_multi_line_stable(self, scanned):
        assert_multi_line_stable(scanned, LINES_MAP)

    def test_sig_start_valid(self, scanned):
        assert_sig_start_valid(scanned)

    def test_no_gaps(self, scanned):
        assert_no_gaps(scanned, LINES_MAP, cursor_past_end=True)

    def test_cursor_bounded(self):
        assert_cursor_bounded(cursor=8)


# ---------------------------------------------------------------------------
# Trace 3
# ---------------------------------------------------------------------------

class TestTrace3:
    def test_final_skeletons_match_expected(self, scanned):
        result = _skeleton_map(scanned)
        assert result == EXPECTED_SKELETONS

    def test_no_skeleton_on_other_lines(self, scanned):
        other_lines = {2, 4, 6}
        for s in scanned:
            assert s.line_number not in other_lines, (
                f"Unexpected skeleton on 'Other' line {s.line_number}"
            )

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 4
# ---------------------------------------------------------------------------

class TestTrace4:
    def test_skeleton_line_numbers_are_one_indexed(self, scanned):
        for s in scanned:
            assert s.line_number >= 1

    def test_async_flag_matches_def_keyword(self, scanned):
        for s in scanned:
            expected = LINES_MAP[s.line_number] == "AsyncDef"
            assert s.is_async == expected

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 5
# ---------------------------------------------------------------------------

class TestTrace5:
    def test_skeleton_count_equals_def_line_count(self, scanned):
        def_line_count = sum(
            1 for v in LINES_MAP.values() if v in ("Def", "AsyncDef")
        )
        assert len(scanned) == def_line_count

    def test_skeletons_only_on_def_lines(self, scanned):
        for s in scanned:
            assert LINES_MAP[s.line_number] in ("Def", "AsyncDef")

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 6
# ---------------------------------------------------------------------------

class TestTrace6:
    def test_multiline_sig_reported_at_def_line_not_body_line(self, scanned):
        line_numbers = {s.line_number for s in scanned}
        assert 3 in line_numbers
        assert 4 not in line_numbers

    def test_multiline_async_sig_reported_at_async_def_line(self, scanned):
        line_numbers = {s.line_number for s in scanned}
        assert 5 in line_numbers
        assert 6 not in line_numbers

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 7
# ---------------------------------------------------------------------------

class TestTrace7:
    def test_first_skeleton_is_line1(self, scanned):
        line_numbers = sorted(s.line_number for s in scanned)
        assert line_numbers[0] == 1

    def test_last_skeleton_is_line7(self, scanned):
        line_numbers = sorted(s.line_number for s in scanned)
        assert line_numbers[-1] == 7

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 8
# ---------------------------------------------------------------------------

class TestTrace8:
    def test_two_sync_skeletons(self, scanned):
        sync_skels = [s for s in scanned if not s.is_async]
        assert len(sync_skels) == 2
        assert {s.line_number for s in sync_skels} == {1, 3}

    def test_two_async_skeletons(self, scanned):
        async_skels = [s for s in scanned if s.is_async]
        assert len(async_skels) == 2
        assert {s.line_number for s in async_skels} == {5, 7}

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 9
# ---------------------------------------------------------------------------

class TestTrace9:
    def test_no_duplicate_line_numbers(self, scanned):
        line_numbers = [s.line_number for s in scanned]
        assert len(line_numbers) == len(set(line_numbers)), (
            "Duplicate line_number entries found"
        )

    def test_skeleton_map_complete(self, scanned):
        assert _skeleton_map(scanned) == EXPECTED_SKELETONS

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Trace 10
# ---------------------------------------------------------------------------

class TestTrace10:
    def test_exact_final_state(self, scanned):
        result = _skeleton_map(scanned)
        assert result == {1: False, 3: False, 5: True, 7: True}

    def test_cursor_at_n_plus_1(self):
        assert_cursor_bounded(cursor=8)

    def test_all_invariants(self, scanned):
        assert_all_invariants(scanned, LINES_MAP, cursor=8)


# ---------------------------------------------------------------------------
# Dedicated invariant verifiers
# ---------------------------------------------------------------------------

class TestInvariantOneIndexed:
    def test_one_indexed_full_file(self, scanned):
        assert_one_indexed(scanned)

    def test_one_indexed_single_def(self):
        src = "def only():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert_one_indexed(skeletons)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1
        finally:
            os.unlink(path)

    def test_one_indexed_async_only(self):
        src = "async def run():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert_one_indexed(skeletons)
        finally:
            os.unlink(path)


class TestInvariantLineNumberCorrect:
    def test_line_number_correct_full_file(self, scanned):
        assert_line_number_correct(scanned, LINES_MAP)

    def test_line_number_correct_mixed_file(self):
        src = textwrap.dedent("""\
            # comment
            def foo():
                pass
            async def bar():
                pass
        """)
        path = _write_tmp(src)
        local_lines = {2: "Def", 4: "AsyncDef"}
        try:
            skeletons = scan_file(path)
            for s in skeletons:
                if s.line_number in local_lines:
                    kind = local_lines[s.line_number]
                    assert s.is_async == (kind == "AsyncDef")
        finally:
            os.unlink(path)


class TestInvariantMultiLineStable:
    def test_multi_line_stable_full_file(self, scanned):
        assert_multi_line_stable(scanned, LINES_MAP)

    def test_multi_line_stable_all_multiline_sigs(self):
        src = textwrap.dedent("""\
            def alpha(
                    x,
                    y):
                pass
            async def beta(
                    a,
                    b):
                pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            for s in skeletons:
                assert s.line_number in {1, 5}
        finally:
            os.unlink(path)


class TestInvariantSigStartValid:
    def test_sig_start_valid_full_file(self, scanned):
        assert_sig_start_valid(scanned)
        line_numbers = {s.line_number for s in scanned}
        assert 3 in line_numbers, "SigStartValid: sig_start for func2 must be line 3"
        assert 4 not in line_numbers, "SigStartValid: continuation line 4 must not anchor a skeleton"
        assert 5 in line_numbers, "SigStartValid: sig_start for func3 must be line 5"
        assert 6 not in line_numbers, "SigStartValid: continuation line 6 must not anchor a skeleton"

    def test_sig_start_valid_multi_param_sync(self):
        src = textwrap.dedent("""\
            def long_sig(
                    param_a,
                    param_b):
                pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert_sig_start_valid(skeletons)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1, (
                f"SigStartValid: expected sig_start=1, got {skeletons[0].line_number}"
            )
            assert skeletons[0].is_async is False
        finally:
            os.unlink(path)

    def test_sig_start_valid_multi_param_async(self):
        src = textwrap.dedent("""\
            async def long_sig(
                    param_a,
                    param_b):
                pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert_sig_start_valid(skeletons)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1, (
                f"SigStartValid: expected sig_start=1, got {skeletons[0].line_number}"
            )
            assert skeletons[0].is_async is True
        finally:
            os.unlink(path)


class TestInvariantNoGaps:
    def test_no_gaps_full_file(self, scanned):
        assert_no_gaps(scanned, LINES_MAP, cursor_past_end=True)

    def test_no_gaps_consecutive_defs(self):
        src = textwrap.dedent("""\
            def a(): pass
            def b(): pass
            async def c(): pass
        """)
        path = _write_tmp(src)
        local_lines = {1: "Def", 2: "Def", 3: "AsyncDef"}
        try:
            skeletons = scan_file(path)
            emitted = {s.line_number for s in skeletons}
            for k, kind in local_lines.items():
                assert k in emitted, f"NoGaps: missing skeleton for line {k}"
        finally:
            os.unlink(path)


class TestInvariantCursorBounded:
    def test_cursor_bounded_after_full_scan(self):
        assert_cursor_bounded(cursor=8)

    def test_cursor_bounded_single_line_file(self):
        src = "def solo():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 1, (
                "CursorBounded: single-def file must yield exactly 1 skeleton"
            )
            assert skeletons[0].line_number == 1, (
                "CursorBounded: skeleton must be anchored at line 1"
            )
        finally:
            os.unlink(path)

    def test_cursor_bounded_empty_file(self):
        path = _write_tmp("")
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 0, (
                "CursorBounded: empty file must yield 0 skeletons"
            )
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_file_returns_no_skeletons(self):
        path = _write_tmp("")
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 0
        finally:
            os.unlink(path)

    def test_file_with_no_functions(self):
        src = textwrap.dedent("""\
            import os
            x = 1
            y = 2
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 0
            assert_one_indexed(skeletons)
        finally:
            os.unlink(path)

    def test_single_sync_def_line1(self):
        src = "def solo():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1
            assert skeletons[0].is_async is False
            assert_one_indexed(skeletons)
            assert_sig_start_valid(skeletons)
            assert_cursor_bounded(cursor=2)
        finally:
            os.unlink(path)

    def test_single_async_def_line1(self):
        src = "async def solo():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1
            assert skeletons[0].is_async is True
        finally:
            os.unlink(path)

    def test_multiline_sig_only_emits_once(self):
        src = textwrap.dedent("""\
            def multiline(
                    arg1,
                    arg2):
                pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1
            assert skeletons[0].is_async is False
        finally:
            os.unlink(path)

    def test_async_multiline_sig_only_emits_once(self):
        src = textwrap.dedent("""\
            async def multiline(
                    arg1,
                    arg2):
                pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            assert len(skeletons) == 1
            assert skeletons[0].line_number == 1
            assert skeletons[0].is_async is True
        finally:
            os.unlink(path)

    def test_full_trace_file_matches_all_expected_skeletons(self, source_path):
        skeletons = scan_file(source_path)
        assert len(skeletons) == 4
        result = _skeleton_map(skeletons)
        assert result == {1: False, 3: False, 5: True, 7: True}
        assert_all_invariants(skeletons, LINES_MAP, cursor=8)

    def test_nested_functions_inner_def_captured(self):
        src = textwrap.dedent("""\
            def outer():
                def inner():
                    pass
        """)
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            line_numbers = {s.line_number for s in skeletons}
            assert 1 in line_numbers
            assert 2 in line_numbers
            assert_one_indexed(skeletons)
            assert_sig_start_valid(skeletons)
        finally:
            os.unlink(path)

    def test_def_at_last_line_with_continuation_false(self):
        src = "x = 1\nasync def tail():\n    pass\n"
        path = _write_tmp(src)
        try:
            skeletons = scan_file(path)
            line_numbers = {s.line_number for s in skeletons}
            assert 2 in line_numbers
            tail = next(s for s in skeletons if s.line_number == 2)
            assert tail.is_async is True
        finally:
            os.unlink(path)