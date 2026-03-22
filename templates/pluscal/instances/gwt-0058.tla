---- MODULE typescript_profile_condition_compile ----

EXTENDS Integers, FiniteSets, TLC

Tokens == <<
    [tla |-> "In",       ts |-> "includes"],
    [tla |-> "And",      ts |-> "ampamp"],
    [tla |-> "Or",       ts |-> "pipepipe"],
    [tla |-> "Eq",       ts |-> "tripleEq"],
    [tla |-> "Neq",      ts |-> "bangEqEq"],
    [tla |-> "ForAll",   ts |-> "every"],
    [tla |-> "Exists",   ts |-> "some"],
    [tla |-> "Len",      ts |-> "length"],
    [tla |-> "Card",     ts |-> "size"],
    [tla |-> "BoolT",    ts |-> "true"],
    [tla |-> "BoolF",    ts |-> "false"]
>>
N == 11

(* --algorithm TSConditionCompile

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
                    /\ r.ts_op  = Tokens[k].ts

    StrictEquality ==
        \A r \in results :
            r.tla_op = "Eq" => r.ts_op = "tripleEq"

    StrictInequality ==
        \A r \in results :
            r.tla_op = "Neq" => r.ts_op = "bangEqEq"

    SetMembershipMapped ==
        \A r \in results :
            r.tla_op = "In" => r.ts_op = "includes"

    ForAllMapped ==
        \A r \in results :
            r.tla_op = "ForAll" => r.ts_op = "every"

    ExistsMapped ==
        \A r \in results :
            r.tla_op = "Exists" => r.ts_op = "some"

    NoError == ~has_error

    MappingsAreCorrect ==
        \A r \in results :
            \E k \in 1..N :
                /\ r.tla_op = Tokens[k].tla
                /\ r.ts_op  = Tokens[k].ts

end define;

process compiler = "compiler"
begin
    CompileLoop:
        while cursor <= N do
            ProcessToken:
                results := results \cup
                    {[tla_op |-> Tokens[cursor].tla,
                      ts_op  |-> Tokens[cursor].ts]};
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        assert AllMapped;
        assert StrictEquality;
        assert StrictInequality;
        assert SetMembershipMapped;
        assert ForAllMapped;
        assert ExistsMapped;
        assert NoError;
        assert MappingsAreCorrect;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "84b990b4" /\ chksum(tla) = "ed4b8d0f")
VARIABLES pc, cursor, results, has_error

(* define statement *)
AllMapped ==
    cursor > N =>
        \A k \in 1..N :
            \E r \in results :
                /\ r.tla_op = Tokens[k].tla
                /\ r.ts_op  = Tokens[k].ts

StrictEquality ==
    \A r \in results :
        r.tla_op = "Eq" => r.ts_op = "tripleEq"

StrictInequality ==
    \A r \in results :
        r.tla_op = "Neq" => r.ts_op = "bangEqEq"

SetMembershipMapped ==
    \A r \in results :
        r.tla_op = "In" => r.ts_op = "includes"

ForAllMapped ==
    \A r \in results :
        r.tla_op = "ForAll" => r.ts_op = "every"

ExistsMapped ==
    \A r \in results :
        r.tla_op = "Exists" => r.ts_op = "some"

NoError == ~has_error

MappingsAreCorrect ==
    \A r \in results :
        \E k \in 1..N :
            /\ r.tla_op = Tokens[k].tla
            /\ r.ts_op  = Tokens[k].ts


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
                                 ts_op  |-> Tokens[cursor].ts]})
                /\ pc' = [pc EXCEPT !["compiler"] = "Advance"]
                /\ UNCHANGED << cursor, has_error >>

Advance == /\ pc["compiler"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["compiler"] = "CompileLoop"]
           /\ UNCHANGED << results, has_error >>

Finish == /\ pc["compiler"] = "Finish"
          /\ Assert(AllMapped, "Failure of assertion at line 77, column 9.")
          /\ Assert(StrictEquality, 
                    "Failure of assertion at line 78, column 9.")
          /\ Assert(StrictInequality, 
                    "Failure of assertion at line 79, column 9.")
          /\ Assert(SetMembershipMapped, 
                    "Failure of assertion at line 80, column 9.")
          /\ Assert(ForAllMapped, 
                    "Failure of assertion at line 81, column 9.")
          /\ Assert(ExistsMapped, 
                    "Failure of assertion at line 82, column 9.")
          /\ Assert(NoError, "Failure of assertion at line 83, column 9.")
          /\ Assert(MappingsAreCorrect, 
                    "Failure of assertion at line 84, column 9.")
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
