---
date: 2026-03-25T00:00:00Z
researcher: FuchsiaRaven
git_commit: 27765af
branch: master
repository: CodeWriter9.0
topic: "cw9 plan-review orchestrator via Claude Agent SDK"
tags: [research, cw9, orchestrator, agent-sdk, plan-review]
status: complete
last_updated: 2026-03-25
last_updated_by: FuchsiaRaven
cw9_project: /home/maceo/Dev/CodeWriter9.0
---

# Research: `cw9 plan-review` Orchestrator

## Research Question

Build a `cw9 plan-review --self|--external <plan-path>` CLI command that orchestrates the 5 decomposed review passes using the Claude Agent SDK, providing both terminal-based streaming output and machine-readable JSON results.

## Existing Infrastructure

### CLI Structure (`python/registry/cli.py`)

- Framework: `argparse` with manual dispatch table (`_DISPATCH` dict at line 2113)
- Pattern: `_add_*_commands(sub)` helpers register parsers, `cmd_*` functions handle dispatch
- Precedent: `cmd_pipeline` (line 617) already orchestrates multiple steps — calls `_run_loop_core()` and `_run_bridge_core()` in sequence, and re-enters `main()` for init/extract
- Adding a command requires: (1) `cmd_plan_review()` function, (2) parser in an `_add_*_commands()` helper, (3) entry in `_DISPATCH`

### Review Command Files

**Self-Hosting** (`.claude/commands/`):
| # | File | Lines | Purpose | Pre-impl? |
|---|---|---|---|---|
| 1 | `cw9_review_01_artifacts.md` | 159 | Artifact existence + status gate | Yes |
| 2 | `cw9_review_02_coverage.md` | 191 | Verifier/trace/invariant coverage | Yes |
| 3 | `cw9_review_03_abstraction_gap.md` | 246 | Decision checklist for unspecified choices | Yes |
| 4 | `cw9_review_04_interaction.md` | 173 | DAG/module conflict (self-hosting only) | Yes |
| 5 | `cw9_review_05_imports.md` | 232 | Dead import/wrong abstraction audit | Post-impl |

**External** (`~/.claude/commands/`):
| # | File | Lines | Purpose | Pre-impl? |
|---|---|---|---|---|
| 1 | `cw9_review_01_artifacts.md` | 182 | Artifact existence + UUID validity | Yes |
| 2 | `cw9_review_02_coverage.md` | 189 | Same as self-hosting | Yes |
| 3 | `cw9_review_03_abstraction_gap.md` | 296 | Multi-language export/gap analysis | Yes |
| 4 | `cw9_review_04_imports.md` | 287 | Multi-language import audit | Post-impl |

Key differences:
- External has no interaction review (no existing GWT corpus to conflict with)
- External reviews 3 and 4 are longer — cover Python/JS/TS/Go/Rust patterns
- External uses `.cw9/` paths; self-hosting uses repo-root paths
- External artifacts review adds crawl.db UUID validity check

### Claude Agent SDK (installed: v0.1.48)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from claude_agent_sdk.types import StreamEvent
```

Key constraints:
- **Streaming and structured output are mutually exclusive** — can't get both from one `query()` call
- `query()` yields `StreamEvent` (with `include_partial_messages=True`), `AssistantMessage`, and `ResultMessage`
- `ResultMessage` has `.result` (text), `.structured_output` (JSON), `.session_id`, `.total_cost_usd`
- For parallel sessions: `asyncio.gather` with independent `query()` calls

## SDK API Choice: `query()` vs `ClaudeSDKClient`

### Decision: `query()` (independent calls)

The review passes don't benefit from shared session context. Each review command is a
self-contained prompt that reads artifacts from disk (specs, bridge JSON, crawl.db) and
writes reports to disk (`thoughts/searchable/shared/plans/`). The inter-pass communication
channel is the filesystem, not conversation history.

### Comparison

| Concern | `query()` | `ClaudeSDKClient` |
|---|---|---|
| Parallel passes (coverage + interaction) | `asyncio.gather` on independent calls | Can't parallelize turns in one session; need multiple clients anyway |
| Gate logic (artifacts must pass first) | Simple: check result, skip remaining | Same complexity |
| Error recovery | Re-run one `query()` call | Must manage session state, decide whether to resume or start fresh |
| Cost tracking | Each `ResultMessage.total_cost_usd`, sum them | Same, but replay of session history on each turn adds cost |
| Context window bloat | Each pass gets a clean window | Later passes carry ~800 lines of prior prompt history that isn't useful |

### Why not `ClaudeSDKClient`?

`ClaudeSDKClient` shines when later turns need conversational context from earlier turns.
Here, the "context" between passes is the report files written to disk — not conversation
state. The abstraction gap review reads the coverage report *file*, not the coverage
review's conversation. Carrying dead session context would bloat the window and add replay
cost with no benefit.

### Why not `fork_session`?

Forking from the artifacts session into parallel coverage + interaction branches is
architecturally elegant but practically wasteful. The artifacts pass produces a report file
(the gate verdict), not conversational findings that the parallel passes need in-context.
The forked sessions would carry artifacts' tool calls and reasoning as dead weight.

### Why not subagents (`AgentDefinition`)?

Subagents delegate execution-order decisions to the LLM. We know the dependency graph
statically (artifacts gates everything, coverage || interaction, then abstraction gap).
Letting an LLM discover this ordering is unnecessary indirection that costs tokens and
introduces non-determinism in execution order.

### SDK Capabilities Reference

| Feature | `query()` | `ClaudeSDKClient` |
|---|---|---|
| Session resumption | `resume=session_id` | Automatic across `.query()` calls |
| Session forking | `fork_session=True` | Not documented |
| Streaming output | `include_partial_messages=True` | `include_partial_messages=True` |
| Structured output | `output_format={...}` | `output_format={...}` |
| Streaming + structured | **Mutually exclusive** | **Mutually exclusive** |
| Parallel execution | `asyncio.gather` on independent calls | Multiple client instances |
| Cost tracking | `ResultMessage.total_cost_usd` per call | Same, per `.query()` turn |
| Session persistence | Always to disk (`~/.claude/projects/`) | Always to disk |
| Custom tools/hooks | Not available | Available |
| Mid-session model change | Not available | `set_model()` |

## Proposed Design

### CLI Interface

```
cw9 plan-review <plan-path> [--self|--external] [--json] [--skip-imports] [--phase pre|post|all]
```

- `--self` / `--external`: selects which command file set to use (default: auto-detect from `.cw9/` presence)
- `--json`: machine-readable JSON output to stdout (suppresses terminal streaming)
- `--skip-imports`: skip the post-impl imports review (useful when running pre-impl only)
- `--phase pre|post|all`: `pre` runs 1-4 (or 1-3 for external), `post` runs imports only, `all` runs everything

### Execution Flow

```
┌─────────────────────────────┐
│   1. Artifacts (gate)       │  ← Must pass before anything else
└─────────────┬───────────────┘
              │ pass?
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
┌──────────┐   ┌──────────────┐   ┌──────────────┐
│ Coverage │   │ Interaction  │   │    (skip if   │
│   (2)    │   │   (4, self   │   │   external)   │
│          │   │   only)      │   │               │
└────┬─────┘   └──────┬───────┘   └───────────────┘
     │                │
     └───────┬────────┘
             ▼
┌─────────────────────────────┐
│  3. Abstraction Gap         │  ← Benefits from 2+4 findings
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  5/4. Imports (post-impl)   │  ← Only if --phase=post or all
└─────────────────────────────┘
```

### Implementation: `cmd_plan_review()`

```python
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from claude_agent_sdk.types import StreamEvent


# Review pass definition
SELF_REVIEWS = [
    ("artifacts",       ".claude/commands/cw9_review_01_artifacts.md"),
    ("coverage",        ".claude/commands/cw9_review_02_coverage.md"),
    ("abstraction_gap", ".claude/commands/cw9_review_03_abstraction_gap.md"),
    ("interaction",     ".claude/commands/cw9_review_04_interaction.md"),
    ("imports",         ".claude/commands/cw9_review_05_imports.md"),
]

EXTERNAL_REVIEWS = [
    ("artifacts",       "~/.claude/commands/cw9_review_01_artifacts.md"),
    ("coverage",        "~/.claude/commands/cw9_review_02_coverage.md"),
    ("abstraction_gap", "~/.claude/commands/cw9_review_03_abstraction_gap.md"),
    ("imports",         "~/.claude/commands/cw9_review_04_imports.md"),
]


async def _run_review_pass(
    name: str,
    prompt_file: Path,
    plan_path: str,
    cwd: str,
    json_mode: bool,
) -> dict:
    """Run a single review pass via Claude Agent SDK."""
    prompt_text = prompt_file.read_text()
    # The command files expect $ARGUMENTS to be the plan path
    full_prompt = f"{prompt_text}\n\n$ARGUMENTS: {plan_path}"

    result_text = ""
    cost = 0.0
    session_id = ""

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=["Read", "Grep", "Glob", "Bash"],
        permission_mode="acceptEdits",
        include_partial_messages=not json_mode,
    )

    async for msg in query(prompt=full_prompt, options=options):
        if isinstance(msg, StreamEvent) and not json_mode:
            event = msg.event
            etype = event.get("type")
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    sys.stdout.write(delta.get("text", ""))
                    sys.stdout.flush()
        elif isinstance(msg, ResultMessage):
            result_text = msg.result or ""
            cost = msg.total_cost_usd
            session_id = msg.session_id

    # Parse verdict from result text
    verdict = "unknown"
    if "PASS" in result_text.upper():
        verdict = "pass"
    elif "FAIL" in result_text.upper() or "CRITICAL" in result_text.upper():
        verdict = "fail"
    elif "WARNING" in result_text.upper():
        verdict = "warning"

    return {
        "name": name,
        "verdict": verdict,
        "session_id": session_id,
        "cost_usd": cost,
        "result_length": len(result_text),
        "result_text": result_text,
    }


async def _orchestrate_reviews(
    mode: str,
    plan_path: str,
    cwd: str,
    phase: str,
    json_mode: bool,
) -> dict:
    """Run all review passes in dependency order."""
    reviews = SELF_REVIEWS if mode == "self" else EXTERNAL_REVIEWS
    results = {}
    total_cost = 0.0

    # Resolve prompt files
    def resolve(rel_path: str) -> Path:
        if rel_path.startswith("~"):
            return Path(rel_path).expanduser()
        return Path(cwd) / rel_path

    # Phase 1: Artifacts (gate)
    if phase in ("pre", "all"):
        artifacts_file = resolve(dict(reviews)["artifacts"])
        if not json_mode:
            print(f"\n{'='*60}")
            print(f"  REVIEW PASS 1: Artifacts")
            print(f"{'='*60}\n")

        r = await _run_review_pass("artifacts", artifacts_file, plan_path, cwd, json_mode)
        results["artifacts"] = r
        total_cost += r["cost_usd"]

        if r["verdict"] == "fail":
            if not json_mode:
                print(f"\n⛔ Artifacts review FAILED — stopping.")
            return {
                "status": "blocked",
                "blocked_by": "artifacts",
                "results": results,
                "total_cost_usd": total_cost,
            }

        # Phase 2: Parallel passes (coverage + interaction for self, coverage only for external)
        parallel_names = ["coverage"]
        if mode == "self" and "interaction" in dict(reviews):
            parallel_names.append("interaction")

        if not json_mode:
            names_str = " + ".join(parallel_names)
            print(f"\n{'='*60}")
            print(f"  REVIEW PASS 2: {names_str} (parallel)")
            print(f"{'='*60}\n")

        parallel_tasks = []
        for name in parallel_names:
            f = resolve(dict(reviews)[name])
            parallel_tasks.append(
                _run_review_pass(name, f, plan_path, cwd, json_mode)
            )

        parallel_results = await asyncio.gather(*parallel_tasks)
        for pr in parallel_results:
            results[pr["name"]] = pr
            total_cost += pr["cost_usd"]

        # Phase 3: Abstraction Gap (benefits from coverage + interaction)
        if not json_mode:
            print(f"\n{'='*60}")
            print(f"  REVIEW PASS 3: Abstraction Gap")
            print(f"{'='*60}\n")

        gap_file = resolve(dict(reviews)["abstraction_gap"])
        r = await _run_review_pass("abstraction_gap", gap_file, plan_path, cwd, json_mode)
        results["abstraction_gap"] = r
        total_cost += r["cost_usd"]

    # Phase 4: Imports (post-impl only)
    if phase in ("post", "all"):
        imports_key = "imports"
        if imports_key in dict(reviews):
            if not json_mode:
                print(f"\n{'='*60}")
                print(f"  REVIEW PASS 4: Import Audit")
                print(f"{'='*60}\n")

            imports_file = resolve(dict(reviews)[imports_key])
            r = await _run_review_pass(imports_key, imports_file, plan_path, cwd, json_mode)
            results["imports"] = r
            total_cost += r["cost_usd"]

    # Summary
    overall = "pass"
    for name, r in results.items():
        if r["verdict"] == "fail":
            overall = "fail"
            break
        if r["verdict"] == "warning" and overall == "pass":
            overall = "warning"

    return {
        "status": overall,
        "mode": mode,
        "plan_path": plan_path,
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": {k: {kk: vv for kk, vv in v.items() if kk != "result_text"}
                    for k, v in results.items()},
        "total_cost_usd": total_cost,
    }


def cmd_plan_review(args: argparse.Namespace) -> int:
    """Orchestrate cw9 plan-review passes via Claude Agent SDK."""
    plan_path = args.plan_path
    mode = "self" if args.self_hosting else "external"
    phase = args.phase
    json_mode = args.json_output
    cwd = str(Path(args.target_dir).resolve())

    # Auto-detect mode if neither flag given
    if not args.self_hosting and not args.external:
        if (Path(cwd) / ".cw9").is_dir():
            mode = "external"
        else:
            mode = "self"

    summary = asyncio.run(
        _orchestrate_reviews(mode, plan_path, cwd, phase, json_mode)
    )

    if json_mode:
        print(json.dumps(summary, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  SUMMARY: {summary['status'].upper()}")
        print(f"  Total cost: ${summary['total_cost_usd']:.4f}")
        print(f"{'='*60}")
        for name, r in summary["results"].items():
            icon = {"pass": "✓", "fail": "✗", "warning": "⚠", "unknown": "?"}
            print(f"  {icon.get(r['verdict'], '?')} {name}: {r['verdict']}")

    return 0 if summary["status"] != "fail" else 1
```

### Registration in cli.py

Add to `_add_utility_commands()` (line 2099):

```python
p_plan_review = sub.add_parser("plan-review", help="Orchestrate plan review passes")
p_plan_review.add_argument("plan_path", help="Path to CW9 TDD plan")
p_plan_review.add_argument("target_dir", nargs="?", default=".")
p_plan_review.add_argument("--self", dest="self_hosting", action="store_true",
                           help="Use self-hosting review commands")
p_plan_review.add_argument("--external", action="store_true",
                           help="Use external project review commands")
p_plan_review.add_argument("--json", dest="json_output", action="store_true",
                           help="Machine-readable JSON output")
p_plan_review.add_argument("--phase", choices=["pre", "post", "all"], default="all",
                           help="Which review phases to run (default: all)")
```

Add to `_DISPATCH` (line 2114):
```python
"plan-review": cmd_plan_review,
```

## Key Design Decisions

### 1. Read `.md` files directly, don't invoke slash commands

The review commands are `.md` prompt files. The orchestrator reads their content and passes it as the prompt to `query()`. This is more reliable than trying to invoke `/cw9_review_01_artifacts` through the CLI — the Agent SDK doesn't support slash command invocation, and reading the file gives us the exact same prompt text.

### 2. Streaming XOR Structured — handle with `--json` flag

Since the SDK can't do both streaming and structured output in one call, the CLI has two modes:
- Default: streaming terminal output (human watches live), machine-readable summary printed at end
- `--json`: no streaming, just the final JSON summary to stdout

### 3. Verdict parsing is heuristic

Each review command writes a verdict in its report text (PASS/FAIL/WARNING). The orchestrator does simple string matching. If this proves fragile, we could add structured output mode per-pass — but that would require adding JSON schema instructions to each review command, which changes their prompts.

A more robust alternative: define a `ReviewResult` Pydantic model and use `output_format` on the `query()` call. But this means the review prompt must also produce the JSON, which may degrade the review quality. **Recommendation: start with heuristic parsing, upgrade to structured output only if verdict extraction proves unreliable.**

### 4. Artifacts is a hard gate

If artifacts review fails, nothing else runs. This prevents wasting API budget on reviews that will certainly fail (no specs = nothing to check coverage of).

### 5. Coverage and interaction run in parallel

They read different artifacts and don't depend on each other. `asyncio.gather` runs them concurrently, saving wall-clock time.

### 6. `--phase` separates pre-impl from post-impl

The import review runs AFTER implementation. The `--phase pre` flag lets the orchestrator be called at the right pipeline stage:
- After `cw9 loop` + `cw9 bridge`: `cw9 plan-review <plan> --phase pre`
- After `cw9_implement`: `cw9 plan-review <plan> --phase post`
- Full review: `cw9 plan-review <plan> --phase all`

## Machine-Readable Output Schema

```json
{
  "status": "pass|fail|warning|blocked",
  "mode": "self|external",
  "plan_path": "thoughts/searchable/shared/plans/...",
  "phase": "pre|post|all",
  "timestamp": "2026-03-25T12:00:00Z",
  "results": {
    "artifacts": {
      "name": "artifacts",
      "verdict": "pass|fail|warning",
      "session_id": "abc123",
      "cost_usd": 0.0234,
      "result_length": 4521
    },
    "coverage": { ... },
    "interaction": { ... },
    "abstraction_gap": { ... },
    "imports": { ... }
  },
  "total_cost_usd": 0.1234
}
```

## Dependencies

- `claude-agent-sdk >= 0.1.48` (already installed)
- No new external dependencies needed
- Review command `.md` files must exist at their expected paths

## Files to Modify

| File | Change |
|---|---|
| `python/registry/cli.py:2099` | Add `plan-review` parser to `_add_utility_commands()` |
| `python/registry/cli.py:2114` | Add `"plan-review": cmd_plan_review` to `_DISPATCH` |
| `python/registry/cli.py` (new section) | Add `cmd_plan_review()`, `_orchestrate_reviews()`, `_run_review_pass()` |

## CW9 Mention Summary

Functions: cmd_plan_review(), _orchestrate_reviews(), _run_review_pass(), main(), _add_utility_commands()
Files: python/registry/cli.py, .claude/commands/cw9_review_01_artifacts.md, .claude/commands/cw9_review_02_coverage.md, .claude/commands/cw9_review_03_abstraction_gap.md, .claude/commands/cw9_review_04_interaction.md, .claude/commands/cw9_review_05_imports.md
Directories: python/registry/, .claude/commands/
