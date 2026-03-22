---- MODULE scanner_typescript_line_ranges ----

EXTENDS Integers, FiniteSets, TLC

\* Input lines: types of declarations found at each line position
\* "Func" = function declaration, "Arrow" = arrow function, "Method" = class method
\* "ClassOpen" = class opening, "Other" = non-declaration line, "Cont" = continuation
Lines == << "Func", "Other", "ClassOpen", "Method", "Arrow", "Other", "Func" >>
Conts == << FALSE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE >>
N == 7

(* --algorithm ScannerTypeScriptLineRanges

variables
    i         = 1,
    skeletons = {},
    in_sig    = FALSE,
    sig_start = 0;

define
    OneIndexed ==
        \A s \in skeletons : s.line_num >= 1

    LineNumberCorrect ==
        \A s \in skeletons :
            /\ s.line_num >= 1
            /\ s.line_num <= N
            /\ Lines[s.line_num] \in {"Func", "Arrow", "Method"}

    NoGaps ==
        i > N =>
            ( \A k \in 1..N :
                Lines[k] \in {"Func", "Arrow", "Method"} =>
                    \E s \in skeletons : s.line_num = k )

    CursorBounded == i <= N + 1
end define;

process scanner = "scanner"
begin
    ScanLoop:
        while i <= N do
            ProcessLine:
                if Lines[i] \in {"Func", "Arrow", "Method"} /\ ~in_sig then
                    sig_start := i;
                    if Conts[i] then
                        in_sig := TRUE;
                    else
                        skeletons := skeletons \cup {[line_num |-> i]};
                    end if;
                elsif in_sig then
                    if ~Conts[i] then
                        skeletons := skeletons \cup {[line_num |-> sig_start]};
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
\* BEGIN TRANSLATION (chksum(pcal) = "f96d8712" /\ chksum(tla) = "672a87c0")
VARIABLES pc, i, skeletons, in_sig, sig_start

(* define statement *)
OneIndexed ==
    \A s \in skeletons : s.line_num >= 1

LineNumberCorrect ==
    \A s \in skeletons :
        /\ s.line_num >= 1
        /\ s.line_num <= N
        /\ Lines[s.line_num] \in {"Func", "Arrow", "Method"}

NoGaps ==
    i > N =>
        ( \A k \in 1..N :
            Lines[k] \in {"Func", "Arrow", "Method"} =>
                \E s \in skeletons : s.line_num = k )

CursorBounded == i <= N + 1


vars == << pc, i, skeletons, in_sig, sig_start >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ i = 1
        /\ skeletons = {}
        /\ in_sig = FALSE
        /\ sig_start = 0
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF i <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessLine"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << i, skeletons, in_sig, sig_start >>

ProcessLine == /\ pc["scanner"] = "ProcessLine"
               /\ IF Lines[i] \in {"Func", "Arrow", "Method"} /\ ~in_sig
                     THEN /\ sig_start' = i
                          /\ IF Conts[i]
                                THEN /\ in_sig' = TRUE
                                     /\ UNCHANGED skeletons
                                ELSE /\ skeletons' = (skeletons \cup {[line_num |-> i]})
                                     /\ UNCHANGED in_sig
                     ELSE /\ IF in_sig
                                THEN /\ IF ~Conts[i]
                                           THEN /\ skeletons' = (skeletons \cup {[line_num |-> sig_start]})
                                                /\ in_sig' = FALSE
                                           ELSE /\ TRUE
                                                /\ UNCHANGED << skeletons, 
                                                                in_sig >>
                                ELSE /\ TRUE
                                     /\ UNCHANGED << skeletons, in_sig >>
                          /\ UNCHANGED sig_start
               /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
               /\ i' = i

Advance == /\ pc["scanner"] = "Advance"
           /\ i' = i + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << skeletons, in_sig, sig_start >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << i, skeletons, in_sig, sig_start >>

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
