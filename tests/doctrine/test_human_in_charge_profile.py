"""ATDD acceptance tests for the human-in-charge sentinel profile (WP05)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.agent_profiles.repository import AgentProfileRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

_SHIPPED_DIR = Path(__file__).parents[2] / "packs" / "built-in" / "agent_profiles"


def test_human_in_charge_exists_in_shipped() -> None:
    """AgentProfileRepository.get('human-in-charge') returns a non-None profile."""
    repo = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)

    profile = repo.get("human-in-charge")

    assert profile is not None, "human-in-charge profile not found in shipped/"
    assert profile.profile_id == "human-in-charge"


def test_human_in_charge_sentinel_true() -> None:
    """profile.sentinel is True for the human-in-charge profile."""
    repo = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)

    profile = repo.get("human-in-charge")

    assert profile is not None
    assert profile.sentinel is True, f"Expected sentinel=True, got sentinel={profile.sentinel}"


def test_human_in_charge_in_shipped() -> None:
    """human-in-charge YAML exists in shipped/."""
    shipped_yaml = _SHIPPED_DIR / "human-in-charge.agent.yaml"

    assert shipped_yaml.exists(), "human-in-charge.agent.yaml not found in shipped/"


def test_kanban_shows_hic_marker(tmp_path: Path) -> None:
    """Kanban status renders 👤 marker for WPs with agent_profile: human-in-charge.

    Covers both the lazy (repo=None) and pre-built repo paths.
    """
    # repo_root is 3 levels up from _SHIPPED_DIR:
    # shipped/ → agent_profiles/ → doctrine/ → src/ → repo_root
    repo_root = _SHIPPED_DIR.parents[3]

    from specify_cli.cli.commands.agent.tasks import _get_hic_marker

    # --- lazy path: repo=None, resolved internally ---
    marker = _get_hic_marker("human-in-charge", repo_root)
    assert "👤" in marker, f"Expected '👤' marker for human-in-charge (lazy), got: {repr(marker)}"

    # --- pre-built repo path ---
    pre_built = AgentProfileRepository(built_in_dir=_SHIPPED_DIR)
    marker_prebuilt = _get_hic_marker("human-in-charge", repo_root, repo=pre_built)
    assert "👤" in marker_prebuilt, (
        f"Expected '👤' marker for human-in-charge (pre-built), got: {repr(marker_prebuilt)}"
    )

    # Non-sentinel profiles should return empty string (both paths)
    assert _get_hic_marker("generic-agent", repo_root) == ""
    assert _get_hic_marker("generic-agent", repo_root, repo=pre_built) == ""

    # Unknown/None profiles should return empty string gracefully
    assert _get_hic_marker(None, tmp_path) == ""
    assert _get_hic_marker("nonexistent-profile", tmp_path) == ""


def test_hic_marker_survives_narrowed_activation(tmp_path: Path) -> None:
    """The 👤 marker must not disappear when the project narrows
    ``activated_agent_profiles`` to a set that excludes ``human-in-charge``.

    Regression (charter-sole-door-bypass-closure-01KZ3WAA landing-fold
    defect 1): ``_get_hic_marker``'s self-resolving fallback (``repo=None``)
    built its profile lookup from ``ActiveCharterService.agent_profiles`` -- the
    activation-*gated* dict -- so a project that narrows activation to
    exclude ``human-in-charge`` (e.g. ``activated_agent_profiles:
    [architect-alphonso]``) silently loses the sentinel marker even though
    ``profile.sentinel`` is a structural property, not an activation-gated
    one (exactly like ``get_provenance()``, which this same mission's
    ``charter.activation.resolver`` module deliberately keeps ungated via
    ``agent_profile_repository`` / ``raw_repository()``).
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "activated_agent_profiles:\n  - architect-alphonso\n", encoding="utf-8"
    )

    from specify_cli.cli.commands.agent.tasks_status_cmd import _get_hic_marker

    marker = _get_hic_marker("human-in-charge", tmp_path)

    assert marker == "👤 ", (
        f"Expected the human-in-charge marker to survive narrowed activation, "
        f"got: {marker!r}"
    )
