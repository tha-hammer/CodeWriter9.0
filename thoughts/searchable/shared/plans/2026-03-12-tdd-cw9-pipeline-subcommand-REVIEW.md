# Plan Review Report: `cw9 pipeline` Subcommand — TDD Implementation Plan

**Reviewer**: DustyForge
**Date**: 2026-03-12
**Plan**: `thoughts/searchable/shared/plans/2026-03-12-tdd-cw9-pipeline-subcommand.md`
**Research**: `thoughts/searchable/shared/research/2026-03-12-run-loop-bridge-wiring.md`

---

## Review Summary

| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ⚠️ | 4 issues |
| Interfaces | ⚠️ | 3 issues |
| Promises | ✅ | 1 issue |
| Data Models | ✅ | 1 issue |
| APIs | ⚠️ | 3 issues |

---

## Contract Review

### Well-Defined:
- ✅ **`_register_payload()` extraction** — Clean separation of IO (stdin/stdout) from business logic. Validation stays in `cmd_register()` as CLI-layer concern, `_register_payload()` receives pre-validated dict. This matches the actual code at `cli.py:421-513` well.
- ✅ **`registry.cw7` module** — Pure move of 4 functions with no behavioral change. `extract()`, `build_plan_path_map()`, `copy_context_files()`, `_slugify()` have no external dependencies beyond stdlib.
- ✅ **Exit code contract** — B8 clearly specifies: rc=0 only when all attempted phases pass. Matches existing `run_loop_bridge.py:479-485` logic.
- ✅ **`cmd_register()` thin wrapper** — B2 test_register_via_stdin_still_works ensures backward compat. Regression gate in B9 is appropriate.

### Missing or Unclear:

- ⚠️ **`_register_payload()` return type not fully specified** — Plan shows `{"requirements": req_output, "gwts": gwt_output}` but doesn't specify the shape of each element. From actual code: `req_output` is `[{"id": cw7_id, "req_id": req_id}]` and `gwt_output` is `[{"criterion_id": criterion_id, "gwt_id": gwt_id}]`. Tests in B2 check `result["requirements"][0]["req_id"].startswith("req-")` which is correct. **Recommendation**: Add docstring with return type to plan's `_register_payload()` pseudo-code.

- ⚠️ **Error contract for `_register_payload()` unspecified** — What happens if `target` has no `.cw9/`? If DAG is missing? If bindings file is corrupt? The current `cmd_register()` checks for `.cw9/` before calling business logic. `_register_payload()` calls `ProjectContext.from_target(target)` which will succeed even without `.cw9/` (falls through to installed mode). **Recommendation**: `_register_payload()` should raise `ValueError` or return error dict if preconditions fail, OR the `.cw9/` check should remain a precondition enforced by callers.

- ⚠️ **`extract()` error contract change** — Plan says "Remove `sys.exit()` calls — raise `ValueError` instead" but doesn't specify which `sys.exit()` calls exist in `extract()`. Looking at actual code: `extract()` in `cw7_extract.py` calls `sys.exit(1)` when session auto-detection finds 0 or >1 sessions. The `main()` function also calls `sys.exit(1)` for missing DB. **Recommendation**: Specify exactly: `extract()` should raise `ValueError("No sessions found")` and `ValueError("Multiple sessions: ...")` instead of `sys.exit()`. The `main()` wrapper keeps `sys.exit()`.

- ❌ **`cmd_pipeline()` ↔ `cmd_loop()`/`cmd_bridge()` calling contract is underspecified** — Plan says "calls `cmd_loop()` and `cmd_bridge()` by constructing `argparse.Namespace` objects" but never defines the Namespace shape. From actual code:
  - `cmd_loop` expects: `args.gwt_id` (str), `args.target_dir` (str), `args.max_retries` (int), `args.context_file` (Path|None)
  - `cmd_bridge` expects: `args.gwt_id` (str), `args.target_dir` (str)

  **Recommendation**: Add explicit Namespace construction to B4 Green section:
  ```python
  loop_ns = argparse.Namespace(
      gwt_id=gwt_id, target_dir=str(target),
      max_retries=args.max_retries, context_file=ctx_path,
  )
  bridge_ns = argparse.Namespace(
      gwt_id=gwt_id, target_dir=str(target),
  )
  ```

---

## Interface Review

### Well-Defined:
- ✅ **CLI argument interface** — Desired end state (lines 31-37) clearly shows all flag combinations. Matches `run_loop_bridge.py` argparse (lines 341-380).
- ✅ **Subcommand registration pattern** — Plan correctly follows existing `p_<name> = sub.add_parser(...)` + `elif args.command == "..."` pattern from `cli.py:572-642`.
- ✅ **`registry.cw7` public interface** — `extract`, `build_plan_path_map`, `copy_context_files` matches actual `cw7_extract.py` exports.

### Missing or Unclear:

- ❌ **`cmd_pipeline()` subparser definition not specified** — Plan shows the stub function (B3) but never provides the subparser registration code. Need:
  ```python
  p_pipeline = sub.add_parser("pipeline", help="Run full CW9 pipeline: setup → loop → bridge")
  p_pipeline.add_argument("target_dir", nargs="?", default=".")
  p_pipeline.add_argument("--db", type=Path, default=None)
  p_pipeline.add_argument("--session", default=None)
  p_pipeline.add_argument("--gwt", action="append", dest="gwts", default=None)
  p_pipeline.add_argument("--max-retries", type=int, default=5)
  p_pipeline.add_argument("--skip-setup", action="store_true")
  p_pipeline.add_argument("--loop-only", action="store_true")
  p_pipeline.add_argument("--bridge-only", action="store_true")
  p_pipeline.add_argument("--plan-path-dir", type=Path, default=None)
  ```
  **Impact**: Without this, implementor must infer arg names from test code. Risk of mismatch between test expectations and argparse names (e.g., `args.gwts` vs `args.gwt`, `args.max_retries` vs `args.max_retries`).

- ⚠️ **`--db` env var fallback** — Plan says "Missing DB is an error" (hard constraint) and B3 tests `monkeypatch.delenv("CW7_DB")`. But the env var name isn't documented. Old code uses `CW7_FIXTURE_DB`. Plan should specify: `args.db = args.db or os.environ.get("CW7_DB")`.

- ⚠️ **`target_dir` argument position** — Current `loop` subcommand uses `p_loop.add_argument("gwt_id")` then `p_loop.add_argument("target_dir", nargs="?", default=".")`. Plan's desired syntax is `cw9 pipeline /path/to/project --db ...` (target_dir is positional first). This means pipeline's subparser should have `target_dir` as the first positional arg. Tests in B3 use `main(["pipeline", str(project), "--db", ...])` confirming positional-first. Just needs to be explicit in subparser definition.

---

## Promise Review

### Well-Defined:
- ✅ **Phase ordering guarantee** — setup → loop → bridge. Skip semantics clearly defined (B5).
- ✅ **Per-GWT iteration** — Loop runs for each GWT, bridge runs only for verified GWTs (those with `.tla` specs).
- ✅ **Idempotency** — `_register_payload()` is idempotent via bindings lookup (B2 test_idempotent_on_rerun).
- ✅ **Mode exclusivity** — `--loop-only` skips bridge, `--bridge-only` skips setup+loop, `--skip-setup` skips init/extract/register.

### Missing or Unclear:

- ⚠️ **Partial failure behavior** — If GWT-1 loop passes but GWT-2 loop fails, does bridge still run for GWT-1? Looking at `run_loop_bridge.py:434`: `verified_ids = [gid for gid, passed in loop_results.items() if passed]` — yes, bridge runs for passed GWTs only. Plan's B8 tests don't cover this partial-failure-continues case. **Recommendation**: Add test: "loop fails for one GWT, bridge still runs for the other, rc=1".

---

## Data Model Review

### Well-Defined:
- ✅ **CW7 DB schema** — `_make_cw7_db` fixture creates `sessions`, `requirements`, `acceptance_criteria`, `plan_paths` tables. Matches actual CW7 schema used by `cw7_extract.py`.
- ✅ **Bridge artifacts schema** — `_make_bridge_artifacts()` helper matches actual bridge output structure (`gwt_id`, `module_name`, `data_structures`, `operations`, `verifiers`, `assertions`, `test_scenarios`).
- ✅ **DAG JSON structure** — `{"nodes": {}, "edges": [], "test_artifacts": {}}` matches `_EMPTY_DAG` at `cli.py:49-53`.

### Missing or Unclear:

- ⚠️ **`_make_cw7_db` fixture inconsistency between B1 and B4** — Plan's B1 `_make_cw7_db` (line 84-111) creates **1 GWT** (1 acceptance_criteria row). But B4's `test_pipeline_calls_loop_per_gwt` (line 512-513) asserts `len(loop_gwts) == 2`, which requires 2 GWTs. The existing `_make_cw7_db` in `test_run_loop_bridge.py:43-95` creates **2 GWTs** (2 acceptance_criteria rows, 2 plan_paths). **Recommendation**: B1's `_make_cw7_db` should match the existing fixture with 2 GWTs, or B4's assertion should be `== 1`. Suggest: match existing fixture (2 GWTs) since B4 depends on it.

---

## API Review

### Well-Defined:
- ✅ **CLI interface** — `cw9 pipeline <target> --db <path> [--session ID] [--gwt ID]... [--loop-only|--bridge-only] [--skip-setup] [--plan-path-dir PATH] [--max-retries N]` — comprehensive flag set.
- ✅ **Backward compatibility** — `cw9 register` via stdin/stdout unchanged (B9 regression gate).
- ✅ **Import compatibility** — `tools/cw7_extract.py` becomes thin re-export wrapper.

### Missing or Unclear:

- ⚠️ **`--gwt` flag semantics when used with setup** — B6's `test_explicit_gwts_processed` uses `--gwt gwt-0001` with `--loop-only` after setup. But what if the user specifies `--gwt gwt-9999` (non-existent)? Should `cmd_pipeline` validate GWT existence, or just pass through and let `cmd_loop` fail? Old code passes through. Plan should document this.

- ⚠️ **`--plan-path-dir` without `--db`** — Plan doesn't test/specify what happens with `--plan-path-dir` but no `--db`. Setup phase needs `--db` for `extract()` and `build_plan_path_map()`. If `--skip-setup` + `--plan-path-dir`, context files can't be copied (no register_output for criterion mapping). Old code handles this via `setup_project()` which has the DB. Plan should clarify: `--plan-path-dir` is only meaningful with setup phase.

- ❌ **`resolve_gwt_ids` not addressed** — Plan doesn't specify how GWT ID resolution works in `cmd_pipeline()`. The old `run_loop_bridge.py:313-335` has `resolve_gwt_ids()` that: (1) uses explicit `--gwt` args if provided, (2) reads from register_output, (3) falls back to DAG. This logic needs to exist in `cmd_pipeline()` but is never specified. B8's `test_no_gwts_found_returns_1` tests the failure case, but the resolution logic itself isn't defined. **Recommendation**: Specify `resolve_gwt_ids` as a helper or inline in `cmd_pipeline()`.

---

## Critical Issues (Must Address Before Implementation)

1. **`_make_cw7_db` fixture has 1 GWT in B1 but B4 expects 2 GWTs**
   - Impact: B4 `test_pipeline_calls_loop_per_gwt` will fail even with correct implementation
   - Recommendation: Update B1's `_make_cw7_db` to include 2 GWTs (matching existing fixture in `test_run_loop_bridge.py:43-95`)

2. **Subparser definition for `pipeline` command missing from plan**
   - Impact: Implementor must reverse-engineer arg names from test assertions, risking name mismatches
   - Recommendation: Add explicit subparser registration to B3's Green section

3. **`resolve_gwt_ids` logic unspecified**
   - Impact: Without GWT resolution, `cmd_pipeline()` can't determine what to process when `--gwt` isn't given
   - Recommendation: Port `resolve_gwt_ids()` from `run_loop_bridge.py:313-335` into `cmd_pipeline()` or as a shared helper

4. **Namespace construction for `cmd_loop`/`cmd_bridge` calls unspecified**
   - Impact: Wrong attribute names in Namespace will cause AttributeError at runtime
   - Recommendation: Add explicit Namespace construction showing all required attributes

---

## Suggested Plan Amendments

```diff
# In Behavior 1: _make_cw7_db fixture

- conn.execute("INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
-              (1, session_id, "REQ-001", "gwt",
-               "the app loads", "the counter renders", "counter shows 0"))
+ # Match existing test_run_loop_bridge.py fixture: 2 GWTs
+ conn.execute("INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
+              (1, session_id, "REQ-001", "gwt",
+               "the app loads", "the counter renders", "counter shows 0"))
+ conn.execute("INSERT INTO acceptance_criteria VALUES (?, ?, ?, ?, ?, ?, ?)",
+              (2, session_id, "REQ-001", "gwt",
+               "counter is 5", "user clicks increment", "counter becomes 6"))
+ # Add second plan_path
+ conn.execute("INSERT INTO plan_paths VALUES (?, ?, ?)", (1002, session_id, 2))

# In Behavior 3: Add subparser definition

+ # In Green section, add to cli.py main():
+ p_pipeline = sub.add_parser("pipeline", help="Run full CW9 pipeline: setup → loop → bridge")
+ p_pipeline.add_argument("target_dir", nargs="?", default=".")
+ p_pipeline.add_argument("--db", type=Path, default=None,
+                          help="CW7 SQLite database path (or set CW7_DB env var)")
+ p_pipeline.add_argument("--session", default=None)
+ p_pipeline.add_argument("--gwt", action="append", dest="gwts", default=None)
+ p_pipeline.add_argument("--max-retries", type=int, default=5)
+ p_pipeline.add_argument("--skip-setup", action="store_true")
+ p_pipeline.add_argument("--loop-only", action="store_true")
+ p_pipeline.add_argument("--bridge-only", action="store_true")
+ p_pipeline.add_argument("--plan-path-dir", type=Path, default=None)

# In Behavior 3: Add env var fallback for --db

+ # At top of cmd_pipeline(), after need_setup check:
+ if need_setup:
+     db = args.db or Path(os.environ.get("CW7_DB", ""))
+     if not db or not str(db):
+         print("Error: --db required (or set CW7_DB)", file=sys.stderr)
+         return 1

# In Behavior 4: Add resolve_gwt_ids helper

+ def _resolve_gwt_ids(project_dir, register_output, explicit_gwts):
+     """Port of run_loop_bridge.resolve_gwt_ids."""
+     if explicit_gwts:
+         return explicit_gwts
+     if register_output and register_output.get("gwts"):
+         return [g["gwt_id"] for g in register_output["gwts"]]
+     dag_path = project_dir / ".cw9" / "dag.json"
+     if dag_path.exists():
+         dag_data = json.loads(dag_path.read_text())
+         return sorted(nid for nid in dag_data.get("nodes", {}) if nid.startswith("gwt-"))
+     return []

# In Behavior 4: Add Namespace construction

+ # When calling cmd_loop:
+ loop_ns = argparse.Namespace(
+     gwt_id=gwt_id,
+     target_dir=str(target),
+     max_retries=args.max_retries,
+     context_file=ctx_file_path,  # Path or None
+ )
+ rc = cmd_loop(loop_ns)
+
+ # When calling cmd_bridge:
+ bridge_ns = argparse.Namespace(
+     gwt_id=gwt_id,
+     target_dir=str(target),
+ )
+ rc = cmd_bridge(bridge_ns)
```

---

## Review Checklist

### Contracts
- [x] Component boundaries are clearly defined
- [x] Input/output contracts are specified (with amendments above)
- [ ] Error contracts enumerate all failure modes — **`_register_payload()` errors unspecified**
- [x] Preconditions and postconditions are documented
- [x] Invariants are identified

### Interfaces
- [x] All public methods are defined with signatures
- [x] Naming follows codebase conventions
- [x] Interface matches existing patterns
- [x] Extension points are considered
- [ ] Visibility modifiers are appropriate — **need `_resolve_gwt_ids` as private helper**

### Promises
- [x] Behavioral guarantees are documented
- [x] Async operations have timeout/cancellation handling (N/A — sync)
- [x] Resource cleanup is specified (temp dir from old script stays as-is)
- [x] Idempotency requirements are addressed
- [ ] Ordering guarantees are documented where needed — **partial failure continue behavior unspecified**

### Data Models
- [x] All fields have types
- [ ] Required vs optional is clear — **`_make_cw7_db` fixture mismatch**
- [x] Relationships are documented
- [x] Migration strategy is defined (N/A)
- [x] Serialization format is specified (JSON)

### APIs
- [ ] All endpoints are defined — **subparser registration missing**
- [x] Request/response formats are specified
- [x] Error responses are documented
- [x] Authentication requirements are clear (N/A)
- [x] Versioning strategy is defined (N/A)

---

## Approval Status

- [ ] **Ready for Implementation** — No critical issues
- [x] **Needs Minor Revision** — Address the 4 critical items above before proceeding
- [ ] **Needs Major Revision** — Critical issues must be resolved first

**Verdict**: The plan is architecturally sound and the TDD structure is well-organized. The 4 critical items are all specification gaps (not design flaws) that can be filled with the amendments above. The underlying approach — extract `_register_payload()`, move `cw7_extract.py`, add `cmd_pipeline()` following existing patterns — is correct. Once amendments are applied, the plan is ready for implementation.
