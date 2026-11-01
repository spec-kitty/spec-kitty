"""Canonical ``WPStatusChanged`` wire-payload builder (#6449).

One authority for the payload the TeamSpace replay envelope carries for a lane
transition. Before this module the mission-state dry-run
(``migration/mission_state._status_event_to_teamspace_envelope``) assembled the
payload as a plain dict, so the shape could drift from the contract model and
only surface later, as a conformance report; that dict is gone.

The construction pattern mirrors ``core/mission_payload.build_mission_created_payload``
(#2270): build the contract model, then shape the wire dict through the shared
``apply_keep_none_fields`` primitive.

Wire-shape policy
-----------------
``reason``, ``review_ref`` and ``evidence`` survive as explicit ``null``: the
package's canonical 3.0.0 ``WPStatusChanged`` conformance fixture
(``producer_contract/fixtures/upcast/cases/conformance/mission_lifecycle.WPStatusChanged.136.json``)
carries them that way, and so does every local ``status.events.jsonl`` row. Every
other unset optional is dropped, which means ``mission_id`` appears exactly when
the event has one and ``summary`` (a display-only, producer-supplied field) never
appears for a local transition.

Local-only ``StatusEvent`` fields never cross this boundary: ``policy_metadata``,
``review_result`` and ``reason_source`` are local provenance with no counterpart
on the contract model.

This is a CORE module: it imports the shared contract package and CORE helpers
only, never an INTEGRATION (``sync``/``tracker``) surface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from spec_kitty_events.status import StatusTransitionPayload

from specify_cli.core.payload_shaping import apply_keep_none_fields

from .models import StatusEvent

__all__ = ["build_status_event_payload"]

#: Unset optionals whose explicit ``None`` is part of the wire shape.
_KEEP_NONE_FIELDS: tuple[str, ...] = ("reason", "review_ref", "evidence")

#: Contract fields a local transition cannot supply; the producer fills them.
#: ``summary`` is the display-only gist (spec-kitty/spec-kitty#4327) — a local
#: lane transition never carries one, and inventing one would be fabrication.
_PRODUCER_SUPPLIED_FIELDS: frozenset[str] = frozenset({"summary"})

#: Contract field -> the ``StatusEvent`` attribute it is carried from. Kept as an
#: explicit table so the coverage ratchet in the test suite can assert that this
#: table plus the producer-supplied set equals
#: ``StatusTransitionPayload.model_fields``: a new field on the contract model
#: then fails a test instead of being silently dropped (the defect that dropped
#: ``mission_id`` here, #6449).
_EVENT_FIELD_ATTRS: dict[str, str] = {
    "mission_slug": "mission_slug",
    "mission_id": "mission_id",
    "wp_id": "wp_id",
    "from_lane": "from_lane",
    "to_lane": "to_lane",
    "actor": "actor",
    "force": "force",
    "reason": "reason",
    "execution_mode": "execution_mode",
    "review_ref": "review_ref",
    "evidence": "evidence",
}

_LANE_FIELDS: frozenset[str] = frozenset({"from_lane", "to_lane"})


def build_wp_status_changed_payload(**fields: Any) -> dict[str, Any]:
    """Build the ``WPStatusChanged`` payload from explicit field values.

    Raises ``pydantic.ValidationError`` when the values cannot be represented by
    the contract model — an unknown or misspelled field, a missing required field,
    ``force`` without a reason, ``approved``/``done`` without evidence, malformed
    evidence. Callers that must keep a reporting contract (the dry-run does) catch
    it at their boundary.
    """
    model = StatusTransitionPayload(**fields)
    payload: dict[str, Any] = apply_keep_none_fields(model, keep_none_fields=_KEEP_NONE_FIELDS)
    return payload


def build_status_event_payload(
    event: StatusEvent,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a local ``StatusEvent`` as its canonical ``WPStatusChanged`` payload.

    ``overrides`` lets a historical-replay caller replace individual payload
    fields before construction — the dry-run uses it for exactly two documented
    rewrites (the ``in_progress -> in_review`` ``for_review`` alias and the
    approval/done evidence synthesis). Any other divergence from the event is a
    defect, not an override.

    Unknown override keys raise ``ValueError`` (a typo would otherwise be dropped
    silently, which is the class of bug this builder exists to prevent).
    """
    resolved = dict(overrides or {})
    unknown = sorted(set(resolved) - set(StatusTransitionPayload.model_fields))
    if unknown:
        raise ValueError(f"unknown WPStatusChanged payload override(s): {', '.join(unknown)}; known fields: {', '.join(StatusTransitionPayload.model_fields)}")

    fields: dict[str, Any] = {}
    for payload_field, event_attr in _EVENT_FIELD_ATTRS.items():
        if payload_field in resolved:
            fields[payload_field] = resolved.pop(payload_field)
        else:
            fields[payload_field] = _event_value(event, payload_field, event_attr)
    for producer_field in _PRODUCER_SUPPLIED_FIELDS:
        if producer_field in resolved:
            fields[producer_field] = resolved.pop(producer_field)
    return build_wp_status_changed_payload(**fields)


def _event_value(event: StatusEvent, payload_field: str, event_attr: str) -> Any:
    """Return ``event``'s value for one contract field, rendered for the model."""
    value = getattr(event, event_attr)
    if payload_field in _LANE_FIELDS:
        # The contract model accepts canonical lane strings and resolves aliases.
        return str(value)
    if payload_field == "evidence":
        return event.evidence.to_dict() if event.evidence else None
    # ``actor`` (string or resolved-binding dict) and the plain scalars pass
    # through verbatim; ``StatusEvent.__post_init__`` already decoded the actor.
    return value
