"""Locking pins for the two migration backfill writers (WP01 T004/T005).

Families 6 and 7 of the writer census (data-model.md section 2):

* ``verdict_provenance_backfill.backfill_verdict_provenance`` -- the
  ``slot_present`` event-log read and the append now share ONE lock
  acquisition (T004).
* ``backfill_runtime_state.backfill_runtime_state`` -- the claim-anchor read,
  the idempotency read and the (now single, combined) append share ONE lock
  acquisition (T005).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

import specify_cli.migration.backfill_runtime_state as brs
import specify_cli.migration.verdict_provenance_backfill as vpb
import specify_cli.status.store as status_store
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status import feature_status_lock, read_event_stream
from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
from specify_cli.workspace.root_resolver import resolve_status_lock_root
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _expected_lock(feature_dir: Path) -> str:
    return str(feature_status_lock_path(resolve_status_lock_root(feature_dir), feature_dir.name))


class _LockObserver:
    """Snapshot the locks held by this thread at the store write and at reads."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, module: Any, read_names: tuple[str, ...]) -> None:
        self.at_write: list[set[str]] = []
        self.at_read: dict[str, list[set[str]]] = {name: [] for name in read_names}
        original_fsync = status_store._fsync_directory

        def _record_write(directory: Path) -> None:
            self.at_write.append(set(_get_thread_locks()))
            original_fsync(directory)

        monkeypatch.setattr(status_store, "_fsync_directory", _record_write)
        for name in read_names:
            original = getattr(module, name)

            def _record_read(*args: Any, _name: str = name, _orig: Any = original, **kwargs: Any) -> Any:
                self.at_read[_name].append(set(_get_thread_locks()))
                return _orig(*args, **kwargs)

            monkeypatch.setattr(module, name, _record_read)


def _write_legacy_verdict(feature_dir: Path, wp_id: str = "WP01") -> None:
    sub_dir = feature_dir / "tasks" / f"{wp_id}-locking"
    artifact = ReviewCycleArtifact(
        cycle_number=1,
        wp_id=wp_id,
        mission_slug=feature_dir.name,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-01-01T00:00:00+00:00",
    )
    path = sub_dir / "review-cycle-1.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    path.write_text(f"---\nverdict: rejected\n{text[4:]}", encoding="utf-8")


@pytest.fixture
def verdict_feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / "042-verdict-locking"
    fd.mkdir(parents=True)
    _write_legacy_verdict(fd)
    return fd


# ---------------------------------------------------------------------------
# T004 -- verdict-provenance backfill
# ---------------------------------------------------------------------------


def test_verdict_backfill_reads_and_appends_under_one_lock(verdict_feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observer = _LockObserver(monkeypatch, vpb, ("event_sourced_review_result",))
    outcome = vpb.backfill_verdict_provenance(verdict_feature_dir)
    assert outcome.appended_wp_ids == ("WP01",)
    expected = _expected_lock(verdict_feature_dir)
    assert observer.at_read["event_sourced_review_result"], "slot_present read never ran"
    assert all(expected in held for held in observer.at_read["event_sourced_review_result"])
    assert len(observer.at_write) == 1 and expected in observer.at_write[0]
    assert expected not in _get_thread_locks()


def test_verdict_backfill_is_idempotent(verdict_feature_dir: Path) -> None:
    assert vpb.backfill_verdict_provenance(verdict_feature_dir).appended_count == 1
    assert vpb.backfill_verdict_provenance(verdict_feature_dir).appended_count == 0


def test_verdict_backfill_waits_for_a_concurrent_lock_holder(verdict_feature_dir: Path) -> None:
    hold_seconds = 0.6
    released_at: list[float] = []
    ready = threading.Event()

    def _hold() -> None:
        with feature_status_lock(resolve_status_lock_root(verdict_feature_dir), verdict_feature_dir.name, timeout=5):
            ready.set()
            time.sleep(hold_seconds)
            released_at.append(time.monotonic())

    holder = threading.Thread(target=_hold)
    holder.start()
    try:
        assert ready.wait(timeout=5)
        outcome = vpb.backfill_verdict_provenance(verdict_feature_dir)
        finished_at = time.monotonic()
    finally:
        holder.join(timeout=10)
    assert not holder.is_alive()
    assert outcome.appended_count == 1
    assert released_at and finished_at >= released_at[0], "backfill did not wait for the holder"


# ---------------------------------------------------------------------------
# T005 -- runtime-state backfill
# ---------------------------------------------------------------------------


def test_runtime_backfill_reads_and_appends_under_one_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = build_mission(tmp_path)
    observer = _LockObserver(monkeypatch, brs, ("read_event_stream", "_claim_anchors"))
    result = brs.backfill_runtime_state(feature_dir)
    assert result.action == "wrote" and result.seeded_count > 0
    expected = _expected_lock(feature_dir)
    for name, snapshots in observer.at_read.items():
        assert snapshots, f"{name} never ran"
        assert all(expected in held for held in snapshots), name
    assert len(observer.at_write) == 1, "the seed pair must land in ONE atomic write"
    assert expected in observer.at_write[0]
    assert expected not in _get_thread_locks()


def test_runtime_backfill_single_write_carries_transitions_and_annotations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = build_mission(tmp_path)
    calls: list[list[Any]] = []
    original = brs.append_event_stream_atomic_verified

    def _record(fd: Path, events: list[Any]) -> None:
        calls.append(list(events))
        original(fd, events)

    monkeypatch.setattr(brs, "append_event_stream_atomic_verified", _record)
    result = brs.backfill_runtime_state(feature_dir)
    assert len(calls) == 1
    kinds = {type(event).__name__ for event in calls[0]}
    assert kinds == {"StatusEvent", "InnerStateChanged"}
    assert len(calls[0]) == result.seeded_count
    stream = read_event_stream(feature_dir)
    assert {a.event_id for a in stream.annotations} >= {e.event_id for e in calls[0] if type(e).__name__ == "InnerStateChanged"}


def test_runtime_backfill_is_idempotent(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    assert brs.backfill_runtime_state(feature_dir).action == "wrote"
    second = brs.backfill_runtime_state(feature_dir)
    assert second.action == "skip"
    assert second.seeded_count == 0


def test_runtime_backfill_dry_run_writes_nothing_and_releases_lock(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    result = brs.backfill_runtime_state(feature_dir, dry_run=True)
    assert result.action == "wrote" and result.reason == "dry-run (no write)"
    assert brs.backfill_runtime_state(feature_dir).action == "wrote"
    assert _expected_lock(feature_dir) not in _get_thread_locks()


def test_runtime_backfill_waits_for_a_concurrent_lock_holder(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    hold_seconds = 0.6
    released_at: list[float] = []
    ready = threading.Event()

    def _hold() -> None:
        with feature_status_lock(resolve_status_lock_root(feature_dir), feature_dir.name, timeout=5):
            ready.set()
            time.sleep(hold_seconds)
            released_at.append(time.monotonic())

    holder = threading.Thread(target=_hold)
    holder.start()
    try:
        assert ready.wait(timeout=5)
        result = brs.backfill_runtime_state(feature_dir)
        finished_at = time.monotonic()
    finally:
        holder.join(timeout=10)
    assert not holder.is_alive()
    assert result.action == "wrote"
    assert released_at and finished_at >= released_at[0], "backfill did not wait for the holder"


def test_backfill_never_mints_a_git_dir_in_a_bare_tree(tmp_path: Path) -> None:
    """The lock's non-git degrade must not turn the tree into a fake repo root."""
    feature_dir = build_mission(tmp_path)
    brs.backfill_runtime_state(feature_dir)
    assert not (tmp_path / ".git").exists()
    assert (tmp_path / ".kittify" / "spec-kitty-locks").is_dir()
