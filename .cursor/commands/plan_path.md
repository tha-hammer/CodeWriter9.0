# Plan Path

You are tasked with creating Layer 3 function paths — straight-line execution plans that trace a single user story from trigger to terminal condition, with UUID resource references from the Resource Registry.

This is the path planner from the layered planning architecture (`specs/layered_planning.md`). Each path is planned independently with minimal context: just the user story and the resources it touches. No other paths, no architectural justifications, no full codebase exploration.

## Initial Response

When this command is invoked:

1. **Check if a user story was provided as a parameter**:
   - If provided (e.g., `/plan_path "I want to type a prompt and see generated Rust code"`), use it directly
   - Begin the planning process immediately

2. **If no parameter provided**, respond with:
```
I'll help you plan a Layer 3 function path. I need a user story to trace.

Please provide a user story in one of these formats:
- "I want to [action] and [see result]"
- "When [trigger], [what should happen]"
- A natural language description of a single user-visible action and its outcome

Example: "I want to type a prompt and see generated Rust code"

Tip: You can also invoke directly: `/plan_path "I want to edit existing code by describing changes"`
```

Then wait for the user's input.

## Process

### Phase 1: Read the Resource Registry

Read `specs/schemas/resource_registry.json` fully. This is your only data source — do NOT read schema files, other paths, or architectural docs. The registry contains all 39+ resources across six schema prefixes:

| Prefix | Schema | Description |
|--------|--------|-------------|
| `db-*` | database | Processors, data structures, services, DAOs, verifiers, errors |
| `api-*` | external_api | Endpoints, request handlers, filters, API contracts |
| `mq-*` | message_queue | Process chains, interceptors, execution patterns |
| `ui-*` | ui_state | Modules, components, access controls, data loaders, verifiers |
| `cfg-*` | configuration | Utilities, types, transformers, errors, settings, testing |
| `fs-*` | filesystem | Reserved — currently no entries |

### Phase 2: Parse the User Story

Extract three things from the user story:

1. **Trigger**: The user action or system event that starts this path
   - Example: "User types a prompt in the session loop" → trigger is a UI action on `ui-k9m2` (module)

2. **Expected outcome**: The observable result the user sees when the path completes
   - Example: "sees generated Rust code" → terminal condition is compiled code visible to user

3. **Path name**: Derive a kebab-case name from the story
   - Example: "I want to type a prompt and see generated Rust code" → `generate-code-from-prompt`

Present your parsing to the user:
```
From your user story, I've extracted:

Trigger: [description] (likely involves [UUID candidates])
Outcome: [description]
Path name: [kebab-case-name]

Does this capture the intent correctly?
```

### Phase 3: Identify Relevant Resources

Match the story's steps to resources in the registry. For each step you're mentally sketching:

1. **What data does this step read or write?** → Look for `db-*`, `fs-*` resources
2. **What external systems does it call?** → Look for `api-*` resources
3. **What events does it produce or consume?** → Look for `mq-*` resources
4. **What UI surfaces does it update?** → Look for `ui-*` resources
5. **What configuration or shared types does it use?** → Look for `cfg-*` resources
6. **What can go wrong?** → Look for error definition resources (`db-x7j4`, `cfg-c8j4`)

Build the Resource References table with ONLY the resources this path touches. Do not include resources that are irrelevant to this specific path.

### Phase 4: Handle Escalation (Missing Resources)

If a step needs a resource that doesn't exist in the registry:

1. **Do NOT modify `specs/schemas/resource_registry.json`** — that is a separate Schema Store operation
2. **Propose the new resource** to the user:

```
This path needs a resource that doesn't exist in the registry:

PROPOSED RESOURCE:
  UUID: <schema-prefix>-<4-char-suffix>  [PROPOSED]
  Schema: <schema type>
  Name: <descriptive name>
  Description: <what it represents>

Should I include this as [PROPOSED] in the path and continue?
Note: You'll need to add it to the registry separately before this path can be implemented.
```

3. If confirmed, include the resource in the Resource References table with a `[PROPOSED]` marker
4. If the user wants to add it to the registry first, pause and let them do so, then re-read the registry

### Phase 5: Plan the Step Sequence

Construct a linear sequence of steps from trigger to terminal condition. Each step must have:

- **Number and name**: e.g., `1. **Parse intent from prompt**`
- **Input**: What this step receives, referencing UUIDs where applicable
- **Process**: What transformation happens (WHAT, not HOW — no code, no algorithms)
- **Output**: What this step produces
- **Error**: What can go wrong, referencing error definition UUIDs

**Rules:**
- Steps reference resources by UUID only — never by implementation path or filename
- Each step has exactly one primary transformation
- The sequence is linear — branches become error handling within a step, not separate paths
- Duplication with other paths is acceptable — each path owns its own steps
- No implementation details — describe transformations, not algorithms

Present the step sequence to the user for review before writing the file.

### Phase 6: Define Terminal Condition and Feedback Loops

**Terminal condition**: What the user observes when the path completes successfully. This must be concrete and testable — not "the system processes the request" but "the user sees compiled Rust code matching their prompt."

**Feedback loops**: Any bounded retry mechanisms within the path. Rules:
- Every loop MUST have a max retry count
- Loops operate on shrinking subsets (only the broken parts), not the full output
- If no retries are needed, state "None — this path is strictly linear"

### Phase 7: Write the Path File

Write the path to `specs/orchestration/<path-name>.md` using this exact template:

```markdown
# PATH: <kebab-case-name>

**Layer:** 3 (Function Path)
**Priority:** P<0-3>
**Version:** 1

## Trigger

<Description of what starts this path — a user action or system event>

## Resource References

| UUID | Name | Role in this path |
|------|------|-------------------|
| `cfg-a1b2` | config_store | Example: stores configuration state |

**UUID format (REQUIRED — parser rejects anything else):**
- Backtick-wrapped: `` `xx-xxxx` `` or `` `xxx-xxxx` ``
- Prefix: 2-3 lowercase letters (category: `cfg`, `api`, `db`, `fn`, `ui`, `fs`, `mq`)
- Hyphen, then exactly 4 alphanumeric chars (e.g. `a1b2`, `q7v1`)
- Name column: single word, no spaces

## Steps

1. **<Step name>**
   - Input: <what comes in, with UUID refs where applicable>
   - Process: <what transformation happens>
   - Output: <what this step produces>
   - Error: <what can fail> -> `<error-uuid>` (<error type>)

2. **<Step name>**
   ...

## Terminal Condition

<Concrete, observable result. What the user sees/receives when all steps complete.>

## Feedback Loops

<Bounded retry mechanisms, or "None — this path is strictly linear.">
```

**Priority assignment:**
- P0: Core user-facing functionality (the main thing the system does)
- P1: Important secondary flows (common but not primary)
- P2: Edge cases, admin flows, error recovery
- P3: Nice-to-haves, optimization paths

### Phase 8: Create Version Tracking

After writing the path file:

1. Create the version directory: `paths/<path-name>/`
2. Copy the path to: `paths/<path-name>/v1.md`
3. Create `paths/<path-name>/history.jsonl` with the initial entry:

```jsonl
{"version":1,"timestamp":"<ISO-8601>","reason":"initial","steps":<step-count>,"resources":["<uuid1>","<uuid2>",...]}
```

### Phase 9: Beads Integration

1. Check for existing beads issues: `bd list --status=open`
2. If a related issue exists, link to it
3. If creating a new path warrants tracking: `bd create --title="Path: <path-name>" --description="Layer 3 function path for: <user story>" --type=task --priority=2`

## Important Guidelines

1. **Minimal context**: Read ONLY `specs/schemas/resource_registry.json`. Do not read other paths, schema files, or architectural docs unless the user explicitly asks you to.

2. **UUID-only references**: Never reference a resource by its implementation path. Always use the UUID from the registry.

3. **One path per invocation**: Each `/plan_path` call produces exactly one path for exactly one user story. If the user story is too large (multiple screens, multiple actors, multiple sessions), help them decompose it into smaller stories first.

4. **Duplication is correct**: If this path needs a step that another path also has, that is fine. Each path owns its own implementation. No shared function reasoning.

5. **No implementation details**: Describe WHAT happens at each step, not HOW. No code snippets, no algorithm choices, no language-specific details. The path is a planning artifact, not a spec.

6. **Interactive process**: Present your understanding at each phase and get user confirmation before proceeding to the next. Don't write the full path in one shot.

7. **Escalation over guessing**: If you're unsure whether a resource exists for something, check the registry. If it's not there, escalate — don't silently omit it or invent an implicit dependency.

## Reference

The existing manually-written paths are in `specs/orchestration/`:
- `generate_code.md` — the first path (Cycle 0), 10 steps, 17 resources
- `apply_edit.md` — incremental edit path

These are your ground truth for output format and level of detail.
