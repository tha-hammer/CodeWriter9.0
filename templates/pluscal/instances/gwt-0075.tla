---- MODULE GoEntryPointDiscovery ----

EXTENDS Integers, FiniteSets, TLC

NumSkeletons == 2
NumSourceFiles == 2

(* --algorithm GoEntryPointDiscovery

variables
    codebase_type \in {"web_app", "cli", "library"},
    entry_points = {},
    skel_idx = 1,
    file_idx = 1,
    sk_is_main = FALSE,
    sk_is_public = FALSE,
    sk_has_receiver = FALSE,
    sk_is_test_file = FALSE,
    f_is_test = FALSE,
    f_has_gin_route = FALSE,
    f_has_http_handle = FALSE,
    f_has_cobra = FALSE;

define

    ValidEntryTypes ==
        \A ep \in entry_points :
            ep.entry_type \in {"MAIN", "PUBLIC_API", "HTTP_ROUTE", "CLI_COMMAND"}

    MainHasCorrectName ==
        \A ep \in entry_points :
            ep.entry_type = "MAIN" => ep.function_name = "main"

    MainNeverPublicApi ==
        \A ep \in entry_points :
            ep.function_name = "main" => ep.entry_type /= "PUBLIC_API"

    PublicOnlyForLibrary ==
        \A ep \in entry_points :
            ep.entry_type = "PUBLIC_API" => codebase_type = "library"

    HttpRouteHasRoute ==
        \A ep \in entry_points :
            ep.entry_type = "HTTP_ROUTE" => ep.route /= "none"

    HandleFuncMethodAgnostic ==
        \A ep \in entry_points :
            (ep.entry_type = "HTTP_ROUTE" /\ ep.route_type = "handlefunc") =>
            ep.method = "none"

    GinRouteHasMethod ==
        \A ep \in entry_points :
            ep.route_type = "gin" => ep.method /= "none"

    NoDuplicates ==
        \A ep1 \in entry_points : \A ep2 \in entry_points :
            (ep1.file_path = ep2.file_path /\
             ep1.function_name = ep2.function_name) =>
            ep1 = ep2

    MethodsNeverPublicApi ==
        \A ep \in entry_points :
            ep.entry_type = "PUBLIC_API" => ep.has_receiver = FALSE

end define;

fair process discoverer = "discoverer"
begin
    ProcessSkeletons:
        while skel_idx <= NumSkeletons do
            ChooseIsMain:
                either
                    sk_is_main := TRUE;
                or
                    sk_is_main := FALSE;
                end either;
            ChooseIsPublic:
                either
                    sk_is_public := TRUE;
                or
                    sk_is_public := FALSE;
                end either;
            ChooseHasReceiver:
                either
                    sk_has_receiver := TRUE;
                or
                    sk_has_receiver := FALSE;
                end either;
            ChooseIsTestFileSkel:
                either
                    sk_is_test_file := TRUE;
                or
                    sk_is_test_file := FALSE;
                end either;
            ClassifySkel:
                if sk_is_test_file then
                    skip;
                elsif sk_is_main /\ ~sk_has_receiver then
                    entry_points := entry_points \union
                        {[file_path     |-> skel_idx,
                          function_name |-> "main",
                          entry_type    |-> "MAIN",
                          route         |-> "none",
                          method        |-> "none",
                          route_type    |-> "none",
                          has_receiver  |-> FALSE]};
                elsif sk_is_public /\ ~sk_has_receiver /\ ~sk_is_main /\
                      codebase_type = "library" then
                    entry_points := entry_points \union
                        {[file_path     |-> skel_idx,
                          function_name |-> "ExportedFunc",
                          entry_type    |-> "PUBLIC_API",
                          route         |-> "none",
                          method        |-> "none",
                          route_type    |-> "none",
                          has_receiver  |-> FALSE]};
                end if;
                skel_idx := skel_idx + 1;
        end while;
    ScanFiles:
        while file_idx <= NumSourceFiles do
            ChooseIsTestFileF:
                either
                    f_is_test := TRUE;
                or
                    f_is_test := FALSE;
                end either;
            ChooseGinRoute:
                either
                    f_has_gin_route := TRUE;
                or
                    f_has_gin_route := FALSE;
                end either;
            ChooseHttpHandle:
                either
                    f_has_http_handle := TRUE;
                or
                    f_has_http_handle := FALSE;
                end either;
            ChooseCobra:
                either
                    f_has_cobra := TRUE;
                or
                    f_has_cobra := FALSE;
                end either;
            ProcessGinRoute:
                if ~f_is_test /\ f_has_gin_route then
                    entry_points := entry_points \union
                        {[file_path     |-> NumSkeletons + file_idx,
                          function_name |-> "ginRouteHandler",
                          entry_type    |-> "HTTP_ROUTE",
                          route         |-> "/api",
                          method        |-> "GET",
                          route_type    |-> "gin",
                          has_receiver  |-> FALSE]};
                end if;
            ProcessHttpHandle:
                if ~f_is_test /\ f_has_http_handle then
                    entry_points := entry_points \union
                        {[file_path     |-> NumSkeletons + file_idx,
                          function_name |-> "httpHandleFunc",
                          entry_type    |-> "HTTP_ROUTE",
                          route         |-> "/health",
                          method        |-> "none",
                          route_type    |-> "handlefunc",
                          has_receiver  |-> FALSE]};
                end if;
            ProcessCobraCmd:
                if ~f_is_test /\ f_has_cobra then
                    entry_points := entry_points \union
                        {[file_path     |-> NumSkeletons + file_idx,
                          function_name |-> "cobraCommand",
                          entry_type    |-> "CLI_COMMAND",
                          route         |-> "none",
                          method        |-> "none",
                          route_type    |-> "none",
                          has_receiver  |-> FALSE]};
                end if;
                file_idx := file_idx + 1;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "38cd1f8c" /\ chksum(tla) = "ff801279")
VARIABLES pc, codebase_type, entry_points, skel_idx, file_idx, sk_is_main, 
          sk_is_public, sk_has_receiver, sk_is_test_file, f_is_test, 
          f_has_gin_route, f_has_http_handle, f_has_cobra

(* define statement *)
ValidEntryTypes ==
    \A ep \in entry_points :
        ep.entry_type \in {"MAIN", "PUBLIC_API", "HTTP_ROUTE", "CLI_COMMAND"}

MainHasCorrectName ==
    \A ep \in entry_points :
        ep.entry_type = "MAIN" => ep.function_name = "main"

MainNeverPublicApi ==
    \A ep \in entry_points :
        ep.function_name = "main" => ep.entry_type /= "PUBLIC_API"

PublicOnlyForLibrary ==
    \A ep \in entry_points :
        ep.entry_type = "PUBLIC_API" => codebase_type = "library"

HttpRouteHasRoute ==
    \A ep \in entry_points :
        ep.entry_type = "HTTP_ROUTE" => ep.route /= "none"

HandleFuncMethodAgnostic ==
    \A ep \in entry_points :
        (ep.entry_type = "HTTP_ROUTE" /\ ep.route_type = "handlefunc") =>
        ep.method = "none"

GinRouteHasMethod ==
    \A ep \in entry_points :
        ep.route_type = "gin" => ep.method /= "none"

NoDuplicates ==
    \A ep1 \in entry_points : \A ep2 \in entry_points :
        (ep1.file_path = ep2.file_path /\
         ep1.function_name = ep2.function_name) =>
        ep1 = ep2

MethodsNeverPublicApi ==
    \A ep \in entry_points :
        ep.entry_type = "PUBLIC_API" => ep.has_receiver = FALSE


vars == << pc, codebase_type, entry_points, skel_idx, file_idx, sk_is_main, 
           sk_is_public, sk_has_receiver, sk_is_test_file, f_is_test, 
           f_has_gin_route, f_has_http_handle, f_has_cobra >>

ProcSet == {"discoverer"}

Init == (* Global variables *)
        /\ codebase_type \in {"web_app", "cli", "library"}
        /\ entry_points = {}
        /\ skel_idx = 1
        /\ file_idx = 1
        /\ sk_is_main = FALSE
        /\ sk_is_public = FALSE
        /\ sk_has_receiver = FALSE
        /\ sk_is_test_file = FALSE
        /\ f_is_test = FALSE
        /\ f_has_gin_route = FALSE
        /\ f_has_http_handle = FALSE
        /\ f_has_cobra = FALSE
        /\ pc = [self \in ProcSet |-> "ProcessSkeletons"]

ProcessSkeletons == /\ pc["discoverer"] = "ProcessSkeletons"
                    /\ IF skel_idx <= NumSkeletons
                          THEN /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseIsMain"]
                          ELSE /\ pc' = [pc EXCEPT !["discoverer"] = "ScanFiles"]
                    /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                    file_idx, sk_is_main, sk_is_public, 
                                    sk_has_receiver, sk_is_test_file, 
                                    f_is_test, f_has_gin_route, 
                                    f_has_http_handle, f_has_cobra >>

ChooseIsMain == /\ pc["discoverer"] = "ChooseIsMain"
                /\ \/ /\ sk_is_main' = TRUE
                   \/ /\ sk_is_main' = FALSE
                /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseIsPublic"]
                /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                file_idx, sk_is_public, sk_has_receiver, 
                                sk_is_test_file, f_is_test, f_has_gin_route, 
                                f_has_http_handle, f_has_cobra >>

ChooseIsPublic == /\ pc["discoverer"] = "ChooseIsPublic"
                  /\ \/ /\ sk_is_public' = TRUE
                     \/ /\ sk_is_public' = FALSE
                  /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseHasReceiver"]
                  /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                  file_idx, sk_is_main, sk_has_receiver, 
                                  sk_is_test_file, f_is_test, f_has_gin_route, 
                                  f_has_http_handle, f_has_cobra >>

ChooseHasReceiver == /\ pc["discoverer"] = "ChooseHasReceiver"
                     /\ \/ /\ sk_has_receiver' = TRUE
                        \/ /\ sk_has_receiver' = FALSE
                     /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseIsTestFileSkel"]
                     /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                     file_idx, sk_is_main, sk_is_public, 
                                     sk_is_test_file, f_is_test, 
                                     f_has_gin_route, f_has_http_handle, 
                                     f_has_cobra >>

ChooseIsTestFileSkel == /\ pc["discoverer"] = "ChooseIsTestFileSkel"
                        /\ \/ /\ sk_is_test_file' = TRUE
                           \/ /\ sk_is_test_file' = FALSE
                        /\ pc' = [pc EXCEPT !["discoverer"] = "ClassifySkel"]
                        /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                        file_idx, sk_is_main, sk_is_public, 
                                        sk_has_receiver, f_is_test, 
                                        f_has_gin_route, f_has_http_handle, 
                                        f_has_cobra >>

ClassifySkel == /\ pc["discoverer"] = "ClassifySkel"
                /\ IF sk_is_test_file
                      THEN /\ TRUE
                           /\ UNCHANGED entry_points
                      ELSE /\ IF sk_is_main /\ ~sk_has_receiver
                                 THEN /\ entry_points' = (            entry_points \union
                                                          {[file_path     |-> skel_idx,
                                                            function_name |-> "main",
                                                            entry_type    |-> "MAIN",
                                                            route         |-> "none",
                                                            method        |-> "none",
                                                            route_type    |-> "none",
                                                            has_receiver  |-> FALSE]})
                                 ELSE /\ IF sk_is_public /\ ~sk_has_receiver /\ ~sk_is_main /\
                                            codebase_type = "library"
                                            THEN /\ entry_points' = (            entry_points \union
                                                                     {[file_path     |-> skel_idx,
                                                                       function_name |-> "ExportedFunc",
                                                                       entry_type    |-> "PUBLIC_API",
                                                                       route         |-> "none",
                                                                       method        |-> "none",
                                                                       route_type    |-> "none",
                                                                       has_receiver  |-> FALSE]})
                                            ELSE /\ TRUE
                                                 /\ UNCHANGED entry_points
                /\ skel_idx' = skel_idx + 1
                /\ pc' = [pc EXCEPT !["discoverer"] = "ProcessSkeletons"]
                /\ UNCHANGED << codebase_type, file_idx, sk_is_main, 
                                sk_is_public, sk_has_receiver, sk_is_test_file, 
                                f_is_test, f_has_gin_route, f_has_http_handle, 
                                f_has_cobra >>

ScanFiles == /\ pc["discoverer"] = "ScanFiles"
             /\ IF file_idx <= NumSourceFiles
                   THEN /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseIsTestFileF"]
                   ELSE /\ pc' = [pc EXCEPT !["discoverer"] = "Finish"]
             /\ UNCHANGED << codebase_type, entry_points, skel_idx, file_idx, 
                             sk_is_main, sk_is_public, sk_has_receiver, 
                             sk_is_test_file, f_is_test, f_has_gin_route, 
                             f_has_http_handle, f_has_cobra >>

ChooseIsTestFileF == /\ pc["discoverer"] = "ChooseIsTestFileF"
                     /\ \/ /\ f_is_test' = TRUE
                        \/ /\ f_is_test' = FALSE
                     /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseGinRoute"]
                     /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                     file_idx, sk_is_main, sk_is_public, 
                                     sk_has_receiver, sk_is_test_file, 
                                     f_has_gin_route, f_has_http_handle, 
                                     f_has_cobra >>

ChooseGinRoute == /\ pc["discoverer"] = "ChooseGinRoute"
                  /\ \/ /\ f_has_gin_route' = TRUE
                     \/ /\ f_has_gin_route' = FALSE
                  /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseHttpHandle"]
                  /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                  file_idx, sk_is_main, sk_is_public, 
                                  sk_has_receiver, sk_is_test_file, f_is_test, 
                                  f_has_http_handle, f_has_cobra >>

ChooseHttpHandle == /\ pc["discoverer"] = "ChooseHttpHandle"
                    /\ \/ /\ f_has_http_handle' = TRUE
                       \/ /\ f_has_http_handle' = FALSE
                    /\ pc' = [pc EXCEPT !["discoverer"] = "ChooseCobra"]
                    /\ UNCHANGED << codebase_type, entry_points, skel_idx, 
                                    file_idx, sk_is_main, sk_is_public, 
                                    sk_has_receiver, sk_is_test_file, 
                                    f_is_test, f_has_gin_route, f_has_cobra >>

ChooseCobra == /\ pc["discoverer"] = "ChooseCobra"
               /\ \/ /\ f_has_cobra' = TRUE
                  \/ /\ f_has_cobra' = FALSE
               /\ pc' = [pc EXCEPT !["discoverer"] = "ProcessGinRoute"]
               /\ UNCHANGED << codebase_type, entry_points, skel_idx, file_idx, 
                               sk_is_main, sk_is_public, sk_has_receiver, 
                               sk_is_test_file, f_is_test, f_has_gin_route, 
                               f_has_http_handle >>

ProcessGinRoute == /\ pc["discoverer"] = "ProcessGinRoute"
                   /\ IF ~f_is_test /\ f_has_gin_route
                         THEN /\ entry_points' = (            entry_points \union
                                                  {[file_path     |-> NumSkeletons + file_idx,
                                                    function_name |-> "ginRouteHandler",
                                                    entry_type    |-> "HTTP_ROUTE",
                                                    route         |-> "/api",
                                                    method        |-> "GET",
                                                    route_type    |-> "gin",
                                                    has_receiver  |-> FALSE]})
                         ELSE /\ TRUE
                              /\ UNCHANGED entry_points
                   /\ pc' = [pc EXCEPT !["discoverer"] = "ProcessHttpHandle"]
                   /\ UNCHANGED << codebase_type, skel_idx, file_idx, 
                                   sk_is_main, sk_is_public, sk_has_receiver, 
                                   sk_is_test_file, f_is_test, f_has_gin_route, 
                                   f_has_http_handle, f_has_cobra >>

ProcessHttpHandle == /\ pc["discoverer"] = "ProcessHttpHandle"
                     /\ IF ~f_is_test /\ f_has_http_handle
                           THEN /\ entry_points' = (            entry_points \union
                                                    {[file_path     |-> NumSkeletons + file_idx,
                                                      function_name |-> "httpHandleFunc",
                                                      entry_type    |-> "HTTP_ROUTE",
                                                      route         |-> "/health",
                                                      method        |-> "none",
                                                      route_type    |-> "handlefunc",
                                                      has_receiver  |-> FALSE]})
                           ELSE /\ TRUE
                                /\ UNCHANGED entry_points
                     /\ pc' = [pc EXCEPT !["discoverer"] = "ProcessCobraCmd"]
                     /\ UNCHANGED << codebase_type, skel_idx, file_idx, 
                                     sk_is_main, sk_is_public, sk_has_receiver, 
                                     sk_is_test_file, f_is_test, 
                                     f_has_gin_route, f_has_http_handle, 
                                     f_has_cobra >>

ProcessCobraCmd == /\ pc["discoverer"] = "ProcessCobraCmd"
                   /\ IF ~f_is_test /\ f_has_cobra
                         THEN /\ entry_points' = (            entry_points \union
                                                  {[file_path     |-> NumSkeletons + file_idx,
                                                    function_name |-> "cobraCommand",
                                                    entry_type    |-> "CLI_COMMAND",
                                                    route         |-> "none",
                                                    method        |-> "none",
                                                    route_type    |-> "none",
                                                    has_receiver  |-> FALSE]})
                         ELSE /\ TRUE
                              /\ UNCHANGED entry_points
                   /\ file_idx' = file_idx + 1
                   /\ pc' = [pc EXCEPT !["discoverer"] = "ScanFiles"]
                   /\ UNCHANGED << codebase_type, skel_idx, sk_is_main, 
                                   sk_is_public, sk_has_receiver, 
                                   sk_is_test_file, f_is_test, f_has_gin_route, 
                                   f_has_http_handle, f_has_cobra >>

Finish == /\ pc["discoverer"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["discoverer"] = "Done"]
          /\ UNCHANGED << codebase_type, entry_points, skel_idx, file_idx, 
                          sk_is_main, sk_is_public, sk_has_receiver, 
                          sk_is_test_file, f_is_test, f_has_gin_route, 
                          f_has_http_handle, f_has_cobra >>

discoverer == ProcessSkeletons \/ ChooseIsMain \/ ChooseIsPublic
                 \/ ChooseHasReceiver \/ ChooseIsTestFileSkel
                 \/ ClassifySkel \/ ScanFiles \/ ChooseIsTestFileF
                 \/ ChooseGinRoute \/ ChooseHttpHandle \/ ChooseCobra
                 \/ ProcessGinRoute \/ ProcessHttpHandle \/ ProcessCobraCmd
                 \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == discoverer
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(discoverer)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
