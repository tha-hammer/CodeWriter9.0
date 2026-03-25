---- MODULE PassDependencyBlocking ----

EXTENDS Integers, Sequences, FiniteSets, TLC

PASSES == {"artifacts", "coverage", "interaction", "abstraction_gap", "imports"}

DEPS ==
  ("artifacts"       :> {}) @@
  ("coverage"        :> {"artifacts"}) @@
  ("interaction"     :> {"artifacts"}) @@
  ("abstraction_gap" :> {"coverage", "interaction"}) @@
  ("imports"         :> {"abstraction_gap"})

TOPO == <<"artifacts", "coverage", "interaction", "abstraction_gap", "imports">>

BLOCKING  == {"FAIL", "blocked"}
SATISFIED == {"PASS", "WARNING"}
TERMINAL  == {"PASS", "WARNING", "FAIL", "blocked"}

(* --algorithm PassDependencyBlocking

variables
  passStatus = [p \in PASSES |-> "pending"],
  ran        = {},
  idx        = 1;

define

  AnyDepBlocking(p) ==
    \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

  DirectBlockInvariant ==
    \A p \in PASSES :
      passStatus[p] = "blocked" =>
        \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

  BlockedNeverRan ==
    \A p \in PASSES : passStatus[p] = "blocked" => p \notin ran

  NeverRunBlocked ==
    \A p \in ran : passStatus[p] # "blocked"

  ScheduledOnlySatisfied ==
    \A p \in ran :
      \A dep \in DEPS[p] : passStatus[dep] \in SATISFIED

  PartialSuccessInvariant ==
    \A p \in PASSES :
      ( passStatus[p] \in SATISFIED /\
        \A dep \in DEPS[p] : passStatus[dep] \in SATISFIED ) =>
      p \in ran

  BlockedDistinctFromFail ==
    \A p \in PASSES :
      ~( passStatus[p] = "blocked" /\ passStatus[p] = "FAIL" )

  FinalAllResolved ==
    idx > Len(TOPO) =>
      \A p \in PASSES : passStatus[p] \in TERMINAL

  TransitiveBlockWitness ==
    \A p \in PASSES :
      passStatus[p] = "blocked" =>
        \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

end define;

fair process scheduler = "main"
variables cp = "";
begin
  ProcessPasses:
    while idx <= Len(TOPO) do
      cp := TOPO[idx];
      if AnyDepBlocking(cp) then
        passStatus[cp] := "blocked";
      else
        either
          passStatus[cp] := "PASS";
        or
          passStatus[cp] := "WARNING";
        or
          passStatus[cp] := "FAIL";
        end either;
        ran := ran \cup {cp};
      end if;
      idx := idx + 1;
    end while;
  Finish:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8a173339" /\ chksum(tla) = "8a0f39ff")
VARIABLES pc, passStatus, ran, idx

(* define statement *)
AnyDepBlocking(p) ==
  \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

DirectBlockInvariant ==
  \A p \in PASSES :
    passStatus[p] = "blocked" =>
      \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

BlockedNeverRan ==
  \A p \in PASSES : passStatus[p] = "blocked" => p \notin ran

NeverRunBlocked ==
  \A p \in ran : passStatus[p] # "blocked"

ScheduledOnlySatisfied ==
  \A p \in ran :
    \A dep \in DEPS[p] : passStatus[dep] \in SATISFIED

PartialSuccessInvariant ==
  \A p \in PASSES :
    ( passStatus[p] \in SATISFIED /\
      \A dep \in DEPS[p] : passStatus[dep] \in SATISFIED ) =>
    p \in ran

BlockedDistinctFromFail ==
  \A p \in PASSES :
    ~( passStatus[p] = "blocked" /\ passStatus[p] = "FAIL" )

FinalAllResolved ==
  idx > Len(TOPO) =>
    \A p \in PASSES : passStatus[p] \in TERMINAL

TransitiveBlockWitness ==
  \A p \in PASSES :
    passStatus[p] = "blocked" =>
      \E dep \in DEPS[p] : passStatus[dep] \in BLOCKING

VARIABLE cp

vars == << pc, passStatus, ran, idx, cp >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ passStatus = [p \in PASSES |-> "pending"]
        /\ ran = {}
        /\ idx = 1
        (* Process scheduler *)
        /\ cp = ""
        /\ pc = [self \in ProcSet |-> "ProcessPasses"]

ProcessPasses == /\ pc["main"] = "ProcessPasses"
                 /\ IF idx <= Len(TOPO)
                       THEN /\ cp' = TOPO[idx]
                            /\ IF AnyDepBlocking(cp')
                                  THEN /\ passStatus' = [passStatus EXCEPT ![cp'] = "blocked"]
                                       /\ ran' = ran
                                  ELSE /\ \/ /\ passStatus' = [passStatus EXCEPT ![cp'] = "PASS"]
                                          \/ /\ passStatus' = [passStatus EXCEPT ![cp'] = "WARNING"]
                                          \/ /\ passStatus' = [passStatus EXCEPT ![cp'] = "FAIL"]
                                       /\ ran' = (ran \cup {cp'})
                            /\ idx' = idx + 1
                            /\ pc' = [pc EXCEPT !["main"] = "ProcessPasses"]
                       ELSE /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                            /\ UNCHANGED << passStatus, ran, idx, cp >>

Finish == /\ pc["main"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << passStatus, ran, idx, cp >>

scheduler == ProcessPasses \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == scheduler
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(scheduler)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM Spec => []DirectBlockInvariant
THEOREM Spec => []BlockedNeverRan
THEOREM Spec => []NeverRunBlocked
THEOREM Spec => []ScheduledOnlySatisfied
THEOREM Spec => []PartialSuccessInvariant
THEOREM Spec => []BlockedDistinctFromFail
THEOREM Spec => []FinalAllResolved
THEOREM Spec => []TransitiveBlockWitness

====
