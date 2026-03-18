# Local Review

You are tasked with setting up a local review environment for a colleague's branch. This involves creating a worktree, setting up dependencies, and launching a new Claude Code session.

## Process

When invoked with a parameter like `gh_username:branchName`:

1. **Parse the input**:
   - Extract GitHub username and branch name from the format `username:branchname`
   - If no parameter provided, ask for it in the format: `gh_username:branchName`

2. **Extract ticket information**:
   - Look for ticket numbers in the branch name (e.g., `eng-1696`, `ENG-1696`)
   - Use this to create a short worktree directory name
   - If no ticket found, use a sanitized version of the branch name

3. **Set up the remote and worktree**:
   - Check if the remote already exists using `git remote -v`
   - If not, add it: `git remote add USERNAME git@github.com:USERNAME/silmari-oracle`
   - Fetch from the remote: `git fetch USERNAME`
   - Create worktree: `git worktree add -b BRANCHNAME ~/wt/silmari-oracle/SHORT_NAME USERNAME/BRANCHNAME`

4. **Configure the worktree**:
   - Copy Claude settings: `cp .claude/settings.local.json WORKTREE/.claude/`
   - Run setup: `make -C WORKTREE setup`
   - Initialize thoughts: `cd WORKTREE && silmari-oracle init --directory silmari-oracle`

## Error Handling

- If worktree already exists, inform the user they need to remove it first
- If remote fetch fails, check if the username/repo exists
- If setup fails, provide the error but continue with the launch

## Example Usage

```
/local_review samdickson22:sam/eng-1696-hotkey-for-yolo-mode
```

This will:
- Add 'samdickson22' as a remote
- Create worktree at `~/wt/silmari-oracle/eng-1696`
- Set up the environment

## Beads Integration

After setting up the worktree:
1. **Check for related issues**: Run `bd list --status=open` to see if there's a tracked issue for this PR
2. **Review existing context**: If a beads issue exists, run `bd show <id>` to see any notes or dependencies

During/after review:
1. **Track review findings**: If you discover issues during review, create beads issues:
   ```bash
   bd create --title="Review: [finding]" --type=bug|task --priority=2
   ```
2. **Link to PR work**: If the PR implements a tracked issue, note the connection
3. **Sync beads**: Run `bd dolt push and bd dolt pull` after creating any issues
