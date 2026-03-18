---
title: "Plan Review: TDD Brownfield Walker — Remaining Implementation"
date: 2026-03-14
reviewer: claude-opus
plan: thoughts/searchable/shared/plans/2026-03-13-tdd-brownfield-walker-remaining.md
tags: [review, tdd, brownfield, scanner, rust, javascript, orchestrator, gwt-author]
status: complete
review_type: pre-implementation-review
---

# Plan Review Report: TDD Brownfield Walker — Remaining Implementation

**Scope:** Pre-implementation architectural review of 6-component TDD plan.

**Critical finding:** Components 1–4 are already implemented and passing tests (45/45 pass).
Only Components 5 (Rust scanner) and 6 (JavaScript scanner) remain to be built.

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 3 issues |
| Interfaces | ✅ | 1 minor issue |
| Promises | ✅ | 0 issues |
| Data Models | ✅ | 0 issues |
| APIs | ⚠️ | 1 issue |

---

## Scope Correction: What's Already Done

The plan describes 6 components as "remaining." In reality, 4 are fully implemented:

| # | Component | Status | File Lines | Tests |
|---|-----------|--------|-----------|-------|
| 1 | DFS crawl orchestrator | ✅ DONE | 276 lines | 10 pass |
| 2 | `cw9 gwt-author` command | ✅ DONE | 215 lines | 11 pass |
| 3 | TypeScript skeleton scanner | ✅ DONE | 389 lines | 12 pass |
| 4 | Go skeleton scanner | ✅ DONE | 270 lines | 12 pass |
| 5 | Rust skeleton scanner | ❌ NOT STARTED | — | — |
| 6 | JavaScript skeleton scanner | ❌ NOT STARTED | — | — |

**Recommendation:** Update the plan status to reflect this. Implementation should proceed with only Components 5 and 6.

---

## Contract Review

### Well-Defined:
- ✅ Scanner interface contract (`scan_file(path) -> list[Skeleton]`, `scan_directory(root, excludes) -> list[Skeleton]`) is proven across 3 implementations (Python, TypeScript, Go)
- ✅ `Skeleton` data model has all fields needed by the Rust/JS scanners: `is_self` on `SkeletonParam`, `visibility` and `is_async` on `Skeleton`
- ✅ `CrawlOrchestrator` contract with `extract_fn: Callable[[Skeleton, str], FnRecord]` is implemented and tested
- ✅ `FnRecord.failure_modes: list[str]` exists for the `EXTRACTION_FAILED` stub pattern

### Missing or Unclear:

- ⚠️ **Component 5 (Rust), Behavior 5.5: `is_self` param for `&self`/`&mut self`** — The plan's test asserts `ref_params[0].is_self is True` and `ref_params[0].name == "self"`. This is consistent with `SkeletonParam(is_self=True)` which exists in the data model. However, the plan doesn't specify what `type` should be for self params. Should `&self` have `type="&Self"`? `type="&self"`? `type=""`? The Python scanner sets `type=""` for `self`/`cls`. The plan should specify the convention.

  **Impact:** Inconsistent self-param type strings across language scanners.
  **Recommendation:** Follow Python scanner convention: `type=""` for self params. Add explicit assertion to test 5.5.

- ⚠️ **Component 5 (Rust), Behavior 5.12: `impl Trait for Type` — class_name resolution** — The plan correctly specifies `class_name="UserService"` (the concrete type). But the regex `_IMPL_RE` captures the first `\w+` after `impl`. For `impl fmt::Display for UserService`, the first `\w+` is `fmt` (or `Display` depending on how the path is handled). The plan provides the regex but doesn't resolve how `for` keyword changes the capture target.

  **Impact:** Wrong `class_name` for trait implementations if regex isn't carefully designed.
  **Recommendation:** The `_IMPL_RE` regex needs special handling for the `for` keyword. When `for` is present, capture the type AFTER `for`, not after `impl`. Suggest adding a separate `_IMPL_FOR_RE` or a two-pass approach.

- ⚠️ **Component 6 (JavaScript): No `_ARROW_RE` overlap protection** — The plan defines `_FUNC_RE`, `_ARROW_RE`, `_MODULE_EXPORTS_RE`, `_NAMED_EXPORTS_RE`, and `_METHOD_RE` as separate patterns. A line like `exports.handler = function handler(req) {` could match both `_NAMED_EXPORTS_RE` and `_FUNC_RE`. The plan doesn't specify match priority or how to prevent double-counting.

  **Impact:** Duplicate Skeleton entries for the same function.
  **Recommendation:** Define explicit match priority (e.g., try `_MODULE_EXPORTS_RE` and `_NAMED_EXPORTS_RE` first, skip `_FUNC_RE`/`_ARROW_RE` if they already matched). The TypeScript scanner uses ordered if/elif chains — follow that pattern.

---

## Interface Review

### Well-Defined:
- ✅ `scan_file(path: Path) -> list[Skeleton]` — identical across all scanners
- ✅ `scan_directory(root: Path, excludes: list[str] | None = None) -> list[Skeleton]` — identical
- ✅ Default excludes convention: each scanner defines its own `DEFAULT_EXCLUDES` set
- ✅ File extension filtering: `.rs` for Rust, `.js`/`.jsx` for JavaScript (skip `.min.js`)

### Missing or Unclear:

- ⚠️ **Component 5 (Rust): `scan_directory` test doesn't verify `.rs` extension filtering** — The plan's `TestScanDirectory` tests don't include a case verifying that non-`.rs` files (e.g., `.toml`, `.lock`) are ignored. This is implicit but not tested. Minor — the existing scanners also don't test this explicitly.

---

## Promise Review

### Well-Defined:
- ✅ File hash: SHA-256 hex of file content — consistent with Python/TS/Go scanners
- ✅ Empty file → empty list (tested for both scanners)
- ✅ Deterministic output: same file produces same hash (tested)
- ✅ Rust scanner ingests `#[cfg(test)]` functions (explicit design decision with rationale)
- ✅ JavaScript scanner skips `.min.js` files
- ✅ No cross-scanner dependencies (Rust and JS scanners are fully independent)

---

## Data Model Review

### Well-Defined:
- ✅ All plan test code uses existing `Skeleton` and `SkeletonParam` fields correctly
- ✅ `visibility` values: "public"/"private" — consistent across all scanners
- ✅ `is_async` boolean — used by both Rust (`async fn`) and JS (`async function`)
- ✅ `class_name` semantics: `impl Type` → class_name for Rust, `class Name` → class_name for JS
- ✅ `return_type`: `None` for JS (no annotations), string for Rust
- ✅ Param types: empty string for JS (no types), full type string for Rust

---

## API Review

### Well-Defined:
- ✅ No new CLI commands needed — Components 5 and 6 are library-only (scanners)
- ✅ Import paths: `from registry.scanner_rust import scan_file, scan_directory`
- ✅ No new external dependencies required

### Missing or Unclear:

- ⚠️ **Integration with `cmd_ingest`** — The plan doesn't specify how these new scanners get wired into the `cmd_ingest` flow. Currently `cmd_ingest` (cli.py:760) uses `scanner_python.scan_directory()`. When Rust/JS scanners are added, `cmd_ingest` needs to dispatch to the correct scanner based on file type or codebase type. This wiring is out of scope per the plan, but should be noted as a follow-up.

  **Impact:** Scanners work in isolation but aren't usable via the CLI until wiring is added.
  **Recommendation:** Create a follow-up issue for scanner dispatch in `cmd_ingest`.

---

## Critical Issues (Must Address Before Implementation)

None. The remaining work (Components 5 and 6) is well-specified, follows proven patterns, and all data model fields exist.

## Warnings (Should Address)

1. **Rust `impl for` regex** (Component 5, Behavior 5.12): The `_IMPL_RE` regex as written will capture the wrong type name for `impl Trait for Type` blocks. This needs explicit handling — either a separate regex or post-match `for` keyword detection.

2. **JavaScript match priority** (Component 6): Define explicit match ordering to prevent double-counting when multiple patterns match the same line (e.g., `exports.handler = function handler(...)`).

3. **Rust self-param type convention** (Component 5, Behavior 5.5): Specify what `SkeletonParam.type` should be for `&self`, `&mut self`, `self` params.

## Suggested Plan Amendments

```diff
# In Component 5 (Rust Scanner):

+ Clarify: SkeletonParam.type for self params should be "" (empty string),
+   matching Python scanner convention. &self → SkeletonParam(name="self", type="", is_self=True)

+ Update _IMPL_RE handling: When the word "for" appears between impl and type,
+   capture the type AFTER "for" as class_name, not the trait name before it.
+   Example: "impl Display for UserService" → class_name="UserService"

# In Component 6 (JavaScript Scanner):

+ Add explicit match priority note: Try regex patterns in this order:
+   1. _MODULE_EXPORTS_RE
+   2. _NAMED_EXPORTS_RE
+   3. _CLASS_RE
+   4. _METHOD_RE (only inside class context)
+   5. _ARROW_RE
+   6. _FUNC_RE
+   On first match, skip remaining patterns for that line.

# Plan-level:

+ Update "What's Missing" table: Mark Components 1-4 as DONE
+ Update Implementation Order: Only Components 5 and 6 remain (parallelizable)
+ Update success criteria for Components 1-4: Change [ ] to [x] (already verified)
```

## Approval Status

- [x] **Needs Minor Revision** — Address warnings before proceeding

The plan is fundamentally sound. The 3 warnings are implementation-detail clarifications, not architectural issues. Components 5 and 6 can proceed once the regex/priority concerns are noted by the implementer. The existing 4 components serve as excellent reference implementations.

---

## Review Checklist

### Contracts
- [x] Component boundaries are clearly defined
- [x] Input/output contracts are specified (scan_file/scan_directory)
- [x] Error contracts enumerate all failure modes
- [x] Preconditions and postconditions are documented
- [ ] Self-param type convention not specified for Rust scanner

### Interfaces
- [x] All public methods are defined with signatures
- [x] Naming follows codebase conventions
- [x] Interface matches existing patterns (3 reference scanners)
- [x] Extension points are considered
- [x] Visibility modifiers are appropriate

### Promises
- [x] Behavioral guarantees are documented
- [x] Resource cleanup is specified (no resources to manage)
- [x] Ordering guarantees are documented where needed

### Data Models
- [x] All fields have types
- [x] Required vs optional is clear
- [x] Relationships are documented
- [x] Serialization format is specified (Skeleton dataclass)

### APIs
- [x] All endpoints are defined (no new CLI commands)
- [ ] Scanner dispatch wiring to cmd_ingest not specified (follow-up)
