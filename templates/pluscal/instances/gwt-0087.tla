---- MODULE ExtractFindings ----

EXTENDS Integers, TLC

(* --algorithm ExtractFindings

variables
    input_valid      \in {TRUE, FALSE},
    input_has_issues \in {TRUE, FALSE},
    parsed           = FALSE,
    pass_name        = "",
    issues_count     = 0,
    report_path      = "null",
    exception_raised = FALSE,
    result_ready     = FALSE;

define

    IssuesListType ==
        issues_count >= 0

    NoExceptionLeaks ==
        ~exception_raised

    GracefulDegradation ==
        (result_ready /\ ~parsed) =>
            (issues_count = 0 /\ report_path = "null")

    StructuredOutput ==
        (result_ready /\ parsed) =>
            (pass_name # "" /\ issues_count >= 0 /\ report_path # "null")

    PassNamePreserved ==
        (result_ready /\ parsed) => (pass_name # "")

    EmptyStringHandled ==
        (~input_valid /\ result_ready) =>
            (issues_count = 0 /\ report_path = "null")

    IssuesNonNegative ==
        issues_count >= 0

end define;

fair process extractor = "extractor"
begin
    AttemptParse:
        if input_valid then
            parsed := TRUE
        else
            parsed           := FALSE;
            exception_raised := FALSE
        end if;

    BuildResult:
        if parsed then
            pass_name    := "coverage";
            issues_count := IF input_has_issues THEN 1 ELSE 0;
            report_path  := "thoughts/searchable/shared/plans/coverage_report.md"
        else
            pass_name    := "";
            issues_count := 0;
            report_path  := "null"
        end if;
        result_ready := TRUE;

    Finish:
        assert ~exception_raised;
        assert result_ready;
        assert issues_count >= 0

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e457d84d" /\ chksum(tla) = "ad7225b0")
VARIABLES pc, input_valid, input_has_issues, parsed, pass_name, issues_count, 
          report_path, exception_raised, result_ready

(* define statement *)
IssuesListType ==
    issues_count >= 0

NoExceptionLeaks ==
    ~exception_raised

GracefulDegradation ==
    (result_ready /\ ~parsed) =>
        (issues_count = 0 /\ report_path = "null")

StructuredOutput ==
    (result_ready /\ parsed) =>
        (pass_name # "" /\ issues_count >= 0 /\ report_path # "null")

PassNamePreserved ==
    (result_ready /\ parsed) => (pass_name # "")

EmptyStringHandled ==
    (~input_valid /\ result_ready) =>
        (issues_count = 0 /\ report_path = "null")

IssuesNonNegative ==
    issues_count >= 0


vars == << pc, input_valid, input_has_issues, parsed, pass_name, issues_count, 
           report_path, exception_raised, result_ready >>

ProcSet == {"extractor"}

Init == (* Global variables *)
        /\ input_valid \in {TRUE, FALSE}
        /\ input_has_issues \in {TRUE, FALSE}
        /\ parsed = FALSE
        /\ pass_name = ""
        /\ issues_count = 0
        /\ report_path = "null"
        /\ exception_raised = FALSE
        /\ result_ready = FALSE
        /\ pc = [self \in ProcSet |-> "AttemptParse"]

AttemptParse == /\ pc["extractor"] = "AttemptParse"
                /\ IF input_valid
                      THEN /\ parsed' = TRUE
                           /\ UNCHANGED exception_raised
                      ELSE /\ parsed' = FALSE
                           /\ exception_raised' = FALSE
                /\ pc' = [pc EXCEPT !["extractor"] = "BuildResult"]
                /\ UNCHANGED << input_valid, input_has_issues, pass_name, 
                                issues_count, report_path, result_ready >>

BuildResult == /\ pc["extractor"] = "BuildResult"
               /\ IF parsed
                     THEN /\ pass_name' = "coverage"
                          /\ issues_count' = IF input_has_issues THEN 1 ELSE 0
                          /\ report_path' = "thoughts/searchable/shared/plans/coverage_report.md"
                     ELSE /\ pass_name' = ""
                          /\ issues_count' = 0
                          /\ report_path' = "null"
               /\ result_ready' = TRUE
               /\ pc' = [pc EXCEPT !["extractor"] = "Finish"]
               /\ UNCHANGED << input_valid, input_has_issues, parsed, 
                               exception_raised >>

Finish == /\ pc["extractor"] = "Finish"
          /\ Assert(~exception_raised, 
                    "Failure of assertion at line 68, column 9.")
          /\ Assert(result_ready, 
                    "Failure of assertion at line 69, column 9.")
          /\ Assert(issues_count >= 0, 
                    "Failure of assertion at line 70, column 9.")
          /\ pc' = [pc EXCEPT !["extractor"] = "Done"]
          /\ UNCHANGED << input_valid, input_has_issues, parsed, pass_name, 
                          issues_count, report_path, exception_raised, 
                          result_ready >>

extractor == AttemptParse \/ BuildResult \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == extractor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(extractor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
