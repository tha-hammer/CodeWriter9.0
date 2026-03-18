---- MODULE GWT0024WriteResult ----
(*
 * PlusCal specification for gwt-0024: write_result_file hosted behavior.
 *
 * Given:  A loop or gen-tests worker job has completed
 *         (PASS, FAIL, or max-retries exhausted).
 * When:   write_result_file() is called with the job outcome.
 * Then:   (1) Structured result (gwt_id, result, attempts, error) is written
 *             to the Postgres job_results table.
 *         (2) Raw LLM session logs are uploaded to object storage.
 *         (3) Local .cw9/sessions/ write does NOT occur — replaced entirely
 *             by operations (1) and (2).
 *)

EXTENDS Integers, FiniteSets, TLC, Sequences

CONSTANTS
    GwtId,
    MaxAttempts,
    MaxSteps

ASSUME MaxAttempts \in Nat /\ MaxAttempts >= 1
ASSUME MaxSteps    \in Nat /\ MaxSteps    >= 6

JobOutcomes == {"PASS", "FAIL", "MAX_RETRIES"}

States == {
    "JobRunning",
    "JobComplete",
    "WritingDB",
    "UploadingLogs",
    "Persisted",
    "DBError",
    "StorageError"
}

TerminalStates == {"Persisted", "DBError", "StorageError"}

(* --algorithm GWT0024WriteResult

variables
    current_state       = "JobRunning",
    job_outcome         = "NONE",
    attempts            = 0,
    error_msg           = "none",
    db_written          = FALSE,
    storage_uploaded    = FALSE,
    local_written       = FALSE,
    write_result_called = FALSE,
    step_count          = 0;

define

    TypeInvariant ==
        /\ current_state       \in States
        /\ job_outcome         \in (JobOutcomes \union {"NONE"})
        /\ attempts            \in Nat
        /\ db_written          \in BOOLEAN
        /\ storage_uploaded    \in BOOLEAN
        /\ local_written       \in BOOLEAN
        /\ write_result_called \in BOOLEAN

    ValidState == current_state \in States

    BoundedExecution == step_count <= MaxSteps

    NoLocalWrite == local_written = FALSE

    PersistenceConsistency ==
        current_state = "Persisted" =>
            (db_written = TRUE /\ storage_uploaded = TRUE)

    DBWriteRequiresOutcome ==
        db_written = TRUE => job_outcome \in JobOutcomes

    StorageRequiresDB ==
        storage_uploaded = TRUE => db_written = TRUE

    WriteCalledRequiresOutcome ==
        write_result_called = TRUE => job_outcome \in JobOutcomes

    HostedReplacement ==
        write_result_called = TRUE => local_written = FALSE

    OrderingConsistency ==
        storage_uploaded = TRUE => write_result_called = TRUE

end define;

fair process WriteResultWorker = "worker"
begin
    CompleteJob:
        either
            job_outcome := "PASS";
            error_msg   := "none";
        or
            job_outcome := "FAIL";
            error_msg   := "test_failure";
        or
            job_outcome := "MAX_RETRIES";
            error_msg   := "max_retries_exhausted";
        end either;
        attempts      := MaxAttempts;
        current_state := "JobComplete";
        step_count    := step_count + 1;

    CallWriteResult:
        write_result_called := TRUE;
        current_state       := "WritingDB";
        step_count          := step_count + 1;

    WriteDB:
        either
            db_written    := TRUE;
            current_state := "UploadingLogs";
        or
            error_msg     := "db_write_failed";
            current_state := "DBError";
        end either;
        step_count := step_count + 1;

    CheckDB:
        if current_state = "DBError" then
            goto Finish;
        end if;

    UploadLogs:
        either
            storage_uploaded := TRUE;
            current_state    := "Persisted";
        or
            error_msg     := "storage_upload_failed";
            current_state := "StorageError";
        end either;
        step_count := step_count + 1;

    Finish:
        assert current_state \in TerminalStates;
        assert local_written = FALSE;
        assert write_result_called = TRUE => job_outcome \in JobOutcomes;
        assert current_state = "Persisted" =>
                   (db_written = TRUE /\ storage_uploaded = TRUE);
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "49033b77" /\ chksum(tla) = "898a4864")
VARIABLES pc, current_state, job_outcome, attempts, error_msg, db_written, 
          storage_uploaded, local_written, write_result_called, step_count

(* define statement *)
TypeInvariant ==
    /\ current_state       \in States
    /\ job_outcome         \in (JobOutcomes \union {"NONE"})
    /\ attempts            \in Nat
    /\ db_written          \in BOOLEAN
    /\ storage_uploaded    \in BOOLEAN
    /\ local_written       \in BOOLEAN
    /\ write_result_called \in BOOLEAN

ValidState == current_state \in States

BoundedExecution == step_count <= MaxSteps

NoLocalWrite == local_written = FALSE

PersistenceConsistency ==
    current_state = "Persisted" =>
        (db_written = TRUE /\ storage_uploaded = TRUE)

DBWriteRequiresOutcome ==
    db_written = TRUE => job_outcome \in JobOutcomes

StorageRequiresDB ==
    storage_uploaded = TRUE => db_written = TRUE

WriteCalledRequiresOutcome ==
    write_result_called = TRUE => job_outcome \in JobOutcomes

HostedReplacement ==
    write_result_called = TRUE => local_written = FALSE

OrderingConsistency ==
    storage_uploaded = TRUE => write_result_called = TRUE


vars == << pc, current_state, job_outcome, attempts, error_msg, db_written, 
           storage_uploaded, local_written, write_result_called, step_count
        >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ current_state = "JobRunning"
        /\ job_outcome = "NONE"
        /\ attempts = 0
        /\ error_msg = "none"
        /\ db_written = FALSE
        /\ storage_uploaded = FALSE
        /\ local_written = FALSE
        /\ write_result_called = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "CompleteJob"]

CompleteJob == /\ pc["worker"] = "CompleteJob"
               /\ \/ /\ job_outcome' = "PASS"
                     /\ error_msg' = "none"
                  \/ /\ job_outcome' = "FAIL"
                     /\ error_msg' = "test_failure"
                  \/ /\ job_outcome' = "MAX_RETRIES"
                     /\ error_msg' = "max_retries_exhausted"
               /\ attempts' = MaxAttempts
               /\ current_state' = "JobComplete"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["worker"] = "CallWriteResult"]
               /\ UNCHANGED << db_written, storage_uploaded, local_written, 
                               write_result_called >>

CallWriteResult == /\ pc["worker"] = "CallWriteResult"
                   /\ write_result_called' = TRUE
                   /\ current_state' = "WritingDB"
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["worker"] = "WriteDB"]
                   /\ UNCHANGED << job_outcome, attempts, error_msg, 
                                   db_written, storage_uploaded, local_written >>

WriteDB == /\ pc["worker"] = "WriteDB"
           /\ \/ /\ db_written' = TRUE
                 /\ current_state' = "UploadingLogs"
                 /\ UNCHANGED error_msg
              \/ /\ error_msg' = "db_write_failed"
                 /\ current_state' = "DBError"
                 /\ UNCHANGED db_written
           /\ step_count' = step_count + 1
           /\ pc' = [pc EXCEPT !["worker"] = "CheckDB"]
           /\ UNCHANGED << job_outcome, attempts, storage_uploaded, 
                           local_written, write_result_called >>

CheckDB == /\ pc["worker"] = "CheckDB"
           /\ IF current_state = "DBError"
                 THEN /\ pc' = [pc EXCEPT !["worker"] = "Finish"]
                 ELSE /\ pc' = [pc EXCEPT !["worker"] = "UploadLogs"]
           /\ UNCHANGED << current_state, job_outcome, attempts, error_msg, 
                           db_written, storage_uploaded, local_written, 
                           write_result_called, step_count >>

UploadLogs == /\ pc["worker"] = "UploadLogs"
              /\ \/ /\ storage_uploaded' = TRUE
                    /\ current_state' = "Persisted"
                    /\ UNCHANGED error_msg
                 \/ /\ error_msg' = "storage_upload_failed"
                    /\ current_state' = "StorageError"
                    /\ UNCHANGED storage_uploaded
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["worker"] = "Finish"]
              /\ UNCHANGED << job_outcome, attempts, db_written, local_written, 
                              write_result_called >>

Finish == /\ pc["worker"] = "Finish"
          /\ Assert(current_state \in TerminalStates, 
                    "Failure of assertion at line 138, column 9.")
          /\ Assert(local_written = FALSE, 
                    "Failure of assertion at line 139, column 9.")
          /\ Assert(write_result_called = TRUE => job_outcome \in JobOutcomes, 
                    "Failure of assertion at line 140, column 9.")
          /\ Assert(current_state = "Persisted" =>
                        (db_written = TRUE /\ storage_uploaded = TRUE), 
                    "Failure of assertion at line 141, column 9.")
          /\ TRUE
          /\ pc' = [pc EXCEPT !["worker"] = "Done"]
          /\ UNCHANGED << current_state, job_outcome, attempts, error_msg, 
                          db_written, storage_uploaded, local_written, 
                          write_result_called, step_count >>

WriteResultWorker == CompleteJob \/ CallWriteResult \/ WriteDB \/ CheckDB
                        \/ UploadLogs \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == WriteResultWorker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(WriteResultWorker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
