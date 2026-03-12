"""CW7 database extraction — extract requirements + GWT criteria for CW9.

Library module: raises ValueError on error (no sys.exit).
For CLI use, see tools/cw7_extract.py.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


def _slugify(text: str, max_len: int = 40) -> str:
    """Derive a snake_case name from free text."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s[:max_len].rstrip("_")


def extract(db_path: Path, session_id: str | None = None) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Resolve session
    if session_id is None:
        rows = conn.execute("SELECT id FROM sessions").fetchall()
        if len(rows) == 0:
            conn.close()
            raise ValueError("No sessions found in database")
        if len(rows) > 1:
            ids = [r["id"] for r in rows]
            conn.close()
            raise ValueError(f"Multiple sessions found, use --session: {ids}")
        session_id = rows[0]["id"]

    # Requirements
    req_rows = conn.execute(
        "SELECT requirement_id, description FROM requirements "
        "WHERE session_id = ? ORDER BY requirement_id",
        (session_id,),
    ).fetchall()

    requirements = []
    for r in req_rows:
        requirements.append({
            "id": r["requirement_id"],
            "text": r["description"],
        })

    # GWT acceptance criteria
    ac_rows = conn.execute(
        "SELECT id, requirement_id, given_clause, when_clause, then_clause "
        "FROM acceptance_criteria "
        "WHERE session_id = ? AND format = 'gwt' "
        "ORDER BY id",
        (session_id,),
    ).fetchall()

    gwts = []
    for a in ac_rows:
        given = a["given_clause"] or ""
        when = a["when_clause"] or ""
        then = a["then_clause"] or ""

        name = _slugify(when) if when else None

        gwt = {
            "criterion_id": f"cw7-crit-{a['id']}",
            "given": given,
            "when": when,
            "then": then,
            "parent_req": a["requirement_id"],
        }
        if name:
            gwt["name"] = name

        gwts.append(gwt)

    conn.close()
    return {"requirements": requirements, "gwts": gwts}


def build_plan_path_map(db_path: Path, session_id: str) -> dict[int, int]:
    """Build acceptance_criterion_id -> plan_path_id mapping from CW7 DB.

    Returns {acceptance_criterion_id: plan_path_id}.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, acceptance_criterion_id FROM plan_paths "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return {r["acceptance_criterion_id"]: r["id"] for r in rows}


def copy_context_files(
    plan_path_dir: Path,
    context_dir: Path,
    gwts: list[dict],
    plan_path_map: dict[int, int] | None = None,
) -> int:
    """Copy plan_path files into context dir keyed by criterion_id.

    Returns the number of files copied.
    """
    context_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for gwt in gwts:
        crit_id_str = gwt["criterion_id"]  # e.g. "cw7-crit-3328"
        ac_id = int(crit_id_str.split("-")[-1])

        file_id = plan_path_map.get(ac_id, ac_id) if plan_path_map else ac_id
        matches = list(plan_path_dir.glob(f"{file_id}-*.md"))
        if matches:
            dest = context_dir / f"{crit_id_str}.md"
            dest.write_text(matches[0].read_text())
            copied += 1
    return copied
