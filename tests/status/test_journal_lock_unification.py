"""F2-T1: lock/WAL unification between the locked ``StatusEvent`` writer
(``status/emit.py``) and the previously-unlocked lifecycle appenders
(``status/lifecycle_events.py``).

Regression coverage for the lost-write race documented in
``m1-contract-drafts/F2.md`` section 2.2: ``store._append_serialized_atomic``
(locked, temp-write+rename) and ``lifecycle_events._atomic_append``
(unlocked, plain ``O_APPEND``) both wrote the same
``status.events.jsonl``/``.kittify/canonical-events.jsonl`` files without
coordinating, so a concurrent locked writer could silently clobber an
unlocked writer's just-appended line.

Test IDs below map to F2.md section 4's negative/fault/race/compatibility
matrix: K1, K2, C1, CO1-CO4, FT1, FT2, WAL1. (CL2 pinned the local projection
against the persisted host LamportClock; that clock died with the sync
transport in issue #5, so the independence property it guarded holds vacuously.)
"""

from __future__ import annotations

import json
import multiprocessing
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git_init(path: Path) -> None:
    """Minimal git init for test fixtures that need a real git root."""
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )


import specify_cli.status.store as status_store
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.lifecycle_events import (
    emit_wp_created_local,
    mission_event_log_path,
)
from specify_cli.status.locking import (
    _PROJECT_LOCK_SENTINEL,
    feature_status_lock,
    feature_status_lock_path,
    project_event_log_lock,
)
from specify_cli.status.models import TransitionRequest
from specify_cli.status.reducer import materialize
from specify_cli.status.store import (
    append_raw_rows_atomic,
    is_non_lane_event,
    read_events_raw,
)

from tests.status.conftest import seed_wp_to_planned as _seed_planned

_MISSION_SLUG = "journal-lock-unification"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    return tmp_path


@pytest.fixture()
def feature_dir(repo: Path) -> Path:
    fd = repo / "kitty-specs" / _MISSION_SLUG
    fd.mkdir(parents=True)
    return fd


# ---------------------------------------------------------------------------
# append_raw_rows_atomic (public, path-parameterized) -- promotion checks
# ---------------------------------------------------------------------------


def test_append_raw_rows_atomic_is_public_and_path_parameterized(
    tmp_path: Path,
) -> None:
    """The public wrapper writes to an explicit path, not a feature_dir-
    derived one -- required so it can serve BOTH status.events.jsonl
    (inside a feature_dir) and .kittify/canonical-events.jsonl (which is
    not inside any feature_dir) as F2.md section 3.1 item 3 requires."""
    target = tmp_path / ".kittify" / "canonical-events.jsonl"
    append_raw_rows_atomic(target, [{"event_type": "X", "a": 1}])
    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event_type"] == "X"


def test_append_raw_rows_atomic_matches_existing_status_events_behavior(
    tmp_path: Path,
) -> None:
    """Same primitive, same on-disk shape as the pre-existing private
    _append_serialized_atomic used for StatusEvent rows (behavior-
    preserving promotion, F2.md section 3.3)."""
    feature_dir = tmp_path
    path = feature_dir / status_store.EVENTS_FILENAME
    append_raw_rows_atomic(path, [{"b": 2, "a": 1}])
    # sanitize_event_for_log + sort_keys=True -> deterministic key order
    raw = path.read_text(encoding="utf-8").strip()
    assert json.loads(raw) == {"a": 1, "b": 2}
    assert list(raw) == list(json.dumps({"a": 1, "b": 2}, sort_keys=True))


# ---------------------------------------------------------------------------
# project_event_log_lock -- new sibling lock
# ---------------------------------------------------------------------------


def test_project_event_log_lock_path_uses_fixed_sentinel(repo: Path) -> None:
    with project_event_log_lock(repo) as lock_path:
        assert lock_path.name == f"{_PROJECT_LOCK_SENTINEL}.status.lock"
        assert lock_path.parent.name == "spec-kitty-locks"


def test_project_event_log_lock_is_reentrant_per_thread(repo: Path) -> None:
    # nested acquisition in the same thread must not deadlock
    with project_event_log_lock(repo), project_event_log_lock(repo):
        pass


def test_project_event_log_lock_distinct_from_any_mission_lock(
    repo: Path,
) -> None:
    with project_event_log_lock(repo) as p_lock:
        pass
    m_lock = feature_status_lock_path(repo, _MISSION_SLUG)
    assert p_lock != m_lock


# ---------------------------------------------------------------------------
# K1/K2 -- kill/crash mid-write leaves the original untouched
# ---------------------------------------------------------------------------


def test_k1_fsync_failure_leaves_original_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "status.events.jsonl"
    append_raw_rows_atomic(path, [{"event_type": "First", "n": 1}])
    original = path.read_text(encoding="utf-8")

    def _raise_fsync(_fd: int) -> None:
        raise OSError("simulated kill before fsync")

    monkeypatch.setattr(status_store.os, "fsync", _raise_fsync)

    with pytest.raises(OSError, match="simulated kill before fsync"):
        append_raw_rows_atomic(path, [{"event_type": "Second", "n": 2}])

    assert path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".status.events.jsonl.*.tmp")) == []


def test_k2_rehomed_lifecycle_writer_survives_replace_failure(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-process-shape variant of K1 for the REHOMED writer specifically
    (extends test_store.py's existing replace-failure pattern, which only
    ever covered the pre-rehoming StatusEvent path)."""
    first = emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        wp_title="First",
    )
    assert first is not None
    log_path = mission_event_log_path(feature_dir)
    original = log_path.read_text(encoding="utf-8")

    def _raise_replace(_src: Path, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(status_store.os, "replace", _raise_replace)

    # append_lifecycle_event never raises (compatibility contract, F2.md
    # section 3.3/6.2) -- the OSError is caught internally and surfaced as
    # a None return, exactly like the pre-existing write-failure contract.
    result = emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP02",
        wp_title="Second",
    )
    assert result is None
    assert log_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# C1 -- crash before replace leaves original untouched, soft-fail contract
# ---------------------------------------------------------------------------


def test_c1_fsync_os_error_during_rehomed_append_returns_none(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_path = mission_event_log_path(feature_dir)

    def _raise_fsync(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(status_store.os, "fsync", _raise_fsync)

    result = emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        wp_title="First",
    )
    assert result is None
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# CO1 -- THE regression test for the lost-write race
# ---------------------------------------------------------------------------


def _mp_emit_transition(feature_dir: str, mission_slug: str, wp_id: str, queue) -> None:
    try:
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=Path(feature_dir),
                mission_slug=mission_slug,
                wp_id=wp_id,
                to_lane="claimed",
                actor="implementer",
            )
        )
        queue.put(("transition_ok", event.event_id))
    except Exception as exc:  # noqa: BLE001 -- report, never crash silently
        queue.put(("transition_error", repr(exc)))


def _mp_emit_lifecycle(feature_dir: str, mission_slug: str, wp_id: str, queue) -> None:
    try:
        envelope = emit_wp_created_local(
            Path(feature_dir),
            mission_slug=mission_slug,
            wp_id=wp_id,
            wp_title=f"Title for {wp_id}",
        )
        queue.put(("lifecycle_ok", envelope.get("event_id") if envelope else None))
    except Exception as exc:  # noqa: BLE001
        queue.put(("lifecycle_error", repr(exc)))


@pytest.mark.stress
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="multiprocessing 'fork' start method is POSIX-only",
)
def test_co1_locked_and_rehomed_writers_never_lose_a_row(feature_dir: Path) -> None:
    """The exact race from F2.md section 2.2: a locked StatusEvent writer
    and a (post-fix) locked lifecycle writer race on the same
    status.events.jsonl. Both rows must survive every iteration -- this
    test is red against the unmodified _atomic_append(open('a')) path and
    green only once lifecycle_events.py is rehomed onto the shared lock +
    crash-safe primitive."""
    ctx = multiprocessing.get_context("fork")
    for i in range(10):
        transition_wp_id = f"TWP{i:02d}"
        lifecycle_wp_id = f"LWP{i:02d}"
        _seed_planned(feature_dir, transition_wp_id, slug=_MISSION_SLUG)
        queue: multiprocessing.Queue = ctx.Queue()
        proc_a = ctx.Process(
            target=_mp_emit_transition,
            args=(str(feature_dir), _MISSION_SLUG, transition_wp_id, queue),
        )
        proc_b = ctx.Process(
            target=_mp_emit_lifecycle,
            args=(str(feature_dir), _MISSION_SLUG, lifecycle_wp_id, queue),
        )
        proc_a.start()
        proc_b.start()
        results = [queue.get(timeout=30) for _ in range(2)]
        proc_a.join(timeout=30)
        proc_b.join(timeout=30)

        assert proc_a.exitcode == 0, f"iter {i}: transition worker crashed"
        assert proc_b.exitcode == 0, f"iter {i}: lifecycle worker crashed"
        errors = [r for r in results if r[0].endswith("_error")]
        assert not errors, f"iter {i}: worker errors: {errors}"

    raw_rows = read_events_raw(feature_dir)
    lifecycle_rows = [r for r in raw_rows if is_non_lane_event(r) and r.get("event_type") == "WPCreated"]
    assert len(lifecycle_rows) == 10, f"expected 10 surviving WPCreated rows (one per iteration), got {len(lifecycle_rows)} -- a lost write means the race is back"


def test_co2_two_concurrent_wp_created_calls_both_survive(feature_dir: Path) -> None:
    ctx = multiprocessing.get_context("fork")
    queue: multiprocessing.Queue = ctx.Queue()
    proc_a = ctx.Process(
        target=_mp_emit_lifecycle,
        args=(str(feature_dir), _MISSION_SLUG, "WP01", queue),
    )
    proc_b = ctx.Process(
        target=_mp_emit_lifecycle,
        args=(str(feature_dir), _MISSION_SLUG, "WP02", queue),
    )
    proc_a.start()
    proc_b.start()
    results = [queue.get(timeout=30) for _ in range(2)]
    proc_a.join(timeout=30)
    proc_b.join(timeout=30)

    assert proc_a.exitcode == 0 and proc_b.exitcode == 0
    oks = [r for r in results if r[0] == "lifecycle_ok"]
    assert len(oks) == 2

    log_path = mission_event_log_path(feature_dir)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # each line must parse -- no interleaved partial writes


def test_co3_project_and_mission_locks_do_not_mutually_block(feature_dir: Path, repo: Path) -> None:
    """Different lock sentinels (mission vs project) never contend."""
    # Must be able to take the project lock while the mission lock is held,
    # from the SAME thread even -- proves they are independent locks, not
    # aliases of one another.
    with (
        feature_status_lock(repo, _MISSION_SLUG, timeout=2),
        project_event_log_lock(repo, timeout=2),
    ):
        pass


def test_co4_reentrant_caller_can_invoke_rehomed_appender_without_deadlock(
    feature_dir: Path,
) -> None:
    """A caller already holding feature_status_lock can call a rehomed
    lifecycle appender that acquires the SAME mission's lock in the same
    thread -- proves the existing re-entrant bookkeeping still holds."""
    # The realistic re-entrancy path: emit_status_transition holds the
    # lock across the whole transaction; a lifecycle appender invoked
    # from inside that same lock scope must not deadlock.
    repo_root = feature_dir.parent.parent
    with feature_status_lock(repo_root, _MISSION_SLUG, timeout=2):
        result = emit_wp_created_local(
            feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            wp_title="Reentrant",
        )
        assert result is not None


# ---------------------------------------------------------------------------
# FT1/FT2 -- flat-truth precedence unaffected by rehoming
# ---------------------------------------------------------------------------


def test_ft1_rehomed_lifecycle_row_stays_non_lane(feature_dir: Path) -> None:
    _seed_planned(feature_dir, "WP01", slug=_MISSION_SLUG)
    emit_status_transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            to_lane="claimed",
            actor="implementer",
        )
    )
    emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        wp_title="T",
    )

    raw_rows = read_events_raw(feature_dir)
    lifecycle_rows = [r for r in raw_rows if r.get("event_type") == "WPCreated"]
    assert len(lifecycle_rows) == 1
    assert is_non_lane_event(lifecycle_rows[0]) is True

    snapshot = materialize(feature_dir)
    # WP01's lane is driven only by the StatusEvent transition, never by
    # the co-resident lifecycle row.
    assert snapshot.work_packages["WP01"]["lane"] == "claimed"


# ---------------------------------------------------------------------------
# WAL1 -- fsync/replace ordering for the rehomed writer
# ---------------------------------------------------------------------------


def test_wal1_fsync_precedes_replace_for_rehomed_lifecycle_writer(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    call_order: list[str] = []

    real_fsync = status_store.os.fsync
    real_replace = status_store.os.replace

    def _tracking_fsync(fd, *a, **kw):  # noqa: ANN001
        call_order.append("fsync")
        return real_fsync(fd, *a, **kw)

    def _tracking_replace(src, dst, *a, **kw):  # noqa: ANN001
        call_order.append("replace")
        return real_replace(src, dst, *a, **kw)

    monkeypatch.setattr(status_store.os, "fsync", _tracking_fsync)
    monkeypatch.setattr(status_store.os, "replace", _tracking_replace)

    result = emit_wp_created_local(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id="WP01",
        wp_title="T",
    )
    assert result is not None

    # file fsync -> replace -> directory fsync, strictly in that order.
    # Mission cross-os-primitive-unification WP05/#4714 migrated the status
    # lock (specify_cli.status.locking) onto kernel.locks.machine_file_lock,
    # which durably persists its own holder LockRecord with a real
    # os.fsync(fd) on every acquire (unlike the pre-migration filelock, which
    # never fsynced) -- this monkeypatches the GLOBAL os.fsync, so that one
    # extra, legitimate fsync from acquiring the status lock around the
    # replace step is observed here too, between the file fsync and the
    # replace. The ordering invariants this test actually cares about (file
    # fsync first, replace only after a fsync, directory fsync last) are
    # unaffected.
    assert call_order[0] == "fsync"
    assert "replace" in call_order
    assert call_order.index("replace") > call_order.index("fsync")
    assert call_order[-1] == "fsync"
    assert call_order.count("fsync") == 3
