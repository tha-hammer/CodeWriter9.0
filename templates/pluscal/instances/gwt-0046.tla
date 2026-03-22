---- MODULE scanner_python_line_ranges ----

EXTENDS Integers, FiniteSets, TLC

Lines == << "Def", "Other", "Def", "Other", "AsyncDef", "Other", "AsyncDef" >>
Conts == << FALSE,  FALSE,  TRUE,  FALSE,  TRUE,       FALSE,  FALSE >>
N     == 7

(* --algorithm ScannerPythonLineRanges

variables
    i         = 1,
    skeletons = {},
    in_sig    = FALSE,
    sig_start = 0,
    sig_async = FALSE;

define

    OneIndexed ==
        \A s \in skeletons : s.line_num >= 1

    LineNumberCorrect ==
        \A s \in skeletons :
            /\ s.line_num >= 1
            /\ s.line_num <= N
            /\ Lines[s.line_num] \in {"Def", "AsyncDef"}
            /\ s.is_async = (Lines[s.line_num] = "AsyncDef")

    MultiLineStable ==
        \A s \in skeletons :
            Lines[s.line_num] \in {"Def", "AsyncDef"}

    NoGaps ==
        i > N =>
            ( \A k \in 1..N :
                Lines[k] \in {"Def", "AsyncDef"} =>
                    \E s \in skeletons : s.line_num = k )

    SigStartValid ==
        in_sig =>
            ( /\ sig_start >= 1
              /\ sig_start <= N
              /\ Lines[sig_start] \in {"Def", "AsyncDef"} )

    CursorBounded == i <= N + 1

end define;

process scanner = "scanner"
begin
    ScanLoop:
        while i <= N do
            ProcessLine:
                if Lines[i] \in {"Def", "AsyncDef"} /\ ~in_sig then
                    sig_start := i;
                    sig_async := (Lines[i] = "AsyncDef");
                    if Conts[i] then
                        in_sig := TRUE;
                    else
                        skeletons := skeletons \cup
                            {[ line_num |-> sig_start,
                               is_async |-> sig_async ]};
                    end if;
                elsif in_sig then
                    if ~Conts[i] then
                        skeletons := skeletons \cup
                            {[ line_num |-> sig_start,
                               is_async |-> sig_async ]};
                        in_sig := FALSE;
                    end if;
                end if;
            Advance:
                i := i + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "359b6720" /\ chksum(tla) = "9b06d347")
VARIABLES pc, i, skeletons, in_sig, sig_start, sig_async

(* define statement *)
OneIndexed ==
    \A s \in skeletons : s.line_num >= 1

LineNumberCorrect ==
    \A s \in skeletons :
        /\ s.line_num >= 1
        /\ s.line_num <= N
        /\ Lines[s.line_num] \in {"Def", "AsyncDef"}
        /\ s.is_async = (Lines[s.line_num] = "AsyncDef")

MultiLineStable ==
    \A s \in skeletons :
        Lines[s.line_num] \in {"Def", "AsyncDef"}

NoGaps ==
    i > N =>
        ( \A k \in 1..N :
            Lines[k] \in {"Def", "AsyncDef"} =>
                \E s \in skeletons : s.line_num = k )

SigStartValid ==
    in_sig =>
        ( /\ sig_start >= 1
          /\ sig_start <= N
          /\ Lines[sig_start] \in {"Def", "AsyncDef"} )

CursorBounded == i <= N + 1


vars == << pc, i, skeletons, in_sig, sig_start, sig_async >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ i = 1
        /\ skeletons = {}
        /\ in_sig = FALSE
        /\ sig_start = 0
        /\ sig_async = FALSE
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF i <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessLine"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << i, skeletons, in_sig, sig_start, sig_async >>

ProcessLine == /\ pc["scanner"] = "ProcessLine"
               /\ IF Lines[i] \in {"Def", "AsyncDef"} /\ ~in_sig
                     THEN /\ sig_start' = i
                          /\ sig_async' = (Lines[i] = "AsyncDef")
                          /\ IF Conts[i]
                                THEN /\ in_sig' = TRUE
                                     /\ UNCHANGED skeletons
                                ELSE /\ skeletons' = (         skeletons \cup
                                                      {[ line_num |-> sig_start',
                                                         is_async |-> sig_async' ]})
                                     /\ UNCHANGED in_sig
                     ELSE /\ IF in_sig
                                THEN /\ IF ~Conts[i]
                                           THEN /\ skeletons' = (         skeletons \cup
                                                                 {[ line_num |-> sig_start,
                                                                    is_async |-> sig_async ]})
                                                /\ in_sig' = FALSE
                                           ELSE /\ TRUE
                                                /\ UNCHANGED << skeletons, 
                                                                in_sig >>
                                ELSE /\ TRUE
                                     /\ UNCHANGED << skeletons, in_sig >>
                          /\ UNCHANGED << sig_start, sig_async >>
               /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
               /\ i' = i

Advance == /\ pc["scanner"] = "Advance"
           /\ i' = i + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << skeletons, in_sig, sig_start, sig_async >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << i, skeletons, in_sig, sig_start, sig_async >>

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
