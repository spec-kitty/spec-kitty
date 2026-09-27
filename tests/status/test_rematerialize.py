"""Tests for the shared status.json re-materialization authority (WP03 / NFR-002).

``reconcile_status_snapshot`` is the single authority lane allocation
(#5160 friction 1) and the mission→target squash seam (#4955) use to regenerate
the derived ``status.json`` from its event log after the log is reconciled,
rather than git-merging the derived snapshot.
"""

from __future__ import annotations

from pathlib import Path

import json

from specify_cli.status import (
    EVENTS_FILENAME,
    SNAPSHOT_FILENAME,
    materialize_snapshot,
    materialize_to_json,
    reconcile_status_snapshot,
)

from tests.status.conftest import seed_wp_to_planned


def _feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir


def test_reconcile_regenerates_snapshot_from_event_log(tmp_path: Path) -> None:
    """Given a reconciled event log and a stale/absent snapshot, the derived
    ``status.json`` is regenerated to exactly what the canonical ``materialize``
    reducer produces — the single authority (NFR-002)."""
    feature_dir = _feature_dir(tmp_path)
    seed_wp_to_planned(feature_dir, "WP01", slug="demo-mission")

    # Simulate the post-merge state: the event log is present (union-merged),
    # but the derived snapshot is stale / conflicting garbage on disk.
    snapshot_path = feature_dir / SNAPSHOT_FILENAME
    snapshot_path.write_text("<<<<<<< stale conflicting snapshot\n", encoding="utf-8")

    changed = reconcile_status_snapshot(feature_dir)
    assert changed is True

    # The regenerated snapshot is byte-identical to the canonical reducer's
    # output — reconcile delegates to `materialize`, not a forked reducer.
    reconciled = snapshot_path.read_text(encoding="utf-8")
    expected = materialize_to_json(materialize_snapshot(feature_dir))
    assert reconciled == expected
    assert "<<<<<<<" not in reconciled
    # The regenerated snapshot is valid JSON reflecting the reconciled log.
    json.loads(reconciled)
    assert "WP01" in reconciled


def test_reconcile_is_noop_without_event_log(tmp_path: Path) -> None:
    """With no event log there is no authoritative state to derive from: the
    reconcile is a no-op and fabricates no snapshot."""
    feature_dir = _feature_dir(tmp_path)
    assert not (feature_dir / EVENTS_FILENAME).exists()

    changed = reconcile_status_snapshot(feature_dir)

    assert changed is False
    assert not (feature_dir / SNAPSHOT_FILENAME).exists()


def test_reconcile_is_noop_on_empty_event_log(tmp_path: Path) -> None:
    """Squad fold: an existing-but-empty event log carries no authoritative state,
    so reconcile must no-op rather than write a degenerate empty snapshot over
    whatever status.json is on disk."""
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / EVENTS_FILENAME).write_text("   \n", encoding="utf-8")
    snapshot_path = feature_dir / SNAPSHOT_FILENAME
    snapshot_path.write_text("<<<<<<< divergent snapshot\n", encoding="utf-8")

    changed = reconcile_status_snapshot(feature_dir)

    assert changed is False
    # The on-disk snapshot is left untouched (NOT overwritten with an empty one).
    assert snapshot_path.read_text(encoding="utf-8") == "<<<<<<< divergent snapshot\n"
