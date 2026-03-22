---- MODULE SeamMismatchDetected ----
EXTENDS Integers, FiniteSets, TLC
(*--algorithm SeamMismatchDetected
variables
  caller_ok_type  = "DictStrAny",
  callee_exp_type = "Config",
  caller_uuid = "aaaa1111",
  callee_uuid = "bbbb2222",
  caller_fn   = "get_config",
  callee_fn   = "process",
  result = {},
  phase  = "idle";
define
  CompatPairs ==
    { <<"Str",       "Str">>,
      <<"StrOrNone", "StrOrNone">>,
      <<"Config",    "Config">> }
  TypeCompatible(p, e) == <<p, e>> \in CompatPairs
  SeverityCorrect ==
    \A m \in result : m.severity = "type_mismatch"
  MismatchDetected ==
    phase = "done" =>
      (~TypeCompatible(caller_ok_type, callee_exp_type) => result /= {})
  MismatchCorrect ==
    phase = "done" =>
      (~TypeCompatible(caller_ok_type, callee_exp_type) =>
        \E m \in result :
          /\ m.expected_type = callee_exp_type
          /\ m.provided_type = caller_ok_type
          /\ m.severity      = "type_mismatch")
  NoSpuriousMismatches ==
    phase = "done" =>
      \A m \in result :
        /\ m.expected_type = callee_exp_type
        /\ m.provided_type = caller_ok_type
        /\ ~TypeCompatible(caller_ok_type, callee_exp_type)
        /\ m.severity = "type_mismatch"
end define;
fair process checker = "checker"
begin
  StartCheck:
    phase := "checking";
  CheckTypes:
    if ~TypeCompatible(caller_ok_type, callee_exp_type) then
      result := { [ caller_uuid       |-> caller_uuid,
                    callee_uuid       |-> callee_uuid,
                    caller_function   |-> caller_fn,
                    callee_function   |-> callee_fn,
                    callee_input_name |-> "config",
                    expected_type     |-> callee_exp_type,
                    provided_type     |-> caller_ok_type,
                    severity          |-> "type_mismatch" ] };
    end if;
  Finish:
    phase := "done";
end process;
end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "ac2579a2" /\ chksum(tla) = "71a076ce")
VARIABLES pc, caller_ok_type, callee_exp_type, caller_uuid, callee_uuid, 
          caller_fn, callee_fn, result, phase

(* define statement *)
CompatPairs ==
  { <<"Str",       "Str">>,
    <<"StrOrNone", "StrOrNone">>,
    <<"Config",    "Config">> }
TypeCompatible(p, e) == <<p, e>> \in CompatPairs
SeverityCorrect ==
  \A m \in result : m.severity = "type_mismatch"
MismatchDetected ==
  phase = "done" =>
    (~TypeCompatible(caller_ok_type, callee_exp_type) => result /= {})
MismatchCorrect ==
  phase = "done" =>
    (~TypeCompatible(caller_ok_type, callee_exp_type) =>
      \E m \in result :
        /\ m.expected_type = callee_exp_type
        /\ m.provided_type = caller_ok_type
        /\ m.severity      = "type_mismatch")
NoSpuriousMismatches ==
  phase = "done" =>
    \A m \in result :
      /\ m.expected_type = callee_exp_type
      /\ m.provided_type = caller_ok_type
      /\ ~TypeCompatible(caller_ok_type, callee_exp_type)
      /\ m.severity = "type_mismatch"


vars == << pc, caller_ok_type, callee_exp_type, caller_uuid, callee_uuid, 
           caller_fn, callee_fn, result, phase >>

ProcSet == {"checker"}

Init == (* Global variables *)
        /\ caller_ok_type = "DictStrAny"
        /\ callee_exp_type = "Config"
        /\ caller_uuid = "aaaa1111"
        /\ callee_uuid = "bbbb2222"
        /\ caller_fn = "get_config"
        /\ callee_fn = "process"
        /\ result = {}
        /\ phase = "idle"
        /\ pc = [self \in ProcSet |-> "StartCheck"]

StartCheck == /\ pc["checker"] = "StartCheck"
              /\ phase' = "checking"
              /\ pc' = [pc EXCEPT !["checker"] = "CheckTypes"]
              /\ UNCHANGED << caller_ok_type, callee_exp_type, caller_uuid, 
                              callee_uuid, caller_fn, callee_fn, result >>

CheckTypes == /\ pc["checker"] = "CheckTypes"
              /\ IF ~TypeCompatible(caller_ok_type, callee_exp_type)
                    THEN /\ result' = { [ caller_uuid       |-> caller_uuid,
                                          callee_uuid       |-> callee_uuid,
                                          caller_function   |-> caller_fn,
                                          callee_function   |-> callee_fn,
                                          callee_input_name |-> "config",
                                          expected_type     |-> callee_exp_type,
                                          provided_type     |-> caller_ok_type,
                                          severity          |-> "type_mismatch" ] }
                    ELSE /\ TRUE
                         /\ UNCHANGED result
              /\ pc' = [pc EXCEPT !["checker"] = "Finish"]
              /\ UNCHANGED << caller_ok_type, callee_exp_type, caller_uuid, 
                              callee_uuid, caller_fn, callee_fn, phase >>

Finish == /\ pc["checker"] = "Finish"
          /\ phase' = "done"
          /\ pc' = [pc EXCEPT !["checker"] = "Done"]
          /\ UNCHANGED << caller_ok_type, callee_exp_type, caller_uuid, 
                          callee_uuid, caller_fn, callee_fn, result >>

checker == StartCheck \/ CheckTypes \/ Finish

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
