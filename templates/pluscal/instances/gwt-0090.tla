---- MODULE FailTriggerCorrection ----

EXTENDS Integers, Sequences, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

(* --algorithm FailTriggerCorrection

variables
    attempt           = 1,
    verdict           = "pending",
    phase             = "reviewing",
    correctionCount   = 0,
    findingsReady     = FALSE,
    reviewHistory     = <<>>,
    correctionHistory = <<>>,
    autoFix           = TRUE;

define

    Verdicts == {"pending", "PASS", "WARNING", "FAIL"}
    Phases   == {"reviewing", "extracting", "correcting", "done"}

    ValidVerdict == verdict \in Verdicts

    ValidPhase == phase \in Phases

    CorrectionCountInvariant == correctionCount <= attempt - 1

    AttemptGuard ==
        \A i \in 1..Len(correctionHistory) :
            correctionHistory[i].attempt < MaxRetries

    FindingsExtractedBeforeCorrection ==
        phase = "correcting" => findingsReady = TRUE

    CorrectionRequiresAutoFix ==
        correctionCount > 0 => autoFix = TRUE

    NoCorrectionOnLastAttempt ==
        correctionCount <= MaxRetries - 1

    SequentialOrder ==
        Len(correctionHistory) <= Len(reviewHistory)

    NoSpuriousCorrections ==
        \A i \in 1..Len(correctionHistory) :
            LET ca == correctionHistory[i].attempt
            IN \E j \in 1..Len(reviewHistory) :
                   reviewHistory[j].attempt = ca /\
                   reviewHistory[j].verdict = "FAIL"

end define;

fair process Orchestrator = "orchestrator"
begin
    ReviewLoop:
        while attempt <= MaxRetries /\ phase /= "done" do
            RunReview:
                with v \in {"PASS", "WARNING", "FAIL"} do
                    verdict       := v;
                    reviewHistory := Append(reviewHistory,
                                        [attempt |-> attempt,
                                         verdict |-> v]);
                    findingsReady := FALSE;
                end with;

            EvalVerdict:
                if verdict \in {"PASS", "WARNING"} then
                    phase := "done";
                elsif verdict = "FAIL" /\ autoFix /\ attempt < MaxRetries then
                    phase := "extracting";
                else
                    phase := "done";
                end if;

            CheckPhase:
                if phase = "extracting" then
                    ExtractFindings:
                        findingsReady := TRUE;
                        phase         := "correcting";
                    RunCorrection:
                        assert findingsReady = TRUE;
                        assert attempt < MaxRetries;
                        assert autoFix = TRUE;
                        correctionHistory := Append(correctionHistory,
                                                [attempt |-> attempt,
                                                 corrNum |-> correctionCount + 1]);
                        correctionCount   := correctionCount + 1;
                        findingsReady     := FALSE;
                        phase             := "reviewing";
                        attempt           := attempt + 1;
                end if;
        end while;

    Terminate:
        assert phase = "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "db0147a4" /\ chksum(tla) = "66eee1b8")
VARIABLES pc, attempt, verdict, phase, correctionCount, findingsReady, 
          reviewHistory, correctionHistory, autoFix

(* define statement *)
Verdicts == {"pending", "PASS", "WARNING", "FAIL"}
Phases   == {"reviewing", "extracting", "correcting", "done"}

ValidVerdict == verdict \in Verdicts

ValidPhase == phase \in Phases

CorrectionCountInvariant == correctionCount <= attempt - 1

AttemptGuard ==
    \A i \in 1..Len(correctionHistory) :
        correctionHistory[i].attempt < MaxRetries

FindingsExtractedBeforeCorrection ==
    phase = "correcting" => findingsReady = TRUE

CorrectionRequiresAutoFix ==
    correctionCount > 0 => autoFix = TRUE

NoCorrectionOnLastAttempt ==
    correctionCount <= MaxRetries - 1

SequentialOrder ==
    Len(correctionHistory) <= Len(reviewHistory)

NoSpuriousCorrections ==
    \A i \in 1..Len(correctionHistory) :
        LET ca == correctionHistory[i].attempt
        IN \E j \in 1..Len(reviewHistory) :
               reviewHistory[j].attempt = ca /\
               reviewHistory[j].verdict = "FAIL"


vars == << pc, attempt, verdict, phase, correctionCount, findingsReady, 
           reviewHistory, correctionHistory, autoFix >>

ProcSet == {"orchestrator"}

Init == (* Global variables *)
        /\ attempt = 1
        /\ verdict = "pending"
        /\ phase = "reviewing"
        /\ correctionCount = 0
        /\ findingsReady = FALSE
        /\ reviewHistory = <<>>
        /\ correctionHistory = <<>>
        /\ autoFix = TRUE
        /\ pc = [self \in ProcSet |-> "ReviewLoop"]

ReviewLoop == /\ pc["orchestrator"] = "ReviewLoop"
              /\ IF attempt <= MaxRetries /\ phase /= "done"
                    THEN /\ pc' = [pc EXCEPT !["orchestrator"] = "RunReview"]
                    ELSE /\ pc' = [pc EXCEPT !["orchestrator"] = "Terminate"]
              /\ UNCHANGED << attempt, verdict, phase, correctionCount, 
                              findingsReady, reviewHistory, correctionHistory, 
                              autoFix >>

RunReview == /\ pc["orchestrator"] = "RunReview"
             /\ \E v \in {"PASS", "WARNING", "FAIL"}:
                  /\ verdict' = v
                  /\ reviewHistory' = Append(reviewHistory,
                                         [attempt |-> attempt,
                                          verdict |-> v])
                  /\ findingsReady' = FALSE
             /\ pc' = [pc EXCEPT !["orchestrator"] = "EvalVerdict"]
             /\ UNCHANGED << attempt, phase, correctionCount, 
                             correctionHistory, autoFix >>

EvalVerdict == /\ pc["orchestrator"] = "EvalVerdict"
               /\ IF verdict \in {"PASS", "WARNING"}
                     THEN /\ phase' = "done"
                     ELSE /\ IF verdict = "FAIL" /\ autoFix /\ attempt < MaxRetries
                                THEN /\ phase' = "extracting"
                                ELSE /\ phase' = "done"
               /\ pc' = [pc EXCEPT !["orchestrator"] = "CheckPhase"]
               /\ UNCHANGED << attempt, verdict, correctionCount, 
                               findingsReady, reviewHistory, correctionHistory, 
                               autoFix >>

CheckPhase == /\ pc["orchestrator"] = "CheckPhase"
              /\ IF phase = "extracting"
                    THEN /\ pc' = [pc EXCEPT !["orchestrator"] = "ExtractFindings"]
                    ELSE /\ pc' = [pc EXCEPT !["orchestrator"] = "ReviewLoop"]
              /\ UNCHANGED << attempt, verdict, phase, correctionCount, 
                              findingsReady, reviewHistory, correctionHistory, 
                              autoFix >>

ExtractFindings == /\ pc["orchestrator"] = "ExtractFindings"
                   /\ findingsReady' = TRUE
                   /\ phase' = "correcting"
                   /\ pc' = [pc EXCEPT !["orchestrator"] = "RunCorrection"]
                   /\ UNCHANGED << attempt, verdict, correctionCount, 
                                   reviewHistory, correctionHistory, autoFix >>

RunCorrection == /\ pc["orchestrator"] = "RunCorrection"
                 /\ Assert(findingsReady = TRUE, 
                           "Failure of assertion at line 85, column 25.")
                 /\ Assert(attempt < MaxRetries, 
                           "Failure of assertion at line 86, column 25.")
                 /\ Assert(autoFix = TRUE, 
                           "Failure of assertion at line 87, column 25.")
                 /\ correctionHistory' = Append(correctionHistory,
                                            [attempt |-> attempt,
                                             corrNum |-> correctionCount + 1])
                 /\ correctionCount' = correctionCount + 1
                 /\ findingsReady' = FALSE
                 /\ phase' = "reviewing"
                 /\ attempt' = attempt + 1
                 /\ pc' = [pc EXCEPT !["orchestrator"] = "ReviewLoop"]
                 /\ UNCHANGED << verdict, reviewHistory, autoFix >>

Terminate == /\ pc["orchestrator"] = "Terminate"
             /\ Assert(phase = "done", 
                       "Failure of assertion at line 99, column 9.")
             /\ pc' = [pc EXCEPT !["orchestrator"] = "Done"]
             /\ UNCHANGED << attempt, verdict, phase, correctionCount, 
                             findingsReady, reviewHistory, correctionHistory, 
                             autoFix >>

Orchestrator == ReviewLoop \/ RunReview \/ EvalVerdict \/ CheckPhase
                   \/ ExtractFindings \/ RunCorrection \/ Terminate

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
