"""Tests for charter.offering.agent_profiles.validation and capabilities utilities.

Covers mutation-prone areas:
- is_agent_profile_file: suffix and stem boundary checks
- validate_agent_profile_yaml: required-field errors vs empty errors
- get_capabilities: all return paths (known role, unknown string, wrong type)

Patterns: Boundary Pair (filename variants), Non-Identity Inputs (real
role names vs unknown strings), Bi-Directional Logic (True/False results).
"""

from pathlib import Path

import pytest

from charter.offering.agent_profiles.capabilities import get_capabilities
from charter.offering.agent_profiles.profile import Role
from charter.offering.agent_profiles.validation import (
    is_agent_profile_file,
    validate_agent_profile_yaml,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── is_agent_profile_file ──────────────────────────────────────────────────


class TestIsAgentProfileFile:
    """Boundary pairs on file-extension and stem-suffix matching."""

    def test_canonical_agent_yaml_returns_true(self):
        assert is_agent_profile_file(Path("python-pedro.agent.yaml")) is True

    def test_yaml_without_agent_stem_returns_false(self):
        # No ".agent." in stem → not an agent profile
        assert is_agent_profile_file(Path("plan.yaml")) is False

    def test_agent_yml_suffix_returns_false(self):
        # .yml is not .yaml — one character off
        assert is_agent_profile_file(Path("python-pedro.agent.yml")) is False

    def test_yaml_with_agent_in_middle_of_stem_returns_false(self):
        # stem is "my-agent-profile" — ends with "-profile", not ".agent"
        assert is_agent_profile_file(Path("my-agent-profile.yaml")) is False

    def test_stem_ending_exactly_in_agent_returns_true(self):
        # stem = "my-profile.agent" which ends with ".agent"
        assert is_agent_profile_file(Path("my-profile.agent.yaml")) is True

    def test_non_yaml_extension_returns_false(self):
        assert is_agent_profile_file(Path("profile.agent.json")) is False

    def test_agent_yaml_in_subdirectory_returns_true(self):
        assert is_agent_profile_file(Path("built-in/python-pedro.agent.yaml")) is True


# ── validate_agent_profile_yaml ────────────────────────────────────────────


class TestValidateAgentProfileYaml:
    """validate_agent_profile_yaml returns empty list for valid profiles,
    non-empty list with field-naming errors for invalid ones."""

    def _minimal_valid(self) -> dict:
        return {
            "profile-id": "test-id",
            "name": "Test Profile",
            "purpose": "Testing",
            "role": "implementer",
            "specialization": {"primary-focus": "Testing"},
        }

    def test_valid_minimal_profile_returns_no_errors(self):
        errors = validate_agent_profile_yaml(self._minimal_valid())
        assert errors == []

    def test_missing_profile_id_returns_error(self):
        data = self._minimal_valid()
        del data["profile-id"]
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0

    def test_missing_name_returns_error(self):
        data = self._minimal_valid()
        del data["name"]
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0

    def test_missing_specialization_returns_error(self):
        data = self._minimal_valid()
        del data["specialization"]
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0

    def test_routing_priority_out_of_range_returns_error(self):
        data = self._minimal_valid()
        data["routing-priority"] = 150  # max is 100
        errors = validate_agent_profile_yaml(data)
        assert len(errors) > 0


# ── get_capabilities ───────────────────────────────────────────────────────


class TestGetCapabilities:
    """get_capabilities covers all Role enum variants and unknown strings."""

    @pytest.mark.parametrize("role", [Role(r) for r in sorted(Role._KNOWN)])
    def test_known_role_enum_returns_capabilities(self, role: Role):
        result = get_capabilities(role)
        assert result is not None
        assert result.role == role
        assert len(result.default_capabilities) > 0
        assert len(result.canonical_verbs) > 0

    def test_known_role_string_returns_capabilities(self):
        result = get_capabilities("implementer")
        assert result is not None
        assert result.role == Role.IMPLEMENTER

    def test_case_insensitive_role_string_returns_capabilities(self):
        result = get_capabilities("REVIEWER")
        assert result is not None
        assert result.role == Role.REVIEWER

    def test_unknown_role_string_returns_none(self):
        result = get_capabilities("dragon-wrangler")
        assert result is None

    def test_wrong_type_returns_none(self):
        result = get_capabilities(42)  # type: ignore[arg-type]
        assert result is None

    def test_implementer_has_write_capability(self):
        result = get_capabilities(Role.IMPLEMENTER)
        assert "write" in result.default_capabilities

    def test_reviewer_lacks_write_capability(self):
        result = get_capabilities(Role.REVIEWER)
        assert "write" not in result.default_capabilities
