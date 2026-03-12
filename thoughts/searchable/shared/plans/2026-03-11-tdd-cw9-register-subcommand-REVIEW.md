# Plan Review Report: `cw9 register` Subcommand

**Plan:** `thoughts/searchable/shared/plans/2026-03-11-tdd-cw9-register-subcommand.md`
**Reviewer:** DustyForge (Orchestration LLM)
**Date:** 2026-03-11

---

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 2 warnings |
| Interfaces | ✅ | 0 issues |
| Promises | ⚠️ | 1 warning |
| Data Models | ✅ | 0 issues |
| APIs | ⚠️ | 1 warning |
| Mandatory Fixes (5) | ✅ | All 5 addressed |

---

## Mandatory Fixes Verification

All 5 fixes from the prior orchestration session are addressed:

| Fix | Severity | Status | How Addressed |
|-----|----------|--------|---------------|
| 1. criterion_bindings in dag.json | CRITICAL | ✅ | Separate `bindings.py` module, `.cw9/criterion_bindings.json` |
| 2. `cw9 init --force` destructive | CRITICAL | ✅ | New `--ensure` flag (safe idempotent alternative) |
| 3. `parent_req` dangling reference | MEDIUM | ✅ | 3-step resolution in `cmd_register` before calling `register_gwt()` |
| 4. `--json` flag redundant | SMALL | ✅ | Omitted entirely — JSON is the only behavior |
| 5. `cw9 extract` in CW7 flow | MEDIUM | ✅ | `extract` appears only in test fixtures, not adapter flow |

**Verified against live code:**
- `dag.py:415-424` — `to_dict()` writes only `nodes`, `edges`, `closure`, `components`, conditional `test_artifacts`. No room for bindings.
- `dag.py:430-457` — `from_dict()` uses `.get()` for all keys; unknown keys silently dropped.
- `cli.py:64-67,89-91` — `--force` bypasses guard, unconditionally writes `_EMPTY_DAG`.
- `dag.py:347-350` — `register_gwt()` raises `NodeNotFoundError` unconditionally on invalid `parent_req`.

---

## Contract Review

### Well-Defined:
- ✅ **Stdin contract** (plan lines 254-278) — Clear JSON schema with `requirements` and `gwts` arrays. Required vs optional fields documented.
- ✅ **Stdout contract** (plan lines 280-291) — Mirrors stdin structure with allocated CW9 IDs.
- ✅ **Bindings contract** (Phase 1) — `load_bindings()` / `save_bindings()` with `dict[str, str]` type. Namespaced keys (`req:` / `gwt:` prefixes) prevent collision.
- ✅ **Error contract** — Exit 1 + JSON on stderr for all error cases. Three error cases tested: missing `.cw9/`, malformed JSON, missing `criterion_id`.
- ✅ **Processing order** (plan lines 293-301) — Requirements first, then GWTs. Explicit and correct.

### Warnings:

#### W1: Missing validation for `requirements[].id` (MEDIUM)

**Plan line 517:** `cw7_id = req.get("id", "")` silently defaults to empty string when `"id"` is absent.

**Impact:** If a requirement lacks `"id"`, the binding key becomes `"req:"` (empty string after prefix). A second requirement without `"id"` would collide on the same binding key, returning the first requirement's `req_id` for both. GWTs referencing `parent_req: ""` would also match this ghost binding.

**Recommendation:** Validate `requirements[].id` as required, same as `gwts[].criterion_id`:
```python
for i, req in enumerate(requirements):
    if "id" not in req:
        print(json.dumps({"error": f"requirements[{i}]: missing required field 'id'"}),
              file=sys.stderr)
        return 1
```

Add a test case:
```python
def test_missing_requirement_id_fails(self, project, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
        "requirements": [{"text": "no id here"}],
    })))
    rc = main(["register", str(project)])
    assert rc == 1
```

#### W2: Missing validation for `requirements[].text` (LOW)

**Plan line 524:** `text=req.get("text", cw7_id)` falls back to the CW7 ID when `"text"` is absent. This is reasonable but undocumented in the stdin contract. The contract at plan line 259 shows `"text"` present but doesn't say whether it's required or optional.

**Recommendation:** Document `"text"` as optional in the contract (with fallback to `id`), or validate it as required.

---

## Interface Review

### Well-Defined:
- ✅ **`register_gwt()` call** (plan line 554-560) — Parameters match verified signature at `dag.py:313-320`: `given`, `when`, `then`, `parent_req`, `name`. All correct.
- ✅ **`register_requirement()` call** (plan line 523-526) — Parameters match verified signature at `dag.py:354`: `text`, `name`. Correct.
- ✅ **`RegistryDag.load()` / `.save()`** (plan lines 495, 566) — Signatures verified at `dag.py:463-468`. `load(path)` returns `RegistryDag`, `save(path)` returns `None`.
- ✅ **`dag.nodes` dict iteration** (plan line 432) — Iterating `dag.nodes` yields string keys. Verified `dict[str, Node]` at `dag.py:30`.
- ✅ **`dag.edges` list with `from_id`/`to_id`** (plan line 416) — `Edge` dataclass has `from_id`, `to_id`, `edge_type`. Verified at `types.py:91-97`.
- ✅ **`Node.given` attribute** (plan line 659) — Verified `Node` has `given: str | None = None` at `types.py:55`. E2E test's `dag.nodes[gwt1_id].given` is valid.
- ✅ **CLI `main()` returns int** — Verified at `cli.py:443`. Tests assert `rc == 0` / `rc == 1` directly. No `sys.exit()` inside `main()`.
- ✅ **Argparse registration pattern** — Plan follows exact existing pattern: `sub.add_parser()` at lines 451-488, dispatch via `if/elif` at lines 492-508.
- ✅ **`--ensure` and `--force` mutual exclusivity** — Plan tests this (line 203-205) and implements the guard (line 220-221).

---

## Promise Review

### Well-Defined:
- ✅ **Idempotency** — Re-registration returns same IDs via bindings lookup. Tested in Phase 3 (tests 3d, 3e) and Phase 4 E2E.
- ✅ **`--ensure` no-op guarantee** — Tested by writing modified DAG and confirming it survives (plan line 196).
- ✅ **Processing order** — Requirements before GWTs, documented and enforced by code structure.

### Warnings:

#### W3: Stale binding → missing DAG node (LOW)

**Scenario:** First call registers `req-0001` and stores binding `req:r1 → req-0001`. User manually deletes `req-0001` from `dag.json`. Second call looks up binding, finds `req-0001`, returns it — but the node doesn't exist in the DAG. GWT's `parent_req` resolution would then find `req-0001` in bindings (step 3 at plan line 552), pass it to `register_gwt()`, which raises `NodeNotFoundError` at `dag.py:348`.

**Impact:** Low — requires manual DAG editing, which is unsupported. But worth noting.

**Recommendation:** No code change needed. Add a one-line design note: "Bindings assume DAG nodes are never manually deleted. If a bound node is missing, `register_gwt()` will raise `NodeNotFoundError`."

---

## Data Model Review

### Well-Defined:
- ✅ **Bindings file schema** — `dict[str, str]` with namespaced keys (`req:` / `gwt:` prefixes). Simple JSON round-trip. Plan lines 133-146.
- ✅ **DAG unchanged** — `to_dict()` / `from_dict()` not modified. Bindings are external. No migration needed.
- ✅ **Node fields** — `Node.given`, `Node.when`, `Node.then`, `Node.text` all exist as optional fields (`str | None = None`) on the dataclass at `types.py:55-58`.

---

## API Review

### Well-Defined:
- ✅ **CLI invocation** — `cw9 register <target_dir>` with JSON stdin, JSON stdout. No `--json` flag needed.
- ✅ **Exit codes** — 0 for success, 1 for all errors. Consistent with existing subcommands.
- ✅ **Error format** — JSON on stderr: `{"error": "..."}`. Machine-parseable.

### Warnings:

#### W4: `test_register_requirement` doesn't verify bindings file (LOW)

**Plan test 3a** (line 387-395) checks stdout has `req_id` starting with `req-` but doesn't verify the bindings file was written. The bindings round-trip is tested in Phase 1, and the E2E test in Phase 4 implicitly covers this (idempotent retry requires bindings). But the unit test for requirement registration could also assert bindings exist.

**Recommendation:** Optional — the E2E test covers this. No action required unless you want defense-in-depth.

---

## Code-Level Findings

### Well-Defined:
- ✅ **All line number references are accurate** — Verified against live code.
- ✅ **Test fixture `project`** (plan line 369-375) — Follows existing pattern from `test_cli.py` (`tmp_path / subdir`).
- ✅ **`monkeypatch.setattr("sys.stdin", ...)` pattern** — Correct for mocking stdin in pytest.
- ✅ **Stdout capture** via `monkeypatch.setattr("sys.stdout", io.StringIO())` — Works because `cmd_register` uses `print()`, not `sys.stdout.write()` with buffering. Correct.

### Notes (not issues):

- **N1:** `_run` helper is duplicated between `TestRegister` and `TestRegisterE2E`. Plan line 593 acknowledges this as a potential refactor. Acceptable as-is — test readability > DRY.
- **N2:** `getattr(args, 'ensure', False)` (plan line 220) is defensive but unnecessary since `--ensure` is defined on the init parser. `args.ensure` would work directly. Harmless.
- **N3:** Plan test at line 192 writes `{"nodes": {"x": {}}, ...}` as a DAG sentinel. This isn't a valid DAG (missing `closure`, `components`) but the test only checks raw JSON content, not loads it via `RegistryDag.load()`. Correct for the test's purpose.

---

## Critical Issues (Must Address Before Implementation)

**None.** All 5 mandatory fixes from the orchestration session are incorporated. The plan is sound.

---

## Suggested Plan Amendments

```diff
# In Phase 3: cmd_register validation

+ Add: Validate requirements[].id as required field (same pattern as criterion_id)
+ Add: Test case for missing requirement id
~ Clarify: Document requirements[].text as optional (fallback to id) in stdin contract
```

---

## Approval Status

- [x] **Ready for Implementation** — No critical issues
- [ ] **Needs Minor Revision** — Address warnings before proceeding
- [ ] **Needs Major Revision** — Critical issues must be resolved first

**Verdict:** Plan is approved for implementation. W1 (missing `requirements[].id` validation) should be incorporated during the Green phase — it's a 5-line addition that prevents a real silent-failure bug. W2-W4 are optional improvements.

---

## Review Checklist

### Contracts
- [x] Component boundaries are clearly defined
- [x] Input/output contracts are specified
- [x] Error contracts enumerate all failure modes
- [x] Preconditions and postconditions are documented
- [x] Invariants are identified

### Interfaces
- [x] All public methods are defined with signatures
- [x] Naming follows codebase conventions
- [x] Interface matches existing patterns
- [x] Extension points are considered
- [x] Visibility modifiers are appropriate

### Promises
- [x] Behavioral guarantees are documented
- [x] Async operations have timeout/cancellation handling (N/A — synchronous CLI)
- [x] Resource cleanup is specified (N/A — file writes are atomic-enough)
- [x] Idempotency requirements are addressed
- [x] Ordering guarantees are documented where needed

### Data Models
- [x] All fields have types
- [x] Required vs optional is clear
- [x] Relationships are documented
- [x] Migration strategy is defined (N/A — no schema changes)
- [x] Serialization format is specified

### APIs
- [x] All endpoints are defined
- [x] Request/response formats are specified
- [x] Error responses are documented
- [x] Authentication requirements are clear (N/A — local CLI)
- [x] Versioning strategy is defined (N/A — first version)
