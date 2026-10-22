"""WP04 (governance-at-the-gate, #3682) — gate-side approval evidence capture.

FR-006 / SC-006: a first-pass ``move-task --to approved`` now (a) emits a
``policy_metadata`` sidecar + a non-null ``review_ref`` on the ``approved``
status event, and (b) authors a ``tasks/<WP>/review-cycle-1.md`` artifact
(FR-007). These are red-first, end-to-end orchestration tests driving the
REAL ``_do_move_task`` orchestrator against WP02 Fake ports (mirroring
``test_move_task_orchestration.py``'s pattern), with a locally-defined
capturing coord router so the exact ``TransitionRequest`` reaching
``commit_status`` can be inspected -- ``FakeCoordCommitRouter`` (the shared
fixture in ``test_tasks_ports.py``) only records ``(mission_slug,
capability)``, not the full request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    TasksPorts,
)
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import FakeFsReader, FakeGitOps, FakeRender

pytestmark = pytest.mark.fast

_MISSION = "wp04-gate-evidence"


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> tuple[Path, Path]:
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"agent: testbot\n"
        f"subtasks: [T001]\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _seed_wp_event(feature_dir: Path, wp_id: str, to_lane: str) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{to_lane}",
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


@dataclass
class _CapturingCoordRouter:
    """A minimal ``CoordCommitRouter`` that retains the FULL request per call.

    Unlike the shared ``FakeCoordCommitRouter`` (which only logs
    ``(mission_slug, capability)`` — sufficient for the disjointness proofs
    it exists for), this WP04 test needs to inspect ``policy_metadata`` /
    ``review_ref`` on the actual ``TransitionRequest`` the orchestrator built.
    """

    write_dir: Path
    status_result: CommitStatusResult = field(default_factory=lambda: CommitStatusResult(event=None, skipped=False))
    requests: list[TransitionRequest] = field(default_factory=list)

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        return self.write_dir

    def commit_status(self, request: TransitionRequest, *, capability: GuardCapability) -> CommitStatusResult:
        self.requests.append(request)
        return self.status_result

    def commit_artifact(self, *args: object, **kwargs: object) -> CommitArtifactResult:
        raise AssertionError("commit_artifact must not be called with auto_commit=False")


def _fake_ports(feature_dir: Path) -> tuple[TasksPorts, _CapturingCoordRouter]:
    coord = _CapturingCoordRouter(write_dir=feature_dir)
    ports = TasksPorts(fs=FakeFsReader(), coord=coord, git=FakeGitOps(), render=FakeRender())
    return ports, coord


def _run_approve(tmp_path: Path, *, ports: TasksPorts) -> None:
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
                task_id="WP01",
                to="approved",
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid="4242",
                note=None,
                review_feedback_file=None,
                approval_ref=None,
                reviewer="reviewer-renata",
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
            ports=ports,
        )


def test_first_pass_approve_emits_non_null_policy_metadata_and_review_ref(
    tmp_path: Path,
) -> None:
    """T1 (red-first): a first-pass ``in_review -> approved`` move emits its
    lane-hop ``TransitionRequest`` with a non-null ``policy_metadata``
    (``tool``/``profile``/``model``/``shell_pid``) AND a non-null
    ``review_ref`` -- closing the FR-006 brownfield gap where the approval
    event carried neither."""
    feature_dir, _wp = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_review")
    ports, coord = _fake_ports(feature_dir)

    _run_approve(tmp_path, ports=ports)

    assert len(coord.requests) == 1
    request = coord.requests[0]
    assert request.to_lane == Lane.APPROVED
    assert request.policy_metadata is not None
    assert request.policy_metadata["tool"] == "reviewer-renata"
    assert "profile" in request.policy_metadata
    assert "model" in request.policy_metadata
    assert request.policy_metadata["shell_pid"] == "4242"
    assert request.review_ref is not None
    assert request.review_ref.strip() != ""


def test_first_pass_approve_writes_review_cycle_artifact_with_reproduction_command(
    tmp_path: Path,
) -> None:
    """T2 (red-first): the SAME first-pass approve authors
    ``tasks/WP01-test/review-cycle-1.md`` on disk (verdict ``approved``, a
    ``reproduction_command``) -- SC-006's second half. ``auto_commit=False``
    still writes the file locally; only the git commit is skipped."""
    feature_dir, _wp = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_review")
    ports, _coord = _fake_ports(feature_dir)

    _run_approve(tmp_path, ports=ports)

    cycle_path = feature_dir / "tasks" / "WP01-test" / "review-cycle-1.md"
    assert cycle_path.exists()
    content = cycle_path.read_text(encoding="utf-8")
    assert "reproduction_command:" in content
    assert "null" not in content.splitlines()[next(i for i, line in enumerate(content.splitlines()) if line.startswith("reproduction_command:"))]
    assert "WP01" in content
    assert "--to approved" in content
