---- MODULE SchemaInitIdempotent ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Tables,
    Rows,
    MaxReconnects

ASSUME MaxReconnects >= 1
ASSUME Tables # {}
ASSUME Rows # {}

(* --algorithm SchemaInitIdempotent

variables
    schema_exists = {},
    data = [t \in Tables |-> {}],
    connected = FALSE,
    wal_mode = FALSE,
    fk_on = FALSE,
    reconnect_count = 0,
    op = "idle",
    data_before = [t \in Tables |-> {}],
    schema_before = {};

define

    SchemaStable ==
        connected => (schema_exists = Tables)

    NoPragmaLoss ==
        connected => (wal_mode = TRUE /\ fk_on = TRUE)

    BoundedReconnects ==
        reconnect_count <= MaxReconnects

    DataNotLost ==
        \A t \in Tables : data_before[t] \subseteq data[t]

    IdempotentDDL ==
        (schema_before = Tables) => (schema_exists = Tables)

end define;

fair process db = "main"
begin
    Connect:
        wal_mode        := TRUE;
        fk_on           := TRUE;
        schema_exists   := Tables;
        connected       := TRUE;
        op              := "connected";

    WorkLoop:
        while reconnect_count < MaxReconnects do
            either
                InsertRow:
                    with t \in Tables do
                        with r \in Rows do
                            data := [data EXCEPT ![t] = data[t] \union {r}];
                        end with;
                    end with;
                    op := "inserted";
            or
                TakeSnapshot:
                    data_before   := data;
                    schema_before := schema_exists;
                    connected     := FALSE;
                    wal_mode      := FALSE;
                    fk_on         := FALSE;
                    op            := "disconnected";

                Reconnect:
                    wal_mode      := TRUE;
                    fk_on         := TRUE;
                    schema_exists := Tables;
                    connected     := TRUE;
                    reconnect_count := reconnect_count + 1;
                    op            := "reconnected";

                VerifyPreservation:
                    assert schema_exists = schema_before;
                    assert \A t \in Tables : data[t] = data_before[t];
                    op := "verified";
            end either;
        end while;

    Terminate:
        op := "done";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "9affe0e7" /\ chksum(tla) = "f889a97e")
VARIABLES pc, schema_exists, data, connected, wal_mode, fk_on, 
          reconnect_count, op, data_before, schema_before

(* define statement *)
SchemaStable ==
    connected => (schema_exists = Tables)

NoPragmaLoss ==
    connected => (wal_mode = TRUE /\ fk_on = TRUE)

BoundedReconnects ==
    reconnect_count <= MaxReconnects

DataNotLost ==
    \A t \in Tables : data_before[t] \subseteq data[t]

IdempotentDDL ==
    (schema_before = Tables) => (schema_exists = Tables)


vars == << pc, schema_exists, data, connected, wal_mode, fk_on, 
           reconnect_count, op, data_before, schema_before >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ schema_exists = {}
        /\ data = [t \in Tables |-> {}]
        /\ connected = FALSE
        /\ wal_mode = FALSE
        /\ fk_on = FALSE
        /\ reconnect_count = 0
        /\ op = "idle"
        /\ data_before = [t \in Tables |-> {}]
        /\ schema_before = {}
        /\ pc = [self \in ProcSet |-> "Connect"]

Connect == /\ pc["main"] = "Connect"
           /\ wal_mode' = TRUE
           /\ fk_on' = TRUE
           /\ schema_exists' = Tables
           /\ connected' = TRUE
           /\ op' = "connected"
           /\ pc' = [pc EXCEPT !["main"] = "WorkLoop"]
           /\ UNCHANGED << data, reconnect_count, data_before, schema_before >>

WorkLoop == /\ pc["main"] = "WorkLoop"
            /\ IF reconnect_count < MaxReconnects
                  THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "InsertRow"]
                          \/ /\ pc' = [pc EXCEPT !["main"] = "TakeSnapshot"]
                  ELSE /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
            /\ UNCHANGED << schema_exists, data, connected, wal_mode, fk_on, 
                            reconnect_count, op, data_before, schema_before >>

InsertRow == /\ pc["main"] = "InsertRow"
             /\ \E t \in Tables:
                  \E r \in Rows:
                    data' = [data EXCEPT ![t] = data[t] \union {r}]
             /\ op' = "inserted"
             /\ pc' = [pc EXCEPT !["main"] = "WorkLoop"]
             /\ UNCHANGED << schema_exists, connected, wal_mode, fk_on, 
                             reconnect_count, data_before, schema_before >>

TakeSnapshot == /\ pc["main"] = "TakeSnapshot"
                /\ data_before' = data
                /\ schema_before' = schema_exists
                /\ connected' = FALSE
                /\ wal_mode' = FALSE
                /\ fk_on' = FALSE
                /\ op' = "disconnected"
                /\ pc' = [pc EXCEPT !["main"] = "Reconnect"]
                /\ UNCHANGED << schema_exists, data, reconnect_count >>

Reconnect == /\ pc["main"] = "Reconnect"
             /\ wal_mode' = TRUE
             /\ fk_on' = TRUE
             /\ schema_exists' = Tables
             /\ connected' = TRUE
             /\ reconnect_count' = reconnect_count + 1
             /\ op' = "reconnected"
             /\ pc' = [pc EXCEPT !["main"] = "VerifyPreservation"]
             /\ UNCHANGED << data, data_before, schema_before >>

VerifyPreservation == /\ pc["main"] = "VerifyPreservation"
                      /\ Assert(schema_exists = schema_before, 
                                "Failure of assertion at line 83, column 21.")
                      /\ Assert(\A t \in Tables : data[t] = data_before[t], 
                                "Failure of assertion at line 84, column 21.")
                      /\ op' = "verified"
                      /\ pc' = [pc EXCEPT !["main"] = "WorkLoop"]
                      /\ UNCHANGED << schema_exists, data, connected, wal_mode, 
                                      fk_on, reconnect_count, data_before, 
                                      schema_before >>

Terminate == /\ pc["main"] = "Terminate"
             /\ op' = "done"
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << schema_exists, data, connected, wal_mode, fk_on, 
                             reconnect_count, data_before, schema_before >>

db == Connect \/ WorkLoop \/ InsertRow \/ TakeSnapshot \/ Reconnect
         \/ VerifyPreservation \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == db
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(db)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
