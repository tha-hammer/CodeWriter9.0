---- MODULE PlanReviewVerdictAggregation ----

EXTENDS Integers, Sequences, FiniteSets, TLC

NumPasses == 3

Verdict   == {"pass", "fail", "warning", "unknown"}
StatusSet == {"pass", "fail", "warning"}

(* --algorithm PlanReviewVerdictAggregation

variables
    verdicts  = <<>>,
    status    = "pass",
    exit_code = 0,
    phase     = "adding";

define

    FailDominates ==
        ( phase = "done" /\
          (\E i \in DOMAIN verdicts : verdicts[i] = "fail") )
        => status = "fail"

    WarningSecond ==
        ( phase = "done" /\
          ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
          (\E i \in DOMAIN verdicts : verdicts[i] = "warning") )
        => status = "warning"

    ExitCodeMapping ==
        /\ ( phase = "done" /\ status \in {"pass", "warning"} ) => exit_code = 0
        /\ ( phase = "done" /\ status = "fail" )                => exit_code = 1

    StatusIsValid ==
        phase = "done" => status \in StatusSet

    VerdictLengthBound ==
        Len(verdicts) <= NumPasses

end define;

fair process orchestrator = "main"
begin
    AddVerdicts:
        while Len(verdicts) < NumPasses do
            PickVerdict:
                with v \in Verdict do
                    verdicts := Append(verdicts, v);
                end with;
        end while;
    ComputeOverall:
        if \E i \in DOMAIN verdicts : verdicts[i] = "fail" then
            status := "fail";
        elsif \E i \in DOMAIN verdicts : verdicts[i] = "warning" then
            status := "warning";
        else
            status := "pass";
        end if;
    SetExitCode:
        if status = "fail" then
            exit_code := 1;
        else
            exit_code := 0;
        end if;
    MarkDone:
        phase := "done";
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b91ba9d1" /\ chksum(tla) = "3df8c657")
VARIABLES pc, verdicts, status, exit_code, phase

(* define statement *)
FailDominates ==
    ( phase = "done" /\
      (\E i \in DOMAIN verdicts : verdicts[i] = "fail") )
    => status = "fail"

WarningSecond ==
    ( phase = "done" /\
      ~(\E i \in DOMAIN verdicts : verdicts[i] = "fail") /\
      (\E i \in DOMAIN verdicts : verdicts[i] = "warning") )
    => status = "warning"

ExitCodeMapping ==
    /\ ( phase = "done" /\ status \in {"pass", "warning"} ) => exit_code = 0
    /\ ( phase = "done" /\ status = "fail" )                => exit_code = 1

StatusIsValid ==
    phase = "done" => status \in StatusSet

VerdictLengthBound ==
    Len(verdicts) <= NumPasses


vars == << pc, verdicts, status, exit_code, phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ verdicts = <<>>
        /\ status = "pass"
        /\ exit_code = 0
        /\ phase = "adding"
        /\ pc = [self \in ProcSet |-> "AddVerdicts"]

AddVerdicts == /\ pc["main"] = "AddVerdicts"
               /\ IF Len(verdicts) < NumPasses
                     THEN /\ pc' = [pc EXCEPT !["main"] = "PickVerdict"]
                     ELSE /\ pc' = [pc EXCEPT !["main"] = "ComputeOverall"]
               /\ UNCHANGED << verdicts, status, exit_code, phase >>

PickVerdict == /\ pc["main"] = "PickVerdict"
               /\ \E v \in Verdict:
                    verdicts' = Append(verdicts, v)
               /\ pc' = [pc EXCEPT !["main"] = "AddVerdicts"]
               /\ UNCHANGED << status, exit_code, phase >>

ComputeOverall == /\ pc["main"] = "ComputeOverall"
                  /\ IF \E i \in DOMAIN verdicts : verdicts[i] = "fail"
                        THEN /\ status' = "fail"
                        ELSE /\ IF \E i \in DOMAIN verdicts : verdicts[i] = "warning"
                                   THEN /\ status' = "warning"
                                   ELSE /\ status' = "pass"
                  /\ pc' = [pc EXCEPT !["main"] = "SetExitCode"]
                  /\ UNCHANGED << verdicts, exit_code, phase >>

SetExitCode == /\ pc["main"] = "SetExitCode"
               /\ IF status = "fail"
                     THEN /\ exit_code' = 1
                     ELSE /\ exit_code' = 0
               /\ pc' = [pc EXCEPT !["main"] = "MarkDone"]
               /\ UNCHANGED << verdicts, status, phase >>

MarkDone == /\ pc["main"] = "MarkDone"
            /\ phase' = "done"
            /\ pc' = [pc EXCEPT !["main"] = "Finish"]
            /\ UNCHANGED << verdicts, status, exit_code >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << verdicts, status, exit_code, phase >>

orchestrator == AddVerdicts \/ PickVerdict \/ ComputeOverall \/ SetExitCode
                   \/ MarkDone \/ Finish

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
