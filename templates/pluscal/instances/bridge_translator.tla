------------------------ MODULE bridge_translator ------------------------
(*
 * Bridge Translator — Instantiation of the State Machine template.
 *
 * Models the mechanical spec-to-code translation pipeline:
 *   idle                → parsing_spec:          TLA+ spec received
 *   parsing_spec        → translating_vars:      spec parsed into AST
 *   parsing_spec        → failed:                spec cannot be parsed
 *   translating_vars    → translating_actions:    state vars → data_structures
 *   translating_actions → translating_invariants: actions → operations
 *   translating_invariants → translating_traces:  invariants → verifiers + assertions
 *   translating_traces  → validating_output:      traces → test scenarios
 *   validating_output   → done:                   all outputs conform to schemas
 *   validating_output   → failed:                 output does not conform
 *
 * Invariants:
 *   OutputConformsToSchema  — completed artifacts match target shapes
 *   TranslationOrder        — translators execute in dependency order
 *   NoPartialOutput         — done implies all translators produced output
 *   InputPreserved          — input_hash immutable after parsing
 *   ValidState, BoundedExecution
 *
 * Two-phase action model: mutate primary state, then update derived.
 *)

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,            \* bound for model checking
    NumVariables,        \* number of state variables in the input spec (>= 0)
    NumActions,          \* number of actions in the input spec (>= 0)
    NumInvariants        \* number of invariants in the input spec (>= 0)

(* --algorithm BridgeTranslator

variables
    current_state = "idle",
    \* Input spec components (set during parsing)
    vars_found = 0,
    actions_found = 0,
    invariants_found = 0,
    has_traces = FALSE,
    \* Output artifacts (set during translation)
    data_structures_out = 0,
    operations_out = 0,
    verifiers_out = 0,
    assertions_out = 0,
    scenarios_out = 0,
    \* Conformance tracking
    schema_valid = TRUE,
    input_hash = 0,
    \* Control
    step_count = 0,
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    \* --- State validity ---
    StateSet == {"idle", "parsing_spec", "translating_vars",
                 "translating_actions", "translating_invariants",
                 "translating_traces", "validating_output",
                 "done", "failed"}
    ValidState == current_state \in StateSet

    \* --- Bounded execution ---
    BoundedExecution == step_count <= MaxSteps

    \* --- Output conforms to schema shapes ---
    OutputConformsToSchema == dirty = TRUE \/
        (current_state = "done" =>
            /\ data_structures_out = vars_found
            /\ operations_out = actions_found
            /\ verifiers_out = invariants_found
            /\ assertions_out = invariants_found)

    \* --- Translation order ---
    TranslationOrder == dirty = TRUE \/
        (/\ (current_state = "translating_actions" => data_structures_out = vars_found)
         /\ (current_state = "translating_invariants" => operations_out = actions_found)
         /\ (current_state = "translating_traces" => verifiers_out = invariants_found))

    \* --- No partial output ---
    NoPartialOutput == dirty = TRUE \/
        (current_state = "done" =>
            /\ data_structures_out = vars_found
            /\ operations_out = actions_found
            /\ verifiers_out = invariants_found
            /\ assertions_out = invariants_found)

    \* --- Input preserved ---
    InputPreserved == dirty = TRUE \/
        (current_state \notin {"idle", "parsing_spec"} => input_hash > 0)

end define;

fair process translator = "main"
begin
    MainLoop:
        while current_state \notin {"done", "failed"} /\ step_count < MaxSteps do
            either
                \* --- Receive spec: idle → parsing_spec ---
                ReceiveSpec:
                    if current_state = "idle" then
                        current_state := "parsing_spec";
                        dirty := TRUE;
                        op := "receive_spec";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "receive_skip";
                        result := "error";
                    end if;
            or
                \* --- Parse spec: parsing_spec → translating_vars or failed ---
                ParseSpec:
                    if current_state = "parsing_spec" then
                        vars_found := NumVariables;
                        actions_found := NumActions;
                        invariants_found := NumInvariants;
                        has_traces := (NumInvariants > 0);
                        input_hash := NumVariables + NumActions + NumInvariants + 1;
                        dirty := TRUE;
                        op := "parsed";
                        step_count := step_count + 1;
                    ParseDecide:
                        if NumVariables >= 0 /\ NumActions >= 0 /\ NumInvariants >= 0 then
                            current_state := "translating_vars";
                            result := "ok";
                        else
                            current_state := "failed";
                            result := "parse_error";
                        end if;
                        dirty := FALSE;
                    else
                        op := "parse_skip";
                        result := "error";
                    end if;
            or
                \* --- Translate vars: translating_vars → translating_actions ---
                TranslateVars:
                    if current_state = "translating_vars" then
                        data_structures_out := vars_found;
                        current_state := "translating_actions";
                        dirty := TRUE;
                        op := "translated_vars";
                        result := "ok";
                        step_count := step_count + 1;
                    TranslateVarsDone:
                        dirty := FALSE;
                    else
                        op := "vars_skip";
                        result := "error";
                    end if;
            or
                \* --- Translate actions: translating_actions → translating_invariants ---
                TranslateActions:
                    if current_state = "translating_actions" then
                        operations_out := actions_found;
                        current_state := "translating_invariants";
                        dirty := TRUE;
                        op := "translated_actions";
                        result := "ok";
                        step_count := step_count + 1;
                    TranslateActionsDone:
                        dirty := FALSE;
                    else
                        op := "actions_skip";
                        result := "error";
                    end if;
            or
                \* --- Translate invariants: translating_invariants → translating_traces ---
                TranslateInvariants:
                    if current_state = "translating_invariants" then
                        verifiers_out := invariants_found;
                        assertions_out := invariants_found;
                        current_state := "translating_traces";
                        dirty := TRUE;
                        op := "translated_invariants";
                        result := "ok";
                        step_count := step_count + 1;
                    TranslateInvariantsDone:
                        dirty := FALSE;
                    else
                        op := "invariants_skip";
                        result := "error";
                    end if;
            or
                \* --- Translate traces: translating_traces → validating_output ---
                TranslateTraces:
                    if current_state = "translating_traces" then
                        if has_traces then
                            scenarios_out := invariants_found;
                        else
                            scenarios_out := 0;
                        end if;
                        current_state := "validating_output";
                        dirty := TRUE;
                        op := "translated_traces";
                        result := "ok";
                        step_count := step_count + 1;
                    TranslateTracesDone:
                        dirty := FALSE;
                    else
                        op := "traces_skip";
                        result := "error";
                    end if;
            or
                \* --- Validate output: validating_output → done or failed ---
                ValidateOutput:
                    if current_state = "validating_output" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                    ValidateDecide:
                        if data_structures_out = vars_found
                           /\ operations_out = actions_found
                           /\ verifiers_out = invariants_found
                           /\ assertions_out = invariants_found then
                            schema_valid := TRUE;
                            current_state := "done";
                            op := "validated";
                            result := "success";
                        else
                            schema_valid := FALSE;
                            current_state := "failed";
                            op := "validation_failed";
                            result := "schema_mismatch";
                        end if;
                        dirty := FALSE;
                    else
                        op := "validate_skip";
                        result := "error";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)

\* BEGIN TRANSLATION - placeholder for pcal.trans output
VARIABLES pc, current_state, vars_found, actions_found, invariants_found, 
          has_traces, data_structures_out, operations_out, verifiers_out, 
          assertions_out, scenarios_out, schema_valid, input_hash, step_count, 
          op, result, dirty

(* define statement *)
StateSet == {"idle", "parsing_spec", "translating_vars",
             "translating_actions", "translating_invariants",
             "translating_traces", "validating_output",
             "done", "failed"}
ValidState == current_state \in StateSet


BoundedExecution == step_count <= MaxSteps


OutputConformsToSchema == dirty = TRUE \/
    (current_state = "done" =>
        /\ data_structures_out = vars_found
        /\ operations_out = actions_found
        /\ verifiers_out = invariants_found
        /\ assertions_out = invariants_found)


TranslationOrder == dirty = TRUE \/
    (/\ (current_state = "translating_actions" => data_structures_out = vars_found)
     /\ (current_state = "translating_invariants" => operations_out = actions_found)
     /\ (current_state = "translating_traces" => verifiers_out = invariants_found))


NoPartialOutput == dirty = TRUE \/
    (current_state = "done" =>
        /\ data_structures_out = vars_found
        /\ operations_out = actions_found
        /\ verifiers_out = invariants_found
        /\ assertions_out = invariants_found)


InputPreserved == dirty = TRUE \/
    (current_state \notin {"idle", "parsing_spec"} => input_hash > 0)


vars == << pc, current_state, vars_found, actions_found, invariants_found, 
           has_traces, data_structures_out, operations_out, verifiers_out, 
           assertions_out, scenarios_out, schema_valid, input_hash, 
           step_count, op, result, dirty >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ vars_found = 0
        /\ actions_found = 0
        /\ invariants_found = 0
        /\ has_traces = FALSE
        /\ data_structures_out = 0
        /\ operations_out = 0
        /\ verifiers_out = 0
        /\ assertions_out = 0
        /\ scenarios_out = 0
        /\ schema_valid = TRUE
        /\ input_hash = 0
        /\ step_count = 0
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "MainLoop"]

MainLoop == /\ pc["main"] = "MainLoop"
            /\ IF current_state \notin {"done", "failed"} /\ step_count < MaxSteps
                  THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "ReceiveSpec"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "ParseSpec"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TranslateVars"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TranslateActions"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TranslateInvariants"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TranslateTraces"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "ValidateOutput"]
                  ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
            /\ UNCHANGED << current_state, vars_found, actions_found, 
                            invariants_found, has_traces, data_structures_out, 
                            operations_out, verifiers_out, assertions_out, 
                            scenarios_out, schema_valid, input_hash, 
                            step_count, op, result, dirty >>

ReceiveSpec == /\ pc["main"] = "ReceiveSpec"
               /\ IF current_state = "idle"
                     THEN /\ current_state' = "parsing_spec"
                          /\ dirty' = TRUE
                          /\ op' = "receive_spec"
                          /\ result' = "ok"
                          /\ step_count' = step_count + 1
                     ELSE /\ op' = "receive_skip"
                          /\ result' = "error"
                          /\ UNCHANGED << current_state, step_count, dirty >>
               /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
               /\ UNCHANGED << vars_found, actions_found, invariants_found, 
                               has_traces, data_structures_out, operations_out, 
                               verifiers_out, assertions_out, scenarios_out, 
                               schema_valid, input_hash >>

ParseSpec == /\ pc["main"] = "ParseSpec"
             /\ IF current_state = "parsing_spec"
                   THEN /\ vars_found' = NumVariables
                        /\ actions_found' = NumActions
                        /\ invariants_found' = NumInvariants
                        /\ has_traces' = (NumInvariants > 0)
                        /\ input_hash' = NumVariables + NumActions + NumInvariants + 1
                        /\ dirty' = TRUE
                        /\ op' = "parsed"
                        /\ step_count' = step_count + 1
                        /\ pc' = [pc EXCEPT !["main"] = "ParseDecide"]
                        /\ UNCHANGED result
                   ELSE /\ op' = "parse_skip"
                        /\ result' = "error"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << vars_found, actions_found, 
                                        invariants_found, has_traces, 
                                        input_hash, step_count, dirty >>
             /\ UNCHANGED << current_state, data_structures_out, 
                             operations_out, verifiers_out, assertions_out, 
                             scenarios_out, schema_valid >>

ParseDecide == /\ pc["main"] = "ParseDecide"
               /\ IF NumVariables >= 0 /\ NumActions >= 0 /\ NumInvariants >= 0
                     THEN /\ current_state' = "translating_vars"
                          /\ result' = "ok"
                     ELSE /\ current_state' = "failed"
                          /\ result' = "parse_error"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
               /\ UNCHANGED << vars_found, actions_found, invariants_found, 
                               has_traces, data_structures_out, operations_out, 
                               verifiers_out, assertions_out, scenarios_out, 
                               schema_valid, input_hash, step_count, op >>

TranslateVars == /\ pc["main"] = "TranslateVars"
                 /\ IF current_state = "translating_vars"
                       THEN /\ data_structures_out' = vars_found
                            /\ current_state' = "translating_actions"
                            /\ dirty' = TRUE
                            /\ op' = "translated_vars"
                            /\ result' = "ok"
                            /\ step_count' = step_count + 1
                            /\ pc' = [pc EXCEPT !["main"] = "TranslateVarsDone"]
                       ELSE /\ op' = "vars_skip"
                            /\ result' = "error"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << current_state, data_structures_out, 
                                            step_count, dirty >>
                 /\ UNCHANGED << vars_found, actions_found, invariants_found, 
                                 has_traces, operations_out, verifiers_out, 
                                 assertions_out, scenarios_out, schema_valid, 
                                 input_hash >>

TranslateVarsDone == /\ pc["main"] = "TranslateVarsDone"
                     /\ dirty' = FALSE
                     /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                     /\ UNCHANGED << current_state, vars_found, actions_found, 
                                     invariants_found, has_traces, 
                                     data_structures_out, operations_out, 
                                     verifiers_out, assertions_out, 
                                     scenarios_out, schema_valid, input_hash, 
                                     step_count, op, result >>

TranslateActions == /\ pc["main"] = "TranslateActions"
                    /\ IF current_state = "translating_actions"
                          THEN /\ operations_out' = actions_found
                               /\ current_state' = "translating_invariants"
                               /\ dirty' = TRUE
                               /\ op' = "translated_actions"
                               /\ result' = "ok"
                               /\ step_count' = step_count + 1
                               /\ pc' = [pc EXCEPT !["main"] = "TranslateActionsDone"]
                          ELSE /\ op' = "actions_skip"
                               /\ result' = "error"
                               /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                               /\ UNCHANGED << current_state, operations_out, 
                                               step_count, dirty >>
                    /\ UNCHANGED << vars_found, actions_found, 
                                    invariants_found, has_traces, 
                                    data_structures_out, verifiers_out, 
                                    assertions_out, scenarios_out, 
                                    schema_valid, input_hash >>

TranslateActionsDone == /\ pc["main"] = "TranslateActionsDone"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << current_state, vars_found, 
                                        actions_found, invariants_found, 
                                        has_traces, data_structures_out, 
                                        operations_out, verifiers_out, 
                                        assertions_out, scenarios_out, 
                                        schema_valid, input_hash, step_count, 
                                        op, result >>

TranslateInvariants == /\ pc["main"] = "TranslateInvariants"
                       /\ IF current_state = "translating_invariants"
                             THEN /\ verifiers_out' = invariants_found
                                  /\ assertions_out' = invariants_found
                                  /\ current_state' = "translating_traces"
                                  /\ dirty' = TRUE
                                  /\ op' = "translated_invariants"
                                  /\ result' = "ok"
                                  /\ step_count' = step_count + 1
                                  /\ pc' = [pc EXCEPT !["main"] = "TranslateInvariantsDone"]
                             ELSE /\ op' = "invariants_skip"
                                  /\ result' = "error"
                                  /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                                  /\ UNCHANGED << current_state, verifiers_out, 
                                                  assertions_out, step_count, 
                                                  dirty >>
                       /\ UNCHANGED << vars_found, actions_found, 
                                       invariants_found, has_traces, 
                                       data_structures_out, operations_out, 
                                       scenarios_out, schema_valid, input_hash >>

TranslateInvariantsDone == /\ pc["main"] = "TranslateInvariantsDone"
                           /\ dirty' = FALSE
                           /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                           /\ UNCHANGED << current_state, vars_found, 
                                           actions_found, invariants_found, 
                                           has_traces, data_structures_out, 
                                           operations_out, verifiers_out, 
                                           assertions_out, scenarios_out, 
                                           schema_valid, input_hash, 
                                           step_count, op, result >>

TranslateTraces == /\ pc["main"] = "TranslateTraces"
                   /\ IF current_state = "translating_traces"
                         THEN /\ IF has_traces
                                    THEN /\ scenarios_out' = invariants_found
                                    ELSE /\ scenarios_out' = 0
                              /\ current_state' = "validating_output"
                              /\ dirty' = TRUE
                              /\ op' = "translated_traces"
                              /\ result' = "ok"
                              /\ step_count' = step_count + 1
                              /\ pc' = [pc EXCEPT !["main"] = "TranslateTracesDone"]
                         ELSE /\ op' = "traces_skip"
                              /\ result' = "error"
                              /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                              /\ UNCHANGED << current_state, scenarios_out, 
                                              step_count, dirty >>
                   /\ UNCHANGED << vars_found, actions_found, invariants_found, 
                                   has_traces, data_structures_out, 
                                   operations_out, verifiers_out, 
                                   assertions_out, schema_valid, input_hash >>

TranslateTracesDone == /\ pc["main"] = "TranslateTracesDone"
                       /\ dirty' = FALSE
                       /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                       /\ UNCHANGED << current_state, vars_found, 
                                       actions_found, invariants_found, 
                                       has_traces, data_structures_out, 
                                       operations_out, verifiers_out, 
                                       assertions_out, scenarios_out, 
                                       schema_valid, input_hash, step_count, 
                                       op, result >>

ValidateOutput == /\ pc["main"] = "ValidateOutput"
                  /\ IF current_state = "validating_output"
                        THEN /\ dirty' = TRUE
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["main"] = "ValidateDecide"]
                             /\ UNCHANGED << op, result >>
                        ELSE /\ op' = "validate_skip"
                             /\ result' = "error"
                             /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                             /\ UNCHANGED << step_count, dirty >>
                  /\ UNCHANGED << current_state, vars_found, actions_found, 
                                  invariants_found, has_traces, 
                                  data_structures_out, operations_out, 
                                  verifiers_out, assertions_out, scenarios_out, 
                                  schema_valid, input_hash >>

ValidateDecide == /\ pc["main"] = "ValidateDecide"
                  /\ IF data_structures_out = vars_found
                        /\ operations_out = actions_found
                        /\ verifiers_out = invariants_found
                        /\ assertions_out = invariants_found
                        THEN /\ schema_valid' = TRUE
                             /\ current_state' = "done"
                             /\ op' = "validated"
                             /\ result' = "success"
                        ELSE /\ schema_valid' = FALSE
                             /\ current_state' = "failed"
                             /\ op' = "validation_failed"
                             /\ result' = "schema_mismatch"
                  /\ dirty' = FALSE
                  /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                  /\ UNCHANGED << vars_found, actions_found, invariants_found, 
                                  has_traces, data_structures_out, 
                                  operations_out, verifiers_out, 
                                  assertions_out, scenarios_out, input_hash, 
                                  step_count >>

translator == MainLoop \/ ReceiveSpec \/ ParseSpec \/ ParseDecide
                 \/ TranslateVars \/ TranslateVarsDone \/ TranslateActions
                 \/ TranslateActionsDone \/ TranslateInvariants
                 \/ TranslateInvariantsDone \/ TranslateTraces
                 \/ TranslateTracesDone \/ ValidateOutput \/ ValidateDecide

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == translator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(translator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION

===========================================================================
