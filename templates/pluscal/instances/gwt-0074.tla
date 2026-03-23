---- MODULE JSTSEntryPointDiscovery ----

EXTENDS Integers, FiniteSets, TLC

NODE_MODULES_PATHS == {"node_modules/express/index.js"}
MIN_JS_PATHS       == {"dist/bundle.min.js"}
DTS_PATHS          == {"src/types.d.ts"}
ALL_EXCLUDED       == NODE_MODULES_PATHS \union MIN_JS_PATHS \union DTS_PATHS

IsExcluded(fp) == fp \in ALL_EXCLUDED

HTTP_METHODS   == {"GET", "POST", "PUT", "DELETE", "PATCH"}
CODEBASE_TYPES == {"web_app", "cli", "library", "event_driven"}

SKELETONS == {
    [file_path |-> "src/index.js",
     function_name |-> "createApp",
     visibility |-> "public",
     has_class |-> FALSE],
    [file_path |-> "src/app.js",
     function_name |-> "internalHelper",
     visibility |-> "private",
     has_class |-> FALSE],
    [file_path |-> "src/cli.js",
     function_name |-> "runCli",
     visibility |-> "public",
     has_class |-> FALSE],
    [file_path |-> "node_modules/express/index.js",
     function_name |-> "nmHandler",
     visibility |-> "public",
     has_class |-> FALSE],
    [file_path |-> "dist/bundle.min.js",
     function_name |-> "minFunc",
     visibility |-> "public",
     has_class |-> FALSE],
    [file_path |-> "src/types.d.ts",
     function_name |-> "MyType",
     visibility |-> "public",
     has_class |-> FALSE]
}

PublicTopLevelSkeletons ==
    {s \in SKELETONS :
        s.visibility = "public" /\
        ~s.has_class /\
        ~IsExcluded(s.file_path)}

(* --algorithm JSTSEntryPointDiscovery

variables
    codebase_type   \in CODEBASE_TYPES,
    has_pkg_json    \in BOOLEAN,
    pkg_json_valid  \in BOOLEAN,
    has_http_routes \in BOOLEAN,
    has_cli_cmds    \in BOOLEAN,
    entry_points    = {},
    phase           = "init";

define

    VALID_PHASES == {"init", "parse_manifest", "scan_routes", "scan_cli",
                     "collect_api", "deduplicate", "fallback", "complete"}

    ValidPhase == phase \in VALID_PHASES

    NodeModulesExcluded ==
        \A ep \in entry_points : ep.file_path \notin NODE_MODULES_PATHS

    MinJsExcluded ==
        \A ep \in entry_points : ep.file_path \notin MIN_JS_PATHS

    DtsProducesNoEntries ==
        \A ep \in entry_points : ep.file_path \notin DTS_PATHS

    RouteMethodUppercase ==
        \A ep \in entry_points :
            ep.entry_type = "HTTP_ROUTE" => ep.method \in HTTP_METHODS

    DeduplicatedResults ==
        \A ep1 \in entry_points :
        \A ep2 \in entry_points :
            (ep1.file_path = ep2.file_path /\
             ep1.function_name = ep2.function_name)
            => ep1 = ep2

    AllEntryTypesValid ==
        \A ep \in entry_points :
            ep.entry_type \in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}

    LibraryPublicApiAtCompletion ==
        (phase = "complete" /\ codebase_type = "library")
        =>
        \A s \in PublicTopLevelSkeletons :
            \E ep \in entry_points :
                ep.file_path     = s.file_path     /\
                ep.function_name = s.function_name /\
                ep.entry_type    = "PUBLIC_API"

    PkgJsonCliOnlyWhenPresent ==
        \A ep \in entry_points :
            (ep.entry_type = "CLI_COMMAND" /\ ep.function_name = "mycli")
            => (has_pkg_json /\ pkg_json_valid)

    FallbackOnlyWhenNoEntries ==
        (phase = "complete" /\
         ~has_http_routes /\
         ~has_cli_cmds /\
         ~(has_pkg_json /\ pkg_json_valid) /\
         codebase_type # "library")
        =>
        \A s \in PublicTopLevelSkeletons :
            \E ep \in entry_points :
                ep.file_path     = s.file_path     /\
                ep.function_name = s.function_name /\
                ep.entry_type    = "PUBLIC_API"

    AllInvariantsHold ==
        /\ ValidPhase
        /\ NodeModulesExcluded
        /\ MinJsExcluded
        /\ DtsProducesNoEntries
        /\ RouteMethodUppercase
        /\ DeduplicatedResults
        /\ AllEntryTypesValid
        /\ LibraryPublicApiAtCompletion
        /\ PkgJsonCliOnlyWhenPresent
        /\ FallbackOnlyWhenNoEntries

end define;

fair process discoverer = "discoverer"
begin
    ParseManifest:
        phase := "parse_manifest";
        if has_pkg_json /\ pkg_json_valid then
            entry_points := entry_points \union {
                [file_path     |-> "src/cli.js",
                 function_name |-> "mycli",
                 entry_type    |-> "CLI_COMMAND",
                 route         |-> "none",
                 method        |-> "none"]
            };
        end if;

    ScanRoutes:
        phase := "scan_routes";
        if has_http_routes then
            entry_points := entry_points \union {
                [file_path     |-> "src/app.js",
                 function_name |-> "getUsers",
                 entry_type    |-> "HTTP_ROUTE",
                 route         |-> "/users",
                 method        |-> "GET"],
                [file_path     |-> "src/app.js",
                 function_name |-> "createUser",
                 entry_type    |-> "HTTP_ROUTE",
                 route         |-> "/users",
                 method        |-> "POST"]
            };
        end if;

    ScanCLI:
        phase := "scan_cli";
        if has_cli_cmds then
            entry_points := entry_points \union {
                [file_path     |-> "src/cli.js",
                 function_name |-> "build",
                 entry_type    |-> "CLI_COMMAND",
                 route         |-> "none",
                 method        |-> "none"]
            };
        end if;

    CollectPublicAPI:
        phase := "collect_api";
        if codebase_type = "library" then
            entry_points := entry_points \union
                {[file_path     |-> s.file_path,
                  function_name |-> s.function_name,
                  entry_type    |-> "PUBLIC_API",
                  route         |-> "none",
                  method        |-> "none"] : s \in PublicTopLevelSkeletons};
        end if;

    Deduplicate:
        phase := "deduplicate";
        skip;

    Fallback:
        phase := "fallback";
        if entry_points = {} /\ codebase_type # "library" then
            entry_points :=
                {[file_path     |-> s.file_path,
                  function_name |-> s.function_name,
                  entry_type    |-> "PUBLIC_API",
                  route         |-> "none",
                  method        |-> "none"] : s \in PublicTopLevelSkeletons};
        end if;

    Complete:
        phase := "complete";
        skip;

end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "e7fea16e" /\ chksum(tla) = "17ecfe7")
VARIABLES pc, codebase_type, has_pkg_json, pkg_json_valid, has_http_routes, 
          has_cli_cmds, entry_points, phase

(* define statement *)
VALID_PHASES == {"init", "parse_manifest", "scan_routes", "scan_cli",
                 "collect_api", "deduplicate", "fallback", "complete"}

ValidPhase == phase \in VALID_PHASES

NodeModulesExcluded ==
    \A ep \in entry_points : ep.file_path \notin NODE_MODULES_PATHS

MinJsExcluded ==
    \A ep \in entry_points : ep.file_path \notin MIN_JS_PATHS

DtsProducesNoEntries ==
    \A ep \in entry_points : ep.file_path \notin DTS_PATHS

RouteMethodUppercase ==
    \A ep \in entry_points :
        ep.entry_type = "HTTP_ROUTE" => ep.method \in HTTP_METHODS

DeduplicatedResults ==
    \A ep1 \in entry_points :
    \A ep2 \in entry_points :
        (ep1.file_path = ep2.file_path /\
         ep1.function_name = ep2.function_name)
        => ep1 = ep2

AllEntryTypesValid ==
    \A ep \in entry_points :
        ep.entry_type \in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}

LibraryPublicApiAtCompletion ==
    (phase = "complete" /\ codebase_type = "library")
    =>
    \A s \in PublicTopLevelSkeletons :
        \E ep \in entry_points :
            ep.file_path     = s.file_path     /\
            ep.function_name = s.function_name /\
            ep.entry_type    = "PUBLIC_API"

PkgJsonCliOnlyWhenPresent ==
    \A ep \in entry_points :
        (ep.entry_type = "CLI_COMMAND" /\ ep.function_name = "mycli")
        => (has_pkg_json /\ pkg_json_valid)

FallbackOnlyWhenNoEntries ==
    (phase = "complete" /\
     ~has_http_routes /\
     ~has_cli_cmds /\
     ~(has_pkg_json /\ pkg_json_valid) /\
     codebase_type # "library")
    =>
    \A s \in PublicTopLevelSkeletons :
        \E ep \in entry_points :
            ep.file_path     = s.file_path     /\
            ep.function_name = s.function_name /\
            ep.entry_type    = "PUBLIC_API"

AllInvariantsHold ==
    /\ ValidPhase
    /\ NodeModulesExcluded
    /\ MinJsExcluded
    /\ DtsProducesNoEntries
    /\ RouteMethodUppercase
    /\ DeduplicatedResults
    /\ AllEntryTypesValid
    /\ LibraryPublicApiAtCompletion
    /\ PkgJsonCliOnlyWhenPresent
    /\ FallbackOnlyWhenNoEntries


vars == << pc, codebase_type, has_pkg_json, pkg_json_valid, has_http_routes, 
           has_cli_cmds, entry_points, phase >>

ProcSet == {"discoverer"}

Init == (* Global variables *)
        /\ codebase_type \in CODEBASE_TYPES
        /\ has_pkg_json \in BOOLEAN
        /\ pkg_json_valid \in BOOLEAN
        /\ has_http_routes \in BOOLEAN
        /\ has_cli_cmds \in BOOLEAN
        /\ entry_points = {}
        /\ phase = "init"
        /\ pc = [self \in ProcSet |-> "ParseManifest"]

ParseManifest == /\ pc["discoverer"] = "ParseManifest"
                 /\ phase' = "parse_manifest"
                 /\ IF has_pkg_json /\ pkg_json_valid
                       THEN /\ entry_points' = (                entry_points \union {
                                                    [file_path     |-> "src/cli.js",
                                                     function_name |-> "mycli",
                                                     entry_type    |-> "CLI_COMMAND",
                                                     route         |-> "none",
                                                     method        |-> "none"]
                                                })
                       ELSE /\ TRUE
                            /\ UNCHANGED entry_points
                 /\ pc' = [pc EXCEPT !["discoverer"] = "ScanRoutes"]
                 /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                                 has_http_routes, has_cli_cmds >>

ScanRoutes == /\ pc["discoverer"] = "ScanRoutes"
              /\ phase' = "scan_routes"
              /\ IF has_http_routes
                    THEN /\ entry_points' = (                entry_points \union {
                                                 [file_path     |-> "src/app.js",
                                                  function_name |-> "getUsers",
                                                  entry_type    |-> "HTTP_ROUTE",
                                                  route         |-> "/users",
                                                  method        |-> "GET"],
                                                 [file_path     |-> "src/app.js",
                                                  function_name |-> "createUser",
                                                  entry_type    |-> "HTTP_ROUTE",
                                                  route         |-> "/users",
                                                  method        |-> "POST"]
                                             })
                    ELSE /\ TRUE
                         /\ UNCHANGED entry_points
              /\ pc' = [pc EXCEPT !["discoverer"] = "ScanCLI"]
              /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                              has_http_routes, has_cli_cmds >>

ScanCLI == /\ pc["discoverer"] = "ScanCLI"
           /\ phase' = "scan_cli"
           /\ IF has_cli_cmds
                 THEN /\ entry_points' = (                entry_points \union {
                                              [file_path     |-> "src/cli.js",
                                               function_name |-> "build",
                                               entry_type    |-> "CLI_COMMAND",
                                               route         |-> "none",
                                               method        |-> "none"]
                                          })
                 ELSE /\ TRUE
                      /\ UNCHANGED entry_points
           /\ pc' = [pc EXCEPT !["discoverer"] = "CollectPublicAPI"]
           /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                           has_http_routes, has_cli_cmds >>

CollectPublicAPI == /\ pc["discoverer"] = "CollectPublicAPI"
                    /\ phase' = "collect_api"
                    /\ IF codebase_type = "library"
                          THEN /\ entry_points' = (            entry_points \union
                                                   {[file_path     |-> s.file_path,
                                                     function_name |-> s.function_name,
                                                     entry_type    |-> "PUBLIC_API",
                                                     route         |-> "none",
                                                     method        |-> "none"] : s \in PublicTopLevelSkeletons})
                          ELSE /\ TRUE
                               /\ UNCHANGED entry_points
                    /\ pc' = [pc EXCEPT !["discoverer"] = "Deduplicate"]
                    /\ UNCHANGED << codebase_type, has_pkg_json, 
                                    pkg_json_valid, has_http_routes, 
                                    has_cli_cmds >>

Deduplicate == /\ pc["discoverer"] = "Deduplicate"
               /\ phase' = "deduplicate"
               /\ TRUE
               /\ pc' = [pc EXCEPT !["discoverer"] = "Fallback"]
               /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                               has_http_routes, has_cli_cmds, entry_points >>

Fallback == /\ pc["discoverer"] = "Fallback"
            /\ phase' = "fallback"
            /\ IF entry_points = {} /\ codebase_type # "library"
                  THEN /\ entry_points' = {[file_path     |-> s.file_path,
                                            function_name |-> s.function_name,
                                            entry_type    |-> "PUBLIC_API",
                                            route         |-> "none",
                                            method        |-> "none"] : s \in PublicTopLevelSkeletons}
                  ELSE /\ TRUE
                       /\ UNCHANGED entry_points
            /\ pc' = [pc EXCEPT !["discoverer"] = "Complete"]
            /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                            has_http_routes, has_cli_cmds >>

Complete == /\ pc["discoverer"] = "Complete"
            /\ phase' = "complete"
            /\ TRUE
            /\ pc' = [pc EXCEPT !["discoverer"] = "Done"]
            /\ UNCHANGED << codebase_type, has_pkg_json, pkg_json_valid, 
                            has_http_routes, has_cli_cmds, entry_points >>

discoverer == ParseManifest \/ ScanRoutes \/ ScanCLI \/ CollectPublicAPI
                 \/ Deduplicate \/ Fallback \/ Complete

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
