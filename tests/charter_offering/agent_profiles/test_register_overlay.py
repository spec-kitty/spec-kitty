"""Unit coverage for ``AgentProfileRepository.register_overlay`` (R1).

``register_overlay`` is the public overlay seam that replaced the direct
``_profiles``/``_provenance``/``_source_paths`` writes at the projection and
dispatch surfaces. It honours ``_LAYER_RANK`` precedence:

* an ``org`` overlay REPLACES a ``builtin`` entry (org outranks builtin);
* an ``org`` overlay does NOT clobber a ``project`` entry (project outranks org);
* a previously-unseen id is always admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.profile import AgentProfile
from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


def _make_profile(profile_id: str, *, name: str) -> AgentProfile:
    """Build a minimal-but-valid profile for overlay tests."""
    return AgentProfile.model_validate(
        {
            "profile-id": profile_id,
            "name": name,
            "description": "Overlay unit-test profile",
            "schema-version": "1.0",
            "roles": ["implementer"],
            "purpose": "Unit test profile for register_overlay rank semantics.",
            "specialization": {"primary-focus": "overlay testing"},
        }
    )


def test_org_overlay_replaces_builtin() -> None:
    """An org overlay of a built-in id wins (org outranks builtin)."""
    repo = AgentProfileRepository()
    assert repo.get_provenance("python-pedro") == "builtin"

    org = _make_profile("python-pedro", name="Org Pedro")
    src = Path("/org/python-pedro.agent.yaml")
    repo.register_overlay(org, layer="org", source_path=src)

    assert repo.get_provenance("python-pedro") == "org"
    resolved = repo.get("python-pedro")
    assert resolved is not None and resolved.name == "Org Pedro"
    assert repo.get_source_path("python-pedro") == src


def test_org_overlay_does_not_clobber_project() -> None:
    """An org overlay never replaces a higher-ranked project entry."""
    repo = AgentProfileRepository()
    project = _make_profile("acme-implementer", name="Acme Project Impl")
    project_src = Path("/proj/acme-implementer.agent.yaml")
    repo.register_overlay(project, layer="project", source_path=project_src)

    org = _make_profile("acme-implementer", name="Org Impl")
    repo.register_overlay(org, layer="org", source_path=Path("/org/acme.agent.yaml"))

    assert repo.get_provenance("acme-implementer") == "project"
    resolved = repo.get("acme-implementer")
    assert resolved is not None and resolved.name == "Acme Project Impl"
    assert repo.get_source_path("acme-implementer") == project_src


def test_overlay_admits_unseen_id() -> None:
    """A previously-unseen id is admitted at the overlay layer."""
    repo = AgentProfileRepository()
    assert repo.get("brand-new-org-analyst") is None

    org = _make_profile("brand-new-org-analyst", name="Brand New Analyst")
    repo.register_overlay(org, layer="org", source_path=None)

    assert repo.get_provenance("brand-new-org-analyst") == "org"
    resolved = repo.get("brand-new-org-analyst")
    assert resolved is not None and resolved.name == "Brand New Analyst"
