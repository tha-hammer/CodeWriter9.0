"""
pytest test suite for JSTSEntryPointDiscovery behavior.

Each test_trace_N / TestTraceN class directly translates one TLC-generated
trace into RegistryDag fixture construction + discoverer simulation + final-state
assertions.  assert_all_invariants verifies every TLA+ invariant at the
complete phase.  Dedicated TestInvariant* classes exercise each invariant
across ≥2 trace-derived topologies.  TestEdgeCase* covers isolated nodes,
empty DAGs, missing package.json, deduplication, and diamond patterns.
"""

from __future__ import annotations

import pytest

from registry.dag import CycleError, NodeNotFoundError, RegistryDag
from registry.types import Edge, EdgeType, Node

# ─────────────────────────────────────────────────────────────────────────────
# Constants mirroring the verified TLA+ spec
# ─────────────────────────────────────────────────────────────────────────────

NODE_MODULES_PATHS: frozenset[str] = frozenset({"node_modules/express/index.js"})
MIN_JS_PATHS: frozenset[str] = frozenset({"dist/bundle.min.js"})
DTS_PATHS: frozenset[str] = frozenset({"src/types.d.ts"})
HTTP_METHODS: frozenset[str] = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH"})
VALID_PHASES: frozenset[str] = frozenset(
    {
        "init",
        "parse_manifest",
        "scan_routes",
        "scan_cli",
        "collect_api",
        "deduplicate",
        "fallback",
        "complete",
    }
)

# PublicTopLevelSkeletons: visibility=public, has_class=False, NOT in excluded paths
PUBLIC_TOP_LEVEL_SKELETONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("src/index.js", "createApp"),
        ("src/cli.js", "runCli"),
    }
)

# Full SKELETONS set from the TLA+ spec
ALL_SKELETONS: list[dict] = [
    {
        "file_path": "src/index.js",
        "function_name": "createApp",
        "visibility": "public",
        "has_class": False,
    },
    {
        "file_path": "src/app.js",
        "function_name": "internalHelper",
        "visibility": "private",
        "has_class": False,
    },
    {
        "file_path": "src/cli.js",
        "function_name": "runCli",
        "visibility": "public",
        "has_class": False,
    },
    {
        "file_path": "node_modules/express/index.js",
        "function_name": "nmHandler",
        "visibility": "public",
        "has_class": False,
    },
    {
        "file_path": "dist/bundle.min.js",
        "function_name": "minFunc",
        "visibility": "public",
        "has_class": False,
    },
    {
        "file_path": "src/types.d.ts",
        "function_name": "MyType",
        "visibility": "public",
        "has_class": False,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _nid(file_path: str, function_name: str) -> str:
    """Canonical node ID: '<file_path>::<function_name>'."""
    return f"{file_path}::{function_name}"


def _make_project_dag(
    codebase_type: str,
    has_pkg_json: bool,
    pkg_json_valid: bool,
    has_http_routes: bool,
    has_cli_cmds: bool,
) -> RegistryDag:
    """
    Build a RegistryDag whose nodes represent the project's skeleton structure
    as inferred from a trace's Init state.
    """
    dag = RegistryDag()

    # ── Static skeleton nodes ────────────────────────────────────────────────
    for skel in ALL_SKELETONS:
        dag.add_node(
            Node.resource(
                _nid(skel["file_path"], skel["function_name"]),
                skel["function_name"],
                description=(
                    f"file={skel['file_path']} "
                    f"visibility={skel['visibility']} "
                    f"has_class={skel['has_class']}"
                ),
            )
        )

    # ── Conditionally present nodes ──────────────────────────────────────────
    if has_http_routes:
        for fn in ("getUsers", "createUser"):
            dag.add_node(
                Node.resource(
                    _nid("src/app.js", fn),
                    fn,
                    description="file=src/app.js visibility=public has_class=False",
                )
            )

    if has_pkg_json and pkg_json_valid:
        dag.add_node(
            Node.resource(
                _nid("src/cli.js", "mycli"),
                "mycli",
                description="file=src/cli.js visibility=public has_class=False bin=mycli",
            )
        )

    if has_cli_cmds:
        dag.add_node(
            Node.resource(
                _nid("src/cli.js", "build"),
                "build",
                description="file=src/cli.js visibility=public has_class=False",
            )
        )

    # ── Static import edges ──────────────────────────────────────────────────
    dag.add_edge(
        Edge(
            _nid("src/cli.js", "runCli"),
            _nid("src/index.js", "createApp"),
            EdgeType.IMPORTS,
        )
    )
    dag.add_edge(
        Edge(
            _nid("src/app.js", "internalHelper"),
            _nid("src/index.js", "createApp"),
            EdgeType.IMPORTS,
        )
    )

    # ── Conditional import edges ─────────────────────────────────────────────
    if has_http_routes:
        dag.add_edge(
            Edge(
                _nid("src/app.js", "getUsers"),
                _nid("src/index.js", "createApp"),
                EdgeType.IMPORTS,
            )
        )
        dag.add_edge(
            Edge(
                _nid("src/app.js", "createUser"),
                _nid("src/index.js", "createApp"),
                EdgeType.IMPORTS,
            )
        )

    if has_pkg_json and pkg_json_valid:
        dag.add_edge(
            Edge(
                _nid("src/cli.js", "mycli"),
                _nid("src/cli.js", "runCli"),
                EdgeType.IMPORTS,
            )
        )

    if has_cli_cmds:
        dag.add_edge(
            Edge(
                _nid("src/cli.js", "build"),
                _nid("src/cli.js", "runCli"),
                EdgeType.IMPORTS,
            )
        )

    return dag


def run_discoverer(
    codebase_type: str,
    has_pkg_json: bool,
    pkg_json_valid: bool,
    has_http_routes: bool,
    has_cli_cmds: bool,
) -> tuple[str, list[dict]]:
    """
    Simulate the TLA+ JSTSEntryPointDiscovery PlusCal algorithm.

    Returns (final_phase, sorted_list_of_entry_point_dicts).
    """
    ep_set: set[tuple[str, str, str, str, str]] = set()

    # ParseManifest
    if has_pkg_json and pkg_json_valid:
        ep_set.add(("src/cli.js", "mycli", "CLI_COMMAND", "none", "none"))

    # ScanRoutes
    if has_http_routes:
        ep_set.add(("src/app.js", "getUsers", "HTTP_ROUTE", "/users", "GET"))
        ep_set.add(("src/app.js", "createUser", "HTTP_ROUTE", "/users", "POST"))

    # ScanCLI
    if has_cli_cmds:
        ep_set.add(("src/cli.js", "build", "CLI_COMMAND", "none", "none"))

    # CollectPublicAPI
    if codebase_type == "library":
        for fp, fn in PUBLIC_TOP_LEVEL_SKELETONS:
            ep_set.add((fp, fn, "PUBLIC_API", "none", "none"))

    # Fallback
    if not ep_set and codebase_type != "library":
        for fp, fn in PUBLIC_TOP_LEVEL_SKELETONS:
            ep_set.add((fp, fn, "PUBLIC_API", "none", "none"))

    # Complete
    result: list[dict] = sorted(
        [
            {
                "file_path": fp,
                "function_name": fn,
                "entry_type": et,
                "route": route,
                "method": method,
            }
            for fp, fn, et, route, method in ep_set
        ],
        key=lambda d: (d["file_path"], d["function_name"]),
    )
    return "complete", result


def assert_all_invariants(
    phase: str,
    entry_points: list[dict],
    codebase_type: str,
    has_pkg_json: bool,
    pkg_json_valid: bool,
    has_http_routes: bool,
    has_cli_cmds: bool,
) -> None:
    """Assert every TLA+ invariant from AllInvariantsHold for the given state."""
    # ValidPhase
    assert phase in VALID_PHASES, f"ValidPhase violated: {phase!r}"

    for ep in entry_points:
        fp = ep["file_path"]
        fn = ep["function_name"]
        et = ep["entry_type"]
        method = ep["method"]

        assert fp not in NODE_MODULES_PATHS, (
            f"NodeModulesExcluded violated: {fp!r} is a node_modules path"
        )
        assert fp not in MIN_JS_PATHS, (
            f"MinJsExcluded violated: {fp!r} is a .min.js path"
        )
        assert fp not in DTS_PATHS, (
            f"DtsProducesNoEntries violated: {fp!r} is a .d.ts path"
        )
        if et == "HTTP_ROUTE":
            assert method in HTTP_METHODS, (
                f"RouteMethodUppercase violated: method={method!r} for {fp}::{fn}"
            )
        assert et in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}, (
            f"AllEntryTypesValid violated: entry_type={et!r} for {fp}::{fn}"
        )
        if et == "CLI_COMMAND" and fn == "mycli":
            assert has_pkg_json and pkg_json_valid, (
                "PkgJsonCliOnlyWhenPresent violated: 'mycli' CLI_COMMAND present "
                f"but has_pkg_json={has_pkg_json}, pkg_json_valid={pkg_json_valid}"
            )

    # DeduplicatedResults
    keys = [(ep["file_path"], ep["function_name"]) for ep in entry_points]
    assert len(keys) == len(set(keys)), (
        f"DeduplicatedResults violated: duplicate keys in {keys}"
    )

    # LibraryPublicApiAtCompletion
    if phase == "complete" and codebase_type == "library":
        pub_api_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in entry_points
            if ep["entry_type"] == "PUBLIC_API"
        }
        for fp, fn in PUBLIC_TOP_LEVEL_SKELETONS:
            assert (fp, fn) in pub_api_keys, (
                f"LibraryPublicApiAtCompletion violated: library missing "
                f"PUBLIC_API for {fp}::{fn}"
            )

    # FallbackOnlyWhenNoEntries
    if (
        phase == "complete"
        and not has_http_routes
        and not has_cli_cmds
        and not (has_pkg_json and pkg_json_valid)
        and codebase_type != "library"
    ):
        pub_api_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in entry_points
            if ep["entry_type"] == "PUBLIC_API"
        }
        for fp, fn in PUBLIC_TOP_LEVEL_SKELETONS:
            assert (fp, fn) in pub_api_keys, (
                f"FallbackOnlyWhenNoEntries violated: fallback should have "
                f"produced PUBLIC_API for {fp}::{fn}"
            )


def _ep_key_set(entry_points: list[dict]) -> set[tuple[str, str, str]]:
    """Return {(file_path, function_name, entry_type)} for quick set comparisons."""
    return {
        (ep["file_path"], ep["function_name"], ep["entry_type"])
        for ep in entry_points
    }


# ─────────────────────────────────────────────────────────────────────────────
# Trace 1 — cli, pkg_json=valid, has_cli_cmds=True, has_http_routes=False
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace1CliValidPkgJsonWithCliCmds:
    """Trace 1: CLI project, valid package.json, scanner finds build command."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="cli",
            has_pkg_json=True,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=True,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="cli",
            has_pkg_json=True,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=True,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_mycli_cli_command_present(self, result):
        _, eps = result
        assert any(
            ep["function_name"] == "mycli" and ep["entry_type"] == "CLI_COMMAND"
            for ep in eps
        )

    def test_build_cli_command_present(self, result):
        _, eps = result
        assert any(
            ep["function_name"] == "build" and ep["entry_type"] == "CLI_COMMAND"
            for ep in eps
        )

    def test_no_http_routes(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "HTTP_ROUTE" for ep in eps)

    def test_no_public_api(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "PUBLIC_API" for ep in eps)

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/cli.js", "mycli", "CLI_COMMAND"),
            ("src/cli.js", "build", "CLI_COMMAND"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "cli", True, True, False, True)

    def test_dag_mycli_node_is_queryable(self, dag):
        assert dag.query_relevant(_nid("src/cli.js", "mycli")) is not None

    def test_dag_build_subgraph_extractable(self, dag):
        assert dag.extract_subgraph(_nid("src/cli.js", "build")) is not None

    def test_dag_expected_node_count(self, dag):
        # 6 static skeletons + mycli + build = 8
        assert dag.node_count == len(ALL_SKELETONS) + 2


# ─────────────────────────────────────────────────────────────────────────────
# Trace 2 — library, no pkg_json, no routes, no cli_cmds
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace2LibraryNoPkgJsonPublicApi:
    """Trace 2: Library project with no package.json; CollectPublicAPI fires."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="library",
            has_pkg_json=False,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="library",
            has_pkg_json=False,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_create_app_public_api(self, result):
        _, eps = result
        assert any(
            ep["file_path"] == "src/index.js"
            and ep["function_name"] == "createApp"
            and ep["entry_type"] == "PUBLIC_API"
            for ep in eps
        )

    def test_run_cli_public_api(self, result):
        _, eps = result
        assert any(
            ep["file_path"] == "src/cli.js"
            and ep["function_name"] == "runCli"
            and ep["entry_type"] == "PUBLIC_API"
            for ep in eps
        )

    def test_no_cli_commands(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "CLI_COMMAND" for ep in eps)

    def test_no_http_routes(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "HTTP_ROUTE" for ep in eps)

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/index.js", "createApp", "PUBLIC_API"),
            ("src/cli.js", "runCli", "PUBLIC_API"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "library", False, True, False, False)

    def test_dag_create_app_node_queryable(self, dag):
        assert dag.query_relevant(_nid("src/index.js", "createApp")) is not None

    def test_dag_run_cli_node_queryable(self, dag):
        assert dag.query_relevant(_nid("src/cli.js", "runCli")) is not None

    def test_missing_pkg_json_does_not_error(self, result):
        phase, eps = result
        assert phase == "complete"
        assert isinstance(eps, list)


# ─────────────────────────────────────────────────────────────────────────────
# Trace 3 — library, pkg_json present but invalid, routes + cli_cmds
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace3LibraryInvalidPkgJsonAllDiscoveryPaths:
    """Trace 3: Library with broken package.json, routes, CLI commands, and public API."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="library",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="library",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_no_mycli_when_pkg_json_invalid(self, result):
        _, eps = result
        assert not any(ep["function_name"] == "mycli" for ep in eps)

    def test_http_routes_with_correct_methods(self, result):
        _, eps = result
        route_tuples = {
            (ep["function_name"], ep["method"], ep["route"])
            for ep in eps
            if ep["entry_type"] == "HTTP_ROUTE"
        }
        assert route_tuples == {
            ("getUsers", "GET", "/users"),
            ("createUser", "POST", "/users"),
        }

    def test_build_cli_command_present(self, result):
        _, eps = result
        assert any(
            ep["function_name"] == "build" and ep["entry_type"] == "CLI_COMMAND"
            for ep in eps
        )

    def test_all_public_top_level_skeletons_as_public_api(self, result):
        _, eps = result
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert pub_keys == PUBLIC_TOP_LEVEL_SKELETONS

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
            ("src/cli.js", "build", "CLI_COMMAND"),
            ("src/index.js", "createApp", "PUBLIC_API"),
            ("src/cli.js", "runCli", "PUBLIC_API"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "library", True, False, True, True)

    def test_dag_extract_subgraph_library_root(self, dag):
        assert dag.extract_subgraph(_nid("src/index.js", "createApp")) is not None

    def test_dag_query_route_handler(self, dag):
        assert dag.query_relevant(_nid("src/app.js", "getUsers")) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Trace 4 — event_driven, invalid pkg_json, routes + cli_cmds
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace4EventDrivenInvalidPkgRoutesAndCli:
    """Trace 4: event_driven project; no PUBLIC_API because not a library."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="event_driven",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="event_driven",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_no_public_api_for_non_library(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "PUBLIC_API" for ep in eps)

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
            ("src/cli.js", "build", "CLI_COMMAND"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "event_driven", True, False, True, True)

    def test_dag_validate_edge_diamond_pattern(self, dag):
        result = dag.validate_edge(
            _nid("src/cli.js", "build"),
            _nid("src/index.js", "createApp"),
            EdgeType.IMPORTS,
        )
        assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# Trace 5 — web_app, no pkg_json, routes + cli_cmds
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace5WebAppNoPkgJsonRoutesCli:
    """Trace 5: web_app with no package.json; pkg.json absence does not cause errors."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="web_app",
            has_pkg_json=False,
            pkg_json_valid=True,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="web_app",
            has_pkg_json=False,
            pkg_json_valid=True,
            has_http_routes=True,
            has_cli_cmds=True,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_no_mycli_without_pkg_json(self, result):
        _, eps = result
        assert not any(ep["function_name"] == "mycli" for ep in eps)

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
            ("src/cli.js", "build", "CLI_COMMAND"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "web_app", False, True, True, True)

    def test_dag_impact_query_on_core_node(self, dag):
        assert dag.query_impact(_nid("src/index.js", "createApp")) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Trace 6 — library, no pkg_json, no routes, no cli_cmds, invalid pkg_json
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace6LibraryAllConditionsFalse:
    """Trace 6: Library type always produces PUBLIC_API regardless of other conditions."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="library",
            has_pkg_json=False,
            pkg_json_valid=False,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="library",
            has_pkg_json=False,
            pkg_json_valid=False,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/index.js", "createApp", "PUBLIC_API"),
            ("src/cli.js", "runCli", "PUBLIC_API"),
        }

    def test_all_entries_are_public_api(self, result):
        _, eps = result
        assert all(ep["entry_type"] == "PUBLIC_API" for ep in eps)

    def test_library_ignores_missing_pkg_json(self, result):
        phase, eps = result
        assert phase == "complete"
        assert len(eps) == 2

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "library", False, False, False, False)

    def test_dag_node_count_equals_skeleton_count(self, dag):
        assert dag.node_count == len(ALL_SKELETONS)

    def test_dag_only_static_edges(self, dag):
        assert dag.edge_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Trace 7 — cli, valid pkg_json, has_cli_cmds=False
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace7CliValidPkgJsonNoCli:
    """Trace 7: Valid pkg.json emits mycli; no separate CLI scanner result."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="cli",
            has_pkg_json=True,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="cli",
            has_pkg_json=True,
            pkg_json_valid=True,
            has_http_routes=False,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {("src/cli.js", "mycli", "CLI_COMMAND")}

    def test_no_build_without_cli_cmds(self, result):
        _, eps = result
        assert not any(ep["function_name"] == "build" for ep in eps)

    def test_mycli_route_and_method_are_none(self, result):
        _, eps = result
        mycli = next(ep for ep in eps if ep["function_name"] == "mycli")
        assert mycli["route"] == "none"
        assert mycli["method"] == "none"

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "cli", True, True, False, False)

    def test_pkg_json_cli_constraint_holds(self, result):
        _, eps = result
        mycli_eps = [ep for ep in eps if ep["function_name"] == "mycli"]
        assert len(mycli_eps) == 1
        assert mycli_eps[0]["entry_type"] == "CLI_COMMAND"


# ─────────────────────────────────────────────────────────────────────────────
# Trace 8 — event_driven, invalid pkg_json, no cli_cmds, has_http_routes
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace8EventDrivenInvalidPkgNoCLIWithRoutes:
    """Trace 8: event_driven with only HTTP routes; methods must be uppercase."""

    @pytest.fixture
    def dag(self) -> RegistryDag:
        return _make_project_dag(
            codebase_type="event_driven",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=False,
        )

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="event_driven",
            has_pkg_json=True,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
        }

    def test_http_methods_are_uppercase_members(self, result):
        _, eps = result
        for ep in eps:
            if ep["entry_type"] == "HTTP_ROUTE":
                assert ep["method"] == ep["method"].upper()
                assert ep["method"] in HTTP_METHODS

    def test_get_users_route_and_method(self, result):
        _, eps = result
        get_ep = next(ep for ep in eps if ep["function_name"] == "getUsers")
        assert get_ep["method"] == "GET"
        assert get_ep["route"] == "/users"

    def test_create_user_route_and_method(self, result):
        _, eps = result
        post_ep = next(ep for ep in eps if ep["function_name"] == "createUser")
        assert post_ep["method"] == "POST"
        assert post_ep["route"] == "/users"

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "event_driven", True, False, True, False)

    def test_dag_affected_tests_for_route_node(self, dag):
        affected = dag.query_affected_tests(_nid("src/app.js", "getUsers"))
        assert isinstance(affected, list)


# ─────────────────────────────────────────────────────────────────────────────
# Trace 9 — cli, no pkg_json, no cli_cmds, has_http_routes
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace9CliNoPkgJsonHttpRoutesOnly:
    """Trace 9: CLI codebase type but only HTTP routes discovered."""

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="cli",
            has_pkg_json=False,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
        }

    def test_no_cli_commands_without_pkg_json(self, result):
        _, eps = result
        assert not any(ep["entry_type"] == "CLI_COMMAND" for ep in eps)

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "cli", False, False, True, False)


# ─────────────────────────────────────────────────────────────────────────────
# Trace 10 — web_app, no pkg_json, no cli_cmds, has_http_routes
# ─────────────────────────────────────────────────────────────────────────────


class TestTrace10WebAppNoPkgJsonHttpRoutesOnly:
    """Trace 10: web_app with no pkg.json and only HTTP routes."""

    @pytest.fixture
    def result(self) -> tuple[str, list[dict]]:
        return run_discoverer(
            codebase_type="web_app",
            has_pkg_json=False,
            pkg_json_valid=False,
            has_http_routes=True,
            has_cli_cmds=False,
        )

    def test_final_phase_is_complete(self, result):
        phase, _ = result
        assert phase == "complete"

    def test_exact_entry_point_set(self, result):
        _, eps = result
        assert _ep_key_set(eps) == {
            ("src/app.js", "getUsers", "HTTP_ROUTE"),
            ("src/app.js", "createUser", "HTTP_ROUTE"),
        }

    def test_all_invariants(self, result):
        phase, eps = result
        assert_all_invariants(phase, eps, "web_app", False, False, True, False)

    def test_cli_and_web_app_produce_identical_results_without_pkg_json(self):
        _, eps_cli = run_discoverer("cli", False, False, True, False)
        _, eps_web = run_discoverer("web_app", False, False, True, False)
        assert _ep_key_set(eps_cli) == _ep_key_set(eps_web)


# ─────────────────────────────────────────────────────────────────────────────
# Invariant verifiers
# ─────────────────────────────────────────────────────────────────────────────


class TestInvariantNodeModulesExcluded:
    """NodeModulesExcluded: no entry_point.file_path ∈ NODE_MODULES_PATHS."""

    def test_excluded_in_cli_trace1(self):
        _, eps = run_discoverer("cli", True, True, False, True)
        for ep in eps:
            assert ep["file_path"] not in NODE_MODULES_PATHS

    def test_excluded_in_library_trace6(self):
        _, eps = run_discoverer("library", False, False, False, False)
        for ep in eps:
            assert ep["file_path"] not in NODE_MODULES_PATHS

    def test_excluded_in_web_app_trace10(self):
        _, eps = run_discoverer("web_app", False, False, True, False)
        for ep in eps:
            assert ep["file_path"] not in NODE_MODULES_PATHS

    def test_node_modules_skeleton_in_dag_but_never_in_entry_points(self):
        dag = _make_project_dag("library", False, False, False, False)
        assert dag.query_relevant(_nid("node_modules/express/index.js", "nmHandler")) is not None
        _, eps = run_discoverer("library", False, False, False, False)
        assert not any(ep["file_path"] == "node_modules/express/index.js" for ep in eps)


class TestInvariantMinJsExcluded:
    """MinJsExcluded: no entry_point.file_path ∈ MIN_JS_PATHS."""

    def test_excluded_in_event_driven_trace8(self):
        _, eps = run_discoverer("event_driven", True, False, True, False)
        for ep in eps:
            assert ep["file_path"] not in MIN_JS_PATHS

    def test_excluded_in_library_trace3(self):
        _, eps = run_discoverer("library", True, False, True, True)
        for ep in eps:
            assert ep["file_path"] not in MIN_JS_PATHS

    def test_min_js_skeleton_in_dag_but_never_in_entry_points(self):
        dag = _make_project_dag("web_app", False, False, True, False)
        assert dag.query_relevant(_nid("dist/bundle.min.js", "minFunc")) is not None
        _, eps = run_discoverer("web_app", False, False, True, False)
        assert not any(ep["file_path"] == "dist/bundle.min.js" for ep in eps)


class TestInvariantDtsProducesNoEntries:
    """DtsProducesNoEntries: no entry_point.file_path ∈ DTS_PATHS."""

    def test_excluded_in_cli_trace1(self):
        _, eps = run_discoverer("cli", True, True, False, True)
        for ep in eps:
            assert ep["file_path"] not in DTS_PATHS

    def test_excluded_in_library_trace6(self):
        _, eps = run_discoverer("library", False, False, False, False)
        for ep in eps:
            assert ep["file_path"] not in DTS_PATHS

    def test_dts_skeleton_in_dag_but_never_in_entry_points(self):
        dag = _make_project_dag("library", False, False, False, False)
        assert dag.query_relevant(_nid("src/types.d.ts", "MyType")) is not None
        _, eps = run_discoverer("library", False, False, False, False)
        assert not any(ep["file_path"] == "src/types.d.ts" for ep in eps)


class TestInvariantRouteMethodUppercase:
    """RouteMethodUppercase: HTTP_ROUTE entries carry a method ∈ HTTP_METHODS."""

    def test_get_method_is_uppercase_in_trace9(self):
        _, eps = run_discoverer("cli", False, False, True, False)
        get_eps = [ep for ep in eps if ep["function_name"] == "getUsers"]
        assert get_eps
        assert get_eps[0]["method"] == "GET"
        assert get_eps[0]["method"] in HTTP_METHODS

    def test_post_method_is_uppercase_in_trace8(self):
        _, eps = run_discoverer("event_driven", True, False, True, False)
        post_eps = [ep for ep in eps if ep["function_name"] == "createUser"]
        assert post_eps
        assert post_eps[0]["method"] == "POST"
        assert post_eps[0]["method"] in HTTP_METHODS

    def test_all_http_methods_valid_across_traces_3_and_4(self):
        for codebase_type, hp, pv, hr, hc in [
            ("library", True, False, True, True),
            ("event_driven", True, False, True, True),
        ]:
            _, eps = run_discoverer(codebase_type, hp, pv, hr, hc)
            for ep in eps:
                if ep["entry_type"] == "HTTP_ROUTE":
                    assert ep["method"] in HTTP_METHODS, (
                        f"method={ep['method']!r} not in HTTP_METHODS: {ep}"
                    )

    def test_non_route_entries_have_method_none(self):
        _, eps = run_discoverer("cli", True, True, False, True)
        assert eps, "expected non-empty entry_points for cli/valid-pkg/cli-cmds"
        for ep in eps:
            assert ep["entry_type"] == "CLI_COMMAND", (
                f"unexpected entry_type={ep['entry_type']!r} for {ep['function_name']!r}"
            )
            assert ep["method"] == "none", (
                f"CLI_COMMAND entry {ep['function_name']!r} has method={ep['method']!r}, expected 'none'"
            )


class TestInvariantDeduplicatedResults:
    """DeduplicatedResults: no two entry_points share (file_path, function_name)."""

    def test_no_duplicates_in_library_trace3(self):
        _, eps = run_discoverer("library", True, False, True, True)
        keys = [(ep["file_path"], ep["function_name"]) for ep in eps]
        assert len(keys) == len(set(keys))

    def test_no_duplicates_in_cli_trace1(self):
        _, eps = run_discoverer("cli", True, True, False, True)
        keys = [(ep["file_path"], ep["function_name"]) for ep in eps]
        assert len(keys) == len(set(keys))

    def test_idempotent_double_run_produces_same_set(self):
        _, eps1 = run_discoverer("library", True, True, True, True)
        _, eps2 = run_discoverer("library", True, True, True, True)
        assert _ep_key_set(eps1) == _ep_key_set(eps2)

    def test_cli_trace7_single_entry_has_no_duplicates(self):
        _, eps = run_discoverer("cli", True, True, False, False)
        assert len(eps) == 1


class TestInvariantAllEntryTypesValid:
    """AllEntryTypesValid: every entry_type ∈ {HTTP_ROUTE, CLI_COMMAND, PUBLIC_API}."""

    def test_valid_types_in_cli_trace1(self):
        _, eps = run_discoverer("cli", True, True, False, True)
        for ep in eps:
            assert ep["entry_type"] in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}

    def test_valid_types_in_library_trace3(self):
        _, eps = run_discoverer("library", True, False, True, True)
        for ep in eps:
            assert ep["entry_type"] in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}

    def test_valid_types_across_all_10_traces(self):
        configs = [
            ("cli", True, True, False, True),
            ("library", False, True, False, False),
            ("library", True, False, True, True),
            ("event_driven", True, False, True, True),
            ("web_app", False, True, True, True),
            ("library", False, False, False, False),
            ("cli", True, True, False, False),
            ("event_driven", True, False, True, False),
            ("cli", False, False, True, False),
            ("web_app", False, False, True, False),
        ]
        for cfg in configs:
            _, eps = run_discoverer(*cfg)
            for ep in eps:
                assert ep["entry_type"] in {"HTTP_ROUTE", "CLI_COMMAND", "PUBLIC_API"}, (
                    f"Config {cfg}: invalid entry_type={ep['entry_type']!r}"
                )


class TestInvariantLibraryPublicApiAtCompletion:
    """LibraryPublicApiAtCompletion: library at complete includes all PublicTopLevelSkeletons."""

    def test_library_trace2_satisfies_invariant(self):
        phase, eps = run_discoverer("library", False, True, False, False)
        assert phase == "complete"
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert PUBLIC_TOP_LEVEL_SKELETONS.issubset(pub_keys)

    def test_library_trace3_satisfies_invariant(self):
        phase, eps = run_discoverer("library", True, False, True, True)
        assert phase == "complete"
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert PUBLIC_TOP_LEVEL_SKELETONS.issubset(pub_keys)

    def test_library_trace6_satisfies_invariant(self):
        phase, eps = run_discoverer("library", False, False, False, False)
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert PUBLIC_TOP_LEVEL_SKELETONS.issubset(pub_keys)

    def test_non_library_does_not_require_public_api(self):
        _, eps = run_discoverer("web_app", False, False, True, False)
        assert not any(ep["entry_type"] == "PUBLIC_API" for ep in eps)


class TestInvariantPkgJsonCliOnlyWhenPresent:
    """PkgJsonCliOnlyWhenPresent: 'mycli' CLI_COMMAND ⇒ has_pkg_json ∧ pkg_json_valid."""

    def test_mycli_present_when_both_true(self):
        _, eps = run_discoverer("cli", True, True, False, False)
        assert any(
            ep["function_name"] == "mycli" and ep["entry_type"] == "CLI_COMMAND"
            for ep in eps
        )

    def test_mycli_absent_when_no_pkg_json(self):
        _, eps = run_discoverer("cli", False, True, False, False)
        assert not any(ep["function_name"] == "mycli" for ep in eps)

    def test_mycli_absent_when_pkg_json_invalid(self):
        _, eps = run_discoverer("library", True, False, True, True)
        assert not any(ep["function_name"] == "mycli" for ep in eps)

    def test_mycli_absent_when_both_false(self):
        _, eps = run_discoverer("event_driven", False, False, True, True)
        assert not any(ep["function_name"] == "mycli" for ep in eps)

    def test_mycli_constraint_holds_for_trace7(self):
        _, eps = run_discoverer("cli", True, True, False, False)
        mycli_eps = [ep for ep in eps if ep["function_name"] == "mycli"]
        assert len(mycli_eps) == 1
        assert mycli_eps[0]["entry_type"] == "CLI_COMMAND"


class TestInvariantFallbackOnlyWhenNoEntries:
    """FallbackOnlyWhenNoEntries: when no sources yield entries and not library, fallback fires."""

    def test_fallback_triggers_for_cli_no_sources(self):
        phase, eps = run_discoverer("cli", False, False, False, False)
        assert phase == "complete"
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert PUBLIC_TOP_LEVEL_SKELETONS.issubset(pub_keys)

    def test_fallback_triggers_for_web_app_no_sources(self):
        phase, eps = run_discoverer("web_app", False, False, False, False)
        pub_keys = {
            (ep["file_path"], ep["function_name"])
            for ep in eps
            if ep["entry_type"] == "PUBLIC_API"
        }
        assert PUBLIC_TOP_LEVEL_SKELETONS.issubset(pub_keys)

    def test_fallback_does_not_trigger_when_routes_present(self):
        _, eps = run_discoverer("web_app", False, False, True, False)
        assert len(eps) > 0, "expected HTTP_ROUTE entries when has_http_routes=True"
        assert all(ep["entry_type"] == "HTTP_ROUTE" for ep in eps)

    def test_fallback_does_not_trigger_for_library(self):
        _, eps = run_discoverer("library", False, False, False, False)
        assert all(ep["entry_type"] == "PUBLIC_API" for ep in eps)
        assert len(eps) == len(PUBLIC_TOP_LEVEL_SKELETONS)

    def test_fallback_invariant_via_assert_all_invariants(self):
        phase, eps = run_discoverer("event_driven", False, False, False, False)
        assert_all_invariants(phase, eps, "event_driven", False, False, False, False)


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCaseMissingPackageJson:
    """Missing package.json must not cause errors (GWT explicit requirement)."""

    def test_discoverer_completes_without_pkg_json_trace2(self):
        phase, eps = run_discoverer("library", False, True, False, False)
        assert phase == "complete"
        assert isinstance(eps, list)

    def test_discoverer_completes_without_pkg_json_trace5(self):
        phase, eps = run_discoverer("web_app", False, True, True, True)
        assert phase == "complete"
        assert isinstance(eps, list)

    def test_dag_construction_succeeds_without_pkg_json(self):
        dag = _make_project_dag("cli", False, False, False, False)
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant(_nid("src/cli.js", "mycli"))

    def test_no_mycli_node_in_dag_without_valid_pkg_json(self):
        dag = _make_project_dag("web_app", True, False, False, False)
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant(_nid("src/cli.js", "mycli"))


class TestEdgeCaseEmptyDag:
    """RegistryDag with no nodes is safe for all structural queries."""

    def test_empty_dag_node_count(self):
        assert RegistryDag().node_count == 0

    def test_empty_dag_edge_count(self):
        assert RegistryDag().edge_count == 0

    def test_query_relevant_raises_for_nonexistent_node(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant("nonexistent::function")

    def test_extract_subgraph_raises_for_nonexistent_node(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.extract_subgraph("ghost::node")

    def test_query_impact_raises_for_nonexistent_node(self):
        dag = RegistryDag()
        with pytest.raises(NodeNotFoundError):
            dag.query_impact("phantom::target")


class TestEdgeCaseIsolatedNodes:
    """A RegistryDag node with no edges is still safely queryable."""

    def test_isolated_skeleton_node_is_queryable(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("src/index.js::createApp", "createApp"))
        result = dag.query_relevant("src/index.js::createApp")
        assert result is not None

    def test_isolated_node_impact_query_does_not_raise(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("src/index.js::createApp", "createApp"))
        result = dag.query_impact("src/index.js::createApp")
        assert result is not None

    def test_all_excluded_skeletons_remain_isolated_in_project_dag(self):
        dag = _make_project_dag("library", False, False, False, False)
        for excluded_id in [
            _nid("node_modules/express/index.js", "nmHandler"),
            _nid("dist/bundle.min.js", "minFunc"),
            _nid("src/types.d.ts", "MyType"),
        ]:
            result = dag.query_relevant(excluded_id)
            assert result is not None

    def test_minimal_project_dag_has_exactly_two_static_edges(self):
        dag = _make_project_dag("library", False, False, False, False)
        assert dag.edge_count == 2


class TestEdgeCaseDiamondDependencyPattern:
    """Diamond pattern must not raise CycleError; DeduplicatedResults must still hold."""

    def _build_diamond_dag(self) -> RegistryDag:
        dag = RegistryDag()
        dag.add_node(Node.resource(_nid("src/index.js", "createApp"), "createApp"))
        dag.add_node(Node.resource(_nid("src/cli.js", "runCli"), "runCli"))
        dag.add_node(Node.resource(_nid("src/cli.js", "build"), "build"))
        dag.add_edge(Edge(_nid("src/cli.js", "runCli"), _nid("src/index.js", "createApp"), EdgeType.IMPORTS))
        dag.add_edge(Edge(_nid("src/cli.js", "build"), _nid("src/cli.js", "runCli"), EdgeType.IMPORTS))
        return dag

    def test_diamond_edge_is_valid_per_validate_edge(self):
        dag = self._build_diamond_dag()
        result = dag.validate_edge(
            _nid("src/cli.js", "build"),
            _nid("src/index.js", "createApp"),
            EdgeType.IMPORTS,
        )
        assert result is not None

    def test_adding_diamond_edge_does_not_raise(self):
        dag = self._build_diamond_dag()
        dag.add_edge(
            Edge(
                _nid("src/cli.js", "build"),
                _nid("src/index.js", "createApp"),
                EdgeType.IMPORTS,
            )
        )
        assert dag.edge_count == 3

    def test_backward_edge_raises_cycle_error(self):
        dag = RegistryDag()
        dag.add_node(Node.resource("A::f", "f"))
        dag.add_node(Node.resource("B::g", "g"))
        dag.add_edge(Edge("A::f", "B::g", EdgeType.IMPORTS))
        with pytest.raises(CycleError):
            dag.add_edge(Edge("B::g", "A::f", EdgeType.IMPORTS))

    def test_deduplication_invariant_holds_for_all_10_traces(self):
        configs = [
            ("cli", True, True, False, True),
            ("library", False, True, False, False),
            ("library", True, False, True, True),
            ("event_driven", True, False, True, True),
            ("web_app", False, True, True, True),
            ("library", False, False, False, False),
            ("cli", True, True, False, False),
            ("event_driven", True, False, True, False),
            ("cli", False, False, True, False),
            ("web_app", False, False, True, False),
        ]
        for cfg in configs:
            _, eps = run_discoverer(*cfg)
            keys = [(ep["file_path"], ep["function_name"]) for ep in eps]
            assert len(keys) == len(set(keys)), (
                f"Config {cfg}: DeduplicatedResults violated"
            )


class TestEdgeCaseAllTracesConsistency:
    """Cross-trace consistency properties derived from TLA+ AllInvariantsHold."""

    _ALL_TRACE_CONFIGS = [
        ("cli", True, True, False, True),
        ("library", False, True, False, False),
        ("library", True, False, True, True),
        ("event_driven", True, False, True, True),
        ("web_app", False, True, True, True),
        ("library", False, False, False, False),
        ("cli", True, True, False, False),
        ("event_driven", True, False, True, False),
        ("cli", False, False, True, False),
        ("web_app", False, False, True, False),
    ]

    def test_all_10_traces_final_phase_is_complete(self):
        for cfg in self._ALL_TRACE_CONFIGS:
            phase, _ = run_discoverer(*cfg)
            assert phase == "complete", f"Config {cfg}: expected complete, got {phase!r}"

    def test_all_10_traces_produce_nonempty_entry_points(self):
        for cfg in self._ALL_TRACE_CONFIGS:
            _, eps = run_discoverer(*cfg)
            assert len(eps) > 0, f"Config {cfg}: entry_points must be non-empty"

    def test_all_10_traces_pass_all_invariants(self):
        for cfg in self._ALL_TRACE_CONFIGS:
            ct, hp, pv, hr, hc = cfg
            phase, eps = run_discoverer(ct, hp, pv, hr, hc)
            assert_all_invariants(
                phase=phase,
                entry_points=eps,
                codebase_type=ct,
                has_pkg_json=hp,
                pkg_json_valid=pv,
                has_http_routes=hr,
                has_cli_cmds=hc,
            )

    def test_all_10_traces_dag_construction_does_not_raise(self):
        for cfg in self._ALL_TRACE_CONFIGS:
            ct, hp, pv, hr, hc = cfg
            dag = _make_project_dag(ct, hp, pv, hr, hc)
            assert dag.node_count >= len(ALL_SKELETONS)
            assert dag.edge_count >= 2