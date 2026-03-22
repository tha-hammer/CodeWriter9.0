"""Rust skeleton scanner — extracts fn/method signatures.

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
    "target", ".git", "node_modules", "__pycache__",
    ".venv", "vendor", "build", "dist",
}

# ── Regex patterns ────────────────────────────────────────────────

# fn hello(name: &str) -> String {
# pub fn hello(name: &str) -> String {
# pub(crate) fn process(data: Vec<u8>) -> Result<(), Error> {
# async fn fetch(url: &str) -> Result<Response, Error> {
# pub async unsafe fn raw_ptr(p: *const u8) -> u8 {
# pub(super) const fn max_size() -> usize {
_FUNC_RE = re.compile(
    r"^(\s*)"                                    # leading whitespace
    r"(pub(?:\s*\([^)]*\))?\s+)?"               # optional pub/pub(crate)/pub(super)
    r"(?:default\s+)?"                           # optional default (trait impl)
    r"(?:const\s+)?"                             # optional const
    r"(async\s+)?"                               # optional async
    r"(?:unsafe\s+)?"                            # optional unsafe
    r"(?:extern\s+\"[^\"]*\"\s+)?"              # optional extern "C"
    r"fn\s+(\w+)"                                # fn keyword + name
    r"\s*(?:<[^{(]*?>)?"                         # optional generic params <T, U>
    r"\s*\("                                     # opening paren
)

# impl UserService {
# impl<T: Clone> Repository<T> {
# impl<'a> Decoder<'a> for MyDecoder {
# impl fmt::Display for UserService {
_IMPL_RE = re.compile(
    r"^(\s*)impl\b"                              # impl keyword
    r"(?:\s*<[^{]*?>)?"                          # optional generic params
    r"\s+(?:\w+(?:::\w+)*(?:<[^{]*?>)?\s+for\s+)?"  # optional Trait for
    r"(\w+)"                                     # type name
)

# trait Repository {
# pub trait Handler<T> {
_TRAIT_RE = re.compile(
    r"^(\s*)(?:pub(?:\s*\([^)]*\))?\s+)?trait\s+(\w+)"
)


def _parse_rust_params(param_str: str) -> list[SkeletonParam]:
    """Parse Rust parameter string into SkeletonParam objects."""
    params: list[SkeletonParam] = []
    param_str = " ".join(param_str.split()).strip()
    if not param_str:
        return params

    # Split at top-level commas
    depth = 0
    segments: list[str] = []
    current = ""
    for ch in param_str:
        if ch in "(<{[":
            depth += 1
            current += ch
        elif ch in ")>}]":
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

        # Handle self variants
        stripped = seg.strip()
        if stripped in ("self", "mut self"):
            params.append(SkeletonParam(name="self", type="Self", is_self=True))
            continue
        if stripped in ("&self", "&mut self"):
            params.append(SkeletonParam(name="self", type="&Self", is_self=True))
            continue

        # Regular param: name: type
        # Find the colon at depth 0
        depth = 0
        colon_idx = -1
        for i, ch in enumerate(stripped):
            if ch in "(<{[":
                depth += 1
            elif ch in ")>}]":
                depth -= 1
            elif ch == ":" and depth == 0:
                colon_idx = i
                break

        if colon_idx >= 0:
            name = stripped[:colon_idx].strip()
            type_str = stripped[colon_idx + 1:].strip()
            # Strip mut from name
            if name.startswith("mut "):
                name = name[4:]
            params.append(SkeletonParam(name=name, type=type_str, is_self=False))
        else:
            # Just a name, no type
            params.append(SkeletonParam(name=stripped, type="", is_self=False))

    return params


def _parse_return_type(sig: str) -> str | None:
    """Extract return type from a Rust function signature.

    Return type is between -> and where/{.
    """
    # Find ->
    arrow_idx = sig.find("->")
    if arrow_idx < 0:
        return None

    rest = sig[arrow_idx + 2:].strip()

    # Return type ends at 'where' or '{' at depth 0
    result = []
    depth = 0
    i = 0
    while i < len(rest):
        ch = rest[i]

        # Check for 'where' keyword at depth 0
        if depth == 0 and rest[i:].startswith("where") and (
            i + 5 >= len(rest) or not rest[i + 5].isalnum()
        ):
            break

        if ch == "{" and depth == 0:
            break

        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1

        result.append(ch)
        i += 1

    ret = "".join(result).strip()
    return ret if ret else None


def _gather_signature(lines: list[str], start: int) -> tuple[str, int]:
    """Gather a full function signature from start line until opening brace.

    Returns (full_signature_text, end_line_index).
    """
    sig_lines = []
    j = start
    brace_found = False

    while j < len(lines):
        sig_lines.append(lines[j])
        line = lines[j]
        # Check if this line has an opening brace at depth 0 (outside params)
        paren_depth = 0
        for ch in line:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
            elif ch == "{" and paren_depth == 0:
                brace_found = True
                break
        if brace_found:
            break
        # Also check for ; (declaration without body, e.g., in trait)
        if ";" in line and paren_depth == 0:
            break
        j += 1

    return " ".join(l.strip() for l in sig_lines), j + 1


def scan_file(path: Path) -> list[Skeleton]:
    """Extract function/method skeletons from a single Rust file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return []

    if not text.strip():
        return []

    file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    skeletons: list[Skeleton] = []

    # Track impl/trait blocks via brace depth
    # Each entry: (type_name_or_None, brace_depth_at_open, is_trait)
    block_stack: list[tuple[str | None, int, bool]] = []
    brace_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and single-line comments
        if not stripped or stripped.startswith("//"):
            i += 1
            continue

        # Skip attributes (but don't skip the next line)
        if stripped.startswith("#[") or stripped.startswith("#!["):
            # Just update braces and continue
            brace_depth += stripped.count("{") - stripped.count("}")
            i += 1
            continue

        # Check for trait block
        trait_match = _TRAIT_RE.match(line)
        if trait_match and "{" in line:
            block_stack.append((None, brace_depth, True))
            brace_depth += line.count("{") - line.count("}")
            i += 1
            continue

        # Check for impl block
        impl_match = _IMPL_RE.match(line)
        if impl_match and not _FUNC_RE.match(line):
            type_name = impl_match.group(2)
            # impl Trait for Type blocks are treated like trait blocks
            # (methods are trait-required, not standalone)
            is_trait_impl = bool(re.search(r'\bfor\b', line[:line.index('{')] if '{' in line else line))
            block_stack.append((type_name, brace_depth, is_trait_impl))
            brace_depth += line.count("{") - line.count("}")
            # Pop blocks that have closed
            while block_stack and brace_depth <= block_stack[-1][1]:
                block_stack.pop()
            i += 1
            continue

        # Check for fn declaration
        func_match = _FUNC_RE.match(line)
        if func_match:
            # Check if we're inside a trait block (skip trait method signatures)
            in_trait = any(is_trait for _, _, is_trait in block_stack)
            if in_trait:
                # Still need to track braces
                brace_depth += line.count("{") - line.count("}")
                while block_stack and brace_depth <= block_stack[-1][1]:
                    block_stack.pop()
                i += 1
                continue

            leading_ws = func_match.group(1)
            pub_str = func_match.group(2)
            is_async = bool(func_match.group(3))
            func_name = func_match.group(4)

            # Gather full signature (may span multiple lines)
            full_sig, j = _gather_signature(lines, i)

            # Extract param text between first ( and matching )
            paren_start = full_sig.index("(")
            depth = 0
            param_end = -1
            for ci, ch in enumerate(full_sig[paren_start:], paren_start):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        param_end = ci
                        break

            param_str = full_sig[paren_start + 1:param_end] if param_end > 0 else ""
            params = _parse_rust_params(param_str)

            # Return type
            after_params = full_sig[param_end + 1:] if param_end > 0 else ""
            return_type = _parse_return_type(after_params)

            # Visibility
            if pub_str and pub_str.strip() == "pub":
                visibility = "public"
            else:
                visibility = "private"

            # Class context from impl block
            class_name = None
            for type_name, _, is_trait in reversed(block_stack):
                if type_name and not is_trait:
                    class_name = type_name
                    break

            skeletons.append(Skeleton(
                function_name=func_name,
                file_path=str(path),
                line_number=i + 1,
                class_name=class_name,
                visibility=visibility,
                is_async=is_async,
                params=params,
                return_type=return_type,
                file_hash=file_hash,
            ))

            # Update brace depth for consumed lines
            for k in range(i, min(j, len(lines))):
                brace_depth += lines[k].count("{") - lines[k].count("}")
            while block_stack and brace_depth <= block_stack[-1][1]:
                block_stack.pop()
            i = j if j > i + 1 else i + 1
            continue

        # Track brace depth
        brace_depth += line.count("{") - line.count("}")
        while block_stack and brace_depth <= block_stack[-1][1]:
            block_stack.pop()

        i += 1

    return skeletons


def scan_directory(
    root: Path,
    excludes: list[str] | None = None,
) -> list[Skeleton]:
    """Walk a directory tree and scan all Rust files.

    Does NOT skip test files (ingested for confirmatory first-pass use).
    Default excludes: target, .git, vendor, etc.
    """
    exclude_set = set(excludes) if excludes is not None else DEFAULT_EXCLUDES
    skeletons: list[Skeleton] = []

    for rs_file in sorted(root.rglob("*.rs")):
        # Skip excluded directories
        if any(part in exclude_set for part in rs_file.parts):
            continue
        skeletons.extend(scan_file(rs_file))

    return skeletons
