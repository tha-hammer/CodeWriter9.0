-------------------------- MODULE GWT0016TestGenLoop --------------------------

EXTENDS Integers, Sequences, TLC

CONSTANTS
    MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 0

(* --algorithm TestGenLoop

variables
    phase = "build_test_plan_prompt",
    llm_call_count = 0,
    pass1_done = FALSE,
    pass2_done = FALSE,
    pass3_done = FALSE,
    code_extracted = FALSE,
    verification_passed = FALSE,
    retry_count = 0,
    prompt_built = "none",
    llm_response = "none",
    terminated = FALSE,
    retries_exhausted = FALSE;

define

    ValidPhase ==
        phase \in {
            "build_test_plan_prompt", "pass1_llm",
            "build_review_prompt",    "pass2_llm",
            "build_codegen_prompt",   "pass3_llm",
            "extract_code",           "verify",
            "build_retry_prompt",     "retry_llm",
            "extract_code_retry",     "verify_retry",
            "success",                "exhausted"
        }

    PassesAreOrdered ==
        (pass2_done => pass1_done) /\ (pass3_done => pass2_done)

    ExactlyThreeLLMCallsBeforeExtract ==
        code_extracted => llm_call_count >= 3

    NoExtraLLMCallsInMainPasses ==
        (pass3_done /\ ~code_extracted) => llm_call_count = 3

    RetryOnlyAfterVerifyFail ==
        (retry_count > 0) =>
            (pass1_done /\ pass2_done /\ pass3_done /\ code_extracted)

    RetryBounded == retry_count <= MaxRetries

    TerminationMeansSuccessOrExhausted ==
        terminated => (phase = "success" \/ phase = "exhausted")

    SuccessImpliesVerified ==
        phase = "success" => verification_passed

end define;

fair process worker = "gen_tests_worker"
begin

    BuildTestPlanPrompt:
        assert phase = "build_test_plan_prompt";
        prompt_built := "test_plan_prompt";
        phase := "pass1_llm";

    Pass1LLM:
        assert phase = "pass1_llm";
        assert prompt_built = "test_plan_prompt";
        llm_response := "test_plan_response";
        llm_call_count := llm_call_count + 1;
        pass1_done := TRUE;
        phase := "build_review_prompt";

    BuildReviewPrompt:
        assert phase = "build_review_prompt";
        assert pass1_done = TRUE;
        prompt_built := "review_prompt";
        phase := "pass2_llm";

    Pass2LLM:
        assert phase = "pass2_llm";
        assert prompt_built = "review_prompt";
        llm_response := "review_response";
        llm_call_count := llm_call_count + 1;
        pass2_done := TRUE;
        phase := "build_codegen_prompt";

    BuildCodegenPrompt:
        assert phase = "build_codegen_prompt";
        assert pass2_done = TRUE;
        prompt_built := "codegen_prompt";
        phase := "pass3_llm";

    Pass3LLM:
        assert phase = "pass3_llm";
        assert prompt_built = "codegen_prompt";
        llm_response := "codegen_response";
        llm_call_count := llm_call_count + 1;
        pass3_done := TRUE;
        phase := "extract_code";

    ExtractCode:
        assert phase = "extract_code";
        assert llm_call_count = 3;
        assert pass1_done /\ pass2_done /\ pass3_done;
        code_extracted := TRUE;
        phase := "verify";

    Verify:
        assert phase = "verify";
        assert code_extracted = TRUE;
        either
            verification_passed := TRUE;
            phase := "success";
        or
            verification_passed := FALSE;
            phase := "build_retry_prompt";
        end either;

    AfterVerify:
        if verification_passed then
            terminated := TRUE;
            goto Terminate;
        elsif retry_count >= MaxRetries then
            retries_exhausted := TRUE;
            phase := "exhausted";
            terminated := TRUE;
            goto Terminate;
        else
            skip;
        end if;

    BuildRetryPrompt:
        assert phase = "build_retry_prompt";
        assert ~verification_passed;
        retry_count := retry_count + 1;
        prompt_built := "retry_prompt";
        phase := "retry_llm";

    RetryLLM:
        assert phase = "retry_llm";
        assert prompt_built = "retry_prompt";
        llm_response := "retry_response";
        llm_call_count := llm_call_count + 1;
        phase := "extract_code_retry";

    ExtractCodeRetry:
        assert phase = "extract_code_retry";
        phase := "verify_retry";

    VerifyRetry:
        assert phase = "verify_retry";
        either
            verification_passed := TRUE;
            phase := "success";
        or
            verification_passed := FALSE;
            phase := "build_retry_prompt";
        end either;

    AfterVerifyRetry:
        if verification_passed then
            terminated := TRUE;
            goto Terminate;
        elsif retry_count >= MaxRetries then
            retries_exhausted := TRUE;
            phase := "exhausted";
            terminated := TRUE;
            goto Terminate;
        else
            goto BuildRetryPrompt;
        end if;

    Terminate:
        assert terminated = TRUE;
        assert phase = "success" \/ phase = "exhausted";
        assert llm_call_count >= 3;
        assert pass1_done /\ pass2_done /\ pass3_done;
        assert code_extracted;
        assert retry_count <= MaxRetries;
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "cdc4ecd1" /\ chksum(tla) = "66c6dab6")
VARIABLES pc, phase, llm_call_count, pass1_done, pass2_done, pass3_done, 
          code_extracted, verification_passed, retry_count, prompt_built, 
          llm_response, terminated, retries_exhausted

(* define statement *)
ValidPhase ==
    phase \in {
        "build_test_plan_prompt", "pass1_llm",
        "build_review_prompt",    "pass2_llm",
        "build_codegen_prompt",   "pass3_llm",
        "extract_code",           "verify",
        "build_retry_prompt",     "retry_llm",
        "extract_code_retry",     "verify_retry",
        "success",                "exhausted"
    }

PassesAreOrdered ==
    (pass2_done => pass1_done) /\ (pass3_done => pass2_done)

ExactlyThreeLLMCallsBeforeExtract ==
    code_extracted => llm_call_count >= 3

NoExtraLLMCallsInMainPasses ==
    (pass3_done /\ ~code_extracted) => llm_call_count = 3

RetryOnlyAfterVerifyFail ==
    (retry_count > 0) =>
        (pass1_done /\ pass2_done /\ pass3_done /\ code_extracted)

RetryBounded == retry_count <= MaxRetries

TerminationMeansSuccessOrExhausted ==
    terminated => (phase = "success" \/ phase = "exhausted")

SuccessImpliesVerified ==
    phase = "success" => verification_passed


vars == << pc, phase, llm_call_count, pass1_done, pass2_done, pass3_done, 
           code_extracted, verification_passed, retry_count, prompt_built, 
           llm_response, terminated, retries_exhausted >>

ProcSet == {"gen_tests_worker"}

Init == (* Global variables *)
        /\ phase = "build_test_plan_prompt"
        /\ llm_call_count = 0
        /\ pass1_done = FALSE
        /\ pass2_done = FALSE
        /\ pass3_done = FALSE
        /\ code_extracted = FALSE
        /\ verification_passed = FALSE
        /\ retry_count = 0
        /\ prompt_built = "none"
        /\ llm_response = "none"
        /\ terminated = FALSE
        /\ retries_exhausted = FALSE
        /\ pc = [self \in ProcSet |-> "BuildTestPlanPrompt"]

BuildTestPlanPrompt == /\ pc["gen_tests_worker"] = "BuildTestPlanPrompt"
                       /\ Assert(phase = "build_test_plan_prompt", 
                                 "Failure of assertion at line 66, column 9.")
                       /\ prompt_built' = "test_plan_prompt"
                       /\ phase' = "pass1_llm"
                       /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Pass1LLM"]
                       /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                       pass3_done, code_extracted, 
                                       verification_passed, retry_count, 
                                       llm_response, terminated, 
                                       retries_exhausted >>

Pass1LLM == /\ pc["gen_tests_worker"] = "Pass1LLM"
            /\ Assert(phase = "pass1_llm", 
                      "Failure of assertion at line 71, column 9.")
            /\ Assert(prompt_built = "test_plan_prompt", 
                      "Failure of assertion at line 72, column 9.")
            /\ llm_response' = "test_plan_response"
            /\ llm_call_count' = llm_call_count + 1
            /\ pass1_done' = TRUE
            /\ phase' = "build_review_prompt"
            /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "BuildReviewPrompt"]
            /\ UNCHANGED << pass2_done, pass3_done, code_extracted, 
                            verification_passed, retry_count, prompt_built, 
                            terminated, retries_exhausted >>

BuildReviewPrompt == /\ pc["gen_tests_worker"] = "BuildReviewPrompt"
                     /\ Assert(phase = "build_review_prompt", 
                               "Failure of assertion at line 79, column 9.")
                     /\ Assert(pass1_done = TRUE, 
                               "Failure of assertion at line 80, column 9.")
                     /\ prompt_built' = "review_prompt"
                     /\ phase' = "pass2_llm"
                     /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Pass2LLM"]
                     /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                     pass3_done, code_extracted, 
                                     verification_passed, retry_count, 
                                     llm_response, terminated, 
                                     retries_exhausted >>

Pass2LLM == /\ pc["gen_tests_worker"] = "Pass2LLM"
            /\ Assert(phase = "pass2_llm", 
                      "Failure of assertion at line 85, column 9.")
            /\ Assert(prompt_built = "review_prompt", 
                      "Failure of assertion at line 86, column 9.")
            /\ llm_response' = "review_response"
            /\ llm_call_count' = llm_call_count + 1
            /\ pass2_done' = TRUE
            /\ phase' = "build_codegen_prompt"
            /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "BuildCodegenPrompt"]
            /\ UNCHANGED << pass1_done, pass3_done, code_extracted, 
                            verification_passed, retry_count, prompt_built, 
                            terminated, retries_exhausted >>

BuildCodegenPrompt == /\ pc["gen_tests_worker"] = "BuildCodegenPrompt"
                      /\ Assert(phase = "build_codegen_prompt", 
                                "Failure of assertion at line 93, column 9.")
                      /\ Assert(pass2_done = TRUE, 
                                "Failure of assertion at line 94, column 9.")
                      /\ prompt_built' = "codegen_prompt"
                      /\ phase' = "pass3_llm"
                      /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Pass3LLM"]
                      /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                      pass3_done, code_extracted, 
                                      verification_passed, retry_count, 
                                      llm_response, terminated, 
                                      retries_exhausted >>

Pass3LLM == /\ pc["gen_tests_worker"] = "Pass3LLM"
            /\ Assert(phase = "pass3_llm", 
                      "Failure of assertion at line 99, column 9.")
            /\ Assert(prompt_built = "codegen_prompt", 
                      "Failure of assertion at line 100, column 9.")
            /\ llm_response' = "codegen_response"
            /\ llm_call_count' = llm_call_count + 1
            /\ pass3_done' = TRUE
            /\ phase' = "extract_code"
            /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "ExtractCode"]
            /\ UNCHANGED << pass1_done, pass2_done, code_extracted, 
                            verification_passed, retry_count, prompt_built, 
                            terminated, retries_exhausted >>

ExtractCode == /\ pc["gen_tests_worker"] = "ExtractCode"
               /\ Assert(phase = "extract_code", 
                         "Failure of assertion at line 107, column 9.")
               /\ Assert(llm_call_count = 3, 
                         "Failure of assertion at line 108, column 9.")
               /\ Assert(pass1_done /\ pass2_done /\ pass3_done, 
                         "Failure of assertion at line 109, column 9.")
               /\ code_extracted' = TRUE
               /\ phase' = "verify"
               /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Verify"]
               /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                               pass3_done, verification_passed, retry_count, 
                               prompt_built, llm_response, terminated, 
                               retries_exhausted >>

Verify == /\ pc["gen_tests_worker"] = "Verify"
          /\ Assert(phase = "verify", 
                    "Failure of assertion at line 114, column 9.")
          /\ Assert(code_extracted = TRUE, 
                    "Failure of assertion at line 115, column 9.")
          /\ \/ /\ verification_passed' = TRUE
                /\ phase' = "success"
             \/ /\ verification_passed' = FALSE
                /\ phase' = "build_retry_prompt"
          /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "AfterVerify"]
          /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, pass3_done, 
                          code_extracted, retry_count, prompt_built, 
                          llm_response, terminated, retries_exhausted >>

AfterVerify == /\ pc["gen_tests_worker"] = "AfterVerify"
               /\ IF verification_passed
                     THEN /\ terminated' = TRUE
                          /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Terminate"]
                          /\ UNCHANGED << phase, retries_exhausted >>
                     ELSE /\ IF retry_count >= MaxRetries
                                THEN /\ retries_exhausted' = TRUE
                                     /\ phase' = "exhausted"
                                     /\ terminated' = TRUE
                                     /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Terminate"]
                                ELSE /\ TRUE
                                     /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "BuildRetryPrompt"]
                                     /\ UNCHANGED << phase, terminated, 
                                                     retries_exhausted >>
               /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                               pass3_done, code_extracted, verification_passed, 
                               retry_count, prompt_built, llm_response >>

BuildRetryPrompt == /\ pc["gen_tests_worker"] = "BuildRetryPrompt"
                    /\ Assert(phase = "build_retry_prompt", 
                              "Failure of assertion at line 138, column 9.")
                    /\ Assert(~verification_passed, 
                              "Failure of assertion at line 139, column 9.")
                    /\ retry_count' = retry_count + 1
                    /\ prompt_built' = "retry_prompt"
                    /\ phase' = "retry_llm"
                    /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "RetryLLM"]
                    /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                    pass3_done, code_extracted, 
                                    verification_passed, llm_response, 
                                    terminated, retries_exhausted >>

RetryLLM == /\ pc["gen_tests_worker"] = "RetryLLM"
            /\ Assert(phase = "retry_llm", 
                      "Failure of assertion at line 145, column 9.")
            /\ Assert(prompt_built = "retry_prompt", 
                      "Failure of assertion at line 146, column 9.")
            /\ llm_response' = "retry_response"
            /\ llm_call_count' = llm_call_count + 1
            /\ phase' = "extract_code_retry"
            /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "ExtractCodeRetry"]
            /\ UNCHANGED << pass1_done, pass2_done, pass3_done, code_extracted, 
                            verification_passed, retry_count, prompt_built, 
                            terminated, retries_exhausted >>

ExtractCodeRetry == /\ pc["gen_tests_worker"] = "ExtractCodeRetry"
                    /\ Assert(phase = "extract_code_retry", 
                              "Failure of assertion at line 152, column 9.")
                    /\ phase' = "verify_retry"
                    /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "VerifyRetry"]
                    /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                    pass3_done, code_extracted, 
                                    verification_passed, retry_count, 
                                    prompt_built, llm_response, terminated, 
                                    retries_exhausted >>

VerifyRetry == /\ pc["gen_tests_worker"] = "VerifyRetry"
               /\ Assert(phase = "verify_retry", 
                         "Failure of assertion at line 156, column 9.")
               /\ \/ /\ verification_passed' = TRUE
                     /\ phase' = "success"
                  \/ /\ verification_passed' = FALSE
                     /\ phase' = "build_retry_prompt"
               /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "AfterVerifyRetry"]
               /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                               pass3_done, code_extracted, retry_count, 
                               prompt_built, llm_response, terminated, 
                               retries_exhausted >>

AfterVerifyRetry == /\ pc["gen_tests_worker"] = "AfterVerifyRetry"
                    /\ IF verification_passed
                          THEN /\ terminated' = TRUE
                               /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Terminate"]
                               /\ UNCHANGED << phase, retries_exhausted >>
                          ELSE /\ IF retry_count >= MaxRetries
                                     THEN /\ retries_exhausted' = TRUE
                                          /\ phase' = "exhausted"
                                          /\ terminated' = TRUE
                                          /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Terminate"]
                                     ELSE /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "BuildRetryPrompt"]
                                          /\ UNCHANGED << phase, terminated, 
                                                          retries_exhausted >>
                    /\ UNCHANGED << llm_call_count, pass1_done, pass2_done, 
                                    pass3_done, code_extracted, 
                                    verification_passed, retry_count, 
                                    prompt_built, llm_response >>

Terminate == /\ pc["gen_tests_worker"] = "Terminate"
             /\ Assert(terminated = TRUE, 
                       "Failure of assertion at line 179, column 9.")
             /\ Assert(phase = "success" \/ phase = "exhausted", 
                       "Failure of assertion at line 180, column 9.")
             /\ Assert(llm_call_count >= 3, 
                       "Failure of assertion at line 181, column 9.")
             /\ Assert(pass1_done /\ pass2_done /\ pass3_done, 
                       "Failure of assertion at line 182, column 9.")
             /\ Assert(code_extracted, 
                       "Failure of assertion at line 183, column 9.")
             /\ Assert(retry_count <= MaxRetries, 
                       "Failure of assertion at line 184, column 9.")
             /\ TRUE
             /\ pc' = [pc EXCEPT !["gen_tests_worker"] = "Done"]
             /\ UNCHANGED << phase, llm_call_count, pass1_done, pass2_done, 
                             pass3_done, code_extracted, verification_passed, 
                             retry_count, prompt_built, llm_response, 
                             terminated, retries_exhausted >>

worker == BuildTestPlanPrompt \/ Pass1LLM \/ BuildReviewPrompt \/ Pass2LLM
             \/ BuildCodegenPrompt \/ Pass3LLM \/ ExtractCode \/ Verify
             \/ AfterVerify \/ BuildRetryPrompt \/ RetryLLM
             \/ ExtractCodeRetry \/ VerifyRetry \/ AfterVerifyRetry
             \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

================================================================================
