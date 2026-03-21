---- MODULE CrawlBridgeResourceNodes ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Uuids

(* --algorithm CrawlBridgeResourceNodes

variables
    dag_nodes   = [u \in {} |-> ""],
    nodes_added = 0,
    remaining   = Uuids;

define

    RESOURCE == "RESOURCE"

    TypeOK ==
        /\ nodes_added >= 0
        /\ \A u \in DOMAIN dag_nodes : dag_nodes[u] = RESOURCE

    OnlyResourceKinds ==
        \A u \in DOMAIN dag_nodes : dag_nodes[u] = RESOURCE

    NodesAddedMatchesDomainSize ==
        nodes_added = Cardinality(DOMAIN dag_nodes)

    UUIDDomainSubsetOfInput ==
        DOMAIN dag_nodes \subseteq Uuids

    ProcessedNodesAreResource ==
        \A u \in Uuids \ remaining :
            /\ u \in DOMAIN dag_nodes
            /\ dag_nodes[u] = RESOURCE

    TerminalCorrectness ==
        remaining = {} =>
            /\ nodes_added = Cardinality(Uuids)
            /\ DOMAIN dag_nodes = Uuids
            /\ \A u \in Uuids : dag_nodes[u] = RESOURCE
            /\ Cardinality(DOMAIN dag_nodes) = Cardinality(Uuids)

end define;

fair process bridge = "bridge"
begin
    ProcessRecords:
        while remaining /= {} do
            with uuid \in remaining do
                dag_nodes   := dag_nodes @@ (uuid :> RESOURCE);
                nodes_added := nodes_added + 1;
                remaining   := remaining \ {uuid};
            end with;
        end while;
    Finish:
        assert nodes_added = Cardinality(Uuids);
        assert DOMAIN dag_nodes = Uuids;
        assert \A u \in Uuids : dag_nodes[u] = RESOURCE;
        assert Cardinality(DOMAIN dag_nodes) = Cardinality(Uuids);
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "73fe425c" /\ chksum(tla) = "4bb9de4f")
VARIABLES pc, dag_nodes, nodes_added, remaining

(* define statement *)
RESOURCE == "RESOURCE"

TypeOK ==
    /\ nodes_added >= 0
    /\ \A u \in DOMAIN dag_nodes : dag_nodes[u] = RESOURCE

OnlyResourceKinds ==
    \A u \in DOMAIN dag_nodes : dag_nodes[u] = RESOURCE

NodesAddedMatchesDomainSize ==
    nodes_added = Cardinality(DOMAIN dag_nodes)

UUIDDomainSubsetOfInput ==
    DOMAIN dag_nodes \subseteq Uuids

ProcessedNodesAreResource ==
    \A u \in Uuids \ remaining :
        /\ u \in DOMAIN dag_nodes
        /\ dag_nodes[u] = RESOURCE

TerminalCorrectness ==
    remaining = {} =>
        /\ nodes_added = Cardinality(Uuids)
        /\ DOMAIN dag_nodes = Uuids
        /\ \A u \in Uuids : dag_nodes[u] = RESOURCE
        /\ Cardinality(DOMAIN dag_nodes) = Cardinality(Uuids)


vars == << pc, dag_nodes, nodes_added, remaining >>

ProcSet == {"bridge"}

Init == (* Global variables *)
        /\ dag_nodes = [u \in {} |-> ""]
        /\ nodes_added = 0
        /\ remaining = Uuids
        /\ pc = [self \in ProcSet |-> "ProcessRecords"]

ProcessRecords == /\ pc["bridge"] = "ProcessRecords"
                  /\ IF remaining /= {}
                        THEN /\ \E uuid \in remaining:
                                  /\ dag_nodes' = dag_nodes @@ (uuid :> RESOURCE)
                                  /\ nodes_added' = nodes_added + 1
                                  /\ remaining' = remaining \ {uuid}
                             /\ pc' = [pc EXCEPT !["bridge"] = "ProcessRecords"]
                        ELSE /\ pc' = [pc EXCEPT !["bridge"] = "Finish"]
                             /\ UNCHANGED << dag_nodes, nodes_added, remaining >>

Finish == /\ pc["bridge"] = "Finish"
          /\ Assert(nodes_added = Cardinality(Uuids), 
                    "Failure of assertion at line 57, column 9.")
          /\ Assert(DOMAIN dag_nodes = Uuids, 
                    "Failure of assertion at line 58, column 9.")
          /\ Assert(\A u \in Uuids : dag_nodes[u] = RESOURCE, 
                    "Failure of assertion at line 59, column 9.")
          /\ Assert(Cardinality(DOMAIN dag_nodes) = Cardinality(Uuids), 
                    "Failure of assertion at line 60, column 9.")
          /\ pc' = [pc EXCEPT !["bridge"] = "Done"]
          /\ UNCHANGED << dag_nodes, nodes_added, remaining >>

bridge == ProcessRecords \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == bridge
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(bridge)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

TypeOKInv                == TypeOK
OnlyResourceKindsInv     == OnlyResourceKinds
CountMatchesDomainInv    == NodesAddedMatchesDomainSize
UUIDDomainSubsetInv      == UUIDDomainSubsetOfInput
ProcessedNodesResourceInv == ProcessedNodesAreResource
TerminalCorrectnessInv   == TerminalCorrectness

====
