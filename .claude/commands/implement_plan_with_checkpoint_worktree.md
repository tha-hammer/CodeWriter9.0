# Implement Plan with Checkpoint Worktree

You are tasked with implementing an approved technical plan from `thoughts/searchable/shared/plans/` in a dedicated worktree. These plans contain phases with specific changes and success criteria.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Getting Started

When given a plan path:
- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Create a todo list to track your progress
- **Update beads issue status**: If there's a tracked beads issue, run `bd update <id> --status=in_progress`
- Start implementing if you understand what needs to be done

If no plan path provided, ask for one.

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:
- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- Update checkboxes in the plan as you complete sections

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgment matters too.

If you encounter a mismatch:
- STOP and think deeply about why the plan can't be followed
- Present the issue clearly:
  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]

  How should I proceed?
  ```

## Checkpoint Strategy (CRITICAL)

This is a worktree environment designed for safe experimentation. Use git checkpoints frequently:

**Checkpoint After:**
- Completing each phase or major section
- Before attempting risky refactors
- After fixing a complex bug
- When tests pass for a logical unit of work
- Before context window resets

**Checkpoint Commands:**
```bash
git add -A
git commit -m "checkpoint: [brief description of what was done]"
git push
```

**Why Checkpoints Matter:**
- Worktrees allow safe exploration without affecting main branch
- Git push ensures work survives context resets
- Checkpoints create resume points if something breaks
- They document your progress through the implementation

**Do NOT wait until everything is perfect** - checkpoint working progress frequently!

## Verification Approach

After implementing a phase:
- Run the success criteria checks (usually `make check test` covers everything)
- Fix any issues before proceeding
- Update your progress in both the plan and your todos
- Check off completed items in the plan file itself using Edit
- **Create a checkpoint commit** after successful verification

Don't let verification interrupt your flow - batch it at natural stopping points.

## If You Get Stuck

When something isn't working as expected:
- First, make sure you've read and understood all the relevant code
- Consider if the codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance
- **Create a checkpoint** before attempting alternative approaches

Use sub-tasks sparingly - mainly for targeted debugging or exploring unfamiliar territory.

## Resuming Work

If the plan has existing checkmarks:
- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off

Check git log to see what checkpoints exist:
```bash
git log --oneline -10
```

## Virtual Environment

The worktree should have a virtual environment set up. If you need to run Python commands:
- Check for venv activation instructions from the setup output
- Usually: `source venv/bin/activate` (in worktree) or `source ../venv/bin/activate` (parent dir)
- The setup script should have handled this, but verify if you encounter import errors

## Final Steps

When implementation is complete and all tests pass:
1. Create a final checkpoint: `git commit -m "feat: [descriptive summary]"`
2. Read `.claude/commands/commit.md` (or `.cursor/commands/commit.md`) and create a proper commit
3. Push your changes: `git push`
4. Read `.claude/commands/describe_pr.md` and create a PR
5. Link the PR in the Linear ticket

Remember: You're implementing a solution in a safe worktree environment. Checkpoint often, maintain forward momentum, and keep the end goal in mind.

## Beads Integration

When implementation is complete:
1. **Sync beads**: Run `bd dolt push and bd dolt pull` to commit any beads changes
2. **Close the issue**: If all work is done, run `bd close <id>`
3. **Update dependencies**: If this unblocks other work, check `bd blocked` to see what's now ready
