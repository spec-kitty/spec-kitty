"""Pure planner for the WP-status snapshot backfill (#5579).

The reduced status snapshot (``materialize_snapshot(feature_dir).work_packages``)
omits every WP that has no *lane* event: a ``genesis`` WP never materialises
(ADR ``2026-06-07-3``) and a ``WPCreated`` row is a lifecycle event, not a lane
transition. Read surfaces that list WPs from ``tasks/WP*.md`` therefore
disagree with the snapshot for any Mission whose log never seeded some WP.

This module decides **what to seed**; it never writes. The write lives in
:func:`specify_cli.migration.backfill_runtime_state.apply_wp_status_backfill`,
which reuses that module's lock + atomic-append path so no second event-log
writer exists (C-002). The reducer is untouched (C-001): the repair is more
events, never a snapshot overlay.

Seed shape, per WP file the snapshot lacks (``files_only``):

* a ``genesis -> planned`` seed, always;
* when the Mission carries terminal evidence, a forced ``planned -> done``
  whose ``reason`` cites that evidence (``evidence=None``, ``force=True``).

Both use the ``migration:`` actor (C-003), deterministic event ids (FR-010) and
deterministic timestamps, so a re-run is a no-op by construction.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kernel.clock import UTC, datetime, parse_iso, timedelta
from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.frontmatter import FrontmatterError
from specify_cli.status import Lane, StatusEvent, materialize_snapshot, read_authored_wp_frontmatter

from .mission_state import deterministic_ulid

logger = logging.getLogger(__name__)

#: Actor on every seed. The ``migration:`` prefix is what
#: ``consolidation.wp_attribution.MIGRATION_ACTOR_PREFIX`` keys on, so attribution
#: windows ignore these rows (C-003); a test pins the prefix relationship.
WP_STATUS_BACKFILL_ACTOR = "migration:backfill_wp_status"

#: Namespace component of every deterministic seed id (FR-010).
SEED_NAMESPACE = "wp-status-backfill"

#: Seed timestamp when ``meta.json`` carries no parseable ``created_at``. The Unix
#: epoch is deliberately synthetic and constant, so the seed is reproducible.
FALLBACK_SEED_AT = "1970-01-01T00:00:00+00:00"

#: The forced ``done`` lands this long after the ``planned`` seed so the reducer's
#: ``(at, event_id)`` order is ``planned`` then ``done`` regardless of id order.
_DONE_OFFSET = timedelta(seconds=1)

#: ``meta.json`` keys that prove a Mission finished, in precedence order (FR-004).
_META_EVIDENCE_KEYS = ("merged_at", "accepted_at")

_PLANNED_REASON = "wp-status backfill (#5579): WP file has no lane event; seeded planned"
_DONE_REASON_TEMPLATE = "wp-status backfill (#5579): Mission finished ({evidence}); seeded WP driven to done"


#: ``WpStatusBackfillResult.skip_reason`` of a Mission refused because its
#: status authority is a live coordination surface (stable JSON vocabulary).
COORD_SURFACE_LIVE = "COORD_SURFACE_LIVE"

#: Operator-facing explanation rendered next to a ``COORD_SURFACE_LIVE`` skip.
COORD_SURFACE_LIVE_MESSAGE = (
    "its status log lives on a live coordination surface, so the PRIMARY-partition log is not the authority "
    "and seeding it would split-brain the Mission. Consolidate the Mission first "
    "(`spec-kitty consolidate --mission <slug>`), or run this command from the coordination checkout."
)


def coordination_surface_is_live(feature_dir: Path) -> bool:
    """Whether *feature_dir*'s status authority is a live coordination surface.

    Asks the canonical surface authority
    (:func:`specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor`)
    where the Mission's ``status.events.jsonl`` currently lives, instead of
    probing git here. The surface is *live* when it resolves somewhere other than
    *feature_dir* (the PRIMARY-partition Mission directory): a coord-routing
    topology whose coordination worktree is materialised, or whose branch still
    exists. It is *not* live (the PRIMARY-partition log is the authority) when

    * the Mission declares no ``coordination_branch`` in ``meta.json`` (it has no
      coordination surface; this cheap pre-check skips the resolver, whose
      mission index is rebuilt on every call and is O(corpus));
    * the topology routes status to the PRIMARY partition, or the Mission is
      completed (merge evidence makes the primary log the record);
    * the coordination worktree root exists but is empty;
    * the coordination branch is gone (``CoordinationBranchDeleted``) -- the
      documented degrade, kept so a post-deletion Mission can still be repaired;
    * there is no repository, no readable ``meta.json`` or no resolvable root.

    Fail closed: any other ``StatusReadPathNotFound`` (a coord-declared topology
    whose surface cannot be proven) counts as live. Read-only: the resolver
    never writes, materialises or mints a branch.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, resolve_status_surface_with_anchor
    from specify_cli.core.paths import MissionMetaReadError, WorkspaceRootNotFound, resolve_canonical_root
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    if not (load_meta(feature_dir, allow_missing=True, on_malformed="none") or {}).get("coordination_branch"):
        return False
    try:
        repo_root = resolve_canonical_root(feature_dir)
        surface = resolve_status_surface_with_anchor(repo_root, feature_dir.name)
    except (WorkspaceRootNotFound, FileNotFoundError, MissionMetaReadError, CoordinationBranchDeleted):
        # CoordinationBranchDeleted is a StatusReadPathNotFound: keep it ahead of
        # the fail-closed arm by listing it here, in the degrade set.
        return False
    except StatusReadPathNotFound:
        return True
    return bool(surface.surface_path.parent.resolve() != feature_dir.resolve())


@dataclass(frozen=True)
class WpGap:
    """Set difference between a Mission's WP files and its reduced snapshot.

    Attributes:
        files_only: WP ids with a valid WP file but no lane events (to be seeded).
        snapshot_only: WP ids the snapshot carries that have no WP file. Reported,
            never repaired (files are not invented, events are not deleted).
        malformed: ``tasks/`` file names skipped for malformed frontmatter or a
            missing ``work_package_id``; never guessed.
    """

    files_only: frozenset[str]
    snapshot_only: frozenset[str]
    malformed: tuple[str, ...] = ()


@dataclass(frozen=True)
class TerminalEvidence:
    """Why a Mission counts as finished (FR-004).

    Attributes:
        source: ``"meta.merged_at"``, ``"meta.accepted_at"`` or ``"manifest"``.
        description: Text cited in the forced ``done`` event's ``reason``.
    """

    source: str
    description: str


@dataclass(frozen=True)
class WpStatusPlan:
    """Everything the writer needs for one Mission; a pure value."""

    slug: str
    gap: WpGap
    evidence: TerminalEvidence | None
    events: tuple[StatusEvent, ...]


def collect_wp_file_ids(tasks_dir: Path) -> tuple[frozenset[str], tuple[str, ...]]:
    """Return ``(valid WP ids, malformed file names)`` for ``tasks/WP*.md``.

    Mirrors ``status.bootstrap._collect_wp_ids`` (frontmatter ``work_package_id``,
    malformed files reported and skipped) but reads the *authored* frontmatter:
    ``read_wp_frontmatter`` re-reduces the whole event log once per file to refresh
    runtime fields this planner never looks at.
    """
    ids: set[str] = set()
    malformed: list[str] = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            meta, _body = read_authored_wp_frontmatter(wp_file)
        except (FrontmatterError, ValidationError):
            logger.warning("Skipping %s: malformed frontmatter", wp_file.name)
            malformed.append(wp_file.name)
            continue
        if not meta.work_package_id:
            logger.warning("Skipping %s: missing or invalid work_package_id", wp_file.name)
            malformed.append(wp_file.name)
            continue
        ids.add(meta.work_package_id)
    return frozenset(ids), tuple(malformed)


def read_snapshot_wp_ids(feature_dir: Path) -> frozenset[str]:
    """Return the WP ids the reduced snapshot carries, without writing anything.

    Uses the read-only ``materialize_snapshot``; ``materialize`` also rewrites
    ``status.json`` and must not be used for an audit.
    """
    return frozenset(materialize_snapshot(feature_dir).work_packages)


def compute_gap(file_ids: Collection[str], snapshot_ids: Collection[str], malformed: tuple[str, ...] = ()) -> WpGap:
    """Compare file ids with snapshot ids, set-wise and in both directions (FR-001)."""
    files = frozenset(file_ids)
    snapshot = frozenset(snapshot_ids)
    return WpGap(files_only=files - snapshot, snapshot_only=snapshot - files, malformed=malformed)


def resolve_terminal_evidence(
    meta: Mapping[str, Any] | None,
    slug: str,
    manifest: Mapping[str, str] | None,
) -> TerminalEvidence | None:
    """Decide whether the Mission is finished, from recorded evidence only (FR-004).

    ``meta.json`` ``merged_at`` wins over ``accepted_at``; otherwise an
    evidence-manifest entry ``{slug: reason}`` with a non-empty reason. Nothing
    else counts: no inference from the log, the branch or the WP files.
    """
    for key in _META_EVIDENCE_KEYS:
        value = (meta or {}).get(key)
        if isinstance(value, str) and value.strip():
            return TerminalEvidence(source=f"meta.{key}", description=f"meta.json {key}={value.strip()}")
    reason = (manifest or {}).get(slug)
    if isinstance(reason, str) and reason.strip():
        return TerminalEvidence(source="manifest", description=f"evidence manifest: {reason.strip()}")
    return None


def seed_timestamp(meta: Mapping[str, Any] | None) -> str:
    """Return the deterministic ``planned`` seed timestamp (ISO-8601 UTC).

    ``meta.json`` ``created_at`` when it parses, else :data:`FALLBACK_SEED_AT`.
    A naive timestamp is read as UTC; ``Z`` is accepted.
    """
    raw = (meta or {}).get("created_at")
    if not isinstance(raw, str) or not raw.strip():
        return FALLBACK_SEED_AT
    try:
        parsed: datetime = parse_iso(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return FALLBACK_SEED_AT
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def seed_event_id(mission_key: str, wp_id: str, to_lane: str) -> str:
    """Deterministic seed id keyed on ``(mission, wp, to_lane, namespace)`` (FR-010)."""
    return str(deterministic_ulid(f"{mission_key}|{wp_id}|{to_lane}|{SEED_NAMESPACE}"))


def _planned_event(slug: str, mission_id: str | None, mission_key: str, wp_id: str, at: str) -> StatusEvent:
    return StatusEvent(
        event_id=seed_event_id(mission_key, wp_id, str(Lane.PLANNED)),
        mission_slug=slug,
        wp_id=wp_id,
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at=at,
        actor=WP_STATUS_BACKFILL_ACTOR,
        force=False,
        execution_mode="worktree",
        reason=_PLANNED_REASON,
        mission_id=mission_id,
    )


def _done_event(
    slug: str,
    mission_id: str | None,
    mission_key: str,
    wp_id: str,
    at: str,
    evidence: TerminalEvidence,
) -> StatusEvent:
    return StatusEvent(
        event_id=seed_event_id(mission_key, wp_id, str(Lane.DONE)),
        mission_slug=slug,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.DONE,
        at=at,
        actor=WP_STATUS_BACKFILL_ACTOR,
        force=True,
        execution_mode="worktree",
        reason=_DONE_REASON_TEMPLATE.format(evidence=evidence.description),
        evidence=None,
        mission_id=mission_id,
    )


def build_seed_events(
    *,
    slug: str,
    mission_id: str | None,
    wp_ids: Collection[str],
    planned_at: str,
    evidence: TerminalEvidence | None,
) -> tuple[StatusEvent, ...]:
    """Build the seed events for *wp_ids*, in WP-id order.

    *mission_id* is the ULID from ``meta.json`` (``None`` when the Mission has
    none); the event id key falls back to *slug* then, as the runtime backfill
    does.
    """
    mission_key = mission_id or slug
    done_at = (parse_iso(planned_at) + _DONE_OFFSET).isoformat()
    events: list[StatusEvent] = []
    for wp_id in sorted(wp_ids):
        events.append(_planned_event(slug, mission_id, mission_key, wp_id, planned_at))
        if evidence is not None:
            events.append(_done_event(slug, mission_id, mission_key, wp_id, done_at, evidence))
    return tuple(events)


def plan_wp_status_backfill(
    feature_dir: Path,
    *,
    manifest: Mapping[str, str] | None = None,
) -> WpStatusPlan:
    """Plan the seeds for one Mission directory. Reads only; never writes.

    A WP that already has any lane event is in the snapshot, hence never in
    ``files_only``, hence never touched (FR-002, US2 scenario 4).

    Args:
        feature_dir: The Mission directory (``kitty-specs/<slug>``).
        manifest: Optional evidence manifest ``{mission slug: reason}``.

    Raises:
        specify_cli.status.StoreError: the event log is unreadable.
        specify_cli.core.paths.MissionMetaReadError: ``meta.json`` exists but is corrupt.
    """
    slug = feature_dir.name
    meta = load_meta_fail_closed(feature_dir)
    raw_id = (meta or {}).get("mission_id")
    mission_id = str(raw_id) if raw_id else None

    tasks_dir = feature_dir / "tasks"
    file_ids, malformed = collect_wp_file_ids(tasks_dir) if tasks_dir.is_dir() else (frozenset[str](), ())
    gap = compute_gap(file_ids, read_snapshot_wp_ids(feature_dir), malformed)

    evidence = resolve_terminal_evidence(meta, slug, manifest)
    events = build_seed_events(
        slug=slug,
        # Mirrors the runtime backfill: an id equal to the slug is "no id".
        mission_id=mission_id if mission_id != slug else None,
        wp_ids=gap.files_only,
        planned_at=seed_timestamp(meta),
        evidence=evidence,
    )
    return WpStatusPlan(slug=slug, gap=gap, evidence=evidence, events=events)
