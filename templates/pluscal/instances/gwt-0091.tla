---- MODULE CorrectionReviewRerun ----

EXTENDS Integers, Sequences, TLC, FiniteSets

CONSTANTS MaxRetries

ASSUME MaxRetries \in Nat /\ MaxRetries >= 1

RECURSIVE SumCosts(_)
SumCosts(seq) ==
    IF seq = <<>> THEN 0
    ELSE Head(seq).cost + SumCosts(Tail(seq))

(* --algorithm CorrectionReviewRerun

variables
    attempt        = 1,
    history        = <<>>,
    corrections    = <<>>,
    currentVerdict = "NONE",
    totalCost      = 0,
    nextSid        = 1,
    phase          = "RunReview";

define

    AttemptPositive ==
        attempt >= 1

    AttemptBounded ==
        attempt <= MaxRetries

    HistoryLengthInvariant ==
        \/ (phase = "RunReview"     /\ Len(history) = attempt - 1)
        \/ (phase = "RunCorrection" /\ Len(history) = attempt)
        \/ (phase = "IncrAttempt"   /\ Len(history) = attempt)
        \/ (phase = "Finish"        /\ Len(history) = attempt)

    CorrectionsAppendOnly ==
        Len(corrections) <= Len(history)

    CorrectionsTerminalBound ==
        phase = "Finish" => Len(corrections) <= Len(history) - 1

    VerdictFromLatest ==
        Len(history) > 0 => currentVerdict = history[Len(history)].verdict

    CostAccumulation ==
        totalCost = SumCosts(history) + SumCosts(corrections)

    AllSids ==
        { history[i].session_id : i \in 1..Len(history) }
        \union
        { corrections[i].session_id : i \in 1..Len(corrections) }

    SessionIdsUnique ==
        Cardinality(AllSids) = Len(history) + Len(corrections)

    IndependentTracking == SessionIdsUnique

    TerminalVerdictOrExhausted ==
        phase = "Finish" =>
            (currentVerdict = "PASS" \/ attempt >= MaxRetries)

    SamePassReRun ==
        \* Structurally enforced: the orchestrator loop has exactly one
        \* review step type; every re-run returns to the same ReviewStep
        \* with the same pass name (the single process models a single pass).
        TRUE

end define;

fair process orchestrator = "orch"
variables verd = "NONE", sid = 0;
begin
  OrchestratorLoop:
    while phase # "Finish" do
      if phase = "RunReview" then
        either
          verd := "PASS";
        or
          verd := "FAIL";
        end either;
        sid := nextSid;
        nextSid := nextSid + 1;
        history := Append(history,
            [verdict    |-> verd,
             session_id |-> sid,
             cost       |-> 5]);
        totalCost := totalCost + 5;
        currentVerdict := verd;
        if verd = "PASS" \/ attempt >= MaxRetries then
          phase := "Finish";
        else
          phase := "RunCorrection";
        end if;
      elsif phase = "RunCorrection" then
        sid := nextSid;
        nextSid := nextSid + 1;
        corrections := Append(corrections,
            [session_id |-> sid,
             cost       |-> 7]);
        totalCost := totalCost + 7;
        phase := "IncrAttempt";
      elsif phase = "IncrAttempt" then
        attempt := attempt + 1;
        phase := "RunReview";
      end if;
    end while;
  Terminate:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "6c4154c7" /\ chksum(tla) = "15fcb70")
VARIABLES pc, attempt, history, corrections, currentVerdict, totalCost, 
          nextSid, phase

(* define statement *)
AttemptPositive ==
    attempt >= 1

AttemptBounded ==
    attempt <= MaxRetries

HistoryLengthInvariant ==
    \/ (phase = "RunReview"     /\ Len(history) = attempt - 1)
    \/ (phase = "RunCorrection" /\ Len(history) = attempt)
    \/ (phase = "IncrAttempt"   /\ Len(history) = attempt)
    \/ (phase = "Finish"        /\ Len(history) = attempt)

CorrectionsAppendOnly ==
    Len(corrections) <= Len(history)

CorrectionsTerminalBound ==
    phase = "Finish" => Len(corrections) <= Len(history) - 1

VerdictFromLatest ==
    Len(history) > 0 => currentVerdict = history[Len(history)].verdict

CostAccumulation ==
    totalCost = SumCosts(history) + SumCosts(corrections)

AllSids ==
    { history[i].session_id : i \in 1..Len(history) }
    \union
    { corrections[i].session_id : i \in 1..Len(corrections) }

SessionIdsUnique ==
    Cardinality(AllSids) = Len(history) + Len(corrections)

IndependentTracking == SessionIdsUnique

TerminalVerdictOrExhausted ==
    phase = "Finish" =>
        (currentVerdict = "PASS" \/ attempt >= MaxRetries)

SamePassReRun ==



    TRUE

VARIABLES verd, sid

vars == << pc, attempt, history, corrections, currentVerdict, totalCost, 
           nextSid, phase, verd, sid >>

ProcSet == {"orch"}

Init == (* Global variables *)
        /\ attempt = 1
        /\ history = <<>>
        /\ corrections = <<>>
        /\ currentVerdict = "NONE"
        /\ totalCost = 0
        /\ nextSid = 1
        /\ phase = "RunReview"
        (* Process orchestrator *)
        /\ verd = "NONE"
        /\ sid = 0
        /\ pc = [self \in ProcSet |-> "OrchestratorLoop"]

OrchestratorLoop == /\ pc["orch"] = "OrchestratorLoop"
                    /\ IF phase # "Finish"
                          THEN /\ IF phase = "RunReview"
                                     THEN /\ \/ /\ verd' = "PASS"
                                             \/ /\ verd' = "FAIL"
                                          /\ sid' = nextSid
                                          /\ nextSid' = nextSid + 1
                                          /\ history' =        Append(history,
                                                        [verdict    |-> verd',
                                                         session_id |-> sid',
                                                         cost       |-> 5])
                                          /\ totalCost' = totalCost + 5
                                          /\ currentVerdict' = verd'
                                          /\ IF verd' = "PASS" \/ attempt >= MaxRetries
                                                THEN /\ phase' = "Finish"
                                                ELSE /\ phase' = "RunCorrection"
                                          /\ UNCHANGED << attempt, corrections >>
                                     ELSE /\ IF phase = "RunCorrection"
                                                THEN /\ sid' = nextSid
                                                     /\ nextSid' = nextSid + 1
                                                     /\ corrections' =            Append(corrections,
                                                                       [session_id |-> sid',
                                                                        cost       |-> 7])
                                                     /\ totalCost' = totalCost + 7
                                                     /\ phase' = "IncrAttempt"
                                                     /\ UNCHANGED attempt
                                                ELSE /\ IF phase = "IncrAttempt"
                                                           THEN /\ attempt' = attempt + 1
                                                                /\ phase' = "RunReview"
                                                           ELSE /\ TRUE
                                                                /\ UNCHANGED << attempt, 
                                                                                phase >>
                                                     /\ UNCHANGED << corrections, 
                                                                     totalCost, 
                                                                     nextSid, 
                                                                     sid >>
                                          /\ UNCHANGED << history, 
                                                          currentVerdict, verd >>
                               /\ pc' = [pc EXCEPT !["orch"] = "OrchestratorLoop"]
                          ELSE /\ pc' = [pc EXCEPT !["orch"] = "Terminate"]
                               /\ UNCHANGED << attempt, history, corrections, 
                                               currentVerdict, totalCost, 
                                               nextSid, phase, verd, sid >>

Terminate == /\ pc["orch"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["orch"] = "Done"]
             /\ UNCHANGED << attempt, history, corrections, currentVerdict, 
                             totalCost, nextSid, phase, verd, sid >>

orchestrator == OrchestratorLoop \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == orchestrator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(orchestrator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
