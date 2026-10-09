"""Unit tests for paradigm schema validation."""

from charter.offering.paradigms.validation import validate_paradigm
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestValidateParadigm:
    def test_valid_minimal_paradigm(self, sample_paradigm_data: dict) -> None:
        errors = validate_paradigm(sample_paradigm_data)
        assert errors == []

    def test_valid_enriched_paradigm(self, enriched_paradigm_data: dict) -> None:
        errors = validate_paradigm(enriched_paradigm_data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = {"schema_version": "1.0", "id": "test-first"}
        errors = validate_paradigm(data)
        assert len(errors) > 0

    def test_invalid_id_pattern(self, sample_paradigm_data: dict) -> None:
        sample_paradigm_data["id"] = "Invalid_ID"
        errors = validate_paradigm(sample_paradigm_data)
        assert any("id" in e for e in errors)

