---- MODULE EntryPointDiscoveryDispatch ----

EXTENDS Integers, FiniteSets, Sequences, TLC

CONSTANTS MaxSteps

ASSUME MaxSteps \in Nat /\ MaxSteps >= 5

PythonLangs        == {"none", "python"}
NonPythonLangs     == {"go", "rust", "javascript", "typescript"}
KnownLangs         == PythonLangs \cup NonPythonLangs
ValidCodebaseTypes == {"web_app", "cli", "event_driven", "library"}
PythonHelpers      == {"web_routes", "cli_commands",
                       "event_handlers", "public_api", "main_functions"}
AllDispatchTargets == NonPythonLangs \cup {"python", "none"}

(* --algorithm EntryPointDiscoveryDispatch

variables
    lang            \in {"none", "python", "go", "rust",
                         "javascript", "typescript", "ruby"},
    skeletons_given \in {TRUE, FALSE},
    codebase_type   = "unresolved",
    dispatched_to   = "none",
    python_helper   = "none",
    result_empty    = FALSE,
    autodetect_done = FALSE,
    phase           = "init",
    step_count      = 0;

define

    TypeInvariant ==
        /\ lang            \in KnownLangs \cup {"ruby"}
        /\ phase           \in {"init", "resolving", "dispatching",
                                 "python_subdispatch", "finished"}
        /\ dispatched_to   \in AllDispatchTargets
        /\ python_helper   \in PythonHelpers \cup {"none"}
        /\ result_empty    \in {TRUE, FALSE}
        /\ autodetect_done \in {TRUE, FALSE}
        /\ step_count      \in 0..MaxSteps

    PythonPreserved ==
        (phase = "finished" /\ lang \in PythonLangs) =>
            (dispatched_to = "python" /\ python_helper \in PythonHelpers)

    NonPythonDispatched ==
        (phase = "finished" /\ lang \in NonPythonLangs) =>
            (dispatched_to = lang /\ python_helper = "none" /\ result_empty = FALSE)

    UnknownSafe ==
        (phase = "finished" /\ lang \notin KnownLangs) =>
            (result_empty = TRUE /\ dispatched_to = "none" /\ python_helper = "none")

    AutodetectBeforeDispatch ==
        (phase \in {"dispatching", "python_subdispatch", "finished"}) =>
            autodetect_done = TRUE

    CodebaseResolvedBeforeDispatch ==
        (phase \in {"dispatching", "python_subdispatch", "finished"}) =>
            codebase_type \in ValidCodebaseTypes

    MutualExclusion ==
        ~(dispatched_to \in NonPythonLangs /\ result_empty = TRUE)

    BoundedExecution == step_count <= MaxSteps

end define;

fair process DiscoveryDispatch = "main"
begin
    Start:
        phase := "resolving";
        step_count := step_count + 1;

    ResolveCodebase:
        with t \in {"web_app", "cli", "event_driven", "library"} do
            codebase_type := t;
        end with;
        autodetect_done := TRUE;
        phase := "dispatching";
        step_count := step_count + 1;

    DispatchByLang:
        if lang \in {"none", "python"} then
            dispatched_to := "python"
        elsif lang = "go" then
            dispatched_to := "go"
        elsif lang = "rust" then
            dispatched_to := "rust"
        elsif lang = "javascript" then
            dispatched_to := "javascript"
        elsif lang = "typescript" then
            dispatched_to := "typescript"
        else
            result_empty := TRUE
        end if;
        step_count := step_count + 1;

    PythonSubDispatch:
        if dispatched_to = "python" then
            phase := "python_subdispatch";
            if codebase_type = "web_app" then
                python_helper := "web_routes"
            elsif codebase_type = "cli" then
                python_helper := "cli_commands"
            elsif codebase_type = "event_driven" then
                python_helper := "event_handlers"
            else
                python_helper := "public_api"
            end if
        end if;
        step_count := step_count + 1;

    Finish:
        phase := "finished";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "544f89ca" /\ chksum(tla) = "4d74abec")
VARIABLES pc, lang, skeletons_given, codebase_type, dispatched_to, 
          python_helper, result_empty, autodetect_done, phase, step_count

(* define statement *)
TypeInvariant ==
    /\ lang            \in KnownLangs \cup {"ruby"}
    /\ phase           \in {"init", "resolving", "dispatching",
                             "python_subdispatch", "finished"}
    /\ dispatched_to   \in AllDispatchTargets
    /\ python_helper   \in PythonHelpers \cup {"none"}
    /\ result_empty    \in {TRUE, FALSE}
    /\ autodetect_done \in {TRUE, FALSE}
    /\ step_count      \in 0..MaxSteps

PythonPreserved ==
    (phase = "finished" /\ lang \in PythonLangs) =>
        (dispatched_to = "python" /\ python_helper \in PythonHelpers)

NonPythonDispatched ==
    (phase = "finished" /\ lang \in NonPythonLangs) =>
        (dispatched_to = lang /\ python_helper = "none" /\ result_empty = FALSE)

UnknownSafe ==
    (phase = "finished" /\ lang \notin KnownLangs) =>
        (result_empty = TRUE /\ dispatched_to = "none" /\ python_helper = "none")

AutodetectBeforeDispatch ==
    (phase \in {"dispatching", "python_subdispatch", "finished"}) =>
        autodetect_done = TRUE

CodebaseResolvedBeforeDispatch ==
    (phase \in {"dispatching", "python_subdispatch", "finished"}) =>
        codebase_type \in ValidCodebaseTypes

MutualExclusion ==
    ~(dispatched_to \in NonPythonLangs /\ result_empty = TRUE)

BoundedExecution == step_count <= MaxSteps


vars == << pc, lang, skeletons_given, codebase_type, dispatched_to, 
           python_helper, result_empty, autodetect_done, phase, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ lang \in {"none", "python", "go", "rust",
                     "javascript", "typescript", "ruby"}
        /\ skeletons_given \in {TRUE, FALSE}
        /\ codebase_type = "unresolved"
        /\ dispatched_to = "none"
        /\ python_helper = "none"
        /\ result_empty = FALSE
        /\ autodetect_done = FALSE
        /\ phase = "init"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "Start"]

Start == /\ pc["main"] = "Start"
         /\ phase' = "resolving"
         /\ step_count' = step_count + 1
         /\ pc' = [pc EXCEPT !["main"] = "ResolveCodebase"]
         /\ UNCHANGED << lang, skeletons_given, codebase_type, dispatched_to, 
                         python_helper, result_empty, autodetect_done >>

ResolveCodebase == /\ pc["main"] = "ResolveCodebase"
                   /\ \E t \in {"web_app", "cli", "event_driven", "library"}:
                        codebase_type' = t
                   /\ autodetect_done' = TRUE
                   /\ phase' = "dispatching"
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["main"] = "DispatchByLang"]
                   /\ UNCHANGED << lang, skeletons_given, dispatched_to, 
                                   python_helper, result_empty >>

DispatchByLang == /\ pc["main"] = "DispatchByLang"
                  /\ IF lang \in {"none", "python"}
                        THEN /\ dispatched_to' = "python"
                             /\ UNCHANGED result_empty
                        ELSE /\ IF lang = "go"
                                   THEN /\ dispatched_to' = "go"
                                        /\ UNCHANGED result_empty
                                   ELSE /\ IF lang = "rust"
                                              THEN /\ dispatched_to' = "rust"
                                                   /\ UNCHANGED result_empty
                                              ELSE /\ IF lang = "javascript"
                                                         THEN /\ dispatched_to' = "javascript"
                                                              /\ UNCHANGED result_empty
                                                         ELSE /\ IF lang = "typescript"
                                                                    THEN /\ dispatched_to' = "typescript"
                                                                         /\ UNCHANGED result_empty
                                                                    ELSE /\ result_empty' = TRUE
                                                                         /\ UNCHANGED dispatched_to
                  /\ step_count' = step_count + 1
                  /\ pc' = [pc EXCEPT !["main"] = "PythonSubDispatch"]
                  /\ UNCHANGED << lang, skeletons_given, codebase_type, 
                                  python_helper, autodetect_done, phase >>

PythonSubDispatch == /\ pc["main"] = "PythonSubDispatch"
                     /\ IF dispatched_to = "python"
                           THEN /\ phase' = "python_subdispatch"
                                /\ IF codebase_type = "web_app"
                                      THEN /\ python_helper' = "web_routes"
                                      ELSE /\ IF codebase_type = "cli"
                                                 THEN /\ python_helper' = "cli_commands"
                                                 ELSE /\ IF codebase_type = "event_driven"
                                                            THEN /\ python_helper' = "event_handlers"
                                                            ELSE /\ python_helper' = "public_api"
                           ELSE /\ TRUE
                                /\ UNCHANGED << python_helper, phase >>
                     /\ step_count' = step_count + 1
                     /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                     /\ UNCHANGED << lang, skeletons_given, codebase_type, 
                                     dispatched_to, result_empty, 
                                     autodetect_done >>

Finish == /\ pc["main"] = "Finish"
          /\ phase' = "finished"
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << lang, skeletons_given, codebase_type, dispatched_to, 
                          python_helper, result_empty, autodetect_done, 
                          step_count >>

DiscoveryDispatch == Start \/ ResolveCodebase \/ DispatchByLang
                        \/ PythonSubDispatch \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == DiscoveryDispatch
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(DiscoveryDispatch)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
