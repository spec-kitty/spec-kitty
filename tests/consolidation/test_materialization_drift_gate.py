"""#5863 — consolidate warns when a Mission's status.json has drifted from its
event log (the event log is the sole authority for lane state).

The contract: a snapshot that is PRESENT and whose CONTENT diverges from the
reduced log emits a warning that names ``spec-kitty agent status materialize``;
a snapshot that matches the log (or is simply absent/not-yet-materialized) is
silent. Emitted as a warning, not a refusal, so it never false-blocks a
consolidation whose status.json was seeded or left loosely (see the gate's
docstring and the PR notes).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.executor import _warn_on_materialization_drift
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


def test_matching_snapshot_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    feature_dir = _seed(tmp_path)
    (feature_dir / SNAPSHOT_FILENAME).write_text(materialize_to_json(materialize_snapshot(feature_dir)), encoding="utf-8")
    _warn_on_materialization_drift(feature_dir, _SLUG)  # no raise
    assert "drifted" not in capsys.readouterr().out


def test_absent_snapshot_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    feature_dir = _seed(tmp_path)  # no status.json written
    _warn_on_materialization_drift(feature_dir, _SLUG)  # no raise — not yet materialized
    assert "drifted" not in capsys.readouterr().out


def test_drifted_snapshot_warns(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    feature_dir = _seed(tmp_path)
    snapshot = json.loads(materialize_to_json(materialize_snapshot(feature_dir)))
    # A writer committed a 'done' snapshot the event log (in_progress) does not
    # materialize to: a present, content-drifted status.json.
    snapshot["work_packages"]["WP01"]["lane"] = "done"
    (feature_dir / SNAPSHOT_FILENAME).write_text(json.dumps(snapshot), encoding="utf-8")
    _warn_on_materialization_drift(feature_dir, _SLUG)  # warns, never raises
    out = capsys.readouterr().out
    assert "drifted from its event log" in out
    assert "spec-kitty agent status materialize" in out
