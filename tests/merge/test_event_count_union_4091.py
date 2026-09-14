"""Scope: #4091 / FR-007 -- coord->target ``status.json.event_count`` consistency.

CHARACTERIZATION / REGRESSION GUARD (not a red-first pin). #4091 asked whether,
after a coord->target status-bookkeeping projection, ``status.json.event_count``
could disagree with the unioned ``status.events.jsonl``. WP05 proved it CANNOT on
HEAD: ``_project_status_bookkeeping_to_target``
(``merge/bookkeeping_projection.py``) already

  1. unions ``source (coord) ∪ original (target)`` via ``merge_event_log_texts``
     (id-keyed dedupe/sort -- ``_union_event_logs``), and
  2. rematerializes ``status.json = reduce(union events)``
     (``_rematerialize_status_snapshot`` -> ``reduce``).

and ``ReducedStatus.event_count`` is **by definition**
``len(unique WPStatusChanged events)`` (``spec_kitty_events/status.py`` --
``reduce_status_events`` filters to ``WP_STATUS_CHANGED`` at step 1, dedups, and
sets ``event_count = len(unique_events)``). So the count is a **unique-transition**
count, never a raw-line count: off-axis ``InnerStateChanged`` annotations and any
duplicate (same-id) transitions do not inflate it. The projected snapshot is
consistent with the unioned log by construction.

This test therefore asserts the current-correct behavior. The load-bearing
distinction (the #4091 trap) is: assert ``event_count`` against the
**independently computed unique-transition count**, NEVER against the raw jsonl
line count -- the fixture is deliberately built so the two differ (a surviving
annotation line + a cross-stream duplicate transition), and the test pins
``event_count < raw_line_count`` to prove the measures are distinct.

The union branch runs ONLY under a coord husk
(``bookkeeping_projection.py`` -> ``is_under_worktrees_segment``); a
``single_branch`` mission never reaches it, so the fixture MUST be coord-shaped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (mirror production)
from specify_cli.merge.bookkeeping_projection import (
    _project_status_bookkeeping_to_target,
)
from specify_cli.status import (
    merge_event_log_texts,
    read_events_from_text,
    reduce,
)
from specify_cli.status.models import (
    ULID_PATTERN,
    InnerStateChanged,
    Lane,
    StatusEvent,
    WPInnerStateDelta,
)
from specify_cli.status.store import append_annotations_atomic_verified, append_event

pytestmark = [pytest.mark.fast]

_SLUG = "test-coord-eventcount-4091"
_MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"

# Deterministic 26-char ULIDs from the strict annotation alphabet
# (``ULID_PATTERN`` == ``^[0-9A-HJKMNP-TV-Z]{26}$`` -- no I/L/O/U). The coord WP02
# id is reused on the target stream on purpose: the union must dedupe it.
_COORD_WP01_DONE = "01TESTCWP01DNE000000000001"
_COORD_WP02_DONE = "01TESTCWP02DNE000000000002"
_TARGET_WP03_DONE = "01TESTTWP03DNE000000000003"
_COORD_WP01_ANNOTATION = "01TESTAWP01NTE000000000004"


def _seed_done(feature_dir: Path, *, event_id: str, wp_id: str, at: str) -> None:
    """Append a WPStatusChanged (transition) DONE event."""
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


def _seed_annotation(feature_dir: Path, *, event_id: str, wp_id: str, at: str) -> None:
    """Append an off-axis ``InnerStateChanged`` annotation (NOT a transition).

    An annotation adds a raw jsonl line but is filtered out before the reducer's
    transition count, so it must never contribute to ``event_count``.
    """
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=event_id,
                wp_id=wp_id,
                at=at,
                actor="merge",
                delta=WPInnerStateDelta(note="runtime annotation"),
            )
        ],
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
    coord_specs = tmp_path / ".worktrees" / f"{coord_dir_name}-coord" / "kitty-specs" / coord_dir_name
    coord_specs.mkdir(parents=True)
    return primary_dir, coord_specs


def test_fixture_ids_are_valid_annotation_ulids() -> None:
    """Guard the hand-crafted ids against the strict annotation ULID alphabet."""
    for ulid in (
        _COORD_WP01_DONE,
        _COORD_WP02_DONE,
        _TARGET_WP03_DONE,
        _COORD_WP01_ANNOTATION,
    ):
        assert len(ulid) == 26 and ULID_PATTERN.match(ulid), ulid


def test_projected_event_count_equals_unique_transition_count(tmp_path: Path) -> None:
    """#4091 / FR-007: after the coord->target projection, ``status.json``'s
    ``event_count`` equals the number of **unique transition** events in the
    unioned log -- NOT the raw jsonl line count (the annotation and the
    cross-stream duplicate make the two measures differ)."""
    primary_dir, coord_specs = _bootstrap(tmp_path)

    # Coord worktree: two DONE transitions + one off-axis annotation.
    _seed_done(
        coord_specs,
        event_id=_COORD_WP01_DONE,
        wp_id="WP01",
        at="2026-06-06T12:00:00+00:00",
    )
    _seed_done(
        coord_specs,
        event_id=_COORD_WP02_DONE,
        wp_id="WP02",
        at="2026-06-06T12:05:00+00:00",
    )
    _seed_annotation(
        coord_specs,
        event_id=_COORD_WP01_ANNOTATION,
        wp_id="WP01",
        at="2026-06-06T12:06:00+00:00",
    )

    # Target (primary) checkout: the SAME WP02 transition (a cross-stream
    # duplicate the union must collapse) + a target-newer WP03 transition.
    _seed_done(
        primary_dir,
        event_id=_COORD_WP02_DONE,
        wp_id="WP02",
        at="2026-06-06T12:05:00+00:00",
    )
    _seed_done(
        primary_dir,
        event_id=_TARGET_WP03_DONE,
        wp_id="WP03",
        at="2026-06-07T12:00:00+00:00",
    )

    coord_events_text = (coord_specs / "status.events.jsonl").read_text(encoding="utf-8")
    target_events_text = (primary_dir / "status.events.jsonl").read_text(encoding="utf-8")

    target_events_path, target_status_path = _project_status_bookkeeping_to_target(
        main_repo=tmp_path,
        mission_slug=_SLUG,
        status_feature_dir=coord_specs,
    )

    union_text = target_events_path.read_text(encoding="utf-8")

    # Independent oracle: the unique-transition count of the unioned log, computed
    # the same way production does (merge -> read transitions -> reduce).
    expected_event_count = reduce(
        read_events_from_text(
            primary_dir,
            merge_event_log_texts(coord_events_text, target_events_text),
        )
    ).event_count

    snapshot = json.loads(target_status_path.read_text(encoding="utf-8"))
    raw_line_count = len([line for line in union_text.splitlines() if line.strip()])

    # Fixture preconditions: three unique WPs survive; the annotation survives the
    # union (id-keyed) but is off-axis.
    assert expected_event_count == 3, "fixture precondition: WP01/WP02/WP03 are the three unique transitions (the cross-stream WP02 duplicate must collapse)"
    for wp in ("WP01", "WP02", "WP03"):
        assert wp in union_text, f"{wp} transition must survive the union"
    assert '"annotation"' in union_text, "fixture precondition: the off-axis annotation must survive the id-keyed union"

    # --- Load-bearing assertion (the #4091 trap): count is the unique-TRANSITION
    #     count, asserted against the independent oracle -- NOT the raw line count.
    assert snapshot["event_count"] == expected_event_count, (
        "#4091: projected status.json.event_count must equal the unique-transition count of the unioned event log (reduce(union))."
    )

    # --- Distinctness proof: the raw line count is strictly larger, so the test
    #     genuinely distinguishes the two measures (asserting against raw lines
    #     would be the false expectation #4091 warned against).
    assert snapshot["event_count"] < raw_line_count, (
        "measures must be distinct: event_count counts unique transitions while "
        f"the union carries {raw_line_count} raw lines (annotation + transitions); "
        "if these were equal the test would not exercise the #4091 distinction."
    )
