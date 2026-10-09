"""Tests for the Role half-open value object and AgentProfile model updates."""
import json
import warnings

import pytest
from pydantic import ValidationError

from charter.offering.agent_profiles.profile import AgentProfile, Role


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

class TestRoleConstruction:
    def test_known_constant_is_role_instance(self):
        assert isinstance(Role.IMPLEMENTER, Role)

    def test_role_is_str_subclass(self):
        assert issubclass(Role, str)
        assert isinstance(Role.IMPLEMENTER, str)

    def test_custom_role_constructs_without_error(self):
        r = Role("senior-tech-lead")
        assert r == "senior-tech-lead"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            Role("")

    def test_constant_equality_with_plain_string(self):
        assert Role.IMPLEMENTER == "implementer"
        assert Role.REVIEWER    == "reviewer"
        assert Role.ARCHITECT   == "architect"
        assert Role.DESIGNER    == "designer"
        assert Role.PLANNER     == "planner"
        assert Role.RESEARCHER  == "researcher"
        assert Role.CURATOR     == "curator"
        assert Role.MANAGER     == "manager"

    def test_constant_equality_with_self(self):
        assert Role("implementer") == Role.IMPLEMENTER

    def test_all_eight_constants_exist(self):
        for constant in (
            Role.IMPLEMENTER, Role.REVIEWER, Role.ARCHITECT, Role.DESIGNER,
            Role.PLANNER, Role.RESEARCHER, Role.CURATOR, Role.MANAGER,
        ):
            assert isinstance(constant, Role)


class TestRoleIsKnown:
    def test_known_constant_returns_true(self):
        assert Role.is_known(Role.IMPLEMENTER)

    def test_plain_string_known_returns_true(self):
        assert Role.is_known("implementer")

    def test_plain_string_known_is_case_insensitive(self):
        assert Role.is_known("IMPLEMENTER")

    def test_custom_role_returns_false(self):
        assert not Role.is_known(Role("data-engineer"))

    def test_unknown_string_returns_false(self):
        assert not Role.is_known("unknown-role")

    def test_all_known_constants_are_known(self):
        for constant in (
            Role.IMPLEMENTER, Role.REVIEWER, Role.ARCHITECT, Role.DESIGNER,
            Role.PLANNER, Role.RESEARCHER, Role.CURATOR, Role.MANAGER,
        ):
            assert Role.is_known(constant), f"Expected {constant!r} to be known"


class TestRoleSerialization:
    def test_json_round_trip(self):
        r = Role.IMPLEMENTER
        serialised = json.dumps(r)
        rehydrated = Role(json.loads(serialised))
        assert rehydrated == r
        assert isinstance(rehydrated, Role)

    def test_custom_role_round_trip(self):
        r = Role("my-custom-role")
        assert Role(json.loads(json.dumps(r))) == r

    def test_pydantic_serialises_as_string(self):
        p = AgentProfile(**{
            "profile-id": "test",
            "name": "Test",
            "purpose": "Test purpose",
            "specialization": {"primary-focus": "Testing"},
            "roles": ["implementer"],
        })
        dumped = p.model_dump()
        assert dumped["roles"] == ["implementer"]
        assert isinstance(dumped["roles"][0], str)


_BASE = {
    "profile-id": "test-p",
    "name": "Test Profile",
    "purpose": "Test purpose",
    "specialization": {"primary-focus": "Testing"},
}


class TestAgentProfileModel:
    def test_roles_list_accepted(self):
        p = AgentProfile(**_BASE, roles=["implementer", "reviewer"])
        assert p.roles == [Role.IMPLEMENTER, Role.REVIEWER]
        assert p.role == Role.IMPLEMENTER

    def test_roles_list_normalizes_case(self):
        p = AgentProfile(**_BASE, roles=["IMPLEMENTER", "Reviewer", "Org-Lead"])
        assert p.roles == [Role.IMPLEMENTER, Role.REVIEWER, Role("org-lead")]
        assert Role.is_known(p.roles[0])
        assert Role.is_known(p.roles[1])

    def test_scalar_role_coerces_to_list_with_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            p = AgentProfile(**_BASE, role="implementer")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "test-p" in str(w[0].message)
        assert "roles: [implementer]" in str(w[0].message)
        assert p.roles == [Role.IMPLEMENTER]

    def test_neither_role_nor_roles_raises(self):
        with pytest.raises(ValidationError):
            AgentProfile(**_BASE)

    def test_both_keys_is_a_load_error(self):
        """Re-pinned by WP04 (FR-004): "roles wins" was a silent discard.

        The old contract let a profile declare two contradictory role sources
        and resolved it by throwing one away without telling anyone. The setup
        is unchanged; only the assertion moved to the loud outcome.
        """
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            with pytest.raises(ValidationError, match="role"):
                AgentProfile(**{**_BASE, "roles": ["architect"], "role": "implementer"})

    def test_avatar_present(self):
        p = AgentProfile(**_BASE, roles=["implementer"],
                         **{"avatar-image": "agent_profiles/avatars/test.png"})
        assert p.avatar_image == "agent_profiles/avatars/test.png"

    def test_avatar_absent(self):
        p = AgentProfile(**_BASE, roles=["implementer"])
        assert p.avatar_image is None

    def test_custom_role_accepted(self):
        p = AgentProfile(**_BASE, roles=["my-custom-org-role"])
        assert p.roles[0] == "my-custom-org-role"
        assert isinstance(p.roles[0], Role)
        assert not Role.is_known(p.roles[0])

    def test_role_property_returns_first_role(self):
        p = AgentProfile(**_BASE, roles=["architect", "reviewer"])
        assert p.role == Role.ARCHITECT

    def test_single_role_list(self):
        p = AgentProfile(**_BASE, roles=["curator"])
        assert p.roles == [Role.CURATOR]
        assert p.role == Role.CURATOR
