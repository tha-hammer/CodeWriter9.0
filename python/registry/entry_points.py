"""Entry point discovery for all supported languages.

Detects the codebase type (web app, CLI, library, event-driven) and
extracts appropriate entry points for the DFS crawl.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from registry.crawl_types import EntryPoint, EntryType, Skeleton


def detect_codebase_type(root: Path, *, lang: str | None = None) -> str | None:
    """Detect the codebase type from dependency manifests and imports.

    Returns one of: 'web_app', 'cli', 'event_driven', 'library', or None.
    """
    if lang in ("javascript", "typescript"):
        return _detect_codebase_type_js(root)
    if lang == "go":
        return _detect_codebase_type_go(root)
    if lang == "rust":
        return _detect_codebase_type_rust(root)
    return _detect_codebase_type_python(root)


def _detect_codebase_type_python(root: Path) -> str:
    """Detect codebase type for Python projects."""
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


def _detect_codebase_type_js(root: Path) -> str:
    """Detect codebase type for JavaScript/TypeScript projects."""
    pkg_json = root / "package.json"
    if not pkg_json.exists():
        return "library"

    try:
        text = pkg_json.read_text(encoding="utf-8", errors="replace").lower()
    except (OSError, PermissionError):
        return "library"

    # Web frameworks
    web_frameworks = [
        "express", "next", "nuxt", "fastify", "koa", "hapi", "nestjs",
        "@nestjs/core", "react", "vue", "angular", "svelte", "gatsby",
        "remix", "astro",
    ]
    if any(fw in text for fw in web_frameworks):
        return "web_app"

    # Event-driven
    event_libs = ["bull", "bullmq", "kafka", "amqplib", "rabbitmq", "socket.io"]
    if any(lib in text for lib in event_libs):
        return "event_driven"

    # CLI
    cli_libs = ["commander", "yargs", "inquirer", "oclif", "meow", "cac"]
    if any(lib in text for lib in cli_libs):
        return "cli"

    # Check for bin field
    if '"bin"' in text:
        return "cli"

    return "library"


def _detect_codebase_type_go(root: Path) -> str:
    """Detect codebase type for Go projects."""
    # Check for main package with main.go
    main_go = root / "main.go"
    cmd_dir = root / "cmd"
    if main_go.exists() or cmd_dir.exists():
        return "cli"

    go_mod = root / "go.mod"
    if go_mod.exists():
        try:
            text = go_mod.read_text(encoding="utf-8", errors="replace").lower()
        except (OSError, PermissionError):
            return "library"
        web_frameworks = ["gin-gonic", "gorilla/mux", "echo", "fiber", "chi"]
        if any(fw in text for fw in web_frameworks):
            return "web_app"

    return "library"


def _detect_codebase_type_rust(root: Path) -> str:
    """Detect codebase type for Rust projects."""
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.exists():
        return "library"

    try:
        text = cargo_toml.read_text(encoding="utf-8", errors="replace").lower()
    except (OSError, PermissionError):
        return "library"

    # Check for [[bin]] section
    if "[[bin]]" in text:
        return "cli"

    web_frameworks = ["actix-web", "axum", "rocket", "warp", "tide"]
    if any(fw in text for fw in web_frameworks):
        return "web_app"

    return "library"


def discover_entry_points(
    root: Path,
    codebase_type: str | None = None,
    *,
    lang: str | None = None,
    skeletons: list[Skeleton] | None = None,
) -> list[EntryPoint]:
    """Discover entry points for a codebase.

    Uses scanner output (skeletons) when available to avoid redundant file scanning.
    Falls back to file-based discovery for Python or when skeletons aren't provided.
    """
    if codebase_type is None:
        codebase_type = detect_codebase_type(root, lang=lang)

    if lang == "go":
        return _discover_entry_points_go(root, codebase_type, skeletons or [])
    elif lang == "rust":
        return _discover_entry_points_rust(root, codebase_type, skeletons or [])
    elif lang in ("javascript", "typescript"):
        return _discover_entry_points_js(root, codebase_type, skeletons or [], lang=lang)

    # Python: existing behavior (file-based discovery)
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


# ── Go entry point discovery ─────────────────────────────────────────────


_GO_ROUTE_RE = re.compile(
    r'\.\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*"([^"]+)"'
)

_GO_HANDLE_FUNC_RE = re.compile(
    r'(?:HandleFunc|Handle)\s*\(\s*"([^"]+)"'
)

_GO_COBRA_RE = re.compile(r'cobra\.Command\s*\{[^}]*Use:\s*"(\w+)"', re.DOTALL)


def _discover_entry_points_go(
    root: Path, codebase_type: str, skeletons: list[Skeleton],
) -> list[EntryPoint]:
    """Discover Go entry points from scanner output + framework patterns."""
    entry_points: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    def _add(ep: EntryPoint) -> None:
        key = (ep.file_path, ep.function_name)
        if key not in seen:
            seen.add(key)
            entry_points.append(ep)

    for skel in skeletons:
        if skel.function_name == "main" and skel.class_name is None:
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name="main",
                entry_type=EntryType.MAIN,
            ))
            continue

        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    if codebase_type == "web_app":
        entry_points.extend(_discover_go_routes(root, seen))

    if codebase_type == "cli":
        entry_points.extend(_discover_go_cli_commands(root, seen))

    return entry_points


def _discover_go_routes(
    root: Path, seen: set[tuple[str, str]],
) -> list[EntryPoint]:
    """Find HTTP route registrations in Go source files."""
    entry_points: list[EntryPoint] = []
    for go_file in sorted(root.rglob("*.go")):
        if any(p.startswith(".") for p in go_file.parts) or go_file.name.endswith("_test.go"):
            continue
        try:
            text = go_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue
        rel = str(go_file.relative_to(root))
        for match in _GO_ROUTE_RE.finditer(text):
            method, route = match.group(1), match.group(2)
            key = (rel, route)
            if key not in seen:
                seen.add(key)
                entry_points.append(EntryPoint(
                    file_path=rel,
                    function_name=route,
                    entry_type=EntryType.HTTP_ROUTE,
                    route=route,
                    method=method,
                ))
        for match in _GO_HANDLE_FUNC_RE.finditer(text):
            route = match.group(1)
            key = (rel, route)
            if key not in seen:
                seen.add(key)
                entry_points.append(EntryPoint(
                    file_path=rel,
                    function_name=route,
                    entry_type=EntryType.HTTP_ROUTE,
                    route=route,
                    method=None,
                ))
    return entry_points


def _discover_go_cli_commands(
    root: Path, seen: set[tuple[str, str]],
) -> list[EntryPoint]:
    """Find Cobra CLI command registrations in Go source files."""
    entry_points: list[EntryPoint] = []
    for go_file in sorted(root.rglob("*.go")):
        if any(p.startswith(".") for p in go_file.parts) or go_file.name.endswith("_test.go"):
            continue
        try:
            text = go_file.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue
        rel = str(go_file.relative_to(root))
        for match in _GO_COBRA_RE.finditer(text):
            cmd_name = match.group(1)
            key = (rel, cmd_name)
            if key not in seen:
                seen.add(key)
                entry_points.append(EntryPoint(
                    file_path=rel,
                    function_name=cmd_name,
                    entry_type=EntryType.CLI_COMMAND,
                ))
    return entry_points


# ── Rust entry point discovery ────────────────────────────────────────────


_RUST_ROUTE_ATTR_RE = re.compile(
    r'#\[(get|post|put|delete|patch|head)\s*\(\s*"([^"]+)"'
)

_RUST_AXUM_ROUTE_RE = re.compile(
    r'\.route\s*\(\s*"([^"]+)"\s*,\s*(get|post|put|delete|patch|head)\s*\('
)

_RUST_FN_AFTER_ATTR_RE = re.compile(r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)')

_RUST_CLAP_RE = re.compile(r'#\[derive\([^)]*Parser[^)]*\)\]')


def _discover_entry_points_rust(
    root: Path, codebase_type: str, skeletons: list[Skeleton],
) -> list[EntryPoint]:
    """Discover Rust entry points from scanner output + framework patterns."""
    entry_points: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    def _add(ep: EntryPoint) -> None:
        key = (ep.file_path, ep.function_name)
        if key not in seen:
            seen.add(key)
            entry_points.append(ep)

    for skel in skeletons:
        if skel.function_name == "main" and skel.class_name is None:
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name="main",
                entry_type=EntryType.MAIN,
            ))
            continue

        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    if codebase_type == "web_app":
        entry_points.extend(_discover_rust_routes(root, seen))

    if codebase_type == "cli":
        entry_points.extend(_discover_rust_cli(root, seen))

    return entry_points


def _discover_rust_routes(
    root: Path, seen: set[tuple[str, str]],
) -> list[EntryPoint]:
    """Find HTTP route registrations in Rust source files."""
    entry_points: list[EntryPoint] = []
    for rs_file in sorted(root.rglob("*.rs")):
        if any(p.startswith(".") for p in rs_file.parts):
            continue
        try:
            lines = rs_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, PermissionError):
            continue
        rel = str(rs_file.relative_to(root))

        pending_route = None
        pending_method = None
        for line in lines:
            attr_match = _RUST_ROUTE_ATTR_RE.search(line)
            if attr_match:
                pending_method = attr_match.group(1).upper()
                pending_route = attr_match.group(2)
                continue
            if pending_route:
                fn_match = _RUST_FN_AFTER_ATTR_RE.match(line)
                if fn_match:
                    fn_name = fn_match.group(1)
                    key = (rel, fn_name)
                    if key not in seen:
                        seen.add(key)
                        entry_points.append(EntryPoint(
                            file_path=rel,
                            function_name=fn_name,
                            entry_type=EntryType.HTTP_ROUTE,
                            route=pending_route,
                            method=pending_method,
                        ))
                pending_route = None
                pending_method = None

        text = "\n".join(lines)
        for match in _RUST_AXUM_ROUTE_RE.finditer(text):
            route, method = match.group(1), match.group(2).upper()
            key = (rel, route)
            if key not in seen:
                seen.add(key)
                entry_points.append(EntryPoint(
                    file_path=rel,
                    function_name=route,
                    entry_type=EntryType.HTTP_ROUTE,
                    route=route,
                    method=method,
                ))
    return entry_points


def _discover_rust_cli(
    root: Path, seen: set[tuple[str, str]],
) -> list[EntryPoint]:
    """Find Clap CLI structs in Rust source files."""
    entry_points: list[EntryPoint] = []
    for rs_file in sorted(root.rglob("*.rs")):
        if any(p.startswith(".") for p in rs_file.parts):
            continue
        try:
            lines = rs_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, PermissionError):
            continue
        rel = str(rs_file.relative_to(root))
        pending_clap = False
        for line in lines:
            if _RUST_CLAP_RE.search(line):
                pending_clap = True
                continue
            if pending_clap:
                struct_match = re.match(r'\s*(?:pub\s+)?struct\s+(\w+)', line)
                if struct_match:
                    name = struct_match.group(1)
                    key = (rel, name)
                    if key not in seen:
                        seen.add(key)
                        entry_points.append(EntryPoint(
                            file_path=rel,
                            function_name=name,
                            entry_type=EntryType.CLI_COMMAND,
                        ))
                    pending_clap = False
                elif not line.strip().startswith("#["):
                    pending_clap = False
    return entry_points


# ── JavaScript / TypeScript entry point discovery ─────────────────────────


_JS_ROUTE_RE = re.compile(
    r'\.\s*(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']'
)

_JS_CLI_COMMAND_RE = re.compile(r'\.command\s*\(\s*["\'](\w+)["\']')


def _discover_entry_points_js(
    root: Path, codebase_type: str, skeletons: list[Skeleton], *, lang: str,
) -> list[EntryPoint]:
    """Discover JS/TS entry points from scanner output + framework patterns."""
    entry_points: list[EntryPoint] = []
    seen: set[tuple[str, str]] = set()

    def _add(ep: EntryPoint) -> None:
        key = (ep.file_path, ep.function_name)
        if key not in seen:
            seen.add(key)
            entry_points.append(ep)

    entry_points.extend(_discover_js_manifest_entry_points(root, seen))

    for skel in skeletons:
        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    if codebase_type == "web_app":
        entry_points.extend(_discover_js_routes(root, seen, lang=lang))

    if codebase_type == "cli":
        entry_points.extend(_discover_js_cli_commands(root, seen, lang=lang))

    if not entry_points:
        for skel in skeletons:
            if skel.visibility == "public" and skel.class_name is None:
                _add(EntryPoint(
                    file_path=skel.file_path,
                    function_name=skel.function_name,
                    entry_type=EntryType.PUBLIC_API,
                ))

    return entry_points


def _discover_js_manifest_entry_points(
    root: Path, seen: set[tuple[str, str]],
) -> list[EntryPoint]:
    """Extract entry points from package.json bin/main/module fields."""
    entry_points: list[EntryPoint] = []
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return entry_points
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return entry_points

    bin_field = pkg.get("bin")
    if isinstance(bin_field, str):
        key = (bin_field, "bin")
        if key not in seen:
            seen.add(key)
            entry_points.append(EntryPoint(
                file_path=bin_field,
                function_name="bin",
                entry_type=EntryType.CLI_COMMAND,
            ))
    elif isinstance(bin_field, dict):
        for cmd_name, cmd_path in bin_field.items():
            key = (str(cmd_path), cmd_name)
            if key not in seen:
                seen.add(key)
                entry_points.append(EntryPoint(
                    file_path=str(cmd_path),
                    function_name=cmd_name,
                    entry_type=EntryType.CLI_COMMAND,
                ))

    main_field = pkg.get("main")
    if isinstance(main_field, str):
        key = (main_field, "main")
        if key not in seen:
            seen.add(key)
            entry_points.append(EntryPoint(
                file_path=main_field,
                function_name="main",
                entry_type=EntryType.MAIN,
            ))

    return entry_points


def _discover_js_routes(
    root: Path, seen: set[tuple[str, str]], *, lang: str,
) -> list[EntryPoint]:
    """Find Express/Koa/Hapi route registrations in JS/TS files."""
    entry_points: list[EntryPoint] = []
    exts = ("*.ts", "*.tsx") if lang == "typescript" else ("*.js", "*.jsx")
    for ext in exts:
        for src_file in sorted(root.rglob(ext)):
            if any(p.startswith(".") or p == "node_modules" for p in src_file.parts):
                continue
            if src_file.name.endswith((".min.js", ".d.ts")):
                continue
            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue
            rel = str(src_file.relative_to(root))
            for match in _JS_ROUTE_RE.finditer(text):
                method, route = match.group(1).upper(), match.group(2)
                key = (rel, route)
                if key not in seen:
                    seen.add(key)
                    entry_points.append(EntryPoint(
                        file_path=rel,
                        function_name=route,
                        entry_type=EntryType.HTTP_ROUTE,
                        route=route,
                        method=method,
                    ))
    return entry_points


def _discover_js_cli_commands(
    root: Path, seen: set[tuple[str, str]], *, lang: str,
) -> list[EntryPoint]:
    """Find commander/yargs CLI command registrations in JS/TS files."""
    entry_points: list[EntryPoint] = []
    exts = ("*.ts", "*.tsx") if lang == "typescript" else ("*.js", "*.jsx")
    for ext in exts:
        for src_file in sorted(root.rglob(ext)):
            if any(p.startswith(".") or p == "node_modules" for p in src_file.parts):
                continue
            if src_file.name.endswith((".min.js", ".d.ts")):
                continue
            try:
                text = src_file.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue
            rel = str(src_file.relative_to(root))
            for match in _JS_CLI_COMMAND_RE.finditer(text):
                cmd_name = match.group(1)
                key = (rel, cmd_name)
                if key not in seen:
                    seen.add(key)
                    entry_points.append(EntryPoint(
                        file_path=rel,
                        function_name=cmd_name,
                        entry_type=EntryType.CLI_COMMAND,
                    ))
    return entry_points
