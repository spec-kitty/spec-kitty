"""Status emit orchestration pipeline.

Single entry point for ALL state changes in the canonical status model.
Validates a transition, appends an event to the JSONL log, materializes
a status snapshot, and emits SaaS telemetry.

The event log is the sole authority for mutable WP state. In explicit
phase-1 compatibility mode (``meta.json`` with ``status_phase: 1``),
this pipeline may mirror the canonical lane into an existing WP
frontmatter ``lane`` field. That mirror is transitional and never
authoritative.

**Verdict durability (WP03 / FR-008 / contracts/verdict-durability-write.md,
mission verdict-seam-write-unification-01KZ9Q35):** for a recorded verdict
(any outbound-from-``in_review`` transition, which the FSM requires to carry
a ``ReviewResult``), the ``store.append_event_stream_atomic_verified`` call
in step 5 below IS the single authoritative durable act (contract G1/NFR-004)
-- the same append every other transition already goes through, not a
bespoke second write. It never holds ``feature_status_lock`` across a
``git`` subprocess (NFR-001/G3: the only subprocess call on this path,
resolving the lock's own path, happens BEFORE the lock is acquired -- see
``locking.feature_status_lock``), and the event log itself is
union-merge-driver protected (``.gitattributes`` -> ``merge=spec-kitty-
event-log``) so two concurrent distinct verdicts union rather than clobber
(SC-003). The separate ``review-cycle-N.md`` artifact commit
(``review/cycle.py::_commit_review_cycle_artifact``) is NOT part of this
authoritative act -- it stays a hard-error, best-effort-in-name-only render
until WP05's reader flip demotes it (D-PLAN-11).

Shell order (critical -- do not reorder; contract ``emit-pipeline.md`` §2,
flat/primary column). This module is the flat/primary composition shell;
validation and event construction are NOT here but in the status-owned
pipeline ``status/transition_pipeline.py::prepare_transition`` (FR-005):
    1. feature_status_lock(resolve_status_lock_root(...), feature_dir.name)
    2. Derive from_lane from the reduced log for this WP -- once (NFR-004)
    4. prepare_transition(...)  (alias-resolve, gates, validate, build)
    5. store.append_event_stream_atomic_verified -> reducer.materialize -> lane mirror
    6. Release the lock
    7. _saas_fan_out(event, mission_slug, repo_root)  (skipped when fan_out=False)
    8. Return the event
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import ulid as _ulid_mod
from pydantic import ValidationError

from kernel.clock import now_utc, now_utc_iso, timedelta
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.mission_metadata import load_meta
from specify_cli.frontmatter import FrontmatterError, read_frontmatter, write_frontmatter
from specify_cli.workspace import canonicalize_feature_dir
from .wp_metadata import coerce_legacy_dependencies, read_wp_frontmatter

from .models import (
    ActorField,
    DoneEvidence,
    EventStream,
    InnerStateChanged,
    Lane,
    RepoEvidence,
    ReviewApproval,
    ReviewResult,
    StatusEvent,
    StatusSnapshot,
    TransitionRequest,
    VerificationResult,
    WPInnerStateDelta,
)
from .dependency_verdict import readiness_from_snapshot, unresolvable_readiness
from .resolved_binding import ResolvedBinding
from .wp_state import annotate
from . import store as _store
from . import reducer as _reducer
from .adapters import fire_resolved_binding_fanout, fire_saas_fanout
from .locking import feature_status_lock
from .transition_pipeline import PreparedTransition, prepare_transition

if TYPE_CHECKING:
    from specify_cli.core.dependency_graph import DependencyReadiness

logger = logging.getLogger(__name__)

_LEGACY_LANE_FIELD = "lane"

# ---------------------------------------------------------------------------
# SaaS package capability gate (T022, WP04)
# ---------------------------------------------------------------------------
# Detect at import time whether the installed spec_kitty_events supports the
# genesis lane. spec_kitty_events 5.2.0 has no genesis member; 6.0.0+ will add
# it. When genesis is absent from the installed package, fan-out for genesis
# transitions is deliberately skipped rather than silently swallowed by pydantic
# ValidationError in _build_payload_via_model. Canonical local persistence is
# completely unaffected — fan-out is best-effort.
#
# NOTE: once spec-kitty-events 6.0.0 (genesis lane) ships and the pyproject.toml
# constraint is bumped to >=6.0.0,<7.0.0, this gate resolves to True on all
# installs and may eventually be removed.
try:
    import spec_kitty_events as _spec_kitty_events_mod

    _EVENTS_SUPPORTS_GENESIS: bool = "genesis" in {lane.value for lane in _spec_kitty_events_mod.Lane}
    # First-class resolved-binding bridge gate (FR-015 / IC-09, T049). Mirrors the
    # genesis gate: detect at import time whether the installed spec_kitty_events
    # exposes ``WPResolvedBindingChanged``. 6.1.0 does NOT; 6.2.0 (a SEPARATE
    # cross-repo deliverable) will. When absent, the fan-out for an off-transition
    # binding change is deliberately skipped (logged), NEVER a swallowed
    # ValidationError — local persistence is completely unaffected. When the event
    # ships and the pin is bumped, this gate resolves True on all installs and the
    # bridge lights up automatically with no code change here.
    _EVENTS_SUPPORTS_RESOLVED_BINDING: bool = hasattr(_spec_kitty_events_mod, "WPResolvedBindingChanged")
except (ImportError, AttributeError):
    # ImportError: spec_kitty_events not installed. AttributeError: installed but
    # lacks a Lane enum. Either way, treat both capabilities as unsupported.
    _EVENTS_SUPPORTS_GENESIS = False
    _EVENTS_SUPPORTS_RESOLVED_BINDING = False


def _load_mission_id(feature_dir: Path) -> str | None:
    """Load the canonical mission_id (ULID) from meta.json.

    Returns None when meta.json is absent or does not contain
    a ``mission_id`` key (legacy missions pre-dating 3.1.1).
    Never raises — missing/corrupt meta is a silent degradation
    (on_malformed="none" absorbs both missing and malformed to None).
    """
    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none")
    if meta is None:
        return None
    raw_id = meta.get("mission_id")
    return str(raw_id) if raw_id else None


class TransitionError(Exception):
    """Raised when a status transition is invalid."""


def _generate_ulid() -> str:
    """Generate a new ULID string."""
    if hasattr(_ulid_mod, "new"):
        return str(_ulid_mod.new().str)
    return str(_ulid_mod.ULID())


# ---------------------------------------------------------------------------
# WP06 (T028) -- pure status-domain helpers
# ---------------------------------------------------------------------------
#
# Per FR-032, the status domain stays free of coordination-layer concerns.
# These helpers are pure: ``build_status_event`` mints a StatusEvent in
# memory (ULID, ISO timestamp, Lane coercion) with no I/O;
# ``append_event_jsonl`` performs a single-line JSONL append with no
# commit and no materialization.
#
# Workflow call sites compose ``build_status_event`` + the coordination
# transaction's ``append_event`` (which calls into store + reducer).
# Compatibility callers may still use ``emit_status_transition``.
# Production workflow code routes through coordination.status_transition
# so event append + outbound fanout are transactionally ordered.


def build_status_event(  # noqa: PLR0913 -- pass-through to a dataclass constructor
    *,
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    actor: ActorField,
    at: str | None = None,
    mission_id: str | None = None,
    force: bool = False,
    execution_mode: str = "worktree",
    reason: str | None = None,
    reason_source: str | None = None,
    review_ref: str | None = None,
    summary: str | None = None,
    evidence: DoneEvidence | None = None,
    review_result: ReviewResult | None = None,
    policy_metadata: dict[str, Any] | None = None,
) -> StatusEvent:
    """Construct a fresh :class:`StatusEvent` with a new ULID and timestamp.

    Pure: no I/O, no validation, no side effects. Callers that need
    transition validation should run :func:`validate_transition` first
    and let it raise; this helper only assembles a value object.

    Args:
        mission_slug: Human mission identifier (e.g. ``"034-feature"``).
        wp_id: Work-package id (e.g. ``"WP01"``).
        from_lane: Canonical lane the WP is leaving.
        to_lane: Canonical lane the WP enters.
        actor: Identity of the actor performing the transition.
        at: Optional producer occurrence timestamp; defaults to now.
        mission_id: ULID-based machine identity (optional for legacy).
        force: True if this transition bypasses guard conditions.
        execution_mode: ``"worktree"`` or ``"direct_repo"``.
        reason: Optional human reason (required for force).
        reason_source: Optional provenance discriminator for ``reason``
            (``"operator"`` / ``"synthetic"``); ``None`` when not tracked.
        review_ref: Optional review-feedback reference.
        summary: Optional one-line human gist of the transition for the NOW
            view (#4327); validated at the CLI boundary, never here.
        evidence: Optional :class:`DoneEvidence` for done transitions.
        review_result: Optional structured review outcome for review exits.
        policy_metadata: Optional orchestrator policy metadata dict.

    Returns:
        A new :class:`StatusEvent` ready to append to the event log.
    """
    return StatusEvent(
        event_id=_generate_ulid(),
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=at or now_utc_iso(),
        actor=actor,
        force=force,
        execution_mode=execution_mode,
        reason=reason,
        reason_source=reason_source,
        review_ref=review_ref,
        summary=summary,
        evidence=evidence,
        review_result=review_result,
        policy_metadata=policy_metadata,
        mission_id=mission_id,
    )


def append_event_jsonl(events_path: Path, event: StatusEvent) -> None:
    """Append a single :class:`StatusEvent` to a JSONL event log.

    Pure I/O: writes one canonical JSON line. Does not materialize,
    does not commit, does not fan out. The caller is responsible for
    holding any required lock.

    Args:
        events_path: Path to the ``status.events.jsonl`` file. Parent
            directories are created on demand.
        event: The :class:`StatusEvent` to append.
    """
    # Delegate to the canonical store implementation so the wire format
    # stays consistent (sorted keys, trailing newline, etc.). The store
    # accepts the feature_dir, not the events_path directly.
    feature_dir = events_path.parent
    feature_dir.mkdir(parents=True, exist_ok=True)
    _store.append_event_verified(feature_dir, event)


def build_claim_policy_metadata(
    shell_pid: int,
    shell_pid_created_at: str,
    agent: str,
) -> dict[str, Any]:
    """Return the ``planned -> claimed`` ``policy_metadata`` sidecar.

    Pinned keys — ``shell_pid``, ``shell_pid_created_at``, ``agent`` — are the
    exact keys the reducer's claim fold (``reducer._wp_state_from_event``)
    extracts into the snapshot runtime slots. Defining the builder here gives
    the claim-writer WP and the reducer a single agreed shape; downstream WPs
    import this exact symbol rather than re-deriving the dict.
    """
    return {
        "shell_pid": shell_pid,
        "shell_pid_created_at": shell_pid_created_at,
        "agent": agent,
    }


def _reduce_write_surface(feature_dir: Path) -> StatusSnapshot:
    """Read and reduce the full event log of a shell's write surface -- once.

    This is the shell's ONE full-log read per emit (NFR-004). The returned
    snapshot serves both the WP's ``from_lane`` (:func:`_derive_from_lane`)
    and the dependency verdict (:func:`_resolve_dependency_readiness`), so
    wiring the guard added no second read.
    """
    # follow_imports=skip makes _store.read_events/_reducer.reduce return Any
    # (specify_cli.* boundary); the real signatures return list[StatusEvent]
    # and StatusSnapshot. The annotation below is type-only.
    events = _store.read_events(feature_dir)
    snapshot: StatusSnapshot = _reducer.reduce(events)
    return snapshot


def _derive_from_lane(feature_dir: Path, wp_id: str, *, snapshot: StatusSnapshot | None = None) -> str:
    """Derive the current lane for a WP from canonical reduced state.

    The event log may not be append-ordered by logical transition time,
    so we must reduce the full log to determine the current lane
    deterministically. A shell that has already reduced its write surface
    passes that ``snapshot`` so the lane is taken from the same single read
    (NFR-004); without one, this helper performs the read itself.

    A WP with no lane-state events yet (created but not seeded) is reported as
    ``GENESIS`` — distinct from ``PLANNED`` — so the bootstrap seed is an
    explicit ``genesis -> planned`` transition rather than a dropped
    ``planned -> planned`` self-transition.
    """
    # Lane(…).value is str but Lane itself is not str — the casts below are
    # type-only with no behaviour change.
    if snapshot is None:
        snapshot = _reduce_write_surface(feature_dir)
    wp_state = snapshot.work_packages.get(wp_id)
    if wp_state is None:
        return cast(str, Lane.GENESIS)

    lane_raw: str | None = cast("str | None", wp_state.get("lane"))
    if lane_raw is not None:
        return cast(str, Lane(lane_raw))
    return cast(str, Lane.GENESIS)


def _declared_dependencies(planning_feature_dir: Path, wp_id: str) -> tuple[str, ...]:
    """The ``dependencies`` a WP prompt file declares on the PRIMARY planning surface.

    WP files are authored on the primary checkout (``cli/commands/implement.py::
    find_wp_file``), never on the coordination write surface. Resolve that
    planning surface even when a flat caller supplies a coord write dir.
    A WP without a prompt file declares nothing.

    Only the ``dependencies`` key is read, from the raw frontmatter: the typed
    ``read_wp_frontmatter`` re-points runtime fields from a reduced snapshot
    (a second full-log read on the emit path, NFR-004), and whole-model
    ``WPMetadata`` validation would refuse status writes for defects unrelated
    to dependencies. The value is normalised with the same legacy coercion
    ``WPMetadata`` applies (:func:`wp_metadata.coerce_legacy_dependencies`), so
    the shells accept exactly the files the pre-flight sites accept (FR-014).

    Raises ``TransitionError`` when the frontmatter cannot be parsed, the
    ``dependencies`` value is one ``WPMetadata`` would also refuse, or MORE
    THAN ONE ``tasks/`` file matches ``wp_id`` (a rename leftover: the
    declarations are unresolvable, not absent -- distinct from the
    genuinely-absent case of zero matches, which still declares nothing).
    The shells do not let that raise escape: :func:`_resolve_dependency_readiness`
    maps it to an *unsatisfied* verdict, so only the guarded entry edges are
    refused (fail-closed where the guard has an opinion, ``force`` bypassable)
    and every other edge is unaffected.
    """
    # The plain door can also write a registered coord surface (the
    # transactional fallback). WP prompts remain PRIMARY artifacts there;
    # reading the coord copy would treat an absent prompt as no dependencies.
    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415
    from specify_cli.workspace.root_resolver import WorkspaceRootNotFound, resolve_canonical_root  # noqa: PLC0415

    # Preserve the plain door's explicit ad-hoc dirs and primary bootstrap
    # surfaces. Only a kitty-specs dir names the durable primary planning home
    # this re-anchor exists to protect; an ad-hoc caller-supplied dir (outside
    # kitty-specs) is left untouched.
    #
    # No hand-rolled root-walk comparison here (the prior `parent.parent`
    # equality gate a write-side gate correctly flags as re-derivation):
    # WORK_PACKAGE_TASK is a PRIMARY-partition kind (mission_runtime.artifacts),
    # so `PlacementSeam.read_dir` resolves the primary mission dir for EVERY
    # topology and coord state (it never transits coord, never raises
    # CoordinationBranchDeleted) -- calling it unconditionally is idempotent
    # when `planning_feature_dir` already IS the canonical primary dir (the
    # canonicalizer's `meta.json`-exists short-circuit returns the handle
    # unchanged), so dropping the "already anchored" fast path costs nothing
    # beyond a redundant resolve.
    if planning_feature_dir.parent.name == KITTY_SPECS_DIR:
        try:
            primary_root = resolve_canonical_root(planning_feature_dir)
        except WorkspaceRootNotFound:
            pass
        else:
            planning_feature_dir = placement_seam(primary_root, planning_feature_dir.name).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    matches = _match_wp_files(planning_feature_dir, wp_id)
    if len(matches) > 1:
        names = ", ".join(sorted(path.name for path in matches))
        logger.warning(
            "Multiple work package files matched %s in %s; dependency declarations are ambiguous",
            wp_id,
            planning_feature_dir,
        )
        raise TransitionError(
            f"Cannot resolve the declared dependencies of {wp_id}: ambiguous match ({len(matches)} files in {planning_feature_dir / 'tasks'}: {names})"
        )
    if not matches:
        return ()
    wp_file = matches[0]
    try:
        frontmatter, _body = read_frontmatter(wp_file)
    except FrontmatterError as exc:
        raise TransitionError(f"Cannot resolve the declared dependencies of {wp_id}: {wp_file} is unreadable ({exc})") from exc
    return _coerce_declared_dependencies(frontmatter.get("dependencies"), wp_id=wp_id, wp_file=wp_file)


def _coerce_declared_dependencies(raw: object, *, wp_id: str, wp_file: Path) -> tuple[str, ...]:
    """Normalize a frontmatter ``dependencies`` value to a tuple of WP ids (pure).

    Legacy string forms (``"[]"``, ``"WP01, WP02"``, bare ``"WP01"``) go
    through ``WPMetadata``'s own coercion first; only a value that
    ``WPMetadata`` would also reject stays fail-closed.
    """
    if raw is None:
        return ()
    coerced = coerce_legacy_dependencies(raw)
    if isinstance(coerced, list) and all(isinstance(dep, str) for dep in coerced):
        return tuple(dep.strip() for dep in coerced if dep.strip())
    raise TransitionError(f"Cannot resolve the declared dependencies of {wp_id}: {wp_file} declares a malformed `dependencies` value ({raw!r})")


def _resolve_dependency_readiness(planning_feature_dir: Path, wp_id: str, snapshot: StatusSnapshot) -> DependencyReadiness:
    """The shells' dependency verdict (FR-013): declared deps x reduced write surface.

    Called INSIDE the lock/transaction with the snapshot the shell already
    reduced for ``from_lane``, so the verdict reflects the post-lock state of
    the write surface (never the pre-lock TOCTOU the guard exists to close)
    and costs no additional log read. Always returns a verdict -- a WP with no
    declared dependencies is *satisfied*, not ``None`` (C-004 reserves ``None``
    for direct guard-level callers).

    A WP file whose declared dependencies cannot be resolved (unparseable
    frontmatter, or a ``dependencies`` value ``WPMetadata`` would also refuse)
    yields an *unsatisfied* verdict rather than an error: the guard then
    refuses only ``planned -> claimed`` / ``claimed -> in_progress``, ``force``
    + actor + reason still overrides, and ``-> blocked``, ``-> canceled`` and
    the review edges are never affected by a corrupt planning artifact.
    """
    try:
        declared = _declared_dependencies(planning_feature_dir, wp_id)
    except TransitionError as exc:
        logger.warning("Dependency readiness of %s is unresolvable; refusing the guarded entry edges: %s", wp_id, exc)
        return unresolvable_readiness(wp_id, str(exc))
    return readiness_from_snapshot(snapshot, wp_id, declared)


def _build_done_evidence(evidence: dict[str, Any]) -> DoneEvidence:
    """Build a DoneEvidence dataclass from a raw dict.

    Raises TransitionError if the evidence dict is missing required
    fields (review.reviewer, review.verdict, review.reference).
    """
    review_data = evidence.get("review")
    if not isinstance(review_data, dict):
        raise TransitionError("Moving to done requires evidence with review.reviewer review.verdict, and review.reference")
    reviewer = review_data.get("reviewer")
    verdict = review_data.get("verdict")
    reference = review_data.get("reference")
    if not reviewer or not verdict or not reference or not str(reference).strip():
        raise TransitionError("Moving to done requires evidence with review.reviewer review.verdict, and review.reference")

    review_approval = ReviewApproval(
        reviewer=reviewer,
        verdict=verdict,
        reference=str(reference),
    )

    repos = [RepoEvidence(**r) for r in evidence.get("repos", [])]
    verification = [VerificationResult(**v) for v in evidence.get("verification", [])]

    return DoneEvidence(
        review=review_approval,
        repos=repos,
        verification=verification,
    )


def _infer_subtasks_complete(
    feature_dir: Path,
    wp_id: str,
    *,
    status_dir: Path | None = None,
    event_stream: EventStream | None = None,
) -> bool:
    """Infer subtask completion for a WP from the frontmatter-roster model.

    Mirrors the CLI door (``tasks_shared._check_unchecked_subtasks``) exactly
    (#2816 IC-10 / FR-016 / SC-010). The subtask **roster** (which task ids
    belong to ``wp_id``) is the authored ``subtasks:`` frontmatter list — static
    design intent — sourced via
    :func:`core.subtask_rows.authored_subtask_roster`, NOT ``tasks.md`` checkbox
    rows. **Completion** is resolved solely from the event-sourced reduced
    snapshot's ``subtasks`` slot via
    :func:`core.subtask_rows.unchecked_subtask_ids_from_snapshot`.

    ``feature_dir`` is the PRIMARY planning surface that owns the authored WP
    roster. ``status_dir`` is the topology-aware STATUS surface that owns the
    event log; flat missions default it to ``feature_dir``. Keeping these legs
    separate prevents coordination missions from reading completion out of the
    primary planning checkout.

    Fail-closed and symmetric with the CLI door: an empty authored roster is
    "nothing to block on" -> complete; a WP with an authored roster but an
    absent/silent snapshot slot has every roster id reported incomplete ->
    blocks. The ``tasks.md`` checkbox proxy is retired — a raw checkbox edit
    without ``mark-status`` no longer moves the gate (the D-13 incoherence is
    closed).
    """
    from specify_cli.core.subtask_rows import (  # noqa: PLC0415
        authored_subtask_roster,
        unchecked_subtask_ids_from_event_stream,
        unchecked_subtask_ids_from_snapshot,
    )

    roster = authored_subtask_roster(feature_dir, wp_id)
    if not roster:
        return True
    if event_stream is not None:
        return not unchecked_subtask_ids_from_event_stream(event_stream, wp_id, roster)
    return not unchecked_subtask_ids_from_snapshot(
        status_dir or feature_dir,
        wp_id,
        roster,
    )


def _infer_implementation_evidence(feature_dir: Path, wp_id: str) -> bool:
    """Infer implementation evidence from prior canonical events for this WP."""
    return _infer_implementation_evidence_from_event_stream(_store.read_event_stream(feature_dir), wp_id)


def _infer_implementation_evidence_from_event_stream(event_stream: EventStream, wp_id: str) -> bool:
    """Infer implementation evidence from an already-resolved canonical stream."""
    return any(event.wp_id == wp_id for event in event_stream.transitions)


def _read_status_phase(feature_dir: Path) -> int | None:
    """Return the parsed ``status_phase`` int from meta.json, or ``None``.

    ``None`` covers a missing meta.json, a malformed meta.json, and a
    non-numeric ``status_phase`` — every "the feature did not declare a numeric
    phase" case, degrading to OFF at both gate call sites without raising.
    Uses ``on_malformed="none"`` so both missing and malformed degrade to
    ``None``; a malformed-but-present file still logs the warning (existence
    check first).
    """
    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none")
    if meta is None:
        if (feature_dir / "meta.json").exists():
            logger.warning("Invalid meta.json in %s; skipping phase-1 gating", feature_dir)
        return None
    status_phase = meta.get("status_phase")
    try:
        return int(str(status_phase).strip())
    except (TypeError, ValueError):
        return None


# The transitional frontmatter ``lane`` mirror keys on ``status_phase`` (the
# runtime-slot snapshot authority is now unconditional — its predicate was
# deleted in the #2816 cutover). The lane-mirror gate is retained separately so
# it can be retired independently of the runtime-slot cutover (C-004).
def _legacy_lane_mirror_enabled(feature_dir: Path) -> bool:
    """Return True when the transitional frontmatter ``lane`` mirror is active.

    Governs whether :func:`_mirror_phase1_frontmatter_lane` still writes the
    legacy ``lane`` field. Keys on ``status_phase >= 1`` (phase-2 recognition:
    a mission advanced to ``status_phase: 2`` still mirrors — a strict ``"1"``
    equality would silently drop a phase-2 mission's lane mirror). Non-numeric
    / missing / malformed -> OFF. Retained per C-004 (the ``lane`` field is
    still frontmatter-authored; evicting it is a separate follow-up).
    """
    phase = _read_status_phase(feature_dir)
    return phase is not None and phase >= 1


def _match_wp_files(feature_dir: Path, wp_id: str) -> list[Path]:
    """Every ``tasks/`` markdown file whose name matches *wp_id* (pure, no logging).

    Zero matches means genuinely no WP file (case (a)); more than one means
    the canonical file is ambiguous, e.g. a rename leftover such as
    ``WP03.md`` alongside a surviving ``WP03-run-state.md`` (case (b)). The
    two cases carry different meaning to different callers -- :func:`_find_wp_file`
    collapses both to "no lane mirror to touch", while the dependency-guard
    read in :func:`_declared_dependencies` must not collapse them, since case
    (b) means the declarations are unresolvable, not absent.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return []

    wp_pattern = re.compile(rf"^{re.escape(wp_id)}(?:[-_.]|\.md$)")
    return [path for path in tasks_dir.glob("*.md") if path.name.lower() != "readme.md" and wp_pattern.match(path.name)]


def _find_wp_file(feature_dir: Path, wp_id: str) -> Path | None:
    """Locate the canonical WP markdown file for *wp_id* under tasks/.

    Used only by the phase-1 lane mirror: both zero matches and multiple
    matches collapse to ``None`` there (skip quietly) -- unlike the
    dependency-guard read, which must distinguish the two (see
    :func:`_match_wp_files`).
    """
    matches = _match_wp_files(feature_dir, wp_id)
    if len(matches) != 1:
        if len(matches) > 1:
            logger.warning(
                "Multiple work package files matched %s in %s; skipping phase-1 lane mirror",
                wp_id,
                feature_dir,
            )
        return None
    return matches[0]


def _mirror_phase1_frontmatter_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Mirror the canonical lane into legacy frontmatter only in phase-1 mode.

    This is a compatibility bridge for repos still marked ``status_phase: 1``.
    It never creates a new ``lane`` field; it only updates an already-present
    field so stale consumers can observe the canonical state during cutover.
    """
    if not _legacy_lane_mirror_enabled(feature_dir):
        return

    wp_file = _find_wp_file(feature_dir, wp_id)
    if wp_file is None:
        return

    try:
        wp_meta = read_wp_frontmatter(wp_file)
    except (FrontmatterError, ValidationError) as exc:
        logger.warning("Failed to read %s for phase-1 lane mirror: %s", wp_file, exc)
        return

    wp_meta_dict, _ = wp_meta
    if wp_meta_dict.lane is not None and str(wp_meta_dict.lane).strip() == lane:
        return

    frontmatter, body = read_frontmatter(wp_file)
    if _LEGACY_LANE_FIELD not in frontmatter:
        return
    frontmatter[_LEGACY_LANE_FIELD] = lane
    try:
        write_frontmatter(wp_file, frontmatter, body)
    except FrontmatterError as exc:
        logger.warning("Failed to write %s for phase-1 lane mirror: %s", wp_file, exc)


def _legacy_alias_collapses_to_current_lane(
    raw_lane: str,
    resolved_lane: str,
    from_lane: str,
) -> bool:
    """Return True when a legacy alias resolves to the WP's current lane.

    ``in_review`` used to exist as a separate waypoint before the canonical
    model collapsed review work into ``for_review``. Treating this as a no-op
    preserves compatibility without writing illegal self-transitions.
    """
    normalized = raw_lane.strip().lower()
    return normalized != resolved_lane and resolved_lane == from_lane


def _feature_status_lock_root(feature_dir: Path, repo_root: Path | None) -> Path:
    """Resolve the repo root used for per-feature status locking.

    Thin shim — delegates to the single shared implementation in
    :func:`specify_cli.workspace.root_resolver.resolve_status_lock_root`
    (WP02 / SC-002 consolidation).
    """
    from specify_cli.workspace.root_resolver import resolve_status_lock_root

    # Local annotation re-narrows the cross-module (``Any``) result to ``Path``.
    lock_root: Path = resolve_status_lock_root(feature_dir, repo_root)
    return lock_root


def _flat_subtasks_dir_resolver(
    feature_dir: Path,
    repo_root: Path | None,
    mission_slug: str,
    *,
    effective_root: Path | None = None,  # noqa: ARG001 -- deliberately dropped; see D-1 in design-notes/WP02-pipeline.md
) -> Path:
    """The flat shell's subtask-gate resolver: today's observable behaviour.

    Before the pipeline promotion the flat/primary shells never passed
    ``request.effective_root`` to ``resolve_subtasks_gate_dir`` while the
    transactional ``_prepare_event`` did. The pipeline threads it; this
    adapter preserves the flat shell's behaviour verbatim (D-1 in
    ``design-notes/WP02-pipeline.md``) until WP06 adjudicates the parity.
    """
    from specify_cli.missions._read_path_resolver import resolve_subtasks_gate_dir  # noqa: PLC0415

    resolved: Path = resolve_subtasks_gate_dir(feature_dir, repo_root, mission_slug)
    return resolved


def _has_legacy_overrides(legacy: dict[str, Any]) -> bool:
    """True when any legacy positional/keyword transition argument was supplied."""
    if any(value is not None for key, value in legacy.items() if key not in ("force", "execution_mode")):
        return True
    return bool(legacy["force"]) or legacy["execution_mode"] != "worktree"


def _coerce_transition_request(
    feature_dir: TransitionRequest | Path | None,
    legacy: dict[str, Any],
) -> TransitionRequest:
    """Normalise the two call shapes of ``emit_status_transition`` to one request.

    A ``TransitionRequest`` in the first position is used as-is (mixing it
    with legacy arguments is a ``TypeError``); otherwise the legacy arguments
    are packed into a fresh request. ``legacy`` keys are ``TransitionRequest``
    field names.
    """
    if isinstance(feature_dir, TransitionRequest):
        if _has_legacy_overrides(legacy):
            raise TypeError("emit_status_transition accepts either a TransitionRequest or legacy transition arguments, not both")
        return feature_dir
    return TransitionRequest(feature_dir=feature_dir, **legacy)


def _collapse_alias_in_place(
    feature_dir: Path,
    request: TransitionRequest,
    *,
    mission_slug: str,
    mission_id: str | None,
    from_lane: str,
    resolved_lane: str,
) -> StatusEvent:
    """Alias-collapse no-op arm of the flat shell: mirror only, nothing appended.

    Returns the same unpersisted synthetic ``StatusEvent`` the shell always
    returned for this arm (``evidence=None``), so callers see a lane-shaped
    result without a duplicate self-transition on the log.
    """
    wp_id = request.wp_id
    if wp_id is None or request.actor is None:  # guarded by the pipeline; keeps the type invariant explicit
        raise TypeError("emit_status_transition requires wp_id and actor")
    logger.info(
        "Collapsing legacy alias %s to existing lane %s for %s/%s",
        request.to_lane,
        resolved_lane,
        mission_slug,
        wp_id,
    )
    _mirror_phase1_frontmatter_lane(feature_dir, wp_id, resolved_lane)
    # #4327: normalize the inline moment fields exactly as the persisted arm
    # does (``prepare_transition`` already refused invalid values at the
    # shared boundary before choosing this arm); the synthetic event a
    # caller inspects must never carry an un-normalized gist/pointer shape a
    # persisted event would not.
    from .moment_fields import validate_review_ref, validate_summary

    summary = validate_summary(request.summary) if request.summary is not None else None
    review_ref = validate_review_ref(request.review_ref, repo_root=request.repo_root) if request.review_ref is not None else None
    return build_status_event(
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=resolved_lane,
        actor=request.actor,
        mission_id=mission_id,
        force=request.force,
        execution_mode=request.execution_mode,
        reason=request.reason,
        reason_source=request.reason_source,
        review_ref=review_ref,
        summary=summary,
        evidence=None,
        review_result=request.review_result,
        policy_metadata=request.policy_metadata,
    )


def _persist_prepared(feature_dir: Path, prepared: PreparedTransition, event: StatusEvent) -> None:
    """Step 5 of the flat shell: atomic append -> materialize -> lane mirror.

    Runs under the shell's ``feature_status_lock``. The transition and its
    claim annotation are persisted as one unit: a resolved binding must never
    lag behind the claim it describes.

    WP03/FR-008/contract-G1: when ``event.review_result`` is set (any
    outbound-from-``in_review`` transition), THIS append is the single
    authoritative durability write for the recorded verdict -- see the module
    docstring. Reused unconditionally for every transition (C-001); no
    second, bespoke persistence path exists for verdicts.
    """
    annotation = prepared.annotation
    _store.append_event_stream_atomic_verified(
        feature_dir,
        [event, *([annotation] if annotation is not None else [])],
    )
    try:
        _reducer.materialize(feature_dir)
    except Exception:
        logger.warning(
            "Materialization failed after event %s was persisted; run 'status materialize' to recover",
            event.event_id,
        )
    if prepared.mirror_frontmatter_lane:
        _mirror_phase1_frontmatter_lane(feature_dir, event.wp_id, prepared.resolved_lane)


def emit_status_transition(  # NOSONAR — central orchestration hub; 15 of 20 params are optional with stable defaults; refactor tracked separately
    feature_dir: TransitionRequest | Path | None = None,
    _legacy_mission_slug: str | None = None,
    wp_id: str | None = None,
    to_lane: str | None = None,
    actor: ActorField | None = None,
    *,
    mission_dir: Path | None = None,
    mission_slug: str | None = None,
    force: bool = False,
    reason: str | None = None,
    reason_source: str | None = None,
    evidence: dict[str, Any] | None = None,
    review_ref: str | None = None,
    workspace_context: str | None = None,
    subtasks_complete: bool | None = None,
    implementation_evidence_present: bool | None = None,
    execution_mode: str = "worktree",
    repo_root: Path | None = None,
    policy_metadata: dict[str, Any] | None = None,
    review_result: Any = None,
    ensure_sync_daemon: bool = True,
    sync_dossier: bool = True,  # noqa: ARG001 -- 3.2.6 compatibility; fan-out retired by #677
    fan_out: bool = True,
) -> StatusEvent:
    """Flat/primary composition shell over :func:`prepare_transition`.

    Performs the whole write path for a flat / ``SINGLE_BRANCH`` / ``LANES``
    mission (contract ``emit-pipeline.md`` §2, flat column): acquire the
    mission status lock, derive ``from_lane`` once, run the status-owned
    pipeline, persist atomically, materialize, mirror, release, then fan out.
    Validation and event construction live in the pipeline -- this shell
    never calls ``validate_transition`` itself (P-2).

    Validation failures raise TransitionError BEFORE any data is
    persisted. SaaS failures never block canonical persistence.

    Args:
        feature_dir: Path to the kitty-specs mission directory, or a
            ``TransitionRequest`` for the request-object call path.
        mission_slug: Mission identifier (e.g. "034-mission-name").
        wp_id: Work package identifier (e.g. "WP01").
        to_lane: Target lane (canonical or alias).
        actor: Identity of the actor performing the transition.
        force: If True, bypass guard conditions (requires actor + reason).
        reason: Reason for the transition (required for force and some guards).
        evidence: Evidence dict for done transitions.
        review_ref: Review feedback reference (required for for_review -> in_progress).
        workspace_context: Active workspace context identifier.
        subtasks_complete: Whether subtasks are complete for review handoff.
        implementation_evidence_present: Whether implementation evidence is present.
        execution_mode: "worktree" or "direct_repo".
        repo_root: Repository root for SaaS fan-out (optional).
        policy_metadata: Orchestrator policy metadata dict (optional).
        review_result: Structured ReviewResult for in_review -> * transitions (optional).
        ensure_sync_daemon: If False, emit SaaS events without starting the local sync daemon.
        sync_dossier: Deprecated 3.2.6 compatibility keyword. Accepted as a
            no-op because the permanently-empty dossier fan-out registry was
            retired by issue #677.
        fan_out: When False, step 7 (SaaS + resolved-binding fan-out) is
            skipped and the persisted event is returned as-is. The coord
            fallback arm uses this to fan out only after its commit succeeds
            (FR-008 / SC-002); the default preserves immediate fan-out.

    Returns:
        The persisted StatusEvent.

    Raises:
        TransitionError: If the transition is invalid.
        specify_cli.status.store.StoreError: If the event log is corrupted.
    """
    request = _coerce_transition_request(
        feature_dir,
        {
            "_legacy_mission_slug": _legacy_mission_slug,
            "wp_id": wp_id,
            "to_lane": to_lane,
            "actor": actor,
            "mission_dir": mission_dir,
            "mission_slug": mission_slug,
            "force": force,
            "reason": reason,
            "reason_source": reason_source,
            "evidence": evidence,
            "review_ref": review_ref,
            "workspace_context": workspace_context,
            "subtasks_complete": subtasks_complete,
            "implementation_evidence_present": implementation_evidence_present,
            "execution_mode": execution_mode,
            "repo_root": repo_root,
            "policy_metadata": policy_metadata,
            "review_result": review_result,
        },
    )
    request_feature_dir = request.feature_dir or request.mission_dir
    request_mission_slug = request.mission_slug or request._legacy_mission_slug
    if request_feature_dir is None or request_mission_slug is None or request.wp_id is None or request.to_lane is None or request.actor is None:
        raise TypeError("emit_status_transition requires feature_dir/mission_dir, mission_slug, wp_id, to_lane, and actor")

    # WP03/T014/FR-013: route the feature_dir through the canonical-root
    # resolver. When the caller hands us a worktree-rooted path, this
    # rewrites it to the main repo's kitty-specs/<slug>/ so the event log
    # never lands in a stale worktree-local copy.
    canonical_feature_dir: Path = canonicalize_feature_dir(request_feature_dir)

    # Step 1: acquire. The lock is keyed on the mission directory NAME
    # (FR-004): colliding slugs no longer over-serialize and a bare legacy
    # slug serializes against its ordinary writers.
    lock_root = _feature_status_lock_root(canonical_feature_dir, request.repo_root)
    with feature_status_lock(lock_root, canonical_feature_dir.name):
        # T023: mission_id (ULID) from meta.json is the canonical machine-facing
        # identity for new events; None for legacy/pre-3.1.1 missions.
        mission_id = _load_mission_id(canonical_feature_dir)

        # Step 2: reduce the write surface once (NFR-004: the only full-log
        # read); ``from_lane`` and the dependency verdict both come from it.
        snapshot = _reduce_write_surface(canonical_feature_dir)
        from_lane = _derive_from_lane(canonical_feature_dir, request.wp_id, snapshot=snapshot)

        # Step 3: the dependency verdict, in-lock, against the write surface
        # (FR-013). The declaration reader resolves PRIMARY WP prompts even
        # when this flat shell writes a coord fallback surface.
        readiness = _resolve_dependency_readiness(canonical_feature_dir, request.wp_id, snapshot)

        # Step 4: the status-owned pipeline (validate + build; pure).
        prepared = prepare_transition(
            request=request,
            feature_dir=canonical_feature_dir,
            mission_slug=request_mission_slug,
            mission_id=mission_id,
            from_lane=from_lane,
            readiness=readiness,
            resolve_subtasks_dir=_flat_subtasks_dir_resolver,
        )
        if prepared.event is None:
            return _collapse_alias_in_place(
                canonical_feature_dir,
                request,
                mission_slug=request_mission_slug,
                mission_id=mission_id,
                from_lane=from_lane,
                resolved_lane=prepared.resolved_lane,
            )

        # Step 5: persist -> materialize -> mirror, still under the lock.
        _persist_prepared(canonical_feature_dir, prepared, prepared.event)

    # Step 7: fan-out after release (never blocks canonical persistence).
    if fan_out:
        _saas_fan_out(
            prepared.event,
            request_mission_slug,
            request.repo_root,
            policy_metadata=request.policy_metadata,
            ensure_sync_daemon=ensure_sync_daemon,
        )
        if prepared.annotation is not None:
            _resolved_binding_fan_out(prepared.annotation, request_mission_slug)

    return prepared.event


def _batch_request_identity(first: TransitionRequest) -> tuple[Path, str, str]:
    """Resolve the batch's shared (feature_dir, mission_slug, wp_id) from its first request."""
    feature_dir = first.feature_dir or first.mission_dir
    mission_slug = first.mission_slug or first._legacy_mission_slug
    wp_id = first.wp_id
    if feature_dir is None or mission_slug is None or wp_id is None:
        raise TypeError("emit_status_transition_batch requires feature_dir/mission_dir, mission_slug, and wp_id")
    return canonicalize_feature_dir(feature_dir), mission_slug, wp_id


def _check_batch_request_identity(
    request: TransitionRequest,
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
) -> None:
    """Refuse a batch member that is incomplete or targets another mission/WP.

    Runs BEFORE the lock is acquired: ``canonicalize_feature_dir`` consults
    the git worktree registry and no lock may be held across git (NFR-001).
    """
    request_feature_dir = request.feature_dir or request.mission_dir
    request_mission_slug = request.mission_slug or request._legacy_mission_slug
    if request_feature_dir is None or request_mission_slug is None or request.wp_id is None or request.to_lane is None or request.actor is None:
        raise TypeError("Each batch transition requires feature_dir/mission_dir, mission_slug, wp_id, to_lane, and actor")
    if canonicalize_feature_dir(request_feature_dir) != feature_dir or request_mission_slug != mission_slug or request.wp_id != wp_id:
        raise TypeError("emit_status_transition_batch only supports one feature/mission/wp per batch")


def _prepare_batch(
    requests: list[TransitionRequest],
    *,
    feature_dir: Path,
    mission_slug: str,
    mission_id: str | None,
    from_lane: str,
    readiness: DependencyReadiness,
) -> list[tuple[StatusEvent, PreparedTransition, TransitionRequest]]:
    """Run the pipeline per request, chaining ``from_lane`` in memory.

    ``from_lane`` advances from each prepared event's ``resolved_lane`` so the
    batch never re-reads the log (NFR-004). Alias-collapse members are skipped
    exactly as before the promotion (no event, no mirror). Any refusal raises
    before the caller appends anything: the batch is all-or-nothing.

    ``readiness`` is the in-lock verdict for the batch's single WP. A batch
    only ever moves that one WP, and a WP's verdict depends on its
    *dependencies'* lanes, which the batch cannot change -- so the verdict
    resolved against the write surface at acquisition is the verdict for every
    member, including those reached through the accumulated in-memory state.

    Fail-closed on a missing workspace (#946): this door alone passes
    ``default_workspace_context=False``, so a member that omits
    ``workspace_context`` on ``claimed -> in_progress`` is refused by the
    pipeline's guard ("requires workspace context") instead of being handed a
    synthetic ``<execution_mode>:<root>``. WP02 of mission
    ``fsm-write-path-integrity-01M1TZV6`` dropped that skip for door parity
    (D-2); operator decision 2026-09-07 reinstated it (mission-review
    DRIFT-3). The rule lives in the pipeline as a policy knob, not here.
    """
    built: list[tuple[StatusEvent, PreparedTransition, TransitionRequest]] = []
    batch_started_at = now_utc()
    for request in requests:
        prepared = prepare_transition(
            request=request,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            from_lane=from_lane,
            readiness=readiness,
            at=(batch_started_at + timedelta(microseconds=len(built))).isoformat(),
            resolve_subtasks_dir=_flat_subtasks_dir_resolver,
            default_workspace_context=False,
        )
        if prepared.event is None:
            continue
        built.append((prepared.event, prepared, request))
        from_lane = prepared.resolved_lane
    return built


def emit_status_transition_batch(
    requests: list[TransitionRequest],
    *,
    ensure_sync_daemon: bool = True,
    sync_dossier: bool = True,  # noqa: ARG001 -- 3.2.6 compatibility; fan-out retired by #677
    fan_out: bool = True,
) -> list[StatusEvent]:
    """Validate and persist a same-WP transition sequence atomically.

    Composite operations such as implementation start have multiple legal lane
    edges but one user-visible lifecycle action. This is the batch variant of
    the flat/primary shell (contract ``emit-pipeline.md`` §2): ONE
    ``feature_status_lock`` acquisition (FR-018) covers the single from-lane
    derivation, every per-request :func:`prepare_transition`, the single
    atomic append, the materialize and the lane mirrors; fan-out follows the
    release. The full sequence is validated before any write -- a refused
    member persists nothing. ``sync_dossier`` remains an accepted no-op
    keyword for 3.2.6 callers after retirement of the permanently-empty
    dossier fan-out registry in issue #677; ``fan_out=False`` skips step 7 for
    the coord fallback arm (FR-008).
    """
    if not requests:
        return []

    feature_dir, mission_slug, wp_id = _batch_request_identity(requests[0])
    for request in requests:
        _check_batch_request_identity(request, feature_dir=feature_dir, mission_slug=mission_slug, wp_id=wp_id)

    lock_root = _feature_status_lock_root(feature_dir, requests[0].repo_root)
    with feature_status_lock(lock_root, feature_dir.name):
        mission_id = _load_mission_id(feature_dir)
        # One reduce of the write surface (NFR-004) feeds both the batch's
        # starting ``from_lane`` and its in-lock dependency verdict (FR-013).
        snapshot = _reduce_write_surface(feature_dir)
        from_lane: str = str(_derive_from_lane(feature_dir, wp_id, snapshot=snapshot))
        readiness = _resolve_dependency_readiness(feature_dir, wp_id, snapshot)
        built = _prepare_batch(
            requests,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            from_lane=from_lane,
            readiness=readiness,
        )
        if not built:
            return []

        events = [event for event, _prepared, _request in built]
        annotations: list[InnerStateChanged] = [prepared.annotation for _event, prepared, _request in built if prepared.annotation is not None]
        _store.append_event_stream_atomic_verified(feature_dir, [*events, *annotations])

        try:
            _reducer.materialize(feature_dir)
        except Exception:
            logger.warning(
                "Materialization failed after batch ending in event %s was persisted; run 'status materialize' to recover",
                events[-1].event_id,
            )

        for event in events:
            _mirror_phase1_frontmatter_lane(feature_dir, event.wp_id, str(event.to_lane))

    if fan_out:
        for event, _prepared, request in built:
            _saas_fan_out(
                event,
                mission_slug,
                request.repo_root,
                policy_metadata=request.policy_metadata,
                ensure_sync_daemon=ensure_sync_daemon,
            )
        for annotation in annotations:
            _resolved_binding_fan_out(annotation, mission_slug)

    return events


def emit_inner_state_changed(
    feature_dir: Path,
    wp_id: str,
    delta: WPInnerStateDelta,
    *,
    actor: str,
    mission_slug: str,
    at: str | None = None,
    repo_root: Path | None = None,
) -> InnerStateChanged:
    """Persist a single off-axis ``InnerStateChanged`` annotation.

    This is the public emit API downstream WPs call to record runtime-state
    changes (``shell_pid``, subtask marks, notes, tracker refs, reassignment,
    review overrides) without traversing the FSM.

    Pipeline:
        1. Resolve the write target via ``canonicalize_feature_dir(feature_dir)``
           — never ``Path.cwd()`` (FR-012 / C-003 / #2647).
        2. Mint a real ULID and build the typed event via the sanctioned
           ``wp_state.annotate()`` non-transition seam (which refuses an empty
           delta and validates ``wp_id``).
        3. Persist through the durability-verified store append seam under the
           per-feature status lock, then best-effort materialize the snapshot.

    Args:
        feature_dir: kitty-specs feature directory (canonicalized here).
        wp_id: Target work-package id (e.g. ``"WP01"``).
        delta: Typed partial runtime-state payload. An empty delta is refused.
        actor: Identity of the actor causing the change.
        mission_slug: Mission identifier used for resolved-binding fan-out.
        at: Optional ISO-8601 occurrence timestamp; defaults to now.
        repo_root: Optional repo root for status-lock resolution.

    Returns:
        The persisted :class:`InnerStateChanged`.

    Raises:
        ValueError: for a malformed ``wp_id`` or an empty delta.
        specify_cli.status.store.StoreError: if persistence/readback fails.
    """
    feature_dir = canonicalize_feature_dir(feature_dir)

    event = annotate(
        wp_id,
        delta,
        actor=actor,
        at=at or now_utc_iso(),
        event_id=_generate_ulid(),
    )

    lock_root = _feature_status_lock_root(feature_dir, repo_root)
    with feature_status_lock(lock_root, feature_dir.name):
        _store.append_annotations_atomic_verified(feature_dir, [event])
        try:
            _reducer.materialize(feature_dir)
        except Exception:
            logger.warning(
                "Materialization failed after annotation %s was persisted; run 'status materialize' to recover",
                event.event_id,
            )

    # First-class resolved-binding bridge (FR-015 / IC-09, T049). Additive and
    # best-effort — runs AFTER the annotation is durably persisted + materialized,
    # so it can never alter local persistence or the reduced snapshot. A non-
    # binding annotation is a no-op; a binding annotation fans out when the events
    # package supports it, else logs an intentional skip (version-gated).
    _resolved_binding_fan_out(event, mission_slug)

    return event


#: The resolved-binding delta slots (FR-013) that make an ``InnerStateChanged`` a
#: genuine binding change worth a ``WPResolvedBindingChanged`` fan-out. A delta
#: touching none of these (e.g. a ``shell_pid``/note/subtask annotation) is not a
#: binding change and never bridges.
_RESOLVED_BINDING_DELTA_FIELDS: tuple[str, ...] = (
    "role",
    "agent_profile",
    "agent_profile_version",
    "model",
    "provider",
)


def _resolved_binding_fan_out(event: InnerStateChanged, mission_slug: str) -> None:
    """Version-gated ``WPResolvedBindingChanged`` fan-out for a binding change.

    ``emit_inner_state_changed`` has no fan-out of its own; this adds the
    first-class resolved-binding bridge (spec-kitty ↔ spec-kitty-saas) additively.
    Only an annotation that actually carries a resolved binding fans out — a plain
    runtime annotation (``shell_pid``/note/subtask) is a no-op here.

    Gated exactly like the genesis gate (:data:`_EVENTS_SUPPORTS_RESOLVED_BINDING`
    / :func:`_saas_fan_out`): when the installed ``spec_kitty_events`` lacks
    ``WPResolvedBindingChanged`` the fan-out is a **logged, intentional skip**,
    never a swallowed ``ValidationError``, and canonical local state is untouched.
    The concrete payload model is built by the registered sync handler once 6.2.0
    ships; the status layer only feature-detects via the gate and hands off kwargs
    (the same handoff shape as :func:`_saas_fan_out` — no local type definition).
    """
    delta = event.delta
    binding = {name: getattr(delta, name) for name in _RESOLVED_BINDING_DELTA_FIELDS}
    if all(value is None for value in binding.values()):
        return  # not a resolved-binding annotation — nothing to bridge

    if not _EVENTS_SUPPORTS_RESOLVED_BINDING:
        logger.info(
            "Skipping WPResolvedBindingChanged fan-out (wp_id=%s mission_slug=%s); "
            "installed spec_kitty_events lacks WPResolvedBindingChanged (needs "
            ">=6.2.0). Canonical local state is unaffected.",
            event.wp_id,
            mission_slug,
        )
        return

    fire_resolved_binding_fanout(
        wp_id=event.wp_id,
        # ``mission_slug`` is the canonical identity (Terminology Canon); no
        # ``feature_slug`` alias is introduced on this new write path.
        mission_slug=mission_slug,
        actor=event.actor,
        causation_id=event.event_id,
        occurred_at=event.at,
        **binding,
    )


def build_resolved_actor(
    *,
    role: str,
    tool: str | None,
    binding: ResolvedBinding | None,
    self_profile: str | None = None,
    self_model: str | None = None,
) -> dict[str, str | None]:
    """Structured ``{role, profile, tool, model}`` actor for the IC-09 fan-out.

    ``spec_kitty_events`` 6.1.0 ``StatusTransitionPayload.actor`` already accepts
    ``Union[str, Dict]`` — so no shared-package change is needed to carry this
    shape. The dict form lets the SaaS fan-out ride the transition's *resolved*
    identity rather than the bare ``--agent`` tool string.

    The ``model``/``profile`` prefer the genuine dispatch-resolved binding; when
    no binding is present (or the binding leaves a segment unresolved),
    ``self_model``/``self_profile`` (FR-005) carry a **self-asserted** value
    parsed from the ``--agent`` boundary string — never a synthetic default. An
    absent value on both sides stays a plain ``None`` (the ``RESOLVED_MODEL_ABSENT``
    delta sentinel is a reduced-slot concern, not an actor concern).

    .. note:: WP12 (FR-015) landed the plumbing this seam waited on. The
       ``emit_status_transition`` / ``build_status_event`` / ``StatusEvent.actor``
       surfaces are now typed :data:`~specify_cli.status.models.ActorField`
       (``str | dict``), and ``decode_actor`` guards the ``from_dict`` round-trip,
       so a caller may pass this dict as the claim/review transition ``actor`` and
       it reaches ``_saas_fan_out`` (``fire_saas_fanout(actor=event.actor, …)``)
       uncorrupted. The ``emit_status_transition`` ``# NOSONAR`` hub was NOT
       inflated — the guard reads a projected string via ``actor_identity_str``.
       The off-transition binding change additionally bridges through the
       version-gated :func:`_resolved_binding_fan_out` (``WPResolvedBindingChanged``).
    """
    return {
        "role": role,
        "profile": (binding.agent_profile if binding is not None else None) or self_profile,
        "tool": tool,
        "model": (binding.model if binding is not None else None) or self_model,
    }


# Compatibility alias for the WP10 test/import surface.
_build_resolved_actor = build_resolved_actor


def parse_agent_boundary_string(
    raw: str,
) -> tuple[str, str | None, str | None, str | None]:
    """Parse the compact ``--agent`` CLI value into ``(tool, model, profile, role)``.

    THIN, non-synthesizing boundary parser for FR-005. Unlike
    :func:`specify_cli.status.wp_metadata._resolve_agent_from_colon_string` (the
    **persisted-frontmatter** parser, which fills an absent segment with a
    tool-derived synthetic default such as ``"unknown-model"`` or
    ``"{tool}-default"``), this parser leaves an absent segment as ``None`` —
    a self-asserted live-claim actor must never fabricate identity it was never
    given (C-002/C-007).

    Accepts both the bare ``tool`` form (``"claude"``) and the full compact
    ``tool:model:profile:role`` form; missing trailing segments and empty
    interior segments (``"claude::reviewer-renata:"``) both normalize to
    ``None``. Raises :class:`ValueError` for an empty ``tool`` segment — a
    tool is required to identify the agent at all.
    """
    segments = raw.split(":")
    while len(segments) < 4:
        segments.append("")
    tool, model_seg, profile_seg, role_seg = segments[:4]
    if not tool:
        raise ValueError(f"Empty agent tool in --agent value: {raw!r}")
    return tool, (model_seg or None), (profile_seg or None), (role_seg or None)


def build_self_asserting_actor(
    *,
    role: str,
    agent: str | None,
    fallback_tool: str | None,
    binding: ResolvedBinding | None,
) -> dict[str, str | None]:
    """Build a claim/review transition actor from a compact ``--agent`` value.

    THE single seam (FR-005) that every live claim/review call site routes
    through. It composes the two thin primitives —
    :func:`parse_agent_boundary_string` (parse the compact
    ``tool:model:profile:role`` string into a **bare** tool plus self-asserted
    profile/model, absent segments staying ``None``) and
    :func:`build_resolved_actor` (a genuine dispatch-resolved ``binding`` always
    wins; the self-asserted value only fills a gap the binding leaves open).

    Crucially, only the **parsed bare tool** ever reaches ``actor["tool"]`` — the
    whole compact ``--agent`` string must never land there (the #2861 leak this
    seam closes). When ``agent`` is falsy no parse happens and ``fallback_tool``
    carries the tool slot; a genuinely present ``agent`` always yields a
    non-empty parsed tool (the parser raises on an empty tool segment), so the
    fallback is only reached for a bindingless, agentless claim.

    No synthetic default is ever fabricated and no :class:`ResolvedBinding` is
    minted here (C-002/C-007): an identity segment absent on both the binding
    and the self-asserted parse stays a plain ``None``.
    """
    parsed_tool: str | None = None
    self_profile: str | None = None
    self_model: str | None = None
    if agent:
        parsed_tool, self_model, self_profile, _self_role = parse_agent_boundary_string(agent)
    return build_resolved_actor(
        role=role,
        tool=parsed_tool or fallback_tool,
        binding=binding,
        self_profile=self_profile,
        self_model=self_model,
    )


@dataclass(frozen=True)
class ResolvedBindingEmit:
    """Outcome of a resolved-binding claim-seam emit (FR-014 / T039).

    ``annotation`` is the persisted :class:`InnerStateChanged` — the latest-wins
    channel the IC-07 reconstruction reads — or ``None`` when no binding was
    threaded (a bare ``--agent`` claim with no dispatch context). ``structured_actor``
    is the ``{role, profile, tool, model}`` form staged for the IC-09 SaaS fan-out
    (consumed by WP12 once the emit signatures widen; see :func:`_build_resolved_actor`).
    """

    annotation: InnerStateChanged | None
    structured_actor: dict[str, str | None]


def emit_resolved_binding(
    feature_dir: Path,
    wp_id: str,
    *,
    mission_slug: str,
    actor: str,
    role: str,
    binding: ResolvedBinding | None,
    tool: str | None = None,
    repo_root: Path | None = None,
) -> ResolvedBindingEmit:
    """Record a claim seam's genuinely dispatch-resolved binding (FR-014 / T039).

    Emitted at BOTH the implement-claim and review-claim seams so the resolved
    identity folds **latest-wins** across the lifecycle. This is a mandatory
    complement to the ``policy_metadata`` claim fold, which the reducer applies
    ONLY on ``planned → claimed`` (``reducer._wp_state_from_event``): a
    review-claim (``for_review → in_review``) never hits that fold, so relying on
    it alone would freeze the resolved identity at the implementer's binding.
    The :class:`InnerStateChanged` annotation folds regardless of lane.

    When ``binding`` is ``None`` (a claim with no dispatch context) NO annotation
    is written — the resolved slots stay absent (a valid "never-reclaimed-with-
    dispatch" state per the resolved-binding contract). The structured actor is
    still produced for the caller (role + tool), so a future WP12 fan-out has an
    actor even for a bindingless claim.

    Args:
        feature_dir: kitty-specs feature directory (canonicalized by the emit).
        wp_id: Target work-package id (e.g. ``"WP01"``).
        mission_slug: Mission identifier used for resolved-binding fan-out.
        actor: Identity of the actor performing the claim (the annotation actor).
        role: The *actual* role that ran at this seam (``"implementer"`` /
            ``"reviewer"``) — never the authored recommendation.
        binding: The dispatch-resolved binding, or ``None`` for no dispatch context.
        tool: The AI tool string (the ``--agent`` value) for the structured actor.
        repo_root: Optional repo root for status-lock resolution.

    Returns:
        A :class:`ResolvedBindingEmit` carrying the persisted annotation (or
        ``None``) and the staged structured actor.
    """
    structured_actor = build_resolved_actor(role=role, tool=tool, binding=binding)
    if binding is None:
        return ResolvedBindingEmit(annotation=None, structured_actor=structured_actor)
    annotation = emit_inner_state_changed(
        feature_dir,
        wp_id,
        binding.to_delta(role=role),
        actor=actor,
        mission_slug=mission_slug,
        repo_root=repo_root,
    )
    return ResolvedBindingEmit(annotation=annotation, structured_actor=structured_actor)


def _saas_fan_out(
    event: StatusEvent,
    mission_slug: str,
    repo_root: Path | None,
    *,
    policy_metadata: dict[str, Any] | None = None,
    ensure_sync_daemon: bool = True,
) -> None:
    """Conditionally fan out a SaaS telemetry event via the registered handlers.

    Routes through specify_cli.status.adapters.fire_saas_fanout, which
    is non-raising and a no-op when no sync handler has been registered
    (e.g., 0.1x branch or test environments without sync imported).
    Canonical status persistence is never affected by handler failures.

    Genesis compatibility gate (T022, WP04):
    When the installed spec_kitty_events does not support the genesis lane
    (i.e., spec_kitty_events < 6.0.0), fan-out for genesis transitions is
    deliberately skipped. This is a logged, intentional skip — NOT a silent
    swallowed ValidationError. Once spec_kitty_events 6.0.0 (genesis lane) is
    installed, this gate resolves True and genesis seeds fan out normally.
    """
    from_lane_str = str(event.from_lane)
    to_lane_str = str(event.to_lane)
    if (from_lane_str == "genesis" or to_lane_str == "genesis") and not _EVENTS_SUPPORTS_GENESIS:
        logger.info(
            "Skipping SaaS fan-out for genesis transition (wp_id=%s from=%s to=%s); "
            "installed spec_kitty_events lacks the genesis lane (needs >=6.0.0). "
            "Canonical local state is unaffected.",
            event.wp_id,
            from_lane_str,
            to_lane_str,
        )
        return

    # WPStatusChangeMetadata lives in the CORE status layer (not sync/INTEGRATION),
    # so importing it here does not cross the CORE→INTEGRATION boundary that
    # test_integration_boundary.py enforces; the actual SaaS wiring still routes
    # only through the status/adapters observer registry (fire_saas_fanout).
    from specify_cli.status.wp_status_metadata import WPStatusChangeMetadata

    fire_saas_fanout(
        wp_id=event.wp_id,
        from_lane=str(event.from_lane),
        to_lane=str(event.to_lane),
        # Deliver the actor verbatim (FR-015 / IC-09): a resolved-binding claim
        # carries a ``{role, profile, tool, model}`` dict — which spec_kitty_events
        # 6.1.0 ``StatusTransitionPayload.actor`` already accepts (Union[str, Dict])
        # — while a plain-string actor (the common case) fans out exactly as
        # before. No dict is ever fabricated for a bare string (defensive
        # feature-detection is the pass-through itself).
        actor=event.actor,
        mission_slug=mission_slug,
        mission_id=event.mission_id,
        # Producer occurrence time: thread the canonical local lane-transition
        # time so SaaS persists Event.occurred_at = StatusEvent.at, not the
        # sync-emission clock (Rule R-T-01 in spec-kitty-events).
        metadata=WPStatusChangeMetadata.from_status_event(event, policy_metadata=policy_metadata),
        ensure_daemon=ensure_sync_daemon,
        # The emitting checkout root, so the Zeitgeist bridge resolves relay
        # credentials from it instead of the process cwd (#125).
        repo_root=repo_root,
    )
