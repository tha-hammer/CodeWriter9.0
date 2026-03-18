---- MODULE RegisterPayload ----

EXTENDS Integers, TLC

CONSTANTS
    NumGWT,
    NumREQ

(* --algorithm RegisterPayload

variables
    phase = "Init",
    dag_loaded = FALSE,
    bindings_loaded = FALSE,
    gwt_done = 0,
    req_done = 0,
    closure_valid = FALSE,
    bindings_saved = FALSE,
    dag_uploaded = FALSE,
    bindings_uploaded = FALSE,
    llm_called = FALSE;

define

    NeverCallsLLM == ~llm_called

    BindingsSavedBeforeUpload ==
        bindings_uploaded => bindings_saved

    DagUploadedOnlyAfterMutation ==
        dag_uploaded =>
            (gwt_done = NumGWT /\ req_done = NumREQ /\ closure_valid)

    DagUploadedOnlyAfterBindingsSaved ==
        dag_uploaded => bindings_saved

    ClosureSetBeforeUpload ==
        dag_uploaded => closure_valid

    CompletionImpliesFullProtocol ==
        (phase = "Complete") =>
            (dag_loaded
             /\ bindings_loaded
             /\ gwt_done = NumGWT
             /\ req_done = NumREQ
             /\ closure_valid
             /\ bindings_saved
             /\ dag_uploaded
             /\ bindings_uploaded
             /\ ~llm_called)

    TypeOK ==
        /\ phase \in {"Init", "LoadDag", "LoadBindings",
                      "RegisterGWT", "RegisterREQ",
                      "ClosureRecomputed",
                      "SaveBindings", "UploadDag", "UploadBindings",
                      "Complete"}
        /\ dag_loaded \in BOOLEAN
        /\ bindings_loaded \in BOOLEAN
        /\ gwt_done \in 0..NumGWT
        /\ req_done \in 0..NumREQ
        /\ closure_valid \in BOOLEAN
        /\ bindings_saved \in BOOLEAN
        /\ dag_uploaded \in BOOLEAN
        /\ bindings_uploaded \in BOOLEAN
        /\ llm_called \in BOOLEAN

end define;

fair process register = "register_payload"
begin
    LoadDag:
        dag_loaded := TRUE;
        phase      := "LoadDag";

    LoadBindings:
        bindings_loaded := TRUE;
        phase           := "LoadBindings";

    RegisterGWTs:
        while gwt_done < NumGWT do
            gwt_done := gwt_done + 1;
            phase    := "RegisterGWT";
        end while;

    RegisterREQs:
        while req_done < NumREQ do
            req_done := req_done + 1;
            phase    := "RegisterREQ";
        end while;

    MarkClosure:
        closure_valid := TRUE;
        phase         := "ClosureRecomputed";

    SaveBindings:
        bindings_saved := TRUE;
        phase          := "SaveBindings";

    UploadDag:
        dag_uploaded := TRUE;
        phase        := "UploadDag";

    UploadBindings:
        bindings_uploaded := TRUE;
        phase             := "UploadBindings";

    Complete:
        phase := "Complete";

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "5cc4d070" /\ chksum(tla) = "901823c7")
VARIABLES pc, phase, dag_loaded, bindings_loaded, gwt_done, req_done, 
          closure_valid, bindings_saved, dag_uploaded, bindings_uploaded, 
          llm_called

(* define statement *)
NeverCallsLLM == ~llm_called

BindingsSavedBeforeUpload ==
    bindings_uploaded => bindings_saved

DagUploadedOnlyAfterMutation ==
    dag_uploaded =>
        (gwt_done = NumGWT /\ req_done = NumREQ /\ closure_valid)

DagUploadedOnlyAfterBindingsSaved ==
    dag_uploaded => bindings_saved

ClosureSetBeforeUpload ==
    dag_uploaded => closure_valid

CompletionImpliesFullProtocol ==
    (phase = "Complete") =>
        (dag_loaded
         /\ bindings_loaded
         /\ gwt_done = NumGWT
         /\ req_done = NumREQ
         /\ closure_valid
         /\ bindings_saved
         /\ dag_uploaded
         /\ bindings_uploaded
         /\ ~llm_called)

TypeOK ==
    /\ phase \in {"Init", "LoadDag", "LoadBindings",
                  "RegisterGWT", "RegisterREQ",
                  "ClosureRecomputed",
                  "SaveBindings", "UploadDag", "UploadBindings",
                  "Complete"}
    /\ dag_loaded \in BOOLEAN
    /\ bindings_loaded \in BOOLEAN
    /\ gwt_done \in 0..NumGWT
    /\ req_done \in 0..NumREQ
    /\ closure_valid \in BOOLEAN
    /\ bindings_saved \in BOOLEAN
    /\ dag_uploaded \in BOOLEAN
    /\ bindings_uploaded \in BOOLEAN
    /\ llm_called \in BOOLEAN


vars == << pc, phase, dag_loaded, bindings_loaded, gwt_done, req_done, 
           closure_valid, bindings_saved, dag_uploaded, bindings_uploaded, 
           llm_called >>

ProcSet == {"register_payload"}

Init == (* Global variables *)
        /\ phase = "Init"
        /\ dag_loaded = FALSE
        /\ bindings_loaded = FALSE
        /\ gwt_done = 0
        /\ req_done = 0
        /\ closure_valid = FALSE
        /\ bindings_saved = FALSE
        /\ dag_uploaded = FALSE
        /\ bindings_uploaded = FALSE
        /\ llm_called = FALSE
        /\ pc = [self \in ProcSet |-> "LoadDag"]

LoadDag == /\ pc["register_payload"] = "LoadDag"
           /\ dag_loaded' = TRUE
           /\ phase' = "LoadDag"
           /\ pc' = [pc EXCEPT !["register_payload"] = "LoadBindings"]
           /\ UNCHANGED << bindings_loaded, gwt_done, req_done, closure_valid, 
                           bindings_saved, dag_uploaded, bindings_uploaded, 
                           llm_called >>

LoadBindings == /\ pc["register_payload"] = "LoadBindings"
                /\ bindings_loaded' = TRUE
                /\ phase' = "LoadBindings"
                /\ pc' = [pc EXCEPT !["register_payload"] = "RegisterGWTs"]
                /\ UNCHANGED << dag_loaded, gwt_done, req_done, closure_valid, 
                                bindings_saved, dag_uploaded, 
                                bindings_uploaded, llm_called >>

RegisterGWTs == /\ pc["register_payload"] = "RegisterGWTs"
                /\ IF gwt_done < NumGWT
                      THEN /\ gwt_done' = gwt_done + 1
                           /\ phase' = "RegisterGWT"
                           /\ pc' = [pc EXCEPT !["register_payload"] = "RegisterGWTs"]
                      ELSE /\ pc' = [pc EXCEPT !["register_payload"] = "RegisterREQs"]
                           /\ UNCHANGED << phase, gwt_done >>
                /\ UNCHANGED << dag_loaded, bindings_loaded, req_done, 
                                closure_valid, bindings_saved, dag_uploaded, 
                                bindings_uploaded, llm_called >>

RegisterREQs == /\ pc["register_payload"] = "RegisterREQs"
                /\ IF req_done < NumREQ
                      THEN /\ req_done' = req_done + 1
                           /\ phase' = "RegisterREQ"
                           /\ pc' = [pc EXCEPT !["register_payload"] = "RegisterREQs"]
                      ELSE /\ pc' = [pc EXCEPT !["register_payload"] = "MarkClosure"]
                           /\ UNCHANGED << phase, req_done >>
                /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, 
                                closure_valid, bindings_saved, dag_uploaded, 
                                bindings_uploaded, llm_called >>

MarkClosure == /\ pc["register_payload"] = "MarkClosure"
               /\ closure_valid' = TRUE
               /\ phase' = "ClosureRecomputed"
               /\ pc' = [pc EXCEPT !["register_payload"] = "SaveBindings"]
               /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, req_done, 
                               bindings_saved, dag_uploaded, bindings_uploaded, 
                               llm_called >>

SaveBindings == /\ pc["register_payload"] = "SaveBindings"
                /\ bindings_saved' = TRUE
                /\ phase' = "SaveBindings"
                /\ pc' = [pc EXCEPT !["register_payload"] = "UploadDag"]
                /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, 
                                req_done, closure_valid, dag_uploaded, 
                                bindings_uploaded, llm_called >>

UploadDag == /\ pc["register_payload"] = "UploadDag"
             /\ dag_uploaded' = TRUE
             /\ phase' = "UploadDag"
             /\ pc' = [pc EXCEPT !["register_payload"] = "UploadBindings"]
             /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, req_done, 
                             closure_valid, bindings_saved, bindings_uploaded, 
                             llm_called >>

UploadBindings == /\ pc["register_payload"] = "UploadBindings"
                  /\ bindings_uploaded' = TRUE
                  /\ phase' = "UploadBindings"
                  /\ pc' = [pc EXCEPT !["register_payload"] = "Complete"]
                  /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, 
                                  req_done, closure_valid, bindings_saved, 
                                  dag_uploaded, llm_called >>

Complete == /\ pc["register_payload"] = "Complete"
            /\ phase' = "Complete"
            /\ pc' = [pc EXCEPT !["register_payload"] = "Done"]
            /\ UNCHANGED << dag_loaded, bindings_loaded, gwt_done, req_done, 
                            closure_valid, bindings_saved, dag_uploaded, 
                            bindings_uploaded, llm_called >>

register == LoadDag \/ LoadBindings \/ RegisterGWTs \/ RegisterREQs
               \/ MarkClosure \/ SaveBindings \/ UploadDag
               \/ UploadBindings \/ Complete

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == register
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(register)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
