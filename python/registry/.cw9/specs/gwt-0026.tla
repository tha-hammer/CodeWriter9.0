---- MODULE GWT0026PromptContext ----

EXTENDS Integers, TLC

CONSTANTS
    MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps > 0

(* --algorithm GWT0026PromptContext

variables
    current_state    = "Idle",
    crawl_db_present \in BOOLEAN,
    dag_nodes        = FALSE,
    fn_records       = FALSE,
    combined_context = FALSE,
    prompt_built     = FALSE,
    error_occurred   = FALSE,
    step_count       = 0;

define

    StateSet ==
        { "Idle", "QueryingDag", "FetchingRecords",
          "FormattingCtx", "BuildingPrompt", "PromptReady" }

    ValidState ==
        current_state \in StateSet

    BoundedExecution ==
        step_count <= MaxSteps

    PromptBuiltImpliesContextFormatted ==
        prompt_built => combined_context

    ContextFormattedImpliesDAGQueried ==
        combined_context => dag_nodes

    NoCrawlDbMeansNoFnRecords ==
        (~crawl_db_present) => (~fn_records)

    NoCrawlDbNoError ==
        (~crawl_db_present) => (~error_occurred)

    PromptReadyIsTerminal ==
        (current_state = "PromptReady") =>
            ( /\ prompt_built
              /\ combined_context
              /\ dag_nodes
              /\ ~error_occurred )

end define;

fair process Worker = "loop_worker"
begin

    CallQueryContext:
        current_state := "QueryingDag";
        step_count    := step_count + 1;

    RunDagQueryRelevant:
        dag_nodes  := TRUE;
        step_count := step_count + 1;
        if crawl_db_present then
            current_state := "FetchingRecords";
        else
            current_state := "FormattingCtx";
        end if;

    MaybeFetchRecords:
        if current_state = "FetchingRecords" then
            fn_records    := TRUE;
            current_state := "FormattingCtx";
            step_count    := step_count + 1;
        end if;

    RunFormatPromptContext:
        assert dag_nodes = TRUE;
        combined_context := TRUE;
        current_state    := "BuildingPrompt";
        step_count       := step_count + 1;

    RunBuildPrompt:
        assert combined_context = TRUE;
        prompt_built  := TRUE;
        current_state := "PromptReady";
        step_count    := step_count + 1;

    Finish:
        assert current_state    = "PromptReady";
        assert prompt_built     = TRUE;
        assert combined_context = TRUE;
        assert dag_nodes        = TRUE;
        assert error_occurred   = FALSE;
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8a207a1b" /\ chksum(tla) = "3feb6f38")
VARIABLES pc, current_state, crawl_db_present, dag_nodes, fn_records, 
          combined_context, prompt_built, error_occurred, step_count

(* define statement *)
StateSet ==
    { "Idle", "QueryingDag", "FetchingRecords",
      "FormattingCtx", "BuildingPrompt", "PromptReady" }

ValidState ==
    current_state \in StateSet

BoundedExecution ==
    step_count <= MaxSteps

PromptBuiltImpliesContextFormatted ==
    prompt_built => combined_context

ContextFormattedImpliesDAGQueried ==
    combined_context => dag_nodes

NoCrawlDbMeansNoFnRecords ==
    (~crawl_db_present) => (~fn_records)

NoCrawlDbNoError ==
    (~crawl_db_present) => (~error_occurred)

PromptReadyIsTerminal ==
    (current_state = "PromptReady") =>
        ( /\ prompt_built
          /\ combined_context
          /\ dag_nodes
          /\ ~error_occurred )


vars == << pc, current_state, crawl_db_present, dag_nodes, fn_records, 
           combined_context, prompt_built, error_occurred, step_count >>

ProcSet == {"loop_worker"}

Init == (* Global variables *)
        /\ current_state = "Idle"
        /\ crawl_db_present \in BOOLEAN
        /\ dag_nodes = FALSE
        /\ fn_records = FALSE
        /\ combined_context = FALSE
        /\ prompt_built = FALSE
        /\ error_occurred = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "CallQueryContext"]

CallQueryContext == /\ pc["loop_worker"] = "CallQueryContext"
                    /\ current_state' = "QueryingDag"
                    /\ step_count' = step_count + 1
                    /\ pc' = [pc EXCEPT !["loop_worker"] = "RunDagQueryRelevant"]
                    /\ UNCHANGED << crawl_db_present, dag_nodes, fn_records, 
                                    combined_context, prompt_built, 
                                    error_occurred >>

RunDagQueryRelevant == /\ pc["loop_worker"] = "RunDagQueryRelevant"
                       /\ dag_nodes' = TRUE
                       /\ step_count' = step_count + 1
                       /\ IF crawl_db_present
                             THEN /\ current_state' = "FetchingRecords"
                             ELSE /\ current_state' = "FormattingCtx"
                       /\ pc' = [pc EXCEPT !["loop_worker"] = "MaybeFetchRecords"]
                       /\ UNCHANGED << crawl_db_present, fn_records, 
                                       combined_context, prompt_built, 
                                       error_occurred >>

MaybeFetchRecords == /\ pc["loop_worker"] = "MaybeFetchRecords"
                     /\ IF current_state = "FetchingRecords"
                           THEN /\ fn_records' = TRUE
                                /\ current_state' = "FormattingCtx"
                                /\ step_count' = step_count + 1
                           ELSE /\ TRUE
                                /\ UNCHANGED << current_state, fn_records, 
                                                step_count >>
                     /\ pc' = [pc EXCEPT !["loop_worker"] = "RunFormatPromptContext"]
                     /\ UNCHANGED << crawl_db_present, dag_nodes, 
                                     combined_context, prompt_built, 
                                     error_occurred >>

RunFormatPromptContext == /\ pc["loop_worker"] = "RunFormatPromptContext"
                          /\ Assert(dag_nodes = TRUE, 
                                    "Failure of assertion at line 79, column 9.")
                          /\ combined_context' = TRUE
                          /\ current_state' = "BuildingPrompt"
                          /\ step_count' = step_count + 1
                          /\ pc' = [pc EXCEPT !["loop_worker"] = "RunBuildPrompt"]
                          /\ UNCHANGED << crawl_db_present, dag_nodes, 
                                          fn_records, prompt_built, 
                                          error_occurred >>

RunBuildPrompt == /\ pc["loop_worker"] = "RunBuildPrompt"
                  /\ Assert(combined_context = TRUE, 
                            "Failure of assertion at line 85, column 9.")
                  /\ prompt_built' = TRUE
                  /\ current_state' = "PromptReady"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["loop_worker"] = "Finish"]
                  /\ UNCHANGED << crawl_db_present, dag_nodes, fn_records, 
                                  combined_context, error_occurred >>

Finish == /\ pc["loop_worker"] = "Finish"
          /\ Assert(current_state    = "PromptReady", 
                    "Failure of assertion at line 91, column 9.")
          /\ Assert(prompt_built     = TRUE, 
                    "Failure of assertion at line 92, column 9.")
          /\ Assert(combined_context = TRUE, 
                    "Failure of assertion at line 93, column 9.")
          /\ Assert(dag_nodes        = TRUE, 
                    "Failure of assertion at line 94, column 9.")
          /\ Assert(error_occurred   = FALSE, 
                    "Failure of assertion at line 95, column 9.")
          /\ TRUE
          /\ pc' = [pc EXCEPT !["loop_worker"] = "Done"]
          /\ UNCHANGED << current_state, crawl_db_present, dag_nodes, 
                          fn_records, combined_context, prompt_built, 
                          error_occurred, step_count >>

Worker == CallQueryContext \/ RunDagQueryRelevant \/ MaybeFetchRecords
             \/ RunFormatPromptContext \/ RunBuildPrompt \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
