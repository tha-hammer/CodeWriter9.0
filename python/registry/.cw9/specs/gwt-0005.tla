---- MODULE GWT0005SingleClientReuse ----

EXTENDS Integers, Sequences, TLC

MAX_RETRIES == 8

(* --algorithm GWT0005SingleClientReuse

variables
    run_loop_started  = FALSE,
    make_client_calls = 0,
    client_handle     = "none",
    attempt_number    = 0,
    retry_count       = 0,
    succeeded         = FALSE,
    job_outcome       = "pending",
    conv_context      = <<>>,
    llm_result        = "none";

define

    TypeOK ==
        /\ run_loop_started  \in BOOLEAN
        /\ make_client_calls \in {0, 1}
        /\ client_handle     \in {"none", "sdk_client", "disconnected"}
        /\ attempt_number    \in 0..(MAX_RETRIES + 1)
        /\ retry_count       \in 0..(MAX_RETRIES + 1)
        /\ succeeded         \in BOOLEAN
        /\ job_outcome       \in {"pending", "success", "exhausted"}
        /\ llm_result        \in {"none", "ok", "fail"}

    AtMostOneClientCreated ==
        make_client_calls <= 1

    ClientHandleConsistent ==
        client_handle \in {"sdk_client", "disconnected"} => make_client_calls = 1

    SingleClientReusedForAllAttempts ==
        attempt_number > 1 => make_client_calls = 1

    RetriesBounded ==
        retry_count <= MAX_RETRIES + 1

    ContextGrowsWithAttempts ==
        Len(conv_context) <= attempt_number

    SuccessRequiresClient ==
        job_outcome = "success" =>
            client_handle \in {"sdk_client", "disconnected"}

    ExhaustionRequiresClient ==
        job_outcome = "exhausted" =>
            client_handle \in {"sdk_client", "disconnected"}

    JobTerminatedCorrectly ==
        job_outcome \notin {"success", "exhausted"} =>
            \/ ~run_loop_started
            \/ client_handle \in {"none", "sdk_client"}

end define;

fair process worker = "gwt_worker"
begin
    StartLoop:
        run_loop_started := TRUE;

    MakeClient:
        make_client_calls := make_client_calls + 1;
        client_handle     := "sdk_client";

    TryLoop:
        while ~succeeded /\ retry_count <= MAX_RETRIES do
            CallLLM:
                attempt_number := attempt_number + 1;
                either
                    llm_result := "ok";
                or
                    llm_result := "fail";
                end either;

            ProcessResponse:
                if llm_result = "ok" then
                    conv_context := Append(conv_context, attempt_number);
                    succeeded    := TRUE;
                    job_outcome  := "success";
                else
                    conv_context := Append(conv_context, attempt_number);
                    retry_count  := retry_count + 1;
                    llm_result   := "none";
                end if;
        end while;

    CheckExhausted:
        if ~succeeded then
            job_outcome := "exhausted";
        end if;

    Disconnect:
        client_handle := "disconnected";

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "abe862dd" /\ chksum(tla) = "f817269f")
VARIABLES pc, run_loop_started, make_client_calls, client_handle, 
          attempt_number, retry_count, succeeded, job_outcome, conv_context, 
          llm_result

(* define statement *)
TypeOK ==
    /\ run_loop_started  \in BOOLEAN
    /\ make_client_calls \in {0, 1}
    /\ client_handle     \in {"none", "sdk_client", "disconnected"}
    /\ attempt_number    \in 0..(MAX_RETRIES + 1)
    /\ retry_count       \in 0..(MAX_RETRIES + 1)
    /\ succeeded         \in BOOLEAN
    /\ job_outcome       \in {"pending", "success", "exhausted"}
    /\ llm_result        \in {"none", "ok", "fail"}

AtMostOneClientCreated ==
    make_client_calls <= 1

ClientHandleConsistent ==
    client_handle \in {"sdk_client", "disconnected"} => make_client_calls = 1

SingleClientReusedForAllAttempts ==
    attempt_number > 1 => make_client_calls = 1

RetriesBounded ==
    retry_count <= MAX_RETRIES + 1

ContextGrowsWithAttempts ==
    Len(conv_context) <= attempt_number

SuccessRequiresClient ==
    job_outcome = "success" =>
        client_handle \in {"sdk_client", "disconnected"}

ExhaustionRequiresClient ==
    job_outcome = "exhausted" =>
        client_handle \in {"sdk_client", "disconnected"}

JobTerminatedCorrectly ==
    job_outcome \notin {"success", "exhausted"} =>
        \/ ~run_loop_started
        \/ client_handle \in {"none", "sdk_client"}


vars == << pc, run_loop_started, make_client_calls, client_handle, 
           attempt_number, retry_count, succeeded, job_outcome, conv_context, 
           llm_result >>

ProcSet == {"gwt_worker"}

Init == (* Global variables *)
        /\ run_loop_started = FALSE
        /\ make_client_calls = 0
        /\ client_handle = "none"
        /\ attempt_number = 0
        /\ retry_count = 0
        /\ succeeded = FALSE
        /\ job_outcome = "pending"
        /\ conv_context = <<>>
        /\ llm_result = "none"
        /\ pc = [self \in ProcSet |-> "StartLoop"]

StartLoop == /\ pc["gwt_worker"] = "StartLoop"
             /\ run_loop_started' = TRUE
             /\ pc' = [pc EXCEPT !["gwt_worker"] = "MakeClient"]
             /\ UNCHANGED << make_client_calls, client_handle, attempt_number, 
                             retry_count, succeeded, job_outcome, conv_context, 
                             llm_result >>

MakeClient == /\ pc["gwt_worker"] = "MakeClient"
              /\ make_client_calls' = make_client_calls + 1
              /\ client_handle' = "sdk_client"
              /\ pc' = [pc EXCEPT !["gwt_worker"] = "TryLoop"]
              /\ UNCHANGED << run_loop_started, attempt_number, retry_count, 
                              succeeded, job_outcome, conv_context, llm_result >>

TryLoop == /\ pc["gwt_worker"] = "TryLoop"
           /\ IF ~succeeded /\ retry_count <= MAX_RETRIES
                 THEN /\ pc' = [pc EXCEPT !["gwt_worker"] = "CallLLM"]
                 ELSE /\ pc' = [pc EXCEPT !["gwt_worker"] = "CheckExhausted"]
           /\ UNCHANGED << run_loop_started, make_client_calls, client_handle, 
                           attempt_number, retry_count, succeeded, job_outcome, 
                           conv_context, llm_result >>

CallLLM == /\ pc["gwt_worker"] = "CallLLM"
           /\ attempt_number' = attempt_number + 1
           /\ \/ /\ llm_result' = "ok"
              \/ /\ llm_result' = "fail"
           /\ pc' = [pc EXCEPT !["gwt_worker"] = "ProcessResponse"]
           /\ UNCHANGED << run_loop_started, make_client_calls, client_handle, 
                           retry_count, succeeded, job_outcome, conv_context >>

ProcessResponse == /\ pc["gwt_worker"] = "ProcessResponse"
                   /\ IF llm_result = "ok"
                         THEN /\ conv_context' = Append(conv_context, attempt_number)
                              /\ succeeded' = TRUE
                              /\ job_outcome' = "success"
                              /\ UNCHANGED << retry_count, llm_result >>
                         ELSE /\ conv_context' = Append(conv_context, attempt_number)
                              /\ retry_count' = retry_count + 1
                              /\ llm_result' = "none"
                              /\ UNCHANGED << succeeded, job_outcome >>
                   /\ pc' = [pc EXCEPT !["gwt_worker"] = "TryLoop"]
                   /\ UNCHANGED << run_loop_started, make_client_calls, 
                                   client_handle, attempt_number >>

CheckExhausted == /\ pc["gwt_worker"] = "CheckExhausted"
                  /\ IF ~succeeded
                        THEN /\ job_outcome' = "exhausted"
                        ELSE /\ TRUE
                             /\ UNCHANGED job_outcome
                  /\ pc' = [pc EXCEPT !["gwt_worker"] = "Disconnect"]
                  /\ UNCHANGED << run_loop_started, make_client_calls, 
                                  client_handle, attempt_number, retry_count, 
                                  succeeded, conv_context, llm_result >>

Disconnect == /\ pc["gwt_worker"] = "Disconnect"
              /\ client_handle' = "disconnected"
              /\ pc' = [pc EXCEPT !["gwt_worker"] = "Finish"]
              /\ UNCHANGED << run_loop_started, make_client_calls, 
                              attempt_number, retry_count, succeeded, 
                              job_outcome, conv_context, llm_result >>

Finish == /\ pc["gwt_worker"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["gwt_worker"] = "Done"]
          /\ UNCHANGED << run_loop_started, make_client_calls, client_handle, 
                          attempt_number, retry_count, succeeded, job_outcome, 
                          conv_context, llm_result >>

worker == StartLoop \/ MakeClient \/ TryLoop \/ CallLLM \/ ProcessResponse
             \/ CheckExhausted \/ Disconnect \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

ClientCreatedExactlyOnce ==
    <>(make_client_calls = 1) /\ [](make_client_calls <= 1)

ClientReusedAcrossAllRetries ==
    [](attempt_number > 1 => make_client_calls = 1)

ConversationContextGrowsMonotonically ==
    [][Len(conv_context') >= Len(conv_context)]_conv_context

JobEventuallyTerminates ==
    <>(job_outcome \in {"success", "exhausted"})

====
