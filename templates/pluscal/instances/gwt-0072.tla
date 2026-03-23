---- MODULE TemplateSelectedByAnnotation ----

EXTENDS Integers, TLC, FiniteSets

NoMetadata    == 0
DefaultTmpl   == 1
ObsTmpl       == 2
UnknownTmpl   == 3

KnownTemplates == {DefaultTmpl, ObsTmpl}

(* --algorithm TemplateSelectedByAnnotation

variables
    gwt_metadata     = NoMetadata,
    selected_template = DefaultTmpl,
    file_exists      = FALSE,
    template_loaded  = FALSE,
    error            = FALSE,
    phase            = "idle";

define

    TypeOK ==
        /\ gwt_metadata \in {NoMetadata, DefaultTmpl, ObsTmpl, UnknownTmpl}
        /\ selected_template \in {DefaultTmpl, ObsTmpl, UnknownTmpl}
        /\ error \in BOOLEAN
        /\ template_loaded \in BOOLEAN
        /\ file_exists \in BOOLEAN

    DefaultFallback ==
        (phase = "prompt_built" /\ gwt_metadata = NoMetadata) =>
            selected_template = DefaultTmpl

    AnnotationRespected ==
        \A t \in KnownTemplates :
            (phase = "prompt_built" /\ gwt_metadata = t) =>
                selected_template = t

    NoSilentFallback ==
        ~(gwt_metadata = UnknownTmpl /\ template_loaded = TRUE)

    PromptBuiltOnlyIfLoaded ==
        phase = "prompt_built" => template_loaded = TRUE

    ErrorMeansNoPrompt ==
        error = TRUE => phase # "prompt_built"

    UnknownTemplateImpliesError ==
        (gwt_metadata = UnknownTmpl /\
         phase \notin {"idle", "metadata_read", "template_resolved"}) =>
            error = TRUE

    KnownTemplateNeverErrors ==
        (gwt_metadata \in KnownTemplates /\
         phase \notin {"idle", "metadata_read"}) =>
            error = FALSE

end define;

fair process runner = "main"
begin
    ChooseInput:
        either
            gwt_metadata := NoMetadata;
        or
            gwt_metadata := DefaultTmpl;
        or
            gwt_metadata := ObsTmpl;
        or
            gwt_metadata := UnknownTmpl;
        end either;
        phase := "metadata_read";

    ReadMeta:
        if gwt_metadata = NoMetadata then
            selected_template := DefaultTmpl;
        else
            selected_template := gwt_metadata;
        end if;
        phase := "template_resolved";

    CheckFile:
        if selected_template \in KnownTemplates then
            file_exists := TRUE;
            phase := "exists_checked";
        else
            error := TRUE;
            phase := "error_raised";
        end if;

    MaybeLoad:
        if error = TRUE then
            goto Terminate;
        end if;

    LoadContent:
        template_loaded := TRUE;
        phase := "content_loaded";

    BuildPrompt:
        phase := "prompt_built";

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "357632b0" /\ chksum(tla) = "c73aceb1")
VARIABLES pc, gwt_metadata, selected_template, file_exists, template_loaded, 
          error, phase

(* define statement *)
TypeOK ==
    /\ gwt_metadata \in {NoMetadata, DefaultTmpl, ObsTmpl, UnknownTmpl}
    /\ selected_template \in {DefaultTmpl, ObsTmpl, UnknownTmpl}
    /\ error \in BOOLEAN
    /\ template_loaded \in BOOLEAN
    /\ file_exists \in BOOLEAN

DefaultFallback ==
    (phase = "prompt_built" /\ gwt_metadata = NoMetadata) =>
        selected_template = DefaultTmpl

AnnotationRespected ==
    \A t \in KnownTemplates :
        (phase = "prompt_built" /\ gwt_metadata = t) =>
            selected_template = t

NoSilentFallback ==
    ~(gwt_metadata = UnknownTmpl /\ template_loaded = TRUE)

PromptBuiltOnlyIfLoaded ==
    phase = "prompt_built" => template_loaded = TRUE

ErrorMeansNoPrompt ==
    error = TRUE => phase # "prompt_built"

UnknownTemplateImpliesError ==
    (gwt_metadata = UnknownTmpl /\
     phase \notin {"idle", "metadata_read", "template_resolved"}) =>
        error = TRUE

KnownTemplateNeverErrors ==
    (gwt_metadata \in KnownTemplates /\
     phase \notin {"idle", "metadata_read"}) =>
        error = FALSE


vars == << pc, gwt_metadata, selected_template, file_exists, template_loaded, 
           error, phase >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ gwt_metadata = NoMetadata
        /\ selected_template = DefaultTmpl
        /\ file_exists = FALSE
        /\ template_loaded = FALSE
        /\ error = FALSE
        /\ phase = "idle"
        /\ pc = [self \in ProcSet |-> "ChooseInput"]

ChooseInput == /\ pc["main"] = "ChooseInput"
               /\ \/ /\ gwt_metadata' = NoMetadata
                  \/ /\ gwt_metadata' = DefaultTmpl
                  \/ /\ gwt_metadata' = ObsTmpl
                  \/ /\ gwt_metadata' = UnknownTmpl
               /\ phase' = "metadata_read"
               /\ pc' = [pc EXCEPT !["main"] = "ReadMeta"]
               /\ UNCHANGED << selected_template, file_exists, template_loaded, 
                               error >>

ReadMeta == /\ pc["main"] = "ReadMeta"
            /\ IF gwt_metadata = NoMetadata
                  THEN /\ selected_template' = DefaultTmpl
                  ELSE /\ selected_template' = gwt_metadata
            /\ phase' = "template_resolved"
            /\ pc' = [pc EXCEPT !["main"] = "CheckFile"]
            /\ UNCHANGED << gwt_metadata, file_exists, template_loaded, error >>

CheckFile == /\ pc["main"] = "CheckFile"
             /\ IF selected_template \in KnownTemplates
                   THEN /\ file_exists' = TRUE
                        /\ phase' = "exists_checked"
                        /\ error' = error
                   ELSE /\ error' = TRUE
                        /\ phase' = "error_raised"
                        /\ UNCHANGED file_exists
             /\ pc' = [pc EXCEPT !["main"] = "MaybeLoad"]
             /\ UNCHANGED << gwt_metadata, selected_template, template_loaded >>

MaybeLoad == /\ pc["main"] = "MaybeLoad"
             /\ IF error = TRUE
                   THEN /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
                   ELSE /\ pc' = [pc EXCEPT !["main"] = "LoadContent"]
             /\ UNCHANGED << gwt_metadata, selected_template, file_exists, 
                             template_loaded, error, phase >>

LoadContent == /\ pc["main"] = "LoadContent"
               /\ template_loaded' = TRUE
               /\ phase' = "content_loaded"
               /\ pc' = [pc EXCEPT !["main"] = "BuildPrompt"]
               /\ UNCHANGED << gwt_metadata, selected_template, file_exists, 
                               error >>

BuildPrompt == /\ pc["main"] = "BuildPrompt"
               /\ phase' = "prompt_built"
               /\ pc' = [pc EXCEPT !["main"] = "Terminate"]
               /\ UNCHANGED << gwt_metadata, selected_template, file_exists, 
                               template_loaded, error >>

Terminate == /\ pc["main"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["main"] = "Done"]
             /\ UNCHANGED << gwt_metadata, selected_template, file_exists, 
                             template_loaded, error, phase >>

runner == ChooseInput \/ ReadMeta \/ CheckFile \/ MaybeLoad \/ LoadContent
             \/ BuildPrompt \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == runner
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(runner)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
