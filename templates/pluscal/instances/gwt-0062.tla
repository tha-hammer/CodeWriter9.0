---- MODULE rust_profile_condition_compile ----

EXTENDS Integers, FiniteSets, TLC

Tokens == <<
    [tla |-> "In",       rs |-> "contains_ref", helper |-> FALSE],
    [tla |-> "And",      rs |-> "ampamp",        helper |-> FALSE],
    [tla |-> "Or",       rs |-> "pipepipe",      helper |-> FALSE],
    [tla |-> "Eq",       rs |-> "doubleEq",      helper |-> FALSE],
    [tla |-> "Neq",      rs |-> "bangEq",        helper |-> FALSE],
    [tla |-> "ForAll",   rs |-> "iter_all",      helper |-> FALSE],
    [tla |-> "Exists",   rs |-> "iter_any",      helper |-> FALSE],
    [tla |-> "Len",      rs |-> "dot_len",       helper |-> FALSE],
    [tla |-> "Card",     rs |-> "dot_len",       helper |-> FALSE],
    [tla |-> "BoolT",    rs |-> "true",          helper |-> FALSE],
    [tla |-> "BoolF",    rs |-> "false",         helper |-> FALSE]
>>
N == 11

(* --algorithm RustConditionCompile

variables
    cursor    = 1,
    results   = {},
    has_error = FALSE;

define
    AllMapped ==
        cursor > N =>
            \A k \in 1..N :
                \E r \in results :
                    /\ r.tla_op = Tokens[k].tla
                    /\ r.rs_op  = Tokens[k].rs

    HelperAlwaysEmpty ==
        \A r \in results : r.helper = FALSE

    ReferenceContains ==
        \A r \in results :
            r.tla_op = "In" => r.rs_op = "contains_ref"

    ClosureSyntax ==
        \A r \in results :
            r.tla_op = "ForAll" => r.rs_op = "iter_all"

    ExistsSyntax ==
        \A r \in results :
            r.tla_op = "Exists" => r.rs_op = "iter_any"

    NoError == ~has_error
end define;

process compiler = "compiler"
begin
    CompileLoop:
        while cursor <= N do
            ProcessToken:
                results := results \cup
                    {[tla_op |-> Tokens[cursor].tla,
                      rs_op  |-> Tokens[cursor].rs,
                      helper |-> Tokens[cursor].helper]};
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "c3064cce" /\ chksum(tla) = "a6f7517e")
VARIABLES pc, cursor, results, has_error

(* define statement *)
AllMapped ==
    cursor > N =>
        \A k \in 1..N :
            \E r \in results :
                /\ r.tla_op = Tokens[k].tla
                /\ r.rs_op  = Tokens[k].rs

HelperAlwaysEmpty ==
    \A r \in results : r.helper = FALSE

ReferenceContains ==
    \A r \in results :
        r.tla_op = "In" => r.rs_op = "contains_ref"

ClosureSyntax ==
    \A r \in results :
        r.tla_op = "ForAll" => r.rs_op = "iter_all"

ExistsSyntax ==
    \A r \in results :
        r.tla_op = "Exists" => r.rs_op = "iter_any"

NoError == ~has_error


vars == << pc, cursor, results, has_error >>

ProcSet == {"compiler"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ results = {}
        /\ has_error = FALSE
        /\ pc = [self \in ProcSet |-> "CompileLoop"]

CompileLoop == /\ pc["compiler"] = "CompileLoop"
               /\ IF cursor <= N
                     THEN /\ pc' = [pc EXCEPT !["compiler"] = "ProcessToken"]
                     ELSE /\ pc' = [pc EXCEPT !["compiler"] = "Finish"]
               /\ UNCHANGED << cursor, results, has_error >>

ProcessToken == /\ pc["compiler"] = "ProcessToken"
                /\ results' = (       results \cup
                               {[tla_op |-> Tokens[cursor].tla,
                                 rs_op  |-> Tokens[cursor].rs,
                                 helper |-> Tokens[cursor].helper]})
                /\ pc' = [pc EXCEPT !["compiler"] = "Advance"]
                /\ UNCHANGED << cursor, has_error >>

Advance == /\ pc["compiler"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["compiler"] = "CompileLoop"]
           /\ UNCHANGED << results, has_error >>

Finish == /\ pc["compiler"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["compiler"] = "Done"]
          /\ UNCHANGED << cursor, results, has_error >>

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
