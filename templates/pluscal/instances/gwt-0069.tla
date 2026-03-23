---- MODULE BehavioralContracts ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Rules,
    Edges,
    EdgeCallee,
    EdgeCaller,
    FnOuts,
    RuleMatches,
    RuleRequiredOuts,
    DefaultVal

(* --algorithm BehavioralContracts

variables
    violations         = {},
    satisfied_count    = 0,
    checked_count      = 0,
    pending_edges      = Edges,
    current_edge       = DefaultVal,
    pending_rules      = {},
    current_rule       = DefaultVal,
    edge_matched       = FALSE,
    edge_has_violation = FALSE,
    done               = FALSE;

define

    ViolatedEdges ==
        {e \in Edges : \E v \in violations : v.edge = e}

    CountConsistency ==
        done =>
            (checked_count = satisfied_count + Cardinality(ViolatedEdges))

    ViolationComplete ==
        \A v \in violations :
            /\ v.rule        \in Rules
            /\ v.edge        \in Edges
            /\ v.missing_out \in RuleRequiredOuts[v.rule]

    NoFalsePositives ==
        \A v \in violations :
            v.missing_out \notin FnOuts[v.callee]

    NoMatchNoViolation ==
        \A v \in violations :
            <<v.rule, v.edge>> \in RuleMatches

    EmptyEdgesImpliesEmptyReport ==
        Edges = {} =>
            (violations = {} /\ satisfied_count = 0 /\ checked_count = 0)

    ZeroViolationsWhenAllCompliant ==
        (done /\
         (\A e \in Edges : \A r \in Rules :
             <<r, e>> \in RuleMatches =>
             RuleRequiredOuts[r] \subseteq FnOuts[EdgeCallee[e]]))
        => (violations = {})

    NoMatchNoCount ==
        done =>
            (\A e \in Edges :
                (\A r \in Rules : <<r, e>> \notin RuleMatches) =>
                e \notin ViolatedEdges)

end define;

fair process checker = "checker"
begin
    PickEdge:
        if pending_edges # {} then
            with e \in pending_edges do
                current_edge       := e;
                pending_edges      := pending_edges \ {e};
                pending_rules      := Rules;
                edge_matched       := FALSE;
                edge_has_violation := FALSE;
            end with;
            goto CheckRules;
        else
            goto Finish;
        end if;

    CheckRules:
        if pending_rules # {} then
            with r \in pending_rules do
                current_rule  := r;
                pending_rules := pending_rules \ {r};
            end with;
            if <<current_rule, current_edge>> \in RuleMatches then
                edge_matched := TRUE;
                goto CheckOuts;
            else
                goto CheckRules;
            end if;
        else
            goto FinalizeEdge;
        end if;

    CheckOuts:
        with missing = RuleRequiredOuts[current_rule] \ FnOuts[EdgeCallee[current_edge]] do
            violations := violations \union
                { [ rule        |-> current_rule,
                    edge        |-> current_edge,
                    callee      |-> EdgeCallee[current_edge],
                    caller      |-> EdgeCaller[current_edge],
                    missing_out |-> out ] : out \in missing };
            if missing # {} then
                edge_has_violation := TRUE;
            end if;
        end with;
        goto CheckRules;

    FinalizeEdge:
        if edge_matched then
            checked_count := checked_count + 1;
        end if;

    AfterCheckedCount:
        if edge_matched /\ ~edge_has_violation then
            satisfied_count := satisfied_count + 1;
        end if;
        goto PickEdge;

    Finish:
        done := TRUE;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "1c5de269" /\ chksum(tla) = "5383a80f")
VARIABLES pc, violations, satisfied_count, checked_count, pending_edges, 
          current_edge, pending_rules, current_rule, edge_matched, 
          edge_has_violation, done

(* define statement *)
ViolatedEdges ==
    {e \in Edges : \E v \in violations : v.edge = e}

CountConsistency ==
    done =>
        (checked_count = satisfied_count + Cardinality(ViolatedEdges))

ViolationComplete ==
    \A v \in violations :
        /\ v.rule        \in Rules
        /\ v.edge        \in Edges
        /\ v.missing_out \in RuleRequiredOuts[v.rule]

NoFalsePositives ==
    \A v \in violations :
        v.missing_out \notin FnOuts[v.callee]

NoMatchNoViolation ==
    \A v \in violations :
        <<v.rule, v.edge>> \in RuleMatches

EmptyEdgesImpliesEmptyReport ==
    Edges = {} =>
        (violations = {} /\ satisfied_count = 0 /\ checked_count = 0)

ZeroViolationsWhenAllCompliant ==
    (done /\
     (\A e \in Edges : \A r \in Rules :
         <<r, e>> \in RuleMatches =>
         RuleRequiredOuts[r] \subseteq FnOuts[EdgeCallee[e]]))
    => (violations = {})

NoMatchNoCount ==
    done =>
        (\A e \in Edges :
            (\A r \in Rules : <<r, e>> \notin RuleMatches) =>
            e \notin ViolatedEdges)


vars == << pc, violations, satisfied_count, checked_count, pending_edges, 
           current_edge, pending_rules, current_rule, edge_matched, 
           edge_has_violation, done >>

ProcSet == {"checker"}

Init == (* Global variables *)
        /\ violations = {}
        /\ satisfied_count = 0
        /\ checked_count = 0
        /\ pending_edges = Edges
        /\ current_edge = DefaultVal
        /\ pending_rules = {}
        /\ current_rule = DefaultVal
        /\ edge_matched = FALSE
        /\ edge_has_violation = FALSE
        /\ done = FALSE
        /\ pc = [self \in ProcSet |-> "PickEdge"]

PickEdge == /\ pc["checker"] = "PickEdge"
            /\ IF pending_edges # {}
                  THEN /\ \E e \in pending_edges:
                            /\ current_edge' = e
                            /\ pending_edges' = pending_edges \ {e}
                            /\ pending_rules' = Rules
                            /\ edge_matched' = FALSE
                            /\ edge_has_violation' = FALSE
                       /\ pc' = [pc EXCEPT !["checker"] = "CheckRules"]
                  ELSE /\ pc' = [pc EXCEPT !["checker"] = "Finish"]
                       /\ UNCHANGED << pending_edges, current_edge, 
                                       pending_rules, edge_matched, 
                                       edge_has_violation >>
            /\ UNCHANGED << violations, satisfied_count, checked_count, 
                            current_rule, done >>

CheckRules == /\ pc["checker"] = "CheckRules"
              /\ IF pending_rules # {}
                    THEN /\ \E r \in pending_rules:
                              /\ current_rule' = r
                              /\ pending_rules' = pending_rules \ {r}
                         /\ IF <<current_rule', current_edge>> \in RuleMatches
                               THEN /\ edge_matched' = TRUE
                                    /\ pc' = [pc EXCEPT !["checker"] = "CheckOuts"]
                               ELSE /\ pc' = [pc EXCEPT !["checker"] = "CheckRules"]
                                    /\ UNCHANGED edge_matched
                    ELSE /\ pc' = [pc EXCEPT !["checker"] = "FinalizeEdge"]
                         /\ UNCHANGED << pending_rules, current_rule, 
                                         edge_matched >>
              /\ UNCHANGED << violations, satisfied_count, checked_count, 
                              pending_edges, current_edge, edge_has_violation, 
                              done >>

CheckOuts == /\ pc["checker"] = "CheckOuts"
             /\ LET missing == RuleRequiredOuts[current_rule] \ FnOuts[EdgeCallee[current_edge]] IN
                  /\ violations' = (          violations \union
                                    { [ rule        |-> current_rule,
                                        edge        |-> current_edge,
                                        callee      |-> EdgeCallee[current_edge],
                                        caller      |-> EdgeCaller[current_edge],
                                        missing_out |-> out ] : out \in missing })
                  /\ IF missing # {}
                        THEN /\ edge_has_violation' = TRUE
                        ELSE /\ TRUE
                             /\ UNCHANGED edge_has_violation
             /\ pc' = [pc EXCEPT !["checker"] = "CheckRules"]
             /\ UNCHANGED << satisfied_count, checked_count, pending_edges, 
                             current_edge, pending_rules, current_rule, 
                             edge_matched, done >>

FinalizeEdge == /\ pc["checker"] = "FinalizeEdge"
                /\ IF edge_matched
                      THEN /\ checked_count' = checked_count + 1
                      ELSE /\ TRUE
                           /\ UNCHANGED checked_count
                /\ pc' = [pc EXCEPT !["checker"] = "AfterCheckedCount"]
                /\ UNCHANGED << violations, satisfied_count, pending_edges, 
                                current_edge, pending_rules, current_rule, 
                                edge_matched, edge_has_violation, done >>

AfterCheckedCount == /\ pc["checker"] = "AfterCheckedCount"
                     /\ IF edge_matched /\ ~edge_has_violation
                           THEN /\ satisfied_count' = satisfied_count + 1
                           ELSE /\ TRUE
                                /\ UNCHANGED satisfied_count
                     /\ pc' = [pc EXCEPT !["checker"] = "PickEdge"]
                     /\ UNCHANGED << violations, checked_count, pending_edges, 
                                     current_edge, pending_rules, current_rule, 
                                     edge_matched, edge_has_violation, done >>

Finish == /\ pc["checker"] = "Finish"
          /\ done' = TRUE
          /\ pc' = [pc EXCEPT !["checker"] = "Done"]
          /\ UNCHANGED << violations, satisfied_count, checked_count, 
                          pending_edges, current_edge, pending_rules, 
                          current_rule, edge_matched, edge_has_violation >>

checker == PickEdge \/ CheckRules \/ CheckOuts \/ FinalizeEdge
              \/ AfterCheckedCount \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == checker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(checker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
