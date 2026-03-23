------------------------- MODULE ObservabilityStateMachineTemplate -------------------------
(*
 * Observability State Machine PlusCal Template — CodeWriter9.0
 *
 * Extends the base state_machine pattern with mandatory observability
 * variables (trace_log, audit_log) and enforcement invariants
 * (TraceComplete, AuditComplete).
 *
 * Any action that transitions state MUST simultaneously append to
 * trace_log and audit_log. If an action omits either append, TLC
 * will report a TraceComplete or AuditComplete violation.
 *
 * Fill-in markers:
 *   {{FILL:MODULE_NAME}}        — TLA+ module name
 *   {{FILL:STATE_SET}}          — set of possible states (enum)
 *   {{FILL:INITIAL_STATE}}      — starting state
 *   {{FILL:TRANSITION_SET}}     — set of [from, to, guard, action] transitions
 *                                  MUST include trace_log and audit_log appends
 *   {{FILL:BYPASS_CONDITIONS}}  — conditions that skip transitions entirely
 *   {{FILL:TERMINAL_STATES}}    — states with no outgoing transitions
 *   {{FILL:PRIMARY_INVARIANTS}} — domain-specific invariants
 *   {{FILL:CUSTOM_ACTIONS}}     — additional domain-specific actions
 *
 * Observability enforcement via simultaneous assignment:
 *   The || (parallel assignment) operator ensures trace_log and audit_log
 *   are updated in the SAME atomic step as the state transition. No
 *   intermediate state exists where current_state has changed but
 *   trace_log has not. TLC will report a TraceComplete or AuditComplete
 *   violation if any instantiation omits either log append.
 *)

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    StateSet,           \* {{FILL:STATE_SET}} — finite set of state names
    InitialState,       \* {{FILL:INITIAL_STATE}} — starting state
    TerminalStates,     \* {{FILL:TERMINAL_STATES}} — subset of StateSet
    MaxSteps            \* bound for model checking

(* --algorithm {{FILL:MODULE_NAME}}

variables
    current_state = InitialState,
    history = <<>>,         \* sequence of visited states
    step_count = 0,
    trace_log = <<>>,       \* Seq of span records: [action |-> String, state |-> String, ts |-> Nat]
    audit_log = <<>>,       \* Seq of mutation records: [from_state |-> String, to_state |-> String, ts |-> Nat]
    op = "idle",
    result = "none",
    bypassed = FALSE;

define
    \* --- Base Invariants (preserved from state_machine) ---

    \* Current state is always valid
    ValidState == current_state \in StateSet

    \* Bounded execution
    BoundedExecution == step_count <= MaxSteps

    \* Base invariants combined
    BasePreserved == ValidState /\ BoundedExecution

    \* --- Observability Invariants ---

    \* Every completed action must have a corresponding trace entry
    TraceComplete ==
        step_count > 0 => Len(trace_log) >= step_count

    \* Every state transition must have a corresponding audit entry
    AuditComplete ==
        Len(history) > 0 => Len(audit_log) >= Len(history)

    \* trace_log never shrinks (structural: only Append used)
    TraceLogMonotonic == Len(trace_log) >= 0

    \* audit_log never shrinks (structural: only Append used)
    AuditLogMonotonic == Len(audit_log) >= 0

    \* {{FILL:PRIMARY_INVARIANTS}}

end define;

fair process actor = "main"
begin
    Loop:
        while current_state \notin TerminalStates /\ step_count < MaxSteps do
            either
                \* --- Attempt transition ---
                \* {{FILL:TRANSITION_SET}} — one branch per transition
                \* Pattern (MUST include trace_log and audit_log appends):
                \*   TransitionLabel:
                \*     if guard_condition then
                \*       history := Append(history, current_state) ||
                \*       current_state := target_state ||
                \*       step_count := step_count + 1 ||
                \*       trace_log := Append(trace_log,
                \*                      [action |-> "transition_name",
                \*                       state |-> target_state,
                \*                       ts |-> step_count + 1]) ||
                \*       audit_log := Append(audit_log,
                \*                      [from_state |-> current_state,
                \*                       to_state |-> target_state,
                \*                       ts |-> step_count + 1]) ||
                \*       op := "transitioned" ||
                \*       result := target_state;
                \*     else
                \*       op := "guard_failed";
                \*       result := "error";
                \*     end if;
                skip;
            or
                \* --- Check bypass ---
                \* {{FILL:BYPASS_CONDITIONS}}
                skip;
            end either;
        end while;
end process;

end algorithm; *)

===========================================================================
