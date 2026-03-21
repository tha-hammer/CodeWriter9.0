---- MODULE SemaphoreBoundedConcurrency ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Records,
    Concurrency

ASSUME Concurrency \in Nat /\ Concurrency >= 1
ASSUME IsFiniteSet(Records) /\ Records # {}

(* --algorithm SemaphoreBoundedConcurrency

variables
    semaphore = Concurrency,
    active    = {},
    completed = {},
    pending   = Records;

define

    SemaphoreNonNeg == semaphore >= 0

    ActiveBounded == Cardinality(active) <= Concurrency

    SemaphoreConsistent == semaphore + Cardinality(active) = Concurrency

    ActiveReleasedOnComplete == active \cap completed = {}

    AllEventuallyProcessed ==
        (pending = {} /\ active = {}) => (completed = Records)

end define;

fair process extractor \in Records
begin
    Acquire:
        await semaphore > 0 /\ self \in pending;
        semaphore := semaphore - 1;
        active    := active \cup {self};
        pending   := pending \ {self};
    Extract:
        skip;
    Release:
        active    := active \ {self};
        completed := completed \cup {self};
        semaphore := semaphore + 1;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "990fdab9" /\ chksum(tla) = "63662e02")
VARIABLES pc, semaphore, active, completed, pending

(* define statement *)
SemaphoreNonNeg == semaphore >= 0

ActiveBounded == Cardinality(active) <= Concurrency

SemaphoreConsistent == semaphore + Cardinality(active) = Concurrency

ActiveReleasedOnComplete == active \cap completed = {}

AllEventuallyProcessed ==
    (pending = {} /\ active = {}) => (completed = Records)


vars == << pc, semaphore, active, completed, pending >>

ProcSet == (Records)

Init == (* Global variables *)
        /\ semaphore = Concurrency
        /\ active = {}
        /\ completed = {}
        /\ pending = Records
        /\ pc = [self \in ProcSet |-> "Acquire"]

Acquire(self) == /\ pc[self] = "Acquire"
                 /\ semaphore > 0 /\ self \in pending
                 /\ semaphore' = semaphore - 1
                 /\ active' = (active \cup {self})
                 /\ pending' = pending \ {self}
                 /\ pc' = [pc EXCEPT ![self] = "Extract"]
                 /\ UNCHANGED completed

Extract(self) == /\ pc[self] = "Extract"
                 /\ TRUE
                 /\ pc' = [pc EXCEPT ![self] = "Release"]
                 /\ UNCHANGED << semaphore, active, completed, pending >>

Release(self) == /\ pc[self] = "Release"
                 /\ active' = active \ {self}
                 /\ completed' = (completed \cup {self})
                 /\ semaphore' = semaphore + 1
                 /\ pc' = [pc EXCEPT ![self] = "Finish"]
                 /\ UNCHANGED pending

Finish(self) == /\ pc[self] = "Finish"
                /\ TRUE
                /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << semaphore, active, completed, pending >>

extractor(self) == Acquire(self) \/ Extract(self) \/ Release(self)
                      \/ Finish(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in Records: extractor(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in Records : WF_vars(extractor(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Init =>
    /\ semaphore = Concurrency
    /\ active    = {}
    /\ completed = {}
    /\ pending   = Records

====
