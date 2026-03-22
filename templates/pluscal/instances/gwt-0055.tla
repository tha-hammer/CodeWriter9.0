---- MODULE scanner_javascript_nested_depth ----

EXTENDS Integers, Sequences, FiniteSets, TLC

Events == <<
    [type |-> "ClassOpen",   name |-> "A",           vis |-> "public"],
    [type |-> "Method",      name |-> "getData",      vis |-> "public"],
    [type |-> "Method",      name |-> "#secret",      vis |-> "private"],
    [type |-> "Constructor", name |-> "constructor",  vis |-> "public"],
    [type |-> "CloseBrace",  name |-> "",             vis |-> "public"],
    [type |-> "Func",        name |-> "helper",       vis |-> "public"]
>>
N == 6

(* --algorithm ScannerJSNestedDepth

variables
    cursor      = 1,
    class_stack = << >>,
    brace_depth = 0,
    skeletons   = {};

define
    DepthConsistency ==
        \A s \in skeletons :
            \/ (s.class_name = "None")
            \/ (s.class_name # "None")

    ConstructorExclusion ==
        ~(\E s \in skeletons : s.func_name = "constructor")

    HashPrivate ==
        \A s \in skeletons :
            (s.func_name = "#secret") => (s.visibility = "private")

    PublicDefault ==
        \A s \in skeletons :
            (s.func_name # "#secret") => (s.visibility = "public")

    ReturnTypeNone ==
        \A s \in skeletons : s.return_type = "None"

    ExpectedResults ==
        cursor > N =>
            /\ \E s \in skeletons : s.func_name = "getData" /\ s.class_name = "A"    /\ s.visibility = "public"
            /\ \E s \in skeletons : s.func_name = "#secret" /\ s.class_name = "A"    /\ s.visibility = "private"
            /\ \E s \in skeletons : s.func_name = "helper"  /\ s.class_name = "None" /\ s.visibility = "public"
            /\ ~(\E s \in skeletons : s.func_name = "constructor")

end define;

process scanner = "scanner"
begin
    ScanLoop:
        while cursor <= N do
            ProcessEvent:
                if Events[cursor].type = "ClassOpen" then
                    class_stack := Append(class_stack,
                        [name |-> Events[cursor].name, depth |-> brace_depth]);
                    brace_depth := brace_depth + 1;
                elsif Events[cursor].type = "CloseBrace" then
                    brace_depth := brace_depth - 1;
                    if Len(class_stack) > 0 /\ brace_depth <= class_stack[Len(class_stack)].depth then
                        class_stack := SubSeq(class_stack, 1, Len(class_stack) - 1);
                    end if;
                elsif Events[cursor].type = "Constructor" then
                    skip;
                elsif Events[cursor].type \in {"Func", "Method"} then
                    if Len(class_stack) > 0 then
                        skeletons := skeletons \cup
                            {[func_name   |-> Events[cursor].name,
                              class_name  |-> class_stack[Len(class_stack)].name,
                              visibility  |-> Events[cursor].vis,
                              return_type |-> "None"]};
                    else
                        skeletons := skeletons \cup
                            {[func_name   |-> Events[cursor].name,
                              class_name  |-> "None",
                              visibility  |-> Events[cursor].vis,
                              return_type |-> "None"]};
                    end if;
                end if;
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3bf10ad7" /\ chksum(tla) = "b797798")
VARIABLES pc, cursor, class_stack, brace_depth, skeletons

(* define statement *)
DepthConsistency ==
    \A s \in skeletons :
        \/ (s.class_name = "None")
        \/ (s.class_name # "None")

ConstructorExclusion ==
    ~(\E s \in skeletons : s.func_name = "constructor")

HashPrivate ==
    \A s \in skeletons :
        (s.func_name = "#secret") => (s.visibility = "private")

PublicDefault ==
    \A s \in skeletons :
        (s.func_name # "#secret") => (s.visibility = "public")

ReturnTypeNone ==
    \A s \in skeletons : s.return_type = "None"

ExpectedResults ==
    cursor > N =>
        /\ \E s \in skeletons : s.func_name = "getData" /\ s.class_name = "A"    /\ s.visibility = "public"
        /\ \E s \in skeletons : s.func_name = "#secret" /\ s.class_name = "A"    /\ s.visibility = "private"
        /\ \E s \in skeletons : s.func_name = "helper"  /\ s.class_name = "None" /\ s.visibility = "public"
        /\ ~(\E s \in skeletons : s.func_name = "constructor")


vars == << pc, cursor, class_stack, brace_depth, skeletons >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ class_stack = << >>
        /\ brace_depth = 0
        /\ skeletons = {}
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF cursor <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessEvent"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << cursor, class_stack, brace_depth, skeletons >>

ProcessEvent == /\ pc["scanner"] = "ProcessEvent"
                /\ IF Events[cursor].type = "ClassOpen"
                      THEN /\ class_stack' =            Append(class_stack,
                                             [name |-> Events[cursor].name, depth |-> brace_depth])
                           /\ brace_depth' = brace_depth + 1
                           /\ UNCHANGED skeletons
                      ELSE /\ IF Events[cursor].type = "CloseBrace"
                                 THEN /\ brace_depth' = brace_depth - 1
                                      /\ IF Len(class_stack) > 0 /\ brace_depth' <= class_stack[Len(class_stack)].depth
                                            THEN /\ class_stack' = SubSeq(class_stack, 1, Len(class_stack) - 1)
                                            ELSE /\ TRUE
                                                 /\ UNCHANGED class_stack
                                      /\ UNCHANGED skeletons
                                 ELSE /\ IF Events[cursor].type = "Constructor"
                                            THEN /\ TRUE
                                                 /\ UNCHANGED skeletons
                                            ELSE /\ IF Events[cursor].type \in {"Func", "Method"}
                                                       THEN /\ IF Len(class_stack) > 0
                                                                  THEN /\ skeletons' = (         skeletons \cup
                                                                                        {[func_name   |-> Events[cursor].name,
                                                                                          class_name  |-> class_stack[Len(class_stack)].name,
                                                                                          visibility  |-> Events[cursor].vis,
                                                                                          return_type |-> "None"]})
                                                                  ELSE /\ skeletons' = (         skeletons \cup
                                                                                        {[func_name   |-> Events[cursor].name,
                                                                                          class_name  |-> "None",
                                                                                          visibility  |-> Events[cursor].vis,
                                                                                          return_type |-> "None"]})
                                                       ELSE /\ TRUE
                                                            /\ UNCHANGED skeletons
                                      /\ UNCHANGED << class_stack, brace_depth >>
                /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
                /\ UNCHANGED cursor

Advance == /\ pc["scanner"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << class_stack, brace_depth, skeletons >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << cursor, class_stack, brace_depth, skeletons >>

scanner == ScanLoop \/ ProcessEvent \/ Advance \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == scanner
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
