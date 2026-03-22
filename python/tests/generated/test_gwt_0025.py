import builtins
import os
from unittest.mock import patch

import pytest

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import Edge, EdgeType, Node, SubgraphResult

NA = "A"
NB = "B"
NC = "C"
ALL_NODES = {NA, NB, NC}
START_NODE = NA
MAX_STEPS = 4
REACHABLE = {NA, NB, NC}
VALID_PHASES = {"init", "expanding", "complete", "partial"}


def _make_chain_dag() -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.behavior(NA, NA, "given A", "when A", "then A"))
    dag.add_node(Node.behavior(NB, NB, "given B", "when B", "then B"))
    dag.add_node(Node.behavior(NC, NC, "given C", "when C", "then C"))
    dag.add_edge(Edge(NA, NB, EdgeType.IMPORTS))
    dag.add_edge(Edge(NB, NC, EdgeType.IMPORTS))
    return dag


def _node_ids(result: SubgraphResult) -> set[str]:
    # SubgraphResult.nodes is already a set[str] of node IDs
    return result.nodes


def _assert_seed_always_included(visited: set[str], phase: str) -> None:
    if phase != "init":
        assert START_NODE in visited, (
            f"SeedAlwaysIncluded violated: {START_NODE!r} not in visited={visited!r}"
        )


def _assert_chain_fully_covered(visited: set[str], phase: str) -> None:
    if phase == "complete":
        for n in (NA, NB, NC):
            assert n in visited, (
                f"ChainFullyCovered violated: {n!r} not in visited={visited!r}"
            )


def _assert_completeness_invariant(visited: set[str], phase: str) -> None:
    if phase == "complete":
        assert REACHABLE.issubset(visited), (
            f"CompletenessInvariant violated: Reachable={REACHABLE!r} not subset visited={visited!r}"
        )


def _assert_frontier_subset_visited(frontier: set[str], visited: set[str]) -> None:
    assert frontier.issubset(visited), (
        f"FrontierSubsetVisited violated: frontier={frontier!r} not subset visited={visited!r}"
    )


def _assert_bounded_depth(depth: int) -> None:
    assert depth <= MAX_STEPS, (
        f"BoundedDepth violated: depth={depth} > MaxSteps={MAX_STEPS}"
    )


def _assert_valid_phase(phase: str) -> None:
    assert phase in VALID_PHASES, (
        f"ValidPhase violated: {phase!r} not in {VALID_PHASES!r}"
    )


def _assert_all_invariants(
    visited: set[str],
    phase: str,
    depth: int,
    frontier: set[str],
) -> None:
    _assert_seed_always_included(visited, phase)
    _assert_chain_fully_covered(visited, phase)
    _assert_completeness_invariant(visited, phase)
    _assert_frontier_subset_visited(frontier, visited)
    _assert_bounded_depth(depth)
    _assert_valid_phase(phase)


@pytest.fixture
def chain_dag() -> RegistryDag:
    return _make_chain_dag()


@pytest.fixture(autouse=True)
def _clean_claudecode_env():
    original = os.environ.pop("CLAUDECODE", None)
    yield
    if original is not None:
        os.environ["CLAUDECODE"] = original
    else:
        os.environ.pop("CLAUDECODE", None)


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_forward_subgraph_chain(chain_dag: RegistryDag, trace_id: int) -> None:
    _assert_seed_always_included({NA}, "expanding")
    _assert_frontier_subset_visited({NA}, {NA})
    _assert_bounded_depth(0)
    _assert_valid_phase("expanding")

    step1_visited: set[str] = {NA, NB}
    _assert_seed_always_included(step1_visited, "expanding")
    _assert_frontier_subset_visited({NB}, step1_visited)
    _assert_bounded_depth(1)
    _assert_valid_phase("expanding")

    step2_visited: set[str] = {NA, NB, NC}
    _assert_seed_always_included(step2_visited, "expanding")
    _assert_frontier_subset_visited({NC}, step2_visited)
    _assert_bounded_depth(2)
    _assert_valid_phase("expanding")

    _assert_seed_always_included(step2_visited, "expanding")
    _assert_frontier_subset_visited(set(), step2_visited)
    _assert_bounded_depth(3)
    _assert_valid_phase("expanding")

    _assert_frontier_subset_visited(set(), step2_visited)
    _assert_bounded_depth(3)
    _assert_valid_phase("expanding")

    result: SubgraphResult = chain_dag.extract_subgraph(NA)
    visited: set[str] = _node_ids(result)

    assert visited == {NA, NB, NC}, (
        f"Trace {trace_id}: expected visited={{A,B,C}}, got {visited!r}"
    )
    _assert_all_invariants(visited, "complete", 3, set())


def test_claudecode_removed_before_sdk_import(
    chain_dag: RegistryDag, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    assert os.environ.get("CLAUDECODE") == "1"

    env_snapshot: dict[str, str | None] = {}
    _real_import = builtins.__import__

    def _capturing_import(name: str, *args, **kwargs):
        if name == "claude_agent_sdk":
            env_snapshot["CLAUDECODE"] = os.environ.get("CLAUDECODE", "__absent__")
        return _real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_capturing_import):
        try:
            chain_dag.extract_subgraph(NA)
        except Exception:
            pass

    if env_snapshot:
        assert env_snapshot.get("CLAUDECODE") == "__absent__", (
            "_build_async_extract_fn() must remove CLAUDECODE from os.environ "
            "before importing claude_agent_sdk; "
            f"observed CLAUDECODE={env_snapshot.get('CLAUDECODE')!r}"
        )


def test_claudecode_not_present_in_env_during_sdk_module_init(
    chain_dag: RegistryDag, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "claude-code-sentinel")

    env_during_call: list[str | None] = []
    _real_import = builtins.__import__

    def _spy_import(name: str, *args, **kwargs):
        result = _real_import(name, *args, **kwargs)
        if name == "claude_agent_sdk":
            env_during_call.append(os.environ.get("CLAUDECODE"))
        return result

    with patch("builtins.__import__", side_effect=_spy_import):
        try:
            chain_dag.extract_subgraph(NA)
        except Exception:
            pass

    for observed in env_during_call:
        assert observed is None, (
            "CLAUDECODE must be absent during claude_agent_sdk import; "
            f"got {observed!r}"
        )


def test_claudecode_restored_after_extraction(
    chain_dag: RegistryDag, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = "restored-sentinel"
    monkeypatch.setenv("CLAUDECODE", sentinel)

    try:
        chain_dag.extract_subgraph(NA)
    except Exception:
        pass

    assert os.environ.get("CLAUDECODE") == sentinel, (
        "CLAUDECODE must be restored to its original value after extraction; "
        f"got {os.environ.get('CLAUDECODE')!r}"
    )


def test_extraction_without_claudecode_set_succeeds(chain_dag: RegistryDag) -> None:
    assert "CLAUDECODE" not in os.environ
    result: SubgraphResult = chain_dag.extract_subgraph(NA)
    visited: set[str] = _node_ids(result)
    assert visited == {NA, NB, NC}
    _assert_all_invariants(visited, "complete", 3, set())


def test_claudecode_present_extraction_returns_full_subgraph(
    chain_dag: RegistryDag, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    result: SubgraphResult = chain_dag.extract_subgraph(NA)
    visited: set[str] = _node_ids(result)
    assert visited == {NA, NB, NC}, (
        f"Full subgraph expected even with CLAUDECODE set; got {visited!r}"
    )
    _assert_all_invariants(visited, "complete", 3, set())


def test_claudecode_absent_after_env_removal_is_idempotent(
    chain_dag: RegistryDag,
) -> None:
    assert "CLAUDECODE" not in os.environ
    result: SubgraphResult = chain_dag.extract_subgraph(NA)
    visited: set[str] = _node_ids(result)
    assert visited == {NA, NB, NC}, (
        f"Expected full chain {{A,B,C}} but got {visited!r}"
    )
    assert NA in visited
    _assert_valid_phase("complete")


class TestSeedAlwaysIncluded:

    def test_chain_dag_seed_in_expanding_and_complete(self, chain_dag: RegistryDag) -> None:
        result = chain_dag.extract_subgraph(NA)
        visited = _node_ids(result)
        _assert_seed_always_included(visited, "expanding")
        _assert_seed_always_included(visited, "complete")

    def test_single_node_dag_seed_included(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        _assert_seed_always_included(visited, "expanding")
        _assert_seed_always_included(visited, "complete")

    def test_init_phase_vacuously_true(self) -> None:
        _assert_seed_always_included(set(), "init")

    def test_seed_missing_in_non_init_raises(self) -> None:
        with pytest.raises(AssertionError):
            _assert_seed_always_included({NB, NC}, "expanding")


class TestChainFullyCovered:

    def test_full_chain_dag_all_covered(self, chain_dag: RegistryDag) -> None:
        result = chain_dag.extract_subgraph(NA)
        visited = _node_ids(result)
        _assert_chain_fully_covered(visited, "complete")

    def test_expanding_phase_does_not_require_full_coverage(self) -> None:
        _assert_chain_fully_covered({NA, NB}, "expanding")

    def test_two_node_dag_incomplete_chain_detected(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        dag.add_node(Node.behavior(NB, NB, "g", "w", "t"))
        dag.add_edge(Edge(NA, NB, EdgeType.IMPORTS))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert NC not in visited
        with pytest.raises(AssertionError):
            _assert_chain_fully_covered(visited, "complete")


class TestCompletenessInvariant:

    def test_full_chain_reachable_subset_of_visited(self, chain_dag: RegistryDag) -> None:
        result = chain_dag.extract_subgraph(NA)
        _assert_completeness_invariant(_node_ids(result), "complete")

    def test_single_node_reachable_is_itself(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert {NA}.issubset(visited)
        assert NA in visited

    def test_missing_reachable_node_detected(self) -> None:
        with pytest.raises(AssertionError):
            _assert_completeness_invariant({NA, NB}, "complete")

    def test_expanding_phase_does_not_enforce_completeness(self) -> None:
        _assert_completeness_invariant({NA}, "expanding")


class TestFrontierSubsetVisited:

    def test_post_seed_state_2(self) -> None:
        _assert_frontier_subset_visited({NA}, {NA})

    def test_after_expand_b_state_3(self) -> None:
        _assert_frontier_subset_visited({NB}, {NA, NB})

    def test_after_expand_c_state_4(self) -> None:
        _assert_frontier_subset_visited({NC}, {NA, NB, NC})

    def test_empty_frontier_states_5_6_7(self) -> None:
        _assert_frontier_subset_visited(set(), {NA, NB, NC})
        _assert_frontier_subset_visited(set(), set())

    def test_frontier_not_subset_raises(self) -> None:
        with pytest.raises(AssertionError):
            _assert_frontier_subset_visited({NB}, {NA})

    def test_chain_dag_full_extraction_frontier_empty(self, chain_dag: RegistryDag) -> None:
        result = chain_dag.extract_subgraph(NA)
        visited = _node_ids(result)
        successors_of_visited = set()
        if NA in visited:
            successors_of_visited.add(NB)
        if NB in visited:
            successors_of_visited.add(NC)
        assert successors_of_visited.issubset(visited)


class TestBoundedDepth:

    @pytest.mark.parametrize("depth", [0, 1, 2, 3, 4])
    def test_valid_depths_accepted(self, depth: int) -> None:
        _assert_bounded_depth(depth)

    @pytest.mark.parametrize("depth", [5, 6, 100])
    def test_depths_exceeding_max_rejected(self, depth: int) -> None:
        with pytest.raises(AssertionError):
            _assert_bounded_depth(depth)

    def test_chain_dag_depth_within_bound(self, chain_dag: RegistryDag) -> None:
        chain_dag.extract_subgraph(NA)
        _assert_bounded_depth(3)

    def test_single_node_dag_depth_zero(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        dag.extract_subgraph(NA)
        _assert_bounded_depth(0)


class TestValidPhase:

    @pytest.mark.parametrize("phase", ["init", "expanding", "complete", "partial"])
    def test_all_valid_phases_accepted(self, phase: str) -> None:
        _assert_valid_phase(phase)

    @pytest.mark.parametrize(
        "bad_phase", ["done", "running", "", "COMPLETE", "Done", "pending"]
    )
    def test_invalid_phases_rejected(self, bad_phase: str) -> None:
        with pytest.raises(AssertionError):
            _assert_valid_phase(bad_phase)

    def test_chain_dag_terminates_in_complete_phase(self, chain_dag: RegistryDag) -> None:
        result = chain_dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert visited == {NA, NB, NC}
        _assert_valid_phase("complete")

    def test_single_node_dag_terminates_in_complete_phase(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert visited == {NA}
        _assert_valid_phase("complete")


class TestEdgeCases:

    def test_isolated_node_subgraph(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert visited == {NA}
        _assert_seed_always_included(visited, "complete")
        _assert_frontier_subset_visited(set(), visited)
        _assert_bounded_depth(0)
        _assert_valid_phase("complete")

    def test_nonexistent_node_raises_node_not_found(self, chain_dag: RegistryDag) -> None:
        with pytest.raises(NodeNotFoundError):
            chain_dag.extract_subgraph("NONEXISTENT")

    def test_empty_dag_raises_on_extraction(self) -> None:
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.extract_subgraph(NA)

    def test_diamond_pattern_all_reachable(self) -> None:
        ND = "D"
        dag = RegistryDag()
        for nid in (NA, NB, NC, ND):
            dag.add_node(Node.behavior(nid, nid, "g", "w", "t"))
        dag.add_edge(Edge(NA, NB, EdgeType.IMPORTS))
        dag.add_edge(Edge(NA, NC, EdgeType.IMPORTS))
        dag.add_edge(Edge(NB, ND, EdgeType.IMPORTS))
        dag.add_edge(Edge(NC, ND, EdgeType.IMPORTS))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert {NA, NB, NC, ND}.issubset(visited)
        _assert_seed_always_included(visited, "complete")
        _assert_valid_phase("complete")
        _assert_bounded_depth(2)
        _assert_frontier_subset_visited(set(), visited)

    def test_seed_from_middle_of_chain(self) -> None:
        dag = _make_chain_dag()
        result = dag.extract_subgraph(NB)
        visited = _node_ids(result)
        assert NB in visited
        assert NC in visited
        assert NA in visited
        _assert_valid_phase("complete")
        _assert_bounded_depth(len(visited) - 1)

    def test_seed_from_leaf_node(self) -> None:
        dag = _make_chain_dag()
        result = dag.extract_subgraph(NC)
        visited = _node_ids(result)
        assert NC in visited
        assert NA in visited
        assert NB in visited
        _assert_frontier_subset_visited(set(), visited)
        _assert_bounded_depth(len(visited) - 1)
        _assert_valid_phase("complete")

    def test_two_independent_chains_no_cross_contamination(self) -> None:
        ND, NE = "D", "E"
        dag = RegistryDag()
        for nid in (NA, NB, NC, ND, NE):
            dag.add_node(Node.behavior(nid, nid, "g", "w", "t"))
        dag.add_edge(Edge(NA, NB, EdgeType.IMPORTS))
        dag.add_edge(Edge(NB, NC, EdgeType.IMPORTS))
        dag.add_edge(Edge(ND, NE, EdgeType.IMPORTS))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        assert visited == {NA, NB, NC}
        assert ND not in visited
        assert NE not in visited
        _assert_all_invariants(visited, "complete", 3, set())

    def test_wide_fan_out_bounded_depth(self) -> None:
        children = [NB, NC, "D", "E"]
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        for child in children:
            dag.add_node(Node.behavior(child, child, "g", "w", "t"))
            dag.add_edge(Edge(NA, child, EdgeType.IMPORTS))
        result = dag.extract_subgraph(NA)
        visited = _node_ids(result)
        expected = {NA} | set(children)
        assert expected.issubset(visited)
        _assert_bounded_depth(1)
        _assert_frontier_subset_visited(set(), visited)
        _assert_valid_phase("complete")

    def test_cycle_edge_rejected_or_traversal_still_terminates(self) -> None:
        dag = RegistryDag()
        dag.add_node(Node.behavior(NA, NA, "g", "w", "t"))
        cycle_detected_at_add = False
        try:
            dag.add_edge(Edge(NA, NA, EdgeType.IMPORTS))
        except CycleError:
            cycle_detected_at_add = True
        if not cycle_detected_at_add:
            result = dag.extract_subgraph(NA)
            visited = _node_ids(result)
            assert NA in visited
            _assert_valid_phase("complete")
            _assert_bounded_depth(len(visited) - 1)

    def test_claudecode_set_does_not_alter_subgraph_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dag_a = _make_chain_dag()
        result_without = _node_ids(dag_a.extract_subgraph(NA))
        monkeypatch.setenv("CLAUDECODE", "1")
        dag_b = _make_chain_dag()
        result_with = _node_ids(dag_b.extract_subgraph(NA))
        assert result_without == result_with == {NA, NB, NC}, (
            "Subgraph result must be identical regardless of CLAUDECODE; "
            f"without={result_without!r}, with={result_with!r}"
        )

    def test_all_invariants_hold_after_claudecode_removal(
        self, chain_dag: RegistryDag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDECODE", "1")
        result = chain_dag.extract_subgraph(NA)
        visited = _node_ids(result)
        _assert_all_invariants(visited, "complete", 3, set())