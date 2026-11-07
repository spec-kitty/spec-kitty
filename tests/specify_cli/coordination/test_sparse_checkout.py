"""Unit tests for the lane sparse-checkout policy.

Covers FR-029: lane worktrees do NOT see ``status.events.jsonl`` or
``status.json`` even though those files exist in the underlying commit
on the coordination branch.

Also asserts that the primary checkout is unaffected — the exclusion
is per-worktree, not repo-global.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination import (
    CoordinationWorkspace,
    lane_sparse_checkout_patterns,
)
from specify_cli.lanes.lane_checkout import exclude_lane_status_files, lane_mission_dir_name

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


MISSION_SLUG = "demo-feature"
MID8 = "01J6XW9K"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"
LANE_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}-lane-a"
MISSION_DIR = f"{MISSION_SLUG}-{MID8}"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo_with_status_files(tmp_path: Path) -> Path:
    """A tmp repo where the coord branch contains the two status files.

    Mirrors the state after the bootstrap step puts ``status.events.jsonl``
    and ``status.json`` on the coordination branch.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    # Build the kitty-specs tree on main first so it propagates.
    spec_dir = repo / "kitty-specs" / MISSION_DIR
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text("# spec\n")
    (spec_dir / "status.events.jsonl").write_text(
        '{"actor":"test","wp_id":"WP01","to_lane":"planned"}\n'
    )
    (spec_dir / "status.json").write_text('{"wps":{}}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", COORD_BRANCH)
    return repo


def test_lane_sparse_checkout_patterns_shape() -> None:
    patterns = lane_sparse_checkout_patterns(MISSION_SLUG, MID8)
    assert patterns[0] == "/*"
    assert f"!kitty-specs/{MISSION_DIR}/status.events.jsonl" in patterns
    assert f"!kitty-specs/{MISSION_DIR}/status.json" in patterns
    # Exclusion patterns must begin with '!' (non-cone format).
    for line in patterns[1:]:
        assert line.startswith("!"), f"non-cone exclusion must start with '!': {line!r}"


def test_lane_sparse_checkout_excludes_status_files(
    repo_with_status_files: Path,
) -> None:
    repo = repo_with_status_files
    lane_path = repo / ".worktrees" / f"{MISSION_SLUG}-{MID8}-lane-a"
    _git(repo, "worktree", "add", "-b", LANE_BRANCH,
         str(lane_path), COORD_BRANCH)

    exclude_lane_status_files(lane_path, lane_mission_dir_name(MISSION_SLUG, coordination_mid8=MID8))

    spec_dir = lane_path / "kitty-specs" / MISSION_DIR
    # Other files in the spec dir still present.
    assert (spec_dir / "spec.md").exists()
    # The two status files are excluded from the lane filesystem.
    assert not (spec_dir / "status.events.jsonl").exists()
    assert not (spec_dir / "status.json").exists()


def test_primary_checkout_unaffected(
    repo_with_status_files: Path,
) -> None:
    """The primary checkout still contains the status files."""
    repo = repo_with_status_files
    lane_path = repo / ".worktrees" / f"{MISSION_SLUG}-{MID8}-lane-a"
    _git(repo, "worktree", "add", "-b", LANE_BRANCH,
         str(lane_path), COORD_BRANCH)
    exclude_lane_status_files(lane_path, lane_mission_dir_name(MISSION_SLUG, coordination_mid8=MID8))

    spec_dir = repo / "kitty-specs" / MISSION_DIR
    assert (spec_dir / "status.events.jsonl").exists()
    assert (spec_dir / "status.json").exists()


def test_coord_worktree_unaffected(
    repo_with_status_files: Path,
) -> None:
    """The coordination worktree must still contain the status files."""
    repo = repo_with_status_files
    coord_path = CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    # Also create a lane worktree and apply sparse-checkout.
    lane_path = repo / ".worktrees" / f"{MISSION_SLUG}-{MID8}-lane-a"
    _git(repo, "worktree", "add", "-b", LANE_BRANCH,
         str(lane_path), COORD_BRANCH)
    exclude_lane_status_files(lane_path, lane_mission_dir_name(MISSION_SLUG, coordination_mid8=MID8))

    # The coord worktree's sparse-checkout was never touched.
    coord_spec = coord_path / "kitty-specs" / MISSION_DIR
    assert (coord_spec / "status.events.jsonl").exists()
    assert (coord_spec / "status.json").exists()


def test_exclude_lane_status_files_idempotent(
    repo_with_status_files: Path,
) -> None:
    repo = repo_with_status_files
    lane_path = repo / ".worktrees" / f"{MISSION_SLUG}-{MID8}-lane-a"
    _git(repo, "worktree", "add", "-b", LANE_BRANCH,
         str(lane_path), COORD_BRANCH)

    exclude_lane_status_files(lane_path, lane_mission_dir_name(MISSION_SLUG, coordination_mid8=MID8))
    exclude_lane_status_files(lane_path, lane_mission_dir_name(MISSION_SLUG, coordination_mid8=MID8))

    spec_dir = lane_path / "kitty-specs" / MISSION_DIR
    assert not (spec_dir / "status.events.jsonl").exists()
    assert not (spec_dir / "status.json").exists()
