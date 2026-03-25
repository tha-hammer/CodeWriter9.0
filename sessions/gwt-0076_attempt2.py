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
) -> list[dict]:
    """
    Direct Python translation of the RustDiscovery TLA+ PlusCal algorithm.

    Actions execute in deterministic order:
      SkelCheckMain -> SkelCheckPubAPI -> FileCheckActix
      -> FileCheckAxum -> FileCheckClap -> Finish (no-op)

    Returns the final entry_points list (set semantics via dedup).
    """
    seen: set[tuple] = set()
    entry_points: list[dict] = []

    def _add(ep: dict) -> None:
        key = tuple(sorted(ep.items()))
        if key not in seen:
            seen.add(key)
            entry_points.append(ep)

    # -- SkelCheckMain -------------------------------------------------------
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

    # -- SkelCheckPubAPI -----------------------------------------------------
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

    # -- FileCheckActix -------------------------------------------------------
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

    # -- FileCheckAxum --------------------------------------------------------
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

    # -- FileCheckClap --------------------------------------------------------
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

    # -- Finish ---------------------------------------------------------------
    # skip (no-op in TLA+)
    return entry_points


# ---------------------------------------------------------------------------
# DAG fixture builder – encodes the TLA+ Init state into a RegistryDag
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
    """
    Construct a RegistryDag whose topology mirrors the Rust project
    structure described by one TLA+ Init-state variable assignment.

    Nodes
    -----
    project_root  - the Cargo workspace root (resource node)
    skel_fn       - one function skeleton from the scanner (resource node)
    src_file      - one Rust source file on disk (resource node)

    Edges
    -----
    project_root -> skel_fn  (IMPORTS)
    project_root -> src_file (IMPORTS)

    All TLA+ variables are persisted in dag.test_artifacts for use by
    _run_from_dag / assert_all_invariants.
    """
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


def _run_from_dag(dag: RegistryDag) -> list[dict]:
    """Invoke the discoverer using the artifacts stored inside *dag*."""
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

def assert_all_invariants(entry_points: list[dict], codebase_type: str) -> None:
    """
    Assert all nine TLA+ invariants hold on *entry_points*.

    Invariants checked (in AllInvariants conjunction):
      ValidEntryTypes, DotfilesExcluded,
      MainIsTopLevel, MainNotImpl,
      PublicOnlyForLibrary, ImplMethodsExcluded,
      HttpRouteHasMethod,
      NoMainFromImpl, NoPublicAPIFromImpl.
    """
    for ep in entry_points:
        # ValidEntryTypes
        assert ep["etype"] in VALID_ENTRY_TYPES, (
            f"ValidEntryTypes violated: etype={ep['etype']!r}"
        )
        # DotfilesExcluded
        assert ep["is_dotfile"] is False, (
            f"DotfilesExcluded violated: entry carries is_dotfile=True  {ep}"
        )
        # NoMainFromImpl / NoPublicAPIFromImpl
        if ep["has_class"]:
            assert ep["etype"] != "MAIN", (
                "NoMainFromImpl violated: has_class=True with etype=MAIN"
            )
            assert ep["etype"] != "PUBLIC_API", (
                "NoPublicAPIFromImpl violated: has_class=True with etype=PUBLIC_API"
            )
        # MainIsTopLevel + MainNotImpl
        if ep["etype"] == "MAIN":
            assert ep["is_main"] is True, (
                f"MainIsTopLevel violated: MAIN entry has is_main={ep['is_main']}"
            )
            assert ep["has_class"] is False, (
                f"MainNotImpl violated: MAIN entry has has_class={ep['has_class']}"
            )
        # PublicOnlyForLibrary + ImplMethodsExcluded
        if ep["etype"] == "PUBLIC_API":
            assert codebase_type == "library", (
                f"PublicOnlyForLibrary violated: PUBLIC_API emitted for "
                f"codebase_type={codebase_type!r}"
            )
            assert ep["has_class"] is False, (
                f"ImplMethodsExcluded violated: PUBLIC_API has has_class={ep['has_class']}"
            )
        # HttpRouteHasMethod
        if ep["etype"] == "HTTP_ROUTE":
            assert ep["method"] in VALID_HTTP_METHODS, (
                f"HttpRouteHasMethod violated: method={ep['method']!r}"
            )


# ============================================================================
# -- Trace-derived tests -----------------------------------------------------
# ============================================================================

# ---------------------------------------------------------------------------
# Trace 1
# web_app | skel_dotfile=T skel_is_main=F skel_has_class=T
#         | file_dotfile=T file_has_actix=F file_has_axum=T file_actix_method=GET
#         | file_axum_method=POST file_has_clap=T
# Expected final entry_points = {}
# All file checks blocked by file_dotfile=TRUE; skel blocked by skel_dotfile=TRUE
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 1: all file checks blocked by file_dotfile=TRUE, "
            "skel blocked by skel_dotfile=TRUE -> expected empty entry_points"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 2
# web_app | skel_dotfile=F skel_is_main=F skel_has_class=F
#         | file_dotfile=T file_has_actix=T file_actix_method=GET
#         | file_has_axum=T file_axum_method=POST file_has_clap=F
# Expected final entry_points = {}
# SkelCheckMain: skel_is_main=F -> skip
# SkelCheckPubAPI: codebase_type!=library -> skip
# All file checks blocked by file_dotfile=TRUE
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 2: file_dotfile=TRUE blocks all file checks; "
            "codebase_type=web_app blocks PUBLIC_API; skel_is_main=F blocks MAIN"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 3
# cli | skel_dotfile=T skel_is_main=T skel_has_class=T
#     | file_dotfile=T file_has_actix=T file_actix_method=POST
#     | file_has_axum=F file_axum_method=POST file_has_clap=F
# Expected final entry_points = {}
# skel_dotfile=TRUE blocks both skel checks
# file_dotfile=TRUE blocks all file checks
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 3: skel_dotfile=TRUE and file_dotfile=TRUE block every check"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 4
# library | skel_dotfile=T skel_is_public=F skel_is_main=F skel_has_class=F
#         | file_dotfile=T file_has_axum=T file_actix_method=POST
#         | file_axum_method=POST file_has_clap=F
# Expected final entry_points = {}
# skel_dotfile=TRUE blocks skel checks (even though codebase_type=library)
# file_dotfile=TRUE blocks all file checks
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 4: skel_dotfile=TRUE blocks PUBLIC_API even for library "
            "codebase; file_dotfile=TRUE blocks all file checks"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 5
# cli | skel_dotfile=F skel_is_main=T skel_has_class=T skel_is_public=T
#     | file_dotfile=T file_has_actix=T file_actix_method=POST
#     | file_has_axum=F file_axum_method=POST file_has_clap=T
# Expected final entry_points = {}
# SkelCheckMain: skel_has_class=TRUE -> guard fails
# SkelCheckPubAPI: codebase_type=cli -> skip
# file_dotfile=TRUE blocks all file checks
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 5: skel_has_class=TRUE prevents MAIN; "
            "cli codebase prevents PUBLIC_API; "
            "file_dotfile=TRUE blocks all file checks"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 6
# cli | skel_dotfile=T skel_is_main=F skel_has_class=F skel_is_public=T
#     | file_dotfile=T file_has_actix=T file_actix_method=GET
#     | file_has_axum=F file_axum_method=GET file_has_clap=T
# Expected final entry_points = {}
# skel_dotfile=TRUE blocks skel checks
# file_dotfile=TRUE blocks all file checks
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 6: skel_dotfile=TRUE and file_dotfile=TRUE block everything"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 7  <- the only trace that produces non-empty entry_points
# web_app | skel_dotfile=F skel_is_main=F skel_is_public=F skel_has_class=T
#         | file_dotfile=F file_has_actix=T file_actix_method=POST
#         | file_has_axum=T file_axum_method=GET file_has_clap=T
# Expected final entry_points =
#   {HTTP_ROUTE/POST/actix, HTTP_ROUTE/GET/axum, CLI_COMMAND/NONE/clap}
# ---------------------------------------------------------------------------

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
        assert len(eps) == 3, (
            f"Trace 7: expected 3 entry points, got {len(eps)}: {eps}"
        )

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
        assert actix_ep in eps, (
            "Trace 7: Actix POST HTTP_ROUTE entry missing"
        )

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
        assert axum_ep in eps, (
            "Trace 7: Axum GET HTTP_ROUTE entry missing"
        )

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
        assert clap_ep in eps, (
            "Trace 7: Clap CLI_COMMAND entry missing"
        )

    def test_no_main_entry(self, dag):
        eps = _run_from_dag(dag)
        assert not any(ep["etype"] == "MAIN" for ep in eps), (
            "Trace 7: skel_is_main=FALSE -> no MAIN entry expected"
        )

    def test_no_public_api_entry(self, dag):
        eps = _run_from_dag(dag)
        assert not any(ep["etype"] == "PUBLIC_API" for ep in eps), (
            "Trace 7: codebase_type=web_app -> no PUBLIC_API expected"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 8
# web_app | skel_dotfile=F skel_is_main=T skel_has_class=T skel_is_public=F
#         | file_dotfile=F file_has_actix=F file_actix_method=POST
#         | file_has_axum=F file_axum_method=POST file_has_clap=F
# Expected final entry_points = {}
# SkelCheckMain: skel_has_class=TRUE -> guard fails
# SkelCheckPubAPI: codebase_type=web_app -> skip
# No file sources present -> all file checks no-op
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 8: skel_has_class=TRUE blocks MAIN; "
            "no actix/axum/clap present -> empty entry_points"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 9
# cli | skel_dotfile=F skel_is_main=T skel_has_class=T skel_is_public=T
#     | file_dotfile=F file_has_actix=F file_actix_method=POST
#     | file_has_axum=F file_axum_method=GET file_has_clap=F
# Expected final entry_points = {}
# SkelCheckMain: skel_has_class=TRUE -> guard fails (impl fn cannot be main)
# SkelCheckPubAPI: codebase_type=cli -> skip
# No file sources -> all file checks no-op
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 9: impl-block main (skel_has_class=TRUE) must be excluded; "
            "cli codebase blocks PUBLIC_API; no file sources present"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ---------------------------------------------------------------------------
# Trace 10
# library | skel_dotfile=F skel_is_main=F skel_is_public=T skel_has_class=T
#         | file_dotfile=F file_has_actix=F file_actix_method=POST
#         | file_has_axum=F file_axum_method=GET file_has_clap=F
# Expected final entry_points = {}
# SkelCheckMain: skel_is_main=FALSE -> skip
# SkelCheckPubAPI: skel_has_class=TRUE -> guard fails (impl fn cannot be PUBLIC_API)
# No file sources -> all file checks no-op
# ---------------------------------------------------------------------------

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
        assert eps == [], (
            "Trace 10: impl-block pub fn (skel_has_class=TRUE) excluded from PUBLIC_API; "
            "no file sources present"
        )

    def test_all_invariants(self, dag):
        eps = _run_from_dag(dag)
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


# ============================================================================
# -- Per-invariant verifiers (>= 2 topologies each) --------------------------
# ============================================================================

class TestInvariantMainIsTopLevel:
    """
    TLA+ invariant MainIsTopLevel:
      every MAIN entry has is_main=True AND has_class=False.
    Topology A - fn main() not inside an impl block  -> MAIN entry produced.
    Topology B - impl-block fn named main             -> no MAIN entry (excluded).
    """

    def test_top_level_main_fields(self):
        # Topology A: valid top-level main
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
        # Topology B: main inside impl block (Trace 9 variant)
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "MAIN" for e in eps), (
            "impl-block fn cannot produce MAIN entry"
        )
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantMainNotImpl:
    """
    TLA+ invariant MainNotImpl: no MAIN entry has has_class=True.
    Topology A - top-level main (has_class=False) -> MAIN present, has_class=False.
    Topology B - dotfile fn main                  -> no MAIN (blocked by dotfile).
    """

    def test_top_level_main_no_class(self):
        dag = _build_dag(
            codebase_type="web_app",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=False,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert any(ep["etype"] == "MAIN" for ep in eps), (
            "MainNotImpl topology A: expected a MAIN entry to be present"
        )
        for ep in eps:
            if ep["etype"] == "MAIN":
                assert ep["has_class"] is False
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_dotfile_main_not_emitted(self):
        # Trace 3 variant: skel_dotfile=True, skel_is_main=True
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
    """
    TLA+ invariant PublicOnlyForLibrary:
      PUBLIC_API entries only appear when codebase_type=library.
    Topology A - library codebase, eligible pub fn -> PUBLIC_API emitted.
    Topology B - web_app codebase, same fn         -> no PUBLIC_API.
    Topology C - cli codebase, same fn             -> no PUBLIC_API.
    """

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
        assert not any(e["etype"] == "PUBLIC_API" for e in eps), (
            "PublicOnlyForLibrary: web_app must not emit PUBLIC_API"
        )
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])

    def test_cli_no_public_api(self):
        # Trace 6 topology
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=False,
            file_dotfile=True, file_has_actix=True, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=True,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps), (
            "PublicOnlyForLibrary: cli must not emit PUBLIC_API"
        )
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantImplMethodsExcluded:
    """
    TLA+ invariant ImplMethodsExcluded: no PUBLIC_API entry has has_class=True.
    Topology A - library with pub fn in impl block -> no PUBLIC_API (Trace 10).
    Topology B - library with free pub fn          -> PUBLIC_API with has_class=False.
    """

    def test_impl_pub_fn_excluded(self):
        # Trace 10 topology
        dag = _build_dag(
            codebase_type="library",
            skel_dotfile=False, skel_is_main=False,
            skel_is_public=True, skel_has_class=True,
            file_dotfile=False, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "PUBLIC_API" for e in eps), (
            "ImplMethodsExcluded: pub fn inside impl block must not become PUBLIC_API"
        )
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
    """
    TLA+ invariant DotfilesExcluded: no entry point carries is_dotfile=True.
    Topology A - file_dotfile=TRUE  -> file checks produce nothing (Traces 1-6).
    Topology B - file_dotfile=FALSE -> file checks may produce entries, none dotfile.
    """

    def test_file_dotfile_produces_no_entries(self):
        # Trace 1 topology
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
        # Trace 7 topology
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
            assert ep["is_dotfile"] is False, (
                f"DotfilesExcluded: entry has is_dotfile=True: {ep}"
            )
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])


class TestInvariantHttpRouteHasMethod:
    """
    TLA+ invariant HttpRouteHasMethod:
      every HTTP_ROUTE entry has a valid HTTP method.
    Topology A - Actix GET route   (Trace 7 variant with GET actix).
    Topology B - Axum GET + Actix POST (Trace 7).
    """

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
        # Trace 7 topology
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
    """
    TLA+ invariant ValidEntryTypes:
      every etype is in {MAIN, PUBLIC_API, HTTP_ROUTE, CLI_COMMAND}.
    Topology A - empty set (trivially true).
    Topology B - HTTP_ROUTE and CLI_COMMAND entries present; all etypes valid.
                 Note: MAIN and PUBLIC_API cannot coexist in one trace (MAIN
                 requires skel_is_main=True; PUBLIC_API requires skel_is_main=False),
                 so full four-type coverage requires separate traces.
    """

    def test_empty_entry_points_vacuously_valid(self):
        # Trace 8 topology
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
        # Trace 7 topology: produces HTTP_ROUTE (x2) + CLI_COMMAND entries
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
        # Separate topology to exercise the MAIN etype path
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
        # Separate topology to exercise the PUBLIC_API etype path
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
    """
    TLA+ invariant NoMainFromImpl: if has_class=True then etype != MAIN.
    Topology A - impl fn main (skel_has_class=True, skel_is_main=True) -> excluded.
    Topology B - top-level fn main (skel_has_class=False)              -> MAIN emitted.
    """

    def test_impl_main_not_in_entry_points(self):
        # Trace 5 / 8 variant
        dag = _build_dag(
            codebase_type="cli",
            skel_dotfile=False, skel_is_main=True,
            skel_is_public=False, skel_has_class=True,
            file_dotfile=True, file_has_actix=False, file_actix_method="GET",
            file_has_axum=False, file_axum_method="GET", file_has_clap=False,
        )
        eps = _run_from_dag(dag)
        assert not any(e["etype"] == "MAIN" for e in eps), (
            "NoMainFromImpl: skel_has_class=True must prevent any MAIN entry"
        )
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
    """
    TLA+ invariant NoPublicAPIFromImpl: if has_class=True then etype != PUBLIC_API.
    Topology A - library with impl pub fn (has_class=True) -> no PUBLIC_API (Trace 10).
    Topology B - library with free pub fn (has_class=False) -> PUBLIC_API emitted.
    """

    def test_impl_pub_fn_not_public_api(self):
        # Trace 10 topology
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
# -- Edge-case tests ---------------------------------------------------------
# ============================================================================

class TestEdgeCases:
    """
    Targeted edge-case tests derived minimally from the trace space.
    """

    def test_empty_dag_no_crashes(self):
        """An empty RegistryDag and no-source project must not raise."""
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
        """
        All three file sources present, file_dotfile=False, web_app.
        Expect exactly actix + axum HTTP_ROUTEs + clap CLI_COMMAND.
        (Derived from Trace 7.)
        """
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
        """
        Library codebase with a free pub fn AND axum routes.
        PUBLIC_API and HTTP_ROUTE entries must both appear.
        """
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
        """
        CLI codebase with fn main() (top-level) and a clap Parser struct.
        Both MAIN and CLI_COMMAND entries must appear.
        """
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
        """
        skel_dotfile=TRUE: even a valid main/public fn must be excluded.
        Derived from Trace 3 and Trace 4 - dotfile guard is the first condition.
        """
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
        """
        After building the fixture DAG, query_relevant on the project root
        must not raise and must include both child nodes (skel_fn, src_file).
        """
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
            assert "skel_fn" in relevant_ids, (
                "query_relevant must include skel_fn reachable from project_root"
            )
            assert "src_file" in relevant_ids, (
                "query_relevant must include src_file reachable from project_root"
            )
        assert dag.node_count == 3
        eps = _run_from_dag(dag)
        assert len(eps) == 3
        assert_all_invariants(eps, dag.test_artifacts["codebase_type"])