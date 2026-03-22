---- MODULE scanner_go_nested_depth ----

EXTENDS Integers, FiniteSets, TLC

Events == <<
    [has_recv |-> FALSE, recv_type |-> "None",  name |-> "Hello",    cap |-> TRUE],
    [has_recv |-> TRUE,  recv_type |-> "Svc",   name |-> "GetUser",  cap |-> TRUE],
    [has_recv |-> TRUE,  recv_type |-> "Point", name |-> "distance", cap |-> FALSE],
    [has_recv |-> FALSE, recv_type |-> "None",  name |-> "helper",   cap |-> FALSE]
>>
N == 4

(* --algorithm ScannerGoNestedDepth

variables
    cursor    = 1,
    skeletons = {};

define
    ReceiverResolution ==
        \A s \in skeletons :
            \/ (s.class_name = "None" /\ s.has_recv = FALSE)
            \/ (s.class_name # "None" /\ s.has_recv = TRUE)

    VisibilityCorrect ==
        \A s \in skeletons :
            \/ (s.visibility = "public"  /\ s.cap = TRUE)
            \/ (s.visibility = "private" /\ s.cap = FALSE)

    AllRecorded ==
        cursor > N =>
            \A k \in 1..N :
                \E s \in skeletons : s.func_name = Events[k].name
end define;

process scanner = "scanner"
begin
    ScanLoop:
        while cursor <= N do
            ProcessEvent:
                skeletons := skeletons \cup
                    {[func_name  |-> Events[cursor].name,
                      class_name |-> Events[cursor].recv_type,
                      has_recv   |-> Events[cursor].has_recv,
                      cap        |-> Events[cursor].cap,
                      visibility |-> IF Events[cursor].cap THEN "public" ELSE "private"]};
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "a0c791cc" /\ chksum(tla) = "4320667f")
VARIABLES pc, cursor, skeletons

(* define statement *)
ReceiverResolution ==
    \A s \in skeletons :
        \/ (s.class_name = "None" /\ s.has_recv = FALSE)
        \/ (s.class_name # "None" /\ s.has_recv = TRUE)

VisibilityCorrect ==
    \A s \in skeletons :
        \/ (s.visibility = "public"  /\ s.cap = TRUE)
        \/ (s.visibility = "private" /\ s.cap = FALSE)

AllRecorded ==
    cursor > N =>
        \A k \in 1..N :
            \E s \in skeletons : s.func_name = Events[k].name


vars == << pc, cursor, skeletons >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ skeletons = {}
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF cursor <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessEvent"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << cursor, skeletons >>

ProcessEvent == /\ pc["scanner"] = "ProcessEvent"
                /\ skeletons' = (         skeletons \cup
                                 {[func_name  |-> Events[cursor].name,
                                   class_name |-> Events[cursor].recv_type,
                                   has_recv   |-> Events[cursor].has_recv,
                                   cap        |-> Events[cursor].cap,
                                   visibility |-> IF Events[cursor].cap THEN "public" ELSE "private"]})
                /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
                /\ UNCHANGED cursor

Advance == /\ pc["scanner"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED skeletons

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << cursor, skeletons >>

scanner == ScanLoop \/ ProcessEvent \/ Advance \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == scanner
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
