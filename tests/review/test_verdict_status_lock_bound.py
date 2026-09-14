"""Regression test for #3773 item 1 (PR #3712 hardening): bound the in-queue
``feature_status_lock`` wait so a verdict save can never hang indefinitely
behind a wedged (not crashed) per-mission status-lock holder.

PR #3712 gave the checkout-wide verdict-save queue
(``specify_cli.review.verdict_commit_queue.acquire_verdict_save_queue``) a
bounded ~10s acquisition (``VerdictSaveBusy`` on timeout -- see
``tests/review/test_verdict_commit_queue.py``). But the queue-holder still
calls straight into ``create_rejected_review_cycle`` (``review/cycle.py``),
which acquires the SEPARATE per-mission ``feature_status_lock`` for its own
cycle-allocation critical section (``_allocate_and_write_review_cycle_locked``
/ ``_adopt_or_allocate_review_cycle_locked``) with the library DEFAULT
``timeout=-1`` -- block forever (``status/locking.py``). A wedged status-lock
holder -- NOT a crashed one, so OS lock cleanup never intervenes either --
therefore made the queue-holder (and every other verdict save behind it) hang
forever, only partially honouring the "10s bounded wait" the queue's own
tests pin.

This test holds ``feature_status_lock`` from a SEPARATE, real OS process
(mirroring ``test_verdict_commit_queue.py``'s own spawn-based owner/contender
pattern -- the identical mechanism already proven for the queue's own lock),
then drives the exact production orchestration seam
(``tasks_verdict_persistence._persist_review_cycle_with_queue`` -- the ONE
function that owns the checkout-wide queue acquisition around the complete
allocate/commit/read-back call, per its own docstring) from a background
thread in THIS process, bounded by a finite ``Thread.join(timeout=...)``
rather than letting an unbounded call block the test suite itself.

Before the fix this test fails outright: the join times out with the driver
thread still blocked inside ``feature_status_lock`` -- captured as explicit
RED evidence, not a suite hang. After the fix, the call returns within
``DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS`` plus a generous margin and raises
``VerdictPersistenceFailure`` reporting the SAME truthful, non-durable
``VerdictSaveBusy``-shaped outcome (``verdict_durably_persisted=False``,
``classification="busy"``) the queue's own timeout already produces --
distinguished only by its own ``feature_status_lock_busy`` reason.
"""

from __future__ import annotations

import multiprocessing
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from specify_cli.agent_tasks_ports import TasksPorts
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState
from specify_cli.cli.commands.agent.tasks_verdict_persistence import (
    VerdictPersistenceFailure,
    _persist_review_cycle_with_queue,
)
from specify_cli.review.cycle import CreatedRejectedReviewCycle, create_rejected_review_cycle
from specify_cli.review.verdict_commit_queue import DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS
from specify_cli.status import FeatureStatusLockTimeoutError, feature_status_lock
from tests._perf_helpers import assert_timing_budget
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

if TYPE_CHECKING:
    from specify_cli.agent_tasks_ports import CoordCommitRouter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "verdict-lock-bound"
_WP_ID = "WP01"
_WP_SLUG = f"{_WP_ID}-core"

#: Generous ceiling above the production budget -- this pins "bounded by
#: roughly that budget", not "instantaneous". A single named constant
#: (Sonar S1192) rather than a repeated literal at each use site below.
_JOIN_CEILING_SECONDS = DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS + 10.0


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)


def _build_fixture(repo: Path) -> None:
    """A real git repo with one WP task file -- the minimal shape
    ``create_rejected_review_cycle`` needs (mirrors ``test_cycle.py``'s own
    ``test_create_rejected_review_cycle_commits_the_written_artifact``
    fixture; no ``meta.json``/``lanes.json`` required for a flat mission)."""
    _init_repo(repo)
    tasks_dir = repo / "kitty-specs" / _MISSION / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / f"{_WP_SLUG}.md").write_text(f"# {_WP_ID}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)


def _hold_status_lock_until_released(repository: str, mission: str, ready: Any, release: Any) -> None:
    """Spawn-safe worker: acquire the REAL per-mission status lock and hold it.

    Its own 60s acquisition timeout is a deadlock backstop for this worker
    only -- it is never the lock under test (that is the PARENT process's
    acquisition, inside the verdict-save call below).
    """
    with feature_status_lock(Path(repository), mission, timeout=60.0):
        ready.send(True)
        if not release.wait(30):
            raise TimeoutError("parent did not release the status lock")


def _build_state(repo: Path) -> _MoveTaskState:
    """A minimal ``_MoveTaskState`` -- only the fields
    ``_persist_review_cycle_with_queue`` itself actually reads (mirrors
    ``test_tasks_move_task_seam.py``'s own minimal-state-plus-overrides
    idiom)."""
    state = _MoveTaskState(
        task_id=_WP_ID,
        to="planned",
        mission=_MISSION,
        agent="test-agent",
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
        auto_commit=True,
        json_output=True,
    )
    state.main_repo_root = repo
    state.mission_slug = _MISSION
    state.resolved_auto_commit = True
    state.skip_target_branch_commit = False
    return state


def test_wedged_status_lock_yields_bounded_busy_failure_not_a_hang(tmp_path: Path) -> None:
    """A live, wedged ``feature_status_lock`` holder must not hang a verdict save.

    RED (pre-fix): ``feature_status_lock`` inside ``create_rejected_review_
    cycle`` uses the library default ``timeout=-1`` -- the driver thread below
    never finishes and ``thread.join(_JOIN_CEILING_SECONDS)`` times out with
    the thread still alive, failing the ``not driver.is_alive()`` assertion.

    GREEN (post-fix): the driver thread finishes within
    ``DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS`` (bounded by the SAME budget the
    checkout-wide queue already uses) and raises ``VerdictPersistenceFailure``
    whose signal reports ``verdict_durably_persisted=False`` and the
    ``feature_status_lock_busy`` reason.
    """
    repo = tmp_path
    _build_fixture(repo)
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: exercising the wedged status lock.\n", encoding="utf-8")

    def _create(commit_router: CoordCommitRouter | None) -> CreatedRejectedReviewCycle:
        return create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=_MISSION,
            wp_id=_WP_ID,
            wp_slug=_WP_SLUG,
            feedback_source=feedback,
            reviewer_agent="reviewer-lock-test",
            commit_router=commit_router,
        )

    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    release = context.Event()
    holder = context.Process(
        target=_hold_status_lock_until_released,
        args=(str(repo), _MISSION, child, release),
    )
    holder.start()
    child.close()
    try:
        assert parent.poll(10), "spawned holder never acquired the status lock"
        assert parent.recv() is True

        ports = TasksPorts(
            fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
            coord=FakeCoordCommitRouter(write_dir=repo / "kitty-specs" / _MISSION),
            git=FakeGitOps(),
            render=FakeRender(),
        )
        state = _build_state(repo)

        outcome: list[BaseException | None] = []

        def _drive() -> None:
            try:
                _persist_review_cycle_with_queue(state, ports, _create)
            except BaseException as exc:  # noqa: BLE001 - captured for assertion, not swallowed
                outcome.append(exc)
            else:
                outcome.append(None)

        driver = threading.Thread(target=_drive, daemon=True)
        driver.start()
        driver.join(_JOIN_CEILING_SECONDS)

        assert not driver.is_alive(), (
            "the verdict-save call did not return within "
            f"{_JOIN_CEILING_SECONDS:g}s while feature_status_lock was held by a "
            "separate, live (wedged, not crashed) process -- it must be bounded by "
            "the SAME budget the checkout-wide verdict-save queue already uses, "
            "never an unbounded hang"
        )

        assert len(outcome) == 1
        [captured] = outcome
        assert isinstance(captured, VerdictPersistenceFailure), f"expected a typed VerdictPersistenceFailure, got: {captured!r}"
        signal = captured.signal
        assert signal.outcome.verdict_durably_persisted is False
        assert signal.outcome.classification == "busy"
        assert signal.outcome.reason == "feature_status_lock_busy"
        assert isinstance(captured.__cause__, FeatureStatusLockTimeoutError)
    finally:
        release.set()
        holder.join(timeout=10)
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=10)
        parent.close()


@pytest.mark.performance
def test_wedged_status_lock_busy_failure_stays_within_the_join_ceiling(tmp_path: Path) -> None:
    """The wedged-status-lock busy failure returns within ``_JOIN_CEILING_SECONDS`` (nightly).

    Split from ``test_wedged_status_lock_yields_bounded_busy_failure_not_a_hang``
    (#4015); budget preserved.
    """
    repo = tmp_path
    _build_fixture(repo)
    feedback = repo / "feedback.md"
    feedback.write_text("**Issue**: exercising the wedged status lock.\n", encoding="utf-8")

    def _create(commit_router: CoordCommitRouter | None) -> CreatedRejectedReviewCycle:
        return create_rejected_review_cycle(
            main_repo_root=repo,
            mission_slug=_MISSION,
            wp_id=_WP_ID,
            wp_slug=_WP_SLUG,
            feedback_source=feedback,
            reviewer_agent="reviewer-lock-test",
            commit_router=commit_router,
        )

    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    release = context.Event()
    holder = context.Process(
        target=_hold_status_lock_until_released,
        args=(str(repo), _MISSION, child, release),
    )
    holder.start()
    child.close()
    try:
        parent.poll(10)
        parent.recv()

        ports = TasksPorts(
            fs=FakeFsReader(default_planning_dir=repo / "kitty-specs" / _MISSION),
            coord=FakeCoordCommitRouter(write_dir=repo / "kitty-specs" / _MISSION),
            git=FakeGitOps(),
            render=FakeRender(),
        )
        state = _build_state(repo)

        outcome: list[BaseException | None] = []

        def _drive() -> None:
            try:
                _persist_review_cycle_with_queue(state, ports, _create)
            except BaseException as exc:  # noqa: BLE001 - captured for assertion, not swallowed
                outcome.append(exc)
            else:
                outcome.append(None)

        started = time.perf_counter()
        driver = threading.Thread(target=_drive, daemon=True)
        driver.start()
        driver.join(_JOIN_CEILING_SECONDS)
        elapsed = time.perf_counter() - started

        assert_timing_budget(elapsed, _JOIN_CEILING_SECONDS, name="wedged_status_lock_busy_failure")
    finally:
        release.set()
        holder.join(timeout=10)
        if holder.is_alive():
            holder.terminate()
            holder.join(timeout=10)
        parent.close()


def test_in_queue_status_lock_timeout_is_bounded_only_when_queue_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The status-lock bound (#3773 item 1) is scoped to the queue-held path.

    The unbounded-hang hazard exists only while the checkout-wide verdict queue
    is held (there a wedged ``feature_status_lock`` holder would wedge every
    other verdict save, and the timeout is translated into a truthful busy
    envelope). Off the queue -- the ``--no-auto-commit`` and ``local_only``
    feedback paths, which have no such translation -- the acquisition keeps its
    historical unbounded (-1) wait so a rare contention never becomes an
    envelope-less error. This pins that scoping decision at the helper.
    """
    from specify_cli.review import cycle

    monkeypatch.setattr(cycle, "verdict_save_queue_is_held", lambda _repo: True)
    assert cycle._in_queue_status_lock_timeout(tmp_path) == DEFAULT_VERDICT_SAVE_TIMEOUT_SECONDS

    monkeypatch.setattr(cycle, "verdict_save_queue_is_held", lambda _repo: False)
    assert cycle._in_queue_status_lock_timeout(tmp_path) == -1.0

    # A non-git path cannot own the checkout-wide queue: the probe raises
    # GitTopologyError there (not False), and the allocator must degrade to the
    # historical unbounded wait rather than crash. (Regression: PR #3712 landing
    # -- the scoping probe crashed every local-only create_rejected_review_cycle
    # run outside a git repo with NotAGitRepositoryError.)
    from kernel.git_topology import NotAGitRepositoryError

    def _raise_not_a_repo(_repo: Path) -> bool:
        raise NotAGitRepositoryError(_repo)

    monkeypatch.setattr(cycle, "verdict_save_queue_is_held", _raise_not_a_repo)
    assert cycle._in_queue_status_lock_timeout(tmp_path) == -1.0
