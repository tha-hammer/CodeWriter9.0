---- MODULE BridgeJob ----

EXTENDS Integers, FiniteSets, TLC

PhaseSet == {
    "dequeued",
    "parsing",
    "translating_state_vars",
    "translating_actions",
    "translating_inv_verifiers",
    "translating_inv_assertions",
    "translating_traces",
    "writing_artifact",
    "uploading_artifact",
    "complete",
    "failed"
}

TerminalPhases == {"complete", "failed"}

(* --algorithm BridgeJob

variables
    phase                   = "dequeued",
    spec_file_present       = TRUE,
    traces_file_present     = TRUE,
    sim_traces_file_present = TRUE,
    spec_parsed             = FALSE,
    state_vars_done         = FALSE,
    actions_done            = FALSE,
    inv_verifiers_done      = FALSE,
    inv_assertions_done     = FALSE,
    traces_done             = FALSE,
    artifact_written        = FALSE,
    artifact_uploaded       = FALSE,
    llm_invoked             = FALSE,
    subprocess_invoked      = FALSE,
    parse_error             = FALSE,
    translate_error         = FALSE;

define

    ValidPhase == phase \in PhaseSet

    NoLLMInvoked == llm_invoked = FALSE

    NoSubprocessInvoked == subprocess_invoked = FALSE

    ParsePrecedesTranslations ==
        (state_vars_done \/ actions_done \/ inv_verifiers_done \/
         inv_assertions_done \/ traces_done) => spec_parsed

    AllTranslationsPrecedeWrite ==
        artifact_written =>
            (state_vars_done /\ actions_done /\ inv_verifiers_done /\
             inv_assertions_done /\ traces_done)

    WritePrecedesUpload == artifact_uploaded => artifact_written

    CompletionRequiresUpload == (phase = "complete") => artifact_uploaded

    PipelineIntegrity ==
        artifact_uploaded =>
            (artifact_written /\ traces_done /\ inv_assertions_done /\
             inv_verifiers_done /\ actions_done /\ state_vars_done /\ spec_parsed)

    InputFilesRequiredForParse ==
        (phase \notin {"dequeued"}) =>
            (spec_file_present /\ traces_file_present /\ sim_traces_file_present)

    CompletionRequiresArtifact ==
        (phase = "complete") => (artifact_written /\ artifact_uploaded)

    SafeTermination ==
        (phase = "complete") =>
            (NoLLMInvoked /\ NoSubprocessInvoked /\ PipelineIntegrity)

end define;

fair process runner = "run_bridge"
begin

    AwaitDequeue:
        await phase = "dequeued"
            /\ spec_file_present
            /\ traces_file_present
            /\ sim_traces_file_present;
        phase := "parsing";

    RunParseSpec:
        if spec_file_present then
            spec_parsed  := TRUE;
            parse_error  := FALSE;
            phase        := "translating_state_vars";
        else
            parse_error  := TRUE;
            phase        := "failed";
        end if;

    CheckParsed:
        if parse_error then
            goto Terminate;
        end if;

    RunTranslateStateVars:
        await spec_parsed;
        state_vars_done := TRUE;
        phase           := "translating_actions";

    RunTranslateActions:
        await state_vars_done;
        actions_done := TRUE;
        phase        := "translating_inv_verifiers";

    RunTranslateInvVerifiers:
        await actions_done;
        inv_verifiers_done := TRUE;
        phase              := "translating_inv_assertions";

    RunTranslateInvAssertions:
        await inv_verifiers_done;
        inv_assertions_done := TRUE;
        phase               := "translating_traces";

    RunTranslateTraces:
        await inv_assertions_done;
        traces_done := TRUE;
        phase       := "writing_artifact";

    CheckAllTranslations:
        if ~(state_vars_done /\ actions_done /\ inv_verifiers_done /\
             inv_assertions_done /\ traces_done) then
            translate_error := TRUE;
            phase           := "failed";
            goto Terminate;
        end if;

    WriteArtifactFile:
        await state_vars_done /\ actions_done /\ inv_verifiers_done /\
              inv_assertions_done /\ traces_done;
        artifact_written := TRUE;
        phase            := "uploading_artifact";

    UploadArtifactFile:
        await artifact_written;
        artifact_uploaded := TRUE;
        phase             := "complete";

    Terminate:
        assert llm_invoked = FALSE;
        assert subprocess_invoked = FALSE;
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "2c413dda" /\ chksum(tla) = "e5ad5a2")
VARIABLES pc, phase, spec_file_present, traces_file_present, 
          sim_traces_file_present, spec_parsed, state_vars_done, actions_done, 
          inv_verifiers_done, inv_assertions_done, traces_done, 
          artifact_written, artifact_uploaded, llm_invoked, 
          subprocess_invoked, parse_error, translate_error

(* define statement *)
ValidPhase == phase \in PhaseSet

NoLLMInvoked == llm_invoked = FALSE

NoSubprocessInvoked == subprocess_invoked = FALSE

ParsePrecedesTranslations ==
    (state_vars_done \/ actions_done \/ inv_verifiers_done \/
     inv_assertions_done \/ traces_done) => spec_parsed

AllTranslationsPrecedeWrite ==
    artifact_written =>
        (state_vars_done /\ actions_done /\ inv_verifiers_done /\
         inv_assertions_done /\ traces_done)

WritePrecedesUpload == artifact_uploaded => artifact_written

CompletionRequiresUpload == (phase = "complete") => artifact_uploaded

PipelineIntegrity ==
    artifact_uploaded =>
        (artifact_written /\ traces_done /\ inv_assertions_done /\
         inv_verifiers_done /\ actions_done /\ state_vars_done /\ spec_parsed)

InputFilesRequiredForParse ==
    (phase \notin {"dequeued"}) =>
        (spec_file_present /\ traces_file_present /\ sim_traces_file_present)

CompletionRequiresArtifact ==
    (phase = "complete") => (artifact_written /\ artifact_uploaded)

SafeTermination ==
    (phase = "complete") =>
        (NoLLMInvoked /\ NoSubprocessInvoked /\ PipelineIntegrity)


vars == << pc, phase, spec_file_present, traces_file_present, 
           sim_traces_file_present, spec_parsed, state_vars_done, 
           actions_done, inv_verifiers_done, inv_assertions_done, traces_done, 
           artifact_written, artifact_uploaded, llm_invoked, 
           subprocess_invoked, parse_error, translate_error >>

ProcSet == {"run_bridge"}

Init == (* Global variables *)
        /\ phase = "dequeued"
        /\ spec_file_present = TRUE
        /\ traces_file_present = TRUE
        /\ sim_traces_file_present = TRUE
        /\ spec_parsed = FALSE
        /\ state_vars_done = FALSE
        /\ actions_done = FALSE
        /\ inv_verifiers_done = FALSE
        /\ inv_assertions_done = FALSE
        /\ traces_done = FALSE
        /\ artifact_written = FALSE
        /\ artifact_uploaded = FALSE
        /\ llm_invoked = FALSE
        /\ subprocess_invoked = FALSE
        /\ parse_error = FALSE
        /\ translate_error = FALSE
        /\ pc = [self \in ProcSet |-> "AwaitDequeue"]

AwaitDequeue == /\ pc["run_bridge"] = "AwaitDequeue"
                /\   phase = "dequeued"
                   /\ spec_file_present
                   /\ traces_file_present
                   /\ sim_traces_file_present
                /\ phase' = "parsing"
                /\ pc' = [pc EXCEPT !["run_bridge"] = "RunParseSpec"]
                /\ UNCHANGED << spec_file_present, traces_file_present, 
                                sim_traces_file_present, spec_parsed, 
                                state_vars_done, actions_done, 
                                inv_verifiers_done, inv_assertions_done, 
                                traces_done, artifact_written, 
                                artifact_uploaded, llm_invoked, 
                                subprocess_invoked, parse_error, 
                                translate_error >>

RunParseSpec == /\ pc["run_bridge"] = "RunParseSpec"
                /\ IF spec_file_present
                      THEN /\ spec_parsed' = TRUE
                           /\ parse_error' = FALSE
                           /\ phase' = "translating_state_vars"
                      ELSE /\ parse_error' = TRUE
                           /\ phase' = "failed"
                           /\ UNCHANGED spec_parsed
                /\ pc' = [pc EXCEPT !["run_bridge"] = "CheckParsed"]
                /\ UNCHANGED << spec_file_present, traces_file_present, 
                                sim_traces_file_present, state_vars_done, 
                                actions_done, inv_verifiers_done, 
                                inv_assertions_done, traces_done, 
                                artifact_written, artifact_uploaded, 
                                llm_invoked, subprocess_invoked, 
                                translate_error >>

CheckParsed == /\ pc["run_bridge"] = "CheckParsed"
               /\ IF parse_error
                     THEN /\ pc' = [pc EXCEPT !["run_bridge"] = "Terminate"]
                     ELSE /\ pc' = [pc EXCEPT !["run_bridge"] = "RunTranslateStateVars"]
               /\ UNCHANGED << phase, spec_file_present, traces_file_present, 
                               sim_traces_file_present, spec_parsed, 
                               state_vars_done, actions_done, 
                               inv_verifiers_done, inv_assertions_done, 
                               traces_done, artifact_written, 
                               artifact_uploaded, llm_invoked, 
                               subprocess_invoked, parse_error, 
                               translate_error >>

RunTranslateStateVars == /\ pc["run_bridge"] = "RunTranslateStateVars"
                         /\ spec_parsed
                         /\ state_vars_done' = TRUE
                         /\ phase' = "translating_actions"
                         /\ pc' = [pc EXCEPT !["run_bridge"] = "RunTranslateActions"]
                         /\ UNCHANGED << spec_file_present, 
                                         traces_file_present, 
                                         sim_traces_file_present, spec_parsed, 
                                         actions_done, inv_verifiers_done, 
                                         inv_assertions_done, traces_done, 
                                         artifact_written, artifact_uploaded, 
                                         llm_invoked, subprocess_invoked, 
                                         parse_error, translate_error >>

RunTranslateActions == /\ pc["run_bridge"] = "RunTranslateActions"
                       /\ state_vars_done
                       /\ actions_done' = TRUE
                       /\ phase' = "translating_inv_verifiers"
                       /\ pc' = [pc EXCEPT !["run_bridge"] = "RunTranslateInvVerifiers"]
                       /\ UNCHANGED << spec_file_present, traces_file_present, 
                                       sim_traces_file_present, spec_parsed, 
                                       state_vars_done, inv_verifiers_done, 
                                       inv_assertions_done, traces_done, 
                                       artifact_written, artifact_uploaded, 
                                       llm_invoked, subprocess_invoked, 
                                       parse_error, translate_error >>

RunTranslateInvVerifiers == /\ pc["run_bridge"] = "RunTranslateInvVerifiers"
                            /\ actions_done
                            /\ inv_verifiers_done' = TRUE
                            /\ phase' = "translating_inv_assertions"
                            /\ pc' = [pc EXCEPT !["run_bridge"] = "RunTranslateInvAssertions"]
                            /\ UNCHANGED << spec_file_present, 
                                            traces_file_present, 
                                            sim_traces_file_present, 
                                            spec_parsed, state_vars_done, 
                                            actions_done, inv_assertions_done, 
                                            traces_done, artifact_written, 
                                            artifact_uploaded, llm_invoked, 
                                            subprocess_invoked, parse_error, 
                                            translate_error >>

RunTranslateInvAssertions == /\ pc["run_bridge"] = "RunTranslateInvAssertions"
                             /\ inv_verifiers_done
                             /\ inv_assertions_done' = TRUE
                             /\ phase' = "translating_traces"
                             /\ pc' = [pc EXCEPT !["run_bridge"] = "RunTranslateTraces"]
                             /\ UNCHANGED << spec_file_present, 
                                             traces_file_present, 
                                             sim_traces_file_present, 
                                             spec_parsed, state_vars_done, 
                                             actions_done, inv_verifiers_done, 
                                             traces_done, artifact_written, 
                                             artifact_uploaded, llm_invoked, 
                                             subprocess_invoked, parse_error, 
                                             translate_error >>

RunTranslateTraces == /\ pc["run_bridge"] = "RunTranslateTraces"
                      /\ inv_assertions_done
                      /\ traces_done' = TRUE
                      /\ phase' = "writing_artifact"
                      /\ pc' = [pc EXCEPT !["run_bridge"] = "CheckAllTranslations"]
                      /\ UNCHANGED << spec_file_present, traces_file_present, 
                                      sim_traces_file_present, spec_parsed, 
                                      state_vars_done, actions_done, 
                                      inv_verifiers_done, inv_assertions_done, 
                                      artifact_written, artifact_uploaded, 
                                      llm_invoked, subprocess_invoked, 
                                      parse_error, translate_error >>

CheckAllTranslations == /\ pc["run_bridge"] = "CheckAllTranslations"
                        /\ IF ~(state_vars_done /\ actions_done /\ inv_verifiers_done /\
                                inv_assertions_done /\ traces_done)
                              THEN /\ translate_error' = TRUE
                                   /\ phase' = "failed"
                                   /\ pc' = [pc EXCEPT !["run_bridge"] = "Terminate"]
                              ELSE /\ pc' = [pc EXCEPT !["run_bridge"] = "WriteArtifactFile"]
                                   /\ UNCHANGED << phase, translate_error >>
                        /\ UNCHANGED << spec_file_present, traces_file_present, 
                                        sim_traces_file_present, spec_parsed, 
                                        state_vars_done, actions_done, 
                                        inv_verifiers_done, 
                                        inv_assertions_done, traces_done, 
                                        artifact_written, artifact_uploaded, 
                                        llm_invoked, subprocess_invoked, 
                                        parse_error >>

WriteArtifactFile == /\ pc["run_bridge"] = "WriteArtifactFile"
                     /\ state_vars_done /\ actions_done /\ inv_verifiers_done /\
                        inv_assertions_done /\ traces_done
                     /\ artifact_written' = TRUE
                     /\ phase' = "uploading_artifact"
                     /\ pc' = [pc EXCEPT !["run_bridge"] = "UploadArtifactFile"]
                     /\ UNCHANGED << spec_file_present, traces_file_present, 
                                     sim_traces_file_present, spec_parsed, 
                                     state_vars_done, actions_done, 
                                     inv_verifiers_done, inv_assertions_done, 
                                     traces_done, artifact_uploaded, 
                                     llm_invoked, subprocess_invoked, 
                                     parse_error, translate_error >>

UploadArtifactFile == /\ pc["run_bridge"] = "UploadArtifactFile"
                      /\ artifact_written
                      /\ artifact_uploaded' = TRUE
                      /\ phase' = "complete"
                      /\ pc' = [pc EXCEPT !["run_bridge"] = "Terminate"]
                      /\ UNCHANGED << spec_file_present, traces_file_present, 
                                      sim_traces_file_present, spec_parsed, 
                                      state_vars_done, actions_done, 
                                      inv_verifiers_done, inv_assertions_done, 
                                      traces_done, artifact_written, 
                                      llm_invoked, subprocess_invoked, 
                                      parse_error, translate_error >>

Terminate == /\ pc["run_bridge"] = "Terminate"
             /\ Assert(llm_invoked = FALSE, 
                       "Failure of assertion at line 150, column 9.")
             /\ Assert(subprocess_invoked = FALSE, 
                       "Failure of assertion at line 151, column 9.")
             /\ TRUE
             /\ pc' = [pc EXCEPT !["run_bridge"] = "Done"]
             /\ UNCHANGED << phase, spec_file_present, traces_file_present, 
                             sim_traces_file_present, spec_parsed, 
                             state_vars_done, actions_done, inv_verifiers_done, 
                             inv_assertions_done, traces_done, 
                             artifact_written, artifact_uploaded, llm_invoked, 
                             subprocess_invoked, parse_error, translate_error >>

runner == AwaitDequeue \/ RunParseSpec \/ CheckParsed
             \/ RunTranslateStateVars \/ RunTranslateActions
             \/ RunTranslateInvVerifiers \/ RunTranslateInvAssertions
             \/ RunTranslateTraces \/ CheckAllTranslations
             \/ WriteArtifactFile \/ UploadArtifactFile \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == runner
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(runner)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
