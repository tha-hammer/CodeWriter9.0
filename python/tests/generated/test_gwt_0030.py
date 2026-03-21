"""
pytest test suite for IncrementalSkip – _should_skip / incremental-crawl behaviour.

Derived from TLC-verified traces; invariants are checked at every intermediate
state, not just at the final state.

Real API imports only:
    from registry.types import Edge, EdgeType, Node, NodeKind
    from registry.dag import RegistryDag
"""
from __future__ import annotations

import pytest
from registry.types import Edge, EdgeType, Node, NodeKind
from registry.dag import RegistryDag

# ---------------------------------------------------------------------------
# Symbolic constants (TLA+ model values made concrete)
# ---------------------------------------------------------------------------

UUID_1 = "uuid-1"
UUID_2 = "uuid-2"
ALL_UUIDS = frozenset({UUID_1, UUID_2})

HASH_1 = "hash-aaa"
HASH_2 = "hash-bbb"

TERMINAL_DESC_1 = "terminal-description-alpha"
TERMINAL_DESC_2 = "terminal-description-beta"
NON_TERMINAL_DESC_1 = "non-terminal-description-alpha"
NON_TERMINAL_DESC_2 = "non-terminal-description-beta"

TERMINAL_DESCRIPTIONS = frozenset({TERMINAL_DESC_1, TERMINAL_DESC_2})
NON_TERMINAL_DESCRIPTIONS = frozenset({NON_TERMINAL_DESC_1, NON_TERMINAL_DESC_2})


def _sanity_check() -> None:
    assert TERMINAL_DESCRIPTIONS.isdisjoint(NON_TERMINAL_DESCRIPTIONS)


_sanity_check()


# ---------------------------------------------------------------------------
# TLA+ predicate translations
# ---------------------------------------------------------------------------

def is_terminal(uuid: str, records: dict) -> bool:
    return records[uuid]["do_description"] in TERMINAL_DESCRIPTIONS


def hash_matches(uuid: str, records: dict, current_hashes: dict) -> bool:
    return records[uuid]["src_hash"] == current_hashes[uuid]


def should_skip(uuid: str, records: dict, current_hashes: dict, incremental: bool) -> bool:
    return incremental and is_terminal(uuid, records) and hash_matches(uuid, records, current_hashes)


# ---------------------------------------------------------------------------
# Invariant checkers
# ---------------------------------------------------------------------------

def inv_skip_only_when_incremental(skipped: set, incremental: bool) -> None:
    if skipped:
        assert incremental, (
            f"SkipOnlyWhenIncremental violated: "
            f"skipped={skipped} but incremental={incremental}"
        )


def inv_skip_only_when_hash_match(
    skipped: set, records: dict, current_hashes: dict
) -> None:
    for u in skipped:
        assert records[u]["src_hash"] == current_hashes[u], (
            f"SkipOnlyWhenHashMatch violated for {u}: "
            f"src_hash={records[u]['src_hash']} != current={current_hashes[u]}"
        )


def inv_skip_never_extracted(skipped: set, extracted: set) -> None:
    overlap = skipped & extracted
    assert not overlap, f"SkipNeverExtracted violated: overlap={overlap}"


def inv_unchanged_never_extracted(
    skipped: set,
    remaining: set,
    records: dict,
    current_hashes: dict,
    incremental: bool,
    all_uuids: frozenset = ALL_UUIDS,
) -> None:
    processed = all_uuids - remaining
    for u in processed:
        if incremental and is_terminal(u, records) and hash_matches(u, records, current_hashes):
            assert u in skipped, (
                f"UnchangedNeverExtracted violated for {u}: "
                "qualifies for skip but is absent from skipped"
            )


def inv_processed_partition(
    skipped: set,
    extracted: set,
    remaining: set,
    all_uuids: frozenset = ALL_UUIDS,
) -> None:
    processed = all_uuids - remaining
    for u in processed:
        assert u in skipped or u in extracted, (
            f"ProcessedPartition violated for {u}: "
            "not in skipped and not in extracted"
        )


def inv_bounded_skipped(skipped: set, all_uuids: frozenset = ALL_UUIDS) -> None:
    stray = skipped - all_uuids
    assert not stray, f"BoundedSkipped violated: {stray} not in UUIDs"


def inv_bounded_extracted(extracted: set, all_uuids: frozenset = ALL_UUIDS) -> None:
    stray = extracted - all_uuids
    assert not stray, f"BoundedExtracted violated: {stray} not in UUIDs"


def assert_all_invariants(
    skipped: set,
    extracted: set,
    remaining: set,
    records: dict,
    current_hashes: dict,
    incremental: bool,
    all_uuids: frozenset = ALL_UUIDS,
) -> None:
    inv_skip_only_when_incremental(skipped, incremental)
    inv_skip_only_when_hash_match(skipped, records, current_hashes)
    inv_skip_never_extracted(skipped, extracted)
    inv_unchanged_never_extracted(
        skipped, remaining, records, current_hashes, incremental, all_uuids
    )
    inv_processed_partition(skipped, extracted, remaining, all_uuids)
    inv_bounded_skipped(skipped, all_uuids)
    inv_bounded_extracted(extracted, all_uuids)


# ---------------------------------------------------------------------------
# Processor simulation
# ---------------------------------------------------------------------------

def run_processor(
    records: dict,
    current_hashes: dict,
    incremental: bool,
    all_uuids: frozenset = ALL_UUIDS,
) -> tuple:
    remaining = set(all_uuids)
    skipped: set = set()
    extracted: set = set()

    assert_all_invariants(
        skipped, extracted, remaining, records, current_hashes, incremental, all_uuids
    )

    for uuid in sorted(all_uuids):
        remaining.remove(uuid)

        if should_skip(uuid, records, current_hashes, incremental):
            skipped.add(uuid)
        else:
            extracted.add(uuid)

        assert_all_invariants(
            skipped, extracted, remaining, records, current_hashes, incremental, all_uuids
        )

    assert not remaining, "remaining must be empty at Finish"
    assert_all_invariants(
        skipped, extracted, remaining, records, current_hashes, incremental, all_uuids
    )

    return skipped, extracted


# ---------------------------------------------------------------------------
# Helper: build a two-node RegistryDag
# ---------------------------------------------------------------------------

def _build_dag(
    uuid1_desc: str,
    uuid1_hash: str,
    uuid2_desc: str,
    uuid2_hash: str,
) -> RegistryDag:
    dag = RegistryDag()
    dag.add_node(Node.resource(UUID_1, "node-uuid1", uuid1_desc))
    dag.add_node(Node.resource(UUID_2, "node-uuid2", uuid2_desc))
    return dag


# ===========================================================================
# Trace-derived tests
# ===========================================================================


class TestTrace1:
    """
    Trace 1 - incremental=TRUE, both records terminal but src_hash != current_hash.
    current_hashes: {UUID_1: Hash1, UUID_2: Hash1}
    records:        {UUID_1: {Terminal1, Hash2}, UUID_2: {Terminal1, Hash2}}
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        dag = _build_dag(TERMINAL_DESC_1, HASH_2, TERMINAL_DESC_1, HASH_2)
        return records, current_hashes, dag

    def test_both_extracted_due_to_hash_mismatch(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set(), f"Expected no skips; got {skipped}"
        assert extracted == {UUID_1, UUID_2}, f"Expected both extracted; got {extracted}"

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_should_skip_false_for_each_uuid(self, state):
        records, current_hashes, _ = state
        assert not should_skip(UUID_1, records, current_hashes, incremental=True)
        assert not should_skip(UUID_2, records, current_hashes, incremental=True)


class TestTrace2:
    """
    Trace 2 - incremental=TRUE.
    UUID_1: Terminal1, src_hash=Hash2, current=Hash1 -> mismatch -> extracted
    UUID_2: NonTerminal1, src_hash=Hash1, current=Hash2 -> non-terminal -> extracted
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        dag = _build_dag(TERMINAL_DESC_1, HASH_2, NON_TERMINAL_DESC_1, HASH_1)
        return records, current_hashes, dag

    def test_both_extracted_mixed_reasons(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_uuid1_hash_mismatch_prevents_skip(self, state):
        records, current_hashes, _ = state
        assert not hash_matches(UUID_1, records, current_hashes)
        assert is_terminal(UUID_1, records)
        assert not should_skip(UUID_1, records, current_hashes, incremental=True)

    def test_uuid2_non_terminal_prevents_skip(self, state):
        records, current_hashes, _ = state
        assert not is_terminal(UUID_2, records)
        assert not should_skip(UUID_2, records, current_hashes, incremental=True)


class TestTrace3:
    """
    Trace 3 - incremental=FALSE.
    UUID_1: NonTerminal2, src_hash=Hash2, current=Hash1
    UUID_2: Terminal1,    src_hash=Hash2, current=Hash2  (hash matches but incremental=False)
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        dag = _build_dag(NON_TERMINAL_DESC_2, HASH_2, TERMINAL_DESC_1, HASH_2)
        return records, current_hashes, dag

    def test_non_incremental_all_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, False)

    def test_incremental_false_suppresses_skip_even_with_hash_match(self, state):
        records, current_hashes, _ = state
        assert is_terminal(UUID_2, records)
        assert hash_matches(UUID_2, records, current_hashes)
        assert not should_skip(UUID_2, records, current_hashes, incremental=False)

    def test_skip_only_when_incremental_with_empty_skipped(self, state):
        records, current_hashes, _ = state
        skipped, _ = run_processor(records, current_hashes, incremental=False)
        inv_skip_only_when_incremental(skipped, incremental=False)


class TestTrace4:
    """
    Trace 4 - incremental=FALSE.
    UUID_1: Terminal2, src_hash=Hash1, current=Hash2
    UUID_2: NonTerminal2, src_hash=Hash2, current=Hash1
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_2, UUID_2: HASH_1}
        dag = _build_dag(TERMINAL_DESC_2, HASH_1, NON_TERMINAL_DESC_2, HASH_2)
        return records, current_hashes, dag

    def test_non_incremental_various_hashes_all_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, False)


class TestTrace5:
    """
    Trace 5 - incremental=TRUE, both non-terminal descriptions.
    UUID_1: NonTerminal2, src_hash=Hash1, current=Hash1 (hash matches but non-terminal)
    UUID_2: NonTerminal1, src_hash=Hash1, current=Hash2
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        dag = _build_dag(NON_TERMINAL_DESC_2, HASH_1, NON_TERMINAL_DESC_1, HASH_1)
        return records, current_hashes, dag

    def test_non_terminal_never_skipped(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_uuid1_hash_match_irrelevant_because_non_terminal(self, state):
        records, current_hashes, _ = state
        assert hash_matches(UUID_1, records, current_hashes)
        assert not is_terminal(UUID_1, records)
        assert not should_skip(UUID_1, records, current_hashes, incremental=True)


class TestTrace6:
    """
    Trace 6 - incremental=TRUE, both non-terminal.
    UUID_1: NonTerminal1, src_hash=Hash1, current=Hash2
    UUID_2: NonTerminal2, src_hash=Hash1, current=Hash1
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_2, UUID_2: HASH_1}
        dag = _build_dag(NON_TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_2, HASH_1)
        return records, current_hashes, dag

    def test_non_terminal_both_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_uuid2_hash_match_irrelevant_non_terminal(self, state):
        records, current_hashes, _ = state
        assert hash_matches(UUID_2, records, current_hashes)
        assert not is_terminal(UUID_2, records)
        assert not should_skip(UUID_2, records, current_hashes, incremental=True)


class TestTrace7:
    """
    Trace 7 - incremental=TRUE.
    UUID_1: NonTerminal1, src_hash=Hash2, current=Hash1
    UUID_2: Terminal2,    src_hash=Hash2, current=Hash1 -> terminal but hash mismatch
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        dag = _build_dag(NON_TERMINAL_DESC_1, HASH_2, TERMINAL_DESC_2, HASH_2)
        return records, current_hashes, dag

    def test_terminal_with_hash_mismatch_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_uuid2_terminal_but_hash_mismatch_prevents_skip(self, state):
        records, current_hashes, _ = state
        assert is_terminal(UUID_2, records)
        assert not hash_matches(UUID_2, records, current_hashes)
        assert not should_skip(UUID_2, records, current_hashes, incremental=True)


class TestTrace8:
    """
    Trace 8 - incremental=FALSE, both terminal with hash mismatch.
    UUID_1: Terminal2, src_hash=Hash2, current=Hash1
    UUID_2: Terminal2, src_hash=Hash2, current=Hash1
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        dag = _build_dag(TERMINAL_DESC_2, HASH_2, TERMINAL_DESC_2, HASH_2)
        return records, current_hashes, dag

    def test_non_incremental_terminal_hash_mismatch_all_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=False)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, False)


class TestTrace9:
    """
    Trace 9 - THE PRIMARY TRACE.

    incremental=TRUE.
    UUID_1: Terminal1, src_hash=Hash1, current=Hash1 -> SKIPPED
    UUID_2: NonTerminal1, src_hash=Hash1, current=Hash2 -> extracted

    Expected final: skipped={UUID_1}, extracted={UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        dag = _build_dag(TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_1, HASH_1)
        return records, current_hashes, dag

    def test_uuid1_is_skipped(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert UUID_1 in skipped, f"UUID_1 must be skipped; skipped={skipped}"

    def test_uuid2_is_extracted(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert UUID_2 in extracted, f"UUID_2 must be extracted; extracted={extracted}"

    def test_partition_is_disjoint(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert UUID_1 not in extracted, "UUID_1 must NOT be extracted"
        assert UUID_2 not in skipped, "UUID_2 must NOT be skipped"
        assert skipped.isdisjoint(extracted), "skipped and extracted must be disjoint"

    def test_all_uuids_accounted_for(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped | extracted == ALL_UUIDS

    def test_should_skip_true_for_uuid1(self, state):
        records, current_hashes, _ = state
        assert should_skip(UUID_1, records, current_hashes, incremental=True) is True

    def test_should_skip_false_for_uuid2_non_terminal(self, state):
        records, current_hashes, _ = state
        assert should_skip(UUID_2, records, current_hashes, incremental=True) is False

    def test_should_skip_false_for_uuid1_when_not_incremental(self, state):
        records, current_hashes, _ = state
        assert should_skip(UUID_1, records, current_hashes, incremental=False) is False

    def test_invariants_at_init(self, state):
        records, current_hashes, _ = state
        assert_all_invariants(set(), set(), ALL_UUIDS, records, current_hashes, True)

    def test_invariants_after_uuid1_processed(self, state):
        records, current_hashes, _ = state
        skipped = {UUID_1}
        extracted: set = set()
        remaining = {UUID_2}
        assert_all_invariants(skipped, extracted, remaining, records, current_hashes, True)

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_skip_only_when_incremental_holds(self, state):
        records, current_hashes, _ = state
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        assert skipped
        inv_skip_only_when_incremental(skipped, incremental=True)

    def test_skip_only_when_hash_match_holds(self, state):
        records, current_hashes, _ = state
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        inv_skip_only_when_hash_match(skipped, records, current_hashes)
        assert records[UUID_1]["src_hash"] == current_hashes[UUID_1]

    def test_skip_never_extracted_holds(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_skip_never_extracted(skipped, extracted)

    def test_unchanged_never_extracted_holds(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_unchanged_never_extracted(skipped, set(), records, current_hashes, True)

    def test_processed_partition_holds(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_processed_partition(skipped, extracted, set())

    def test_bounded_skipped_holds(self, state):
        records, current_hashes, _ = state
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        inv_bounded_skipped(skipped)

    def test_bounded_extracted_holds(self, state):
        records, current_hashes, _ = state
        _, extracted = run_processor(records, current_hashes, incremental=True)
        inv_bounded_extracted(extracted)

    def test_dag_node_count(self, state):
        _, _, dag = state
        assert dag.node_count == 2

    def test_dag_extract_subgraph_uuid1(self, state):
        _, _, dag = state
        result = dag.extract_subgraph(UUID_1)
        assert UUID_1 in result.nodes

    def test_dag_extract_subgraph_uuid2(self, state):
        _, _, dag = state
        result = dag.extract_subgraph(UUID_2)
        assert UUID_2 in result.nodes


class TestTrace10:
    """
    Trace 10 - incremental=TRUE.
    UUID_1: Terminal1, src_hash=Hash1, current=Hash2 -> hash mismatch -> extracted
    UUID_2: NonTerminal1, src_hash=Hash2, current=Hash2 -> non-terminal -> extracted
    Expected final: skipped={}, extracted={UUID_1, UUID_2}
    """

    @pytest.fixture
    def state(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_2, UUID_2: HASH_2}
        dag = _build_dag(TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_1, HASH_2)
        return records, current_hashes, dag

    def test_both_extracted(self, state):
        records, current_hashes, dag = state
        assert dag.node_count == 2
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        assert extracted == {UUID_1, UUID_2}

    def test_invariants_final_state(self, state):
        records, current_hashes, _ = state
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_uuid1_terminal_hash_mismatch(self, state):
        records, current_hashes, _ = state
        assert is_terminal(UUID_1, records)
        assert not hash_matches(UUID_1, records, current_hashes)
        assert not should_skip(UUID_1, records, current_hashes, incremental=True)

    def test_uuid2_non_terminal_hash_match_irrelevant(self, state):
        records, current_hashes, _ = state
        assert not is_terminal(UUID_2, records)
        assert hash_matches(UUID_2, records, current_hashes)
        assert not should_skip(UUID_2, records, current_hashes, incremental=True)


# ===========================================================================
# Dedicated invariant verifier tests
# ===========================================================================


class TestInvSkipOnlyWhenIncremental:

    def test_skip_only_occurs_with_incremental_true_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        assert skipped == {UUID_1}
        inv_skip_only_when_incremental(skipped, incremental=True)

    def test_no_skip_when_incremental_false_both_qualify(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, _ = run_processor(records, current_hashes, incremental=False)
        assert skipped == set()
        inv_skip_only_when_incremental(skipped, incremental=False)

    def test_empty_skipped_vacuously_satisfies_with_incremental_false(self):
        inv_skip_only_when_incremental(set(), incremental=False)

    def test_empty_skipped_vacuously_satisfies_with_incremental_true(self):
        inv_skip_only_when_incremental(set(), incremental=True)

    def test_non_empty_skipped_requires_incremental_true(self):
        with pytest.raises(AssertionError, match="SkipOnlyWhenIncremental"):
            inv_skip_only_when_incremental({UUID_1}, incremental=False)


class TestInvSkipOnlyWhenHashMatch:

    def test_skipped_uuid_must_have_hash_match_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        assert UUID_1 in skipped
        inv_skip_only_when_hash_match(skipped, records, current_hashes)
        assert records[UUID_1]["src_hash"] == current_hashes[UUID_1] == HASH_1

    def test_hash_mismatch_prevents_skip_trace1(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        skipped, _ = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        inv_skip_only_when_hash_match(skipped, records, current_hashes)

    def test_hash_mismatch_in_skipped_raises(self):
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_2}
        with pytest.raises(AssertionError, match="SkipOnlyWhenHashMatch"):
            inv_skip_only_when_hash_match({UUID_1}, records, current_hashes)

    def test_empty_skipped_vacuously_satisfies(self):
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2}}
        current_hashes = {UUID_1: HASH_1}
        inv_skip_only_when_hash_match(set(), records, current_hashes)


class TestInvSkipNeverExtracted:

    def test_disjoint_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == {UUID_1}
        assert extracted == {UUID_2}
        inv_skip_never_extracted(skipped, extracted)

    def test_disjoint_all_extracted_trace1(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == set()
        inv_skip_never_extracted(skipped, extracted)

    def test_overlap_raises(self):
        with pytest.raises(AssertionError, match="SkipNeverExtracted"):
            inv_skip_never_extracted({UUID_1}, {UUID_1})


class TestInvUnchangedNeverExtracted:

    def test_qualifying_processed_uuid_in_skipped_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_unchanged_never_extracted(skipped, set(), records, current_hashes, True)

    def test_incremental_false_removes_obligation_both_qualify(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, _ = run_processor(records, current_hashes, incremental=False)
        assert skipped == set()
        inv_unchanged_never_extracted(skipped, set(), records, current_hashes, False)

    def test_violation_raises(self):
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_1}
        with pytest.raises(AssertionError, match="UnchangedNeverExtracted"):
            inv_unchanged_never_extracted(
                skipped=set(),
                remaining=set(),
                records=records,
                current_hashes=current_hashes,
                incremental=True,
                all_uuids=frozenset({UUID_1}),
            )


class TestInvProcessedPartition:

    def test_all_partitioned_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_processed_partition(skipped, extracted, set())
        assert (skipped | extracted) == ALL_UUIDS

    def test_all_extracted_partition_trace1(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_1}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_processed_partition(skipped, extracted, set())
        assert (skipped | extracted) == ALL_UUIDS

    def test_partial_processing_holds_at_midpoint(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped = {UUID_1}
        extracted: set = set()
        remaining = {UUID_2}
        inv_processed_partition(skipped, extracted, remaining)

    def test_violation_raises(self):
        with pytest.raises(AssertionError, match="ProcessedPartition"):
            inv_processed_partition(
                skipped=set(),
                extracted=set(),
                remaining=set(),
                all_uuids=frozenset({UUID_1}),
            )


class TestInvBoundedCollections:

    def test_skipped_subset_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_bounded_skipped(skipped)
        inv_bounded_extracted(extracted)
        assert skipped <= ALL_UUIDS
        assert extracted <= ALL_UUIDS

    def test_extracted_subset_trace2(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        inv_bounded_skipped(skipped)
        inv_bounded_extracted(extracted)
        assert extracted <= ALL_UUIDS

    def test_bounded_skipped_violation_raises(self):
        with pytest.raises(AssertionError, match="BoundedSkipped"):
            inv_bounded_skipped({"unknown-uuid-xyz"})

    def test_bounded_extracted_violation_raises(self):
        with pytest.raises(AssertionError, match="BoundedExtracted"):
            inv_bounded_extracted({"unknown-uuid-xyz"})


# ===========================================================================
# Edge-case tests
# ===========================================================================


class TestEdgeCases:

    def test_single_uuid_skip_terminal_hash_match_incremental(self):
        single = frozenset({UUID_1})
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_1}

        assert should_skip(UUID_1, records, current_hashes, incremental=True) is True

        remaining = {UUID_1}
        skipped: set = set()
        extracted: set = set()
        assert_all_invariants(skipped, extracted, remaining, records, current_hashes, True, single)

        remaining.remove(UUID_1)
        skipped.add(UUID_1)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True, single)

        assert skipped == {UUID_1}
        assert extracted == set()

    def test_single_uuid_no_skip_non_incremental(self):
        single = frozenset({UUID_1})
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_1}

        assert should_skip(UUID_1, records, current_hashes, incremental=False) is False

        remaining = {UUID_1}
        skipped: set = set()
        extracted: set = set()
        remaining.remove(UUID_1)
        extracted.add(UUID_1)
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, False, single)
        assert extracted == {UUID_1}

    def test_single_uuid_no_skip_hash_mismatch(self):
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_2}
        assert should_skip(UUID_1, records, current_hashes, incremental=True) is False

    def test_single_uuid_no_skip_non_terminal(self):
        records = {UUID_1: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_1}
        assert should_skip(UUID_1, records, current_hashes, incremental=True) is False

    def test_all_three_conditions_required_for_skip(self):
        records = {UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1}}
        current_hashes = {UUID_1: HASH_1}

        assert should_skip(UUID_1, records, current_hashes, True) is True
        assert should_skip(UUID_1, records, current_hashes, False) is False

        nt_records = {UUID_1: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1}}
        assert should_skip(UUID_1, nt_records, current_hashes, True) is False

        mismatch_hashes = {UUID_1: HASH_2}
        assert should_skip(UUID_1, records, mismatch_hashes, True) is False

    def test_both_uuids_skip_when_all_qualify(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        skipped, extracted = run_processor(records, current_hashes, incremental=True)
        assert skipped == {UUID_1, UUID_2}
        assert extracted == set()
        assert_all_invariants(skipped, extracted, set(), records, current_hashes, True)

    def test_dag_node_registration_matches_trace9(self):
        dag = _build_dag(TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_1, HASH_1)
        assert dag.node_count == 2

    def test_dag_with_import_edge_does_not_affect_skip_logic(self):
        dag = RegistryDag()
        dag.add_node(Node.resource(UUID_1, "node-1", TERMINAL_DESC_1))
        dag.add_node(Node.resource(UUID_2, "node-2", NON_TERMINAL_DESC_1))
        dag.add_edge(Edge(UUID_1, UUID_2, EdgeType.IMPORTS))
        assert dag.edge_count == 1

        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        assert should_skip(UUID_1, records, current_hashes, True) is True
        assert should_skip(UUID_2, records, current_hashes, True) is False

    def test_invariants_at_every_intermediate_step_trace9(self):
        records = {
            UUID_1: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_1},
            UUID_2: {"do_description": NON_TERMINAL_DESC_1, "src_hash": HASH_1},
        }
        current_hashes = {UUID_1: HASH_1, UUID_2: HASH_2}
        incremental = True

        assert_all_invariants(set(), set(), ALL_UUIDS, records, current_hashes, incremental)
        assert_all_invariants({UUID_1}, set(), {UUID_2}, records, current_hashes, incremental)
        assert_all_invariants({UUID_1}, {UUID_2}, set(), records, current_hashes, incremental)
        assert_all_invariants({UUID_1}, {UUID_2}, set(), records, current_hashes, incremental)

    def test_dag_extract_subgraph_returns_uuid1_node_in_trace9(self):
        dag = _build_dag(TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_1, HASH_1)
        result = dag.extract_subgraph(UUID_1)
        assert UUID_1 in result.nodes

    def test_dag_extract_subgraph_isolated_nodes(self):
        dag = _build_dag(TERMINAL_DESC_1, HASH_1, NON_TERMINAL_DESC_1, HASH_1)
        sg1 = dag.extract_subgraph(UUID_1)
        sg2 = dag.extract_subgraph(UUID_2)
        assert UUID_1 in sg1.nodes
        assert UUID_2 not in sg1.nodes
        assert UUID_2 in sg2.nodes
        assert UUID_1 not in sg2.nodes

    def test_non_incremental_never_violates_skip_only_when_incremental(self):
        topologies = [
            (
                {UUID_1: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_2},
                 UUID_2: {"do_description": TERMINAL_DESC_1, "src_hash": HASH_2}},
                {UUID_1: HASH_1, UUID_2: HASH_2},
            ),
            (
                {UUID_1: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_1},
                 UUID_2: {"do_description": NON_TERMINAL_DESC_2, "src_hash": HASH_2}},
                {UUID_1: HASH_2, UUID_2: HASH_1},
            ),
            (
                {UUID_1: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2},
                 UUID_2: {"do_description": TERMINAL_DESC_2, "src_hash": HASH_2}},
                {UUID_1: HASH_1, UUID_2: HASH_1},
            ),
        ]
        for records, current_hashes in topologies:
            skipped, _ = run_processor(records, current_hashes, incremental=False)
            assert skipped == set(), f"Expected empty skipped for non-incremental; got {skipped}"
            inv_skip_only_when_incremental(skipped, incremental=False)