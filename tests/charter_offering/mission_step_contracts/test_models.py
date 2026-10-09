"""Unit tests for MissionStepContract models."""

import pytest
from pydantic import ValidationError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.missions.step_contracts import (
    DelegatesTo,
    MissionStepContract,
    MissionStepContractStep as MissionStep,
)

pytestmark = pytest.mark.fast


class TestDelegatesTo:
    def test_construction(self) -> None:
        d = DelegatesTo(kind=ArtifactKind.TACTIC, candidates=["tdd-red-green-refactor"])
        assert d.kind == ArtifactKind.TACTIC
        assert d.candidates == ["tdd-red-green-refactor"]

    def test_frozen(self) -> None:
        d = DelegatesTo(kind=ArtifactKind.DIRECTIVE, candidates=["x"])
        with pytest.raises(ValidationError):
            d.kind = ArtifactKind.TACTIC  # type: ignore[misc]

    def test_requires_at_least_one_candidate(self) -> None:
        with pytest.raises(ValidationError):
            DelegatesTo(kind=ArtifactKind.TACTIC, candidates=[])

    def test_accepts_paradigm_kind(self) -> None:
        d = DelegatesTo(kind=ArtifactKind.PARADIGM, candidates=["execution-lanes"])
        assert d.kind == ArtifactKind.PARADIGM


class TestMissionStep:
    def test_minimal_construction(self) -> None:
        step = MissionStep(id="bootstrap", description="Load context")
        assert step.id == "bootstrap"
        assert step.description == "Load context"
        assert step.command is None
        assert step.delegates_to is None
        assert step.guidance is None
        assert step.inputs == []

    def test_full_construction(self) -> None:
        step = MissionStep(
            id="workspace",
            description="Create workspace",
            command="spec-kitty implement {wp_id}",
            inputs=[
                {
                    "flag": "--profile",
                    "source": "wp.agent_profile",
                    "optional": True,
                },
            ],
            delegates_to=DelegatesTo(
                kind=ArtifactKind.PARADIGM,
                candidates=["execution-lanes", "shared-branch-ci"],
            ),
            guidance="Execution lanes own worktrees.",
        )
        assert step.command is not None
        assert step.delegates_to is not None
        assert step.delegates_to.kind == ArtifactKind.PARADIGM
        assert len(step.delegates_to.candidates) == 2
        assert step.guidance is not None
        assert len(step.inputs) == 1
        assert step.inputs[0].flag == "--profile"
        assert step.inputs[0].source == "wp.agent_profile"
        assert step.inputs[0].optional is True

    def test_inputs_require_non_empty_flag_and_source(self) -> None:
        with pytest.raises(ValidationError):
            MissionStep(
                id="bootstrap",
                description="Load context",
                inputs=[{"flag": "", "source": "wp.agent_profile"}],
            )
        with pytest.raises(ValidationError):
            MissionStep(
                id="bootstrap",
                description="Load context",
                inputs=[{"flag": "--profile", "source": ""}],
            )

    def test_unknown_step_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            MissionStep(
                id="bootstrap",
                description="Load context",
                inputz=[{"flag": "--profile", "source": "wp.agent_profile"}],  # type: ignore[call-arg]
            )

    def test_unknown_input_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            MissionStep(
                id="bootstrap",
                description="Load context",
                inputs=[
                    {
                        "flag": "--profile",
                        "source": "wp.agent_profile",
                        "optional_typo": True,
                    },
                ],
            )


class TestMissionStepContract:
    def test_minimal_construction(self, minimal_step_contract_data: dict) -> None:
        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        assert contract.id == "test-implement"
        assert contract.action == "implement"
        assert contract.mission == "software-dev"
        assert len(contract.steps) == 1

    def test_full_construction(self, full_step_contract_data: dict) -> None:
        contract = MissionStepContract.model_validate(full_step_contract_data)
        assert contract.id == "implement"
        assert contract.action == "implement"
        assert len(contract.steps) == 6

        # Check delegation wiring
        workspace_step = contract.steps[1]
        assert workspace_step.delegates_to is not None
        assert workspace_step.delegates_to.kind == ArtifactKind.PARADIGM
        assert "execution-lanes" in workspace_step.delegates_to.candidates

        # Check freeform guidance
        commit_step = contract.steps[4]
        assert commit_step.guidance is not None
        assert "conventional commit" in commit_step.guidance

        # Check command inputs are schema-owned, not silently discarded.
        bootstrap_step = contract.steps[0]
        assert [input.flag for input in bootstrap_step.inputs] == ["--profile", "--tool"]
        assert [input.source for input in bootstrap_step.inputs] == [
            "wp.agent_profile",
            "env.agent_tool",
        ]

    def test_frozen_model(self, minimal_step_contract_data: dict) -> None:
        contract = MissionStepContract.model_validate(minimal_step_contract_data)
        with pytest.raises(ValidationError):
            contract.action = "changed"  # type: ignore[misc]

    def test_requires_at_least_one_step(self) -> None:
        with pytest.raises(ValidationError):
            MissionStepContract.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "action": "implement",
                    "mission": "software-dev",
                    "steps": [],
                }
            )

    def test_missing_steps_raises(self) -> None:
        with pytest.raises(ValidationError):
            MissionStepContract.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "action": "implement",
                    "mission": "software-dev",
                }
            )

    def test_step_ids_must_be_unique(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            MissionStepContract.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "action": "implement",
                    "mission": "software-dev",
                    "steps": [
                        {"id": "step1", "description": "First"},
                        {"id": "step1", "description": "Duplicate"},
                    ],
                }
            )

    def test_schema_version_alias(self) -> None:
        contract = MissionStepContract.model_validate(
            {
                "schema_version": "1.0",
                "id": "alias-test",
                "action": "test",
                "mission": "software-dev",
                "steps": [{"id": "s1", "description": "S1"}],
            }
        )
        assert contract.schema_version == "1.0"

    def test_unknown_contract_fields_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            MissionStepContract.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "bad",
                    "action": "implement",
                    "mission": "software-dev",
                    "steps": [{"id": "s1", "description": "S1"}],
                    "inputz": [],
                }
            )

    def test_json_schema_exposes_step_inputs_and_forbids_unknown_fields(self) -> None:
        schema = MissionStepContract.model_json_schema()

        step_schema = schema["$defs"]["MissionStepContractStep"]
        assert step_schema["additionalProperties"] is False
        assert step_schema["properties"]["inputs"] == {
            "items": {"$ref": "#/$defs/MissionStepInput"},
            "title": "Inputs",
            "type": "array",
        }

        input_schema = schema["$defs"]["MissionStepInput"]
        assert input_schema["additionalProperties"] is False
        assert input_schema["required"] == ["flag", "source"]
        assert input_schema["properties"]["optional"]["default"] is False
