---- MODULE RegisterIdempotent ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    InputCriteria,
    MaxSteps

ASSUME InputCriteria # {}

(* --algorithm RegisterIdempotent

variables
  bindings        = [c \in {} |-> 0],
  dag_nodes       = {},
  next_id         = 1,
  to_process      = {},
  registered      = {},
  phase           = "first_inv",
  call_count      = 0,
  call_count_at_save = 0,
  bindings_at_save = [c \in {} |-> 0],
  step_count      = 0;

define

  IdempotentAllocation ==
    phase = "done" =>
      (\A c \in InputCriteria : bindings[c] = bindings_at_save[c])

  NoDuplicateNodes ==
    Cardinality(dag_nodes) = Cardinality(DOMAIN bindings)

  BindingStable ==
    \A c \in DOMAIN bindings_at_save :
      (c \in DOMAIN bindings) => (bindings[c] = bindings_at_save[c])

  SecondCallSkipsAllocate ==
    phase = "done" => call_count = call_count_at_save

  BoundedExecution == step_count <= MaxSteps

end define;

fair process actor = "main"
begin
  StartFirst:
    to_process := InputCriteria;
    registered := {};
    phase      := "first_inv";
    step_count := step_count + 1;

  ProcessFirstLoop:
    while to_process # {} do
      with c \in to_process do
        if c \in DOMAIN bindings then
          registered := registered \cup {c};
          to_process := to_process \ {c};
        else
          bindings   := bindings @@ (c :> next_id);
          dag_nodes  := dag_nodes \cup {next_id};
          next_id    := next_id + 1;
          call_count := call_count + 1;
          registered := registered \cup {c};
          to_process := to_process \ {c};
        end if;
      end with;
      step_count := step_count + 1;
    end while;

  SaveFirst:
    bindings_at_save   := bindings;
    call_count_at_save := call_count;
    phase              := "second_inv";
    to_process         := InputCriteria;
    registered         := {};
    step_count         := step_count + 1;

  ProcessSecondLoop:
    while to_process # {} do
      with c \in to_process do
        if c \in DOMAIN bindings then
          registered := registered \cup {c};
          to_process := to_process \ {c};
        else
          bindings   := bindings @@ (c :> next_id);
          dag_nodes  := dag_nodes \cup {next_id};
          next_id    := next_id + 1;
          call_count := call_count + 1;
          registered := registered \cup {c};
          to_process := to_process \ {c};
        end if;
      end with;
      step_count := step_count + 1;
    end while;

  Finish:
    phase      := "done";
    step_count := step_count + 1;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3eeb8093" /\ chksum(tla) = "7dc2989c")
VARIABLES pc, bindings, dag_nodes, next_id, to_process, registered, phase, 
          call_count, call_count_at_save, bindings_at_save, step_count

(* define statement *)
IdempotentAllocation ==
  phase = "done" =>
    (\A c \in InputCriteria : bindings[c] = bindings_at_save[c])

NoDuplicateNodes ==
  Cardinality(dag_nodes) = Cardinality(DOMAIN bindings)

BindingStable ==
  \A c \in DOMAIN bindings_at_save :
    (c \in DOMAIN bindings) => (bindings[c] = bindings_at_save[c])

SecondCallSkipsAllocate ==
  phase = "done" => call_count = call_count_at_save

BoundedExecution == step_count <= MaxSteps


vars == << pc, bindings, dag_nodes, next_id, to_process, registered, phase, 
           call_count, call_count_at_save, bindings_at_save, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ bindings = [c \in {} |-> 0]
        /\ dag_nodes = {}
        /\ next_id = 1
        /\ to_process = {}
        /\ registered = {}
        /\ phase = "first_inv"
        /\ call_count = 0
        /\ call_count_at_save = 0
        /\ bindings_at_save = [c \in {} |-> 0]
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "StartFirst"]

StartFirst == /\ pc["main"] = "StartFirst"
              /\ to_process' = InputCriteria
              /\ registered' = {}
              /\ phase' = "first_inv"
              /\ step_count' = step_count + 1
              /\ pc' = [pc EXCEPT !["main"] = "ProcessFirstLoop"]
              /\ UNCHANGED << bindings, dag_nodes, next_id, call_count, 
                              call_count_at_save, bindings_at_save >>

ProcessFirstLoop == /\ pc["main"] = "ProcessFirstLoop"
                    /\ IF to_process # {}
                          THEN /\ \E c \in to_process:
                                    IF c \in DOMAIN bindings
                                       THEN /\ registered' = (registered \cup {c})
                                            /\ to_process' = to_process \ {c}
                                            /\ UNCHANGED << bindings, 
                                                            dag_nodes, next_id, 
                                                            call_count >>
                                       ELSE /\ bindings' = bindings @@ (c :> next_id)
                                            /\ dag_nodes' = (dag_nodes \cup {next_id})
                                            /\ next_id' = next_id + 1
                                            /\ call_count' = call_count + 1
                                            /\ registered' = (registered \cup {c})
                                            /\ to_process' = to_process \ {c}
                               /\ step_count' = step_count + 1
                               /\ pc' = [pc EXCEPT !["main"] = "ProcessFirstLoop"]
                          ELSE /\ pc' = [pc EXCEPT !["main"] = "SaveFirst"]
                               /\ UNCHANGED << bindings, dag_nodes, next_id, 
                                               to_process, registered, 
                                               call_count, step_count >>
                    /\ UNCHANGED << phase, call_count_at_save, 
                                    bindings_at_save >>

SaveFirst == /\ pc["main"] = "SaveFirst"
             /\ bindings_at_save' = bindings
             /\ call_count_at_save' = call_count
             /\ phase' = "second_inv"
             /\ to_process' = InputCriteria
             /\ registered' = {}
             /\ step_count' = step_count + 1
             /\ pc' = [pc EXCEPT !["main"] = "ProcessSecondLoop"]
             /\ UNCHANGED << bindings, dag_nodes, next_id, call_count >>

ProcessSecondLoop == /\ pc["main"] = "ProcessSecondLoop"
                     /\ IF to_process # {}
                           THEN /\ \E c \in to_process:
                                     IF c \in DOMAIN bindings
                                        THEN /\ registered' = (registered \cup {c})
                                             /\ to_process' = to_process \ {c}
                                             /\ UNCHANGED << bindings, 
                                                             dag_nodes, 
                                                             next_id, 
                                                             call_count >>
                                        ELSE /\ bindings' = bindings @@ (c :> next_id)
                                             /\ dag_nodes' = (dag_nodes \cup {next_id})
                                             /\ next_id' = next_id + 1
                                             /\ call_count' = call_count + 1
                                             /\ registered' = (registered \cup {c})
                                             /\ to_process' = to_process \ {c}
                                /\ step_count' = step_count + 1
                                /\ pc' = [pc EXCEPT !["main"] = "ProcessSecondLoop"]
                           ELSE /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                                /\ UNCHANGED << bindings, dag_nodes, next_id, 
                                                to_process, registered, 
                                                call_count, step_count >>
                     /\ UNCHANGED << phase, call_count_at_save, 
                                     bindings_at_save >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "done"
          /\ step_count' = step_count + 1
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << bindings, dag_nodes, next_id, to_process, registered, 
                          call_count, call_count_at_save, bindings_at_save >>

actor == StartFirst \/ ProcessFirstLoop \/ SaveFirst \/ ProcessSecondLoop
            \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == actor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(actor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
