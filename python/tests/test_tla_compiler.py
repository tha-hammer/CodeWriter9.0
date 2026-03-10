"""Tests for the bounded TLA+ → Python assertion compiler (Phase 5B)."""

import pytest

from registry.tla_compiler import compile_condition, compile_assertions, CompileError


class TestTlaCompiler:
    def test_basic_operators(self):
        r = compile_condition("x \\in S /\\ y = 3")
        assert "in" in r.python_expr
        assert "and" in r.python_expr
        assert "==" in r.python_expr

    def test_universal_quantifier(self):
        r = compile_condition("\\A x \\in S : x > 0")
        assert "all(" in r.python_expr
        assert "for x in S" in r.python_expr

    def test_record_field_access(self):
        r = compile_condition("state.count > 0", state_var="state")
        assert 'state["count"]' in r.python_expr

    def test_len_cardinality(self):
        r = compile_condition("Len(seq) > 0 /\\ Cardinality(S) = 3")
        assert "len(seq)" in r.python_expr
        assert "len(S)" in r.python_expr

    def test_boolean_literals(self):
        r = compile_condition("dirty = TRUE")
        assert "True" in r.python_expr

    def test_unsupported_operator_raises(self):
        with pytest.raises(CompileError):
            compile_condition("\\CHOOSE x \\in S : P(x)")

    def test_dirty_guard_stripped(self):
        r = compile_condition("dirty = TRUE /\\ x > 0")
        assert "dirty" not in r.python_expr
        assert "x" in r.python_expr

    def test_compile_assertions_from_verifiers(self):
        verifiers = {
            "NoFalsePositives": {
                "conditions": ["\\A t \\in affected : t \\in candidates"],
                "applies_to": ["affected", "candidates"],
            },
            "ValidState": {
                "conditions": ["Len(result) >= 0"],
                "applies_to": ["result"],
            },
        }
        results = compile_assertions(verifiers)
        assert "NoFalsePositives" in results
        assert "all(" in results["NoFalsePositives"].python_expr
        assert "ValidState" in results
        assert "len(result)" in results["ValidState"].python_expr
