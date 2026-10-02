"""Loud post-fix EMPTY surface for both coordination topologies (mission
coord-artifact-single-home-01M3V4BE, WP04, T021).

Research D4/US2.7/FR-003a: after this mission, every COORD write seeds the
coordination surface, so an EMPTY coordination worktree on a POST-FIX Mission
(its coordination-branch history already carries the
``Spec-Kitty-Coordination-Seed: <mission_id>`` trailer, WP03's single
discriminator -- :func:`specify_cli.coordination.coord_seed.coord_branch_is_post_fix`)
signals a regression -- the Mission dir was removed from an otherwise-seeded
worktree -- and must warn for BOTH coordination topologies, not only
``LANES_WITH_COORD`` (today's behaviour, pinned UNCHANGED for a PRE-FIX
Mission by ``test_surface_resolver_coord_empty_warning.py`` and
``test_surface_resolver_solo_coord_primary.py``). The read side keeps the
PRIMARY fallback (C-002) in every case.

The post-fix fixture is built through WP03's REAL seed (round 5, X2): a
pre-fix EMPTY Mission (``make_prefix_coord_mission(worktree="empty")``), then
``PlacementSeam.write_dir(STATUS_STATE)`` -> SEEDED (with the trailer commit),
then the Mission dir is deleted from the worktree again -- reproducing a
genuine post-fix regression shape, never a hand-rolled trailer commit (a
manual commit of the Mission dir carries no trailer and so is not post-fix).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.coordination.surface_resolver import (
    ResolvedStatusSurface,
    resolve_status_surface_with_anchor,
)
from tests._factories.coord_mission import CoordMission, make_prefix_coord_mission

pytestmark = [pytest.mark.fast]

_LOGGER_NAME = "specify_cli.coordination.surface_resolver"
_COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)


def _warning_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]


def _assert_root_fallback(resolved: ResolvedStatusSurface, coord: CoordMission) -> None:
    """C-002: every case keeps resolving to the repository root checkout."""
    assert resolved.read_dir.resolve() == coord.root_mission_dir.resolve()
    assert resolved.primary_anchor.resolve() == coord.root_mission_dir.resolve()


def _seed_then_empty_again(coord: CoordMission) -> None:
    """Seed the coordination surface through the real write-side accessor
    (the trailer commit lands on the coordination branch), then delete the
    Mission dir from the worktree again -- the post-fix regression shape.
    """
    location = placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.STATUS_STATE)
    assert location.path == coord.coord_mission_dir
    assert coord.coord_mission_dir.exists()
    shutil.rmtree(coord.coord_mission_dir)
    assert not coord.coord_mission_dir.exists()


# ---------------------------------------------------------------------------
# Post-fix: loud for BOTH topologies (the new behaviour).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_post_fix_empty_warns_for_both_topologies(tmp_path: Path, topology: MissionTopology, caplog: pytest.LogCaptureFixture) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    _seed_then_empty_again(coord)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert _warning_records(caplog), (
        f"a POST-FIX Mission's EMPTY coordination worktree must warn for "
        f"topology={topology.value!r} too -- got no WARNING record. "
        f"All records: {[(r.name, r.levelname, r.getMessage()) for r in caplog.records]}"
    )
    _assert_root_fallback(resolved, coord)


# ---------------------------------------------------------------------------
# Pre-fix: UNCHANGED (negative controls -- the mislabelled-fixture case the
# brownfield scout flags is explicitly avoided here by using the real seed,
# never the old "branch tree carries the dir" heuristic).
# ---------------------------------------------------------------------------


def test_pre_fix_coord_stays_quiet(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Today's #2533 behaviour, unchanged: a PRE-FIX solo ``coord`` Mission's
    legitimately-empty coord worktree (no seed trailer yet) stays quiet."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert not _warning_records(caplog), [r.getMessage() for r in caplog.records]
    _assert_root_fallback(resolved, coord)


def test_pre_fix_lanes_with_coord_still_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Today's behaviour, unchanged: a PRE-FIX ``lanes_with_coord`` Mission's
    empty coord worktree still warns (the pre-existing LANES_WITH_COORD
    rule — independent of the new post-fix discriminator)."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="empty")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert _warning_records(caplog)
    _assert_root_fallback(resolved, coord)


# ---------------------------------------------------------------------------
# T021 edge case -- the ``_CoordGitProbeError`` decision: degrade to loud,
# never propagate and never silently stay quiet.
# ---------------------------------------------------------------------------


def test_post_fix_discriminator_git_probe_failure_degrades_to_loud_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Decision (documented on ``_empty_coord_surface``): a git-probe failure
    while classifying post-fix-ness DEGRADES to ``post_fix=True`` (loud) and
    NEVER propagates. Pinned on a PRE-FIX solo ``coord`` Mission, which would
    otherwise stay quiet (#2533) -- the one case where degrading vs
    propagating is actually observable."""
    import specify_cli.coordination.coord_seed as coord_seed_module

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    def _boom(repo_root: Path, coordination_branch: str, mission_id: str) -> bool:
        raise coord_seed_module._CoordGitProbeError("simulated git log failure")

    monkeypatch.setattr(coord_seed_module, "coord_branch_is_post_fix", _boom)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert _warning_records(caplog), "a git-probe failure classifying post-fix-ness must degrade to LOUD, never silent"
    _assert_root_fallback(resolved, coord)
