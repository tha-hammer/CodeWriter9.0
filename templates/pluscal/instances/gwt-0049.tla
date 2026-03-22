---- MODULE scanner_typescript_nested_depth ----

EXTENDS Integers, Sequences, FiniteSets, TLC

Events == <<
    [type |-> "ClassOpen", name |-> "A"],
    [type |-> "Method",    name |-> "getUser"],
    [type |-> "CloseBrace", name |-> ""],
    [type |-> "Func",      name |-> "helper"],
    [type |-> "ClassOpen", name |-> "B"],
    [type |-> "Method",    name |-> "save"]
>>
N == 6

(* --algorithm ScannerTSNestedDepth

variables
    cursor      = 1,
    class_stack = << >>,
    brace_depth = 0,
    skeletons   = {};

define
    DepthConsistency ==
        \A s \in skeletons :
            \/ (s.class_name = "None" /\ s.inside_class = FALSE)
            \/ (s.class_name # "None" /\ s.inside_class = TRUE)

    AllFuncsRecorded ==
        cursor > N =>
            \A k \in 1..N :
                Events[k].type \in {"Func", "Method"} =>
                    \E s \in skeletons : s.func_name = Events[k].name

    MethodsHaveClass ==
        \A s \in skeletons :
            s.inside_class = TRUE => s.class_name # "None"

    FuncsOutsideHaveNone ==
        \A s \in skeletons :
            s.inside_class = FALSE => s.class_name = "None"

    StackDepthNonNegative ==
        brace_depth >= 0

    CursorBounded ==
        cursor >= 1 /\ cursor <= N + 1
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
                elsif Events[cursor].type \in {"Func", "Method"} then
                    if Len(class_stack) > 0 then
                        skeletons := skeletons \cup
                            {[func_name    |-> Events[cursor].name,
                              class_name   |-> class_stack[Len(class_stack)].name,
                              inside_class |-> TRUE]};
                    else
                        skeletons := skeletons \cup
                            {[func_name    |-> Events[cursor].name,
                              class_name   |-> "None",
                              inside_class |-> FALSE]};
                    end if;
                    brace_depth := brace_depth + 1;
                end if;
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "ecd60d59" /\ chksum(tla) = "44e4f38d")
VARIABLES pc, cursor, class_stack, brace_depth, skeletons

(* define statement *)
DepthConsistency ==
    \A s \in skeletons :
        \/ (s.class_name = "None" /\ s.inside_class = FALSE)
        \/ (s.class_name # "None" /\ s.inside_class = TRUE)

AllFuncsRecorded ==
    cursor > N =>
        \A k \in 1..N :
            Events[k].type \in {"Func", "Method"} =>
                \E s \in skeletons : s.func_name = Events[k].name

MethodsHaveClass ==
    \A s \in skeletons :
        s.inside_class = TRUE => s.class_name # "None"

FuncsOutsideHaveNone ==
    \A s \in skeletons :
        s.inside_class = FALSE => s.class_name = "None"

StackDepthNonNegative ==
    brace_depth >= 0

CursorBounded ==
    cursor >= 1 /\ cursor <= N + 1


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
                                 ELSE /\ IF Events[cursor].type \in {"Func", "Method"}
                                            THEN /\ IF Len(class_stack) > 0
                                                       THEN /\ skeletons' = (         skeletons \cup
                                                                             {[func_name    |-> Events[cursor].name,
                                                                               class_name   |-> class_stack[Len(class_stack)].name,
                                                                               inside_class |-> TRUE]})
                                                       ELSE /\ skeletons' = (         skeletons \cup
                                                                             {[func_name    |-> Events[cursor].name,
                                                                               class_name   |-> "None",
                                                                               inside_class |-> FALSE]})
                                                 /\ brace_depth' = brace_depth + 1
                                            ELSE /\ TRUE
                                                 /\ UNCHANGED << brace_depth, 
                                                                 skeletons >>
                                      /\ UNCHANGED class_stack
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
