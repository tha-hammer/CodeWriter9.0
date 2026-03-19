---- MODULE SweepRemainingAsync ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    NumTasks,
    MaxConcurrency,
    FailingTask

ASSUME NumTasks >= 1
ASSUME MaxConcurrency >= 1 /\ MaxConcurrency <= NumTasks
ASSUME FailingTask \in 1..NumTasks

(* --algorithm SweepRemainingAsync

variables
    task_state      = [t \in 1..NumTasks |-> "pending"],
    sem_count       = MaxConcurrency,
    sem_held        = [t \in 1..NumTasks |-> FALSE],
    results         = [t \in 1..NumTasks |-> "none"],
    gather_complete = FALSE;

define

    SemaphoreValid ==
        sem_count >= 0 /\ sem_count <= MaxConcurrency

    SemaphoreConsistent ==
        sem_count + Cardinality({t \in 1..NumTasks : sem_held[t]}) = MaxConcurrency

    NoCancellation ==
        \A t \in 1..NumTasks : task_state[t] # "cancelled"

    ExceptionCapturedAsResult ==
        gather_complete => results[FailingTask] = "exception"

    AllOthersSucceedWhenGatherDone ==
        gather_complete =>
            \A t \in (1..NumTasks) \ {FailingTask} : results[t] = "ok"

    GatherRequiresAllTasksDone ==
        gather_complete =>
            \A t \in 1..NumTasks :
                task_state[t] = "completed" \/ task_state[t] = "failed"

    FailedTaskSlotReleased ==
        task_state[FailingTask] = "failed" => ~sem_held[FailingTask]

    CompletedOrFailedReleaseSemaphore ==
        \A t \in 1..NumTasks :
            (task_state[t] = "completed" \/ task_state[t] = "failed") =>
                ~sem_held[t]

    RunningTasksHoldSemaphore ==
        \A t \in 1..NumTasks :
            task_state[t] = "running" => sem_held[t]

end define;

fair process Task \in 1..NumTasks
begin
    Acquire:
        await sem_count > 0;
        sem_count        := sem_count - 1;
        sem_held[self]   := TRUE;
        task_state[self] := "running";
    Execute:
        if self = FailingTask then
            results[self] := "exception";
        else
            results[self] := "ok";
        end if;
    Release:
        sem_count      := sem_count + 1;
        sem_held[self] := FALSE;
        if results[self] = "exception" then
            task_state[self] := "failed";
        else
            task_state[self] := "completed";
        end if;
end process;

fair process Gatherer = 0
begin
    WaitAll:
        await \A t \in 1..NumTasks :
            task_state[t] = "completed" \/ task_state[t] = "failed";
    Finish:
        gather_complete := TRUE;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "d43be5b8" /\ chksum(tla) = "fbfab604")
VARIABLES pc, task_state, sem_count, sem_held, results, gather_complete

(* define statement *)
SemaphoreValid ==
    sem_count >= 0 /\ sem_count <= MaxConcurrency

SemaphoreConsistent ==
    sem_count + Cardinality({t \in 1..NumTasks : sem_held[t]}) = MaxConcurrency

NoCancellation ==
    \A t \in 1..NumTasks : task_state[t] # "cancelled"

ExceptionCapturedAsResult ==
    gather_complete => results[FailingTask] = "exception"

AllOthersSucceedWhenGatherDone ==
    gather_complete =>
        \A t \in (1..NumTasks) \ {FailingTask} : results[t] = "ok"

GatherRequiresAllTasksDone ==
    gather_complete =>
        \A t \in 1..NumTasks :
            task_state[t] = "completed" \/ task_state[t] = "failed"

FailedTaskSlotReleased ==
    task_state[FailingTask] = "failed" => ~sem_held[FailingTask]

CompletedOrFailedReleaseSemaphore ==
    \A t \in 1..NumTasks :
        (task_state[t] = "completed" \/ task_state[t] = "failed") =>
            ~sem_held[t]

RunningTasksHoldSemaphore ==
    \A t \in 1..NumTasks :
        task_state[t] = "running" => sem_held[t]


vars == << pc, task_state, sem_count, sem_held, results, gather_complete >>

ProcSet == (1..NumTasks) \cup {0}

Init == (* Global variables *)
        /\ task_state = [t \in 1..NumTasks |-> "pending"]
        /\ sem_count = MaxConcurrency
        /\ sem_held = [t \in 1..NumTasks |-> FALSE]
        /\ results = [t \in 1..NumTasks |-> "none"]
        /\ gather_complete = FALSE
        /\ pc = [self \in ProcSet |-> CASE self \in 1..NumTasks -> "Acquire"
                                        [] self = 0 -> "WaitAll"]

Acquire(self) == /\ pc[self] = "Acquire"
                 /\ sem_count > 0
                 /\ sem_count' = sem_count - 1
                 /\ sem_held' = [sem_held EXCEPT ![self] = TRUE]
                 /\ task_state' = [task_state EXCEPT ![self] = "running"]
                 /\ pc' = [pc EXCEPT ![self] = "Execute"]
                 /\ UNCHANGED << results, gather_complete >>

Execute(self) == /\ pc[self] = "Execute"
                 /\ IF self = FailingTask
                       THEN /\ results' = [results EXCEPT ![self] = "exception"]
                       ELSE /\ results' = [results EXCEPT ![self] = "ok"]
                 /\ pc' = [pc EXCEPT ![self] = "Release"]
                 /\ UNCHANGED << task_state, sem_count, sem_held, 
                                 gather_complete >>

Release(self) == /\ pc[self] = "Release"
                 /\ sem_count' = sem_count + 1
                 /\ sem_held' = [sem_held EXCEPT ![self] = FALSE]
                 /\ IF results[self] = "exception"
                       THEN /\ task_state' = [task_state EXCEPT ![self] = "failed"]
                       ELSE /\ task_state' = [task_state EXCEPT ![self] = "completed"]
                 /\ pc' = [pc EXCEPT ![self] = "Done"]
                 /\ UNCHANGED << results, gather_complete >>

Task(self) == Acquire(self) \/ Execute(self) \/ Release(self)

WaitAll == /\ pc[0] = "WaitAll"
           /\   \A t \in 1..NumTasks :
              task_state[t] = "completed" \/ task_state[t] = "failed"
           /\ pc' = [pc EXCEPT ![0] = "Finish"]
           /\ UNCHANGED << task_state, sem_count, sem_held, results, 
                           gather_complete >>

Finish == /\ pc[0] = "Finish"
          /\ gather_complete' = TRUE
          /\ pc' = [pc EXCEPT ![0] = "Done"]
          /\ UNCHANGED << task_state, sem_count, sem_held, results >>

Gatherer == WaitAll \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Gatherer
           \/ (\E self \in 1..NumTasks: Task(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in 1..NumTasks : WF_vars(Task(self))
        /\ WF_vars(Gatherer)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
