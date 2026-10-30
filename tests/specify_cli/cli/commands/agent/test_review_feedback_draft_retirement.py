"""#6632 regression: a review rejection must not leave its feedback draft behind.

The review prompt tells a rejecting reviewer to write feedback to
``kitty-specs/<mission>/tasks/<wp-dir>/review-feedback-N.md`` and promises the rejection command
"handles all file updates automatically". The command wrote and committed ``review-cycle-N.md`` and
left that source untracked, so the work package's next ``move-task --to for_review`` refused with
``Blocking: 1 uncommitted file(s)`` naming the tool's own output.

This module drives the real ``move-task`` Typer app end to end and — deliberately — does **not** stub
``_validate_ready_for_review``: that gate *is* the reported defect, and the sibling
``test_move_task_reject_fix_approve_cycle.py`` stubs it, which is why the suite never saw this.

Cases:

* the printed rejection command retires the draft, leaves the mission directory clean, and the next
  ``--to for_review`` passes Check 1 (SC-001);
* the draft is kept — never destroyed — when the record is not durable, when the reviewer already
  committed it, or when it lies outside the mission directory (SC-002, FR-002/FR-003/FR-004);
* the recorded ``review-cycle-1.md`` still holds the reviewer's text verbatim (SC-003).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.review.cycle import review_feedback_source_path
from specify_cli.status import Lane
from specify_cli.status.models import StatusEvent
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import commit_lane_implementation, write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "001-review-feedback-clean"
WP_SLUG = "WP01-core"
_WP_FRONTMATTER = (
    "---\nwork_package_id: WP01\ntitle: Core\nowned_files:\n  - src/**\n"
    "agent: reviewer\nsubtasks: []\ntracker_refs: []\ndependencies: []\n---\n\n# WP01\n\n## Activity Log\n"
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _seed_hops(feature_dir: Path, hops: list[tuple[Lane, Lane]], *, day: str) -> None:
    for index, (from_lane, to_lane) in enumerate(hops, start=1):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{day}-{index}",
                mission_slug=MISSION_SLUG,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"{day}T00:00:0{index}+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
            ),
        )


def _dirty_paths(repo: Path, scope: str) -> list[str]:
    """Paths ``git status --porcelain`` reports under *scope*, without the status prefix."""
    raw = _git(repo, "status", "--porcelain", scope)
    return [line[3:] for line in raw.splitlines() if line.strip()]


def _build_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, auto_commit: bool = True) -> tuple[Path, Path]:
    """Materialise a lanes mission with WP01 in ``in_review``, ready for a rejection.

    The shape mirrors the reproduction in the Mission's ``research/repro-6632.py``: a seed commit, a
    ``lanes.json`` recording that commit as the planning commit, a real lane implementation commit (so
    the evidence window is computable), and an event log driven to ``in_review``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "6632@example.invalid")
    _git(repo, "config", "user.name", "Review Feedback")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "--allow-empty", "-m", "planning base")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text(
        f"auto_commit: {'true' if auto_commit else 'false'}\nprotection:\n  protected_branches: []\n",
        encoding="utf-8",
    )
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01 - Core\n", encoding="utf-8")
    (tasks_dir / f"{WP_SLUG}.md").write_text(_WP_FRONTMATTER, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "seed review feedback fixture")
    commit_lane_implementation(repo, feature_dir)
    _seed_hops(
        feature_dir,
        [
            (Lane.GENESIS, Lane.PLANNED),
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
            (Lane.FOR_REVIEW, Lane.IN_REVIEW),
        ],
        day="2026-01-01",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: repo)
    monkeypatch.setattr(tasks_module, "get_mission_type", lambda *_a, **_k: "software-dev")
    return repo, feature_dir


def _advertised_draft(feature_dir: Path, cycle: int = 1) -> Path:
    """The draft path the review prompt prints — taken from the owning helper, never hand-joined."""
    return review_feedback_source_path(feature_dir / "tasks" / WP_SLUG, cycle)


def _reject(draft: Path) -> object:
    """Run the rejection command the review prompt prints."""
    return CliRunner().invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "planned",
            "--review-feedback-file",
            str(draft),
            "--mission",
            MISSION_SLUG,
            "--agent",
            "reviewer",
        ],
    )


def _resubmit() -> object:
    """The implementer's next move after rework: the one that used to be blocked."""
    return CliRunner().invoke(
        tasks_app,
        ["move-task", "WP01", "--to", "for_review", "--mission", MISSION_SLUG, "--agent", "reviewer"],
    )


def test_rejection_retires_the_draft_and_the_next_for_review_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001/SC-003: the reported dead end, end to end through the real CLI."""
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)
    draft = _advertised_draft(feature_dir)
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("**Issue 1**: fix the off-by-one in the tally.\n", encoding="utf-8")

    rejected = _reject(draft)
    assert rejected.exit_code == 0, rejected.output  # type: ignore[attr-defined]

    record = draft.parent / "review-cycle-1.md"
    assert record.is_file(), "the rejection must still write the review-cycle record"
    assert "fix the off-by-one in the tally" in record.read_text(encoding="utf-8"), "the record must keep the reviewer's text verbatim"

    leftovers = [path for path in _dirty_paths(repo, f"kitty-specs/{MISSION_SLUG}") if path.endswith("review-feedback-1.md")]
    assert leftovers == [], f"the rejection left its own feedback draft untracked: {leftovers}"
    assert not draft.exists(), f"the rejected draft should be retired once the record is durable: {draft}"

    _seed_hops(feature_dir, [(Lane.PLANNED, Lane.CLAIMED), (Lane.CLAIMED, Lane.IN_PROGRESS)], day="2026-01-02")
    resubmitted = _resubmit()
    assert resubmitted.exit_code == 0, resubmitted.output  # type: ignore[attr-defined]
    assert "Blocking:" not in resubmitted.output  # type: ignore[attr-defined]


def test_a_non_durable_record_keeps_the_draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-002: ``--no-auto-commit`` writes no durable record, so nothing may be removed."""
    _repo, feature_dir = _build_mission(tmp_path, monkeypatch, auto_commit=False)
    draft = _advertised_draft(feature_dir)
    draft.parent.mkdir(parents=True, exist_ok=True)
    body = "**Issue 1**: keep this even when the record is not committed.\n"
    draft.write_text(body, encoding="utf-8")

    rejected = _reject(draft)
    assert rejected.exit_code == 0, rejected.output  # type: ignore[attr-defined]
    assert draft.exists(), "a non-durable record must never authorize removing the only copy"
    assert draft.read_text(encoding="utf-8") == body


def test_a_tracked_draft_is_never_deleted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: removing an already-committed draft would itself dirty the tree."""
    repo, feature_dir = _build_mission(tmp_path, monkeypatch)
    draft = _advertised_draft(feature_dir)
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("**Issue 1**: the reviewer committed this one.\n", encoding="utf-8")
    _git(repo, "add", str(draft))
    _git(repo, "commit", "-m", "reviewer: commit the feedback file")

    rejected = _reject(draft)
    assert rejected.exit_code == 0, rejected.output  # type: ignore[attr-defined]
    assert draft.exists(), "a tracked draft must be left alone"
    _git(repo, "ls-files", "--error-unmatch", str(draft.relative_to(repo)))


def test_a_draft_outside_the_mission_directory_is_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: a scratch note outside ``kitty-specs/<mission>/`` is not this seam's to delete.

    The positive control on the same fixture shape is the first test: an inside-mission draft *is*
    removed after a durable rejection.
    """
    _repo, feature_dir = _build_mission(tmp_path, monkeypatch)
    draft = tmp_path / "review-feedback-1.md"
    draft.write_text("**Issue 1**: a scratch note outside the mission.\n", encoding="utf-8")

    rejected = _reject(draft)
    assert rejected.exit_code == 0, rejected.output  # type: ignore[attr-defined]
    assert draft.exists(), "a draft outside the mission directory must be untouched"


def test_a_kept_draft_is_announced_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """FR-008: a draft the seam kept must be visible to the operator.

    Both feedback-file legs the writer serves — the rejection
    (``persist_rejected_review_cycle_for_rollback``) and #6652's
    approval-with-feedback (``_persist_approved_review_cycle``) — call this
    announcer with the write result. It prints each reason on stderr, so a
    ``--json`` caller's stdout document is unchanged, and it tolerates the
    ``SimpleNamespace`` writer double the frozen seam tests inject.
    """
    from types import SimpleNamespace

    from specify_cli.cli.commands.agent.tasks_verdict_persistence import _announce_kept_feedback_draft

    _announce_kept_feedback_draft(None)
    _announce_kept_feedback_draft(SimpleNamespace())
    assert "Warning:" not in capsys.readouterr().err

    _announce_kept_feedback_draft(SimpleNamespace(warnings=("Review feedback draft /tmp/x.md was kept: it changed after the record.",)))
    captured = capsys.readouterr()
    assert "Warning: Review feedback draft /tmp/x.md was kept" in captured.err
    assert captured.out == "", "the announcement must never touch stdout"

    # The real write result carries the same field, and no warnings means silence.
    from specify_cli.review.cycle import CreatedRejectedReviewCycle

    assert "warnings" in CreatedRejectedReviewCycle.__dataclass_fields__
