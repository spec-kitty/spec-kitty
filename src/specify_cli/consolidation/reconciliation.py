"""Terminus Reconciliation Gate — the tree-authoritative merge-outcome verifier.

Mission ``terminus-merge-integrity-01M380R6`` WP06 (S-D / FR-001, FR-002,
FR-012; NFR-005). This module is the executable form of the epic invariant
(:doc:`contracts/terminus-reconciliation`):

    After a terminus command returns, *if* its exit code is 0 *then*
    ``MergeOutcomeVerifier.verify(target, approved_wp_set) == PASS`` held
    **before any teardown ran** — every approved WP's approved commits are
    reachable from the target tree, and no excluded (canceled/removed) commit
    is, matched by **patch-id equivalence** so cherry-picked/re-lettered copies
    of canceled code are caught too.

Why a tree-authoritative gate (D3): the pre-fix asserts
(``_assert_merged_wps_done_on_target``, ``_phase_porcelain_invariant``) check
derived rows/meta the *same run* wrote — circular. Git reachability is the only
authority the wrong bookkeeping cannot fake.

Claim integrity (D3+, non-negotiable):

* approved commit SHAs come from **lane-branch git tips**, never status rows —
  forbids the vacuous ``_assert_merged_wps_done_on_target`` pattern — bounded by the
  approval stamps (#5668): a lane tip holding content beyond what review approved
  refuses before any collector reads it (:func:`_approved_bound_verdict`);
* WP membership (approved vs canceled) is read through
  :func:`specify_cli.status.reducer.materialize_snapshot`, which reduces via
  ``spec_kitty_events.status.reduce`` — the **wall-clock** diary reducer (it is
  NOT the Lamport ``reduce_status_events``; CLI lane rows carry no Lamport
  clock). A wall-clock-later approval cannot green-wash a committed rejection
  *in the gate's own claim* because that reducer (spec-kitty-events PR #102,
  fixing issue #101; ``spec-kitty-events>=10.5.1``) sorts a non-seed departure
  from ``approved`` after the approval it followed, so a real-time ``approved -> in_progress``
  rejection applies even when a clock-ahead approval carried a later ``at``
  (spec-kitty#4941 / #6213 corrected the earlier "Lamport wrapper" claim). The
  consolidation module reaches the reducer through the ``specify_cli.status``
  facade, not a direct ``spec_kitty_events`` import (C-002);
* the claim is **fail-closed**: an unresolved/unmaterialized coord surface, or a
  claim that is empty while the manifest lists WPs, refuses rather than passing
  vacuously (closes PP-F3). This claim-integrity refusal is **strategy-
  independent** — it fires for squash too, ABOVE the squash content-deferral
  early-return, so an empty-claim squash can never pass vacuously (#5001
  FOLD-1). A production claim whose excluded window base cannot be resolved, and
  a git probe that errors mid-window, also refuse rather than skipping to PASS
  (fail-closed, #5001 FOLD-3).

Scope note (FR-013): the PASS result is scoped to **approved-WP commit
reachability** only, NOT verdict integrity — the residual LWW-reducer
wall-clock ordering bug (#4941; #4990 closed the rejection-after-approval
case) is out of scope for this mission and stays named-open in the docs.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.lane_tip import read_tip
from specify_cli.lanes.compute import is_planning_lane, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.consolidation.approved_bound import (
    approval_stamp,
)
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    blob_id_at,
    changed_paths_of,
    commits_in_range,
    is_merge_commit,
    merge_tree_write_tree_available as merge_tree_write_tree_available,
    patch_id_of,
    path_state_at as path_state_at,
    sha_reachable_from,
)
from specify_cli.consolidation.canceled_attestation import (
    OVERRIDABLE_REASONS,
    attestation_stamps,
)
from specify_cli.consolidation.workspace import post_fix_marker_path
from specify_cli.consolidation.wp_evidence import evaluate_evidence
from specify_cli.consolidation.wp_attribution import (
    Attributed,
    AttributionOutcome,
    CanceledPathState,
    Unattributable,
    UnattributableReason,
    canceled_spine_content,
    first_governed_open_stamp,
    lacks_lane_head_stamps,
    lane_never_started,
    lane_dependency_merges,
    lane_own_commits,
    resolve_canceled_wp,
)

# Re-exports (C-005): every name moved out of this module stays importable from it.
from specify_cli.consolidation.reconciliation_claim_types import (
    ApprovedLaneContent as ApprovedLaneContent,
    ApprovedWpCommitSet as ApprovedWpCommitSet,
    CanceledDependencyContent as CanceledDependencyContent,
    LaneContribution as LaneContribution,
    MissingApprovedContent as MissingApprovedContent,
    PresenceGap as PresenceGap,
    _GAP_ABSENT as _GAP_ABSENT,
    _GAP_UNCHANGED as _GAP_UNCHANGED,
)
from specify_cli.consolidation.reconciliation_kernel import (
    _APPROVED_MEMBERSHIP_LANES as _APPROVED_MEMBERSHIP_LANES,
    _ClaimEventLog as _ClaimEventLog,
    _KITTY_OPS_ROOT_RECORD as _KITTY_OPS_ROOT_RECORD,
    _LaneWalk as _LaneWalk,
    _closed_world_anchors as _closed_world_anchors,
    _dependency_lane_ids as _dependency_lane_ids,
    _is_bookkeeping as _is_bookkeeping,
    _is_nested_alias_coordination_file as _is_nested_alias_coordination_file,
    _lane_branch_for as _lane_branch_for,
    _lane_first_parent_spine as _lane_first_parent_spine,
    _lane_is_approved as _lane_is_approved,
    _lane_tip_commits as _lane_tip_commits,
    _planning_prefix as _planning_prefix,
)
from specify_cli.consolidation.reconciliation_rendering import (
    APPROVED_CONTENT_MISSING as APPROVED_CONTENT_MISSING,
    CANCELED_REACHABLE_VIA_DEPENDENCY as CANCELED_REACHABLE_VIA_DEPENDENCY,
    _ALSO_HAS as _ALSO_HAS,
    _BOTH_NEEDED as _BOTH_NEEDED,
    _RECOVERY_TAIL as _RECOVERY_TAIL,
    _attest_tail as _attest_tail,
    _describe_approved_content_missing as _describe_approved_content_missing,
    _describe_canceled_content as _describe_canceled_content,
    _describe_canceled_reachable as _describe_canceled_reachable,
    _join_refusals as _join_refusals,
    _renamed_note as _renamed_note,
)
from specify_cli.consolidation.reconciliation_closed_world import (
    ExternalDependencyAttribution as ExternalDependencyAttribution,
    _REFUSE_DEPENDENCY_COVERS_MISSION_WORK as _REFUSE_DEPENDENCY_COVERS_MISSION_WORK,
    _REFUSE_DEPENDENCY_MISSION_NAMESPACE as _REFUSE_DEPENDENCY_MISSION_NAMESPACE,
    _REFUSE_DEPENDENCY_MOVED as _REFUSE_DEPENDENCY_MOVED,
    _REFUSE_DEPENDENCY_NOT_MERGED as _REFUSE_DEPENDENCY_NOT_MERGED,
    _REFUSE_DEPENDENCY_NO_WINDOW_BASE as _REFUSE_DEPENDENCY_NO_WINDOW_BASE,
    _REFUSE_DEPENDENCY_PROBE as _REFUSE_DEPENDENCY_PROBE,
    _REFUSE_DEPENDENCY_RECORDED_TIP as _REFUSE_DEPENDENCY_RECORDED_TIP,
    _REFUSE_DEPENDENCY_UNRESOLVED as _REFUSE_DEPENDENCY_UNRESOLVED,
    _collect_excluded as _collect_excluded,
    _mission_namespaces as _mission_namespaces,
    _mission_spines as _mission_spines,
    _mission_tip_shas as _mission_tip_shas,
    _mission_work_reaches as _mission_work_reaches,
    _namespace_hit as _namespace_hit,
    _recorded_lane_heads as _recorded_lane_heads,
    _recorded_work_hit as _recorded_work_hit,
    _refused as _refused,
    _verify_declared_ref as _verify_declared_ref,
    dependency_refs_moved_refusal as dependency_refs_moved_refusal,
    resolve_external_dependency_refs as resolve_external_dependency_refs,
)
from specify_cli.consolidation.reconciliation_bound import (
    _BoundVerdict as _BoundVerdict,
    _WriteBranchScope as _WriteBranchScope,
    _approved_bound_verdict as _approved_bound_verdict,
    _bound_approved_wp_ids as _bound_approved_wp_ids,
    _bound_claim_base as _bound_claim_base,
    _bound_claim_base_unresolved_text as _bound_claim_base_unresolved_text,
    _bound_events_unreadable_text as _bound_events_unreadable_text,
    _bound_lanes as _bound_lanes,
    _bound_write_branch as _bound_write_branch,
    _write_branch_verdict as _write_branch_verdict,
    approval_stamp_anchors as approval_stamp_anchors,
    approved_bound_refusal as approved_bound_refusal,
    lane_tips_moved_refusal as lane_tips_moved_refusal,
)
from specify_cli.consolidation.reconciliation_verifier import (
    Divergence as Divergence,
    MergeOutcomeVerifier as MergeOutcomeVerifier,
    VerifyResult as VerifyResult,
    VerifyStatus as VerifyStatus,
    _REFUSE_EMPTY_AUTHORED_BLOBS as _REFUSE_EMPTY_AUTHORED_BLOBS,
    _REFUSE_NO_AUTHORSHIP_AUTHORITY as _REFUSE_NO_AUTHORSHIP_AUTHORITY,
    _REFUSE_WINDOW_BASE_UNRESOLVED as _REFUSE_WINDOW_BASE_UNRESOLVED,
    _RESTORE_IN_PROGRESS as _RESTORE_IN_PROGRESS,
    _fold_divergence as _fold_divergence,
    _merge_canceled_content_into_result as _merge_canceled_content_into_result,
    _refuse_merged_independent_change as _refuse_merged_independent_change,
    _with_attribution_hint as _with_attribution_hint,
    claim_integrity_refusal as claim_integrity_refusal,
    is_legitimate_three_way_resolution as is_legitimate_three_way_resolution,
)

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


def _mixed_lanes(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[ExecutionLane]:
    """Contract C2: every lane with ≥1 approved WP AND ≥1 canceled-with-
    provenance WP, sorted deterministically by lane id.

    ``not lane_fully_canceled(...)`` mirrors the same guard
    :func:`_unresolvable_approved_lane_branches` already applies (US1 AS-exempt
    shape): a lane whose EVERY WP is canceled-with-provenance is not "mixed" —
    there is no surviving WP to compare against — even when
    :func:`_lane_is_approved` alone still counts it true (a WP can be BOTH
    ``approved`` in the reduced snapshot AND canceled-with-provenance per the
    caller's *excluded_canceled_wp_ids*, the "provenance override" shape). Such
    a lane's created branch may legitimately not even exist.
    """

    def _is_mixed(lane: ExecutionLane) -> bool:
        has_approved = _lane_is_approved(lane, work_packages)
        has_canceled = any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids)
        return has_approved and has_canceled and not lane_fully_canceled(lane, excluded_canceled_wp_ids)

    return sorted((lane for lane in lanes_manifest.lanes if _is_mixed(lane)), key=lambda lane: lane.lane_id)


def _mixed_lane_recovery(reason: UnattributableReason, wp_id: str) -> str:
    """Recovery for one mixed-lane REFUSE reason — never one that cannot succeed (FR-012)."""
    if reason is UnattributableReason.EVENTS_UNREADABLE:
        return f"Recovery: repair the mission's status event log (status.events.jsonl) so it reads cleanly, {_RECOVERY_TAIL}; this refusal cannot be overridden"
    if reason is UnattributableReason.SPINE_UNREADABLE:
        return f"Recovery: repair the lane branch so its git history reads from the coordination base, {_RECOVERY_TAIL}; this refusal cannot be overridden"
    if reason is UnattributableReason.CANCELED_LANE_CONTENT:
        return (
            "Re-running alone cannot clear this. "
            "Recovery: remove those commits from the dependent lane by reverting them on it "
            "(do not rebuild the lane: a rebuilt lane trips the resume lane-tip check), "
            f"{_RECOVERY_TAIL}; this refusal cannot be overridden"
        )
    if reason is UnattributableReason.COMMIT_OUTSIDE_WINDOWS:
        return (
            "No governed WP window will ever cover those commits, so re-running alone cannot clear this. "
            f"Recovery: verify by hand that they carry no canceled work and that {wp_id}'s canceled content is "
            f"absent or superseded, then {_attest_tail(wp_id)}"
        )
    return (
        "This attribution evidence cannot appear later (the event log is append-only), so re-running alone "
        f"cannot clear it. Recovery: verify by hand that {wp_id}'s canceled content is absent or superseded on "
        f"the lane, then {_attest_tail(wp_id)}"
    )


def _mixed_lane_unattributable_refusal(lane_id: str, wp_id: str, outcome: Unattributable) -> str:
    """T022's refusal text — names the mixed lane, the canceled WP, the resolver's
    own detail (which itself names lane/WP/evidence, NFR-003), and the recovery
    that works for THIS reason (FR-012)."""
    return f"mixed lane {lane_id}: canceled {wp_id} cannot be attributed — {outcome.detail}. {_mixed_lane_recovery(outcome.reason, wp_id)}."


def _resolve_mixed_lane_canceled_content(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    planning_prefix: str | None,
    target_base: str | None = None,
    sb_window: tuple[str, str] | None = None,
    *,
    canceled_lane_commits: frozenset[str],
    event_log: _ClaimEventLog | None = None,
) -> tuple[frozenset[CanceledPathState], frozenset[str], str | None]:
    """Resolve every mixed lane's canceled-with-provenance WPs (T022/T023).

    Returns ``(canceled_content, attested_wp_ids, refusal)``. Events are read
    through :func:`specify_cli.status.read_events` exactly ONCE per claim
    (*event_log*, shared with :func:`_resolve_canceled_dependency_lanes` and the
    approved-bound check, :func:`_approved_bound_verdict`; a
    caller that passes none gets its own). This function itself reads only when
    at least one mixed lane exists (decided from ``lanes.json`` + the reduced
    snapshot + *excluded_canceled_wp_ids* alone); since #5668 every claim with a
    code lane reads the log once, through the approved-bound check, and its
    mixed-lane verdicts stay byte-identical to pre-#5046 behaviour. A
    ``StoreError`` reading them refuses with the ``events_unreadable`` reason
    (NFR-002; never overridable — the attestation lives in that same log).
    Every canceled WP in every mixed lane is handed to
    :func:`~specify_cli.consolidation.wp_attribution.resolve_canceled_wp`, and every
    one that refuses is named in the returned text (#5720), each refusal unchanged,
    joined in lane and WP order. An unreadable log refuses alone: nothing else can
    be computed without it.

    FR-012: an operator attestation
    (:func:`~specify_cli.consolidation.canceled_attestation.attestation_stamps`)
    adds its own ``lane_head`` stamp as a closed-world anchor for its lane (lane
    commits up to the attestation are exempt; a later straggler is still
    refused), and an attested WP's overridable Unattributable reason falls back
    to the pre-change whole-lane behaviour (no per-WP canceled content).
    Visible canceled content still FAILs.

    *canceled_lane_commits* (#5569/#5613,
    :attr:`_CanceledDependencyResolution.unapproved_commits`: the fully-canceled
    lanes' own commits, less only those a later approved commit fully superseded
    on every lane that carries them) are never exempt from the closed world,
    whichever anchor reaches them. No attestation takes a commit out of that set.
    """
    mixed_lanes = _mixed_lanes(lanes_manifest, work_packages, excluded_canceled_wp_ids)
    if not mixed_lanes:
        return frozenset(), frozenset(), None

    event_log = event_log or _ClaimEventLog(feature_dir)
    events = event_log.read()
    if events is None:
        lane = mixed_lanes[0]
        wp_id = next(wp for wp in sorted(lane.wp_ids) if wp in excluded_canceled_wp_ids)
        return frozenset(), frozenset(), _mixed_lane_unattributable_refusal(lane.lane_id, wp_id, event_log.unreadable(lane.lane_id, wp_id))

    stamps = attestation_stamps(events)
    scope = _MixedLaneScope(
        repo_root=repo_root,
        lanes_manifest=lanes_manifest,
        events=events,
        stamps=stamps,
        excluded_canceled_wp_ids=excluded_canceled_wp_ids,
        coord_base_ref=coord_base_ref,
        target_base=target_base,
        sb_window=sb_window,
        is_bookkeeping=functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix),
        canceled_lane_commits=canceled_lane_commits,
    )
    canceled_content: set[CanceledPathState] = set()
    refusals: list[str] = []
    for lane in mixed_lanes:
        lane_content, lane_refusals = _resolve_mixed_lane(scope, lane)
        canceled_content |= lane_content
        refusals.extend(lane_refusals)
    if refusals:
        # Every canceled WP that refuses is named in this one text (#5720), lanes and WPs in id order.
        return frozenset(), frozenset(), _join_refusals(refusals)
    return frozenset(canceled_content), frozenset(stamps), None


@dataclass(frozen=True)
class _MixedLaneScope:
    """What every mixed lane of one claim shares while its canceled work packages are resolved."""

    repo_root: Path
    lanes_manifest: LanesManifest
    events: Sequence[Any]
    stamps: Mapping[str, str | None]
    excluded_canceled_wp_ids: frozenset[str]
    coord_base_ref: str
    target_base: str | None
    sb_window: tuple[str, str] | None
    is_bookkeeping: Callable[[str], bool]
    canceled_lane_commits: frozenset[str]


def _resolve_mixed_lane(scope: _MixedLaneScope, lane: ExecutionLane) -> tuple[set[CanceledPathState], list[str]]:
    """``(canceled content, refusals)`` of one mixed lane: every canceled WP is resolved, none stops the others (#5720).

    An attested WP whose refusal is overridable (FR-012) falls back to the pre-change
    whole-lane behaviour and adds no refusal.
    """
    # #5100: a protected single_branch repo-root lane reads its authored
    # window ``fork_point..mission_branch`` (same source as the collectors).
    lane_base, branch = (
        scope.sb_window if scope.sb_window and is_planning_lane(lane) else (scope.coord_base_ref, _lane_branch_for(scope.lanes_manifest, lane.lane_id))
    )
    lane_canceled = sorted(wp for wp in lane.wp_ids if wp in scope.excluded_canceled_wp_ids)
    attestation_anchors = [stamp for wp in lane_canceled if (stamp := scope.stamps.get(wp))]
    anchors = [
        *_closed_world_anchors(scope.lanes_manifest, lane, scope.target_base, excluded_canceled_wp_ids=scope.excluded_canceled_wp_ids),
        *attestation_anchors,
    ]
    content: set[CanceledPathState] = set()
    refusals: list[str] = []
    for wp_id in lane_canceled:
        outcome: AttributionOutcome = resolve_canceled_wp(
            scope.repo_root,
            events=scope.events,
            lane_id=lane.lane_id,
            lane_wp_ids=lane.wp_ids,
            canceled_wp_id=wp_id,
            lane_branch=branch,
            coord_base_ref=lane_base,
            is_bookkeeping=scope.is_bookkeeping,
            closed_world_anchors=anchors,
            never_exempt_commits=scope.canceled_lane_commits,
        )
        if isinstance(outcome, Attributed):
            content |= outcome.canceled_content
        elif wp_id in scope.stamps and outcome.reason in OVERRIDABLE_REASONS:
            continue  # FR-012: operator-attested — pre-change whole-lane behaviour for this WP.
        else:
            refusals.append(_mixed_lane_unattributable_refusal(lane.lane_id, wp_id, outcome))
    return content, refusals


def _fully_canceled_lane_commits(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    target_base: str | None,
) -> frozenset[str]:
    """Commits authored by FULLY-canceled lanes since their own base (#5569).

    A fully-canceled lane (every WP canceled-with-provenance) has no approved
    work, so nothing reachable from its tip after its base is authorship of any
    lane. The allocator merges a dependency lane into a dependent lane without
    ``--no-ff``, so a fresh dependent lane fast-forwards and these commits sit on
    the dependent lane's first-parent spine; this set is what
    :func:`_collect_authored` and the closed world subtract so they cannot be
    claimed as approved authorship. "After its base" is the shared
    :func:`~specify_cli.consolidation.wp_attribution.lane_own_commits` over the
    lane's own anchors, so ancestry the lane inherited from approved dependency
    lanes or the target is never counted. A canceled lane whose branch is gone
    yields nothing (claim building tolerates an unresolvable lane, as
    :func:`_lane_tip_commits` documents). A live lane's dependency on such a
    lane is refused by :func:`_unreadable_canceled_dependency_lanes` unless the
    event log proves the lane never started (no branch was ever created, so
    there is nothing to subtract; spec-kitty#5937); call this only after that check.
    """
    by_lane = _fully_canceled_lane_own_commits(repo_root, lanes_manifest, excluded_canceled_wp_ids, coord_base_ref, target_base)
    return frozenset().union(*by_lane.values())


def _fully_canceled_lane_own_commits(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    target_base: str | None,
) -> dict[str, frozenset[str]]:
    """:func:`_fully_canceled_lane_commits`, kept per fully-canceled lane id (#5613)."""
    by_lane: dict[str, frozenset[str]] = {}
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane) or not lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        tip_commits = _lane_tip_commits(repo_root, coord_base_ref, _lane_branch_for(lanes_manifest, lane.lane_id))
        anchors = _closed_world_anchors(lanes_manifest, lane, target_base, excluded_canceled_wp_ids=excluded_canceled_wp_ids)
        by_lane[lane.lane_id] = lane_own_commits(repo_root, coord_base_ref, tip_commits, anchors)
    return by_lane


@dataclass(frozen=True)
class _CanceledLaneQuery:
    """What the fully-canceled dependency lane resolution reads (#5613)."""

    repo_root: Path
    feature_dir: Path
    lanes_manifest: LanesManifest
    work_packages: Mapping[str, Any]
    excluded_ids: frozenset[str]
    coord_base_ref: str
    planning_prefix: str | None
    target_base: str | None
    sb_window: tuple[str, str] | None


@dataclass(frozen=True)
class _CanceledDependencyResolution:
    """Outcome of :func:`_resolve_canceled_dependency_lanes` (#5613).

    ``unapproved_commits`` is what :func:`_collect_authored` and the mixed-lane
    closed world subtract: the fully-canceled lanes' own commits, less the ones a
    later approved commit fully superseded on every lane that carries them.
    Nothing else leaves that set: an attestation lifts a refusal, never a commit.
    """

    unapproved_commits: frozenset[str] = frozenset()
    content: frozenset[CanceledDependencyContent] = frozenset()
    refusal: str | None = None


def _carrier_spines(query: _CanceledLaneQuery, canceled_commits: frozenset[str]) -> dict[str, list[str]]:
    """Approved, not fully-canceled lane id -> its first-parent spine, for lanes that carry a canceled-lane commit."""
    carriers: dict[str, list[str]] = {}
    for lane in query.lanes_manifest.lanes:
        if not _lane_is_approved(lane, query.work_packages) or lane_fully_canceled(lane, query.excluded_ids):
            continue
        lane_branch = _lane_branch_for(query.lanes_manifest, lane.lane_id)
        base, branch = query.sb_window if query.sb_window and is_planning_lane(lane) else (query.coord_base_ref, lane_branch)
        spine = _lane_first_parent_spine(query.repo_root, base, branch)
        if canceled_commits.intersection(spine):
            carriers[lane.lane_id] = spine
    return carriers


def _carried_unattributable_refusal(lane_id: str, wp_id: str, carrier_ids: Sequence[str], outcome: Unattributable) -> str:
    """The refusal for a canceled dependency WP whose carried work has no attribution evidence."""
    return (
        f"canceled {wp_id} (lane {lane_id}) is carried by approved lane(s) {', '.join(carrier_ids)} but cannot be attributed — "
        f"{outcome.detail}. {_mixed_lane_recovery(outcome.reason, wp_id)}."
    )


def _unstamped_carried_refusal(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    carriers: Mapping[str, list[str]],
    event_log: _ClaimEventLog,
) -> str | None:
    """The up-front REFUSE for a carried fully-canceled lane with an unstamped WP, or ``None`` (#5613).

    Every unstamped WP is named in the one text (#5720), lanes and WPs in id order.

    A canceled WP whose closed work window carries no ``lane_head`` stamp has no
    attribution evidence: the claim REFUSEs and names the override, exactly as a
    mixed lane does for ``no_stamp``. That covers a legacy mission (created before
    the stamps) and, identically, a modern mission whose best-effort stamp capture
    failed for that transition: the two cannot be told apart from the log, and the
    evidence cannot appear later in either.

    An operator attestation of that WP lifts THIS refusal and nothing else, and
    only while :data:`~specify_cli.consolidation.canceled_attestation.OVERRIDABLE_REASONS`
    (the one authority) lists ``no_stamp``. It is per WP: every unstamped WP of the
    lane must be attested itself. No commit is lifted with it -- neither the
    attested WP's nor a stamped sibling's -- so the lane's content is still
    resolved over all of its own commits (:func:`_carried_dependency_content`) and
    live content still FAILs with ``CANCELED_REACHABLE_VIA_DEPENDENCY``. An
    unreadable event log refuses and cannot be overridden.
    """
    carried = {lane_id: sorted(c for c, spine in carriers.items() if own.intersection(spine)) for lane_id, own in sorted(own_by_lane.items())}
    carried = {lane_id: carrier_ids for lane_id, carrier_ids in carried.items() if carrier_ids}
    wps_by_lane = {lane.lane_id: sorted(lane.wp_ids) for lane in query.lanes_manifest.lanes}
    events = event_log.read()
    if events is None:
        lane_id, carrier_ids = next(iter(carried.items()))
        wp_id = wps_by_lane[lane_id][0]
        return _carried_unattributable_refusal(lane_id, wp_id, carrier_ids, event_log.unreadable(lane_id, wp_id))
    liftable = frozenset(attestation_stamps(events)) if UnattributableReason.NO_STAMP in OVERRIDABLE_REASONS else frozenset()
    refusals = [
        _carried_unattributable_refusal(lane_id, wp_id, carrier_ids, Unattributable.for_reason(UnattributableReason.NO_STAMP, lane_id, wp_id))
        for lane_id, carrier_ids in carried.items()
        for wp_id in wps_by_lane[lane_id]
        if wp_id not in liftable and lacks_lane_head_stamps(events, wp_id)
    ]
    return _join_refusals(refusals) if refusals else None


def _unreadable_carrier_refusal(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    unreadable: Mapping[str, tuple[list[str], GitProbeError]],
) -> str | None:
    """The REFUSE for carrier lanes whose spine could not be read, or ``None`` (#6313).

    Every canceled WP of every fully-canceled lane an unreadable carrier holds is named
    once, with the unreadable carriers that hold it, lanes and WPs in id order. The
    reason is ``spine_unreadable``, as on a mixed lane, and the recovery names the
    carrier: ``OVERRIDABLE_REASONS`` omits the reason, so no attestation lifts it. A
    probe error is not always a broken branch: a path renamed to more than one target
    raises one too, so the recovery names that fix as well.
    """
    wps_by_lane = {lane.lane_id: sorted(lane.wp_ids) for lane in query.lanes_manifest.lanes}
    refusals: list[str] = []
    for lane_id, own in sorted(own_by_lane.items()):
        held_by = sorted(carrier_id for carrier_id, (spine, _error) in unreadable.items() if own.intersection(spine))
        if not held_by:
            continue
        carriers = ", ".join(held_by)
        errors = "; ".join(f"{carrier_id}: {unreadable[carrier_id][1]}" for carrier_id in held_by)
        refusals.extend(
            f"canceled {wp_id} (lane {lane_id}) is carried by approved lane(s) {carriers} "
            f"but cannot be attributed ({UnattributableReason.SPINE_UNREADABLE.value}) — "
            f"the git history of carrier lane(s) {carriers} could not be read to resolve which canceled content they still carry ({errors}). "
            f"Recovery: repair the branch of carrier lane(s) {carriers} so its history reads, or, when the error reports a path renamed to "
            f"more than one path, keep only one of those renames on the carrier, {_RECOVERY_TAIL}; this refusal cannot be overridden."
            for wp_id in wps_by_lane[lane_id]
        )
    return _join_refusals(refusals) if refusals else None


def _carried_dependency_content(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    carriers: Mapping[str, list[str]],
    canceled: frozenset[str],
) -> tuple[frozenset[str], frozenset[CanceledDependencyContent], str | None]:
    """``(superseded commits, carried content, refusal)`` over every carrier lane's spine (#5613).

    A canceled commit counts as superseded only when it is superseded on EVERY
    carrier that holds it; then it stays in that lane's authorship (its content is
    not the lane's final state) and consolidation is not refused for it. A carrier
    whose spine cannot be read REFUSEs (#6313, :func:`_unreadable_carrier_refusal`):
    subtracting its canceled commits is not enough, because the canceled lines stay in
    the carrier's authored blobs and would ship unnamed.
    """
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=query.lanes_manifest.mission_slug, planning_prefix=query.planning_prefix)
    lane_of = {sha: lane_id for lane_id, own in own_by_lane.items() for sha in own}
    wps_of = {lane.lane_id: tuple(sorted(lane.wp_ids)) for lane in query.lanes_manifest.lanes}
    superseded: set[str] = set()
    live_commits: set[str] = set()
    content: set[CanceledDependencyContent] = set()
    unreadable: dict[str, tuple[list[str], GitProbeError]] = {}
    for carrier_id, spine in carriers.items():
        on_spine = canceled.intersection(spine)
        try:
            lane_superseded, live = canceled_spine_content(query.repo_root, spine, canceled, is_bookkeeping)
        except GitProbeError as exc:
            live_commits |= on_spine
            unreadable[carrier_id] = (spine, exc)
            continue
        superseded |= lane_superseded
        live_commits |= on_spine - lane_superseded
        for path, entry in live.items():
            content.add(CanceledDependencyContent(wps_of[lane_of[entry.sha]], lane_of[entry.sha], carrier_id, path, entry.state, entry.renamed_from))
    return frozenset(superseded - live_commits), frozenset(content), _unreadable_carrier_refusal(query, own_by_lane, unreadable)


def _resolve_canceled_dependency_lanes(query: _CanceledLaneQuery, event_log: _ClaimEventLog | None = None) -> _CanceledDependencyResolution:
    """Resolve the fully-canceled lanes whose commits an approved lane carries (#5569, #5613).

    The base is :func:`_fully_canceled_lane_commits`: every such lane's own commits
    leave the approved claim. Four refinements, none of which runs (and no event
    log is read) for a mission where no approved lane carries such a commit:

    * a canceled WP without ``lane_head`` stamps REFUSEs with the override named,
      until the operator attests it (:func:`_unstamped_carried_refusal`). The
      attestation lifts that refusal only;
    * a canceled commit a later approved commit fully superseded on every carrier
      stays in the claim, so a superseded canceled dependency consolidates --
      whether its WP is stamped, or unstamped and attested;
    * the remaining live content is recorded so the verifier can name it with
      ``CANCELED_REACHABLE_VIA_DEPENDENCY``. It is computed over ALL of the lanes'
      own commits, attested or not: content that would ship always FAILs;
    * a carrier whose spine cannot be read REFUSEs (``spine_unreadable``, #6313),
      as the mixed-lane axis does; no attestation lifts it.
    """
    own_by_lane = _fully_canceled_lane_own_commits(query.repo_root, query.lanes_manifest, query.excluded_ids, query.coord_base_ref, query.target_base)
    own = frozenset().union(*own_by_lane.values())
    carriers = _carrier_spines(query, own) if own else {}
    if not carriers:
        return _CanceledDependencyResolution(unapproved_commits=own)
    refusal = _unstamped_carried_refusal(query, own_by_lane, carriers, event_log or _ClaimEventLog(query.feature_dir))
    if refusal is not None:
        return _CanceledDependencyResolution(refusal=refusal)
    superseded, content, unreadable_refusal = _carried_dependency_content(query, own_by_lane, carriers, own)
    if unreadable_refusal is not None:
        return _CanceledDependencyResolution(refusal=unreadable_refusal)
    return _CanceledDependencyResolution(unapproved_commits=own - superseded, content=content)


class _UnreadableCanceledLane(NamedTuple):
    """A fully-canceled dependency lane the claim refuses (#5569), and why.

    ``log_detail`` is set only when the status event log could not be read to
    prove the lane never started (spec-kitty#5937); it carries the store error.
    """

    lane_id: str
    branch: str
    log_detail: str | None = None

    @property
    def events_unreadable(self) -> bool:
        return self.log_detail is not None


def _missing_canceled_branch_refusal(
    repo_root: Path,
    lane: ExecutionLane,
    branch: str,
    event_log: _ClaimEventLog,
) -> _UnreadableCanceledLane | None:
    """Refuse a fully-canceled dependency lane whose branch is missing, unless it provably never started.

    In order: an unreadable event log refuses (with the store error); a log that
    does not prove :func:`~specify_cli.consolidation.wp_attribution.lane_never_started`
    refuses; a lane-tip ref still recorded for the branch refuses (it is positive
    evidence that the branch existed); otherwise the lane is tolerated (``None``).
    """
    events = event_log.read()
    if events is None:
        detail = event_log.unreadable(lane.lane_id, lane.wp_ids[0]).detail
        return _UnreadableCanceledLane(lane.lane_id, branch, detail)
    if not lane_never_started(events, lane.wp_ids):
        return _UnreadableCanceledLane(lane.lane_id, branch)
    # Lazy import, as phase_teardown does: only this rare arm needs the lane-tip refs.

    if read_tip(repo_root, branch) is not None:
        return _UnreadableCanceledLane(lane.lane_id, branch)
    return None


def _unreadable_canceled_dependency_lanes(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    event_log: _ClaimEventLog,
) -> list[_UnreadableCanceledLane]:
    """Every fully-canceled lane a live lane depends on whose tip is unreadable (#5569).

    :func:`_fully_canceled_lane_commits` tolerates a canceled lane whose branch is gone
    (or whose range git cannot read) and yields nothing for it. That is only safe while
    nobody inherited the lane's commits: the allocator fast-forwards a dependency lane
    into its dependent, so the canceled commits sit on the dependent lane's first-parent
    spine, and an empty set for the canceled lane leaves nothing to subtract — the
    canceled content would be attributed as approved authorship and ship. For such a
    dependency lane the unreadable tip must therefore refuse. A canceled lane nobody
    depends on stays tolerated (its commits are on no live lane's spine).

    One exception (spec-kitty#5937): a missing branch is tolerated when the event log
    positively proves the lane never started
    (:func:`~specify_cli.consolidation.wp_attribution.lane_never_started`: every WP
    canceled from ``planned``/``blocked``, none ever moved into any lane other than
    ``planned``/``blocked``/``canceled``, migration seeds included). A lane branch is
    created only when a WP moves past those lanes (a claim, or ``agent action review``
    on a WP forced into ``for_review``), so such a lane never had a branch and nothing
    of it can be on a dependent's spine. Every
    other case keeps refusing: the log cannot be read, the log does not prove it
    (an empty or partial log is never proof), a lane-tip ref is still recorded for
    the branch, or the branch exists but its range cannot be read.

    *event_log* is the claim's one shared :class:`_ClaimEventLog`; it is read only
    when a canceled dependency's branch is missing. Its unreadable arm is defensive:
    :func:`build_approved_wp_set` materializes the snapshot first, which already
    refuses a malformed log, so it is reached only when the reader fails and the
    snapshot did not. The lane-tip arm (``read_tip``) is an extra fail-closed arm,
    not the proof: ``read_tip`` returns ``None`` on any git failure, and the ref is
    normally cleared when a lane becomes fully terminal.
    """
    live_dependencies = {
        dep
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane) and not lane_fully_canceled(lane, excluded_canceled_wp_ids)
        for dep in _dependency_lane_ids(lanes_manifest, lane)
    }
    unreadable: list[_UnreadableCanceledLane] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda candidate: candidate.lane_id):
        if lane.lane_id not in live_dependencies or is_planning_lane(lane) or not lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        if not branch_exists(repo_root, branch):
            refused = _missing_canceled_branch_refusal(repo_root, lane, branch, event_log)
            if refused is not None:
                unreadable.append(refused)
            continue
        try:
            commits_in_range(repo_root, coord_base_ref, branch)
        except GitProbeError:
            unreadable.append(_UnreadableCanceledLane(lane.lane_id, branch))
    return unreadable


def _unreadable_canceled_dependency_clause(lane: _UnreadableCanceledLane) -> str:
    """One lane's clause of the #5569 refusal; the unreadable-log arm names the log, never a branch restore."""
    lane_id, branch = lane.lane_id, lane.branch
    if lane.events_unreadable:
        return (
            f"fully-canceled lane {lane_id} (branch '{branch}') is a dependency of a live lane but its branch is missing, "
            f"and the status event log could not be read to prove the lane never started ({lane.log_detail}). "
            "Recovery: repair or restore the Mission's status.events.jsonl (for example from git history), "
            "then re-run `spec-kitty consolidate`"
        )
    return (
        f"fully-canceled lane {lane_id} (branch '{branch}') is a dependency of a live lane but its commits cannot be read "
        "(the branch is missing or its history is unreadable): its canceled content, which the dependent lane inherited, "
        f"cannot be told apart from approved work. Recovery: restore '{branch}' (for example "
        f"`git branch {branch} refs/spec-kitty/lane-tip/{branch}` when a lane-tip ref was recorded, or from `git reflog`), "
        "then re-run `spec-kitty consolidate`; if the branch was rebuilt, run `spec-kitty consolidate --abort` before re-running"
    )


def _unreadable_canceled_dependency_refusal_text(unreadable: list[_UnreadableCanceledLane]) -> str:
    """The #5569 fail-closed refusal for a canceled dependency lane whose tip cannot be read."""
    return "; ".join(_unreadable_canceled_dependency_clause(lane) for lane in unreadable)


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


def _unsuperseded_holders(holders: Sequence[ApprovedLaneContent]) -> list[ApprovedLaneContent]:
    """The holders of a path no OTHER holder built atop (a dependent lane supersedes its dependency)."""
    return [holder for holder in holders if not any(holder.lane_id in other.ancestors for other in holders if other is not holder)]


def _presence_gap(states: set[str | None], target: str | None, started_from: Callable[[], set[str | None]]) -> PresenceGap | None:
    """``"absent"`` / ``"unchanged"`` when the *target* state is none of *states*, else ``None``.

    A target holding another, third content is NOT a gap here: that is a merge
    resolution or a later legitimate edit, which the blob-attribution and
    closed-world axes already judge. What this axis adds is the case they cannot
    see because the content is simply not there: the path is absent although
    every unsuperseded lane ends with it present, or the target still holds a
    state the lane started from (the approved change, or deletion, never landed).
    *started_from* is read only when it can decide.
    """
    if target in states:
        return None
    if target is None:
        return _GAP_ABSENT
    return _GAP_UNCHANGED if target in started_from() else None


def _started_from(path: str, holders: Sequence[ApprovedLaneContent], base: Callable[[], str | None], state_at: StateAt | None) -> set[str | None]:
    """The states *holders* started *path* from: the pre-consolidation state, and what each dependency held when it was built on.

    A dependent lane starts from its dependency's tip, so a target that landed
    the dependency's change but not the lane's own still holds what the lane
    started from, not the pre-consolidation state.
    """
    started = {base()}
    if state_at is not None:
        started.update(state_at(fork, path) for holder in holders for fork in holder.dependency_forks.values())
    return started


StateAt = Callable[[str, str], str | None]


def _owns_change(holder: ApprovedLaneContent, path: str, holders: Sequence[ApprovedLaneContent], state_at: StateAt | None) -> bool:
    """False when *holder* only carries what a dependency lane held when *holder* was built on it.

    A dependent lane's first-parent spine includes the dependency lane's commits
    (the allocator fast-forwards them in), so its final state for a path it never
    touched is the dependency's state at that moment. Such a lane neither
    supersedes the dependency (which may have moved on since, e.g. reverted the
    path) nor is the author to name. Unknown (no probe, or no recorded fork)
    counts as its own change, the stricter reading.
    """
    if state_at is None:
        return True
    carried = holder.final_state[path]
    forks = (holder.dependency_forks.get(other.lane_id) for other in holders if other is not holder)
    return not any(fork is not None and state_at(fork, path) == carried for fork in forks)


def _dropped_own_change(holder: ApprovedLaneContent, path: str, base: str | None, state_at: StateAt | None) -> bool:
    """True when *holder*'s final state for *path* is a net change only a LOSS explains on the target.

    Three facts, all read at the lane's own base (``fork_point``), never against
    the target alone:

    * the target still holds *path* as the lane found it (*base* equals the state
      at the fork point). A target that edited, deleted or renamed the path itself
      since the lane was cut produces a merge resolution, not a dropped change;
    * the lane's final state differs from the state at its fork point. A lane that
      left the path as it found it (changed and reverted, by itself or through the
      lanes it was built on) has nothing to land;
    * the lane tip really holds that final state. When a merge on the lane's own
      spine took another version, the lane does not end on what its commits say.

    A content without ``tip`` / ``fork_point`` (hand-built) is read as cut from the
    pre-consolidation target: only the net-change fact applies, against *base*.
    """
    final = holder.final_state[path]
    if state_at is None or holder.tip is None or holder.fork_point is None:
        return final != base
    found_at_fork = state_at(holder.fork_point, path)
    return found_at_fork == base and final != found_at_fork and state_at(holder.tip, path) == final


def _missing_entries(path: str, holders: Sequence[ApprovedLaneContent], unmet: set[str | None], found: PresenceGap) -> list[MissingApprovedContent]:
    """One :class:`MissingApprovedContent` per unmet state, naming every holder that ended on it."""
    entries: list[MissingApprovedContent] = []
    for state in sorted(unmet, key=lambda value: (value is not None, value or "")):
        owners = [holder for holder in holders if holder.final_state[path] == state]
        wp_ids = tuple(dict.fromkeys(wp for owner in owners for wp in owner.wp_ids))
        entries.append(MissingApprovedContent(wp_ids=wp_ids, lane_ids=tuple(owner.lane_id for owner in owners), path=path, expected=state, found=found))
    return entries


def _path_gap(
    path: str,
    holders: Sequence[ApprovedLaneContent],
    target: str | None,
    base_state: Callable[[], str | None],
    state_at: StateAt | None,
) -> list[MissingApprovedContent]:
    """The unmet approved states of ONE path (the body of :func:`unmet_approved_content`).

    The common case costs nothing beyond the target read: the target holds a
    state an unsuperseded holder ended on. Only a candidate gap pays for the
    lane-base reads that decide whether it is a dropped change.
    """
    unsuperseded = _unsuperseded_holders(holders)
    if (
        _presence_gap({holder.final_state[path] for holder in unsuperseded}, target, functools.partial(_started_from, path, unsuperseded, base_state, state_at))
        is None
    ):
        return []
    authors = [holder for holder in holders if _owns_change(holder, path, holders, state_at)]
    live = _unsuperseded_holders(authors)
    found = _presence_gap({holder.final_state[path] for holder in live}, target, functools.partial(_started_from, path, live, base_state, state_at))
    if found is None:
        return []
    base = base_state()
    unmet = {holder.final_state[path] for holder in live if _dropped_own_change(holder, path, base, state_at)}
    return _missing_entries(path, authors, unmet, found)


def unmet_approved_content(
    contents: Sequence[ApprovedLaneContent],
    *,
    target_state: Callable[[str], str | None],
    base_state: Callable[[str], str | None],
    skip: Callable[[str], bool] | None = None,
    state_at: StateAt | None = None,
) -> list[MissingApprovedContent]:
    """Pure presence verdict (#5571): approved lane content the target does not hold.

    Per path, the lanes holding a final state for it are reduced to those no other
    holder was built atop (a dependent lane supersedes the lanes it depends on: it
    deleted, renamed away or reverted the path). Those unsuperseded states are the
    only ones the target must hold. Lanes that are not in *contents* -- canceled or
    unapproved -- never supersede anything, because the claim builder only records
    approved lanes. Independent lanes that ended on different states for one path
    are a merge-resolution case: the target must hold one of them, or something
    else entirely, but not nothing. *skip* names the paths judged elsewhere
    (bookkeeping, canceled WP content).

    A gap is reported only for a lane's OWN NET change on a path the target left
    alone since the lane was cut (:func:`_owns_change`, :func:`_dropped_own_change`),
    judged against the lane's own base through *state_at* ``(ref, path)``. Comparing
    a lane's final state with the target alone would read every path the lanes left
    net unchanged, and every path the target moved meanwhile, as approved work
    dropped. Without *state_at* each lane is taken as cut from the pre-consolidation
    target (*base_state*).
    """
    holders_by_path: dict[str, list[ApprovedLaneContent]] = {}
    for content in contents:
        for path in content.final_state:
            holders_by_path.setdefault(path, []).append(content)
    missing: list[MissingApprovedContent] = []
    for path in sorted(holders_by_path):
        if skip is not None and skip(path):
            continue
        base = functools.cache(functools.partial(base_state, path))
        missing.extend(_path_gap(path, holders_by_path[path], target_state(path), base, state_at))
    return missing


def _order_lane_content(contents: list[ApprovedLaneContent]) -> tuple[ApprovedLaneContent, ...]:
    """Dependency order: every lane after the lanes it depends on, ties by lane id (deterministic)."""
    remaining = {content.lane_id: content for content in contents}
    ordered: list[ApprovedLaneContent] = []
    while remaining:
        ready = sorted(lane_id for lane_id, content in remaining.items() if not (content.ancestors & remaining.keys()))
        if not ready:  # a dependency cycle is invalid input elsewhere; stay deterministic rather than loop
            ready = sorted(remaining)
        for lane_id in ready:
            ordered.append(remaining.pop(lane_id))
    return tuple(ordered)


def _dependency_forks(repo_root: Path, lanes_manifest: LanesManifest, branch: str, spine: Sequence[str], ancestors: Iterable[str]) -> dict[str, str]:
    """Dependency lane id -> the commit of that lane *branch* was built on (newest spine commit the dependency also holds).

    One range read per dependency lane, no path read. A dependency whose branch
    cannot be read, or none of whose commits sit on the spine (it came in through
    a true merge commit), records nothing: the lane's held paths then count as its
    own, the stricter reading.
    """
    forks: dict[str, str] = {}
    for dependency in ancestors:
        try:
            ahead = frozenset(commits_in_range(repo_root, _lane_branch_for(lanes_manifest, dependency), branch))
        except GitProbeError:
            continue
        fork = next((sha for sha in spine if sha not in ahead), None)
        if fork is not None:
            forks[dependency] = fork
    return forks


def _lane_content(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    spine: Sequence[str],
    lane_blobs: set[tuple[str, str]],
    lane_deletions: set[str],
) -> ApprovedLaneContent:
    """An approved lane's final path state, from the SAME walk that produced ``authored_blobs`` (#5571).

    *spine* is the lane's whole first-parent spine, newest first: its head is the
    lane tip and the first parent of its oldest commit is the commit the lane was
    cut from. Both are recorded as refs for the verifier, never read here.
    """
    state: dict[str, str | None] = dict.fromkeys(lane_deletions)
    state.update(dict(lane_blobs))
    approved_wps = tuple(wp for wp in lane.wp_ids if str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES)
    ancestors = _dependency_lane_ids(lanes_manifest, lane)
    return ApprovedLaneContent(
        lane_id=lane.lane_id,
        wp_ids=approved_wps,
        ancestors=frozenset(ancestors),
        final_state=state,
        tip=spine[0] if spine else None,
        fork_point=f"{spine[-1]}^" if spine else None,
        dependency_forks=_dependency_forks(repo_root, lanes_manifest, _lane_branch_for(lanes_manifest, lane.lane_id), spine, ancestors),
    )


def _approved_stamps(lane: object, work_packages: Mapping[str, Mapping[str, object]], presence: _PresenceScope | None) -> tuple[str, ...]:
    """The approval stamps of *lane*'s WPs that are in an approved membership lane (#7307); canceled WPs never count."""
    if presence is None:
        return ()
    stamps: list[str] = []
    for wp in getattr(lane, "wp_ids", ()):
        stamp = presence.approval_stamps.get(wp)
        if stamp and str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES:
            stamps.append(stamp)
    return tuple(stamps)


def _drop_unreviewed_merges(repo_root: Path, spine: list[str], stamps: Sequence[str]) -> list[str]:
    """*spine* less every merge commit no approval stamp in *stamps* reaches (#7307).

    Returns *spine* itself when nothing is dropped. A merge whose parents cannot be read
    is dropped (attributes less; the verifier then REFUSEs on its own probe error).
    """
    kept: list[str] = []
    dropped = False
    for sha in spine:
        try:
            merge = is_merge_commit(repo_root, sha)
        except GitProbeError:
            dropped = True
            continue
        if not merge or any(sha_reachable_from(repo_root, sha, stamp) for stamp in stamps):
            kept.append(sha)
        else:
            dropped = True
    return kept if dropped else spine


def _own_dependency_merges(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: object,
    work_packages: Mapping[str, Mapping[str, object]],
    spine: Sequence[str],
) -> frozenset[str]:
    """*lane*'s merges of its declared, not fully canceled, dependency lanes on its *spine* (#7307)."""
    tips = [
        _lane_branch_for(lanes_manifest, dep.lane_id)
        for dep in lanes_manifest.lanes
        if dep.lane_id in tuple(getattr(lane, "depends_on_lanes", ()) or ()) and _lane_is_approved(dep, work_packages)
    ]
    # ``lane_dependency_merges`` comes from a mypy-skipped module (#7334): the
    # typed local keeps the return honest instead of leaking ``Any``.
    merges: frozenset[str] = lane_dependency_merges(repo_root, spine, tips)
    return merges


def _final_authored_walk(repo_root: Path, first_parent_shas: list[str]) -> tuple[set[tuple[str, str]], set[str]]:
    """FINAL ``(path, blob)``s AND final DELETED paths across a lane's first-parent spine (F5, #5022).

    Walks the spine newest→oldest (``git rev-list`` order) and, per path, keeps
    only the FIRST (hence newest, hence final) state seen — so a superseded
    intermediate ``v1`` is dropped in favor of the lane's final ``v2``, and a path
    deleted-then-re-added ends up present (in ``blobs``), never in ``deletions``. A
    merge commit on the spine contributes nothing (its combined diff is empty for
    a clean auto-merge), so a second-parent-smuggled blob/deletion is never
    recorded as authored. A path whose newest touching commit deletes it has no
    blob at that commit (:func:`blob_id_at` raises); it is marked seen and
    recorded in ``deletions`` instead of ``blobs`` — the lane's own final state for
    that path IS "deleted", so it is legitimate authored authority for the squash
    deletion-attribution axis (#5022), not merely "no shippable blob".

    Computed in ONE spine walk (not two) so :func:`_collect_authored` — the sole
    production caller — never re-reads the same commits' diffs twice.

    FIX D (#5001 landing remediation) — the invariant this axis rests on: the
    squash content axis's soundness depends on lanes being sliced by DISJOINT
    write-scope (project doctrine: lanes collapse by write-scope, not
    dependency — each lane owns a distinct set of paths). Under that invariant
    each content path is authored by exactly ONE approved lane, so "the FINAL
    first-parent blob per (lane, path), unioned across approved lanes" and "the
    final blob per path, full stop" coincide — there is no path two approved
    lanes both touch to disambiguate between. When two approved lanes DO modify
    the SAME path (the invariant violated in practice), this axis alone would
    false-FAIL whenever their independently-resolved final blobs differ from the
    squash's (correctly merged/rebased) resolution. That gap is now partly
    closed downstream: for a path authored by EXACTLY TWO approved lanes,
    :func:`is_legitimate_three_way_resolution` (terminus-merge-resolution-
    attribution / #5051-adjacent) attributes the CLEAN ``git merge-tree``
    resolution as a second chance — so only the genuine same-line-CONFLICT
    sub-case still stays unattributable, pinned as
    ``test_squash_three_way_merge_resolution_is_unattributable`` (strict
    ``xfail``, tracked in #5051). Both remain the SAFE direction (refuse/rollback
    a legitimate merge, never ship unattributed content); the sustainable fix is
    still upstream — restore write-scope disjointness at lane-slicing time (or
    register content-path merge drivers) rather than widen this recognizer
    toward an N-way merge simulator.
    """
    seen_paths: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    for sha in first_parent_shas:
        for path in changed_paths_of(repo_root, sha):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            try:
                blobs.add((path, blob_id_at(repo_root, sha, path)))
            except GitProbeError:
                deletions.add(path)  # deleted at this (newest touching) commit — final state deleted
    return blobs, deletions


def _final_authored_blobs(repo_root: Path, first_parent_shas: list[str]) -> set[tuple[str, str]]:
    """FINAL ``(path, blob)`` per path across a lane's first-parent spine (F5).

    Thin wrapper over :func:`_final_authored_walk` kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    blobs, _deletions = _final_authored_walk(repo_root, first_parent_shas)
    return blobs


def _final_authored_deletions(repo_root: Path, first_parent_shas: list[str]) -> set[str]:
    """FINAL deleted paths across a lane's first-parent spine (#5022 / WP1 T002).

    A path P is a member iff the FIRST (newest) commit on the spine that touches
    P deletes it — the lane's own final state for P is "deleted". A path
    added-then-deleted within the lane IS a member (final state deleted); a path
    deleted-then-re-added is NOT (its final state is present, and it is in
    :func:`_final_authored_blobs` instead — see :func:`_final_authored_walk` for
    the shared newest-first spine walk both draw from).

    Thin wrapper over :func:`_final_authored_walk`, kept as an independently
    testable/importable name; :func:`_collect_authored` calls the combined walk
    directly rather than through this wrapper, to avoid a second spine walk.
    """
    _blobs, deletions = _final_authored_walk(repo_root, first_parent_shas)
    return deletions


def _record_lane_path_contribution(
    path_contributions: dict[str, list[LaneContribution]],
    lane: ExecutionLane,
    lane_blobs: set[tuple[str, str]],
    authored: list[str],
) -> None:
    """Record *lane*'s contribution to every path in its own FINAL blob set.

    Extracted from :func:`_collect_authored` (Sonar complexity ceiling): a lane
    with no authored commits or no final blobs contributes nothing (there is
    no still-resolvable lane commit to record). *authored* is the lane's first-parent
    spine AFTER the fully-canceled lanes' commits are dropped (#5569), so a canceled
    commit is never recorded as the lane's commit. ``authored[0]`` (newest) is
    the lane's own tip on its first-parent spine — a raw SHA, always resolvable
    for the lifetime of the transaction even after a branch ref is deleted; it
    CAN be a merge commit, which is exactly why a fresh :class:`LaneContribution`
    is built PER PATH (never one shared object reused across every path): each
    carries THIS path's own final first-parent-authored blob
    (:attr:`LaneContribution.authored_blob`, ``_blob`` from *lane_blobs*) — the
    fail-closed guard input :func:`is_legitimate_three_way_resolution` checks
    the lane's raw tip-tree blob against before trusting a simulation that feeds
    that tip's FULL tree (#5124 landing fold).
    """
    if not lane_blobs or not authored:
        return
    lane_commit = authored[0]
    for path, blob in lane_blobs:
        path_contributions.setdefault(path, []).append(LaneContribution(lane_id=lane.lane_id, lane_commit=lane_commit, authored_blob=blob))


class _AuthoredClaim(NamedTuple):
    """What :func:`_collect_authored` derives from the approved lanes' spines, in its historical positional order."""

    shas: frozenset[str]
    patch_ids: frozenset[str]
    blobs: frozenset[tuple[str, str]]
    deletions: frozenset[str]
    multi_lane_paths: Mapping[str, tuple[LaneContribution, LaneContribution]]
    lane_content: tuple[ApprovedLaneContent, ...]


@dataclass(frozen=True)
class _PresenceScope:
    """What the presence axis measures every approved code lane from (#5788, #5792 review M1).

    ``base`` is the target's pre-mutation tip (:func:`_bound_claim_base`). ``carried``
    are the commits after ``base`` the mission branch (*coord_base_ref*) already
    holds, or ``None`` when that range cannot be read. ``lane_bases`` maps a lane id
    to its own base, the lane head when its first governed work began
    (:func:`~specify_cli.consolidation.wp_attribution.first_governed_open_stamp`, the
    closed world's first anchor), ``None`` when no stamp names it. ``canceled`` are
    the fully-canceled lanes' own commits measured from ``base`` (L1: the same base as
    the spine they are subtracted from).
    """

    base: str
    carried: frozenset[str] | None
    lane_bases: Mapping[str, str | None]
    canceled: frozenset[str]
    #: Each WP's newest approval stamp (:func:`approval_stamp`), ``None`` when unstamped (#7307).
    approval_stamps: Mapping[str, str | None] = field(default_factory=dict)


def _presence_scope(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_ids: frozenset[str],
    *,
    base: str,
    coord_base_ref: str,
    events: Sequence[Any] | None,
) -> _PresenceScope:
    """Build the :class:`_PresenceScope` of one claim: one range read for the mission branch, the event log already read."""
    try:
        carried: frozenset[str] | None = frozenset(commits_in_range(repo_root, base, coord_base_ref))
    except GitProbeError:
        carried = None
    lane_bases = {lane.lane_id: first_governed_open_stamp(events, frozenset(lane.wp_ids)) for lane in lanes_manifest.lanes} if events is not None else {}
    canceled = _fully_canceled_lane_commits(repo_root, lanes_manifest, excluded_ids, base, base)
    stamps = {wp: approval_stamp(events, wp) for lane in lanes_manifest.lanes for wp in lane.wp_ids} if events is not None else {}
    return _PresenceScope(base=base, carried=carried, lane_bases=lane_bases, canceled=canceled, approval_stamps=stamps)


def _presence_range_unreadable_refusal(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    presence: _PresenceScope,
    coord_base_ref: str,
) -> str | None:
    """The refusal text when an approved code lane would be measured from a mission-branch range that cannot be read, else ``None``.

    Fail-closed, like the squash blob axis (#5013: a git-probe error REFUSEs, it never
    passes vacuously): measuring the lane from *coord_base_ref* instead would restore the
    reading #5788 exists to prevent, so a release that dropped approved code over an
    unreadable range would ship. A claim with no approved code lane measures nothing
    here and is not refused.
    """
    if presence.carried is not None:
        return None
    if not any(_lane_is_approved(lane, work_packages) and not is_planning_lane(lane) for lane in lanes_manifest.lanes):
        return None
    return (
        f"the commits between '{presence.base}' and the mission branch ('{coord_base_ref}') could not be read, "
        "so the approved lanes' code cannot be checked for presence on the target. "
        "Recovery: restore or repair that branch, then re-run"
    )


def _commits_before(repo_root: Path, base: str, lane_base: str | None) -> frozenset[str] | None:
    """The commits after *base* that *lane_base* reaches (they predate the lane's own work), or ``None`` when unknown."""
    if lane_base is None:
        return None
    try:
        return frozenset(commits_in_range(repo_root, base, lane_base))
    except GitProbeError:
        return None


def _presence_spine(repo_root: Path, presence: _PresenceScope, lane_id: str, branch: str) -> list[str]:
    """*lane*'s presence spine: ``base..lane`` first-parent, less what the mission branch carried from before the lane's own base.

    A commit the mission branch carries is the lane's own only when the lane's own
    base does not reach it: the lane authored it after its first governed claim and
    an earlier attempt merged it (#5788). A mission-branch commit made outside every
    lane before the lane was cut is reached by that base and is never the lane's
    content (M1). With no readable lane base every carried commit is dropped, the
    pre-#5788 reading. Raises :class:`GitProbeError` when the mission-branch range
    cannot be read: the claim refuses first (:func:`_presence_range_unreadable_refusal`),
    and this never falls back to the authorship walk, the reading #5788 prevents.
    """
    if presence.carried is None:
        raise GitProbeError(f"the commits after '{presence.base}' that the mission branch carries could not be read")
    before = _commits_before(repo_root, presence.base, presence.lane_bases.get(lane_id))
    dropped = presence.carried if before is None else presence.carried & before
    return [sha for sha in _lane_first_parent_spine(repo_root, presence.base, branch) if sha not in dropped]


def _presence_lane_content(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    walk: _LaneWalk,
    presence: _PresenceScope | None,
    canceled_lane_commits: frozenset[str],
) -> ApprovedLaneContent:
    """*lane*'s :class:`ApprovedLaneContent`, measured from the lane's own base (:func:`_presence_spine`).

    The fully-canceled lanes' commits are dropped before the final states are read,
    both the claim's set and the one measured from the presence base (L1). The
    authorship walk is reused when the presence spine is the same commit list and
    drops nothing more (the common case: the mission branch carries none of the
    lane's commits), so no second diff walk is paid then (L2).
    """
    if presence is None:
        return _lane_content(repo_root, lanes_manifest, lane, work_packages, walk.spine, walk.blobs, walk.deletions)
    spine = _presence_spine(repo_root, presence, lane.lane_id, walk.branch)
    canceled = canceled_lane_commits | presence.canceled
    authored = [sha for sha in spine if sha not in canceled]
    if spine == walk.spine and authored == [sha for sha in walk.spine if sha not in canceled_lane_commits]:
        return _lane_content(repo_root, lanes_manifest, lane, work_packages, walk.spine, walk.blobs, walk.deletions)
    blobs, deletions = _final_authored_walk(repo_root, authored)
    return _lane_content(repo_root, lanes_manifest, lane, work_packages, spine, blobs, deletions)


def _collect_authored(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None = None,
    *,
    canceled_lane_commits: frozenset[str],
    presence: _PresenceScope | None = None,
) -> _AuthoredClaim:
    """Approved lanes → their OWN first-parent SHAs + patch-ids + FINAL blobs + FINAL deletions + multi-lane paths.

    The authorship claim the closed-world content checks attribute against. A lane
    contributes its authorship only when at least one of its WPs is approved/done (a
    fully-canceled lane's commits are NOT approved authorship). Authorship is the
    lane's **first-parent** spine (``git rev-list --first-parent``): a commit a lane
    merged IN from another branch (a removed WP's commit smuggled via a carrier
    merge's second parent) is excluded, so it is never mistaken for approved work.
    Merge commits on the spine yield an empty patch-id and contribute only their SHA.

    *canceled_lane_commits* (#5569, :func:`_fully_canceled_lane_commits`) are dropped
    from every lane's spine before anything is derived from it: a fully-canceled
    dependency lane's commit that the allocator fast-forwarded onto an approved lane's
    first-parent spine is canceled content, never approved authorship. Dropping it
    here removes its SHA, patch-id, blob and deletion from the claim at once, so
    ``_collect_excluded`` keeps it excluded and the squash blob axis cannot attribute
    it. Only the canceled lane's OWN commits go; the approved lane's own commits, and
    ancestry both lanes inherited, stay.

    ``authored_blobs`` (#5013 WS1) is the squash-sound content axis's authority: the
    FINAL first-parent blob per (lane, path), unioned across approved lanes.
    ``authored_deletions`` (#5022 / WP1) is its deletion analogue: the FINAL
    first-parent-DELETED path per lane, unioned across approved lanes — the
    squash deletion-attribution axis's authority for a legitimate approved
    deletion.

    ``multi_lane_paths`` (terminus-merge-resolution-attribution / FR-009,
    smuggled-tip guard added by the #5124 landing fold) is derived in this SAME
    per-lane walk — never a second one: for each approved lane, every path in
    that lane's own ``lane_blobs`` (its FINAL first-parent blob set,
    :func:`_final_authored_walk`) records its OWN, per-path
    :class:`LaneContribution` (:func:`_record_lane_path_contribution`) — one
    contribution per (lane, path), carrying that path's own authored blob,
    never one lane-wide object reused across every path. A path collected from
    EXACTLY two lanes (i.e. two DISTINCT lanes each recorded one contribution
    for it — the per-path widening does not change this count) becomes a
    ``multi_lane_paths`` entry; a path from one lane (the common case under the
    disjoint-write-scope invariant) or from three-or-more lanes is absent — the
    merge-resolution recognizer only ever runs for the exactly-two case
    (Decision 2, ``research.md``).

    The sixth element (#5571) is each approved CODE lane's final path state in
    dependency order (:class:`ApprovedLaneContent`), taken from that same walk.
    A planning (repo-root) lane is left out: its commits already sit on the
    target, so there is nothing to integrate and nothing to be missing.

    *presence* (#5788, #5792 review M1, :class:`_PresenceScope`) is what that sixth
    element measures a lane from: ``base..lane`` from the target's pre-mutation tip
    (:func:`_bound_claim_base`), less the commits the mission branch already carries
    that the lane's own base (its first governed claim stamp) also reaches. Measured
    from *coord_base_ref* alone, a lane the mission branch already carries (an
    earlier attempt merged it; that attempt's later commit, kept by the operator,
    then dropped its content) has an empty range, so its approved content would
    never be judged; measured from the target tip alone, a mission-branch commit
    made outside every lane before the lane was cut would read as the lane's
    approved content. The authorship axes keep *coord_base_ref*. ``None`` measures
    from *coord_base_ref* too.
    """
    shas: set[str] = set()
    patch_ids: set[str] = set()
    blobs: set[tuple[str, str]] = set()
    deletions: set[str] = set()
    path_contributions: dict[str, list[LaneContribution]] = {}
    lane_contents: list[ApprovedLaneContent] = []
    for lane in lanes_manifest.lanes:
        if not _lane_is_approved(lane, work_packages):
            continue
        base, branch = sb_window if sb_window and is_planning_lane(lane) else (coord_base_ref, _lane_branch_for(lanes_manifest, lane.lane_id))
        first_parent = _lane_first_parent_spine(repo_root, base, branch)
        full_authored = [sha for sha in first_parent if sha not in canceled_lane_commits]
        full_blobs, full_deletions = _final_authored_walk(repo_root, full_authored)
        # #7307 review: a merge on the spine counts toward this lane's authorship only
        # when one of its approved WPs' approval stamps reaches it (it was in a reviewed
        # tip). A merge made after the approval is the lane's unreviewed work: the
        # approved bound skips merges, so it is left out here and the verifier judges
        # what it adds beyond its parents (a clean merge carries nothing; any own
        # content FAILs), on the closed-world and the squash blob axes alike.
        reviewed = full_authored if is_planning_lane(lane) else _drop_unreviewed_merges(repo_root, full_authored, _approved_stamps(lane, work_packages, presence))
        # Presence (#5788/#5571): measured from the FULL ``coord_base_ref..lane``
        # spine, unchanged — approved content must be PRESENT on the target.
        if not is_planning_lane(lane):
            lane_contents.append(
                _presence_lane_content(
                    repo_root,
                    lanes_manifest,
                    lane,
                    work_packages,
                    _LaneWalk(base, branch, first_parent, full_blobs, full_deletions),
                    presence,
                    canceled_lane_commits,
                )
            )
        # Authorship (#5968): the squash blob-attribution axis attributes a
        # target blob to the claim when it is some approved lane's authored
        # content. A DEPENDENT lane fast-forwards its dependency's commits onto
        # its own first-parent spine at implement time; when the dependency is
        # REWRITTEN (reset/amend) and re-approved after the fork, that stale
        # inherited copy is no longer reachable from the re-approved dependency
        # but still rides the dependent lane's spine, so the default squash
        # lands it and the axis would attribute it to the dependent lane. Bound
        # such a lane's authorship to its OWN creation base
        # (``first_governed_open_stamp``, carried on ``presence.lane_bases``):
        # everything that base reaches predates the lane's own work and is the
        # dependency's authorship, never this lane's. Measuring from the lane's
        # own base rather than the dependency's current tip is what catches the
        # rewrite. Shrinking the authorship is the fail-closed direction (never
        # attributes more).
        #
        # Only lanes that DECLARE a dependency are bounded: an independent
        # lane's first-parent spine is entirely its own authorship, with nothing
        # inherited to exclude, so bounding it could only wrongly drop its own
        # content (e.g. when its first-claim stamp was recorded at a later tip
        # rather than the creation base). Gating on ``depends_on_lanes`` keeps
        # the fix to the exact shape it closes.
        authored = reviewed
        lane_blobs, lane_deletions = (full_blobs, full_deletions) if reviewed is full_authored else _final_authored_walk(repo_root, reviewed)
        lane_own_base = presence.lane_bases.get(lane.lane_id) if (presence is not None and not is_planning_lane(lane) and lane.depends_on_lanes) else None
        if lane_own_base is not None:
            own = lane_own_commits(repo_root, base, reviewed, [lane_own_base])
            if len(own) != len(reviewed):
                authored = [sha for sha in reviewed if sha in own]
                lane_blobs, lane_deletions = _final_authored_walk(repo_root, authored)
        for sha in authored:
            shas.add(sha)
            pid = patch_id_of(repo_root, sha)
            if pid:
                patch_ids.add(pid)
        # #7307: the lane's own REVIEWED dependency merges (``reviewed`` holds only
        # merges an approval stamp reaches) stay its authorship by SHA even when the
        # #5968 own-base bound above drops them (they predate the first claim stamp).
        # Only the SHA: their blobs stay the dependency's (#5968).
        shas |= _own_dependency_merges(repo_root, lanes_manifest, lane, work_packages, reviewed)
        blobs |= lane_blobs
        deletions |= lane_deletions
        _record_lane_path_contribution(path_contributions, lane, lane_blobs, authored)
    multi_lane_paths = {path: (contributions[0], contributions[1]) for path, contributions in path_contributions.items() if len(contributions) == 2}
    return _AuthoredClaim(frozenset(shas), frozenset(patch_ids), frozenset(blobs), frozenset(deletions), multi_lane_paths, _order_lane_content(lane_contents))


__all__ = [
    "ApprovedWpCommitSet",
    "MergeOutcomeVerifier",
    "TERMINUS_ENTRY_POINTS",
    "UnroutedTerminusPathError",
    "VerifyResult",
    "build_approved_wp_set",
    "claim_integrity_refusal",
    "detect_legacy_in_flight_state",
    "route_terminus",
    "write_post_fix_marker",
]
