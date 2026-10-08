"""Concurrent Mission writers on ``agent action implement`` (#5819, #5804; WP02).

Red-first reproductions of the two silent-corruption shapes of the
``agent action implement`` claim window:

* **#5819** -- ``implement`` captured the byte size of ``status.events.jsonl``
  *before* it took the Mission lock; when its own status commit then failed, the
  failure handler blindly truncated the log back to that size and cut every row
  another writer (``move-task``) had appended and committed in between.
* **#5804** -- on a coord Mission the claim row is already committed by the
  transactional emit when the follow-up commit fails; the handler still claimed
  "Event log rolled back" and truncated the coordination worktree's log under
  a concurrent claimant.

Determinism: the interleavings are produced with ``threading.Event`` hooks at
named seams (no ``sleep`` as synchronisation; every wait carries a timeout so a
regression fails instead of hanging). The hook that lets the second writer in
runs it to completion only when the interleaving is *permitted*, i.e. when the
first writer is not holding the Mission write lock: the SAME test is RED on a
capture-before-lock implementation and GREEN once the capture, the write and the
rollback share one lock hold.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest
import typer
import typer.main

import specify_cli.cli.commands.agent.tasks_move_task_executor as move_task_executor
import specify_cli.cli.commands.agent.workflow as workflow
import specify_cli.cli.commands.agent.workflow_executor as workflow_executor
import specify_cli.status.locking as locking
from specify_cli import app as root_app
from specify_cli.status import STATUS_ROLLBACK_REFUSED, RollbackPoint, RollbackRefusal, capture_rollback_point, mission_write_lock
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from tests.specify_cli.cli.commands.agent.test_issue_4905_coord_staging import (
    _build_flat_two_lane_mission,
    _build_two_lane_coord_mission,
)
from tests.utils import write_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Upper bound for every cross-thread wait; a regression fails with a message instead of hanging.
WAIT_SECONDS = 120.0
EVENTS = "status.events.jsonl"
NOTE = "descoped"
STAGING_FAILURE = "safe_commit: failed to stage requested files in repo: ['status.events.jsonl'] (index.lock held by a concurrent git process)"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def _invoke(*args: str) -> int:
    """Run the root CLI in-process without ``CliRunner`` (which swaps ``sys.stdout`` process-wide)."""
    command = typer.main.get_command(root_app)
    try:
        result = command.main(args=list(args), prog_name="spec-kitty", standalone_mode=False)
    except typer.Exit as exc:
        return int(exc.exit_code)
    return int(result or 0)


def _rows(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _disk_rows(feature_dir: Path) -> list[dict[str, Any]]:
    return _rows((feature_dir / EVENTS).read_text(encoding="utf-8"))


def _head_rows(repo: Path, relative: str) -> list[dict[str, Any]]:
    return _rows(_git(repo, "show", f"HEAD:{relative}"))


def _lane_of(rows: list[dict[str, Any]], wp_id: str) -> str | None:
    lane = None
    for row in rows:
        if row.get("wp_id") == wp_id and row.get("to_lane"):
            lane = row["to_lane"]
    return lane


def _notes(rows: list[dict[str, Any]], wp_id: str, note: str) -> list[str]:
    return [row["event_id"] for row in rows if row.get("wp_id") == wp_id and (row.get("delta") or {}).get("note") == note]


def _canceled_ids(rows: list[dict[str, Any]], wp_id: str) -> list[str]:
    return [row["event_id"] for row in rows if row.get("wp_id") == wp_id and row.get("to_lane") == "canceled"]


def _add_wp03(repo: Path, mission_dirname: str) -> None:
    """Add WP03 to the flat two-lane Mission (lane-b) so a third writer has its own work package."""
    feature_dir = repo / "kitty-specs" / mission_dirname
    write_wp(repo, mission_dirname, "planned", "WP03")
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    manifest.lanes = [replace(lane, wp_ids=(*lane.wp_ids, "WP03")) if lane.lane_id == "lane-b" else lane for lane in manifest.lanes]
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: add WP03")


@dataclass
class Interleave:
    """Named-seam hooks that run writer B inside writer A's claim window."""

    repo: Path
    feature_dir: Path
    lock_dirname: str
    body_of_b: Callable[[], None]
    pause_b_at_persist: bool = False
    a_thread: threading.Thread = field(default_factory=threading.main_thread)
    b_started: threading.Event = field(default_factory=threading.Event)
    b_paused: threading.Event = field(default_factory=threading.Event)
    release_b: threading.Event = field(default_factory=threading.Event)
    b_done: threading.Event = field(default_factory=threading.Event)
    b_error: list[BaseException] = field(default_factory=list)
    a_held_lock_at_window: list[bool] = field(default_factory=list)
    thread: threading.Thread | None = None

    def a_holds_mission_lock(self) -> bool:
        return str(locking.feature_status_lock_path(self.repo, self.lock_dirname)) in locking._get_thread_locks()

    def start_b(self) -> None:
        def _run() -> None:
            self.b_started.set()
            try:
                self.body_of_b()
            except (AssertionError, RuntimeError, OSError, typer.Exit) as exc:  # re-raised on the test thread by join_b
                self.b_error.append(exc)
            finally:
                self.b_done.set()

        self.thread = threading.Thread(target=_run, name="writer-b", daemon=True)
        self.thread.start()

    def a_in_window(self) -> None:
        """Called on writer A's thread right after its claim emit, i.e. inside the capture-to-rollback window."""
        holds = self.a_holds_mission_lock()
        self.a_held_lock_at_window.append(holds)
        if self.thread is None:
            self.start_b()
        self.release_b.set()
        if not holds:
            # the interleaving is permitted: writer B runs to completion inside A's window
            assert self.b_done.wait(WAIT_SECONDS), "writer B did not finish while writer A was inside its window"

    def join_b(self) -> None:
        assert self.thread is not None
        self.thread.join(WAIT_SECONDS)
        assert self.b_done.is_set(), "writer B never finished"
        assert not self.b_error, f"writer B raised: {self.b_error!r}"


@contextmanager
def _installed(
    il: Interleave, monkeypatch: pytest.MonkeyPatch, *, fail_commit_attr: str, fail_when: Callable[[], bool], commit_before_failure: bool = False
) -> Iterator[Interleave]:
    original_start = workflow_executor._implement_start_claim

    def _hooked_start(**kwargs: Any) -> Any:
        result = original_start(**kwargs)
        if threading.current_thread() is il.a_thread:
            il.a_in_window()
        return result

    monkeypatch.setattr(workflow_executor, "_implement_start_claim", _hooked_start)

    original_persist = move_task_executor._mt_persist_wp_file

    def _hooked_persist(st: Any, ports: Any) -> Any:
        if il.pause_b_at_persist and threading.current_thread() is not il.a_thread:
            il.b_paused.set()
            assert il.release_b.wait(WAIT_SECONDS), "writer B was never released"
        return original_persist(st, ports)

    monkeypatch.setattr(move_task_executor, "_mt_persist_wp_file", _hooked_persist)

    original_lock = locking._named_status_lock

    @contextmanager
    def _hooked_lock(lock_path: Path, *, timeout: float) -> Iterator[Path]:
        if threading.current_thread() is il.a_thread and il.b_paused.is_set():
            il.release_b.set()  # A is about to queue on the lock writer B holds paused
        with original_lock(lock_path, timeout=timeout) as held:
            yield held

    monkeypatch.setattr(locking, "_named_status_lock", _hooked_lock)

    original_commit = getattr(workflow, fail_commit_attr)

    def _failing_commit(**kwargs: Any) -> Any:
        if threading.current_thread() is not il.a_thread or not fail_when():
            return original_commit(**kwargs)
        if commit_before_failure:
            original_commit(**kwargs)  # the transaction commits, then the follow-up fails
        raise RuntimeError(STAGING_FAILURE)

    monkeypatch.setattr(workflow, fail_commit_attr, _failing_commit)
    yield il


# ---------------------------------------------------------------------------
# #5819 -- lanes Mission, legacy safe_commit arm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["transition", "annotation"])
def test_failed_implement_never_erases_a_committed_foreign_row(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """#5819: a failed implement restores only what it wrote itself."""
    repo, mission = _build_flat_two_lane_mission(tmp_path, monkeypatch, mission_slug="five-eight-one-nine")
    _add_wp03(repo, mission)
    feature_dir = repo / "kitty-specs" / mission

    # alice already claimed WP01 (control: the unobstructed claim succeeds)
    assert _invoke("agent", "action", "implement", "WP01", "--mission", mission, "--agent", "alice", "--allow-sparse-checkout") == 0
    capsys.readouterr()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "test: settle after alice's first claim")
    baseline_ids = {row["event_id"] for row in _disk_rows(feature_dir)}

    relative = f"kitty-specs/{mission}"

    def _writer_b() -> None:
        rc = _invoke("agent", "tasks", "move-task", "WP02", "--to", "canceled", "--agent", "system", "--note", NOTE, "--mission", mission)
        assert rc == 0, f"writer B (move-task) exited {rc}"
        # B commits its status files, as the real lanes move-task does; under the Mission lock so the
        # commit never captures another writer's transient rows
        with mission_write_lock(feature_dir, repo_root=repo, timeout=-1):
            _git(repo, "add", f"{relative}/{EVENTS}", f"{relative}/status.json")
            _git(repo, "commit", "-q", "-m", "writer B: WP02 canceled")

    il = Interleave(
        repo=repo,
        feature_dir=feature_dir,
        lock_dirname=mission,
        body_of_b=_writer_b,
        pause_b_at_persist=(mode == "annotation"),
    )
    armed = [True]
    with _installed(il, monkeypatch, fail_commit_attr="_commit_via_legacy_safe_commit", fail_when=lambda: armed[0]):
        if mode == "annotation":
            il.start_b()  # B commits its transition, then pauses (holding the Mission lock) before its annotation
            assert il.b_paused.wait(WAIT_SECONDS), "writer B never reached its annotation seam"
        a_rc = _invoke("agent", "action", "implement", "WP01", "--mission", mission, "--agent", "alice", "--allow-sparse-checkout")
        if il.thread is None:  # transition mode: B was started inside A's window
            raise AssertionError("writer A never reached its claim window")
        il.join_b()
    armed[0] = False  # the obstruction (index.lock contention) is over before the next writer
    out = capsys.readouterr().out

    assert a_rc == 1, out
    disk = _disk_rows(feature_dir)
    disk_ids = {row["event_id"] for row in disk}
    assert _lane_of(disk, "WP02") == "canceled", "writer B's committed cancel was erased from the on-disk log (#5819)"
    assert _notes(disk, "WP02", NOTE), "writer B's committed annotation was erased from the on-disk log (#5819)"
    assert not [row for row in disk if row["event_id"] not in baseline_ids and row.get("actor") == "alice"], "writer A's own failed rows must be rolled back"

    # the next committing status writer (carol's implement) must not commit the erasure into HEAD
    assert _invoke("agent", "action", "implement", "WP03", "--mission", mission, "--agent", "carol", "--allow-sparse-checkout") == 0
    after_next = _disk_rows(feature_dir)
    assert _lane_of(after_next, "WP02") == "canceled", "writer B's committed cancel disappeared after the next writer (#5819)"
    assert disk_ids <= {row["event_id"] for row in after_next}
    head = _head_rows(repo, f"{relative}/{EVENTS}")
    assert _lane_of(head, "WP02") == "canceled", "writer B's committed cancel is gone from HEAD after the next writer (#5819)"
    assert _notes(head, "WP02", NOTE), "writer B's committed annotation is gone from HEAD after the next writer (#5819)"
    assert _lane_of(head, "WP03") == "in_progress"


# ---------------------------------------------------------------------------
# #5804 -- coord Mission, transactional arm
# ---------------------------------------------------------------------------


def test_coord_claims_leave_a_parseable_log_and_honest_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#5804: two concurrent coord claims, A's follow-up commit fails while B appends."""
    repo, mission, coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="five-eight-oh-four")
    mid8 = mission.rsplit("-", 1)[1]
    coord_dir = CoordinationWorkspace.worktree_path(repo, mission, mid8) / "kitty-specs" / mission
    coord_relative = f"kitty-specs/{mission}/{EVENTS}"

    def _writer_b() -> None:
        rc = _invoke("agent", "action", "implement", "WP02", "--mission", mission, "--agent", "bob", "--allow-sparse-checkout")
        assert rc == 0, f"writer B (implement WP02) exited {rc}"

    il = Interleave(repo=repo, feature_dir=coord_dir, lock_dirname=mission, body_of_b=_writer_b)
    first_failure = threading.Event()

    def _fail_once() -> bool:
        if first_failure.is_set():
            return False
        first_failure.set()
        return True

    with _installed(il, monkeypatch, fail_commit_attr="_commit_via_coordination_transaction", fail_when=_fail_once, commit_before_failure=True):
        a_rc = _invoke("agent", "action", "implement", "WP01", "--mission", mission, "--agent", "alice", "--allow-sparse-checkout")
        assert il.thread is not None, "writer A never reached its claim window"
        il.join_b()
    out = capsys.readouterr().out

    assert a_rc == 1, out
    raw = (coord_dir / EVENTS).read_text(encoding="utf-8")
    assert "\x00" not in raw, "the coordination log holds NUL bytes (#5804)"
    assert all(line.strip() for line in raw.splitlines()), "the coordination log holds a whitespace-only line (#5804)"
    rows = _rows(raw)
    coord_head = _head_rows(coord_dir, coord_relative)
    assert _lane_of(coord_head, "WP01") == "in_progress", "writer A's committed claim is not in the coordination HEAD"
    assert _lane_of(coord_head, "WP02") == "in_progress", "writer B's committed claim is not in the coordination HEAD"
    assert _lane_of(rows, "WP01") == "in_progress"
    assert _lane_of(rows, "WP02") == "in_progress"
    assert "rolled back" not in out.lower(), f"output claims a rollback although the claim is committed on the coordination branch:\n{out}"
    assert "was committed" in out, out


def test_coord_review_claim_with_a_failing_follow_up_reports_the_committed_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A15: the review window measures the coord log; a committed in_review claim is reported as committed, never cut."""
    from specify_cli.status import Lane
    from specify_cli.task_utils import locate_work_package
    from tests.utils import _seed_canonical_wp_state

    repo, mission, _coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="coord-review-claim")
    mid8 = mission.rsplit("-", 1)[1]
    coord_worktree = CoordinationWorkspace.worktree_path(repo, mission, mid8)
    coord_dir = coord_worktree / "kitty-specs" / mission
    _seed_canonical_wp_state(coord_worktree, mission, "WP01", "for_review", actor="alice", assignee="Owner", shell_pid="1234", timestamp="2025-01-02T00:00:00Z")
    _git(coord_worktree, "add", "-A")
    _git(coord_worktree, "commit", "-q", "-m", "coord: WP01 for_review")
    original_commit = workflow._commit_via_coordination_transaction

    def _commit_then_fail(**kwargs: Any) -> Any:
        original_commit(**kwargs)  # the transaction commits the claim, then the follow-up fails
        raise RuntimeError(STAGING_FAILURE)

    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _commit_then_fail)
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        workflow_executor.review_claim_transition(
            wp=locate_work_package(repo, mission, "WP01"),
            feature_dir=coord_dir,
            current_lane=Lane.FOR_REVIEW,
            agent="rae",
            main_repo_root=repo,
            mission_slug=mission,
            normalized_wp_id="WP01",
            target_branch="mission-target",
            status_execution_mode="worktree",
            repo_root=repo,
        )

    out = capsys.readouterr().out
    assert "claim was committed" in out, out
    assert "rolled back" not in out.lower()
    raw = (coord_dir / EVENTS).read_text(encoding="utf-8")
    assert "\x00" not in raw
    assert _lane_of(_rows(raw), "WP01") == "in_review", "the committed review claim was cut from the coordination log"
    assert _lane_of(_head_rows(coord_dir, f"kitty-specs/{mission}/{EVENTS}"), "WP01") == "in_review"
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS][-1] == "committed"


# ---------------------------------------------------------------------------
# A4 / T010 -- truthful reporting of a rollback that left the files alone
# ---------------------------------------------------------------------------

UNIT_MISSION = "demo-01ABCDEF"
COORD_META = ("kitty/mission-demo-coord", "01ABCDEF000000000000000000", "01ABCDEF")


def _claim_row(event_id: str) -> str:
    return json.dumps({"event_id": event_id, "wp_id": "WP01", "to_lane": "in_progress"}, sort_keys=True) + "\n"


@dataclass
class _ClaimedRepo:
    repo: Path
    feature_dir: Path
    point: RollbackPoint

    @property
    def events(self) -> Path:
        return self.feature_dir / EVENTS


def _claim_repo(tmp_path: Path, *, commit_claim: bool) -> _ClaimedRepo:
    """A repo whose log holds one committed row, a rollback point captured under the lock, then the claim row appended."""
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / UNIT_MISSION
    feature_dir.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (feature_dir / EVENTS).write_text(_claim_row("before"), encoding="utf-8")
    (feature_dir / "status.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    with mission_write_lock(feature_dir, repo_root=repo):
        point = capture_rollback_point(feature_dir, repo_root=repo)
    with (feature_dir / EVENTS).open("a", encoding="utf-8") as fh:
        fh.write(_claim_row("claim"))
    if commit_claim:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "claim")
    return _ClaimedRepo(repo, feature_dir, point)


def _commit_change(claimed: _ClaimedRepo) -> None:
    workflow._commit_workflow_change(
        repo_root=claimed.repo,
        mission_slug="demo",
        target_branch="main",
        paths=[claimed.events],
        message="chore: Start WP01 implementation [alice]",
        operation="planned -> claimed for WP01",
        wp_id="WP01",
        rollback_point=claimed.point,
        auto_rebase_lane_after_commit=True,
    )


def _fail_follow_up(monkeypatch: pytest.MonkeyPatch, attr: str) -> None:
    def _boom(**_kwargs: Any) -> None:
        raise RuntimeError("follow-up failed")

    monkeypatch.setattr(workflow, attr, _boom)


@pytest.mark.parametrize("arm", ["legacy", "coord"])
def test_committed_claim_is_reported_as_committed_never_rolled_back(
    arm: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    claimed = _claim_repo(tmp_path, commit_claim=True)
    before = claimed.events.read_bytes()
    if arm == "legacy":
        monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: (None, None, None))
        _fail_follow_up(monkeypatch, "_commit_via_legacy_safe_commit")
    else:
        monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: COORD_META)
        _fail_follow_up(monkeypatch, "_commit_via_coordination_transaction")
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit) as exit_info:
        _commit_change(claimed)

    out = capsys.readouterr().out
    assert exit_info.value.exit_code == 1
    assert "WP01 claim was committed; the follow-up planned -> claimed for WP01 commit failed: follow-up failed" in out
    assert "rolled back" not in out.lower()
    assert claimed.events.read_bytes() == before, "a committed claim must not be cut"
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS] == ["committed"]


def test_uncommitted_claim_is_rolled_back_and_said_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    claimed = _claim_repo(tmp_path, commit_claim=False)
    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: (None, None, None))
    _fail_follow_up(monkeypatch, "_commit_via_legacy_safe_commit")
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    assert "Event log rolled back to pre-emit state." in capsys.readouterr().out
    assert claimed.events.read_text(encoding="utf-8") == _claim_row("before")
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS] == ["refused"]


def test_other_refusals_print_the_error_code_and_the_remedy_and_leave_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    claimed = _claim_repo(tmp_path, commit_claim=False)
    with claimed.events.open("a", encoding="utf-8") as fh:
        fh.write('{"event_id": "torn"')  # a torn row: not whole JSON rows
    torn = claimed.events.read_bytes()
    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: (None, None, None))
    _fail_follow_up(monkeypatch, "_commit_via_legacy_safe_commit")
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    out = capsys.readouterr().out
    assert STATUS_ROLLBACK_REFUSED in out
    assert "git diff HEAD --" in out
    assert "rolled back to pre-emit state" not in out
    assert claimed.events.read_bytes() == torn
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS] == ["refused"]


def _raise_permission_error(*_args: Any, **_kwargs: Any) -> None:
    raise PermissionError("read-only file system")


def test_rollback_io_error_is_reported_with_the_original_commit_error_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F2: an OSError out of the rollback becomes a coded refusal; the receipt, the commit error and exit 1 survive."""
    claimed = _claim_repo(tmp_path, commit_claim=False)
    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: (None, None, None))
    _fail_follow_up(monkeypatch, "_commit_via_legacy_safe_commit")
    monkeypatch.setattr(workflow, "rollback_status_artifacts", _raise_permission_error)
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit) as exit_info:
        _commit_change(claimed)

    out = capsys.readouterr().out
    assert exit_info.value.exit_code == 1
    assert "Failed to commit workflow status update for WP01: follow-up failed" in out
    assert STATUS_ROLLBACK_REFUSED in out
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS] == ["refused"]


def test_coord_fallback_rollback_io_error_carries_the_refusal_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F2: the coord fallback arm's OSError path returns the same coded refusal (non-empty message)."""
    from specify_cli.coordination import status_transition

    point = RollbackPoint(events_path=tmp_path / EVENTS, status_path=tmp_path / "status.json", pre_event_size=0, pre_status_bytes=None, events_existed=False)
    monkeypatch.setattr(status_transition, "rollback_status_artifacts", _raise_permission_error)

    outcome = status_transition._restore_coord_status_artifacts(point, repo_root=tmp_path)

    assert not outcome.rolled_back
    assert STATUS_ROLLBACK_REFUSED in outcome.message()


@pytest.mark.parametrize("revert", ["real", "silent_noop"])
def test_lane_sync_refusal_arm_keeps_receipt_and_message_consistent(
    revert: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kernel.clock import now_utc
    from specify_cli.coordination.types import CommitReceipt
    from specify_cli.lanes.lifecycle_sync import LaneAutoRebaseSyncError

    claimed = _claim_repo(tmp_path, commit_claim=True)
    receipt = CommitReceipt(
        commit_sha="abc123",
        committed_at=now_utc(),
        destination_ref=COORD_META[0],
        worktree_root=claimed.repo,
        event_ids=("claim",),
    )

    def _commit(**kwargs: Any) -> CommitReceipt:
        workflow._record_receipt(COORD_META[0], str(kwargs["message"]), "committed", sha=receipt.commit_sha, wp_id="WP01")
        return receipt

    def _sync_refuses(**_kwargs: Any) -> None:
        raise LaneAutoRebaseSyncError(lane_id="lane-a", lane_branch="kitty/mission-demo-lane-a", lane_worktree_path=claimed.repo / "lane-a")

    def _revert(_receipt: CommitReceipt) -> None:
        if revert == "real":
            _git(claimed.repo, "revert", "--no-edit", "HEAD")  # the real revert removes the claim row from the committed log

    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: COORD_META)
    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _commit)
    monkeypatch.setattr(workflow, "_sync_lane_after_coordination_commit", _sync_refuses)
    monkeypatch.setattr(workflow, "_revert_coordination_commit", _revert)
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    out = capsys.readouterr().out
    outcome = workflow._WORKFLOW_COMMIT_RECEIPTS[-1]["outcome"]
    if revert == "real":
        assert "claim was committed" not in out
        assert outcome == "refused"
        assert claimed.events.read_text(encoding="utf-8") == _claim_row("before")
    else:  # the revert changed nothing: the claim is still committed, in the message and the receipt alike
        assert "claim was committed; the lane sync after the planned -> claimed for WP01 commit failed" in out
        assert "follow-up" not in out
        assert outcome == "committed"


def _coord_claim_with_slow_lane_sync(claimed: _ClaimedRepo, monkeypatch: pytest.MonkeyPatch, during_sync: Callable[[], None]) -> None:
    """Stub a coord commit that lands the claim and a lane sync that runs *during_sync* and then refuses."""
    from kernel.clock import now_utc
    from specify_cli.coordination.types import CommitReceipt
    from specify_cli.lanes.lifecycle_sync import LaneAutoRebaseSyncError

    receipt = CommitReceipt(commit_sha="abc123", committed_at=now_utc(), destination_ref=COORD_META[0], worktree_root=claimed.repo, event_ids=("claim",))

    def _sync(**_kwargs: Any) -> None:
        during_sync()
        raise LaneAutoRebaseSyncError(lane_id="lane-a", lane_branch="kitty/mission-demo-lane-a", lane_worktree_path=claimed.repo / "lane-a")

    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: COORD_META)
    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", lambda **_kw: receipt)
    monkeypatch.setattr(workflow, "_sync_lane_after_coordination_commit", _sync)
    monkeypatch.setattr(workflow, "_revert_coordination_commit", lambda _receipt: None)
    workflow._reset_workflow_receipts()


def _commit_releasing_lock_for_lane_sync(claimed: _ClaimedRepo) -> None:
    """Commit as a claim caller does: hold the Mission lock for the commit, release it before the lane sync."""
    with ExitStack() as hold:
        hold.enter_context(mission_write_lock(claimed.feature_dir, repo_root=claimed.repo, timeout=-1))
        workflow._commit_workflow_change(
            repo_root=claimed.repo,
            mission_slug="demo",
            target_branch="main",
            paths=[claimed.events],
            message="chore: Start WP01 implementation [alice]",
            operation="planned -> claimed for WP01",
            wp_id="WP01",
            rollback_point=claimed.point,
            auto_rebase_lane_after_commit=True,
            before_lane_sync=hold.close,
        )


def _bounded_taker_succeeds(claimed: _ClaimedRepo) -> bool:
    """Whether another thread takes the Mission lock within a short bound (it is free)."""
    taken: list[bool] = []

    def _take() -> None:
        try:
            with mission_write_lock(claimed.feature_dir, repo_root=claimed.repo, timeout=2.0):
                taken.append(True)
        except locking.FeatureStatusLockTimeoutError:
            taken.append(False)

    thread = threading.Thread(target=_take, name="bounded-taker")
    thread.start()
    thread.join(WAIT_SECONDS)
    return taken == [True]


def test_lane_sync_runs_without_the_mission_lock_and_a_clean_refusal_cuts_only_the_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F1: the slow lane auto-rebase must not hold the Mission lock; the refusal still rolls the claim back."""
    claimed = _claim_repo(tmp_path, commit_claim=False)
    free_during_sync: list[bool] = []
    _coord_claim_with_slow_lane_sync(claimed, monkeypatch, lambda: free_during_sync.append(_bounded_taker_succeeds(claimed)))

    with pytest.raises(typer.Exit):
        _commit_releasing_lock_for_lane_sync(claimed)

    assert free_during_sync == [True], "a bounded taker must get the Mission lock while the lane sync runs"
    assert claimed.events.read_text(encoding="utf-8") == _claim_row("before")


def test_lane_sync_refusal_keeps_a_row_a_foreign_writer_appended_during_the_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F1: the rollback after a released-lock sync cuts only the claim's own rows and refuses when a foreign row followed."""
    claimed = _claim_repo(tmp_path, commit_claim=False)

    def _foreign_writer_appends() -> None:
        with mission_write_lock(claimed.feature_dir, repo_root=claimed.repo, timeout=2.0), claimed.events.open("a", encoding="utf-8") as fh:
            fh.write(_claim_row("foreign"))

    _coord_claim_with_slow_lane_sync(claimed, monkeypatch, _foreign_writer_appends)

    with pytest.raises(typer.Exit):
        _commit_releasing_lock_for_lane_sync(claimed)

    assert STATUS_ROLLBACK_REFUSED in capsys.readouterr().out
    assert claimed.events.read_text(encoding="utf-8") == _claim_row("before") + _claim_row("claim") + _claim_row("foreign")


def test_lane_sync_refusal_cuts_nothing_when_the_claim_rows_were_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No ownership proof (the tail was torn while the lock was held) means no cut, even if the tail is whole by rollback time."""
    claimed = _claim_repo(tmp_path, commit_claim=False)
    with claimed.events.open("a", encoding="utf-8") as fh:
        fh.write('{"event_id": "foreign"')  # torn: no closing brace, no newline

    def _foreign_writer_completes_the_row() -> None:
        with mission_write_lock(claimed.feature_dir, repo_root=claimed.repo, timeout=2.0), claimed.events.open("a", encoding="utf-8") as fh:
            fh.write("}\n")

    _coord_claim_with_slow_lane_sync(claimed, monkeypatch, _foreign_writer_completes_the_row)

    with pytest.raises(typer.Exit):
        _commit_releasing_lock_for_lane_sync(claimed)

    assert RollbackRefusal.TAIL_UNPARSEABLE.value in capsys.readouterr().out
    assert claimed.events.read_text(encoding="utf-8") == _claim_row("before") + _claim_row("claim") + '{"event_id": "foreign"}\n'


def test_claim_wrappers_hand_the_body_a_release_for_the_mission_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F1: ``implement_claim_transition`` holds the lock for the body and the body can release it for the lane sync."""
    repo, mission, _coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="release-hook")
    seen: list[tuple[bool, bool]] = []
    status_dirs: list[Path] = []

    def _body(*, release_lock: Callable[[], None], wf_feature_dir: Path, **_kwargs: Any) -> None:
        status_dirs.append(wf_feature_dir)
        held = bool(locking._get_thread_locks())
        release_lock()
        seen.append((held, bool(locking._get_thread_locks())))

    monkeypatch.setattr(workflow_executor, "_implement_claim_transition_body", _body)
    unused: Any = None
    workflow_executor.implement_claim_transition(
        repo_root=repo,
        main_repo_root=repo,
        mission_slug=mission,
        normalized_wp_id="WP01",
        wp=unused,
        wp_meta=unused,
        feature_dir=repo,
        agent="alice",
        target_branch="mission-target",
        workspace_path=repo,
        status_execution_mode="worktree",
    )

    assert seen == [(True, False)]
    assert status_dirs == [workflow._canonical_status_feature_dir(repo, mission)], "the body gets the resolved status dir instead of resolving it again"


def test_real_revert_after_a_lane_sync_refusal_leaves_no_rollback_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real ``git revert`` already restores the log; the follow-up rollback must see that as done, not as a foreign tail."""
    from kernel.clock import now_utc
    from specify_cli.coordination.types import CommitReceipt
    from specify_cli.lanes.lifecycle_sync import LaneAutoRebaseSyncError

    claimed = _claim_repo(tmp_path, commit_claim=False)
    (claimed.feature_dir / "status.json").write_text('{"claimed": true}\n', encoding="utf-8")
    _git(claimed.repo, "add", "-A")
    _git(claimed.repo, "commit", "-q", "-m", "claim")
    receipt = CommitReceipt(
        commit_sha=_git(claimed.repo, "rev-parse", "HEAD").strip(),
        committed_at=now_utc(),
        destination_ref=COORD_META[0],
        worktree_root=claimed.repo,
        event_ids=("claim",),
    )

    def _sync_refuses(**_kwargs: Any) -> None:
        raise LaneAutoRebaseSyncError(
            lane_id="lane-a",
            lane_branch="kitty/mission-demo-lane-a",
            lane_worktree_path=claimed.repo / "lane-a",
            coordination_branch=COORD_META[0],
            coordination_head=None,
            halt_reason="conflict",
        )

    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: COORD_META)

    def _commit(**kwargs: Any) -> CommitReceipt:
        workflow._record_receipt(COORD_META[0], str(kwargs["message"]), "committed", sha=receipt.commit_sha, wp_id="WP01")
        return receipt

    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _commit)
    monkeypatch.setattr(workflow, "_sync_lane_after_coordination_commit", _sync_refuses)  # _revert_coordination_commit stays REAL
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    out = capsys.readouterr().out
    assert STATUS_ROLLBACK_REFUSED not in out
    assert "Failed to rollback" not in out
    assert claimed.events.read_text(encoding="utf-8") == _claim_row("before")
    assert (claimed.feature_dir / "status.json").read_text(encoding="utf-8") == "{}\n"
    assert workflow._WORKFLOW_COMMIT_RECEIPTS[-1]["outcome"] == "refused"


def test_failed_revert_after_a_lane_sync_refusal_names_the_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    claimed = _claim_repo(tmp_path, commit_claim=True)

    def _no_revert(_receipt: Any) -> None:
        raise RuntimeError("coordination branch advanced")

    _coord_claim_with_slow_lane_sync(claimed, monkeypatch, lambda: None)
    monkeypatch.setattr(workflow, "_revert_coordination_commit", _no_revert)

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    out = capsys.readouterr().out
    assert "Failed to rollback lifecycle state after lane sync refusal: coordination branch advanced" in out
    assert "WP01 stays claimed and its lane was not synced" in out
    assert "move-task WP01 --to planned --mission demo" in out


def test_exit_arm_records_a_committed_receipt_when_the_claim_is_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    claimed = _claim_repo(tmp_path, commit_claim=True)

    def _exit(**_kwargs: Any) -> None:
        raise typer.Exit(1)

    monkeypatch.setattr(workflow, "_load_coord_branch_meta", lambda _fd: COORD_META)
    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _exit)
    workflow._reset_workflow_receipts()

    with pytest.raises(typer.Exit):
        _commit_change(claimed)

    assert "claim was committed" in capsys.readouterr().out
    assert [r["outcome"] for r in workflow._WORKFLOW_COMMIT_RECEIPTS] == ["committed"]


# ---------------------------------------------------------------------------
# T009 / T011 -- the window's lock key and the checkout claim lock
# ---------------------------------------------------------------------------


def test_claim_window_lock_is_keyed_like_the_coord_transaction_for_a_slug_without_mid8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The window lock path equals the coord transaction's (``_mission_specs_dir_name``), so the transaction re-enters it instead of timing out."""
    from specify_cli.coordination.legacy_resolution import _mission_specs_dir_name

    repo, mission, _coord_branch = _build_two_lane_coord_mission(tmp_path, monkeypatch, mission_slug="no-mid8-in-slug")
    mid8 = mission.rsplit("-", 1)[1]
    assert mission.removesuffix(f"-{mid8}") == "no-mid8-in-slug", "fixture: the human slug must not embed the mid8"
    held: list[set[str]] = []

    def _capture_body(**_kwargs: Any) -> None:
        held.append(set(locking._get_thread_locks()))

    monkeypatch.setattr(workflow_executor, "_implement_claim_transition_body", _capture_body)
    unused: Any = None  # the stubbed body never reads the work package
    workflow_executor.implement_claim_transition(
        repo_root=repo,
        main_repo_root=repo,
        mission_slug=mission,
        normalized_wp_id="WP01",
        wp=unused,
        wp_meta=unused,
        feature_dir=repo,
        agent="alice",
        target_branch="mission-target",
        workspace_path=repo,
        status_execution_mode="worktree",
    )

    transaction_key = str(locking.feature_status_lock_path(repo, _mission_specs_dir_name("no-mid8-in-slug", mid8)))
    assert held == [{transaction_key}]


def _make_single_branch(repo: Path, mission: str) -> None:
    """Re-stamp the flat two-lane Mission as single_branch: WP01 and WP02 share the repository root lane."""
    feature_dir = repo / "kitty-specs" / mission
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    meta["topology"] = "single_branch"
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    manifest.mission_branch = ""
    manifest.lanes = [
        ExecutionLane(
            lane_id=PLANNING_LANE_ID,
            wp_ids=("WP01", "WP02"),
            write_scope=("src/**",),
            predicted_surfaces=("test",),
            depends_on_lanes=(),
            parallel_group=0,
        )
    ]
    write_lanes_json(feature_dir, manifest)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "planning: single_branch")


def test_single_branch_agent_claims_serialize_on_the_checkout_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#5796 (agent arm): the second claimant waits on the checkout lock, then is refused WRITE_CHECKOUT_OCCUPIED; exactly one WP is in_progress."""
    repo, mission = _build_flat_two_lane_mission(tmp_path, monkeypatch, mission_slug="single-branch-claims")
    _make_single_branch(repo, mission)
    feature_dir = repo / "kitty-specs" / mission
    b_progress = threading.Event()  # B queued on the checkout lock (fixed code) or finished (unlocked code)
    b_thread: list[threading.Thread] = []
    a_thread = threading.main_thread()

    def _writer_b() -> None:
        try:
            _invoke("agent", "action", "implement", "WP02", "--mission", mission, "--agent", "bob", "--allow-sparse-checkout")
        finally:
            b_progress.set()

    original_guard = workflow._guard_repo_root_claim

    def _guard_then_race(*args: Any, **kwargs: Any) -> None:
        original_guard(*args, **kwargs)
        if threading.current_thread() is a_thread and not b_thread:
            b_thread.append(threading.Thread(target=_writer_b, name="writer-b", daemon=True))
            b_thread[0].start()
            assert b_progress.wait(WAIT_SECONDS), "writer B neither queued on the checkout lock nor finished"

    original_lock = locking._named_status_lock

    @contextmanager
    def _watched_lock(lock_path: Path, *, timeout: float) -> Iterator[Path]:
        if threading.current_thread().name == "writer-b" and Path(lock_path).name.startswith("__checkout-"):
            b_progress.set()
        with original_lock(lock_path, timeout=timeout) as held:
            yield held

    monkeypatch.setattr(workflow, "_guard_repo_root_claim", _guard_then_race)
    monkeypatch.setattr(locking, "_named_status_lock", _watched_lock)

    a_rc = _invoke("agent", "action", "implement", "WP01", "--mission", mission, "--agent", "alice", "--allow-sparse-checkout")
    b_thread[0].join(WAIT_SECONDS)
    out = capsys.readouterr().out

    assert a_rc == 0, out
    assert not b_thread[0].is_alive()
    rows = _disk_rows(feature_dir)
    assert [wp for wp in ("WP01", "WP02") if _lane_of(rows, wp) == "in_progress"] == ["WP01"], "both claimants passed the occupancy scan (#5796)\n" + out
    assert "WRITE_CHECKOUT_OCCUPIED" in out


def test_checkout_claim_lock_is_shared_across_missions_of_one_checkout(tmp_path: Path) -> None:
    """A claimant of another single_branch Mission waits for the checkout lock too (cross-Mission arm)."""
    from tests.lanes.test_checkout_occupancy import _init_repo, _write_repo_root_lane, _write_single_branch_meta
    from specify_cli.lanes.compute import PLANNING_LANE_ID as repo_root_lane
    from specify_cli.workspace.context import ResolvedWorkspace

    repo = tmp_path / "repo"
    _init_repo(repo)
    for slug, mission_id in (("cross-a", "01CROSSAAAAAAAAAAAAAAAAAAA"), ("cross-b", "01CROSSBBBBBBBBBBBBBBBBBBB")):
        _write_single_branch_meta(repo, slug, mission_id)
        _write_repo_root_lane(repo, slug, "WP01")

    def _workspace(slug: str) -> ResolvedWorkspace:
        return ResolvedWorkspace(
            mission_slug=slug,
            wp_id="WP01",
            execution_mode="code_change",
            mode_source="test",
            resolution_kind="repo_root",
            workspace_name=repo_root_lane,
            worktree_path=repo,
            branch_name=None,
            lane_id=repo_root_lane,
            lane_wp_ids=["WP01"],
        )

    holding = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def _first() -> None:
        with ExitStack() as stack:
            workflow_executor.enter_checkout_claim_lock(stack, repo, "cross-a", _workspace("cross-a"))
            order.append("a-in")
            holding.set()
            assert release.wait(WAIT_SECONDS)
            order.append("a-out")

    def _second() -> None:
        with ExitStack() as stack:
            workflow_executor.enter_checkout_claim_lock(stack, repo, "cross-b", _workspace("cross-b"))
            order.append("b-in")

    t1 = threading.Thread(target=_first)
    t1.start()
    assert holding.wait(WAIT_SECONDS)
    t2 = threading.Thread(target=_second)
    t2.start()
    t2.join(0.5)
    assert t2.is_alive(), "the second Mission's claimant entered while the first held the checkout lock"
    release.set()
    t1.join(WAIT_SECONDS)
    t2.join(WAIT_SECONDS)
    assert order == ["a-in", "a-out", "b-in"]


def test_lane_worktree_claims_take_no_checkout_lock(tmp_path: Path) -> None:
    from specify_cli.workspace.context import ResolvedWorkspace

    lane_workspace = ResolvedWorkspace(
        mission_slug="m",
        wp_id="WP01",
        execution_mode="code_change",
        mode_source="test",
        resolution_kind="lane_workspace",
        workspace_name="lane-a",
        worktree_path=tmp_path,
        branch_name=None,
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
    )
    with ExitStack() as stack:
        workflow_executor.enter_checkout_claim_lock(stack, tmp_path, "m", lane_workspace)
        assert not locking._get_thread_locks()
