"""Open-Ops rendering for session presence (session-start / session-stop).

Surfaces orphaned Ops — work that was opened via ``spec-kitty dispatch`` but
never closed — at session boundaries (FR-009).

Performance contract: this runs on every Claude Code session start/stop, so it
is scan-only (``list_orphan_ops()``), makes no git calls, and must add < 0.5 s
at 1,000 Op files (same pro-rata budget as the doctor ops sweep enumeration).

Scope: this surface reads the project root checkout's ``kitty-ops/`` only,
deliberately. Op records can also live in a linked worktree (#6564), and the
repository-wide sweep is ``spec-kitty doctor ops`` (#6661); listing worktree Ops
here would need one ``git worktree list`` per session boundary and is a separate
decision with its own latency budget.
"""

from __future__ import annotations

import json
from kernel.clock import UTC, datetime, parse_iso, Clock, DEFAULT_CLOCK
from pathlib import Path


__all__ = ["render_open_ops_section", "render_open_ops_reminder"]

_CLOSE_CMD = "spec-kitty profile-invocation complete --invocation-id {invocation_id} --outcome <done|failed|abandoned>"
_SWEEP_HINT = "Sweep stale ones: spec-kitty doctor ops --close-stale"


def _read_first_event(path: Path) -> tuple[str, str]:
    """Return (profile_id, started_at) from the first JSONL line, best-effort."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            first_line = handle.readline()
        event = json.loads(first_line)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "", ""
    if not isinstance(event, dict):
        return "", ""
    return str(event.get("profile_id") or ""), str(event.get("started_at") or "")


def _format_age(started_at: str, now: datetime) -> str:
    """Human age like ``26h old``; empty string when unparseable."""
    try:
        started = parse_iso(started_at)
    except ValueError:
        return ""
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    hours = max(0.0, (now - started).total_seconds() / 3600.0)
    return f"{int(hours)}h old"


def render_open_ops_section(repo_root: Path, now: datetime | None = None, *, clock: Clock = DEFAULT_CLOCK) -> str:
    """Render the open-Ops section for session-start output.

    Returns an empty string when there are no open Ops — zero open Ops must
    produce zero extra output.  No git calls; single directory scan.

    ``clock``: injectable :class:`kernel.clock.Clock` (kernel-clock-single-door
    FR-009); defaults to :data:`kernel.clock.DEFAULT_CLOCK`. Used only when
    ``now`` is omitted -- ``now`` (an explicit value) still takes precedence.
    """
    from specify_cli.doctor.ops import list_orphan_ops

    orphans = list_orphan_ops(repo_root)
    if not orphans:
        return ""
    now = now if now is not None else clock.now()
    lines = [f"⚠ Open Ops ({len(orphans)}): work that was dispatched but never closed"]
    for path in orphans:
        invocation_id = path.stem
        profile_id, started_at = _read_first_event(path)
        age = _format_age(started_at, now)
        meta = ", ".join(part for part in (profile_id, age) if part)
        meta_text = f" ({meta})" if meta else ""
        lines.append(f"  {invocation_id}{meta_text} — close: " + _CLOSE_CMD.format(invocation_id=invocation_id))
    lines.append(_SWEEP_HINT)
    return "\n".join(lines)


def render_open_ops_reminder(repo_root: Path, now: datetime | None = None, *, clock: Clock = DEFAULT_CLOCK) -> str:
    """Render the end-of-session reminder for the Stop hook.

    Returns an empty string when there are no open Ops.  Scan-only, no git.
    """
    section = render_open_ops_section(repo_root, now=now, clock=clock)
    if not section:
        return ""
    return "spec-kitty: this session is ending with open Ops — close each with the\nreal outcome before moving on.\n" + section
