"""Tests for WP01 — post-mission lifecycle events + re-open-aware classification.

Covers the FR-001/FR-002 contract:

* ``MissionReopened`` and ``FollowUpRecorded`` are registered, emittable, and
  **reducer-skipped** (WP ``status.json`` is unaffected by them).
* ``FollowUpRecorded`` is idempotent on ``(mission_id, commit_sha | pr_number)``;
  ``MissionReopened`` is append-each.
* On a merged mission (all WPs terminal), a ``MissionReopened`` event postdating
  the last merge marker makes ``derive_mission_lifecycle`` report a ``reopened``
  (actionable) surface_state — the FR-002 crux.
* The two new types are classified as post-mission lifecycle facts by the
  CLI's own ``lifecycle._POST_MISSION_EVENT_TYPES`` set (the local-only
  authority) and round-trip through ``read_events`` as reducer-skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import UTC, datetime
from specify_cli.status import lifecycle_events as le
from specify_cli.status.lifecycle import derive_mission_lifecycle
from specify_cli.status.lifecycle_events import (
    FOLLOW_UP_RECORDED,
    LIFECYCLE_EVENT_TYPES,
    MISSION_REOPENED,
    emit_follow_up_recorded,
    emit_mission_reopened,
    mission_event_log_path,
    read_lifecycle_events,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import reduce
from specify_cli.status.store import read_events
from specify_cli.status.views import format_post_mission_events
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.fast

MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _write_meta(
    feature_dir: Path,
    *,
    created_at: str = "2026-04-01T10:00:00+00:00",
    merged_at: str | None = None,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "created_at": created_at,
        "friendly_name": feature_dir.name,
        "mission_id": MISSION_ID,
        "mission_number": int(feature_dir.name.split("-", 1)[0]),
        "mission_slug": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    if merged_at is not None:
        meta["merged_at"] = merged_at
        meta["merged_by"] = "merger"
        meta["merged_into"] = "main"
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_status_event(
    feature_dir: Path,
    *,
    wp_id: str,
    to_lane: str,
    at: str,
    event_id: str,
    from_lane: str = "planned",
) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=event_id,
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane(from_lane),
            to_lane=Lane(to_lane),
            at=at,
            actor="test-agent",
            force=False,
            execution_mode="worktree",
            mission_id=MISSION_ID,
        ),
    )


def _merged_mission(tmp_path: Path, *, merged_at: str) -> Path:
    """A mission whose single WP reached a terminal (done) lane, then merged."""
    feature_dir = tmp_path / "kitty-specs" / "070-merged"
    _write_meta(feature_dir, merged_at=merged_at)
    _append_status_event(
        feature_dir,
        wp_id="WP01",
        to_lane="done",
        at="2026-04-02T10:00:00+00:00",
        event_id="01TESTDONE000000000000001",
        from_lane="approved",
    )
    return feature_dir


# ---------------------------------------------------------------------------
# T001 (1): registration + reducer-skip round-trip
# ---------------------------------------------------------------------------


def test_new_event_types_are_registered() -> None:
    assert MISSION_REOPENED in LIFECYCLE_EVENT_TYPES
    assert FOLLOW_UP_RECORDED in LIFECYCLE_EVENT_TYPES
    # ``__all__`` carries the symbol names so ``append_lifecycle_event`` (which
    # gates on the LIFECYCLE_EVENT_TYPES frozenset) does not silently drop them
    # and the constants/helpers are part of the public surface.
    assert "MISSION_REOPENED" in le.__all__
    assert "FOLLOW_UP_RECORDED" in le.__all__
    assert "emit_mission_reopened" in le.__all__
    assert "emit_follow_up_recorded" in le.__all__


def test_emitting_events_is_reducer_skipped(tmp_path: Path) -> None:
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    snapshot_before = reduce(read_events(feature_dir))

    reopened = emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="bug found after merge",
        reopened_by="claude",
    )
    follow_up = emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="a" * 40,
        recorded_by="claude",
    )

    assert reopened is not None
    assert follow_up is not None
    assert reopened["event_type"] == MISSION_REOPENED
    assert follow_up["event_type"] == FOLLOW_UP_RECORDED
    assert reopened["aggregate_id"] == MISSION_ID
    assert reopened["aggregate_type"] == "Mission"

    # Reducer-skip: WP snapshot is byte-identical before/after lifecycle events.
    snapshot_after = reduce(read_events(feature_dir))
    assert snapshot_after.work_packages == snapshot_before.work_packages
    assert snapshot_after.summary == snapshot_before.summary

    # The lifecycle events do persist in the shared log and round-trip via the
    # lifecycle reader (not the WP reducer).
    persisted = read_lifecycle_events(mission_event_log_path(feature_dir))
    persisted_types = {e["event_type"] for e in persisted}
    assert MISSION_REOPENED in persisted_types
    assert FOLLOW_UP_RECORDED in persisted_types


# ---------------------------------------------------------------------------
# T001 (2): FollowUpRecorded dedup; MissionReopened append-each
# ---------------------------------------------------------------------------


def test_follow_up_recorded_is_idempotent_on_ref(tmp_path: Path) -> None:
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    first = emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="b" * 40,
        recorded_by="claude",
    )
    second = emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="b" * 40,
        recorded_by="claude",
    )

    assert first is not None
    assert second is None  # identical ref → deduped no-op

    log = read_lifecycle_events(mission_event_log_path(feature_dir))
    follow_ups = [e for e in log if e["event_type"] == FOLLOW_UP_RECORDED]
    assert len(follow_ups) == 1


def test_mission_reopened_is_append_each(tmp_path: Path) -> None:
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    first = emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="first reopen",
        reopened_by="claude",
    )
    second = emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="second reopen",
        reopened_by="claude",
    )

    assert first is not None
    assert second is not None  # append-each, never deduped

    log = read_lifecycle_events(mission_event_log_path(feature_dir))
    reopens = [e for e in log if e["event_type"] == MISSION_REOPENED]
    assert len(reopens) == 2


def test_follow_up_pr_dedup_distinct_from_commit(tmp_path: Path) -> None:
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    pr_first = emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="pr",
        pr_number=42,
        recorded_by="claude",
    )
    pr_second = emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="pr",
        pr_number=42,
        recorded_by="claude",
    )

    assert pr_first is not None
    assert pr_second is None

    log = read_lifecycle_events(mission_event_log_path(feature_dir))
    prs = [e for e in log if e["event_type"] == FOLLOW_UP_RECORDED]
    assert len(prs) == 1


# ---------------------------------------------------------------------------
# T001 (3): re-open-aware classification (the FR-002 crux)
# ---------------------------------------------------------------------------


def test_merged_mission_is_archived_without_reopen(tmp_path: Path) -> None:
    """Baseline: a terminal, aged mission with no reopen event is archived."""
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert result.state == "archived"
    assert result.surface_state is None
    assert result.post_mission_events == ()
    assert result.last_follow_up_at is None


def test_reopen_event_makes_merged_mission_actionable(tmp_path: Path) -> None:
    """A MissionReopened postdating the merge marker → reopened/actionable."""
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    # Re-open: per D-A2 the merge marker is cleared and the event recorded.
    # Simulate the IC-02 clear so the classifier sees no live merge marker.
    _write_meta(feature_dir, merged_at=None)
    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="critical regression",
        reopened_by="claude",
    )

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert result.state == "reopened"
    assert result.surface_state == "reopened"
    assert len(result.post_mission_events) == 1
    assert result.post_mission_events[0]["event_type"] == MISSION_REOPENED


def test_remerge_after_reopen_drops_reopened_state(tmp_path: Path) -> None:
    """A merge marker postdating the latest reopen → no longer reopened."""
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    _write_meta(feature_dir, merged_at=None)
    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="reopen",
        reopened_by="claude",
        reopened_at="2026-04-10T10:00:00+00:00",
    )
    # Re-merge re-stamps merged_at to a time AFTER the reopen event.
    _write_meta(feature_dir, merged_at="2026-04-15T10:00:00+00:00")

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert result.state == "archived"
    assert result.surface_state is None
    # The reopen fact is still surfaced in post_mission_events for history.
    assert len(result.post_mission_events) == 1


def test_post_mission_events_sorted_and_last_follow_up_recorded(tmp_path: Path) -> None:
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    # The merge marker is retained so the mission remains *completed* — the
    # precondition for emitting post-mission events (#1926). Both events are
    # therefore accepted; this test exercises the sort/last_follow_up surface,
    # not the reopen-clears-merge sequencing.
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="reopen",
        reopened_by="claude",
        reopened_at="2026-04-05T10:00:00+00:00",
    )
    emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="c" * 40,
        recorded_by="claude",
        recorded_at="2026-04-06T10:00:00+00:00",
    )

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert [e["event_type"] for e in result.post_mission_events] == [
        MISSION_REOPENED,
        FOLLOW_UP_RECORDED,
    ]
    assert result.last_follow_up_at is not None
    assert result.last_follow_up_at.isoformat() == "2026-04-06T10:00:00+00:00"


# ---------------------------------------------------------------------------
# T004: SaaS strict-path boundary + reducer-skip round-trip
# ---------------------------------------------------------------------------


def test_new_types_stay_local_only_via_cli_contract() -> None:
    """The two new types stay local-only via the CLI's OWN exclusion contract.

    Re-pinned (events 6.1.0 canonicalization): the original assertion proxied
    "local-only" through *absence from the external model map*
    (``spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL``). That
    proxy was always fragile and is now false — events 6.1.0 promoted
    ``MissionReopened`` / ``FollowUpRecorded`` (and ~10 other CLI lifecycle
    types) into the canonical map, so map-absence no longer holds and never
    was the seam that keeps these events out of the WP state machine.

    The robust invariant lives at the CLI seam: ``lifecycle._POST_MISSION_EVENT_TYPES``
    is the authority that classifies these as post-mission lifecycle facts —
    they are collected for the *local* re-open/archive classification
    (``derive_mission_lifecycle``) and are reducer-skipped so they never mutate
    WP ``status.json``. Asserting on the CLI's own frozenset (and on the
    reducer-skip + classification behavior exercised by the sibling tests)
    keeps this test's intent — these stay local to the mission's lifecycle
    surface — while being robust to the events package adding canonical models.
    """
    from specify_cli.status.lifecycle import _POST_MISSION_EVENT_TYPES

    # The CLI's own post-mission classification set is the local-only authority.
    assert MISSION_REOPENED in _POST_MISSION_EVENT_TYPES
    assert FOLLOW_UP_RECORDED in _POST_MISSION_EVENT_TYPES
    # And it is exactly these two types (a third type silently joining the set
    # would change the local classification surface and must be deliberate).
    assert sorted(_POST_MISSION_EVENT_TYPES) == sorted(
        {MISSION_REOPENED, FOLLOW_UP_RECORDED}
    )


def test_events_round_trip_as_reducer_skipped(tmp_path: Path) -> None:
    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")
    wp_events_before = len(read_events(feature_dir))

    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="reopen",
        reopened_by="claude",
    )
    emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="d" * 40,
        recorded_by="claude",
    )

    # read_events (the WP reducer reader) skips the two lifecycle events.
    assert len(read_events(feature_dir)) == wp_events_before


# ---------------------------------------------------------------------------
# T009: format_post_mission_events renderer (views.py)
# ---------------------------------------------------------------------------


def _canonical_post_mission_events(
    tmp_path: Path,
) -> tuple[list[dict[str, Any]], Path]:
    """Emit one reopen + one commit follow-up via the canonical helpers and
    return the persisted envelopes (renderer input) + the feature_dir."""
    feature_dir = tmp_path / "kitty-specs" / "090-render"
    _write_meta(feature_dir, merged_at="2026-04-03T10:00:00+00:00")
    emit_mission_reopened(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        reason="critical regression",
        reopened_by="operator",
        reopened_at="2026-05-01T10:00:00+00:00",
    )
    emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="commit",
        commit_sha="e" * 40,
        recorded_by="claude",
        recorded_at="2026-05-02T10:00:00+00:00",
    )
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    return events, feature_dir


def test_renderer_empty_list_returns_empty() -> None:
    assert format_post_mission_events([]) == []
    assert format_post_mission_events(()) == []


def test_renderer_renders_reopen_line(tmp_path: Path) -> None:
    events, _ = _canonical_post_mission_events(tmp_path)
    reopen_events = [e for e in events if e["event_type"] == MISSION_REOPENED]
    lines = format_post_mission_events(reopen_events)
    assert len(lines) == 1
    line = lines[0]
    # actor + reason + when are all surfaced.
    assert line.startswith("re-opened by operator")
    assert "critical regression" in line
    assert "2026-05-01T10:00:00+00:00" in line


def test_renderer_renders_follow_up_commit_line(tmp_path: Path) -> None:
    events, _ = _canonical_post_mission_events(tmp_path)
    follow_events = [e for e in events if e["event_type"] == FOLLOW_UP_RECORDED]
    lines = format_post_mission_events(follow_events)
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("follow-up commit " + "e" * 40)
    assert "by claude" in line
    assert "2026-05-02T10:00:00+00:00" in line


def test_renderer_renders_follow_up_pr_line(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "091-render-pr"
    _write_meta(feature_dir, merged_at="2026-04-03T10:00:00+00:00")
    emit_follow_up_recorded(
        feature_dir,
        mission_id=MISSION_ID,
        mission_slug=feature_dir.name,
        follow_up_type="pr",
        pr_number=99,
        recorded_by="renata",
        recorded_at="2026-05-03T10:00:00+00:00",
    )
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    lines = format_post_mission_events(events)
    assert lines == ["follow-up PR #99 by renata (2026-05-03T10:00:00+00:00)"]


def test_renderer_renders_reopen_and_follow_up_together(tmp_path: Path) -> None:
    events, _ = _canonical_post_mission_events(tmp_path)
    lines = format_post_mission_events(events)
    assert len(lines) == 2
    assert any(line.startswith("re-opened by operator") for line in lines)
    assert any(line.startswith("follow-up commit") for line in lines)


def test_renderer_reopen_without_reason_omits_suffix(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "092-no-reason"
    _write_meta(feature_dir, merged_at="2026-04-03T10:00:00+00:00")
    # A pre-#6438 ledger line. `emit_mission_reopened` now builds
    # `MissionReopenedPayload`, whose `reason` is non-empty by contract, so the
    # emitter can no longer produce this shape; historical rows are never
    # rewritten and the renderer must still handle them. The row is therefore
    # appended through the same public primitive the emitter uses.
    le.append_lifecycle_event(
        mission_event_log_path(feature_dir),
        MISSION_REOPENED,
        {
            "mission_id": MISSION_ID,
            "mission_slug": feature_dir.name,
            "reason": "",
            "reopened_by": "operator",
            "reopened_at": "2026-05-04T10:00:00+00:00",
            "cleared_merge": None,
        },
        aggregate_id=MISSION_ID,
        aggregate_type="Mission",
        mission_slug=feature_dir.name,
    )
    events = read_lifecycle_events(mission_event_log_path(feature_dir))
    lines = format_post_mission_events(events)
    assert lines == ["re-opened by operator (2026-05-04T10:00:00+00:00)"]
    # No trailing " — " em-dash separator when reason is empty.
    assert "—" not in lines[0]


def test_renderer_skips_non_dict_and_non_dict_payload_entries() -> None:
    # Defensive branches (views.py): a non-dict entry is skipped entirely; a
    # dict entry whose payload is not a dict is treated as an empty payload
    # (actor → "unknown"), never raising.
    # Built as list[Any]: the renderer's runtime guards (isinstance checks)
    # are the unit under test, so we deliberately feed off-contract shapes.
    malformed: list[Any] = [
        "not-a-dict",
        # canonical-event-exempt(exception-flow): off-contract shape feeds views.py isinstance guards; no *Payload model can represent a non-dict-payload entry
        {"event_type": "UnrelatedEvent", "payload": {}},
        # canonical-event-exempt(exception-flow): payload=None is a malformed shape the canonical emit path never produces; exercises the views.py coerce guard
        {
            "event_type": MISSION_REOPENED,
            "timestamp": "2026-05-05T10:00:00+00:00",
            "payload": None,  # non-dict payload → coerced to {}
        },
    ]
    rendered = format_post_mission_events(malformed)
    assert rendered == ["re-opened by unknown (2026-05-05T10:00:00+00:00)"]


# ---------------------------------------------------------------------------
# Emit-helper branch coverage (lifecycle_events.py / lifecycle.py / emit.py)
# ---------------------------------------------------------------------------


def test_iso_str_to_datetime_parses_and_passes_through_none() -> None:
    from specify_cli.status.lifecycle_events import _iso_str_to_datetime

    assert _iso_str_to_datetime(None) is None
    parsed = _iso_str_to_datetime("2026-05-06T10:00:00+00:00")
    assert parsed is not None
    assert parsed == datetime(2026, 5, 6, 10, 0, tzinfo=UTC)


def test_follow_up_commit_without_sha_raises(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "093-bad-commit"
    feature_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="commit_sha is required"):
        emit_follow_up_recorded(
            feature_dir,
            mission_id=MISSION_ID,
            mission_slug=feature_dir.name,
            follow_up_type="commit",
            commit_sha=None,
            recorded_by="claude",
        )


def test_follow_up_pr_without_number_raises(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "094-bad-pr"
    feature_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="pr_number is required"):
        emit_follow_up_recorded(
            feature_dir,
            mission_id=MISSION_ID,
            mission_slug=feature_dir.name,
            follow_up_type="pr",
            pr_number=None,
            recorded_by="claude",
        )


def test_follow_up_unknown_type_raises(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "095-bad-type"
    feature_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="follow_up_type must be 'commit' or 'pr'"):
        emit_follow_up_recorded(
            feature_dir,
            mission_id=MISSION_ID,
            mission_slug=feature_dir.name,
            follow_up_type="tag",
            recorded_by="claude",
        )


def test_latest_event_time_falls_back_to_envelope_timestamp() -> None:
    # lifecycle._latest_event_time: when the payload carries neither
    # reopened_at nor recorded_at, the envelope ``timestamp`` is used.
    from specify_cli.status.lifecycle import _latest_event_time

    # canonical-event-exempt(exception-flow): payload omits reopened_at (the emit path always sets it) to force the envelope-timestamp fallback in lifecycle
    event = {
        "event_type": MISSION_REOPENED,
        "timestamp": "2026-05-07T10:00:00+00:00",
        "payload": {"reopened_by": "operator"},  # no reopened_at
    }
    parsed = _latest_event_time(event)
    assert parsed == datetime(2026, 5, 7, 10, 0, tzinfo=UTC)


def test_derive_from_lane_returns_genesis_when_wp_state_lacks_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # emit._derive_from_lane: a reduced WP state present but carrying no
    # ``lane`` key falls back to GENESIS rather than raising.
    from specify_cli.status import emit as emit_mod
    from specify_cli.status.models import Lane as _Lane
    from specify_cli.status.models import StatusSnapshot

    feature_dir = _merged_mission(tmp_path, merged_at="2026-04-03T10:00:00+00:00")

    lan_eless_snapshot = StatusSnapshot(
        mission_slug=feature_dir.name,
        materialized_at="2026-05-08T10:00:00+00:00",
        event_count=1,
        last_event_id="01TESTNOLANE0000000000001",
        work_packages={"WP01": {"actor": "claude"}},  # no "lane" key
        summary={},
    )
    monkeypatch.setattr(emit_mod._reducer, "reduce", lambda _events: lan_eless_snapshot)

    assert emit_mod._derive_from_lane(feature_dir, "WP01") == str(_Lane.GENESIS)
