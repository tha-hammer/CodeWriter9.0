---- MODULE SeamUnresolvedFlagged ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Inputs,
    InternalCallInputs,
    NullUuidInputs,
    MaxInputs

UnresolvedInputs == InternalCallInputs \cap NullUuidInputs

(* --algorithm SeamUnresolvedFlagged

variables
    inputs_checked   = {},
    unresolved_found = {},
    mismatches       = {},
    phase            = "scanning",
    current_input    = "none";

define

    AllScanned ==
        phase = "done" => inputs_checked = Inputs

    UnresolvedCorrect ==
        phase = "done" =>
            unresolved_found = UnresolvedInputs

    NoFalseUnresolved ==
        unresolved_found \subseteq UnresolvedInputs

    UnresolvedNotInMismatches ==
        mismatches \cap unresolved_found = {}

    BoundedCheck ==
        Cardinality(inputs_checked) <= MaxInputs

end define;

fair process checker = "checker"
begin
    Iterate:
        while inputs_checked /= Inputs do
            PickInput:
                with i \in (Inputs \ inputs_checked) do
                    current_input := i;
                end with;
            CheckInput:
                if current_input \in InternalCallInputs
                        /\ current_input \in NullUuidInputs then
                    unresolved_found := unresolved_found \cup {current_input};
                    inputs_checked   := inputs_checked   \cup {current_input};
                    current_input    := "none";
                else
                    inputs_checked := inputs_checked \cup {current_input};
                    current_input  := "none";
                end if;
        end while;
    Terminate:
        phase := "done";
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "6a257c19" /\ chksum(tla) = "aba11b1")
VARIABLES pc, inputs_checked, unresolved_found, mismatches, phase, 
          current_input

(* define statement *)
AllScanned ==
    phase = "done" => inputs_checked = Inputs

UnresolvedCorrect ==
    phase = "done" =>
        unresolved_found = UnresolvedInputs

NoFalseUnresolved ==
    unresolved_found \subseteq UnresolvedInputs

UnresolvedNotInMismatches ==
    mismatches \cap unresolved_found = {}

BoundedCheck ==
    Cardinality(inputs_checked) <= MaxInputs


vars == << pc, inputs_checked, unresolved_found, mismatches, phase, 
           current_input >>

ProcSet == {"checker"}

Init == (* Global variables *)
        /\ inputs_checked = {}
        /\ unresolved_found = {}
        /\ mismatches = {}
        /\ phase = "scanning"
        /\ current_input = "none"
        /\ pc = [self \in ProcSet |-> "Iterate"]

Iterate == /\ pc["checker"] = "Iterate"
           /\ IF inputs_checked /= Inputs
                 THEN /\ pc' = [pc EXCEPT !["checker"] = "PickInput"]
                 ELSE /\ pc' = [pc EXCEPT !["checker"] = "Terminate"]
           /\ UNCHANGED << inputs_checked, unresolved_found, mismatches, phase, 
                           current_input >>

PickInput == /\ pc["checker"] = "PickInput"
             /\ \E i \in (Inputs \ inputs_checked):
                  current_input' = i
             /\ pc' = [pc EXCEPT !["checker"] = "CheckInput"]
             /\ UNCHANGED << inputs_checked, unresolved_found, mismatches, 
                             phase >>

CheckInput == /\ pc["checker"] = "CheckInput"
              /\ IF current_input \in InternalCallInputs
                         /\ current_input \in NullUuidInputs
                    THEN /\ unresolved_found' = (unresolved_found \cup {current_input})
                         /\ inputs_checked' = (inputs_checked   \cup {current_input})
                         /\ current_input' = "none"
                    ELSE /\ inputs_checked' = (inputs_checked \cup {current_input})
                         /\ current_input' = "none"
                         /\ UNCHANGED unresolved_found
              /\ pc' = [pc EXCEPT !["checker"] = "Iterate"]
              /\ UNCHANGED << mismatches, phase >>

Terminate == /\ pc["checker"] = "Terminate"
             /\ phase' = "done"
             /\ pc' = [pc EXCEPT !["checker"] = "Done"]
             /\ UNCHANGED << inputs_checked, unresolved_found, mismatches, 
                             current_input >>

checker == Iterate \/ PickInput \/ CheckInput \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == checker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(checker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

TypeInvariant ==
    /\ inputs_checked   \subseteq Inputs
    /\ unresolved_found \subseteq Inputs
    /\ mismatches       \subseteq Inputs
    /\ phase            \in {"scanning", "done"}
    /\ current_input    \in (Inputs \cup {"none"})

====
