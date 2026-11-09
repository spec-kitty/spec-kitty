"""The claim orchestration of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP14).

:func:`build_approved_wp_set` is the one function that decides which refusal a claim gets first, so the
whole refusal order lives here, in one place: external dependency refs, unreadable recorded lane heads,
unmaterializable status surface, unresolvable approved lane branches, unreadable canceled dependency
lanes, canceled dependency refusal, mixed-lane refusal, approved-bound refusal, evidence refusal,
unreadable presence range, then the collectors. With it live its compound-refusal helper, the claim-side
refusal builders and collectors only it calls, and the terminus vocabulary (the NFR-005 entry-point
allowlist and the FR-012 post-fix marker). Moved verbatim out of ``reconciliation.py``; no verdict changed.
That module re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation_authorship import (
    _collect_authored,
    _presence_range_unreadable_refusal,
    _presence_scope,
)
from specify_cli.consolidation.reconciliation_bound import (
    _approved_bound_verdict,
    _BoundVerdict,
    _bound_claim_base,
)
from specify_cli.consolidation.reconciliation_canceled import (
    _CanceledLaneQuery,
    _resolve_canceled_dependency_lanes,
    _resolve_mixed_lane_canceled_content,
    _unreadable_canceled_dependency_lanes,
    _unreadable_canceled_dependency_refusal_text,
)
from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet
from specify_cli.consolidation.reconciliation_closed_world import (
    _REFUSE_DEPENDENCY_PROBE,
    _collect_excluded,
    _recorded_lane_heads,
    resolve_external_dependency_refs,
)
from specify_cli.consolidation.reconciliation_kernel import (
    _APPROVED_MEMBERSHIP_LANES,
    _ClaimEventLog,
    _lane_branch_for,
    _lane_is_approved,
    _lane_tip_commits,
    _planning_prefix,
)
from specify_cli.consolidation.reconciliation_rendering import _ALSO_HAS, _BOTH_NEEDED
from specify_cli.consolidation.workspace import post_fix_marker_path
from specify_cli.consolidation.wp_evidence import evaluate_evidence
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_fully_canceled
from specify_cli.lanes.models import LanesManifest

logger = logging.getLogger(__name__)


# NFR-005 concrete floor: the six terminus entry points that MUST route through
# the reconciliation gate. Shrink-only — adding a terminus path that mutates
# refs/worktrees without adding it here means :func:`route_terminus` refuses it,
# and the self-mutation test proves a seventh, unrouted path fails the gate.
TERMINUS_ENTRY_POINTS: frozenset[str] = frozenset(
    {
        "consolidate",
        "consolidate --resume",
        "consolidate --abort",
        "upgrade",
        "agent issue-verdict",
        "doctor coordination --fix",
    }
)


class UnroutedTerminusPathError(RuntimeError):
    """Raised when a terminus path not on the NFR-005 allowlist tries to route."""


def route_terminus(entry_point: str) -> None:
    """Assert *entry_point* is on the NFR-005 allowlist before it runs the gate.

    Raises :class:`UnroutedTerminusPathError` for any terminus path not in
    :data:`TERMINUS_ENTRY_POINTS`. The self-mutation test drives a synthetic
    seventh path through here to prove an unrouted terminus command fails the
    gate rather than silently bypassing it (DIRECTIVE_043).
    """
    if entry_point not in TERMINUS_ENTRY_POINTS:
        raise UnroutedTerminusPathError(
            f"terminus entry point {entry_point!r} is not routed through the "
            "reconciliation gate; add it to TERMINUS_ENTRY_POINTS and wire the "
            "gate before it tears down any ref/worktree (NFR-005)"
        )


def write_post_fix_marker(repo_root: Path, mission_id: str) -> None:
    """Stamp the FR-012 post-fix marker for this in-flight merge transaction.

    FR-012: the marker a post-fix merge writes at transaction start (#5111: with
    its fresh ``state.json``). Its ABSENCE on an in-flight (resumed) merge means
    the state was created by pre-fix code, whose shape the new guarantees cannot
    be retro-applied to (D6) -- refuse. It is cleared only by
    :func:`~specify_cli.consolidation.state.clear_state`, together with the state.
    """
    path = post_fix_marker_path(mission_id, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("terminus-reconciliation-gate\n", encoding="utf-8")


def detect_legacy_in_flight_state(repo_root: Path, mission_id: str, *, is_resume: bool) -> str | None:
    """FR-012: return a recovery message when a pre-fix in-flight state is found.

    A resumed merge whose transaction was started by pre-fix code carries no
    post-fix marker. The new tree-authoritative guarantees cannot be
    retro-applied to that unknown-shape state (D6, operator-confirmed), so the
    command must REFUSE with a recovery instruction rather than auto-heal.
    A fresh (non-resume) merge is never legacy — it writes the marker together
    with its ``state.json`` at transaction start (#5111). Returns ``None`` when the state is post-fix (safe to
    proceed).
    """
    if not is_resume:
        return None
    if post_fix_marker_path(mission_id, repo_root).exists():
        return None
    return (
        "a pre-fix in-flight merge state was detected (no reconciliation marker). "
        "The terminus reconciliation guarantees cannot be retro-applied to it. "
        "Run `spec-kitty consolidate --abort` to clear the stale state, verify the target "
        "branch and lane tips by hand, then start a fresh `spec-kitty consolidate`."
    )


def build_approved_wp_set(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    coord_base_ref: str,
    excluded_canceled_wp_ids: Iterable[str] = (),
    excluded_window_base: str | None = None,
    external_dependency_refs: Sequence[str] = (),
    external_dependency_pins: Mapping[str, str] | None = None,
) -> ApprovedWpCommitSet:
    """Derive the fail-closed, reduced-snapshot claim once per transaction (T027).

    * WP membership is read through
      :func:`specify_cli.status.reducer.materialize_snapshot`, which reduces via
      the **wall-clock** diary reducer ``spec_kitty_events.status.reduce`` (not
      the Lamport ``reduce_status_events`` — CLI lane rows carry no Lamport
      clock). A wall-clock-later approval cannot override a committed rejection in
      the claim because that reducer (spec-kitty-events PR #102, fixing issue
      #101; ``spec-kitty-events>=10.5.1``) sorts a non-seed departure from
      ``approved`` after the approval it followed (spec-kitty#4941 / #6213 corrected the
      earlier "Lamport wrapper" wording); the consolidation module reaches it
      through the ``specify_cli.status`` facade (C-002);
    * approved commit SHAs still come from **lane-branch git tips** relative to
      *coord_base_ref* (never status rows), but the approved-bound check in front of the
      collectors (:func:`_approved_bound_verdict`, #5668) refuses a lane whose tip holds
      content beyond what the approval stamps name, so the live tip equals the approved
      content up to tool-made merges and bookkeeping commits;
    * fail-closed: an unmaterializable coord surface, or a claim that is empty
      while the manifest lists WPs, yields a REFUSE-shaped claim;
    * *external_dependency_refs* (#6771) are the operator's declared external dependency
      refs (``specify_cli consolidate --dependency-ref``). They are verified once, HERE,
      before any collector reads a lane tip, and the resulting exempt sets ride on the
      claim so the verifier and the ``--dry-run`` forecast attribute the same content. A
      declaration that cannot be honoured yields a REFUSE-shaped claim, so it refuses at
      claim time (before the first mutating phase) instead of at the gate.
    """
    # Imported lazily so this module stays import-light and the status facade is
    # resolved through ``specify_cli.status`` (C-002: the status facade, not a
    # direct ``spec_kitty_events`` import).
    from specify_cli.status import materialize_snapshot

    lane_heads = _recorded_lane_heads(feature_dir) if external_dependency_refs else frozenset()
    external_dependency = resolve_external_dependency_refs(
        repo_root,
        refs=external_dependency_refs if lane_heads is not None else (),
        window_base=excluded_window_base,
        mission_branch=lanes_manifest.mission_branch,
        lanes_manifest=lanes_manifest,
        coord_base_ref=coord_base_ref,
        recorded_lane_heads=lane_heads or frozenset(),
        pins=external_dependency_pins,
    )

    manifest_wp_ids = frozenset(wp for lane in lanes_manifest.lanes for wp in lane.wp_ids)
    planning_prefix = _planning_prefix(repo_root, feature_dir)
    if lane_heads is None:
        unreadable = _REFUSE_DEPENDENCY_PROBE.format(doing="reading the status log for the Mission's recorded lane heads", exc="status log unreadable")
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, unreadable)
    if external_dependency.refusal is not None:
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, external_dependency.refusal)
    try:
        snapshot = materialize_snapshot(feature_dir)
    except Exception as exc:  # noqa: BLE001 — any unmaterializable surface fails closed
        return ApprovedWpCommitSet(
            manifest_wp_ids=manifest_wp_ids,
            excluded_window_base=excluded_window_base,
            surface_resolved=False,
            refusal=f"coordination surface could not be materialized: {exc}",
            mission_slug=lanes_manifest.mission_slug,
            planning_prefix=planning_prefix,
        )

    work_packages = snapshot.work_packages or {}
    excluded_ids = frozenset(excluded_canceled_wp_ids)
    unresolvable = _unresolvable_approved_lane_branches(repo_root, lanes_manifest, work_packages, excluded_ids)
    if unresolvable:
        return _refusal_claim(
            lanes_manifest,
            manifest_wp_ids,
            planning_prefix,
            excluded_window_base,
            _missing_branch_refusal_text(unresolvable),
        )
    # One event-log reader for the whole claim (NFR-001): the canceled-dependency
    # branch check below, the canceled-dependency resolution, the mixed-lane
    # resolution and the bound verdict all share it, so the log is read at most once.
    event_log = _ClaimEventLog(feature_dir)
    unreadable_canceled = _unreadable_canceled_dependency_lanes(repo_root, lanes_manifest, excluded_ids, coord_base_ref, event_log)
    if unreadable_canceled:
        return _refusal_claim(
            lanes_manifest,
            manifest_wp_ids,
            planning_prefix,
            excluded_window_base,
            _unreadable_canceled_dependency_refusal_text(unreadable_canceled),
        )
    from specify_cli.lanes.single_branch_landing import authorship_window

    sb_window = authorship_window(repo_root, lanes_manifest.mission_slug, lanes_manifest.mission_branch, lanes_manifest.target_branch)
    # Mixed-lane canceled-content resolution (T022/T023, #5046 WP05) — after the
    # snapshot and the branch-resolvability check, before any of the existing
    # collectors, per plan.md D-3. Any Unattributable outcome refuses the WHOLE
    # claim immediately (refusals take precedence over FAIL by construction).
    dependency = _resolve_canceled_dependency_lanes(
        _CanceledLaneQuery(repo_root, feature_dir, lanes_manifest, work_packages, excluded_ids, coord_base_ref, planning_prefix, excluded_window_base, sb_window),
        event_log,
    )
    bound_verdict = functools.partial(
        _approved_bound_verdict,
        repo_root,
        lanes_manifest,
        work_packages,
        excluded_ids,
        coord_base_ref=coord_base_ref,
        window_base=excluded_window_base,
        planning_prefix=planning_prefix,
        event_log=event_log,
    )
    if dependency.refusal is not None:
        compound = _compound_refusal(dependency.refusal, bound_verdict, event_log)
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, compound)
    canceled_lane_commits = dependency.unapproved_commits
    canceled_content, attested_wp_ids, mixed_lane_refusal = _resolve_mixed_lane_canceled_content(
        repo_root,
        feature_dir,
        lanes_manifest,
        work_packages,
        excluded_ids,
        coord_base_ref,
        planning_prefix,
        excluded_window_base,
        sb_window,
        canceled_lane_commits=canceled_lane_commits,
        event_log=event_log,
    )
    if mixed_lane_refusal is not None:
        compound = _compound_refusal(mixed_lane_refusal, bound_verdict, event_log)
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, compound)

    # Approved-bound check (#5668): after the mixed-lane resolution (its refusals keep
    # precedence, and name this check's refusals too, #5720), before the collectors read the live lane tips.
    bound = bound_verdict()
    if bound.refusal is not None:
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, bound.refusal)

    # Implementation-evidence + independent-review axis (#5939 single_branch, #6715 every
    # topology): the stamp bound above refuses content a lane gained AFTER its approval; it has
    # nothing to bound on a lane that holds no content at all (a single_branch Mission's one lane is
    # bounded through its Mission branch since S8, #7283, but only when it lands one). REFUSE (before the collectors read tips, so nothing is
    # rolled back) when an approved WP has no change to its owned_files in its evidence window,
    # no confirmable independent review, or an uncomputable / unreadable window. The single
    # authority is ``consolidation.wp_evidence``; the event log is read lazily through the one
    # claim reader, only when an attestation could lift a refusal.
    evidence = evaluate_evidence(repo_root, feature_dir, lanes_manifest, work_packages, excluded_ids, events=event_log.read)
    if evidence.refusal is not None:
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, evidence.refusal)

    approved = _collect_approved_shas(repo_root, lanes_manifest, work_packages, coord_base_ref, sb_window)
    presence = _presence_scope(
        repo_root,
        lanes_manifest,
        excluded_ids,
        base=_bound_claim_base(repo_root, excluded_window_base, coord_base_ref),
        coord_base_ref=coord_base_ref,
        events=event_log.read(),
    )
    presence_refusal = _presence_range_unreadable_refusal(lanes_manifest, work_packages, presence, coord_base_ref)
    if presence_refusal is not None:
        return _refusal_claim(lanes_manifest, manifest_wp_ids, planning_prefix, excluded_window_base, presence_refusal)
    # Authored (WP1/WP2 shared prerequisite): computed BEFORE the excluded axis so
    # #5018's commit-level narrowing (below) can subtract it. Collectors stay pure
    # (WP2 note) — no shared mutable state, just a value threaded as a parameter.
    authored_shas, authored_patch_ids, authored_blobs, authored_deletions, multi_lane_paths, approved_lane_content = _collect_authored(
        repo_root,
        lanes_manifest,
        work_packages,
        coord_base_ref,
        sb_window,
        canceled_lane_commits=canceled_lane_commits,
        presence=presence,
    )
    excluded_shas, excluded_patch_ids = _collect_excluded(
        repo_root,
        lanes_manifest,
        coord_base_ref,
        excluded_ids,
        authored_shas=authored_shas,
        authored_patch_ids=authored_patch_ids,
    )
    return ApprovedWpCommitSet(
        approved=approved,
        excluded_shas=excluded_shas,
        excluded_patch_ids=excluded_patch_ids,
        manifest_wp_ids=manifest_wp_ids,
        excluded_window_base=excluded_window_base,
        surface_resolved=True,
        enforce_closed_world=True,
        authored_shas=authored_shas,
        authored_patch_ids=authored_patch_ids,
        authored_blobs=authored_blobs,
        authored_deletions=authored_deletions,
        multi_lane_paths=multi_lane_paths,
        mission_slug=lanes_manifest.mission_slug,
        planning_prefix=planning_prefix,
        canceled_content=canceled_content,
        attested_canceled_wp_ids=attested_wp_ids,
        approved_lane_content=approved_lane_content,
        canceled_dependency_content=dependency.content,
        bound_lane_tips=bound.lane_tips,
        bound_lane_branches=bound.lane_branches,
        no_implementation_attested_wp_ids=evidence.lifted_wp_ids,
        external_dependency_refs=external_dependency.refs,
        external_dependency_pins=dict(external_dependency.pins),
        external_dependency_shas=external_dependency.shas,
        external_dependency_blobs=external_dependency.blobs,
        external_dependency_deletions=external_dependency.deletions,
    )


def _compound_refusal(first: str, bound_verdict: Callable[[], _BoundVerdict], event_log: _ClaimEventLog) -> str:
    """*first* followed by the approved-bound refusals the operator would otherwise meet one run later (#5720).

    *first* is a mixed-lane or canceled-dependency refusal. The approved bound is evaluated
    as it stands once the operator follows that recovery: a canceled-superseded attestation
    covers no commit of it. *first* stays alone when the event log cannot be read
    (the bound cannot be computed, and *first* or the bound's own refusal says so) and when
    a git probe fails (the bound is reported by the next run, which refuses before any
    change either way). The log is read at most once per claim, through *event_log*.
    """
    if event_log.read() is None:
        return first
    try:
        verdict = bound_verdict()
    except GitProbeError:
        logger.debug("the approved bound could not be evaluated for the compound refusal", exc_info=True)
        return first
    if verdict.refusal is None:
        return first
    return f"{first}\n\n{_ALSO_HAS}\n{verdict.refusal}\n\n{_BOTH_NEEDED}"


def _missing_branch_refusal_text(unresolvable: list[tuple[str, str]]) -> str:
    """Compose the PD-5 refusal text, joining multiple lanes deterministically."""
    return "; ".join(
        f"approved lane {lane_id}: created branch '{branch}' does not exist in git; "
        "the lane's work cannot be attributed. Verify the lane worktree was allocated and "
        "its branch was not deleted before the merge could attribute its commits."
        for lane_id, branch in unresolvable
    )


def _refusal_claim(
    lanes_manifest: LanesManifest,
    manifest_wp_ids: frozenset[str],
    planning_prefix: str | None,
    excluded_window_base: str | None,
    message: str,
) -> ApprovedWpCommitSet:
    """Build a REFUSE-shaped claim, mirroring the unmaterializable-surface refusal."""
    return ApprovedWpCommitSet(
        manifest_wp_ids=manifest_wp_ids,
        excluded_window_base=excluded_window_base,
        surface_resolved=True,
        refusal=message,
        mission_slug=lanes_manifest.mission_slug,
        planning_prefix=planning_prefix,
    )


def _unresolvable_approved_lane_branches(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[tuple[str, str]]:
    """PD-5: name every approved, non-planning, non-canceled lane whose created
    branch does not exist in git.

    This is the ONLY new strict arm (probe-error tolerance on
    :func:`_lane_tip_commits` / :func:`_lane_first_parent_spine` is unchanged,
    on every axis — #5001 FOLD-3 scoping). A lane qualifies when it is not
    ``lane-planning``, at least one of its WPs is approved, and it is not
    fully canceled; such a lane's created branch not resolving means its
    approved work can never be attributed, so the claim must refuse BY NAME
    rather than silently returning an empty commit set for it (US1 AS3).
    """
    unresolvable: list[tuple[str, str]] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda lane: lane.lane_id):
        if is_planning_lane(lane):
            continue
        if not _lane_is_approved(lane, work_packages):
            continue
        if lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        if not branch_exists(repo_root, branch):
            unresolvable.append((lane.lane_id, branch))
    return unresolvable


def _collect_approved_shas(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Approved WPs → their lane-tip commit SHAs (reduced-snapshot membership + git tips)."""
    approved: dict[str, tuple[str, ...]] = {}
    for lane in lanes_manifest.lanes:
        base, branch = sb_window if sb_window and is_planning_lane(lane) else (coord_base_ref, _lane_branch_for(lanes_manifest, lane.lane_id))
        for wp_id in lane.wp_ids:
            state = work_packages.get(wp_id)
            if state is None:
                continue
            lane_value = str(state.get("lane", ""))
            if lane_value in _APPROVED_MEMBERSHIP_LANES:
                approved[wp_id] = tuple(_lane_tip_commits(repo_root, base, branch))
    return approved


__all__ = [
    "TERMINUS_ENTRY_POINTS",
    "UnroutedTerminusPathError",
    "_collect_approved_shas",
    "_compound_refusal",
    "_missing_branch_refusal_text",
    "_refusal_claim",
    "_unresolvable_approved_lane_branches",
    "build_approved_wp_set",
    "detect_legacy_in_flight_state",
    "route_terminus",
    "write_post_fix_marker",
]
