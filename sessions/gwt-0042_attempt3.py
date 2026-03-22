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

from registry.dag import RegistryDag
from registry.types import Node, Edge, EdgeType, NodeKind

# ---------------------------------------------------------------------------
# Lazy import of extract to avoid collection-time ImportError
# ---------------------------------------------------------------------------

def _get_extract():
    from CW7Extract import extract
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
    id         INTEGER PRIMARY KEY,
    text       TEXT    NOT NULL,
    session_id INTEGER NOT NULL
);
CREATE TABLE acceptance_criteria (
    id             INTEGER PRIMARY KEY,
    format         TEXT    NOT NULL,
    given          TEXT    NOT NULL DEFAULT '',
    when_text      TEXT    NOT NULL DEFAULT '',
    then_text      TEXT    NOT NULL DEFAULT '',
    requirement_id INTEGER NOT NULL,
    name           TEXT
);
"""


def _build_db(
    path,
    sessions,
    requirements,
    acceptance_criteria,
):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript(_SCHEMA_DDL)
    cur.executemany("INSERT INTO sessions VALUES (?)", sessions)
    cur.executemany(
        "INSERT INTO requirements VALUES (?, ?, ?)", requirements
    )
    cur.executemany(
        "INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
        acceptance_criteria,
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
    Output GWT fields: criterion_id, given_c, when_c, then_c, parent_req[, name].
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
# (TLA+ invariants translated to Python predicates)
# ---------------------------------------------------------------------------

def _check_output_reqs_shape(result):
    """
    OutputReqsShape:
      phase = 'complete' =>
        /\\ Len(output_reqs) >= 0
        /\\ forall k : 'id' in DOMAIN req[k]  /\\  'text' in DOMAIN req[k]
    """
    reqs = result["requirements"]
    assert isinstance(reqs, list), "requirements must be a list"
    for req in reqs:
        assert "id" in req,   f"requirement missing 'id': {req}"
        assert "text" in req, f"requirement missing 'text': {req}"


def _check_output_gwts_shape(result):
    """
    OutputGWTsShape:
      forall k : 'criterion_id', 'given_c', 'when_c', 'then_c', 'parent_req' in DOMAIN gwt[k]

    Field names are given_c / when_c / then_c per the TLA+ OutputGWTsShape verifier.
    """
    gwts = result["gwts"]
    assert isinstance(gwts, list), "gwts must be a list"
    required = {"criterion_id", "given_c", "when_c", "then_c", "parent_req"}
    for gwt in gwts:
        missing = required - gwt.keys()
        assert not missing, f"gwt missing fields {missing}: {gwt}"


def _check_criterion_id_prefix_ok(result):
    """
    CriterionIdPrefixOK:
      forall k : output_gwts[k].criterion_id starts with CW7_PREFIX
    """
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
    """
    NameConditional:
      forall k : 'name' in DOMAIN output_gwts[k]  <=>  ~output_gwts[k].when_was_empty
      where when_was_empty == (when_c == '')

    Key must be ABSENT (not merely None) when when_c is empty.
    """
    for gwt in result["gwts"]:
        when_nonempty = bool(gwt.get("when_c", ""))
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
    """
    Invariants composite:
      ValidPhase /\\ OutputReqsShape /\\ OutputGWTsShape /\\ CriterionIdPrefixOK
      /\\ NameConditional /\\ NoOutputOnError /\\ SuccessImpliesValidSession
      /\\ ErrorOnZeroSessions /\\ ErrorOnMultiSessions /\\ OnlyGWTFormatIncluded
    (subset verifiable from the returned dict)
    """
    _check_output_reqs_shape(result)
    _check_output_gwts_shape(result)
    _check_criterion_id_prefix_ok(result)
    _check_name_conditional(result)


# ===========================================================================
# Trace-derived tests
# Traces 1-10 are structurally identical (same Init state, same final state).
# Represented as a single parametrized test plus detailed assertion methods.
# ===========================================================================

class TestTracesSuccessPath:
    """
    Covers TLC Traces 1-10 (all produce the same final state):
      output_reqs = [{id:1,text:'req 1'}, {id:2,text:'req 2'}]
      output_gwts = [
          {criterion_id:'cw7-crit-1', given_c:'', when_c:'nonempty', then_c:'', parent_req:1, name:'slug'},
          {criterion_id:'cw7-crit-3', given_c:'', when_c:'',         then_c:'', parent_req:1},
      ]
    """

    @pytest.mark.parametrize("trace_num", range(1, 11))
    def test_trace_N_complete_final_state(self, extract, standard_db, trace_num):
        """
        Parametrized over all 10 TLC traces.
        Each calls extract() on the identical DB and verifies the full
        final state plus every invariant.
        """
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
        assert gwt1["given_c"] == ""
        assert gwt1["when_c"] == "nonempty"
        assert gwt1["then_c"] == ""
        assert gwt1["parent_req"] == 1
        assert "name" in gwt1
        assert gwt1["name"] == "slug"

        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["given_c"] == ""
        assert gwt3["when_c"] == ""
        assert gwt3["then_c"] == ""
        assert gwt3["parent_req"] == 1
        assert "name" not in gwt3

        _check_all_invariants(result)

    def test_result_is_dict(self, extract, standard_db):
        """ValidPhase / complete: extract must return a dict on success."""
        result = extract(standard_db)
        assert isinstance(result, dict)

    def test_requirements_count_equals_num_reqs(self, extract, standard_db):
        """OutputReqsShape: Len(output_reqs) = NumReqs = 2."""
        result = extract(standard_db)
        assert len(result["requirements"]) == 2

    def test_gwts_count_equals_gwt_indices_cardinality(self, extract, standard_db):
        """OnlyGWTFormatIncluded: |{i: format[i]='gwt'}| = 2."""
        result = extract(standard_db)
        assert len(result["gwts"]) == 2

    def test_criterion_ids_are_cw7_crit_1_and_3(self, extract, standard_db):
        """GWTIndices contains rows 1 and 3 (format='gwt'); row 2 excluded."""
        result = extract(standard_db)
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert cids == {"cw7-crit-1", "cw7-crit-3"}

    def test_gwt_row1_has_name(self, extract, standard_db):
        """Row 1: when_c='nonempty' -> name present (NameConditional)."""
        result = extract(standard_db)
        gwt1 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-1")
        assert gwt1["when_c"] == "nonempty"
        assert "name" in gwt1

    def test_gwt_row3_has_no_name(self, extract, standard_db):
        """Row 3: when_c='' -> name absent (NameConditional)."""
        result = extract(standard_db)
        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["when_c"] == ""
        assert "name" not in gwt3

    def test_other_format_row_excluded(self, extract, standard_db):
        """Row 2 (format='other') does not appear in gwts."""
        result = extract(standard_db)
        cids = [g["criterion_id"] for g in result["gwts"]]
        assert "cw7-crit-2" not in cids

    def test_parent_req_is_1_for_all_gwts(self, extract, standard_db):
        """All gwts link back to the resolved session/requirement (id=1)."""
        result = extract(standard_db)
        for gwt in result["gwts"]:
            assert gwt["parent_req"] == 1

    def test_criterion_ids_are_unique(self, extract, standard_db):
        """No duplicate criterion_id values in the output."""
        result = extract(standard_db)
        cids = [g["criterion_id"] for g in result["gwts"]]
        assert len(cids) == len(set(cids))


# ===========================================================================
# Error-path tests
# ErrorOnZeroSessions, ErrorOnMultiSessions, NoOutputOnError
# ===========================================================================

class TestErrorPaths:
    """
    TLA+ error branches:
      err_no_session    -> raised_error = 'ValueError: no sessions found'
      err_multi_session -> raised_error = 'ValueError: multiple sessions, specify session_id'
    """

    def test_zero_sessions_raises_value_error(self, extract, zero_sessions_db):
        """ErrorOnZeroSessions: SessionCount=0, no session_id -> must raise."""
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_zero_sessions_error_message_mentions_no_sessions(self, extract, zero_sessions_db):
        """Raised message matches TLA+ raised_error 'no sessions found'."""
        with pytest.raises(ValueError, match=re.compile("no sessions", re.IGNORECASE)):
            extract(zero_sessions_db)

    def test_multi_sessions_raises_value_error(self, extract, multi_sessions_db):
        """ErrorOnMultiSessions: SessionCount=2, no session_id -> must raise."""
        with pytest.raises(ValueError):
            extract(multi_sessions_db)

    def test_multi_sessions_error_message_mentions_multiple_or_session_id(
        self, extract, multi_sessions_db
    ):
        """Raised message matches TLA+ raised_error about multiple sessions / session_id."""
        with pytest.raises(ValueError) as exc_info:
            extract(multi_sessions_db)
        msg = str(exc_info.value).lower()
        assert "multiple sessions" in msg or "session_id" in msg

    def test_zero_sessions_produces_no_partial_output(self, extract, zero_sessions_db):
        """
        NoOutputOnError: error path must not return a partial dict;
        the function must raise, never return silently.
        """
        raised = False
        try:
            extract(zero_sessions_db)
        except ValueError:
            raised = True
        assert raised, "extract must raise ValueError on zero sessions"

    def test_multi_sessions_produces_no_partial_output(self, extract, multi_sessions_db):
        """NoOutputOnError: error path must raise, never return silently."""
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
    """
    GWTIndices = {i in 1..NumAcRows : AcFormats[i] = 'gwt'}
    Only rows whose format equals GWT_FORMAT appear in the output.
    Exercised across >= 2 topologies.
    """

    def test_mixed_formats_standard_topology(self, extract, standard_db):
        """3 rows, 2 GWT -> 2 gwts; row 2 (other) excluded."""
        result = extract(standard_db)
        assert len(result["gwts"]) == 2
        cids = {g["criterion_id"] for g in result["gwts"]}
        assert "cw7-crit-2" not in cids

    def test_all_gwt_topology(self, extract, tmp_path):
        """All rows GWT -> all appear."""
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
        """0 GWT rows -> gwts = []."""
        result = extract(all_other_format_db)
        assert result["gwts"] == []

    def test_single_gwt_among_others(self, extract, tmp_path):
        """1 GWT among many 'other' rows -> exactly 1 gwt."""
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
    """
    ValidPhase: phase in {start, query_reqs, query_gwts, complete,
                          err_no_session, err_multi_session}
    Verified indirectly: success -> complete (returns dict),
                         errors  -> raise (no invalid phase leaks out).
    """

    def test_success_implies_complete_phase(self, extract, standard_db):
        """SuccessImpliesValidSession + ValidPhase: 1 session -> result returned."""
        result = extract(standard_db)
        assert result is not None
        assert "requirements" in result and "gwts" in result

    def test_single_gwt_also_succeeds(self, extract, single_gwt_db):
        """ValidPhase: single-GWT topology terminates in complete phase."""
        result = extract(single_gwt_db)
        assert result is not None

    def test_zero_sessions_raises_not_returns(self, extract, zero_sessions_db):
        """ValidPhase: err_no_session phase must surface as ValueError."""
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_two_sessions_raises_not_returns(self, extract, multi_sessions_db):
        """ValidPhase: err_multi_session phase must surface as ValueError."""
        with pytest.raises(ValueError):
            extract(multi_sessions_db)


# ===========================================================================
# OutputReqsShape invariant tests
# ===========================================================================

class TestOutputReqsShape:
    """
    OutputReqsShape: on success, forall k : 'id' in req[k] /\\ 'text' in req[k]
    """

    def test_standard_topology(self, extract, standard_db):
        """OutputReqsShape holds for standard 2-requirement topology."""
        result = extract(standard_db)
        _check_output_reqs_shape(result)
        assert len(result["requirements"]) == 2

    def test_single_req_topology(self, extract, single_gwt_db):
        """OutputReqsShape holds for single-requirement topology."""
        result = extract(single_gwt_db)
        _check_output_reqs_shape(result)
        assert len(result["requirements"]) == 1
        req = result["requirements"][0]
        assert req["id"] == 1
        assert req["text"] == "only req"

    def test_requirement_id_values_standard(self, extract, standard_db):
        """ids are exactly {1, 2} for the standard fixture."""
        result = extract(standard_db)
        ids = {r["id"] for r in result["requirements"]}
        assert ids == {1, 2}

    def test_requirement_text_values_standard(self, extract, standard_db):
        """text values are exactly {'req 1', 'req 2'} for the standard fixture."""
        result = extract(standard_db)
        texts = {r["text"] for r in result["requirements"]}
        assert texts == {"req 1", "req 2"}


# ===========================================================================
# OutputGWTsShape invariant tests
# ===========================================================================

class TestOutputGWTsShape:
    """
    OutputGWTsShape: on success, forall k :
      {criterion_id, given_c, when_c, then_c, parent_req} subset DOMAIN gwt[k]
    Field names given_c / when_c / then_c per the TLA+ spec.
    """

    def test_standard_topology(self, extract, standard_db):
        """OutputGWTsShape holds for the standard 3-row fixture."""
        result = extract(standard_db)
        _check_output_gwts_shape(result)

    def test_single_gwt_topology(self, extract, single_gwt_db):
        """OutputGWTsShape holds and field values are correct for single-GWT fixture."""
        result = extract(single_gwt_db)
        _check_output_gwts_shape(result)
        gwt = result["gwts"][0]
        assert gwt["given_c"] == "given text"
        assert gwt["when_c"]  == "when text"
        assert gwt["then_c"]  == "then text"

    def test_empty_gwts_list_is_valid(self, extract, all_other_format_db):
        """Empty gwts still satisfies the shape invariant (vacuously true)."""
        result = extract(all_other_format_db)
        _check_output_gwts_shape(result)


# ===========================================================================
# CriterionIdPrefixOK invariant tests
# ===========================================================================

class TestCriterionIdPrefixOK:
    """
    CriterionIdPrefixOK: forall k : gwt[k].criterion_id starts with 'cw7-crit-'
    """

    def test_standard_topology(self, extract, standard_db):
        """CriterionIdPrefixOK holds for the standard 2-GWT topology."""
        result = extract(standard_db)
        _check_criterion_id_prefix_ok(result)

    def test_single_gwt_topology(self, extract, single_gwt_db):
        """CriterionIdPrefixOK holds and criterion_id is 'cw7-crit-1'."""
        result = extract(single_gwt_db)
        _check_criterion_id_prefix_ok(result)
        assert result["gwts"][0]["criterion_id"] == "cw7-crit-1"

    def test_prefix_format_is_cw7_crit_N(self, extract, standard_db):
        """criterion_id matches regex 'cw7-crit-\\d+'."""
        result = extract(standard_db)
        for gwt in result["gwts"]:
            assert CRITERION_ID_RE.match(gwt["criterion_id"]), (
                f"'{gwt['criterion_id']}' does not match 'cw7-crit-N'"
            )

    def test_multiple_gwt_rows_all_prefixed(self, extract, tmp_path):
        """CriterionIdPrefixOK holds across 5 GWT rows."""
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
    """
    NameConditional: 'name' in DOMAIN gwt[k]  <=>  ~gwt[k].when_was_empty
    where when_was_empty == (when_c == '')
    """

    def test_when_nonempty_implies_name_present(self, extract, standard_db):
        """NameConditional: when_c non-empty -> 'name' key present in gwt."""
        result = extract(standard_db)
        gwt1 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-1")
        assert gwt1["when_c"] != ""
        assert "name" in gwt1

    def test_when_empty_implies_name_absent(self, extract, standard_db):
        """NameConditional: when_c empty -> 'name' key absent from gwt."""
        result = extract(standard_db)
        gwt3 = next(g for g in result["gwts"] if g["criterion_id"] == "cw7-crit-3")
        assert gwt3["when_c"] == ""
        assert "name" not in gwt3

    def test_name_conditional_single_gwt(self, extract, single_gwt_db):
        """NameConditional holds for single-GWT fixture (when_c non-empty)."""
        result = extract(single_gwt_db)
        _check_name_conditional(result)

    def test_all_empty_when_no_names(self, extract, tmp_path):
        """All GWT rows have empty when_text -> no gwt has 'name'."""
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
            assert gwt["when_c"] == ""
            assert "name" not in gwt

    def test_all_nonempty_when_all_have_names(self, extract, tmp_path):
        """All GWT rows have non-empty when_text -> every gwt has 'name'."""
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
            assert gwt["when_c"] != ""
            assert "name" in gwt


# ===========================================================================
# NoOutputOnError invariant tests
# ===========================================================================

class TestNoOutputOnError:
    """
    NoOutputOnError: phase in {err_no_session, err_multi_session} ->
                     output_reqs = [] /\\ output_gwts = []
    Verified by confirming extract raises rather than returning partial data.
    """

    def test_zero_sessions_raises(self, extract, zero_sessions_db):
        """NoOutputOnError: zero sessions must raise, not return."""
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_multi_sessions_raises(self, extract, multi_sessions_db):
        """NoOutputOnError: multiple sessions must raise, not return."""
        with pytest.raises(ValueError):
            extract(multi_sessions_db)

    def test_zero_sessions_exception_not_dict(self, extract, zero_sessions_db):
        """extract must not return a dict on error; it must raise."""
        result_or_none = None
        try:
            result_or_none = extract(zero_sessions_db)
        except ValueError:
            pass
        assert result_or_none is None, (
            "extract returned a value instead of raising on zero sessions"
        )

    def test_multi_sessions_exception_not_dict(self, extract, multi_sessions_db):
        """extract must not return a dict on multiple-sessions error; it must raise."""
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
    """
    SuccessImpliesValidSession: phase = 'complete' => SessionCount = 1
    """

    def test_single_session_returns_result(self, extract, standard_db):
        """SuccessImpliesValidSession: 1 session -> complete phase, result dict returned."""
        result = extract(standard_db)
        assert "requirements" in result

    def test_single_session_single_gwt_returns_result(self, extract, single_gwt_db):
        """SuccessImpliesValidSession: 1 session, 1 GWT -> complete phase."""
        result = extract(single_gwt_db)
        assert "requirements" in result

    def test_zero_sessions_does_not_complete(self, extract, zero_sessions_db):
        """SuccessImpliesValidSession contrapositive: 0 sessions -> not complete."""
        with pytest.raises(ValueError):
            extract(zero_sessions_db)

    def test_two_sessions_does_not_complete(self, extract, multi_sessions_db):
        """SuccessImpliesValidSession contrapositive: 2 sessions -> not complete."""
        with pytest.raises(ValueError):
            extract(multi_sessions_db)


# ===========================================================================
# OnlyGWTFormatIncluded invariant tests
# ===========================================================================

class TestOnlyGWTFormatIncluded:
    """
    OnlyGWTFormatIncluded:
      Len(output_gwts) = |{i : AcFormats[i] = 'gwt'}|
    """

    def test_standard_topology_two_gwt_rows(self, extract, standard_db):
        """3 rows, 2 GWT -> 2 gwts."""
        result = extract(standard_db)
        assert len(result["gwts"]) == 2

    def test_all_other_format_zero_gwts(self, extract, all_other_format_db):
        """0 GWT rows -> 0 gwts."""
        result = extract(all_other_format_db)
        assert len(result["gwts"]) == 0

    def test_single_gwt_one_output(self, extract, single_gwt_db):
        """1 GWT row -> 1 gwt."""
        result = extract(single_gwt_db)
        assert len(result["gwts"]) == 1

    def test_count_matches_gwt_format_rows(self, extract, tmp_path):
        """5 rows, 3 GWT -> exactly 3 gwts."""
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
        """extract raises for a non-existent path (no valid schema present)."""
        with pytest.raises(Exception):
            extract("/nonexistent/path/to/missing.db")

    def test_empty_requirements_and_acs(self, extract, tmp_path):
        """1 session, 0 reqs, 0 ACs -> empty lists, no crash."""
        path = str(tmp_path / "empty.db")
        _build_db(path, sessions=[(1,)], requirements=[], acceptance_criteria=[])
        result = extract(path)
        assert result["requirements"] == []
        assert result["gwts"] == []

    def test_requirements_without_any_ac(self, extract, tmp_path):
        """Requirements exist but no ACs -> gwts = []."""
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
        """20 GWT rows -> all 20 in output; all invariants hold."""
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
        """All criterion_ids in the output are distinct."""
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
        """Every gwt.parent_req refers to a requirement id that exists in the output."""
        result = extract(standard_db)
        req_ids = {r["id"] for r in result["requirements"]}
        for gwt in result["gwts"]:
            assert gwt["parent_req"] in req_ids, (
                f"parent_req {gwt['parent_req']} not in requirement ids {req_ids}"
            )

    def test_interleaved_gwt_and_other_formats(self, extract, tmp_path):
        """
        Alternating gwt/other rows -> only gwt rows appear;
        criterion_id numbers match AC row ids in the DB.
        """
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
        assert gwt5["when_c"] == ""
        assert "name" not in gwt5

    def test_all_invariants_on_single_gwt_db(self, extract, single_gwt_db):
        """Full invariant suite on the minimal single-GWT topology."""
        result = extract(single_gwt_db)
        _check_all_invariants(result)
        assert len(result["requirements"]) == 1
        assert len(result["gwts"]) == 1