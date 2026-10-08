"""WP02 (#3176): builder ``agent_profile_overlay_dir`` seam.

Red-first (C-003): on ``upstream/main`` the builder has no
``agent_profile_overlay_dir`` parameter, so the ``overlay-set`` call raises
``TypeError`` — the red signal. Once the seam is threaded, the project profile
authored at ``.kittify/agent_profiles/<id>.agent.yaml`` becomes visible through
``build_activation_aware_doctrine_service(...).agent_profile_repository`` while
the unset call stays byte-identical (NFR-002): it resolves the doctrine-root
``agent_profiles`` directory, never ``.kittify/agent_profiles``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PROJECT_OVERLAY = ".kittify/agent_profiles"
_PROFILE_ID = "custom-carol"


def _seed_project_profile(repo_root: Path) -> Path:
    """Author ``.kittify/agent_profiles/custom-carol.agent.yaml`` under *repo_root*."""
    overlay_dir = repo_root / _PROJECT_OVERLAY
    overlay_dir.mkdir(parents=True)
    (overlay_dir / f"{_PROFILE_ID}.agent.yaml").write_text(
        "\n".join(
            [
                f"profile-id: {_PROFILE_ID}",
                "name: Custom Carol",
                "description: Project profile.",
                "roles:",
                "  - architect",
                "purpose: Project-only profile.",
                "specialization:",
                "  primary-focus: testing projections",
                "  avoidance-boundary: unrelated work",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return overlay_dir


def test_overlay_dir_exposes_project_profile(tmp_path: Path) -> None:
    """With the overlay set, the seeded project profile is visible through the seam."""
    overlay_dir = _seed_project_profile(tmp_path)

    service = build_activation_aware_doctrine_service(tmp_path, agent_profile_overlay_dir=overlay_dir)
    ids = {p.profile_id for p in service.agent_profile_repository.list_all()}

    assert _PROFILE_ID in ids


def test_overlay_unset_is_byte_identical(tmp_path: Path) -> None:
    """Unset (default ``None``) resolves the doctrine root, not ``.kittify/agent_profiles``."""
    _seed_project_profile(tmp_path)

    service = build_activation_aware_doctrine_service(tmp_path)
    ids = {p.profile_id for p in service.agent_profile_repository.list_all()}

    assert _PROFILE_ID not in ids


def test_doctrine_service_overlay_dir_directs_project_dir(tmp_path: Path) -> None:
    """NFR-002: overlay set ⇒ repo project_dir is the overlay; unset ⇒ ``_project_dir``."""
    overlay = tmp_path / _PROJECT_OVERLAY
    overlay.mkdir(parents=True)

    unset = CharterOfferingService(project_root=tmp_path)
    assert unset.agent_profiles._project_dir == unset._project_dir("agent_profiles")

    directed = CharterOfferingService(project_root=tmp_path, agent_profile_overlay_dir=overlay)
    assert directed.agent_profiles._project_dir == overlay
