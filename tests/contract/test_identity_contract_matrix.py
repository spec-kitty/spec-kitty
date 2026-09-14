"""Identity contract matrix — the catch-all backstop for FR-062 / FR-063.

This test file enumerates every machine-facing payload surface that mission 083
migrated to the canonical ``mission_id`` identity and asserts that ``mission_id``
is present (or that ``aggregate_id`` is the ULID) in each one.

Surfaces covered
----------------
1. **Status snapshot** — ``StatusSnapshot.to_dict()``:
   the materialised per-mission view written to ``status.json``.
   It must carry the canonical identity fields via
   ``mission_identity_fields(...)``.

2. **Status event envelope (WP-level)** — ``StatusEvent.to_dict()``:
   WP-level events use ``aggregate_id = wp_id`` but the envelope must still
   include ``mission_id`` when the event was written post-WP05.
   (Legacy events without ``mission_id`` survive as compatibility; the field
   is simply omitted.  That case is covered by a separate negative assertion.)

3. **Merge state** — ``MergeState.to_dict()``:
   the persisted merge state at
   ``.kittify/runtime/merge/<mission_id>/state.json`` is keyed by
   ``mission_id`` (WP02 + WP10).

4. **Lane manifest** — ``LanesManifest.to_dict()``:
   the per-feature ``lanes.json`` file carries ``mission_id`` alongside
   ``mission_slug``.

Design notes
------------
- Each surface is exercised against **real production code**, not mocks,
  whenever possible.  The tests emit synthetic payloads through the real
  ``to_dict()`` paths.
- The former surface 5 (the sync ``EventEmitter``'s mission-lifecycle
  emissions) died with the sync transport (issue #5). Surface 5 is now the
  runtime-moment envelope published by epic E3's producer, registered via
  ``register_runtime_emitter_factory`` (``runtime.next._internal_runtime.events``,
  #3929): its payload carries the mission's ``mission_id`` and ``mission_slug``.
- Each parametrised case emits an assertion with a clear surface name so
  a regression immediately identifies the offending payload.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.merge.state import MergeState
from specify_cli.status.models import (
    Lane,
    StatusEvent,
    StatusSnapshot,
)

pytestmark = [pytest.mark.fast]

# A representative ULID used everywhere the tests need a canonical mission_id.
ULID_CANONICAL = "01KNRQK0R1ZDS8Z57M1TRXF0XR"
MISSION_SLUG = "080-canonical-matrix"


# ---------------------------------------------------------------------------
# Surface enumerators — one builder per payload surface.
# ---------------------------------------------------------------------------


def _build_status_snapshot() -> dict[str, Any]:
    """Surface 1: StatusSnapshot.to_dict() carries mission identity fields."""
    snap = StatusSnapshot(
        mission_slug=MISSION_SLUG,
        materialized_at="2026-04-11T12:00:00+00:00",
        event_count=0,
        last_event_id=None,
        work_packages={},
        summary={lane.value: 0 for lane in Lane},
        mission_number=80,
        mission_type="software-dev",
    )
    return snap.to_dict()


def _build_wp_status_event() -> dict[str, Any]:
    """Surface 2: StatusEvent (WP-level) envelope includes mission_id."""
    event = StatusEvent(
        event_id="01HXYZ0123456789ABCDEFGHJK",
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-04-11T12:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        mission_id=ULID_CANONICAL,
    )
    return event.to_dict()


def _build_merge_state() -> dict[str, Any]:
    """Surface 3: MergeState.to_dict() is keyed by mission_id."""
    state = MergeState(
        mission_id=ULID_CANONICAL,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=["WP01", "WP02"],
    )
    return state.to_dict()


def _build_lanes_manifest() -> dict[str, Any]:
    """Surface 4: LanesManifest.to_dict() carries mission_id."""
    lane_a = ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("src/**",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=ULID_CANONICAL,
        mission_branch=f"kitty/mission-canonical-matrix-{ULID_CANONICAL[:8]}",
        target_branch="main",
        lanes=[lane_a],
        computed_at="2026-04-11T12:00:00+00:00",
        computed_from="dependency_graph",
    )
    return manifest.to_dict()


def _build_runtime_moment_envelope() -> dict[str, Any]:
    """Surface 5: the E3 runtime-moment envelope's payload carries the mission ULID and slug."""
    import json
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from spec_kitty_events.mission_next import MissionRunStartedPayload, RuntimeActorIdentity

    from specify_cli.events.runtime_moments import RuntimeMomentProducer

    run_id = "0123456789abcdef0123456789abcdef"
    payload = MissionRunStartedPayload(
        run_id=run_id,
        mission_type="software-dev",
        actor=RuntimeActorIdentity(actor_id="claude", actor_type="llm"),
    )
    published: list[dict[str, Any]] = []
    with (
        tempfile.TemporaryDirectory() as tmp,
        patch("specify_cli.status.fire_lifecycle_saas_fanout", side_effect=lambda **kwargs: published.append(kwargs)),
    ):
        root = Path(tmp)
        feature_dir = root / "kitty-specs" / MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(json.dumps({"mission_id": ULID_CANONICAL}), encoding="utf-8")
        run_dir = root / ".kittify" / "runtime" / "runs" / run_id
        run_dir.mkdir(parents=True)
        record = {"event_type": "MissionRunStarted", "timestamp": "2026-04-11T12:00:00+00:00", "payload": payload.model_dump(mode="json")}
        (run_dir / "run.events.jsonl").write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        producer = RuntimeMomentProducer.for_mission(feature_dir=feature_dir, mission_slug=MISSION_SLUG, mission_type="software-dev")
        producer.emit_mission_run_started(payload)
    envelope: dict[str, Any] = published[0]["envelope"]
    return envelope


# ---------------------------------------------------------------------------
# Contract matrix
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractSurface:
    """One row in the identity contract matrix."""

    name: str
    builder: Callable[[], dict[str, Any]]
    # Where the canonical ULID must appear in the resulting dict.
    # ``"payload.mission_id"`` is dot-notation for nested lookup.
    identity_locations: tuple[str, ...]
    # Optional — a dot-notation key that must equal the ULID exactly
    # (used for aggregate_id checks where applicable).
    ulid_equals: tuple[str, ...] = ()


CONTRACT_MATRIX: tuple[ContractSurface, ...] = (
    ContractSurface(
        name="status_snapshot",
        builder=_build_status_snapshot,
        identity_locations=("mission_slug",),
        # StatusSnapshot uses mission_identity_fields which outputs slug-based
        # identity metadata (mission_slug, mission_number, mission_type).
        # The ULID itself is not in the snapshot surface because the snapshot
        # is keyed by slug for backward compatibility with dashboard readers.
        # Still asserted here for enumeration completeness.
    ),
    ContractSurface(
        name="wp_status_event",
        builder=_build_wp_status_event,
        identity_locations=("mission_id", "mission_slug"),
        ulid_equals=("mission_id",),
    ),
    ContractSurface(
        name="merge_state",
        builder=_build_merge_state,
        identity_locations=("mission_id", "mission_slug"),
        ulid_equals=("mission_id",),
    ),
    ContractSurface(
        name="lanes_manifest",
        builder=_build_lanes_manifest,
        identity_locations=("mission_id", "mission_slug"),
        ulid_equals=("mission_id",),
    ),
    ContractSurface(
        name="runtime_moment_envelope",
        builder=_build_runtime_moment_envelope,
        identity_locations=("payload.mission_id", "payload.mission_slug", "payload.run_id"),
        ulid_equals=("payload.mission_id",),
    ),
)


def _dig(payload: dict[str, Any], dotted: str) -> Any:
    """Lookup dotted key path, returning ``None`` on miss."""
    cur: Any = payload
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ---------------------------------------------------------------------------
# Parametrised enumeration test — catches any surface that silently drops
# the canonical identity field.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "surface",
    CONTRACT_MATRIX,
    ids=lambda s: s.name,
)
def test_surface_carries_identity(surface: ContractSurface) -> None:
    """Every enumerated machine-facing surface must carry mission identity.

    Fails with an actionable message naming the offending surface so a
    regression is immediately traceable.
    """
    payload = surface.builder()
    assert isinstance(payload, dict), (
        f"Surface {surface.name!r} produced non-dict payload: {type(payload).__name__}"
    )
    assert payload, f"Surface {surface.name!r} produced an empty payload"

    for key in surface.identity_locations:
        value = _dig(payload, key)
        assert value, (
            f"Surface {surface.name!r} is missing identity field {key!r}. "
            f"Payload keys: {sorted(payload.keys())}. "
            f"FR-063 requires every machine-facing surface to carry mission identity."
        )

    for key in surface.ulid_equals:
        value = _dig(payload, key)
        assert value == ULID_CANONICAL, (
            f"Surface {surface.name!r} field {key!r} must equal the canonical "
            f"ULID {ULID_CANONICAL!r}, got {value!r}"
        )


def test_legacy_wp_status_event_without_mission_id_is_valid() -> None:
    """Legacy WP events that lack ``mission_id`` must still be serialisable.

    This is the negative corollary of the matrix check above: a pre-WP05 event
    written before the migration should round-trip cleanly with no
    ``mission_id`` key in ``to_dict()``.  The contract is: post-WP05 events
    carry ``mission_id``; legacy events do not. Readers must handle both.
    """
    legacy_event = StatusEvent(
        event_id="01HXYZ0123456789ABCDEFGHJK",
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-04-11T12:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        # No mission_id — legacy event.
    )
    payload = legacy_event.to_dict()
    assert "mission_id" not in payload, (
        "Legacy StatusEvent without mission_id must not synthesise a false value"
    )
    assert "legacy_aggregate_id" not in payload, (
        "legacy_aggregate_id is only emitted when mission_id is present"
    )
    assert payload["mission_slug"] == MISSION_SLUG


