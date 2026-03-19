---- MODULE CrawlOrchestratorUpsert ----

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    Coroutines,
    MaxSteps

ASSUME Cardinality(Coroutines) >= 1
ASSUME MaxSteps \in Nat /\ MaxSteps >= 1

(* --algorithm CrawlOrchestratorUpsert

variables
    phase           = [c \in Coroutines |-> "IDLE"],
    upsert_log      = <<>>,
    upsert_started  = 0,
    upsert_finished = 0;

define

    Phases == {"IDLE", "EXTRACTING", "EXTRACTED", "COMPLETE"}

    TypeInvariant ==
        /\ \A c \in Coroutines : phase[c] \in Phases
        /\ upsert_started  \in 0..Cardinality(Coroutines)
        /\ upsert_finished \in 0..Cardinality(Coroutines)
        /\ Len(upsert_log) \in 0..Cardinality(Coroutines)
        /\ \A i \in 1..Len(upsert_log) : upsert_log[i] \in Coroutines

    NoSimultaneousUpserts ==
        upsert_started - upsert_finished <= 1

    UpsertLogNoDuplicates ==
        \A i, j \in 1..Len(upsert_log) :
            i /= j => upsert_log[i] /= upsert_log[j]

    CompletionImpliesUpserted ==
        \A c \in Coroutines :
            phase[c] = "COMPLETE" =>
                \E i \in 1..Len(upsert_log) : upsert_log[i] = c

    UpsertLogLengthMatchesCompletions ==
        Len(upsert_log) = Cardinality({c \in Coroutines : phase[c] = "COMPLETE"})

end define;

fair process coroutine \in Coroutines
begin
    StartExtract:
        phase[self] := "EXTRACTING";

    AwaitExtract:
        phase[self] := "EXTRACTED";

    SyncUpsert:
        upsert_started  := upsert_started  + 1;
        upsert_log      := Append(upsert_log, self);
        phase[self]     := "COMPLETE";
        upsert_finished := upsert_finished + 1;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3dcdb314" /\ chksum(tla) = "f0e280d4")
VARIABLES pc, phase, upsert_log, upsert_started, upsert_finished

(* define statement *)
Phases == {"IDLE", "EXTRACTING", "EXTRACTED", "COMPLETE"}

TypeInvariant ==
    /\ \A c \in Coroutines : phase[c] \in Phases
    /\ upsert_started  \in 0..Cardinality(Coroutines)
    /\ upsert_finished \in 0..Cardinality(Coroutines)
    /\ Len(upsert_log) \in 0..Cardinality(Coroutines)
    /\ \A i \in 1..Len(upsert_log) : upsert_log[i] \in Coroutines

NoSimultaneousUpserts ==
    upsert_started - upsert_finished <= 1

UpsertLogNoDuplicates ==
    \A i, j \in 1..Len(upsert_log) :
        i /= j => upsert_log[i] /= upsert_log[j]

CompletionImpliesUpserted ==
    \A c \in Coroutines :
        phase[c] = "COMPLETE" =>
            \E i \in 1..Len(upsert_log) : upsert_log[i] = c

UpsertLogLengthMatchesCompletions ==
    Len(upsert_log) = Cardinality({c \in Coroutines : phase[c] = "COMPLETE"})


vars == << pc, phase, upsert_log, upsert_started, upsert_finished >>

ProcSet == (Coroutines)

Init == (* Global variables *)
        /\ phase = [c \in Coroutines |-> "IDLE"]
        /\ upsert_log = <<>>
        /\ upsert_started = 0
        /\ upsert_finished = 0
        /\ pc = [self \in ProcSet |-> "StartExtract"]

StartExtract(self) == /\ pc[self] = "StartExtract"
                      /\ phase' = [phase EXCEPT ![self] = "EXTRACTING"]
                      /\ pc' = [pc EXCEPT ![self] = "AwaitExtract"]
                      /\ UNCHANGED << upsert_log, upsert_started, 
                                      upsert_finished >>

AwaitExtract(self) == /\ pc[self] = "AwaitExtract"
                      /\ phase' = [phase EXCEPT ![self] = "EXTRACTED"]
                      /\ pc' = [pc EXCEPT ![self] = "SyncUpsert"]
                      /\ UNCHANGED << upsert_log, upsert_started, 
                                      upsert_finished >>

SyncUpsert(self) == /\ pc[self] = "SyncUpsert"
                    /\ upsert_started' = upsert_started  + 1
                    /\ upsert_log' = Append(upsert_log, self)
                    /\ phase' = [phase EXCEPT ![self] = "COMPLETE"]
                    /\ upsert_finished' = upsert_finished + 1
                    /\ pc' = [pc EXCEPT ![self] = "Done"]

coroutine(self) == StartExtract(self) \/ AwaitExtract(self)
                      \/ SyncUpsert(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in Coroutines: coroutine(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in Coroutines : WF_vars(coroutine(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
