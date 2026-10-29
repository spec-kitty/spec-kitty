"""Regression (M1, adversarial squad on PR #3156): the synthesized approval
body collides with the review-cycle content-identity guard.

``_persist_approved_review_cycle`` (``tasks_move_task.py``, inside
``_mt_finalize_plan``) synthesizes a throwaway feedback body of
``f"Approved by {reviewer_agent}: {approval_reference}\\n"``. Both components
are deterministic for a repeated ``--note "Review passed"`` approval (the
literal, hard-coded note the machine path always sends — see
``src/runtime/next/prompt_builder.py:293`` and
``src/specify_cli/cli/commands/agent/workflow_executor.py:1916,2080``).

So: reject (cycle 1) -> approve (cycle 2, synthesized body A) -> WP re-opened,
reject again (cycle 3) -> approve again with the SAME ``--note`` (cycle 4,
byte-identical synthesized body A) -> ``_guard_feedback_source_provenance``
(``src/specify_cli/review/cycle.py``) sees cycle 4's body match cycle 2's
body verbatim and raises ``ReviewCycleError`` -- caught by ``_do_move_task``'s
generic ``except Exception`` and re-raised as ``typer.Exit(1)``. The WP can
never be approved a second time through the ordinary machine path.

Drives the REAL ``_do_move_task`` orchestrator with a real Git checkout and
artifact commit router, while retaining injected non-durability ports, so this
is a genuine end-to-end reproduction of the collision, not merely a unit test
of the guard.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import typer

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    RealCoordCommitRouter,
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import TransitionRequest
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import commit_lane_implementation
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "approval-body-collision"
_MISSION_ID = "01HQZZZZZZZZZZZZZZZZZZZZZZ"
_WP_ID = "WP01"


def _init_repo(path: Path) -> None:
    """Create the smallest governed Git destination used by verdict saves."""
    subprocess.run(
        ["git", "init", "-b", "wip-lane"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> tuple[Path, Path]:
    """Minimal WP + feature structure (mirrors ``test_move_task_orchestration``)."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": mission_slug}),
        encoding="utf-8",
    )
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"agent: testbot\n"
        f"subtasks: [T001, T002, T003]\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _seed_wp_event(feature_dir: Path, wp_id: str, to_lane: str) -> None:
    """Seed a WP event so the canonical event log reports *to_lane* as current."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{to_lane}-{len(list(feature_dir.glob('status.events*')))}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(to_lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_rejection_result_event(feature_dir: Path, wp_id: str) -> None:
    """Seed the ``in_review -> planned`` rejection's ``review_result`` directly.

    WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint:
    ``_persist_approved_review_cycle``'s "is the current verdict a
    rejection" probe now resolves the event authority
    (``event_sourced_review_result``), not ``review-cycle-N.md``
    frontmatter. This test's ``FakeCoordCommitRouter.commit_status`` is a
    canned stub (``CommitStatusResult(event=None, ...)``) that never
    appends to the real event log at all -- the event log here is
    ENTIRELY hand-seeded via ``_seed_wp_event``/this helper, standing in
    for what the real ``commit_status`` -> ``emit_status_transition`` path
    would have durably recorded for the reject move that just ran. Without
    this, the approval probe correctly (per G2) treats the rejection as
    absent and no-ops the second cycle's write -- not a WP05 regression,
    but a test-fixture gap this WP's repoint newly exposes.
    """
    from specify_cli.status.models import ReviewResult

    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-rejected-{len(list(feature_dir.glob('status.events*')))}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=False,
            execution_mode="worktree",
            reason="rejected on review",
            review_result=ReviewResult(
                reviewer="reviewer-renata", verdict="changes_requested", reference="x"
            ),
        ),
    )


def _seed_lanes_json(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Write a minimal ``lanes.json`` covering *wp_id*.

    #4758's ``_mt_guard_planned_boundary_lanes`` now refuses any hop OUT of
    ``planned`` when ``lanes.json`` is absent (a required precondition, not a
    behavior change under test here).
    """
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=_MISSION_ID,
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="wip-lane",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=(wp_id,),
                    write_scope=(f"src/{wp_id.lower()}/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            # #6715: the real planning commit (the fixture repository's tip), so the evidence
            # window the move into review reads is computable; WP01's implementation is
            # committed on its lane branch below.
            planning_commit_sha=subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=feature_dir.parents[1], check=True, capture_output=True, text=True
            ).stdout.strip(),
        ),
    )
    commit_lane_implementation(feature_dir.parents[1], feature_dir, path=f"src/{wp_id.lower()}/impl.py")


def _fake_ports(feature_dir: Path) -> TasksPorts:
    coord = _RealArtifactFixtureRouter(feature_dir)
    return TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=coord,
        git=FakeGitOps(),
        render=FakeRender(),
    )


class _RealArtifactFixtureRouter:
    """Use real Git durability while keeping status emission fixture-controlled."""

    def __init__(self, write_dir: Path) -> None:
        self.write_dir = write_dir
        self._real = RealCoordCommitRouter()

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        del mission
        return self.write_dir

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        del request, capability
        return CommitStatusResult(event=None, skipped=False)

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        return self._real.commit_artifact(
            mission,
            paths,
            message,
            kind=kind,
            policy=policy,
        )


def _run_move(
    tmp_path: Path,
    *,
    to: str,
    ports: TasksPorts,
    note: str | None = None,
    review_feedback_file: Path | None = None,
    approval_ref: str | None = None,
    done_override_reason: str | None = None,
) -> None:
    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to=to,
                mission=_MISSION,
                # #6715 ruling A: an asserted reviewer (a placeholder approval is refused at the move).
                agent="reviewer-renata",
                assignee=None,
                shell_pid=None,
                note=note,
                review_feedback_file=review_feedback_file,
                approval_ref=approval_ref,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=done_override_reason,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=True,
                json_output=True,
            ),
            ports=ports,
        )


def test_reject_approve_reject_approve_with_identical_note_succeeds(
    tmp_path: Path,
) -> None:
    """Full reject -> approve -> reject -> approve cycle with a byte-identical
    ``--note "Review passed"`` on both approvals must succeed both times.

    Before the fix: the second ``to=approved`` call raises ``typer.Exit(1)``
    because its synthesized body collides with the first approval's body.
    """
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed approval collision fixture"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    ports = _fake_ports(feature_dir)
    wp_dir = feature_dir / "tasks" / wp_file.stem
    # lanes.json is now a required precondition to leave 'planned' (#4758,
    # _mt_guard_planned_boundary_lanes) -- fixture update, not a behavior
    # change: this test exercises the approval-body content-identity
    # collision, not the lanes.json guard.
    _seed_lanes_json(feature_dir, _MISSION, _WP_ID)

    # Cycle 1: reject.
    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    feedback1 = tmp_path / "feedback1.md"
    feedback1.write_text("**Issue**: first pass needs work.\n", encoding="utf-8")
    _run_move(tmp_path, to="planned", ports=ports, review_feedback_file=feedback1)
    assert (wp_dir / "review-cycle-1.md").exists()
    _seed_rejection_result_event(feature_dir, _WP_ID)

    # Cycle 2: approve with the machine's hard-coded note.
    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    _run_move(tmp_path, to="approved", ports=ports, note="Review passed")
    assert (wp_dir / "review-cycle-2.md").exists()
    # WP06 (verdict-seam-write-unification-01KZ9Q35, FR-003/SC-007):
    # ReviewCycleArtifact no longer carries a verdict field -- the approval
    # write's own synthesized body ("Approved by ...") is the checkable proxy.
    assert "Approved by" in (wp_dir / "review-cycle-2.md").read_text(
        encoding="utf-8"
    )

    # Cycle 3: WP re-opened, rejected again with distinct feedback.
    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    feedback2 = tmp_path / "feedback2.md"
    feedback2.write_text("**Issue**: second pass needs work.\n", encoding="utf-8")
    _run_move(tmp_path, to="planned", ports=ports, review_feedback_file=feedback2)
    assert (wp_dir / "review-cycle-3.md").exists()
    _seed_rejection_result_event(feature_dir, _WP_ID)

    # Cycle 4: approve AGAIN with the byte-identical note. This is the M1
    # reproduction -- must succeed, not raise.
    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    try:
        _run_move(tmp_path, to="approved", ports=ports, note="Review passed")
    except typer.Exit as exc:  # pragma: no cover - only on the pre-fix code path
        pytest.fail(
            f"second approval with an identical --note raised typer.Exit"
            f"({exc.exit_code}) -- the synthesized approval body collided "
            "with the provenance guard (M1)"
        )

    # The identical approval adopts the already committed cycle-2 record.  A
    # new cycle-4 file would duplicate the same evidence instead of preserving
    # the retained-record idempotence contract.
    assert not (wp_dir / "review-cycle-4.md").exists()
    cycle2 = wp_dir / "review-cycle-2.md"
    destination = subprocess.run(
        [
            "git",
            "show",
            "wip-lane:kitty-specs/approval-body-collision/tasks/"
            "WP01-test/review-cycle-2.md",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    ).stdout
    assert destination == cycle2.read_bytes()
    assert "Approved by" in cycle2.read_text(encoding="utf-8")


def test_approval_with_real_feedback_file_records_its_content(
    tmp_path: Path,
) -> None:
    """#6652: ``--review-feedback-file`` on an approval over a rejection lands in
    the committed approval cycle, below the ``Approved by <reviewer>: <ref>`` line.
    """
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed approval feedback fixture"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    ports = _fake_ports(feature_dir)
    _seed_lanes_json(feature_dir, _MISSION, _WP_ID)
    rejection = tmp_path / "rejection.md"
    rejection.write_text("**Issue**: first pass needs work.\n", encoding="utf-8")
    approval_feedback = tmp_path / "approval-feedback.md"
    approval_feedback.write_text(
        "# Review\n\nDISTINCTIVE-APPROVAL-FEEDBACK-LINE: alpha() checked; tests pass.\n",
        encoding="utf-8",
    )

    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    _run_move(tmp_path, to="planned", ports=ports, review_feedback_file=rejection)
    _seed_rejection_result_event(feature_dir, _WP_ID)
    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    _run_move(
        tmp_path,
        to="approved",
        ports=ports,
        note="Review passed",
        review_feedback_file=approval_feedback,
        approval_ref="PR-42",
    )

    committed = subprocess.run(
        [
            "git",
            "show",
            f"wip-lane:kitty-specs/{_MISSION}/tasks/{wp_file.stem}/review-cycle-2.md",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    approved_line = committed.index(": PR-42")
    assert committed.rfind("Approved by", 0, approved_line) != -1
    assert approved_line < committed.index("DISTINCTIVE-APPROVAL-FEEDBACK-LINE: alpha() checked; tests pass.")


@pytest.mark.parametrize("target", ["approved", "done"])
def test_first_pass_approval_records_feedback_file_and_approval_ref(
    tmp_path: Path,
    target: str,
) -> None:
    """#6652 through the real ``_do_move_task``: ``in_review -> approved`` and
    ``in_review -> done`` both write a new approval record that holds the
    ``--approval-ref`` line and the file's content."""
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed first-pass approval fixture"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    ports = _fake_ports(feature_dir)
    _seed_lanes_json(feature_dir, _MISSION, _WP_ID)
    feedback = tmp_path / "approval-feedback.md"
    feedback.write_text("DISTINCTIVE-FIRST-PASS-FEEDBACK\n", encoding="utf-8")

    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    _run_move(
        tmp_path,
        to=target,
        ports=ports,
        note="Review passed",
        review_feedback_file=feedback,
        approval_ref="PR-42",
        done_override_reason="no lane branch in this fixture" if target == "done" else None,
    )

    text = (feature_dir / "tasks" / wp_file.stem / "review-cycle-1.md").read_text(encoding="utf-8")
    assert "Approved by" in text
    assert ": PR-42" in text
    assert "DISTINCTIVE-FIRST-PASS-FEEDBACK" in text


def test_approval_with_non_utf8_feedback_file_is_refused_not_crashed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A latin-1 ``--review-feedback-file`` on approval is a clean refusal.

    It exits 1 with a message naming the encoding problem, not a raw codec
    traceback, and writes no review-cycle record.
    """
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed non-utf8 fixture"], cwd=tmp_path, check=True, capture_output=True)
    ports = _fake_ports(feature_dir)
    _seed_lanes_json(feature_dir, _MISSION, _WP_ID)
    feedback = tmp_path / "latin1.md"
    feedback.write_bytes(b"caf\xe9\n")

    _seed_wp_event(feature_dir, _WP_ID, "in_review")
    with pytest.raises(typer.Exit) as exc_info:
        _run_move(tmp_path, to="approved", ports=ports, note="Review passed", review_feedback_file=feedback)

    assert exc_info.value.exit_code == 1
    assert "not readable UTF-8 text" in capsys.readouterr().out
    assert not list((feature_dir / "tasks" / wp_file.stem).glob("review-cycle-*.md"))
