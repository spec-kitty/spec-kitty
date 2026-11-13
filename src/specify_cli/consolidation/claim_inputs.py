"""The claim inputs of one consolidation run, built by one constructor (FR-012, IC-08).

The forecast, the fresh run and the resume all build the reconciliation claim with
:func:`~specify_cli.consolidation.reconciliation.build_approved_wp_set`. Before this module each
call site assembled the builder's inputs itself, so parity between the three was lost in the
inputs (research R-05). Now each call site describes what it already holds in a
:class:`ClaimInputContext`, asks :func:`claim_inputs` for a :class:`ClaimInputs` value from one of
three sources, and builds the claim through :func:`build_claim`.

Sources (data-model section 6):

* ``LIVE`` -- the forecast (``consolidate --dry-run``): every value read live.
* ``LIVE_THEN_SAVED`` -- a fresh run: read live and saved in ``state.json`` by the claim phase.
* ``SAVED`` -- a ``--resume``: read from the saved record, never live for a value the record holds
  (CI-3); a value the record lacks keeps the resolution the call site performed.

Phase 2 of mission consolidation-window-provenance kept every per-mode quirk so no verdict changed
(C-004). WP17 aligns the forecast with the fresh run (FR-013): ``LIVE`` excludes the canceled work
packages the fresh run excludes (:func:`~specify_cli.consolidation.done_bookkeeping.acceptably_canceled_wp_ids`,
read-only) and resolves its coordination base to the SHA the fresh run's claim phase captures (the
status surface ref, ``git rev-parse``d), falling back to the ``mission_branch`` name exactly where the
fresh run does. The forecast still reads its own status directory, and the gate's defensive rebuild
keeps the live ``mission_branch`` name through ``coord_base_override``. The status surface read is
the neutral :mod:`~specify_cli.consolidation.status_surface`, shared with the claim phase. WP18 (FR-015) makes
:attr:`ClaimInputs.dependency_anchors` of a ``SAVED`` value the ONE frozen anchor set of a resume:
:func:`build_claim` hands it to every claim-time reader of the closed-world anchors, and the
executor hands it to the approved-reviewed attestation check. ``LIVE`` and ``LIVE_THEN_SAVED`` pass
none, so the forecast and the fresh run read live, exactly as before.

This module never writes: persisting the pre-mutation anchors stays with the claim phase
(``phase_claim._resolve_pre_mutation_*``), which runs before the constructor, as do the resume's
fail-closed anchor checks. It imports no executor-family module, at module level or deferred, and never
touches the event log or the rollback snapshot (CI-4, C-009).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from specify_cli.consolidation.done_bookkeeping import acceptably_canceled_wp_ids
from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.consolidation.status_surface import status_surface_tip
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import LanesManifest

__all__ = [
    "ClaimInputContext",
    "ClaimInputSource",
    "ClaimInputs",
    "build_claim",
    "claim_inputs",
    "frozen_dependency_tips",
    "live_lane_tips",
]

_EMPTY: Mapping[str, str] = MappingProxyType({})


class ClaimInputSource(StrEnum):
    """Where a run's claim inputs come from."""

    LIVE = "live"
    LIVE_THEN_SAVED = "live_then_saved"
    SAVED = "saved"


@dataclass(frozen=True)
class ClaimInputs:
    """The inputs one claim build reads, as one immutable value (data-model section 6).

    Attributes:
        source: Which resolver produced the value.
        target_base: The target's pre-consolidation tip (the closed-world window base), or ``None``
            when the target ref did not resolve.
        coord_base: The coordination base the claim measures lanes from: a SHA, or the live
            ``mission_branch`` NAME when no status surface ref resolves, and for the gate rebuild
            (Phase 2 quirk).
        dependency_anchors: Created dependency-lane branch -> tip SHA, for every lane another lane
            depends on that is neither a planning lane nor fully canceled under the CURRENT excluded
            set, drawn from the lane tips in the key space of ``ConsolidationState.pre_interrupt_lane_tips``
            (``LIVE``: read live; ``LIVE_THEN_SAVED``: the tips the claim phase captured; ``SAVED``: the
            record's). For ``SAVED`` it is the resume's one frozen anchor set (FR-015), passed to the claim
            builder; a dependency lane the record froze no tip for is read live and named in
            :attr:`degraded_dependency_anchors`.
        dependency_refs: The declared external dependency refs (#6771).
        dependency_pins: Declared ref -> the SHA it was verified against.
        excluded_canceled_wp_ids: Canceled work packages excluded from the claim.
        strategy: The consolidation strategy value (``squash``, ``merge`` or ``rebase``).
        status_dir: The status directory the claim reads.
        mission_branch_tip: The Mission branch's tip, frozen (#7626): the record's pre-mutation snapshot
            when it holds one (a resume, the gate rebuild), else the tip read now (a fresh run's claim,
            which precedes the first mutation). Never read again later, so a branch merged into the
            Mission branch after this point is not trusted history. ``None`` when the branch is absent.
        degraded_dependency_anchors: ``SAVED`` only: the dependency-lane branches the saved record
            holds no frozen tip for (a record written without that tip, H1), read live instead -- the
            degraded anchors the ADR names. Empty for ``LIVE`` and ``LIVE_THEN_SAVED``.
    """

    source: ClaimInputSource
    target_base: str | None
    coord_base: str
    dependency_anchors: Mapping[str, str]
    dependency_refs: tuple[str, ...]
    dependency_pins: Mapping[str, str]
    excluded_canceled_wp_ids: frozenset[str]
    strategy: str
    status_dir: Path
    degraded_dependency_anchors: tuple[str, ...] = ()
    mission_branch_tip: str | None = None


@dataclass(frozen=True)
class ClaimInputContext:
    """What a call site already holds when it asks for its claim inputs.

    Attributes:
        repo_root: The main repository root.
        manifest: The Mission's lanes manifest.
        status_dir: The status directory the call site reads (the forecast's own, or the run's
            ``feature_dir``).
        strategy: The requested strategy value.
        resolved_target_base: The target base the call site resolved: the live target tip for the
            forecast, ``_resolve_pre_mutation_target_sha`` (persisted-or-captured) for the run.
        resolved_coord_sha: ``_resolve_pre_mutation_coord_sha`` (persisted-or-captured) for the run;
            ``None`` for the forecast or a Mission without a coordination checkpoint.
        checkpoint_sha: The live coordination checkpoint the claim phase captured, if any.
        state: The run's ``ConsolidationState`` (required for ``SAVED``).
        dependency_refs: The declared external dependency refs.
        dependency_pins: Their recorded pins.
        excluded_canceled_wp_ids: The run's excluded canceled work packages (not persisted in
            ``state.json``, so ``SAVED`` reads them from here too). ``LIVE`` ignores it and derives
            the set the fresh run would resolve (FR-013).
        coord_base_override: An explicit coordination base that replaces the resolved one: the gate
            rebuild's live ``mission_branch`` name (Phase 2 quirk, T052). Not a fourth source.
        mission_slug: The resolved Mission slug the run reads its status surface by (``LIVE`` derives
            the excluded canceled work packages from it); ``None`` falls back to the manifest's slug.
        prior: ``SAVED`` only: the resume's ``SAVED`` value built earlier in this run (for the
            approved-reviewed attestation check, before the record is loaded for the run). Its frozen
            anchor set and degraded branches are reused, never read again, so the attestation check and
            the claim read ONE anchor set (FR-015, L4); every other value is read from *state* as usual.
    """

    repo_root: Path
    manifest: LanesManifest
    status_dir: Path
    strategy: str
    resolved_target_base: str | None
    resolved_coord_sha: str | None = None
    checkpoint_sha: str | None = None
    state: ConsolidationState | None = None
    dependency_refs: tuple[str, ...] = ()
    dependency_pins: Mapping[str, str] = field(default_factory=dict)
    excluded_canceled_wp_ids: frozenset[str] = frozenset()
    coord_base_override: str | None = None
    mission_slug: str | None = None
    prior: ClaimInputs | None = None


def live_lane_tips(repo_root: Path, manifest: LanesManifest, excluded_canceled_wp_ids: frozenset[str]) -> dict[str, str]:
    """Every lane's CREATED branch -> its live tip, over the lanes ``pre_interrupt_lane_tips`` keys.

    The one lane-tip reader of a claim: the claim phase captures ``pre_interrupt_lane_tips`` with it
    (``phase_claim._capture_pre_interrupt_lane_tips``) and the forecast reads its tips with it. Skips
    the planning lane (:func:`~specify_cli.lanes.compute.is_planning_lane`; its "tip" is the moving
    target) and a fully canceled lane (its branch may never have been created); a branch that does not
    resolve contributes nothing.
    """
    tips: dict[str, str] = {}
    for lane in manifest.lanes:
        if is_planning_lane(lane) or lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = lane_created_branch(manifest, lane.lane_id)
        tip = capture_branch_tip(repo_root, branch)
        if tip is not None:
            tips[branch] = tip
    return tips


def _dependency_branches(manifest: LanesManifest, excluded_canceled_wp_ids: frozenset[str]) -> frozenset[str]:
    """Created branches of every lane another lane depends on, less planning and fully-canceled lanes.

    The lanes ``_closed_world_anchors`` anchors on. The fully-canceled test reads the CURRENT
    excluded set, so a dependency lane canceled since the interrupted run froze its tip is no anchor.
    """
    by_id = {lane.lane_id: lane for lane in manifest.lanes}
    dependency_ids = {lane_id for lane in manifest.lanes for lane_id in lane.depends_on_lanes if lane_id in by_id}
    return frozenset(
        lane_created_branch(manifest, lane_id)
        for lane_id in dependency_ids
        if not is_planning_lane(by_id[lane_id]) and not lane_fully_canceled(by_id[lane_id], excluded_canceled_wp_ids)
    )


def _dependency_anchors(manifest: LanesManifest, lane_tips: Mapping[str, str], excluded_canceled_wp_ids: frozenset[str]) -> Mapping[str, str]:
    """The entries of *lane_tips* whose lane is a dependency anchor of *manifest* (:func:`_dependency_branches`)."""
    branches = _dependency_branches(manifest, excluded_canceled_wp_ids)
    return _frozen({branch: sha for branch, sha in lane_tips.items() if branch in branches})


def _saved_dependency_anchors(context: ClaimInputContext, frozen_tips: Mapping[str, str]) -> tuple[Mapping[str, str], tuple[str, ...]]:
    """A resume's dependency anchors: the frozen tip of each dependency lane, else its live tip (degraded).

    Returns ``(anchors, degraded branches)``. A dependency lane the record froze no tip for is NOT
    dropped: it keeps today's live read (FR-015's degraded anchor), named so the claim phase can say
    so. A degraded branch that does not resolve contributes no SHA, and the closed world then reads
    its branch name, exactly as a fresh run would.
    """
    anchors = dict(_dependency_anchors(context.manifest, frozen_tips, context.excluded_canceled_wp_ids))
    degraded = tuple(sorted(_dependency_branches(context.manifest, context.excluded_canceled_wp_ids) - anchors.keys()))
    for branch in degraded:
        tip = capture_branch_tip(context.repo_root, branch)
        if tip is not None:
            anchors[branch] = tip
    return _frozen(anchors), degraded


def _frozen(mapping: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(mapping)) if mapping else _EMPTY


def _run_coord_base(context: ClaimInputContext, saved_coord_sha: str | None) -> str:
    """The run's coordination base: override, else saved/resolved SHA, else checkpoint, else ``mission_branch``.

    Exactly ``_capture_reconciliation_claim``'s ``coord_base_sha or checkpoint.sha or
    mission_branch`` (``is not None`` tests, as there); the override is the gate rebuild's.
    """
    if context.coord_base_override is not None:
        return context.coord_base_override
    if saved_coord_sha is not None:
        return saved_coord_sha
    if context.checkpoint_sha is not None:
        return context.checkpoint_sha
    mission_branch: str = context.manifest.mission_branch
    return mission_branch


def _mission_branch_tip(context: ClaimInputContext, *, read_live: bool = True) -> str | None:
    """The Mission branch's frozen tip: the record's pre-mutation snapshot, else (before any mutation) the tip as it stands.

    A resume (``read_live=False``) whose record holds a snapshot never reads the branch: the
    snapshot's entry or nothing, so a branch that moved during an interrupted run cannot become a
    trusted root. A record with NO snapshot was rebaselined after a full restore (#6770): no branch
    moved in this run yet, so the resume reads the tip as it stands, as a fresh run does (#7626
    follow-up, operator ruling: the operator's commits on the Mission branch between attempts are
    trusted history).
    """
    branch: str = context.manifest.mission_branch
    snapshot = context.state.pre_mutation_refs if context.state is not None else {}
    saved: str | None = snapshot.get(branch)
    if saved or (not read_live and snapshot):
        return saved
    # Local annotation re-narrows the callee's return type (the narrow-file mypy override erases it).
    tip: str | None = capture_branch_tip(context.repo_root, branch)
    return tip


def _mission_slug(context: ClaimInputContext) -> str:
    """The slug the run resolved, else the manifest's."""
    slug: str = context.mission_slug or context.manifest.mission_slug
    return slug


def _live_excluded_canceled(context: ClaimInputContext) -> frozenset[str]:
    """The canceled work packages the fresh run excludes, by the same read-only call (``executor.py``, FR-013).

    ``acceptably_canceled_wp_ids`` reduces the status surface through the read door and never
    writes; it fails open to an empty set on an unreadable surface, exactly as the fresh run does.
    """
    return frozenset(acceptably_canceled_wp_ids(context.repo_root, _mission_slug(context)))


def _live_coord_base(context: ClaimInputContext) -> str:
    """The coordination base a fresh run resolves before it persists anything (FR-013).

    The fresh run's claim phase captures the status surface tip (``run_state._capture_coord_checkpoint``,
    through the one neutral read :func:`~specify_cli.consolidation.status_surface.status_surface_tip`);
    with no SHA it falls back to the ``mission_branch`` name (``coord_base_sha or checkpoint.sha or
    mission_branch``). Read-only: placement resolution and ``rev-parse`` never seed or materialize a surface.
    """
    tip = status_surface_tip(context.repo_root, _mission_slug(context))
    if tip is not None:
        # Local annotation re-narrows to ``str`` (the narrow-file mypy override erases the callee's return type).
        sha: str = tip[1]
        return sha
    mission_branch: str = context.manifest.mission_branch
    return mission_branch


def _live(context: ClaimInputContext) -> ClaimInputs:
    """The forecast's inputs: the fresh run's excluded set and coordination base, read live and read-only (FR-013)."""
    excluded = _live_excluded_canceled(context)
    lane_tips = live_lane_tips(context.repo_root, context.manifest, excluded)
    return ClaimInputs(
        source=ClaimInputSource.LIVE,
        target_base=context.resolved_target_base,
        coord_base=_live_coord_base(context),
        dependency_anchors=_dependency_anchors(context.manifest, lane_tips, excluded),
        dependency_refs=tuple(context.dependency_refs),
        dependency_pins=_frozen(context.dependency_pins),
        excluded_canceled_wp_ids=excluded,
        strategy=context.strategy,
        status_dir=context.status_dir,
        mission_branch_tip=_mission_branch_tip(context),
    )


def _captured_lane_tips(context: ClaimInputContext) -> Mapping[str, str]:
    """The lane tips the claim phase captured into the record (``pre_interrupt_lane_tips``), else read live.

    A fresh run on a topology with a status surface checkpoint captures them just before the
    constructor runs (``phase_claim._resolve_pre_mutation_coord_sha``), with :func:`live_lane_tips`;
    reusing them keeps one read. A run that captured none (no checkpoint) reads them live.
    """
    captured = context.state.pre_interrupt_lane_tips if context.state is not None else {}
    if captured:
        return captured
    return live_lane_tips(context.repo_root, context.manifest, context.excluded_canceled_wp_ids)


def _live_then_saved(context: ClaimInputContext) -> ClaimInputs:
    """A fresh run's inputs: the values the claim phase resolved (and saved) before any mutation."""
    lane_tips = _captured_lane_tips(context)
    return ClaimInputs(
        source=ClaimInputSource.LIVE_THEN_SAVED,
        target_base=context.resolved_target_base,
        coord_base=_run_coord_base(context, context.resolved_coord_sha),
        dependency_anchors=_dependency_anchors(context.manifest, lane_tips, frozenset(context.excluded_canceled_wp_ids)),
        dependency_refs=tuple(context.dependency_refs),
        dependency_pins=_frozen(context.dependency_pins),
        excluded_canceled_wp_ids=frozenset(context.excluded_canceled_wp_ids),
        strategy=context.strategy,
        status_dir=context.status_dir,
        mission_branch_tip=_mission_branch_tip(context),
    )


def _saved(context: ClaimInputContext) -> ClaimInputs:
    """A resume's inputs, read from the saved record; a value it lacks keeps the call site's resolution (CI-3)."""
    state = context.state
    if state is None:
        raise ValueError("ClaimInputSource.SAVED needs the run's saved ConsolidationState")
    prior = context.prior
    if prior is not None and prior.source is ClaimInputSource.SAVED:
        anchors, degraded = prior.dependency_anchors, prior.degraded_dependency_anchors
    else:
        anchors, degraded = _saved_dependency_anchors(context, dict(state.pre_interrupt_lane_tips))
    return ClaimInputs(
        source=ClaimInputSource.SAVED,
        target_base=state.pre_mutation_target_sha or context.resolved_target_base,
        coord_base=_run_coord_base(context, state.pre_mutation_coord_sha or context.resolved_coord_sha),
        dependency_anchors=anchors,
        dependency_refs=tuple(state.dependency_refs),
        dependency_pins=_frozen(state.dependency_ref_pins),
        excluded_canceled_wp_ids=frozenset(context.excluded_canceled_wp_ids),
        strategy=state.strategy,
        status_dir=context.status_dir,
        degraded_dependency_anchors=degraded,
        mission_branch_tip=_mission_branch_tip(context, read_live=False),
    )


_RESOLVERS = {
    ClaimInputSource.LIVE: _live,
    ClaimInputSource.LIVE_THEN_SAVED: _live_then_saved,
    ClaimInputSource.SAVED: _saved,
}


def claim_inputs(source: ClaimInputSource, context: ClaimInputContext) -> ClaimInputs:
    """The one constructor of a run's :class:`ClaimInputs` (CI-1): one resolver per source."""
    return _RESOLVERS[source](context)


def frozen_dependency_tips(inputs: ClaimInputs) -> Mapping[str, str] | None:
    """The one frozen anchor set a claim built from *inputs* reads (FR-015): ``SAVED`` only, else ``None`` (live)."""
    return inputs.dependency_anchors if inputs.source is ClaimInputSource.SAVED else None


def build_claim(repo_root: Path, manifest: LanesManifest, inputs: ClaimInputs) -> ApprovedWpCommitSet:
    """Build the reconciliation claim from *inputs* with the builder's keyword arguments of today.

    Every source passes ``excluded_canceled_wp_ids`` (the forecast passes the fresh run's set since
    WP17). The pins: the builder reads them through ``pins or {}`` and ``.get``, so a read-only
    mapping equals the dict the call sites passed. A resume (``SAVED``) also passes its frozen
    dependency anchors (:func:`frozen_dependency_tips`, FR-015); the forecast and the fresh run pass
    ``None`` and keep their verdicts.
    """
    return build_approved_wp_set(
        repo_root,
        inputs.status_dir,
        manifest,
        coord_base_ref=inputs.coord_base,
        excluded_canceled_wp_ids=inputs.excluded_canceled_wp_ids,
        excluded_window_base=inputs.target_base,
        external_dependency_refs=inputs.dependency_refs,
        external_dependency_pins=inputs.dependency_pins,
        frozen_dependency_tips=frozen_dependency_tips(inputs),
        mission_branch_tip=inputs.mission_branch_tip,
    )
