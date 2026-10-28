"""Policy audit log — separate from the lane-transition event stream.

Policy overrides (risk, commit guard, merge gate) are feature-level or
merge-level actions that do not map to WP lane transitions. They are
stored in a dedicated append-only JSONL file at:

    kitty-specs/{mission_slug}/policy-audit.jsonl

This log is read-only evidence for governance. It does not drive state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import ulid as _ulid_mod

from kernel.errors import GuardedReadError
from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso
from kernel.guarded_read import read_guarded

AUDIT_FILENAME = "policy-audit.jsonl"


class PolicyAuditReadError(GuardedReadError):
    """``policy-audit.jsonl`` could not be read: undecodable, malformed JSON or a malformed event (#6588)."""


class _MalformedAuditLine(ValueError):
    """One audit line that is not a well-formed :class:`PolicyAuditEvent`."""


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
        """Decode one line; raise :class:`ValueError` for malformed JSON or a malformed event."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _MalformedAuditLine(f"invalid JSON: {exc.msg}") from exc
        except RecursionError as exc:
            raise _MalformedAuditLine("invalid JSON: nested too deeply") from exc
        return cls(**_checked_fields(data))


def _checked_fields(data: object) -> dict[str, Any]:
    """*data* as constructor kwargs, or :class:`_MalformedAuditLine` naming what is wrong."""
    if not isinstance(data, dict):
        raise _MalformedAuditLine(f"expected a JSON object, got {type(data).__name__}")
    expected = {f.name for f in fields(PolicyAuditEvent)}
    missing, unexpected = sorted(expected - data.keys()), sorted(data.keys() - expected)
    if missing:
        raise _MalformedAuditLine(f"missing field(s): {', '.join(missing)}")
    if unexpected:
        raise _MalformedAuditLine(f"unexpected field(s): {', '.join(unexpected)}")
    for name in sorted(expected - {"details"}):
        if not isinstance(data[name], str):
            raise _MalformedAuditLine(f"field {name!r} must be a string")
    if not isinstance(data["details"], dict):
        raise _MalformedAuditLine("field 'details' must be an object")
    return data


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


def _parse_audit_lines(content: bytes | str) -> list[PolicyAuditEvent]:
    """Every event of *content*; a malformed line raises :class:`_MalformedAuditLine` naming its 1-based number."""
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    events: list[PolicyAuditEvent] = []
    # split("\n"), not splitlines(): the reported number must be the physical line.
    for line_number, line in enumerate(text.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(PolicyAuditEvent.from_json_line(line))
        except _MalformedAuditLine as exc:
            raise _MalformedAuditLine(f"malformed audit line {line_number}: {exc}") from exc
    return events


def read_audit_events(feature_dir: Path) -> list[PolicyAuditEvent]:
    """Read all policy audit events for a feature.

    Raises:
        PolicyAuditReadError: the file exists but cannot be decoded, or a line is
            not a well-formed event; it names the file and the line (#6588).
    """
    audit_path = feature_dir / AUDIT_FILENAME
    if not audit_path.exists():
        return []
    return read_guarded(audit_path, _parse_audit_lines, errors=(_MalformedAuditLine,), error_cls=PolicyAuditReadError)
