"""Tests for the TLA+ Composition Engine (Phase 2)."""

import textwrap

import pytest

from registry.composer import (
    ComposedModule,
    CompositionError,
    TlaModule,
    compose,
    detect_shared_variables,
    generate_cross_invariants,
    parse_tla,
    SpecCache,
)
from registry.dag import RegistryDag
from registry.types import Edge, EdgeType, Node, NodeKind


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_MODULE_A = textwrap.dedent("""\
    ---- MODULE ModA ----
    EXTENDS Integers, FiniteSets

    CONSTANTS MaxVal

    VARIABLES x, y, shared_counter

    Init == /\\ x = 0
            /\\ y = 0
            /\\ shared_counter = 0

    IncrX == /\\ x' = x + 1
             /\\ UNCHANGED << y, shared_counter >>

    IncrShared == /\\ shared_counter' = shared_counter + 1
                  /\\ UNCHANGED << x, y >>

    Next == IncrX \\/ IncrShared

    XBounded == x <= MaxVal

    Spec == Init /\\ [][Next]_<< x, y, shared_counter >>

    ====
""")

SIMPLE_MODULE_B = textwrap.dedent("""\
    ---- MODULE ModB ----
    EXTENDS Integers

    CONSTANTS MaxVal

    VARIABLES z, shared_counter

    Init == /\\ z = 0
            /\\ shared_counter = 0

    IncrZ == /\\ z' = z + 1
             /\\ UNCHANGED shared_counter

    DecrShared == /\\ shared_counter' = shared_counter - 1
                  /\\ UNCHANGED z

    Next == IncrZ \\/ DecrShared

    ZBounded == z <= MaxVal

    Spec == Init /\\ [][Next]_<< z, shared_counter >>

    ====
""")


# ---------------------------------------------------------------------------
# Parser Tests
# ---------------------------------------------------------------------------

class TestParseTla:
    def test_parse_module_name(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert mod.name == "ModA"

    def test_parse_extends(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert "Integers" in mod.extends
        assert "FiniteSets" in mod.extends

    def test_parse_variables(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert "x" in mod.variables
        assert "y" in mod.variables
        assert "shared_counter" in mod.variables

    def test_parse_module_b_variables(self):
        mod = parse_tla(SIMPLE_MODULE_B)
        assert "z" in mod.variables
        assert "shared_counter" in mod.variables

    def test_parse_constants(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert "MaxVal" in mod.constants

    def test_parse_init_name(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert mod.init_name == "Init"

    def test_parse_next_name(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        assert mod.next_name == "Next"


# ---------------------------------------------------------------------------
# Variable Unification Tests
# ---------------------------------------------------------------------------

class TestDetectSharedVariables:
    def test_shared_by_name(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        shared = detect_shared_variables(mod_a, mod_b)
        assert shared == ["shared_counter"]

    def test_no_shared(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        # Module with completely different variables
        mod_c = TlaModule(name="ModC", variables=["w", "v"])
        shared = detect_shared_variables(mod_a, mod_c)
        assert shared == []

    def test_all_shared(self):
        mod = parse_tla(SIMPLE_MODULE_A)
        shared = detect_shared_variables(mod, mod)
        assert set(shared) == {"x", "y", "shared_counter"}


# ---------------------------------------------------------------------------
# Composition Tests
# ---------------------------------------------------------------------------

class TestCompose:
    def test_compose_produces_module(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert isinstance(result, ComposedModule)
        assert result.name == "ModA_ModB_composed"

    def test_shared_vars_detected(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert result.shared_vars == ["shared_counter"]

    def test_a_only_vars(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "x" in result.a_only_vars
        assert "y" in result.a_only_vars

    def test_b_only_vars(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "z" in result.b_only_vars

    def test_composed_text_has_init(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "Init_composed" in result.text

    def test_composed_text_has_next(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "Next_composed" in result.text

    def test_composed_text_has_unchanged(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "UNCHANGED" in result.text

    def test_composed_text_has_spec(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "Spec ==" in result.text

    def test_composed_extends_union(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b)
        assert "FiniteSets" in result.text
        assert "Integers" in result.text

    def test_custom_module_name(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b, module_name="MyComposed")
        assert result.name == "MyComposed"
        assert "MODULE MyComposed" in result.text

    def test_cross_invariants_in_output(self):
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        result = compose(mod_a, mod_b, cross_invariants=["SharedCounterBounded"])
        assert "SharedCounterBounded" in result.text
        assert "Inv_composed" in result.text


# ---------------------------------------------------------------------------
# Cross-Invariant Generation Tests
# ---------------------------------------------------------------------------

class TestCrossInvariants:
    def _make_dag(self) -> RegistryDag:
        dag = RegistryDag()
        dag.add_node(Node.resource("mod-a", "ModA", path="ModA.tla"))
        dag.add_node(Node.resource("mod-b", "ModB", path="ModB.tla"))
        dag.add_edge(Edge("mod-a", "mod-b", EdgeType.DEPENDS_ON))
        return dag

    def test_generates_cross_invariant(self):
        dag = self._make_dag()
        mod_a = TlaModule(name="ModA", source_path="ModA.tla")
        mod_b = TlaModule(name="ModB", source_path="ModB.tla")
        invs = generate_cross_invariants(mod_a, mod_b, dag)
        assert len(invs) >= 1
        assert any("Cross_" in inv for inv in invs)

    def test_no_cross_invariant_without_edges(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("mod-a", "ModA"))
        dag.add_node(Node.resource("mod-b", "ModB"))
        mod_a = TlaModule(name="ModA")
        mod_b = TlaModule(name="ModB")
        invs = generate_cross_invariants(mod_a, mod_b, dag)
        assert invs == []


# ---------------------------------------------------------------------------
# Spec Cache Tests
# ---------------------------------------------------------------------------

class TestSpecCache:
    def test_put_and_get(self):
        cache = SpecCache()
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        composed = compose(mod_a, mod_b)
        cache.put("component-0", composed)
        assert cache.get("component-0") is composed
        assert cache.count == 1

    def test_get_missing(self):
        cache = SpecCache()
        assert cache.get("nonexistent") is None

    def test_save(self, tmp_path):
        cache = SpecCache()
        mod_a = parse_tla(SIMPLE_MODULE_A)
        mod_b = parse_tla(SIMPLE_MODULE_B)
        composed = compose(mod_a, mod_b)
        cache.put("component-0", composed)
        cache.save(tmp_path)
        files = list(tmp_path.glob("*.tla"))
        assert len(files) == 1
        content = files[0].read_text()
        assert "Init_composed" in content
