"""``accept --mode pr`` cleans up absorbed lanes before the PR merges (S5, WP16, FR-036, SC-006).

After a committed pr-mode acceptance, every code lane whose tip the pushed PR head
(``refs/remotes/<remote>/<branch>``) absorbs is removed through the lane-cleanup module
bound to the landed-removal guard; a lane the pushed head does not carry is kept and
reported (``NOT_LANDED_ON_NAMED_REMOTE``). No raw ``git worktree remove`` /
``git branch -d`` advice is printed in pr mode.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from specify_cli.acceptance import _build_acceptance_instructions, pr_mode_lane_cleanup
from specify_cli.consolidation.lane_cleanup import LaneCleanupOutcome
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.git.destructive_guard import NOT_LANDED_ON_NAMED_REMOTE
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import predict_lane_worktree
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01ABCDEF"
_PR_HEAD = f"kitty/mission-{_SLUG}"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, name: str, content: str) -> None:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", f"add {name}")


def _idle(paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


def _manifest() -> LanesManifest:
    lanes = [
        ExecutionLane(lane_id=lane_id, wp_ids=(f"WP0{i + 1}",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
        for i, lane_id in enumerate(("lane-a", "lane-b"))
    ]
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_PR_HEAD,
        target_branch="main",
        lanes=lanes,
        computed_at="2026-11-06T00:00:00+00:00",
        computed_from="test",
    )


@pytest.fixture
def mission(tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    """lane-a was folded into the pushed PR head; lane-b was never pushed."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _commit(root, "base.py", "x = 1\n")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-q", "-u", "origin", "main")
    manifest = _manifest()
    feature_dir = root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    write_lanes_json(feature_dir, manifest)
    _git(root, "branch", _PR_HEAD)
    worktrees: dict[str, Path] = {}
    for lane_id in ("lane-a", "lane-b"):
        path = Path(predict_lane_worktree(root, _SLUG, lane_id)[0])
        _git(root, "worktree", "add", "-q", "-b", lane_created_branch(manifest, lane_id), str(path), _PR_HEAD)
        _commit(path, f"{lane_id}.py", f"{lane_id} = 1\n")
        worktrees[lane_id] = path
    head = root.parent / "pr-head"
    _git(root, "worktree", "add", "-q", str(head), _PR_HEAD)
    _git(head, "merge", "-q", "--no-ff", "-m", "fold lane-a", lane_created_branch(manifest, "lane-a"))
    _git(head, "push", "-q", "origin", _PR_HEAD)
    _git(root, "fetch", "-q", "origin")
    return root, feature_dir, worktrees


def test_pr_mode_removes_absorbed_lanes_before_pr_merge(mission: tuple[Path, Path, dict[str, Path]]) -> None:
    root, feature_dir, worktrees = mission
    report = pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert report is not None
    by_lane = {result.item.lane_id: result for result in report.results}
    assert by_lane["lane-a"].outcome is LaneCleanupOutcome.REMOVED
    assert not worktrees["lane-a"].exists()
    # The PR has not merged: origin/main still lacks the lane.
    assert subprocess.run(["git", "merge-base", "--is-ancestor", _PR_HEAD, "origin/main"], cwd=root, check=False).returncode != 0


def test_pr_mode_keeps_unpushed_lane_reported(mission: tuple[Path, Path, dict[str, Path]]) -> None:
    root, feature_dir, worktrees = mission
    report = pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert report is not None
    kept = {result.item.lane_id: result for result in report.kept}
    assert kept["lane-b"].code == NOT_LANDED_ON_NAMED_REMOTE
    assert worktrees["lane-b"].exists()
    assert any("lane-b" in line and NOT_LANDED_ON_NAMED_REMOTE in line for line in report.render_lines())


def test_no_raw_worktree_remove_advice(tmp_path: Path) -> None:
    summary = cast(Any, SimpleNamespace(feature=_SLUG, worktree_root=tmp_path / "lane", primary_repo_root=tmp_path))
    instructions, cleanup = _build_acceptance_instructions(summary, "pr", _PR_HEAD, False)
    text = " ".join(instructions + cleanup)
    assert "git worktree remove" not in text
    assert "git branch -d" not in text
    assert "spec-kitty doctor workspaces --prune" in text


@pytest.mark.parametrize("mode", ["local", "checklist"])
def test_local_mode_no_raw_git_removal_advice(tmp_path: Path, mode: str) -> None:
    # #7327: local/checklist-mode cleanup advice routes removal through the CLI's
    # guarded cleanup, never a raw ``git worktree remove`` / ``git branch -d`` recipe.
    summary = cast(Any, SimpleNamespace(feature=_SLUG, worktree_root=tmp_path / "lane", primary_repo_root=tmp_path))
    instructions, cleanup = _build_acceptance_instructions(summary, mode, "kitty/mission-demo-01ABCDEF", False)
    text = " ".join(instructions + cleanup)
    assert "git worktree remove" not in text
    assert "git branch -d" not in text
    assert "spec-kitty doctor workspaces --prune" in text


def _write_meta(feature_dir: Path, **fields: object) -> None:
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, **fields}), encoding="utf-8")


@pytest.mark.parametrize("flag", [True, "true"], ids=["boolean", "non-boolean-fails-toward-retention"])
def test_pr_mode_honours_meta_lane_retention(mission: tuple[Path, Path, dict[str, Path]], flag: object) -> None:
    root, feature_dir, worktrees = mission
    _write_meta(feature_dir, retain_worktrees=flag, retain_branches=flag)
    report = pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert report is not None
    by_lane = {result.item.lane_id: result for result in report.results}
    assert by_lane["lane-a"].outcome is LaneCleanupOutcome.RETAINED_BY_POLICY
    assert worktrees["lane-a"].exists()
    assert _git(root, "branch", "--list", lane_created_branch(_manifest(), "lane-a"))


def test_pr_mode_corrupt_meta_removes_nothing(mission: tuple[Path, Path, dict[str, Path]]) -> None:
    root, feature_dir, worktrees = mission
    (feature_dir / "meta.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(MissionMetaReadError):
        pr_mode_lane_cleanup(root, feature_dir, _PR_HEAD, probe=_idle)
    assert worktrees["lane-a"].exists()
