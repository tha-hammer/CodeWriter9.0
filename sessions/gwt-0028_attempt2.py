import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Edge, EdgeType, Node


# ---------------------------------------------------------------------------
# Constants derived from the TLA+ spec
# ---------------------------------------------------------------------------

ENTRY_POINTS: frozenset[int] = frozenset({1, 2})
INITIAL_PENDING: frozenset[int] = frozenset({3, 4})
MAX_STEPS: int = 10


# ---------------------------------------------------------------------------
# Orchestrator: models the TLA+ DfsBeforeSweep algorithm backed by RegistryDag
# ---------------------------------------------------------------------------

class CrawlOrchestrator:
    """
    Simulates the TLA+ DfsBeforeSweep algorithm.

    State variables mirror the TLA+ spec:
        phase        — "dfs" | "sweep" | "done"
        visited      — set of entry-point IDs that have been DFS-visited
        pending      — set of pending record IDs awaiting sweep processing
        dfs_complete — True after DfsFinish
        sweep_active — True between SweepActivate and SweepDeactivate
        step_count   — incremented by DfsVisit, SweepActivate, SweepDeactivate

    The backing RegistryDag accumulates:
        • behavior nodes  — one per entry point, added during dfs_visit()
        • resource nodes  — one per pending record, added during sweep_process()
    """

    def __init__(self, entry_points, initial_pending):
        self.dag = RegistryDag()
        self.entry_points = frozenset(entry_points)
        self.phase = "dfs"
        self.visited: set[int] = set()
        self.pending: set[int] = set(initial_pending)
        self.dfs_complete: bool = False
        self.sweep_active: bool = False
        self.step_count: int = 0

    # -- DFS actions ---------------------------------------------------------

    def dfs_loop(self) -> str:
        """Returns the label of the next action as per DfsLoop guard."""
        return "DfsVisit" if self.visited != self.entry_points else "DfsFinish"

    def dfs_visit(self, ep: int) -> None:
        """DfsVisit: register one entry-point node in the DAG and record it as visited."""
        assert self.phase == "dfs", (
            f"dfs_visit called in phase '{self.phase}'"
        )
        assert ep in self.entry_points, (
            f"{ep} is not an entry point"
        )
        assert ep not in self.visited, (
            f"entry point {ep} already visited"
        )
        self.dag.add_node(
            Node.behavior(str(ep), f"entry_point_{ep}", "given", "when", "then")
        )
        self.visited.add(ep)
        self.step_count += 1

    def dfs_finish(self) -> None:
        """DfsFinish: assert coverage, set dfs_complete, transition to sweep."""
        assert self.visited == self.entry_points, (
            f"DfsFinish before all entry points visited: "
            f"visited={self.visited}, entry_points={self.entry_points}"
        )
        self.dfs_complete = True
        self.phase = "sweep"

    # -- Sweep actions -------------------------------------------------------

    def sweep_loop(self) -> str:
        """Returns the label of the next action as per SweepLoop guard."""
        return "SweepActivate" if self.pending else "Terminate"

    def sweep_activate(self) -> None:
        """SweepActivate: mark sweep active, increment step."""
        assert self.phase == "sweep", (
            f"sweep_activate called in phase '{self.phase}'"
        )
        assert self.pending, "sweep_activate called with empty pending"
        assert not self.sweep_active, "sweep_activate called while sweep_active=True"
        self.sweep_active = True
        self.step_count += 1

    def sweep_process(self, p: int) -> None:
        """SweepProcess: extract pending record into DAG, remove from pending."""
        assert self.phase == "sweep", (
            f"sweep_process called in phase '{self.phase}'"
        )
        assert self.sweep_active, "sweep_process called while sweep_active=False"
        assert p in self.pending, f"{p} not in pending"
        self.dag.add_node(
            Node.resource(str(p), f"pending_record_{p}", f"sweep record {p}")
        )
        self.pending.discard(p)

    def sweep_deactivate(self) -> None:
        """SweepDeactivate: mark sweep inactive, increment step."""
        assert self.phase == "sweep", (
            f"sweep_deactivate called in phase '{self.phase}'"
        )
        assert self.sweep_active, "sweep_deactivate called while sweep_active=False"
        self.sweep_active = False
        self.step_count += 1

    def terminate(self) -> None:
        """Terminate: assert pending is empty, transition to done."""
        assert self.phase == "sweep", (
            f"terminate called in phase '{self.phase}'"
        )
        assert not self.pending, (
            f"terminate called with non-empty pending: {self.pending}"
        )
        self.phase = "done"


# ---------------------------------------------------------------------------
# Invariant verifier
# ---------------------------------------------------------------------------

def check_invariants(o: CrawlOrchestrator) -> None:
    """
    Verify all four TLA+ invariants for the current orchestrator state.

    PhaseSequencing:      phase = "sweep" => dfs_complete = TRUE
    NoSweepDuringDfs:     phase = "dfs"   => sweep_active = FALSE
    AllEntryPointsVisited: phase /= "dfs"  => visited = EntryPoints
    BoundedExecution:     step_count <= MaxSteps
    """
    if o.phase == "sweep":
        assert o.dfs_complete, (
            f"PhaseSequencing violated: phase='sweep' but dfs_complete=False"
        )
    if o.phase == "dfs":
        assert not o.sweep_active, (
            f"NoSweepDuringDfs violated: phase='dfs' but sweep_active=True"
        )
    if o.phase != "dfs":
        assert o.visited == o.entry_points, (
            f"AllEntryPointsVisited violated: phase='{o.phase}' "
            f"but visited={o.visited} != entry_points={o.entry_points}"
        )
    assert o.step_count <= MAX_STEPS, (
        f"BoundedExecution violated: step_count={o.step_count} > {MAX_STEPS}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_full_trace(dfs_order, sweep_order):
    """
    Execute a complete DfsBeforeSweep trace, asserting invariants at every state.
    """
    o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)

    assert o.phase == "dfs"
    assert o.visited == set()
    assert o.pending == set(INITIAL_PENDING)
    assert o.step_count == 0
    assert o.dfs_complete is False
    assert o.sweep_active is False
    check_invariants(o)

    for ep in dfs_order:
        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)
        o.dfs_visit(ep)
        check_invariants(o)

    assert o.dfs_loop() == "DfsFinish"
    check_invariants(o)

    o.dfs_finish()
    assert o.phase == "sweep"
    assert o.dfs_complete is True
    assert o.sweep_active is False
    assert o.step_count == len(dfs_order)
    check_invariants(o)

    for p in sweep_order:
        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_process(p)
        assert p not in o.pending
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        check_invariants(o)

    assert o.sweep_loop() == "Terminate"
    check_invariants(o)

    o.terminate()
    assert o.phase == "done"
    assert o.pending == set()
    assert o.visited == set(ENTRY_POINTS)
    assert o.dfs_complete is True
    assert o.sweep_active is False
    expected_steps = len(dfs_order) + 2 * len(sweep_order)
    assert o.step_count == expected_steps, (
        f"step_count={o.step_count} != expected {expected_steps} "
        f"for dfs_order={dfs_order}, sweep_order={sweep_order}"
    )
    check_invariants(o)

    return o


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orch_dfs12_sweep43():
    return CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)


@pytest.fixture
def orch_dfs21_sweep43():
    return CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)


@pytest.fixture
def orch_dfs12_sweep34():
    return CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)


@pytest.fixture
def orch_dfs21_sweep34():
    return CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

class TestTrace1:
    def test_init_state(self, orch_dfs12_sweep43):
        o = orch_dfs12_sweep43
        assert o.phase == "dfs"
        assert o.visited == set()
        assert o.pending == {3, 4}
        assert o.step_count == 0
        assert o.dfs_complete is False
        assert o.sweep_active is False
        check_invariants(o)

    def test_full_trace(self, orch_dfs12_sweep43):
        o = orch_dfs12_sweep43
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(1)
        assert o.visited == {1}
        assert o.step_count == 1
        assert o.phase == "dfs"
        assert o.dfs_complete is False
        assert o.sweep_active is False
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(2)
        assert o.visited == {1, 2}
        assert o.step_count == 2
        assert o.phase == "dfs"
        assert o.dfs_complete is False
        assert o.sweep_active is False
        check_invariants(o)

        assert o.dfs_loop() == "DfsFinish"
        check_invariants(o)

        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        assert o.sweep_active is False
        assert o.step_count == 2
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 3
        check_invariants(o)

        o.sweep_process(4)
        assert o.pending == {3}
        assert o.step_count == 3
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 4
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 5
        check_invariants(o)

        o.sweep_process(3)
        assert o.pending == set()
        assert o.step_count == 5
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 6
        check_invariants(o)

        assert o.sweep_loop() == "Terminate"
        check_invariants(o)

        o.terminate()
        assert o.phase == "done"
        assert o.pending == set()
        assert o.visited == {1, 2}
        assert o.step_count == 6
        assert o.dfs_complete is True
        assert o.sweep_active is False
        check_invariants(o)

        assert o.dag.node_count == 4


# ---------------------------------------------------------------------------
# Trace 2
# ---------------------------------------------------------------------------

class TestTrace2:
    def test_full_trace(self, orch_dfs21_sweep43):
        o = orch_dfs21_sweep43
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(2)
        assert o.visited == {2}
        assert o.step_count == 1
        assert o.phase == "dfs"
        assert o.dfs_complete is False
        assert o.sweep_active is False
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(1)
        assert o.visited == {1, 2}
        assert o.step_count == 2
        assert o.phase == "dfs"
        check_invariants(o)

        assert o.dfs_loop() == "DfsFinish"
        check_invariants(o)

        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        assert o.step_count == 2
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 3
        check_invariants(o)

        o.sweep_process(4)
        assert o.pending == {3}
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 4
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 5
        check_invariants(o)

        o.sweep_process(3)
        assert o.pending == set()
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 6
        check_invariants(o)

        assert o.sweep_loop() == "Terminate"
        check_invariants(o)

        o.terminate()
        assert o.phase == "done"
        assert o.pending == set()
        assert o.visited == {1, 2}
        assert o.step_count == 6
        assert o.dfs_complete is True
        assert o.sweep_active is False
        check_invariants(o)
        assert o.dag.node_count == 4


# ---------------------------------------------------------------------------
# Trace 3
# ---------------------------------------------------------------------------

class TestTrace3:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[2, 1], sweep_order=[4, 3])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.step_count == 6
        assert o.dfs_complete is True
        assert o.dag.node_count == 4


# ---------------------------------------------------------------------------
# Trace 4
# ---------------------------------------------------------------------------

class TestTrace4:
    def test_full_trace(self, orch_dfs12_sweep34):
        o = orch_dfs12_sweep34
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(1)
        assert o.visited == {1}
        assert o.step_count == 1
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(2)
        assert o.visited == {1, 2}
        assert o.step_count == 2
        check_invariants(o)

        assert o.dfs_loop() == "DfsFinish"
        check_invariants(o)

        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        assert o.step_count == 2
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 3
        check_invariants(o)

        o.sweep_process(3)
        assert o.pending == {4}
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 4
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 5
        check_invariants(o)

        o.sweep_process(4)
        assert o.pending == set()
        assert o.sweep_active is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 6
        check_invariants(o)

        assert o.sweep_loop() == "Terminate"
        check_invariants(o)

        o.terminate()
        assert o.phase == "done"
        assert o.pending == set()
        assert o.visited == {1, 2}
        assert o.step_count == 6
        assert o.dfs_complete is True
        assert o.sweep_active is False
        check_invariants(o)
        assert o.dag.node_count == 4


# ---------------------------------------------------------------------------
# Trace 5
# ---------------------------------------------------------------------------

class TestTrace5:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[2, 1], sweep_order=[4, 3])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.dfs_complete is True
        assert o.step_count == 6


# ---------------------------------------------------------------------------
# Trace 6
# ---------------------------------------------------------------------------

class TestTrace6:
    def test_full_trace(self, orch_dfs21_sweep34):
        o = orch_dfs21_sweep34
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(2)
        assert o.visited == {2}
        assert o.step_count == 1
        check_invariants(o)

        assert o.dfs_loop() == "DfsVisit"
        check_invariants(o)

        o.dfs_visit(1)
        assert o.visited == {1, 2}
        assert o.step_count == 2
        check_invariants(o)

        assert o.dfs_loop() == "DfsFinish"
        check_invariants(o)

        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 3
        check_invariants(o)

        o.sweep_process(3)
        assert o.pending == {4}
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 4
        check_invariants(o)

        assert o.sweep_loop() == "SweepActivate"
        check_invariants(o)

        o.sweep_activate()
        assert o.sweep_active is True
        assert o.step_count == 5
        check_invariants(o)

        o.sweep_process(4)
        assert o.pending == set()
        check_invariants(o)

        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.step_count == 6
        check_invariants(o)

        assert o.sweep_loop() == "Terminate"
        check_invariants(o)

        o.terminate()
        assert o.phase == "done"
        assert o.pending == set()
        assert o.visited == {1, 2}
        assert o.step_count == 6
        assert o.dfs_complete is True
        assert o.sweep_active is False
        check_invariants(o)
        assert o.dag.node_count == 4


# ---------------------------------------------------------------------------
# Trace 7
# ---------------------------------------------------------------------------

class TestTrace7:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[1, 2], sweep_order=[4, 3])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.dfs_complete is True
        assert o.step_count == 6


# ---------------------------------------------------------------------------
# Trace 8
# ---------------------------------------------------------------------------

class TestTrace8:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[1, 2], sweep_order=[4, 3])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.dfs_complete is True
        assert o.step_count == 6


# ---------------------------------------------------------------------------
# Trace 9
# ---------------------------------------------------------------------------

class TestTrace9:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[2, 1], sweep_order=[4, 3])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.dfs_complete is True
        assert o.step_count == 6


# ---------------------------------------------------------------------------
# Trace 10
# ---------------------------------------------------------------------------

class TestTrace10:
    def test_full_trace(self):
        o = _run_full_trace(dfs_order=[1, 2], sweep_order=[3, 4])
        assert o.phase == "done"
        assert o.visited == {1, 2}
        assert o.pending == set()
        assert o.dfs_complete is True
        assert o.step_count == 6


# ---------------------------------------------------------------------------
# PhaseSequencing invariant tests
# ---------------------------------------------------------------------------

class TestPhaseSequencingInvariant:

    def test_dfs_phase_dfs_complete_is_false_initially(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        assert o.phase == "dfs"
        assert o.dfs_complete is False
        check_invariants(o)

    def test_dfs_complete_remains_false_mid_dfs(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        assert o.phase == "dfs"
        assert o.dfs_complete is False
        check_invariants(o)

    def test_sweep_phase_enforces_dfs_complete_topology_dfs12(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        o.dfs_visit(2)
        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        check_invariants(o)

    def test_sweep_phase_enforces_dfs_complete_topology_dfs21(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(2)
        o.dfs_visit(1)
        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        check_invariants(o)

    def test_dfs_complete_persists_through_sweep_and_done(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()

        o.sweep_activate()
        assert o.dfs_complete is True
        check_invariants(o)

        o.sweep_process(3)
        assert o.dfs_complete is True
        check_invariants(o)

        o.sweep_deactivate()
        assert o.dfs_complete is True
        check_invariants(o)

        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        o.terminate()
        assert o.phase == "done"
        assert o.dfs_complete is True
        check_invariants(o)


# ---------------------------------------------------------------------------
# NoSweepDuringDfs invariant tests
# ---------------------------------------------------------------------------

class TestNoSweepDuringDfsInvariant:

    def test_sweep_active_false_at_init(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        assert o.phase == "dfs"
        assert o.sweep_active is False
        check_invariants(o)

    def test_sweep_active_stays_false_throughout_dfs_topology_dfs12(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        for ep in [1, 2]:
            assert o.phase == "dfs"
            assert o.sweep_active is False
            check_invariants(o)
            o.dfs_visit(ep)
            assert o.phase == "dfs"
            assert o.sweep_active is False
            check_invariants(o)

    def test_sweep_active_stays_false_throughout_dfs_topology_dfs21(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        for ep in [2, 1]:
            assert o.phase == "dfs"
            assert o.sweep_active is False
            check_invariants(o)
            o.dfs_visit(ep)
            assert o.sweep_active is False
            check_invariants(o)

    def test_sweep_active_only_set_after_dfs_finishes(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        assert o.phase == "sweep"
        o.sweep_activate()
        assert o.sweep_active is True
        assert o.phase == "sweep"
        check_invariants(o)

    def test_sweep_active_reset_between_records(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(2); o.dfs_visit(1); o.dfs_finish()
        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.phase == "sweep"
        check_invariants(o)

    def test_cannot_activate_sweep_during_dfs_phase(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        assert o.phase == "dfs"
        with pytest.raises(AssertionError):
            o.sweep_activate()


# ---------------------------------------------------------------------------
# AllEntryPointsVisited invariant tests
# ---------------------------------------------------------------------------

class TestAllEntryPointsVisitedInvariant:

    def test_dfs_phase_allows_partial_visited(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        assert o.phase == "dfs"
        assert o.visited == {1}
        assert o.visited != ENTRY_POINTS
        check_invariants(o)

    def test_sweep_phase_has_full_visited_topology_dfs12(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        assert o.phase == "sweep"
        assert o.visited == set(ENTRY_POINTS)
        check_invariants(o)

    def test_sweep_phase_has_full_visited_topology_dfs21(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(2); o.dfs_visit(1); o.dfs_finish()
        assert o.phase == "sweep"
        assert o.visited == set(ENTRY_POINTS)
        check_invariants(o)

    def test_visited_unchanged_during_sweep(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        snapshot = frozenset(o.visited)

        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        assert o.visited == snapshot
        check_invariants(o)

        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        assert o.visited == snapshot
        check_invariants(o)

    def test_done_phase_has_full_visited(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(2); o.dfs_visit(1); o.dfs_finish()
        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        o.terminate()
        assert o.phase == "done"
        assert o.visited == set(ENTRY_POINTS)
        check_invariants(o)

    def test_cannot_finish_dfs_with_partial_visited(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        with pytest.raises(AssertionError):
            o.dfs_finish()


# ---------------------------------------------------------------------------
# BoundedExecution invariant tests
# ---------------------------------------------------------------------------

class TestBoundedExecutionInvariant:

    def test_step_count_zero_at_init(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        assert o.step_count == 0
        check_invariants(o)

    def test_step_count_increments_only_on_visit_activate_deactivate(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)

        o.dfs_visit(1);       assert o.step_count == 1; check_invariants(o)
        o.dfs_visit(2);       assert o.step_count == 2; check_invariants(o)
        o.dfs_finish();       assert o.step_count == 2; check_invariants(o)

        o.sweep_activate();   assert o.step_count == 3; check_invariants(o)
        o.sweep_process(3);   assert o.step_count == 3; check_invariants(o)
        o.sweep_deactivate(); assert o.step_count == 4; check_invariants(o)

        o.sweep_activate();   assert o.step_count == 5; check_invariants(o)
        o.sweep_process(4);   assert o.step_count == 5; check_invariants(o)
        o.sweep_deactivate(); assert o.step_count == 6; check_invariants(o)

        o.terminate();        assert o.step_count == 6; check_invariants(o)

    def test_final_step_count_within_max_steps_topology_dfs12_sweep43(self):
        o = _run_full_trace(dfs_order=[1, 2], sweep_order=[4, 3])
        assert o.step_count == 6
        assert o.step_count <= MAX_STEPS

    def test_final_step_count_within_max_steps_topology_dfs21_sweep34(self):
        o = _run_full_trace(dfs_order=[2, 1], sweep_order=[3, 4])
        assert o.step_count == 6
        assert o.step_count <= MAX_STEPS

    def test_step_count_intermediate_states_always_bounded(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        states = []

        o.dfs_visit(1);       states.append(o.step_count)
        o.dfs_visit(2);       states.append(o.step_count)
        o.dfs_finish();       states.append(o.step_count)
        o.sweep_activate();   states.append(o.step_count)
        o.sweep_process(4);   states.append(o.step_count)
        o.sweep_deactivate(); states.append(o.step_count)
        o.sweep_activate();   states.append(o.step_count)
        o.sweep_process(3);   states.append(o.step_count)
        o.sweep_deactivate(); states.append(o.step_count)
        o.terminate();        states.append(o.step_count)

        assert states == [1, 2, 2, 3, 3, 4, 5, 5, 6, 6]
        assert all(s <= MAX_STEPS for s in states)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_pending_set_terminates_immediately_after_dfs(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=set())
        check_invariants(o)
        o.dfs_visit(1); check_invariants(o)
        o.dfs_visit(2); check_invariants(o)
        o.dfs_finish();  check_invariants(o)
        assert o.sweep_loop() == "Terminate"
        o.terminate()
        assert o.phase == "done"
        assert o.pending == set()
        assert o.step_count == 2
        assert o.dag.node_count == 2
        check_invariants(o)

    def test_single_entry_point_single_dfs_visit(self):
        o = CrawlOrchestrator(entry_points={1}, initial_pending={3, 4})
        check_invariants(o)
        assert o.dfs_loop() == "DfsVisit"
        o.dfs_visit(1)
        assert o.visited == {1}
        check_invariants(o)
        assert o.dfs_loop() == "DfsFinish"
        o.dfs_finish()
        assert o.phase == "sweep"
        assert o.dfs_complete is True
        check_invariants(o)
        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        check_invariants(o)
        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        check_invariants(o)
        o.terminate()
        assert o.phase == "done"
        assert o.visited == {1}
        assert o.dag.node_count == 3
        check_invariants(o)

    def test_single_pending_record_sweep_one_cycle(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending={3})
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        check_invariants(o)
        assert o.sweep_loop() == "SweepActivate"
        o.sweep_activate()
        assert o.sweep_active is True
        o.sweep_process(3)
        assert o.pending == set()
        o.sweep_deactivate()
        assert o.sweep_active is False
        assert o.sweep_loop() == "Terminate"
        o.terminate()
        assert o.phase == "done"
        assert o.step_count == 4
        check_invariants(o)

    def test_dag_empty_at_init(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        assert o.dag.node_count == 0
        assert o.dag.edge_count == 0

    def test_dag_grows_only_during_dfs_then_sweep(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2)
        assert o.dag.node_count == 2
        o.dfs_finish()
        assert o.dag.node_count == 2

        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        assert o.dag.node_count == 3

        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        assert o.dag.node_count == 4

        o.terminate()
        assert o.dag.node_count == 4

    def test_dag_edge_between_entry_points_is_preserved(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2)
        o.dag.add_edge(Edge("1", "2", EdgeType.IMPORTS))
        assert o.dag.edge_count == 1
        o.dfs_finish(); check_invariants(o)
        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        o.sweep_activate(); o.sweep_process(4); o.sweep_deactivate()
        o.terminate()
        assert o.dag.edge_count == 1
        assert o.dag.node_count == 4
        check_invariants(o)

    def test_query_relevant_after_dfs_finds_entry_point_node(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2)
        o.dag.add_edge(Edge("1", "2", EdgeType.IMPORTS))
        result = o.dag.extract_subgraph("1")
        assert result is not None

    def test_query_impact_on_pending_node_after_sweep(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        o.sweep_activate(); o.sweep_process(3); o.sweep_deactivate()
        result = o.dag.query_impact("3")
        assert result is not None

    def test_cannot_visit_entry_point_twice(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        with pytest.raises(AssertionError):
            o.dfs_visit(1)

    def test_cannot_visit_non_entry_point_node(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        with pytest.raises(AssertionError):
            o.dfs_visit(3)

    def test_cannot_activate_sweep_in_dfs_phase(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        with pytest.raises(AssertionError):
            o.sweep_activate()

    def test_cannot_finish_dfs_before_all_entry_points_visited(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1)
        with pytest.raises(AssertionError):
            o.dfs_finish()

    def test_cannot_terminate_with_pending_remaining(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        with pytest.raises(AssertionError):
            o.terminate()

    def test_cannot_deactivate_sweep_when_not_active(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        with pytest.raises(AssertionError):
            o.sweep_deactivate()

    def test_cannot_activate_sweep_when_already_active(self):
        o = CrawlOrchestrator(entry_points=ENTRY_POINTS, initial_pending=INITIAL_PENDING)
        o.dfs_visit(1); o.dfs_visit(2); o.dfs_finish()
        o.sweep_activate()
        assert o.sweep_active is True
        with pytest.raises(AssertionError):
            o.sweep_activate()

    def test_dag_node_not_found_for_unregistered_node(self):
        dag = RegistryDag()
        dag.add_node(Node.behavior("1", "entry_1", "g", "w", "t"))
        with pytest.raises(NodeNotFoundError):
            dag.extract_subgraph("999")

    def test_all_four_trace_combinations_reach_done(self):
        combinations = [
            ([1, 2], [4, 3]),
            ([2, 1], [4, 3]),
            ([1, 2], [3, 4]),
            ([2, 1], [3, 4]),
        ]
        for dfs_order, sweep_order in combinations:
            o = _run_full_trace(dfs_order=dfs_order, sweep_order=sweep_order)
            assert o.phase == "done", (
                f"phase != 'done' for dfs_order={dfs_order}, sweep_order={sweep_order}"
            )
            assert o.step_count == 6
            assert o.dfs_complete is True
            assert o.visited == set(ENTRY_POINTS)
            assert o.pending == set()