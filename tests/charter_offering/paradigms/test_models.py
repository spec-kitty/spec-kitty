"""Unit tests for Paradigm model."""

import pytest
from pydantic import ValidationError

from charter.offering.paradigms.models import Paradigm
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestParadigm:
    def test_minimal_construction(self, sample_paradigm_data: dict) -> None:
        paradigm = Paradigm.model_validate(sample_paradigm_data)
        assert paradigm.id == "test-first"
        assert paradigm.schema_version == "1.0"
        assert "red-green-refactor" in paradigm.summary

    def test_frozen_model(self, sample_paradigm_data: dict) -> None:
        paradigm = Paradigm.model_validate(sample_paradigm_data)
        with pytest.raises(ValidationError):
            paradigm.name = "changed"  # type: ignore[misc]

    def test_invalid_id_pattern_raises(self, sample_paradigm_data: dict) -> None:
        sample_paradigm_data["id"] = "Test_First"
        with pytest.raises(ValidationError):
            Paradigm.model_validate(sample_paradigm_data)

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            Paradigm.model_validate({"schema_version": "1.0", "id": "bad"})

