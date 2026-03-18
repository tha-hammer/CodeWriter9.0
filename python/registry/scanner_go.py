"""Go skeleton scanner — extracts func/method signatures.

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
    "vendor", ".git", "node_modules", "testdata",
    "__pycache__", ".venv", "build", "dist",
}

# ── Regex patterns ────────────────────────────────────────────────

# func Hello(name string) string {
# func (s *UserService) GetUser(id int) (*User, error) {
_FUNC_RE = re.compile(
    r"^func\s+"
    r"(?:\((\w+)\s+\*?(\w+)\)\s+)?"  # optional receiver: (s *Type)
    r"(\w+)"                           # function name
    r"\s*\("                           # opening paren
)


def _parse_go_params(param_str: str) -> list[SkeletonParam]:
    """Parse Go parameter string into SkeletonParam objects.

    Handles Go's shared-type syntax: (a, b int) means both are int.
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
        if ch in "({":
            depth += 1
            current += ch
        elif ch in ")}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            segments.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        segments.append(current.strip())

    # Go allows shared types: a, b int means both have type int.
    # We parse segments, then backfill types.
    raw: list[tuple[str, str]] = []
    for seg in segments:
        parts = seg.split()
        if len(parts) >= 2:
            # name type  (e.g., "id int" or "ctx context.Context")
            name = parts[0]
            type_str = " ".join(parts[1:])
            raw.append((name, type_str))
        elif len(parts) == 1:
            # Just a name (type comes from the next segment that has one)
            raw.append((parts[0], ""))

    # Backfill: walk backwards, carry the last-seen type to any empty slots
    last_type = ""
    for i in range(len(raw) - 1, -1, -1):
        name, t = raw[i]
        if t:
            last_type = t
        else:
            raw[i] = (name, last_type)

    for name, type_str in raw:
        params.append(SkeletonParam(name=name, type=type_str, is_self=False))

    return params


def _parse_return_type(sig: str) -> str | None:
    """Extract return type from a Go function signature.

    Handles: ) string {, ) (string, error) {, ) (cfg *Config, err error) {
    """
    # Find the closing paren of the parameter list
    idx = sig.rfind(")")
    if idx < 0:
        return None

    # But for multi-return types there may be another ) — we need the one matching
    # the opening ( of the params. Use depth counting from the func opening paren.
    # Find the opening paren
    open_idx = sig.find("(")
    if open_idx < 0:
        return None

    depth = 0
    param_close = -1
    for i in range(open_idx, len(sig)):
        if sig[i] == "(":
            depth += 1
        elif sig[i] == ")":
            depth -= 1
            if depth == 0:
                param_close = i
                break

    if param_close < 0:
        return None

    rest = sig[param_close + 1:].strip()
    if not rest or rest.startswith("{"):
        return None

    # Strip trailing {
    if "{" in rest:
        rest = rest[:rest.index("{")].strip()

    return rest if rest else None


def scan_file(path: Path) -> list[Skeleton]:
    """Extract function/method skeletons from a single Go file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    skeletons: list[Skeleton] = []

    # Track whether we're inside an interface block
    in_interface = False
    interface_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("//"):
            i += 1
            continue

        # Detect interface blocks: type Repository interface {
        if re.match(r"^type\s+\w+\s+interface\s*\{", stripped):
            in_interface = True
            interface_depth = 1
            i += 1
            continue

        # Track interface block depth
        if in_interface:
            interface_depth += stripped.count("{") - stripped.count("}")
            if interface_depth <= 0:
                in_interface = False
            i += 1
            continue

        # Check for function/method declaration
        func_match = _FUNC_RE.match(stripped)
        if func_match:
            receiver_var = func_match.group(1)  # noqa: F841
            receiver_type = func_match.group(2)
            func_name = func_match.group(3)

            # Gather parameter text
            paren_start = stripped.index("(", func_match.start(3))
            paren_depth = 0
            param_text = ""
            sig_lines = []
            j = i

            # Collect lines until we have balanced parens for the parameter list
            for j in range(i, len(lines)):
                l = lines[j]
                sig_lines.append(l.strip())
                for ch in l[paren_start if j == i else 0:]:
                    if ch == "(":
                        paren_depth += 1
                    elif ch == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            break
                if paren_depth == 0:
                    break

            j += 1
            full_sig = " ".join(sig_lines)

            # Extract param text between first ( and matching )
            sig_from_paren = full_sig[full_sig.index("(", full_sig.index(func_name)):]
            depth = 0
            param_end = -1
            for ci, ch in enumerate(sig_from_paren):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        param_end = ci
                        break

            param_str = sig_from_paren[1:param_end] if param_end > 0 else ""
            params = _parse_go_params(param_str)

            # Return type
            return_type = _parse_return_type(sig_from_paren)

            # Class context from receiver
            class_name = receiver_type if receiver_type else None

            # Visibility: Go convention — capitalized = exported (public)
            visibility = "public" if func_name[0].isupper() else "private"

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=class_name,
                visibility=visibility,
                is_async=False,
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
    """Walk a directory tree and scan all Go files.

    Skips _test.go files and vendor directories by default.
    """
    exclude_set = set(excludes) if excludes is not None else DEFAULT_EXCLUDES
    skeletons: list[Skeleton] = []

    for go_file in sorted(root.rglob("*.go")):
        # Skip excluded directories
        if any(part in exclude_set for part in go_file.parts):
            continue
        # Skip test files
        if go_file.name.endswith("_test.go"):
            continue
        skeletons.extend(scan_file(go_file))

    return skeletons
