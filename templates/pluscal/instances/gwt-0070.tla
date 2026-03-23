---- MODULE CrossCuttingCLI ----

EXTENDS Integers, TLC

(*--algorithm CrossCuttingCLI

variables
    cross_cutting \in BOOLEAN,
    json_flag \in BOOLEAN,
    rules_file_exists \in BOOLEAN,
    has_seam_report = FALSE,
    has_behavioral_report = FALSE,
    has_behavioral_json = FALSE,
    stderr_error = FALSE,
    exit_code = 0,
    rules_loaded = FALSE,
    terminated = FALSE;

define

    BackwardCompatible ==
        (terminated /\ ~cross_cutting) =>
            (~has_behavioral_report /\ ~has_behavioral_json)

    FlagEnablesBehavioral ==
        (terminated /\ cross_cutting /\ rules_file_exists) =>
            has_behavioral_report

    JsonIncludesBehavioral ==
        (terminated /\ json_flag /\ cross_cutting /\ rules_file_exists) =>
            has_behavioral_json

    MissingRulesError ==
        (terminated /\ cross_cutting /\ ~rules_file_exists) =>
            (stderr_error /\ exit_code = 1)

    BothReportsPresent ==
        (terminated /\ cross_cutting /\ rules_file_exists) =>
            (has_seam_report /\ has_behavioral_report)

    SeamReportAlwaysPresent ==
        (terminated /\ ~stderr_error) =>
            has_seam_report

    NoSpuriousBehavioralOnError ==
        (terminated /\ stderr_error) =>
            (~has_behavioral_report /\ ~has_behavioral_json)

    ExitCodeCleanOnSuccess ==
        (terminated /\ ~stderr_error) =>
            (exit_code = 0)

end define;

fair process cmd_seams_proc = "cmd_seams"
begin
    ParseFlags:
        skip;

    LoadRules:
        if cross_cutting then
            if rules_file_exists then
                rules_loaded := TRUE;
            else
                stderr_error := TRUE;
                exit_code := 1;
                goto Finish;
            end if;
        end if;

    RunSeamCheck:
        has_seam_report := TRUE;

    RunBehavioralCheck:
        if cross_cutting /\ rules_loaded then
            has_behavioral_report := TRUE;
        end if;

    FormatOutput:
        if json_flag /\ cross_cutting /\ rules_loaded then
            has_behavioral_json := TRUE;
        end if;

    Finish:
        terminated := TRUE;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f1394b55" /\ chksum(tla) = "7011bacf")
VARIABLES pc, cross_cutting, json_flag, rules_file_exists, has_seam_report, 
          has_behavioral_report, has_behavioral_json, stderr_error, exit_code, 
          rules_loaded, terminated

(* define statement *)
BackwardCompatible ==
    (terminated /\ ~cross_cutting) =>
        (~has_behavioral_report /\ ~has_behavioral_json)

FlagEnablesBehavioral ==
    (terminated /\ cross_cutting /\ rules_file_exists) =>
        has_behavioral_report

JsonIncludesBehavioral ==
    (terminated /\ json_flag /\ cross_cutting /\ rules_file_exists) =>
        has_behavioral_json

MissingRulesError ==
    (terminated /\ cross_cutting /\ ~rules_file_exists) =>
        (stderr_error /\ exit_code = 1)

BothReportsPresent ==
    (terminated /\ cross_cutting /\ rules_file_exists) =>
        (has_seam_report /\ has_behavioral_report)

SeamReportAlwaysPresent ==
    (terminated /\ ~stderr_error) =>
        has_seam_report

NoSpuriousBehavioralOnError ==
    (terminated /\ stderr_error) =>
        (~has_behavioral_report /\ ~has_behavioral_json)

ExitCodeCleanOnSuccess ==
    (terminated /\ ~stderr_error) =>
        (exit_code = 0)


vars == << pc, cross_cutting, json_flag, rules_file_exists, has_seam_report, 
           has_behavioral_report, has_behavioral_json, stderr_error, 
           exit_code, rules_loaded, terminated >>

ProcSet == {"cmd_seams"}

Init == (* Global variables *)
        /\ cross_cutting \in BOOLEAN
        /\ json_flag \in BOOLEAN
        /\ rules_file_exists \in BOOLEAN
        /\ has_seam_report = FALSE
        /\ has_behavioral_report = FALSE
        /\ has_behavioral_json = FALSE
        /\ stderr_error = FALSE
        /\ exit_code = 0
        /\ rules_loaded = FALSE
        /\ terminated = FALSE
        /\ pc = [self \in ProcSet |-> "ParseFlags"]

ParseFlags == /\ pc["cmd_seams"] = "ParseFlags"
              /\ TRUE
              /\ pc' = [pc EXCEPT !["cmd_seams"] = "LoadRules"]
              /\ UNCHANGED << cross_cutting, json_flag, rules_file_exists, 
                              has_seam_report, has_behavioral_report, 
                              has_behavioral_json, stderr_error, exit_code, 
                              rules_loaded, terminated >>

LoadRules == /\ pc["cmd_seams"] = "LoadRules"
             /\ IF cross_cutting
                   THEN /\ IF rules_file_exists
                              THEN /\ rules_loaded' = TRUE
                                   /\ pc' = [pc EXCEPT !["cmd_seams"] = "RunSeamCheck"]
                                   /\ UNCHANGED << stderr_error, exit_code >>
                              ELSE /\ stderr_error' = TRUE
                                   /\ exit_code' = 1
                                   /\ pc' = [pc EXCEPT !["cmd_seams"] = "Finish"]
                                   /\ UNCHANGED rules_loaded
                   ELSE /\ pc' = [pc EXCEPT !["cmd_seams"] = "RunSeamCheck"]
                        /\ UNCHANGED << stderr_error, exit_code, rules_loaded >>
             /\ UNCHANGED << cross_cutting, json_flag, rules_file_exists, 
                             has_seam_report, has_behavioral_report, 
                             has_behavioral_json, terminated >>

RunSeamCheck == /\ pc["cmd_seams"] = "RunSeamCheck"
                /\ has_seam_report' = TRUE
                /\ pc' = [pc EXCEPT !["cmd_seams"] = "RunBehavioralCheck"]
                /\ UNCHANGED << cross_cutting, json_flag, rules_file_exists, 
                                has_behavioral_report, has_behavioral_json, 
                                stderr_error, exit_code, rules_loaded, 
                                terminated >>

RunBehavioralCheck == /\ pc["cmd_seams"] = "RunBehavioralCheck"
                      /\ IF cross_cutting /\ rules_loaded
                            THEN /\ has_behavioral_report' = TRUE
                            ELSE /\ TRUE
                                 /\ UNCHANGED has_behavioral_report
                      /\ pc' = [pc EXCEPT !["cmd_seams"] = "FormatOutput"]
                      /\ UNCHANGED << cross_cutting, json_flag, 
                                      rules_file_exists, has_seam_report, 
                                      has_behavioral_json, stderr_error, 
                                      exit_code, rules_loaded, terminated >>

FormatOutput == /\ pc["cmd_seams"] = "FormatOutput"
                /\ IF json_flag /\ cross_cutting /\ rules_loaded
                      THEN /\ has_behavioral_json' = TRUE
                      ELSE /\ TRUE
                           /\ UNCHANGED has_behavioral_json
                /\ pc' = [pc EXCEPT !["cmd_seams"] = "Finish"]
                /\ UNCHANGED << cross_cutting, json_flag, rules_file_exists, 
                                has_seam_report, has_behavioral_report, 
                                stderr_error, exit_code, rules_loaded, 
                                terminated >>

Finish == /\ pc["cmd_seams"] = "Finish"
          /\ terminated' = TRUE
          /\ pc' = [pc EXCEPT !["cmd_seams"] = "Done"]
          /\ UNCHANGED << cross_cutting, json_flag, rules_file_exists, 
                          has_seam_report, has_behavioral_report, 
                          has_behavioral_json, stderr_error, exit_code, 
                          rules_loaded >>

cmd_seams_proc == ParseFlags \/ LoadRules \/ RunSeamCheck
                     \/ RunBehavioralCheck \/ FormatOutput \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == cmd_seams_proc
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(cmd_seams_proc)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM BackwardCompatible /\ FlagEnablesBehavioral /\ JsonIncludesBehavioral
     /\ MissingRulesError /\ BothReportsPresent /\ SeamReportAlwaysPresent
     /\ NoSpuriousBehavioralOnError /\ ExitCodeCleanOnSuccess

====
