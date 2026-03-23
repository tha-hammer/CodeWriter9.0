---- MODULE CrossCuttingRulesLoader ----

EXTENDS Integers, FiniteSets, TLC

ValidPositions == {"pre", "post", "wrap"}

GoodRule == [resource_type |-> "database",
             required_outs |-> {"audit_event"},
             position      |-> "wrap"]

BadRule  == [resource_type |-> "database",
             required_outs |-> {"audit_event"},
             position      |-> "INVALID"]

(* --algorithm LoadCrossCuttingRules

variables
    file_exists        = FALSE,
    json_valid         = FALSE,
    all_fields_present = FALSE,
    rules_data         = {},
    result             = {},
    error              = "",
    phase              = "init";

define

    NoPartialResults ==
        error /= "" => result = {}

    ValidPositionOnly ==
        \A r \in result : r["position"] \in ValidPositions

    CompleteFields ==
        \A r \in result :
            /\ "resource_type" \in DOMAIN r
            /\ "required_outs" \in DOMAIN r
            /\ "position"      \in DOMAIN r

    FileAbsentImpliesError ==
        (~file_exists /\ phase \in {"returned", "raised"}) =>
            error = "FileNotFoundError"

    MalformedImpliesError ==
        (file_exists /\ ~json_valid /\ phase \in {"returned", "raised"}) =>
            error = "ValueError"

    InvalidSchemaImpliesError ==
        (file_exists /\ json_valid /\ ~all_fields_present /\
         phase \in {"returned", "raised"}) =>
            error = "ValueError"

    SafeResult ==
        phase \in {"returned", "raised"} =>
            \/ (error = "" /\ \A r \in result : r["position"] \in ValidPositions)
            \/ (error /= "" /\ result = {})

    EmptyRulesValid ==
        (file_exists /\ json_valid /\ all_fields_present /\
         rules_data = {} /\ phase = "returned") =>
            result = {}

    PhaseValid ==
        phase \in {"init", "file_read", "json_parsed",
                   "validating_positions", "positions_valid",
                   "returned", "raised"}

end define;

fair process loader = "main"
begin
    ChooseFileExists:
        either
            file_exists := TRUE;
        or
            file_exists := FALSE;
        end either;

    ChooseJsonValid:
        if file_exists then
            either
                json_valid := TRUE;
            or
                json_valid := FALSE;
            end either;
        end if;

    ChooseSchema:
        if file_exists /\ json_valid then
            either
                all_fields_present := TRUE;
                rules_data := {GoodRule};
            or
                all_fields_present := TRUE;
                rules_data := {BadRule};
            or
                all_fields_present := TRUE;
                rules_data := {};
            or
                all_fields_present := FALSE;
            end either;
        end if;

    ReadFile:
        if ~file_exists then
            error := "FileNotFoundError";
            phase := "raised";
            goto RaisedError;
        else
            phase := "file_read";
        end if;

    ParseJSON:
        if ~json_valid then
            error := "ValueError";
            phase := "raised";
            goto RaisedError;
        else
            phase := "json_parsed";
        end if;

    ValidateRules:
        if ~all_fields_present then
            error := "ValueError";
            phase := "raised";
            goto RaisedError;
        else
            phase := "validating_positions";
        end if;

    CheckPositions:
        if \E r \in rules_data : r["position"] \notin ValidPositions then
            error := "ValueError";
            phase := "raised";
            goto RaisedError;
        else
            phase := "positions_valid";
        end if;

    BuildResult:
        result := rules_data;
        phase  := "returned";
        goto Finish;

    RaisedError:
        assert result = {};
        assert error \in {"FileNotFoundError", "ValueError"};

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e6a39953" /\ chksum(tla) = "f8aced38")
VARIABLES pc, file_exists, json_valid, all_fields_present, rules_data, result, 
          error, phase

(* define statement *)
NoPartialResults ==
    error /= "" => result = {}

ValidPositionOnly ==
    \A r \in result : r["position"] \in ValidPositions

CompleteFields ==
    \A r \in result :
        /\ "resource_type" \in DOMAIN r
        /\ "required_outs" \in DOMAIN r
        /\ "position"      \in DOMAIN r

FileAbsentImpliesError ==
    (~file_exists /\ phase \in {"returned", "raised"}) =>
        error = "FileNotFoundError"

MalformedImpliesError ==
    (file_exists /\ ~json_valid /\ phase \in {"returned", "raised"}) =>
        error = "ValueError"

InvalidSchemaImpliesError ==
    (file_exists /\ json_valid /\ ~all_fields_present /\
     phase \in {"returned", "raised"}) =>
        error = "ValueError"

SafeResult ==
    phase \in {"returned", "raised"} =>
        \/ (error = "" /\ \A r \in result : r["position"] \in ValidPositions)
        \/ (error /= "" /\ result = {})

EmptyRulesValid ==
    (file_exists /\ json_valid /\ all_fields_present /\
     rules_data = {} /\ phase = "returned") =>
        result = {}

PhaseValid ==
    phase \in {"init", "file_read", "json_parsed",
               "validating_positions", "positions_valid",
               "returned", "raised"}


vars == << pc, file_exists, json_valid, all_fields_present, rules_data, 
           result, error, phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ file_exists = FALSE
        /\ json_valid = FALSE
        /\ all_fields_present = FALSE
        /\ rules_data = {}
        /\ result = {}
        /\ error = ""
        /\ phase = "init"
        /\ pc = [self \in ProcSet |-> "ChooseFileExists"]

ChooseFileExists == /\ pc["main"] = "ChooseFileExists"
                    /\ \/ /\ file_exists' = TRUE
                       \/ /\ file_exists' = FALSE
                    /\ pc' = [pc EXCEPT !["main"] = "ChooseJsonValid"]
                    /\ UNCHANGED << json_valid, all_fields_present, rules_data, 
                                    result, error, phase >>

ChooseJsonValid == /\ pc["main"] = "ChooseJsonValid"
                   /\ IF file_exists
                         THEN /\ \/ /\ json_valid' = TRUE
                                 \/ /\ json_valid' = FALSE
                         ELSE /\ TRUE
                              /\ UNCHANGED json_valid
                   /\ pc' = [pc EXCEPT !["main"] = "ChooseSchema"]
                   /\ UNCHANGED << file_exists, all_fields_present, rules_data, 
                                   result, error, phase >>

ChooseSchema == /\ pc["main"] = "ChooseSchema"
                /\ IF file_exists /\ json_valid
                      THEN /\ \/ /\ all_fields_present' = TRUE
                                 /\ rules_data' = {GoodRule}
                              \/ /\ all_fields_present' = TRUE
                                 /\ rules_data' = {BadRule}
                              \/ /\ all_fields_present' = TRUE
                                 /\ rules_data' = {}
                              \/ /\ all_fields_present' = FALSE
                                 /\ UNCHANGED rules_data
                      ELSE /\ TRUE
                           /\ UNCHANGED << all_fields_present, rules_data >>
                /\ pc' = [pc EXCEPT !["main"] = "ReadFile"]
                /\ UNCHANGED << file_exists, json_valid, result, error, phase >>

ReadFile == /\ pc["main"] = "ReadFile"
            /\ IF ~file_exists
                  THEN /\ error' = "FileNotFoundError"
                       /\ phase' = "raised"
                       /\ pc' = [pc EXCEPT !["main"] = "RaisedError"]
                  ELSE /\ phase' = "file_read"
                       /\ pc' = [pc EXCEPT !["main"] = "ParseJSON"]
                       /\ error' = error
            /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                            rules_data, result >>

ParseJSON == /\ pc["main"] = "ParseJSON"
             /\ IF ~json_valid
                   THEN /\ error' = "ValueError"
                        /\ phase' = "raised"
                        /\ pc' = [pc EXCEPT !["main"] = "RaisedError"]
                   ELSE /\ phase' = "json_parsed"
                        /\ pc' = [pc EXCEPT !["main"] = "ValidateRules"]
                        /\ error' = error
             /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                             rules_data, result >>

ValidateRules == /\ pc["main"] = "ValidateRules"
                 /\ IF ~all_fields_present
                       THEN /\ error' = "ValueError"
                            /\ phase' = "raised"
                            /\ pc' = [pc EXCEPT !["main"] = "RaisedError"]
                       ELSE /\ phase' = "validating_positions"
                            /\ pc' = [pc EXCEPT !["main"] = "CheckPositions"]
                            /\ error' = error
                 /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                                 rules_data, result >>

CheckPositions == /\ pc["main"] = "CheckPositions"
                  /\ IF \E r \in rules_data : r["position"] \notin ValidPositions
                        THEN /\ error' = "ValueError"
                             /\ phase' = "raised"
                             /\ pc' = [pc EXCEPT !["main"] = "RaisedError"]
                        ELSE /\ phase' = "positions_valid"
                             /\ pc' = [pc EXCEPT !["main"] = "BuildResult"]
                             /\ error' = error
                  /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                                  rules_data, result >>

BuildResult == /\ pc["main"] = "BuildResult"
               /\ result' = rules_data
               /\ phase' = "returned"
               /\ pc' = [pc EXCEPT !["main"] = "Finish"]
               /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                               rules_data, error >>

RaisedError == /\ pc["main"] = "RaisedError"
               /\ Assert(result = {}, 
                         "Failure of assertion at line 146, column 9.")
               /\ Assert(error \in {"FileNotFoundError", "ValueError"}, 
                         "Failure of assertion at line 147, column 9.")
               /\ pc' = [pc EXCEPT !["main"] = "Finish"]
               /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                               rules_data, result, error, phase >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << file_exists, json_valid, all_fields_present, 
                          rules_data, result, error, phase >>

loader == ChooseFileExists \/ ChooseJsonValid \/ ChooseSchema \/ ReadFile
             \/ ParseJSON \/ ValidateRules \/ CheckPositions \/ BuildResult
             \/ RaisedError \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == loader
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(loader)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
