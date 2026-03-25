---- MODULE CorrectionAgentOptions ----

EXTENDS Integers, FiniteSets, Sequences, TLC

(*
 * All expected values are defined as TLA+ operators rather than CONSTANTS
 * with ASSUME, so TLC can evaluate them without model configuration.
 *)

ExpectedTools  == {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}
ExpectedTurns  == 20
ExpectedModel  == "claude-sonnet-4-6"
ExpectedPrompt == "CW9 correction agent"
BoundSteps     == 10

(* --algorithm CorrectionAgentOptions

variables
    phase         = "idle",
    allowed_tools = {},
    max_turns     = 0,
    model         = "",
    system_prompt = "",
    output_format = "UNSET",
    options_valid = FALSE,
    step_count    = 0;

define

    ExactToolSet ==
        phase = "assembled" =>
            allowed_tools = {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}

    TurnLimit ==
        phase = "assembled" => max_turns = 20

    ModelFixed ==
        phase = "assembled" => model = "claude-sonnet-4-6"

    SystemPromptIdentity ==
        phase = "assembled" => system_prompt = "CW9 correction agent"

    NoWebSearch ==
        "WebSearch" \notin allowed_tools

    NoWebFetch ==
        "WebFetch" \notin allowed_tools

    NoSubAgentTools ==
        "TodoWrite" \notin allowed_tools /\ "Agent" \notin allowed_tools

    OutputFormatUnset ==
        phase = "assembled" => output_format = "UNSET"

    BoundedExecution ==
        step_count <= BoundSteps

    AllInvariants ==
        /\ ExactToolSet
        /\ TurnLimit
        /\ ModelFixed
        /\ SystemPromptIdentity
        /\ NoWebSearch
        /\ NoWebFetch
        /\ NoSubAgentTools
        /\ OutputFormatUnset
        /\ BoundedExecution

end define;

fair process correctionAgent = "correction_agent"
begin
    Assemble:
        allowed_tools := {"Read", "Grep", "Glob", "Bash", "Edit", "Write"};
        max_turns     := 20;
        model         := "claude-sonnet-4-6";
        system_prompt := "CW9 correction agent";
        output_format := "UNSET";
        phase         := "assembled";
        step_count    := step_count + 1;

    Validate:
        assert allowed_tools = ExpectedTools;
        assert max_turns     = ExpectedTurns;
        assert model         = ExpectedModel;
        assert system_prompt = ExpectedPrompt;
        assert output_format = "UNSET";
        assert "WebSearch" \notin allowed_tools;
        assert "WebFetch"  \notin allowed_tools;
        assert "TodoWrite" \notin allowed_tools;
        assert "Agent"     \notin allowed_tools;
        options_valid := TRUE;
        step_count    := step_count + 1;

    Invoke:
        assert options_valid = TRUE;
        phase      := "query_invoked";
        step_count := step_count + 1;

    Finish:
        phase      := "complete";
        step_count := step_count + 1;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "748af709" /\ chksum(tla) = "15f28cae")
VARIABLES pc, phase, allowed_tools, max_turns, model, system_prompt, 
          output_format, options_valid, step_count

(* define statement *)
ExactToolSet ==
    phase = "assembled" =>
        allowed_tools = {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}

TurnLimit ==
    phase = "assembled" => max_turns = 20

ModelFixed ==
    phase = "assembled" => model = "claude-sonnet-4-6"

SystemPromptIdentity ==
    phase = "assembled" => system_prompt = "CW9 correction agent"

NoWebSearch ==
    "WebSearch" \notin allowed_tools

NoWebFetch ==
    "WebFetch" \notin allowed_tools

NoSubAgentTools ==
    "TodoWrite" \notin allowed_tools /\ "Agent" \notin allowed_tools

OutputFormatUnset ==
    phase = "assembled" => output_format = "UNSET"

BoundedExecution ==
    step_count <= BoundSteps

AllInvariants ==
    /\ ExactToolSet
    /\ TurnLimit
    /\ ModelFixed
    /\ SystemPromptIdentity
    /\ NoWebSearch
    /\ NoWebFetch
    /\ NoSubAgentTools
    /\ OutputFormatUnset
    /\ BoundedExecution


vars == << pc, phase, allowed_tools, max_turns, model, system_prompt, 
           output_format, options_valid, step_count >>

ProcSet == {"correction_agent"}

Init == (* Global variables *)
        /\ phase = "idle"
        /\ allowed_tools = {}
        /\ max_turns = 0
        /\ model = ""
        /\ system_prompt = ""
        /\ output_format = "UNSET"
        /\ options_valid = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "Assemble"]

Assemble == /\ pc["correction_agent"] = "Assemble"
            /\ allowed_tools' = {"Read", "Grep", "Glob", "Bash", "Edit", "Write"}
            /\ max_turns' = 20
            /\ model' = "claude-sonnet-4-6"
            /\ system_prompt' = "CW9 correction agent"
            /\ output_format' = "UNSET"
            /\ phase' = "assembled"
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["correction_agent"] = "Validate"]
            /\ UNCHANGED options_valid

Validate == /\ pc["correction_agent"] = "Validate"
            /\ Assert(allowed_tools = ExpectedTools, 
                      "Failure of assertion at line 83, column 9.")
            /\ Assert(max_turns     = ExpectedTurns, 
                      "Failure of assertion at line 84, column 9.")
            /\ Assert(model         = ExpectedModel, 
                      "Failure of assertion at line 85, column 9.")
            /\ Assert(system_prompt = ExpectedPrompt, 
                      "Failure of assertion at line 86, column 9.")
            /\ Assert(output_format = "UNSET", 
                      "Failure of assertion at line 87, column 9.")
            /\ Assert("WebSearch" \notin allowed_tools, 
                      "Failure of assertion at line 88, column 9.")
            /\ Assert("WebFetch"  \notin allowed_tools, 
                      "Failure of assertion at line 89, column 9.")
            /\ Assert("TodoWrite" \notin allowed_tools, 
                      "Failure of assertion at line 90, column 9.")
            /\ Assert("Agent"     \notin allowed_tools, 
                      "Failure of assertion at line 91, column 9.")
            /\ options_valid' = TRUE
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["correction_agent"] = "Invoke"]
            /\ UNCHANGED << phase, allowed_tools, max_turns, model, 
                            system_prompt, output_format >>

Invoke == /\ pc["correction_agent"] = "Invoke"
          /\ Assert(options_valid = TRUE, 
                    "Failure of assertion at line 96, column 9.")
          /\ phase' = "query_invoked"
          /\ step_count' = step_count + 1
          /\ pc' = [pc EXCEPT !["correction_agent"] = "Finish"]
          /\ UNCHANGED << allowed_tools, max_turns, model, system_prompt, 
                          output_format, options_valid >>

Finish == /\ pc["correction_agent"] = "Finish"
          /\ phase' = "complete"
          /\ step_count' = step_count + 1
          /\ pc' = [pc EXCEPT !["correction_agent"] = "Done"]
          /\ UNCHANGED << allowed_tools, max_turns, model, system_prompt, 
                          output_format, options_valid >>

correctionAgent == Assemble \/ Validate \/ Invoke \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == correctionAgent
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(correctionAgent)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
