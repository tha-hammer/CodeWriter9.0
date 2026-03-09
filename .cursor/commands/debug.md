# Debug

You are tasked with helping debug issues during manual testing or implementation. This command allows you to investigate problems by examining logs, database state, and git history without editing files. Think of this as a way to bootstrap a debugging session without using the primary window's context.

## Initial Response

When invoked WITH a plan/ticket file:
```
I'll help debug issues with [file name]. Let me understand the current state.

What specific problem are you encountering?
- What were you trying to test/implement?
- What went wrong?
- Any error messages?

I'll investigate the logs, database, and git state to help figure out what's happening.
```

When invoked WITHOUT parameters:
```
I'll help debug your current issue.

Please describe what's going wrong:
- What are you working on?
- What specific problem occurred?
- When did it last work?

I can investigate logs, database state, and recent changes to help identify the issue.
```

## Environment Information

## Process Steps

### Step 0: Check Beads for Related Issues - CRITICALLY IMPORTANT

Before diving into investigation:
1. **Sync beads**: Run `bd dolt push and bd dolt pull` to get latest issue state
2. **Check for related bugs**: Run `bd list --type=bug --status=open` to see known issues
3. **Check in-progress work**: Run `bd list --status=in_progress` - the bug may be related to active work
4. **Review blocked issues**: Run `bd blocked` - the issue might be blocking something

If you find a related issue, run `bd show <id>` for full context before investigating.

### Step 1: Understand the Problem

After the user describes the issue:

1. **Read any provided context** (plan or ticket file):
   - Understand what they're implementing/testing
   - Note which phase or step they're on
   - Identify expected vs actual behavior

2. **Quick state check**:
   - Current git branch and recent commits
   - Any uncommitted changes
   - When the issue started occurring

### Step 2: Investigate the Issue

Spawn parallel Task agents for efficient investigation:

```
Task 1 - Check Recent Logs:
Find and analyze the most recent logs for errors:
1. Find latest daemon log: ls -t ~/.silmari-oracle/logs/daemon-*.log | head -1
2. Find latest WUI log: ls -t ~/.silmari-oracle/logs/wui-*.log | head -1
3. Search for errors, warnings, or issues around the problem timeframe
4. Note the working directory (first line of log)
5. Look for stack traces or repeated errors
Return: Key errors/warnings with timestamps
```

```
Task 2 - Database State:
Check the current database state:
1. Connect to database: sqlite3 ~/.silmari-oracle/daemon.db
2. Check schema: .tables and .schema for relevant tables
3. Query recent data:
   - SELECT * FROM sessions ORDER BY created_at DESC LIMIT 5;
   - SELECT * FROM conversation_events WHERE created_at > datetime('now', '-1 hour');
   - Other queries based on the issue
4. Look for stuck states or anomalies
Return: Relevant database findings
```

```
Task 3 - Git and File State:
Understand what changed recently:
1. Check git status and current branch
2. Look at recent commits: git log --oneline -10
3. Check uncommitted changes: git diff
4. Verify expected files exist
5. Look for any file permission issues
Return: Git state and any file issues
```

### Step 3: Present Findings

Based on the investigation, present a focused debug report:

```markdown
## Debug Report

### What's Wrong
[Clear statement of the issue based on evidence]

### Evidence Found

**From Logs** (`~/.silmari-oracle/logs/`):
- [Error/warning with timestamp]
- [Pattern or repeated issue]

**From Database**:
```sql
-- Relevant query and result
[Finding from database]
```

**From Git/Files**:
- [Recent changes that might be related]
- [File state issues]

### Root Cause
[Most likely explanation based on evidence]

### Next Steps

1. **Try This First**:
   ```bash
   [Specific command or action]
   ```

2. **If That Doesn't Work**:
   - Restart services: `make daemon` and `make wui`
   - Check browser console for WUI errors
   - Run with debug: `silmari-oracle_DEBUG=true make daemon`

### Can't Access?
Some issues might be outside my reach:
- Browser console errors (F12 in browser)
- MCP server internal state
- System-level issues

### Beads Tracking - CRITICALLY IPORTANT
- Related issue: [bd-XXX if found, or "None found"]
- Suggested action: [Create new bug / Update existing / None needed]

Would you like me to investigate something specific further?
```

### Step 4: Track in Beads

After presenting findings:

1. **If this is a new bug** (not already tracked):
   ```bash
   bd create --title="[Brief bug description]" --type=bug --priority=2
   ```
   Include key findings in the issue description.

2. **If updating an existing issue**:
   ```bash
   bd update <id> --status=in_progress
   ```
   Add debug findings as context.

3. **If bug is blocking other work**:
   ```bash
   bd dep add <blocked-issue> <this-bug>
   ```
   This shows what's waiting on this fix.

4. **When the bug is fixed**:
   ```bash
   bd close <id>
   bd dolt push and bd dolt pull
   ```

## Important Notes

- **Focus on manual testing scenarios** - This is for debugging during implementation
- **Always require problem description** - Can't debug without knowing what's wrong
- **Read files completely** - No limit/offset when reading context
- **Think like `commit` or `describe_pr`** - Understand git state and changes
- **Guide back to user** - Some issues (browser console, MCP internals) are outside reach
- **No file editing** - Pure investigation only

## Quick Reference
**Git State**:
```bash
git status
git log --oneline -10
git diff
```

**Beads Issue Tracking**:
```bash
bd dolt push and bd dolt pull                              # Get latest state
bd list --type=bug --status=open     # See known bugs
bd list --status=in_progress         # Active work
bd show <id>                         # Issue details
bd create --title="..." --type=bug   # Create bug issue
bd close <id>                        # Mark fixed
```

Remember: This command helps you investigate without burning the primary window's context. Perfect for when you hit an issue during manual testing and need to dig into logs, database, or git state.
