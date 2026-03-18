---
date: 2026-03-13T21:01:00-04:00
researcher: DustyForge
git_commit: 66c4f88d6e6d8a7b0cd3b6588544047a9abc1a4c
branch: feature/brownfield-code-walker
repository: CodeWriter9.0
topic: "How-to: Brownfield Code Walker for Existing Codebases"
tags: [documentation, howto, brownfield, code-walker, in-do-out, crawl, pipeline, ingest]
status: complete
last_updated: 2026-03-13
last_updated_by: DustyForge
type: howto
---

# How to Use the Brownfield Code Walker to Add Features to an Existing Codebase

## Introduction

This guide walks through using the CW9 brownfield code walker to ingest an existing codebase, extract behavioral IN:DO:OUT cards for every function, detect staleness when code changes, author GWT specifications that reference ingested functions by UUID, and feed those cards into the CW9 pipeline for formal verification. The result is a persistent, queryable behavioral map of the codebase that replaces manual research.

## Prerequisites

- CW9 engine installed (`python/registry/` package on your PATH as `cw9`)
- An initialized CW9 project (run `cw9 init` on your target project first)
- The external codebase you want to ingest accessible on disk
- Claude Agent SDK configured (for LLM extraction in `cw9 ingest` Phase 1 and `cw9 gwt-author`)

### Supported Languages

| Language | Scanner | Entry Point Detection | File Extensions |
|----------|---------|----------------------|-----------------|
| Python | `scanner_python.py` | Yes (Flask, FastAPI, Click, argparse, main) | `*.py` |
| JavaScript | `scanner_javascript.py` | Auto-detected via `package.json` | `*.js`, `*.jsx` (excludes `*.min.js`) |
| TypeScript | `scanner_typescript.py` | Auto-detected via `tsconfig.json` | `*.ts`, `*.tsx` (excludes `*.d.ts`) |
| Go | `scanner_go.py` | Auto-detected via `go.mod` | `*.go` (excludes `*_test.go`) |
| Rust | `scanner_rust.py` | Auto-detected via `Cargo.toml` | `*.rs` |

## Step 1: Initialize Your CW9 Project

If you haven't already, create the `.cw9/` directory in your project:

```bash
cw9 init /path/to/your/project
```

This creates the `.cw9/` directory where `crawl.db`, `dag.json`, and other pipeline artifacts live.

## Step 2: Ingest the External Codebase

Run the skeleton pre-pass and populate `crawl.db`:

```bash
cw9 ingest /path/to/external/codebase /path/to/your/project
```

This performs several phases in sequence:

1. **Phase 0 (Skeleton Pre-Pass)** -- Scans all source files using the language-appropriate scanner, extracting function/method signatures (name, params, return type, line number, file hash) without reading function bodies.
2. **Phase 0b (Entry Point Discovery)** -- Detects HTTP routes, CLI commands, `main()` functions, and public API surfaces (Python only).
3. **Phase 1 (Store Population)** -- Creates a `crawl.db` SQLite database with one record per function. Records are initially `SKELETON_ONLY` -- they have signatures but no behavioral IN:DO:OUT data yet.
4. **Post-Crawl Bridge** -- Materializes all crawl records into the registry DAG as `RESOURCE` nodes with `CALLS` edges, and removes orphaned nodes from prior runs.

### Common Flags

```bash
# Auto-detect language (default) or specify explicitly
cw9 ingest /path/to/codebase . --lang python

# Re-ingest only files that changed since last run
cw9 ingest /path/to/codebase . --incremental

# Limit to the first N functions (useful for testing)
cw9 ingest /path/to/codebase . --max-functions 50

# Get machine-readable JSON output
cw9 ingest /path/to/codebase . --json
```

### What Gets Stored

Each function becomes a record in `crawl.db` with a **deterministic UUID** derived from `uuid5(CRAWL_NAMESPACE, "file_path::class_name::function_name")`. This UUID is stable across re-ingests -- the same function at the same path always gets the same UUID.

The `crawl.db` schema includes:
- **`records`** -- one row per function with UUID, name, file path, line number, file hash, IN:DO:OUT fields, and operational claim
- **`ins`** -- input fields with provenance tracking (parameter, state, literal, internal_call, external)
- **`outs`** -- output fields classified as ok, err, side_effect, or mutation
- **`entry_points`** -- detected entry points (HTTP routes, CLI commands, main functions)
- **`crawl_runs`** -- audit log of each ingest run with timestamps and counters

## Step 3: Run LLM Extraction (DFS Crawl)

After the skeleton pre-pass, records contain signatures but no behavioral data. Run the DFS crawl to invoke Claude for each function and fill in the IN:DO:OUT fields:

```bash
cw9 crawl /path/to/your/project
```

This automatically starts from entry points discovered during ingest (HTTP routes, CLI commands, `main()` functions). If none were stored, it falls back to extracting all skeleton-only records.

### Common Flags

```bash
# Specify entry points manually (repeatable)
cw9 crawl . --entry handle_request --entry main

# Skip already-extracted records whose files haven't changed
cw9 crawl . --incremental

# Limit to N functions (useful for testing or cost control)
cw9 crawl . --max-functions 50

# Use a different Claude model
cw9 crawl . --model claude-sonnet-4-6

# Get machine-readable JSON output
cw9 crawl . --json
```

### Python API (Advanced)

For custom extract functions (e.g., using a different LLM or adding post-processing), use the orchestrator directly:

```python
from registry.crawl_orchestrator import CrawlOrchestrator
from registry.crawl_store import CrawlStore

with CrawlStore(project_path / ".cw9" / "crawl.db") as store:
    orch = CrawlOrchestrator(
        store=store,
        entry_points=["handle_request", "main"],  # function names to start from
        extract_fn=your_llm_extract_function,      # (skeleton, body) -> FnRecord
        max_functions=100,                         # optional cap
        incremental=True,                          # skip unchanged files
    )
    result = orch.run()
    print(f"Extracted: {result['extracted']}, Failed: {result['failed']}, "
          f"Skipped: {result['skipped']}, AX records: {result['ax_records']}")
```

### How the DFS Works

1. The orchestrator resolves each entry point name to a UUID in `crawl.db`.
2. For each entry point, it calls `extract_fn(skeleton, body)` to get a full `FnRecord` with IN:DO:OUT data.
3. When the LLM identifies an `internal_call` input (e.g., function A calls function B), the orchestrator follows that edge and extracts function B next -- depth-first.
4. When the LLM identifies an `external` input (e.g., calling `redis.get()`), the orchestrator creates an `AxRecord` boundary stub and does not traverse further.
5. A visited set prevents cycles -- each function is extracted at most once.

### Retry Behavior

If `extract_fn` raises an exception, the orchestrator retries up to 3 times, passing the error message back as `error_feedback` on subsequent attempts. After 3 failures, an `EXTRACTION_FAILED` stub is stored so the crawl can continue.

### The `extract_fn` Interface

The function you provide must accept these arguments and return an `FnRecord`:

```python
def extract_fn(
    skeleton: Skeleton,        # function signature from the pre-pass
    body: str,                 # function body text read from disk
    error_feedback: str = None # error from previous attempt (retries only)
) -> FnRecord:
    ...
```

## Step 4: Check for Stale Records

When source files change after an ingest, detect which records need re-extraction:

```bash
cw9 stale /path/to/your/project
```

This computes SHA-256 hashes of all source files referenced in `crawl.db` and compares them against stored hashes. Staleness propagates transitively -- if function A calls function B and B's file changed, both A and B are marked stale.

Example output:

```
3 stale record(s) (1 directly changed):
  validate_input @ src/validators.py [direct]
  handle_request @ src/handlers.py [transitive]
  process_order @ src/orders.py [transitive]
```

After fixing stale records, re-run ingest with `--incremental` to update only the changed functions.

## Step 5: Inspect IN:DO:OUT Cards

View the behavioral card for any function by UUID:

```bash
cw9 show <uuid> /path/to/your/project --card
```

This renders a markdown IN:DO:OUT card showing:

```
### validate_input (InputValidator) @ src/validators.py:42
**Claim:** Validates user input and returns sanitized data or error

**IN:**
- data: dict (parameter)
- schema: Schema (parameter)
- config: Config (internal_call) [from get_config @ src/config.py]

**DO:** Validates input data against schema
1. Check required fields are present
2. Validate field types against schema
3. Sanitize string fields

**OUT:**
- ok: SanitizedInput -- validated and sanitized input data
- err: ValidationError -- validation failure details

**FAILURE MODES:** missing required field; type mismatch; malformed input
```

## Step 6: Author GWT Specifications

After ingesting a codebase, use `cw9 gwt-author` to generate GWT (Given-When-Then) specifications that reference ingested functions by UUID:

```bash
cw9 gwt-author --research research-notes.md /path/to/your/project
```

### How It Works

1. **Mention Extraction** -- Scans your research notes for function name mentions (e.g., `get_user()`) and file path mentions (e.g., `src/handlers/user.py`).
2. **Card Query** -- Looks up matching records in `crawl.db` and pulls their transitive dependency subgraphs.
3. **Prompt Construction** -- Builds an LLM prompt containing your research notes alongside the relevant IN:DO:OUT cards with their UUIDs.
4. **Response Parsing** -- Parses the LLM's JSON response into a register-compatible payload.
5. **UUID Validation** -- Verifies that all `depends_on` UUIDs reference real records in `crawl.db`, removing any invalid ones.

### Writing Research Notes

Your research notes file should mention the functions and files you want to modify. The mention extractor looks for:

- **Function names** followed by `()` -- e.g., `get_user()`, `validate_input()`
- **File paths** with recognized extensions -- e.g., `src/handlers/user.py`, `pkg/service.go`

Example research notes:

```markdown
# Add Admin Role Check

We need to modify get_user() in src/handlers/user.py to check
whether the requesting user has admin privileges before returning
sensitive fields. The validate_permissions() function in
src/auth/permissions.py already has the role checking logic.
```

### Piping to Register

The output of `gwt-author` is a JSON payload compatible with `cw9 register`:

```bash
cw9 gwt-author --research notes.md . | cw9 register .
```

The register step creates GWT nodes in the DAG with `DEPENDS_ON` edges pointing to the crawled function UUIDs. This connects the behavioral specification to the actual code it targets.

## Step 7: Run the Pipeline with Brownfield Context

Once you have ingested code and registered GWTs with `depends_on` references, run the pipeline with `--skip-setup` to bypass CW7 database extraction (since your specs came from the brownfield walker instead):

```bash
cw9 pipeline --skip-setup --gwt crawl-gwt-001 /path/to/your/project
```

The `--skip-setup` flag skips the `init`, `extract`, and CW7 database steps, jumping directly to GWT resolution and the LLM verification loop. The pipeline's `query_context()` function loads IN:DO:OUT cards from `crawl.db` for any `RESOURCE` nodes in the GWT's transitive dependency graph, providing the LLM with behavioral context about the existing code.

## Complete Workflow Example

```bash
# 1. Initialize CW9 project
cw9 init myproject

# 2. Ingest the external codebase (language is auto-detected)
cw9 ingest /path/to/external/repo myproject

# 3. Run DFS LLM extraction to fill IN:DO:OUT cards
cw9 crawl myproject

# 4. Check what's stale after source changes
cw9 stale myproject

# 5. Re-ingest only changed files, then re-crawl incrementally
cw9 ingest /path/to/external/repo myproject --incremental
cw9 crawl myproject --incremental

# 6. Inspect a specific function's card
cw9 show <uuid> myproject --card

# 7. Author GWTs from research notes
cw9 gwt-author --research research.md myproject > gwts.json

# 8. Register the GWTs into the DAG
cat gwts.json | cw9 register myproject

# 9. Run the pipeline for a specific GWT
cw9 pipeline --skip-setup --gwt crawl-gwt-001 myproject
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `python/registry/scanner_python.py` | Python skeleton scanner |
| `python/registry/scanner_javascript.py` | JavaScript/JSX skeleton scanner |
| `python/registry/scanner_typescript.py` | TypeScript/TSX skeleton scanner |
| `python/registry/scanner_go.py` | Go skeleton scanner |
| `python/registry/scanner_rust.py` | Rust skeleton scanner |
| `python/registry/crawl_types.py` | Data models: Skeleton, FnRecord, AxRecord, InField, OutField |
| `python/registry/crawl_store.py` | SQLite store for crawl.db (all CRUD, staleness, subgraph queries) |
| `python/registry/crawl_bridge.py` | Bridge from crawl.db records to DAG RESOURCE nodes |
| `python/registry/crawl_orchestrator.py` | DFS crawl orchestrator (LLM extraction) |
| `python/registry/gwt_author.py` | Research notes -> GWT specification authoring |
| `python/registry/entry_points.py` | Entry point and codebase type detection (all languages) |
| `python/registry/cli.py` | CLI command implementations (ingest, crawl, stale, show, gwt-author) |
| `python/registry/one_shot_loop.py` | Pipeline loop with crawl.db card loading via query_context() |
