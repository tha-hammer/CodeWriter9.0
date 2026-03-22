---- MODULE ForwardSubgraphComplete ----

EXTENDS Integers, FiniteSets, TLC

NA == "A"
NB == "B"
NC == "C"
AllNodes == {NA, NB, NC}
StartNode == NA
MaxSteps  == 4

Succs(n) ==
    IF      n = NA THEN {NB}
    ELSE IF n = NB THEN {NC}
    ELSE {}

RECURSIVE Reach(_, _)
Reach(S, boundary) ==
    IF boundary = {} THEN S
    ELSE
        LET next == ( UNION { Succs(n) : n \in boundary } ) \ S
        IN Reach(S \cup next, next)

Reachable == Reach({StartNode}, {StartNode})

(* --algorithm ForwardSubgraphComplete

variables
    visited  = {},
    frontier = {},
    phase    = "init",
    depth    = 0;

define

    SeedAlwaysIncluded ==
        phase /= "init" => StartNode \in visited

    ChainFullyCovered ==
        phase = "complete" =>
            /\ NA \in visited
            /\ NB \in visited
            /\ NC \in visited

    CompletenessInvariant ==
        phase = "complete" => Reachable \subseteq visited

    FrontierSubsetVisited ==
        frontier \subseteq visited

    BoundedDepth ==
        depth <= MaxSteps

    ValidPhase ==
        phase \in {"init", "expanding", "complete", "partial"}

end define;

fair process traversal = "traversal"
begin
    Seed:
        visited  := {StartNode};
        frontier := {StartNode};
        phase    := "expanding";
        depth    := 0;

    Expand:
        while frontier /= {} /\ depth < MaxSteps do
            with node \in frontier do
                with newCallees = Succs(node) \ visited do
                    visited  := visited \cup newCallees;
                    frontier := (frontier \ {node}) \cup newCallees;
                    depth    := depth + 1;
                end with;
            end with;
        end while;

    Terminate:
        if frontier = {} then
            phase := "complete";
        else
            phase := "partial";
        end if;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "9078d6b2" /\ chksum(tla) = "9e2ad891")
VARIABLES pc, visited, frontier, phase, depth

(* define statement *)
SeedAlwaysIncluded ==
    phase /= "init" => StartNode \in visited

ChainFullyCovered ==
    phase = "complete" =>
        /\ NA \in visited
        /\ NB \in visited
        /\ NC \in visited

CompletenessInvariant ==
    phase = "complete" => Reachable \subseteq visited

FrontierSubsetVisited ==
    frontier \subseteq visited

BoundedDepth ==
    depth <= MaxSteps

ValidPhase ==
    phase \in {"init", "expanding", "complete", "partial"}


vars == << pc, visited, frontier, phase, depth >>

ProcSet == {"traversal"}

Init == (* Global variables *)
        /\ visited = {}
        /\ frontier = {}
        /\ phase = "init"
        /\ depth = 0
        /\ pc = [self \in ProcSet |-> "Seed"]

Seed == /\ pc["traversal"] = "Seed"
        /\ visited' = {StartNode}
        /\ frontier' = {StartNode}
        /\ phase' = "expanding"
        /\ depth' = 0
        /\ pc' = [pc EXCEPT !["traversal"] = "Expand"]

Expand == /\ pc["traversal"] = "Expand"
          /\ IF frontier /= {} /\ depth < MaxSteps
                THEN /\ \E node \in frontier:
                          LET newCallees == Succs(node) \ visited IN
                            /\ visited' = (visited \cup newCallees)
                            /\ frontier' = ((frontier \ {node}) \cup newCallees)
                            /\ depth' = depth + 1
                     /\ pc' = [pc EXCEPT !["traversal"] = "Expand"]
                ELSE /\ pc' = [pc EXCEPT !["traversal"] = "Terminate"]
                     /\ UNCHANGED << visited, frontier, depth >>
          /\ phase' = phase

Terminate == /\ pc["traversal"] = "Terminate"
             /\ IF frontier = {}
                   THEN /\ phase' = "complete"
                   ELSE /\ phase' = "partial"
             /\ pc' = [pc EXCEPT !["traversal"] = "Done"]
             /\ UNCHANGED << visited, frontier, depth >>

traversal == Seed \/ Expand \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == traversal
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(traversal)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
