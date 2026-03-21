---- MODULE GracefulShutdown ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Tasks

ASSUME Tasks # {} /\ IsFiniteSet(Tasks)

(*--algorithm GracefulShutdown

variables
    shutdown_requested   = FALSE,
    in_flight            = {},
    completed            = {},
    started_after_signal = {},
    in_flight_at_signal  = {},
    pending              = Tasks,
    run_active           = TRUE;

define

    TypeOK ==
        /\ shutdown_requested   \in BOOLEAN
        /\ in_flight            \subseteq Tasks
        /\ completed            \subseteq Tasks
        /\ started_after_signal \subseteq Tasks
        /\ in_flight_at_signal  \subseteq Tasks
        /\ pending              \subseteq Tasks
        /\ run_active           \in BOOLEAN

    NoNewAfterShutdown ==
        shutdown_requested => started_after_signal = {}

    InFlightDoesNotGrow ==
        shutdown_requested => in_flight \subseteq in_flight_at_signal

    InFlightCompletes ==
        ~run_active => in_flight = {}

    CompletedSubsetTasks ==
        completed \subseteq Tasks

    Partitioned ==
        /\ (in_flight \intersect completed) = {}
        /\ (pending   \intersect completed) = {}
        /\ (pending   \intersect in_flight) = {}

end define;

fair process signal_handler = "signal"
begin
    FireSignal:
        either
            shutdown_requested  := TRUE;
            in_flight_at_signal := in_flight;
        or
            skip;
        end either;
end process;

fair process orchestrator = "orchestrator"
variables
    phase     = "running",
    candidate = "none";
begin
    OrchestratorLoop:
        while phase = "running" do
            either
                await ~shutdown_requested /\ pending # {};
                with t \in pending do
                    candidate := t;
                    pending   := pending \ {t};
                end with;
            StartOrAbort:
                if ~shutdown_requested then
                    in_flight := in_flight \union {candidate};
                else
                    pending := pending \union {candidate};
                end if;
                candidate := "none";
            or
                await shutdown_requested \/ pending = {};
                phase := "draining";
            end either;
        end while;
    DrainInflight:
        await in_flight = {};
    OrchestratorDone:
        run_active := FALSE;
end process;

fair process completer = "completer"
begin
    WaitForWork:
        await in_flight # {} \/ ~run_active;
    CheckWork:
        if in_flight # {} then
            with t \in in_flight do
                in_flight := in_flight \ {t};
                completed := completed \union {t};
            end with;
            goto WaitForWork;
        end if;
    CompleterFinish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "a6c64a0b" /\ chksum(tla) = "bf4e92d0")
VARIABLES pc, shutdown_requested, in_flight, completed, started_after_signal, 
          in_flight_at_signal, pending, run_active

(* define statement *)
TypeOK ==
    /\ shutdown_requested   \in BOOLEAN
    /\ in_flight            \subseteq Tasks
    /\ completed            \subseteq Tasks
    /\ started_after_signal \subseteq Tasks
    /\ in_flight_at_signal  \subseteq Tasks
    /\ pending              \subseteq Tasks
    /\ run_active           \in BOOLEAN

NoNewAfterShutdown ==
    shutdown_requested => started_after_signal = {}

InFlightDoesNotGrow ==
    shutdown_requested => in_flight \subseteq in_flight_at_signal

InFlightCompletes ==
    ~run_active => in_flight = {}

CompletedSubsetTasks ==
    completed \subseteq Tasks

Partitioned ==
    /\ (in_flight \intersect completed) = {}
    /\ (pending   \intersect completed) = {}
    /\ (pending   \intersect in_flight) = {}

VARIABLES phase, candidate

vars == << pc, shutdown_requested, in_flight, completed, started_after_signal, 
           in_flight_at_signal, pending, run_active, phase, candidate >>

ProcSet == {"signal"} \cup {"orchestrator"} \cup {"completer"}

Init == (* Global variables *)
        /\ shutdown_requested = FALSE
        /\ in_flight = {}
        /\ completed = {}
        /\ started_after_signal = {}
        /\ in_flight_at_signal = {}
        /\ pending = Tasks
        /\ run_active = TRUE
        (* Process orchestrator *)
        /\ phase = "running"
        /\ candidate = "none"
        /\ pc = [self \in ProcSet |-> CASE self = "signal" -> "FireSignal"
                                        [] self = "orchestrator" -> "OrchestratorLoop"
                                        [] self = "completer" -> "WaitForWork"]

FireSignal == /\ pc["signal"] = "FireSignal"
              /\ \/ /\ shutdown_requested' = TRUE
                    /\ in_flight_at_signal' = in_flight
                 \/ /\ TRUE
                    /\ UNCHANGED <<shutdown_requested, in_flight_at_signal>>
              /\ pc' = [pc EXCEPT !["signal"] = "Done"]
              /\ UNCHANGED << in_flight, completed, started_after_signal, 
                              pending, run_active, phase, candidate >>

signal_handler == FireSignal

OrchestratorLoop == /\ pc["orchestrator"] = "OrchestratorLoop"
                    /\ IF phase = "running"
                          THEN /\ \/ /\ ~shutdown_requested /\ pending # {}
                                     /\ \E t \in pending:
                                          /\ candidate' = t
                                          /\ pending' = pending \ {t}
                                     /\ pc' = [pc EXCEPT !["orchestrator"] = "StartOrAbort"]
                                     /\ phase' = phase
                                  \/ /\ shutdown_requested \/ pending = {}
                                     /\ phase' = "draining"
                                     /\ pc' = [pc EXCEPT !["orchestrator"] = "OrchestratorLoop"]
                                     /\ UNCHANGED <<pending, candidate>>
                          ELSE /\ pc' = [pc EXCEPT !["orchestrator"] = "DrainInflight"]
                               /\ UNCHANGED << pending, phase, candidate >>
                    /\ UNCHANGED << shutdown_requested, in_flight, completed, 
                                    started_after_signal, in_flight_at_signal, 
                                    run_active >>

StartOrAbort == /\ pc["orchestrator"] = "StartOrAbort"
                /\ IF ~shutdown_requested
                      THEN /\ in_flight' = (in_flight \union {candidate})
                           /\ UNCHANGED pending
                      ELSE /\ pending' = (pending \union {candidate})
                           /\ UNCHANGED in_flight
                /\ candidate' = "none"
                /\ pc' = [pc EXCEPT !["orchestrator"] = "OrchestratorLoop"]
                /\ UNCHANGED << shutdown_requested, completed, 
                                started_after_signal, in_flight_at_signal, 
                                run_active, phase >>

DrainInflight == /\ pc["orchestrator"] = "DrainInflight"
                 /\ in_flight = {}
                 /\ pc' = [pc EXCEPT !["orchestrator"] = "OrchestratorDone"]
                 /\ UNCHANGED << shutdown_requested, in_flight, completed, 
                                 started_after_signal, in_flight_at_signal, 
                                 pending, run_active, phase, candidate >>

OrchestratorDone == /\ pc["orchestrator"] = "OrchestratorDone"
                    /\ run_active' = FALSE
                    /\ pc' = [pc EXCEPT !["orchestrator"] = "Done"]
                    /\ UNCHANGED << shutdown_requested, in_flight, completed, 
                                    started_after_signal, in_flight_at_signal, 
                                    pending, phase, candidate >>

orchestrator == OrchestratorLoop \/ StartOrAbort \/ DrainInflight
                   \/ OrchestratorDone

WaitForWork == /\ pc["completer"] = "WaitForWork"
               /\ in_flight # {} \/ ~run_active
               /\ pc' = [pc EXCEPT !["completer"] = "CheckWork"]
               /\ UNCHANGED << shutdown_requested, in_flight, completed, 
                               started_after_signal, in_flight_at_signal, 
                               pending, run_active, phase, candidate >>

CheckWork == /\ pc["completer"] = "CheckWork"
             /\ IF in_flight # {}
                   THEN /\ \E t \in in_flight:
                             /\ in_flight' = in_flight \ {t}
                             /\ completed' = (completed \union {t})
                        /\ pc' = [pc EXCEPT !["completer"] = "WaitForWork"]
                   ELSE /\ pc' = [pc EXCEPT !["completer"] = "CompleterFinish"]
                        /\ UNCHANGED << in_flight, completed >>
             /\ UNCHANGED << shutdown_requested, started_after_signal, 
                             in_flight_at_signal, pending, run_active, phase, 
                             candidate >>

CompleterFinish == /\ pc["completer"] = "CompleterFinish"
                   /\ TRUE
                   /\ pc' = [pc EXCEPT !["completer"] = "Done"]
                   /\ UNCHANGED << shutdown_requested, in_flight, completed, 
                                   started_after_signal, in_flight_at_signal, 
                                   pending, run_active, phase, candidate >>

completer == WaitForWork \/ CheckWork \/ CompleterFinish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == signal_handler \/ orchestrator \/ completer
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(signal_handler)
        /\ WF_vars(orchestrator)
        /\ WF_vars(completer)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
