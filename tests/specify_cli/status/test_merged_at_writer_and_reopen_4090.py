"""Track B (#4090): merge writes ``merged_at`` + ``is_mission_merged`` is reopen-aware.

WP04 couples two changes into one behavioural contract:

* **Writer restored** — :func:`specify_cli.merge.baseline.record_baseline_merge_commit`
  (the meta-write authority the merge executor already invokes) now stamps
  ``merged_at`` (+ ``merged_commit``) onto the mission ``meta.json``. Its
  production writer had been deleted in #2258, leaving the surface resolver's
  primary-wins guard and the runtime terminal short-circuit dormant.
* **Reopen-aware guard** — :func:`specify_cli.status.lifecycle.is_mission_merged`
  now reads the marker AS reopen-aware (merged iff ``merged_at`` present AND no
  later ``MissionReopened``), so restoring the writer does not make a re-opened
  mission read as merged forever across the three consumers.

The third test drives the real ``runtime_bridge`` :1600 terminal short-circuit
predicate so the coupling is proven end-to-end, not just on the writer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.next.runtime_bridge import _primary_mission_is_completed
from specify_cli.merge.baseline import record_baseline_merge_commit
from specify_cli.status import is_mission_merged
from specify_cli.status.lifecycle_events import emit_mission_reopened

pytestmark = [pytest.mark.fast]

_SLUG = "merged-writer-4090"
_MID = "01KTDVHZKGCHCW6HQ4V577PNES"
_MERGED_AT = "2026-08-30T00:00:00+00:00"
_REOPEN_AT = "2026-08-30T01:00:00+00:00"


def _write_meta(feature_dir: Path, *, merged_at: str | None = None) -> None:
    """Write a minimal modern-mission ``meta.json`` under *feature_dir*."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": _SLUG,
        "mission_id": _MID,
        "mid8": _MID[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-08-29T00:00:00+00:00",
    }
    if merged_at is not None:
        meta["merged_at"] = merged_at
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_writer_stamps_merged_at_and_marks_merged(tmp_path: Path) -> None:
    """The restored writer stamps ``merged_at`` (+ ``merged_commit``) and the
    mission then reads as merged (#4090 Part 1)."""
    feature_dir = tmp_path / _SLUG
    _write_meta(feature_dir)  # deliberately NO merged_at yet

    assert is_mission_merged(feature_dir) is False  # precondition: dormant marker

    meta_path = record_baseline_merge_commit(feature_dir, "abc123def456", mission_id=_MID)
    assert meta_path == feature_dir / "meta.json"  # folded into bookkeeping commit

    written = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert str(written.get("merged_at") or "").strip()  # a real timestamp landed
    # tmp_path is not a git repo -> merged_commit falls back to the baseline SHA.
    assert written.get("merged_commit") == "abc123def456"

    assert is_mission_merged(feature_dir) is True


def test_writer_is_idempotent_on_resume(tmp_path: Path) -> None:
    """A second call (``--resume``) never re-stamps an already-present marker."""
    feature_dir = tmp_path / _SLUG
    _write_meta(feature_dir, merged_at=_MERGED_AT)

    result = record_baseline_merge_commit(feature_dir, "abc123def456", mission_id=_MID)
    written = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    # baseline_merge_commit was still absent, so the meta IS rewritten (path
    # returned), but the pre-existing merged_at is preserved verbatim.
    assert result == feature_dir / "meta.json"
    assert written["merged_at"] == _MERGED_AT
    assert written["baseline_merge_commit"] == "abc123def456"


def test_reopened_mission_is_not_merged(tmp_path: Path) -> None:
    """A ``MissionReopened`` postdating the marker flips ``is_mission_merged``
    to ``False`` — even when ``merged_at`` survives on the surface (#4090 Part 2).

    Non-vacuous: the marker is left in place (the event-sourced guard, not a
    meta-clearer, is what makes the mission read as not-merged), and the same
    ``feature_dir`` reads as merged BEFORE the re-open.
    """
    feature_dir = tmp_path / _SLUG
    _write_meta(feature_dir, merged_at=_MERGED_AT)

    # Sanity: merged before any re-open (proves the assertion below is live).
    assert is_mission_merged(feature_dir) is True

    event = emit_mission_reopened(
        feature_dir,
        mission_id=_MID,
        mission_slug=_SLUG,
        reason="follow-up work discovered",
        reopened_by="tester",
        reopened_at=_REOPEN_AT,
    )
    assert event is not None  # the re-open fact was recorded

    # The marker deliberately still present, but the later re-open wins.
    still_marked = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert still_marked["merged_at"] == _MERGED_AT
    assert is_mission_merged(feature_dir) is False


def test_runtime_bridge_terminal_short_circuit_tracks_marker(tmp_path: Path) -> None:
    """The runtime_bridge :1600 short-circuit predicate fires for a merged
    mission and stands down for a re-opened one (#4090 coupling proof).

    ``_primary_mission_is_completed`` is the exact guard the bootstrap terminal
    short-circuit at ``runtime_bridge.py`` :1600 gates on.
    """
    feature_dir = tmp_path / _SLUG
    _write_meta(feature_dir, merged_at=_MERGED_AT)

    # Merged -> short-circuit fires (returns a terminal "already completed").
    assert _primary_mission_is_completed(feature_dir) is True

    emit_mission_reopened(
        feature_dir,
        mission_id=_MID,
        mission_slug=_SLUG,
        reason="re-open after merge",
        reopened_by="tester",
        reopened_at=_REOPEN_AT,
    )

    # Re-opened -> short-circuit stands down, the run advances normally.
    assert _primary_mission_is_completed(feature_dir) is False
