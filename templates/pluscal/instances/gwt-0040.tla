---- MODULE TestGenPipeline ----

EXTENDS Integers, TLC

CONSTANTS MaxAttempts

ASSUME MaxAttempts \in Nat /\ MaxAttempts >= 1

(* --algorithm TestGenPipeline

variables
    pass_completed    = "NONE",
    verification_stage = "NONE",
    verification_passed = FALSE,
    attempt           = 1,
    file_written      = FALSE,
    pipeline_done     = FALSE,
    vfailed           = FALSE;

define

    PassValues  == {"NONE", "PLAN", "REVIEW", "CODEGEN"}
    StageValues == {"NONE", "COMPILE", "COLLECT", "RUN"}

    TypeOK ==
        /\ pass_completed     \in PassValues
        /\ verification_stage \in StageValues
        /\ verification_passed \in BOOLEAN
        /\ attempt            \in 1..MaxAttempts
        /\ file_written       \in BOOLEAN
        /\ pipeline_done      \in BOOLEAN

    \* File is only written once codegen completes
    FileWrittenOnlyAfterCodegen ==
        file_written => pass_completed = "CODEGEN"

    \* Verification never starts until the test file exists
    VerificationRequiresFile ==
        verification_stage # "NONE" => file_written

    \* Verification never starts until codegen completed
    VerificationRequiresCodegen ==
        verification_stage # "NONE" => pass_completed = "CODEGEN"

    \* Verification can only pass at the RUN stage (all three stages traversed)
    VerificationPassedRequiresRun ==
        verification_passed => verification_stage = "RUN"

    \* Verification passing requires a written file from a completed codegen pass
    VerificationPassedRequiresCodegen ==
        verification_passed =>
            /\ file_written
            /\ pass_completed = "CODEGEN"

    \* Retry only resets to codegen input level, never below REVIEW
    RetryNeverBelowReview ==
        (pipeline_done = FALSE /\ pass_completed = "REVIEW")
            => ~file_written

    AttemptBounded ==
        attempt \in 1..MaxAttempts

    \* Pipeline only terminates on success or exhausted retries
    TerminationSound ==
        pipeline_done =>
            verification_passed \/ attempt = MaxAttempts

end define;

fair process pipeline = "main"
begin

    RunPlan:
        pass_completed := "PLAN";

    RunReview:
        \* Pass 2 strictly consumes Pass 1 output
        assert pass_completed = "PLAN";
        pass_completed := "REVIEW";

    CodegenLoop:
        while ~pipeline_done do

            DoCodegen:
                \* Pass 3 strictly consumes Pass 2 output
                assert pass_completed \in {"REVIEW", "CODEGEN"};
                pass_completed     := "CODEGEN";
                file_written       := TRUE;
                verification_stage := "NONE";
                vfailed            := FALSE;

            DoCompile:
                \* Stage 1 of verification: Python AST parse
                assert file_written;
                verification_stage := "COMPILE";
                either
                    skip;
                or
                    vfailed := TRUE;
                end either;

            DoCollect:
                \* Stage 2: pytest --collect-only (skipped if compile failed)
                if ~vfailed then
                    verification_stage := "COLLECT";
                    either
                        skip;
                    or
                        vfailed := TRUE;
                    end either;
                end if;

            DoRun:
                \* Stage 3: pytest -x -v (skipped if any prior stage failed)
                if ~vfailed then
                    verification_stage := "RUN";
                    either
                        verification_passed := TRUE;
                        pipeline_done       := TRUE;
                    or
                        vfailed := TRUE;
                    end either;
                end if;

            CheckRetry:
                \* On failure: retry codegen only (not plan/review), bounded by MaxAttempts
                if vfailed then
                    if attempt < MaxAttempts then
                        attempt            := attempt + 1;
                        pass_completed     := "REVIEW";
                        file_written       := FALSE;
                        verification_stage := "NONE";
                    else
                        pipeline_done := TRUE;
                    end if;
                end if;

        end while;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "85019cdb" /\ chksum(tla) = "fd4f1010")
VARIABLES pc, pass_completed, verification_stage, verification_passed, 
          attempt, file_written, pipeline_done, vfailed

(* define statement *)
PassValues  == {"NONE", "PLAN", "REVIEW", "CODEGEN"}
StageValues == {"NONE", "COMPILE", "COLLECT", "RUN"}

TypeOK ==
    /\ pass_completed     \in PassValues
    /\ verification_stage \in StageValues
    /\ verification_passed \in BOOLEAN
    /\ attempt            \in 1..MaxAttempts
    /\ file_written       \in BOOLEAN
    /\ pipeline_done      \in BOOLEAN


FileWrittenOnlyAfterCodegen ==
    file_written => pass_completed = "CODEGEN"


VerificationRequiresFile ==
    verification_stage # "NONE" => file_written


VerificationRequiresCodegen ==
    verification_stage # "NONE" => pass_completed = "CODEGEN"


VerificationPassedRequiresRun ==
    verification_passed => verification_stage = "RUN"


VerificationPassedRequiresCodegen ==
    verification_passed =>
        /\ file_written
        /\ pass_completed = "CODEGEN"


RetryNeverBelowReview ==
    (pipeline_done = FALSE /\ pass_completed = "REVIEW")
        => ~file_written

AttemptBounded ==
    attempt \in 1..MaxAttempts


TerminationSound ==
    pipeline_done =>
        verification_passed \/ attempt = MaxAttempts


vars == << pc, pass_completed, verification_stage, verification_passed, 
           attempt, file_written, pipeline_done, vfailed >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ pass_completed = "NONE"
        /\ verification_stage = "NONE"
        /\ verification_passed = FALSE
        /\ attempt = 1
        /\ file_written = FALSE
        /\ pipeline_done = FALSE
        /\ vfailed = FALSE
        /\ pc = [self \in ProcSet |-> "RunPlan"]

RunPlan == /\ pc["main"] = "RunPlan"
           /\ pass_completed' = "PLAN"
           /\ pc' = [pc EXCEPT !["main"] = "RunReview"]
           /\ UNCHANGED << verification_stage, verification_passed, attempt, 
                           file_written, pipeline_done, vfailed >>

RunReview == /\ pc["main"] = "RunReview"
             /\ Assert(pass_completed = "PLAN", 
                       "Failure of assertion at line 78, column 9.")
             /\ pass_completed' = "REVIEW"
             /\ pc' = [pc EXCEPT !["main"] = "CodegenLoop"]
             /\ UNCHANGED << verification_stage, verification_passed, attempt, 
                             file_written, pipeline_done, vfailed >>

CodegenLoop == /\ pc["main"] = "CodegenLoop"
               /\ IF ~pipeline_done
                     THEN /\ pc' = [pc EXCEPT !["main"] = "DoCodegen"]
                     ELSE /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
               /\ UNCHANGED << pass_completed, verification_stage, 
                               verification_passed, attempt, file_written, 
                               pipeline_done, vfailed >>

DoCodegen == /\ pc["main"] = "DoCodegen"
             /\ Assert(pass_completed \in {"REVIEW", "CODEGEN"}, 
                       "Failure of assertion at line 86, column 17.")
             /\ pass_completed' = "CODEGEN"
             /\ file_written' = TRUE
             /\ verification_stage' = "NONE"
             /\ vfailed' = FALSE
             /\ pc' = [pc EXCEPT !["main"] = "DoCompile"]
             /\ UNCHANGED << verification_passed, attempt, pipeline_done >>

DoCompile == /\ pc["main"] = "DoCompile"
             /\ Assert(file_written, 
                       "Failure of assertion at line 94, column 17.")
             /\ verification_stage' = "COMPILE"
             /\ \/ /\ TRUE
                   /\ UNCHANGED vfailed
                \/ /\ vfailed' = TRUE
             /\ pc' = [pc EXCEPT !["main"] = "DoCollect"]
             /\ UNCHANGED << pass_completed, verification_passed, attempt, 
                             file_written, pipeline_done >>

DoCollect == /\ pc["main"] = "DoCollect"
             /\ IF ~vfailed
                   THEN /\ verification_stage' = "COLLECT"
                        /\ \/ /\ TRUE
                              /\ UNCHANGED vfailed
                           \/ /\ vfailed' = TRUE
                   ELSE /\ TRUE
                        /\ UNCHANGED << verification_stage, vfailed >>
             /\ pc' = [pc EXCEPT !["main"] = "DoRun"]
             /\ UNCHANGED << pass_completed, verification_passed, attempt, 
                             file_written, pipeline_done >>

DoRun == /\ pc["main"] = "DoRun"
         /\ IF ~vfailed
               THEN /\ verification_stage' = "RUN"
                    /\ \/ /\ verification_passed' = TRUE
                          /\ pipeline_done' = TRUE
                          /\ UNCHANGED vfailed
                       \/ /\ vfailed' = TRUE
                          /\ UNCHANGED <<verification_passed, pipeline_done>>
               ELSE /\ TRUE
                    /\ UNCHANGED << verification_stage, verification_passed, 
                                    pipeline_done, vfailed >>
         /\ pc' = [pc EXCEPT !["main"] = "CheckRetry"]
         /\ UNCHANGED << pass_completed, attempt, file_written >>

CheckRetry == /\ pc["main"] = "CheckRetry"
              /\ IF vfailed
                    THEN /\ IF attempt < MaxAttempts
                               THEN /\ attempt' = attempt + 1
                                    /\ pass_completed' = "REVIEW"
                                    /\ file_written' = FALSE
                                    /\ verification_stage' = "NONE"
                                    /\ UNCHANGED pipeline_done
                               ELSE /\ pipeline_done' = TRUE
                                    /\ UNCHANGED << pass_completed, 
                                                    verification_stage, 
                                                    attempt, file_written >>
                    ELSE /\ TRUE
                         /\ UNCHANGED << pass_completed, verification_stage, 
                                         attempt, file_written, pipeline_done >>
              /\ pc' = [pc EXCEPT !["main"] = "CodegenLoop"]
              /\ UNCHANGED << verification_passed, vfailed >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << pass_completed, verification_stage, 
                             verification_passed, attempt, file_written, 
                             pipeline_done, vfailed >>

pipeline == RunPlan \/ RunReview \/ CodegenLoop \/ DoCodegen \/ DoCompile
               \/ DoCollect \/ DoRun \/ CheckRetry \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == pipeline
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(pipeline)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
