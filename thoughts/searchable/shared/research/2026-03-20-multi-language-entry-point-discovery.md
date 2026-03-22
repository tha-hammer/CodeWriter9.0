---
date: 2026-03-20T14:30:00-05:00
researcher: DustyForge
git_commit: a714079
branch: master
repository: CodeWriter9.0
topic: "Multi-language entry point discovery: current state and per-language analysis"
tags: [research, codebase, entry-points, multi-language, javascript, typescript, go, rust, scanners]
status: complete
last_updated: 2026-03-20
last_updated_by: DustyForge
---

```
┌─────────────────────────────────────────────────────────────────┐
│  Research: Multi-Language Entry Point Discovery                  │
│  Status: ✅ Complete  |  Date: 2026-03-20                       │
└─────────────────────────────────────────────────────────────────┘
```

**Date**: 2026-03-20T14:30:00-05:00
**Researcher**: DustyForge
**Git Commit**: a714079
**Branch**: master
**Repository**: CodeWriter9.0

## Research Question

`discover_entry_points` currently returns `[]` for all non-Python languages (line 156-157 of `entry_points.py`). We need entry point discovery for all detectable languages: JavaScript, TypeScript, Go, and Rust. What exists today, what's missing, and what does each language need?

## 📊 Summary

The system has **two independent subsystems** that both analyze source code but serve different purposes:

| Subsystem | Purpose | Multi-Language? |
|---|---|---|
| **Scanners** (`scanner_*.py`) | Extract every function/method signature → `Skeleton` objects | ✅ All 5 languages |
| **Entry Point Discovery** (`entry_points.py`) | Identify *which* functions are architectural entry points → `EntryPoint` objects | 🔴 Python only |

`detect_codebase_type()` already supports all 5 languages — it correctly classifies JS/TS/Go/Rust projects as `web_app`, `cli`, `event_driven`, or `library`. But `discover_entry_points()` short-circuits at line 156 before using that classification for anything.

The comment at line 154 — *"Non-Python languages return empty for now (scanners find all symbols)"* — explains the current design intent: scanners already find ALL symbols, so crawl falls through to the "all SKELETON_ONLY records" fallback (`cli.py:1058-1060`). Entry points are an optimization that prioritizes important functions for DFS crawl order, not a hard requirement.

---

## 🔍 Detailed Findings

### The Gate: `entry_points.py:148-177`

```python
def discover_entry_points(
    root: Path, codebase_type: str | None = None, *, lang: str | None = None,
) -> list[EntryPoint]:
    if lang and lang != "python":        # ← THE GATE (line 156)
        return []                         # ← Always empty for non-Python
    if codebase_type is None:
        codebase_type = detect_codebase_type(root)

    entry_points: list[EntryPoint] = []
    if codebase_type == "web_app":
        entry_points.extend(_discover_web_routes(root))      # Python regex: @app.get, @app.route
    elif codebase_type == "cli":
        entry_points.extend(_discover_cli_commands(root))     # Python regex: @click.command
    elif codebase_type == "event_driven":
        entry_points.extend(_discover_event_handlers(root))   # Python regex: @celery_app.task
    entry_points.extend(_discover_main_functions(root))        # Python regex: def main(), __main__.py
    if codebase_type == "library" or not entry_points:
        entry_points.extend(_discover_public_api(root))        # Python regex: __all__ = [...]
    return entry_points
```

### How the Gate Is Reached: `cli.py:836-861`

```python
lang = args.lang or _detect_language(ingest_path)             # line 836
codebase_type = detect_codebase_type(ingest_path, lang=lang)  # line 837
scanner = _get_scanner(lang)                                   # line 840
skeletons = scanner(ingest_path)                               # line 847
# ... normalize paths ...
entry_points = discover_entry_points(ingest_path, codebase_type, lang=lang)  # line 861
```

When `lang="javascript"`, line 861 calls `discover_entry_points(..., lang="javascript")`, which hits the gate at line 156 and returns `[]`. The `entry_points` table stays empty.

### Fallback Behavior When No Entry Points Exist

`cli.py:1048-1060` shows what `cmd_crawl` does when the table is empty:

```python
if not entry_names:
    stored_eps = store.get_entry_points() if hasattr(store, "get_entry_points") else []
    entry_names = [ep.function_name for ep in stored_eps]

if not entry_names:
    all_recs = store.get_all_records()
    entry_names = [r.function_name for r in all_recs if r.do_description == "SKELETON_ONLY"]
```

When `entry_points` is empty, crawl falls through to **all SKELETON_ONLY records** — every function in the project becomes an entry point. This means crawl works for non-Python projects, but:
- No DFS priority ordering (random function order instead of routes-first or main-first)
- No architectural classification (every function is treated equally)
- Potentially crawls internal helpers before public API surface

---

### What Each Language Needs: Per-Language Analysis

### 🟦 JavaScript (`scanner_javascript.py`)

**Scanner exists**: ✅ Handles `*.js`, `*.jsx` (skips `*.min.js`)
**Codebase type detection exists**: ✅ `_detect_codebase_type_js` in `entry_points.py:68-102`

**Entry point patterns needed by codebase type:**

| Codebase Type | Pattern | Example | EntryType |
|---|---|---|---|
| `web_app` (Express) | `app.get("/path", handler)` / `router.post("/path", handler)` | `app.get("/users", getUsers)` | `HTTP_ROUTE` |
| `web_app` (Next.js) | `pages/*.js` or `app/*/page.js` file convention | `pages/api/users.js` → default export | `HTTP_ROUTE` |
| `web_app` (React) | `src/index.js` or `src/App.js` root component | `ReactDOM.render(<App />)` | `MAIN` |
| `cli` | `bin` field in `package.json` | `"bin": {"mycli": "./cli.js"}` | `CLI_COMMAND` |
| `cli` (commander) | `.command("name")` chains | `program.command("build")` | `CLI_COMMAND` |
| `event_driven` | `queue.process(handler)` / `consumer.on("message", handler)` | Bull/Kafka consumers | `EVENT_HANDLER` |
| `library` | `main`/`exports` in `package.json` | `"main": "index.js"` → exported names | `PUBLIC_API` |
| any | `module.exports` / `exports.name` | Already detected by scanner | `PUBLIC_API` |

**Scanner already detects** (`scanner_javascript.py:75-92`):
- `module.exports = function(...)` → `Skeleton(function_name="default_export")`
- `exports.name = function(...)` → `Skeleton(function_name=name)`
- All function/class declarations with `export` keyword

**What the scanner does NOT detect** (entry-point-specific):
- Express route registrations (`app.get("/path", handler)`)
- Next.js page file conventions
- `package.json` `bin`/`main`/`exports` fields
- Commander/yargs command registrations

---

### 🟦 TypeScript (`scanner_typescript.py`)

**Scanner exists**: ✅ Handles `*.ts`, `*.tsx` (skips `*.d.ts`)
**Codebase type detection exists**: ✅ Shares `_detect_codebase_type_js` (line 20-21)

**Same patterns as JavaScript, plus:**

| Pattern | Example | EntryType |
|---|---|---|
| NestJS decorators | `@Controller("/users")`, `@Get()`, `@Post()` | `HTTP_ROUTE` |
| NestJS injectable | `@Injectable()` class | `PUBLIC_API` |
| Exported interfaces/types | `export interface User { ... }` | `PUBLIC_API` |

**`lang_typescript.py:120-151` already has partial API discovery:**
- `TypeScriptProfile.discover_api_context()` scans for `export function`, `export class`, `export interface`, `export type`, `export const`, `export enum`
- But this returns a string context for LLM prompts, not `EntryPoint` objects
- Could be adapted or serve as a pattern reference

---

### 🟩 Go (`scanner_go.py`)

**Scanner exists**: ✅ Handles `*.go` (skips `*_test.go`)
**Codebase type detection exists**: ✅ `_detect_codebase_type_go` in `entry_points.py:105-123`

**Entry point patterns needed by codebase type:**

| Codebase Type | Pattern | Example | EntryType |
|---|---|---|---|
| `cli` | `func main()` in `package main` | `cmd/server/main.go` | `MAIN` |
| `cli` | Cobra commands | `cmd.AddCommand(serveCmd)` | `CLI_COMMAND` |
| `web_app` (Gin) | `r.GET("/path", handler)` | `r.GET("/users", getUsers)` | `HTTP_ROUTE` |
| `web_app` (Echo) | `e.GET("/path", handler)` | Same pattern | `HTTP_ROUTE` |
| `web_app` (Chi) | `r.Get("/path", handler)` | Same pattern | `HTTP_ROUTE` |
| `library` | Exported functions (capitalized) | `func NewService()` | `PUBLIC_API` |

**Go-specific considerations:**
- Visibility is built into the language: capitalized = exported = public API. The scanner already detects this (`scanner_go.py:228`).
- `func main()` in `package main` is THE entry point — detection is trivial (check for `package main` + `func main()`)
- The `cmd/` directory convention is already checked by `_detect_codebase_type_go` (line 110)
- For `library` type: all exported functions (already marked `visibility="public"` by scanner) are effectively the public API

---

### 🟧 Rust (`scanner_rust.py`)

**Scanner exists**: ✅ Handles `*.rs` (does NOT skip test files — intentional)
**Codebase type detection exists**: ✅ `_detect_codebase_type_rust` in `entry_points.py:126-145`

**Entry point patterns needed by codebase type:**

| Codebase Type | Pattern | Example | EntryType |
|---|---|---|---|
| `cli` | `fn main()` | `src/main.rs` | `MAIN` |
| `cli` (Clap) | `#[derive(Parser)]` struct | `#[command(name = "myapp")]` | `CLI_COMMAND` |
| `web_app` (Axum) | `.route("/path", get(handler))` | Router builder chains | `HTTP_ROUTE` |
| `web_app` (Actix) | `#[get("/path")]` / `web::resource("/path")` | Attribute macros | `HTTP_ROUTE` |
| `web_app` (Rocket) | `#[get("/path")]` | Attribute macros | `HTTP_ROUTE` |
| `library` | `pub fn` in `src/lib.rs` | Top-level public functions | `PUBLIC_API` |

**Rust-specific considerations:**
- `fn main()` in `src/main.rs` is THE binary entry point — trivial to detect
- `src/lib.rs` is THE library entry point — its `pub` items are the public API
- `[[bin]]` targets in `Cargo.toml` define additional entry points (already checked by `_detect_codebase_type_rust`)
- The scanner already tracks `pub` vs `pub(crate)` visibility (`scanner_rust.py:297-300`)
- Attribute macros (`#[get("/")]`, `#[tokio::main]`) are tracked for brace depth but not semantically interpreted

---

### Cross-Language Patterns: What's Common

Several entry point patterns are **structurally identical** across languages:

| Pattern | Python | JS/TS | Go | Rust |
|---|---|---|---|---|
| "Main function" | `def main()` + `__main__.py` | `"main"` in package.json | `func main()` in `package main` | `fn main()` in `main.rs` |
| "Route decorator/registration" | `@app.get("/path")` | `app.get("/path", h)` | `r.GET("/path", h)` | `#[get("/path")]` |
| "CLI command" | `@click.command` | `.command("name")` | `cmd.AddCommand()` | `#[derive(Parser)]` |
| "Public API surface" | `__all__` in `__init__.py` | `exports` in package.json | Capitalized names | `pub` in `lib.rs` |

---

## 📋 Code References

| File | Lines | What's There |
|---|---|---|
| `python/registry/entry_points.py` | 15-26 | `detect_codebase_type` — dispatches to 4 language-specific detectors |
| `python/registry/entry_points.py` | 68-102 | `_detect_codebase_type_js` — JS/TS framework detection |
| `python/registry/entry_points.py` | 105-123 | `_detect_codebase_type_go` — Go framework detection |
| `python/registry/entry_points.py` | 126-145 | `_detect_codebase_type_rust` — Rust framework detection |
| `python/registry/entry_points.py` | 148-177 | `discover_entry_points` — the gate + Python-only discovery |
| `python/registry/entry_points.py` | 196-251 | `_discover_web_routes` — Python HTTP route patterns |
| `python/registry/entry_points.py` | 259-296 | `_discover_cli_commands` — Python CLI patterns |
| `python/registry/entry_points.py` | 302-337 | `_discover_event_handlers` — Python event patterns |
| `python/registry/entry_points.py` | 340-366 | `_discover_main_functions` — Python main() + __main__.py |
| `python/registry/entry_points.py` | 369-393 | `_discover_public_api` — Python __all__ exports |
| `python/registry/cli.py` | 760-793 | `_detect_language` — 5-language manifest + extension detection |
| `python/registry/cli.py` | 796-808 | `_get_scanner` — scanner dispatch by language |
| `python/registry/cli.py` | 836-865 | `cmd_ingest` — detection → scan → entry point flow |
| `python/registry/cli.py` | 1048-1060 | `cmd_crawl` — entry point fallback to all SKELETON_ONLY records |
| `python/registry/scanner_javascript.py` | 30-92 | JS regex patterns (6 patterns: func, arrow, class, method, module.exports, exports.name) |
| `python/registry/scanner_typescript.py` | 29-70 | TS regex patterns (4 patterns + visibility + return type parsing) |
| `python/registry/scanner_go.py` | 26-92 | Go regex patterns (func/method + param parsing) |
| `python/registry/scanner_rust.py` | 30-56 | Rust regex patterns (fn + impl + trait) |
| `python/registry/lang_typescript.py` | 120-151 | `discover_api_context` — partial TS export surface scanner (returns string, not EntryPoints) |
| `python/registry/crawl_types.py` | 58-64 | `EntryType` enum — 6 types: http_route, cli_command, public_api, event_handler, main, test |
| `python/registry/crawl_types.py` | 195-203 | `EntryPoint` dataclass — file_path, function_name, entry_type, route, method |

## 🏗️ Architecture Documentation

### Current Data Flow

```
                    ┌──────────────────────────────────┐
                    │         _detect_language()        │
                    │  manifest probing → extension     │
                    │  counting → returns lang string   │
                    └──────────┬───────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
   ┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
   │ _get_scanner  │  │ detect_codebase │  │ discover_entry   │
   │ (all 5 langs) │  │ _type           │  │ _points          │
   │               │  │ (all 5 langs)   │  │ (PYTHON ONLY)    │
   └──────┬───────┘  └────────┬────────┘  └───────┬──────────┘
          │                   │                    │
          ▼                   │          ┌─────────┴──────────┐
   ┌──────────────┐           │          │ if lang != python: │
   │ list[Skeleton]│          │          │   return []        │
   │ ALL functions │          │          └────────────────────┘
   │ per language  │          │
   └──────────────┘           │
                              ▼
                    ┌──────────────────────┐
                    │ codebase_type string │
                    │ (used by Python      │
                    │  discoverers only)   │
                    └──────────────────────┘
```

### What Each Scanner Already Provides (Skeleton Fields)

| Field | Python | JavaScript | TypeScript | Go | Rust |
|---|---|---|---|---|---|
| `function_name` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `file_path` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `line_number` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `class_name` | ✅ (indent) | ✅ (brace) | ✅ (brace) | ✅ (receiver) | ✅ (impl block) |
| `visibility` | ✅ (`_` prefix) | ✅ (`export`/`#`) | ✅ (keywords) | ✅ (capitalization) | ✅ (`pub`/`pub(crate)`) |
| `is_async` | ✅ | ✅ | ✅ | ❌ (always False) | ✅ |
| `params` | ✅ (typed) | ✅ (names only) | ✅ (typed) | ✅ (typed) | ✅ (typed + self) |
| `return_type` | ✅ | ❌ (always None) | ✅ | ✅ | ✅ |

## 📚 Historical Context

- `thoughts/shared/research/2026-03-20-crawl-entry-point-resolution-failures.md` — Companion research: entry point resolution bugs (class_name mismatch, _read_function_body sending EOF)
- `thoughts/shared/research/2026-03-13-brownfield-code-walker-for-cw9-pipeline.md` — Original brownfield walker research covering the scanner architecture
- `thoughts/shared/plans/2026-03-13-tdd-brownfield-walker-remaining/` — TDD plans for each non-Python scanner (phases 03-06)
- `thoughts/shared/plans/2026-03-10-tdd-multi-language-test-gen.md` — Earlier multi-language test generation plan
- `thoughts/shared/docs/howto-brownfield-code-walker.md` — How-to guide covering `discover_entry_points` and scanning

## 🔗 Related Research

- `thoughts/shared/research/2026-03-20-crawl-entry-point-resolution-failures.md` — Fixes for the Python entry point resolution bugs should be implemented first, as the patterns established there (class→all-methods expansion, `__main__`→`main` mapping, build/lib exclusion, end_line_number) apply to multi-language discovery too.

## ❓ Open Questions

1. **Priority ordering**: Should entry point discovery for each language be implemented all at once, or incrementally by most-requested language first?
2. **Public API for Go/Rust**: Capitalized names (Go) and `pub` items in `lib.rs` (Rust) are already detectable from scanner output. Should `discover_entry_points` filter Skeleton results rather than re-scanning files?
3. **Next.js/Nuxt file conventions**: File-based routing requires understanding directory structure (`pages/`, `app/`) rather than code patterns. Should this be a separate discoverer or integrated into `_discover_web_routes`?
4. **NestJS decorator scanning**: `@Controller`, `@Get()`, `@Post()` are structurally similar to Python's `@app.get()`. Should the TypeScript entry point discoverer share regex infrastructure with Python's?
