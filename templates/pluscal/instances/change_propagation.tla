------------------------- MODULE change_propagation -------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,
    NumNodes,
    MaxEdges,
    MaxArtifacts

(* --algorithm change_propagation

variables
    current_state = "idle",
    adjacency = [n \in 1..NumNodes |-> {}],
    edge_count = 0,
    test_artifacts = [n \in 1..NumNodes |-> 0],
    artifact_count = 0,
    target = 0,
    impact_set = {},
    candidates = {},
    affected_tests = {},
    step_count = 0,
    op = "none",
    result = "none",
    dirty = FALSE;

define
    StateSet == {"idle", "building_graph", "assigning_artifacts", "selecting_target", 
                 "computing_impact", "collecting_tests", "done", "failed"}
    
    ValidState == current_state \in StateSet
    
    BoundedExecution == step_count <= MaxSteps
    
    Reachable(start, adj) ==
        LET RECURSIVE Reach(_)
            Reach(visited) ==
                LET next == UNION {adj[n] : n \in visited} \ visited
                IN IF next = {} THEN visited ELSE Reach(visited \union next)
        IN Reach({start})
    
    NoFalsePositives == 
        dirty = TRUE \/ (current_state = "done" => 
            \A a \in affected_tests : \E n \in candidates : test_artifacts[n] = a)
    
    NoFalseNegatives == 
        dirty = TRUE \/ (current_state = "done" => 
            \A n \in candidates : test_artifacts[n] # 0 => test_artifacts[n] \in affected_tests)
    
    SelfTestIncluded == 
        dirty = TRUE \/ (current_state = "done" => 
            (test_artifacts[target] # 0 => test_artifacts[target] \in affected_tests))

end define;

fair process main = "actor"
begin
    Loop:
        while current_state \notin {"done", "failed"} /\ step_count < MaxSteps do
            either
                IdleToBuilding:
                    if current_state = "idle" then
                        adjacency := [n \in 1..NumNodes |-> {}];
                        edge_count := 0;
                        test_artifacts := [n \in 1..NumNodes |-> 0];
                        artifact_count := 0;
                        dirty := TRUE;
                        step_count := step_count + 1;
                        op := "initialize";
                IdleToBuildingDecide:
                        current_state := "building_graph";
                        dirty := FALSE;
                    end if;
            or
                AddEdge:
                    if current_state = "building_graph" /\ edge_count < MaxEdges then
                        with i \in 1..NumNodes, j \in 1..NumNodes do
                            if i < j /\ j \notin adjacency[i] then
                                adjacency := [adjacency EXCEPT ![i] = adjacency[i] \union {j}];
                                edge_count := edge_count + 1;
                                dirty := TRUE;
                                step_count := step_count + 1;
                                op := "add_edge";
                            end if;
                        end with;
                AddEdgeDecide:
                        if dirty then
                            dirty := FALSE;
                        end if;
                    end if;
            or
                BuildingToAssigning:
                    if current_state = "building_graph" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                        op := "finish_building";
                BuildingToAssigningDecide:
                        current_state := "assigning_artifacts";
                        dirty := FALSE;
                    end if;
            or
                AssignArtifact:
                    if current_state = "assigning_artifacts" /\ artifact_count < MaxArtifacts then
                        with n \in 1..NumNodes, a \in 1..MaxArtifacts do
                            if test_artifacts[n] = 0 then
                                test_artifacts := [test_artifacts EXCEPT ![n] = a];
                                artifact_count := artifact_count + 1;
                                dirty := TRUE;
                                step_count := step_count + 1;
                                op := "assign_artifact";
                            end if;
                        end with;
                AssignArtifactDecide:
                        if dirty then
                            dirty := FALSE;
                        end if;
                    end if;
            or
                AssigningToSelecting:
                    if current_state = "assigning_artifacts" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                        op := "finish_assigning";
                AssigningToSelectingDecide:
                        current_state := "selecting_target";
                        dirty := FALSE;
                    end if;
            or
                SelectTarget:
                    if current_state = "selecting_target" then
                        with t \in 1..NumNodes do
                            target := t;
                            impact_set := {};
                            dirty := TRUE;
                            step_count := step_count + 1;
                            op := "select_target";
                        end with;
                SelectTargetDecide:
                        current_state := "computing_impact";
                        dirty := FALSE;
                    end if;
            or
                ComputeImpact:
                    if current_state = "computing_impact" then
                        impact_set := {n \in 1..NumNodes : n # target /\ target \in Reachable(n, adjacency)};
                        dirty := TRUE;
                        step_count := step_count + 1;
                        op := "compute_impact";
                ComputeImpactDecide:
                        current_state := "collecting_tests";
                        candidates := impact_set \union {target};
                        dirty := FALSE;
                    end if;
            or
                CollectTests:
                    if current_state = "collecting_tests" then
                        affected_tests := {test_artifacts[n] : n \in candidates} \ {0};
                        dirty := TRUE;
                        step_count := step_count + 1;
                        op := "collect_tests";
                CollectTestsDecide:
                        current_state := "done";
                        result := "success";
                        dirty := FALSE;
                    end if;
            or
                Timeout:
                    if step_count >= MaxSteps then
                        current_state := "failed";
                        op := "timeout";
                        result := "timeout";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "de3ed68f" /\ chksum(tla) = "50cf7ca4")
VARIABLES pc, current_state, adjacency, edge_count, test_artifacts, 
          artifact_count, target, impact_set, candidates, affected_tests, 
          step_count, op, result, dirty

(* define statement *)
StateSet == {"idle", "building_graph", "assigning_artifacts", "selecting_target",
             "computing_impact", "collecting_tests", "done", "failed"}

ValidState == current_state \in StateSet

BoundedExecution == step_count <= MaxSteps

Reachable(start, adj) ==
    LET RECURSIVE Reach(_)
        Reach(visited) ==
            LET next == UNION {adj[n] : n \in visited} \ visited
            IN IF next = {} THEN visited ELSE Reach(visited \union next)
    IN Reach({start})

NoFalsePositives ==
    dirty = TRUE \/ (current_state = "done" =>
        \A a \in affected_tests : \E n \in candidates : test_artifacts[n] = a)

NoFalseNegatives ==
    dirty = TRUE \/ (current_state = "done" =>
        \A n \in candidates : test_artifacts[n] # 0 => test_artifacts[n] \in affected_tests)

SelfTestIncluded ==
    dirty = TRUE \/ (current_state = "done" =>
        (test_artifacts[target] # 0 => test_artifacts[target] \in affected_tests))


vars == << pc, current_state, adjacency, edge_count, test_artifacts, 
           artifact_count, target, impact_set, candidates, affected_tests, 
           step_count, op, result, dirty >>

ProcSet == {"actor"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ adjacency = [n \in 1..NumNodes |-> {}]
        /\ edge_count = 0
        /\ test_artifacts = [n \in 1..NumNodes |-> 0]
        /\ artifact_count = 0
        /\ target = 0
        /\ impact_set = {}
        /\ candidates = {}
        /\ affected_tests = {}
        /\ step_count = 0
        /\ op = "none"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["actor"] = "Loop"
        /\ IF current_state \notin {"done", "failed"} /\ step_count < MaxSteps
              THEN /\ \/ /\ pc' = [pc EXCEPT !["actor"] = "IdleToBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "AddEdge"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "BuildingToAssigning"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "AssignArtifact"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "AssigningToSelecting"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "SelectTarget"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "ComputeImpact"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "CollectTests"]
                      \/ /\ pc' = [pc EXCEPT !["actor"] = "Timeout"]
              ELSE /\ pc' = [pc EXCEPT !["actor"] = "Done"]
        /\ UNCHANGED << current_state, adjacency, edge_count, test_artifacts, 
                        artifact_count, target, impact_set, candidates, 
                        affected_tests, step_count, op, result, dirty >>

IdleToBuilding == /\ pc["actor"] = "IdleToBuilding"
                  /\ IF current_state = "idle"
                        THEN /\ adjacency' = [n \in 1..NumNodes |-> {}]
                             /\ edge_count' = 0
                             /\ test_artifacts' = [n \in 1..NumNodes |-> 0]
                             /\ artifact_count' = 0
                             /\ dirty' = TRUE
                             /\ step_count' = step_count + 1
                             /\ op' = "initialize"
                             /\ pc' = [pc EXCEPT !["actor"] = "IdleToBuildingDecide"]
                        ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                             /\ UNCHANGED << adjacency, edge_count, 
                                             test_artifacts, artifact_count, 
                                             step_count, op, dirty >>
                  /\ UNCHANGED << current_state, target, impact_set, 
                                  candidates, affected_tests, result >>

IdleToBuildingDecide == /\ pc["actor"] = "IdleToBuildingDecide"
                        /\ current_state' = "building_graph"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, test_artifacts, 
                                        artifact_count, target, impact_set, 
                                        candidates, affected_tests, step_count, 
                                        op, result >>

AddEdge == /\ pc["actor"] = "AddEdge"
           /\ IF current_state = "building_graph" /\ edge_count < MaxEdges
                 THEN /\ \E i \in 1..NumNodes:
                           \E j \in 1..NumNodes:
                             IF i < j /\ j \notin adjacency[i]
                                THEN /\ adjacency' = [adjacency EXCEPT ![i] = adjacency[i] \union {j}]
                                     /\ edge_count' = edge_count + 1
                                     /\ dirty' = TRUE
                                     /\ step_count' = step_count + 1
                                     /\ op' = "add_edge"
                                ELSE /\ TRUE
                                     /\ UNCHANGED << adjacency, edge_count, 
                                                     step_count, op, dirty >>
                      /\ pc' = [pc EXCEPT !["actor"] = "AddEdgeDecide"]
                 ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, step_count, op, 
                                      dirty >>
           /\ UNCHANGED << current_state, test_artifacts, artifact_count, 
                           target, impact_set, candidates, affected_tests, 
                           result >>

AddEdgeDecide == /\ pc["actor"] = "AddEdgeDecide"
                 /\ IF dirty
                       THEN /\ dirty' = FALSE
                       ELSE /\ TRUE
                            /\ dirty' = dirty
                 /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 test_artifacts, artifact_count, target, 
                                 impact_set, candidates, affected_tests, 
                                 step_count, op, result >>

BuildingToAssigning == /\ pc["actor"] = "BuildingToAssigning"
                       /\ IF current_state = "building_graph"
                             THEN /\ dirty' = TRUE
                                  /\ step_count' = step_count + 1
                                  /\ op' = "finish_building"
                                  /\ pc' = [pc EXCEPT !["actor"] = "BuildingToAssigningDecide"]
                             ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                                  /\ UNCHANGED << step_count, op, dirty >>
                       /\ UNCHANGED << current_state, adjacency, edge_count, 
                                       test_artifacts, artifact_count, target, 
                                       impact_set, candidates, affected_tests, 
                                       result >>

BuildingToAssigningDecide == /\ pc["actor"] = "BuildingToAssigningDecide"
                             /\ current_state' = "assigning_artifacts"
                             /\ dirty' = FALSE
                             /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                             /\ UNCHANGED << adjacency, edge_count, 
                                             test_artifacts, artifact_count, 
                                             target, impact_set, candidates, 
                                             affected_tests, step_count, op, 
                                             result >>

AssignArtifact == /\ pc["actor"] = "AssignArtifact"
                  /\ IF current_state = "assigning_artifacts" /\ artifact_count < MaxArtifacts
                        THEN /\ \E n \in 1..NumNodes:
                                  \E a \in 1..MaxArtifacts:
                                    IF test_artifacts[n] = 0
                                       THEN /\ test_artifacts' = [test_artifacts EXCEPT ![n] = a]
                                            /\ artifact_count' = artifact_count + 1
                                            /\ dirty' = TRUE
                                            /\ step_count' = step_count + 1
                                            /\ op' = "assign_artifact"
                                       ELSE /\ TRUE
                                            /\ UNCHANGED << test_artifacts, 
                                                            artifact_count, 
                                                            step_count, op, 
                                                            dirty >>
                             /\ pc' = [pc EXCEPT !["actor"] = "AssignArtifactDecide"]
                        ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                             /\ UNCHANGED << test_artifacts, artifact_count, 
                                             step_count, op, dirty >>
                  /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                  impact_set, candidates, affected_tests, 
                                  result >>

AssignArtifactDecide == /\ pc["actor"] = "AssignArtifactDecide"
                        /\ IF dirty
                              THEN /\ dirty' = FALSE
                              ELSE /\ TRUE
                                   /\ dirty' = dirty
                        /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                        /\ UNCHANGED << current_state, adjacency, edge_count, 
                                        test_artifacts, artifact_count, target, 
                                        impact_set, candidates, affected_tests, 
                                        step_count, op, result >>

AssigningToSelecting == /\ pc["actor"] = "AssigningToSelecting"
                        /\ IF current_state = "assigning_artifacts"
                              THEN /\ dirty' = TRUE
                                   /\ step_count' = step_count + 1
                                   /\ op' = "finish_assigning"
                                   /\ pc' = [pc EXCEPT !["actor"] = "AssigningToSelectingDecide"]
                              ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                                   /\ UNCHANGED << step_count, op, dirty >>
                        /\ UNCHANGED << current_state, adjacency, edge_count, 
                                        test_artifacts, artifact_count, target, 
                                        impact_set, candidates, affected_tests, 
                                        result >>

AssigningToSelectingDecide == /\ pc["actor"] = "AssigningToSelectingDecide"
                              /\ current_state' = "selecting_target"
                              /\ dirty' = FALSE
                              /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                              /\ UNCHANGED << adjacency, edge_count, 
                                              test_artifacts, artifact_count, 
                                              target, impact_set, candidates, 
                                              affected_tests, step_count, op, 
                                              result >>

SelectTarget == /\ pc["actor"] = "SelectTarget"
                /\ IF current_state = "selecting_target"
                      THEN /\ \E t \in 1..NumNodes:
                                /\ target' = t
                                /\ impact_set' = {}
                                /\ dirty' = TRUE
                                /\ step_count' = step_count + 1
                                /\ op' = "select_target"
                           /\ pc' = [pc EXCEPT !["actor"] = "SelectTargetDecide"]
                      ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                           /\ UNCHANGED << target, impact_set, step_count, op, 
                                           dirty >>
                /\ UNCHANGED << current_state, adjacency, edge_count, 
                                test_artifacts, artifact_count, candidates, 
                                affected_tests, result >>

SelectTargetDecide == /\ pc["actor"] = "SelectTargetDecide"
                      /\ current_state' = "computing_impact"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, test_artifacts, 
                                      artifact_count, target, impact_set, 
                                      candidates, affected_tests, step_count, 
                                      op, result >>

ComputeImpact == /\ pc["actor"] = "ComputeImpact"
                 /\ IF current_state = "computing_impact"
                       THEN /\ impact_set' = {n \in 1..NumNodes : n # target /\ target \in Reachable(n, adjacency)}
                            /\ dirty' = TRUE
                            /\ step_count' = step_count + 1
                            /\ op' = "compute_impact"
                            /\ pc' = [pc EXCEPT !["actor"] = "ComputeImpactDecide"]
                       ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                            /\ UNCHANGED << impact_set, step_count, op, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 test_artifacts, artifact_count, target, 
                                 candidates, affected_tests, result >>

ComputeImpactDecide == /\ pc["actor"] = "ComputeImpactDecide"
                       /\ current_state' = "collecting_tests"
                       /\ candidates' = (impact_set \union {target})
                       /\ dirty' = FALSE
                       /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                       /\ UNCHANGED << adjacency, edge_count, test_artifacts, 
                                       artifact_count, target, impact_set, 
                                       affected_tests, step_count, op, result >>

CollectTests == /\ pc["actor"] = "CollectTests"
                /\ IF current_state = "collecting_tests"
                      THEN /\ affected_tests' = {test_artifacts[n] : n \in candidates} \ {0}
                           /\ dirty' = TRUE
                           /\ step_count' = step_count + 1
                           /\ op' = "collect_tests"
                           /\ pc' = [pc EXCEPT !["actor"] = "CollectTestsDecide"]
                      ELSE /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                           /\ UNCHANGED << affected_tests, step_count, op, 
                                           dirty >>
                /\ UNCHANGED << current_state, adjacency, edge_count, 
                                test_artifacts, artifact_count, target, 
                                impact_set, candidates, result >>

CollectTestsDecide == /\ pc["actor"] = "CollectTestsDecide"
                      /\ current_state' = "done"
                      /\ result' = "success"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, test_artifacts, 
                                      artifact_count, target, impact_set, 
                                      candidates, affected_tests, step_count, 
                                      op >>

Timeout == /\ pc["actor"] = "Timeout"
           /\ IF step_count >= MaxSteps
                 THEN /\ current_state' = "failed"
                      /\ op' = "timeout"
                      /\ result' = "timeout"
                 ELSE /\ TRUE
                      /\ UNCHANGED << current_state, op, result >>
           /\ pc' = [pc EXCEPT !["actor"] = "Loop"]
           /\ UNCHANGED << adjacency, edge_count, test_artifacts, 
                           artifact_count, target, impact_set, candidates, 
                           affected_tests, step_count, dirty >>

main == Loop \/ IdleToBuilding \/ IdleToBuildingDecide \/ AddEdge
           \/ AddEdgeDecide \/ BuildingToAssigning
           \/ BuildingToAssigningDecide \/ AssignArtifact
           \/ AssignArtifactDecide \/ AssigningToSelecting
           \/ AssigningToSelectingDecide \/ SelectTarget
           \/ SelectTargetDecide \/ ComputeImpact \/ ComputeImpactDecide
           \/ CollectTests \/ CollectTestsDecide \/ Timeout

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == main
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(main)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

===========================================================================
