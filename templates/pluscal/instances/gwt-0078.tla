---- MODULE ArtifactsGate ----
EXTENDS Integers, FiniteSets, TLC

Verdict       == {"pass", "fail", "warning", "unknown"}
ArtifactsCost == 10
ParallelCost  == 10

(* --algorithm ArtifactsGate

variables
    artifacts_verdict = "fail",
    gate_checked      = FALSE,
    passes_started    = {},
    final_result      = [
        status     |-> "none",
        blocked_by |-> "none",
        results    |-> [x \in {} |-> 0],
        total_cost |-> 0
    ];

define

    GateBlocking ==
        (gate_checked /\ artifacts_verdict = "fail") =>
            (DOMAIN final_result.results = {"artifacts"} /\
             passes_started = {"artifacts"})

    GatePassthrough ==
        (final_result.status \in {"pass", "warning"}) =>
            ({"artifacts", "coverage", "security"} \subseteq passes_started)

    BlockedStatus ==
        (final_result.status = "blocked") <=>
            (gate_checked /\ artifacts_verdict = "fail")

    CostAccuracy ==
        (final_result.status = "blocked") =>
            (final_result.total_cost = ArtifactsCost)

    OnlyArtifactsWhenBlocked ==
        (final_result.status = "blocked") =>
            DOMAIN final_result.results = {"artifacts"}

    NoExtraPassesWhenBlocked ==
        (final_result.status = "blocked") =>
            passes_started = {"artifacts"}

    TypeOK ==
        /\ gate_checked      \in BOOLEAN
        /\ passes_started    \subseteq {"artifacts", "coverage", "security"}
        /\ artifacts_verdict \in Verdict
        /\ final_result.status \in {"none", "blocked", "pass", "fail", "warning"}

end define;

fair process orchestrator = "main"
begin
    SelectVerdict:
        with v \in Verdict do
            artifacts_verdict := v;
        end with;

    RunArtifacts:
        passes_started := {"artifacts"};

    CheckGate:
        gate_checked := TRUE;
        if artifacts_verdict = "fail" then
            final_result := [
                status     |-> "blocked",
                blocked_by |-> "artifacts",
                results    |-> [n \in {"artifacts"} |->
                                   [name     |-> "artifacts",
                                    verdict  |-> artifacts_verdict,
                                    cost_usd |-> ArtifactsCost]],
                total_cost |-> ArtifactsCost
            ];
            goto Terminate;
        end if;

    RunParallel:
        passes_started := passes_started \union {"coverage", "security"};
        final_result := [
            status     |-> IF artifacts_verdict = "warning" THEN "warning" ELSE "pass",
            blocked_by |-> "none",
            results    |-> [n \in {"artifacts", "coverage", "security"} |->
                               IF n = "artifacts"
                               THEN [name     |-> "artifacts",
                                     verdict  |-> artifacts_verdict,
                                     cost_usd |-> ArtifactsCost]
                               ELSE IF n = "coverage"
                               THEN [name     |-> "coverage",
                                     verdict  |-> "pass",
                                     cost_usd |-> 5]
                               ELSE [name     |-> "security",
                                     verdict  |-> "pass",
                                     cost_usd |-> 5]
                           ],
            total_cost |-> ArtifactsCost + ParallelCost
        ];

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "760c13b0" /\ chksum(tla) = "73fd73e2")
VARIABLES pc, artifacts_verdict, gate_checked, passes_started, final_result

(* define statement *)
GateBlocking ==
    (gate_checked /\ artifacts_verdict = "fail") =>
        (DOMAIN final_result.results = {"artifacts"} /\
         passes_started = {"artifacts"})

GatePassthrough ==
    (final_result.status \in {"pass", "warning"}) =>
        ({"artifacts", "coverage", "security"} \subseteq passes_started)

BlockedStatus ==
    (final_result.status = "blocked") <=>
        (gate_checked /\ artifacts_verdict = "fail")

CostAccuracy ==
    (final_result.status = "blocked") =>
        (final_result.total_cost = ArtifactsCost)

OnlyArtifactsWhenBlocked ==
    (final_result.status = "blocked") =>
        DOMAIN final_result.results = {"artifacts"}

NoExtraPassesWhenBlocked ==
    (final_result.status = "blocked") =>
        passes_started = {"artifacts"}

TypeOK ==
    /\ gate_checked      \in BOOLEAN
    /\ passes_started    \subseteq {"artifacts", "coverage", "security"}
    /\ artifacts_verdict \in Verdict
    /\ final_result.status \in {"none", "blocked", "pass", "fail", "warning"}


vars == << pc, artifacts_verdict, gate_checked, passes_started, final_result
        >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ artifacts_verdict = "fail"
        /\ gate_checked = FALSE
        /\ passes_started = {}
        /\ final_result =                     [
                              status     |-> "none",
                              blocked_by |-> "none",
                              results    |-> [x \in {} |-> 0],
                              total_cost |-> 0
                          ]
        /\ pc = [self \in ProcSet |-> "SelectVerdict"]

SelectVerdict == /\ pc["main"] = "SelectVerdict"
                 /\ \E v \in Verdict:
                      artifacts_verdict' = v
                 /\ pc' = [pc EXCEPT !["main"] = "RunArtifacts"]
                 /\ UNCHANGED << gate_checked, passes_started, final_result >>

RunArtifacts == /\ pc["main"] = "RunArtifacts"
                /\ passes_started' = {"artifacts"}
                /\ pc' = [pc EXCEPT !["main"] = "CheckGate"]
                /\ UNCHANGED << artifacts_verdict, gate_checked, final_result >>

CheckGate == /\ pc["main"] = "CheckGate"
             /\ gate_checked' = TRUE
             /\ IF artifacts_verdict = "fail"
                   THEN /\ final_result' =                 [
                                               status     |-> "blocked",
                                               blocked_by |-> "artifacts",
                                               results    |-> [n \in {"artifacts"} |->
                                                                  [name     |-> "artifacts",
                                                                   verdict  |-> artifacts_verdict,
                                                                   cost_usd |-> ArtifactsCost]],
                                               total_cost |-> ArtifactsCost
                                           ]
                        /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "RunParallel"]
                        /\ UNCHANGED final_result
             /\ UNCHANGED << artifacts_verdict, passes_started >>

RunParallel == /\ pc["main"] = "RunParallel"
               /\ passes_started' = (passes_started \union {"coverage", "security"})
               /\ final_result' =                 [
                                      status     |-> IF artifacts_verdict = "warning" THEN "warning" ELSE "pass",
                                      blocked_by |-> "none",
                                      results    |-> [n \in {"artifacts", "coverage", "security"} |->
                                                         IF n = "artifacts"
                                                         THEN [name     |-> "artifacts",
                                                               verdict  |-> artifacts_verdict,
                                                               cost_usd |-> ArtifactsCost]
                                                         ELSE IF n = "coverage"
                                                         THEN [name     |-> "coverage",
                                                               verdict  |-> "pass",
                                                               cost_usd |-> 5]
                                                         ELSE [name     |-> "security",
                                                               verdict  |-> "pass",
                                                               cost_usd |-> 5]
                                                     ],
                                      total_cost |-> ArtifactsCost + ParallelCost
                                  ]
               /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
               /\ UNCHANGED << artifacts_verdict, gate_checked >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << artifacts_verdict, gate_checked, passes_started, 
                             final_result >>

orchestrator == SelectVerdict \/ RunArtifacts \/ CheckGate \/ RunParallel
                   \/ Terminate

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
