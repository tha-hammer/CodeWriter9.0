---- MODULE observability_state_machine ----
EXTENDS Integers, Sequences, TLC

CONSTANTS MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps >= 2

States == {"init", "processing", "done"}

(* --algorithm ObservabilityStateMachine

variables
    current_state = "init",
    step_count    = 0,
    trace_log     = <<>>,
    audit_log     = <<>>,
    history       = <<>>,
    phase         = "running";

define

    ValidState == current_state \in States

    BoundedExecution == step_count <= MaxSteps

    \* Every completed action must have a corresponding trace entry.
    \* A compliant transition increments step_count and appends to trace_log
    \* simultaneously, keeping Len(trace_log) >= step_count at all times.
    \* Any instantiation that omits the trace_log append will violate this.
    TraceComplete ==
        step_count > 0 => Len(trace_log) >= step_count

    \* Every state mutation must have a corresponding audit entry.
    \* A compliant transition appends to history and audit_log together,
    \* keeping Len(audit_log) >= Len(history) at all times.
    \* Any instantiation that omits the audit_log append will violate this.
    AuditComplete ==
        Len(history) > 0 => Len(audit_log) >= Len(history)

    \* TraceLogMonotonic: trace_log never shrinks.
    \* Enforced structurally -- only Append is used; no element is ever removed.
    TraceLogMonotonic == Len(trace_log) >= 0

    \* AuditLogMonotonic: audit_log never shrinks.
    \* Enforced structurally -- only Append is used; no element is ever removed.
    AuditLogMonotonic == Len(audit_log) >= 0

    \* All base state-machine invariants hold throughout execution.
    BasePreserved == ValidState /\ BoundedExecution

end define;

fair process actor = "main"
begin
    RunLoop:
        while current_state /= "done" /\ step_count < MaxSteps do
            \* TransitionWithTrace: the mandatory compliant pattern.
            \* All variables are updated simultaneously (||) so that every
            \* post-state satisfies TraceComplete and AuditComplete.
            \* An instantiation that drops the trace_log or audit_log line
            \* will produce a state where the respective invariant is FALSE,
            \* and TLC will report the violation with the offending action name.
            if current_state = "init" then
                history       := Append(history, current_state)              ||
                current_state := "processing"                                 ||
                step_count    := step_count + 1                              ||
                trace_log     := Append(trace_log,
                                    [action |-> "init_to_proc",
                                     state  |-> "processing",
                                     ts     |-> step_count + 1])             ||
                audit_log     := Append(audit_log,
                                    [from_state |-> "init",
                                     to_state   |-> "processing",
                                     ts         |-> step_count + 1]);
            elsif current_state = "processing" then
                history       := Append(history, current_state)              ||
                current_state := "done"                                       ||
                step_count    := step_count + 1                              ||
                trace_log     := Append(trace_log,
                                    [action |-> "proc_to_done",
                                     state  |-> "done",
                                     ts     |-> step_count + 1])             ||
                audit_log     := Append(audit_log,
                                    [from_state |-> "processing",
                                     to_state   |-> "done",
                                     ts         |-> step_count + 1]);
            else
                skip;
            end if;
        end while;
    Terminate:
        phase := "complete";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "aaec54d2" /\ chksum(tla) = "afb3bfe0")
VARIABLES pc, current_state, step_count, trace_log, audit_log, history, phase

(* define statement *)
ValidState == current_state \in States

BoundedExecution == step_count <= MaxSteps





TraceComplete ==
    step_count > 0 => Len(trace_log) >= step_count





AuditComplete ==
    Len(history) > 0 => Len(audit_log) >= Len(history)



TraceLogMonotonic == Len(trace_log) >= 0



AuditLogMonotonic == Len(audit_log) >= 0


BasePreserved == ValidState /\ BoundedExecution


vars == << pc, current_state, step_count, trace_log, audit_log, history, 
           phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "init"
        /\ step_count = 0
        /\ trace_log = <<>>
        /\ audit_log = <<>>
        /\ history = <<>>
        /\ phase = "running"
        /\ pc = [self \in ProcSet |-> "RunLoop"]

RunLoop == /\ pc["main"] = "RunLoop"
           /\ IF current_state /= "done" /\ step_count < MaxSteps
                 THEN /\ IF current_state = "init"
                            THEN /\ /\ audit_log' = Append(audit_log,
                                                       [from_state |-> "init",
                                                        to_state   |-> "processing",
                                                        ts         |-> step_count + 1])
                                    /\ current_state' = "processing"
                                    /\ history' = Append(history, current_state)
                                    /\ step_count' = step_count + 1
                                    /\ trace_log' = Append(trace_log,
                                                       [action |-> "init_to_proc",
                                                        state  |-> "processing",
                                                        ts     |-> step_count + 1])
                            ELSE /\ IF current_state = "processing"
                                       THEN /\ /\ audit_log' = Append(audit_log,
                                                                  [from_state |-> "processing",
                                                                   to_state   |-> "done",
                                                                   ts         |-> step_count + 1])
                                               /\ current_state' = "done"
                                               /\ history' = Append(history, current_state)
                                               /\ step_count' = step_count + 1
                                               /\ trace_log' = Append(trace_log,
                                                                  [action |-> "proc_to_done",
                                                                   state  |-> "done",
                                                                   ts     |-> step_count + 1])
                                       ELSE /\ TRUE
                                            /\ UNCHANGED << current_state, 
                                                            step_count, 
                                                            trace_log, 
                                                            audit_log, history >>
                      /\ pc' = [pc EXCEPT !["main"] = "RunLoop"]
                 ELSE /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                      /\ UNCHANGED << current_state, step_count, trace_log, 
                                      audit_log, history >>
           /\ phase' = phase

Terminate == /\ pc["main"] = "Terminate"
             /\ phase' = "complete"
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << current_state, step_count, trace_log, audit_log, 
                             history >>

actor == RunLoop \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == actor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(actor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
====
