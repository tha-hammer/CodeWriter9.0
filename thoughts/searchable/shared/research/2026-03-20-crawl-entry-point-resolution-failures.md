---
date: 2026-03-20T09:30:00-05:00
researcher: DustyForge
git_commit: 80b5a7d
branch: master
repository: CodeWriter9.0
topic: "Crawl entry point resolution failures and LLM JSON extraction errors"
tags: [research, codebase, crawl, entry-points, llm-extraction, bug-analysis, body-extraction]
status: complete
last_updated: 2026-03-20
last_updated_by: DustyForge
last_updated_note: "Resolved all open questions: class→all-methods expansion, build/lib exclusion, Option B confirmed, arrow fn strategy, multi-line comment handling"
---

```
┌──────────────────────────────────────────────────────────┐
│  Research: Crawl Entry Point Resolution & LLM Errors     │
│  Status: ✅ Complete  |  Date: 2026-03-20                │
└──────────────────────────────────────────────────────────┘
```

**Date**: 2026-03-20T09:30:00-05:00
**Researcher**: DustyForge
**Git Commit**: 80b5a7d
**Branch**: master
**Repository**: CodeWriter9.0

## Research Question

The `cw9 crawl --incremental` command produces two categories of errors:
1. "Entry point not found in store" for names like `ProjectContext`, `RegistryDag`, `__main__`
2. "No JSON object found in response" where the LLM returns prose instead of JSON

Evaluate the proposed fixes and document the root causes.

## 📊 Summary

Both errors are pre-existing bugs in the crawl pipeline. Issue 1 stems from a **naming mismatch** between how entry points are discovered (by class name / module name) vs. how records are stored (by method/function name). Issue 2 stems from a **broken body extraction function** that sends everything from the function's start line to the end of the file — not the actual function body — overwhelming the LLM with irrelevant code.

---

## 🔍 Detailed Findings

### Issue 1: Entry Point Not Found in Store

#### How Entry Points Are Discovered

`entry_points.py:369` (`_discover_public_api`) scans `__init__.py` for `__all__` members and creates `EntryPoint` records with `function_name` set to the **exported name** (e.g., `ProjectContext`, `RegistryDag`).

`entry_points.py:340` (`_discover_main_functions`) creates entries with `function_name="__main__"` for `__main__.py` files.

#### How Records Are Stored

The ingester stores records per **method**, not per class:

| Entry Point Name | Stored As | file_path |
|---|---|---|
| `ProjectContext` | `function_name=from_target`, `class_name=ProjectContext` | `registry/context.py` |
| `RegistryDag` | `function_name=add_node`, `class_name=RegistryDag` | `registry/dag.py` |
| `Edge` | `function_name=to_dict`, `class_name=Edge` | `registry/types.py` |
| `__main__` | **No record exists** | (not ingested) |
| `main` | `function_name=main`, `class_name=None` | `registry/cli.py` |

#### The Resolution Code

`crawl_orchestrator.py:222-237` (`_resolve_uuid_by_name`) searches **only** `rec.function_name`:

```python
def _resolve_uuid_by_name(self, function_name: str, source_file: str | None = None) -> str | None:
    # Searches rec.function_name == function_name
    # Never checks rec.class_name
```

#### Data Flow Gap

`cli.py:1053` extracts only the name, discarding the file path:

```python
entry_names = [ep.function_name for ep in stored_eps]
```

The orchestrator then receives bare names like `["ProjectContext", "__main__", "main"]` with no file context.

#### Three Distinct Sub-Cases

| Sub-Case | Entry Name | Why It Fails | Records Exist? |
|---|---|---|---|
| 🔴 Public API classes | `ProjectContext`, `RegistryDag`, `SchemaExtractor` | Stored as `class_name`, not `function_name` | Yes (methods) |
| 🔴 Type/enum classes | `Edge`, `EdgeType`, `Node`, `NodeKind` | Same class_name mismatch | Yes (methods) |
| 🔴 `__main__` modules | `__main__` | No record with this function_name; `main` exists separately | No direct match |

---

### Issue 2: LLM Returns Prose Instead of JSON

#### The Real Root Cause: `_read_function_body` Sends File Remainders, Not Function Bodies

The initial analysis incorrectly attributed this to "700-line functions." The functions themselves are normal-sized. The problem is in `crawl_orchestrator.py:35-71` (`_read_function_body`):

```python
def _read_function_body(file_path, function_name, line_number, project_root=None):
    # ...
    lines = text.splitlines()
    start = max(0, line_number - 1)

    if start < len(lines):
        return "\n".join(lines[start:])  # ← FROM START LINE TO EOF
```

**It reads from the function's start line to the end of the file.** There is no end-of-function detection — no indentation tracking, no AST parsing, nothing.

#### Measured Impact: Actual Function Size vs. What the LLM Receives

`cli.py` is 1780 lines. Here's what `_read_function_body` sends for each function:

| Function | Line | Actual Body | Sent to LLM | Ratio |
|---|---|---|---|---|
| `_get_engine_root` | 21 | **5 lines** | **1760 lines** | 352x |
| `cmd_init` | 57 | **79 lines** | **1724 lines** | 21.8x |
| `cmd_test` | 709 | **49 lines** | **1072 lines** | 21.9x |
| `cmd_crawl` | 1021 | **165 lines** | **760 lines** | 4.6x |
| `main` | 1628 | **149 lines** | **153 lines** | 1.0x |

For `_get_engine_root` — a 5-line helper — the LLM receives the **entire rest of the file**: 1760 lines containing 20+ unrelated functions, nested function definitions, argparse setup, system prompts, and JSON parsers. The LLM sees a wall of code that isn't the function it was asked about, tries to make sense of it, and generates reasoning prose instead of JSON.

#### Correlation: Every cli.py Function Failed Extraction

```
Total EXTRACTION_FAILED records: 39
  - registry/cli.py:         24 functions (all failed)
  - registry/bridge.py:       8 functions (720-line file)
  - registry/composer.py:     2 functions (537-line file)
  - registry/_resources.py:   2 functions
```

The 8 cli.py functions that **succeeded** are all small utilities defined late in the file (low "lines to EOF"):
- `_register_payload` (line 439) — succeeded despite 1342 lines to EOF, but it's a self-contained utility
- `_extract_json_object` (line 1270) — only 511 lines to EOF
- `_short_path`, `_positive_int`, `_format_elapsed` (lines 1000-1016) — small utilities near end

#### The Three Fallback Paths in `_read_function_body`

```python
# Path 1: line_number is None → returns ENTIRE FILE
if line_number is None:
    return text

# Path 2: line_number valid → returns from line to EOF (the common case)
if start < len(lines):
    return "\n".join(lines[start:])

# Path 3: line_number past EOF → searches for function name, returns from match to EOF
for i, line in enumerate(lines):
    if function_name in line:
        return "\n".join(lines[i:])

# Path 4: nothing found → returns ENTIRE FILE
return text
```

All four paths return too much. The function never attempts to find where the function *ends*.

#### What a Human Developer Does (and What the Code Should Do)

A human developer reading `cmd_init` at line 57 would:
1. See `def cmd_init(args):` with 0-indent
2. Read the indented body (lines 58-135)
3. Stop at line 136 when indentation returns to column 0 (the next `def`)

Python's `ast` module does exactly this — `ast.parse()` gives every `FunctionDef` node an `end_lineno` attribute (Python 3.8+). The scanner (`scanner_python.py`) already does indent-tracking for class context but doesn't record function end lines.

#### Why Prompt Hardening Alone Won't Fix This

Even with the strongest "return JSON only" instruction, sending 1760 lines of unrelated code to extract a 5-line function is fundamentally broken:
- The signal-to-noise ratio is 0.3% (5 / 1760)
- The LLM must somehow figure out which 5 of 1760 lines are "the function"
- Any model will struggle with that — it's not a prompt problem, it's a data problem

---

## 🎯 Fix Evaluation

### Fix 1: Class Name → All Methods Expansion

**Proposed**: Search `class_name` when `function_name` doesn't match.

**Assessment**: ✅ **Correct, but should resolve to ALL methods of the class, not just one.**

**Rationale**: When the entry point is `ProjectContext`, the intent is "this class is part of the public API — crawl it." Picking a single method and hoping DFS discovers the rest is fragile:
- Python constructors (`__init__`) are often just `self.x = x` — assignment-heavy, not call-heavy. DFS dead-ends there.
- Factory methods like `from_target` call deeper, but miss sibling methods that aren't in its call chain.
- The sweep phase (Phase 2) catches uncrawled records, but sweep doesn't do DFS tracing of internal calls — it just extracts each record in isolation. So methods discovered via sweep lose their call-graph context.

Expanding a class entry point to ALL its methods gives each method DFS priority, which means their internal calls are traced properly.

**Implementation approach**:

The orchestrator's entry point loop (`crawl_orchestrator.py:345-352`) currently resolves each name to a single UUID. For class names, it should resolve to multiple UUIDs:

```python
# In CrawlOrchestrator.run(), Phase 1:
for ep_name in self.entry_points:
    if self._shutdown_requested:
        break

    # Try direct function_name match (single UUID)
    uuid = self._resolve_uuid_by_name(ep_name)
    if uuid is not None:
        await self._dfs_extract(uuid)
        continue

    # Try class_name match (multiple UUIDs — all methods of the class)
    class_uuids = self._resolve_class_methods(ep_name)
    if class_uuids:
        for uuid in class_uuids:
            if self._shutdown_requested:
                break
            await self._dfs_extract(uuid)
        continue

    # __main__ → main fallback
    if ep_name == "__main__":
        uuid = self._resolve_uuid_by_name("main")
        if uuid is not None:
            await self._dfs_extract(uuid)
            continue

    logger.warning("Entry point not found in store: %s", ep_name)

def _resolve_class_methods(self, class_name: str) -> list[str]:
    """Return UUIDs of all methods belonging to a class."""
    all_records = self.store.get_all_records()
    return [rec.uuid for rec in all_records if rec.class_name == class_name]
```

**Why this is better than single-method resolution**:
- `ProjectContext` has 5 methods (`from_target`, `external`, `installed`, `self_hosting`, `is_self_hosting`). Each gets DFS-traced individually.
- `RegistryDag` has 20+ methods. All get DFS priority.
- No guessing which method is the "best" entry — they all are.
- The file_path from EntryPoint should also be propagated for disambiguation (multiple `main` functions exist across files).

### Fix 2: `__main__` → `main` Mapping

**Proposed**: Not explicitly mentioned but needed.

**Assessment**: 🟡 **Needed as a separate fallback**.

Class name search won't help for `__main__` because it's not a class. Options:
1. Map `__main__` → `main` as a name alias
2. Look for `main` in the same package directory
3. Both

Option 1 is simplest and handles the common case.

### Fix 3: File Path Propagation + `build/lib/` Exclusion

**Assessment**: 🟡 **Important for correctness**.

Currently `cli.py:1053` discards file_path. There are duplicate entry points (e.g., `main` appears 6 times across different files, including `build/lib/`). Passing `(name, file_path)` tuples would allow scoped resolution.

**`build/lib/` exclusion** — **Decision: Yes, exclude.**

The `build/lib/` directory is a setuptools artifact — a stale copy of source files. Scanning it doubles every entry point and every record. Currently the entry_points table has 30 entries: 15 real + 15 `build/lib/` duplicates. This means:
- Every class entry point resolves to methods from BOTH the real source AND the build copy
- DFS wastes time extracting duplicate records
- The build copy may be stale (different code than the live source)

The fix: add `build` to the exclude list in `entry_points.py`'s discovery functions. The scanners (`scanner_python.py`, etc.) already have `"build"` in `DEFAULT_EXCLUDES` — the entry point discoverers should match:

```python
# In entry_points.py, each discovery function already checks:
if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
    continue
# Should also exclude build artifacts:
if any(part in ("build", "dist", ".eggs") for part in py_file.parts):
    continue
```

### Fix 4: Proper Function Body Extraction (replaces "prompt hardening")

**Proposed (original)**: Truncate large bodies, stronger JSON-only instruction.

**Revised assessment**: 🔴 **The root fix is proper body extraction, not truncation or prompt changes.**

The original "Fix 4" misdiagnosed the problem as large functions. The real problem is `_read_function_body` doesn't detect function boundaries. The fix is to extract the **actual function body** — the same way a human reads code.

#### Approach: AST-Based Body Extraction

Use Python's `ast` module to get exact function boundaries:

```python
import ast

def _read_function_body(file_path, function_name, line_number, project_root=None):
    # ... read file text ...

    # Parse AST to find exact function boundaries
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fall back to indent-based extraction for files with syntax errors
        return _read_function_body_by_indent(lines, line_number)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno == line_number:
                # end_lineno is available in Python 3.8+
                return "\n".join(lines[node.lineno - 1 : node.end_lineno])

    # Fallback: indent-based extraction
    return _read_function_body_by_indent(lines, line_number)
```

**Why AST, not regex/indent-heuristic as primary**:
- The `ast` module IS how Python itself understands scope — it's the programmatic equivalent of a human reading indentation structure
- Handles edge cases correctly: multi-line strings, continuation lines, nested functions, decorators
- `end_lineno` is exact and reliable (Python 3.8+, which CW9 requires)
- The scanner (`scanner_python.py`) already operates on the same principle (indent tracking for class scope) — AST is the cleaner version of the same idea

**Indent-based fallback** for non-Python files or syntax errors:

```python
def _read_function_body_by_indent(lines, start_line):
    """Walk indentation like a human reading code."""
    start = start_line - 1
    if start >= len(lines):
        return ""

    def_indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1

    while end < len(lines):
        line = lines[end]
        if line.strip():  # non-blank
            indent = len(line) - len(line.lstrip())
            if indent <= def_indent:
                break
        end += 1

    return "\n".join(lines[start:end])
```

#### Why This Fixes the LLM Issue Without Prompt Changes

| Function | Before (lines to EOF) | After (AST body) | LLM sees |
|---|---|---|---|
| `_get_engine_root` | 1760 lines | 5 lines | Just the function |
| `cmd_init` | 1724 lines | 79 lines | Just the function |
| `cmd_crawl` | 760 lines | 165 lines | Just the function |

When the LLM receives only the actual function body, it has clear context for extraction. The "Let me read the actual file..." behavior disappears because there's nothing ambiguous to read — the function IS the input.

#### Multi-Language Body Extraction: One Principle, Language-Appropriate Implementations

Indentation-based scope detection is Python-specific. The other four supported languages use braces for scope. But the underlying principle is the same: **a human reading code identifies the scope boundary native to that language and stops there.**

| Language | Scope Marker | How a Human Reads | Programmatic Equivalent |
|---|---|---|---|
| Python | Indentation | "Read indented block, stop at dedent" | `ast.parse()` → `end_lineno` |
| Go | `{ }` | "Find opening brace, match closing brace" | Brace-depth counter |
| Rust | `{ }` | Same | Same |
| JavaScript | `{ }` | Same (+ handle arrow fns `=>`) | Same (+ arrow fn detection) |
| TypeScript | `{ }` | Same | Same (reuses JS scanner) |

#### Current State of Each Scanner

All five scanners already track scope to some degree — they must, to understand class/receiver context. But **none record where functions end**:

**Python** (`scanner_python.py:112-207`):
- Tracks `class_stack` with indent levels for class context
- Records `line_number` on Skeleton but not end line
- Does NOT use `ast` — does its own line-by-line indent tracking
- Could use `ast.parse()` to get exact `end_lineno` (Python 3.8+ guarantees it)

**Go** (`scanner_go.py:134-246`):
- Already tracks `interface_depth` via brace counting (lines 160-172)
- Already does brace-depth counting for parameter gathering
- Records `line_number` but not end line
- The brace-depth mechanism for finding function end is a natural extension of existing code

**Rust** (`scanner_rust.py`):
- Scanner header says: "Line-by-line text scanning with brace-depth counting"
- Already tracks `impl` block depth
- Same pattern: records start, not end

**JavaScript** (`scanner_javascript.py:185-250`):
- Already tracks `brace_depth` and `class_stack` with brace depth at class open
- Already updates brace_depth across scanned lines
- Must also handle arrow functions: `const fn = (x) => { ... }` and expression arrows `const fn = (x) => x + 1`

**TypeScript** (`scanner_typescript.py`):
- Reuses the JavaScript scanner's approach
- Same brace-depth considerations apply

#### Brace-Depth Body Extraction for Go/Rust/JS/TS

The algorithm is the same for all brace-scoped languages. A human reading code skips over comments and string literals when tracking brace depth — the algorithm must do the same for line comments (`//`), multi-line block comments (`/* ... */`), and string literals.

```python
def _read_function_body_by_braces(lines, start_line):
    """Walk brace depth like a human reading Go/Rust/JS/TS code.

    Skips braces inside:
    - String literals ("...", '...', `...`)
    - Line comments (// ...)
    - Block comments (/* ... */)
    - Template literal interpolations (`${...}`) — tracked separately from scope braces
    """
    start = start_line - 1
    if start >= len(lines):
        return ""

    depth = 0
    found_open = False
    in_string = False
    string_char = None
    in_block_comment = False
    in_template_literal = False
    template_brace_depth = 0  # tracks ${...} nesting inside template literals
    end = start

    for idx in range(start, len(lines)):
        line = lines[idx]
        i = 0
        while i < len(line):
            ch = line[i]

            # ── Block comment state ──────────────────────────
            if in_block_comment:
                if ch == '*' and i + 1 < len(line) and line[i + 1] == '/':
                    in_block_comment = False
                    i += 2
                else:
                    i += 1
                continue

            # ── String literal state ─────────────────────────
            if in_string:
                if ch == '\\':
                    i += 2  # skip escaped char
                    continue
                if in_template_literal and ch == '$' and i + 1 < len(line) and line[i + 1] == '{':
                    # Template interpolation: `text ${expr} text`
                    # The braces inside ${} are NOT scope braces
                    template_brace_depth += 1
                    i += 2
                    continue
                if in_template_literal and template_brace_depth > 0:
                    if ch == '{':
                        template_brace_depth += 1
                    elif ch == '}':
                        template_brace_depth -= 1
                    i += 1
                    continue
                if ch == string_char:
                    in_string = False
                    in_template_literal = False
                i += 1
                continue

            # ── Normal code state ────────────────────────────

            # Block comment start: /*
            if ch == '/' and i + 1 < len(line) and line[i + 1] == '*':
                in_block_comment = True
                i += 2
                continue

            # Line comment: // (skip rest of line)
            if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break

            # String literal start
            if ch in ('"', "'", '`'):
                in_string = True
                string_char = ch
                in_template_literal = (ch == '`')
                template_brace_depth = 0
                i += 1
                continue

            # Scope braces
            if ch == '{':
                depth += 1
                found_open = True
            elif ch == '}':
                depth -= 1
                if found_open and depth == 0:
                    return "\n".join(lines[start : idx + 1])

            i += 1
        end = idx

    # Never found matching close — return what we have
    return "\n".join(lines[start : end + 1])
```

**What this handles** (the same things a human skips when tracking scope):

| Construct | Example | Handling |
|---|---|---|
| Line comments | `// { not a brace }` | `break` — skip rest of line |
| Block comments | `/* { spans \n multiple } lines */` | `in_block_comment` state machine |
| Double-quoted strings | `"{ not a brace }"` | `in_string` state machine |
| Single-quoted strings | `'{'` (char literal in Go/Rust) | Same |
| Template literals | `` `text ${expr} text` `` | `in_template_literal` flag |
| Template interpolation | `` `${obj.method({key: val})}` `` | `template_brace_depth` counter |
| Escaped chars in strings | `"\""`, `"\{"` | `\\` → skip next char |
| Multi-line signatures | `func foo(\n  arg int,\n) {` | `found_open` waits for first `{` |
| Nested blocks | `if { for { } }` | depth tracking naturally handles |

#### JS/TS Arrow Functions Without Braces

**Decision**: Read to `;` combined with scanning for the next `const`/`let`/`function`/`class` declaration.

Arrow functions come in two forms:
```javascript
// Braced body — handled by brace-depth counter above
const add = (a, b) => { return a + b; };

// Expression body — NO braces to track
const add = (a, b) => a + b;
const getUser = (id) => fetch(`/api/users/${id}`).then(r => r.json());
```

For expression-body arrows, the function body ends at whichever comes first:
1. A `;` at the same or lower nesting depth (the statement terminator)
2. A line starting with a new declaration keyword (`const`, `let`, `var`, `function`, `class`, `export`, `module`)

This mirrors how a human reads: "the arrow function's body is the expression, which ends at the semicolon or when I see the next top-level declaration."

```python
_DECL_KEYWORDS = {'const', 'let', 'var', 'function', 'class', 'export', 'module', 'type', 'interface'}

def _read_arrow_expression_body(lines, start_line):
    """Read an arrow function with expression body (no braces)."""
    start = start_line - 1
    if start >= len(lines):
        return ""

    for idx in range(start, len(lines)):
        line = lines[idx]
        stripped = line.strip()

        # Check for semicolon (end of expression statement)
        if ';' in line and idx > start:
            return "\n".join(lines[start : idx + 1])

        # Check for next declaration (only on subsequent lines)
        if idx > start and stripped:
            first_word = stripped.split()[0].rstrip(':')
            if first_word in _DECL_KEYWORDS:
                return "\n".join(lines[start : idx])

    return "\n".join(lines[start:])
```

The scanner must detect which form an arrow function uses (presence of `{` after `=>`) and dispatch to the right body extractor.

#### Design Decision: Record `end_line_number` at Ingest Time (Option B — Confirmed)

**Decision**: Option B — record `end_line_number` in each scanner at ingest time.

**What this means**:

1. **`Skeleton` dataclass** (`crawl_types.py:77`): Add `end_line_number: int | None = None`
2. **Each scanner**: Record the end line during its existing scope-tracking traversal
   - Python scanner: use `ast.parse()` to get `FunctionDef.end_lineno`
   - Go/Rust/JS/TS scanners: use brace-depth counter (already present for other purposes) to find the closing `}`
3. **`skeleton_json`**: New field serialized into the JSON blob stored in `records`
4. **`_read_function_body`**: Becomes a simple slice: `lines[start:end]`

**Why Option B over Option A** (re-parse at crawl time):
- **Parse once, use many**: Each scanner already walks the code during ingest. Recording the end line is one extra assignment — zero additional parsing cost.
- **No runtime language detection**: `_read_function_body` doesn't need to figure out whether it's looking at Python or Go. It just reads `skeleton.end_line_number`.
- **Debuggable**: The end line is visible in the DB. You can query `SELECT function_name, line_number, end_line_number FROM records` to verify correctness.
- **Consistent with existing design**: Skeletons already record everything the crawl needs to know about a function. The end line is a natural addition.

**Migration path**:
- Add the field with `None` default — existing records continue to work
- `_read_function_body` checks: if `end_line_number` is set, slice; otherwise fall back to scope-detection (for records ingested before the migration)
- Re-running `cw9 ingest` populates the new field for all records

---

## 📋 Code References

- `python/registry/crawl_orchestrator.py:35-71` — `_read_function_body` (**the primary bug for Issue 2**)
- `python/registry/crawl_orchestrator.py:222-237` — `_resolve_uuid_by_name` (the bug for Issue 1)
- `python/registry/crawl_orchestrator.py:129-134` — Where `_read_function_body` is called in `extract_one`
- `python/registry/crawl_orchestrator.py:345-352` — Entry point resolution loop (logs the warning)
- `python/registry/scanner_python.py:112-207` — `scan_file` (indent-tracking scanner, records `line_number` but not end line)
- `python/registry/scanner_go.py:134-246` — `scan_file` (brace-depth for interfaces, records start not end)
- `python/registry/scanner_rust.py` — `scan_file` (brace-depth for impl blocks, records start not end)
- `python/registry/scanner_javascript.py:185-250` — `scan_file` (brace-depth + class_stack, records start not end)
- `python/registry/crawl_types.py:77-87` — `Skeleton` dataclass (no `end_line_number` field)
- `python/registry/cli.py:1047-1053` — Entry point name extraction (discards file_path)
- `python/registry/cli.py:1239-1258` — `_EXTRACT_SYSTEM_PROMPT` (JSON instruction)
- `python/registry/cli.py:1261-1302` — `_extract_json_object` (parser that throws the error)
- `python/registry/cli.py:1387-1442` — `_build_async_extract_fn` (LLM call with `allowed_tools=[]`)
- `python/registry/entry_points.py:369-393` — `_discover_public_api` (creates class-name entries)
- `python/registry/entry_points.py:340-366` — `_discover_main_functions` (creates `__main__` entries)
- `python/registry/crawl_store.py:608-628` — Entry point storage/retrieval

## 🏗️ Architecture Documentation

### Entry Point Resolution Flow

```
Entry Point Discovery Flow:

  entry_points.py                    crawl_store.py                 crawl_orchestrator.py
  ─────────────                      ──────────────                 ─────────────────────
  discover_entry_points()            insert_entry_point()           _resolve_uuid_by_name()
       │                                  │                              │
       ├─ _discover_public_api()          │                              ├─ searches function_name ✅
       │  returns name="ProjectContext"   │                              └─ ignores class_name  ❌
       │                                  │
       ├─ _discover_main_functions()      │
       │  returns name="__main__"         │
       │                                  │
       └─ (other discoverers)             │
                                          │
  Ingest (separate step):                 │
  ─────────────────────                   │
  Stores methods as records               ▼
  function_name="from_target"         entry_points table:
  class_name="ProjectContext"         function_name="ProjectContext"
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      MISMATCH — no record has this as function_name
```

### Body Extraction Flow (Current — Broken)

```
  extract_one()                         _read_function_body()
  ──────────────                        ─────────────────────
  Gets record from store                Reads file from disk
  record.line_number = 57               lines[56:]  ← from line 57 to EOF
  record.function_name = "cmd_init"
       │                                Returns 1724 lines  ← Should be 79
       ▼                                     │
  Sends to LLM                               ▼
  skeleton + body                       LLM sees cmd_init + cmd_status +
       │                                cmd_extract + ... + main() + all
       ▼                                helper functions = entire file
  LLM confused
  "Let me read the actual file..."      ← Overwhelmed, breaks JSON mode
```

### Body Extraction Flow (Fixed — Option B: end_line_number at Ingest)

```
  INGEST TIME (once)                    CRAWL TIME (per function)
  ──────────────────                    ────────────────────────

  scanner_python.py                     extract_one()
  ─────────────────                     ──────────────
  ast.parse(text)                       Gets record from store
  FunctionDef at line 57                skeleton.line_number = 57
  node.end_lineno = 135                 skeleton.end_line_number = 135
       │                                     │
       ▼                                     ▼
  Skeleton(                             _read_function_body()
    line_number=57,                     ─────────────────────
    end_line_number=135,                lines[56:135]  ← Simple slice
  )                                     Returns 79 lines
       │                                     │
       ▼                                     ▼
  Stored in crawl.db                    Sends to LLM
  skeleton_json includes                skeleton + 79-line body
  end_line_number                            │
                                             ▼
                                        LLM sees ONLY cmd_init
                                        Returns clean JSON
```

```
  For brace-scoped languages:

  scanner_go.py / scanner_rust.py / scanner_javascript.py
  ────────────────────────────────────────────────────────
  Finds func/fn declaration at line 42
  Counts brace depth: { +1, } -1
  Skips braces in strings, // comments, /* */ blocks
  Closing } at depth 0 → line 87
       │
       ▼
  Skeleton(line_number=42, end_line_number=87)
  Stored in crawl.db → used at crawl time as simple slice
```

## 📚 Historical Context

- `thoughts/shared/research/2026-03-19-concurrent-crawl-extraction.md` — Recent research on crawl concurrency (related but distinct from these bugs)

## ✅ Resolved Decisions

All five open questions have been answered and incorporated into the fix designs above.

| # | Question | Decision | Where Incorporated |
|---|---|---|---|
| 1 | Class entry points → `__init__` or any method? | **All methods.** Expand class name to every method of the class, giving each DFS priority. Single-method resolution is fragile — constructors are often assignment-only dead-ends. | Fix 1 |
| 2 | Exclude `build/lib/` duplicates? | **Yes.** Build artifacts are stale copies. Add `build`, `dist`, `.eggs` to entry point discovery excludes (scanners already exclude them). | Fix 3 |
| 3 | Option A (crawl-time) or Option B (ingest-time) for `end_line_number`? | **Option B.** Record `end_line_number` in Skeleton at ingest. Parse once, use at crawl. Degrades gracefully for old records (fallback to scope detection). | Fix 4 |
| 4 | JS/TS expression-body arrow function end detection? | **Read to `;` combined with next declaration keyword** (`const`/`let`/`var`/`function`/`class`/`export`). Whichever comes first. | Fix 4 (brace-depth section) |
| 5 | Handle multi-line `/* ... */` block comments in brace counter? | **Yes, of course.** Block comments are a normal case. Added `in_block_comment` state machine to the brace-depth algorithm. Also handles template literal `${}` interpolation. | Fix 4 (brace-depth section) |

## ❓ Remaining Open Questions

1. Should the `Skeleton.to_dict()` / `from_dict()` serialization include `end_line_number` in `skeleton_json`, or should it be a separate column on the `records` table? (Separate column is queryable; embedded in JSON is simpler migration.)
2. For Rust raw strings (`r#"..."#`), should the string-literal tracker handle the `#` delimiters? Edge case — only matters if a raw string contains unbalanced braces.
