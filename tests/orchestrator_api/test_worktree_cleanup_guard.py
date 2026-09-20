"""Regression: orchestrator-api lane-worktree cleanup must refuse dirt (#4753, WP02).

Pre-fix, ``_apply_lane_merge_cleanup`` ran an unconditional
``git worktree remove --force`` for every lane worktree once
``retention.remove_worktree`` resolved True -- an orchestrator-driven merge
could silently destroy uncommitted operator work in a lane worktree with no
warning and no non-zero exit, exactly mirroring the coordination-worktree
defect WP02 also fixes.

This test drives the REAL entry point (``_apply_lane_merge_cleanup``)
against a lane worktree carrying a genuine tracked-file dirt and asserts
that the shared guarded seam
(``specify_cli.git.destructive_guard.guarded_worktree_remove``) refuses
instead of force-removing it -- using the DEFAULT (non-retaining,
``retain=False``) call so the pre-fix red is a missing refusal, not a
signature error.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.core.paths import RetentionDecision
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.lanes.branch_naming import worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.orchestrator_api.commands import _apply_lane_merge_cleanup

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

SLUG = "orch-guard-fixture-01KXTM59"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _manifest(slug: str, lane_id: str = "lane-a") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=slug,
        mission_branch=f"kitty/mission-{slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=lane_id,
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def _retention(*, remove_worktree: bool) -> RetentionDecision:
    return RetentionDecision(
        delete_branch=False,
        remove_worktree=remove_worktree,
        teardown_coordination=False,
        branch_source="cli",
        worktree_source="cli",
        warnings=(),
        override_notices=(),
    )


@pytest.fixture
def lane_worktree(tmp_path: Path) -> tuple[Path, LanesManifest, Path]:
    repo = _init_repo(tmp_path)
    manifest = _manifest(SLUG)
    lane = manifest.lanes[0]
    wt_path = worktree_path(repo, SLUG, mission_id=None, lane_id=lane.lane_id)
    _git(repo, "worktree", "add", "--detach", str(wt_path))
    return repo, manifest, wt_path


def test_cleanup_refuses_dirty_lane_worktree(
    lane_worktree: tuple[Path, LanesManifest, Path],
) -> None:
    """A tracked-file edit inside the lane worktree blocks force-removal."""
    repo, manifest, wt_path = lane_worktree
    tracked_file = wt_path / "README.md"
    original = tracked_file.read_text(encoding="utf-8")
    tracked_file.write_text(original + "uncommitted operator work\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused):
        _apply_lane_merge_cleanup(
            repo,
            SLUG,
            manifest,
            retention=_retention(remove_worktree=True),
            mission_branch_deletable=False,
        )

    assert wt_path.exists(), "dirty lane worktree must survive the refusal"
    assert tracked_file.read_text(encoding="utf-8") == original + "uncommitted operator work\n"


def test_cleanup_removes_clean_lane_worktree(
    lane_worktree: tuple[Path, LanesManifest, Path],
) -> None:
    """Unchanged behavior: a clean lane worktree is still removed."""
    repo, manifest, wt_path = lane_worktree
    assert wt_path.exists()

    _apply_lane_merge_cleanup(
        repo,
        SLUG,
        manifest,
        retention=_retention(remove_worktree=True),
        mission_branch_deletable=False,
    )

    assert not wt_path.exists()


def test_cleanup_skips_worktree_removal_when_retention_resolves_no_removal(
    lane_worktree: tuple[Path, LanesManifest, Path],
) -> None:
    """`retention.remove_worktree=False` must not even attempt removal (the
    upstream skip-teardown decision is a distinct axis from the guard)."""
    repo, manifest, wt_path = lane_worktree
    assert wt_path.exists()

    _apply_lane_merge_cleanup(
        repo,
        SLUG,
        manifest,
        retention=_retention(remove_worktree=False),
        mission_branch_deletable=False,
    )

    assert wt_path.exists(), "retention.remove_worktree=False must retain the worktree"
