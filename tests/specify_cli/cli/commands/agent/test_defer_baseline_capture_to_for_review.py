"""#6062: baseline capture is deferred OFF the ``agent action implement`` claim
path onto a capture-if-missing step on the ``in_progress -> for_review`` edge.

A claim must return promptly after materializing the lane worktree and moving
the WP to ``doing``; running the project's test suite synchronously there (and
holding a lock scoped to the ``for_review`` transition) is the #6062 hang. The
baseline is still needed by the pre-review regression gate, so it is captured
lazily, capture-if-missing, right before the gate loads it
(``tasks_move_task_gates._mt_capture_baseline_if_missing``).

These tests pin the new helper's three behaviours:
- it captures on the ``in_progress -> for_review`` edge when the artifact is absent;
- it is a no-op when the artifact already exists (idempotent);
- it is a no-op off that edge.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent import tasks_move_task_gates
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
from specify_cli.status import Lane

pytestmark = pytest.mark.fast

_WP_SLUG = "WP01-defer-baseline"
_MISSION = "defer-baseline-capture"


def _location(primary_dir: Path) -> tuple[Path, str, Path]:
    return primary_dir, _WP_SLUG, primary_dir / "tasks" / _WP_SLUG / "baseline-tests.json"


def _make_state(*, old_lane: Lane, target_lane: Lane, feature_dir: Path) -> _MoveTaskState:
    st = _MoveTaskState(
        task_id="WP01",
        to=target_lane.value,
        mission=_MISSION,
        agent="claude",
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
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        skip_pre_review_gate=False,
    )
    st.old_lane = old_lane
    st.target_lane = target_lane
    st.main_repo_root = feature_dir.parent
    st.target_branch = "main"
    st.mission_slug = _MISSION
    st.feature_dir = feature_dir
    st.wp = SimpleNamespace(path=Path(f"{_WP_SLUG}.md"), frontmatter="")
    return st


@pytest.fixture
def capture_spy(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Spy the lazy import target ``workflow_executor.capture_and_commit_baseline``."""
    calls: list[dict[str, object]] = []

    def _spy(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow_executor.capture_and_commit_baseline",
        _spy,
    )
    return calls


def test_captures_on_for_review_edge_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture_spy: list[dict[str, object]]) -> None:
    primary_dir = tmp_path / "kitty-specs" / _MISSION
    primary_dir.mkdir(parents=True)
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_baseline_artifact_location",
        lambda _st: _location(primary_dir),
    )
    st = _make_state(old_lane=Lane.IN_PROGRESS, target_lane=Lane.FOR_REVIEW, feature_dir=primary_dir)

    tasks_move_task_gates._mt_capture_baseline_if_missing(st)

    assert len(capture_spy) == 1, "capture must run on in_progress->for_review when the artifact is absent"
    kwargs = capture_spy[0]
    assert kwargs["feature_dir"] == primary_dir
    assert kwargs["wp_slug"] == _WP_SLUG
    assert kwargs["target_branch"] == "main"


def test_noop_when_baseline_already_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture_spy: list[dict[str, object]]) -> None:
    primary_dir = tmp_path / "kitty-specs" / _MISSION
    artifact = primary_dir / "tasks" / _WP_SLUG / "baseline-tests.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_baseline_artifact_location",
        lambda _st: _location(primary_dir),
    )
    st = _make_state(old_lane=Lane.IN_PROGRESS, target_lane=Lane.FOR_REVIEW, feature_dir=primary_dir)

    tasks_move_task_gates._mt_capture_baseline_if_missing(st)

    assert capture_spy == [], "capture must be a no-op when the baseline artifact already exists (idempotent)"


def test_noop_off_the_for_review_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture_spy: list[dict[str, object]]) -> None:
    primary_dir = tmp_path / "kitty-specs" / _MISSION
    primary_dir.mkdir(parents=True)
    # Would capture if reached; prove the edge guard returns first.
    monkeypatch.setattr(
        tasks_move_task_gates,
        "_mt_baseline_artifact_location",
        lambda _st: _location(primary_dir),
    )
    st = _make_state(old_lane=Lane.PLANNED, target_lane=Lane.CLAIMED, feature_dir=primary_dir)

    tasks_move_task_gates._mt_capture_baseline_if_missing(st)

    assert capture_spy == [], "capture must not run off the in_progress->for_review edge"


def test_capture_is_fail_open_when_resolution_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture_spy: list[dict[str, object]]) -> None:
    """#6062 fail-open: a capture-prep fault (e.g. an ambiguous wp-slug or a
    malformed meta.json in the placement seam) must NEVER refuse the for_review
    move — it degrades to no baseline, matching the LOAD-side three-catch."""

    def _boom(_st: object) -> tuple[Path, str, Path]:
        raise RuntimeError("ambiguous wp slug")

    monkeypatch.setattr(tasks_move_task_gates, "_mt_baseline_artifact_location", _boom)
    st = _make_state(old_lane=Lane.IN_PROGRESS, target_lane=Lane.FOR_REVIEW, feature_dir=tmp_path / "kitty-specs" / _MISSION)

    # Must not raise: the fault is swallowed (logged), the move proceeds, and no
    # capture is attempted. Pre-fix (resolution outside any guard) this raised
    # and the for_review transition was refused.
    tasks_move_task_gates._mt_capture_baseline_if_missing(st)

    assert capture_spy == [], "a resolution fault must skip capture, not attempt it"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def test_captures_at_the_lane_fork_point_not_the_advanced_base_tip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture_spy: list[dict[str, object]]) -> None:
    """#6062 review fold: the baseline must describe the base the lane FORKED from.

    On a busy Mission the base branch keeps moving between the claim and the
    ``for_review`` move. Capturing at the base tip would suppress a sibling WP's
    merged failure as "pre-existing" and report a since-fixed base failure as a
    regression. The capture ref must be the lane/base merge-base.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("fork point\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fork point")
    fork_sha = _git(repo, "rev-parse", "HEAD")
    lane = tmp_path / "lane"
    _git(repo, "worktree", "add", "-q", "-b", "lane", str(lane))
    # The base advances AFTER the fork with a new failing test.
    (repo / "test_sibling_regression.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "sibling WP lands a failing test")
    assert _git(repo, "rev-parse", "main") != fork_sha

    primary_dir = repo / "kitty-specs" / _MISSION
    primary_dir.mkdir(parents=True)
    monkeypatch.setattr(tasks_move_task_gates, "_mt_baseline_artifact_location", lambda _st: _location(primary_dir))
    monkeypatch.setattr(tasks_move_task_gates, "_mt_resolve_pre_review_workspace", lambda _st: lane)
    st = _make_state(old_lane=Lane.IN_PROGRESS, target_lane=Lane.FOR_REVIEW, feature_dir=primary_dir)
    st.main_repo_root = repo

    tasks_move_task_gates._mt_capture_baseline_if_missing(st)

    assert len(capture_spy) == 1
    captured_ref = str(capture_spy[0]["target_branch"])
    assert _git(repo, "rev-parse", f"{captured_ref}^{{commit}}") == fork_sha
    shown = subprocess.run(["git", "cat-file", "-e", f"{captured_ref}:test_sibling_regression.py"], cwd=repo, check=False)
    assert shown.returncode != 0, "the baseline ref must not contain tests that landed on the base after the fork"
