---
date: 2026-03-23T00:00:00Z
researcher: DustyForge
topic: "Multi-Language Entry Point Discovery — CW9 Review"
tags: [review, entry-points, multi-language, traditional-implementation]
status: complete
reviewed_plan: thoughts/searchable/shared/plans/2026-03-20-multi-language-entry-point-discovery.md
---

# CW9 Plan Review: Multi-Language Entry Point Discovery

## Review Summary

| Check | Status | Issues |
|-------|--------|--------|
| Pipeline applicability | N/A | Plan explicitly opts out of CW9 pipeline (traditional impl) |
| Artifact existence | N/A | No GWT IDs or TLA+ artifacts referenced |
| Status consistency | N/A | No pipeline statuses to check |
| UUID validity | N/A | No crawl.db UUIDs referenced |
| Context file quality | N/A | No CW9 context files referenced |
| Bridge artifact match | N/A | No bridge artifacts referenced |
| Test-to-verifier mapping | N/A | No formal verifiers |
| Simulation trace coverage | N/A | No simulation traces |
| TLA+ invariant coverage | N/A | No TLA+ specs |
| Code accuracy | **FAIL** | 3 issues |
| Type/import accuracy | **PASS** | 0 issues |
| Test helper accuracy | **FAIL** | 1 issue |
| Line number accuracy | **FAIL** | 2 critical mismatches |

## Pipeline Opt-Out Assessment

The plan explicitly states in "What We're NOT Doing":

> Registering this in the TLA+ pipeline (`_self_describe`) | Traditional implementation — this is regex pattern matching, not graph operations

Per CLAUDE.md, the pipeline may be skipped for work that doesn't change DAG behavior or add new modules to `python/registry/`. However, this plan **adds significant new code to `python/registry/entry_points.py`** — approximately 10 new functions, 6 compiled regexes, and new behavioral paths. The justification ("regex pattern matching, not graph operations") is debatable since the plan changes `discover_entry_points()` dispatch logic, which directly affects crawl ordering.

**Verdict**: The pipeline opt-out is borderline acceptable. The new code is deterministic pattern matching (no LLM, no DAG mutations), so it fits the "mechanical" exception. But it's a judgment call — more functions are being added to a registry module than most pipeline-skipped changes.

## Code Accuracy Analysis

### Line Number Mismatches (CRITICAL)

| Plan Claims | Actual | Impact |
|---|---|---|
| `skeletons` computed at `cli.py:847` | Computed at `cli.py:830` inside `_ingest_scan()` | Plan references wrong line; implementer will look at wrong location |
| `discover_entry_points` called at `cli.py:861` | Called at `cli.py:840` inside `_ingest_scan()` | Same — 21-line offset throughout |

The plan also says `cmd_ingest` owns these lines directly, but they're actually in the helper function `_ingest_scan()` (line 823). The edit is still correct — `skeletons` IS in scope at line 840 — but the plan's narrative ("The skeletons variable is already in scope at line 847") points to a blank line.

### Function Signature Mismatch

The plan's proposed new signature (Phase 1) restructures the Python dispatch logic:

```python
# Plan proposes:
if lang == "go": ...
elif lang == "rust": ...
elif lang in ("javascript", "typescript"): ...
# Python: existing behavior
entry_points: list[EntryPoint] = []
...
```

But the actual current code (lines 156-177) has the gate BEFORE `codebase_type` auto-detection:

```python
# Actual current code:
if lang and lang != "python":
    return []                         # <-- gate
if codebase_type is None:
    codebase_type = detect_codebase_type(root)  # <-- auto-detect
```

The plan's replacement moves `codebase_type` auto-detection to the top (before language dispatch), which is correct. But the plan's code passes `lang` to `detect_codebase_type()`:

```python
codebase_type = detect_codebase_type(root, lang=lang)
```

The actual `detect_codebase_type` signature (line 15) is:

```python
def detect_codebase_type(root: Path, *, lang: str | None = None) -> str | None:
```

This IS compatible — `lang` is a keyword-only parameter. No issue here.

### Import Accuracy

The plan proposes adding `Skeleton` to the import:

```python
from registry.crawl_types import EntryPoint, EntryType, Skeleton
```

Verified: `Skeleton` IS defined in `crawl_types.py` at line 76. Import is correct.

However, `Skeleton` is used only for type hints in the plan's code — the actual function signatures use `list` (bare), not `list[Skeleton]`. The import is needed but the type annotations are loose.

## Test Helper Accuracy

### `_skel()` Helper Issue

The plan's test helper:

```python
def _skel(file_path, function_name, *, visibility="public", class_name=None, **kw):
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
```

Actual `Skeleton` required fields: `function_name`, `file_path`, `line_number`. All others have defaults.

The helper passes `params=[]`, `return_type=None`, `file_hash="abc123"` explicitly, but these already have defaults (`field(default_factory=list)`, `None`, `""`). This is fine but redundant.

**Issue**: The helper imports `SkeletonParam` but never uses it. The import line in the test file includes `SkeletonParam`:

```python
from registry.crawl_types import EntryType, Skeleton, SkeletonParam
```

This is a dead import that will trigger linting warnings.

## Logical Analysis

### Correctness of Go/Rust Discoverers

The skeleton-based discovery logic is sound:
- `main` function with `class_name is None` → `MAIN` entry point (correct for both Go and Rust)
- `visibility == "public"` + `class_name is None` + `library` codebase type → `PUBLIC_API` (correct)
- Framework regex patterns are reasonable for Gin/Echo/Chi, Cobra, Actix/Axum, Clap

**Potential issue**: Go `main()` uses `continue` after adding the entry point, which means a function named `main` in package `main` that is also public won't be double-counted. Good.

### Correctness of JS/TS Discoverer

The fallback logic at the end of `_discover_entry_points_js` is interesting:

```python
if not entry_points:
    for skel in skeletons:
        if skel.visibility == "public" and skel.class_name is None:
            _add(...)
```

This means if NO entry points were found (no manifest, no routes, no CLI commands, AND the codebase isn't a `library`), it falls back to treating all public exports as entry points. This is reasonable but could be noisy for large codebases.

### Regex Concerns

1. `_GO_COBRA_RE` uses `re.DOTALL` with `[^}]*` which could match across multiple struct definitions if `}` appears in a string literal. Low risk for real Go code.

2. `_JS_COMMANDER_RE` and `_JS_YARGS_RE` are identical patterns with different names. The comment says "Same pattern works for yargs" — should just be one constant.

3. `_RUST_ROUTE_ATTR_RE` doesn't handle multi-line attributes or additional attribute parameters like `#[get("/path", guard = "auth")]`. Low risk.

### Test Coverage Assessment

Tests cover:
- Go: main, method-named-main exclusion, public API, method exclusion, Gin routes, HandleFunc, Cobra
- Rust: main, impl-main exclusion, pub functions, Actix attrs, Axum routes, Clap
- JS: package.json bin (string + dict), main field, Express routes, node_modules exclusion, commander, public API from skeletons
- TS: Express routes, public API, .d.ts exclusion

**Missing test cases**:
1. No test for Go `HandleFunc` with non-GET method (always defaults to "GET" — is this intentional?)
2. No test for empty skeletons + no framework files = empty result for Go/Rust
3. No test for Rust `pending_route` state machine edge case (attribute followed by non-fn line)
4. No test for JS/TS fallback behavior (no entry points found → all public exports)
5. No test for `detect_codebase_type` being called when `codebase_type=None` for new languages
6. No integration test verifying `_ingest_scan` passes skeletons correctly

## Issues

### Critical (must fix before implementation)

1. **Line number drift**: Plan references `cli.py:847` and `cli.py:861` but the actual lines are `830` and `840` respectively, inside `_ingest_scan()` not `cmd_ingest()`. An implementer following the plan will look at wrong lines.
   - Impact: Wasted time, potential wrong edit location
   - Fix: Update plan to reference `_ingest_scan()` at lines 830 and 840

### Warnings (should fix)

1. **Dead import in test file**: `SkeletonParam` imported but never used in `test_entry_points_multi_lang.py`
   - Fix: Remove `SkeletonParam` from import

2. **Duplicate regex constants**: `_JS_COMMANDER_RE` and `_JS_YARGS_RE` are identical
   - Fix: Use single `_JS_CLI_COMMAND_RE` constant

3. **Go HandleFunc always assumes GET**: `_discover_go_routes` sets `method="GET"` for all `HandleFunc`/`Handle` matches. `http.HandleFunc` is method-agnostic (handles all methods).
   - Fix: Use `method="ANY"` or `method=None` for HandleFunc matches

4. **Missing test for fallback behavior**: The JS/TS fallback (all public exports when nothing else found) has no dedicated test
   - Fix: Add test case with non-library codebase type and no framework patterns

### Cosmetic (nice to fix)

1. **Loose type annotations**: All discoverer functions accept `skeletons: list` instead of `skeletons: list[Skeleton]`
   - Fix: Use `list[Skeleton]` for type safety

2. **Plan narrative mentions `cmd_ingest`**: Should say `_ingest_scan` since that's where the edit happens
   - Fix: Update Phase 4 text

## Approval Status

- [x] **Ready for `/cw9_implement`** — all issues resolved in rev 2026-03-23
- [ ] **Needs minor revision**
- [ ] **Needs revision** — ~~line number drift is critical, plus several warnings worth addressing~~ FIXED
- [ ] **Needs re-pipeline** — artifacts missing or stale
