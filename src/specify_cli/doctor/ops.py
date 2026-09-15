"""Op orphan detection and stale sweep for spec-kitty doctor ops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from kernel.clock import datetime, UTC, parse_iso
from pathlib import Path

from specify_cli.invocation.errors import AlreadyClosedError
from specify_cli.invocation.writer import EVENTS_DIR, OP_CLOSURES_FILENAME, OP_CLOSURES_RELATIVE_PATH, closed_invocation_ids

_NON_OP_JSONL = {
    "ops-index.jsonl",
    "lifecycle.jsonl",
    "propagation-errors.jsonl",
    OP_CLOSURES_FILENAME,
}


def _has_completed_event(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("event") == "completed":
                    return True
    except OSError:
        return False
    return False


def list_orphan_ops(repo_root: Path) -> list[Path]:
    """List open Op records: no ``completed`` event and no spine closure.

    An Op counts as closed when its per-record file carries a ``completed``
    event OR the append-only closure spine (#4397) carries a closure for its
    invocation id — the doctor sweep closes pre-existing records on the spine,
    never by mutating the byte-frozen per-record file.
    """
    ops_dir = repo_root / EVENTS_DIR
    if not ops_dir.exists():
        return []
    closed_on_spine = closed_invocation_ids(repo_root)
    return [
        path for path in sorted(ops_dir.glob("*.jsonl")) if path.name not in _NON_OP_JSONL and path.stem not in closed_on_spine and not _has_completed_event(path)
    ]


@dataclass
class SweepOpEntry:
    """Per-op sweep result mirroring the doctor-ops-close-stale contract JSON."""

    invocation_id: str
    profile_id: str
    started_at: str
    age_hours: float | None
    action_taken: str  # "none" | "closed_abandoned" | "already_closed"
    parse_warning: str | None = None
    error: str | None = None
    commit: str | None = None  # "committed" | "not_committed:<refusal>" (sweep closes only)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "invocation_id": self.invocation_id,
            "profile_id": self.profile_id,
            "started_at": self.started_at,
            "age_hours": self.age_hours,
            "action_taken": self.action_taken,
        }
        if self.parse_warning is not None:
            result["parse_warning"] = self.parse_warning
        if self.error is not None:
            result["error"] = self.error
        if self.commit is not None:
            result["commit"] = self.commit
        return result


@dataclass
class SweepReport:
    """Result of a doctor ops stale sweep, per contracts/doctor-ops-close-stale.md."""

    open_ops: list[SweepOpEntry] = field(default_factory=list)
    swept: int = 0
    skipped_fresh: int = 0
    threshold_hours: float = 24.0

    @property
    def has_errors(self) -> bool:
        return any(entry.error is not None for entry in self.open_ops)

    def to_dict(self) -> dict[str, object]:
        return {
            "open_ops": [entry.to_dict() for entry in self.open_ops],
            "swept": self.swept,
            "skipped_fresh": self.skipped_fresh,
            "threshold_hours": self.threshold_hours,
            "closure_spine": OP_CLOSURES_RELATIVE_PATH.as_posix(),
        }


def _read_started_fields(path: Path) -> tuple[str, str]:
    """Return (profile_id, started_at) from the first event line, best-effort."""
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        event = json.loads(first_line)
    except (OSError, IndexError, json.JSONDecodeError):
        return "", ""
    if not isinstance(event, dict):
        return "", ""
    return str(event.get("profile_id") or ""), str(event.get("started_at") or "")


def _age_hours(started_at: str, now: datetime) -> float | None:
    """Age in hours from started_at to now; None when started_at is unparseable.

    Comparisons are timezone-aware only: a naive started_at is interpreted as UTC.
    """
    try:
        started = parse_iso(started_at)
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (now - started).total_seconds() / 3600.0


def close_stale_ops(
    repo_root: Path,
    *,
    threshold_hours: float,
    now: datetime,
) -> SweepReport:
    """Close open Ops older than ``threshold_hours`` as abandoned via the executor.

    Every close goes through ``ProfileInvocationExecutor.complete_invocation`` with
    ``outcome="abandoned"`` and ``closed_by="doctor_sweep"`` — the only sanctioned
    close path (research R4); the sweep never appends JSONL directly. Because the
    sweep's targets are pre-existing ``kitty-ops/`` records — byte-frozen archive
    history under the historical-preservation gate — the executor records each
    closure on the append-only spine ``kitty-ops/op-closures.jsonl`` and auto-commits
    only that spine; per-record files are never touched (#4397). A race with a
    concurrent manual close (``AlreadyClosedError``) is recorded as
    ``already_closed`` and is not a failure. Any other per-op exception is recorded
    as an error entry and the sweep continues.

    Unparseable ``started_at`` timestamps are treated as stale (the broken-record
    case the sweep exists for) and carry a ``parse_warning``.
    ``threshold_hours == 0`` sweeps all open Ops.
    """
    from specify_cli.invocation.executor import ProfileInvocationExecutor
    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    report = SweepReport(threshold_hours=threshold_hours)
    orphans = list_orphan_ops(repo_root)
    if not orphans:
        return report

    # Same SaaS propagator the dispatch close path uses (FR-008 parity):
    # sync-gated and best-effort inside the propagator itself, so swept
    # `abandoned` completions reach SaaS instead of leaving the Op open there.
    executor = ProfileInvocationExecutor(repo_root, propagator=InvocationSaaSPropagator(repo_root))
    for path in orphans:
        invocation_id = path.stem
        profile_id, started_at = _read_started_fields(path)
        age = _age_hours(started_at, now)
        parse_warning = None if age is not None else (f"unparseable started_at {started_at!r}; treated as stale")
        is_stale = threshold_hours == 0 or age is None or age > threshold_hours
        entry = SweepOpEntry(
            invocation_id=invocation_id,
            profile_id=profile_id,
            started_at=started_at,
            age_hours=age,
            action_taken="none",
            parse_warning=parse_warning,
        )
        if not is_stale:
            report.skipped_fresh += 1
            report.open_ops.append(entry)
            continue
        try:
            executor.complete_invocation(
                invocation_id,
                outcome="abandoned",
                closed_by="doctor_sweep",
            )
            entry.action_taken = "closed_abandoned"
            report.swept += 1
            outcome_note = executor.last_op_commit
            if outcome_note is not None and outcome_note.committed:
                entry.commit = "committed"
            elif outcome_note is not None:
                entry.commit = f"not_committed:{outcome_note.refusal or 'unknown refusal'}"
        except AlreadyClosedError:
            entry.action_taken = "already_closed"
        except Exception as exc:  # noqa: BLE001 - one bad file must not block the sweep
            entry.error = repr(exc)
        report.open_ops.append(entry)
    return report
