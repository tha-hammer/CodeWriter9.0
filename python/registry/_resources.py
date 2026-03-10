"""Resolve bundled data files for the cw9 CLI.

When installed via pip/uv/pipx, data files live inside the package at
registry/_data/. When running from a repo checkout, they live at
ENGINE_ROOT/templates/ and ENGINE_ROOT/tools/.

This module provides a uniform API that works in both modes.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path


# The _data package anchor for importlib.resources
_DATA_ANCHOR = "registry._data"

# Repo-layout ENGINE_ROOT (only valid in dev mode)
_REPO_ENGINE_ROOT = Path(__file__).resolve().parent.parent.parent


def is_installed_mode() -> bool:
    """Detect whether running from installed package vs repo checkout.

    Heuristic: if _REPO_ENGINE_ROOT / "templates" exists, we're in repo mode.
    """
    return not (_REPO_ENGINE_ROOT / "templates").is_dir()


def get_data_path(relative_path: str) -> Path:
    """Resolve a bundled data file to a real filesystem path.

    Args:
        relative_path: Path relative to _data/, e.g. "tools/tla2tools.jar"

    Returns:
        Absolute Path to the file on disk.

    Raises:
        FileNotFoundError: If the file doesn't exist in either location.
    """
    if not is_installed_mode():
        # Repo checkout: map _data/ paths back to ENGINE_ROOT layout
        repo_path = _map_to_repo_path(relative_path)
        if repo_path.exists():
            return repo_path

    # Installed mode: resolve from package data
    parts = relative_path.split("/")
    resource = files(_DATA_ANCHOR)
    for part in parts:
        resource = resource.joinpath(part)

    # files() returns a Traversable; we need a real Path.
    # NOTE: This uses Path(str(resource)) which requires extracted (non-zip)
    # package layout. uv tool install and pipx install always extract.
    # Zip-based imports (zipapp, --target with zip) are not supported.
    resolved = Path(str(resource))
    if resolved.exists():
        return resolved

    raise FileNotFoundError(
        f"Bundled data file not found: {relative_path}\n"
        f"  Checked package: {resource}\n"
        f"  Checked repo: {_map_to_repo_path(relative_path)}\n"
        f"  If you installed cw9 via pip/uv and see this error, "
        f"try reinstalling: `uv tool install --force .`"
    )


def get_template_dir(kind: str) -> Path:
    """Get the directory for a template kind ('pluscal' or 'schema').

    Returns:
        Path to the template directory.
    """
    return get_data_path(f"templates/{kind}")


def _map_to_repo_path(relative_path: str) -> Path:
    """Map a _data/-relative path back to the repo ENGINE_ROOT layout.

    _data/tools/tla2tools.jar -> ENGINE_ROOT/tools/tla2tools.jar
    _data/templates/pluscal/x.tla -> ENGINE_ROOT/templates/pluscal/x.tla
    """
    return _REPO_ENGINE_ROOT / relative_path
