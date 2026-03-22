---- MODULE scanner_rust_line_ranges ----

EXTENDS Integers, FiniteSets, TLC

Lines == << "ImplOpen", "Fn", "CloseBrace", "TraitOpen", "Fn", "CloseBrace", "Fn" >>
N == 7

(* --algorithm ScannerRustLineRanges

variables
    i        = 1,
    skeletons = {},
    in_trait  = FALSE;

define
    InTrait(k) ==
        \E j \in 1..(k-1) :
            /\ Lines[j] = "TraitOpen"
            /\ ~\E m \in (j+1)..(k-1) : Lines[m] = "CloseBrace"

    LineNumberCorrect ==
        \A s \in skeletons :
            /\ s.line_num >= 1
            /\ s.line_num <= N
            /\ Lines[s.line_num] = "Fn"

    TraitExclusion ==
        \A s \in skeletons :
            ~(\E j \in 1..(s.line_num - 1) :
                Lines[j] = "TraitOpen" /\
                ~(\E m \in (j+1)..(s.line_num - 1) : Lines[m] = "CloseBrace"))

    NoGaps ==
        i > N =>
            \A k \in 1..N :
                (Lines[k] = "Fn" /\ ~InTrait(k)) =>
                    \E s \in skeletons : s.line_num = k

    CursorBounded == i <= N + 1

end define;

process scanner = "scanner"
begin
    ScanLoop:
        while i <= N do
            ProcessLine:
                if Lines[i] = "TraitOpen" then
                    in_trait := TRUE;
                elsif Lines[i] = "CloseBrace" /\ in_trait then
                    in_trait := FALSE;
                elsif Lines[i] = "Fn" /\ ~in_trait then
                    skeletons := skeletons \cup {[line_num |-> i]};
                end if;
            Advance:
                i := i + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "1445dac5" /\ chksum(tla) = "786dc1dd")
VARIABLES pc, i, skeletons, in_trait

(* define statement *)
InTrait(k) ==
    \E j \in 1..(k-1) :
        /\ Lines[j] = "TraitOpen"
        /\ ~\E m \in (j+1)..(k-1) : Lines[m] = "CloseBrace"

LineNumberCorrect ==
    \A s \in skeletons :
        /\ s.line_num >= 1
        /\ s.line_num <= N
        /\ Lines[s.line_num] = "Fn"

TraitExclusion ==
    \A s \in skeletons :
        ~(\E j \in 1..(s.line_num - 1) :
            Lines[j] = "TraitOpen" /\
            ~(\E m \in (j+1)..(s.line_num - 1) : Lines[m] = "CloseBrace"))

NoGaps ==
    i > N =>
        \A k \in 1..N :
            (Lines[k] = "Fn" /\ ~InTrait(k)) =>
                \E s \in skeletons : s.line_num = k

CursorBounded == i <= N + 1


vars == << pc, i, skeletons, in_trait >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ i = 1
        /\ skeletons = {}
        /\ in_trait = FALSE
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF i <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessLine"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << i, skeletons, in_trait >>

ProcessLine == /\ pc["scanner"] = "ProcessLine"
               /\ IF Lines[i] = "TraitOpen"
                     THEN /\ in_trait' = TRUE
                          /\ UNCHANGED skeletons
                     ELSE /\ IF Lines[i] = "CloseBrace" /\ in_trait
                                THEN /\ in_trait' = FALSE
                                     /\ UNCHANGED skeletons
                                ELSE /\ IF Lines[i] = "Fn" /\ ~in_trait
                                           THEN /\ skeletons' = (skeletons \cup {[line_num |-> i]})
                                           ELSE /\ TRUE
                                                /\ UNCHANGED skeletons
                                     /\ UNCHANGED in_trait
               /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
               /\ i' = i

Advance == /\ pc["scanner"] = "Advance"
           /\ i' = i + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << skeletons, in_trait >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << i, skeletons, in_trait >>

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
