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

Phase 2 of mission consolidation-window-provenance keeps every per-mode quirk exactly, so no verdict
changes (C-004): the forecast passes no excluded canceled work packages, uses the live
``mission_branch`` NAME as its coordination base and reads its own status directory; the gate's
defensive rebuild keeps the live ``mission_branch`` name through ``coord_base_override``. WP17
aligns the forecast, WP18 starts reading :attr:`ClaimInputs.dependency_anchors`.

This module never writes: persisting the pre-mutation anchors stays with the claim phase
(``phase_claim._resolve_pre_mutation_*``), which runs before the constructor, as do the resume's
fail-closed anchor checks. It imports no executor-family module and never touches the event log or
the rollback snapshot (CI-4, C-009).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from specify_cli.consolidation.reconciliation import ApprovedWpCommitSet, build_approved_wp_set
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.lanes.compute import lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import LanesManifest

__all__ = [
    "ClaimInputContext",
    "ClaimInputSource",
    "ClaimInputs",
    "build_claim",
    "claim_inputs",
    "live_lane_tips",
]

_PLANNING_LANE_ID = "lane-planning"
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
            ``mission_branch`` NAME for the forecast and the gate rebuild (Phase 2 quirk).
        lane_tips: Created lane branch -> tip SHA, the key space of
            ``ConsolidationState.pre_interrupt_lane_tips`` (no planning lane, no fully canceled lane).
        dependency_anchors: The subset of :attr:`lane_tips` whose lane another lane depends on
            (created dependency-lane branch -> tip SHA). Computed here, not passed to the builder in
            this phase; WP18 makes it the one anchor set of the closed world (FR-015).
        dependency_refs: The declared external dependency refs (#6771).
        dependency_pins: Declared ref -> the SHA it was verified against.
        excluded_canceled_wp_ids: Canceled work packages excluded from the claim.
        strategy: The consolidation strategy value (``squash``, ``merge`` or ``rebase``).
        status_dir: The status directory the claim reads.
    """

    source: ClaimInputSource
    target_base: str | None
    coord_base: str
    lane_tips: Mapping[str, str]
    dependency_anchors: Mapping[str, str]
    dependency_refs: tuple[str, ...]
    dependency_pins: Mapping[str, str]
    excluded_canceled_wp_ids: frozenset[str]
    strategy: str
    status_dir: Path


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
            ``state.json``, so ``SAVED`` reads them from here too).
        coord_base_override: An explicit coordination base that replaces the resolved one: the gate
            rebuild's live ``mission_branch`` name (Phase 2 quirk, T052). Not a fourth source.
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


def live_lane_tips(repo_root: Path, manifest: LanesManifest, excluded_canceled_wp_ids: frozenset[str]) -> dict[str, str]:
    """Every lane's CREATED branch -> its live tip, over the lanes ``pre_interrupt_lane_tips`` keys.

    Skips the ``lane-planning`` lane (its "tip" is the moving target) and a fully canceled lane
    (its branch may never have been created); a branch that does not resolve contributes nothing,
    as in ``phase_claim._capture_pre_interrupt_lane_tips``.
    """
    tips: dict[str, str] = {}
    for lane in manifest.lanes:
        if lane.lane_id == _PLANNING_LANE_ID or lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = lane_created_branch(manifest, lane.lane_id)
        tip = capture_branch_tip(repo_root, branch)
        if tip is not None:
            tips[branch] = tip
    return tips


def _dependency_anchors(manifest: LanesManifest, lane_tips: Mapping[str, str]) -> Mapping[str, str]:
    """The entries of *lane_tips* whose lane another lane of *manifest* depends on."""
    known = {lane.lane_id for lane in manifest.lanes}
    dependency_ids = {lane_id for lane in manifest.lanes for lane_id in lane.depends_on_lanes if lane_id in known}
    branches = {lane_created_branch(manifest, lane_id) for lane_id in dependency_ids}
    return _frozen({branch: sha for branch, sha in lane_tips.items() if branch in branches})


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


def _live(context: ClaimInputContext) -> ClaimInputs:
    """The forecast's inputs, with its Phase 2 quirks: no excluded set, the live ``mission_branch`` name."""
    excluded: frozenset[str] = frozenset()
    lane_tips = live_lane_tips(context.repo_root, context.manifest, excluded)
    return ClaimInputs(
        source=ClaimInputSource.LIVE,
        target_base=context.resolved_target_base,
        coord_base=context.manifest.mission_branch,
        lane_tips=_frozen(lane_tips),
        dependency_anchors=_dependency_anchors(context.manifest, lane_tips),
        dependency_refs=tuple(context.dependency_refs),
        dependency_pins=_frozen(context.dependency_pins),
        excluded_canceled_wp_ids=excluded,
        strategy=context.strategy,
        status_dir=context.status_dir,
    )


def _live_then_saved(context: ClaimInputContext) -> ClaimInputs:
    """A fresh run's inputs: the values the claim phase resolved (and saved) before any mutation."""
    lane_tips = live_lane_tips(context.repo_root, context.manifest, context.excluded_canceled_wp_ids)
    return ClaimInputs(
        source=ClaimInputSource.LIVE_THEN_SAVED,
        target_base=context.resolved_target_base,
        coord_base=_run_coord_base(context, context.resolved_coord_sha),
        lane_tips=_frozen(lane_tips),
        dependency_anchors=_dependency_anchors(context.manifest, lane_tips),
        dependency_refs=tuple(context.dependency_refs),
        dependency_pins=_frozen(context.dependency_pins),
        excluded_canceled_wp_ids=frozenset(context.excluded_canceled_wp_ids),
        strategy=context.strategy,
        status_dir=context.status_dir,
    )


def _saved(context: ClaimInputContext) -> ClaimInputs:
    """A resume's inputs, read from the saved record; a value it lacks keeps the call site's resolution (CI-3)."""
    state = context.state
    if state is None:
        raise ValueError("ClaimInputSource.SAVED needs the run's saved ConsolidationState")
    lane_tips = dict(state.pre_interrupt_lane_tips)
    return ClaimInputs(
        source=ClaimInputSource.SAVED,
        target_base=state.pre_mutation_target_sha or context.resolved_target_base,
        coord_base=_run_coord_base(context, state.pre_mutation_coord_sha or context.resolved_coord_sha),
        lane_tips=_frozen(lane_tips),
        dependency_anchors=_dependency_anchors(context.manifest, lane_tips),
        dependency_refs=tuple(state.dependency_refs),
        dependency_pins=_frozen(state.dependency_ref_pins),
        excluded_canceled_wp_ids=frozenset(context.excluded_canceled_wp_ids),
        strategy=state.strategy,
        status_dir=context.status_dir,
    )


_RESOLVERS = {
    ClaimInputSource.LIVE: _live,
    ClaimInputSource.LIVE_THEN_SAVED: _live_then_saved,
    ClaimInputSource.SAVED: _saved,
}


def claim_inputs(source: ClaimInputSource, context: ClaimInputContext) -> ClaimInputs:
    """The one constructor of a run's :class:`ClaimInputs` (CI-1): one resolver per source."""
    return _RESOLVERS[source](context)


def build_claim(repo_root: Path, manifest: LanesManifest, inputs: ClaimInputs) -> ApprovedWpCommitSet:
    """Build the reconciliation claim from *inputs* with the builder's keyword arguments of today.

    The forecast used to omit ``excluded_canceled_wp_ids``; the builder's default is ``()`` and it
    reads the argument through ``frozenset(...)``, so the forecast's empty frozenset passed here is
    the same call. Likewise the pins: the builder reads them through ``pins or {}`` and ``.get``,
    so a read-only mapping equals the dict the call sites passed.
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
    )
