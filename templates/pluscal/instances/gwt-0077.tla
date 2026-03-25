---- MODULE ReviewOrchestration ----

EXTENDS Integers, FiniteSets, TLC

(* --algorithm ReviewOrchestration

variables
    current_step = "idle",
    artifacts_verdict = "not_run",
    pass_states = [artifacts       |-> "not_run",
                   coverage        |-> "not_run",
                   interaction     |-> "not_run",
                   abstraction_gap |-> "not_run",
                   imports         |-> "not_run"],
    total_cost = 0,
    overall_status = "pass",
    art_verdict \in {"pass", "fail"};

define
    Passes == {"artifacts","coverage","interaction","abstraction_gap","imports"}

    DependencyOrder ==
        (pass_states["abstraction_gap"] \in {"running","done"}) =>
        (pass_states["coverage"] = "done" /\ pass_states["interaction"] = "done")

    GateEnforcement ==
        (artifacts_verdict = "fail") =>
        (\A p \in Passes \ {"artifacts"} : pass_states[p] = "not_run")

    CostMonotonicity == total_cost >= 0

    CompletionConsistency ==
        (current_step = "done") =>
        (\A p \in Passes : pass_states[p] = "done")

    ParallelSafety ==
        (current_step = "parallel") =>
        (pass_states["coverage"] \in {"running","done"} /\
         pass_states["interaction"] \in {"running","done"})

    BoundedCost == total_cost <= 5

    TypeOK ==
        /\ current_step \in {"idle","artifacts","parallel",
                              "abstraction_gap","imports","done","blocked"}
        /\ artifacts_verdict \in {"not_run","pass","fail"}
        /\ (\A p \in Passes : pass_states[p] \in {"not_run","running","done"})
        /\ total_cost \in Nat
        /\ overall_status \in {"pass","fail","blocked"}

end define;

fair process Orchestrator = "orch"
begin
    StartArtifacts:
        current_step := "artifacts";
        pass_states["artifacts"] := "running";

    CompleteArtifacts:
        artifacts_verdict := art_verdict;
        total_cost := total_cost + 1;
        pass_states["artifacts"] := "done";

    CheckGate:
        if artifacts_verdict = "fail" then
            goto HandleFail;
        else
            skip;
        end if;

    StartParallel:
        current_step := "parallel";
        pass_states := [pass_states EXCEPT !["coverage"] = "running",
                                           !["interaction"] = "running"];

    ChooseParallel:
        either
            goto FinishCoverageFirst;
        or
            goto FinishInteractionFirst;
        end either;

    FinishCoverageFirst:
        pass_states["coverage"] := "done";
        total_cost := total_cost + 1;
        goto FinishInteractionSecond;

    FinishInteractionFirst:
        pass_states["interaction"] := "done";
        total_cost := total_cost + 1;

    FinishCoverageSecond:
        pass_states["coverage"] := "done";
        total_cost := total_cost + 1;
        goto StartAbstractionGap;

    FinishInteractionSecond:
        pass_states["interaction"] := "done";
        total_cost := total_cost + 1;

    StartAbstractionGap:
        current_step := "abstraction_gap";
        pass_states["abstraction_gap"] := "running";

    CompleteAbstractionGap:
        pass_states["abstraction_gap"] := "done";
        total_cost := total_cost + 1;

    StartImports:
        current_step := "imports";
        pass_states["imports"] := "running";

    CompleteImports:
        pass_states["imports"] := "done";
        total_cost := total_cost + 1;
        current_step := "done";
        goto Terminate;

    HandleFail:
        overall_status := "blocked";
        current_step := "blocked";

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8d972c3c" /\ chksum(tla) = "af5db879")
VARIABLES pc, current_step, artifacts_verdict, pass_states, total_cost, 
          overall_status, art_verdict

(* define statement *)
Passes == {"artifacts","coverage","interaction","abstraction_gap","imports"}

DependencyOrder ==
    (pass_states["abstraction_gap"] \in {"running","done"}) =>
    (pass_states["coverage"] = "done" /\ pass_states["interaction"] = "done")

GateEnforcement ==
    (artifacts_verdict = "fail") =>
    (\A p \in Passes \ {"artifacts"} : pass_states[p] = "not_run")

CostMonotonicity == total_cost >= 0

CompletionConsistency ==
    (current_step = "done") =>
    (\A p \in Passes : pass_states[p] = "done")

ParallelSafety ==
    (current_step = "parallel") =>
    (pass_states["coverage"] \in {"running","done"} /\
     pass_states["interaction"] \in {"running","done"})

BoundedCost == total_cost <= 5

TypeOK ==
    /\ current_step \in {"idle","artifacts","parallel",
                          "abstraction_gap","imports","done","blocked"}
    /\ artifacts_verdict \in {"not_run","pass","fail"}
    /\ (\A p \in Passes : pass_states[p] \in {"not_run","running","done"})
    /\ total_cost \in Nat
    /\ overall_status \in {"pass","fail","blocked"}


vars == << pc, current_step, artifacts_verdict, pass_states, total_cost, 
           overall_status, art_verdict >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ current_step = "idle"
        /\ artifacts_verdict = "not_run"
        /\ pass_states = [artifacts       |-> "not_run",
                          coverage        |-> "not_run",
                          interaction     |-> "not_run",
                          abstraction_gap |-> "not_run",
                          imports         |-> "not_run"]
        /\ total_cost = 0
        /\ overall_status = "pass"
        /\ art_verdict \in {"pass", "fail"}
        /\ pc = [self \in ProcSet |-> "StartArtifacts"]

StartArtifacts == /\ pc["orch"] = "StartArtifacts"
                  /\ current_step' = "artifacts"
                  /\ pass_states' = [pass_states EXCEPT !["artifacts"] = "running"]
                  /\ pc' = [pc EXCEPT !["orch"] = "CompleteArtifacts"]
                  /\ UNCHANGED << artifacts_verdict, total_cost, 
                                  overall_status, art_verdict >>

CompleteArtifacts == /\ pc["orch"] = "CompleteArtifacts"
                     /\ artifacts_verdict' = art_verdict
                     /\ total_cost' = total_cost + 1
                     /\ pass_states' = [pass_states EXCEPT !["artifacts"] = "done"]
                     /\ pc' = [pc EXCEPT !["orch"] = "CheckGate"]
                     /\ UNCHANGED << current_step, overall_status, art_verdict >>

CheckGate == /\ pc["orch"] = "CheckGate"
             /\ IF artifacts_verdict = "fail"
                   THEN /\ pc' = [pc EXCEPT !["orch"] = "HandleFail"]
                   ELSE /\ TRUE
                        /\ pc' = [pc EXCEPT !["orch"] = "StartParallel"]
             /\ UNCHANGED << current_step, artifacts_verdict, pass_states, 
                             total_cost, overall_status, art_verdict >>

StartParallel == /\ pc["orch"] = "StartParallel"
                 /\ current_step' = "parallel"
                 /\ pass_states' = [pass_states EXCEPT !["coverage"] = "running",
                                                       !["interaction"] = "running"]
                 /\ pc' = [pc EXCEPT !["orch"] = "ChooseParallel"]
                 /\ UNCHANGED << artifacts_verdict, total_cost, overall_status, 
                                 art_verdict >>

ChooseParallel == /\ pc["orch"] = "ChooseParallel"
                  /\ \/ /\ pc' = [pc EXCEPT !["orch"] = "FinishCoverageFirst"]
                     \/ /\ pc' = [pc EXCEPT !["orch"] = "FinishInteractionFirst"]
                  /\ UNCHANGED << current_step, artifacts_verdict, pass_states, 
                                  total_cost, overall_status, art_verdict >>

FinishCoverageFirst == /\ pc["orch"] = "FinishCoverageFirst"
                       /\ pass_states' = [pass_states EXCEPT !["coverage"] = "done"]
                       /\ total_cost' = total_cost + 1
                       /\ pc' = [pc EXCEPT !["orch"] = "FinishInteractionSecond"]
                       /\ UNCHANGED << current_step, artifacts_verdict, 
                                       overall_status, art_verdict >>

FinishInteractionFirst == /\ pc["orch"] = "FinishInteractionFirst"
                          /\ pass_states' = [pass_states EXCEPT !["interaction"] = "done"]
                          /\ total_cost' = total_cost + 1
                          /\ pc' = [pc EXCEPT !["orch"] = "FinishCoverageSecond"]
                          /\ UNCHANGED << current_step, artifacts_verdict, 
                                          overall_status, art_verdict >>

FinishCoverageSecond == /\ pc["orch"] = "FinishCoverageSecond"
                        /\ pass_states' = [pass_states EXCEPT !["coverage"] = "done"]
                        /\ total_cost' = total_cost + 1
                        /\ pc' = [pc EXCEPT !["orch"] = "StartAbstractionGap"]
                        /\ UNCHANGED << current_step, artifacts_verdict, 
                                        overall_status, art_verdict >>

FinishInteractionSecond == /\ pc["orch"] = "FinishInteractionSecond"
                           /\ pass_states' = [pass_states EXCEPT !["interaction"] = "done"]
                           /\ total_cost' = total_cost + 1
                           /\ pc' = [pc EXCEPT !["orch"] = "StartAbstractionGap"]
                           /\ UNCHANGED << current_step, artifacts_verdict, 
                                           overall_status, art_verdict >>

StartAbstractionGap == /\ pc["orch"] = "StartAbstractionGap"
                       /\ current_step' = "abstraction_gap"
                       /\ pass_states' = [pass_states EXCEPT !["abstraction_gap"] = "running"]
                       /\ pc' = [pc EXCEPT !["orch"] = "CompleteAbstractionGap"]
                       /\ UNCHANGED << artifacts_verdict, total_cost, 
                                       overall_status, art_verdict >>

CompleteAbstractionGap == /\ pc["orch"] = "CompleteAbstractionGap"
                          /\ pass_states' = [pass_states EXCEPT !["abstraction_gap"] = "done"]
                          /\ total_cost' = total_cost + 1
                          /\ pc' = [pc EXCEPT !["orch"] = "StartImports"]
                          /\ UNCHANGED << current_step, artifacts_verdict, 
                                          overall_status, art_verdict >>

StartImports == /\ pc["orch"] = "StartImports"
                /\ current_step' = "imports"
                /\ pass_states' = [pass_states EXCEPT !["imports"] = "running"]
                /\ pc' = [pc EXCEPT !["orch"] = "CompleteImports"]
                /\ UNCHANGED << artifacts_verdict, total_cost, overall_status, 
                                art_verdict >>

CompleteImports == /\ pc["orch"] = "CompleteImports"
                   /\ pass_states' = [pass_states EXCEPT !["imports"] = "done"]
                   /\ total_cost' = total_cost + 1
                   /\ current_step' = "done"
                   /\ pc' = [pc EXCEPT !["orch"] = "Terminate"]
                   /\ UNCHANGED << artifacts_verdict, overall_status, 
                                   art_verdict >>

HandleFail == /\ pc["orch"] = "HandleFail"
              /\ overall_status' = "blocked"
              /\ current_step' = "blocked"
              /\ pc' = [pc EXCEPT !["orch"] = "Terminate"]
              /\ UNCHANGED << artifacts_verdict, pass_states, total_cost, 
                              art_verdict >>

Terminate == /\ pc["orch"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["orch"] = "Done"]
             /\ UNCHANGED << current_step, artifacts_verdict, pass_states, 
                             total_cost, overall_status, art_verdict >>

Orchestrator == StartArtifacts \/ CompleteArtifacts \/ CheckGate
                   \/ StartParallel \/ ChooseParallel
                   \/ FinishCoverageFirst \/ FinishInteractionFirst
                   \/ FinishCoverageSecond \/ FinishInteractionSecond
                   \/ StartAbstractionGap \/ CompleteAbstractionGap
                   \/ StartImports \/ CompleteImports \/ HandleFail
                   \/ Terminate

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
