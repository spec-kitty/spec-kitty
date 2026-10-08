"""T005 — ATDD test: ``agent_profile_repository`` accessor semantics (FR-001).

charter-sole-door-bypass-closure-01KZ3WAA WP01. Proves the pinned semantics
hold, not just that the accessor exists (contracts/charter-doctrine-service-
contract.md "Lineage/mutation accessor semantics"):

1. ``register_overlay()`` of a non-activated profile via the accessor still
   leaves it excluded from the gated ``agent_profiles`` property -- mutation
   capability and activation filtering are orthogonal.
2. ``get_provenance()`` via the accessor is a read-only lookup on the raw
   repository, returning the expected provenance for a known profile.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from charter.activation.pack_context import PackContext
from charter.activation.resolver import ActiveCharterService
from charter.offering.agent_profiles import AgentProfileRepository
from charter.offering.service import CharterOfferingService

pytestmark = pytest.mark.fast


def _known_builtin_profile_id() -> str:
    """Return a real built-in agent profile ID, skipping if the layout has none."""
    profiles = AgentProfileRepository().list_all()
    if not profiles:
        pytest.skip("no built-in agent profiles available in this layout")
    return profiles[0].profile_id


class TestAccessorReturnsRawRepository:
    """The accessor returns the SAME raw repository object ``_inner`` holds."""

    def test_returns_the_inner_agent_profiles_repository(self) -> None:
        inner = CharterOfferingService()
        wrapped = ActiveCharterService(inner, pack_context=None)

        assert wrapped.agent_profile_repository is inner.agent_profiles


class TestRegisterOverlayDoesNotBypassActivationFilter:
    """T001 pinned semantics #1: a mutation via the accessor never leaks past
    the gated ``agent_profiles`` property's three-state activation filter."""

    def test_overlaid_non_activated_profile_stays_gated_out(self) -> None:
        inner = CharterOfferingService()
        pack_ctx = MagicMock(spec=PackContext)
        # Explicit activation set that excludes the profile we are about to
        # overlay -- proves the filter, not a bare-project "admit all" no-op.
        pack_ctx.activated_agent_profiles = frozenset({"reviewer-renata"})

        wrapped = ActiveCharterService(inner, pack_context=pack_ctx)

        shadow_profile = MagicMock()
        shadow_profile.profile_id = "shadow-sam"
        wrapped.agent_profile_repository.register_overlay(
            shadow_profile, layer="org", source_path=None
        )

        # The mutation landed on the raw repository...
        assert wrapped.agent_profile_repository.get("shadow-sam") is shadow_profile
        # ...but the gated `agent_profiles` view still excludes it: mutation
        # and activation filtering are orthogonal (T001 pinned semantics).
        assert "shadow-sam" not in wrapped.agent_profiles

    def test_overlaid_activated_profile_becomes_visible(self) -> None:
        """Sanity control: an ACTIVATED overlay id does pass the filter.

        Without this, the previous test could pass vacuously if the filter
        excluded everything regardless of the overlay.
        """
        inner = CharterOfferingService()
        pack_ctx = MagicMock(spec=PackContext)
        pack_ctx.activated_agent_profiles = frozenset({"shadow-sam"})

        wrapped = ActiveCharterService(inner, pack_context=pack_ctx)

        shadow_profile = MagicMock()
        shadow_profile.profile_id = "shadow-sam"
        wrapped.agent_profile_repository.register_overlay(
            shadow_profile, layer="org", source_path=None
        )

        assert wrapped.agent_profiles == {"shadow-sam": shadow_profile}


class TestGetProvenanceIsReadOnlyOnRawRepository:
    """T001 pinned semantics #2: ``get_provenance()`` reads the raw repository."""

    def test_returns_builtin_for_a_known_builtin_profile(self) -> None:
        profile_id = _known_builtin_profile_id()
        inner = CharterOfferingService()
        wrapped = ActiveCharterService(inner, pack_context=None)

        assert wrapped.agent_profile_repository.get_provenance(profile_id) == "builtin"

    def test_returns_none_for_an_unknown_profile(self) -> None:
        inner = CharterOfferingService()
        wrapped = ActiveCharterService(inner, pack_context=None)

        assert wrapped.agent_profile_repository.get_provenance("no-such-profile") is None
