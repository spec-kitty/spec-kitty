"""Targeted diff-coverage tests for #2684 runtime-state-eviction critical-path
lines (status/*). Each test pins one otherwise-uncovered new branch surfaced by
``diff-cover`` against ``origin/main``:

* ``emit._infer_subtasks_complete`` frontmatter-roster + event-sourced snapshot
  completion (authored ``subtasks:`` roster, fail-closed silent snapshot);
* ``store.append_annotations_atomic_verified`` success round-trip, append-failure
  wrapping, and readback-miss fail-loud;
* ``store.is_non_lane_event`` annotation discriminator;
* ``store.read_event_stream`` malformed-annotation and unknown-kind fail-loud;
* ``wp_state.annotate`` malformed-wp_id and empty-delta refusals;
* model serialization/validation edges (``WPInnerStateDelta.to_dict`` replace
  channel, ``InnerStateChanged.from_dict`` ULID/kind validation).

These are pure-unit proofs; no CLI, git, or SaaS surface is exercised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import store as _store
from specify_cli.status.emit import _infer_subtasks_complete
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.store import (
    StoreError,
    append_annotations_atomic_verified,
    is_non_lane_event,
    read_event_stream,
)
from specify_cli.status.wp_state import annotate
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "diffcov-2684-gaps"


def _ulid(suffix: str) -> str:
    """A syntactically valid 26-char ULID from a short suffix."""
    return ("01KX" + suffix).ljust(26, "0")[:26]


def _seed_roster(feature_dir: Path, wp_id: str, subtasks: list[str]) -> None:
    """Author the WP frontmatter ``subtasks:`` roster the gate now reads.

    Since #2816 IC-10 the roster (which ``T###`` ids belong to *wp_id*) is the
    authored frontmatter list, not ``tasks.md`` checkbox rows.
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    subtasks_header = "subtasks:" if subtasks else "subtasks: []"
    lines = ["---", f"work_package_id: {wp_id}", subtasks_header]
    lines.extend(f"- {task_id}" for task_id in subtasks)
    lines.extend(["---", "", f"# {wp_id}", ""])
    (tasks_dir / f"{wp_id}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_wp_entry(feature_dir: Path, wp_id: str) -> None:
    """Seed a ``planned -> in_progress`` transition so the WP has a snapshot entry."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=_ulid("TRN"),
            mission_slug=_MISSION_SLUG,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_subtasks(feature_dir: Path, wp_id: str, subtasks: dict[str, Lane]) -> None:
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=_ulid("ANN"),
                wp_id=wp_id,
                at="2026-01-01T00:01:00+00:00",
                actor="test",
                delta=WPInnerStateDelta(subtasks=subtasks),
            )
        ],
    )


# ---------------------------------------------------------------------------
# emit._infer_subtasks_complete — frontmatter roster + event-sourced snapshot
# ---------------------------------------------------------------------------


def test_infer_subtasks_complete_all_done(tmp_path: Path) -> None:
    """An authored roster whose every id is DONE in the snapshot is complete."""
    _seed_roster(tmp_path, "WP01", ["T001", "T002"])
    _seed_wp_entry(tmp_path, "WP01")
    _seed_subtasks(tmp_path, "WP01", {"T001": Lane.DONE, "T002": Lane.DONE})
    assert _infer_subtasks_complete(tmp_path, "WP01") is True


def test_infer_subtasks_partial_is_incomplete(tmp_path: Path) -> None:
    """A roster id still not DONE in the snapshot blocks (fail-closed)."""
    _seed_roster(tmp_path, "WP01", ["T001", "T002"])
    _seed_wp_entry(tmp_path, "WP01")
    _seed_subtasks(tmp_path, "WP01", {"T001": Lane.DONE, "T002": Lane.PLANNED})
    assert _infer_subtasks_complete(tmp_path, "WP01") is False


def test_infer_subtasks_empty_roster_is_complete(tmp_path: Path) -> None:
    """A WP with no authored roster is 'nothing to block on' -> complete."""
    _seed_roster(tmp_path, "WP01", [])
    _seed_wp_entry(tmp_path, "WP01")
    assert _infer_subtasks_complete(tmp_path, "WP01") is True


def test_infer_subtasks_silent_snapshot_blocks_fail_closed(tmp_path: Path) -> None:
    """Fail-closed: an authored roster with NO event-sourced ``subtasks`` slot
    BLOCKS (every roster id unprovable). The retired ``tasks.md`` checkbox proxy
    is gone — an emptied ``tasks.md`` can no longer fall the gate open. A WP with
    no authored roster is 'nothing to block on' -> complete."""
    _seed_roster(tmp_path, "WP01", ["T001"])
    # No snapshot subtasks slot -> silent -> fail-closed BLOCK on the roster id.
    assert _infer_subtasks_complete(tmp_path, "WP01") is False
    # A resolvable WP with an explicitly empty authored roster has nothing to block.
    _seed_roster(tmp_path, "WP99", [])
    assert _infer_subtasks_complete(tmp_path, "WP99") is True


# ---------------------------------------------------------------------------
# store.append_annotations_atomic_verified (412, 415-416, 421)
# ---------------------------------------------------------------------------


def test_append_annotations_round_trip(tmp_path: Path) -> None:
    """A durably-appended annotation reads back through the annotation path."""
    ann = InnerStateChanged(
        event_id=_ulid("RT0"),
        wp_id="WP01",
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        delta=WPInnerStateDelta(note="hello"),
    )
    append_annotations_atomic_verified(tmp_path, [ann])
    stream = read_event_stream(tmp_path)
    assert [a.event_id for a in stream.annotations] == [ann.event_id]


def test_append_annotations_empty_is_noop(tmp_path: Path) -> None:
    """An empty batch returns without touching the store."""
    append_annotations_atomic_verified(tmp_path, [])
    assert read_event_stream(tmp_path).annotations == []


def test_append_annotations_wraps_append_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A raising serializer surfaces a StoreError with the append-failed prose."""
    ann = InnerStateChanged(
        event_id=_ulid("AF0"),
        wp_id="WP01",
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        delta=WPInnerStateDelta(note="x"),
    )

    def _boom(_feature_dir: Path, _rows: list[dict[str, Any]]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(_store, "_append_serialized_atomic", _boom)
    with pytest.raises(StoreError, match="annotation append failed: disk full"):
        append_annotations_atomic_verified(tmp_path, [ann])


def test_append_annotations_readback_miss_fails_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A silent-drop store (append no-op) is caught by the readback verification."""
    ann = InnerStateChanged(
        event_id=_ulid("RB0"),
        wp_id="WP01",
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        delta=WPInnerStateDelta(note="x"),
    )
    monkeypatch.setattr(_store, "_append_serialized_atomic", lambda *_a, **_k: None)
    with pytest.raises(StoreError, match="missing after append"):
        append_annotations_atomic_verified(tmp_path, [ann])


# ---------------------------------------------------------------------------
# store.is_non_lane_event annotation discriminator (511)
# ---------------------------------------------------------------------------


def test_is_non_lane_event_never_skips_annotation() -> None:
    """An annotation envelope is surfaced to reduce(), never skip-and-dropped."""
    assert is_non_lane_event({"kind": "annotation", "event_name": "retrospective.x"}) is False


# ---------------------------------------------------------------------------
# store.read_event_stream fail-loud paths (581-582, 587)
# ---------------------------------------------------------------------------


def test_read_event_stream_malformed_annotation_raises(tmp_path: Path) -> None:
    """A kind==annotation line missing required keys fails loud (never silent)."""
    events_path = tmp_path / _store.EVENTS_FILENAME
    events_path.write_text(json.dumps({"kind": "annotation", "wp_id": "WP01"}) + "\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Invalid event structure on line 1"):
        read_event_stream(tmp_path)


def test_read_event_stream_unknown_kind_raises(tmp_path: Path) -> None:
    """An unknown ``kind`` is never silently skipped."""
    events_path = tmp_path / _store.EVENTS_FILENAME
    events_path.write_text(json.dumps({"kind": "bogus", "wp_id": "WP01"}) + "\n", encoding="utf-8")
    with pytest.raises(StoreError, match="Unknown event kind 'bogus' on line 1"):
        read_event_stream(tmp_path)


# ---------------------------------------------------------------------------
# wp_state.annotate refusals (742, 744)
# ---------------------------------------------------------------------------


def test_annotate_refuses_malformed_wp_id() -> None:
    with pytest.raises(ValueError, match="WP-id pattern"):
        annotate(
            "not-a-wp",
            WPInnerStateDelta(note="x"),
            actor="test",
            at="2026-01-01T00:00:00+00:00",
            event_id=_ulid("AN0"),
        )


def test_annotate_refuses_empty_delta() -> None:
    with pytest.raises(ValueError, match="empty delta"):
        annotate(
            "WP01",
            WPInnerStateDelta(),
            actor="test",
            at="2026-01-01T00:00:00+00:00",
            event_id=_ulid("AN1"),
        )


# ---------------------------------------------------------------------------
# model serialization / validation edges (models 421, 496, 499)
# ---------------------------------------------------------------------------


def test_delta_to_dict_carries_replace_channel() -> None:
    """The wholesale-replace tracker_refs channel serializes distinctly."""
    delta = WPInnerStateDelta(tracker_refs_replace=["#2684", "#2816"])
    d = delta.to_dict()
    assert d["tracker_refs_replace"] == ["#2684", "#2816"]


def test_inner_state_changed_from_dict_rejects_bad_ulid() -> None:
    with pytest.raises(ValueError, match="not a valid ULID"):
        InnerStateChanged.from_dict(
            {
                "event_id": "not-a-ulid",
                "kind": "annotation",
                "wp_id": "WP01",
                "at": "2026-01-01T00:00:00+00:00",
                "actor": "test",
                "delta": {"note": "x"},
            }
        )


def test_inner_state_changed_from_dict_rejects_wrong_kind() -> None:
    with pytest.raises(ValueError, match="requires kind == 'annotation'"):
        InnerStateChanged.from_dict(
            {
                "event_id": _ulid("KND"),
                "kind": "transition",
                "wp_id": "WP01",
                "at": "2026-01-01T00:00:00+00:00",
                "actor": "test",
                "delta": {"note": "x"},
            }
        )
