---- MODULE ProjectProvision ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    MaxRequests,
    MaxProjectIds

ASSUME MaxRequests \in Nat /\ MaxRequests >= 1
ASSUME MaxProjectIds \in Nat /\ MaxProjectIds >= MaxRequests

(* --algorithm ProjectProvision

variables
    next_project_id = 1,
    postgres_records = {},
    storage_prefixes = {},
    filesystem_dirs = {},
    requests_processed = 0,
    op = "idle",
    response_project_id = 0,
    response_prefix_id = 0,
    request_pending = FALSE,
    phase = "await_request";

define

    UniqueProjectIds ==
        \A r1 \in postgres_records :
            \A r2 \in postgres_records :
                r1 /= r2 => r1.project_id /= r2.project_id

    StoragePrefixProvisionedForEachProject ==
        \A r \in postgres_records :
            \E s \in storage_prefixes : s.project_id = r.project_id

    EachStoragePrefixMatchesARecord ==
        \A s \in storage_prefixes :
            \E r \in postgres_records : r.project_id = s.project_id

    NoFilesystemDirsCreated ==
        filesystem_dirs = {}

    NoWorkerFilesystemPollution ==
        filesystem_dirs = {}

    ResponseConsistency ==
        phase = "responded" =>
            /\ response_project_id >= 1
            /\ response_prefix_id = response_project_id

    BoundedRequests ==
        requests_processed <= MaxRequests

    ProjectIdsArePositive ==
        \A r \in postgres_records : r.project_id >= 1

    StoragePrefixIdsArePositive ==
        \A s \in storage_prefixes : s.prefix_id >= 1

end define;

fair process api_handler = "api"
begin

    AwaitRequest:
        while requests_processed < MaxRequests do
            request_pending := TRUE;
            phase           := "processing";
            op              := "request_received";

            AllocateProjectId:
                if next_project_id > MaxProjectIds then
                    op              := "id_exhausted";
                    phase           := "await_request";
                    request_pending := FALSE;
                    goto AwaitRequest;
                else
                    response_project_id := next_project_id;
                    next_project_id     := next_project_id + 1;
                    op                  := "id_allocated";
                end if;

            ProvisionProject:
                postgres_records := postgres_records \union
                    {[project_id |-> response_project_id,
                      status     |-> "active"]};
                response_prefix_id := response_project_id;
                storage_prefixes   := storage_prefixes \union
                    {[project_id |-> response_project_id,
                      prefix_id  |-> response_project_id]};
                op := "project_provisioned";

            SendResponse:
                phase              := "responded";
                request_pending    := FALSE;
                requests_processed := requests_processed + 1;
                op                 := "response_sent";

            ResetPhase:
                phase := "await_request";

        end while;

    Terminate:
        op := "handler_finished";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "22708137" /\ chksum(tla) = "f7be3204")
VARIABLES pc, next_project_id, postgres_records, storage_prefixes, 
          filesystem_dirs, requests_processed, op, response_project_id, 
          response_prefix_id, request_pending, phase

(* define statement *)
UniqueProjectIds ==
    \A r1 \in postgres_records :
        \A r2 \in postgres_records :
            r1 /= r2 => r1.project_id /= r2.project_id

StoragePrefixProvisionedForEachProject ==
    \A r \in postgres_records :
        \E s \in storage_prefixes : s.project_id = r.project_id

EachStoragePrefixMatchesARecord ==
    \A s \in storage_prefixes :
        \E r \in postgres_records : r.project_id = s.project_id

NoFilesystemDirsCreated ==
    filesystem_dirs = {}

NoWorkerFilesystemPollution ==
    filesystem_dirs = {}

ResponseConsistency ==
    phase = "responded" =>
        /\ response_project_id >= 1
        /\ response_prefix_id = response_project_id

BoundedRequests ==
    requests_processed <= MaxRequests

ProjectIdsArePositive ==
    \A r \in postgres_records : r.project_id >= 1

StoragePrefixIdsArePositive ==
    \A s \in storage_prefixes : s.prefix_id >= 1


vars == << pc, next_project_id, postgres_records, storage_prefixes, 
           filesystem_dirs, requests_processed, op, response_project_id, 
           response_prefix_id, request_pending, phase >>

ProcSet == {"api"}

Init == (* Global variables *)
        /\ next_project_id = 1
        /\ postgres_records = {}
        /\ storage_prefixes = {}
        /\ filesystem_dirs = {}
        /\ requests_processed = 0
        /\ op = "idle"
        /\ response_project_id = 0
        /\ response_prefix_id = 0
        /\ request_pending = FALSE
        /\ phase = "await_request"
        /\ pc = [self \in ProcSet |-> "AwaitRequest"]

AwaitRequest == /\ pc["api"] = "AwaitRequest"
                /\ IF requests_processed < MaxRequests
                      THEN /\ request_pending' = TRUE
                           /\ phase' = "processing"
                           /\ op' = "request_received"
                           /\ pc' = [pc EXCEPT !["api"] = "AllocateProjectId"]
                      ELSE /\ pc' = [pc EXCEPT !["api"] = "Terminate"]
                           /\ UNCHANGED << op, request_pending, phase >>
                /\ UNCHANGED << next_project_id, postgres_records, 
                                storage_prefixes, filesystem_dirs, 
                                requests_processed, response_project_id, 
                                response_prefix_id >>

AllocateProjectId == /\ pc["api"] = "AllocateProjectId"
                     /\ IF next_project_id > MaxProjectIds
                           THEN /\ op' = "id_exhausted"
                                /\ phase' = "await_request"
                                /\ request_pending' = FALSE
                                /\ pc' = [pc EXCEPT !["api"] = "AwaitRequest"]
                                /\ UNCHANGED << next_project_id, 
                                                response_project_id >>
                           ELSE /\ response_project_id' = next_project_id
                                /\ next_project_id' = next_project_id + 1
                                /\ op' = "id_allocated"
                                /\ pc' = [pc EXCEPT !["api"] = "ProvisionProject"]
                                /\ UNCHANGED << request_pending, phase >>
                     /\ UNCHANGED << postgres_records, storage_prefixes, 
                                     filesystem_dirs, requests_processed, 
                                     response_prefix_id >>

ProvisionProject == /\ pc["api"] = "ProvisionProject"
                    /\ postgres_records' = (                postgres_records \union
                                            {[project_id |-> response_project_id,
                                              status     |-> "active"]})
                    /\ response_prefix_id' = response_project_id
                    /\ storage_prefixes' = (                  storage_prefixes \union
                                            {[project_id |-> response_project_id,
                                              prefix_id  |-> response_project_id]})
                    /\ op' = "project_provisioned"
                    /\ pc' = [pc EXCEPT !["api"] = "SendResponse"]
                    /\ UNCHANGED << next_project_id, filesystem_dirs, 
                                    requests_processed, response_project_id, 
                                    request_pending, phase >>

SendResponse == /\ pc["api"] = "SendResponse"
                /\ phase' = "responded"
                /\ request_pending' = FALSE
                /\ requests_processed' = requests_processed + 1
                /\ op' = "response_sent"
                /\ pc' = [pc EXCEPT !["api"] = "ResetPhase"]
                /\ UNCHANGED << next_project_id, postgres_records, 
                                storage_prefixes, filesystem_dirs, 
                                response_project_id, response_prefix_id >>

ResetPhase == /\ pc["api"] = "ResetPhase"
              /\ phase' = "await_request"
              /\ pc' = [pc EXCEPT !["api"] = "AwaitRequest"]
              /\ UNCHANGED << next_project_id, postgres_records, 
                              storage_prefixes, filesystem_dirs, 
                              requests_processed, op, response_project_id, 
                              response_prefix_id, request_pending >>

Terminate == /\ pc["api"] = "Terminate"
             /\ op' = "handler_finished"
             /\ pc' = [pc EXCEPT !["api"] = "Done"]
             /\ UNCHANGED << next_project_id, postgres_records, 
                             storage_prefixes, filesystem_dirs, 
                             requests_processed, response_project_id, 
                             response_prefix_id, request_pending, phase >>

api_handler == AwaitRequest \/ AllocateProjectId \/ ProvisionProject
                  \/ SendResponse \/ ResetPhase \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == api_handler
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(api_handler)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
