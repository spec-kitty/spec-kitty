#!/usr/bin/env python3
"""Unit tests for mission schema validation and per-feature mission functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from specify_cli.mission import (
    Mission,
    MissionError,
    MissionNotFoundError,
    discover_missions,
    get_mission_type,
    get_mission_for_feature,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
MISSIONS_ROOT = REPO_ROOT / "src" / "specify_cli" / "missions"


def build_valid_config(**overrides: Any) -> dict[str, Any]:
    """Return a baseline valid mission configuration for testing."""
    config: dict[str, Any] = {
        "name": "Test Mission",
        "description": "Mission used for schema validation tests",
        "version": "1.0.0",
        "domain": "software",
        "workflow": {"phases": [{"name": "implement", "description": "Do the work"}]},
        "artifacts": {"required": ["spec.md"], "optional": ["plan.md"]},
        "paths": {"workspace": "src/"},
        "validation": {"checks": ["git_clean"], "custom_validators": False},
    }
    config.update(overrides)
    return config


def _write_mission(tmp_path: Path, config: dict[str, Any]) -> Path:
    """Write YAML config to temp mission directory."""
    mission_dir = tmp_path / "mission"
    mission_dir.mkdir()
    (mission_dir / "mission.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return mission_dir

def test_missing_required_field_raises_error(tmp_path: Path) -> None:
    """Missing required fields should raise MissionError with helpful message."""
    config = build_valid_config()
    config.pop("name", None)
    mission_dir = _write_mission(tmp_path, config)

    with pytest.raises(MissionError) as excinfo:
        Mission(mission_dir)

    message = str(excinfo.value)
    assert "name" in message
    assert "Field required" in message


def test_typo_field_reports_extra_input(tmp_path: Path) -> None:
    """Typos such as 'validaton' should produce extra field errors."""
    config = build_valid_config()
    config["validaton"] = {"checks": ["git_clean"]}
    mission_dir = _write_mission(tmp_path, config)

    with pytest.raises(MissionError) as excinfo:
        Mission(mission_dir)

    message = str(excinfo.value)
    assert "validaton" in message
    assert "valid root fields" in message


def test_invalid_version_type_is_reported(tmp_path: Path) -> None:
    """Wrong types (int version) should be rejected."""
    config = build_valid_config(version=1)
    mission_dir = _write_mission(tmp_path, config)

    with pytest.raises(MissionError) as excinfo:
        Mission(mission_dir)

    message = str(excinfo.value)
    assert "version" in message
    assert "valid string" in message


def test_hybrid_config_ignores_v1_compatibility_fields(tmp_path: Path) -> None:
    """Hybrid mission configs should ignore known v1 compatibility root keys."""
    config = build_valid_config()
    config.update(
        {
            "mission": "software-dev",
            "initial": "draft",
            "states": {},
            "transitions": [],
            "guards": {},
            "inputs": [],
            "outputs": [],
        }
    )
    mission_dir = _write_mission(tmp_path, config)

    mission = Mission(mission_dir)
    assert mission.name == "Test Mission"
    assert mission.domain == "software"


# =============================================================================
# Per-Feature Mission Tests (T004, T005)
# =============================================================================


@pytest.fixture
def sample_kittify_dir(tmp_path: Path) -> Path:
    """Create a sample .kittify directory with software-dev and research missions."""
    kittify_dir = tmp_path / ".kittify"
    missions_dir = kittify_dir / "missions"

    # Create software-dev mission
    software_dev = missions_dir / "software-dev"
    software_dev.mkdir(parents=True)
    software_dev_config = {
        "name": "Software Dev Kitty",
        "description": "Build software",
        "version": "1.0.0",
        "domain": "software",
        "workflow": {"phases": [{"name": "implement", "description": "Code it"}]},
        "artifacts": {"required": ["spec.md"], "optional": []},
    }
    (software_dev / "mission.yaml").write_text(yaml.safe_dump(software_dev_config))

    # Create research mission
    research = missions_dir / "research"
    research.mkdir(parents=True)
    research_config = {
        "name": "Deep Research Kitty",
        "description": "Conduct research",
        "version": "1.0.0",
        "domain": "research",
        "workflow": {"phases": [{"name": "gather", "description": "Collect data"}]},
        "artifacts": {"required": ["findings.md"], "optional": []},
    }
    (research / "mission.yaml").write_text(yaml.safe_dump(research_config))

    return kittify_dir


@pytest.fixture
def feature_with_mission(tmp_path: Path, sample_kittify_dir: Path) -> Path:
    """Create a feature directory with the canonical mission_type in meta.json."""
    feature_dir = tmp_path / "kitty-specs" / "001-test-feature"
    feature_dir.mkdir(parents=True)
    meta = {
        "feature_number": "001",
        "slug": "001-test-feature",
        "friendly_name": "Test Feature",
        # Canonical mission_type field (the legacy `mission` field was retired in
        # rc3 M5 / #3598 — readers no longer resolve it).
        "mission_type": "software-dev",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta))
    return feature_dir


@pytest.fixture
def feature_with_research_mission(tmp_path: Path, sample_kittify_dir: Path) -> Path:
    """Create a feature directory with a research mission_type in meta.json."""
    feature_dir = tmp_path / "kitty-specs" / "002-research-feature"
    feature_dir.mkdir(parents=True)
    meta = {
        "feature_number": "002",
        "slug": "002-research-feature",
        "friendly_name": "Research Feature",
        "mission_type": "research",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta))
    return feature_dir


@pytest.fixture
def legacy_feature(tmp_path: Path, sample_kittify_dir: Path) -> Path:
    """Create a feature directory WITHOUT mission field (legacy)."""
    feature_dir = tmp_path / "kitty-specs" / "000-legacy"
    feature_dir.mkdir(parents=True)
    meta = {
        "feature_number": "000",
        "slug": "000-legacy",
        "friendly_name": "Legacy Feature",
        # NO mission field - simulates pre-v0.8.0 feature
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta))
    return feature_dir


@pytest.fixture
def feature_with_invalid_mission(tmp_path: Path, sample_kittify_dir: Path) -> Path:
    """Create a feature with a mission_type that doesn't exist."""
    feature_dir = tmp_path / "kitty-specs" / "003-invalid"
    feature_dir.mkdir(parents=True)
    meta = {
        "feature_number": "003",
        "slug": "003-invalid",
        "friendly_name": "Invalid Mission Feature",
        "mission_type": "nonexistent-mission",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta))
    return feature_dir


class TestGetFeatureMissionKey:
    """Tests for get_mission_type() helper function."""

    def test_returns_mission_from_meta_json(self, feature_with_mission: Path) -> None:
        """Should extract mission key from meta.json."""
        assert get_mission_type(feature_with_mission) == "software-dev"

    def test_returns_research_mission(self, feature_with_research_mission: Path) -> None:
        """Should extract research mission key."""
        assert get_mission_type(feature_with_research_mission) == "research"

    def test_degrades_neutrally_when_no_mission_field(self, legacy_feature: Path) -> None:
        """FR-003a: a typeless meta.json degrades to neutral, never software-dev."""
        result = get_mission_type(legacy_feature)
        assert result == ""
        assert result != "software-dev"

    def test_degrades_neutrally_when_no_meta_json(self, tmp_path: Path) -> None:
        """FR-003a: an absent meta.json degrades to neutral, never software-dev."""
        empty_feature = tmp_path / "kitty-specs" / "empty"
        empty_feature.mkdir(parents=True)
        result = get_mission_type(empty_feature)
        assert result == ""
        assert result != "software-dev"

    def test_degrades_neutrally_on_invalid_json(self, tmp_path: Path) -> None:
        """FR-003a: an unreadable meta.json degrades to neutral, never software-dev."""
        feature_dir = tmp_path / "kitty-specs" / "bad-json"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text("{ invalid json }")
        result = get_mission_type(feature_dir)
        assert result == ""
        assert result != "software-dev"


@pytest.mark.non_sandbox
class TestGetMissionForFeature:
    """Tests for get_mission_for_feature() function (T004)."""

    def test_returns_correct_mission(self, feature_with_mission: Path, sample_kittify_dir: Path) -> None:
        """Should return the mission specified in meta.json."""
        mission = get_mission_for_feature(feature_with_mission, sample_kittify_dir.parent)
        assert mission.name == "Software Dev Kitty"
        assert mission.domain == "software"

    def test_returns_research_mission(self, feature_with_research_mission: Path, sample_kittify_dir: Path) -> None:
        """Should return research mission when specified."""
        mission = get_mission_for_feature(feature_with_research_mission, sample_kittify_dir.parent)
        assert mission.name == "Deep Research Kitty"
        assert mission.domain == "research"

    def test_typed_unknown_mission_raises(self, feature_with_invalid_mission: Path, sample_kittify_dir: Path) -> None:
        """A typed-but-unknown mission type surfaces a visible error (#3831/#4088,
        FR-007/SC-003) instead of the old silent warn-and-substitute to software-dev.

        The org-aware loader resolves a typed value through the resolver chain and,
        if it is neither a resolvable mission.yaml nor a registered org type, raises
        rather than falling back."""
        with pytest.raises(MissionNotFoundError):
            get_mission_for_feature(feature_with_invalid_mission, sample_kittify_dir.parent)

    def test_raises_when_no_kittify_dir(self, tmp_path: Path) -> None:
        """Should raise MissionNotFoundError when .kittify not found."""
        feature_dir = tmp_path / "orphan-feature"
        feature_dir.mkdir(parents=True)
        meta = {"feature_number": "999", "slug": "orphan", "mission": "software-dev"}
        (feature_dir / "meta.json").write_text(json.dumps(meta))

        with pytest.raises(MissionNotFoundError, match="Could not find .kittify"):
            get_mission_for_feature(feature_dir)


class TestGetMissionForFeatureLegacy:
    """Tests for backward compatibility with legacy features (T005)."""

    def test_legacy_feature_defaults_to_software_dev(self, legacy_feature: Path, sample_kittify_dir: Path) -> None:
        """Features without mission field should use software-dev."""
        mission = get_mission_for_feature(legacy_feature, sample_kittify_dir.parent)
        assert mission.domain == "software"
        assert "software" in mission.name.lower()

    def test_legacy_feature_no_type_fallback_warning(self, legacy_feature: Path, sample_kittify_dir: Path) -> None:
        """A typeless feature defaults to the software-dev template with no
        'mission not found / using software-dev as default' warning — that
        warn-and-substitute path was removed in the org-aware loader.

        The separate legacy-tier ('.kittify/missions/') 'run spec-kitty migrate'
        deprecation nudge (emitted by the shared resolver, consistent with how
        command-templates already resolve) is expected here and is not what this
        test guards."""
        import warnings as w

        with w.catch_warnings(record=True) as caught:
            w.simplefilter("always")
            get_mission_for_feature(legacy_feature, sample_kittify_dir.parent)
            fallback_warnings = [
                c
                for c in caught
                if "not found" in str(c.message).lower() or "using software-dev as default" in str(c.message).lower()
            ]
            assert fallback_warnings == []


class TestDiscoverMissions:
    """Tests for discover_missions() function."""

    def test_discovers_all_missions(self, sample_kittify_dir: Path) -> None:
        """Should find project missions plus packaged built-ins."""
        missions = discover_missions(sample_kittify_dir.parent)
        assert "software-dev" in missions
        assert "research" in missions
        assert len(missions) >= 2

    def test_returns_mission_and_source_tuple(self, sample_kittify_dir: Path) -> None:
        """Should return (Mission, source) tuples."""
        missions = discover_missions(sample_kittify_dir.parent)
        mission, source = missions["software-dev"]
        assert isinstance(mission, Mission)
        assert source == "project"

    def test_returns_built_ins_when_no_kittify(self, tmp_path: Path) -> None:
        """Should still return packaged built-ins when .kittify doesn't exist."""
        missions = discover_missions(tmp_path)
        assert "software-dev" in missions
        assert all(source == "built-in" for _, source in missions.values())

    def test_returns_built_ins_when_no_project_missions_dir(self, tmp_path: Path) -> None:
        """Should still return packaged built-ins when project missions/ doesn't exist."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        missions = discover_missions(tmp_path)
        assert "software-dev" in missions
        assert all(source == "built-in" for _, source in missions.values())

    def test_skips_invalid_missions(self, sample_kittify_dir: Path) -> None:
        """Should skip missions with invalid mission.yaml."""
        # Create invalid mission
        invalid_dir = sample_kittify_dir / "missions" / "broken"
        invalid_dir.mkdir()
        (invalid_dir / "mission.yaml").write_text("name: Missing Required Fields")

        with pytest.warns(UserWarning, match="Skipping invalid mission"):
            missions = discover_missions(sample_kittify_dir.parent)

        assert "broken" not in missions
        assert "software-dev" in missions

    def test_skips_directories_without_mission_yaml(self, sample_kittify_dir: Path) -> None:
        """Should skip directories that don't have mission.yaml."""
        # Create directory without mission.yaml
        empty_dir = sample_kittify_dir / "missions" / "empty-dir"
        empty_dir.mkdir()

        missions = discover_missions(sample_kittify_dir.parent)
        assert "empty-dir" not in missions
