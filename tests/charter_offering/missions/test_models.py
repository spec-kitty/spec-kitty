"""Unit tests for the unified :class:`MissionStep` model (WP01, FR-011).

These tests pin the spec-required fields and validation rules of the
canonical :class:`charter.offering.missions.models.MissionStep` introduced by
mission ``charter-doctrine-mission-type-configuration-01KSWJVX``:

* The three ``step_type`` discriminant values (``agent``,
  ``human_in_loop``, ``integration``) are accepted; any other value is
  rejected.
* ``id`` must match :data:`IDENTIFIER_PATTERN` (ASCII kebab-case).
* The optional list fields (``delegates_to``, ``depends_on``) default to
  empty lists.
* Optional scalar fields (``agent_profile``, ``guidance``) can be
  ``None``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from charter.offering.missions.models import IDENTIFIER_PATTERN, MissionStep


pytestmark = pytest.mark.fast


class TestMissionStepStepType:
    """``step_type`` accepts only the three canonical discriminant values."""

    @pytest.mark.parametrize(
        "step_type",
        ["agent", "human_in_loop", "integration"],
    )
    def test_valid_step_type_accepted(self, step_type: str) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type=step_type,  # type: ignore[arg-type]
            prompt_template="prompt.md",
        )
        assert step.step_type == step_type

    @pytest.mark.parametrize(
        "step_type",
        ["agentic", "robot", "manual", "", "Agent"],
    )
    def test_invalid_step_type_rejected(self, step_type: str) -> None:
        with pytest.raises(ValidationError):
            MissionStep(
                id="specify",
                display_name="Specification",
                step_type=step_type,  # type: ignore[arg-type]
                prompt_template="prompt.md",
            )


class TestMissionStepIdValidation:
    """``id`` must match :data:`IDENTIFIER_PATTERN` (ASCII kebab-case)."""

    @pytest.mark.parametrize(
        "step_id",
        ["specify", "plan-tasks", "exec-summary", "a", "wp01-bootstrap"],
    )
    def test_valid_id_accepted(self, step_id: str) -> None:
        step = MissionStep(
            id=step_id,
            display_name="Step",
            step_type="agent",
            prompt_template="prompt.md",
        )
        assert step.id == step_id

    @pytest.mark.parametrize(
        "step_id",
        [
            "Specify",        # capitals
            "plan tasks",     # space
            "plan_tasks",     # underscore
            "1-specify",      # leading digit
            "-specify",       # leading hyphen
            "specify!",       # punctuation
            "specify/plan",   # slash
            "",               # empty
        ],
    )
    def test_invalid_id_rejected(self, step_id: str) -> None:
        with pytest.raises(ValidationError):
            MissionStep(
                id=step_id,
                display_name="Step",
                step_type="agent",
                prompt_template="prompt.md",
            )


class TestMissionStepDefaults:
    """List fields default to empty; optional scalars default to ``None``."""

    def test_delegates_to_defaults_to_empty_list(self) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type="agent",
            prompt_template="prompt.md",
        )
        assert step.delegates_to == []

    def test_depends_on_defaults_to_empty_list(self) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type="agent",
            prompt_template="prompt.md",
        )
        assert step.depends_on == []

    def test_agent_profile_optional_defaults_none(self) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type="agent",
            prompt_template="prompt.md",
        )
        assert step.agent_profile is None

    def test_guidance_optional_defaults_none(self) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type="agent",
            prompt_template="prompt.md",
        )
        assert step.guidance is None


class TestMissionStepFullConstruction:
    """Every field can be populated together."""

    def test_full_construction(self) -> None:
        step = MissionStep(
            id="implement",
            display_name="Implement Work Package",
            step_type="agent",
            prompt_template="prompts/implement.md",
            agent_profile="python-pedro",
            guidance="Use the TDD red-green-refactor cycle.",
            delegates_to=[
                "directive:030-test-and-typecheck-quality-gate",
                "tactic:tdd-red-green-refactor",
            ],
            depends_on=["plan"],
        )
        assert step.id == "implement"
        assert step.display_name == "Implement Work Package"
        assert step.step_type == "agent"
        assert step.prompt_template == "prompts/implement.md"
        assert step.agent_profile == "python-pedro"
        assert step.guidance is not None
        assert len(step.delegates_to) == 2
        assert step.depends_on == ["plan"]

    def test_model_is_frozen(self) -> None:
        step = MissionStep(
            id="specify",
            display_name="Specification",
            step_type="agent",
            prompt_template="prompt.md",
        )
        with pytest.raises(ValidationError):
            step.id = "plan"  # type: ignore[misc]

    def test_required_fields_missing_raises(self) -> None:
        with pytest.raises(ValidationError):
            MissionStep.model_validate({"id": "specify"})

    def test_human_in_loop_step_type_construction(self) -> None:
        step = MissionStep(
            id="approve",
            display_name="Operator Approval",
            step_type="human_in_loop",
            prompt_template="prompts/approve.md",
        )
        assert step.step_type == "human_in_loop"

    def test_integration_step_type_construction(self) -> None:
        step = MissionStep(
            id="deploy",
            display_name="Deploy to Staging",
            step_type="integration",
            prompt_template="prompts/deploy.md",
        )
        assert step.step_type == "integration"


class TestIdentifierPatternExport:
    """``IDENTIFIER_PATTERN`` is exported for downstream callers."""

    def test_identifier_pattern_is_kebab_case(self) -> None:
        assert IDENTIFIER_PATTERN == r"^[a-z][a-z0-9-]*$"


class TestMissionOrchestrationFamilyRetired:
    """dead-port-disposition-01M1TZVN T014b: the dead state-machine models are gone."""

    def test_models_module_no_longer_declares_the_family(self) -> None:
        import charter.offering.missions.models as models

        for name in ("MissionOrchestration", "MissionStateObject", "MissionTransition"):
            assert name not in models.__all__, name
            assert not hasattr(models, name), name

    def test_mission_is_constructible_without_orchestration(self) -> None:
        """Before T014b ``Mission`` required an ``orchestration`` nothing ever supplied."""
        from charter.offering.missions.models import Mission

        mission = Mission(schema_version="1.0", key="software-dev", name="Software Development")

        assert "orchestration" not in Mission.model_fields
        assert mission.steps == []
