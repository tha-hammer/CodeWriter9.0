"""Criterion-to-GWT ID bindings for idempotent registration."""

from __future__ import annotations

import json
from pathlib import Path

_BINDINGS_FILE = "criterion_bindings.json"


def load_bindings(state_root: Path) -> dict[str, str]:
    path = state_root / _BINDINGS_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_bindings(state_root: Path, bindings: dict[str, str]) -> None:
    path = state_root / _BINDINGS_FILE
    path.write_text(json.dumps(bindings, indent=2) + "\n")
