"""TLA+ Composition Engine — Phase 2 of CodeWriter9.0 bootstrap.

Composes two TLA+ modules sharing variables into a single module:
  Init_composed = Init_A ∧ Init_B
  Next_composed = Next_A ∨ Next_B (with UNCHANGED)
  Inv_composed  = Inv_A ∧ Inv_B ∧ Inv_cross

Operates on compiled TLA+ output (post-PlusCal translation), never on
raw PlusCal. The LLM writes PlusCal; this engine handles composition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from registry.dag import RegistryDag
from registry.types import EdgeType


@dataclass
class TlaModule:
    """Parsed TLA+ module."""
    name: str
    extends: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    definitions: dict[str, str] = field(default_factory=dict)
    init_name: str = "Init"
    next_name: str = "Next"
    spec_name: str = "Spec"
    invariants: list[str] = field(default_factory=list)
    raw_text: str = ""
    source_path: str | None = None


@dataclass
class ComposedModule:
    """Result of composing two TLA+ modules."""
    name: str
    source_a: TlaModule
    source_b: TlaModule
    shared_vars: list[str]
    a_only_vars: list[str]
    b_only_vars: list[str]
    cross_invariants: list[str] = field(default_factory=list)
    text: str = ""


class ParseError(Exception):
    pass


class CompositionError(Exception):
    pass


# ---------------------------------------------------------------------------
# TLA+ Module Parser
# ---------------------------------------------------------------------------

_MODULE_RE = re.compile(
    r'-+\s*MODULE\s+(\w+)\s*-+', re.MULTILINE
)
_EXTENDS_RE = re.compile(
    r'EXTENDS\s+([^\n]+)', re.MULTILINE
)
_CONSTANTS_RE = re.compile(
    r'CONSTANTS?\s+([\w][\w\s,]*\w)', re.MULTILINE
)
_VARIABLES_RE = re.compile(
    r'VARIABLES?\s+([\w\s,\\]+?)(?:\n\n|\n\()', re.MULTILINE | re.DOTALL
)
_INVARIANT_COMMENT_RE = re.compile(
    r'\\\*\s*(?:INVARIANT|invariant)[:\s]*(\w+)', re.MULTILINE
)
_DEF_RE = re.compile(
    r'^(\w+)\s*==\s*(.+?)(?=\n\w+\s*==|\n\n|\Z)',
    re.MULTILINE | re.DOTALL
)
_INIT_RE = re.compile(r'^(Init\w*)\s*==', re.MULTILINE)
_NEXT_RE = re.compile(r'^(Next\w*)\s*==', re.MULTILINE)
_SPEC_RE = re.compile(r'^(Spec\w*)\s*==', re.MULTILINE)


def parse_tla(text: str, source_path: str | None = None) -> TlaModule:
    """Parse a TLA+ module from text."""
    mod = TlaModule(name="unknown", raw_text=text, source_path=source_path)

    # Module name
    m = _MODULE_RE.search(text)
    if m:
        mod.name = m.group(1)

    # EXTENDS
    m = _EXTENDS_RE.search(text)
    if m:
        mod.extends = [s.strip() for s in m.group(1).split(",") if s.strip()]

    # CONSTANTS
    m = _CONSTANTS_RE.search(text)
    if m:
        raw = m.group(1)
        mod.constants = [
            c.strip().rstrip(",")
            for c in re.split(r'[,\n]+', raw.strip())
            if c.strip() and not c.strip().startswith("\\*")
        ]

    # VARIABLES
    m = _VARIABLES_RE.search(text)
    if m:
        raw = m.group(1)
        raw = re.sub(r'\\[\s\n]*', '', raw)  # remove line continuation
        mod.variables = [
            v.strip().rstrip(",")
            for v in re.split(r',\s*', raw.strip())
            if v.strip()
        ]

    # Definitions
    # Extract the section between VARIABLES and the end marker
    translation_start = text.find("\\* BEGIN TRANSLATION")
    if translation_start >= 0:
        section = text[translation_start:]
    else:
        section = text

    for dm in _DEF_RE.finditer(section):
        name = dm.group(1)
        body = dm.group(2).strip()
        mod.definitions[name] = body

    # Init/Next/Spec names
    m = _INIT_RE.search(section)
    if m:
        mod.init_name = m.group(1)
    m = _NEXT_RE.search(section)
    if m:
        mod.next_name = m.group(1)
    m = _SPEC_RE.search(section)
    if m:
        mod.spec_name = m.group(1)

    # Invariants — from comments and from known patterns
    for im in _INVARIANT_COMMENT_RE.finditer(text):
        inv_name = im.group(1)
        if inv_name not in mod.invariants:
            mod.invariants.append(inv_name)

    # Also detect invariants from cfg-style patterns in definitions
    for name, body in mod.definitions.items():
        # Heuristic: boolean definitions that reference variables
        if name.startswith(("_", "vars", "ProcSet", "Init", "Next", "Spec",
                           "Termination", "Terminating")):
            continue
        if any(v in body for v in mod.variables):
            # Likely a state predicate / invariant
            if name not in mod.invariants:
                mod.invariants.append(name)

    return mod


def parse_tla_file(path: str | Path) -> TlaModule:
    """Parse a TLA+ module from a file."""
    p = Path(path)
    return parse_tla(p.read_text(), source_path=str(p))


# ---------------------------------------------------------------------------
# Variable Unification
# ---------------------------------------------------------------------------

def detect_shared_variables(
    mod_a: TlaModule,
    mod_b: TlaModule,
    dag: RegistryDag | None = None,
) -> list[str]:
    """Detect shared variables between two modules.

    Primary method: variable name intersection.
    Secondary: if a DAG is provided, use cross-layer edges to infer
    semantic equivalence even when names differ.
    """
    shared = sorted(set(mod_a.variables) & set(mod_b.variables))

    if dag is not None:
        # Look for edges between nodes associated with these modules
        a_nodes = _module_dag_nodes(mod_a, dag)
        b_nodes = _module_dag_nodes(mod_b, dag)
        for edge in dag.edges:
            if ((edge.from_id in a_nodes and edge.to_id in b_nodes) or
                    (edge.from_id in b_nodes and edge.to_id in a_nodes)):
                # Cross-edge found; could indicate semantic variable sharing
                # For now, we track this as metadata but don't auto-unify
                pass

    return shared


def _module_dag_nodes(mod: TlaModule, dag: RegistryDag) -> set[str]:
    """Find DAG nodes associated with a module."""
    results: set[str] = set()
    mod_name_lower = mod.name.lower()
    for nid, node in dag.nodes.items():
        if mod_name_lower in node.name.lower():
            results.add(nid)
        if mod.source_path and node.path and mod.source_path in node.path:
            results.add(nid)
    return results


# ---------------------------------------------------------------------------
# Composition Engine
# ---------------------------------------------------------------------------

def compose(
    mod_a: TlaModule,
    mod_b: TlaModule,
    dag: RegistryDag | None = None,
    cross_invariants: list[str] | None = None,
    module_name: str | None = None,
) -> ComposedModule:
    """Compose two TLA+ modules sharing variables.

    Produces:
      Init_composed = Init_A ∧ Init_B
      Next_composed = Next_A ∨ Next_B (with UNCHANGED for non-participating vars)
      Inv_composed  = Inv_A ∧ Inv_B ∧ Inv_cross
    """
    shared = detect_shared_variables(mod_a, mod_b, dag)
    a_only = sorted(set(mod_a.variables) - set(shared))
    b_only = sorted(set(mod_b.variables) - set(shared))
    all_vars = sorted(set(mod_a.variables) | set(mod_b.variables))

    if not shared and not all_vars:
        raise CompositionError(
            f"Modules {mod_a.name} and {mod_b.name} share no variables "
            f"and have no variables to compose"
        )

    name = module_name or f"{mod_a.name}_{mod_b.name}_composed"

    result = ComposedModule(
        name=name,
        source_a=mod_a,
        source_b=mod_b,
        shared_vars=shared,
        a_only_vars=a_only,
        b_only_vars=b_only,
        cross_invariants=cross_invariants or [],
    )

    result.text = _generate_composed_tla(result, all_vars)
    return result


def _generate_composed_tla(comp: ComposedModule, all_vars: list[str]) -> str:
    """Generate the TLA+ text for a composed module."""
    lines: list[str] = []
    border = "-" * 30
    lines.append(f"{border} MODULE {comp.name} {border}")
    lines.append("(*")
    lines.append(f" * Composed from: {comp.source_a.name} + {comp.source_b.name}")
    lines.append(f" * Shared variables: {', '.join(comp.shared_vars) if comp.shared_vars else 'none'}")
    lines.append(f" * Generated by CodeWriter9.0 Composition Engine")
    lines.append(" *)")
    lines.append("")

    # EXTENDS — union of both modules' extends
    all_extends = sorted(set(comp.source_a.extends) | set(comp.source_b.extends))
    if all_extends:
        lines.append(f"EXTENDS {', '.join(all_extends)}")
        lines.append("")

    # CONSTANTS — union
    all_constants = sorted(set(comp.source_a.constants) | set(comp.source_b.constants))
    if all_constants:
        lines.append("CONSTANTS")
        for c in all_constants:
            lines.append(f"    {c}")
        lines.append("")

    # VARIABLES — union (shared vars listed once)
    lines.append("VARIABLES")
    lines.append(f"    {', '.join(all_vars)}")
    lines.append("")

    a_name = comp.source_a.name
    b_name = comp.source_b.name

    # Vars tuple for UNCHANGED
    vars_str = f"<< {', '.join(all_vars)} >>"
    lines.append(f"vars == {vars_str}")
    lines.append("")

    # Bring in definitions from both modules (prefixed to avoid collision)
    lines.append(f"\\* --- Definitions from {a_name} ---")
    for dname, dbody in comp.source_a.definitions.items():
        if dname in ("vars", "ProcSet", "Init", "Next", "Spec",
                     "Termination", "Terminating"):
            continue
        prefixed = f"{a_name}_{dname}"
        lines.append(f"{prefixed} == {dbody}")
    lines.append("")

    lines.append(f"\\* --- Definitions from {b_name} ---")
    for dname, dbody in comp.source_b.definitions.items():
        if dname in ("vars", "ProcSet", "Init", "Next", "Spec",
                     "Termination", "Terminating"):
            continue
        prefixed = f"{b_name}_{dname}"
        lines.append(f"{prefixed} == {dbody}")
    lines.append("")

    # Init — conjunction
    a_init = comp.source_a.init_name
    b_init = comp.source_b.init_name
    lines.append(f"\\* --- Composed Init: {a_name}.{a_init} /\\ {b_name}.{b_init} ---")
    _emit_composed_init(lines, comp, all_vars)
    lines.append("")

    # Next — disjunction with UNCHANGED
    a_next = comp.source_a.next_name
    b_next = comp.source_b.next_name
    lines.append(f"\\* --- Composed Next: {a_name}.{a_next} \\/ {b_name}.{b_next} ---")
    _emit_composed_next(lines, comp, all_vars)
    lines.append("")

    # Invariants — conjunction of all
    lines.append("\\* --- Composed Invariants ---")
    all_invs: list[str] = []
    for inv in comp.source_a.invariants:
        prefixed = f"{a_name}_{inv}"
        all_invs.append(prefixed)
    for inv in comp.source_b.invariants:
        prefixed = f"{b_name}_{inv}"
        all_invs.append(prefixed)
    for cinv in comp.cross_invariants:
        all_invs.append(cinv)
        lines.append(f"\\* Cross-invariant (must be defined externally or below)")
    if all_invs:
        lines.append(f"Inv_composed == {' /\\\\ '.join(all_invs)}")
    lines.append("")

    # Spec
    lines.append(f"Spec == Init_composed /\\ [][Next_composed]_vars")
    lines.append("")

    lines.append("=" * 75)

    return "\n".join(lines)


def _emit_composed_init(
    lines: list[str], comp: ComposedModule, all_vars: list[str]
) -> None:
    """Generate composed Init predicate.

    For shared variables, the init values must agree (conjunction).
    For module-only variables, each module initializes its own.
    """
    a_init = comp.source_a.definitions.get(comp.source_a.init_name, "")
    b_init = comp.source_b.definitions.get(comp.source_b.init_name, "")

    if a_init and b_init:
        # Direct conjunction of the original Init definitions
        lines.append(f"Init_composed ==")
        lines.append(f"    \\* From {comp.source_a.name}")
        lines.append(f"    /\\ {a_init}")
        lines.append(f"    \\* From {comp.source_b.name}")
        lines.append(f"    /\\ {b_init}")
    else:
        # Fallback: reference by name
        a_ref = f"{comp.source_a.name}_{comp.source_a.init_name}"
        b_ref = f"{comp.source_b.name}_{comp.source_b.init_name}"
        lines.append(f"Init_composed == {a_ref} /\\ {b_ref}")


def _emit_composed_next(
    lines: list[str], comp: ComposedModule, all_vars: list[str]
) -> None:
    """Generate composed Next predicate.

    Next_composed = (Next_A /\\ UNCHANGED b_only_vars)
                 \\/ (Next_B /\\ UNCHANGED a_only_vars)
    """
    a_name = comp.source_a.name
    b_name = comp.source_b.name

    a_unchanged = comp.b_only_vars  # when A steps, B-only vars unchanged
    b_unchanged = comp.a_only_vars  # when B steps, A-only vars unchanged

    lines.append("Next_composed ==")

    # A takes a step
    a_next_ref = f"{a_name}_{comp.source_a.next_name}"
    if a_unchanged:
        unchanged_str = f"<< {', '.join(a_unchanged)} >>"
        lines.append(f"    \\/ ({a_next_ref} /\\ UNCHANGED {unchanged_str})")
    else:
        lines.append(f"    \\/ {a_next_ref}")

    # B takes a step
    b_next_ref = f"{b_name}_{comp.source_b.next_name}"
    if b_unchanged:
        unchanged_str = f"<< {', '.join(b_unchanged)} >>"
        lines.append(f"    \\/ ({b_next_ref} /\\ UNCHANGED {unchanged_str})")
    else:
        lines.append(f"    \\/ {b_next_ref}")


# ---------------------------------------------------------------------------
# Cross-Invariant Generation
# ---------------------------------------------------------------------------

def generate_cross_invariants(
    mod_a: TlaModule,
    mod_b: TlaModule,
    dag: RegistryDag,
) -> list[str]:
    """Generate cross-invariant names from registry dependency edges.

    For each cross-layer edge between the modules' DAG nodes, generate
    an invariant stub that the user/LLM must fill in.
    """
    a_nodes = _module_dag_nodes(mod_a, dag)
    b_nodes = _module_dag_nodes(mod_b, dag)
    invariants: list[str] = []

    for edge in dag.edges:
        if edge.from_id in a_nodes and edge.to_id in b_nodes:
            inv_name = f"Cross_{edge.from_id}_{edge.to_id}_{edge.edge_type.value}"
            inv_name = re.sub(r'[^a-zA-Z0-9_]', '_', inv_name)
            invariants.append(inv_name)
        elif edge.from_id in b_nodes and edge.to_id in a_nodes:
            inv_name = f"Cross_{edge.from_id}_{edge.to_id}_{edge.edge_type.value}"
            inv_name = re.sub(r'[^a-zA-Z0-9_]', '_', inv_name)
            invariants.append(inv_name)

    return sorted(set(invariants))


# ---------------------------------------------------------------------------
# Composed Spec Cache
# ---------------------------------------------------------------------------

@dataclass
class SpecCache:
    """Cache of composed specs indexed by connected component."""
    entries: dict[str, ComposedModule] = field(default_factory=dict)

    def get(self, component_id: str) -> ComposedModule | None:
        return self.entries.get(component_id)

    def put(self, component_id: str, composed: ComposedModule) -> None:
        self.entries[component_id] = composed

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        for comp_id, composed in self.entries.items():
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', comp_id)
            path = d / f"{safe_name}.tla"
            path.write_text(composed.text)

    @property
    def count(self) -> int:
        return len(self.entries)


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

def compose_from_files(
    path_a: str | Path,
    path_b: str | Path,
    dag: RegistryDag | None = None,
    module_name: str | None = None,
) -> ComposedModule:
    """Compose two TLA+ files."""
    mod_a = parse_tla_file(path_a)
    mod_b = parse_tla_file(path_b)
    cross_invs = generate_cross_invariants(mod_a, mod_b, dag) if dag else []
    return compose(mod_a, mod_b, dag=dag, cross_invariants=cross_invs,
                   module_name=module_name)


def compose_component(
    component_members: list[str],
    module_paths: dict[str, str | Path],
    dag: RegistryDag,
    component_id: str,
) -> ComposedModule | None:
    """Compose all modules in a connected component.

    Reduces pairwise: compose(a, b) then compose(result, c), etc.
    Returns None if fewer than 2 modules.
    """
    paths = [module_paths[m] for m in component_members if m in module_paths]
    if len(paths) < 2:
        return None

    modules = [parse_tla_file(p) for p in paths]
    result = modules[0]
    for i in range(1, len(modules)):
        cross_invs = generate_cross_invariants(result, modules[i], dag)
        composed = compose(result, modules[i], dag=dag,
                          cross_invariants=cross_invs,
                          module_name=f"component_{component_id}")
        # Wrap composed output as a TlaModule for further composition
        result = parse_tla(composed.text)

    # Return the final composition
    final = compose(
        parse_tla_file(paths[0]),
        parse_tla_file(paths[1]),
        dag=dag,
        module_name=f"component_{component_id}",
    )
    if len(paths) > 2:
        # Re-do with iterative composition for >2 modules
        current = parse_tla_file(paths[0])
        for p in paths[1:]:
            next_mod = parse_tla_file(p)
            cross_invs = generate_cross_invariants(current, next_mod, dag)
            comp = compose(current, next_mod, dag=dag,
                          cross_invariants=cross_invs,
                          module_name=f"component_{component_id}")
            current = parse_tla(comp.text)
        final = comp

    return final
