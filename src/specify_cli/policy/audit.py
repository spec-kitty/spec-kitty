"""Policy audit log — separate from the lane-transition event stream.

Policy overrides (risk, commit guard, merge gate) are feature-level or
merge-level actions that do not map to WP lane transitions. They are
stored in a dedicated append-only JSONL file at:

    kitty-specs/{mission_slug}/policy-audit.jsonl

This log is read-only evidence for governance. It does not drive state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import ulid as _ulid_mod

from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso

AUDIT_FILENAME = "policy-audit.jsonl"


def _generate_ulid() -> str:
    if hasattr(_ulid_mod, "new"):
        return str(_ulid_mod.new().str)
    return str(_ulid_mod.ULID())


@dataclass(frozen=True)
class PolicyAuditEvent:
    """A single policy audit event."""

    event_id: str
    event_type: str  # "risk_override" | "commit_guard_override" | "merge_gate_override"
    mission_slug: str
    actor: str
    reason: str
    details: dict[str, Any]
    at: str  # ISO 8601

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json_line(cls, line: str) -> PolicyAuditEvent:
        data = json.loads(line)
        return cls(**data)


def create_audit_event(
    event_type: str,
    mission_slug: str,
    actor: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> PolicyAuditEvent:
    """Create a new PolicyAuditEvent with generated ID and timestamp."""
    return PolicyAuditEvent(
        event_id=_generate_ulid(),
        event_type=event_type,
        mission_slug=mission_slug,
        actor=actor,
        reason=reason,
        details=details or {},
        at=now_utc_iso(),
    )


def append_audit_event(feature_dir: Path, event: PolicyAuditEvent) -> None:
    """Append a policy audit event to the feature's audit log."""
    audit_path = feature_dir / AUDIT_FILENAME
    # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
    append_event_log_lines(audit_path, [event.to_json_line()])


def read_audit_events(feature_dir: Path) -> list[PolicyAuditEvent]:
    """Read all policy audit events for a feature."""
    audit_path = feature_dir / AUDIT_FILENAME
    if not audit_path.exists():
        return []
    events: list[PolicyAuditEvent] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(PolicyAuditEvent.from_json_line(line))
    return events
