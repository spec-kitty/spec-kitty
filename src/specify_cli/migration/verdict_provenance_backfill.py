"""Verdict-provenance backfill + provenance gate (FR-012, SC-008).

Populates the event authority (``status.events.jsonl``) for **every** existing
mission before any verdict reader flips to being event-sourced only. Scope is
strictly:

1. **Backfill** (:func:`backfill_verdict_provenance`): reduce each WP's
   terminal ``review-cycle-N.md`` verdict into a hand-constructed
   ``review_result`` event, when the event log carries no ``review_result``
   opinion for that WP yet.
2. **Provenance predicate** (:func:`stranded_verdict_findings`): a pure
   function — "terminal ``.md`` verdict + no event ``review_result`` slot" —
   that a merge-time gate (owned elsewhere, e.g. WP05's SC-008 interlock)
   imports and calls directly.

**Mechanism (D-PLAN-10, verified by post-plan squad).** This module uses
:func:`~specify_cli.status.store.append_events_atomic_verified` with a
**hand-constructed** :class:`~specify_cli.status.models.StatusEvent` — never
:func:`~specify_cli.status.emit.emit_status_transition`. ``emit_status_transition``
derives ``from_lane`` from the WP's *current* lane and runs
``validate_transition``, so it cannot replay a historical ``in_review -> *``
edge onto a WP that has since moved on. The precedent for this hand-construction
pattern is :mod:`specify_cli.migration.backfill_runtime_state` (its
``_build_seed_events`` / ``append_events_atomic_verified`` call).

The backfilled event's ``at`` is **always** the historical verdict timestamp
from the artifact's ``reviewed_at`` frontmatter (:class:`~specify_cli.review.artifacts.
ReviewCycleArtifact` requires this field to be a non-empty string — never
absent on a successfully parsed artifact) — **never** ``now()``. A
late-stamped rejection would sort last in the reducer's ``(at, event_id)``
fold (:func:`specify_cli.status.reducer.reduce`) and wrongly resurrect over a
real, later approval.

**Idempotency (G1).** Keyed on ``(mission_id, wp_id, verdict, cycle)`` via a
deterministic ULID (:func:`~specify_cli.migration.mission_state.deterministic_ulid`,
matching the ``backfill_runtime_state`` precedent). A re-run is additionally a
true no-op at the call-site level: once a WP has ANY ``review_result`` event
opinion (``slot_present`` is ``True`` — including a lane-only approval that
carries no structured ``ReviewResult``, per
:func:`specify_cli.status.reducer.event_sourced_review_result`'s three-way
contract), this module skips it.

**Verdict bridge (temporary, C-001 guard).** The mission's canonical
approved/rejected <-> approved/changes_requested bridge is WP04's owned
surface and does not exist yet. This module maps ``rejected -> changes_requested``
and ``approved -> approved`` locally as a stopgap
(``# TODO(WP04): replace with the canonical verdict bridge once it lands``) --
this must not become a second permanent bridge.

Out of scope (owned by other WPs):

- The authoritative durability write on the *live* recording path
  (``status/emit.py``'s add-leg) is WP03's.
- Any CLI/``--json`` surface for the provenance predicate is unowned by this
  WP; :func:`stranded_verdict_findings` is a plain importable function, not a
  doctor subcommand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from specify_cli.migration.mission_state import deterministic_ulid
from specify_cli.mission_metadata import load_meta
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status import (
    APPROVED,
    CHANGES_REQUESTED,
    Lane,
    ReviewResult,
    StatusEvent,
    emission_event_verdict,
    event_sourced_review_result,
    feature_status_lock,
    is_changes_requested,
    mission_lock_key,
)
from specify_cli.status._unsafe import append_events_atomic_verified
from specify_cli.workspace.root_resolver import resolve_status_lock_root

#: Actor identity stamped on every backfilled event, matching the
#: ``migration:<module>`` convention set by ``backfill_runtime_state.py``'s
#: ``BACKFILL_ACTOR``.
BACKFILL_ACTOR = "migration:verdict_provenance_backfill"

#: WP05 (verdict-seam-write-unification-01KZ9Q35) resolved this module's own
#: ``TODO(WP04)``: the canonical verdict bridge (``status.verdict_vocab``)
#: has now landed, so the local ``_VERDICT_BRIDGE`` stopgap this module used
#: to carry is retired -- :func:`~specify_cli.status.verdict_vocab.
#: emission_event_verdict` is the direct replacement (``artifact.verdict`` is
#: always one of :data:`~specify_cli.status.verdict_vocab.
#: EmissionArtifactVerdict`'s two values, per ``REVIEW_ARTIFACT_VERDICTS``'
#: own write-time validation in ``review/artifacts.py``).
#:
#: The lane a backfilled event exits into, keyed by the BRIDGED (event-side)
#: verdict. ``changes_requested`` sends the WP back to active rework (mirrors
#: the real ``_mt_plan_review_result``/``tasks_move_task.py`` rejection
#: flow's ``in_review -> in_progress`` edge); ``approved`` lands on
#: ``APPROVED`` (mirrors that same flow's ``target_lane in (APPROVED, DONE)``
#: branch). Keyed on the bridge's own named constants, not raw literals.
_TO_LANE_BY_BRIDGED_VERDICT: dict[str, Lane] = {
    CHANGES_REQUESTED: Lane.IN_PROGRESS,
    APPROVED: Lane.APPROVED,
}

_WP_DIR_PREFIX_RE = re.compile(r"^(WP\d+)")
_REVIEW_CYCLE_FILENAME_RE = re.compile(r"^review-cycle-(\d+)\.md$")


@dataclass(frozen=True)
class ProvenanceFinding:
    """One stranded-verdict finding: a WP with a terminal ``.md`` verdict and
    no event ``review_result`` slot (FR-012 / G3).

    Returned only for WPs that qualify (i.e. every row in a
    :func:`stranded_verdict_findings` result has both fields on the "bad"
    side) -- callers that want a bare count use ``len(...)``; callers that
    want per-WP detail (e.g. a doctor-style report) get it from the fields
    directly, never a re-derivation.
    """

    wp_id: str
    has_md_verdict: bool
    has_event_slot: bool


@dataclass(frozen=True)
class BackfillOutcome:
    """Result of one :func:`backfill_verdict_provenance` run.

    ``appended_wp_ids`` is empty on a fully-converged re-run (G1) -- this is
    the idempotency witness a caller/test asserts on, not a bare count.
    """

    feature_dir: Path
    appended_wp_ids: tuple[str, ...] = ()

    @property
    def appended_count(self) -> int:
        return len(self.appended_wp_ids)


def _resolve_mission_id(feature_dir: Path) -> str | None:
    """Best-effort ``mission_id`` (ULID) for *feature_dir*, or ``None``.

    Tolerant: a missing or malformed ``meta.json`` (pre-mission_id-era mission,
    or a bare test fixture) yields ``None`` rather than raising -- the
    backfilled event's ``mission_id`` field is optional (legacy-compatible)
    per :class:`~specify_cli.status.models.StatusEvent`.
    """
    meta = load_meta(feature_dir, on_malformed="none")
    if not isinstance(meta, dict):
        return None
    mission_id = meta.get("mission_id")
    return mission_id if isinstance(mission_id, str) and mission_id else None


def _review_cycle_candidate_dirs(feature_dir: Path, wp_id: str) -> list[Path]:
    """Return every ``tasks/`` directory that may hold *wp_id*'s review cycles.

    Tolerant fan-out (the exact ``tasks/<wp_id>`` dir, plus every
    ``tasks/<wp_id>-*`` sibling) -- the real, on-disk convention names the
    review-cycle directory ``<wp_id>-<slug>`` (verified against this
    repository's own ``kitty-specs/`` corpus), so the bare exact-match dir is
    the rarer case. Scanning wider than strictly necessary is safe for a
    read-only provenance scan.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return []
    candidates: list[Path] = []
    exact = tasks_dir / wp_id
    if exact.is_dir():
        candidates.append(exact)
    candidates.extend(
        sorted(
            entry
            for entry in tasks_dir.iterdir()
            if entry.is_dir() and entry.name.startswith(f"{wp_id}-")
        )
    )
    return candidates


def discover_wp_ids_with_review_cycles(feature_dir: Path) -> list[str]:
    """Return every WP id under *feature_dir* that has >=1 review-cycle artifact.

    Derived from ``tasks/`` subdirectory names (``WP\\d+`` prefix) that
    contain at least one ``review-cycle-*.md`` file -- no dependence on a
    ``tasks/WP*.md`` manifest file existing (an archived/legacy mission may
    lack one while still carrying its review-cycle history).
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return []
    wp_ids: set[str] = set()
    for entry in sorted(tasks_dir.iterdir()):
        if not entry.is_dir():
            continue
        match = _WP_DIR_PREFIX_RE.match(entry.name)
        if match is None:
            continue
        if any(entry.glob("review-cycle-*.md")):
            wp_ids.add(match.group(1))
    return sorted(wp_ids)


def _cycle_number(path: Path) -> int:
    """Sort key: the numeric cycle a ``review-cycle-*.md`` filename encodes,
    or ``0`` for an unparseable sibling (never masks a genuinely higher one)."""
    match = _REVIEW_CYCLE_FILENAME_RE.match(path.name)
    return int(match.group(1)) if match else 0


def _legacy_frontmatter_verdict(path: Path) -> str | None:
    """Best-effort read of a historical ``verdict`` frontmatter key (WP06,
    FR-003/SC-007).

    ``ReviewCycleArtifact`` no longer carries a ``verdict`` field (WP06
    retired it as part of making single-authority structural -- every LIVE
    verdict reader resolves the event authority instead, per WP05's reader
    collapse). This migration is the one deliberate exception: it exists
    SPECIFICALLY to recover a verdict recorded before that schema change, from
    an already-written, already-committed ``.md`` file that will forever
    carry ``verdict:`` in its frontmatter (historical git content does not
    retroactively lose fields). This reads the RAW frontmatter mapping
    directly -- deliberately bypassing ``ReviewCycleArtifact.from_dict``,
    which no longer surfaces this key -- rather than reintroducing the field
    on the live dataclass just for this one-time backfill's sake.

    Returns ``None`` (never raises) when the file is unreadable, carries no
    parseable frontmatter, or the ``verdict`` key is absent/non-string --
    callers must treat that as "no legacy verdict to recover", not a crash.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    rest = text[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    closing = rest.find("\n---")
    if closing == -1:
        return None
    yaml = YAML()
    try:
        data = yaml.load(rest[:closing])
    except Exception:  # noqa: BLE001 - tolerant legacy parse, never a crash
        return None
    if not isinstance(data, dict):
        return None
    verdict = data.get("verdict")
    return verdict if isinstance(verdict, str) else None


def terminal_review_artifact(
    feature_dir: Path, wp_id: str
) -> tuple[ReviewCycleArtifact, Path, str | None] | None:
    """Return (artifact, path, legacy_verdict) for *wp_id*'s terminal verdict,
    or ``None``.

    **Terminal verdict** (T007) = the highest-numbered ``review-cycle-N.md``
    for the WP. When more than one candidate directory exists (see
    :func:`_review_cycle_candidate_dirs`), the terminal artifact is the one
    with the highest ``cycle_number`` across ALL of them, tie-broken by the
    later ``reviewed_at`` (lexical compare, matching the reducer's own
    ``(at, event_id)`` ordering discipline) -- a real mission has exactly one
    such directory, so this tie-break is a defensive edge case, not the
    common path.

    **Tolerant of unparseable artifacts.** A real, measured shape in this
    repository's own ``kitty-specs/`` corpus: some historical
    ``review-cycle-N.md`` files predate the YAML-frontmatter schema entirely
    (plain prose, no ``---`` delimiters) and raise ``ValueError`` from
    :meth:`ReviewCycleArtifact.from_file`. Such a directory's highest cycle is
    skipped rather than crashing this scan or silently falling back to a
    LOWER, non-terminal cycle (which would fabricate the wrong "terminal"
    answer) -- callers see ``None`` for that WP, same as "no review cycles at
    all".

    ``legacy_verdict`` (WP06) is read directly from the raw frontmatter (see
    :func:`_legacy_frontmatter_verdict`) alongside the parsed artifact, since
    ``ReviewCycleArtifact`` itself no longer carries a ``verdict`` field.
    """
    best: tuple[ReviewCycleArtifact, Path, str | None] | None = None
    for directory in _review_cycle_candidate_dirs(feature_dir, wp_id):
        candidates = sorted(directory.glob("review-cycle-*.md"), key=_cycle_number)
        if not candidates:
            continue
        terminal_path = candidates[-1]
        try:
            artifact = ReviewCycleArtifact.from_file(terminal_path)
        except ValueError:
            continue
        if best is None or (artifact.cycle_number, artifact.reviewed_at) > (
            best[0].cycle_number,
            best[0].reviewed_at,
        ):
            legacy_verdict = _legacy_frontmatter_verdict(terminal_path)
            best = (artifact, terminal_path, legacy_verdict)
    return best


def stranded_verdict_findings(feature_dir: Path) -> list[ProvenanceFinding]:
    """Pure predicate (FR-012 / G3): every WP with a terminal ``.md`` verdict
    and no event ``review_result`` slot.

    Distinct from the reconcile doctor's *location* classes
    (``deleted_coord_branch_absorption``, ``live_coord_pre_adr_primary_record``,
    D-PLAN-15) -- this predicate is about verdict *provenance* (event slot vs
    ``.md``-only), never about which physical directory a record sits in.

    Returns an empty list once every stranded WP has been backfilled (T010 /
    US6 scenario 2) -- a merge-time gate treats a non-empty result as
    "blocks", per G3.
    """
    findings: list[ProvenanceFinding] = []
    for wp_id in discover_wp_ids_with_review_cycles(feature_dir):
        terminal = terminal_review_artifact(feature_dir, wp_id)
        if terminal is None:
            continue
        _, _, legacy_verdict = terminal
        if legacy_verdict is None:
            # No legacy `verdict` frontmatter key to migrate (WP06) -- e.g. an
            # artifact written after the schema change, which never carried
            # the field in the first place. Nothing stranded here.
            continue
        lookup = event_sourced_review_result(feature_dir, wp_id)
        if lookup.slot_present:
            continue
        findings.append(
            ProvenanceFinding(wp_id=wp_id, has_md_verdict=True, has_event_slot=False)
        )
    return findings


def _backfill_event_for_wp(
    feature_dir: Path,
    wp_id: str,
    artifact: ReviewCycleArtifact,
    path: Path,
    legacy_verdict: str,
    mission_id: str | None,
) -> StatusEvent:
    """Hand-construct the historical ``review_result`` event for one WP.

    ``at`` is the artifact's own ``reviewed_at`` -- the historical verdict
    timestamp -- never ``now()`` (D-PLAN-10). ``from_lane=IN_REVIEW`` mirrors
    the real edge this event replays (a review verdict always exits
    ``in_review``); the reducer's own review-result-slot rule
    (``event.review_result is not None or event.from_lane == IN_REVIEW``)
    would fire from ``review_result`` alone regardless, but stating the
    correct historical ``from_lane`` keeps the event internally truthful.

    ``legacy_verdict`` (WP06) is the RAW frontmatter ``verdict`` value read by
    :func:`terminal_review_artifact` via :func:`_legacy_frontmatter_verdict`
    -- ``ReviewCycleArtifact`` itself no longer carries this field.
    """
    bridged_verdict = emission_event_verdict(legacy_verdict)
    reference = f"review-cycle://{feature_dir.name}/{path.parent.name}/{path.name}"
    review_result = ReviewResult(
        reviewer=artifact.reviewer_agent,
        verdict=bridged_verdict,
        reference=reference,
        feedback_path=str(path) if is_changes_requested(bridged_verdict) else None,
    )
    event_id = str(
        deterministic_ulid(
            f"{mission_id or feature_dir.name}|{wp_id}|review_result|"
            f"{legacy_verdict}|{artifact.cycle_number}"
        )
    )
    return StatusEvent(
        event_id=event_id,
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.IN_REVIEW,
        to_lane=_TO_LANE_BY_BRIDGED_VERDICT[bridged_verdict],
        at=artifact.reviewed_at,
        actor=BACKFILL_ACTOR,
        force=False,
        execution_mode="worktree",
        review_result=review_result,
        mission_id=mission_id,
    )


def backfill_verdict_provenance(feature_dir: Path) -> BackfillOutcome:
    """Idempotently backfill ``status.events.jsonl`` from terminal ``.md``
    verdicts (FR-012 core).

    For each WP with a terminal ``.md`` verdict and no event ``review_result``
    slot (the same predicate :func:`stranded_verdict_findings` reports),
    append one hand-constructed historical event via
    :func:`~specify_cli.status.store.append_events_atomic_verified`. A
    fully-converged re-run appends nothing (G1): every previously-backfilled
    WP now has ``slot_present=True`` and is skipped.
    """
    mission_id = _resolve_mission_id(feature_dir)
    # fsm-write-path-integrity WP01 (FR-002, writer family 6): the whole
    # discover -> ``slot_present`` read -> append sequence runs under ONE
    # acquisition of the mission status lock (keyed on ``mission_lock_key``).
    # ``event_sourced_review_result`` reads the event log, so leaving it
    # outside the lock is a TOCTOU against a concurrent verdict writer; the
    # backfill is a one-shot migration, so holding the lock across the review
    # artifact reads too is cheap. No ``nullcontext()`` degrade at this site
    # (conscious choice): the lock root resolver never fails. No git subprocess
    # runs inside the section (NFR-001).
    lock_root = resolve_status_lock_root(feature_dir)
    with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
        events, appended_wp_ids = _collect_backfill_events(feature_dir, mission_id)
        if events:
            append_events_atomic_verified(feature_dir, events)
    return BackfillOutcome(feature_dir=feature_dir, appended_wp_ids=tuple(appended_wp_ids))


def _collect_backfill_events(feature_dir: Path, mission_id: str | None) -> tuple[list[StatusEvent], list[str]]:
    """Return the stranded-verdict events to append plus their WP ids.

    Caller must hold the mission status lock: the ``slot_present`` probe is an
    event-log read whose answer the append relies on.
    """
    events: list[StatusEvent] = []
    appended_wp_ids: list[str] = []
    for wp_id in discover_wp_ids_with_review_cycles(feature_dir):
        terminal = terminal_review_artifact(feature_dir, wp_id)
        if terminal is None:
            continue
        artifact, path, legacy_verdict = terminal
        if legacy_verdict is None:
            continue
        if event_sourced_review_result(feature_dir, wp_id).slot_present:
            continue
        events.append(
            _backfill_event_for_wp(feature_dir, wp_id, artifact, path, legacy_verdict, mission_id)
        )
        appended_wp_ids.append(wp_id)
    return events, appended_wp_ids


# Public surface (re-declared post-wiring, verdict-seam-write-unification-
# 01KZ9Q35 pre-merge remediation, 2026-08-06). The two entry points below now
# have live ``src/`` importers, so the ``__all__`` demotion the post-merge
# green-up applied (when this was a caller-less library) is reversed:
#
# - ``backfill_verdict_provenance`` is imported+called by the auto-discovered
#   upgrade migration ``specify_cli.upgrade.migrations.
#   m_zz_verdict_provenance_backfill`` (the FR-012/SC-008 wiring).
# - ``stranded_verdict_findings`` is imported by that same migration's
#   ``detect``/dry-run preview AND by the ``spec-kitty accept`` provenance
#   diagnostic (``specify_cli.cli.commands.accept``).
#
# Both therefore pass ``tests/architectural/test_no_dead_symbols.py`` (each has
# a non-test ``src/`` caller). The remaining module-internal helpers
# (``terminal_review_artifact``, ``BackfillOutcome``, ...) stay ordinary
# module-level names, reachable by tests via explicit imports but off the
# star-export surface. #3236 now tracks ONLY the function-level census-
# exclusion narrowing (``_legacy_frontmatter_verdict``'s disclosed reader blind
# spot), not the wiring -- which this remediation closes.
__all__ = [
    "backfill_verdict_provenance",
    "stranded_verdict_findings",
]
