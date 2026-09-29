"""``mission close --discard`` never deletes or expects a single_branch target (#5100 B1).

For an unprotected single_branch mission ``lanes.json`` records
``mission_branch == target_branch`` (the user's own branch). Discard must not
treat it as a minted mission branch: deleting it destroys the user's work, and
expecting it deleted makes the residual check report a spurious leak.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands import mission_type
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "sb-discard-01ABCDEF"
_MINTED = "kitty/mission-sb-discard-01ABCDEF"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _exists(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"], capture_output=True).returncode == 0


def _manifest(mission_branch: str, target_branch: str) -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-planning", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF000000000000000000",
        mission_branch=mission_branch,
        target_branch=target_branch,
        lanes=[lane],
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def _repo(tmp_path: Path, target: str, *, mint: bool) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed").write_text("s\n", encoding="utf-8")
    _git(repo, "add", "seed")
    _git(repo, "commit", "-q", "-m", "seed")
    for branch in {target, _MINTED} if mint else {target}:
        if branch != "main":
            _git(repo, "branch", branch)
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    return repo, feature_dir


def test_unprotected_single_branch_discard_keeps_target_branch_and_commits(tmp_path: Path) -> None:
    repo, feature_dir = _repo(tmp_path, "feat/x", mint=False)
    _git(repo, "checkout", "-q", "feat/x")
    (repo / "work").write_text("unpushed\n", encoding="utf-8")
    _git(repo, "add", "work")
    _git(repo, "commit", "-q", "-m", "unpushed work")
    tip = _git(repo, "rev-parse", "feat/x")
    _git(repo, "checkout", "-q", "main")  # HEAD elsewhere: -D would succeed
    manifest = _manifest("feat/x", "feat/x")
    write_lanes_json(feature_dir, manifest)

    mission_type._delete_lane_branches(repo, _SLUG, manifest)

    assert _exists(repo, "feat/x")
    assert _git(repo, "rev-parse", "feat/x") == tip
    assert "feat/x" not in mission_type._expected_discard_branches(feature_dir, _SLUG, feature_dir / "meta.json")


def test_unprotected_single_branch_discard_succeeds_with_head_on_target(tmp_path: Path) -> None:
    repo, feature_dir = _repo(tmp_path, "feat/x", mint=False)
    _git(repo, "checkout", "-q", "feat/x")
    manifest = _manifest("feat/x", "feat/x")
    write_lanes_json(feature_dir, manifest)

    mission_type._delete_lane_branches(repo, _SLUG, manifest)

    # No spurious leak: the residual check must not expect the target branch gone.
    leaked = [b for b in mission_type._expected_discard_branches(feature_dir, _SLUG, feature_dir / "meta.json") if _exists(repo, b)]
    assert leaked == []
    assert _exists(repo, "feat/x")


def test_protected_mint_branch_is_still_deleted_on_discard(tmp_path: Path) -> None:
    repo, feature_dir = _repo(tmp_path, "main", mint=True)
    manifest = _manifest(_MINTED, "main")
    write_lanes_json(feature_dir, manifest)

    assert _MINTED in mission_type._expected_discard_branches(feature_dir, _SLUG, feature_dir / "meta.json")
    mission_type._delete_lane_branches(repo, _SLUG, manifest)

    assert not _exists(repo, _MINTED)
    assert _exists(repo, "main")


def test_discard_reports_only_branches_it_actually_deleted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An unprotected single_branch discard deletes nothing and must not claim it did (#5100)."""
    repo, feature_dir = _repo(tmp_path, "feat/x", mint=False)
    manifest = _manifest("feat/x", "feat/x")
    write_lanes_json(feature_dir, manifest)

    mission_type._delete_lane_branches(repo, _SLUG, manifest)

    assert "Deleted" not in capsys.readouterr().out


def test_discard_reports_the_mission_branch_it_deleted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, feature_dir = _repo(tmp_path, "main", mint=True)
    manifest = _manifest(_MINTED, "main")
    write_lanes_json(feature_dir, manifest)

    mission_type._delete_lane_branches(repo, _SLUG, manifest)

    out = capsys.readouterr().out
    assert "Deleted mission/coordination branch" in out
    assert "lane branch(es)" not in out, "the planning lane owns no branch"
