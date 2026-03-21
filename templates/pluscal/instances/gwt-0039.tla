---- MODULE RetryPromptBuilder ----

EXTENDS FiniteSets, TLC

ErrorClasses == {
    "syntax_error", "parse_error", "type_error",
    "invariant_violation", "deadlock", "constant_mismatch",
    "timeout", "unknown"
}

InstructionClasses == {
    "syntax_error", "parse_error", "type_error",
    "invariant_violation", "deadlock", "constant_mismatch"
}

PromptSectionUniverse == {
    "initial_prompt", "retry_header", "classification",
    "previous_output", "error_message", "counterexample",
    "tlc_output", "closing"
}

RequiredCoreSections == {
    "initial_prompt", "retry_header",
    "previous_output", "error_message",
    "tlc_output", "closing"
}

Phases == {"building", "complete"}

(* --algorithm RetryPromptBuilder

variables
    error_class \in ErrorClasses,
    has_counterexample \in {TRUE, FALSE},
    prompt_sections = {},
    phase = "building";

define
    TypeOK ==
        /\ error_class \in ErrorClasses
        /\ has_counterexample \in {TRUE, FALSE}
        /\ prompt_sections \subseteq PromptSectionUniverse
        /\ phase \in Phases

    RequiredSectionsPresent ==
        phase = "complete" =>
            RequiredCoreSections \subseteq prompt_sections

    InitialPromptAlwaysPresent ==
        phase = "complete" =>
            "initial_prompt" \in prompt_sections

    PreviousOutputAlwaysPresent ==
        phase = "complete" =>
            "previous_output" \in prompt_sections

    ClassificationIncludedWhenExpected ==
        (phase = "complete" /\ error_class \in InstructionClasses) =>
            "classification" \in prompt_sections

    ClassificationOmittedWhenNoInstruction ==
        (phase = "complete" /\ error_class \notin InstructionClasses) =>
            "classification" \notin prompt_sections

    CounterexampleIncludedWhenPresent ==
        (phase = "complete" /\ has_counterexample = TRUE) =>
            "counterexample" \in prompt_sections

    CounterexampleOmittedWhenAbsent ==
        (phase = "complete" /\ has_counterexample = FALSE) =>
            "counterexample" \notin prompt_sections

    GWTThenCondition ==
        (phase = "complete" /\ error_class \in InstructionClasses) =>
            /\ "classification" \in prompt_sections
            /\ "previous_output" \in prompt_sections
            /\ "initial_prompt" \in prompt_sections

    OnlyKnownSections ==
        prompt_sections \subseteq PromptSectionUniverse

end define;

fair process builder = "main"
begin
    AddInitialPrompt:
        prompt_sections := prompt_sections \union {"initial_prompt"};

    AddRetryHeader:
        prompt_sections := prompt_sections \union {"retry_header"};

    AddClassification:
        if error_class \in InstructionClasses then
            prompt_sections := prompt_sections \union {"classification"};
        end if;

    AddPreviousOutput:
        prompt_sections := prompt_sections \union {"previous_output"};

    AddErrorMessage:
        prompt_sections := prompt_sections \union {"error_message"};

    AddCounterexample:
        if has_counterexample = TRUE then
            prompt_sections := prompt_sections \union {"counterexample"};
        end if;

    AddTLCOutput:
        prompt_sections := prompt_sections \union {"tlc_output"};

    AddClosing:
        prompt_sections := prompt_sections \union {"closing"};

    Finish:
        phase := "complete";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "cb709816" /\ chksum(tla) = "29407c68")
VARIABLES pc, error_class, has_counterexample, prompt_sections, phase

(* define statement *)
TypeOK ==
    /\ error_class \in ErrorClasses
    /\ has_counterexample \in {TRUE, FALSE}
    /\ prompt_sections \subseteq PromptSectionUniverse
    /\ phase \in Phases

RequiredSectionsPresent ==
    phase = "complete" =>
        RequiredCoreSections \subseteq prompt_sections

InitialPromptAlwaysPresent ==
    phase = "complete" =>
        "initial_prompt" \in prompt_sections

PreviousOutputAlwaysPresent ==
    phase = "complete" =>
        "previous_output" \in prompt_sections

ClassificationIncludedWhenExpected ==
    (phase = "complete" /\ error_class \in InstructionClasses) =>
        "classification" \in prompt_sections

ClassificationOmittedWhenNoInstruction ==
    (phase = "complete" /\ error_class \notin InstructionClasses) =>
        "classification" \notin prompt_sections

CounterexampleIncludedWhenPresent ==
    (phase = "complete" /\ has_counterexample = TRUE) =>
        "counterexample" \in prompt_sections

CounterexampleOmittedWhenAbsent ==
    (phase = "complete" /\ has_counterexample = FALSE) =>
        "counterexample" \notin prompt_sections

GWTThenCondition ==
    (phase = "complete" /\ error_class \in InstructionClasses) =>
        /\ "classification" \in prompt_sections
        /\ "previous_output" \in prompt_sections
        /\ "initial_prompt" \in prompt_sections

OnlyKnownSections ==
    prompt_sections \subseteq PromptSectionUniverse


vars == << pc, error_class, has_counterexample, prompt_sections, phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ error_class \in ErrorClasses
        /\ has_counterexample \in {TRUE, FALSE}
        /\ prompt_sections = {}
        /\ phase = "building"
        /\ pc = [self \in ProcSet |-> "AddInitialPrompt"]

AddInitialPrompt == /\ pc["main"] = "AddInitialPrompt"
                    /\ prompt_sections' = (prompt_sections \union {"initial_prompt"})
                    /\ pc' = [pc EXCEPT !["main"] = "AddRetryHeader"]
                    /\ UNCHANGED << error_class, has_counterexample, phase >>

AddRetryHeader == /\ pc["main"] = "AddRetryHeader"
                  /\ prompt_sections' = (prompt_sections \union {"retry_header"})
                  /\ pc' = [pc EXCEPT !["main"] = "AddClassification"]
                  /\ UNCHANGED << error_class, has_counterexample, phase >>

AddClassification == /\ pc["main"] = "AddClassification"
                     /\ IF error_class \in InstructionClasses
                           THEN /\ prompt_sections' = (prompt_sections \union {"classification"})
                           ELSE /\ TRUE
                                /\ UNCHANGED prompt_sections
                     /\ pc' = [pc EXCEPT !["main"] = "AddPreviousOutput"]
                     /\ UNCHANGED << error_class, has_counterexample, phase >>

AddPreviousOutput == /\ pc["main"] = "AddPreviousOutput"
                     /\ prompt_sections' = (prompt_sections \union {"previous_output"})
                     /\ pc' = [pc EXCEPT !["main"] = "AddErrorMessage"]
                     /\ UNCHANGED << error_class, has_counterexample, phase >>

AddErrorMessage == /\ pc["main"] = "AddErrorMessage"
                   /\ prompt_sections' = (prompt_sections \union {"error_message"})
                   /\ pc' = [pc EXCEPT !["main"] = "AddCounterexample"]
                   /\ UNCHANGED << error_class, has_counterexample, phase >>

AddCounterexample == /\ pc["main"] = "AddCounterexample"
                     /\ IF has_counterexample = TRUE
                           THEN /\ prompt_sections' = (prompt_sections \union {"counterexample"})
                           ELSE /\ TRUE
                                /\ UNCHANGED prompt_sections
                     /\ pc' = [pc EXCEPT !["main"] = "AddTLCOutput"]
                     /\ UNCHANGED << error_class, has_counterexample, phase >>

AddTLCOutput == /\ pc["main"] = "AddTLCOutput"
                /\ prompt_sections' = (prompt_sections \union {"tlc_output"})
                /\ pc' = [pc EXCEPT !["main"] = "AddClosing"]
                /\ UNCHANGED << error_class, has_counterexample, phase >>

AddClosing == /\ pc["main"] = "AddClosing"
              /\ prompt_sections' = (prompt_sections \union {"closing"})
              /\ pc' = [pc EXCEPT !["main"] = "Finish"]
              /\ UNCHANGED << error_class, has_counterexample, phase >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "complete"
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << error_class, has_counterexample, prompt_sections >>

builder == AddInitialPrompt \/ AddRetryHeader \/ AddClassification
              \/ AddPreviousOutput \/ AddErrorMessage \/ AddCounterexample
              \/ AddTLCOutput \/ AddClosing \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == builder
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(builder)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
