---
date: 2026-03-10
researcher: claude-opus
branch: master
repository: CodeWriter9.0
topic: "TDD Plan: Multi-Language Test Generation (Strangler Fig)"
tags: [tdd, plan, multi-language, typescript, rust, go, bridge, test-gen]
status: implemented
type: tdd-plan
---

# Multi-Language Test Generation — TDD Implementation Plan

## Overview

Extend the CW9 test generation pipeline to emit tests in TypeScript, Rust, and Go
in addition to Python. The bridge artifacts are already language-neutral JSON; all
Python coupling lives downstream in 4 files. We use a strangler-fig approach:
refactor Python to use the new abstraction first, then add TypeScript, Rust, and
Go as successive implementations — TypeScript validates the abstraction, Rust and
Go prove it generalizes.

## Plan Files

| Phase | File | Behaviors | Description |
|-------|------|-----------|-------------|
| 1 | [phase1-abstraction.md](phase1-abstraction.md) | B1–B6 (incl. B5b) | Extract the abstraction (Strangler Fig on Python) |
| 2 | [phase2-typescript.md](phase2-typescript.md) | B7–B11 | TypeScript implementation |
| 3 | [phase3-rust.md](phase3-rust.md) | B12–B17 | Rust implementation |
| 4 | [phase4-go.md](phase4-go.md) | B18–B24 | Go implementation |

## Cross-Cutting Design Decisions

These apply across ALL phases and were established during plan review:

1. **`VerifyResult` lives in `lang.py`** (not `test_gen_loop.py`) — prevents circular
   imports when language backends return verification results.
2. **`CompiledExpression.helper_defs`** — empty string by default, used by Go for
   quantifier helper functions. Compiled expressions are prompt hints, not eval'd code.
3. **Shared `_extract_code_by_fence_tag()`** in `lang.py` — all 4 profiles delegate
   `extract_code_from_response()` to this, parameterized by `fence_language_tag`.
4. **`compile_assertions()` in protocol** — replaces the old `tla_compiler.compile_assertions()`
   call in `build_compiler_hints()`. Ensures `--lang rust` produces Rust hints, not Python.
5. **`test_file_name()` in protocol** — ensures every profile declares its output naming.
6. **`@pytest.mark.integration`** — registered in `pyproject.toml`, auto-skipped via
   `conftest.py` when required tools aren't installed.
7. **Profiles are stateless** — `get_profile()` creates a new instance per call.

## Current State Analysis

### Python Coupling Points (6 total, 4 files)

| # | Location | What's coupled | Line(s) |
|---|----------|----------------|---------|
| C1 | `tla_compiler.py` | Compiles TLA+ → **Python** expressions (`all()`, `len()`, `==`) | 29-108 |
| C2 | `test_gen_loop.py:discover_api_context()` | Globs `*.py`, reads `import/class/def` lines | 74-111 |
| C3 | `test_gen_loop.py:build_test_plan_prompt()` | Hardcoded Python code examples (RegistryDag, pytest.raises) | 176-196 |
| C3b | `test_gen_loop.py:build_codegen_prompt()` | `from registry.dag import`, `pass compile()` | 260-277 |
| C3c | `test_gen_loop.py:build_retry_prompt()` | Same Python import instructions | 280-298 |
| C4 | `test_gen_loop.py:verify_test_file()` | `compile()` → `pytest --collect-only` → `pytest -x` | 301-346 |
| C5 | `test_gen_loop.py:_extract_code_from_response()` | `` `python` `` fence pattern | 349-380 |
| C6 | `test_gen_loop.py:_TEST_GEN_SYSTEM_PROMPT` | "Python test generation expert" | 383-389 |
| C7 | `test_gen_loop.py:TestGenContext.python_dir` | Field name leaks Python | 46 |
| C8 | `cli.py:cmd_gen_tests()` | No `--lang` flag, hardcodes pytest path | 296-375, 471-474 |
| C9 | `context.py:ProjectContext.python_dir` | Field semantically means "source dir" | 30 |

### What's Already Language-Neutral

- `bridge.py` — all 4 translators produce abstract schema paths (`shared/data_types/String`)
- `traces.py` — simulation trace loading/formatting
- `one_shot_loop.py` — GWT → PlusCal → TLC loop
- `dag.py`, `types.py`, `extractor.py` — core DAG infrastructure
- Bridge artifact JSON format — `data_structures`, `operations`, `verifiers`, `assertions`

### Key Discoveries

- `_tla_type_to_schema_type()` in `bridge.py:331` maps to abstract types, not Python types
- `CompiledAssertion` dataclass has `python_expr` field — needs renaming to `target_expr`
- `verify_test_file()` has a clean 3-stage pattern (syntax → collect → run) that maps
  well to other languages: `cargo check`/`tsc --noEmit` → `cargo test --no-run`/`jest --listTests` → `cargo test`/`jest`
- `ProjectContext.python_dir` is used by both `discover_api_context()` and `verify_test_file()` — semantically "source root"

## Desired End State

A `TargetLanguage` protocol/enum that selects:
- Assertion compiler (TLA+ → target language expressions)
- API context discovery (scan source files for public signatures)
- Prompt builders (system prompt + structural patterns + code examples)
- Test file verification (syntax check → test discovery → test execution)
- Code extraction from LLM response (language-specific fence patterns)
- Output file extension and path

Python remains the default. TypeScript validates the abstraction. Rust and Go
are implemented using the same interface, proving the protocol generalizes
across compiled, systems, and GC'd languages.

### Observable Behaviors

1. `cw9 gen-tests gwt-0024 --lang python` produces identical output to today
2. `cw9 gen-tests gwt-0024 --lang typescript` produces a `.test.ts` file
3. `cw9 gen-tests gwt-0024 --lang rust` produces a `.rs` test file
4. `cw9 gen-tests gwt-0024 --lang go` produces a `_test.go` file
5. `cw9 gen-tests gwt-0024` (no flag) defaults to `python` (backwards compatible)
6. Each language's compiler transforms TLA+ conditions into idiomatic expressions
7. Each language's verifier uses the correct toolchain (`pytest`/`jest`/`cargo test`/`go test`)

## What We're NOT Doing

- Changing the bridge — it's already language-neutral
- Changing the TLA+/PlusCal loop — language-independent
- Changing the DAG, extractor, or schema format
- Multi-language in a single project (one `--lang` per `gen-tests` invocation)

## Testing Strategy

- **Framework**: pytest (our test harness is Python regardless of target language)
- **Unit tests**: Each behavior gets its own test class mirroring existing patterns
- **Integration**: CLI flag wiring, end-to-end prompt assembly
- **No mocks for core types**: Use real `ParsedSpec`, `BridgeResult`, etc.

## Implementation Order

```
Phase 1 (Strangler Fig):
  B1: TargetLanguage enum
  B2: LanguageProfile protocol (incl. compile_assertions, test_file_name, VerifyResult, CompiledExpression.helper_defs)
  B3: PythonProfile (wrap existing, CompiledAssertion→CompiledExpression migration)
  B4: TestGenContext refactor (source_dir, lang_profile, prompt builder signatures)
  B5: CLI --lang flag
  B5b: Integration test markers + tool-availability skip decorators
  B6: Output path logic
  ── Checkpoint: all tests pass, Python unchanged ──

Phase 2 (TypeScript):
  B7:  TS assertion compiler
  B8:  TS API discovery
  B9:  TS prompts
  B10: TS verification
  B11: TS code extraction
  ── Checkpoint: --lang typescript works ──

Phase 3 (Rust):
  B12: Rust assertion compiler
  B13: Rust API discovery
  B14: Rust prompts
  B15: Rust verification
  B16: Rust code extraction
  B17: Rust output file naming
  ── Checkpoint: --lang rust works ──

Phase 4 (Go):
  B18: Go assertion compiler
  B19: Go API discovery
  B20: Go prompts
  B21: Go verification
  B22: Go code extraction
  B23: Go output file naming
  B24: get_profile() factory complete
  ── Checkpoint: --lang go works, all 4 languages complete ──
```

## References

- Bridge implementation: `python/registry/bridge.py`
- TLA+ compiler: `python/registry/tla_compiler.py`
- Test gen loop: `python/registry/test_gen_loop.py`
- CLI: `python/registry/cli.py`
- Context: `python/registry/context.py`
- Existing bridge tests: `python/tests/test_bridge.py`
- Existing compiler tests: `python/tests/test_tla_compiler.py`
- Existing CLI tests: `python/tests/test_cli.py`
- Pipeline plan review (typed IR gap): `thoughts/searchable/shared/docs/registry-driven-pipeline-plan-REVIEW.md`
