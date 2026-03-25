---- MODULE PlanReviewModeDetection ----

EXTENDS Integers, TLC

(* --algorithm PlanReviewModeDetection

variables
    self_flag \in BOOLEAN,
    external_flag \in BOOLEAN,
    cw9_dir_exists \in BOOLEAN,
    mode = "unset",
    reviews_list = "UNSET",
    determined = FALSE;

define

    ModeValid ==
        determined => mode \in {"self", "external"}

    ReviewsValid ==
        determined => reviews_list \in {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}

    ModeReviewConsistency ==
        determined =>
            /\ (mode = "self"     => reviews_list = "SELF_REVIEWS")
            /\ (mode = "external" => reviews_list = "EXTERNAL_REVIEWS")

    ExplicitOverrideSelf ==
        (determined /\ self_flag = TRUE /\ external_flag = FALSE)
            => mode = "self"

    ExplicitOverrideExternal ==
        (determined /\ external_flag = TRUE /\ self_flag = FALSE)
            => mode = "external"

    AutoDetectExternal ==
        ( determined
            /\ self_flag     = FALSE
            /\ external_flag = FALSE
            /\ cw9_dir_exists = TRUE )
            => mode = "external"

    AutoDetectSelf ==
        ( determined
            /\ self_flag     = FALSE
            /\ external_flag = FALSE
            /\ cw9_dir_exists = FALSE )
            => mode = "self"

end define;

fair process detector = "main"
begin
    DetermineMode:
        if ~(self_flag /\ external_flag) then
            if self_flag = TRUE then
                mode := "self" || reviews_list := "SELF_REVIEWS";
            elsif external_flag = TRUE then
                mode := "external" || reviews_list := "EXTERNAL_REVIEWS";
            elsif cw9_dir_exists = TRUE then
                mode := "external" || reviews_list := "EXTERNAL_REVIEWS";
            else
                mode := "self" || reviews_list := "SELF_REVIEWS";
            end if;
        end if;
    Finish:
        if ~(self_flag /\ external_flag) then
            determined := TRUE;
        end if;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "212d83f" /\ chksum(tla) = "ec34670b")
VARIABLES pc, self_flag, external_flag, cw9_dir_exists, mode, reviews_list, 
          determined

(* define statement *)
ModeValid ==
    determined => mode \in {"self", "external"}

ReviewsValid ==
    determined => reviews_list \in {"SELF_REVIEWS", "EXTERNAL_REVIEWS"}

ModeReviewConsistency ==
    determined =>
        /\ (mode = "self"     => reviews_list = "SELF_REVIEWS")
        /\ (mode = "external" => reviews_list = "EXTERNAL_REVIEWS")

ExplicitOverrideSelf ==
    (determined /\ self_flag = TRUE /\ external_flag = FALSE)
        => mode = "self"

ExplicitOverrideExternal ==
    (determined /\ external_flag = TRUE /\ self_flag = FALSE)
        => mode = "external"

AutoDetectExternal ==
    ( determined
        /\ self_flag     = FALSE
        /\ external_flag = FALSE
        /\ cw9_dir_exists = TRUE )
        => mode = "external"

AutoDetectSelf ==
    ( determined
        /\ self_flag     = FALSE
        /\ external_flag = FALSE
        /\ cw9_dir_exists = FALSE )
        => mode = "self"


vars == << pc, self_flag, external_flag, cw9_dir_exists, mode, reviews_list, 
           determined >>

ProcSet == {"main"}

Init == (* Global variables *)
        /\ self_flag \in BOOLEAN
        /\ external_flag \in BOOLEAN
        /\ cw9_dir_exists \in BOOLEAN
        /\ mode = "unset"
        /\ reviews_list = "UNSET"
        /\ determined = FALSE
        /\ pc = [self \in ProcSet |-> "DetermineMode"]

DetermineMode == /\ pc["main"] = "DetermineMode"
                 /\ IF ~(self_flag /\ external_flag)
                       THEN /\ IF self_flag = TRUE
                                  THEN /\ /\ mode' = "self"
                                          /\ reviews_list' = "SELF_REVIEWS"
                                  ELSE /\ IF external_flag = TRUE
                                             THEN /\ /\ mode' = "external"
                                                     /\ reviews_list' = "EXTERNAL_REVIEWS"
                                             ELSE /\ IF cw9_dir_exists = TRUE
                                                        THEN /\ /\ mode' = "external"
                                                                /\ reviews_list' = "EXTERNAL_REVIEWS"
                                                        ELSE /\ /\ mode' = "self"
                                                                /\ reviews_list' = "SELF_REVIEWS"
                       ELSE /\ TRUE
                            /\ UNCHANGED << mode, reviews_list >>
                 /\ pc' = [pc EXCEPT !["main"] = "Finish"]
                 /\ UNCHANGED << self_flag, external_flag, cw9_dir_exists, 
                                 determined >>

Finish == /\ pc["main"] = "Finish"
          /\ IF ~(self_flag /\ external_flag)
                THEN /\ determined' = TRUE
                ELSE /\ TRUE
                     /\ UNCHANGED determined
          /\ pc' = [pc EXCEPT !["main"] = "Done"]
          /\ UNCHANGED << self_flag, external_flag, cw9_dir_exists, mode, 
                          reviews_list >>

detector == DetermineMode \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == detector
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(detector)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

====
