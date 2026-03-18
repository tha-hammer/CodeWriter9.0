---- MODULE CrawlOrchestrator_gwt0017 ----
(*
 * PlusCal specification for gwt-0017
 *
 * Given:  crawl.db downloaded with skeleton FnRecord entries (SKELETON_ONLY DO)
 * When:   CrawlOrchestrator.run() executes the DFS extraction loop
 * Then:   each skeleton record receives exactly one Claude Agent SDK call
 *         (claude-sonnet-4-6) via extract_one() to fill IN:DO:OUT data;
 *         on full completion the populated crawl.db is uploaded to object
 *         storage and the Postgres job record is updated to PASSED.
 *)

EXTENDS Integers, FiniteSets, TLC

Records  == {"rec1", "rec2", "rec3"}
MaxSteps == Cardinality(Records) * 2 + 4

(* --algorithm CrawlOrchestratorDFS

variables
    dfs_stack   = Records,
    extracted   = {},
    sdk_calls   = [r \in Records |-> 0],
    current_rec = "none",
    db_uploaded = FALSE,
    job_status  = "RUNNING",
    phase       = "DFS_LOOP",
    step_count  = 0;

define

    AllExtracted == extracted = Records

    AtMostOneSDKCallPerRecord == \A r \in Records : sdk_calls[r] <= 1

    ExactlyOneCallForExtractedRecords ==
        \A r \in extracted : sdk_calls[r] = 1

    UploadOnlyAfterAllExtracted == db_uploaded => AllExtracted

    PassedOnlyAfterUpload == job_status = "PASSED" => db_uploaded

    BoundedExecution == step_count <= MaxSteps

    CompletionCorrectness ==
        phase = "COMPLETE" =>
            ( AllExtracted
              /\ db_uploaded
              /\ job_status = "PASSED" )

    ExactlyOneCallAtCompletion ==
        phase = "COMPLETE" => (\A r \in Records : sdk_calls[r] = 1)

    NoSkeletonRecordLeftBehind ==
        phase = "COMPLETE" => (dfs_stack = {} /\ extracted = Records)

end define;

fair process Orchestrator = "orchestrator"
begin
    DfsLoop:
        while dfs_stack # {} do
            PickRecord:
                with r \in dfs_stack do
                    current_rec := r;
                    dfs_stack   := dfs_stack \ {r};
                end with;
                step_count := step_count + 1;
            ExtractOne:
                sdk_calls[current_rec] := sdk_calls[current_rec] + 1;
                extracted              := extracted \union {current_rec};
                current_rec            := "none";
                step_count             := step_count + 1;
        end while;
    UploadDb:
        db_uploaded := TRUE;
        phase       := "UPLOADING";
        step_count  := step_count + 1;
    UpdateJob:
        job_status := "PASSED";
        phase      := "COMPLETE";
        step_count := step_count + 1;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "a29c234" /\ chksum(tla) = "742e3de5")
VARIABLES pc, dfs_stack, extracted, sdk_calls, current_rec, db_uploaded, 
          job_status, phase, step_count

(* define statement *)
AllExtracted == extracted = Records

AtMostOneSDKCallPerRecord == \A r \in Records : sdk_calls[r] <= 1

ExactlyOneCallForExtractedRecords ==
    \A r \in extracted : sdk_calls[r] = 1

UploadOnlyAfterAllExtracted == db_uploaded => AllExtracted

PassedOnlyAfterUpload == job_status = "PASSED" => db_uploaded

BoundedExecution == step_count <= MaxSteps

CompletionCorrectness ==
    phase = "COMPLETE" =>
        ( AllExtracted
          /\ db_uploaded
          /\ job_status = "PASSED" )

ExactlyOneCallAtCompletion ==
    phase = "COMPLETE" => (\A r \in Records : sdk_calls[r] = 1)

NoSkeletonRecordLeftBehind ==
    phase = "COMPLETE" => (dfs_stack = {} /\ extracted = Records)


vars == << pc, dfs_stack, extracted, sdk_calls, current_rec, db_uploaded, 
           job_status, phase, step_count >>

ProcSet == {"orchestrator"}

Init == (* Global variables *)
        /\ dfs_stack = Records
        /\ extracted = {}
        /\ sdk_calls = [r \in Records |-> 0]
        /\ current_rec = "none"
        /\ db_uploaded = FALSE
        /\ job_status = "RUNNING"
        /\ phase = "DFS_LOOP"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "DfsLoop"]

DfsLoop == /\ pc["orchestrator"] = "DfsLoop"
           /\ IF dfs_stack # {}
                 THEN /\ pc' = [pc EXCEPT !["orchestrator"] = "PickRecord"]
                 ELSE /\ pc' = [pc EXCEPT !["orchestrator"] = "UploadDb"]
           /\ UNCHANGED << dfs_stack, extracted, sdk_calls, current_rec, 
                           db_uploaded, job_status, phase, step_count >>

PickRecord == /\ pc["orchestrator"] = "PickRecord"
              /\ \E r \in dfs_stack:
                   /\ current_rec' = r
                   /\ dfs_stack' = dfs_stack \ {r}
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["orchestrator"] = "ExtractOne"]
              /\ UNCHANGED << extracted, sdk_calls, db_uploaded, job_status, 
                              phase >>

ExtractOne == /\ pc["orchestrator"] = "ExtractOne"
              /\ sdk_calls' = [sdk_calls EXCEPT ![current_rec] = sdk_calls[current_rec] + 1]
              /\ extracted' = (extracted \union {current_rec})
              /\ current_rec' = "none"
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["orchestrator"] = "DfsLoop"]
              /\ UNCHANGED << dfs_stack, db_uploaded, job_status, phase >>

UploadDb == /\ pc["orchestrator"] = "UploadDb"
            /\ db_uploaded' = TRUE
            /\ phase' = "UPLOADING"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["orchestrator"] = "UpdateJob"]
            /\ UNCHANGED << dfs_stack, extracted, sdk_calls, current_rec, 
                            job_status >>

UpdateJob == /\ pc["orchestrator"] = "UpdateJob"
             /\ job_status' = "PASSED"
             /\ phase' = "COMPLETE"
             /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["orchestrator"] = "Done"]
             /\ UNCHANGED << dfs_stack, extracted, sdk_calls, current_rec, 
                             db_uploaded >>

Orchestrator == DfsLoop \/ PickRecord \/ ExtractOne \/ UploadDb
                   \/ UpdateJob

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
