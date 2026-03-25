---- MODULE OrchestrateReviewsSelectsPasses ----

EXTENDS FiniteSets, TLC

AllPasses == {"artifacts", "coverage", "interaction", "abstraction_gap", "imports"}

(* --algorithm OrchestrateReviewsSelectsPasses

variables
    Phase     = "pre",
    Mode      = "self",
    executed  = {},
    exec_done = FALSE;

define

    TypeOK == executed \subseteq AllPasses

    PreSkipsImports ==
        Phase = "pre" => ~("imports" \in executed)

    PostOnlyImports ==
        (Phase = "post" /\ exec_done) => (executed = {"imports"})

    ExternalNoInteraction ==
        Mode = "external" => ~("interaction" \in executed)

    AllSelfComplete ==
        (Phase = "all" /\ Mode = "self" /\ exec_done) =>
        (executed = AllPasses)

    AllExternalComplete ==
        (Phase = "all" /\ Mode = "external" /\ exec_done) =>
        (executed = {"artifacts", "coverage", "abstraction_gap", "imports"})

    PreSelfComplete ==
        (Phase = "pre" /\ Mode = "self" /\ exec_done) =>
        (executed = {"artifacts", "coverage", "interaction", "abstraction_gap"})

    PreExternalSubset ==
        (Phase = "pre" /\ Mode = "external") =>
        (executed \subseteq {"artifacts", "coverage", "abstraction_gap"})

    PreExternalComplete ==
        (Phase = "pre" /\ Mode = "external" /\ exec_done) =>
        (executed = {"artifacts", "coverage", "abstraction_gap"})

    SelectionCorrect ==
        exec_done =>
        (executed =
            IF Phase = "pre"
            THEN (IF Mode = "self"
                  THEN AllPasses \ {"imports"}
                  ELSE (AllPasses \ {"interaction"}) \ {"imports"})
            ELSE IF Phase = "post"
                 THEN {"imports"}
                 ELSE (IF Mode = "self"
                       THEN AllPasses
                       ELSE AllPasses \ {"interaction"}))

end define;

fair process Orchestrator = "main"
begin
    ChoosePhase:
        either Phase := "pre";
        or     Phase := "post";
        or     Phase := "all";
        end either;

    ChooseMode:
        either Mode := "self";
        or     Mode := "external";
        end either;

    Select:
        executed :=
            IF Phase = "pre"
            THEN (IF Mode = "self"
                  THEN AllPasses \ {"imports"}
                  ELSE (AllPasses \ {"interaction"}) \ {"imports"})
            ELSE IF Phase = "post"
                 THEN {"imports"}
                 ELSE (IF Mode = "self"
                       THEN AllPasses
                       ELSE AllPasses \ {"interaction"});

    Finish:
        exec_done := TRUE;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "66a2d595" /\ chksum(tla) = "90abb1bc")
VARIABLES pc, Phase, Mode, executed, exec_done

(* define statement *)
TypeOK == executed \subseteq AllPasses

PreSkipsImports ==
    Phase = "pre" => ~("imports" \in executed)

PostOnlyImports ==
    (Phase = "post" /\ exec_done) => (executed = {"imports"})

ExternalNoInteraction ==
    Mode = "external" => ~("interaction" \in executed)

AllSelfComplete ==
    (Phase = "all" /\ Mode = "self" /\ exec_done) =>
    (executed = AllPasses)

AllExternalComplete ==
    (Phase = "all" /\ Mode = "external" /\ exec_done) =>
    (executed = {"artifacts", "coverage", "abstraction_gap", "imports"})

PreSelfComplete ==
    (Phase = "pre" /\ Mode = "self" /\ exec_done) =>
    (executed = {"artifacts", "coverage", "interaction", "abstraction_gap"})

PreExternalSubset ==
    (Phase = "pre" /\ Mode = "external") =>
    (executed \subseteq {"artifacts", "coverage", "abstraction_gap"})

PreExternalComplete ==
    (Phase = "pre" /\ Mode = "external" /\ exec_done) =>
    (executed = {"artifacts", "coverage", "abstraction_gap"})

SelectionCorrect ==
    exec_done =>
    (executed =
        IF Phase = "pre"
        THEN (IF Mode = "self"
              THEN AllPasses \ {"imports"}
              ELSE (AllPasses \ {"interaction"}) \ {"imports"})
        ELSE IF Phase = "post"
             THEN {"imports"}
             ELSE (IF Mode = "self"
                   THEN AllPasses
                   ELSE AllPasses \ {"interaction"}))


vars == << pc, Phase, Mode, executed, exec_done >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ Phase = "pre"
        /\ Mode = "self"
        /\ executed = {}
        /\ exec_done = FALSE
        /\ pc = [self \in ProcSet |-> "ChoosePhase"]

ChoosePhase == /\ pc["main"] = "ChoosePhase"
               /\ \/ /\ Phase' = "pre"
                  \/ /\ Phase' = "post"
                  \/ /\ Phase' = "all"
               /\ pc' = [pc EXCEPT !["main"] = "ChooseMode"]
               /\ UNCHANGED << Mode, executed, exec_done >>

ChooseMode == /\ pc["main"] = "ChooseMode"
              /\ \/ /\ Mode' = "self"
                 \/ /\ Mode' = "external"
              /\ pc' = [pc EXCEPT !["main"] = "Select"]
              /\ UNCHANGED << Phase, executed, exec_done >>

Select == /\ pc["main"] = "Select"
          /\ executed' = (IF Phase = "pre"
                          THEN (IF Mode = "self"
                                THEN AllPasses \ {"imports"}
                                ELSE (AllPasses \ {"interaction"}) \ {"imports"})
                          ELSE IF Phase = "post"
                               THEN {"imports"}
                               ELSE (IF Mode = "self"
                                     THEN AllPasses
                                     ELSE AllPasses \ {"interaction"}))
          /\ pc' = [pc EXCEPT !["main"] = "Finish"]
          /\ UNCHANGED << Phase, Mode, exec_done >>

Finish == /\ pc["main"] = "Finish"
          /\ exec_done' = TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << Phase, Mode, executed >>

Orchestrator == ChoosePhase \/ ChooseMode \/ Select \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
