---- MODULE python_profile_condition_compile ----

EXTENDS Integers, FiniteSets, TLC

Tokens == <<
    [tla |-> "In",       py |-> "in"],
    [tla |-> "And",      py |-> "and"],
    [tla |-> "Or",       py |-> "or"],
    [tla |-> "Eq",       py |-> "eq"],
    [tla |-> "Neq",      py |-> "neq"],
    [tla |-> "ForAll",   py |-> "all"],
    [tla |-> "Exists",   py |-> "any"],
    [tla |-> "Len",      py |-> "len"],
    [tla |-> "Card",     py |-> "len"],
    [tla |-> "BoolT",    py |-> "True"],
    [tla |-> "BoolF",    py |-> "False"]
>>

N == 11

(* --algorithm PythonConditionCompile

variables
    cursor     = 1,
    results    = {},
    has_error  = FALSE;

define
    AllMapped ==
        cursor > N =>
            \A k \in 1..N :
                \E r \in results :
                    /\ r.tla_op = Tokens[k].tla
                    /\ r.py_op  = Tokens[k].py

    OriginalPreserved ==
        \A r \in results : r.tla_op # ""

    NoError ==
        ~has_error

    QuantifierBeforeIn ==
        TRUE
end define;

process compiler = "compiler"
begin
    CompileLoop:
        while cursor <= N do
            ProcessToken:
                results := results \cup
                    {[tla_op |-> Tokens[cursor].tla,
                      py_op  |-> Tokens[cursor].py]};
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "c97859c3" /\ chksum(tla) = "6448251a")
VARIABLES pc, cursor, results, has_error

(* define statement *)
AllMapped ==
    cursor > N =>
        \A k \in 1..N :
            \E r \in results :
                /\ r.tla_op = Tokens[k].tla
                /\ r.py_op  = Tokens[k].py

OriginalPreserved ==
    \A r \in results : r.tla_op # ""

NoError ==
    ~has_error

QuantifierBeforeIn ==
    TRUE


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
                                 py_op  |-> Tokens[cursor].py]})
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
