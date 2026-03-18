---- MODULE GWT0009_CompileComposeVerify ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    Jobs,
    MaxSteps

ASSUME Jobs # {} /\ IsFiniteSet(Jobs)
ASSUME MaxSteps \in Nat /\ MaxSteps > 0

(* --algorithm GWT0009_CompileComposeVerify

variables
    job_state        = [j \in Jobs |-> "idle"],
    temp_dir         = [j \in Jobs |-> "none"],
    verified_tla     = [j \in Jobs |-> FALSE],
    verified_cfg     = [j \in Jobs |-> FALSE],
    files_uploaded   = [j \in Jobs |-> FALSE],
    container_exited = [j \in Jobs |-> FALSE],
    pcal_ok          = [j \in Jobs |-> FALSE],
    tlc_ok           = [j \in Jobs |-> FALSE],
    step_count       = [j \in Jobs |-> 0];

define

    AllStates == {"idle", "tempdir_created", "pcal_running",
                  "tlc_running", "pass", "fail",
                  "files_read", "uploaded", "exited"}

    ValidStates ==
        \A j \in Jobs : job_state[j] \in AllStates

    TempDirIsolation ==
        \A j1, j2 \in Jobs :
            (j1 # j2 /\ temp_dir[j1] # "none" /\ temp_dir[j2] # "none")
            => temp_dir[j1] # temp_dir[j2]

    UploadBeforeExit ==
        \A j \in Jobs :
            (container_exited[j] /\ pcal_ok[j] /\ tlc_ok[j])
            => files_uploaded[j]

    FilesReadBeforeUpload ==
        \A j \in Jobs :
            files_uploaded[j] => (verified_tla[j] /\ verified_cfg[j])

    UploadRequiresTempDir ==
        \A j \in Jobs :
            files_uploaded[j] => temp_dir[j] # "none"

    NoUploadOnFail ==
        \A j \in Jobs :
            (job_state[j] = "fail") => ~files_uploaded[j]

    TempDirOwnedByJob ==
        \A j \in Jobs :
            temp_dir[j] # "none" => temp_dir[j] = j

    BoundedExecution ==
        \A j \in Jobs : step_count[j] <= MaxSteps

end define;

fair process container \in Jobs
begin
    CreateTempDir:
        temp_dir[self]   := self;
        job_state[self]  := "tempdir_created";
        step_count[self] := step_count[self] + 1;

    RunPCal:
        job_state[self]  := "pcal_running";
        step_count[self] := step_count[self] + 1;

    PCAlChoice:
        either
            pcal_ok[self] := TRUE;
        or
            pcal_ok[self] := FALSE;
        end either;

    AfterPCal:
        if ~pcal_ok[self] then
            job_state[self] := "fail";
            goto CleanupFail;
        end if;

    RunTLC:
        job_state[self]  := "tlc_running";
        step_count[self] := step_count[self] + 1;

    TLCChoice:
        either
            tlc_ok[self] := TRUE;
        or
            tlc_ok[self] := FALSE;
        end either;

    AfterTLC:
        if ~tlc_ok[self] then
            job_state[self] := "fail";
            goto CleanupFail;
        end if;

    MarkPass:
        job_state[self]  := "pass";
        step_count[self] := step_count[self] + 1;

    ReadVerifiedFiles:
        assert temp_dir[self] = self;
        verified_tla[self] := TRUE;
        verified_cfg[self] := TRUE;
        job_state[self]    := "files_read";
        step_count[self]   := step_count[self] + 1;

    UploadToStorage:
        assert verified_tla[self] /\ verified_cfg[self];
        files_uploaded[self] := TRUE;
        job_state[self]      := "uploaded";
        step_count[self]     := step_count[self] + 1;

    ExitContainer:
        container_exited[self] := TRUE;
        job_state[self]        := "exited";
        step_count[self]       := step_count[self] + 1;
        goto Finish;

    CleanupFail:
        container_exited[self] := TRUE;
        step_count[self]       := step_count[self] + 1;

    Finish:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "8b0a4f8e" /\ chksum(tla) = "fa2da4d3")
VARIABLES pc, job_state, temp_dir, verified_tla, verified_cfg, files_uploaded, 
          container_exited, pcal_ok, tlc_ok, step_count

(* define statement *)
AllStates == {"idle", "tempdir_created", "pcal_running",
              "tlc_running", "pass", "fail",
              "files_read", "uploaded", "exited"}

ValidStates ==
    \A j \in Jobs : job_state[j] \in AllStates

TempDirIsolation ==
    \A j1, j2 \in Jobs :
        (j1 # j2 /\ temp_dir[j1] # "none" /\ temp_dir[j2] # "none")
        => temp_dir[j1] # temp_dir[j2]

UploadBeforeExit ==
    \A j \in Jobs :
        (container_exited[j] /\ pcal_ok[j] /\ tlc_ok[j])
        => files_uploaded[j]

FilesReadBeforeUpload ==
    \A j \in Jobs :
        files_uploaded[j] => (verified_tla[j] /\ verified_cfg[j])

UploadRequiresTempDir ==
    \A j \in Jobs :
        files_uploaded[j] => temp_dir[j] # "none"

NoUploadOnFail ==
    \A j \in Jobs :
        (job_state[j] = "fail") => ~files_uploaded[j]

TempDirOwnedByJob ==
    \A j \in Jobs :
        temp_dir[j] # "none" => temp_dir[j] = j

BoundedExecution ==
    \A j \in Jobs : step_count[j] <= MaxSteps


vars == << pc, job_state, temp_dir, verified_tla, verified_cfg, 
           files_uploaded, container_exited, pcal_ok, tlc_ok, step_count >>

ProcSet == (Jobs)

Init == (* Global variables *)
        /\ job_state = [j \in Jobs |-> "idle"]
        /\ temp_dir = [j \in Jobs |-> "none"]
        /\ verified_tla = [j \in Jobs |-> FALSE]
        /\ verified_cfg = [j \in Jobs |-> FALSE]
        /\ files_uploaded = [j \in Jobs |-> FALSE]
        /\ container_exited = [j \in Jobs |-> FALSE]
        /\ pcal_ok = [j \in Jobs |-> FALSE]
        /\ tlc_ok = [j \in Jobs |-> FALSE]
        /\ step_count = [j \in Jobs |-> 0]
        /\ pc = [self \in ProcSet |-> "CreateTempDir"]

CreateTempDir(self) == /\ pc[self] = "CreateTempDir"
                       /\ temp_dir' = [temp_dir EXCEPT ![self] = self]
                       /\ job_state' = [job_state EXCEPT ![self] = "tempdir_created"]
                       /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                       /\ pc' = [pc EXCEPT ![self] = "RunPCal"]
                       /\ UNCHANGED << verified_tla, verified_cfg, 
                                       files_uploaded, container_exited, 
                                       pcal_ok, tlc_ok >>

RunPCal(self) == /\ pc[self] = "RunPCal"
                 /\ job_state' = [job_state EXCEPT ![self] = "pcal_running"]
                 /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                 /\ pc' = [pc EXCEPT ![self] = "PCAlChoice"]
                 /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                 files_uploaded, container_exited, pcal_ok, 
                                 tlc_ok >>

PCAlChoice(self) == /\ pc[self] = "PCAlChoice"
                    /\ \/ /\ pcal_ok' = [pcal_ok EXCEPT ![self] = TRUE]
                       \/ /\ pcal_ok' = [pcal_ok EXCEPT ![self] = FALSE]
                    /\ pc' = [pc EXCEPT ![self] = "AfterPCal"]
                    /\ UNCHANGED << job_state, temp_dir, verified_tla, 
                                    verified_cfg, files_uploaded, 
                                    container_exited, tlc_ok, step_count >>

AfterPCal(self) == /\ pc[self] = "AfterPCal"
                   /\ IF ~pcal_ok[self]
                         THEN /\ job_state' = [job_state EXCEPT ![self] = "fail"]
                              /\ pc' = [pc EXCEPT ![self] = "CleanupFail"]
                         ELSE /\ pc' = [pc EXCEPT ![self] = "RunTLC"]
                              /\ UNCHANGED job_state
                   /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                   files_uploaded, container_exited, pcal_ok, 
                                   tlc_ok, step_count >>

RunTLC(self) == /\ pc[self] = "RunTLC"
                /\ job_state' = [job_state EXCEPT ![self] = "tlc_running"]
                /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                /\ pc' = [pc EXCEPT ![self] = "TLCChoice"]
                /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                files_uploaded, container_exited, pcal_ok, 
                                tlc_ok >>

TLCChoice(self) == /\ pc[self] = "TLCChoice"
                   /\ \/ /\ tlc_ok' = [tlc_ok EXCEPT ![self] = TRUE]
                      \/ /\ tlc_ok' = [tlc_ok EXCEPT ![self] = FALSE]
                   /\ pc' = [pc EXCEPT ![self] = "AfterTLC"]
                   /\ UNCHANGED << job_state, temp_dir, verified_tla, 
                                   verified_cfg, files_uploaded, 
                                   container_exited, pcal_ok, step_count >>

AfterTLC(self) == /\ pc[self] = "AfterTLC"
                  /\ IF ~tlc_ok[self]
                        THEN /\ job_state' = [job_state EXCEPT ![self] = "fail"]
                             /\ pc' = [pc EXCEPT ![self] = "CleanupFail"]
                        ELSE /\ pc' = [pc EXCEPT ![self] = "MarkPass"]
                             /\ UNCHANGED job_state
                  /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                  files_uploaded, container_exited, pcal_ok, 
                                  tlc_ok, step_count >>

MarkPass(self) == /\ pc[self] = "MarkPass"
                  /\ job_state' = [job_state EXCEPT ![self] = "pass"]
                  /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                  /\ pc' = [pc EXCEPT ![self] = "ReadVerifiedFiles"]
                  /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                  files_uploaded, container_exited, pcal_ok, 
                                  tlc_ok >>

ReadVerifiedFiles(self) == /\ pc[self] = "ReadVerifiedFiles"
                           /\ Assert(temp_dir[self] = self, 
                                     "Failure of assertion at line 111, column 9.")
                           /\ verified_tla' = [verified_tla EXCEPT ![self] = TRUE]
                           /\ verified_cfg' = [verified_cfg EXCEPT ![self] = TRUE]
                           /\ job_state' = [job_state EXCEPT ![self] = "files_read"]
                           /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                           /\ pc' = [pc EXCEPT ![self] = "UploadToStorage"]
                           /\ UNCHANGED << temp_dir, files_uploaded, 
                                           container_exited, pcal_ok, tlc_ok >>

UploadToStorage(self) == /\ pc[self] = "UploadToStorage"
                         /\ Assert(verified_tla[self] /\ verified_cfg[self], 
                                   "Failure of assertion at line 118, column 9.")
                         /\ files_uploaded' = [files_uploaded EXCEPT ![self] = TRUE]
                         /\ job_state' = [job_state EXCEPT ![self] = "uploaded"]
                         /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                         /\ pc' = [pc EXCEPT ![self] = "ExitContainer"]
                         /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                         container_exited, pcal_ok, tlc_ok >>

ExitContainer(self) == /\ pc[self] = "ExitContainer"
                       /\ container_exited' = [container_exited EXCEPT ![self] = TRUE]
                       /\ job_state' = [job_state EXCEPT ![self] = "exited"]
                       /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                       /\ pc' = [pc EXCEPT ![self] = "Finish"]
                       /\ UNCHANGED << temp_dir, verified_tla, verified_cfg, 
                                       files_uploaded, pcal_ok, tlc_ok >>

CleanupFail(self) == /\ pc[self] = "CleanupFail"
                     /\ container_exited' = [container_exited EXCEPT ![self] = TRUE]
                     /\ step_count' = [step_count EXCEPT ![self] = step_count[self] + 1]
                     /\ pc' = [pc EXCEPT ![self] = "Finish"]
                     /\ UNCHANGED << job_state, temp_dir, verified_tla, 
                                     verified_cfg, files_uploaded, pcal_ok, 
                                     tlc_ok >>

Finish(self) == /\ pc[self] = "Finish"
                /\ TRUE
                /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << job_state, temp_dir, verified_tla, 
                                verified_cfg, files_uploaded, container_exited, 
                                pcal_ok, tlc_ok, step_count >>

container(self) == CreateTempDir(self) \/ RunPCal(self) \/ PCAlChoice(self)
                      \/ AfterPCal(self) \/ RunTLC(self) \/ TLCChoice(self)
                      \/ AfterTLC(self) \/ MarkPass(self)
                      \/ ReadVerifiedFiles(self) \/ UploadToStorage(self)
                      \/ ExitContainer(self) \/ CleanupFail(self)
                      \/ Finish(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in Jobs: container(self))
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ \A self \in Jobs : WF_vars(container(self))

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
