--------------------------- MODULE registry_crud ---------------------------
(*
 * Registry CRUD — First instantiation of the CRUD PlusCal template.
 *
 * Models the CodeWriter9.0 registry DAG: a set of nodes (resources) and
 * directed edges (dependencies). Verifies the 4 GWT behaviors:
 *   gwt-0001: closure updates on register
 *   gwt-0002: component detection
 *   gwt-0003: context query returns transitive deps
 *   gwt-0004: cycle rejection
 *
 * Two-phase action model: mutate state, then update derived (closure,
 * components). Invariants hold at the "Loop" label (ready state).
 *)

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    IdSet,
    EdgeTypeSet,
    MaxRecords

(* --algorithm RegistryCRUD

variables
    nodes = {},
    edges = {},
    closure = {},
    components = {},
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    NodeIds == {n.id : n \in nodes}

    RECURSIVE TransitiveClosure(_)
    TransitiveClosure(E) ==
        LET pairs == {<<a, b>> \in E \X E : a.to = b.from}
            composed == {[from |-> p[1].from, to |-> p[2].to] : p \in pairs}
            extended == E \union composed
        IN  IF extended = E THEN E
            ELSE TransitiveClosure(extended)

    ActualClosure == TransitiveClosure({[from |-> e.from, to |-> e.to] : e \in edges})

    Reachable(start) ==
        {pair.to : pair \in {p \in ActualClosure : p.from = start}}

    UndirectedEdges == {[from |-> e.from, to |-> e.to] : e \in edges}
                       \union {[from |-> e.to, to |-> e.from] : e \in edges}

    UndirectedClosure == TransitiveClosure(UndirectedEdges)

    ComponentOf(id) ==
        {id} \union {pair.to : pair \in {p \in UndirectedClosure : p.from = id}}

    ActualComponents ==
        LET RECURSIVE BuildComponents(_, _)
            BuildComponents(remaining, acc) ==
                IF remaining = {} THEN acc
                ELSE LET pick == CHOOSE x \in remaining : TRUE
                         comp == ComponentOf(pick) \intersect remaining
                     IN  BuildComponents(remaining \ comp, acc \union {comp})
        IN  BuildComponents(NodeIds, {})

    \* --- Invariants (hold when dirty = FALSE, i.e., at ready state) ---

    \* gwt-0001: Closure always matches actual transitive reachability
    ClosureCorrect == dirty = TRUE \/ closure = ActualClosure

    \* gwt-0002: Components always form valid partition
    ComponentsValid == dirty = TRUE \/ components = ActualComponents

    \* gwt-0004: No cycles — always holds, even mid-step
    AcyclicGraph == \A id \in NodeIds : id \notin Reachable(id)

    \* Structural integrity — always holds
    ReferentialIntegrity == \A e \in edges : e.from \in NodeIds /\ e.to \in NodeIds
    ValidEdgeTypes == \A e \in edges : e.type \in EdgeTypeSet
    BoundedSize == Cardinality(nodes) <= MaxRecords
    ValidIds == NodeIds \subseteq IdSet

end define;

fair process actor = "main"
begin
    Loop:
        while TRUE do
            either
                \* --- AddNode ---
                AddNode:
                    with nid \in IdSet do
                        if nid \notin NodeIds /\ Cardinality(nodes) < MaxRecords then
                            nodes := nodes \union {[id |-> nid, kind |-> "resource", name |-> "node"]};
                            dirty := TRUE;
                            op := "node_added";
                            result := nid;
                        else
                            op := "add_node_skip";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- AddEdge (with cycle rejection: gwt-0004) ---
                AddEdge:
                    with fid \in IdSet, tid \in IdSet, etype \in EdgeTypeSet do
                        if fid \in NodeIds /\ tid \in NodeIds /\ fid /= tid then
                            if fid \notin Reachable(tid) then
                                edges := edges \union {[from |-> fid, to |-> tid, type |-> etype]};
                                dirty := TRUE;
                                op := "edge_added";
                                result := "ok";
                            else
                                op := "cycle_rejected";
                                result := "error";
                            end if;
                        else
                            op := "edge_invalid";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- RemoveEdge ---
                RemoveEdge:
                    with fid \in IdSet, tid \in IdSet do
                        edges := {e \in edges : ~(e.from = fid /\ e.to = tid)};
                        dirty := TRUE;
                        op := "edge_removed";
                        result := "ok";
                    end with;
            or
                \* --- QueryContext (gwt-0003) ---
                QueryCtx:
                    with qid \in IdSet do
                        if qid \in NodeIds then
                            result := {qid} \union Reachable(qid) \union ComponentOf(qid);
                            op := "queried";
                        else
                            op := "query_not_found";
                            result := "error";
                        end if;
                    end with;
            end either;
            \* Phase 2: update derived state (gwt-0001, gwt-0002)
            UpdateDerived:
                closure := ActualClosure;
                components := ActualComponents;
                dirty := FALSE;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "ed39f5dc" /\ chksum(tla) = "78993240")
VARIABLES pc, nodes, edges, closure, components, op, result, dirty

(* define statement *)
NodeIds == {n.id : n \in nodes}

RECURSIVE TransitiveClosure(_)
TransitiveClosure(E) ==
    LET pairs == {<<a, b>> \in E \X E : a.to = b.from}
        composed == {[from |-> p[1].from, to |-> p[2].to] : p \in pairs}
        extended == E \union composed
    IN  IF extended = E THEN E
        ELSE TransitiveClosure(extended)

ActualClosure == TransitiveClosure({[from |-> e.from, to |-> e.to] : e \in edges})

Reachable(start) ==
    {pair.to : pair \in {p \in ActualClosure : p.from = start}}

UndirectedEdges == {[from |-> e.from, to |-> e.to] : e \in edges}
                   \union {[from |-> e.to, to |-> e.from] : e \in edges}

UndirectedClosure == TransitiveClosure(UndirectedEdges)

ComponentOf(id) ==
    {id} \union {pair.to : pair \in {p \in UndirectedClosure : p.from = id}}

ActualComponents ==
    LET RECURSIVE BuildComponents(_, _)
        BuildComponents(remaining, acc) ==
            IF remaining = {} THEN acc
            ELSE LET pick == CHOOSE x \in remaining : TRUE
                     comp == ComponentOf(pick) \intersect remaining
                 IN  BuildComponents(remaining \ comp, acc \union {comp})
    IN  BuildComponents(NodeIds, {})




ClosureCorrect == dirty = TRUE \/ closure = ActualClosure


ComponentsValid == dirty = TRUE \/ components = ActualComponents


AcyclicGraph == \A id \in NodeIds : id \notin Reachable(id)


ReferentialIntegrity == \A e \in edges : e.from \in NodeIds /\ e.to \in NodeIds
ValidEdgeTypes == \A e \in edges : e.type \in EdgeTypeSet
BoundedSize == Cardinality(nodes) <= MaxRecords
ValidIds == NodeIds \subseteq IdSet


vars == << pc, nodes, edges, closure, components, op, result, dirty >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ nodes = {}
        /\ edges = {}
        /\ closure = {}
        /\ components = {}
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["main"] = "Loop"
        /\ \/ /\ pc' = [pc EXCEPT !["main"] = "AddNode"]
           \/ /\ pc' = [pc EXCEPT !["main"] = "AddEdge"]
           \/ /\ pc' = [pc EXCEPT !["main"] = "RemoveEdge"]
           \/ /\ pc' = [pc EXCEPT !["main"] = "QueryCtx"]
        /\ UNCHANGED << nodes, edges, closure, components, op, result, dirty >>

UpdateDerived == /\ pc["main"] = "UpdateDerived"
                 /\ closure' = ActualClosure
                 /\ components' = ActualComponents
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << nodes, edges, op, result >>

AddNode == /\ pc["main"] = "AddNode"
           /\ \E nid \in IdSet:
                IF nid \notin NodeIds /\ Cardinality(nodes) < MaxRecords
                   THEN /\ nodes' = (nodes \union {[id |-> nid, kind |-> "resource", name |-> "node"]})
                        /\ dirty' = TRUE
                        /\ op' = "node_added"
                        /\ result' = nid
                   ELSE /\ op' = "add_node_skip"
                        /\ result' = "error"
                        /\ UNCHANGED << nodes, dirty >>
           /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
           /\ UNCHANGED << edges, closure, components >>

AddEdge == /\ pc["main"] = "AddEdge"
           /\ \E fid \in IdSet:
                \E tid \in IdSet:
                  \E etype \in EdgeTypeSet:
                    IF fid \in NodeIds /\ tid \in NodeIds /\ fid /= tid
                       THEN /\ IF fid \notin Reachable(tid)
                                  THEN /\ edges' = (edges \union {[from |-> fid, to |-> tid, type |-> etype]})
                                       /\ dirty' = TRUE
                                       /\ op' = "edge_added"
                                       /\ result' = "ok"
                                  ELSE /\ op' = "cycle_rejected"
                                       /\ result' = "error"
                                       /\ UNCHANGED << edges, dirty >>
                       ELSE /\ op' = "edge_invalid"
                            /\ result' = "error"
                            /\ UNCHANGED << edges, dirty >>
           /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
           /\ UNCHANGED << nodes, closure, components >>

RemoveEdge == /\ pc["main"] = "RemoveEdge"
              /\ \E fid \in IdSet:
                   \E tid \in IdSet:
                     /\ edges' = {e \in edges : ~(e.from = fid /\ e.to = tid)}
                     /\ dirty' = TRUE
                     /\ op' = "edge_removed"
                     /\ result' = "ok"
              /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
              /\ UNCHANGED << nodes, closure, components >>

QueryCtx == /\ pc["main"] = "QueryCtx"
            /\ \E qid \in IdSet:
                 IF qid \in NodeIds
                    THEN /\ result' = ({qid} \union Reachable(qid) \union ComponentOf(qid))
                         /\ op' = "queried"
                    ELSE /\ op' = "query_not_found"
                         /\ result' = "error"
            /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
            /\ UNCHANGED << nodes, edges, closure, components, dirty >>

actor == Loop \/ UpdateDerived \/ AddNode \/ AddEdge \/ RemoveEdge
            \/ QueryCtx

Next == actor

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(actor)

\* END TRANSLATION 

===========================================================================
