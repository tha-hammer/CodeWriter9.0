---- MODULE SeamReportComplete ----
EXTENDS Integers, TLC

CONSTANTS
    MaxMismatches,
    MaxUnresolved,
    MaxSatisfied

(* --algorithm SeamReportComplete

variables
    phase     = "init",
    mm_count  = 0,
    ur_count  = 0,
    sat_count = 0,
    total     = 0;

define

    TotalEdges == MaxMismatches + MaxUnresolved + MaxSatisfied

    CurrentSum == mm_count + ur_count + sat_count

    CompletenessHolds ==
        phase = "done" => CurrentSum = total

    MonotonicProgress ==
        phase # "init" => CurrentSum <= total

    NonNegative ==
        /\ mm_count  >= 0
        /\ ur_count  >= 0
        /\ sat_count >= 0
        /\ total     >= 0

    TotalIsN ==
        phase # "init" => total = TotalEdges

    FinalCorrectness ==
        phase = "done" =>
            /\ mm_count  = MaxMismatches
            /\ ur_count  = MaxUnresolved
            /\ sat_count = MaxSatisfied
            /\ total     = TotalEdges
            /\ CurrentSum = TotalEdges

    SeamInvariants ==
        /\ CompletenessHolds
        /\ MonotonicProgress
        /\ NonNegative
        /\ TotalIsN
        /\ FinalCorrectness

end define;

fair process checker = "checker"
begin
    InitReport:
        total := TotalEdges;
        phase := "processing";

    Processing:
        while mm_count + ur_count + sat_count < TotalEdges do
            ProcessEdge:
            either
                await mm_count < MaxMismatches;
                mm_count := mm_count + 1;
            or
                await ur_count < MaxUnresolved;
                ur_count := ur_count + 1;
            or
                await sat_count < MaxSatisfied;
                sat_count := sat_count + 1;
            end either;
        end while;

    FinalizeReport:
        phase := "done";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e99f8dc6" /\ chksum(tla) = "6e8a8127")
VARIABLES pc, phase, mm_count, ur_count, sat_count, total

(* define statement *)
TotalEdges == MaxMismatches + MaxUnresolved + MaxSatisfied

CurrentSum == mm_count + ur_count + sat_count

CompletenessHolds ==
    phase = "done" => CurrentSum = total

MonotonicProgress ==
    phase # "init" => CurrentSum <= total

NonNegative ==
    /\ mm_count  >= 0
    /\ ur_count  >= 0
    /\ sat_count >= 0
    /\ total     >= 0

TotalIsN ==
    phase # "init" => total = TotalEdges

FinalCorrectness ==
    phase = "done" =>
        /\ mm_count  = MaxMismatches
        /\ ur_count  = MaxUnresolved
        /\ sat_count = MaxSatisfied
        /\ total     = TotalEdges
        /\ CurrentSum = TotalEdges

SeamInvariants ==
    /\ CompletenessHolds
    /\ MonotonicProgress
    /\ NonNegative
    /\ TotalIsN
    /\ FinalCorrectness


vars == << pc, phase, mm_count, ur_count, sat_count, total >>

ProcSet == {"checker"}

Init == (* Global variables *)
        /\ phase = "init"
        /\ mm_count = 0
        /\ ur_count = 0
        /\ sat_count = 0
        /\ total = 0
        /\ pc = [self \in ProcSet |-> "InitReport"]

InitReport == /\ pc["checker"] = "InitReport"
              /\ total' = TotalEdges
              /\ phase' = "processing"
              /\ pc' = [pc EXCEPT !["checker"] = "Processing"]
              /\ UNCHANGED << mm_count, ur_count, sat_count >>

Processing == /\ pc["checker"] = "Processing"
              /\ IF mm_count + ur_count + sat_count < TotalEdges
                    THEN /\ pc' = [pc EXCEPT !["checker"] = "ProcessEdge"]
                    ELSE /\ pc' = [pc EXCEPT !["checker"] = "FinalizeReport"]
              /\ UNCHANGED << phase, mm_count, ur_count, sat_count, total >>

ProcessEdge == /\ pc["checker"] = "ProcessEdge"
               /\ \/ /\ mm_count < MaxMismatches
                     /\ mm_count' = mm_count + 1
                     /\ UNCHANGED <<ur_count, sat_count>>
                  \/ /\ ur_count < MaxUnresolved
                     /\ ur_count' = ur_count + 1
                     /\ UNCHANGED <<mm_count, sat_count>>
                  \/ /\ sat_count < MaxSatisfied
                     /\ sat_count' = sat_count + 1
                     /\ UNCHANGED <<mm_count, ur_count>>
               /\ pc' = [pc EXCEPT !["checker"] = "Processing"]
               /\ UNCHANGED << phase, total >>

FinalizeReport == /\ pc["checker"] = "FinalizeReport"
                  /\ phase' = "done"
                  /\ pc' = [pc EXCEPT !["checker"] = "Done"]
                  /\ UNCHANGED << mm_count, ur_count, sat_count, total >>

checker == InitReport \/ Processing \/ ProcessEdge \/ FinalizeReport

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == checker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(checker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
