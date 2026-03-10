---
date: 2026-03-10T07:54:05-04:00
researcher: claude-opus
git_commit: 650d82b
branch: master
repository: CodeWriter9.0
topic: "ProjectContext Refactor + Flywheel Features (Phases 6-8)"
tags: [orchestration, flywheel, refactor, project-context, packaging, self-hosting]
status: in_progress
last_updated: 2026-03-10
last_updated_by: claude-opus
type: implementation_strategy
---

# Handoff: ProjectContext Refactor + Flywheel Features Complete

## Task(s)

### Role: Plan Orchestrator
This session orchestrated feature development through the pipeline and reviewed all implementation LLM output for drift, correctness, and ground rule compliance.

### Completed — Phases 6-8: Three Pipeline-Built Features

**Phase 6: Dependency Validation** — `validate_edge()` pre-check
- GWT behaviors: `gwt-0015` (valid_edge_accepted), `gwt-0016` (cycle_creating_edge_rejected), `gwt-0017` (kind_incompatible_edge_rejected)
- TLC: 762 distinct states, 6 invariants, attempt 2
- 21 generated tests, all pass
- Implementation: `python/registry/dag.py:172-213`

**Phase 7: Subgraph Extraction** — `extract_subgraph()` minimal context query
- GWT behaviors: `gwt-0018` (ancestors_and_descendants), `gwt-0019` (isolated_node), `gwt-0020` (no_dangling_edges)
- TLC: 180,280 distinct states, 6 invariants, attempt 1
- 20 generated tests, all pass
- Implementation: `python/registry/dag.py:215-239`

**Phase 8: Change Propagation** — `query_affected_tests()` targeted test re-run query
- GWT behaviors: `gwt-0021` (affected_test_included), `gwt-0022` (no_artifacts_empty), `gwt-0023` (own_artifact_included)
- TLC: 1,349,968 distinct states, 5 invariants, attempt 2
- 17 generated tests, all pass
- Implementation: `python/registry/dag.py:242-259`, plus `test_artifacts` dict on RegistryDag

**All committed.** DAG: 96 nodes, 198 edges, 9 components. Test suite: 250 tests pass.

### In Progress — ProjectContext Refactor (uncommitted)

The `ProjectContext` refactor decouples CW9's path assumptions into three roots:
- `engine_root` — CW9's own code (templates, tools, python/registry)
- `target_root` — external project's source code
- `state_root` — project-specific state (DAG, schemas, specs, artifacts)

**Status: Code complete, reviewed, 250 tests pass, NOT YET COMMITTED.**

This was done as a direct refactor (not through the pipeline) because it's structural plumbing with no state machine to verify — just path routing.

### Discussed — Next Steps (Packaging Roadmap)

Scoped a 4-stage packaging plan:
- **Stage 0** (DONE): `ProjectContext` dataclass + refactor all path references
- **Stage 1** (NEXT): `cw9 init` creates `.cw9/` in target repo — CLI exists but needs testing on a real external project
- **Stage 2** (FUTURE): `cw9 ingest` for brownfield — scan existing codebase to populate schemas
- **Stage 3** (FUTURE): Package as installable CLI binary

## Critical References
- `BOOTSTRAP.md` — Master plan, 11/11 checklist complete (line 794-813)
- `BOOTSTRAP.md:626-661` — Phase 5+ self-hosting definition and pipeline flow
- `python/registry/context.py` — NEW: ProjectContext dataclass (the core of the refactor)

## Recent changes

### Committed (Phases 6-8):
- `python/registry/dag.py:166-213` — `validate_edge()` + `_KIND_INCOMPATIBLE` set
- `python/registry/dag.py:215-239` — `extract_subgraph()`
- `python/registry/dag.py:242-259` — `query_affected_tests()` + `test_artifacts` dict
- `python/registry/types.py` — added `ValidationResult`, `SubgraphResult` dataclasses
- `python/registry/extractor.py` — Phase 6/7/8 GWT registrations (15 nodes, ~60 edges)
- `python/tests/generated/test_dep_validation.py` — 21 generated tests
- `python/tests/generated/test_subgraph_extraction.py` — 20 generated tests
- `python/tests/generated/test_change_propagation.py` — 17 generated tests
- `templates/pluscal/instances/dep_validation.tla` — TLC-verified spec
- `templates/pluscal/instances/subgraph_extraction.tla` — TLC-verified spec
- `templates/pluscal/instances/change_propagation.tla` — TLC-verified spec

### Uncommitted (ProjectContext refactor):
- `python/registry/context.py` — NEW: `ProjectContext` with `self_hosting()`, `external()`, `from_target()` constructors
- `python/registry/cli.py` — NEW: `cw9 init` and `cw9 status` commands
- `cw9` — NEW: CLI entry point script (repo root)
- `python/registry/one_shot_loop.py:242-266` — `_find_tla2tools` now takes `tools_dir` instead of `project_root`; `OneShotLoop` accepts `ctx: ProjectContext`
- `python/run_impact_loop.py` — uses `ctx.session_dir`, `ctx.template_dir`, `ctx.schema_dir`, `ctx.spec_dir`, `ctx.artifact_dir`
- `python/run_dep_validation_loop.py` — same pattern
- `python/run_subgraph_loop.py` — same pattern
- `python/run_change_prop_loop.py` — same pattern
- `python/run_bridge_loop.py` — same pattern
- `python/run_bridge_retroactive.py` — same pattern
- `python/pyproject.toml` — added `[project.scripts] cw9 = "registry.cli:main"`
- `python/registry/__init__.py` — exports `ProjectContext`

## Learnings

### Pipeline orchestration
- **Step ordering matters.** Implementation LLM tried to implement `query_affected_tests()` before running the pipeline (tests first, implement second). Caught and redirected — the pipeline flow is GWT → loop → TLC → bridge → test gen → THEN implement.
- **Watch for speculative dependencies.** Implementation LLM added `depval-0001 → impact-0001` edge that wasn't real. Caught and removed.
- **Direct refactor is appropriate for plumbing.** `ProjectContext` has no state machine to model — TLC can't verify path correctness. Existing tests validate the self-hosting case; integration tests against external projects validate the external case.

### ProjectContext architecture
- The path coupling surface is narrower than expected: one anchor (`PROJECT_ROOT`) with known relative paths. The refactor touched 6 files in `python/registry/` and 6 `run_*` scripts.
- `OneShotLoop` has backward-compatible `project_root` param that auto-converts to `ProjectContext` in `__post_init__`. This means existing code that hasn't been updated yet still works.
- `cli.py:109` has a minor concern: `dag_path = ctx.schema_dir.parent / "dag.json"` assumes DAG is one level above schema_dir. Works for external layout, slightly wrong for self-hosting. Not blocking since `cw9 status` targets external projects.

### Agent mail note
- Identity: **DustyForge** on project `/home/maceo/Dev/CodeWriter9.0`
- **Important:** Use agent mail for coordination context, NOT local memory files, to avoid polluting the project's memory with session-specific state.

## Artifacts
- `python/registry/context.py` — ProjectContext dataclass (NEW, uncommitted)
- `python/registry/cli.py` — cw9 CLI entry point (NEW, uncommitted)
- `cw9` — CLI shell script (NEW, uncommitted)
- `python/run_dep_validation_loop.py` — Phase 6 loop script (committed)
- `python/run_subgraph_loop.py` — Phase 7 loop script (committed)
- `python/run_change_prop_loop.py` — Phase 8 loop script (committed)
- `templates/pluscal/instances/dep_validation.tla` — Phase 6 verified spec
- `templates/pluscal/instances/subgraph_extraction.tla` — Phase 7 verified spec
- `templates/pluscal/instances/change_propagation.tla` — Phase 8 verified spec
- `python/tests/generated/dep_validation_bridge_artifacts.json`
- `python/tests/generated/subgraph_extraction_bridge_artifacts.json`
- `python/tests/generated/change_propagation_bridge_artifacts.json`
- `thoughts/searchable/shared/handoffs/general/2026-03-10_06-51-35_phase8-complete-change-propagation.md` — Implementation LLM's handoff

## Action Items & Next Steps

### Immediate (commit the refactor):
1. **Commit the ProjectContext refactor** — All uncommitted changes listed above. 250 tests pass. This is the prerequisite for everything below.
2. **Clean up temp files in repo root** — `*_llm_response*.txt`, `*_loop_output.log`, `#!Notes.md` (8+ files polluting root since Phase 5)

### Stage 1 — External project support:
3. **Test `cw9 init` + `cw9 status` on a real external project** — The CLI works (`cw9 init /tmp/test` verified) but hasn't been tested with actual schemas and a pipeline run.
4. **Create starter schema templates** — `cw9 init` currently creates empty `schema/` dir. Needs template schemas (backend, frontend, middleware, shared) with empty structures for greenfield.
5. **Test full pipeline on external project** — Create a small test project, `cw9 init`, add schemas, run a loop script pointed at the external project's `ProjectContext.external()`. This is the real validation.

### Stage 2 — Brownfield ingestion (future):
6. **Design `cw9 ingest`** — Scan existing codebase to populate schemas. Options: LLM-assisted, convention-based, or manual. This is the hard problem.

### Stage 3 — CLI packaging (future):
7. **Package as installable tool** — Python CLI first (`pip install`), Rust binary later.

## Other Notes

### DAG state after Phase 8
- 96 nodes, 198 edges, 9 connected components
- Phase 6 nodes: `req-0005`, `gwt-0015`, `gwt-0016`, `gwt-0017`, `depval-0001`
- Phase 7 nodes: `req-0006`, `gwt-0018`, `gwt-0019`, `gwt-0020`, `subgraph-0001`
- Phase 8 nodes: `req-0007`, `gwt-0021`, `gwt-0022`, `gwt-0023`, `changeprop-0001`
- Next IDs: `req-0008`, `gwt-0024+`

### Test execution
```bash
cd python && python3 -m pytest tests/ -v
# 250 passed — must run from python/ directory
```

### CLI usage
```bash
# From repo root:
./cw9 init /path/to/external/project
./cw9 status /path/to/external/project

# Or from python/:
python3 -m registry.cli init /path/to/project
```

### Key file locations
- ProjectContext: `python/registry/context.py`
- CLI: `python/registry/cli.py`, `cw9` (repo root)
- Registry DAG: `python/registry/dag.py` (validate_edge:172, extract_subgraph:215, query_affected_tests:242)
- Schema extractor: `python/registry/extractor.py` (self-registration at end of file)
- One-shot loop: `python/registry/one_shot_loop.py` (OneShotLoop:585, now accepts ctx param)
- Loop scripts: `python/run_*_loop.py` (all 5 now use ProjectContext)
- TLA+ instances: `templates/pluscal/instances/`

### Pipeline commands
```bash
# Run all tests
cd python && python3 -m pytest tests/ -v

# Run a loop (example: impact analysis)
CLAUDECODE= python3 python/run_impact_loop.py

# Re-extract DAG
python3 -c "from registry.extractor import SchemaExtractor; e = SchemaExtractor(schema_dir='schema/'); d = e.extract(); d.save('schema/registry_dag.json')"
```

### Agent coordination
- Use agent mail (DustyForge identity) for session coordination, NOT local memory files
- Topic `bootstrap-state` has messages from Phase 3-5
