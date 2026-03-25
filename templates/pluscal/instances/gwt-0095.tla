---- MODULE ParallelPassDispatch ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS MAX_RETRIES

PASSES            == {"artifacts", "coverage", "interaction",
                      "abstraction_gap", "imports"}
PHASE2_PASSES     == {"coverage", "interaction"}
ENABLING_VERDICTS == {"PASS", "WARNING"}
TERMINAL_VERDICTS == {"PASS", "WARNING", "FAIL", "blocked"}

(* --algorithm ParallelPassDispatch

variables
  passVerdict      = [p \in PASSES |-> "pending"],
  passBudget       = [p \in PASSES |-> MAX_RETRIES],
  passAttempt      = [p \in PASSES |-> 0],
  autoFix          = TRUE,
  phase2Dispatched = FALSE,
  covDone          = FALSE,
  intDone          = FALSE;

define

  ArtifactsGate ==
    phase2Dispatched =>
      passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

  PhaseBarrier ==
    passAttempt["abstraction_gap"] > 0 => (covDone /\ intDone)

  BudgetNonNegative ==
    \A p \in PASSES : passBudget[p] >= 0

  AttemptBounded ==
    \A p \in PASSES : passAttempt[p] <= MAX_RETRIES + 1

  CoverageGated ==
    passAttempt["coverage"] > 0 =>
      passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

  InteractionGated ==
    passAttempt["interaction"] > 0 =>
      passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

  ImportsAfterPhase3 ==
    passAttempt["imports"] > 0 =>
      passAttempt["abstraction_gap"] > 0

  ConcurrentUnblockInvariant ==
    \A p \in PHASE2_PASSES :
      passAttempt[p] > 0 =>
        passVerdict["artifacts"] \in ENABLING_VERDICTS

  IndependentBudgetBounds ==
    \A p1, p2 \in PHASE2_PASSES :
      p1 /= p2 =>
        (passBudget[p1] >= 0 /\ passBudget[p2] >= 0)

end define;

fair process Orchestrator = "orch"
begin
  ArtifactsRun:
    passAttempt["artifacts"] := 1;
    either
      passVerdict["artifacts"] := "PASS"
    or
      passVerdict["artifacts"] := "WARNING"
    or
      passVerdict["artifacts"] := "FAIL"
    end either;

  ArtifactsGateCheck:
    if passVerdict["artifacts"] \in ENABLING_VERDICTS /\ autoFix then
      phase2Dispatched := TRUE
    else
      passVerdict["coverage"] := "blocked" ||
      passVerdict["interaction"] := "blocked" ||
      phase2Dispatched := TRUE
    end if;

  WaitPhase2:
    await covDone /\ intDone;

  AbsGapStart:
    passAttempt["abstraction_gap"] := 1;

  AbsGapExec:
    if passVerdict["coverage"] \in ENABLING_VERDICTS /\
       passVerdict["interaction"] \in ENABLING_VERDICTS then
      either
        passVerdict["abstraction_gap"] := "PASS"
      or
        passVerdict["abstraction_gap"] := "WARNING"
      or
        passVerdict["abstraction_gap"] := "FAIL"
      end either
    else
      passVerdict["abstraction_gap"] := "blocked"
    end if;

  ImportsStart:
    passAttempt["imports"] := 1;

  ImportsExec:
    if passVerdict["abstraction_gap"] \in ENABLING_VERDICTS then
      either
        passVerdict["imports"] := "PASS"
      or
        passVerdict["imports"] := "WARNING"
      or
        passVerdict["imports"] := "FAIL"
      end either
    else
      passVerdict["imports"] := "blocked"
    end if;

  OrchestratorFinish:
    skip
end process;

fair process CoverageWorker = "cov"
begin
  CovWait:
    await phase2Dispatched;

  CovRun:
    while passVerdict["coverage"] \notin TERMINAL_VERDICTS do
      CovAttempt:
        passAttempt["coverage"] := passAttempt["coverage"] + 1;
        either
          passVerdict["coverage"] := "PASS"
        or
          passVerdict["coverage"] := "WARNING"
        or
          if passBudget["coverage"] > 0 then
            passBudget["coverage"] := passBudget["coverage"] - 1
          else
            passVerdict["coverage"] := "FAIL"
          end if
        end either
    end while;

  CovFinish:
    covDone := TRUE
end process;

fair process InteractionWorker = "int"
begin
  IntWait:
    await phase2Dispatched;

  IntRun:
    while passVerdict["interaction"] \notin TERMINAL_VERDICTS do
      IntAttempt:
        passAttempt["interaction"] := passAttempt["interaction"] + 1;
        either
          passVerdict["interaction"] := "PASS"
        or
          passVerdict["interaction"] := "WARNING"
        or
          if passBudget["interaction"] > 0 then
            passBudget["interaction"] := passBudget["interaction"] - 1
          else
            passVerdict["interaction"] := "FAIL"
          end if
        end either
    end while;

  IntFinish:
    intDone := TRUE
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "449c7b04" /\ chksum(tla) = "73bf7a4b")
VARIABLES pc, passVerdict, passBudget, passAttempt, autoFix, phase2Dispatched, 
          covDone, intDone

(* define statement *)
ArtifactsGate ==
  phase2Dispatched =>
    passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

PhaseBarrier ==
  passAttempt["abstraction_gap"] > 0 => (covDone /\ intDone)

BudgetNonNegative ==
  \A p \in PASSES : passBudget[p] >= 0

AttemptBounded ==
  \A p \in PASSES : passAttempt[p] <= MAX_RETRIES + 1

CoverageGated ==
  passAttempt["coverage"] > 0 =>
    passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

InteractionGated ==
  passAttempt["interaction"] > 0 =>
    passVerdict["artifacts"] \in (ENABLING_VERDICTS \cup {"FAIL"})

ImportsAfterPhase3 ==
  passAttempt["imports"] > 0 =>
    passAttempt["abstraction_gap"] > 0

ConcurrentUnblockInvariant ==
  \A p \in PHASE2_PASSES :
    passAttempt[p] > 0 =>
      passVerdict["artifacts"] \in ENABLING_VERDICTS

IndependentBudgetBounds ==
  \A p1, p2 \in PHASE2_PASSES :
    p1 /= p2 =>
      (passBudget[p1] >= 0 /\ passBudget[p2] >= 0)


vars == << pc, passVerdict, passBudget, passAttempt, autoFix, 
           phase2Dispatched, covDone, intDone >>

ProcSet == {"orch"} \cup {"cov"} \cup {"int"}

Init == (* Global variables *)
        /\ passVerdict = [p \in PASSES |-> "pending"]
        /\ passBudget = [p \in PASSES |-> MAX_RETRIES]
        /\ passAttempt = [p \in PASSES |-> 0]
        /\ autoFix = TRUE
        /\ phase2Dispatched = FALSE
        /\ covDone = FALSE
        /\ intDone = FALSE
        /\ pc = [self \in ProcSet |-> CASE self = "orch" -> "ArtifactsRun"
                                        [] self = "cov" -> "CovWait"
                                        [] self = "int" -> "IntWait"]

ArtifactsRun == /\ pc["orch"] = "ArtifactsRun"
                /\ passAttempt' = [passAttempt EXCEPT !["artifacts"] = 1]
                /\ \/ /\ passVerdict' = [passVerdict EXCEPT !["artifacts"] = "PASS"]
                   \/ /\ passVerdict' = [passVerdict EXCEPT !["artifacts"] = "WARNING"]
                   \/ /\ passVerdict' = [passVerdict EXCEPT !["artifacts"] = "FAIL"]
                /\ pc' = [pc EXCEPT !["orch"] = "ArtifactsGateCheck"]
                /\ UNCHANGED << passBudget, autoFix, phase2Dispatched, covDone, 
                                intDone >>

ArtifactsGateCheck == /\ pc["orch"] = "ArtifactsGateCheck"
                      /\ IF passVerdict["artifacts"] \in ENABLING_VERDICTS /\ autoFix
                            THEN /\ phase2Dispatched' = TRUE
                                 /\ UNCHANGED passVerdict
                            ELSE /\ /\ passVerdict' = [passVerdict EXCEPT !["coverage"] = "blocked",
                                                                          !["interaction"] = "blocked"]
                                    /\ phase2Dispatched' = TRUE
                      /\ pc' = [pc EXCEPT !["orch"] = "WaitPhase2"]
                      /\ UNCHANGED << passBudget, passAttempt, autoFix, 
                                      covDone, intDone >>

WaitPhase2 == /\ pc["orch"] = "WaitPhase2"
              /\ covDone /\ intDone
              /\ pc' = [pc EXCEPT !["orch"] = "AbsGapStart"]
              /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                              phase2Dispatched, covDone, intDone >>

AbsGapStart == /\ pc["orch"] = "AbsGapStart"
               /\ passAttempt' = [passAttempt EXCEPT !["abstraction_gap"] = 1]
               /\ pc' = [pc EXCEPT !["orch"] = "AbsGapExec"]
               /\ UNCHANGED << passVerdict, passBudget, autoFix, 
                               phase2Dispatched, covDone, intDone >>

AbsGapExec == /\ pc["orch"] = "AbsGapExec"
              /\ IF passVerdict["coverage"] \in ENABLING_VERDICTS /\
                    passVerdict["interaction"] \in ENABLING_VERDICTS
                    THEN /\ \/ /\ passVerdict' = [passVerdict EXCEPT !["abstraction_gap"] = "PASS"]
                            \/ /\ passVerdict' = [passVerdict EXCEPT !["abstraction_gap"] = "WARNING"]
                            \/ /\ passVerdict' = [passVerdict EXCEPT !["abstraction_gap"] = "FAIL"]
                    ELSE /\ passVerdict' = [passVerdict EXCEPT !["abstraction_gap"] = "blocked"]
              /\ pc' = [pc EXCEPT !["orch"] = "ImportsStart"]
              /\ UNCHANGED << passBudget, passAttempt, autoFix, 
                              phase2Dispatched, covDone, intDone >>

ImportsStart == /\ pc["orch"] = "ImportsStart"
                /\ passAttempt' = [passAttempt EXCEPT !["imports"] = 1]
                /\ pc' = [pc EXCEPT !["orch"] = "ImportsExec"]
                /\ UNCHANGED << passVerdict, passBudget, autoFix, 
                                phase2Dispatched, covDone, intDone >>

ImportsExec == /\ pc["orch"] = "ImportsExec"
               /\ IF passVerdict["abstraction_gap"] \in ENABLING_VERDICTS
                     THEN /\ \/ /\ passVerdict' = [passVerdict EXCEPT !["imports"] = "PASS"]
                             \/ /\ passVerdict' = [passVerdict EXCEPT !["imports"] = "WARNING"]
                             \/ /\ passVerdict' = [passVerdict EXCEPT !["imports"] = "FAIL"]
                     ELSE /\ passVerdict' = [passVerdict EXCEPT !["imports"] = "blocked"]
               /\ pc' = [pc EXCEPT !["orch"] = "OrchestratorFinish"]
               /\ UNCHANGED << passBudget, passAttempt, autoFix, 
                               phase2Dispatched, covDone, intDone >>

OrchestratorFinish == /\ pc["orch"] = "OrchestratorFinish"
                      /\ TRUE
                      /\ pc' = [pc EXCEPT !["orch"] = "Done"]
                      /\ UNCHANGED << passVerdict, passBudget, passAttempt, 
                                      autoFix, phase2Dispatched, covDone, 
                                      intDone >>

Orchestrator == ArtifactsRun \/ ArtifactsGateCheck \/ WaitPhase2
                   \/ AbsGapStart \/ AbsGapExec \/ ImportsStart
                   \/ ImportsExec \/ OrchestratorFinish

CovWait == /\ pc["cov"] = "CovWait"
           /\ phase2Dispatched
           /\ pc' = [pc EXCEPT !["cov"] = "CovRun"]
           /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                           phase2Dispatched, covDone, intDone >>

CovRun == /\ pc["cov"] = "CovRun"
          /\ IF passVerdict["coverage"] \notin TERMINAL_VERDICTS
                THEN /\ pc' = [pc EXCEPT !["cov"] = "CovAttempt"]
                ELSE /\ pc' = [pc EXCEPT !["cov"] = "CovFinish"]
          /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                          phase2Dispatched, covDone, intDone >>

CovAttempt == /\ pc["cov"] = "CovAttempt"
              /\ passAttempt' = [passAttempt EXCEPT !["coverage"] = passAttempt["coverage"] + 1]
              /\ \/ /\ passVerdict' = [passVerdict EXCEPT !["coverage"] = "PASS"]
                    /\ UNCHANGED passBudget
                 \/ /\ passVerdict' = [passVerdict EXCEPT !["coverage"] = "WARNING"]
                    /\ UNCHANGED passBudget
                 \/ /\ IF passBudget["coverage"] > 0
                          THEN /\ passBudget' = [passBudget EXCEPT !["coverage"] = passBudget["coverage"] - 1]
                               /\ UNCHANGED passVerdict
                          ELSE /\ passVerdict' = [passVerdict EXCEPT !["coverage"] = "FAIL"]
                               /\ UNCHANGED passBudget
              /\ pc' = [pc EXCEPT !["cov"] = "CovRun"]
              /\ UNCHANGED << autoFix, phase2Dispatched, covDone, intDone >>

CovFinish == /\ pc["cov"] = "CovFinish"
             /\ covDone' = TRUE
             /\ pc' = [pc EXCEPT !["cov"] = "Done"]
             /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                             phase2Dispatched, intDone >>

CoverageWorker == CovWait \/ CovRun \/ CovAttempt \/ CovFinish

IntWait == /\ pc["int"] = "IntWait"
           /\ phase2Dispatched
           /\ pc' = [pc EXCEPT !["int"] = "IntRun"]
           /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                           phase2Dispatched, covDone, intDone >>

IntRun == /\ pc["int"] = "IntRun"
          /\ IF passVerdict["interaction"] \notin TERMINAL_VERDICTS
                THEN /\ pc' = [pc EXCEPT !["int"] = "IntAttempt"]
                ELSE /\ pc' = [pc EXCEPT !["int"] = "IntFinish"]
          /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                          phase2Dispatched, covDone, intDone >>

IntAttempt == /\ pc["int"] = "IntAttempt"
              /\ passAttempt' = [passAttempt EXCEPT !["interaction"] = passAttempt["interaction"] + 1]
              /\ \/ /\ passVerdict' = [passVerdict EXCEPT !["interaction"] = "PASS"]
                    /\ UNCHANGED passBudget
                 \/ /\ passVerdict' = [passVerdict EXCEPT !["interaction"] = "WARNING"]
                    /\ UNCHANGED passBudget
                 \/ /\ IF passBudget["interaction"] > 0
                          THEN /\ passBudget' = [passBudget EXCEPT !["interaction"] = passBudget["interaction"] - 1]
                               /\ UNCHANGED passVerdict
                          ELSE /\ passVerdict' = [passVerdict EXCEPT !["interaction"] = "FAIL"]
                               /\ UNCHANGED passBudget
              /\ pc' = [pc EXCEPT !["int"] = "IntRun"]
              /\ UNCHANGED << autoFix, phase2Dispatched, covDone, intDone >>

IntFinish == /\ pc["int"] = "IntFinish"
             /\ intDone' = TRUE
             /\ pc' = [pc EXCEPT !["int"] = "Done"]
             /\ UNCHANGED << passVerdict, passBudget, passAttempt, autoFix, 
                             phase2Dispatched, covDone >>

InteractionWorker == IntWait \/ IntRun \/ IntAttempt \/ IntFinish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Orchestrator \/ CoverageWorker \/ InteractionWorker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Orchestrator)
        /\ WF_vars(CoverageWorker)
        /\ WF_vars(InteractionWorker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec =>
  [](ArtifactsGate           /\
     PhaseBarrier             /\
     BudgetNonNegative        /\
     AttemptBounded           /\
     CoverageGated            /\
     InteractionGated         /\
     ImportsAfterPhase3       /\
     ConcurrentUnblockInvariant /\
     IndependentBudgetBounds)

====
