"""SC-002 cross-partition scan: no PRIMARY on coord, no COORD on a lane ref.

write-path-integrity WP02 / T013 (SC-002 / NFR-001). A real-git lifecycle scan
that enforces the write-path partition invariant end to end across the two write
seams this mission hardens:

* ``implement`` planning auto-commit -> the coordination ref must carry ZERO
  PRIMARY-partition mission files (``spec.md`` / ``tasks.md`` / ``lanes.json`` /
  ...). ``meta.json`` is EXCLUDED from the count (self-bookkeeping identity
  metadata legitimately co-travels, C-008).
* ``move-task`` lane-deliverable commit -> the lane ref must carry ZERO
  COORD-partition artifacts (``status.events.jsonl`` / ``status.json`` /
  ``acceptance-matrix.json`` / ``issue-matrix.md``).

Classification uses the SAME canonical authorities the write side uses
(:func:`~specify_cli.coordination.coherence.is_coord_residue_churn` /
:func:`~specify_cli.coordination.coherence.is_self_bookkeeping_churn`), so the
scan cannot drift from the routing it guards.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import CommitTarget
from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git
from specify_cli.coordination.coherence import (
    is_coord_residue_churn,
    is_self_bookkeeping_churn,
)
from specify_cli.missions._create import ensure_coordination_branch

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _tree_paths(repo: Path, ref: str) -> list[str]:
    out = _git(repo, "ls-tree", "-r", "--name-only", ref)
    return [p for p in out.splitlines() if p]


def _primary_mission_files_on_ref(repo: Path, ref: str, slug: str) -> list[str]:
    """PRIMARY-partition mission files present on *ref* (``meta.json`` excluded)."""
    prefix = f"kitty-specs/{slug}/"
    offenders: list[str] = []
    for path in _tree_paths(repo, ref):
        if not path.startswith(prefix):
            continue
        if is_self_bookkeeping_churn(path):  # meta.json etc. — exempt (C-008)
            continue
        if not is_coord_residue_churn(path):  # PRIMARY-partition
            offenders.append(path)
    return offenders


def _coord_artifacts_on_ref(repo: Path, ref: str, slug: str) -> list[str]:
    """COORD-partition artifacts present on *ref* (``meta.json`` excluded)."""
    prefix = f"kitty-specs/{slug}/"
    offenders: list[str] = []
    for path in _tree_paths(repo, ref):
        if not path.startswith(prefix):
            continue
        if is_self_bookkeeping_churn(path):
            continue
        if is_coord_residue_churn(path):
            offenders.append(path)
    return offenders


# ---------------------------------------------------------------------------
# SC-002 leg 1: implement planning auto-commit — no PRIMARY on the coord ref.
# ---------------------------------------------------------------------------

_IMPL_SLUG = "wp-integrity-scan-01KZZD69"
_IMPL_ID = "01KZZD69SCAN0000000000000P"
_IMPL_TARGET = "pr/write-path-integrity-scan"


def test_sc002_no_primary_files_on_coord_after_implement(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", _IMPL_TARGET, "main")
    _git(repo, "checkout", "-q", _IMPL_TARGET)

    coord = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=_IMPL_SLUG,
        mission_id=_IMPL_ID,
        target_branch=_IMPL_TARGET,
    )
    coord_branch = coord.branch_name

    feature_dir = repo / "kitty-specs" / _IMPL_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nSubstantive.\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01\n\n- [ ] T001\n", encoding="utf-8")
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _IMPL_ID,
                "mission_slug": _IMPL_SLUG,
                "mid8": _IMPL_ID[:8],
                "mission_type": "software-dev",
                "target_branch": _IMPL_TARGET,
                "created_at": "2026-08-14T00:00:00+00:00",
                "friendly_name": "scan",
                "coordination_branch": coord_branch,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (feature_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": _IMPL_SLUG,
                "mission_id": _IMPL_ID,
                "mission_branch": f"kitty/mission-{_IMPL_SLUG}",
                "target_branch": _IMPL_TARGET,
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-08-14T00:00:00+00:00",
                "computed_from": "scan",
                "planning_artifact_wps": [],
                "planning_commit_sha": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _ensure_planning_artifacts_committed_git(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_slug=_IMPL_SLUG,
        wp_id="WP01",
        planning_branch=_IMPL_TARGET,
        auto_commit=True,
        placement_ref=CommitTarget(ref=coord_branch),
    )

    offenders = _primary_mission_files_on_ref(repo, coord_branch, _IMPL_SLUG)
    assert offenders == [], (
        f"SC-002: PRIMARY-partition files leaked onto the coordination ref "
        f"{coord_branch!r}: {offenders!r}"
    )
    # And they landed on the primary target branch instead (routed, not dropped).
    target_primary = _primary_mission_files_on_ref(repo, _IMPL_TARGET, _IMPL_SLUG)
    assert f"kitty-specs/{_IMPL_SLUG}/lanes.json" in target_primary


# ---------------------------------------------------------------------------
# SC-002 leg 2: move-task lane deliverables — no COORD artifact on the lane ref.
# ---------------------------------------------------------------------------

_MT_SLUG = "wp-integrity-scan-mt-01KZZD69"
_MT_TARGET = "mission/wp-integrity-scan-mt"
_MT_LANE = "kitty/mission-wp-integrity-scan-mt-lane-a"


def test_sc002_no_coord_artifacts_on_lane_after_move_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.tasks_move_task import (
        _MoveTaskState,
        _mt_commit_lane_deliverables,
    )
    from specify_cli.workspace.context import ResolvedWorkspace

    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "keep.txt").write_text("keep\n", encoding="utf-8")
    (repo / "kitty-specs" / _MT_SLUG).mkdir(parents=True)
    (repo / "kitty-specs" / _MT_SLUG / "keep.txt").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", _MT_TARGET, "main")

    lane_wt = repo / ".worktrees" / f"{_MT_SLUG}-lane-a"
    _git(repo, "worktree", "add", "-q", "-b", _MT_LANE, str(lane_wt), _MT_TARGET)
    (lane_wt / "src" / "foo.py").write_text("print('x')\n", encoding="utf-8")
    (lane_wt / "kitty-specs" / _MT_SLUG / "status.events.jsonl").write_text(
        '{"event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV"}\n', encoding="utf-8"
    )
    # Also a coord-residue matrix artifact (not the status log) to widen coverage.
    (lane_wt / "kitty-specs" / _MT_SLUG / "issue-matrix.md").write_text(
        "# Issue Matrix\n", encoding="utf-8"
    )

    resolved = ResolvedWorkspace(
        mission_slug=_MT_SLUG,
        wp_id="WP01",
        execution_mode="worktree",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name=f"{_MT_SLUG}-lane-a",
        worktree_path=lane_wt,
        branch_name=_MT_LANE,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )
    monkeypatch.setattr(_tasks, "resolve_workspace_for_wp", lambda *a, **k: resolved)

    st = _MoveTaskState(
        task_id="WP01",
        to="for_review",
        mission=_MT_SLUG,
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
    st.mission_slug = _MT_SLUG

    _mt_commit_lane_deliverables(st)

    offenders = _coord_artifacts_on_ref(repo, _MT_LANE, _MT_SLUG)
    assert offenders == [], (
        f"SC-002: COORD-partition artifacts leaked onto the lane ref "
        f"{_MT_LANE!r}: {offenders!r}"
    )
    # The genuine code deliverable IS on the lane (routing preserved, not over-dropped).
    assert "src/foo.py" in _tree_paths(repo, _MT_LANE)
