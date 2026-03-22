---
date: 2026-03-22T00:00:00Z
researcher: DustyForge
git_commit: 7325cb2
branch: master
repository: CodeWriter9.0
topic: "Horizontal Contract Verification TDD Plan"
tags: [plan, tdd, cw9, seam-checking, type-safety]
status: verified
last_updated: 2026-03-22
last_updated_by: DustyForge
cw9_project: /home/maceo/Dev/CodeWriter9.0
research_doc: thoughts/searchable/shared/research/2026-03-22-horizontal-contract-verification.md
---

# Horizontal Contract Verification (cw9 seams) — TDD Implementation Plan

## Overview

Add a `cw9 seams` command that cross-references crawl.db caller outputs against callee inputs to detect type mismatches at function boundaries. This closes the "horizontal contract" gap: CW9 currently verifies each function meets its own spec (vertical) but never checks that caller outputs satisfy callee inputs (horizontal).

## Research Reference
- Research doc: `thoughts/searchable/shared/research/2026-03-22-horizontal-contract-verification.md`
- CW9 project: `/home/maceo/Dev/CodeWriter9.0`
- crawl.db: 1,567 records (158 extracted), 39 resolved deps, 67 unresolved internal_calls
- 18 concrete type mismatches already found in CW9's own codebase
- Beads: `cosmic-hr-1t71`

## Verified Specs and Traces

All 4 GWTs verified by TLC and bridge artifacts extracted.

### gwt-0064: seam_mismatch_detected (verified, 8 attempts)
- **Given**: caller A with outs [{ok, "Dict[str, Any]"}], callee B with ins [{name: "config", type_str: "Config", source: internal_call, source_uuid: A.uuid}]
- **When**: `check_seam(A.uuid, B.uuid)` is called
- **Then**: SeamMismatch reported with severity "type_mismatch"
- **Verified spec**: `templates/pluscal/instances/gwt-0064.tla`
- **Bridge artifacts**: `python/tests/generated/gwt-0064_bridge_artifacts.json`
  - data_structures: 1 — `SeamMismatchDetectedState`
  - operations: 3 — `StartCheck`, `CheckTypes`, `Finish`
  - verifiers: 5 — `CompatPairs`, `SeverityCorrect`, `MismatchDetected`, `MismatchCorrect`, `NoSpuriousMismatches`
  - assertions: 5, simulation traces: 10

### gwt-0065: seam_satisfied_no_report (verified, 1 attempt)
- **Given**: caller A with outs [{ok, "list[FnRecord]"}], callee B with ins [{name: "records", type_str: "list[FnRecord]", source: internal_call, source_uuid: A.uuid}]
- **When**: `check_seam(A.uuid, B.uuid)` is called
- **Then**: no SeamMismatch reported — types are compatible
- **Verified spec**: `templates/pluscal/instances/gwt-0065.tla`
- **Bridge artifacts**: `python/tests/generated/gwt-0065_bridge_artifacts.json`
  - data_structures: 1 — `SeamSatisfiedNoReportState`
  - operations: 4 — `Start`, `CheckSeam`, `ConfirmCompatible`, `Finish`
  - verifiers: 4 — `PhaseValid`, `ReflexiveCompatPairs`, `NoFalsePositive`, `SeamSatisfied`
  - assertions: 4, simulation traces: 10

### gwt-0066: seam_unresolved_flagged (verified, 3 attempts)
- **Given**: callee B with ins [{name: "data", source: internal_call, source_uuid: NULL}]
- **When**: `check_all_seams()` iterates deps view and unresolved ins
- **Then**: UnresolvedSeam reported with severity "unresolved"
- **Verified spec**: `templates/pluscal/instances/gwt-0066.tla`
- **Bridge artifacts**: `python/tests/generated/gwt-0066_bridge_artifacts.json`
  - data_structures: 1 — `SeamUnresolvedFlaggedState`
  - operations: 4 — `Iterate`, `PickInput`, `CheckInput`, `Terminate`
  - verifiers: 5 — `AllScanned`, `UnresolvedCorrect`, `NoFalseUnresolved`, `UnresolvedNotInMismatches`, `BoundedCheck`
  - assertions: 5, simulation traces: 10

### gwt-0067: seam_report_complete (verified, 6 attempts)
- **Given**: crawl.db with N edges, M mismatches, K unresolved, (N-M-K) satisfied
- **When**: `check_all_seams()` runs to completion
- **Then**: SeamReport.total_edges = len(mismatches) + len(unresolved) + satisfied
- **Verified spec**: `templates/pluscal/instances/gwt-0067.tla`
- **Bridge artifacts**: `python/tests/generated/gwt-0067_bridge_artifacts.json`
  - data_structures: 1 — `SeamReportCompleteState`
  - operations: 4 — `InitReport`, `Processing`, `ProcessEdge`, `FinalizeReport`
  - verifiers: 8 — `TotalEdges`, `CurrentSum`, `CompletenessHolds`, `MonotonicProgress`, `NonNegative`, `TotalIsN`, `FinalCorrectness`, `SeamInvariants`
  - assertions: 8, simulation traces: 10 (64 steps each, modeling 30 edges: 10 mismatches + 10 unresolved + 10 satisfied)

### Combined Verified Invariants (22 total)

The formal models collectively verify these properties:

**Type Checking (gwt-0064/0065)**:
- `MismatchDetected`: incompatible types always produce a SeamMismatch
- `NoSpuriousMismatches`: every reported mismatch corresponds to a real incompatibility
- `MismatchCorrect`: mismatch fields (expected_type, provided_type, severity) are accurate
- `SeverityCorrect`: all mismatches have severity="type_mismatch"
- `NoFalsePositive`: compatible types never produce a mismatch
- `SeamSatisfied`: at completion, compatible seams have empty result
- `ReflexiveCompatPairs`: type_compatible(T, T) = TRUE for all T

**Unresolved Detection (gwt-0066)**:
- `AllScanned`: every input is checked
- `UnresolvedCorrect`: exactly the NULL-source_uuid inputs are flagged
- `NoFalseUnresolved`: resolved inputs are never flagged as unresolved
- `UnresolvedNotInMismatches`: unresolved items don't appear in mismatches list

**Report Completeness (gwt-0067)**:
- `CompletenessHolds`: total_edges = mismatches + unresolved + satisfied
- `MonotonicProgress`: sum only increases during processing
- `NonNegative`: all counts >= 0
- `TotalIsN`: total matches input edge count
- `FinalCorrectness`: at done phase, all counts are final and correct

## What We're NOT Doing
- Tier B (bridge port extraction) — future work
- Tier C (session-gap detection) — future work
- Error-path matching (matching callee ins against caller `err` outs)
- Polymorphic dispatch resolution (attribute/callback/protocol dispatch types)
- Auto-fix or auto-suggest for mismatches

---

## Step 1: SeamMismatch and SeamReport Data Types

### CW9 Binding
- **GWTs**: gwt-0064, gwt-0065, gwt-0066, gwt-0067 (all reference these types)
- **File**: `python/registry/crawl_types.py` (add after line 215, after TestReference)

### Implementation

```python
@dataclass
class SeamMismatch:
    """A detected mismatch or unresolved edge at a function boundary."""
    caller_uuid: str          # empty string for unresolved
    callee_uuid: str
    caller_function: str      # empty string for unresolved
    callee_function: str
    callee_input_name: str
    expected_type: str        # callee's InField.type_str
    provided_type: str        # caller's OutField.type_str (empty for unresolved)
    dispatch: DispatchKind
    severity: str             # "type_mismatch" | "unresolved" | "no_ok_output"


@dataclass
class SeamReport:
    """Complete seam analysis across all dependency edges."""
    mismatches: list[SeamMismatch]    # severity in {"type_mismatch", "no_ok_output"}
    unresolved: list[SeamMismatch]    # severity == "unresolved"
    satisfied: int                     # count of compatible seams
    total_edges: int                   # = len(mismatches) + len(unresolved) + satisfied
```

### Success Criteria
- [x] Types importable: `from registry.crawl_types import SeamMismatch, SeamReport`
- [x] SeamMismatch fields match the spec
- [x] SeamReport completeness invariant: `total_edges == len(mismatches) + len(unresolved) + satisfied`

---

## Step 2: type_compatible() — Type Compatibility Function

### CW9 Binding
- **GWTs**: gwt-0064 (`CompatPairs` verifier), gwt-0065 (`ReflexiveCompatPairs` verifier)
- **Bridge operations**: gwt-0064 `CheckTypes`, gwt-0065 `CheckSeam`
- **Must satisfy verified invariants**: `CompatPairs`, `ReflexiveCompatPairs`, `NoFalsePositive`
- **File**: `python/registry/seam_checker.py` (new file)

### TDD Cycle

#### Red: Failing Tests

```python
# test_seam_checker.py (hand-written for infrastructure — per CLAUDE.md rules)
from registry.seam_checker import type_compatible

# Tier 1: Exact match
def test_exact_match():
    assert type_compatible("list[FnRecord]", "list[FnRecord]") is True

def test_exact_mismatch():
    assert type_compatible("Dict[str, Any]", "Config") is False

# Tier 2: Normalized match
def test_case_insensitive():
    assert type_compatible("dict[str, Any]", "Dict[str, Any]") is True

def test_list_alias():
    assert type_compatible("List[int]", "list[int]") is True

def test_optional_alias():
    assert type_compatible("Optional[str]", "str | None") is True

# Tier 3: Structural subtype
def test_narrower_satisfies_union():
    assert type_compatible("str", "str | None") is True

def test_any_satisfies_anything():
    assert type_compatible("Any", "Config") is True

def test_incompatible():
    assert type_compatible("int", "str") is False

# Reflexivity
def test_reflexive():
    for t in ["str", "int", "list[FnRecord]", "Dict[str, Any]", "None"]:
        assert type_compatible(t, t) is True
```

#### Green: Minimal Implementation

```python
# python/registry/seam_checker.py

def type_compatible(provided: str, expected: str) -> bool:
    """Check if provided type string is compatible with expected type string.

    Three-tier compatibility:
    1. Exact match
    2. Normalized match (case-insensitive, alias resolution)
    3. Structural subtype (Any matches all, narrower satisfies union)
    """
    # Tier 1: exact
    if provided == expected:
        return True

    # Tier 2: normalized
    p_norm = _normalize_type(provided)
    e_norm = _normalize_type(expected)
    if p_norm == e_norm:
        return True

    # Tier 3: structural
    if p_norm == "any" or e_norm == "any":
        return True
    if _is_union_member(p_norm, e_norm):
        return True

    return False
```

### Success Criteria
- [x] All type_compatible tests pass
- [x] Reflexivity holds for all tested types
- [x] No false positives for genuinely incompatible types

---

## Step 3: check_seam() — Single Edge Checker

### CW9 Binding
- **GWTs**: gwt-0064 (`MismatchDetected`, `MismatchCorrect`, `NoSpuriousMismatches`, `SeverityCorrect`), gwt-0065 (`SeamSatisfied`, `NoFalsePositive`)
- **Bridge operations**: gwt-0064 `StartCheck` → `CheckTypes` → `Finish`, gwt-0065 `Start` → `CheckSeam` → `ConfirmCompatible` → `Finish`
- **File**: `python/registry/seam_checker.py`

### TDD Cycle

#### Red: Failing Tests (from context files)

```python
from registry.seam_checker import check_seam
from registry.crawl_types import FnRecord, InField, OutField, InSource, OutKind, DispatchKind

def test_mismatch_detected():
    """gwt-0064: type mismatch produces SeamMismatch."""
    caller = FnRecord(
        uuid="aaaa-1111", function_name="get_config", file_path="a.py",
        src_hash="abc", ins=[], do_description="returns config dict",
        outs=[OutField(name=OutKind.OK, type_str="Dict[str, Any]")]
    )
    callee = FnRecord(
        uuid="bbbb-2222", function_name="process", file_path="b.py",
        src_hash="def",
        ins=[InField(name="config", type_str="Config", source=InSource.INTERNAL_CALL,
                     source_uuid="aaaa-1111")],
        do_description="processes config", outs=[]
    )
    mismatches = check_seam(caller, callee)
    assert len(mismatches) == 1
    assert mismatches[0].severity == "type_mismatch"
    assert mismatches[0].expected_type == "Config"
    assert mismatches[0].provided_type == "Dict[str, Any]"

def test_satisfied_no_report():
    """gwt-0065: compatible types produce empty result."""
    caller = FnRecord(
        uuid="aaaa-1111", function_name="get_records", file_path="a.py",
        src_hash="abc", ins=[], do_description="returns records",
        outs=[OutField(name=OutKind.OK, type_str="list[FnRecord]")]
    )
    callee = FnRecord(
        uuid="bbbb-2222", function_name="process_records", file_path="b.py",
        src_hash="def",
        ins=[InField(name="records", type_str="list[FnRecord]",
                     source=InSource.INTERNAL_CALL, source_uuid="aaaa-1111")],
        do_description="processes records", outs=[]
    )
    assert check_seam(caller, callee) == []

def test_no_ok_output():
    """Caller has no ok output — severity is no_ok_output."""
    caller = FnRecord(
        uuid="aaaa-1111", function_name="do_effect", file_path="a.py",
        src_hash="abc", ins=[], do_description="side effect only",
        outs=[OutField(name=OutKind.SIDE_EFFECT, type_str="None")]
    )
    callee = FnRecord(
        uuid="bbbb-2222", function_name="use_result", file_path="b.py",
        src_hash="def",
        ins=[InField(name="result", type_str="str",
                     source=InSource.INTERNAL_CALL, source_uuid="aaaa-1111")],
        do_description="uses result", outs=[]
    )
    mismatches = check_seam(caller, callee)
    assert len(mismatches) == 1
    assert mismatches[0].severity == "no_ok_output"
```

#### Green: Implementation

```python
def check_seam(caller: FnRecord, callee: FnRecord) -> list[SeamMismatch]:
    """Compare caller's ok outputs against callee's internal_call inputs linked to caller."""
    mismatches = []

    # Find callee inputs sourced from this caller
    linked_ins = [i for i in callee.ins
                  if i.source == InSource.INTERNAL_CALL and i.source_uuid == caller.uuid]
    if not linked_ins:
        return []

    # Find caller's ok output
    ok_outs = [o for o in caller.outs if o.name == OutKind.OK]

    for inp in linked_ins:
        if not ok_outs:
            mismatches.append(SeamMismatch(
                caller_uuid=caller.uuid, callee_uuid=callee.uuid,
                caller_function=caller.function_name, callee_function=callee.function_name,
                callee_input_name=inp.name, expected_type=inp.type_str,
                provided_type="", dispatch=inp.dispatch, severity="no_ok_output",
            ))
            continue

        # Check if any ok output is compatible
        best_out = ok_outs[0]  # Use first ok output
        if not type_compatible(best_out.type_str, inp.type_str):
            mismatches.append(SeamMismatch(
                caller_uuid=caller.uuid, callee_uuid=callee.uuid,
                caller_function=caller.function_name, callee_function=callee.function_name,
                callee_input_name=inp.name, expected_type=inp.type_str,
                provided_type=best_out.type_str, dispatch=inp.dispatch, severity="type_mismatch",
            ))

    return mismatches
```

### Success Criteria
- [x] Mismatch detected for incompatible types (gwt-0064)
- [x] Empty result for compatible types (gwt-0065)
- [x] no_ok_output severity when caller has no ok output

---

## Step 4: CrawlStore Methods — get_dependency_edges() and get_unresolved_internal_calls()

### CW9 Binding
- **GWTs**: gwt-0066, gwt-0067
- **File**: `python/registry/crawl_store.py` (add after `validate_completeness()` at line 590)

### TDD Cycle

#### Red: Failing Tests

```python
def test_get_dependency_edges(tmp_path):
    """Resolved deps view returns all edges with non-NULL source_uuid."""
    from registry.crawl_store import CrawlStore
    from registry.crawl_types import FnRecord, InField, OutField, InSource, OutKind

    db = tmp_path / "crawl.db"
    with CrawlStore(db) as store:
        caller = FnRecord(uuid="aaaa-1111", function_name="caller", file_path="a.py",
                          src_hash="a", ins=[], do_description="caller",
                          outs=[OutField(name=OutKind.OK, type_str="str")])
        callee = FnRecord(uuid="bbbb-2222", function_name="callee", file_path="b.py",
                          src_hash="b",
                          ins=[InField(name="x", type_str="str", source=InSource.INTERNAL_CALL,
                                       source_uuid="aaaa-1111")],
                          do_description="callee",
                          outs=[OutField(name=OutKind.OK, type_str="bool")])
        store.upsert_record(caller)
        store.upsert_record(callee)

        edges = store.get_dependency_edges()
        assert len(edges) == 1
        assert edges[0][0] == "bbbb-2222"  # dependent_uuid
        assert edges[0][1] == "aaaa-1111"  # dependency_uuid

def test_get_unresolved_internal_calls(tmp_path):
    """Unresolved internal_call ins returned as dicts."""
    from registry.crawl_store import CrawlStore
    from registry.crawl_types import FnRecord, InField, OutField, InSource, OutKind

    db = tmp_path / "crawl.db"
    with CrawlStore(db) as store:
        rec = FnRecord(uuid="bbbb-2222", function_name="callee", file_path="b.py",
                       src_hash="b",
                       ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                                    source_uuid=None, source_function="unknown")],
                       do_description="callee",
                       outs=[OutField(name=OutKind.OK, type_str="bool")])
        store.upsert_record(rec)

        unresolved = store.get_unresolved_internal_calls()
        assert len(unresolved) == 1
        assert unresolved[0]["name"] == "data"
        assert unresolved[0]["function_name"] == "callee"
```

#### Green: Implementation

```python
# In CrawlStore, after validate_completeness():

def get_dependency_edges(self) -> list[tuple[str, str, str, str | None]]:
    """All (dependent_uuid, dependency_uuid, dispatch, dispatch_candidates) from deps view."""
    rows = self.conn.execute("SELECT * FROM deps").fetchall()
    return [(r["dependent_uuid"], r["dependency_uuid"], r["dispatch"],
             r["dispatch_candidates"]) for r in rows]

def get_unresolved_internal_calls(self) -> list[dict]:
    """ins with source='internal_call' and source_uuid IS NULL."""
    rows = self.conn.execute(
        """SELECT i.record_uuid, i.name, i.type_str, i.source_function,
                  i.dispatch, r.function_name, r.file_path
           FROM ins i
           JOIN records r ON i.record_uuid = r.uuid
           WHERE i.source = 'internal_call' AND i.source_uuid IS NULL"""
    ).fetchall()
    return [dict(r) for r in rows]
```

### Success Criteria
- [x] `get_dependency_edges()` returns all resolved deps view rows
- [x] `get_unresolved_internal_calls()` returns dicts with function_name + input name
- [x] Both methods return empty lists on empty database

---

## Step 5: check_all_seams() — Full Report Generator

### CW9 Binding
- **GWTs**: gwt-0066 (`AllScanned`, `UnresolvedCorrect`, `NoFalseUnresolved`, `UnresolvedNotInMismatches`), gwt-0067 (`CompletenessHolds`, `MonotonicProgress`, `NonNegative`, `TotalIsN`, `FinalCorrectness`)
- **Bridge operations**: gwt-0066 `Iterate` → `PickInput` → `CheckInput` → `Terminate`, gwt-0067 `InitReport` → `Processing` → `ProcessEdge` → `FinalizeReport`
- **File**: `python/registry/seam_checker.py`

### TDD Cycle

#### Red: Failing Tests

```python
def test_unresolved_flagged(tmp_path):
    """gwt-0066: unresolved internal_call inputs produce unresolved entries."""
    from registry.seam_checker import check_all_seams
    from registry.crawl_store import CrawlStore
    from registry.crawl_types import FnRecord, InField, OutField, InSource, OutKind

    db = tmp_path / "crawl.db"
    with CrawlStore(db) as store:
        rec = FnRecord(uuid="bbbb-2222", function_name="process_data", file_path="b.py",
                       src_hash="def",
                       ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                                    source_uuid=None, source_function="unknown_fn")],
                       do_description="processes data",
                       outs=[OutField(name=OutKind.OK, type_str="bool")])
        store.upsert_record(rec)

        report = check_all_seams(store)
        assert len(report.unresolved) == 1
        assert report.unresolved[0].severity == "unresolved"
        assert report.unresolved[0].callee_input_name == "data"

def test_report_completeness(tmp_path):
    """gwt-0067: total_edges = mismatches + unresolved + satisfied."""
    from registry.seam_checker import check_all_seams
    from registry.crawl_store import CrawlStore
    from registry.crawl_types import FnRecord, InField, OutField, InSource, OutKind

    db = tmp_path / "crawl.db"
    with CrawlStore(db) as store:
        # Caller A
        store.upsert_record(FnRecord(
            uuid="aaaa-1111", function_name="get_name", file_path="a.py",
            src_hash="abc", ins=[], do_description="returns name",
            outs=[OutField(name=OutKind.OK, type_str="str")]
        ))
        # Callee B1 — satisfied (str == str)
        store.upsert_record(FnRecord(
            uuid="bbbb-2222", function_name="use_name", file_path="b.py",
            src_hash="def",
            ins=[InField(name="name", type_str="str", source=InSource.INTERNAL_CALL,
                         source_uuid="aaaa-1111")],
            do_description="uses name",
            outs=[OutField(name=OutKind.OK, type_str="bool")]
        ))
        # Callee B2 — mismatch (str vs int)
        store.upsert_record(FnRecord(
            uuid="cccc-3333", function_name="count_items", file_path="c.py",
            src_hash="ghi",
            ins=[InField(name="count", type_str="int", source=InSource.INTERNAL_CALL,
                         source_uuid="aaaa-1111")],
            do_description="counts",
            outs=[OutField(name=OutKind.OK, type_str="int")]
        ))
        # Callee B3 — unresolved
        store.upsert_record(FnRecord(
            uuid="dddd-4444", function_name="process_data", file_path="d.py",
            src_hash="jkl",
            ins=[InField(name="data", type_str="dict", source=InSource.INTERNAL_CALL,
                         source_uuid=None, source_function="unknown")],
            do_description="processes",
            outs=[OutField(name=OutKind.OK, type_str="bool")]
        ))

        report = check_all_seams(store)

        # Completeness invariant (gwt-0067: CompletenessHolds, TotalIsN, FinalCorrectness)
        assert report.total_edges == len(report.mismatches) + len(report.unresolved) + report.satisfied
        assert report.total_edges == 3
        assert report.satisfied == 1
        assert len(report.mismatches) == 1
        assert len(report.unresolved) == 1

        # NonNegative invariant (gwt-0067)
        assert report.satisfied >= 0
        assert report.total_edges >= 0
        assert len(report.mismatches) >= 0
        assert len(report.unresolved) >= 0

        # UnresolvedNotInMismatches invariant (gwt-0066): disjointness
        unresolved_callees = {u.callee_uuid for u in report.unresolved}
        mismatch_callees = {m.callee_uuid for m in report.mismatches}
        assert not unresolved_callees & mismatch_callees

def test_empty_report(tmp_path):
    """gwt-0067: empty crawl.db produces zero-edge report with completeness invariant."""
    from registry.seam_checker import check_all_seams
    from registry.crawl_store import CrawlStore

    db = tmp_path / "crawl.db"
    with CrawlStore(db) as store:
        report = check_all_seams(store)
        assert report.total_edges == 0
        assert report.satisfied == 0
        assert report.mismatches == []
        assert report.unresolved == []
        assert report.total_edges == len(report.mismatches) + len(report.unresolved) + report.satisfied
```

#### Green: Implementation

```python
def check_all_seams(store: "CrawlStore") -> SeamReport:
    """Run seam analysis across all dependency edges in crawl.db."""
    mismatches: list[SeamMismatch] = []
    satisfied = 0

    # Process resolved edges from deps view
    edges = store.get_dependency_edges()
    for dep_uuid, caller_uuid, dispatch, _ in edges:
        caller = store.get_record(caller_uuid)
        callee = store.get_record(dep_uuid)
        if caller is None or callee is None:
            continue
        edge_mismatches = check_seam(caller, callee)
        if edge_mismatches:
            mismatches.extend(edge_mismatches)
        else:
            satisfied += 1

    # Process unresolved edges
    unresolved_rows = store.get_unresolved_internal_calls()
    unresolved = [
        SeamMismatch(
            caller_uuid="", callee_uuid=row["record_uuid"],
            caller_function="", callee_function=row["function_name"],
            callee_input_name=row["name"], expected_type=row["type_str"],
            provided_type="", dispatch=DispatchKind(row["dispatch"]),
            severity="unresolved",
        )
        for row in unresolved_rows
    ]

    total = len(mismatches) + len(unresolved) + satisfied
    return SeamReport(mismatches=mismatches, unresolved=unresolved,
                      satisfied=satisfied, total_edges=total)
```

### Notes
- `TotalEdges` and `CurrentSum` (gwt-0067 bridge verifiers) are computed expressions, not boolean predicates — they feed into `CompletenessHolds` and `FinalCorrectness` but don't need dedicated test assertions.

### Success Criteria
- [x] Unresolved inputs flagged with severity="unresolved" (gwt-0066)
- [x] Completeness invariant holds: `total_edges == len(mismatches) + len(unresolved) + satisfied` (gwt-0067)
- [x] Every edge accounted for — no edge counted twice or missed
- [x] Unresolved and mismatch sets are disjoint (gwt-0066: `UnresolvedNotInMismatches`)
- [x] All counts are non-negative (gwt-0067: `NonNegative`)
- [x] Empty crawl.db produces zero-edge report (gwt-0067: degenerate case)

---

## Step 6: render_seam_report() and seam_report_to_json() — Output Formatters

### CW9 Binding
- **File**: `python/registry/seam_checker.py`

### Implementation

```python
def render_seam_report(report: SeamReport, verbose: bool = False) -> str:
    """Human-readable seam report."""
    lines = [f"Seam Report: {report.total_edges} edges analyzed"]
    lines.append(f"  {report.satisfied} satisfied, "
                 f"{len(report.mismatches)} mismatches, "
                 f"{len(report.unresolved)} unresolved")

    if report.mismatches:
        lines.append("\nMismatches:")
        for m in report.mismatches:
            lines.append(f"  {m.caller_function}() -> {m.callee_function}().{m.callee_input_name}")
            lines.append(f"    provides: {m.provided_type}, expects: {m.expected_type}")

    if report.unresolved:
        lines.append(f"\nUnresolved ({len(report.unresolved)}):")
        for u in report.unresolved:
            lines.append(f"  {u.callee_function}().{u.callee_input_name}: {u.expected_type}")

    return "\n".join(lines)

def seam_report_to_json(report: SeamReport) -> dict:
    """Machine-readable seam report."""
    from dataclasses import asdict
    return {
        "total_edges": report.total_edges,
        "satisfied": report.satisfied,
        "mismatches": [asdict(m) for m in report.mismatches],
        "unresolved": [asdict(u) for u in report.unresolved],
    }
```

### Success Criteria
- [x] render_seam_report produces readable output
- [x] seam_report_to_json produces valid JSON-serializable dict
- [x] Both handle empty reports gracefully

---

## Step 7: cmd_seams() — CLI Command

### CW9 Binding
- **File**: `python/registry/cli.py`
- Add to `_add_crawl_commands()` (line 1838)
- Add to `_DISPATCH` (line 1988)

### Implementation

Follows `cmd_stale` pattern (line 1655):

```python
def cmd_seams(args: argparse.Namespace) -> int:
    """Check seam compatibility across function boundaries in crawl.db."""
    target = Path(args.target_dir).resolve()
    state_root = _require_cw9(target)
    if state_root is None:
        return 1

    crawl_db_path = state_root / "crawl.db"
    if not crawl_db_path.exists():
        print("No crawl.db found. Run: cw9 ingest", file=sys.stderr)
        return 1

    from registry.crawl_store import CrawlStore
    from registry.seam_checker import check_all_seams, render_seam_report, seam_report_to_json

    with CrawlStore(crawl_db_path) as store:
        report = check_all_seams(store)

    if getattr(args, "output_json", False):
        import json
        print(json.dumps(seam_report_to_json(report), indent=2))
    else:
        print(render_seam_report(report, verbose=getattr(args, "verbose", False)))

    return 1 if report.mismatches else 0
```

Parser registration in `_add_crawl_commands()`:
```python
p_seams = sub.add_parser("seams", help="Check seam compatibility across function boundaries")
p_seams.add_argument("target_dir", nargs="?", default=".")
p_seams.add_argument("--json", action="store_true", dest="output_json")
p_seams.add_argument("--verbose", action="store_true")
p_seams.add_argument("--file", default=None, help="Filter to functions in this file")
p_seams.add_argument("--function", default=None, help="Filter to this function name")
```

Dispatch entry: `"seams": cmd_seams`

### Success Criteria
- [x] `cw9 seams .` runs against CW9's own crawl.db
- [x] Exit code 0 when no mismatches, 1 when mismatches found
- [x] `--json` produces valid JSON output
- [ ] `--verbose` includes satisfied seams (not yet implemented — verbose mode deferred)

---

## Implementation Order

| Step | File | What | Depends On |
|---|---|---|---|
| 1 | `crawl_types.py` | SeamMismatch, SeamReport dataclasses | nothing |
| 2 | `seam_checker.py` | type_compatible() | Step 1 |
| 3 | `seam_checker.py` | check_seam() | Steps 1, 2 |
| 4 | `crawl_store.py` | get_dependency_edges(), get_unresolved_internal_calls() | nothing |
| 5 | `seam_checker.py` | check_all_seams() | Steps 1-4 |
| 6 | `seam_checker.py` | render_seam_report(), seam_report_to_json() | Steps 1, 5 |
| 7 | `cli.py` | cmd_seams, parser, dispatch | Steps 1-6 |

## Integration Testing

After all steps:
```bash
# Run against CW9's own codebase
cw9 seams /home/maceo/Dev/CodeWriter9.0

# Verify JSON output
cw9 seams /home/maceo/Dev/CodeWriter9.0 --json | python3 -m json.tool

# All tests pass
cd /home/maceo/Dev/CodeWriter9.0/python && python3 -m pytest tests/ -x
```

Expected results from CW9's own crawl.db:
- 39 resolved deps → some mismatches + some satisfied
- 67 unresolved internal_calls → 67 unresolved entries
- total_edges = 39 + 67 = 106
- At least 2 genuine type mismatches (extract_one→_dfs_extract, extract_module_name→compile_compose_verify)

## Verification (Post-Implementation)

```bash
# Re-ingest to pick up new seam_checker.py
cw9 ingest python/registry /home/maceo/Dev/CodeWriter9.0 --incremental

# Check staleness
cw9 stale /home/maceo/Dev/CodeWriter9.0

# Re-verify GWTs if specs exist
cw9 loop gwt-0064 /home/maceo/Dev/CodeWriter9.0 --context-file .cw9/context/gwt-0064.md
```

## References
- Research: `thoughts/searchable/shared/research/2026-03-22-horizontal-contract-verification.md`
- Context files: `.cw9/context/gwt-0064.md` through `gwt-0067.md`
- Beads: `cosmic-hr-1t71`
