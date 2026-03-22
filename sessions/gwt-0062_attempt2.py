Looking at the error, the Python environment used to run the tests (`/home/maceo/.local/share/uv/tools/codewriter-registry/bin/python3`) does not have `pytest` installed. The fix is to convert the test file to use `unittest.TestCase` (which pytest can also collect, and which works natively without pytest), and replace `pytest.raises` with `self.assertRaises`/`self.assertRaisesRegex`.

import unittest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import Node

# ── TLA+ Tokens table (Tokens[1..11] from the verified spec) ─────────────────

TOKENS = [
    {"tla_op": "In",     "rs_op": "contains_ref", "helper": False},
    {"tla_op": "And",    "rs_op": "ampamp",        "helper": False},
    {"tla_op": "Or",     "rs_op": "pipepipe",      "helper": False},
    {"tla_op": "Eq",     "rs_op": "doubleEq",      "helper": False},
    {"tla_op": "Neq",    "rs_op": "bangEq",        "helper": False},
    {"tla_op": "ForAll", "rs_op": "iter_all",      "helper": False},
    {"tla_op": "Exists", "rs_op": "iter_any",      "helper": False},
    {"tla_op": "Len",    "rs_op": "dot_len",       "helper": False},
    {"tla_op": "Card",   "rs_op": "dot_len",       "helper": False},
    {"tla_op": "BoolT",  "rs_op": "true",          "helper": False},
    {"tla_op": "BoolF",  "rs_op": "false",         "helper": False},
]
N = 11

EXPECTED_FINAL = frozenset((t["tla_op"], t["rs_op"]) for t in TOKENS)


# ── DAG construction helpers ─────────────────────────────────────────────────

def _fresh_dag() -> RegistryDag:
    return RegistryDag()


def _op_node_id(tla_op: str) -> str:
    return f"op_{tla_op}"


def _process_token(dag: RegistryDag, token: dict) -> None:
    dag.add_node(
        Node.resource(
            id=_op_node_id(token["tla_op"]),
            name=token["rs_op"],
            description="helper=true" if token["helper"] else "helper=false",
        )
    )


def _get_results(dag: RegistryDag) -> list:
    out = []
    for node in dag.to_dict().get("nodes", []):
        nid = node.get("id", "")
        if nid.startswith("op_"):
            out.append({
                "tla_op": nid[3:],
                "rs_op": node.get("name", ""),
                "helper": node.get("description", "") == "helper=true",
            })
    return out


def _result_pairs(dag: RegistryDag) -> frozenset:
    return frozenset((r["tla_op"], r["rs_op"]) for r in _get_results(dag))


def _compile_all(dag: RegistryDag) -> int:
    cursor = 1
    for token in TOKENS:
        _process_token(dag, token)
        cursor += 1
    return cursor


# ── Invariant checkers ────────────────────────────────────────────────────────

def _inv_no_error(has_error: bool) -> None:
    assert not has_error, "NoError violated: has_error is True"


def _inv_helper_always_empty(results: list) -> None:
    for r in results:
        assert r["helper"] is False, (
            f"HelperAlwaysEmpty violated: {r['tla_op']} has helper=True"
        )


def _inv_reference_contains(results: list) -> None:
    for r in results:
        if r["tla_op"] == "In":
            assert r["rs_op"] == "contains_ref", (
                f"ReferenceContains violated: In → {r['rs_op']}"
            )


def _inv_closure_syntax(results: list) -> None:
    for r in results:
        if r["tla_op"] == "ForAll":
            assert r["rs_op"] == "iter_all", (
                f"ClosureSyntax violated: ForAll → {r['rs_op']}"
            )


def _inv_exists_syntax(results: list) -> None:
    for r in results:
        if r["tla_op"] == "Exists":
            assert r["rs_op"] == "iter_any", (
                f"ExistsSyntax violated: Exists → {r['rs_op']}"
            )


def _inv_all_mapped(results: list, cursor: int) -> None:
    if cursor > N:
        mapped = {(r["tla_op"], r["rs_op"]) for r in results}
        for tok in TOKENS:
            assert (tok["tla_op"], tok["rs_op"]) in mapped, (
                f"AllMapped violated: ({tok['tla_op']}, {tok['rs_op']}) missing"
            )


def _assert_all_invariants(dag: RegistryDag, cursor: int, has_error: bool = False) -> None:
    results = _get_results(dag)
    _inv_no_error(has_error)
    _inv_helper_always_empty(results)
    _inv_reference_contains(results)
    _inv_closure_syntax(results)
    _inv_exists_syntax(results)
    _inv_all_mapped(results, cursor)


# ── Trace 1 ───────────────────────────────────────────────────────────────────

class TestTrace1(unittest.TestCase):

    def test_init_state_is_empty(self):
        dag = _fresh_dag()
        self.assertEqual(_get_results(dag), [])
        self.assertEqual(dag.node_count, 0)
        _assert_all_invariants(dag, cursor=1)

    def test_invariants_hold_at_every_step(self):
        dag = _fresh_dag()
        cursor = 1
        _assert_all_invariants(dag, cursor)
        for token in TOKENS:
            _process_token(dag, token)
            _assert_all_invariants(dag, cursor)
            cursor += 1
            _assert_all_invariants(dag, cursor)
        self.assertEqual(cursor, 12)
        _assert_all_invariants(dag, cursor)

    def test_final_state_matches_expected_results(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        self.assertEqual(cursor, 12)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)
        self.assertEqual(dag.node_count, N)

    def test_first_process_token_adds_in_operator(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        results = _get_results(dag)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tla_op"], "In")
        self.assertEqual(results[0]["rs_op"], "contains_ref")
        self.assertIs(results[0]["helper"], False)
        _assert_all_invariants(dag, cursor=1)


# ── Trace 2 ───────────────────────────────────────────────────────────────────

class TestTrace2(unittest.TestCase):

    def test_after_first_two_tokens_both_present(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        _process_token(dag, TOKENS[1])
        results = _get_results(dag)
        tla_ops = {r["tla_op"] for r in results}
        self.assertEqual(tla_ops, {"In", "And"})
        _assert_all_invariants(dag, cursor=2)

    def test_and_operator_maps_to_ampamp(self):
        dag = _fresh_dag()
        for token in TOKENS[:2]:
            _process_token(dag, token)
        results = _get_results(dag)
        and_r = next(r for r in results if r["tla_op"] == "And")
        self.assertEqual(and_r["rs_op"], "ampamp")
        self.assertIs(and_r["helper"], False)

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 3 ───────────────────────────────────────────────────────────────────

class TestTrace3(unittest.TestCase):

    def test_after_three_tokens_or_operator_present(self):
        dag = _fresh_dag()
        for token in TOKENS[:3]:
            _process_token(dag, token)
        results = _get_results(dag)
        or_r = next((r for r in results if r["tla_op"] == "Or"), None)
        self.assertIsNotNone(or_r)
        self.assertEqual(or_r["rs_op"], "pipepipe")
        _assert_all_invariants(dag, cursor=3)

    def test_helper_always_empty_through_or(self):
        dag = _fresh_dag()
        for token in TOKENS[:3]:
            _process_token(dag, token)
        _inv_helper_always_empty(_get_results(dag))

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 4 ───────────────────────────────────────────────────────────────────

class TestTrace4(unittest.TestCase):

    def test_eq_operator_maps_to_double_eq(self):
        dag = _fresh_dag()
        for token in TOKENS[:4]:
            _process_token(dag, token)
        results = _get_results(dag)
        eq_r = next(r for r in results if r["tla_op"] == "Eq")
        self.assertEqual(eq_r["rs_op"], "doubleEq")
        self.assertIs(eq_r["helper"], False)
        _assert_all_invariants(dag, cursor=4)

    def test_four_tokens_yields_four_nodes(self):
        dag = _fresh_dag()
        for token in TOKENS[:4]:
            _process_token(dag, token)
        self.assertEqual(dag.node_count, 4)

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 5 ───────────────────────────────────────────────────────────────────

class TestTrace5(unittest.TestCase):

    def test_neq_operator_maps_to_bang_eq(self):
        dag = _fresh_dag()
        for token in TOKENS[:5]:
            _process_token(dag, token)
        results = _get_results(dag)
        neq_r = next(r for r in results if r["tla_op"] == "Neq")
        self.assertEqual(neq_r["rs_op"], "bangEq")
        self.assertIs(neq_r["helper"], False)
        _assert_all_invariants(dag, cursor=5)

    def test_reference_contains_holds_at_cursor_5(self):
        dag = _fresh_dag()
        for token in TOKENS[:5]:
            _process_token(dag, token)
        _inv_reference_contains(_get_results(dag))

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 6 ───────────────────────────────────────────────────────────────────

class TestTrace6(unittest.TestCase):

    def test_forall_maps_to_iter_all(self):
        dag = _fresh_dag()
        for token in TOKENS[:6]:
            _process_token(dag, token)
        results = _get_results(dag)
        fa_r = next(r for r in results if r["tla_op"] == "ForAll")
        self.assertEqual(fa_r["rs_op"], "iter_all")
        self.assertIs(fa_r["helper"], False)
        _assert_all_invariants(dag, cursor=6)

    def test_closure_syntax_holds_immediately_after_forall(self):
        dag = _fresh_dag()
        for token in TOKENS[:6]:
            _process_token(dag, token)
        _inv_closure_syntax(_get_results(dag))

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 7 ───────────────────────────────────────────────────────────────────

class TestTrace7(unittest.TestCase):

    def test_exists_maps_to_iter_any(self):
        dag = _fresh_dag()
        for token in TOKENS[:7]:
            _process_token(dag, token)
        results = _get_results(dag)
        ex_r = next(r for r in results if r["tla_op"] == "Exists")
        self.assertEqual(ex_r["rs_op"], "iter_any")
        self.assertIs(ex_r["helper"], False)
        _assert_all_invariants(dag, cursor=7)

    def test_exists_syntax_holds_immediately_after_exists(self):
        dag = _fresh_dag()
        for token in TOKENS[:7]:
            _process_token(dag, token)
        _inv_exists_syntax(_get_results(dag))

    def test_forall_and_exists_are_distinct_rs_ops(self):
        dag = _fresh_dag()
        for token in TOKENS[:7]:
            _process_token(dag, token)
        results = _get_results(dag)
        rs_by_tla = {r["tla_op"]: r["rs_op"] for r in results}
        self.assertNotEqual(rs_by_tla["ForAll"], rs_by_tla["Exists"])

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 8 ───────────────────────────────────────────────────────────────────

class TestTrace8(unittest.TestCase):

    def test_len_maps_to_dot_len(self):
        dag = _fresh_dag()
        for token in TOKENS[:8]:
            _process_token(dag, token)
        results = _get_results(dag)
        len_r = next(r for r in results if r["tla_op"] == "Len")
        self.assertEqual(len_r["rs_op"], "dot_len")
        self.assertIs(len_r["helper"], False)
        _assert_all_invariants(dag, cursor=8)

    def test_helper_always_empty_through_len(self):
        dag = _fresh_dag()
        for token in TOKENS[:8]:
            _process_token(dag, token)
        _inv_helper_always_empty(_get_results(dag))

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 9 ───────────────────────────────────────────────────────────────────

class TestTrace9(unittest.TestCase):

    def test_card_maps_to_dot_len(self):
        dag = _fresh_dag()
        for token in TOKENS[:9]:
            _process_token(dag, token)
        results = _get_results(dag)
        card_r = next(r for r in results if r["tla_op"] == "Card")
        self.assertEqual(card_r["rs_op"], "dot_len")
        self.assertIs(card_r["helper"], False)
        _assert_all_invariants(dag, cursor=9)

    def test_len_and_card_both_compile_to_dot_len(self):
        dag = _fresh_dag()
        for token in TOKENS[:9]:
            _process_token(dag, token)
        results = _get_results(dag)
        dot_len_entries = [r for r in results if r["rs_op"] == "dot_len"]
        dot_len_tla_ops = {r["tla_op"] for r in dot_len_entries}
        self.assertIn("Len", dot_len_tla_ops)
        self.assertIn("Card", dot_len_tla_ops)
        self.assertEqual(len(dot_len_entries), 2)

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Trace 10 ──────────────────────────────────────────────────────────────────

class TestTrace10(unittest.TestCase):

    def test_boolt_maps_to_true(self):
        dag = _fresh_dag()
        for token in TOKENS[:10]:
            _process_token(dag, token)
        results = _get_results(dag)
        bt_r = next(r for r in results if r["tla_op"] == "BoolT")
        self.assertEqual(bt_r["rs_op"], "true")
        self.assertIs(bt_r["helper"], False)
        _assert_all_invariants(dag, cursor=10)

    def test_boolf_maps_to_false(self):
        dag = _fresh_dag()
        for token in TOKENS:
            _process_token(dag, token)
        results = _get_results(dag)
        bf_r = next(r for r in results if r["tla_op"] == "BoolF")
        self.assertEqual(bf_r["rs_op"], "false")
        self.assertIs(bf_r["helper"], False)

    def test_full_compilation_node_count_equals_n(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        self.assertEqual(cursor, 12)
        self.assertEqual(dag.node_count, N)
        _assert_all_invariants(dag, cursor)

    def test_full_compilation_final_state(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        _assert_all_invariants(dag, cursor)
        self.assertEqual(_result_pairs(dag), EXPECTED_FINAL)


# ── Invariant verifier: AllMapped ─────────────────────────────────────────────

class TestInvariantAllMapped(unittest.TestCase):

    def test_all_mapped_holds_after_full_compile_trace1(self):
        dag = _fresh_dag()
        cursor = _compile_all(dag)
        self.assertGreater(cursor, N)
        _inv_all_mapped(_get_results(dag), cursor)

    def test_all_mapped_holds_after_full_compile_trace2(self):
        dag = _fresh_dag()
        cursor = 1
        for token in TOKENS:
            _process_token(dag, token)
            cursor += 1
        self.assertEqual(cursor, 12)
        _inv_all_mapped(_get_results(dag), cursor)

    def test_all_mapped_vacuously_true_when_cursor_le_n(self):
        dag = _fresh_dag()
        for token in TOKENS[:5]:
            _process_token(dag, token)
        _inv_all_mapped(_get_results(dag), cursor=5)

    def test_every_token_pair_present_in_final_result(self):
        dag = _fresh_dag()
        _compile_all(dag)
        pairs = _result_pairs(dag)
        for tok in TOKENS:
            self.assertIn((tok["tla_op"], tok["rs_op"]), pairs)

    def test_all_mapped_requires_both_tla_op_and_rs_op(self):
        dag = _fresh_dag()
        for token in TOKENS[:3]:
            _process_token(dag, token)
        pairs = _result_pairs(dag)
        missing = [tok for tok in TOKENS if (tok["tla_op"], tok["rs_op"]) not in pairs]
        self.assertEqual(len(missing), N - 3)


# ── Invariant verifier: HelperAlwaysEmpty ────────────────────────────────────

class TestInvariantHelperAlwaysEmpty(unittest.TestCase):

    def test_helper_false_after_full_compile_trace1(self):
        dag = _fresh_dag()
        _compile_all(dag)
        _inv_helper_always_empty(_get_results(dag))

    def test_helper_false_intermediate_trace3_three_tokens(self):
        dag = _fresh_dag()
        for token in TOKENS[:3]:
            _process_token(dag, token)
        _inv_helper_always_empty(_get_results(dag))

    def test_helper_false_after_every_individual_process_token(self):
        dag = _fresh_dag()
        for token in TOKENS:
            _process_token(dag, token)
            _inv_helper_always_empty(_get_results(dag))

    def test_helper_value_is_python_false_not_truthy_string(self):
        dag = _fresh_dag()
        _compile_all(dag)
        for r in _get_results(dag):
            self.assertIs(r["helper"], False)
            self.assertIsNot(r["helper"], True)


# ── Invariant verifier: ReferenceContains ────────────────────────────────────

class TestInvariantReferenceContains(unittest.TestCase):

    def test_reference_contains_after_full_compile_trace1(self):
        dag = _fresh_dag()
        _compile_all(dag)
        _inv_reference_contains(_get_results(dag))

    def test_reference_contains_immediately_after_first_process_token(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        _inv_reference_contains(_get_results(dag))

    def test_in_rs_op_is_contains_ref_not_bare_contains(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        results = _get_results(dag)
        in_r = next(r for r in results if r["tla_op"] == "In")
        self.assertEqual(in_r["rs_op"], "contains_ref")
        self.assertNotEqual(in_r["rs_op"], "contains")

    def test_reference_contains_vacuously_true_before_in_processed(self):
        dag = _fresh_dag()
        _inv_reference_contains([])


# ── Invariant verifier: ClosureSyntax ────────────────────────────────────────

class TestInvariantClosureSyntax(unittest.TestCase):

    def test_closure_syntax_after_full_compile_trace1(self):
        dag = _fresh_dag()
        _compile_all(dag)
        _inv_closure_syntax(_get_results(dag))

    def test_closure_syntax_at_cursor_6_trace6(self):
        dag = _fresh_dag()
        for token in TOKENS[:6]:
            _process_token(dag, token)
        _inv_closure_syntax(_get_results(dag))

    def test_forall_rs_op_is_iter_all_not_iter_any(self):
        dag = _fresh_dag()
        _compile_all(dag)
        results = _get_results(dag)
        fa = next(r for r in results if r["tla_op"] == "ForAll")
        self.assertEqual(fa["rs_op"], "iter_all")
        self.assertNotEqual(fa["rs_op"], "iter_any")

    def test_closure_syntax_vacuously_true_before_forall_processed(self):
        dag = _fresh_dag()
        for token in TOKENS[:5]:
            _process_token(dag, token)
        tla_ops = {r["tla_op"] for r in _get_results(dag)}
        self.assertNotIn("ForAll", tla_ops)
        _inv_closure_syntax(_get_results(dag))


# ── Invariant verifier: ExistsSyntax ─────────────────────────────────────────

class TestInvariantExistsSyntax(unittest.TestCase):

    def test_exists_syntax_after_full_compile_trace1(self):
        dag = _fresh_dag()
        _compile_all(dag)
        _inv_exists_syntax(_get_results(dag))

    def test_exists_syntax_at_cursor_7_trace7(self):
        dag = _fresh_dag()
        for token in TOKENS[:7]:
            _process_token(dag, token)
        _inv_exists_syntax(_get_results(dag))

    def test_exists_rs_op_is_iter_any_not_iter_all(self):
        dag = _fresh_dag()
        _compile_all(dag)
        results = _get_results(dag)
        ex = next(r for r in results if r["tla_op"] == "Exists")
        self.assertEqual(ex["rs_op"], "iter_any")
        self.assertNotEqual(ex["rs_op"], "iter_all")

    def test_exists_syntax_vacuously_true_before_exists_processed(self):
        dag = _fresh_dag()
        for token in TOKENS[:6]:
            _process_token(dag, token)
        tla_ops = {r["tla_op"] for r in _get_results(dag)}
        self.assertNotIn("Exists", tla_ops)
        _inv_exists_syntax(_get_results(dag))


# ── Invariant verifier: NoError ───────────────────────────────────────────────

class TestInvariantNoError(unittest.TestCase):

    def test_no_error_in_init_state(self):
        _inv_no_error(False)

    def test_no_error_throughout_full_compile_trace1(self):
        has_error = False
        dag = _fresh_dag()
        _inv_no_error(has_error)
        for token in TOKENS:
            _process_token(dag, token)
            _inv_no_error(has_error)

    def test_no_error_in_finish_state(self):
        has_error = False
        dag = _fresh_dag()
        _compile_all(dag)
        _inv_no_error(has_error)

    def test_add_node_does_not_raise_for_valid_token(self):
        dag = _fresh_dag()
        for token in TOKENS:
            _process_token(dag, token)
        self.assertEqual(dag.node_count, N)

    def test_no_error_invariant_raises_when_has_error_is_true(self):
        with self.assertRaises(AssertionError) as ctx:
            _inv_no_error(True)
        self.assertIn("NoError violated", str(ctx.exception))


# ── Edge case tests ───────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_empty_dag_all_invariants_vacuously_hold(self):
        dag = _fresh_dag()
        results = _get_results(dag)
        self.assertEqual(results, [])
        _inv_helper_always_empty(results)
        _inv_reference_contains(results)
        _inv_closure_syntax(results)
        _inv_exists_syntax(results)
        _inv_all_mapped(results, cursor=1)
        _inv_no_error(False)

    def test_single_in_operator_node(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        results = _get_results(dag)
        self.assertEqual(len(results), 1)
        _inv_reference_contains(results)
        _inv_helper_always_empty(results)

    def test_single_forall_node_closure_syntax(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[5])
        results = _get_results(dag)
        self.assertEqual(len(results), 1)
        _inv_closure_syntax(results)
        _inv_helper_always_empty(results)

    def test_single_exists_node_exists_syntax(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[6])
        results = _get_results(dag)
        self.assertEqual(len(results), 1)
        _inv_exists_syntax(results)
        _inv_helper_always_empty(results)

    def test_len_and_card_share_rs_op_dot_len(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[7])
        _process_token(dag, TOKENS[8])
        results = _get_results(dag)
        rs_ops = [r["rs_op"] for r in results]
        self.assertEqual(rs_ops.count("dot_len"), 2)
        tla_ops = {r["tla_op"] for r in results}
        self.assertEqual(tla_ops, {"Len", "Card"})
        _inv_helper_always_empty(results)

    def test_quantifier_pair_has_distinct_rs_ops(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[5])
        _process_token(dag, TOKENS[6])
        results = _get_results(dag)
        by_tla = {r["tla_op"]: r["rs_op"] for r in results}
        self.assertNotEqual(by_tla["ForAll"], by_tla["Exists"])
        self.assertEqual(by_tla["ForAll"], "iter_all")
        self.assertEqual(by_tla["Exists"], "iter_any")

    def test_bool_literals_compile_correctly(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[9])
        _process_token(dag, TOKENS[10])
        results = _get_results(dag)
        by_tla = {r["tla_op"]: r["rs_op"] for r in results}
        self.assertEqual(by_tla["BoolT"], "true")
        self.assertEqual(by_tla["BoolF"], "false")
        _inv_helper_always_empty(results)

    def test_two_fresh_dags_produce_identical_final_states(self):
        dag1 = _fresh_dag()
        dag2 = _fresh_dag()
        _compile_all(dag1)
        _compile_all(dag2)
        self.assertEqual(_result_pairs(dag1), _result_pairs(dag2))
        self.assertEqual(dag1.node_count, dag2.node_count)

    def test_all_mapped_vacuously_holds_when_cursor_le_n(self):
        dag = _fresh_dag()
        for token in TOKENS[:6]:
            _process_token(dag, token)
        pairs = _result_pairs(dag)
        unprocessed = [tok for tok in TOKENS[6:] if (tok["tla_op"], tok["rs_op"]) not in pairs]
        self.assertEqual(len(unprocessed), N - 6)
        _inv_all_mapped(_get_results(dag), cursor=6)

    def test_all_mapped_raises_when_cursor_above_n_with_incomplete_results(self):
        dag = _fresh_dag()
        for token in TOKENS[:3]:
            _process_token(dag, token)
        with self.assertRaises(AssertionError) as ctx:
            _inv_all_mapped(_get_results(dag), cursor=N + 1)
        self.assertIn("AllMapped violated", str(ctx.exception))

    def test_requirement_node_can_be_registered_in_dag(self):
        dag = _fresh_dag()
        dag.add_node(Node.resource(
            id="req_compile_condition_operator_mapping",
            name="compile_condition_operator_mapping",
            description=(
                "RustProfile.compile_condition translates TLA+ operators to Rust: "
                "In→.contains(&x), ForAll→.iter().all, Exists→.iter().any"
            ),
        ))
        self.assertEqual(dag.node_count, 1)
        nodes = dag.to_dict().get("nodes", [])
        req_node = next(
            (n for n in nodes if n.get("id") == "req_compile_condition_operator_mapping"),
            None,
        )
        self.assertIsNotNone(req_node)
        self.assertEqual(req_node.get("name"), "compile_condition_operator_mapping")

    def test_operator_node_is_retrievable_via_to_dict(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[0])
        nodes = dag.to_dict().get("nodes", [])
        node_ids = [n.get("id") for n in nodes]
        self.assertIn(_op_node_id("In"), node_ids)

    def test_operator_node_fields_persisted_correctly(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[5])
        nodes = dag.to_dict().get("nodes", [])
        forall_node = next(
            (n for n in nodes if n.get("id") == _op_node_id("ForAll")), None
        )
        self.assertIsNotNone(forall_node)
        self.assertEqual(forall_node.get("name"), "iter_all")
        self.assertEqual(forall_node.get("description"), "helper=false")

    def test_multiple_operator_nodes_coexist_without_id_collision(self):
        dag = _fresh_dag()
        _process_token(dag, TOKENS[5])
        _process_token(dag, TOKENS[6])
        self.assertEqual(dag.node_count, 2)
        node_ids = {n.get("id") for n in dag.to_dict().get("nodes", [])}
        self.assertIn(_op_node_id("ForAll"), node_ids)
        self.assertIn(_op_node_id("Exists"), node_ids)

    def test_node_not_found_error_raised_for_nonexistent_node(self):
        dag = _fresh_dag()
        with self.assertRaises(NodeNotFoundError):
            dag.extract_subgraph("op_NonExistent")


if __name__ == "__main__":
    unittest.main()