---- MODULE SweepRemainingAsync ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    N,
    M

(* --algorithm SweepRemainingAsync

variables
    sem       = N,
    active    = 0,
    processed = 0,
    task_acq  = [i \in 1..M |-> 0],
    task_rel  = [i \in 1..M |-> 0];

define

    ConcurrencyBound ==
        active <= N

    SemNonNegative ==
        sem >= 0

    SemaphoreConservation ==
        sem + active = N

    PerTaskAtMostOnce ==
        \A i \in 1..M : task_acq[i] <= 1 /\ task_rel[i] <= 1

    AcqBeforeRel ==
        \A i \in 1..M : task_rel[i] <= task_acq[i]

    WhenCompleteSymmetric ==
        processed = M =>
            \A i \in 1..M : task_acq[i] = 1 /\ task_rel[i] = 1

    AllInvariants ==
        /\ ConcurrencyBound
        /\ SemNonNegative
        /\ SemaphoreConservation
        /\ PerTaskAtMostOnce
        /\ AcqBeforeRel
        /\ WhenCompleteSymmetric

end define;

fair process Task \in 1..M
begin
    Acquire:
        await sem > 0;
        sem            := sem - 1;
        active         := active + 1;
        task_acq[self] := task_acq[self] + 1;
    Execute:
        skip;
    Release:
        sem            := sem + 1;
        active         := active - 1;
        task_rel[self] := task_rel[self] + 1;
        processed      := processed + 1;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3b56b8c3" /\ chksum(tla) = "1cd138e7")
VARIABLES pc, sem, active, processed, task_acq, task_rel

(* define statement *)
ConcurrencyBound ==
    active <= N

SemNonNegative ==
    sem >= 0

SemaphoreConservation ==
    sem + active = N

PerTaskAtMostOnce ==
    \A i \in 1..M : task_acq[i] <= 1 /\ task_rel[i] <= 1

AcqBeforeRel ==
    \A i \in 1..M : task_rel[i] <= task_acq[i]

WhenCompleteSymmetric ==
    processed = M =>
        \A i \in 1..M : task_acq[i] = 1 /\ task_rel[i] = 1

AllInvariants ==
    /\ ConcurrencyBound
    /\ SemNonNegative
    /\ SemaphoreConservation
    /\ PerTaskAtMostOnce
    /\ AcqBeforeRel
    /\ WhenCompleteSymmetric


vars == << pc, sem, active, processed, task_acq, task_rel >>

ProcSet == (1..M)

Init == (* Global variables *)
        /\ sem = N
        /\ active = 0
        /\ processed = 0
        /\ task_acq = [i \in 1..M |-> 0]
        /\ task_rel = [i \in 1..M |-> 0]
        /\ pc = [self \in ProcSet |-> "Acquire"]

Acquire(self) == /\ pc[self] = "Acquire"
                 /\ sem > 0
                 /\ sem' = sem - 1
                 /\ active' = active + 1
                 /\ task_acq' = [task_acq EXCEPT ![self] = task_acq[self] + 1]
                 /\ pc' = [pc EXCEPT ![self] = "Execute"]
                 /\ UNCHANGED << processed, task_rel >>

Execute(self) == /\ pc[self] = "Execute"
                 /\ TRUE
                 /\ pc' = [pc EXCEPT ![self] = "Release"]
                 /\ UNCHANGED << sem, active, processed, task_acq, task_rel >>

Release(self) == /\ pc[self] = "Release"
                 /\ sem' = sem + 1
                 /\ active' = active - 1
                 /\ task_rel' = [task_rel EXCEPT ![self] = task_rel[self] + 1]
                 /\ processed' = processed + 1
                 /\ pc' = [pc EXCEPT ![self] = "Finish"]
                 /\ UNCHANGED task_acq

Finish(self) == /\ pc[self] = "Finish"
                /\ TRUE
                /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << sem, active, processed, task_acq, task_rel >>

Task(self) == Acquire(self) \/ Execute(self) \/ Release(self)
                 \/ Finish(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in 1..M: Task(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in 1..M : WF_vars(Task(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

Invariant == AllInvariants

Liveness == <>(processed = M)

THEOREM Spec => []Invariant /\ Liveness

====
