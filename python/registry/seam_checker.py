"""Horizontal contract verification — seam checking across function boundaries."""

from __future__ import annotations

import re

import json
from pathlib import Path

from registry.crawl_types import (
    BehavioralReport,
    BehavioralViolation,
    CrossCuttingRule,
    DispatchKind,
    FnRecord,
    InSource,
    OutKind,
    SeamMismatch,
    SeamReport,
)


_VALID_POSITIONS = {"pre", "post", "wrap"}


# ── Cross-cutting rules loading (gwt-0068) ──────────────────────


def load_cross_cutting_rules(path: Path | str) -> list[CrossCuttingRule]:
    """Load cross-cutting rules from a JSON file.

    Verifiers: NoPartialResults, ValidPositionOnly, CompleteFields,
    FileAbsentImpliesError, MalformedImpliesError, InvalidSchemaImpliesError,
    SafeResult, EmptyRulesValid.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")

    text = path.read_text()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {path}: {exc}") from exc

    if not isinstance(data, dict) or "rules" not in data:
        raise ValueError(f"Invalid schema: expected object with 'rules' key in {path}")

    rules_list = data["rules"]
    if not isinstance(rules_list, list):
        raise ValueError(f"Invalid schema: 'rules' must be an array in {path}")

    required_fields = {"resource_type", "required_outs", "position"}
    result: list[CrossCuttingRule] = []
    for i, rule_data in enumerate(rules_list):
        if not isinstance(rule_data, dict):
            raise ValueError(f"Rule {i} must be an object in {path}")
        missing = required_fields - set(rule_data.keys())
        if missing:
            raise ValueError(f"Rule {i} missing fields {missing} in {path}")
        if rule_data["position"] not in _VALID_POSITIONS:
            raise ValueError(
                f"Rule {i} has invalid position '{rule_data['position']}'; "
                f"must be one of {_VALID_POSITIONS}"
            )
        result.append(CrossCuttingRule(
            resource_type=rule_data["resource_type"],
            required_outs=list(rule_data["required_outs"]),
            position=rule_data["position"],
        ))

    return result


# ── Resource-type matching (gwt-0069 helper) ────────────────────


def _matches_resource_type(record: FnRecord, rule: CrossCuttingRule) -> bool:
    """Check if a record matches a rule's resource_type.

    Transitional heuristic until records table has a resource_type column.
    """
    rt = rule.resource_type

    if rt == "external_api":
        return record.is_external

    bc = (getattr(record, "boundary_contract", None) or "").lower()
    fp = record.file_path.lower()

    if rt == "database":
        if "database" in bc or "db" in bc:
            return True
        if "/db/" in fp or "_store." in fp:
            return True
        return False

    if rt == "message_queue":
        return "queue" in bc or "mq" in bc

    return False


# ── Behavioral contract checking (gwt-0069) ─────────────────────


def check_behavioral_contracts(
    store: "CrawlStore",  # noqa: F821
    rules: list[CrossCuttingRule],
) -> BehavioralReport:
    """Check behavioral contracts across dependency edges.

    Verifiers: CountConsistency, ViolationComplete, NoFalsePositives,
    NoMatchNoViolation, EmptyEdgesImpliesEmptyReport,
    ZeroViolationsWhenAllCompliant, NoMatchNoCount.
    """
    violations: list[BehavioralViolation] = []
    satisfied = 0

    # In the deps view: dep_uuid = record with the IN (the caller in call terms),
    # caller_uuid = source of the IN (the dependency / callee in call terms).
    # Variable names follow check_all_seams convention.
    edges = store.get_dependency_edges()
    for dep_uuid, caller_uuid, dispatch, _ in edges:
        dependent = store.get_record(dep_uuid)      # the function that calls
        dependency = store.get_record(caller_uuid)   # the function being called
        if dependent is None or dependency is None:
            continue

        # Check which rules match the dependency (the function being called)
        edge_matched = False
        edge_has_violation = False

        for rule in rules:
            if not _matches_resource_type(dependency, rule):
                continue
            edge_matched = True

            # Check required outs on the dependency
            dep_out_types = {o.type_str for o in dependency.outs}
            dep_out_descriptions = {o.description for o in dependency.outs}
            dep_out_all = dep_out_types | dep_out_descriptions

            for required_out in rule.required_outs:
                if required_out not in dep_out_all:
                    edge_has_violation = True
                    violations.append(BehavioralViolation(
                        rule_resource_type=rule.resource_type,
                        callee_uuid=dependency.uuid,
                        callee_function=dependency.function_name,
                        missing_contract=required_out,
                        caller_uuid=dependent.uuid,
                        caller_function=dependent.function_name,
                    ))

        if edge_matched and not edge_has_violation:
            satisfied += 1

    total_checked = satisfied + len(violations)
    return BehavioralReport(
        violations=violations,
        satisfied=satisfied,
        total_checked=total_checked,
    )


# ── Behavioral report formatters (gwt-0070) ─────────────────────


def render_behavioral_report(report: BehavioralReport) -> str:
    """Human-readable behavioral contract report."""
    lines = [f"\nBehavioral Report: {report.total_checked} edges checked"]
    lines.append(
        f"  {report.satisfied} satisfied, "
        f"{len(report.violations)} violations"
    )

    if report.violations:
        lines.append("\nBehavioral Violations:")
        for v in report.violations:
            lines.append(
                f"  {v.caller_function}() -> {v.callee_function}(): "
                f"missing {v.missing_contract} (rule: {v.rule_resource_type})"
            )

    return "\n".join(lines)


def behavioral_report_to_json(report: BehavioralReport) -> dict:
    """Machine-readable behavioral report."""
    from dataclasses import asdict

    return {
        "total_checked": report.total_checked,
        "satisfied": report.satisfied,
        "violations": [asdict(v) for v in report.violations],
    }


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
