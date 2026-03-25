---- MODULE PlanReviewPhaseFiltering ----

EXTENDS Integers, FiniteSets, TLC

AllPasses ==
    {"artifacts", "coverage", "interaction", "abstraction_gap", "imports"}

PhaseModePasses(ph, md) ==
    IF ph = "post" THEN
        {"imports"}
    ELSE IF ph = "pre" THEN
        IF md = "external"
            THEN {"artifacts", "coverage", "abstraction_gap"}
            ELSE {"artifacts", "coverage", "interaction", "abstraction_gap"}
    ELSE
        IF md = "external"
            THEN {"artifacts", "coverage", "abstraction_gap", "imports"}
            ELSE AllPasses

ExpectedPassesFor(ph, md, av) ==
    IF ph = "post" THEN
        {"imports"}
    ELSE IF av = "fail" THEN
        {"artifacts"}
    ELSE
        PhaseModePasses(ph, md)

ShouldExecutePass(ph, md, av, p) ==
    IF ph = "post" THEN
        p = "imports"
    ELSE IF av = "fail" THEN
        p = "artifacts"
    ELSE
        p \in PhaseModePasses(ph, md)

(* --algorithm PlanReviewPhaseFiltering

variables
    Phase            \in {"pre", "post", "all"},
    Mode             \in {"self", "external"},
    ArtifactsVerdict \in {"pass", "fail"},
    executed           = {},
    remaining          = {"artifacts", "coverage", "interaction",
                          "abstraction_gap", "imports"},
    current_pass       = "",
    orchestration_done = FALSE;

define

    PreSkipsImports ==
        Phase = "pre" => "imports" \notin executed

    ExternalNoInteraction ==
        Mode = "external" => "interaction" \notin executed

    PreExternalSubset ==
        (Phase = "pre" /\ Mode = "external") =>
            executed \subseteq {"artifacts", "coverage", "abstraction_gap"}

    PostOnlyImports ==
        (Phase = "post" /\ orchestration_done) => executed = {"imports"}

    AllSelfComplete ==
        (Phase = "all" /\ Mode = "self" /\
         ArtifactsVerdict = "pass" /\ orchestration_done) =>
            executed = AllPasses

    AllExternalComplete ==
        (Phase = "all" /\ Mode = "external" /\
         ArtifactsVerdict = "pass" /\ orchestration_done) =>
            executed = {"artifacts", "coverage", "abstraction_gap", "imports"}

    PreSelfComplete ==
        (Phase = "pre" /\ Mode = "self" /\
         ArtifactsVerdict = "pass" /\ orchestration_done) =>
            executed = {"artifacts", "coverage", "interaction", "abstraction_gap"}

    PreExternalComplete ==
        (Phase = "pre" /\ Mode = "external" /\
         ArtifactsVerdict = "pass" /\ orchestration_done) =>
            executed = {"artifacts", "coverage", "abstraction_gap"}

    FinalSetCorrect ==
        orchestration_done =>
            executed = ExpectedPassesFor(Phase, Mode, ArtifactsVerdict)

    ExecutedSubsetAllPasses ==
        executed \subseteq AllPasses

end define;

fair process orchestrator = "main"
begin
    Orchestrate:
        while remaining # {} do
            with p \in remaining do
                current_pass := p ||
                remaining    := remaining \ {p};
            end with;
            RunOrSkip:
                if ShouldExecutePass(Phase, Mode, ArtifactsVerdict, current_pass) then
                    executed := executed \cup {current_pass};
                end if;
        end while;
    Finish:
        orchestration_done := TRUE;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "9750d6fe" /\ chksum(tla) = "26bcafbb")
VARIABLES pc, Phase, Mode, ArtifactsVerdict, executed, remaining, 
          current_pass, orchestration_done

(* define statement *)
PreSkipsImports ==
    Phase = "pre" => "imports" \notin executed

ExternalNoInteraction ==
    Mode = "external" => "interaction" \notin executed

PreExternalSubset ==
    (Phase = "pre" /\ Mode = "external") =>
        executed \subseteq {"artifacts", "coverage", "abstraction_gap"}

PostOnlyImports ==
    (Phase = "post" /\ orchestration_done) => executed = {"imports"}

AllSelfComplete ==
    (Phase = "all" /\ Mode = "self" /\
     ArtifactsVerdict = "pass" /\ orchestration_done) =>
        executed = AllPasses

AllExternalComplete ==
    (Phase = "all" /\ Mode = "external" /\
     ArtifactsVerdict = "pass" /\ orchestration_done) =>
        executed = {"artifacts", "coverage", "abstraction_gap", "imports"}

PreSelfComplete ==
    (Phase = "pre" /\ Mode = "self" /\
     ArtifactsVerdict = "pass" /\ orchestration_done) =>
        executed = {"artifacts", "coverage", "interaction", "abstraction_gap"}

PreExternalComplete ==
    (Phase = "pre" /\ Mode = "external" /\
     ArtifactsVerdict = "pass" /\ orchestration_done) =>
        executed = {"artifacts", "coverage", "abstraction_gap"}

FinalSetCorrect ==
    orchestration_done =>
        executed = ExpectedPassesFor(Phase, Mode, ArtifactsVerdict)

ExecutedSubsetAllPasses ==
    executed \subseteq AllPasses


vars == << pc, Phase, Mode, ArtifactsVerdict, executed, remaining, 
           current_pass, orchestration_done >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ Phase \in {"pre", "post", "all"}
        /\ Mode \in {"self", "external"}
        /\ ArtifactsVerdict \in {"pass", "fail"}
        /\ executed = {}
        /\ remaining = {"artifacts", "coverage", "interaction",
                        "abstraction_gap", "imports"}
        /\ current_pass = ""
        /\ orchestration_done = FALSE
        /\ pc = [self \in ProcSet |-> "Orchestrate"]

Orchestrate == /\ pc["main"] = "Orchestrate"
               /\ IF remaining # {}
                     THEN /\ \E p \in remaining:
                               /\ current_pass' = p
                               /\ remaining' = remaining \ {p}
                          /\ pc' = [pc EXCEPT !["main"] = "RunOrSkip"]
                     ELSE /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                          /\ UNCHANGED << remaining, current_pass >>
               /\ UNCHANGED << Phase, Mode, ArtifactsVerdict, executed, 
                               orchestration_done >>

RunOrSkip == /\ pc["main"] = "RunOrSkip"
             /\ IF ShouldExecutePass(Phase, Mode, ArtifactsVerdict, current_pass)
                   THEN /\ executed' = (executed \cup {current_pass})
                   ELSE /\ TRUE
                        /\ UNCHANGED executed
             /\ pc' = [pc EXCEPT !["main"] = "Orchestrate"]
             /\ UNCHANGED << Phase, Mode, ArtifactsVerdict, remaining, 
                             current_pass, orchestration_done >>

Finish == /\ pc["main"] = "Finish"
          /\ orchestration_done' = TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << Phase, Mode, ArtifactsVerdict, executed, remaining, 
                          current_pass >>

orchestrator == Orchestrate \/ RunOrSkip \/ Finish

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
