--------------------------- MODULE ArtifactUpload ---------------------------

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    ArtifactPatterns,
    StoragePrefix,
    MaxSteps

ASSUME ArtifactPatterns # {}
ASSUME MaxSteps \in Nat /\ MaxSteps > 0

(* --algorithm ArtifactUpload

variables
    core_result   = "none",
    worker_phase  = "idle",
    pending       = ArtifactPatterns,
    uploaded      = {},
    container_up  = TRUE,
    step_count    = 0;

define

    UploadBeforeExit ==
        ~container_up =>
            (pending = {} /\ uploaded = ArtifactPatterns)

    UploadAfterCore ==
        worker_phase = "uploading" =>
            core_result \in {"passed", "failed"}

    ContainerExitRequiresUpload ==
        ~container_up =>
            ( pending = {}                          /\
              uploaded = ArtifactPatterns           /\
              core_result \in {"passed", "failed"}  )

    ValidWorkerPhase ==
        worker_phase \in {"idle", "uploading", "complete", "exited"}

    ValidCoreResult ==
        core_result \in {"none", "passed", "failed"}

    BoundedSteps == step_count <= MaxSteps

end define;

fair process core_pipeline = "core"
begin
    RunCore:
        either
            core_result := "passed"
        or
            core_result := "failed"
        end either;
end process;

fair process artifact_uploader = "worker"
begin
    AwaitCore:
        await core_result \in {"passed", "failed"};
        worker_phase := "uploading";
    UploadArtifacts:
        while pending # {} do
            UploadOne:
                with artifact \in pending do
                    uploaded   := uploaded \union {artifact};
                    pending    := pending \ {artifact};
                    step_count := step_count + 1;
                end with;
        end while;
    MarkComplete:
        worker_phase := "complete";
    Terminate:
        assert pending = {} /\ uploaded = ArtifactPatterns;
        container_up := FALSE;
        worker_phase := "exited";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "70e18cae" /\ chksum(tla) = "c8176f8b")
VARIABLES pc, core_result, worker_phase, pending, uploaded, container_up, 
          step_count

(* define statement *)
UploadBeforeExit ==
    ~container_up =>
        (pending = {} /\ uploaded = ArtifactPatterns)

UploadAfterCore ==
    worker_phase = "uploading" =>
        core_result \in {"passed", "failed"}

ContainerExitRequiresUpload ==
    ~container_up =>
        ( pending = {}                          /\
          uploaded = ArtifactPatterns           /\
          core_result \in {"passed", "failed"}  )

ValidWorkerPhase ==
    worker_phase \in {"idle", "uploading", "complete", "exited"}

ValidCoreResult ==
    core_result \in {"none", "passed", "failed"}

BoundedSteps == step_count <= MaxSteps


vars == << pc, core_result, worker_phase, pending, uploaded, container_up, 
           step_count >>

ProcSet == {"core"} \cup {"worker"}

Init == (* Global variables *)
        /\ core_result = "none"
        /\ worker_phase = "idle"
        /\ pending = ArtifactPatterns
        /\ uploaded = {}
        /\ container_up = TRUE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> CASE self = "core" -> "RunCore"
                                        [] self = "worker" -> "AwaitCore"]

RunCore == /\ pc["core"] = "RunCore"
           /\ \/ /\ core_result' = "passed"
              \/ /\ core_result' = "failed"
           /\ pc' = [pc EXCEPT !["core"] = "Done"]
           /\ UNCHANGED << worker_phase, pending, uploaded, container_up, 
                           step_count >>

core_pipeline == RunCore

AwaitCore == /\ pc["worker"] = "AwaitCore"
             /\ core_result \in {"passed", "failed"}
             /\ worker_phase' = "uploading"
             /\ pc' = [pc EXCEPT !["worker"] = "UploadArtifacts"]
             /\ UNCHANGED << core_result, pending, uploaded, container_up, 
                             step_count >>

UploadArtifacts == /\ pc["worker"] = "UploadArtifacts"
                   /\ IF pending # {}
                         THEN /\ pc' = [pc EXCEPT !["worker"] = "UploadOne"]
                         ELSE /\ pc' = [pc EXCEPT !["worker"] = "MarkComplete"]
                   /\ UNCHANGED << core_result, worker_phase, pending, 
                                   uploaded, container_up, step_count >>

UploadOne == /\ pc["worker"] = "UploadOne"
             /\ \E artifact \in pending:
                  /\ uploaded' = (uploaded \union {artifact})
                  /\ pending' = pending \ {artifact}
                  /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["worker"] = "UploadArtifacts"]
             /\ UNCHANGED << core_result, worker_phase, container_up >>

MarkComplete == /\ pc["worker"] = "MarkComplete"
                /\ worker_phase' = "complete"
                /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                /\ UNCHANGED << core_result, pending, uploaded, container_up, 
                                step_count >>

Terminate == /\ pc["worker"] = "Terminate"
             /\ Assert(pending = {} /\ uploaded = ArtifactPatterns, 
                       "Failure of assertion at line 76, column 9.")
             /\ container_up' = FALSE
             /\ worker_phase' = "exited"
             /\ pc' = [pc EXCEPT !["worker"] = "Done"]
             /\ UNCHANGED << core_result, pending, uploaded, step_count >>

artifact_uploader == AwaitCore \/ UploadArtifacts \/ UploadOne
                        \/ MarkComplete \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == core_pipeline \/ artifact_uploader
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(core_pipeline)
        /\ WF_vars(artifact_uploader)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec =>
    [](
        ContainerExitRequiresUpload /\
        UploadBeforeExit            /\
        UploadAfterCore             /\
        ValidWorkerPhase            /\
        ValidCoreResult             /\
        BoundedSteps
    )

===========================================================================
