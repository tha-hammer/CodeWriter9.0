# Implementation Plan

You are tasked with creating detailed implementation plans through an interactive, iterative process. You should be skeptical, thorough, and work collaboratively with the user to produce high-quality technical specifications.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Initial Response

When this command is invoked:

1. **Check if parameters were provided**:
   - If a file path or ticket reference was provided as a parameter, skip the default message
   - Immediately read any provided files FULLY
   - Begin the research process

2. **If no parameters provided**, respond with:
```
I'll help you create a detailed implementation plan. Let me start by understanding what we're building.

Please provide:
1. The task/ticket description (or reference to a ticket file)
2. Any relevant context, constraints, or specific requirements
3. Links to related research or previous implementations

I'll analyze this information and work with you to create a comprehensive plan.

Tip: You can also invoke this command with a ticket file directly: `/create_plan thoughts/maceo/tickets/eng_1234.md`
For deeper analysis, try: `/create_plan think deeply about thoughts/maceo/tickets/eng_1234.md`
```

Then wait for the user's input.

## Process Steps

### Step 1: Context Gathering & Initial Analysis

1. **Read all mentioned files immediately and FULLY**:
   - Ticket files (e.g., `thoughts/maceo/tickets/eng_1234.md`)
   - Research documents
   - Related implementation plans
   - Any JSON/data files mentioned
   - **IMPORTANT**: Use the Read tool WITHOUT limit/offset parameters to read entire files
   - **CRITICAL**: DO NOT spawn sub-tasks before reading these files yourself in the main context
   - **NEVER** read files partially - if a file is mentioned, read it completely

2. **Spawn initial research tasks to gather context**:
   Before asking the user any questions, use specialized agents to research in parallel:

   - Use the **codebase-locator** agent to find all files related to the ticket/task
   - Use the **codebase-analyzer** agent to understand how the current implementation works
   - If relevant, use the **thoughts-locator** agent to find any existing thoughts documents about this feature
   - If a Linear ticket is mentioned, use the **linear-ticket-reader** agent to get full details

   These agents will:
   - Find relevant source files, configs, and tests
   - Identify the specific directories to focus on (e.g., if WUI is mentioned, they'll focus on silmari-oracle-wui/)
   - Trace data flow and key functions
   - Return detailed explanations with file:line references

3. **Read all files identified by research tasks**:
   - After research tasks complete, read ALL files they identified as relevant
   - Read them FULLY into the main context
   - This ensures you have complete understanding before proceeding

4. **Analyze and verify understanding**:
   - Cross-reference the ticket requirements with actual code
   - Identify any discrepancies or misunderstandings
   - Note assumptions that need verification
   - Determine true scope based on codebase reality

5. **Present informed understanding and focused questions**:
   ```
   Based on the ticket and my research of the codebase, I understand we need to [accurate summary].

   I've found that:
   - [Current implementation detail with file:line reference]
   - [Relevant pattern or constraint discovered]
   - [Potential complexity or edge case identified]

   Questions that my research couldn't answer:
   - [Specific technical question that requires human judgment]
   - [Business logic clarification]
   - [Design preference that affects implementation]
   ```

   Only ask questions that you genuinely cannot answer through code investigation.

### Step 2: Research & Discovery

After getting initial clarifications:

1. **If the user corrects any misunderstanding**:
   - DO NOT just accept the correction
   - Spawn new research tasks to verify the correct information
   - Read the specific files/directories they mention
   - Only proceed once you've verified the facts yourself

2. **Create a research todo list** using TodoWrite to track exploration tasks

3. **Spawn parallel sub-tasks for comprehensive research**:
   - Create multiple Task agents to research different aspects concurrently
   - Use the right agent for each type of research:

   **For deeper investigation:**
   - **codebase-locator** - To find more specific files (e.g., "find all files that handle [specific component]")
   - **codebase-analyzer** - To understand implementation details (e.g., "analyze how [system] works")
   - **codebase-pattern-finder** - To find similar features we can model after

   **For historical context:**
   - **thoughts-locator** - To find any research, plans, or decisions about this area
   - **thoughts-analyzer** - To extract key insights from the most relevant documents

   **For related tickets:**
   - **linear-searcher** - To find similar issues or past implementations

   Each agent knows how to:
   - Find the right files and code patterns
   - Identify conventions and patterns to follow
   - Look for integration points and dependencies
   - Return specific file:line references
   - Find tests and examples

3. **Wait for ALL sub-tasks to complete** before proceeding

4. **Present findings and design options**:
   ```
   Based on my research, here's what I found:

   **Current State:**
   - [Key discovery about existing code]
   - [Pattern or convention to follow]

   **Design Options:**
   1. [Option A] - [pros/cons]
   2. [Option B] - [pros/cons]

   **Open Questions:**
   - [Technical uncertainty]
   - [Design decision needed]

   Which approach aligns best with your vision?
   ```

### Step 3: Plan Structure Development

Once aligned on approach:

1. **Create initial plan outline**:
   ```
   Here's my proposed plan structure:

   ## Overview
   [1-2 sentence summary]

   ## Implementation Phases:
   1. [Phase name] - [what it accomplishes]
   2. [Phase name] - [what it accomplishes]
   3. [Phase name] - [what it accomplishes]

   Does this phasing make sense? Should I adjust the order or granularity?
   ```

2. **Get feedback on structure** before writing details

### Step 4: Detailed Plan Writing

After structure approval:

1. **Write the plan** to `thoughts/searchable/shared/plans/YYYY-MM-DD-ENG-XXXX-description.md`
   - Format: `YYYY-MM-DD-ENG-XXXX-description.md` where:
     - YYYY-MM-DD is today's date
     - ENG-XXXX is the ticket number (omit if no ticket)
     - description is a brief kebab-case description
   - Examples:
     - With ticket: `2025-01-08-ENG-1478-parent-child-tracking.md`
     - Without ticket: `2025-01-08-improve-error-handling.md`
2. **Use this template structure**:

````markdown
# [Feature/Task Name] Implementation Plan

## Overview

[Brief description of what we're implementing and why]

## Current State Analysis

[What exists now, what's missing, key constraints discovered]

## Desired End State

[A Specification of the desired end state after this plan is complete, and how to verify it]

### Key Discoveries:
- [Important finding with file:line reference]
- [Pattern to follow]
- [Constraint to work within]

## What We're NOT Doing

[Explicitly list out-of-scope items to prevent scope creep]

## Implementation Approach

[High-level strategy and reasoning]

## Phase 1: [Descriptive Name]

### Overview
[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File Group]
**File**: `path/to/file.ext`
**Changes**: [Summary of changes]

```[language]
// Specific code to add/modify
```

### Success Criteria:

#### Automated Verification:
- [ ] Migration applies cleanly: `make migrate`
- [ ] Unit tests pass: `make test-component`
- [ ] Type checking passes: `npm run typecheck`
- [ ] Linting passes: `make lint`
- [ ] Integration tests pass: `make test-integration`

#### Manual Verification:
- [ ] Feature works as expected when tested via UI
- [ ] Performance is acceptable under load
- [ ] Edge case handling verified manually
- [ ] No regressions in related features

---

## Phase 2: [Descriptive Name]

[Similar structure with both automated and manual success criteria...]

---

## Testing Strategy

### Unit Tests:
- [What to test]
- [Key edge cases]

### Integration Tests:
- [End-to-end scenarios]

### Manual Testing Steps:
1. [Specific step to verify feature]
2. [Another verification step]
3. [Edge case to test manually]

## Performance Considerations

[Any performance implications or optimizations needed]

## Migration Notes

[If applicable, how to handle existing data/systems]

## References

- Original ticket: `thoughts/maceo/tickets/eng_XXXX.md`
- Related research: `thoughts/searchable/shared/research/[relevant].md`
- Similar implementation: `[file:line]`
````

### Step 4.5: Beads Issue Tracking (Recommended)

After writing the plan file:

1. **Check for existing beads issues**:
   - Run `bd list --status=open` to see if there's already a tracked issue for this work
   - If an existing issue matches, note its ID for linking

2. **Create or update beads issue**:
   - If no existing issue: `bd create --title="[Feature Name]" --type=feature --priority=2`
   - If issue exists: `bd update <id> --status=in_progress`

3. **Add plan reference to beads issue**:
   - Update the issue with a note: `bd update <id>` and add the plan path in comments
   - This creates traceability between plans and tracked work

4. **Link dependencies if applicable**:
   - If this work depends on other issues: `bd dep add <this-issue> <depends-on>`
   - If other work depends on this: `bd dep add <other-issue> <this-issue>`

### Step 4.6: GitHub Issue Creation (Optional)

After writing the plan file:

1. **Extract issue number from plan filename**:
   - If plan filename contains `ENG-XXXX` pattern, extract the issue number
   - Example: `2025-11-25-ENG-1234-description.md` → issue number `1234`
   - Use the GitHub utility function: `silmari_oracle::github::utils::extract_issue_from_filename()`

2. **Create or link GitHub issue** (only if `gh` CLI is available):
   - Check if GitHub CLI is available: Use `silmari_oracle::github::is_gh_available()`
   - If issue number extracted:
     - Try to get existing issue: Use `silmari_oracle::github::issues::get_issue()` with the extracted number
     - If issue exists, add plan link as comment using `silmari_oracle::github::issues::add_comment()`
     - If issue doesn't exist (returns error), create new issue with plan summary using `silmari_oracle::github::issues::create_issue()`
   - Add issue URL to plan References section:
     ```markdown
     ## References
     
     - GitHub Issue: #{number} - {issue_url}
     - Original ticket: `thoughts/maceo/tickets/eng_{number}.md`
     - Related research: `thoughts/searchable/shared/research/[relevant].md`
     ```

3. **Error Handling**:
   - If `gh` CLI is not available, skip GitHub operations silently
   - If GitHub operations fail, log warning but don't fail plan creation
   - Plan creation should succeed even if GitHub integration fails

**Note**: Since create_plan is executed by AI agents reading markdown instructions, the actual GitHub operations will be performed by the agent using the GitHub module we created. The agent will need to:
- Import/use the GitHub module functions from `silmari_oracle::github`
- Extract issue numbers using the utility functions
- Handle errors gracefully

### Step 5: Sync and Review

1. **Sync the thoughts directory**:
   - Run `silmari-oracle sync` to sync the newly created plan
   - This ensures the plan is properly indexed and available

2. **Present the draft plan location**:
   ```
   I've created the initial implementation plan at:
   `thoughts/searchable/shared/plans/YYYY-MM-DD-ENG-XXXX-description.md`

   Please review it and let me know:
   - Are the phases properly scoped?
   - Are the success criteria specific enough?
   - Any technical details that need adjustment?
   - Missing edge cases or considerations?
   ```

3. **Iterate based on feedback** - be ready to:
   - Add missing phases
   - Adjust technical approach
   - Clarify success criteria (both automated and manual)
   - Add/remove scope items
   - After making changes, run `silmari-oracle sync` again

4. **Continue refining** until the user is satisfied

## Important Guidelines

1. **Be Skeptical**:
   - Question vague requirements
   - Identify potential issues early
   - Ask "why" and "what about"
   - Don't assume - verify with code

2. **Be Interactive**:
   - Don't write the full plan in one shot
   - Get buy-in at each major step
   - Allow course corrections
   - Work collaboratively

3. **Be Thorough**:
   - Read all context files COMPLETELY before planning
   - Research actual code patterns using parallel sub-tasks
   - Include specific file paths and line numbers
   - Write measurable success criteria with clear automated vs manual distinction
   - automated steps should use `make` whenever possible - for example `make -C silmari-oracle-wui check` instead of `cd silmari-oracle-wui && bun run fmt`

4. **Be Practical**:
   - Focus on incremental, testable changes
   - Consider migration and rollback
   - Think about edge cases
   - Include "what we're NOT doing"

5. **Track Progress**:
   - Use TodoWrite to track planning tasks
   - Update todos as you complete research
   - Mark planning tasks complete when done

6. **No Open Questions in Final Plan**:
   - If you encounter open questions during planning, STOP
   - Research or ask for clarification immediately
   - Do NOT write the plan with unresolved questions
   - The implementation plan must be complete and actionable
   - Every decision must be made before finalizing the plan

## Success Criteria Guidelines

**Always separate success criteria into two categories:**

1. **Automated Verification** (can be run by execution agents):
   - Commands that can be run: `make test`, `npm run lint`, etc.
   - Specific files that should exist
   - Code compilation/type checking
   - Automated test suites

2. **Manual Verification** (requires human testing):
   - UI/UX functionality
   - Performance under real conditions
   - Edge cases that are hard to automate
   - User acceptance criteria

**Format example:**
```markdown
### Success Criteria:

#### Automated Verification:
- [ ] Database migration runs successfully: `make migrate`
- [ ] All unit tests pass: `go test ./...`
- [ ] No linting errors: `golangci-lint run`
- [ ] API endpoint returns 200: `curl localhost:8080/api/new-endpoint`

#### Manual Verification:
- [ ] New feature appears correctly in the UI
- [ ] Performance is acceptable with 1000+ items
- [ ] Error messages are user-friendly
- [ ] Feature works correctly on mobile devices
```

## Common Patterns

### For Database Changes:
- Start with schema/migration
- Add store methods
- Update business logic
- Expose via API
- Update clients

### For New Features:
- Research existing patterns first
- Start with data model
- Build backend logic
- Add API endpoints
- Implement UI last

### For Refactoring:
- Document current behavior
- Plan incremental changes
- Maintain backwards compatibility
- Include migration strategy

## Sub-task Spawning Best Practices

When spawning research sub-tasks:

1. **Spawn multiple tasks in parallel** for efficiency
2. **Each task should be focused** on a specific area
3. **Provide detailed instructions** including:
   - Exactly what to search for
   - Which directories to focus on
   - What information to extract
   - Expected output format
4. **Be EXTREMELY specific about directories**:
   - If the ticket mentions "WUI", specify `silmari-oracle-wui/` directory
   - If it mentions "daemon", specify `hld/` directory
   - Never use generic terms like "UI" when you mean "WUI"
   - Include the full path context in your prompts
5. **Specify read-only tools** to use
6. **Request specific file:line references** in responses
7. **Wait for all tasks to complete** before synthesizing
8. **Verify sub-task results**:
   - If a sub-task returns unexpected results, spawn follow-up tasks
   - Cross-check findings against the actual codebase
   - Don't accept results that seem incorrect

Example of spawning multiple tasks:
```python
# Spawn these tasks concurrently:
tasks = [
    Task("Research database schema", db_research_prompt),
    Task("Find API patterns", api_research_prompt),
    Task("Investigate UI components", ui_research_prompt),
    Task("Check test patterns", test_research_prompt)
]
```

## Example Interaction Flow

```
User: /implementation_plan
Assistant: I'll help you create a detailed implementation plan...

User: We need to add parent-child tracking for Claude sub-tasks. See thoughts/maceo/tickets/eng_1478.md
Assistant: Let me read that ticket file completely first...

[Reads file fully]

Based on the ticket, I understand we need to track parent-child relationships for Claude sub-task events in the hld daemon. Before I start planning, I have some questions...

[Interactive process continues...]
```



## ✨ Enhanced Formatting 

### 🎨 Visual Improvements

**1. Document Header**
- Added ASCII box banner with project title
- Status indicator and date
- Professional framing

**2. Section Headers with Emojis**
- 📚 📊 🎯 🚫 🚀 🛡️ for better visual scanning
- Consistent emoji usage throughout
- Improved hierarchy and navigation

**3. Tables for Structured Information**
- **Documentation Structure** - Clean 4-column table showing locations, files, purpose, and status
- **Strengths** - 2-column table with evidence
- **Gaps Priority Matrix** - ASCII table with priority indicators (🔴🟡🟢)
- **Key Discoveries** - 3-column action table
- **Success Criteria** - Separate tables for automated and manual verification
- **Out of Scope** - Comparison table showing what we're NOT doing vs what we ARE doing

**4. ASCII Art Boxes**
```
┌─────────────────────────────────────────┐
│  Professional framing for key sections  │
└─────────────────────────────────────────┘
```

**5. Collapsible Details Sections**
- Used `<details>` tags for detailed file breakdowns
- Keeps main content scannable while preserving detail

**6. Two-Column Layout**
- HTML tables for side-by-side comparisons
- Documentation deliverables in 2x2 grid
- Better use of horizontal space

**7. Phase Headers with Decorative Boxes**
```
╔═════════════════════════════════════╗
║           PHASE 1                    ║
║  Safety & Quick Start Documentation ║
╚═════════════════════════════════════╝
```

**8. Priority Indicators**
- 🔴 Critical
- 🟡 Important  
- 🟢 Enhancement
- ⚪ Out of scope

**9. Visual Flow Diagrams**
```
Phase 1 → Phase 2 → Phase 3 → Phase 4
   ↓         ↓         ↓         ↓
Benefits flow diagram with arrows
```

**10. Metrics Tables**
- Before/After comparisons
- Target vs Current measurements
- Improvement calculations

### 📋 Structure Improvements

- **Better hierarchy** with consistent emoji usage
- **Scannable content** with tables and boxes
- **Visual separation** between sections
- **Professional appearance** while maintaining readability
- **Markdown-native** - No external dependencies, works everywhere

### ✅ Benefits

The enhanced formatting provides:
- **Faster scanning** - Visual cues help readers find information quickly
- **Better comprehension** - Tables organize complex information clearly
- **Professional appearance** - Looks polished and well-organized
- **Improved navigation** - Emojis and boxes create visual landmarks
- **Maintained simplicity** - Still plain Markdown, no special tools needed

The document should be evisually appealing and easier to navigate while maintaining full Markdown compatibility. All the enhancements MUST use standard Markdown features (tables, HTML, code blocks, emojis) that render correctly in GitHub, VS Code, and other Markdown viewers.