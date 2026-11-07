"""Integration coverage for lane lifecycle auto-rebase sync points."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.lifecycle_sync import (
    LANE_AUTO_REBASE_FAILED,
    LaneAutoRebaseSyncError,
    sync_lane_after_coordination_commit,
)
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _status_event(
    event_id: str,
    *,
    mission_slug: str,
    to_lane: str,
) -> str:
    return json.dumps(
        {
            "actor": "tester",
            "at": "2026-06-15T04:00:00Z",
            "event_id": event_id,
            "execution_mode": "worktree",
            "force": False,
            "from_lane": "genesis",
            "mission_slug": mission_slug,
            "reason": None,
            "review_ref": None,
            "to_lane": to_lane,
            "wp_id": "WP01",
        },
        sort_keys=True,
    ) + "\n"


def _init_repo(tmp_path: Path, mission_slug: str) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@spec-kitty"], repo)
    _run(["git", "config", "user.name", "test"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    feature_dir = repo / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True)
    write_single_lane_manifest(
        feature_dir,
        wp_ids=("WP01",),
        lane_id="lane-a",
        write_scope=("src/**", "kitty-specs/**"),
    )
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\n---\n# WP01\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "shared.txt").write_text("base\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "seed mission"], repo)

    coordination_branch = f"kitty/mission-{mission_slug}"
    lane_branch = f"kitty/mission-{mission_slug}-lane-a"
    _run(["git", "branch", coordination_branch, "main"], repo)
    worktree = repo / ".worktrees" / f"{mission_slug}-lane-a"
    worktree.parent.mkdir()
    _run(["git", "worktree", "add", "-b", lane_branch, str(worktree), "main"], repo)
    _run(["git", "config", "user.email", "test@spec-kitty"], worktree)
    _run(["git", "config", "user.name", "test"], worktree)
    return repo, feature_dir, coordination_branch, lane_branch


def test_lifecycle_sync_clean_rebase_updates_lane_worktree(tmp_path: Path) -> None:
    repo, feature_dir, coordination_branch, _lane_branch = _init_repo(
        tmp_path,
        "sync-clean",
    )
    worktree = repo / ".worktrees" / "sync-clean-lane-a"

    _run(["git", "switch", coordination_branch], repo)
    (feature_dir / "status.events.jsonl").write_text(
        _status_event(
            "01AAA000000000000000000001",
            mission_slug="sync-clean",
            to_lane="claimed",
        ),
        encoding="utf-8",
    )
    _run(["git", "add", "kitty-specs/sync-clean/status.events.jsonl"], repo)
    _run(["git", "commit", "-m", "coord: claim WP01"], repo)
    _run(["git", "switch", "main"], repo)

    (worktree / "src" / "lane.txt").write_text("lane work\n", encoding="utf-8")
    _run(["git", "add", "src/lane.txt"], worktree)
    _run(["git", "commit", "-m", "lane work"], worktree)

    report = sync_lane_after_coordination_commit(
        repo_root=repo,
        mission_slug="sync-clean",
        wp_id="WP01",
        coordination_branch=coordination_branch,
    )

    assert report is not None
    assert report.succeeded is True
    assert (worktree / "kitty-specs" / "sync-clean" / "status.events.jsonl").exists()


def test_lifecycle_sync_recreate_has_no_status_files(tmp_path: Path) -> None:
    """The recreate goes through the one lane-checkout helper (Mission WP09, FR-040).

    The recreated checkout is attached to the lane branch and never shows the
    Mission's status files, while the lane branch tree still carries the log
    the coordination merge brought in (C-008: no lane-side deletion).
    """
    repo, feature_dir, coordination_branch, lane_branch = _init_repo(
        tmp_path,
        "sync-missing-worktree",
    )
    worktree = repo / ".worktrees" / "sync-missing-worktree-lane-a"
    _run(["git", "worktree", "remove", "--force", str(worktree)], repo)

    _run(["git", "switch", coordination_branch], repo)
    (feature_dir / "status.events.jsonl").write_text(
        _status_event(
            "01BBB000000000000000000002",
            mission_slug="sync-missing-worktree",
            to_lane="in_review",
        ),
        encoding="utf-8",
    )
    _run(
        [
            "git",
            "add",
            "kitty-specs/sync-missing-worktree/status.events.jsonl",
        ],
        repo,
    )
    _run(["git", "commit", "-m", "coord: review-claim WP01"], repo)
    _run(["git", "switch", "main"], repo)

    report = sync_lane_after_coordination_commit(
        repo_root=repo,
        mission_slug="sync-missing-worktree",
        wp_id="WP01",
        coordination_branch=coordination_branch,
    )

    assert report is not None
    assert report.succeeded is True
    assert (worktree / ".git").exists()
    status_path = "kitty-specs/sync-missing-worktree/status.events.jsonl"
    assert not (worktree / status_path).exists()
    _run(["git", "cat-file", "-e", f"{lane_branch}:{status_path}"], repo)


def test_lifecycle_sync_conflict_refuses_and_preserves_lane_state(tmp_path: Path) -> None:
    repo, feature_dir, coordination_branch, lane_branch = _init_repo(
        tmp_path,
        "sync-conflict",
    )
    worktree = repo / ".worktrees" / "sync-conflict-lane-a"

    _run(["git", "switch", coordination_branch], repo)
    (repo / "src" / "shared.txt").write_text("coordination\n", encoding="utf-8")
    _run(["git", "add", "src/shared.txt"], repo)
    _run(["git", "commit", "-m", "coord: update shared"], repo)
    coordination_head = _run(["git", "rev-parse", coordination_branch], repo).stdout.strip()
    _run(["git", "switch", "main"], repo)

    (worktree / "src" / "shared.txt").write_text("lane\n", encoding="utf-8")
    _run(["git", "add", "src/shared.txt"], worktree)
    _run(["git", "commit", "-m", "lane: update shared"], worktree)
    pre_sync_head = _run(["git", "rev-parse", "HEAD"], worktree).stdout.strip()
    pre_sync_body = (worktree / "src" / "shared.txt").read_text(encoding="utf-8")

    with pytest.raises(LaneAutoRebaseSyncError) as exc_info:
        sync_lane_after_coordination_commit(
            repo_root=repo,
            mission_slug="sync-conflict",
            wp_id="WP01",
            coordination_branch=coordination_branch,
        )

    payload = exc_info.value.to_dict()
    assert payload["error_code"] == LANE_AUTO_REBASE_FAILED
    assert payload["lane_worktree_path"] == str(worktree)
    assert payload["coordination_head"] == coordination_head
    assert payload["lane_branch"] == lane_branch

    assert _run(["git", "rev-parse", "HEAD"], worktree).stdout.strip() == pre_sync_head
    assert (worktree / "src" / "shared.txt").read_text(encoding="utf-8") == pre_sync_body
    assert "UU " not in _run(["git", "status", "--porcelain"], worktree).stdout
