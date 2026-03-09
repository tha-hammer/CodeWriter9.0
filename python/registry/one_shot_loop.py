"""One-Shot Loop — Phase 3 of CodeWriter9.0 bootstrap.

Core algorithm: registry context → LLM prompt → PlusCal extraction →
compile → compose → TLC verify → counterexample translation → route.

The LLM writes PlusCal ONLY. This module handles compilation, composition,
and verification. Counterexample traces are translated back to PlusCal-level
concepts (variable names, process labels) for human/LLM readability.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from registry.composer import compose_from_files, parse_tla_file, ComposedModule
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind, QueryResult


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class LoopResult(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    FAIL = "fail"


class LoopState(str, Enum):
    IDLE = "idle"
    QUERYING_CONTEXT = "querying_context"
    PROMPTING_LLM = "prompting_llm"
    EXTRACTING_FRAGMENT = "extracting_fragment"
    COMPILING = "compiling"
    COMPOSING = "composing"
    VERIFYING = "verifying"
    TRANSLATING_ERROR = "translating_error"
    ROUTING = "routing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TLCResult:
    """Result of a TLC model-checking run."""
    success: bool
    states_found: int = 0
    states_distinct: int = 0
    counterexample: str | None = None
    raw_output: str = ""
    error_message: str | None = None


@dataclass
class CounterexampleTrace:
    """A parsed TLC counterexample with PlusCal-level translations."""
    raw_trace: str
    states: list[dict[str, Any]] = field(default_factory=list)
    violated_invariant: str | None = None
    pluscal_summary: str = ""


@dataclass
class ContextBundle:
    """Assembled context for an LLM prompt."""
    behavior_id: str
    behavior: Node | None = None
    transitive_deps: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    schemas: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    existing_specs: list[str] = field(default_factory=list)


@dataclass
class LoopStatus:
    """Status of a one-shot loop iteration."""
    state: LoopState = LoopState.IDLE
    consecutive_failures: int = 0
    result: LoopResult | None = None
    tlc_result: TLCResult | None = None
    counterexample: CounterexampleTrace | None = None
    error: str | None = None
    compiled_spec_path: Path | None = None


# ---------------------------------------------------------------------------
# Registry Context Query
# ---------------------------------------------------------------------------

def query_context(dag: RegistryDag, behavior_id: str) -> ContextBundle:
    """Given a GWT behavior ID, query the DAG for all transitive dependencies.

    Assembles schemas, templates, and existing specs into a context bundle
    suitable for LLM prompt construction.
    """
    if behavior_id not in dag.nodes:
        raise ValueError(f"Behavior {behavior_id!r} not found in registry")

    query = dag.query_relevant(behavior_id)
    bundle = ContextBundle(behavior_id=behavior_id)
    bundle.behavior = dag.nodes[behavior_id]

    for dep_id in query.transitive_deps:
        node = dag.nodes.get(dep_id)
        if node is None:
            continue
        bundle.transitive_deps.append(node)

        # Classify by kind
        if node.kind == NodeKind.SPEC:
            if node.path:
                bundle.templates.append(node.path)
        elif node.kind == NodeKind.RESOURCE:
            if node.schema:
                bundle.schemas.append(node.schema)
            if node.path and node.path.endswith(".tla"):
                bundle.existing_specs.append(node.path)

    bundle.edges = query.all_edges
    return bundle


def format_prompt_context(bundle: ContextBundle) -> str:
    """Format a ContextBundle into text suitable for an LLM prompt."""
    sections: list[str] = []

    # Behavior description
    if bundle.behavior:
        b = bundle.behavior
        sections.append(
            f"## Target Behavior: {bundle.behavior_id}\n"
            f"Given: {b.given}\n"
            f"When: {b.when}\n"
            f"Then: {b.then}\n"
        )

    # Transitive dependencies
    if bundle.transitive_deps:
        dep_lines = []
        for node in bundle.transitive_deps:
            dep_lines.append(f"- {node.id} ({node.kind.value}): {node.name} — {node.description}")
        sections.append("## Transitive Dependencies\n" + "\n".join(dep_lines))

    # Available templates
    if bundle.templates:
        sections.append("## Available Templates\n" + "\n".join(f"- {t}" for t in bundle.templates))

    # Existing specs
    if bundle.existing_specs:
        sections.append("## Existing Specs\n" + "\n".join(f"- {s}" for s in bundle.existing_specs))

    # Dependency edges
    if bundle.edges:
        edge_lines = []
        for e in bundle.edges:
            edge_lines.append(f"- {e.from_id} --{e.edge_type.value}--> {e.to_id}")
        sections.append("## Dependency Edges\n" + "\n".join(edge_lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# PlusCal Fragment Extraction
# ---------------------------------------------------------------------------

# Pattern 1: PlusCal algorithm block
_PCAL_ALGORITHM_RE = re.compile(
    r'(\(\*\s*)?--algorithm\s+\w+.*?end\s+algorithm\s*;?\s*(\*\))?',
    re.DOTALL | re.IGNORECASE,
)

# Pattern 2: Fenced code block with tla/pluscal marker
_FENCED_TLA_RE = re.compile(
    r'```(?:tla\+?|pluscal|pcal)\s*\n(.*?)```',
    re.DOTALL | re.IGNORECASE,
)

# Pattern 3: Generic fenced code block containing PlusCal markers
_FENCED_GENERIC_RE = re.compile(
    r'```\s*\n(.*?--algorithm\s+.*?end\s+algorithm.*?)```',
    re.DOTALL | re.IGNORECASE,
)


def extract_pluscal(llm_response: str) -> str | None:
    """Parse LLM response to extract PlusCal code.

    Tries multiple patterns in order:
    0. Complete TLA+ module (starts with ---- MODULE or contains it)
    1. Fenced code block with tla/pluscal language marker
    2. Generic fenced code block containing PlusCal markers
    3. Direct --algorithm...end algorithm block

    Returns the extracted PlusCal fragment or None if not found.
    When a complete TLA+ module is found, returns the full module text
    (needed for pcal.trans which requires MODULE/EXTENDS/CONSTANTS).
    """
    # Check for a complete TLA+ module first — if the LLM output the whole
    # module (MODULE ... ====), use it as-is since pcal.trans needs the
    # full module wrapper, not just the algorithm block.
    module_match = re.search(
        r'(-{4,}\s*MODULE\s+\w+\s*-{4,}.*?={4,})',
        llm_response,
        re.DOTALL,
    )
    if module_match and '--algorithm' in module_match.group(1).lower():
        return module_match.group(1).strip()

    # Try fenced code blocks (most structured)
    m = _FENCED_TLA_RE.search(llm_response)
    if m:
        content = m.group(1).strip()
        # If the fenced block contains a full module, return it
        if re.match(r'-{4,}\s*MODULE', content):
            return content
        return content

    # Try generic fenced block with algorithm markers
    m = _FENCED_GENERIC_RE.search(llm_response)
    if m:
        return m.group(1).strip()

    # Try direct algorithm block
    m = _PCAL_ALGORITHM_RE.search(llm_response)
    if m:
        return m.group(0).strip()

    return None


# ---------------------------------------------------------------------------
# Compile → Compose → TLC Pipeline
# ---------------------------------------------------------------------------

_TLA2TOOLS_JAR = "tools/tla2tools.jar"


def _find_tla2tools(project_root: str | Path | None = None) -> str:
    """Locate the tla2tools.jar file."""
    if project_root:
        jar = Path(project_root) / _TLA2TOOLS_JAR
        if jar.exists():
            return str(jar)

    # Try relative to cwd
    jar = Path(_TLA2TOOLS_JAR)
    if jar.exists():
        return str(jar)

    # Try environment variable
    env_jar = os.environ.get("TLA2TOOLS_JAR")
    if env_jar and Path(env_jar).exists():
        return env_jar

    raise FileNotFoundError(
        f"Cannot find tla2tools.jar. Set TLA2TOOLS_JAR env var or place at {_TLA2TOOLS_JAR}"
    )


def compile_pluscal(
    tla_path: str | Path,
    project_root: str | Path | None = None,
) -> tuple[bool, str]:
    """Compile PlusCal to TLA+ using pcal.trans.

    Returns (success, output_or_error).
    """
    jar = _find_tla2tools(project_root)
    tla_path = Path(tla_path)

    result = subprocess.run(
        ["java", "-cp", jar, "pcal.trans", str(tla_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = result.stdout + result.stderr
    success = result.returncode == 0 and "error" not in output.lower().split("translation")[0]
    return success, output


def run_tlc(
    tla_path: str | Path,
    cfg_path: str | Path | None = None,
    project_root: str | Path | None = None,
    workers: str = "auto",
) -> TLCResult:
    """Run TLC model checker on a TLA+ spec.

    Returns a TLCResult with success status and counterexample if found.
    """
    jar = _find_tla2tools(project_root)
    tla_path = Path(tla_path)

    cmd = [
        "java", "-XX:+UseParallelGC",
        "-cp", jar,
        "tlc2.TLC",
        str(tla_path),
        "-workers", workers,
        "-nowarning",
    ]
    if cfg_path:
        cmd.extend(["-config", str(cfg_path)])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    raw = result.stdout + result.stderr
    tlc_result = TLCResult(
        success=result.returncode == 0,
        raw_output=raw,
    )

    # Parse state counts
    states_m = re.search(r'(\d+)\s+states\s+generated.*?(\d+)\s+distinct', raw)
    if states_m:
        tlc_result.states_found = int(states_m.group(1))
        tlc_result.states_distinct = int(states_m.group(2))

    # Check for invariant violations
    if "Error:" in raw or "Invariant" in raw and "is violated" in raw:
        tlc_result.success = False
        # Extract counterexample
        ce_match = re.search(
            r'(Error:.*?(?:State\s+\d+:.*?)*)(?:\n\n|\Z)',
            raw,
            re.DOTALL,
        )
        if ce_match:
            tlc_result.counterexample = ce_match.group(1).strip()
        error_match = re.search(r'Error:\s*(.+)', raw)
        if error_match:
            tlc_result.error_message = error_match.group(1).strip()

    # Also check for "Model checking completed. No error has been found."
    if "No error has been found" in raw:
        tlc_result.success = True

    return tlc_result


def compile_compose_verify(
    pluscal_fragment: str,
    module_name: str,
    cfg_text: str,
    compose_with: str | Path | None = None,
    dag: RegistryDag | None = None,
    project_root: str | Path | None = None,
) -> tuple[TLCResult, Path]:
    """Full pipeline: write PlusCal → compile → optionally compose → TLC.

    Returns (tlc_result, tla_path).
    """
    project_root = Path(project_root) if project_root else Path.cwd()

    # Write PlusCal to temp file
    tmpdir = Path(tempfile.mkdtemp(prefix="cw9_"))
    tla_path = tmpdir / f"{module_name}.tla"
    cfg_path = tmpdir / f"{module_name}.cfg"

    tla_path.write_text(pluscal_fragment)
    cfg_path.write_text(cfg_text)

    # Compile PlusCal → TLA+
    ok, compile_output = compile_pluscal(tla_path, project_root)
    if not ok:
        return TLCResult(
            success=False,
            raw_output=compile_output,
            error_message=f"PlusCal compilation failed: {compile_output}",
        ), tla_path

    # Optionally compose with another spec
    if compose_with:
        composed = compose_from_files(
            tla_path, compose_with,
            dag=dag,
            module_name=f"{module_name}_composed",
        )
        composed_path = tmpdir / f"{module_name}_composed.tla"
        composed_path.write_text(composed.text)
        # Generate composed cfg
        composed_cfg = tmpdir / f"{module_name}_composed.cfg"
        composed_cfg.write_text(cfg_text)  # Use same config as base
        tla_path = composed_path
        cfg_path = composed_cfg

    # Run TLC
    tlc_result = run_tlc(tla_path, cfg_path, project_root)
    return tlc_result, tla_path


# ---------------------------------------------------------------------------
# Counterexample Translator
# ---------------------------------------------------------------------------

# TLC state line patterns
_STATE_HEADER_RE = re.compile(r'State\s+(\d+):\s*<(.+?)>')
_VAR_ASSIGN_RE = re.compile(r'/\\\s+(\w+)\s*=\s*(.+)')
_INVARIANT_VIOLATED_RE = re.compile(r'Invariant\s+(\w+)\s+is\s+violated')
_BACK_TO_STATE_RE = re.compile(r'Back\s+to\s+state\s+(\d+)')

# PlusCal label/pc mapping
_PC_LABEL_RE = re.compile(r'pc\s*=\s*(?:\[.*?"main"\s*\|->\s*)?["\']?(\w+)["\']?')


def parse_counterexample(raw_trace: str) -> CounterexampleTrace:
    """Parse a TLC counterexample trace into structured states.

    Extracts state numbers, variable assignments, and the violated invariant.
    """
    trace = CounterexampleTrace(raw_trace=raw_trace)

    # Find violated invariant
    inv_m = _INVARIANT_VIOLATED_RE.search(raw_trace)
    if inv_m:
        trace.violated_invariant = inv_m.group(1)

    # Parse states
    current_state: dict[str, Any] | None = None
    for line in raw_trace.split("\n"):
        line = line.strip()

        # State header
        header_m = _STATE_HEADER_RE.match(line)
        if header_m:
            if current_state is not None:
                trace.states.append(current_state)
            current_state = {
                "state_num": int(header_m.group(1)),
                "label": header_m.group(2),
                "vars": {},
            }
            continue

        # Variable assignment within a state
        if current_state is not None:
            var_m = _VAR_ASSIGN_RE.match(line)
            if var_m:
                current_state["vars"][var_m.group(1)] = var_m.group(2).strip()

        # Back-to-state (lasso)
        back_m = _BACK_TO_STATE_RE.match(line)
        if back_m:
            if current_state is not None:
                trace.states.append(current_state)
                current_state = None

    if current_state is not None:
        trace.states.append(current_state)

    return trace


def translate_counterexample(
    trace: CounterexampleTrace,
    variable_descriptions: dict[str, str] | None = None,
) -> str:
    """Translate a parsed counterexample to PlusCal-level natural language.

    Focuses on:
    - PlusCal labels (from pc variable) rather than TLA+ internal names
    - Variable names as written in PlusCal (not the generated TLA+ names)
    - State transitions in terms of the algorithm's labels
    """
    if not trace.states:
        return "No states in counterexample trace."

    var_desc = variable_descriptions or {}
    lines: list[str] = []

    if trace.violated_invariant:
        lines.append(f"INVARIANT VIOLATED: {trace.violated_invariant}")
        lines.append("")

    lines.append("State trace (PlusCal-level):")
    lines.append("")

    for state in trace.states:
        state_num = state.get("state_num", "?")
        label = state.get("label", "unknown")
        lines.append(f"  Step {state_num}: {label}")

        vars_dict = state.get("vars", {})
        for var_name, var_value in vars_dict.items():
            # Skip internal TLA+ variables (pc, ProcSet, etc.)
            if var_name in ("ProcSet",):
                continue

            # Translate pc to PlusCal label
            if var_name == "pc":
                pc_m = _PC_LABEL_RE.match(f"pc = {var_value}")
                if pc_m:
                    pluscal_label = pc_m.group(1)
                    lines.append(f"    at label: {pluscal_label}")
                    continue

            # Use description if available, otherwise show raw
            desc = var_desc.get(var_name, "")
            if desc:
                lines.append(f"    {var_name} ({desc}) = {var_value}")
            else:
                lines.append(f"    {var_name} = {var_value}")

        lines.append("")

    trace.pluscal_summary = "\n".join(lines)
    return trace.pluscal_summary


# ---------------------------------------------------------------------------
# Pass / Retry / Fail Router
# ---------------------------------------------------------------------------

def route_result(
    tlc_result: TLCResult,
    consecutive_failures: int,
) -> tuple[LoopResult, str]:
    """Route based on TLC result and failure history.

    Deterministic routing:
    - TLC passes → PASS (done)
    - First TLC failure → RETRY (with counterexample feedback)
    - Second consecutive failure → FAIL (requirements inconsistency)

    Returns (result, message).
    """
    if tlc_result.success:
        return LoopResult.PASS, (
            f"TLC verification passed. "
            f"{tlc_result.states_found} states generated, "
            f"{tlc_result.states_distinct} distinct."
        )

    if consecutive_failures >= 1:
        # This is the second consecutive failure
        return LoopResult.FAIL, (
            f"Requirements inconsistency detected after {consecutive_failures + 1} "
            f"consecutive failures. Last error: {tlc_result.error_message or 'unknown'}. "
            f"The specification likely has contradictory requirements — do not retry."
        )

    # First failure — retry with counterexample
    msg = f"TLC verification failed (attempt {consecutive_failures + 1}). "
    if tlc_result.counterexample:
        msg += f"Counterexample available for feedback."
    elif tlc_result.error_message:
        msg += f"Error: {tlc_result.error_message}"
    else:
        msg += "No counterexample captured."

    return LoopResult.RETRY, msg


# ---------------------------------------------------------------------------
# One-Shot Loop Orchestrator
# ---------------------------------------------------------------------------

@dataclass
class OneShotLoop:
    """Orchestrates the one-shot loop lifecycle.

    States: idle → querying_context → prompting_llm → extracting_fragment →
            compiling → composing → verifying → translating_error → routing →
            done | failed

    The loop does NOT call the LLM directly — it prepares context and
    processes responses. The caller is responsible for the LLM interaction.
    """
    dag: RegistryDag
    project_root: str | Path = "."
    status: LoopStatus = field(default_factory=LoopStatus)
    _context: ContextBundle | None = field(default=None, repr=False)
    _compose_with: str | Path | None = field(default=None, repr=False)

    def query(self, behavior_id: str) -> ContextBundle:
        """Step 1: Query registry context for a behavior."""
        self.status.state = LoopState.QUERYING_CONTEXT
        self._context = query_context(self.dag, behavior_id)
        self.status.state = LoopState.PROMPTING_LLM
        return self._context

    def format_prompt(self) -> str:
        """Step 2: Format context into an LLM prompt."""
        if self._context is None:
            raise RuntimeError("Must call query() before format_prompt()")
        return format_prompt_context(self._context)

    def process_response(
        self,
        llm_response: str,
        module_name: str,
        cfg_text: str,
        compose_with: str | Path | None = None,
        variable_descriptions: dict[str, str] | None = None,
    ) -> LoopStatus:
        """Steps 3-7: Extract → compile → compose → verify → route.

        Returns the final LoopStatus.
        """
        self._compose_with = compose_with

        # Step 3: Extract PlusCal
        self.status.state = LoopState.EXTRACTING_FRAGMENT
        fragment = extract_pluscal(llm_response)
        if fragment is None:
            self.status.state = LoopState.FAILED
            self.status.error = "No PlusCal fragment found in LLM response"
            self.status.result = LoopResult.FAIL
            return self.status

        # Steps 4-5: Compile → Compose → Verify
        self.status.state = LoopState.COMPILING
        tlc_result, tla_path = compile_compose_verify(
            pluscal_fragment=fragment,
            module_name=module_name,
            cfg_text=cfg_text,
            compose_with=compose_with,
            dag=self.dag,
            project_root=self.project_root,
        )
        self.status.tlc_result = tlc_result
        self.status.compiled_spec_path = tla_path

        # Step 6: Translate counterexample if failed
        if not tlc_result.success and tlc_result.counterexample:
            self.status.state = LoopState.TRANSLATING_ERROR
            trace = parse_counterexample(tlc_result.counterexample)
            translate_counterexample(trace, variable_descriptions)
            self.status.counterexample = trace

        # Step 7: Route
        self.status.state = LoopState.ROUTING
        result, message = route_result(
            tlc_result, self.status.consecutive_failures
        )
        self.status.result = result

        if result == LoopResult.PASS:
            self.status.state = LoopState.DONE
            self.status.consecutive_failures = 0
        elif result == LoopResult.RETRY:
            self.status.state = LoopState.IDLE  # Ready for next attempt
            self.status.consecutive_failures += 1
        else:  # FAIL
            self.status.state = LoopState.FAILED
            self.status.error = message

        return self.status
