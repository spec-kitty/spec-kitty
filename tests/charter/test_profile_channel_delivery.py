"""WP12 — the profile channel *renders* every kind it attests.

Profiles are loaded by the implement loop on every work package, so they are a
first-class entry vector. Before WP12 only ``_render_profile_directives`` /
``_render_profile_tactics`` existed, so a profile that resolved a procedure,
styleguide, or toolguide reached its agent with none of them.

These tests pin the render boundary:

* **T068/T070** — the PR #3007 exemplar ``procedure:onboard-external-agent-to-pack``,
  reached from ``agent_profile:doctrine-daphne`` by a ``requires`` edge (the profile
  channel), now reaches an agent under that profile.
* **T067** — a profile that cites styleguide / toolguide references renders those
  kinds too, not only directives and tactics.
* **T069** — the channel is conditional on ``profile: str | None``; an absent
  profile renders nothing and never falls open.
* **T066** — kinds the profile schema does not attest (asset / anti-pattern /
  paradigm) are **not** invented into a profile section; they are C-007 deferrals.
"""

from __future__ import annotations

import pytest

from charter.activation.context_renderers.profile_sections import (
    _PROFILE_PROCEDURES_HEADER_TPL,
    _PROFILE_STYLEGUIDES_HEADER_TPL,
    _PROFILE_TOOLGUIDES_HEADER_TPL,
    _render_profile_sections,
)
from charter.offering.agent_profiles import AgentProfile, AgentProfileRepository
from charter.offering.service import CharterOfferingService

pytestmark = pytest.mark.fast


def _real_service() -> CharterOfferingService:
    """A CharterOfferingService over the shipped built-in doctrine tree (self-resolving)."""
    return CharterOfferingService()


def test_exemplar_procedure_reaches_agent_under_daphne() -> None:
    """T068/T070: the profile-resolved procedure reaches the rendered context."""
    service = _real_service()
    profile = AgentProfileRepository().resolve_profile("doctrine-daphne")

    block = _render_profile_sections(profile, service)

    assert _PROFILE_PROCEDURES_HEADER_TPL.format(profile_id="doctrine-daphne") in block
    assert "onboard-external-agent-to-pack" in block


def test_absent_profile_renders_nothing() -> None:
    """T069: ``profile=None`` renders nothing — no fail-open procedure leak."""
    service = _real_service()
    assert _render_profile_sections(None, service) == ""


def test_styleguide_and_toolguide_kinds_render() -> None:
    """T067: a profile citing styleguide/toolguide refs renders those sections."""
    service = _real_service()
    profile = AgentProfile.model_validate(
        {
            "profile-id": "synthetic-guide-citer",
            "name": "Synthetic Guide Citer",
            "roles": ["implementer"],
            "purpose": "test fixture",
            "specialization": {"primary-focus": "testing"},
            "styleguide-references": [
                {"id": "testing-principles", "rationale": "cite a styleguide"}
            ],
            "toolguide-references": [
                {"id": "contextive", "rationale": "cite a toolguide"}
            ],
        }
    )

    block = _render_profile_sections(profile, service)

    assert (
        _PROFILE_STYLEGUIDES_HEADER_TPL.format(profile_id="synthetic-guide-citer")
        in block
    )
    assert "testing-principles" in block
    assert (
        _PROFILE_TOOLGUIDES_HEADER_TPL.format(profile_id="synthetic-guide-citer")
        in block
    )
    assert "contextive" in block


def test_unattested_kinds_are_not_invented() -> None:
    """T066: asset / anti-pattern / paradigm are deferred, never a profile section."""
    service = _real_service()
    profile = AgentProfileRepository().resolve_profile("doctrine-daphne")

    block = _render_profile_sections(profile, service)

    for absent in ("Profile-Cited Assets", "Profile-Cited Anti-Patterns", "Profile-Cited Paradigms"):
        assert absent not in block
