"""Unit tests for toolguide schema validation."""

from charter.offering.toolguides.validation import validate_toolguide
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestValidateToolguide:
    def test_valid_minimal_toolguide(self, sample_toolguide_data: dict) -> None:
        errors = validate_toolguide(sample_toolguide_data)
        assert errors == []

    def test_valid_enriched_toolguide(self, enriched_toolguide_data: dict) -> None:
        errors = validate_toolguide(enriched_toolguide_data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = {"schema_version": "1.0", "id": "test"}
        errors = validate_toolguide(data)
        assert len(errors) > 0

    def test_pack_relative_guide_path_is_valid(self, sample_toolguide_data: dict) -> None:
        """Pack-relative guide_path must pass JSON schema validation (issue #1157)."""
        sample_toolguide_data["guide_path"] = "toolguides/my-tool.md"
        errors = validate_toolguide(sample_toolguide_data)
        assert errors == []

    def test_invalid_guide_path_pattern(self, sample_toolguide_data: dict) -> None:
        sample_toolguide_data["guide_path"] = "/absolute/guide.md"
        errors = validate_toolguide(sample_toolguide_data)
        assert any("guide_path" in e for e in errors)

