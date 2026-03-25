---- MODULE gwt_0083_cmd_plan_review_auto_fix ----

EXTENDS Integers, FiniteSets, TLC

AutoFix    == TRUE
MaxRetries == 2

DispatchTarget == {"orchestrate_reviews", "orchestrate_reviews_with_correction"}

(* --algorithm CmdPlanReviewDispatch

variables
    auto_fix              = AutoFix,
    max_retries_in        = MaxRetries,
    args_parsed           = FALSE,
    dispatch_target       = "none",
    forwarded_max_retries = 0,
    dispatched            = FALSE;

define

    AutoFixDispatch ==
        ~dispatched \/
        ~(auto_fix = TRUE) \/
        (dispatch_target = "orchestrate_reviews_with_correction")

    NoAutoFixDispatch ==
        ~dispatched \/
        ~(auto_fix = FALSE) \/
        (dispatch_target = "orchestrate_reviews")

    MaxRetriesForwarded ==
        ~dispatched \/
        ~(dispatch_target = "orchestrate_reviews_with_correction") \/
        (forwarded_max_retries = max_retries_in)

    MutualExclusion ==
        ~dispatched \/
        (dispatch_target \in DispatchTarget)

    ValidDispatchTarget ==
        (dispatch_target = "none") \/ (dispatch_target \in DispatchTarget)

    AutoFixIsBooleanFlag ==
        auto_fix \in {TRUE, FALSE}

    TerminalReached ==
        ~dispatched \/ args_parsed

end define;

fair process cmd_plan_review_proc = "cmd_plan_review"
begin
    ParseArgs:
        args_parsed := TRUE;

    ChooseDispatch:
        if auto_fix = TRUE then
            dispatch_target := "orchestrate_reviews_with_correction";
        else
            dispatch_target := "orchestrate_reviews";
        end if;

    ForwardArgs:
        if dispatch_target = "orchestrate_reviews_with_correction" then
            forwarded_max_retries := max_retries_in;
        else
            forwarded_max_retries := 0;
        end if;

    Commit:
        dispatched := TRUE;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b8686cfb" /\ chksum(tla) = "3680e632")
VARIABLES pc, auto_fix, max_retries_in, args_parsed, dispatch_target, 
          forwarded_max_retries, dispatched

(* define statement *)
AutoFixDispatch ==
    ~dispatched \/
    ~(auto_fix = TRUE) \/
    (dispatch_target = "orchestrate_reviews_with_correction")

NoAutoFixDispatch ==
    ~dispatched \/
    ~(auto_fix = FALSE) \/
    (dispatch_target = "orchestrate_reviews")

MaxRetriesForwarded ==
    ~dispatched \/
    ~(dispatch_target = "orchestrate_reviews_with_correction") \/
    (forwarded_max_retries = max_retries_in)

MutualExclusion ==
    ~dispatched \/
    (dispatch_target \in DispatchTarget)

ValidDispatchTarget ==
    (dispatch_target = "none") \/ (dispatch_target \in DispatchTarget)

AutoFixIsBooleanFlag ==
    auto_fix \in {TRUE, FALSE}

TerminalReached ==
    ~dispatched \/ args_parsed


vars == << pc, auto_fix, max_retries_in, args_parsed, dispatch_target, 
           forwarded_max_retries, dispatched >>

ProcSet == {"cmd_plan_review"}

Init == (* Global variables *)
        /\ auto_fix = AutoFix
        /\ max_retries_in = MaxRetries
        /\ args_parsed = FALSE
        /\ dispatch_target = "none"
        /\ forwarded_max_retries = 0
        /\ dispatched = FALSE
        /\ pc = [self \in ProcSet |-> "ParseArgs"]

ParseArgs == /\ pc["cmd_plan_review"] = "ParseArgs"
             /\ args_parsed' = TRUE
             /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "ChooseDispatch"]
             /\ UNCHANGED << auto_fix, max_retries_in, dispatch_target, 
                             forwarded_max_retries, dispatched >>

ChooseDispatch == /\ pc["cmd_plan_review"] = "ChooseDispatch"
                  /\ IF auto_fix = TRUE
                        THEN /\ dispatch_target' = "orchestrate_reviews_with_correction"
                        ELSE /\ dispatch_target' = "orchestrate_reviews"
                  /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "ForwardArgs"]
                  /\ UNCHANGED << auto_fix, max_retries_in, args_parsed, 
                                  forwarded_max_retries, dispatched >>

ForwardArgs == /\ pc["cmd_plan_review"] = "ForwardArgs"
               /\ IF dispatch_target = "orchestrate_reviews_with_correction"
                     THEN /\ forwarded_max_retries' = max_retries_in
                     ELSE /\ forwarded_max_retries' = 0
               /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Commit"]
               /\ UNCHANGED << auto_fix, max_retries_in, args_parsed, 
                               dispatch_target, dispatched >>

Commit == /\ pc["cmd_plan_review"] = "Commit"
          /\ dispatched' = TRUE
          /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Finish"]
          /\ UNCHANGED << auto_fix, max_retries_in, args_parsed, 
                          dispatch_target, forwarded_max_retries >>

Finish == /\ pc["cmd_plan_review"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["cmd_plan_review"] = "Done"]
          /\ UNCHANGED << auto_fix, max_retries_in, args_parsed, 
                          dispatch_target, forwarded_max_retries, dispatched >>

cmd_plan_review_proc == ParseArgs \/ ChooseDispatch \/ ForwardArgs
                           \/ Commit \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == cmd_plan_review_proc
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(cmd_plan_review_proc)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
