"""#2549 reproduction + Seam-A pin: move-task lane deliverables never leak coord state.

write-path-integrity WP02 / T012 (FR-003). The mission's #2549 slice: determine
which of ``move-task``'s two commit mechanisms can leak a coord-partition
artifact (``status.events.jsonl`` / ``status.json`` / ``acceptance-matrix.json``
/ ``issue-matrix.md``) onto the LANE branch, then close it.

Reproduction verdict (encoded by ``test_..._leak_surface_is_real`` below):
``_mt_commit_lane_deliverables`` commits lane deliverables through a RAW
``safe_commit`` on the lane branch, BYPASSING the kind-aware
``commit_for_mission`` classifier and the ``BookkeepingTransaction`` Seam-A
guard. Its only filter, ``_filter_runtime_state_paths``, strips ``.spec-kitty/``
/ ``.kittify/`` runtime dirs -- NOT coord-partition mission artifacts. So a
coord-residue file surfacing in the lane worktree's ``git status`` (the residual
``--force`` leak surface) WOULD be committed onto the lane ref. The port-based
``commit_status`` path already wraps ``commit_for_mission`` and is guarded, so
the leak is the raw-deliverable path -- routed through Seam A here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "mt-2549-repro-01KZZD69"
_TARGET_BRANCH = "mission/mt-2549"
_LANE_BRANCH = "kitty/mission-mt-2549-lane-a"
_STATUS_REL = f"kitty-specs/{_MISSION_SLUG}/status.events.jsonl"
_DELIVERABLE_REL = "src/foo.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _make_lane_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Build a repo with a real lane worktree carrying a coord-residue status file
    AND a genuine code deliverable, both dirty/untracked. Returns (repo, lane_wt)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    # Pre-create the src/ and kitty-specs/<slug>/ dirs as TRACKED (a real lane
    # already carries kitty-specs/ and the project's src tree), so the new files
    # added in the lane below surface INDIVIDUALLY in ``git status --porcelain``
    # rather than being collapsed under an untracked parent directory.
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "keep.txt").write_text("keep\n", encoding="utf-8")
    (repo / "kitty-specs" / _MISSION_SLUG).mkdir(parents=True, exist_ok=True)
    (repo / "kitty-specs" / _MISSION_SLUG / "keep.txt").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", _TARGET_BRANCH, "main")

    lane_wt = repo / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    _git(repo, "worktree", "add", "-q", "-b", _LANE_BRANCH, str(lane_wt), _TARGET_BRANCH)

    # A genuine code deliverable (PRIMARY) — must be committed to the lane.
    (lane_wt / _DELIVERABLE_REL).write_text("print('work')\n", encoding="utf-8")
    # A coord-partition artifact that surfaced in the lane worktree (the #2549
    # leak surface) — must NEVER be committed to the lane branch.
    (lane_wt / _STATUS_REL).write_text(
        '{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}\n', encoding="utf-8"
    )
    return repo, lane_wt


def test_mt_2549_leak_surface_is_real(tmp_path: Path) -> None:
    """Non-vacuity: the coord-residue status file genuinely reaches the raw
    deliverable set (via git status + the runtime-state filter), i.e. the leak
    surface exists. Only the Seam-A drop (the next test) stops it landing on the
    lane branch."""
    from specify_cli.cli.commands.agent.tasks_move_task import _lane_deliverable_paths
    from kernel.git import status_entries
    from specify_cli.cli.commands.agent.tasks_shared import _filter_runtime_state_paths

    _repo, lane_wt = _make_lane_worktree(tmp_path)
    filtered = _filter_runtime_state_paths(status_entries(lane_wt, untracked=None))
    unguarded = {p.relative_to(lane_wt).as_posix() for p in _lane_deliverable_paths(lane_wt, filtered)}
    # The runtime-state deny-list does NOT strip the coord-partition status file:
    # it reaches the raw deliverable set. THIS is the #2549 leak surface.
    assert _STATUS_REL in unguarded, (
        "expected the coord-residue status file to reach the raw deliverable set "
        f"(the #2549 leak surface); got {sorted(unguarded)!r}"
    )
    assert _DELIVERABLE_REL in unguarded


def test_mt_2549_status_never_committed_on_lane_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the REAL ``_mt_commit_lane_deliverables`` and assert the resulting
    lane-branch commit carries the code deliverable but NOT the coord-residue
    status file (Seam-A closes the #2549 leak). Pre-fix this commit would include
    ``status.events.jsonl`` on the lane ref."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import (
        _MoveTaskState,
        _mt_commit_lane_deliverables,
    )
    from specify_cli.workspace.context import ResolvedWorkspace

    repo, lane_wt = _make_lane_worktree(tmp_path)

    resolved = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name=f"{_MISSION_SLUG}-lane-a",
        worktree_path=lane_wt,
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
        json_output=True,
    )
    st.main_repo_root = repo
    st.mission_slug = _MISSION_SLUG

    _mt_commit_lane_deliverables(st)

    committed = set(
        _git(lane_wt, "show", "--name-only", "--pretty=format:", "HEAD").splitlines()
    )
    assert _DELIVERABLE_REL in committed, (
        f"the genuine code deliverable must be committed to the lane; got {committed!r}"
    )
    assert _STATUS_REL not in committed, (
        "#2549 regression: a coord-partition status file was committed onto the "
        f"lane branch {_LANE_BRANCH!r}: {committed!r}"
    )


def test_repo_root_wp_never_auto_commits_arbitrary_dirty_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A1a (#5100): for a repo-root WP with no owned checkout, ``move-task
    --to for_review`` must NOT stage every dirty path of the repository-root
    checkout (stray ``.env.local``, unrelated files) as "WP deliverables"."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import (
        _MoveTaskState,
        _mt_commit_lane_deliverables,
    )
    from specify_cli.workspace.context import ResolvedWorkspace

    repo, lane_wt = _make_lane_worktree(tmp_path)
    # A single_branch repo has no lane worktree; drop the fixture's so its untracked
    # ``.worktrees/`` dir cannot make safe_commit refuse for an unrelated reason.
    _git(repo, "worktree", "remove", "--force", str(lane_wt))
    _git(repo, "checkout", "-q", "-b", "work")  # an UNPROTECTED branch, so protection cannot mask the sweep
    (repo / ".env.local").write_text("SECRET=1\n", encoding="utf-8")
    (repo / _DELIVERABLE_REL).write_text("print('repo root work')\n", encoding="utf-8")
    head_before = _git(repo, "rev-parse", "HEAD")
    branch = _git(repo, "branch", "--show-current")

    resolved = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        execution_mode="direct_repo",
        mode_source="test",
        resolution_kind="repo_root",
        workspace_name="repo-root",
        worktree_path=repo,
        branch_name=branch,
        lane_id="lane-planning",
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

    _mt_commit_lane_deliverables(st)

    assert _git(repo, "rev-parse", "HEAD") == head_before, "no auto-commit may land for a repo-root WP"
    assert ".env.local" not in _git(repo, "ls-files")
