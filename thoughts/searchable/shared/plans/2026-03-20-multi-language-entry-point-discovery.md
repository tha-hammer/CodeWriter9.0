```
┌─────────────────────────────────────────────────────────────────┐
│  Multi-Language Entry Point Discovery Implementation Plan       │
│  Status: ✅ Revised  |  Date: 2026-03-20 (rev 2026-03-23)      │
└─────────────────────────────────────────────────────────────────┘
```

# Multi-Language Entry Point Discovery

## 📚 Overview

CW9 currently finds "front door" functions (main functions, web route handlers,
CLI commands, public API surface) only for Python projects. For JavaScript,
TypeScript, Go, and Rust, it falls back to treating every function as equally
important, which means crawl order is random instead of prioritized.

This plan adds entry point discovery for all four non-Python languages by reusing
the information scanners already collect (visibility, class membership) and adding
targeted pattern matching for framework-specific entry points (Express routes,
Cobra commands, Axum handlers, etc.).

## 📊 Current State Analysis

### What Works Today

| Component | All 5 Languages? | Notes |
|---|---|---|
| `_detect_language()` | ✅ | Manifest probing + extension counting |
| `detect_codebase_type()` | ✅ | Framework detection per language |
| Scanners (`scanner_*.py`) | ✅ | Extract every function with visibility, class_name |
| `discover_entry_points()` | 🔴 Python only | Line 156 gates non-Python to `return []` |

### The Gate (`entry_points.py:156-157`)

```python
if lang and lang != "python":
    return []
```

All non-Python languages hit this and get nothing. The crawl then falls back to
`cli.py:1056-1061` which treats ALL skeleton records as entry points — no priority.

### What Scanners Already Know

| Signal | JS | TS | Go | Rust |
|---|---|---|---|---|
| `visibility="public"` | ✅ `export` keyword, `module.exports` | ✅ `export` keyword, TS access modifiers | ✅ Capitalized name | ✅ `pub` keyword |
| `class_name=None` (top-level) | ✅ | ✅ | ✅ (no receiver) | ✅ (no `impl` block) |
| `return_type` | ❌ always None | ✅ | ✅ | ✅ |
| `is_async` | ✅ | ✅ | ❌ always False | ✅ |

### Key Discovery

- `entry_points.py:148-177`: `discover_entry_points()` takes `root: Path` and
  `codebase_type: str` but does NOT take the already-scanned skeletons
- `cli.py:830` (inside `_ingest_scan()`): skeletons are produced first, then
  entry points are discovered separately at line 840 — they never see each other
- For Go and Rust, `visibility="public"` + `class_name is None` already identifies
  the public API surface without any new file scanning
- For JS/TS, the same filter works for ESM exports, but framework patterns
  (Express routes, package.json `bin` field) need additional file-level checks

## 🎯 Desired End State

After this plan is complete:

- `discover_entry_points()` returns prioritized `EntryPoint` lists for all 5 languages
- Entry points are seeded from scanner output (no redundant file scanning)
- Framework-specific patterns (Express, Gin, Axum, etc.) are detected where scanners can't
- Crawl processes front-door functions first for all languages
- All existing Python entry point tests still pass
- New tests cover each language's discovery patterns

### How to Verify

```bash
cd python && python3 -m pytest tests/test_scanner_python.py -v
```

All existing tests pass, plus new test classes for JS, TS, Go, Rust entry points.

Manual verification: run `cw9 ingest` on a real multi-language project and confirm
`Entry points: N` shows a non-zero count.

## 🚫 What We're NOT Doing

| Not Doing | Doing Instead |
|---|---|
| Fixing Python entry point resolution bugs (class_name mismatch, `__main__` mapping) | Those are tracked in companion research doc, separate work |
| Adding `end_line_number` to Skeleton | Separate bug fix, doesn't affect discovery |
| Registering this in the TLA+ pipeline (`_self_describe`) | Traditional implementation — this is regex pattern matching, not graph operations |
| NestJS decorator scanning | Can be added later; TypeScript ESM exports cover the common case |
| Next.js/Nuxt file-convention routing | Directory-structure detection is a different problem; defer |
| Changing `CrawlOrchestrator` DFS logic | We only change what entry points are *found*, not how they're *used* |

## 🚀 Implementation Approach

The core idea: change `discover_entry_points()` to accept the already-computed
skeleton list and use it as the primary data source. Per-language discoverers
filter skeletons for public API / main functions, then do targeted file reads
only for patterns scanners can't detect (framework route registrations, manifest
fields).

```
Before:
  scan_directory() → skeletons     (thrown away for entry points)
  discover_entry_points() → []     (re-scans files, but gates non-Python)

After:
  scan_directory() → skeletons
  discover_entry_points(skeletons=skeletons) → EntryPoint list
      ├── filter skeletons by visibility/name  (all languages)
      └── scan for framework patterns          (where needed)
```

---

╔═══════════════════════════════════════╗
║            PHASE 1                     ║
║  Refactor the Gate + Signature         ║
╚═══════════════════════════════════════╝

## Phase 1: Refactor the Gate + Signature

### Overview

Change `discover_entry_points()` to accept an optional `skeletons` parameter and
route to per-language discoverers instead of short-circuiting.

### Changes Required

#### 1. Update function signature
**File**: `python/registry/entry_points.py`
**Lines**: 148-177

Replace the gate and dispatch logic:

```python
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
    entry_points.extend(_discover_main_functions(root))
    if codebase_type == "library" or not entry_points:
        entry_points.extend(_discover_public_api(root))
    return entry_points
```

#### 2. Add Skeleton import
**File**: `python/registry/entry_points.py`
**Lines**: 12 (add to existing import)

```python
from registry.crawl_types import EntryPoint, EntryType, Skeleton
```

Note: `Skeleton` is imported from `crawl_types` — check the actual location.
If it's in a different module, adjust the import accordingly.

#### 3. Update _ingest_scan to pass skeletons
**File**: `python/registry/cli.py`
**Line**: 840 (inside `_ingest_scan()`)

Change:
```python
entry_points = discover_entry_points(ingest_path, codebase_type, lang=lang)
```

To:
```python
entry_points = discover_entry_points(ingest_path, codebase_type, lang=lang, skeletons=skeletons)
```

This passes the already-computed skeleton list through. No other changes to
`_ingest_scan` are needed — the skeletons variable is already in scope at line 830.

### Success Criteria

#### Automated Verification:
- [x] All existing Python entry point tests pass: `python3 -m pytest tests/test_scanner_python.py::TestDetectCodebaseType tests/test_scanner_python.py::TestDiscoverWebRoutes tests/test_scanner_python.py::TestDiscoverCliCommands tests/test_scanner_python.py::TestDiscoverMainFunctions tests/test_scanner_python.py::TestDiscoverPublicApi -v`
- [x] No import errors: `python3 -c "from registry.entry_points import discover_entry_points"`

#### Manual Verification:
- [x] `cw9 ingest .` on a Python project still shows non-zero entry points

---

╔═══════════════════════════════════════╗
║            PHASE 2                     ║
║  Go + Rust Discoverers                 ║
╚═══════════════════════════════════════╝

## Phase 2: Go + Rust Entry Point Discoverers

### Overview

These are the simplest languages because the scanner already captures everything
we need. `visibility="public"` means exported in both languages. `func main()` /
`fn main()` is the binary entry point. Framework route patterns need light regex.

### Changes Required

#### 1. Go discoverer
**File**: `python/registry/entry_points.py`

```python
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
        # main() in any file is a binary entry point
        if skel.function_name == "main" and skel.class_name is None:
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name="main",
                entry_type=EntryType.MAIN,
            ))
            continue

        # Public package-level functions are the library API
        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    # Framework route detection (Gin, Echo, Chi, Gorilla)
    if codebase_type == "web_app":
        entry_points.extend(_discover_go_routes(root, seen))

    # Cobra CLI command detection
    if codebase_type == "cli":
        entry_points.extend(_discover_go_cli_commands(root, seen))

    return entry_points
```

#### 2. Go framework patterns
**File**: `python/registry/entry_points.py`

```python
_GO_ROUTE_RE = re.compile(
    r'\.\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\(\s*"([^"]+)"'
)
# Matches: r.GET("/path", handler), e.POST("/path", handler), etc.

_GO_HANDLE_FUNC_RE = re.compile(
    r'(?:HandleFunc|Handle)\s*\(\s*"([^"]+)"'
)
# Matches: http.HandleFunc("/path", handler), mux.Handle("/path", handler)


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
                    method=None,  # HandleFunc is method-agnostic
                ))
    return entry_points


_GO_COBRA_RE = re.compile(r'cobra\.Command\s*\{[^}]*Use:\s*"(\w+)"', re.DOTALL)


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
```

#### 3. Rust discoverer
**File**: `python/registry/entry_points.py`

```python
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
        # fn main() is the binary entry point
        if skel.function_name == "main" and skel.class_name is None:
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name="main",
                entry_type=EntryType.MAIN,
            ))
            continue

        # pub functions in lib.rs are the library API
        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    # Axum/Actix/Rocket route detection
    if codebase_type == "web_app":
        entry_points.extend(_discover_rust_routes(root, seen))

    # Clap CLI detection
    if codebase_type == "cli":
        entry_points.extend(_discover_rust_cli(root, seen))

    return entry_points
```

#### 4. Rust framework patterns
**File**: `python/registry/entry_points.py`

```python
_RUST_ROUTE_ATTR_RE = re.compile(
    r'#\[(get|post|put|delete|patch|head)\s*\(\s*"([^"]+)"'
)
# Matches: #[get("/path")], #[post("/path")] — Actix-web and Rocket

_RUST_AXUM_ROUTE_RE = re.compile(
    r'\.route\s*\(\s*"([^"]+)"\s*,\s*(get|post|put|delete|patch|head)\s*\('
)
# Matches: .route("/path", get(handler))

_RUST_FN_AFTER_ATTR_RE = re.compile(r'^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)')


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

        # Attribute macro routes (#[get("/path")] on next fn)
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

        # Axum router builder routes
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


_RUST_CLAP_RE = re.compile(r'#\[derive\([^)]*Parser[^)]*\)\]')


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
    return entry_points
```

### Success Criteria

#### Automated Verification:
- [x] All existing tests pass: `cd python && python3 -m pytest tests/test_scanner_python.py -v`
- [x] New Go tests pass (added in Phase 5)
- [x] New Rust tests pass (added in Phase 5)

#### Manual Verification:
- [ ] `cw9 ingest <go-project>` shows non-zero entry points
- [ ] `cw9 ingest <rust-project>` shows non-zero entry points

---

╔═══════════════════════════════════════╗
║            PHASE 3                     ║
║  JavaScript + TypeScript Discoverers   ║
╚═══════════════════════════════════════╝

## Phase 3: JavaScript + TypeScript Entry Point Discoverers

### Overview

JS/TS need both skeleton filtering (for ESM exports) and file-level scanning
(for Express routes, package.json fields, commander CLI registrations). A single
shared discoverer handles both languages since their patterns overlap heavily.

### Changes Required

#### 1. JS/TS discoverer
**File**: `python/registry/entry_points.py`

```python
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

    # Check package.json for bin/main fields
    entry_points.extend(_discover_js_manifest_entry_points(root, seen))

    for skel in skeletons:
        # Public top-level functions are the module API
        if (skel.visibility == "public"
                and skel.class_name is None
                and codebase_type == "library"):
            _add(EntryPoint(
                file_path=skel.file_path,
                function_name=skel.function_name,
                entry_type=EntryType.PUBLIC_API,
            ))

    # Express/Koa/Hapi route detection
    if codebase_type == "web_app":
        entry_points.extend(_discover_js_routes(root, seen, lang=lang))

    # Commander/yargs CLI detection
    if codebase_type == "cli":
        entry_points.extend(_discover_js_cli_commands(root, seen, lang=lang))

    # Main entry points from package.json main/module fields (already found above)
    # If nothing found, fall back to exported functions as public API
    if not entry_points:
        for skel in skeletons:
            if skel.visibility == "public" and skel.class_name is None:
                _add(EntryPoint(
                    file_path=skel.file_path,
                    function_name=skel.function_name,
                    entry_type=EntryType.PUBLIC_API,
                ))

    return entry_points
```

#### 2. package.json manifest parsing
**File**: `python/registry/entry_points.py`

```python
import json


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

    # "bin" field — CLI entry points
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

    # "main" field — primary entry point
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
```

#### 3. JS/TS route detection
**File**: `python/registry/entry_points.py`

```python
_JS_ROUTE_RE = re.compile(
    r'\.\s*(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']'
)
# Matches: app.get("/path", handler), router.post('/path', handler)

_JS_DEF_RE = re.compile(r'(?:function|const|let|var)\s+(\w+)')


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
```

#### 4. JS/TS CLI command detection
**File**: `python/registry/entry_points.py`

```python
_JS_CLI_COMMAND_RE = re.compile(r'\.command\s*\(\s*["\'](\w+)["\']')
# Matches: program.command("build"), .command('serve')
# Works for both commander and yargs — same .command("name", ...) API


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
```

### Success Criteria

#### Automated Verification:
- [x] All existing tests pass: `cd python && python3 -m pytest tests/test_scanner_python.py -v`
- [x] New JS tests pass (added in Phase 5)
- [x] New TS tests pass (added in Phase 5)

#### Manual Verification:
- [ ] `cw9 ingest <express-project>` shows HTTP_ROUTE entry points
- [ ] `cw9 ingest <typescript-library>` shows PUBLIC_API entry points

---

╔═══════════════════════════════════════╗
║            PHASE 4                     ║
║  Wire into cmd_ingest                  ║
╚═══════════════════════════════════════╝

## Phase 4: Wire into cmd_ingest

### Overview

This is the one-line change that connects everything. The skeletons computed at
`cli.py:830` (inside `_ingest_scan()`) get passed into `discover_entry_points()` at line 840.

### Changes Required

#### 1. Pass skeletons through
**File**: `python/registry/cli.py`
**Line**: 840 (inside `_ingest_scan()`)

```python
# Before:
entry_points = discover_entry_points(ingest_path, codebase_type, lang=lang)

# After:
entry_points = discover_entry_points(ingest_path, codebase_type, lang=lang, skeletons=skeletons)
```

That's it. The `skeletons` variable is already in scope from line 830.
The new `skeletons` keyword argument is optional (defaults to `None`), so
any other callers of `discover_entry_points` are unaffected.

### Success Criteria

#### Automated Verification:
- [x] Full test suite passes: `cd python && python3 -m pytest tests/ -v`
- [x] No import errors: `python3 -c "from registry.cli import cmd_ingest"`

#### Manual Verification:
- [ ] `cw9 ingest <go-project>` prints `Entry points: N` where N > 0
- [ ] `cw9 ingest <rust-project>` prints `Entry points: N` where N > 0
- [ ] `cw9 ingest <js-project>` prints `Entry points: N` where N > 0
- [ ] `cw9 ingest <python-project>` still works correctly (regression check)

---

╔═══════════════════════════════════════╗
║            PHASE 5                     ║
║  Tests                                 ║
╚═══════════════════════════════════════╝

## Phase 5: Tests

### Overview

Add test classes for each language following the existing pattern in
`test_scanner_python.py:227+`. Each test creates synthetic source files in
`tmp_path`, calls `discover_entry_points()` with the appropriate language,
and asserts on the returned `EntryPoint` objects.

### Changes Required

#### 1. New test file
**File**: `python/tests/test_entry_points_multi_lang.py`

A separate test file keeps things clean since the existing entry point tests
in `test_scanner_python.py` are Python-specific and interleaved with scanner tests.

```python
"""Tests for multi-language entry point discovery.

Covers: Go, Rust, JavaScript, TypeScript.
"""
import json
import pytest
from pathlib import Path

from registry.entry_points import discover_entry_points
from registry.crawl_types import EntryType, Skeleton


def _skel(file_path, function_name, *, visibility="public", class_name=None, **kw):
    """Helper to build a Skeleton with minimal required fields."""
    return Skeleton(
        file_path=file_path,
        function_name=function_name,
        line_number=1,
        params=[],
        return_type=None,
        file_hash="abc123",
        visibility=visibility,
        class_name=class_name,
        is_async=False,
        **kw,
    )


# ── Go tests ─────────────────────────────────────────────────────


class TestGoMainFunction:
    def test_finds_main(self, tmp_path: Path):
        skels = [_skel("main.go", "main")]
        eps = discover_entry_points(tmp_path, "cli", lang="go", skeletons=skels)
        assert len(eps) == 1
        assert eps[0].entry_type == EntryType.MAIN
        assert eps[0].function_name == "main"

    def test_ignores_method_named_main(self, tmp_path: Path):
        skels = [_skel("foo.go", "main", class_name="Server")]
        eps = discover_entry_points(tmp_path, "cli", lang="go", skeletons=skels)
        assert len(eps) == 0


class TestGoPublicApi:
    def test_finds_exported_functions(self, tmp_path: Path):
        skels = [
            _skel("pkg.go", "NewService", visibility="public"),
            _skel("pkg.go", "helperFunc", visibility="private"),
        ]
        eps = discover_entry_points(tmp_path, "library", lang="go", skeletons=skels)
        names = [ep.function_name for ep in eps]
        assert "NewService" in names
        assert "helperFunc" not in names

    def test_skips_methods(self, tmp_path: Path):
        skels = [_skel("pkg.go", "String", visibility="public", class_name="MyType")]
        eps = discover_entry_points(tmp_path, "library", lang="go", skeletons=skels)
        assert len(eps) == 0


class TestGoRoutes:
    def test_finds_gin_routes(self, tmp_path: Path):
        (tmp_path / "main.go").write_text(
            'package main\n\nfunc main() {\n\tr.GET("/users", getUsers)\n\tr.POST("/users", createUser)\n}\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="go", skeletons=[])
        routes = [ep.route for ep in eps if ep.entry_type == EntryType.HTTP_ROUTE]
        assert "/users" in routes

    def test_finds_http_handle_func(self, tmp_path: Path):
        (tmp_path / "main.go").write_text(
            'package main\n\nimport "net/http"\n\nfunc main() {\n\thttp.HandleFunc("/health", healthCheck)\n}\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="go", skeletons=[])
        routes = [ep.route for ep in eps if ep.entry_type == EntryType.HTTP_ROUTE]
        assert "/health" in routes

    def test_handle_func_method_is_none(self, tmp_path: Path):
        """HandleFunc is method-agnostic — method should be None, not GET."""
        (tmp_path / "main.go").write_text(
            'package main\n\nimport "net/http"\n\nfunc main() {\n\thttp.HandleFunc("/api", handler)\n}\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="go", skeletons=[])
        route_eps = [ep for ep in eps if ep.route == "/api"]
        assert len(route_eps) == 1
        assert route_eps[0].method is None


class TestGoCli:
    def test_finds_cobra_commands(self, tmp_path: Path):
        (tmp_path / "cmd.go").write_text(
            'package cmd\n\nvar serveCmd = &cobra.Command{\n\tUse: "serve",\n\tRun: runServe,\n}\n'
        )
        eps = discover_entry_points(tmp_path, "cli", lang="go", skeletons=[])
        names = [ep.function_name for ep in eps if ep.entry_type == EntryType.CLI_COMMAND]
        assert "serve" in names


# ── Rust tests ────────────────────────────────────────────────────


class TestRustMainFunction:
    def test_finds_main(self, tmp_path: Path):
        skels = [_skel("src/main.rs", "main")]
        eps = discover_entry_points(tmp_path, "cli", lang="rust", skeletons=skels)
        assert len(eps) == 1
        assert eps[0].entry_type == EntryType.MAIN

    def test_ignores_impl_main(self, tmp_path: Path):
        skels = [_skel("src/lib.rs", "main", class_name="App")]
        eps = discover_entry_points(tmp_path, "cli", lang="rust", skeletons=skels)
        assert len(eps) == 0


class TestRustPublicApi:
    def test_finds_pub_functions(self, tmp_path: Path):
        skels = [
            _skel("src/lib.rs", "new_service", visibility="public"),
            _skel("src/lib.rs", "internal_helper", visibility="private"),
        ]
        eps = discover_entry_points(tmp_path, "library", lang="rust", skeletons=skels)
        names = [ep.function_name for ep in eps]
        assert "new_service" in names
        assert "internal_helper" not in names


class TestRustRoutes:
    def test_finds_actix_route_attrs(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.rs").write_text(
            '#[get("/health")]\nasync fn health() -> impl Responder {\n    "ok"\n}\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="rust", skeletons=[])
        assert any(ep.route == "/health" for ep in eps)

    def test_finds_axum_routes(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.rs").write_text(
            'let app = Router::new()\n    .route("/users", get(list_users))\n    .route("/users", post(create_user));\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="rust", skeletons=[])
        routes = [ep.route for ep in eps]
        assert "/users" in routes


class TestRustCli:
    def test_finds_clap_parser(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.rs").write_text(
            '#[derive(Parser, Debug)]\n#[command(name = "myapp")]\nstruct Cli {\n    #[arg(short)]\n    verbose: bool,\n}\n'
        )
        eps = discover_entry_points(tmp_path, "cli", lang="rust", skeletons=[])
        names = [ep.function_name for ep in eps if ep.entry_type == EntryType.CLI_COMMAND]
        assert "Cli" in names


# ── JavaScript tests ──────────────────────────────────────────────


class TestJsManifest:
    def test_finds_bin_string(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"bin": "./cli.js"}))
        eps = discover_entry_points(tmp_path, "cli", lang="javascript", skeletons=[])
        assert any(ep.entry_type == EntryType.CLI_COMMAND for ep in eps)

    def test_finds_bin_dict(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"bin": {"mycli": "./bin/cli.js", "helper": "./bin/help.js"}})
        )
        eps = discover_entry_points(tmp_path, "cli", lang="javascript", skeletons=[])
        names = [ep.function_name for ep in eps if ep.entry_type == EntryType.CLI_COMMAND]
        assert "mycli" in names
        assert "helper" in names

    def test_finds_main_field(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"main": "index.js"}))
        eps = discover_entry_points(tmp_path, "library", lang="javascript", skeletons=[])
        assert any(ep.entry_type == EntryType.MAIN for ep in eps)


class TestJsRoutes:
    def test_finds_express_routes(self, tmp_path: Path):
        (tmp_path / "app.js").write_text(
            'const app = express()\napp.get("/users", getUsers)\napp.post("/users", createUser)\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="javascript", skeletons=[])
        routes = [ep.route for ep in eps if ep.entry_type == EntryType.HTTP_ROUTE]
        assert "/users" in routes

    def test_skips_node_modules(self, tmp_path: Path):
        nm = tmp_path / "node_modules" / "express"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text('app.get("/internal", handler)\n')
        eps = discover_entry_points(tmp_path, "web_app", lang="javascript", skeletons=[])
        assert not any(ep.route == "/internal" for ep in eps)


class TestJsCliCommands:
    def test_finds_commander_commands(self, tmp_path: Path):
        (tmp_path / "cli.js").write_text(
            'const { program } = require("commander")\nprogram.command("build")\nprogram.command("serve")\n'
        )
        eps = discover_entry_points(tmp_path, "cli", lang="javascript", skeletons=[])
        names = [ep.function_name for ep in eps if ep.entry_type == EntryType.CLI_COMMAND]
        assert "build" in names
        assert "serve" in names


class TestJsFallback:
    def test_all_public_exports_when_nothing_else_found(self, tmp_path: Path):
        """When no manifest, routes, or CLI commands found, fall back to all public exports."""
        skels = [
            _skel("index.js", "createApp", visibility="public"),
            _skel("index.js", "_helper", visibility="private"),
            _skel("utils.js", "formatDate", visibility="public"),
        ]
        # codebase_type="web_app" but no route files exist → no routes found → fallback
        eps = discover_entry_points(tmp_path, "web_app", lang="javascript", skeletons=skels)
        names = [ep.function_name for ep in eps]
        assert "createApp" in names
        assert "formatDate" in names
        assert "_helper" not in names


class TestJsPublicApi:
    def test_finds_exported_functions(self, tmp_path: Path):
        skels = [
            _skel("index.js", "createApp", visibility="public"),
            _skel("index.js", "_internal", visibility="private"),
        ]
        eps = discover_entry_points(tmp_path, "library", lang="javascript", skeletons=skels)
        names = [ep.function_name for ep in eps]
        assert "createApp" in names
        assert "_internal" not in names


# ── TypeScript tests ──────────────────────────────────────────────


class TestTsRoutes:
    def test_finds_express_routes_ts(self, tmp_path: Path):
        (tmp_path / "app.ts").write_text(
            'import express from "express"\nconst app = express()\napp.get("/api/health", healthCheck)\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="typescript", skeletons=[])
        routes = [ep.route for ep in eps if ep.entry_type == EntryType.HTTP_ROUTE]
        assert "/api/health" in routes


class TestTsPublicApi:
    def test_finds_exported_functions(self, tmp_path: Path):
        skels = [
            _skel("src/index.ts", "createService", visibility="public"),
            _skel("src/internal.ts", "helper", visibility="private"),
        ]
        eps = discover_entry_points(tmp_path, "library", lang="typescript", skeletons=skels)
        names = [ep.function_name for ep in eps]
        assert "createService" in names
        assert "helper" not in names

    def test_skips_d_ts_files(self, tmp_path: Path):
        (tmp_path / "types.d.ts").write_text(
            'export declare function foo(): void;\n'
        )
        eps = discover_entry_points(tmp_path, "web_app", lang="typescript", skeletons=[])
        # .d.ts files should not produce route entry points
        assert len(eps) == 0
```

### Success Criteria

#### Automated Verification:
- [x] All tests pass: `cd python && python3 -m pytest tests/test_entry_points_multi_lang.py tests/test_scanner_python.py -v`
- [ ] Full suite still passes: `cd python && python3 -m pytest tests/ -v`

#### Manual Verification:
- [ ] Test output shows all new test classes discovered and passing

---

## 🛡️ Testing Strategy

### Unit Tests (Phase 5)
- **Go**: main detection, public API filtering, Gin/Echo routes, HandleFunc (method=None), Cobra commands, method exclusion
- **Rust**: main detection, pub function filtering, Actix/Axum routes, Clap CLI, impl method exclusion
- **JavaScript**: package.json bin/main, Express routes, commander commands, node_modules exclusion, public API from skeletons, fallback behavior (all public exports when nothing else found)
- **TypeScript**: Express routes in .ts files, public API from skeletons, .d.ts exclusion

### Key Edge Cases
- Function named `main` inside a class/impl/receiver — should NOT be MAIN entry point
- Private functions should never appear as PUBLIC_API
- node_modules directory must be skipped for JS/TS
- .min.js and .d.ts files must be skipped
- Empty skeleton list should still find framework patterns from file scanning
- Missing package.json should not crash

### Regression
- All existing Python entry point tests must continue passing unchanged
- The Python code path in `discover_entry_points` is untouched

## Performance Considerations

- **Skeleton reuse eliminates redundant scanning**: For Go and Rust `library` type,
  no file I/O is needed at all — just filtering the in-memory skeleton list
- **Framework pattern scanning is targeted**: Only runs for the matching codebase type
  (web_app gets route scanning, cli gets command scanning, library gets neither)
- **node_modules exclusion**: The `node_modules` check in path parts prevents
  scanning potentially thousands of dependency files

## References

- Research: `thoughts/searchable/shared/research/2026-03-20-multi-language-entry-point-discovery.md`
- Companion bugs: `thoughts/searchable/shared/research/2026-03-20-crawl-entry-point-resolution-failures.md`
- Scanner architecture: `thoughts/searchable/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md`
- How-to guide: `thoughts/searchable/shared/docs/howto-brownfield-code-walker.md`
