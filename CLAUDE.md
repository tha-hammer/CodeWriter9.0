# CLAUDE.md — CW9 Development Process

## What This Project Is

CodeWriter9.0 is a registry-driven pipeline for verified code generation using TLA+/PlusCal formal methods. The core principle: **every component earns the right to exist by being formally specified and verified before implementation.** See `BOOTSTRAP.md` for the full architecture.

## The Bootstrap Methodology (Mandatory)

All changes to CW9 code **must** follow the bootstrap pipeline. This is not optional.

### The Pipeline

```
1. Register GWT behaviors    →  cw9 register (or extractor.py self-describe)
2. Generate TLA+ spec        →  cw9 loop (LLM → PlusCal → TLC verify)
3. Extract bridge artifacts   →  cw9 bridge (mechanical translation)
4. Generate tests             →  cw9 gen-tests (LLM-in-the-loop)
5. Implement to pass tests    →  code comes LAST
```

### When Full Pipeline Is Required

- **Any new feature** added to `python/registry/`
- **Any behavioral change** to existing modules (new code paths, changed invariants)
- **Any new CLI command** added to `cli.py`
- **Any new module** (scanner, language profile, store, etc.)

### When Pipeline May Be Skipped

- Pure refactoring that preserves all existing behavior (rename, extract method, move file)
- Bug fixes where the fix is mechanical and existing tests cover the behavior
- Documentation-only changes
- Test-only changes (adding tests to already-verified code)
- Configuration changes (pyproject.toml, config.toml)

**When in doubt, use the pipeline.** The cost of unnecessary verification is low. The cost of unverified code is technical debt that compounds.

### Single Piece Flow

For each new feature or behavioral change:

```bash
# 1. Register the behavior
echo '{"requirements": [...], "gwts": [...]}' | cw9 register

# 2. Run the verification loop
cw9 loop <gwt-id> --context-file .cw9/context/<gwt-id>.md

# 3. Extract bridge artifacts from verified spec
cw9 bridge .cw9/specs/<gwt-id>.tla --gwt <gwt-id>

# 4. Generate tests from bridge artifacts
cw9 gen-tests <gwt-id> --lang python

# 5. Implement to pass the generated tests
# Code comes LAST — tests define the contract
```

## Key Architecture Rules

1. **DAG is a graph, not a document store.** Spec content stays on disk. Never stuff documents into `Node.description`.
2. **Conform-or-die.** New behaviors must conform to existing verified specs. If your new code can't satisfy an existing spec, your code is wrong, not the spec.
3. **Monotonic growth.** Nodes are never deleted, only superseded.
4. **LLM writes PlusCal only.** The system composes TLA+. Never hand-write TLA+ specs.
5. **Bridge is mechanical.** Bridge translators are deterministic — no LLM involved.
6. **Tests are generated, not hand-written** (for pipeline-verified features). Hand-written tests are only for the pipeline infrastructure itself.
7. **`--context-file` is the designed channel** for supplementary LLM context. Context lives at `.cw9/context/<criterion_id>.md`.
8. **Separate commands per pipeline step.** Each is independently re-runnable. Never bundle steps.
9. **Pipeline is sequential per GWT.** dag.json is not safe for concurrent writes. Max 3-4 concurrent `cw9 loop` or `cw9 gen-tests` processes — more exhausts /tmp and causes silent Java failures.
10. **TLA+ module name MUST match filename** (TLC constraint).
11. **Context files MUST include a Test Interface section.** Concrete import paths, constructor calls, attribute access patterns, and one working test snippet. Without this, `cw9 gen-tests` hallucinates wrong APIs ~60% of the time. See BOOTSTRAP.md "Context File Template".

## Tech Stack

- Python 3.13 — use `python3` not `python`
- pytest for testing — `cd python && python3 -m pytest tests/`
- Java 21 required for TLA+ tools (`tools/tla2tools.jar`)
- PlusCal compile: `java -cp tools/tla2tools.jar pcal.trans <file>.tla`
- TLC verify: `java -XX:+UseParallelGC -cp tools/tla2tools.jar tlc2.TLC <file>.tla -config <file>.cfg -workers auto -nowarning`
- Issue tracking: `bd` (beads) — see AGENTS.md

## Key Paths

| What | Where |
|---|---|
| Python package | `python/registry/` |
| CLI entry point | `python/registry/cli.py` → `cw9` command |
| Core DAG engine | `python/registry/dag.py` |
| Schema extractor | `python/registry/extractor.py` |
| TLA+ templates | `templates/pluscal/` (4 base templates) |
| TLA+ instances | `templates/pluscal/instances/` (verified specs) |
| Generated tests | `python/tests/generated/` |
| Bridge artifacts | `python/tests/generated/*_bridge_artifacts.json` |
| Schema files | `.cw9/schema/*.json` (or `schema/*.json` for self-hosting) |
| Project config | `.cw9/config.toml` |
| DAG state | `dag.json` (self-hosting) or `.cw9/dag.json` (external) |
| Crawl database | `.cw9/crawl.db` |

## Development Checklist

Before submitting any code change, verify:

- [ ] GWT behaviors registered for any new/changed behavior
- [ ] Context file written with Test Interface + Anti-Patterns sections
- [ ] TLA+ spec generated and TLC-verified (0 violations)
- [ ] Bridge artifacts extracted from verified spec
- [ ] Tests generated from bridge artifacts
- [ ] Generated tests PASS (not just "exist" — verify with pytest)
- [ ] `python3 -m pytest python/tests/` — all tests pass
- [ ] No hand-written specs (LLM generates PlusCal via `cw9 loop`)
- [ ] No hand-written tests for pipeline features (use `cw9 gen-tests`)
- [ ] DAG updated (`cw9 extract` if schema changed)
- [ ] BOOTSTRAP.md updated if new phase/capability added

## GWT ID Namespaces

CW9 has two separate DAG contexts with independent GWT ID spaces:

### Self-Hosting DAG (`schema/self_hosting.json` + `resource_registry.generic.json`)

| Range | Owner |
|---|---|
| gwt-0001..0004 | Registry CRUD (Phase 0) |
| gwt-0005..0007 | One-shot loop (Phase 3) |
| gwt-0008..0011 | Bridge (Phase 4) |
| gwt-0012..0014 | Impact analysis (Phase 5) |
| gwt-0015..0017 | Dependency validation (Phase 6) |
| gwt-0018..0020 | Subgraph extraction (Phase 7) |
| gwt-0021..0023 | Change propagation (Phase 8) |
| gwt-0024..0027 | CrawlStore verification (Batch 1) |
| gwt-0028..0031 | CrawlOrchestrator verification (Batch 1) |
| gwt-0032..0035 | CLI Pipeline verification (Batch 1) |
| gwt-0036..0038 | ProjectContext verification (Batch 2) |
| gwt-0039..0041 | LLM Integration verification (Batch 2) |
| gwt-0042..0043 | CW7 Bridge verification (Batch 2) |
| gwt-0044..0045 | Crawl Bridge verification (Batch 2) |
| gwt-0046..0055 | Scanner verification (Batch 3) |
| gwt-0056..0063 | Language Profile verification (Batch 3) |
| gwt-0064..0067 | Observability cross-cutting verification |
| gwt-0068..0072 | Observability cross-cutting enforcement |
| gwt-0073 | Entry point dispatch (remove non-Python gate) |
| gwt-0074 | JS/TS entry point discovery |
| gwt-0075 | Go entry point discovery |
| gwt-0076 | Rust entry point discovery |
| gwt-0077+ | Available for new features |

### Crawl DAG (repo root `dag.json`)

| Range | Owner |
|---|---|
| gwt-0001..0028 | Crawl pipeline behaviors (concurrent extraction, sweep, orchestration) |
| gwt-0029+ | Available for new crawl behaviors |

**Concurrent write safety:** If multiple impl LLMs are active, only ONE may run `cw9 register` at a time. The second must wait until the first's registrations are committed. See AGENTS.md.

**IDs collide between contexts.** Self-hosting gwt-0015 = "valid_edge_accepted". Crawl gwt-0015 = "asyncio_gather error isolation". Always check which DAG you're operating on. See `BOOTSTRAP.md` "Dual DAG Contexts" section.

## Common Workflows

### Adding a new feature to the DAG engine (dag.py)

```bash
# Register the GWT
echo '{"requirements": [{"id": "REQ-NEW", "text": "..."}], "gwts": [{"criterion_id": "GWT-NEW", "given": "...", "when": "...", "then": "..."}]}' | cw9 register

# Write context file (MUST include Test Interface section — see BOOTSTRAP.md template)
mkdir -p .cw9/context
cat > .cw9/context/GWT-NEW.md << 'EOF'
# Context for GWT-NEW
## Behavior
Given ..., when ..., then ...
## Concrete Data Shapes
<dataclass definitions with field types>
## Key Invariants to Model
- InvariantName: description
## Test Interface (MANDATORY)
from registry.module import function
result = function(arg)
assert result.field == expected
## Anti-Patterns (DO NOT USE)
- common mistakes for this module
EOF

# Run verification loop
cw9 loop GWT-NEW --context-file .cw9/context/GWT-NEW.md

# Bridge + test gen
cw9 bridge .cw9/specs/GWT-NEW.tla --gwt GWT-NEW
cw9 gen-tests GWT-NEW --lang python

# Now implement
```

### Adding a new scanner or language profile

Same pipeline. The scanner's behavior is a GWT. Register it, verify it, generate tests, then implement.

### Fixing a bug

If existing tests cover the behavior: fix directly, no pipeline needed.
If the bug reveals a missing behavioral spec: register GWT first, then fix.

### Running all tests

```bash
cd /home/maceo/Dev/CodeWriter9.0/python
python3 -m pytest tests/ -x
```
