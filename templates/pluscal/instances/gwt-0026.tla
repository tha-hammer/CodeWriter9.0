---- MODULE StalenessPropagation ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Nodes,
    Hashes,
    MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps > 0
ASSUME Nodes /= {} /\ Hashes /= {}

(*--algorithm StalenessPropagation

variables
    stored_hashes  \in [Nodes -> Hashes],
    current_hashes \in [Nodes -> Hashes],
    edges          \in SUBSET (Nodes \X Nodes),
    direct_stale   = {},
    transitive_stale = {},
    phase          = "detect",
    step_count     = 0,
    prev_size      = 0;

define

    DirectlyStale ==
        {n \in Nodes : stored_hashes[n] /= current_hashes[n]}

    OneHopExpand(S) ==
        S \cup {e[1] : e \in {ep \in edges : ep[2] \in S}}

    DirectCorrect ==
        phase /= "detect" => direct_stale = DirectlyStale

    MonotonicGrowth ==
        Cardinality(transitive_stale) >= prev_size

    TransitiveComplete ==
        phase = "complete" =>
            /\ OneHopExpand(transitive_stale) = transitive_stale
            /\ direct_stale \subseteq transitive_stale

    NoFalseNegatives ==
        phase = "complete" =>
            \A n \in Nodes : n \in direct_stale => n \in transitive_stale

    AllDependentsIncluded ==
        phase = "complete" =>
            \A e \in edges :
                e[2] \in transitive_stale => e[1] \in transitive_stale

    BoundedExecution == step_count <= MaxSteps

end define;

fair process detector = "detector"
begin
    DetectDirect:
        direct_stale     := DirectlyStale;
        transitive_stale := DirectlyStale;
        prev_size        := 0;
        phase            := "propagate";
        step_count       := step_count + 1;

    PropLoop:
        while phase = "propagate" /\ step_count < MaxSteps do
            PropStep:
                prev_size        := Cardinality(transitive_stale);
                transitive_stale := OneHopExpand(transitive_stale);
                step_count       := step_count + 1;
            CheckFix:
                if Cardinality(transitive_stale) = prev_size then
                    phase := "complete";
                end if;
        end while;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "5673275b" /\ chksum(tla) = "760d1888")
VARIABLES pc, stored_hashes, current_hashes, edges, direct_stale, 
          transitive_stale, phase, step_count, prev_size

(* define statement *)
DirectlyStale ==
    {n \in Nodes : stored_hashes[n] /= current_hashes[n]}

OneHopExpand(S) ==
    S \cup {e[1] : e \in {ep \in edges : ep[2] \in S}}

DirectCorrect ==
    phase /= "detect" => direct_stale = DirectlyStale

MonotonicGrowth ==
    Cardinality(transitive_stale) >= prev_size

TransitiveComplete ==
    phase = "complete" =>
        /\ OneHopExpand(transitive_stale) = transitive_stale
        /\ direct_stale \subseteq transitive_stale

NoFalseNegatives ==
    phase = "complete" =>
        \A n \in Nodes : n \in direct_stale => n \in transitive_stale

AllDependentsIncluded ==
    phase = "complete" =>
        \A e \in edges :
            e[2] \in transitive_stale => e[1] \in transitive_stale

BoundedExecution == step_count <= MaxSteps


vars == << pc, stored_hashes, current_hashes, edges, direct_stale, 
           transitive_stale, phase, step_count, prev_size >>

ProcSet == {"detector"}

Init == (* Global variables *)
        /\ stored_hashes \in [Nodes -> Hashes]
        /\ current_hashes \in [Nodes -> Hashes]
        /\ edges \in SUBSET (Nodes \X Nodes)
        /\ direct_stale = {}
        /\ transitive_stale = {}
        /\ phase = "detect"
        /\ step_count = 0
        /\ prev_size = 0
        /\ pc = [self \in ProcSet |-> "DetectDirect"]

DetectDirect == /\ pc["detector"] = "DetectDirect"
                /\ direct_stale' = DirectlyStale
                /\ transitive_stale' = DirectlyStale
                /\ prev_size' = 0
                /\ phase' = "propagate"
                /\ step_count' = step_count + 1
                /\ pc' = [pc EXCEPT !["detector"] = "PropLoop"]
                /\ UNCHANGED << stored_hashes, current_hashes, edges >>

PropLoop == /\ pc["detector"] = "PropLoop"
            /\ IF phase = "propagate" /\ step_count < MaxSteps
                  THEN /\ pc' = [pc EXCEPT !["detector"] = "PropStep"]
                  ELSE /\ pc' = [pc EXCEPT !["detector"] = "Finish"]
            /\ UNCHANGED << stored_hashes, current_hashes, edges, direct_stale, 
                            transitive_stale, phase, step_count, prev_size >>

PropStep == /\ pc["detector"] = "PropStep"
            /\ prev_size' = Cardinality(transitive_stale)
            /\ transitive_stale' = OneHopExpand(transitive_stale)
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["detector"] = "CheckFix"]
            /\ UNCHANGED << stored_hashes, current_hashes, edges, direct_stale, 
                            phase >>

CheckFix == /\ pc["detector"] = "CheckFix"
            /\ IF Cardinality(transitive_stale) = prev_size
                  THEN /\ phase' = "complete"
                  ELSE /\ TRUE
                       /\ phase' = phase
            /\ pc' = [pc EXCEPT !["detector"] = "PropLoop"]
            /\ UNCHANGED << stored_hashes, current_hashes, edges, direct_stale, 
                            transitive_stale, step_count, prev_size >>

Finish == /\ pc["detector"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["detector"] = "Done"]
          /\ UNCHANGED << stored_hashes, current_hashes, edges, direct_stale, 
                          transitive_stale, phase, step_count, prev_size >>

detector == DetectDirect \/ PropLoop \/ PropStep \/ CheckFix \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == detector
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(detector)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
