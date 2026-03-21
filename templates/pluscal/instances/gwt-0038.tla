---- MODULE ProjectContextExternal ----

EXTENDS Integers, TLC

CONSTANTS
    EngineRoot,
    TargetRoot,
    MaxSteps

(* --algorithm ProjectContextExternal

variables
    phase                    = "init",
    engine_root_v            = EngineRoot,
    target_root_v            = TargetRoot,
    state_root               = [base |-> "unset", under_cw9 |-> FALSE],
    schema_dir               = [base |-> "unset", under_cw9 |-> FALSE],
    spec_dir                 = [base |-> "unset", under_cw9 |-> FALSE],
    template_dir             = [base |-> "unset", under_cw9 |-> FALSE],
    tools_dir                = [base |-> "unset", under_cw9 |-> FALSE],
    artifact_dir             = [base |-> "unset", under_cw9 |-> FALSE],
    test_output_dir          = [base |-> "unset", under_cw9 |-> FALSE],
    artifact_dir_under_state = FALSE,
    spec_dir_under_state     = FALSE,
    step_count               = 0;

define

    UnderStateRoot(p)  == p.base = TargetRoot /\ p.under_cw9 = TRUE
    UnderEngineRoot(p) == p.base = EngineRoot
    UnderTargetOnly(p) == p.base = TargetRoot /\ p.under_cw9 = FALSE

    BoundedExecution == step_count <= MaxSteps

    StateRootCorrect ==
        phase = "complete" =>
            (state_root.base = TargetRoot /\ state_root.under_cw9 = TRUE)

    SchemaUnderState ==
        phase = "complete" => UnderStateRoot(schema_dir)

    SpecUnderState ==
        phase = "complete" => UnderStateRoot(spec_dir)

    TemplateFromEngine ==
        phase = "complete" => UnderEngineRoot(template_dir)

    ToolsFromEngine ==
        phase = "complete" => UnderEngineRoot(tools_dir)

    ArtifactUnderState ==
        phase = "complete" => UnderStateRoot(artifact_dir)

    TestOutputNotUnderCw9 ==
        phase = "complete" => UnderTargetOnly(test_output_dir)

    NoCrossContamination ==
        phase = "complete" =>
            /\ ~UnderEngineRoot(schema_dir)
            /\ ~UnderEngineRoot(spec_dir)
            /\ ~UnderEngineRoot(artifact_dir)
            /\ ~UnderStateRoot(template_dir)
            /\ ~UnderStateRoot(tools_dir)

    ArtifactDirFlagCorrect ==
        phase = "complete" => artifact_dir_under_state = TRUE

    SpecDirFlagCorrect ==
        phase = "complete" => spec_dir_under_state = TRUE

    ArtifactSpecDiverge ==
        phase = "complete" =>
            UnderStateRoot(artifact_dir) /\ ~UnderStateRoot(test_output_dir)

    AllInvariants ==
        /\ BoundedExecution
        /\ StateRootCorrect
        /\ SchemaUnderState
        /\ SpecUnderState
        /\ TemplateFromEngine
        /\ ToolsFromEngine
        /\ ArtifactUnderState
        /\ TestOutputNotUnderCw9
        /\ NoCrossContamination
        /\ ArtifactDirFlagCorrect
        /\ SpecDirFlagCorrect
        /\ ArtifactSpecDiverge

end define;

fair process main = "main"
begin
    CheckPrecondition:
        step_count := step_count + 1;
        if engine_root_v # target_root_v then
            phase := "computing";
        else
            phase := "precond_failed";
            goto Terminate;
        end if;

    ComputeStateRoot:
        state_root := [base |-> target_root_v, under_cw9 |-> TRUE];
        step_count := step_count + 1;

    ComputeSchemaDir:
        schema_dir := [base |-> target_root_v, under_cw9 |-> TRUE];
        step_count := step_count + 1;

    ComputeSpecDir:
        spec_dir             := [base |-> target_root_v, under_cw9 |-> TRUE];
        spec_dir_under_state := TRUE;
        step_count           := step_count + 1;

    ComputeTemplateDir:
        template_dir := [base |-> engine_root_v, under_cw9 |-> FALSE];
        step_count   := step_count + 1;

    ComputeToolsDir:
        tools_dir  := [base |-> engine_root_v, under_cw9 |-> FALSE];
        step_count := step_count + 1;

    ComputeArtifactDir:
        artifact_dir             := [base |-> target_root_v, under_cw9 |-> TRUE];
        artifact_dir_under_state := TRUE;
        step_count               := step_count + 1;

    ComputeTestOutput:
        test_output_dir := [base |-> target_root_v, under_cw9 |-> FALSE];
        step_count      := step_count + 1;

    Finish:
        phase := "complete";

    Terminate:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "7c7de2dc" /\ chksum(tla) = "7dad0329")
VARIABLES pc, phase, engine_root_v, target_root_v, state_root, schema_dir, 
          spec_dir, template_dir, tools_dir, artifact_dir, test_output_dir, 
          artifact_dir_under_state, spec_dir_under_state, step_count

(* define statement *)
UnderStateRoot(p)  == p.base = TargetRoot /\ p.under_cw9 = TRUE
UnderEngineRoot(p) == p.base = EngineRoot
UnderTargetOnly(p) == p.base = TargetRoot /\ p.under_cw9 = FALSE

BoundedExecution == step_count <= MaxSteps

StateRootCorrect ==
    phase = "complete" =>
        (state_root.base = TargetRoot /\ state_root.under_cw9 = TRUE)

SchemaUnderState ==
    phase = "complete" => UnderStateRoot(schema_dir)

SpecUnderState ==
    phase = "complete" => UnderStateRoot(spec_dir)

TemplateFromEngine ==
    phase = "complete" => UnderEngineRoot(template_dir)

ToolsFromEngine ==
    phase = "complete" => UnderEngineRoot(tools_dir)

ArtifactUnderState ==
    phase = "complete" => UnderStateRoot(artifact_dir)

TestOutputNotUnderCw9 ==
    phase = "complete" => UnderTargetOnly(test_output_dir)

NoCrossContamination ==
    phase = "complete" =>
        /\ ~UnderEngineRoot(schema_dir)
        /\ ~UnderEngineRoot(spec_dir)
        /\ ~UnderEngineRoot(artifact_dir)
        /\ ~UnderStateRoot(template_dir)
        /\ ~UnderStateRoot(tools_dir)

ArtifactDirFlagCorrect ==
    phase = "complete" => artifact_dir_under_state = TRUE

SpecDirFlagCorrect ==
    phase = "complete" => spec_dir_under_state = TRUE

ArtifactSpecDiverge ==
    phase = "complete" =>
        UnderStateRoot(artifact_dir) /\ ~UnderStateRoot(test_output_dir)

AllInvariants ==
    /\ BoundedExecution
    /\ StateRootCorrect
    /\ SchemaUnderState
    /\ SpecUnderState
    /\ TemplateFromEngine
    /\ ToolsFromEngine
    /\ ArtifactUnderState
    /\ TestOutputNotUnderCw9
    /\ NoCrossContamination
    /\ ArtifactDirFlagCorrect
    /\ SpecDirFlagCorrect
    /\ ArtifactSpecDiverge


vars == << pc, phase, engine_root_v, target_root_v, state_root, schema_dir, 
           spec_dir, template_dir, tools_dir, artifact_dir, test_output_dir, 
           artifact_dir_under_state, spec_dir_under_state, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ phase = "init"
        /\ engine_root_v = EngineRoot
        /\ target_root_v = TargetRoot
        /\ state_root = [base |-> "unset", under_cw9 |-> FALSE]
        /\ schema_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ spec_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ template_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ tools_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ artifact_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ test_output_dir = [base |-> "unset", under_cw9 |-> FALSE]
        /\ artifact_dir_under_state = FALSE
        /\ spec_dir_under_state = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "CheckPrecondition"]

CheckPrecondition == /\ pc["main"] = "CheckPrecondition"
                     /\ step_count' = step_count + 1
                     /\ IF engine_root_v # target_root_v
                           THEN /\ phase' = "computing"
                                /\ pc' = [pc EXCEPT !["main"] = "ComputeStateRoot"]
                           ELSE /\ phase' = "precond_failed"
                                /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                     /\ UNCHANGED << engine_root_v, target_root_v, state_root, 
                                     schema_dir, spec_dir, template_dir, 
                                     tools_dir, artifact_dir, test_output_dir, 
                                     artifact_dir_under_state, 
                                     spec_dir_under_state >>

ComputeStateRoot == /\ pc["main"] = "ComputeStateRoot"
                    /\ state_root' = [base |-> target_root_v, under_cw9 |-> TRUE]
                    /\ step_count' = step_count + 1
                    /\ pc' = [pc EXCEPT !["main"] = "ComputeSchemaDir"]
                    /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                    schema_dir, spec_dir, template_dir, 
                                    tools_dir, artifact_dir, test_output_dir, 
                                    artifact_dir_under_state, 
                                    spec_dir_under_state >>

ComputeSchemaDir == /\ pc["main"] = "ComputeSchemaDir"
                    /\ schema_dir' = [base |-> target_root_v, under_cw9 |-> TRUE]
                    /\ step_count' = step_count + 1
                    /\ pc' = [pc EXCEPT !["main"] = "ComputeSpecDir"]
                    /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                    state_root, spec_dir, template_dir, 
                                    tools_dir, artifact_dir, test_output_dir, 
                                    artifact_dir_under_state, 
                                    spec_dir_under_state >>

ComputeSpecDir == /\ pc["main"] = "ComputeSpecDir"
                  /\ spec_dir' = [base |-> target_root_v, under_cw9 |-> TRUE]
                  /\ spec_dir_under_state' = TRUE
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["main"] = "ComputeTemplateDir"]
                  /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                  state_root, schema_dir, template_dir, 
                                  tools_dir, artifact_dir, test_output_dir, 
                                  artifact_dir_under_state >>

ComputeTemplateDir == /\ pc["main"] = "ComputeTemplateDir"
                      /\ template_dir' = [base |-> engine_root_v, under_cw9 |-> FALSE]
                      /\ step_count' = step_count + 1
                      /\ pc' = [pc EXCEPT !["main"] = "ComputeToolsDir"]
                      /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                      state_root, schema_dir, spec_dir, 
                                      tools_dir, artifact_dir, test_output_dir, 
                                      artifact_dir_under_state, 
                                      spec_dir_under_state >>

ComputeToolsDir == /\ pc["main"] = "ComputeToolsDir"
                   /\ tools_dir' = [base |-> engine_root_v, under_cw9 |-> FALSE]
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["main"] = "ComputeArtifactDir"]
                   /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                   state_root, schema_dir, spec_dir, 
                                   template_dir, artifact_dir, test_output_dir, 
                                   artifact_dir_under_state, 
                                   spec_dir_under_state >>

ComputeArtifactDir == /\ pc["main"] = "ComputeArtifactDir"
                      /\ artifact_dir' = [base |-> target_root_v, under_cw9 |-> TRUE]
                      /\ artifact_dir_under_state' = TRUE
                      /\ step_count' = step_count + 1
                      /\ pc' = [pc EXCEPT !["main"] = "ComputeTestOutput"]
                      /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                      state_root, schema_dir, spec_dir, 
                                      template_dir, tools_dir, test_output_dir, 
                                      spec_dir_under_state >>

ComputeTestOutput == /\ pc["main"] = "ComputeTestOutput"
                     /\ test_output_dir' = [base |-> target_root_v, under_cw9 |-> FALSE]
                     /\ step_count' = step_count + 1
                     /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                     /\ UNCHANGED << phase, engine_root_v, target_root_v, 
                                     state_root, schema_dir, spec_dir, 
                                     template_dir, tools_dir, artifact_dir, 
                                     artifact_dir_under_state, 
                                     spec_dir_under_state >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "complete"
          /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
          /\ UNCHANGED << engine_root_v, target_root_v, state_root, schema_dir, 
                          spec_dir, template_dir, tools_dir, artifact_dir, 
                          test_output_dir, artifact_dir_under_state, 
                          spec_dir_under_state, step_count >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << phase, engine_root_v, target_root_v, state_root, 
                             schema_dir, spec_dir, template_dir, tools_dir, 
                             artifact_dir, test_output_dir, 
                             artifact_dir_under_state, spec_dir_under_state, 
                             step_count >>

main == CheckPrecondition \/ ComputeStateRoot \/ ComputeSchemaDir
           \/ ComputeSpecDir \/ ComputeTemplateDir \/ ComputeToolsDir
           \/ ComputeArtifactDir \/ ComputeTestOutput \/ Finish
           \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == main
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(main)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
