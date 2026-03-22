---- MODULE scanner_rust_nested_depth ----

EXTENDS Integers, Sequences, FiniteSets, TLC

Events == <<
    [type |-> "ImplOpen",   name |-> "Foo",  is_trait |-> FALSE],
    [type |-> "Fn",         name |-> "bar",  is_trait |-> FALSE],
    [type |-> "CloseBrace", name |-> "",     is_trait |-> FALSE],
    [type |-> "TraitOpen",  name |-> "",     is_trait |-> TRUE],
    [type |-> "Fn",         name |-> "baz",  is_trait |-> FALSE],
    [type |-> "CloseBrace", name |-> "",     is_trait |-> FALSE],
    [type |-> "Fn",         name |-> "free", is_trait |-> FALSE]
>>
N == 7

(* --algorithm ScannerRustNestedDepth

variables
    cursor      = 1,
    block_stack = << >>,
    skeletons   = {};

define
    ImplResolution ==
        \A s \in skeletons :
            \/ (s.class_name = "None")
            \/ (s.class_name # "None")

    TraitExclusion ==
        ~(\E s \in skeletons : s.func_name = "baz")

    AllNonTraitFnsRecorded ==
        cursor > N =>
            /\ \E s \in skeletons : s.func_name = "bar"  /\ s.class_name = "Foo"
            /\ \E s \in skeletons : s.func_name = "free" /\ s.class_name = "None"
            /\ ~\E s \in skeletons : s.func_name = "baz"
end define;

process scanner = "scanner"
begin
    ScanLoop:
        while cursor <= N do
            ProcessEvent:
                if Events[cursor].type = "ImplOpen" then
                    block_stack := Append(block_stack,
                        [name |-> Events[cursor].name, is_trait |-> FALSE]);
                elsif Events[cursor].type = "TraitOpen" then
                    block_stack := Append(block_stack,
                        [name |-> "None", is_trait |-> TRUE]);
                elsif Events[cursor].type = "CloseBrace" then
                    if Len(block_stack) > 0 then
                        block_stack := SubSeq(block_stack, 1, Len(block_stack) - 1);
                    end if;
                elsif Events[cursor].type = "Fn" then
                    if Len(block_stack) > 0 /\ block_stack[Len(block_stack)].is_trait then
                        skip;
                    elsif Len(block_stack) > 0 then
                        skeletons := skeletons \cup
                            {[func_name  |-> Events[cursor].name,
                              class_name |-> block_stack[Len(block_stack)].name]};
                    else
                        skeletons := skeletons \cup
                            {[func_name  |-> Events[cursor].name,
                              class_name |-> "None"]};
                    end if;
                end if;
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "58028195" /\ chksum(tla) = "38b8d91e")
VARIABLES pc, cursor, block_stack, skeletons

(* define statement *)
ImplResolution ==
    \A s \in skeletons :
        \/ (s.class_name = "None")
        \/ (s.class_name # "None")

TraitExclusion ==
    ~(\E s \in skeletons : s.func_name = "baz")

AllNonTraitFnsRecorded ==
    cursor > N =>
        /\ \E s \in skeletons : s.func_name = "bar"  /\ s.class_name = "Foo"
        /\ \E s \in skeletons : s.func_name = "free" /\ s.class_name = "None"
        /\ ~\E s \in skeletons : s.func_name = "baz"


vars == << pc, cursor, block_stack, skeletons >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ block_stack = << >>
        /\ skeletons = {}
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF cursor <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessEvent"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << cursor, block_stack, skeletons >>

ProcessEvent == /\ pc["scanner"] = "ProcessEvent"
                /\ IF Events[cursor].type = "ImplOpen"
                      THEN /\ block_stack' =            Append(block_stack,
                                             [name |-> Events[cursor].name, is_trait |-> FALSE])
                           /\ UNCHANGED skeletons
                      ELSE /\ IF Events[cursor].type = "TraitOpen"
                                 THEN /\ block_stack' =            Append(block_stack,
                                                        [name |-> "None", is_trait |-> TRUE])
                                      /\ UNCHANGED skeletons
                                 ELSE /\ IF Events[cursor].type = "CloseBrace"
                                            THEN /\ IF Len(block_stack) > 0
                                                       THEN /\ block_stack' = SubSeq(block_stack, 1, Len(block_stack) - 1)
                                                       ELSE /\ TRUE
                                                            /\ UNCHANGED block_stack
                                                 /\ UNCHANGED skeletons
                                            ELSE /\ IF Events[cursor].type = "Fn"
                                                       THEN /\ IF Len(block_stack) > 0 /\ block_stack[Len(block_stack)].is_trait
                                                                  THEN /\ TRUE
                                                                       /\ UNCHANGED skeletons
                                                                  ELSE /\ IF Len(block_stack) > 0
                                                                             THEN /\ skeletons' = (         skeletons \cup
                                                                                                   {[func_name  |-> Events[cursor].name,
                                                                                                     class_name |-> block_stack[Len(block_stack)].name]})
                                                                             ELSE /\ skeletons' = (         skeletons \cup
                                                                                                   {[func_name  |-> Events[cursor].name,
                                                                                                     class_name |-> "None"]})
                                                       ELSE /\ TRUE
                                                            /\ UNCHANGED skeletons
                                                 /\ UNCHANGED block_stack
                /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
                /\ UNCHANGED cursor

Advance == /\ pc["scanner"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << block_stack, skeletons >>

Finish == /\ pc["scanner"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << cursor, block_stack, skeletons >>

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
