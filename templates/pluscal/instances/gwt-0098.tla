---- MODULE AggregateVerdictsBlocked ----

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS NumPasses

Passes  == 1..NumPasses
Verdict == {"pass", "fail", "warning", "blocked"}

(* --algorithm AggregateVerdictsBlocked

variables
  pass_verdicts  \in [Passes -> Verdict],
  aggregated      = FALSE,
  overall         = "none",
  passed_bucket   = {},
  failed_bucket   = {},
  blocked_bucket  = {},
  stuck_on        = {},
  idx             = 1;

define

  BlockedImpliesFail ==
    aggregated =>
      ((\E p \in Passes : pass_verdicts[p] = "blocked") => overall = "fail")

  FailImpliesFail ==
    aggregated =>
      ((\E p \in Passes : pass_verdicts[p] = "fail") => overall = "fail")

  BucketPartition ==
    aggregated =>
      (passed_bucket \union failed_bucket \union blocked_bucket = Passes)

  BucketDisjoint ==
    aggregated =>
      (passed_bucket \cap failed_bucket  = {} /\
       passed_bucket \cap blocked_bucket = {} /\
       failed_bucket \cap blocked_bucket = {})

  BlockedNotStuckOn ==
    aggregated =>
      (\A p \in blocked_bucket : p \notin stuck_on)

  FailIsStuckOn ==
    aggregated =>
      (\A p \in failed_bucket : p \in stuck_on)

  StuckOnExactlyFails ==
    aggregated => (stuck_on = failed_bucket)

  WarningInPassed ==
    aggregated =>
      (\A p \in Passes : pass_verdicts[p] = "warning" => p \in passed_bucket)

  PassInPassed ==
    aggregated =>
      (\A p \in Passes : pass_verdicts[p] = "pass" => p \in passed_bucket)

  FailInFailed ==
    aggregated =>
      (\A p \in Passes : pass_verdicts[p] = "fail" => p \in failed_bucket)

  BlockedInBlocked ==
    aggregated =>
      (\A p \in Passes : pass_verdicts[p] = "blocked" => p \in blocked_bucket)

  NoFailOrBlockedMeansPassOrWarning ==
    aggregated =>
      ((\A p \in Passes : pass_verdicts[p] \in {"pass", "warning"})
       => overall \in {"pass", "warning"})

  OverallIsValid ==
    aggregated => overall \in {"pass", "fail", "warning"}

  BucketsSubsetPasses ==
    passed_bucket  \subseteq Passes /\
    failed_bucket  \subseteq Passes /\
    blocked_bucket \subseteq Passes /\
    stuck_on       \subseteq Passes

end define;

fair process aggregator = "aggregator"
begin
  ProcessNext:
    while idx <= NumPasses do
      if pass_verdicts[idx] = "warning" then
        passed_bucket  := passed_bucket \union {idx};
      elsif pass_verdicts[idx] = "pass" then
        passed_bucket  := passed_bucket \union {idx};
      elsif pass_verdicts[idx] = "fail" then
        failed_bucket  := failed_bucket \union {idx};
        stuck_on       := stuck_on \union {idx};
      else
        blocked_bucket := blocked_bucket \union {idx};
      end if;
      idx := idx + 1;
    end while;

  ComputeOverall:
    if failed_bucket /= {} \/ blocked_bucket /= {} then
      overall := "fail";
    elsif \E p \in Passes : pass_verdicts[p] = "warning" then
      overall := "warning";
    else
      overall := "pass";
    end if;

  SetAggregated:
    aggregated := TRUE;

  Finish:
    skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3c8a9dd2" /\ chksum(tla) = "c56bf99c")
VARIABLES pc, pass_verdicts, aggregated, overall, passed_bucket, 
          failed_bucket, blocked_bucket, stuck_on, idx

(* define statement *)
BlockedImpliesFail ==
  aggregated =>
    ((\E p \in Passes : pass_verdicts[p] = "blocked") => overall = "fail")

FailImpliesFail ==
  aggregated =>
    ((\E p \in Passes : pass_verdicts[p] = "fail") => overall = "fail")

BucketPartition ==
  aggregated =>
    (passed_bucket \union failed_bucket \union blocked_bucket = Passes)

BucketDisjoint ==
  aggregated =>
    (passed_bucket \cap failed_bucket  = {} /\
     passed_bucket \cap blocked_bucket = {} /\
     failed_bucket \cap blocked_bucket = {})

BlockedNotStuckOn ==
  aggregated =>
    (\A p \in blocked_bucket : p \notin stuck_on)

FailIsStuckOn ==
  aggregated =>
    (\A p \in failed_bucket : p \in stuck_on)

StuckOnExactlyFails ==
  aggregated => (stuck_on = failed_bucket)

WarningInPassed ==
  aggregated =>
    (\A p \in Passes : pass_verdicts[p] = "warning" => p \in passed_bucket)

PassInPassed ==
  aggregated =>
    (\A p \in Passes : pass_verdicts[p] = "pass" => p \in passed_bucket)

FailInFailed ==
  aggregated =>
    (\A p \in Passes : pass_verdicts[p] = "fail" => p \in failed_bucket)

BlockedInBlocked ==
  aggregated =>
    (\A p \in Passes : pass_verdicts[p] = "blocked" => p \in blocked_bucket)

NoFailOrBlockedMeansPassOrWarning ==
  aggregated =>
    ((\A p \in Passes : pass_verdicts[p] \in {"pass", "warning"})
     => overall \in {"pass", "warning"})

OverallIsValid ==
  aggregated => overall \in {"pass", "fail", "warning"}

BucketsSubsetPasses ==
  passed_bucket  \subseteq Passes /\
  failed_bucket  \subseteq Passes /\
  blocked_bucket \subseteq Passes /\
  stuck_on       \subseteq Passes


vars == << pc, pass_verdicts, aggregated, overall, passed_bucket, 
           failed_bucket, blocked_bucket, stuck_on, idx >>

ProcSet == {"aggregator"}

Init == (* Global variables *)
        /\ pass_verdicts \in [Passes -> Verdict]
        /\ aggregated = FALSE
        /\ overall = "none"
        /\ passed_bucket = {}
        /\ failed_bucket = {}
        /\ blocked_bucket = {}
        /\ stuck_on = {}
        /\ idx = 1
        /\ pc = [self \in ProcSet |-> "ProcessNext"]

ProcessNext == /\ pc["aggregator"] = "ProcessNext"
               /\ IF idx <= NumPasses
                     THEN /\ IF pass_verdicts[idx] = "warning"
                                THEN /\ passed_bucket' = (passed_bucket \union {idx})
                                     /\ UNCHANGED << failed_bucket, 
                                                     blocked_bucket, stuck_on >>
                                ELSE /\ IF pass_verdicts[idx] = "pass"
                                           THEN /\ passed_bucket' = (passed_bucket \union {idx})
                                                /\ UNCHANGED << failed_bucket, 
                                                                blocked_bucket, 
                                                                stuck_on >>
                                           ELSE /\ IF pass_verdicts[idx] = "fail"
                                                      THEN /\ failed_bucket' = (failed_bucket \union {idx})
                                                           /\ stuck_on' = (stuck_on \union {idx})
                                                           /\ UNCHANGED blocked_bucket
                                                      ELSE /\ blocked_bucket' = (blocked_bucket \union {idx})
                                                           /\ UNCHANGED << failed_bucket, 
                                                                           stuck_on >>
                                                /\ UNCHANGED passed_bucket
                          /\ idx' = idx + 1
                          /\ pc' = [pc EXCEPT !["aggregator"] = "ProcessNext"]
                     ELSE /\ pc' = [pc EXCEPT !["aggregator"] = "ComputeOverall"]
                          /\ UNCHANGED << passed_bucket, failed_bucket, 
                                          blocked_bucket, stuck_on, idx >>
               /\ UNCHANGED << pass_verdicts, aggregated, overall >>

ComputeOverall == /\ pc["aggregator"] = "ComputeOverall"
                  /\ IF failed_bucket /= {} \/ blocked_bucket /= {}
                        THEN /\ overall' = "fail"
                        ELSE /\ IF \E p \in Passes : pass_verdicts[p] = "warning"
                                   THEN /\ overall' = "warning"
                                   ELSE /\ overall' = "pass"
                  /\ pc' = [pc EXCEPT !["aggregator"] = "SetAggregated"]
                  /\ UNCHANGED << pass_verdicts, aggregated, passed_bucket, 
                                  failed_bucket, blocked_bucket, stuck_on, idx >>

SetAggregated == /\ pc["aggregator"] = "SetAggregated"
                 /\ aggregated' = TRUE
                 /\ pc' = [pc EXCEPT !["aggregator"] = "Finish"]
                 /\ UNCHANGED << pass_verdicts, overall, passed_bucket, 
                                 failed_bucket, blocked_bucket, stuck_on, idx >>

Finish == /\ pc["aggregator"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["aggregator"] = "Done"]
          /\ UNCHANGED << pass_verdicts, aggregated, overall, passed_bucket, 
                          failed_bucket, blocked_bucket, stuck_on, idx >>

aggregator == ProcessNext \/ ComputeOverall \/ SetAggregated \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == aggregator
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(aggregator)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
