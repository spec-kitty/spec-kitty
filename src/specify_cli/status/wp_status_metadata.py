"""CORE params object for ``WPStatusChanged`` fan-out.

This dataclass lives in the CORE ``status`` layer rather than in
``sync``/INTEGRATION so that CORE producers — ``status/emit._saas_fan_out`` and
the coordination outbound path — can build it without crossing the
CORE→INTEGRATION boundary enforced by
``tests/architectural/test_integration_boundary.py`` (the crossing allowlist is
permanently closed). ``sync.events`` re-exports it for the INTEGRATION-side
emitter, which is the allowed INTEGRATION→CORE direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WPStatusChangeMetadata:
    """Optional ``WPStatusChanged`` fields, bundled into one params object.

    S107: ``emit_wp_status_changed`` originally declared these 8 fields as
    individual keyword parameters, pushing it to 15 total parameters. Every
    field here mirrors the identically-named keyword ``EventEmitter.
    emit_wp_status_changed`` (``sync/emitter.py``) already accepts, so
    threading ``metadata`` through to that call is a plain field-by-field
    unpack — no behavior change.
    """

    causation_id: str | None = None
    policy_metadata: dict[str, Any] | None = None
    force: bool = False
    reason: str | None = None
    review_ref: str | None = None
    # One-line human gist of the transition (#4327); carried onto the
    # ``WPStatusChanged`` moment as the bounded inline ``summary`` attr by
    # the Zeitgeist bridge (capability-gated on the installed codec).
    summary: str | None = None
    execution_mode: str | None = None
    evidence: dict[str, Any] | None = None
    occurred_at: str | None = None

    @classmethod
    def from_status_event(
        cls, event: Any, *, policy_metadata: dict[str, Any] | None = None
    ) -> WPStatusChangeMetadata:
        """Build from a StatusEvent (the two production fan-out callers).

        ``policy_metadata`` is passed explicitly because callers resolve it
        separately from the event (status/emit.py resolves its own; the
        coordination outbound path uses ``event.policy_metadata``).
        """
        return cls(
            causation_id=event.event_id,
            policy_metadata=policy_metadata,
            force=event.force,
            reason=event.reason,
            review_ref=event.review_ref,
            summary=getattr(event, "summary", None),
            execution_mode=event.execution_mode,
            evidence=event.evidence.to_dict() if event.evidence else None,
            occurred_at=event.at,
        )
