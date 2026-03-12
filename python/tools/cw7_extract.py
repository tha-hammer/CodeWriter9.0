#!/usr/bin/env python3
"""Extract CW7 requirements + GWT criteria as CW9 register JSON.

Usage:
    python cw7_extract.py <db_path> [--session <session_id>]

    # Pipe directly into cw9 register:
    python cw7_extract.py /path/to/gate-outputs.db --session session-123 \
        | cw9 register /tmp/test-project

    # Counter-app fixture (single session, no filter needed):
    python cw7_extract.py ~/Dev/CodeWriter7/fixtures/pipeline-outputs/counter-app.db \
        | cw9 register /tmp/test-project
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
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
            print("Error: no sessions in database", file=sys.stderr)
            sys.exit(1)
        if len(rows) > 1:
            ids = [r["id"] for r in rows]
            print(
                f"Error: multiple sessions found, use --session: {ids}",
                file=sys.stderr,
            )
            sys.exit(1)
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

        # Derive a name from the when clause (most action-descriptive)
        name = _slugify(when) if when else None

        gwt = {
            "criterion_id": f"cw7-crit-{a['id']}",
            "given": given,
            "when": when,
            "then": then,
            # parent_req uses the raw requirement_id — same string as requirements[].id
            "parent_req": a["requirement_id"],
        }
        if name:
            gwt["name"] = name

        gwts.append(gwt)

    conn.close()
    return {"requirements": requirements, "gwts": gwts}


def copy_context_files(
    plan_path_dir: Path,
    context_dir: Path,
    gwts: list[dict],
) -> int:
    """Copy plan_path files into .cw9/context/ keyed by criterion_id.

    Returns the number of files copied.
    """
    context_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for gwt in gwts:
        crit_id_str = gwt["criterion_id"]  # e.g. "cw7-crit-1046"
        # Extract the numeric ID for matching plan_path filenames
        numeric_id = crit_id_str.split("-")[-1]
        matches = list(plan_path_dir.glob(f"{numeric_id}-*.md"))
        if matches:
            dest = context_dir / f"{crit_id_str}.md"
            dest.write_text(matches[0].read_text())
            copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract CW7 data as CW9 register JSON"
    )
    parser.add_argument("db_path", type=Path, help="Path to CW7 SQLite database")
    parser.add_argument(
        "--session",
        default=None,
        help="Session ID to extract (auto-detected if only one exists)",
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        print(f"Error: {args.db_path} not found", file=sys.stderr)
        sys.exit(1)

    payload = extract(args.db_path, args.session)

    # Summary to stderr (doesn't interfere with JSON on stdout)
    print(
        f"Extracted {len(payload['requirements'])} requirements, "
        f"{len(payload['gwts'])} GWTs from session {args.session or '(auto)'}",
        file=sys.stderr,
    )

    json.dump(payload, sys.stdout, indent=2)
    print()  # trailing newline


if __name__ == "__main__":
    main()
