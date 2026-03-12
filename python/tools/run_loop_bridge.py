#!/usr/bin/env python3
"""Run the full CW9 pipeline with real LLM calls.

End-to-end: CW7 extract → cw9 init → cw9 extract → cw9 register → cw9 loop → cw9 bridge

This is the *real* pipeline script — unlike test_loop_bridge.py (which has
a synthetic bridge-only mode), this always calls the LLM via claude-agent-sdk.

Usage:
    # Full pipeline on counter-app fixture:
    python run_loop_bridge.py

    # Custom CW7 database:
    python run_loop_bridge.py --db ~/Dev/CodeWriter7/fixtures/pipeline-outputs/counter-app.db

    # Target specific GWT(s):
    python run_loop_bridge.py --gwt gwt-0001
    python run_loop_bridge.py --gwt gwt-0001 --gwt gwt-0002

    # Skip setup (project already initialized + registered):
    python run_loop_bridge.py --skip-setup --project-dir /tmp/cw9-counter

    # Loop only (no bridge):
    python run_loop_bridge.py --loop-only

    # Resume from loop (bridge only, specs already verified):
    python run_loop_bridge.py --bridge-only --skip-setup --project-dir /tmp/cw9-counter

    # Adjust retry budget:
    python run_loop_bridge.py --max-retries 3
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure registry is importable
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

from registry.cli import main as cw9_main

# Default CW7 fixture
CW7_DEFAULT_DB = Path(
    os.environ.get(
        "CW7_FIXTURE_DB",
        os.path.expanduser(
            "/home/maceo/Dev/CodeWriter7/.cw7/gate-outputs.db"
        ),
    )
)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _inline_fixture() -> dict:
    """Minimal counter-app fixture when CW7 DB isn't available."""
    return {
        "requirements": [
            {"id": "REQ-F001", "text": "Display a counter value starting at 0"},
            {"id": "REQ-F002", "text": "Increment button adds 1 to the counter"},
            {"id": "REQ-F003", "text": "Decrement button subtracts 1 from the counter"},
            {"id": "REQ-NF001", "text": "Counter cannot go below 0"},
        ],
        "gwts": [
            {
                "criterion_id": "cw7-crit-1",
                "given": "the application loads for the first time",
                "when": "the counter component renders",
                "then": "the counter displays 0",
                "parent_req": "REQ-F001",
                "name": "initial_counter_display",
            },
            {
                "criterion_id": "cw7-crit-2",
                "given": "the counter value is 5",
                "when": "the user clicks the increment button",
                "then": "the counter value becomes 6",
                "parent_req": "REQ-F002",
                "name": "counter_increment",
            },
            {
                "criterion_id": "cw7-crit-3",
                "given": "the counter value is 3",
                "when": "the user clicks the decrement button",
                "then": "the counter value becomes 2",
                "parent_req": "REQ-F003",
                "name": "counter_decrement",
            },
            {
                "criterion_id": "cw7-crit-6",
                "given": "the counter value is 0",
                "when": "the user clicks the decrement button",
                "then": "the counter value remains 0",
                "parent_req": "REQ-NF001",
                "name": "counter_floor_constraint",
            },
        ],
    }


# ── Phase 0: Setup ──────────────────────────────────────────────────────

def setup_project(project_dir: Path, db_path: Path, session_id: str | None = None,
                   plan_path_dir: Path | None = None) -> dict:
    """cw9 init → cw9 extract → cw7_extract | cw9 register."""
    import unittest.mock as mock

    log(f"\n{'─' * 60}")
    log("Phase 0: Project Setup")
    log(f"{'─' * 60}")

    # init
    rc = cw9_main(["init", str(project_dir), "--ensure"])
    if rc != 0:
        rc = cw9_main(["init", str(project_dir)])
    assert rc == 0, f"cw9 init failed (rc={rc})"
    log("  [1/3] cw9 init ........... OK")

    # extract
    rc = cw9_main(["extract", str(project_dir)])
    assert rc == 0, f"cw9 extract failed (rc={rc})"
    log("  [2/3] cw9 extract ........ OK")

    # register from CW7 fixture
    if db_path.exists():
        from tools.cw7_extract import extract as cw7_extract
        payload = cw7_extract(db_path, session_id)
        log(f"  CW7 source: {db_path}")
    else:
        log(f"  WARNING: {db_path} not found — using inline fixture")
        payload = _inline_fixture()

    # Copy plan_path context files to .cw9/context/
    if plan_path_dir is not None:
        from tools.cw7_extract import copy_context_files
        context_dir = project_dir / ".cw9" / "context"
        n_copied = copy_context_files(plan_path_dir, context_dir, payload["gwts"])
        log(f"  Context files: {n_copied}/{len(payload['gwts'])} copied to {context_dir}")

    log(f"  Payload: {len(payload['requirements'])} reqs, "
        f"{len(payload['gwts'])} GWTs")

    stdin_data = json.dumps(payload)
    stdout_capture = io.StringIO()

    with mock.patch("sys.stdin", io.StringIO(stdin_data)), \
         mock.patch("sys.stdout", stdout_capture):
        rc = cw9_main(["register", str(project_dir)])

    assert rc == 0, f"cw9 register failed (rc={rc})"
    register_output = json.loads(stdout_capture.getvalue())

    n_reqs = len(register_output.get("requirements", []))
    n_gwts = len(register_output.get("gwts", []))
    log(f"  [3/3] cw9 register ....... OK ({n_reqs} reqs, {n_gwts} GWTs)")

    return register_output


# ── Phase 1: Loop (LLM → PlusCal → TLC) ─────────────────────────────────

def run_loop_phase(
    project_dir: Path,
    gwt_ids: list[str],
    max_retries: int,
    gwt_to_criterion: dict[str, str] | None = None,
) -> dict[str, bool]:
    """Run cw9 loop for each GWT. Returns {gwt_id: passed}."""
    log(f"\n{'─' * 60}")
    log("Phase 1: Loop (LLM → PlusCal → TLC)")
    log(f"{'─' * 60}")
    log(f"  GWTs to process: {len(gwt_ids)}")
    log(f"  Max retries per GWT: {max_retries}")

    context_dir = project_dir / ".cw9" / "context"
    results: dict[str, bool] = {}

    for i, gwt_id in enumerate(gwt_ids, 1):
        log(f"\n  [{i}/{len(gwt_ids)}] {gwt_id}")
        t0 = time.time()

        cmd = [
            "loop", gwt_id, str(project_dir),
            "--max-retries", str(max_retries),
        ]

        # Look up context file via criterion_id mapping
        if gwt_to_criterion:
            crit_id = gwt_to_criterion.get(gwt_id)
            if crit_id:
                ctx_file = context_dir / f"{crit_id}.md"
                if ctx_file.exists():
                    cmd.extend(["--context-file", str(ctx_file)])
                    log(f"    context: {ctx_file.name}")

        rc = cw9_main(cmd)

        elapsed = time.time() - t0
        passed = rc == 0

        if passed:
            spec_path = project_dir / ".cw9" / "specs" / f"{gwt_id}.tla"
            sim_path = project_dir / ".cw9" / "specs" / f"{gwt_id}_sim_traces.json"
            sim_count = 0
            if sim_path.exists():
                sim_count = len(json.loads(sim_path.read_text()))
            log(f"    PASS ({elapsed:.1f}s) — spec: {spec_path.name}, "
                f"{sim_count} sim traces")
        else:
            log(f"    FAIL ({elapsed:.1f}s) — loop did not converge")

        results[gwt_id] = passed

    return results


# ── Phase 2: Bridge (spec → artifacts) ───────────────────────────────────

def run_bridge_phase(
    project_dir: Path,
    gwt_ids: list[str],
) -> dict[str, bool]:
    """Run cw9 bridge for each GWT that has a verified spec."""
    log(f"\n{'─' * 60}")
    log("Phase 2: Bridge (spec → artifacts)")
    log(f"{'─' * 60}")

    results: dict[str, bool] = {}

    for i, gwt_id in enumerate(gwt_ids, 1):
        spec_path = project_dir / ".cw9" / "specs" / f"{gwt_id}.tla"
        if not spec_path.exists():
            log(f"  [{i}/{len(gwt_ids)}] {gwt_id} — SKIP (no verified spec)")
            results[gwt_id] = False
            continue

        log(f"  [{i}/{len(gwt_ids)}] {gwt_id}")

        rc = cw9_main(["bridge", gwt_id, str(project_dir)])
        passed = rc == 0

        if passed:
            artifact_path = (project_dir / ".cw9" / "bridge"
                             / f"{gwt_id}_bridge_artifacts.json")
            data = json.loads(artifact_path.read_text())
            log(f"    PASS — {len(data['data_structures'])} structs, "
                f"{len(data['operations'])} ops, "
                f"{len(data['verifiers'])} verifiers, "
                f"{len(data['assertions'])} assertions, "
                f"{len(data['test_scenarios'])} scenarios")

            # Validate artifact shapes
            _validate_bridge_artifacts(data)
            log("    Artifact validation: OK")
        else:
            log("    FAIL — bridge translation error")

        results[gwt_id] = passed

    return results


def _validate_bridge_artifacts(data: dict) -> None:
    """Validate bridge artifact structure matches expected schema shapes."""
    assert data["gwt_id"], "gwt_id is empty"
    assert data["module_name"], "module_name is empty"

    for name, ds in data["data_structures"].items():
        assert "function_id" in ds, f"data_structure {name} missing function_id"
        assert "fields" in ds, f"data_structure {name} missing fields"
        for field_name, fld in ds["fields"].items():
            assert "type" in fld, f"field {field_name} missing type"
            assert fld["type"].startswith("shared/data_types/"), \
                f"field {field_name} type not a schema path: {fld['type']}"

    for name, op in data["operations"].items():
        assert "function_id" in op, f"operation {name} missing function_id"
        assert "parameters" in op, f"operation {name} missing parameters"
        assert "returns" in op, f"operation {name} missing returns"

    for name, v in data["verifiers"].items():
        assert "conditions" in v, f"verifier {name} missing conditions"
        assert len(v["conditions"]) > 0, f"verifier {name} has empty conditions"

    for name, a in data["assertions"].items():
        assert "condition" in a, f"assertion {name} missing condition"
        assert "message" in a, f"assertion {name} missing message"

    for s in data["test_scenarios"]:
        assert "name" in s, "test_scenario missing name"
        assert "setup" in s, "test_scenario missing setup"
        assert "steps" in s, "test_scenario missing steps"

    # Round-trip JSON check
    json.dumps(data)


# ── Resolve GWT targets ─────────────────────────────────────────────────

def resolve_gwt_ids(
    project_dir: Path,
    register_output: dict | None,
    explicit_gwts: list[str] | None,
) -> list[str]:
    """Determine which GWT IDs to process."""
    if explicit_gwts:
        return explicit_gwts

    # From register output
    if register_output and register_output.get("gwts"):
        return [g["gwt_id"] for g in register_output["gwts"]]

    # From DAG
    dag_path = project_dir / ".cw9" / "dag.json"
    if dag_path.exists():
        dag_data = json.loads(dag_path.read_text())
        return sorted(
            nid for nid in dag_data.get("nodes", {})
            if nid.startswith("gwt-")
        )

    return []


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full CW9 pipeline with real LLM: loop → bridge",
    )
    parser.add_argument(
        "--db", type=Path, default=CW7_DEFAULT_DB,
        help="CW7 SQLite database path",
    )
    parser.add_argument(
        "--session", default=None,
        help="CW7 session ID (auto-detected if only one)",
    )
    parser.add_argument(
        "--project-dir", type=Path, default=None,
        help="Project directory (default: temp dir)",
    )
    parser.add_argument(
        "--gwt", action="append", dest="gwts", default=None,
        help="GWT ID(s) to process (default: all registered). Repeatable.",
    )
    parser.add_argument(
        "--max-retries", type=int, default=5,
        help="Max LLM retries per GWT (default: 5)",
    )
    parser.add_argument(
        "--skip-setup", action="store_true",
        help="Skip init/extract/register (project already set up)",
    )
    parser.add_argument(
        "--loop-only", action="store_true",
        help="Run loop only, skip bridge",
    )
    parser.add_argument(
        "--bridge-only", action="store_true",
        help="Run bridge only (specs must already exist)",
    )
    parser.add_argument(
        "--plan-path-dir", type=Path, default=None,
        help="Directory with CW7 plan_path markdown files (e.g., 1046-name.md)",
    )
    args = parser.parse_args()

    # Resolve project directory
    if args.project_dir:
        project_dir = args.project_dir.resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
    else:
        project_dir = Path(tempfile.mkdtemp(prefix="cw9-pipeline-"))

    t_start = time.time()

    log("=" * 60)
    log("CW9 Pipeline — Real LLM")
    log("=" * 60)
    log(f"  Project:     {project_dir}")
    log(f"  CW7 DB:      {args.db}")
    log(f"  Max retries: {args.max_retries}")
    mode = "bridge-only" if args.bridge_only else "loop-only" if args.loop_only else "full"
    log(f"  Mode:        {mode}")

    # Infer session ID from plan_path_dir name if not explicitly provided
    session_id = args.session
    if session_id is None and args.plan_path_dir is not None:
        dirname = args.plan_path_dir.name
        if dirname.startswith("session-"):
            session_id = dirname
            log(f"  Session:     {session_id} (inferred from plan-path-dir)")

    # Phase 0: Setup
    register_output = None
    if not args.skip_setup and not args.bridge_only:
        register_output = setup_project(project_dir, args.db, session_id, args.plan_path_dir)
    else:
        log("\n  Setup: skipped")

    # Resolve targets
    gwt_ids = resolve_gwt_ids(project_dir, register_output, args.gwts)
    if not gwt_ids:
        log("\nERROR: No GWT IDs found. Provide --gwt or ensure register ran.")
        return 1
    log(f"\n  Targets: {gwt_ids}")

    # Build gwt_id → criterion_id mapping for context file lookup
    gwt_to_criterion: dict[str, str] = {}
    if register_output and register_output.get("gwts"):
        for g in register_output["gwts"]:
            gwt_to_criterion[g["gwt_id"]] = g["criterion_id"]

    # Phase 1: Loop
    loop_results: dict[str, bool] = {}
    if not args.bridge_only:
        loop_results = run_loop_phase(
            project_dir, gwt_ids, args.max_retries, gwt_to_criterion,
        )
        verified_ids = [gid for gid, passed in loop_results.items() if passed]
    else:
        # Bridge-only: assume all have specs
        verified_ids = [
            gid for gid in gwt_ids
            if (project_dir / ".cw9" / "specs" / f"{gid}.tla").exists()
        ]

    # Phase 2: Bridge
    bridge_results: dict[str, bool] = {}
    if not args.loop_only and verified_ids:
        bridge_results = run_bridge_phase(project_dir, verified_ids)

    # Summary
    elapsed = time.time() - t_start
    log(f"\n{'=' * 60}")
    log(f"Pipeline Complete ({elapsed:.1f}s)")
    log(f"{'=' * 60}")
    log(f"  Project: {project_dir}")

    if loop_results:
        n_pass = sum(1 for v in loop_results.values() if v)
        n_total = len(loop_results)
        log(f"  Loop:    {n_pass}/{n_total} passed")
        for gid, passed in loop_results.items():
            log(f"    {gid}: {'PASS' if passed else 'FAIL'}")

    if bridge_results:
        n_pass = sum(1 for v in bridge_results.values() if v)
        n_total = len(bridge_results)
        log(f"  Bridge:  {n_pass}/{n_total} passed")
        for gid, passed in bridge_results.items():
            log(f"    {gid}: {'PASS' if passed else 'FAIL'}")

    # List generated artifacts
    artifact_dir = project_dir / ".cw9" / "bridge"
    if artifact_dir.exists():
        artifacts = sorted(artifact_dir.glob("*_bridge_artifacts.json"))
        if artifacts:
            log(f"\n  Artifacts ({len(artifacts)}):")
            for a in artifacts:
                log(f"    {a}")

    log(f"{'=' * 60}")

    # Exit code: 0 if all attempted steps passed
    all_passed = (
        all(loop_results.values()) if loop_results else True
    ) and (
        all(bridge_results.values()) if bridge_results else True
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
