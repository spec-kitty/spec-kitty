"""Optional ``Event.lamport_clock`` conformance for the lifecycle-envelope migration.

Issue #6414 (parent epic #6411). ``spec-kitty-events`` 11.x made
``Event.lamport_clock`` optional: an envelope without one is *unclocked* and sorts
before every clocked envelope (``spec_kitty_events.ordering.canonical_order_key``),
and ``0`` is a real clocked position, not "no clock recorded".

The upgrade migration rewrites legacy 9-key lifecycle rows that never recorded a
causal clock. It must therefore emit the contract's own unclocked representation
(``None``) instead of a fixed ``0`` sentinel, which falsely claims position zero.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events import Event
from spec_kitty_events.ordering import canonical_order_key

from specify_cli.status.lifecycle_events import mission_event_log_path, read_lifecycle_events
from specify_cli.status.migrate_lifecycle_envelope import migrate_lifecycle_envelope

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "optional-lamport-clock-migration"


def _git_init(path: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    return feature_dir


def _legacy_row(
    *,
    project_uuid: str,
    event_type: str = "WPCreated",
    aggregate_id: str = "WP01",
    payload: dict[str, Any] | None = None,
    timestamp: str = "2026-02-08T12:00:00+00:00",
    event_id: str | None = None,
) -> dict[str, Any]:
    """One legacy 9-key envelope row, matching ``lifecycle_events._build_envelope``."""
    return {
        "event_id": event_id or f"01{uuid.uuid4().hex[:24].upper()}",
        "event_type": event_type,
        "aggregate_id": aggregate_id,
        "aggregate_type": "WorkPackage",
        "schema_version": "5.0.0",
        "timestamp": timestamp,
        "payload": payload if payload is not None else {"wp_id": "WP01"},
        "project_uuid": project_uuid,
        "project_slug": "demo",
    }


def _write_rows(log_path: Path, rows: list[dict[str, Any]]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _migrated_row(feature_dir: Path, project_uuid: str) -> dict[str, Any]:
    log_path = mission_event_log_path(feature_dir)
    _write_rows(log_path, [_legacy_row(project_uuid=project_uuid)])
    manifest = migrate_lifecycle_envelope(log_path)
    assert manifest.migrated_count == 1
    return dict(read_lifecycle_events(log_path)[0])


def test_migrated_legacy_row_is_unclocked(feature_dir: Path) -> None:
    """A row that never recorded a clock must be emitted unclocked, not clocked at 0."""
    migrated = _migrated_row(feature_dir, str(uuid.uuid4()))

    assert migrated["lamport_clock"] is None, (
        "a legacy row recorded no causal clock; emitting 0 claims a clocked position at zero, which sorts after every unclocked row and groups as concurrent"
    )
    # The strict 14-key profile requires the key to be PRESENT, exactly as null.
    assert "lamport_clock" in migrated
    # And the row must still be a valid envelope under the pinned contract.
    Event.model_validate(migrated)


def test_migrated_row_sorts_before_a_newer_unclocked_row(feature_dir: Path) -> None:
    """The fix keeps the migrated row's real (earlier) position in the log order."""
    migrated = _migrated_row(feature_dir, str(uuid.uuid4()))
    newer = dict(
        migrated,
        event_id=f"01{uuid.uuid4().hex[:24].upper()}",
        timestamp="2026-09-01T00:00:00+00:00",
        lamport_clock=None,
    )

    older_event = Event.model_validate(migrated)
    newer_event = Event.model_validate(newer)

    ordered = sorted([newer_event, older_event], key=canonical_order_key)
    assert [event.event_id for event in ordered] == [migrated["event_id"], newer["event_id"]], (
        "the earlier-stamped migrated row must sort first; a synthetic lamport_clock=0 would place it after every unclocked row"
    )


def test_rerun_over_migrated_output_is_a_byte_identical_no_op(feature_dir: Path) -> None:
    """Idempotency (MIG2) survives the sentinel change: presence, not value, is the marker."""
    project_uuid = str(uuid.uuid4())
    log_path = mission_event_log_path(feature_dir)
    _write_rows(log_path, [_legacy_row(project_uuid=project_uuid)])

    first = migrate_lifecycle_envelope(log_path)
    assert first.migrated_count == 1
    after_first = log_path.read_text(encoding="utf-8")

    second = migrate_lifecycle_envelope(log_path)
    assert second.migrated_count == 0
    assert second.unchanged_count == 1
    assert log_path.read_text(encoding="utf-8") == after_first


def test_already_migrated_zero_sentinel_is_left_untouched(feature_dir: Path) -> None:
    """Rows an older migration already stamped with 0 are not rewritten on a re-run."""
    project_uuid = str(uuid.uuid4())
    already_migrated = {
        "event_id": f"01{uuid.uuid4().hex[:24].upper()}",
        "event_type": "WPCreated",
        "aggregate_id": "WP01",
        "payload": {"wp_id": "WP01"},
        "timestamp": "2026-02-08T12:00:00+00:00",
        "build_id": "b1",
        "node_id": "n1",
        "lamport_clock": 0,
        "causation_id": None,
        "project_uuid": project_uuid,
        "project_slug": "demo",
        "correlation_id": f"01{uuid.uuid4().hex[:24].upper()}",
        "schema_version": "3.0.0",
        "data_tier": 0,
    }
    log_path = mission_event_log_path(feature_dir)
    _write_rows(log_path, [already_migrated])
    original = log_path.read_text(encoding="utf-8")

    manifest = migrate_lifecycle_envelope(log_path)

    assert manifest.migrated_count == 0
    assert manifest.unchanged_count == 1
    assert log_path.read_text(encoding="utf-8") == original
