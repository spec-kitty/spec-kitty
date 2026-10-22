"""Tests for the test-only status seeding helper (``tests/_support/status_seed``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status import store
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event, seed_status_events

pytestmark = pytest.mark.fast


def _event(event_id: str, wp_id: str, from_lane: Lane, to_lane: Lane) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug="034-feature-name",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-02-08T12:00:00Z",
        actor="claude-opus",
        force=False,
        execution_mode="worktree",
    )


@pytest.fixture
def events() -> list[StatusEvent]:
    return [
        _event("01HXYZ0123456789ABCDEFGH01", "WP01", Lane.PLANNED, Lane.CLAIMED),
        _event("01HXYZ0123456789ABCDEFGH02", "WP01", Lane.CLAIMED, Lane.IN_PROGRESS),
        _event("01HXYZ0123456789ABCDEFGH03", "WP02", Lane.PLANNED, Lane.CLAIMED),
    ]


def _log_bytes(feature_dir: Path) -> bytes:
    """Log content with platform newline translation undone (text mode writes CRLF on Windows)."""
    log: Path = feature_dir / store.EVENTS_FILENAME
    return log.read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.parametrize("sequential", [False, True], ids=["one-batch", "sequential-singles"])
def test_bytes_equal_canonical_serialization(tmp_path: Path, events: list[StatusEvent], sequential: bool) -> None:
    if sequential:
        for event in events:
            seed_status_event(tmp_path, event)
    else:
        seed_status_events(tmp_path, events)

    expected = "".join(store.serialize_event_line(e.to_dict()) + "\n" for e in events)
    assert _log_bytes(tmp_path) == expected.encode("utf-8")


def test_empty_batch_creates_no_file(tmp_path: Path) -> None:
    seed_status_events(tmp_path, [])

    assert not (tmp_path / store.EVENTS_FILENAME).exists()
