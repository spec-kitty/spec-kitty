"""Writer serialization pins (fsm-write-path-integrity WP01, US1 / SC-001 / SC-008).

Part 1 -- the rollback-truncate race. ``BookkeepingTransaction._rollback``
restores ``status.events.jsonl`` by truncating to the byte offset captured at
the transaction's first append (``transaction.py``, ``fh.truncate(self._pre_emit_size)``).
Any writer that appends WITHOUT holding the mission status lock can land inside
that window and is silently truncated away with the rolled-back event.

The retrospective lifecycle appender is the live post-merge writer that does
exactly that on main, so it is the reproduction vehicle here.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

import specify_cli.coordination.transaction as transaction_module
from specify_cli.coordination.transaction import (
    BookkeepingCommitFailed,
    BookkeepingTransaction,
)
from specify_cli.retrospective.lifecycle_events import _append_retro_lifecycle_event
from specify_cli.status.emit import build_status_event
from specify_cli.status.models import StatusEvent

# Part 2 -- SC-008 lock-held assertions, one per writer family (see below).
import specify_cli.migration.backfill_runtime_state as brs
import specify_cli.migration.verdict_provenance_backfill as vpb
import specify_cli.status.store as status_store
from kernel.clock import UTC, datetime
from specify_cli.decisions.emit import emit_decision_opened
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.migration.rebuild_state import rebuild_event_log
from specify_cli.retrospective.events import FailedPayload, emit_retrospective_event
from specify_cli.retrospective.lifecycle_events import Actor, emit_capture_failed
from specify_cli.retrospective.schema import ActorRef
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status import (
    TransitionRequest,
    WPInnerStateDelta,
    emit_inner_state_changed,
    emit_status_transition,
)
from specify_cli.status.emit import emit_status_transition_batch
from specify_cli.status.lifecycle_events import emit_wp_created_local
from specify_cli.status.locking import _get_thread_locks
from tests.status.conftest import seed_wp_to_planned
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MID8 = "01J6XW9K"
MISSION_ID = "01J6XW9K00000000000000000P"
# The slug embeds the mid8 so the transaction dir name equals the slug
# (``_mission_specs_dir_name`` is idempotent on an embedded suffix). This
# isolates the rollback race from the lock-key convention (FR-004, T006),
# which has its own pin in ``tests/status/test_locking_key.py``.
MISSION_SLUG = f"writer-serialization-{MID8}"
FEATURE_DIRNAME = MISSION_SLUG
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Tmp repo with a modern coordination-topology mission seeded."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    feature_dir = r / "kitty-specs" / FEATURE_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": MISSION_ID,
                "mission_slug": MISSION_SLUG,
                "target_branch": "main",
                "coordination_branch": COORD_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(r, "add", "kitty-specs")
    _git(r, "commit", "-q", "-m", "seed mission")
    _git(r, "branch", COORD_BRANCH)
    return r


def _make_event(wp_id: str, to_lane: str = "claimed") -> StatusEvent:
    return build_status_event(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane=to_lane,
        actor="implementer-ivan",
    )


def _acquire(repo: Path) -> Any:
    return BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation="writer-serialization",
    )


def _event_ids(events_path: Path) -> list[str]:
    return [json.loads(line)["event_id"] for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_retro_append_waits_for_rollback_and_lands_after_truncate(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retrospective lifecycle append never lands inside the rollback window.

    Ordering (SC-001, permanent functional pin per C-009 -- this was the
    red-first repro for the rollback-truncate race): the retrospective append
    runs in a second thread and blocks on the mission status lock the
    transaction holds; the forced commit failure rolls the transaction back
    (truncate) and releases the lock; only then does the append land --
    after the truncate, so it is never inside the window. Before WP01 the
    append was unlocked, landed inside the window immediately, and was
    truncated away with the transaction's own event.
    """
    # Seed: one committed transaction so the log exists pre-emit (a missing
    # pre-emit log is unlinked wholesale on rollback -- a different arm).
    with _acquire(repo) as txn:
        seed = _make_event("WP01")
        txn.append_event(seed)
        txn.commit("status: seed")
    events_path = txn.feature_dir / "status.events.jsonl"
    assert _event_ids(events_path) == [seed.event_id]

    def _forced_commit_failure(**_kwargs: Any) -> None:
        raise RuntimeError("forced commit failure (test)")

    monkeypatch.setattr(transaction_module, "safe_commit", _forced_commit_failure)

    retro_event = {
        "type": "RetrospectiveCaptureFailed",
        "event_id": "01RETROEVENT00000000000001",
        "lamport": 99,
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
    }
    thread_errors: list[BaseException] = []

    def _racing_append(feature_dir: Path) -> None:
        try:
            _append_retro_lifecycle_event(feature_dir, retro_event, lock_timeout=10.0)
        except BaseException as exc:
            thread_errors.append(exc)

    doomed = _make_event("WP02")
    racers: list[threading.Thread] = []

    def _commit_racing_transaction() -> None:
        with _acquire(repo) as txn:
            txn.append_event(doomed)  # captures _pre_emit_size
            racers.append(threading.Thread(target=_racing_append, args=(txn.feature_dir,)))
            racers[0].start()
            # Unlocked (main): the append lands now. Locked (fixed): the racer
            # blocks here on the lock until the transaction releases it.
            racers[0].join(timeout=2.0)
            txn.commit("status: should fail")  # -> _rollback() -> truncate

    with pytest.raises(BookkeepingCommitFailed, match=r"safe_commit (recovery )?failed on"):
        _commit_racing_transaction()
    (racer,) = racers

    racer.join(timeout=15.0)
    assert not racer.is_alive(), "racing append never completed"
    assert not thread_errors, thread_errors

    ids = _event_ids(events_path)
    assert doomed.event_id not in ids, "positive control: rollback removed the txn event"
    assert seed.event_id in ids
    assert retro_event["event_id"] in ids, "SC-001: retro append was truncated away"


# ---------------------------------------------------------------------------
# Part 2 -- SC-008: a lock-held assertion for every writer family
# ---------------------------------------------------------------------------
#
# Census (data-model.md section 2, FR-001): (1) emit single + inner-state,
# (2) lifecycle appender, (3) BookkeepingTransaction, (4) retrospective
# run-terminus, (5) retrospective lifecycle, (6) verdict-provenance backfill,
# (7) runtime-state backfill -- plus the batch door (FR-018, WP02) -- and the
# WP07 addendum found by WP03's writes gate: (8) decision-point rows
# (``decisions/emit.py``), (9) the legacy whole-log rebuild
# (``migration/rebuild_state.py``).
#
# Every store write funnels through ``store.append_raw_rows_atomic`` ->
# ``_fsync_directory(path.parent)``; the recorder snapshots this thread's held
# locks at that moment and requires ``<feature_dir.name>.status.lock`` among
# them. Family 9 is a whole-log rewrite, not a store append: its durable step
# is ``os.replace(tmp, <feature_dir>/status.events.jsonl)``, so the recorder
# also snapshots every ``os.replace`` whose destination is the event log.
# Families 1-3 were already locked: those cases are pins.


class _HeldLocksAtWrite:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.snapshots: list[tuple[Path, set[str]]] = []
        original = status_store._fsync_directory
        original_replace = os.replace

        def _record(directory: Path) -> None:
            self.snapshots.append((directory, set(_get_thread_locks())))
            original(directory)

        def _record_replace(src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
            if Path(dst).name == status_store.EVENTS_FILENAME:
                self.snapshots.append((Path(dst).parent, set(_get_thread_locks())))
            original_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(status_store, "_fsync_directory", _record)
        monkeypatch.setattr(os, "replace", _record_replace)

    def assert_locked_for(self, feature_dir: Path) -> None:
        writes = [held for directory, held in self.snapshots if directory == feature_dir]
        assert writes, f"no store write observed for {feature_dir}"
        expected_name = f"{feature_dir.name}.status.lock"
        for held in writes:
            assert any(Path(lock).name == expected_name for lock in held), f"store wrote {feature_dir} without holding {expected_name}; held={sorted(held)}"


def _git_sandbox(tmp_path: Path) -> Path:
    """Make ``tmp_path`` a checkout: production mission trees always have a git
    root, and family 2's ``_lifecycle_write_lock`` deliberately degrades to
    ``nullcontext()`` when no root resolves (documented per-site choice)."""
    if not (tmp_path / ".git").exists():
        _git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


def _flat_mission(tmp_path: Path, name: str = "family-pin-01AAAAAA") -> Path:
    fd = _git_sandbox(tmp_path) / "kitty-specs" / name
    fd.mkdir(parents=True)
    seed_wp_to_planned(fd, "WP01", slug=name)
    return fd


def _family_1_emit_single(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    emit_status_transition(TransitionRequest(feature_dir=fd, mission_slug=fd.name, wp_id="WP01", to_lane="claimed", actor="pin"))
    return fd


def _family_1_inner_state(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    emit_inner_state_changed(fd, "WP01", WPInnerStateDelta(shell_pid=4242), actor="pin", mission_slug=fd.name)
    return fd


def _family_2_lifecycle_appender(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    assert emit_wp_created_local(fd, mission_slug=fd.name, wp_id="WP02", wp_title="Pin") is not None
    return fd


def _family_4_retro_run_terminus(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    emit_retrospective_event(
        feature_dir=fd,
        mission_slug=fd.name,
        mission_id=MISSION_ID,
        mid8=MID8,
        actor=ActorRef(kind="runtime", id="pin"),
        event_name="retrospective.failed",
        payload=FailedPayload(failure_code="pin", message="pin"),
    )
    return fd


def _family_5_retro_lifecycle(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    emit_capture_failed(
        MISSION_ID,
        fd.name,
        tmp_path,
        failure_category="other",
        failure_message="pin",
        remediation_hint=None,
        policy_source={},
        attempted_provenance_kind="runtime_post_completion",
        missing_artifacts=None,
        actor=Actor(kind="runtime", id="pin"),
    )
    return fd


def _family_6_verdict_backfill(tmp_path: Path) -> Path:
    fd = _git_sandbox(tmp_path) / "kitty-specs" / "family-pin-01AAAAAA"
    fd.mkdir(parents=True)
    path = fd / "tasks" / "WP01-pin" / "review-cycle-1.md"
    ReviewCycleArtifact(
        cycle_number=1,
        wp_id="WP01",
        mission_slug=fd.name,
        reviewer_agent="r",
        reviewed_at="2026-01-01T00:00:00+00:00",
    ).write(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(f"---\nverdict: rejected\n{text[4:]}", encoding="utf-8")
    assert vpb.backfill_verdict_provenance(fd).appended_count == 1
    return fd


def _family_7_runtime_backfill(tmp_path: Path) -> Path:
    fd = build_mission(_git_sandbox(tmp_path))
    assert brs.backfill_runtime_state(fd).action == "wrote"
    return fd


def _family_8_decision_point(tmp_path: Path) -> Path:
    fd = _flat_mission(tmp_path)
    entry = IndexEntry(
        decision_id="01AAAAAAAAAAAAAAAAAAAAAAAA",
        origin_flow=OriginFlow.CHARTER,
        step_id="charter.q1",
        slot_key=None,
        input_key="pin",
        question="Pin?",
        options=("yes", "no"),
        status=DecisionStatus.OPEN,
        final_answer=None,
        rationale=None,
        other_answer=False,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        resolved_at=None,
        resolved_by=None,
        mission_id=MISSION_ID,
        mission_slug=fd.name,
    )
    assert emit_decision_opened(tmp_path, fd.name, decision_id=entry.decision_id, entry=entry, actor="pin") >= 1
    return fd


def _family_9_rebuild_state(tmp_path: Path) -> Path:
    fd = _git_sandbox(tmp_path) / "kitty-specs" / "family-pin-01AAAAAA"
    (fd / "tasks").mkdir(parents=True)
    (fd / "tasks" / "WP01-pin.md").write_text(
        "---\nwp_code: 'WP01'\ntitle: Pin\nlane: 'in_progress'\ndependencies: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    assert not rebuild_event_log(fd, fd.name, {}).skipped
    return fd


@pytest.mark.parametrize(
    "family",
    [
        pytest.param(_family_1_emit_single, id="1-emit-single"),
        pytest.param(_family_1_inner_state, id="1-inner-state"),
        pytest.param(_family_2_lifecycle_appender, id="2-lifecycle-appender"),
        pytest.param(_family_4_retro_run_terminus, id="4-retro-run-terminus"),
        pytest.param(_family_5_retro_lifecycle, id="5-retro-lifecycle"),
        pytest.param(_family_6_verdict_backfill, id="6-verdict-backfill"),
        pytest.param(_family_7_runtime_backfill, id="7-runtime-backfill"),
        pytest.param(_family_8_decision_point, id="8-decision-point"),
        pytest.param(_family_9_rebuild_state, id="9-rebuild-state"),
    ],
)
def test_family_writes_only_while_holding_its_mission_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    family: Any,
) -> None:
    recorder = _HeldLocksAtWrite(monkeypatch)
    feature_dir = family(tmp_path)
    recorder.assert_locked_for(feature_dir)


def test_family_3_transaction_writes_only_while_holding_its_mission_lock(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _HeldLocksAtWrite(monkeypatch)
    with _acquire(repo) as txn:
        txn.append_event(_make_event("WP01"))
        txn.commit("status: family 3 pin")
    recorder.assert_locked_for(txn.feature_dir)


def test_batch_door_writes_only_while_holding_its_mission_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _HeldLocksAtWrite(monkeypatch)
    fd = _flat_mission(tmp_path)
    emit_status_transition_batch([TransitionRequest(feature_dir=fd, mission_slug=fd.name, wp_id="WP01", to_lane="claimed", actor="pin")])
    recorder.assert_locked_for(fd)
