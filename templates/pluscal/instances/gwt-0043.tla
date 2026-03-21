---- MODULE ValidateDependsOn ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    AllUUIDs,
    DependsOnInput,
    MaxSteps

(* --algorithm ValidateDependsOn

variables
    remaining         = DependsOnInput,
    depends_on_output = {},
    warnings          = 0,
    exception_raised  = FALSE,
    step_count        = 0;

define

    OutputSubsetOfAll ==
        \A u \in depends_on_output : u \in AllUUIDs

    NoExceptionRaised ==
        exception_raised = FALSE

    BoundedExecution ==
        step_count <= MaxSteps

    NoInvalidSurvives ==
        \A u \in depends_on_output : u \in AllUUIDs /\ u \in DependsOnInput

    ProcessedValidRetained ==
        \A u \in DependsOnInput :
            u \notin remaining =>
                (u \in AllUUIDs => u \in depends_on_output)

    ProcessedInvalidExcluded ==
        \A u \in DependsOnInput :
            u \notin remaining =>
                (u \notin AllUUIDs => u \notin depends_on_output)

    TerminalOutputCorrect ==
        (remaining = {}) =>
            \A u \in DependsOnInput :
                (u \in AllUUIDs  => u \in depends_on_output) /\
                (u \notin AllUUIDs => u \notin depends_on_output)

    TerminalCondition ==
        (remaining = {}) =>
            \A u \in depends_on_output : u \in AllUUIDs

    WarningsNotExceptions ==
        exception_raised = FALSE

end define;

fair process validator = "validator"
begin
    Validate:
        while remaining # {} /\ step_count < MaxSteps do
            with uuid \in remaining do
                remaining := remaining \ {uuid};
                if uuid \in AllUUIDs then
                    depends_on_output := depends_on_output \cup {uuid};
                else
                    warnings := warnings + 1;
                end if;
            end with;
            step_count := step_count + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f38ba872" /\ chksum(tla) = "568368dd")
VARIABLES pc, remaining, depends_on_output, warnings, exception_raised, 
          step_count

(* define statement *)
OutputSubsetOfAll ==
    \A u \in depends_on_output : u \in AllUUIDs

NoExceptionRaised ==
    exception_raised = FALSE

BoundedExecution ==
    step_count <= MaxSteps

NoInvalidSurvives ==
    \A u \in depends_on_output : u \in AllUUIDs /\ u \in DependsOnInput

ProcessedValidRetained ==
    \A u \in DependsOnInput :
        u \notin remaining =>
            (u \in AllUUIDs => u \in depends_on_output)

ProcessedInvalidExcluded ==
    \A u \in DependsOnInput :
        u \notin remaining =>
            (u \notin AllUUIDs => u \notin depends_on_output)

TerminalOutputCorrect ==
    (remaining = {}) =>
        \A u \in DependsOnInput :
            (u \in AllUUIDs  => u \in depends_on_output) /\
            (u \notin AllUUIDs => u \notin depends_on_output)

TerminalCondition ==
    (remaining = {}) =>
        \A u \in depends_on_output : u \in AllUUIDs

WarningsNotExceptions ==
    exception_raised = FALSE


vars == << pc, remaining, depends_on_output, warnings, exception_raised, 
           step_count >>

ProcSet == {"validator"}

Init == (* Global variables *)
        /\ remaining = DependsOnInput
        /\ depends_on_output = {}
        /\ warnings = 0
        /\ exception_raised = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "Validate"]

Validate == /\ pc["validator"] = "Validate"
            /\ IF remaining # {} /\ step_count < MaxSteps
                  THEN /\ \E uuid \in remaining:
                            /\ remaining' = remaining \ {uuid}
                            /\ IF uuid \in AllUUIDs
                                  THEN /\ depends_on_output' = (depends_on_output \cup {uuid})
                                       /\ UNCHANGED warnings
                                  ELSE /\ warnings' = warnings + 1
                                       /\ UNCHANGED depends_on_output
                       /\ step_count' = step_count + 1
                       /\ pc' = [pc EXCEPT !["validator"] = "Validate"]
                  ELSE /\ pc' = [pc EXCEPT !["validator"] = "Finish"]
                       /\ UNCHANGED << remaining, depends_on_output, warnings, 
                                       step_count >>
            /\ UNCHANGED exception_raised

Finish == /\ pc["validator"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["validator"] = "Done"]
          /\ UNCHANGED << remaining, depends_on_output, warnings, 
                          exception_raised, step_count >>

validator == Validate \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == validator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(validator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
