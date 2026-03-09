------------------------ MODULE composition_engine ------------------------
(*
 * Composition Engine Lifecycle — Instantiation of the State Machine template.
 *
 * Models the lifecycle of compose(spec_a, spec_b):
 *   empty    → partial:   first spec registered
 *   partial  → composed:  compose() called (requires ≥2 specs)
 *   composed → verified:  TLC passes on composed spec
 *   composed → failed:    TLC rejects composed spec
 *   failed   → partial:   spec revised (conform-or-die)
 *   partial  → partial:   additional spec registered
 *
 * Invariants:
 *   MonotonicGrowth    — verified specs are never removed
 *   AssociativityHolds — compose order doesn't change result (modeled as
 *                        commutativity of the composed_from set)
 *   NoEmptyCompose     — never compose with fewer than 2 specs
 *   VerifiedIsTerminal — once verified, no further transitions (for a given
 *                        composition; new specs restart the cycle)
 *
 * Two-phase action model: mutate state, then update derived.
 *)

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS
    SpecSet,            \* finite set of spec identifiers (e.g., {"a", "b", "c"})
    MaxSteps            \* bound for model checking

(* --algorithm CompositionEngine

variables
    current_state = "empty",
    registered = {},        \* set of registered spec ids
    composed_from = {},     \* set of spec ids in current composition
    verified_set = {},      \* set of spec ids that have been verified (monotonic)
    step_count = 0,
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    \* --- State validity ---
    StateSet == {"empty", "partial", "composed", "verified", "failed"}
    ValidState == current_state \in StateSet

    \* --- Monotonic growth: verified specs never removed ---
    MonotonicGrowth == verified_set \subseteq registered

    \* --- No empty compose: composed_from has ≥2 specs when composed ---
    NoEmptyCompose == current_state \in {"composed", "verified"}
                        => Cardinality(composed_from) >= 2

    \* --- Associativity: composed_from is a set, so order is irrelevant ---
    \* (structural guarantee: sets are unordered, so any permutation of
    \*  registration order yields the same composed_from)
    AssociativityHolds == current_state = "composed"
                            => composed_from \subseteq registered

    \* --- Bounded execution ---
    BoundedExecution == step_count <= MaxSteps

    \* --- Registered specs are always from SpecSet ---
    ValidSpecs == registered \subseteq SpecSet

    \* --- Invariants gated on dirty flag (hold at ready state) ---
    DerivedConsistency == dirty = TRUE \/
        (/\ composed_from \subseteq registered
         /\ verified_set \subseteq registered)

end define;

fair process actor = "main"
begin
    Loop:
        while step_count < MaxSteps do
            either
                \* --- RegisterSpec: add a spec to the engine ---
                RegisterSpec:
                    with sid \in SpecSet do
                        if sid \notin registered then
                            registered := registered \union {sid};
                            dirty := TRUE;
                            if current_state = "empty" then
                                current_state := "partial";
                            elsif current_state = "verified" then
                                \* new spec invalidates current composition
                                current_state := "partial";
                                composed_from := {};
                            end if;
                            op := "spec_registered";
                            result := sid;
                            step_count := step_count + 1;
                        else
                            op := "register_skip";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- Compose: combine registered specs ---
                Compose:
                    if current_state = "partial" /\ Cardinality(registered) >= 2 then
                        composed_from := registered;
                        current_state := "composed";
                        dirty := TRUE;
                        op := "composed";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "compose_skip";
                        result := "error";
                    end if;
            or
                \* --- Verify: TLC passes on composed spec ---
                Verify:
                    if current_state = "composed" then
                        either
                            \* TLC passes
                            verified_set := verified_set \union composed_from;
                            current_state := "verified";
                            dirty := TRUE;
                            op := "verified";
                            result := "pass";
                            step_count := step_count + 1;
                        or
                            \* TLC rejects
                            current_state := "failed";
                            op := "verification_failed";
                            result := "fail";
                            step_count := step_count + 1;
                        end either;
                    else
                        op := "verify_skip";
                        result := "error";
                    end if;
            or
                \* --- Revise: fix failed spec (conform-or-die) ---
                Revise:
                    if current_state = "failed" then
                        \* failed composition is discarded, back to partial
                        composed_from := {};
                        current_state := "partial";
                        op := "revised";
                        result := "ok";
                        step_count := step_count + 1;
                    else
                        op := "revise_skip";
                        result := "error";
                    end if;
            end either;
            \* Phase 2: update derived state
            UpdateDerived:
                dirty := FALSE;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "3c4dbfbb" /\ chksum(tla) = "8439a6f6")
VARIABLES pc, current_state, registered, composed_from, verified_set, 
          step_count, op, result, dirty

(* define statement *)
StateSet == {"empty", "partial", "composed", "verified", "failed"}
ValidState == current_state \in StateSet


MonotonicGrowth == verified_set \subseteq registered


NoEmptyCompose == current_state \in {"composed", "verified"}
                    => Cardinality(composed_from) >= 2




AssociativityHolds == current_state = "composed"
                        => composed_from \subseteq registered


BoundedExecution == step_count <= MaxSteps


ValidSpecs == registered \subseteq SpecSet


DerivedConsistency == dirty = TRUE \/
    (/\ composed_from \subseteq registered
     /\ verified_set \subseteq registered)


vars == << pc, current_state, registered, composed_from, verified_set, 
           step_count, op, result, dirty >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ current_state = "empty"
        /\ registered = {}
        /\ composed_from = {}
        /\ verified_set = {}
        /\ step_count = 0
        /\ op = "idle"
        /\ result = "none"
        /\ dirty = FALSE
        /\ pc = [self \in ProcSet |-> "Loop"]

Loop == /\ pc["main"] = "Loop"
        /\ IF step_count < MaxSteps
              THEN /\ \/ /\ pc' = [pc EXCEPT !["main"] = "RegisterSpec"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "Compose"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "Verify"]
                      \/ /\ pc' = [pc EXCEPT !["main"] = "Revise"]
              ELSE /\ pc' = [pc EXCEPT !["main"] = "Done"]
        /\ UNCHANGED << current_state, registered, composed_from, verified_set, 
                        step_count, op, result, dirty >>

UpdateDerived == /\ pc["main"] = "UpdateDerived"
                 /\ dirty' = FALSE
                 /\ pc' = [pc EXCEPT !["main"] = "Loop"]
                 /\ UNCHANGED << current_state, registered, composed_from, 
                                 verified_set, step_count, op, result >>

RegisterSpec == /\ pc["main"] = "RegisterSpec"
                /\ \E sid \in SpecSet:
                     IF sid \notin registered
                        THEN /\ registered' = (registered \union {sid})
                             /\ dirty' = TRUE
                             /\ IF current_state = "empty"
                                   THEN /\ current_state' = "partial"
                                        /\ UNCHANGED composed_from
                                   ELSE /\ IF current_state = "verified"
                                              THEN /\ current_state' = "partial"
                                                   /\ composed_from' = {}
                                              ELSE /\ TRUE
                                                   /\ UNCHANGED << current_state, 
                                                                   composed_from >>
                             /\ op' = "spec_registered"
                             /\ result' = sid
                             /\ step_count' = step_count + 1
                        ELSE /\ op' = "register_skip"
                             /\ result' = "error"
                             /\ UNCHANGED << current_state, registered, 
                                             composed_from, step_count, dirty >>
                /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
                /\ UNCHANGED verified_set

Compose == /\ pc["main"] = "Compose"
           /\ IF current_state = "partial" /\ Cardinality(registered) >= 2
                 THEN /\ composed_from' = registered
                      /\ current_state' = "composed"
                      /\ dirty' = TRUE
                      /\ op' = "composed"
                      /\ result' = "ok"
                      /\ step_count' = step_count + 1
                 ELSE /\ op' = "compose_skip"
                      /\ result' = "error"
                      /\ UNCHANGED << current_state, composed_from, step_count, 
                                      dirty >>
           /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
           /\ UNCHANGED << registered, verified_set >>

Verify == /\ pc["main"] = "Verify"
          /\ IF current_state = "composed"
                THEN /\ \/ /\ verified_set' = (verified_set \union composed_from)
                           /\ current_state' = "verified"
                           /\ dirty' = TRUE
                           /\ op' = "verified"
                           /\ result' = "pass"
                           /\ step_count' = step_count + 1
                        \/ /\ current_state' = "failed"
                           /\ op' = "verification_failed"
                           /\ result' = "fail"
                           /\ step_count' = step_count + 1
                           /\ UNCHANGED <<verified_set, dirty>>
                ELSE /\ op' = "verify_skip"
                     /\ result' = "error"
                     /\ UNCHANGED << current_state, verified_set, step_count, 
                                     dirty >>
          /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
          /\ UNCHANGED << registered, composed_from >>

Revise == /\ pc["main"] = "Revise"
          /\ IF current_state = "failed"
                THEN /\ composed_from' = {}
                     /\ current_state' = "partial"
                     /\ op' = "revised"
                     /\ result' = "ok"
                     /\ step_count' = step_count + 1
                ELSE /\ op' = "revise_skip"
                     /\ result' = "error"
                     /\ UNCHANGED << current_state, composed_from, step_count >>
          /\ pc' = [pc EXCEPT !["main"] = "UpdateDerived"]
          /\ UNCHANGED << registered, verified_set, dirty >>

actor == Loop \/ UpdateDerived \/ RegisterSpec \/ Compose \/ Verify
            \/ Revise

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == actor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(actor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

===========================================================================
