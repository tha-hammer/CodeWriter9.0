---- MODULE CrawlConcurrencyPipeline ----

EXTENDS Integers, TLC

CONSTANTS
    MIN_CONCURRENCY,
    MAX_CONCURRENCY,
    DEFAULT_CONCURRENCY,
    MaxSteps

ASSUME DEFAULT_CONCURRENCY = 10
ASSUME MIN_CONCURRENCY >= 1
ASSUME MIN_CONCURRENCY <= DEFAULT_CONCURRENCY
ASSUME MAX_CONCURRENCY >= DEFAULT_CONCURRENCY
ASSUME MaxSteps >= 8

(*
 * Behavior: gwt-0022
 * Models the --concurrency flag flowing from argparse through
 * cmd_crawl() -> CrawlOrchestrator.__init__() -> _sweep_remaining_async()
 *
 * Suggested TLC model constants:
 *   MIN_CONCURRENCY     <- 1
 *   MAX_CONCURRENCY     <- 100
 *   DEFAULT_CONCURRENCY <- 10
 *   MaxSteps            <- 10
 *
 * raw_concurrency covers: below-min (0), at-min (1), mid-range (5),
 * at-default (10), above-max (101).
 *)

(* --algorithm CrawlConcurrencyPipeline

variables
    user_provided   \in {TRUE, FALSE},
    raw_concurrency \in {0, 1, 5, 10, 101},
    stage           = "Idle",
    parsed_value    = 0,
    validation_ok   = FALSE,
    cmd_crawl_value = 0,
    orchestrator_value = 0,
    sweep_value     = 0,
    pipeline_error  = FALSE,
    step_count      = 0;

define

    ValidStages ==
        {"Idle", "Parsing", "Validating", "CmdCrawl",
         "OrchestratorInit", "SweepAsync", "Complete", "Error"}

    TypeInvariant ==
        /\ stage \in ValidStages
        /\ step_count >= 0

    BoundedExecution == step_count <= MaxSteps

    \* When no flag supplied, argparse fills in the default of 10
    DefaultApplied ==
        (~user_provided /\ stage \notin {"Idle", "Parsing"}) =>
            parsed_value = DEFAULT_CONCURRENCY

    \* Validation only passes for integers in the accepted range
    ValidationCorrect ==
        validation_ok =>
            (parsed_value >= MIN_CONCURRENCY /\ parsed_value <= MAX_CONCURRENCY)

    \* cmd_crawl() must forward the exact validated value to the orchestrator
    ValuePreservedToCmdCrawl ==
        stage \in {"OrchestratorInit", "SweepAsync", "Complete"} =>
            cmd_crawl_value = parsed_value

    \* CrawlOrchestrator.__init__() must forward the value to _sweep_remaining_async()
    OrchestratorPreservesValue ==
        stage \in {"SweepAsync", "Complete"} =>
            orchestrator_value = cmd_crawl_value

    \* The sweep call receives the same integer that was parsed
    SweepReceivesCorrectValue ==
        stage = "Complete" => sweep_value = parsed_value

    \* Valid user-supplied input must never reach the Error stage
    NoErrorOnValidUserInput ==
        (user_provided
            /\ raw_concurrency >= MIN_CONCURRENCY
            /\ raw_concurrency <= MAX_CONCURRENCY) =>
            stage /= "Error"

    \* Default value (10) is always valid; default path must never error
    NoErrorOnDefault ==
        ~user_provided => stage /= "Error"

end define;

fair process pipeline = "main"
begin
    StartParsing:
        stage      := "Parsing";
        step_count := step_count + 1;

    ParseArg:
        \* argparse assigns user value or falls back to default=10
        if user_provided then
            parsed_value := raw_concurrency;
        else
            parsed_value := DEFAULT_CONCURRENCY;
        end if;
        stage      := "Validating";
        step_count := step_count + 1;

    ValidateArg:
        \* Validation: must be a positive integer within the accepted range
        if parsed_value >= MIN_CONCURRENCY /\ parsed_value <= MAX_CONCURRENCY then
            validation_ok := TRUE;
        else
            validation_ok  := FALSE;
            pipeline_error := TRUE;
        end if;

    RouteAfterValidation:
        step_count := step_count + 1;
        if pipeline_error then
            stage := "Error";
            goto Terminate;
        else
            stage := "CmdCrawl";
        end if;

    InvokeCmdCrawl:
        \* cmd_crawl() receives the validated concurrency and passes it forward
        cmd_crawl_value := parsed_value;
        stage           := "OrchestratorInit";
        step_count      := step_count + 1;

    InitOrchestrator:
        \* CrawlOrchestrator.__init__(concurrency=cmd_crawl_value)
        orchestrator_value := cmd_crawl_value;
        stage              := "SweepAsync";
        step_count         := step_count + 1;

    ForwardToSweep:
        \* _sweep_remaining_async(concurrency=orchestrator_value)
        sweep_value := orchestrator_value;
        stage       := "Complete";
        step_count  := step_count + 1;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "6fa0233b" /\ chksum(tla) = "d7037514")
VARIABLES pc, user_provided, raw_concurrency, stage, parsed_value, 
          validation_ok, cmd_crawl_value, orchestrator_value, sweep_value, 
          pipeline_error, step_count

(* define statement *)
ValidStages ==
    {"Idle", "Parsing", "Validating", "CmdCrawl",
     "OrchestratorInit", "SweepAsync", "Complete", "Error"}

TypeInvariant ==
    /\ stage \in ValidStages
    /\ step_count >= 0

BoundedExecution == step_count <= MaxSteps


DefaultApplied ==
    (~user_provided /\ stage \notin {"Idle", "Parsing"}) =>
        parsed_value = DEFAULT_CONCURRENCY


ValidationCorrect ==
    validation_ok =>
        (parsed_value >= MIN_CONCURRENCY /\ parsed_value <= MAX_CONCURRENCY)


ValuePreservedToCmdCrawl ==
    stage \in {"OrchestratorInit", "SweepAsync", "Complete"} =>
        cmd_crawl_value = parsed_value


OrchestratorPreservesValue ==
    stage \in {"SweepAsync", "Complete"} =>
        orchestrator_value = cmd_crawl_value


SweepReceivesCorrectValue ==
    stage = "Complete" => sweep_value = parsed_value


NoErrorOnValidUserInput ==
    (user_provided
        /\ raw_concurrency >= MIN_CONCURRENCY
        /\ raw_concurrency <= MAX_CONCURRENCY) =>
        stage /= "Error"


NoErrorOnDefault ==
    ~user_provided => stage /= "Error"


vars == << pc, user_provided, raw_concurrency, stage, parsed_value, 
           validation_ok, cmd_crawl_value, orchestrator_value, sweep_value, 
           pipeline_error, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ user_provided \in {TRUE, FALSE}
        /\ raw_concurrency \in {0, 1, 5, 10, 101}
        /\ stage = "Idle"
        /\ parsed_value = 0
        /\ validation_ok = FALSE
        /\ cmd_crawl_value = 0
        /\ orchestrator_value = 0
        /\ sweep_value = 0
        /\ pipeline_error = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "StartParsing"]

StartParsing == /\ pc["main"] = "StartParsing"
                /\ stage' = "Parsing"
                /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["main"] = "ParseArg"]
                /\ UNCHANGED << user_provided, raw_concurrency, parsed_value, 
                                validation_ok, cmd_crawl_value, 
                                orchestrator_value, sweep_value, 
                                pipeline_error >>

ParseArg == /\ pc["main"] = "ParseArg"
            /\ IF user_provided
                  THEN /\ parsed_value' = raw_concurrency
                  ELSE /\ parsed_value' = DEFAULT_CONCURRENCY
            /\ stage' = "Validating"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["main"] = "ValidateArg"]
            /\ UNCHANGED << user_provided, raw_concurrency, validation_ok, 
                            cmd_crawl_value, orchestrator_value, sweep_value, 
                            pipeline_error >>

ValidateArg == /\ pc["main"] = "ValidateArg"
               /\ IF parsed_value >= MIN_CONCURRENCY /\ parsed_value <= MAX_CONCURRENCY
                     THEN /\ validation_ok' = TRUE
                          /\ UNCHANGED pipeline_error
                     ELSE /\ validation_ok' = FALSE
                          /\ pipeline_error' = TRUE
               /\ pc' = [pc EXCEPT !["main"] = "RouteAfterValidation"]
               /\ UNCHANGED << user_provided, raw_concurrency, stage, 
                               parsed_value, cmd_crawl_value, 
                               orchestrator_value, sweep_value, step_count >>

RouteAfterValidation == /\ pc["main"] = "RouteAfterValidation"
                        /\ step_count' = step_count + 1
                        /\ IF pipeline_error
                              THEN /\ stage' = "Error"
                                   /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                              ELSE /\ stage' = "CmdCrawl"
                                   /\ pc' = [pc EXCEPT !["main"] = "InvokeCmdCrawl"]
                        /\ UNCHANGED << user_provided, raw_concurrency, 
                                        parsed_value, validation_ok, 
                                        cmd_crawl_value, orchestrator_value, 
                                        sweep_value, pipeline_error >>

InvokeCmdCrawl == /\ pc["main"] = "InvokeCmdCrawl"
                  /\ cmd_crawl_value' = parsed_value
                  /\ stage' = "OrchestratorInit"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["main"] = "InitOrchestrator"]
                  /\ UNCHANGED << user_provided, raw_concurrency, parsed_value, 
                                  validation_ok, orchestrator_value, 
                                  sweep_value, pipeline_error >>

InitOrchestrator == /\ pc["main"] = "InitOrchestrator"
                    /\ orchestrator_value' = cmd_crawl_value
                    /\ stage' = "SweepAsync"
                    /\ step_count' = step_count + 1
                    /\ pc' = [pc EXCEPT !["main"] = "ForwardToSweep"]
                    /\ UNCHANGED << user_provided, raw_concurrency, 
                                    parsed_value, validation_ok, 
                                    cmd_crawl_value, sweep_value, 
                                    pipeline_error >>

ForwardToSweep == /\ pc["main"] = "ForwardToSweep"
                  /\ sweep_value' = orchestrator_value
                  /\ stage' = "Complete"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                  /\ UNCHANGED << user_provided, raw_concurrency, parsed_value, 
                                  validation_ok, cmd_crawl_value, 
                                  orchestrator_value, pipeline_error >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << user_provided, raw_concurrency, stage, 
                             parsed_value, validation_ok, cmd_crawl_value, 
                             orchestrator_value, sweep_value, pipeline_error, 
                             step_count >>

pipeline == StartParsing \/ ParseArg \/ ValidateArg \/ RouteAfterValidation
               \/ InvokeCmdCrawl \/ InitOrchestrator \/ ForwardToSweep
               \/ Terminate

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
