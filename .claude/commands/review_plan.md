# Review Plan

You are tasked with reviewing an implementation plan BEFORE implementation begins to ensure all contracts, interfaces, promises, data models, and APIs are properly defined and validated.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Purpose

`review_plan` is a **pre-implementation architectural review** that catches design gaps before code is written. This prevents costly rework and ensures implementation success.

## Initial Setup

When invoked:

1. **Locate the plan**:
   - If plan path provided as parameter, use it
   - Otherwise, search `thoughts/searchable/shared/plans/` for recent plans
   - Ask user to specify if multiple candidates exist

2. **Read the plan completely**:
   - Use Read tool WITHOUT limit/offset
   - Understand the full scope before analysis

3. **Gather codebase context**:
   - Spawn parallel research tasks to understand existing patterns
   - Find related interfaces, contracts, and data models in the codebase

## Review Process

### Step 1: Contract Analysis

**Contracts define agreements between components.** Review for:

1. **Component Boundaries**:
   - Are boundaries between modules/services clearly defined?
   - What data crosses each boundary?
   - Who owns what state?

2. **Explicit Contracts**:
   - Are input/output contracts specified for each function/method?
   - Are preconditions and postconditions documented?
   - Are invariants maintained?

3. **Error Contracts**:
   - What errors can each component return?
   - How should callers handle each error type?
   - Are error codes/types explicitly enumerated?

4. **Spawn contract research**:
   ```
   Task: Find existing contract patterns in codebase
   - Look for trait definitions, interfaces, type signatures
   - Identify how errors are propagated
   - Note any contract enforcement patterns (assertions, validators)
   ```

### Step 2: Interface Analysis

**Interfaces define how components communicate.** Review for:

1. **Public Interface Completeness**:
   - Are all public methods/functions defined?
   - Are method signatures complete (parameters, return types)?
   - Are visibility modifiers appropriate (pub, pub(crate), private)?

2. **Interface Consistency**:
   - Do similar operations have consistent signatures?
   - Are naming conventions followed?
   - Does the interface match existing codebase patterns?

3. **Interface Evolution**:
   - Can the interface evolve without breaking changes?
   - Are extension points provided?
   - Is there a versioning strategy?

4. **Spawn interface research**:
   ```
   Task: Analyze existing interfaces in related modules
   - Find similar interfaces to model after
   - Identify trait patterns used in the codebase
   - Note any interface conventions or standards
   ```

### Step 3: Promise Analysis

**Promises define guarantees and async behavior.** Review for:

1. **Behavioral Promises**:
   - What guarantees does each component make?
   - Are idempotency guarantees specified where needed?
   - Are ordering guarantees documented?

2. **Async/Concurrent Promises**:
   - Are async operations clearly identified?
   - What happens on timeout/cancellation?
   - Are race conditions addressed?

3. **Resource Promises**:
   - Are resource cleanup guarantees specified?
   - Are memory/performance bounds documented?
   - Are RAII patterns or cleanup handlers planned?

4. **Spawn promise research**:
   ```
   Task: Find async patterns and guarantees in codebase
   - Look for async/await usage patterns
   - Identify cancellation handling
   - Note resource management patterns
   ```

### Step 4: Data Model Analysis

**Data models define the structure of information.** Review for:

1. **Schema Completeness**:
   - Are all fields defined with types?
   - Are optional vs required fields clear?
   - Are default values specified?

2. **Schema Consistency**:
   - Do field names follow conventions?
   - Are types consistent across related models?
   - Are enums/variants exhaustively defined?

3. **Data Relationships**:
   - Are relationships between models clear (1:1, 1:N, N:M)?
   - Are foreign key/reference semantics defined?
   - Are cascading behaviors specified (delete, update)?

4. **Data Evolution**:
   - Is migration strategy defined for schema changes?
   - Are backward compatibility concerns addressed?
   - Is serialization format specified?

5. **Spawn data model research**:
   ```
   Task: Analyze existing data models
   - Find similar models to compare against
   - Identify serialization patterns (serde, protobuf, etc.)
   - Note any ORM or database patterns used
   ```

### Step 5: API Analysis

**APIs define external communication contracts.** Review for:

1. **API Specification**:
   - Are all endpoints/methods defined?
   - Are request/response formats specified?
   - Are status codes/error responses documented?

2. **API Consistency**:
   - Do endpoints follow REST/RPC conventions?
   - Are naming patterns consistent?
   - Is authentication/authorization addressed?

3. **API Versioning**:
   - Is versioning strategy defined?
   - Are deprecation policies clear?
   - Are breaking changes identified?

4. **API Documentation**:
   - Are examples provided?
   - Are edge cases documented?
   - Are rate limits/quotas specified?

5. **Spawn API research**:
   ```
   Task: Analyze existing API patterns
   - Find similar endpoints to model after
   - Identify authentication patterns
   - Note error response formats used
   ```

## Step 6: Generate Review Report

Create comprehensive review summary:

```markdown
## Plan Review Report: thoughts/searchable/shared/plans/2026-01-04-tdd-silk-encoding-rust-pipeline-optimization-REVIEW.md [Plan Name + REVIEW]

### Review Summary
| Category | Status | Issues Found |
|----------|--------|--------------|
| Contracts | ✅/⚠️/❌ | N issues |
| Interfaces | ✅/⚠️/❌ | N issues |
| Promises | ✅/⚠️/❌ | N issues |
| Data Models | ✅/⚠️/❌ | N issues |
| APIs | ✅/⚠️/❌ | N issues |

### Contract Review

#### Well-Defined:
- ✅ [Contract 1] - Clear input/output specification
- ✅ [Contract 2] - Error handling documented

#### Missing or Unclear:
- ⚠️ [Issue 1] - Missing error contract for [scenario]
- ❌ [Issue 2] - No contract defined for [boundary]

#### Recommendations:
- Add explicit error types for [component]
- Document preconditions for [function]

---

### Interface Review

#### Well-Defined:
- ✅ [Interface 1] - Complete method signatures
- ✅ [Interface 2] - Follows codebase patterns

#### Missing or Unclear:
- ⚠️ [Issue 1] - Method [X] missing return type
- ❌ [Issue 2] - Interface inconsistent with [existing pattern]

#### Recommendations:
- Add [method] to complete the interface
- Rename [X] to match convention [Y]

---

### Promise Review

#### Well-Defined:
- ✅ [Promise 1] - Idempotency guaranteed
- ✅ [Promise 2] - Cancellation behavior specified

#### Missing or Unclear:
- ⚠️ [Issue 1] - No timeout handling for [operation]
- ❌ [Issue 2] - Race condition possible in [scenario]

#### Recommendations:
- Add timeout handling with [strategy]
- Document ordering guarantees for [operation]

---

### Data Model Review

#### Well-Defined:
- ✅ [Model 1] - Complete schema with types
- ✅ [Model 2] - Relationships clearly defined

#### Missing or Unclear:
- ⚠️ [Issue 1] - Field [X] missing type annotation
- ❌ [Issue 2] - No migration strategy for [change]

#### Recommendations:
- Define default values for [optional fields]
- Add migration plan for [schema change]

---

### API Review

#### Well-Defined:
- ✅ [Endpoint 1] - Request/response documented
- ✅ [Endpoint 2] - Error codes specified

#### Missing or Unclear:
- ⚠️ [Issue 1] - Missing authentication for [endpoint]
- ❌ [Issue 2] - No versioning strategy

#### Recommendations:
- Add auth requirements for [endpoint]
- Document rate limiting policy

---

### Critical Issues (Must Address Before Implementation)

1. **[Issue Category]**: [Description]
   - Impact: [What breaks if not addressed]
   - Recommendation: [How to fix]

2. **[Issue Category]**: [Description]
   - Impact: [What breaks if not addressed]
   - Recommendation: [How to fix]

### Suggested Plan Amendments

```diff
# In Phase [N]: [Phase Name]

+ Add: Contract specification for [component]
+ Add: Error handling for [scenario]
- Remove: [Unnecessary complexity]
~ Modify: [Interface X] to match pattern [Y]
```

### Approval Status

- [ ] **Ready for Implementation** - No critical issues
- [ ] **Needs Minor Revision** - Address warnings before proceeding
- [ ] **Needs Major Revision** - Critical issues must be resolved first
```

## Review Checklist

### Contracts
- [ ] Component boundaries are clearly defined
- [ ] Input/output contracts are specified
- [ ] Error contracts enumerate all failure modes
- [ ] Preconditions and postconditions are documented
- [ ] Invariants are identified

### Interfaces
- [ ] All public methods are defined with signatures
- [ ] Naming follows codebase conventions
- [ ] Interface matches existing patterns
- [ ] Extension points are considered
- [ ] Visibility modifiers are appropriate

### Promises
- [ ] Behavioral guarantees are documented
- [ ] Async operations have timeout/cancellation handling
- [ ] Resource cleanup is specified
- [ ] Idempotency requirements are addressed
- [ ] Ordering guarantees are documented where needed

### Data Models
- [ ] All fields have types
- [ ] Required vs optional is clear
- [ ] Relationships are documented
- [ ] Migration strategy is defined
- [ ] Serialization format is specified

### APIs
- [ ] All endpoints are defined
- [ ] Request/response formats are specified
- [ ] Error responses are documented
- [ ] Authentication requirements are clear
- [ ] Versioning strategy is defined

## Important Guidelines

1. **Be Thorough**: Review every aspect, don't assume correctness
2. **Be Specific**: Point to exact sections that need changes
3. **Be Constructive**: Provide recommendations, not just criticisms
4. **Be Practical**: Focus on issues that will cause real problems
5. **Be Pattern-Aware**: Compare against existing codebase patterns

## Severity Levels

- ✅ **Well-Defined**: No action needed
- ⚠️ **Warning**: Should be addressed, but not blocking
- ❌ **Critical**: Must be resolved before implementation

After completing review:
1. **Create tracking issue** if critical issues found: `bd create --title="Plan Review: [Plan Name]" --type=task --priority=1`
2. **Link issues**: If plan amendments create new work items, create and link them with `bd dep add`
3. **Update existing issue**: If reviewing a plan for an existing issue, add review findings as notes
4. **Sync beads**: Run `bd dolt push and bd dolt pull` to persist any beads changes
