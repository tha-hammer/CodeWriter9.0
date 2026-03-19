# CW9 Worktree Setup

Bootstrap a new git worktree with CW9 crawl data from a parent tree, so extracted IN:DO:OUT cards carry over and only new/changed functions need LLM extraction.

## Arguments

$ARGUMENTS = worktree branch name and/or path. If not provided, ask.

## Process

### 1. Resolve Paths

- Identify the **main tree** (current working directory, or the git main working tree)
- Confirm `.cw9/crawl.db` exists in the main tree. If not, abort with instructions to run `cw9 ingest` first
- Determine the **worktree branch name** from $ARGUMENTS
- Determine the **worktree path** — default: `~/Dev/<repo-name>-<branch-name>`

Confirm with the user:

```
Main tree: /path/to/main
Worktree path: /path/to/worktree
Branch: feature-name
crawl.db: N total records (M extracted, K skeletons)
```

### 2. Create Worktree

```bash
git worktree add <worktree-path> -b <branch-name>
```

If `silmari-oracle` is available, prefer:
```bash
silmari-oracle worktree create <branch-name>
```

### 3. Bootstrap CW9

Copy the `.cw9/` directory from the main tree to the worktree:

```bash
cp -r <main-tree>/.cw9 <worktree-path>/.cw9
```

### 4. Re-ingest with Adoption

Run incremental ingest against the worktree. This converts absolute paths to relative, adopts extraction data from the parent's records where content hasn't changed, and creates skeletons only for genuinely new/changed files:

```bash
cw9 ingest <worktree-path> <worktree-path> --incremental
```

Check the output for the `adopted` count — this shows how many extracted cards were carried over from the parent tree.

### 5. Verify

Query the resulting DB to confirm the state:

```sql
SELECT
  CASE WHEN do_description = 'SKELETON_ONLY' THEN 'skeleton'
       WHEN do_description = 'EXTRACTION_FAILED' THEN 'failed'
       ELSE 'extracted' END as status,
  COUNT(*)
FROM records
WHERE is_external = FALSE
GROUP BY status;
```

### 6. Report

Tell the user:
- How many records were adopted (saved LLM calls)
- How many skeletons remain (need `cw9 crawl --incremental`)
- Estimated crawl time at ~20s per skeleton
- The command to run next:

```bash
cd <worktree-path>
cw9 crawl . --incremental
```

## Notes

- The re-ingest step is critical. Without it, the copied DB has absolute paths pointing to the main tree, and UUIDs won't match the worktree's files.
- Adoption matches by `(function_name, class_name, src_hash)`. Files that changed between main and worktree will correctly get new skeletons.
- Orphan records (extracted with old absolute paths, no matching worktree file) are harmless — the bridge step will clean them up.
