------------------------ MODULE WorkerClientInit ------------------------

EXTENDS Integers, TLC, Sequences

CONSTANTS MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps > 0

WorkerStates == {
    "starting",
    "env_checking",
    "env_validated",
    "client_initializing",
    "client_ready",
    "env_missing",
    "env_tainted"
}

TerminalWorkerStates == {"client_ready", "env_missing", "env_tainted"}

CredSources == {"none", "injected", "inherited"}

InitPaths == {"none", "make_client", "build_llm_fn"}

(* --algorithm WorkerClientInit

variables
    worker_state           = "starting",
    injected_has_claudecode  = FALSE,
    inherited_has_claudecode = FALSE,
    env_source             = "none",
    init_path              = "none",
    credentials_source     = "none",
    client_initialized     = FALSE,
    step_count             = 0;

define

    TypeInvariant ==
        /\ worker_state            \in WorkerStates
        /\ env_source              \in CredSources
        /\ init_path               \in InitPaths
        /\ credentials_source      \in CredSources
        /\ client_initialized      \in BOOLEAN
        /\ injected_has_claudecode  \in BOOLEAN
        /\ inherited_has_claudecode \in BOOLEAN

    BoundedExecution == step_count <= MaxSteps

    CredentialsFromInjectedOnly ==
        client_initialized => credentials_source = "injected"

    ClientReadyImpliesInjectedEnv ==
        worker_state = "client_ready" =>
            ( injected_has_claudecode = TRUE /\ env_source = "injected" )

    NoClientFromInheritedEnv ==
        client_initialized => env_source /= "inherited"

    NoClientFromMissingEnv ==
        client_initialized => env_source /= "none"

    InheritedNeverUsedAsCredentials ==
        credentials_source /= "inherited"

    TaintedEnvBlocksClientInit ==
        worker_state = "env_tainted" => client_initialized = FALSE

    MissingEnvBlocksClientInit ==
        worker_state = "env_missing" => client_initialized = FALSE

    ClientInitRequiresExclusiveInjectedSource ==
        client_initialized =>
            ( injected_has_claudecode = TRUE
              /\ env_source            = "injected"
              /\ credentials_source    = "injected" )

end define;

fair process worker = "worker"
begin
    StartWorker:
        worker_state := "env_checking";
        step_count   := step_count + 1;

    SetupEnv:
        either
            injected_has_claudecode  := TRUE  ||
            inherited_has_claudecode := FALSE;
        or
            injected_has_claudecode  := FALSE ||
            inherited_has_claudecode := FALSE;
        or
            injected_has_claudecode  := FALSE ||
            inherited_has_claudecode := TRUE;
        or
            injected_has_claudecode  := TRUE  ||
            inherited_has_claudecode := TRUE;
        end either;

    ValidateEnv:
        step_count := step_count + 1;
        if injected_has_claudecode = TRUE then
            env_source   := "injected";
            worker_state := "env_validated";
        elsif inherited_has_claudecode = TRUE then
            env_source   := "inherited";
            worker_state := "env_tainted";
        else
            env_source   := "none";
            worker_state := "env_missing";
        end if;

    RouteOrAbort:
        step_count := step_count + 1;
        if worker_state /= "env_validated" then
            goto Terminate;
        end if;

    ChooseInitPath:
        either
            init_path := "make_client";
        or
            init_path := "build_llm_fn";
        end either;
        worker_state := "client_initializing";
        step_count   := step_count + 1;

    InitializeClient:
        assert env_source              = "injected";
        assert injected_has_claudecode = TRUE;
        credentials_source := "injected";
        client_initialized := TRUE;
        worker_state       := "client_ready";
        step_count         := step_count + 1;

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e8be4ca1" /\ chksum(tla) = "193f8b13")
VARIABLES pc, worker_state, injected_has_claudecode, inherited_has_claudecode, 
          env_source, init_path, credentials_source, client_initialized, 
          step_count

(* define statement *)
TypeInvariant ==
    /\ worker_state            \in WorkerStates
    /\ env_source              \in CredSources
    /\ init_path               \in InitPaths
    /\ credentials_source      \in CredSources
    /\ client_initialized      \in BOOLEAN
    /\ injected_has_claudecode  \in BOOLEAN
    /\ inherited_has_claudecode \in BOOLEAN

BoundedExecution == step_count <= MaxSteps

CredentialsFromInjectedOnly ==
    client_initialized => credentials_source = "injected"

ClientReadyImpliesInjectedEnv ==
    worker_state = "client_ready" =>
        ( injected_has_claudecode = TRUE /\ env_source = "injected" )

NoClientFromInheritedEnv ==
    client_initialized => env_source /= "inherited"

NoClientFromMissingEnv ==
    client_initialized => env_source /= "none"

InheritedNeverUsedAsCredentials ==
    credentials_source /= "inherited"

TaintedEnvBlocksClientInit ==
    worker_state = "env_tainted" => client_initialized = FALSE

MissingEnvBlocksClientInit ==
    worker_state = "env_missing" => client_initialized = FALSE

ClientInitRequiresExclusiveInjectedSource ==
    client_initialized =>
        ( injected_has_claudecode = TRUE
          /\ env_source            = "injected"
          /\ credentials_source    = "injected" )


vars == << pc, worker_state, injected_has_claudecode, 
           inherited_has_claudecode, env_source, init_path, 
           credentials_source, client_initialized, step_count >>

ProcSet == {"worker"}

Init == (* Global variables *)
        /\ worker_state = "starting"
        /\ injected_has_claudecode = FALSE
        /\ inherited_has_claudecode = FALSE
        /\ env_source = "none"
        /\ init_path = "none"
        /\ credentials_source = "none"
        /\ client_initialized = FALSE
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "StartWorker"]

StartWorker == /\ pc["worker"] = "StartWorker"
               /\ worker_state' = "env_checking"
               /\ step_count' = step_count + 1
               /\ pc' = [pc EXCEPT !["worker"] = "SetupEnv"]
               /\ UNCHANGED << injected_has_claudecode, 
                               inherited_has_claudecode, env_source, init_path, 
                               credentials_source, client_initialized >>

SetupEnv == /\ pc["worker"] = "SetupEnv"
            /\ \/ /\ /\ inherited_has_claudecode' = FALSE
                     /\ injected_has_claudecode' = TRUE
               \/ /\ /\ inherited_has_claudecode' = FALSE
                     /\ injected_has_claudecode' = FALSE
               \/ /\ /\ inherited_has_claudecode' = TRUE
                     /\ injected_has_claudecode' = FALSE
               \/ /\ /\ inherited_has_claudecode' = TRUE
                     /\ injected_has_claudecode' = TRUE
            /\ pc' = [pc EXCEPT !["worker"] = "ValidateEnv"]
            /\ UNCHANGED << worker_state, env_source, init_path, 
                            credentials_source, client_initialized, step_count >>

ValidateEnv == /\ pc["worker"] = "ValidateEnv"
               /\ step_count' = step_count + 1
               /\ IF injected_has_claudecode = TRUE
                     THEN /\ env_source' = "injected"
                          /\ worker_state' = "env_validated"
                     ELSE /\ IF inherited_has_claudecode = TRUE
                                THEN /\ env_source' = "inherited"
                                     /\ worker_state' = "env_tainted"
                                ELSE /\ env_source' = "none"
                                     /\ worker_state' = "env_missing"
               /\ pc' = [pc EXCEPT !["worker"] = "RouteOrAbort"]
               /\ UNCHANGED << injected_has_claudecode, 
                               inherited_has_claudecode, init_path, 
                               credentials_source, client_initialized >>

RouteOrAbort == /\ pc["worker"] = "RouteOrAbort"
                /\ step_count' = step_count + 1
                /\ IF worker_state /= "env_validated"
                      THEN /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                      ELSE /\ pc' = [pc EXCEPT !["worker"] = "ChooseInitPath"]
                /\ UNCHANGED << worker_state, injected_has_claudecode, 
                                inherited_has_claudecode, env_source, 
                                init_path, credentials_source, 
                                client_initialized >>

ChooseInitPath == /\ pc["worker"] = "ChooseInitPath"
                  /\ \/ /\ init_path' = "make_client"
                     \/ /\ init_path' = "build_llm_fn"
                  /\ worker_state' = "client_initializing"
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["worker"] = "InitializeClient"]
                  /\ UNCHANGED << injected_has_claudecode, 
                                  inherited_has_claudecode, env_source, 
                                  credentials_source, client_initialized >>

InitializeClient == /\ pc["worker"] = "InitializeClient"
                    /\ Assert(env_source              = "injected", 
                              "Failure of assertion at line 130, column 9.")
                    /\ Assert(injected_has_claudecode = TRUE, 
                              "Failure of assertion at line 131, column 9.")
                    /\ credentials_source' = "injected"
                    /\ client_initialized' = TRUE
                    /\ worker_state' = "client_ready"
                    /\ step_count' = step_count + 1
                    /\ pc' = [pc EXCEPT !["worker"] = "Terminate"]
                    /\ UNCHANGED << injected_has_claudecode, 
                                    inherited_has_claudecode, env_source, 
                                    init_path >>

Terminate == /\ pc["worker"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["worker"] = "Done"]
             /\ UNCHANGED << worker_state, injected_has_claudecode, 
                             inherited_has_claudecode, env_source, init_path, 
                             credentials_source, client_initialized, 
                             step_count >>

worker == StartWorker \/ SetupEnv \/ ValidateEnv \/ RouteOrAbort
             \/ ChooseInitPath \/ InitializeClient \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == worker
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(worker)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

=============================================================================
