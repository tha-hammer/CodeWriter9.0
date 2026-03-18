# CW9 Research

Research an existing codebase using `cw9` CLI tools to produce a research document with function-level detail.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for synthesis — don't read entire codebases yourself.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers.
Have subagents write to file to save the main context window.

## Arguments

$ARGUMENTS = task description, target project path, and/or path to existing research. If not provided, ask.

## CW9 CLI Reference

`cw9` is a CLI tool. You call it via bash.

```
cw9 init <project>                          # create .cw9/ dir (run once)
cw9 ingest <path> <project> [--lang X]      # scan source files into crawl.db (skeletons)
cw9 ingest <path> <project> --incremental   # re-scan only changed files
cw9 crawl <project>                         # DFS LLM extraction (fills IN:DO:OUT cards)
cw9 crawl <project> --incremental           # re-extract only changed functions
cw9 stale <project>                         # show which records are out of date
cw9 show <node-id> <project> --card         # print one IN:DO:OUT card
cw9 status <project> --json                 # pipeline status
```

**Important**: `ingest` creates skeleton records (signatures only). `crawl` fills in the IN:DO:OUT behavioral data via LLM extraction. Full cards are critical — they feed directly into the pipeline's PlusCal generation prompt, giving the LLM the actual behavioral contracts of the functions your GWT depends on.

The data lives in `<project>/.cw9/crawl.db` (SQLite). You can query it directly:

```sql
-- list all ingested files and function counts
SELECT file_path, COUNT(*) as fn_count FROM records WHERE is_external = FALSE GROUP BY file_path ORDER BY fn_count DESC;

-- find functions by name pattern
SELECT uuid, function_name, file_path, line_number FROM records WHERE function_name LIKE '%pattern%';

-- find all functions in a directory
SELECT uuid, function_name, file_path FROM records WHERE file_path LIKE 'backend/%' AND is_external = FALSE;

-- check what a function's inputs and outputs are
SELECT r.function_name, i.name, i.type_str, i.source FROM records r JOIN ins i ON r.uuid = i.record_uuid WHERE r.function_name = 'someName';

-- find callers of a function (who calls it?)
SELECT r.function_name, r.file_path FROM records r JOIN ins i ON r.uuid = i.record_uuid WHERE i.source = 'internal_call' AND i.source_function = 'targetName';

-- find entry points (HTTP routes, CLI commands, main functions)
SELECT e.kind, e.route, r.function_name, r.file_path FROM entry_points e JOIN records r ON e.record_uuid = r.uuid;

-- check if cards are skeletons or fully extracted
SELECT function_name, do_description FROM records WHERE do_description = 'SKELETON_ONLY' LIMIT 5;
```

## Process

### 1. Orient

- Read $ARGUMENTS to understand what the user wants to research or build
- Identify the target project directory and confirm `.cw9/` exists (run `cw9 init` if not)
- If a codebase path is given, ingest it. If crawl.db already exists, use `--incremental`

### 2. Beads Setup

- Run `bd list --status=open` to check for existing tracked issues on this topic
- If none exists: `bd create --title="Research: [topic]" --type=task --priority=2`
- Note the beads ID for later

### 3. Ingest and Crawl

```bash
# Skeleton scan (fast — signatures only)
cw9 ingest <path> <project>

# LLM extraction (slower — fills IN:DO:OUT behavioral data)
cw9 crawl <project>
```

Run `ingest` first for the broad view, then `crawl` to fill in behavioral detail. If crawl.db already exists and source hasn't changed, use `--incremental` on both.

Check extraction status:
```sql
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN do_description = 'SKELETON_ONLY' THEN 1 ELSE 0 END) as skeletons,
  SUM(CASE WHEN do_description != 'SKELETON_ONLY' THEN 1 ELSE 0 END) as extracted
FROM records WHERE is_external = FALSE;
```

### 4. Explore

Use cw9 to understand the relevant code. Your goal is to build a mental model of what exists before proposing changes.

- **Start broad**: query crawl.db to see what's there — file counts, directories, function counts
- **Find entry points**: query `entry_points` table to understand how the code is invoked
- **Trace call graphs**: use `cw9 show <uuid> --card` on key functions to see their IN:DO:OUT contracts
- **Follow dependencies**: query the `ins` table with `source = 'internal_call'` to trace what calls what
- **Read source**: when a card isn't enough, read the actual source file at the line number shown

Do NOT try to explore everything. Focus on the functions and files relevant to the user's task. Use SQL queries to narrow down, then `cw9 show --card` on the important ones.

### 5. Write Research Document

Write to: `thoughts/searchable/shared/research/YYYY-MM-DD-description.md`

Use this structure:

```markdown
---
date: [ISO timestamp]
researcher: [name]
git_commit: [hash]
branch: [branch]
repository: [repo]
topic: "[topic]"
tags: [research, cw9, relevant-tags]
status: complete
last_updated: [YYYY-MM-DD]
last_updated_by: [name]
cw9_project: [target project path]
---

# Research: [Topic]

## Research Question
[What the user wants to understand or build]

## Codebase Overview
[High-level structure from cw9 ingest — file counts, directories, entry points]
[Extraction status: N skeletons, M fully extracted]

## Key Functions

### functionName()
- **File**: path/to/file.ext:line
- **UUID**: [crawl.db UUID]
- **Role**: [what it does based on IN:DO:OUT card or source read]
- **Calls**: [internal dependencies]
- **Called by**: [callers]

[Repeat for each key function]

## Call Graph
[How the key functions connect — which calls which, data flow]

## Findings
[What you discovered that's relevant to the user's task]

## Proposed Changes
[What needs to change, referencing specific functions and UUIDs]

## CW9 Mention Summary
Functions: functionName(), otherFunction()
Files: path/to/relevant/file.ext
Directories: relevant/directory/

Note: The "CW9 Mention Summary" section is formatted for gwt-author extraction.
Function names MUST include () for mention extraction.
```

### 6. Report

Tell the user:
- What you found during exploration (key functions, call patterns, existing behavior)
- Where the research document was written
- Extraction status (how many cards are skeleton vs fully extracted)
- What to run next: `/cw9_plan <research-doc-path> <project>`

Update beads: `bd update <id> --status=done`

## Guidelines

- Use bash to run cw9 commands. That's it.
- Query crawl.db with `sqlite3 <project>/.cw9/crawl.db` when you need to search or aggregate.
- When `cw9 show --card` gives you a skeleton-only record (do_description = "SKELETON_ONLY"), read the actual source file to understand the function.
- Don't ingest the entire world. Ingest the directories relevant to the task.
- The research doc's "CW9 Mention Summary" section is what gwt-author will parse. Functions need `()`, files need extensions, directories need trailing `/`.
- Mentioning ANY file under a directory causes gwt-author to expand to the entire ancestor directory tree. A broad mention like `backend/` pulls ALL functions under that tree.
- If crawl.db doesn't exist yet, run `cw9 init` then `cw9 ingest`.
- Run `cw9 crawl` before moving to `/cw9_plan` — full IN:DO:OUT cards feed the pipeline prompt and produce much better PlusCal specs than skeletons alone.
