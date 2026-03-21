---------------------------- MODULE CW7Extract ----------------------------

EXTENDS Integers, Sequences, FiniteSets, TLC

CW7_PREFIX == "cw7-crit-"
GWT_FORMAT == "gwt"

SessionIdProvided == FALSE
SessionCount      == 1
NumReqs           == 2
NumAcRows         == 3

AcFormats == [i \in 1..NumAcRows |->
                IF i = 2 THEN "other" ELSE "gwt"]

WhenEmpty == [i \in 1..NumAcRows |-> i = 3]

(* --algorithm CW7Extract

variables
    phase            = "start",
    resolved_session = 0,
    req_index        = 1,
    ac_index         = 1,
    output_reqs      = <<>>,
    output_gwts      = <<>>,
    raised_error     = "";

define

    GWTIndices == {i \in 1..NumAcRows : AcFormats[i] = GWT_FORMAT}

    ValidPhase ==
        phase \in {"start", "query_reqs", "query_gwts",
                   "complete", "err_no_session", "err_multi_session"}

    OutputReqsShape ==
        phase = "complete" =>
            /\ Len(output_reqs) = NumReqs
            /\ \A k \in 1..Len(output_reqs) :
                /\ "id"   \in DOMAIN output_reqs[k]
                /\ "text" \in DOMAIN output_reqs[k]

    OutputGWTsShape ==
        phase = "complete" =>
            /\ Len(output_gwts) = Cardinality(GWTIndices)
            /\ \A k \in 1..Len(output_gwts) :
                /\ "criterion_id" \in DOMAIN output_gwts[k]
                /\ "given_c"      \in DOMAIN output_gwts[k]
                /\ "when_c"       \in DOMAIN output_gwts[k]
                /\ "then_c"       \in DOMAIN output_gwts[k]
                /\ "parent_req"   \in DOMAIN output_gwts[k]

    CriterionIdPrefixOK ==
        phase = "complete" =>
            \A k \in 1..Len(output_gwts) :
                output_gwts[k].criterion_id.prefix = CW7_PREFIX

    NameConditional ==
        phase = "complete" =>
            \A k \in 1..Len(output_gwts) :
                "name" \in DOMAIN output_gwts[k] <=> ~output_gwts[k].when_was_empty

    NoOutputOnError ==
        phase \in {"err_no_session", "err_multi_session"} =>
            output_reqs = <<>> /\ output_gwts = <<>>

    SuccessImpliesValidSession ==
        phase = "complete" => (SessionCount = 1 \/ SessionIdProvided)

    ErrorOnZeroSessions ==
        (~SessionIdProvided /\ SessionCount = 0) => phase /= "complete"

    ErrorOnMultiSessions ==
        (~SessionIdProvided /\ SessionCount = 2) => phase /= "complete"

    OnlyGWTFormatIncluded ==
        phase = "complete" =>
            Len(output_gwts) =
                Cardinality({i \in 1..NumAcRows : AcFormats[i] = GWT_FORMAT})

    Invariants ==
        ValidPhase
        /\ OutputReqsShape
        /\ OutputGWTsShape
        /\ CriterionIdPrefixOK
        /\ NameConditional
        /\ NoOutputOnError
        /\ SuccessImpliesValidSession
        /\ ErrorOnZeroSessions
        /\ ErrorOnMultiSessions
        /\ OnlyGWTFormatIncluded

end define;

fair process extract = "extract"
begin
    Resolve:
        if SessionIdProvided then
            resolved_session := 1;
            phase := "query_reqs";
        elsif SessionCount = 0 then
            phase := "err_no_session";
            raised_error := "ValueError: no sessions found";
            goto Terminate;
        elsif SessionCount = 2 then
            phase := "err_multi_session";
            raised_error := "ValueError: multiple sessions, specify session_id";
            goto Terminate;
        else
            resolved_session := 1;
            phase := "query_reqs";
        end if;

    QueryReqs:
        req_index   := 1;
        output_reqs := <<>>;

    ReqLoop:
        while req_index <= NumReqs do
            ReqStep:
                output_reqs := Append(output_reqs,
                    [id |-> req_index, text |-> req_index]);
                req_index := req_index + 1;
        end while;

    StartGWT:
        ac_index    := 1;
        output_gwts := <<>>;
        phase       := "query_gwts";

    GWTLoop:
        while ac_index <= NumAcRows do
            GWTCheck:
                if AcFormats[ac_index] = GWT_FORMAT then
                    if WhenEmpty[ac_index] then
                        output_gwts := Append(output_gwts,
                            [criterion_id  |-> [prefix |-> CW7_PREFIX,
                                                num    |-> ac_index],
                             given_c        |-> "",
                             when_c         |-> "",
                             then_c         |-> "",
                             parent_req     |-> resolved_session,
                             when_was_empty |-> TRUE]);
                    else
                        output_gwts := Append(output_gwts,
                            [criterion_id  |-> [prefix |-> CW7_PREFIX,
                                                num    |-> ac_index],
                             given_c        |-> "",
                             when_c         |-> "nonempty",
                             then_c         |-> "",
                             parent_req     |-> resolved_session,
                             when_was_empty |-> FALSE,
                             name           |-> "slug"]);
                    end if;
                end if;
            GWTIncr:
                ac_index := ac_index + 1;
        end while;

    Complete:
        phase := "complete";

    Terminate:
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "82aa31db" /\ chksum(tla) = "68080c64")
VARIABLES pc, phase, resolved_session, req_index, ac_index, output_reqs, 
          output_gwts, raised_error

(* define statement *)
GWTIndices == {i \in 1..NumAcRows : AcFormats[i] = GWT_FORMAT}

ValidPhase ==
    phase \in {"start", "query_reqs", "query_gwts",
               "complete", "err_no_session", "err_multi_session"}

OutputReqsShape ==
    phase = "complete" =>
        /\ Len(output_reqs) = NumReqs
        /\ \A k \in 1..Len(output_reqs) :
            /\ "id"   \in DOMAIN output_reqs[k]
            /\ "text" \in DOMAIN output_reqs[k]

OutputGWTsShape ==
    phase = "complete" =>
        /\ Len(output_gwts) = Cardinality(GWTIndices)
        /\ \A k \in 1..Len(output_gwts) :
            /\ "criterion_id" \in DOMAIN output_gwts[k]
            /\ "given_c"      \in DOMAIN output_gwts[k]
            /\ "when_c"       \in DOMAIN output_gwts[k]
            /\ "then_c"       \in DOMAIN output_gwts[k]
            /\ "parent_req"   \in DOMAIN output_gwts[k]

CriterionIdPrefixOK ==
    phase = "complete" =>
        \A k \in 1..Len(output_gwts) :
            output_gwts[k].criterion_id.prefix = CW7_PREFIX

NameConditional ==
    phase = "complete" =>
        \A k \in 1..Len(output_gwts) :
            "name" \in DOMAIN output_gwts[k] <=> ~output_gwts[k].when_was_empty

NoOutputOnError ==
    phase \in {"err_no_session", "err_multi_session"} =>
        output_reqs = <<>> /\ output_gwts = <<>>

SuccessImpliesValidSession ==
    phase = "complete" => (SessionCount = 1 \/ SessionIdProvided)

ErrorOnZeroSessions ==
    (~SessionIdProvided /\ SessionCount = 0) => phase /= "complete"

ErrorOnMultiSessions ==
    (~SessionIdProvided /\ SessionCount = 2) => phase /= "complete"

OnlyGWTFormatIncluded ==
    phase = "complete" =>
        Len(output_gwts) =
            Cardinality({i \in 1..NumAcRows : AcFormats[i] = GWT_FORMAT})

Invariants ==
    ValidPhase
    /\ OutputReqsShape
    /\ OutputGWTsShape
    /\ CriterionIdPrefixOK
    /\ NameConditional
    /\ NoOutputOnError
    /\ SuccessImpliesValidSession
    /\ ErrorOnZeroSessions
    /\ ErrorOnMultiSessions
    /\ OnlyGWTFormatIncluded


vars == << pc, phase, resolved_session, req_index, ac_index, output_reqs, 
           output_gwts, raised_error >>

ProcSet == {"extract"}

Init == (* Global variables *)
        /\ phase = "start"
        /\ resolved_session = 0
        /\ req_index = 1
        /\ ac_index = 1
        /\ output_reqs = <<>>
        /\ output_gwts = <<>>
        /\ raised_error = ""
        /\ pc = [self \in ProcSet |-> "Resolve"]

Resolve == /\ pc["extract"] = "Resolve"
           /\ IF SessionIdProvided
                 THEN /\ resolved_session' = 1
                      /\ phase' = "query_reqs"
                      /\ pc' = [pc EXCEPT !["extract"] = "QueryReqs"]
                      /\ UNCHANGED raised_error
                 ELSE /\ IF SessionCount = 0
                            THEN /\ phase' = "err_no_session"
                                 /\ raised_error' = "ValueError: no sessions found"
                                 /\ pc' = [pc EXCEPT !["extract"] = "Terminate"]
                                 /\ UNCHANGED resolved_session
                            ELSE /\ IF SessionCount = 2
                                       THEN /\ phase' = "err_multi_session"
                                            /\ raised_error' = "ValueError: multiple sessions, specify session_id"
                                            /\ pc' = [pc EXCEPT !["extract"] = "Terminate"]
                                            /\ UNCHANGED resolved_session
                                       ELSE /\ resolved_session' = 1
                                            /\ phase' = "query_reqs"
                                            /\ pc' = [pc EXCEPT !["extract"] = "QueryReqs"]
                                            /\ UNCHANGED raised_error
           /\ UNCHANGED << req_index, ac_index, output_reqs, output_gwts >>

QueryReqs == /\ pc["extract"] = "QueryReqs"
             /\ req_index' = 1
             /\ output_reqs' = <<>>
             /\ pc' = [pc EXCEPT !["extract"] = "ReqLoop"]
             /\ UNCHANGED << phase, resolved_session, ac_index, output_gwts, 
                             raised_error >>

ReqLoop == /\ pc["extract"] = "ReqLoop"
           /\ IF req_index <= NumReqs
                 THEN /\ pc' = [pc EXCEPT !["extract"] = "ReqStep"]
                 ELSE /\ pc' = [pc EXCEPT !["extract"] = "StartGWT"]
           /\ UNCHANGED << phase, resolved_session, req_index, ac_index, 
                           output_reqs, output_gwts, raised_error >>

ReqStep == /\ pc["extract"] = "ReqStep"
           /\ output_reqs' =            Append(output_reqs,
                             [id |-> req_index, text |-> req_index])
           /\ req_index' = req_index + 1
           /\ pc' = [pc EXCEPT !["extract"] = "ReqLoop"]
           /\ UNCHANGED << phase, resolved_session, ac_index, output_gwts, 
                           raised_error >>

StartGWT == /\ pc["extract"] = "StartGWT"
            /\ ac_index' = 1
            /\ output_gwts' = <<>>
            /\ phase' = "query_gwts"
            /\ pc' = [pc EXCEPT !["extract"] = "GWTLoop"]
            /\ UNCHANGED << resolved_session, req_index, output_reqs, 
                            raised_error >>

GWTLoop == /\ pc["extract"] = "GWTLoop"
           /\ IF ac_index <= NumAcRows
                 THEN /\ pc' = [pc EXCEPT !["extract"] = "GWTCheck"]
                 ELSE /\ pc' = [pc EXCEPT !["extract"] = "Complete"]
           /\ UNCHANGED << phase, resolved_session, req_index, ac_index, 
                           output_reqs, output_gwts, raised_error >>

GWTCheck == /\ pc["extract"] = "GWTCheck"
            /\ IF AcFormats[ac_index] = GWT_FORMAT
                  THEN /\ IF WhenEmpty[ac_index]
                             THEN /\ output_gwts' =            Append(output_gwts,
                                                    [criterion_id  |-> [prefix |-> CW7_PREFIX,
                                                                        num    |-> ac_index],
                                                     given_c        |-> "",
                                                     when_c         |-> "",
                                                     then_c         |-> "",
                                                     parent_req     |-> resolved_session,
                                                     when_was_empty |-> TRUE])
                             ELSE /\ output_gwts' =            Append(output_gwts,
                                                    [criterion_id  |-> [prefix |-> CW7_PREFIX,
                                                                        num    |-> ac_index],
                                                     given_c        |-> "",
                                                     when_c         |-> "nonempty",
                                                     then_c         |-> "",
                                                     parent_req     |-> resolved_session,
                                                     when_was_empty |-> FALSE,
                                                     name           |-> "slug"])
                  ELSE /\ TRUE
                       /\ UNCHANGED output_gwts
            /\ pc' = [pc EXCEPT !["extract"] = "GWTIncr"]
            /\ UNCHANGED << phase, resolved_session, req_index, ac_index, 
                            output_reqs, raised_error >>

GWTIncr == /\ pc["extract"] = "GWTIncr"
           /\ ac_index' = ac_index + 1
           /\ pc' = [pc EXCEPT !["extract"] = "GWTLoop"]
           /\ UNCHANGED << phase, resolved_session, req_index, output_reqs, 
                           output_gwts, raised_error >>

Complete == /\ pc["extract"] = "Complete"
            /\ phase' = "complete"
            /\ pc' = [pc EXCEPT !["extract"] = "Terminate"]
            /\ UNCHANGED << resolved_session, req_index, ac_index, output_reqs, 
                            output_gwts, raised_error >>

Terminate == /\ pc["extract"] = "Terminate"
             /\ TRUE
             /\ pc' = [pc EXCEPT !["extract"] = "Done"]
             /\ UNCHANGED << phase, resolved_session, req_index, ac_index, 
                             output_reqs, output_gwts, raised_error >>

extract == Resolve \/ QueryReqs \/ ReqLoop \/ ReqStep \/ StartGWT
              \/ GWTLoop \/ GWTCheck \/ GWTIncr \/ Complete \/ Terminate

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == extract
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(extract)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
