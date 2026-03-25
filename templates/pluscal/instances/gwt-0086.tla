---- MODULE RunReviewPassAutoFix ----

EXTENDS Integers, TLC

MaxSteps == 10

Verdicts == {"pass", "fail", "warning", "unknown"}

(* --algorithm RunReviewPassAutoFix

variables
    auto_fix_active   \in BOOLEAN,
    user_json_flag    \in BOOLEAN,
    json_mode         = FALSE,
    query_constructed = FALSE,
    stdout_written    = FALSE,
    result_captured   = FALSE,
    cost_captured     = FALSE,
    verdict           = "none",
    phase             = "init",
    step_count        = 0;

define

    JsonModeForced ==
        (auto_fix_active /\ query_constructed) => json_mode = TRUE

    NoStreaming ==
        json_mode => ~stdout_written

    ResultCaptured ==
        (phase = "complete") => result_captured

    CostAccumulated ==
        result_captured => cost_captured

    VerdictParsed ==
        (phase = "complete") => verdict \in Verdicts

    BoundedExecution ==
        step_count <= MaxSteps

    TypeOK ==
        /\ json_mode         \in BOOLEAN
        /\ query_constructed \in BOOLEAN
        /\ stdout_written    \in BOOLEAN
        /\ result_captured   \in BOOLEAN
        /\ cost_captured     \in BOOLEAN
        /\ verdict           \in (Verdicts \union {"none"})
        /\ phase             \in {"init", "init_done", "query_constructed",
                                  "messages_processed", "result_captured", "complete"}
        /\ step_count        \in 0..MaxSteps

end define;

fair process runner = "runner"
begin
    InitPass:
        if auto_fix_active then
            json_mode := TRUE;
        else
            json_mode := user_json_flag;
        end if;
        phase      := "init_done";
        step_count := step_count + 1;

    ConstructQuery:
        query_constructed := TRUE;
        phase      := "query_constructed";
        step_count := step_count + 1;

    ProcessAssistantMsg:
        if json_mode then
            stdout_written := FALSE;
        else
            stdout_written := TRUE;
        end if;
        phase      := "messages_processed";
        step_count := step_count + 1;

    CaptureResult:
        result_captured := TRUE;
        cost_captured   := TRUE;
        phase      := "result_captured";
        step_count := step_count + 1;

    ParseVerdict:
        with v \in Verdicts do
            verdict := v;
        end with;
        phase      := "complete";
        step_count := step_count + 1;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b332f1e8" /\ chksum(tla) = "f75bd6f1")
VARIABLES pc, auto_fix_active, user_json_flag, json_mode, query_constructed, 
          stdout_written, result_captured, cost_captured, verdict, phase, 
          step_count

(* define statement *)
JsonModeForced ==
    (auto_fix_active /\ query_constructed) => json_mode = TRUE

NoStreaming ==
    json_mode => ~stdout_written

ResultCaptured ==
    (phase = "complete") => result_captured

CostAccumulated ==
    result_captured => cost_captured

VerdictParsed ==
    (phase = "complete") => verdict \in Verdicts

BoundedExecution ==
    step_count <= MaxSteps

TypeOK ==
    /\ json_mode         \in BOOLEAN
    /\ query_constructed \in BOOLEAN
    /\ stdout_written    \in BOOLEAN
    /\ result_captured   \in BOOLEAN
    /\ cost_captured     \in BOOLEAN
    /\ verdict           \in (Verdicts \union {"none"})
    /\ phase             \in {"init", "init_done", "query_constructed",
                              "messages_processed", "result_captured", "complete"}
    /\ step_count        \in 0..MaxSteps


vars == << pc, auto_fix_active, user_json_flag, json_mode, query_constructed, 
           stdout_written, result_captured, cost_captured, verdict, phase, 
           step_count >>

ProcSet == {"runner"}

Init == (* Global variables *)
        /\ auto_fix_active \in BOOLEAN
        /\ user_json_flag \in BOOLEAN
        /\ json_mode = FALSE
        /\ query_constructed = FALSE
        /\ stdout_written = FALSE
        /\ result_captured = FALSE
        /\ cost_captured = FALSE
        /\ verdict = "none"
        /\ phase = "init"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "InitPass"]

InitPass == /\ pc["runner"] = "InitPass"
            /\ IF auto_fix_active
                  THEN /\ json_mode' = TRUE
                  ELSE /\ json_mode' = user_json_flag
            /\ phase' = "init_done"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["runner"] = "ConstructQuery"]
            /\ UNCHANGED << auto_fix_active, user_json_flag, query_constructed, 
                            stdout_written, result_captured, cost_captured, 
                            verdict >>

ConstructQuery == /\ pc["runner"] = "ConstructQuery"
                  /\ query_constructed' = TRUE
                  /\ phase' = "query_constructed"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["runner"] = "ProcessAssistantMsg"]
                  /\ UNCHANGED << auto_fix_active, user_json_flag, json_mode, 
                                  stdout_written, result_captured, 
                                  cost_captured, verdict >>

ProcessAssistantMsg == /\ pc["runner"] = "ProcessAssistantMsg"
                       /\ IF json_mode
                             THEN /\ stdout_written' = FALSE
                             ELSE /\ stdout_written' = TRUE
                       /\ phase' = "messages_processed"
                       /\ step_count' = step_count + 1
                       /\ pc' = [pc EXCEPT !["runner"] = "CaptureResult"]
                       /\ UNCHANGED << auto_fix_active, user_json_flag, 
                                       json_mode, query_constructed, 
                                       result_captured, cost_captured, verdict >>

CaptureResult == /\ pc["runner"] = "CaptureResult"
                 /\ result_captured' = TRUE
                 /\ cost_captured' = TRUE
                 /\ phase' = "result_captured"
                 /\ step_count' = step_count + 1
                 /\ pc' = [pc EXCEPT !["runner"] = "ParseVerdict"]
                 /\ UNCHANGED << auto_fix_active, user_json_flag, json_mode, 
                                 query_constructed, stdout_written, verdict >>

ParseVerdict == /\ pc["runner"] = "ParseVerdict"
                /\ \E v \in Verdicts:
                     verdict' = v
                /\ phase' = "complete"
                /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["runner"] = "Finish"]
                /\ UNCHANGED << auto_fix_active, user_json_flag, json_mode, 
                                query_constructed, stdout_written, 
                                result_captured, cost_captured >>

Finish == /\ pc["runner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["runner"] = "Done"]
          /\ UNCHANGED << auto_fix_active, user_json_flag, json_mode, 
                          query_constructed, stdout_written, result_captured, 
                          cost_captured, verdict, phase, step_count >>

runner == InitPass \/ ConstructQuery \/ ProcessAssistantMsg
             \/ CaptureResult \/ ParseVerdict \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == runner
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(runner)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
