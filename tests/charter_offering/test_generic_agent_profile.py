"""Acceptance tests for the generic-agent profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_SHIPPED_DIR = Path(__file__).parents[2] / "packs" / "built-in" / "agent_profiles"


def test_generic_agent_exists_in_shipped() -> None:
    """generic-agent profile must be loadable from shipped/."""
    repo = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)

    profile = repo.get("generic-agent")

    assert profile is not None, "generic-agent profile not found in shipped/"
    assert profile.profile_id == "generic-agent"


def test_generic_agent_references_directive_028() -> None:
    """Resolved profile has exactly one directive reference to DIRECTIVE_028 (code='028')."""
    repo = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)

    profile = repo.get("generic-agent")
    assert profile is not None

    directive_codes = [ref.code for ref in profile.directive_references]
    assert "028" in directive_codes, f"Expected code '028' in directive_references, got: {directive_codes}"
    assert directive_codes == ["028"], f"Expected exactly 1 directive reference, got: {directive_codes}"
