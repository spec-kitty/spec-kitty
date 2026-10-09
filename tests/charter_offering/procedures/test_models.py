"""Tests for Procedure domain model."""

import pytest
from pydantic import ValidationError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.procedures.models import (
    ActorRole,
    Procedure,
    ProcedureStep,
)
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# Alias kept for readability in test assertions
ProcedureReferenceType = ArtifactKind


class TestProcedureModel:
    """Procedure Pydantic model tests."""

    def test_valid_procedure(self, sample_procedure_data: dict) -> None:
        p = Procedure.model_validate(sample_procedure_data)
        assert p.id == "curation-interview"
        assert p.name == "Doctrine Curation Interview"
        assert [s.title for s in p.steps] == [
            "Present artifact for review",
            "Record verdict",
            "Promote accepted artifacts",
        ]
        assert p.entry_condition.startswith("At least one")

    def test_enriched_procedure(self, enriched_procedure_data: dict) -> None:
        p = Procedure.model_validate(enriched_procedure_data)
        assert p.id == "mission-merge-workflow"
        assert p.steps[0].on_failure is not None
        # Post-WP02: step-level `tactic_refs` has been excised from
        # ProcedureStep; relationships live in src/charter/offering/graph.yaml.
        assert not hasattr(p.steps[0], "tactic_refs")
        assert [r.type for r in p.references] == [
            ProcedureReferenceType.DIRECTIVE,
            ProcedureReferenceType.TEMPLATE,
        ]
        assert p.references[0].type == ProcedureReferenceType.DIRECTIVE
        assert p.references[1].type == ProcedureReferenceType.TEMPLATE

    def test_step_rejects_tactic_refs(self) -> None:
        """Regression test: step-level `tactic_refs` must be rejected by
        extra="forbid" after WP02 inline-ref excision."""
        with pytest.raises(ValidationError):
            ProcedureStep.model_validate(
                {"title": "test step", "tactic_refs": ["some-tactic"]}
            )

    def test_step_actor_defaults_to_agent(self) -> None:
        step = ProcedureStep(title="test step")
        assert step.actor == ActorRole.AGENT

    def test_all_actor_roles(self) -> None:
        for role in ("human", "agent", "system"):
            step = ProcedureStep(title="test", actor=role)
            assert step.actor == role

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            Procedure.model_validate({"schema_version": "1.0", "id": "x"})

    def test_empty_steps_raises(self) -> None:
        with pytest.raises(ValidationError):
            Procedure.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "empty",
                    "name": "Empty",
                    "purpose": "Nothing",
                    "entry_condition": "Never",
                    "exit_condition": "Never",
                    "steps": [],
                }
            )

    def test_invalid_id_pattern_raises(self) -> None:
        with pytest.raises(ValidationError):
            Procedure.model_validate(
                {
                    "schema_version": "1.0",
                    "id": "UPPER_CASE",
                    "name": "Bad",
                    "purpose": "Test",
                    "entry_condition": "x",
                    "exit_condition": "x",
                    "steps": [{"title": "s"}],
                }
            )

    def test_frozen_model(self, sample_procedure_data: dict) -> None:
        p = Procedure.model_validate(sample_procedure_data)
        with pytest.raises(ValidationError):
            p.name = "changed"
