---- MODULE RegistryDagHostedPersistence ----
EXTENDS Integers, Sequences, TLC

CONSTANTS MaxSteps

(* --algorithm RegistryDagHostedPersistence

variables
    context \in {"local", "hosted"},
    dag_state         = "uninitialized",
    backend_used      = "none",
    persist_op        = "idle",
    last_in_memory_op = "none",
    step_count        = 0,
    load_completed    = FALSE,
    save_completed    = FALSE;

define

    ExpectedBackend(ctx) ==
        IF ctx = "hosted" THEN "postgres" ELSE "file"

    TypeOK ==
        /\ context \in {"local", "hosted"}
        /\ dag_state \in {"uninitialized", "ready", "failed"}
        /\ backend_used \in {"none", "file", "postgres"}
        /\ persist_op \in {"idle", "loading", "saving"}
        /\ last_in_memory_op \in
               {"none", "add_node", "add_edge", "query_relevant",
                "register_gwt", "register_requirement",
                "merge_registered_nodes"}
        /\ step_count \in 0..MaxSteps
        /\ load_completed \in BOOLEAN
        /\ save_completed \in BOOLEAN

    BackendMatchesContext ==
        (load_completed \/ save_completed) =>
            backend_used = ExpectedBackend(context)

    HostedLoadUsesPostgres ==
        (context = "hosted" /\ load_completed) => backend_used = "postgres"

    HostedSaveUsesPostgres ==
        (context = "hosted" /\ save_completed) => backend_used = "postgres"

    LocalLoadUsesFile ==
        (context = "local" /\ load_completed) => backend_used = "file"

    LocalSaveUsesFile ==
        (context = "local" /\ save_completed) => backend_used = "file"

    InMemoryInterfaceUnchanged ==
        dag_state = "ready" =>
            last_in_memory_op \in
                {"none", "add_node", "add_edge", "query_relevant",
                 "register_gwt", "register_requirement",
                 "merge_registered_nodes"}

    OnlyBackendDiffers ==
        dag_state = "ready" =>
            (/\ backend_used \in {"file", "postgres"}
             /\ last_in_memory_op \in
                    {"none", "add_node", "add_edge", "query_relevant",
                     "register_gwt", "register_requirement",
                     "merge_registered_nodes"})

    HostedReadyUsesPostgres ==
        (context = "hosted" /\ dag_state = "ready") =>
            backend_used = "postgres"

    LocalReadyUsesFile ==
        (context = "local" /\ dag_state = "ready") =>
            backend_used = "file"

    BoundedExecution == step_count <= MaxSteps

end define;

fair process worker = "worker"
begin
    CallLoad:
        persist_op := "loading";
        step_count := step_count + 1;

    SelectLoadBackend:
        if context = "hosted" then
            backend_used := "postgres";
        else
            backend_used := "file";
        end if;

    ExecuteLoad:
        dag_state      := "ready";
        load_completed := TRUE;
        persist_op     := "idle";
        step_count     := step_count + 1;

    InMemoryOps:
        either
            last_in_memory_op := "add_node";
        or
            last_in_memory_op := "add_edge";
        or
            last_in_memory_op := "query_relevant";
        or
            last_in_memory_op := "register_gwt";
        or
            last_in_memory_op := "register_requirement";
        or
            last_in_memory_op := "merge_registered_nodes";
        end either;
        step_count := step_count + 1;

    CallSave:
        persist_op := "saving";
        step_count := step_count + 1;

    SelectSaveBackend:
        if context = "hosted" then
            backend_used := "postgres";
        else
            backend_used := "file";
        end if;

    ExecuteSave:
        save_completed := TRUE;
        persist_op     := "idle";
        step_count     := step_count + 1;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "69206aa" /\ chksum(tla) = "7c0566a2")
VARIABLES pc, context, dag_state, backend_used, persist_op, last_in_memory_op, 
          step_count, load_completed, save_completed

(* define statement *)
ExpectedBackend(ctx) ==
    IF ctx = "hosted" THEN "postgres" ELSE "file"

TypeOK ==
    /\ context \in {"local", "hosted"}
    /\ dag_state \in {"uninitialized", "ready", "failed"}
    /\ backend_used \in {"none", "file", "postgres"}
    /\ persist_op \in {"idle", "loading", "saving"}
    /\ last_in_memory_op \in
           {"none", "add_node", "add_edge", "query_relevant",
            "register_gwt", "register_requirement",
            "merge_registered_nodes"}
    /\ step_count \in 0..MaxSteps
    /\ load_completed \in BOOLEAN
    /\ save_completed \in BOOLEAN

BackendMatchesContext ==
    (load_completed \/ save_completed) =>
        backend_used = ExpectedBackend(context)

HostedLoadUsesPostgres ==
    (context = "hosted" /\ load_completed) => backend_used = "postgres"

HostedSaveUsesPostgres ==
    (context = "hosted" /\ save_completed) => backend_used = "postgres"

LocalLoadUsesFile ==
    (context = "local" /\ load_completed) => backend_used = "file"

LocalSaveUsesFile ==
    (context = "local" /\ save_completed) => backend_used = "file"

InMemoryInterfaceUnchanged ==
    dag_state = "ready" =>
        last_in_memory_op \in
            {"none", "add_node", "add_edge", "query_relevant",
             "register_gwt", "register_requirement",
             "merge_registered_nodes"}

OnlyBackendDiffers ==
    dag_state = "ready" =>
        (/\ backend_used \in {"file", "postgres"}
         /\ last_in_memory_op \in
                {"none", "add_node", "add_edge", "query_relevant",
                 "register_gwt", "register_requirement",
                 "merge_registered_nodes"})

HostedReadyUsesPostgres ==
    (context = "hosted" /\ dag_state = "ready") =>
        backend_used = "postgres"

LocalReadyUsesFile ==
    (context = "local" /\ dag_state = "ready") =>
        backend_used = "file"

BoundedExecution == step_count <= MaxSteps


vars == << pc, context, dag_state, backend_used, persist_op, 
           last_in_memory_op, step_count, load_completed, save_completed >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ context \in {"local", "hosted"}
        /\ dag_state = "uninitialized"
        /\ backend_used = "none"
        /\ persist_op = "idle"
        /\ last_in_memory_op = "none"
        /\ step_count = 0
        /\ load_completed = FALSE
        /\ save_completed = FALSE
        /\ pc = [self \in ProcSet |-> "CallLoad"]

CallLoad == /\ pc["worker"] = "CallLoad"
            /\ persist_op' = "loading"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["worker"] = "SelectLoadBackend"]
            /\ UNCHANGED << context, dag_state, backend_used, 
                            last_in_memory_op, load_completed, save_completed >>

SelectLoadBackend == /\ pc["worker"] = "SelectLoadBackend"
                     /\ IF context = "hosted"
                           THEN /\ backend_used' = "postgres"
                           ELSE /\ backend_used' = "file"
                     /\ pc' = [pc EXCEPT !["worker"] = "ExecuteLoad"]
                     /\ UNCHANGED << context, dag_state, persist_op, 
                                     last_in_memory_op, step_count, 
                                     load_completed, save_completed >>

ExecuteLoad == /\ pc["worker"] = "ExecuteLoad"
               /\ dag_state' = "ready"
               /\ load_completed' = TRUE
               /\ persist_op' = "idle"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["worker"] = "InMemoryOps"]
               /\ UNCHANGED << context, backend_used, last_in_memory_op, 
                               save_completed >>

InMemoryOps == /\ pc["worker"] = "InMemoryOps"
               /\ \/ /\ last_in_memory_op' = "add_node"
                  \/ /\ last_in_memory_op' = "add_edge"
                  \/ /\ last_in_memory_op' = "query_relevant"
                  \/ /\ last_in_memory_op' = "register_gwt"
                  \/ /\ last_in_memory_op' = "register_requirement"
                  \/ /\ last_in_memory_op' = "merge_registered_nodes"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["worker"] = "CallSave"]
               /\ UNCHANGED << context, dag_state, backend_used, persist_op, 
                               load_completed, save_completed >>

CallSave == /\ pc["worker"] = "CallSave"
            /\ persist_op' = "saving"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["worker"] = "SelectSaveBackend"]
            /\ UNCHANGED << context, dag_state, backend_used, 
                            last_in_memory_op, load_completed, save_completed >>

SelectSaveBackend == /\ pc["worker"] = "SelectSaveBackend"
                     /\ IF context = "hosted"
                           THEN /\ backend_used' = "postgres"
                           ELSE /\ backend_used' = "file"
                     /\ pc' = [pc EXCEPT !["worker"] = "ExecuteSave"]
                     /\ UNCHANGED << context, dag_state, persist_op, 
                                     last_in_memory_op, step_count, 
                                     load_completed, save_completed >>

ExecuteSave == /\ pc["worker"] = "ExecuteSave"
               /\ save_completed' = TRUE
               /\ persist_op' = "idle"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["worker"] = "Finish"]
               /\ UNCHANGED << context, dag_state, backend_used, 
                               last_in_memory_op, load_completed >>

Finish == /\ pc["worker"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["worker"] = "Done"]
          /\ UNCHANGED << context, dag_state, backend_used, persist_op, 
                          last_in_memory_op, step_count, load_completed, 
                          save_completed >>

worker == CallLoad \/ SelectLoadBackend \/ ExecuteLoad \/ InMemoryOps
             \/ CallSave \/ SelectSaveBackend \/ ExecuteSave \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
====
