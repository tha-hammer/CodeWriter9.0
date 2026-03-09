# Implement Plan with Checkpoints

You are tasked with implementing an approved technical plan from `thoughts/searchable/shared/plans/`. These plans contain phases with specific changes and success criteria. This enhanced version includes checkpoint management for better progress tracking and recovery.
Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.
## Getting Started

When given a plan path:
- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket (if a ticket is provided) and/or original research and planning document and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Think from a Test Driven Development perspective
- Create a todo list to track your progress
- **Update beads issue status**: If there's a tracked beads issue, run `bd update <id> --status=in_progress`
- **Create a checkpoint** before starting implementation
- Start implementing if you understand what needs to be done

If no plan path provided, ask for one.

## Checkpoint System

### Creating Checkpoints
Before starting implementation work:
```bash
# Create a checkpoint for the current phase
`silmari-oracle checkpoint create "phase_1_initial_setup" "Starting Phase 1: Initial setup and configuration"`
```

### Checkpoint Management
- **Pre-phase checkpoints**: Create before starting each major phase
- **Post-phase checkpoints**: Create after completing verification of each phase
- **Recovery checkpoints**: Create when encountering issues or making significant discoveries
- **Commit checkpoints**: Create before committing changes

### Checkpoint Naming Convention
- `phase_N_description` for phase boundaries
- `recovery_issue_description` for recovery points
- `commit_feature_name` for commit boundaries
- `discovery_finding_name` for significant discoveries

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:
- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- Update checkboxes in the plan as you complete section
- **ALWAYS USE TDD** Write tests - RED GREEN REFACTOR
- **USE ACTUAL DATA** When available, use actual data
- **USE ACTAL LLMs** When testing LLM calls ALWAYS use actual LLM calls unless explicitly told otherwise
- **USE BAML** If any structured or deterministic output is needed YOU MUST USE BAML
- **Create checkpoints at natural stopping points**

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgment matters too.

If you encounter a mismatch:
- **Create a recovery checkpoint** before proceeding
- STOP and think deeply about why the plan can't be followed
- Present the issue clearly:
  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]

  How should I proceed?
  ```

## Verification Approach

After implementing a phase:
- **Create a post-phase checkpoint**
- Run the success criteria checks (usually `make check test` covers everything)
- Fix any issues before proceeding
- Update your progress in both the plan and your todos
- Check off completed items in the plan file itself using Edit
- **Create a commit checkpoint** if ready to commit

Don't let verification interrupt your flow - batch it at natural stopping points.

## Checkpoint-Integrated Workflow

### Phase Implementation Cycle
1. **Pre-phase checkpoint**: `silmari-oracle checkpoint create "phase_N_start" "Starting Phase N: [description]"`
2. Implement phase changes
3. **Post-phase checkpoint**: `silmari-oracle checkpoint create "phase_N_complete" "Completed Phase N: [description]"`
4. Run verification tests
5. **Recovery checkpoint** (if issues found): `silmari-oracle checkpoint create "phase_N_recovery" "Recovery point for Phase N issues"`
6. Fix issues and repeat verification
7. Update plan checkboxes
8. **Commit checkpoint** (if ready): `silmari-oracle checkpoint create "commit_phase_N" "Ready to commit Phase N changes"`

### Recovery and Resumption
- Use `silmari-oracle checkpoint list` to see available recovery points
- Use `silmari-oracle checkpoint restore <checkpoint_name>` to restore to a specific point
- Checkpoints preserve both code state and plan progress

## If You Get Stuck

When something isn't working as expected:
- **Create a recovery checkpoint** immediately
- First, make sure you've read and understood all the relevant code
- Second, make sure your test was properly constructed, verify props, data model, data shapes
- Consider if the codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance

Use sub-tasks sparingly - mainly for targeted debugging or exploring unfamiliar territory.

## Resuming Work

If the plan has existing checkmarks:
- **Check available checkpoints** with `silmari-oracle checkpoint list`
- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off
- **Restore to appropriate checkpoint** if needed
- **ALWAYS USE TDD** Write tests - RED GREEN REFACTOR
- **USE ACTUAL DATA** When available, use actual data
- **USE ACTAL LLMs** When testing LLM calls ALWAYS use actual LLM calls unless explicitly told otherwise
- **USE BAML** If any structured or deterministic output is needed YOU MUST USE BAML

## Commit Integration

When ready to commit:
1. **Create commit checkpoint**: `silmari-oracle checkpoint create "commit_ready" "Ready to commit changes"`
2. Follow the commit process from `.claude/commands/commit.md`
3. **Create post-commit checkpoint**: `silmari-oracle checkpoint create "commit_complete" "Successfully committed changes"`

## Checkpoint Commands Reference

```bash
# Create a checkpoint
silmari-oracle checkpoint create <name> <description>

# List all checkpoints
silmari-oracle checkpoint list

# Restore to a checkpoint
silmari-oracle checkpoint restore <checkpoint_name>

# Clean up old checkpoints
silmari-oracle checkpoint cleanup [--keep-recent N]
```

Remember: You're implementing a solution with proper checkpoint management, not just checking boxes. Keep the end goal in mind, maintain forward momentum, and use checkpoints to ensure you can always recover and resume work effectively.

## Beads Integration

When implementation is complete:
1. **Sync beads**: Run `bd dolt push and bd dolt pull` to commit any beads changes
2. **Close the issue**: If all work is done, run `bd close <id>`
3. **Update dependencies**: If this unblocks other work, check `bd blocked` to see what's now ready
