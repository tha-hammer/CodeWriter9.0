---- MODULE AbstractionGapGating ----

EXTENDS Sequences, FiniteSets, TLC

Verdict == {"pass", "fail", "warning", "blocked"}

TerminalVerdicts == {"pass", "fail", "warning", "blocked"}

PermittedVerdicts == {"pass", "warning"}

BlockingVerdicts == {"fail", "blocked"}

(* --algorithm AbstractionGapGating

variables
    coverage_verdict \in Verdict,
    interaction_verdict \in Verdict,
    ag_scheduled = FALSE,
    ag_blocked = FALSE,
    evaluated = FALSE;

define

    BothTerminal ==
        coverage_verdict \in TerminalVerdicts /\ interaction_verdict \in TerminalVerdicts

    BothRequired ==
        ag_scheduled =>
            coverage_verdict \in PermittedVerdicts /\
            interaction_verdict \in PermittedVerdicts

    FailBlocks ==
        (coverage_verdict = "fail" \/ interaction_verdict = "fail") =>
            ~ag_scheduled /\ (evaluated => ag_blocked)

    BlockedPropagates ==
        (coverage_verdict = "blocked" \/ interaction_verdict = "blocked") =>
            ~ag_scheduled /\ (evaluated => ag_blocked)

    WarningPermits ==
        (coverage_verdict = "warning" /\ interaction_verdict = "warning" /\ evaluated) =>
            ag_scheduled /\ ~ag_blocked

    MutualExclusion ==
        ~(ag_scheduled /\ ag_blocked)

    EvaluatedFinal ==
        evaluated => (ag_scheduled \/ ag_blocked)

end define;

fair process checker = "checker"
begin
    Evaluate:
        if coverage_verdict \in PermittedVerdicts /\ interaction_verdict \in PermittedVerdicts then
            ag_scheduled := TRUE;
            ag_blocked := FALSE;
        else
            ag_scheduled := FALSE;
            ag_blocked := TRUE;
        end if;
    Finish:
        evaluated := TRUE;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "91845a25" /\ chksum(tla) = "5bca3551")
VARIABLES pc, coverage_verdict, interaction_verdict, ag_scheduled, ag_blocked, 
          evaluated

(* define statement *)
BothTerminal ==
    coverage_verdict \in TerminalVerdicts /\ interaction_verdict \in TerminalVerdicts

BothRequired ==
    ag_scheduled =>
        coverage_verdict \in PermittedVerdicts /\
        interaction_verdict \in PermittedVerdicts

FailBlocks ==
    (coverage_verdict = "fail" \/ interaction_verdict = "fail") =>
        ~ag_scheduled /\ (evaluated => ag_blocked)

BlockedPropagates ==
    (coverage_verdict = "blocked" \/ interaction_verdict = "blocked") =>
        ~ag_scheduled /\ (evaluated => ag_blocked)

WarningPermits ==
    (coverage_verdict = "warning" /\ interaction_verdict = "warning" /\ evaluated) =>
        ag_scheduled /\ ~ag_blocked

MutualExclusion ==
    ~(ag_scheduled /\ ag_blocked)

EvaluatedFinal ==
    evaluated => (ag_scheduled \/ ag_blocked)


vars == << pc, coverage_verdict, interaction_verdict, ag_scheduled, 
           ag_blocked, evaluated >>

ProcSet == {"checker"}

Init == (* Global variables *)
        /\ coverage_verdict \in Verdict
        /\ interaction_verdict \in Verdict
        /\ ag_scheduled = FALSE
        /\ ag_blocked = FALSE
        /\ evaluated = FALSE
        /\ pc = [self \in ProcSet |-> "Evaluate"]

Evaluate == /\ pc["checker"] = "Evaluate"
            /\ IF coverage_verdict \in PermittedVerdicts /\ interaction_verdict \in PermittedVerdicts
                  THEN /\ ag_scheduled' = TRUE
                       /\ ag_blocked' = FALSE
                  ELSE /\ ag_scheduled' = FALSE
                       /\ ag_blocked' = TRUE
            /\ pc' = [pc EXCEPT !["checker"] = "Finish"]
            /\ UNCHANGED << coverage_verdict, interaction_verdict, evaluated >>

Finish == /\ pc["checker"] = "Finish"
          /\ evaluated' = TRUE
          /\ pc' = [pc EXCEPT !["checker"] = "Done"]
          /\ UNCHANGED << coverage_verdict, interaction_verdict, ag_scheduled, 
                          ag_blocked >>

checker == Evaluate \/ Finish

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
