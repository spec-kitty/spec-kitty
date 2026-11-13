"""Closed-world inputs of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP11).

The excluded-content collection and the declared external dependency refs (#6771): resolving a ref,
verifying it, and the pin check at the gate. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.consolidation._constants import (
    DEPENDENCY_REF_COVERS_MISSION_WORK,
    DEPENDENCY_REF_MOVED,
    DEPENDENCY_REF_UNREACHABLE,
    DEPENDENCY_REF_UNRESOLVED,
    DEPENDENCY_REF_UNVERIFIABLE,
    error_code_suffix,
)
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    commits_in_range,
    first_parent_commits_in_range,
    patch_id_of,
    resolve_commit,
    sha_reachable_from,
)
from specify_cli.consolidation.mission_base import MissionBase, MissionBaseProvenance, MissionBaseReason, pre_mission_history
from specify_cli.consolidation.reconciliation_authorship import _final_authored_walk
from specify_cli.consolidation.reconciliation_kernel import _lane_branch_for, _lane_tip_commits
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.lane_tip import LaneTipListingError, read_tip, recorded_tip_branches
from specify_cli.lanes.models import LanesManifest
from specify_cli.status import stamp_of

if TYPE_CHECKING:
    from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet

logger = logging.getLogger(__name__)

# Declared external dependency refs (#6771). A lane that merges a dependency branch's
# newer head in (a two-parent merge, so the lane is still reviewed on one tree) brings
# that branch's commits into the closed-world window. The window's authorship authority is
# each approved lane's OWN first-parent spine, so every one of those commits reads as
# "belongs to NO approved WP" and the landing is refused. The closed world cannot tell
# that apart from a removed WP riding a carrier lane by structure alone (#4945 is the same
# shape), so the operator DECLARES the ref: `specify_cli consolidate --dependency-ref`.
# These are the fail-closed refusals of a declaration that cannot be honoured; each names
# the declaration, because the operator has to fix the command, not the repository.
_REFUSE_DEPENDENCY_UNRESOLVED: str = (
    "external dependency ref '{ref}' does not resolve to a commit; declare a ref that resolves (a branch, tag or SHA), "
    "or drop --dependency-ref. Nothing was exempted" + error_code_suffix(DEPENDENCY_REF_UNRESOLVED)
)


_REFUSE_DEPENDENCY_NOT_MERGED: str = (
    "external dependency ref '{ref}' is not reachable from the mission branch {mission_branch} or from any lane branch, so the "
    "mission never merged it in and it cannot explain any content in the landing window. Nothing was exempted" + error_code_suffix(DEPENDENCY_REF_UNREACHABLE)
)


_REFUSE_DEPENDENCY_COVERS_MISSION_WORK: str = (
    "external dependency ref '{ref}' would exempt commit {sha} which sits on {spine} — an external dependency may never cover "
    "mission-authored work (that is exactly how a removed work package's commit rides a carrier lane). Nothing was exempted"
    + error_code_suffix(DEPENDENCY_REF_COVERS_MISSION_WORK)
)


_REFUSE_DEPENDENCY_MISSION_NAMESPACE: str = (
    "external dependency ref '{ref}' is named inside this Mission's own branch namespace ({namespace}); a Mission's branches hold "
    "mission-authored work, also after the branch is deleted or its work package is removed. Nothing was exempted"
    + error_code_suffix(DEPENDENCY_REF_COVERS_MISSION_WORK)
)


_REFUSE_DEPENDENCY_RECORDED_TIP: str = (
    "external dependency ref '{ref}' would exempt commit {sha}, which {recorded} — a Mission's recorded work tip is "
    "mission-authored work, whether or not its work package or lane branch still exists. Nothing was exempted"
    + error_code_suffix(DEPENDENCY_REF_COVERS_MISSION_WORK)
)


_REFUSE_DEPENDENCY_NO_WINDOW_BASE: str = (
    "dependency ref(s) {refs} are declared but the target's pre-run commit could not be resolved, so the window a "
    "declaration would exempt cannot be bounded (fail-closed). Nothing was exempted" + error_code_suffix(DEPENDENCY_REF_UNVERIFIABLE)
)


_REFUSE_DEPENDENCY_PROBE: str = "a git probe failed while {doing}: {exc}. Nothing was exempted" + error_code_suffix(DEPENDENCY_REF_UNVERIFIABLE)


_REFUSE_DEPENDENCY_MOVED: str = (
    "external dependency ref '{ref}' was pinned to {pinned} when this consolidation claimed it, but now resolves to {now}. "
    "A declaration is verified once, against the commit it named; a moved ref would exempt different history than the one "
    "that was verified. Restore the ref to {pinned}, or run `spec-kitty consolidate --abort` and re-run with the new ref" + error_code_suffix(DEPENDENCY_REF_MOVED)
)


def _collect_excluded(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    coord_base_ref: str,
    excluded_canceled_wp_ids: frozenset[str],
    *,
    authored_shas: frozenset[str] = frozenset(),
    authored_patch_ids: frozenset[str] = frozenset(),
) -> tuple[frozenset[str], frozenset[str]]:
    """Canceled WP ids → their lane-tip commit SHAs + patch-ids (RN-F4), COMMIT-granular (#5018).

    Sourced from ``acceptably_canceled_wp_ids`` (mapped to lane tips by the
    caller) so a canceled lane's commits — including cherry-picked/re-lettered
    copies caught by patch-id — never land. Empty when no provenance-canceled WP
    exists; the verifier's excluded check stays non-vacuous regardless.

    A lane qualifies (the ``any(...)`` guard) the moment it lists ANY
    canceled-with-provenance WP — that stays LANE-granular, because a lane is one
    shared branch and there is no cheaper way to find "does this lane need
    narrowing at all". Within a qualifying (possibly MIXED) lane, though, the
    excluded set is narrowed to COMMIT granularity (C-001: granularity, not
    strictness) by subtracting *authored_shas* / *authored_patch_ids* — the
    approved lanes' OWN first-parent authorship (:func:`_collect_authored`,
    computed BEFORE this call in :func:`build_approved_wp_set`) — from the
    qualifying lane's tip commits: ``excluded_shas ← lane_tips − authored_shas``,
    ``excluded_patch_ids ← lane_patch_ids − authored_patch_ids``. A survivor WP
    sharing a mixed lane with a canceled sibling therefore keeps its own
    legitimately-approved commits OUT of the excluded set, closing #5018's
    false-FAIL, while a commit NOT on any approved lane's first-parent spine — a
    canceled WP's own work, OR a removed WP's commit smuggled into the lane via a
    merge's SECOND parent (#4977's mechanism; ``_lane_tip_commits`` walks ALL
    ancestry, first- and second-parent alike, so a smuggled second-parent commit
    is present here but absent from the first-parent-only ``authored_*`` sets) —
    is never subtracted and stays excluded. A fully-canceled lane (no approved
    WP at all) never contributes to *authored_shas*/*authored_patch_ids*
    (:func:`_collect_authored` skips it), so the subtraction is a no-op and every
    one of its tip commits stays excluded, unchanged from the pre-#5018 behavior.

    **Correction (#5046 WP05):** "stays excluded" here is SHA/patch-id
    reachability only, NOT a guarantee that the canceled WP's CONTENT can
    never ship — the #5046 hole a prior revision of this docstring stated as
    if it were one. A squash mints new SHAs for every commit, so this axis
    contributes nothing under the default strategy at all; and even under
    merge/rebase, a LATER survivor commit on the SAME mixed lane can carry
    the canceled WP's exact bytes forward unchanged (or a surviving commit
    can simply never touch the canceled WP's paths), in which case those
    bytes are perfectly reachable via the survivor's own SHA and this axis
    never sees them. Whether that content is genuinely superseded, or is
    exactly the unsuperseded #5046 defect, is what
    :attr:`ApprovedWpCommitSet.canceled_content` /
    :meth:`MergeOutcomeVerifier._canceled_content_divergence` decide — the
    CONTENT-identity axis this SHA-level exclusion cannot substitute for.
    """
    shas: set[str] = set()
    patch_ids: set[str] = set()
    for lane in lanes_manifest.lanes:
        if not any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        lane_tip_shas = set(_lane_tip_commits(repo_root, coord_base_ref, branch))
        lane_patch_ids = {pid for sha in lane_tip_shas if (pid := patch_id_of(repo_root, sha))}
        shas |= lane_tip_shas - authored_shas
        patch_ids |= lane_patch_ids - authored_patch_ids
    return frozenset(shas), frozenset(patch_ids)


@dataclass(frozen=True)
class ExternalDependencyAttribution:
    """The verified result of the operator's ``--dependency-ref`` declarations (#6771).

    ``shas`` are the declared refs' commits inside the closed-world window
    (``window_base..ref``), ``blobs``/``deletions`` their final per-path state from the SAME
    :func:`_final_authored_walk` the lane authorship uses (C-002 — never a second walk).
    ``refusal`` is set when a declaration cannot be honoured fail-closed; the sets are then
    EMPTY, so a refused declaration exempts nothing.
    """

    refs: tuple[str, ...] = ()
    shas: frozenset[str] = frozenset()
    blobs: frozenset[tuple[str, str]] = frozenset()
    deletions: frozenset[str] = frozenset()
    refusal: str | None = None
    #: ``ref -> commit SHA`` each declared ref was verified against. The caller persists it
    #: (``ConsolidationState.dependency_ref_pins``) so the gate and a ``--resume`` verify
    #: the SAME commit, never whatever the name resolves to later.
    pins: Mapping[str, str] = field(default_factory=dict)


def _mission_spines(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    *,
    coord_base_ref: str,
    window_base: str,
    pre_mission: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Commit SHA -> the mission spine it sits on, for the #6771 declaration guard.

    Every commit a mission AUTHORED or CARRIED onto a first-parent spine is mission work: a
    lane's own spine (``coord_base_ref..lane-branch --first-parent``, tolerant of an
    unresolvable lane exactly as :func:`_lane_first_parent_spine` is) and the mission
    branch's own spine above the window base. A declaration that would exempt one of these
    is refused, which keeps the closed world from being widened into a bypass: a removed work
    package's commit is on its lane's spine, and a direct commit on the mission branch is on
    the mission branch's spine. An external dependency's commits are on neither (they arrived
    as a merge's second parent), which is exactly what makes them declarable.

    Mission work is what the Mission authored AFTER its base (#7560, ADR 2026-09-29-1
    Amendment): history the target lacks below the Mission base (*pre_mission*,
    ``window_base..mission_base``) is pre-Mission and sits on no Mission spine, so it is
    skipped on both walks. On a lane spine (bounded by *coord_base_ref*, above the base) the
    skip is defensive; on the Mission branch's spine it is what keeps a Mission branch cut from
    a fork of the target from reading the fork's own history as Mission work.
    """
    spines: dict[str, str] = {}
    for lane in lanes_manifest.lanes:
        label = f"lane {lane.lane_id}'s first-parent spine"
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        # An ABSENT branch (deleted, or never cut) guards nothing here; the namespace and
        # recorded-tip guards cover what it held. A branch that EXISTS but whose spine cannot
        # be read is a probe failure: it raises, and the caller REFUSEs (it must never shrink
        # the spine set the guard defends).
        if not branch_exists(repo_root, branch):
            continue
        for sha in first_parent_commits_in_range(repo_root, coord_base_ref, branch):
            if sha not in pre_mission:
                spines.setdefault(sha, label)
    mission_label = f"the mission branch {lanes_manifest.mission_branch}'s first-parent spine"
    # The mission branch is READ, not tolerated: a spine this guard cannot read is a spine it
    # cannot defend, and the caller turns the resulting GitProbeError into a REFUSE.
    for sha in first_parent_commits_in_range(repo_root, window_base, lanes_manifest.mission_branch):
        if sha not in pre_mission:
            spines.setdefault(sha, mission_label)
    return spines


def _mission_work_reaches(
    repo_root: Path,
    sha: str,
    mission_branch: str,
    lanes_manifest: LanesManifest,
) -> bool:
    """True when the mission branch OR any lane branch reaches *sha* (#6771).

    A work-package branch brings its dependency branch in during implementation, which is BEFORE the
    consolidation folds the lanes into the mission branch — so at claim time the merged head is
    reachable from the LANE, not yet from the mission branch. Both are the mission's own work
    reaching the ref, so both count. An unresolvable lane branch (a fully-canceled lane, a
    topology that cut it after this read) contributes nothing rather than failing the probe:
    the same tolerance :func:`_lane_first_parent_spine` documents for authorship.
    """
    if sha_reachable_from(repo_root, sha, mission_branch):
        return True
    for lane in lanes_manifest.lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        if branch_exists(repo_root, branch) and sha_reachable_from(repo_root, sha, branch):
            return True
    return False


def _recorded_lane_heads(feature_dir: Path) -> frozenset[str] | None:
    """Every ``lane_head`` stamp ANY work package of the Mission recorded (canceled and removed ones included), or ``None`` when the log is unreadable."""
    from specify_cli.consolidation.commit_to_target_stamps import consolidation_events
    from specify_cli.status import StoreError

    try:
        events = consolidation_events(feature_dir)
    except StoreError:
        return None
    return frozenset(stamp for event in events if (stamp := stamp_of(event)))


def _mission_namespaces(lanes_manifest: LanesManifest) -> tuple[str, ...]:
    """Branch-name stems that mark a branch as this Mission's own (the mission branch and every lane branch it names)."""
    stems: dict[str, None] = {lanes_manifest.mission_branch: None}
    for lane in lanes_manifest.lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        stems[branch] = None
        stems[branch.removesuffix(f"-{lane.lane_id}")] = None
    return tuple(stems)


def _mission_tip_shas(repo_root: Path, namespaces: Sequence[str]) -> dict[str, str]:
    """``sha -> branch`` for every recorded lane work tip (``refs/spec-kitty/lane-tip/*``) in this Mission's namespace.

    Raises :class:`GitProbeError` when the listing cannot be read: unknown is never "none".
    """
    try:
        branches = recorded_tip_branches(repo_root)
    except LaneTipListingError as exc:
        raise GitProbeError(str(exc)) from exc
    tips: dict[str, str] = {}
    for branch in sorted(branches):
        if any(branch.startswith(stem) for stem in namespaces):
            tip = read_tip(repo_root, branch)
            if tip:
                tips.setdefault(tip, branch)
    return tips


def _namespace_hit(ref: str, namespaces: Sequence[str]) -> str | None:
    """The Mission branch stem *ref* is named inside, or ``None`` (also catches ``refs/heads/`` and remote-qualified spellings)."""
    return next((stem for stem in namespaces if stem in ref), None)


def _recorded_work_hit(
    repo_root: Path,
    window_base: str,
    window: Sequence[str],
    lane_heads: frozenset[str],
    tip_shas: Mapping[str, str],
    pre_mission: frozenset[str] = frozenset(),
) -> tuple[str, str] | None:
    """The first window commit on the first-parent history of a recorded Mission work tip, with how it was recorded, or ``None``.

    A work package's stamps and a lane's recorded tip are where its work ENDED, not where a
    carrier lane's `git merge` took it in: a lane that a carrier pulled in at commit X and that
    kept going to a stamped Y holds X on Y's first-parent spine, while no stamp or tip sits in ``window_base..X``. So each
    recorded commit contributes its first-parent spine back to the window base. Commits an
    external dependency brought in sit on second-parent sides and are not on it. A recorded
    commit that no longer resolves covers nothing and is skipped; a probe failure raises.
    Pre-Mission commits (*pre_mission*, #7560) are not Mission work and never hit.
    """
    in_window = set(window) - pre_mission
    recorded = [(sha, "a work package of this Mission recorded as a lane head in the status log") for sha in sorted(lane_heads)]
    recorded += [(sha, f"is on the history of the recorded work tip of the Mission lane branch '{branch}'") for sha, branch in sorted(tip_shas.items())]
    for tip, how in recorded:
        try:
            resolve_commit(repo_root, tip)
        except GitProbeError:
            continue
        for sha in first_parent_commits_in_range(repo_root, window_base, tip):
            if sha in in_window:
                return sha, how
    return None


def _refused(refs: tuple[str, ...], message: str) -> ExternalDependencyAttribution:
    return ExternalDependencyAttribution(refs=refs, refusal=message)


def resolve_external_dependency_refs(
    repo_root: Path,
    *,
    refs: Sequence[str],
    window_base: str | None,
    mission_branch: str,
    lanes_manifest: LanesManifest,
    coord_base_ref: str,
    recorded_lane_heads: frozenset[str] = frozenset(),
    pins: Mapping[str, str] | None = None,
    pre_mission: frozenset[str] = frozenset(),
) -> ExternalDependencyAttribution:
    """Verify the declared dependency refs and return the sets that are outside the closed world.

    A declared ref is honoured only when it is an external branch the mission really merged
    in: it resolves, the mission branch reaches it, it is not Mission-authored (below), and
    NONE of its window commits sits on a mission spine (:func:`_mission_spines`). Those commits
    then join the content that predates the window — the standing commits already on the
    target have. Nothing else changes: an undeclared commit stays un-attributable.
    Attribution is never widened toward merge simulation (C-001: #4945 and #6771 are
    structurally identical, so only an explicit declaration separates them).

    The guard fails closed against ANY Mission authorship, not just the CURRENT manifest's
    live spines (a removed or canceled work package's lane branch is gone and absent from
    ``lanes.json``, which is the #4945 shape): a ref NAMED inside the Mission's branch
    namespace is refused, and so is a window commit that is a ``lane_head`` stamp any work
    package recorded (*recorded_lane_heads*, canceled and removed ones included) or the
    recorded work tip of a Mission lane branch (``refs/spec-kitty/lane-tip/*``).

    Mission work is what the Mission authored after its base (#7560, ADR 2026-09-29-1
    Amendment). *pre_mission* is the history the target lacks below the Mission base
    (:func:`_pre_mission_attribution`); both guard walks skip it, so a Mission branch cut from
    a fork of the target can declare the fork's pin. The declared ref's own window is
    unchanged (``window_base..ref``): it is not bounded at the base.

    *pins* (``ref -> SHA``) are the commits an earlier step of this consolidation verified.
    A pinned ref is verified against its PIN; if the name now resolves elsewhere the
    declaration REFUSEs naming both SHAs (``DEPENDENCY_REF_MOVED``). The SHAs verified now are
    returned in :attr:`ExternalDependencyAttribution.pins`.

    No declaration short-circuits before any git probe, so an undeclared run costs exactly
    what it costs today (NFR-001). Every failure is a REFUSE with the sets left EMPTY, and
    each carries a stable ``Error code:`` suffix: an unresolvable ref, a ref the mission never
    merged, a ref that would cover mission work, a moved ref, an unbounded window, or any
    :class:`GitProbeError` (NFR-002).
    """
    declared = tuple(dict.fromkeys(ref for ref in refs if ref.strip()))
    if not declared:
        return ExternalDependencyAttribution()
    if window_base is None:
        return _refused(declared, _REFUSE_DEPENDENCY_NO_WINDOW_BASE.format(refs=", ".join(declared)))
    namespaces = _mission_namespaces(lanes_manifest)
    try:
        spines = _mission_spines(repo_root, lanes_manifest, coord_base_ref=coord_base_ref, window_base=window_base, pre_mission=pre_mission)
        tip_shas = _mission_tip_shas(repo_root, namespaces)
    except GitProbeError as exc:
        return _refused(declared, _REFUSE_DEPENDENCY_PROBE.format(doing="reading the mission spines", exc=exc))
    known_pins = pins or {}
    verified_pins: dict[str, str] = {}
    shas: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for ref in declared:
        outcome = _verify_declared_ref(
            repo_root,
            ref,
            pinned=known_pins.get(ref),
            window_base=window_base,
            mission_branch=mission_branch,
            lanes_manifest=lanes_manifest,
            namespaces=namespaces,
            spines=spines,
            guards=(recorded_lane_heads, tip_shas, pre_mission),
        )
        if isinstance(outcome, str):
            return _refused(declared, outcome)
        tip, window, ref_blobs, ref_deletions = outcome
        verified_pins[ref] = tip
        shas.update(window)
        blobs |= ref_blobs
        deletions |= ref_deletions
    return ExternalDependencyAttribution(refs=declared, shas=frozenset(shas), blobs=frozenset(blobs), deletions=frozenset(deletions), pins=verified_pins)


def _verify_declared_ref(
    repo_root: Path,
    ref: str,
    *,
    pinned: str | None,
    window_base: str,
    mission_branch: str,
    lanes_manifest: LanesManifest,
    namespaces: Sequence[str],
    spines: Mapping[str, str],
    guards: tuple[frozenset[str], Mapping[str, str], frozenset[str]],
) -> str | tuple[str, list[str], set[tuple[str, str]], set[str]]:
    """Verify ONE declared ref: the refusal text, or ``(tip, window, blobs, deletions)``."""
    lane_heads, tip_shas, pre_mission = guards
    namespace = _namespace_hit(ref, namespaces)
    if namespace is not None:
        return _REFUSE_DEPENDENCY_MISSION_NAMESPACE.format(ref=ref, namespace=namespace)
    try:
        tip = resolve_commit(repo_root, ref)
    except GitProbeError:
        tip = ""
    if pinned is not None:
        if tip and tip != pinned:
            return _REFUSE_DEPENDENCY_MOVED.format(ref=ref, pinned=pinned, now=tip)
        tip = pinned  # SHA authority: a deleted name does not unpin a commit that still exists
    if not tip:
        return _REFUSE_DEPENDENCY_UNRESOLVED.format(ref=ref)
    try:
        if pinned is not None:
            tip = resolve_commit(repo_root, pinned)
        if not _mission_work_reaches(repo_root, tip, mission_branch, lanes_manifest):
            return _REFUSE_DEPENDENCY_NOT_MERGED.format(ref=ref, mission_branch=mission_branch)
        window = commits_in_range(repo_root, window_base, tip)
        covered = [sha for sha in window if sha in spines]
        if covered:
            return _REFUSE_DEPENDENCY_COVERS_MISSION_WORK.format(ref=ref, sha=covered[0][:10], spine=spines[covered[0]])
        recorded = _recorded_work_hit(repo_root, window_base, window, lane_heads, tip_shas, pre_mission)
        if recorded is not None:
            return _REFUSE_DEPENDENCY_RECORDED_TIP.format(ref=ref, sha=recorded[0][:10], recorded=recorded[1])
        ref_blobs, ref_deletions = _final_authored_walk(repo_root, window)
    except GitProbeError as exc:
        return _REFUSE_DEPENDENCY_PROBE.format(doing=f"verifying external dependency ref '{ref}'", exc=exc)
    return tip, window, ref_blobs, ref_deletions


@dataclass(frozen=True)
class PreMissionHistory:
    """History the target lacks that predates the Mission (#7560): ``window_base..mission_base``.

    ``shas`` are those commits, ``blobs``/``deletions`` their final per-path state from the SAME
    :func:`_final_authored_walk` the declared refs use. No patch-ids: the exemption is by exact
    SHA, so a re-lettered copy of a pre-Mission commit is still judged (fail-closed). All empty when the
    window base already reaches the base, when the base is unavailable, when the range holds
    recorded Mission work, and when a probe failed (``base`` is then unavailable, its ``kind``
    naming why): that is today's bound, which exempts nothing.
    """

    base: MissionBase
    shas: frozenset[str] = frozenset()
    blobs: frozenset[tuple[str, str]] = frozenset()
    deletions: frozenset[str] = frozenset()


# The short clause the note line prints for a failed probe: never raw git stderr.
_PROBE_FAILED_REASON = "a git probe failed"
_RANGE_HOLDS_MISSION_WORK_REASON = "pre-Mission range holds Mission work"


def _pre_mission_attribution(
    repo_root: Path,
    window_base: str | None,
    base: MissionBase,
    *,
    feature_dir: Path | None,
    lanes_manifest: LanesManifest | None,
) -> PreMissionHistory:
    """The pre-Mission history below *base* that *window_base* lacks; any doubt degrades to today's bound.

    Only a **recorded** base exempts (see the comment below); a derived or unavailable base
    returns the empty history. An empty range costs no further probe (no walk). A non-empty range must hold no recorded
    Mission work: a ``lane_head`` stamp any work package of the Mission recorded (read from
    *feature_dir*'s status log) or a recorded lane work tip in the Mission's branch namespace
    (from *lanes_manifest*). Such a commit means the base sits above the Mission's start, so the
    whole set is dropped (``RANGE_HOLDS_MISSION_WORK``). ``None`` for either skips that guard
    (a hand-built claim with no Mission on disk). A :class:`GitProbeError`, or an unreadable
    status log, returns empty sets with the base marked unavailable (``PROBE_FAILED``):
    fail-closed, because it exempts nothing.
    """
    if base.provenance is not MissionBaseProvenance.RECORDED:
        # A derived base is the first parent of the first scaffold commit, not the commit the
        # branch was cut from: a non-Mission-path commit made on the Mission branch before the
        # scaffold sits in ``window_base..base`` and topology cannot tell it from fork history,
        # so exempting it would pass Mission-authored content as pre-Mission (fail-open). Only a
        # recorded base (write-once at the cut) exempts; a legacy Mission opts in by recording
        # ``mission_base_sha`` in its meta.json (validated like any recorded base).
        return PreMissionHistory(base)
    try:
        shas = pre_mission_history(repo_root, window_base, base)
        if not shas:
            return PreMissionHistory(base)
        if _range_holds_mission_work(repo_root, frozenset(shas), feature_dir, lanes_manifest):
            return PreMissionHistory(_unavailable(_RANGE_HOLDS_MISSION_WORK_REASON, MissionBaseReason.RANGE_HOLDS_MISSION_WORK))
        blobs, deletions = _final_authored_walk(repo_root, list(shas))
    except GitProbeError:
        logger.debug("pre-Mission attribution below %s degraded to the target's pre-run bound", base.sha, exc_info=True)
        return PreMissionHistory(_unavailable(_PROBE_FAILED_REASON, MissionBaseReason.PROBE_FAILED))
    return PreMissionHistory(base, frozenset(shas), frozenset(blobs), frozenset(deletions))


def _unavailable(reason: str, kind: MissionBaseReason) -> MissionBase:
    return MissionBase(None, MissionBaseProvenance.UNAVAILABLE, reason, kind)


def _range_holds_mission_work(
    repo_root: Path,
    shas: frozenset[str],
    feature_dir: Path | None,
    lanes_manifest: LanesManifest | None,
) -> bool:
    """True when *shas* holds a recorded ``lane_head`` stamp or a recorded lane work tip of this Mission.

    Raises :class:`GitProbeError` when the status log or the lane-tip listing cannot be read.
    """
    if feature_dir is not None:
        lane_heads = _recorded_lane_heads(feature_dir)
        if lane_heads is None:
            raise GitProbeError("the status log is unreadable, so its recorded lane heads are unknown")
        if lane_heads & shas:
            return True
    if lanes_manifest is not None:
        return not shas.isdisjoint(_mission_tip_shas(repo_root, _mission_namespaces(lanes_manifest)))
    return False


def _note_detail(base: MissionBase) -> str | None:
    """*base*'s reason as one short clause, chosen by its kind: a probe failure is the fixed clause, whole.

    A probe failure's reason carries git stderr, so it is replaced, never split or trimmed.
    """
    return _PROBE_FAILED_REASON if base.kind is MissionBaseReason.PROBE_FAILED else base.reason


def mission_base_note(claim: ApprovedWpCommitSet) -> str | None:
    """The one provenance note line for *claim*'s Mission base (FR-007), or ``None`` when there is nothing to say.

    Nothing is said when the Mission branch itself does not resolve: no pre-Mission history can exist then.
    """
    base = claim.mission_base
    if base is None:
        return None
    detail = _note_detail(base)
    if claim.pre_mission_shas and base.sha is not None:
        detail = f": {detail}" if detail else ""
        return (
            f"Mission base {base.sha[:10]} ({base.provenance}{detail}): {len(claim.pre_mission_shas)} commit(s) of history "
            "the target lacks predate this Mission and are not judged as Mission work (#7560)."
        )
    if base.provenance is MissionBaseProvenance.UNAVAILABLE and base.kind is not MissionBaseReason.MISSION_BRANCH_UNRESOLVED:
        return f"Mission base unavailable ({detail}); reconciliation windows are bounded by the target's pre-run tip only."
    return None


def dependency_refs_moved_refusal(repo_root: Path, pins: Mapping[str, str]) -> str | None:
    """Refusal text when a pinned declared ref now resolves to a different commit (``DEPENDENCY_REF_MOVED``), else ``None``.

    The reconciliation gate runs this against the pins the claim recorded, so a ref moved
    between claim and gate (or between an interrupted run and its ``--resume``) cannot widen
    the exemption. A ref that no longer resolves is not "moved": the pinned commit still stands.
    """
    for ref, pinned in pins.items():
        try:
            now = resolve_commit(repo_root, ref)
        except GitProbeError:
            continue
        if now != pinned:
            return _REFUSE_DEPENDENCY_MOVED.format(ref=ref, pinned=pinned, now=now)
    return None


__all__ = [
    "ExternalDependencyAttribution",
    "PreMissionHistory",
    "_REFUSE_DEPENDENCY_COVERS_MISSION_WORK",
    "_REFUSE_DEPENDENCY_MISSION_NAMESPACE",
    "_REFUSE_DEPENDENCY_MOVED",
    "_REFUSE_DEPENDENCY_NOT_MERGED",
    "_REFUSE_DEPENDENCY_NO_WINDOW_BASE",
    "_REFUSE_DEPENDENCY_PROBE",
    "_REFUSE_DEPENDENCY_RECORDED_TIP",
    "_REFUSE_DEPENDENCY_UNRESOLVED",
    "_collect_excluded",
    "_mission_namespaces",
    "_mission_spines",
    "_mission_tip_shas",
    "_mission_work_reaches",
    "_pre_mission_attribution",
    "_namespace_hit",
    "_recorded_lane_heads",
    "_recorded_work_hit",
    "_refused",
    "_verify_declared_ref",
    "dependency_refs_moved_refusal",
    "mission_base_note",
    "resolve_external_dependency_refs",
]
