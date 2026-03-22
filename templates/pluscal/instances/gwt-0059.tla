---- MODULE typescript_profile_file_validity ----

EXTENDS Integers, FiniteSets, TLC

Verifiers == <<
    [name |-> "inv1", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv2", has_cond |-> TRUE,  is_dict |-> TRUE],
    [name |-> "inv3", has_cond |-> FALSE, is_dict |-> TRUE],
    [name |-> "skip", has_cond |-> TRUE,  is_dict |-> FALSE]
>>
N == 4

(* --algorithm TSFileValidity

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

    StageOrdering ==
        stage \in {"idle", "compile_all", "type_check", "discover", "run", "done"}

    TypeCheckPassedOnlyAfterCompile ==
        passed => stage \in {"type_check", "discover", "run", "done"}

    CompiledSubsetValid ==
        \A c \in compiled :
            \E k \in 1..N :
                Verifiers[k].name = c.name /\
                Verifiers[k].is_dict /\
                Verifiers[k].has_cond

    TerminalImpliesAllChecked ==
        stage = "done" => passed = TRUE

    NoDuplicateNames ==
        \A c1 \in compiled : \A c2 \in compiled :
            c1.name = c2.name => c1 = c2
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
    TypeCheck:
        stage := "type_check";
        passed := TRUE;
    Discover:
        stage := "discover";
    Run:
        stage := "run";
    Finish:
        stage := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "2e5f2285" /\ chksum(tla) = "5306f567")
VARIABLES pc, cursor, compiled, stage, passed

(* define statement *)
BatchConsistent ==
    cursor > N =>
        \A k \in 1..N :
            (Verifiers[k].is_dict /\ Verifiers[k].has_cond) =>
                \E c \in compiled : c.name = Verifiers[k].name

NonDictSkipped ==
    ~(\E c \in compiled : c.name = "skip")

StageOrdering ==
    stage \in {"idle", "compile_all", "type_check", "discover", "run", "done"}

TypeCheckPassedOnlyAfterCompile ==
    passed => stage \in {"type_check", "discover", "run", "done"}

CompiledSubsetValid ==
    \A c \in compiled :
        \E k \in 1..N :
            Verifiers[k].name = c.name /\
            Verifiers[k].is_dict /\
            Verifiers[k].has_cond

TerminalImpliesAllChecked ==
    stage = "done" => passed = TRUE

NoDuplicateNames ==
    \A c1 \in compiled : \A c2 \in compiled :
        c1.name = c2.name => c1 = c2


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
                     ELSE /\ pc' = [pc EXCEPT !["verifier"] = "TypeCheck"]
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

TypeCheck == /\ pc["verifier"] = "TypeCheck"
             /\ stage' = "type_check"
             /\ passed' = TRUE
             /\ pc' = [pc EXCEPT !["verifier"] = "Discover"]
             /\ UNCHANGED << cursor, compiled >>

Discover == /\ pc["verifier"] = "Discover"
            /\ stage' = "discover"
            /\ pc' = [pc EXCEPT !["verifier"] = "Run"]
            /\ UNCHANGED << cursor, compiled, passed >>

Run == /\ pc["verifier"] = "Run"
       /\ stage' = "run"
       /\ pc' = [pc EXCEPT !["verifier"] = "Finish"]
       /\ UNCHANGED << cursor, compiled, passed >>

Finish == /\ pc["verifier"] = "Finish"
          /\ stage' = "done"
          /\ pc' = [pc EXCEPT !["verifier"] = "Done"]
          /\ UNCHANGED << cursor, compiled, passed >>

verifier == CompileAll \/ ProcessLoop \/ ProcessV \/ AdvanceV \/ TypeCheck
               \/ Discover \/ Run \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == verifier
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
