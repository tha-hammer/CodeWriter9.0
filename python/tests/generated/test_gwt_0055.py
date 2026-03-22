import pytest
from pathlib import Path
from registry.scanner_javascript import scan_file as _scan_file

def scan_file(path):
    return _scan_file(Path(path) if isinstance(path, str) else path)

# ---------------------------------------------------------------------------
# Canonical JavaScript source encoding the 6-event TLA+ sequence:
#   Event 1  ClassOpen   "A"           → push class_stack, brace_depth 0→1
#   Event 2  Method      "getData"     → skeleton(A, getData, public)
#   Event 3  Method      "#secret"     → skeleton(A, #secret, private)
#   Event 4  Constructor "constructor" → skipped (ConstructorExclusion)
#   Event 5  CloseBrace                → brace_depth 1→0, pop class_stack
#   Event 6  Func        "helper"      → skeleton("None", helper, public)
# ---------------------------------------------------------------------------
JS_SOURCE = """\
class A {
  getData() {}
  #secret() {}
  constructor() {}
}
function helper() {}
"""

# Final-state skeleton set (State 21 of every trace).
EXPECTED_FINAL_SKELETONS = frozenset([
    ("getData", "A",    "public",  "None"),
    ("#secret", "A",    "private", "None"),
    ("helper",  "None", "public",  "None"),
])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def js_file(tmp_path):
    p = tmp_path / "trace_module.js"
    p.write_text(JS_SOURCE)
    return str(p)


@pytest.fixture
def js_file_class_b(tmp_path):
    p = tmp_path / "class_b.js"
    p.write_text(
        "class B {\n"
        "  getData() {}\n"
        "  #secret() {}\n"
        "  constructor() {}\n"
        "}\n"
        "function helper() {}\n"
    )
    return str(p)


@pytest.fixture
def js_file_multi_hash(tmp_path):
    p = tmp_path / "multi_hash.js"
    p.write_text(
        "class C {\n"
        "  #alpha() {}\n"
        "  #beta() {}\n"
        "  gamma() {}\n"
        "}\n"
    )
    return str(p)


@pytest.fixture
def js_file_all_public(tmp_path):
    p = tmp_path / "all_public.js"
    p.write_text("class D {\n  foo() {}\n  bar() {}\n}\n")
    return str(p)


@pytest.fixture
def js_file_funcs_only(tmp_path):
    p = tmp_path / "funcs_only.js"
    p.write_text("function alpha() {}\nfunction beta() {}\n")
    return str(p)


# ---------------------------------------------------------------------------
# Invariant verifier helpers
# ---------------------------------------------------------------------------

def _assert_depth_consistency(skeletons):
    for s in skeletons:
        assert "class_name" in s, f"skeleton missing class_name: {s}"
        assert isinstance(s["class_name"], str), (
            f"class_name must be a string (sentinel 'None' or actual class name), "
            f"got {type(s['class_name'])!r}: {s}"
        )


def _assert_constructor_exclusion(skeletons):
    for s in skeletons:
        assert s["function_name"] != "constructor", (
            f"constructor must be excluded from skeletons, found: {s}"
        )


def _assert_hash_private(skeletons):
    for s in skeletons:
        if s["function_name"].startswith("#"):
            assert s["visibility"] == "private", (
                f"hash-prefixed method must be private: {s}"
            )


def _assert_public_default(skeletons):
    for s in skeletons:
        if not s["function_name"].startswith("#"):
            assert s["visibility"] == "public", (
                f"non-hash method must default to public: {s}"
            )


def _assert_return_type_none(skeletons):
    for s in skeletons:
        assert s["return_type"] == "None", (
            f"return_type must be sentinel string 'None': {s}"
        )


def _assert_expected_results(skeletons):
    by_name = {s["function_name"]: s for s in skeletons}

    assert "getData" in by_name, "getData must be present in skeletons"
    assert by_name["getData"]["class_name"] == "A"
    assert by_name["getData"]["visibility"] == "public"

    assert "#secret" in by_name, "#secret must be present in skeletons"
    assert by_name["#secret"]["class_name"] == "A"
    assert by_name["#secret"]["visibility"] == "private"

    assert "helper" in by_name, "helper must be present in skeletons"
    assert by_name["helper"]["class_name"] == "None"
    assert by_name["helper"]["visibility"] == "public"

    assert "constructor" not in by_name


def _assert_all_invariants(skeletons):
    _assert_depth_consistency(skeletons)
    _assert_constructor_exclusion(skeletons)
    _assert_hash_private(skeletons)
    _assert_public_default(skeletons)
    _assert_return_type_none(skeletons)
    _assert_expected_results(skeletons)


def _assert_structural_invariants(skeletons):
    _assert_depth_consistency(skeletons)
    _assert_constructor_exclusion(skeletons)
    _assert_hash_private(skeletons)
    _assert_public_default(skeletons)
    _assert_return_type_none(skeletons)


def _to_tuple_set(skeletons):
    return frozenset(
        (s["function_name"], s["class_name"], s["visibility"], s["return_type"])
        for s in skeletons
    )


# ---------------------------------------------------------------------------
# Trace-derived tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_scan_file_final_state(js_file, trace_id):
    skeletons = scan_file(js_file)
    assert isinstance(skeletons, list), (
        f"Trace {trace_id}: scan_file must return a list"
    )
    assert len(skeletons) == 3, (
        f"Trace {trace_id}: expected 3 skeletons, got {len(skeletons)}: {skeletons}"
    )
    assert _to_tuple_set(skeletons) == EXPECTED_FINAL_SKELETONS, (
        f"Trace {trace_id}: skeleton set mismatch.\n"
        f"  Expected: {EXPECTED_FINAL_SKELETONS}\n"
        f"  Got:      {_to_tuple_set(skeletons)}"
    )
    _assert_all_invariants(skeletons)


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_class_name_attribution(js_file, trace_id):
    skeletons = scan_file(js_file)
    by_name = {s["function_name"]: s for s in skeletons}
    assert by_name["getData"]["class_name"] == "A"
    assert by_name["#secret"]["class_name"] == "A"
    assert by_name["helper"]["class_name"] == "None"


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_constructor_excluded(js_file, trace_id):
    skeletons = scan_file(js_file)
    _assert_constructor_exclusion(skeletons)
    func_names = [s["function_name"] for s in skeletons]
    assert "constructor" not in func_names


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_hash_prefix_implies_private(js_file, trace_id):
    skeletons = scan_file(js_file)
    by_name = {s["function_name"]: s for s in skeletons}
    assert by_name["#secret"]["visibility"] == "private"
    _assert_hash_private(skeletons)


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_non_hash_implies_public(js_file, trace_id):
    skeletons = scan_file(js_file)
    _assert_public_default(skeletons)
    by_name = {s["function_name"]: s for s in skeletons}
    assert by_name["getData"]["visibility"] == "public"
    assert by_name["helper"]["visibility"] == "public"


@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_return_type_is_none_sentinel(js_file, trace_id):
    skeletons = scan_file(js_file)
    _assert_return_type_none(skeletons)
    for s in skeletons:
        assert s["return_type"] == "None"


# ---------------------------------------------------------------------------
# Dedicated invariant tests
# ---------------------------------------------------------------------------

class TestDepthConsistency:

    def test_topology_canonical_class_methods_have_string_class_name(self, js_file):
        skeletons = scan_file(js_file)
        class_methods = [s for s in skeletons if s["class_name"] != "None"]
        assert len(class_methods) >= 1
        for s in class_methods:
            assert isinstance(s["class_name"], str) and s["class_name"] != ""
        _assert_depth_consistency(skeletons)

    def test_topology_canonical_top_level_func_has_none_class_name(self, js_file):
        skeletons = scan_file(js_file)
        top_level = [s for s in skeletons if s["class_name"] == "None"]
        assert len(top_level) == 1
        assert top_level[0]["function_name"] == "helper"
        _assert_depth_consistency(skeletons)

    def test_topology_funcs_only_all_class_names_are_none(self, js_file_funcs_only):
        skeletons = scan_file(js_file_funcs_only)
        assert len(skeletons) >= 1
        for s in skeletons:
            assert s["class_name"] == "None"
        _assert_depth_consistency(skeletons)

    def test_topology_class_b_methods_have_class_name_b(self, js_file_class_b):
        skeletons = scan_file(js_file_class_b)
        for s in skeletons:
            if s["function_name"] != "helper":
                assert s["class_name"] == "B"
        _assert_depth_consistency(skeletons)


class TestConstructorExclusion:

    def test_topology_canonical_no_constructor(self, js_file):
        skeletons = scan_file(js_file)
        _assert_constructor_exclusion(skeletons)

    def test_topology_class_b_no_constructor(self, js_file_class_b):
        skeletons = scan_file(js_file_class_b)
        _assert_constructor_exclusion(skeletons)

    def test_topology_constructor_only_yields_empty(self, tmp_path):
        p = tmp_path / "ctor_only.js"
        p.write_text("class E {\n  constructor() {}\n}\n")
        skeletons = scan_file(str(p))
        assert skeletons == []
        _assert_constructor_exclusion(skeletons)

    def test_topology_mixed_constructor_and_methods(self, js_file):
        skeletons = scan_file(js_file)
        func_names = {s["function_name"] for s in skeletons}
        assert "constructor" not in func_names
        assert "getData" in func_names
        assert "#secret" in func_names


class TestHashPrivate:

    def test_topology_canonical_secret_is_private(self, js_file):
        skeletons = scan_file(js_file)
        _assert_hash_private(skeletons)
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["#secret"]["visibility"] == "private"

    def test_topology_multi_hash_all_private(self, js_file_multi_hash):
        skeletons = scan_file(js_file_multi_hash)
        _assert_hash_private(skeletons)
        hash_methods = [s for s in skeletons if s["function_name"].startswith("#")]
        assert len(hash_methods) == 2
        for s in hash_methods:
            assert s["visibility"] == "private"

    def test_topology_class_b_secret_is_private(self, js_file_class_b):
        skeletons = scan_file(js_file_class_b)
        _assert_hash_private(skeletons)
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["#secret"]["visibility"] == "private"

    def test_topology_no_hash_methods_invariant_vacuously_true(self, js_file_all_public):
        skeletons = scan_file(js_file_all_public)
        assert all(not s["function_name"].startswith("#") for s in skeletons)
        _assert_hash_private(skeletons)


class TestPublicDefault:

    def test_topology_canonical_get_data_and_helper_public(self, js_file):
        skeletons = scan_file(js_file)
        _assert_public_default(skeletons)
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["getData"]["visibility"] == "public"
        assert by_name["helper"]["visibility"] == "public"

    def test_topology_all_public_class(self, js_file_all_public):
        skeletons = scan_file(js_file_all_public)
        _assert_public_default(skeletons)
        for s in skeletons:
            assert s["visibility"] == "public"

    def test_topology_multi_hash_gamma_is_public(self, js_file_multi_hash):
        skeletons = scan_file(js_file_multi_hash)
        _assert_public_default(skeletons)
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["gamma"]["visibility"] == "public"

    def test_topology_funcs_only_all_public(self, js_file_funcs_only):
        skeletons = scan_file(js_file_funcs_only)
        _assert_public_default(skeletons)
        for s in skeletons:
            assert s["visibility"] == "public"


class TestReturnTypeNone:

    def test_topology_canonical_all_return_type_none(self, js_file):
        skeletons = scan_file(js_file)
        _assert_return_type_none(skeletons)
        for s in skeletons:
            assert s["return_type"] == "None"

    def test_topology_funcs_only_return_type_none(self, js_file_funcs_only):
        skeletons = scan_file(js_file_funcs_only)
        _assert_return_type_none(skeletons)

    def test_topology_class_b_return_type_none(self, js_file_class_b):
        skeletons = scan_file(js_file_class_b)
        _assert_return_type_none(skeletons)

    def test_topology_multi_hash_return_type_none(self, js_file_multi_hash):
        skeletons = scan_file(js_file_multi_hash)
        _assert_return_type_none(skeletons)


class TestExpectedResults:

    def test_topology_canonical_exact_skeleton_set(self, js_file):
        skeletons = scan_file(js_file)
        assert _to_tuple_set(skeletons) == EXPECTED_FINAL_SKELETONS

    def test_topology_canonical_skeleton_count_is_three(self, js_file):
        skeletons = scan_file(js_file)
        assert len(skeletons) == 3

    def test_topology_class_b_analogous_expected_results(self, js_file_class_b):
        skeletons = scan_file(js_file_class_b)
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["getData"]["class_name"] == "B"
        assert by_name["getData"]["visibility"] == "public"
        assert by_name["#secret"]["class_name"] == "B"
        assert by_name["#secret"]["visibility"] == "private"
        assert by_name["helper"]["class_name"] == "None"
        assert by_name["helper"]["visibility"] == "public"
        assert "constructor" not in by_name
        _assert_structural_invariants(skeletons)

    def test_topology_canonical_all_invariants(self, js_file):
        skeletons = scan_file(js_file)
        _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_file_returns_empty_skeletons(self, tmp_path):
        p = tmp_path / "empty.js"
        p.write_text("")
        skeletons = scan_file(str(p))
        assert isinstance(skeletons, list)
        assert len(skeletons) == 0
        _assert_structural_invariants(skeletons)

    def test_only_constructor_yields_empty(self, tmp_path):
        p = tmp_path / "ctor_only.js"
        p.write_text("class F {\n  constructor() {}\n}\n")
        skeletons = scan_file(str(p))
        assert skeletons == []
        _assert_constructor_exclusion(skeletons)

    def test_single_standalone_function_class_name_none(self, tmp_path):
        p = tmp_path / "lone_func.js"
        p.write_text("function lone() {}\n")
        skeletons = scan_file(str(p))
        assert len(skeletons) == 1
        assert skeletons[0]["function_name"] == "lone"
        assert skeletons[0]["class_name"] == "None"
        assert skeletons[0]["visibility"] == "public"
        assert skeletons[0]["return_type"] == "None"

    def test_single_class_method_no_outside_functions(self, tmp_path):
        p = tmp_path / "single_class.js"
        p.write_text("class G {\n  compute() {}\n}\n")
        skeletons = scan_file(str(p))
        assert len(skeletons) == 1
        assert skeletons[0]["function_name"] == "compute"
        assert skeletons[0]["class_name"] == "G"
        assert skeletons[0]["visibility"] == "public"
        assert skeletons[0]["return_type"] == "None"
        _assert_structural_invariants(skeletons)

    def test_two_independent_classes_no_cross_contamination(self, tmp_path):
        p = tmp_path / "two_classes.js"
        p.write_text(
            "class X {\n  xMethod() {}\n}\n"
            "class Y {\n  yMethod() {}\n}\n"
        )
        skeletons = scan_file(str(p))
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["xMethod"]["class_name"] == "X"
        assert by_name["yMethod"]["class_name"] == "Y"
        _assert_structural_invariants(skeletons)

    def test_class_with_hash_and_public_methods(self, tmp_path):
        p = tmp_path / "mixed_visibility.js"
        p.write_text("class H {\n  #priv() {}\n  pub() {}\n}\n")
        skeletons = scan_file(str(p))
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["#priv"]["visibility"] == "private"
        assert by_name["pub"]["visibility"] == "public"
        assert by_name["#priv"]["class_name"] == "H"
        assert by_name["pub"]["class_name"] == "H"
        _assert_structural_invariants(skeletons)

    def test_class_followed_by_standalone_function(self, tmp_path):
        p = tmp_path / "class_then_func.js"
        p.write_text("class I {\n  method() {}\n}\nfunction stand() {}\n")
        skeletons = scan_file(str(p))
        by_name = {s["function_name"]: s for s in skeletons}
        assert by_name["method"]["class_name"] == "I"
        assert by_name["stand"]["class_name"] == "None"
        _assert_structural_invariants(skeletons)

    def test_multiple_hash_methods_all_private(self, js_file_multi_hash):
        skeletons = scan_file(js_file_multi_hash)
        hash_skeletons = [s for s in skeletons if s["function_name"].startswith("#")]
        assert len(hash_skeletons) == 2
        for s in hash_skeletons:
            assert s["visibility"] == "private"
        _assert_structural_invariants(skeletons)

    def test_constructor_among_many_methods_still_excluded(self, tmp_path):
        p = tmp_path / "ctor_embedded.js"
        p.write_text(
            "class J {\n"
            "  first() {}\n"
            "  constructor() {}\n"
            "  second() {}\n"
            "}\n"
        )
        skeletons = scan_file(str(p))
        func_names = {s["function_name"] for s in skeletons}
        assert "constructor" not in func_names
        assert "first" in func_names
        assert "second" in func_names
        assert len(skeletons) == 2
        _assert_structural_invariants(skeletons)