------------------------ MODULE one_shot_loop ------------------------
(*
 * One-Shot Loop Lifecycle — Instantiation of the State Machine template.
 *
 * Models the core one-shot loop algorithm:
 *   idle             → querying_context:    behavior ID received
 *   querying_context → prompting_llm:       context assembled
 *   prompting_llm    → extracting_fragment: LLM response received
 *   extracting_fragment → compiling:        PlusCal fragment extracted
 *   compiling        → composing:           PlusCal compiled to TLA+
 *   composing        → verifying:           composed with existing specs
 *   verifying        → routing:             TLC result available
 *   routing          → done:                TLC passed
 *   routing          → idle:                first failure (retry)
 *   routing          → failed:              second consecutive failure
 *   verifying        → translating_error:   TLC found counterexample
 *   translating_error → routing:            error translated to PlusCal concepts
 *
 * Invariants:
 *   MutualExclusionOnCompose — cannot call compose while compose is mid-operation
 *   TwoFailureLimit          — after two consecutive failures, must go to failed
 *   DeterministicRouting     — pass/retry/fail routing is deterministic
 *   ValidState               — current_state is always in StateSet
 *   BoundedExecution         — step_count never exceeds MaxSteps
 *
 * Two-phase action model: mutate primary state, then update derived.
 *)

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,            \* bound for model checking
    MaxRetries           \* max retries before failure (should be 1 for 2-failure limit)

(* --algorithm OneShotLoop

variables
    current_state = "idle",
    consecutive_failures = 0,
    compose_busy = FALSE,     \* mutex: composition engine is mid-operation
    composed_specs = {},      \* set of spec IDs that have been composed
    tlc_passed = FALSE,       \* latest TLC result
    has_counterexample = FALSE,
    step_count = 0,
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    \* --- State validity ---
    StateSet == {"idle", "querying_context", "prompting_llm",
                 "extracting_fragment", "compiling", "composing",
                 "verifying", "translating_error", "routing",
                 "done", "failed"}
    ValidState == current_state \in StateSet

    \* --- Mutual exclusion on compose ---
    \* Cannot be in composing state while compose_busy is already TRUE
    \* from a prior incomplete operation. compose_busy is set TRUE only
    \* when entering composing, and cleared on leaving.
    MutualExclusionOnCompose == dirty = TRUE \/
        (current_state = "composing" => compose_busy = TRUE)

    \* --- Two consecutive failures must lead to failed ---
    TwoFailureLimit == dirty = TRUE \/
        (consecutive_failures > MaxRetries => current_state \in {"failed", "routing"})

    \* --- Deterministic routing: result is determined by tlc_passed + consecutive_failures ---
    \* (structural: each routing branch has a unique guard)
    DeterministicRouting == dirty = TRUE \/
        (current_state = "done" => tlc_passed = TRUE)

    \* --- Bounded execution ---
    BoundedExecution == step_count <= MaxSteps

    \* --- Derived consistency ---
    DerivedConsistency == dirty = TRUE \/
        (current_state = "done" => consecutive_failures = 0)

end define;

fair process loop = "main"
begin
    MainLoop:
        while current_state \notin {"done", "failed"} /\ step_count < MaxSteps do
            either
                \* --- Receive behavior ID: idle → querying_context ---
                ReceiveBehavior:
                    if current_state = "idle" then
                        current_state := "querying_context";
                        dirty := TRUE;
                        op := "receive_behavior";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "receive_skip";
                        result := "error";
                    end if;
            or
                \* --- Query context: querying_context → prompting_llm ---
                QueryContext:
                    if current_state = "querying_context" then
                        current_state := "prompting_llm";
                        dirty := TRUE;
                        op := "query_context";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "query_skip";
                        result := "error";
                    end if;
            or
                \* --- LLM response: prompting_llm → extracting_fragment ---
                ReceiveResponse:
                    if current_state = "prompting_llm" then
                        current_state := "extracting_fragment";
                        dirty := TRUE;
                        op := "receive_response";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "response_skip";
                        result := "error";
                    end if;
            or
                \* --- Extract PlusCal: extracting_fragment → compiling ---
                ExtractFragment:
                    if current_state = "extracting_fragment" then
                        current_state := "compiling";
                        dirty := TRUE;
                        op := "extract_fragment";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "extract_skip";
                        result := "error";
                    end if;
            or
                \* --- Compile PlusCal: compiling → composing ---
                CompilePlusCal:
                    if current_state = "compiling" then
                        current_state := "composing";
                        compose_busy := TRUE;
                        dirty := TRUE;
                        op := "compile";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "compile_skip";
                        result := "error";
                    end if;
            or
                \* --- Compose specs: composing → verifying ---
                ComposeSpecs:
                    if current_state = "composing" /\ compose_busy = TRUE then
                        composed_specs := composed_specs \union {"new_spec"};
                        compose_busy := FALSE;
                        current_state := "verifying";
                        dirty := TRUE;
                        op := "compose";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "compose_skip";
                        result := "error";
                    end if;
            or
                \* --- TLC verification: verifying → routing or translating_error ---
                RunTLC:
                    if current_state = "verifying" then
                        either
                            \* TLC passes
                            tlc_passed := TRUE;
                            has_counterexample := FALSE;
                            current_state := "routing";
                            dirty := TRUE;
                            op := "tlc_pass";
                            result := "pass";
                            step_count := step_count + 1;
                        or
                            \* TLC fails with counterexample
                            tlc_passed := FALSE;
                            has_counterexample := TRUE;
                            current_state := "translating_error";
                            dirty := TRUE;
                            op := "tlc_fail";
                            result := "fail";
                            step_count := step_count + 1;
                        or
                            \* TLC fails without counterexample
                            tlc_passed := FALSE;
                            has_counterexample := FALSE;
                            current_state := "routing";
                            dirty := TRUE;
                            op := "tlc_fail_no_ce";
                            result := "fail";
                            step_count := step_count + 1;
                        end either;
                    else
                        op := "tlc_skip";
                        result := "error";
                    end if;
            or
                \* --- Translate counterexample: translating_error → routing ---
                TranslateError:
                    if current_state = "translating_error" then
                        current_state := "routing";
                        dirty := TRUE;
                        op := "translate_error";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "translate_skip";
                        result := "error";
                    end if;
            or
                \* --- Route result: routing → done | idle (retry) | failed ---
                RouteResult:
                    if current_state = "routing" then
                        if tlc_passed = TRUE then
                            \* PASS: done
                            current_state := "done";
                            consecutive_failures := 0;
                            dirty := TRUE;
                            op := "route_pass";
                            result := "done";
                            step_count := step_count + 1;
                        elsif consecutive_failures > MaxRetries then
                            \* FAIL: too many consecutive failures
                            current_state := "failed";
                            dirty := TRUE;
                            op := "route_fail";
                            result := "requirements_inconsistency";
                            step_count := step_count + 1;
                        else
                            \* RETRY: first failure
                            consecutive_failures := consecutive_failures + 1;
                            current_state := "idle";
                            dirty := TRUE;
                            op := "route_retry";
                            result := "retry";
                            step_count := step_count + 1;
                        end if;
                    else
                        op := "route_skip";
                        result := "error";
                    end if;
            end either;
            \* Phase 2: update derived state
            UpdateDerived:
                dirty := FALSE;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION - placeholder for pcal.trans output
VARIABLES pc, current_state, consecutive_failures, compose_busy, 
          composed_specs, tlc_passed, has_counterexample, step_count, op, 
          result, dirty

(* define statement *)
StateSet == {"idle", "querying_context", "prompting_llm",
             "extracting_fragment", "compiling", "composing",
             "verifying", "translating_error", "routing",
             "done", "failed"}
ValidState == current_state \in StateSet





MutualExclusionOnCompose == dirty = TRUE \/
    (current_state = "composing" => compose_busy = TRUE)


TwoFailureLimit == dirty = TRUE \/
    (consecutive_failures > MaxRetries => current_state \in {"failed", "routing"})



DeterministicRouting == dirty = TRUE \/
    (current_state = "done" => tlc_passed = TRUE)


BoundedExecution == step_count <= MaxSteps


DerivedConsistency == dirty = TRUE \/
    (current_state = "done" => consecutive_failures = 0)


vars == << pc, current_state, consecutive_failures, compose_busy, 
           composed_specs, tlc_passed, has_counterexample, step_count, op, 
           result, dirty >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ consecutive_failures = 0
        /\ compose_busy = FALSE
        /\ composed_specs = {}
        /\ tlc_passed = FALSE
        /\ has_counterexample = FALSE
        /\ step_count = 0
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "MainLoop"]

MainLoop == /\ pc["main"] = "MainLoop"
            /\ IF current_state \notin {"done", "failed"} /\ step_count < MaxSteps
                  THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "ReceiveBehavior"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "QueryContext"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "ReceiveResponse"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "ExtractFragment"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "CompilePlusCal"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "ComposeSpecs"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "RunTLC"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TranslateError"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "RouteResult"]
                  ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
            /\ UNCHANGED << current_state, consecutive_failures, compose_busy, 
                            composed_specs, tlc_passed, has_counterexample, 
                            step_count, op, result, dirty >>

UpdateDerived == /\ pc["main"] = "UpdateDerived"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, consecutive_failures, 
                                 compose_busy, composed_specs, tlc_passed, 
                                 has_counterexample, step_count, op, result >>

ReceiveBehavior == /\ pc["main"] = "ReceiveBehavior"
                   /\ IF current_state = "idle"
                         THEN /\ current_state' = "querying_context"
                              /\ dirty' = TRUE
                              /\ op' = "receive_behavior"
                              /\ result' = "ok"
                              /\ step_count' = step_count + 1
                         ELSE /\ op' = "receive_skip"
                              /\ result' = "error"
                              /\ UNCHANGED << current_state, step_count, dirty >>
                   /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                   /\ UNCHANGED << consecutive_failures, compose_busy, 
                                   composed_specs, tlc_passed, 
                                   has_counterexample >>

QueryContext == /\ pc["main"] = "QueryContext"
                /\ IF current_state = "querying_context"
                      THEN /\ current_state' = "prompting_llm"
                           /\ dirty' = TRUE
                           /\ op' = "query_context"
                           /\ result' = "ok"
                           /\ step_count' = step_count + 1
                      ELSE /\ op' = "query_skip"
                           /\ result' = "error"
                           /\ UNCHANGED << current_state, step_count, dirty >>
                /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                /\ UNCHANGED << consecutive_failures, compose_busy, 
                                composed_specs, tlc_passed, has_counterexample >>

ReceiveResponse == /\ pc["main"] = "ReceiveResponse"
                   /\ IF current_state = "prompting_llm"
                         THEN /\ current_state' = "extracting_fragment"
                              /\ dirty' = TRUE
                              /\ op' = "receive_response"
                              /\ result' = "ok"
                              /\ step_count' = step_count + 1
                         ELSE /\ op' = "response_skip"
                              /\ result' = "error"
                              /\ UNCHANGED << current_state, step_count, dirty >>
                   /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                   /\ UNCHANGED << consecutive_failures, compose_busy, 
                                   composed_specs, tlc_passed, 
                                   has_counterexample >>

ExtractFragment == /\ pc["main"] = "ExtractFragment"
                   /\ IF current_state = "extracting_fragment"
                         THEN /\ current_state' = "compiling"
                              /\ dirty' = TRUE
                              /\ op' = "extract_fragment"
                              /\ result' = "ok"
                              /\ step_count' = step_count + 1
                         ELSE /\ op' = "extract_skip"
                              /\ result' = "error"
                              /\ UNCHANGED << current_state, step_count, dirty >>
                   /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                   /\ UNCHANGED << consecutive_failures, compose_busy, 
                                   composed_specs, tlc_passed, 
                                   has_counterexample >>

CompilePlusCal == /\ pc["main"] = "CompilePlusCal"
                  /\ IF current_state = "compiling"
                        THEN /\ current_state' = "composing"
                             /\ compose_busy' = TRUE
                             /\ dirty' = TRUE
                             /\ op' = "compile"
                             /\ result' = "ok"
                             /\ step_count' = step_count + 1
                        ELSE /\ op' = "compile_skip"
                             /\ result' = "error"
                             /\ UNCHANGED << current_state, compose_busy, 
                                             step_count, dirty >>
                  /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                  /\ UNCHANGED << consecutive_failures, composed_specs, 
                                  tlc_passed, has_counterexample >>

ComposeSpecs == /\ pc["main"] = "ComposeSpecs"
                /\ IF current_state = "composing" /\ compose_busy = TRUE
                      THEN /\ composed_specs' = (composed_specs \union {"new_spec"})
                           /\ compose_busy' = FALSE
                           /\ current_state' = "verifying"
                           /\ dirty' = TRUE
                           /\ op' = "compose"
                           /\ result' = "ok"
                           /\ step_count' = step_count + 1
                      ELSE /\ op' = "compose_skip"
                           /\ result' = "error"
                           /\ UNCHANGED << current_state, compose_busy, 
                                           composed_specs, step_count, dirty >>
                /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                /\ UNCHANGED << consecutive_failures, tlc_passed, 
                                has_counterexample >>

RunTLC == /\ pc["main"] = "RunTLC"
          /\ IF current_state = "verifying"
                THEN /\ \/ /\ tlc_passed' = TRUE
                           /\ has_counterexample' = FALSE
                           /\ current_state' = "routing"
                           /\ dirty' = TRUE
                           /\ op' = "tlc_pass"
                           /\ result' = "pass"
                           /\ step_count' = step_count + 1
                        \/ /\ tlc_passed' = FALSE
                           /\ has_counterexample' = TRUE
                           /\ current_state' = "translating_error"
                           /\ dirty' = TRUE
                           /\ op' = "tlc_fail"
                           /\ result' = "fail"
                           /\ step_count' = step_count + 1
                        \/ /\ tlc_passed' = FALSE
                           /\ has_counterexample' = FALSE
                           /\ current_state' = "routing"
                           /\ dirty' = TRUE
                           /\ op' = "tlc_fail_no_ce"
                           /\ result' = "fail"
                           /\ step_count' = step_count + 1
                ELSE /\ op' = "tlc_skip"
                     /\ result' = "error"
                     /\ UNCHANGED << current_state, tlc_passed, 
                                     has_counterexample, step_count, dirty >>
          /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
          /\ UNCHANGED << consecutive_failures, compose_busy, composed_specs >>

TranslateError == /\ pc["main"] = "TranslateError"
                  /\ IF current_state = "translating_error"
                        THEN /\ current_state' = "routing"
                             /\ dirty' = TRUE
                             /\ op' = "translate_error"
                             /\ result' = "ok"
                             /\ step_count' = step_count + 1
                        ELSE /\ op' = "translate_skip"
                             /\ result' = "error"
                             /\ UNCHANGED << current_state, step_count, dirty >>
                  /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                  /\ UNCHANGED << consecutive_failures, compose_busy, 
                                  composed_specs, tlc_passed, 
                                  has_counterexample >>

RouteResult == /\ pc["main"] = "RouteResult"
               /\ IF current_state = "routing"
                     THEN /\ IF tlc_passed = TRUE
                                THEN /\ current_state' = "done"
                                     /\ consecutive_failures' = 0
                                     /\ dirty' = TRUE
                                     /\ op' = "route_pass"
                                     /\ result' = "done"
                                     /\ step_count' = step_count + 1
                                ELSE /\ IF consecutive_failures > MaxRetries
                                           THEN /\ current_state' = "failed"
                                                /\ dirty' = TRUE
                                                /\ op' = "route_fail"
                                                /\ result' = "requirements_inconsistency"
                                                /\ step_count' = step_count + 1
                                                /\ UNCHANGED consecutive_failures
                                           ELSE /\ consecutive_failures' = consecutive_failures + 1
                                                /\ current_state' = "idle"
                                                /\ dirty' = TRUE
                                                /\ op' = "route_retry"
                                                /\ result' = "retry"
                                                /\ step_count' = step_count + 1
                     ELSE /\ op' = "route_skip"
                          /\ result' = "error"
                          /\ UNCHANGED << current_state, consecutive_failures, 
                                          step_count, dirty >>
               /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
               /\ UNCHANGED << compose_busy, composed_specs, tlc_passed, 
                               has_counterexample >>

loop == MainLoop \/ UpdateDerived \/ ReceiveBehavior \/ QueryContext
           \/ ReceiveResponse \/ ExtractFragment \/ CompilePlusCal
           \/ ComposeSpecs \/ RunTLC \/ TranslateError \/ RouteResult

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == loop
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(loop)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION

===========================================================================
