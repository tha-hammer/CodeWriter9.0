---- MODULE WorkerContextReconstruction ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps >= 7

(* --algorithm WorkerContextReconstruction

variables
    object_storage_ok \in BOOLEAN,
    postgres_ok \in BOOLEAN,
    current_state = "Fresh",
    artifacts_downloaded = FALSE,
    postgres_data_read = FALSE,
    project_context_ready = FALSE,
    registry_dag_ready = FALSE,
    crawl_store_ready = FALSE,
    session_affinity_used = FALSE,
    warm_cache_used = FALSE,
    prev_worker_conn_used = FALSE,
    step_count = 0;

define

    AllStates == {
        "Fresh",
        "FetchingArtifacts",
        "ReadingPostgres",
        "BuildingProjectContext",
        "BuildingRegistryDag",
        "BuildingCrawlStore",
        "Reconstructed",
        "Failed"
    }

    TerminalStates == {"Reconstructed", "Failed"}

    ValidState == current_state \in AllStates

    BoundedExecution == step_count <= MaxSteps

    FullReconstructionOnSuccess ==
        current_state = "Reconstructed" =>
            /\ project_context_ready
            /\ registry_dag_ready
            /\ crawl_store_ready

    NoSessionAffinityEver == ~session_affinity_used

    NoWarmCacheEver == ~warm_cache_used

    NoPrevWorkerConnEver == ~prev_worker_conn_used

    StatelessReconstruction ==
        (project_context_ready \/ registry_dag_ready \/ crawl_store_ready) =>
            /\ ~session_affinity_used
            /\ ~warm_cache_used
            /\ ~prev_worker_conn_used

    ArtifactsPrecedeContext ==
        project_context_ready => artifacts_downloaded

    PostgresPrecedesCrawlStore ==
        crawl_store_ready => postgres_data_read

    BothSourcesRequiredForSuccess ==
        current_state = "Reconstructed" =>
            /\ artifacts_downloaded
            /\ postgres_data_read

    GivenImpliesThen ==
        (object_storage_ok /\ postgres_ok) =>
            (current_state = "Reconstructed" =>
                /\ project_context_ready
                /\ registry_dag_ready
                /\ crawl_store_ready
                /\ ~session_affinity_used
                /\ ~warm_cache_used
                /\ ~prev_worker_conn_used)

    ReconstructionOrderRespected ==
        registry_dag_ready => project_context_ready

    CrawlStoreLastInChain ==
        crawl_store_ready => registry_dag_ready

end define;

fair process worker = "worker"
begin
    Reconstruct:
        while current_state \notin TerminalStates /\ step_count < MaxSteps do
            if current_state = "Fresh" then
                current_state := "FetchingArtifacts";
                step_count := step_count + 1;
            elsif current_state = "FetchingArtifacts" then
                if object_storage_ok then
                    artifacts_downloaded := TRUE;
                    current_state := "ReadingPostgres";
                else
                    current_state := "Failed";
                end if;
                step_count := step_count + 1;
            elsif current_state = "ReadingPostgres" then
                if postgres_ok then
                    postgres_data_read := TRUE;
                    current_state := "BuildingProjectContext";
                else
                    current_state := "Failed";
                end if;
                step_count := step_count + 1;
            elsif current_state = "BuildingProjectContext" then
                project_context_ready := TRUE;
                current_state := "BuildingRegistryDag";
                step_count := step_count + 1;
            elsif current_state = "BuildingRegistryDag" then
                registry_dag_ready := TRUE;
                current_state := "BuildingCrawlStore";
                step_count := step_count + 1;
            elsif current_state = "BuildingCrawlStore" then
                crawl_store_ready := TRUE;
                current_state := "Reconstructed";
                step_count := step_count + 1;
            end if;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8df1696c" /\ chksum(tla) = "5d84dd39")
VARIABLES pc, object_storage_ok, postgres_ok, current_state, 
          artifacts_downloaded, postgres_data_read, project_context_ready, 
          registry_dag_ready, crawl_store_ready, session_affinity_used, 
          warm_cache_used, prev_worker_conn_used, step_count

(* define statement *)
AllStates == {
    "Fresh",
    "FetchingArtifacts",
    "ReadingPostgres",
    "BuildingProjectContext",
    "BuildingRegistryDag",
    "BuildingCrawlStore",
    "Reconstructed",
    "Failed"
}

TerminalStates == {"Reconstructed", "Failed"}

ValidState == current_state \in AllStates

BoundedExecution == step_count <= MaxSteps

FullReconstructionOnSuccess ==
    current_state = "Reconstructed" =>
        /\ project_context_ready
        /\ registry_dag_ready
        /\ crawl_store_ready

NoSessionAffinityEver == ~session_affinity_used

NoWarmCacheEver == ~warm_cache_used

NoPrevWorkerConnEver == ~prev_worker_conn_used

StatelessReconstruction ==
    (project_context_ready \/ registry_dag_ready \/ crawl_store_ready) =>
        /\ ~session_affinity_used
        /\ ~warm_cache_used
        /\ ~prev_worker_conn_used

ArtifactsPrecedeContext ==
    project_context_ready => artifacts_downloaded

PostgresPrecedesCrawlStore ==
    crawl_store_ready => postgres_data_read

BothSourcesRequiredForSuccess ==
    current_state = "Reconstructed" =>
        /\ artifacts_downloaded
        /\ postgres_data_read

GivenImpliesThen ==
    (object_storage_ok /\ postgres_ok) =>
        (current_state = "Reconstructed" =>
            /\ project_context_ready
            /\ registry_dag_ready
            /\ crawl_store_ready
            /\ ~session_affinity_used
            /\ ~warm_cache_used
            /\ ~prev_worker_conn_used)

ReconstructionOrderRespected ==
    registry_dag_ready => project_context_ready

CrawlStoreLastInChain ==
    crawl_store_ready => registry_dag_ready


vars == << pc, object_storage_ok, postgres_ok, current_state, 
           artifacts_downloaded, postgres_data_read, project_context_ready, 
           registry_dag_ready, crawl_store_ready, session_affinity_used, 
           warm_cache_used, prev_worker_conn_used, step_count >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ object_storage_ok \in BOOLEAN
        /\ postgres_ok \in BOOLEAN
        /\ current_state = "Fresh"
        /\ artifacts_downloaded = FALSE
        /\ postgres_data_read = FALSE
        /\ project_context_ready = FALSE
        /\ registry_dag_ready = FALSE
        /\ crawl_store_ready = FALSE
        /\ session_affinity_used = FALSE
        /\ warm_cache_used = FALSE
        /\ prev_worker_conn_used = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "Reconstruct"]

Reconstruct == /\ pc["worker"] = "Reconstruct"
               /\ IF current_state \notin TerminalStates /\ step_count < MaxSteps
                     THEN /\ IF current_state = "Fresh"
                                THEN /\ current_state' = "FetchingArtifacts"
                                     /\ step_count' = step_count + 1
                                     /\ UNCHANGED << artifacts_downloaded, 
                                                     postgres_data_read, 
                                                     project_context_ready, 
                                                     registry_dag_ready, 
                                                     crawl_store_ready >>
                                ELSE /\ IF current_state = "FetchingArtifacts"
                                           THEN /\ IF object_storage_ok
                                                      THEN /\ artifacts_downloaded' = TRUE
                                                           /\ current_state' = "ReadingPostgres"
                                                      ELSE /\ current_state' = "Failed"
                                                           /\ UNCHANGED artifacts_downloaded
                                                /\ step_count' = step_count + 1
                                                /\ UNCHANGED << postgres_data_read, 
                                                                project_context_ready, 
                                                                registry_dag_ready, 
                                                                crawl_store_ready >>
                                           ELSE /\ IF current_state = "ReadingPostgres"
                                                      THEN /\ IF postgres_ok
                                                                 THEN /\ postgres_data_read' = TRUE
                                                                      /\ current_state' = "BuildingProjectContext"
                                                                 ELSE /\ current_state' = "Failed"
                                                                      /\ UNCHANGED postgres_data_read
                                                           /\ step_count' = step_count + 1
                                                           /\ UNCHANGED << project_context_ready, 
                                                                           registry_dag_ready, 
                                                                           crawl_store_ready >>
                                                      ELSE /\ IF current_state = "BuildingProjectContext"
                                                                 THEN /\ project_context_ready' = TRUE
                                                                      /\ current_state' = "BuildingRegistryDag"
                                                                      /\ step_count' = step_count + 1
                                                                      /\ UNCHANGED << registry_dag_ready, 
                                                                                      crawl_store_ready >>
                                                                 ELSE /\ IF current_state = "BuildingRegistryDag"
                                                                            THEN /\ registry_dag_ready' = TRUE
                                                                                 /\ current_state' = "BuildingCrawlStore"
                                                                                 /\ step_count' = step_count + 1
                                                                                 /\ UNCHANGED crawl_store_ready
                                                                            ELSE /\ IF current_state = "BuildingCrawlStore"
                                                                                       THEN /\ crawl_store_ready' = TRUE
                                                                                            /\ current_state' = "Reconstructed"
                                                                                            /\ step_count' = step_count + 1
                                                                                       ELSE /\ TRUE
                                                                                            /\ UNCHANGED << current_state, 
                                                                                                            crawl_store_ready, 
                                                                                                            step_count >>
                                                                                 /\ UNCHANGED registry_dag_ready
                                                                      /\ UNCHANGED project_context_ready
                                                           /\ UNCHANGED postgres_data_read
                                                /\ UNCHANGED artifacts_downloaded
                          /\ pc' = [pc EXCEPT !["worker"] = "Reconstruct"]
                     ELSE /\ pc' = [pc EXCEPT !["worker"] = "Finish"]
                          /\ UNCHANGED << current_state, artifacts_downloaded, 
                                          postgres_data_read, 
                                          project_context_ready, 
                                          registry_dag_ready, 
                                          crawl_store_ready, step_count >>
               /\ UNCHANGED << object_storage_ok, postgres_ok, 
                               session_affinity_used, warm_cache_used, 
                               prev_worker_conn_used >>

Finish == /\ pc["worker"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["worker"] = "Done"]
          /\ UNCHANGED << object_storage_ok, postgres_ok, current_state, 
                          artifacts_downloaded, postgres_data_read, 
                          project_context_ready, registry_dag_ready, 
                          crawl_store_ready, session_affinity_used, 
                          warm_cache_used, prev_worker_conn_used, step_count >>

worker == Reconstruct \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

TypeInvariant ==
    /\ current_state \in {
           "Fresh", "FetchingArtifacts", "ReadingPostgres",
           "BuildingProjectContext", "BuildingRegistryDag",
           "BuildingCrawlStore", "Reconstructed", "Failed"
       }
    /\ artifacts_downloaded  \in BOOLEAN
    /\ postgres_data_read    \in BOOLEAN
    /\ project_context_ready \in BOOLEAN
    /\ registry_dag_ready    \in BOOLEAN
    /\ crawl_store_ready     \in BOOLEAN
    /\ session_affinity_used \in BOOLEAN
    /\ warm_cache_used       \in BOOLEAN
    /\ prev_worker_conn_used \in BOOLEAN
    /\ step_count            \in Nat

Liveness ==
    <>(current_state \in {"Reconstructed", "Failed"})

ReconstructedGivenBothSources ==
    (object_storage_ok /\ postgres_ok) => <>(current_state = "Reconstructed")

====
