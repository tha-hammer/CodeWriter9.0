--------------------------- MODULE ContextStackRanking ---------------------------

EXTENDS Integers, Sequences, FiniteSets, TLC

(*
 * Models build_test_plan_prompt() context-section ranking (gwt-0041).
 * Ranks: 1=simulation_traces  2=api_context  3=verifiers+compiler_hints
 *        4=tla_spec_text       5=structural_patterns
 * Fallback: if rank-1 absent but test_scenarios non-empty, a fallback
 * section is appended after rank 5.
 *)

(* --algorithm ContextStackRanking

variables
    has_sim_traces     \in {TRUE, FALSE},
    has_api_context    = TRUE,
    has_verifiers      \in {TRUE, FALSE},
    has_tla_spec       \in {TRUE, FALSE},
    has_test_scenarios \in {TRUE, FALSE},
    section_order      = <<>>,
    fallback_appended  = FALSE,
    built              = FALSE;

define

    ContainsRank(r) ==
        \E i \in 1..Len(section_order) : section_order[i] = r

    StrictlyIncreasing ==
        \A i \in 1..(Len(section_order) - 1) :
            section_order[i] < section_order[i + 1]

    ValidRanks ==
        \A i \in 1..Len(section_order) :
            section_order[i] \in 1..5

    NoDuplicates ==
        \A i \in 1..Len(section_order) :
        \A j \in 1..Len(section_order) :
            i # j => section_order[i] # section_order[j]

    SimTracesFirst ==
        built =>
            ((has_sim_traces /\ Len(section_order) >= 1) => section_order[1] = 1)

    Rank1Iff ==
        built => (ContainsRank(1) <=> has_sim_traces)

    Rank2Iff ==
        built => (ContainsRank(2) <=> has_api_context)

    Rank3Iff ==
        built => (ContainsRank(3) <=> has_verifiers)

    Rank4Iff ==
        built => (ContainsRank(4) <=> has_tla_spec)

    Rank5Always ==
        built => ContainsRank(5)

    FallbackIff ==
        built =>
            (fallback_appended <=> (~has_sim_traces /\ has_test_scenarios))

    TypeOK ==
        /\ has_sim_traces     \in BOOLEAN
        /\ has_api_context    \in BOOLEAN
        /\ has_verifiers      \in BOOLEAN
        /\ has_tla_spec       \in BOOLEAN
        /\ has_test_scenarios \in BOOLEAN
        /\ fallback_appended  \in BOOLEAN
        /\ built              \in BOOLEAN
        /\ \A i \in 1..Len(section_order) : section_order[i] \in 1..5

    OrderingInvariant ==
        built =>
            /\ StrictlyIncreasing
            /\ ValidRanks
            /\ NoDuplicates
            /\ SimTracesFirst
            /\ Rank1Iff
            /\ Rank2Iff
            /\ Rank3Iff
            /\ Rank4Iff
            /\ Rank5Always
            /\ FallbackIff

    GWTInvariant ==
        built =>
            /\ (has_sim_traces => section_order[1] = 1)
            /\ (has_api_context =>
                    \E i \in 1..Len(section_order) :
                        /\ section_order[i] = 2
                        /\ (~has_sim_traces \/ i > 1))
            /\ (has_verifiers =>
                    \E i \in 1..Len(section_order) :
                        /\ section_order[i] = 3
                        /\ (~has_api_context \/ \E j \in 1..(i-1) : section_order[j] = 2))
            /\ (has_tla_spec =>
                    \E i \in 1..Len(section_order) :
                        /\ section_order[i] = 4
                        /\ (~has_verifiers \/ \E j \in 1..(i-1) : section_order[j] = 3))
            /\ (\E i \in 1..Len(section_order) :
                    /\ section_order[i] = 5
                    /\ (~has_tla_spec \/ \E j \in 1..(i-1) : section_order[j] = 4))

end define;

fair process promptBuilder = "builder"
begin
    AppendRank1:
        if has_sim_traces then
            section_order := Append(section_order, 1);
        end if;
    AppendRank2:
        if has_api_context then
            section_order := Append(section_order, 2);
        end if;
    AppendRank3:
        if has_verifiers then
            section_order := Append(section_order, 3);
        end if;
    AppendRank4:
        if has_tla_spec then
            section_order := Append(section_order, 4);
        end if;
    AppendRank5:
        section_order := Append(section_order, 5);
    CheckFallback:
        if ~has_sim_traces /\ has_test_scenarios then
            fallback_appended := TRUE;
        end if;
    Finish:
        built := TRUE;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "7f9ccf76" /\ chksum(tla) = "bc290d15")
VARIABLES pc, has_sim_traces, has_api_context, has_verifiers, has_tla_spec, 
          has_test_scenarios, section_order, fallback_appended, built

(* define statement *)
ContainsRank(r) ==
    \E i \in 1..Len(section_order) : section_order[i] = r

StrictlyIncreasing ==
    \A i \in 1..(Len(section_order) - 1) :
        section_order[i] < section_order[i + 1]

ValidRanks ==
    \A i \in 1..Len(section_order) :
        section_order[i] \in 1..5

NoDuplicates ==
    \A i \in 1..Len(section_order) :
    \A j \in 1..Len(section_order) :
        i # j => section_order[i] # section_order[j]

SimTracesFirst ==
    built =>
        ((has_sim_traces /\ Len(section_order) >= 1) => section_order[1] = 1)

Rank1Iff ==
    built => (ContainsRank(1) <=> has_sim_traces)

Rank2Iff ==
    built => (ContainsRank(2) <=> has_api_context)

Rank3Iff ==
    built => (ContainsRank(3) <=> has_verifiers)

Rank4Iff ==
    built => (ContainsRank(4) <=> has_tla_spec)

Rank5Always ==
    built => ContainsRank(5)

FallbackIff ==
    built =>
        (fallback_appended <=> (~has_sim_traces /\ has_test_scenarios))

TypeOK ==
    /\ has_sim_traces     \in BOOLEAN
    /\ has_api_context    \in BOOLEAN
    /\ has_verifiers      \in BOOLEAN
    /\ has_tla_spec       \in BOOLEAN
    /\ has_test_scenarios \in BOOLEAN
    /\ fallback_appended  \in BOOLEAN
    /\ built              \in BOOLEAN
    /\ \A i \in 1..Len(section_order) : section_order[i] \in 1..5

OrderingInvariant ==
    built =>
        /\ StrictlyIncreasing
        /\ ValidRanks
        /\ NoDuplicates
        /\ SimTracesFirst
        /\ Rank1Iff
        /\ Rank2Iff
        /\ Rank3Iff
        /\ Rank4Iff
        /\ Rank5Always
        /\ FallbackIff

GWTInvariant ==
    built =>
        /\ (has_sim_traces => section_order[1] = 1)
        /\ (has_api_context =>
                \E i \in 1..Len(section_order) :
                    /\ section_order[i] = 2
                    /\ (~has_sim_traces \/ i > 1))
        /\ (has_verifiers =>
                \E i \in 1..Len(section_order) :
                    /\ section_order[i] = 3
                    /\ (~has_api_context \/ \E j \in 1..(i-1) : section_order[j] = 2))
        /\ (has_tla_spec =>
                \E i \in 1..Len(section_order) :
                    /\ section_order[i] = 4
                    /\ (~has_verifiers \/ \E j \in 1..(i-1) : section_order[j] = 3))
        /\ (\E i \in 1..Len(section_order) :
                /\ section_order[i] = 5
                /\ (~has_tla_spec \/ \E j \in 1..(i-1) : section_order[j] = 4))


vars == << pc, has_sim_traces, has_api_context, has_verifiers, has_tla_spec, 
           has_test_scenarios, section_order, fallback_appended, built >>

ProcSet == {"builder"}

Init == (* Global variables *)
        /\ has_sim_traces \in {TRUE, FALSE}
        /\ has_api_context = TRUE
        /\ has_verifiers \in {TRUE, FALSE}
        /\ has_tla_spec \in {TRUE, FALSE}
        /\ has_test_scenarios \in {TRUE, FALSE}
        /\ section_order = <<>>
        /\ fallback_appended = FALSE
        /\ built = FALSE
        /\ pc = [self \in ProcSet |-> "AppendRank1"]

AppendRank1 == /\ pc["builder"] = "AppendRank1"
               /\ IF has_sim_traces
                     THEN /\ section_order' = Append(section_order, 1)
                     ELSE /\ TRUE
                          /\ UNCHANGED section_order
               /\ pc' = [pc EXCEPT !["builder"] = "AppendRank2"]
               /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                               has_tla_spec, has_test_scenarios, 
                               fallback_appended, built >>

AppendRank2 == /\ pc["builder"] = "AppendRank2"
               /\ IF has_api_context
                     THEN /\ section_order' = Append(section_order, 2)
                     ELSE /\ TRUE
                          /\ UNCHANGED section_order
               /\ pc' = [pc EXCEPT !["builder"] = "AppendRank3"]
               /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                               has_tla_spec, has_test_scenarios, 
                               fallback_appended, built >>

AppendRank3 == /\ pc["builder"] = "AppendRank3"
               /\ IF has_verifiers
                     THEN /\ section_order' = Append(section_order, 3)
                     ELSE /\ TRUE
                          /\ UNCHANGED section_order
               /\ pc' = [pc EXCEPT !["builder"] = "AppendRank4"]
               /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                               has_tla_spec, has_test_scenarios, 
                               fallback_appended, built >>

AppendRank4 == /\ pc["builder"] = "AppendRank4"
               /\ IF has_tla_spec
                     THEN /\ section_order' = Append(section_order, 4)
                     ELSE /\ TRUE
                          /\ UNCHANGED section_order
               /\ pc' = [pc EXCEPT !["builder"] = "AppendRank5"]
               /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                               has_tla_spec, has_test_scenarios, 
                               fallback_appended, built >>

AppendRank5 == /\ pc["builder"] = "AppendRank5"
               /\ section_order' = Append(section_order, 5)
               /\ pc' = [pc EXCEPT !["builder"] = "CheckFallback"]
               /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                               has_tla_spec, has_test_scenarios, 
                               fallback_appended, built >>

CheckFallback == /\ pc["builder"] = "CheckFallback"
                 /\ IF ~has_sim_traces /\ has_test_scenarios
                       THEN /\ fallback_appended' = TRUE
                       ELSE /\ TRUE
                            /\ UNCHANGED fallback_appended
                 /\ pc' = [pc EXCEPT !["builder"] = "Finish"]
                 /\ UNCHANGED << has_sim_traces, has_api_context, 
                                 has_verifiers, has_tla_spec, 
                                 has_test_scenarios, section_order, built >>

Finish == /\ pc["builder"] = "Finish"
          /\ built' = TRUE
          /\ pc' = [pc EXCEPT !["builder"] = "Done"]
          /\ UNCHANGED << has_sim_traces, has_api_context, has_verifiers, 
                          has_tla_spec, has_test_scenarios, section_order, 
                          fallback_appended >>

promptBuilder == AppendRank1 \/ AppendRank2 \/ AppendRank3 \/ AppendRank4
                    \/ AppendRank5 \/ CheckFallback \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == promptBuilder
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(promptBuilder)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

AllInvariants == TypeOK /\ OrderingInvariant /\ GWTInvariant

GWTLiveness == <>(built)

=============================================================================
