---- MODULE GwtAuthor ----
EXTENDS Integers, TLC

CONSTANTS
    MaxTime

ASSUME /\ MaxTime \in Nat
       /\ MaxTime >= 10

(* --algorithm GwtAuthor

variables
    phase = "Idle",
    research_notes_ready = TRUE,
    crawl_db_ready = TRUE,
    dag_json_ready = TRUE,
    llm_call_count = 0,
    prompt_built = FALSE,
    llm_response = "none",
    parse_ok = FALSE,
    depends_on_valid = FALSE,
    validation_ok = FALSE,
    gwt_json = "none",
    returned_to_caller = FALSE,
    elapsed = 0,
    job_ok = TRUE;

define

    Phases == { "Idle", "BuildingPrompt", "CallingLLM",
                "ParsingResponse", "ValidatingDependsOn",
                "ReturningResult", "Completed", "Failed" }

    ValidPhase == phase \in Phases

    LLMNeverExceedsOne == llm_call_count <= 1

    ExactlyOneLLMAtCompletion ==
        phase = "Completed" => llm_call_count = 1

    PromptBuiltBeforeLLM ==
        llm_call_count > 0 => prompt_built

    ParseBeforeValidation ==
        validation_ok => parse_ok

    ValidationBeforeReturn ==
        returned_to_caller => validation_ok

    GwtJsonSetOnSuccess ==
        phase = "Completed" => gwt_json /= "none"

    ReturnedOnSuccess ==
        phase = "Completed" => returned_to_caller = TRUE

    TimeBound ==
        phase = "Completed" => elapsed < 60

    BoundedElapsed ==
        elapsed <= MaxTime

    PhaseOrderRespected ==
        /\ (phase = "CallingLLM"         => prompt_built)
        /\ (phase = "ParsingResponse"    => llm_call_count = 1)
        /\ (phase = "ValidatingDependsOn" => parse_ok)
        /\ (phase = "ReturningResult"    => validation_ok)

end define;

fair process GwtAuthorJob = "gwt_author"
begin

    Dequeue:
        await research_notes_ready /\ crawl_db_ready /\ dag_json_ready;
        phase := "BuildingPrompt";
        elapsed := elapsed + 1;

    BuildPrompt:
        prompt_built := TRUE;
        phase := "CallingLLM";
        elapsed := elapsed + 1;

    CallLLM:
        llm_call_count := llm_call_count + 1;
        llm_response := "llm_raw_response";
        phase := "ParsingResponse";
        elapsed := elapsed + 1;

    ParseResponse:
        parse_ok := TRUE;
        elapsed := elapsed + 1;
        either
            depends_on_valid := TRUE;
        or
            depends_on_valid := FALSE;
        end either;
        phase := "ValidatingDependsOn";

    ValidateDependsOn:
        elapsed := elapsed + 1;
        if depends_on_valid then
            validation_ok := TRUE;
            phase := "ReturningResult";
        else
            job_ok := FALSE;
            phase := "Failed";
        end if;

    AfterValidate:
        if phase = "Failed" then
            goto Terminate;
        end if;

    ReturnResult:
        elapsed := elapsed + 1;
        if elapsed < 60 then
            gwt_json := "gwt_output";
            returned_to_caller := TRUE;
            phase := "Completed";
        else
            job_ok := FALSE;
            phase := "Failed";
        end if;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "1801f610" /\ chksum(tla) = "967c9a48")
VARIABLES pc, phase, research_notes_ready, crawl_db_ready, dag_json_ready, 
          llm_call_count, prompt_built, llm_response, parse_ok, 
          depends_on_valid, validation_ok, gwt_json, returned_to_caller, 
          elapsed, job_ok

(* define statement *)
Phases == { "Idle", "BuildingPrompt", "CallingLLM",
            "ParsingResponse", "ValidatingDependsOn",
            "ReturningResult", "Completed", "Failed" }

ValidPhase == phase \in Phases

LLMNeverExceedsOne == llm_call_count <= 1

ExactlyOneLLMAtCompletion ==
    phase = "Completed" => llm_call_count = 1

PromptBuiltBeforeLLM ==
    llm_call_count > 0 => prompt_built

ParseBeforeValidation ==
    validation_ok => parse_ok

ValidationBeforeReturn ==
    returned_to_caller => validation_ok

GwtJsonSetOnSuccess ==
    phase = "Completed" => gwt_json /= "none"

ReturnedOnSuccess ==
    phase = "Completed" => returned_to_caller = TRUE

TimeBound ==
    phase = "Completed" => elapsed < 60

BoundedElapsed ==
    elapsed <= MaxTime

PhaseOrderRespected ==
    /\ (phase = "CallingLLM"         => prompt_built)
    /\ (phase = "ParsingResponse"    => llm_call_count = 1)
    /\ (phase = "ValidatingDependsOn" => parse_ok)
    /\ (phase = "ReturningResult"    => validation_ok)


vars == << pc, phase, research_notes_ready, crawl_db_ready, dag_json_ready, 
           llm_call_count, prompt_built, llm_response, parse_ok, 
           depends_on_valid, validation_ok, gwt_json, returned_to_caller, 
           elapsed, job_ok >>

ProcSet == {"gwt_author"}

Init == (* Global variables *)
        /\ phase = "Idle"
        /\ research_notes_ready = TRUE
        /\ crawl_db_ready = TRUE
        /\ dag_json_ready = TRUE
        /\ llm_call_count = 0
        /\ prompt_built = FALSE
        /\ llm_response = "none"
        /\ parse_ok = FALSE
        /\ depends_on_valid = FALSE
        /\ validation_ok = FALSE
        /\ gwt_json = "none"
        /\ returned_to_caller = FALSE
        /\ elapsed = 0
        /\ job_ok = TRUE
        /\ pc = [self \in ProcSet |-> "Dequeue"]

Dequeue == /\ pc["gwt_author"] = "Dequeue"
           /\ research_notes_ready /\ crawl_db_ready /\ dag_json_ready
           /\ phase' = "BuildingPrompt"
           /\ elapsed' = elapsed + 1
           /\ pc' = [pc EXCEPT !["gwt_author"] = "BuildPrompt"]
           /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                           dag_json_ready, llm_call_count, prompt_built, 
                           llm_response, parse_ok, depends_on_valid, 
                           validation_ok, gwt_json, returned_to_caller, job_ok >>

BuildPrompt == /\ pc["gwt_author"] = "BuildPrompt"
               /\ prompt_built' = TRUE
               /\ phase' = "CallingLLM"
               /\ elapsed' = elapsed + 1
               /\ pc' = [pc EXCEPT !["gwt_author"] = "CallLLM"]
               /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                               dag_json_ready, llm_call_count, llm_response, 
                               parse_ok, depends_on_valid, validation_ok, 
                               gwt_json, returned_to_caller, job_ok >>

CallLLM == /\ pc["gwt_author"] = "CallLLM"
           /\ llm_call_count' = llm_call_count + 1
           /\ llm_response' = "llm_raw_response"
           /\ phase' = "ParsingResponse"
           /\ elapsed' = elapsed + 1
           /\ pc' = [pc EXCEPT !["gwt_author"] = "ParseResponse"]
           /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                           dag_json_ready, prompt_built, parse_ok, 
                           depends_on_valid, validation_ok, gwt_json, 
                           returned_to_caller, job_ok >>

ParseResponse == /\ pc["gwt_author"] = "ParseResponse"
                 /\ parse_ok' = TRUE
                 /\ elapsed' = elapsed + 1
                 /\ \/ /\ depends_on_valid' = TRUE
                    \/ /\ depends_on_valid' = FALSE
                 /\ phase' = "ValidatingDependsOn"
                 /\ pc' = [pc EXCEPT !["gwt_author"] = "ValidateDependsOn"]
                 /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                                 dag_json_ready, llm_call_count, prompt_built, 
                                 llm_response, validation_ok, gwt_json, 
                                 returned_to_caller, job_ok >>

ValidateDependsOn == /\ pc["gwt_author"] = "ValidateDependsOn"
                     /\ elapsed' = elapsed + 1
                     /\ IF depends_on_valid
                           THEN /\ validation_ok' = TRUE
                                /\ phase' = "ReturningResult"
                                /\ UNCHANGED job_ok
                           ELSE /\ job_ok' = FALSE
                                /\ phase' = "Failed"
                                /\ UNCHANGED validation_ok
                     /\ pc' = [pc EXCEPT !["gwt_author"] = "AfterValidate"]
                     /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                                     dag_json_ready, llm_call_count, 
                                     prompt_built, llm_response, parse_ok, 
                                     depends_on_valid, gwt_json, 
                                     returned_to_caller >>

AfterValidate == /\ pc["gwt_author"] = "AfterValidate"
                 /\ IF phase = "Failed"
                       THEN /\ pc' = [pc EXCEPT !["gwt_author"] = "Terminate"]
                       ELSE /\ pc' = [pc EXCEPT !["gwt_author"] = "ReturnResult"]
                 /\ UNCHANGED << phase, research_notes_ready, crawl_db_ready, 
                                 dag_json_ready, llm_call_count, prompt_built, 
                                 llm_response, parse_ok, depends_on_valid, 
                                 validation_ok, gwt_json, returned_to_caller, 
                                 elapsed, job_ok >>

ReturnResult == /\ pc["gwt_author"] = "ReturnResult"
                /\ elapsed' = elapsed + 1
                /\ IF elapsed' < 60
                      THEN /\ gwt_json' = "gwt_output"
                           /\ returned_to_caller' = TRUE
                           /\ phase' = "Completed"
                           /\ UNCHANGED job_ok
                      ELSE /\ job_ok' = FALSE
                           /\ phase' = "Failed"
                           /\ UNCHANGED << gwt_json, returned_to_caller >>
                /\ pc' = [pc EXCEPT !["gwt_author"] = "Terminate"]
                /\ UNCHANGED << research_notes_ready, crawl_db_ready, 
                                dag_json_ready, llm_call_count, prompt_built, 
                                llm_response, parse_ok, depends_on_valid, 
                                validation_ok >>

Terminate == /\ pc["gwt_author"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["gwt_author"] = "Done"]
             /\ UNCHANGED << phase, research_notes_ready, crawl_db_ready, 
                             dag_json_ready, llm_call_count, prompt_built, 
                             llm_response, parse_ok, depends_on_valid, 
                             validation_ok, gwt_json, returned_to_caller, 
                             elapsed, job_ok >>

GwtAuthorJob == Dequeue \/ BuildPrompt \/ CallLLM \/ ParseResponse
                   \/ ValidateDependsOn \/ AfterValidate \/ ReturnResult
                   \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == GwtAuthorJob
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(GwtAuthorJob)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec =>
    []( ValidPhase
      /\ LLMNeverExceedsOne
      /\ ExactlyOneLLMAtCompletion
      /\ PromptBuiltBeforeLLM
      /\ ParseBeforeValidation
      /\ ValidationBeforeReturn
      /\ GwtJsonSetOnSuccess
      /\ ReturnedOnSuccess
      /\ TimeBound
      /\ BoundedElapsed
      /\ PhaseOrderRespected )

====
