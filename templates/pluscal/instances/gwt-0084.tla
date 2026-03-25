---- MODULE OrchestrateReviewsInit ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    MaxRetries,
    PassNames

(*--algorithm OrchestrateReviewsInit

variables
    max_retries      = MaxRetries,
    attempt_counts   = [p \in PassNames |-> 0],
    budget_exhausted = {},
    completed_passes = {},
    active_pass      = CHOOSE p \in PassNames : TRUE,
    phase            = "init";

define

    TypeOK ==
        /\ max_retries \in Nat
        /\ \A p \in PassNames : attempt_counts[p] \in Nat
        /\ budget_exhausted \subseteq PassNames
        /\ completed_passes \subseteq PassNames
        /\ phase \in {"init", "running", "done"}

    \* max_retries is never mutated; it always equals the value supplied at init
    DefaultRetries ==
        max_retries = MaxRetries

    \* No pass ever accumulates more than max_retries + 1 total attempts
    TotalAttemptsPerPass ==
        \A p \in PassNames : attempt_counts[p] <= max_retries + 1

    \* Attempt counters are non-negative
    CountsNonNegative ==
        \A p \in PassNames : attempt_counts[p] >= 0

    \* A pass enters budget_exhausted only once its counter has crossed the limit
    BudgetExhaustionSound ==
        \A p \in PassNames :
            p \in budget_exhausted => attempt_counts[p] > max_retries

    \* Any pass whose counter has crossed max_retries and has NOT succeeded
    \* must be in budget_exhausted.  Completed passes are exempt: a pass may
    \* succeed on its (max_retries+1)-th attempt, leaving the counter above
    \* max_retries while the pass legitimately belongs only in completed_passes.
    BudgetExhaustionComplete ==
        \A p \in PassNames :
            (attempt_counts[p] > max_retries /\ p \notin completed_passes)
                => p \in budget_exhausted

    \* Exhausted and completed sets never overlap
    DisjointTermination ==
        budget_exhausted \intersect completed_passes = {}

    \* Before execution begins every counter is zero
    InitialCountsZero ==
        phase = "init" =>
            \A p \in PassNames : attempt_counts[p] = 0

end define;

fair process orchestrator = "main"
begin
    InitBudget:
        assert \A p \in PassNames : attempt_counts[p] = 0;
        assert budget_exhausted = {};
        assert max_retries = MaxRetries;
        phase := "running";

    RunPasses:
        while (PassNames \ budget_exhausted) \ completed_passes /= {} do
            with p \in (PassNames \ budget_exhausted) \ completed_passes do
                active_pass := p;
            end with;

        AttemptAndOutcome:
            attempt_counts[active_pass] := attempt_counts[active_pass] + 1;
            either
                \* Pass succeeded on this attempt
                completed_passes := completed_passes \union {active_pass};
            or
                \* Pass failed; retire it if the budget ceiling has been reached
                if attempt_counts[active_pass] > max_retries then
                    budget_exhausted := budget_exhausted \union {active_pass};
                end if;
            end either;

        end while;

    Finish:
        phase := "done";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f3d94219" /\ chksum(tla) = "cc4fe62b")
VARIABLES pc, max_retries, attempt_counts, budget_exhausted, completed_passes, 
          active_pass, phase

(* define statement *)
TypeOK ==
    /\ max_retries \in Nat
    /\ \A p \in PassNames : attempt_counts[p] \in Nat
    /\ budget_exhausted \subseteq PassNames
    /\ completed_passes \subseteq PassNames
    /\ phase \in {"init", "running", "done"}


DefaultRetries ==
    max_retries = MaxRetries


TotalAttemptsPerPass ==
    \A p \in PassNames : attempt_counts[p] <= max_retries + 1


CountsNonNegative ==
    \A p \in PassNames : attempt_counts[p] >= 0


BudgetExhaustionSound ==
    \A p \in PassNames :
        p \in budget_exhausted => attempt_counts[p] > max_retries





BudgetExhaustionComplete ==
    \A p \in PassNames :
        (attempt_counts[p] > max_retries /\ p \notin completed_passes)
            => p \in budget_exhausted


DisjointTermination ==
    budget_exhausted \intersect completed_passes = {}


InitialCountsZero ==
    phase = "init" =>
        \A p \in PassNames : attempt_counts[p] = 0


vars == << pc, max_retries, attempt_counts, budget_exhausted, 
           completed_passes, active_pass, phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ max_retries = MaxRetries
        /\ attempt_counts = [p \in PassNames |-> 0]
        /\ budget_exhausted = {}
        /\ completed_passes = {}
        /\ active_pass = (CHOOSE p \in PassNames : TRUE)
        /\ phase = "init"
        /\ pc = [self \in ProcSet |-> "InitBudget"]

InitBudget == /\ pc["main"] = "InitBudget"
              /\ Assert(\A p \in PassNames : attempt_counts[p] = 0, 
                        "Failure of assertion at line 67, column 9.")
              /\ Assert(budget_exhausted = {}, 
                        "Failure of assertion at line 68, column 9.")
              /\ Assert(max_retries = MaxRetries, 
                        "Failure of assertion at line 69, column 9.")
              /\ phase' = "running"
              /\ pc' = [pc EXCEPT !["main"] = "RunPasses"]
              /\ UNCHANGED << max_retries, attempt_counts, budget_exhausted, 
                              completed_passes, active_pass >>

RunPasses == /\ pc["main"] = "RunPasses"
             /\ IF (PassNames \ budget_exhausted) \ completed_passes /= {}
                   THEN /\ \E p \in (PassNames \ budget_exhausted) \ completed_passes:
                             active_pass' = p
                        /\ pc' = [pc EXCEPT !["main"] = "AttemptAndOutcome"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                        /\ UNCHANGED active_pass
             /\ UNCHANGED << max_retries, attempt_counts, budget_exhausted, 
                             completed_passes, phase >>

AttemptAndOutcome == /\ pc["main"] = "AttemptAndOutcome"
                     /\ attempt_counts' = [attempt_counts EXCEPT ![active_pass] = attempt_counts[active_pass] + 1]
                     /\ \/ /\ completed_passes' = (completed_passes \union {active_pass})
                           /\ UNCHANGED budget_exhausted
                        \/ /\ IF attempt_counts'[active_pass] > max_retries
                                 THEN /\ budget_exhausted' = (budget_exhausted \union {active_pass})
                                 ELSE /\ TRUE
                                      /\ UNCHANGED budget_exhausted
                           /\ UNCHANGED completed_passes
                     /\ pc' = [pc EXCEPT !["main"] = "RunPasses"]
                     /\ UNCHANGED << max_retries, active_pass, phase >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "done"
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << max_retries, attempt_counts, budget_exhausted, 
                          completed_passes, active_pass >>

orchestrator == InitBudget \/ RunPasses \/ AttemptAndOutcome \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
====
