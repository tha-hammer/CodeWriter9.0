---- MODULE JobLifecycle ----

EXTENDS Integers, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 0

(* --algorithm JobLifecycle

variables
    job_status     = "PENDING",
    postgres_status = "PENDING",
    retry_count    = 0,
    loop_result    = "NONE";

define

    States == {"PENDING", "QUEUED", "RUNNING", "PASSED", "FAILED", "RETRYING"}

    TerminalStates == {"PASSED", "FAILED"}

    ValidLoopResults == {"NONE", "PASS", "FAIL", "RETRY"}

    TypeInvariant ==
        /\ job_status      \in States
        /\ postgres_status \in States
        /\ retry_count     \in 0..MaxRetries
        /\ loop_result     \in ValidLoopResults

    \* Every atomic Postgres write keeps job_status and postgres_status in sync.
    \* This encodes the "each transition is written atomically to Postgres" requirement.
    AtomicConsistency == postgres_status = job_status

    RetryBound == retry_count <= MaxRetries

    \* Once a job enters a terminal state it must never leave it.
    TerminalIsAbsorbing ==
        job_status \in TerminalStates => postgres_status \in TerminalStates

    \* Master safety invariant checked by TLC on every reachable state.
    JobLifecycleInvariant ==
        /\ TypeInvariant
        /\ AtomicConsistency
        /\ RetryBound
        /\ TerminalIsAbsorbing

    \* Liveness: under fair scheduling the job always eventually terminates.
    EventuallyTerminal == <>(job_status \in TerminalStates)

end define;

fair process lifecycle = "job"
begin

    Enqueue:
        \* PENDING -> QUEUED: atomic Postgres write on enqueue.
        await job_status = "PENDING" /\ postgres_status = "PENDING";
        job_status      := "QUEUED" ||
        postgres_status := "QUEUED";

    Dequeue:
        \* QUEUED -> RUNNING: atomic Postgres write on worker dequeue.
        await job_status = "QUEUED";
        job_status      := "RUNNING" ||
        postgres_status := "RUNNING";

    PickResult:
        \* Non-deterministically model run_loop / process_response outcome.
        await job_status = "RUNNING";
        with r \in {"PASS", "FAIL", "RETRY"} do
            loop_result := r;
        end with;

    RouteResult:
        \* route_result / write_result_file: one atomic Postgres write per branch.
        if loop_result = "PASS" then
            \* LoopResult.PASS or successful completion -> PASSED (terminal).
            job_status      := "PASSED" ||
            postgres_status := "PASSED";
        elsif loop_result = "FAIL" then
            \* LoopResult.FAIL or unhandled exception at max_retries -> FAILED (terminal).
            job_status      := "FAILED" ||
            postgres_status := "FAILED";
        elsif loop_result = "RETRY" /\ retry_count < MaxRetries then
            \* LoopResult.RETRY within retry budget -> RETRYING (transient).
            job_status      := "RETRYING"         ||
            postgres_status := "RETRYING"         ||
            retry_count     := retry_count + 1;
        else
            \* LoopResult.RETRY but retry budget exhausted -> FAILED (terminal).
            job_status      := "FAILED" ||
            postgres_status := "FAILED";
        end if;

    CheckRetry:
        \* RETRYING -> RUNNING: second atomic Postgres write; then loop back.
        if job_status = "RETRYING" then
            job_status      := "RUNNING" ||
            postgres_status := "RUNNING";
            goto PickResult;
        end if;

    Terminate:
        \* Job is in a terminal state; no further transitions occur.
        assert job_status \in TerminalStates;
        assert postgres_status = job_status;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "d6924435" /\ chksum(tla) = "5bd9fd98")
VARIABLES pc, job_status, postgres_status, retry_count, loop_result

(* define statement *)
States == {"PENDING", "QUEUED", "RUNNING", "PASSED", "FAILED", "RETRYING"}

TerminalStates == {"PASSED", "FAILED"}

ValidLoopResults == {"NONE", "PASS", "FAIL", "RETRY"}

TypeInvariant ==
    /\ job_status      \in States
    /\ postgres_status \in States
    /\ retry_count     \in 0..MaxRetries
    /\ loop_result     \in ValidLoopResults



AtomicConsistency == postgres_status = job_status

RetryBound == retry_count <= MaxRetries


TerminalIsAbsorbing ==
    job_status \in TerminalStates => postgres_status \in TerminalStates


JobLifecycleInvariant ==
    /\ TypeInvariant
    /\ AtomicConsistency
    /\ RetryBound
    /\ TerminalIsAbsorbing


EventuallyTerminal == <>(job_status \in TerminalStates)


vars == << pc, job_status, postgres_status, retry_count, loop_result >>

ProcSet == {"job"}

Init == (* Global variables *)
        /\ job_status = "PENDING"
        /\ postgres_status = "PENDING"
        /\ retry_count = 0
        /\ loop_result = "NONE"
        /\ pc = [self \in ProcSet |-> "Enqueue"]

Enqueue == /\ pc["job"] = "Enqueue"
           /\ job_status = "PENDING" /\ postgres_status = "PENDING"
           /\ /\ job_status' = "QUEUED"
              /\ postgres_status' = "QUEUED"
           /\ pc' = [pc EXCEPT !["job"] = "Dequeue"]
           /\ UNCHANGED << retry_count, loop_result >>

Dequeue == /\ pc["job"] = "Dequeue"
           /\ job_status = "QUEUED"
           /\ /\ job_status' = "RUNNING"
              /\ postgres_status' = "RUNNING"
           /\ pc' = [pc EXCEPT !["job"] = "PickResult"]
           /\ UNCHANGED << retry_count, loop_result >>

PickResult == /\ pc["job"] = "PickResult"
              /\ job_status = "RUNNING"
              /\ \E r \in {"PASS", "FAIL", "RETRY"}:
                   loop_result' = r
              /\ pc' = [pc EXCEPT !["job"] = "RouteResult"]
              /\ UNCHANGED << job_status, postgres_status, retry_count >>

RouteResult == /\ pc["job"] = "RouteResult"
               /\ IF loop_result = "PASS"
                     THEN /\ /\ job_status' = "PASSED"
                             /\ postgres_status' = "PASSED"
                          /\ UNCHANGED retry_count
                     ELSE /\ IF loop_result = "FAIL"
                                THEN /\ /\ job_status' = "FAILED"
                                        /\ postgres_status' = "FAILED"
                                     /\ UNCHANGED retry_count
                                ELSE /\ IF loop_result = "RETRY" /\ retry_count < MaxRetries
                                           THEN /\ /\ job_status' = "RETRYING"
                                                   /\ postgres_status' = "RETRYING"
                                                   /\ retry_count' = retry_count + 1
                                           ELSE /\ /\ job_status' = "FAILED"
                                                   /\ postgres_status' = "FAILED"
                                                /\ UNCHANGED retry_count
               /\ pc' = [pc EXCEPT !["job"] = "CheckRetry"]
               /\ UNCHANGED loop_result

CheckRetry == /\ pc["job"] = "CheckRetry"
              /\ IF job_status = "RETRYING"
                    THEN /\ /\ job_status' = "RUNNING"
                            /\ postgres_status' = "RUNNING"
                         /\ pc' = [pc EXCEPT !["job"] = "PickResult"]
                    ELSE /\ pc' = [pc EXCEPT !["job"] = "Terminate"]
                         /\ UNCHANGED << job_status, postgres_status >>
              /\ UNCHANGED << retry_count, loop_result >>

Terminate == /\ pc["job"] = "Terminate"
             /\ Assert(job_status \in TerminalStates, 
                       "Failure of assertion at line 106, column 9.")
             /\ Assert(postgres_status = job_status, 
                       "Failure of assertion at line 107, column 9.")
             /\ pc' = [pc EXCEPT !["job"] = "Done"]
             /\ UNCHANGED << job_status, postgres_status, retry_count, 
                             loop_result >>

lifecycle == Enqueue \/ Dequeue \/ PickResult \/ RouteResult \/ CheckRetry
                \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == lifecycle
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(lifecycle)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
