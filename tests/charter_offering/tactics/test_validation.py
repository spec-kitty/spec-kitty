"""Unit tests for tactic schema validation."""

from charter.offering.tactics.validation import validate_tactic
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestValidateTactic:
    def test_valid_minimal_tactic(self, sample_tactic_data: dict) -> None:
        errors = validate_tactic(sample_tactic_data)
        assert errors == []

    def test_valid_enriched_tactic(self, enriched_tactic_data: dict) -> None:
        errors = validate_tactic(enriched_tactic_data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = {"schema_version": "1.0", "id": "test"}
        errors = validate_tactic(data)
        assert len(errors) > 0

    def test_invalid_id_pattern(self, sample_tactic_data: dict) -> None:
        sample_tactic_data["id"] = "UPPER_CASE"
        errors = validate_tactic(sample_tactic_data)
        assert any("id" in e for e in errors)

    def test_empty_steps_invalid(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "test",
            "name": "Test",
            "steps": [],
        }
        errors = validate_tactic(data)
        assert any("steps" in e for e in errors)

    def test_backward_compat_minimal_still_validates(self) -> None:
        """Existing minimal tactics (no references) still pass."""
        minimal = {
            "schema_version": "1.0",
            "id": "simple-tactic",
            "name": "Simple",
            "steps": [{"title": "Do the thing"}],
        }
        errors = validate_tactic(minimal)
        assert errors == []
