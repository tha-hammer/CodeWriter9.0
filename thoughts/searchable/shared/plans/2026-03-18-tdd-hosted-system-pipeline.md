---
date: 2026-03-18T16:35:00Z
researcher: Claude Code (claude-opus-4-6)
git_commit: 3b62041
branch: hosted-system-pipeline
repository: CodeWriter9.0
topic: "Hosted System Pipeline TDD Plan"
tags: [plan, tdd, cw9, hosted, architecture, api, worker, pipeline, postgres]
status: review
last_updated: 2026-03-18
last_updated_by: Claude Code (claude-opus-4-6)
cw9_project: python/registry
research_doc: thoughts/searchable/shared/research/2026-03-18-hosted-system-pipeline.md
---

# Hosted System Pipeline — TDD Implementation Plan

## Overview

Map the CW9 CLI pipeline (`init/extract/loop/bridge/gen-tests/test`) into a hosted 3-plane system (control plane, execution plane, data plane) where pipeline stages become asynchronous jobs backed by Postgres metadata, object storage artifacts, and a job queue.

The verified TLA+ specs and simulation traces produced by the CW9 pipeline define exactly what data structures, operations, and invariants the hosted system must satisfy. This plan derives every implementation step from those formally verified artifacts.

## Research Reference

- Research doc: `thoughts/searchable/shared/research/2026-03-18-hosted-system-pipeline.md`
- CW9 project: `python/registry`
- crawl.db records: 331 functions across 25+ files
- GWTs registered: 27 (26 verified, 1 failed)

## Pipeline Results

| Metric | Count |
|--------|-------|
| GWTs authored | 27 |
| GWTs verified (PASS) | 26 |
| GWTs failed | 1 (gwt-0021: crawl-store-hosted-postgres-adapter) |
| Simulation traces | 260 (10 per verified GWT) |
| Total operations | ~170 |
| Total verifiers | ~250 |
| Total assertions | ~250 |

## Verified Specs and Traces

### gwt-0001: hosted-worker-input-download
- **Given**: A hosted worker job has been dequeued and input artifacts reside in object storage
- **When**: the worker begins job execution
- **Then**: the worker downloads all declared input artifacts from object storage to /workspace/.cw9/ before invoking any core pipeline function
- **Verified spec**: `.cw9/specs/gwt-0001.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0001_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0001_bridge_artifacts.json`
  - data_structures: 1 — WorkerArtifactDownloadState
  - operations: 7 — BeginExecution, DownloadArtifacts, DownloadNext, CheckWorkspace, SelectPipelineFunction, AwaitPipelineResult, Terminate
  - verifiers: 11, assertions: 11

### gwt-0002: hosted-worker-output-upload
- **Given**: A hosted worker job has completed core pipeline function execution and output artifacts exist in the ephemeral workspace
- **When**: the core function returns (whether passing or failing)
- **Then**: the worker uploads all output artifacts to object storage before the container exits
- **Verified spec**: `.cw9/specs/gwt-0002.tla` (3 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0002_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0002_bridge_artifacts.json`
  - data_structures: 1 — ArtifactUploadState
  - operations: 6 — RunCore, AwaitCore, UploadArtifacts, UploadOne, MarkComplete, Terminate
  - verifiers: 6, assertions: 6

### gwt-0003: hosted-worker-stateless-reconstruction
- **Given**: A hosted worker container starts fresh with no pre-existing state
- **When**: the worker reconstructs its execution context
- **Then**: the worker fully reconstructs all required state from object storage downloads and Postgres reads without session affinity or warm-up cache
- **Verified spec**: `.cw9/specs/gwt-0003.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0003_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0003_bridge_artifacts.json`
  - data_structures: 1 — WorkerContextReconstructionState
  - operations: 2 — Reconstruct, Finish
  - verifiers: 15, assertions: 15

### gwt-0004: project-context-hosted-factory
- **Given**: A hosted worker has been given a project_id, ephemeral workspace path, and storage client handle
- **When**: ProjectContext.hosted() is called
- **Then**: a frozen ProjectContext is returned with state_root=/workspace/.cw9/, container-baked template/tools dirs, and storage_client attribute; existing factory modes unchanged
- **Verified spec**: `.cw9/specs/gwt-0004.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0004_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0004_bridge_artifacts.json`
  - data_structures: 1 — ProjectContextHostedState
  - operations: 6 — SelectMode, Dispatch, AfterDispatch, CheckHosted, AfterCheck, Finish
  - verifiers: 8, assertions: 8

### gwt-0005: loop-job-sdk-session-per-gwt
- **Given**: A hosted heavy-tla worker has been assigned a loop job for a single GWT
- **When**: run_loop() begins execution
- **Then**: _make_client() is called exactly once, producing a single ClaudeSDKClient reused across all retry attempts
- **Verified spec**: `.cw9/specs/gwt-0005.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0005_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0005_bridge_artifacts.json`
  - data_structures: 1 — GWT0005SingleClientReuseState
  - operations: 9, verifiers: 9, assertions: 9

### gwt-0006: loop-job-sdk-session-lifetime
- **Given**: A loop job has an active ClaudeSDKClient created at job start
- **When**: the retry loop exits (PASS, FAIL, or exhausted)
- **Then**: safe_disconnect() is called in a finally block; no SDK session state persists after container exit
- **Verified spec**: `.cw9/specs/gwt-0006.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0006_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0006_bridge_artifacts.json`
  - data_structures: 1 — GWT0006_SafeDisconnectState
  - operations: 9, verifiers: 9, assertions: 9

### gwt-0007: loop-job-gwt-independence
- **Given**: Two or more loop jobs execute concurrently for different GWT IDs
- **When**: each worker processes its assigned GWT
- **Then**: each creates its own independent ClaudeSDKClient and DAG copy; no shared state between workers
- **Verified spec**: `.cw9/specs/gwt-0007.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0007_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0007_bridge_artifacts.json`
  - data_structures: 1 — GWT0007IsolationState
  - operations: 0, verifiers: 13, assertions: 13

### gwt-0008: sdk-credentials-environment-injection
- **Given**: A hosted worker container is starting a loop or crawl job
- **When**: the worker initializes its LLM client
- **Then**: CLAUDECODE env var consumed from container's injected environment, not inherited from parent CLI
- **Verified spec**: `.cw9/specs/gwt-0008.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0008_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0008_bridge_artifacts.json`
  - data_structures: 1 — WorkerClientInitState
  - operations: 7, verifiers: 10, assertions: 10

### gwt-0009: tlc-temp-dir-containerized-isolation
- **Given**: A heavy-tla loop worker is executing compile_compose_verify() inside a container
- **When**: compile_compose_verify() creates /tmp/cw9_XXXX/ and invokes java processes
- **Then**: temp directory is isolated per container; on PASS, verified files uploaded to object storage
- **Verified spec**: `.cw9/specs/gwt-0009.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0009_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0009_bridge_artifacts.json`
  - data_structures: 1 — GWT0009_CompileComposeVerifyState
  - operations: 0, verifiers: 9, assertions: 9

### gwt-0010: job-state-machine-transitions
- **Given**: A job record exists in Postgres with status PENDING
- **When**: the job lifecycle progresses
- **Then**: transitions through PENDING→QUEUED→RUNNING→{PASSED/FAILED/RETRYING} atomically in Postgres
- **Verified spec**: `.cw9/specs/gwt-0010.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0010_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0010_bridge_artifacts.json`
  - data_structures: 1 — JobLifecycleState
  - operations: 6 — Enqueue, Dequeue, PickResult, RouteResult, CheckRetry, Terminate
  - verifiers: 9, assertions: 9

### gwt-0011: loop-sim-traces-on-pass
- **Given**: A loop job attempt has produced LoopResult.PASS
- **When**: run_loop() receives the PASS result
- **Then**: run_tlc_simulate() is called, traces written to specs/{gwt_id}_sim_traces.json, included in upload batch
- **Verified spec**: `.cw9/specs/gwt-0011.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0011_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0011_bridge_artifacts.json`
  - data_structures: 1 — gwt_0011_SimTraceUploadState
  - operations: 6, verifiers: 13, assertions: 13

### gwt-0012: extract-job-light-worker
- **Given**: An extract job has been dequeued with schemas and dag.json downloaded
- **When**: SchemaExtractor.extract() runs inside cmd_extract()
- **Then**: DAG rebuilt from schemas, registered nodes merged, updated dag.json uploaded; no LLM, no subprocess, <10s
- **Verified spec**: `.cw9/specs/gwt-0012.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0012_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0012_bridge_artifacts.json`
  - data_structures: 1 — gwt0012_ExtractJobDAGRebuildState
  - operations: 6 — Dequeue, LoadOldDag, RunExtract, MergeRegistered, UploadDag, Finish
  - verifiers: 9, assertions: 9

### gwt-0013: bridge-job-light-worker
- **Given**: A bridge job has been dequeued with spec and trace files downloaded
- **When**: run_bridge() executes
- **Then**: TLA+ spec parsed via parse_spec(), all translate_* functions populate BridgeResult, artifact JSON written and uploaded; no LLM, no subprocess
- **Verified spec**: `.cw9/specs/gwt-0013.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0013_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0013_bridge_artifacts.json`
  - data_structures: 1 — BridgeJobState
  - operations: 12, verifiers: 11, assertions: 11

### gwt-0014: loop-job-heavy-tla-worker
- **Given**: A loop job is assigned to a worker node
- **When**: the scheduler selects a worker
- **Then**: node must be heavy-tla classified (Java JRE, tla2tools.jar, Claude SDK); timeout accommodates 8×300s+60s
- **Verified spec**: `.cw9/specs/gwt-0014.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0014_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0014_bridge_artifacts.json`
  - data_structures: 1 — gwt0014_SchedulerHeavyTLAState
  - operations: 7, verifiers: 8, assertions: 8

### gwt-0015: gen-tests-job-heavy-lang-worker
- **Given**: A gen-tests job has been dequeued with a target language profile
- **When**: run_test_gen_loop() executes
- **Then**: Claude SDK invoked for plan/review/codegen passes, language-specific verify_test_file() runs subprocess, generated test uploaded
- **Verified spec**: `.cw9/specs/gwt-0015.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0015_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0015_bridge_artifacts.json`
  - data_structures: 1 — GenTestsLoopState
  - operations: 7, verifiers: 15, assertions: 15

### gwt-0016: gen-tests-3-pass-structure
- **Given**: A gen-tests worker has initialized a language profile and downloaded artifacts
- **When**: run_test_gen_loop() begins
- **Then**: exactly 3 sequential LLM calls (plan→review→codegen), followed by extract+verify, then retry loop if verification fails
- **Verified spec**: `.cw9/specs/gwt-0016.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0016_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0016_bridge_artifacts.json`
  - data_structures: 1 — GWT0016TestGenLoopState
  - operations: 15, verifiers: 8, assertions: 8

### gwt-0017: crawl-job-heavy-tla-worker
- **Given**: A crawl job has been dequeued with crawl.db containing skeleton records
- **When**: CrawlOrchestrator.run() executes
- **Then**: exactly one Claude SDK call per skeleton record, populated crawl.db uploaded, job marked PASSED
- **Verified spec**: `.cw9/specs/gwt-0017.tla` (3 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0017_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0017_bridge_artifacts.json`
  - data_structures: 1 — CrawlOrchestrator_gwt0017State
  - operations: 5, verifiers: 9, assertions: 9

### gwt-0018: ingest-job-light-worker
- **Given**: An ingest job has been dequeued with access to source code and crawl.db
- **When**: cmd_ingest() runs the scanner
- **Then**: skeleton FnRecord entries written to crawl.db, RESOURCE nodes to dag.json, no LLM, <10s, artifacts uploaded
- **Verified spec**: `.cw9/specs/gwt-0018.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0018_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0018_bridge_artifacts.json`
  - data_structures: 1 — IngestScannerState
  - operations: 8, verifiers: 9, assertions: 9

### gwt-0019: init-becomes-control-plane-api
- **Given**: A user submits POST /projects to the control plane API
- **When**: the API handler processes the request
- **Then**: Postgres project record created, object storage prefix provisioned, no .cw9/ filesystem directory created
- **Verified spec**: `.cw9/specs/gwt-0019.tla` (3 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0019_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0019_bridge_artifacts.json`
  - data_structures: 1 — ProjectProvisionState
  - operations: 6, verifiers: 9, assertions: 9

### gwt-0020: dag-hosted-postgres-storage
- **Given**: A hosted worker needs to read or write the project's RegistryDag
- **When**: RegistryDag.load() or RegistryDag.save() is called in hosted context
- **Then**: DAG read from/written to Postgres JSON column; in-memory object and all methods unchanged
- **Verified spec**: `.cw9/specs/gwt-0020.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0020_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0020_bridge_artifacts.json`
  - data_structures: 1 — RegistryDagHostedPersistenceState
  - operations: 8 — CallLoad, SelectLoadBackend, ExecuteLoad, InMemoryOps, CallSave, SelectSaveBackend, ExecuteSave, Finish
  - verifiers: 11, assertions: 11

### gwt-0021: crawl-store-hosted-postgres-adapter — FAILED (8 attempts)
- **Given**: A hosted worker needs to read or write crawl.db behavioral records
- **When**: CrawlStore is instantiated in hosted mode
- **Then**: CrawlStore connects to Postgres instead of SQLite with same interface
- **Status**: TLC model checking failed after 8 attempts — behavior too broad for single formal model
- **Plan**: Implement manually based on research doc findings (CrawlStore analysis: 23 public methods, 7 tables, 4 views, 9 indexes — see Section 4 of research doc)

### gwt-0022: pipeline-maps-to-job-dag
- **Given**: A user submits POST /projects/{id}/runs to trigger a full pipeline run
- **When**: the control plane builds the execution plan
- **Then**: job DAG persisted with extract→register→loop(parallel)→bridge→gen-tests ordering
- **Verified spec**: `.cw9/specs/gwt-0022.tla` (5 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0022_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0022_bridge_artifacts.json`
  - data_structures: 1 — GWTPipelineDAGState
  - operations: 5, verifiers: 10, assertions: 10

### gwt-0023: register-job-light-worker
- **Given**: A register job has been dequeued with dag.json and criterion_bindings.json downloaded
- **When**: _register_payload() executes
- **Then**: DAG mutated, bindings updated, both uploaded; no LLM call
- **Verified spec**: `.cw9/specs/gwt-0023.tla` (5 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0023_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0023_bridge_artifacts.json`
  - data_structures: 1 — RegisterPayloadState
  - operations: 9, verifiers: 7, assertions: 7

### gwt-0024: write-result-file-becomes-db-update
- **Given**: A loop or gen-tests job has completed
- **When**: write_result_file() is called
- **Then**: structured result written to Postgres job_results table, raw logs uploaded to object storage
- **Verified spec**: `.cw9/specs/gwt-0024.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0024_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0024_bridge_artifacts.json`
  - data_structures: 1 — GWT0024WriteResultState
  - operations: 6, verifiers: 10, assertions: 10

### gwt-0025: gwt-author-job-single-llm-call
- **Given**: A gwt-author job has been dequeued with research notes, crawl.db, and dag.json
- **When**: run_gwt_author() executes
- **Then**: exactly one LLM call, response parsed, depends_on validated against crawl.db, GWT JSON returned; <60s
- **Verified spec**: `.cw9/specs/gwt-0025.tla` (2 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0025_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0025_bridge_artifacts.json`
  - data_structures: 1 — GwtAuthorState
  - operations: 8, verifiers: 12, assertions: 12

### gwt-0026: loop-context-query-from-dag-and-crawl
- **Given**: A loop worker has downloaded dag.json and optionally crawl.db
- **When**: query_context() is called for the GWT ID
- **Then**: relevant DAG nodes retrieved, matching FnRecord cards fetched from crawl.db, context formatted; if crawl.db absent, prompt built with DAG context only without error
- **Verified spec**: `.cw9/specs/gwt-0026.tla` (3 attempts)
- **Simulation traces**: `.cw9/specs/gwt-0026_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0026_bridge_artifacts.json`
  - data_structures: 1 — GWT0026PromptContextState
  - operations: 6, verifiers: 7, assertions: 7

### gwt-0027: loop-retry-prompt-includes-counterexample
- **Given**: A loop job attempt has returned LoopResult.RETRY with a counterexample
- **When**: build_retry_prompt() constructs the next attempt's prompt
- **Then**: retry prompt includes translated counterexample, TLC error classification, previous PlusCal text, sent to persistent ClaudeSDKClient with full correction history
- **Verified spec**: `.cw9/specs/gwt-0027.tla` (1 attempt)
- **Simulation traces**: `.cw9/specs/gwt-0027_sim_traces.json` (10 traces)
- **Bridge artifacts**: `.cw9/bridge/gwt-0027_bridge_artifacts.json`
  - data_structures: 1 — GWT0027RetryPromptBuilderState
  - operations: 9, verifiers: 6, assertions: 6

## What We're NOT Doing

- No actual cloud infrastructure provisioning (Postgres, S3, Kubernetes)
- No container image builds or Dockerfiles
- No authentication/authorization for the API
- No monitoring/observability layer
- No rate limiting or cost controls for LLM calls
- No UI or dashboard
- No migration of existing `.cw9/` projects to hosted

## Testing Strategy

- **Framework**: pytest (existing)
- **Fixture pattern**: module-level helpers (`_make_*` builders), `tmp_path` for ephemeral storage, `@pytest.fixture` with `yield` for connection lifecycle
- **Mocking**: `AsyncMock` for LLM callables, inline fake functions for extract_fn/storage operations, `patch` for CLI/subprocess isolation
- **Integration markers**: `@pytest.mark.integration` for tests requiring Postgres or external tools
- **CrawlStore tests**: `store` fixture using `tmp_path` (existing pattern from `test_crawl.py:217`)

---

## Step 1: Job State Machine — `JobStatus` Enum and `JobRecord` Model

### CW9 Binding
- **GWT**: gwt-0010 (job-state-machine-transitions)
- **Bridge artifact**: `data_structures[0]` — JobLifecycleState
- **Bridge operations**: Enqueue, Dequeue, PickResult, RouteResult, CheckRetry, Terminate
- **depends_on UUIDs**:
  - `45c95d8c` — run_loop @ loop_runner.py:220
  - `924330b9` — write_result_file @ status.py:61

### Test Specification
**Given**: An empty in-memory job store
**When**: A job is created, enqueued, dequeued, and routed through outcomes
**Then**: State transitions follow PENDING→QUEUED→RUNNING→{PASSED/FAILED/RETRYING} with atomic updates
**Edge Cases**: RETRYING→RUNNING back-transition, exhausted retries→FAILED, invalid transitions rejected

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_job_state.py`
```python
"""Tests for hosted job state machine — derived from gwt-0010 simulation traces."""
import pytest
from registry.hosted.job_state import JobStatus, JobRecord, InvalidTransitionError


class TestJobStatusEnum:
    def test_all_states_defined(self):
        assert set(JobStatus) == {
            JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING,
            JobStatus.PASSED, JobStatus.FAILED, JobStatus.RETRYING,
        }

    def test_terminal_states(self):
        assert JobStatus.PASSED.is_terminal
        assert JobStatus.FAILED.is_terminal
        assert not JobStatus.RUNNING.is_terminal
        assert not JobStatus.RETRYING.is_terminal


class TestJobRecordTransitions:
    def test_pending_to_queued(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        assert job.status == JobStatus.PENDING
        job.enqueue()
        assert job.status == JobStatus.QUEUED

    def test_queued_to_running(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        job.enqueue()
        job.dequeue()
        assert job.status == JobStatus.RUNNING

    def test_running_to_passed(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        job.enqueue()
        job.dequeue()
        job.route_result("pass")
        assert job.status == JobStatus.PASSED

    def test_running_to_failed(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        job.enqueue()
        job.dequeue()
        job.route_result("fail")
        assert job.status == JobStatus.FAILED

    def test_retrying_to_running(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop", max_retries=8)
        job.enqueue()
        job.dequeue()
        job.route_result("retry")
        assert job.status == JobStatus.RETRYING
        job.check_retry()
        assert job.status == JobStatus.RUNNING
        assert job.attempt == 2

    def test_exhausted_retries_to_failed(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop", max_retries=1)
        job.enqueue()
        job.dequeue()
        job.route_result("retry")
        job.check_retry()  # attempt 2 > max_retries=1
        assert job.status == JobStatus.FAILED

    def test_invalid_transition_raises(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        with pytest.raises(InvalidTransitionError):
            job.dequeue()  # PENDING → RUNNING is invalid (must go through QUEUED)

    def test_terminal_state_is_absorbing(self):
        job = JobRecord(gwt_id="gwt-0001", job_type="loop")
        job.enqueue()
        job.dequeue()
        job.route_result("pass")
        with pytest.raises(InvalidTransitionError):
            job.route_result("fail")  # PASSED is terminal
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/__init__.py` (new package)
**File**: `python/registry/hosted/job_state.py`
```python
"""Job state machine for hosted pipeline — from gwt-0010 verified spec."""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class InvalidTransitionError(Exception):
    pass


class JobStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.PASSED, JobStatus.FAILED)


_VALID_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.QUEUED},
    JobStatus.QUEUED: {JobStatus.RUNNING},
    JobStatus.RUNNING: {JobStatus.PASSED, JobStatus.FAILED, JobStatus.RETRYING},
    JobStatus.RETRYING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.PASSED: set(),
    JobStatus.FAILED: set(),
}


@dataclass
class JobRecord:
    gwt_id: str
    job_type: str
    status: JobStatus = field(default=JobStatus.PENDING)
    attempt: int = field(default=1)
    max_retries: int = field(default=8)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = field(default=None)

    def _transition(self, target: JobStatus) -> None:
        if target not in _VALID_TRANSITIONS[self.status]:
            raise InvalidTransitionError(
                f"Cannot transition from {self.status.value} to {target.value}"
            )
        self.status = target

    def enqueue(self) -> None:
        self._transition(JobStatus.QUEUED)

    def dequeue(self) -> None:
        self._transition(JobStatus.RUNNING)

    def route_result(self, result: str) -> None:
        match result:
            case "pass":
                self._transition(JobStatus.PASSED)
            case "fail":
                self._transition(JobStatus.FAILED)
            case "retry":
                self._transition(JobStatus.RETRYING)

    def check_retry(self) -> None:
        if self.attempt >= self.max_retries:
            self._transition(JobStatus.FAILED)
        else:
            self.attempt += 1
            self._transition(JobStatus.RUNNING)
```

### Success Criteria
- [ ] Test fails for right reason (Red)
- [ ] Test passes (Green)
- [ ] All existing tests still pass after refactor

---

## Step 2: ProjectContext.hosted() Factory

### CW9 Binding
- **GWT**: gwt-0004 (project-context-hosted-factory)
- **Bridge artifact**: `data_structures[0]` — ProjectContextHostedState
- **Bridge operations**: SelectMode, Dispatch, AfterDispatch, CheckHosted, AfterCheck, Finish
- **depends_on UUIDs**:
  - `1b2e7529` — from_target @ context.py
  - `3841686c` — self_hosting @ context.py:47
  - `7392f42f` — external @ context.py:108
  - `9c450f7f` — installed @ context.py:131

### Test Specification
**Given**: A project_id, workspace Path, and mock storage client
**When**: ProjectContext.hosted() is called
**Then**: Frozen dataclass returned with correct paths; existing factory modes unchanged
**Edge Cases**: storage_client is None (should raise), workspace doesn't exist (should raise)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_context_hosted.py`
```python
"""Tests for ProjectContext.hosted() — derived from gwt-0004 simulation traces."""
from pathlib import Path
import pytest
from registry.context import ProjectContext


class TestHostedFactory:
    def test_state_root_under_workspace(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ctx = ProjectContext.hosted(
            project_id="proj-001",
            workspace=workspace,
            storage_client=object(),  # mock
        )
        assert ctx.state_root == workspace / ".cw9"

    def test_engine_paths_are_container_baked(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ctx = ProjectContext.hosted(
            project_id="proj-001",
            workspace=workspace,
            storage_client=object(),
            engine_root=tmp_path / "engine",
        )
        assert ctx.template_dir == tmp_path / "engine" / "templates" / "pluscal"
        assert ctx.tools_dir == tmp_path / "engine" / "tools"

    def test_is_not_self_hosting(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ctx = ProjectContext.hosted(
            project_id="proj-001",
            workspace=workspace,
            storage_client=object(),
            engine_root=tmp_path / "engine",
        )
        assert not ctx.is_self_hosting

    def test_storage_client_accessible(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        client = object()
        ctx = ProjectContext.hosted(
            project_id="proj-001",
            workspace=workspace,
            storage_client=client,
        )
        assert ctx.storage_client is client

    def test_existing_factories_unchanged(self, tmp_path):
        """Regression: self_hosting, external, installed still work."""
        engine = tmp_path / "engine"
        engine.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (target / ".cw9").mkdir()
        ctx = ProjectContext.external(engine, target)
        assert ctx.state_root == target / ".cw9"

    def test_schema_spec_artifact_session_dirs(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        ctx = ProjectContext.hosted(
            project_id="proj-001",
            workspace=workspace,
            storage_client=object(),
        )
        state = workspace / ".cw9"
        assert ctx.schema_dir == state / "schema"
        assert ctx.spec_dir == state / "specs"
        assert ctx.artifact_dir == state / "bridge"
        assert ctx.session_dir == state / "sessions"
```

#### Green: Minimal Implementation
**File**: `python/registry/context.py` — add `hosted()` classmethod and `storage_client` field

Add `storage_client: object | None = None` field to ProjectContext (line ~37).
Add `hosted()` classmethod after `installed()` (~line 152).

```python
@classmethod
def hosted(
    cls,
    project_id: str,
    workspace: Path,
    storage_client,
    engine_root: Path | None = None,
) -> "ProjectContext":
    workspace = Path(workspace).resolve()
    state_root = workspace / ".cw9"
    if engine_root is not None:
        engine_root = Path(engine_root).resolve()
        template_dir = engine_root / "templates" / "pluscal"
        tools_dir = engine_root / "tools"
        python_dir = engine_root / "python"
    else:
        from registry._resources import get_template_dir, get_data_path
        template_dir = get_template_dir("pluscal")
        tools_dir = get_data_path("tools")
        python_dir = workspace
    return cls(
        engine_root=engine_root,
        target_root=workspace,
        state_root=state_root,
        template_dir=template_dir,
        tools_dir=tools_dir,
        python_dir=python_dir,
        schema_dir=state_root / "schema",
        spec_dir=state_root / "specs",
        artifact_dir=state_root / "bridge",
        session_dir=state_root / "sessions",
        test_output_dir=workspace / "tests" / "generated",
        storage_client=storage_client,
    )
```

### Success Criteria
- [ ] Test fails for right reason (Red)
- [ ] Test passes (Green)
- [ ] All existing context tests still pass (test_context.py)

---

## Step 3: RegistryDag Postgres Backend

### CW9 Binding
- **GWT**: gwt-0020 (dag-hosted-postgres-storage)
- **Bridge operations**: CallLoad, SelectLoadBackend, ExecuteLoad, InMemoryOps, CallSave, SelectSaveBackend, ExecuteSave, Finish
- **Key verifiers**: HostedLoadUsesPostgres, HostedSaveUsesPostgres, LocalLoadUsesFile, LocalSaveUsesFile, InMemoryInterfaceUnchanged, OnlyBackendDiffers

### Test Specification
**Given**: A RegistryDag with a Postgres-backed storage adapter
**When**: load() and save() are called in hosted mode
**Then**: Reads from/writes to Postgres; all in-memory operations (add_node, add_edge, query_relevant, etc.) are unchanged
**Edge Cases**: Local mode still uses file I/O, backend dispatch is clean

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_dag_hosted.py`
```python
"""Tests for RegistryDag hosted persistence — derived from gwt-0020 simulation traces."""
import json
import pytest
from registry.dag import RegistryDag
from registry.types import Node, Edge, EdgeType
from registry.hosted.storage import DagStorageBackend, InMemoryDagBackend


def make_node(nid: str) -> Node:
    return Node.resource(nid, nid, f"Test node {nid}")


class TestDagBackendDispatch:
    def test_save_to_backend(self):
        backend = InMemoryDagBackend()
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.save_to_backend(backend, project_id="proj-001")
        assert backend.has_dag("proj-001")

    def test_load_from_backend(self):
        backend = InMemoryDagBackend()
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.save_to_backend(backend, project_id="proj-001")
        loaded = RegistryDag.load_from_backend(backend, project_id="proj-001")
        assert loaded.node_count == 1
        assert "a" in loaded.nodes

    def test_roundtrip_preserves_all_data(self):
        backend = InMemoryDagBackend()
        dag = RegistryDag()
        dag.add_node(make_node("x"))
        dag.add_node(make_node("y"))
        dag.add_edge(Edge("x", "y", EdgeType.DEPENDS_ON))
        dag.save_to_backend(backend, project_id="proj-001")
        loaded = RegistryDag.load_from_backend(backend, project_id="proj-001")
        assert loaded.node_count == dag.node_count
        assert loaded.edge_count == dag.edge_count
        assert loaded.closure == dag.closure

    def test_local_file_save_still_works(self, tmp_path):
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        path = tmp_path / "dag.json"
        dag.save(path)
        loaded = RegistryDag.load(path)
        assert loaded.node_count == 1

    def test_in_memory_operations_unchanged(self):
        """Regression: all in-memory methods work identically regardless of backend."""
        dag = RegistryDag()
        dag.add_node(make_node("a"))
        dag.add_node(make_node("b"))
        dag.add_node(make_node("c"))
        dag.add_edge(Edge("a", "b", EdgeType.CALLS))
        dag.add_edge(Edge("b", "c", EdgeType.CALLS))
        result = dag.query_relevant("a")
        assert "c" in result.transitive_deps
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/storage.py`
```python
"""Storage backends for hosted persistence — from gwt-0020 verified spec."""
import json
from abc import ABC, abstractmethod


class DagStorageBackend(ABC):
    @abstractmethod
    def load_dag_json(self, project_id: str) -> str: ...
    @abstractmethod
    def save_dag_json(self, project_id: str, data: str) -> None: ...
    @abstractmethod
    def has_dag(self, project_id: str) -> bool: ...


class InMemoryDagBackend(DagStorageBackend):
    def __init__(self):
        self._store: dict[str, str] = {}
    def load_dag_json(self, project_id: str) -> str:
        return self._store[project_id]
    def save_dag_json(self, project_id: str, data: str) -> None:
        self._store[project_id] = data
    def has_dag(self, project_id: str) -> bool:
        return project_id in self._store
```

Then add `save_to_backend` / `load_from_backend` to `RegistryDag` in `dag.py`:
```python
def save_to_backend(self, backend: "DagStorageBackend", project_id: str) -> None:
    backend.save_dag_json(project_id, self.to_json())

@classmethod
def load_from_backend(cls, backend: "DagStorageBackend", project_id: str) -> "RegistryDag":
    return cls.from_json(backend.load_dag_json(project_id))
```

### Success Criteria
- [ ] All existing dag tests pass (test_dag.py)
- [ ] Backend dispatch tests pass
- [ ] File-based save/load unchanged

---

## Step 4: CrawlStore Postgres Adapter (Manual — gwt-0021 failed)

### Rationale
gwt-0021 failed TLC verification after 8 attempts because modeling the full CrawlStore interface (23 public methods, 7 tables, recursive CTEs) in a single PlusCal spec was too broad. We plan this step manually from the research doc's CrawlStore analysis.

### Design: Protocol-Based Backend Swap

The existing CrawlStore uses SQLite directly. Rather than rewriting it, introduce a `CrawlStoreBackend` protocol that abstracts the connection and SQL dialect differences.

### Test Specification
**Given**: A CrawlStoreBackend protocol and a PostgresCrawlBackend implementation
**When**: CrawlStore methods are called in hosted mode
**Then**: All 23 public methods work identically, using Postgres instead of SQLite
**Key differences**: `?` → `%s` placeholders, `AUTOINCREMENT` → `SERIAL`, `INSERT OR REPLACE` → `INSERT ... ON CONFLICT`, `datetime('now')` → `NOW()`, `cur.lastrowid` → `RETURNING id`

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_crawl_hosted.py`
```python
"""Tests for CrawlStore Postgres adapter — manual plan (gwt-0021 failed verification)."""
import pytest
from registry.crawl_store import CrawlStore
from registry.hosted.crawl_backend import InMemoryCrawlBackend

# Reuse existing test helpers
from tests.test_crawl import _make_fn_record, _make_ax_record


@pytest.fixture
def hosted_store():
    backend = InMemoryCrawlBackend()
    store = CrawlStore.from_backend(backend)
    store.connect()
    yield store
    store.close()


class TestHostedCrawlStoreBasic:
    def test_connect_creates_schema(self, hosted_store):
        tables = hosted_store.list_tables()
        assert "records" in tables

    def test_insert_and_get_record(self, hosted_store):
        rec = _make_fn_record()
        hosted_store.insert_record(rec)
        got = hosted_store.get_record(rec.uuid)
        assert got is not None
        assert got.function_name == rec.function_name

    def test_upsert_preserves_ins_outs(self, hosted_store):
        rec = _make_fn_record()
        hosted_store.insert_record(rec)
        hosted_store.upsert_record(rec)
        got = hosted_store.get_record(rec.uuid)
        assert len(got.ins) == len(rec.ins)

    def test_context_manager(self):
        backend = InMemoryCrawlBackend()
        with CrawlStore.from_backend(backend) as store:
            rec = _make_fn_record()
            store.insert_record(rec)
            assert store.get_record(rec.uuid) is not None


class TestHostedCrawlStoreStaleness:
    def test_stale_detection(self, hosted_store):
        rec = _make_fn_record(src_hash="abc123")
        hosted_store.insert_record(rec)
        stale = hosted_store.get_stale_records({"src/handlers/user.py": "different_hash"})
        assert rec.uuid in stale

    def test_not_stale_when_hash_matches(self, hosted_store):
        rec = _make_fn_record(src_hash="abc123")
        hosted_store.insert_record(rec)
        stale = hosted_store.get_stale_records({"src/handlers/user.py": "abc123"})
        assert rec.uuid not in stale
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/crawl_backend.py`

Implement `CrawlStoreBackend` protocol with `InMemoryCrawlBackend` for testing and `PostgresCrawlBackend` for production. Add `CrawlStore.from_backend()` classmethod.

### Success Criteria
- [ ] All existing CrawlStore tests pass unchanged (test_crawl.py)
- [ ] Hosted backend tests pass with InMemoryCrawlBackend
- [ ] Same public interface: get_record, upsert_record, insert_record, get_all_uuids, get_pending_uuids, get_stale_records, get_card_text, etc.

---

## Step 5: Object Storage Abstraction

### CW9 Binding
- **GWTs**: gwt-0001 (input download), gwt-0002 (output upload)
- **Bridge operations (gwt-0001)**: BeginExecution, DownloadArtifacts, DownloadNext, CheckWorkspace, SelectPipelineFunction, AwaitPipelineResult, Terminate
- **Bridge operations (gwt-0002)**: RunCore, AwaitCore, UploadArtifacts, UploadOne, MarkComplete, Terminate
- **Key verifiers (gwt-0001)**: AllDeclaredInputsDownloaded, WorkspaceMatchesInputs, NoFunctionBeforeAllDownloaded
- **Key verifiers (gwt-0002)**: AllOutputsUploaded, UploadAfterCoreComplete, NoContainerExitBeforeUpload

### Test Specification
**Given**: A storage client protocol and an in-memory implementation
**When**: download_inputs() and upload_outputs() are called
**Then**: All declared artifacts are transferred between storage and workspace
**Edge Cases**: Missing artifact in storage (error), partial upload on failure (all-or-nothing)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_worker_storage.py`
```python
"""Tests for worker artifact download/upload — from gwt-0001, gwt-0002 simulation traces."""
from pathlib import Path
import pytest
from registry.hosted.storage import (
    StorageClient, InMemoryStorageClient,
    download_inputs, upload_outputs,
)


@pytest.fixture
def storage():
    return InMemoryStorageClient()


class TestDownloadInputs:
    def test_downloads_all_declared_inputs(self, storage, tmp_path):
        storage.put("proj-001/dag.json", b'{"nodes":[],"edges":[],"closure":{},"components":{}}')
        storage.put("proj-001/schema/backend.json", b'{}')
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        download_inputs(
            storage, project_id="proj-001", workspace=workspace,
            artifacts=["dag.json", "schema/backend.json"],
        )
        assert (workspace / ".cw9" / "dag.json").exists()
        assert (workspace / ".cw9" / "schema" / "backend.json").exists()

    def test_missing_artifact_raises(self, storage, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        with pytest.raises(FileNotFoundError):
            download_inputs(
                storage, project_id="proj-001", workspace=workspace,
                artifacts=["nonexistent.json"],
            )

    def test_no_pipeline_fn_before_all_downloaded(self, storage, tmp_path):
        """Verifier: NoFunctionBeforeAllDownloaded."""
        storage.put("proj-001/dag.json", b'{}')
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        download_inputs(
            storage, project_id="proj-001", workspace=workspace,
            artifacts=["dag.json"],
        )
        assert (workspace / ".cw9" / "dag.json").read_bytes() == b'{}'


class TestUploadOutputs:
    def test_uploads_all_outputs(self, storage, tmp_path):
        workspace = tmp_path / "workspace"
        state = workspace / ".cw9" / "specs"
        state.mkdir(parents=True)
        (state / "gwt-0001.tla").write_text("spec content")
        (state / "gwt-0001_sim_traces.json").write_text("[]")
        upload_outputs(
            storage, project_id="proj-001", workspace=workspace,
            artifacts=["specs/gwt-0001.tla", "specs/gwt-0001_sim_traces.json"],
        )
        assert storage.get("proj-001/specs/gwt-0001.tla") == b"spec content"
        assert storage.get("proj-001/specs/gwt-0001_sim_traces.json") == b"[]"

    def test_upload_after_core_complete(self, storage, tmp_path):
        """Verifier: UploadAfterCoreComplete — outputs only uploaded after core fn returns."""
        workspace = tmp_path / "workspace"
        state = workspace / ".cw9" / "bridge"
        state.mkdir(parents=True)
        (state / "gwt-0001_bridge_artifacts.json").write_text("{}")
        upload_outputs(
            storage, project_id="proj-001", workspace=workspace,
            artifacts=["bridge/gwt-0001_bridge_artifacts.json"],
        )
        assert storage.has("proj-001/bridge/gwt-0001_bridge_artifacts.json")
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/storage.py` (extend)
```python
from abc import ABC, abstractmethod
from pathlib import Path


class StorageClient(ABC):
    @abstractmethod
    def get(self, key: str) -> bytes: ...
    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...
    @abstractmethod
    def has(self, key: str) -> bool: ...
    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]: ...


class InMemoryStorageClient(StorageClient):
    def __init__(self):
        self._store: dict[str, bytes] = {}
    def get(self, key: str) -> bytes:
        if key not in self._store:
            raise FileNotFoundError(key)
        return self._store[key]
    def put(self, key: str, data: bytes) -> None:
        self._store[key] = data
    def has(self, key: str) -> bool:
        return key in self._store
    def list_prefix(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]


def download_inputs(
    client: StorageClient, project_id: str, workspace: Path, artifacts: list[str],
) -> None:
    state_root = workspace / ".cw9"
    for artifact in artifacts:
        key = f"{project_id}/{artifact}"
        data = client.get(key)
        dest = state_root / artifact
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def upload_outputs(
    client: StorageClient, project_id: str, workspace: Path, artifacts: list[str],
) -> None:
    state_root = workspace / ".cw9"
    for artifact in artifacts:
        src = state_root / artifact
        key = f"{project_id}/{artifact}"
        client.put(key, src.read_bytes())
```

### Success Criteria
- [ ] Download creates correct directory structure
- [ ] Upload sends correct content to storage
- [ ] Missing artifacts raise appropriate errors

---

## Step 6: Worker Lifecycle — Stateless Reconstruction

### CW9 Binding
- **GWT**: gwt-0003 (hosted-worker-stateless-reconstruction)
- **Bridge operations**: Reconstruct, Finish
- **Key verifiers**: NoSessionAffinity, NoWarmUpCache, AllStateFromStorage, ProjectContextReconstructed, DagReconstructed, CrawlStoreReconstructed (15 total)

### Test Specification
**Given**: A fresh worker container with no pre-existing state
**When**: reconstruct_worker_context() is called
**Then**: ProjectContext, RegistryDag, and CrawlStore connection are all available
**Edge Cases**: Missing optional artifacts (crawl.db absent → skip), corrupted dag.json → error

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_worker_lifecycle.py`
```python
"""Tests for worker stateless reconstruction — from gwt-0003 simulation traces."""
from pathlib import Path
import json
import pytest
from registry.hosted.worker import reconstruct_worker_context, WorkerContext
from registry.hosted.storage import InMemoryStorageClient


@pytest.fixture
def storage_with_project():
    client = InMemoryStorageClient()
    dag = {"nodes": [], "edges": [], "closure": {}, "components": {}}
    client.put("proj-001/dag.json", json.dumps(dag).encode())
    return client


class TestStatelessReconstruction:
    def test_reconstructs_project_context(self, storage_with_project, tmp_path):
        wctx = reconstruct_worker_context(
            storage=storage_with_project,
            project_id="proj-001",
            workspace=tmp_path / "workspace",
            job_type="loop",
        )
        assert wctx.ctx.state_root == tmp_path / "workspace" / ".cw9"

    def test_reconstructs_dag(self, storage_with_project, tmp_path):
        wctx = reconstruct_worker_context(
            storage=storage_with_project,
            project_id="proj-001",
            workspace=tmp_path / "workspace",
            job_type="extract",
        )
        assert wctx.dag is not None
        assert wctx.dag.node_count == 0

    def test_no_session_affinity(self, storage_with_project, tmp_path):
        """Two independent reconstructions produce equivalent state."""
        wctx1 = reconstruct_worker_context(
            storage=storage_with_project,
            project_id="proj-001",
            workspace=tmp_path / "ws1",
            job_type="bridge",
        )
        wctx2 = reconstruct_worker_context(
            storage=storage_with_project,
            project_id="proj-001",
            workspace=tmp_path / "ws2",
            job_type="bridge",
        )
        assert wctx1.dag.to_json() == wctx2.dag.to_json()

    def test_missing_crawl_db_is_ok(self, storage_with_project, tmp_path):
        """crawl.db is optional — workers that don't need it skip it."""
        wctx = reconstruct_worker_context(
            storage=storage_with_project,
            project_id="proj-001",
            workspace=tmp_path / "workspace",
            job_type="extract",
        )
        assert wctx.crawl_store is None
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/worker.py`
```python
"""Worker lifecycle — from gwt-0001, gwt-0002, gwt-0003 verified specs."""
from dataclasses import dataclass
from pathlib import Path
from registry.context import ProjectContext
from registry.dag import RegistryDag
from registry.crawl_store import CrawlStore
from registry.hosted.storage import StorageClient, download_inputs


@dataclass
class WorkerContext:
    ctx: ProjectContext
    dag: RegistryDag
    crawl_store: CrawlStore | None


_JOB_INPUT_ARTIFACTS = {
    "loop": ["dag.json"],
    "bridge": ["dag.json"],
    "extract": ["dag.json"],
    "register": ["dag.json"],
    "gen-tests": ["dag.json"],
    "crawl": ["dag.json"],
    "ingest": ["dag.json"],
}


def reconstruct_worker_context(
    storage: StorageClient,
    project_id: str,
    workspace: Path,
    job_type: str,
) -> WorkerContext:
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    artifacts = _JOB_INPUT_ARTIFACTS.get(job_type, ["dag.json"])
    download_inputs(storage, project_id, workspace, artifacts)
    ctx = ProjectContext.hosted(
        project_id=project_id,
        workspace=workspace,
        storage_client=storage,
    )
    dag_path = ctx.state_root / "dag.json"
    dag = RegistryDag.load(dag_path) if dag_path.exists() else RegistryDag()
    crawl_db_path = ctx.state_root / "crawl.db"
    crawl_store = None
    if crawl_db_path.exists():
        crawl_store = CrawlStore(crawl_db_path)
        crawl_store.connect()
    return WorkerContext(ctx=ctx, dag=dag, crawl_store=crawl_store)
```

### Success Criteria
- [ ] Worker context fully reconstructed from storage
- [ ] No session affinity between independent reconstructions
- [ ] Missing optional artifacts handled gracefully

---

## Step 7: write_result_file() → DB Update

### CW9 Binding
- **GWT**: gwt-0024 (write-result-file-becomes-db-update)
- **Bridge operations**: CompleteJob, CallWriteResult, WriteDB, CheckDB, UploadLogs, Finish
- **Key verifiers**: NoLocalWrite, DBWriteRequiresOutcome, StorageRequiresDB, HostedReplacement

### Test Specification
**Given**: A completed job with result data
**When**: write_result_hosted() is called
**Then**: Structured result written to a results store (DB), raw session logs uploaded to object storage; no local .cw9/sessions/ write

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_write_result_hosted.py`
```python
"""Tests for hosted write_result — from gwt-0024 simulation traces."""
import pytest
from registry.hosted.results import write_result_hosted, InMemoryResultStore
from registry.hosted.storage import InMemoryStorageClient


class TestWriteResultHosted:
    def test_writes_structured_result_to_store(self):
        store = InMemoryResultStore()
        storage = InMemoryStorageClient()
        write_result_hosted(
            result_store=store,
            storage=storage,
            project_id="proj-001",
            gwt_id="gwt-0001",
            result="pass",
            attempts=1,
            error=None,
            session_logs={"gwt-0001_attempt1.txt": b"LLM response..."},
        )
        r = store.get("proj-001", "gwt-0001")
        assert r["result"] == "pass"
        assert r["attempts"] == 1

    def test_uploads_session_logs_to_storage(self):
        store = InMemoryResultStore()
        storage = InMemoryStorageClient()
        write_result_hosted(
            result_store=store,
            storage=storage,
            project_id="proj-001",
            gwt_id="gwt-0001",
            result="fail",
            attempts=3,
            error="Exhausted",
            session_logs={
                "gwt-0001_attempt1.txt": b"attempt 1",
                "gwt-0001_attempt2.txt": b"attempt 2",
                "gwt-0001_attempt3.txt": b"attempt 3",
            },
        )
        assert storage.has("proj-001/sessions/gwt-0001_attempt1.txt")
        assert storage.has("proj-001/sessions/gwt-0001_attempt3.txt")

    def test_no_local_file_write(self, tmp_path):
        """Verifier: NoLocalWrite — no .cw9/sessions/ directory touched."""
        store = InMemoryResultStore()
        storage = InMemoryStorageClient()
        sessions_dir = tmp_path / ".cw9" / "sessions"
        write_result_hosted(
            result_store=store,
            storage=storage,
            project_id="proj-001",
            gwt_id="gwt-0001",
            result="pass",
            attempts=1,
            error=None,
            session_logs={},
        )
        assert not sessions_dir.exists()
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/results.py`

### Success Criteria
- [ ] Structured result persisted to store
- [ ] Session logs uploaded to object storage
- [ ] No local filesystem writes

---

## Step 8: Control Plane — POST /projects (Init Replacement)

### CW9 Binding
- **GWT**: gwt-0019 (init-becomes-control-plane-api)
- **Bridge operations**: AwaitRequest, AllocateProjectId, ProvisionProject, SendResponse, ResetPhase, Terminate
- **Key verifiers**: UniqueProjectIds, StoragePrefixProvisionedForEachProject, NoFilesystemDirsCreated

### Test Specification
**Given**: A control plane API service
**When**: POST /projects is called with project configuration
**Then**: Unique project_id allocated, storage prefix provisioned, Postgres record created; no .cw9/ directory anywhere

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_control_plane.py`
```python
"""Tests for control plane project provisioning — from gwt-0019 simulation traces."""
import pytest
from registry.hosted.control_plane import ControlPlane, InMemoryProjectStore
from registry.hosted.storage import InMemoryStorageClient


@pytest.fixture
def control_plane():
    return ControlPlane(
        project_store=InMemoryProjectStore(),
        storage=InMemoryStorageClient(),
    )


class TestCreateProject:
    def test_returns_unique_project_id(self, control_plane):
        r1 = control_plane.create_project(name="project-alpha")
        r2 = control_plane.create_project(name="project-beta")
        assert r1["project_id"] != r2["project_id"]

    def test_provisions_storage_prefix(self, control_plane):
        r = control_plane.create_project(name="project-alpha")
        assert "storage_prefix" in r
        assert r["project_id"] in r["storage_prefix"]

    def test_no_filesystem_directory_created(self, control_plane, tmp_path):
        """Verifier: NoFilesystemDirsCreated."""
        before = set(tmp_path.iterdir())
        control_plane.create_project(name="test")
        after = set(tmp_path.iterdir())
        assert before == after

    def test_project_persisted_in_store(self, control_plane):
        r = control_plane.create_project(name="proj")
        project = control_plane.get_project(r["project_id"])
        assert project["name"] == "proj"
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/control_plane.py`

### Success Criteria
- [ ] Unique project IDs generated
- [ ] Storage prefix provisioned
- [ ] No filesystem .cw9/ directory created

---

## Step 9: Pipeline Job DAG — Orchestration

### CW9 Binding
- **GWT**: gwt-0022 (pipeline-maps-to-job-dag)
- **Bridge operations**: SubmitRequest, BuildDAG, WaitForDAG, ScheduleStep, Terminate
- **Key verifiers**: OrderingInvariant, ExtractBeforeRegister, RegisterBeforeAllLoop, LoopBeforeBridge, BridgeBeforeGenTests, LoopJobsIndependent

### Test Specification
**Given**: A POST /projects/{id}/runs request with a list of GWT IDs
**When**: The control plane builds the execution plan
**Then**: Job DAG has correct ordering: extract→register→loop(parallel per GWT)→bridge(per GWT)→gen-tests(per GWT)

### TDD Cycle

#### Red: Write Failing Test
**File**: `python/tests/test_job_dag.py`
```python
"""Tests for pipeline job DAG construction — from gwt-0022 simulation traces."""
import pytest
from registry.hosted.job_dag import build_job_dag, JobDAG


class TestJobDAGConstruction:
    def test_extract_before_register(self):
        dag = build_job_dag(gwt_ids=["gwt-0001", "gwt-0002"])
        extract = dag.find_job("extract")
        register = dag.find_job("register")
        assert dag.is_before(extract, register)

    def test_register_before_all_loops(self):
        dag = build_job_dag(gwt_ids=["gwt-0001", "gwt-0002"])
        register = dag.find_job("register")
        for gwt_id in ["gwt-0001", "gwt-0002"]:
            loop = dag.find_job("loop", gwt_id=gwt_id)
            assert dag.is_before(register, loop)

    def test_loop_jobs_are_independent(self):
        """Verifier: LoopJobsIndependent — different GWT loops have no edge between them."""
        dag = build_job_dag(gwt_ids=["gwt-0001", "gwt-0002"])
        loop1 = dag.find_job("loop", gwt_id="gwt-0001")
        loop2 = dag.find_job("loop", gwt_id="gwt-0002")
        assert not dag.is_before(loop1, loop2)
        assert not dag.is_before(loop2, loop1)

    def test_loop_before_bridge(self):
        dag = build_job_dag(gwt_ids=["gwt-0001"])
        loop = dag.find_job("loop", gwt_id="gwt-0001")
        bridge = dag.find_job("bridge", gwt_id="gwt-0001")
        assert dag.is_before(loop, bridge)

    def test_bridge_before_gen_tests(self):
        dag = build_job_dag(gwt_ids=["gwt-0001"])
        bridge = dag.find_job("bridge", gwt_id="gwt-0001")
        gen_tests = dag.find_job("gen-tests", gwt_id="gwt-0001")
        assert dag.is_before(bridge, gen_tests)

    def test_ready_jobs_initially_extract_only(self):
        dag = build_job_dag(gwt_ids=["gwt-0001"])
        ready = dag.ready_jobs()
        assert len(ready) == 1
        assert ready[0].job_type == "extract"
```

#### Green: Minimal Implementation
**File**: `python/registry/hosted/job_dag.py`

### Success Criteria
- [ ] Correct ordering constraints
- [ ] Loop jobs parallelizable
- [ ] Ready jobs computed correctly

---

## Step 10: Light Worker Jobs — Extract, Bridge, Register, Ingest

### CW9 Binding
- **GWTs**: gwt-0012 (extract), gwt-0013 (bridge), gwt-0023 (register), gwt-0018 (ingest)
- **Key shared verifiers**: NoLLMCall, NoSubprocessCall (extract/register/ingest), BoundedExecution

### Test Specification
Each light worker wraps an existing function with download→execute→upload lifecycle. Tests verify:
1. Core function is called with correct inputs
2. Outputs uploaded to storage
3. No LLM or subprocess calls for light workers
4. Execution completes in bounded time

#### Red: Write Failing Tests
**File**: `python/tests/test_light_workers.py`
```python
"""Tests for light worker jobs — from gwt-0012, gwt-0013, gwt-0018, gwt-0023 traces."""
import json
import pytest
from registry.hosted.workers.extract_worker import run_extract_job
from registry.hosted.workers.bridge_worker import run_bridge_job
from registry.hosted.workers.register_worker import run_register_job
from registry.hosted.workers.ingest_worker import run_ingest_job
from registry.hosted.storage import InMemoryStorageClient
from registry.hosted.job_state import JobRecord


@pytest.fixture
def storage_with_dag():
    client = InMemoryStorageClient()
    dag = {"nodes": [], "edges": [], "closure": {}, "components": {}}
    client.put("proj-001/dag.json", json.dumps(dag).encode())
    return client


class TestExtractWorker:
    def test_uploads_rebuilt_dag(self, storage_with_dag, tmp_path):
        storage_with_dag.put("proj-001/schema/backend.json", b'{}')
        job = JobRecord(gwt_id="", job_type="extract")
        run_extract_job(
            storage=storage_with_dag,
            project_id="proj-001",
            workspace=tmp_path,
            job=job,
        )
        assert storage_with_dag.has("proj-001/dag.json")
        assert job.status.value == "passed"


class TestBridgeWorker:
    def test_produces_bridge_artifacts(self, storage_with_dag, tmp_path):
        # Provide a minimal spec file
        storage_with_dag.put("proj-001/specs/gwt-0001.tla", b"---- MODULE test ----\n====")
        storage_with_dag.put("proj-001/specs/gwt-0001_traces.json", b"[]")
        storage_with_dag.put("proj-001/specs/gwt-0001_sim_traces.json", b"[]")
        job = JobRecord(gwt_id="gwt-0001", job_type="bridge")
        run_bridge_job(
            storage=storage_with_dag,
            project_id="proj-001",
            workspace=tmp_path,
            job=job,
        )
        assert storage_with_dag.has("proj-001/bridge/gwt-0001_bridge_artifacts.json")
```

#### Green: Minimal Implementation
**Files**: `python/registry/hosted/workers/` package with one module per worker type.

Each worker follows the pattern:
1. `download_inputs(storage, project_id, workspace, artifacts)`
2. Reconstruct context
3. Call existing function (e.g., `run_bridge()`)
4. `upload_outputs(storage, project_id, workspace, output_artifacts)`
5. Update job status

### Success Criteria
- [ ] Each worker calls the existing core function
- [ ] Inputs downloaded, outputs uploaded
- [ ] Job status updated correctly

---

## Step 11: Heavy Worker Jobs — Loop, Crawl, Gen-Tests, GWT-Author

### CW9 Binding
- **GWTs**: gwt-0005/0006/0007 (SDK session), gwt-0008 (credentials), gwt-0009 (TLC isolation), gwt-0011 (sim traces), gwt-0014 (scheduler), gwt-0015/0016 (gen-tests), gwt-0017 (crawl), gwt-0025 (gwt-author), gwt-0026 (context query), gwt-0027 (retry prompt)

### Test Specification
Heavy workers add SDK session management and external tool execution atop the light worker pattern. Tests verify:
1. Single ClaudeSDKClient per GWT, reused across retries (gwt-0005)
2. safe_disconnect() in finally block (gwt-0006)
3. Independent workers share no state (gwt-0007)
4. CLAUDECODE env var from container environment (gwt-0008)
5. /tmp isolation per container (gwt-0009)
6. Simulation traces written and uploaded on PASS (gwt-0011)

#### Red: Write Failing Tests
**File**: `python/tests/test_heavy_workers.py`

Full test implementations are in the detail file at `2026-03-18-tdd-hosted-system-pipeline/step-11-heavy-workers.md`. The detail file contains 13 test classes covering all 128 bridge verifiers across 13 GWTs:

| GWT | Test Class | Verifiers | Coverage |
|-----|-----------|-----------|----------|
| gwt-0005 | TestSingleClientPerGWT | 9/9 | 100% |
| gwt-0006 | TestSafeDisconnectLifetime | 9/9 | 100% |
| gwt-0007 | TestGWTIndependence | 13/13 | 100% |
| gwt-0008 | TestCredentialInjection | 10/10 | 100% |
| gwt-0009 | TestTLCTempDirIsolation | 9/9 | 100% |
| gwt-0011 | TestSimTracesOnPass | 13/13 | 100% |
| gwt-0014 | TestLoopWorkerScheduling | 8/8 | 100% |
| gwt-0015 | TestGenTestsWorkerLifecycle | 15/15 | 100% |
| gwt-0016 | TestGenTests3PassStructure | 8/8 | 100% |
| gwt-0017 | TestCrawlWorker | 9/9 | 100% |
| gwt-0025 | TestGWTAuthorWorker | 12/12 | 100% |
| gwt-0026 | TestLoopContextQuery | 7/7 | 100% |
| gwt-0027 | TestRetryPromptBuilder | 6/6 | 100% |

### Success Criteria
- [ ] SDK session management verified (gwt-0005, gwt-0006, gwt-0007)
- [ ] Credentials sourced from environment (gwt-0008)
- [ ] TLC temp dir isolation verified (gwt-0009)
- [ ] Simulation traces captured on PASS (gwt-0011)
- [ ] Scheduler requirements verified (gwt-0014)
- [ ] Gen-tests worker lifecycle and 3-pass structure verified (gwt-0015, gwt-0016)
- [ ] Crawl worker extraction pipeline verified (gwt-0017)
- [ ] GWT-author worker verified (gwt-0025)
- [ ] Loop context query verified (gwt-0026)
- [ ] Retry prompt builder verified (gwt-0027)
- [ ] Worker isolation between concurrent GWTs
- [ ] All 128 bridge verifiers have at least one test assertion
- [ ] All simulation trace edge cases covered

---

## Integration Testing

After all steps are implemented, verify cross-behavior integration:

### End-to-End: Full Pipeline Run
```python
class TestFullPipelineIntegration:
    def test_create_project_and_run_pipeline(self):
        """Integration: POST /projects → POST /runs → jobs execute → artifacts produced."""
        # 1. Create project (gwt-0019)
        # 2. Upload schemas (gwt-0001 input)
        # 3. Submit run (gwt-0022 DAG)
        # 4. Execute extract job (gwt-0012)
        # 5. Execute register job (gwt-0023)
        # 6. Execute loop job (gwt-0005, gwt-0006, gwt-0010, gwt-0011)
        # 7. Execute bridge job (gwt-0013)
        # 8. Verify all artifacts in storage (gwt-0002 output)
        pass
```

### Cross-Worker State Consistency
```python
class TestCrossWorkerConsistency:
    def test_extract_output_is_register_input(self):
        """Extract worker's dag.json is consumed by register worker."""
        pass

    def test_loop_output_is_bridge_input(self):
        """Loop worker's .tla spec is consumed by bridge worker."""
        pass
```

## Verification

After implementation, re-verify the code:
```bash
cw9 ingest python/registry python/registry --incremental
cw9 stale python/registry
cw9 pipeline --skip-setup --gwt gwt-0004 python/registry  # spot-check
```

## Implementation Order Summary

| Step | Component | GWT(s) | New Files |
|------|-----------|--------|-----------|
| 1 | JobStatus + JobRecord | gwt-0010 | `hosted/job_state.py`, `tests/test_job_state.py` |
| 2 | ProjectContext.hosted() | gwt-0004 | modify `context.py`, `tests/test_context_hosted.py` |
| 3 | RegistryDag backends | gwt-0020 | `hosted/storage.py`, `tests/test_dag_hosted.py` |
| 4 | CrawlStore adapter | gwt-0021* | `hosted/crawl_backend.py`, `tests/test_crawl_hosted.py` |
| 5 | Object storage abstraction | gwt-0001, gwt-0002 | extend `hosted/storage.py`, `tests/test_worker_storage.py` |
| 6 | Worker lifecycle | gwt-0003 | `hosted/worker.py`, `tests/test_worker_lifecycle.py` |
| 7 | write_result_hosted() | gwt-0024 | `hosted/results.py`, `tests/test_write_result_hosted.py` |
| 8 | POST /projects | gwt-0019 | `hosted/control_plane.py`, `tests/test_control_plane.py` |
| 9 | Job DAG orchestration | gwt-0022 | `hosted/job_dag.py`, `tests/test_job_dag.py` |
| 10 | Light workers | gwt-0012,0013,0018,0023 | `hosted/workers/*.py`, `tests/test_light_workers.py` |
| 11 | Heavy workers | gwt-0005-0009,0011,0014-0017,0025-0027 | `hosted/workers/*.py`, `tests/test_heavy_workers.py` |

\* gwt-0021 failed verification — planned manually from research doc.

## References

- Research: `thoughts/searchable/shared/research/2026-03-18-hosted-system-pipeline.md`
- Verified specs: `python/registry/.cw9/specs/`
- Bridge artifacts: `python/registry/.cw9/bridge/`
- Simulation traces: `python/registry/.cw9/specs/*_sim_traces.json`
- Existing tests: `python/tests/` (38 files, patterns documented above)
- CrawlStore analysis: research doc §4 + crawl_store.py (23 methods, 7 tables)
- ProjectContext analysis: context.py (4 factory methods, 12 fields)
- RegistryDag analysis: dag.py (load/save/add_node/add_edge/query_relevant + 13 more methods)
