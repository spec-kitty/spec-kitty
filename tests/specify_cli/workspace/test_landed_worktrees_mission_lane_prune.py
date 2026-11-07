"""``doctor workspaces --prune`` as the backstop for a released Mission's lanes (S5, WP16, FR-039, NFR-005).

A lane of a consolidated (``merged_at``) or pr-accepted Mission is a removal candidate
under the same proofs as any landed worktree, when no consolidation record is active
and no retention is declared. Otherwise it stays report-only (``mission_owned``).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from specify_cli.workspace.landed_worktrees import Reason, Verdict, WorktreeAssessment, WorktreeVerdict, assess_worktrees, prune_landed
from specify_cli.workspace.process_probe import ProcessProbeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01ABCDEF" + "0" * 18
_SLUG = "demo-01ABCDEF"
_LANE = f"kitty/mission-{_SLUG}-lane-a"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, name: str, content: str) -> None:
    (cwd / name).parent.mkdir(parents=True, exist_ok=True)
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", f"add {name}")


def _idle(paths: Sequence[Path]) -> ProcessProbeResult:
    return ProcessProbeResult(available=True)


def _meta(root: Path, **fields: object) -> None:
    meta = {"mission_id": _MISSION_ID, "mission_slug": _SLUG, "target_branch": "main", **fields}
    path = root / "kitty-specs" / _SLUG / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repo whose Mission lane landed on ``origin/main``; the lane worktree is still there."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".worktrees/\n.kittify/runtime/\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _commit(root, "base.py", "x = 1\n")
    _git(root, "remote", "add", "origin", str(origin))
    worktree = root / ".worktrees" / f"{_SLUG}-lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(worktree))
    _commit(worktree, "lane.py", "y = 2\n")
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate", _LANE)
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    return root, worktree


def _verdict(assessment: WorktreeAssessment, worktree: Path) -> WorktreeVerdict:
    [match] = [v for v in assessment.verdicts if v.path.resolve() == worktree.resolve()]
    return match


def test_prune_candidates_consolidated_mission_lane(repo: tuple[Path, Path]) -> None:
    root, worktree = repo
    _meta(root, merged_at="2026-11-06T00:00:00+00:00")
    assert _verdict(assess_worktrees(root, current_dir=root, probe=_idle), worktree).verdict is Verdict.LANDED
    [outcome] = prune_landed(root, current_dir=root, probe=_idle)
    assert outcome.removed and outcome.branch_deleted
    assert not worktree.exists()


def test_pr_accepted_mission_lane_is_a_candidate(repo: tuple[Path, Path]) -> None:
    root, worktree = repo
    _meta(root, accepted_at="2026-11-06T00:00:00+00:00", acceptance_mode="pr")
    assert _verdict(assess_worktrees(root, current_dir=root, probe=_idle), worktree).verdict is Verdict.LANDED


def test_active_record_keeps_lane_report_only(repo: tuple[Path, Path]) -> None:
    root, worktree = repo
    _meta(root, merged_at="2026-11-06T00:00:00+00:00")
    record = root / ".kittify" / "runtime" / "merge" / _MISSION_ID / "state.json"
    record.parent.mkdir(parents=True)
    record.write_text("{}", encoding="utf-8")
    verdict = _verdict(assess_worktrees(root, current_dir=root, probe=_idle), worktree)
    assert verdict.verdict is Verdict.MISSION_OWNED and verdict.reason is Reason.MISSION_LANE
    assert prune_landed(root, current_dir=root, probe=_idle) == []
    assert worktree.exists()


def test_retained_mission_keeps_lane_report_only(repo: tuple[Path, Path]) -> None:
    root, worktree = repo
    _meta(root, merged_at="2026-11-06T00:00:00+00:00", retain_worktrees=True)
    assert _verdict(assess_worktrees(root, current_dir=root, probe=_idle), worktree).verdict is Verdict.MISSION_OWNED


def test_unreleased_mission_keeps_lane_report_only(repo: tuple[Path, Path]) -> None:
    root, worktree = repo
    _meta(root)
    assert _verdict(assess_worktrees(root, current_dir=root, probe=_idle), worktree).verdict is Verdict.MISSION_OWNED


def test_prune_second_run_changes_nothing(repo: tuple[Path, Path]) -> None:
    root, _worktree = repo
    _meta(root, merged_at="2026-11-06T00:00:00+00:00")
    assert len(prune_landed(root, current_dir=root, probe=_idle)) == 1
    assert prune_landed(root, current_dir=root, probe=_idle) == []
    assert not any(v.removable for v in assess_worktrees(root, current_dir=root, probe=_idle).verdicts)
