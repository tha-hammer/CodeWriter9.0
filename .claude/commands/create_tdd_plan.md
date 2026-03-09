# TDD Implementation Plan

Create detailed Test-Driven Development implementation plans through an interactive, iterative process. Follow TDD principles: Red-Green-Refactor cycles, behavior-first thinking, and incremental development.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Initial Response

**If parameters provided:**
- Read all mentioned files FULLY (no partial reads)
- Begin research immediately

**If no parameters:**
```
I'll help you create a detailed TDD implementation plan. Let me start by understanding what we're building.

Please provide:
1. The task/ticket description (or reference to a ticket file)
2. Any relevant context, constraints, or specific requirements
3. Links to related research or previous implementations

I'll analyze this information and work with you to create a comprehensive TDD plan that breaks the work into the smallest testable behaviors.

Tip: You can also invoke this command with a ticket file directly: `/create_tdd_plan thoughts/maceo/tickets/eng_1234.md`
```

## Process Steps

### Step 1: Context Gathering

1. **Read all mentioned files FULLY** (tickets, research docs, plans, JSON files)
   - Use Read tool WITHOUT limit/offset
   - DO NOT spawn sub-tasks before reading files yourself
   - NEVER read files partially

2. **Spawn parallel research tasks**:
   - **codebase-locator** - Find related files, configs, tests
   - **codebase-analyzer** - Understand current implementation
   - **thoughts-locator** - Find existing thoughts documents
   - **linear-ticket-reader** - Get ticket details if mentioned

3. **Read all files identified by research tasks** FULLY

4. **Present understanding with TDD focus**:
   ```
   Based on the ticket and my research, I understand we need to [summary].

   I've found:
   - [Implementation detail with file:line]
   - [Pattern/constraint discovered]

   From a TDD perspective, testable behaviors:
   - [Observable behavior 1]
   - [Observable behavior 2]

   Questions:
   - [Only ask what code investigation couldn't answer]
   ```

### Step 2: Behavior Identification

1. **If user corrects understanding**: Verify with new research tasks, don't just accept

2. **Create research todo list** using TodoWrite

3. **Identify testable behaviors**:
   - Break into **smallest observable behaviors**
   - Use "Given X, when Y, then Z" format
   - Focus on **what** not **how**
   - Identify inputs/outputs and edge cases

4. **Spawn parallel research** for test patterns, similar features, testing frameworks

5. **Present behavior breakdown**:
   ```
   **Smallest Testable Behaviors:**
   1. [Behavior] - Given [context], when [action], then [result]
   2. [Behavior] - Given [context], when [action], then [result]

   **Test Strategy:**
   - Unit tests: [behaviors]
   - Integration tests: [behaviors]
   - E2E tests: [behaviors]

   **Test Framework:** [identified from codebase]
   **Order:** Start with [simplest], then [next], finally [most complex]

   Does this breakdown make sense?
   ```

### Step 3: Plan Structure

Get feedback on structure before writing details:
```
**TDD Plan Structure:**
- Overview
- Testable Behaviors: [list]
- Each behavior follows Red-Green-Refactor:
  🔴 Red: Write failing test
  🟢 Green: Write minimal code to pass
  🔵 Refactor: Improve code while keeping tests green
```

### Step 4: Write Plan

1. **Write to**: `thoughts/searchable/shared/plans/YYYY-MM-DD-ENG-XXXX-tdd-description.md`
   - Format: `YYYY-MM-DD-ENG-XXXX-tdd-description.md`
   - Examples: `2025-01-08-ENG-1478-tdd-parent-child-tracking.md`

2. **Use template structure**:

````markdown
# [Feature/Task Name] TDD Implementation Plan

## Overview
[Brief description with emphasis on testable behaviors]

## Current State Analysis
[What exists, what's missing, constraints]

### Key Discoveries:
- [Finding with file:line]
- [Pattern to follow]
- [Existing test patterns]

## Desired End State
[Specification and how to verify through tests]

### Observable Behaviors:
- [Behavior 1: Given X, when Y, then Z]
- [Behavior 2: Given X, when Y, then Z]

## What We're NOT Doing
[Out-of-scope items]

## Testing Strategy
- **Framework**: [Jest, Vitest, Rust, etc.]
- **Test Types**: Unit [what], Integration [what], E2E [what]
- **Mocking/Setup**: [strategy]

## Behavior 1: [Name]

### Test Specification
**Given**: [Initial state]
**When**: [Action]
**Then**: [Expected result]

**Edge Cases**: [list]

### TDD Cycle

#### 🔴 Red: Write Failing Test
**File**: `path/to/test/file.test.ts`
```[language]
describe('[Behavior]', () => {
  it('should [expected]', () => {
    // Arrange, Act, Assert
  });
});
```

#### 🟢 Green: Minimal Implementation
**File**: `path/to/impl/file.ts`
```[language]
// Minimal code to pass
```

#### 🔵 Refactor: Improve Code
**File**: `path/to/impl/file.ts`
```[language]
// Refactored code
```

### Success Criteria
**Automated:**
- [ ] Test fails for right reason (Red): `npm test -- file.test.ts`
- [ ] Test passes (Green): `npm test -- file.test.ts`
- [ ] All tests pass after refactor: `npm test`
- [ ] Coverage, typecheck, lint pass

**Manual:**
- [ ] Behavior works as expected
- [ ] Edge cases handled
- [ ] No regressions

---

## Behavior 2: [Name]
[Similar structure...]

## Integration & E2E Testing
- Integration: [scenarios]
- E2E: [user flows]

## References
- Ticket: `thoughts/{user_name}/tickets/eng_XXXX.md`
- Research: `thoughts/searchable/shared/research/[relevant].md`
- Patterns: `[file:line]`
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
   - Include the plan path in the issue description
   - This creates traceability between TDD plans and tracked work

4. **Link dependencies if applicable**:
   - If this work depends on other issues: `bd dep add <this-issue> <depends-on>`
   - If other work depends on this: `bd dep add <other-issue> <this-issue>`

### Step 5: Sync and Review

1. **Sync**: Run `silmari-oracle sync`

2. **Present plan location** and ask for review:
   - Behaviors broken down properly?
   - Test specs clear (Given/When/Then)?
   - Red-Green-Refactor cycle clear?
   - Missing behaviors/edge cases?

3. **Iterate** based on feedback, sync after changes

## Guidelines

### Core Principles
- **Think behavior, not functions**: "How do I observe this working?" "What inputs/outputs prove it?"
- **Tiniest slice**: When stuck, go smaller (e.g., "returns empty list" → "parses single token" → "parses multiple")
- **Test fails first**: See test fail for right reason before writing code
- **Red-Green-Refactor**: Each behavior must follow this cycle
- **Test first**: Always write test before implementation

### Behavior Breakdown
1. **Start simplest**: Empty input → empty output, single item, happy path
2. **Add complexity**: Multiple items, edge cases, errors
3. **Given/When/Then**: Initial state → Action → Expected result
4. **Focus observability**: What can we test? Inputs? Outputs? Side effects?
5. **Avoid implementation**: Test "what" not "how"

### Success Criteria Format
**Always separate:**
- **Automated Verification**: Commands (`make test`, `npm run lint`), test files, compilation, Red/Green/Refactor verification
- **Manual Verification**: UI/UX, performance, hard-to-automate edge cases, behavior observation

### Research Best Practices
- Spawn multiple tasks in parallel
- Be specific about directories (e.g., `silmari-oracle-wui/` not "UI")
- Request file:line references
- Wait for all tasks before synthesizing
- Verify results, don't accept incorrect findings
- Focus on test patterns and existing test files

### Common Patterns
- **New Features**: Simplest behavior → failing test → minimal code → refactor → next behavior
- **Database**: Schema tests → store unit tests → business logic integration → API E2E
- **UI Components**: Behavior tests, user interactions, edge cases, accessibility
- **Refactoring**: Ensure coverage first, refactor incrementally, run tests after each change

### Important Rules
- Read all context files COMPLETELY before planning
- Use `make` commands when possible: `make -C silmari-oracle-wui check`
- No open questions in final plan - resolve before finalizing
- Be interactive: get buy-in at each step, don't write full plan in one shot
- Be skeptical: question vague requirements, verify with code
