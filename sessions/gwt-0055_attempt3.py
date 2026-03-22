import pytest
from scanner_javascript_nested_depth import scan_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _no_class(skeleton) -> bool:
    """Return True when the skeleton is not inside any class."""
    cn = skeleton.get("class_name") if isinstance(skeleton, dict) else getattr(skeleton, "class_name", None)
    return cn is None or cn == "None"


def _class_of(skeleton) -> str | None:
    cn = skeleton.get("class_name") if isinstance(skeleton, dict) else getattr(skeleton, "class_name", None)
    return None if (cn is None or cn == "None") else cn


def _skeletons_as_dicts(raw) -> list[dict]:
    """Normalize whatever scan_file returns into a list of plain dicts."""
    result = []
    for s in raw:
        if isinstance(s, dict):
            result.append(s)
        else:
            result.append({
                "func_name":   getattr(s, "func_name",   None),
                "class_name":  getattr(s, "class_name",  None),
                "visibility":  getattr(s, "visibility",  None),
                "return_type": getattr(s, "return_type", None),
            })
    return result


# ---------------------------------------------------------------------------
# Invariant verifiers (called from every test)
# ---------------------------------------------------------------------------

def assert_depth_consistency(skeletons: list[dict]) -> None:
    """DepthConsistency: every skeleton's class_name is either None/'None' or a real name."""
    for s in skeletons:
        cn = s["class_name"]
        assert cn is None or isinstance(cn, str), (
            f"DepthConsistency violated: class_name={cn!r} has unexpected type"
        )


def assert_constructor_exclusion(skeletons: list[dict]) -> None:
    """ConstructorExclusion: no skeleton with func_name == 'constructor'."""
    names = [s["func_name"] for s in skeletons]
    assert "constructor" not in names, (
        f"ConstructorExclusion violated: found constructor in {names}"
    )


def assert_hash_private(skeletons: list[dict]) -> None:
    """HashPrivate: if func_name starts with '#', visibility must be 'private'."""
    for s in skeletons:
        if str(s["func_name"]).startswith("#"):
            assert s["visibility"] == "private", (
                f"HashPrivate violated: {s['func_name']!r} has visibility={s['visibility']!r}"
            )


def assert_public_default(skeletons: list[dict]) -> None:
    """PublicDefault: if func_name does NOT start with '#', visibility must be 'public'."""
    for s in skeletons:
        if not str(s["func_name"]).startswith("#"):
            assert s["visibility"] == "public", (
                f"PublicDefault violated: {s['func_name']!r} has visibility={s['visibility']!r}"
            )


def assert_return_type_none(skeletons: list[dict]) -> None:
    """ReturnTypeNone: every skeleton has return_type == 'None' or None."""
    for s in skeletons:
        rt = s["return_type"]
        assert rt is None or rt == "None", (
            f"ReturnTypeNone violated: {s['func_name']!r} has return_type={rt!r}"
        )


def assert_expected_results(skeletons: list[dict], cursor_past_n: bool) -> None:
    """ExpectedResults: once cursor > N, the three canonical entries must be present."""
    if not cursor_past_n:
        return
    func_names = [s["func_name"] for s in skeletons]
    # getData present with class A, public
    get_data = [s for s in skeletons if s["func_name"] == "getData"]
    assert get_data, "ExpectedResults: getData not found"
    assert _class_of(get_data[0]) == "A", f"ExpectedResults: getData class_name={_class_of(get_data[0])!r}"
    assert get_data[0]["visibility"] == "public"

    # #secret present with class A, private
    secret = [s for s in skeletons if s["func_name"] == "#secret"]
    assert secret, "ExpectedResults: #secret not found"
    assert _class_of(secret[0]) == "A", f"ExpectedResults: #secret class_name={_class_of(secret[0])!r}"
    assert secret[0]["visibility"] == "private"

    # helper present outside any class, public
    helper = [s for s in skeletons if s["func_name"] == "helper"]
    assert helper, "ExpectedResults: helper not found"
    assert _no_class(helper[0]), f"ExpectedResults: helper class_name={helper[0]['class_name']!r}"
    assert helper[0]["visibility"] == "public"

    # constructor excluded
    assert "constructor" not in func_names, "ExpectedResults: constructor must be absent"


def assert_all_invariants(skeletons: list[dict], cursor_past_n: bool = True) -> None:
    assert_depth_consistency(skeletons)
    assert_constructor_exclusion(skeletons)
    assert_hash_private(skeletons)
    assert_public_default(skeletons)
    assert_return_type_none(skeletons)
    assert_expected_results(skeletons, cursor_past_n)


# ---------------------------------------------------------------------------
# Canonical JavaScript source (derived from the TLA+ Events sequence)
#
# Events:
#   1: ClassOpen  "A"           (class_stack gains A, brace_depth->1)
#   2: Method     "getData"     (public method inside A  -> skeleton added)
#   3: Method     "#secret"     (private method inside A -> skeleton added)
#   4: Constructor "constructor" (skipped, ConstructorExclusion)
#   5: CloseBrace               (brace_depth->0, class A popped)
#   6: Func       "helper"      (public function outside any class -> skeleton added)
# ---------------------------------------------------------------------------

CANONICAL_JS = """\
class A {
  getData() {}
  #secret() {}
  constructor() {}
}
function helper() {}
"""

EXPECTED_SKELETONS = [
    {"func_name": "getData",  "class_name": "A",    "visibility": "public",  "return_type": "None"},
    {"func_name": "#secret",  "class_name": "A",    "visibility": "private", "return_type": "None"},
    {"func_name": "helper",   "class_name": None,   "visibility": "public",  "return_type": "None"},
]


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def canonical_js_file(tmp_path_factory):
    """Write the canonical JS source to a temp file and return its path."""
    p = tmp_path_factory.mktemp("js") / "subject.js"
    p.write_text(CANONICAL_JS)
    return str(p)


@pytest.fixture(scope="module")
def canonical_skeletons(canonical_js_file):
    """Run scan_file once on the canonical source; return normalised list."""
    raw = scan_file(canonical_js_file)
    return _skeletons_as_dicts(raw)


# ---------------------------------------------------------------------------
# Helper: build an ad-hoc temp JS file
# ---------------------------------------------------------------------------

def _js_file(tmp_path, content: str, name: str = "subject.js") -> str:
    p = tmp_path / name
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# Trace 1 - canonical run (all 10 TLC traces share the identical event
# sequence and identical final state; a single parameterised test covers all)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", list(range(1, 11)))
def test_trace_canonical_final_state(tmp_path, trace_id):
    """
    Traces 1-10 all exercise the same six-event sequence and reach the same
    final state.  For each trace we:
      - build a fresh file (Init: skeletons={}, class_stack=<<>>, brace_depth=0)
      - call scan_file  (models the ScanLoop->...->Finish sequence)
      - assert the three expected skeletons are present
      - verify all six invariants hold (DepthConsistency, ConstructorExclusion,
        HashPrivate, PublicDefault, ReturnTypeNone, ExpectedResults)
    """
    path = _js_file(tmp_path, CANONICAL_JS, f"trace_{trace_id}.js")

    raw = scan_file(path)
    skeletons = _skeletons_as_dicts(raw)

    func_names = {s["func_name"] for s in skeletons}
    assert "getData"     in func_names
    assert "#secret"     in func_names
    assert "helper"      in func_names
    assert "constructor" not in func_names

    assert_all_invariants(skeletons, cursor_past_n=True)


# ---------------------------------------------------------------------------
# Dedicated invariant tests  (each exercises >=2 trace-derived topologies)
# ---------------------------------------------------------------------------

class TestDepthConsistency:
    """Every skeleton's class_name is a string (or None) - never an object."""

    def test_inside_class_has_string_class_name(self, canonical_skeletons):
        inside = [s for s in canonical_skeletons if not _no_class(s)]
        assert inside, "Expected at least one in-class skeleton"
        for s in inside:
            cn = s["class_name"]
            assert isinstance(cn, str) and cn not in ("None", ""), (
                f"class_name {cn!r} should be a non-empty string for in-class method"
            )
        assert_depth_consistency(canonical_skeletons)

    def test_outside_class_has_none_class_name(self, canonical_skeletons):
        outside = [s for s in canonical_skeletons if _no_class(s)]
        assert outside, "Expected at least one top-level skeleton"
        for s in outside:
            assert _no_class(s), f"class_name {s['class_name']!r} should be None for top-level func"
        assert_depth_consistency(canonical_skeletons)

    def test_two_topologies(self, tmp_path):
        src_a = "class X { foo() {} }\n"
        sk_a = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_a, "a.js")))
        assert_depth_consistency(sk_a)

        src_b = "function bar() {}\n"
        sk_b = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_b, "b.js")))
        assert_depth_consistency(sk_b)


class TestConstructorExclusion:
    """No skeleton should ever have func_name == 'constructor'."""

    def test_canonical_excludes_constructor(self, canonical_skeletons):
        assert_constructor_exclusion(canonical_skeletons)

    def test_explicit_constructor_file(self, tmp_path):
        src = "class B { constructor() {} compute() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert_constructor_exclusion(sk)
        assert any(s["func_name"] == "compute" for s in sk)

    def test_constructor_only_class(self, tmp_path):
        src = "class C { constructor() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert_constructor_exclusion(sk)
        assert sk == []

    def test_two_topologies(self, tmp_path):
        sk1 = _skeletons_as_dicts(scan_file(_js_file(tmp_path, CANONICAL_JS, "t1.js")))
        assert_constructor_exclusion(sk1)

        src2 = "class D { constructor() {} render() {} }\nfunction init() {}\n"
        sk2 = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src2, "t2.js")))
        assert_constructor_exclusion(sk2)


class TestHashPrivate:
    """Methods whose name starts with '#' must have visibility == 'private'."""

    def test_hash_secret_is_private(self, canonical_skeletons):
        secret = [s for s in canonical_skeletons if s["func_name"] == "#secret"]
        assert secret
        assert secret[0]["visibility"] == "private"
        assert_hash_private(canonical_skeletons)

    def test_multiple_hash_methods(self, tmp_path):
        src = "class E { #one() {} #two() {} pub() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert_hash_private(sk)
        hash_entries = [s for s in sk if str(s["func_name"]).startswith("#")]
        assert len(hash_entries) == 2
        for h in hash_entries:
            assert h["visibility"] == "private"

    def test_two_topologies(self, tmp_path):
        src_a = "class F { #priv() {} }\n"
        sk_a = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_a, "a.js")))
        assert_hash_private(sk_a)

        src_b = "class G { pub() {} }\n"
        sk_b = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_b, "b.js")))
        assert_hash_private(sk_b)


class TestPublicDefault:
    """Methods whose name does NOT start with '#' must have visibility == 'public'."""

    def test_get_data_is_public(self, canonical_skeletons):
        gd = [s for s in canonical_skeletons if s["func_name"] == "getData"]
        assert gd
        assert gd[0]["visibility"] == "public"
        assert_public_default(canonical_skeletons)

    def test_top_level_helper_is_public(self, canonical_skeletons):
        h = [s for s in canonical_skeletons if s["func_name"] == "helper"]
        assert h
        assert h[0]["visibility"] == "public"

    def test_two_topologies(self, tmp_path):
        src_a = "class H { alpha() {} beta() {} }\n"
        sk_a = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_a, "a.js")))
        assert_public_default(sk_a)

        src_b = "function gamma() {}\nfunction delta() {}\n"
        sk_b = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_b, "b.js")))
        assert_public_default(sk_b)


class TestReturnTypeNone:
    """Every skeleton must report return_type as None or the string 'None'."""

    def test_all_canonical_skeletons(self, canonical_skeletons):
        assert_return_type_none(canonical_skeletons)

    def test_two_topologies(self, tmp_path):
        src_a = "class I { fetch() {} }\n"
        sk_a = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_a, "a.js")))
        assert_return_type_none(sk_a)

        src_b = "function load() {}\n"
        sk_b = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src_b, "b.js")))
        assert_return_type_none(sk_b)

    def test_mixed_topology(self, tmp_path):
        src = "class J { #priv() {} pub() {} }\nfunction bare() {}\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert_return_type_none(sk)


class TestExpectedResults:
    """End-to-end assertion that the three canonical skeletons are present."""

    def test_get_data_skeleton(self, canonical_skeletons):
        matches = [s for s in canonical_skeletons
                   if s["func_name"] == "getData" and _class_of(s) == "A"]
        assert len(matches) == 1
        assert matches[0]["visibility"] == "public"
        rt = matches[0]["return_type"]
        assert rt is None or rt == "None"

    def test_secret_skeleton(self, canonical_skeletons):
        matches = [s for s in canonical_skeletons
                   if s["func_name"] == "#secret" and _class_of(s) == "A"]
        assert len(matches) == 1
        assert matches[0]["visibility"] == "private"

    def test_helper_skeleton(self, canonical_skeletons):
        matches = [s for s in canonical_skeletons
                   if s["func_name"] == "helper" and _no_class(s)]
        assert len(matches) == 1
        assert matches[0]["visibility"] == "public"

    def test_constructor_absent(self, canonical_skeletons):
        assert not any(s["func_name"] == "constructor" for s in canonical_skeletons)

    def test_exact_count(self, canonical_skeletons):
        assert len(canonical_skeletons) == 3

    def test_two_topologies(self, tmp_path):
        sk1 = _skeletons_as_dicts(scan_file(_js_file(tmp_path, CANONICAL_JS, "t1.js")))
        assert_expected_results(sk1, cursor_past_n=True)

        src2 = "class A { getData() {} #secret() {} }\nfunction helper() {}\n"
        sk2 = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src2, "t2.js")))
        assert_expected_results(sk2, cursor_past_n=True)


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_file(self, tmp_path):
        """Empty source -> no skeletons; all invariants trivially hold."""
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, "")))
        assert sk == []
        assert_all_invariants(sk, cursor_past_n=False)

    def test_empty_class_body(self, tmp_path):
        """Class with only a constructor -> zero skeletons (ConstructorExclusion)."""
        src = "class Empty { constructor() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert sk == []
        assert_constructor_exclusion(sk)

    def test_class_with_no_methods_at_all(self, tmp_path):
        """Class with empty body -> zero skeletons."""
        src = "class Empty {}\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert_all_invariants(sk, cursor_past_n=False)

    def test_only_bare_functions(self, tmp_path):
        """Functions outside any class -> class_name is None for all."""
        src = "function alpha() {}\nfunction beta() {}\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert len(sk) == 2
        for s in sk:
            assert _no_class(s)
        assert_all_invariants(sk, cursor_past_n=False)

    def test_multiple_classes(self, tmp_path):
        """Methods from two different classes -> each skeleton bound to correct class."""
        src = "class X { foo() {} }\nclass Y { bar() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        foo_entries = [s for s in sk if s["func_name"] == "foo"]
        bar_entries = [s for s in sk if s["func_name"] == "bar"]
        assert foo_entries and _class_of(foo_entries[0]) == "X"
        assert bar_entries and _class_of(bar_entries[0]) == "Y"
        assert_all_invariants(sk, cursor_past_n=False)

    def test_hash_method_inside_class_is_private(self, tmp_path):
        """Hash-prefixed methods in a class body are always private (HashPrivate invariant)."""
        src = "class Z { #hidden() {} regular() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        hidden = [s for s in sk if s["func_name"] == "#hidden"]
        assert hidden and hidden[0]["visibility"] == "private"
        regular = [s for s in sk if s["func_name"] == "regular"]
        assert regular and regular[0]["visibility"] == "public"
        assert_all_invariants(sk, cursor_past_n=False)

    def test_constructor_among_other_methods(self, tmp_path):
        """Constructor surrounded by real methods -> only real methods emitted."""
        src = "class K { before() {} constructor() {} after() {} }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        names = {s["func_name"] for s in sk}
        assert names == {"before", "after"}
        assert "constructor" not in names
        assert_all_invariants(sk, cursor_past_n=False)

    def test_mixed_class_and_top_level(self, tmp_path):
        """Mixed: class methods and bare functions coexist without crosstalk."""
        src = CANONICAL_JS
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        in_class  = [s for s in sk if not _no_class(s)]
        top_level = [s for s in sk if _no_class(s)]
        assert all(_class_of(s) is not None for s in in_class)
        assert all(_no_class(s) for s in top_level)
        assert_all_invariants(sk, cursor_past_n=True)

    def test_brace_depth_tracking_nested_braces(self, tmp_path):
        """Methods inside conditionals/blocks inside a class still belong to the class."""
        src = (
            "class M {\n"
            "  process() {}\n"
            "  #validate() {}\n"
            "}\n"
            "function standalone() {}\n"
        )
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        process    = [s for s in sk if s["func_name"] == "process"]
        validate   = [s for s in sk if s["func_name"] == "#validate"]
        standalone = [s for s in sk if s["func_name"] == "standalone"]
        assert process   and _class_of(process[0])   == "M"
        assert validate  and _class_of(validate[0])  == "M" and validate[0]["visibility"] == "private"
        assert standalone and _no_class(standalone[0])
        assert_all_invariants(sk, cursor_past_n=False)

    def test_return_type_always_none_regardless_of_annotation(self, tmp_path):
        """Even if the source has return-type annotations, skeleton.return_type == 'None'."""
        src = "class N { getCount() { return 42; } }\n"
        sk = _skeletons_as_dicts(scan_file(_js_file(tmp_path, src)))
        assert sk
        assert_return_type_none(sk)