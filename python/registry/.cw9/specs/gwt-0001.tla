---- MODULE WorkerArtifactDownload ----
(*
 * Specification for gwt-0001
 * Worker must download all declared input artifacts to the ephemeral
 * local workspace at /workspace/.cw9/ before invoking any core pipeline function.
 *
 * Expected TLC model values:
 *   ArtifactTypes     <- {"schemas", "dag_json", "crawl_db", "specs", "bridge_artifacts"}
 *   PipelineFunctions <- {"from_target", "run_loop", "run_test_gen_loop", "run_bridge"}
 *   MaxSteps          <- 20
 *)

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    ArtifactTypes,
    PipelineFunctions,
    MaxSteps

(* --algorithm WorkerArtifactDownload

variables
    worker_state = "dequeued",
    downloaded = {},
    pipeline_fn_invoked = "none",
    step_count = 0,
    job_result = "none";

define

    AllDownloaded == downloaded = ArtifactTypes

    PipelineInvoked == pipeline_fn_invoked /= "none"

    SafetyNoEarlyPipelineInvocation ==
        PipelineInvoked => AllDownloaded

    PipelineOnlyAfterWorkspaceReady ==
        worker_state = "pipeline_running" => AllDownloaded

    WorkspacePrefixCorrect ==
        worker_state = "workspace_ready" => AllDownloaded

    ValidState ==
        worker_state \in {
            "dequeued", "downloading", "workspace_ready",
            "pipeline_running", "completed", "failed"
        }

    DownloadedSubset == downloaded \subseteq ArtifactTypes

    BoundedExecution == step_count <= MaxSteps

    ValidPipelineFn ==
        pipeline_fn_invoked = "none" \/ pipeline_fn_invoked \in PipelineFunctions

    TypeInvariant ==
        /\ ValidState
        /\ DownloadedSubset
        /\ BoundedExecution
        /\ ValidPipelineFn

    GwtThenCondition ==
        /\ SafetyNoEarlyPipelineInvocation
        /\ PipelineOnlyAfterWorkspaceReady

end define;

fair process worker = "worker"
begin
    BeginExecution:
        worker_state := "downloading";
        step_count := step_count + 1;

    DownloadArtifacts:
        while downloaded /= ArtifactTypes /\ step_count < MaxSteps do
            DownloadNext:
                with artifact \in (ArtifactTypes \ downloaded) do
                    downloaded := downloaded \union {artifact};
                    step_count := step_count + 1;
                end with;
        end while;

    CheckWorkspace:
        if downloaded = ArtifactTypes then
            worker_state := "workspace_ready";
            step_count := step_count + 1;
        else
            worker_state := "failed";
            job_result := "artifact_download_incomplete";
            step_count := step_count + 1;
            goto Terminate;
        end if;

    SelectPipelineFunction:
        with fn \in PipelineFunctions do
            pipeline_fn_invoked := fn;
        end with;
        worker_state := "pipeline_running";
        step_count := step_count + 1;

    AwaitPipelineResult:
        either
            worker_state := "completed";
            job_result := "success";
        or
            worker_state := "failed";
            job_result := "pipeline_error";
        end either;
        step_count := step_count + 1;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "4c348aad" /\ chksum(tla) = "4c9f209e")
VARIABLES pc, worker_state, downloaded, pipeline_fn_invoked, step_count, 
          job_result

(* define statement *)
AllDownloaded == downloaded = ArtifactTypes

PipelineInvoked == pipeline_fn_invoked /= "none"

SafetyNoEarlyPipelineInvocation ==
    PipelineInvoked => AllDownloaded

PipelineOnlyAfterWorkspaceReady ==
    worker_state = "pipeline_running" => AllDownloaded

WorkspacePrefixCorrect ==
    worker_state = "workspace_ready" => AllDownloaded

ValidState ==
    worker_state \in {
        "dequeued", "downloading", "workspace_ready",
        "pipeline_running", "completed", "failed"
    }

DownloadedSubset == downloaded \subseteq ArtifactTypes

BoundedExecution == step_count <= MaxSteps

ValidPipelineFn ==
    pipeline_fn_invoked = "none" \/ pipeline_fn_invoked \in PipelineFunctions

TypeInvariant ==
    /\ ValidState
    /\ DownloadedSubset
    /\ BoundedExecution
    /\ ValidPipelineFn

GwtThenCondition ==
    /\ SafetyNoEarlyPipelineInvocation
    /\ PipelineOnlyAfterWorkspaceReady


vars == << pc, worker_state, downloaded, pipeline_fn_invoked, step_count, 
           job_result >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ worker_state = "dequeued"
        /\ downloaded = {}
        /\ pipeline_fn_invoked = "none"
        /\ step_count = 0
        /\ job_result = "none"
        /\ pc = [self \in ProcSet |-> "BeginExecution"]

BeginExecution == /\ pc["worker"] = "BeginExecution"
                  /\ worker_state' = "downloading"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["worker"] = "DownloadArtifacts"]
                  /\ UNCHANGED << downloaded, pipeline_fn_invoked, job_result >>

DownloadArtifacts == /\ pc["worker"] = "DownloadArtifacts"
                     /\ IF downloaded /= ArtifactTypes /\ step_count < MaxSteps
                           THEN /\ pc' = [pc EXCEPT !["worker"] = "DownloadNext"]
                           ELSE /\ pc' = [pc EXCEPT !["worker"] = "CheckWorkspace"]
                     /\ UNCHANGED << worker_state, downloaded, 
                                     pipeline_fn_invoked, step_count, 
                                     job_result >>

DownloadNext == /\ pc["worker"] = "DownloadNext"
                /\ \E artifact \in (ArtifactTypes \ downloaded):
                     /\ downloaded' = (downloaded \union {artifact})
                     /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["worker"] = "DownloadArtifacts"]
                /\ UNCHANGED << worker_state, pipeline_fn_invoked, job_result >>

CheckWorkspace == /\ pc["worker"] = "CheckWorkspace"
                  /\ IF downloaded = ArtifactTypes
                        THEN /\ worker_state' = "workspace_ready"
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["worker"] = "SelectPipelineFunction"]
                             /\ UNCHANGED job_result
                        ELSE /\ worker_state' = "failed"
                             /\ job_result' = "artifact_download_incomplete"
                             /\ step_count' = step_count + 1
                             /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                  /\ UNCHANGED << downloaded, pipeline_fn_invoked >>

SelectPipelineFunction == /\ pc["worker"] = "SelectPipelineFunction"
                          /\ \E fn \in PipelineFunctions:
                               pipeline_fn_invoked' = fn
                          /\ worker_state' = "pipeline_running"
                          /\ step_count' = step_count + 1
                          /\ pc' = [pc EXCEPT !["worker"] = "AwaitPipelineResult"]
                          /\ UNCHANGED << downloaded, job_result >>

AwaitPipelineResult == /\ pc["worker"] = "AwaitPipelineResult"
                       /\ \/ /\ worker_state' = "completed"
                             /\ job_result' = "success"
                          \/ /\ worker_state' = "failed"
                             /\ job_result' = "pipeline_error"
                       /\ step_count' = step_count + 1
                       /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                       /\ UNCHANGED << downloaded, pipeline_fn_invoked >>

Terminate == /\ pc["worker"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["worker"] = "Done"]
             /\ UNCHANGED << worker_state, downloaded, pipeline_fn_invoked, 
                             step_count, job_result >>

worker == BeginExecution \/ DownloadArtifacts \/ DownloadNext
             \/ CheckWorkspace \/ SelectPipelineFunction
             \/ AwaitPipelineResult \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

Liveness == <>(worker_state \in {"completed", "failed"})

====
