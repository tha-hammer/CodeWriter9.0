---- MODULE CrawlBridgeOrphanCleanup ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    ResourceUUIDNodes,
    ResourceNonUUIDNodes,
    OtherNodes,
    CrawlUUIDs

(* --algorithm CrawlBridgeOrphanCleanup

variables
    dag_resource_uuid    = ResourceUUIDNodes,
    dag_resource_nonuuid = ResourceNonUUIDNodes,
    dag_other            = OtherNodes,
    work_queue           = ResourceUUIDNodes,
    nodes_removed        = 0,
    phase                = "init";

define

    OtherNodesPreserved ==
        dag_other = OtherNodes

    NonUUIDResourceNodesPreserved ==
        dag_resource_nonuuid = ResourceNonUUIDNodes

    DAGResourceUUIDSubset ==
        dag_resource_uuid \subseteq ResourceUUIDNodes

    WorkQueueSubset ==
        work_queue \subseteq ResourceUUIDNodes

    CounterConsistency ==
        nodes_removed = Cardinality(ResourceUUIDNodes) - Cardinality(dag_resource_uuid)

    ProcessedNodesCorrect ==
        \A nid \in ResourceUUIDNodes \ work_queue :
            (nid \in dag_resource_uuid) => (nid \in CrawlUUIDs)

    KeptUUIDNodesAreProtected ==
        \A nid \in dag_resource_uuid :
            nid \in CrawlUUIDs \/ nid \in work_queue

    NoOrphansRemain ==
        phase = "done" =>
            (\A nid \in ResourceUUIDNodes :
                (nid \notin CrawlUUIDs) => (nid \notin dag_resource_uuid))

end define;

fair process cleanup = "orphan_cleanup"
begin
    StartPhase:
        phase := "running";
    ProcessNodes:
        while work_queue # {} do
            with nid \in work_queue do
                work_queue := work_queue \ {nid};
                if nid \notin CrawlUUIDs then
                    dag_resource_uuid := dag_resource_uuid \ {nid};
                    nodes_removed := nodes_removed + 1;
                end if;
            end with;
        end while;
    Finish:
        phase := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f2ba8fda" /\ chksum(tla) = "6d5b25d9")
VARIABLES pc, dag_resource_uuid, dag_resource_nonuuid, dag_other, work_queue, 
          nodes_removed, phase

(* define statement *)
OtherNodesPreserved ==
    dag_other = OtherNodes

NonUUIDResourceNodesPreserved ==
    dag_resource_nonuuid = ResourceNonUUIDNodes

DAGResourceUUIDSubset ==
    dag_resource_uuid \subseteq ResourceUUIDNodes

WorkQueueSubset ==
    work_queue \subseteq ResourceUUIDNodes

CounterConsistency ==
    nodes_removed = Cardinality(ResourceUUIDNodes) - Cardinality(dag_resource_uuid)

ProcessedNodesCorrect ==
    \A nid \in ResourceUUIDNodes \ work_queue :
        (nid \in dag_resource_uuid) => (nid \in CrawlUUIDs)

KeptUUIDNodesAreProtected ==
    \A nid \in dag_resource_uuid :
        nid \in CrawlUUIDs \/ nid \in work_queue

NoOrphansRemain ==
    phase = "done" =>
        (\A nid \in ResourceUUIDNodes :
            (nid \notin CrawlUUIDs) => (nid \notin dag_resource_uuid))


vars == << pc, dag_resource_uuid, dag_resource_nonuuid, dag_other, work_queue, 
           nodes_removed, phase >>

ProcSet == {"orphan_cleanup"}

Init == (* Global variables *)
        /\ dag_resource_uuid = ResourceUUIDNodes
        /\ dag_resource_nonuuid = ResourceNonUUIDNodes
        /\ dag_other = OtherNodes
        /\ work_queue = ResourceUUIDNodes
        /\ nodes_removed = 0
        /\ phase = "init"
        /\ pc = [self \in ProcSet |-> "StartPhase"]

StartPhase == /\ pc["orphan_cleanup"] = "StartPhase"
              /\ phase' = "running"
              /\ pc' = [pc EXCEPT !["orphan_cleanup"] = "ProcessNodes"]
              /\ UNCHANGED << dag_resource_uuid, dag_resource_nonuuid, 
                              dag_other, work_queue, nodes_removed >>

ProcessNodes == /\ pc["orphan_cleanup"] = "ProcessNodes"
                /\ IF work_queue # {}
                      THEN /\ \E nid \in work_queue:
                                /\ work_queue' = work_queue \ {nid}
                                /\ IF nid \notin CrawlUUIDs
                                      THEN /\ dag_resource_uuid' = dag_resource_uuid \ {nid}
                                           /\ nodes_removed' = nodes_removed + 1
                                      ELSE /\ TRUE
                                           /\ UNCHANGED << dag_resource_uuid, 
                                                           nodes_removed >>
                           /\ pc' = [pc EXCEPT !["orphan_cleanup"] = "ProcessNodes"]
                      ELSE /\ pc' = [pc EXCEPT !["orphan_cleanup"] = "Finish"]
                           /\ UNCHANGED << dag_resource_uuid, work_queue, 
                                           nodes_removed >>
                /\ UNCHANGED << dag_resource_nonuuid, dag_other, phase >>

Finish == /\ pc["orphan_cleanup"] = "Finish"
          /\ phase' = "done"
          /\ pc' = [pc EXCEPT !["orphan_cleanup"] = "Done"]
          /\ UNCHANGED << dag_resource_uuid, dag_resource_nonuuid, dag_other, 
                          work_queue, nodes_removed >>

cleanup == StartPhase \/ ProcessNodes \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == cleanup
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(cleanup)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
