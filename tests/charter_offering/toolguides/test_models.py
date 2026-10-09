"""Unit tests for Toolguide model."""

import pytest
from pydantic import ValidationError

from charter.offering.toolguides.models import Toolguide
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestToolguide:
    def test_minimal_construction(self, sample_toolguide_data: dict) -> None:
        toolguide = Toolguide.model_validate(sample_toolguide_data)
        assert toolguide.id == "test-toolguide"
        assert toolguide.schema_version == "1.0"
        assert toolguide.commands == []

    def test_enriched_construction(self, enriched_toolguide_data: dict) -> None:
        toolguide = Toolguide.model_validate(enriched_toolguide_data)
        assert toolguide.tool == "git"
        assert set(toolguide.commands) == {"git", "spec-kitty"}

    def test_frozen_model(self, sample_toolguide_data: dict) -> None:
        toolguide = Toolguide.model_validate(sample_toolguide_data)
        with pytest.raises(ValidationError):
            toolguide.title = "changed"  # type: ignore[misc]

    def test_pack_relative_guide_path_accepted(self, sample_toolguide_data: dict) -> None:
        """Pack-relative paths like toolguides/my-tool.md must be accepted (issue #1157)."""
        sample_toolguide_data["guide_path"] = "toolguides/my-tool.md"
        toolguide = Toolguide.model_validate(sample_toolguide_data)
        assert toolguide.guide_path == "toolguides/my-tool.md"

    def test_nested_pack_relative_guide_path_accepted(self, sample_toolguide_data: dict) -> None:
        """Nested pack-relative paths must be accepted (issue #1157)."""
        sample_toolguide_data["guide_path"] = "docs/guides/my-tool.md"
        toolguide = Toolguide.model_validate(sample_toolguide_data)
        assert toolguide.guide_path == "docs/guides/my-tool.md"

    def test_absolute_guide_path_rejected(self, sample_toolguide_data: dict) -> None:
        """Absolute paths must be rejected — they can never be pack-relative."""
        sample_toolguide_data["guide_path"] = "/absolute/path.md"
        with pytest.raises(ValidationError):
            Toolguide.model_validate(sample_toolguide_data)

    def test_invalid_guide_path_pattern_raises(self, sample_toolguide_data: dict) -> None:
        sample_toolguide_data["guide_path"] = "/absolute/guide.md"
        with pytest.raises(ValidationError):
            Toolguide.model_validate(sample_toolguide_data)

    def test_invalid_schema_version_raises(self, sample_toolguide_data: dict) -> None:
        sample_toolguide_data["schema_version"] = "2.0"
        with pytest.raises(ValidationError):
            Toolguide.model_validate(sample_toolguide_data)

