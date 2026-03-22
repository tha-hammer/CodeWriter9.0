---- MODULE python_profile_file_validity ----

EXTENDS Integers, FiniteSets, TLC

Verifiers == <<
    [name |-> "inv1", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv2", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv3", has_cond |-> FALSE, is_dict |-> TRUE],
    [name |-> "skip", has_cond |-> TRUE,  is_dict |-> FALSE]
>>
N == 4

(* --algorithm PythonFileValidity

variables
    cursor    = 1,
    compiled  = {},
    stage     = "idle",
    passed    = FALSE;

define
    BatchConsistent ==
        cursor > N =>
            \A k \in 1..N :
                (Verifiers[k].is_dict /\ Verifiers[k].has_cond) =>
                    \E c \in compiled : c.name = Verifiers[k].name

    NonDictSkipped ==
        ~(\E c \in compiled : c.name = "skip")

    EmptyCondSkipped ==
        ~(\E c \in compiled : c.name = "inv3")

    StageOrdering ==
        stage \in {"idle", "compile_all", "check_syntax", "check_collect", "done"}

    SyntaxPassedOnlyAfterCompile ==
        passed => stage \in {"check_syntax", "check_collect", "done"}

    CollectImpliesSyntax ==
        stage = "check_collect" => passed = TRUE

    DoneImpliesAllChecked ==
        stage = "done" => passed = TRUE
end define;

process verifier = "verifier"
begin
    CompileAll:
        stage := "compile_all";
    ProcessLoop:
        while cursor <= N do
            ProcessVerifier:
                if Verifiers[cursor].is_dict /\ Verifiers[cursor].has_cond then
                    compiled := compiled \cup {[name |-> Verifiers[cursor].name]};
                end if;
            AdvanceV:
                cursor := cursor + 1;
        end while;
    CheckSyntax:
        stage := "check_syntax";
        passed := TRUE;
    CheckCollect:
        stage := "check_collect";
        skip;
    Finish:
        stage := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "dc3442ae" /\ chksum(tla) = "965ca295")
VARIABLES pc, cursor, compiled, stage, passed

(* define statement *)
BatchConsistent ==
    cursor > N =>
        \A k \in 1..N :
            (Verifiers[k].is_dict /\ Verifiers[k].has_cond) =>
                \E c \in compiled : c.name = Verifiers[k].name

NonDictSkipped ==
    ~(\E c \in compiled : c.name = "skip")

EmptyCondSkipped ==
    ~(\E c \in compiled : c.name = "inv3")

StageOrdering ==
    stage \in {"idle", "compile_all", "check_syntax", "check_collect", "done"}

SyntaxPassedOnlyAfterCompile ==
    passed => stage \in {"check_syntax", "check_collect", "done"}

CollectImpliesSyntax ==
    stage = "check_collect" => passed = TRUE

DoneImpliesAllChecked ==
    stage = "done" => passed = TRUE


vars == << pc, cursor, compiled, stage, passed >>

ProcSet == {"verifier"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ compiled = {}
        /\ stage = "idle"
        /\ passed = FALSE
        /\ pc = [self \in ProcSet |-> "CompileAll"]

CompileAll == /\ pc["verifier"] = "CompileAll"
              /\ stage' = "compile_all"
              /\ pc' = [pc EXCEPT !["verifier"] = "ProcessLoop"]
              /\ UNCHANGED << cursor, compiled, passed >>

ProcessLoop == /\ pc["verifier"] = "ProcessLoop"
               /\ IF cursor <= N
                     THEN /\ pc' = [pc EXCEPT !["verifier"] = "ProcessVerifier"]
                     ELSE /\ pc' = [pc EXCEPT !["verifier"] = "CheckSyntax"]
               /\ UNCHANGED << cursor, compiled, stage, passed >>

ProcessVerifier == /\ pc["verifier"] = "ProcessVerifier"
                   /\ IF Verifiers[cursor].is_dict /\ Verifiers[cursor].has_cond
                         THEN /\ compiled' = (compiled \cup {[name |-> Verifiers[cursor].name]})
                         ELSE /\ TRUE
                              /\ UNCHANGED compiled
                   /\ pc' = [pc EXCEPT !["verifier"] = "AdvanceV"]
                   /\ UNCHANGED << cursor, stage, passed >>

AdvanceV == /\ pc["verifier"] = "AdvanceV"
            /\ cursor' = cursor + 1
            /\ pc' = [pc EXCEPT !["verifier"] = "ProcessLoop"]
            /\ UNCHANGED << compiled, stage, passed >>

CheckSyntax == /\ pc["verifier"] = "CheckSyntax"
               /\ stage' = "check_syntax"
               /\ passed' = TRUE
               /\ pc' = [pc EXCEPT !["verifier"] = "CheckCollect"]
               /\ UNCHANGED << cursor, compiled >>

CheckCollect == /\ pc["verifier"] = "CheckCollect"
                /\ stage' = "check_collect"
                /\ TRUE
                /\ pc' = [pc EXCEPT !["verifier"] = "Finish"]
                /\ UNCHANGED << cursor, compiled, passed >>

Finish == /\ pc["verifier"] = "Finish"
          /\ stage' = "done"
          /\ pc' = [pc EXCEPT !["verifier"] = "Done"]
          /\ UNCHANGED << cursor, compiled, passed >>

verifier == CompileAll \/ ProcessLoop \/ ProcessVerifier \/ AdvanceV
               \/ CheckSyntax \/ CheckCollect \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == verifier
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
