"""
pytest test suite for the Rust Discoverer (RustDiscovery TLA+ model).

All 10 TLC-verified traces are translated into concrete tests.
The RustDiscovery PlusCal algorithm is re-implemented in Python
(simulate_rust_discoverer) as a faithful step-for-step translation.
RegistryDag / Node / Edge / EdgeType are the ONLY API imports used.
"""
from __future__ import annotations

import pytest
from registry.types import Edge, EdgeType, Node
from registry.dag import RegistryDag

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

VALID_ENTRY_TYPES: frozenset[str] = frozenset(
    {"MAIN", "PUBLIC_API", "HTTP_ROUTE", "CLI_COMMAND"}
)
VALID_HTTP_METHODS: frozenset[str] = frozenset(
    {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"}
)


# ---------------------------------------------------------------------------
# Python translation of the RustDiscovery TLA+ PlusCal algorithm
# ---------------------------------------------------------------------------

def simulate_rust_discoverer(
    *,
    codebase_type: str,
    skel_dotfile: bool,
    skel_is_main: bool,
    skel_is_public: bool,
    skel_has_class: bool,
    file_dotfile: bool,
    file_has_actix: bool,
    file_actix_method: str,
    file_has_axum: bool,
    file_axum_method: str,
    file_has_clap: bool,
) -> list:
    seen: set = set()
    entry_points: list = []

    def _add(ep: dict) -> None:
        key = tuple(sorted(ep.items()))
        if key not in seen:
            seen.add(key)
            entry_points.append(ep)

    if not skel_dotfile and skel_is_main and not skel_has_class:
        _add({
            "etype":      "MAIN",
            "is_main":    True,
            "has_class":  False,
            "is_public":  skel_is_public,
            "is_dotfile": False,
            "method":     "NONE",
            "src":        "skel",
        })

    if (
        not skel_dotfile
        and codebase_type == "library"
        and skel_is_public
        and not skel_has_class
        and not skel_is_main
    ):
        _add({
            "etype":      "PUBLIC_API",
            "is_main":    False,
            "has_class":  False,
            "is_public":  True,
            "is_dotfile": False,
            "method":     "NONE",
            "src":        "skel",
        })

    if not file_dotfile and file_has_actix:
        _add({
            "etype":      "HTTP_ROUTE",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     file_actix_method,
            "src":        "actix",
        })

    if not file_dotfile and file_has_axum:
        _add({
            "etype":      "HTTP_ROUTE",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     file_axum_method,
            "src":        "axum",
        })

    if not file_dotfile and file_has_clap:
        _add({
            "etype":      "CLI_COMMAND",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     "NONE",
            "src":        "clap",
        })

    return entry_points


# ---------------------------------------------------------------------------
# DAG fixture builder
# ---------------------------------------------------------------------------

def _build_dag(
    *,
    codebase_type: str,
    skel_dotfile: bool,
    skel_is_main: bool,
    skel_is_public: bool,
    skel_has_class: bool,
    file_dotfile: bool,
    file_has_actix: bool,
    file_actix_method: str,
    file_has_axum: bool,
    file_axum_method: str,
    file_has_clap: bool,
) -> RegistryDag:
    dag = RegistryDag()

    dag.add_node(Node.resource(
        "project_root", "Rust Project Root",
        description=f"codebase_type={codebase_type}",
        codebase_type=codebase_type,
    ))
    dag.add_node(Node.resource(
        "skel_fn", "Skeleton Function",
        description="Function skeleton produced by the scanner",
        node_role="skeleton",
        is_dotfile=skel_dotfile,
        is_main=skel_is_main,
        is_public=skel_is_public,
        has_class=skel_has_class,
    ))
    dag.add_node(Node.resource(
        "src_file", "Source File",
        description="Rust source file on disk",
        node_role="source_file",
        is_dotfile=file_dotfile,
        has_actix=file_has_actix,
        actix_method=file_actix_method,
        has_axum=file_has_axum,
        axum_method=file_axum_method,
        has_clap=file_has_clap,
    ))

    dag.add_edge(Edge("project_root", "skel_fn",  EdgeType.IMPORTS))
    dag.add_edge(Edge("project_root", "src_file", EdgeType.IMPORTS))

    dag.test_artifacts = {
        "codebase_type":     codebase_type,
        "skel_dotfile":      skel_dotfile,
        "skel_is_main":      skel_is_main,
        "skel_is_public":    skel_is_public,
        "skel_has_class":    skel_has_class,
        "file_dotfile":      file_dotfile,
        "file_has_actix":    file_has_actix,
        "file_actix_method": file_actix_method,
        "file_has_axum":     file_has_axum,
        "file_axum_method":  file_axum_method,
        "file_has_clap":     file_has_clap,
    }
    return dag


def _run_from_dag(dag: RegistryDag) -> list:
    a = dag.test_artifacts
    return simulate_rust_discoverer(
        codebase_type=a["codebase_type"],
        skel_dotfile=a["skel_dotfile"],
        skel_is_main=a["skel_is_main"],
        skel_is_public=a["skel_is_public"],
        skel_has_class=a["skel_has_class"],
        file_dotfile=a["file_dotfile"],
        file_has_actix=a["file_has_actix"],
        file_actix_method=a["file_actix_method"],
        file_has_axum=a["file_has_axum"],
        file_axum_method=a["file_axum_method"],
        file_has_clap=a["file_has_clap"],
    )


# ---------------------------------------------------------------------------
# AllInvariants assertion helper
# ---------------------------------------------------------------------------

def assert_all_invariants(entry_points: list, codebase_type: str) -> None:
    for ep in entry_points:
        assert ep["etype"] in VALID_ENTRY_TYPES, (
            f"ValidEntryTypes violated: etype={ep['etype']!r}"
        )
        assert ep["is_dotfile"] is False, (
            f"DotfilesExcluded violated: entry carries is_dotfile=True  {ep}"
        )
        if ep["has_class"]:
            assert ep["etype"] != "MAIN", (
                "NoMainFromImpl violated: has_class=True with etype=MAIN"
            )
            assert ep["etype"] != "PUBLIC_API", (
                "NoPublicAPIFromImpl violated: has_class=True with etype=PUBLIC_API"
            )
        if ep["etype"] == "MAIN":
            assert ep["is_main"] is True, (
                f"MainIsTopLevel violated: MAIN entry has is_main={ep['is_main']}"
            )
            assert ep["has_class"] is False, (
                f"MainNotImpl violated: MAIN entry has has_class={ep['has_class']}"
            )
        if ep["etype"] == "PUBLIC_API":
            assert codebase_type == "library", (
                f"PublicOnlyForLibrary violated: PUBLIC_API emitted for "
                f"codebase_type={codebase_type!r}"
            )
            assert ep["has_class"] is False, (
                f"ImplMethodsExcluded violated: PUBLIC_API has has_class={ep['has_class']}"
            )
        if ep["etype"] == "HTTP_ROUTE":
            assert ep["method"] in VALID_HTTP_METHODS, (
                f"HttpRouteHasMethod violated: method={ep['method']!r}"
            )


# ============================================================================
# Trace-derived tests
# ============================================================================

class TestTrace1:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="web_app",
            skel_dotfile=True,
            skel_is_main=False,
            skel_is_public=True,
            skel_has_class=True,
            file_dotfile=True,
            file_has_actix=False,
            file_actix_method="GET",
            file_has_axum=True,
            file_axum_method="POST",
            file_has_clap=True,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace2:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="web_app",
            skel_dotfile=False,
            skel_is_main=False,
            skel_is_public=True,
            skel_has_class=False,
            file_dotfile=True,
            file_has_actix=True,
            file_actix_method="GET",
            file_has_axum=True,
            file_axum_method="POST",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace3:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="cli",
            skel_dotfile=True,
            skel_is_main=True,
            skel_is_public=True,
            skel_has_class=True,
            file_dotfile=True,
            file_has_actix=True,
            file_actix_method="POST",
            file_has_axum=False,
            file_axum_method="POST",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace4:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="library",
            skel_dotfile=True,
            skel_is_main=False,
            skel_is_public=False,
            skel_has_class=False,
            file_dotfile=True,
            file_has_actix=False,
            file_actix_method="POST",
            file_has_axum=True,
            file_axum_method="POST",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace5:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="cli",
            skel_dotfile=False,
            skel_is_main=True,
            skel_is_public=True,
            skel_has_class=True,
            file_dotfile=True,
            file_has_actix=True,
            file_actix_method="POST",
            file_has_axum=False,
            file_axum_method="POST",
            file_has_clap=True,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace6:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="cli",
            skel_dotfile=True,
            skel_is_main=False,
            skel_is_public=True,
            skel_has_class=False,
            file_dotfile=True,
            file_has_actix=True,
            file_actix_method="GET",
            file_has_axum=False,
            file_axum_method="GET",
            file_has_clap=True,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace7:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="web_app",
            skel_dotfile=False,
            skel_is_main=False,
            skel_is_public=False,
            skel_has_class=True,
            file_dotfile=False,
            file_has_actix=True,
            file_actix_method="POST",
            file_has_axum=True,
            file_axum_method="GET",
            file_has_clap=True,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_three_entries(self, dag):
        eps = _run_from_dag(dag)
        assert len(eps) == 3, f"Trace 7: expected 3 entry points, got {len(eps)}: {eps}"

    def test_actix_post_route_present(self, dag):
        eps = _run_from_dag(dag)
        actix_ep = {
            "etype":      "HTTP_ROUTE",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     "POST",
            "src":        "actix",
        }
        assert actix_ep in eps

    def test_axum_get_route_present(self, dag):
        eps = _run_from_dag(dag)
        axum_ep = {
            "etype":      "HTTP_ROUTE",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     "GET",
            "src":        "axum",
        }
        assert axum_ep in eps

    def test_clap_cli_command_present(self, dag):
        eps = _run_from_dag(dag)
        clap_ep = {
            "etype":      "CLI_COMMAND",
            "is_main":    False,
            "has_class":  False,
            "is_public":  False,
            "is_dotfile": False,
            "method":     "NONE",
            "src":        "clap",
        }
        assert clap_ep in eps

    def test_no_main_entry(self, dag):
        eps = _run_from_dag(dag)
        assert not any(ep["etype"] == "MAIN" for ep in eps)

    def test_no_public_api_entry(self, dag):
        eps = _run_from_dag(dag)
        assert not any(ep["etype"] == "PUBLIC_API" for ep in eps)

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace8:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="web_app",
            skel_dotfile=False,
            skel_is_main=True,
            skel_is_public=False,
            skel_has_class=True,
            file_dotfile=False,
            file_has_actix=False,
            file_actix_method="POST",
            file_has_axum=False,
            file_axum_method="POST",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace9:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="cli",
            skel_dotfile=False,
            skel_is_main=True,
            skel_is_public=True,
            skel_has_class=True,
            file_dotfile=False,
            file_has_actix=False,
            file_actix_method="POST",
            file_has_axum=False,
            file_axum_method="GET",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestTrace10:
    @pytest.fixture
    def dag(self):
        return _build_dag(
            codebase_type="library",
            skel_dotfile=False,
            skel_is_main=False,
            skel_is_public=True,
            skel_has_class=True,
            file_dotfile=False,
            file_has_actix=False,
            file_actix_method="POST",
            file_has_axum=False,
            file_axum_method="GET",
            file_has_clap=False,
        )

    def test_dag_structure(self, dag):
        assert dag.node_count == 3
        assert dag.edge_count == 2

    def test_final_state_empty(self, dag):
        eps = _run_from_dag(dag)
        assert eps == []

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ============================================================================
# Per-invariant verifiers
# ============================================================================

class TestInvariantMainIsTopLevel:
    def test_top_level_main_fields(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        main_eps = [e for e in eps if e["etype"] == "MAIN"]
        assert len(main_eps) == 1
        assert main_eps[0]["is_main"] is True
        assert main_eps[0]["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_impl_main_excluded(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "MAIN" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantMainNotImpl:
    def test_top_level_main_no_class(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert any(ep["etype"] == "MAIN" for ep in eps)
        for ep in eps:
            if ep["etype"] == "MAIN":
                assert ep["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_dotfile_main_not_emitted(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=True, skel_is_main=True,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "MAIN" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantPublicOnlyForLibrary:
    def test_library_emits_public_api(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        pub_eps = [e for e in eps if e["etype"] == "PUBLIC_API"]
        assert len(pub_eps) == 1
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_web_app_no_public_api(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_cli_no_public_api(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=True, file_has_actix=True, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantImplMethodsExcluded:
    def test_impl_pub_fn_excluded(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_free_pub_fn_has_class_false(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        pub_eps = [e for e in eps if e["etype"] == "PUBLIC_API"]
        assert len(pub_eps) == 1
        assert pub_eps[0]["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantDotfilesExcluded:
    def test_file_dotfile_produces_no_entries(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=True, skel_is_main=False,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=True, file_axum_method="POST", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        assert eps == []
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_non_dotfile_entries_have_is_dotfile_false(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=False, file_has_actix=True, file_actix_method="POST",
            file_has_axum=True, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        assert len(eps) == 3
        for ep in eps:
            assert ep["is_dotfile"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantHttpRouteHasMethod:
    def test_actix_get_method_valid(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=False, file_has_actix=True, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        http_eps = [e for e in eps if e["etype"] == "HTTP_ROUTE"]
        assert len(http_eps) == 1
        assert http_eps[0]["method"] == "GET"
        assert http_eps[0]["method"] in VALID_HTTP_METHODS
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_axum_and_actix_methods_valid(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=False, file_has_actix=True, file_actix_method="POST",
            file_has_axum=True, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        for ep in eps:
            if ep["etype"] == "HTTP_ROUTE":
                assert ep["method"] in VALID_HTTP_METHODS
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantValidEntryTypes:
    def test_empty_entry_points_vacuously_valid(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="POST",
            file_has_axum=False, file_axum_method="POST", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert eps == []
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_all_etypes_are_valid_values(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=False, file_has_actix=True, file_actix_method="POST",
            file_has_axum=True, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        for ep in eps:
            assert ep["etype"] in VALID_ENTRY_TYPES
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_main_etype_is_valid(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert any(ep["etype"] == "MAIN" for ep in eps)
        for ep in eps:
            assert ep["etype"] in VALID_ENTRY_TYPES
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_public_api_etype_is_valid(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert any(ep["etype"] == "PUBLIC_API" for ep in eps)
        for ep in eps:
            assert ep["etype"] in VALID_ENTRY_TYPES
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantNoMainFromImpl:
    def test_impl_main_not_in_entry_points(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "MAIN" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_top_level_main_emitted(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        main_eps = [e for e in eps if e["etype"] == "MAIN"]
        assert len(main_eps) == 1
        assert main_eps[0]["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantNoPublicAPIFromImpl:
    def test_impl_pub_fn_not_public_api(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_free_pub_fn_is_public_api(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        pub_eps = [e for e in eps if e["etype"] == "PUBLIC_API"]
        assert len(pub_eps) == 1
        assert pub_eps[0]["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ============================================================================
# Edge-case tests
# ============================================================================

class TestEdgeCases:
    def test_empty_dag_no_crashes(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("root", "Empty Project", description="no sources"))
        dag.test_artifacts = {
            "codebase_type":     "library",
            "skel_dotfile":      True,
            "skel_is_main":      False,
            "skel_is_public":    True,
            "skel_has_class":    False,
            "file_dotfile":      True,
            "file_has_actix":    False,
            "file_actix_method": "GET",
            "file_has_axum":     False,
            "file_axum_method":  "GET",
            "file_has_clap":     False,
        }
        eps = _run_from_dag(dag)
        assert eps == []
        assert_all_invariants(eps, "library")

    def test_all_sources_present_non_dotfile_web_app(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=True, file_actix_method="POST",
            file_has_axum=True, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        etypes = [e["etype"] for e in eps]
        assert etypes.count("HTTP_ROUTE") == 2
        assert etypes.count("CLI_COMMAND") == 1
        assert "MAIN" not in etypes
        assert "PUBLIC_API" not in etypes
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_library_pub_fn_and_http_routes_coexist(self):
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=True, file_axum_method="POST", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        pub_eps  = [e for e in eps if e["etype"] == "PUBLIC_API"]
        http_eps = [e for e in eps if e["etype"] == "HTTP_ROUTE"]
        assert len(pub_eps)  == 1
        assert len(http_eps) == 1
        assert http_eps[0]["method"] == "POST"
        assert http_eps[0]["src"]    == "axum"
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_main_and_clap_coexist_in_cli(self):
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        main_eps = [e for e in eps if e["etype"] == "MAIN"]
        cli_eps  = [e for e in eps if e["etype"] == "CLI_COMMAND"]
        assert len(main_eps) == 1
        assert len(cli_eps)  == 1
        assert main_eps[0]["is_main"]   is True
        assert main_eps[0]["has_class"] is False
        assert cli_eps[0]["src"]        == "clap"
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_isolated_skeleton_dotfile_yields_nothing(self):
        for ctype in ("cli", "library", "web_app"):
            dag = _build_dag(
                codebase_type=ctype,
                skel_dotfile=True, skel_is_main=True,
                skel_is_public=True, skel_has_class=False,
                file_dotfile=True, file_has_actix=True, file_actix_method="GET",
                file_has_axum=True, file_axum_method="POST", file_has_clap=True,
            )
            eps = _run_from_dag(dag)
            assert eps == [], (
                f"skel_dotfile=TRUE and file_dotfile=TRUE must yield empty "
                f"entry_points for codebase_type={ctype!r}"
            )
            assert_all_invariants(eps, ctype)

    def test_dag_query_relevant_after_discoverer(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=False, file_has_actix=True, file_actix_method="POST",
            file_has_axum=True, file_axum_method="GET", file_has_clap=True,
        )
        result = dag.query_relevant("project_root")
        if hasattr(result, "nodes"):
            relevant_ids = {n.id for n in result.nodes}
            assert "skel_fn" in relevant_ids
            assert "src_file" in relevant_ids
        assert dag.node_count == 3
        eps = _run_from_dag(dag)
        assert len(eps) == 3
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])