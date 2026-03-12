#!/usr/bin/env python3
"""Test CW9 pipeline: cw9 loop → cw9 bridge using CW7 counter-app fixture.

Picks up where cw7_extract.py leaves off:
  cw7_extract.py: CW7 approval → cw9 init → cw9 extract → cw9 register
  This script:    cw9 loop → cw9 bridge

Usage:
    # Full pipeline — init + register + loop + bridge (requires LLM):
    python test_loop_bridge.py

    # With custom project dir:
    python test_loop_bridge.py --project-dir /tmp/test-counter

    # Bridge-only — skip loop, write synthetic spec (no LLM needed):
    python test_loop_bridge.py --bridge-only

    # Loop only — skip bridge:
    python test_loop_bridge.py --loop-only

    # Target a specific GWT (default: first registered):
    python test_loop_bridge.py --gwt gwt-0001
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure registry is importable
SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PYTHON_DIR))

from registry.cli import main as cw9_main

# CW7 fixture database (counter-app)
CW7_FIXTURE_DB = Path(
    os.environ.get(
        "CW7_FIXTURE_DB",
        os.path.expanduser(
            "~/Dev/CodeWriter7/fixtures/pipeline-outputs/counter-app.db"
        ),
    )
)

# A minimal counter-app PlusCal spec for bridge-only testing.
# Models: counter starts at 0, increment/decrement with floor at 0, reset.
# Uses top-level action definitions (no `self` parameter) so the bridge
# parser can extract operations via its `Name == ...` regex.
SYNTHETIC_SPEC = """\
------------------------ MODULE counter_app ------------------------
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    MaxSteps

(* --algorithm CounterApp

variables
    counter = 0,
    current_state = "idle",
    step_count = 0,
    dirty = FALSE;

define
    ValidCounter == counter >= 0
    BoundedExecution == step_count <= MaxSteps
    CounterNonNegative == dirty = TRUE \\/ counter >= 0
end define;

end algorithm; *)

\\* BEGIN TRANSLATION - placeholder
VARIABLES pc, counter, current_state, step_count, dirty

(* define statement *)
ValidCounter == counter >= 0
BoundedExecution == step_count <= MaxSteps
CounterNonNegative == dirty = TRUE \\/ counter >= 0

vars == << pc, counter, current_state, step_count, dirty >>

Init == (* Global variables *)
        /\\ counter = 0
        /\\ current_state = "idle"
        /\\ step_count = 0
        /\\ dirty = FALSE
        /\\ pc = "Loop"

IncrementAction == /\\ pc = "Loop"
                   /\\ current_state = "idle"
                   /\\ counter' = counter + 1
                   /\\ dirty' = TRUE
                   /\\ step_count' = step_count + 1
                   /\\ pc' = "Loop"
                   /\\ UNCHANGED current_state

DecrementAction == /\\ pc = "Loop"
                   /\\ current_state = "idle"
                   /\\ counter > 0
                   /\\ counter' = counter - 1
                   /\\ dirty' = TRUE
                   /\\ step_count' = step_count + 1
                   /\\ pc' = "Loop"
                   /\\ UNCHANGED current_state

ResetAction == /\\ pc = "Loop"
               /\\ current_state = "idle"
               /\\ counter' = 0
               /\\ dirty' = TRUE
               /\\ step_count' = step_count + 1
               /\\ pc' = "Loop"
               /\\ UNCHANGED current_state

FinishAction == /\\ pc = "Loop"
                /\\ current_state' = "done"
                /\\ pc' = "Done"
                /\\ UNCHANGED << counter, step_count, dirty >>

Next == IncrementAction \\/ DecrementAction \\/ ResetAction \\/ FinishAction

Spec == Init /\\ [][Next]_vars

\\* END TRANSLATION

===========================================================================
"""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def setup_project(project_dir: Path) -> dict:
    """Run: cw9 init → cw9 extract → cw7_extract | cw9 register.

    Returns the register output (requirement + GWT ID mappings).
    """
    log(f"\n[setup] Initializing project at {project_dir}")

    # Step 1: cw9 init
    rc = cw9_main(["init", str(project_dir), "--ensure"])
    if rc != 0:
        # Try without --ensure (first init)
        rc = cw9_main(["init", str(project_dir)])
    assert rc == 0, f"cw9 init failed (rc={rc})"
    log("  init: OK")

    # Step 2: cw9 extract (builds DAG from schemas)
    rc = cw9_main(["extract", str(project_dir)])
    assert rc == 0, f"cw9 extract failed (rc={rc})"
    log("  extract: OK")

    # Step 3: cw7_extract → cw9 register
    from tools.cw7_extract import extract as cw7_extract

    if not CW7_FIXTURE_DB.exists():
        log(f"  WARNING: CW7 fixture not found at {CW7_FIXTURE_DB}")
        log("  Using inline fixture data instead")
        payload = _inline_fixture()
    else:
        payload = cw7_extract(CW7_FIXTURE_DB)
        log(f"  cw7_extract: {len(payload['requirements'])} reqs, "
            f"{len(payload['gwts'])} GWTs")

    # Pipe payload into cw9 register via monkeypatch
    import unittest.mock as mock

    stdin_data = json.dumps(payload)
    stdout_capture = io.StringIO()

    with mock.patch("sys.stdin", io.StringIO(stdin_data)), \
         mock.patch("sys.stdout", stdout_capture):
        rc = cw9_main(["register", str(project_dir)])

    assert rc == 0, f"cw9 register failed (rc={rc})"

    register_output = json.loads(stdout_capture.getvalue())
    log(f"  register: {len(register_output.get('requirements', []))} reqs, "
        f"{len(register_output.get('gwts', []))} GWTs registered")

    return register_output


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


def run_loop(project_dir: Path, gwt_id: str, max_retries: int = 5) -> int:
    """Run: cw9 loop <gwt_id>.

    Requires claude-agent-sdk and API access.
    Returns exit code.
    """
    log(f"\n[loop] Running cw9 loop {gwt_id} (max_retries={max_retries})")
    rc = cw9_main(["loop", gwt_id, str(project_dir),
                    "--max-retries", str(max_retries)])
    if rc == 0:
        spec_path = project_dir / ".cw9" / "specs" / f"{gwt_id}.tla"
        log(f"  PASS — verified spec: {spec_path}")
        assert spec_path.exists(), f"Spec file missing after PASS: {spec_path}"

        # Check for simulation traces (v5)
        sim_path = project_dir / ".cw9" / "specs" / f"{gwt_id}_sim_traces.json"
        if sim_path.exists():
            traces = json.loads(sim_path.read_text())
            log(f"  {len(traces)} simulation traces collected")
    else:
        log(f"  FAIL — loop did not converge in {max_retries} attempts")

    return rc


def write_synthetic_spec(project_dir: Path, gwt_id: str) -> Path:
    """Write a synthetic TLA+ spec for bridge-only testing (no LLM needed)."""
    spec_dir = project_dir / ".cw9" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{gwt_id}.tla"
    spec_path.write_text(SYNTHETIC_SPEC)
    log(f"  Wrote synthetic spec: {spec_path}")
    return spec_path


def run_bridge(project_dir: Path, gwt_id: str) -> int:
    """Run: cw9 bridge <gwt_id>.

    Requires a verified spec at .cw9/specs/<gwt_id>.tla.
    Returns exit code.
    """
    log(f"\n[bridge] Running cw9 bridge {gwt_id}")
    rc = cw9_main(["bridge", gwt_id, str(project_dir)])
    if rc == 0:
        artifact_path = (project_dir / ".cw9" / "bridge"
                         / f"{gwt_id}_bridge_artifacts.json")
        assert artifact_path.exists(), f"Artifact file missing: {artifact_path}"

        data = json.loads(artifact_path.read_text())
        log(f"  Bridge artifacts saved: {artifact_path}")
        log(f"    gwt_id: {data['gwt_id']}")
        log(f"    module_name: {data['module_name']}")
        log(f"    data_structures: {len(data['data_structures'])}")
        log(f"    operations: {len(data['operations'])}")
        log(f"    verifiers: {len(data['verifiers'])}")
        log(f"    assertions: {len(data['assertions'])}")
        log(f"    test_scenarios: {len(data['test_scenarios'])}")
        log(f"    simulation_traces: {len(data.get('simulation_traces', []))}")

        # Validate artifact structure
        _validate_bridge_artifacts(data)
        log("  Artifact validation: PASS")
    else:
        log("  FAIL — bridge translation failed")

    return rc


def _validate_bridge_artifacts(data: dict) -> None:
    """Validate bridge artifact structure matches expected schema shapes."""
    assert data["gwt_id"], "gwt_id is empty"
    assert data["module_name"], "module_name is empty"

    # data_structures shape: {Name: {function_id, fields, ...}}
    for name, ds in data["data_structures"].items():
        assert "function_id" in ds, f"data_structure {name} missing function_id"
        assert "fields" in ds, f"data_structure {name} missing fields"
        for field_name, field in ds["fields"].items():
            assert "type" in field, f"field {field_name} missing type"
            assert field["type"].startswith("shared/data_types/"), \
                f"field {field_name} type not a schema path: {field['type']}"

    # operations shape: {Name: {function_id, parameters, returns, ...}}
    for name, op in data["operations"].items():
        assert "function_id" in op, f"operation {name} missing function_id"
        assert "parameters" in op, f"operation {name} missing parameters"
        assert "returns" in op, f"operation {name} missing returns"

    # verifiers shape: {Name: {conditions, message, applies_to, ...}}
    for name, v in data["verifiers"].items():
        assert "conditions" in v, f"verifier {name} missing conditions"
        assert len(v["conditions"]) > 0, f"verifier {name} has empty conditions"

    # assertions shape: {Name: {condition, message, ...}}
    for name, a in data["assertions"].items():
        assert "condition" in a, f"assertion {name} missing condition"
        assert "message" in a, f"assertion {name} missing message"

    # test_scenarios shape: [{name, setup, steps, expected_outcome, ...}]
    for s in data["test_scenarios"]:
        assert "name" in s, "test_scenario missing name"
        assert "setup" in s, "test_scenario missing setup"
        assert "steps" in s, "test_scenario missing steps"

    # All outputs must be JSON-serializable (round-trip check)
    json.dumps(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test CW9 pipeline: cw9 loop → cw9 bridge"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Project directory (default: temp dir)",
    )
    parser.add_argument(
        "--gwt",
        default=None,
        help="GWT ID to target (default: first registered GWT)",
    )
    parser.add_argument(
        "--bridge-only",
        action="store_true",
        help="Skip loop, write synthetic spec, run bridge only (no LLM)",
    )
    parser.add_argument(
        "--loop-only",
        action="store_true",
        help="Run loop only, skip bridge",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Max LLM retries for loop (default: 5)",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Skip init/extract/register (project already set up)",
    )
    args = parser.parse_args()

    # Resolve project directory
    if args.project_dir:
        project_dir = args.project_dir.resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
    else:
        project_dir = Path(tempfile.mkdtemp(prefix="cw9-test-"))

    log("=" * 70)
    log("CW9 Pipeline Test: cw9 loop → cw9 bridge")
    log(f"  project: {project_dir}")
    log(f"  mode: {'bridge-only' if args.bridge_only else 'loop-only' if args.loop_only else 'full'}")
    log("=" * 70)

    # Phase 0: Setup (init + extract + register)
    if not args.skip_setup:
        register_output = setup_project(project_dir)
    else:
        log("\n[setup] Skipped (--skip-setup)")
        register_output = None

    # Resolve target GWT
    gwt_id = args.gwt
    if gwt_id is None:
        if register_output and register_output.get("gwts"):
            gwt_id = register_output["gwts"][0]["gwt_id"]
        else:
            # Read DAG to find first registered GWT
            dag_path = project_dir / ".cw9" / "dag.json"
            if dag_path.exists():
                dag_data = json.loads(dag_path.read_text())
                gwt_ids = sorted(
                    nid for nid in dag_data.get("nodes", {})
                    if nid.startswith("gwt-")
                )
                if gwt_ids:
                    gwt_id = gwt_ids[0]

    if gwt_id is None:
        log("\nERROR: No GWT ID found. Provide --gwt or ensure register ran.")
        return 1

    log(f"\n  Target GWT: {gwt_id}")

    # Phase 1: Loop (LLM → PlusCal → TLC)
    if args.bridge_only:
        log("\n[loop] Skipped (--bridge-only)")
        write_synthetic_spec(project_dir, gwt_id)
    else:
        rc = run_loop(project_dir, gwt_id, max_retries=args.max_retries)
        if rc != 0:
            log("\nPipeline stopped: loop failed.")
            return rc

    # Phase 2: Bridge (spec → artifacts)
    if args.loop_only:
        log("\n[bridge] Skipped (--loop-only)")
    else:
        rc = run_bridge(project_dir, gwt_id)
        if rc != 0:
            log("\nPipeline stopped: bridge failed.")
            return rc

    # Summary
    log("\n" + "=" * 70)
    log("Pipeline test PASSED")
    log(f"  Project: {project_dir}")
    log(f"  GWT: {gwt_id}")

    spec_path = project_dir / ".cw9" / "specs" / f"{gwt_id}.tla"
    if spec_path.exists():
        log(f"  Spec: {spec_path}")

    artifact_path = (project_dir / ".cw9" / "bridge"
                     / f"{gwt_id}_bridge_artifacts.json")
    if artifact_path.exists():
        log(f"  Artifacts: {artifact_path}")

    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
