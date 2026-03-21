"""
pytest test suite for CW7Extract.extract(db_path)

Derived from TLC-verified TLA+ spec (CW7Extract module).
All 10 traces share an identical final state; they are captured as a single
parametrized test plus dedicated invariant and edge-case classes.

Assumed CW7 SQLite schema:
  sessions(id INTEGER PRIMARY KEY)
  requirements(id INTEGER PRIMARY KEY, text TEXT, session_id INTEGER)
  acceptance_criteria(
      id             INTEGER PRIMARY KEY,
      format         TEXT,      -- 'gwt' | 'other' | ...
      given          TEXT,
      when_text      TEXT,
      then_text      TEXT,
      requirement_id INTEGER,
      name           TEXT       -- nullable
  )

Adjust column names / table names to match the real CW7 schema if they differ.
"""

import re
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Lazy import of extract to avoid collection-time ImportError
# ---------------------------------------------------------------------------

def _get_extract():
    from registry.cw7 import extract
    return extract


# ---------------------------------------------------------------------------
# Constants from the TLA+ spec
# ---------------------------------------------------------------------------

CW7_PREFIX = "cw7-crit-"
GWT_FORMAT = "gwt"

CRITERION_ID_RE = re.compile(r"^cw7-crit-\d+$")

# ---------------------------------------------------------------------------
# Database-builder helper
# ---------------------------------------------------------------------------

_SCHEMA_DDL = """
CREATE TABLE sessions (
    id  INTEGER PRIMARY KEY
);
CREATE TABLE requirements (
    requirement_id INTEGER NOT NULL,
    description    TEXT    NOT NULL,
    session_id     INTEGER NOT NULL
);
CREATE TABLE acceptance_criteria (
    id             INTEGER PRIMARY KEY,
    requirement_id INTEGER NOT NULL,
    given_clause   TEXT    NOT NULL DEFAULT '',
    when_clause    TEXT    NOT NULL DEFAULT '',
    then_clause    TEXT    NOT NULL DEFAULT '',
    session_id     INTEGER NOT NULL,
    format         TEXT    NOT NULL
);
"""


def _build_db(path, sessions, requirements, acceptance_criteria):
    """Build a CW7-compatible SQLite database.

    Args:
        sessions: list of (id,) tuples
        requirements: list of (requirement_id, description, session_id) tuples
        acceptance_criteria: list of (id, format, given, when_text, then_text,
                            requirement_id, name) tuples — adapted to real schema
    """
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript(_SCHEMA_DDL)
    cur.executemany("INSERT INTO sessions VALUES (?)", sessions)
    cur.executemany(
        "INSERT INTO requirements(requirement_id, description, session_id) VALUES (?, ?, ?)",
        requirements,
    )
    # Remap old test format (id, format, given, when_text, then_text, req_id, name)
    # to real schema (id, requirement_id, given_clause, when_clause, then_clause, session_id, format)
    for row in acceptance_criteria:
        ac_id, fmt, given, when_text, then_text, req_id, _name = row
        # Derive session_id from the first session
        sid = sessions[0][0] if sessions else 1
        cur.execute(
            "INSERT INTO acceptance_criteria"
            "(id, requirement_id, given_clause, when_clause, then_clause, session_id, format)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ac_id, req_id, given, when_text, then_text, sid, fmt),
        )
    con.commit()
    con.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def extract():
    return _get_extract()


@pytest.fixture
def standard_db(tmp_path):
    """
    Canonical fixture matching all 10 TLC traces (Init -> Terminate):
      Sessions:  1 (id=1)
      Requirements: 2 rows -- (1,'req 1',1), (2,'req 2',1)
      AC rows:
        id=1  format=gwt   given=''  when_text='nonempty'  then_text=''  req=1  name='slug'
        id=2  format=other given=''  when_text='nonempty'  then_text=''  req=1  name=None
        id=3  format=gwt   given=''  when_text=''          then_text=''  req=1  name=None
    Final state: 2 output_reqs, 2 output_gwts (cw7-crit-1, cw7-crit-3).
    """
    path = str(tmp_path / "standard.db")
    _build_db(
        path,
        sessions=[(1,)],
        requirements=[(1, "req 1", 1), (2, "req 2", 1)],
        acceptance_criteria=[
            (1, "gwt",   "", "nonempty", "", 1, "slug"),
            (2, "other", "", "nonempty", "", 1, None),
            (3, "gwt",   "", "",         "", 1, None),
        ],
    )
    return path


@pytest.fixture
def zero_sessions_db(tmp_path):
    """Empty sessions table -> err_no_session path."""
    path = str(tmp_path / "zero_sessions.db")
    _build_db(path, sessions=[], requirements=[], acceptance_criteria=[])
    return path


@pytest.fixture
def multi_sessions_db(tmp_path):
    """Two sessions, no session_id provided -> err_multi_session path."""
    path = str(tmp_path / "multi_sessions.db")
    _build_db(
        path,
        sessions=[(1,), (2,)],
        requirements=[(1, "req 1", 1), (2, "req 2", 2)],
        acceptance_criteria=[
            (1, "gwt", "", "nonempty", "", 1, "slug"),
        ],
    )
    return path


@pytest.fixture
def single_gwt_db(tmp_path):
    """1 session, 1 req, 1 GWT criterion with all fields populated."""
    path = str(tmp_path / "single_gwt.db")
    _build_db(
        path,
        sessions=[(1,)],
        requirements=[(1, "only req", 1)],
        acceptance_criteria=[
            (1, "gwt", "given text", "when text", "then text", 1, "my-name"),
        ],
    )
    return path


@pytest.fixture
def all_other_format_db(tmp_path):
    """1 session, 1 req, all ACs in non-GWT format -> output_gwts == []."""
    path = str(tmp_path / "all_other.db")
    _build_db(
        path,
        sessions=[(1,)],
        requirements=[(1, "req", 1)],
        acceptance_criteria=[
            (1, "other", "", "nonempty", "", 1, None),
            (2, "other", "", "nonempty", "", 1, None),
        ],
    )
    return path


# ---------------------------------------------------------------------------
# Invariant assertion helpers
# ---------------------------------------------------------------------------

def _check_output_reqs_shape(result):
    reqs = result["requirements"]
    assert isinstance(reqs, list), "requirements must be a list"
    for req in reqs:
        assert "id" in req,   f"requirement missing 'id': {req}"
        assert "text" in req, f"requirement missing 'text': {req}"


def _check_output_gwts_shape(result):
    gwts = result["gwts"]
    assert isinstance(gwts, list), "gwts must be a list"
    required = {"criterion_id", "given", "when", "then", "parent_req"}
    for gwt in gwts:
        missing = required - gwt.keys()
        assert not missing, f"gwt missing fields {missing}: {gwt}"


def _check_criterion_id_prefix_ok(result):
    for gwt in result["gwts"]:
        cid = gwt["criterion_id"]
        assert isinstance(cid, str), f"criterion_id must be str, got {type(cid)}"
        assert cid.startswith(CW7_PREFIX), (
            f"criterion_id '{cid}' does not start with '{CW7_PREFIX}'"
        )
        assert CRITERION_ID_RE.match(cid), (
            f"criterion_id '{cid}' does not match pattern 'cw7-crit-N'"
        )


def _check_name_conditional(result):
    for gwt in result["gwts"]:
        when_nonempty = bool(gwt.get("when", ""))
        has_name = "name" in gwt
        if when_nonempty:
            assert has_name, (
                f"NameConditional: 'name' must be present when 'when_c' is non-empty: {gwt}"
            )
        else:
            assert not has_name, (
                f"NameConditional: 'name' must be absent when 'when_c' is empty: {gwt}"
            )


def _check_all_invariants(result):
    _check_output_reqs_shape(result)
    _check_output_gwts_shape(result)
    _check_criterion_id_prefix_ok(result)
    _check_name_conditional(result)


# ===========================================================================
# Trace-derived tests
# ===========================================================================

class TestTracesSuccessPath:
    """
    Covers TLC Traces 1-10 (all produce the same final state):
      output_reqs = [{id:1,text:'req 1'}, {id:2,text:'req 2'}]
      output_gwts = [
          {criterion_id:'cw7-crit-1', given:'', when:'nonempty', then:'', parent_req:1, name:'slug'},
          {criterion_id:'cw7-crit-3', given:'', when:'',         then:'', parent_req:1},
      ]
    """

    @pytest.mark.parametrize("trace_num", list(range(1, 11)))
    def test_trace_N_complete_final_state(self, extract, standard_db, trace_num):
        result = extract(standard_db)

        assert isinstance(result, dict), "extract must return a dict"
        assert "requirements" in result
        assert "gwts" in result

        assert len(result["requirements"]) == 2
        _check_output_reqs_shape(result)

        req_ids = {r["id"] for r in result["requirements"]}
        assert req_ids == {1, 2}

        assert len(result["gwts"]) == 2
        _check_output_gwts_shape(result)

        cids = {g["criterion_id"] for g in result["gwts"]}
        assert "cw7-crit-2" not in cids
        assert {"cw7-crit-1", "cw7-crit-3"} == cids

        _check_criterion_id_prefix_ok(result)
        _check_name_conditional(result)

        gwt1 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-1")
        assert gwt1["given"] == ""
        assert gwt1["when"] == "nonempty"
        assert gwt1["then"] == ""
        assert gwt1["parent_req"] == 1
        assert "name" in gwt1
        assert gwt1["name"] == "nonempty"

        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["given"] == ""
        assert gwt3["when"] == ""
        assert gwt3["then"] == ""
        assert gwt3["parent_req"] == 1
        assert "name" not in gwt3

        _check_all_invariants(result)

    def test_result_is_dict(self, extract, standard_db):
        result = extract(standard_db)
        assert isinstance(result, dict)

    def test_requirements_count_equals_num_reqs(self, extract, standard_db):
        result = extract(standard_db)
        assert len(result["requirements"]) == 2

    def test_gwts_count_equals_gwt_indices_cardinality(self, extract, standard_db):
        result = extract(standard_db)
        assert len(result["gwts"]) == 2

    def test_criterion_ids_are_cw7_crit_1_and_3(self, extract, standard_db):
        result = extract(standard_db)
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert cids == {"cw7-crit-1", "cw7-crit-3"}

    def test_gwt_row1_has_name(self, extract, standard_db):
        result = extract(standard_db)
        gwt1 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-1")
        assert gwt1["when"] == "nonempty"
        assert "name" in gwt1

    def test_gwt_row3_has_no_name(self, extract, standard_db):
        result = extract(standard_db)
        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["when"] == ""
        assert "name" not in gwt3

    def test_other_format_row_excluded(self, extract, standard_db):
        result = extract(standard_db)
        cids = [g["criterion_id"] for g in result["gwts"]]
        assert "cw7-crit-2" not in cids

    def test_parent_req_is_1_for_all_gwts(self, extract, standard_db):
        result = extract(standard_db)
        for gwt in result["gwts"]:
            assert gwt["parent_req"] == 1

    def test_criterion_ids_are_unique(self, extract, standard_db):
        result = extract(standard_db)
        cids = [g["criterion_id"] for g in result["gwts"]]
        assert len(cids) == len(set(cids))


# ===========================================================================
# Error-path tests
# ===========================================================================

class TestErrorPaths:

    def test_zero_sessions_raises_value_error(self, extract, zero_sessions_db):
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_zero_sessions_error_message_mentions_no_sessions(self, extract, zero_sessions_db):
        with pytest.raises(ValueError, match=re.compile("no sessions", re.IGNORECASE)):
            extract(zero_sessions_db)

    def test_multi_sessions_raises_value_error(self, extract, multi_sessions_db):
        with pytest.raises(ValueError):
            extract(multi_sessions_db)

    def test_multi_sessions_error_message_mentions_multiple_or_session_id(
        self, extract, multi_sessions_db
    ):
        with pytest.raises(ValueError) as exc_info:
            extract(multi_sessions_db)
        msg = str(exc_info.value).lower()
        assert "multiple sessions" in msg or "session_id" in msg

    def test_zero_sessions_produces_no_partial_output(self, extract, zero_sessions_db):
        raised = False
        try:
            extract(zero_sessions_db)
        except ValueError:
            raised = True
        assert raised, "extract must raise ValueError on zero sessions"

    def test_multi_sessions_produces_no_partial_output(self, extract, multi_sessions_db):
        raised = False
        try:
            extract(multi_sessions_db)
        except ValueError:
            raised = True
        assert raised, "extract must raise ValueError on multiple sessions"


# ===========================================================================
# GWTIndices invariant tests
# ===========================================================================

class TestGWTIndices:

    def test_mixed_formats_standard_topology(self, extract, standard_db):
        result = extract(standard_db)
        assert len(result["gwts"]) == 2
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert "cw7-crit-2" not in cids

    def test_all_gwt_topology(self, extract, tmp_path):
        path = str(tmp_path / "all_gwt.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "req", 1)],
            acceptance_criteria=[
                (1, "gwt", "g1", "w1", "t1", 1, "n1"),
                (2, "gwt", "g2", "w2", "t2", 1, "n2"),
                (3, "gwt", "g3", "w3", "t3", 1, "n3"),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 3

    def test_no_gwt_rows_gives_empty_gwts(self, extract, all_other_format_db):
        result = extract(all_other_format_db)
        assert result["gwts"] == []

    def test_single_gwt_among_others(self, extract, tmp_path):
        path = str(tmp_path / "one_gwt.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "req", 1)],
            acceptance_criteria=[
                (1, "other", "", "x", "", 1, None),
                (2, "gwt",   "", "y", "", 1, "name"),
                (3, "other", "", "z", "", 1, None),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 1
        assert result["gwts"][0]["criterion_id"] == "cw7-crit-2"


# ===========================================================================
# ValidPhase invariant tests
# ===========================================================================

class TestValidPhase:

    def test_success_implies_complete_phase(self, extract, standard_db):
        result = extract(standard_db)
        assert result is not None
        assert "requirements" in result and "gwts" in result

    def test_single_gwt_also_succeeds(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        assert result is not None

    def test_zero_sessions_raises_not_returns(self, extract, zero_sessions_db):
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_two_sessions_raises_not_returns(self, extract, multi_sessions_db):
        with pytest.raises(ValueError):
            extract(multi_sessions_db)


# ===========================================================================
# OutputReqsShape invariant tests
# ===========================================================================

class TestOutputReqsShape:

    def test_standard_topology(self, extract, standard_db):
        result = extract(standard_db)
        _check_output_reqs_shape(result)
        assert len(result["requirements"]) == 2

    def test_single_req_topology(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        _check_output_reqs_shape(result)
        assert len(result["requirements"]) == 1
        req = result["requirements"][0]
        assert req["id"] == 1
        assert req["text"] == "only req"

    def test_requirement_id_values_standard(self, extract, standard_db):
        result = extract(standard_db)
        ids = {r["id"] for r in result["requirements"]}
        assert ids == {1, 2}

    def test_requirement_text_values_standard(self, extract, standard_db):
        result = extract(standard_db)
        texts = {r["text"] for r in result["requirements"]}
        assert texts == {"req 1", "req 2"}


# ===========================================================================
# OutputGWTsShape invariant tests
# ===========================================================================

class TestOutputGWTsShape:

    def test_standard_topology(self, extract, standard_db):
        result = extract(standard_db)
        _check_output_gwts_shape(result)

    def test_single_gwt_topology(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        _check_output_gwts_shape(result)
        gwt = result["gwts"][0]
        assert gwt["given"] == "given text"
        assert gwt["when"]  == "when text"
        assert gwt["then"]  == "then text"

    def test_empty_gwts_list_is_valid(self, extract, all_other_format_db):
        result = extract(all_other_format_db)
        _check_output_gwts_shape(result)


# ===========================================================================
# CriterionIdPrefixOK invariant tests
# ===========================================================================

class TestCriterionIdPrefixOK:

    def test_standard_topology(self, extract, standard_db):
        result = extract(standard_db)
        _check_criterion_id_prefix_ok(result)

    def test_single_gwt_topology(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        _check_criterion_id_prefix_ok(result)
        assert result["gwts"][0]["criterion_id"] == "cw7-crit-1"

    def test_prefix_format_is_cw7_crit_N(self, extract, standard_db):
        result = extract(standard_db)
        for gwt in result["gwts"]:
            assert CRITERION_ID_RE.match(gwt["criterion_id"]), (
                f"'{gwt['criterion_id']}' does not match 'cw7-crit-N'"
            )

    def test_multiple_gwt_rows_all_prefixed(self, extract, tmp_path):
        path = str(tmp_path / "multi.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (i, "gwt", "", f"w{i}", "", 1, f"n{i}") for i in range(1, 6)
            ],
        )
        result = extract(path)
        _check_criterion_id_prefix_ok(result)


# ===========================================================================
# NameConditional invariant tests
# ===========================================================================

class TestNameConditional:

    def test_when_nonempty_implies_name_present(self, extract, standard_db):
        result = extract(standard_db)
        gwt1 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-1")
        assert gwt1["when"] != ""
        assert "name" in gwt1

    def test_when_empty_implies_name_absent(self, extract, standard_db):
        result = extract(standard_db)
        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["when"] == ""
        assert "name" not in gwt3

    def test_name_conditional_single_gwt(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        _check_name_conditional(result)

    def test_all_empty_when_no_names(self, extract, tmp_path):
        path = str(tmp_path / "empty_when.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (1, "gwt", "", "", "", 1, None),
                (2, "gwt", "", "", "", 1, None),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 2
        for gwt in result["gwts"]:
            assert gwt["when"] == ""
            assert "name" not in gwt

    def test_all_nonempty_when_all_have_names(self, extract, tmp_path):
        path = str(tmp_path / "nonempty_when.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (1, "gwt", "", "w1", "", 1, "slug1"),
                (2, "gwt", "", "w2", "", 1, "slug2"),
                (3, "gwt", "", "w3", "", 1, "slug3"),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 3
        for gwt in result["gwts"]:
            assert gwt["when"] != ""
            assert "name" in gwt


# ===========================================================================
# NoOutputOnError invariant tests
# ===========================================================================

class TestNoOutputOnError:

    def test_zero_sessions_raises(self, extract, zero_sessions_db):
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_multi_sessions_raises(self, extract, multi_sessions_db):
        with pytest.raises(ValueError):
            extract(multi_sessions_db)

    def test_zero_sessions_exception_not_dict(self, extract, zero_sessions_db):
        result_or_none = None
        try:
            result_or_none = extract(zero_sessions_db)
        except ValueError:
            pass
        assert result_or_none is None, (
            "extract returned a value instead of raising on zero sessions"
        )

    def test_multi_sessions_exception_not_dict(self, extract, multi_sessions_db):
        result_or_none = None
        try:
            result_or_none = extract(multi_sessions_db)
        except ValueError:
            pass
        assert result_or_none is None, (
            "extract returned a value instead of raising on multiple sessions"
        )


# ===========================================================================
# SuccessImpliesValidSession invariant tests
# ===========================================================================

class TestSuccessImpliesValidSession:

    def test_single_session_returns_result(self, extract, standard_db):
        result = extract(standard_db)
        assert "requirements" in result

    def test_single_session_single_gwt_returns_result(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        assert "requirements" in result

    def test_zero_sessions_does_not_complete(self, extract, zero_sessions_db):
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_two_sessions_does_not_complete(self, extract, multi_sessions_db):
        with pytest.raises(ValueError):
            extract(multi_sessions_db)


# ===========================================================================
# OnlyGWTFormatIncluded invariant tests
# ===========================================================================

class TestOnlyGWTFormatIncluded:

    def test_standard_topology_two_gwt_rows(self, extract, standard_db):
        result = extract(standard_db)
        assert len(result["gwts"]) == 2

    def test_all_other_format_zero_gwts(self, extract, all_other_format_db):
        result = extract(all_other_format_db)
        assert len(result["gwts"]) == 0

    def test_single_gwt_one_output(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        assert len(result["gwts"]) == 1

    def test_count_matches_gwt_format_rows(self, extract, tmp_path):
        path = str(tmp_path / "five_rows.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (1, "gwt",   "", "w1", "", 1, "n1"),
                (2, "other", "", "w2", "", 1, None),
                (3, "gwt",   "", "w3", "", 1, "n3"),
                (4, "other", "", "w4", "", 1, None),
                (5, "gwt",   "", "w5", "", 1, "n5"),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 3
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert cids == {"cw7-crit-1", "cw7-crit-3", "cw7-crit-5"}


# ===========================================================================
# Edge-case tests
# ===========================================================================

class TestEdgeCases:

    def test_nonexistent_db_path_raises(self, extract):
        with pytest.raises(Exception):
            extract("/nonexistent/path/to/missing.db")

    def test_empty_requirements_and_acs(self, extract, tmp_path):
        path = str(tmp_path / "empty.db")
        _build_db(path, sessions=[(1,)], requirements=[], acceptance_criteria=[])
        result = extract(path)
        assert result["requirements"] == []
        assert result["gwts"] == []

    def test_requirements_without_any_ac(self, extract, tmp_path):
        path = str(tmp_path / "no_ac.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "req no ac", 1), (2, "req no ac 2", 1)],
            acceptance_criteria=[],
        )
        result = extract(path)
        assert len(result["requirements"]) == 2
        assert result["gwts"] == []
        _check_output_reqs_shape(result)

    def test_large_number_of_gwt_criteria(self, extract, tmp_path):
        path = str(tmp_path / "large.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (i, "gwt", f"g{i}", f"w{i}", f"t{i}", 1, f"name{i}")
                for i in range(1, 21)
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 20
        _check_all_invariants(result)

    def test_criterion_ids_unique_under_multiple_rows(self, extract, tmp_path):
        path = str(tmp_path / "unique.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (1, "gwt", "", "w1", "", 1, "n1"),
                (2, "gwt", "", "w2", "", 1, "n2"),
                (3, "gwt", "", "",   "", 1, None),
            ],
        )
        result = extract(path)
        cids = [g["criterion_id"] for g in result["gwts"]]
        assert len(cids) == len(set(cids)), "duplicate criterion_ids found"

    def test_parent_req_links_to_valid_requirement(self, extract, standard_db):
        result = extract(standard_db)
        req_ids = {r["id"] for r in result["requirements"]}
        for gwt in result["gwts"]:
            assert gwt["parent_req"] in req_ids, (
                f"parent_req {gwt['parent_req']} not in requirement ids {req_ids}"
            )

    def test_interleaved_gwt_and_other_formats(self, extract, tmp_path):
        path = str(tmp_path / "interleaved.db")
        _build_db(
            path,
            sessions=[(1,)],
            requirements=[(1, "r", 1)],
            acceptance_criteria=[
                (1, "gwt",   "", "w1", "", 1, "n1"),
                (2, "other", "", "w2", "", 1, None),
                (3, "gwt",   "", "w3", "", 1, "n3"),
                (4, "other", "", "w4", "", 1, None),
                (5, "gwt",   "", "",   "", 1, None),
            ],
        )
        result = extract(path)
        assert len(result["gwts"]) == 3
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert cids == {"cw7-crit-1", "cw7-crit-3", "cw7-crit-5"}
        _check_all_invariants(result)
        gwt5 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-5")
        assert gwt5["when"] == ""
        assert "name" not in gwt5

    def test_all_invariants_on_single_gwt_db(self, extract, single_gwt_db):
        result = extract(single_gwt_db)
        _check_all_invariants(result)
        assert len(result["requirements"]) == 1
        assert len(result["gwts"]) == 1