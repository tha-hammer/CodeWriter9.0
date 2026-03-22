---- MODULE LoopWritesSpecOnPass ----

EXTENDS Integers

CONSTANTS MaxSteps

(* --algorithm LoopWritesSpecOnPass

variables
  loop_result = "idle",
  compiled_spec_exists = TRUE,
  cfg_exists \in {TRUE, FALSE},
  spec_dir_has_tla = FALSE,
  spec_dir_has_cfg = FALSE,
  spec_dir_has_traces = FALSE,
  phase = "start",
  step_count = 0;

define
  PassImpliesWrite ==
    phase = "done" /\ loop_result = "pass" => spec_dir_has_tla = TRUE

  FailImpliesNoWrite ==
    phase = "done" /\ loop_result = "fail" => spec_dir_has_tla = FALSE

  CfgConditional ==
    spec_dir_has_cfg = TRUE => cfg_exists = TRUE

  TracesOnPass ==
    phase = "done" /\ loop_result = "pass" => spec_dir_has_traces = TRUE

  BoundedExecution == step_count <= MaxSteps
end define;

fair process runner = "runner"
begin
  Start:
    phase := "run_loop";
    loop_result := "running";
    step_count := step_count + 1;

  RunLoop:
    either
      loop_result := "pass";
    or
      loop_result := "fail";
    end either;
    phase := "check_result";
    step_count := step_count + 1;

  CheckResult:
    if loop_result = "pass" then
      phase := "write_files";
    else
      phase := "done";
      goto Finish;
    end if;

  AfterCheck:
    step_count := step_count + 1;

  WriteTla:
    spec_dir_has_tla := TRUE;
    step_count := step_count + 1;

  WriteCfg:
    if cfg_exists then
      spec_dir_has_cfg := TRUE;
    end if;

  WriteTraces:
    spec_dir_has_traces := TRUE;
    phase := "done";
    step_count := step_count + 1;

  Finish:
    skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "fc3a0831" /\ chksum(tla) = "32bee617")
VARIABLES pc, loop_result, compiled_spec_exists, cfg_exists, spec_dir_has_tla, 
          spec_dir_has_cfg, spec_dir_has_traces, phase, step_count

(* define statement *)
PassImpliesWrite ==
  phase = "done" /\ loop_result = "pass" => spec_dir_has_tla = TRUE

FailImpliesNoWrite ==
  phase = "done" /\ loop_result = "fail" => spec_dir_has_tla = FALSE

CfgConditional ==
  spec_dir_has_cfg = TRUE => cfg_exists = TRUE

TracesOnPass ==
  phase = "done" /\ loop_result = "pass" => spec_dir_has_traces = TRUE

BoundedExecution == step_count <= MaxSteps


vars == << pc, loop_result, compiled_spec_exists, cfg_exists, 
           spec_dir_has_tla, spec_dir_has_cfg, spec_dir_has_traces, phase, 
           step_count >>

ProcSet == {"runner"}

Init == (* Global variables *)
        /\ loop_result = "idle"
        /\ compiled_spec_exists = TRUE
        /\ cfg_exists \in {TRUE, FALSE}
        /\ spec_dir_has_tla = FALSE
        /\ spec_dir_has_cfg = FALSE
        /\ spec_dir_has_traces = FALSE
        /\ phase = "start"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "Start"]

Start == /\ pc["runner"] = "Start"
         /\ phase' = "run_loop"
         /\ loop_result' = "running"
         /\ step_count' = step_count + 1
         /\ pc' = [pc EXCEPT !["runner"] = "RunLoop"]
         /\ UNCHANGED << compiled_spec_exists, cfg_exists, spec_dir_has_tla, 
                         spec_dir_has_cfg, spec_dir_has_traces >>

RunLoop == /\ pc["runner"] = "RunLoop"
           /\ \/ /\ loop_result' = "pass"
              \/ /\ loop_result' = "fail"
           /\ phase' = "check_result"
           /\ step_count' = step_count + 1
           /\ pc' = [pc EXCEPT !["runner"] = "CheckResult"]
           /\ UNCHANGED << compiled_spec_exists, cfg_exists, spec_dir_has_tla, 
                           spec_dir_has_cfg, spec_dir_has_traces >>

CheckResult == /\ pc["runner"] = "CheckResult"
               /\ IF loop_result = "pass"
                     THEN /\ phase' = "write_files"
                          /\ pc' = [pc EXCEPT !["runner"] = "AfterCheck"]
                     ELSE /\ phase' = "done"
                          /\ pc' = [pc EXCEPT !["runner"] = "Finish"]
               /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                               spec_dir_has_tla, spec_dir_has_cfg, 
                               spec_dir_has_traces, step_count >>

AfterCheck == /\ pc["runner"] = "AfterCheck"
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["runner"] = "WriteTla"]
              /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                              spec_dir_has_tla, spec_dir_has_cfg, 
                              spec_dir_has_traces, phase >>

WriteTla == /\ pc["runner"] = "WriteTla"
            /\ spec_dir_has_tla' = TRUE
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["runner"] = "WriteCfg"]
            /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                            spec_dir_has_cfg, spec_dir_has_traces, phase >>

WriteCfg == /\ pc["runner"] = "WriteCfg"
            /\ IF cfg_exists
                  THEN /\ spec_dir_has_cfg' = TRUE
                  ELSE /\ TRUE
                       /\ UNCHANGED spec_dir_has_cfg
            /\ pc' = [pc EXCEPT !["runner"] = "WriteTraces"]
            /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                            spec_dir_has_tla, spec_dir_has_traces, phase, 
                            step_count >>

WriteTraces == /\ pc["runner"] = "WriteTraces"
               /\ spec_dir_has_traces' = TRUE
               /\ phase' = "done"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["runner"] = "Finish"]
               /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                               spec_dir_has_tla, spec_dir_has_cfg >>

Finish == /\ pc["runner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["runner"] = "Done"]
          /\ UNCHANGED << loop_result, compiled_spec_exists, cfg_exists, 
                          spec_dir_has_tla, spec_dir_has_cfg, 
                          spec_dir_has_traces, phase, step_count >>

runner == Start \/ RunLoop \/ CheckResult \/ AfterCheck \/ WriteTla
             \/ WriteCfg \/ WriteTraces \/ Finish

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
