---- MODULE scanner_go_line_ranges ----

EXTENDS Integers, FiniteSets, TLC

Lines == << "Func", "Other", "InterfaceOpen", "Func", "InterfaceClose", "Func", "Other" >>
N == 7

(* --algorithm ScannerGoLineRanges

variables
    i            = 1,
    skeletons    = {},
    in_interface = FALSE;

define
    InInterface(k) ==
        \E j \in 1..(k-1) :
            /\ Lines[j] = "InterfaceOpen"
            /\ ~(\E m \in (j+1)..(k-1) : Lines[m] = "InterfaceClose")

    LineNumberCorrect ==
        \A s \in skeletons :
            /\ s.line_num >= 1
            /\ s.line_num <= N
            /\ Lines[s.line_num] = "Func"

    InterfaceExclusion ==
        \A s \in skeletons :
            \A k \in 1..N :
                (s.line_num = k) => Lines[k] = "Func"

    NoGaps ==
        (i > N) =>
            \A k \in 1..N :
                (Lines[k] = "Func" /\ ~InInterface(k)) =>
                    \E s \in skeletons : s.line_num = k

    CursorBounded == i <= N + 1
end define;

process scanner = "scanner"
begin
    ScanLoop:
        while i <= N do
            ProcessLine:
                if Lines[i] = "InterfaceOpen" then
                    in_interface := TRUE;
                elsif Lines[i] = "InterfaceClose" then
                    in_interface := FALSE;
                elsif Lines[i] = "Func" /\ ~in_interface then
                    skeletons := skeletons \cup {[line_num |-> i]};
                end if;
            Advance:
                i := i + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f96c7899" /\ chksum(tla) = "dd45b4a5")
VARIABLES pc, i, skeletons, in_interface

(* define statement *)
InInterface(k) ==
    \E j \in 1..(k-1) :
        /\ Lines[j] = "InterfaceOpen"
        /\ ~(\E m \in (j+1)..(k-1) : Lines[m] = "InterfaceClose")

LineNumberCorrect ==
    \A s \in skeletons :
        /\ s.line_num >= 1
        /\ s.line_num <= N
        /\ Lines[s.line_num] = "Func"

InterfaceExclusion ==
    \A s \in skeletons :
        \A k \in 1..N :
            (s.line_num = k) => Lines[k] = "Func"

NoGaps ==
    (i > N) =>
        \A k \in 1..N :
            (Lines[k] = "Func" /\ ~InInterface(k)) =>
                \E s \in skeletons : s.line_num = k

CursorBounded == i <= N + 1


vars == << pc, i, skeletons, in_interface >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ i = 1
        /\ skeletons = {}
        /\ in_interface = FALSE
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF i <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessLine"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << i, skeletons, in_interface >>

ProcessLine == /\ pc["scanner"] = "ProcessLine"
               /\ IF Lines[i] = "InterfaceOpen"
                     THEN /\ in_interface' = TRUE
                          /\ UNCHANGED skeletons
                     ELSE /\ IF Lines[i] = "InterfaceClose"
                                THEN /\ in_interface' = FALSE
                                     /\ UNCHANGED skeletons
                                ELSE /\ IF Lines[i] = "Func" /\ ~in_interface
                                           THEN /\ skeletons' = (skeletons \cup {[line_num |-> i]})
                                           ELSE /\ TRUE
                                                /\ UNCHANGED skeletons
                                     /\ UNCHANGED in_interface
               /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
               /\ i' = i

Advance == /\ pc["scanner"] = "Advance"
           /\ i' = i + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << skeletons, in_interface >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << i, skeletons, in_interface >>

scanner == ScanLoop \/ ProcessLine \/ Advance \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == scanner
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
