# Validation Report: `cw9 register` Subcommand TDD Plan

**Plan:** `thoughts/searchable/shared/plans/2026-03-11-tdd-cw9-register-subcommand.md`
**Validator:** DustyForge (Orchestration LLM)
**Date:** 2026-03-11

---

## Implementation Status

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| Phase 1 | Criterion Bindings File | ✅ Fully implemented | 3/3 pass |
| Phase 2 | `--ensure` Flag on `cw9 init` | ✅ Fully implemented | 3/3 pass |
| Phase 3 | `cw9 register` Core Registration | ✅ Fully implemented | 9/9 pass |
| Phase 4 | End-to-End Integration | ✅ Fully implemented | 1/1 pass |

**Total new tests:** 16 (13 in `test_register.py` + 3 in `test_cli.py`)

---

## Automated Verification Results

| Check | Result |
|-------|--------|
| `pytest tests/test_register.py -v` | ✅ 13 passed |
| `pytest tests/test_cli.py::TestInit -v` | ✅ 12 passed (9 existing + 3 new) |
| `pytest -x` (full suite) | ✅ 528 passed, 1 warning |
| No regressions | ✅ Confirmed (was 512, now 528 = +16 new tests) |

The 1 warning is pre-existing (`pytest.mark.slow` unregistered in `test_packaging.py`).

---

## Phase-by-Phase Verification

### Phase 1: Criterion Bindings File ✅

**File created:** `python/registry/bindings.py` (21 lines)

Matches plan exactly:
- `load_bindings(state_root: Path) -> dict[str, str]` — returns `{}` when file missing
- `save_bindings(state_root: Path, bindings: dict[str, str])` — writes JSON with indent=2
- `_BINDINGS_FILE = "criterion_bindings.json"` — correct constant

**Tests verified:** `TestBindings` — 3 tests covering load-missing, round-trip, overwrite.

### Phase 2: `--ensure` Flag ✅

**File modified:** `python/registry/cli.py:63-70`

Implementation matches plan:
- `args.ensure and args.force` → exit 1 with error (line 63-65)
- `args.ensure and state_root.exists()` → return 0 silently (line 69-70)
- `--ensure` argument added to init parser (line 571-572)

**Improvement over plan:** Uses `args.ensure` directly instead of `getattr(args, 'ensure', False)`. Cleaner since the argument is always defined on the init parser.

**Tests verified:** 3 new tests in `TestInit`:
- `test_ensure_is_noop_when_exists` — ✅
- `test_ensure_creates_when_absent` — ✅
- `test_ensure_and_force_conflict` — ✅

### Phase 3: `cw9 register` Core Registration ✅

**File modified:** `python/registry/cli.py:400-506`

Implementation matches plan with one improvement:

- **W1 amendment incorporated:** `requirements[].id` validation added at lines 425-430 (the review finding was addressed)
- Uses `req["id"]` (line 448) instead of plan's `req.get("id", "")` — correct since validation ensures `id` is present
- Stdin parsing, requirement registration, GWT registration, parent_req resolution, bindings save — all match plan
- Argparse wiring at lines 604-606 and dispatch at lines 627-628 — correct

**Tests verified:** 9 tests in `TestRegister`:
- `test_register_requirement` — ✅ (also verifies bindings file — improvement over plan)
- `test_register_gwt` — ✅
- `test_parent_req_wiring` — ✅
- `test_idempotent_reregistration` — ✅ (improved: counts nodes before AND after)
- `test_mixed_fresh_and_idempotent` — ✅
- `test_no_cw9_fails` — ✅
- `test_malformed_json_fails` — ✅
- `test_missing_criterion_id_fails` — ✅
- `test_missing_requirement_id_fails` — ✅ (W1 amendment test added)

### Phase 4: End-to-End Integration ✅

**Test verified:** `TestRegisterE2E::test_full_handoff_with_idempotent_retry` — ✅

Covers: Shamir-style payload with 1 requirement + 2 GWTs (one with parent_req), DAG node verification, DECOMPOSES edge verification, idempotent retry with exact output match, node count stability.

---

## Code Review Findings

### Matches Plan:
- ✅ Bindings module is minimal and separate from DAG
- ✅ `cmd_register` reads JSON stdin, validates, registers, emits JSON stdout
- ✅ Requirements processed before GWTs (correct ordering)
- ✅ Bindings use namespaced keys (`req:` / `gwt:` prefixes)
- ✅ Parent-req resolution: same-payload → DAG nodes → prior bindings → None fallback
- ✅ No `--json` flag on register (JSON-only behavior)
- ✅ No `extract` step in the flow
- ✅ `--ensure` and `--force` mutually exclusive

### Improvements Over Plan:
- `args.ensure` used directly instead of `getattr()` (cleaner)
- `test_register_requirement` also verifies bindings file was written (defense-in-depth)
- `test_idempotent_reregistration` counts GWT nodes before AND after (not just after)
- W1 amendment (requirement ID validation) was incorporated

### No Issues Found:
- No regressions (528 tests pass, up from 512)
- Error handling covers all specified cases
- Implementation is ~107 lines of production code — matches plan's ~40 LOC estimate for register + ~30 LOC for ensure (the plan underestimated validation code)

---

## Mandatory Fixes Verified in Implementation

| Fix | Code Location | Status |
|-----|---------------|--------|
| 1. Separate bindings file | `bindings.py` writes to `.cw9/criterion_bindings.json` | ✅ |
| 2. `--ensure` flag | `cli.py:69-70` returns 0 when `.cw9/` exists | ✅ |
| 3. parent_req resolution | `cli.py:472-483` 3-step lookup before `register_gwt()` | ✅ |
| 4. No `--json` flag | `cli.py:604-606` only `target_dir` argument | ✅ |
| 5. No `extract` in flow | Not present in `cmd_register` or tests (except fixture setup) | ✅ |

---

## File Change Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `python/registry/bindings.py` | Created | 21 lines |
| `python/registry/cli.py` | Modified | +~120 lines (cmd_register + --ensure + argparse) |
| `python/tests/test_register.py` | Created | 230 lines |
| `python/tests/test_cli.py` | Modified | +3 tests for --ensure |

---

## Approval

✅ **Validation PASSED.** All 4 phases fully implemented. All 16 new tests pass. No regressions. All 5 mandatory fixes verified in code. W1 amendment incorporated. Full suite at 528 tests.
