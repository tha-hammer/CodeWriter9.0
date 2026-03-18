---- MODULE GWT0027RetryPromptBuilder ----

EXTENDS Integers, Sequences, TLC

CONSTANTS MaxAttempts

ASSUME MaxAttempts >= 1

(* --algorithm GWT0027RetryPromptBuilder

variables
    attempt_no          = 1,
    loop_result         = "NONE",
    raw_ce_available    = FALSE,
    structured_trace    = FALSE,
    error_class         = "NONE",
    human_trace         = FALSE,
    prev_pluscal        = FALSE,
    retry_prompt        = [has_trace       |-> FALSE,
                           has_error_class |-> FALSE,
                           has_prev_pluscal|-> FALSE],
    prompt_sent         = FALSE,
    client_history      = <<>>;

define

    BoundedExecution ==
        attempt_no <= MaxAttempts + 1

    RetryPromptCompleteness ==
        prompt_sent =>
            ( retry_prompt.has_trace        = TRUE
           /\ retry_prompt.has_error_class  = TRUE
           /\ retry_prompt.has_prev_pluscal = TRUE )

    AllHistoryEntriesComplete ==
        \A i \in 1..Len(client_history) :
            client_history[i].has_trace        = TRUE /\
            client_history[i].has_error_class  = TRUE /\
            client_history[i].has_prev_pluscal = TRUE

    SentImpliesNonEmptyHistory ==
        prompt_sent => Len(client_history) > 0

    HistoryCountBelowAttemptNo ==
        Len(client_history) < attempt_no

    FullCorrectionHistoryPreserved ==
        \A i \in 1..Len(client_history) :
            client_history[i].has_trace = TRUE

end define;

fair process RetryPromptLoop = "main"
begin
    AttemptStart:
        while attempt_no <= MaxAttempts do
            either
                TriggerRetry:
                    loop_result      := "RETRY";
                    raw_ce_available := TRUE;
                    prev_pluscal     := TRUE;
            or
                TriggerSuccess:
                    loop_result := "SUCCESS";
                    goto Terminate;
            end either;

            ParseCE:
                assert loop_result      = "RETRY";
                assert raw_ce_available = TRUE;
                structured_trace := TRUE;

            ClassifyError:
                assert structured_trace = TRUE;
                error_class := "COUNTEREXAMPLE_VIOLATION";

            TranslateCE:
                assert structured_trace = TRUE;
                human_trace := TRUE;

            BuildPrompt:
                assert human_trace  = TRUE;
                assert error_class /= "NONE";
                assert prev_pluscal = TRUE;
                retry_prompt := [
                    has_trace        |-> TRUE,
                    has_error_class  |-> TRUE,
                    has_prev_pluscal |-> TRUE
                ];

            SendToClient:
                assert retry_prompt.has_trace        = TRUE;
                assert retry_prompt.has_error_class  = TRUE;
                assert retry_prompt.has_prev_pluscal = TRUE;
                client_history   := Append(client_history, retry_prompt);
                prompt_sent      := TRUE;
                attempt_no       := attempt_no + 1;
                raw_ce_available := FALSE;
                structured_trace := FALSE;
                human_trace      := FALSE;
                error_class      := "NONE";
                prev_pluscal     := FALSE;
                loop_result      := "NONE";
        end while;

    Terminate:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "d0dd1868" /\ chksum(tla) = "22de6913")
VARIABLES pc, attempt_no, loop_result, raw_ce_available, structured_trace, 
          error_class, human_trace, prev_pluscal, retry_prompt, prompt_sent, 
          client_history

(* define statement *)
BoundedExecution ==
    attempt_no <= MaxAttempts + 1

RetryPromptCompleteness ==
    prompt_sent =>
        ( retry_prompt.has_trace        = TRUE
       /\ retry_prompt.has_error_class  = TRUE
       /\ retry_prompt.has_prev_pluscal = TRUE )

AllHistoryEntriesComplete ==
    \A i \in 1..Len(client_history) :
        client_history[i].has_trace        = TRUE /\
        client_history[i].has_error_class  = TRUE /\
        client_history[i].has_prev_pluscal = TRUE

SentImpliesNonEmptyHistory ==
    prompt_sent => Len(client_history) > 0

HistoryCountBelowAttemptNo ==
    Len(client_history) < attempt_no

FullCorrectionHistoryPreserved ==
    \A i \in 1..Len(client_history) :
        client_history[i].has_trace = TRUE


vars == << pc, attempt_no, loop_result, raw_ce_available, structured_trace, 
           error_class, human_trace, prev_pluscal, retry_prompt, prompt_sent, 
           client_history >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ attempt_no = 1
        /\ loop_result = "NONE"
        /\ raw_ce_available = FALSE
        /\ structured_trace = FALSE
        /\ error_class = "NONE"
        /\ human_trace = FALSE
        /\ prev_pluscal = FALSE
        /\ retry_prompt = [has_trace       |-> FALSE,
                           has_error_class |-> FALSE,
                           has_prev_pluscal|-> FALSE]
        /\ prompt_sent = FALSE
        /\ client_history = <<>>
        /\ pc = [self \in ProcSet |-> "AttemptStart"]

AttemptStart == /\ pc["main"] = "AttemptStart"
                /\ IF attempt_no <= MaxAttempts
                      THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "TriggerRetry"]
                              \/ /\ pc' = [pc EXCEPT !["main"] = "TriggerSuccess"]
                      ELSE /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                                structured_trace, error_class, human_trace, 
                                prev_pluscal, retry_prompt, prompt_sent, 
                                client_history >>

ParseCE == /\ pc["main"] = "ParseCE"
           /\ Assert(loop_result      = "RETRY", 
                     "Failure of assertion at line 70, column 17.")
           /\ Assert(raw_ce_available = TRUE, 
                     "Failure of assertion at line 71, column 17.")
           /\ structured_trace' = TRUE
           /\ pc' = [pc EXCEPT !["main"] = "ClassifyError"]
           /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                           error_class, human_trace, prev_pluscal, 
                           retry_prompt, prompt_sent, client_history >>

ClassifyError == /\ pc["main"] = "ClassifyError"
                 /\ Assert(structured_trace = TRUE, 
                           "Failure of assertion at line 75, column 17.")
                 /\ error_class' = "COUNTEREXAMPLE_VIOLATION"
                 /\ pc' = [pc EXCEPT !["main"] = "TranslateCE"]
                 /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                                 structured_trace, human_trace, prev_pluscal, 
                                 retry_prompt, prompt_sent, client_history >>

TranslateCE == /\ pc["main"] = "TranslateCE"
               /\ Assert(structured_trace = TRUE, 
                         "Failure of assertion at line 79, column 17.")
               /\ human_trace' = TRUE
               /\ pc' = [pc EXCEPT !["main"] = "BuildPrompt"]
               /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                               structured_trace, error_class, prev_pluscal, 
                               retry_prompt, prompt_sent, client_history >>

BuildPrompt == /\ pc["main"] = "BuildPrompt"
               /\ Assert(human_trace  = TRUE, 
                         "Failure of assertion at line 83, column 17.")
               /\ Assert(error_class /= "NONE", 
                         "Failure of assertion at line 84, column 17.")
               /\ Assert(prev_pluscal = TRUE, 
                         "Failure of assertion at line 85, column 17.")
               /\ retry_prompt' =                 [
                                      has_trace        |-> TRUE,
                                      has_error_class  |-> TRUE,
                                      has_prev_pluscal |-> TRUE
                                  ]
               /\ pc' = [pc EXCEPT !["main"] = "SendToClient"]
               /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                               structured_trace, error_class, human_trace, 
                               prev_pluscal, prompt_sent, client_history >>

SendToClient == /\ pc["main"] = "SendToClient"
                /\ Assert(retry_prompt.has_trace        = TRUE, 
                          "Failure of assertion at line 93, column 17.")
                /\ Assert(retry_prompt.has_error_class  = TRUE, 
                          "Failure of assertion at line 94, column 17.")
                /\ Assert(retry_prompt.has_prev_pluscal = TRUE, 
                          "Failure of assertion at line 95, column 17.")
                /\ client_history' = Append(client_history, retry_prompt)
                /\ prompt_sent' = TRUE
                /\ attempt_no' = attempt_no + 1
                /\ raw_ce_available' = FALSE
                /\ structured_trace' = FALSE
                /\ human_trace' = FALSE
                /\ error_class' = "NONE"
                /\ prev_pluscal' = FALSE
                /\ loop_result' = "NONE"
                /\ pc' = [pc EXCEPT !["main"] = "AttemptStart"]
                /\ UNCHANGED retry_prompt

TriggerRetry == /\ pc["main"] = "TriggerRetry"
                /\ loop_result' = "RETRY"
                /\ raw_ce_available' = TRUE
                /\ prev_pluscal' = TRUE
                /\ pc' = [pc EXCEPT !["main"] = "ParseCE"]
                /\ UNCHANGED << attempt_no, structured_trace, error_class, 
                                human_trace, retry_prompt, prompt_sent, 
                                client_history >>

TriggerSuccess == /\ pc["main"] = "TriggerSuccess"
                  /\ loop_result' = "SUCCESS"
                  /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                  /\ UNCHANGED << attempt_no, raw_ce_available, 
                                  structured_trace, error_class, human_trace, 
                                  prev_pluscal, retry_prompt, prompt_sent, 
                                  client_history >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << attempt_no, loop_result, raw_ce_available, 
                             structured_trace, error_class, human_trace, 
                             prev_pluscal, retry_prompt, prompt_sent, 
                             client_history >>

RetryPromptLoop == AttemptStart \/ ParseCE \/ ClassifyError \/ TranslateCE
                      \/ BuildPrompt \/ SendToClient \/ TriggerRetry
                      \/ TriggerSuccess \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == RetryPromptLoop
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(RetryPromptLoop)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
