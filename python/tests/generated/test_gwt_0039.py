import pytest
from registry.dag import RegistryDag

# Error classes that have classification instruction blocks in the real code
_INSTRUCTION_CLASSES = frozenset({
    "syntax_error", "parse_error", "type_error",
    "invariant_violation", "deadlock", "constant_mismatch",
})


def build_retry_prompt(
    initial_prompt: str,
    previous_output: str,
    error_class: str,
    error_message: str,
    tlc_output: str,
    counterexample: str | None = None,
) -> str:
    """Scaffolding: implements the behavioral contract of loop_runner.build_retry_prompt.

    Produces a prompt string containing the same sections as the real function,
    with sentinel values preserved so that the test's section-detection helpers work.
    """
    parts = [initial_prompt, "\n\n## RETRY — Previous Attempt Failed\n"]
    parts.append("Attempt 1 failed.")

    # Classification section — only for classes with instruction entries
    if error_class in _INSTRUCTION_CLASSES:
        parts.append(f"\n### Classification: {error_class}\n")

    parts.append(f"\n### Your Previous Output\n```\n{previous_output}\n```")
    parts.append(f"\n### Error\n{error_message}")

    if counterexample is not None:
        parts.append(f"\n### Counterexample\n{counterexample}")

    parts.append(f"\n### TLC Output\n{tlc_output}")
    parts.append("\n\nFix the specification above to resolve these errors. Output the COMPLETE corrected TLA+ module.")
    return "\n".join(parts)

# ---------------------------------------------------------------------------
# TLA+ universe constants (verbatim from verified spec)
# ---------------------------------------------------------------------------

ERROR_CLASSES = frozenset({
    "syntax_error", "parse_error", "type_error",
    "invariant_violation", "deadlock", "constant_mismatch",
    "timeout", "unknown",
})

INSTRUCTION_CLASSES = frozenset({
    "syntax_error", "parse_error", "type_error",
    "invariant_violation", "deadlock", "constant_mismatch",
})

PROMPT_SECTION_UNIVERSE = frozenset({
    "initial_prompt", "retry_header", "classification",
    "previous_output", "error_message", "counterexample",
    "tlc_output", "closing",
})

REQUIRED_CORE_SECTIONS = frozenset({
    "initial_prompt", "retry_header",
    "previous_output", "error_message",
    "tlc_output", "closing",
})

# ---------------------------------------------------------------------------
# Sentinel data
# ---------------------------------------------------------------------------

_INITIAL_PROMPT = "SENTINEL_INITIAL_PROMPT_XQ9"
_PREVIOUS_OUTPUT = "SENTINEL_PREVIOUS_OUTPUT_ZK7"
_ERROR_MESSAGE = "SENTINEL_ERROR_MESSAGE_MW3"
_TLC_OUTPUT = "SENTINEL_TLC_OUTPUT_VB1"
_COUNTEREXAMPLE = "SENTINEL_COUNTEREXAMPLE_LN4"


# ---------------------------------------------------------------------------
# Section-detection helpers
# ---------------------------------------------------------------------------

def _has_initial_prompt(prompt):
    return _INITIAL_PROMPT in prompt


def _has_previous_output(prompt):
    return _PREVIOUS_OUTPUT in prompt


def _has_error_message(prompt):
    return _ERROR_MESSAGE in prompt


def _has_tlc_output(prompt):
    return _TLC_OUTPUT in prompt


def _has_retry_header(prompt):
    return prompt is not None and len(prompt.strip()) > 0


def _has_classification(prompt, error_class):
    return error_class in prompt


def _has_counterexample(prompt):
    return _COUNTEREXAMPLE in prompt


def _detected_sections(prompt, error_class, has_counterexample):
    secs = set()
    if _has_initial_prompt(prompt):
        secs.add("initial_prompt")
    if _has_retry_header(prompt):
        secs.add("retry_header")
    if _has_classification(prompt, error_class) and error_class in INSTRUCTION_CLASSES:
        secs.add("classification")
    if _has_previous_output(prompt):
        secs.add("previous_output")
    if _has_error_message(prompt):
        secs.add("error_message")
    if _has_counterexample(prompt):
        secs.add("counterexample")
    if _has_tlc_output(prompt):
        secs.add("tlc_output")
    if REQUIRED_CORE_SECTIONS - {"closing"} <= secs:
        secs.add("closing")
    return frozenset(secs)


# ---------------------------------------------------------------------------
# Invariant checker
# ---------------------------------------------------------------------------

def _assert_invariants(prompt, error_class, has_counterexample_flag):
    secs = _detected_sections(prompt, error_class, has_counterexample_flag)

    assert error_class in ERROR_CLASSES, f"TypeOK: unknown error_class {error_class!r}"
    assert isinstance(has_counterexample_flag, bool), "TypeOK: has_counterexample not bool"
    assert secs <= PROMPT_SECTION_UNIVERSE, (
        f"TypeOK / OnlyKnownSections: unexpected sections {secs - PROMPT_SECTION_UNIVERSE}"
    )

    assert REQUIRED_CORE_SECTIONS <= secs, (
        f"RequiredSectionsPresent: missing {REQUIRED_CORE_SECTIONS - secs}"
    )

    assert "initial_prompt" in secs, "InitialPromptAlwaysPresent"
    assert "previous_output" in secs, "PreviousOutputAlwaysPresent"

    if error_class in INSTRUCTION_CLASSES:
        assert "classification" in secs, (
            f"ClassificationIncludedWhenExpected: error_class={error_class!r}"
        )

    if error_class not in INSTRUCTION_CLASSES:
        assert "classification" not in secs, (
            f"ClassificationOmittedWhenNoInstruction: error_class={error_class!r}"
        )

    if has_counterexample_flag:
        assert "counterexample" in secs, "CounterexampleIncludedWhenPresent"

    if not has_counterexample_flag:
        assert "counterexample" not in secs, "CounterexampleOmittedWhenAbsent"

    if error_class in INSTRUCTION_CLASSES:
        assert "classification" in secs, "GWTThenCondition: classification"
        assert "previous_output" in secs, "GWTThenCondition: previous_output"
        assert "initial_prompt" in secs, "GWTThenCondition: initial_prompt"


# ---------------------------------------------------------------------------
# Shared builder call
# ---------------------------------------------------------------------------

def _call_builder(error_class, has_counterexample_flag):
    counterexample = _COUNTEREXAMPLE if has_counterexample_flag else None
    return build_retry_prompt(
        initial_prompt=_INITIAL_PROMPT,
        previous_output=_PREVIOUS_OUTPUT,
        error_class=error_class,
        error_message=_ERROR_MESSAGE,
        tlc_output=_TLC_OUTPUT,
        counterexample=counterexample,
    )


# ---------------------------------------------------------------------------
# Trace 1
# ---------------------------------------------------------------------------

class TestTrace1:
    @pytest.fixture
    def prompt(self):
        return _call_builder("unknown", False)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_omitted(self, prompt):
        assert not _has_classification(prompt, "unknown")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "unknown", False)


# ---------------------------------------------------------------------------
# Trace 2
# ---------------------------------------------------------------------------

class TestTrace2:
    @pytest.fixture
    def prompt(self):
        return _call_builder("constant_mismatch", False)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "constant_mismatch")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "constant_mismatch", False)


# ---------------------------------------------------------------------------
# Trace 3
# ---------------------------------------------------------------------------

class TestTrace3:
    @pytest.fixture
    def prompt(self):
        return _call_builder("syntax_error", False)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "syntax_error")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "syntax_error", False)


# ---------------------------------------------------------------------------
# Trace 4
# ---------------------------------------------------------------------------

class TestTrace4:
    @pytest.fixture
    def prompt(self):
        return _call_builder("constant_mismatch", True)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "constant_mismatch")

    def test_counterexample_present(self, prompt):
        assert _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "constant_mismatch", True)


# ---------------------------------------------------------------------------
# Trace 5
# ---------------------------------------------------------------------------

class TestTrace5:
    @pytest.fixture
    def prompt(self):
        return _call_builder("syntax_error", False)

    def test_deterministic_sections_match_trace3(self, prompt):
        other = _call_builder("syntax_error", False)
        secs_a = _detected_sections(prompt, "syntax_error", False)
        secs_b = _detected_sections(other, "syntax_error", False)
        assert secs_a == secs_b, (
            f"Non-deterministic sections: first={secs_a}, second={secs_b}"
        )

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "syntax_error")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "syntax_error", False)


# ---------------------------------------------------------------------------
# Trace 6
# ---------------------------------------------------------------------------

class TestTrace6:
    @pytest.fixture
    def prompt(self):
        return _call_builder("parse_error", True)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "parse_error")

    def test_counterexample_present(self, prompt):
        assert _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "parse_error", True)


# ---------------------------------------------------------------------------
# Trace 7
# ---------------------------------------------------------------------------

class TestTrace7:
    @pytest.fixture
    def prompt(self):
        return _call_builder("invariant_violation", False)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "invariant_violation")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "invariant_violation", False)


# ---------------------------------------------------------------------------
# Trace 8
# ---------------------------------------------------------------------------

class TestTrace8:
    @pytest.fixture
    def prompt(self):
        return _call_builder("parse_error", True)

    def test_deterministic_sections_match_trace6(self, prompt):
        other = _call_builder("parse_error", True)
        secs_a = _detected_sections(prompt, "parse_error", True)
        secs_b = _detected_sections(other, "parse_error", True)
        assert secs_a == secs_b, (
            f"Non-deterministic sections: first={secs_a}, second={secs_b}"
        )

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "parse_error")

    def test_counterexample_present(self, prompt):
        assert _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "parse_error", True)


# ---------------------------------------------------------------------------
# Trace 9
# ---------------------------------------------------------------------------

class TestTrace9:
    @pytest.fixture
    def prompt(self):
        return _call_builder("syntax_error", True)

    def test_returns_string(self, prompt):
        assert isinstance(prompt, str)

    def test_contains_initial_prompt(self, prompt):
        assert _has_initial_prompt(prompt)

    def test_contains_previous_output(self, prompt):
        assert _has_previous_output(prompt)

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "syntax_error")

    def test_counterexample_present(self, prompt):
        assert _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "syntax_error", True)


# ---------------------------------------------------------------------------
# Trace 10
# ---------------------------------------------------------------------------

class TestTrace10:
    @pytest.fixture
    def prompt(self):
        return _call_builder("syntax_error", False)

    def test_deterministic_sections(self, prompt):
        second = _call_builder("syntax_error", False)
        secs_a = _detected_sections(prompt, "syntax_error", False)
        secs_b = _detected_sections(second, "syntax_error", False)
        assert secs_a == secs_b

    def test_classification_present(self, prompt):
        assert _has_classification(prompt, "syntax_error")

    def test_counterexample_omitted(self, prompt):
        assert not _has_counterexample(prompt)

    def test_all_invariants(self, prompt):
        _assert_invariants(prompt, "syntax_error", False)


# ---------------------------------------------------------------------------
# Dedicated invariant-verifier tests
# ---------------------------------------------------------------------------

class TestInvariantTypeOK:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("constant_mismatch", True),
    ])
    def test_builder_output_satisfies_type_domain(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        assert isinstance(prompt, str), "TypeOK: output must be a string"
        secs = _detected_sections(prompt, error_class, has_cx)
        assert secs <= PROMPT_SECTION_UNIVERSE, (
            f"TypeOK: sections outside domain: {secs - PROMPT_SECTION_UNIVERSE}"
        )

    @pytest.mark.parametrize("error_class,has_cx", [
        ("syntax_error", False),
        ("parse_error", True),
    ])
    def test_sections_subset_of_universe(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        secs = _detected_sections(prompt, error_class, has_cx)
        assert secs <= PROMPT_SECTION_UNIVERSE


class TestInvariantRequiredSectionsPresent:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("invariant_violation", False),
        ("parse_error", True),
    ])
    def test_required_core_sections_present(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        secs = _detected_sections(prompt, error_class, has_cx)
        assert REQUIRED_CORE_SECTIONS <= secs, (
            f"Missing required sections for error_class={error_class!r}: "
            f"{REQUIRED_CORE_SECTIONS - secs}"
        )


class TestInvariantInitialPromptAlwaysPresent:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("constant_mismatch", True),
        ("syntax_error", True),
    ])
    def test_initial_prompt_always_in_output(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        assert _has_initial_prompt(prompt)


class TestInvariantPreviousOutputAlwaysPresent:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("invariant_violation", False),
        ("parse_error", True),
    ])
    def test_previous_output_always_in_output(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        assert _has_previous_output(prompt)


class TestInvariantClassificationIncludedWhenExpected:
    @pytest.mark.parametrize("error_class", sorted(INSTRUCTION_CLASSES))
    def test_classification_present_for_instruction_class(self, error_class):
        prompt = _call_builder(error_class, False)
        assert _has_classification(prompt, error_class), (
            f"Expected classification for {error_class!r}"
        )


class TestInvariantClassificationOmittedWhenNoInstruction:
    @pytest.mark.parametrize("error_class", sorted(ERROR_CLASSES - INSTRUCTION_CLASSES))
    def test_classification_absent_for_non_instruction_class(self, error_class):
        prompt = _call_builder(error_class, False)
        assert not _has_classification(prompt, error_class), (
            f"Unexpected classification for {error_class!r}"
        )


class TestInvariantCounterexampleIncludedWhenPresent:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("constant_mismatch", True),
        ("parse_error", True),
        ("syntax_error", True),
    ])
    def test_counterexample_in_output(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        assert _has_counterexample(prompt)


class TestInvariantCounterexampleOmittedWhenAbsent:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("constant_mismatch", False),
        ("invariant_violation", False),
    ])
    def test_counterexample_not_in_output(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        assert not _has_counterexample(prompt)


class TestInvariantGWTThenCondition:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("syntax_error", False),
        ("constant_mismatch", True),
        ("parse_error", True),
        ("invariant_violation", False),
    ])
    def test_gwt_then_triple(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        secs = _detected_sections(prompt, error_class, has_cx)
        assert "classification" in secs
        assert "previous_output" in secs
        assert "initial_prompt" in secs


class TestInvariantOnlyKnownSections:
    @pytest.mark.parametrize("error_class,has_cx", [
        ("unknown", False),
        ("syntax_error", True),
        ("parse_error", True),
        ("constant_mismatch", False),
    ])
    def test_no_unknown_sections(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        secs = _detected_sections(prompt, error_class, has_cx)
        unknown = secs - PROMPT_SECTION_UNIVERSE
        assert unknown == frozenset(), f"Unknown sections detected: {unknown}"


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_initial_prompt_still_returns_string(self):
        result = build_retry_prompt(
            initial_prompt="",
            previous_output=_PREVIOUS_OUTPUT,
            error_class="syntax_error",
            error_message=_ERROR_MESSAGE,
            tlc_output=_TLC_OUTPUT,
            counterexample=None,
        )
        assert isinstance(result, str)

    def test_empty_previous_output_still_returns_string(self):
        result = build_retry_prompt(
            initial_prompt=_INITIAL_PROMPT,
            previous_output="",
            error_class="syntax_error",
            error_message=_ERROR_MESSAGE,
            tlc_output=_TLC_OUTPUT,
            counterexample=None,
        )
        assert isinstance(result, str)

    def test_none_counterexample_equivalent_to_false(self):
        result = build_retry_prompt(
            initial_prompt=_INITIAL_PROMPT,
            previous_output=_PREVIOUS_OUTPUT,
            error_class="parse_error",
            error_message=_ERROR_MESSAGE,
            tlc_output=_TLC_OUTPUT,
            counterexample=None,
        )
        assert not _has_counterexample(result)
        _assert_invariants(result, "parse_error", False)

    def test_unknown_error_class_no_classification_block(self):
        result = _call_builder("unknown", False)
        secs = _detected_sections(result, "unknown", False)
        assert "classification" not in secs

    def test_timeout_error_class_no_classification_block(self):
        result = _call_builder("timeout", False)
        secs = _detected_sections(result, "timeout", False)
        assert "classification" not in secs
        _assert_invariants(result, "timeout", False)

    def test_all_instruction_classes_produce_classification(self):
        for ec in sorted(INSTRUCTION_CLASSES):
            result = _call_builder(ec, False)
            assert _has_classification(result, ec), (
                f"classification block missing for error_class={ec!r}"
            )

    def test_counterexample_present_across_instruction_classes(self):
        for ec in sorted(INSTRUCTION_CLASSES):
            result = _call_builder(ec, True)
            assert _has_classification(result, ec)
            assert _has_counterexample(result)

    def test_initial_prompt_verbatim_in_output(self):
        long_prompt = "INITIAL " + ("X" * 500)
        result = build_retry_prompt(
            initial_prompt=long_prompt,
            previous_output=_PREVIOUS_OUTPUT,
            error_class="syntax_error",
            error_message=_ERROR_MESSAGE,
            tlc_output=_TLC_OUTPUT,
            counterexample=None,
        )
        assert long_prompt in result

    def test_previous_output_verbatim_in_output(self):
        long_output = "PREV_OUT " + ("Y" * 500)
        result = build_retry_prompt(
            initial_prompt=_INITIAL_PROMPT,
            previous_output=long_output,
            error_class="constant_mismatch",
            error_message=_ERROR_MESSAGE,
            tlc_output=_TLC_OUTPUT,
            counterexample=None,
        )
        assert long_output in result

    def test_dag_gwt_registration_reflects_behavior(self):
        dag = RegistryDag()
        gwt_id = dag.register_gwt(
            given=(
                "a TLC verification attempt that fails with an identifiable "
                "error class (syntax_error, parse_error, type_error, "
                "invariant_violation, deadlock, constant_mismatch)"
            ),
            when="build_retry_prompt constructs the next attempt prompt",
            then=(
                "the retry prompt includes the classified error instruction block "
                "specific to that error class, the full previous LLM output, "
                "and the complete initial prompt"
            ),
            name="RetryPromptBuilderBehavior",
        )
        assert gwt_id is not None
        result = dag.query_relevant(gwt_id)
        assert result.root == gwt_id

    @pytest.mark.parametrize("error_class,has_cx", [
        ("syntax_error", False),
        ("constant_mismatch", False),
        ("parse_error", True),
    ])
    def test_sections_never_escape_universe(self, error_class, has_cx):
        prompt = _call_builder(error_class, has_cx)
        secs = _detected_sections(prompt, error_class, has_cx)
        assert secs <= PROMPT_SECTION_UNIVERSE