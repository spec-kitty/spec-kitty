"""Op orphan detection and stale sweep for spec-kitty doctor ops."""

from __future__ import annotations

import dataclasses
import json
from collections import Counter
import logging
import os
from dataclasses import dataclass, field
from kernel.clock import datetime, UTC, parse_iso
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.invocation.errors import AlreadyClosedError
from specify_cli.invocation.lifecycle import find_orphans, read_lifecycle_records, write_abandoned_completion
from specify_cli.invocation.op_custody import repository_checkouts
from specify_cli.invocation.writer import EVENTS_DIR, OP_CLOSURES_RELATIVE_PATH, open_invocation_ids

if TYPE_CHECKING:
    from specify_cli.invocation.executor import OpCommitOutcome
    from specify_cli.invocation.record import ProfileInvocationRecord

#: ``SweepOpEntry.commit`` prefix for a sweep close whose spine commit was
#: deliberately skipped (#6410): the closure stays on disk, uncommitted.
SWEEP_COMMIT_SKIPPED_PREFIX = "skipped:"

logger = logging.getLogger(__name__)


def display_path(path: Path, repo_root: Path) -> str:
    """*path* relative to the project root, with ``/`` separators (#6661).

    A record in a linked worktree has no path under the project root, so it renders
    as ``../lane/kitty-ops/<id>.jsonl`` rather than raising ``ValueError`` like
    ``Path.relative_to``. A record in the root checkout keeps the historical
    ``kitty-ops/<id>.jsonl``. Both sides are normalized first, so a symlinked root
    does not produce a cosmetically odd route.

    The one case with no relative form is a checkout on a different drive (Windows),
    where ``os.path.relpath`` raises; there the absolute path is returned, because a
    correct absolute path beats a wrong or invented relative one.
    """
    try:
        relative = os.path.relpath(Path(path).resolve(), Path(repo_root).resolve())
    except ValueError:  # a different Windows drive has no relative path
        return Path(path).as_posix()
    return Path(relative).as_posix()


def list_orphan_ops(repo_root: Path) -> list[Path]:
    """List open Op records in ONE checkout: no ``completed`` event, no spine closure.

    A single-directory scan of ``<repo_root>/kitty-ops`` — no git calls — because
    the session-start/stop reminder calls it on every session boundary under a
    < 0.5 s budget. It therefore sees the checkout it is handed and nothing else:
    use :func:`scan_op_records` for the repository-wide sweep.

    An Op counts as closed when its per-record file carries a ``completed``
    event OR the append-only closure spine (#4397) carries a closure for its
    invocation id — the doctor sweep closes pre-existing records on the spine,
    never by mutating the byte-frozen per-record file. Both halves of that rule
    live in :func:`specify_cli.invocation.writer.open_invocation_ids`, so this
    surface and the local-retention engine cannot disagree about it (#6739).
    """
    ops_dir = repo_root / EVENTS_DIR
    if not ops_dir.is_dir():
        return []
    return [ops_dir / f"{invocation_id}.jsonl" for invocation_id in sorted(open_invocation_ids(repo_root))]


def _checkouts(repo_root: Path) -> list[Path]:
    """The project root checkout first, then every linked worktree, de-duplicated."""
    checkouts: list[Path] = []
    seen: set[Path] = set()
    for checkout in [repo_root, *repository_checkouts(repo_root)]:
        key = checkout.resolve()
        if key in seen:
            continue
        seen.add(key)
        checkouts.append(checkout)
    return checkouts


def scan_op_records(repo_root: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Orphan Op records as ``(owning checkout, record path)`` pairs, and unreadable checkouts.

    Reads every checkout of the repository (#6661): Op records are written in the
    checkout the command runs in (#6564), so a record can live in a linked worktree.
    The checkout set is the shared enumeration in
    :mod:`specify_cli.invocation.op_custody` (one ``git worktree list`` per call); each
    checkout is read with its own :func:`list_orphan_ops`, so its own closure spine
    decides what is still open. Ordering is the project root first, then
    ``git worktree list`` order, and file-name order inside a checkout.

    Without git (not a checkout, or the command fails) the set is the project root
    alone, which is the behavior before #6661.

    The owning checkout is the one the record was read from, never re-derived from the
    record's path shape, so a sweep closes a record through the checkout that produced
    it. A checkout whose Op store cannot be read is returned separately rather than
    aborting the scan (NFR-002) and rather than disappearing silently: the command
    reports it on stderr.
    """
    found: list[tuple[Path, Path]] = []
    unreadable: list[Path] = []
    for checkout in _checkouts(repo_root):
        try:
            records = list_orphan_ops(checkout)
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("doctor ops: cannot read Op records in %s: %s", checkout, exc)
            unreadable.append(checkout)
            continue
        found.extend((checkout, record) for record in records)
    return found, unreadable


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
    commit: str | None = None  # "committed" | "not_committed:<refusal>" | "skipped:<reason>" (sweep closes only)

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
class SweepLifecycleEntry:
    """One orphaned ``started`` lifecycle record the sweep saw (#7346, contract doctor-ops-lifecycle-sweep)."""

    canonical_action_id: str
    mission_id: str
    wp_id: str | None
    agent: str
    started_at: str
    age_hours: float | None
    action_taken: str = "none"  # "none" | "closed_abandoned"
    path: str | None = None  # the closure file, relative to the checkout holding it
    commit: str | None = None  # "committed" | "not_committed:<refusal>" | "skipped:<reason>"
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclass
class SweepReport:
    """Result of a doctor ops stale sweep, per contracts/doctor-ops-close-stale.md."""

    open_ops: list[SweepOpEntry] = field(default_factory=list)
    swept: int = 0
    skipped_fresh: int = 0
    threshold_hours: float = 24.0
    #: Orphaned WP lifecycle records the sweep saw (#7346); additive JSON key.
    lifecycle_records: list[SweepLifecycleEntry] = field(default_factory=list)
    #: Checkouts whose Op store could not be read. Deliberately absent from
    #: :meth:`to_dict`: the sweep JSON is a frozen contract (C-001), so the command
    #: reports these on stderr instead of inventing a key.
    unreadable_checkouts: list[Path] = field(default_factory=list, repr=False)

    @property
    def has_errors(self) -> bool:
        entries: list[SweepOpEntry | SweepLifecycleEntry] = [*self.open_ops, *self.lifecycle_records]
        return any(entry.error is not None for entry in entries)

    @property
    def lifecycle_fresh(self) -> int:
        """Orphaned lifecycle records left open because they are younger than the threshold."""
        return sum(1 for entry in self.lifecycle_records if entry.action_taken == "none" and entry.error is None)

    def to_dict(self) -> dict[str, object]:
        return {
            "open_ops": [entry.to_dict() for entry in self.open_ops],
            "swept": self.swept,
            "skipped_fresh": self.skipped_fresh,
            "threshold_hours": self.threshold_hours,
            "closure_spine": OP_CLOSURES_RELATIVE_PATH.as_posix(),
            "lifecycle_records": [entry.to_dict() for entry in self.lifecycle_records],
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

    Records are swept in every checkout of the repository (#6661), and each one is
    closed by an executor whose ``record_root`` is the checkout that holds it, so
    the spine append and its auto-commit land there rather than in the project root.
    ``repo_root`` still owns governance (profiles, glossary) and the SaaS propagator.

    Unparseable ``started_at`` timestamps are treated as stale (the broken-record
    case the sweep exists for) and carry a ``parse_warning``.
    ``threshold_hours == 0`` sweeps all open Ops.
    """
    from specify_cli.invocation.executor import ProfileInvocationExecutor
    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    report = SweepReport(threshold_hours=threshold_hours)
    orphans, report.unreadable_checkouts = scan_op_records(repo_root)
    if not orphans:
        return report

    # Same SaaS propagator the dispatch close path uses (FR-008 parity):
    # sync-gated and best-effort inside the propagator itself, so swept
    # `abandoned` completions reach SaaS instead of leaving the Op open there.
    propagator = InvocationSaaSPropagator(repo_root)
    executors: dict[Path, ProfileInvocationExecutor] = {}

    def executor_for(checkout: Path) -> ProfileInvocationExecutor:
        """The executor for *checkout*: one per checkout, reused across its Ops."""
        key = checkout.resolve()
        executor = executors.get(key)
        if executor is None:
            executor = ProfileInvocationExecutor(repo_root, record_root=checkout, propagator=propagator)
            executors[key] = executor
        return executor

    for checkout, path in orphans:
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
            executor = executor_for(checkout)
            executor.complete_invocation(
                invocation_id,
                outcome="abandoned",
                closed_by="doctor_sweep",
            )
            entry.action_taken = "closed_abandoned"
            report.swept += 1
            entry.commit = _commit_note(executor.last_op_commit)
        except AlreadyClosedError:
            entry.action_taken = "already_closed"
        except Exception as exc:  # noqa: BLE001 - one bad file must not block the sweep
            entry.error = repr(exc)
        report.open_ops.append(entry)
    return report


def _commit_note(outcome: OpCommitOutcome | None) -> str | None:
    """A sweep entry's ``commit`` value for an auto-commit outcome (#4397, #6410)."""
    if outcome is None:
        return None
    if outcome.committed:
        return "committed"
    if outcome.skipped:
        return f"{SWEEP_COMMIT_SKIPPED_PREFIX}{outcome.skipped}"
    return f"not_committed:{outcome.refusal or 'unknown refusal'}"


# ---------------------------------------------------------------------------
# WP lifecycle records (#7346)
# ---------------------------------------------------------------------------

#: A lifecycle record's identity across checkouts: Mission, action, agent, work package, ``at``.
_LifecycleKey = tuple[str, str, str, str | None, str]

#: ``reason`` of an ``abandoned`` lifecycle record the sweep writes.
LIFECYCLE_ABANDONED_REASON = "abandoned by doctor ops --close-stale (older than {threshold}h)"


def close_stale_lifecycle_records(repo_root: Path, *, threshold_hours: float, now: datetime) -> list[SweepLifecycleEntry]:
    """Close orphaned WP lifecycle records older than ``threshold_hours`` as abandoned (#7346).

    Every checkout of the repository is read first (the project root first, as
    :func:`scan_op_records` orders them). A ``started`` record that no completion
    pairs is reported; one older than the threshold (any, at ``0``) gets an
    ``abandoned`` record written next to it in the checkout that holds it
    (:func:`~specify_cli.invocation.lifecycle.write_abandoned_completion`).

    A record held by several checkouts (tracked on a shared branch) is closed at
    most once across them: never when any checkout already holds its completion,
    otherwise once, in the first checkout that holds it. Identical records within
    one checkout are each their own orphan, so occurrences are counted, not
    collapsed. Each checkout's closures are committed once through the executor's
    record commit (#6410 skip rules, protected-branch refusal reported). Mission
    status, ``meta.json`` and work package files are never read or written.
    """
    stores = [(checkout, records) for checkout in _checkouts(repo_root) if (records := _read_lifecycle_store(checkout)) is not None]
    # The most completions of a record identity any one checkout holds: those copies are closed somewhere.
    paired_somewhere: Counter[_LifecycleKey] = Counter()
    for _checkout, records in stores:
        paired_somewhere |= _paired_counts(records)
    seen: Counter[_LifecycleKey] = Counter()
    entries: list[SweepLifecycleEntry] = []
    for checkout, records in stores:
        entries.extend(
            _sweep_lifecycle_checkout(repo_root, checkout, records, threshold_hours=threshold_hours, now=now, seen=seen, paired_somewhere=paired_somewhere)
        )
    return entries


def _record_key(record: ProfileInvocationRecord) -> _LifecycleKey:
    return (record.mission_id, record.canonical_action_id, record.agent, record.wp_id, record.at.isoformat())


def _read_lifecycle_store(checkout: Path) -> list[ProfileInvocationRecord] | None:
    try:
        records: list[ProfileInvocationRecord] = read_lifecycle_records(checkout)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("doctor ops: cannot read lifecycle records in %s: %s", checkout, exc)
        return None
    return records


def _unpaired_ids(records: list[ProfileInvocationRecord]) -> set[int]:
    """The ``started`` records no completion pairs, matched record by record (WP02 review B3).

    Pairing counts per ``(mission_id, canonical_action_id)`` group, and
    :func:`~specify_cli.invocation.lifecycle.unpaired_started` names the group's
    latest records as the unpaired ones. One ``implement::implement`` group holds
    every work package of a Mission, so that label can name a record its own
    checkout completed, and the sweep compares records across checkouts. Here a
    completion pairs a ``started`` record of its own agent and work package first,
    then any remaining one in read order. The counts per group are unchanged.
    """
    unpaired: set[int] = set()
    for group in find_orphans(records):
        open_started = list(group.started)
        for completion in group.completions:
            match = next((s for s in open_started if (s.agent, s.wp_id) == (completion.agent, completion.wp_id)), None)
            open_started.remove(match if match is not None else open_started[0])
        unpaired.update(id(record) for record in open_started)
    return unpaired


def _paired_counts(records: list[ProfileInvocationRecord]) -> Counter[_LifecycleKey]:
    """Per record identity, how many of a checkout's ``started`` copies a completion pairs."""
    unpaired = _unpaired_ids(records)
    return Counter(_record_key(record) for record in records if record.phase == "started" and id(record) not in unpaired)


def _sweep_lifecycle_checkout(
    repo_root: Path,
    checkout: Path,
    records: list[ProfileInvocationRecord],
    *,
    threshold_hours: float,
    now: datetime,
    seen: Counter[_LifecycleKey],
    paired_somewhere: Counter[_LifecycleKey],
) -> list[SweepLifecycleEntry]:
    """Close one checkout's stale unpaired ``started`` records, then commit the closures once.

    An unpaired copy is acted on only beyond both counts: the copies some checkout
    holds paired (*paired_somewhere*, already closed there) and the copies earlier
    checkouts hold (*seen*, owned there, paired or not). This checkout then adds the
    copies it holds to *seen*.
    """
    reason = LIFECYCLE_ABANDONED_REASON.format(threshold=f"{threshold_hours:g}")
    entries: list[SweepLifecycleEntry] = []
    closures: list[tuple[SweepLifecycleEntry, Path]] = []
    unpaired = _unpaired_ids(records)
    held: Counter[_LifecycleKey] = Counter()
    for started in (record for record in records if record.phase == "started"):
        key = _record_key(started)
        held[key] += 1
        if id(started) not in unpaired or held[key] <= max(seen[key], paired_somewhere[key]):
            continue
        entry = _lifecycle_entry(started, now)
        entries.append(entry)
        if threshold_hours == 0 or (entry.age_hours is not None and entry.age_hours > threshold_hours):
            path = _close_lifecycle_record(checkout, started, entry, reason)
            if path is not None:
                closures.append((entry, path))
    seen |= held
    _commit_lifecycle_closures(repo_root, checkout, closures)
    return entries


def _lifecycle_entry(started: ProfileInvocationRecord, now: datetime) -> SweepLifecycleEntry:
    at = started.at if started.at.tzinfo is not None else started.at.replace(tzinfo=UTC)
    return SweepLifecycleEntry(
        canonical_action_id=started.canonical_action_id,
        mission_id=started.mission_id,
        wp_id=started.wp_id,
        agent=started.agent,
        started_at=at.isoformat(),
        age_hours=_age_hours(at.isoformat(), now),
    )


def _close_lifecycle_record(checkout: Path, started: ProfileInvocationRecord, entry: SweepLifecycleEntry, reason: str) -> Path | None:
    """Write the ``abandoned`` record; a failure is recorded on *entry* and the sweep continues."""
    try:
        path: Path = write_abandoned_completion(checkout, started=started, reason=reason)
    except Exception as exc:  # noqa: BLE001 - one unwritable record must not block the sweep
        entry.error = repr(exc)
        return None
    entry.action_taken = "closed_abandoned"
    entry.path = path.relative_to(checkout).as_posix()
    return path


def _commit_lifecycle_closures(repo_root: Path, checkout: Path, closures: list[tuple[SweepLifecycleEntry, Path]]) -> None:
    """Commit one checkout's new closure files once and stamp each entry with the outcome."""
    if not closures:
        return
    from specify_cli.invocation.executor import ProfileInvocationExecutor

    executor = ProfileInvocationExecutor(repo_root, record_root=checkout)
    note = _commit_note(executor.commit_lifecycle_closures([path for _entry, path in closures]))
    for entry, _path in closures:
        entry.commit = note
