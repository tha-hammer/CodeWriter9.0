---- MODULE SelfHostingContext ----

EXTENDS Integers, TLC

CONSTANTS
    EngineRootPath,
    MaxSteps

(* --algorithm SelfHostingContext

variables
    engine_root       = EngineRootPath,
    target_root       = "UNSET",
    state_root        = "UNSET",
    spec_dir_location = "UNSET",
    template_dir      = "UNSET",
    artifact_dir      = "UNSET",
    test_output_dir   = "UNSET",
    is_self_hosting   = FALSE,
    paths_equal       = FALSE,
    phase             = "INIT",
    step_count        = 0;

define
    INSTANCES == "INSTANCES"
    CW9_SPECS == "CW9_SPECS"

    TypeInvariant ==
        /\ spec_dir_location \in {"UNSET", INSTANCES, CW9_SPECS}
        /\ is_self_hosting   \in BOOLEAN
        /\ paths_equal       \in BOOLEAN
        /\ phase             \in {"INIT", "CALLING", "CONSTRUCTING", "COMPLETE"}
        /\ step_count        \in 0..MaxSteps

    RootsAligned ==
        phase = "COMPLETE" =>
            /\ target_root = engine_root
            /\ state_root  = engine_root

    SpecInInstancesDir ==
        phase = "COMPLETE" => spec_dir_location = INSTANCES

    NoCW9Indirection ==
        phase = "COMPLETE" => spec_dir_location # CW9_SPECS

    SelfHostingFlagSet ==
        phase = "COMPLETE" => is_self_hosting = TRUE

    PathsEqualConsistent ==
        phase = "COMPLETE" =>
            paths_equal = (target_root = engine_root /\ state_root = engine_root)

    BoundedExecution == step_count <= MaxSteps

    SelfHostingCorrect ==
        /\ RootsAligned
        /\ SpecInInstancesDir
        /\ NoCW9Indirection
        /\ SelfHostingFlagSet
        /\ PathsEqualConsistent

end define;

fair process selfHosting = "main"
begin
    CallSelfHosting:
        phase      := "CALLING";
        step_count := step_count + 1;

    SetRoots:
        target_root := engine_root;
        state_root  := engine_root;
        step_count  := step_count + 1;

    SetDerivedPaths:
        phase             := "CONSTRUCTING";
        spec_dir_location := INSTANCES;
        template_dir      := engine_root;
        artifact_dir      := engine_root;
        test_output_dir   := engine_root;
        is_self_hosting   := TRUE;
        step_count        := step_count + 1;

    ComputePathsEqual:
        paths_equal := (target_root = engine_root) /\ (state_root = engine_root);
        phase       := "COMPLETE";
        step_count  := step_count + 1;

    Finish:
        assert paths_equal        = TRUE;
        assert target_root        = engine_root;
        assert state_root         = engine_root;
        assert spec_dir_location  = INSTANCES;
        assert spec_dir_location  # CW9_SPECS;
        assert is_self_hosting    = TRUE;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "37e0df00" /\ chksum(tla) = "9061d686")
VARIABLES pc, engine_root, target_root, state_root, spec_dir_location, 
          template_dir, artifact_dir, test_output_dir, is_self_hosting, 
          paths_equal, phase, step_count

(* define statement *)
INSTANCES == "INSTANCES"
CW9_SPECS == "CW9_SPECS"

TypeInvariant ==
    /\ spec_dir_location \in {"UNSET", INSTANCES, CW9_SPECS}
    /\ is_self_hosting   \in BOOLEAN
    /\ paths_equal       \in BOOLEAN
    /\ phase             \in {"INIT", "CALLING", "CONSTRUCTING", "COMPLETE"}
    /\ step_count        \in 0..MaxSteps

RootsAligned ==
    phase = "COMPLETE" =>
        /\ target_root = engine_root
        /\ state_root  = engine_root

SpecInInstancesDir ==
    phase = "COMPLETE" => spec_dir_location = INSTANCES

NoCW9Indirection ==
    phase = "COMPLETE" => spec_dir_location # CW9_SPECS

SelfHostingFlagSet ==
    phase = "COMPLETE" => is_self_hosting = TRUE

PathsEqualConsistent ==
    phase = "COMPLETE" =>
        paths_equal = (target_root = engine_root /\ state_root = engine_root)

BoundedExecution == step_count <= MaxSteps

SelfHostingCorrect ==
    /\ RootsAligned
    /\ SpecInInstancesDir
    /\ NoCW9Indirection
    /\ SelfHostingFlagSet
    /\ PathsEqualConsistent


vars == << pc, engine_root, target_root, state_root, spec_dir_location, 
           template_dir, artifact_dir, test_output_dir, is_self_hosting, 
           paths_equal, phase, step_count >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ engine_root = EngineRootPath
        /\ target_root = "UNSET"
        /\ state_root = "UNSET"
        /\ spec_dir_location = "UNSET"
        /\ template_dir = "UNSET"
        /\ artifact_dir = "UNSET"
        /\ test_output_dir = "UNSET"
        /\ is_self_hosting = FALSE
        /\ paths_equal = FALSE
        /\ phase = "INIT"
        /\ step_count = 0
        /\ pc = [self \in ProcSet |-> "CallSelfHosting"]

CallSelfHosting == /\ pc["main"] = "CallSelfHosting"
                   /\ phase' = "CALLING"
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["main"] = "SetRoots"]
                   /\ UNCHANGED << engine_root, target_root, state_root, 
                                   spec_dir_location, template_dir, 
                                   artifact_dir, test_output_dir, 
                                   is_self_hosting, paths_equal >>

SetRoots == /\ pc["main"] = "SetRoots"
            /\ target_root' = engine_root
            /\ state_root' = engine_root
            /\ step_count' = step_count + 1
            /\ pc' = [pc EXCEPT !["main"] = "SetDerivedPaths"]
            /\ UNCHANGED << engine_root, spec_dir_location, template_dir, 
                            artifact_dir, test_output_dir, is_self_hosting, 
                            paths_equal, phase >>

SetDerivedPaths == /\ pc["main"] = "SetDerivedPaths"
                   /\ phase' = "CONSTRUCTING"
                   /\ spec_dir_location' = INSTANCES
                   /\ template_dir' = engine_root
                   /\ artifact_dir' = engine_root
                   /\ test_output_dir' = engine_root
                   /\ is_self_hosting' = TRUE
                   /\ step_count' = step_count + 1
                   /\ pc' = [pc EXCEPT !["main"] = "ComputePathsEqual"]
                   /\ UNCHANGED << engine_root, target_root, state_root, 
                                   paths_equal >>

ComputePathsEqual == /\ pc["main"] = "ComputePathsEqual"
                     /\ paths_equal' = ((target_root = engine_root) /\ (state_root = engine_root))
                     /\ phase' = "COMPLETE"
                     /\ step_count' = step_count + 1
                     /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                     /\ UNCHANGED << engine_root, target_root, state_root, 
                                     spec_dir_location, template_dir, 
                                     artifact_dir, test_output_dir, 
                                     is_self_hosting >>

Finish == /\ pc["main"] = "Finish"
          /\ Assert(paths_equal        = TRUE, 
                    "Failure of assertion at line 90, column 9.")
          /\ Assert(target_root        = engine_root, 
                    "Failure of assertion at line 91, column 9.")
          /\ Assert(state_root         = engine_root, 
                    "Failure of assertion at line 92, column 9.")
          /\ Assert(spec_dir_location  = INSTANCES, 
                    "Failure of assertion at line 93, column 9.")
          /\ Assert(spec_dir_location  # CW9_SPECS, 
                    "Failure of assertion at line 94, column 9.")
          /\ Assert(is_self_hosting    = TRUE, 
                    "Failure of assertion at line 95, column 9.")
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << engine_root, target_root, state_root, 
                          spec_dir_location, template_dir, artifact_dir, 
                          test_output_dir, is_self_hosting, paths_equal, phase, 
                          step_count >>

selfHosting == CallSelfHosting \/ SetRoots \/ SetDerivedPaths
                  \/ ComputePathsEqual \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == selfHosting
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(selfHosting)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
