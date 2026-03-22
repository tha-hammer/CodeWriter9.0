"""Horizontal contract verification — seam checking across function boundaries."""

from __future__ import annotations

import re

from registry.crawl_types import (
    DispatchKind,
    FnRecord,
    InSource,
    OutKind,
    SeamMismatch,
    SeamReport,
)


# ── Type compatibility ────────────────────────────────────────────

_ALIASES: dict[str, str] = {
    "list": "list",
    "dict": "dict",
    "tuple": "tuple",
    "set": "set",
    "frozenset": "frozenset",
    "optional": "optional",
}


def _normalize_type(t: str) -> str:
    """Normalize a type string for comparison."""
    s = t.strip()
    # Lowercase the outer type name but preserve inner generics casing
    # e.g. "Dict[str, Any]" -> "dict[str, any]"
    s = s.lower()
    # Normalize Optional[X] -> x | none
    m = re.match(r"optional\[(.+)\]", s)
    if m:
        s = f"{m.group(1)} | none"
    return s


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


def _is_union_member(provided: str, expected: str) -> bool:
    """Check if provided is a member of expected's union type."""
    # Parse "x | y | z" into members
    if "|" in expected:
        members = [m.strip() for m in expected.split("|")]
        return provided in members
    if "|" in provided:
        # provided is a union — check if all members are compatible with expected
        members = [m.strip() for m in provided.split("|")]
        if "|" in expected:
            exp_members = {m.strip() for m in expected.split("|")}
            return all(m in exp_members for m in members)
    return False


# ── Single edge checker ──────────────────────────────────────────


def check_seam(caller: FnRecord, callee: FnRecord) -> list[SeamMismatch]:
    """Compare caller's ok outputs against callee's internal_call inputs linked to caller."""
    mismatches: list[SeamMismatch] = []

    # Find callee inputs sourced from this caller
    linked_ins = [
        i
        for i in callee.ins
        if i.source == InSource.INTERNAL_CALL and i.source_uuid == caller.uuid
    ]
    if not linked_ins:
        return []

    # Find caller's ok output
    ok_outs = [o for o in caller.outs if o.name == OutKind.OK]

    for inp in linked_ins:
        if not ok_outs:
            mismatches.append(
                SeamMismatch(
                    caller_uuid=caller.uuid,
                    callee_uuid=callee.uuid,
                    caller_function=caller.function_name,
                    callee_function=callee.function_name,
                    callee_input_name=inp.name,
                    expected_type=inp.type_str,
                    provided_type="",
                    dispatch=inp.dispatch,
                    severity="no_ok_output",
                )
            )
            continue

        # Check if any ok output is compatible
        best_out = ok_outs[0]  # Use first ok output
        if not type_compatible(best_out.type_str, inp.type_str):
            mismatches.append(
                SeamMismatch(
                    caller_uuid=caller.uuid,
                    callee_uuid=callee.uuid,
                    caller_function=caller.function_name,
                    callee_function=callee.function_name,
                    callee_input_name=inp.name,
                    expected_type=inp.type_str,
                    provided_type=best_out.type_str,
                    dispatch=inp.dispatch,
                    severity="type_mismatch",
                )
            )

    return mismatches


# ── Full report generator ────────────────────────────────────────


def check_all_seams(store: "CrawlStore") -> SeamReport:  # noqa: F821
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
            caller_uuid="",
            callee_uuid=row["record_uuid"],
            caller_function="",
            callee_function=row["function_name"],
            callee_input_name=row["name"],
            expected_type=row["type_str"],
            provided_type="",
            dispatch=DispatchKind(row["dispatch"]),
            severity="unresolved",
        )
        for row in unresolved_rows
    ]

    total = len(mismatches) + len(unresolved) + satisfied
    return SeamReport(
        mismatches=mismatches,
        unresolved=unresolved,
        satisfied=satisfied,
        total_edges=total,
    )


# ── Output formatters ────────────────────────────────────────────


def render_seam_report(report: SeamReport, verbose: bool = False) -> str:
    """Human-readable seam report."""
    lines = [f"Seam Report: {report.total_edges} edges analyzed"]
    lines.append(
        f"  {report.satisfied} satisfied, "
        f"{len(report.mismatches)} mismatches, "
        f"{len(report.unresolved)} unresolved"
    )

    if report.mismatches:
        lines.append("\nMismatches:")
        for m in report.mismatches:
            lines.append(
                f"  {m.caller_function}() -> {m.callee_function}().{m.callee_input_name}"
            )
            lines.append(f"    provides: {m.provided_type}, expects: {m.expected_type}")

    if report.unresolved:
        lines.append(f"\nUnresolved ({len(report.unresolved)}):")
        for u in report.unresolved:
            lines.append(
                f"  {u.callee_function}().{u.callee_input_name}: {u.expected_type}"
            )

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
