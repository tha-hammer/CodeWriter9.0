---- MODULE CrawlOrchestrator ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    DFSLen,
    PendingNodes,
    SemMax

ASSUME /\ DFSLen >= 0 /\ SemMax >= 1

(* --algorithm CrawlOrchestrator

variables
    phase       = "idle",
    dfs_idx     = 1,
    p1_done     = {},
    p2_done     = {},
    semaphore   = SemMax,
    p1_complete = FALSE;

define

    TypeOK ==
        /\ phase \in {"idle", "phase1", "phase2", "complete"}
        /\ dfs_idx \in 1..(DFSLen + 1)
        /\ p1_done \subseteq 1..DFSLen
        /\ p2_done \subseteq PendingNodes
        /\ semaphore \in 0..SemMax

    Phase1BeforePhase2 ==
        (p2_done /= {}) => p1_complete

    Phase1FlagAccurate ==
        p1_complete => (p1_done = 1..DFSLen)

    SemaphoreNonNeg ==
        semaphore >= 0

    ConcurrencyBound ==
        SemMax - semaphore >= 0

    DFSSequentialOrder ==
        \A i \in 1..DFSLen :
            i \in p1_done =>
            (\A j \in 1..(i-1) : j \in p1_done)

    NoPhase2BeforeSignal ==
        ~p1_complete => p2_done = {}

end define;

fair process orchestrator = "orch"
begin
    OStart:
        phase := "phase1";

    P1Loop:
        while dfs_idx <= DFSLen do
            P1Process:
                p1_done := p1_done \cup {dfs_idx};
                dfs_idx := dfs_idx + 1;
        end while;

    P1Signal:
        p1_complete := TRUE;
        phase := "phase2";

    OGather:
        await p2_done = PendingNodes;

    OComplete:
        phase := "complete";

end process;

fair process p2worker \in PendingNodes
begin
    WaitPhase2:
        await p1_complete;

    Acquire:
        await semaphore > 0;
        semaphore := semaphore - 1;

    Process:
        p2_done := p2_done \cup {self};

    Release:
        semaphore := semaphore + 1;

    WFinish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "66d89e9b" /\ chksum(tla) = "ddc12797")
VARIABLES pc, phase, dfs_idx, p1_done, p2_done, semaphore, p1_complete

(* define statement *)
TypeOK ==
    /\ phase \in {"idle", "phase1", "phase2", "complete"}
    /\ dfs_idx \in 1..(DFSLen + 1)
    /\ p1_done \subseteq 1..DFSLen
    /\ p2_done \subseteq PendingNodes
    /\ semaphore \in 0..SemMax

Phase1BeforePhase2 ==
    (p2_done /= {}) => p1_complete

Phase1FlagAccurate ==
    p1_complete => (p1_done = 1..DFSLen)

SemaphoreNonNeg ==
    semaphore >= 0

ConcurrencyBound ==
    SemMax - semaphore >= 0

DFSSequentialOrder ==
    \A i \in 1..DFSLen :
        i \in p1_done =>
        (\A j \in 1..(i-1) : j \in p1_done)

NoPhase2BeforeSignal ==
    ~p1_complete => p2_done = {}


vars == << pc, phase, dfs_idx, p1_done, p2_done, semaphore, p1_complete >>

ProcSet == {"orch"} \cup (PendingNodes)

Init == (* Global variables *)
        /\ phase = "idle"
        /\ dfs_idx = 1
        /\ p1_done = {}
        /\ p2_done = {}
        /\ semaphore = SemMax
        /\ p1_complete = FALSE
        /\ pc = [self \in ProcSet |-> CASE self = "orch" -> "OStart"
                                        [] self \in PendingNodes -> "WaitPhase2"]

OStart == /\ pc["orch"] = "OStart"
          /\ phase' = "phase1"
          /\ pc' = [pc EXCEPT !["orch"] = "P1Loop"]
          /\ UNCHANGED << dfs_idx, p1_done, p2_done, semaphore, p1_complete >>

P1Loop == /\ pc["orch"] = "P1Loop"
          /\ IF dfs_idx <= DFSLen
                THEN /\ pc' = [pc EXCEPT !["orch"] = "P1Process"]
                ELSE /\ pc' = [pc EXCEPT !["orch"] = "P1Signal"]
          /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, semaphore, 
                          p1_complete >>

P1Process == /\ pc["orch"] = "P1Process"
             /\ p1_done' = (p1_done \cup {dfs_idx})
             /\ dfs_idx' = dfs_idx + 1
             /\ pc' = [pc EXCEPT !["orch"] = "P1Loop"]
             /\ UNCHANGED << phase, p2_done, semaphore, p1_complete >>

P1Signal == /\ pc["orch"] = "P1Signal"
            /\ p1_complete' = TRUE
            /\ phase' = "phase2"
            /\ pc' = [pc EXCEPT !["orch"] = "OGather"]
            /\ UNCHANGED << dfs_idx, p1_done, p2_done, semaphore >>

OGather == /\ pc["orch"] = "OGather"
           /\ p2_done = PendingNodes
           /\ pc' = [pc EXCEPT !["orch"] = "OComplete"]
           /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, semaphore, 
                           p1_complete >>

OComplete == /\ pc["orch"] = "OComplete"
             /\ phase' = "complete"
             /\ pc' = [pc EXCEPT !["orch"] = "Done"]
             /\ UNCHANGED << dfs_idx, p1_done, p2_done, semaphore, p1_complete >>

orchestrator == OStart \/ P1Loop \/ P1Process \/ P1Signal \/ OGather
                   \/ OComplete

WaitPhase2(self) == /\ pc[self] = "WaitPhase2"
                    /\ p1_complete
                    /\ pc' = [pc EXCEPT ![self] = "Acquire"]
                    /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, 
                                    semaphore, p1_complete >>

Acquire(self) == /\ pc[self] = "Acquire"
                 /\ semaphore > 0
                 /\ semaphore' = semaphore - 1
                 /\ pc' = [pc EXCEPT ![self] = "Process"]
                 /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, p1_complete >>

Process(self) == /\ pc[self] = "Process"
                 /\ p2_done' = (p2_done \cup {self})
                 /\ pc' = [pc EXCEPT ![self] = "Release"]
                 /\ UNCHANGED << phase, dfs_idx, p1_done, semaphore, 
                                 p1_complete >>

Release(self) == /\ pc[self] = "Release"
                 /\ semaphore' = semaphore + 1
                 /\ pc' = [pc EXCEPT ![self] = "WFinish"]
                 /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, p1_complete >>

WFinish(self) == /\ pc[self] = "WFinish"
                 /\ TRUE
                 /\ pc' = [pc EXCEPT ![self] = "Done"]
                 /\ UNCHANGED << phase, dfs_idx, p1_done, p2_done, semaphore, 
                                 p1_complete >>

p2worker(self) == WaitPhase2(self) \/ Acquire(self) \/ Process(self)
                     \/ Release(self) \/ WFinish(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == orchestrator
           \/ (\E self \in PendingNodes: p2worker(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(orchestrator)
        /\ \A self \in PendingNodes : WF_vars(p2worker(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
