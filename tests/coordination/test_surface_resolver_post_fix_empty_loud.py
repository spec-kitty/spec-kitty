"""EMPTY coordination worktree, pre-fix and post-fix, under the one read door (WP05).

History: mission coord-artifact-single-home-01M3V4BE (WP04, T021) made an EMPTY coordination
worktree warn loudly while the read fell back to the repository root checkout (C-002). ADR
``2026-11-06-2-one-status-read-contract`` reverses that fallback (Mission
lane-worktree-model-hardening WP05):

* a POST-FIX Mission (its coordination branch was seeded, so it carries the log) reads the
  committed coordination branch (``COORD_BRANCH_REF``), never the root's copy; the legacy
  path projection names the composed coordination path;
* a PRE-FIX Mission (the branch holds no log yet) takes the declared pre-seed fallback: the
  write checkout, with ``fallback_reason`` on the surface instead of a log warning.

The post-fix fixture is built through WP03's REAL seed: a pre-fix EMPTY Mission
(``make_prefix_coord_mission(worktree="empty")``), then ``PlacementSeam.write_dir(STATUS_STATE)``
-> SEEDED (with the trailer commit), then the Mission dir is deleted from the worktree again.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, MissionTopology, placement_seam
from specify_cli.coordination.surface_resolver import resolve_status_surface_with_anchor
from specify_cli.status.read_surface import StatusReadSource, resolve_status_read
from tests._factories.coord_mission import CoordMission, make_prefix_coord_mission

pytestmark = [pytest.mark.fast]

_LOGGER_NAME = "specify_cli.coordination.surface_resolver"
_COORD_TOPOLOGIES = (MissionTopology.COORD, MissionTopology.LANES_WITH_COORD)


def _warning_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]


def _seed_then_empty_again(coord: CoordMission) -> None:
    """Seed the coordination surface through the real write-side accessor, then delete the
    Mission dir from the worktree again -- the post-fix regression shape."""
    location = placement_seam(coord.repo_root, coord.mission_dir_name).write_dir(MissionArtifactKind.STATUS_STATE)
    assert location.path == coord.coord_mission_dir
    assert coord.coord_mission_dir.exists()
    shutil.rmtree(coord.coord_mission_dir)
    assert not coord.coord_mission_dir.exists()


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_post_fix_empty_reads_the_coordination_branch(tmp_path: Path, topology: MissionTopology, caplog: pytest.LogCaptureFixture) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    _seed_then_empty_again(coord)

    surface = resolve_status_read(coord.repo_root, coord.mission_dir_name)
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert surface.source is StatusReadSource.COORD_BRANCH_REF
    assert surface.path is None
    # The legacy projection never names the repository root checkout's stale copy.
    assert resolved.read_dir.resolve() == coord.coord_mission_dir.resolve()
    assert resolved.primary_anchor.resolve() == coord.root_mission_dir.resolve()
    assert not _warning_records(caplog)


@pytest.mark.parametrize("topology", _COORD_TOPOLOGIES)
def test_pre_fix_empty_takes_the_declared_pre_seed_fallback(tmp_path: Path, topology: MissionTopology, caplog: pytest.LogCaptureFixture) -> None:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")

    surface = resolve_status_read(coord.repo_root, coord.mission_dir_name)
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.fallback_reason
    assert resolved.read_dir.resolve() == coord.root_mission_dir.resolve()
    assert resolved.primary_anchor.resolve() == coord.root_mission_dir.resolve()
    assert not _warning_records(caplog), [r.getMessage() for r in caplog.records]
