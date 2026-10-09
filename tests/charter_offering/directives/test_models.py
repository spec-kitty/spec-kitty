"""Unit tests for Directive model and typed references."""

import pytest
from pydantic import ValidationError

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.directives.models import (
    _ENFORCEMENT_RANK,
    Directive,
    Enforcement,
)
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# Alias kept for readability in test assertions
DirectiveReferenceType = ArtifactKind


class TestEnforcement:
    def test_required_value(self) -> None:
        assert Enforcement.REQUIRED == "required"

    def test_lenient_adherence_value(self) -> None:
        assert Enforcement.LENIENT_ADHERENCE == "lenient-adherence"

    def test_advisory_value(self) -> None:
        assert Enforcement.ADVISORY == "advisory"

    def test_json_serialization_uses_value(self) -> None:
        """StrEnum value/JSON behavior must survive the ordering override (FR-001)."""
        import json

        assert json.dumps({"enforcement": Enforcement.LENIENT_ADHERENCE}) == (
            '{"enforcement": "lenient-adherence"}'
        )

    def test_rank_order_matches_intent(self) -> None:
        """required > lenient-adherence > advisory, per the explicit rank map."""
        assert Enforcement.REQUIRED > Enforcement.LENIENT_ADHERENCE > Enforcement.ADVISORY
        assert Enforcement.ADVISORY < Enforcement.LENIENT_ADHERENCE < Enforcement.REQUIRED
        assert Enforcement.REQUIRED >= Enforcement.REQUIRED
        assert Enforcement.ADVISORY <= Enforcement.ADVISORY

    def test_comparison_is_rank_driven_not_lexical(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC-009: comparison must consult the rank map, not `StrEnum`'s lexical compare.

        Alphabetically, "advisory" < "lenient-adherence" < "required" --
        which happens to coincide with the intended rank order today, so a
        naive test asserting only ``REQUIRED > ADVISORY`` would pass under
        EITHER a rank-driven implementation OR StrEnum's inherited lexical
        `__lt__`, proving nothing about *which* one is actually driving the
        comparison (the exact gap SC-009 exists to close: a future rename
        that breaks the alphabetical coincidence must not silently flip
        ordering).

        This test breaks that coincidence by monkeypatching the rank map so
        REQUIRED ranks BELOW ADVISORY. A rank-driven `__lt__` must honor the
        patched map and flip; a lexical `__lt__` would ignore the patch
        entirely (it never reads `_ENFORCEMENT_RANK`) and keep the
        alphabetical result -- so this test only stays green under a
        genuinely rank-driven comparator.
        """
        monkeypatch.setitem(_ENFORCEMENT_RANK, Enforcement.REQUIRED.value, -1)

        assert Enforcement.REQUIRED < Enforcement.ADVISORY
        assert Enforcement.ADVISORY > Enforcement.REQUIRED

    def test_comparison_rejects_unrelated_type(self) -> None:
        """Comparing against an unrelated type raises TypeError, not a silent result."""
        with pytest.raises(TypeError):
            _ = Enforcement.REQUIRED < 5


class TestDirectiveReferenceType:
    def test_toolguide_value(self) -> None:
        assert DirectiveReferenceType.TOOLGUIDE == "toolguide"

    def test_template_value(self) -> None:
        assert DirectiveReferenceType.TEMPLATE == "template"


class TestDirective:
    def test_minimal_construction(self, sample_directive_data: dict) -> None:
        directive = Directive.model_validate(sample_directive_data)
        assert directive.id == "DIRECTIVE_999"
        assert directive.title == "Test Directive"
        assert directive.enforcement == Enforcement.REQUIRED
        # Post-WP02: inline `tactic_refs` has been excised from the Directive
        # model; cross-artifact relationships live in src/charter/offering/graph.yaml.
        assert not hasattr(directive, "tactic_refs")
        assert directive.scope is None
        assert directive.procedures == []
        assert directive.references == []
        assert directive.integrity_rules == []
        assert directive.validation_criteria == []
        assert directive.explicit_allowances == []

    def test_enriched_construction(self, enriched_directive_data: dict) -> None:
        directive = Directive.model_validate(enriched_directive_data)
        assert directive.scope == "Applies to all test scenarios."
        assert set(directive.procedures) == {
            "Write acceptance test first",
            "Run test suite",
        }
        assert {r.id for r in directive.references} == {"git-agent-commit-signing"}
        assert directive.references[0].type == DirectiveReferenceType.TOOLGUIDE
        assert directive.references[0].id == "git-agent-commit-signing"
        assert set(directive.integrity_rules) == {"Tests must pass before merge"}
        assert set(directive.validation_criteria) == {"Coverage above 90%"}
        assert set(directive.explicit_allowances) == {
            "Documented exceptions may expand scope when they reduce implementation risk."
        }
        # Post-WP02: inline `tactic_refs` is no longer a Directive attribute.
        assert not hasattr(directive, "tactic_refs")

    def test_frozen_model(self, sample_directive_data: dict) -> None:
        directive = Directive.model_validate(sample_directive_data)
        with pytest.raises(ValidationError):
            directive.title = "changed"  # type: ignore[misc]

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            Directive.model_validate({"id": "DIRECTIVE_001", "title": "Test"})

    def test_invalid_enforcement_raises(self, sample_directive_data: dict) -> None:
        sample_directive_data["enforcement"] = "invalid"
        with pytest.raises(ValidationError):
            Directive.model_validate(sample_directive_data)

    def test_lenient_adherence_requires_explicit_allowances(self, sample_directive_data: dict) -> None:
        sample_directive_data["enforcement"] = "lenient-adherence"
        with pytest.raises(ValidationError):
            Directive.model_validate(sample_directive_data)

    def test_invalid_reference_type_raises(self, enriched_directive_data: dict) -> None:
        enriched_directive_data["references"] = [{"type": "unknown", "id": "whatever"}]
        with pytest.raises(ValidationError):
            Directive.model_validate(enriched_directive_data)
