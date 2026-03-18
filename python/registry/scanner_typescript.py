"""TypeScript/JavaScript skeleton scanner — extracts function/method/class signatures.

Line-by-line text scanning with brace-depth counting. No AST, no tree-sitter.
Produces Skeleton objects for each function/method found.
Follows the same interface as scanner_python.py.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from registry.crawl_types import Skeleton, SkeletonParam

# Default directories to skip during scan
DEFAULT_EXCLUDES = {
    "node_modules", ".git", ".next", "dist", "build", "out",
    ".nuxt", ".output", "coverage", ".turbo", ".cache",
    "__pycache__", ".venv", "vendor",
}

# ── Regex patterns ────────────────────────────────────────────────

# function greet(name: string): string {
# export function greet(...)
# export default function main(...)
# async function loadData(...)
_FUNC_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(async\s+)?"                      # optional async
    r"function\s+(\w+)"                 # function keyword + name
    r"\s*\("                            # opening paren
)

# const handler = (req: Request): void => {
# export const handler = async (req: Request) => {
_ARROW_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(?:const|let|var)\s+(\w+)"        # binding keyword + name
    r"\s*=\s*"                          # assignment
    r"(async\s+)?"                      # optional async
    r"\("                               # opening paren
)

# class UserService {
# export class UserService extends Base {
_CLASS_RE = re.compile(
    r"^(\s*)"
    r"(?:export\s+)?(?:default\s+)?(?:abstract\s+)?"
    r"class\s+(\w+)"
)

# Method inside a class:
#   async getUser(id: number): Promise<User> {
#   private validate(user: User): boolean {
_METHOD_RE = re.compile(
    r"^(\s+)"                           # must be indented
    r"(?:public\s+|private\s+|protected\s+|static\s+|readonly\s+|abstract\s+|override\s+)*"
    r"(async\s+)?"                      # optional async
    r"(\w+)"                            # method name
    r"\s*\("                            # opening paren
)

# Visibility keyword at start of method line
_VISIBILITY_RE = re.compile(
    r"^\s*(?:static\s+|readonly\s+|abstract\s+|override\s+)*(private|protected|public)\s+"
)


def _parse_return_type(sig: str) -> str | None:
    """Extract return type from a complete function signature.

    Looks for ): ReturnType { pattern, handling generic nesting.
    """
    # Find the closing paren that ends the parameter list
    idx = sig.rfind(")")
    if idx < 0:
        return None
    rest = sig[idx + 1:].strip()
    # Expect : ReturnType {
    if not rest.startswith(":"):
        return None
    rest = rest[1:].strip()
    # Strip trailing { or => or ;
    # Walk forward tracking angle bracket depth
    result = []
    depth = 0
    for ch in rest:
        if ch in "{" and depth == 0:
            break
        if ch == "=" and depth == 0:
            # arrow =>
            break
        if ch == ";" and depth == 0:
            break
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        result.append(ch)
    ret = "".join(result).strip()
    return ret if ret else None


def _parse_params(param_str: str) -> list[SkeletonParam]:
    """Parse a TypeScript parameter string into SkeletonParam objects."""
    params: list[SkeletonParam] = []
    param_str = " ".join(param_str.split()).strip()
    if not param_str:
        return params

    depth = 0
    current = ""
    for ch in param_str:
        if ch in "(<{":
            depth += 1
            current += ch
        elif ch in ")>}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            p = _parse_single_param(current.strip())
            if p:
                params.append(p)
            current = ""
        else:
            current += ch
    if current.strip():
        p = _parse_single_param(current.strip())
        if p:
            params.append(p)

    return params


def _parse_single_param(param: str) -> SkeletonParam | None:
    """Parse a single TS param like 'name: string' or 'name?: string = default'."""
    if not param:
        return None

    # Strip default value (at depth 0)
    depth = 0
    for i, ch in enumerate(param):
        if ch in "(<{":
            depth += 1
        elif ch in ")>}":
            depth -= 1
        elif ch == "=" and depth == 0:
            param = param[:i].strip()
            break

    # Handle rest/spread: ...args: string[]
    if param.startswith("..."):
        param = param[3:]

    # Split name: type at depth-0 colon
    name = param
    type_str = ""
    depth = 0
    for i, ch in enumerate(param):
        if ch in "(<{":
            depth += 1
        elif ch in ")>}":
            depth -= 1
        elif ch == ":" and depth == 0:
            name = param[:i].strip()
            type_str = param[i + 1:].strip()
            break

    # Strip optional marker
    if name.endswith("?"):
        name = name[:-1]

    return SkeletonParam(name=name, type=type_str, is_self=False)


def _is_export(line: str) -> bool:
    """Check if a line starts with export."""
    return line.lstrip().startswith("export")


def _gather_params(lines: list[str], start: int, initial_paren_content: str) -> tuple[str, int, str]:
    """Gather parameter text across continuation lines until parens balance.

    Returns (param_text, end_line_index, full_signature).
    """
    line = lines[start]
    paren_depth = line.count("(") - line.count(")")
    param_text = initial_paren_content
    sig_lines = [line]

    j = start + 1
    while paren_depth > 0 and j < len(lines):
        continuation = lines[j]
        param_text += " " + continuation.strip()
        paren_depth += continuation.count("(") - continuation.count(")")
        sig_lines.append(continuation)
        j += 1

    # Remove trailing ) from param_text
    if ")" in param_text:
        param_text = param_text[:param_text.rfind(")")]

    full_sig = " ".join(l.strip() for l in sig_lines)
    return param_text, j, full_sig


def scan_file(path: Path) -> list[Skeleton]:
    """Extract function/method/class skeletons from a TypeScript/JavaScript file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    skeletons: list[Skeleton] = []

    # Track class context via brace depth
    class_stack: list[tuple[str, int]] = []  # (class_name, brace_depth_at_open)
    brace_depth = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Skip empty lines and single-line comments
        if not stripped or stripped.startswith("//"):
            i += 1
            continue

        indent = len(line) - len(stripped)

        # Check for class definition
        class_match = _CLASS_RE.match(line)
        if class_match and "{" in line:
            class_name = class_match.group(2)
            class_stack.append((class_name, brace_depth))
            # Count braces on this line
            brace_depth += line.count("{") - line.count("}")
            i += 1
            continue

        # Check for function declaration
        func_match = _FUNC_RE.match(line)
        if func_match:
            is_async = bool(func_match.group(2))
            func_name = func_match.group(3)

            # Get everything after the opening paren
            paren_start = line.index("(")
            param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])

            params = _parse_params(param_text)
            return_type = _parse_return_type(full_sig[full_sig.index("("):])

            visibility = "public" if _is_export(line) else "private"
            # Determine class context
            current_class = class_stack[-1][0] if class_stack else None

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=current_class,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=return_type,
                file_hash=file_hash,
            ))
            # Update brace depth for all lines consumed
            for k in range(i, j):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            # Pop class stack if braces closed
            while class_stack and brace_depth <= class_stack[-1][1]:
                class_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Check for arrow function
        arrow_match = _ARROW_RE.match(line)
        if arrow_match:
            func_name = arrow_match.group(2)
            is_async = bool(arrow_match.group(3))

            paren_start = line.index("(", arrow_match.start(2))
            param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])

            params = _parse_params(param_text)
            # For arrow functions, look for ): ReturnType =>
            return_type = _parse_return_type(full_sig[full_sig.index("("):])

            visibility = "public" if _is_export(line) else "private"
            current_class = class_stack[-1][0] if class_stack else None

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=current_class,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=return_type,
                file_hash=file_hash,
            ))
            for k in range(i, j):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            while class_stack and brace_depth <= class_stack[-1][1]:
                class_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Check for class method (must be inside a class)
        if class_stack:
            method_match = _METHOD_RE.match(line)
            if method_match and method_match.group(3) != "constructor" or (
                method_match and method_match.group(3) == "constructor"
            ):
                is_async = bool(method_match.group(2))
                method_name = method_match.group(3)

                paren_start = line.index("(")
                param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])

                params = _parse_params(param_text)
                return_type = _parse_return_type(full_sig[full_sig.index("("):])

                # Determine visibility
                vis_match = _VISIBILITY_RE.match(line)
                visibility = vis_match.group(1) if vis_match else "public"

                skeletons.append(Skeleton(
                    function_name=method_name,
                    file_path=str(path),
                    line_number=i + 1,
                    class_name=class_stack[-1][0],
                    visibility=visibility,
                    is_async=is_async,
                    params=params,
                    return_type=return_type,
                    file_hash=file_hash,
                ))
                for k in range(i, j):
                    brace_depth += lines[k].count("{") - lines[k].count("}")
                while class_stack and brace_depth <= class_stack[-1][1]:
                    class_stack.pop()
                i = j if j > i + 1 else i + 1
                continue

        # Track brace depth for class scope
        brace_depth += line.count("{") - line.count("}")
        while class_stack and brace_depth <= class_stack[-1][1]:
            class_stack.pop()

        i += 1

    return skeletons


def scan_directory(
    root: Path,
    excludes: list[str] | None = None,
) -> list[Skeleton]:
    """Walk a directory tree and scan all TypeScript/JavaScript files.

    Scans .ts and .tsx files (not .d.ts declaration files).
    Default excludes: node_modules, .git, dist, build, etc.
    """
    exclude_set = set(excludes) if excludes is not None else DEFAULT_EXCLUDES
    skeletons: list[Skeleton] = []

    for ext in ("*.ts", "*.tsx"):
        for ts_file in sorted(root.rglob(ext)):
            # Skip excluded directories
            if any(part in exclude_set for part in ts_file.parts):
                continue
            # Skip declaration files
            if ts_file.name.endswith(".d.ts"):
                continue
            skeletons.extend(scan_file(ts_file))

    return skeletons
