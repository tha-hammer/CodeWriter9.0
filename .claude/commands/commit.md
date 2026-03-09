# Commit Changes

You are tasked with creating git commits for the changes made during this session.

## Process:

1. **Think about what changed:**
   - Review the conversation history and understand what was accomplished
   - Run `git status` to see current changes
   - Run `git diff` to understand the modifications
   - Consider whether changes should be one commit or multiple logical commits

2. **Plan your commit(s):**
   - Identify which files belong together
   - Draft clear, descriptive commit messages
   - Use imperative mood in commit messages
   - Focus on why the changes were made, not just what

3. **Present your plan to the user:**
   - List the files you plan to add for each commit
   - Show the commit message(s) you'll use
   - Ask: "I plan to create [N] commit(s) with these changes. Shall I proceed?"

4. **Execute upon confirmation:**
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages
   - Show the result with `git log --oneline -n [number]`

## Important:
- **NEVER add co-author information or Claude attribution**
- Commits should be authored solely by the user
- Do not include any "Generated with Claude" messages
- Do not add "Co-Authored-By" lines
- Write commit messages as if the user wrote them

## Remember:
- You have the full context of what was done in this session
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit

## Beads Integration

After committing changes:
1. **Sync beads**: Run `bd dolt push and bd dolt pull` to ensure any beads changes are committed
2. **Update related issues**: If working on a tracked beads issue, consider:
   - `bd update <id> --status=in_progress` if work is ongoing
   - `bd close <id>` if the commit completes the issue

## Post Commit
1. Review `specs/` and update technical specifications with the latest work
2. If new specification files are created update the `specs/SPECS.md` index file
3. If architechture changed or modified update the `specs/ARCHITECHTURE.md` file   