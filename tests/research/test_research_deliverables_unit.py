"""Unit tests for research deliverables path handling."""

from __future__ import annotations

import json
from pathlib import Path



import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestGetDeliverablesPath:
    """Tests for get_deliverables_path function."""

    def test_returns_path_from_meta_json(self, tmp_path: Path) -> None:
        """Should return deliverables_path from meta.json when present."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"
        meta_file.write_text(json.dumps({
            "mission": "research",
            "deliverables_path": "docs/research/test-feature/"
        }))

        result = get_deliverables_path(feature_dir)
        assert result == "docs/research/test-feature/"

    def test_returns_default_for_research_mission_without_path(self, tmp_path: Path) -> None:
        """Should return default path for research mission if deliverables_path not set."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-market-research"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"
        meta_file.write_text(json.dumps({
            "mission_type": "research",
            "slug": "001-market-research"
        }))

        result = get_deliverables_path(feature_dir)
        assert result == "docs/research/001-market-research/"

    def test_returns_none_for_software_dev_mission(self, tmp_path: Path) -> None:
        """Should return None for software-dev missions (no deliverables path needed)."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-feature"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"
        meta_file.write_text(json.dumps({
            "mission": "software-dev"
        }))

        result = get_deliverables_path(feature_dir)
        assert result is None

    def test_uses_mission_slug_for_default_when_provided(self, tmp_path: Path) -> None:
        """Should use provided mission_slug for default path generation."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "002-analysis"
        feature_dir.mkdir(parents=True)
        # No meta.json - should use provided slug

        result = get_deliverables_path(feature_dir, mission_slug="002-analysis")
        assert result == "docs/research/002-analysis/"

    def test_handles_missing_meta_json(self, tmp_path: Path) -> None:
        """Should handle missing meta.json gracefully."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        # No meta.json created

        result = get_deliverables_path(feature_dir)
        assert result is None

    def test_handles_invalid_json(self, tmp_path: Path) -> None:
        """Should handle invalid JSON gracefully."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"
        meta_file.write_text("{ invalid json }")

        result = get_deliverables_path(feature_dir)
        assert result is None


class TestValidateDeliverablesPath:
    """Tests for validate_deliverables_path function."""

    def test_rejects_kitty_specs_prefix(self) -> None:
        """Should reject paths starting with kitty-specs/."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("kitty-specs/001-test/research/")
        assert not is_valid
        assert "kitty-specs/" in error

    def test_rejects_just_research_at_root(self) -> None:
        """Should reject just 'research/' at root (ambiguous)."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("research/")
        assert not is_valid
        assert "ambiguous" in error.lower()

        is_valid2, error2 = validate_deliverables_path("research")
        assert not is_valid2
        assert "ambiguous" in error2.lower()

    def test_rejects_absolute_paths(self) -> None:
        """Should reject absolute paths."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("/absolute/path/to/research/")
        assert not is_valid
        assert "relative" in error.lower()

    def test_accepts_valid_docs_research_path(self) -> None:
        """Should accept valid docs/research/<feature>/ paths."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("docs/research/001-market-analysis/")
        assert is_valid
        assert error == ""

    def test_accepts_valid_research_outputs_path(self) -> None:
        """Should accept valid research-outputs/<feature>/ paths."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("research-outputs/001-analysis/")
        assert is_valid
        assert error == ""

    def test_accepts_custom_valid_path(self) -> None:
        """Should accept other valid relative paths."""

        from specify_cli.mission import validate_deliverables_path

        is_valid, error = validate_deliverables_path("output/findings/market-research/")
        assert is_valid
        assert error == ""


class TestMetaJsonDeliverablesPath:
    """Tests for meta.json storage of deliverables_path."""

    def test_meta_json_stores_deliverables_path(self, tmp_path: Path) -> None:
        """meta.json should store deliverables_path for research missions."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"

        # Write meta.json with deliverables_path
        meta_data = {
            "feature_number": "001",
            "slug": "001-test-research",
            "friendly_name": "Test Research",
            "mission": "research",
            "deliverables_path": "docs/research/test/",
            "created_at": "2025-01-25T10:00:00Z"
        }
        meta_file.write_text(json.dumps(meta_data))

        # Verify we can read it back
        result = get_deliverables_path(feature_dir)
        assert result == "docs/research/test/"

    def test_default_deliverables_path_when_missing(self, tmp_path: Path) -> None:
        """Should default to docs/research/<feature>/ when not specified for research."""

        from specify_cli.mission import get_deliverables_path

        feature_dir = tmp_path / "kitty-specs" / "018-literature-review"
        feature_dir.mkdir(parents=True)
        meta_file = feature_dir / "meta.json"

        # Write meta.json WITHOUT deliverables_path but WITH research mission
        meta_data = {
            "mission_type": "research",
            "slug": "018-literature-review"
        }
        meta_file.write_text(json.dumps(meta_data))

        result = get_deliverables_path(feature_dir)
        assert result == "docs/research/018-literature-review/"
