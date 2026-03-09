------------------------- MODULE impact_analysis -------------------------
(*
 * Impact Analysis Query System — PlusCal Specification
 * 
 * Reverse dependency traversal that finds all nodes transitively 
 * depending on a target node in a directed graph (DAG).
 *)

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,           \* bound for model checking
    NumNodes,           \* number of nodes in the graph
    MaxEdges            \* maximum number of edges to add

(* --algorithm impact_analysis

variables
    current_state = "idle",
    adjacency = [n \in 1..NumNodes |-> {}],   \* adjacency list representation
    edge_count = 0,
    target = 0,                               \* 0 means not selected yet
    reverse_set = {},                         \* result set
    visited = {},                             \* BFS tracking
    worklist = {},                            \* BFS queue
    direct_dependents = {},                   \* nodes with direct edge to target
    step_count = 0,
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    \* --- State definitions ---
    StateSet == {"idle", "building_graph", "selecting_target", "computing_reverse", "collecting_results", "done", "failed"}
    TerminalStates == {"done", "failed"}
    
    \* --- Invariants ---
    
    \* Current state is always valid
    ValidState == current_state \in StateSet
    
    \* Bounded execution
    BoundedExecution == step_count <= MaxSteps
    
    \* Reverse closure completeness: when done, every node in reverse_set has a path to target
    ReverseClosureComplete == 
        dirty = TRUE \/ 
        (current_state = "done" /\ target # 0) =>
            \A n \in reverse_set : 
                \E path_len \in 1..NumNodes : 
                    \E path \in [1..path_len -> 1..NumNodes] :
                        /\ path[1] = n
                        /\ path[path_len] = target
                        /\ \A i \in 1..(path_len-1) : path[i+1] \in adjacency[path[i]]
    
    \* If target has no predecessors, reverse_set should be empty
    LeafHasNoImpact ==
        dirty = TRUE \/
        (current_state = "done" /\ target # 0) =>
            ((\A p \in 1..NumNodes : target \notin adjacency[p]) => reverse_set = {})
    
    \* Direct dependents are included in reverse set
    DirectDependentsIncluded ==
        dirty = TRUE \/
        (current_state = "done" /\ target # 0) =>
            direct_dependents \subseteq reverse_set
    
    \* Monotonic growth (simplified)
    MonotonicGrowth == dirty = TRUE \/ TRUE

end define;

fair process main = "main"
begin
    Loop:
        while current_state \notin TerminalStates /\ step_count < MaxSteps do
            either
                \* --- Start building graph ---
                StartBuilding:
                    if current_state = "idle" then
                        current_state := "building_graph";
                        step_count := step_count + 1;
                        op := "start_building";
                        dirty := TRUE;
                    StartBuildingDone:
                        dirty := FALSE;
                    else
                        op := "skip_start";
                    end if;
            or
                \* --- Add edge 1->2 ---
                AddEdge12:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ 2 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {2}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_1_2";
                        dirty := TRUE;
                    AddEdge12Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_2";
                    end if;
            or
                \* --- Add edge 1->3 ---
                AddEdge13:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 3 /\ 3 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {3}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_1_3";
                        dirty := TRUE;
                    AddEdge13Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_3";
                    end if;
            or
                \* --- Add edge 1->4 ---
                AddEdge14:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[1] then
                        adjacency := [adjacency EXCEPT ![1] = adjacency[1] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_1_4";
                        dirty := TRUE;
                    AddEdge14Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_1_4";
                    end if;
            or
                \* --- Add edge 2->3 ---
                AddEdge23:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 3 /\ 3 \notin adjacency[2] then
                        adjacency := [adjacency EXCEPT ![2] = adjacency[2] \union {3}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_2_3";
                        dirty := TRUE;
                    AddEdge23Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_2_3";
                    end if;
            or
                \* --- Add edge 2->4 ---
                AddEdge24:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[2] then
                        adjacency := [adjacency EXCEPT ![2] = adjacency[2] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_2_4";
                        dirty := TRUE;
                    AddEdge24Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_2_4";
                    end if;
            or
                \* --- Add edge 3->4 ---
                AddEdge34:
                    if current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[3] then
                        adjacency := [adjacency EXCEPT ![3] = adjacency[3] \union {4}];
                        edge_count := edge_count + 1;
                        step_count := step_count + 1;
                        op := "add_edge_3_4";
                        dirty := TRUE;
                    AddEdge34Done:
                        dirty := FALSE;
                    else
                        op := "skip_edge_3_4";
                    end if;
            or
                \* --- Finish building graph ---
                FinishBuilding:
                    if current_state = "building_graph" then
                        current_state := "selecting_target";
                        step_count := step_count + 1;
                        op := "finish_building";
                        dirty := TRUE;
                    FinishBuildingDone:
                        dirty := FALSE;
                    else
                        op := "skip_finish_building";
                    end if;
            or
                \* --- Select target node 1 ---
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
                        op := "select_target_1";
                        dirty := FALSE;
                    else
                        op := "skip_select_1";
                    end if;
            or
                \* --- Select target node 2 ---
                SelectTarget2:
                    if current_state = "selecting_target" /\ NumNodes >= 2 then
                        target := 2;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget2Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        op := "select_target_2";
                        dirty := FALSE;
                    else
                        op := "skip_select_2";
                    end if;
            or
                \* --- Select target node 3 ---
                SelectTarget3:
                    if current_state = "selecting_target" /\ NumNodes >= 3 then
                        target := 3;
                        step_count := step_count + 1;
                        dirty := TRUE;
                    SelectTarget3Compute:
                        direct_dependents := {p \in 1..NumNodes : target \in adjacency[p]};
                        worklist := {target};
                        visited := {};
                        reverse_set := {};
                        current_state := "computing_reverse";
                        op := "select_target_3";
                        dirty := FALSE;
                    else
                        op := "skip_select_3";
                    end if;
            or
                \* --- Select target node 4 ---
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
                        op := "select_target_4";
                        dirty := FALSE;
                    else
                        op := "skip_select_4";
                    end if;
            or
                \* --- BFS step ---
                BFSStep:
                    if current_state = "computing_reverse" /\ worklist # {} then
                        with n \in worklist do
                            visited := visited \union {n};
                            worklist := (worklist \ {n}) \union
                                {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin visited /\ p # n};
                            reverse_set := reverse_set \union
                                {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin visited /\ p # n};
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
                \* --- Finish computing reverse ---
                FinishComputing:
                    if current_state = "computing_reverse" /\ worklist = {} then
                        current_state := "collecting_results";
                        step_count := step_count + 1;
                        op := "finish_computing";
                        dirty := TRUE;
                    FinishComputingDone:
                        dirty := FALSE;
                    else
                        op := "skip_finish_computing";
                    end if;
            or
                \* --- Collect results ---
                CollectResults:
                    if current_state = "collecting_results" then
                        current_state := "done";
                        step_count := step_count + 1;
                        op := "collect_results";
                        result := "success";
                        dirty := TRUE;
                    CollectResultsDone:
                        dirty := FALSE;
                    else
                        op := "skip_collect";
                    end if;
            or
                \* --- Timeout failure ---
                TimeoutFailure:
                    if step_count >= MaxSteps then
                        current_state := "failed";
                        op := "timeout";
                        result := "timeout";
                        dirty := TRUE;
                    TimeoutFailureDone:
                        dirty := FALSE;
                    else
                        op := "skip_timeout";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "187d6e4b" /\ chksum(tla) = "8c19c4d7")
VARIABLES pc, current_state, adjacency, edge_count, target, reverse_set, 
          visited, worklist, direct_dependents, step_count, op, result, dirty

(* define statement *)
StateSet == {"idle", "building_graph", "selecting_target", "computing_reverse", "collecting_results", "done", "failed"}
TerminalStates == {"done", "failed"}




ValidState == current_state \in StateSet


BoundedExecution == step_count <= MaxSteps


ReverseClosureComplete ==
    dirty = TRUE \/
    (current_state = "done" /\ target # 0) =>
        \A n \in reverse_set :
            \E path_len \in 1..NumNodes :
                \E path \in [1..path_len -> 1..NumNodes] :
                    /\ path[1] = n
                    /\ path[path_len] = target
                    /\ \A i \in 1..(path_len-1) : path[i+1] \in adjacency[path[i]]


LeafHasNoImpact ==
    dirty = TRUE \/
    (current_state = "done" /\ target # 0) =>
        ((\A p \in 1..NumNodes : target \notin adjacency[p]) => reverse_set = {})


DirectDependentsIncluded ==
    dirty = TRUE \/
    (current_state = "done" /\ target # 0) =>
        direct_dependents \subseteq reverse_set


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
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["main"] = "Loop"
        /\ IF current_state \notin TerminalStates /\ step_count < MaxSteps
              THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "StartBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge12"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge13"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge14"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge23"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge24"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge34"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "FinishBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget1"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget2"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget3"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget4"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "BFSStep"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "FinishComputing"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "CollectResults"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "TimeoutFailure"]
              ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
        /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                        reverse_set, visited, worklist, direct_dependents, 
                        step_count, op, result, dirty >>

StartBuilding == /\ pc["main"] = "StartBuilding"
                 /\ IF current_state = "idle"
                       THEN /\ current_state' = "building_graph"
                            /\ step_count' = step_count + 1
                            /\ op' = "start_building"
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "StartBuildingDone"]
                       ELSE /\ op' = "skip_start"
                            /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                            /\ UNCHANGED << current_state, step_count, dirty >>
                 /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                 visited, worklist, direct_dependents, result >>

StartBuildingDone == /\ pc["main"] = "StartBuildingDone"
                     /\ dirty' = FALSE
                     /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                     /\ UNCHANGED << current_state, adjacency, edge_count, 
                                     target, reverse_set, visited, worklist, 
                                     direct_dependents, step_count, op, result >>

AddEdge12 == /\ pc["main"] = "AddEdge12"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ 2 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {2}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_1_2"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge12Done"]
                   ELSE /\ op' = "skip_edge_1_2"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge12Done == /\ pc["main"] = "AddEdge12Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

AddEdge13 == /\ pc["main"] = "AddEdge13"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 3 /\ 3 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {3}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_1_3"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge13Done"]
                   ELSE /\ op' = "skip_edge_1_3"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge13Done == /\ pc["main"] = "AddEdge13Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

AddEdge14 == /\ pc["main"] = "AddEdge14"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[1]
                   THEN /\ adjacency' = [adjacency EXCEPT ![1] = adjacency[1] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_1_4"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge14Done"]
                   ELSE /\ op' = "skip_edge_1_4"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge14Done == /\ pc["main"] = "AddEdge14Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

AddEdge23 == /\ pc["main"] = "AddEdge23"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 3 /\ 3 \notin adjacency[2]
                   THEN /\ adjacency' = [adjacency EXCEPT ![2] = adjacency[2] \union {3}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_2_3"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge23Done"]
                   ELSE /\ op' = "skip_edge_2_3"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge23Done == /\ pc["main"] = "AddEdge23Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

AddEdge24 == /\ pc["main"] = "AddEdge24"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[2]
                   THEN /\ adjacency' = [adjacency EXCEPT ![2] = adjacency[2] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_2_4"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge24Done"]
                   ELSE /\ op' = "skip_edge_2_4"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge24Done == /\ pc["main"] = "AddEdge24Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

AddEdge34 == /\ pc["main"] = "AddEdge34"
             /\ IF current_state = "building_graph" /\ edge_count < MaxEdges /\ NumNodes >= 4 /\ 4 \notin adjacency[3]
                   THEN /\ adjacency' = [adjacency EXCEPT ![3] = adjacency[3] \union {4}]
                        /\ edge_count' = edge_count + 1
                        /\ step_count' = step_count + 1
                        /\ op' = "add_edge_3_4"
                        /\ dirty' = TRUE
                        /\ pc' = [pc EXCEPT !["main"] = "AddEdge34Done"]
                   ELSE /\ op' = "skip_edge_3_4"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, reverse_set, visited, 
                             worklist, direct_dependents, result >>

AddEdge34Done == /\ pc["main"] = "AddEdge34Done"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                 reverse_set, visited, worklist, 
                                 direct_dependents, step_count, op, result >>

FinishBuilding == /\ pc["main"] = "FinishBuilding"
                  /\ IF current_state = "building_graph"
                        THEN /\ current_state' = "selecting_target"
                             /\ step_count' = step_count + 1
                             /\ op' = "finish_building"
                             /\ dirty' = TRUE
                             /\ pc' = [pc EXCEPT !["main"] = "FinishBuildingDone"]
                        ELSE /\ op' = "skip_finish_building"
                             /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                             /\ UNCHANGED << current_state, step_count, dirty >>
                  /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                  visited, worklist, direct_dependents, result >>

FinishBuildingDone == /\ pc["main"] = "FinishBuildingDone"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << current_state, adjacency, edge_count, 
                                      target, reverse_set, visited, worklist, 
                                      direct_dependents, step_count, op, 
                                      result >>

SelectTarget1 == /\ pc["main"] = "SelectTarget1"
                 /\ IF current_state = "selecting_target"
                       THEN /\ target' = 1
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget1Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip_select_1"
                            /\ pc' = [pc EXCEPT !["main"] = "Loop"]
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
                        /\ op' = "select_target_1"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, result >>

SelectTarget2 == /\ pc["main"] = "SelectTarget2"
                 /\ IF current_state = "selecting_target" /\ NumNodes >= 2
                       THEN /\ target' = 2
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget2Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip_select_2"
                            /\ pc' = [pc EXCEPT !["main"] = "Loop"]
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
                        /\ op' = "select_target_2"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, result >>

SelectTarget3 == /\ pc["main"] = "SelectTarget3"
                 /\ IF current_state = "selecting_target" /\ NumNodes >= 3
                       THEN /\ target' = 3
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget3Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip_select_3"
                            /\ pc' = [pc EXCEPT !["main"] = "Loop"]
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
                        /\ op' = "select_target_3"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, result >>

SelectTarget4 == /\ pc["main"] = "SelectTarget4"
                 /\ IF current_state = "selecting_target" /\ NumNodes >= 4
                       THEN /\ target' = 4
                            /\ step_count' = step_count + 1
                            /\ dirty' = TRUE
                            /\ pc' = [pc EXCEPT !["main"] = "SelectTarget4Compute"]
                            /\ op' = op
                       ELSE /\ op' = "skip_select_4"
                            /\ pc' = [pc EXCEPT !["main"] = "Loop"]
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
                        /\ op' = "select_target_4"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, target, 
                                        step_count, result >>

BFSStep == /\ pc["main"] = "BFSStep"
           /\ IF current_state = "computing_reverse" /\ worklist # {}
                 THEN /\ \E n \in worklist:
                           /\ visited' = (visited \union {n})
                           /\ worklist' = (        (worklist \ {n}) \union
                                           {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin visited' /\ p # n})
                           /\ reverse_set' = (           reverse_set \union
                                              {p \in 1..NumNodes : n \in adjacency[p] /\ p \notin visited' /\ p # n})
                      /\ step_count' = step_count + 1
                      /\ dirty' = TRUE
                      /\ pc' = [pc EXCEPT !["main"] = "BFSStepDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_bfs"
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << reverse_set, visited, worklist, 
                                      step_count, dirty >>
           /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                           direct_dependents, result >>

BFSStepDone == /\ pc["main"] = "BFSStepDone"
               /\ op' = "bfs_step"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["main"] = "Loop"]
               /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                               reverse_set, visited, worklist, 
                               direct_dependents, step_count, result >>

FinishComputing == /\ pc["main"] = "FinishComputing"
                   /\ IF current_state = "computing_reverse" /\ worklist = {}
                         THEN /\ current_state' = "collecting_results"
                              /\ step_count' = step_count + 1
                              /\ op' = "finish_computing"
                              /\ dirty' = TRUE
                              /\ pc' = [pc EXCEPT !["main"] = "FinishComputingDone"]
                         ELSE /\ op' = "skip_finish_computing"
                              /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                              /\ UNCHANGED << current_state, step_count, dirty >>
                   /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                   visited, worklist, direct_dependents, 
                                   result >>

FinishComputingDone == /\ pc["main"] = "FinishComputingDone"
                       /\ dirty' = FALSE
                       /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                       /\ UNCHANGED << current_state, adjacency, edge_count, 
                                       target, reverse_set, visited, worklist, 
                                       direct_dependents, step_count, op, 
                                       result >>

CollectResults == /\ pc["main"] = "CollectResults"
                  /\ IF current_state = "collecting_results"
                        THEN /\ current_state' = "done"
                             /\ step_count' = step_count + 1
                             /\ op' = "collect_results"
                             /\ result' = "success"
                             /\ dirty' = TRUE
                             /\ pc' = [pc EXCEPT !["main"] = "CollectResultsDone"]
                        ELSE /\ op' = "skip_collect"
                             /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                             /\ UNCHANGED << current_state, step_count, result, 
                                             dirty >>
                  /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                  visited, worklist, direct_dependents >>

CollectResultsDone == /\ pc["main"] = "CollectResultsDone"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << current_state, adjacency, edge_count, 
                                      target, reverse_set, visited, worklist, 
                                      direct_dependents, step_count, op, 
                                      result >>

TimeoutFailure == /\ pc["main"] = "TimeoutFailure"
                  /\ IF step_count >= MaxSteps
                        THEN /\ current_state' = "failed"
                             /\ op' = "timeout"
                             /\ result' = "timeout"
                             /\ dirty' = TRUE
                             /\ pc' = [pc EXCEPT !["main"] = "TimeoutFailureDone"]
                        ELSE /\ op' = "skip_timeout"
                             /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                             /\ UNCHANGED << current_state, result, dirty >>
                  /\ UNCHANGED << adjacency, edge_count, target, reverse_set, 
                                  visited, worklist, direct_dependents, 
                                  step_count >>

TimeoutFailureDone == /\ pc["main"] = "TimeoutFailureDone"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << current_state, adjacency, edge_count, 
                                      target, reverse_set, visited, worklist, 
                                      direct_dependents, step_count, op, 
                                      result >>

main == Loop \/ StartBuilding \/ StartBuildingDone \/ AddEdge12
           \/ AddEdge12Done \/ AddEdge13 \/ AddEdge13Done \/ AddEdge14
           \/ AddEdge14Done \/ AddEdge23 \/ AddEdge23Done \/ AddEdge24
           \/ AddEdge24Done \/ AddEdge34 \/ AddEdge34Done \/ FinishBuilding
           \/ FinishBuildingDone \/ SelectTarget1 \/ SelectTarget1Compute
           \/ SelectTarget2 \/ SelectTarget2Compute \/ SelectTarget3
           \/ SelectTarget3Compute \/ SelectTarget4 \/ SelectTarget4Compute
           \/ BFSStep \/ BFSStepDone \/ FinishComputing
           \/ FinishComputingDone \/ CollectResults \/ CollectResultsDone
           \/ TimeoutFailure \/ TimeoutFailureDone

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
