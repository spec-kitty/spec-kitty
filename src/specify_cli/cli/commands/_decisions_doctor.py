"""``doctor decisions`` sibling — event-log reconciler for the Decision Moment
index (T012, mission local-write-safety-01M2ZPZD WP03, FR-004/FR-005).

Per the doctor per-subcommand-module convention (``_mission_state_doctor.py``
/ ``_review_cycle_reconcile_doctor.py``, #4813 soft-gated extraction SHAPE):
the ``decisions`` ``@app.command`` shell in ``doctor.py`` stays a thin
delegator; all diagnose/repair logic lives here.

Diagnoses (default, read-only) or repairs (``--repair``) divergence between
``decisions/index.json`` and the authoritative ``status.events.jsonl`` event
log, via the SAME canonical ``event -> IndexEntry`` fold the forward write
path (``decisions/service.py``) shares
(:mod:`specify_cli.decisions.index_fold`) — see
``kitty-specs/local-write-safety-01M2ZPZD/contracts/decisions-doctor.md``
("Single fold, no second reducer"). ``--repair`` runs under the SAME sidecar
lock the write path uses (T010, I8), so a concurrent open/resolve cannot race
a repair.

Repair never invents an entry absent from the log, and never drops a
log-backed entry: :func:`_rebuild_index_from_log` rebuilds the ENTIRE index
from every ``decision_point_id`` group found in the log, via
:func:`~specify_cli.decisions.index_fold.fold_events` — nothing in this
module hand-interprets an opened/resolved payload.

Review-feedback-2 (cycle 2, operator-directed fold-in): two follow-ups on the
otherwise-approved substance above.

- **Fold A** — the log-derived fold cannot faithfully reconstruct a
  slot_key-origin decision (the wire only carries one collapsed ``step_id``
  field, an upstream ``spec_kitty_events`` schema gap this WP does not own —
  see :func:`_is_unrecoverable_slot_key_origin`). ``--repair`` now detects
  that case from the PRE-repair on-disk entry and refuses to rewrite its
  attribution rather than silently mis-attributing it, warning loudly
  instead (:func:`_emit_lossy_attribution_warning`).
- **Fold B** — :func:`_repair` re-reads the event log AND the current index
  itself, INSIDE the sidecar lock, rather than rebuilding from
  ``_diagnose``'s pre-lock snapshot — closing the window in which a
  concurrent open/resolve landing between the diagnose read and the lock
  acquisition would be silently dropped.

- **Fold C** (#470 dead-symbol gate + robustness) — :func:`fold_events`
  (:mod:`specify_cli.decisions.index_fold`) raises
  :class:`~specify_cli.decisions.index_fold.FoldError` when a decision's
  grouped event envelopes violate the fold's invariants (no
  ``DecisionPointOpened``, more than one ``DecisionPointOpened``/
  ``DecisionPointResolved``, or an unrecognized event type) — a malformed
  on-disk event log, not a programmer error. Before this fold-in nothing in
  this module caught it, so one malformed decision_id's event group crashed
  the WHOLE ``--repair``/diagnose run with an uncaught exception, including
  every OTHER decision that was folding cleanly. :func:`_rebuild_index_from_log`
  now catches ``FoldError`` per decision_id (mirroring Fold A's
  keep-pre-repair-entry-unchanged shape): it keeps the PRE-repair on-disk
  entry unchanged if one exists, drops the decision_id from the rebuilt
  index if it does not, and records the decision_id in the returned
  malformed-fold list either way so the caller can report the condition
  cleanly instead of the doctor crashing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import typer

from kernel.locks import machine_file_lock
from mission_runtime import MissionArtifactKind, placement_seam
from spec_kitty_events.decisionpoint import (
    DECISION_POINT_OPENED,
    DECISION_POINT_RESOLVED,
)

from specify_cli.decisions import index_fold as _index_fold
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import DecisionIndex, IndexEntry

from ._doctor_shared import console

__all__ = [
    "run_decisions_reconciliation",
]

_EVENTS_FILENAME = "status.events.jsonl"
_LOCK_FILENAME = "index.json.lock"
#: Matches the write path's own acquire-wait bound (``decisions/service.py``).
_LOCK_ACQUIRE_TIMEOUT_S = 10.0

_DECISION_EVENT_TYPES = (DECISION_POINT_OPENED, DECISION_POINT_RESOLVED)


@dataclass
class DecisionsReconciliationReport:
    """One mission's decisions-index/event-log reconciliation result."""

    mission_slug: str
    log_decision_ids: list[str] = field(default_factory=list)
    index_decision_ids: list[str] = field(default_factory=list)
    missing_from_index: list[str] = field(default_factory=list)
    orphaned_in_index: list[str] = field(default_factory=list)
    repaired: bool = False
    #: Fold A (review-feedback-2, cycle 2): decision_ids ``--repair`` found
    #: PRE-repair evidence of a slot_key origin for (``step_id is None and
    #: slot_key is not None``) and therefore REFUSED to rewrite from the log
    #: -- the wire cannot faithfully reconstruct that distinction (see
    #: ``_rebuild_index_from_log``). Empty on every non-repair run.
    lossy_attribution: list[str] = field(default_factory=list)
    #: Fold C (#470 dead-symbol gate + robustness): decision_ids whose
    #: grouped event envelopes raised ``index_fold.FoldError`` -- a
    #: malformed event-log group, not a programmer error -- during
    #: ``--repair``. Empty on every non-repair run and on a run with no
    #: malformed groups.
    malformed_folds: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.missing_from_index and not self.orphaned_in_index


def _mission_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the COORD-partition ``kitty-specs/<mission_slug>/`` dir via the
    kind-aware placement seam — the SAME ``STATUS_STATE`` kind
    ``decisions/service.py`` and ``decisions/emit.py`` resolve, so this
    reconciler reads ``status.events.jsonl`` from the same directory the
    writers use.

    #4966 AC-D2 (WP03 residual): the decisions LEDGER (``decisions/index.json``
    / ``DM-<id>.md``) no longer resolves through this helper — see
    :func:`_ledger_dir` below. Only the event log stays COORD-routed here.
    """
    mission_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    return mission_dir


def _ledger_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the PRIMARY-partition dir holding the decision ledger content.

    #4966 AC-D2 (WP03 residual): must resolve the SAME dir
    ``decisions/service.py::_ledger_dir`` resolves (the ``PRIMARY_METADATA``
    kind), so this reconciler's repair target AND its sidecar lock path
    (:func:`_decisions_lock_path`) stay in lockstep with the forward write
    path — a concurrent open/resolve cannot race a repair only if both sides
    serialize against the SAME ``index.json.lock``.
    """
    ledger_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    return ledger_dir


def _events_path(mission_dir: Path) -> Path:
    return mission_dir / _EVENTS_FILENAME


def _decisions_lock_path(ledger_dir: Path) -> Path:
    return _store.decisions_dir(ledger_dir) / _LOCK_FILENAME


def _read_decision_events(events_path: Path) -> dict[str, list[dict]]:  # type: ignore[type-arg]
    """Group DecisionPointOpened/Resolved event envelopes by
    ``decision_point_id``, in on-disk (append) order."""
    grouped: dict[str, list[dict]] = {}  # type: ignore[type-arg]
    if not events_path.exists():
        return grouped
    for raw_line in events_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        event = json.loads(line)
        if event.get("event_type") not in _DECISION_EVENT_TYPES:
            continue
        payload = event.get("payload") or {}
        decision_id = payload.get("decision_point_id")
        if not decision_id:
            continue
        grouped.setdefault(decision_id, []).append(event)
    return grouped


def _is_unrecoverable_slot_key_origin(entry: IndexEntry) -> bool:
    """True when *entry* is PRE-repair on-disk evidence of a slot_key origin.

    Fold A (review-feedback-2, cycle 2): the wire event
    (``spec_kitty_events.decisionpoint``) only ever carries a single
    collapsed ``step_id`` field -- ``decisions/emit.py:213`` writes
    ``entry.step_id if entry.step_id is not None else entry.slot_key`` onto
    it before emission. Folding such a decision's events therefore
    reconstructs ``step_id=<the original slot_key value>, slot_key=None`` --
    silently different from the original. The ONLY place that distinction
    still survives is a pre-repair on-disk ``IndexEntry`` that was built by
    the forward write path (which preserves the caller's own step_id/slot_key
    split losslessly, see ``index_fold.build_opened_entry``) -- this entry's
    ``step_id is None and slot_key is not None`` is exactly that surviving
    evidence.
    # Follow-up: the real fix belongs upstream in ``spec_kitty_events`` (carry
    # step_id AND slot_key distinctly on the wire) -- a client-repo boundary
    # this WP does not own. Once fixed there, this refuse-to-rewrite path
    # can be dropped for an unconditional rebuild.
    """
    return entry.step_id is None and entry.slot_key is not None


def _rebuild_index_from_log(
    current: DecisionIndex,
    grouped: dict[str, list[dict]],  # type: ignore[type-arg]
) -> tuple[DecisionIndex, list[str], list[str]]:
    """Rebuild the FULL index from the log via the T008 canonical fold.

    Fold A (review-feedback-2, cycle 2): for each decision_id, if *current*
    (the PRE-repair on-disk index) already holds an entry that is
    unrecoverable slot_key-origin evidence
    (:func:`_is_unrecoverable_slot_key_origin`), that entry is KEPT
    UNCHANGED instead of being rebuilt from the log -- membership is
    preserved (the decision stays in the index) but its attribution, which
    the log cannot prove, is never silently fabricated. The decision_id is
    recorded in the returned refused-list so the caller can warn loudly. A
    decision with NO pre-repair on-disk copy at all cannot be checked this
    way (the same undetectable case the module docstring documents) and
    folds from the log as before.

    Fold C (#470 dead-symbol gate + robustness): if folding a decision_id's
    event group instead raises ``index_fold.FoldError`` (a malformed group
    -- see the module docstring), that one decision_id is isolated from the
    rest of the run: its PRE-repair on-disk entry is kept unchanged if one
    exists (same shape as Fold A), or it is simply omitted from the rebuilt
    index if there is no pre-repair copy to fall back to. Either way the
    decision_id is recorded in the returned malformed-list so the caller can
    report the condition cleanly -- a malformed group for ONE decision must
    never crash the fold for every other, cleanly-folding decision in the
    same run.

    ``mission_id`` is taken from the rebuilt entries themselves (every
    opened event carries it) rather than re-reading ``meta.json`` — the log
    alone is authoritative here. Falls back to *current*'s ``mission_id``
    only for the degenerate empty-log case.
    """
    current_by_id = {e.decision_id: e for e in current.entries}
    lossy_ids: list[str] = []
    malformed_ids: list[str] = []
    rebuilt_entries: list[IndexEntry] = []
    for decision_id, events in sorted(grouped.items()):
        existing = current_by_id.get(decision_id)
        if existing is not None and _is_unrecoverable_slot_key_origin(existing):
            rebuilt_entries.append(existing)
            lossy_ids.append(decision_id)
            continue
        try:
            rebuilt_entries.append(_index_fold.fold_events(events))
        except _index_fold.FoldError:
            malformed_ids.append(decision_id)
            if existing is not None:
                rebuilt_entries.append(existing)
    mission_id = rebuilt_entries[0].mission_id if rebuilt_entries else current.mission_id
    return DecisionIndex(mission_id=mission_id, entries=tuple(rebuilt_entries)), lossy_ids, malformed_ids


def _diagnose(events_dir: Path, ledger_dir: Path, mission_slug: str) -> tuple[DecisionsReconciliationReport, dict[str, list[dict]]]:  # type: ignore[type-arg]
    """Diagnose log/index divergence.

    ``events_dir`` (COORD/``STATUS_STATE``) and ``ledger_dir`` (PRIMARY/
    ``PRIMARY_METADATA``) are resolved separately (#4966 AC-D2) -- the event
    log and the ledger content no longer share one directory.
    """
    grouped = _read_decision_events(_events_path(events_dir))
    index = _store.load_index(ledger_dir)
    log_ids = set(grouped)
    index_ids = {e.decision_id for e in index.entries}
    report = DecisionsReconciliationReport(
        mission_slug=mission_slug,
        log_decision_ids=sorted(log_ids),
        index_decision_ids=sorted(index_ids),
        missing_from_index=sorted(log_ids - index_ids),
        orphaned_in_index=sorted(index_ids - log_ids),
    )
    return report, grouped


def _repair(events_dir: Path, ledger_dir: Path) -> tuple[list[str], list[str]]:
    """Rebuild ``index.json`` from a FRESH in-lock read of the event log,
    under the sidecar lock (I8: the SAME lock the write path uses, T010) — a
    concurrent open/resolve cannot race a repair, and a repair cannot race a
    concurrent open/resolve.

    Fold B (review-feedback-2, cycle 2): ``_diagnose``'s log/index reads run
    BEFORE this lock is acquired, so by the time this acquisition succeeds
    that snapshot may already be stale — a concurrent open/resolve landing
    in the window between the diagnose read and the lock acquisition would
    be silently dropped by a rebuild sourced from it. This function
    therefore re-reads BOTH the event log and the current index itself,
    INSIDE the lock, rather than accepting either as a pre-lock argument.

    ``events_dir`` (COORD) and ``ledger_dir`` (PRIMARY, #4966 AC-D2) are
    resolved separately by the caller; the lock is taken against
    ``ledger_dir`` — the SAME dir ``decisions/service.py`` locks against.

    Returns ``(lossy_ids, malformed_ids)``: the decision_ids
    :func:`_rebuild_index_from_log` refused to rewrite (Fold A) and the
    decision_ids whose event group raised ``FoldError`` (Fold C), so the
    caller can report both conditions loudly instead of crashing.
    """
    lock_path = _decisions_lock_path(ledger_dir)
    with machine_file_lock(lock_path, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):
        grouped = _read_decision_events(_events_path(events_dir))
        current = _store.load_index(ledger_dir)
        rebuilt, lossy_ids, malformed_ids = _rebuild_index_from_log(current, grouped)
        _store.save_index(ledger_dir, rebuilt)
        return lossy_ids, malformed_ids


def _emit_lossy_attribution_warning(report: DecisionsReconciliationReport) -> None:
    """Fold A (review-feedback-2, cycle 2): warn loudly when ``--repair``
    refused to rewrite a decision's attribution rather than fabricate it."""
    if not report.lossy_attribution:
        return
    console.print(
        f"  [red]refused to rewrite[/red] ({len(report.lossy_attribution)}) decision(s) with "
        "unrecoverable slot_key attribution -- the event-log wire schema "
        "(spec_kitty_events.decisionpoint) only carries a single collapsed "
        "step_id field, so a slot_key-origin decision cannot be faithfully "
        f"rebuilt from the log alone; kept pre-repair attribution unchanged: {', '.join(report.lossy_attribution)}"
    )


def _emit_malformed_fold_warning(report: DecisionsReconciliationReport) -> None:
    """Fold C (#470 dead-symbol gate + robustness): report -- rather than
    crash on -- a decision_id whose event group could not be folded."""
    if not report.malformed_folds:
        return
    console.print(
        f"  [red]could not fold[/red] ({len(report.malformed_folds)}) decision(s) from a malformed event-log group -- "
        "the DecisionPointOpened/Resolved envelopes for these decision_ids do not satisfy the canonical fold's "
        "invariants (index_fold.FoldError); kept the pre-repair index entry unchanged where one existed, otherwise "
        f"omitted the decision_id from the rebuilt index: {', '.join(report.malformed_folds)}"
    )


def _emit_human(report: DecisionsReconciliationReport) -> None:
    if report.clean:
        suffix = " (repaired)" if report.repaired else ""
        console.print(f"[green]ok[/green]: {report.mission_slug} -- decisions index matches the event log ({len(report.log_decision_ids)} decision(s)){suffix}.")
    else:
        console.print(f"[yellow]diverged[/yellow]: {report.mission_slug}")
        if report.missing_from_index:
            console.print(f"  missing from index ({len(report.missing_from_index)}): {', '.join(report.missing_from_index)}")
        if report.orphaned_in_index:
            console.print(f"  orphaned in index, no backing event ({len(report.orphaned_in_index)}): {', '.join(report.orphaned_in_index)}")
    _emit_lossy_attribution_warning(report)
    _emit_malformed_fold_warning(report)


def _emit_json(report: DecisionsReconciliationReport) -> None:
    payload = {
        "mission_slug": report.mission_slug,
        "clean": report.clean,
        "log_decision_ids": report.log_decision_ids,
        "index_decision_ids": report.index_decision_ids,
        "missing_from_index": report.missing_from_index,
        "orphaned_in_index": report.orphaned_in_index,
        "repaired": report.repaired,
        "lossy_attribution": report.lossy_attribution,
        "malformed_folds": report.malformed_folds,
    }
    console.print_json(json.dumps(payload, indent=2))


def run_decisions_reconciliation(
    repo_root: Path,
    mission: str,
    *,
    json_output: bool,
    repair: bool,
) -> None:
    """Entry point for ``doctor decisions`` (T012,
    ``contracts/decisions-doctor.md``).

    Diagnose (default): read-only report of log/index divergence — entries
    in the log missing from the index, and index entries with no backing
    event.

    ``--repair``: rebuild ``index.json`` from the log via the canonical fold,
    under the sidecar lock. A no-op (no write) when the log and index
    already agree.

    Informational only, matching the ``doctor review-cycle-reconcile``
    precedent: always exits 0.
    """
    # Function-local (H2/I-6 precedent, ``_review_cycle_reconcile_doctor.py``):
    # avoids a doctor <-> selector-resolution module-load cycle.
    from specify_cli.cli.selector_resolution import (
        resolve_mission_dir_with_bare_modern_fold,
    )

    mission_root = resolve_mission_dir_with_bare_modern_fold(mission, repo_root, json_mode=json_output)
    mission_slug = mission_root.name
    # #4966 AC-D2: the event log (COORD) and the ledger content (PRIMARY)
    # resolve to separate dirs — see ``_mission_dir`` / ``_ledger_dir``.
    events_dir = _mission_dir(repo_root, mission_slug)
    ledger_dir = _ledger_dir(repo_root, mission_slug)

    report, _grouped = _diagnose(events_dir, ledger_dir, mission_slug)

    if repair and not report.clean:
        lossy_ids, malformed_ids = _repair(events_dir, ledger_dir)
        report, _grouped = _diagnose(events_dir, ledger_dir, mission_slug)
        report.repaired = True
        report.lossy_attribution = sorted(lossy_ids)
        report.malformed_folds = sorted(malformed_ids)

    if json_output:
        _emit_json(report)
    else:
        _emit_human(report)

    raise typer.Exit(0)
