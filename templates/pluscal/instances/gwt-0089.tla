---- MODULE WarningVerdictOrchestration ----

EXTENDS Integers, FiniteSets, TLC

PASSES == {"artifacts", "coverage", "abstraction_gap"}

Deps(p) ==
  IF p = "coverage"             THEN {"artifacts"}
  ELSE IF p = "abstraction_gap" THEN {"coverage"}
  ELSE {}

(* --algorithm WarningVerdictOrchestration

variables
  verdict           = [p \in PASSES |-> "pending"],
  correctionInvoked = [p \in PASSES |-> FALSE],
  autoFix           = TRUE,
  summaryStatus     = "pending";

define

  NonBlocking(v)   == v \in {"PASS", "WARNING"}
  IsComplete(p)    == verdict[p] \in {"PASS", "WARNING", "FAIL"}
  DepsSatisfied(p) == \A d \in Deps(p) : NonBlocking(verdict[d])
  Schedulable(p)   == verdict[p] = "pending" /\ DepsSatisfied(p)

  NoCorrection_OnWarning ==
    \A p \in PASSES : verdict[p] = "WARNING" => ~correctionInvoked[p]

  WarningIsNonBlocking ==
    \A p \in PASSES : verdict[p] = "WARNING" => NonBlocking(verdict[p])

  WarningRecorded ==
    \A p \in PASSES : verdict[p] \in {"pending", "PASS", "WARNING", "FAIL"}

  WarningEnablesDependents ==
    \A p \in PASSES : verdict[p] = "WARNING" =>
      \A q \in PASSES :
        ( p \in Deps(q) /\ \A d \in Deps(q) \ {p} : NonBlocking(verdict[d]) ) =>
          ( Schedulable(q) \/ IsComplete(q) )

  CorrectionOnlyOnFail ==
    \A p \in PASSES : correctionInvoked[p] => verdict[p] = "FAIL"

  SummaryReflectsWarning ==
    summaryStatus = "warning" =>
      ( \E p \in PASSES : verdict[p] = "WARNING" ) /\
      ~( \E p \in PASSES : verdict[p] = "FAIL" )

  SummaryReflectsFail ==
    summaryStatus = "fail" =>
      \E p \in PASSES : verdict[p] = "FAIL"

  SummaryReflectsPass ==
    summaryStatus = "pass" =>
      \A p \in PASSES : verdict[p] = "PASS"

end define;

fair process orchestrator = "orch"
begin
  OrchestratorStart:
    while \E q \in PASSES : Schedulable(q) do
      SelectPass:
        with p \in {q \in PASSES : Schedulable(q)} do
          either
            verdict[p] := "PASS";
          or
            verdict[p] := "WARNING";
          or
            verdict[p] := "FAIL";
            if autoFix then
              correctionInvoked[p] := TRUE;
            end if;
          end either;
        end with;
    end while;
  ComputeSummary:
    if \E p \in PASSES : verdict[p] = "FAIL" then
      summaryStatus := "fail";
    elsif \E p \in PASSES : verdict[p] = "WARNING" then
      summaryStatus := "warning";
    else
      summaryStatus := "pass";
    end if;
  Finish:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3b45cb15" /\ chksum(tla) = "c39ec6e4")
VARIABLES pc, verdict, correctionInvoked, autoFix, summaryStatus

(* define statement *)
NonBlocking(v)   == v \in {"PASS", "WARNING"}
IsComplete(p)    == verdict[p] \in {"PASS", "WARNING", "FAIL"}
DepsSatisfied(p) == \A d \in Deps(p) : NonBlocking(verdict[d])
Schedulable(p)   == verdict[p] = "pending" /\ DepsSatisfied(p)

NoCorrection_OnWarning ==
  \A p \in PASSES : verdict[p] = "WARNING" => ~correctionInvoked[p]

WarningIsNonBlocking ==
  \A p \in PASSES : verdict[p] = "WARNING" => NonBlocking(verdict[p])

WarningRecorded ==
  \A p \in PASSES : verdict[p] \in {"pending", "PASS", "WARNING", "FAIL"}

WarningEnablesDependents ==
  \A p \in PASSES : verdict[p] = "WARNING" =>
    \A q \in PASSES :
      ( p \in Deps(q) /\ \A d \in Deps(q) \ {p} : NonBlocking(verdict[d]) ) =>
        ( Schedulable(q) \/ IsComplete(q) )

CorrectionOnlyOnFail ==
  \A p \in PASSES : correctionInvoked[p] => verdict[p] = "FAIL"

SummaryReflectsWarning ==
  summaryStatus = "warning" =>
    ( \E p \in PASSES : verdict[p] = "WARNING" ) /\
    ~( \E p \in PASSES : verdict[p] = "FAIL" )

SummaryReflectsFail ==
  summaryStatus = "fail" =>
    \E p \in PASSES : verdict[p] = "FAIL"

SummaryReflectsPass ==
  summaryStatus = "pass" =>
    \A p \in PASSES : verdict[p] = "PASS"


vars == << pc, verdict, correctionInvoked, autoFix, summaryStatus >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ verdict = [p \in PASSES |-> "pending"]
        /\ correctionInvoked = [p \in PASSES |-> FALSE]
        /\ autoFix = TRUE
        /\ summaryStatus = "pending"
        /\ pc = [self \in ProcSet |-> "OrchestratorStart"]

OrchestratorStart == /\ pc["orch"] = "OrchestratorStart"
                     /\ IF \E q \in PASSES : Schedulable(q)
                           THEN /\ pc' = [pc EXCEPT !["orch"] = "SelectPass"]
                           ELSE /\ pc' = [pc EXCEPT !["orch"] = "ComputeSummary"]
                     /\ UNCHANGED << verdict, correctionInvoked, autoFix, 
                                     summaryStatus >>

SelectPass == /\ pc["orch"] = "SelectPass"
              /\ \E p \in {q \in PASSES : Schedulable(q)}:
                   \/ /\ verdict' = [verdict EXCEPT ![p] = "PASS"]
                      /\ UNCHANGED correctionInvoked
                   \/ /\ verdict' = [verdict EXCEPT ![p] = "WARNING"]
                      /\ UNCHANGED correctionInvoked
                   \/ /\ verdict' = [verdict EXCEPT ![p] = "FAIL"]
                      /\ IF autoFix
                            THEN /\ correctionInvoked' = [correctionInvoked EXCEPT ![p] = TRUE]
                            ELSE /\ TRUE
                                 /\ UNCHANGED correctionInvoked
              /\ pc' = [pc EXCEPT !["orch"] = "OrchestratorStart"]
              /\ UNCHANGED << autoFix, summaryStatus >>

ComputeSummary == /\ pc["orch"] = "ComputeSummary"
                  /\ IF \E p \in PASSES : verdict[p] = "FAIL"
                        THEN /\ summaryStatus' = "fail"
                        ELSE /\ IF \E p \in PASSES : verdict[p] = "WARNING"
                                   THEN /\ summaryStatus' = "warning"
                                   ELSE /\ summaryStatus' = "pass"
                  /\ pc' = [pc EXCEPT !["orch"] = "Finish"]
                  /\ UNCHANGED << verdict, correctionInvoked, autoFix >>

Finish == /\ pc["orch"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["orch"] = "Done"]
          /\ UNCHANGED << verdict, correctionInvoked, autoFix, summaryStatus >>

orchestrator == OrchestratorStart \/ SelectPass \/ ComputeSummary \/ Finish

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
