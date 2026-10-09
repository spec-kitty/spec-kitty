"""Unit tests for styleguide schema validation."""

import pytest
from pydantic import ValidationError

from charter.offering.styleguides.models import Styleguide
from charter.offering.styleguides.validation import validate_styleguide
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestValidateStyleguide:
    def test_valid_minimal_styleguide(
        self, sample_styleguide_data: dict
    ) -> None:
        errors = validate_styleguide(sample_styleguide_data)
        assert errors == []

    def test_valid_enriched_styleguide(
        self, enriched_styleguide_data: dict
    ) -> None:
        errors = validate_styleguide(enriched_styleguide_data)
        assert errors == []

    def test_missing_required_field(self) -> None:
        data = {"schema_version": "1.0", "id": "test"}
        errors = validate_styleguide(data)
        assert len(errors) > 0

    def test_invalid_scope_value(self, sample_styleguide_data: dict) -> None:
        sample_styleguide_data["scope"] = "invalid"
        errors = validate_styleguide(sample_styleguide_data)
        assert any("scope" in e for e in errors)

    def test_empty_principles_invalid(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "test",
            "title": "Test",
            "scope": "code",
            "principles": [],
        }
        errors = validate_styleguide(data)
        assert any("principles" in e for e in errors)

    def test_empty_pattern_lists_rejected_by_schema_and_model(self) -> None:
        data = {
            "schema_version": "1.0",
            "id": "test",
            "title": "Test",
            "scope": "code",
            "principles": ["Write clear code"],
            "patterns": [],
            "anti_patterns": [],
        }

        errors = validate_styleguide(data)
        assert any(error.startswith("patterns:") for error in errors)
        assert any(error.startswith("anti_patterns:") for error in errors)

        with pytest.raises(ValidationError):
            Styleguide.model_validate(data)
