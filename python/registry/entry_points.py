"""Entry point discovery for Python codebases.

Detects the codebase type (web app, CLI, library, event-driven) and
extracts appropriate entry points for the DFS crawl.
"""

from __future__ import annotations

import re
from pathlib import Path

from registry.crawl_types import EntryPoint, EntryType


def detect_codebase_type(root: Path) -> str | None:
    """Detect the codebase type from dependency manifests and imports.

    Returns one of: 'web_app', 'cli', 'event_driven', 'library', or None.
    """
    # Check pyproject.toml
    pyproject = root / "pyproject.toml"
    requirements = root / "requirements.txt"
    setup_py = root / "setup.py"

    dep_text = ""
    if pyproject.exists():
        dep_text += pyproject.read_text(encoding="utf-8", errors="replace")
    if requirements.exists():
        dep_text += "\n" + requirements.read_text(encoding="utf-8", errors="replace")
    if setup_py.exists():
        dep_text += "\n" + setup_py.read_text(encoding="utf-8", errors="replace")

    dep_lower = dep_text.lower()

    # Web frameworks (check first — most specific)
    web_frameworks = ["fastapi", "flask", "django", "starlette", "sanic", "tornado", "aiohttp"]
    if any(fw in dep_lower for fw in web_frameworks):
        return "web_app"

    # Event-driven
    event_libs = ["celery", "dramatiq", "rq", "kafka", "pika", "kombu"]
    if any(lib in dep_lower for lib in event_libs):
        return "event_driven"

    # CLI
    cli_libs = ["click", "typer", "argparse"]
    if any(lib in dep_lower for lib in cli_libs):
        return "cli"

    # Check for console_scripts entry point
    if "console_scripts" in dep_text:
        return "cli"

    # Default: library
    return "library"


def discover_entry_points(root: Path, codebase_type: str | None = None) -> list[EntryPoint]:
    """Discover entry points for a Python codebase.

    If codebase_type is None, auto-detects it.
    """
    if codebase_type is None:
        codebase_type = detect_codebase_type(root)

    entry_points: list[EntryPoint] = []

    if codebase_type == "web_app":
        entry_points.extend(_discover_web_routes(root))
    elif codebase_type == "cli":
        entry_points.extend(_discover_cli_commands(root))
    elif codebase_type == "event_driven":
        entry_points.extend(_discover_event_handlers(root))

    # Always check for main() and __main__.py
    entry_points.extend(_discover_main_functions(root))

    # If library, discover public API
    if codebase_type == "library" or not entry_points:
        entry_points.extend(_discover_public_api(root))

    return entry_points


# Route decorator patterns
_ROUTE_DECORATORS = [
    # FastAPI / Starlette
    re.compile(r'@\w+\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']'),
    # Flask / Blueprint
    re.compile(r'@\w+\.route\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?'),
    # Django urlpatterns (path("...", view_func))
    re.compile(r'path\s*\(\s*["\']([^"\']+)["\'].*?(\w+)(?:\s*\.as_view\(\))?'),
]

# Decorator that indicates a Flask/FastAPI route handler with HTTP method in decorator name
_METHOD_DECORATOR_RE = re.compile(r'@\w+\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']')
_FLASK_ROUTE_RE = re.compile(r'@\w+\.route\s*\(\s*["\']([^"\']+)["\']')
_DEF_RE = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)')


def _discover_web_routes(root: Path) -> list[EntryPoint]:
    """Find HTTP route handlers in a web framework project."""
    entries: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    for py_file in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, PermissionError):
            continue

        pending_route: str | None = None
        pending_method: str | None = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check for method-specific decorators (FastAPI style)
            method_match = _METHOD_DECORATOR_RE.search(stripped)
            if method_match:
                pending_method = method_match.group(1).upper()
                pending_route = method_match.group(2)
                continue

            # Check for Flask-style @app.route
            flask_match = _FLASK_ROUTE_RE.search(stripped)
            if flask_match:
                pending_route = flask_match.group(1)
                pending_method = None  # methods specified separately or defaulting to GET
                continue

            # Check if this line is a def following a route decorator
            if pending_route is not None:
                def_match = _DEF_RE.match(line)
                if def_match:
                    func_name = def_match.group(1)
                    key = (str(py_file), func_name)
                    if key not in seen:
                        seen.add(key)
                        entries.append(EntryPoint(
                            file_path=str(py_file),
                            function_name=func_name,
                            entry_type=EntryType.HTTP_ROUTE,
                            route=pending_route,
                            method=pending_method or "GET",
                        ))
                    pending_route = None
                    pending_method = None
                elif not stripped.startswith("@"):
                    # Not a decorator continuation — clear pending
                    pending_route = None
                    pending_method = None

    return entries


_CLI_DECORATOR_RE = re.compile(r'@\w+\.(command|group)\s*\(')
_CLICK_COMMAND_RE = re.compile(r'@click\.(command|group)')
_ARGPARSE_ADD_RE = re.compile(r'add_subparser|add_parser|add_argument')


def _discover_cli_commands(root: Path) -> list[EntryPoint]:
    """Find CLI command handlers (click, typer, argparse)."""
    entries: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    for py_file in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, PermissionError):
            continue

        pending_cli = False
        for i, line in enumerate(lines):
            stripped = line.strip()

            if _CLI_DECORATOR_RE.search(stripped) or _CLICK_COMMAND_RE.search(stripped):
                pending_cli = True
                continue

            if pending_cli:
                def_match = _DEF_RE.match(line)
                if def_match:
                    func_name = def_match.group(1)
                    key = (str(py_file), func_name)
                    if key not in seen:
                        seen.add(key)
                        entries.append(EntryPoint(
                            file_path=str(py_file),
                            function_name=func_name,
                            entry_type=EntryType.CLI_COMMAND,
                        ))
                    pending_cli = False
                elif not stripped.startswith("@"):
                    pending_cli = False

    return entries


_TASK_DECORATOR_RE = re.compile(r'@\w+\.task|@dramatiq\.actor|@celery_app\.task')


def _discover_event_handlers(root: Path) -> list[EntryPoint]:
    """Find event/task handlers (celery, dramatiq)."""
    entries: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    for py_file in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, PermissionError):
            continue

        pending_event = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if _TASK_DECORATOR_RE.search(stripped):
                pending_event = True
                continue
            if pending_event:
                def_match = _DEF_RE.match(line)
                if def_match:
                    func_name = def_match.group(1)
                    key = (str(py_file), func_name)
                    if key not in seen:
                        seen.add(key)
                        entries.append(EntryPoint(
                            file_path=str(py_file),
                            function_name=func_name,
                            entry_type=EntryType.EVENT_HANDLER,
                        ))
                    pending_event = False
                elif not stripped.startswith("@"):
                    pending_event = False

    return entries


def _discover_main_functions(root: Path) -> list[EntryPoint]:
    """Find main() functions and __main__.py files."""
    entries: list[EntryPoint] = []

    for py_file in sorted(root.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        # Check for def main() or if __name__ == "__main__"
        if re.search(r'^def\s+main\s*\(', text, re.MULTILINE):
            entries.append(EntryPoint(
                file_path=str(py_file),
                function_name="main",
                entry_type=EntryType.MAIN,
            ))
        elif py_file.name == "__main__.py":
            entries.append(EntryPoint(
                file_path=str(py_file),
                function_name="__main__",
                entry_type=EntryType.MAIN,
            ))

    return entries


def _discover_public_api(root: Path) -> list[EntryPoint]:
    """Find public API surface for library-type projects."""
    entries: list[EntryPoint] = []

    # Look for __init__.py with __all__
    for init_file in sorted(root.rglob("__init__.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in init_file.parts):
            continue
        try:
            text = init_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        # Extract __all__ members
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', text, re.DOTALL)
        if all_match:
            members = re.findall(r'["\'](\w+)["\']', all_match.group(1))
            for member in members:
                entries.append(EntryPoint(
                    file_path=str(init_file),
                    function_name=member,
                    entry_type=EntryType.PUBLIC_API,
                ))

    return entries
