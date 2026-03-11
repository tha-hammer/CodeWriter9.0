from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ToolResultBlock, TextBlock, ResultMessage, tool, create_sdk_mcp_server
import asyncio
import sys
import subprocess
import json
import time
import platform
import threading
import gc
import resource

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    import msvcrt
else:
    import select
import os
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import structlog

# Configure structured logging for this module
log = structlog.get_logger(__name__)

# =============================================================================
# Memory Management and Client Cleanup Utilities
# =============================================================================
# These utilities address known issues with the Claude Agent SDK where
# Query.close() can hang indefinitely during task group cleanup, causing
# 100%+ CPU usage and memory accumulation in long-running processes.
# See: https://github.com/anthropics/claude-agent-sdk-python/issues/378
# =============================================================================

DISCONNECT_TIMEOUT_SECONDS = 10.0  # Timeout for client disconnect operations


async def safe_disconnect(client: ClaudeSDKClient, timeout: float = DISCONNECT_TIMEOUT_SECONDS) -> bool:
    """Safely disconnect from Claude SDK with timeout to prevent hangs.

    The Claude Agent SDK has a known bug where Query.close() can hang
    indefinitely during task group cleanup. This wrapper adds timeout
    protection to prevent the process from becoming unresponsive.

    Args:
        client: The ClaudeSDKClient instance to disconnect
        timeout: Maximum seconds to wait for disconnect (default: 10.0)

    Returns:
        True if disconnect completed normally, False if timed out
    """
    try:
        await asyncio.wait_for(client.disconnect(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        log.warning("client_disconnect_timeout",
            timeout=timeout,
            message="Client disconnect timed out - forcing cleanup")
        # Attempt to force cancel any hanging task groups
        if hasattr(client, '_tg') and client._tg:
            try:
                client._tg.cancel_scope.cancel()
            except Exception as e:
                log.warning("task_group_cancel_failed", error=str(e))
        return False
    except Exception as e:
        log.warning("client_disconnect_error", error=str(e))
        return False


def log_memory_usage(context: str = ""):
    """Log current memory usage for debugging and monitoring.

    Helps detect memory leaks during long-running plan implementations.
    Only works on Unix-like systems (Linux/WSL).

    Args:
        context: Optional context string to identify where the measurement was taken
    """
    if IS_WINDOWS:
        # Windows doesn't support resource module the same way
        return

    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # On Linux, ru_maxrss is in KB; convert to MB
        max_rss_mb = usage.ru_maxrss / 1024
        log.info("memory_usage",
            context=context,
            max_rss_mb=round(max_rss_mb, 2),
            user_time_s=round(usage.ru_utime, 2),
            system_time_s=round(usage.ru_stime, 2))
    except Exception as e:
        log.debug("memory_usage_check_failed", error=str(e))


def cleanup_between_plans():
    """Perform cleanup between plan iterations to prevent memory accumulation.

    This addresses WSL2 memory exhaustion issues during long-running
    plan implementations by forcing garbage collection and flushing
    any accumulated observability data.
    """
    # Force garbage collection
    collected = gc.collect()
    log.debug("garbage_collection", objects_collected=collected)

    # Flush Langfuse traces if available
    if langfuse is not None:
        try:
            langfuse.flush()
            log.debug("langfuse_flushed")
        except Exception as e:
            log.debug("langfuse_flush_failed", error=str(e))

# Langfuse integration (optional)
try:
    from langfuse import Langfuse, observe
    LANGFUSE_AVAILABLE = bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    observe = lambda **kwargs: lambda f: f  # No-op decorator

# Initialize Langfuse if available
langfuse: Optional["Langfuse"] = None
if LANGFUSE_AVAILABLE:
    try:
        langfuse = Langfuse()
        log.info("langfuse_initialized", host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
    except Exception as e:
        log.warning("langfuse_init_failed", error=str(e))
        langfuse = None


class LangfuseCircuitBreaker:
    """Circuit breaker for Langfuse API calls.

    Implements graceful degradation when Langfuse is unavailable:
    1. First failure: Log warning, continue execution
    2. Repeated failures: Apply exponential backoff
    3. Circuit breaker: After N consecutive failures, stop attempting for cooldown period
    4. Recovery: Automatically attempt again after cooldown
    """

    MAX_FAILURES = 3           # Open circuit after 3 consecutive failures
    COOLDOWN_SECONDS = 300     # 5 minute cooldown when circuit is open
    INITIAL_BACKOFF_MS = 100   # Start with 100ms backoff
    MAX_BACKOFF_MS = 30000     # Cap at 30 seconds

    def __init__(self):
        self.consecutive_failures = 0
        self.circuit_opened_at: float | None = None
        self.current_backoff_ms = self.INITIAL_BACKOFF_MS

    def should_attempt(self) -> bool:
        """Check if we should attempt a Langfuse call."""
        if self.circuit_opened_at is None:
            return True

        elapsed = time.time() - self.circuit_opened_at
        if elapsed >= self.COOLDOWN_SECONDS:
            # Try again after cooldown
            self.circuit_opened_at = None
            self.consecutive_failures = 0
            self.current_backoff_ms = self.INITIAL_BACKOFF_MS
            log.info("langfuse_circuit_closed", message="Circuit breaker recovered after cooldown")
            return True

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        self.consecutive_failures = 0
        self.current_backoff_ms = self.INITIAL_BACKOFF_MS

    def record_failure(self) -> None:
        """Record a failed call."""
        self.consecutive_failures += 1
        self.current_backoff_ms = min(
            self.current_backoff_ms * 2,
            self.MAX_BACKOFF_MS
        )

        if self.consecutive_failures >= self.MAX_FAILURES:
            self.circuit_opened_at = time.time()
            log.warning("langfuse_circuit_opened",
                failures=self.consecutive_failures,
                cooldown_seconds=self.COOLDOWN_SECONDS)


# Global circuit breaker instance for Langfuse
langfuse_circuit_breaker = LangfuseCircuitBreaker()


# ANSI escape codes for terminal colors
class Colors:
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'


def input_with_timeout(prompt: str, timeout: float = 30.0, default: str = "") -> str:
    """Get user input with a timeout. Returns default if timeout expires.

    Args:
        prompt: The prompt to display
        timeout: Seconds to wait for input (default 30)
        default: Value to return on timeout (default empty string)
    """
    print(prompt, end='', flush=True)

    if IS_WINDOWS:
        # Windows implementation using msvcrt and threading
        result = [default]
        input_ready = threading.Event()

        def get_input():
            chars = []
            while not input_ready.is_set():
                if msvcrt.kbhit():
                    char = msvcrt.getwch()
                    if char == '\r':  # Enter key
                        print()  # Move to next line
                        result[0] = ''.join(chars)
                        input_ready.set()
                        return
                    elif char == '\x08':  # Backspace
                        if chars:
                            chars.pop()
                            # Erase character from display
                            print('\b \b', end='', flush=True)
                    else:
                        chars.append(char)
                        print(char, end='', flush=True)
                time.sleep(0.01)  # Small sleep to prevent CPU spinning

        input_thread = threading.Thread(target=get_input, daemon=True)
        input_thread.start()
        input_ready.wait(timeout=timeout)

        if not input_ready.is_set():
            input_ready.set()  # Signal thread to stop
            print(f"\n{Colors.YELLOW}Timeout after {timeout}s - continuing automatically{Colors.ENDC}")
            return default
        return result[0].strip()
    else:
        # Unix implementation using select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().strip()
        else:
            print(f"\n{Colors.YELLOW}Timeout after {timeout}s - continuing automatically{Colors.ENDC}")
            return default


class PlanStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanProgress:
    """Track progress for a single plan file."""
    file_name: str
    path: str
    status: str = PlanStatus.NOT_STARTED.value
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


@dataclass
class SessionState:
    """Persistent state for a TDD implementation session."""
    session_id: str
    started_at: str
    plan_path: str
    plans: list[dict] = field(default_factory=list)
    
    @classmethod
    def create_new(cls, plan_path: str) -> "SessionState":
        """Create a new session state."""
        return cls(
            session_id=str(uuid.uuid4())[:8],
            started_at=datetime.now().isoformat(),
            plan_path=plan_path,
            plans=[]
        )
    
    @classmethod
    def load(cls, state_file: Path) -> "SessionState | None":
        """Load session state from file."""
        if not state_file.exists():
            return None
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"{Colors.RED}Warning: Could not load state file: {e}{Colors.ENDC}")
            return None
    
    def save(self, state_file: Path):
        """Save session state to file."""
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2)
    
    def get_plan(self, file_name: str) -> dict | None:
        """Get plan progress by file name."""
        for plan in self.plans:
            if plan["file_name"] == file_name:
                return plan
        return None
    
    def update_plan(self, file_name: str, **kwargs):
        """Update plan progress."""
        plan = self.get_plan(file_name)
        if plan:
            plan.update(kwargs)
        else:
            self.plans.append({"file_name": file_name, **kwargs})

class TDDPlanImplementer:
    """Reviews TDD plan requirements in a loop, processing each plan file."""

    STATE_FILE_NAME = ".tdd_state.json"

    def __init__(self, req_plan_path: str, options: ClaudeAgentOptions = None):
        self.req_plan_path = Path(req_plan_path)
        self.client = ClaudeSDKClient(options)
        self.plan_files = []
        self.state: SessionState | None = None
        self._state_file = self._get_state_file_path()

    def _get_state_file_path(self) -> Path:
        """Determine where to store the state file."""
        if self.req_plan_path.is_file():
            return self.req_plan_path.parent / self.STATE_FILE_NAME
        else:
            return self.req_plan_path / self.STATE_FILE_NAME

    def load_plans(self):
        """Load plan files from a single file or directory of markdown files."""
        if self.req_plan_path.is_file():
            self.plan_files = [self.req_plan_path]
        elif self.req_plan_path.is_dir():
            all_files = sorted(self.req_plan_path.glob("*.md"))
            # Skip REVIEW files - they are outputs from tdd_plan_review.py
            self.plan_files = [f for f in all_files if not f.stem.endswith("-REVIEW")]
        else:
            raise FileNotFoundError(f"Path not found: {self.req_plan_path}")
        print(f"Loaded {len(self.plan_files)} plan file(s)")

    def load_or_create_state(self) -> bool:
        """Load existing state or create new session. Returns True if resuming."""
        self.state = SessionState.load(self._state_file)
        
        if self.state is not None:
            # Verify state matches current plan path
            if self.state.plan_path == str(self.req_plan_path):
                completed = sum(1 for p in self.state.plans if p.get("status") == PlanStatus.COMPLETED.value)
                in_progress = sum(1 for p in self.state.plans if p.get("status") == PlanStatus.IN_PROGRESS.value)
                print(f"{Colors.GREEN}Resuming session {self.state.session_id} from {self.state.started_at}{Colors.ENDC}")
                print(f"  Progress: {completed}/{len(self.plan_files)} completed, {in_progress} in progress")
                return True
            else:
                print(f"{Colors.YELLOW}Found state for different path, starting fresh{Colors.ENDC}")
                self.state = None
        
        # Create new session
        self.state = SessionState.create_new(str(self.req_plan_path))
        # Initialize plans in state
        for plan_file in self.plan_files:
            self.state.update_plan(
                plan_file.name,
                path=str(plan_file),
                status=PlanStatus.NOT_STARTED.value
            )
        self._save_state()
        print(f"{Colors.GREEN}Started new session {self.state.session_id}{Colors.ENDC}")
        return False

    def _save_state(self):
        """Save current state to disk."""
        if self.state:
            self.state.save(self._state_file)

    def _mark_plan_started(self, plan_file: Path):
        """Mark a plan as in progress."""
        self.state.update_plan(
            plan_file.name,
            path=str(plan_file),
            status=PlanStatus.IN_PROGRESS.value,
            started_at=datetime.now().isoformat()
        )
        self._save_state()

    def _mark_plan_completed(self, plan_file: Path):
        """Mark a plan as completed."""
        self.state.update_plan(
            plan_file.name,
            status=PlanStatus.COMPLETED.value,
            completed_at=datetime.now().isoformat()
        )
        self._save_state()

    def _mark_plan_failed(self, plan_file: Path, error: str):
        """Mark a plan as failed."""
        self.state.update_plan(
            plan_file.name,
            status=PlanStatus.FAILED.value,
            completed_at=datetime.now().isoformat(),
            error=error
        )
        self._save_state()

    def should_skip_plan(self, plan_file: Path) -> bool:
        """Check if a plan should be skipped based on state."""
        plan = self.state.get_plan(plan_file.name)
        if plan and plan.get("status") == PlanStatus.COMPLETED.value:
            return True
        return False

    def track_plans(self):
        """Initialize tracking data structures for all plans."""
        self.plan_checkpoints = {}  # Track checkpoint names per plan
        self.plan_results = []      # Track results
        return self.plan_checkpoints, self.plan_results


    @observe(name="implement_plan")
    async def implement_plan(self, plan_file: Path):
        """Implement a single plan file with Claude and Langfuse tracing.

        The @observe decorator automatically creates spans and tracks token usage
        when Langfuse is available.
        """
        await self.client.connect()
        print("\n" + "="*80)
        print(f"Implementing Plan: {plan_file.name}")
        print("="*80)

        # Log structured event for observability
        log.info("plan_implementation_started",
            plan_file=str(plan_file),
            plan_name=plan_file.stem)

        # Create a detailed prompt for Claude with the plan file path
        prompt = f"""# Implement Plan with Checkpoints

Plan file to implement: {plan_file}

You are tasked with implementing an approved technical plan from `thoughts/searchable/shared/plans/`. These plans contain phases with specific changes and success criteria. This enhanced version includes checkpoint management for better progress tracking and recovery.

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Getting Started

When given a plan path:
- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket (if a ticket is provided) and/or original research and planning document and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Think from a Test Driven Development perspective
- Create a todo list to track your progress
- **Update beads issue status**: If there's a tracked beads issue, run `bd update <id> --status=in_progress`
- **Create a checkpoint** before starting implementation
- Start implementing if you understand what needs to be done

If no plan path provided, ask for one.

## Checkpoint System

### Creating Checkpoints
Before starting implementation work:
```bash
# Create a checkpoint for the current phase
`silmari-oracle checkpoint create "phase_1_initial_setup" "Starting Phase 1: Initial setup and configuration"`
```

### Checkpoint Management
- **Pre-phase checkpoints**: Create before starting each major phase
- **Post-phase checkpoints**: Create after completing verification of each phase
- **Recovery checkpoints**: Create when encountering issues or making significant discoveries
- **Commit checkpoints**: Create before committing changes

### Checkpoint Naming Convention
- `phase_N_description` for phase boundaries
- `recovery_issue_description` for recovery points
- `commit_feature_name` for commit boundaries
- `discovery_finding_name` for significant discoveries

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:
- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- Update checkboxes in the plan as you complete section
- **ALWAYS USE TDD** Write tests - RED GREEN REFACTOR
- **USE ACTUAL DATA** When available, use actual data
- **USE ACTAL LLMs** When testing LLM calls ALWAYS use actual LLM calls unless explicitly told otherwise
- **USE BAML** If any structured or deterministic output is needed YOU MUST USE BAML
- **Create checkpoints at natural stopping points**

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgment matters too.

If you encounter a mismatch:
- **Create a recovery checkpoint** before proceeding
- STOP and think deeply about why the plan can't be followed
- Present the issue clearly:
  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]

  How should I proceed?
  ```

## Verification Approach

After implementing a phase:
- **Create a post-phase checkpoint**
- Run the success criteria checks (usually `make check test` covers everything)
- Fix any issues before proceeding
- Update your progress in both the plan and your todos
- Check off completed items in the plan file itself using Edit
- **Create a commit checkpoint** if ready to commit

Don't let verification interrupt your flow - batch it at natural stopping points.

## Checkpoint-Integrated Workflow

### Phase Implementation Cycle
1. **Pre-phase checkpoint**: `silmari-oracle checkpoint create "phase_N_start" "Starting Phase N: [description]"`
2. Implement phase changes
3. **Post-phase checkpoint**: `silmari-oracle checkpoint create "phase_N_complete" "Completed Phase N: [description]"`
4. Run verification tests
5. **Recovery checkpoint** (if issues found): `silmari-oracle checkpoint create "phase_N_recovery" "Recovery point for Phase N issues"`
6. Fix issues and repeat verification
7. Update plan checkboxes
8. **Commit checkpoint** (if ready): `silmari-oracle checkpoint create "commit_phase_N" "Ready to commit Phase N changes"`

### Recovery and Resumption
- Use `silmari-oracle checkpoint list` to see available recovery points
- Use `silmari-oracle checkpoint restore <checkpoint_name>` to restore to a specific point
- Checkpoints preserve both code state and plan progress

## If You Get Stuck

When something isn't working as expected:
- **Create a recovery checkpoint** immediately
- First, make sure you've read and understood all the relevant code
- Second, make sure your test was properly constructed, verify props, data model, data shapes
- Consider if the codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance

Use sub-tasks sparingly - mainly for targeted debugging or exploring unfamiliar territory.

## Resuming Work

If the plan has existing checkmarks:
- **Check available checkpoints** with `silmari-oracle checkpoint list`
- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off
- **Restore to appropriate checkpoint** if needed
- **ALWAYS USE TDD** Write tests - RED GREEN REFACTOR
- **USE ACTUAL DATA** When available, use actual data
- **USE ACTAL LLMs** When testing LLM calls ALWAYS use actual LLM calls unless explicitly told otherwise
- **USE BAML** If any structured or deterministic output is needed YOU MUST USE BAML

## Commit Integration

When ready to commit:
1. **Create commit checkpoint**: `silmari-oracle checkpoint create "commit_ready" "Ready to commit changes"`
2. Follow the commit process from `.claude/commands/commit.md`
3. **Create post-commit checkpoint**: `silmari-oracle checkpoint create "commit_complete" "Successfully committed changes"`

## Checkpoint Commands Reference

```bash
# Create a checkpoint
silmari-oracle checkpoint create <name> <description>

# List all checkpoints
silmari-oracle checkpoint list

# Restore to a checkpoint
silmari-oracle checkpoint restore <checkpoint_name>

# Clean up old checkpoints
silmari-oracle checkpoint cleanup [--keep-recent N]
```

Remember: You're implementing a solution with proper checkpoint management, not just checking boxes. Keep the end goal in mind, maintain forward momentum, and use checkpoints to ensure you can always recover and resume work effectively.


## Beads Integration

When implementation is complete:
1. **Sync beads**: Run `bd sync` to commit any beads changes
2. **Close the issue**: If all work is done, run `bd close <id>`
3. **Update dependencies**: If this unblocks other work, check `bd blocked` to see what's now ready
"""

        # Send to Claude
        await self.client.query(prompt)

        # Collect and display response
        print(f"\n{'─'*80}")
        print("Claude's Review:")
        print(f"{'─'*80}\n")

        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"{Colors.BLUE}{block.text}{Colors.ENDC}\n", end="")
                    elif isinstance(block, ToolResultBlock):
                        print(f"{Colors.YELLOW}Tool: {block.content}{Colors.ENDC}\n")   # Tool being called
                    elif hasattr(block, "name"):
                        print(f"{Colors.YELLOW}Tool: {block.name}{Colors.ENDC}\n")   # Tool being called
            elif isinstance(message, ResultMessage):
                print(f"{Colors.GREEN}Done: {message.subtype}{Colors.ENDC}\n")      # Final result
        print("\n")

        # Use safe disconnect with timeout to prevent SDK hang bug
        await safe_disconnect(self.client)

        # Log structured completion event
        log.info("plan_implementation_completed",
            plan_file=str(plan_file),
            plan_name=plan_file.stem)

        print(f"\n{'='*80}")
        print("Plan Implementation Complete")
        print(f"{'='*80}")

    @observe(name="validate_plan")
    async def validate_plan(self, plan_file: Path):
        """Validate a single plan file with Claude and Langfuse tracing.

        The @observe decorator automatically creates spans and tracks token usage
        when Langfuse is available.
        """
        await self.client.connect()
        print("\n" + "="*80)
        print(f"Validating Plan: {plan_file.name}")
        print("="*80)

        # Log structured event for observability
        log.info("plan_validation_started",
            plan_file=str(plan_file),
            plan_name=plan_file.stem)

        # Create a detailed prompt for Claude with the plan file path
        prompt = f"""# Validate Plan

You are tasked with validating that an implementation plan was correctly executed, verifying all success criteria and identifying any deviations or issues.

Validate the plan file: {plan_file}

Use Haiku subagents for file searches, grep, ripgrep and other file tasks.
Use up to 10 Sonnet subagents for researching files, codepaths, and getting line numbers.
Strive to keep the main context for the actual plan, we don't want to run out of context window before it is time to write the file or be at the last 10% at the time of writing.
Use beads and agent mail with subagents to track progress and store paths, filenames:line numbers
Have subagents write to file to save the main context window.

## Initial Setup

When invoked:
1. **Determine context** - Are you in an existing conversation or starting fresh?
   - If existing: Review what was implemented in this session
   - If fresh: Need to discover what was done through git and codebase analysis

2. **Locate the plan**:
   - If plan path provided, use it
   - Otherwise, search recent commits for plan references or ask user

3. **Gather implementation evidence**:
   ```bash
   # Check recent commits
   git log --oneline -n 20
   git diff HEAD~N..HEAD  # Where N covers implementation commits

   # Run comprehensive checks
   cd $(git rev-parse --show-toplevel) && make check test
   ```

## Validation Process

### Step 1: Context Discovery

If starting fresh or need more context:

1. **Read the implementation plan** completely
2. **Identify what should have changed**:
   - List all files that should be modified
   - Note all success criteria (automated and manual)
   - Identify key functionality to verify

3. **Spawn parallel research tasks** to discover implementation:
   ```
   Task 1 - Verify database changes:
   Research if migration [N] was added and schema changes match plan.
   Check: migration files, schema version, table structure
   Return: What was implemented vs what plan specified

   Task 2 - Verify code changes:
   Find all modified files related to [feature].
   Compare actual changes to plan specifications.
   Return: File-by-file comparison of planned vs actual

   Task 3 - Verify test coverage:
   Check if tests were added/modified as specified.
   Run test commands and capture results.
   Return: Test status and any missing coverage
   ```

### Step 2: Systematic Validation

For each phase in the plan:

1. **Check completion status**:
   - Look for checkmarks in the plan (- [x])
   - Verify the actual code matches claimed completion

2. **Run automated verification**:
   - Execute each command from "Automated Verification"
   - Document pass/fail status
   - If failures, investigate root cause

3. **Assess manual criteria**:
   - List what needs manual testing
   - Provide clear steps for user verification

4. **Think deeply about edge cases**:
   - Were error conditions handled?
   - Are there missing validations?
   - Could the implementation break existing functionality?

### Step 3: Generate Validation Report

Create comprehensive validation summary:

```markdown
## Validation Report: [Plan Name]

### Implementation Status
✓ Phase 1: [Name] - Fully implemented
✓ Phase 2: [Name] - Fully implemented
⚠️ Phase 3: [Name] - Partially implemented (see issues)

### Automated Verification Results
✓ Build passes: `make build`
✓ Tests pass: `make test`
✗ Linting issues: `make lint` (3 warnings)

### Code Review Findings

#### Matches Plan:
- Database migration correctly adds [table]
- API endpoints implement specified methods
- Error handling follows plan

#### Deviations from Plan:
- Used different variable names in [file:line]
- Added extra validation in [file:line] (improvement)

#### Potential Issues:
- Missing index on foreign key could impact performance
- No rollback handling in migration

### Manual Testing Required:
1. UI functionality:
   - [ ] Verify [feature] appears correctly
   - [ ] Test error states with invalid input

2. Integration:
   - [ ] Confirm works with existing [component]
   - [ ] Check performance with large datasets

### Recommendations:
- Address linting warnings before merge
- Consider adding integration test for [scenario]
- Document new API endpoints
```

## Working with Existing Context

If you were part of the implementation:
- Review the conversation history
- Check your todo list for what was completed
- Focus validation on work done in this session
- Be honest about any shortcuts or incomplete items

## Important Guidelines

1. **Be thorough but practical** - Focus on what matters
2. **Run all automated checks** - Don't skip verification commands
3. **Document everything** - Both successes and issues
4. **Think critically** - Question if the implementation truly solves the problem
5. **Consider maintenance** - Will this be maintainable long-term?

## Validation Checklist

Always verify:
- [ ] All phases marked complete are actually done
- [ ] Automated tests pass
- [ ] Code follows existing patterns
- [ ] No regressions introduced
- [ ] Error handling is robust
- [ ] Documentation updated if needed
- [ ] Manual test steps are clear

## Relationship to Other Commands


The validation works best after commits are made, as it can analyze the git history to understand what was implemented.

Remember: Good validation catches issues before they reach production. Be constructive but thorough in identifying gaps or improvements.


## Beads Integration

After successful validation:
1. **Close the issue**: If validation passes completely, run `bd close <id>` to mark the work as complete
2. **Sync beads**: Run `bd sync` to commit any beads changes
3. **Check unblocked work**: Run `bd blocked` to see if this completion unblocks other issues
4. **Review ready work**: Run `bd ready` to see what's now available to work on next

Plan file to validate: {plan_file}
Save or append the validation report to: `VALIDATION_REPORT.md`
"""
        # Send to Claude
        await self.client.query(prompt)

        # Collect and display response
        print(f"\n{'─'*80}")
        print("Claude's Validation:")
        print(f"{'─'*80}\n")

        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"{Colors.BLUE}{block.text}{Colors.ENDC}\n", end="")
                    elif hasattr(block, "name"):
                        print(f"{Colors.YELLOW}Tool: {block.name}{Colors.ENDC}\n")   # Tool being called
            elif isinstance(message, ResultMessage):
                print(f"{Colors.GREEN}Done: {message.subtype}{Colors.ENDC}\n")      # Final result
        print("\n")

        # Use safe disconnect with timeout to prevent SDK hang bug
        await safe_disconnect(self.client)

        # Log structured completion event
        log.info("plan_validation_completed",
            plan_file=str(plan_file),
            plan_name=plan_file.stem)

        print(f"\n{'='*80}")
        print("Plan Validation Complete")
        print(f"{'='*80}")

    async def run_all_plans(self):
        """Iterate through all plan files and implement each one.

        This method includes memory management to prevent WSL2 crashes during
        long-running plan implementations:
        - Logs memory usage before/after each plan
        - Forces garbage collection between plans
        - Flushes observability data to prevent accumulation
        """
        total_plans = len(self.plan_files)
        log_memory_usage(f"session_start_{total_plans}_plans")

        for idx, plan_file in enumerate(self.plan_files, 1):
            print(f"\n{'='*80}")
            print(f"Processing Plan {idx}/{total_plans}: {plan_file.name}")
            print(f"{'='*80}\n")

            # Log memory at start of each plan
            log_memory_usage(f"plan_{idx}_start")

            # Check if plan should be skipped (already completed)
            if self.should_skip_plan(plan_file):
                print(f"{Colors.YELLOW}Skipping {plan_file.name} (already completed){Colors.ENDC}")
                continue

            # Mark plan as in progress before starting
            self._mark_plan_started(plan_file)

            try:
                print(f"{Colors.GREEN}Implementing {plan_file.name}...{Colors.ENDC}\n")
                await self.implement_plan(plan_file)
                print(f"{Colors.GREEN}Implementation complete for {plan_file.name}{Colors.ENDC}\n")

                print(f"{Colors.GREEN}Validating {plan_file.name}...{Colors.ENDC}\n")
                await self.validate_plan(plan_file)
                print(f"{Colors.GREEN}Validation complete for {plan_file.name}{Colors.ENDC}\n")

                # Mark plan as completed after successful implementation and validation
                self._mark_plan_completed(plan_file)

            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Interrupted! Progress saved. Run again to resume.{Colors.ENDC}")
                raise
            except Exception as e:
                self._mark_plan_failed(plan_file, str(e))
                print(f"{Colors.RED}Failed: {e}{Colors.ENDC}")
                raise
            finally:
                # CRITICAL: Cleanup after each plan to prevent memory accumulation
                # This addresses the Claude SDK hang bug and WSL2 OOM issues
                log_memory_usage(f"plan_{idx}_before_cleanup")
                cleanup_between_plans()
                log_memory_usage(f"plan_{idx}_after_cleanup")

            # Wait for user to continue or exit (auto-continue after 30s)
            if idx < total_plans:
                user_input = input_with_timeout(
                    "\nPress Enter to continue to next plan, or type 'exit' to quit (auto-continue in 30s): ",
                    timeout=30.0,
                    default=""  # Empty string = continue
                )
                if user_input.lower() == 'exit':
                    print(f"{Colors.YELLOW}Exiting. Progress saved. Run again to resume.{Colors.ENDC}")
                    break

        # Final cleanup
        cleanup_between_plans()
        log_memory_usage("session_end")

        # Check if all plans completed
        completed = sum(1 for p in self.state.plans if p.get("status") == PlanStatus.COMPLETED.value)
        if completed == total_plans:
            print(f"\n{'='*80}")
            print(f"{Colors.GREEN}All Plans Complete!{Colors.ENDC}")
            print(f"{'='*80}")
            # Optionally clean up state file after full completion
            # self._state_file.unlink(missing_ok=True)
        else:
            print(f"\n{'='*80}")
            print(f"Session paused: {completed}/{total_plans} plans completed")
            print(f"Run again to resume from where you left off.")
            print(f"{'='*80}")

# Method 2: In-Process SDK MCP Tools
# These tools are defined inline and wrapped with create_sdk_mcp_server()

@tool(
    "extract_functions",
    "Extract function definitions from source files using chain-map",
    {"file_path": str},
)
async def extract_functions(args: dict[str, Any]) -> dict[str, Any]:
    """Extract functions from a file using chain-map."""
    file_path = args.get("file_path", "")
    print(f"\n[DEBUG] extract_functions called with: {file_path}", file=sys.stderr)
    if not file_path:
        return {
            "content": [{"type": "text", "text": "Error: file_path is required"}]
        }
    try:
        print(f"[DEBUG] Running chain-map extract...", file=sys.stderr)
        result = subprocess.run(
            ["npx", "chain-map", "extract", "--json", str(file_path)],
            capture_output=True,
            text=True,
            timeout=30,
            shell=IS_WINDOWS,  # Required on Windows for npx
        )
        print(f"[DEBUG] chain-map exit code: {result.returncode}", file=sys.stderr)
        if result.returncode == 0:
            print(f"[DEBUG] Successfully extracted {len(result.stdout)} bytes", file=sys.stderr)
            return {"content": [{"type": "text", "text": result.stdout}]}
        else:
            print(f"[DEBUG] chain-map stderr: {result.stderr}", file=sys.stderr)
            return {"content": [{"type": "text", "text": f"Error: {result.stderr}"}]}
    except Exception as e:
        print(f"[DEBUG] Exception: {str(e)}", file=sys.stderr)
        return {"content": [{"type": "text", "text": f"Failed to extract: {str(e)}"}]}


@tool(
    "list_plan_phases",
    "List all phases from a markdown plan file",
    {"plan_file": str},
)
async def list_plan_phases(args: dict[str, Any]) -> dict[str, Any]:
    """Extract and list phases from a markdown plan file."""
    plan_file = args.get("plan_file", "")
    if not plan_file:
        return {
            "content": [{"type": "text", "text": "Error: plan_file is required"}]
        }
    try:
        with open(str(plan_file), 'r') as f:
            content = f.read()

        # Extract phase headings (## Phase or ## Phase X:)
        lines = content.split('\n')
        phases = []
        for i, line in enumerate(lines):
            if line.startswith('## Phase'):
                phases.append({"line": i, "heading": line})

        return {"content": [{"type": "text", "text": json.dumps(phases, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Failed to list phases: {str(e)}"}]}


@tool(
    "get_completion_status",
    "Check which items are marked as complete in a plan",
    {"plan_file": str},
)
async def get_completion_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get completion status (checkmarks) from a markdown file."""
    plan_file = args.get("plan_file", "")
    if not plan_file:
        return {
            "content": [{"type": "text", "text": "Error: plan_file is required"}]
        }
    try:
        with open(str(plan_file), 'r') as f:
            content = f.read()

        # Count completed items (- [x]) vs incomplete (- [ ])
        completed = content.count('- [x]')
        incomplete = content.count('- [ ]')
        total = completed + incomplete

        status = {
            "total_items": total,
            "completed": completed,
            "incomplete": incomplete,
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }

        return {"content": [{"type": "text", "text": json.dumps(status, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Failed to get status: {str(e)}"}]}


# Create the SDK MCP server with custom tools
code_analysis_tools = create_sdk_mcp_server(
    name="code-analysis",
    version="1.0.0",
    tools=[extract_functions, list_plan_phases, get_completion_status]
)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="TDD Plan Implementer - implements plans with Claude")
    parser.add_argument("plan_path", nargs="?", help="Path to plan file or directory")
    parser.add_argument("--reset", action="store_true", help="Reset progress and start fresh")
    parser.add_argument("--status", action="store_true", help="Show current progress and exit")
    args = parser.parse_args()
    
    # Get path from command line argument or user input
    if args.plan_path:
        req_plan_path = Path(args.plan_path)
    else:
        user_path = input("Enter path to plan file or directory: ").strip()
        req_plan_path = Path(user_path)

    # Configure Claude SDK options with MCP tools
    # Method 2: In-process SDK MCP server with custom tools
    options = ClaudeAgentOptions(
        model="opus",
        mcp_servers={"code-analysis": code_analysis_tools},
        allowed_tools=[
            "Read",
            "Write",
            "Bash",
            "Grep",
            "Glob",
            "Edit",
            "LS",
            "Cat",
            "Head",
            "Tail",
            "Sort",
            "Uniq",
            "mcp__code-analysis__extract_functions",
            "mcp__code-analysis__list_plan_phases",
            "mcp__code-analysis__get_completion_status",
        ],
        permission_mode="bypassPermissions",
        system_prompt="""You are an expert developer and CTO.

  IMPORTANT: You have access to specialized MCP tools for code analysis:
  - mcp__code-analysis__list_plan_phases: Use this to parse plan files
  - mcp__code-analysis__get_completion_status: Use this to check completion status
  - mcp__code-analysis__extract_functions: Use this to analyze code

  Prefer these specialized tools over generic file reading when applicable.""",
    )

    implementer = TDDPlanImplementer(req_plan_path, options)
    implementer.load_plans()
    
    # Handle --reset flag
    if args.reset:
        if implementer._state_file.exists():
            implementer._state_file.unlink()
            print(f"{Colors.YELLOW}Progress reset. Starting fresh.{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}No previous state found.{Colors.ENDC}")
    
    implementer.load_or_create_state()
    
    # Handle --status flag
    if args.status:
        print(f"\n{'='*60}")
        print(f"Session: {implementer.state.session_id}")
        print(f"Started: {implementer.state.started_at}")
        print(f"{'='*60}")
        for plan in implementer.state.plans:
            status = plan.get("status", "unknown")
            status_color = {
                "completed": Colors.GREEN,
                "in_progress": Colors.YELLOW,
                "failed": Colors.RED,
                "not_started": Colors.ENDC
            }.get(status, Colors.ENDC)
            print(f"  {status_color}[{status:12}]{Colors.ENDC} {plan['file_name']}")
        return
    
    implementer.track_plans()
    await implementer.run_all_plans()

if __name__ == "__main__":
    asyncio.run(main())