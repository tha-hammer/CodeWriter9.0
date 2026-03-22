import pytest

from scanner_rust_nested_depth import scan_file
from registry.dag import RegistryDag
from registry.types import Node


# ---------------------------------------------------------------------------
# Rust source templates – derived directly from the TLC event sequence
#
#   Event 1: ImplOpen("Foo")          → impl Foo {
#   Event 2: Fn("bar") in impl Foo    →     fn bar() {}
#   Event 3: CloseBrace               → }
#   Event 4: TraitOpen                → trait SomeTrait {
#   Event 5: Fn("baz") in trait       →     fn baz() {}   ← must be excluded
#   Event 6: CloseBrace               → }
#   Event 7: Fn("free") at top level  → fn free() {}
#
# Final TLC state (all 10 traces identical):
#   skeletons = { {class_name="Foo",  func_name="bar"},
#                 {class_name=None,   func_name="free"} }
# ---------------------------------------------------------------------------

RUST_CANONICAL = (
    "impl Foo {\n"
    "    fn bar() {}\n"
    "}\n"
    "trait SomeTrait {\n"
    "    fn baz() {}\n"
    "}\n"
    "fn free() {}\n"
)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _to_pairs(skeletons) -> frozenset:
    """Return frozenset of (func_name, class_name) from whatever scan_file returns."""
    pairs = set()
    for s in skeletons:
        if hasattr(s, "func_name"):
            pairs.add((s.func_name, s.class_name))
        else:
            pairs.add((s["func_name"], s["class_name"]))
    return frozenset(pairs)


def _class_name(s):
    return s.class_name if hasattr(s, "class_name") else s["class_name"]


def _func_name(s):
    return s.func_name if hasattr(s, "func_name") else s["func_name"]


# ---------------------------------------------------------------------------
# TLA+ invariant verifiers
# (hold at EVERY intermediate state; called on the terminal skeletons)
# ---------------------------------------------------------------------------

def _check_impl_resolution(skeletons):
    """
    ImplResolution: class_name is either None (free fn) or a *non-empty* string.
    """
    for s in skeletons:
        cn = _class_name(s)
        assert cn is None or (isinstance(cn, str) and cn != ""), (
            f"ImplResolution violated: class_name={cn!r} must be None or "
            f"a non-empty str"
        )


def _check_trait_exclusion(skeletons):
    """TraitExclusion: no skeleton whose func_name is 'baz' (a trait method)."""
    bad = [s for s in skeletons if _func_name(s) == "baz"]
    assert not bad, (
        f"TraitExclusion violated: 'baz' must never appear in skeletons, got {bad}"
    )


def _check_all_non_trait_fns_recorded(skeletons):
    """
    AllNonTraitFnsRecorded (only meaningful once cursor > N=7):
      • bar  with class_name="Foo" is present
      • free with class_name=None  is present
      • baz  is absent
    """
    pairs = _to_pairs(skeletons)
    assert ("bar", "Foo") in pairs, (
        f"AllNonTraitFnsRecorded violated: (bar, Foo) missing from {pairs}"
    )
    assert ("free", None) in pairs, (
        f"AllNonTraitFnsRecorded violated: (free, None) missing from {pairs}"
    )
    assert not any(fn == "baz" for fn, _ in pairs), (
        f"AllNonTraitFnsRecorded violated: baz must be absent, got {pairs}"
    )


def _assert_all_invariants(skeletons):
    _check_impl_resolution(skeletons)
    _check_trait_exclusion(skeletons)
    _check_all_non_trait_fns_recorded(skeletons)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def canonical_rs(tmp_path):
    """
    Fixture derived from Init state of all 10 TLC traces.
    Init: skeletons={}, block_stack=<<>>, cursor=1
    The file encodes exactly the 7 events in the TLC model.
    """
    p = tmp_path / "lib.rs"
    p.write_text(RUST_CANONICAL)
    return str(p)


# ---------------------------------------------------------------------------
# Trace-derived tests  (Traces 1-10 are structurally identical)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_id", range(1, 11))
def test_trace_canonical_final_state(canonical_rs, trace_id):
    """
    Traces 1-10 — ImplResolution, TraitExclusion, AllNonTraitFnsRecorded.

    Expected final state (TLC State 24 for every trace):
        skeletons = { {class_name="Foo", func_name="bar"},
                      {class_name=None,  func_name="free"} }
        block_stack = <<>>   (scanner left no dangling blocks)
    """
    skeletons = list(scan_file(canonical_rs))
    pairs = _to_pairs(skeletons)

    assert ("bar", "Foo") in pairs, (
        f"[trace {trace_id}] bar/Foo missing from skeletons: {pairs}"
    )
    assert ("free", None) in pairs, (
        f"[trace {trace_id}] free/None missing from skeletons: {pairs}"
    )
    assert len(pairs) == 2, (
        f"[trace {trace_id}] Expected exactly 2 skeletons, got {pairs}"
    )

    _assert_all_invariants(skeletons)


# ---------------------------------------------------------------------------
# Dedicated ImplResolution verifier
# ---------------------------------------------------------------------------

class TestImplResolution:
    """Every skeleton's class_name is either None (free fn) or a type-name string."""

    def test_impl_method_carries_type_name(self, tmp_path):
        p = tmp_path / "impl_only.rs"
        p.write_text("impl Foo {\n    fn bar() {}\n}\n")
        skeletons = list(scan_file(str(p)))

        _check_impl_resolution(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("bar", "Foo") in pairs

    def test_free_fn_carries_none_class_name(self, tmp_path):
        p = tmp_path / "free_only.rs"
        p.write_text("fn free() {}\n")
        skeletons = list(scan_file(str(p)))

        _check_impl_resolution(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("free", None) in pairs

    def test_canonical_both_class_names_valid(self, canonical_rs):
        skeletons = list(scan_file(canonical_rs))
        _check_impl_resolution(skeletons)
        for s in skeletons:
            cn = _class_name(s)
            assert cn is None or (isinstance(cn, str) and cn != ""), (
                f"class_name {cn!r} is invalid"
            )

    def test_multiple_impl_blocks_each_get_own_class_name(self, tmp_path):
        p = tmp_path / "two_impls.rs"
        p.write_text(
            "impl Alpha {\n    fn one() {}\n}\n"
            "impl Beta  {\n    fn two() {}\n}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("one", "Alpha") in pairs
        assert ("two", "Beta") in pairs


# ---------------------------------------------------------------------------
# Dedicated TraitExclusion verifier
# ---------------------------------------------------------------------------

class TestTraitExclusion:
    """Functions declared inside trait blocks are never recorded as skeletons."""

    def test_canonical_baz_excluded(self, canonical_rs):
        skeletons = list(scan_file(canonical_rs))
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert all(fn != "baz" for fn, _ in pairs)

    def test_trait_only_file_yields_empty_skeletons(self, tmp_path):
        p = tmp_path / "trait_only.rs"
        p.write_text("trait T {\n    fn baz() {}\n    fn qux() {}\n}\n")
        skeletons = list(scan_file(str(p)))
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert len(pairs) == 0, f"Expected empty skeletons, got {pairs}"

    def test_trait_impl_for_type_excluded(self, tmp_path):
        p = tmp_path / "trait_impl.rs"
        p.write_text(
            "impl SomeTrait for Foo {\n"
            "    fn baz() {}\n"
            "}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert len(pairs) == 0, (
            f"impl Trait for Type methods must be fully excluded, got {pairs}"
        )

    def test_trait_exclusion_does_not_suppress_impl_methods(self, tmp_path):
        p = tmp_path / "impl_then_trait.rs"
        p.write_text(
            "impl Foo {\n    fn bar() {}\n}\n"
            "trait T {\n    fn baz() {}\n}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("bar", "Foo") in pairs
        assert len(pairs) == 1


# ---------------------------------------------------------------------------
# Dedicated AllNonTraitFnsRecorded verifier
# ---------------------------------------------------------------------------

class TestAllNonTraitFnsRecorded:
    """
    After scanning the full file (cursor > N):
    • every non-trait fn is present in skeletons
    • trait methods are absent
    """

    def test_canonical_all_fns_recorded(self, canonical_rs):
        skeletons = list(scan_file(canonical_rs))
        _check_all_non_trait_fns_recorded(skeletons)

    def test_impl_method_recorded_after_trait_block(self, tmp_path):
        p = tmp_path / "trait_then_impl.rs"
        p.write_text(
            "trait T {\n    fn baz() {}\n}\n"
            "impl Foo {\n    fn bar() {}\n}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_trait_exclusion(skeletons)
        _check_impl_resolution(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("bar", "Foo") in pairs
        assert ("baz", "T") not in pairs
        assert all(fn != "baz" for fn, _ in pairs)

    def test_free_fn_recorded_after_impl_closes(self, tmp_path):
        p = tmp_path / "impl_then_free.rs"
        p.write_text(
            "impl Foo {\n    fn bar() {}\n}\n"
            "fn free() {}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("bar", "Foo") in pairs
        assert ("free", None) in pairs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_file_yields_no_skeletons(self, tmp_path):
        p = tmp_path / "empty.rs"
        p.write_text("")
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        assert len(skeletons) == 0

    def test_empty_impl_block_yields_no_skeletons(self, tmp_path):
        p = tmp_path / "empty_impl.rs"
        p.write_text("impl Foo {}\n")
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        assert len(_to_pairs(skeletons)) == 0

    def test_empty_trait_block_yields_no_skeletons(self, tmp_path):
        p = tmp_path / "empty_trait.rs"
        p.write_text("trait T {}\n")
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        assert len(_to_pairs(skeletons)) == 0

    def test_multiple_free_fns_all_get_none_class_name(self, tmp_path):
        p = tmp_path / "multi_free.rs"
        p.write_text("fn alpha() {}\nfn beta() {}\nfn gamma() {}\n")
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("alpha", None) in pairs
        assert ("beta",  None) in pairs
        assert ("gamma", None) in pairs

    def test_multiple_impls_distinct_class_names(self, tmp_path):
        p = tmp_path / "multi_impl.rs"
        p.write_text(
            "impl Alpha {\n    fn one() {}\n}\n"
            "impl Beta  {\n    fn two() {}\n}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("one", "Alpha") in pairs
        assert ("two", "Beta")  in pairs
        assert ("one", "Beta")  not in pairs
        assert ("two", "Alpha") not in pairs

    def test_block_stack_fully_unwinds_between_blocks(self, tmp_path):
        p = tmp_path / "unwind.rs"
        p.write_text(
            "impl Foo {\n    fn bar() {}\n}\n"
            "fn free() {}\n"
        )
        skeletons = list(scan_file(str(p)))
        pairs = _to_pairs(skeletons)
        assert ("free", "Foo") not in pairs
        assert ("free", None) in pairs
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)

    def test_interleaved_trait_and_impl_ordering(self, tmp_path):
        p = tmp_path / "interleaved.rs"
        p.write_text(
            "trait T {\n    fn baz() {}\n}\n"
            "impl Foo {\n    fn bar() {}\n}\n"
            "fn free() {}\n"
        )
        skeletons = list(scan_file(str(p)))
        _check_impl_resolution(skeletons)
        _check_trait_exclusion(skeletons)
        pairs = _to_pairs(skeletons)
        assert ("bar",  "Foo") in pairs
        assert ("free", None)  in pairs
        assert all(fn != "baz" for fn, _ in pairs)

    def test_dag_node_for_scanned_skeleton(self, tmp_path):
        p = tmp_path / "dag_compat.rs"
        p.write_text("impl Foo {\n    fn bar() {}\n}\n")
        skeletons = list(scan_file(str(p)))
        pairs = _to_pairs(skeletons)
        assert ("bar", "Foo") in pairs

        dag = RegistryDag()
        for fn, cn in pairs:
            node_id = f"{cn or 'free'}__{fn}"
            dag.add_node(
                Node.behavior(
                    id=node_id,
                    name=node_id,
                    given="rust source with impl block",
                    when="scan_file is called",
                    then=f"method {fn} recorded under class {cn}",
                )
            )
        assert dag.node_count == len(pairs)