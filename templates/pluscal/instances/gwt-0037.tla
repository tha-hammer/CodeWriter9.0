----------------------- MODULE ProjectContextResolution -----------------------

EXTENDS Integers, TLC

(* --algorithm ProjectContextResolution

variables
    config_exists        \in BOOLEAN,
    config_engine_valid  \in BOOLEAN,
    engine_root_provided \in BOOLEAN,
    engine_equals_target \in BOOLEAN,
    auto_detect_success  \in BOOLEAN,
    engine_resolved      = FALSE,
    selected_mode        = "UNRESOLVED";

define

    ModeValid ==
        selected_mode \in {"UNRESOLVED", "SELF_HOSTING", "EXTERNAL", "INSTALLED"}

    ResolvedModeConsistency ==
        ( selected_mode = "SELF_HOSTING" ) =>
            ( engine_resolved /\ engine_equals_target )

    ExternalModeConsistency ==
        ( selected_mode = "EXTERNAL" ) =>
            ( engine_resolved /\ ~engine_equals_target )

    InstalledModeConsistency ==
        ( selected_mode = "INSTALLED" ) =>
            ~engine_resolved

    ConfigDrivenNeverInstalled ==
        ( ~engine_root_provided /\ config_exists /\ config_engine_valid ) =>
            ( selected_mode = "UNRESOLVED" \/
              selected_mode \in {"SELF_HOSTING", "EXTERNAL"} )

    ThenConfigSelfHosting ==
        ( ~engine_root_provided /\
          config_exists /\ config_engine_valid /\
          engine_equals_target ) =>
            ( selected_mode = "UNRESOLVED" \/ selected_mode = "SELF_HOSTING" )

    ThenConfigExternal ==
        ( ~engine_root_provided /\
          config_exists /\ config_engine_valid /\
          ~engine_equals_target ) =>
            ( selected_mode = "UNRESOLVED" \/ selected_mode = "EXTERNAL" )

    ExplicitRootNeverInstalled ==
        engine_root_provided =>
            ( selected_mode = "UNRESOLVED" \/
              selected_mode \in {"SELF_HOSTING", "EXTERNAL"} )

    NoSourceNoAuto ==
        ( ~engine_root_provided /\
          ~( config_exists /\ config_engine_valid ) /\
          ~auto_detect_success ) =>
            ( selected_mode = "UNRESOLVED" \/ selected_mode = "INSTALLED" )

end define;

fair process resolver = "main"
begin
    ResolveConfig:
        if engine_root_provided then
            engine_resolved := TRUE;
        elsif config_exists /\ config_engine_valid then
            engine_resolved := TRUE;
        else
            skip;
        end if;

    AutoDetect:
        if ~engine_resolved then
            if auto_detect_success then
                engine_resolved := TRUE;
            else
                skip;
            end if;
        else
            skip;
        end if;

    SelectMode:
        if engine_resolved then
            if engine_equals_target then
                selected_mode := "SELF_HOSTING";
            else
                selected_mode := "EXTERNAL";
            end if;
        else
            selected_mode := "INSTALLED";
        end if;

    Terminate:
        assert selected_mode \in {"SELF_HOSTING", "EXTERNAL", "INSTALLED"};

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "da00d17f" /\ chksum(tla) = "4cf29823")
VARIABLES pc, config_exists, config_engine_valid, engine_root_provided, 
          engine_equals_target, auto_detect_success, engine_resolved, 
          selected_mode

(* define statement *)
ModeValid ==
    selected_mode \in {"UNRESOLVED", "SELF_HOSTING", "EXTERNAL", "INSTALLED"}

ResolvedModeConsistency ==
    ( selected_mode = "SELF_HOSTING" ) =>
        ( engine_resolved /\ engine_equals_target )

ExternalModeConsistency ==
    ( selected_mode = "EXTERNAL" ) =>
        ( engine_resolved /\ ~engine_equals_target )

InstalledModeConsistency ==
    ( selected_mode = "INSTALLED" ) =>
        ~engine_resolved

ConfigDrivenNeverInstalled ==
    ( ~engine_root_provided /\ config_exists /\ config_engine_valid ) =>
        ( selected_mode = "UNRESOLVED" \/
          selected_mode \in {"SELF_HOSTING", "EXTERNAL"} )

ThenConfigSelfHosting ==
    ( ~engine_root_provided /\
      config_exists /\ config_engine_valid /\
      engine_equals_target ) =>
        ( selected_mode = "UNRESOLVED" \/ selected_mode = "SELF_HOSTING" )

ThenConfigExternal ==
    ( ~engine_root_provided /\
      config_exists /\ config_engine_valid /\
      ~engine_equals_target ) =>
        ( selected_mode = "UNRESOLVED" \/ selected_mode = "EXTERNAL" )

ExplicitRootNeverInstalled ==
    engine_root_provided =>
        ( selected_mode = "UNRESOLVED" \/
          selected_mode \in {"SELF_HOSTING", "EXTERNAL"} )

NoSourceNoAuto ==
    ( ~engine_root_provided /\
      ~( config_exists /\ config_engine_valid ) /\
      ~auto_detect_success ) =>
        ( selected_mode = "UNRESOLVED" \/ selected_mode = "INSTALLED" )


vars == << pc, config_exists, config_engine_valid, engine_root_provided, 
           engine_equals_target, auto_detect_success, engine_resolved, 
           selected_mode >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ config_exists \in BOOLEAN
        /\ config_engine_valid \in BOOLEAN
        /\ engine_root_provided \in BOOLEAN
        /\ engine_equals_target \in BOOLEAN
        /\ auto_detect_success \in BOOLEAN
        /\ engine_resolved = FALSE
        /\ selected_mode = "UNRESOLVED"
        /\ pc = [self \in ProcSet |-> "ResolveConfig"]

ResolveConfig == /\ pc["main"] = "ResolveConfig"
                 /\ IF engine_root_provided
                       THEN /\ engine_resolved' = TRUE
                       ELSE /\ IF config_exists /\ config_engine_valid
                                  THEN /\ engine_resolved' = TRUE
                                  ELSE /\ TRUE
                                       /\ UNCHANGED engine_resolved
                 /\ pc' = [pc EXCEPT !["main"] = "AutoDetect"]
                 /\ UNCHANGED << config_exists, config_engine_valid, 
                                 engine_root_provided, engine_equals_target, 
                                 auto_detect_success, selected_mode >>

AutoDetect == /\ pc["main"] = "AutoDetect"
              /\ IF ~engine_resolved
                    THEN /\ IF auto_detect_success
                               THEN /\ engine_resolved' = TRUE
                               ELSE /\ TRUE
                                    /\ UNCHANGED engine_resolved
                    ELSE /\ TRUE
                         /\ UNCHANGED engine_resolved
              /\ pc' = [pc EXCEPT !["main"] = "SelectMode"]
              /\ UNCHANGED << config_exists, config_engine_valid, 
                              engine_root_provided, engine_equals_target, 
                              auto_detect_success, selected_mode >>

SelectMode == /\ pc["main"] = "SelectMode"
              /\ IF engine_resolved
                    THEN /\ IF engine_equals_target
                               THEN /\ selected_mode' = "SELF_HOSTING"
                               ELSE /\ selected_mode' = "EXTERNAL"
                    ELSE /\ selected_mode' = "INSTALLED"
              /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
              /\ UNCHANGED << config_exists, config_engine_valid, 
                              engine_root_provided, engine_equals_target, 
                              auto_detect_success, engine_resolved >>

Terminate == /\ pc["main"] = "Terminate"
             /\ Assert(selected_mode \in {"SELF_HOSTING", "EXTERNAL", "INSTALLED"}, 
                       "Failure of assertion at line 97, column 9.")
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << config_exists, config_engine_valid, 
                             engine_root_provided, engine_equals_target, 
                             auto_detect_success, engine_resolved, 
                             selected_mode >>

resolver == ResolveConfig \/ AutoDetect \/ SelectMode \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == resolver
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(resolver)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

=============================================================================
