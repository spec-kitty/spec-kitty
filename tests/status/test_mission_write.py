"""Mission write primitive (concurrent-mission-writers WP01, #5819).

The two ``test_pin_*`` tests are the red-first reproductions of the blind
``fh.truncate(pre_size)`` the coord fallback arm and ``BookkeepingTransaction``
used to run: they were RED on the unchanged code (a row another writer committed
was cut; a shrunk log was padded with NUL bytes) and now pin the primitive.
"""

from __future__ import annotations

import os
import json
import subprocess
import threading
from pathlib import Path
from typing import Any, BinaryIO

import pytest

import specify_cli.coordination.status_transition as st
import specify_cli.coordination.transaction as transaction_module
import specify_cli.status.mission_write as mw
from kernel.git import GitCommandError, run_git
from specify_cli.coordination.transaction import BookkeepingCommitFailed, BookkeepingTransaction
from specify_cli.status.emit import build_status_event
from specify_cli.status.models import StatusEvent
from specify_cli.status import (
    STATUS_ROLLBACK_REFUSED,
    RollbackPoint,
    RollbackRefusal,
    capture_rollback_point,
    locked_rewrite_text,
    mission_write_lock,
    rollback_events_log,
    rollback_status_artifacts,
)
from specify_cli.status.locking import (
    UNBOUNDED_LOCK_WAIT,
    FeatureStatusLockTimeoutError,
    _get_thread_locks,
    feature_status_lock_path,
    holds_status_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_DIRNAME = "demo-mission-01ABCDEF"
EVENTS = "status.events.jsonl"
STATUS = "status.json"
SEED_STATUS = b'{"seed": true}\n'


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def _row(event_id: str) -> str:
    return json.dumps({"event_id": event_id, "wp_id": "WP01", "to_lane": "claimed"}, sort_keys=True) + "\n"


def _append(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _init_repo(root: Path) -> Path:
    feature_dir = root / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    return feature_dir


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


@pytest.fixture
def mission(root: Path) -> Path:
    feature_dir = _init_repo(root)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    (feature_dir / STATUS).write_bytes(SEED_STATUS)
    _commit_all(root, "seed")
    return feature_dir


def _point(mission: Path, root: Path) -> RollbackPoint:
    with mission_write_lock(mission, repo_root=root):
        return capture_rollback_point(mission, repo_root=root)


def _snapshot(mission: Path) -> tuple[bytes, bytes]:
    return (mission / EVENTS).read_bytes(), (mission / STATUS).read_bytes()


# --- red-first pins (retargeted onto the primitive) -------------------------------------


def test_pin_restore_must_not_cut_a_row_another_writer_committed(mission: Path, root: Path) -> None:
    events = mission / EVENTS
    point = _point(mission, root)
    _append(events, _row("01B"))
    _commit_all(root, "other writer")

    outcome = st._restore_coord_status_artifacts(point, repo_root=root)

    assert outcome.refusal is RollbackRefusal.TAIL_ALREADY_COMMITTED
    assert "01B" in events.read_text(encoding="utf-8")


def test_pin_restore_must_not_pad_a_shrunk_log_with_nul_bytes(mission: Path, root: Path) -> None:
    events = mission / EVENTS
    _append(events, _row("01B"))
    point = _point(mission, root)
    events.write_text(_row("01A"), encoding="utf-8")

    outcome = st._restore_coord_status_artifacts(point, repo_root=root)

    assert outcome.refusal is RollbackRefusal.LOG_SHRANK
    assert b"\x00" not in events.read_bytes()


def _run_coord_arm(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch, *, commit_error: Exception, emitter_commits: bool) -> BaseException:
    """Run the coord fallback arm with a commit that fails; return the error that propagates out of it."""
    from types import SimpleNamespace

    identity: Any = SimpleNamespace(repo_root=root, owned=None)
    seam = SimpleNamespace(write_dir=lambda _kind: SimpleNamespace(path=mission))
    monkeypatch.setattr(st, "_canonical_coord_mission_slug", lambda *_a: "demo")
    monkeypatch.setattr(st, "_capture_coord_tail", lambda *_a: None)  # the fixture rows are not full events
    monkeypatch.setattr(st, "placement_seam", lambda *_a, **_k: seam)

    def _failing_commit(**_kwargs: object) -> None:
        raise commit_error

    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", _failing_commit)

    def _emit(coord_fd: Path) -> str:
        _append(coord_fd / EVENTS, _row("01B"))
        if emitter_commits:
            _commit_all(root, "another writer committed the row")
        return "emitted"

    try:
        st._emit_on_coord_then_commit(identity, "demo", root, emit=_emit, repo_root=root)
    except RuntimeError as exc:
        return exc
    pytest.fail("the injected commit failure did not surface")


def test_coord_arm_appends_a_refused_rollback_to_the_commit_error(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F7: the coord fallback arm surfaces STATUS_ROLLBACK_REFUSED on the error it re-raises (it only logged it)."""
    error = _run_coord_arm(mission, root, monkeypatch, commit_error=RuntimeError("coord commit failed"), emitter_commits=True)

    assert "coord commit failed" in str(error)
    assert STATUS_ROLLBACK_REFUSED in str(error)
    assert RollbackRefusal.TAIL_ALREADY_COMMITTED.value in str(error)
    assert "01B" in (mission / EVENTS).read_text(encoding="utf-8")


def test_coord_arm_leaves_the_commit_error_alone_when_the_rollback_succeeds(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    error = _run_coord_arm(mission, root, monkeypatch, commit_error=RuntimeError("coord commit failed"), emitter_commits=False)

    assert str(error) == "coord commit failed"
    assert (mission / EVENTS).read_text(encoding="utf-8") == _row("01A")


def test_holds_status_lock_follows_the_calling_threads_hold(mission: Path, root: Path) -> None:
    lock_path = feature_status_lock_path(root, MISSION_DIRNAME)
    other_path = feature_status_lock_path(root, "other-mission-01ZZZZZZ")

    assert not holds_status_lock(lock_path)
    with mission_write_lock(mission, repo_root=root):
        assert holds_status_lock(lock_path)
        assert not holds_status_lock(other_path)
        seen_elsewhere: list[bool] = []
        thread = threading.Thread(target=lambda: seen_elsewhere.append(holds_status_lock(lock_path)))
        thread.start()
        thread.join()
        assert seen_elsewhere == [False], "another thread does not hold it"
    assert not holds_status_lock(lock_path)


def test_unbounded_lock_wait_is_the_unbounded_timeout() -> None:
    assert UNBOUNDED_LOCK_WAIT < 0


def test_named_constructor_builds_a_point_without_reading_or_locking(root: Path) -> None:
    """The caller measured under its own hold; the constructor neither checks the lock nor touches the files."""
    point = RollbackPoint.measured_under_held_lock(events_path=root / "log.jsonl", status_path=root / "status.json", pre_event_size=7, events_existed=True)

    assert point == RollbackPoint(events_path=root / "log.jsonl", status_path=root / "status.json", pre_event_size=7, pre_status_bytes=None, events_existed=True)


def test_io_error_refusal_does_not_claim_the_log_is_unchanged(tmp_path: Path) -> None:
    outcome = mw.RollbackOutcome(rolled_back=False, refusal=RollbackRefusal.IO_ERROR, events_path=tmp_path / EVENTS)

    assert STATUS_ROLLBACK_REFUSED in outcome.message()
    assert "partly rewritten" in outcome.message() and "left unchanged" not in outcome.message()
    assert f"git diff HEAD -- {tmp_path / EVENTS}" in outcome.message()


# --- lock and capture ---------------------------------------------------------------------


def test_mission_write_lock_is_the_status_lock_file_and_reentrant(mission: Path, root: Path) -> None:
    key = str(feature_status_lock_path(root, MISSION_DIRNAME))
    with mission_write_lock(mission, repo_root=root) as outer, mission_write_lock(mission, repo_root=root) as inner:
        assert outer == inner == Path(key)
        assert key in _get_thread_locks()
        with st.coord_status_lock(root, mission) as coord:
            assert coord == Path(key)
    assert key not in _get_thread_locks()


def test_capture_refuses_without_the_lock(mission: Path, root: Path) -> None:
    with pytest.raises(RuntimeError, match="requires the Mission write lock"):
        capture_rollback_point(mission, repo_root=root)


def test_capture_refuses_while_only_another_mission_lock_is_held(mission: Path, root: Path) -> None:
    other = mission.parent / "other-mission-01ZZZZZZ"
    other.mkdir()
    with mission_write_lock(other, repo_root=root), pytest.raises(RuntimeError, match="requires the Mission write lock"):
        capture_rollback_point(mission, repo_root=root)


def test_capture_records_size_status_and_existence(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    assert point == RollbackPoint(
        events_path=mission / EVENTS,
        status_path=mission / STATUS,
        pre_event_size=(mission / EVENTS).stat().st_size,
        pre_status_bytes=SEED_STATUS,
        events_existed=True,
    )


def test_capture_of_a_mission_without_status_files(root: Path) -> None:
    feature_dir = _init_repo(root)
    point = _point(feature_dir, root)
    assert (point.pre_event_size, point.pre_status_bytes, point.events_existed) == (0, None, False)


def test_capture_resolves_the_lock_root_without_an_explicit_repo_root(mission: Path) -> None:
    with mission_write_lock(mission):
        assert capture_rollback_point(mission).pre_event_size == (mission / EVENTS).stat().st_size


def test_capture_in_a_coord_worktree_agrees_with_the_lock_taken_by_the_caller(root: Path, tmp_path: Path) -> None:
    feature_dir = _init_repo(root)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    _commit_all(root, "seed")
    coord = tmp_path / "coord-wt"
    _git(root, "worktree", "add", "-q", "-b", "kitty/coord", str(coord))
    coord_dir = coord / "kitty-specs" / MISSION_DIRNAME
    with st.coord_status_lock(root, coord_dir):
        point = capture_rollback_point(coord_dir, repo_root=root)
        _append(coord_dir / EVENTS, _row("01B"))
        outcome = rollback_status_artifacts(point, expected_event_ids=["01B"], repo_root=root)
    assert outcome.rolled_back
    assert (coord_dir / EVENTS).read_text(encoding="utf-8") == _row("01A")


# --- rollback: success arms ---------------------------------------------------------------


def test_rollback_cuts_exactly_the_appended_rows_and_restores_status(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    before = (mission / EVENTS).read_bytes()
    _append(mission / EVENTS, _row("01B") + _row("01C"))
    (mission / STATUS).write_bytes(b"changed\n")

    outcome = rollback_status_artifacts(point, expected_event_ids=["01C", "01B"], repo_root=root)

    assert outcome.rolled_back and outcome.refusal is None and outcome.message() == ""
    assert (mission / EVENTS).read_bytes() == before
    assert (mission / STATUS).read_bytes() == SEED_STATUS


def test_rollback_with_nothing_appended_is_a_noop(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    before = _snapshot(mission)
    assert rollback_status_artifacts(point, repo_root=root).rolled_back
    assert _snapshot(mission) == before


def test_rollback_unlinks_a_status_snapshot_that_did_not_exist(mission: Path, root: Path) -> None:
    (mission / STATUS).unlink()
    point = _point(mission, root)
    (mission / STATUS).write_bytes(b"created by the emit\n")
    _append(mission / EVENTS, _row("01B"))

    assert rollback_status_artifacts(point, repo_root=root).rolled_back
    assert not (mission / STATUS).exists()


def test_rollback_unlinks_a_log_that_did_not_exist(root: Path) -> None:
    feature_dir = _init_repo(root)
    point = _point(feature_dir, root)
    _append(feature_dir / EVENTS, _row("01B"))

    assert rollback_events_log(point, expected_event_ids=["01B"], repo_root=root).rolled_back
    assert not (feature_dir / EVENTS).exists()


def test_rollback_of_a_log_that_never_existed_and_still_does_not_is_done(root: Path) -> None:
    feature_dir = _init_repo(root)
    assert rollback_events_log(_point(feature_dir, root), repo_root=root).rolled_back


def test_a_leading_blank_line_inserted_by_the_raw_appender_is_legal(root: Path) -> None:
    feature_dir = _init_repo(root)
    (feature_dir / EVENTS).write_text(_row("01A").rstrip("\n"), encoding="utf-8")
    _commit_all(root, "seed without trailing newline")
    point = _point(feature_dir, root)
    _append(feature_dir / EVENTS, "\n" + _row("01B"))

    assert rollback_events_log(point, expected_event_ids=["01B"], repo_root=root).rolled_back
    assert (feature_dir / EVENTS).read_text(encoding="utf-8") == _row("01A").rstrip("\n")


def test_uncommitted_rows_in_a_directory_that_is_not_a_git_repo_are_cut(tmp_path: Path) -> None:
    feature_dir = tmp_path / "plain" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    point = _point(feature_dir, tmp_path / "plain")
    _append(feature_dir / EVENTS, _row("01B"))

    assert rollback_events_log(point, repo_root=tmp_path / "plain").rolled_back
    assert (feature_dir / EVENTS).read_text(encoding="utf-8") == _row("01A")


def test_rows_in_a_repository_with_no_commit_yet_are_cut(root: Path) -> None:
    feature_dir = _init_repo(root)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    point = _point(feature_dir, root)
    _append(feature_dir / EVENTS, _row("01B"))

    assert rollback_events_log(point, repo_root=root).rolled_back


def test_rows_of_a_log_head_does_not_track_are_cut(mission: Path, root: Path) -> None:
    (mission / "other.txt").write_text("x", encoding="utf-8")
    _git(root, "rm", "-q", "--cached", str((mission / EVENTS).relative_to(root)))
    _git(root, "commit", "-q", "-m", "untrack the log")
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))

    assert rollback_events_log(point, expected_event_ids=["01B"], repo_root=root).rolled_back


# --- rollback: refusals leave both files byte-identical ----------------------------------


def test_refusal_message_names_code_reason_and_remedy(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    (mission / EVENTS).unlink()
    outcome = rollback_events_log(point, repo_root=root)
    assert outcome.refusal is RollbackRefusal.LOG_VANISHED
    assert outcome.message() == (
        f"STATUS_ROLLBACK_REFUSED: {RollbackRefusal.LOG_VANISHED.value}; {mission / EVENTS} left unchanged. Inspect with: git diff HEAD -- {mission / EVENTS}"
    )


def test_a_vanished_log_is_refused(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    (mission / EVENTS).unlink()
    assert rollback_status_artifacts(point, repo_root=root).refusal is RollbackRefusal.LOG_VANISHED
    assert (mission / STATUS).read_bytes() == SEED_STATUS


def test_a_torn_tail_is_refused_and_both_files_stay_byte_identical(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B") + '{"event_id": "01C", "to_la')
    (mission / STATUS).write_bytes(b"changed\n")
    before = _snapshot(mission)

    outcome = rollback_status_artifacts(point, repo_root=root)

    assert outcome.refusal is RollbackRefusal.TAIL_UNPARSEABLE
    assert _snapshot(mission) == before


@pytest.mark.parametrize("tail", ['["not", "an", "object"]\n', '{"no_event_id": 1}\n', "not json\n"])
def test_a_tail_of_non_event_rows_is_refused(mission: Path, root: Path, tail: str) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, tail)
    assert rollback_events_log(point, repo_root=root).refusal is RollbackRefusal.TAIL_UNPARSEABLE


def test_a_tail_that_is_not_the_callers_rows_is_refused(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B") + _row("01X"))
    before = _snapshot(mission)

    outcome = rollback_status_artifacts(point, expected_event_ids=["01B"], repo_root=root)

    assert outcome.refusal is RollbackRefusal.TAIL_NOT_OWNED
    assert _snapshot(mission) == before


def test_a_duplicated_row_is_not_owned_as_a_multiset(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B") + _row("01B"))
    assert rollback_events_log(point, expected_event_ids=["01B"], repo_root=root).refusal is RollbackRefusal.TAIL_NOT_OWNED


def test_an_unreadable_head_fails_closed(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))
    before = _snapshot(mission)

    def _boom(cwd: Path, ref: str, path: str) -> bytes | None:
        raise GitCommandError(argv=("cat-file",), cwd=cwd, returncode=128, stderr="fatal: bad object")

    monkeypatch.setattr(mw, "blob_at", _boom)

    outcome = rollback_status_artifacts(point, repo_root=root)

    assert outcome.refusal is RollbackRefusal.HEAD_UNREADABLE
    assert _snapshot(mission) == before


def test_a_malformed_committed_line_fails_closed(mission: Path, root: Path) -> None:
    """The committed ids are unknown when HEAD's log holds a non-JSON line, so no tail may be cut on that proof."""
    _append(mission / EVENTS, "not json\n")
    _commit_all(root, "corrupt committed log")
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))
    before = _snapshot(mission)

    outcome = rollback_status_artifacts(point, repo_root=root)

    assert outcome.refusal is RollbackRefusal.HEAD_UNREADABLE
    assert _snapshot(mission) == before


def test_a_head_that_cannot_be_resolved_fails_closed(mission: Path, root: Path) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))
    (root / ".git" / "refs" / "heads" / "main").write_text("0123456789abcdef0123456789abcdef01234567\n", encoding="utf-8")

    assert rollback_events_log(point, repo_root=root).refusal is RollbackRefusal.HEAD_UNREADABLE


def test_refusal_is_logged_at_warning(mission: Path, root: Path, caplog: pytest.LogCaptureFixture) -> None:
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))
    _commit_all(root, "other writer")
    with caplog.at_level("WARNING", logger=mw.logger.name):
        rollback_events_log(point, repo_root=root)
    assert any("STATUS_ROLLBACK_REFUSED" in record.getMessage() for record in caplog.records)


def test_rollback_never_truncates_above_the_descriptor_size(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    point = _point(mission, root)
    sizes: list[tuple[int, int]] = []
    real = os.ftruncate

    def _spy(fd: int, length: int) -> None:
        # ``mw.os`` is the global ``os`` module: only record the event log's own descriptor.
        if os.fstat(fd).st_ino == (mission / EVENTS).stat().st_ino:
            sizes.append((os.fstat(fd).st_size, length))
        real(fd, length)

    monkeypatch.setattr(os, "ftruncate", _spy)
    _append(mission / EVENTS, _row("01B"))
    assert rollback_events_log(point, repo_root=root).rolled_back
    (only,) = sizes
    assert only[1] <= only[0]


def test_rollback_runs_inside_the_lock(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = str(feature_status_lock_path(root, MISSION_DIRNAME))
    point = _point(mission, root)
    _append(mission / EVENTS, _row("01B"))
    seen: list[bool] = []
    real = mw._cut_tail

    def _spy(p: RollbackPoint, fh: BinaryIO) -> None:
        seen.append(key in _get_thread_locks())
        real(p, fh)

    monkeypatch.setattr(mw, "_cut_tail", _spy)
    rollback_events_log(point, repo_root=root)
    assert seen == [True]


# --- locked_rewrite_text ----------------------------------------------------------------------


def test_locked_rewrite_text_reads_and_writes_under_the_lock(mission: Path, root: Path) -> None:
    target = mission / "tasks.md"
    key = str(feature_status_lock_path(root, MISSION_DIRNAME))
    seen: list[tuple[bool, str | None]] = []

    def _transform(current: str | None) -> str:
        seen.append((key in _get_thread_locks(), current))
        return (current or "") + "line\n"

    assert locked_rewrite_text(target, _transform, feature_dir=mission, repo_root=root) == "line\n"
    assert locked_rewrite_text(target, _transform, feature_dir=mission, repo_root=root) == "line\nline\n"
    assert seen == [(True, None), (True, "line\n")]
    assert target.read_text(encoding="utf-8") == "line\nline\n"


def test_locked_rewrite_text_skips_the_write_when_unchanged(mission: Path, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = mission / "tasks.md"
    target.write_text("same\n", encoding="utf-8")
    monkeypatch.setattr(mw, "atomic_write", lambda *a, **k: pytest.fail("rewrote an unchanged file"))
    assert locked_rewrite_text(target, lambda current: current or "", feature_dir=mission, repo_root=root) == "same\n"


def test_two_threads_rewriting_one_file_lose_no_update(mission: Path, root: Path) -> None:
    target = mission / "tasks.md"
    inside = threading.Event()
    release = threading.Event()
    results: list[str] = []

    def _first(current: str | None) -> str:
        inside.set()
        assert release.wait(10), "second writer never queued"
        return (current or "") + "A\n"

    def _run_first() -> None:
        results.append(locked_rewrite_text(target, _first, feature_dir=mission, repo_root=root))

    def _run_second() -> None:
        results.append(locked_rewrite_text(target, lambda current: (current or "") + "B\n", feature_dir=mission, repo_root=root))

    t1 = threading.Thread(target=_run_first)
    t1.start()
    assert inside.wait(10)
    t2 = threading.Thread(target=_run_second)
    t2.start()
    release.set()
    t1.join(10)
    t2.join(10)
    assert target.read_text(encoding="utf-8") == "A\nB\n"


def test_a_contended_lock_times_out_naming_the_lock(mission: Path, root: Path) -> None:
    held = threading.Event()
    done = threading.Event()

    def _holder() -> None:
        with mission_write_lock(mission, repo_root=root):
            held.set()
            done.wait(10)

    thread = threading.Thread(target=_holder)
    thread.start()
    try:
        assert held.wait(10)
        with pytest.raises(FeatureStatusLockTimeoutError) as raised, mission_write_lock(mission, repo_root=root, timeout=0.2):
            pass
        assert raised.value.error_code == "STATUS_LOCK_HELD"
    finally:
        done.set()
        thread.join(10)


# --- BookkeepingTransaction._rollback goes through the primitive --------------------------

TXN_MID8 = "01J6XW9K"
TXN_MISSION_ID = "01J6XW9K00000000000000000P"
TXN_SLUG = f"txn-mission-{TXN_MID8}"
TXN_COORD_BRANCH = f"kitty/mission-{TXN_SLUG}"


@pytest.fixture
def txn_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "txn-repo"
    feature_dir = _init_repo(repo).parent / TXN_SLUG
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": TXN_MISSION_ID, "mission_slug": TXN_SLUG, "target_branch": "main", "coordination_branch": TXN_COORD_BRANCH}) + "\n",
        encoding="utf-8",
    )
    _git(repo, "config", "commit.gpgsign", "false")
    _commit_all(repo, "seed mission")
    _git(repo, "branch", TXN_COORD_BRANCH)
    return repo


def _txn(repo: Path) -> BookkeepingTransaction:
    return BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=TXN_MISSION_ID,
        mission_slug=TXN_SLUG,
        mid8=TXN_MID8,
        destination_ref=TXN_COORD_BRANCH,
        operation="mission-write-pin",
    )


def _event(wp_id: str) -> StatusEvent:
    return build_status_event(
        mission_slug=TXN_SLUG,
        mission_id=TXN_MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane="claimed",
        actor="implementer-ivan",
    )


def _doomed_transaction_body(txn: BookkeepingTransaction, event: StatusEvent, committed_by_another_writer: bool) -> None:
    txn.append_event(event)
    if committed_by_another_writer:
        _commit_all(txn.worktree_root, "someone else committed the row")
    txn.commit("status: doomed")


def _run_doomed_transaction(repo: Path, event: StatusEvent, *, committed_by_another_writer: bool) -> tuple[Path, str]:
    """Append *event* in a transaction whose commit fails; return the Mission's log path and the failure text."""
    txn = _txn(repo)
    try:
        with txn:
            _doomed_transaction_body(txn, event, committed_by_another_writer)
    except BookkeepingCommitFailed as exc:
        return txn.feature_dir / EVENTS, str(exc)
    pytest.fail("the injected commit failure did not surface")


def test_transaction_rollback_cuts_its_own_rows_on_commit_failure(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction_module, "safe_commit", _failing_commit)
    events_path, failure = _run_doomed_transaction(txn_repo, _event("WP01"), committed_by_another_writer=False)
    assert STATUS_ROLLBACK_REFUSED not in failure
    assert not events_path.exists()


def test_transaction_rollback_refuses_rows_already_committed_and_says_so(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction_module, "safe_commit", _failing_commit)
    doomed = _event("WP01")
    events_path, failure = _run_doomed_transaction(txn_repo, doomed, committed_by_another_writer=True)
    assert STATUS_ROLLBACK_REFUSED in failure
    assert RollbackRefusal.TAIL_ALREADY_COMMITTED.value in failure
    assert doomed.event_id in events_path.read_text(encoding="utf-8")


def test_transaction_rollback_survives_an_oserror_in_the_log_cut(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction_module, "safe_commit", _failing_commit)

    def _eio(*_args: object) -> None:
        raise OSError(5, "EIO")

    monkeypatch.setattr(mw, "_cut_tail", _eio)
    doomed = _event("WP01")
    events_path, failure = _run_doomed_transaction(txn_repo, doomed, committed_by_another_writer=False)
    assert "forced commit failure" in failure
    assert STATUS_ROLLBACK_REFUSED in failure and "EIO" in failure
    # The cut failed, so the log keeps its row and status.json was not restored over it.
    assert doomed.event_id in events_path.read_text(encoding="utf-8")


def _materialize_fails_for(wp_id: str) -> Any:
    """A ``reducer.materialize`` stand-in that fails once the log holds a row for *wp_id* (after the append landed)."""

    def _materialize(feature_dir: Path) -> None:
        if wp_id in (feature_dir / EVENTS).read_text(encoding="utf-8"):
            raise RuntimeError("materialize failed after the append")

    return _materialize


def test_transaction_rollback_owns_a_unit_whose_post_append_step_failed(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F4 (two-unit shape): unit 2 is on disk when its materialize fails; the rollback must cut both units, not refuse unit 2's rows."""
    monkeypatch.setattr(transaction_module._reducer, "materialize", _materialize_fails_for("WP02"))
    txn = _txn(txn_repo)

    def _body() -> None:
        with txn:
            txn.append_event(_event("WP01"))
            txn.append_event(_event("WP02"))

    with pytest.raises(RuntimeError, match="materialize failed"):
        _body()
    assert not (txn.feature_dir / EVENTS).exists()


def test_transaction_rollback_still_cuts_unit_one_when_unit_two_never_landed(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F4: an attempted unit whose append raised before writing anything is not expected in the tail."""
    txn = _txn(txn_repo)

    def _refused(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("append refused before writing")

    def _body() -> None:
        with txn:
            txn.append_event(_event("WP01"))
            monkeypatch.setattr(transaction_module, "append_event_stream_log", _refused)
            txn.append_event(_event("WP02"))

    with pytest.raises(RuntimeError, match="append refused"):
        _body()
    assert not (txn.feature_dir / EVENTS).exists()


def test_exit_path_exception_carries_the_refused_rollback(txn_repo: Path) -> None:
    """F4: an error raised in the body (not by commit) shows STATUS_ROLLBACK_REFUSED when the rows were already committed."""
    txn = _txn(txn_repo)

    def _body() -> None:
        with txn:
            txn.append_event(_event("WP01"))
            _commit_all(txn.worktree_root, "someone else committed the row")
            raise RuntimeError("body failed")

    with pytest.raises(RuntimeError) as raised:
        _body()
    assert "body failed" in str(raised.value)
    assert STATUS_ROLLBACK_REFUSED in str(raised.value)


def test_transaction_rollback_survives_a_lock_timeout_in_the_log_cut(txn_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transaction_module, "safe_commit", _failing_commit)

    def _timeout(*_args: object, **_kwargs: object) -> None:
        raise FeatureStatusLockTimeoutError("lock held", timeout=0.1)

    monkeypatch.setattr(transaction_module, "rollback_events_log", _timeout)
    doomed = _event("WP01")
    events_path, failure = _run_doomed_transaction(txn_repo, doomed, committed_by_another_writer=False)
    assert "forced commit failure" in failure
    assert STATUS_ROLLBACK_REFUSED in failure and "lock held" in failure
    assert doomed.event_id in events_path.read_text(encoding="utf-8")


def _failing_commit(**_kwargs: object) -> None:
    raise RuntimeError("forced commit failure (test)")


# --- review cycle 1 ----------------------------------------------------------------------


def test_capture_on_an_owned_checkout_agrees_with_the_lock_taken_on_the_owned_root(root: Path, tmp_path: Path) -> None:
    feature_dir = _init_repo(root)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    _commit_all(root, "seed")
    owned_root = tmp_path / "owned"
    _git(root, "worktree", "add", "-q", "-b", "kitty/owned", str(owned_root))
    owned_dir = owned_root / "kitty-specs" / MISSION_DIRNAME
    # BookkeepingTransaction.acquire locks on owned.owned_root, keyed by the Mission dir name.
    with mission_write_lock(owned_dir, repo_root=owned_root):
        point = capture_rollback_point(owned_dir, repo_root=owned_root)
        _append(owned_dir / EVENTS, _row("01B"))
        assert rollback_events_log(point, expected_event_ids=["01B"], repo_root=owned_root).rolled_back
    with pytest.raises(RuntimeError, match="requires the Mission write lock"):
        capture_rollback_point(owned_dir, repo_root=owned_root)


def test_the_non_repository_probe_pins_git_to_the_c_locale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = tmp_path / "plain" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / EVENTS).write_text(_row("01A"), encoding="utf-8")
    point = _point(feature_dir, tmp_path / "plain")
    _append(feature_dir / EVENTS, _row("01B"))
    envs: list[object] = []
    real = run_git

    def _spy(cwd: Path, *args: str, **kwargs: Any) -> Any:
        envs.append(kwargs.get("env"))
        return real(cwd, *args, **kwargs)

    monkeypatch.setattr("specify_cli.status.mission_write.run_git", _spy)
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert rollback_events_log(point, repo_root=tmp_path / "plain").rolled_back
    assert envs and all(isinstance(env, dict) and env["LC_ALL"] == "C" for env in envs)
