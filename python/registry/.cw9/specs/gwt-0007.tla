-------------------------- MODULE GWT0007Isolation --------------------------

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    GwtIds

ASSUME Cardinality(GwtIds) >= 2

(* --algorithm GWT0007Isolation

variables
    sdk_clients  = [g \in GwtIds |-> 0],
    dag_copies   = [g \in GwtIds |-> 0],
    crawl_conns  = [g \in GwtIds |-> 0],
    next_id      = 1,
    worker_state = [g \in GwtIds |-> "INIT"];

define

    WorkerStates == {"INIT", "CLIENT_READY", "DAG_LOADED", "CRAWL_READY", "FINISHED"}

    AllStatesValid ==
        \A g \in GwtIds : worker_state[g] \in WorkerStates

    NoSharedSDKClient ==
        \A g1, g2 \in GwtIds :
            (g1 # g2 /\ sdk_clients[g1] # 0 /\ sdk_clients[g2] # 0)
            => sdk_clients[g1] # sdk_clients[g2]

    NoSharedDAG ==
        \A g1, g2 \in GwtIds :
            (g1 # g2 /\ dag_copies[g1] # 0 /\ dag_copies[g2] # 0)
            => dag_copies[g1] # dag_copies[g2]

    NoSharedCrawlStore ==
        \A g1, g2 \in GwtIds :
            (g1 # g2 /\ crawl_conns[g1] # 0 /\ crawl_conns[g2] # 0)
            => crawl_conns[g1] # crawl_conns[g2]

    ResourceIdsMonotonicallyGrow ==
        next_id >= 1

    AllocatedClientIds == {sdk_clients[g] : g \in GwtIds} \ {0}
    AllocatedDagIds    == {dag_copies[g]  : g \in GwtIds} \ {0}
    AllocatedConnIds   == {crawl_conns[g] : g \in GwtIds} \ {0}

    ClientCountConsistent ==
        Cardinality(AllocatedClientIds) =
            Cardinality({g \in GwtIds : sdk_clients[g] # 0})

    DagCountConsistent ==
        Cardinality(AllocatedDagIds) =
            Cardinality({g \in GwtIds : dag_copies[g] # 0})

    ConnCountConsistent ==
        Cardinality(AllocatedConnIds) =
            Cardinality({g \in GwtIds : crawl_conns[g] # 0})

    IsolationInvariant ==
        NoSharedSDKClient /\ NoSharedDAG /\ NoSharedCrawlStore

end define;

fair process worker \in GwtIds
begin
    MakeClient:
        sdk_clients[self] := next_id;
        next_id           := next_id + 1;
        worker_state[self] := "CLIENT_READY";

    LoadDag:
        dag_copies[self] := next_id;
        next_id          := next_id + 1;
        worker_state[self] := "DAG_LOADED";

    InitCrawlStore:
        crawl_conns[self] := next_id;
        next_id           := next_id + 1;
        worker_state[self] := "CRAWL_READY";

    RunLoop:
        worker_state[self] := "FINISHED";

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8dba8949" /\ chksum(tla) = "ea2bbc4f")
VARIABLES pc, sdk_clients, dag_copies, crawl_conns, next_id, worker_state

(* define statement *)
WorkerStates == {"INIT", "CLIENT_READY", "DAG_LOADED", "CRAWL_READY", "FINISHED"}

AllStatesValid ==
    \A g \in GwtIds : worker_state[g] \in WorkerStates

NoSharedSDKClient ==
    \A g1, g2 \in GwtIds :
        (g1 # g2 /\ sdk_clients[g1] # 0 /\ sdk_clients[g2] # 0)
        => sdk_clients[g1] # sdk_clients[g2]

NoSharedDAG ==
    \A g1, g2 \in GwtIds :
        (g1 # g2 /\ dag_copies[g1] # 0 /\ dag_copies[g2] # 0)
        => dag_copies[g1] # dag_copies[g2]

NoSharedCrawlStore ==
    \A g1, g2 \in GwtIds :
        (g1 # g2 /\ crawl_conns[g1] # 0 /\ crawl_conns[g2] # 0)
        => crawl_conns[g1] # crawl_conns[g2]

ResourceIdsMonotonicallyGrow ==
    next_id >= 1

AllocatedClientIds == {sdk_clients[g] : g \in GwtIds} \ {0}
AllocatedDagIds    == {dag_copies[g]  : g \in GwtIds} \ {0}
AllocatedConnIds   == {crawl_conns[g] : g \in GwtIds} \ {0}

ClientCountConsistent ==
    Cardinality(AllocatedClientIds) =
        Cardinality({g \in GwtIds : sdk_clients[g] # 0})

DagCountConsistent ==
    Cardinality(AllocatedDagIds) =
        Cardinality({g \in GwtIds : dag_copies[g] # 0})

ConnCountConsistent ==
    Cardinality(AllocatedConnIds) =
        Cardinality({g \in GwtIds : crawl_conns[g] # 0})

IsolationInvariant ==
    NoSharedSDKClient /\ NoSharedDAG /\ NoSharedCrawlStore


vars == << pc, sdk_clients, dag_copies, crawl_conns, next_id, worker_state >>

ProcSet == (GwtIds)

Init == (* Global variables *)
        /\ sdk_clients = [g \in GwtIds |-> 0]
        /\ dag_copies = [g \in GwtIds |-> 0]
        /\ crawl_conns = [g \in GwtIds |-> 0]
        /\ next_id = 1
        /\ worker_state = [g \in GwtIds |-> "INIT"]
        /\ pc = [self \in ProcSet |-> "MakeClient"]

MakeClient(self) == /\ pc[self] = "MakeClient"
                    /\ sdk_clients' = [sdk_clients EXCEPT ![self] = next_id]
                    /\ next_id' = next_id + 1
                    /\ worker_state' = [worker_state EXCEPT ![self] = "CLIENT_READY"]
                    /\ pc' = [pc EXCEPT ![self] = "LoadDag"]
                    /\ UNCHANGED << dag_copies, crawl_conns >>

LoadDag(self) == /\ pc[self] = "LoadDag"
                 /\ dag_copies' = [dag_copies EXCEPT ![self] = next_id]
                 /\ next_id' = next_id + 1
                 /\ worker_state' = [worker_state EXCEPT ![self] = "DAG_LOADED"]
                 /\ pc' = [pc EXCEPT ![self] = "InitCrawlStore"]
                 /\ UNCHANGED << sdk_clients, crawl_conns >>

InitCrawlStore(self) == /\ pc[self] = "InitCrawlStore"
                        /\ crawl_conns' = [crawl_conns EXCEPT ![self] = next_id]
                        /\ next_id' = next_id + 1
                        /\ worker_state' = [worker_state EXCEPT ![self] = "CRAWL_READY"]
                        /\ pc' = [pc EXCEPT ![self] = "RunLoop"]
                        /\ UNCHANGED << sdk_clients, dag_copies >>

RunLoop(self) == /\ pc[self] = "RunLoop"
                 /\ worker_state' = [worker_state EXCEPT ![self] = "FINISHED"]
                 /\ pc' = [pc EXCEPT ![self] = "Terminate"]
                 /\ UNCHANGED << sdk_clients, dag_copies, crawl_conns, next_id >>

Terminate(self) == /\ pc[self] = "Terminate"
                   /\ TRUE
                   /\ pc' = [pc EXCEPT ![self] = "Done"]
                   /\ UNCHANGED << sdk_clients, dag_copies, crawl_conns, 
                                   next_id, worker_state >>

worker(self) == MakeClient(self) \/ LoadDag(self) \/ InitCrawlStore(self)
                   \/ RunLoop(self) \/ Terminate(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in GwtIds: worker(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in GwtIds : WF_vars(worker(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM IsolationInvariant
THEOREM ClientCountConsistent
THEOREM DagCountConsistent
THEOREM ConnCountConsistent
THEOREM AllStatesValid
THEOREM ResourceIdsMonotonicallyGrow

=============================================================================
