"""Scope: #2709 / FR-005 / US2-S4 -- coord->target status projection must UNION.

Formerly a red-first ``@pytest.mark.regression`` reproduction (WP03 witnessing
RED within the fix WP); relocated here and un-marked (landing fold: make
``@pytest.mark.regression`` mean exactly one thing) once the fix landed and
this test started passing. #2709 is fixed — this is now a permanent guard,
not a red-first pin.

The coord->target status bookkeeping projection (``merge/bookkeeping_projection.py::
_project_status_bookkeeping_to_target``) used to blind-``write_bytes`` the
coord-worktree ``status.events.jsonl`` **and** ``status.json`` over the target
checkout. A target-newer event the coord worktree lacks was therefore dropped, and
the derived ``status.json`` went stale.

This is a SEPARATE fix surface from the squash-merge repro
(``test_issue_2709_squash_provenance.py``): the squash test exercises the
non-worktree fast path, so it never reaches the projection write. FR-005 requires
the projection to union ``source ∪ original`` via ``merge_event_payloads`` and
rematerialize ``status.json = reduce(union)``.

RED-for-the-right-reason: the FIRST failing assertion is the target-newer event
survival (union contract), asserted BEFORE the snapshot equality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (mirror production)
from specify_cli.consolidation.bookkeeping_projection import (
    _project_status_bookkeeping_to_target,
)
from specify_cli.status import (
    materialize_to_json,
    merge_event_log_texts,
    read_events_from_text,
    reduce,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.fast]

_SLUG = "test-coord-projection-2709"
_MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"


def _seed_event(feature_dir: Path, *, event_id: str, wp_id: str, at: str) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=_SLUG,
            mission_id=_MISSION_ID,
            wp_id=wp_id,
            from_lane=Lane.APPROVED,
            to_lane=Lane.DONE,
            at=at,
            actor="merge",
            force=False,
            execution_mode="worktree",
        ),
    )


def _bootstrap(tmp_path: Path) -> tuple[Path, Path]:
    """Return (primary_dir, coord_specs) for a coord-topology projection."""
    mid8 = _MISSION_ID[:8]
    coord_branch = f"kitty/mission-{_SLUG}-{mid8}"

    primary_dir = tmp_path / "kitty-specs" / _SLUG
    primary_dir.mkdir(parents=True)
    (primary_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "coordination_branch": coord_branch,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )

    coord_dir_name = f"{_SLUG}-{mid8}"
    coord_specs = (
        tmp_path / ".worktrees" / f"{coord_dir_name}-coord" / "kitty-specs" / coord_dir_name
    )
    coord_specs.mkdir(parents=True)
    return primary_dir, coord_specs


def test_projection_unions_target_newer_event_and_rematerializes_snapshot(
    tmp_path: Path,
) -> None:
    """#2709 / FR-005 / US2-S4: the projection must union the event log and
    rematerialize ``status.json`` from ``reduce(union)`` -- not blind-copy the
    coord worktree over a target that carries a newer event."""
    primary_dir, coord_specs = _bootstrap(tmp_path)

    # Coord worktree: a done event for WP01.
    _seed_event(
        coord_specs,
        event_id="01TESTCOORDPROJWP01DONE0000",
        wp_id="WP01",
        at="2026-06-06T12:00:00+00:00",
    )
    # Target (primary) checkout: a NEWER done event for WP02 the coord lacks.
    _seed_event(
        primary_dir,
        event_id="01TESTTARGETPROJWP02DONE000",
        wp_id="WP02",
        at="2026-06-07T12:00:00+00:00",
    )

    coord_events_text = (coord_specs / "status.events.jsonl").read_text(encoding="utf-8")
    target_events_text = (primary_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert "WP02" in target_events_text, (
        "fixture precondition: the target-newer WP02 event must be on the primary "
        "checkout before the projection"
    )

    target_events_path, target_status_path = _project_status_bookkeeping_to_target(
        main_repo=tmp_path,
        mission_slug=_SLUG,
        status_feature_dir=coord_specs,
    )

    merged_events = target_events_path.read_text(encoding="utf-8")
    # --- Contract assertion #1 (union): the target-newer event survives. ---
    assert "WP02" in merged_events, (
        "#2709 FR-005 regression: the coord->target projection blind-overwrote the "
        "target event log with the coord copy, dropping the target-newer WP02 event."
    )
    assert "WP01" in merged_events, "coord-side WP01 event must also survive the union"

    # --- Contract assertion #2: status.json == reduce(union events). ---
    expected_events_text = merge_event_log_texts(coord_events_text, target_events_text)
    expected_snapshot = materialize_to_json(
        reduce(read_events_from_text(primary_dir, expected_events_text))
    )
    assert target_status_path.read_text(encoding="utf-8") == expected_snapshot, (
        "#2709 FR-005 regression: status.json was not rematerialized from the "
        "unioned event log (reduce(union)); it contradicts the merged log."
    )
