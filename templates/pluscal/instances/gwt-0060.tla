---- MODULE go_profile_condition_compile ----

EXTENDS Integers, FiniteSets, TLC

Tokens == <<
    [tla |-> "In",       go_op |-> "slicesContains", needs_helper |-> FALSE],
    [tla |-> "And",      go_op |-> "ampamp",         needs_helper |-> FALSE],
    [tla |-> "Or",       go_op |-> "pipepipe",       needs_helper |-> FALSE],
    [tla |-> "Eq",       go_op |-> "doubleEq",       needs_helper |-> FALSE],
    [tla |-> "Neq",      go_op |-> "bangEq",         needs_helper |-> FALSE],
    [tla |-> "ForAll",   go_op |-> "allSatisfy",     needs_helper |-> TRUE],
    [tla |-> "Exists",   go_op |-> "anySatisfy",     needs_helper |-> TRUE],
    [tla |-> "Len",      go_op |-> "len",            needs_helper |-> FALSE],
    [tla |-> "Card",     go_op |-> "len",            needs_helper |-> FALSE],
    [tla |-> "BoolT",    go_op |-> "true",           needs_helper |-> FALSE],
    [tla |-> "BoolF",    go_op |-> "false",          needs_helper |-> FALSE]
>>
N == 11

(* --algorithm GoConditionCompile

variables
    cursor      = 1,
    results     = {},
    has_helper  = FALSE,
    has_error   = FALSE;

define
    AllMapped ==
        cursor > N =>
            \A k \in 1..N :
                \E r \in results :
                    /\ r.tla_op = Tokens[k].tla
                    /\ r.go_op  = Tokens[k].go_op

    HelperEmitted ==
        (\E r \in results : r.needs_helper) => has_helper

    NoQuantifierNoHelper ==
        (~\E r \in results : r.needs_helper) => ~has_helper

    NoError == ~has_error
end define;

process compiler = "compiler"
begin
    CompileLoop:
        while cursor <= N do
            ProcessToken:
                results := results \cup
                    {[tla_op       |-> Tokens[cursor].tla,
                      go_op        |-> Tokens[cursor].go_op,
                      needs_helper |-> Tokens[cursor].needs_helper]};
                if Tokens[cursor].needs_helper then
                    has_helper := TRUE;
                end if;
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "648ed901" /\ chksum(tla) = "fe55c917")
VARIABLES pc, cursor, results, has_helper, has_error

(* define statement *)
AllMapped ==
    cursor > N =>
        \A k \in 1..N :
            \E r \in results :
                /\ r.tla_op = Tokens[k].tla
                /\ r.go_op  = Tokens[k].go_op

HelperEmitted ==
    (\E r \in results : r.needs_helper) => has_helper

NoQuantifierNoHelper ==
    (~\E r \in results : r.needs_helper) => ~has_helper

NoError == ~has_error


vars == << pc, cursor, results, has_helper, has_error >>

ProcSet == {"compiler"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ results = {}
        /\ has_helper = FALSE
        /\ has_error = FALSE
        /\ pc = [self \in ProcSet |-> "CompileLoop"]

CompileLoop == /\ pc["compiler"] = "CompileLoop"
               /\ IF cursor <= N
                     THEN /\ pc' = [pc EXCEPT !["compiler"] = "ProcessToken"]
                     ELSE /\ pc' = [pc EXCEPT !["compiler"] = "Finish"]
               /\ UNCHANGED << cursor, results, has_helper, has_error >>

ProcessToken == /\ pc["compiler"] = "ProcessToken"
                /\ results' = (       results \cup
                               {[tla_op       |-> Tokens[cursor].tla,
                                 go_op        |-> Tokens[cursor].go_op,
                                 needs_helper |-> Tokens[cursor].needs_helper]})
                /\ IF Tokens[cursor].needs_helper
                      THEN /\ has_helper' = TRUE
                      ELSE /\ TRUE
                           /\ UNCHANGED has_helper
                /\ pc' = [pc EXCEPT !["compiler"] = "Advance"]
                /\ UNCHANGED << cursor, has_error >>

Advance == /\ pc["compiler"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["compiler"] = "CompileLoop"]
           /\ UNCHANGED << results, has_helper, has_error >>

Finish == /\ pc["compiler"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["compiler"] = "Done"]
          /\ UNCHANGED << cursor, results, has_helper, has_error >>

compiler == CompileLoop \/ ProcessToken \/ Advance \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == compiler
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
