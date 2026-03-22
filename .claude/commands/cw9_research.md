# CW9 Research (Self-Hosting)

Research CW9's own codebase to plan new features or understand existing behavior. This is the self-hosting variant — CW9 researching itself.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for synthesis — don't read entire codebases yourself.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = task description and/or path to existing research. If not provided, ask.

## Self-Hosting Context

CW9 is researching its own code. Key paths:

| What | Where |
|---|---|
| Python package | `python/registry/` |
| CLI entry point | `python/registry/cli.py` |
| Core DAG engine | `python/registry/dag.py` |
| TLA+ templates | `templates/pluscal/` (4 base templates) |
| Verified specs | `templates/pluscal/instances/` |
| Bridge artifacts | `python/tests/generated/*_bridge_artifacts.json` |
| Generated tests | `python/tests/generated/test_gwt_*.py` |
| Context files | `.cw9/context/gwt-*.md` (63 existing) |
| Schema files | `schema/` |
| Self-hosting DAG | `dag.json` (repo root — NOT `.cw9/dag.json`) |
| Sessions | `sessions/` |

**GWT ID namespace**: gwt-0001..0063 are allocated. Next available: **gwt-0064+**. See CLAUDE.md for the full allocation table.

**Dual DAG warning**: The repo has TWO DAGs with colliding ID spaces. `dag.json` (repo root) is the self-hosting DAG. `.cw9/dag.json` would be for an external project. Always confirm which DAG you're operating on.

## Process

### 1. Orient

- Read $ARGUMENTS to understand what the user wants to research or build
- This is self-hosting — you're researching `python/registry/` source files directly
- Check existing context files (`.cw9/context/`) and verified specs (`templates/pluscal/instances/`) for prior art
- No need to `cw9 ingest` or `cw9 crawl` yourself — read the source directly

### 2. Beads Setup

- Run `bd list --status=open` to check for existing tracked issues on this topic
- If none exists: `bd create --title="Research: [topic]" --type=task --priority=2`
- Note the beads ID for later

### 3. Explore

Your research sources, in priority order:

1. **Source files** in `python/registry/` — read the actual code
2. **Existing context files** in `.cw9/context/` — 63 GWTs worth of behavioral documentation
3. **Verified TLA+ specs** in `templates/pluscal/instances/` — formal models of existing behavior
4. **Bridge artifacts** in `python/tests/generated/` — data structures, operations, verifiers
5. **Generated tests** in `python/tests/generated/` — concrete test scenarios
6. **DAG** at `dag.json` — node/edge relationships between GWTs
7. **crawl.db** at `.cw9/crawl.db` (if it exists) — IN:DO:OUT cards from self-crawl

Key modules and what they do:

| Module | Purpose |
|---|---|
| `cli.py` | CLI entry point, all `cw9` subcommands |
| `dag.py` | Registry DAG: nodes, edges, closure, components |
| `context.py` | `ProjectContext` — routes self-hosting vs external paths |
| `extractor.py` | Schema → DAG extraction |
| `one_shot_loop.py` | LLM → PlusCal → compile → TLC verify → route |
| `loop_runner.py` | Orchestrates one_shot_loop with retry |
| `test_gen_loop.py` | Bridge artifacts + sim traces → runnable tests |
| `bridge.py` | Spec → data structures, operations, verifiers |
| `composer.py` | Composes TLA+ specs across connected components |
| `lang.py`, `lang_*.py` | Language profiles (Python/TS/Go/Rust) |
| `crawl_*.py` | Crawl pipeline (store, orchestrator, sweeper) |
| `scanner_*.py` | Language-specific code scanners |

### 4. Write Research Document

Write to: `thoughts/searchable/shared/research/YYYY-MM-DD-description.md`

Use this structure:

```markdown
---
date: [ISO timestamp]
researcher: [name]
git_commit: [hash]
branch: [branch]
repository: CodeWriter9.0
topic: "[topic]"
tags: [research, cw9, self-hosting, relevant-tags]
status: complete
last_updated: [YYYY-MM-DD]
last_updated_by: [name]
---

# Research: [Topic]

## Research Question
[What the user wants to understand or build]

## Existing Coverage
- GWT IDs touching this area: [list]
- Context files: [list paths]
- Verified specs: [list paths]
- Test files: [list paths]

## Key Functions

### functionName()
- **File**: python/registry/module.py:line
- **Role**: [what it does from source reading]
- **Calls**: [internal dependencies]
- **Called by**: [callers]

[Repeat for each key function]

## Call Graph
[How the key functions connect — which calls which, data flow]

## Findings
[What you discovered that's relevant to the user's task]

## Proposed Changes
[What needs to change, referencing specific functions and files]

## GWT Namespace Impact
- Next available GWT ID: gwt-NNNN (check dag.json for latest)
- Estimated new GWTs needed: N
- Affected existing GWTs: [list any that need updating]

## CW9 Mention Summary
Functions: functionName(), otherFunction()
Files: python/registry/relevant_file.py
Directories: python/registry/

Note: The "CW9 Mention Summary" section is formatted for gwt-author extraction.
Function names MUST include () for mention extraction.
```

### 5. Report

Tell the user:
- What you found during exploration (key functions, call patterns, existing behavior)
- Where the research document was written
- Which existing GWTs/specs/context files are relevant
- What to run next: `/cw9_plan <research-doc-path>`

Update beads: `bd update <id> --status=done`

## Guidelines

- **You're inside the codebase.** Read source files directly — don't rely on crawl.db for self-hosting research.
- **Check existing coverage first.** 63 GWTs are already verified. Your new feature may interact with or extend existing specs.
- **Context files are documentation.** The 63 context files in `.cw9/context/` are the best behavioral documentation of each module. Read them.
- **Test with `cd python && python3 -m pytest tests/ -x`** to verify current state.
- The research doc's "CW9 Mention Summary" section is what gwt-author will parse. Functions need `()`, files need extensions, directories need trailing `/`.
- Mentioning ANY file under a directory causes gwt-author to expand to the entire ancestor directory tree.
