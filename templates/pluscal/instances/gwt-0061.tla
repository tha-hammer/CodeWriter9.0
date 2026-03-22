---- MODULE go_profile_file_validity ----

EXTENDS Integers, FiniteSets, TLC

Verifiers == <<
    [name |-> "inv1", has_cond |-> TRUE,  is_dict |-> TRUE,  uses_quant |-> FALSE],
    [name |-> "inv2", has_cond |-> TRUE,  is_dict |-> TRUE,  uses_quant |-> TRUE],
    [name |-> "inv3", has_cond |-> FALSE, is_dict |-> TRUE,  uses_quant |-> FALSE],
    [name |-> "skip", has_cond |-> TRUE,  is_dict |-> FALSE, uses_quant |-> FALSE]
>>
N == 4

(* --algorithm GoFileValidity

variables
    cursor        = 1,
    compiled      = {},
    helper_needed = FALSE,
    stage         = "idle",
    passed        = FALSE;

define
    BatchConsistent ==
        cursor > N =>
            \A k \in 1..N :
                (Verifiers[k].is_dict /\ Verifiers[k].has_cond) =>
                    \E c \in compiled : c.name = Verifiers[k].name

    HelperIncluded ==
        helper_needed =>
            (stage \in {"vet", "list", "run", "done"} => passed = TRUE)

    StageOrdering ==
        stage \in {"idle", "compile_all", "vet", "list", "run", "done"}

    VetPassedWhenDone ==
        stage = "done" => passed = TRUE

    CompiledOnlyEligible ==
        \A c \in compiled :
            \E k \in 1..N :
                Verifiers[k].name = c.name /\
                Verifiers[k].is_dict /\
                Verifiers[k].has_cond

    HelperNeededIffQuantUsed ==
        cursor > N =>
            (helper_needed <=>
                \E k \in 1..N :
                    Verifiers[k].is_dict /\
                    Verifiers[k].has_cond /\
                    Verifiers[k].uses_quant)
end define;

process verifier = "verifier"
begin
    CompileAll:
        stage := "compile_all";
    LoopStart:
        while cursor <= N do
            ProcessV:
                if Verifiers[cursor].is_dict /\ Verifiers[cursor].has_cond then
                    compiled := compiled \cup {[name |-> Verifiers[cursor].name]};
                    if Verifiers[cursor].uses_quant then
                        helper_needed := TRUE;
                    end if;
                end if;
            AdvanceV:
                cursor := cursor + 1;
        end while;
    GoVet:
        stage := "vet";
        passed := TRUE;
    ListTests:
        stage := "list";
    RunTests:
        stage := "run";
    Finish:
        stage := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "140c9f67" /\ chksum(tla) = "e49a02c6")
VARIABLES pc, cursor, compiled, helper_needed, stage, passed

(* define statement *)
BatchConsistent ==
    cursor > N =>
        \A k \in 1..N :
            (Verifiers[k].is_dict /\ Verifiers[k].has_cond) =>
                \E c \in compiled : c.name = Verifiers[k].name

HelperIncluded ==
    helper_needed =>
        (stage \in {"vet", "list", "run", "done"} => passed = TRUE)

StageOrdering ==
    stage \in {"idle", "compile_all", "vet", "list", "run", "done"}

VetPassedWhenDone ==
    stage = "done" => passed = TRUE

CompiledOnlyEligible ==
    \A c \in compiled :
        \E k \in 1..N :
            Verifiers[k].name = c.name /\
            Verifiers[k].is_dict /\
            Verifiers[k].has_cond

HelperNeededIffQuantUsed ==
    cursor > N =>
        (helper_needed <=>
            \E k \in 1..N :
                Verifiers[k].is_dict /\
                Verifiers[k].has_cond /\
                Verifiers[k].uses_quant)


vars == << pc, cursor, compiled, helper_needed, stage, passed >>

ProcSet == {"verifier"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ compiled = {}
        /\ helper_needed = FALSE
        /\ stage = "idle"
        /\ passed = FALSE
        /\ pc = [self \in ProcSet |-> "CompileAll"]

CompileAll == /\ pc["verifier"] = "CompileAll"
              /\ stage' = "compile_all"
              /\ pc' = [pc EXCEPT !["verifier"] = "LoopStart"]
              /\ UNCHANGED << cursor, compiled, helper_needed, passed >>

LoopStart == /\ pc["verifier"] = "LoopStart"
             /\ IF cursor <= N
                   THEN /\ pc' = [pc EXCEPT !["verifier"] = "ProcessV"]
                   ELSE /\ pc' = [pc EXCEPT !["verifier"] = "GoVet"]
             /\ UNCHANGED << cursor, compiled, helper_needed, stage, passed >>

ProcessV == /\ pc["verifier"] = "ProcessV"
            /\ IF Verifiers[cursor].is_dict /\ Verifiers[cursor].has_cond
                  THEN /\ compiled' = (compiled \cup {[name |-> Verifiers[cursor].name]})
                       /\ IF Verifiers[cursor].uses_quant
                             THEN /\ helper_needed' = TRUE
                             ELSE /\ TRUE
                                  /\ UNCHANGED helper_needed
                  ELSE /\ TRUE
                       /\ UNCHANGED << compiled, helper_needed >>
            /\ pc' = [pc EXCEPT !["verifier"] = "AdvanceV"]
            /\ UNCHANGED << cursor, stage, passed >>

AdvanceV == /\ pc["verifier"] = "AdvanceV"
            /\ cursor' = cursor + 1
            /\ pc' = [pc EXCEPT !["verifier"] = "LoopStart"]
            /\ UNCHANGED << compiled, helper_needed, stage, passed >>

GoVet == /\ pc["verifier"] = "GoVet"
         /\ stage' = "vet"
         /\ passed' = TRUE
         /\ pc' = [pc EXCEPT !["verifier"] = "ListTests"]
         /\ UNCHANGED << cursor, compiled, helper_needed >>

ListTests == /\ pc["verifier"] = "ListTests"
             /\ stage' = "list"
             /\ pc' = [pc EXCEPT !["verifier"] = "RunTests"]
             /\ UNCHANGED << cursor, compiled, helper_needed, passed >>

RunTests == /\ pc["verifier"] = "RunTests"
            /\ stage' = "run"
            /\ pc' = [pc EXCEPT !["verifier"] = "Finish"]
            /\ UNCHANGED << cursor, compiled, helper_needed, passed >>

Finish == /\ pc["verifier"] = "Finish"
          /\ stage' = "done"
          /\ pc' = [pc EXCEPT !["verifier"] = "Done"]
          /\ UNCHANGED << cursor, compiled, helper_needed, passed >>

verifier == CompileAll \/ LoopStart \/ ProcessV \/ AdvanceV \/ GoVet
               \/ ListTests \/ RunTests \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == verifier
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
