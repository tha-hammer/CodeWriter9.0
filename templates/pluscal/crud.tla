--------------------------- MODULE CRUDTemplate ----------------------------
(*
 * CRUD PlusCal Template — CodeWriter9.0
 *
 * Reusable template for any domain with set-based state, create/read/update/
 * delete actions, and structural invariants. The LLM fills in domain-specific
 * parameters (marked with {{FILL:...}}); the system handles compilation and
 * model checking.
 *
 * Architecture: Two-phase action model.
 *   Phase 1: Mutate primary state (sets dirty flag)
 *   Phase 2: Recompute derived state (clears dirty flag)
 *   Invariants on derived state are gated on dirty=FALSE.
 *   This correctly models TLA+'s simultaneous-assignment semantics.
 *
 * Fill-in markers:
 *   {{FILL:MODULE_NAME}}        — TLA+ module name
 *   {{FILL:RECORD_FIELDS}}      — record field definitions for the primary set
 *   {{FILL:ID_SET}}             — finite set of possible IDs for model checking
 *   {{FILL:RELATION_TYPE_SET}}  — set of relation/edge types (or {} if none)
 *   {{FILL:MAX_RECORDS}}        — bound for model checking
 *   {{FILL:DERIVED_STATE}}      — variables derived from primary state
 *   {{FILL:DERIVED_COMPUTE}}    — operators computing derived state
 *   {{FILL:DERIVED_UPDATE}}     — UpdateDerived label body
 *   {{FILL:PRIMARY_INVARIANTS}} — invariants that always hold (on primary state)
 *   {{FILL:DERIVED_INVARIANTS}} — invariants gated on dirty=FALSE
 *   {{FILL:ACTIONS}}            — domain-specific CRUD action labels
 *
 * To instantiate:
 *   1. Copy this file to templates/pluscal/instances/<name>.tla
 *   2. Fill all {{FILL:...}} markers
 *   3. Compile: java -cp tools/tla2tools.jar pcal.trans <name>.tla
 *   4. Create <name>.cfg with SPECIFICATION Spec, CONSTANTS, INVARIANTS
 *   5. Check:  java -XX:+UseParallelGC -cp tools/tla2tools.jar \
 *              tlc2.TLC <name>.tla -config <name>.cfg -workers auto -nowarning
 *
 * First customer: registry_crud.tla (verifies the registry DAG itself)
 *)

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    IdSet,              \* {{FILL:ID_SET}}
    RelationTypeSet,    \* {{FILL:RELATION_TYPE_SET}}
    MaxRecords          \* {{FILL:MAX_RECORDS}}

(* --algorithm {{FILL:MODULE_NAME}}

variables
    \* --- Primary state ---
    records = {},       \* set of [id |-> ..., {{FILL:RECORD_FIELDS}}]
    relations = {},     \* set of [from |-> ..., to |-> ..., type |-> ...]

    \* --- Derived state (recomputed after each mutation) ---
    \* {{FILL:DERIVED_STATE}}

    \* --- Control ---
    op = "idle",
    result = "none",
    dirty = FALSE;

define
    RecordIds == {r.id : r \in records}

    \* {{FILL:DERIVED_COMPUTE}} — operators for derived state

    \* --- Primary invariants (always hold) ---
    ReferentialIntegrity == \A r \in relations :
        r.from \in RecordIds /\ r.to \in RecordIds
    ValidRelationTypes == \A r \in relations : r.type \in RelationTypeSet
    BoundedSize == Cardinality(records) <= MaxRecords
    ValidIds == RecordIds \subseteq IdSet

    \* {{FILL:PRIMARY_INVARIANTS}} — domain-specific, always hold

    \* --- Derived invariants (hold when dirty = FALSE) ---
    \* {{FILL:DERIVED_INVARIANTS}} — gated on dirty = TRUE \/ ...

end define;

fair process actor = "main"
begin
    Loop:
        while TRUE do
            either
                \* {{FILL:ACTIONS}} — one label per CRUD action
                \* Pattern:
                \*   ActionLabel:
                \*     with params \in SomeSet do
                \*       if precondition then
                \*         records/relations := mutated;
                \*         dirty := TRUE;
                \*         op := "action_name";
                \*         result := ...;
                \*       else
                \*         op := "action_rejected";
                \*         result := "error";
                \*       end if;
                \*     end with;
                skip;
            or
                skip;
            end either;
            \* Phase 2: recompute derived state
            UpdateDerived:
                \* {{FILL:DERIVED_UPDATE}}
                dirty := FALSE;
        end while;
end process;

end algorithm; *)

===========================================================================
