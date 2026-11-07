"""FR-042: lane commits Spec Kitty makes leave the Mission status files unstaged.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10 (S6, restated ruling 3):
lanes never change status. ``move-task --to for_review``'s deliverable
auto-commit commits the lane's deliverables and never the Mission's
``status.events.jsonl`` / ``status.json``, whatever the topology. The status
files are left out by pathspec, never removed from the lane index (C-008): the
fork-time blob stays in lane history. Paired control: the deliverable lands.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "s6commit-01M6QY1M"
_LANE_BRANCH = "kitty/mission-s6commit-01M6QY1M-lane-a"
_EVENTS = f"kitty-specs/{_MISSION_SLUG}/status.events.jsonl"
_SNAPSHOT = f"kitty-specs/{_MISSION_SLUG}/status.json"
_OTHER_EVENTS = "kitty-specs/another-mission/status.events.jsonl"
_DELIVERABLE = "src/feature_code.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _make_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", _LANE_BRANCH)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    for rel in (_EVENTS, _SNAPSHOT, _OTHER_EVENTS):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("fork-time\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fork-time copy")
    for rel in (_EVENTS, _SNAPSHOT, _OTHER_EVENTS):
        (repo / rel).write_text("fork-time\nlane-written\n", encoding="utf-8")
    (repo / _DELIVERABLE).parent.mkdir(parents=True, exist_ok=True)
    (repo / _DELIVERABLE).write_text("print('deliverable')\n", encoding="utf-8")
    return repo


def _drive_collector(repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """Run the real collector against ``repo``; return (head_before, head_after)."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import (
        _MoveTaskState,
        _mt_commit_lane_deliverables,
    )
    from specify_cli.workspace.context import ResolvedWorkspace

    resolved = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name=f"{_MISSION_SLUG}-lane-a",
        worktree_path=repo,
        branch_name=_LANE_BRANCH,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )
    monkeypatch.setattr(_tasks, "resolve_workspace_for_wp", lambda *a, **k: resolved)
    st = _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=_MISSION_SLUG,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=True,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=True,
        json_output=False,
    )
    st.main_repo_root = repo
    st.mission_slug = _MISSION_SLUG
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    _mt_commit_lane_deliverables(st)
    return head_before, _git(repo, "rev-parse", "HEAD").strip()


def test_deliverable_autocommit_never_stages_status_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_fixture(tmp_path)

    head_before, head_after = _drive_collector(repo, monkeypatch)

    assert head_after != head_before, "paired control: the deliverable is committed"
    committed = {line for line in _git(repo, "show", "--name-only", "--pretty=format:", head_after).splitlines() if line.strip()}
    assert committed == {_DELIVERABLE}, f"no Mission status file may ride a lane commit; got {sorted(committed)!r}"
    tracked = set(_git(repo, "ls-files").splitlines())
    assert {_EVENTS, _SNAPSHOT, _OTHER_EVENTS} <= tracked, "the fork-time blobs stay in the lane index (C-008)"
    assert not _git(repo, "diff", "--cached", "--name-only").strip(), "nothing is left staged"
    dirty = _git(repo, "status", "--porcelain").splitlines()
    assert {line[3:] for line in dirty} == {_EVENTS, _SNAPSHOT, _OTHER_EVENTS}, dirty
