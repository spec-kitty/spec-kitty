"""Tests for YAML schema validation of agent profiles."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.agent_profiles.profile import AgentProfile
from charter.offering.agent_profiles.validation import (
    is_agent_profile_file,
    validate_agent_profile_yaml,
)
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_profile(fixtures_dir: Path) -> dict:
    """Load valid complete profile fixture."""
    yaml = YAML(typ="safe")
    with (fixtures_dir / "valid-profile.agent.yaml").open() as f:
        return yaml.load(f)


@pytest.fixture
def minimal_profile(fixtures_dir: Path) -> dict:
    """Load minimal valid profile fixture."""
    yaml = YAML(typ="safe")
    with (fixtures_dir / "minimal-profile.agent.yaml").open() as f:
        return yaml.load(f)


@pytest.fixture
def invalid_missing_purpose(fixtures_dir: Path) -> dict:
    """Load invalid profile (missing purpose)."""
    yaml = YAML(typ="safe")
    with (fixtures_dir / "invalid-missing-purpose.agent.yaml").open() as f:
        return yaml.load(f)


@pytest.fixture
def invalid_bad_priority(fixtures_dir: Path) -> dict:
    """Load invalid profile (bad routing-priority)."""
    yaml = YAML(typ="safe")
    with (fixtures_dir / "invalid-bad-priority.agent.yaml").open() as f:
        return yaml.load(f)


class TestSchemaValidation:
    """Test YAML schema validation."""

    def test_valid_complete_profile_passes(self, valid_profile: dict):
        """Valid complete profile passes validation."""
        errors = validate_agent_profile_yaml(valid_profile)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_minimal_profile_passes(self, minimal_profile: dict):
        """Minimal valid profile (only required fields) passes."""
        errors = validate_agent_profile_yaml(minimal_profile)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_purpose_fails(self, invalid_missing_purpose: dict):
        """Missing required 'purpose' field fails validation."""
        errors = validate_agent_profile_yaml(invalid_missing_purpose)
        assert len(errors) > 0
        assert any("purpose" in err.lower() for err in errors)

    def test_missing_specialization_fails(self):
        """Missing required 'specialization' section fails."""
        data = {
            "profile-id": "test",
            "name": "Test",
            "purpose": "Testing",
            # Missing specialization
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("specialization" in err.lower() for err in errors)

    def test_missing_profile_id_fails(self):
        """Missing required 'profile-id' fails."""
        data = {
            "name": "Test",
            "purpose": "Testing",
            "specialization": {"primary-focus": "Test"},
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("profile-id" in err.lower() for err in errors)

    def test_missing_name_fails(self):
        """Missing required 'name' fails."""
        data = {
            "profile-id": "test",
            "purpose": "Testing",
            "specialization": {"primary-focus": "Test"},
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("name" in err.lower() for err in errors)

    def test_missing_primary_focus_fails(self):
        """Missing required 'specialization.primary-focus' fails."""
        data = {
            "profile-id": "test",
            "name": "Test",
            "purpose": "Testing",
            "specialization": {},  # Missing primary-focus
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("primary-focus" in err.lower() for err in errors)

    def test_routing_priority_out_of_range_high_fails(self, invalid_bad_priority: dict):
        """routing-priority > 100 fails."""
        errors = validate_agent_profile_yaml(invalid_bad_priority)
        assert len(errors) > 0
        assert any("routing-priority" in err.lower() or "150" in err for err in errors)

    def test_routing_priority_negative_fails(self):
        """routing-priority < 0 fails."""
        data = {
            "profile-id": "test",
            "name": "Test",
            "purpose": "Testing",
            "routing-priority": -1,
            "specialization": {"primary-focus": "Test"},
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("routing-priority" in err.lower() or "-1" in err for err in errors)

    def test_unknown_top_level_field_fails(self):
        """Unknown top-level field fails (additionalProperties: false)."""
        data = {
            "profile-id": "test",
            "name": "Test",
            "purpose": "Testing",
            "specialization": {"primary-focus": "Test"},
            "unknown-field": "should fail",
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0
        assert any("unknown-field" in err.lower() or "additional" in err.lower() for err in errors)

    def test_max_concurrent_tasks_zero_fails(self):
        """max-concurrent-tasks: 0 fails (minimum 1)."""
        data = {
            "profile-id": "test",
            "name": "Test",
            "purpose": "Testing",
            "max-concurrent-tasks": 0,
            "specialization": {"primary-focus": "Test"},
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0

    def test_invalid_profile_id_pattern_fails(self):
        """profile-id not matching pattern fails."""
        data = {
            "profile-id": "Invalid_ID",  # Underscore not allowed
            "name": "Test",
            "purpose": "Testing",
            "specialization": {"primary-focus": "Test"},
        }
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0


class TestAgentProfileSchemaVersionContract:
    """Schema and runtime model agree on agent-profile schema-version values."""

    def _profile_with_schema_version(self, schema_version: str) -> dict:
        return {
            "profile-id": "schema-version-test",
            "name": "Schema Version Test",
            "purpose": "Prove schema-version validation is consistent.",
            "schema-version": schema_version,
            "roles": ["implementer"],
            "specialization": {"primary-focus": "Schema validation"},
        }

    @pytest.mark.parametrize("schema_version", ["1.0", "2"])
    def test_schema_and_runtime_accept_supported_schema_versions(self, schema_version: str) -> None:
        data = self._profile_with_schema_version(schema_version)

        assert validate_agent_profile_yaml(data) == []
        assert AgentProfile.model_validate(data).schema_version == schema_version

    @pytest.mark.parametrize("schema_version", ["1", "2.0", "3", "latest", ""])
    def test_schema_and_runtime_reject_unsupported_schema_versions(self, schema_version: str) -> None:
        data = self._profile_with_schema_version(schema_version)

        errors = validate_agent_profile_yaml(data)
        assert any("schema-version" in error for error in errors)

        with pytest.raises(ValueError, match="schema-version|schema_version|String should match pattern"):
            AgentProfile.model_validate(data)


class TestFileTypeDetection:
    """Test file type detection utility (T018b)."""

    def test_agent_profile_file_detected(self):
        """File with .agent.yaml extension is detected."""
        assert is_agent_profile_file(Path("test.agent.yaml")) is True

    def test_regular_yaml_not_detected(self):
        """Regular .yaml file is not detected."""
        assert is_agent_profile_file(Path("test.yaml")) is False

    def test_non_yaml_not_detected(self):
        """Non-YAML file is not detected."""
        assert is_agent_profile_file(Path("test.md")) is False

    def test_dotfile_agent_yaml_detected(self):
        """Hidden .agent.yaml file is detected."""
        assert is_agent_profile_file(Path(".hidden.agent.yaml")) is True
