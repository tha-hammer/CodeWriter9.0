---- MODULE rust_profile_file_validity ----

EXTENDS Integers, FiniteSets, TLC

Verifiers == <<
    [name |-> "inv1", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv2", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv3", has_cond |-> FALSE, is_dict |-> TRUE],
    [name |-> "skip", has_cond |-> TRUE,  is_dict |-> FALSE]
>>
N == 4

(* --algorithm RustFileValidity

variables
    cursor   = 1,
    compiled = {},
    stage    = "idle",
    passed   = FALSE;

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

    NoHelperNeeded ==
        TRUE

    StageOrdering ==
        stage \in {"idle", "compile_all", "cargo_check", "compile_test", "run", "done"}

    CargoCheckPassedOnlyAfterCompile ==
        passed => stage \in {"cargo_check", "compile_test", "run", "done"}

    CompiledSubsetValid ==
        \A c \in compiled :
            \E k \in 1..N :
                Verifiers[k].name = c.name /\
                Verifiers[k].is_dict /\
                Verifiers[k].has_cond

    TestFileValid ==
        stage = "done" => passed

end define;

process verifier = "verifier"
begin
    CompileAll:
        stage := "compile_all";
    ProcessLoop:
        while cursor <= N do
            ProcessV:
                if Verifiers[cursor].is_dict /\ Verifiers[cursor].has_cond then
                    compiled := compiled \cup {[name |-> Verifiers[cursor].name]};
                end if;
            AdvanceV:
                cursor := cursor + 1;
        end while;
    CargoCheck:
        stage := "cargo_check";
        passed := TRUE;
    CompileTest:
        stage := "compile_test";
    RunTest:
        stage := "run";
    Finish:
        stage := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "9d90363d" /\ chksum(tla) = "7a4c96eb")
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

NoHelperNeeded ==
    TRUE

StageOrdering ==
    stage \in {"idle", "compile_all", "cargo_check", "compile_test", "run", "done"}

CargoCheckPassedOnlyAfterCompile ==
    passed => stage \in {"cargo_check", "compile_test", "run", "done"}

CompiledSubsetValid ==
    \A c \in compiled :
        \E k \in 1..N :
            Verifiers[k].name = c.name /\
            Verifiers[k].is_dict /\
            Verifiers[k].has_cond

TestFileValid ==
    stage = "done" => passed


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
                     THEN /\ pc' = [pc EXCEPT !["verifier"] = "ProcessV"]
                     ELSE /\ pc' = [pc EXCEPT !["verifier"] = "CargoCheck"]
               /\ UNCHANGED << cursor, compiled, stage, passed >>

ProcessV == /\ pc["verifier"] = "ProcessV"
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

CargoCheck == /\ pc["verifier"] = "CargoCheck"
              /\ stage' = "cargo_check"
              /\ passed' = TRUE
              /\ pc' = [pc EXCEPT !["verifier"] = "CompileTest"]
              /\ UNCHANGED << cursor, compiled >>

CompileTest == /\ pc["verifier"] = "CompileTest"
               /\ stage' = "compile_test"
               /\ pc' = [pc EXCEPT !["verifier"] = "RunTest"]
               /\ UNCHANGED << cursor, compiled, passed >>

RunTest == /\ pc["verifier"] = "RunTest"
           /\ stage' = "run"
           /\ pc' = [pc EXCEPT !["verifier"] = "Finish"]
           /\ UNCHANGED << cursor, compiled, passed >>

Finish == /\ pc["verifier"] = "Finish"
          /\ stage' = "done"
          /\ pc' = [pc EXCEPT !["verifier"] = "Done"]
          /\ UNCHANGED << cursor, compiled, passed >>

verifier == CompileAll \/ ProcessLoop \/ ProcessV \/ AdvanceV \/ CargoCheck
               \/ CompileTest \/ RunTest \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == verifier
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
