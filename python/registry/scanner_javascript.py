"""JavaScript skeleton scanner — extracts function/method/class signatures.

Line-by-line text scanning with brace-depth counting. No AST, no tree-sitter.
Fully independent from scanner_typescript.py.
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

# function greet(name) {
# export function greet(name) {
# export default function main() {
# async function loadData() {
_FUNC_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(async\s+)?"                      # optional async
    r"function\s+(\w+)"                 # function keyword + name
    r"\s*\("                            # opening paren
)

# const handler = (req, res) => {
# export const handler = async (req) => {
# let processor = function(data) {
# const processor = function processData(data) {
_ARROW_RE = re.compile(
    r"^(\s*)"                           # leading whitespace
    r"(?:export\s+)?(?:default\s+)?"    # optional export/default
    r"(?:const|let|var)\s+(\w+)"        # binding keyword + name
    r"\s*=\s*"                          # assignment
    r"(async\s+)?"                      # optional async
    r"(?:function\s*(?:\w+\s*)?)?"      # optional function keyword + optional name
    r"\("                               # opening paren
)

# class UserService {
# export class UserService extends Base {
_CLASS_RE = re.compile(
    r"^(\s*)"
    r"(?:export\s+)?(?:default\s+)?"
    r"class\s+(\w+)"
)

# Method inside a class (must be indented):
#   async getUser(id) {
#   #privateMethod(data) {
_METHOD_RE = re.compile(
    r"^(\s+)"                           # must be indented
    r"(?:static\s+)?(?:get\s+|set\s+)?"  # optional static/getter/setter
    r"(async\s+)?"                      # optional async
    r"(#?\w+)"                          # method name (# for private fields)
    r"\s*\("                            # opening paren
)

# module.exports = function handler(req, res) {
# module.exports = function(req, res) {
# module.exports = (req, res) => {
# module.exports = async (req) => {
_MODULE_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"module\.exports\s*=\s*"
    r"(async\s+)?"
    r"(?:function\s*(\w+)?\s*)?"        # optional function keyword + optional name
    r"\("                               # opening paren
)

# exports.handler = function(req, res) {
# exports.handler = (req, res) => {
# exports.handler = async function process(req) {
_NAMED_EXPORTS_RE = re.compile(
    r"^(\s*)"
    r"exports\.(\w+)\s*=\s*"            # exports.name =
    r"(async\s+)?"                      # optional async
    r"(?:function\s*(?:\w+\s*)?)?"      # optional function keyword + optional name
    r"\("                               # opening paren
)


def _parse_js_params(param_str: str) -> list[SkeletonParam]:
    """Parse a JavaScript parameter string into SkeletonParam objects.

    No type annotations in JS — just parameter names, possibly with defaults,
    rest (...), and destructured patterns.
    """
    params: list[SkeletonParam] = []
    param_str = " ".join(param_str.split()).strip()
    if not param_str:
        return params

    # Split at top-level commas
    depth = 0
    segments: list[str] = []
    current = ""
    for ch in param_str:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            segments.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        segments.append(current.strip())

    for seg in segments:
        if not seg:
            continue

        name = seg.strip()

        # Strip default value at depth 0
        depth = 0
        for i, ch in enumerate(name):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "=" and depth == 0:
                name = name[:i].strip()
                break

        # Handle rest/spread: ...args
        if name.startswith("..."):
            name = name[3:]

        if not name:
            continue

        params.append(SkeletonParam(name=name, type="", is_self=False))

    return params


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
    """Extract function/method/class skeletons from a JavaScript file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    if not text.strip():
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
            brace_depth += line.count("{") - line.count("}")
            i += 1
            continue

        # Check for module.exports pattern
        mod_match = _MODULE_EXPORTS_RE.match(stripped)
        if mod_match:
            is_async = bool(mod_match.group(2))
            func_name = mod_match.group(3) or "default_export"

            paren_start = stripped.index("(")
            param_text, j, full_sig = _gather_params(lines, i, stripped[paren_start + 1:])
            params = _parse_js_params(param_text)

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=None,
                visibility="public",
                is_async=is_async,
                params=params,
                return_type=None,
                file_hash=file_hash,
            ))
            for k in range(i, j):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            while class_stack and brace_depth <= class_stack[-1][1]:
                class_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Check for exports.name pattern
        exports_match = _NAMED_EXPORTS_RE.match(stripped)
        if exports_match:
            func_name = exports_match.group(2)
            is_async = bool(exports_match.group(3))

            paren_start = stripped.index("(")
            param_text, j, full_sig = _gather_params(lines, i, stripped[paren_start + 1:])
            params = _parse_js_params(param_text)

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=None,
                visibility="public",
                is_async=is_async,
                params=params,
                return_type=None,
                file_hash=file_hash,
            ))
            for k in range(i, j):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            while class_stack and brace_depth <= class_stack[-1][1]:
                class_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Check for function declaration
        func_match = _FUNC_RE.match(line)
        if func_match:
            is_async = bool(func_match.group(2))
            func_name = func_match.group(3)

            paren_start = line.index("(")
            param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])
            params = _parse_js_params(param_text)

            visibility = "private" if func_name.startswith("#") else "public"
            current_class = class_stack[-1][0] if class_stack else None

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=current_class,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=None,
                file_hash=file_hash,
            ))
            for k in range(i, j):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            while class_stack and brace_depth <= class_stack[-1][1]:
                class_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Check for arrow function / function expression
        arrow_match = _ARROW_RE.match(line)
        if arrow_match:
            func_name = arrow_match.group(2)
            is_async = bool(arrow_match.group(3))

            paren_start = line.index("(", arrow_match.start(2))
            param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])
            params = _parse_js_params(param_text)

            visibility = "private" if func_name.startswith("#") else "public"
            current_class = class_stack[-1][0] if class_stack else None

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=current_class,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=None,
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
            if method_match:
                is_async = bool(method_match.group(2))
                method_name = method_match.group(3)

                # Skip constructor
                if method_name == "constructor":
                    brace_depth += line.count("{") - line.count("}")
                    while class_stack and brace_depth <= class_stack[-1][1]:
                        class_stack.pop()
                    i += 1
                    continue

                paren_start = line.index("(")
                param_text, j, full_sig = _gather_params(lines, i, line[paren_start + 1:])
                params = _parse_js_params(param_text)

                # # prefix means private
                visibility = "private" if method_name.startswith("#") else "public"

                skeletons.append(Skeleton(
                    function_name=method_name,
                    file_path=str(path),
                    line_number=i + 1,
                    class_name=class_stack[-1][0],
                    visibility=visibility,
                    is_async=is_async,
                    params=params,
                    return_type=None,
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
    """Walk a directory tree and scan all JavaScript files.

    Scans .js and .jsx files (not .min.js or .ts/.tsx).
    Default excludes: node_modules, .git, dist, build, etc.
    """
    exclude_set = set(excludes) if excludes is not None else DEFAULT_EXCLUDES
    skeletons: list[Skeleton] = []

    for ext in ("*.js", "*.jsx"):
        for js_file in sorted(root.rglob(ext)):
            # Skip excluded directories
            if any(part in exclude_set for part in js_file.parts):
                continue
            # Skip minified files
            if js_file.name.endswith(".min.js"):
                continue
            skeletons.extend(scan_file(js_file))

    return skeletons
