---- MODULE gwt_0011_SimTraceUpload ----

EXTENDS Integers, TLC

CONSTANTS
    GWT_ID,
    MaxSteps

SIM_TIMEOUT_LIMIT == 300

States == {
    "AwaitResult",
    "PassReceived",
    "Simulating",
    "TracesWritten",
    "UploadBatched",
    "ContainerExit",
    "NonPassTerminated"
}

TerminalStates == {"ContainerExit", "NonPassTerminated"}

(* --algorithm gwt_0011_SimTraceUpload

variables
    loop_result        = "NONE",
    tla_file_available = FALSE,
    current_state      = "AwaitResult",
    simulate_called    = FALSE,
    simulate_timeout   = 0,
    traces_written     = FALSE,
    traces_file        = "NONE",
    upload_batch       = {},
    step_count         = 0;

define

    SimTracesFile == <<GWT_ID, "sim_traces_json">>

    TypeInvariant ==
        /\ loop_result        \in {"NONE", "PASS", "FAIL"}
        /\ tla_file_available \in BOOLEAN
        /\ current_state      \in States
        /\ simulate_called    \in BOOLEAN
        /\ simulate_timeout   \in 0..SIM_TIMEOUT_LIMIT
        /\ traces_written     \in BOOLEAN

    ValidState == current_state \in States

    BoundedExecution == step_count <= MaxSteps

    SimTimeoutBounded ==
        simulate_called => simulate_timeout <= SIM_TIMEOUT_LIMIT

    SimCalledOnlyAfterPass ==
        simulate_called => loop_result = "PASS"

    TlaFilePresentWhenSimCalled ==
        simulate_called => tla_file_available

    TracesWrittenImpliesSimCalled ==
        traces_written => simulate_called

    TracesFileCorrect ==
        traces_written => traces_file = SimTracesFile

    UploadBatchContainsTraces ==
        current_state \in {"UploadBatched", "ContainerExit"} =>
            traces_file \in upload_batch

    ContainerExitSafety ==
        current_state = "ContainerExit" =>
            /\ simulate_called
            /\ simulate_timeout <= SIM_TIMEOUT_LIMIT
            /\ traces_written
            /\ traces_file = SimTracesFile
            /\ traces_file \in upload_batch

    NonPassSkipsSimulation ==
        current_state = "NonPassTerminated" => ~simulate_called

    OrderingGuarantee ==
        traces_file \in upload_batch =>
            /\ traces_written
            /\ simulate_called

end define;

fair process runner = "run_loop"
begin
    ReceiveResult:
        either
            loop_result        := "PASS";
            tla_file_available := TRUE;
            current_state      := "PassReceived";
        or
            loop_result   := "FAIL";
            current_state := "NonPassTerminated";
        end either;
        step_count := step_count + 1;

    RunSimulation:
        if current_state = "PassReceived" /\ tla_file_available then
            simulate_called  := TRUE;
            simulate_timeout := SIM_TIMEOUT_LIMIT;
            current_state    := "Simulating";
            step_count       := step_count + 1;
        end if;

    WriteTraces:
        if current_state = "Simulating" then
            traces_written := TRUE;
            traces_file    := SimTracesFile;
            current_state  := "TracesWritten";
            step_count     := step_count + 1;
        end if;

    AddToUploadBatch:
        if current_state = "TracesWritten" then
            upload_batch  := upload_batch \union {traces_file};
            current_state := "UploadBatched";
            step_count    := step_count + 1;
        end if;

    ExitContainer:
        if current_state = "UploadBatched" then
            current_state := "ContainerExit";
        elsif current_state \notin TerminalStates then
            current_state := "NonPassTerminated";
        end if;
        step_count := step_count + 1;

    Terminate:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "916cad99" /\ chksum(tla) = "15536aea")
VARIABLES pc, loop_result, tla_file_available, current_state, simulate_called, 
          simulate_timeout, traces_written, traces_file, upload_batch, 
          step_count

(* define statement *)
SimTracesFile == <<GWT_ID, "sim_traces_json">>

TypeInvariant ==
    /\ loop_result        \in {"NONE", "PASS", "FAIL"}
    /\ tla_file_available \in BOOLEAN
    /\ current_state      \in States
    /\ simulate_called    \in BOOLEAN
    /\ simulate_timeout   \in 0..SIM_TIMEOUT_LIMIT
    /\ traces_written     \in BOOLEAN

ValidState == current_state \in States

BoundedExecution == step_count <= MaxSteps

SimTimeoutBounded ==
    simulate_called => simulate_timeout <= SIM_TIMEOUT_LIMIT

SimCalledOnlyAfterPass ==
    simulate_called => loop_result = "PASS"

TlaFilePresentWhenSimCalled ==
    simulate_called => tla_file_available

TracesWrittenImpliesSimCalled ==
    traces_written => simulate_called

TracesFileCorrect ==
    traces_written => traces_file = SimTracesFile

UploadBatchContainsTraces ==
    current_state \in {"UploadBatched", "ContainerExit"} =>
        traces_file \in upload_batch

ContainerExitSafety ==
    current_state = "ContainerExit" =>
        /\ simulate_called
        /\ simulate_timeout <= SIM_TIMEOUT_LIMIT
        /\ traces_written
        /\ traces_file = SimTracesFile
        /\ traces_file \in upload_batch

NonPassSkipsSimulation ==
    current_state = "NonPassTerminated" => ~simulate_called

OrderingGuarantee ==
    traces_file \in upload_batch =>
        /\ traces_written
        /\ simulate_called


vars == << pc, loop_result, tla_file_available, current_state, 
           simulate_called, simulate_timeout, traces_written, traces_file, 
           upload_batch, step_count >>

ProcSet == {"run_loop"}

Init == (* Global variables *)
        /\ loop_result = "NONE"
        /\ tla_file_available = FALSE
        /\ current_state = "AwaitResult"
        /\ simulate_called = FALSE
        /\ simulate_timeout = 0
        /\ traces_written = FALSE
        /\ traces_file = "NONE"
        /\ upload_batch = {}
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "ReceiveResult"]

ReceiveResult == /\ pc["run_loop"] = "ReceiveResult"
                 /\ \/ /\ loop_result' = "PASS"
                       /\ tla_file_available' = TRUE
                       /\ current_state' = "PassReceived"
                    \/ /\ loop_result' = "FAIL"
                       /\ current_state' = "NonPassTerminated"
                       /\ UNCHANGED tla_file_available
                 /\ step_count' = step_count + 1
                 /\ pc' = [pc EXCEPT !["run_loop"] = "RunSimulation"]
                 /\ UNCHANGED << simulate_called, simulate_timeout, 
                                 traces_written, traces_file, upload_batch >>

RunSimulation == /\ pc["run_loop"] = "RunSimulation"
                 /\ IF current_state = "PassReceived" /\ tla_file_available
                       THEN /\ simulate_called' = TRUE
                            /\ simulate_timeout' = SIM_TIMEOUT_LIMIT
                            /\ current_state' = "Simulating"
                            /\ step_count' = step_count + 1
                       ELSE /\ TRUE
                            /\ UNCHANGED << current_state, simulate_called, 
                                            simulate_timeout, step_count >>
                 /\ pc' = [pc EXCEPT !["run_loop"] = "WriteTraces"]
                 /\ UNCHANGED << loop_result, tla_file_available, 
                                 traces_written, traces_file, upload_batch >>

WriteTraces == /\ pc["run_loop"] = "WriteTraces"
               /\ IF current_state = "Simulating"
                     THEN /\ traces_written' = TRUE
                          /\ traces_file' = SimTracesFile
                          /\ current_state' = "TracesWritten"
                          /\ step_count' = step_count + 1
                     ELSE /\ TRUE
                          /\ UNCHANGED << current_state, traces_written, 
                                          traces_file, step_count >>
               /\ pc' = [pc EXCEPT !["run_loop"] = "AddToUploadBatch"]
               /\ UNCHANGED << loop_result, tla_file_available, 
                               simulate_called, simulate_timeout, upload_batch >>

AddToUploadBatch == /\ pc["run_loop"] = "AddToUploadBatch"
                    /\ IF current_state = "TracesWritten"
                          THEN /\ upload_batch' = (upload_batch \union {traces_file})
                               /\ current_state' = "UploadBatched"
                               /\ step_count' = step_count + 1
                          ELSE /\ TRUE
                               /\ UNCHANGED << current_state, upload_batch, 
                                               step_count >>
                    /\ pc' = [pc EXCEPT !["run_loop"] = "ExitContainer"]
                    /\ UNCHANGED << loop_result, tla_file_available, 
                                    simulate_called, simulate_timeout, 
                                    traces_written, traces_file >>

ExitContainer == /\ pc["run_loop"] = "ExitContainer"
                 /\ IF current_state = "UploadBatched"
                       THEN /\ current_state' = "ContainerExit"
                       ELSE /\ IF current_state \notin TerminalStates
                                  THEN /\ current_state' = "NonPassTerminated"
                                  ELSE /\ TRUE
                                       /\ UNCHANGED current_state
                 /\ step_count' = step_count + 1
                 /\ pc' = [pc EXCEPT !["run_loop"] = "Terminate"]
                 /\ UNCHANGED << loop_result, tla_file_available, 
                                 simulate_called, simulate_timeout, 
                                 traces_written, traces_file, upload_batch >>

Terminate == /\ pc["run_loop"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["run_loop"] = "Done"]
             /\ UNCHANGED << loop_result, tla_file_available, current_state, 
                             simulate_called, simulate_timeout, traces_written, 
                             traces_file, upload_batch, step_count >>

runner == ReceiveResult \/ RunSimulation \/ WriteTraces \/ AddToUploadBatch
             \/ ExitContainer \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == runner
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(runner)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
