"""#6652 / #6654 — the approval review-cycle record keeps the reviewer's feedback
file and carries a replay command a shell can run.

#6652: ``move-task --to approved --review-feedback-file <f>`` validated the file,
then wrote a synthesized one-line body (``Approved by <reviewer>: <ref>``) and
reported ``verdict_durably_persisted: true``; the file's content was lost. The
operator ruled (2026-10-26) that approval persists the content: the approval
line, a blank line, then the file verbatim. A file supplied on a WP whose latest
verdict is already an approval writes a new cycle; a file the approval cannot
record (damaged verdict slot) is refused rather than dropped.

#6654: ``reproduction_command`` interpolated the reviewer unquoted, so
``Jane Doe (model-x)`` produced invalid shell and split into three argv words.

The end-to-end cases drive the real ``_do_move_task`` orchestrator against fake
ports (``auto_commit=False`` still writes the record locally), mirroring
``test_move_task_approval_evidence.py``. The verdict-slot edges call
``_persist_approved_review_cycle`` directly with the slot lookup stubbed.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import typer

from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    TasksPorts,
)
from specify_cli.cli.commands.agent import tasks_move_task as _tmt
from specify_cli.cli.commands.agent import tasks_verdict_persistence as _tvp
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import ReviewCycleError
from specify_cli.status.models import Lane, ReviewResult, StatusEvent, TransitionRequest
from specify_cli.status.reducer import ReviewResultLookup
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import FakeFsReader, FakeGitOps, FakeRender

pytestmark = pytest.mark.fast

_MISSION = "approval-feedback-6652"
_WP_ID = "WP01"
_REVIEWER = "reviewer-renata"
_DISTINCTIVE = "DISTINCTIVE-APPROVAL-FEEDBACK-LINE: alpha() checked; tests pass."
_APPROVAL_LINE = f"Approved by {_REVIEWER}: approval:{_WP_ID}"


def _build_wp_file(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _MISSION
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (tasks_dir / f"{_WP_ID}-test.md").write_text(
        f"---\nwork_package_id: {_WP_ID}\ntitle: Test\nexecution_mode: code_change\nagent: testbot\n"
        f"subtasks: [T001]\nowned_files:\n  - src/wp01/**\nauthoritative_surface: src/wp01/\n---\n\n# {_WP_ID}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir


def _seed_in_review(feature_dir: Path) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{_WP_ID}-in_review",
            mission_slug=feature_dir.name,
            wp_id=_WP_ID,
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


@dataclass
class _CapturingCoordRouter:
    write_dir: Path
    requests: list[TransitionRequest] = field(default_factory=list)

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        return self.write_dir

    def commit_status(self, request: TransitionRequest, *, capability: GuardCapability) -> CommitStatusResult:
        self.requests.append(request)
        return CommitStatusResult(event=None, skipped=False)

    def commit_artifact(self, *args: object, **kwargs: object) -> CommitArtifactResult:
        raise AssertionError("commit_artifact must not be called with auto_commit=False")


def _ports(feature_dir: Path) -> TasksPorts:
    return TasksPorts(fs=FakeFsReader(), coord=_CapturingCoordRouter(write_dir=feature_dir), git=FakeGitOps(), render=FakeRender())


def _approve(tmp_path: Path, feature_dir: Path, *, reviewer: str = _REVIEWER, feedback: Path | None = None) -> None:
    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={"_validate_ready_for_review": (True, []), "_check_unchecked_subtasks": []},
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to="approved",
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid="4242",
                note="Review passed",
                review_feedback_file=feedback,
                approval_ref=None,
                reviewer=reviewer,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=False,
                json_output=True,
            ),
            ports=_ports(feature_dir),
        )


def _cycle(feature_dir: Path, number: int = 1) -> ReviewCycleArtifact:
    return ReviewCycleArtifact.from_file(feature_dir / "tasks" / f"{_WP_ID}-test" / f"review-cycle-{number}.md")


def _feedback_file(tmp_path: Path) -> Path:
    path = tmp_path / "approval-feedback.md"
    path.write_text(f"# Review\n\n{_DISTINCTIVE}\n", encoding="utf-8")
    return path


# --- end to end through _do_move_task ---------------------------------------


def test_approval_with_feedback_file_records_its_content(tmp_path: Path) -> None:
    """#6652 FR-001: the approval line, then the reviewer's file verbatim."""
    feature_dir = _build_wp_file(tmp_path)
    _seed_in_review(feature_dir)

    _approve(tmp_path, feature_dir, feedback=_feedback_file(tmp_path))

    body = str(_cycle(feature_dir).body)
    assert body.startswith(f"{_APPROVAL_LINE}\n\n")
    assert _DISTINCTIVE in body
    assert body.endswith(f"# Review\n\n{_DISTINCTIVE}\n")


def test_approval_without_feedback_file_keeps_the_one_line_body(tmp_path: Path) -> None:
    """FR-002 positive control: no file, same synthesized approval as before."""
    feature_dir = _build_wp_file(tmp_path)
    _seed_in_review(feature_dir)

    _approve(tmp_path, feature_dir)

    assert str(_cycle(feature_dir).body).strip() == _APPROVAL_LINE


def test_approval_refuses_a_prior_review_cycle_as_feedback(tmp_path: Path) -> None:
    """FR-004: a file that parses as a review-cycle record is refused, as on a rejection."""
    feature_dir = _build_wp_file(tmp_path)
    _seed_in_review(feature_dir)
    copied = tmp_path / "copied-cycle.md"
    copied.write_text(
        "---\naffected_files: []\ncycle_number: 1\nmission_slug: other\nreviewed_at: '2026-01-01T00:00:00Z'\n"
        "reviewer_agent: someone\nverdict: rejected\nwp_id: WP09\n---\n\nold body\n",
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit):
        _approve(tmp_path, feature_dir, feedback=copied)

    assert not (feature_dir / "tasks" / f"{_WP_ID}-test" / "review-cycle-1.md").exists()


def test_reproduction_command_keeps_a_multi_word_reviewer_as_one_argument(tmp_path: Path) -> None:
    """#6654 FR-006: the recorded command is valid shell and replays the same attribution."""
    reviewer = "Jane Doe (model-x)"
    feature_dir = _build_wp_file(tmp_path)
    _seed_in_review(feature_dir)

    _approve(tmp_path, feature_dir, reviewer=reviewer)

    command = _cycle(feature_dir).reproduction_command
    assert command is not None
    argv = shlex.split(command)
    assert argv[argv.index("--agent") + 1] == reviewer
    assert argv[:6] == ["spec-kitty", "agent", "tasks", "move-task", _WP_ID, "--to"]
    assert subprocess.run(["bash", "-n", "-c", command], capture_output=True, check=False).returncode == 0


def test_reproduction_command_reads_unchanged_for_a_bare_word_reviewer(tmp_path: Path) -> None:
    """#6654 ratchet: a single-word reviewer needs no quoting."""
    feature_dir = _build_wp_file(tmp_path)
    _seed_in_review(feature_dir)

    _approve(tmp_path, feature_dir)

    assert _cycle(feature_dir).reproduction_command == f"spec-kitty agent tasks move-task {_WP_ID} --to approved --mission {_MISSION} --agent {_REVIEWER}"


# --- verdict-slot edges, at the writer -----------------------------------------


def _state(tmp_path: Path, *, feedback: Path | None) -> _tmt._MoveTaskState:
    st = _tmt._MoveTaskState(
        task_id=_WP_ID,
        to="approved",
        mission=_MISSION,
        agent="testbot",
        assignee=None,
        shell_pid=None,
        note="Review passed",
        review_feedback_file=None,
        approval_ref=None,
        reviewer=_REVIEWER,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=False,
        json_output=True,
    )
    st.main_repo_root = tmp_path
    st.mission_slug = _MISSION
    st.feature_dir = tmp_path / "kitty-specs" / _MISSION
    st.resolved_auto_commit = False
    st.skip_target_branch_commit = False
    st.resolved_feedback_source = feedback
    return st


def _stub_slot(monkeypatch: pytest.MonkeyPatch, lookup: ReviewResultLookup) -> None:
    monkeypatch.setattr(_tvp, "event_sourced_review_result", lambda _feature_dir, _wp_id: lookup)


_APPROVED_SLOT = ReviewResultLookup(slot_present=True, result=ReviewResult(reviewer=_REVIEWER, verdict="approved", reference="x"))
_DAMAGED_SLOT = ReviewResultLookup(slot_present=True, result=None)


def test_already_approved_wp_with_feedback_file_writes_a_new_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-003: a supplied file is recorded even when the latest verdict is already an approval."""
    feature_dir = _build_wp_file(tmp_path)
    _stub_slot(monkeypatch, _APPROVED_SLOT)

    signal = _tvp._persist_approved_review_cycle(_state(tmp_path, feedback=_feedback_file(tmp_path)), _ports(feature_dir))

    assert signal is not None
    assert _DISTINCTIVE in str(_cycle(feature_dir).body)


def test_already_approved_wp_without_feedback_file_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-002: no duplicate approval stub when no file is supplied."""
    feature_dir = _build_wp_file(tmp_path)
    _stub_slot(monkeypatch, _APPROVED_SLOT)

    assert _tvp._persist_approved_review_cycle(_state(tmp_path, feedback=None), _ports(feature_dir)) is None
    assert not (feature_dir / "tasks" / f"{_WP_ID}-test" / "review-cycle-1.md").exists()


def test_damaged_verdict_slot_refuses_a_supplied_feedback_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-005: a file the approval cannot record is refused, never dropped in silence."""
    feature_dir = _build_wp_file(tmp_path)
    _stub_slot(monkeypatch, _DAMAGED_SLOT)
    feedback = _feedback_file(tmp_path)

    with pytest.raises(ReviewCycleError, match="approval-feedback.md"):
        _tvp._persist_approved_review_cycle(_state(tmp_path, feedback=feedback), _ports(feature_dir))

    assert not (feature_dir / "tasks" / f"{_WP_ID}-test" / "review-cycle-1.md").exists()


def test_damaged_verdict_slot_without_feedback_file_stays_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007 of the verdict seam (unchanged): no file, damaged slot, nothing written."""
    feature_dir = _build_wp_file(tmp_path)
    _stub_slot(monkeypatch, _DAMAGED_SLOT)

    assert _tvp._persist_approved_review_cycle(_state(tmp_path, feedback=None), _ports(feature_dir)) is None
