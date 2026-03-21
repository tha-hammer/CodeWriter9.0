---- MODULE DfsBeforeSweep ----

EXTENDS Integers, FiniteSets, TLC

EntryPoints    == {1, 2}
InitialPending == {3, 4}
MaxSteps       == 10

(* --algorithm DfsBeforeSweep

variables
  phase        = "dfs",
  visited      = {},
  pending      = InitialPending,
  dfs_complete = FALSE,
  sweep_active = FALSE,
  step_count   = 0;

define
  PhaseSequencing       == phase = "sweep" => dfs_complete = TRUE
  NoSweepDuringDfs      == phase = "dfs"   => sweep_active = FALSE
  AllEntryPointsVisited == phase /= "dfs"  => visited = EntryPoints
  BoundedExecution      == step_count <= MaxSteps
  Invariants == PhaseSequencing
             /\ NoSweepDuringDfs
             /\ AllEntryPointsVisited
             /\ BoundedExecution
end define;

fair process crawler = "main"
begin
  DfsLoop:
    while visited /= EntryPoints do
      DfsVisit:
        with ep \in EntryPoints \ visited do
          visited    := visited \cup {ep};
          step_count := step_count + 1;
        end with;
    end while;
  DfsFinish:
    dfs_complete := TRUE;
    phase        := "sweep";
  SweepLoop:
    while pending /= {} do
      SweepActivate:
        sweep_active := TRUE;
        step_count   := step_count + 1;
      SweepProcess:
        with p \in pending do
          pending := pending \ {p};
        end with;
      SweepDeactivate:
        sweep_active := FALSE;
        step_count   := step_count + 1;
    end while;
  Terminate:
    phase := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "b675548d" /\ chksum(tla) = "6ffb3a1e")
VARIABLES pc, phase, visited, pending, dfs_complete, sweep_active, step_count

(* define statement *)
PhaseSequencing       == phase = "sweep" => dfs_complete = TRUE
NoSweepDuringDfs      == phase = "dfs"   => sweep_active = FALSE
AllEntryPointsVisited == phase /= "dfs"  => visited = EntryPoints
BoundedExecution      == step_count <= MaxSteps
Invariants == PhaseSequencing
           /\ NoSweepDuringDfs
           /\ AllEntryPointsVisited
           /\ BoundedExecution


vars == << pc, phase, visited, pending, dfs_complete, sweep_active, 
           step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ phase = "dfs"
        /\ visited = {}
        /\ pending = InitialPending
        /\ dfs_complete = FALSE
        /\ sweep_active = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "DfsLoop"]

DfsLoop == /\ pc["main"] = "DfsLoop"
           /\ IF visited /= EntryPoints
                 THEN /\ pc' = [pc EXCEPT !["main"] = "DfsVisit"]
                 ELSE /\ pc' = [pc EXCEPT !["main"] = "DfsFinish"]
           /\ UNCHANGED << phase, visited, pending, dfs_complete, sweep_active, 
                           step_count >>

DfsVisit == /\ pc["main"] = "DfsVisit"
            /\ \E ep \in EntryPoints \ visited:
                 /\ visited' = (visited \cup {ep})
                 /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["main"] = "DfsLoop"]
            /\ UNCHANGED << phase, pending, dfs_complete, sweep_active >>

DfsFinish == /\ pc["main"] = "DfsFinish"
             /\ dfs_complete' = TRUE
             /\ phase' = "sweep"
             /\ pc' = [pc EXCEPT !["main"] = "SweepLoop"]
             /\ UNCHANGED << visited, pending, sweep_active, step_count >>

SweepLoop == /\ pc["main"] = "SweepLoop"
             /\ IF pending /= {}
                   THEN /\ pc' = [pc EXCEPT !["main"] = "SweepActivate"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
             /\ UNCHANGED << phase, visited, pending, dfs_complete, 
                             sweep_active, step_count >>

SweepActivate == /\ pc["main"] = "SweepActivate"
                 /\ sweep_active' = TRUE
                 /\ step_count' = step_count + 1
                 /\ pc' = [pc EXCEPT !["main"] = "SweepProcess"]
                 /\ UNCHANGED << phase, visited, pending, dfs_complete >>

SweepProcess == /\ pc["main"] = "SweepProcess"
                /\ \E p \in pending:
                     pending' = pending \ {p}
                /\ pc' = [pc EXCEPT !["main"] = "SweepDeactivate"]
                /\ UNCHANGED << phase, visited, dfs_complete, sweep_active, 
                                step_count >>

SweepDeactivate == /\ pc["main"] = "SweepDeactivate"
                   /\ sweep_active' = FALSE
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["main"] = "SweepLoop"]
                   /\ UNCHANGED << phase, visited, pending, dfs_complete >>

Terminate == /\ pc["main"] = "Terminate"
             /\ phase' = "done"
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << visited, pending, dfs_complete, sweep_active, 
                             step_count >>

crawler == DfsLoop \/ DfsVisit \/ DfsFinish \/ SweepLoop \/ SweepActivate
              \/ SweepProcess \/ SweepDeactivate \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == crawler
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(crawler)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
