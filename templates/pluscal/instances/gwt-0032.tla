---- MODULE ExtractPreservesGwts ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    OldGwts,
    OldReqs,
    SchemaNodes,
    MaxSteps

ASSUME OldGwts # {}
ASSUME OldReqs # {}
ASSUME SchemaNodes # {}

(* --algorithm ExtractPreservesGwts
variables
    old_dag_nodes = {},
    extracted_nodes = {},
    result_nodes = {},
    old_gwt_nodes = {},
    phase = "load_old",
    step_count = 0;

define
    TypeOK ==
        /\ phase \in {"load_old", "extract", "merge", "save", "done"}
        /\ step_count <= MaxSteps

    GwtPreserved ==
        phase = "done" => old_gwt_nodes \subseteq result_nodes

    SchemaFresh ==
        phase = "done" => extracted_nodes \subseteq result_nodes

    NoGwtLoss ==
        phase = "done" => \A n \in old_gwt_nodes : n \in result_nodes

    BoundedExecution ==
        step_count <= MaxSteps

    MergeCorrect ==
        phase = "done" => result_nodes = extracted_nodes \union old_gwt_nodes
end define;

fair process extractor = "main"
begin
    LoadOld:
        old_dag_nodes := OldGwts \union OldReqs;
        old_gwt_nodes := OldGwts \union OldReqs;
        phase := "extract";
        step_count := step_count + 1;
    Extract:
        extracted_nodes := SchemaNodes;
        phase := "merge";
        step_count := step_count + 1;
    Merge:
        result_nodes := extracted_nodes \union old_gwt_nodes;
        phase := "save";
        step_count := step_count + 1;
    Save:
        phase := "done";
        step_count := step_count + 1;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "19a1e0fe" /\ chksum(tla) = "e885f7bd")
VARIABLES pc, old_dag_nodes, extracted_nodes, result_nodes, old_gwt_nodes, 
          phase, step_count

(* define statement *)
TypeOK ==
    /\ phase \in {"load_old", "extract", "merge", "save", "done"}
    /\ step_count <= MaxSteps

GwtPreserved ==
    phase = "done" => old_gwt_nodes \subseteq result_nodes

SchemaFresh ==
    phase = "done" => extracted_nodes \subseteq result_nodes

NoGwtLoss ==
    phase = "done" => \A n \in old_gwt_nodes : n \in result_nodes

BoundedExecution ==
    step_count <= MaxSteps

MergeCorrect ==
    phase = "done" => result_nodes = extracted_nodes \union old_gwt_nodes


vars == << pc, old_dag_nodes, extracted_nodes, result_nodes, old_gwt_nodes, 
           phase, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ old_dag_nodes = {}
        /\ extracted_nodes = {}
        /\ result_nodes = {}
        /\ old_gwt_nodes = {}
        /\ phase = "load_old"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "LoadOld"]

LoadOld == /\ pc["main"] = "LoadOld"
           /\ old_dag_nodes' = (OldGwts \union OldReqs)
           /\ old_gwt_nodes' = (OldGwts \union OldReqs)
           /\ phase' = "extract"
           /\ step_count' = step_count + 1
           /\ pc' = [pc EXCEPT !["main"] = "Extract"]
           /\ UNCHANGED << extracted_nodes, result_nodes >>

Extract == /\ pc["main"] = "Extract"
           /\ extracted_nodes' = SchemaNodes
           /\ phase' = "merge"
           /\ step_count' = step_count + 1
           /\ pc' = [pc EXCEPT !["main"] = "Merge"]
           /\ UNCHANGED << old_dag_nodes, result_nodes, old_gwt_nodes >>

Merge == /\ pc["main"] = "Merge"
         /\ result_nodes' = (extracted_nodes \union old_gwt_nodes)
         /\ phase' = "save"
         /\ step_count' = step_count + 1
         /\ pc' = [pc EXCEPT !["main"] = "Save"]
         /\ UNCHANGED << old_dag_nodes, extracted_nodes, old_gwt_nodes >>

Save == /\ pc["main"] = "Save"
        /\ phase' = "done"
        /\ step_count' = step_count + 1
        /\ pc' = [pc EXCEPT !["main"] = "Finish"]
        /\ UNCHANGED << old_dag_nodes, extracted_nodes, result_nodes, 
                        old_gwt_nodes >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << old_dag_nodes, extracted_nodes, result_nodes, 
                          old_gwt_nodes, phase, step_count >>

extractor == LoadOld \/ Extract \/ Merge \/ Save \/ Finish

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
