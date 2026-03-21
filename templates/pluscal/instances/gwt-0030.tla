---- MODULE IncrementalSkip ----

EXTENDS Integers, FiniteSets, TLC

CONSTANTS
    UUIDs,
    TerminalDescriptions,
    NonTerminalDescriptions,
    Hashes

ASSUME
    /\ UUIDs # {}
    /\ TerminalDescriptions # {}
    /\ NonTerminalDescriptions # {}
    /\ Hashes # {}
    /\ TerminalDescriptions \cap NonTerminalDescriptions = {}

(* --algorithm IncrementalSkip

variables
    incremental \in {TRUE, FALSE},
    records \in [UUIDs -> [do_description : TerminalDescriptions \cup NonTerminalDescriptions,
                            src_hash : Hashes]],
    current_hashes \in [UUIDs -> Hashes],
    skipped = {},
    extracted = {},
    remaining = UUIDs,
    uuid = CHOOSE u \in UUIDs : TRUE;

define

    IsTerminal(u) ==
        records[u].do_description \in TerminalDescriptions

    HashMatches(u) ==
        records[u].src_hash = current_hashes[u]

    ShouldSkip(u) ==
        incremental /\ IsTerminal(u) /\ HashMatches(u)

    SkipOnlyWhenIncremental ==
        skipped # {} => incremental = TRUE

    SkipOnlyWhenHashMatch ==
        \A u \in skipped : records[u].src_hash = current_hashes[u]

    SkipNeverExtracted ==
        skipped \cap extracted = {}

    UnchangedNeverExtracted ==
        \A u \in UUIDs \ remaining :
            (incremental /\ IsTerminal(u) /\ HashMatches(u)) =>
            u \in skipped

    ProcessedPartition ==
        \A u \in UUIDs \ remaining :
            u \in skipped \/ u \in extracted

    BoundedSkipped ==
        skipped \subseteq UUIDs

    BoundedExtracted ==
        extracted \subseteq UUIDs

end define;

fair process Processor = "processor"
begin
    ProcessLoop:
        while remaining # {} do
            CheckSkip:
                uuid := CHOOSE u \in remaining : TRUE;
                remaining := remaining \ {uuid};
                if incremental /\ IsTerminal(uuid) /\ HashMatches(uuid) then
                    skipped := skipped \cup {uuid};
                else
                    extracted := extracted \cup {uuid};
                end if;
        end while;
    Finish:
        skip;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "f17b3dd7" /\ chksum(tla) = "f4a7d803")
VARIABLES pc, incremental, records, current_hashes, skipped, extracted, 
          remaining, uuid

(* define statement *)
IsTerminal(u) ==
    records[u].do_description \in TerminalDescriptions

HashMatches(u) ==
    records[u].src_hash = current_hashes[u]

ShouldSkip(u) ==
    incremental /\ IsTerminal(u) /\ HashMatches(u)

SkipOnlyWhenIncremental ==
    skipped # {} => incremental = TRUE

SkipOnlyWhenHashMatch ==
    \A u \in skipped : records[u].src_hash = current_hashes[u]

SkipNeverExtracted ==
    skipped \cap extracted = {}

UnchangedNeverExtracted ==
    \A u \in UUIDs \ remaining :
        (incremental /\ IsTerminal(u) /\ HashMatches(u)) =>
        u \in skipped

ProcessedPartition ==
    \A u \in UUIDs \ remaining :
        u \in skipped \/ u \in extracted

BoundedSkipped ==
    skipped \subseteq UUIDs

BoundedExtracted ==
    extracted \subseteq UUIDs


vars == << pc, incremental, records, current_hashes, skipped, extracted, 
           remaining, uuid >>

ProcSet == {"processor"}

Init == (* Global variables *)
        /\ incremental \in {TRUE, FALSE}
        /\ records \in [UUIDs -> [do_description : TerminalDescriptions \cup NonTerminalDescriptions,
                                   src_hash : Hashes]]
        /\ current_hashes \in [UUIDs -> Hashes]
        /\ skipped = {}
        /\ extracted = {}
        /\ remaining = UUIDs
        /\ uuid = (CHOOSE u \in UUIDs : TRUE)
        /\ pc = [self \in ProcSet |-> "ProcessLoop"]

ProcessLoop == /\ pc["processor"] = "ProcessLoop"
               /\ IF remaining # {}
                     THEN /\ pc' = [pc EXCEPT !["processor"] = "CheckSkip"]
                     ELSE /\ pc' = [pc EXCEPT !["processor"] = "Finish"]
               /\ UNCHANGED << incremental, records, current_hashes, skipped, 
                               extracted, remaining, uuid >>

CheckSkip == /\ pc["processor"] = "CheckSkip"
             /\ uuid' = (CHOOSE u \in remaining : TRUE)
             /\ remaining' = remaining \ {uuid'}
             /\ IF incremental /\ IsTerminal(uuid') /\ HashMatches(uuid')
                   THEN /\ skipped' = (skipped \cup {uuid'})
                        /\ UNCHANGED extracted
                   ELSE /\ extracted' = (extracted \cup {uuid'})
                        /\ UNCHANGED skipped
             /\ pc' = [pc EXCEPT !["processor"] = "ProcessLoop"]
             /\ UNCHANGED << incremental, records, current_hashes >>

Finish == /\ pc["processor"] = "Finish"
          /\ TRUE
          /\ pc' = [pc EXCEPT !["processor"] = "Done"]
          /\ UNCHANGED << incremental, records, current_hashes, skipped, 
                          extracted, remaining, uuid >>

Processor == ProcessLoop \/ CheckSkip \/ Finish

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == Processor
           \/ Terminating

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(Processor)

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 

THEOREM IncrementalSkipCorrect ==
    []SkipOnlyWhenIncremental
    /\ []SkipOnlyWhenHashMatch
    /\ []SkipNeverExtracted
    /\ []UnchangedNeverExtracted
    /\ []ProcessedPartition
    /\ []BoundedSkipped
    /\ []BoundedExtracted

====
