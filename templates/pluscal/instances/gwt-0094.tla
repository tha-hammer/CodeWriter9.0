---- MODULE ArtifactsBlockAll ----
EXTENDS Integers, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

(* --algorithm ArtifactsBlockAll

variables
    artifactsVerdict   = "PENDING",
    artifactsAttempts  = 0,
    coverageVerdict    = "PENDING",
    interactionVerdict = "PENDING",
    abstGapVerdict     = "PENDING",
    importsVerdict     = "PENDING",
    reviewCallCount    = 0,
    summaryStatus      = "none",
    stuckOn            = "none",
    sessionDone        = FALSE;

define

    AllBlocked ==
        sessionDone =>
            /\ coverageVerdict    = "blocked"
            /\ interactionVerdict = "blocked"
            /\ abstGapVerdict     = "blocked"
            /\ importsVerdict     = "blocked"

    SummaryCorrect ==
        sessionDone =>
            /\ summaryStatus = "fail"
            /\ stuckOn       = "artifacts"

    NoneRun ==
        sessionDone => reviewCallCount = MaxRetries

    ArtifactsTerminalFail ==
        sessionDone => artifactsVerdict = "FAIL"

    StuckOnArtifacts ==
        sessionDone => stuckOn = "artifacts"

    TypeOK ==
        /\ artifactsVerdict   \in {"PENDING", "FAIL"}
        /\ coverageVerdict    \in {"PENDING", "blocked"}
        /\ interactionVerdict \in {"PENDING", "blocked"}
        /\ abstGapVerdict     \in {"PENDING", "blocked"}
        /\ importsVerdict     \in {"PENDING", "blocked"}
        /\ summaryStatus      \in {"none", "fail"}
        /\ stuckOn            \in {"none", "artifacts"}
        /\ reviewCallCount    \in 0..MaxRetries
        /\ sessionDone        \in BOOLEAN

end define;

fair process orchestrator = "orch"
begin
    RunArtifacts:
        while artifactsAttempts < MaxRetries do
            AttemptArtifact:
                artifactsAttempts := artifactsAttempts + 1;
                reviewCallCount   := reviewCallCount + 1;
        end while;
    MarkArtifactsFail:
        artifactsVerdict := "FAIL";
    TryScheduleCoverage:
        if artifactsVerdict = "FAIL" then
            coverageVerdict := "blocked";
        end if;
    TryScheduleInteraction:
        if artifactsVerdict = "FAIL" then
            interactionVerdict := "blocked";
        end if;
    TryScheduleAbstGap:
        if coverageVerdict = "blocked" \/ interactionVerdict = "blocked" then
            abstGapVerdict := "blocked";
        end if;
    TryScheduleImports:
        if abstGapVerdict = "blocked" then
            importsVerdict := "blocked";
        end if;
    ComposeSummary:
        summaryStatus := "fail";
        stuckOn       := "artifacts";
        sessionDone   := TRUE;
    Terminate:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "ec9d53a0" /\ chksum(tla) = "e9291194")
VARIABLES pc, artifactsVerdict, artifactsAttempts, coverageVerdict, 
          interactionVerdict, abstGapVerdict, importsVerdict, reviewCallCount, 
          summaryStatus, stuckOn, sessionDone

(* define statement *)
AllBlocked ==
    sessionDone =>
        /\ coverageVerdict    = "blocked"
        /\ interactionVerdict = "blocked"
        /\ abstGapVerdict     = "blocked"
        /\ importsVerdict     = "blocked"

SummaryCorrect ==
    sessionDone =>
        /\ summaryStatus = "fail"
        /\ stuckOn       = "artifacts"

NoneRun ==
    sessionDone => reviewCallCount = MaxRetries

ArtifactsTerminalFail ==
    sessionDone => artifactsVerdict = "FAIL"

StuckOnArtifacts ==
    sessionDone => stuckOn = "artifacts"

TypeOK ==
    /\ artifactsVerdict   \in {"PENDING", "FAIL"}
    /\ coverageVerdict    \in {"PENDING", "blocked"}
    /\ interactionVerdict \in {"PENDING", "blocked"}
    /\ abstGapVerdict     \in {"PENDING", "blocked"}
    /\ importsVerdict     \in {"PENDING", "blocked"}
    /\ summaryStatus      \in {"none", "fail"}
    /\ stuckOn            \in {"none", "artifacts"}
    /\ reviewCallCount    \in 0..MaxRetries
    /\ sessionDone        \in BOOLEAN


vars == << pc, artifactsVerdict, artifactsAttempts, coverageVerdict, 
           interactionVerdict, abstGapVerdict, importsVerdict, 
           reviewCallCount, summaryStatus, stuckOn, sessionDone >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ artifactsVerdict = "PENDING"
        /\ artifactsAttempts = 0
        /\ coverageVerdict = "PENDING"
        /\ interactionVerdict = "PENDING"
        /\ abstGapVerdict = "PENDING"
        /\ importsVerdict = "PENDING"
        /\ reviewCallCount = 0
        /\ summaryStatus = "none"
        /\ stuckOn = "none"
        /\ sessionDone = FALSE
        /\ pc = [self \in ProcSet |-> "RunArtifacts"]

RunArtifacts == /\ pc["orch"] = "RunArtifacts"
                /\ IF artifactsAttempts < MaxRetries
                      THEN /\ pc' = [pc EXCEPT !["orch"] = "AttemptArtifact"]
                      ELSE /\ pc' = [pc EXCEPT !["orch"] = "MarkArtifactsFail"]
                /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                coverageVerdict, interactionVerdict, 
                                abstGapVerdict, importsVerdict, 
                                reviewCallCount, summaryStatus, stuckOn, 
                                sessionDone >>

AttemptArtifact == /\ pc["orch"] = "AttemptArtifact"
                   /\ artifactsAttempts' = artifactsAttempts + 1
                   /\ reviewCallCount' = reviewCallCount + 1
                   /\ pc' = [pc EXCEPT !["orch"] = "RunArtifacts"]
                   /\ UNCHANGED << artifactsVerdict, coverageVerdict, 
                                   interactionVerdict, abstGapVerdict, 
                                   importsVerdict, summaryStatus, stuckOn, 
                                   sessionDone >>

MarkArtifactsFail == /\ pc["orch"] = "MarkArtifactsFail"
                     /\ artifactsVerdict' = "FAIL"
                     /\ pc' = [pc EXCEPT !["orch"] = "TryScheduleCoverage"]
                     /\ UNCHANGED << artifactsAttempts, coverageVerdict, 
                                     interactionVerdict, abstGapVerdict, 
                                     importsVerdict, reviewCallCount, 
                                     summaryStatus, stuckOn, sessionDone >>

TryScheduleCoverage == /\ pc["orch"] = "TryScheduleCoverage"
                       /\ IF artifactsVerdict = "FAIL"
                             THEN /\ coverageVerdict' = "blocked"
                             ELSE /\ TRUE
                                  /\ UNCHANGED coverageVerdict
                       /\ pc' = [pc EXCEPT !["orch"] = "TryScheduleInteraction"]
                       /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                       interactionVerdict, abstGapVerdict, 
                                       importsVerdict, reviewCallCount, 
                                       summaryStatus, stuckOn, sessionDone >>

TryScheduleInteraction == /\ pc["orch"] = "TryScheduleInteraction"
                          /\ IF artifactsVerdict = "FAIL"
                                THEN /\ interactionVerdict' = "blocked"
                                ELSE /\ TRUE
                                     /\ UNCHANGED interactionVerdict
                          /\ pc' = [pc EXCEPT !["orch"] = "TryScheduleAbstGap"]
                          /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                          coverageVerdict, abstGapVerdict, 
                                          importsVerdict, reviewCallCount, 
                                          summaryStatus, stuckOn, sessionDone >>

TryScheduleAbstGap == /\ pc["orch"] = "TryScheduleAbstGap"
                      /\ IF coverageVerdict = "blocked" \/ interactionVerdict = "blocked"
                            THEN /\ abstGapVerdict' = "blocked"
                            ELSE /\ TRUE
                                 /\ UNCHANGED abstGapVerdict
                      /\ pc' = [pc EXCEPT !["orch"] = "TryScheduleImports"]
                      /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                      coverageVerdict, interactionVerdict, 
                                      importsVerdict, reviewCallCount, 
                                      summaryStatus, stuckOn, sessionDone >>

TryScheduleImports == /\ pc["orch"] = "TryScheduleImports"
                      /\ IF abstGapVerdict = "blocked"
                            THEN /\ importsVerdict' = "blocked"
                            ELSE /\ TRUE
                                 /\ UNCHANGED importsVerdict
                      /\ pc' = [pc EXCEPT !["orch"] = "ComposeSummary"]
                      /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                      coverageVerdict, interactionVerdict, 
                                      abstGapVerdict, reviewCallCount, 
                                      summaryStatus, stuckOn, sessionDone >>

ComposeSummary == /\ pc["orch"] = "ComposeSummary"
                  /\ summaryStatus' = "fail"
                  /\ stuckOn' = "artifacts"
                  /\ sessionDone' = TRUE
                  /\ pc' = [pc EXCEPT !["orch"] = "Terminate"]
                  /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                                  coverageVerdict, interactionVerdict, 
                                  abstGapVerdict, importsVerdict, 
                                  reviewCallCount >>

Terminate == /\ pc["orch"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["orch"] = "Done"]
             /\ UNCHANGED << artifactsVerdict, artifactsAttempts, 
                             coverageVerdict, interactionVerdict, 
                             abstGapVerdict, importsVerdict, reviewCallCount, 
                             summaryStatus, stuckOn, sessionDone >>

orchestrator == RunArtifacts \/ AttemptArtifact \/ MarkArtifactsFail
                   \/ TryScheduleCoverage \/ TryScheduleInteraction
                   \/ TryScheduleAbstGap \/ TryScheduleImports
                   \/ ComposeSummary \/ Terminate

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
