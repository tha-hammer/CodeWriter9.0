------------------------ MODULE GenTestsLoop ------------------------

EXTENDS Integers, Sequences, FiniteSets, TLC

(* --algorithm GenTestsLoop

variables
    lang_profile    \in {"Python", "TypeScript", "Rust", "Go"},
    job_state        = "Dequeued",
    artifacts_ready  = FALSE,
    passes_done      = {},
    generated_file   = "none",
    subprocess_used  = "none",
    verify_outcome   = "none",
    uploaded         = FALSE,
    upload_key       = "none",
    job_error        = "none";

define

    Languages  == {"Python", "TypeScript", "Rust", "Go"}
    LLMPasses  == {"plan", "review", "codegen"}

    AllStates  == {
        "Dequeued", "ArtifactsDownloaded",
        "PlanDone", "ReviewDone", "CodegenDone",
        "VerifyPassed", "VerifyFailed",
        "Uploaded", "JobFailed"
    }

    TerminalStates == {"Uploaded", "JobFailed"}

    SubprocessFor(lang) ==
        IF lang = "Python"     THEN "pytest"
        ELSE IF lang = "TypeScript" THEN "npx_jest"
        ELSE IF lang = "Rust"  THEN "cargo_test"
        ELSE "go_test"

    TestFileFor(lang) ==
        IF lang = "Python"     THEN "test_output.py"
        ELSE IF lang = "TypeScript" THEN "test_output.ts"
        ELSE IF lang = "Rust"  THEN "test_output.rs"
        ELSE "test_output.go"

    UploadKeyFor(lang) ==
        IF lang = "Python"     THEN "tests/generated/test_output.py"
        ELSE IF lang = "TypeScript" THEN "tests/generated/test_output.ts"
        ELSE IF lang = "Rust"  THEN "tests/generated/test_output.rs"
        ELSE "tests/generated/test_output.go"

    ValidState == job_state \in AllStates
    ValidLang  == lang_profile \in Languages

    UploadOnlyAfterVerifyPassed ==
        uploaded => verify_outcome = "passed"

    LLMOrderPreserved ==
        /\ ("review"  \in passes_done => "plan" \in passes_done)
        /\ ("codegen" \in passes_done =>
                "plan" \in passes_done /\ "review" \in passes_done)

    GeneratedFileSetBeforeVerify ==
        verify_outcome /= "none" => generated_file /= "none"

    SubprocessMatchesLang ==
        subprocess_used /= "none" =>
            subprocess_used = SubprocessFor(lang_profile)

    UploadKeyCorrect ==
        uploaded => upload_key = UploadKeyFor(lang_profile)

    ArtifactsBeforeLLM ==
        passes_done /= {} => artifacts_ready

    AllPassesAtCodegenDone ==
        job_state \in {"CodegenDone", "VerifyPassed", "VerifyFailed", "Uploaded"} =>
            passes_done = LLMPasses

    UploadedImpliesFullPipeline ==
        uploaded =>
            /\ passes_done     = LLMPasses
            /\ verify_outcome  = "passed"
            /\ generated_file /= "none"
            /\ subprocess_used = SubprocessFor(lang_profile)
            /\ upload_key      = UploadKeyFor(lang_profile)

    UploadPathUnderTestsGenerated ==
        uploaded =>
            \/ upload_key = "tests/generated/test_output.py"
            \/ upload_key = "tests/generated/test_output.ts"
            \/ upload_key = "tests/generated/test_output.rs"
            \/ upload_key = "tests/generated/test_output.go"

end define;

fair process worker = "worker"
begin
    DownloadArtifacts:
        if job_state = "Dequeued" then
            artifacts_ready := TRUE;
            job_state       := "ArtifactsDownloaded";
        else
            job_error := "unexpected_state_download";
            job_state := "JobFailed";
        end if;

    CallLLMPlan:
        if job_state = "ArtifactsDownloaded" then
            either
                passes_done := passes_done \union {"plan"};
                job_state   := "PlanDone";
            or
                job_error := "llm_plan_error";
                job_state := "JobFailed";
            end either;
        else
            if job_state /= "JobFailed" then
                job_error := "bad_state_plan";
                job_state := "JobFailed";
            end if;
        end if;

    CallLLMReview:
        if job_state = "PlanDone" then
            either
                passes_done := passes_done \union {"review"};
                job_state   := "ReviewDone";
            or
                job_error := "llm_review_error";
                job_state := "JobFailed";
            end either;
        else
            if job_state /= "JobFailed" then
                job_error := "bad_state_review";
                job_state := "JobFailed";
            end if;
        end if;

    CallLLMCodegen:
        if job_state = "ReviewDone" then
            either
                passes_done    := passes_done \union {"codegen"};
                generated_file := TestFileFor(lang_profile);
                job_state      := "CodegenDone";
            or
                job_error := "llm_codegen_error";
                job_state := "JobFailed";
            end either;
        else
            if job_state /= "JobFailed" then
                job_error := "bad_state_codegen";
                job_state := "JobFailed";
            end if;
        end if;

    RunVerify:
        if job_state = "CodegenDone" then
            either
                subprocess_used := SubprocessFor(lang_profile);
                verify_outcome  := "passed";
                job_state       := "VerifyPassed";
            or
                subprocess_used := SubprocessFor(lang_profile);
                verify_outcome  := "failed";
                job_state       := "VerifyFailed";
            end either;
        else
            if job_state /= "JobFailed" then
                job_error := "bad_state_verify";
                job_state := "JobFailed";
            end if;
        end if;

    UploadOrFail:
        if job_state = "VerifyPassed" then
            upload_key := UploadKeyFor(lang_profile);
            uploaded   := TRUE;
            job_state  := "Uploaded";
        else
            if job_state /= "JobFailed" then
                job_error := "verify_not_passed_no_upload";
                job_state := "JobFailed";
            end if;
        end if;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "ad1c381c" /\ chksum(tla) = "817537b0")
VARIABLES pc, lang_profile, job_state, artifacts_ready, passes_done, 
          generated_file, subprocess_used, verify_outcome, uploaded, 
          upload_key, job_error

(* define statement *)
Languages  == {"Python", "TypeScript", "Rust", "Go"}
LLMPasses  == {"plan", "review", "codegen"}

AllStates  == {
    "Dequeued", "ArtifactsDownloaded",
    "PlanDone", "ReviewDone", "CodegenDone",
    "VerifyPassed", "VerifyFailed",
    "Uploaded", "JobFailed"
}

TerminalStates == {"Uploaded", "JobFailed"}

SubprocessFor(lang) ==
    IF lang = "Python"     THEN "pytest"
    ELSE IF lang = "TypeScript" THEN "npx_jest"
    ELSE IF lang = "Rust"  THEN "cargo_test"
    ELSE "go_test"

TestFileFor(lang) ==
    IF lang = "Python"     THEN "test_output.py"
    ELSE IF lang = "TypeScript" THEN "test_output.ts"
    ELSE IF lang = "Rust"  THEN "test_output.rs"
    ELSE "test_output.go"

UploadKeyFor(lang) ==
    IF lang = "Python"     THEN "tests/generated/test_output.py"
    ELSE IF lang = "TypeScript" THEN "tests/generated/test_output.ts"
    ELSE IF lang = "Rust"  THEN "tests/generated/test_output.rs"
    ELSE "tests/generated/test_output.go"

ValidState == job_state \in AllStates
ValidLang  == lang_profile \in Languages

UploadOnlyAfterVerifyPassed ==
    uploaded => verify_outcome = "passed"

LLMOrderPreserved ==
    /\ ("review"  \in passes_done => "plan" \in passes_done)
    /\ ("codegen" \in passes_done =>
            "plan" \in passes_done /\ "review" \in passes_done)

GeneratedFileSetBeforeVerify ==
    verify_outcome /= "none" => generated_file /= "none"

SubprocessMatchesLang ==
    subprocess_used /= "none" =>
        subprocess_used = SubprocessFor(lang_profile)

UploadKeyCorrect ==
    uploaded => upload_key = UploadKeyFor(lang_profile)

ArtifactsBeforeLLM ==
    passes_done /= {} => artifacts_ready

AllPassesAtCodegenDone ==
    job_state \in {"CodegenDone", "VerifyPassed", "VerifyFailed", "Uploaded"} =>
        passes_done = LLMPasses

UploadedImpliesFullPipeline ==
    uploaded =>
        /\ passes_done     = LLMPasses
        /\ verify_outcome  = "passed"
        /\ generated_file /= "none"
        /\ subprocess_used = SubprocessFor(lang_profile)
        /\ upload_key      = UploadKeyFor(lang_profile)

UploadPathUnderTestsGenerated ==
    uploaded =>
        \/ upload_key = "tests/generated/test_output.py"
        \/ upload_key = "tests/generated/test_output.ts"
        \/ upload_key = "tests/generated/test_output.rs"
        \/ upload_key = "tests/generated/test_output.go"


vars == << pc, lang_profile, job_state, artifacts_ready, passes_done, 
           generated_file, subprocess_used, verify_outcome, uploaded, 
           upload_key, job_error >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ lang_profile \in {"Python", "TypeScript", "Rust", "Go"}
        /\ job_state = "Dequeued"
        /\ artifacts_ready = FALSE
        /\ passes_done = {}
        /\ generated_file = "none"
        /\ subprocess_used = "none"
        /\ verify_outcome = "none"
        /\ uploaded = FALSE
        /\ upload_key = "none"
        /\ job_error = "none"
        /\ pc = [self \in ProcSet |-> "DownloadArtifacts"]

DownloadArtifacts == /\ pc["worker"] = "DownloadArtifacts"
                     /\ IF job_state = "Dequeued"
                           THEN /\ artifacts_ready' = TRUE
                                /\ job_state' = "ArtifactsDownloaded"
                                /\ UNCHANGED job_error
                           ELSE /\ job_error' = "unexpected_state_download"
                                /\ job_state' = "JobFailed"
                                /\ UNCHANGED artifacts_ready
                     /\ pc' = [pc EXCEPT !["worker"] = "CallLLMPlan"]
                     /\ UNCHANGED << lang_profile, passes_done, generated_file, 
                                     subprocess_used, verify_outcome, uploaded, 
                                     upload_key >>

CallLLMPlan == /\ pc["worker"] = "CallLLMPlan"
               /\ IF job_state = "ArtifactsDownloaded"
                     THEN /\ \/ /\ passes_done' = (passes_done \union {"plan"})
                                /\ job_state' = "PlanDone"
                                /\ UNCHANGED job_error
                             \/ /\ job_error' = "llm_plan_error"
                                /\ job_state' = "JobFailed"
                                /\ UNCHANGED passes_done
                     ELSE /\ IF job_state /= "JobFailed"
                                THEN /\ job_error' = "bad_state_plan"
                                     /\ job_state' = "JobFailed"
                                ELSE /\ TRUE
                                     /\ UNCHANGED << job_state, job_error >>
                          /\ UNCHANGED passes_done
               /\ pc' = [pc EXCEPT !["worker"] = "CallLLMReview"]
               /\ UNCHANGED << lang_profile, artifacts_ready, generated_file, 
                               subprocess_used, verify_outcome, uploaded, 
                               upload_key >>

CallLLMReview == /\ pc["worker"] = "CallLLMReview"
                 /\ IF job_state = "PlanDone"
                       THEN /\ \/ /\ passes_done' = (passes_done \union {"review"})
                                  /\ job_state' = "ReviewDone"
                                  /\ UNCHANGED job_error
                               \/ /\ job_error' = "llm_review_error"
                                  /\ job_state' = "JobFailed"
                                  /\ UNCHANGED passes_done
                       ELSE /\ IF job_state /= "JobFailed"
                                  THEN /\ job_error' = "bad_state_review"
                                       /\ job_state' = "JobFailed"
                                  ELSE /\ TRUE
                                       /\ UNCHANGED << job_state, job_error >>
                            /\ UNCHANGED passes_done
                 /\ pc' = [pc EXCEPT !["worker"] = "CallLLMCodegen"]
                 /\ UNCHANGED << lang_profile, artifacts_ready, generated_file, 
                                 subprocess_used, verify_outcome, uploaded, 
                                 upload_key >>

CallLLMCodegen == /\ pc["worker"] = "CallLLMCodegen"
                  /\ IF job_state = "ReviewDone"
                        THEN /\ \/ /\ passes_done' = (passes_done \union {"codegen"})
                                   /\ generated_file' = TestFileFor(lang_profile)
                                   /\ job_state' = "CodegenDone"
                                   /\ UNCHANGED job_error
                                \/ /\ job_error' = "llm_codegen_error"
                                   /\ job_state' = "JobFailed"
                                   /\ UNCHANGED <<passes_done, generated_file>>
                        ELSE /\ IF job_state /= "JobFailed"
                                   THEN /\ job_error' = "bad_state_codegen"
                                        /\ job_state' = "JobFailed"
                                   ELSE /\ TRUE
                                        /\ UNCHANGED << job_state, job_error >>
                             /\ UNCHANGED << passes_done, generated_file >>
                  /\ pc' = [pc EXCEPT !["worker"] = "RunVerify"]
                  /\ UNCHANGED << lang_profile, artifacts_ready, 
                                  subprocess_used, verify_outcome, uploaded, 
                                  upload_key >>

RunVerify == /\ pc["worker"] = "RunVerify"
             /\ IF job_state = "CodegenDone"
                   THEN /\ \/ /\ subprocess_used' = SubprocessFor(lang_profile)
                              /\ verify_outcome' = "passed"
                              /\ job_state' = "VerifyPassed"
                           \/ /\ subprocess_used' = SubprocessFor(lang_profile)
                              /\ verify_outcome' = "failed"
                              /\ job_state' = "VerifyFailed"
                        /\ UNCHANGED job_error
                   ELSE /\ IF job_state /= "JobFailed"
                              THEN /\ job_error' = "bad_state_verify"
                                   /\ job_state' = "JobFailed"
                              ELSE /\ TRUE
                                   /\ UNCHANGED << job_state, job_error >>
                        /\ UNCHANGED << subprocess_used, verify_outcome >>
             /\ pc' = [pc EXCEPT !["worker"] = "UploadOrFail"]
             /\ UNCHANGED << lang_profile, artifacts_ready, passes_done, 
                             generated_file, uploaded, upload_key >>

UploadOrFail == /\ pc["worker"] = "UploadOrFail"
                /\ IF job_state = "VerifyPassed"
                      THEN /\ upload_key' = UploadKeyFor(lang_profile)
                           /\ uploaded' = TRUE
                           /\ job_state' = "Uploaded"
                           /\ UNCHANGED job_error
                      ELSE /\ IF job_state /= "JobFailed"
                                 THEN /\ job_error' = "verify_not_passed_no_upload"
                                      /\ job_state' = "JobFailed"
                                 ELSE /\ TRUE
                                      /\ UNCHANGED << job_state, job_error >>
                           /\ UNCHANGED << uploaded, upload_key >>
                /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                /\ UNCHANGED << lang_profile, artifacts_ready, passes_done, 
                                generated_file, subprocess_used, 
                                verify_outcome >>

Terminate == /\ pc["worker"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["worker"] = "Done"]
             /\ UNCHANGED << lang_profile, job_state, artifacts_ready, 
                             passes_done, generated_file, subprocess_used, 
                             verify_outcome, uploaded, upload_key, job_error >>

worker == DownloadArtifacts \/ CallLLMPlan \/ CallLLMReview
             \/ CallLLMCodegen \/ RunVerify \/ UploadOrFail \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
