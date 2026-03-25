---- MODULE PassVerdictBreaksRetryLoop ----

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

(* --algorithm PassVerdictBreaksRetryLoop

variables
  attempt           = 1,
  verdict           = "pending",
  correctionInvoked = FALSE,
  passComplete      = FALSE,
  passHistory       = <<>>,
  nextScheduled     = {},
  autoFixActive     = TRUE;

define

  DependentsOfArtifacts == {"coverage", "interaction"}

  VerdictSet == {"PASS", "FAIL", "WARNING", "pending"}

  TypeInvariant ==
    /\ attempt \in 1 .. (MaxRetries + 1)
    /\ verdict \in VerdictSet
    /\ correctionInvoked \in BOOLEAN
    /\ passComplete \in BOOLEAN
    /\ nextScheduled \subseteq DependentsOfArtifacts

  NoCorrection_OnPass ==
    verdict = "PASS" => ~correctionInvoked

  PassRecorded ==
    (passComplete /\ verdict = "PASS") =>
      (Len(passHistory) >= 1 /\ passHistory[Len(passHistory)] = "PASS")

  LoopTermination ==
    passComplete => attempt \in 1 .. (MaxRetries + 1)

  ScheduleNext ==
    (passComplete /\ verdict = "PASS") =>
      nextScheduled = DependentsOfArtifacts

  BoundedAttempts == attempt \in 1 .. (MaxRetries + 1)

  AttemptNotIncrementedOnPass ==
    (passComplete /\ verdict = "PASS") =>
      Len(passHistory) = attempt

end define;

fair process Orchestrator = "orch"
begin
  RetryLoop:
    while ~passComplete /\ attempt <= MaxRetries + 1 do
      StartAttempt:
        correctionInvoked := FALSE;
        verdict := "pending";
      RunReview:
        either
          verdict := "PASS";
        or
          verdict := "FAIL";
        or
          verdict := "WARNING";
        end either;
      AppendHistory:
        passHistory := Append(passHistory, verdict);
      CheckVerdict:
        if verdict = "PASS" then
          passComplete      := TRUE;
          nextScheduled     := DependentsOfArtifacts;
        else
          if autoFixActive /\ attempt < MaxRetries + 1 then
            correctionInvoked := TRUE;
            attempt           := attempt + 1;
          else
            passComplete := TRUE;
          end if;
        end if;
    end while;
  Finish:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e20e0b56" /\ chksum(tla) = "4a2611f3")
VARIABLES pc, attempt, verdict, correctionInvoked, passComplete, passHistory, 
          nextScheduled, autoFixActive

(* define statement *)
DependentsOfArtifacts == {"coverage", "interaction"}

VerdictSet == {"PASS", "FAIL", "WARNING", "pending"}

TypeInvariant ==
  /\ attempt \in 1 .. (MaxRetries + 1)
  /\ verdict \in VerdictSet
  /\ correctionInvoked \in BOOLEAN
  /\ passComplete \in BOOLEAN
  /\ nextScheduled \subseteq DependentsOfArtifacts

NoCorrection_OnPass ==
  verdict = "PASS" => ~correctionInvoked

PassRecorded ==
  (passComplete /\ verdict = "PASS") =>
    (Len(passHistory) >= 1 /\ passHistory[Len(passHistory)] = "PASS")

LoopTermination ==
  passComplete => attempt \in 1 .. (MaxRetries + 1)

ScheduleNext ==
  (passComplete /\ verdict = "PASS") =>
    nextScheduled = DependentsOfArtifacts

BoundedAttempts == attempt \in 1 .. (MaxRetries + 1)

AttemptNotIncrementedOnPass ==
  (passComplete /\ verdict = "PASS") =>
    Len(passHistory) = attempt


vars == << pc, attempt, verdict, correctionInvoked, passComplete, passHistory, 
           nextScheduled, autoFixActive >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ attempt = 1
        /\ verdict = "pending"
        /\ correctionInvoked = FALSE
        /\ passComplete = FALSE
        /\ passHistory = <<>>
        /\ nextScheduled = {}
        /\ autoFixActive = TRUE
        /\ pc = [self \in ProcSet |-> "RetryLoop"]

RetryLoop == /\ pc["orch"] = "RetryLoop"
             /\ IF ~passComplete /\ attempt <= MaxRetries + 1
                   THEN /\ pc' = [pc EXCEPT !["orch"] = "StartAttempt"]
                   ELSE /\ pc' = [pc EXCEPT !["orch"] = "Finish"]
             /\ UNCHANGED << attempt, verdict, correctionInvoked, passComplete, 
                             passHistory, nextScheduled, autoFixActive >>

StartAttempt == /\ pc["orch"] = "StartAttempt"
                /\ correctionInvoked' = FALSE
                /\ verdict' = "pending"
                /\ pc' = [pc EXCEPT !["orch"] = "RunReview"]
                /\ UNCHANGED << attempt, passComplete, passHistory, 
                                nextScheduled, autoFixActive >>

RunReview == /\ pc["orch"] = "RunReview"
             /\ \/ /\ verdict' = "PASS"
                \/ /\ verdict' = "FAIL"
                \/ /\ verdict' = "WARNING"
             /\ pc' = [pc EXCEPT !["orch"] = "AppendHistory"]
             /\ UNCHANGED << attempt, correctionInvoked, passComplete, 
                             passHistory, nextScheduled, autoFixActive >>

AppendHistory == /\ pc["orch"] = "AppendHistory"
                 /\ passHistory' = Append(passHistory, verdict)
                 /\ pc' = [pc EXCEPT !["orch"] = "CheckVerdict"]
                 /\ UNCHANGED << attempt, verdict, correctionInvoked, 
                                 passComplete, nextScheduled, autoFixActive >>

CheckVerdict == /\ pc["orch"] = "CheckVerdict"
                /\ IF verdict = "PASS"
                      THEN /\ passComplete' = TRUE
                           /\ nextScheduled' = DependentsOfArtifacts
                           /\ UNCHANGED << attempt, correctionInvoked >>
                      ELSE /\ IF autoFixActive /\ attempt < MaxRetries + 1
                                 THEN /\ correctionInvoked' = TRUE
                                      /\ attempt' = attempt + 1
                                      /\ UNCHANGED passComplete
                                 ELSE /\ passComplete' = TRUE
                                      /\ UNCHANGED << attempt, 
                                                      correctionInvoked >>
                           /\ UNCHANGED nextScheduled
                /\ pc' = [pc EXCEPT !["orch"] = "RetryLoop"]
                /\ UNCHANGED << verdict, passHistory, autoFixActive >>

Finish == /\ pc["orch"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["orch"] = "Done"]
          /\ UNCHANGED << attempt, verdict, correctionInvoked, passComplete, 
                          passHistory, nextScheduled, autoFixActive >>

Orchestrator == RetryLoop \/ StartAttempt \/ RunReview \/ AppendHistory
                   \/ CheckVerdict \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
