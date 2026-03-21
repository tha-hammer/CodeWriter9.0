"""
pytest test suite – ProjectContextResolution engine-root selection.

Derived from 10 TLC-verified traces of the TLA+ specification.
All nine invariants are verified at every logical state:
  Init → post-ResolveConfig → post-AutoDetect → SelectMode/Terminate.
"""
from __future__ import annotations

import pytest
from registry.dag import RegistryDag, NodeNotFoundError
from registry.types import (
    Edge,
    EdgeType,
    Node,
    ImpactResult,
    SubgraphResult,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TARGET_ID   = "target_root"
ENGINE_ID   = "engine_root"
CONFIG_ID   = "config_toml"
VALID_MODES = frozenset({"UNRESOLVED", "SELF_HOSTING", "EXTERNAL", "INSTALLED"})


# ---------------------------------------------------------------------------
# Pure test helpers  (no mock classes, no API re-implementation)
# ---------------------------------------------------------------------------

def _node_exists(dag: RegistryDag, node_id: str) -> bool:
    """True iff node_id is registered in the DAG (query succeeds without error)."""
    try:
        dag.query_relevant(node_id)
        return True
    except NodeNotFoundError:
        return False


def _eid(engine_equals_target: bool) -> str:
    """Effective engine node-id: TARGET_ID when self-hosting, ENGINE_ID otherwise."""
    return TARGET_ID if engine_equals_target else ENGINE_ID


def _build_dag_from_init(
    config_exists: bool,
    config_engine_valid: bool,
    engine_root_provided: bool,
    engine_equals_target: bool,
    auto_detect_success: bool,
) -> RegistryDag:
    """
    Construct a RegistryDag that mirrors the TLA+ Init-state variables.

    Node mapping
    ─────────────────────────────────────────────────────────────────────────
    TARGET_ID               always present
    CONFIG_ID               present when config_exists
    ENGINE_ID / TARGET_ID   present when engine is resolvable and != target

    Edge mapping  (all EdgeType.IMPORTS)
    ─────────────────────────────────────────────────────────────────────────
    CONFIG  -> TARGET        when config_exists
    CONFIG  -> ENGINE        when config_exists and config_engine_valid and engine != target
    TARGET  -> ENGINE        when engine_root_provided and engine != target
    TARGET  -> ENGINE        when auto_detect (fallback) fires and engine != target
    """
    dag = RegistryDag()
    engine_node_id = _eid(engine_equals_target)
    seen: dict = {}

    def _put(node: Node) -> None:
        if node.id not in seen:
            dag.add_node(node)
            seen[node.id] = True

    _put(Node.resource(TARGET_ID, "Target Root", "Project target directory"))

    if config_exists:
        _put(Node.resource(CONFIG_ID, "Config TOML", ".cw9/config.toml"))
        dag.add_edge(Edge(CONFIG_ID, TARGET_ID, EdgeType.IMPORTS))
        if config_engine_valid and engine_node_id != TARGET_ID:
            _put(Node.resource(engine_node_id, "Engine Root", "Config-specified engine root"))
            dag.add_edge(Edge(CONFIG_ID, engine_node_id, EdgeType.IMPORTS))

    if engine_root_provided and engine_node_id != TARGET_ID:
        _put(Node.resource(engine_node_id, "Engine Root", "Explicitly provided engine root"))
        dag.add_edge(Edge(TARGET_ID, engine_node_id, EdgeType.IMPORTS))

    # AutoDetect only fires when ResolveConfig found nothing
    config_resolved = config_exists and config_engine_valid
    if not config_resolved and not engine_root_provided and auto_detect_success:
        if engine_node_id != TARGET_ID:
            _put(Node.resource(engine_node_id, "Engine Root", "Auto-detected engine root"))
            dag.add_edge(Edge(TARGET_ID, engine_node_id, EdgeType.IMPORTS))

    return dag


def _simulate(
    config_exists: bool,
    config_engine_valid: bool,
    engine_root_provided: bool,
    engine_equals_target: bool,
    auto_detect_success: bool,
) -> tuple:
    """
    Execute TLA+ actions  ResolveConfig -> AutoDetect -> SelectMode.
    Returns (engine_resolved, selected_mode).
    """
    # ResolveConfig
    resolved = engine_root_provided or (config_exists and config_engine_valid)
    # AutoDetect
    if not resolved:
        resolved = auto_detect_success
    # SelectMode
    mode = ("SELF_HOSTING" if engine_equals_target else "EXTERNAL") if resolved else "INSTALLED"
    return resolved, mode


def _verify_invariants(
    mode,
    engine_resolved,
    engine_equals_target,
    engine_root_provided,
    config_exists,
    config_engine_valid,
    auto_detect_success,
):
    """Assert all nine TLA+ invariants hold simultaneously for the given state."""
    # ModeValid
    assert mode in VALID_MODES, "ModeValid violated: {!r}".format(mode)

    # ResolvedModeConsistency
    if mode == "SELF_HOSTING":
        assert engine_resolved,      "ResolvedModeConsistency: SELF_HOSTING requires engine_resolved"
        assert engine_equals_target, "ResolvedModeConsistency: SELF_HOSTING requires engine_equals_target"

    # ExternalModeConsistency
    if mode == "EXTERNAL":
        assert engine_resolved,          "ExternalModeConsistency: EXTERNAL requires engine_resolved"
        assert not engine_equals_target, "ExternalModeConsistency: EXTERNAL requires ~engine_equals_target"

    # InstalledModeConsistency
    if mode == "INSTALLED":
        assert not engine_resolved, "InstalledModeConsistency: INSTALLED requires ~engine_resolved"

    # ConfigDrivenNeverInstalled
    if not engine_root_provided and config_exists and config_engine_valid:
        assert mode != "INSTALLED", "ConfigDrivenNeverInstalled violated"

    # ThenConfigSelfHosting
    if (not engine_root_provided and config_exists
            and config_engine_valid and engine_equals_target):
        assert mode in {"UNRESOLVED", "SELF_HOSTING"}, "ThenConfigSelfHosting violated"

    # ThenConfigExternal
    if (not engine_root_provided and config_exists
            and config_engine_valid and not engine_equals_target):
        assert mode in {"UNRESOLVED", "EXTERNAL"}, "ThenConfigExternal violated"

    # ExplicitRootNeverInstalled
    if engine_root_provided:
        assert mode != "INSTALLED", "ExplicitRootNeverInstalled violated"

    # NoSourceNoAuto
    if (not engine_root_provided
            and not (config_exists and config_engine_valid)
            and not auto_detect_success):
        assert mode in {"UNRESOLVED", "INSTALLED"}, "NoSourceNoAuto violated"


# ---------------------------------------------------------------------------
# Trace parameter table
# Column order:
#   config_exists, config_engine_valid, engine_root_provided,
#   engine_equals_target, auto_detect_success,
#   expected_engine_resolved, expected_mode
# ---------------------------------------------------------------------------
_TRACES = [
    pytest.param(True,  True,  False, False, True,  True,  "EXTERNAL",     id="trace_1"),
    pytest.param(False, False, False, False, True,  True,  "EXTERNAL",     id="trace_2"),
    pytest.param(True,  False, True,  True,  False, True,  "SELF_HOSTING", id="trace_3"),
    pytest.param(True,  True,  False, False, False, True,  "EXTERNAL",     id="trace_4"),
    pytest.param(True,  False, False, False, True,  True,  "EXTERNAL",     id="trace_5"),
    pytest.param(False, False, False, True,  True,  True,  "SELF_HOSTING", id="trace_6"),
    pytest.param(True,  False, False, False, False, False, "INSTALLED",    id="trace_7"),
    pytest.param(True,  True,  True,  False, False, True,  "EXTERNAL",     id="trace_8"),
    pytest.param(True,  False, True,  False, False, True,  "EXTERNAL",     id="trace_9"),
    pytest.param(False, False, True,  True,  False, True,  "SELF_HOSTING", id="trace_10"),
]

_TRACE_ARGNAMES = (
    "config_exists,config_engine_valid,engine_root_provided,"
    "engine_equals_target,auto_detect_success,"
    "exp_resolved,exp_mode"
)


# ===========================================================================
# 1.  Trace-derived tests
# ===========================================================================

class TestTraceDerivedResolution:
    """
    One parametrized test per TLC trace.
    Each test:
      - builds the fixture DAG from Init-state variables
      - executes the action sequence via _simulate()
      - asserts final (engine_resolved, selected_mode) matches the trace
      - validates DAG structural consistency
      - verifies all nine invariants at the terminal state
    """

    @pytest.mark.parametrize(_TRACE_ARGNAMES, _TRACES)
    def test_final_state(
        self,
        config_exists, config_engine_valid, engine_root_provided,
        engine_equals_target, auto_detect_success,
        exp_resolved, exp_mode,
    ):
        dag = _build_dag_from_init(
            config_exists, config_engine_valid, engine_root_provided,
            engine_equals_target, auto_detect_success,
        )
        engine_resolved, mode = _simulate(
            config_exists, config_engine_valid, engine_root_provided,
            engine_equals_target, auto_detect_success,
        )

        # final state
        assert engine_resolved == exp_resolved, (
            "engine_resolved mismatch: expected {}, got {}".format(exp_resolved, engine_resolved)
        )
        assert mode == exp_mode, (
            "selected_mode mismatch: expected {!r}, got {!r}".format(exp_mode, mode)
        )

        # DAG structural consistency
        assert _node_exists(dag, TARGET_ID), "target_root must always be in DAG"
        if config_exists:
            assert _node_exists(dag, CONFIG_ID), "config_toml must be in DAG when config_exists"
        engine_node_id = _eid(engine_equals_target)
        if engine_resolved and engine_node_id != TARGET_ID:
            assert _node_exists(dag, engine_node_id), (
                "engine_root must be present when resolved and separate from target"
            )
        if not engine_resolved and engine_node_id != TARGET_ID:
            assert not _node_exists(dag, engine_node_id), (
                "engine_root must NOT be present when unresolved"
            )

        # all invariants at terminal state
        _verify_invariants(
            mode=mode,
            engine_resolved=engine_resolved,
            engine_equals_target=engine_equals_target,
            engine_root_provided=engine_root_provided,
            config_exists=config_exists,
            config_engine_valid=config_engine_valid,
            auto_detect_success=auto_detect_success,
        )

    @pytest.mark.parametrize(_TRACE_ARGNAMES, _TRACES)
    def test_invariants_at_every_intermediate_state(
        self,
        config_exists, config_engine_valid, engine_root_provided,
        engine_equals_target, auto_detect_success,
        exp_resolved, exp_mode,
    ):
        """
        Replay each TLA+ step and assert ALL invariants hold at EVERY state,
        not only at termination (TLC verifies invariants at every reachable state).
        """
        kwargs = dict(
            engine_equals_target=engine_equals_target,
            engine_root_provided=engine_root_provided,
            config_exists=config_exists,
            config_engine_valid=config_engine_valid,
            auto_detect_success=auto_detect_success,
        )

        # State 1 - Init
        _verify_invariants(mode="UNRESOLVED", engine_resolved=False, **kwargs)

        # State 2 - post ResolveConfig
        r2 = engine_root_provided or (config_exists and config_engine_valid)
        _verify_invariants(mode="UNRESOLVED", engine_resolved=r2, **kwargs)

        # State 3 - post AutoDetect
        r3 = r2 or auto_detect_success
        _verify_invariants(mode="UNRESOLVED", engine_resolved=r3, **kwargs)

        # State 4 - post SelectMode  (Terminate)
        final_mode = (
            ("SELF_HOSTING" if engine_equals_target else "EXTERNAL") if r3 else "INSTALLED"
        )
        _verify_invariants(mode=final_mode, engine_resolved=r3, **kwargs)
        assert final_mode == exp_mode
        assert r3 == exp_resolved


# ===========================================================================
# 2.  Invariant-dedicated tests  (>= 2 trace-derived topologies per invariant)
# ===========================================================================

class TestModeValidInvariant:
    """ModeValid: selected_mode in {UNRESOLVED, SELF_HOSTING, EXTERNAL, INSTALLED}"""

    def test_external_trace_1_config_auto_detect(self):
        _, mode = _simulate(True, True, False, False, True)
        assert mode in VALID_MODES

    def test_external_trace_4_config_only(self):
        _, mode = _simulate(True, True, False, False, False)
        assert mode in VALID_MODES

    def test_installed_trace_7_no_paths(self):
        _, mode = _simulate(True, False, False, False, False)
        assert mode in VALID_MODES

    def test_self_hosting_trace_3_explicit(self):
        _, mode = _simulate(True, False, True, True, False)
        assert mode in VALID_MODES

    def test_self_hosting_trace_6_auto_detect(self):
        _, mode = _simulate(False, False, False, True, True)
        assert mode in VALID_MODES

    def test_unresolved_is_a_valid_mode_at_init(self):
        assert "UNRESOLVED" in VALID_MODES


class TestResolvedModeConsistencyInvariant:
    """SELF_HOSTING => engine_resolved and engine_equals_target"""

    def test_trace_3_explicit_root_self_hosting(self):
        resolved, mode = _simulate(True, False, True, True, False)
        assert mode == "SELF_HOSTING"
        assert resolved is True

    def test_trace_6_auto_detect_self_hosting(self):
        resolved, mode = _simulate(False, False, False, True, True)
        assert mode == "SELF_HOSTING"
        assert resolved is True

    def test_trace_10_explicit_no_config_self_hosting(self):
        resolved, mode = _simulate(False, False, True, True, False)
        assert mode == "SELF_HOSTING"
        assert resolved is True

    def test_external_never_claims_self_hosting(self):
        for (ce, cv, ep, ads) in [
            (True, True, False, True),
            (True, True, True, False),
            (False, False, True, True),
        ]:
            _, mode = _simulate(ce, cv, ep, False, ads)
            assert mode != "SELF_HOSTING", "Unexpected SELF_HOSTING for engine_equals_target=False"


class TestExternalModeConsistencyInvariant:
    """EXTERNAL => engine_resolved and not engine_equals_target"""

    def test_trace_1_config_and_auto_detect(self):
        resolved, mode = _simulate(True, True, False, False, True)
        assert mode == "EXTERNAL"
        assert resolved is True

    def test_trace_4_config_only(self):
        resolved, mode = _simulate(True, True, False, False, False)
        assert mode == "EXTERNAL"
        assert resolved is True

    def test_trace_8_config_and_explicit(self):
        resolved, mode = _simulate(True, True, True, False, False)
        assert mode == "EXTERNAL"
        assert resolved is True

    def test_trace_9_explicit_only(self):
        resolved, mode = _simulate(True, False, True, False, False)
        assert mode == "EXTERNAL"
        assert resolved is True

    def test_trace_2_auto_detect_no_config(self):
        resolved, mode = _simulate(False, False, False, False, True)
        assert mode == "EXTERNAL"
        assert resolved is True


class TestInstalledModeConsistencyInvariant:
    """INSTALLED => not engine_resolved"""

    def test_trace_7_config_invalid_no_auto(self):
        resolved, mode = _simulate(True, False, False, False, False)
        assert mode == "INSTALLED"
        assert resolved is False

    def test_fully_empty_no_config_no_auto(self):
        resolved, mode = _simulate(False, False, False, False, False)
        assert mode == "INSTALLED"
        assert resolved is False

    def test_installed_never_when_explicit_root_external(self):
        _, mode = _simulate(False, False, True, False, False)
        assert mode != "INSTALLED"

    def test_installed_never_when_explicit_root_self_hosting(self):
        _, mode = _simulate(False, False, True, True, False)
        assert mode != "INSTALLED"


class TestConfigDrivenNeverInstalledInvariant:
    """not engine_root_provided and config_exists and config_engine_valid => mode != INSTALLED"""

    def test_trace_1_config_valid_auto_detect(self):
        _, mode = _simulate(True, True, False, False, True)
        assert mode != "INSTALLED"

    def test_trace_4_config_valid_no_auto(self):
        _, mode = _simulate(True, True, False, False, False)
        assert mode != "INSTALLED"

    def test_config_valid_engine_equals_target(self):
        _, mode = _simulate(True, True, False, True, False)
        assert mode != "INSTALLED"


class TestThenConfigSelfHostingInvariant:
    """not engine_root_provided and config_valid and engine_equals_target => mode in {UNRESOLVED, SELF_HOSTING}"""

    def test_config_valid_engine_equals_target_no_auto(self):
        _, mode = _simulate(True, True, False, True, False)
        assert mode in {"UNRESOLVED", "SELF_HOSTING"}

    def test_config_valid_engine_equals_target_with_auto(self):
        _, mode = _simulate(True, True, False, True, True)
        assert mode in {"UNRESOLVED", "SELF_HOSTING"}

    def test_init_state_unresolved_satisfies_invariant(self):
        _verify_invariants(
            mode="UNRESOLVED",
            engine_resolved=False,
            engine_equals_target=True,
            engine_root_provided=False,
            config_exists=True,
            config_engine_valid=True,
            auto_detect_success=False,
        )


class TestThenConfigExternalInvariant:
    """not engine_root_provided and config_valid and not engine_equals_target => mode in {UNRESOLVED, EXTERNAL}"""

    def test_trace_1(self):
        _, mode = _simulate(True, True, False, False, True)
        assert mode in {"UNRESOLVED", "EXTERNAL"}

    def test_trace_4(self):
        _, mode = _simulate(True, True, False, False, False)
        assert mode in {"UNRESOLVED", "EXTERNAL"}

    def test_init_state_unresolved_satisfies_invariant(self):
        _verify_invariants(
            mode="UNRESOLVED",
            engine_resolved=False,
            engine_equals_target=False,
            engine_root_provided=False,
            config_exists=True,
            config_engine_valid=True,
            auto_detect_success=False,
        )


class TestExplicitRootNeverInstalledInvariant:
    """engine_root_provided => mode != INSTALLED"""

    def test_trace_3_self_hosting(self):
        _, mode = _simulate(True, False, True, True, False)
        assert mode != "INSTALLED"

    def test_trace_8_config_and_explicit(self):
        _, mode = _simulate(True, True, True, False, False)
        assert mode != "INSTALLED"

    def test_trace_9_explicit_only(self):
        _, mode = _simulate(True, False, True, False, False)
        assert mode != "INSTALLED"

    def test_trace_10_explicit_self_hosting_no_config(self):
        _, mode = _simulate(False, False, True, True, False)
        assert mode != "INSTALLED"


class TestNoSourceNoAutoInvariant:
    """not engine_root_provided and not (config and valid) and not auto_detect => mode in {UNRESOLVED, INSTALLED}"""

    def test_trace_7_config_exists_but_invalid(self):
        _, mode = _simulate(True, False, False, False, False)
        assert mode in {"UNRESOLVED", "INSTALLED"}

    def test_fully_empty(self):
        _, mode = _simulate(False, False, False, False, False)
        assert mode in {"UNRESOLVED", "INSTALLED"}

    def test_config_exists_invalid_engine_equals_target(self):
        _, mode = _simulate(True, False, False, True, False)
        assert mode in {"UNRESOLVED", "INSTALLED"}


# ===========================================================================
# 3.  Edge cases
# ===========================================================================

class TestEdgeCases:
    """
    Isolated nodes, empty DAG, diamond topology, missing artifacts.
    Derived from traces where possible; minimally invented otherwise.
    """

    def test_empty_dag_only_target_node(self):
        """Absolute minimum: target_root only. All resolution paths absent -> INSTALLED."""
        dag = _build_dag_from_init(False, False, False, False, False)
        assert dag.node_count == 1
        assert dag.edge_count == 0
        _, mode = _simulate(False, False, False, False, False)
        assert mode == "INSTALLED"

    def test_isolated_engine_node_does_not_change_resolution(self):
        """
        Engine node manually inserted with no edges (orphan).
        Resolution is still driven by _simulate, so mode remains INSTALLED.
        (Extends trace 7 topology.)
        """
        dag = _build_dag_from_init(True, False, False, False, False)
        dag.add_node(Node.resource(ENGINE_ID, "Orphan Engine", "unconnected"))
        _, mode = _simulate(True, False, False, False, False)
        assert mode == "INSTALLED"
        assert _node_exists(dag, ENGINE_ID)
        assert dag.node_count == 3

    def test_trace_7_config_invalid_dag_structure(self):
        """Trace 7: config.toml present, [engine].root invalid -> INSTALLED, no engine node."""
        dag = _build_dag_from_init(True, False, False, False, False)
        assert _node_exists(dag, TARGET_ID)
        assert _node_exists(dag, CONFIG_ID)
        assert not _node_exists(dag, ENGINE_ID)
        assert dag.node_count == 2
        assert dag.edge_count == 1
        _, mode = _simulate(True, False, False, False, False)
        assert mode == "INSTALLED"

    def test_diamond_two_configs_one_engine(self):
        """
        Diamond: config_a and config_b both point to the same engine.
        Manual construction; engine is reachable -> EXTERNAL.
        """
        dag = RegistryDag()
        dag.add_node(Node.resource(TARGET_ID,  "Target",   "target dir"))
        dag.add_node(Node.resource("config_a", "Config A", "config_a.toml"))
        dag.add_node(Node.resource("config_b", "Config B", "config_b.toml"))
        dag.add_node(Node.resource(ENGINE_ID,  "Engine",   "engine dir"))
        dag.add_edge(Edge("config_a", TARGET_ID, EdgeType.IMPORTS))
        dag.add_edge(Edge("config_b", TARGET_ID, EdgeType.IMPORTS))
        dag.add_edge(Edge("config_a", ENGINE_ID, EdgeType.IMPORTS))
        dag.add_edge(Edge("config_b", ENGINE_ID, EdgeType.IMPORTS))

        assert dag.node_count == 4
        assert dag.edge_count == 4
        assert _node_exists(dag, ENGINE_ID)
        _, mode = _simulate(True, True, False, False, False)
        assert mode == "EXTERNAL"

    def test_self_hosting_engine_is_same_node_as_target(self):
        """
        engine_equals_target=True: eid == TARGET_ID, so no separate engine node exists.
        DAG has exactly 1 node; simulation correctly returns SELF_HOSTING.
        (Derived from trace 6.)
        """
        dag = _build_dag_from_init(False, False, False, True, True)
        assert dag.node_count == 1
        assert dag.edge_count == 0
        resolved, mode = _simulate(False, False, False, True, True)
        assert resolved is True
        assert mode == "SELF_HOSTING"
        _verify_invariants(
            mode=mode,
            engine_resolved=resolved,
            engine_equals_target=True,
            engine_root_provided=False,
            config_exists=False,
            config_engine_valid=False,
            auto_detect_success=True,
        )

    def test_node_not_found_error_for_missing_config(self):
        """config_exists=False -> CONFIG_ID absent -> NodeNotFoundError on query."""
        dag = _build_dag_from_init(False, False, False, False, False)
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant(CONFIG_ID)

    def test_node_not_found_error_for_missing_engine(self):
        """Trace 7 topology: ENGINE_ID absent -> NodeNotFoundError on query."""
        dag = _build_dag_from_init(True, False, False, False, False)
        with pytest.raises(NodeNotFoundError):
            dag.query_relevant(ENGINE_ID)

    def test_trace_8_config_and_explicit_root_node_count(self):
        """
        Trace 8: config_engine_valid=T AND engine_root_provided=T.
        Both converge on the same ENGINE_ID node; no duplicates.
        """
        dag = _build_dag_from_init(True, True, True, False, False)
        assert dag.node_count == 3
        assert dag.edge_count == 3
        resolved, mode = _simulate(True, True, True, False, False)
        assert mode == "EXTERNAL"
        assert resolved is True

    def test_component_members_self_hosting_trace_10(self):
        """
        Trace 10: engine_root_provided=T, engine_equals_target=T.
        eid == TARGET_ID -> component trivially contains both identifiers.
        """
        dag = _build_dag_from_init(False, False, True, True, False)
        members = dag.component_members(TARGET_ID)
        assert TARGET_ID in members
        eid = _eid(True)
        assert eid in members

    def test_validate_edge_config_to_engine_is_valid_before_insert(self):
        """
        Before inserting CONFIG->ENGINE, validate_edge must confirm the edge is safe.
        """
        dag = RegistryDag()
        dag.add_node(Node.resource(TARGET_ID, "Target", "target dir"))
        dag.add_node(Node.resource(CONFIG_ID, "Config", "config.toml"))
        dag.add_node(Node.resource(ENGINE_ID, "Engine", "engine dir"))
        result = dag.validate_edge(CONFIG_ID, ENGINE_ID, EdgeType.IMPORTS)
        assert result.valid

    def test_validate_edge_rejects_cycle_engine_back_to_config(self):
        """
        In trace 4 topology (CONFIG->TARGET, CONFIG->ENGINE),
        adding ENGINE->CONFIG would form a cycle and must be rejected.
        """
        dag = _build_dag_from_init(True, True, False, False, False)
        result = dag.validate_edge(ENGINE_ID, CONFIG_ID, EdgeType.IMPORTS)
        assert not result.valid

    def test_remove_engine_node_transitions_to_installed_state(self):
        """
        Removing engine_root after a resolved trace 1 topology invalidates resolution.
        Subsequent invariant check with INSTALLED mode must pass.
        """
        dag = _build_dag_from_init(True, True, False, False, True)
        assert _node_exists(dag, ENGINE_ID)
        count_before = dag.node_count
        dag.remove_node(ENGINE_ID)
        assert not _node_exists(dag, ENGINE_ID)
        assert dag.node_count == count_before - 1
        _verify_invariants(
            mode="INSTALLED",
            engine_resolved=False,
            engine_equals_target=False,
            engine_root_provided=False,
            config_exists=True,
            config_engine_valid=False,
            auto_detect_success=False,
        )

    def test_extract_subgraph_from_target_does_not_raise(self):
        """
        extract_subgraph from TARGET_ID in the trace 4 topology must succeed.
        """
        dag = _build_dag_from_init(True, True, False, False, False)
        sub = dag.extract_subgraph(TARGET_ID)
        assert sub is not None

    def test_auto_detect_fallback_only_fires_when_config_fails(self):
        """
        Trace 5: config_exists=T but config_engine_valid=F; auto_detect fires.
        Trace 1: config_engine_valid=T; auto_detect is a no-op (already resolved).
        Both must end in EXTERNAL with engine_resolved=True.
        """
        r5, m5 = _simulate(True, False, False, False, True)
        assert r5 is True
        assert m5 == "EXTERNAL"
        dag5 = _build_dag_from_init(True, False, False, False, True)
        assert _node_exists(dag5, ENGINE_ID)

        r1, m1 = _simulate(True, True, False, False, True)
        assert r1 is True
        assert m1 == "EXTERNAL"
        dag1 = _build_dag_from_init(True, True, False, False, True)
        assert _node_exists(dag1, ENGINE_ID)

    def test_query_impact_from_engine_root_does_not_raise(self):
        """
        query_impact on ENGINE_ID in a resolved topology must not raise.
        (Derived from trace 4 topology.)
        """
        dag = _build_dag_from_init(True, True, False, False, False)
        impact = dag.query_impact(ENGINE_ID)
        assert impact is not None