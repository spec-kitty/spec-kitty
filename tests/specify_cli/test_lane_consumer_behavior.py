"""Behavior tests for the Lane sentinel consumers touched by #2675 (WP06).

WP05 promoted ``Lane.UNINITIALIZED`` to a real ``Lane`` StrEnum member, so
``Lane("uninitialized")`` now *succeeds* where it used to raise
``ValueError``. Several consumers had an ``except ValueError`` (or an
equality comparison against the pre-WP05 raw string sentinel) that silently
relied on that failure to mean "unseeded WP" -- those branches go dead once
WP05 lands, and every consumer already ``str(...)``-coerces the lane before
comparing it, so ``mypy`` cannot see the resulting behavior change. Only a
behavior test can.

Primary targets (these ACTUALLY FLIP after WP05 if the consumer isn't
updated -- the red-first spine; see the class module docstrings below for
the live-repro proof each test encodes):

1. ``done_bookkeeping._resolve_lane_with_planned_fallback`` (site-1): the
   ``except ValueError`` used to return ``(coord_lane, False)``; the ``try``
   now succeeds and would return ``(Lane.UNINITIALIZED, True)`` --
   flipping the force-done flag ``False -> True``.
2. ``coordination.status_transition.read_current_wp_state_transactional``
   (~:557): the ``except (ValueError, ...)`` used to return
   ``(Lane.GENESIS, None)``; the ``try`` now succeeds and would return
   ``(Lane.UNINITIALIZED, None)`` instead.

Secondary characterization (already correct both before AND after WP05 --
NOT the red-first spine, included for completeness):

3. ``core.worktree_topology._read_canonical_lane_or_default`` maps an
   unseeded WP to ``"planned"`` (StrEnum equality already covered this).
4. ``merge.done_bookkeeping._assert_merged_wps_reached_done`` (site-2)
   still treats an unseeded WP as NOT done (``Lane.UNINITIALIZED !=
   Lane.DONE``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.core.worktree_topology import _read_canonical_lane_or_default
from specify_cli.consolidation import done_bookkeeping as db
from specify_cli.status import Lane

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def unseeded_mission_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """A real git repo with a mission whose event log exists but is empty.

    Production-shaped fixture (not a toy placeholder): a genuine
    ``status.events.jsonl`` file that exists on disk with zero events, which
    is exactly the shape ``get_wp_lane`` documents as producing
    ``Lane.UNINITIALIZED`` -- a WP that was never seeded via
    ``finalize-tasks``, distinct from a mission whose event log is entirely
    absent (that path raises ``CanonicalStatusNotFoundError`` instead and is
    a different, already-covered contract).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    mission_slug = "lane-consumer-behavior-01KXTEST"
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission (unfinalized event log)")

    return repo, feature_dir, mission_slug


# ---------------------------------------------------------------------------
# Primary target 1: done_bookkeeping site-1 -- force-done must stay False.
# ---------------------------------------------------------------------------


def test_done_bookkeeping_planned_fallback_keeps_force_done_false_for_unseeded_wp() -> None:
    """RED-FIRST (T050): the exact preserved tuple, not merely "not done".

    Before WP05, ``Lane("uninitialized")`` raised ``ValueError`` and the
    ``except`` branch returned ``(coord_lane, False)``. After WP05,
    ``get_wp_lane`` returns the real ``Lane.UNINITIALIZED`` member and
    ``Lane(resolve_lane_alias(...))`` no longer raises -- without WP06's
    explicit handling this would silently flip the force-done flag to
    ``True`` (an invalid PLANNED -> DONE jump the state machine should
    reject). ``get_wp_lane`` is mocked to return ``Lane.UNINITIALIZED``
    directly -- the real, production return type per WP05 -- not the
    pre-WP05 raw string, so this test exercises the actual current
    contract.
    """
    # WP02 (verdict-seam-boundary-hardening-01KZG179, T006): the call site now
    # resolves this via ``from specify_cli.status import get_wp_lane`` (the
    # facade symbol), not the ``status.lane_reader`` submodule object, so the
    # mock target moves to the facade's own already-bound attribute.
    with patch("specify_cli.status.get_wp_lane", return_value=Lane.UNINITIALIZED):
        lane, force_done = db._resolve_lane_with_planned_fallback(
            coord_lane=Lane.PLANNED,
            primary_feature_dir=Path("/nonexistent/primary"),
            wp_id="WP42",
        )

    assert (lane, force_done) == (Lane.PLANNED, False)


# ---------------------------------------------------------------------------
# Primary target 2: coordination/status_transition.py:557 -- GENESIS fallback.
# ---------------------------------------------------------------------------


def test_transactional_read_preserves_genesis_fallback_for_unseeded_wp(
    unseeded_mission_repo: tuple[Path, Path, str],
) -> None:
    """RED-FIRST (T050): unseeded WP must still resolve to Lane.GENESIS.

    Before WP05, ``Lane(resolve_lane_alias(get_wp_lane(...)))`` raised
    ``ValueError`` for the "uninitialized" sentinel and the ``except``
    branch returned ``(Lane.GENESIS, None)`` (the FR-008d/R7 contract).
    After WP05 the ``try`` succeeds and would return
    ``(Lane.UNINITIALIZED, None)`` instead -- a type-invisible flip (every
    caller ``str(...)``-coerces the result) unless WP06 preserves the
    fallback explicitly.
    """
    repo, feature_dir, mission_slug = unseeded_mission_repo

    from specify_cli.coordination.status_transition import (
        read_current_wp_state_transactional,
    )

    _state = read_current_wp_state_transactional(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id="WP01",
        repo_root=repo,
    )
    lane, actor = _state.lane, _state.actor

    assert lane == Lane.GENESIS
    assert actor is None


# ---------------------------------------------------------------------------
# Secondary characterization 3: worktree_topology unseeded -> planned.
# ---------------------------------------------------------------------------


def test_worktree_topology_unseeded_wp_reads_as_planned(
    unseeded_mission_repo: tuple[Path, Path, str],
) -> None:
    """Secondary characterization (NOT the red-first spine): already correct
    both before and after WP05 -- ``Lane.UNINITIALIZED`` compares equal to
    the legacy string sentinel via StrEnum equality either way. Included so
    the consumer's explicit ``Lane.UNINITIALIZED`` comparison (T052) stays
    pinned against a real event log rather than only a mocked return value.
    """
    _repo, feature_dir, _mission_slug = unseeded_mission_repo

    assert _read_canonical_lane_or_default(feature_dir, "WP01") == "planned"


# ---------------------------------------------------------------------------
# Secondary characterization 4: done_bookkeeping site-2 -- still not done.
# ---------------------------------------------------------------------------


def test_assert_merged_wps_reached_done_treats_unseeded_wp_as_not_done(
    unseeded_mission_repo: tuple[Path, Path, str],
) -> None:
    """Secondary characterization (NOT the red-first spine): already correct
    both before and after WP05 -- ``Lane.UNINITIALIZED != Lane.DONE`` holds
    either way the comparison arrives (via the now-dead ``except
    ValueError`` before WP06, or via the direct equality check after).
    """
    repo, _feature_dir, mission_slug = unseeded_mission_repo
    surface = repo / "kitty-specs" / mission_slug / "status.events.jsonl"

    with (
        patch.object(db, "resolve_status_surface", return_value=surface),
        pytest.raises(typer.Exit) as exc_info,
    ):
        db._assert_merged_wps_reached_done(repo, mission_slug, ["WP01"])

    assert exc_info.value.exit_code == 1
