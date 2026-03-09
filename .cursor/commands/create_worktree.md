
2. set up worktree for implementation:
2a. Create a new worktree with a descriptive name: `silmari-oracle worktree create feature-name`
   - **CRITICAL**: Use the proper `silmari-oracle worktree create` command, NOT `git worktree add`
   - This creates worktree at `~/wt/<repo-name>/feature-name` with branch `feature-name`
   - Or let it auto-generate: `silmari-oracle worktree create` (creates unique name like `swift_fix_1430`)

3. determine required data:

branch name
path to plan file (use relative path only)
launch prompt
command to run

**IMPORTANT PATH USAGE:**
- The thoughts/ directory is synced between the main repo and worktrees
- Always use ONLY the relative path starting with `thoughts/searchable/shared/...` without any directory prefix
- Example: `thoughts/searchable/shared/plans/fix-mcp-keepalive-proper.md` (not the full absolute path)
- This works because thoughts are synced and accessible from the worktree

3a. confirm with the user by sending a message to the Human

```
based on the input, I plan to create a worktree with the following details:

worktree path: ~/wt/<repo-name>/feature-name
branch name: feature-name
path to plan file: $FILEPATH
launch prompt:

    /implement_plan_with_checkpoint_worktree at $FILEPATH
```

incorporate any user feedback then:

4. launch implementation session: `/implement_plan_with_checkpoint_worktree at $FILEPATH`

Note: The new command includes checkpoint strategy and final steps for commit/PR creation.
