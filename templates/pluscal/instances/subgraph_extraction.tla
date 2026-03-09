------------------------- MODULE subgraph_extraction -------------------------

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,
    NumNodes,
    MaxEdges

(* --algorithm subgraph_extraction

variables
    current_state = "idle",
    adjacency = [n \in 1..NumNodes |-> {}],
    edge_count = 0,
    target = 0,
    forward_set = {},
    reverse_set = {},
    subgraph_nodes = {},
    subgraph_edges = {},
    fw_worklist = {},
    fw_visited = {},
    rv_worklist = {},
    rv_visited = {},
    step_count = 0,
    op = "none",
    result = "none",
    dirty = FALSE;

define
    StateSet == {"idle", "building_graph", "selecting_target", "computing_forward", 
                 "computing_reverse", "collecting_edges", "done", "failed"}
    
    ValidState == current_state \in StateSet
    
    BoundedExecution == step_count <= MaxSteps
    
    SubgraphCompleteness == 
        dirty = TRUE \/ current_state # "done" \/
        (target \in subgraph_nodes /\
         forward_set \subseteq subgraph_nodes /\
         reverse_set \subseteq subgraph_nodes)
    
    NoHoles ==
        dirty = TRUE \/ current_state # "done" \/
        (subgraph_nodes = forward_set \union reverse_set \union {target})
    
    NoDanglingEdges ==
        dirty = TRUE \/ current_state # "done" \/
        (\A edge \in subgraph_edges :
            edge[1] \in subgraph_nodes /\ edge[2] \in subgraph_nodes)
    
    IsolatedNodeCorrect ==
        dirty = TRUE \/ current_state # "done" \/
        ((adjacency[target] = {} /\ (\A n \in 1..NumNodes : target \notin adjacency[n])) =>
         (subgraph_nodes = {target} /\ subgraph_edges = {}))

end define;

fair process main = "main"
begin
    Loop:
        while current_state \notin {"done", "failed"} /\ step_count < MaxSteps do
            either
                \* idle → building_graph
                InitGraph:
                    if current_state = "idle" then
                        adjacency := [n \in 1..NumNodes |-> {}];
                        edge_count := 0;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    InitGraphDone:
                        current_state := "building_graph";
                        dirty := FALSE;
                        op := "init_graph";
                    else
                        op := "skip_init";
                    end if;
            or
                \* building_graph → building_graph (add edge)
                AddEdge:
                    if current_state = "building_graph" /\ edge_count < MaxEdges then
                        with i \in 1..NumNodes, j \in 1..NumNodes do
                            if i < j /\ j \notin adjacency[i] then
                                adjacency := [adjacency EXCEPT ![i] = adjacency[i] \union {j}];
                                edge_count := edge_count + 1;
                                dirty := TRUE;
                                step_count := step_count + 1;
                            end if;
                        end with;
                    AddEdgeDone:
                        dirty := FALSE;
                        op := "add_edge";
                    else
                        op := "skip_add_edge";
                    end if;
            or
                \* building_graph → selecting_target
                FinishBuilding:
                    if current_state = "building_graph" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                    FinishBuildingDone:
                        current_state := "selecting_target";
                        dirty := FALSE;
                        op := "finish_building";
                    else
                        op := "skip_finish_building";
                    end if;
            or
                \* selecting_target → computing_forward
                SelectTarget:
                    if current_state = "selecting_target" then
                        with t \in 1..NumNodes do
                            target := t;
                            fw_worklist := adjacency[t];
                            fw_visited := adjacency[t];
                            forward_set := {};
                            dirty := TRUE;
                            step_count := step_count + 1;
                        end with;
                    SelectTargetDone:
                        current_state := "computing_forward";
                        dirty := FALSE;
                        op := "select_target";
                    else
                        op := "skip_select_target";
                    end if;
            or
                \* computing_forward → computing_forward (BFS step)
                ForwardBFS:
                    if current_state = "computing_forward" /\ fw_worklist # {} then
                        with n \in fw_worklist do
                            forward_set := forward_set \union {n};
                            fw_worklist := (fw_worklist \ {n}) \union
                                {s \in adjacency[n] : s \notin fw_visited};
                            fw_visited := fw_visited \union
                                {s \in adjacency[n] : s \notin fw_visited};
                            dirty := TRUE;
                            step_count := step_count + 1;
                        end with;
                    ForwardBFSDone:
                        dirty := FALSE;
                        op := "forward_bfs_step";
                    else
                        op := "skip_forward_bfs";
                    end if;
            or
                \* computing_forward → computing_reverse
                StartReverse:
                    if current_state = "computing_forward" /\ fw_worklist = {} then
                        rv_worklist := {n \in 1..NumNodes : target \in adjacency[n]};
                        rv_visited := {n \in 1..NumNodes : target \in adjacency[n]};
                        reverse_set := {};
                        dirty := TRUE;
                        step_count := step_count + 1;
                    StartReverseDone:
                        current_state := "computing_reverse";
                        dirty := FALSE;
                        op := "start_reverse";
                    else
                        op := "skip_start_reverse";
                    end if;
            or
                \* computing_reverse → computing_reverse (BFS step)
                ReverseBFS:
                    if current_state = "computing_reverse" /\ rv_worklist # {} then
                        with n \in rv_worklist do
                            reverse_set := reverse_set \union {n};
                            rv_worklist := (rv_worklist \ {n}) \union
                                {m \in 1..NumNodes : n \in adjacency[m] /\ m \notin rv_visited};
                            rv_visited := rv_visited \union
                                {m \in 1..NumNodes : n \in adjacency[m] /\ m \notin rv_visited};
                            dirty := TRUE;
                            step_count := step_count + 1;
                        end with;
                    ReverseBFSDone:
                        dirty := FALSE;
                        op := "reverse_bfs_step";
                    else
                        op := "skip_reverse_bfs";
                    end if;
            or
                \* computing_reverse → collecting_edges
                StartCollecting:
                    if current_state = "computing_reverse" /\ rv_worklist = {} then
                        subgraph_nodes := forward_set \union reverse_set \union {target};
                        subgraph_edges := {<<i,j>> \in (subgraph_nodes \X subgraph_nodes) :
                            j \in adjacency[i]};
                        dirty := TRUE;
                        step_count := step_count + 1;
                    StartCollectingDone:
                        current_state := "collecting_edges";
                        dirty := FALSE;
                        op := "start_collecting";
                    else
                        op := "skip_start_collecting";
                    end if;
            or
                \* collecting_edges → done
                Finish:
                    if current_state = "collecting_edges" then
                        result := "success";
                        dirty := TRUE;
                        step_count := step_count + 1;
                    FinishDone:
                        current_state := "done";
                        dirty := FALSE;
                        op := "finish";
                    else
                        op := "skip_finish";
                    end if;
            or
                \* any state → failed (timeout)
                Timeout:
                    if step_count >= MaxSteps then
                        result := "timeout";
                        dirty := TRUE;
                    TimeoutDone:
                        current_state := "failed";
                        dirty := FALSE;
                        op := "timeout";
                    else
                        op := "skip_timeout";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "331cb9d8" /\ chksum(tla) = "9e844ab0")
VARIABLES pc, current_state, adjacency, edge_count, target, forward_set, 
          reverse_set, subgraph_nodes, subgraph_edges, fw_worklist, 
          fw_visited, rv_worklist, rv_visited, step_count, op, result, dirty

(* define statement *)
StateSet == {"idle", "building_graph", "selecting_target", "computing_forward",
             "computing_reverse", "collecting_edges", "done", "failed"}

ValidState == current_state \in StateSet

BoundedExecution == step_count <= MaxSteps

SubgraphCompleteness ==
    dirty = TRUE \/ current_state # "done" \/
    (target \in subgraph_nodes /\
     forward_set \subseteq subgraph_nodes /\
     reverse_set \subseteq subgraph_nodes)

NoHoles ==
    dirty = TRUE \/ current_state # "done" \/
    (subgraph_nodes = forward_set \union reverse_set \union {target})

NoDanglingEdges ==
    dirty = TRUE \/ current_state # "done" \/
    (\A edge \in subgraph_edges :
        edge[1] \in subgraph_nodes /\ edge[2] \in subgraph_nodes)

IsolatedNodeCorrect ==
    dirty = TRUE \/ current_state # "done" \/
    ((adjacency[target] = {} /\ (\A n \in 1..NumNodes : target \notin adjacency[n])) =>
     (subgraph_nodes = {target} /\ subgraph_edges = {}))


vars == << pc, current_state, adjacency, edge_count, target, forward_set, 
           reverse_set, subgraph_nodes, subgraph_edges, fw_worklist, 
           fw_visited, rv_worklist, rv_visited, step_count, op, result, dirty
        >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ adjacency = [n \in 1..NumNodes |-> {}]
        /\ edge_count = 0
        /\ target = 0
        /\ forward_set = {}
        /\ reverse_set = {}
        /\ subgraph_nodes = {}
        /\ subgraph_edges = {}
        /\ fw_worklist = {}
        /\ fw_visited = {}
        /\ rv_worklist = {}
        /\ rv_visited = {}
        /\ step_count = 0
        /\ op = "none"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["main"] = "Loop"
        /\ IF current_state \notin {"done", "failed"} /\ step_count < MaxSteps
              THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "InitGraph"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "FinishBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "SelectTarget"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "ForwardBFS"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "StartReverse"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "ReverseBFS"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "StartCollecting"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "Timeout"]
              ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
        /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                        forward_set, reverse_set, subgraph_nodes, 
                        subgraph_edges, fw_worklist, fw_visited, rv_worklist, 
                        rv_visited, step_count, op, result, dirty >>

InitGraph == /\ pc["main"] = "InitGraph"
             /\ IF current_state = "idle"
                   THEN /\ adjacency' = [n \in 1..NumNodes |-> {}]
                        /\ edge_count' = 0
                        /\ dirty' = TRUE
                        /\ step_count' = step_count + 1
                        /\ pc' = [pc EXCEPT !["main"] = "InitGraphDone"]
                        /\ op' = op
                   ELSE /\ op' = "skip_init"
                        /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                        /\ UNCHANGED << adjacency, edge_count, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, target, forward_set, reverse_set, 
                             subgraph_nodes, subgraph_edges, fw_worklist, 
                             fw_visited, rv_worklist, rv_visited, result >>

InitGraphDone == /\ pc["main"] = "InitGraphDone"
                 /\ current_state' = "building_graph"
                 /\ dirty' = FALSE
                 /\ op' = "init_graph"
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << adjacency, edge_count, target, forward_set, 
                                 reverse_set, subgraph_nodes, subgraph_edges, 
                                 fw_worklist, fw_visited, rv_worklist, 
                                 rv_visited, step_count, result >>

AddEdge == /\ pc["main"] = "AddEdge"
           /\ IF current_state = "building_graph" /\ edge_count < MaxEdges
                 THEN /\ \E i \in 1..NumNodes:
                           \E j \in 1..NumNodes:
                             IF i < j /\ j \notin adjacency[i]
                                THEN /\ adjacency' = [adjacency EXCEPT ![i] = adjacency[i] \union {j}]
                                     /\ edge_count' = edge_count + 1
                                     /\ dirty' = TRUE
                                     /\ step_count' = step_count + 1
                                ELSE /\ TRUE
                                     /\ UNCHANGED << adjacency, edge_count, 
                                                     step_count, dirty >>
                      /\ pc' = [pc EXCEPT !["main"] = "AddEdgeDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_add_edge"
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, step_count, dirty >>
           /\ UNCHANGED << current_state, target, forward_set, reverse_set, 
                           subgraph_nodes, subgraph_edges, fw_worklist, 
                           fw_visited, rv_worklist, rv_visited, result >>

AddEdgeDone == /\ pc["main"] = "AddEdgeDone"
               /\ dirty' = FALSE
               /\ op' = "add_edge"
               /\ pc' = [pc EXCEPT !["main"] = "Loop"]
               /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                               forward_set, reverse_set, subgraph_nodes, 
                               subgraph_edges, fw_worklist, fw_visited, 
                               rv_worklist, rv_visited, step_count, result >>

FinishBuilding == /\ pc["main"] = "FinishBuilding"
                  /\ IF current_state = "building_graph"
                        THEN /\ dirty' = TRUE
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["main"] = "FinishBuildingDone"]
                             /\ op' = op
                        ELSE /\ op' = "skip_finish_building"
                             /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                             /\ UNCHANGED << step_count, dirty >>
                  /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                  forward_set, reverse_set, subgraph_nodes, 
                                  subgraph_edges, fw_worklist, fw_visited, 
                                  rv_worklist, rv_visited, result >>

FinishBuildingDone == /\ pc["main"] = "FinishBuildingDone"
                      /\ current_state' = "selecting_target"
                      /\ dirty' = FALSE
                      /\ op' = "finish_building"
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, target, 
                                      forward_set, reverse_set, subgraph_nodes, 
                                      subgraph_edges, fw_worklist, fw_visited, 
                                      rv_worklist, rv_visited, step_count, 
                                      result >>

SelectTarget == /\ pc["main"] = "SelectTarget"
                /\ IF current_state = "selecting_target"
                      THEN /\ \E t \in 1..NumNodes:
                                /\ target' = t
                                /\ fw_worklist' = adjacency[t]
                                /\ fw_visited' = adjacency[t]
                                /\ forward_set' = {}
                                /\ dirty' = TRUE
                                /\ step_count' = step_count + 1
                           /\ pc' = [pc EXCEPT !["main"] = "SelectTargetDone"]
                           /\ op' = op
                      ELSE /\ op' = "skip_select_target"
                           /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                           /\ UNCHANGED << target, forward_set, fw_worklist, 
                                           fw_visited, step_count, dirty >>
                /\ UNCHANGED << current_state, adjacency, edge_count, 
                                reverse_set, subgraph_nodes, subgraph_edges, 
                                rv_worklist, rv_visited, result >>

SelectTargetDone == /\ pc["main"] = "SelectTargetDone"
                    /\ current_state' = "computing_forward"
                    /\ dirty' = FALSE
                    /\ op' = "select_target"
                    /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                    /\ UNCHANGED << adjacency, edge_count, target, forward_set, 
                                    reverse_set, subgraph_nodes, 
                                    subgraph_edges, fw_worklist, fw_visited, 
                                    rv_worklist, rv_visited, step_count, 
                                    result >>

ForwardBFS == /\ pc["main"] = "ForwardBFS"
              /\ IF current_state = "computing_forward" /\ fw_worklist # {}
                    THEN /\ \E n \in fw_worklist:
                              /\ forward_set' = (forward_set \union {n})
                              /\ fw_worklist' = (           (fw_worklist \ {n}) \union
                                                 {s \in adjacency[n] : s \notin fw_visited})
                              /\ fw_visited' = (          fw_visited \union
                                                {s \in adjacency[n] : s \notin fw_visited})
                              /\ dirty' = TRUE
                              /\ step_count' = step_count + 1
                         /\ pc' = [pc EXCEPT !["main"] = "ForwardBFSDone"]
                         /\ op' = op
                    ELSE /\ op' = "skip_forward_bfs"
                         /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                         /\ UNCHANGED << forward_set, fw_worklist, fw_visited, 
                                         step_count, dirty >>
              /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                              reverse_set, subgraph_nodes, subgraph_edges, 
                              rv_worklist, rv_visited, result >>

ForwardBFSDone == /\ pc["main"] = "ForwardBFSDone"
                  /\ dirty' = FALSE
                  /\ op' = "forward_bfs_step"
                  /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                  /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                  forward_set, reverse_set, subgraph_nodes, 
                                  subgraph_edges, fw_worklist, fw_visited, 
                                  rv_worklist, rv_visited, step_count, result >>

StartReverse == /\ pc["main"] = "StartReverse"
                /\ IF current_state = "computing_forward" /\ fw_worklist = {}
                      THEN /\ rv_worklist' = {n \in 1..NumNodes : target \in adjacency[n]}
                           /\ rv_visited' = {n \in 1..NumNodes : target \in adjacency[n]}
                           /\ reverse_set' = {}
                           /\ dirty' = TRUE
                           /\ step_count' = step_count + 1
                           /\ pc' = [pc EXCEPT !["main"] = "StartReverseDone"]
                           /\ op' = op
                      ELSE /\ op' = "skip_start_reverse"
                           /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                           /\ UNCHANGED << reverse_set, rv_worklist, 
                                           rv_visited, step_count, dirty >>
                /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                forward_set, subgraph_nodes, subgraph_edges, 
                                fw_worklist, fw_visited, result >>

StartReverseDone == /\ pc["main"] = "StartReverseDone"
                    /\ current_state' = "computing_reverse"
                    /\ dirty' = FALSE
                    /\ op' = "start_reverse"
                    /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                    /\ UNCHANGED << adjacency, edge_count, target, forward_set, 
                                    reverse_set, subgraph_nodes, 
                                    subgraph_edges, fw_worklist, fw_visited, 
                                    rv_worklist, rv_visited, step_count, 
                                    result >>

ReverseBFS == /\ pc["main"] = "ReverseBFS"
              /\ IF current_state = "computing_reverse" /\ rv_worklist # {}
                    THEN /\ \E n \in rv_worklist:
                              /\ reverse_set' = (reverse_set \union {n})
                              /\ rv_worklist' = (           (rv_worklist \ {n}) \union
                                                 {m \in 1..NumNodes : n \in adjacency[m] /\ m \notin rv_visited})
                              /\ rv_visited' = (          rv_visited \union
                                                {m \in 1..NumNodes : n \in adjacency[m] /\ m \notin rv_visited})
                              /\ dirty' = TRUE
                              /\ step_count' = step_count + 1
                         /\ pc' = [pc EXCEPT !["main"] = "ReverseBFSDone"]
                         /\ op' = op
                    ELSE /\ op' = "skip_reverse_bfs"
                         /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                         /\ UNCHANGED << reverse_set, rv_worklist, rv_visited, 
                                         step_count, dirty >>
              /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                              forward_set, subgraph_nodes, subgraph_edges, 
                              fw_worklist, fw_visited, result >>

ReverseBFSDone == /\ pc["main"] = "ReverseBFSDone"
                  /\ dirty' = FALSE
                  /\ op' = "reverse_bfs_step"
                  /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                  /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                                  forward_set, reverse_set, subgraph_nodes, 
                                  subgraph_edges, fw_worklist, fw_visited, 
                                  rv_worklist, rv_visited, step_count, result >>

StartCollecting == /\ pc["main"] = "StartCollecting"
                   /\ IF current_state = "computing_reverse" /\ rv_worklist = {}
                         THEN /\ subgraph_nodes' = (forward_set \union reverse_set \union {target})
                              /\ subgraph_edges' =               {<<i,j>> \in (subgraph_nodes' \X subgraph_nodes') :
                                                   j \in adjacency[i]}
                              /\ dirty' = TRUE
                              /\ step_count' = step_count + 1
                              /\ pc' = [pc EXCEPT !["main"] = "StartCollectingDone"]
                              /\ op' = op
                         ELSE /\ op' = "skip_start_collecting"
                              /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                              /\ UNCHANGED << subgraph_nodes, subgraph_edges, 
                                              step_count, dirty >>
                   /\ UNCHANGED << current_state, adjacency, edge_count, 
                                   target, forward_set, reverse_set, 
                                   fw_worklist, fw_visited, rv_worklist, 
                                   rv_visited, result >>

StartCollectingDone == /\ pc["main"] = "StartCollectingDone"
                       /\ current_state' = "collecting_edges"
                       /\ dirty' = FALSE
                       /\ op' = "start_collecting"
                       /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                       /\ UNCHANGED << adjacency, edge_count, target, 
                                       forward_set, reverse_set, 
                                       subgraph_nodes, subgraph_edges, 
                                       fw_worklist, fw_visited, rv_worklist, 
                                       rv_visited, step_count, result >>

Finish == /\ pc["main"] = "Finish"
          /\ IF current_state = "collecting_edges"
                THEN /\ result' = "success"
                     /\ dirty' = TRUE
                     /\ step_count' = step_count + 1
                     /\ pc' = [pc EXCEPT !["main"] = "FinishDone"]
                     /\ op' = op
                ELSE /\ op' = "skip_finish"
                     /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                     /\ UNCHANGED << step_count, result, dirty >>
          /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                          forward_set, reverse_set, subgraph_nodes, 
                          subgraph_edges, fw_worklist, fw_visited, rv_worklist, 
                          rv_visited >>

FinishDone == /\ pc["main"] = "FinishDone"
              /\ current_state' = "done"
              /\ dirty' = FALSE
              /\ op' = "finish"
              /\ pc' = [pc EXCEPT !["main"] = "Loop"]
              /\ UNCHANGED << adjacency, edge_count, target, forward_set, 
                              reverse_set, subgraph_nodes, subgraph_edges, 
                              fw_worklist, fw_visited, rv_worklist, rv_visited, 
                              step_count, result >>

Timeout == /\ pc["main"] = "Timeout"
           /\ IF step_count >= MaxSteps
                 THEN /\ result' = "timeout"
                      /\ dirty' = TRUE
                      /\ pc' = [pc EXCEPT !["main"] = "TimeoutDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_timeout"
                      /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                      /\ UNCHANGED << result, dirty >>
           /\ UNCHANGED << current_state, adjacency, edge_count, target, 
                           forward_set, reverse_set, subgraph_nodes, 
                           subgraph_edges, fw_worklist, fw_visited, 
                           rv_worklist, rv_visited, step_count >>

TimeoutDone == /\ pc["main"] = "TimeoutDone"
               /\ current_state' = "failed"
               /\ dirty' = FALSE
               /\ op' = "timeout"
               /\ pc' = [pc EXCEPT !["main"] = "Loop"]
               /\ UNCHANGED << adjacency, edge_count, target, forward_set, 
                               reverse_set, subgraph_nodes, subgraph_edges, 
                               fw_worklist, fw_visited, rv_worklist, 
                               rv_visited, step_count, result >>

main == Loop \/ InitGraph \/ InitGraphDone \/ AddEdge \/ AddEdgeDone
           \/ FinishBuilding \/ FinishBuildingDone \/ SelectTarget
           \/ SelectTargetDone \/ ForwardBFS \/ ForwardBFSDone
           \/ StartReverse \/ StartReverseDone \/ ReverseBFS
           \/ ReverseBFSDone \/ StartCollecting \/ StartCollectingDone
           \/ Finish \/ FinishDone \/ Timeout \/ TimeoutDone

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
