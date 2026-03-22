---- MODULE PipelineStepOrdering ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS GwtIds, MaxSteps

ASSUME GwtIds # {}

(* --algorithm PipelineStepOrdering

variables
    phase            = "setup",
    setup_result     = "pending",
    loop_done        = {},
    loop_passed      = {},
    bridge_attempted = {},
    bridge_done      = {},
    exit_code        = 0,
    step_count       = 0,
    current_gwt      = CHOOSE g \in GwtIds : TRUE;

define

    SetupBeforeLoop ==
        phase = "loop" => setup_result = "pass"

    LoopBeforeBridge ==
        phase = "bridge" => loop_done = GwtIds

    BridgeOnlyVerified ==
        \A g \in bridge_done : g \in loop_passed

    EarlyExitOnSetupFail ==
        setup_result = "fail" => phase = "done"

    AllGwtsAttempted ==
        (phase # "loop" /\ setup_result = "pass") => loop_done = GwtIds

    ExitCodeCorrect ==
        (phase = "done" /\ setup_result = "pass") =>
            (exit_code = 0 <=> loop_passed = GwtIds /\ bridge_done = loop_passed)

    BoundedExecution ==
        step_count <= MaxSteps

end define;

fair process pipeline = "main"
begin

    SetupInit:
        either
            step_count := step_count + 1;
        or
            setup_result := "fail";
            phase        := "done";
            exit_code    := 1;
            step_count   := step_count + 1;
        end either;

    AfterInit:
        if phase = "done" then
            goto PipelineDone;
        end if;

    SetupExtract:
        either
            step_count := step_count + 1;
        or
            setup_result := "fail";
            phase        := "done";
            exit_code    := 1;
            step_count   := step_count + 1;
        end either;

    AfterExtract:
        if phase = "done" then
            goto PipelineDone;
        else
            setup_result := "pass";
            phase        := "loop";
        end if;

    LoopPhase:
        while loop_done # GwtIds do
            current_gwt := CHOOSE g \in GwtIds \ loop_done : TRUE;
        LoopRun:
            either
                loop_done   := loop_done \cup {current_gwt};
                loop_passed := loop_passed \cup {current_gwt};
            or
                loop_done := loop_done \cup {current_gwt};
            end either;
        LoopCount:
            step_count := step_count + 1;
        end while;

    AfterLoop:
        phase := "bridge";

    BridgePhase:
        while bridge_attempted # loop_passed do
            current_gwt := CHOOSE g \in loop_passed \ bridge_attempted : TRUE;
        BridgeRun:
            either
                bridge_attempted := bridge_attempted \cup {current_gwt};
                bridge_done      := bridge_done \cup {current_gwt};
            or
                bridge_attempted := bridge_attempted \cup {current_gwt};
            end either;
        BridgeCount:
            step_count := step_count + 1;
        end while;

    AfterBridge:
        if loop_passed = GwtIds /\ bridge_done = loop_passed then
            exit_code := 0;
        else
            exit_code := 1;
        end if;

    SetPhaseDone:
        phase := "done";

    PipelineDone:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e0c0bcf" /\ chksum(tla) = "ed39bbe5")
VARIABLES pc, phase, setup_result, loop_done, loop_passed, bridge_attempted, 
          bridge_done, exit_code, step_count, current_gwt

(* define statement *)
SetupBeforeLoop ==
    phase = "loop" => setup_result = "pass"

LoopBeforeBridge ==
    phase = "bridge" => loop_done = GwtIds

BridgeOnlyVerified ==
    \A g \in bridge_done : g \in loop_passed

EarlyExitOnSetupFail ==
    setup_result = "fail" => phase = "done"

AllGwtsAttempted ==
    (phase # "loop" /\ setup_result = "pass") => loop_done = GwtIds

ExitCodeCorrect ==
    (phase = "done" /\ setup_result = "pass") =>
        (exit_code = 0 <=> loop_passed = GwtIds /\ bridge_done = loop_passed)

BoundedExecution ==
    step_count <= MaxSteps


vars == << pc, phase, setup_result, loop_done, loop_passed, bridge_attempted, 
           bridge_done, exit_code, step_count, current_gwt >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ phase = "setup"
        /\ setup_result = "pending"
        /\ loop_done = {}
        /\ loop_passed = {}
        /\ bridge_attempted = {}
        /\ bridge_done = {}
        /\ exit_code = 0
        /\ step_count = 0
        /\ current_gwt = (CHOOSE g \in GwtIds : TRUE)
        /\ pc = [self \in ProcSet |-> "SetupInit"]

SetupInit == /\ pc["main"] = "SetupInit"
             /\ \/ /\ step_count' = step_count + 1
                   /\ UNCHANGED <<phase, setup_result, exit_code>>
                \/ /\ setup_result' = "fail"
                   /\ phase' = "done"
                   /\ exit_code' = 1
                   /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["main"] = "AfterInit"]
             /\ UNCHANGED << loop_done, loop_passed, bridge_attempted, 
                             bridge_done, current_gwt >>

AfterInit == /\ pc["main"] = "AfterInit"
             /\ IF phase = "done"
                   THEN /\ pc' = [pc EXCEPT !["main"] = "PipelineDone"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "SetupExtract"]
             /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                             bridge_attempted, bridge_done, exit_code, 
                             step_count, current_gwt >>

SetupExtract == /\ pc["main"] = "SetupExtract"
                /\ \/ /\ step_count' = step_count + 1
                      /\ UNCHANGED <<phase, setup_result, exit_code>>
                   \/ /\ setup_result' = "fail"
                      /\ phase' = "done"
                      /\ exit_code' = 1
                      /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["main"] = "AfterExtract"]
                /\ UNCHANGED << loop_done, loop_passed, bridge_attempted, 
                                bridge_done, current_gwt >>

AfterExtract == /\ pc["main"] = "AfterExtract"
                /\ IF phase = "done"
                      THEN /\ pc' = [pc EXCEPT !["main"] = "PipelineDone"]
                           /\ UNCHANGED << phase, setup_result >>
                      ELSE /\ setup_result' = "pass"
                           /\ phase' = "loop"
                           /\ pc' = [pc EXCEPT !["main"] = "LoopPhase"]
                /\ UNCHANGED << loop_done, loop_passed, bridge_attempted, 
                                bridge_done, exit_code, step_count, 
                                current_gwt >>

LoopPhase == /\ pc["main"] = "LoopPhase"
             /\ IF loop_done # GwtIds
                   THEN /\ current_gwt' = (CHOOSE g \in GwtIds \ loop_done : TRUE)
                        /\ pc' = [pc EXCEPT !["main"] = "LoopRun"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "AfterLoop"]
                        /\ UNCHANGED current_gwt
             /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                             bridge_attempted, bridge_done, exit_code, 
                             step_count >>

LoopRun == /\ pc["main"] = "LoopRun"
           /\ \/ /\ loop_done' = (loop_done \cup {current_gwt})
                 /\ loop_passed' = (loop_passed \cup {current_gwt})
              \/ /\ loop_done' = (loop_done \cup {current_gwt})
                 /\ UNCHANGED loop_passed
           /\ pc' = [pc EXCEPT !["main"] = "LoopCount"]
           /\ UNCHANGED << phase, setup_result, bridge_attempted, bridge_done, 
                           exit_code, step_count, current_gwt >>

LoopCount == /\ pc["main"] = "LoopCount"
             /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["main"] = "LoopPhase"]
             /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                             bridge_attempted, bridge_done, exit_code, 
                             current_gwt >>

AfterLoop == /\ pc["main"] = "AfterLoop"
             /\ phase' = "bridge"
             /\ pc' = [pc EXCEPT !["main"] = "BridgePhase"]
             /\ UNCHANGED << setup_result, loop_done, loop_passed, 
                             bridge_attempted, bridge_done, exit_code, 
                             step_count, current_gwt >>

BridgePhase == /\ pc["main"] = "BridgePhase"
               /\ IF bridge_attempted # loop_passed
                     THEN /\ current_gwt' = (CHOOSE g \in loop_passed \ bridge_attempted : TRUE)
                          /\ pc' = [pc EXCEPT !["main"] = "BridgeRun"]
                     ELSE /\ pc' = [pc EXCEPT !["main"] = "AfterBridge"]
                          /\ UNCHANGED current_gwt
               /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                               bridge_attempted, bridge_done, exit_code, 
                               step_count >>

BridgeRun == /\ pc["main"] = "BridgeRun"
             /\ \/ /\ bridge_attempted' = (bridge_attempted \cup {current_gwt})
                   /\ bridge_done' = (bridge_done \cup {current_gwt})
                \/ /\ bridge_attempted' = (bridge_attempted \cup {current_gwt})
                   /\ UNCHANGED bridge_done
             /\ pc' = [pc EXCEPT !["main"] = "BridgeCount"]
             /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                             exit_code, step_count, current_gwt >>

BridgeCount == /\ pc["main"] = "BridgeCount"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["main"] = "BridgePhase"]
               /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                               bridge_attempted, bridge_done, exit_code, 
                               current_gwt >>

AfterBridge == /\ pc["main"] = "AfterBridge"
               /\ IF loop_passed = GwtIds /\ bridge_done = loop_passed
                     THEN /\ exit_code' = 0
                     ELSE /\ exit_code' = 1
               /\ pc' = [pc EXCEPT !["main"] = "SetPhaseDone"]
               /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                               bridge_attempted, bridge_done, step_count, 
                               current_gwt >>

SetPhaseDone == /\ pc["main"] = "SetPhaseDone"
                /\ phase' = "done"
                /\ pc' = [pc EXCEPT !["main"] = "PipelineDone"]
                /\ UNCHANGED << setup_result, loop_done, loop_passed, 
                                bridge_attempted, bridge_done, exit_code, 
                                step_count, current_gwt >>

PipelineDone == /\ pc["main"] = "PipelineDone"
                /\ TRUE
                /\ pc' = [pc EXCEPT !["main"] = "Done"]
                /\ UNCHANGED << phase, setup_result, loop_done, loop_passed, 
                                bridge_attempted, bridge_done, exit_code, 
                                step_count, current_gwt >>

pipeline == SetupInit \/ AfterInit \/ SetupExtract \/ AfterExtract
               \/ LoopPhase \/ LoopRun \/ LoopCount \/ AfterLoop
               \/ BridgePhase \/ BridgeRun \/ BridgeCount \/ AfterBridge
               \/ SetPhaseDone \/ PipelineDone

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
