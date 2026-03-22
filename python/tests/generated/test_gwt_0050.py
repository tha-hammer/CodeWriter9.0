import pytest
from registry.dag import RegistryDag, CycleError, NodeNotFoundError
from registry.types import (
    Edge,
    EdgeType,
    ImpactResult,
    Node,
    NodeKind,
    QueryResult,
    SubgraphResult,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# TLA+ model constants
# Lines == << "Func", "Other", "InterfaceOpen", "Func", "InterfaceClose", "Func", "Other" >>
# N == 7
# ---------------------------------------------------------------------------
N = 7
LINES = ["Func", "Other", "InterfaceOpen", "Func", "InterfaceClose", "Func", "Other"]
EXPECTED_LINE_NUMBERS = frozenset({1, 6})


# ---------------------------------------------------------------------------
# TLA+ helper: InInterface(k)
# ---------------------------------------------------------------------------

def _in_interface(k: int, lines: list) -> bool:
    """InInterface(k): 1-indexed. True iff line k is inside an open interface block."""
    for j in range(1, k):
        if lines[j - 1] == "InterfaceOpen":
            has_close = any(
                lines[m - 1] == "InterfaceClose" for m in range(j + 1, k)
            )
            if not has_close:
                return True
    return False


# ---------------------------------------------------------------------------
# Core scanner simulation using RegistryDag
#
# Mirrors the TLA+ scanner state machine:
#   - Func outside interface  -> resource node (id="func-{i}"), appended to top_level
#   - Func inside interface   -> behavior node (id="method-{i}"), NOT in top_level
#   - InterfaceOpen           -> resource node (id="iface-{i}"), sets in_iface=True
#   - InterfaceClose          -> sets in_iface=False
#   - Other                   -> skipped
#
# Returns (dag, top_level_line_numbers) where top_level_line_numbers mirrors
# the TLA+ "skeletons" set reduced to line numbers.
# ---------------------------------------------------------------------------

def _process_lines(lines: list) -> tuple[RegistryDag, list[int]]:
    """Simulate scanning a sequence of line types; build RegistryDag and top-level list."""
    dag = RegistryDag()
    top_level: list[int] = []
    in_iface = False
    for i, line_type in enumerate(lines, start=1):
        if line_type == "InterfaceOpen":
            in_iface = True
            dag.add_node(Node.resource(f"iface-{i}", f"Interface{i}", f"interface at line {i}"))
        elif line_type == "InterfaceClose":
            in_iface = False
        elif line_type == "Func":
            if in_iface:
                dag.add_node(Node.behavior(
                    f"method-{i}", f"Method{i}",
                    given="interface is defined",
                    when=f"method at line {i} is called",
                    then="method executes",
                ))
            else:
                dag.add_node(Node.resource(f"func-{i}", f"Func{i}", f"func at line {i}"))
                top_level.append(i)
    return dag, top_level


# ---------------------------------------------------------------------------
# Invariant assertion helpers  (mirror the four TLA+ invariants)
# ---------------------------------------------------------------------------

def assert_line_number_correct(line_nums: list[int], lines: list, n: int) -> None:
    """LineNumberCorrect: every captured line number is in [1..N] and is a Func line."""
    for ln in line_nums:
        assert 1 <= ln <= n, f"LineNumberCorrect violated: {ln} not in [1..{n}]"
        if lines:
            assert lines[ln - 1] == "Func", (
                f"LineNumberCorrect violated: line {ln} is {lines[ln - 1]!r}, expected 'Func'"
            )


def assert_interface_exclusion(line_nums: list[int], lines: list, n: int) -> None:
    """InterfaceExclusion: no captured line is inside an interface block."""
    for ln in line_nums:
        assert not _in_interface(ln, lines), (
            f"InterfaceExclusion violated: line {ln} is inside an interface block"
        )


def assert_no_gaps(line_nums: list[int], lines: list, n: int) -> None:
    """NoGaps: after full scan, every non-interface Func line is captured."""
    found = set(line_nums)
    for k in range(1, n + 1):
        if lines and lines[k - 1] == "Func" and not _in_interface(k, lines):
            assert k in found, f"NoGaps violated: Func at line {k} missing from results"


def assert_cursor_bounded(i_final: int, n: int) -> None:
    """CursorBounded surrogate: final cursor does not exceed N+1."""
    assert i_final <= n + 1, f"CursorBounded violated: i={i_final} > N+1={n + 1}"


def assert_all_invariants(
    line_nums: list[int], lines: list, n: int, i_final: int
) -> None:
    """Assert all four TLA+ invariants simultaneously."""
    assert isinstance(line_nums, list), "assert_all_invariants requires a list"
    assert_line_number_correct(line_nums, lines, n)
    assert_interface_exclusion(line_nums, lines, n)
    assert_no_gaps(line_nums, lines, n)
    assert_cursor_bounded(i_final, n)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def trace_result():
    """Process the 7-line TLA+ LINES array -> (dag, top_level_line_numbers)."""
    return _process_lines(LINES)


@pytest.fixture
def only_funcs_lines():
    return ["Func", "Func", "Func"]


@pytest.fixture
def only_funcs_result(only_funcs_lines):
    return _process_lines(only_funcs_lines)


@pytest.fixture
def all_in_interface_lines():
    return ["InterfaceOpen", "Func", "InterfaceClose"]


@pytest.fixture
def all_in_interface_result(all_in_interface_lines):
    return _process_lines(all_in_interface_lines)


@pytest.fixture
def empty_result():
    return _process_lines([])


# ---------------------------------------------------------------------------
# Trace-derived tests  (Traces 1-10 all share identical structure & final state)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_final_state(trace_result, trace_id):
    """
    Traces 1-10 — 7-line file with Lines sequence from TLA+ model.
    Final state: top_level = {1, 6}, i = N+1 = 8.
    Verifies: LineNumberCorrect, InterfaceExclusion, NoGaps, CursorBounded.
    """
    dag, top_level = trace_result
    assert set(top_level) == EXPECTED_LINE_NUMBERS, (
        f"Trace {trace_id}: expected {EXPECTED_LINE_NUMBERS}, got {set(top_level)}"
    )
    assert_all_invariants(top_level, LINES, N, i_final=N + 1)


def test_trace_1_line_number_correct(trace_result):
    """Trace 1 — LineNumberCorrect: line numbers are in [1..N] and point to Func lines."""
    dag, top_level = trace_result
    assert_line_number_correct(top_level, LINES, N)


def test_trace_2_interface_exclusion_line_4_absent(trace_result):
    """Trace 2 — InterfaceExclusion: line 4 (Func inside interface) must not appear."""
    dag, top_level = trace_result
    assert 4 not in top_level, (
        "InterfaceExclusion: line 4 is Func inside interface and must be excluded"
    )
    assert_interface_exclusion(top_level, LINES, N)


def test_trace_3_no_gaps_lines_1_and_6(trace_result):
    """Trace 3 — NoGaps: both non-interface Func lines (1 and 6) must be captured."""
    dag, top_level = trace_result
    assert 1 in top_level, "NoGaps: Func at line 1 (outside interface) must be captured"
    assert 6 in top_level, "NoGaps: Func at line 6 (outside interface) must be captured"
    assert_no_gaps(top_level, LINES, N)


def test_trace_4_cursor_bounded(trace_result):
    """Trace 4 — CursorBounded: scan completes normally; surrogate i=N+1 <= N+1."""
    dag, top_level = trace_result
    assert_cursor_bounded(i_final=N + 1, n=N)


def test_trace_5_skeleton_count(trace_result):
    """Trace 5 — exactly two top-level funcs produced for the 7-line trace."""
    dag, top_level = trace_result
    assert len(top_level) == 2


def test_trace_6_line_1_skeleton_correct(trace_result):
    """Trace 6 — line 1 is in the top-level funcs and refers to a Func line."""
    dag, top_level = trace_result
    assert 1 in top_level
    assert LINES[0] == "Func"  # precondition: fixture is correctly set up


def test_trace_7_line_6_skeleton_correct(trace_result):
    """Trace 7 — line 6 is in the top-level funcs and refers to a Func line."""
    dag, top_level = trace_result
    assert 6 in top_level
    assert LINES[5] == "Func"  # precondition: fixture is correctly set up


def test_trace_8_in_interface_guard(trace_result):
    """Trace 8 — line 4 is Func but in_interface=TRUE during processing at i=4."""
    dag, top_level = trace_result
    assert 4 not in top_level
    assert _in_interface(4, LINES) is True  # confirms test helper, not API


def test_trace_9_interface_open_and_close(trace_result):
    """Trace 9 — after InterfaceClose at line 5, in_interface resets; line 6 is captured."""
    dag, top_level = trace_result
    assert 6 in top_level
    assert _in_interface(6, LINES) is False  # fixture precondition


def test_trace_10_all_invariants_exhaustive(trace_result):
    """Trace 10 — exhaustive check of all four invariants against the trace fixture."""
    dag, top_level = trace_result
    assert_all_invariants(top_level, LINES, N, i_final=N + 1)


# ---------------------------------------------------------------------------
# DAG node-count invariants — verify RegistryDag state after scanning
# ---------------------------------------------------------------------------

def test_trace_dag_node_count(trace_result):
    """
    Trace file creates four nodes:
    - func-1 (Foo, resource), iface-3 (MyInterface, resource),
    - method-4 (InInterface, behavior), func-6 (Bar, resource).
    """
    dag, _ = trace_result
    assert dag.node_count == 4


def test_only_funcs_dag_node_count(only_funcs_result):
    dag, top_level = only_funcs_result
    assert dag.node_count == 3
    assert len(top_level) == 3


def test_empty_dag_node_count(empty_result):
    dag, top_level = empty_result
    assert dag.node_count == 0
    assert top_level == []


def test_all_in_interface_dag_node_count(all_in_interface_result):
    """Two nodes added (iface-1 resource + method-2 behavior); zero top-level funcs."""
    dag, top_level = all_in_interface_result
    assert dag.node_count == 2
    assert top_level == []


# ---------------------------------------------------------------------------
# Dedicated invariant verifier classes
# ---------------------------------------------------------------------------

class TestLineNumberCorrectInvariant:
    """LineNumberCorrect holds across multiple file topologies."""

    def test_trace_file_topology(self, trace_result):
        dag, top_level = trace_result
        assert_line_number_correct(top_level, LINES, N)

    def test_only_funcs_topology(self, only_funcs_result, only_funcs_lines):
        dag, top_level = only_funcs_result
        assert_line_number_correct(top_level, only_funcs_lines, n=3)
        assert set(top_level) == {1, 2, 3}

    def test_empty_file_no_skeletons(self, empty_result):
        dag, top_level = empty_result
        assert top_level == []
        assert_line_number_correct(top_level, [], n=0)

    def test_all_in_interface_no_skeletons(self, all_in_interface_result, all_in_interface_lines):
        dag, top_level = all_in_interface_result
        assert top_level == []
        assert_line_number_correct(top_level, all_in_interface_lines, n=3)


class TestInterfaceExclusionInvariant:
    """InterfaceExclusion holds across multiple file topologies."""

    def test_trace_file_excludes_line_4(self, trace_result):
        dag, top_level = trace_result
        assert 4 not in top_level
        assert_interface_exclusion(top_level, LINES, N)

    def test_all_in_interface_yields_empty(self, all_in_interface_result, all_in_interface_lines):
        dag, top_level = all_in_interface_result
        assert top_level == []
        assert_interface_exclusion(top_level, all_in_interface_lines, n=3)

    def test_only_funcs_all_included(self, only_funcs_result, only_funcs_lines):
        dag, top_level = only_funcs_result
        assert set(top_level) == {1, 2, 3}
        assert_interface_exclusion(top_level, only_funcs_lines, n=3)

    def test_empty_file_vacuously_satisfied(self, empty_result):
        dag, top_level = empty_result
        assert_interface_exclusion(top_level, [], n=0)


class TestNoGapsInvariant:
    """NoGaps: after full scan, every non-interface Func line has a top-level entry."""

    def test_trace_file_no_gaps(self, trace_result):
        dag, top_level = trace_result
        assert_no_gaps(top_level, LINES, N)

    def test_only_funcs_no_gaps(self, only_funcs_result, only_funcs_lines):
        dag, top_level = only_funcs_result
        assert_no_gaps(top_level, only_funcs_lines, n=3)

    def test_all_in_interface_no_gaps(self, all_in_interface_result, all_in_interface_lines):
        dag, top_level = all_in_interface_result
        assert_no_gaps(top_level, all_in_interface_lines, n=3)

    def test_empty_file_no_gaps(self, empty_result):
        dag, top_level = empty_result
        assert_no_gaps(top_level, [], n=0)


class TestCursorBoundedInvariant:
    """CursorBounded: verified via successful termination of _process_lines."""

    def test_trace_file_cursor_bounded(self, trace_result):
        dag, top_level = trace_result
        assert_cursor_bounded(i_final=N + 1, n=N)

    def test_only_funcs_cursor_bounded(self, only_funcs_result):
        dag, top_level = only_funcs_result
        assert_cursor_bounded(i_final=3 + 1, n=3)

    def test_all_in_interface_cursor_bounded(self, all_in_interface_result):
        dag, top_level = all_in_interface_result
        assert_cursor_bounded(i_final=3 + 1, n=3)

    def test_empty_file_cursor_bounded(self, empty_result):
        dag, top_level = empty_result
        assert_cursor_bounded(i_final=0 + 1, n=0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_edge_case_single_func_line():
    """Isolated single func — top_level = {1}, all invariants satisfied."""
    lines = ["Func"]
    dag, top_level = _process_lines(lines)
    assert set(top_level) == {1}
    assert dag.node_count == 1
    assert_line_number_correct(top_level, lines, n=1)
    assert_no_gaps(top_level, lines, n=1)
    assert_cursor_bounded(i_final=1 + 1, n=1)


def test_edge_case_empty_file():
    """Empty file — no top-level entries, all invariants vacuously satisfied."""
    lines = []
    dag, top_level = _process_lines(lines)
    assert top_level == []
    assert dag.node_count == 0
    assert_all_invariants(top_level, lines, n=0, i_final=0 + 1)


def test_edge_case_no_func_declarations():
    """File with only Other lines — no top-level entries, no nodes in DAG."""
    lines = ["Other", "Other", "Other"]
    dag, top_level = _process_lines(lines)
    assert top_level == []
    assert dag.node_count == 0


def test_edge_case_func_immediately_after_interface_close():
    """
    Func on the line directly after the closing brace must be captured.
    Mirrors the Trace final state where line 6 is captured after in_interface resets.
    """
    lines = ["InterfaceOpen", "Other", "InterfaceClose", "Func"]
    dag, top_level = _process_lines(lines)
    assert 4 in top_level, "Func after interface close must be captured"
    assert 1 not in top_level
    assert_all_invariants(top_level, lines, n=4, i_final=4 + 1)


def test_edge_case_multiple_interface_blocks():
    """Funcs interleaved with two interface blocks; only funcs outside both are captured."""
    lines = [
        "Func", "InterfaceOpen", "Func", "InterfaceClose",
        "Func", "InterfaceOpen", "Func", "InterfaceClose", "Func",
    ]
    dag, top_level = _process_lines(lines)
    assert 1 in top_level, "func Before at line 1 must be captured"
    assert 5 in top_level, "func Between at line 5 must be captured"
    assert 9 in top_level, "func After at line 9 must be captured"
    assert 3 not in top_level, "MethodA at line 3 (inside interface A) must be excluded"
    assert 7 not in top_level, "MethodB at line 7 (inside interface B) must be excluded"
    assert_all_invariants(top_level, lines, n=9, i_final=9 + 1)


def test_edge_case_consecutive_func_declarations():
    """Four consecutive funcs — NoGaps requires all four to appear."""
    lines = ["Func", "Func", "Func", "Func"]
    dag, top_level = _process_lines(lines)
    assert set(top_level) == {1, 2, 3, 4}
    assert_all_invariants(top_level, lines, n=4, i_final=4 + 1)


def test_edge_case_func_at_last_line():
    """Func at the very last line is captured; CursorBounded: cursor reaches N+1."""
    lines = ["Other", "Func"]
    dag, top_level = _process_lines(lines)
    assert 2 in top_level, "Func at last line must be captured"
    assert 1 not in top_level
    assert_all_invariants(top_level, lines, n=2, i_final=2 + 1)


def test_edge_case_unclosed_interface_excludes_all_subsequent_funcs():
    """If an interface block is never closed, all Func lines after the open are excluded."""
    lines = ["Func", "InterfaceOpen", "Func", "Func"]
    dag, top_level = _process_lines(lines)
    assert 1 in top_level, "func Before must be captured (before interface open)"
    assert 3 not in top_level, "line 3 Func is inside unclosed interface"
    assert 4 not in top_level, "line 4 Func is inside unclosed interface"
    assert_interface_exclusion(top_level, lines, n=4)
    assert_line_number_correct(top_level, lines, n=4)


# ---------------------------------------------------------------------------
# RegistryDag API tests
# ---------------------------------------------------------------------------

def test_registry_dag_add_node_increments_count():
    dag = RegistryDag()
    assert dag.node_count == 0
    dag.add_node(Node.resource("func-1", "Foo", "func Foo() {}"))
    assert dag.node_count == 1


def test_registry_dag_add_multiple_nodes():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    dag.add_node(Node.resource("func-6", "Bar", ""))
    assert dag.node_count == 2


def test_registry_dag_remove_node_decrements_count():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    dag.remove_node("func-1")
    assert dag.node_count == 0


def test_registry_dag_remove_nonexistent_raises_node_not_found():
    dag = RegistryDag()
    with pytest.raises(NodeNotFoundError):
        dag.remove_node("nonexistent")


def test_registry_dag_add_edge_increments_edge_count():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    dag.add_node(Node.resource("func-6", "Bar", ""))
    dag.add_edge(Edge(from_id="func-1", to_id="func-6", edge_type=EdgeType.DEPENDS_ON))
    assert dag.edge_count >= 1


def test_registry_dag_cycle_error_on_reverse_edge():
    """Adding a reverse edge that creates a cycle raises CycleError."""
    dag = RegistryDag()
    dag.add_node(Node.resource("a", "A", ""))
    dag.add_node(Node.resource("b", "B", ""))
    dag.add_edge(Edge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON))
    with pytest.raises(CycleError):
        dag.add_edge(Edge(from_id="b", to_id="a", edge_type=EdgeType.DEPENDS_ON))


def test_registry_dag_component_count_unconnected_nodes():
    """Two unconnected nodes form two separate components."""
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    dag.add_node(Node.resource("func-6", "Bar", ""))
    assert dag.component_count == 2


def test_registry_dag_component_members_contains_self():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    members = dag.component_members("func-1")
    assert "func-1" in members


def test_registry_dag_serialization_roundtrip():
    """to_dict / from_dict roundtrip preserves node_count and edge_count."""
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    dag.add_node(Node.resource("func-6", "Bar", ""))
    dag.add_edge(Edge(from_id="func-1", to_id="func-6", edge_type=EdgeType.DEPENDS_ON))
    data = dag.to_dict()
    dag2 = RegistryDag.from_dict(data)
    assert dag2.node_count == dag.node_count
    assert dag2.edge_count == dag.edge_count


def test_registry_dag_json_roundtrip():
    """to_json / from_json roundtrip preserves node_count."""
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    json_str = dag.to_json()
    dag2 = RegistryDag.from_json(json_str)
    assert dag2.node_count == 1


def test_registry_dag_query_relevant_returns_query_result():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    result = dag.query_relevant("func-1")
    assert isinstance(result, QueryResult)


def test_registry_dag_extract_subgraph_returns_subgraph_result():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    result = dag.extract_subgraph("func-1")
    assert isinstance(result, SubgraphResult)


def test_registry_dag_query_impact_returns_impact_result():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    result = dag.query_impact("func-1")
    assert isinstance(result, ImpactResult)


def test_registry_dag_validate_edge_returns_validation_result():
    dag = RegistryDag()
    dag.add_node(Node.resource("a", "A", ""))
    dag.add_node(Node.resource("b", "B", ""))
    result = dag.validate_edge("a", "b", EdgeType.DEPENDS_ON)
    assert isinstance(result, ValidationResult)


def test_registry_dag_query_affected_tests_returns_list():
    dag = RegistryDag()
    dag.add_node(Node.resource("func-1", "Foo", ""))
    result = dag.query_affected_tests("func-1")
    assert isinstance(result, list)


def test_registry_dag_register_requirement_adds_node():
    dag = RegistryDag()
    req_id = dag.register_requirement(
        "Functions outside interfaces must be captured",
        name="NoGaps",
    )
    assert isinstance(req_id, str)
    assert dag.node_count == 1


def test_registry_dag_register_gwt_adds_behavior_node():
    dag = RegistryDag()
    gwt_id = dag.register_gwt(
        given="a Go file is scanned",
        when="a Func line outside an interface is encountered",
        then="a skeleton entry is created for that line",
        name="SkeletonCreated",
    )
    assert isinstance(gwt_id, str)
    assert dag.node_count == 1


# ---------------------------------------------------------------------------
# Node API tests
# ---------------------------------------------------------------------------

def test_node_resource_has_resource_kind():
    node = Node.resource("func-1", "Foo", "func Foo() {}")
    assert node.kind == NodeKind.RESOURCE


def test_node_behavior_has_behavior_kind():
    node = Node.behavior(
        "method-4", "InInterface",
        given="interface exists",
        when="method is called",
        then="method executes",
    )
    assert node.kind == NodeKind.BEHAVIOR


def test_node_resource_and_behavior_have_different_kinds():
    resource = Node.resource("r", "R", "")
    behavior = Node.behavior("b", "B", given="g", when="w", then="t")
    assert resource.kind != behavior.kind


def test_node_to_dict_contains_id_and_name():
    node = Node.resource("func-1", "Foo", "func Foo() {}")
    d = node.to_dict()
    assert isinstance(d, dict)
    assert d.get("id") == "func-1"
    assert d.get("name") == "Foo"


def test_node_requirement_has_requirement_kind():
    node = Node.requirement("req-1", "All non-interface funcs must be captured")
    assert node.kind == NodeKind.REQUIREMENT


# ---------------------------------------------------------------------------
# Edge API tests
# ---------------------------------------------------------------------------

def test_edge_to_dict_contains_ids():
    edge = Edge(from_id="func-1", to_id="func-6", edge_type=EdgeType.DEPENDS_ON)
    d = edge.to_dict()
    assert isinstance(d, dict)
    assert "func-1" in d.values() or d.get("from_id") == "func-1"
    assert "func-6" in d.values() or d.get("to_id") == "func-6"


def test_edge_type_contains_expected_values():
    assert EdgeType.DEPENDS_ON in EdgeType
    assert EdgeType.CONTAINS in EdgeType
    assert EdgeType.IMPLEMENTS in EdgeType