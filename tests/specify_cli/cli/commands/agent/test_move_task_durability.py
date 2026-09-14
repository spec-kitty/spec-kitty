"""WP11 (T047-T050): transition ordering and the durability signal.

T047 originally reproduced, red-first, the committed-orphan hazard FR-002/
SC-003 exist to close: a transition-emit failure left a COMMITTED
``verdict: approved`` review-cycle artifact on disk for a WP whose lane never
actually moved. T048's revert-compensator (``tasks_verdict_persistence.
revert_committed_verdict_write``, wired at the ``_mt_execute`` call site via
``_mt_execute_with_verdict_revert`` in ``tasks_move_task.py``) now closes that
hazard, so both tests below assert the GREEN post-fix outcome: no readable
committed verdict survives a failed transition, and the retry -- with its
OWN, genuine ``--approval-ref`` -- records the real approval, not a stale one
left over from the reverted failed attempt.

``exit_code == 0``/``typer.Exit`` is asserted as necessary but never
sufficient in either test: every assertion also queries recorded state
directly (``ReviewCycleArtifact.latest`` -- WP05
(verdict-seam-write-unification-01KZ9Q35) retired ``latest_review_artifact_
verdict``, the census "reader"-category verdict parser this test used to
call; ``.latest`` is the KEPT content/cycle-number loader, squad #1 -- git
HEAD content, and the transactional lane), never mere file-listing or
exit-code alone.

Both drive the REAL ``_do_move_task`` orchestrator against a REAL
git-fixture repo with the REAL ``RealCoordCommitRouter.commit_artifact`` (so
"committed"/"reverted" is proven via ``git log``/``git status``/HEAD content,
never mere file existence) while the transition-emit leg (``commit_status``)
is fault-injected via a constructor-supplied stand-in, mirroring the
``RealCoordCommitRouter(emit_fn=...)`` injection seam already established in
``tests/review/test_cycle.py``.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import typer

from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    MissionHandle,
    RealCoordCommitRouter,
    TasksPorts,
)
from specify_cli.coordination import status_transition as _status_transition
from specify_cli.cli.commands.agent import tasks_move_task as _tmt
from specify_cli.cli.commands.agent import tasks_verdict_persistence as _tvp
from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs
from specify_cli.cli.commands.agent.tasks_finalize_validation import (
    _read_transactional_wp_lane,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.review import cycle as _review_cycle
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import (
    create_rejected_review_cycle,
    resolve_review_cycle_pointer,
)
from specify_cli.review.verdict_commit_queue import VerdictSaveBusy, verdict_save_queue_is_held
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    ReviewResult,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import event_sourced_review_result
from specify_cli.status.store import append_annotations_atomic_verified, append_event
from specify_cli.status import TransitionError, TransitionRequest, read_events
from tests._perf_helpers import assert_timing_budget
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

# PR #3211 landing pass (2026-08-05, F6): re-marked from `fast` to
# `integration, git_repo` -- both tests drive the REAL `_do_move_task`
# orchestrator against a REAL git-fixture repo (see the module docstring),
# which `test_pytest_marker_correctness.py`'s Rule 1/Rule 2 require: `git_repo`
# presence, and `fast` exclusion, for any file that invokes git via
# subprocess.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "wp11-durability"
_WP_ID = "WP01"


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _unprotect_main(repo: Path) -> None:
    """Disable branch protection so a real commit lands on ``main``.

    Mirrors ``tests/review/test_cycle.py``'s ``_unprotect_main``.
    """
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        "protection:\n  protected_branches: []\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "test: unprotect main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


_MISSION_ID = "01HQZZZZZZZZZZZZZZZZZZZZZZ"


def _build_wp_file(repo: Path, mission_slug: str, wp_id: str) -> tuple[Path, Path]:
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    # A real, non-coord SINGLE_BRANCH mission still needs a resolvable
    # ``meta.json`` -- ``read_events_transactional`` (a REAL git repo takes the
    # non-fallback path _transaction_topology_available walks) treats an
    # ABSENT meta.json as "maybe still-coord, go check CoordinationWorkspace",
    # which then hard-fails on an empty ``mid8``. Any valid meta dict makes
    # ``meta_exists`` True, short-circuiting to the (false) coord-transaction
    # check instead -- this mission has no coordination_branch/lanes.json, so
    # it is genuinely SINGLE_BRANCH.
    import json as _json

    (feature_dir / "meta.json").write_text(
        _json.dumps({"mission_id": _MISSION_ID, "mission_slug": mission_slug}),
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


def _seed_event_at(seq: int) -> str:
    """A monotonically increasing timestamp keyed by *seq*.

    WP05 (verdict-seam-write-unification-01KZ9Q35) fixture fix:
    ``status/reducer.py::reduce`` sorts transitions by ``(at, event_id)``
    ascending -- every seed call in this module used the SAME literal
    ``at``, so ties broke on ``event_id`` STRING order instead of the
    intended seed/call sequence (e.g. ``"...-in_review-2"`` sorts before
    ``"...-rejected-1"`` lexicographically, silently reordering a rejection
    AFTER a later reopen and corrupting the reduced "current lane"). Giving
    each seeded event its own ``seq``-derived minute makes the sort
    unambiguous and matches the caller's intended chronological order.
    """
    return f"2026-01-01T00:{seq:02d}:00+00:00"


def _seed_wp_event(feature_dir: Path, wp_id: str, to_lane: str, *, seq: int) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{to_lane}-{seq}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(to_lane),
            at=_seed_event_at(seq),
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_rejection_result_event(feature_dir: Path, wp_id: str, *, seq: int) -> None:
    """Seed the ``in_review -> planned`` rejection's ``review_result`` directly.

    WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint:
    ``_persist_approved_review_cycle``'s "is the current verdict a
    rejection" probe now resolves the event authority
    (``event_sourced_review_result``), not ``review-cycle-N.md``
    frontmatter. This module's fixtures write the rejected artifact for
    real (via ``create_rejected_review_cycle``) but never emit a matching
    event -- the fault-injectable/minimal-state harnesses here stand in
    for the full ``commit_status`` -> ``emit_status_transition`` path this
    WP's real production callers use. Without this, the approval probe
    correctly (per G2) treats the rejection as absent and no-ops the
    write -- not a WP05 regression, but a test-fixture gap this WP's
    repoint newly exposes.

    ``seq`` also fixes the ``at`` value (see :func:`_seed_event_at`) so this
    event sorts at its intended position relative to sibling
    ``_seed_wp_event`` calls in the same fixture, not merely by event_id.
    """
    from specify_cli.status.models import ReviewResult

    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-rejected-{seq}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at=_seed_event_at(seq),
            actor="test",
            force=False,
            execution_mode="worktree",
            reason="rejected on review",
            review_result=ReviewResult(
                reviewer="reviewer-renata", verdict="changes_requested", reference="x"
            ),
        ),
    )


@dataclass
class _FaultInjectableCoordRouter:
    """A ``CoordCommitRouter`` whose ``commit_artifact`` is the REAL
    ``RealCoordCommitRouter`` (so the review-cycle write is a genuine,
    verifiable git commit) while ``commit_status`` -- the transition-emit
    leg -- is independently fault-injectable per call.

    ``feature_write_dir`` returns a fixed, test-controlled directory (this
    test does not exercise the coord-worktree resolution seam, only the
    verdict-write / transition-emit ordering) -- the same pattern
    ``FakeCoordCommitRouter`` uses in ``test_tasks_ports.py``.
    """

    write_dir: Path
    real_router: RealCoordCommitRouter = field(default_factory=RealCoordCommitRouter)
    emit_should_fail: bool = False
    status_calls: list[TransitionRequest] = field(default_factory=list)
    status_results: list[CommitStatusResult] = field(default_factory=list)
    artifact_entered: threading.Event | None = None
    artifact_release: threading.Event | None = None
    artifact_wait_after_commit: threading.Event | None = None
    status_committed: threading.Event | None = None

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        return self.write_dir

    def commit_status(
        self, request: TransitionRequest, *, capability: GuardCapability
    ) -> CommitStatusResult:
        self.status_calls.append(request)
        if self.emit_should_fail:
            raise RuntimeError("T047: simulated transition-emit failure")
        result = self.real_router.commit_status(request, capability=capability)
        self.status_results.append(result)
        if self.status_committed is not None:
            self.status_committed.set()
        return result

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: object,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        if self.artifact_entered is not None:
            self.artifact_entered.set()
        if self.artifact_release is not None and not self.artifact_release.wait(10):
            raise TimeoutError("test did not release the first queued verdict writer")
        result = self.real_router.commit_artifact(
            mission, paths, message, kind=kind, policy=policy
        )
        if (
            self.artifact_wait_after_commit is not None
            and not self.artifact_wait_after_commit.wait(10)
        ):
            raise TimeoutError("preceding writer did not commit its status event")
        return result


def _fake_ports(feature_dir: Path, coord: _FaultInjectableCoordRouter) -> TasksPorts:
    return TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=coord,
        git=FakeGitOps(),
        render=FakeRender(),
    )


def _run_move(
    repo: Path,
    *,
    ports: TasksPorts,
    mission_slug: str = _MISSION,
    note: str | None = None,
    approval_ref: str | None = None,
    auto_commit: bool = True,
    to: str = "approved",
    review_feedback_file: Path | None = None,
    reviewer: str | None = None,
    agent: str | None = None,
    json_output: bool = True,
) -> None:
    with setup_mocked_env(
        repo,
        mission_slug=mission_slug,
        target_branch="main",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id=_WP_ID,
                to=to,
                mission=mission_slug,
                agent=agent,
                assignee=None,
                shell_pid=None,
                note=note,
                review_feedback_file=review_feedback_file,
                approval_ref=approval_ref,
                reviewer=reviewer,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=auto_commit,
                json_output=json_output,
            ),
            ports=ports,
        )


def _wp_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _MISSION / "tasks" / f"{_WP_ID}-test"


def _approved_verdict_events(feature_dir: Path) -> list[StatusEvent]:
    """Return authoritative approval events for the test WP."""
    return [
        event
        for event in read_events(feature_dir)
        if event.wp_id == _WP_ID
        and event.review_result is not None
        and event.review_result.verdict == "approved"
    ]


def _assert_event_references_durable_evidence(
    repo: Path, event: StatusEvent, payload: dict[str, object]
) -> None:
    """Assert one event points to the exact governed-ref evidence bytes."""
    review_result = event.review_result
    assert review_result is not None
    evidence_ref = payload["evidence_ref"]
    destination_ref = payload["destination_ref"]
    review_feedback = payload["review_feedback"]
    assert isinstance(evidence_ref, str)
    assert isinstance(destination_ref, str)
    assert isinstance(review_feedback, str)
    assert review_result.reference == review_feedback
    assert event.evidence is not None
    assert event.evidence.review.reference == review_result.reference

    resolved = resolve_review_cycle_pointer(repo, review_result.reference)
    assert resolved.path is not None
    assert resolved.path.resolve() == (repo / evidence_ref).resolve()
    assert review_result.feedback_path == str(resolved.path)

    committed = subprocess.run(
        ["git", "show", f"{destination_ref}:{evidence_ref}"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert committed.stdout == resolved.path.read_bytes()


def _git_status(repo: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _git_head_has_file(repo: Path, relpath: str) -> bool:
    """True iff *relpath* is reachable in ``HEAD``'s tree (``git cat-file -e``).

    Distinct from "was it ever committed" (``_git_log_files`` -- history keeps
    the OLD commit forever) and from "does it exist on disk" (a checkout
    reflects only the CURRENT tree). This is the read T048's revert-commit
    must flip to ``False``: a readable, checked-out-from-HEAD verdict.
    """
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{relpath}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_log_files(repo: Path) -> str:
    result = subprocess.run(
        ["git", "log", "--name-only", "--pretty=format:--COMMIT--"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _setup_fixture(repo: Path) -> Path:
    """Real git repo with WP01 currently ``in_review`` and a rejected
    review-cycle-1.md already committed (the guard's "prior cycle" precondition).
    """
    _init_repo(repo)
    feature_dir, _ = _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)

    _seed_wp_event(feature_dir, _WP_ID, "in_review", seq=0)

    # Seed cycle 1 (rejected) via the real writer + real commit, exactly like
    # production would have left it after an earlier rejection.
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=_MISSION,
        wp_id=_WP_ID,
        wp_slug=f"{_WP_ID}-test",
        body="Needs another pass.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
        commit_router=RealCoordCommitRouter(),
    )
    # WP05 repoint: record the rejection's review_result on the event
    # authority too (see ``_seed_rejection_result_event``'s docstring), then
    # reopen to in_review -- the reducer's carry-forward rule (this event's
    # ``from_lane`` is PLANNED, not IN_REVIEW, and it carries no
    # ``review_result`` of its own) preserves the just-recorded
    # ``changes_requested`` verdict while restoring the "currently in_review"
    # precondition every test in this module relies on.
    _seed_rejection_result_event(feature_dir, _WP_ID, seq=1)
    _seed_wp_event(feature_dir, _WP_ID, "in_review", seq=2)
    return feature_dir


def test_lanes_automatic_approval_commits_transition_and_trailing_note(
    tmp_path: Path,
) -> None:
    """A LANES auto-commit leaves both authoritative status files clean."""
    repo = tmp_path
    mission_slug = "lanes-auto-approval-01HQZZZZ"
    _init_repo(repo)
    feature_dir, _ = _build_wp_file(repo, mission_slug, _WP_ID)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"target_branch": "main", "topology": "lanes"})
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "test: store lanes topology"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _unprotect_main(repo)
    _seed_wp_event(feature_dir, _WP_ID, "in_review", seq=0)
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=_WP_ID,
        wp_slug=f"{_WP_ID}-test",
        body="Needs another pass.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
        commit_router=RealCoordCommitRouter(),
    )
    _seed_rejection_result_event(feature_dir, _WP_ID, seq=1)
    _seed_wp_event(feature_dir, _WP_ID, "in_review", seq=2)

    coord = _FaultInjectableCoordRouter(write_dir=feature_dir)
    _run_move(
        repo,
        ports=_fake_ports(feature_dir, coord),
        mission_slug=mission_slug,
        note="LANES approval note",
        approval_ref="approval:lanes-clean-status",
    )

    events_rel = str((feature_dir / "status.events.jsonl").relative_to(repo))
    status_rel = str((feature_dir / "status.json").relative_to(repo))
    status_porcelain = subprocess.run(
        ["git", "status", "--porcelain", "--", events_rel, status_rel],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert status_porcelain == ""

    committed_events = subprocess.run(
        ["git", "show", f"main:{events_rel}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    payloads = [json.loads(line) for line in committed_events if line.strip()]
    assert any(
        row.get("to_lane") == "approved"
        and (row.get("review_result") or {}).get("verdict") == "approved"
        for row in payloads
    )
    assert any(
        row.get("kind") == "annotation"
        and (row.get("delta") or {}).get("note") == "LANES approval note"
        for row in payloads
    )

    committed_paths = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert not any(path.endswith("snapshot-latest.json") for path in committed_paths)


def test_unbackfilled_legacy_lanes_annotation_remains_uncommitted(
    tmp_path: Path,
) -> None:
    """A valid legacy lanes manifest does not opt in to annotation commits."""
    repo = tmp_path
    mission_slug = "legacy-lanes-approval-01HQZZZZ"
    _init_repo(repo)
    feature_dir, _ = _build_wp_file(repo, mission_slug, _WP_ID)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["target_branch"] = "main"
    meta.pop("topology", None)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    lanes = {
        "version": 1,
        "mission_slug": mission_slug,
        "mission_branch": "main",
        "target_branch": "main",
        "lanes": [{"lane_id": "lane-a", "wp_ids": [_WP_ID]}],
        "computed_at": "2026-08-24T00:00:00+00:00",
        "computed_from": "tasks.md",
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes), encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "test: seed unbackfilled lanes mission"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    identity = _status_transition._TransactionIdentity(
        repo_root=repo,
        feature_dir=feature_dir,
        mission_id=_MISSION_ID,
        mid8=_MISSION_ID[:8],
        destination_ref="main",
        meta_exists=True,
        coordination_branch=None,
        transaction_meta_exists=True,
    )

    assert not _status_transition._lanes_annotation_transaction_available(
        identity, mission_slug
    )


def _rejection_args(feedback: Path, reviewer: str) -> _MoveTaskArgs:
    """Real-command arguments for one automatic rejected-review save."""
    return _MoveTaskArgs(
        task_id=_WP_ID,
        to="planned",
        mission=_MISSION,
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
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
        auto_commit=True,
        json_output=False,
    )


def _assert_queued_rejection_records(
    repo: Path,
    feature_dir: Path,
    first_router: _FaultInjectableCoordRouter,
    second_router: _FaultInjectableCoordRouter,
    first_feedback: Path,
    second_feedback: Path,
) -> None:
    """Assert both queued writes survive as exact evidence/event pairs."""
    assert len(first_router.status_results) == 1
    assert len(second_router.status_results) == 1
    first_event = first_router.status_results[0].event
    second_event = second_router.status_results[0].event
    assert first_event is not None
    assert second_event is not None
    assert first_event.review_result is not None
    assert second_event.review_result is not None, (
        "second queued rejection lost its exact ReviewResult on planned -> planned"
    )

    first_result = first_event.review_result
    second_result = second_event.review_result
    first_resolved = resolve_review_cycle_pointer(repo, first_result.reference)
    second_resolved = resolve_review_cycle_pointer(repo, second_result.reference)
    assert first_resolved.path is not None
    assert second_resolved.path is not None
    assert first_resolved.path != second_resolved.path
    assert ReviewCycleArtifact.from_file(first_resolved.path).body == (
        first_feedback.read_text(encoding="utf-8")
    )
    assert ReviewCycleArtifact.from_file(second_resolved.path).body == (
        second_feedback.read_text(encoding="utf-8")
    )

    first_blob = first_resolved.path.read_bytes()
    second_blob = second_resolved.path.read_bytes()
    assert first_blob != second_blob
    for resolved, blob in ((first_resolved, first_blob), (second_resolved, second_blob)):
        relpath = resolved.path.relative_to(repo)
        committed = subprocess.run(
            ["git", "show", f"main:{relpath}"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        assert committed.stdout == blob

    assert (
        first_event.event_id,
        first_event.from_lane,
        first_event.to_lane,
        first_result.reviewer,
        first_result.verdict,
        first_result.reference,
        first_result.feedback_path,
    ) == (
        first_event.event_id,
        Lane.IN_REVIEW,
        Lane.PLANNED,
        "reviewer-first",
        "changes_requested",
        first_result.reference,
        str(first_resolved.path),
    )
    assert (
        second_event.event_id,
        second_event.from_lane,
        second_event.to_lane,
        second_result.reviewer,
        second_result.verdict,
        second_result.reference,
        second_result.feedback_path,
    ) == (
        second_event.event_id,
        Lane.PLANNED,
        Lane.PLANNED,
        "reviewer-second",
        "changes_requested",
        second_result.reference,
        str(second_resolved.path),
    )

    recorded = read_events(feature_dir)
    assert sum(event.event_id == first_event.event_id for event in recorded) == 1
    assert sum(event.event_id == second_event.event_id for event in recorded) == 1
    current = event_sourced_review_result(feature_dir, _WP_ID)
    assert current.slot_present is True
    assert current.result == second_result


@pytest.mark.parametrize(
    "drop_serialized_result", [False, True], ids=["canonical", "causal-mutation"]
)
def test_two_queued_rejections_preserve_each_exact_cycle_and_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drop_serialized_result: bool,
) -> None:
    """Two real commands serialize evidence, then each publish its own verdict.

    The first writer is paused while holding the real checkout queue.  The
    second command resolves the same ``in_review`` state and reaches the queue,
    but cannot allocate evidence until the first is released.  Writer B then
    pauses after its real Git commit until writer A's real status event lands,
    deterministically forcing B's event to be ``planned -> planned``.

    The mutation case restores the former result-dropping behavior only for
    that second hop and proves the same end-to-end oracle fails causally.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    first_feedback = repo / "first-feedback.md"
    second_feedback = repo / "second-feedback.md"
    first_feedback.write_text("First writer feedback.\n", encoding="utf-8")
    second_feedback.write_text("Second writer feedback.\n", encoding="utf-8")

    first_entered = threading.Event()
    release_first = threading.Event()
    first_status_committed = threading.Event()
    second_entered = threading.Event()
    second_queue_attempted = threading.Event()
    first_router = _FaultInjectableCoordRouter(
        write_dir=feature_dir,
        artifact_entered=first_entered,
        artifact_release=release_first,
        status_committed=first_status_committed,
    )
    second_router = _FaultInjectableCoordRouter(
        write_dir=feature_dir,
        artifact_entered=second_entered,
        artifact_wait_after_commit=first_status_committed,
    )

    real_queue = _tvp.acquire_verdict_save_queue

    @contextmanager
    def _observed_queue(
        repository: Path, *, timeout_seconds: float = 10.0
    ) -> Iterator[Path]:
        if threading.current_thread().name == "queued-rejection-second":
            second_queue_attempted.set()
        with real_queue(repository, timeout_seconds=timeout_seconds) as lock_path:
            yield lock_path

    monkeypatch.setattr(_tvp, "acquire_verdict_save_queue", _observed_queue)
    if drop_serialized_result:
        real_hop_result = _tmt._mt_hop_review_result

        def _drop_second_hop_result(
            st: _tmt._MoveTaskState,
            event: StatusEvent | None,
            current_event_lane: str,
            target: str,
            hop_actor: str,
        ) -> ReviewResult | None:
            result = real_hop_result(st, event, current_event_lane, target, hop_actor)
            if event is None and current_event_lane == Lane.PLANNED and target == Lane.PLANNED:
                return None
            return result

        monkeypatch.setattr(_tmt, "_mt_hop_review_result", _drop_second_hop_result)

    failures: list[BaseException] = []

    def _worker(args: _MoveTaskArgs, ports: TasksPorts) -> None:
        try:
            _do_move_task(args, ports=ports)
        except BaseException as exc:  # surfaced on the parent test thread
            failures.append(exc)

    with setup_mocked_env(
        repo,
        mission_slug=_MISSION,
        target_branch="main",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        first = threading.Thread(
            name="queued-rejection-first",
            target=_worker,
            args=(
                _rejection_args(first_feedback, "reviewer-first"),
                _fake_ports(feature_dir, first_router),
            ),
        )
        second = threading.Thread(
            name="queued-rejection-second",
            target=_worker,
            args=(
                _rejection_args(second_feedback, "reviewer-second"),
                _fake_ports(feature_dir, second_router),
            ),
        )
        first.start()
        assert first_entered.wait(5)
        second.start()
        assert second_queue_attempted.wait(5)
        assert not second_entered.is_set()
        release_first.set()
        first.join(10)
        second.join(10)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    if drop_serialized_result:
        with pytest.raises(AssertionError, match="second queued rejection lost"):
            _assert_queued_rejection_records(
                repo,
                feature_dir,
                first_router,
                second_router,
                first_feedback,
                second_feedback,
            )
    else:
        _assert_queued_rejection_records(
            repo,
            feature_dir,
            first_router,
            second_router,
            first_feedback,
            second_feedback,
        )


@pytest.mark.parametrize(
    "drop_serialized_result", [False, True], ids=["canonical", "causal-mutation"]
)
@pytest.mark.performance
def test_two_queued_rejections_completes_within_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drop_serialized_result: bool,
) -> None:
    """#4015 timing counterpart of ``..._preserve_each_exact_cycle_and_event``.

    Reruns the identical real-checkout-queue, two-thread choreography and
    asserts only the wall-clock budget; the functional per-write correctness
    assertions live on the per-PR sibling test above (verbatim, unmarked).
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    first_feedback = repo / "first-feedback.md"
    second_feedback = repo / "second-feedback.md"
    first_feedback.write_text("First writer feedback.\n", encoding="utf-8")
    second_feedback.write_text("Second writer feedback.\n", encoding="utf-8")

    first_entered = threading.Event()
    release_first = threading.Event()
    first_status_committed = threading.Event()
    second_entered = threading.Event()
    second_queue_attempted = threading.Event()
    first_router = _FaultInjectableCoordRouter(
        write_dir=feature_dir,
        artifact_entered=first_entered,
        artifact_release=release_first,
        status_committed=first_status_committed,
    )
    second_router = _FaultInjectableCoordRouter(
        write_dir=feature_dir,
        artifact_entered=second_entered,
        artifact_wait_after_commit=first_status_committed,
    )

    real_queue = _tvp.acquire_verdict_save_queue

    @contextmanager
    def _observed_queue(
        repository: Path, *, timeout_seconds: float = 10.0
    ) -> Iterator[Path]:
        if threading.current_thread().name == "queued-rejection-second":
            second_queue_attempted.set()
        with real_queue(repository, timeout_seconds=timeout_seconds) as lock_path:
            yield lock_path

    monkeypatch.setattr(_tvp, "acquire_verdict_save_queue", _observed_queue)
    if drop_serialized_result:
        real_hop_result = _tmt._mt_hop_review_result

        def _drop_second_hop_result(
            st: _tmt._MoveTaskState,
            event: StatusEvent | None,
            current_event_lane: str,
            target: str,
            hop_actor: str,
        ) -> ReviewResult | None:
            result = real_hop_result(st, event, current_event_lane, target, hop_actor)
            if event is None and current_event_lane == Lane.PLANNED and target == Lane.PLANNED:
                return None
            return result

        monkeypatch.setattr(_tmt, "_mt_hop_review_result", _drop_second_hop_result)

    def _worker(args: _MoveTaskArgs, ports: TasksPorts) -> None:
        # timing-only: correctness lives on the sibling per-PR test
        with suppress(BaseException):
            _do_move_task(args, ports=ports)

    started = time.monotonic()
    with setup_mocked_env(
        repo,
        mission_slug=_MISSION,
        target_branch="main",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        first = threading.Thread(
            name="queued-rejection-first",
            target=_worker,
            args=(
                _rejection_args(first_feedback, "reviewer-first"),
                _fake_ports(feature_dir, first_router),
            ),
        )
        second = threading.Thread(
            name="queued-rejection-second",
            target=_worker,
            args=(
                _rejection_args(second_feedback, "reviewer-second"),
                _fake_ports(feature_dir, second_router),
            ),
        )
        first.start()
        first_entered.wait(5)
        second.start()
        second_queue_attempted.wait(5)
        release_first.set()
        first.join(10)
        second.join(10)

    elapsed = time.monotonic() - started
    assert_timing_budget(elapsed, 10.0, name="two queued rejections")


def test_failed_transition_emit_is_reverted_leaving_no_committed_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T047/T048 GREEN: a transition-emit failure no longer leaves a committed
    orphan -- ``_mt_execute_with_verdict_revert`` catches the failure and
    ``revert_committed_verdict_write`` undoes the already-committed write
    before ``_do_move_task`` returns its error.

    ``exit_code`` (via ``typer.Exit``) is necessary but NOT sufficient: every
    assertion below queries RECORDED STATE directly.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    wp_dir = _wp_dir(repo)
    relpath = f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"

    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=True)
    ports = _fake_ports(feature_dir, coord)
    real_revert_held = _tvp._revert_committed_verdict_write_held
    compensation_queue_state: list[bool] = []

    def _observe_revert_queue(st: object, signal: object) -> None:
        compensation_queue_state.append(verdict_save_queue_is_held(repo))
        real_revert_held(st, signal)  # type: ignore[arg-type]

    monkeypatch.setattr(_tvp, "_revert_committed_verdict_write_held", _observe_revert_queue)

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(repo, ports=ports, note="Review passed")
    assert exc_info.value.exit_code == 1  # necessary, never sufficient (see below)
    assert compensation_queue_state == [True]

    # (a) No readable committed verdict for this WP -- queried via the KEPT
    # content loader (``ReviewCycleArtifact.latest``, squad #1), not raw file
    # listing. The reverted write must not be the latest: cycle 1 (rejected,
    # seeded by the fixture) is still the true latest.
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- ``cycle_number`` is the checkable proxy for "which
    # write is the reader-visible latest" (exactly what this assertion is
    # about: the reverted cycle-2 must not be promoted over cycle-1).
    latest = ReviewCycleArtifact.latest(wp_dir)
    assert latest is not None and latest.cycle_number == 1, (
        f"expected the pre-existing rejected cycle 1 to still be the reader-"
        f"visible latest after the revert, got {latest}"
    )

    # (b) The orphan file itself is gone from disk...
    artifact = wp_dir / "review-cycle-2.md"
    assert not artifact.exists(), (
        "the reverted verdict write is still present on disk -- the "
        "compensator did not delete it"
    )
    # ...AND not merely deleted-but-uncommitted (that would be a NEW,
    # partially-reverted orphan shape) -- HEAD's tree must not contain it,
    # and the working tree must be clean (the deletion itself was committed).
    assert not _git_head_has_file(repo, relpath), (
        "review-cycle-2.md is still reachable at HEAD -- the deletion was "
        "never committed (partially-reverted state)"
    )
    # Scoped to the WP's own tasks dir (not repo-wide): the fixture's own
    # ``status.events.jsonl`` is deliberately left untracked by ``_setup_
    # fixture`` (a different, unrelated concern from the verdict artifact)
    # and would otherwise be a false positive here.
    tasks_status = subprocess.run(
        ["git", "status", "--porcelain", "--", f"kitty-specs/{_MISSION}/tasks"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert tasks_status == "", (
        f"the WP's tasks dir is not clean after the revert-commit -- a "
        f"partially-reverted state (deleted but not committed, or vice "
        f"versa) must never occur:\n{tasks_status}"
    )
    # The OLD commit that introduced review-cycle-2.md still exists in
    # history (a revert-commit, not a rewrite) -- this is the correct,
    # honest shape: "no readable committed verdict AT HEAD", not "no trace
    # in history ever".
    log = _git_log_files(repo)
    assert "review-cycle-2.md" in log, (
        "the revert should be a NEW commit undoing the write, not a history "
        f"rewrite -- the original commit should still appear in git log:\n{log}"
    )

    # (c) The WP's lane is STILL in_review -- the transition never completed.
    lane = _read_transactional_wp_lane(
        feature_dir=feature_dir, mission_slug=_MISSION, wp_id=_WP_ID, repo_root=repo
    )
    assert lane == Lane.IN_REVIEW, (
        f"expected the lane to still be in_review after the failed transition emit, got {lane}"
    )


def test_retry_after_reverted_orphan_records_the_genuine_approval(
    tmp_path: Path,
) -> None:
    """T047/T048 GREEN, the SC-003 half: once the failed attempt's orphan is
    actually reverted (no longer merely tolerated), the retry is a genuine
    write again -- not a no-op guard short-circuit backed by stale data.

    This is the corrected form of the WP prompt's Objective-section claim
    (empirically disproven pre-fix, see the prior commit's Activity Log):
    the retry now records the RETRY's OWN ``--approval-ref``, because there
    is no orphan left for the no-op guard to treat as "already approved".
    ``exit_code == 0`` is asserted as necessary but never sufficient.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    wp_dir = _wp_dir(repo)

    failing_coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=True)
    with pytest.raises(typer.Exit):
        _run_move(
            repo,
            ports=_fake_ports(feature_dir, failing_coord),
            note="Review passed",
            approval_ref="approval:first-failed-attempt",
        )
    # Precondition: the failed attempt's write was actually reverted (proven
    # in detail by the sibling test) -- confirm no orphan survives to retry
    # against, so this test's own assertions mean what they claim to.
    assert not (wp_dir / "review-cycle-2.md").exists()
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- ``cycle_number`` is the checkable proxy here (the
    # pre-existing rejected cycle-1 is still the true latest).
    latest_before_retry = ReviewCycleArtifact.latest(wp_dir)
    assert latest_before_retry is not None and latest_before_retry.cycle_number == 1

    # Retry: SAME command, its OWN genuine approval_ref, failure removed.
    # Reaching the line after this call (no exception) is "exit 0" --
    # necessary, but per this test's own docstring, never sufficient on its
    # own; every assertion below queries what was actually recorded.
    retry_coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=False)
    _run_move(
        repo,
        ports=_fake_ports(feature_dir, retry_coord),
        note="Review passed",
        approval_ref="approval:genuine-retry",
    )

    # A GENUINE new write happened this time (cycle 2 again -- the deleted slot is free).
    assert len(retry_coord.status_calls) >= 1, (
        "the retry never even attempted the transition emit -- this test is "
        "not exercising the described retry path"
    )
    artifact = wp_dir / "review-cycle-2.md"
    assert artifact.exists(), (
        "the retry did not write a new verdict artifact -- with the orphan "
        "actually reverted, the no-op guard must not fire this time"
    )
    artifact_text = artifact.read_text(encoding="utf-8")
    assert "approval:genuine-retry" in artifact_text, (
        "the retry's OWN approval_ref did not make it into the recorded "
        "artifact -- 'records the correct verdict' (SC-003) is failing"
    )
    assert "approval:first-failed-attempt" not in artifact_text, (
        "the artifact still carries the FIRST FAILED attempt's stale "
        "reference -- the revert did not actually clear the prior write"
    )
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- the approval write's own synthesized body
    # ("Approved by ...") is the checkable proxy.
    latest_after_retry = ReviewCycleArtifact.latest(wp_dir)
    assert latest_after_retry is not None and latest_after_retry.body.startswith("Approved by ")

    status = _git_status(repo)
    assert "review-cycle-2.md" not in status, (
        f"the retry's write is not committed:\n{status}"
    )
    relpath = f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"
    assert _git_head_has_file(repo, relpath), (
        "the retry's genuine write is not reachable at HEAD"
    )

    lane_after_retry = _read_transactional_wp_lane(
        feature_dir=feature_dir, mission_slug=_MISSION, wp_id=_WP_ID, repo_root=repo
    )
    assert lane_after_retry == Lane.APPROVED, (
        f"expected the retry's transition emit to succeed and move the lane "
        f"to approved, got {lane_after_retry}"
    )


# ---------------------------------------------------------------------------
# T050: skip_target_branch_commit threaded to the review-cycle-artifact writer
# ---------------------------------------------------------------------------


@dataclass
class _ProtectedBranchRefusingCommitRouter:
    """Stub ``CoordCommitRouter`` whose ``commit_artifact`` simulates the real
    ``ProtectedBranchRefused`` outcome ``commit_for_mission`` returns for a
    protected target branch -- modeled on ``tests/review/test_cycle.py``'s
    ``_FailingCommitRouter``. ``commit_status``/``feature_write_dir`` assert
    if called: this stub exists to prove whether ``commit_artifact`` is even
    ATTEMPTED, not to exercise the transition-emit leg.
    """

    artifact_calls: list[Path] = field(default_factory=list)
    write_dir: Path | None = None

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        if self.write_dir is None:
            raise AssertionError("feature_write_dir is not used by this reproduction")
        return self.write_dir

    def commit_status(
        self, request: object, *, capability: GuardCapability
    ) -> CommitStatusResult:
        raise AssertionError("commit_status is not used by this reproduction")

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: object,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.artifact_calls.extend(paths)
        return CommitArtifactResult(
            status="error",
            placement_ref=str(paths[0]) if paths else "",
            diagnostic="simulated ProtectedBranchRefused: destination branch is protected",
        )


@dataclass
class _AdverseCommitRouter(_ProtectedBranchRefusingCommitRouter):
    behavior: str = "wrong_surface"

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: object,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.artifact_calls.extend(paths)
        if self.behavior == "raise":
            raise RuntimeError("simulated router exception")
        if self.behavior == "timeout":
            raise TimeoutError("simulated router timeout")
        if self.behavior == "error":
            return CommitArtifactResult(
                status="error",
                placement_ref="main",
                diagnostic="simulated returned router error",
            )
        return CommitArtifactResult(
            status="no_op_wrong_surface",
            placement_ref="main",
            diagnostic="simulated wrong-surface no-op",
        )


def _minimal_state(
    repo: Path,
    *,
    task_id: str = _WP_ID,
    mission_slug: str = _MISSION,
    resolved_auto_commit: bool,
    skip_target_branch_commit: bool,
    json_output: bool = False,
    approval_ref: str | None = None,
    note: str | None = None,
    resolved_feedback_source: Path | None = None,
) -> _tmt._MoveTaskState:
    st = _tmt._MoveTaskState(
        task_id=task_id,
        to="approved",
        mission=mission_slug,
        agent="testbot",
        assignee=None,
        shell_pid=None,
        note=note,
        review_feedback_file=None,
        approval_ref=approval_ref,
        reviewer="reviewer-renata",
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=resolved_auto_commit,
        json_output=json_output,
    )
    st.main_repo_root = repo
    st.mission_slug = mission_slug
    # WP05 (verdict-seam-write-unification-01KZ9Q35, T023) repoint:
    # ``_persist_approved_review_cycle``/``persist_rejected_review_cycle_for_
    # rollback`` now resolve ``event_sourced_review_result(st.feature_dir,
    # st.task_id)`` -- a hand-built state that skips the real orchestrator's
    # ``st.feature_dir = st.mt_feature_dir`` assignment (``tasks_move_task.
    # py``) left this at its dataclass default (``Path()`` == cwd), so the
    # probe silently read the WRONG directory's (nonexistent) event log and
    # always found "absent". Set it here to match what real orchestration
    # would have resolved for this flat-topology fixture.
    st.feature_dir = repo / "kitty-specs" / mission_slug
    st.resolved_auto_commit = resolved_auto_commit
    st.skip_target_branch_commit = skip_target_branch_commit
    st.note_text = note
    st.resolved_feedback_source = resolved_feedback_source
    return st


def _seed_rejected_cycle_1(repo: Path, mission_slug: str, wp_id: str) -> None:
    """A prior rejected cycle on disk, UNCOMMITTED -- sufficient for the
    no-op guard's precondition; this reproduction is not about that guard.

    WP05 repoint: also records the rejection's ``review_result`` on the
    event authority (see ``_seed_rejection_result_event``'s docstring) --
    the event-sourced probe this WP repointed needs it, not merely the
    on-disk artifact frontmatter the pre-WP05 probe used to read.
    """
    create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=mission_slug,
        wp_id=wp_id,
        wp_slug=f"{wp_id}-test",
        body="Needs another pass.\n",
        reviewer_agent="reviewer-renata",
        verdict="rejected",
    )
    _seed_rejection_result_event(repo / "kitty-specs" / mission_slug, wp_id, seq=0)


def test_pre_fix_naive_commit_router_gating_crashes_on_protected_target_branch(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T050 originally reproduced the PRE-FIX defect this WP's Objective
    section describes -- gating the review-cycle-artifact ``commit_router``
    on ``resolved_auto_commit`` ALONE (ignoring ``skip_target_branch_commit``,
    the naive expression this WP replaces) raised ``ReviewCycleError``
    uncaught on a protected-primary-coord topology.

    **WP05 (verdict-seam-write-unification-01KZ9Q35, T026/D-PLAN-11) INVERTS
    the failure mode this pins**: a non-``"committed"`` result is now a
    logged WARNING, never a raised ``ReviewCycleError`` -- so the naive gate
    no longer crashes either. What T050 actually cares about survives
    unchanged, though: the naive expression still ATTEMPTS a protected-branch
    ``commit_artifact`` call at all (an unwanted attempt the FIXED gate
    avoids entirely -- see ``test_protected_target_branch_completes_without_
    raising_after_fix``'s ``router.artifact_calls == []`` assertion), it just
    no longer crashes when that attempt is refused.

    This does not call ``_persist_approved_review_cycle`` itself (that
    function is ALREADY fixed in this diff) -- it inlines the exact
    pre-fix expression (``ports.coord if st.resolved_auto_commit else
    None``) verbatim to prove, in isolation, that the naive gate is what
    attempts the unwanted commit -- per the rule against reverting tracked
    files to observe pre-fix behaviour.
    """
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)

    st = _minimal_state(
        repo, resolved_auto_commit=True, skip_target_branch_commit=True
    )
    router = _ProtectedBranchRefusingCommitRouter()

    # The naive, pre-fix expression this WP replaces (tasks_verdict_
    # persistence.py's two call sites used to read exactly this).
    naive_commit_router = router if st.resolved_auto_commit else None

    with caplog.at_level("WARNING", logger="specify_cli.review.cycle"):
        create_rejected_review_cycle(
            main_repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            wp_id=st.task_id,
            wp_slug=f"{_WP_ID}-test",
            body="Approved by reviewer-renata: approval:WP01\n",
            reviewer_agent="reviewer-renata",
            verdict="approved",
            commit_router=naive_commit_router,
        )

    assert router.artifact_calls, (
        "the naive gate must still ATTEMPT the protected-branch commit -- "
        "that unwanted attempt, not a crash, is what the fixed gate avoids"
    )
    assert any(
        "Failed to commit review-cycle" in record.message for record in caplog.records
    ), (
        "the refused protected-branch commit must still be logged as a "
        f"WARNING (T026), never silently dropped; records={caplog.records}"
    )


def test_protected_target_branch_retains_evidence_but_refuses_automatic_success(
    tmp_path: Path,
) -> None:
    """T050 green: the FIXED ``_persist_approved_review_cycle`` (this diff)
    consults ``skip_target_branch_commit`` and passes ``commit_router=None``
    instead of attempting -- and crashing on -- the protected-branch commit.
    Both the approval and rejection call sites are exercised.
    """
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)

    st = _minimal_state(
        repo,
        resolved_auto_commit=True,
        skip_target_branch_commit=True,
        approval_ref="approval:WP01",
    )
    router = _ProtectedBranchRefusingCommitRouter()
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    with pytest.raises(_tvp.VerdictPersistenceFailure) as failure:
        _tvp._persist_approved_review_cycle(st, ports)
    signal = failure.value.signal

    assert router.artifact_calls == [], (
        "commit_artifact was invoked despite skip_target_branch_commit=True -- "
        "the protected-branch attempt should never happen"
    )
    assert signal is not None
    assert signal.durably_persisted is False
    assert signal.skip_reason == _tvp._DURABILITY_REASON_PROTECTED_TARGET_BRANCH

    wp_dir = _wp_dir(repo)
    artifact = wp_dir / "review-cycle-2.md"
    assert artifact.exists()
    # WP06 (FR-003/SC-007): ReviewCycleArtifact no longer carries a verdict
    # field -- the approval write's own synthesized body ("Approved by ...")
    # is the checkable proxy.
    assert "Approved by" in artifact.read_text(encoding="utf-8")

    # Rejection call site: same gating, exercised via a fresh rollback state.
    st2 = _minimal_state(
        repo,
        resolved_auto_commit=True,
        skip_target_branch_commit=True,
        resolved_feedback_source=None,
    )
    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: needs another look.\n", encoding="utf-8")
    st2.resolved_feedback_source = feedback
    router2 = _ProtectedBranchRefusingCommitRouter()
    ports2 = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router2,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    with pytest.raises(_tvp.VerdictPersistenceFailure) as failure2:
        _tvp.persist_rejected_review_cycle_for_rollback(st2, ports2)
    signal2 = failure2.value.signal
    assert router2.artifact_calls == []
    assert signal2.durably_persisted is False
    assert signal2.skip_reason == _tvp._DURABILITY_REASON_PROTECTED_TARGET_BRANCH


# ---------------------------------------------------------------------------
# T049: the --no-auto-commit durability signal (console notice half)
# ---------------------------------------------------------------------------


def test_no_auto_commit_announces_the_non_durable_write_on_console(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T049: ``--no-auto-commit`` is FR-013's ONE sanctioned non-durable path.
    The console notice (this module's owned half of the durability signal --
    the ``--json`` key requires ``_mt_output``/``_MoveTaskState`` in
    ``tasks_move_task.py``, outside this WP's ``owned_files``; see the
    module docstring and the WP11 report) must actually print, and the
    returned :class:`VerdictDurabilitySignal` must name the reason.
    """
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)

    st = _minimal_state(
        repo,
        resolved_auto_commit=False,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
        json_output=False,
    )
    router = _ProtectedBranchRefusingCommitRouter()  # asserts if commit_artifact is ever called
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    signal = _tvp._persist_approved_review_cycle(st, ports)

    assert router.artifact_calls == [], "no commit should be attempted at all"
    assert signal is not None
    assert signal.durably_persisted is False
    assert signal.skip_reason == _tvp._DURABILITY_REASON_NO_AUTO_COMMIT

    captured = capsys.readouterr()
    assert "written but NOT committed" in captured.out
    assert "--no-auto-commit" in captured.out

    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- the approval write's own synthesized body
    # ("Approved by ...") is the checkable proxy.
    latest = ReviewCycleArtifact.latest(_wp_dir(repo))
    assert latest is not None
    assert latest.body.startswith("Approved by ")


def test_json_output_suppresses_the_durability_console_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The console notice must stay silent under ``--json`` (matching this
    module's established ``if not json_output:`` pattern) -- a machine
    consumer is expected to read the (currently unwired) ``--json`` key
    instead, never a Rich-formatted console line.
    """
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)

    st = _minimal_state(
        repo,
        resolved_auto_commit=False,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
        json_output=True,
    )
    router = _ProtectedBranchRefusingCommitRouter()
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    signal = _tvp._persist_approved_review_cycle(st, ports)
    assert signal is not None
    assert signal.skip_reason == _tvp._DURABILITY_REASON_NO_AUTO_COMMIT

    captured = capsys.readouterr()
    assert captured.out == ""


def test_ordinary_auto_commit_path_reports_durably_persisted_true(
    tmp_path: Path,
) -> None:
    """The normal (auto-commit, not protected) path must report
    ``durably_persisted=True, skip_reason=None`` -- the DoD requirement that
    the key is present/true (not merely absent) on every other path.
    """
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)

    st = _minimal_state(
        repo,
        resolved_auto_commit=True,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
    )
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=RealCoordCommitRouter(),
        git=FakeGitOps(),
        render=FakeRender(),
    )

    signal = _tvp._persist_approved_review_cycle(st, ports)

    assert signal is not None
    assert signal.durably_persisted is True
    assert signal.skip_reason is None
    status = _git_status(repo)
    assert "review-cycle-2.md" not in status, f"expected a real commit:\n{status}"


def test_automatic_verdict_commit_runs_inside_checkout_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T017: automatic allocation/commit/read-back owns the checkout queue."""
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)
    st = _minimal_state(
        repo,
        resolved_auto_commit=True,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
    )
    observed: list[bool] = []
    real_create = _tvp.create_rejected_review_cycle

    def _observing_create(**kwargs: object) -> object:
        observed.append(verdict_save_queue_is_held(repo))
        return real_create(**kwargs)  # type: ignore[arg-type, no-any-return]

    monkeypatch.setattr(_tvp, "create_rejected_review_cycle", _observing_create)
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=RealCoordCommitRouter(),
        git=FakeGitOps(),
        render=FakeRender(),
    )

    signal = _tvp._persist_approved_review_cycle(st, ports)

    assert signal is not None and signal.outcome.classification == "durable"
    assert observed == [True]
    assert verdict_save_queue_is_held(repo) is False


def test_evidence_git_runs_without_allocation_lock_and_inside_checkout_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T017/T019: directly observe evidence staging and read-back in Git."""
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _unprotect_main(repo)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)
    st = _minimal_state(
        repo,
        resolved_auto_commit=True,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
    )
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=RealCoordCommitRouter(),
        git=FakeGitOps(),
        render=FakeRender(),
    )
    real_status_lock = _review_cycle.feature_status_lock
    real_subprocess_run = subprocess.run
    allocation_lock_depth = 0
    observations: list[tuple[str, bool, bool]] = []

    @contextmanager
    def _observing_status_lock(*args: object, **kwargs: object) -> Iterator[None]:
        nonlocal allocation_lock_depth
        with real_status_lock(*args, **kwargs):  # type: ignore[arg-type]
            allocation_lock_depth += 1
            try:
                yield
            finally:
                allocation_lock_depth -= 1

    def _observing_subprocess_run(
        command: Sequence[str], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        invocation: str | None = None
        if (
            len(command) == 5
            and command[:4] == ["git", "add", "--force", "--"]
            and command[4].endswith("review-cycle-2.md")
        ):
            invocation = "stage"
        elif (
            len(command) == 3
            and command[:2] == ["git", "show"]
            and command[2].endswith("review-cycle-2.md")
        ):
            invocation = "readback"
        if invocation is not None:
            observations.append(
                (
                    invocation,
                    allocation_lock_depth > 0,
                    verdict_save_queue_is_held(repo),
                )
            )
        return real_subprocess_run(command, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(_review_cycle, "feature_status_lock", _observing_status_lock)
    monkeypatch.setattr(_review_cycle.subprocess, "run", _observing_subprocess_run)

    signal = _tvp._persist_approved_review_cycle(st, ports)

    assert signal is not None and signal.outcome.classification == "durable"
    assert observations == [
        ("stage", False, True),
        ("readback", False, True),
    ]


def test_local_only_verdict_bypasses_checkout_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T020: local-only remains non-durable and never acquires the queue."""
    repo = tmp_path
    _init_repo(repo)
    _build_wp_file(repo, _MISSION, _WP_ID)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    _seed_rejected_cycle_1(repo, _MISSION, _WP_ID)
    st = _minimal_state(
        repo,
        resolved_auto_commit=False,
        skip_target_branch_commit=False,
        approval_ref="approval:WP01",
    )
    observed: list[bool] = []
    real_create = _tvp.create_rejected_review_cycle

    def _observing_create(**kwargs: object) -> object:
        observed.append(verdict_save_queue_is_held(repo))
        return real_create(**kwargs)  # type: ignore[arg-type, no-any-return]

    monkeypatch.setattr(_tvp, "create_rejected_review_cycle", _observing_create)
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
        coord=_ProtectedBranchRefusingCommitRouter(),
        git=FakeGitOps(),
        render=FakeRender(),
    )

    signal = _tvp._persist_approved_review_cycle(st, ports)

    assert signal is not None and signal.outcome.classification == "local_only"
    assert observed == [False]


def test_queue_busy_fails_before_evidence_allocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T017/T021: real command maps bounded queue refusal without mutation."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)

    def _busy_queue(*_args: object, **_kwargs: object) -> object:
        raise VerdictSaveBusy(repo / ".git" / "busy.lock", 10.0)

    monkeypatch.setattr(_tvp, "acquire_verdict_save_queue", _busy_queue)
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir)

    with pytest.raises(typer.Exit) as failure:
        _run_move(repo, ports=_fake_ports(feature_dir, coord), note="Review passed")

    assert failure.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["result"] == "error"
    assert payload["durability_classification"] == "busy"
    assert payload["durability_reason"] == "verdict_save_busy"
    assert payload["verdict_durably_persisted"] is False
    assert payload["evidence_ref"] is None
    assert payload["destination_ref"] is None
    assert "event_id" not in payload
    assert not (_wp_dir(repo) / "review-cycle-2.md").exists()
    assert _approved_verdict_events(feature_dir) == []
    assert coord.status_calls == []
    assert _read_transactional_wp_lane(
        feature_dir=feature_dir, mission_slug=_MISSION, wp_id=_WP_ID, repo_root=repo
    ) == Lane.IN_REVIEW


def test_automatic_commit_failure_is_error_envelope_and_emits_no_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T018/T021/T022: retained evidence cannot masquerade as command success."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    router = _ProtectedBranchRefusingCommitRouter(write_dir=feature_dir)
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(repo, ports=ports, note="Review passed")

    assert exc_info.value.exit_code == 1
    assert router.artifact_calls
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["result"] == "error"
    assert payload["verdict_durably_persisted"] is False
    assert payload["durability_classification"] == "persistence_failed"
    assert payload["durability_reason"] == "commit_error"
    assert payload["evidence_ref"].endswith("review-cycle-2.md")
    assert payload["destination_ref"].endswith("review-cycle-2.md")
    assert "event_id" not in payload


def test_invalid_transition_is_structured_refusal_without_event_or_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A post-queue state race reports the locked lane without message parsing."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    feedback = repo / "concurrent-feedback.md"
    feedback.write_text("A distinct concurrent rejection.\n", encoding="utf-8")
    events_before = [event.event_id for event in read_events(feature_dir)]
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir)

    def _refuse_transition(
        _request: TransitionRequest, *, capability: GuardCapability
    ) -> CommitStatusResult:
        del capability
        raise TransitionError("opaque concurrent state refusal")

    monkeypatch.setattr(coord, "commit_status", _refuse_transition)
    real_current_lane: Callable[[_tmt._MoveTaskState], str] = (
        _tmt._mt_current_event_lane
    )
    lane_reads = 0

    def _authoritative_lane_changed(st: _tmt._MoveTaskState) -> str:
        nonlocal lane_reads
        lane_reads += 1
        if lane_reads == 1:
            return real_current_lane(st)
        return str(Lane.PLANNED.value)

    monkeypatch.setattr(_tmt, "_mt_current_event_lane", _authoritative_lane_changed)

    with pytest.raises(typer.Exit) as failure:
        _run_move(
            repo,
            ports=_fake_ports(feature_dir, coord),
            to="planned",
            review_feedback_file=feedback,
            reviewer="reviewer-refused",
        )

    assert failure.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload == {
        "result": "error",
        "code": "invalid_transition",
        "error": "opaque concurrent state refusal",
        "current_lane": "planned",
        "requested_lane": "planned",
        "verdict_durably_persisted": False,
        "evidence_ref": None,
        "destination_ref": None,
    }
    assert [event.event_id for event in read_events(feature_dir)] == events_before
    assert not (_wp_dir(repo) / "review-cycle-2.md").exists()
    assert not _git_head_has_file(
        repo, f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"
    )


@pytest.mark.parametrize(
    ("behavior", "expected_reason"),
    [
        ("error", "commit_error"),
        ("wrong_surface", "wrong_surface"),
        ("raise", "commit_exception"),
        ("timeout", "commit_timeout"),
    ],
)
def test_adverse_automatic_commit_outcomes_are_typed_and_retain_evidence(
    tmp_path: Path,
    behavior: str,
    expected_reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T021: real command makes every adverse router outcome explicit."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    router = _AdverseCommitRouter(write_dir=feature_dir, behavior=behavior)
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=router,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    with pytest.raises(typer.Exit) as failure:
        _run_move(repo, ports=ports, note="Review passed")

    assert failure.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["result"] == "error"
    assert payload["durability_classification"] == "persistence_failed"
    assert payload["durability_reason"] == expected_reason
    assert payload["verdict_durably_persisted"] is False
    assert payload["evidence_ref"].endswith("review-cycle-2.md")
    assert (repo / payload["evidence_ref"]).exists()
    assert payload["destination_ref"] is not None
    assert "event_id" not in payload
    assert _approved_verdict_events(feature_dir) == []
    assert not _git_head_has_file(
        repo, f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"
    )
    assert _read_transactional_wp_lane(
        feature_dir=feature_dir, mission_slug=_MISSION, wp_id=_WP_ID, repo_root=repo
    ) == Lane.IN_REVIEW


@pytest.mark.parametrize("behavior", ["error", "raise"])
def test_real_command_retry_adopts_retained_failure_without_duplicate(
    tmp_path: Path,
    behavior: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T021: identical returned/raised-failure retries adopt cycle 2."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    failing_router = _AdverseCommitRouter(write_dir=feature_dir, behavior=behavior)
    failing_ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=failing_router,
        git=FakeGitOps(),
        render=FakeRender(),
    )
    approval_ref = "approval:identical-retry"

    with pytest.raises(typer.Exit) as first_failure:
        _run_move(
            repo,
            ports=failing_ports,
            note="Review passed",
            approval_ref=approval_ref,
        )
    assert first_failure.value.exit_code == 1
    first_payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    retained_ref = first_payload["evidence_ref"]
    retained_path = repo / retained_ref
    assert retained_path.exists()
    assert retained_path.name == "review-cycle-2.md"
    assert _approved_verdict_events(feature_dir) == []

    succeeding_router = _FaultInjectableCoordRouter(write_dir=feature_dir)
    _run_move(
        repo,
        ports=_fake_ports(feature_dir, succeeding_router),
        note="Review passed",
        approval_ref=approval_ref,
    )
    success_payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert success_payload["result"] == "success"
    assert success_payload["evidence_ref"] == retained_ref
    assert success_payload["verdict_durably_persisted"] is True
    assert retained_path.exists()
    assert not (retained_path.parent / "review-cycle-3.md").exists()
    assert _git_head_has_file(repo, retained_ref)
    approved_events = _approved_verdict_events(feature_dir)
    assert len(approved_events) == 1
    _assert_event_references_durable_evidence(repo, approved_events[0], success_payload)
    assert approved_events[0].review_result is not None
    assert approved_events[0].review_result.reference != approval_ref


def test_real_command_retry_after_post_commit_interruption_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """T021: a process interruption after evidence commit adopts, never duplicates."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    real_execute = _tmt._mt_execute
    first_router = _FaultInjectableCoordRouter(write_dir=feature_dir)
    approval_ref = "approval:post-commit-interruption"

    def _interrupt_before_event(_st: object, _ports: object) -> None:
        raise KeyboardInterrupt("simulated response interruption after evidence commit")

    monkeypatch.setattr(_tmt, "_mt_execute", _interrupt_before_event)
    with pytest.raises(KeyboardInterrupt, match="response interruption"):
        _run_move(
            repo,
            ports=_fake_ports(feature_dir, first_router),
            note="Review passed",
            approval_ref=approval_ref,
        )

    retained_path = _wp_dir(repo) / "review-cycle-2.md"
    retained_ref = retained_path.relative_to(repo).as_posix()
    assert retained_path.exists()
    assert _git_head_has_file(repo, retained_ref)
    assert _approved_verdict_events(feature_dir) == []
    assert not (retained_path.parent / "review-cycle-3.md").exists()

    monkeypatch.setattr(_tmt, "_mt_execute", real_execute)
    retry_router = _FaultInjectableCoordRouter(write_dir=feature_dir)
    _run_move(
        repo,
        ports=_fake_ports(feature_dir, retry_router),
        note="Review passed",
        approval_ref=approval_ref,
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert payload["result"] == "success"
    assert payload["evidence_ref"] == retained_ref
    assert not (retained_path.parent / "review-cycle-3.md").exists()
    assert _git_log_files(repo).count("review-cycle-2.md") == 1
    approved_events = _approved_verdict_events(feature_dir)
    assert len(approved_events) == 1
    _assert_event_references_durable_evidence(repo, approved_events[0], payload)
    assert approved_events[0].review_result is not None
    assert approved_events[0].review_result.reference != approval_ref
    assert approval_ref in (repo / str(payload["evidence_ref"])).read_text(encoding="utf-8")


def test_verified_approval_event_never_rebuilds_reference_from_approval_ref(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T019: verified cycle identity, never the caller token, reaches the event."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    approval_ref = "approval:not-durable-evidence"

    _run_move(
        repo,
        ports=_fake_ports(feature_dir, _FaultInjectableCoordRouter(write_dir=feature_dir)),
        note="Review passed",
        approval_ref=approval_ref,
    )
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    approved_events = _approved_verdict_events(feature_dir)

    assert len(approved_events) == 1
    _assert_event_references_durable_evidence(repo, approved_events[0], payload)
    assert approved_events[0].review_result is not None
    assert approved_events[0].review_result.reference != approval_ref


def test_queue_is_released_before_event_status_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T017/T019: event/status mutation begins only after queue release."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    real_execute = _tmt._mt_execute
    observed: list[bool] = []

    def _observing_execute(st: _tmt._MoveTaskState, ports: TasksPorts) -> None:
        observed.append(verdict_save_queue_is_held(repo))
        real_execute(st, ports)

    monkeypatch.setattr(_tmt, "_mt_execute", _observing_execute)
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=False)

    _run_move(repo, ports=_fake_ports(feature_dir, coord), note="Review passed")

    assert observed == [False]


# ---------------------------------------------------------------------------
# T048: the in-line _mt_execute/revert wrap inside _do_move_task
# ---------------------------------------------------------------------------
#
# Note (report-worthy): T048's compensator is wrapped IN-LINE inside
# ``_do_move_task`` rather than factored into a new named top-level helper.
# A new native top-level symbol in ``tasks_move_task.py`` would ALSO need a
# row in ``test_tasks_compat_surface.py``'s consolidated re-export guard
# (``test_guard_keyset_is_superset_of_all_six_seams_native_defs``) plus an
# identity re-export on ``tasks.py`` to satisfy Guard 1 there -- both files
# outside this WP's two named widened purposes. Keeping the wrap inline
# avoids that third file entirely, matching "keep the diff minimal and
# surgical". These tests exercise it end-to-end through ``_do_move_task``
# instead of unit-testing a standalone function.


def _raising_mt_execute(_st: object, _ports: object) -> None:
    raise RuntimeError("simulated unrelated execute failure")


def test_execute_failure_without_pending_write_reports_the_original_error_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No verdict write happened this invocation (``_mt_finalize_plan``
    stubbed to a no-op, so ``pending_verdict_write`` stays ``None`` -- mirrors
    a plain claim/for_review transition with no review-cycle involved). A
    transition-emit failure must surface UNCHANGED: no revert attempted
    (nothing to revert), and the reported error is the ORIGINAL message only
    -- no compensator text.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    monkeypatch.setattr(_tmt, "_mt_finalize_plan", lambda st, ports: None)
    monkeypatch.setattr(_tmt, "_mt_execute", _raising_mt_execute)
    revert_calls: list[object] = []
    monkeypatch.setattr(
        _tmt, "revert_committed_verdict_write", lambda *a: revert_calls.append(a)
    )
    ports = _fake_ports(feature_dir, _FaultInjectableCoordRouter(write_dir=feature_dir))

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(repo, ports=ports, note="Review passed")
    assert exc_info.value.exit_code == 1
    assert revert_calls == [], "the compensator ran with nothing to revert"

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error"] == "simulated unrelated execute failure"


def test_execute_failure_with_failed_revert_surfaces_a_compound_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A durable write DID happen (real ``_mt_finalize_plan``); the compensator
    itself then fails to undo it (stubbed ``VerdictRevertError``). This is a
    COMPOUNDED failure and must NOT be silently swallowed into the original
    error -- both messages must be visible to the operator.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    monkeypatch.setattr(_tmt, "_mt_execute", _raising_mt_execute)

    def _failing_revert(_st: object, _signal: object) -> None:
        raise _tvp.VerdictRevertError("simulated revert-commit failure")

    monkeypatch.setattr(_tmt, "revert_committed_verdict_write", _failing_revert)
    ports = _fake_ports(feature_dir, _FaultInjectableCoordRouter(write_dir=feature_dir))

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(repo, ports=ports, note="Review passed", approval_ref="approval:WP01")
    assert exc_info.value.exit_code == 1

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert "simulated unrelated execute failure" in payload["error"]
    assert "simulated revert-commit failure" in payload["error"]
    # #3773 item 2: this compound path must carry a STRUCTURED durability
    # field, not just prose -- the write itself genuinely landed (real
    # ``_mt_finalize_plan`` ran before the stubbed revert failure), only the
    # compensating undo failed.
    assert payload["result"] == "error"
    assert payload["verdict_durably_persisted"] is True
    assert payload["durability_classification"] == "durable"
    assert payload["evidence_ref"] is not None


def test_execute_failure_with_revert_queue_busy_surfaces_durably_persisted_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#3773 item 2: the SPECIFIC compound shape the hardening item names --
    ``revert_committed_verdict_write`` catches ``VerdictSaveBusy`` while
    trying to acquire the checkout-wide queue for the REVERT itself (a
    genuine, real transition-emit failure via ``_FaultInjectableCoordRouter``,
    not a stubbed ``_mt_execute``/``revert_committed_verdict_write``).

    The original verdict write already landed durably (the real writer runs
    to completion before the emit fails); only the compensator's OWN queue
    acquisition is faulted, so ``revert_committed_verdict_write`` never even
    reaches its unlink/commit step. The resulting compound-failure envelope
    must still be fail-loud (non-zero exit, ``result: error``) AND carry a
    structured ``verdict_durably_persisted: true`` -- a machine consumer must
    not have to infer "the verdict is actually safe" from prose alone.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=True)
    ports = _fake_ports(feature_dir, coord)

    real_acquire = _tvp.acquire_verdict_save_queue
    calls: list[Path] = []

    def _acquire_then_busy(
        repository: Path, *, timeout_seconds: float = 10.0
    ) -> AbstractContextManager[Path]:
        calls.append(repository)
        if len(calls) == 1:
            # The ORIGINAL write's own queue acquisition -- must succeed for
            # real, so the write is genuinely durable by the time the
            # transition-emit failure (and the revert attempt) happens.
            # ``no-any-return``: same pre-existing artifact as this file's
            # other ``real_*(...)`` forwarders (e.g. ``_observing_create``
            # above) -- ``[[tool.mypy.overrides]] follow_imports = "skip"``
            # for ``specify_cli.*`` makes this cross-module call resolve to
            # ``Any`` only when this test file is type-checked in isolation.
            return real_acquire(repository, timeout_seconds=timeout_seconds)  # type: ignore[no-any-return]
        raise VerdictSaveBusy(repo / ".git" / "busy.lock", 10.0)

    monkeypatch.setattr(_tvp, "acquire_verdict_save_queue", _acquire_then_busy)

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(repo, ports=ports, note="Review passed", approval_ref="approval:WP01")
    assert exc_info.value.exit_code == 1
    assert len(calls) == 2, "expected exactly one write-queue and one revert-queue acquisition"

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["result"] == "error"
    assert "T047: simulated transition-emit failure" in payload["error"]
    assert "could not acquire" in payload["error"]
    assert payload["verdict_durably_persisted"] is True
    assert payload["durability_classification"] == "durable"
    assert payload["evidence_ref"] is not None
    assert payload["destination_ref"] is not None

    # Not merely a claimed durability: the write is REALLY still on disk and
    # committed at HEAD -- the compensator never got to attempt the delete,
    # since queue acquisition failed before that step.
    wp_dir = _wp_dir(repo)
    assert (wp_dir / "review-cycle-2.md").exists()
    relpath = f"kitty-specs/{_MISSION}/tasks/{_WP_ID}-test/review-cycle-2.md"
    assert _git_head_has_file(repo, relpath)


# ---------------------------------------------------------------------------
# T049/T050: end-to-end --json wiring (_mt_output, tasks_move_task.py)
# ---------------------------------------------------------------------------


def test_json_output_surfaces_durably_persisted_true_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The durability signal computed in ``tasks_verdict_persistence.py``
    actually reaches the ``--json`` envelope ``_mt_output`` builds in
    ``tasks_move_task.py`` -- the ownership-widening wiring this WP was
    escalated for, not just the unit-level signal computation.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=False)
    _run_move(repo, ports=_fake_ports(feature_dir, coord), note="Review passed")

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["verdict_durably_persisted"] is True
    assert payload["durability_classification"] == "durable"
    assert payload["durability_reason"] is None
    assert payload["evidence_ref"].endswith("WP01-test/review-cycle-2.md")
    assert payload["review_feedback"].endswith("WP01-test/review-cycle-2.md")
    assert payload["destination_ref"] == "main"
    assert "verdict_durability_skip_reason" not in payload


def test_json_output_surfaces_skip_reason_end_to_end_for_no_auto_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--no-auto-commit`` end-to-end: the ``--json`` envelope carries both
    keys (explicit ``false``, plus the distinguishing reason) -- never a bare
    missing key for a machine consumer to infer non-durability from.
    """
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=False)
    approval_ref = "approval:local-only-token"
    _run_move(
        repo,
        ports=_fake_ports(feature_dir, coord),
        note="Review passed",
        approval_ref=approval_ref,
        auto_commit=False,
    )

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["verdict_durably_persisted"] is False
    assert payload["durability_classification"] == "local_only"
    assert payload["durability_reason"] == "no_auto_commit"
    assert payload["destination_ref"] is None
    assert payload["verdict_durability_skip_reason"] == "no_auto_commit"
    approved_events = _approved_verdict_events(feature_dir)
    assert len(approved_events) == 1
    assert approved_events[0].review_result is not None
    assert approved_events[0].review_result.reference == approval_ref
    assert approved_events[0].review_result.feedback_path is None


def test_json_ownership_refusal_is_typed_and_writes_no_verdict_authority(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A policy-valid refusal remains nonzero and proves it wrote nothing."""
    repo = tmp_path
    feature_dir = _setup_fixture(repo)
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01M0A7E17A0000000000000000",
                wp_id=_WP_ID,
                at="2026-01-01T00:03:00+00:00",
                actor="reviewer-b",
                delta=WPInnerStateDelta(agent="reviewer-b"),
            )
        ],
    )
    coord = _FaultInjectableCoordRouter(write_dir=feature_dir, emit_should_fail=False)
    feedback = repo / "reviewer-a-feedback.md"
    feedback.write_text("Reviewer A requests changes.\n", encoding="utf-8")
    events_before = [event.event_id for event in read_events(feature_dir)]
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(
            repo,
            ports=_fake_ports(feature_dir, coord),
            to="planned",
            review_feedback_file=feedback,
            reviewer="reviewer-a",
            agent="reviewer-a",
        )
    assert exc_info.value.exit_code == 1

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload == {
        "result": "error",
        "code": "ownership_refusal",
        "error": (
            "Agent mismatch: WP01 is assigned to 'reviewer-b', not "
            "'reviewer-a'. Use --force to override."
        ),
        "current_lane": "in_review",
        "requested_lane": "planned",
        "assigned_agent": "reviewer-b",
        "requesting_agent": "reviewer-a",
        "verdict_durably_persisted": False,
        "evidence_ref": None,
        "destination_ref": None,
    }
    assert "event_id" not in payload
    assert [event.event_id for event in read_events(feature_dir)] == events_before
    assert coord.status_calls == []
    assert not (_wp_dir(repo) / "review-cycle-2.md").exists()
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head_after == head_before
