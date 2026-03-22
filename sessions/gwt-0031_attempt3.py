import asyncio
from typing import FrozenSet, List, Optional, Set, Tuple
import pytest
from registry.types import Node
from registry.dag import RegistryDag, NodeNotFoundError


# ── TLA+ model parameters ─────────────────────────────────────────────────────
CONCURRENCY: int = 10
ALL_RECORDS: FrozenSet[str] = frozenset({"Records_1", "Records_2"})


# ─────────────────────────────────────────────────────────────────────────────
# DAG fixture helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_dag(*record_ids: str) -> RegistryDag:
    """Return a RegistryDag with one behavior Node per record id."""
    dag = RegistryDag()
    for rid in record_ids:
        dag.add_node(Node.behavior(rid, rid, "given", "when", "then"))
    return dag


# ─────────────────────────────────────────────────────────────────────────────
# Invariant checker  (TLA+ invariants → Python assertions)
# ─────────────────────────────────────────────────────────────────────────────

def _assert_invariants(
    semaphore: int,
    active: FrozenSet[str],
    completed: FrozenSet[str],
    pending: FrozenSet[str],
    concurrency: int,
    records: FrozenSet[str],
    ctx: str = "",
    *,
    real_sem_value: Optional[int] = None,
) -> None:
    p = f"[{ctx}] " if ctx else ""
    assert semaphore >= 0, \
        f"{p}SemaphoreNonNeg: semaphore={semaphore}"
    assert len(active) <= concurrency, \
        f"{p}ActiveBounded: |active|={len(active)} C={concurrency}"
    assert semaphore + len(active) == concurrency, \
        f"{p}SemaphoreConsistent: {semaphore}+{len(active)}!={concurrency}"
    if real_sem_value is not None:
        assert real_sem_value == semaphore, (
            f"{p}SemaphoreConsistent (real asyncio): "
            f"_sem._value={real_sem_value} expected={semaphore}"
        )
    assert active.isdisjoint(completed), \
        f"{p}ActiveReleasedOnComplete: overlap={active & completed}"
    if not pending and not active:
        assert completed == records, \
            f"{p}AllEventuallyProcessed: completed={completed} expected={records}"


class _Sim:
    def __init__(
        self,
        records: FrozenSet[str] = ALL_RECORDS,
        concurrency: int = CONCURRENCY,
    ) -> None:
        self.records = records
        self.concurrency = concurrency
        self._sem = asyncio.Semaphore(concurrency)
        self._lock = asyncio.Lock()
        self.active: Set[str] = set()
        self.completed: Set[str] = set()
        self.pending: Set[str] = set(records)
        self.max_concurrent: int = 0
        self._history: List[Tuple[str, dict]] = []

    @property
    def semaphore(self) -> int:
        return self.concurrency - len(self.active)

    def _snap(self) -> dict:
        return {
            "semaphore": self.semaphore,
            "active": frozenset(self.active),
            "completed": frozenset(self.completed),
            "pending": frozenset(self.pending),
        }

    def _check(self, ctx: str, *, sync_real_sem: bool = True) -> None:
        s = self._snap()
        self._history.append((ctx, s))
        real_val = self._sem._value if sync_real_sem else None
        _assert_invariants(
            s["semaphore"], s["active"], s["completed"], s["pending"],
            self.concurrency, self.records, ctx,
            real_sem_value=real_val,
        )

    async def extract_one(
        self,
        record: str,
        *,
        after_acquire: Optional[asyncio.Event] = None,
        after_extract: Optional[asyncio.Event] = None,
        wait_before_release: Optional[asyncio.Event] = None,
        after_release: Optional[asyncio.Event] = None,
    ) -> None:
        await self._sem.acquire()
        async with self._lock:
            self.active.add(record)
            self.pending.discard(record)
            self.max_concurrent = max(self.max_concurrent, len(self.active))
            self._check(f"{record}:Acquire", sync_real_sem=True)
        if after_acquire is not None:
            after_acquire.set()

        await asyncio.sleep(0)
        async with self._lock:
            self._check(f"{record}:Extract", sync_real_sem=True)
        if after_extract is not None:
            after_extract.set()

        if wait_before_release is not None:
            await wait_before_release.wait()

        async with self._lock:
            self.active.discard(record)
            self.completed.add(record)
            self._check(f"{record}:Release", sync_real_sem=False)
        self._sem.release()
        if after_release is not None:
            after_release.set()

        await asyncio.sleep(0)
        async with self._lock:
            self._check(f"{record}:Finish", sync_real_sem=True)

    def assert_init(self) -> None:
        assert self.semaphore == self.concurrency, \
            f"init semaphore={self.semaphore} expected={self.concurrency}"
        assert frozenset(self.pending) == self.records
        assert frozenset(self.active) == frozenset()
        assert frozenset(self.completed) == frozenset()
        _assert_invariants(
            self.semaphore, frozenset(self.active), frozenset(self.completed),
            frozenset(self.pending), self.concurrency, self.records, "init",
            real_sem_value=self._sem._value,
        )

    def assert_final(
        self,
        expected_completed: FrozenSet[str],
        expected_semaphore: int,
    ) -> None:
        assert frozenset(self.pending) == frozenset(), \
            f"pending not empty: {self.pending}"
        assert frozenset(self.active) == frozenset(), \
            f"active not empty: {self.active}"
        assert frozenset(self.completed) == expected_completed, \
            f"completed={self.completed} expected={expected_completed}"
        assert self.semaphore == expected_semaphore, \
            f"semaphore={self.semaphore} expected={expected_semaphore}"
        _assert_invariants(
            self.semaphore, frozenset(self.active), frozenset(self.completed),
            frozenset(self.pending), self.concurrency, self.records, "final",
            real_sem_value=self._sem._value,
        )

    def recheck_history(self) -> None:
        for ctx, s in self._history:
            _assert_invariants(
                s["semaphore"], s["active"], s["completed"], s["pending"],
                self.concurrency, self.records, ctx,
            )


@pytest.mark.asyncio
async def test_trace_1_sequential_r1_completes_before_r2_starts():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r1_done = asyncio.Event()

    async def _r1() -> None:
        await sim.extract_one("Records_1")
        r1_done.set()

    async def _r2() -> None:
        await r1_done.wait()
        await sim.extract_one("Records_2")

    await asyncio.gather(_r1(), _r2())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 1
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_2_r2_acquires_first_both_active_r1_releases_first():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_acquired = asyncio.Event()
    r1_extracted = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_acquire=r2_acquired,
            wait_before_release=r1_extracted,
        )

    async def _r1() -> None:
        await r2_acquired.wait()
        await sim.extract_one("Records_1", after_extract=r1_extracted)

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_3_r1_extracts_r2_acquires_during_r1_extract():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r1_extracting = asyncio.Event()
    r2_acquired = asyncio.Event()

    async def _r1() -> None:
        await sim.extract_one(
            "Records_1",
            after_extract=r1_extracting,
            wait_before_release=r2_acquired,
        )

    async def _r2() -> None:
        await r1_extracting.wait()
        await sim.extract_one("Records_2", after_acquire=r2_acquired)

    await asyncio.gather(_r1(), _r2())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_4_r2_acquires_first_r2_releases_during_r1_extract():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_acquired = asyncio.Event()
    r2_released = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_acquire=r2_acquired,
            after_release=r2_released,
        )

    async def _r1() -> None:
        await r2_acquired.wait()
        await sim.extract_one("Records_1", wait_before_release=r2_released)

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_5_r1_acquires_first_both_active_r1_releases_first():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r1_acquired = asyncio.Event()
    r1_released = asyncio.Event()

    async def _r1() -> None:
        await sim.extract_one(
            "Records_1",
            after_acquire=r1_acquired,
            after_release=r1_released,
        )

    async def _r2() -> None:
        await r1_acquired.wait()
        await sim.extract_one("Records_2", wait_before_release=r1_released)

    await asyncio.gather(_r1(), _r2())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_6_r1_done_before_r2_extracts():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r1_finished = asyncio.Event()

    async def _r1() -> None:
        await sim.extract_one("Records_1")
        await asyncio.sleep(0)
        r1_finished.set()

    async def _r2() -> None:
        await r1_finished.wait()
        await sim.extract_one("Records_2")

    await asyncio.gather(_r1(), _r2())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 1
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_7_r2_extracts_r1_acquires_during_r2_extract_r2_releases_first():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_extracting = asyncio.Event()
    r1_acquired = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_extract=r2_extracting,
            wait_before_release=r1_acquired,
        )

    async def _r1() -> None:
        await r2_extracting.wait()
        await sim.extract_one("Records_1", after_acquire=r1_acquired)

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_8_r2_first_both_active_r1_releases_first_variant():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_acquired = asyncio.Event()
    r1_released = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_acquire=r2_acquired,
            wait_before_release=r1_released,
        )

    async def _r1() -> None:
        await r2_acquired.wait()
        await sim.extract_one("Records_1", after_release=r1_released)

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_9_r2_extracts_r1_acquires_r2_releases_r1_finishes():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_after_acquire = asyncio.Event()
    r1_acquired = asyncio.Event()
    r2_released = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_acquire=r2_after_acquire,
            wait_before_release=r1_acquired,
            after_release=r2_released,
        )

    async def _r1() -> None:
        await r2_after_acquire.wait()
        await sim.extract_one(
            "Records_1",
            after_acquire=r1_acquired,
            wait_before_release=r2_released,
        )

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_trace_10_r2_first_both_active_r2_releases_first():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, CONCURRENCY)
    sim.assert_init()

    r2_acquired = asyncio.Event()
    r2_released = asyncio.Event()

    async def _r2() -> None:
        await sim.extract_one(
            "Records_2",
            after_acquire=r2_acquired,
            after_release=r2_released,
        )

    async def _r1() -> None:
        await r2_acquired.wait()
        await sim.extract_one(
            "Records_1",
            wait_before_release=r2_released,
        )

    await asyncio.gather(_r2(), _r1())

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 10)
    assert sim.max_concurrent == 2
    sim.recheck_history()


@pytest.mark.asyncio
async def test_invariant_semaphore_non_neg_two_topologies():
    sim_a = _Sim(ALL_RECORDS, concurrency=2)
    r1_done_a = asyncio.Event()

    async def _a1():
        await sim_a.extract_one("Records_1")
        r1_done_a.set()

    async def _a2():
        await r1_done_a.wait()
        await sim_a.extract_one("Records_2")

    await asyncio.gather(_a1(), _a2())
    for _, snap in sim_a._history:
        assert snap["semaphore"] >= 0, f"SemaphoreNonNeg A: {snap['semaphore']}"

    sim_b = _Sim(ALL_RECORDS, concurrency=2)
    b_acquired = asyncio.Event()

    async def _b1():
        await sim_b.extract_one("Records_1", after_acquire=b_acquired)

    async def _b2():
        await b_acquired.wait()
        await sim_b.extract_one("Records_2")

    await asyncio.gather(_b1(), _b2())
    for _, snap in sim_b._history:
        assert snap["semaphore"] >= 0, f"SemaphoreNonNeg B: {snap['semaphore']}"


@pytest.mark.asyncio
async def test_invariant_active_bounded_two_topologies():
    sim_a = _Sim(ALL_RECORDS, concurrency=1)
    await asyncio.gather(
        sim_a.extract_one("Records_1"),
        sim_a.extract_one("Records_2"),
    )
    assert sim_a.max_concurrent == 1, "C=1 must serialise all extractors"
    for _, snap in sim_a._history:
        assert len(snap["active"]) <= 1, f"ActiveBounded C=1: {snap['active']}"

    sim_b = _Sim(ALL_RECORDS, concurrency=2)
    b_acquired = asyncio.Event()

    async def _b1():
        await sim_b.extract_one("Records_1", after_acquire=b_acquired)

    async def _b2():
        await b_acquired.wait()
        await sim_b.extract_one("Records_2")

    await asyncio.gather(_b1(), _b2())
    assert sim_b.max_concurrent == 2
    for _, snap in sim_b._history:
        assert len(snap["active"]) <= 2, f"ActiveBounded C=2: {snap['active']}"


@pytest.mark.asyncio
async def test_invariant_semaphore_consistent_two_topologies():
    sim_seq = _Sim(ALL_RECORDS, CONCURRENCY)
    done = asyncio.Event()

    async def _s1():
        await sim_seq.extract_one("Records_1")
        done.set()

    async def _s2():
        await done.wait()
        await sim_seq.extract_one("Records_2")

    await asyncio.gather(_s1(), _s2())
    for ctx, snap in sim_seq._history:
        assert snap["semaphore"] + len(snap["active"]) == CONCURRENCY, \
            f"SemaphoreConsistent seq [{ctx}]: {snap['semaphore']}+{len(snap['active'])}"

    sim_con = _Sim(ALL_RECORDS, CONCURRENCY)
    acquired = asyncio.Event()

    async def _c1():
        await sim_con.extract_one("Records_1", after_acquire=acquired)

    async def _c2():
        await acquired.wait()
        await sim_con.extract_one("Records_2")

    await asyncio.gather(_c1(), _c2())
    for ctx, snap in sim_con._history:
        assert snap["semaphore"] + len(snap["active"]) == CONCURRENCY, \
            f"SemaphoreConsistent con [{ctx}]: {snap['semaphore']}+{len(snap['active'])}"


@pytest.mark.asyncio
async def test_invariant_active_released_on_complete_two_topologies():
    sim_ov = _Sim(ALL_RECORDS, CONCURRENCY)
    r1_ext = asyncio.Event()
    r2_acq = asyncio.Event()

    async def _ov1():
        await sim_ov.extract_one("Records_1", after_extract=r1_ext, wait_before_release=r2_acq)

    async def _ov2():
        await r1_ext.wait()
        await sim_ov.extract_one("Records_2", after_acquire=r2_acq)

    await asyncio.gather(_ov1(), _ov2())
    for ctx, snap in sim_ov._history:
        overlap = snap["active"] & snap["completed"]
        assert not overlap, f"ActiveReleasedOnComplete overlap [{ctx}]: {overlap}"

    sim_sq = _Sim(ALL_RECORDS, CONCURRENCY)
    ev = asyncio.Event()

    async def _sq1():
        await sim_sq.extract_one("Records_1")
        ev.set()

    async def _sq2():
        await ev.wait()
        await sim_sq.extract_one("Records_2")

    await asyncio.gather(_sq1(), _sq2())
    for ctx, snap in sim_sq._history:
        overlap = snap["active"] & snap["completed"]
        assert not overlap, f"ActiveReleasedOnComplete sequential [{ctx}]: {overlap}"


@pytest.mark.asyncio
async def test_invariant_all_eventually_processed_two_topologies():
    sim_a = _Sim(ALL_RECORDS, CONCURRENCY)
    done_a = asyncio.Event()

    async def _a1():
        await sim_a.extract_one("Records_1")
        done_a.set()

    async def _a2():
        await done_a.wait()
        await sim_a.extract_one("Records_2")

    await asyncio.gather(_a1(), _a2())
    assert frozenset(sim_a.completed) == ALL_RECORDS
    assert frozenset(sim_a.pending) == frozenset()
    assert frozenset(sim_a.active) == frozenset()

    sim_b = _Sim(ALL_RECORDS, CONCURRENCY)
    await asyncio.gather(*[sim_b.extract_one(r) for r in ALL_RECORDS])
    assert frozenset(sim_b.completed) == ALL_RECORDS
    assert frozenset(sim_b.pending) == frozenset()
    assert frozenset(sim_b.active) == frozenset()
    sim_b.recheck_history()


@pytest.mark.asyncio
async def test_edge_single_record_trivially_sequential():
    records = frozenset({"Records_1"})
    dag = _make_dag("Records_1")
    assert dag.node_count == 1

    sim = _Sim(records, CONCURRENCY)
    assert sim.semaphore == CONCURRENCY

    await sim.extract_one("Records_1")

    sim.assert_final(frozenset({"Records_1"}), CONCURRENCY)
    assert sim.max_concurrent == 1
    sim.recheck_history()


@pytest.mark.asyncio
async def test_edge_concurrency_1_forces_strict_serialisation():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, concurrency=1)
    await asyncio.gather(
        sim.extract_one("Records_1"),
        sim.extract_one("Records_2"),
    )

    sim.assert_final(frozenset({"Records_1", "Records_2"}), 1)
    assert sim.max_concurrent == 1, "C=1 must prevent any concurrency"
    for _, snap in sim._history:
        assert len(snap["active"]) <= 1


@pytest.mark.asyncio
async def test_edge_concurrency_equals_record_count_allows_full_parallelism():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2

    sim = _Sim(ALL_RECORDS, concurrency=len(ALL_RECORDS))
    acquired_both = asyncio.Barrier(len(ALL_RECORDS))

    async def _both(record: str) -> None:
        await sim._sem.acquire()
        async with sim._lock:
            sim.active.add(record)
            sim.pending.discard(record)
            sim.max_concurrent = max(sim.max_concurrent, len(sim.active))
            sim._check(f"{record}:Acquire", sync_real_sem=True)
        await acquired_both.wait()
        async with sim._lock:
            sim._check(f"{record}:Extract", sync_real_sem=True)
        async with sim._lock:
            sim.active.discard(record)
            sim.completed.add(record)
            sim._check(f"{record}:Release", sync_real_sem=False)
        sim._sem.release()
        await asyncio.sleep(0)
        async with sim._lock:
            sim._check(f"{record}:Finish", sync_real_sem=True)

    await asyncio.gather(*[_both(r) for r in ALL_RECORDS])

    sim.assert_final(frozenset({"Records_1", "Records_2"}), len(ALL_RECORDS))
    assert sim.max_concurrent == len(ALL_RECORDS)
    sim.recheck_history()


@pytest.mark.asyncio
async def test_edge_five_records_concurrency_3():
    records = frozenset({f"rec_{i}" for i in range(5)})
    dag = _make_dag(*records)
    assert dag.node_count == 5

    sim = _Sim(records, concurrency=3)
    await asyncio.gather(*[sim.extract_one(r) for r in records])

    sim.assert_final(records, 3)
    assert sim.max_concurrent <= 3, f"ActiveBounded C=3: max={sim.max_concurrent}"
    sim.recheck_history()


def test_edge_dag_node_not_found_raises():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2
    with pytest.raises(NodeNotFoundError):
        dag.extract_subgraph("Records_999")


def test_edge_empty_dag_has_zero_nodes():
    dag = RegistryDag()
    assert dag.node_count == 0

    records: FrozenSet[str] = frozenset()
    _assert_invariants(
        semaphore=CONCURRENCY,
        active=frozenset(),
        completed=frozenset(),
        pending=frozenset(),
        concurrency=CONCURRENCY,
        records=records,
        ctx="empty_dag_init",
    )


def test_edge_dag_structural_integrity_two_records():
    dag = _make_dag("Records_1", "Records_2")
    assert dag.node_count == 2
    assert dag.edge_count == 0
    assert dag.component_count == 2

    # SubgraphResult.nodes is set[str] (node ID strings, not Node objects)
    sg1 = dag.extract_subgraph("Records_1")
    assert "Records_1" in sg1.nodes

    sg2 = dag.extract_subgraph("Records_2")
    assert "Records_2" in sg2.nodes