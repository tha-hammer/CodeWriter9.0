---- MODULE AsyncExtractFn ----

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    MaxMessages

ASSUME MaxMessages \in Nat /\ MaxMessages >= 1

(* --algorithm AsyncExtractFn

variables
  state                = "Idle",
  client_constructed   = FALSE,
  allowed_tools_param  = "UNSET",
  system_prompt_param  = "UNSET",
  max_turns_param      = 0,
  prompt_param         = "UNSET",
  msgs_remaining       = MaxMessages,
  collected_texts      = <<>>,
  last_msg_type        = "none",
  raw_output           = "",
  parse_success        = FALSE,
  fn_record            = "none";

define

  AllStates == {
    "Idle", "QueryDispatched", "Streaming",
    "Joined", "Parsed", "Returned", "ParseError"
  }

  TerminalStates == {"Returned", "ParseError"}

  ValidState == state \in AllStates

  ClientNeverConstructed ==
    client_constructed = FALSE

  OnlySDKQueryUsed ==
    \* No ClaudeSDKClient is ever directly constructed or connected;
    \* the standalone claude_agent_sdk.query() call is the only channel.
    client_constructed = FALSE

  QueryParamsValid ==
    state /= "Idle" =>
      /\ allowed_tools_param  = "empty_list"
      /\ system_prompt_param  = "EXTRACT_SYSTEM_PROMPT"
      /\ max_turns_param      = 1
      /\ prompt_param        /= "UNSET"

  CollectionTypeIntegrity ==
    last_msg_type \in {"AssistantMessage", "ResultMessage", "OtherMessage", "none"}

  ParseImpliesNonEmpty ==
    parse_success = TRUE => raw_output /= ""

  FnRecordReturnedOnSuccess ==
    state = "Returned" => fn_record = "FnRecord"

  ParseErrorMeansNoRecord ==
    state = "ParseError" => fn_record = "none"

  ReturnImpliesParseSuccess ==
    state = "Returned" => parse_success = TRUE

  ReturnImpliesCollected ==
    state = "Returned" => Len(collected_texts) > 0

end define;

fair process extractor = "main"
begin
  DispatchQuery:
    \* Call standalone claude_agent_sdk.query() — never touch ClaudeSDKClient
    allowed_tools_param := "empty_list";
    system_prompt_param := "EXTRACT_SYSTEM_PROMPT";
    max_turns_param     := 1;
    prompt_param        := "constructed_prompt";
    state               := "QueryDispatched";

  BeginStream:
    \* Start iterating the async event stream returned by query()
    state := "Streaming";

  CollectLoop:
    while msgs_remaining > 0 do
      CollectMsg:
        either
          \* AssistantMessage event: harvest every TextBlock's content
          collected_texts := Append(collected_texts, "text_block_content");
          last_msg_type   := "AssistantMessage";
          msgs_remaining  := msgs_remaining - 1;
        or
          \* ResultMessage event: harvest the result field
          collected_texts := Append(collected_texts, "result_field_content");
          last_msg_type   := "ResultMessage";
          msgs_remaining  := msgs_remaining - 1;
        or
          \* Any other event type: silently ignored, not collected
          last_msg_type  := "OtherMessage";
          msgs_remaining := msgs_remaining - 1;
        end either;
    end while;

  JoinText:
    \* Concatenate (join) all collected strings into a single raw output
    if Len(collected_texts) > 0 then
      raw_output := "nonempty_joined_output";
      state      := "Joined";
    else
      raw_output := "";
      state      := "Joined";
    end if;

  ParseJSON:
    \* Attempt to parse a JSON object from the raw output
    if raw_output /= "" then
      parse_success := TRUE;
      state         := "Parsed";
    else
      parse_success := FALSE;
      state         := "ParseError";
    end if;

  BuildRecord:
    \* On success, construct and return a FnRecord from the parsed JSON
    if state = "Parsed" then
      fn_record := "FnRecord";
      state     := "Returned";
    end if;

  Finish:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b671b95e" /\ chksum(tla) = "4f415a75")
VARIABLES pc, state, client_constructed, allowed_tools_param, 
          system_prompt_param, max_turns_param, prompt_param, msgs_remaining, 
          collected_texts, last_msg_type, raw_output, parse_success, 
          fn_record

(* define statement *)
AllStates == {
  "Idle", "QueryDispatched", "Streaming",
  "Joined", "Parsed", "Returned", "ParseError"
}

TerminalStates == {"Returned", "ParseError"}

ValidState == state \in AllStates

ClientNeverConstructed ==
  client_constructed = FALSE

OnlySDKQueryUsed ==


  client_constructed = FALSE

QueryParamsValid ==
  state /= "Idle" =>
    /\ allowed_tools_param  = "empty_list"
    /\ system_prompt_param  = "EXTRACT_SYSTEM_PROMPT"
    /\ max_turns_param      = 1
    /\ prompt_param        /= "UNSET"

CollectionTypeIntegrity ==
  last_msg_type \in {"AssistantMessage", "ResultMessage", "OtherMessage", "none"}

ParseImpliesNonEmpty ==
  parse_success = TRUE => raw_output /= ""

FnRecordReturnedOnSuccess ==
  state = "Returned" => fn_record = "FnRecord"

ParseErrorMeansNoRecord ==
  state = "ParseError" => fn_record = "none"

ReturnImpliesParseSuccess ==
  state = "Returned" => parse_success = TRUE

ReturnImpliesCollected ==
  state = "Returned" => Len(collected_texts) > 0


vars == << pc, state, client_constructed, allowed_tools_param, 
           system_prompt_param, max_turns_param, prompt_param, msgs_remaining, 
           collected_texts, last_msg_type, raw_output, parse_success, 
           fn_record >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ state = "Idle"
        /\ client_constructed = FALSE
        /\ allowed_tools_param = "UNSET"
        /\ system_prompt_param = "UNSET"
        /\ max_turns_param = 0
        /\ prompt_param = "UNSET"
        /\ msgs_remaining = MaxMessages
        /\ collected_texts = <<>>
        /\ last_msg_type = "none"
        /\ raw_output = ""
        /\ parse_success = FALSE
        /\ fn_record = "none"
        /\ pc = [self \in ProcSet |-> "DispatchQuery"]

DispatchQuery == /\ pc["main"] = "DispatchQuery"
                 /\ allowed_tools_param' = "empty_list"
                 /\ system_prompt_param' = "EXTRACT_SYSTEM_PROMPT"
                 /\ max_turns_param' = 1
                 /\ prompt_param' = "constructed_prompt"
                 /\ state' = "QueryDispatched"
                 /\ pc' = [pc EXCEPT !["main"] = "BeginStream"]
                 /\ UNCHANGED << client_constructed, msgs_remaining, 
                                 collected_texts, last_msg_type, raw_output, 
                                 parse_success, fn_record >>

BeginStream == /\ pc["main"] = "BeginStream"
               /\ state' = "Streaming"
               /\ pc' = [pc EXCEPT !["main"] = "CollectLoop"]
               /\ UNCHANGED << client_constructed, allowed_tools_param, 
                               system_prompt_param, max_turns_param, 
                               prompt_param, msgs_remaining, collected_texts, 
                               last_msg_type, raw_output, parse_success, 
                               fn_record >>

CollectLoop == /\ pc["main"] = "CollectLoop"
               /\ IF msgs_remaining > 0
                     THEN /\ pc' = [pc EXCEPT !["main"] = "CollectMsg"]
                     ELSE /\ pc' = [pc EXCEPT !["main"] = "JoinText"]
               /\ UNCHANGED << state, client_constructed, allowed_tools_param, 
                               system_prompt_param, max_turns_param, 
                               prompt_param, msgs_remaining, collected_texts, 
                               last_msg_type, raw_output, parse_success, 
                               fn_record >>

CollectMsg == /\ pc["main"] = "CollectMsg"
              /\ \/ /\ collected_texts' = Append(collected_texts, "text_block_content")
                    /\ last_msg_type' = "AssistantMessage"
                    /\ msgs_remaining' = msgs_remaining - 1
                 \/ /\ collected_texts' = Append(collected_texts, "result_field_content")
                    /\ last_msg_type' = "ResultMessage"
                    /\ msgs_remaining' = msgs_remaining - 1
                 \/ /\ last_msg_type' = "OtherMessage"
                    /\ msgs_remaining' = msgs_remaining - 1
                    /\ UNCHANGED collected_texts
              /\ pc' = [pc EXCEPT !["main"] = "CollectLoop"]
              /\ UNCHANGED << state, client_constructed, allowed_tools_param, 
                              system_prompt_param, max_turns_param, 
                              prompt_param, raw_output, parse_success, 
                              fn_record >>

JoinText == /\ pc["main"] = "JoinText"
            /\ IF Len(collected_texts) > 0
                  THEN /\ raw_output' = "nonempty_joined_output"
                       /\ state' = "Joined"
                  ELSE /\ raw_output' = ""
                       /\ state' = "Joined"
            /\ pc' = [pc EXCEPT !["main"] = "ParseJSON"]
            /\ UNCHANGED << client_constructed, allowed_tools_param, 
                            system_prompt_param, max_turns_param, prompt_param, 
                            msgs_remaining, collected_texts, last_msg_type, 
                            parse_success, fn_record >>

ParseJSON == /\ pc["main"] = "ParseJSON"
             /\ IF raw_output /= ""
                   THEN /\ parse_success' = TRUE
                        /\ state' = "Parsed"
                   ELSE /\ parse_success' = FALSE
                        /\ state' = "ParseError"
             /\ pc' = [pc EXCEPT !["main"] = "BuildRecord"]
             /\ UNCHANGED << client_constructed, allowed_tools_param, 
                             system_prompt_param, max_turns_param, 
                             prompt_param, msgs_remaining, collected_texts, 
                             last_msg_type, raw_output, fn_record >>

BuildRecord == /\ pc["main"] = "BuildRecord"
               /\ IF state = "Parsed"
                     THEN /\ fn_record' = "FnRecord"
                          /\ state' = "Returned"
                     ELSE /\ TRUE
                          /\ UNCHANGED << state, fn_record >>
               /\ pc' = [pc EXCEPT !["main"] = "Finish"]
               /\ UNCHANGED << client_constructed, allowed_tools_param, 
                               system_prompt_param, max_turns_param, 
                               prompt_param, msgs_remaining, collected_texts, 
                               last_msg_type, raw_output, parse_success >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << state, client_constructed, allowed_tools_param, 
                          system_prompt_param, max_turns_param, prompt_param, 
                          msgs_remaining, collected_texts, last_msg_type, 
                          raw_output, parse_success, fn_record >>

extractor == DispatchQuery \/ BeginStream \/ CollectLoop \/ CollectMsg
                \/ JoinText \/ ParseJSON \/ BuildRecord \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == extractor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(extractor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec => []ClientNeverConstructed
THEOREM Spec => []QueryParamsValid
THEOREM Spec => []CollectionTypeIntegrity
THEOREM Spec => []ParseImpliesNonEmpty
THEOREM Spec => []FnRecordReturnedOnSuccess
THEOREM Spec => []ParseErrorMeansNoRecord
THEOREM Spec => []ReturnImpliesParseSuccess
THEOREM Spec => []ReturnImpliesCollected

====
