------------------------- MODULE StateMachineTemplate -------------------------
(*
 * State Machine PlusCal Template — CodeWriter9.0
 *
 * Reusable template for domains with enum states, guarded transitions,
 * and bypass conditions. Modeled after execution_patterns schema:
 *   conditions  → trigger predicates (when to fire)
 *   rules       → execution rules (how transitions work)
 *   bypass      → skip conditions (when to skip even if triggered)
 *
 * Fill-in markers:
 *   {{FILL:MODULE_NAME}}        — TLA+ module name
 *   {{FILL:STATE_SET}}          — set of possible states (enum)
 *   {{FILL:INITIAL_STATE}}      — starting state
 *   {{FILL:TRANSITION_SET}}     — set of [from, to, guard, action] transitions
 *   {{FILL:BYPASS_CONDITIONS}}  — conditions that skip transitions entirely
 *   {{FILL:TERMINAL_STATES}}    — states with no outgoing transitions
 *   {{FILL:PRIMARY_INVARIANTS}} — domain-specific invariants
 *   {{FILL:CUSTOM_ACTIONS}}     — additional domain-specific actions
 *
 * Two-phase action model (same pattern as CRUD template).
 *)

EXTENDS Integers, FiniteSets, TLC

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
    op = "idle",
    result = "none",
    bypassed = FALSE;

define
    \* --- Invariants ---

    \* Current state is always valid
    ValidState == current_state \in StateSet

    \* No illegal transitions: current state was reachable from InitialState
    \* (enforced structurally by the algorithm)

    \* Terminal states have no outgoing transitions
    \* (checked by the transition guard logic)

    \* Bounded execution
    BoundedExecution == step_count <= MaxSteps

    \* {{FILL:PRIMARY_INVARIANTS}}

end define;

fair process actor = "main"
begin
    Loop:
        while current_state \notin TerminalStates /\ step_count < MaxSteps do
            either
                \* --- Attempt transition ---
                \* {{FILL:TRANSITION_SET}} — one branch per transition
                \* Pattern:
                \*   TransitionLabel:
                \*     if guard_condition then
                \*       current_state := target_state;
                \*       step_count := step_count + 1;
                \*       op := "transitioned";
                \*       result := target_state;
                \*     else
                \*       op := "guard_failed";
                \*       result := "error";
                \*     end if;
                skip;
            or
                \* --- Check bypass ---
                \* {{FILL:BYPASS_CONDITIONS}}
                \* Pattern:
                \*   BypassLabel:
                \*     if bypass_condition then
                \*       bypassed := TRUE;
                \*       current_state := terminal_state;
                \*       op := "bypassed";
                \*     end if;
                skip;
            end either;
        end while;
end process;

end algorithm; *)

===========================================================================
