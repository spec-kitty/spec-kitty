"""Behavioral tests for PrimitiveExecutionContext.

Following ATDD principles: focus on behavior contracts, not implementation.
These tests verify the execution context correctly handles:
- Glossary enablement decisions (metadata precedence rules)
- Strictness resolution (step vs mission level)
- Token aliasing (backward compatibility)

The PrimitiveExecutionContext is the data carrier for mission primitives.
It flows through the glossary middleware pipeline, accumulating state
(extracted_terms, conflicts) at each stage. See:
- src/charter/offering/missions/primitives.py for data model
- src/specify_cli/glossary/attachment.py for pipeline integration
"""

from charter.offering.missions.primitives import PrimitiveExecutionContext
from glossary.strictness import Strictness
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



def _make_context(**overrides):
    """Factory for minimal valid context."""
    defaults = {
        "step_id": "step-001",
        "mission_id": "mission-001",
        "run_id": "run-001",
        "inputs": {},
        "metadata": {},
        "config": {},
    }
    defaults.update(overrides)
    return PrimitiveExecutionContext(**defaults)


class TestGlossaryEnablementContract:
    """Verify glossary enablement decision rules.

    FR-020: Glossary checks enabled by default for all mission steps.
    Step metadata has precedence over mission config (allows per-step override).
    """

    def test_enabled_by_default(self):
        """Given: no config or metadata
        When: checking if glossary enabled
        Then: returns True (safe default)
        """
        ctx = _make_context()
        assert ctx.is_glossary_enabled() is True

    def test_step_metadata_overrides_mission_config(self):
        """Given: step metadata=disabled, mission config=enabled
        When: checking if glossary enabled
        Then: step metadata wins (higher precedence)
        """
        ctx = _make_context(
            metadata={"glossary_check": "disabled"},
            config={"glossary": {"enabled": True}},
        )
        assert ctx.is_glossary_enabled() is False

    def test_bool_false_disables(self):
        """Given: YAML glossary_check: false (parses as Python False)
        When: checking if glossary enabled
        Then: returns False
        """
        ctx = _make_context(metadata={"glossary_check": False})
        assert ctx.is_glossary_enabled() is False

    def test_bool_true_enables(self):
        ctx = _make_context(metadata={"glossary_check": True})
        assert ctx.is_glossary_enabled() is True

    def test_string_disable_is_case_insensitive(self):
        ctx = _make_context(metadata={"glossary_check": "DISABLED"})
        assert ctx.is_glossary_enabled() is False

    def test_null_falls_through_to_mission_config(self):
        """Given: step metadata=null, mission config=disabled
        When: checking if glossary enabled
        Then: falls through to mission config (False)
        """
        ctx = _make_context(
            metadata={"glossary_check": None},
            config={"glossary": {"enabled": False}},
        )
        assert ctx.is_glossary_enabled() is False


class TestStrictnessResolution:
    """Verify strictness extraction from config and metadata.

    Strictness levels (from glossary.strictness):
    - OFF: No validation (development mode)
    - MEDIUM: Warn on conflicts (default production)
    - MAX: Block on unresolved conflicts (strict production)
    """

    def test_mission_strictness_extracted_from_config(self):
        """Given: config with glossary.strictness = max
        When: accessing mission_strictness property
        Then: returns Strictness.MAX
        """
        ctx = _make_context(config={"glossary": {"strictness": "max"}})
        assert ctx.mission_strictness == Strictness.MAX

    def test_step_strictness_extracted_from_metadata(self):
        """Given: metadata with glossary_check_strictness = off
        When: accessing step_strictness property
        Then: returns Strictness.OFF
        """
        ctx = _make_context(metadata={"glossary_check_strictness": "off"})
        assert ctx.step_strictness == Strictness.OFF

    def test_invalid_strictness_returns_none(self):
        """Given: invalid strictness value
        When: accessing strictness property
        Then: returns None (graceful degradation)
        """
        ctx = _make_context(config={"glossary": {"strictness": "invalid"}})
        assert ctx.mission_strictness is None

    def test_absent_levels_return_none(self):
        ctx = _make_context()
        assert ctx.mission_strictness is None
        assert ctx.step_strictness is None

    def test_both_levels_coexist(self):
        """Given: both mission and step strictness set
        When: accessing both properties
        Then: each returns its respective value independently
        """
        ctx = _make_context(
            metadata={"glossary_check_strictness": "off"},
            config={"glossary": {"strictness": "max"}},
        )
        assert ctx.mission_strictness == Strictness.MAX
        assert ctx.step_strictness == Strictness.OFF


class TestTokenAliasing:
    """Verify backward-compatible token aliasing.

    Historical context: checkpoint_token was the original field name.
    retry_token introduced later for clarity. Both maintained for
    compatibility with legacy mission configs and checkpoints.
    """

    def test_retry_token_populates_checkpoint_token(self):
        """Given: retry_token set
        When: context initialized
        Then: checkpoint_token mirrors retry_token (alias)
        """
        ctx = _make_context(retry_token="tok-123")
        assert ctx.retry_token == "tok-123"
        assert ctx.checkpoint_token == "tok-123"

    def test_checkpoint_token_populates_retry_token(self):
        """Given: checkpoint_token set
        When: context initialized
        Then: retry_token mirrors checkpoint_token (reverse alias)
        """
        ctx = _make_context(checkpoint_token="tok-456")
        assert ctx.retry_token == "tok-456"
        assert ctx.checkpoint_token == "tok-456"


class TestStepInputPopulation:
    """Verify step_input initialization from inputs."""

    def test_step_input_copies_inputs_on_init(self):
        """Given: inputs provided
        When: context initialized
        Then: step_input populated from inputs (middleware compatibility)
        """
        ctx = _make_context(inputs={"key": "value"})
        assert ctx.step_input == {"key": "value"}

    def test_empty_inputs_yields_empty_step_input(self):
        """Given: no inputs
        When: context initialized
        Then: step_input is empty dict
        """
        ctx = _make_context(inputs={})
        assert ctx.step_input == {}

    def test_mutable_defaults_are_instance_local(self):
        first = _make_context()
        second = _make_context()

        first.extracted_terms.append(object())  # type: ignore[arg-type]

        assert second.extracted_terms == []
