---- MODULE RustDiscovery ----

EXTENDS Integers, FiniteSets, TLC

(* --algorithm RustDiscovery

variables
  codebase_type     \in {"web_app", "cli", "library"},
  skel_is_main      \in BOOLEAN,
  skel_is_public    \in BOOLEAN,
  skel_has_class    \in BOOLEAN,
  skel_dotfile      \in BOOLEAN,
  file_dotfile      \in BOOLEAN,
  file_has_actix    \in BOOLEAN,
  file_actix_method \in {"GET", "POST"},
  file_has_axum     \in BOOLEAN,
  file_axum_method  \in {"GET", "POST"},
  file_has_clap     \in BOOLEAN,
  entry_points = {};

define

  MainIsTopLevel ==
    \A ep \in entry_points :
      ep.etype = "MAIN" =>
        ep.is_main = TRUE /\ ep.has_class = FALSE

  MainNotImpl ==
    \A ep \in entry_points :
      ep.etype = "MAIN" => ep.has_class = FALSE

  PublicOnlyForLibrary ==
    \A ep \in entry_points :
      ep.etype = "PUBLIC_API" => codebase_type = "library"

  ImplMethodsExcluded ==
    \A ep \in entry_points :
      ep.etype = "PUBLIC_API" => ep.has_class = FALSE

  DotfilesExcluded ==
    \A ep \in entry_points : ep.is_dotfile = FALSE

  HttpRouteHasMethod ==
    \A ep \in entry_points :
      ep.etype = "HTTP_ROUTE" =>
        ep.method \in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}

  ValidEntryTypes ==
    \A ep \in entry_points :
      ep.etype \in {"MAIN", "PUBLIC_API", "HTTP_ROUTE", "CLI_COMMAND"}

  NoMainFromImpl ==
    \A ep \in entry_points :
      ep.has_class = TRUE => ep.etype /= "MAIN"

  NoPublicAPIFromImpl ==
    \A ep \in entry_points :
      ep.has_class = TRUE => ep.etype /= "PUBLIC_API"

  AllInvariants ==
    /\ MainIsTopLevel
    /\ MainNotImpl
    /\ PublicOnlyForLibrary
    /\ ImplMethodsExcluded
    /\ DotfilesExcluded
    /\ HttpRouteHasMethod
    /\ ValidEntryTypes
    /\ NoMainFromImpl
    /\ NoPublicAPIFromImpl

end define;

fair process Discoverer = "discoverer"
begin
  SkelCheckMain:
    if ~skel_dotfile /\ skel_is_main /\ ~skel_has_class then
      entry_points := entry_points \cup
        {[etype      |-> "MAIN",
          is_main    |-> TRUE,
          has_class  |-> FALSE,
          is_public  |-> skel_is_public,
          is_dotfile |-> FALSE,
          method     |-> "NONE",
          src        |-> "skel"]};
    end if;
  SkelCheckPubAPI:
    if ~skel_dotfile
       /\ codebase_type = "library"
       /\ skel_is_public
       /\ ~skel_has_class
       /\ ~skel_is_main then
      entry_points := entry_points \cup
        {[etype      |-> "PUBLIC_API",
          is_main    |-> FALSE,
          has_class  |-> FALSE,
          is_public  |-> TRUE,
          is_dotfile |-> FALSE,
          method     |-> "NONE",
          src        |-> "skel"]};
    end if;
  FileCheckActix:
    if ~file_dotfile /\ file_has_actix then
      entry_points := entry_points \cup
        {[etype      |-> "HTTP_ROUTE",
          is_main    |-> FALSE,
          has_class  |-> FALSE,
          is_public  |-> FALSE,
          is_dotfile |-> FALSE,
          method     |-> file_actix_method,
          src        |-> "actix"]};
    end if;
  FileCheckAxum:
    if ~file_dotfile /\ file_has_axum then
      entry_points := entry_points \cup
        {[etype      |-> "HTTP_ROUTE",
          is_main    |-> FALSE,
          has_class  |-> FALSE,
          is_public  |-> FALSE,
          is_dotfile |-> FALSE,
          method     |-> file_axum_method,
          src        |-> "axum"]};
    end if;
  FileCheckClap:
    if ~file_dotfile /\ file_has_clap then
      entry_points := entry_points \cup
        {[etype      |-> "CLI_COMMAND",
          is_main    |-> FALSE,
          has_class  |-> FALSE,
          is_public  |-> FALSE,
          is_dotfile |-> FALSE,
          method     |-> "NONE",
          src        |-> "clap"]};
    end if;
  Finish:
    skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "fd9b2bd8" /\ chksum(tla) = "99b77271")
VARIABLES pc, codebase_type, skel_is_main, skel_is_public, skel_has_class, 
          skel_dotfile, file_dotfile, file_has_actix, file_actix_method, 
          file_has_axum, file_axum_method, file_has_clap, entry_points

(* define statement *)
MainIsTopLevel ==
  \A ep \in entry_points :
    ep.etype = "MAIN" =>
      ep.is_main = TRUE /\ ep.has_class = FALSE

MainNotImpl ==
  \A ep \in entry_points :
    ep.etype = "MAIN" => ep.has_class = FALSE

PublicOnlyForLibrary ==
  \A ep \in entry_points :
    ep.etype = "PUBLIC_API" => codebase_type = "library"

ImplMethodsExcluded ==
  \A ep \in entry_points :
    ep.etype = "PUBLIC_API" => ep.has_class = FALSE

DotfilesExcluded ==
  \A ep \in entry_points : ep.is_dotfile = FALSE

HttpRouteHasMethod ==
  \A ep \in entry_points :
    ep.etype = "HTTP_ROUTE" =>
      ep.method \in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}

ValidEntryTypes ==
  \A ep \in entry_points :
    ep.etype \in {"MAIN", "PUBLIC_API", "HTTP_ROUTE", "CLI_COMMAND"}

NoMainFromImpl ==
  \A ep \in entry_points :
    ep.has_class = TRUE => ep.etype /= "MAIN"

NoPublicAPIFromImpl ==
  \A ep \in entry_points :
    ep.has_class = TRUE => ep.etype /= "PUBLIC_API"

AllInvariants ==
  /\ MainIsTopLevel
  /\ MainNotImpl
  /\ PublicOnlyForLibrary
  /\ ImplMethodsExcluded
  /\ DotfilesExcluded
  /\ HttpRouteHasMethod
  /\ ValidEntryTypes
  /\ NoMainFromImpl
  /\ NoPublicAPIFromImpl


vars == << pc, codebase_type, skel_is_main, skel_is_public, skel_has_class, 
           skel_dotfile, file_dotfile, file_has_actix, file_actix_method, 
           file_has_axum, file_axum_method, file_has_clap, entry_points >>

ProcSet == {"discoverer"}

Init == (* Global variables *)
        /\ codebase_type \in {"web_app", "cli", "library"}
        /\ skel_is_main \in BOOLEAN
        /\ skel_is_public \in BOOLEAN
        /\ skel_has_class \in BOOLEAN
        /\ skel_dotfile \in BOOLEAN
        /\ file_dotfile \in BOOLEAN
        /\ file_has_actix \in BOOLEAN
        /\ file_actix_method \in {"GET", "POST"}
        /\ file_has_axum \in BOOLEAN
        /\ file_axum_method \in {"GET", "POST"}
        /\ file_has_clap \in BOOLEAN
        /\ entry_points = {}
        /\ pc = [self \in ProcSet |-> "SkelCheckMain"]

SkelCheckMain == /\ pc["discoverer"] = "SkelCheckMain"
                 /\ IF ~skel_dotfile /\ skel_is_main /\ ~skel_has_class
                       THEN /\ entry_points' = (              entry_points \cup
                                                {[etype      |-> "MAIN",
                                                  is_main    |-> TRUE,
                                                  has_class  |-> FALSE,
                                                  is_public  |-> skel_is_public,
                                                  is_dotfile |-> FALSE,
                                                  method     |-> "NONE",
                                                  src        |-> "skel"]})
                       ELSE /\ TRUE
                            /\ UNCHANGED entry_points
                 /\ pc' = [pc EXCEPT !["discoverer"] = "SkelCheckPubAPI"]
                 /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                                 skel_has_class, skel_dotfile, file_dotfile, 
                                 file_has_actix, file_actix_method, 
                                 file_has_axum, file_axum_method, 
                                 file_has_clap >>

SkelCheckPubAPI == /\ pc["discoverer"] = "SkelCheckPubAPI"
                   /\ IF ~skel_dotfile
                         /\ codebase_type = "library"
                         /\ skel_is_public
                         /\ ~skel_has_class
                         /\ ~skel_is_main
                         THEN /\ entry_points' = (              entry_points \cup
                                                  {[etype      |-> "PUBLIC_API",
                                                    is_main    |-> FALSE,
                                                    has_class  |-> FALSE,
                                                    is_public  |-> TRUE,
                                                    is_dotfile |-> FALSE,
                                                    method     |-> "NONE",
                                                    src        |-> "skel"]})
                         ELSE /\ TRUE
                              /\ UNCHANGED entry_points
                   /\ pc' = [pc EXCEPT !["discoverer"] = "FileCheckActix"]
                   /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                                   skel_has_class, skel_dotfile, file_dotfile, 
                                   file_has_actix, file_actix_method, 
                                   file_has_axum, file_axum_method, 
                                   file_has_clap >>

FileCheckActix == /\ pc["discoverer"] = "FileCheckActix"
                  /\ IF ~file_dotfile /\ file_has_actix
                        THEN /\ entry_points' = (              entry_points \cup
                                                 {[etype      |-> "HTTP_ROUTE",
                                                   is_main    |-> FALSE,
                                                   has_class  |-> FALSE,
                                                   is_public  |-> FALSE,
                                                   is_dotfile |-> FALSE,
                                                   method     |-> file_actix_method,
                                                   src        |-> "actix"]})
                        ELSE /\ TRUE
                             /\ UNCHANGED entry_points
                  /\ pc' = [pc EXCEPT !["discoverer"] = "FileCheckAxum"]
                  /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                                  skel_has_class, skel_dotfile, file_dotfile, 
                                  file_has_actix, file_actix_method, 
                                  file_has_axum, file_axum_method, 
                                  file_has_clap >>

FileCheckAxum == /\ pc["discoverer"] = "FileCheckAxum"
                 /\ IF ~file_dotfile /\ file_has_axum
                       THEN /\ entry_points' = (              entry_points \cup
                                                {[etype      |-> "HTTP_ROUTE",
                                                  is_main    |-> FALSE,
                                                  has_class  |-> FALSE,
                                                  is_public  |-> FALSE,
                                                  is_dotfile |-> FALSE,
                                                  method     |-> file_axum_method,
                                                  src        |-> "axum"]})
                       ELSE /\ TRUE
                            /\ UNCHANGED entry_points
                 /\ pc' = [pc EXCEPT !["discoverer"] = "FileCheckClap"]
                 /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                                 skel_has_class, skel_dotfile, file_dotfile, 
                                 file_has_actix, file_actix_method, 
                                 file_has_axum, file_axum_method, 
                                 file_has_clap >>

FileCheckClap == /\ pc["discoverer"] = "FileCheckClap"
                 /\ IF ~file_dotfile /\ file_has_clap
                       THEN /\ entry_points' = (              entry_points \cup
                                                {[etype      |-> "CLI_COMMAND",
                                                  is_main    |-> FALSE,
                                                  has_class  |-> FALSE,
                                                  is_public  |-> FALSE,
                                                  is_dotfile |-> FALSE,
                                                  method     |-> "NONE",
                                                  src        |-> "clap"]})
                       ELSE /\ TRUE
                            /\ UNCHANGED entry_points
                 /\ pc' = [pc EXCEPT !["discoverer"] = "Finish"]
                 /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                                 skel_has_class, skel_dotfile, file_dotfile, 
                                 file_has_actix, file_actix_method, 
                                 file_has_axum, file_axum_method, 
                                 file_has_clap >>

Finish == /\ pc["discoverer"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["discoverer"] = "Done"]
          /\ UNCHANGED << codebase_type, skel_is_main, skel_is_public, 
                          skel_has_class, skel_dotfile, file_dotfile, 
                          file_has_actix, file_actix_method, file_has_axum, 
                          file_axum_method, file_has_clap, entry_points >>

Discoverer == SkelCheckMain \/ SkelCheckPubAPI \/ FileCheckActix
                 \/ FileCheckAxum \/ FileCheckClap \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Discoverer
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Discoverer)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
