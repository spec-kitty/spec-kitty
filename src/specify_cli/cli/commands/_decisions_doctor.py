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
from typing import Any

import typer

from kernel.locks import machine_file_lock
from mission_runtime import MissionArtifactKind, placement_seam
from spec_kitty_events.decisionpoint import (
    DECISION_POINT_OPENED,
    DECISION_POINT_RESOLVED,
)

from specify_cli.decisions import fork as _fork
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
    #: malformed event-log group, not a programmer error. #4919:
    #: unlike Fold A/lossy_attribution, this is now populated on EVERY run
    #: (read-only diagnose included, not just ``--repair``) -- :func:`_diagnose`
    #: runs the canonical fold itself so a genuinely unfoldable decision is
    #: reported (``clean: false``) even when no repair is requested.
    malformed_folds: list[str] = field(default_factory=list)
    #: #4919: decision_ids present in BOTH the log and the
    #: index whose event-log-folded status disagrees with the index's
    #: on-disk status -- a stale index entry that a clean id-set comparison
    #: alone would miss (e.g. the index still says ``deferred`` after a
    #: ``resolve`` landed in the log). Each item is
    #: ``{"decision_id", "index_status", "folded_status"}``. Empty on a
    #: healthy corpus.
    status_mismatch: list[dict[str, str]] = field(default_factory=list)
    #: WP17 (FR-010/FR-010a/FR-009c, #5023): the two-surface fork/ledger-home
    #: report, computed only when ``repo_root`` is supplied to ``_diagnose``
    #: (``None`` for the back-compat no-``repo_root`` call shape driven
    #: directly by ``tests/status/test_authoritative_non_lane_registry_4897.py``).
    fork_report: _fork.DecisionsForkReport | None = field(default=None, repr=False)
    #: New WP17 finding codes (``DECISION_LOG_FORKED`` /
    #: ``DECISION_LEDGER_ONLY_ON_COORDINATION``), additive to the existing
    #: per-field report shape.
    findings: list[str] = field(default_factory=list)
    #: WP17: ``--repair`` copied a coordination-only ledger into the PRIMARY
    #: ledger dir (additive, no commit -- FR-009b).
    ledger_copied: bool = False

    @property
    def clean(self) -> bool:
        base = not self.missing_from_index and not self.orphaned_in_index and not self.malformed_folds and not self.status_mismatch
        return base and not self.findings


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
    ``decisions/service.py::_ledger_dir`` resolves (the ``DECISION_LEDGER``
    kind), so this reconciler's repair target AND its sidecar lock path
    (:func:`_decisions_lock_path`) stay in lockstep with the forward write
    path — a concurrent open/resolve cannot race a repair only if both sides
    serialize against the SAME ``index.json.lock``.
    """
    ledger_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.DECISION_LEDGER)
    return ledger_dir


def _resolve_events_dir_for_doctor(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the COORD/``STATUS_STATE`` events dir for the READ-ONLY doctor path.

    WP17 (US4.1, #5023): degrades to a deliberately nonexistent placeholder
    when the coordination worktree is genuinely unmaterialized/the branch is
    deleted (:class:`~specify_cli.missions._read_path_resolver
    .StatusReadPathNotFound`, e.g. a fresh clone with no coordination
    worktree) -- there is nothing live to read there yet, so the event log
    degrades to empty exactly as an empty on-disk directory would, rather
    than crashing a read-only diagnose. :func:`~specify_cli.decisions.fork
    .detect_decision_forks` recovers the coordination side's content
    separately via its own worktree-or-ref read, so the overall fork report
    stays accurate even when this single-surface legacy read degrades.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        return _mission_dir(repo_root, mission_slug)
    except StatusReadPathNotFound:
        return repo_root / f".spec-kitty-doctor-unmaterialized-coord~{mission_slug}"


def _events_path(mission_dir: Path) -> Path:
    return mission_dir / _EVENTS_FILENAME


def _decisions_lock_path(ledger_dir: Path) -> Path:
    return Path(_store.decisions_dir(ledger_dir) / _LOCK_FILENAME)


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


#: ``IndexEntry`` fields the log cannot reproduce faithfully, so they are
#: never evidence that an on-disk entry disagrees with the fold:
#: ``summary_json`` is never emitted; ``slot_key`` is collapsed into the
#: wire's single ``step_id``; ``rationale`` and ``resolved_by`` are
#: normalised on emission (``None`` -> ``"no rationale"`` / the acting
#: actor, ``decisions/emit.py``).
_NOT_WIRE_FAITHFUL_FIELDS: frozenset[str] = frozenset({"summary_json", "slot_key", "rationale", "resolved_by"})


def _agrees_on_wire(existing: IndexEntry, folded: IndexEntry) -> bool:
    """True when *existing* matches *folded* on every wire-faithful field."""
    excluded = set(_NOT_WIRE_FAITHFUL_FIELDS)
    if _is_unrecoverable_slot_key_origin(existing):
        excluded.add("step_id")
    existing_wire: dict[str, Any] = existing.model_dump(exclude=excluded)
    folded_wire: dict[str, Any] = folded.model_dump(exclude=excluded)
    return existing_wire == folded_wire


def _reconcile_entry(existing: IndexEntry | None, folded: IndexEntry) -> IndexEntry:
    """The entry ``--repair`` writes for one log-backed decision (#4919).

    - No PRE-repair entry: the fold stands.
    - The PRE-repair entry agrees with the fold on every wire-faithful field
      (:func:`_agrees_on_wire`): it is kept VERBATIM -- a repair triggered by
      some other decision must not rewrite a healthy entry.
    - Otherwise (e.g. a stale status): the wire fields come from the fold,
      while the fields the wire never carries are carried from the PRE-repair
      entry -- ``summary_json`` always, and the ``step_id``/``slot_key``
      attribution for an unrecoverable slot_key-origin entry
      (:func:`_is_unrecoverable_slot_key_origin`) or a ``slot_key`` beside an
      agreeing ``step_id``.

    Before this, the rebuild wrote every entry straight from the fold, so a
    repair of ONE stale status erased every other decision's
    ``summary_json`` (widen-review provenance) and exited 0.
    """
    if existing is None:
        return folded
    if _agrees_on_wire(existing, folded):
        return existing
    carried: dict[str, Any] = {"summary_json": existing.summary_json}
    if _is_unrecoverable_slot_key_origin(existing):
        carried["step_id"] = existing.step_id
        carried["slot_key"] = existing.slot_key
    elif existing.step_id == folded.step_id:
        carried["slot_key"] = existing.slot_key
    return folded.model_copy(update=carried)


def _rebuild_index_from_log(
    current: DecisionIndex,
    grouped: dict[str, list[dict]],  # type: ignore[type-arg]
) -> tuple[DecisionIndex, list[str], list[str]]:
    """Rebuild the FULL index from the log via the T008 canonical fold.

    Every folded entry goes through :func:`_reconcile_entry`: a PRE-repair entry that already agrees with the fold on the wire is
    kept verbatim; a disagreeing one takes the wire fields from the fold and
    carries the fields the wire never holds -- ``summary_json``
    (widen-review provenance) and the step_id/slot_key attribution
    split -- from the PRE-repair entry. Before this, a repair triggered by
    ONE stale status rebuilt every entry from the log and erased every other
    decision's ``summary_json``, exit 0.

    Fold A (review-feedback-2, cycle 2): for each
    decision_id, if *current* (the PRE-repair on-disk index) already holds
    an entry that is unrecoverable slot_key-origin evidence
    (:func:`_is_unrecoverable_slot_key_origin`), its attribution
    (``step_id``/``slot_key``) is KEPT from that entry -- the log cannot
    prove it, so it is never silently fabricated -- while its status and
    terminal fields, which ARE on the wire, still come from the fold (a
    stale status is repaired). The decision_id is recorded in the returned
    refused-list so the caller can warn loudly. A decision with NO
    pre-repair on-disk copy at all cannot be checked this way (the same
    undetectable case the module docstring documents) and folds from the
    log as before.

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
        try:
            folded = _index_fold.fold_events(events)
        except _index_fold.FoldError:
            malformed_ids.append(decision_id)
            if existing is not None:
                rebuilt_entries.append(existing)
            continue
        if existing is not None and _is_unrecoverable_slot_key_origin(existing):
            lossy_ids.append(decision_id)
        rebuilt_entries.append(_reconcile_entry(existing, folded))
    mission_id = rebuilt_entries[0].mission_id if rebuilt_entries else current.mission_id
    return DecisionIndex(mission_id=mission_id, entries=tuple(rebuilt_entries)), lossy_ids, malformed_ids


def _fold_diagnostics(
    grouped: dict[str, list[dict[str, Any]]],
    index_by_id: dict[str, IndexEntry],
) -> tuple[list[str], list[dict[str, str]]]:
    """Run the canonical fold over every log-backed decision_id and report
    what the id-set comparison alone cannot see (#4919):

    - ``malformed_folds``: decision_ids whose grouped event envelopes raise
      ``index_fold.FoldError`` (e.g. a genuinely unfoldable combination of
      ``DecisionPointResolved`` outcomes) -- reported on EVERY run, not just
      ``--repair``, so a read-only ``doctor decisions`` surfaces the problem.
    - ``status_mismatch``: decision_ids present in BOTH the log and the
      index whose folded status disagrees with the on-disk index status (a
      stale entry -- e.g. the index still says ``deferred`` after a
      ``resolve`` landed in the log).

    A decision missing from the index entirely (``missing_from_index``) is
    folded here too (to catch malformed folds regardless of index
    membership) but has no index entry to compare a status against.

    A decision whose PRE-repair on-disk entry is unrecoverable slot_key-origin
    evidence (:func:`_is_unrecoverable_slot_key_origin`) is compared too:
    the wire collapses its step_id/slot_key attribution, but ``status`` IS
    on the wire, so a stale status is reported -- and
    ``--repair`` fixes the status while keeping the attribution
    (:func:`_reconcile_entry`).
    """
    malformed_ids: list[str] = []
    status_mismatch: list[dict[str, str]] = []
    for decision_id in sorted(grouped):
        existing = index_by_id.get(decision_id)
        try:
            folded = _index_fold.fold_events(grouped[decision_id])
        except _index_fold.FoldError:
            malformed_ids.append(decision_id)
            continue
        if existing is not None and existing.status != folded.status:
            status_mismatch.append(
                {
                    "decision_id": decision_id,
                    "index_status": existing.status.value,
                    "folded_status": folded.status.value,
                }
            )
    return malformed_ids, status_mismatch


def _all_decision_ids_from_fork_report(fork_report: _fork.DecisionsForkReport) -> set[str]:
    """Union of every decision id found on EITHER surface, ANY stream (FR-010 rule 1).

    An index entry is orphaned only when absent from this whole union, not
    merely from one surface's ``status.events.jsonl`` (the pre-WP17 rule).
    """
    ids: set[str] = set()
    for finding in fork_report.streams:
        ids |= set(finding.decisions_only_on_primary)
        ids |= set(finding.decisions_only_on_coordination)
        ids |= set(finding.decisions_on_both)
    return ids


def _diagnose(
    events_dir: Path,
    ledger_dir: Path,
    mission_slug: str,
    *,
    repo_root: Path | None = None,
) -> tuple[DecisionsReconciliationReport, dict[str, list[dict]]]:  # type: ignore[type-arg]
    """Diagnose log/index divergence.

    ``events_dir`` (COORD/``STATUS_STATE``) and ``ledger_dir`` (PRIMARY/
    ``DECISION_LEDGER``) are resolved separately (#4966 AC-D2) -- the event
    log and the ledger content no longer share one directory.

    #4919: beyond the id-set comparison (missing/orphaned),
    this now ALSO runs the canonical fold per decision_id
    (:func:`_fold_diagnostics`) so a genuinely unfoldable decision or a stale
    index status is caught by the read-only path too, not just ``--repair``.

    WP17 (FR-010/FR-010a/FR-009c, #5023): when *repo_root* is supplied, this
    additionally runs the two-surface :func:`~specify_cli.decisions.fork
    .detect_decision_forks` comparison, widens the orphan rule to the union
    of every decision id on EITHER surface (rule 1), and records the new
    ``DECISION_LOG_FORKED`` / ``DECISION_LEDGER_ONLY_ON_COORDINATION``
    findings. ``repo_root=None`` (the default) reproduces the pre-WP17
    single-surface behaviour byte-for-byte -- the shape
    ``tests/status/test_authoritative_non_lane_registry_4897.py`` drives
    directly.
    """
    grouped = _read_decision_events(_events_path(events_dir))
    index = _store.load_index(ledger_dir)
    log_ids = set(grouped)
    index_ids = {e.decision_id for e in index.entries}
    index_by_id = {e.decision_id: e for e in index.entries}

    malformed_ids, status_mismatch = _fold_diagnostics(grouped, index_by_id)

    orphan_universe = set(log_ids)
    fork_report: _fork.DecisionsForkReport | None = None
    findings: list[str] = []
    if repo_root is not None:
        fork_report = _fork.detect_decision_forks(repo_root, mission_slug)
        orphan_universe |= _all_decision_ids_from_fork_report(fork_report)
        if fork_report.forked:
            findings.append("DECISION_LOG_FORKED")
        if _fork.ledger_is_coordination_only(fork_report.ledger):
            findings.append("DECISION_LEDGER_ONLY_ON_COORDINATION")

    report = DecisionsReconciliationReport(
        mission_slug=mission_slug,
        log_decision_ids=sorted(log_ids),
        index_decision_ids=sorted(index_ids),
        missing_from_index=sorted(log_ids - index_ids),
        orphaned_in_index=sorted(index_ids - orphan_universe),
        malformed_folds=sorted(malformed_ids),
        status_mismatch=status_mismatch,
        fork_report=fork_report,
        findings=findings,
    )
    return report, grouped


def _retain_event_backed_entries(
    current: DecisionIndex,
    rebuilt: DecisionIndex,
    event_backed_ids: set[str],
) -> DecisionIndex:
    """Keep index entries whose events still exist on either surface.

    ``_rebuild_index_from_log`` folds only the coordination ``status.events.jsonl``.
    A prefix or single-home stream, and the empty placeholder used when the
    coordination worktree is unmaterialized, does not contain every event-backed
    id. Those entries must survive ``--repair`` (FR-011). A genuine orphan, absent
    from *event_backed_ids*, is still dropped.
    """
    rebuilt_ids = {entry.decision_id for entry in rebuilt.entries}
    retained = [entry for entry in current.entries if entry.decision_id in event_backed_ids and entry.decision_id not in rebuilt_ids]
    if not retained:
        return rebuilt
    mission_id = rebuilt.mission_id or current.mission_id
    return DecisionIndex(mission_id=mission_id, entries=tuple(rebuilt.entries) + tuple(retained))


def _repair(
    events_dir: Path,
    ledger_dir: Path,
    *,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
) -> tuple[list[str], list[str]]:
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
        if repo_root is not None and mission_slug is not None:
            fork_report = _fork.detect_decision_forks(repo_root, mission_slug)
            rebuilt = _retain_event_backed_entries(current, rebuilt, _all_decision_ids_from_fork_report(fork_report))
        _store.save_index(ledger_dir, rebuilt)
        return lossy_ids, malformed_ids


def _copy_coordination_only_ledger(repo_root: Path, mission_slug: str, ledger_dir: Path) -> None:
    """FR-009c / contract rule 4: additive-only copy of a coordination-only ledger.

    Reads ``decisions/index.json`` + ``DM-*.md`` from the COORDINATION
    BRANCH TIP (never the worktree -- the branch is what teardown destroys;
    T092 step 3) and copies them into the PRIMARY ledger dir, under the SAME
    sidecar lock the write path and ``_repair`` use. Index entries are
    merged with the single shared :func:`union_decision_index
    <specify_cli.consolidation.drivers.union_decision_index>` (P-M6 -- no
    second union). Never overwrites an existing PRIMARY entry/file. Creates
    NO commit (FR-009b): the existing PRIMARY committers (``spec-commit`` /
    ``accept``) commit the copy.
    """
    from specify_cli.consolidation.drivers import union_decision_index

    index_document, dm_contents = _fork.read_coordination_ledger_raw(repo_root, mission_slug)
    lock_path = _decisions_lock_path(ledger_dir)
    with machine_file_lock(lock_path, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):
        if index_document is not None:
            current_raw = _store.load_index(ledger_dir).model_dump(mode="json")
            merged_raw = union_decision_index(current_raw, index_document)
            merged = DecisionIndex.model_validate(merged_raw)
            _store.save_index(ledger_dir, merged)
        decisions_path = _store.decisions_dir(ledger_dir)
        decisions_path.mkdir(parents=True, exist_ok=True)
        for name, content in dm_contents.items():
            dest = decisions_path / name
            if not dest.exists():
                dest.write_text(content, encoding="utf-8")


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


def _malformed_fold_remedy_text(report: DecisionsReconciliationReport) -> str | None:
    """#4919: the ONE remedy
    sentence for a malformed-fold refusal -- "left in place" plus how to
    inspect the decision further. Shared by :func:`_emit_malformed_fold_warning`
    (human mode, embedded in the printed line) and :func:`_emit_json` (its own
    ``remedy`` field) so both surfaces carry identical remedy text, never two
    independently-worded copies. ``None`` when there is nothing to remedy."""
    if not report.malformed_folds:
        return None
    return (
        "left in place: the pre-repair index entry is kept unchanged where one existed, "
        "otherwise the decision_id stays out of the index (never invented). Inspect with "
        f"'spec-kitty agent decision list --mission {report.mission_slug}' and the raw event log "
        "(status.events.jsonl)."
    )


def _emit_malformed_fold_warning(report: DecisionsReconciliationReport) -> None:
    """Fold C (#470 dead-symbol gate + robustness) / #4919:
    report -- rather than crash on -- a decision_id whose event group could
    not be folded. Names each id and appends the shared remedy text
    ("left in place" plus how to inspect further)."""
    remedy = _malformed_fold_remedy_text(report)
    if remedy is None:
        return
    console.print(
        f"  [red]could not fold[/red] ({len(report.malformed_folds)}) decision(s) from a malformed event-log group -- "
        "the DecisionPointOpened/Resolved envelopes for these decision_ids do not satisfy the canonical fold's "
        f"invariants (index_fold.FoldError); {remedy} Affected: {', '.join(report.malformed_folds)}"
    )


def _emit_status_mismatch_warning(report: DecisionsReconciliationReport) -> None:
    """#4919: report a stale index status -- the id set
    agrees with the log, but the recorded status does not (e.g. the index
    still says ``deferred`` after a ``resolve`` landed in the log)."""
    if not report.status_mismatch:
        return
    detail = ", ".join(f"{item['decision_id']} (index={item['index_status']}, log={item['folded_status']})" for item in report.status_mismatch)
    console.print(f"  [red]stale status[/red] ({len(report.status_mismatch)}) index entry disagrees with the folded event log: {detail}")


def _surface_log_to_json(log: _fork.SurfaceLog | None) -> dict[str, object] | None:
    if log is None:
        return None
    return {"source": log.source, "ref": log.ref, "path": log.path, "event_count": len(log.event_ids)}


def _stream_finding_to_json(finding: _fork.StreamForkFinding) -> dict[str, object]:
    return {
        "stream": finding.stream,
        "state": finding.state,
        "primary": _surface_log_to_json(finding.primary),
        "coordination": _surface_log_to_json(finding.coordination),
        "decisions_only_on_primary": list(finding.decisions_only_on_primary),
        "decisions_only_on_coordination": list(finding.decisions_only_on_coordination),
        "decisions_on_both": list(finding.decisions_on_both),
    }


def _ledger_finding_to_json(ledger: _fork.LedgerHomeFinding) -> dict[str, object]:
    return {
        "state": ledger.state,
        "entries_only_on_coordination": list(ledger.entries_only_on_coordination),
        "dm_files_only_on_coordination": list(ledger.dm_files_only_on_coordination),
    }


def _emit_fork_report_human(fork_report: _fork.DecisionsForkReport) -> None:
    """WP17: print one line per forked stream, the ledger home, then the
    human-readable (never executed, C-003) reconcile steps."""
    for finding in fork_report.streams:
        if finding.state == "forked":
            primary_count = len(finding.primary.event_ids) if finding.primary else 0
            coord_count = len(finding.coordination.event_ids) if finding.coordination else 0
            console.print(f"  [red]{finding.stream}[/red]: forked (primary={primary_count} event(s), coordination={coord_count} event(s))")
    if _fork.ledger_is_coordination_only(fork_report.ledger):
        console.print(
            f"  [red]decisions ledger[/red]: only on the coordination branch "
            f"({len(fork_report.ledger.entries_only_on_coordination)} entr(ies), "
            f"{len(fork_report.ledger.dm_files_only_on_coordination)} DM file(s))"
        )
    for step in fork_report.reconcile_steps:
        console.print(f"  [yellow]reconcile:[/yellow] {step}")


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
    if report.fork_report is not None:
        _emit_fork_report_human(report.fork_report)
    if report.ledger_copied:
        console.print(
            f"  [green]copied[/green] decisions ledger from the coordination branch -- commit with "
            f'`spec-kitty spec-commit -m "..." kitty-specs/{report.mission_slug}/decisions/` (or '
            "`spec-kitty accept`); no commit was created."
        )
    _emit_lossy_attribution_warning(report)
    _emit_malformed_fold_warning(report)
    _emit_status_mismatch_warning(report)


def _emit_json(report: DecisionsReconciliationReport) -> None:
    """#4919: when
    ``malformed_folds`` is non-empty, the single JSON document carries a
    ``remedy`` field (:func:`_malformed_fold_remedy_text`) -- the SAME
    "left in place" + inspection-pointer text the human-mode warning prints
    -- so a ``--json`` refusal is not silently poorer than the human one.

    WP17: additive keys only (``forked``, ``streams``, ``ledger``,
    ``reconcile_steps``, ``findings``, ``ledger_copied``) -- present only
    when a fork report was computed (``repo_root`` was supplied).
    """
    payload: dict[str, object] = {
        "mission_slug": report.mission_slug,
        "clean": report.clean,
        "log_decision_ids": report.log_decision_ids,
        "index_decision_ids": report.index_decision_ids,
        "missing_from_index": report.missing_from_index,
        "orphaned_in_index": report.orphaned_in_index,
        "repaired": report.repaired,
        "lossy_attribution": report.lossy_attribution,
        "malformed_folds": report.malformed_folds,
        "status_mismatch": report.status_mismatch,
        "remedy": _malformed_fold_remedy_text(report),
        "findings": report.findings,
        "ledger_copied": report.ledger_copied,
    }
    if report.fork_report is not None:
        payload["forked"] = report.fork_report.forked
        payload["streams"] = [_stream_finding_to_json(s) for s in report.fork_report.streams]
        payload["ledger"] = _ledger_finding_to_json(report.fork_report.ledger)
        payload["reconcile_steps"] = list(report.fork_report.reconcile_steps)
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
    in the log missing from the index, index entries with no backing event,
    a decision_id whose event group cannot be folded at all
    (``malformed_folds``), and an index entry whose status disagrees with
    the folded log (``status_mismatch``). Always exits 0, even when the
    report is not clean (report-only, matching the ``doctor
    review-cycle-reconcile`` precedent).

    ``--repair``: rebuild ``index.json`` from the log via the canonical fold,
    under the sidecar lock. A no-op (no write) when the log and index
    already agree. #4919: repair never drops a decision it cannot
    fold -- a malformed decision's pre-repair index entry is left unchanged
    (or stays absent if it never had one) and named in ``malformed_folds``.
    When any decision remains malformed after a repair attempt, the command
    reports it (exactly one report — human or JSON, never a second document)
    and then exits **1**; it exits 0 only when every decision the repair
    touched folds cleanly.
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
    events_dir = _resolve_events_dir_for_doctor(repo_root, mission_slug)
    ledger_dir = _ledger_dir(repo_root, mission_slug)

    report, _grouped = _diagnose(events_dir, ledger_dir, mission_slug, repo_root=repo_root)

    if repair and not report.clean:
        forked = report.fork_report is not None and report.fork_report.forked
        ledger_only_coord = report.fork_report is not None and _fork.ledger_is_coordination_only(report.fork_report.ledger)
        if forked:
            # C-003: a forked stream is NEVER auto-merged or re-sequenced --
            # no index rewrite for the forked decisions; the reconcile steps
            # are printed instead (contract rule 2, US4.3).
            lossy_ids: list[str] = []
            malformed_ids = list(report.malformed_folds)
        else:
            # Positive control (US4.4): an unforked Mission still repairs a
            # genuine orphan exactly as before.
            lossy_ids, malformed_ids = _repair(events_dir, ledger_dir, repo_root=repo_root, mission_slug=mission_slug)
        if ledger_only_coord:
            # FR-009c / contract rule 4: additive-only, independent of the
            # stream-fork branch above (a coordination-only ledger can exist
            # on an otherwise unforked Mission, e.g. NFR-002 fixture (d)).
            _copy_coordination_only_ledger(repo_root, mission_slug, ledger_dir)
        report, _grouped = _diagnose(events_dir, ledger_dir, mission_slug, repo_root=repo_root)
        report.repaired = True
        report.lossy_attribution = sorted(lossy_ids)
        report.malformed_folds = sorted(malformed_ids)
        report.ledger_copied = ledger_only_coord

    if json_output:
        _emit_json(report)
    else:
        _emit_human(report)

    # #4919 / WP17: --repair exits non-zero when it could not reconcile
    # every decision -- a malformed decision that remains after the rebuild
    # attempt, or a forked stream (C-003: never auto-merged, so it is
    # reported and refused here rather than the command silently claiming
    # success). The read-only diagnose path (repair=False) always exits 0
    # (report-only) -- a forked/coordination-only-ledger Mission is proven
    # "not clean" separately by ``decision verify`` (FR-010a).
    if repair and report.fork_report is not None and report.fork_report.forked:
        raise typer.Exit(1)
    if repair and report.malformed_folds:
        raise typer.Exit(1)

    raise typer.Exit(0)
