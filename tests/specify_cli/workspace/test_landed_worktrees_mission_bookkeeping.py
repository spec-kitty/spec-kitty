"""``doctor workspaces`` judges a released Mission's lane with the shared landing proof (#7747, WP02).

``consolidate`` prints ``spec-kitty doctor workspaces --prune`` as the remedy for a kept lane. For a
``lanes_with_coord`` lane that synced with the coordination branch, the doctor's plain absorption
proof rated the lane ``not_landed`` / ``CONTENT_NOT_ON_PRIMARY`` once the target reached the remote
primary branch: the lane carries older copies of the Mission's bookkeeping that a squash landing does
not keep in the target's history. The doctor now applies the shared proof to released Mission lanes
only (operator ruling 4, 2026-11-22). Every other worktree keeps the plain proof.

Real repositories with a bare ``origin``; the process probe is injected.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from specify_cli.workspace import landed_worktrees
from specify_cli.workspace.landed_worktrees import Reason, Verdict, WorktreeAssessment, WorktreeVerdict, assess_worktrees, prune_landed
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01ABCDEF" + "0" * 18
_SLUG = "demo-01ABCDEF"
_MD = f"kitty-specs/{_SLUG}"
_COORD = f"kitty/mission-{_SLUG}"
_LANE = f"kitty/mission-{_SLUG}-lane-a"
_WP01 = f"{_MD}/tasks/WP01-x.md"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, message: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
        (cwd / rel).write_text(text, encoding="utf-8")
        _git(cwd, "add", rel)
    _git(cwd, "commit", "-q", "-m", message)


def _idle(paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


def _released(root: Path, **fields: object) -> None:
    """The Mission's ``meta.json`` on the repository root checkout (where the doctor reads it)."""
    meta = {"mission_id": _MISSION_ID, "mission_slug": _SLUG, "target_branch": "main", **fields}
    path = root / _MD / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta), encoding="utf-8")


def _verdict(assessment: WorktreeAssessment, worktree: Path) -> WorktreeVerdict:
    [match] = [v for v in assessment.verdicts if v.path.resolve() == worktree.resolve()]
    return match


@pytest.fixture
def landed(tmp_path: Path) -> tuple[Path, Path]:
    """A ``lanes_with_coord`` lane whose Mission was squash-landed on ``origin/main``; its worktree is still there."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "base", {".gitignore": ".worktrees/\n.kittify/runtime/\n", "base.py": "x = 1\n"})
    _git(root, "remote", "add", "origin", str(origin))
    coord = tmp_path / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    _commit(coord, "tasks", {f"{_MD}/status.json": '{"v": 1}\n', _WP01: "---\nwork_package_id: WP01\n---\nwork\n"})
    lane = root / ".worktrees" / f"{_SLUG}-lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane), _COORD)
    _commit(coord, "WP01 claimed", {f"{_MD}/status.json": '{"v": 2}\n', _WP01: "---\nwork_package_id: WP01\nagent: claude\n---\nwork\n"})
    _git(lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the implement sync
    _commit(lane, "feat(WP01)", {"src/lane.py": "y = 2\n"})
    _commit(coord, "WP01 approved", {f"{_MD}/status.json": '{"v": 3}\n'})
    _git(root, "checkout", "-q", _COORD, "--", "kitty-specs")
    _git(root, "checkout", "-q", _LANE, "--", "src/lane.py")
    _git(root, "commit", "-q", "-m", "squash merge of the Mission")
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    return root, lane


def test_a_released_mission_lane_is_landed_and_pruned(landed: tuple[Path, Path]) -> None:
    root, lane = landed
    _released(root, merged_at="2026-11-23T00:00:00+00:00")
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), lane)
    assert verdict.verdict is Verdict.LANDED, verdict
    [outcome] = prune_landed(root, current_dir=root, probe=_idle)
    assert outcome.removed and outcome.branch_deleted, outcome
    assert not lane.exists()


def test_an_unreleased_mission_lane_stays_report_only(landed: tuple[Path, Path]) -> None:
    root, lane = landed
    _released(root)
    assert _verdict(assess_worktrees(root, current_dir=root, probe=_idle), lane).verdict is Verdict.MISSION_OWNED


def test_a_worktree_that_is_not_a_mission_lane_keeps_the_plain_proof(landed: tuple[Path, Path]) -> None:
    """Ruling 4: the set-aside applies to released Mission lanes only."""
    root, lane = landed
    _released(root, merged_at="2026-11-23T00:00:00+00:00")
    other = root / ".worktrees" / "topic-x"
    _git(root, "worktree", "add", "-q", "-b", "topic/x", str(other), _git(lane, "rev-parse", "HEAD"))
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), other)
    assert verdict.verdict is Verdict.NOT_LANDED and verdict.reason is Reason.CONTENT_NOT_ON_PRIMARY, verdict


def test_a_released_lane_whose_own_commit_edited_its_prompt_is_not_landed(landed: tuple[Path, Path]) -> None:
    root, lane = landed
    _released(root, merged_at="2026-11-23T00:00:00+00:00")
    _commit(lane, "rewrite the prompt", {_WP01: "---\nwork_package_id: WP01\nagent: claude\n---\nwork, rewritten\n"})
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), lane)
    assert verdict.verdict is Verdict.NOT_LANDED and verdict.reason is Reason.CONTENT_NOT_ON_PRIMARY, verdict
    assert prune_landed(root, current_dir=root, probe=_idle) == []
    assert lane.exists()


def test_an_old_git_leaves_a_released_lane_unproven(landed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``merge-tree --write-tree`` the shared proof cannot run: unproven, and the guard gets no proof."""
    root, lane = landed
    _released(root, merged_at="2026-11-23T00:00:00+00:00")
    monkeypatch.setattr(landed_worktrees, "merge_tree_write_tree_available", lambda _repo: False)
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), lane)
    assert verdict.verdict is Verdict.UNPROVEN and verdict.reason is Reason.ABSORPTION_UNSUPPORTED, verdict
    proof = landed_worktrees._absorption_proof(root, _SLUG)
    assert proof(_git(lane, "rev-parse", "HEAD"), "refs/remotes/origin/main") is False


def test_an_old_git_still_proves_a_released_lane_its_merge_landing_reaches(landed: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Review F1: ancestry needs no ``merge-tree``, so a merge-landed lane stays landed and prunable on old git."""
    root, lane = landed
    _released(root, merged_at="2026-11-23T00:00:00+00:00")
    _git(root, "merge", "-q", "--no-ff", "--no-edit", "-X", "ours", _LANE)
    _git(root, "push", "-q", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    monkeypatch.setattr(landed_worktrees, "merge_tree_write_tree_available", lambda _repo: False)
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), lane)
    assert verdict.verdict is Verdict.LANDED, verdict
    proof = landed_worktrees._absorption_proof(root, _SLUG)
    assert proof(_git(lane, "rev-parse", "HEAD"), "refs/remotes/origin/main") is True
    [outcome] = prune_landed(root, current_dir=root, probe=_idle)
    assert outcome.removed and outcome.branch_deleted, outcome


def test_a_detached_head_has_no_mission(landed: tuple[Path, Path]) -> None:
    root, _lane = landed
    assert landed_worktrees._lane_mission_slug(root, None) is None
