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

Layout (WP15): this module holds no logic, only the module docstring, the re-exports and ``__all__``.
The code lives in flat sibling modules, one per unit of the gate:

* ``reconciliation_kernel``: lane branch, spine and dependency helpers, bookkeeping classifier, lane walk.
* ``reconciliation_claim_types``: the claim record, lane content and presence-gap types.
* ``reconciliation_rendering``: refusal wording and the refusal-text joiners.
* ``reconciliation_closed_world``: the closed-world collectors and declared dependency refs.
* ``reconciliation_bound``: the approval-stamp bound and the write-branch verdict.
* ``reconciliation_canceled``: mixed-lane and fully-canceled dependency lane resolution.
* ``reconciliation_authorship``: the authored-content walk and the approved-content presence check.
* ``reconciliation_verifier``: ``MergeOutcomeVerifier`` and the claim-integrity refusal.
* ``reconciliation_claim``: ``build_approved_wp_set`` and the terminus vocabulary.
"""

from __future__ import annotations

from specify_cli.consolidation.git_probes import (
    blob_id_at as blob_id_at,
    commits_in_range as commits_in_range,
    merge_tree_write_tree_available as merge_tree_write_tree_available,
    path_state_at as path_state_at,
)
from specify_cli.consolidation.canceled_attestation import (
    OVERRIDABLE_REASONS as OVERRIDABLE_REASONS,
    attestation_stamps as attestation_stamps,
)
from specify_cli.consolidation.wp_attribution import (
    canceled_spine_content as canceled_spine_content,
    resolve_canceled_wp as resolve_canceled_wp,
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
from specify_cli.consolidation.reconciliation_canceled import (
    _CanceledDependencyResolution as _CanceledDependencyResolution,
    _CanceledLaneQuery as _CanceledLaneQuery,
    _MixedLaneScope as _MixedLaneScope,
    _UnreadableCanceledLane as _UnreadableCanceledLane,
    _carried_dependency_content as _carried_dependency_content,
    _carried_unattributable_refusal as _carried_unattributable_refusal,
    _carrier_spines as _carrier_spines,
    _fully_canceled_lane_commits as _fully_canceled_lane_commits,
    _fully_canceled_lane_own_commits as _fully_canceled_lane_own_commits,
    _missing_canceled_branch_refusal as _missing_canceled_branch_refusal,
    _mixed_lane_recovery as _mixed_lane_recovery,
    _mixed_lane_unattributable_refusal as _mixed_lane_unattributable_refusal,
    _mixed_lanes as _mixed_lanes,
    _resolve_canceled_dependency_lanes as _resolve_canceled_dependency_lanes,
    _resolve_mixed_lane as _resolve_mixed_lane,
    _resolve_mixed_lane_canceled_content as _resolve_mixed_lane_canceled_content,
    _unreadable_canceled_dependency_clause as _unreadable_canceled_dependency_clause,
    _unreadable_canceled_dependency_lanes as _unreadable_canceled_dependency_lanes,
    _unreadable_canceled_dependency_refusal_text as _unreadable_canceled_dependency_refusal_text,
    _unreadable_carrier_refusal as _unreadable_carrier_refusal,
    _unstamped_carried_refusal as _unstamped_carried_refusal,
)
from specify_cli.consolidation.reconciliation_authorship import (
    StateAt as StateAt,
    _AuthoredClaim as _AuthoredClaim,
    _PresenceScope as _PresenceScope,
    _approved_stamps as _approved_stamps,
    _collect_authored as _collect_authored,
    _commits_before as _commits_before,
    _dependency_forks as _dependency_forks,
    _drop_unreviewed_merges as _drop_unreviewed_merges,
    _dropped_own_change as _dropped_own_change,
    _final_authored_blobs as _final_authored_blobs,
    _final_authored_deletions as _final_authored_deletions,
    _final_authored_walk as _final_authored_walk,
    _lane_content as _lane_content,
    _missing_entries as _missing_entries,
    _order_lane_content as _order_lane_content,
    _own_dependency_merges as _own_dependency_merges,
    _owns_change as _owns_change,
    _path_gap as _path_gap,
    _presence_gap as _presence_gap,
    _presence_lane_content as _presence_lane_content,
    _presence_range_unreadable_refusal as _presence_range_unreadable_refusal,
    _presence_scope as _presence_scope,
    _presence_spine as _presence_spine,
    _record_lane_path_contribution as _record_lane_path_contribution,
    _started_from as _started_from,
    _unsuperseded_holders as _unsuperseded_holders,
    unmet_approved_content as unmet_approved_content,
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
from specify_cli.consolidation.reconciliation_claim import (
    TERMINUS_ENTRY_POINTS as TERMINUS_ENTRY_POINTS,
    UnroutedTerminusPathError as UnroutedTerminusPathError,
    _collect_approved_shas as _collect_approved_shas,
    _compound_refusal as _compound_refusal,
    _missing_branch_refusal_text as _missing_branch_refusal_text,
    _refusal_claim as _refusal_claim,
    _unresolvable_approved_lane_branches as _unresolvable_approved_lane_branches,
    build_approved_wp_set as build_approved_wp_set,
    detect_legacy_in_flight_state as detect_legacy_in_flight_state,
    route_terminus as route_terminus,
    write_post_fix_marker as write_post_fix_marker,
)


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
