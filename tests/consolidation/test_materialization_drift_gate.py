"""#5863 — consolidate refuses to land a Mission whose status.json drifts from
its event log (the event log is the sole authority for lane state).

Red-first: before the gate, ``_refuse_on_materialization_drift`` did not exist
and consolidate would land on a stale, dishonest snapshot. The contract: a
genuine drift refuses with exit 1 and names ``spec-kitty agent status
materialize``; a snapshot that matches the log (or is absent/fresh) does not
refuse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.consolidation.executor import _refuse_on_materialization_drift
from specify_cli.status.reducer import SNAPSHOT_FILENAME, materialize_snapshot, materialize_to_json
from specify_cli.status.store import EVENTS_FILENAME

pytestmark = pytest.mark.fast

_SLUG = "drift-5863"


def _ev(seq: int, frm: str, to: str) -> dict[str, object]:
    return {
        "actor": "claude",
        "at": f"2026-10-09T00:00:{seq:02d}+00:00",
        "event_id": f"01E5863{seq:019d}",
        "execution_mode": "worktree",
        "feature_slug": _SLUG,
        "force": False,
        "from_lane": frm,
        "mission_slug": _SLUG,
        "reason": None,
        "review_ref": None,
        "to_lane": to,
        "wp_id": "WP01",
    }


def _seed(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    rows = [_ev(0, "genesis", "planned"), _ev(1, "planned", "claimed"), _ev(2, "claimed", "in_progress")]
    (feature_dir / EVENTS_FILENAME).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    return feature_dir


def test_matching_snapshot_does_not_refuse(tmp_path: Path) -> None:
    feature_dir = _seed(tmp_path)
    (feature_dir / SNAPSHOT_FILENAME).write_text(materialize_to_json(materialize_snapshot(feature_dir)), encoding="utf-8")
    _refuse_on_materialization_drift(feature_dir, _SLUG)  # no raise


def test_absent_snapshot_does_not_refuse(tmp_path: Path) -> None:
    feature_dir = _seed(tmp_path)  # no status.json written
    _refuse_on_materialization_drift(feature_dir, _SLUG)  # no raise — not yet materialized


def test_drifted_snapshot_refuses(tmp_path: Path) -> None:
    feature_dir = _seed(tmp_path)
    snapshot = json.loads(materialize_to_json(materialize_snapshot(feature_dir)))
    # A writer appended the in_progress event without re-materializing: the
    # committed snapshot still says 'claimed'.
    snapshot["work_packages"]["WP01"]["lane"] = "claimed"
    (feature_dir / SNAPSHOT_FILENAME).write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(typer.Exit) as exc:
        _refuse_on_materialization_drift(feature_dir, _SLUG)
    assert exc.value.exit_code == 1
