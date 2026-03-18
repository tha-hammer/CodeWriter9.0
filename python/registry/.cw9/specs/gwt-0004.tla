---- MODULE ProjectContextHosted ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    PROJECT_ID,
    WORKSPACE,
    STORAGE_CLIENT,
    CONTAINER_TEMPLATE_DIR,
    CONTAINER_TOOLS_DIR,
    NULL_STORAGE,
    SELF_HOST_STATE_ROOT,
    SELF_HOST_TEMPLATE_DIR,
    SELF_HOST_TOOLS_DIR,
    EXTERNAL_STATE_ROOT,
    EXTERNAL_TEMPLATE_DIR,
    EXTERNAL_TOOLS_DIR,
    INSTALLED_STATE_ROOT,
    INSTALLED_TEMPLATE_DIR,
    INSTALLED_TOOLS_DIR

PathJoin(base, suffix) == <<base, suffix>>

FactoryModes == {"hosted", "self_hosting", "external", "installed"}

(* --algorithm ProjectContextHosted

variables
    chosen_mode = "none",
    ctx = [ state_root     |-> NULL_STORAGE,
            template_dir   |-> NULL_STORAGE,
            tools_dir      |-> NULL_STORAGE,
            storage_client |-> NULL_STORAGE,
            frozen         |-> FALSE ],
    phase = "init",
    verified = FALSE;

define

    HostedStateRoot == PathJoin(WORKSPACE, ".cw9/")

    TypeOK ==
        /\ chosen_mode \in (FactoryModes \union {"none"})
        /\ phase \in {"init", "dispatched", "complete", "verified"}
        /\ ctx.frozen \in BOOLEAN
        /\ verified \in BOOLEAN

    HostedContextCorrect ==
        ( phase \in {"complete", "verified"} /\ chosen_mode = "hosted" ) =>
            /\ ctx.state_root     = HostedStateRoot
            /\ ctx.template_dir   = CONTAINER_TEMPLATE_DIR
            /\ ctx.tools_dir      = CONTAINER_TOOLS_DIR
            /\ ctx.storage_client = STORAGE_CLIENT
            /\ ctx.frozen         = TRUE

    NonHostedLackStorage ==
        ( phase \in {"complete", "verified"} /\
          chosen_mode \in {"self_hosting", "external", "installed"} ) =>
            ctx.storage_client = NULL_STORAGE

    FrozenOnceComplete ==
        phase \in {"complete", "verified"} => ctx.frozen = TRUE

    HostedPathDerivedFromWorkspace ==
        ( phase \in {"complete", "verified"} /\ chosen_mode = "hosted" ) =>
            ctx.state_root = PathJoin(WORKSPACE, ".cw9/")

    SafetyInvariant ==
        /\ TypeOK
        /\ HostedContextCorrect
        /\ NonHostedLackStorage
        /\ FrozenOnceComplete
        /\ HostedPathDerivedFromWorkspace

    EventuallyVerified == <>(verified = TRUE)

end define;

fair process factory = "factory"
begin
    SelectMode:
        with m \in FactoryModes do
            chosen_mode := m
        end with;
        phase := "dispatched";

    Dispatch:
        if chosen_mode = "hosted" then
            ctx := [ state_root     |-> PathJoin(WORKSPACE, ".cw9/"),
                     template_dir   |-> CONTAINER_TEMPLATE_DIR,
                     tools_dir      |-> CONTAINER_TOOLS_DIR,
                     storage_client |-> STORAGE_CLIENT,
                     frozen         |-> TRUE ];
        elsif chosen_mode = "self_hosting" then
            ctx := [ state_root     |-> SELF_HOST_STATE_ROOT,
                     template_dir   |-> SELF_HOST_TEMPLATE_DIR,
                     tools_dir      |-> SELF_HOST_TOOLS_DIR,
                     storage_client |-> NULL_STORAGE,
                     frozen         |-> TRUE ];
        elsif chosen_mode = "external" then
            ctx := [ state_root     |-> EXTERNAL_STATE_ROOT,
                     template_dir   |-> EXTERNAL_TEMPLATE_DIR,
                     tools_dir      |-> EXTERNAL_TOOLS_DIR,
                     storage_client |-> NULL_STORAGE,
                     frozen         |-> TRUE ];
        else
            ctx := [ state_root     |-> INSTALLED_STATE_ROOT,
                     template_dir   |-> INSTALLED_TEMPLATE_DIR,
                     tools_dir      |-> INSTALLED_TOOLS_DIR,
                     storage_client |-> NULL_STORAGE,
                     frozen         |-> TRUE ];
        end if;

    AfterDispatch:
        phase := "complete";

    CheckHosted:
        if chosen_mode = "hosted" then
            assert ctx.state_root     = PathJoin(WORKSPACE, ".cw9/");
            assert ctx.template_dir   = CONTAINER_TEMPLATE_DIR;
            assert ctx.tools_dir      = CONTAINER_TOOLS_DIR;
            assert ctx.storage_client = STORAGE_CLIENT;
            assert ctx.frozen         = TRUE;
        else
            assert ctx.storage_client = NULL_STORAGE;
            assert ctx.frozen         = TRUE;
        end if;

    AfterCheck:
        verified := TRUE;
        phase := "verified";

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "54b5ee6b" /\ chksum(tla) = "7b1dd105")
VARIABLES pc, chosen_mode, ctx, phase, verified

(* define statement *)
HostedStateRoot == PathJoin(WORKSPACE, ".cw9/")

TypeOK ==
    /\ chosen_mode \in (FactoryModes \union {"none"})
    /\ phase \in {"init", "dispatched", "complete", "verified"}
    /\ ctx.frozen \in BOOLEAN
    /\ verified \in BOOLEAN

HostedContextCorrect ==
    ( phase \in {"complete", "verified"} /\ chosen_mode = "hosted" ) =>
        /\ ctx.state_root     = HostedStateRoot
        /\ ctx.template_dir   = CONTAINER_TEMPLATE_DIR
        /\ ctx.tools_dir      = CONTAINER_TOOLS_DIR
        /\ ctx.storage_client = STORAGE_CLIENT
        /\ ctx.frozen         = TRUE

NonHostedLackStorage ==
    ( phase \in {"complete", "verified"} /\
      chosen_mode \in {"self_hosting", "external", "installed"} ) =>
        ctx.storage_client = NULL_STORAGE

FrozenOnceComplete ==
    phase \in {"complete", "verified"} => ctx.frozen = TRUE

HostedPathDerivedFromWorkspace ==
    ( phase \in {"complete", "verified"} /\ chosen_mode = "hosted" ) =>
        ctx.state_root = PathJoin(WORKSPACE, ".cw9/")

SafetyInvariant ==
    /\ TypeOK
    /\ HostedContextCorrect
    /\ NonHostedLackStorage
    /\ FrozenOnceComplete
    /\ HostedPathDerivedFromWorkspace

EventuallyVerified == <>(verified = TRUE)


vars == << pc, chosen_mode, ctx, phase, verified >>

ProcSet == {"factory"}

Init == (* Global variables *)
        /\ chosen_mode = "none"
        /\ ctx = [ state_root     |-> NULL_STORAGE,
                   template_dir   |-> NULL_STORAGE,
                   tools_dir      |-> NULL_STORAGE,
                   storage_client |-> NULL_STORAGE,
                   frozen         |-> FALSE ]
        /\ phase = "init"
        /\ verified = FALSE
        /\ pc = [self \in ProcSet |-> "SelectMode"]

SelectMode == /\ pc["factory"] = "SelectMode"
              /\ \E m \in FactoryModes:
                   chosen_mode' = m
              /\ phase' = "dispatched"
              /\ pc' = [pc EXCEPT !["factory"] = "Dispatch"]
              /\ UNCHANGED << ctx, verified >>

Dispatch == /\ pc["factory"] = "Dispatch"
            /\ IF chosen_mode = "hosted"
                  THEN /\ ctx' = [ state_root     |-> PathJoin(WORKSPACE, ".cw9/"),
                                   template_dir   |-> CONTAINER_TEMPLATE_DIR,
                                   tools_dir      |-> CONTAINER_TOOLS_DIR,
                                   storage_client |-> STORAGE_CLIENT,
                                   frozen         |-> TRUE ]
                  ELSE /\ IF chosen_mode = "self_hosting"
                             THEN /\ ctx' = [ state_root     |-> SELF_HOST_STATE_ROOT,
                                              template_dir   |-> SELF_HOST_TEMPLATE_DIR,
                                              tools_dir      |-> SELF_HOST_TOOLS_DIR,
                                              storage_client |-> NULL_STORAGE,
                                              frozen         |-> TRUE ]
                             ELSE /\ IF chosen_mode = "external"
                                        THEN /\ ctx' = [ state_root     |-> EXTERNAL_STATE_ROOT,
                                                         template_dir   |-> EXTERNAL_TEMPLATE_DIR,
                                                         tools_dir      |-> EXTERNAL_TOOLS_DIR,
                                                         storage_client |-> NULL_STORAGE,
                                                         frozen         |-> TRUE ]
                                        ELSE /\ ctx' = [ state_root     |-> INSTALLED_STATE_ROOT,
                                                         template_dir   |-> INSTALLED_TEMPLATE_DIR,
                                                         tools_dir      |-> INSTALLED_TOOLS_DIR,
                                                         storage_client |-> NULL_STORAGE,
                                                         frozen         |-> TRUE ]
            /\ pc' = [pc EXCEPT !["factory"] = "AfterDispatch"]
            /\ UNCHANGED << chosen_mode, phase, verified >>

AfterDispatch == /\ pc["factory"] = "AfterDispatch"
                 /\ phase' = "complete"
                 /\ pc' = [pc EXCEPT !["factory"] = "CheckHosted"]
                 /\ UNCHANGED << chosen_mode, ctx, verified >>

CheckHosted == /\ pc["factory"] = "CheckHosted"
               /\ IF chosen_mode = "hosted"
                     THEN /\ Assert(ctx.state_root     = PathJoin(WORKSPACE, ".cw9/"), 
                                    "Failure of assertion at line 119, column 13.")
                          /\ Assert(ctx.template_dir   = CONTAINER_TEMPLATE_DIR, 
                                    "Failure of assertion at line 120, column 13.")
                          /\ Assert(ctx.tools_dir      = CONTAINER_TOOLS_DIR, 
                                    "Failure of assertion at line 121, column 13.")
                          /\ Assert(ctx.storage_client = STORAGE_CLIENT, 
                                    "Failure of assertion at line 122, column 13.")
                          /\ Assert(ctx.frozen         = TRUE, 
                                    "Failure of assertion at line 123, column 13.")
                     ELSE /\ Assert(ctx.storage_client = NULL_STORAGE, 
                                    "Failure of assertion at line 125, column 13.")
                          /\ Assert(ctx.frozen         = TRUE, 
                                    "Failure of assertion at line 126, column 13.")
               /\ pc' = [pc EXCEPT !["factory"] = "AfterCheck"]
               /\ UNCHANGED << chosen_mode, ctx, phase, verified >>

AfterCheck == /\ pc["factory"] = "AfterCheck"
              /\ verified' = TRUE
              /\ phase' = "verified"
              /\ pc' = [pc EXCEPT !["factory"] = "Finish"]
              /\ UNCHANGED << chosen_mode, ctx >>

Finish == /\ pc["factory"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["factory"] = "Done"]
          /\ UNCHANGED << chosen_mode, ctx, phase, verified >>

factory == SelectMode \/ Dispatch \/ AfterDispatch \/ CheckHosted
              \/ AfterCheck \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == factory
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(factory)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
