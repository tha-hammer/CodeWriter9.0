"""Python skeleton scanner — extracts function/method/class signatures.

Line-by-line text scanning with indent tracking. No AST, no tree-sitter.
Produces Skeleton objects for each function/method found.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from registry.crawl_types import Skeleton, SkeletonParam

# Default directories to skip during scan
DEFAULT_EXCLUDES = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "vendor", "target", "build", ".tox", ".mypy_cache",
    ".pytest_cache", "dist", "egg-info", ".eggs",
}

# Regex patterns for Python constructs
_DEF_RE = re.compile(
    r"^(\s*)(async\s+)?def\s+(\w+)\s*\((.*?)(?:\)|$)",
    re.DOTALL,
)
_CLASS_RE = re.compile(r"^(\s*)class\s+(\w+)")
_DECORATOR_RE = re.compile(r"^(\s*)@")
_RETURN_TYPE_RE = re.compile(r"\)\s*->\s*(.+?):\s*$")


def _compute_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_params(param_str: str) -> list[SkeletonParam]:
    """Parse a comma-separated parameter string into SkeletonParam objects."""
    params: list[SkeletonParam] = []
    if not param_str.strip():
        return params

    # Handle multi-line params by normalizing whitespace
    param_str = " ".join(param_str.split())

    depth = 0
    current = ""
    for ch in param_str:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            params.append(_parse_single_param(current.strip()))
            current = ""
        else:
            current += ch
    if current.strip():
        params.append(_parse_single_param(current.strip()))

    return params


def _parse_single_param(param: str) -> SkeletonParam:
    """Parse a single parameter like 'name: type = default'."""
    # Strip default value
    if "=" in param:
        # Handle cases like `x: int = 5` but not `x: dict[str, int]`
        depth = 0
        for i, ch in enumerate(param):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "=" and depth == 0:
                param = param[:i].strip()
                break

    # Check for self/cls
    name = param
    type_str = ""
    is_self = False

    if ":" in param:
        # Handle type annotation
        depth = 0
        for i, ch in enumerate(param):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == ":" and depth == 0:
                name = param[:i].strip()
                type_str = param[i + 1:].strip()
                break
    else:
        name = param.strip()

    # Remove leading * and **
    if name.startswith("**"):
        name = name[2:]
    elif name.startswith("*"):
        name = name[1:]
        if not name:  # bare * separator
            return SkeletonParam(name="*", type="", is_self=False)

    is_self = name in ("self", "cls")
    return SkeletonParam(name=name, type=type_str, is_self=is_self)


def scan_file(path: Path) -> list[Skeleton]:
    """Extract function/method/class skeletons from a single Python file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    skeletons: list[Skeleton] = []

    # Track class context via indent levels
    class_stack: list[tuple[str, int]] = []  # (class_name, indent_level)
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(line) - len(stripped)

        # Pop class stack when indent returns to or below class level
        while class_stack and indent <= class_stack[-1][1]:
            class_stack.pop()

        # Check for class definition
        class_match = _CLASS_RE.match(line)
        if class_match:
            class_indent = len(class_match.group(1))
            class_name = class_match.group(2)
            class_stack.append((class_name, class_indent))
            i += 1
            continue

        # Check for function/method definition
        def_match = _DEF_RE.match(line)
        if def_match:
            def_indent = len(def_match.group(1))
            is_async = bool(def_match.group(2))
            func_name = def_match.group(3)
            param_text = def_match.group(4)

            # If the parentheses aren't closed on this line, gather continuation
            paren_depth = line.count("(") - line.count(")")
            j = i + 1
            while paren_depth > 0 and j < len(lines):
                continuation = lines[j]
                param_text += " " + continuation.strip()
                paren_depth += continuation.count("(") - continuation.count(")")
                j += 1

            # Clean up param_text — remove trailing )
            if ")" in param_text:
                param_text = param_text[:param_text.rfind(")")]

            # Parse return type from the full signature line(s)
            full_sig = " ".join(lines[i:j]).strip() if j > i + 1 else line
            return_type = None
            ret_match = _RETURN_TYPE_RE.search(full_sig)
            if ret_match:
                return_type = ret_match.group(1).strip()

            params = _parse_params(param_text)

            # Determine class context
            class_name = None
            for cn, ci in reversed(class_stack):
                if def_indent > ci:
                    class_name = cn
                    break

            # Determine visibility
            visibility = "private" if func_name.startswith("_") and not func_name.startswith("__") else "public"

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,  # 1-indexed
                class_name=class_name,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=return_type,
                file_hash=file_hash,
            ))
            i = j if j > i + 1 else i + 1
            continue

        i += 1

    return skeletons


def scan_directory(
    root: Path,
    excludes: list[str] | None = None,
) -> list[Skeleton]:
    """Walk a directory tree and scan all Python files.

    Default excludes: __pycache__, node_modules, .git, .venv, etc.
    Files are read as UTF-8 with errors='replace'.
    """
    exclude_set = set(excludes) if excludes is not None else DEFAULT_EXCLUDES
    skeletons: list[Skeleton] = []

    for py_file in sorted(root.rglob("*.py")):
        # Skip excluded directories
        if any(part in exclude_set for part in py_file.parts):
            continue
        skeletons.extend(scan_file(py_file))

    return skeletons
