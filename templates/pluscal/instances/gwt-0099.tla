---- MODULE CorrectionAgentFreshContext ----

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    PassNames,
    MaxSteps

ASSUME PassNames # {} /\ MaxSteps > 0

(* --algorithm CorrectionAgentFreshContext

variables
    phase = "idle",
    review_session_id = "review-session-abc123",
    review_findings = [missing |-> "test_foo", coverage |-> "low"],
    review_report_path = "/tmp/reviews/coverage_report.md",
    query_args = [
        prompt     |-> "",
        resume     |-> TRUE,
        session_id |-> review_session_id,
        options    |-> "default"
    ],
    correction_input = [
        pass_name   |-> "",
        findings    |-> [missing |-> "", coverage |-> ""],
        report_path |-> ""
    ],
    step_count = 0,
    construction_done = FALSE;

define

    NoResume ==
        construction_done => (query_args.resume = FALSE)

    NoSessionCarryover ==
        construction_done => (query_args.session_id = "ABSENT")

    FindingsPresent ==
        construction_done =>
            (correction_input.findings = review_findings /\
             correction_input.findings # [missing |-> "", coverage |-> ""])

    ReportPathPresent ==
        construction_done =>
            (correction_input.report_path = review_report_path /\
             correction_input.report_path # "")

    CleanContext ==
        construction_done =>
            (query_args.session_id = "ABSENT" /\
             query_args.resume = FALSE)

    BoundedExecution == step_count <= MaxSteps

    AllInvariants ==
        NoResume /\
        NoSessionCarryover /\
        FindingsPresent /\
        ReportPathPresent /\
        CleanContext /\
        BoundedExecution

end define;

fair process correctionSpawner = "spawner"
begin
    ReviewFails:
        phase := "review_failed";
        step_count := step_count + 1;

    BuildCorrectionInput:
        correction_input := [
            pass_name   |-> "coverage",
            findings    |-> review_findings,
            report_path |-> review_report_path
        ];
        phase := "correction_input_built";
        step_count := step_count + 1;

    ConstructQuery:
        query_args := [
            prompt     |-> "findings=" \o "test_foo" \o " report=" \o review_report_path,
            resume     |-> FALSE,
            session_id |-> "ABSENT",
            options    |-> "default"
        ];
        phase := "query_constructed";
        step_count := step_count + 1;

    MarkConstructionDone:
        construction_done := TRUE;
        phase := "ready_to_dispatch";
        step_count := step_count + 1;

    Finish:
        phase := "dispatched";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "7d7f9c45" /\ chksum(tla) = "a0bce2f9")
VARIABLES pc, phase, review_session_id, review_findings, review_report_path, 
          query_args, correction_input, step_count, construction_done

(* define statement *)
NoResume ==
    construction_done => (query_args.resume = FALSE)

NoSessionCarryover ==
    construction_done => (query_args.session_id = "ABSENT")

FindingsPresent ==
    construction_done =>
        (correction_input.findings = review_findings /\
         correction_input.findings # [missing |-> "", coverage |-> ""])

ReportPathPresent ==
    construction_done =>
        (correction_input.report_path = review_report_path /\
         correction_input.report_path # "")

CleanContext ==
    construction_done =>
        (query_args.session_id = "ABSENT" /\
         query_args.resume = FALSE)

BoundedExecution == step_count <= MaxSteps

AllInvariants ==
    NoResume /\
    NoSessionCarryover /\
    FindingsPresent /\
    ReportPathPresent /\
    CleanContext /\
    BoundedExecution


vars == << pc, phase, review_session_id, review_findings, review_report_path, 
           query_args, correction_input, step_count, construction_done >>

ProcSet == {"spawner"}

Init == (* Global variables *)
        /\ phase = "idle"
        /\ review_session_id = "review-session-abc123"
        /\ review_findings = [missing |-> "test_foo", coverage |-> "low"]
        /\ review_report_path = "/tmp/reviews/coverage_report.md"
        /\ query_args =              [
                            prompt     |-> "",
                            resume     |-> TRUE,
                            session_id |-> review_session_id,
                            options    |-> "default"
                        ]
        /\ correction_input =                    [
                                  pass_name   |-> "",
                                  findings    |-> [missing |-> "", coverage |-> ""],
                                  report_path |-> ""
                              ]
        /\ step_count = 0
        /\ construction_done = FALSE
        /\ pc = [self \in ProcSet |-> "ReviewFails"]

ReviewFails == /\ pc["spawner"] = "ReviewFails"
               /\ phase' = "review_failed"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["spawner"] = "BuildCorrectionInput"]
               /\ UNCHANGED << review_session_id, review_findings, 
                               review_report_path, query_args, 
                               correction_input, construction_done >>

BuildCorrectionInput == /\ pc["spawner"] = "BuildCorrectionInput"
                        /\ correction_input' =                     [
                                                   pass_name   |-> "coverage",
                                                   findings    |-> review_findings,
                                                   report_path |-> review_report_path
                                               ]
                        /\ phase' = "correction_input_built"
                        /\ step_count' = step_count + 1
                        /\ pc' = [pc EXCEPT !["spawner"] = "ConstructQuery"]
                        /\ UNCHANGED << review_session_id, review_findings, 
                                        review_report_path, query_args, 
                                        construction_done >>

ConstructQuery == /\ pc["spawner"] = "ConstructQuery"
                  /\ query_args' =               [
                                       prompt     |-> "findings=" \o "test_foo" \o " report=" \o review_report_path,
                                       resume     |-> FALSE,
                                       session_id |-> "ABSENT",
                                       options    |-> "default"
                                   ]
                  /\ phase' = "query_constructed"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["spawner"] = "MarkConstructionDone"]
                  /\ UNCHANGED << review_session_id, review_findings, 
                                  review_report_path, correction_input, 
                                  construction_done >>

MarkConstructionDone == /\ pc["spawner"] = "MarkConstructionDone"
                        /\ construction_done' = TRUE
                        /\ phase' = "ready_to_dispatch"
                        /\ step_count' = step_count + 1
                        /\ pc' = [pc EXCEPT !["spawner"] = "Finish"]
                        /\ UNCHANGED << review_session_id, review_findings, 
                                        review_report_path, query_args, 
                                        correction_input >>

Finish == /\ pc["spawner"] = "Finish"
          /\ phase' = "dispatched"
          /\ pc' = [pc EXCEPT !["spawner"] = "Done"]
          /\ UNCHANGED << review_session_id, review_findings, 
                          review_report_path, query_args, correction_input, 
                          step_count, construction_done >>

correctionSpawner == ReviewFails \/ BuildCorrectionInput \/ ConstructQuery
                        \/ MarkConstructionDone \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == correctionSpawner
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(correctionSpawner)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
