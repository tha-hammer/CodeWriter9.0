---- MODULE CorrectionAgentScopeConstraints ----

EXTENDS Integers, FiniteSets, TLC

PassTypes         == {"artifacts", "coverage", "interaction", "abstraction_gap", "imports"}
ModifiableTargets == {"context_files", "plan_text", "test_scaffolding"}
ForbiddenTargets  == {"source_code", "tla_specs", "bridge_artifacts"}
MaxSteps          == 10

(* --algorithm CorrectionAgentScopeConstraints

variables
    pass_type              = "coverage",
    modifications          = {},
    source_code_touched    = FALSE,
    tla_specs_touched      = FALSE,
    bridge_touched         = FALSE,
    phase                  = "selecting",
    step_count             = 0,
    human_review_items     = {},
    pipeline_steps_flagged = {};

define

    NoSourceModification ==
        source_code_touched = FALSE

    NoSpecModification ==
        tla_specs_touched = FALSE

    NoBridgeModification ==
        bridge_touched = FALSE

    AllForbiddenUntouched ==
        /\ NoSourceModification
        /\ NoSpecModification
        /\ NoBridgeModification

    ModificationsOnlyAllowed ==
        \A mod \in modifications : mod.target \in ModifiableTargets

    CoverageScope ==
        (pass_type = "coverage" /\ phase = "done") =>
            \E mod \in modifications :
                /\ mod.target = "test_scaffolding"
                /\ mod.action = "add_assertions"

    AbstractionGapScope ==
        (pass_type = "abstraction_gap" /\ phase = "done") =>
            \E mod \in modifications :
                /\ mod.target = "context_files"
                /\ mod.action = "copy_decision_checklist"

    ImportsScope ==
        (pass_type = "imports" /\ phase = "done") =>
            \E mod \in modifications :
                /\ mod.target = "context_files"
                /\ mod.action = "remove_dead_imports"

    ArtifactsScope ==
        (pass_type = "artifacts" /\ phase = "done") =>
            \E mod \in modifications :
                /\ mod.target = "plan_text"
                /\ mod.action = "list_pipeline_steps_to_rerun"

    ArtifactsNeverInvoked ==
        (pass_type = "artifacts" /\ phase = "done") =>
            pipeline_steps_flagged /= {}

    BoundedExecution ==
        step_count <= MaxSteps

    TypeInvariant ==
        /\ pass_type \in PassTypes
        /\ phase \in {"selecting", "correcting", "done"}
        /\ source_code_touched \in BOOLEAN
        /\ tla_specs_touched   \in BOOLEAN
        /\ bridge_touched      \in BOOLEAN

end define;

fair process agent = "correction_agent"
begin
    SelectPass:
        with pt \in PassTypes do
            pass_type := pt;
        end with;
        phase      := "correcting";
        step_count := step_count + 1;

    ApplyCorrection:
        if pass_type = "coverage" then
            modifications := modifications \cup
                {[target |-> "test_scaffolding", action |-> "add_assertions"]};
            phase := "done";
        elsif pass_type = "abstraction_gap" then
            modifications := modifications \cup
                {[target |-> "context_files", action |-> "copy_decision_checklist"]};
            phase := "done";
        elsif pass_type = "imports" then
            modifications := modifications \cup
                {[target |-> "context_files", action |-> "remove_dead_imports"]};
            human_review_items := human_review_items \cup {"wrong_abstractions"};
            phase := "done";
        elsif pass_type = "artifacts" then
            modifications := modifications \cup
                {[target |-> "plan_text", action |-> "list_pipeline_steps_to_rerun"]};
            pipeline_steps_flagged := pipeline_steps_flagged \cup
                {"bridge", "gen-tests", "verify"};
            phase := "done";
        else
            phase := "done";
        end if;

    CheckForbidden:
        assert source_code_touched = FALSE;
        assert tla_specs_touched   = FALSE;
        assert bridge_touched      = FALSE;
        step_count := step_count + 1;

    CheckModifiable:
        assert \A mod \in modifications : mod.target \in ModifiableTargets;
        step_count := step_count + 1;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "c626cbb7" /\ chksum(tla) = "de821d28")
VARIABLES pc, pass_type, modifications, source_code_touched, 
          tla_specs_touched, bridge_touched, phase, step_count, 
          human_review_items, pipeline_steps_flagged

(* define statement *)
NoSourceModification ==
    source_code_touched = FALSE

NoSpecModification ==
    tla_specs_touched = FALSE

NoBridgeModification ==
    bridge_touched = FALSE

AllForbiddenUntouched ==
    /\ NoSourceModification
    /\ NoSpecModification
    /\ NoBridgeModification

ModificationsOnlyAllowed ==
    \A mod \in modifications : mod.target \in ModifiableTargets

CoverageScope ==
    (pass_type = "coverage" /\ phase = "done") =>
        \E mod \in modifications :
            /\ mod.target = "test_scaffolding"
            /\ mod.action = "add_assertions"

AbstractionGapScope ==
    (pass_type = "abstraction_gap" /\ phase = "done") =>
        \E mod \in modifications :
            /\ mod.target = "context_files"
            /\ mod.action = "copy_decision_checklist"

ImportsScope ==
    (pass_type = "imports" /\ phase = "done") =>
        \E mod \in modifications :
            /\ mod.target = "context_files"
            /\ mod.action = "remove_dead_imports"

ArtifactsScope ==
    (pass_type = "artifacts" /\ phase = "done") =>
        \E mod \in modifications :
            /\ mod.target = "plan_text"
            /\ mod.action = "list_pipeline_steps_to_rerun"

ArtifactsNeverInvoked ==
    (pass_type = "artifacts" /\ phase = "done") =>
        pipeline_steps_flagged /= {}

BoundedExecution ==
    step_count <= MaxSteps

TypeInvariant ==
    /\ pass_type \in PassTypes
    /\ phase \in {"selecting", "correcting", "done"}
    /\ source_code_touched \in BOOLEAN
    /\ tla_specs_touched   \in BOOLEAN
    /\ bridge_touched      \in BOOLEAN


vars == << pc, pass_type, modifications, source_code_touched, 
           tla_specs_touched, bridge_touched, phase, step_count, 
           human_review_items, pipeline_steps_flagged >>

ProcSet == {"correction_agent"}

Init == (* Global variables *)
        /\ pass_type = "coverage"
        /\ modifications = {}
        /\ source_code_touched = FALSE
        /\ tla_specs_touched = FALSE
        /\ bridge_touched = FALSE
        /\ phase = "selecting"
        /\ step_count = 0
        /\ human_review_items = {}
        /\ pipeline_steps_flagged = {}
        /\ pc = [self \in ProcSet |-> "SelectPass"]

SelectPass == /\ pc["correction_agent"] = "SelectPass"
              /\ \E pt \in PassTypes:
                   pass_type' = pt
              /\ phase' = "correcting"
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["correction_agent"] = "ApplyCorrection"]
              /\ UNCHANGED << modifications, source_code_touched, 
                              tla_specs_touched, bridge_touched, 
                              human_review_items, pipeline_steps_flagged >>

ApplyCorrection == /\ pc["correction_agent"] = "ApplyCorrection"
                   /\ IF pass_type = "coverage"
                         THEN /\ modifications' = (             modifications \cup
                                                   {[target |-> "test_scaffolding", action |-> "add_assertions"]})
                              /\ phase' = "done"
                              /\ UNCHANGED << human_review_items, 
                                              pipeline_steps_flagged >>
                         ELSE /\ IF pass_type = "abstraction_gap"
                                    THEN /\ modifications' = (             modifications \cup
                                                              {[target |-> "context_files", action |-> "copy_decision_checklist"]})
                                         /\ phase' = "done"
                                         /\ UNCHANGED << human_review_items, 
                                                         pipeline_steps_flagged >>
                                    ELSE /\ IF pass_type = "imports"
                                               THEN /\ modifications' = (             modifications \cup
                                                                         {[target |-> "context_files", action |-> "remove_dead_imports"]})
                                                    /\ human_review_items' = (human_review_items \cup {"wrong_abstractions"})
                                                    /\ phase' = "done"
                                                    /\ UNCHANGED pipeline_steps_flagged
                                               ELSE /\ IF pass_type = "artifacts"
                                                          THEN /\ modifications' = (             modifications \cup
                                                                                    {[target |-> "plan_text", action |-> "list_pipeline_steps_to_rerun"]})
                                                               /\ pipeline_steps_flagged' = (                      pipeline_steps_flagged \cup
                                                                                             {"bridge", "gen-tests", "verify"})
                                                               /\ phase' = "done"
                                                          ELSE /\ phase' = "done"
                                                               /\ UNCHANGED << modifications, 
                                                                               pipeline_steps_flagged >>
                                                    /\ UNCHANGED human_review_items
                   /\ pc' = [pc EXCEPT !["correction_agent"] = "CheckForbidden"]
                   /\ UNCHANGED << pass_type, source_code_touched, 
                                   tla_specs_touched, bridge_touched, 
                                   step_count >>

CheckForbidden == /\ pc["correction_agent"] = "CheckForbidden"
                  /\ Assert(source_code_touched = FALSE, 
                            "Failure of assertion at line 116, column 9.")
                  /\ Assert(tla_specs_touched   = FALSE, 
                            "Failure of assertion at line 117, column 9.")
                  /\ Assert(bridge_touched      = FALSE, 
                            "Failure of assertion at line 118, column 9.")
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["correction_agent"] = "CheckModifiable"]
                  /\ UNCHANGED << pass_type, modifications, 
                                  source_code_touched, tla_specs_touched, 
                                  bridge_touched, phase, human_review_items, 
                                  pipeline_steps_flagged >>

CheckModifiable == /\ pc["correction_agent"] = "CheckModifiable"
                   /\ Assert(\A mod \in modifications : mod.target \in ModifiableTargets, 
                             "Failure of assertion at line 122, column 9.")
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["correction_agent"] = "Finish"]
                   /\ UNCHANGED << pass_type, modifications, 
                                   source_code_touched, tla_specs_touched, 
                                   bridge_touched, phase, human_review_items, 
                                   pipeline_steps_flagged >>

Finish == /\ pc["correction_agent"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["correction_agent"] = "Done"]
          /\ UNCHANGED << pass_type, modifications, source_code_touched, 
                          tla_specs_touched, bridge_touched, phase, step_count, 
                          human_review_items, pipeline_steps_flagged >>

agent == SelectPass \/ ApplyCorrection \/ CheckForbidden \/ CheckModifiable
            \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == agent
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(agent)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
