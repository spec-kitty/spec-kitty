"""
Test suite for RoleCapabilities.
"""

from charter.offering.agent_profiles.capabilities import DEFAULT_ROLE_CAPABILITIES, RoleCapabilities, get_capabilities
from charter.offering.agent_profiles.profile import AgentProfile, Role
import pytest
pytestmark = [pytest.mark.fast, pytest.mark.doctrine]



class TestRoleCapabilities:
    """Test RoleCapabilities model and defaults."""

    def test_all_roles_have_default_capabilities(self):
        """Each well-known Role value has a default RoleCapabilities entry."""
        for role in [Role(r) for r in sorted(Role._KNOWN)]:
            assert role in DEFAULT_ROLE_CAPABILITIES, f"Missing capabilities for {role}"
            caps = DEFAULT_ROLE_CAPABILITIES[role]
            assert isinstance(caps, RoleCapabilities)
            assert caps.role == role

    def test_default_capabilities_are_non_empty(self):
        """All default capability lists are non-empty."""
        for role, caps in DEFAULT_ROLE_CAPABILITIES.items():
            assert len(caps.default_capabilities) > 0, f"{role} has empty capabilities"
            assert len(caps.canonical_verbs) > 0, f"{role} has empty canonical verbs"

    def test_get_capabilities_for_known_role_enum(self):
        """get_capabilities() returns capabilities for Role enum."""
        caps = get_capabilities(Role.IMPLEMENTER)
        assert caps is not None
        assert caps.role == Role.IMPLEMENTER
        assert "write" in caps.default_capabilities
        assert "implement" in caps.canonical_verbs

    def test_get_capabilities_for_known_role_string(self):
        """get_capabilities() handles role string (case-insensitive)."""
        caps = get_capabilities("architect")
        assert caps is not None
        assert caps.role == Role.ARCHITECT

        caps_upper = get_capabilities("REVIEWER")
        assert caps_upper is not None
        assert caps_upper.role == Role.REVIEWER

    def test_get_capabilities_for_profile_role_from_mixed_case_roles_list(self):
        """Profile-owned role normalization keeps capability lookup case-insensitive."""
        profile = AgentProfile(
            profile_id="casey",
            name="Casey",
            purpose="Case normalization",
            roles=["IMPLEMENTER"],
            specialization={"primary-focus": "Testing"},
        )

        caps = get_capabilities(profile.role)

        assert caps is not None
        assert caps.role == Role.IMPLEMENTER

    def test_get_capabilities_for_custom_role_returns_none(self):
        """get_capabilities() returns None for unknown custom roles."""
        caps = get_capabilities("devops-engineer")
        assert caps is None

        caps_unknown = get_capabilities("security-specialist")
        assert caps_unknown is None

    def test_implementer_capabilities(self):
        """Implementer has expected capabilities."""
        caps = DEFAULT_ROLE_CAPABILITIES[Role.IMPLEMENTER]
        assert "read" in caps.default_capabilities
        assert "write" in caps.default_capabilities
        assert "edit" in caps.default_capabilities
        assert "bash" in caps.default_capabilities
        assert "generate" in caps.canonical_verbs
        assert "implement" in caps.canonical_verbs

    def test_reviewer_capabilities(self):
        """Reviewer has expected (limited) capabilities."""
        caps = DEFAULT_ROLE_CAPABILITIES[Role.REVIEWER]
        assert "read" in caps.default_capabilities
        assert "search" in caps.default_capabilities
        # Reviewer should NOT have write access
        assert "write" not in caps.default_capabilities
        assert "audit" in caps.canonical_verbs
        assert "review" in caps.canonical_verbs

    def test_architect_capabilities(self):
        """Architect has broad capabilities."""
        caps = DEFAULT_ROLE_CAPABILITIES[Role.ARCHITECT]
        assert "read" in caps.default_capabilities
        assert "write" in caps.default_capabilities
        assert "search" in caps.default_capabilities
        assert "synthesize" in caps.canonical_verbs
        assert "plan" in caps.canonical_verbs
