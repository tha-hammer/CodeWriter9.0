------------------------- MODULE AuthSessionTemplate -------------------------
(*
 * Auth/Session PlusCal Template — CodeWriter9.0
 *
 * Reusable template for authentication and session management. Modeled
 * after the security + access_controls schemas:
 *   security.authentication.strategies[]  → auth methods
 *   security.authorization.roles[]        → role names
 *   security.authorization.permissions[]  → permission names
 *   access_controls.condition             → guard function
 *   access_controls.redirect              → failure redirect
 *
 * Fill-in markers:
 *   {{FILL:MODULE_NAME}}        — TLA+ module name
 *   {{FILL:USER_SET}}           — finite set of user IDs
 *   {{FILL:ROLE_SET}}           — set of roles
 *   {{FILL:PERMISSION_SET}}     — set of permissions
 *   {{FILL:RESOURCE_SET}}       — set of protected resources
 *   {{FILL:ROLE_PERMISSIONS}}   — mapping: role -> set of permissions
 *   {{FILL:RESOURCE_REQUIRED}}  — mapping: resource -> required permission
 *   {{FILL:SESSION_TIMEOUT}}    — max steps before session expires
 *   {{FILL:PRIMARY_INVARIANTS}} — domain-specific invariants
 *
 * Two-phase action model (same pattern as CRUD template).
 *)

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    UserSet,            \* {{FILL:USER_SET}}
    RoleSet,            \* {{FILL:ROLE_SET}}
    PermissionSet,      \* {{FILL:PERMISSION_SET}}
    ResourceSet,        \* {{FILL:RESOURCE_SET}}
    SessionTimeout      \* {{FILL:SESSION_TIMEOUT}}

(* --algorithm {{FILL:MODULE_NAME}}

variables
    \* sessions: map of user -> [role, age, active]
    sessions = [u \in UserSet |-> [role |-> "none", age |-> 0, active |-> FALSE]],
    access_log = {},    \* set of [user, resource, granted] records
    op = "idle",
    result = "none";

define
    \* --- Helpers ---
    ActiveSessions == {u \in UserSet : sessions[u].active}
    SessionRole(u) == sessions[u].role

    \* --- Invariants ---

    \* No access without valid session
    NoAccessWithoutSession ==
        \A entry \in access_log :
            entry.granted = TRUE => entry.user \in ActiveSessions

    \* Session timeout respected
    SessionTimeoutRespected ==
        \A u \in UserSet : sessions[u].active => sessions[u].age <= SessionTimeout

    \* Roles are always valid
    ValidRoles ==
        \A u \in UserSet : sessions[u].active => sessions[u].role \in RoleSet

    \* {{FILL:PRIMARY_INVARIANTS}}
    \* Typical domain invariants:
    \*   PermissionRequired == \A entry \in access_log :
    \*       entry.granted => HasPermission(SessionRole(entry.user), ResourceRequired(entry.resource))

end define;

fair process actor = "main"
begin
    Loop:
        while TRUE do
            either
                \* --- Login: create session ---
                Login:
                    with uid \in UserSet, role \in RoleSet do
                        if ~sessions[uid].active then
                            sessions[uid] := [role |-> role, age |-> 0, active |-> TRUE];
                            op := "logged_in";
                            result := uid;
                        else
                            op := "already_active";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- Logout: destroy session ---
                Logout:
                    with uid \in UserSet do
                        if sessions[uid].active then
                            sessions[uid] := [role |-> "none", age |-> 0, active |-> FALSE];
                            op := "logged_out";
                            result := uid;
                        else
                            op := "not_active";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- AccessResource: check permission and log ---
                AccessResource:
                    with uid \in UserSet, res \in ResourceSet do
                        if sessions[uid].active then
                            \* {{FILL:RESOURCE_REQUIRED}} — check permission
                            \* For template: grant all access to active sessions
                            access_log := access_log \union
                                {[user |-> uid, resource |-> res, granted |-> TRUE]};
                            op := "access_granted";
                            result := res;
                        else
                            access_log := access_log \union
                                {[user |-> uid, resource |-> res, granted |-> FALSE]};
                            op := "access_denied";
                            result := "error";
                        end if;
                    end with;
            or
                \* --- Tick: age all sessions, expire if timeout ---
                Tick:
                    with uid \in UserSet do
                        if sessions[uid].active then
                            if sessions[uid].age + 1 > SessionTimeout then
                                sessions[uid] := [role |-> "none", age |-> 0, active |-> FALSE];
                                op := "session_expired";
                                result := uid;
                            else
                                sessions[uid].age := sessions[uid].age + 1;
                                op := "tick";
                                result := uid;
                            end if;
                        end if;
                    end with;
            end either;
        end while;
end process;

end algorithm; *)

===========================================================================
