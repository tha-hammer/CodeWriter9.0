# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Version-controlled: Built on Dolt with cell-level merge
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs with git:

- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->

---

## Multi-Agent Coordination

CW9 development uses up to three concurrent LLM agents. Each has a
distinct responsibility and distinct failure modes.

### Orchestrator (DustyForge)

Reviews plans, catches drift, verifies exit criteria. Does not write
production code. Persists state via MCP agent mail.

**Review protocol (same format every batch):**
1. Verify GWT registrations match the plan (count, IDs, given/when/then quality)
2. Spot-check context files for Test Interface + Anti-Patterns sections
3. After gen-tests: run each test file individually, report pass/fail counts
4. Triage failures into scaffolding vs. spec-reality vs. API mismatch
5. Approve scaffolding fixes; require bridge artifact review for assertion changes
6. Full test suite green before bead closure

### Implementation LLM

Registers GWTs, runs the pipeline, writes code, fixes tests.

**Rules:**
- Follow the pipeline: register → context → loop → bridge → gen-tests → implement
- Context files MUST include Test Interface and Anti-Patterns sections (see BOOTSTRAP.md)
- Do not close beads until tests pass — "artifacts generated" is not "complete"
- Close reasons must be specific to each bead (no copy-paste boilerplate)
- Report to orchestrator before claiming completion
- Max 3-4 concurrent `cw9 loop` or `cw9 gen-tests` processes

### Implementation LLM 2 (when needed)

Parallel worker for independent tasks. Same rules as Impl LLM, plus:

- **MUST NOT run `cw9 register`** while Impl LLM 1 has uncommitted DAG writes
- **MUST NOT modify files** that Impl LLM 1 is actively editing
- Can work on: context file updates, test fixes, documentation, independent features
- Must wait for Impl LLM 1 to commit before touching `self_hosting.json` or `dag.json`

---

## Drift Patterns

Recurring failure modes observed across Batches 1-3. The orchestrator
watches for all of them.

### 1. Premature Bead Closure

Impl LLM closes a bead while tests are still failing, treating
"artifacts generated" as "complete."

**Detection:** Close reason contains hedging ("needs scaffolding fixes",
"tests in progress"). Run tests — if any fail, the bead was closed prematurely.

**Rule:** Beads are closed when tests pass, not when artifacts exist.

### 2. Boilerplate Close Reasons

Impl LLM copies the same close reason across multiple beads that had
different fix profiles.

**Detection:** Compare close reasons across beads in the same batch.
Identical reasons for different modules = copy-paste.

**Rule:** Each close reason must reflect its specific outcome — which
GWTs, how many tests, what scaffolding fixes were needed.

### 3. Fix by Merging

When faced with a "not found" error, impl LLM merges separate DAGs or
data sources instead of routing to the correct one.

**Detection:** New code that combines self-hosting and crawl DAG queries.
Cross-DAG imports where none existed before.

**Rule:** The two DAGs are separate contexts. Query the right one, don't merge.

### 4. Retroactive Alignment

When tasked with removing hardcoded code, impl LLM adds NEW hardcoded
code to make the old hardcoded code work differently.

**Detection:** Diff shows new constants or special-case branches in the
function that was supposed to be simplified.

**Rule:** Removing hardcoded code = data-driven or config-driven, not
replacing one hardcoded approach with another.

### 5. CWD Sensitivity

`cw9` resolves `.` relative to the working directory. Wrong directory
produces confusing "not found" errors.

**Detection:** "GWT not found" or "spec not found" but the files exist.

**Rule:** Verify cwd before running `cw9` commands. Use absolute paths
when in doubt.

---

## Scaffolding Fix Rules

Generated tests frequently need scaffolding fixes — mechanical patches
to import paths, constructor calls, and field access patterns.

### Allowed (no orchestrator review needed)

- Fixing import paths (`from tla_model import X` → `from registry.module import X`)
- Fixing field names (`skeleton.func_name` → `skeleton.function_name`)
- Fixing access patterns (`skeleton["name"]` → `skeleton.name`)
- Fixing argument types (`scan_file("path")` → `scan_file(Path("path"))`)
- Fixing constructor signatures (`Profile(arg)` → `Profile()`)
- Adding missing test helpers or fixtures

### Requires orchestrator review

- Removing test cases entirely
- Changing assertion values or operators
- Weakening invariant checks (e.g., `assert x == 5` → `assert x >= 0`)
- Adding `pytest.mark.skip` or `pytest.mark.xfail`
- Any change where the bridge artifact's verifier condition is modified

**Decision rule:** Check the bridge artifacts JSON. If the fix changes
HOW the test calls the API (scaffolding), it's allowed. If the fix
changes WHAT the test asserts about behavior (weakening), it requires review.

---

## Concurrency Limits

### Pipeline processes

- Max 3-4 concurrent `cw9 loop` processes (Java TLC uses /tmp heavily;
  17+ concurrent processes exhausted a 40GB tmpfs with silent failures)
- Max 3-4 concurrent `cw9 gen-tests` processes (each spawns a Claude subprocess)
- Clean up between batches: `rm -rf /tmp/cw9_* 2>/dev/null`

### DAG writes

- `self_hosting.json` and `dag.json` are NOT safe for concurrent writes
- Only one agent may run `cw9 register` at a time
- Second agent must wait until first agent's registrations are committed to git
- GWT IDs are allocated sequentially — concurrent calls will collide

### Bead operations

- Multiple agents may read beads concurrently (`bd show`, `bd list`)
- Only one agent should update a given bead at a time
- `bd close` is idempotent — safe to retry

---

## Communication

Agents coordinate via MCP agent mail (project key: `/home/maceo/Dev/CodeWriter9.0`).

**Required messages:**
- Session state checkpoint at start and end of each session
- Batch completion report with exit criteria checklist
- Drift detection alerts (reference pattern by number)

**Batch completion format:**
```
Subject: Batch N status — X GWTs, Y tests
Body:
- GWT IDs: gwt-XXXX..gwt-YYYY
- Tests passing: N/M
- Scaffolding fixes applied: list
- Spec-reality mismatches found: list (if any)
- Beads: <bead-id> status
```
