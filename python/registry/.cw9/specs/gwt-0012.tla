---- MODULE gwt0012_ExtractJobDAGRebuild ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    MAX_SCHEMA_FILES,
    MAX_REGISTERED_NODES,
    MAX_TIME_STEPS

ASSUME MAX_SCHEMA_FILES >= 1
ASSUME MAX_REGISTERED_NODES >= 0
ASSUME MAX_TIME_STEPS >= 5

(* --algorithm ExtractJobDAGRebuild

variables
    phase = "Idle",
    old_registered_nodes = {},
    new_dag_nodes = {},
    merged_dag_nodes = {},
    llm_called = FALSE,
    subprocess_called = FALSE,
    dag_uploaded = FALSE,
    time_elapsed = 0;

define

    ValidPhase ==
        phase \in {"Idle", "Loading", "Extracting", "Merging", "Uploading", "Complete", "Failed"}

    NoLLMCall == llm_called = FALSE

    NoSubprocessCall == subprocess_called = FALSE

    BoundedExecution == time_elapsed <= MAX_TIME_STEPS

    UploadBeforeComplete ==
        phase = "Complete" => dag_uploaded = TRUE

    RegisteredNodesMerged ==
        phase = "Complete" =>
            old_registered_nodes \subseteq merged_dag_nodes

    NewNodesCovered ==
        phase = "Complete" =>
            new_dag_nodes \subseteq merged_dag_nodes

    MergeIsUnion ==
        phase \in {"Uploading", "Complete"} =>
            merged_dag_nodes = new_dag_nodes \union old_registered_nodes

    CompletionCorrect ==
        phase = "Complete" =>
            /\ dag_uploaded = TRUE
            /\ llm_called = FALSE
            /\ subprocess_called = FALSE
            /\ time_elapsed <= MAX_TIME_STEPS
            /\ merged_dag_nodes = new_dag_nodes \union old_registered_nodes

end define;

fair process cmd_extract_proc = "cmd_extract"
begin
    Dequeue:
        \* Extract job dequeued; schema files and dag.json already in workspace
        phase := "Loading";
        time_elapsed := time_elapsed + 1;

    LoadOldDag:
        \* RegistryDag.load(): read existing dag.json, capture prior registered nodes
        with reg_count \in 0..MAX_REGISTERED_NODES do
            old_registered_nodes := 1..reg_count;
        end with;
        phase := "Extracting";
        time_elapsed := time_elapsed + 1;

    RunExtract:
        \* SchemaExtractor.extract(): pure Python rebuild from schema files
        \* Invariants NoLLMCall and NoSubprocessCall enforce no LLM / no subprocess
        with node_count \in 1..MAX_SCHEMA_FILES do
            new_dag_nodes := 1..node_count;
        end with;
        phase := "Merging";
        time_elapsed := time_elapsed + 1;

    MergeRegistered:
        \* merge_registered_nodes(): union of freshly extracted nodes and prior registered nodes
        merged_dag_nodes := new_dag_nodes \union old_registered_nodes;
        phase := "Uploading";
        time_elapsed := time_elapsed + 1;

    UploadDag:
        \* RegistryDag.save() then upload updated dag.json to object storage
        dag_uploaded := TRUE;
        phase := "Complete";
        time_elapsed := time_elapsed + 1;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8c70434b" /\ chksum(tla) = "f8a14ac9")
VARIABLES pc, phase, old_registered_nodes, new_dag_nodes, merged_dag_nodes, 
          llm_called, subprocess_called, dag_uploaded, time_elapsed

(* define statement *)
ValidPhase ==
    phase \in {"Idle", "Loading", "Extracting", "Merging", "Uploading", "Complete", "Failed"}

NoLLMCall == llm_called = FALSE

NoSubprocessCall == subprocess_called = FALSE

BoundedExecution == time_elapsed <= MAX_TIME_STEPS

UploadBeforeComplete ==
    phase = "Complete" => dag_uploaded = TRUE

RegisteredNodesMerged ==
    phase = "Complete" =>
        old_registered_nodes \subseteq merged_dag_nodes

NewNodesCovered ==
    phase = "Complete" =>
        new_dag_nodes \subseteq merged_dag_nodes

MergeIsUnion ==
    phase \in {"Uploading", "Complete"} =>
        merged_dag_nodes = new_dag_nodes \union old_registered_nodes

CompletionCorrect ==
    phase = "Complete" =>
        /\ dag_uploaded = TRUE
        /\ llm_called = FALSE
        /\ subprocess_called = FALSE
        /\ time_elapsed <= MAX_TIME_STEPS
        /\ merged_dag_nodes = new_dag_nodes \union old_registered_nodes


vars == << pc, phase, old_registered_nodes, new_dag_nodes, merged_dag_nodes, 
           llm_called, subprocess_called, dag_uploaded, time_elapsed >>

ProcSet == {"cmd_extract"}

Init == (* Global variables *)
        /\ phase = "Idle"
        /\ old_registered_nodes = {}
        /\ new_dag_nodes = {}
        /\ merged_dag_nodes = {}
        /\ llm_called = FALSE
        /\ subprocess_called = FALSE
        /\ dag_uploaded = FALSE
        /\ time_elapsed = 0
        /\ pc = [self \in ProcSet |-> "Dequeue"]

Dequeue == /\ pc["cmd_extract"] = "Dequeue"
           /\ phase' = "Loading"
           /\ time_elapsed' = time_elapsed + 1
           /\ pc' = [pc EXCEPT !["cmd_extract"] = "LoadOldDag"]
           /\ UNCHANGED << old_registered_nodes, new_dag_nodes, 
                           merged_dag_nodes, llm_called, subprocess_called, 
                           dag_uploaded >>

LoadOldDag == /\ pc["cmd_extract"] = "LoadOldDag"
              /\ \E reg_count \in 0..MAX_REGISTERED_NODES:
                   old_registered_nodes' = 1..reg_count
              /\ phase' = "Extracting"
              /\ time_elapsed' = time_elapsed + 1
              /\ pc' = [pc EXCEPT !["cmd_extract"] = "RunExtract"]
              /\ UNCHANGED << new_dag_nodes, merged_dag_nodes, llm_called, 
                              subprocess_called, dag_uploaded >>

RunExtract == /\ pc["cmd_extract"] = "RunExtract"
              /\ \E node_count \in 1..MAX_SCHEMA_FILES:
                   new_dag_nodes' = 1..node_count
              /\ phase' = "Merging"
              /\ time_elapsed' = time_elapsed + 1
              /\ pc' = [pc EXCEPT !["cmd_extract"] = "MergeRegistered"]
              /\ UNCHANGED << old_registered_nodes, merged_dag_nodes, 
                              llm_called, subprocess_called, dag_uploaded >>

MergeRegistered == /\ pc["cmd_extract"] = "MergeRegistered"
                   /\ merged_dag_nodes' = (new_dag_nodes \union old_registered_nodes)
                   /\ phase' = "Uploading"
                   /\ time_elapsed' = time_elapsed + 1
                   /\ pc' = [pc EXCEPT !["cmd_extract"] = "UploadDag"]
                   /\ UNCHANGED << old_registered_nodes, new_dag_nodes, 
                                   llm_called, subprocess_called, dag_uploaded >>

UploadDag == /\ pc["cmd_extract"] = "UploadDag"
             /\ dag_uploaded' = TRUE
             /\ phase' = "Complete"
             /\ time_elapsed' = time_elapsed + 1
             /\ pc' = [pc EXCEPT !["cmd_extract"] = "Finish"]
             /\ UNCHANGED << old_registered_nodes, new_dag_nodes, 
                             merged_dag_nodes, llm_called, subprocess_called >>

Finish == /\ pc["cmd_extract"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["cmd_extract"] = "Done"]
          /\ UNCHANGED << phase, old_registered_nodes, new_dag_nodes, 
                          merged_dag_nodes, llm_called, subprocess_called, 
                          dag_uploaded, time_elapsed >>

cmd_extract_proc == Dequeue \/ LoadOldDag \/ RunExtract \/ MergeRegistered
                       \/ UploadDag \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == cmd_extract_proc
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(cmd_extract_proc)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
