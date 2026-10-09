"""Unit tests for directive schema validation."""

from charter.offering.directives.validation import validate_directive
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestValidateDirective:
    def test_valid_minimal_directive(self, sample_directive_data: dict) -> None:
        errors = validate_directive(sample_directive_data)
        assert errors == []

    def test_valid_enriched_directive(self, enriched_directive_data: dict) -> None:
        errors = validate_directive(enriched_directive_data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = {"schema_version": "1.0", "id": "DIRECTIVE_001"}
        errors = validate_directive(data)
        assert len(errors) > 0

    def test_invalid_enforcement_value(self, sample_directive_data: dict) -> None:
        sample_directive_data["enforcement"] = "optional"
        errors = validate_directive(sample_directive_data)
        assert any("enforcement" in e for e in errors)

    def test_invalid_id_pattern(self, sample_directive_data: dict) -> None:
        sample_directive_data["id"] = "lowercase-id"
        errors = validate_directive(sample_directive_data)
        assert any("id" in e for e in errors)

    def test_backward_compat_minimal_still_validates(self) -> None:
        """Existing minimal directives (no enrichment fields) still pass."""
        minimal = {
            "schema_version": "1.0",
            "id": "DIRECTIVE_001",
            "title": "Test",
            "intent": "Test intent.",
            "enforcement": "required",
        }
        errors = validate_directive(minimal)
        assert errors == []

    def test_lenient_adherence_requires_explicit_allowances(self, sample_directive_data: dict) -> None:
        sample_directive_data["enforcement"] = "lenient-adherence"
        errors = validate_directive(sample_directive_data)
        assert any("explicit_allowances" in e for e in errors)

    def test_invalid_reference_type_fails(self, enriched_directive_data: dict) -> None:
        enriched_directive_data["references"] = [{"type": "unknown", "id": "whatever"}]
        errors = validate_directive(enriched_directive_data)
        assert any("references" in e for e in errors)
