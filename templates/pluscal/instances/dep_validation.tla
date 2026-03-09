------------------------- MODULE dep_validation -------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    MaxSteps,          \* bound for model checking
    NumNodes,          \* number of nodes in the graph (e.g., 4)
    MaxEdges,          \* maximum edges to add during construction
    NumKinds           \* number of node kinds (e.g., 4 for kinds 0..3)

(* --algorithm dep_validation

variables
    current_state = "idle",
    adjacency = [n \in 1..NumNodes |-> {}],     \* adjacency list representation
    node_kind = [n \in 1..NumNodes |-> 0],      \* node kind assignments
    edge_count = 0,                             \* edges added so far
    proposed_from = 0,                          \* source of proposed edge (0 = not set)
    proposed_to = 0,                            \* target of proposed edge (0 = not set)  
    proposed_edge_type = 0,                     \* 0=other, 1=depends_on
    is_valid = TRUE,                            \* validation result
    rejection_reason = "",                      \* "" | "cycle" | "duplicate" | "kind"
    reachable = {},                             \* nodes reachable from proposed_to
    visited = {},                               \* nodes visited in BFS
    worklist = {},                              \* nodes to process in BFS
    step_count = 0,                             \* step counter
    op = "idle",                                \* last operation
    result = "none",                            \* operation result
    dirty = FALSE;                              \* two-phase flag

define
    \* --- State Set ---
    StateSet == {"idle", "building_graph", "proposing_edge", "checking_acyclicity",
                 "checking_duplicate", "checking_kind", "computing_result", "done", "failed"}
    
    TerminalStates == {"done", "failed"}

    \* --- Invariants ---
    
    ValidState == current_state \in StateSet
    
    BoundedExecution == step_count <= MaxSteps
    
    \* Only check when we have valid proposed edges and are done
    ValidProposedEdge == (proposed_from \in 1..NumNodes) /\ (proposed_to \in 1..NumNodes)
    
    \* Acyclicity: when done and valid, proposed_from should not be reachable from proposed_to
    AcyclicityPreserved == 
        dirty = TRUE \/ 
        (current_state = "done" /\ ValidProposedEdge /\ is_valid = TRUE => 
         proposed_from \notin reachable)
    
    \* Duplicate rejection: when rejecting for duplicate, edge should actually exist
    DuplicateRejected == 
        dirty = TRUE \/
        (current_state = "done" /\ ValidProposedEdge /\ rejection_reason = "duplicate" =>
         proposed_to \in adjacency[proposed_from])
    
    \* Kind compatibility: when done and valid with depends_on edge, kinds should be compatible  
    KindCompatibilityEnforced ==
        dirty = TRUE \/
        (current_state = "done" /\ ValidProposedEdge /\ is_valid = TRUE /\ proposed_edge_type = 1 =>
         ~((node_kind[proposed_from] \in {1,2}) /\ (node_kind[proposed_to] = 3)))
    
    \* Happy path: when no issues detected, should be valid
    ValidEdgeAccepted ==
        dirty = TRUE \/
        (current_state = "done" /\ ValidProposedEdge /\ 
         proposed_from \notin reachable /\                    \* no cycle
         proposed_to \notin adjacency[proposed_from] /\       \* no duplicate  
         ~((proposed_edge_type = 1) /\ (node_kind[proposed_from] \in {1,2}) /\ (node_kind[proposed_to] = 3))  \* compatible kinds
         => is_valid = TRUE)

end define;

fair process main = "validator"
begin
    Loop:
        while current_state \notin TerminalStates /\ step_count < MaxSteps do
            either
                \* idle → building_graph: start building with random node kinds
                StartBuilding:
                    if current_state = "idle" then
                        with kf \in [1..NumNodes -> 0..NumKinds-1] do
                            node_kind := kf;
                        end with;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    StartBuildingDone:
                        current_state := "building_graph";
                        op := "start_building";
                        dirty := FALSE;
                    else
                        op := "skip_start";
                    end if;
            or
                \* building_graph → building_graph: add edges (only forward i < j)
                AddEdge:
                    if current_state = "building_graph" /\ edge_count < MaxEdges then
                        with i \in 1..NumNodes, j \in 1..NumNodes do
                            if i < j /\ j \notin adjacency[i] then
                                adjacency := [adjacency EXCEPT ![i] = adjacency[i] \union {j}];
                                edge_count := edge_count + 1;
                                dirty := TRUE;
                                step_count := step_count + 1;
                            else
                                dirty := TRUE;
                            end if;
                        end with;
                    AddEdgeDone:
                        op := "add_edge";
                        dirty := FALSE;
                    else
                        op := "skip_add_edge";
                    end if;
            or
                \* building_graph → proposing_edge: done building
                FinishBuilding:
                    if current_state = "building_graph" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                    FinishBuildingDone:
                        current_state := "proposing_edge";
                        op := "finish_building";
                        dirty := FALSE;
                    else
                        op := "skip_finish_building";
                    end if;
            or
                \* proposing_edge → checking_acyclicity: pick edge to validate
                ProposeEdge:
                    if current_state = "proposing_edge" then
                        with from \in 1..NumNodes, to \in 1..NumNodes, etype \in {0,1} do
                            proposed_from := from;
                            proposed_to := to;
                            proposed_edge_type := etype;
                            is_valid := TRUE;
                            rejection_reason := "";
                            worklist := {to};
                            visited := {};
                            reachable := {};
                        end with;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    ProposeEdgeDone:
                        current_state := "checking_acyclicity";
                        op := "propose_edge";
                        dirty := FALSE;
                    else
                        op := "skip_propose";
                    end if;
            or
                \* checking_acyclicity → checking_acyclicity: BFS step
                BFSStep:
                    if current_state = "checking_acyclicity" /\ worklist # {} then
                        with n \in worklist do
                            visited := visited \union {n};
                            worklist := (worklist \ {n}) \union 
                                       {s \in adjacency[n] : s \notin visited};
                            reachable := reachable \union {n};
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
                \* checking_acyclicity → checking_duplicate: finish BFS, check cycle
                FinishCycleCheck:
                    if current_state = "checking_acyclicity" /\ worklist = {} then
                        if proposed_from \in reachable \/ proposed_from = proposed_to then
                            is_valid := FALSE;
                            rejection_reason := "cycle";
                        else
                            skip;
                        end if;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    FinishCycleCheckDone:
                        current_state := "checking_duplicate";
                        op := "finish_cycle_check";
                        dirty := FALSE;
                    else
                        op := "skip_finish_cycle";
                    end if;
            or
                \* checking_duplicate → checking_kind: check if edge already exists
                CheckDuplicate:
                    if current_state = "checking_duplicate" then
                        if is_valid = TRUE /\ proposed_to \in adjacency[proposed_from] then
                            is_valid := FALSE;
                            rejection_reason := "duplicate";
                        else
                            skip;
                        end if;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    CheckDuplicateDone:
                        current_state := "checking_kind";
                        op := "check_duplicate";
                        dirty := FALSE;
                    else
                        op := "skip_duplicate";
                    end if;
            or
                \* checking_kind → computing_result: check kind compatibility
                CheckKind:
                    if current_state = "checking_kind" then
                        if is_valid = TRUE /\ proposed_edge_type = 1 /\
                           ((node_kind[proposed_from] = 2 /\ node_kind[proposed_to] = 3) \/
                            (node_kind[proposed_from] = 1 /\ node_kind[proposed_to] = 3)) then
                            is_valid := FALSE;
                            rejection_reason := "kind";
                        else
                            skip;
                        end if;
                        dirty := TRUE;
                        step_count := step_count + 1;
                    CheckKindDone:
                        current_state := "computing_result";
                        op := "check_kind";
                        dirty := FALSE;
                    else
                        op := "skip_kind";
                    end if;
            or
                \* computing_result → done: finalize
                ComputeResult:
                    if current_state = "computing_result" then
                        dirty := TRUE;
                        step_count := step_count + 1;
                    ComputeResultDone:
                        current_state := "done";
                        op := "compute_result";
                        result := IF is_valid THEN "valid" ELSE rejection_reason;
                        dirty := FALSE;
                    else
                        op := "skip_compute";
                    end if;
            or
                \* any state → failed: timeout
                Timeout:
                    if step_count >= MaxSteps then
                        dirty := TRUE;
                    TimeoutDone:
                        current_state := "failed";
                        op := "timeout";
                        dirty := FALSE;
                    else
                        op := "skip_timeout";
                    end if;
            end either;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b71d1c6e" /\ chksum(tla) = "6eded1d8")
VARIABLES pc, current_state, adjacency, node_kind, edge_count, proposed_from, 
          proposed_to, proposed_edge_type, is_valid, rejection_reason, 
          reachable, visited, worklist, step_count, op, result, dirty

(* define statement *)
StateSet == {"idle", "building_graph", "proposing_edge", "checking_acyclicity",
             "checking_duplicate", "checking_kind", "computing_result", "done", "failed"}

TerminalStates == {"done", "failed"}



ValidState == current_state \in StateSet

BoundedExecution == step_count <= MaxSteps


ValidProposedEdge == (proposed_from \in 1..NumNodes) /\ (proposed_to \in 1..NumNodes)


AcyclicityPreserved ==
    dirty = TRUE \/
    (current_state = "done" /\ ValidProposedEdge /\ is_valid = TRUE =>
     proposed_from \notin reachable)


DuplicateRejected ==
    dirty = TRUE \/
    (current_state = "done" /\ ValidProposedEdge /\ rejection_reason = "duplicate" =>
     proposed_to \in adjacency[proposed_from])


KindCompatibilityEnforced ==
    dirty = TRUE \/
    (current_state = "done" /\ ValidProposedEdge /\ is_valid = TRUE /\ proposed_edge_type = 1 =>
     ~((node_kind[proposed_from] \in {1,2}) /\ (node_kind[proposed_to] = 3)))


ValidEdgeAccepted ==
    dirty = TRUE \/
    (current_state = "done" /\ ValidProposedEdge /\
     proposed_from \notin reachable /\
     proposed_to \notin adjacency[proposed_from] /\
     ~((proposed_edge_type = 1) /\ (node_kind[proposed_from] \in {1,2}) /\ (node_kind[proposed_to] = 3))
     => is_valid = TRUE)


vars == << pc, current_state, adjacency, node_kind, edge_count, proposed_from, 
           proposed_to, proposed_edge_type, is_valid, rejection_reason, 
           reachable, visited, worklist, step_count, op, result, dirty >>

ProcSet == {"validator"}

Init == (* Global variables *)
        /\ current_state = "idle"
        /\ adjacency = [n \in 1..NumNodes |-> {}]
        /\ node_kind = [n \in 1..NumNodes |-> 0]
        /\ edge_count = 0
        /\ proposed_from = 0
        /\ proposed_to = 0
        /\ proposed_edge_type = 0
        /\ is_valid = TRUE
        /\ rejection_reason = ""
        /\ reachable = {}
        /\ visited = {}
        /\ worklist = {}
        /\ step_count = 0
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["validator"] = "Loop"
        /\ IF current_state \notin TerminalStates /\ step_count < MaxSteps
              THEN /\ \/ /\ pc' = [pc EXCEPT !["validator"] = "StartBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "AddEdge"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "FinishBuilding"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "ProposeEdge"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "BFSStep"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "FinishCycleCheck"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "CheckDuplicate"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "CheckKind"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "ComputeResult"]
                      \/ /\ pc' = [pc EXCEPT !["validator"] = "Timeout"]
              ELSE /\ pc' = [pc EXCEPT !["validator"] = "Done"]
        /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                        proposed_from, proposed_to, proposed_edge_type, 
                        is_valid, rejection_reason, reachable, visited, 
                        worklist, step_count, op, result, dirty >>

StartBuilding == /\ pc["validator"] = "StartBuilding"
                 /\ IF current_state = "idle"
                       THEN /\ \E kf \in [1..NumNodes -> 0..NumKinds-1]:
                                 node_kind' = kf
                            /\ dirty' = TRUE
                            /\ step_count' = step_count + 1
                            /\ pc' = [pc EXCEPT !["validator"] = "StartBuildingDone"]
                            /\ op' = op
                       ELSE /\ op' = "skip_start"
                            /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                            /\ UNCHANGED << node_kind, step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, edge_count, 
                                 proposed_from, proposed_to, 
                                 proposed_edge_type, is_valid, 
                                 rejection_reason, reachable, visited, 
                                 worklist, result >>

StartBuildingDone == /\ pc["validator"] = "StartBuildingDone"
                     /\ current_state' = "building_graph"
                     /\ op' = "start_building"
                     /\ dirty' = FALSE
                     /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                     /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                     proposed_from, proposed_to, 
                                     proposed_edge_type, is_valid, 
                                     rejection_reason, reachable, visited, 
                                     worklist, step_count, result >>

AddEdge == /\ pc["validator"] = "AddEdge"
           /\ IF current_state = "building_graph" /\ edge_count < MaxEdges
                 THEN /\ \E i \in 1..NumNodes:
                           \E j \in 1..NumNodes:
                             IF i < j /\ j \notin adjacency[i]
                                THEN /\ adjacency' = [adjacency EXCEPT ![i] = adjacency[i] \union {j}]
                                     /\ edge_count' = edge_count + 1
                                     /\ dirty' = TRUE
                                     /\ step_count' = step_count + 1
                                ELSE /\ dirty' = TRUE
                                     /\ UNCHANGED << adjacency, edge_count, 
                                                     step_count >>
                      /\ pc' = [pc EXCEPT !["validator"] = "AddEdgeDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_add_edge"
                      /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                      /\ UNCHANGED << adjacency, edge_count, step_count, dirty >>
           /\ UNCHANGED << current_state, node_kind, proposed_from, 
                           proposed_to, proposed_edge_type, is_valid, 
                           rejection_reason, reachable, visited, worklist, 
                           result >>

AddEdgeDone == /\ pc["validator"] = "AddEdgeDone"
               /\ op' = "add_edge"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
               /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                               proposed_from, proposed_to, proposed_edge_type, 
                               is_valid, rejection_reason, reachable, visited, 
                               worklist, step_count, result >>

FinishBuilding == /\ pc["validator"] = "FinishBuilding"
                  /\ IF current_state = "building_graph"
                        THEN /\ dirty' = TRUE
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["validator"] = "FinishBuildingDone"]
                             /\ op' = op
                        ELSE /\ op' = "skip_finish_building"
                             /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                             /\ UNCHANGED << step_count, dirty >>
                  /\ UNCHANGED << current_state, adjacency, node_kind, 
                                  edge_count, proposed_from, proposed_to, 
                                  proposed_edge_type, is_valid, 
                                  rejection_reason, reachable, visited, 
                                  worklist, result >>

FinishBuildingDone == /\ pc["validator"] = "FinishBuildingDone"
                      /\ current_state' = "proposing_edge"
                      /\ op' = "finish_building"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                      /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                      proposed_from, proposed_to, 
                                      proposed_edge_type, is_valid, 
                                      rejection_reason, reachable, visited, 
                                      worklist, step_count, result >>

ProposeEdge == /\ pc["validator"] = "ProposeEdge"
               /\ IF current_state = "proposing_edge"
                     THEN /\ \E from \in 1..NumNodes:
                               \E to \in 1..NumNodes:
                                 \E etype \in {0,1}:
                                   /\ proposed_from' = from
                                   /\ proposed_to' = to
                                   /\ proposed_edge_type' = etype
                                   /\ is_valid' = TRUE
                                   /\ rejection_reason' = ""
                                   /\ worklist' = {to}
                                   /\ visited' = {}
                                   /\ reachable' = {}
                          /\ dirty' = TRUE
                          /\ step_count' = step_count + 1
                          /\ pc' = [pc EXCEPT !["validator"] = "ProposeEdgeDone"]
                          /\ op' = op
                     ELSE /\ op' = "skip_propose"
                          /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                          /\ UNCHANGED << proposed_from, proposed_to, 
                                          proposed_edge_type, is_valid, 
                                          rejection_reason, reachable, visited, 
                                          worklist, step_count, dirty >>
               /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                               result >>

ProposeEdgeDone == /\ pc["validator"] = "ProposeEdgeDone"
                   /\ current_state' = "checking_acyclicity"
                   /\ op' = "propose_edge"
                   /\ dirty' = FALSE
                   /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                   /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                   proposed_from, proposed_to, 
                                   proposed_edge_type, is_valid, 
                                   rejection_reason, reachable, visited, 
                                   worklist, step_count, result >>

BFSStep == /\ pc["validator"] = "BFSStep"
           /\ IF current_state = "checking_acyclicity" /\ worklist # {}
                 THEN /\ \E n \in worklist:
                           /\ visited' = (visited \union {n})
                           /\ worklist' = ( (worklist \ {n}) \union
                                           {s \in adjacency[n] : s \notin visited'})
                           /\ reachable' = (reachable \union {n})
                      /\ step_count' = step_count + 1
                      /\ dirty' = TRUE
                      /\ pc' = [pc EXCEPT !["validator"] = "BFSStepDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_bfs"
                      /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                      /\ UNCHANGED << reachable, visited, worklist, step_count, 
                                      dirty >>
           /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                           proposed_from, proposed_to, proposed_edge_type, 
                           is_valid, rejection_reason, result >>

BFSStepDone == /\ pc["validator"] = "BFSStepDone"
               /\ op' = "bfs_step"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
               /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                               proposed_from, proposed_to, proposed_edge_type, 
                               is_valid, rejection_reason, reachable, visited, 
                               worklist, step_count, result >>

FinishCycleCheck == /\ pc["validator"] = "FinishCycleCheck"
                    /\ IF current_state = "checking_acyclicity" /\ worklist = {}
                          THEN /\ IF proposed_from \in reachable \/ proposed_from = proposed_to
                                     THEN /\ is_valid' = FALSE
                                          /\ rejection_reason' = "cycle"
                                     ELSE /\ TRUE
                                          /\ UNCHANGED << is_valid, 
                                                          rejection_reason >>
                               /\ dirty' = TRUE
                               /\ step_count' = step_count + 1
                               /\ pc' = [pc EXCEPT !["validator"] = "FinishCycleCheckDone"]
                               /\ op' = op
                          ELSE /\ op' = "skip_finish_cycle"
                               /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                               /\ UNCHANGED << is_valid, rejection_reason, 
                                               step_count, dirty >>
                    /\ UNCHANGED << current_state, adjacency, node_kind, 
                                    edge_count, proposed_from, proposed_to, 
                                    proposed_edge_type, reachable, visited, 
                                    worklist, result >>

FinishCycleCheckDone == /\ pc["validator"] = "FinishCycleCheckDone"
                        /\ current_state' = "checking_duplicate"
                        /\ op' = "finish_cycle_check"
                        /\ dirty' = FALSE
                        /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                        /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                        proposed_from, proposed_to, 
                                        proposed_edge_type, is_valid, 
                                        rejection_reason, reachable, visited, 
                                        worklist, step_count, result >>

CheckDuplicate == /\ pc["validator"] = "CheckDuplicate"
                  /\ IF current_state = "checking_duplicate"
                        THEN /\ IF is_valid = TRUE /\ proposed_to \in adjacency[proposed_from]
                                   THEN /\ is_valid' = FALSE
                                        /\ rejection_reason' = "duplicate"
                                   ELSE /\ TRUE
                                        /\ UNCHANGED << is_valid, 
                                                        rejection_reason >>
                             /\ dirty' = TRUE
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["validator"] = "CheckDuplicateDone"]
                             /\ op' = op
                        ELSE /\ op' = "skip_duplicate"
                             /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                             /\ UNCHANGED << is_valid, rejection_reason, 
                                             step_count, dirty >>
                  /\ UNCHANGED << current_state, adjacency, node_kind, 
                                  edge_count, proposed_from, proposed_to, 
                                  proposed_edge_type, reachable, visited, 
                                  worklist, result >>

CheckDuplicateDone == /\ pc["validator"] = "CheckDuplicateDone"
                      /\ current_state' = "checking_kind"
                      /\ op' = "check_duplicate"
                      /\ dirty' = FALSE
                      /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                      /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                      proposed_from, proposed_to, 
                                      proposed_edge_type, is_valid, 
                                      rejection_reason, reachable, visited, 
                                      worklist, step_count, result >>

CheckKind == /\ pc["validator"] = "CheckKind"
             /\ IF current_state = "checking_kind"
                   THEN /\ IF is_valid = TRUE /\ proposed_edge_type = 1 /\
                              ((node_kind[proposed_from] = 2 /\ node_kind[proposed_to] = 3) \/
                               (node_kind[proposed_from] = 1 /\ node_kind[proposed_to] = 3))
                              THEN /\ is_valid' = FALSE
                                   /\ rejection_reason' = "kind"
                              ELSE /\ TRUE
                                   /\ UNCHANGED << is_valid, rejection_reason >>
                        /\ dirty' = TRUE
                        /\ step_count' = step_count + 1
                        /\ pc' = [pc EXCEPT !["validator"] = "CheckKindDone"]
                        /\ op' = op
                   ELSE /\ op' = "skip_kind"
                        /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                        /\ UNCHANGED << is_valid, rejection_reason, step_count, 
                                        dirty >>
             /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                             proposed_from, proposed_to, proposed_edge_type, 
                             reachable, visited, worklist, result >>

CheckKindDone == /\ pc["validator"] = "CheckKindDone"
                 /\ current_state' = "computing_result"
                 /\ op' = "check_kind"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                 /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                 proposed_from, proposed_to, 
                                 proposed_edge_type, is_valid, 
                                 rejection_reason, reachable, visited, 
                                 worklist, step_count, result >>

ComputeResult == /\ pc["validator"] = "ComputeResult"
                 /\ IF current_state = "computing_result"
                       THEN /\ dirty' = TRUE
                            /\ step_count' = step_count + 1
                            /\ pc' = [pc EXCEPT !["validator"] = "ComputeResultDone"]
                            /\ op' = op
                       ELSE /\ op' = "skip_compute"
                            /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                            /\ UNCHANGED << step_count, dirty >>
                 /\ UNCHANGED << current_state, adjacency, node_kind, 
                                 edge_count, proposed_from, proposed_to, 
                                 proposed_edge_type, is_valid, 
                                 rejection_reason, reachable, visited, 
                                 worklist, result >>

ComputeResultDone == /\ pc["validator"] = "ComputeResultDone"
                     /\ current_state' = "done"
                     /\ op' = "compute_result"
                     /\ result' = IF is_valid THEN "valid" ELSE rejection_reason
                     /\ dirty' = FALSE
                     /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                     /\ UNCHANGED << adjacency, node_kind, edge_count, 
                                     proposed_from, proposed_to, 
                                     proposed_edge_type, is_valid, 
                                     rejection_reason, reachable, visited, 
                                     worklist, step_count >>

Timeout == /\ pc["validator"] = "Timeout"
           /\ IF step_count >= MaxSteps
                 THEN /\ dirty' = TRUE
                      /\ pc' = [pc EXCEPT !["validator"] = "TimeoutDone"]
                      /\ op' = op
                 ELSE /\ op' = "skip_timeout"
                      /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
                      /\ dirty' = dirty
           /\ UNCHANGED << current_state, adjacency, node_kind, edge_count, 
                           proposed_from, proposed_to, proposed_edge_type, 
                           is_valid, rejection_reason, reachable, visited, 
                           worklist, step_count, result >>

TimeoutDone == /\ pc["validator"] = "TimeoutDone"
               /\ current_state' = "failed"
               /\ op' = "timeout"
               /\ dirty' = FALSE
               /\ pc' = [pc EXCEPT !["validator"] = "Loop"]
               /\ UNCHANGED << adjacency, node_kind, edge_count, proposed_from, 
                               proposed_to, proposed_edge_type, is_valid, 
                               rejection_reason, reachable, visited, worklist, 
                               step_count, result >>

main == Loop \/ StartBuilding \/ StartBuildingDone \/ AddEdge
           \/ AddEdgeDone \/ FinishBuilding \/ FinishBuildingDone
           \/ ProposeEdge \/ ProposeEdgeDone \/ BFSStep \/ BFSStepDone
           \/ FinishCycleCheck \/ FinishCycleCheckDone \/ CheckDuplicate
           \/ CheckDuplicateDone \/ CheckKind \/ CheckKindDone
           \/ ComputeResult \/ ComputeResultDone \/ Timeout \/ TimeoutDone

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
