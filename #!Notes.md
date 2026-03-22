#! Notes


# IN:DO:OUT ERRORS
---                                                                                    
  What CW9 captures today                                         
                                                                                         
  The toolchain has three layers of traceability:                                        
                                                                                         
  1. cw9 ingest → crawl.db + dag.json: Function-level catalog with UUIDs, descriptions,  
  and calls edges between functions. The DAG knows that handleToolCall calls             
  processSpreadsheet, but the edges carry no payload — just {from, to, edge_type:        
  "calls"}. No argument information.                              
  2. cw9 simulate → TLA+ specs + traces: Each GWT is a self-contained state machine.
  gwt-0125's ProcessUploadedFileState actually has a filename field (required, type      
  String, default "none") — the formal model knows filename matters. But gwt-0124's
  AgentConfigFileUploadToolsState has no filename concept at all. The two specs live in  
  separate universes.                                             
  3. Bridge artifacts: Map TLA+ operations to code concepts. Operations have empty
  parameters: {} — they describe what an operation does ("Action DetermineStrategy from  
  ProcessUploadedFile spec") but not what data flows in or out.
                                                                                         
  The structural gap                                                                     
  
  CW9 verifies vertical contracts (each function meets its own spec) but not horizontal  
  contracts (the seam between two functions preserves data flow). Specifically:
                                                                                         
  - The DAG has the edge handleToolCall → processSpreadsheet but doesn't record which    
  arguments are passed.
  - gwt-0125's TLA+ spec models filename as a required state variable, but gwt-0124 (the 
  caller) has no corresponding variable. The model checker can't find the mismatch       
  because it never composes the two specs.
  - Bridge operations have parameters: {} — a blank map — even though the TLA+ spec has  
  rich state fields. The bridge erases the data flow information the spec already        
  contains.
                                                                                         
  This is the same pattern across all four bugs: CW9 knows A calls B, and independently  
  specifies what A and B do, but never verifies that A's output satisfies B's input 
  contract.                                                                              
                                                                  
  Proposed modifications

  Tier 1: cw9 seams — Static call-site argument checking (catches Bug 4)                 
  
  What it does: New command that cross-references crawl.db call edges with the callee's  
  parameter signature to find missing arguments.                  
                                                                                         
  How it works:                                                                          
  1. cw9 ingest already parses the AST. Extend it to extract, for each calls edge, the
  argument names/keys at the call site (for JS object destructuring, this is             
  straightforward — processSpreadsheet({ buffer, mode }) → ["buffer", "mode"]).
  2. Store these on the edge: {from, to, edge_type: "calls", args_passed: ["buffer",     
  "mode"], call_line: 309}.                                                          
  3. cw9 seams compares args_passed against the callee's parameter destructuring to      
  produce a diff:
                                                                                         
  $ cw9 seams .                                                   
  SEAM handleToolCall:309 → processSpreadsheet                                           
    args_passed:  [buffer, mode]                                                         
    args_expected: [buffer, mode, projectId, uploadId, batchIds, options, filename,      
  userId]                                                                                
    MISSING:      [projectId, uploadId, batchIds, options, filename, userId]             
    ⚠ filename has fallback default (filename || '.xlsx') — silent degradation risk      
                                                                                         
  SEAM handleToolCall:371 → processSpreadsheet                                           
    args_passed:  [buffer, mode, projectId, uploadId, options]                           
    args_expected: [buffer, mode, projectId, uploadId, batchIds, options, filename,      
  userId]                                                                                
    MISSING:      [batchIds, filename, userId]                                           
    ⚠ filename has fallback default (filename || '.xlsx') — silent degradation risk      
                                                                                         
  Key insight: The ⚠ fallback default detection is critical. filename || '.xlsx' silently
   masks the bug — tests pass, the code runs, but the wrong parser is selected. cw9 seams
   should flag any missing argument where the callee uses a default/fallback, because    
  those are the most dangerous seams — they don't crash, they quietly misbehave.

  Implementation cost: Low. The AST parsing infrastructure already exists in cw9 ingest. 
  This is mostly a new traversal pass over existing data.
                                                                                         
  Tier 2: Bridge ports — Carry data flow through the bridge (catches Bugs 1, 4)          
  
  What it does: Extend bridge artifacts with ports that declare what data crosses the    
  boundary between two GWTs.                                      
                                                                                         
  Current state: Bridge operations have parameters: {}. This erases the information      
  that's already in the TLA+ spec. gwt-0125's spec knows filename is required, but the
  bridge for gwt-0125's ReceiveToolCall operation says nothing about what must be        
  provided.                                                       

  Proposed: When cw9 bridge generates artifacts from a TLA+ spec, it should also generate
   inbound port declarations from the spec's Init state, and outbound port declarations
  from the spec's terminal state:                                                        
                                                                  
  {                                                                                      
    "operations": {
      "ReceiveToolCall": {                                                               
        "parameters": {},                                         
        "inbound_port": {                                                                
          "required_from_caller": {                               
            "upload_id": { "source_field": "upload_id", "default": "none", "type":       
  "String" },                                                                            
            "filename":  { "source_field": "filename",  "default": "none", "type":       
  "String" },                                                                            
            "mimetype":  { "source_field": "mimetype",  "default": "none", "type":
  "String" }                                                                             
          }                                                       
        }                                                                                
      }                                                                                  
    }                                                                                    
  }                                                                                      
                                                                  
  Then cw9 verify checks: for every calls edge in the DAG where the callee has an inbound
   port, does the caller actually provide those fields? This is the bridge-level version
  of cw9 seams — it works even when the call site isn't a simple function call (e.g.,    
  when data flows through a shared context object or through the Anthropic API's messages
   array).

  For Bug 1 specifically: The "caller" is the route handler building the messages array, 
  and the "callee" is the Anthropic API (which requires upload context in the message
  text for the LLM to know the ID). This isn't a function call — it's a semantic         
  contract. Port declarations would let you express: "the LLM process requires upload_id
  values in the conversational context, not just in the tool schema."

  Implementation cost: Medium. Requires extending the bridge generator and adding a new  
  verification pass.
                                                                                         
  Tier 3: cw9 compose — Multi-turn session lifecycle specs (catches Bugs 2, 3)           
  
  What it does: Generates composed TLA+ specs that model state across request boundaries.
                                                                  
  The problem: Bugs 2 and 3 aren't call-boundary bugs — they're temporal seam bugs. The  
  state machine doesn't end when the function returns; it ends when the session ends. But
   each GWT models a single request in isolation.                                        
                                                                  
  Proposed: A new spec type, session specs, that model the full lifecycle:               
  
  (* Session-level spec: composes Turn1 and Turn2 *)                                     
  VARIABLES session_messages, turn_number, upload_tools_active                           
                                                                                         
  Init ==                                                                                
    /\ session_messages = <<>>                                                           
    /\ turn_number = 0                                                                   
    /\ upload_tools_active = FALSE                                                       
                                                                                         
  Turn1_Upload ==                                                                        
    /\ turn_number = 0                                            
    /\ (* user uploads file, agent calls process_uploaded_file *)
    /\ session_messages' = Append(session_messages,                                      
         [role |-> "assistant", content |-> {tool_use_block}])                           
    /\ session_messages' = Append(session_messages',                                     
         [role |-> "user", content |-> {tool_result_block}])                             
    /\ upload_tools_active' = TRUE                                                       
    /\ turn_number' = 1                                                                  
                                                                                         
  Turn2_FollowUp ==                                                                      
    /\ turn_number = 1                                            
    /\ (* user sends text-only follow-up *)                                              
    /\ (* INVARIANT: upload_tools_active must still be TRUE *)                           
    /\ (* INVARIANT: session_messages must contain tool_use/tool_result from Turn1 *)    
                                                                                         
  SessionInvariant ==                                                                    
    /\ (upload_tools_active => \E m \in session_messages : m.content has tool_use)       
    /\ (turn_number > 0 => Len(session_messages) > 0)                                    
                                                                                         
  How cw9 compose works:                                                                 
  1. Detect "session-shaped" functions: those that call both getChatSessionById (load    
  state) and appendMessage (persist state). This is a reliable heuristic — it appears in 
  agent.js and nowhere else.                                                            
  2. For each session-shaped function, identify the state that flows through the database
   between turns (the messages array).                                                   
  3. Auto-generate a session spec that models two sequential invocations of the function,
   with the database as the shared medium.                                               
  4. Run the model checker on the composed spec. It will find:                           
    - Bug 2: Turn1's tool_use/tool_result blocks aren't in session_messages after Turn1
  completes (persistence gap).                                                           
    - Bug 3: Turn2's upload_tools_active is FALSE because uploadIds is re-derived from   
  request body, not from session state.                                                  
                                                                                         
  Implementation cost: High. Requires composing TLA+ specs, which means understanding the
   schema of the shared state (the messages array) well enough to generate the inter-turn
   transitions. But this is also the only mechanism that would have caught Bugs 2 and 3
  before they shipped.                                                                   
                                                                  
  Tier 4: cw9 plan enhancement — Auto-detect when session specs are needed               
  
  What it does: During cw9 plan (or cw9 research), when generating GWTs for a function,  
  automatically detect session-shaped patterns and emit a warning + suggested session
  GWTs.                                                                                  
                                                                  
  Heuristic: If the function being planned:                                              
  - Loads state from a persistent store (DB query at the start)
  - Mutates that state (writes at the end)                                               
  - The GWTs only specify single-invocation behavior              
                                                                                         
  Then emit:                                                                             
  ⚠ Session lifecycle gap detected:
    handleToolCall loads session via getChatSessionById and persists via appendMessage.  
    No GWT specifies cross-turn invariants.                                              
    Suggested GWTs:                                                                      
    - gwt-XXXX: "Given Turn1 used tool_use, when Turn2 loads session, then messages      
  include tool_use/tool_result"                                                          
    - gwt-XXXY: "Given Turn1 activated upload tools, when Turn2 has no upload_ids, then  
  upload tools still available"                                                        
                                                                                         
  This is the cheapest intervention with the highest leverage — it doesn't require
  composing TLA+ specs, it just flags the gap at planning time so the human (or the      
  implementing agent) knows to write the cross-turn tests.        
                                                                                         
  ---                                                                                    
  Priority order
                                                                                         
  ┌──────┬────────────────────────┬───────────────────────┬────────┬────────────────┐ 
  │ Tier │          What          │        Catches        │ Effort │      ROI       │    
  ├──────┼────────────────────────┼───────────────────────┼────────┼────────────────┤    
  │ 4    │ cw9 plan session-gap   │ Bugs 2, 3 (at         │ Low    │ Highest        │    
  │      │ detection              │ planning time)        │        │                │    
  ├──────┼────────────────────────┼───────────────────────┼────────┼────────────────┤    
  │ 1    │ cw9 seams call-site    │ Bug 4                 │ Low    │ High           │ 
  │      │ args                   │                       │        │                │    
  ├──────┼────────────────────────┼───────────────────────┼────────┼────────────────┤ 
  │ 2    │ Bridge ports           │ Bugs 1, 4             │ Medium │ Medium         │    
  ├──────┼────────────────────────┼───────────────────────┼────────┼────────────────┤
  │ 3    │ cw9 compose session    │ Bugs 2, 3 (formally)  │ High   │ High but       │    
  │      │ specs                  │                       │        │ expensive      │
  └──────┴────────────────────────┴───────────────────────┴────────┴────────────────┘    
                                                                  
  Tier 4 and Tier 1 together cover all four bug classes at low cost and would have       
  flagged every one of these issues before implementation. Tiers 2-3 make the catches
  formal and automatic rather than advisory.            

# Database writes
  Root Cause

  The corruption happens because of how CrawlStore handles writes:

  1. WAL mode is correctly set (crawl_store.py:29), which should make this resilient — WAL is
  designed so readers never block writers and a crash leaves the DB intact. However...
  2. upsert_record() is not atomic (crawl_store.py:284-292). It does:
    - UPDATE ins SET source_uuid = NULL ...
    - DELETE FROM records WHERE uuid = ?
    - INSERT INTO records ... (inside insert_record)
    - Multiple INSERT INTO ins ... (loop)
    - Multiple INSERT INTO outs ... (loop)
    - conn.commit()

  All of these run inside Python's default implicit transaction, but if SIGKILL arrives between
   the DELETE and the final commit(), the implicit transaction's rollback journal may not be
  cleanly flushed. With WAL mode this should normally auto-recover on next open, unless the
  -wal or -shm files get deleted or the process is killed during a WAL checkpoint.
  3. No PRAGMA synchronous is set — SQLite defaults to FULL in WAL mode (which is safe), but
  the real problem is likely:
  4. The sweep phase fires up to 10 concurrent upsert_record() calls from async tasks
  (crawl_orchestrator.py:338-357), all sharing a single sqlite3.Connection that is not
  thread-safe and has no mutex. Python's sqlite3 module has a check_same_thread default of
  True, but since this is async (single-threaded event loop), it doesn't error — yet the rapid
  interleaving of execute()/commit() calls from concurrent coroutines can corrupt the WAL state
   when a kill arrives mid-checkpoint.
  5. No signal handling or graceful shutdown — SIGTERM/SIGINT kills the process immediately
  with no chance to finish an in-flight transaction or checkpoint.

  Mitigations (in order of impact)

  1. Wrap upsert_record in an explicit transaction (quick fix)

  def upsert_record(self, record: FnRecord | AxRecord) -> None:
      self.conn.execute("BEGIN IMMEDIATE")
      try:
          self.conn.execute(
              "UPDATE ins SET source_uuid = NULL WHERE source_uuid = ?",
              (record.uuid,),
          )
          self.conn.execute("DELETE FROM records WHERE uuid = ?", (record.uuid,))
          self.insert_record(record)  # this calls commit() — needs refactor
      except:
          self.conn.rollback()
          raise

  But insert_record calls commit() internally, so you'd need to refactor: extract a
  _insert_record_no_commit() and have both methods call it.

  2. Add graceful shutdown handling

  import signal, asyncio

  async def run(self):
      loop = asyncio.get_event_loop()
      self._shutdown = False
      for sig in (signal.SIGINT, signal.SIGTERM):
          loop.add_signal_handler(sig, self._handle_shutdown)
      # ... existing crawl logic, checking self._shutdown between extractions

  def _handle_shutdown(self):
      self._shutdown = True
      logger.info("Shutdown requested, finishing current extraction...")

  This lets the current upsert_record + commit() finish before the process exits.

  3. Serialize DB writes from async tasks

  The semaphore bounds concurrency for the LLM calls, but the DB writes still interleave. Add
  an asyncio.Lock around store writes:

  self._db_lock = asyncio.Lock()

  async def _extract_bounded(uuid):
      async with sem:
          result = await self.extract_one(uuid)  # LLM call (concurrent)
      async with self._db_lock:
          self.store.upsert_record(result)  # DB write (serialized)

  4. Auto-backup before crawl

  Cheapest safety net — copy crawl.db before starting:

  import shutil
  shutil.copy2(db_path, db_path.with_suffix('.db.bak'))

  My recommendation

  Do #4 immediately (one line, prevents data loss), then implement #2 + #3 (graceful shutdown +
   serialized writes) as the real fix. #1 is good hygiene but less critical if #3 is in place.



#  CW9 brownfield testing Three distinct problems, one root cause

  1. Simulation traces are 100% failure paths

  All 10 gwt-0004 traces fail at TryLoadEnrichments (9 traces) or TryBuildPrompt (1 trace).
  Zero traces reach the happy path. Zero traces exercise streaming partials. Zero traces call
  onDone.

  This is not "normal." This is a probability problem in the model.

  The spec has 4 sequential either/or nondeterministic choice points before StreamNext, plus
  MaxPartials iterations of another either/or inside the loop. TLC's -simulate does a random
  walk — at each either, it picks a branch uniformly at random.

  The probability of reaching the happy path requires picking the success branch at every
  choice point:
  - TryLoadEnrichments: 1/2
  - TryBuildPrompt: 1/2
  - TryInvokeBAML: 1/2
  - StreamNext (×MaxPartials iterations): (1/2)^MaxPartials each

  If MaxPartials = 3, happy path probability = (1/2)^6 = 1.6%. With 10 traces, the expected
  number of happy-path traces is ~0.16. The model is structurally biased toward failure.

  This means gen-tests — which uses simulation traces as "PRIMARY context" — will generate
  tests that only cover error paths. The very thing the pipeline was designed to produce
  (concrete execution paths for test generation) is systematically missing the most important
  path.

  2. Crawl produced 363 skeletons, 161 failures, ~10 extracted

  The review found all 10 depends_on UUIDs are skeletons, with getEnrichmentsBySession
  actually EXTRACTION_FAILED. The crawl barely worked. That means:

  - The cards-in-prompt fix we made is inert for this run — the cards exist but contain no
  behavioral data (just signatures)
  - The LLM writing PlusCal got function names and GWT Given/When/Then, but NOT the actual
  IN:DO:OUT contracts
  - The spec it produced is structurally correct (invariants hold, verified by TLC) but
  semantically disconnected from the real code behavior

  The spec models runStreamingChatAgent as a generic sequential-fail-at-any-point pipeline. It
   doesn't reflect the actual error types, the actual enrichment data shape, or the actual
  streaming protocol — because it never saw those details in the cards.

  3. The deviation is NOT in the formal proof — it's in what feeds the proof

  The formal proof is solid. TLC exhaustively checked every reachable state. All 11 invariants
   hold. That part is deterministic and complete.

  The deviation enters at three points:

  ┌───────────────┬──────────────────────────────────┬────────────────────────────────────┐
  │     Stage     │              Issue               │           Deterministic?           │
  ├───────────────┼──────────────────────────────────┼────────────────────────────────────┤
  │ Crawl         │ 161 failures, most records       │ No — LLM extraction can fail       │
  │ extraction    │ skeleton-only                    │                                    │
  ├───────────────┼──────────────────────────────────┼────────────────────────────────────┤
  │ PlusCal       │ Spec models generic failure, not │ No — depends on prompt quality     │
  │ generation    │  actual code behavior            │ (cards vs skeletons)               │
  ├───────────────┼──────────────────────────────────┼────────────────────────────────────┤
  │ Simulation    │ Biased toward failure paths by   │ No — random sampling, model has    │
  │ traces        │ model structure                  │ exponential failure bias           │
  ├───────────────┼──────────────────────────────────┼────────────────────────────────────┤
  │ Bridge        │ Correct for the spec, but spec   │ Deterministic given the spec       │
  │ artifacts     │ is generic                       │                                    │
  └───────────────┴──────────────────────────────────┴────────────────────────────────────┘

  Pipeline implications

  Problem 1: Trace sampling is broken for models with nondeterministic error branches. Any
  spec that uses either { succeed } or { fail } at multiple sequential points will
  exponentially bias traces toward failure. This is fundamental to how TLC -simulate works —
  it's a uniform random walk.

  Fix options:
  - Weight simulation toward longer traces (success paths are longer)
  - Run separate simulations: one with failures disabled (to get happy-path traces), one with
  failures enabled
  - Post-process: if all N traces end in failure, re-run with higher N or modified model
  - Add a --simulate-happy-path flag that temporarily removes error branches for trace
  generation

  Problem 2: Skeleton-only cards make the cards-in-prompt fix useless. The pipeline needs to
  gate on extraction quality — if depends_on functions are all skeletons, warn the user to run
   cw9 crawl first.

  Fix options:
  - cw9 pipeline checks extraction status of depends_on UUIDs before running the loop
  - Warn (or error) if >50% of depends_on records are SKELETON_ONLY or EXTRACTION_FAILED
  - Add this check to /cw9_plan_review

  Problem 3: gen-tests inherits trace bias. Since traces are PRIMARY context, biased traces →
  biased tests. The review found this: the plan's human-written tests cover the happy path,
  but the pipeline's automated path wouldn't.

  This is the biggest systemic issue. The pipeline is: verified model → traces → tests → code.
   If traces are biased, the whole downstream chain is biased. The formal verification is
  exhaustive, but the test generation is not — it's sampled.



# Now I have a clear picture of the gap. Let me organize your thinking.            
                                                                                              
  The Problem, Clearly Stated                                                                 
                                                                                              
  Your current brownfield workflow is:                                                        
                                                                                              
  research_codebase skill (~65% context consumed by MCP + skill overhead)                     
      → manual TDD plan (with remaining ~35% context)                                         
      → code generation (debugging surprises from missed dependencies)

  The bottleneck is that research_codebase tries to discover and hold the entire relevant
  slice of a foreign codebase in a single LLM context window. Complex codebases exceed what
  fits.

  What Already Exists in CW9

  The registry DAG already has the right primitives for this:

  - extract_subgraph(node_id) — minimal ancestor+descendant subgraph (designed explicitly for
  context-scoping LLM prompts, per your Phase 6 handoff)
  - query_impact(target_id) — reverse dependency analysis (what depends on X)
  - query_relevant(resource_id) — forward transitive closure
  - 21 typed edge kinds — CALLS, IMPORTS, DEPENDS_ON, HANDLES, CHAINS, TRANSFORMS_FROM/TO,
  etc.

  But the registry is only populated from JSON schema files via extractor.py — greenfield
  only. There's no cw9 ingest for existing codebases yet (noted as "Stage 2 FUTURE" in your
  roadmap).

  What's Missing: The Code Walker

  The gap is a brownfield ingestion layer that:

  1. Walks the target codebase — AST-level analysis of an existing repo (not schema files)
  2. Extracts call chains — function A calls B calls C, with argument/return shapes
  3. Records in-do-out patterns — for each function: what comes in (params, reads), what it
  does (mutations, side effects), what goes out (returns, writes)
  4. Maps dependency loops — circular references, event chains, middleware pipelines
  5. Populates the existing DAG — as RESOURCE, MODULE, and edge nodes with CALLS, IMPORTS,
  DEPENDS_ON, HANDLES relationships

  Once the DAG is populated from real code, the existing pipeline machinery works:

  cw9 ingest <target-repo>        ← NEW: code walker populates DAG
      → DAG now has call chains, in-do-out, dependency edges
      → extract_subgraph() gives precisely-scoped context per GWT
      → LLM sees only the relevant slice, not the whole codebase
      → GWT generators produce specs
      → CW9 pipeline: proofs → traces → code

  Your Insight, Reframed

  Instead of the LLM doing the research (expensive, context-limited, hallucination-prone), a
  deterministic code walker does it once and stores the results in the registry. The LLM then
  consumes pre-computed, precisely-scoped subgraphs — trading one bloated research pass for
  many small, focused generation passes.

  This is the same insight as the-insight.md (registry-as-CSP eliminates nested loops),
  extended to the brownfield case.

  Concrete Architecture Sketch

  ┌─────────────────────────────────────────┐
  │  cw9 ingest <path> [--lang=python|ts|go]│
  │                                          │
  │  1. AST parse → module/function/class    │
  │     nodes (RESOURCE, MODULE kind)        │
  │                                          │
  │  2. Call-chain extraction → CALLS edges  │
  │                                          │
  │  3. Import resolution → IMPORTS edges    │
  │                                          │
  │  4. In-Do-Out annotation per function:   │
  │     - inputs: params, globals read       │
  │     - effects: mutations, I/O, calls     │
  │     - outputs: returns, side effects     │
  │     (stored as node metadata)            │
  │                                          │
  │  5. Dependency cycle detection           │
  │     (already have validate_edge)         │
  │                                          │
  │  6. Closure recomputation (existing BFS) │
  └─────────────┬───────────────────────────┘
                │
                ▼
          dag.json (now populated from real code)
                │
                ▼
  ┌─────────────────────────────────────────┐
  │  GWT authoring (manual or LLM-assisted) │
  │  - User provides behavioral specs       │
  │  - register_gwt() wires to resources    │
  │  - query_context() pulls minimal slice  │
  └─────────────┬───────────────────────────┘
                │
                ▼
          Existing CW9 pipeline
          (loop → bridge → gen-tests)

  Key Design Decisions to Make

  1. AST parsing approach — Use language-native tools (ast for Python, ts-morph/tree-sitter
  for TS, go/ast for Go) or a polyglot tool like tree-sitter for all?
  2. Granularity — Module-level? Function-level? Statement-level? (Function-level seems right
  for the in-do-out pattern)
  3. In-do-out schema — What exactly gets stored per node? I'd suggest:
  {
    "inputs": ["param:name:type", "reads:global_var", "reads:config.key"],
    "effects": ["calls:other_func", "mutates:self.state", "writes:db.table"],
    "outputs": ["returns:type", "raises:ErrorType"]
  }
  4. Incremental updates — Full re-ingest or diff-based? (Start with full, optimize later)
  5. GWT authoring bridge — How do the research findings get converted to GWTs? LLM-assisted
  with the DAG as context? Or do you already have that research in another format?





# The script produces two things:                                                         
                                                                                          
  1. Verified TLA+ specs (one per GWT, in .cw9/specs/)                                    
   
  For each GWT behavior — like "given the counter is at 5, when increment is clicked, then
   the counter becomes 6" — the LLM writes a formal mathematical model in PlusCal. TLC
  (the model checker) then exhaustively explores every possible state of that model. If
  TLC finds any state where the invariants are violated, it feeds the counterexample back
  to the LLM to fix. If TLC passes, the spec is written to disk.

  The spec is proof that the behavior's logic is internally consistent. Not "it compiles"
  or "the tests pass" — it's been checked against every reachable state.

  2. Bridge artifacts (one JSON file per GWT, in .cw9/bridge/)

  Once a spec is verified, the bridge mechanically translates it into code-facing
  artifacts:

  - Data structures — what state the code needs to hold (e.g., a counter field of type
  integer with a minimum of 0)
  - Operations — what functions the code needs (e.g., increment(counter) → counter,
  decrement(counter) → counter)
  - Verifiers — conditions that must always be true (e.g., "counter is never negative")
  - Assertions — test-ready checks with human-readable failure messages
  - Test scenarios — concrete sequences of actions with expected outcomes, derived from
  TLC's state exploration

  What these are used for:

  The bridge artifacts are the input to cw9 gen-tests, which hands them to the LLM along
  with TLC simulation traces to generate actual runnable test files. An implementation LLM
   then writes code to make those tests pass.

  In plain terms: the script takes English-language behavioral requirements, turns them
  into mathematically verified models, then extracts from those models the exact data
  shapes, function signatures, and test cases that the final code must satisfy. The code
  hasn't been written yet — but its contract has been formally derived.


# usage: run_loop_bridge.py [-h] [--db DB] [--session SESSION]
                               [--project-dir PROJECT_DIR] [--gwt GWTS]
                               [--max-retries MAX_RETRIES] [--skip-setup]
                               [--loop-only] [--bridge-only]

     Run full CW9 pipeline with real LLM: loop → bridge

     options:
       -h, --help            show this help message and exit
       --db DB               CW7 SQLite database path
       --session SESSION     CW7 session ID (auto-detected if only one)
       --project-dir PROJECT_DIR
                             Project directory (default: temp dir)
       --gwt GWTS            GWT ID(s) to process (default: all registered).
                             Repeatable.
       --max-retries MAX_RETRIES
                             Max LLM retries per GWT (default: 5)
       --skip-setup          Skip init/extract/register (project already set up)
       --loop-only           Run loop only, skip bridge
       --bridge-only         Run bridge only (specs must already exist)


# This test validates the register subcommand and the P1 fix —
  it doesn't involve code generation at all.
                                                                                          
  Here's where it sits in the pipeline:
                                                                                          
  CW7 approval → cw9 init → cw9 extract → cw9 register → cw9 loop → cw9 bridge → plan_path
                                                ↑                         ↓
                                           WE ARE HERE            code generation happens
  here

  register is plumbing. It takes CW7's approved GWT criteria and maps them into CW9's DAG
  with stable IDs. No LLM is called. The value is:

  1. Clean ID space — gwt-0001 not gwt-0024, so downstream cw9 loop gwt-0001 targets the
  right node
  2. Binding stability — re-running register doesn't create duplicate nodes, so the
  pipeline is resumable
  3. Auditability — every DAG node traces to a CW7 database row

  The LLM enters the picture at cw9 loop, which takes a registered GWT (e.g., gwt-0001)
  and generates a PlusCal/TLA+ formal spec, then cw9 bridge extracts verification
  artifacts, and eventually cw9 gen-tests uses the LLM to generate actual test code from
  simulation traces.

  This test was about making sure the foundation under the code generation pipeline is
  clean — not about code generation itself.

❯ In the @BOOTSTRAP.md process, we used the LLM to generate code. Where does that come in 
 with CW9?                                                                                
  ⎿  Read BOOTSTRAP.md (817 lines)                                                        
                                                                                          
● The LLM enters at cw9 loop. Here's the chain:                                           
                                                                                          
  cw9 register  →  cw9 loop  →  cw9 bridge  →  cw9 gen-tests                              
     (plumbing)     (LLM HERE)    (mechanical)    (LLM HERE)                              
                                                                                          
  cw9 loop <gwt-id> is the one-shot loop from BOOTSTRAP.md Phase 3. It:
  1. Queries the DAG for the GWT's transitive dependencies (context)
  2. Assembles a prompt with that context + PlusCal templates
  3. Sends it to the LLM (Claude Agent SDK) to generate a PlusCal spec
  4. Compiles PlusCal → TLA+, runs TLC model checker
  5. If TLC fails → feeds counterexample back to LLM for retry
  6. If TLC passes → verified spec written to .cw9/specs/

  cw9 bridge <gwt-id> then mechanically translates that verified spec into code-facing
  artifacts (data structures, function signatures, test assertions).

  cw9 gen-tests <gwt-id> uses the LLM again to generate pytest files from TLC simulation
  traces + bridge artifacts.

  So what you just validated — the register step — ensures the LLM gets the right GWT when
   cw9 loop gwt-0001 runs. Without the P1 fix, gwt-0001 would have been "closure updates
  on register" (CW9's own behavior), not the CW7 criterion you actually wanted to verify.

  The next step to see code generation is:
  cw9 loop gwt-0001 "$tmpdir"

  That's where the LLM writes a PlusCal spec for "A prover has a file and runs ingest with
   signing enabled" and TLC either verifies it or produces a counterexample.

In the @BOOTSTRAP.md process, we used the LLM to generate code. Where does that come in 
 with CW9?                                                                                
  ⎿  Read BOOTSTRAP.md (817 lines)                                                        
                                                                                          
● The LLM enters at cw9 loop. Here's the chain:                                           
                                                                                          
  cw9 register  →  cw9 loop  →  cw9 bridge  →  cw9 gen-tests                              
     (plumbing)     (LLM HERE)    (mechanical)    (LLM HERE)                              
                                                                                          
  cw9 loop <gwt-id> is the one-shot loop from BOOTSTRAP.md Phase 3. It:
  1. Queries the DAG for the GWT's transitive dependencies (context)
  2. Assembles a prompt with that context + PlusCal templates
  3. Sends it to the LLM (Claude Agent SDK) to generate a PlusCal spec
  4. Compiles PlusCal → TLA+, runs TLC model checker
  5. If TLC fails → feeds counterexample back to LLM for retry
  6. If TLC passes → verified spec written to .cw9/specs/

  cw9 bridge <gwt-id> then mechanically translates that verified spec into code-facing
  artifacts (data structures, function signatures, test assertions).

  cw9 gen-tests <gwt-id> uses the LLM again to generate pytest files from TLC simulation
  traces + bridge artifacts.

  So what you just validated — the register step — ensures the LLM gets the right GWT when
   cw9 loop gwt-0001 runs. Without the P1 fix, gwt-0001 would have been "closure updates
  on register" (CW9's own behavior), not the CW7 criterion you actually wanted to verify.

  The next step to see code generation is:
  cw9 loop gwt-0001 "$tmpdir"

  That's where the LLM writes a PlusCal spec for "A prover has a file and runs ingest with
   signing enabled" and TLC either verifies it or produces a counterexample.

❯ based on your diagram, the plan_path is superfluous. WE should simply hand off to cw9   
after GWT and tech stack.                                                                 
  ⎿  Interrupted · What should Claude do instead?                                         
                                                                                          
❯ based on your diagram, the plan_path is superfluous. WE should simply hand off to cw9   
after GWT and tech stack in CW7                                                           
                                                                                          
● You're right. Let me trace the redundancy.                                              
                                                                                          
  Current planned flow:                                                                   
  CW7: GWT approval → cw9 register → cw9 loop → cw9 bridge → plan_path → implement
                                                                  ↑                       
                                                            REDUNDANT

  What plan_path does in CW7: Takes architectural context and generates an implementation
  plan — what to build, what files to touch, what patterns to follow.

  What CW9 already produces by the time bridge completes:
  - Verified TLA+ spec (formal model of the behavior)
  - Data structures with types and validation rules
  - Function signatures with parameters and error types
  - Test assertions derived from invariants
  - Test scenarios from TLC simulation traces

  Then gen-tests produces actual runnable test files.

  plan_path would be generating a prose plan for something that already has a formally
  verified spec, concrete data models, function signatures, and generated tests. The
  bridge artifacts ARE the plan — but better, because they're mechanically derived from a
  verified model rather than LLM-generated prose.

  Simplified flow:
  CW7: GWT approval + tech stack → cw9 register → cw9 loop → cw9 bridge → cw9 gen-tests →
  implement to pass tests

  CW7's role reduces to:
  1. Requirements gathering (specs, GWT decomposition, approval)
  2. Tech stack selection (feeds --lang to gen-tests)
  3. Handing off to CW9 with the approved GWTs
  4. Receiving back generated tests as the implementation contract

  The "plan" is implicit: make the tests pass. The tests are derived from verified formal
  specs. No prose planning step needed.


  ---                                                                                     
# Integration Deduction: CW9 API ↔ CW7 /api/chat Pipeline                                 
                                                                                          
  What CW9 Has Today                                                                      
                                                                                          
  Library API (Python):                                                                   

  ┌───────────────────────┬──────────────────────────────────────────────────┬────────┐
  │      Capability       │                       API                        │ Status │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Project               │ ProjectContext.from_target()                     │ Ready  │
  │ initialization        │                                                  │        │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ DAG load/save         │ RegistryDag.load() / .save()                     │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Requirement           │ dag.register_requirement()                       │ Ready  │
  │ registration          │                                                  │        │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ GWT registration      │ dag.register_gwt(given, when, then, parent_req?) │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Impact analysis       │ dag.query_impact(node_id)                        │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Subgraph extraction   │ dag.extract_subgraph(node_id)                    │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Affected test query   │ dag.query_affected_tests(node_id)                │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Bridge translation    │ run_bridge(tla_text, traces?) → BridgeResult     │ Ready  │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Simulation traces     │ load_simulation_traces(),                        │ Ready  │
  │                       │ format_traces_for_prompt()                       │        │
  ├───────────────────────┼──────────────────────────────────────────────────┼────────┤
  │ Context building      │ query_context(dag, gwt_id),                      │ Ready  │
  │                       │ format_prompt_context()                          │        │
  └───────────────────────┴──────────────────────────────────────────────────┴────────┘

  CLI (7 subcommands):

  ┌──────────────────────────────┬──────────┬─────────────────────────────────┐
  │           Command            │ JSON I/O │        Machine-readable?        │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 init                     │ None     │ No — human stdout               │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 status                   │ None     │ No — human stdout               │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 extract                  │ None     │ No — human stdout               │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 loop <gwt_id> <dir>      │ None     │ Exit code only (0/1)            │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 bridge <gwt_id> <dir>    │ None     │ Exit code + file artifact       │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 gen-tests <gwt_id> <dir> │ None     │ Exit code + file artifact       │
  ├──────────────────────────────┼──────────┼─────────────────────────────────┤
  │ cw9 test <dir>               │ None     │ Passes through pytest exit code │
  └──────────────────────────────┴──────────┴─────────────────────────────────┘

  The Integration Gap

  The TDD plan (Behavior 3) specifies this step chain from CW7's Node.js backend:

  extract → register_gwt(API) → loop → bridge → gen-tests → test

  The critical friction point is register_gwt(API). Every other step maps to a CLI
  subcommand that CW7 can shell out to. But GWT registration requires the Python library
  API — there's no CLI path for it. The plan and review both flag this.

  Three Options to Bridge the Gap

  Option 1: Add cw9 register CLI subcommand (Recommended)

  What to build in CW9:
  cw9 register <target_dir> --json
  Reads JSON from stdin, writes JSON to stdout. This is the only subcommand that needs
  machine-readable I/O because it's the handoff point — CW7 must pass structured GWT data
  in and get gwt_id mappings back.

  Stdin contract:
  {
    "gwts": [
      {
        "criterion_id": "crit-1034",
        "given": "an existing encryption key and system configured for 2-of-3 Shamir",
        "when": "user runs CLI command to initiate key backup",
        "then": "exactly 3 distinct key shares are generated",
        "parent_req": "req-0008",
        "name": "backup_key_shamir"
      }
    ]
  }

  Stdout contract:
  {
    "registered": [
      { "criterion_id": "crit-1034", "gwt_id": "gwt-0024" }
    ],
    "dag_path": "/path/to/.cw9/dag.json"
  }

  Implementation: ~40 lines in cli.py. Load DAG, iterate GWTs, call dag.register_gwt() for
   each, save DAG, emit JSON. This leverages the existing library API directly.

  Why this is the right choice: It keeps CW7's adapter as pure subprocess calls — no
  Python bridge script to maintain, no python3 -c inline snippets. The filesystem handoff
  pattern stays consistent across all steps.

  Option 2: Add --json flag to all existing subcommands

  Extend each subcommand to support --json for machine-readable output. This would let CW7
   parse structured results from every step, not just register. For example:

  - cw9 loop gwt-0024 /path --json → stdout: {"status": "pass", "spec_path": "...",
  "attempts": 2}
  - cw9 bridge gwt-0024 /path --json → stdout: {"artifact_path": "...", "counts": {...}}

  Verdict: Nice-to-have but not blocking. CW7 can read file artifacts from .cw9/ directly.
   The exit code + artifact files are sufficient for the adapter's classification logic.
  Add this later if SSE progress reporting needs richer data.

  Option 3: --context-file on cw9 loop

  The analysis identified that CW7's orchestration spec steps are the richest domain
  context for the LLM loop. Today cw9 loop builds context only from the DAG (via
  query_context()). Adding:

  cw9 loop gwt-0024 /path --context-file /path/to/spec-1034.md

  would let CW7 pass its spec markdown as supplementary prompt material. The library API
  already has format_prompt_context() — this just needs a file-read + concatenation before
   the LLM call.

  Verdict: High value, small effort. The spec steps (Input/Process/Output/Error per step)
  give the LLM dramatically better modeling context than the GWT triple alone.

  What the CW9 Library API Already Supports (No Changes Needed)

  These CW7 integration needs map directly to existing API:

  CW7 Need: Parse CW7 spec → GWT triples
  CW9 API: CW7 does this (it already has the GWT data in acceptance_criteria rows)
  ────────────────────────────────────────
  CW7 Need: Register GWTs with DAG edges
  CW9 API: dag.register_gwt(given, when, then, parent_req) ← via new register CLI
  ────────────────────────────────────────
  CW7 Need: Verify each GWT
  CW9 API: cw9 loop <gwt_id> <dir> ← CLI, no change needed
  ────────────────────────────────────────
  CW7 Need: Generate bridge artifacts
  CW9 API: cw9 bridge <gwt_id> <dir> ← CLI, no change needed
  ────────────────────────────────────────
  CW7 Need: Read bridge JSON for planning prompt
  CW9 API: JSON.parse(fs.readFileSync('.cw9/bridge/<id>_bridge_artifacts.json')) — direct
    file read
  ────────────────────────────────────────
  CW7 Need: Generate tests in target language
  CW9 API: cw9 gen-tests <gwt_id> <dir> --lang typescript ← CLI, no change needed
  ────────────────────────────────────────
  CW7 Need: Run affected tests after node change
  CW9 API: cw9 test <dir> --node <id> ← CLI, no change needed

  What Needs to Be Extended in CW9

  ┌───────────────────────────┬──────────┬────────────┬──────────────────────────────┐
  │         Extension         │  Effort  │ Blocking?  │             Why              │
  ├───────────────────────────┼──────────┼────────────┼──────────────────────────────┤
  │ cw9 register subcommand   │ Small    │            │ Only way to register GWTs    │
  │ (JSON stdin→stdout)       │ (~40     │ Yes        │ from Node.js without a       │
  │                           │ LOC)     │            │ Python bridge script         │
  ├───────────────────────────┼──────────┼────────────┼──────────────────────────────┤
  │ --context-file on cw9     │ Small    │            │ Enriches LLM context with    │
  │ loop                      │ (~15     │ No         │ CW7 spec steps; degrades     │
  │                           │ LOC)     │            │ gracefully without it        │
  ├───────────────────────────┼──────────┼────────────┼──────────────────────────────┤
  │ --json on cw9             │ Medium   │            │ Enables richer SSE progress; │
  │ loop/bridge/gen-tests     │ (~60     │ No         │  CW7 can use exit codes +    │
  │                           │ LOC)     │            │ file artifacts without it    │
  ├───────────────────────────┼──────────┼────────────┼──────────────────────────────┤
  │                           │ Small    │            │ register must be idempotent  │
  │ Idempotent registration   │ (~20     │ Yes (per   │ on retry — if criterion_id   │
  │                           │ LOC)     │ review)    │ already mapped to a gwt_id,  │
  │                           │          │            │ reuse it                     │
  └───────────────────────────┴──────────┴────────────┴──────────────────────────────┘

  The Review's Critical Issues — How to Address

  The plan review flagged three critical issues. Here's how the CW9 API extensions resolve
   them:

  1. Missing CW9 behavior identity contract (register_gwt)

  Solved by cw9 register with an idempotency key. The register command should accept a
  criterion_id per GWT and store a criterion_id → gwt_id mapping in .cw9/dag.json (new
  field: "criterion_bindings": {}). On retry, if the binding exists, return the existing
  gwt_id without re-registering.

  2. No deterministic failure-classification table

  This is CW7-side (the adapter classifies CW9 exit codes). But CW9 can help by making
  exit codes more granular:

  ┌───────────┬────────────────┬──────────────────────────┬───────────────────────────┐
  │   Step    │     Exit 0     │          Exit 1          │       Exit 2 (new)        │
  ├───────────┼────────────────┼──────────────────────────┼───────────────────────────┤
  │ register  │ All registered │ Validation error (bad    │ —                         │
  │           │                │ input)                   │                           │
  ├───────────┼────────────────┼──────────────────────────┼───────────────────────────┤
  │ loop      │ PASS           │ Non-convergence (domain) │ Infra failure (LLM        │
  │           │                │                          │ unreachable)              │
  ├───────────┼────────────────┼──────────────────────────┼───────────────────────────┤
  │ bridge    │ Artifacts      │ Missing spec (domain)    │ Parse failure             │
  │           │ written        │                          │                           │
  ├───────────┼────────────────┼──────────────────────────┼───────────────────────────┤
  │ gen-tests │ Test generated │ Domain failure           │ Infra failure             │
  ├───────────┼────────────────┼──────────────────────────┼───────────────────────────┤
  │ test      │ All pass       │ Test failures            │ Infra failure             │
  └───────────┴────────────────┴──────────────────────────┴───────────────────────────┘

  Exit 1 = domain failure → pipeline_partial (terminal). Exit 2 = infra failure →
  pipeline_error (retryable). This maps cleanly to the orchestrator's retry policy.

  3. Integration test verification commands

  CW7-side fix only (use --config vitest.integration.config.ts). No CW9 change.

  Recommended Build Order

  1. cw9 register — JSON stdin/stdout, idempotent with criterion bindings. This unblocks
  Behavior 3 of the TDD plan.
  2. Exit code 2 convention — Distinguish infra vs domain failures across all subcommands.
   This unblocks Behavior 4 (classification matrix).
  3. --context-file on cw9 loop — Enriches verification quality. Not blocking but
  high-value.
  4. --json flag — Progressive enhancement for observability.

  The Full CW7 Adapter Flow (After Extensions)

  // run-cw9-pipeline.ts — the new adapter

  async function runCw9Pipeline(pathFile: string, projectRoot: string):
  Promise<PipelineResult> {
    // 1. Init (idempotent)
    await exec('cw9', ['init', projectRoot, '--force']);

    // 2. Extract DAG from schemas
    await exec('cw9', ['extract', projectRoot]);

    // 3. Register GWTs (JSON stdin/stdout)
    const gwts = await parseGwtsFromPath(pathFile);  // CW7 parses its own spec format
    const { stdout } = await exec('cw9', ['register', projectRoot, '--json'], {
      input: JSON.stringify({ gwts })
    });
    const { registered } = JSON.parse(stdout);

    // 4-7. Per-GWT pipeline
    for (const { gwt_id } of registered) {
      await exec('cw9', ['loop', gwt_id, projectRoot, '--context-file', pathFile]);
      await exec('cw9', ['bridge', gwt_id, projectRoot]);
      await exec('cw9', ['gen-tests', gwt_id, projectRoot, '--lang', targetLang]);
    }

    // 8. Run all tests
    const testResult = await exec('cw9', ['test', projectRoot]);

    // 9. Read bridge artifacts for planning enrichment
    const artifacts = await loadBridgeArtifacts(projectRoot, registered);

    return normalizeResult(testResult, artifacts);
  }

  The library API is already sufficient — the main gap is the register CLI subcommand as a
   machine-readable bridge between CW7's TypeScript and CW9's Python. Everything else is
  subprocess calls + filesystem reads.


# Integration Advisory: CW9 into CW7's /api/chat Pipeline                                 
                                                                                          
  The Problem                                                                             
                                                                                          
  CW7 is a Next.js/TypeScript app with an SSE-driven UI that orchestrates Gates           
  1→GWT→2→Approval→Planning. CW9 is a Python CLI/library that formally verifies GWT       
  behaviors via TLA+/PlusCal and produces bridge artifacts + tests. The question is where 
  and how to wire CW9 into CW7's pipeline.                                                
                                                                                          
  Where CW9 Fits in the Flow

  The natural insertion point is between approval and planning — after the user clicks
  "Start Planning" and POSTs approvals, but before /api/chat runs in plan_path mode:

  POST /api/sessions/{id}/approvals
    → UPDATE acceptance_criteria.approval_status
    → [NEW] For each approved GWT criterion:
        → register_gwt into CW9 DAG
        → cw9 loop (verify)
        → cw9 bridge (artifacts)
        → optionally cw9 gen-tests
    → /api/chat (plan_path) — now with verified bridge artifacts as additional context

  This is correct because:
  - Approved GWTs are the exact input CW9 needs (given, when, then triples)
  - Formal verification adds confidence before expensive planning
  - Bridge artifacts (operations, data structures, verifiers, assertions) enrich the
  planning prompt

  Recommended Approach: CLI Subprocess with Filesystem Handoff

  Use the cw9 CLI via child_process.execFile from CW7's Node.js backend, reading
  structured artifacts from the .cw9/ directory after each command.

  Why this over the alternatives:

  ┌──────────────────────┬────────────────────────────────────────────────────────────┐
  │       Approach       │                          Verdict                           │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ CLI subprocess       │ Simplest. No new services. CW9 is already packaged as a    │
  │ (recommended)        │ cw9 binary. Read .cw9/bridge/*.json and dag.json for       │
  │                      │ structured data.                                           │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ Python HTTP sidecar  │ Premature. Adds deployment complexity. Only justified at   │
  │ (FastAPI)            │ scale or if you need sub-second latency on register_gwt    │
  │                      │ calls.                                                     │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ Library API via      │ Fragile. asyncio.run() inside loop/gen-tests means they    │
  │ Python subprocess    │ can't nest in an existing event loop. The CLI already      │
  │                      │ handles this.                                              │
  └──────────────────────┴────────────────────────────────────────────────────────────┘

  Concrete Integration Steps

  1. Initialize CW9 per project (one-time)

  When a CW7 session first needs verification, initialize the .cw9/ directory in the
  project workspace:

  // In route.ts or a new verification service
  import { execFile } from 'child_process';
  import { promisify } from 'util';
  const exec = promisify(execFile);

  async function ensureCw9Init(projectDir: string): Promise<void> {
    const cw9Dir = path.join(projectDir, '.cw9');
    if (!fs.existsSync(cw9Dir)) {
      await exec('cw9', ['init', projectDir]);
    }
  }

  2. Map approved GWTs from CW7 DB to CW9 DAG

  CW7's acceptance_criteria rows have format='gwt' and contain given/when/then clauses.
  CW9's register_gwt() is a Python-only API — no CLI command for it. Two options:

  Option A: Thin Python registration script (recommended)

  Create a small script CW7 shells out to:

  #!/usr/bin/env python3
  # scripts/register_gwts.py
  import json, sys
  from registry.dag import RegistryDag
  from registry.context import ProjectContext

  def main():
      data = json.loads(sys.stdin.read())
      ctx = ProjectContext.from_target(data["project_dir"])
      dag = RegistryDag.load(ctx.state_root / "dag.json")

      registered = []
      for gwt in data["gwts"]:
          gwt_id = dag.register_gwt(
              given=gwt["given"],
              when=gwt["when"],
              then=gwt["then"],
              parent_req=gwt.get("parent_req"),
          )
          registered.append({"criterion_id": gwt["criterion_id"], "gwt_id": gwt_id})

      dag.save(ctx.state_root / "dag.json")
      json.dump(registered, sys.stdout)

  if __name__ == "__main__":
      main()

  Call from Node.js:

  async function registerGwts(projectDir: string, approvedCriteria: GwtCriterion[]) {
    const input = JSON.stringify({
      project_dir: projectDir,
      gwts: approvedCriteria.map(c => ({
        criterion_id: c.id,
        given: c.given_clause,
        when: c.when_clause,
        then: c.then_clause,
        parent_req: c.requirement_id ? `req-${c.requirement_id}` : undefined,
      })),
    });

    const { stdout } = await exec('python3', ['scripts/register_gwts.py'], { input });
    return JSON.parse(stdout); // [{criterion_id, gwt_id}, ...]
  }

  Option B: Add a cw9 register CLI subcommand to CW9 that reads GWTs from stdin as JSON
  and writes registered IDs to stdout. This is the cleaner long-term solution.

  3. Run verification + bridge per GWT

  After registration, run the pipeline for each GWT. These are the slow steps (LLM + TLC),
   so emit SSE progress:

  async function verifyCriteria(
    projectDir: string,
    gwtMappings: Array<{criterion_id: string, gwt_id: string}>,
    emitSSE: (event: string, data: any) => void,
  ) {
    for (const { criterion_id, gwt_id } of gwtMappings) {
      emitSSE('verification_progress', { criterion_id, gwt_id, status: 'verifying' });

      // Verification loop (LLM → PlusCal → TLC, up to 5 retries)
      const loopResult = await exec('cw9', ['loop', gwt_id, projectDir, '--max-retries',
  '5'],
        { timeout: 600_000 });  // 10min timeout

      if (loopResult.exitCode !== 0) {
        emitSSE('verification_progress', { criterion_id, gwt_id, status: 'failed' });
        continue; // or throw, depending on policy
      }

      // Bridge: translate verified spec → structured artifacts
      await exec('cw9', ['bridge', gwt_id, projectDir]);

      // Read the bridge artifacts for downstream use
      const artifactPath = path.join(projectDir, '.cw9', 'bridge',
        `${gwt_id}_bridge_artifacts.json`);
      const artifacts = JSON.parse(fs.readFileSync(artifactPath, 'utf-8'));

      emitSSE('verification_progress', {
        criterion_id, gwt_id, status: 'verified',
        operations: Object.keys(artifacts.operations).length,
        verifiers: Object.keys(artifacts.verifiers).length,
      });
    }
  }

  4. Feed bridge artifacts into planning

  The biggest payoff: when CW7 runs /api/chat in plan_path mode, augment the planning
  prompt with CW9's verified artifacts. Bridge artifacts contain:

  - data_structures — verified state variables with types and defaults
  - operations — TLA+ actions mapped to function signatures
  - verifiers — invariants the implementation must satisfy
  - assertions — concrete assertion conditions
  - simulation_traces — concrete state sequences (gold for test planning)

  // In the plan_path handler, after loading approved criteria
  const bridgeContext = await loadBridgeArtifacts(projectDir, gwtMappings);

  // Inject into the planning system prompt
  const enrichedPrompt = `
  ${existingPlanningPrompt}

  ## Formally Verified Specifications

  The following GWT behaviors have been formally verified via TLA+ model checking.
  Use these verified operations and invariants to guide implementation planning.

  ${bridgeContext}
  `;

  5. Optional: test generation

  cw9 gen-tests can produce tests in Python, TypeScript, Rust, or Go — matching CW7's tech
   stack recommendations from Gate 2:

  // After planning, optionally generate tests for the target language
  const lang = gate2Output.recommended_language; // from Gate 2
  await exec('cw9', ['gen-tests', gwtId, projectDir, '--lang', lang]);

  Data Flow Diagram

  CW7 Pipeline                           CW9 Pipeline
  ━━━━━━━━━━━━                           ━━━━━━━━━━━━
  User Prompt
    │
    ├─ Gate 1 (requirements)
    ├─ GWT decompose (per req)
    ├─ Gate 2 (tech stack)
    │
    ▼
  Review & Approve GWT ─────────────────► register_gwt() → DAG
    │                                        │
    │                                     cw9 loop → .tla spec
    │                                        │
    │                                     cw9 bridge → bridge_artifacts.json
    │                                        │
    │  ◄─────────────────────────────────── artifacts (operations, verifiers,
    │                                        assertions, sim traces)
    ▼
  Planning (plan_path) ← enriched with verified specs
    │
    ▼
  [Optional] cw9 gen-tests ──────────────► test files

  Key Decisions to Make

  1. Blocking vs async verification: The cw9 loop step can take 1-10 minutes per GWT (LLM
  calls + TLC). You probably want to run verifications in parallel and stream progress via
   SSE rather than blocking the UI.
  2. Failure policy: If verification fails for a GWT after max retries, do you skip it
  during planning (degraded mode) or block the whole pipeline? I'd recommend degraded mode
   — mark it as "unverified" and let planning proceed with whatever was verified.
  3. Project directory: CW7 needs a filesystem location for .cw9/ state. Options: temp
  directory per session, or a persistent workspace directory keyed by session_id.
  4. cw9 register subcommand: Adding a register CLI command to CW9 that accepts GWTs as
  JSON stdin and emits registered IDs as JSON stdout would eliminate the need for the
  register_gwts.py helper script. This is a small, clean addition.
  5. Schema bootstrapping: CW9's init copies starter schemas. For CW7 integration, you'd
  likely want to generate schemas from Gate 1's requirements output rather than using
  starter templates. This could be a new cw9 init --from-gate1 <json> mode or a library
  API call.

  What I'd Build First

  The minimum viable integration:

  1. Add cw9 register subcommand (JSON stdin → JSON stdout)
  2. In CW7's approval handler, after persisting approvals:
    - cw9 init (if needed)
    - cw9 register (pipe approved GWTs)
    - cw9 loop + cw9 bridge per GWT (parallel, with SSE progress)
  3. Read .cw9/bridge/*.json artifacts
  4. Inject bridge context into the plan_path system prompt

  This keeps both codebases clean, uses the filesystem as the integration contract, and
  doesn't require a new service.

# CW9 → CW7 Integration Advisory                                                          
                                                                                          
  The Natural Fit                                                                         
                                                                                          
  CW7 and CW9 have a clean hand-off point. CW7 produces exactly what CW9 consumes:

  ┌────────────────────────────────┬────────────────────────────┬─────────────────────┐
  │           CW7 Output           │         CW9 Input          │ Mapping Complexity  │
  ├────────────────────────────────┼────────────────────────────┼─────────────────────┤
  │ Gate 1 GWT criteria            │ dag.register_gwt(given,    │ Low — direct field  │
  │ (acceptance_criteria table)    │ when, then)                │ mapping             │
  ├────────────────────────────────┼────────────────────────────┼─────────────────────┤
  │ Gates 6-9 schemas (backend,    │                            │ Medium — format     │
  │ frontend, middleware, shared)  │ .cw9/schema/*.json files   │ normalization       │
  │                                │                            │ needed              │
  ├────────────────────────────────┼────────────────────────────┼─────────────────────┤
  │ Gate 2 tech stack              │ CW9 config.toml / language │ Low — drives --lang │
  │                                │  selection                 │  flag               │
  └────────────────────────────────┴────────────────────────────┴─────────────────────┘

  Recommended Integration Point

  After GWT approval, before or parallel to plan path generation:

  Gate 1 → GWT Decompose → User Approval
                                │
                      ┌─────────┴──────────┐
                      │                    │
                Plan Path Gen        CW9 Pipeline
                (existing)           (new integration)
                      │                    │
                      │              cw9 extract
                      │              cw9 loop (verify)
                      │              cw9 bridge
                      │              cw9 gen-tests
                      │                    │
                      └─────────┬──────────┘
                                │
                      Implementation Phase
                      (code + verified tests)

  This is the right spot because:
  1. GWTs are finalized (user-approved) — no wasted verification on rejected criteria
  2. Gate 2 tech stack is known — drives --lang for test generation
  3. Can run parallel to plan path generation (independent concerns)
  4. Tests are ready when implementation begins

  Integration Architecture

  Invocation: Subprocess (not library import)

  Use cw9 as a binary subprocess, not a Python import. Reasons:
  - CW7 is TypeScript/Next.js — can't import Python modules directly
  - CW9 is designed as a CLI tool with clean stdin/stdout contract
  - Subprocess model keeps the systems decoupled and independently versionable
  - CW9's uv tool install packaging supports this well

  Concrete Integration Steps:

  1. Schema Export (CW7 → CW9)

  CW7 Gate 6-9 outputs are stored as JSON blobs in gate_outputs. You need a translation
  layer:

  // New: frontend/src/lib/cw9-bridge.ts
  async function exportSchemasForCW9(sessionId: string, targetDir: string) {
    const cw9Dir = path.join(targetDir, '.cw9');

    // Initialize CW9 project if needed
    await execFile('cw9', ['init', targetDir]);

    // Map CW7 gate outputs → CW9 schema files
    const gateMap = {
      6: 'shared_objects_schema.json',
      7: 'backend_schema.json',
      8: 'frontend_schema.json',
      9: 'middleware_schema.json',
    };

    for (const [gate, filename] of Object.entries(gateMap)) {
      const output = await loadGateOutput(sessionId, Number(gate));
      if (output) {
        const cw9Schema = transformToCW9Format(output, filename);
        await fs.writeFile(path.join(cw9Dir, 'schema', filename),
  JSON.stringify(cw9Schema));
      }
    }
  }

  Key concern: The schema formats differ. CW7 gates produce BAML-typed outputs
  (requirements, function maps, data flows). CW9 expects resource-registry-style JSON with
   UUIDs, function signatures, imports, and dependencies. You'll need a format transformer
   — this is the most significant piece of integration work.

  2. GWT Registration (CW7 → CW9 DAG)

  async function registerApprovedGWTs(sessionId: string, targetDir: string) {
    const criteria = await loadApprovedCriteria(sessionId);

    for (const c of criteria) {
      // CW9's DAG API is file-based — load, mutate, save
      // Alternatively, expose a cw9 CLI command for GWT registration
      await execFile('cw9', ['register-gwt',
        '--given', c.given_clause,
        '--when', c.when_clause,
        '--then', c.then_clause,
        '--parent', c.requirement_id,
        targetDir
      ]);
    }
  }

  Note: CW9 currently lacks a register-gwt CLI command — GWT registration is library-only
  (dag.register_gwt()). You'll want to add this subcommand to cli.py.

  3. Pipeline Execution

  async function runCW9Pipeline(gwtId: string, targetDir: string, lang: string) {
    // Each step is sequential and depends on prior output
    await execFile('cw9', ['extract', targetDir]);
    await execFile('cw9', ['loop', gwtId, targetDir, '--max-retries', '5']);
    await execFile('cw9', ['bridge', gwtId, targetDir]);
    await execFile('cw9', ['gen-tests', gwtId, targetDir, '--lang', lang]);
  }

  4. SSE Progress Reporting

  CW9 currently prints to stdout. For CW7 UI integration, you need structured progress.
  Two options:

  - Option A (simpler): Parse CW9 stdout line-by-line, emit SSE events from the CW7 route
  handler. Works with existing CW9.
  - Option B (cleaner): Add --json-progress flag to CW9 that emits structured JSON lines
  ({"stage": "loop", "attempt": 2, "status": "compiling"}). Better long-term.

  What CW9 Needs to Support This

  Changes required in this (CW9) codebase:

  1. register-gwt CLI subcommand — Currently GWT registration is library-only. Add a CLI
  command that accepts --given, --when, --then, --parent args and calls
  dag.register_gwt().
  2. Schema format compatibility — CW9 schemas use a specific resource-registry format
  with UUIDs. Either:
    - Add a CW9 import-schema command that accepts CW7's gate output format
    - Or document the exact schema transformation CW7 must perform
  3. Structured progress output — Add --json-progress or --machine-readable flag that
  emits JSON-lines progress instead of human-readable text. This lets CW7's SSE layer
  relay progress to the browser.
  4. Non-interactive exit codes — Ensure all commands return clean exit codes (0 =
  success, 1 = verification failed, 2 = compilation error, etc.) for CW7 to handle
  programmatically.

  What CW7 Needs

  1. CW9 bridge module (frontend/src/lib/cw9-bridge.ts) — Schema export, GWT registration,
   pipeline orchestration
  2. Schema transformer — CW7 gate output → CW9 schema format mapping
  3. New SSE event types — cw9_verification_start, cw9_verification_complete,
  cw9_test_generated, etc.
  4. UI panel — Display CW9 verification status and generated tests alongside plan paths
  5. New mode in /api/chat route — mode='verify' or extend plan_path mode to include CW9
  invocation

  Risks and Considerations

  1. Schema format gap is the biggest integration risk. CW9's resource-registry format
  (with UUIDs, function signatures, imports) is structurally different from CW7's gate
  outputs. This transformer needs careful design and testing.
  2. cw9 loop is slow — LLM call + PlusCal compilation + TLC model checking can take
  minutes per GWT. Plan for async/parallel execution and timeout handling.
  3. TLA+ toolchain dependency — CW9 bundles tla2tools.jar (requires JRE). CW7's
  deployment environment must have Java available.
  4. Failure modes — Formal verification can genuinely fail (spec inconsistency). CW7
  needs UI to surface verification failures and let users decide how to proceed (skip,
  retry, edit GWT).

  Recommended Implementation Order

  1. Add register-gwt CLI command to CW9 (small, unblocks everything)
  2. Add --json-progress output to CW9 commands (enables SSE relay)
  3. Build the schema format transformer (biggest piece — design first)
  4. Build CW7's cw9-bridge.ts orchestration module
  5. Add SSE events and UI components in CW7
  6. End-to-end integration testing

  Shall I start implementing any of these CW9-side changes (the register-gwt command or
  --json-progress output)?



# The core problem with few-shot from the oracle is that the LLM sees finished tests and  
  copies the topology/assertions rather than deriving them from bridge data. The question 
  is: what context makes the LLM generate tests that are as good as the oracle but derived
   from the artifacts?
                                                                                          
  The answer is TLC simulation traces.                                                  

  The insight

  When TLC verifies a model with 762 distinct states and passes, it has visited every
  reachable state and confirmed every invariant holds at each one. We currently throw all
  of that away — we capture "pass" and a state count. That's an enormous waste.

  TLC has a -simulate mode that outputs concrete execution traces through the state space,
   even on passing models. Each trace is:

  State 1: <Init>
    /\ current_state = "idle"
    /\ candidates = {}
    /\ affected = {}
    /\ test_artifacts = {"a" :> "test_a.py", "b" :> "test_b.py"}
    /\ adj = {"a" :> {"b"}, "b" :> {"c"}}

  State 2: <SelectNode>
    /\ current_state = "propagating"
    /\ start = "c"
    ...

  State 3: <ComputeAffected>
    /\ affected = {"a", "b", "c"}
    /\ candidates = {"a", "b"}
    ...

  These traces ARE the test cases. Each one says: "starting from THIS state, applying
  THESE actions, produces THIS result, and ALL invariants hold." The LLM's job shifts
  from:

  - Hard: "Design test scenarios for NoFalsePositives" (creative, needs domain reasoning)
  - Easy: "Translate this concrete state trace into Python API calls" (mechanical,
  verifiable)

  The context stack

  Ranked by impact:

  1. TLC simulation traces (primary — the WHAT)

  ## Concrete Verified Scenarios

  Trace 1 (5 steps, tests NoFalsePositives + ValidState):
    Init: nodes={a,b,c,d}, edges={a→b, b→c, c→d}, test_artifacts={a:"test_a.py",
  c:"test_c.py"}
    Action: query_affected_tests("d")
    Result: affected={"test_a.py", "test_c.py"}
    Invariants verified: NoFalsePositives ✓, NoFalseNegatives ✓, SelfTestIncluded ✓

  Trace 2 (3 steps, tests isolated node):
    Init: nodes={x}, edges={}, test_artifacts={x:"test_x.py"}
    Action: query_affected_tests("x")
    Result: affected={"test_x.py"}
    ...

  10 traces from -simulate num=10 gives the LLM concrete input/output pairs. It doesn't
  need to invent topologies — TLC already explored the state space and found interesting
  ones.

  2. Python API source code (the HOW)

  The LLM must see the implementation to bind traces to API calls:

  # From dag.py:242-259
  def query_affected_tests(self, node_id: str) -> list[str]:
      ...

  Plus return types, parameter types, the RegistryDag constructor, add_node/add_edge
  signatures. Without this, the LLM guesses at method signatures.

  3. GWT text + bridge artifacts with compiled hints (the WHY)

  ## Behavioral Requirement
  Given: a registry DAG with test artifact mappings
  When: a node is modified
  Then: all tests affected by the change are identified

  ## Invariant Translations (compiler output — starting points, not final assertions)
    NoFalsePositives: TLA+ `\A t \in affected : t \in candidates` ≈ Python `all(t in
  candidates for t in affected)`
    NoFalseNegatives: TLA+ `\A n \in candidates : test_artifacts[n] \in result` ≈ Python
  `all(test_artifacts[n] in result for n in candidates)`

  The compiled expressions give the LLM a head start on the assertion logic. The GWT text
  grounds the intent.

  4. The verified TLA+ spec (the FULL PICTURE)

  The raw .tla file. The LLM can read TLA+ — it generated it in the first place. The spec
  contains the complete state machine: variable types, init predicate, next relation,
  invariant definitions. The bridge artifacts are a lossy projection; the spec is
  lossless.

  5. Decomposed structural patterns (the FORM)

  NOT the full oracle files. Instead, extract three generic patterns:

  # Pattern: fixture construction (generic)
  def _make_dag(nodes, edges, artifacts):
      dag = RegistryDag()
      for nid in nodes:
          dag.add_node(Node.behavior(nid, nid, "g", "w", "t"))
      for src, dst in edges:
          dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))
      dag.test_artifacts = artifacts
      return dag

  # Pattern: invariant verification (generic)
  def test_invariant(dag):
      result = dag.some_query("node_id")
      assert property_of(result)

  # Pattern: error case (generic)
  def test_invalid_input(dag):
      with pytest.raises(NodeNotFoundError):
          dag.some_query("nonexistent")

  These teach form without leaking module-specific content.

  What NOT to pass

  - Full oracle test files — the LLM will copy topologies instead of deriving from traces
  - The project DAG — fixtures should be self-contained, not coupled to project state
  - All bridge artifacts unfiltered — operations and data_structures are noisy; traces are
   the better input for scenario design

  The engineering delta

  This changes Phase 5A from "connect CounterexampleTrace to TlcTrace" to something more
  significant:

  1. Modify run_tlc() to run -simulate num=10 on passing models and capture output
  2. Extend the trace parser to handle simulation traces (same format as counterexamples,
  minus the violation)
  3. Convert simulation traces to structured data — state sequences with variable bindings
  4. Build the prompt assembler that combines: traces + API source + GWT + bridge hints +
  patterns

  The key shift: TLC goes from a pass/fail gate to a test case generator. The formal
  verification doesn't just prove correctness — it produces the concrete scenarios that
  become Python tests.



#  Issue 1: Node.requirement() signature mismatch (Phase 0)

  The plan's register_requirement() calls Node.requirement(req_id, name, text) with 3
  args, but the actual factory is Node.requirement(id: str, text: str) — 2 args, no name 
  param. The name is hardcoded to "" inside the factory. Either:
  - Change register_requirement() to not pass name, or
  - Modify Node.requirement() to accept an optional name param (small types.py change)

  The tests at lines 290-308 will also need updating — Node.requirement(f"req-{i:04d}",
  f"r{i}", f"text{i}") passes 3 args to a 2-arg method.

  Issue 2: cw9 extract overwrites registered GWTs (Phase 2)

  The plan acknowledges this at line 466 but hand-waves it: "A future enhancement could
  merge..." This is a real problem. The workflow register_gwt() → extract → loop will
  destroy the registered GWTs because extract rebuilds from schemas. The fix is simple:
  load the existing DAG, extract a fresh one, merge registered GWTs (nodes with gwt-
  prefix that aren't in the extracted DAG) back in. This should be Phase 2, not "future."

  Issue 3: loop_runner.py uses process_response wrong (Phase 3)

  The plan shows status = loop.process_response(response, gwt_id) but process_response
  returns self.status which is a LoopStatus. The plan then checks status.result ==
  LoopResult.PASS — this is correct. But status.retry_prompt (line 650) — does LoopStatus 
  have a retry_prompt field? This needs verification. The existing loop scripts build
  retry prompts manually from counterexample output, not from a field on LoopStatus.

DAG registration just means: take one of those given/when/then objects and give it a    
  permanent address in the project's dependency graph.                                    
                                                                                          
  Right now that JSON array has four behaviors — fund the escrow, approve a milestone,
  reject a milestone, close the escrow. They're just floating descriptions. The system    
  doesn't know they exist, can't track them, can't tell you what depends on what.

  Registration means:
  - Assign each one an ID (gwt-0024, gwt-0025, gwt-0026, gwt-0027)
  - Add it as a node in the graph
  - Connect it to the requirement it came from (e.g., "gwt-0024 belongs to req-0008:
  construction escrow")
  - Now every downstream step can refer to it by ID — the TLC verifier knows what to
  check, the bridge knows what traces to extract, the test generator knows what to produce

  It's like checking into a hotel. You show up as "person with a suitcase." Registration
  gives you a room number. Now housekeeping, room service, and checkout all know where to
  find you.

  Without registration, the pipeline has no way to say "run the formal verification for
  the milestone approval behavior" — it doesn't know that behavior exists yet.




# Help me think ahead. There are 2 common use cases: 1. greenfield project, external to   
this repo and 2. brownfield project, external to this project.                            
We will need a way to "point" CW9 at the external repo, maintain state, persist sessions, 
 and write code from this repo - or - we package a globally available binary to invoke in 
 the target repo.  The CW9 code will also need to be able to locate files in the external 
 repo.                                                                                    
                                                                                          
● Good timing to think about this. Let me break it down.                                  
                                                                                          
  The Core Problem                                                                        
   
  Right now CW9 is solipsistic — every path, every schema, every DAG reference assumes    
  it's operating on itself. To work on external repos, you need to solve five things:

  1. Project root — where is the target code?
  2. CW9 state — where do schemas, DAG, specs, bridge artifacts live?
  3. Session continuity — handoffs, pipeline history, retry context
  4. Code targeting — generated tests and implementations land in the right place
  5. Codebase ingestion — how does the DAG get populated for a foreign project?

  Two Deployment Models

  Model A: "Point At" (CW9 stays home)

  CW9 repo is the tool. External project is a target path. State lives in CW9 under
  something like projects/<name>/.

  CodeWriter9.0/
    projects/
      my-saas-app/
        schema/          ← schemas for the external project
        registry_dag.json
        templates/pluscal/instances/
        bridge_artifacts/
        sessions/
      another-project/
        ...
    python/registry/     ← CW9 engine code

  Pros: Single source of truth, easy to compare projects, no installation step.
  Cons: Path management nightmare. Every tool (extractor.py, one_shot_loop.py, bridge.py)
  takes project_root today but assumes schemas are in that root. You'd need to split
  "where is CW9 engine code" from "where is the target project" from "where is CW9 state
  for this project." That's three roots, not one.

  Model B: CLI binary, state in target repo

  CW9 packages as a CLI tool. Target repo gets a .cw9/ directory (like .git/). The tool
  runs in the target repo's context.

  my-saas-app/              ← target repo
    .cw9/
      schema/               ← project schemas
      dag.json              ← registry DAG
      specs/                ← TLA+ instances
      bridge/               ← bridge artifacts
      sessions/             ← handoffs, loop history
      config.toml           ← project-level settings
    src/                    ← their code
    tests/                  ← where generated tests land

  Pros: Clean separation. State travels with the project. Multiple developers can use CW9
  on the same repo. Standard CLI ergonomics (cw9 init, cw9 extract, cw9 verify, cw9
  bridge).
  Cons: Packaging and distribution. The Rust crate helps here — crates/registry-core/
  could become the binary, with Python as an embedded runtime or subprocess.

  My Recommendation: Model B, but staged

  Model B is the right end state, but you don't need to package a binary to start. The
  staging:

  Stage 1 — Decouple paths (do this now, in-repo). Every component that uses PROJECT_ROOT
  or hardcoded paths needs a config object:

  @dataclass
  class ProjectContext:
      target_root: Path      # where the external code lives
      state_root: Path       # where .cw9/ state lives (usually target_root/.cw9)
      schema_dir: Path       # state_root/schema
      spec_dir: Path         # state_root/specs
      artifact_dir: Path     # state_root/bridge
      test_output_dir: Path  # target_root/tests/generated (or configurable)

  This is the foundational refactor. Currently SchemaExtractor, OneShotLoop,
  run_*_loop.py, and bridge.py all assume paths relative to a single root.

  Stage 2 — cw9 init for greenfield. Creates .cw9/ in target repo, generates starter
  schemas from a template. The 4 schema files (backend, frontend, middleware, shared) get
  created with empty structures. User fills them in, or an ingestion step helps.

  Stage 3 — cw9 ingest for brownfield. This is the hard one. You need to scan an existing
  codebase and populate schemas. Options:
  - LLM-assisted: point at a directory, LLM reads code, proposes schema entries
  - Convention-based: scan for known patterns (Express routes → endpoints, SQLAlchemy
  models → data structures)
  - Manual: user writes schemas by hand, CW9 validates

  Stage 4 — Package as CLI. Rust binary wraps the Python engine. cargo install cw9 or a
  standalone binary.

  The Greenfield vs Brownfield Split

  Greenfield is easier — the pipeline works as-is. User writes requirements in plain
  language, pipeline generates specs, verifies, generates tests, user implements. The only
   missing piece is ProjectContext so files land in the right place.

  Brownfield is fundamentally different. You're not building forward from requirements —
  you're building backward from existing code. The pipeline's Phase 0 (extraction)
  currently reads schemas that describe the code. For a brownfield project, someone has to
   create those schemas from the existing codebase. That's either a manual effort or a
  separate ingestion pipeline.

  What to Build Next

  The ProjectContext refactor is the prerequisite for both use cases and both deployment
  models. It's also a good pipeline candidate — you could express it as GWT behaviors
  ("given a project context pointing to an external directory, when extract is called,
  then schemas are read from the state root, not the CW9 root").

  Want to scope that as the next pipeline feature, or think through the
  packaging/distribution question more first?

# Here is the scope:
The coupling surface is narrower than the LLM suggested — it's essentially one    
  anchor (PROJECT_ROOT) with known relative paths below it. Here's how I'd scope          
  packaging:                                                                              
                                                                                          
  Packaging Scope: What You Actually Need                                                 
                                                                                          
  The path analysis shows three distinct path concerns, not five:                         
                                                                                          
  1. Engine root — where CW9's own code lives (templates, tla2tools.jar, bridge logic)    
  2. Target root — where the external project's source code lives
  3. State root — where the DAG, schemas, specs, and artifacts live for that project

  Today all three are the same directory. Decoupling them is the prerequisite for
  everything.

  Staged Plan

  Stage 0: ProjectContext dataclass (the real work)

  @dataclass
  class ProjectContext:
      engine_root: Path   # CW9 install location (templates, tools, python/registry)
      target_root: Path   # external project's root
      state_root: Path    # target_root/.cw9 by default

      # Derived (all under state_root)
      schema_dir: Path
      spec_dir: Path
      artifact_dir: Path
      session_dir: Path

      # Under target_root
      test_output_dir: Path

  What changes:
  - SchemaExtractor.__init__ — already takes schema_dir, just pass ctx.schema_dir
  - OneShotLoop — takes project_root, split into ctx.engine_root (for template reads) and
  ctx.state_root (for spec writes)
  - _find_tla2tools — looks in ctx.engine_root / "tools" instead of PROJECT_ROOT / "tools"
  - Loop scripts — the big surface area (all those PROJECT_ROOT / ... joins). Each gets a
  ProjectContext instead of computing PROJECT_ROOT
  - Node path= strings in _self_describe — these are metadata for CW9's own DAG, leave
  them as-is. External projects get their own DAG with their own paths.

  What doesn't change:
  - dag.py, bridge.py, composer.py, types.py — no hardcoded paths, already clean
  - Rust crate — no paths at all
  - pyproject.toml — stays as-is, pytest config is per-project

  This is ~6 files touched, mostly the 5 loop scripts + one_shot_loop.py. The registry
  core is already decoupled.

  Stage 1: cw9 init

  A script (not yet a binary) that creates .cw9/ in a target directory:

  cw9 init /path/to/my-project

  Creates:
  my-project/.cw9/
    config.toml      # engine_root = "/path/to/CodeWriter9.0"
    schema/           # empty starter schemas
    dag.json          # empty DAG
    specs/            # TLA+ instances will go here
    bridge/           # bridge artifacts will go here
    sessions/         # handoffs and loop logs

  Greenfield starts here. User writes schemas (or Stage 2 helps them).

  Stage 2: cw9 ingest (brownfield)

  This is the hard problem and can be deferred. For now, brownfield = "user writes schemas
   by hand, CW9 validates them." The pipeline already handles everything after schemas
  exist.

  Stage 3: CLI binary

  Wrap with a thin entry point. Could be a Python CLI (click or argparse) first, Rust
  binary later. The Rust crate already has the DAG engine — but the pipeline (LLM calls,
  TLC invocation, bridge) is all Python today, so a Python CLI is the pragmatic first
  step.

  What I'd Build Next

  Stage 0 only. The ProjectContext refactor. It's a pipeline candidate — you can express
  it as GWT behaviors:

  - gwt-0024: Given a ProjectContext pointing to an external directory, when
  SchemaExtractor runs, schemas are read from state_root/schema
  - gwt-0025: Given a ProjectContext, when the loop runs, specs are written to
  state_root/specs, not engine_root
  - gwt-0026: Given a ProjectContext, when bridge generates tests, they land in
  target_root/tests/generated

  That's req-0008, 3 GWT behaviors, one pipeline run. The implementation is a refactor of
  existing code, not new functionality — but it's verified refactoring.

  Stage 1 (cw9 init) follows naturally once ProjectContext exists. Stages 2-3 are separate
   decisions.

















What's Correct
                                                                                          
  The CSP framing is right. The nested loop problem IS arc-consistency propagation. CW7's
  current architecture — verify path A, verify path B, discover A conflicts with B,
  re-verify A, discover that breaks C — has no convergence guarantee. The
  buildDependencyContext() function in CW7's path-reviewer.ts tries to surface sibling
  path info, but it's textual and informational only. The LLM reviewer can see "path-B
  also uses db-5kft" but can't enforce consistency. This is exactly stochastic local
  search on a CSP.

  The O(n²) → O(n) claim is correct IF the monotonic growth property holds. More on this
  below.

  The TLA+ composition formula is mechanically correct. Init_composed = Init_A ∧ Init_B,
  Next_composed as interleaved disjunction with UNCHANGED private vars — this is standard
  TLA+ composition. The per-path-schema-binding-model.md already demonstrates this
  pattern: it models PATHS={p1,p2,p3} with MutualExclusionInv and RegistryMonotonic as
  cross-path invariants. 4,840 states, 3,337 distinct, all 10 properties passed. That's a
  working proof-of-concept.

  The one-shot-with-replay pattern matches the existing cage architecture. Your
  formalization doc already describes the 3-layer cage (locked signature → drift
  correction → compile+test). This output extends the same pattern to TLA+ authorship:
  one-shot, deterministic check, counterexample-as-editing-context on failure. The dhe/9v8
   epic tracks exactly this shift.

  The GWT → TLA+ mapping is clean. Given → Init, When → Action, Then → Invariant. This is
  sound and matches how per-path-schema-binding-model.md was built.

  What Needs Scrutiny

  1. "Monotonic growth — nodes are never deleted, only superseded. Once a behavior's spec
  passes, it's never invalidated by later behaviors."

  This is the central claim and it's not unconditionally true. The
  per-path-schema-binding-model.md proves this for a specific case: RegistryMonotonic
  (INV-9) guarantees |registry'| >= |registry|. But monotonic growth of the registry is
  not the same as monotonic validity of composed specs.

  Consider: behavior A passes against the composed spec. Behavior B is added. B introduces
   a new resource constraint. The composed spec now includes Invariant_B. It's possible
  that the interleaving of A's actions with B's actions violates Invariant_B — even though
   A passed before B existed.

  The document says "compose(compose(A,B), C) = compose(A, compose(B,C))" — associativity.
   This is true for the syntactic composition (Init/Next/Invariant conjunction). But TLC
  satisfaction is NOT associative in the same way. A passing compose(A,B) and B passing
  compose(B,C) does NOT guarantee A passes compose(A,B,C). The new invariant from C might
  constrain A's state space.

  The fix is straightforward but must be stated explicitly: when a new behavior joins a
  connected component, re-verify the entire component's composed spec, not just the new
  behavior against the existing composition. The document's "Handling Late-Discovered
  Dependencies" section says "re-verify only the affected subgraph" — this is correct, but
   the affected subgraph is the entire connected component, not just the new edges.

  2. "Gates 1 and 2 collapse into Ingest."

  This is aspirational, not yet real. CW7's Gate 1 (requirement decomposition into GWT)
  and Gate 2 (techstack selection) produce structured JSON that downstream gates consume.
  CW8.1's equivalent is the session loop (parse_prompt → GWT → schema mutations) plus
  silmari.toml config. Collapsing these into a single LLM call means that single call must
   produce:
  - Parsed requirements
  - GWT decomposition per requirement
  - Techstack decisions
  - Resource identification with UUIDs
  - Registry edges (decomposes, references, constrains)

  That's a lot of structured output for one shot. The current system uses 4 parallel
  extractors (extract_entities, extract_operations, extract_relationships,
  extract_constraints) because splitting improves accuracy. A single ingest call would
  need to be rigorously tested against the same quality bar.

  3. "Bridge — Mechanical translation, no LLM."

  This is the constrained-domain promise: if the spec is complete (all 6 axes determined),
   the translation is mechanical. Your formalization doc's completeness formula covers
  this. But today, CW8.1's fill_function_bodies() still uses the LLM for function body
  generation — because function bodies are the one place where the spec isn't fully
  determined (it specifies contracts, not implementations).

  The Bridge stage as described would need to produce: data models (mechanical from
  types), function signatures (mechanical from schema), and test assertions (mechanical
  from invariants + contracts). This is achievable. But the Implement stage still needs
  the LLM for bodies. The document correctly shows "1 per module" LLM calls at Implement.
  So the claim isn't "no LLM after Bridge" — it's "no LLM at Bridge." That's accurate.

  4. "Don't use full TLA+. Use PlusCal state machines."

  Pragmatically sound for the 80% case. But there's a tension: PlusCal compiles to TLA+
  and the composition formula (Init_A ∧ Init_B, interleaved Next) operates at the TLA+
  level, not PlusCal. You can't compose two PlusCal algorithms directly — you compose
  their TLA+ translations. This means the LLM needs to understand both layers, or the
  templates need to handle composition at the TLA+ level while the LLM fills in
  PlusCal-level state machines. The per-path-schema-binding-model.md example was authored
  directly in TLA+ concepts, not PlusCal. The templates approach could bridge this, but
  it's a design decision that needs to be made explicit.

  5. The verification spectrum timing estimates are optimistic.

  "Bounded TLC (depth 5) ~1s" — this depends entirely on state space. The
  per-path-schema-binding-model.md with 3 paths, 3 resources, MAX_PROPOSED=2 produced
  4,840 states. That's trivial. But 55+ paths share db-5kft. Even with connected-component
   decomposition, a component with 10 paths and 5 shared resources at depth 5 could blow
  up. The funnel architecture from your formalization doc (static classification →
  predicate composition → composed TLC) is the right mitigation, but the timing claims
  need to come from measurement, not estimation.

  What's Missing From This Output

  The connected-component extraction algorithm. The document says "Registry dependency
  graph → connected components → each gets a composed TLA+ spec." But the resource
  registry today doesn't track which paths share which resources in a way that produces
  connected components. The history.jsonl tracks resources per path, and paths reference
  resources by UUID — so the data exists to build the bipartite graph (paths ↔ resources)
  and extract connected components. But no code does this yet.

  The template library. "CRUD, state machine, queue/pipeline, auth/session patterns that
  the LLM fills in rather than writing from scratch" — this is referenced but not defined.
   The /extract_tlaplus_model command gives example invariant patterns (ResourceSafety,
  MonotonicProgress, BalanceNonNegative, RetryBound) but not full composable templates.
  This is a concrete deliverable that would need to be built.

  The transitive closure table. "O(1) dependency queries" requires materialized transitive
   closure. CW8.1's schema_store.rs builds a dependency graph (858 lines) and runs Kahn's
  algorithm for cycle detection, but doesn't precompute transitive closure. SQLite's
  recursive CTEs could do this (WITH RECURSIVE), but it's not implemented.

  Bottom Line

  The architecture described here is sound and represents a genuine simplification over
  CW7's 9-gate pipeline. The key risk is the monotonic validity assumption — you need
  full-component re-verification when new behaviors join, not just incremental checking.
  The one-shot-with-replay pattern is the right LLM interaction model. The philosophical
  point at the end — "the TLA+ spec IS the understanding" — is the correct framing and
  aligns with your constrained-domain thesis.

  The most valuable next step would be building the connected-component extractor from the
   existing resource registry data, because that's the structural prerequisite for
  everything else in this pipeline.
