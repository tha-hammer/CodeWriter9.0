---- MODULE IngestScanner ----

EXTENDS Integers, Sequences, TLC

CONSTANTS MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps >= 6

(* --algorithm IngestScanner

variables
    phase = "Dequeued",
    step_count = 0,
    llm_called = FALSE,
    subprocess_called = FALSE,
    crawldb_exists \in {TRUE, FALSE},
    fn_records_written = FALSE,
    dag_loaded = FALSE,
    resource_nodes_written = FALSE,
    crawldb_uploaded = FALSE,
    dag_json_uploaded = FALSE,
    op = "idle",
    result = "none";

define

    Phases == {
        "Dequeued", "ScanningFS", "WritingCrawlDB",
        "LoadingDag", "WritingDagJson", "UploadingStorage",
        "Finished"
    }

    ValidPhase == phase \in Phases

    NoLLMCalls == llm_called = FALSE

    NoSubprocessCalls == subprocess_called = FALSE

    BoundedExecution == step_count <= MaxSteps

    UploadOrdering ==
        (crawldb_uploaded => fn_records_written) /\
        (dag_json_uploaded => resource_nodes_written)

    CompletionRequiresAll ==
        phase = "Finished" =>
            (crawldb_uploaded /\ dag_json_uploaded /\
             fn_records_written /\ resource_nodes_written /\
             llm_called = FALSE /\ subprocess_called = FALSE)

    PureExecution == NoLLMCalls /\ NoSubprocessCalls

    SafePhaseOrder ==
        (resource_nodes_written => dag_loaded) /\
        (crawldb_uploaded       => fn_records_written) /\
        (dag_json_uploaded      => resource_nodes_written)

end define;

fair process ingest = "ingest"
begin
    StartIngest:
        phase     := "ScanningFS";
        step_count := step_count + 1;
        op        := "job_dequeued";

    RunScanner:
        assert llm_called = FALSE;
        assert subprocess_called = FALSE;
        phase      := "WritingCrawlDB";
        step_count := step_count + 1;
        op         := "scanner_complete";

    WriteFnRecords:
        if crawldb_exists then
            op := "upsert_record"
        else
            op := "insert_record"
        end if;

    AfterFnWrite:
        fn_records_written := TRUE;
        phase              := "LoadingDag";
        step_count         := step_count + 1;

    LoadDag:
        dag_loaded := TRUE;
        phase      := "WritingDagJson";
        step_count := step_count + 1;
        op         := "dag_loaded";

    WriteResourceNodes:
        assert dag_loaded = TRUE;
        assert llm_called = FALSE;
        assert subprocess_called = FALSE;
        resource_nodes_written := TRUE;
        phase                  := "UploadingStorage";
        step_count             := step_count + 1;
        op                     := "resource_nodes_written";

    UploadArtifacts:
        assert fn_records_written = TRUE;
        assert resource_nodes_written = TRUE;
        crawldb_uploaded  := TRUE;
        dag_json_uploaded := TRUE;
        phase             := "Finished";
        step_count        := step_count + 1;
        op                := "artifacts_uploaded";

    Finish:
        assert crawldb_uploaded  = TRUE;
        assert dag_json_uploaded = TRUE;
        assert llm_called        = FALSE;
        assert subprocess_called = FALSE;
        assert step_count        <= MaxSteps;
        result := "success";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "4cd6f3df" /\ chksum(tla) = "f0c4b746")
VARIABLES pc, phase, step_count, llm_called, subprocess_called, 
          crawldb_exists, fn_records_written, dag_loaded, 
          resource_nodes_written, crawldb_uploaded, dag_json_uploaded, op, 
          result

(* define statement *)
Phases == {
    "Dequeued", "ScanningFS", "WritingCrawlDB",
    "LoadingDag", "WritingDagJson", "UploadingStorage",
    "Finished"
}

ValidPhase == phase \in Phases

NoLLMCalls == llm_called = FALSE

NoSubprocessCalls == subprocess_called = FALSE

BoundedExecution == step_count <= MaxSteps

UploadOrdering ==
    (crawldb_uploaded => fn_records_written) /\
    (dag_json_uploaded => resource_nodes_written)

CompletionRequiresAll ==
    phase = "Finished" =>
        (crawldb_uploaded /\ dag_json_uploaded /\
         fn_records_written /\ resource_nodes_written /\
         llm_called = FALSE /\ subprocess_called = FALSE)

PureExecution == NoLLMCalls /\ NoSubprocessCalls

SafePhaseOrder ==
    (resource_nodes_written => dag_loaded) /\
    (crawldb_uploaded       => fn_records_written) /\
    (dag_json_uploaded      => resource_nodes_written)


vars == << pc, phase, step_count, llm_called, subprocess_called, 
           crawldb_exists, fn_records_written, dag_loaded, 
           resource_nodes_written, crawldb_uploaded, dag_json_uploaded, op, 
           result >>

ProcSet == {"ingest"}

Init == (* Global variables *)
        /\ phase = "Dequeued"
        /\ step_count = 0
        /\ llm_called = FALSE
        /\ subprocess_called = FALSE
        /\ crawldb_exists \in {TRUE, FALSE}
        /\ fn_records_written = FALSE
        /\ dag_loaded = FALSE
        /\ resource_nodes_written = FALSE
        /\ crawldb_uploaded = FALSE
        /\ dag_json_uploaded = FALSE
        /\ op = "idle"
        /\ result = "none"
        /\ pc = [self \in ProcSet |-> "StartIngest"]

StartIngest == /\ pc["ingest"] = "StartIngest"
               /\ phase' = "ScanningFS"
               /\ step_count' = step_count + 1
               /\ op' = "job_dequeued"
               /\ pc' = [pc EXCEPT !["ingest"] = "RunScanner"]
               /\ UNCHANGED << llm_called, subprocess_called, crawldb_exists, 
                               fn_records_written, dag_loaded, 
                               resource_nodes_written, crawldb_uploaded, 
                               dag_json_uploaded, result >>

RunScanner == /\ pc["ingest"] = "RunScanner"
              /\ Assert(llm_called = FALSE, 
                        "Failure of assertion at line 68, column 9.")
              /\ Assert(subprocess_called = FALSE, 
                        "Failure of assertion at line 69, column 9.")
              /\ phase' = "WritingCrawlDB"
              /\ step_count' = step_count + 1
              /\ op' = "scanner_complete"
              /\ pc' = [pc EXCEPT !["ingest"] = "WriteFnRecords"]
              /\ UNCHANGED << llm_called, subprocess_called, crawldb_exists, 
                              fn_records_written, dag_loaded, 
                              resource_nodes_written, crawldb_uploaded, 
                              dag_json_uploaded, result >>

WriteFnRecords == /\ pc["ingest"] = "WriteFnRecords"
                  /\ IF crawldb_exists
                        THEN /\ op' = "upsert_record"
                        ELSE /\ op' = "insert_record"
                  /\ pc' = [pc EXCEPT !["ingest"] = "AfterFnWrite"]
                  /\ UNCHANGED << phase, step_count, llm_called, 
                                  subprocess_called, crawldb_exists, 
                                  fn_records_written, dag_loaded, 
                                  resource_nodes_written, crawldb_uploaded, 
                                  dag_json_uploaded, result >>

AfterFnWrite == /\ pc["ingest"] = "AfterFnWrite"
                /\ fn_records_written' = TRUE
                /\ phase' = "LoadingDag"
                /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["ingest"] = "LoadDag"]
                /\ UNCHANGED << llm_called, subprocess_called, crawldb_exists, 
                                dag_loaded, resource_nodes_written, 
                                crawldb_uploaded, dag_json_uploaded, op, 
                                result >>

LoadDag == /\ pc["ingest"] = "LoadDag"
           /\ dag_loaded' = TRUE
           /\ phase' = "WritingDagJson"
           /\ step_count' = step_count + 1
           /\ op' = "dag_loaded"
           /\ pc' = [pc EXCEPT !["ingest"] = "WriteResourceNodes"]
           /\ UNCHANGED << llm_called, subprocess_called, crawldb_exists, 
                           fn_records_written, resource_nodes_written, 
                           crawldb_uploaded, dag_json_uploaded, result >>

WriteResourceNodes == /\ pc["ingest"] = "WriteResourceNodes"
                      /\ Assert(dag_loaded = TRUE, 
                                "Failure of assertion at line 93, column 9.")
                      /\ Assert(llm_called = FALSE, 
                                "Failure of assertion at line 94, column 9.")
                      /\ Assert(subprocess_called = FALSE, 
                                "Failure of assertion at line 95, column 9.")
                      /\ resource_nodes_written' = TRUE
                      /\ phase' = "UploadingStorage"
                      /\ step_count' = step_count + 1
                      /\ op' = "resource_nodes_written"
                      /\ pc' = [pc EXCEPT !["ingest"] = "UploadArtifacts"]
                      /\ UNCHANGED << llm_called, subprocess_called, 
                                      crawldb_exists, fn_records_written, 
                                      dag_loaded, crawldb_uploaded, 
                                      dag_json_uploaded, result >>

UploadArtifacts == /\ pc["ingest"] = "UploadArtifacts"
                   /\ Assert(fn_records_written = TRUE, 
                             "Failure of assertion at line 102, column 9.")
                   /\ Assert(resource_nodes_written = TRUE, 
                             "Failure of assertion at line 103, column 9.")
                   /\ crawldb_uploaded' = TRUE
                   /\ dag_json_uploaded' = TRUE
                   /\ phase' = "Finished"
                   /\ step_count' = step_count + 1
                   /\ op' = "artifacts_uploaded"
                   /\ pc' = [pc EXCEPT !["ingest"] = "Finish"]
                   /\ UNCHANGED << llm_called, subprocess_called, 
                                   crawldb_exists, fn_records_written, 
                                   dag_loaded, resource_nodes_written, result >>

Finish == /\ pc["ingest"] = "Finish"
          /\ Assert(crawldb_uploaded  = TRUE, 
                    "Failure of assertion at line 111, column 9.")
          /\ Assert(dag_json_uploaded = TRUE, 
                    "Failure of assertion at line 112, column 9.")
          /\ Assert(llm_called        = FALSE, 
                    "Failure of assertion at line 113, column 9.")
          /\ Assert(subprocess_called = FALSE, 
                    "Failure of assertion at line 114, column 9.")
          /\ Assert(step_count        <= MaxSteps, 
                    "Failure of assertion at line 115, column 9.")
          /\ result' = "success"
          /\ pc' = [pc EXCEPT !["ingest"] = "Done"]
          /\ UNCHANGED << phase, step_count, llm_called, subprocess_called, 
                          crawldb_exists, fn_records_written, dag_loaded, 
                          resource_nodes_written, crawldb_uploaded, 
                          dag_json_uploaded, op >>

ingest == StartIngest \/ RunScanner \/ WriteFnRecords \/ AfterFnWrite
             \/ LoadDag \/ WriteResourceNodes \/ UploadArtifacts \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == ingest
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(ingest)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

EventuallyFinished == <>(phase = "Finished")

====
