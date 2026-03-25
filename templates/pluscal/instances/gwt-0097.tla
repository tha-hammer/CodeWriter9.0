------------------------ MODULE ImportsGating ------------------------

EXTENDS Integers, FiniteSets, TLC

CONSTANTS MaxSteps

(* --algorithm ImportsGating

variables
    ag_present = FALSE,
    ag_verdict = "none",
    imports_verdict = "pending",
    check_invoked = FALSE,
    step_count = 0;

define

    Verdict == {"pass", "fail", "warning", "blocked"}

    PermitsScheduling == {"pass", "warning"}

    ImportsIsResolved ==
        check_invoked => imports_verdict \in {"scheduled", "blocked"}

    SingleDependency ==
        imports_verdict = "scheduled" =>
            (ag_present /\ ag_verdict \in PermitsScheduling)

    FailBlocks ==
        (ag_present /\ ag_verdict = "fail") =>
            (check_invoked => imports_verdict = "blocked")

    BlockedCascades ==
        (ag_present /\ ag_verdict = "blocked") =>
            (check_invoked => imports_verdict = "blocked")

    WarningPermits ==
        (ag_present /\ ag_verdict = "warning") =>
            (check_invoked => imports_verdict = "scheduled")

    PassPermits ==
        (ag_present /\ ag_verdict = "pass") =>
            (check_invoked => imports_verdict = "scheduled")

    MissingBlocks ==
        (~ag_present) =>
            (check_invoked => imports_verdict = "blocked")

    BoundedExecution == step_count <= MaxSteps

end define;

fair process evaluator = "main"
begin
    SetAbstractionGapVerdict:
        either
            skip;
        or
            with v \in Verdict do
                ag_present := TRUE ||
                ag_verdict := v;
            end with;
        end either;
        step_count := step_count + 1;
    EvaluateImports:
        check_invoked := TRUE;
        step_count := step_count + 1;
        if ag_present /\ ag_verdict \in PermitsScheduling then
            imports_verdict := "scheduled";
        else
            imports_verdict := "blocked";
        end if;
    Finish:
        assert ImportsIsResolved;
        assert SingleDependency;
        assert FailBlocks;
        assert BlockedCascades;
        assert WarningPermits;
        assert PassPermits;
        assert MissingBlocks;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "2d8c0636" /\ chksum(tla) = "303bfc")
VARIABLES pc, ag_present, ag_verdict, imports_verdict, check_invoked, 
          step_count

(* define statement *)
Verdict == {"pass", "fail", "warning", "blocked"}

PermitsScheduling == {"pass", "warning"}

ImportsIsResolved ==
    check_invoked => imports_verdict \in {"scheduled", "blocked"}

SingleDependency ==
    imports_verdict = "scheduled" =>
        (ag_present /\ ag_verdict \in PermitsScheduling)

FailBlocks ==
    (ag_present /\ ag_verdict = "fail") =>
        (check_invoked => imports_verdict = "blocked")

BlockedCascades ==
    (ag_present /\ ag_verdict = "blocked") =>
        (check_invoked => imports_verdict = "blocked")

WarningPermits ==
    (ag_present /\ ag_verdict = "warning") =>
        (check_invoked => imports_verdict = "scheduled")

PassPermits ==
    (ag_present /\ ag_verdict = "pass") =>
        (check_invoked => imports_verdict = "scheduled")

MissingBlocks ==
    (~ag_present) =>
        (check_invoked => imports_verdict = "blocked")

BoundedExecution == step_count <= MaxSteps


vars == << pc, ag_present, ag_verdict, imports_verdict, check_invoked, 
           step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ ag_present = FALSE
        /\ ag_verdict = "none"
        /\ imports_verdict = "pending"
        /\ check_invoked = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "SetAbstractionGapVerdict"]

SetAbstractionGapVerdict == /\ pc["main"] = "SetAbstractionGapVerdict"
                            /\ \/ /\ TRUE
                                  /\ UNCHANGED <<ag_present, ag_verdict>>
                               \/ /\ \E v \in Verdict:
                                       /\ ag_present' = TRUE
                                       /\ ag_verdict' = v
                            /\ step_count' = step_count + 1
                            /\ pc' = [pc EXCEPT !["main"] = "EvaluateImports"]
                            /\ UNCHANGED << imports_verdict, check_invoked >>

EvaluateImports == /\ pc["main"] = "EvaluateImports"
                   /\ check_invoked' = TRUE
                   /\ step_count' = step_count + 1
                   /\ IF ag_present /\ ag_verdict \in PermitsScheduling
                         THEN /\ imports_verdict' = "scheduled"
                         ELSE /\ imports_verdict' = "blocked"
                   /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                   /\ UNCHANGED << ag_present, ag_verdict >>

Finish == /\ pc["main"] = "Finish"
          /\ Assert(ImportsIsResolved, 
                    "Failure of assertion at line 74, column 9.")
          /\ Assert(SingleDependency, 
                    "Failure of assertion at line 75, column 9.")
          /\ Assert(FailBlocks, "Failure of assertion at line 76, column 9.")
          /\ Assert(BlockedCascades, 
                    "Failure of assertion at line 77, column 9.")
          /\ Assert(WarningPermits, 
                    "Failure of assertion at line 78, column 9.")
          /\ Assert(PassPermits, 
                    "Failure of assertion at line 79, column 9.")
          /\ Assert(MissingBlocks, 
                    "Failure of assertion at line 80, column 9.")
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << ag_present, ag_verdict, imports_verdict, 
                          check_invoked, step_count >>

evaluator == SetAbstractionGapVerdict \/ EvaluateImports \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == evaluator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(evaluator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
