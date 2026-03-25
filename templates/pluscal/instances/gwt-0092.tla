---------------------------- MODULE RetriesExhausted ----------------------------
EXTENDS Integers, FiniteSets, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

CoverageDependents == {"abstraction_gap", "imports"}

(*--algorithm RetriesExhausted

variables
    attempt           = 1,
    verdict           = "none",
    permanent         = FALSE,
    correctionCount   = 0,
    blockedPasses     = {},
    summaryStatus     = "none",
    stuckOn           = "none",
    findingsPreserved = FALSE,
    lastAttemptMade   = 0;

define

    ValidAttemptBounds ==
        attempt >= 1 /\ attempt <= MaxRetries + 1

    PermanentFailConsistent ==
        permanent => (verdict = "FAIL" /\ lastAttemptMade = MaxRetries)

    CorrectionCountConsistent ==
        permanent => correctionCount = MaxRetries - 1

    NoCorrectionExceedsMax ==
        correctionCount <= MaxRetries - 1

    DependentsBlockedWhenPermanent ==
        permanent => (CoverageDependents \subseteq blockedPasses)

    SummaryCorrectWhenPermanent ==
        permanent =>
            (summaryStatus    = "fail"
             /\ stuckOn       = "coverage"
             /\ findingsPreserved = TRUE)

    BlockedPassesDistinctFromFailed ==
        \A p \in blockedPasses : p # "coverage"

    FindingsPreservedMonotone ==
        findingsPreserved = TRUE =>
            (summaryStatus = "fail" \/ summaryStatus = "none")

end define;

fair process Orchestrator = "orch"
begin
    RetryStart:
        while attempt <= MaxRetries do
            RunReview:
                either
                    verdict := "FAIL";
                or
                    verdict := "PASS";
                or
                    verdict := "WARNING";
                end either;
                lastAttemptMade := attempt;
            CheckVerdict:
                if verdict # "FAIL" then
                    goto PostLoop;
                end if;
            MaybeSpawnCorrection:
                if attempt < MaxRetries then
                    correctionCount := correctionCount + 1;
                end if;
            IncrementAttempt:
                attempt := attempt + 1;
        end while;
    PostLoop:
        if verdict = "FAIL" then
            permanent         := TRUE        ||
            blockedPasses     := CoverageDependents ||
            summaryStatus     := "fail"      ||
            stuckOn           := "coverage"  ||
            findingsPreserved := TRUE;
        elsif verdict = "PASS" \/ verdict = "WARNING" then
            summaryStatus := "pass";
        end if;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "c6d6eef7" /\ chksum(tla) = "7c5fb067")
VARIABLES pc, attempt, verdict, permanent, correctionCount, blockedPasses, 
          summaryStatus, stuckOn, findingsPreserved, lastAttemptMade

(* define statement *)
ValidAttemptBounds ==
    attempt >= 1 /\ attempt <= MaxRetries + 1

PermanentFailConsistent ==
    permanent => (verdict = "FAIL" /\ lastAttemptMade = MaxRetries)

CorrectionCountConsistent ==
    permanent => correctionCount = MaxRetries - 1

NoCorrectionExceedsMax ==
    correctionCount <= MaxRetries - 1

DependentsBlockedWhenPermanent ==
    permanent => (CoverageDependents \subseteq blockedPasses)

SummaryCorrectWhenPermanent ==
    permanent =>
        (summaryStatus    = "fail"
         /\ stuckOn       = "coverage"
         /\ findingsPreserved = TRUE)

BlockedPassesDistinctFromFailed ==
    \A p \in blockedPasses : p # "coverage"

FindingsPreservedMonotone ==
    findingsPreserved = TRUE =>
        (summaryStatus = "fail" \/ summaryStatus = "none")


vars == << pc, attempt, verdict, permanent, correctionCount, blockedPasses, 
           summaryStatus, stuckOn, findingsPreserved, lastAttemptMade >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ attempt = 1
        /\ verdict = "none"
        /\ permanent = FALSE
        /\ correctionCount = 0
        /\ blockedPasses = {}
        /\ summaryStatus = "none"
        /\ stuckOn = "none"
        /\ findingsPreserved = FALSE
        /\ lastAttemptMade = 0
        /\ pc = [self \in ProcSet |-> "RetryStart"]

RetryStart == /\ pc["orch"] = "RetryStart"
              /\ IF attempt <= MaxRetries
                    THEN /\ pc' = [pc EXCEPT !["orch"] = "RunReview"]
                    ELSE /\ pc' = [pc EXCEPT !["orch"] = "PostLoop"]
              /\ UNCHANGED << attempt, verdict, permanent, correctionCount, 
                              blockedPasses, summaryStatus, stuckOn, 
                              findingsPreserved, lastAttemptMade >>

RunReview == /\ pc["orch"] = "RunReview"
             /\ \/ /\ verdict' = "FAIL"
                \/ /\ verdict' = "PASS"
                \/ /\ verdict' = "WARNING"
             /\ lastAttemptMade' = attempt
             /\ pc' = [pc EXCEPT !["orch"] = "CheckVerdict"]
             /\ UNCHANGED << attempt, permanent, correctionCount, 
                             blockedPasses, summaryStatus, stuckOn, 
                             findingsPreserved >>

CheckVerdict == /\ pc["orch"] = "CheckVerdict"
                /\ IF verdict # "FAIL"
                      THEN /\ pc' = [pc EXCEPT !["orch"] = "PostLoop"]
                      ELSE /\ pc' = [pc EXCEPT !["orch"] = "MaybeSpawnCorrection"]
                /\ UNCHANGED << attempt, verdict, permanent, correctionCount, 
                                blockedPasses, summaryStatus, stuckOn, 
                                findingsPreserved, lastAttemptMade >>

MaybeSpawnCorrection == /\ pc["orch"] = "MaybeSpawnCorrection"
                        /\ IF attempt < MaxRetries
                              THEN /\ correctionCount' = correctionCount + 1
                              ELSE /\ TRUE
                                   /\ UNCHANGED correctionCount
                        /\ pc' = [pc EXCEPT !["orch"] = "IncrementAttempt"]
                        /\ UNCHANGED << attempt, verdict, permanent, 
                                        blockedPasses, summaryStatus, stuckOn, 
                                        findingsPreserved, lastAttemptMade >>

IncrementAttempt == /\ pc["orch"] = "IncrementAttempt"
                    /\ attempt' = attempt + 1
                    /\ pc' = [pc EXCEPT !["orch"] = "RetryStart"]
                    /\ UNCHANGED << verdict, permanent, correctionCount, 
                                    blockedPasses, summaryStatus, stuckOn, 
                                    findingsPreserved, lastAttemptMade >>

PostLoop == /\ pc["orch"] = "PostLoop"
            /\ IF verdict = "FAIL"
                  THEN /\ /\ blockedPasses' = CoverageDependents
                          /\ findingsPreserved' = TRUE
                          /\ permanent' = TRUE
                          /\ stuckOn' = "coverage"
                          /\ summaryStatus' = "fail"
                  ELSE /\ IF verdict = "PASS" \/ verdict = "WARNING"
                             THEN /\ summaryStatus' = "pass"
                             ELSE /\ TRUE
                                  /\ UNCHANGED summaryStatus
                       /\ UNCHANGED << permanent, blockedPasses, stuckOn, 
                                       findingsPreserved >>
            /\ pc' = [pc EXCEPT !["orch"] = "Finish"]
            /\ UNCHANGED << attempt, verdict, correctionCount, lastAttemptMade >>

Finish == /\ pc["orch"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["orch"] = "Done"]
          /\ UNCHANGED << attempt, verdict, permanent, correctionCount, 
                          blockedPasses, summaryStatus, stuckOn, 
                          findingsPreserved, lastAttemptMade >>

Orchestrator == RetryStart \/ RunReview \/ CheckVerdict
                   \/ MaybeSpawnCorrection \/ IncrementAttempt \/ PostLoop
                   \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec => []ValidAttemptBounds
THEOREM Spec => []PermanentFailConsistent
THEOREM Spec => []CorrectionCountConsistent
THEOREM Spec => []NoCorrectionExceedsMax
THEOREM Spec => []DependentsBlockedWhenPermanent
THEOREM Spec => []SummaryCorrectWhenPermanent
THEOREM Spec => []BlockedPassesDistinctFromFailed
THEOREM Spec => []FindingsPreservedMonotone

================================================================================
