---- MODULE OrchestrateReviewsOverallStatus ----

EXTENDS Integers, Sequences, FiniteSets, TLC

NumPasses == 3

Verdict == {"pass", "fail", "warning", "unknown"}
Status  == {"pass", "fail", "warning"}

(* --algorithm OrchestrateReviewsOverallStatus

variables
    verdicts  = <<>>,
    status    = "pass",
    exit_code = 0,
    phase     = "collecting",
    collected = 0;

define

    FailDominates ==
        ( phase = "done" /\
          \E i \in DOMAIN verdicts : verdicts[i] = "fail" )
            => status = "fail"

    WarningSecond ==
        ( phase = "done" /\
          ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
          \E i \in DOMAIN verdicts : verdicts[i] = "warning" )
            => status = "warning"

    PassRequiresAllPass ==
        ( phase = "done" /\ status = "pass" ) =>
            \A i \in DOMAIN verdicts : verdicts[i] \in {"pass", "unknown"}

    ExitCodeMapping ==
        phase = "done" =>
            ( ( status \in {"pass", "warning"} => exit_code = 0 ) /\
              ( status = "fail" => exit_code = 1 ) )

    UnknownTreatedAsPass ==
        ( phase = "done" /\
          ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
          ~(\E i \in DOMAIN verdicts : verdicts[i] = "warning") )
            => status = "pass"

    StatusIsValid ==
        phase = "done" => status \in Status

    ExitCodeIsValid ==
        phase = "done" => exit_code \in {0, 1}

    CollectedBound ==
        collected <= NumPasses

end define;

fair process orchestrator = "main"
begin
    Collect:
        while collected < NumPasses do
            with v \in Verdict do
                verdicts  := Append(verdicts, v);
                collected := collected + 1;
            end with;
        end while;
    Compute:
        if \E i \in DOMAIN verdicts : verdicts[i] = "fail" then
            status    := "fail";
            exit_code := 1;
        elsif \E i \in DOMAIN verdicts : verdicts[i] = "warning" then
            status    := "warning";
            exit_code := 0;
        else
            status    := "pass";
            exit_code := 0;
        end if;
    Finish:
        phase := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "75a51b03" /\ chksum(tla) = "8c5de0af")
VARIABLES pc, verdicts, status, exit_code, phase, collected

(* define statement *)
FailDominates ==
    ( phase = "done" /\
      \E i \in DOMAIN verdicts : verdicts[i] = "fail" )
        => status = "fail"

WarningSecond ==
    ( phase = "done" /\
      ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
      \E i \in DOMAIN verdicts : verdicts[i] = "warning" )
        => status = "warning"

PassRequiresAllPass ==
    ( phase = "done" /\ status = "pass" ) =>
        \A i \in DOMAIN verdicts : verdicts[i] \in {"pass", "unknown"}

ExitCodeMapping ==
    phase = "done" =>
        ( ( status \in {"pass", "warning"} => exit_code = 0 ) /\
          ( status = "fail" => exit_code = 1 ) )

UnknownTreatedAsPass ==
    ( phase = "done" /\
      ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
      ~(\E i \in DOMAIN verdicts : verdicts[i] = "warning") )
        => status = "pass"

StatusIsValid ==
    phase = "done" => status \in Status

ExitCodeIsValid ==
    phase = "done" => exit_code \in {0, 1}

CollectedBound ==
    collected <= NumPasses


vars == << pc, verdicts, status, exit_code, phase, collected >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ verdicts = <<>>
        /\ status = "pass"
        /\ exit_code = 0
        /\ phase = "collecting"
        /\ collected = 0
        /\ pc = [self \in ProcSet |-> "Collect"]

Collect == /\ pc["main"] = "Collect"
           /\ IF collected < NumPasses
                 THEN /\ \E v \in Verdict:
                           /\ verdicts' = Append(verdicts, v)
                           /\ collected' = collected + 1
                      /\ pc' = [pc EXCEPT !["main"] = "Collect"]
                 ELSE /\ pc' = [pc EXCEPT !["main"] = "Compute"]
                      /\ UNCHANGED << verdicts, collected >>
           /\ UNCHANGED << status, exit_code, phase >>

Compute == /\ pc["main"] = "Compute"
           /\ IF \E i \in DOMAIN verdicts : verdicts[i] = "fail"
                 THEN /\ status' = "fail"
                      /\ exit_code' = 1
                 ELSE /\ IF \E i \in DOMAIN verdicts : verdicts[i] = "warning"
                            THEN /\ status' = "warning"
                                 /\ exit_code' = 0
                            ELSE /\ status' = "pass"
                                 /\ exit_code' = 0
           /\ pc' = [pc EXCEPT !["main"] = "Finish"]
           /\ UNCHANGED << verdicts, phase, collected >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "done"
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << verdicts, status, exit_code, collected >>

orchestrator == Collect \/ Compute \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
