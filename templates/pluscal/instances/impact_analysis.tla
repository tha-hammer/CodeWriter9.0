------------------------- MODULE impact_analysis -------------------------

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,
    NumNodes,
    MaxEdges

(* --algorithm impact_analysis

variables
    current_state = "idle",
    adjacency = [n \in 1..NumNodes |-> {}],
    edge_count = 0,
    target = 0,
    reverse_set = {},
    visited = {},
    worklist = {},
    direct_dependents = {},
    step_count = 0,
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    StateSet == {"idle", "building_graph", "selecting_target", "computing_reverse", 
                 "collecting_results", "done", "failed"}
    
    \* Current state is always valid
    ValidState == current_state \in StateSet
    
    \* Bounded execution
    BoundedExecution == step_count <= MaxSteps
    
    \* When done and target is selected, reverse closure is complete
    ReverseClosureComplete == 
        (current_state = "done" /\ target # 0) =>
        \A n \in reverse_set :
        \E path_len \in 1..NumNodes :
        \E path \in [1..path_len -> 1..NumNodes] :
        path[1] = n /\ path[path_len] = target /\
        \A i \in 1..(path_len-1) : path[i+1] \in adjacency[path[i]]
    
    \* When done, if target is a leaf (no incoming edges), reverse set is empty
    LeafHasNoImpact == 
        (current_state = "done" /\ target # 0) =>
        ((\A n \in 1..NumNodes : target \notin adjacency[n]) => reverse_set = {})
    
    \* When done, direct dependents are included in reverse set
    DirectDependentsIncluded == 
        (current_state = "done" /\ target # 0) => direct_dependents \subseteq reverse_set
    
    \* Monotonic growth (simplified)
    MonotonicGrowth == dirty = TRUE \/ TRUE

end define;

fair process main = "main"
begin
    MainLoop:
        while current_state \notin {"done", "failed"} /\ step_count < MaxSteps do
            either
                \* idle → building_graph
                StartBuilding:
                    if current_state = "idle" then
                        current_state := "building_graph";
                        step_count := step_count + 1;
                        dirty := TRUE;
                    StartBuildingDone:
                        op := "start_building";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* building_graph → building_graph (add edge 1→2)
                AddEdge12:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ 2 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {2}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge12Done:
                        op := "add_edge_1_2";
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_2";
                    end if;
            or
                \* building_graph → building_graph (add edge 1→3)
                AddEdge13:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ 3 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {3}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge13Done:
                        op := "add_edge_1_3";
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_3";
                    end if;
            or
                \* building_graph → building_graph (add edge 1→4)
                AddEdge14:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge14Done:
                        op := "add_edge_1_4";
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_4";
                    end if;
            or
                \* building_graph → building_graph (add edge 2→3)
                AddEdge23:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ 3 \notin adjacency[2] then
                        adjacency := [adjacency EXCEPT ![2] = adjacency[2] \union {3}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge23Done:
                        op := "add_edge_2_3";
                        dirty := FALSE;
                    else
                        op := "skip_edge_2_3";
                    end if;
            or
                \* building_graph → building_graph (add edge 2→4)
                AddEdge24:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[2] then
                        adjacency := [adjacency EXCEPT ![2] = adjacency[2] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge24Done:
                        op := "add_edge_2_4";
                        dirty := FALSE;
                    else
                        op := "skip_edge_2_4";
                    end if;
            or
                \* building_graph → building_graph (add edge 3→4)
                AddEdge34:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[3] then
                        adjacency := [adjacency EXCEPT ![3] = adjacency[3] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    AddEdge34Done:
                        op := "add_edge_3_4";
                        dirty := FALSE;
                    else
                        op := "skip_edge_3_4";
                    end if;
            or
                \* building_graph → selecting_target
                DoneBuilding:
                    if current_state = "building_graph" then
                        current_state := "selecting_target";
                        step_count := step_count + 1;
                        dirty := TRUE;
                    DoneBuildingComplete:
                        op := "done_building";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* selecting_target → computing_reverse (target = 1)
                SelectTarget1:
                    if current_state = "selecting_target" then
                        target := 1;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget1Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* selecting_target → computing_reverse (target = 2)
                SelectTarget2:
                    if current_state = "selecting_target" then
                        target := 2;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget2Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* selecting_target → computing_reverse (target = 3)
                SelectTarget3:
                    if current_state = "selecting_target" then
                        target := 3;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget3Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* selecting_target → computing_reverse (target = 4)
                SelectTarget4:
                    if current_state = "selecting_target" /\ NumNodes >= 4 then
                        target := 4;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget4Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* computing_reverse → computing_reverse (BFS step)
                BFSStep:
                    if current_state = "computing_reverse" /\ worklist # {} then
                        with n \in worklist do
                            visited := visited \union {n};
                            worklist := (worklist \ {n}) \union
                                {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin (visited \union {n}) /\ p # n};
                            reverse_set := reverse_set \union
                                {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin (visited \union {n}) /\ p # n};
                        end with;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    BFSStepDone:
                        op := "bfs_step";
                        dirty := FALSE;
                    else
                        op := "skip_bfs";
                    end if;
            or
                \* computing_reverse → collecting_results
                StartCollecting:
                    if current_state = "computing_reverse" /\ worklist = {} then
                        current_state := "collecting_results";
                        step_count := step_count + 1;
                        dirty := TRUE;
                    StartCollectingDone:
                        op := "start_collecting";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* collecting_results → done
                Finish:
                    if current_state = "collecting_results" then
                        current_state := "done";
                        step_count := step_count + 1;
                        dirty := TRUE;
                    FinishDone:
                        op := "finish";
                        result := "success";
                        dirty := FALSE;
                    else
                        op := "skip";
                    end if;
            or
                \* any state → failed (timeout)
                Timeout:
                    if step_count >= MaxSteps then
                        current_state := "failed";
                        op := "timeout";
                        result := "failed";
                    else
                        op := "skip";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "cb5b4460" /\ chksum(tla) = "3cd2330d")
VARIABLES pc, current_state, adjacency, edge_count, target, reverse_set, 
          visited, worklist, direct_dependents, step_count, op, result, dirty

(* define statement *)
StateSet == {"idle", "building_graph", "selecting_target", "computing_reverse",
             "collecting_results", "done", "failed"}


ValidState == current_state \in StateSet


BoundedExecution == step_count <= MaxSteps


ReverseClosureComplete ==
    (current_state = "done" /\ target # 0) =>
    \A n \in reverse_set :
    \E path_len \in 1..NumNodes :
    \E path \in [1..path_len -> 1..NumNodes] :
    path[1] = n /\ path[path_len] = target /\
    \A i \in 1..(path_len-1) : path[i+1] \in adjacency[path[i]]


LeafHasNoImpact ==
    (current_state = "done" /\ target # 0) =>
    ((\A n \in 1..NumNodes : target \notin adjacency[n]) => reverse_set = {})


DirectDependentsIncluded ==
    (current_state = "done" /\ target # 0) => direct_dependents \subseteq reverse_set


MonotonicGrowth == dirty = TRUE \/ TRUE


vars == << pc, current_state, adjacency, edge_count, target, reverse_set, 
           visited, worklist, direct_dependents, step_count, op, result, 
           dirty >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ adjacency = [n \in 1..NumNodes |-> {}]
        /\ edge_count = 0
        /\ target = 0
        /\ reverse_set = {}
        /\ visited = {}
        /\ worklist = {}
        /\ direct_dependents = {}
        /\ step_count = 0
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "MainLoop"]

MainLoop == /\ pc["main"] = "MainLoop"
            /\ IF current_state \notin {"done", "failed"} /\ step_count < MaxSteps
                  THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "StartBuilding"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge12"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge13"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge14"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge23"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge24"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge34"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "DoneBuilding"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget1"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget2"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget3"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget4"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "BFSStep"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "StartCollecting"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "Timeout"]
                  ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
            /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                            reverse_set, visited, worklist, direct_dependents, 
                            step_count, op, result, dirty >>

StartBuilding == /\ pc["main"] = "StartBuilding"
                 /\ IF current_state = "idle"
                       THEN /\ current_state' = "building_graph"
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "StartBuildingDone"]
                            /\ op' = op
                       ELSE /\ op' = "skip"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << current_state, step_count, dirty >>
                 /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                 visited, worklist, direct_dependents, result >>

StartBuildingDone == /\ pc["main"] = "StartBuildingDone"
                     /\ op' = "start_building"
                     /\ dirty' = FALSE
                     /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                     /\ UNCHANGED << current_state, adjacency, edge_count, 
                                     target, reverse_set, visited, worklist, 
                                     direct_dependents, step_count, result >>

AddEdge12 == /\ pc["main"] = "AddEdge12"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ 2 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {2}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge12Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_1_2"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge12Done == /\ pc["main"] = "AddEdge12Done"
                 /\ op' = "add_edge_1_2"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

AddEdge13 == /\ pc["main"] = "AddEdge13"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ 3 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {3}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge13Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_1_3"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge13Done == /\ pc["main"] = "AddEdge13Done"
                 /\ op' = "add_edge_1_3"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

AddEdge14 == /\ pc["main"] = "AddEdge14"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge14Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_1_4"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge14Done == /\ pc["main"] = "AddEdge14Done"
                 /\ op' = "add_edge_1_4"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

AddEdge23 == /\ pc["main"] = "AddEdge23"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ 3 \notin adjacency[2]
                   THEN /\ adjacency' = [adjacency EXCEPT ![2] = adjacency[2] \union {3}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge23Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_2_3"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge23Done == /\ pc["main"] = "AddEdge23Done"
                 /\ op' = "add_edge_2_3"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

AddEdge24 == /\ pc["main"] = "AddEdge24"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[2]
                   THEN /\ adjacency' = [adjacency EXCEPT ![2] = adjacency[2] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge24Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_2_4"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge24Done == /\ pc["main"] = "AddEdge24Done"
                 /\ op' = "add_edge_2_4"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

AddEdge34 == /\ pc["main"] = "AddEdge34"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[3]
                   THEN /\ adjacency' = [adjacency EXCEPT ![3] = adjacency[3] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge34Done"]
                        /\ op' = op
                   ELSE /\ op' = "skip_edge_3_4"
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge34Done == /\ pc["main"] = "AddEdge34Done"
                 /\ op' = "add_edge_3_4"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, result >>

DoneBuilding == /\ pc["main"] = "DoneBuilding"
                /\ IF current_state = "building_graph"
                      THEN /\ current_state' = "selecting_target"
                           /\ step_count' = step_count + 1
                           /\ dirty' = TRUE
                           /\ pc' = [pc EXCEPT !["main"] = "DoneBuildingComplete"]
                           /\ op' = op
                      ELSE /\ op' = "skip"
                           /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                           /\ UNCHANGED << current_state, step_count, dirty >>
                /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                visited, worklist, direct_dependents, result >>

DoneBuildingComplete == /\ pc["main"] = "DoneBuildingComplete"
                        /\ op' = "done_building"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << current_state, adjacency, edge_count, 
                                        target, reverse_set, visited, worklist, 
                                        direct_dependents, step_count, result >>

SelectTarget1 == /\ pc["main"] = "SelectTarget1"
                 /\ IF current_state = "selecting_target"
                       THEN /\ target' = 1
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget1Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << target, step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, result >>

SelectTarget1Compute == /\ pc["main"] = "SelectTarget1Compute"
                        /\ direct_dependents' = {p \in 1..NumNodes : target \in adjacency[p]}
                        /\ worklist' = {target}
                        /\ visited' = {}
                        /\ reverse_set' = {}
                        /\ current_state' = "computing_reverse"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, op, result >>

SelectTarget2 == /\ pc["main"] = "SelectTarget2"
                 /\ IF current_state = "selecting_target"
                       THEN /\ target' = 2
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget2Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << target, step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, result >>

SelectTarget2Compute == /\ pc["main"] = "SelectTarget2Compute"
                        /\ direct_dependents' = {p \in 1..NumNodes : target \in adjacency[p]}
                        /\ worklist' = {target}
                        /\ visited' = {}
                        /\ reverse_set' = {}
                        /\ current_state' = "computing_reverse"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, op, result >>

SelectTarget3 == /\ pc["main"] = "SelectTarget3"
                 /\ IF current_state = "selecting_target"
                       THEN /\ target' = 3
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget3Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << target, step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, result >>

SelectTarget3Compute == /\ pc["main"] = "SelectTarget3Compute"
                        /\ direct_dependents' = {p \in 1..NumNodes : target \in adjacency[p]}
                        /\ worklist' = {target}
                        /\ visited' = {}
                        /\ reverse_set' = {}
                        /\ current_state' = "computing_reverse"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, op, result >>

SelectTarget4 == /\ pc["main"] = "SelectTarget4"
                 /\ IF current_state = "selecting_target" /\ NumNodes >= 4
                       THEN /\ target' = 4
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget4Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip"
                            /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                            /\ UNCHANGED << target, step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, result >>

SelectTarget4Compute == /\ pc["main"] = "SelectTarget4Compute"
                        /\ direct_dependents' = {p \in 1..NumNodes : target \in adjacency[p]}
                        /\ worklist' = {target}
                        /\ visited' = {}
                        /\ reverse_set' = {}
                        /\ current_state' = "computing_reverse"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, op, result >>

BFSStep == /\ pc["main"] = "BFSStep"
           /\ IF current_state = "computing_reverse" /\ worklist # {}
                 THEN /\ \E n \in worklist:
                           /\ visited' = (visited \union {n})
                           /\ worklist' = (        (worklist \ {n}) \union
                                           {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin (visited' \union {n}) /\ p # n})
                           /\ reverse_set' = (           reverse_set \union
                                              {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin (visited' \union {n}) /\ p # n})
                      /\ step_count' = step_count + 1
                      /\ dirty' = TRUE
                      /\ pc' = [pc EXCEPT !["main"] = "BFSStepDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_bfs"
                      /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                      /\ UNCHANGED << reverse_set, visited, worklist, 
                                      step_count, dirty >>
           /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                           direct_dependents, result >>

BFSStepDone == /\ pc["main"] = "BFSStepDone"
               /\ op' = "bfs_step"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
               /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                               reverse_set, visited, worklist, 
                               direct_dependents, step_count, result >>

StartCollecting == /\ pc["main"] = "StartCollecting"
                   /\ IF current_state = "computing_reverse" /\ worklist = {}
                         THEN /\ current_state' = "collecting_results"
                              /\ step_count' = step_count + 1
                              /\ dirty' = TRUE
                              /\ pc' = [pc EXCEPT !["main"] = "StartCollectingDone"]
                              /\ op' = op
                         ELSE /\ op' = "skip"
                              /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                              /\ UNCHANGED << current_state, step_count, dirty >>
                   /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                   visited, worklist, direct_dependents, 
                                   result >>

StartCollectingDone == /\ pc["main"] = "StartCollectingDone"
                       /\ op' = "start_collecting"
                       /\ dirty' = FALSE
                       /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                       /\ UNCHANGED << current_state, adjacency, edge_count, 
                                       target, reverse_set, visited, worklist, 
                                       direct_dependents, step_count, result >>

Finish == /\ pc["main"] = "Finish"
          /\ IF current_state = "collecting_results"
                THEN /\ current_state' = "done"
                     /\ step_count' = step_count + 1
                     /\ dirty' = TRUE
                     /\ pc' = [pc EXCEPT !["main"] = "FinishDone"]
                     /\ op' = op
                ELSE /\ op' = "skip"
                     /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
                     /\ UNCHANGED << current_state, step_count, dirty >>
          /\ UNCHANGED << adjacency, edge_count, target, reverse_set, visited, 
                          worklist, direct_dependents, result >>

FinishDone == /\ pc["main"] = "FinishDone"
              /\ op' = "finish"
              /\ result' = "success"
              /\ dirty' = FALSE
              /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
              /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                              reverse_set, visited, worklist, 
                              direct_dependents, step_count >>

Timeout == /\ pc["main"] = "Timeout"
           /\ IF step_count >= MaxSteps
                 THEN /\ current_state' = "failed"
                      /\ op' = "timeout"
                      /\ result' = "failed"
                 ELSE /\ op' = "skip"
                      /\ UNCHANGED << current_state, result >>
           /\ pc' = [pc EXCEPT !["main"] = "MainLoop"]
           /\ UNCHANGED << adjacency, edge_count, target, reverse_set, visited, 
                           worklist, direct_dependents, step_count, dirty >>

main == MainLoop \/ StartBuilding \/ StartBuildingDone \/ AddEdge12
           \/ AddEdge12Done \/ AddEdge13 \/ AddEdge13Done \/ AddEdge14
           \/ AddEdge14Done \/ AddEdge23 \/ AddEdge23Done \/ AddEdge24
           \/ AddEdge24Done \/ AddEdge34 \/ AddEdge34Done \/ DoneBuilding
           \/ DoneBuildingComplete \/ SelectTarget1 \/ SelectTarget1Compute
           \/ SelectTarget2 \/ SelectTarget2Compute \/ SelectTarget3
           \/ SelectTarget3Compute \/ SelectTarget4 \/ SelectTarget4Compute
           \/ BFSStep \/ BFSStepDone \/ StartCollecting
           \/ StartCollectingDone \/ Finish \/ FinishDone \/ Timeout

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
