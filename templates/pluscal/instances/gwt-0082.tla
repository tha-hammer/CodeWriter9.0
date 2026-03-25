---- MODULE CmdPlanReviewDispatch ----

EXTENDS Integers, TLC

(*--algorithm CmdPlanReviewDispatch

variables
    auto_fix \in BOOLEAN,
    dispatch_target = "none",
    called_function = "none",
    exit_code = -1,
    step_count = 0,
    phase = "Idle";

define

    ValidDispatchTarget ==
        dispatch_target \in {"none", "orchestrate_reviews", "orchestrate_reviews_with_correction"}

    ValidPhase ==
        phase \in {"Idle", "Parsed", "Dispatched", "Executed", "Aggregated", "Complete"}

    ValidCalledFunction ==
        called_function \in {"none", "orchestrate_reviews", "orchestrate_reviews_with_correction"}

    DefaultDispatch ==
        ( auto_fix = FALSE /\
          phase \in {"Dispatched", "Executed", "Aggregated", "Complete"} )
            => dispatch_target = "orchestrate_reviews"

    NoCorrection ==
        ( auto_fix = FALSE /\
          phase \in {"Executed", "Aggregated", "Complete"} )
            => called_function = "orchestrate_reviews"

    BackwardCompatible ==
        auto_fix = FALSE
            => ( dispatch_target = "orchestrate_reviews" \/ dispatch_target = "none" )

    NoCorrectionFunctionDispatched ==
        auto_fix = FALSE
            => called_function /= "orchestrate_reviews_with_correction"

    CorrectExitCode ==
        phase = "Complete" => exit_code = 0

    BoundedExecution == step_count <= 10

end define;

fair process cmd = "cmd_plan_review"
begin
    ParseArgs:
        step_count := step_count + 1;
        phase := "Parsed";

    Dispatch:
        step_count := step_count + 1;
        if auto_fix = FALSE then
            dispatch_target := "orchestrate_reviews";
        else
            dispatch_target := "orchestrate_reviews_with_correction";
        end if;
        phase := "Dispatched";

    Execute:
        step_count := step_count + 1;
        if dispatch_target = "orchestrate_reviews" then
            called_function := "orchestrate_reviews";
        else
            called_function := "orchestrate_reviews_with_correction";
        end if;
        phase := "Executed";

    Aggregate:
        step_count := step_count + 1;
        phase := "Aggregated";

    Finish:
        step_count := step_count + 1;
        exit_code := 0;
        phase := "Complete";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f7b888a4" /\ chksum(tla) = "3c251859")
VARIABLES pc, auto_fix, dispatch_target, called_function, exit_code, 
          step_count, phase

(* define statement *)
ValidDispatchTarget ==
    dispatch_target \in {"none", "orchestrate_reviews", "orchestrate_reviews_with_correction"}

ValidPhase ==
    phase \in {"Idle", "Parsed", "Dispatched", "Executed", "Aggregated", "Complete"}

ValidCalledFunction ==
    called_function \in {"none", "orchestrate_reviews", "orchestrate_reviews_with_correction"}

DefaultDispatch ==
    ( auto_fix = FALSE /\
      phase \in {"Dispatched", "Executed", "Aggregated", "Complete"} )
        => dispatch_target = "orchestrate_reviews"

NoCorrection ==
    ( auto_fix = FALSE /\
      phase \in {"Executed", "Aggregated", "Complete"} )
        => called_function = "orchestrate_reviews"

BackwardCompatible ==
    auto_fix = FALSE
        => ( dispatch_target = "orchestrate_reviews" \/ dispatch_target = "none" )

NoCorrectionFunctionDispatched ==
    auto_fix = FALSE
        => called_function /= "orchestrate_reviews_with_correction"

CorrectExitCode ==
    phase = "Complete" => exit_code = 0

BoundedExecution == step_count <= 10


vars == << pc, auto_fix, dispatch_target, called_function, exit_code, 
           step_count, phase >>

ProcSet == {"cmd_plan_review"}

Init == (* Global variables *)
        /\ auto_fix \in BOOLEAN
        /\ dispatch_target = "none"
        /\ called_function = "none"
        /\ exit_code = -1
        /\ step_count = 0
        /\ phase = "Idle"
        /\ pc = [self \in ProcSet |-> "ParseArgs"]

ParseArgs == /\ pc["cmd_plan_review"] = "ParseArgs"
             /\ step_count' = step_count + 1
             /\ phase' = "Parsed"
             /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Dispatch"]
             /\ UNCHANGED << auto_fix, dispatch_target, called_function, 
                             exit_code >>

Dispatch == /\ pc["cmd_plan_review"] = "Dispatch"
            /\ step_count' = step_count + 1
            /\ IF auto_fix = FALSE
                  THEN /\ dispatch_target' = "orchestrate_reviews"
                  ELSE /\ dispatch_target' = "orchestrate_reviews_with_correction"
            /\ phase' = "Dispatched"
            /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Execute"]
            /\ UNCHANGED << auto_fix, called_function, exit_code >>

Execute == /\ pc["cmd_plan_review"] = "Execute"
           /\ step_count' = step_count + 1
           /\ IF dispatch_target = "orchestrate_reviews"
                 THEN /\ called_function' = "orchestrate_reviews"
                 ELSE /\ called_function' = "orchestrate_reviews_with_correction"
           /\ phase' = "Executed"
           /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Aggregate"]
           /\ UNCHANGED << auto_fix, dispatch_target, exit_code >>

Aggregate == /\ pc["cmd_plan_review"] = "Aggregate"
             /\ step_count' = step_count + 1
             /\ phase' = "Aggregated"
             /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Finish"]
             /\ UNCHANGED << auto_fix, dispatch_target, called_function, 
                             exit_code >>

Finish == /\ pc["cmd_plan_review"] = "Finish"
          /\ step_count' = step_count + 1
          /\ exit_code' = 0
          /\ phase' = "Complete"
          /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Done"]
          /\ UNCHANGED << auto_fix, dispatch_target, called_function >>

cmd == ParseArgs \/ Dispatch \/ Execute \/ Aggregate \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == cmd
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(cmd)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
