# CW9 Worktree Setup (Self-Hosting)

Set up a git worktree for CW9 self-hosting work. Since CW9 is self-hosting (engine = target = state), a worktree is just a normal git worktree — all paths are relative to repo root.

## Arguments

$ARGUMENTS = worktree branch name and/or path. If not provided, ask.

## Process

### 1. Resolve Paths

- Confirm current directory is the CW9 repo root (has `templates/`, `python/registry/`, `dag.json`)
- Determine the **worktree branch name** from $ARGUMENTS
- Determine the **worktree path** — default: `~/Dev/CodeWriter9.0-<branch-name>`

Confirm with the user:

```
Main tree: /home/maceo/Dev/CodeWriter9.0
Worktree path: /home/maceo/Dev/CodeWriter9.0-<branch-name>
Branch: <branch-name>
```

### 2. Create Worktree

```bash
git worktree add <worktree-path> -b <branch-name>
```

### 3. Verify Self-Hosting Layout

The worktree should have all self-hosting paths intact:

```bash
ls <worktree-path>/templates/pluscal/instances/    # verified specs
ls <worktree-path>/python/tests/generated/          # bridge artifacts + generated tests
ls <worktree-path>/.cw9/context/                    # context files
ls <worktree-path>/dag.json                         # self-hosting DAG
ls <worktree-path>/schema/                          # schema files
```

### 4. Run Tests in Worktree

Verify the worktree is healthy:

```bash
cd <worktree-path>/python && python3 -m pytest tests/ -x
```

### 5. Report

Tell the user:
- Worktree created at `<path>` on branch `<branch>`
- Test suite status (passing/failing)
- Ready for work — all CW9 self-hosting paths are relative, so they work in any worktree
- Note: `sessions/` may contain large untracked files. These are session logs from pipeline runs and don't need to be in the worktree.

## Notes

- Self-hosting is simpler than external for worktrees. No `.cw9/crawl.db` to copy or re-ingest — all state paths are relative to repo root.
- The `dag.json`, `templates/`, `python/`, `schema/` directories are all tracked in git, so they come along with the worktree automatically.
- If you need crawl data in the worktree, copy `.cw9/crawl.db` manually and run `cw9 ingest python/registry <worktree-path> --incremental`.
