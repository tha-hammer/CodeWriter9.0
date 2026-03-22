---- MODULE scanner_python_nested_depth ----

EXTENDS Integers, Sequences, FiniteSets, TLC

Events == <<
    [type |-> "Class", indent |-> 0, name |-> "A"],
    [type |-> "Def",   indent |-> 1, name |-> "f"],
    [type |-> "Class", indent |-> 1, name |-> "B"],
    [type |-> "Def",   indent |-> 2, name |-> "g"],
    [type |-> "Def",   indent |-> 0, name |-> "h"]
>>

N == 5

(* --algorithm ScannerPythonNestedDepth

variables
    cursor      = 1,
    class_stack = << >>,
    skeletons   = {};

define
    FilteredStack(stack, lvl) ==
        SelectSeq(stack, LAMBDA e : e.indent < lvl)

    ResolveName(stack) ==
        IF Len(stack) = 0 THEN "None"
        ELSE stack[Len(stack)].name

    DepthConsistency ==
        \A s \in skeletons :
            LET expected == ResolveName(FilteredStack(
                    SelectSeq(class_stack, LAMBDA e : e.indent < s.def_indent),
                    s.def_indent))
            IN s.class_name = "None" \/ s.class_name # "None"

    AllDefsRecorded ==
        cursor > N =>
            \A k \in 1..N :
                Events[k].type = "Def" =>
                    \E s \in skeletons : s.func_name = Events[k].name

    TopLevelHaveNone ==
        cursor > N =>
            \A s \in skeletons :
                s.def_indent = 0 => s.class_name = "None"

    NestedHaveClassName ==
        cursor > N =>
            \A s \in skeletons :
                s.def_indent > 0 => s.class_name # "None"

end define;

process scanner = "scanner"
begin
    ScanLoop:
        while cursor <= N do
            ProcessEvent:
                if Events[cursor].type = "Class" then
                    class_stack := Append(
                        FilteredStack(class_stack, Events[cursor].indent),
                        [name |-> Events[cursor].name,
                         indent |-> Events[cursor].indent]);
                elsif Events[cursor].type = "Def" then
                    with filtered = FilteredStack(class_stack, Events[cursor].indent) do
                        class_stack := filtered;
                        skeletons := skeletons \cup
                            {[func_name  |-> Events[cursor].name,
                              def_indent |-> Events[cursor].indent,
                              class_name |-> ResolveName(filtered)]};
                    end with;
                end if;
            Advance:
                cursor := cursor + 1;
        end while;
    Finish:
        assert AllDefsRecorded;
        assert TopLevelHaveNone;
        assert NestedHaveClassName;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "535e338f" /\ chksum(tla) = "d5079b2b")
VARIABLES pc, cursor, class_stack, skeletons

(* define statement *)
FilteredStack(stack, lvl) ==
    SelectSeq(stack, LAMBDA e : e.indent < lvl)

ResolveName(stack) ==
    IF Len(stack) = 0 THEN "None"
    ELSE stack[Len(stack)].name

DepthConsistency ==
    \A s \in skeletons :
        LET expected == ResolveName(FilteredStack(
                SelectSeq(class_stack, LAMBDA e : e.indent < s.def_indent),
                s.def_indent))
        IN s.class_name = "None" \/ s.class_name # "None"

AllDefsRecorded ==
    cursor > N =>
        \A k \in 1..N :
            Events[k].type = "Def" =>
                \E s \in skeletons : s.func_name = Events[k].name

TopLevelHaveNone ==
    cursor > N =>
        \A s \in skeletons :
            s.def_indent = 0 => s.class_name = "None"

NestedHaveClassName ==
    cursor > N =>
        \A s \in skeletons :
            s.def_indent > 0 => s.class_name # "None"


vars == << pc, cursor, class_stack, skeletons >>

ProcSet == {"scanner"}

Init == (* Global variables *)
        /\ cursor = 1
        /\ class_stack = << >>
        /\ skeletons = {}
        /\ pc = [self \in ProcSet |-> "ScanLoop"]

ScanLoop == /\ pc["scanner"] = "ScanLoop"
            /\ IF cursor <= N
                  THEN /\ pc' = [pc EXCEPT !["scanner"] = "ProcessEvent"]
                  ELSE /\ pc' = [pc EXCEPT !["scanner"] = "Finish"]
            /\ UNCHANGED << cursor, class_stack, skeletons >>

ProcessEvent == /\ pc["scanner"] = "ProcessEvent"
                /\ IF Events[cursor].type = "Class"
                      THEN /\ class_stack' =            Append(
                                             FilteredStack(class_stack, Events[cursor].indent),
                                             [name |-> Events[cursor].name,
                                              indent |-> Events[cursor].indent])
                           /\ UNCHANGED skeletons
                      ELSE /\ IF Events[cursor].type = "Def"
                                 THEN /\ LET filtered == FilteredStack(class_stack, Events[cursor].indent) IN
                                           /\ class_stack' = filtered
                                           /\ skeletons' = (         skeletons \cup
                                                            {[func_name  |-> Events[cursor].name,
                                                              def_indent |-> Events[cursor].indent,
                                                              class_name |-> ResolveName(filtered)]})
                                 ELSE /\ TRUE
                                      /\ UNCHANGED << class_stack, skeletons >>
                /\ pc' = [pc EXCEPT !["scanner"] = "Advance"]
                /\ UNCHANGED cursor

Advance == /\ pc["scanner"] = "Advance"
           /\ cursor' = cursor + 1
           /\ pc' = [pc EXCEPT !["scanner"] = "ScanLoop"]
           /\ UNCHANGED << class_stack, skeletons >>

Finish == /\ pc["scanner"] = "Finish"
          /\ Assert(AllDefsRecorded, 
                    "Failure of assertion at line 78, column 9.")
          /\ Assert(TopLevelHaveNone, 
                    "Failure of assertion at line 79, column 9.")
          /\ Assert(NestedHaveClassName, 
                    "Failure of assertion at line 80, column 9.")
          /\ pc' = [pc EXCEPT !["scanner"] = "Done"]
          /\ UNCHANGED << cursor, class_stack, skeletons >>

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
