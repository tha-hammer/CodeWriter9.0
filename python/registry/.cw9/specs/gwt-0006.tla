------------------------ MODULE GWT0006_SafeDisconnect ------------------------

EXTENDS Integers, Sequences, TLC

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

(*
 * Models the lifecycle of a ClaudeSDKClient within a loop job:
 *   1. Client is created via _make_client() at job start.
 *   2. A retry loop runs, exiting via PASS, FAIL, or max_retries exhausted.
 *   3. A finally block always calls safe_disconnect() before the worker exits.
 *
 * Primary safety property (SafeDisconnectGuarantee):
 *   If the worker has exited, the client must be disconnected.
 *
 * Primary liveness property (EventuallyDisconnected):
 *   The worker always eventually reaches the Exited state with no session.
 *)

(* --algorithm SafeDisconnect

variables
    client_state    = "none",
    loop_outcome    = "none",
    retry_count     = 0,
    finally_entered = FALSE,
    worker_exited   = FALSE,
    session_active  = FALSE;

define

    ClientStates == {"none", "connected", "disconnected"}
    LoopOutcomes == {"none", "pass", "fail", "exhausted"}

    ClientValid ==
        client_state \in ClientStates

    OutcomeValid ==
        loop_outcome \in LoopOutcomes

    RetryBounded ==
        retry_count <= MaxRetries

    SafeDisconnectGuarantee ==
        worker_exited => (client_state = "disconnected" /\ ~session_active)

    FinallyAlwaysEntered ==
        worker_exited => finally_entered

    NoSessionAfterExit ==
        worker_exited => ~session_active

    TypeInvariant ==
        /\ ClientValid
        /\ OutcomeValid
        /\ RetryBounded
        /\ finally_entered \in BOOLEAN
        /\ worker_exited   \in BOOLEAN
        /\ session_active  \in BOOLEAN

end define;

fair process worker = "main"
begin

    MakeClient:
        client_state   := "connected";
        session_active := TRUE;
        retry_count    := 0;
        loop_outcome   := "none";

    RetryLoop:
        while loop_outcome = "none" do
            either
                PassBranch:
                    loop_outcome := "pass";
            or
                FailBranch:
                    loop_outcome := "fail";
            or
                ExhaustCheck:
                    if retry_count < MaxRetries then
                        retry_count := retry_count + 1;
                    else
                        loop_outcome := "exhausted";
                    end if;
            end either;
        end while;

    FinallyBlock:
        finally_entered := TRUE;

    SafeDisconnectCall:
        client_state   := "disconnected";
        session_active := FALSE;

    WorkerExit:
        worker_exited := TRUE;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8ce5d662" /\ chksum(tla) = "32fa2f19")
VARIABLES pc, client_state, loop_outcome, retry_count, finally_entered, 
          worker_exited, session_active

(* define statement *)
ClientStates == {"none", "connected", "disconnected"}
LoopOutcomes == {"none", "pass", "fail", "exhausted"}

ClientValid ==
    client_state \in ClientStates

OutcomeValid ==
    loop_outcome \in LoopOutcomes

RetryBounded ==
    retry_count <= MaxRetries

SafeDisconnectGuarantee ==
    worker_exited => (client_state = "disconnected" /\ ~session_active)

FinallyAlwaysEntered ==
    worker_exited => finally_entered

NoSessionAfterExit ==
    worker_exited => ~session_active

TypeInvariant ==
    /\ ClientValid
    /\ OutcomeValid
    /\ RetryBounded
    /\ finally_entered \in BOOLEAN
    /\ worker_exited   \in BOOLEAN
    /\ session_active  \in BOOLEAN


vars == << pc, client_state, loop_outcome, retry_count, finally_entered, 
           worker_exited, session_active >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ client_state = "none"
        /\ loop_outcome = "none"
        /\ retry_count = 0
        /\ finally_entered = FALSE
        /\ worker_exited = FALSE
        /\ session_active = FALSE
        /\ pc = [self \in ProcSet |-> "MakeClient"]

MakeClient == /\ pc["main"] = "MakeClient"
              /\ client_state' = "connected"
              /\ session_active' = TRUE
              /\ retry_count' = 0
              /\ loop_outcome' = "none"
              /\ pc' = [pc EXCEPT !["main"] = "RetryLoop"]
              /\ UNCHANGED << finally_entered, worker_exited >>

RetryLoop == /\ pc["main"] = "RetryLoop"
             /\ IF loop_outcome = "none"
                   THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "PassBranch"]
                           \/ /\ pc' = [pc EXCEPT !["main"] = "FailBranch"]
                           \/ /\ pc' = [pc EXCEPT !["main"] = "ExhaustCheck"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "FinallyBlock"]
             /\ UNCHANGED << client_state, loop_outcome, retry_count, 
                             finally_entered, worker_exited, session_active >>

PassBranch == /\ pc["main"] = "PassBranch"
              /\ loop_outcome' = "pass"
              /\ pc' = [pc EXCEPT !["main"] = "RetryLoop"]
              /\ UNCHANGED << client_state, retry_count, finally_entered, 
                              worker_exited, session_active >>

FailBranch == /\ pc["main"] = "FailBranch"
              /\ loop_outcome' = "fail"
              /\ pc' = [pc EXCEPT !["main"] = "RetryLoop"]
              /\ UNCHANGED << client_state, retry_count, finally_entered, 
                              worker_exited, session_active >>

ExhaustCheck == /\ pc["main"] = "ExhaustCheck"
                /\ IF retry_count < MaxRetries
                      THEN /\ retry_count' = retry_count + 1
                           /\ UNCHANGED loop_outcome
                      ELSE /\ loop_outcome' = "exhausted"
                           /\ UNCHANGED retry_count
                /\ pc' = [pc EXCEPT !["main"] = "RetryLoop"]
                /\ UNCHANGED << client_state, finally_entered, worker_exited, 
                                session_active >>

FinallyBlock == /\ pc["main"] = "FinallyBlock"
                /\ finally_entered' = TRUE
                /\ pc' = [pc EXCEPT !["main"] = "SafeDisconnectCall"]
                /\ UNCHANGED << client_state, loop_outcome, retry_count, 
                                worker_exited, session_active >>

SafeDisconnectCall == /\ pc["main"] = "SafeDisconnectCall"
                      /\ client_state' = "disconnected"
                      /\ session_active' = FALSE
                      /\ pc' = [pc EXCEPT !["main"] = "WorkerExit"]
                      /\ UNCHANGED << loop_outcome, retry_count, 
                                      finally_entered, worker_exited >>

WorkerExit == /\ pc["main"] = "WorkerExit"
              /\ worker_exited' = TRUE
              /\ pc' = [pc EXCEPT !["main"] = "Finish"]
              /\ UNCHANGED << client_state, loop_outcome, retry_count, 
                              finally_entered, session_active >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << client_state, loop_outcome, retry_count, 
                          finally_entered, worker_exited, session_active >>

worker == MakeClient \/ RetryLoop \/ PassBranch \/ FailBranch
             \/ ExhaustCheck \/ FinallyBlock \/ SafeDisconnectCall
             \/ WorkerExit \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

================================================================================
