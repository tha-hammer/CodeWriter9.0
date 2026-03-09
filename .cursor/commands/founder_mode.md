you're working on an experimental feature that didn't get the proper ticketing and pr stuff set up.

assuming you just made a commit, here are the next steps:


1. get the sha of the commit you just made (if you didn't make one, read `.claude/commands/commit.md` and make one)

2. **Create tracking issue** (choose one):
   - **Beads (local)**: `bd create --title="[Feature Name]" --type=feature --priority=2` - for local/git-based tracking
   - **Linear (external)**: read `.claude/commands/linear.md` - for team ticketing system
   Think deeply about what you just implemented and create a descriptive issue.

3. fetch the ticket/issue to get the recommended git branch name (or use the beads issue ID)
4. git checkout main
5. git checkout -b 'BRANCHNAME'
6. git cherry-pick 'COMMITHASH'
7. git push -u origin 'BRANCHNAME'
8. gh pr create --fill
9. read '.claude/commands/describe_pr.md' and follow the instructions
10. **Update beads**: If using beads, run `bd update <id> --status=in_progress` then `bd dolt push and bd dolt pull`
