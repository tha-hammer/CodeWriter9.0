"""Pipeline status — derive GWT progress from on-disk artifacts.

No database required. Everything is derived from:
  .cw9/dag.json            → universe of GWT IDs
  .cw9/sessions/*_result.json  → per-GWT outcome (written by run_loop)
  .cw9/sessions/*_attempt*.txt → attempt count fallback (in-progress detection)
  .cw9/specs/*.tla             → verified specs
  .cw9/bridge/*_bridge_artifacts.json → bridge completion
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GWTStatus:
    """Status of a single GWT through the pipeline."""
    gwt_id: str
    result: str          # "pass", "fail", "pending", "in_progress"
    attempts: int = 0
    error: str | None = None
    bridge_done: bool = False

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "attempts": self.attempts,
            "error": self.error,
            "bridge_done": self.bridge_done,
        }


@dataclass
class ProjectStatus:
    """Aggregate pipeline status for a project."""
    project_root: str
    total: int = 0
    verified: int = 0
    failed: int = 0
    pending: int = 0
    in_progress: int = 0
    bridge_complete: int = 0
    gwts: dict[str, GWTStatus] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "project_root": self.project_root,
            "total": self.total,
            "verified": self.verified,
            "failed": self.failed,
            "pending": self.pending,
            "in_progress": self.in_progress,
            "bridge_complete": self.bridge_complete,
            "gwts": {gid: gs.to_dict() for gid, gs in self.gwts.items()},
        }


def write_result_file(
    session_dir: Path,
    gwt_id: str,
    result: str,
    attempts: int,
    error: str | None,
) -> None:
    """Write a result JSON for a completed GWT loop run."""
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{gwt_id}_result.json"
    path.write_text(json.dumps({
        "gwt_id": gwt_id,
        "result": result,
        "attempts": attempts,
        "error": error,
    }))


def gather_status(project_dir: Path) -> ProjectStatus:
    """Derive pipeline status from on-disk artifacts.

    Raises FileNotFoundError if .cw9/ does not exist.
    """
    project_dir = Path(project_dir).resolve()
    state_root = project_dir / ".cw9"
    if not state_root.exists():
        raise FileNotFoundError(f"No .cw9/ found in {project_dir}")

    # Load GWT IDs from DAG
    dag_path = state_root / "dag.json"
    gwt_ids: list[str] = []
    if dag_path.exists():
        dag = json.loads(dag_path.read_text())
        gwt_ids = sorted(
            nid for nid in dag.get("nodes", {}) if nid.startswith("gwt-")
        )

    sessions_dir = state_root / "sessions"
    specs_dir = state_root / "specs"
    bridge_dir = state_root / "bridge"

    status = ProjectStatus(project_root=str(project_dir))
    status.total = len(gwt_ids)

    for gwt_id in gwt_ids:
        gs = _derive_gwt_status(gwt_id, sessions_dir, specs_dir, bridge_dir)
        status.gwts[gwt_id] = gs

        if gs.result == "pass":
            status.verified += 1
        elif gs.result == "fail":
            status.failed += 1
        elif gs.result == "in_progress":
            status.in_progress += 1
        else:
            status.pending += 1

        if gs.bridge_done:
            status.bridge_complete += 1

    return status


def _derive_gwt_status(
    gwt_id: str,
    sessions_dir: Path,
    specs_dir: Path,
    bridge_dir: Path,
) -> GWTStatus:
    """Derive status for a single GWT from its artifacts."""
    result_path = sessions_dir / f"{gwt_id}_result.json"
    bridge_path = bridge_dir / f"{gwt_id}_bridge_artifacts.json"
    bridge_done = bridge_path.exists()

    # Prefer structured result file
    if result_path.exists():
        data = json.loads(result_path.read_text())
        return GWTStatus(
            gwt_id=gwt_id,
            result=data.get("result", "fail"),
            attempts=data.get("attempts", 0),
            error=data.get("error"),
            bridge_done=bridge_done,
        )

    # Fallback: count attempt files
    attempt_files = sorted(sessions_dir.glob(f"{gwt_id}_attempt*.txt"))
    if attempt_files:
        # Has attempts but no result → still running
        return GWTStatus(
            gwt_id=gwt_id,
            result="in_progress",
            attempts=len(attempt_files),
            bridge_done=bridge_done,
        )

    # No attempts, no result → pending
    return GWTStatus(gwt_id=gwt_id, result="pending", bridge_done=bridge_done)
