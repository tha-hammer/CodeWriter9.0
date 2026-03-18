---- MODULE gwt0014_SchedulerHeavyTLA ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Nodes,
    MAX_RETRIES,
    TLC_CHECK_SECONDS,
    PCAL_TRANS_SECONDS

TimeoutBudget == MAX_RETRIES * (TLC_CHECK_SECONDS + PCAL_TRANS_SECONDS)

(* --algorithm gwt0014_SchedulerHeavyTLA

variables
    job_state = "pending",
    selected_node = "none",
    node_has_jre \in [Nodes -> BOOLEAN],
    node_has_tla2tools \in [Nodes -> BOOLEAN],
    node_has_sdk_creds \in [Nodes -> BOOLEAN],
    retry_count = 0,
    elapsed_seconds = 0;

define

    IsHeavyTLA(n) ==
        /\ node_has_jre[n]
        /\ node_has_tla2tools[n]
        /\ node_has_sdk_creds[n]

    HeavyTLANodes == { n \in Nodes : IsHeavyTLA(n) }

    JobStates == {
        "pending", "scheduling", "node_selected",
        "validated", "rejected", "running",
        "complete", "timed_out"
    }

    ValidState == job_state \in JobStates

    SchedulerSafetyInvariant ==
        job_state \in {"validated", "running", "complete"} =>
            /\ selected_node \in Nodes
            /\ IsHeavyTLA(selected_node)

    NoNonHeavyTLASelected ==
        selected_node # "none" => IsHeavyTLA(selected_node)

    TimeoutBudgetRespected ==
        job_state = "running" =>
            elapsed_seconds <= TimeoutBudget

    RetryBound == retry_count <= MAX_RETRIES

    CompletionImpliesWithinBudget ==
        job_state = "complete" => elapsed_seconds <= TimeoutBudget

end define;

fair process scheduler = "scheduler"
begin
    Schedule:
        job_state := "scheduling";

    SelectNode:
        if HeavyTLANodes = {} then
            job_state := "rejected";
            goto Terminate;
        else
            with n \in HeavyTLANodes do
                selected_node := n;
                job_state := "node_selected";
            end with;
        end if;

    ValidateNode:
        if IsHeavyTLA(selected_node) then
            job_state := "validated";
        else
            job_state := "rejected";
            goto Terminate;
        end if;

    RunJob:
        job_state := "running";

    RetryLoop:
        while retry_count < MAX_RETRIES do
            elapsed_seconds := elapsed_seconds + TLC_CHECK_SECONDS + PCAL_TRANS_SECONDS;
            retry_count := retry_count + 1;
        end while;

    CheckTimeout:
        if elapsed_seconds <= TimeoutBudget then
            job_state := "complete";
        else
            job_state := "timed_out";
        end if;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "2e31773a" /\ chksum(tla) = "c891593")
VARIABLES pc, job_state, selected_node, node_has_jre, node_has_tla2tools, 
          node_has_sdk_creds, retry_count, elapsed_seconds

(* define statement *)
IsHeavyTLA(n) ==
    /\ node_has_jre[n]
    /\ node_has_tla2tools[n]
    /\ node_has_sdk_creds[n]

HeavyTLANodes == { n \in Nodes : IsHeavyTLA(n) }

JobStates == {
    "pending", "scheduling", "node_selected",
    "validated", "rejected", "running",
    "complete", "timed_out"
}

ValidState == job_state \in JobStates

SchedulerSafetyInvariant ==
    job_state \in {"validated", "running", "complete"} =>
        /\ selected_node \in Nodes
        /\ IsHeavyTLA(selected_node)

NoNonHeavyTLASelected ==
    selected_node # "none" => IsHeavyTLA(selected_node)

TimeoutBudgetRespected ==
    job_state = "running" =>
        elapsed_seconds <= TimeoutBudget

RetryBound == retry_count <= MAX_RETRIES

CompletionImpliesWithinBudget ==
    job_state = "complete" => elapsed_seconds <= TimeoutBudget


vars == << pc, job_state, selected_node, node_has_jre, node_has_tla2tools, 
           node_has_sdk_creds, retry_count, elapsed_seconds >>

ProcSet == {"scheduler"}

Init == (* Global variables *)
        /\ job_state = "pending"
        /\ selected_node = "none"
        /\ node_has_jre \in [Nodes -> BOOLEAN]
        /\ node_has_tla2tools \in [Nodes -> BOOLEAN]
        /\ node_has_sdk_creds \in [Nodes -> BOOLEAN]
        /\ retry_count = 0
        /\ elapsed_seconds = 0
        /\ pc = [self \in ProcSet |-> "Schedule"]

Schedule == /\ pc["scheduler"] = "Schedule"
            /\ job_state' = "scheduling"
            /\ pc' = [pc EXCEPT !["scheduler"] = "SelectNode"]
            /\ UNCHANGED << selected_node, node_has_jre, node_has_tla2tools, 
                            node_has_sdk_creds, retry_count, elapsed_seconds >>

SelectNode == /\ pc["scheduler"] = "SelectNode"
              /\ IF HeavyTLANodes = {}
                    THEN /\ job_state' = "rejected"
                         /\ pc' = [pc EXCEPT !["scheduler"] = "Terminate"]
                         /\ UNCHANGED selected_node
                    ELSE /\ \E n \in HeavyTLANodes:
                              /\ selected_node' = n
                              /\ job_state' = "node_selected"
                         /\ pc' = [pc EXCEPT !["scheduler"] = "ValidateNode"]
              /\ UNCHANGED << node_has_jre, node_has_tla2tools, 
                              node_has_sdk_creds, retry_count, elapsed_seconds >>

ValidateNode == /\ pc["scheduler"] = "ValidateNode"
                /\ IF IsHeavyTLA(selected_node)
                      THEN /\ job_state' = "validated"
                           /\ pc' = [pc EXCEPT !["scheduler"] = "RunJob"]
                      ELSE /\ job_state' = "rejected"
                           /\ pc' = [pc EXCEPT !["scheduler"] = "Terminate"]
                /\ UNCHANGED << selected_node, node_has_jre, 
                                node_has_tla2tools, node_has_sdk_creds, 
                                retry_count, elapsed_seconds >>

RunJob == /\ pc["scheduler"] = "RunJob"
          /\ job_state' = "running"
          /\ pc' = [pc EXCEPT !["scheduler"] = "RetryLoop"]
          /\ UNCHANGED << selected_node, node_has_jre, node_has_tla2tools, 
                          node_has_sdk_creds, retry_count, elapsed_seconds >>

RetryLoop == /\ pc["scheduler"] = "RetryLoop"
             /\ IF retry_count < MAX_RETRIES
                   THEN /\ elapsed_seconds' = elapsed_seconds + TLC_CHECK_SECONDS + PCAL_TRANS_SECONDS
                        /\ retry_count' = retry_count + 1
                        /\ pc' = [pc EXCEPT !["scheduler"] = "RetryLoop"]
                   ELSE /\ pc' = [pc EXCEPT !["scheduler"] = "CheckTimeout"]
                        /\ UNCHANGED << retry_count, elapsed_seconds >>
             /\ UNCHANGED << job_state, selected_node, node_has_jre, 
                             node_has_tla2tools, node_has_sdk_creds >>

CheckTimeout == /\ pc["scheduler"] = "CheckTimeout"
                /\ IF elapsed_seconds <= TimeoutBudget
                      THEN /\ job_state' = "complete"
                      ELSE /\ job_state' = "timed_out"
                /\ pc' = [pc EXCEPT !["scheduler"] = "Terminate"]
                /\ UNCHANGED << selected_node, node_has_jre, 
                                node_has_tla2tools, node_has_sdk_creds, 
                                retry_count, elapsed_seconds >>

Terminate == /\ pc["scheduler"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["scheduler"] = "Done"]
             /\ UNCHANGED << job_state, selected_node, node_has_jre, 
                             node_has_tla2tools, node_has_sdk_creds, 
                             retry_count, elapsed_seconds >>

scheduler == Schedule \/ SelectNode \/ ValidateNode \/ RunJob \/ RetryLoop
                \/ CheckTimeout \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == scheduler
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(scheduler)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
