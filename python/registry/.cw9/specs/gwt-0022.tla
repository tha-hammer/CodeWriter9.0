---- MODULE GWTPipelineDAG ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    N_GWTS,
    N_VERIFIED,
    MaxSteps

ASSUME N_GWTS >= 1
ASSUME N_VERIFIED >= 0 /\ N_VERIFIED <= N_GWTS
ASSUME MaxSteps >= 1

EXTRACT  == "extract"
REGISTER == "register"
LOOP_T   == "loop"
BRIDGE_T == "bridge"
GENTESTS == "gen_tests"

PENDING   == "pending"
COMPLETED == "completed"

GwtIds      == 1..N_GWTS
VerifiedIds == 1..N_VERIFIED

ExtractJob   == {[type |-> EXTRACT]}
RegisterJob  == {[type |-> REGISTER]}
LoopJobs     == {[type |-> LOOP_T,   gwt |-> g] : g \in GwtIds}
BridgeJobs   == {[type |-> BRIDGE_T, gwt |-> g] : g \in VerifiedIds}
GenTestsJobs == {[type |-> GENTESTS, gwt |-> g] : g \in VerifiedIds}

AllJobs ==
    ExtractJob \union RegisterJob \union LoopJobs \union BridgeJobs \union GenTestsJobs

(* --algorithm GWTPipelineDAG

variables
    job_status    = [j \in AllJobs |-> PENDING],
    dag_persisted = FALSE,
    api_triggered = FALSE,
    step_count    = 0;

define

    JobDependencies(j) ==
        IF      j.type = EXTRACT  THEN {}
        ELSE IF j.type = REGISTER THEN ExtractJob
        ELSE IF j.type = LOOP_T   THEN RegisterJob
        ELSE IF j.type = BRIDGE_T THEN {[type |-> LOOP_T,   gwt |-> j.gwt]}
        ELSE                           {[type |-> BRIDGE_T, gwt |-> j.gwt]}

    DepsCompleted(j) ==
        \A dep \in JobDependencies(j) : job_status[dep] = COMPLETED

    ReadyJobs ==
        {j \in AllJobs : job_status[j] = PENDING /\ DepsCompleted(j)}

    OrderingInvariant ==
        \A j \in AllJobs :
            job_status[j] = COMPLETED =>
            \A dep \in JobDependencies(j) : job_status[dep] = COMPLETED

    DAGPersistedFirst ==
        \A j \in AllJobs : job_status[j] = COMPLETED => dag_persisted

    APITriggeredFirst ==
        dag_persisted => api_triggered

    LoopJobsIndependent ==
        \A g1, g2 \in GwtIds :
            g1 # g2 =>
            [type |-> LOOP_T, gwt |-> g1] \notin JobDependencies([type |-> LOOP_T, gwt |-> g2])

    ExtractBeforeRegister ==
        job_status[[type |-> REGISTER]] = COMPLETED =>
        job_status[[type |-> EXTRACT]]  = COMPLETED

    RegisterBeforeAllLoop ==
        \A g \in GwtIds :
            job_status[[type |-> LOOP_T, gwt |-> g]] = COMPLETED =>
            job_status[[type |-> REGISTER]] = COMPLETED

    LoopBeforeBridge ==
        \A g \in VerifiedIds :
            job_status[[type |-> BRIDGE_T, gwt |-> g]] = COMPLETED =>
            job_status[[type |-> LOOP_T,   gwt |-> g]] = COMPLETED

    BridgeBeforeGenTests ==
        \A g \in VerifiedIds :
            job_status[[type |-> GENTESTS, gwt |-> g]] = COMPLETED =>
            job_status[[type |-> BRIDGE_T, gwt |-> g]] = COMPLETED

    BoundedExecution == step_count <= MaxSteps

end define;

fair process UserAPI = "user"
begin
    SubmitRequest:
        api_triggered := TRUE;
end process;

fair process ControlPlane = "cp"
begin
    BuildDAG:
        await api_triggered;
        dag_persisted := TRUE;
end process;

fair process Scheduler = "sched"
begin
    WaitForDAG:
        await dag_persisted;
    ScheduleStep:
        while (\E j \in AllJobs : job_status[j] = PENDING) /\ step_count < MaxSteps do
            with j \in ReadyJobs do
                job_status[j] := COMPLETED;
            end with;
            step_count := step_count + 1;
        end while;
    Terminate:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "daba3909" /\ chksum(tla) = "221bb394")
VARIABLES pc, job_status, dag_persisted, api_triggered, step_count

(* define statement *)
JobDependencies(j) ==
    IF      j.type = EXTRACT  THEN {}
    ELSE IF j.type = REGISTER THEN ExtractJob
    ELSE IF j.type = LOOP_T   THEN RegisterJob
    ELSE IF j.type = BRIDGE_T THEN {[type |-> LOOP_T,   gwt |-> j.gwt]}
    ELSE                           {[type |-> BRIDGE_T, gwt |-> j.gwt]}

DepsCompleted(j) ==
    \A dep \in JobDependencies(j) : job_status[dep] = COMPLETED

ReadyJobs ==
    {j \in AllJobs : job_status[j] = PENDING /\ DepsCompleted(j)}

OrderingInvariant ==
    \A j \in AllJobs :
        job_status[j] = COMPLETED =>
        \A dep \in JobDependencies(j) : job_status[dep] = COMPLETED

DAGPersistedFirst ==
    \A j \in AllJobs : job_status[j] = COMPLETED => dag_persisted

APITriggeredFirst ==
    dag_persisted => api_triggered

LoopJobsIndependent ==
    \A g1, g2 \in GwtIds :
        g1 # g2 =>
        [type |-> LOOP_T, gwt |-> g1] \notin JobDependencies([type |-> LOOP_T, gwt |-> g2])

ExtractBeforeRegister ==
    job_status[[type |-> REGISTER]] = COMPLETED =>
    job_status[[type |-> EXTRACT]]  = COMPLETED

RegisterBeforeAllLoop ==
    \A g \in GwtIds :
        job_status[[type |-> LOOP_T, gwt |-> g]] = COMPLETED =>
        job_status[[type |-> REGISTER]] = COMPLETED

LoopBeforeBridge ==
    \A g \in VerifiedIds :
        job_status[[type |-> BRIDGE_T, gwt |-> g]] = COMPLETED =>
        job_status[[type |-> LOOP_T,   gwt |-> g]] = COMPLETED

BridgeBeforeGenTests ==
    \A g \in VerifiedIds :
        job_status[[type |-> GENTESTS, gwt |-> g]] = COMPLETED =>
        job_status[[type |-> BRIDGE_T, gwt |-> g]] = COMPLETED

BoundedExecution == step_count <= MaxSteps


vars == << pc, job_status, dag_persisted, api_triggered, step_count >>

ProcSet == {"user"} \cup {"cp"} \cup {"sched"}

Init == (* Global variables *)
        /\ job_status = [j \in AllJobs |-> PENDING]
        /\ dag_persisted = FALSE
        /\ api_triggered = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> CASE self = "user" -> "SubmitRequest"
                                        [] self = "cp" -> "BuildDAG"
                                        [] self = "sched" -> "WaitForDAG"]

SubmitRequest == /\ pc["user"] = "SubmitRequest"
                 /\ api_triggered' = TRUE
                 /\ pc' = [pc EXCEPT !["user"] = "Done"]
                 /\ UNCHANGED << job_status, dag_persisted, step_count >>

UserAPI == SubmitRequest

BuildDAG == /\ pc["cp"] = "BuildDAG"
            /\ api_triggered
            /\ dag_persisted' = TRUE
            /\ pc' = [pc EXCEPT !["cp"] = "Done"]
            /\ UNCHANGED << job_status, api_triggered, step_count >>

ControlPlane == BuildDAG

WaitForDAG == /\ pc["sched"] = "WaitForDAG"
              /\ dag_persisted
              /\ pc' = [pc EXCEPT !["sched"] = "ScheduleStep"]
              /\ UNCHANGED << job_status, dag_persisted, api_triggered, 
                              step_count >>

ScheduleStep == /\ pc["sched"] = "ScheduleStep"
                /\ IF (\E j \in AllJobs : job_status[j] = PENDING) /\ step_count < MaxSteps
                      THEN /\ \E j \in ReadyJobs:
                                job_status' = [job_status EXCEPT ![j] = COMPLETED]
                           /\ step_count' = step_count + 1
                           /\ pc' = [pc EXCEPT !["sched"] = "ScheduleStep"]
                      ELSE /\ pc' = [pc EXCEPT !["sched"] = "Terminate"]
                           /\ UNCHANGED << job_status, step_count >>
                /\ UNCHANGED << dag_persisted, api_triggered >>

Terminate == /\ pc["sched"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["sched"] = "Done"]
             /\ UNCHANGED << job_status, dag_persisted, api_triggered, 
                             step_count >>

Scheduler == WaitForDAG \/ ScheduleStep \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == UserAPI \/ ControlPlane \/ Scheduler
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(UserAPI)
        /\ WF_vars(ControlPlane)
        /\ WF_vars(Scheduler)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

AllCompleted == \A j \in AllJobs : job_status[j] = COMPLETED

Liveness == <>AllCompleted

====
