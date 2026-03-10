"""LLM-in-the-loop test generation from bridge artifacts.

Parallel to cw9 loop (GWT → PlusCal → TLC):
  Bridge artifacts + API context → LLM → pytest file → pytest verifies → retry

The bridge artifacts constrain the LLM's generation the same way schemas
constrain PlusCal generation. The TLA+ compiler provides partial translations
as prompt hints, but the LLM handles the semantic gap: binding TLA+ invariants
to actual Python API calls.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from registry.tla_compiler import compile_assertions


@dataclass
class TestGenContext:
    """Everything the LLM needs to generate tests.

    v5: Context stack ranked by impact on test quality:
      1. simulation_traces — concrete verified scenarios (PRIMARY)
      2. api_context — method signatures + return types
      3. gwt_text + bridge_artifacts + compiler_hints — intent + starting expressions
      4. tla_spec_text — complete state machine (lossless)
      5. structural patterns — built into prompt templates (not stored here)
    """
    gwt_id: str
    gwt_text: dict          # {"given": ..., "when": ..., "then": ...}
    module_name: str
    bridge_artifacts: dict   # Full bridge JSON
    compiler_hints: dict     # verifier_name → {"python_expr", "original_tla", "variables_used"}
    api_context: str         # Target module imports + class/method signatures
    test_scenarios: list[dict[str, Any]]     # From counterexample trace pipeline (Phase 5A)
    simulation_traces: list[list[dict[str, Any]]]  # v5: From TLC -simulate (PRIMARY context)
    tla_spec_text: str = ""  # v5: Verified TLA+ spec content (full picture)
    output_dir: Path = Path(".")
    python_dir: Path = Path(".")


@dataclass
class VerifyResult:
    """Result of mechanical test verification."""
    passed: bool
    stage: str               # "compile", "collect", "run"
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    attempt: int = 0


def build_compiler_hints(bridge_artifacts: dict) -> dict:
    """Run the TLA+ compiler on bridge verifier conditions."""
    verifiers = bridge_artifacts.get("verifiers", {})
    compiled = compile_assertions(verifiers)
    hints = {}
    for vname, ca in compiled.items():
        hints[vname] = {
            "python_expr": ca.python_expr,
            "original_tla": ca.original_tla,
            "variables_used": ca.variables_used,
        }
    return hints


def discover_api_context(python_dir: Path, module_name: str) -> str:
    """Extract import paths + class/method signatures for the target module.

    Searches for files matching the module name, then falls back to core
    registry files (dag.py, types.py) which contain the fundamental API
    surface that all generated tests need.
    """
    module_name_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', module_name).lower()
    candidates = list(python_dir.glob(f"registry/*{module_name_snake}*.py"))
    if not candidates:
        candidates = list(python_dir.glob(f"registry/**/*{module_name_snake}*.py"))

    # Always include core registry files — they contain the fundamental API
    # (RegistryDag, Node, Edge, EdgeType, query_affected_tests, query_impact, etc.)
    core_files = ["dag.py", "types.py"]
    registry_dir = python_dir / "registry"
    for core in core_files:
        core_path = registry_dir / core
        if core_path.exists() and core_path not in candidates:
            candidates.append(core_path)

    if not candidates:
        return f"# No source found for module '{module_name}' in {python_dir}/registry/"

    lines = [f"# API context for module: {module_name}"]
    for src_path in candidates[:7]:
        lines.append(f"\n# --- {src_path.name} ---")
        try:
            source = src_path.read_text()
            for line in source.splitlines():
                stripped = line.strip()
                if (stripped.startswith(("import ", "from "))
                    or stripped.startswith(("class ", "def "))
                    or stripped.startswith("@")):
                    lines.append(line)
        except OSError:
            lines.append(f"# Could not read {src_path}")
    return "\n".join(lines)


def build_test_plan_prompt(ctx: TestGenContext) -> str:
    """Pass 1: Generate test plan from simulation traces + API context.

    v5: Context stack ranked by impact on test quality:
      1. TLC simulation traces — concrete verified scenarios (PRIMARY)
      2. Python API signatures — binding targets
      3. GWT text + compiler hints — intent + expression starting points
      4. TLA+ spec — full state machine (if available)
      5. Structural patterns — fixture/assertion templates
    """
    from registry.traces import format_traces_for_prompt, load_simulation_traces

    verifiers = ctx.bridge_artifacts.get("verifiers", {})
    invariant_names = list(verifiers.keys())

    sections = [
        "Generate a test plan for verifying the following behavior.\n",
        "## Behavior (GWT)",
        f"  Given: {ctx.gwt_text.get('given', '')}",
        f"  When:  {ctx.gwt_text.get('when', '')}",
        f"  Then:  {ctx.gwt_text.get('then', '')}\n",
    ]

    # ── RANK 1: SIMULATION TRACES (the WHAT) ──────────────────────────
    if ctx.simulation_traces:
        sim = load_simulation_traces(ctx.simulation_traces, invariant_names)
        sections.append(format_traces_for_prompt(sim, invariant_names))
        sections.append(
            "**Your task**: Translate each trace above into a pytest test.\n"
            "- The Init state defines your fixture (nodes, edges, artifacts)\n"
            "- The actions define your API calls\n"
            "- The final state defines your expected assertions\n"
            "- ALL invariants hold at every state — verify them\n"
            "- Do NOT invent topologies from scratch — derive from traces\n"
        )

    # ── RANK 2: PYTHON API (the HOW) ──────────────────────────────────
    sections.append(f"## Available Python API\n{ctx.api_context}\n")

    # ── RANK 3: GWT + BRIDGE + COMPILER HINTS (the WHY) ──────────────
    if verifiers:
        sections.append("## Invariant Translations (starting points, NOT final assertions)")
        for vname, vdata in verifiers.items():
            conditions = vdata.get("conditions", []) if isinstance(vdata, dict) else []
            applies_to = vdata.get("applies_to", []) if isinstance(vdata, dict) else []
            sections.append(f"  {vname}:")
            sections.append(f"    TLA+ condition: {conditions}")
            sections.append(f"    Applies to: {applies_to}")
            if vname in ctx.compiler_hints:
                hint = ctx.compiler_hints[vname]
                sections.append(f"    Partial Python: {hint['python_expr']}")
                sections.append(
                    f"    ↑ Variables {hint['variables_used']} need binding to real API calls"
                )
        sections.append("")

    # ── RANK 4: TLA+ SPEC (the FULL PICTURE) ─────────────────────────
    if ctx.tla_spec_text:
        sections.append(f"## Verified TLA+ Spec\n```tla\n{ctx.tla_spec_text}\n```\n")

    # ── RANK 5: STRUCTURAL PATTERNS (the FORM) ───────────────────────
    sections.append(
        "## Structural Patterns\n"
        "```python\n"
        "# Pattern: fixture construction from trace Init state\n"
        "def _make_dag(nodes, edges, artifacts):\n"
        "    dag = RegistryDag()\n"
        "    for nid in nodes:\n"
        "        dag.add_node(Node.behavior(nid, nid, 'g', 'w', 't'))\n"
        "    for src, dst in edges:\n"
        "        dag.add_edge(Edge(src, dst, EdgeType.IMPORTS))\n"
        "    dag.test_artifacts = artifacts\n"
        "    return dag\n\n"
        "# Pattern: invariant verification\n"
        "def test_invariant(dag):\n"
        "    result = dag.some_query('node_id')\n"
        "    assert property_of(result)\n\n"
        "# Pattern: error case\n"
        "def test_invalid_input(dag):\n"
        "    with pytest.raises(NodeNotFoundError):\n"
        "        dag.some_query('nonexistent')\n"
        "```\n"
    )

    # Fallback: if no simulation traces, fall back to counterexample scenarios
    if not ctx.simulation_traces and ctx.test_scenarios:
        sections.append("### Trace-derived Scenarios (from TLC counterexamples)")
        for s in ctx.test_scenarios:
            sections.append(f"  - {s.get('name', 'unnamed')}: {s.get('expected_outcome', '')}")
        sections.append("")

    # ── INSTRUCTIONS ──────────────────────────────────────────────────
    if ctx.simulation_traces:
        sections.append(
            "## Instructions\n"
            "Produce a structured test plan with:\n"
            "1. **Trace-derived fixtures**: For each simulation trace, construct a fixture "
            "matching the Init state (specific nodes, edges, test_artifacts).\n"
            "2. **Trace-derived tests**: For each trace, a test that:\n"
            "   - Builds the fixture from Init state variables\n"
            "   - Calls API methods matching the action sequence\n"
            "   - Asserts the result matches the final state\n"
            "   - Verifies ALL invariants hold\n"
            "3. **Invariant verifiers**: For each verifier, a dedicated test method that:\n"
            "   - Exercises the invariant across ≥2 trace-derived topologies\n"
            "   - Binds TLA+ variables to real API calls (see Partial Python hints above)\n"
            "4. **Edge cases**: Isolated nodes, empty DAGs, missing artifacts, diamond patterns\n"
            "   (derive from traces where possible, invent minimally where not)\n"
        )
    else:
        sections.append(
            "## Instructions\n"
            "Produce a structured test plan with:\n"
            "1. **Fixtures**: What DAG topologies or state objects to construct. "
            "Include specific nodes, edges, and test_artifacts mappings.\n"
            "2. **Invariant verifiers**: For each verifier, describe:\n"
            "   - Which API method(s) to call\n"
            "   - How to bind TLA+ state variables to API results\n"
            "   - What assertion to make\n"
            "3. **Scenario tests**: Concrete test cases covering:\n"
            "   - Happy path (invariant holds)\n"
            "   - Edge cases (empty DAG, isolated nodes, diamond topologies)\n"
            "   - Boundary conditions\n"
        )

    return "\n".join(sections)


def build_review_prompt(test_plan: str, ctx: TestGenContext) -> str:
    """Pass 2: Review the test plan for semantic correctness."""
    return (
        "Review this test plan for semantic correctness.\n\n"
        f"## Test Plan\n{test_plan}\n\n"
        f"## Bridge Verifiers (ground truth)\n"
        f"{json.dumps(ctx.bridge_artifacts.get('verifiers', {}), indent=2)}\n\n"
        "## Review Criteria\n"
        "1. Does each verifier test actually verify the TLA+ invariant's *intent*, "
        "not just its syntax?\n"
        "2. Are the fixture topologies sufficient to exercise the invariant?\n"
        "3. Are the API bindings correct? (right method, right arguments, right return type)\n"
        "4. Are edge cases covered? (empty set, single node, missing artifacts)\n\n"
        "Output the revised test plan with corrections. If the plan is correct, "
        "output it unchanged with a note that it passed review.\n"
    )


def build_codegen_prompt(reviewed_plan: str, ctx: TestGenContext) -> str:
    """Pass 3: Emit a complete pytest file from the reviewed plan."""
    return (
        f"Generate a complete, runnable pytest file from this test plan.\n\n"
        f"## Reviewed Test Plan\n{reviewed_plan}\n\n"
        f"## API Context (EXACT imports to use)\n{ctx.api_context}\n\n"
        f"## Requirements\n"
        f"- Module: {ctx.module_name}, GWT ID: {ctx.gwt_id}\n"
        f"- CRITICAL: Use EXACT import paths from the API Context section above.\n"
        f"  Use `from registry.dag import RegistryDag` NOT `from {ctx.module_name}.dag`\n"
        f"  Use `from registry.types import Node, Edge, EdgeType` for type imports\n"
        f"- Use `import pytest` and relevant imports from the API context\n"
        f"- Each verifier becomes a test function or method with a real assertion\n"
        f"- Fixtures construct concrete DAG/state objects (not mocks)\n"
        f"- Include docstrings referencing the TLA+ invariant being tested\n"
        f"- Code must pass `compile()`, `pytest --collect-only`, and `pytest -x`\n"
        f"- Output ONLY the Python code, no markdown fences or explanation\n"
    )


def build_retry_prompt(
    previous_code: str,
    verify_result: VerifyResult,
    ctx: TestGenContext,
) -> str:
    """Build retry prompt from previous attempt's errors."""
    return (
        f"The previous test file failed at the '{verify_result.stage}' stage.\n\n"
        f"## Previous code\n```python\n{previous_code}\n```\n\n"
        f"## Errors\n{chr(10).join(verify_result.errors)}\n\n"
        f"## stderr\n{verify_result.stderr[:2000]}\n\n"
        f"## Available API (EXACT imports)\n{ctx.api_context}\n\n"
        f"## Instructions\n"
        f"Fix the errors and output the corrected Python file.\n"
        f"CRITICAL: Use EXACT import paths: `from registry.dag import RegistryDag`, "
        f"`from registry.types import Node, Edge, EdgeType`.\n"
        f"Do NOT create mock classes — use the real API from the imports above.\n"
        f"Output ONLY the Python code, no markdown fences or explanation.\n"
    )


def verify_test_file(
    test_path: Path, python_dir: Path,
    collect_timeout: int = 30, run_timeout: int = 120,
) -> VerifyResult:
    """Three-stage mechanical verification of a generated test file.

    Stage 1: compile() — syntax check
    Stage 2: pytest --collect-only — test discovery
    Stage 3: pytest -x — run tests (fail fast)
    """
    code = test_path.read_text()

    # Stage 1: Compile
    try:
        compile(code, str(test_path), "exec")
    except SyntaxError as e:
        return VerifyResult(
            passed=False, stage="compile",
            errors=[f"SyntaxError: {e.msg} (line {e.lineno})"],
        )

    # Stage 2: Collect
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "--collect-only", "-q"],
        capture_output=True, text=True, cwd=str(python_dir), timeout=collect_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(
            passed=False, stage="collect",
            errors=[f"pytest --collect-only failed (rc={result.returncode})"],
            stdout=result.stdout, stderr=result.stderr,
        )

    # Stage 3: Run
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-x", "-v"],
        capture_output=True, text=True, cwd=str(python_dir), timeout=run_timeout,
    )
    if result.returncode != 0:
        return VerifyResult(
            passed=False, stage="run",
            errors=[f"pytest -x failed (rc={result.returncode})"],
            stdout=result.stdout, stderr=result.stderr,
        )

    return VerifyResult(passed=True, stage="run", stdout=result.stdout)


def _extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response, stripping markdown fences if present.

    Handles multiple code blocks by extracting the largest one, and deduplicates
    content if the response contains repeated code (e.g., from SDK returning
    both AssistantMessage and ResultMessage with the same content).
    """
    text = response.strip()

    # If there are markdown fences, extract the largest fenced block
    import re
    fenced = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if fenced:
        text = max(fenced, key=len).strip()
    else:
        # Strip single opening/closing fences
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Deduplicate: if the code is exactly repeated, take just the first copy
    half = len(text) // 2
    if half > 100:  # Only for substantial code
        first_half = text[:half].rstrip()
        second_half = text[half:].lstrip()
        if first_half == second_half:
            text = first_half

    return text


_TEST_GEN_SYSTEM_PROMPT = (
    "You are a Python test generation expert. You generate complete, runnable "
    "pytest test files from formal specifications and API documentation. "
    "You use ONLY the real API imports provided — never create mock classes "
    "or re-implement the API. Output ONLY Python code, no markdown fencing "
    "or explanation."
)


async def run_test_gen_loop(
    ctx: TestGenContext,
    call_llm,  # async (prompt: str, system_prompt: str | None) -> str
    max_attempts: int = 3,
    session_dir: Optional[Path] = None,
) -> VerifyResult:
    """Run the LLM test generation loop.

    Args:
        ctx: Test generation context (bridge artifacts, API context, etc.)
        call_llm: Async function that takes a prompt and optional system_prompt
                  and returns LLM response.
        max_attempts: Maximum generation attempts before giving up.
        session_dir: Optional directory for saving session transcripts.

    Returns:
        VerifyResult with passed=True if tests were generated and verified,
        or passed=False with error details.
    """
    test_path = ctx.output_dir / f"test_{ctx.gwt_id.replace('-', '_')}.py"
    ctx.output_dir.mkdir(parents=True, exist_ok=True)

    # Use test-generation-specific system prompt
    sys_prompt = _TEST_GEN_SYSTEM_PROMPT

    # Pass 1: Generate test plan
    plan_prompt = build_test_plan_prompt(ctx)
    test_plan = await call_llm(plan_prompt, system_prompt=sys_prompt)

    # Pass 2: Review
    review_prompt = build_review_prompt(test_plan, ctx)
    reviewed_plan = await call_llm(review_prompt, system_prompt=sys_prompt)

    # Pass 3: Generate code
    codegen_prompt = build_codegen_prompt(reviewed_plan, ctx)
    code_response = await call_llm(codegen_prompt, system_prompt=sys_prompt)
    test_code = _extract_code_from_response(code_response)
    test_path.write_text(test_code)

    if session_dir:
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / f"{ctx.gwt_id}_plan.txt").write_text(test_plan)
        (session_dir / f"{ctx.gwt_id}_review.txt").write_text(reviewed_plan)

    # Verify
    result = verify_test_file(test_path, ctx.python_dir)
    attempt = 1

    # Retry loop
    while not result.passed and attempt < max_attempts:
        attempt += 1
        retry_prompt = build_retry_prompt(test_code, result, ctx)
        code_response = await call_llm(retry_prompt, system_prompt=sys_prompt)
        test_code = _extract_code_from_response(code_response)
        test_path.write_text(test_code)

        if session_dir:
            (session_dir / f"{ctx.gwt_id}_attempt{attempt}.py").write_text(test_code)
            (session_dir / f"{ctx.gwt_id}_attempt{attempt}_errors.txt").write_text(
                "\n".join(result.errors) + "\n" + result.stderr
            )

        result = verify_test_file(test_path, ctx.python_dir)

    result.attempt = attempt
    return result
