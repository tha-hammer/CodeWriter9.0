"""Integration test: OneShotLoop drives the bridge spec through the full pipeline.

This is the bootstrap act — the first real use of the one-shot loop.
The loop queries context for a bridge GWT, the "LLM response" contains
the bridge PlusCal spec, and process_response compiles → verifies it with TLC.
Then the bridge runs on the verified spec to produce schema-conforming artifacts.
"""

import os
import pytest
import shutil

from registry.extractor import SchemaExtractor
from registry.one_shot_loop import OneShotLoop, LoopResult
from registry.bridge import run_bridge


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')
)

BRIDGE_SPEC_PATH = os.path.join(
    PROJECT_ROOT, 'templates', 'pluscal', 'instances', 'bridge_translator.tla'
)

# Check if Java and tla2tools are available
TLA2TOOLS = os.path.join(PROJECT_ROOT, 'tools', 'tla2tools.jar')
JAVA_AVAILABLE = shutil.which('java') is not None and os.path.exists(TLA2TOOLS)


@pytest.mark.skipif(not JAVA_AVAILABLE, reason="Java or tla2tools.jar not available")
class TestLoopDrivesBridge:
    """The one-shot loop drives bridge spec generation and verification."""

    def setup_method(self):
        schema_dir = os.path.join(PROJECT_ROOT, 'schema')
        e = SchemaExtractor(schema_dir=schema_dir, self_host=True)
        self.dag = e.extract()
        self.loop = OneShotLoop(dag=self.dag, project_root=PROJECT_ROOT)

    def test_loop_queries_bridge_gwt_context(self):
        """Step 1: Loop queries context for gwt-0008 (state var translation)."""
        bundle = self.loop.query('gwt-0008')

        # Context should include schemas, templates, and the loop itself
        assert bundle.behavior_id == 'gwt-0008'
        assert bundle.behavior is not None
        assert bundle.behavior.given == "a TLA+ spec with declared state variables"
        assert len(bundle.transitive_deps) >= 20  # rich context

    def test_loop_formats_prompt_for_bridge(self):
        """Step 2: Loop formats context into an LLM prompt."""
        self.loop.query('gwt-0008')
        prompt = self.loop.format_prompt()

        # Prompt should contain the target behavior
        assert 'gwt-0008' in prompt
        assert 'state_var_translation' in prompt or 'state variables' in prompt

        # Prompt should reference schemas and templates
        assert 'data_structure' in prompt.lower() or 'db-f8n5' in prompt
        assert 'template' in prompt.lower() or 'tpl-' in prompt

    def test_loop_processes_bridge_pluscal_spec(self):
        """Step 3: Loop processes the bridge PlusCal spec through full pipeline.

        This IS the bootstrap act: the one-shot loop receives a PlusCal spec
        (the bridge_translator spec), compiles it, runs TLC, and verifies.
        """
        self.loop.query('gwt-0008')
        self.loop.format_prompt()

        # Read the bridge PlusCal spec — this is what the "LLM" produced
        with open(BRIDGE_SPEC_PATH) as f:
            bridge_pluscal = f.read()

        # Wrap in a fenced block as if from LLM response
        llm_response = f"Here is the PlusCal spec for the bridge translator:\n\n```tla\n{bridge_pluscal}\n```\n"

        # TLC config for the bridge spec
        cfg_text = (
            "SPECIFICATION Spec\n\n"
            "CONSTANTS\n"
            "    MaxSteps = 20\n"
            "    NumVariables = 3\n"
            "    NumActions = 4\n"
            "    NumInvariants = 2\n\n"
            "INVARIANTS\n"
            "    ValidState\n"
            "    BoundedExecution\n"
            "    OutputConformsToSchema\n"
            "    TranslationOrder\n"
            "    NoPartialOutput\n"
            "    InputPreserved\n"
        )

        # module_name must match MODULE name in the spec
        status = self.loop.process_response(
            llm_response=llm_response,
            module_name="bridge_translator",
            cfg_text=cfg_text,
        )

        # The loop should PASS — the bridge spec is TLC-verified
        assert status.result == LoopResult.PASS, (
            f"Expected PASS but got {status.result}. "
            f"Error: {status.error}. "
            f"TLC result: {status.tlc_result}"
        )
        assert status.tlc_result is not None
        assert status.tlc_result.success is True
        assert status.tlc_result.states_found > 0

    def test_bridge_runs_on_loop_verified_spec(self):
        """Step 4: After loop verifies, bridge translates the verified spec.

        Full pipeline: loop verifies spec → bridge extracts artifacts.
        """
        # First, verify through the loop
        self.loop.query('gwt-0008')
        self.loop.format_prompt()

        with open(BRIDGE_SPEC_PATH) as f:
            bridge_tla = f.read()

        llm_response = f"```tla\n{bridge_tla}\n```"
        cfg_text = (
            "SPECIFICATION Spec\n\n"
            "CONSTANTS\n"
            "    MaxSteps = 20\n"
            "    NumVariables = 3\n"
            "    NumActions = 4\n"
            "    NumInvariants = 2\n\n"
            "INVARIANTS\n"
            "    ValidState\n"
            "    BoundedExecution\n"
            "    OutputConformsToSchema\n"
            "    TranslationOrder\n"
            "    NoPartialOutput\n"
            "    InputPreserved\n"
        )

        # module_name must match MODULE name in the spec
        status = self.loop.process_response(
            llm_response=llm_response,
            module_name="bridge_translator",
            cfg_text=cfg_text,
        )
        assert status.result == LoopResult.PASS

        # Now run the bridge on the verified spec
        result = run_bridge(bridge_tla)

        # Bridge should produce all 4 artifact types
        assert result.module_name == "bridge_translator"
        assert len(result.data_structures) >= 1
        assert len(result.verifiers) == len(result.parsed_spec.invariants)
        assert len(result.assertions) == len(result.parsed_spec.invariants)

        # The artifacts conform to the spec's invariants
        # (the TLC verification above proves this formally)

    def test_loop_drives_all_four_bridge_gwts(self):
        """All 4 bridge GWT behaviors can be queried through the loop."""
        for gwt_id in ('gwt-0008', 'gwt-0009', 'gwt-0010', 'gwt-0011'):
            loop = OneShotLoop(dag=self.dag, project_root=PROJECT_ROOT)
            bundle = loop.query(gwt_id)
            prompt = loop.format_prompt()

            assert bundle.behavior_id == gwt_id
            assert len(prompt) > 100
            assert len(bundle.transitive_deps) >= 10
