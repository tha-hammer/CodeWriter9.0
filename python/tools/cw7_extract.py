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
import sys
from pathlib import Path

from registry.cw7 import extract, build_plan_path_map, copy_context_files, _slugify


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
