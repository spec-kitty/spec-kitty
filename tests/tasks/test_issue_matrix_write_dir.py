"""Red-first: the issue-matrix writer writes IN PLACE at ``write_dir(ISSUE_MATRIX)`` (WP10, T053/T056).

Mission coord-artifact-single-home-01M3V4BE, WP10 (single-home rule, FR-003 /
FR-007 / SC-003). At base, ``write_issue_matrix`` stages ``issue-matrix.json``
at the caller-supplied ``feature_dir`` (the repository root checkout), and
``commit_router``'s legacy ``shutil.copy2`` then copies it onto the
coordination worktree. This pins the single-home contract: the write lands
directly on the coordination Mission dir, with NO root-checkout residue, and
a refused write (remote-only coordination branch) touches no disk at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.tasks.issue_matrix import IssueMatrixEntry, write_issue_matrix
from tests._factories.coord_mission import (
    CoordMission,
    COORD_TOPOLOGIES,
    make_coord_mission,
    make_prefix_coord_mission,
)
from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SEED_TRAILER = "Spec-Kitty-Coordination-Seed"


def _root_porcelain(coord: CoordMission) -> str:
    relpath = f"kitty-specs/{coord.mission_dir_name}"
    return subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", relpath],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _seed_commit_count(coord: CoordMission) -> int:
    trailer = subprocess.run(
        ["git", "-C", str(coord.repo_root), "log", f"--format=%(trailers:key={_SEED_TRAILER},valueonly)", coord.coordination_branch],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len([line for line in trailer.splitlines() if line.strip()])


def _write(coord: CoordMission, *, actor: str = "tester") -> WriteSeamResult:
    policy = ProtectionPolicy.resolve(coord.repo_root)
    rows = {"#1": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")}
    return write_issue_matrix(
        repo_root=coord.repo_root,
        mission_slug=coord.mission_dir_name,
        rows=rows,
        policy=policy,
        actor=actor,
        target_branch=coord.target_branch,
    )


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_issue_matrix_write_lands_on_coord_with_no_root_residue(tmp_path: Path, topology: MissionTopology) -> None:
    """A MATERIALIZED coordination Mission: the matrix lands on the
    coordination worktree directly, and the root checkout carries no trace
    of the write."""
    coord = make_coord_mission(tmp_path, topology, materialized=True)
    root_status_before = _root_porcelain(coord)

    result = _write(coord)

    assert result.status in ("committed", "unchanged"), result.diagnostic
    coord_file = coord.coord_mission_dir / "issue-matrix.json"
    assert coord_file.exists()
    assert '"verdict": "fixed"' in coord_file.read_text(encoding="utf-8")
    root_file = coord.root_mission_dir / "issue-matrix.json"
    assert not root_file.exists()
    assert _root_porcelain(coord) == root_status_before


def test_issue_matrix_write_prefix_empty_seeds_then_writes_in_place(tmp_path: Path) -> None:
    """Pre-fix EMPTY coordination surface: the write seeds the surface first
    (one seed commit), then lands the matrix in place on the coordination
    Mission dir."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    root_status_before = _root_porcelain(coord)

    result = _write(coord)

    assert result.status in ("committed", "unchanged"), result.diagnostic
    coord_file = coord.coord_mission_dir / "issue-matrix.json"
    assert coord_file.exists()
    root_file = coord.root_mission_dir / "issue-matrix.json"
    assert not root_file.exists()
    assert _root_porcelain(coord) == root_status_before
    # N3 (WP10 cycle 2 fold): the coordination branch carries exactly ONE
    # seed commit -- the docstring's "seeds the surface first" promise, now
    # actually asserted (the tracer sibling test already pins this).
    assert _seed_commit_count(coord) == 1


def test_issue_matrix_write_remote_only_refuses_before_any_write(tmp_path: Path) -> None:
    """A remote-only coordination branch (#4970 parity): the write is
    refused, with NO coordination worktree created and nothing written
    anywhere on disk."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    root_status_before = _root_porcelain(coord)

    result = _write(coord)

    assert result.status == "refused"
    assert not coord.coord_worktree_path.exists()
    assert _root_porcelain(coord) == root_status_before
    assert result.surfaces == ()


def test_issue_matrix_write_non_coord_topology_writes_at_same_primary_path(tmp_path: Path) -> None:
    """C-008: a ``lanes``-topology Mission (no coordination surface at all)
    writes at the SAME primary path as before this WP, committed to the
    same ref."""
    slug = "no-coord-issue-matrix-demo"
    _init_git_repo(tmp_path, branch="topic")
    result = _create_mission(tmp_path, slug, MissionTopology.LANES)
    feature_dir = result.feature_dir
    policy = ProtectionPolicy.resolve(tmp_path)

    rows = {"#1": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")}
    write_result = write_issue_matrix(
        repo_root=tmp_path,
        mission_slug=slug,
        rows=rows,
        policy=policy,
        actor="tester",
        target_branch=result.target_branch,
    )

    assert write_result.status in ("committed", "unchanged"), write_result.diagnostic
    primary_file = feature_dir / "issue-matrix.json"
    assert primary_file.exists()
