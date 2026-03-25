---- MODULE CmdPlanReviewMaxRetries ----

EXTENDS Integers, TLC

(*--algorithm CmdPlanReviewMaxRetries

variables
    phase = "init",
    auto_fix = FALSE,
    cli_retries_omitted = FALSE,
    cli_retries_value = 0,
    parsed_max_retries = 0,
    error_raised = FALSE,
    forwarded = FALSE,
    orchestrator_retries = 0;

define

    TypeOK ==
        /\ phase \in {"init", "parsed", "validated", "forwarded", "complete", "rejected"}
        /\ error_raised \in BOOLEAN
        /\ forwarded \in BOOLEAN
        /\ auto_fix \in BOOLEAN
        /\ cli_retries_omitted \in BOOLEAN

    NegativeRejected ==
        (/\ cli_retries_omitted = FALSE
         /\ cli_retries_value < 0
         /\ phase \notin {"init", "parsed"})
            => error_raised = TRUE

    MaxRetriesForwarded ==
        (auto_fix /\ phase = "complete")
            => (forwarded /\ orchestrator_retries = parsed_max_retries)

    ZeroMeansSinglePass ==
        (forwarded /\ parsed_max_retries = 0)
            => orchestrator_retries = 0

    DefaultWhenOmitted ==
        (cli_retries_omitted /\ phase \notin {"init", "rejected"})
            => parsed_max_retries = 2

    IgnoredWithoutAutoFix ==
        (auto_fix = FALSE /\ phase = "complete")
            => forwarded = FALSE

    ValidParsedRetries ==
        (error_raised = FALSE /\ phase \notin {"init", "parsed", "rejected"})
            => parsed_max_retries >= 0

end define;

fair process parser = "main"
begin

    SetupAutoFix:
        either
            auto_fix := TRUE;
        or
            auto_fix := FALSE;
        end either;

    ChooseRetries:
        either
            cli_retries_omitted := TRUE;
        or
            with v \in {-1, 0, 1, 3} do
                cli_retries_value := v;
            end with;
        end either;

    ParseMaxRetries:
        if cli_retries_omitted then
            parsed_max_retries := 2;
            phase := "parsed";
        else
            parsed_max_retries := cli_retries_value;
            phase := "parsed";
        end if;

    ValidateNonNegative:
        if parsed_max_retries < 0 then
            error_raised := TRUE;
            phase := "rejected";
            goto Terminate;
        else
            phase := "validated";
        end if;

    ForwardToOrchestrator:
        if auto_fix then
            forwarded := TRUE;
            orchestrator_retries := parsed_max_retries;
            phase := "forwarded";
        else
            phase := "complete";
            goto Terminate;
        end if;

    SetComplete:
        phase := "complete";

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f2a956cf" /\ chksum(tla) = "8aa350")
VARIABLES pc, phase, auto_fix, cli_retries_omitted, cli_retries_value, 
          parsed_max_retries, error_raised, forwarded, orchestrator_retries

(* define statement *)
TypeOK ==
    /\ phase \in {"init", "parsed", "validated", "forwarded", "complete", "rejected"}
    /\ error_raised \in BOOLEAN
    /\ forwarded \in BOOLEAN
    /\ auto_fix \in BOOLEAN
    /\ cli_retries_omitted \in BOOLEAN

NegativeRejected ==
    (/\ cli_retries_omitted = FALSE
     /\ cli_retries_value < 0
     /\ phase \notin {"init", "parsed"})
        => error_raised = TRUE

MaxRetriesForwarded ==
    (auto_fix /\ phase = "complete")
        => (forwarded /\ orchestrator_retries = parsed_max_retries)

ZeroMeansSinglePass ==
    (forwarded /\ parsed_max_retries = 0)
        => orchestrator_retries = 0

DefaultWhenOmitted ==
    (cli_retries_omitted /\ phase \notin {"init", "rejected"})
        => parsed_max_retries = 2

IgnoredWithoutAutoFix ==
    (auto_fix = FALSE /\ phase = "complete")
        => forwarded = FALSE

ValidParsedRetries ==
    (error_raised = FALSE /\ phase \notin {"init", "parsed", "rejected"})
        => parsed_max_retries >= 0


vars == << pc, phase, auto_fix, cli_retries_omitted, cli_retries_value, 
           parsed_max_retries, error_raised, forwarded, orchestrator_retries
        >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ phase = "init"
        /\ auto_fix = FALSE
        /\ cli_retries_omitted = FALSE
        /\ cli_retries_value = 0
        /\ parsed_max_retries = 0
        /\ error_raised = FALSE
        /\ forwarded = FALSE
        /\ orchestrator_retries = 0
        /\ pc = [self \in ProcSet |-> "SetupAutoFix"]

SetupAutoFix == /\ pc["main"] = "SetupAutoFix"
                /\ \/ /\ auto_fix' = TRUE
                   \/ /\ auto_fix' = FALSE
                /\ pc' = [pc EXCEPT !["main"] = "ChooseRetries"]
                /\ UNCHANGED << phase, cli_retries_omitted, cli_retries_value, 
                                parsed_max_retries, error_raised, forwarded, 
                                orchestrator_retries >>

ChooseRetries == /\ pc["main"] = "ChooseRetries"
                 /\ \/ /\ cli_retries_omitted' = TRUE
                       /\ UNCHANGED cli_retries_value
                    \/ /\ \E v \in {-1, 0, 1, 3}:
                            cli_retries_value' = v
                       /\ UNCHANGED cli_retries_omitted
                 /\ pc' = [pc EXCEPT !["main"] = "ParseMaxRetries"]
                 /\ UNCHANGED << phase, auto_fix, parsed_max_retries, 
                                 error_raised, forwarded, orchestrator_retries >>

ParseMaxRetries == /\ pc["main"] = "ParseMaxRetries"
                   /\ IF cli_retries_omitted
                         THEN /\ parsed_max_retries' = 2
                              /\ phase' = "parsed"
                         ELSE /\ parsed_max_retries' = cli_retries_value
                              /\ phase' = "parsed"
                   /\ pc' = [pc EXCEPT !["main"] = "ValidateNonNegative"]
                   /\ UNCHANGED << auto_fix, cli_retries_omitted, 
                                   cli_retries_value, error_raised, forwarded, 
                                   orchestrator_retries >>

ValidateNonNegative == /\ pc["main"] = "ValidateNonNegative"
                       /\ IF parsed_max_retries < 0
                             THEN /\ error_raised' = TRUE
                                  /\ phase' = "rejected"
                                  /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                             ELSE /\ phase' = "validated"
                                  /\ pc' = [pc EXCEPT !["main"] = "ForwardToOrchestrator"]
                                  /\ UNCHANGED error_raised
                       /\ UNCHANGED << auto_fix, cli_retries_omitted, 
                                       cli_retries_value, parsed_max_retries, 
                                       forwarded, orchestrator_retries >>

ForwardToOrchestrator == /\ pc["main"] = "ForwardToOrchestrator"
                         /\ IF auto_fix
                               THEN /\ forwarded' = TRUE
                                    /\ orchestrator_retries' = parsed_max_retries
                                    /\ phase' = "forwarded"
                                    /\ pc' = [pc EXCEPT !["main"] = "SetComplete"]
                               ELSE /\ phase' = "complete"
                                    /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                                    /\ UNCHANGED << forwarded, 
                                                    orchestrator_retries >>
                         /\ UNCHANGED << auto_fix, cli_retries_omitted, 
                                         cli_retries_value, parsed_max_retries, 
                                         error_raised >>

SetComplete == /\ pc["main"] = "SetComplete"
               /\ phase' = "complete"
               /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
               /\ UNCHANGED << auto_fix, cli_retries_omitted, 
                               cli_retries_value, parsed_max_retries, 
                               error_raised, forwarded, orchestrator_retries >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << phase, auto_fix, cli_retries_omitted, 
                             cli_retries_value, parsed_max_retries, 
                             error_raised, forwarded, orchestrator_retries >>

parser == SetupAutoFix \/ ChooseRetries \/ ParseMaxRetries
             \/ ValidateNonNegative \/ ForwardToOrchestrator \/ SetComplete
             \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == parser
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(parser)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec => []TypeOK

====
