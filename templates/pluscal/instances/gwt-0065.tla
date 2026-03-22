---- MODULE SeamSatisfiedNoReport ----

EXTENDS Integers, FiniteSets, TLC

TypeValues == {"listFnRecord", "str", "strOrNone"}

CompatPairs == { <<"listFnRecord", "listFnRecord">>,
                 <<"str",          "str">>,
                 <<"str",          "strOrNone">>,
                 <<"strOrNone",    "strOrNone">> }

CallerOkType == "listFnRecord"
CalleeInType  == "listFnRecord"

(*--algorithm SeamSatisfiedNoReport

variables
    provided_type = CallerOkType,
    expected_type = CalleeInType,
    compatible    = FALSE,
    result        = {},
    phase         = "init";

define

    PhaseValid ==
        phase \in {"init", "checking", "confirming", "done"}

    ReflexiveCompatPairs ==
        \A t \in TypeValues : <<t, t>> \in CompatPairs

    NoFalsePositive ==
        (phase = "done" /\ <<provided_type, expected_type>> \in CompatPairs)
            => result = {}

    SeamSatisfied ==
        phase = "done" => result = {}

end define;

fair process checker = "seam_checker"
begin
    Start:
        phase := "checking";

    CheckSeam:
        if <<provided_type, expected_type>> \in CompatPairs then
            compatible := TRUE;
            phase := "confirming";
        else
            compatible := FALSE;
            phase := "confirming";
        end if;

    ConfirmCompatible:
        if compatible = TRUE then
            result := {};
            phase := "done";
        else
            result := { [ provided_type |-> provided_type,
                          expected_type |-> expected_type,
                          severity      |-> "type_mismatch" ] };
            phase := "done";
        end if;

    Finish:
        assert result = {};
        assert compatible = TRUE;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "1b1f5b6d" /\ chksum(tla) = "22ab4a9d")
VARIABLES pc, provided_type, expected_type, compatible, result, phase

(* define statement *)
PhaseValid ==
    phase \in {"init", "checking", "confirming", "done"}

ReflexiveCompatPairs ==
    \A t \in TypeValues : <<t, t>> \in CompatPairs

NoFalsePositive ==
    (phase = "done" /\ <<provided_type, expected_type>> \in CompatPairs)
        => result = {}

SeamSatisfied ==
    phase = "done" => result = {}


vars == << pc, provided_type, expected_type, compatible, result, phase >>

ProcSet == {"seam_checker"}

Init == (* Global variables *)
        /\ provided_type = CallerOkType
        /\ expected_type = CalleeInType
        /\ compatible = FALSE
        /\ result = {}
        /\ phase = "init"
        /\ pc = [self \in ProcSet |-> "Start"]

Start == /\ pc["seam_checker"] = "Start"
         /\ phase' = "checking"
         /\ pc' = [pc EXCEPT !["seam_checker"] = "CheckSeam"]
         /\ UNCHANGED << provided_type, expected_type, compatible, result >>

CheckSeam == /\ pc["seam_checker"] = "CheckSeam"
             /\ IF <<provided_type, expected_type>> \in CompatPairs
                   THEN /\ compatible' = TRUE
                        /\ phase' = "confirming"
                   ELSE /\ compatible' = FALSE
                        /\ phase' = "confirming"
             /\ pc' = [pc EXCEPT !["seam_checker"] = "ConfirmCompatible"]
             /\ UNCHANGED << provided_type, expected_type, result >>

ConfirmCompatible == /\ pc["seam_checker"] = "ConfirmCompatible"
                     /\ IF compatible = TRUE
                           THEN /\ result' = {}
                                /\ phase' = "done"
                           ELSE /\ result' = { [ provided_type |-> provided_type,
                                                 expected_type |-> expected_type,
                                                 severity      |-> "type_mismatch" ] }
                                /\ phase' = "done"
                     /\ pc' = [pc EXCEPT !["seam_checker"] = "Finish"]
                     /\ UNCHANGED << provided_type, expected_type, compatible >>

Finish == /\ pc["seam_checker"] = "Finish"
          /\ Assert(result = {}, 
                    "Failure of assertion at line 67, column 9.")
          /\ Assert(compatible = TRUE, 
                    "Failure of assertion at line 68, column 9.")
          /\ pc' = [pc EXCEPT !["seam_checker"] = "Done"]
          /\ UNCHANGED << provided_type, expected_type, compatible, result, 
                          phase >>

checker == Start \/ CheckSeam \/ ConfirmCompatible \/ Finish

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
