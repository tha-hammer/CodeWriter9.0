---- MODULE UpsertAtomicity ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    UUIDs,
    MaxSteps

ASSUME Cardinality(UUIDs) >= 2

TargetUUID == CHOOSE u \in UUIDs : TRUE
OtherUUID  == CHOOSE u \in UUIDs : u /= TargetUUID

(* --algorithm UpsertAtomicity

variables
    c_records = {TargetUUID, OtherUUID},
    c_ins  = [u \in UUIDs |->
                IF u = TargetUUID THEN {"old_in"}
                ELSE IF u = OtherUUID THEN {"other_in"}
                ELSE {}],
    c_outs = [u \in UUIDs |->
                IF u = TargetUUID THEN {"old_out"}
                ELSE {}],
    c_refs = [u \in UUIDs |->
                IF u = TargetUUID THEN {OtherUUID}
                ELSE {}],
    w_records = {TargetUUID, OtherUUID},
    w_ins  = [u \in UUIDs |->
                IF u = TargetUUID THEN {"old_in"}
                ELSE IF u = OtherUUID THEN {"other_in"}
                ELSE {}],
    w_outs = [u \in UUIDs |->
                IF u = TargetUUID THEN {"old_out"}
                ELSE {}],
    w_refs = [u \in UUIDs |->
                IF u = TargetUUID THEN {OtherUUID}
                ELSE {}],
    txn_state = "idle",
    reader_saw_partial = FALSE,
    step_count = 0;

define

    NoOrphanedIns ==
        \A u \in UUIDs : c_ins[u] /= {} => u \in c_records

    NoOrphanedOuts ==
        \A u \in UUIDs : c_outs[u] /= {} => u \in c_records

    RefIntegrity ==
        \A u \in UUIDs :
            \A src \in c_refs[u] : src \in c_records

    AtomicityHolds == reader_saw_partial = FALSE

    BoundedExecution == step_count <= MaxSteps

    CommitCompleteness ==
        txn_state = "committed" =>
            /\ TargetUUID \in c_records
            /\ c_ins[TargetUUID]  = {"new_in"}
            /\ c_outs[TargetUUID] = {"new_out"}
            /\ c_refs[TargetUUID] = {}

    RollbackPreservation ==
        txn_state = "rolled_back" =>
            /\ TargetUUID \in c_records
            /\ c_ins[TargetUUID]  = {"old_in"}
            /\ c_outs[TargetUUID] = {"old_out"}
            /\ c_refs[TargetUUID] = {OtherUUID}

    OtherUUIDUnaffected ==
        c_ins[OtherUUID] = {"other_in"}

end define;

fair process upsert = "upsert"
begin
    BeginUpsert:
        w_records := c_records;
        w_ins     := c_ins;
        w_outs    := c_outs;
        w_refs    := c_refs;
        txn_state := "begun";
        step_count := step_count + 1;

    NullifyRefs:
        w_refs    := [w_refs EXCEPT ![TargetUUID] = {}];
        txn_state := "nullified";
        step_count := step_count + 1;

    DeleteOld:
        w_records := w_records \ {TargetUUID};
        w_ins     := [w_ins  EXCEPT ![TargetUUID] = {}];
        w_outs    := [w_outs EXCEPT ![TargetUUID] = {}];
        txn_state := "deleted";
        step_count := step_count + 1;

    InsertNew:
        w_records := w_records \union {TargetUUID};
        w_ins     := [w_ins  EXCEPT ![TargetUUID] = {"new_in"}];
        w_outs    := [w_outs EXCEPT ![TargetUUID] = {"new_out"}];
        txn_state := "inserted";
        step_count := step_count + 1;

    DecideOutcome:
        either
            Commit:
                c_records := w_records;
                c_ins     := w_ins;
                c_outs    := w_outs;
                c_refs    := w_refs;
                txn_state := "committed";
                step_count := step_count + 1;
        or
            RollbackOp:
                txn_state := "rolled_back";
                step_count := step_count + 1;
        end either;

    UpsertDone:
        skip;
end process;

fair process reader = "reader"
begin
    ReadLoop:
        while txn_state \notin {"committed", "rolled_back"} /\ step_count < MaxSteps do
            if TargetUUID \in c_records then
                if c_ins[TargetUUID] = {} /\ c_outs[TargetUUID] = {} then
                    reader_saw_partial := TRUE;
                end if;
            else
                if c_ins[TargetUUID] /= {} \/ c_outs[TargetUUID] /= {} then
                    reader_saw_partial := TRUE;
                end if;
            end if;
        end while;
    ReaderDone:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "64f25a62" /\ chksum(tla) = "9d44c7ea")
VARIABLES pc, c_records, c_ins, c_outs, c_refs, w_records, w_ins, w_outs, 
          w_refs, txn_state, reader_saw_partial, step_count

(* define statement *)
NoOrphanedIns ==
    \A u \in UUIDs : c_ins[u] /= {} => u \in c_records

NoOrphanedOuts ==
    \A u \in UUIDs : c_outs[u] /= {} => u \in c_records

RefIntegrity ==
    \A u \in UUIDs :
        \A src \in c_refs[u] : src \in c_records

AtomicityHolds == reader_saw_partial = FALSE

BoundedExecution == step_count <= MaxSteps

CommitCompleteness ==
    txn_state = "committed" =>
        /\ TargetUUID \in c_records
        /\ c_ins[TargetUUID]  = {"new_in"}
        /\ c_outs[TargetUUID] = {"new_out"}
        /\ c_refs[TargetUUID] = {}

RollbackPreservation ==
    txn_state = "rolled_back" =>
        /\ TargetUUID \in c_records
        /\ c_ins[TargetUUID]  = {"old_in"}
        /\ c_outs[TargetUUID] = {"old_out"}
        /\ c_refs[TargetUUID] = {OtherUUID}

OtherUUIDUnaffected ==
    c_ins[OtherUUID] = {"other_in"}


vars == << pc, c_records, c_ins, c_outs, c_refs, w_records, w_ins, w_outs, 
           w_refs, txn_state, reader_saw_partial, step_count >>

ProcSet == {"upsert"} \cup {"reader"}

Init == (* Global variables *)
        /\ c_records = {TargetUUID, OtherUUID}
        /\ c_ins = [u \in UUIDs |->
                      IF u = TargetUUID THEN {"old_in"}
                      ELSE IF u = OtherUUID THEN {"other_in"}
                      ELSE {}]
        /\ c_outs = [u \in UUIDs |->
                       IF u = TargetUUID THEN {"old_out"}
                       ELSE {}]
        /\ c_refs = [u \in UUIDs |->
                       IF u = TargetUUID THEN {OtherUUID}
                       ELSE {}]
        /\ w_records = {TargetUUID, OtherUUID}
        /\ w_ins = [u \in UUIDs |->
                      IF u = TargetUUID THEN {"old_in"}
                      ELSE IF u = OtherUUID THEN {"other_in"}
                      ELSE {}]
        /\ w_outs = [u \in UUIDs |->
                       IF u = TargetUUID THEN {"old_out"}
                       ELSE {}]
        /\ w_refs = [u \in UUIDs |->
                       IF u = TargetUUID THEN {OtherUUID}
                       ELSE {}]
        /\ txn_state = "idle"
        /\ reader_saw_partial = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> CASE self = "upsert" -> "BeginUpsert"
                                        [] self = "reader" -> "ReadLoop"]

BeginUpsert == /\ pc["upsert"] = "BeginUpsert"
               /\ w_records' = c_records
               /\ w_ins' = c_ins
               /\ w_outs' = c_outs
               /\ w_refs' = c_refs
               /\ txn_state' = "begun"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["upsert"] = "NullifyRefs"]
               /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, 
                               reader_saw_partial >>

NullifyRefs == /\ pc["upsert"] = "NullifyRefs"
               /\ w_refs' = [w_refs EXCEPT ![TargetUUID] = {}]
               /\ txn_state' = "nullified"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["upsert"] = "DeleteOld"]
               /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, 
                               w_ins, w_outs, reader_saw_partial >>

DeleteOld == /\ pc["upsert"] = "DeleteOld"
             /\ w_records' = w_records \ {TargetUUID}
             /\ w_ins' = [w_ins  EXCEPT ![TargetUUID] = {}]
             /\ w_outs' = [w_outs EXCEPT ![TargetUUID] = {}]
             /\ txn_state' = "deleted"
             /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["upsert"] = "InsertNew"]
             /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_refs, 
                             reader_saw_partial >>

InsertNew == /\ pc["upsert"] = "InsertNew"
             /\ w_records' = (w_records \union {TargetUUID})
             /\ w_ins' = [w_ins  EXCEPT ![TargetUUID] = {"new_in"}]
             /\ w_outs' = [w_outs EXCEPT ![TargetUUID] = {"new_out"}]
             /\ txn_state' = "inserted"
             /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["upsert"] = "DecideOutcome"]
             /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_refs, 
                             reader_saw_partial >>

DecideOutcome == /\ pc["upsert"] = "DecideOutcome"
                 /\ \/ /\ pc' = [pc EXCEPT !["upsert"] = "Commit"]
                    \/ /\ pc' = [pc EXCEPT !["upsert"] = "RollbackOp"]
                 /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, 
                                 w_ins, w_outs, w_refs, txn_state, 
                                 reader_saw_partial, step_count >>

Commit == /\ pc["upsert"] = "Commit"
          /\ c_records' = w_records
          /\ c_ins' = w_ins
          /\ c_outs' = w_outs
          /\ c_refs' = w_refs
          /\ txn_state' = "committed"
          /\ step_count' = step_count + 1
          /\ pc' = [pc EXCEPT !["upsert"] = "UpsertDone"]
          /\ UNCHANGED << w_records, w_ins, w_outs, w_refs, reader_saw_partial >>

RollbackOp == /\ pc["upsert"] = "RollbackOp"
              /\ txn_state' = "rolled_back"
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["upsert"] = "UpsertDone"]
              /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, 
                              w_ins, w_outs, w_refs, reader_saw_partial >>

UpsertDone == /\ pc["upsert"] = "UpsertDone"
              /\ TRUE
              /\ pc' = [pc EXCEPT !["upsert"] = "Done"]
              /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, 
                              w_ins, w_outs, w_refs, txn_state, 
                              reader_saw_partial, step_count >>

upsert == BeginUpsert \/ NullifyRefs \/ DeleteOld \/ InsertNew
             \/ DecideOutcome \/ Commit \/ RollbackOp \/ UpsertDone

ReadLoop == /\ pc["reader"] = "ReadLoop"
            /\ IF txn_state \notin {"committed", "rolled_back"} /\ step_count < MaxSteps
                  THEN /\ IF TargetUUID \in c_records
                             THEN /\ IF c_ins[TargetUUID] = {} /\ c_outs[TargetUUID] = {}
                                        THEN /\ reader_saw_partial' = TRUE
                                        ELSE /\ TRUE
                                             /\ UNCHANGED reader_saw_partial
                             ELSE /\ IF c_ins[TargetUUID] /= {} \/ c_outs[TargetUUID] /= {}
                                        THEN /\ reader_saw_partial' = TRUE
                                        ELSE /\ TRUE
                                             /\ UNCHANGED reader_saw_partial
                       /\ pc' = [pc EXCEPT !["reader"] = "ReadLoop"]
                  ELSE /\ pc' = [pc EXCEPT !["reader"] = "ReaderDone"]
                       /\ UNCHANGED reader_saw_partial
            /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, w_ins, 
                            w_outs, w_refs, txn_state, step_count >>

ReaderDone == /\ pc["reader"] = "ReaderDone"
              /\ TRUE
              /\ pc' = [pc EXCEPT !["reader"] = "Done"]
              /\ UNCHANGED << c_records, c_ins, c_outs, c_refs, w_records, 
                              w_ins, w_outs, w_refs, txn_state, 
                              reader_saw_partial, step_count >>

reader == ReadLoop \/ ReaderDone

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == upsert \/ reader
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(upsert)
        /\ WF_vars(reader)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
