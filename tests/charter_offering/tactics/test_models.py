"""Unit tests for Tactic models and ReferenceType enum."""

import pytest
from pydantic import ValidationError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.tactics.models import (
    Tactic,
    TacticReference,
    TacticStep,
)
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# Alias kept for readability in test assertions
ReferenceType = ArtifactKind


class TestReferenceType:
    def test_values(self) -> None:
        assert ReferenceType.STYLEGUIDE == "styleguide"
        assert ReferenceType.TACTIC == "tactic"
        assert ReferenceType.DIRECTIVE == "directive"
        assert ReferenceType.TOOLGUIDE == "toolguide"
        assert ReferenceType.PROCEDURE == "procedure"
        assert ReferenceType.TEMPLATE == "template"


class TestTacticReference:
    def test_construction(self) -> None:
        ref = TacticReference(
            name="Test Ref",
            type=ReferenceType.DIRECTIVE,
            id="DIRECTIVE_001",
            when="Before starting",
        )
        assert ref.name == "Test Ref"
        assert ref.type == ReferenceType.DIRECTIVE
        assert ref.id == "DIRECTIVE_001"
        assert ref.when == "Before starting"

    def test_frozen(self) -> None:
        ref = TacticReference(
            name="Test", type=ReferenceType.TACTIC, id="x", when="always"
        )
        with pytest.raises(ValidationError):
            ref.name = "changed"  # type: ignore[misc]


class TestTacticStep:
    def test_minimal_construction(self) -> None:
        step = TacticStep(title="Step One")
        assert step.title == "Step One"
        assert step.description is None
        assert step.examples == []
        assert step.references == []

    def test_full_construction(self) -> None:
        ref = TacticReference(
            name="Ref", type=ReferenceType.DIRECTIVE, id="D001", when="now"
        )
        step = TacticStep(
            title="Step",
            description="A description",
            examples=["ex1", "ex2"],
            references=[ref],
        )
        assert step.description == "A description"
        assert len(step.examples) == 2
        assert len(step.references) == 1


class TestTactic:
    def test_minimal_construction(self, sample_tactic_data: dict) -> None:
        tactic = Tactic.model_validate(sample_tactic_data)
        assert tactic.id == "test-tactic"
        assert tactic.name == "Test Tactic"
        assert tactic.purpose is None
        assert len(tactic.steps) == 1
        assert tactic.references == []

    def test_enriched_construction(self, enriched_tactic_data: dict) -> None:
        tactic = Tactic.model_validate(enriched_tactic_data)
        assert tactic.purpose == "A fully enriched tactic for testing."
        assert len(tactic.steps) == 2
        assert len(tactic.steps[0].references) == 1
        assert {r.type for r in tactic.references} == {ReferenceType.STYLEGUIDE}
        assert tactic.references[0].type == ReferenceType.STYLEGUIDE

    def test_frozen_model(self, sample_tactic_data: dict) -> None:
        tactic = Tactic.model_validate(sample_tactic_data)
        with pytest.raises(ValidationError):
            tactic.name = "changed"  # type: ignore[misc]

    def test_missing_steps_raises(self) -> None:
        with pytest.raises(ValidationError):
            Tactic.model_validate(
                {"schema_version": "1.0", "id": "bad", "name": "Bad"}
            )

    def test_empty_steps_raises(self) -> None:
        with pytest.raises(ValidationError):
            Tactic.model_validate(
                {"schema_version": "1.0", "id": "bad", "name": "Bad", "steps": []}
            )

    def test_schema_version_alias(self) -> None:
        tactic = Tactic.model_validate(
            {
                "schema_version": "1.0",
                "id": "alias-test",
                "name": "Alias Test",
                "steps": [{"title": "S1"}],
            }
        )
        assert tactic.schema_version == "1.0"
