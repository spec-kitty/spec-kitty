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
* WP membership (approved vs canceled) is read through the **Lamport** reduction
  wrapper (:func:`specify_cli.status.reducer.materialize_snapshot`), never LWW
  ``reduce_parsed`` — so a wall-clock-later approval cannot green-wash a
  committed rejection *in the gate's own claim*. This routing choice lives
  entirely inside ``specify_cli``; it does NOT import or touch
  ``spec_kitty_events`` (C-002);
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
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal, NamedTuple

from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.consolidation.approved_bound import (
    BoundRefusal,
    BoundRefusalCode,
    approval_stamp,
    check_lane,
    commits_beyond,
    content_commits,
    render_refusals,
    resolves_commit,
)
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    blob_id_at,
    changed_paths_in_range,
    changed_paths_of,
    commits_in_range,
    first_parent_commits_in_range,
    merge_tree_write_tree_available,
    patch_id_of,
    patch_ids_in_range,
    path_state_at,
    resolve_commit,
    sha_reachable_from,
    three_way_merge_blob,
)
from specify_cli.consolidation.canceled_attestation import (
    ATTEST_FLAG,
    ATTEST_REASON_FLAG,
    OVERRIDABLE_REASONS,
    attestation_stamps,
)
from specify_cli.consolidation.workspace import post_fix_marker_path
from specify_cli.consolidation.wp_attribution import (
    Attributed,
    AttributionOutcome,
    CanceledPathState,
    Unattributable,
    UnattributableReason,
    canceled_spine_content,
    first_governed_open_stamp,
    lacks_lane_head_stamps,
    lane_own_commits,
    resolve_canceled_wp,
)

logger = logging.getLogger(__name__)

# Lanes that count as "approved" (an acceptable, merge-ready ending) for claim
# membership. ``done`` is included so a resume that already baked ``done`` for a
# WP still recognizes it as claimed (never re-derived here — the strings mirror
# ``status.models.Lane`` values, the single lane vocabulary).
_APPROVED_MEMBERSHIP_LANES: frozenset[str] = frozenset({"approved", "done"})

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

# Fail-closed REFUSE reasons (hoisted per Sonar S1192 — the window-base reason is
# shared by the merge/rebase reachability path and the squash blob-attribution
# path, which must refuse identically when the window base cannot be resolved).
_REFUSE_WINDOW_BASE_UNRESOLVED = "the excluded-content window base could not be resolved; the excluded/closed-world axes cannot be verified (fail-closed)"
# Mixed-lane canceled-content recovery tail (contract C4 / NFR-003, #5046):
# shared by the FAIL rendering (:func:`_describe_canceled_content`) and both
# REFUSE reasons the axis can raise (hoisted per Sonar S1192 — used 4+ times).
_RECOVERY_TAIL = "then re-run spec-kitty consolidate"
#: The compound claim refusal (#5720): the first refusal, then the approved-bound refusals the
#: operator would otherwise meet one run later. The first refusal is never reworded.
_ALSO_HAS = "This Mission also has:"
_BOTH_NEEDED = (
    "Both parts need their own fix, in either order: the recovery in the first part does not approve the new content, "
    "and approving the work package again does not clear the first part. Re-run spec-kitty consolidate after both."
)
#: How the target fails to hold an approved lane's content (:class:`MissingApprovedContent`):
#: the path is not there at all, or it still holds the pre-consolidation state.
PresenceGap = Literal["absent", "unchanged"]
_GAP_ABSENT: PresenceGap = "absent"
_GAP_UNCHANGED: PresenceGap = "unchanged"
#: Error code of the #5571 verdict: an approved lane's final authored content is
#: absent from (or not applied to) the target and no later approved lane
#: superseded the path -- e.g. the operator committed the staged deletions an
#: interrupted run left behind. A content verdict: it FAILs and rolls back.
APPROVED_CONTENT_MISSING = "APPROVED_CONTENT_MISSING"
#: Error code of the #5569 verdict (#5613): a fully-canceled dependency lane's
#: content reached an approved lane through the allocator's fast-forwarded
#: dependency step and is on the target. Rendered alongside the strategy axis's
#: own clause. A content verdict: it FAILs and no attestation lifts it, for a
#: stamped and for a legacy (unstamped) canceled WP alike.
CANCELED_REACHABLE_VIA_DEPENDENCY = "CANCELED_REACHABLE_VIA_DEPENDENCY"
# Squash-only (#5013 F1 corollary, widened by #5022): a production claim whose
# authorship set came back empty — BOTH blobs and deletions — while it lists
# approved WPs cannot attribute any target blob or deletion — the empty loop
# would PASS vacuously, so refuse instead.
_REFUSE_EMPTY_AUTHORED_BLOBS = (
    "the approved-authorship blob and deletion sets are both empty while approved WPs are claimed; "
    "the squash content axis cannot attribute any target blob or deletion (fail-closed)"
)
# FIX C (#5001 landing remediation): NO approved lane resolved any commits and no
# authored blob exists, yet the squash window carries a non-bookkeeping A/M path —
# there is no authorship authority to attribute that content against at all.
_REFUSE_NO_AUTHORSHIP_AUTHORITY = (
    "no approved lane resolved any commits and the authored-blob set is empty, "
    "but the squash window carries non-bookkeeping content; there is no "
    "authorship authority to attribute it against (fail-closed)"
)

# A repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan (#2251) — anchored to the
# repo root (``^``), never anywhere-in-tree, so a product-source path that merely
# CONTAINS a ``kitty-ops/`` segment deeper in the tree is not mistaken for the
# toolchain's own Op-record ledger. Mirrors the ULID shape
# ``coordination/coherence.py`` uses for its (deliberately broader, whole-tree)
# dirty-state-gate classifier.
_KITTY_OPS_ROOT_RECORD = re.compile(r"^kitty-ops/[0-9A-HJKMNP-TV-Z]{26}\.jsonl$")


class VerifyStatus(Enum):
    """Outcome of :meth:`MergeOutcomeVerifier.verify`.

    ``PASS`` alone permits teardown. ``FAIL`` (a proven divergence) and
    ``REFUSE`` (a fail-closed claim that cannot even be evaluated) both forbid
    teardown and force a non-zero exit — the contrapositive of the epic
    invariant.
    """

    # ``auto()`` (not string literals): identity comparison only — the values are
    # never serialized — and it keeps the ruff S105 hardcoded-secret heuristic
    # from misreading a member literally named ``PASS``.
    PASS = auto()
    FAIL = auto()
    REFUSE = auto()


class UnroutedTerminusPathError(RuntimeError):
    """Raised when a terminus path not on the NFR-005 allowlist tries to route."""


@dataclass(frozen=True)
class MissingApprovedContent:
    """One path whose approved final content is not on the target (#5571, ``APPROVED_CONTENT_MISSING``).

    ``wp_ids`` / ``lane_ids`` name every approved WP (and its lane) whose final
    authored state for ``path`` equals the unmet ``expected`` state, so a
    dependency chain names the WP that authored the content as well as the lane
    that carried it. ``expected`` is the blob the lane ended on, or ``None`` for a
    deletion that did not land. ``found`` is the :data:`PresenceGap`: ``"absent"``
    (the path is not on the target) or ``"unchanged"`` (the target still holds the
    pre-consolidation state).
    """

    wp_ids: tuple[str, ...]
    lane_ids: tuple[str, ...]
    path: str
    expected: str | None
    found: PresenceGap


@dataclass(frozen=True)
class CanceledDependencyContent:
    """One path a fully-canceled dependency lane left on an approved lane (``CANCELED_REACHABLE_VIA_DEPENDENCY``).

    ``wp_ids`` are the canceled lane's WPs (the lane is the unit the allocator
    merges, so the content is named by all of them), ``canceled_lane_id`` is that
    lane and ``carrier_lane_id`` the approved lane whose first-parent spine carries
    its commit. ``state`` is the blob the newest canceled commit left at ``path``,
    or ``None`` when it deleted the path.
    """

    wp_ids: tuple[str, ...]
    canceled_lane_id: str
    carrier_lane_id: str
    path: str
    state: str | None


@dataclass(frozen=True)
class ApprovedLaneContent:
    """An approved code lane's FINAL authored state, per path (#5571 presence axis).

    The lane is the unit git integrates, so the final state is per lane and named
    by the lane's approved WPs. ``final_state`` maps a repo-relative path to the
    blob the lane's own first-parent spine ends on, or ``None`` when its final
    state for the path is a deletion (a rename contributes its source as ``None``).
    ``ancestors`` are the lane ids this lane transitively depends on: such a lane
    was built atop them, so its final state supersedes theirs for any path both
    hold. Built from the SAME spine walk as ``authored_blobs`` -- never a second one.

    The last three fields let the presence axis judge only the lane's OWN NET
    change (:func:`unmet_approved_content`); no path is read for them at claim
    build. ``tip`` is the lane tip. ``fork_point`` is the commit the lane was cut
    from (the first parent of its oldest own first-parent commit), the lane's own
    base. ``dependency_forks`` maps a dependency lane id to the commit of that
    lane this lane was built on. A hand-built content leaves them unset, which
    reads as "cut from the pre-consolidation target, and every held path is its own".
    """

    lane_id: str
    wp_ids: tuple[str, ...]
    ancestors: frozenset[str]
    final_state: Mapping[str, str | None]
    tip: str | None = None
    fork_point: str | None = None
    dependency_forks: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Divergence:
    """The specific way the target tree diverged from the approved-WP claim.

    ``missing_approved`` — ``(wp_id, sha)`` pairs whose approved commit is NOT
    reachable from the target (approved work was dropped). ``reachable_excluded``
    — ``(sha, patch_id)`` pairs of excluded (canceled/removed) content that IS
    reachable from the target (removed code shipped); ``sha``/``patch_id`` is
    ``""`` when the match was made on the other axis. ``unattributable_content`` —
    ``(sha, patch_id)`` pairs of CONTENT commits in the merge window that belong to
    NO approved WP's authorship (the closed-world axis: a removed WP's commit that
    rode a carrier lane into the target — #4945/#4977/#4981). ``unattributable_blobs``
    — ``(path, blob)`` pairs from the SQUASH blob-attribution axis
    (:meth:`MergeOutcomeVerifier._unattributable_content_squash`, #5013 WS1): a
    squash destroys commit SHAs and patch-ids, so that axis names a repo-relative
    PATH and a blob sha instead — a distinct shape from ``unattributable_content``,
    rendered with its own vocabulary (Epic #5001 landing fix; the two fields were
    previously conflated, mislabeling a path as a "content commit" truncated to 10
    chars and a blob as a "patch-id"). ``unattributable_deletions`` — repo-relative
    PATHS (no blob — the path no longer has one) from the SQUASH DELETION axis
    (#5022 / WP1): a target path deleted in ``B..target`` that is not attributable
    to any approved lane's own first-parent authored deletion, distinct from
    ``unattributable_blobs`` (which names an Added/Modified path plus its blob).
    ``canceled_content`` — :class:`~specify_cli.consolidation.wp_attribution.CanceledPathState`
    entries (mixed-lane-authorship-soundness / #5046, WP05): a MIXED lane's
    canceled-with-provenance WP left its own, unsuperseded content on the
    target (or undid a surviving WP's approved change — SC-007). Distinct from
    every axis above — those all reason about commits/blobs the manifest never
    approved at all; this one reasons about ONE canceled WP's specific
    per-path content inside a lane the manifest DOES otherwise approve, which
    neither SHA/patch-id reachability (squash destroys them) nor blob-union
    attribution (the survivor's own authored blobs never covered the
    canceled WP's distinct paths) can see.
    """

    missing_approved: tuple[tuple[str, str], ...] = ()
    reachable_excluded: tuple[tuple[str, str], ...] = ()
    unattributable_content: tuple[tuple[str, str], ...] = ()
    unattributable_blobs: tuple[tuple[str, str], ...] = ()
    unattributable_deletions: tuple[str, ...] = ()
    canceled_content: tuple[CanceledPathState, ...] = ()

    #: #5571: approved lane content absent from / not applied to the target and
    #: not superseded by a later approved lane.
    approved_content_missing: tuple[MissingApprovedContent, ...] = ()

    #: #5569/#5613: a fully-canceled dependency lane's content that an approved
    #: lane carries and that is on the target. Never attest-liftable.
    canceled_reachable_via_dependency: tuple[CanceledDependencyContent, ...] = ()

    def describe(self) -> str:
        """Operator-facing, one-line-per-divergence explanation."""
        parts: list[str] = []
        for wp_id, sha in self.missing_approved:
            parts.append(f"approved {wp_id} commit {sha[:10]} is NOT reachable from the target — approved work would be dropped")
        for sha, pid in self.reachable_excluded:
            ident = sha[:10] if sha else f"patch-id {pid[:12]}"
            parts.append(f"excluded (canceled/removed) commit {ident} IS reachable from the target — removed code would ship")
        for sha, pid in self.unattributable_content:
            ident = sha[:10] if sha else f"patch-id {pid[:12]}"
            parts.append(
                f"content commit {ident} (patch-id {pid[:12]}) IS reachable from the "
                "target but belongs to NO approved WP — un-attributable "
                "(removed/canceled work would ship)"
            )
        for path, blob in self.unattributable_blobs:
            parts.append(
                f"file '{path}' (blob {blob[:10]}) IS reachable on the target but belongs to NO approved WP — un-attributable (removed/canceled work would ship)"
            )
        for path in self.unattributable_deletions:
            parts.append(
                f"file '{path}' was DELETED from the target but that deletion is NOT "
                "attributable to any approved WP's own authorship — un-attributable "
                "(data loss: approved content may have been silently removed)"
            )
        for entry in self.canceled_content:
            parts.append(_describe_canceled_content(entry))
        for missing in self.approved_content_missing:
            parts.append(_describe_approved_content_missing(missing))
        for carried in self.canceled_reachable_via_dependency:
            parts.append(_describe_canceled_reachable(carried))
        return "; ".join(parts) if parts else "no divergence"


def _describe_canceled_content(entry: CanceledPathState) -> str:
    """Render one mixed-lane canceled-content divergence clause (contract C4).

    Exactly one internal ``;`` — a situation clause naming the path (in single
    quotes) together with its wording, then a recovery clause — matching the
    binding rendering contract with the real-CLI suite
    (``tests/terminus/test_mixed_lane_canceled_content_verdicts.py`` extracts
    the verdict block, splits it on ``;``, and matches each path to its own
    clause; the recovery clause coming AFTER never shadows the situation
    clause a path-substring search finds first).
    """
    who = f"canceled {entry.wp_id}"
    recovery = f"revert {entry.wp_id}'s change to '{entry.path}' on the lane through a surviving WP's governed work, {_RECOVERY_TAIL}"
    if entry.canceled_state is None:
        situation = f"file '{entry.path}' was deleted by {who} (lane {entry.lane_id}) and that deletion is on the target — approved content would be lost"
    else:
        situation = f"file '{entry.path}' carries {who}'s change (lane {entry.lane_id}) on the target — canceled work would ship"
    return f"{situation}; {recovery}"


def _describe_approved_content_missing(entry: MissingApprovedContent) -> str:
    """Render one #5571 clause: names the approved WP(s), their lane(s) and the path.

    One ``;`` between the situation and the recovery, like
    :func:`_describe_canceled_content`. The recovery names the cause an operator
    can act on: a worktree that was committed while it lagged its own HEAD. The
    axis only reports a path the target itself left alone since the lane was cut
    (:func:`_dropped_own_change`), so the loss is on the mission side and the
    recovery says so: it must never read as advice to revert a target commit.
    """
    who = ", ".join(entry.wp_ids)
    lanes = ", ".join(entry.lane_ids)
    if entry.expected is None:
        what = f"its deletion of '{entry.path}' is not applied to the target"
    elif entry.found == _GAP_ABSENT:
        what = f"file '{entry.path}' is absent from the target"
    else:
        what = f"file '{entry.path}' on the target still holds its pre-consolidation content"
    situation = f"{APPROVED_CONTENT_MISSING}: approved {who} (lane {lanes}) {what} and no later approved WP superseded it — approved work would be dropped"
    recovery = (
        f"restore {who}'s change to '{entry.path}' on the mission branch — the target branch did not change this path, so revert nothing there "
        f"(if you committed the staged changes of a lagging coordination or mission worktree, revert that commit on the mission branch, "
        f"and never commit such changes — discard them with `git reset --hard HEAD`), {_RECOVERY_TAIL}"
    )
    return f"{situation}; {recovery}"


def _describe_canceled_reachable(entry: CanceledDependencyContent) -> str:
    """Render one ``CANCELED_REACHABLE_VIA_DEPENDENCY`` clause: the canceled WP(s), both lanes and the path.

    One ``;`` between the situation and the recovery, like
    :func:`_describe_canceled_content`. No attestation is offered: the content is
    on the target, and an attestation only ever covers attribution evidence.
    """
    who = f"canceled {', '.join(entry.wp_ids)}"
    effect = "its deletion" if entry.state is None else "its change"
    situation = (
        f"{CANCELED_REACHABLE_VIA_DEPENDENCY}: file '{entry.path}' carries {who}'s work (lane {entry.canceled_lane_id}), which reached "
        f"approved lane {entry.carrier_lane_id} through a dependency lane, and {effect} IS on the target — canceled work would ship"
    )
    recovery = (
        f"undo {effect} to '{entry.path}' on lane {entry.carrier_lane_id} through a surviving WP's governed work "
        f"(do not rebuild the lane, and no attestation lifts this while the content ships), {_RECOVERY_TAIL}"
    )
    return f"{situation}; {recovery}"


#: #5318/#5296 (FR-009): printed BEFORE the single rollback authority runs, so it
#: describes the restore as in progress and defers to the per-branch report that
#: follows; it never claims that nothing was mutated.
_RESTORE_IN_PROGRESS = (
    "Every branch this consolidation moved (target, mission and coordination "
    "branches) is being restored to its pre-consolidation commit; the rollback "
    "report below names each branch, and a branch marked NOT restored still "
    "carries this run's commits."
)


@dataclass(frozen=True)
class VerifyResult:
    """Result of a single :meth:`MergeOutcomeVerifier.verify` call."""

    status: VerifyStatus
    divergence: Divergence | None = None
    refusal_reason: str | None = None

    @property
    def is_pass(self) -> bool:
        return self.status is VerifyStatus.PASS

    def recovery_guidance(self) -> str:
        """What the operator should do — printed on a non-PASS gate result."""
        if self.status is VerifyStatus.REFUSE:
            # D-4b (FR-010): the mission→target advance already landed before this
            # gate runs, so a REFUSE (a claim that could not even be evaluated, not
            # "known good") is rolled back the same as a FAIL. This text is printed
            # BEFORE the best-effort compare-and-swap restore runs, so it describes
            # the restore as in progress; the executor warns separately if it could
            # not be applied. Reasons that already end in a period are not doubled.
            reason = (self.refusal_reason or "").rstrip(".")
            return f"Reconciliation refused (fail-closed): {reason}. {_RESTORE_IN_PROGRESS} no teardown ran. Resolve the issue above, then re-run the merge."
        detail = self.divergence.describe() if self.divergence else "unknown divergence"
        return (
            f"Reconciliation FAILED: {detail.rstrip('.')}. {_RESTORE_IN_PROGRESS} "
            "nothing was torn down. Inspect the target branch and the lane tips, then "
            "re-run the merge."
        )

    @classmethod
    def passed(cls) -> VerifyResult:
        return cls(status=VerifyStatus.PASS)

    @classmethod
    def failed(cls, divergence: Divergence) -> VerifyResult:
        return cls(status=VerifyStatus.FAIL, divergence=divergence)

    @classmethod
    def refused(cls, reason: str) -> VerifyResult:
        return cls(status=VerifyStatus.REFUSE, refusal_reason=reason)


@dataclass(frozen=True)
class LaneContribution:
    """One approved lane's contribution to a multi-lane-authored content path,
    PER (lane, path) — never lane-only.

    ``terminus-merge-resolution-attribution`` / FR-009 (widened by the #5124
    landing fold's smuggled-tip guard). ``lane_commit`` is a raw SHA — the
    newest commit on the lane's own first-parent spine — never a branch name,
    so it stays resolvable via git's object store for the lifetime of the
    merge transaction even after a lane branch ref is deleted at teardown.
    ``lane_commit`` CAN be a merge commit (a lane's tip is whatever its own
    first-parent spine's newest commit is, merge or not); its FULL tree can
    therefore carry content beyond the lane's own first-parent authorship — a
    disjoint second-parent hunk merged in from an unrelated (e.g. removed)
    lane, the #4977 carrier mechanism. ``authored_blob`` is the fail-closed
    guard input that catches that: the lane's FINAL first-parent-AUTHORED blob
    for THIS path (the same value :attr:`ApprovedWpCommitSet.authored_blobs`
    would record for this (lane, path)), read straight from
    :func:`_final_authored_walk` at contribution-build time — never
    recomputed. :func:`is_legitimate_three_way_resolution` refuses to simulate
    unless each contributing lane's tip-tree blob at *path* equals this value,
    so a merge-commit tip that smuggled extra content can never feed the
    simulation. Used to supply
    :func:`~specify_cli.consolidation.git_probes.three_way_merge_blob`'s two merge
    inputs (via ``lane_commit``) plus the guard check (via ``authored_blob``);
    blob-identity attribution ITSELF (the actual accepted content) continues
    to come from :attr:`ApprovedWpCommitSet.authored_blobs`, never from here.
    """

    lane_id: str
    lane_commit: str
    authored_blob: str


@dataclass(frozen=True)
class ApprovedWpCommitSet:
    """The claim the verifier trusts — derived once per terminus transaction.

    ``approved`` maps each claimed WP id to its approved commit SHAs, read from
    **lane-branch git tips** (never status rows) after the approved-bound check
    (#5668) found each lane within what its approval stamps name. ``excluded_shas`` /
    ``excluded_patch_ids`` are the canceled/removed commits that must NOT be
    reachable from the target. ``manifest_wp_ids`` is the full set the manifest
    lists (the empty-vs-manifest fail-closed cross-check). ``excluded_window_base``
    bounds the patch-id scan to ``base..target`` (NFR-003). ``surface_resolved``
    is ``False`` and/or ``refusal`` is set when the claim could not be built
    fail-closed — the verifier then REFUSES instead of evaluating.
    """

    approved: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    excluded_shas: frozenset[str] = frozenset()
    excluded_patch_ids: frozenset[str] = frozenset()
    manifest_wp_ids: frozenset[str] = frozenset()
    excluded_window_base: str | None = None
    surface_resolved: bool = True
    refusal: str | None = None
    # Closed-world excluded check (S-D widening; #4945/#4977/#4981). The
    # TRACKED-excluded axis (``excluded_shas``/``excluded_patch_ids``, derived
    # from ``acceptably_canceled_wp_ids``) only names commits whose WP the status
    # surface still lists as canceled. A REMOVED WP's commit merged INTO an
    # approved carrier lane is in no lane / no status row, so the tracked axis
    # never names it and the lane-range approved set counts it as approved — it
    # ships. The closed-world axis closes that: every CONTENT commit in the merge
    # window (``excluded_window_base..target``) must be attributable to an approved
    # WP's OWN authorship (by SHA or patch-id); one that is not is a FAIL. The
    # authorship is the first-parent spine of every approved lane (``authored_*``),
    # so a commit smuggled in via a merge's second parent is never mistaken for
    # approved work. ``enforce_closed_world`` gates the whole check: only the
    # production claim builder (:func:`build_approved_wp_set`) turns it on, so a
    # hand-built claim (unit tests that populate only ``approved``) keeps the
    # pre-widening behavior byte-for-byte.
    enforce_closed_world: bool = False
    authored_shas: frozenset[str] = frozenset()
    authored_patch_ids: frozenset[str] = frozenset()
    # Squash-sound closed-world authorship (#5013 / WS1). The **FINAL**
    # first-parent-authored blob **per (lane, path)** across approved lanes, as
    # ``(repo_rel_path, blob_sha)`` tuples. Content identity (blob), never lane-tip
    # SHAs or per-commit patch-ids (both destroyed by squash), so it survives the
    # DEFAULT squash strategy. Taking the FINAL blob per (lane, path) — not the
    # union of every first-parent commit's blob — is the F5 crux: the union would
    # admit a superseded intermediate ``v1`` and false-PASS a canceled blob matching
    # it. Always the ``(path, blob)`` tuple, never blob-only (F10 — catches
    # identical-content-different-path). Populated by ``_collect_authored`` only in
    # the production claim builder; a hand-built claim leaves it empty and the squash
    # axis stays off (``enforce_closed_world`` unset), preserving pre-widening
    # behavior byte-for-byte.
    authored_blobs: frozenset[tuple[str, str]] = frozenset()
    # Squash-sound closed-world DELETION authority (#5022 / WP1). A path P is a
    # member iff, walking an approved lane's first-parent spine newest→oldest,
    # the FIRST (newest) commit that touches P DELETES it — i.e. the lane's own
    # final state for P is "deleted" (mirrors ``authored_blobs``'s "final blob
    # per path", the deletion analogue). A path added-then-deleted within a lane
    # is a member (final state deleted); a path deleted-then-re-added is NOT (its
    # final state is present, and it is in ``authored_blobs`` instead). Populated
    # by ``_collect_authored`` only in the production claim builder, in the SAME
    # spine walk that produces ``authored_blobs`` (:func:`_final_authored_walk`) —
    # a hand-built claim leaves it empty and the squash deletion axis then treats
    # every ``D`` path as unattributable unless it is bookkeeping, preserving
    # pre-#5022 behavior for any claim that never populates it.
    authored_deletions: frozenset[str] = frozenset()
    # Merge-resolution-aware Seam A attribution (terminus-merge-resolution-
    # attribution / #5051-adjacent, FR-009; smuggled-tip guard added by the
    # #5124 landing fold). For each content path authored by EXACTLY TWO
    # approved lanes (a path outside the disjoint-write-scope invariant
    # `_final_authored_walk` documents), the two contributing lanes' PER-PATH
    # :class:`LaneContribution`s — their still-resolvable pre-squash lane
    # commit SHAs (which CAN be a merge commit) plus, per (lane, path), the
    # lane's own first-parent-AUTHORED blob for that path (the guard input
    # that catches a merge-commit tip smuggling extra content — see
    # :class:`LaneContribution`). One ``LaneContribution`` is now recorded PER
    # (lane, path) — never one shared object reused across every path a lane
    # touches — because the authored blob differs per path.
    # Populated in the SAME first-parent spine walk that builds
    # ``authored_blobs`` (:func:`_collect_authored` / :func:`_final_authored_walk`)
    # — never a second walk. Absent (no key) for a single-lane path (the
    # existing ``authored_blobs`` fast path already attributes those) and for a
    # path touched by three-or-more approved lanes (2-way `merge-tree` folding
    # is order-dependent/nondeterministic for N>2 — Decision 2, ``research.md``
    # — so those stay fail-closed, never simulated). The "exactly two lanes"
    # count is still one contribution per (lane, path) — i.e. per lane per
    # path — so a path is a member iff exactly two DISTINCT lanes recorded a
    # contribution for it, unchanged by the per-path widening. Supplies
    # ``is_legitimate_three_way_resolution``'s two merge inputs AND its
    # fail-closed guard; it never itself supplies the FINAL blob identity that
    # is attributed — that authority stays with ``authored_blobs``.
    # Populated by ``_collect_authored`` only in the production claim builder; a
    # hand-built claim leaves it empty and the merge-resolution recognizer never
    # fires, preserving pre-widening behavior byte-for-byte.
    multi_lane_paths: Mapping[str, tuple[LaneContribution, LaneContribution]] = field(default_factory=dict)
    mission_slug: str | None = None
    # Repo-relative posix path of the mission's planning/status directory
    # (``kitty-specs/<slug>``). A window commit that touches ONLY paths under this
    # prefix (plus toolchain churn) is spec-kitty housekeeping, never content.
    planning_prefix: str | None = None
    # Content reachability (approved-SHA ancestry + excluded SHA/patch-id) is only
    # SOUND for ancestry-preserving strategies (merge/rebase): a squash merge
    # preserves neither lane-tip SHAs, per-lane tree equality, nor per-lane
    # patch-ids (verified empirically), AND the post-merge target carries
    # legitimate bookkeeping commits (mission_number bake, done-transition record)
    # that make even an aggregate mission→target tree comparison diverge. Proving
    # approved content landed under squash therefore requires the projection seam
    # WP07/WP08 own. When ``verify_reachability`` is ``False`` (squash), the
    # verifier still runs the squash-sound blob-attribution content axis (#5013,
    # :meth:`MergeOutcomeVerifier._unattributable_content_squash`) plus fail-closed
    # claim integrity (surface + refusal); only the per-SHA approved-reachability
    # check (structurally unsatisfiable once squash mints new SHAs) is deferred —
    # never false-failing a legitimate squash merge (NFR-004). Fail-closed
    # integrity applies to both strategies. ``True`` (merge/rebase — the Tier-0
    # clean-merge strategy) runs the full per-SHA reachability + excluded checks.
    verify_reachability: bool = True
    # Mixed-lane canceled-content axis (mixed-lane-authorship-soundness / #5046,
    # WP05). Every :class:`~specify_cli.consolidation.wp_attribution.CanceledPathState`
    # resolved for a canceled-with-provenance WP sharing an approved lane with a
    # surviving WP (contract C2 "mixed lane") that entered implementation. NOT
    # reused from ``excluded_shas``/``excluded_patch_ids``: those are SHA/patch-id
    # reachability, which (a) a squash destroys entirely, and (b) even under
    # merge/rebase only proves the canceled WP's OWN commit objects are
    # unreachable — never that a LATER survivor commit didn't carry the exact
    # same bytes forward unchanged (see the corrected ``_collect_excluded``
    # docstring). This axis compares per-path CONTENT instead (blob identity),
    # which both strategies preserve. Populated by ``build_approved_wp_set`` only
    # (via ``wp_attribution.resolve_canceled_wp``); a hand-built claim leaves it
    # empty, so :meth:`MergeOutcomeVerifier._canceled_content_divergence` is a
    # no-op and every existing claim keeps pre-#5046 behaviour byte-for-byte.
    canceled_content: frozenset[CanceledPathState] = frozenset()
    # Operator-attested canceled WPs (FR-012, ``canceled_attestation``): read
    # from the same event log the mixed-lane resolution reads. For these WPs the
    # verifier lifts the "merged with an independent change" REFUSE; a FAIL on
    # their visible canceled content still stands. Empty on a hand-built claim.
    attested_canceled_wp_ids: frozenset[str] = frozenset()

    # #5571: each approved CODE lane's FINAL authored state per path, in dependency
    # order (a lane after every lane it depends on; ties by lane id). The approved-
    # content presence axis (:meth:`MergeOutcomeVerifier._approved_content_divergence`)
    # requires the target to hold it unless a later approved lane built atop this
    # one superseded the path. A NEW field: the ``authored_*`` claim fields are
    # untouched. Populated by ``_collect_authored`` in the same spine walk as
    # ``authored_blobs``; a hand-built claim leaves it empty, which turns the axis off.
    approved_lane_content: tuple[ApprovedLaneContent, ...] = ()

    # #5569/#5613: per-path content a fully-canceled dependency lane left on an
    # approved ("carrier") lane's first-parent spine. The commits behind it are
    # already out of ``authored_*``, so the strategy axes fail on their own; this
    # field lets the verifier name the canceled WP, both lanes and the stable code.
    # Empty on a hand-built claim and on every mission without such a lane.
    canceled_dependency_content: frozenset[CanceledDependencyContent] = frozenset()

    # #5668: the lane tip (branch name, SHA) the approved-bound check validated for every
    # code lane it covered, each resolved once when the lane was checked. The reconciliation
    # gate asks whether content arrived on a lane after exactly these tips. Empty on a
    # hand-built claim and on a mission with no checked lane.
    bound_lane_tips: tuple[tuple[str, str], ...] = ()

    @property
    def is_vacuous_against_manifest(self) -> bool:
        """True when the derived claim is empty while the manifest lists WPs."""
        return not self.approved and bool(self.manifest_wp_ids)


def _refuse_merged_independent_change(entry: CanceledPathState) -> str:
    """C3's final row / D-4 (R2): the target is neither the canceled state, the
    pre-state, nor the window-base state — the canceled change was merged with
    an independent one and the gate cannot prove the canceled content is
    absent. Names the lane, the WP, and the path (NFR-003 / contract C4)."""
    return (
        f"mixed lane {entry.lane_id}: canceled {entry.wp_id}'s change to '{entry.path}' was merged with an "
        f"independent change; the gate cannot prove it is absent. Recovery: revert {entry.wp_id}'s change to "
        f"'{entry.path}' on the lane through a surviving WP's governed work, {_RECOVERY_TAIL}; or, after "
        f"verifying by hand that none of {entry.wp_id}'s canceled change remains in '{entry.path}', "
        f"{_attest_tail(entry.wp_id)}."
    )


def _merge_canceled_content_into_result(result: VerifyResult, canceled_fail: list[CanceledPathState]) -> VerifyResult:
    """Fold the canceled-content FAIL candidates into a strategy axis result (T024).

    A strategy REFUSE always wins unchanged (REFUSE precedes FAIL by
    construction throughout this module). Otherwise, with no canceled-content
    entries this is a no-op (byte-identical for every existing claim); with
    entries, a strategy PASS becomes a FAIL carrying only the canceled-content
    divergence, and a strategy FAIL gets the entries merged onto its existing
    :class:`Divergence` (never replacing its other axes).

    LOAD-BEARING COUPLING (#5046; flagged by two independent review lenses at
    landing): under the default squash strategy the #5013 blob-attribution axis
    is NOT canceled-aware — it attributes the union of the lane's authored blobs,
    which INCLUDES the canceled WP's, so it would treat canceled content as
    approved. This canceled-content axis (`_canceled_content_divergence`,
    strategy-independent, run above the squash branch in `verify`) is therefore
    the SOLE thing that stops canceled content shipping under squash. The two
    axes compose as a fail-closed union here; a future change that narrows,
    short-circuits or empties the canceled-content axis MUST NOT assume the blob
    axis backstops it. Keep the canceled axis running for every mixed lane.
    """
    return _fold_divergence(result, "canceled_content", canceled_fail)


def _fold_divergence(result: VerifyResult, field_name: str, entries: Sequence[object]) -> VerifyResult:
    """Fold one strategy-independent axis's FAIL *entries* into a strategy axis result.

    *field_name* is the tuple field of :class:`Divergence` the entries belong to.
    The composition every such axis shares (see
    :func:`_merge_canceled_content_into_result` for the canceled-content one): a
    REFUSE wins unchanged, no entries is a no-op, a PASS becomes a FAIL carrying
    only these entries, and a FAIL gets them appended to that field while keeping
    its other axes.
    """
    if result.status is VerifyStatus.REFUSE or not entries:
        return result
    existing = result.divergence or Divergence()
    return VerifyResult.failed(replace(existing, **{field_name: (*getattr(existing, field_name), *entries)}))


class MergeOutcomeVerifier:
    """Verifies the merge outcome against the approved-WP claim by reachability.

    Constructed with the repository root; :meth:`verify` is pure with respect to
    the repository — it reads git refs and NEVER mutates (a FAIL/REFUSE leaves
    the ref store, worktrees, and merge state exactly as found).
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo = repo_root

    def verify(self, target_ref: str, approved_wp_set: ApprovedWpCommitSet) -> VerifyResult:
        """Return PASS / FAIL(divergence) / REFUSE for the tree at *target_ref*.

        Order (fail-closed first, so a claim that cannot be evaluated never
        reaches the reachability checks). Steps 1-4 are **strategy-independent**
        — they run for squash too (#5001 FOLD-1: pre-fix the squash early-return
        short-circuited to PASS before the vacuous-manifest check, so an
        empty-claim squash passed vacuously, defeating PP-F3):

        1. an explicit ``refusal`` on the claim → REFUSE;
        2. an unresolved/unmaterialized coord surface → REFUSE;
        3. an empty claim while the manifest lists WPs → REFUSE (PP-F3);
        4. (mixed-lane canceled-content axis, #5046 WP05) a mixed lane's
           canceled-with-provenance WP whose content on the target can neither
           be proven absent nor a merge of the canceled change with an
           independent one → REFUSE; an unresolved window base while entries
           exist → REFUSE; unsuperseded canceled-content entries are collected
           as FAIL candidates and merged into whichever axis below runs next
           (a REFUSE from either axis wins; a FAIL from both axes combines);
        4b. (approved-content presence axis, #5571) an approved lane's final content
           absent from / unchanged on the target with no later approved lane built
           atop it superseding the path → FAIL candidate ``APPROVED_CONTENT_MISSING``
           (merged like step 4's; a git probe error → REFUSE);
        5. (squash / ``verify_reachability=False``) the squash-sound closed-world
           BLOB-attribution axis (#5013 WS1): a production claim with empty
           authorship or a ``None`` window base → REFUSE, a git probe error →
           REFUSE, a target A/M path whose blob is authored by no approved lane →
           FAIL(un-attributable); a hand-built (non-production) claim → PASS;
        6. (production merge/rebase claim) an unresolvable excluded window base →
           REFUSE (#5001 FOLD-3: the excluded/closed-world axes cannot be evaluated);
        7. any approved SHA unreachable from *target_ref* → FAIL(missing);
        8. any excluded SHA/patch-id reachable from *target_ref* → FAIL(excluded);
        9. (closed-world) any CONTENT commit in the merge window attributable to
           no approved WP → FAIL(un-attributable);
        10. a git probe error while scanning the window → REFUSE (#5001 FOLD-3);
        11. otherwise → PASS (or FAIL, if step 4 collected canceled-content entries).
        """
        # Claim integrity is STRATEGY-INDEPENDENT (#5001 FOLD-1) and has ONE
        # authority (#5338): the same predicate refuses at claim time, before any
        # mutation, so a claim reaching this gate normally passes it. The empty-claim
        # check stays hoisted ABOVE the squash early-return (PP-F3).
        refusal = claim_integrity_refusal(approved_wp_set)
        if refusal is not None:
            return VerifyResult.refused(refusal)

        # Mixed-lane canceled-content axis (#5046 WP05): strategy-independent,
        # same as the claim-integrity checks above — it runs for squash too.
        canceled_fail, canceled_refuse = self._canceled_content_divergence(target_ref, approved_wp_set)
        if canceled_refuse is not None:
            return VerifyResult.refused(canceled_refuse)

        # #5571: an approved lane's final content absent from / not applied to the
        # target. Strategy-independent: the ancestry skip (`_lane_already_integrated`)
        # hides it under both squash and merge.
        missing_content, missing_refuse = self._approved_content_divergence(target_ref, approved_wp_set)
        if missing_refuse is not None:
            return VerifyResult.refused(missing_refuse)

        # #5569/#5613: a fully-canceled dependency lane's content carried by an
        # approved lane. Strategy-independent; never lifted by an attestation.
        carried, carried_refuse = self._canceled_dependency_divergence(target_ref, approved_wp_set)
        if carried_refuse is not None:
            return VerifyResult.refused(carried_refuse)

        # Squash (and any strategy that does not preserve content identity):
        # claim integrity held, but SHA/patch-id reachability is unsound (a squash
        # destroys lane-tip SHAs AND per-commit patch-ids). The squash-sound
        # closed-world BLOB-attribution axis runs instead (#5013 WS1). Every
        # fail-closed guard — empty authorship, an unresolvable window base, a git
        # probe error — fires INSIDE that branch, strictly above any PASS (F1
        # corollary), so a squash can no longer short-circuit to a vacuous pass the
        # way the pre-#5013 early-return did.
        if not approved_wp_set.verify_reachability:
            strategy_result = self._verify_squash_content(target_ref, approved_wp_set)
        # Reachability-path fail-closed (#5001 FOLD-3): a production claim
        # (``enforce_closed_world``) whose excluded window base could not be
        # resolved cannot evaluate the excluded/closed-world axes at all. Skipping
        # them silently collapsed to PASS (fail-OPEN); refuse instead.
        elif approved_wp_set.enforce_closed_world and approved_wp_set.excluded_window_base is None:
            strategy_result = VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        else:
            strategy_result = self._verify_merge_reachability(target_ref, approved_wp_set)
        with_canceled = _merge_canceled_content_into_result(strategy_result, canceled_fail)
        with_missing = _fold_divergence(with_canceled, "approved_content_missing", missing_content)
        return _fold_divergence(with_missing, "canceled_reachable_via_dependency", carried)

    def _verify_merge_reachability(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """The Tier-0 merge/rebase axis: per-SHA reachability + excluded/closed-world.

        Extracted from :meth:`verify` (Sonar complexity ceiling) — steps 7-10 of
        its docstring, unchanged in behaviour.
        """
        try:
            missing = self._missing_approved(target_ref, claim)
            excluded = self._reachable_excluded(target_ref, claim)
            unattributable = self._unattributable_content(target_ref, claim)
        except GitProbeError as exc:
            # A window probe errored mid-scan (#5001 FOLD-3): we cannot prove the
            # tree is clean, so refuse rather than pass on unevaluated content.
            return VerifyResult.refused(f"a git probe failed while verifying the merge window: {exc}")
        if missing or excluded or unattributable:
            return VerifyResult.failed(
                Divergence(
                    missing_approved=tuple(missing),
                    reachable_excluded=tuple(excluded),
                    unattributable_content=tuple(unattributable),
                )
            )
        return VerifyResult.passed()

    def _canceled_content_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[CanceledPathState], str | None]:
        """Mixed-lane canceled-content axis (D-4, contract C3; #5046 WP05).

        Evaluates every :class:`CanceledPathState` :attr:`ApprovedWpCommitSet.
        canceled_content` entry the claim builder resolved. Returns
        ``(fail_entries, refuse_reason)`` — a non-``None`` *refuse_reason* means
        the caller must REFUSE outright (claim/window-base integrity, or one
        entry whose target state is a merge of the canceled change with an
        independent one — R2); *fail_entries* otherwise holds every entry whose
        canceled content is still unsuperseded on the target (C3 rows 4-5),
        to be merged into whichever strategy axis runs next. A no-op — ``([],
        None)`` — when the claim carries no canceled-content entries at all
        (every existing claim, and every non-mixed-lane production claim).
        """
        if not claim.canceled_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        fail_entries: list[CanceledPathState] = []
        try:
            for entry in sorted(claim.canceled_content, key=lambda e: (e.lane_id, e.wp_id, e.path)):
                target_state = path_state_at(self._repo, target_ref, entry.path)
                window_state = path_state_at(self._repo, window_base, entry.path)
                if target_state == entry.canceled_state:
                    # C3 rows 4-5: the target still carries the canceled state.
                    # FAIL unless the window base ALSO already carried it AND the
                    # pre-state was merely inherited (never produced on the lane
                    # by a surviving commit) — R4.
                    if window_state != entry.canceled_state or entry.pre_state_by_survivor:
                        fail_entries.append(entry)
                    continue
                if target_state == entry.pre_state or target_state == window_state:
                    continue  # C3 row 3: the canceled change did not land.
                if entry.wp_id in claim.attested_canceled_wp_ids:
                    continue  # FR-012: the operator attested this WP's content is superseded.
                return fail_entries, _refuse_merged_independent_change(entry)
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying the canceled-content window: {exc}"
        return fail_entries, None

    def _approved_content_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[MissingApprovedContent], str | None]:
        """#5571: approved lane content absent from the target, as ``(missing, refuse_reason)``.

        For every approved code lane's final authored path state the target must
        hold it, unless a later approved lane built atop that lane superseded the
        path, the lane left the path net unchanged, or the target moved the path
        itself since the lane was cut (:func:`unmet_approved_content`). Paths a
        canceled WP touches (``canceled_content`` -- judged by its own axis)
        and mission bookkeeping are not judged here. A no-op for a claim without
        ``approved_lane_content`` (every hand-built claim). The probe is read-only;
        a failing FAIL rolls back through the single rollback authority in the
        executor, exactly like every other divergence.
        """
        if not claim.enforce_closed_world or not claim.approved_lane_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        canceled_paths = frozenset(entry.path for entry in claim.canceled_content)
        try:
            missing = unmet_approved_content(
                claim.approved_lane_content,
                target_state=lambda path: path_state_at(self._repo, target_ref, path),
                base_state=lambda path: path_state_at(self._repo, window_base, path),
                skip=lambda path: path in canceled_paths or self._is_bookkeeping_path(path, claim),
                state_at=lambda ref, path: path_state_at(self._repo, ref, path),
            )
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying approved content presence: {exc}"
        return missing, None

    def _canceled_dependency_divergence(self, target_ref: str, claim: ApprovedWpCommitSet) -> tuple[list[CanceledDependencyContent], str | None]:
        """#5569/#5613: carried canceled-dependency content on the target, as ``(hits, refuse_reason)``.

        An entry is a hit when the target holds the state the canceled commit left
        at its path and the window base did not already hold it (then this
        consolidation did not ship it). A no-op when the claim carries none.
        """
        if not claim.canceled_dependency_content:
            return [], None
        window_base = claim.excluded_window_base
        if window_base is None:
            return [], _REFUSE_WINDOW_BASE_UNRESOLVED
        hits: list[CanceledDependencyContent] = []
        try:
            for entry in sorted(claim.canceled_dependency_content, key=lambda e: (e.carrier_lane_id, e.canceled_lane_id, e.path)):
                if path_state_at(self._repo, target_ref, entry.path) != entry.state:
                    continue
                if path_state_at(self._repo, window_base, entry.path) != entry.state:
                    hits.append(entry)
        except GitProbeError as exc:
            return [], f"a git probe failed while verifying canceled dependency content: {exc}"
        return hits, None

    @staticmethod
    def _refusal_reason(claim: ApprovedWpCommitSet) -> str | None:
        # Fail-closed claim integrity — applies to BOTH strategies, ahead of the
        # (strategy-dependent) content reachability checks.
        if claim.refusal is not None:
            return claim.refusal
        if not claim.surface_resolved:
            return "coordination surface is unresolved or unmaterialized"
        return None

    def _missing_approved(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        missing: list[tuple[str, str]] = []
        for wp_id, shas in claim.approved.items():
            for sha in shas:
                if not sha_reachable_from(self._repo, sha, target_ref):
                    missing.append((wp_id, sha))
        return missing

    def _reachable_excluded(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        # Non-vacuous even when the canceled set is empty: both loops always
        # run; an empty excluded set simply yields no matches (never a silent
        # short-circuit to PASS). The patch-id axis catches cherry-picked /
        # re-lettered copies a SHA match would miss.
        reachable: list[tuple[str, str]] = []
        for sha in claim.excluded_shas:
            if sha_reachable_from(self._repo, sha, target_ref):
                reachable.append((sha, patch_id_of(self._repo, sha)))
        if claim.excluded_patch_ids and claim.excluded_window_base is not None:
            window = patch_ids_in_range(self._repo, claim.excluded_window_base, target_ref)
            already = {pid for _sha, pid in reachable}
            for pid in claim.excluded_patch_ids:
                if pid in window and pid not in already:
                    reachable.append(("", pid))
        return reachable

    def _unattributable_content(self, target_ref: str, claim: ApprovedWpCommitSet) -> list[tuple[str, str]]:
        """Closed-world axis: window CONTENT commits not attributable to any approved WP.

        Every content commit reachable in the merge window
        (``excluded_window_base..target``) must be attributable — by SHA or
        patch-id — to an approved WP's OWN authorship (:attr:`authored_shas` /
        :attr:`authored_patch_ids`, the first-parent spine of approved lanes). A
        content commit that is not is a removed/canceled WP's commit that rode a
        carrier lane onto the target (#4945/#4977/#4981) — it is returned as a
        ``(sha, patch_id)`` divergence.

        NON-content commits are never flagged: merge commits (empty patch-id) and
        spec-kitty housekeeping commits (status/meta/matrix/retrospective
        projections — every changed path is bookkeeping) are excluded from the
        content set so a legitimate merge never false-fails (NFR-004). Bounded to
        the window — O(#window commits), never O(repo history) (NFR-003).

        Off unless ``enforce_closed_world`` is set (only the production claim
        builder turns it on), so a hand-built claim keeps the pre-widening
        behavior; also a no-op when the window base is unknown.
        """
        if not claim.enforce_closed_world or claim.excluded_window_base is None:
            return []
        unattributable: list[tuple[str, str]] = []
        for sha in commits_in_range(self._repo, claim.excluded_window_base, target_ref):
            pid = patch_id_of(self._repo, sha)
            if not pid:
                continue  # merge commit / empty diff — never content
            if not self._commit_is_content(sha, claim):
                continue  # spec-kitty housekeeping — status/meta/matrix/retrospective
            if sha in claim.authored_shas or pid in claim.authored_patch_ids:
                continue  # attributable to an approved WP's own authorship
            unattributable.append((sha, pid))
        return unattributable

    def _verify_squash_content(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """Squash-sound content verdict via closed-world BLOB attribution (#5013 WS1).

        A squash merge preserves neither lane-tip SHAs nor per-commit patch-ids, so
        the reachability/patch-id axes are inert under it. This axis compares
        **tree/blob content** instead, which a squash DOES preserve: every
        non-bookkeeping Added/Modified path of the aggregate squash diff
        ``B..target`` must carry a blob authored by an approved lane
        (:attr:`ApprovedWpCommitSet.authored_blobs`); one that is not is
        removed/canceled content that shipped ⇒ FAIL ⇒ the executor's existing
        rollback path reverts the squash advance.

        The axis is opt-in: only a production claim (``enforce_closed_world``, set by
        :func:`build_approved_wp_set`) runs it. A hand-built claim keeps the
        pre-#5013 deferral PASS byte-for-byte. Fail-closed guards fire ABOVE any
        PASS (F1 corollary): a ``None`` window base and a git probe error REFUSE
        rather than pass on unevaluated content.

        Empty ``authored_blobs`` **and** empty ``authored_deletions`` (#5022 — a
        lane whose sole approved contribution is a deletion legitimately has an
        empty ``authored_blobs`` but a non-empty ``authored_deletions``, which is
        real authorship authority, not an absence of one) is split by whether any
        approved lane RESOLVED to commits. When the claim carries approved commit
        SHAs but no authored blobs/deletions at all, the axis cannot attribute
        against a claim it should have been able to build ⇒ REFUSE (fail-closed).
        When NO approved lane resolved to commits at all — the tolerant "lane
        branch absent / already consolidated" state the claim builder legitimately
        yields as empty tuples (``{"WP01": ()}``) — there is no authorship
        authority to attribute against, so the axis defers to the pre-#5013 PASS
        rather than false-fail every target path (NFR-004). This matches the claim
        builder's own lane-resolution tolerance (:func:`_lane_tip_commits` /
        :func:`_lane_first_parent_spine`).
        """
        if not claim.enforce_closed_world:
            return VerifyResult.passed()
        if not claim.authored_blobs and not claim.authored_deletions:
            if any(shas for shas in claim.approved.values()):
                return VerifyResult.refused(_REFUSE_EMPTY_AUTHORED_BLOBS)
            return self._verify_squash_vacuous_authorship(target_ref, claim)
        window_base = claim.excluded_window_base
        if window_base is None:
            return VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        try:
            unattributable_blobs, unattributable_deletions = self._unattributable_content_squash(target_ref, claim, window_base)
        except GitProbeError as exc:
            return VerifyResult.refused(f"a git probe failed while verifying the squash window: {exc}")
        if unattributable_blobs or unattributable_deletions:
            return VerifyResult.failed(
                Divergence(
                    unattributable_blobs=tuple(unattributable_blobs),
                    unattributable_deletions=tuple(unattributable_deletions),
                )
            )
        return VerifyResult.passed()

    def _verify_squash_vacuous_authorship(self, target_ref: str, claim: ApprovedWpCommitSet) -> VerifyResult:
        """FIX C (#5001 landing remediation): no lane resolved commits AND
        ``authored_blobs`` is empty — there is no authorship authority at all
        (distinct from the F1-corollary case above, where ``approved`` names
        non-empty SHA tuples but authorship failed to build).

        The pre-#5001 behavior PASSed unconditionally here — a fail-OPEN vacuous
        PASS: a target that carries real, un-evaluated content ships with no
        attribution check ever running. Now the window diff is inspected; a
        non-bookkeeping Added/Modified path with no authorship authority behind
        it REFUSEs (fail-closed) rather than passing silently. A genuinely
        content-free window (every window path absent, or bookkeeping-only)
        keeps the original PASS deferral (NFR-004) — this matches the claim
        builder's own tolerance for a fully-canceled / already-consolidated lane
        (:func:`_lane_tip_commits` / :func:`_lane_first_parent_spine`).
        """
        window_base = claim.excluded_window_base
        if window_base is None:
            return VerifyResult.refused(_REFUSE_WINDOW_BASE_UNRESOLVED)
        try:
            has_content = self._window_has_non_bookkeeping_change(target_ref, claim, window_base)
        except GitProbeError as exc:
            return VerifyResult.refused(f"a git probe failed while verifying the squash window: {exc}")
        if has_content:
            return VerifyResult.refused(_REFUSE_NO_AUTHORSHIP_AUTHORITY)
        return VerifyResult.passed()

    def _window_has_non_bookkeeping_change(self, target_ref: str, claim: ApprovedWpCommitSet, window_base: str) -> bool:
        """True iff ``window_base..target`` carries any un-authorized A/M/D path.

        Mirrors :meth:`_unattributable_content_squash`'s bookkeeping + deletion-
        authority filter, without reading blobs — this only asks WHETHER
        attributable content exists, never WHICH blob it is (there is no
        authorship set to attribute against here; ``claim.authored_deletions`` is
        always empty in the caller's context, :meth:`_verify_squash_vacuous_authorship`
        — no lane resolved any commits — so a ``D`` path here is never skipped as
        authored, only as bookkeeping). A bookkeeping OR authored-deletion ``D``
        path is not content (#5022); any other path — Added, Modified, or an
        un-authored Deleted — is.
        """
        for status, path in changed_paths_in_range(self._repo, window_base, target_ref):
            if self._is_bookkeeping_path(path, claim):
                continue
            if status.startswith("D") and path in claim.authored_deletions:
                continue  # an approved lane's own final-state deletion — not content
            return True
        return False

    def _unattributable_content_squash(self, target_ref: str, claim: ApprovedWpCommitSet, window_base: str) -> tuple[list[tuple[str, str]], list[str]]:
        """``(unattributable_blobs, unattributable_deletions)`` in ``B..target`` (#5013 / #5022).

        Iterates ``git diff --name-status --no-renames window_base..target``
        (:func:`changed_paths_in_range`). A mission-bookkeeping path is skipped
        entirely (status/meta/matrix/retrospective/planning churn — never content).
        For each **Added/Modified** path, reads the target blob (:func:`blob_id_at`;
        an unexpected probe error propagates as :class:`GitProbeError` ⇒ the caller
        REFUSEs); a ``(path, blob)`` absent from
        :attr:`ApprovedWpCommitSet.authored_blobs` is unattributable. For each
        **Deleted** path (#5022 — previously unconditionally skipped, the silent
        data-loss escape), the path is attributable iff it is in
        :attr:`ApprovedWpCommitSet.authored_deletions` (an approved lane's own
        first-parent spine ends by deleting it); otherwise it is a canceled/removed
        WP's deletion that rode a carrier lane onto the target and is unattributable.
        Bounded by the squash diff size (NFR-003).

        An Added/Modified path whose blob is NOT in ``authored_blobs`` (a single
        approved lane's own final content) gets one more, strictly fail-closed
        chance: :func:`is_legitimate_three_way_resolution` (terminus-merge-
        resolution-attribution / #5051-adjacent, FR-002/003) — a path authored by
        EXACTLY TWO approved lanes whose target blob equals the deterministic
        ``git merge-tree`` resolution of those two lanes' own contributions is a
        genuine merge resolution, not removed content, and is attributed too.
        Every other shape (>2 lanes, a single-lane mismatch, binary, a
        conflicting resolution, git<2.38) stays unattributable — this second
        chance never attributes vacuously; see that function's docstring for the
        full fail-closed ordering.
        """
        unattributable_blobs: list[tuple[str, str]] = []
        unattributable_deletions: list[str] = []
        for status, path in changed_paths_in_range(self._repo, window_base, target_ref):
            if self._is_bookkeeping_path(path, claim):
                continue  # status/meta/matrix/retrospective/planning churn — not content
            if status.startswith("D"):
                if path not in claim.authored_deletions:
                    unattributable_deletions.append(path)
                continue
            blob = blob_id_at(self._repo, target_ref, path)  # raises → REFUSE (F1)
            if (path, blob) in claim.authored_blobs:
                continue
            if is_legitimate_three_way_resolution(self._repo, claim, path, blob):
                continue
            unattributable_blobs.append((path, blob))
        return unattributable_blobs, unattributable_deletions

    def _commit_is_content(self, sha: str, claim: ApprovedWpCommitSet) -> bool:
        """True when *sha* changes at least one path that is NOT mission bookkeeping.

        A commit is spec-kitty housekeeping (NOT content) when every path it
        changed is either toolchain-generated churn (the canonical status/meta/
        matrix denylist) or lives under the mission's planning/status directory
        (``planning_prefix`` — covers the retrospective/tasks/plan artifacts that
        are not status-state kinds). A commit with any other changed path is real
        content, subject to the closed-world attribution check above.
        """
        paths = changed_paths_of(self._repo, sha)
        if not paths:
            return False
        return any(not self._is_bookkeeping_path(path, claim) for path in paths)

    @staticmethod
    def _is_bookkeeping_path(path: str, claim: ApprovedWpCommitSet) -> bool:
        """True when *path* is the MISSION's OWN planning/toolchain surface.

        Thin delegation to the module-level :func:`_is_bookkeeping` (extracted,
        mixed-lane-authorship-soundness / #5046 WP05, so
        :func:`build_approved_wp_set` can hand ``wp_attribution.resolve_canceled_wp``
        the SAME denylist via ``functools.partial`` — never a duplicate one — even
        though the claim does not exist yet at that call site). See that
        function's docstring for the full anchoring rules.
        """
        return _is_bookkeeping(path, claim.mission_slug, claim.planning_prefix)


def _is_bookkeeping(path: str, mission_slug: str | None, planning_prefix: str | None) -> bool:
    """True when *path* is the MISSION's OWN planning/toolchain surface.

    Anchored to three mission/toolchain-owned roots — never a global
    basename match — closing a silent-data-loss defect (Epic #5001 landing
    remediation): this used to delegate to
    :func:`~specify_cli.coordination.coherence.is_toolchain_generated_churn`,
    a DIRTY-STATE-gate classifier that, at the time, matched by bare
    basename anywhere in the repository (``PurePosixPath(path).name ==
    "meta.json"`` matched ``src/config/meta.json`` just as readily as the
    mission's own ``kitty-specs/<slug>/meta.json``). In the squash content
    axis a path that classifier called bookkeeping was skipped BEFORE
    authored-blob attribution, so a removed/canceled WP's commit touching an
    ordinary product-source file merely NAMED like a toolchain artifact rode
    a carrier lane onto the target and shipped at exit 0. #4933 has
    since made ``coherence.py``'s ``meta.json`` leg depth-exact
    (``kitty-specs/<mission>/meta.json`` at any monorepo prefix, plus the
    legacy ``.kittify/meta.json``), but it is still not anchored to THIS
    claim's slug — it exempts ANY mission's ``meta.json`` — and it remains a
    dirty-state-gate predicate with its own consumers. This axis therefore
    keeps its own, narrower classification rather than delegating to it.

    A path counts as bookkeeping only when it is anchored to:

    * a ``kitty-specs/<slug>/`` segment sequence where ``<slug>`` is THIS
      claim's own *mission_slug* — covers the mission's own ``meta.json``,
      ``status.events.jsonl``, issue-matrix, ``traces/``, ``decisions/``,
      retrospective, tasks, and plan artifacts, wherever that segment
      sequence occurs in the path (the repo-root ``kitty-specs/<slug>/…`` a
      merge commit lands directly, AND a coordination-topology worktree's
      nested copy alike);
    * *planning_prefix* as an exact prefix (belt-and-suspenders for a
      hand-built claim that sets the prefix without a ``mission_slug``);
    * a repo-ROOT ``.kittify/`` prefix — encoding-provenance,
      mission-state-audit, and other toolchain-owned state;
    * a repo-ROOT ``kitty-ops/<ULID>.jsonl`` Op-record orphan
      (:data:`_KITTY_OPS_ROOT_RECORD`);
    * for a bare-slug coordination claim only (a NESTED *planning_prefix*), the
      coordination-kind files (status pair, traces, matrices, decision log, review
      cycles) anywhere under the composed directory ``kitty-specs/<alias>/``
      *planning_prefix* ends in
      (:func:`_is_nested_alias_coordination_file`, #5651).

    Any other path — including one that merely shares a bookkeeping
    basename — is real content, subject to the closed-world attribution
    check.

    Extracted to module level (mixed-lane-authorship-soundness / #5046 WP05)
    so :func:`build_approved_wp_set` can bind it via ``functools.partial`` and
    hand it to ``wp_attribution.resolve_canceled_wp`` as the SAME denylist the
    verifier itself uses — the claim (:class:`ApprovedWpCommitSet`) does not
    exist yet at that call site, so the *claim*-taking overload
    (:meth:`MergeOutcomeVerifier._is_bookkeeping_path`) cannot be called there.
    """
    normalized = path.rstrip("/")
    if mission_slug:
        parts = normalized.split("/")
        try:
            specs_index = parts.index(KITTY_SPECS_DIR)
        except ValueError:
            specs_index = -1
        # ``kitty-specs`` segment immediately followed by THIS mission's own
        # slug, wherever it occurs in the path (not just at a literal prefix
        # match). Mission-scoped, never a bare basename: a product path can
        # never satisfy this unless it is literally nested under the
        # mission's own planning directory. Anchoring on the SEGMENT SEQUENCE
        # (not *planning_prefix* alone) closes a real mismatch: under
        # coordination topology *planning_prefix* is derived from the
        # STATUS_STATE placement's ``feature_dir`` (the coord WORKTREE's
        # nested copy, e.g. ``.worktrees/<slug>-<mid8>-coord/kitty-specs/
        # <slug>``), while the commits this axis scans land the mission's
        # bookkeeping directly at the repo-root ``kitty-specs/<slug>/`` — the
        # two paths never share a common prefix, so relying on
        # *planning_prefix* alone silently stopped recognizing the
        # mission's own ``status.json`` / ``status.events.jsonl`` / etc. as
        # bookkeeping once the whole-tree churn classifier was dropped.
        if specs_index != -1 and specs_index + 1 < len(parts) and parts[specs_index + 1] == mission_slug:
            return True
    if planning_prefix and (normalized == planning_prefix or normalized.startswith(planning_prefix + "/")):
        return True
    if normalized == KITTIFY_DIR or normalized.startswith(KITTIFY_DIR + "/"):
        return True
    if _is_nested_alias_coordination_file(normalized, mission_slug, planning_prefix):
        return True
    return bool(_KITTY_OPS_ROOT_RECORD.match(normalized))


def _is_nested_alias_coordination_file(path: str, mission_slug: str | None, planning_prefix: str | None) -> bool:
    """True when *path* is a coordination-kind file of the composed directory a bare-slug coordination claim names.

    A bare-slug coordination Mission keeps its primary directory at
    ``kitty-specs/<slug>`` while the coordination seed writes its coordination
    records (the status pair, traces, matrices, the decision log, review cycles)
    under the composed ``kitty-specs/<slug>-<mid8>`` directory (#5651). The claim's
    *planning_prefix* is then the NESTED coordination-worktree path whose last
    segment is that composed name, and the name is read from it, never rebuilt from
    the slug. Only a root-anchored path ``kitty-specs/<alias>/<file>``, at any depth
    below the directory, whose file is a coordination kind
    (:func:`~specify_cli.coordination.coherence.is_coordination_kind_file`, the predicate
    the seed itself uses to decide what to carry) qualifies; a planning file, source, an
    unclassified file and any other directory stay content. A root-form or absent prefix,
    or one that already names the primary directory, never applies this rule.
    """
    if not planning_prefix:
        return False
    prefix_parts = planning_prefix.rstrip("/").split("/")
    # <something>/kitty-specs/<alias>: nested, so the older exact-prefix rule cannot see it.
    if len(prefix_parts) < 3 or prefix_parts[-2] != KITTY_SPECS_DIR or not all(prefix_parts[:-2]):
        return False
    alias = prefix_parts[-1]
    parts = path.split("/")
    if alias == mission_slug or len(parts) < 3 or parts[0] != KITTY_SPECS_DIR or parts[1] != alias:
        return False
    # Function-local: this module imports nothing from the coordination package at its top.
    from specify_cli.coordination.coherence import is_coordination_kind_file

    return is_coordination_kind_file("/".join(parts[2:]))


def is_legitimate_three_way_resolution(
    repo_root: Path,
    claim: ApprovedWpCommitSet,
    path: str,
    target_blob: str,
) -> bool:
    """True iff *target_blob* is the deterministic 2-way merge of *path*'s two
    approved-lane contributions (Seam A merge-resolution recognizer,
    terminus-merge-resolution-attribution / #5051-adjacent, FR-002/FR-003).

    Called ONLY as :meth:`MergeOutcomeVerifier._unattributable_content_squash`'s
    second chance, after the ``authored_blobs`` single-lane fast path has already
    missed — every guard below fires strictly ABOVE any attribution (F1
    corollary), so this never attributes vacuously:

    1. *path* absent from :attr:`ApprovedWpCommitSet.multi_lane_paths` (not
       authored by exactly two approved lanes: zero, one, or three-or-more) →
       ``False`` — the simulation never even runs (Decision 2, ``research.md``:
       2-way ``merge-tree`` folding is order-dependent/nondeterministic for N>2).
    2. The installed git does not support ``git merge-tree --write-tree`` (git<
       2.38, :func:`~specify_cli.consolidation.git_probes.merge_tree_write_tree_available`)
       → ``False`` (Decision 3: fail-closed fallback, no unsound raw-``merge-
       file`` substitute).
    3. Smuggled-tip guard (#5124 landing fold — closes the reopened #4977
       carrier-lane threat): ``lane_commit`` is a raw lane TIP and CAN be a
       merge commit. ``three_way_merge_blob`` below feeds it that commit's
       FULL tree, not just its first-parent authorship — so if a contributing
       lane's tip is a merge commit that smuggled a disjoint SECOND-parent hunk
       into *path* (content ``_final_authored_walk``/``authored_blobs``
       deliberately excludes, being first-parent-only), the simulation would
       reproduce the smuggled hunk right along with the legitimate edit, and a
       target that shipped it would match. The guard: for each of the two
       contributions, the lane's OWN tip-tree blob at *path*
       (:func:`~specify_cli.consolidation.git_probes.blob_id_at`) must equal that
       contribution's recorded first-parent-authored blob
       (:attr:`LaneContribution.authored_blob`) — the value the same spine walk
       already vetted as pure first-parent authorship. A mismatch means the
       tip carries unvetted content beyond what was authored → refuse to
       simulate → ``False`` (the path stays unattributable, FAILing the gate
       and CAS-reverting the target, never shipping the smuggled hunk). A
       :class:`~specify_cli.consolidation.git_probes.GitProbeError` from ``blob_id_at``
       here is NOT caught — it propagates to the caller
       (:meth:`MergeOutcomeVerifier._unattributable_content_squash`), which lets
       it bubble to :meth:`MergeOutcomeVerifier._verify_squash_content`'s
       ``except GitProbeError`` → REFUSE, the fail-closed outcome for an
       unevaluable probe. The legitimate clean disjoint-hunk case (each lane's
       tip IS its own authored blob — no second parent, or a merge commit whose
       combined diff was empty) passes this guard unchanged.
    4. Otherwise, simulate the 2-way merge of the two lanes' OWN commits
       (:func:`~specify_cli.consolidation.git_probes.three_way_merge_blob` — the ONLY
       inputs are those two commits; git derives their common ancestor, so no
       third input, e.g. a canceled/removed hunk, can ever be smuggled in) and
       compare its result for *path* to *target_blob*. A conflicting resolution,
       a binary conflict, or an absent result path all come back as ``None``
       from the simulation and compare unequal → ``False``.

    This is the PER-SEAM recognizer (research open-item 3): it is intentionally
    NOT physically shared with Seam B's presence-under-union check — blob-merge
    and block-presence are conceptually and mechanically distinct questions.
    """
    contributions = claim.multi_lane_paths.get(path)
    if contributions is None:
        return False
    if not merge_tree_write_tree_available(repo_root):
        return False
    lane_a, lane_b = contributions
    for contribution in (lane_a, lane_b):
        if blob_id_at(repo_root, contribution.lane_commit, path) != contribution.authored_blob:
            return False
    resolved_blob = three_way_merge_blob(repo_root, lane_a.lane_commit, lane_b.lane_commit, path)
    return resolved_blob == target_blob


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
) -> ApprovedWpCommitSet:
    """Derive the fail-closed, Lamport-sourced claim once per transaction (T027).

    * WP membership is read through the **Lamport** reduction wrapper
      :func:`specify_cli.status.reducer.materialize_snapshot` (never LWW
      ``reduce_parsed``), so a wall-clock-later approval cannot override a
      committed rejection in the claim (C-002 preserved — no ``spec_kitty_events``
      edit);
    * approved commit SHAs still come from **lane-branch git tips** relative to
      *coord_base_ref* (never status rows), but the approved-bound check in front of the
      collectors (:func:`_approved_bound_verdict`, #5668) refuses a lane whose tip holds
      content beyond what the approval stamps name, so the live tip equals the approved
      content up to tool-made merges and bookkeeping commits;
    * fail-closed: an unmaterializable coord surface, or a claim that is empty
      while the manifest lists WPs, yields a REFUSE-shaped claim.
    """
    # Imported lazily so this module stays import-light and the status facade is
    # resolved through ``specify_cli.status`` (C-002: the Lamport wrapper only).
    from specify_cli.status import materialize_snapshot

    manifest_wp_ids = frozenset(wp for lane in lanes_manifest.lanes for wp in lane.wp_ids)
    planning_prefix = _planning_prefix(repo_root, feature_dir)
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
    unreadable_canceled = _unreadable_canceled_dependency_lanes(repo_root, lanes_manifest, excluded_ids, coord_base_ref)
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
    event_log = _ClaimEventLog(feature_dir)
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

    approved = _collect_approved_shas(repo_root, lanes_manifest, work_packages, coord_base_ref, sb_window)
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
        presence=_presence_scope(
            repo_root,
            lanes_manifest,
            excluded_ids,
            base=_bound_claim_base(repo_root, excluded_window_base, coord_base_ref),
            coord_base_ref=coord_base_ref,
            events=event_log.read(),
        ),
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
    )


def _join_refusals(refusals: Sequence[str]) -> str:
    """One text for several refusals of one kind, in the order given: every refusal is named, none is reworded.

    One refusal per line: each ends in a sentence of its own, so a ``; `` join would read ``....; mixed lane ...``.
    The sibling multi-refusal texts further down join with ``; `` and stay as they are.
    """
    return "\n".join(refusals)


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


class _ClaimEventLog:
    """The mission's status events for ONE claim build: read lazily, and at most once.

    The canceled-dependency resolution and the mixed-lane resolution both need
    the log, each only for some missions; whichever asks first pays the read and
    the other reuses it. A ``StoreError`` is remembered the same way, so both
    report the same unreadable log (NFR-002; never overridable — the attestation
    lives in that same log).
    """

    def __init__(self, feature_dir: Path) -> None:
        self._feature_dir = feature_dir
        self._events: Sequence[Any] | None = None
        self._error: Exception | None = None

    def read(self) -> Sequence[Any] | None:
        """The events in append order, or ``None`` when the log cannot be read (then use :meth:`unreadable`)."""
        if self._events is None and self._error is None:
            # Lazy import: keeps this module import-light, as in ``build_approved_wp_set``.
            from specify_cli.status import StoreError, read_events

            try:
                self._events = read_events(self._feature_dir)
            except StoreError as exc:
                self._error = exc
        return self._events

    def unreadable(self, lane_id: str, wp_id: str) -> Unattributable:
        """The ``events_unreadable`` outcome naming *lane_id* / *wp_id* and the store error."""
        outcome = Unattributable.for_reason(UnattributableReason.EVENTS_UNREADABLE, lane_id, wp_id)
        return Unattributable(outcome.reason, f"{outcome.detail} ({self._error})")


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
    ``approved`` in the Lamport snapshot AND canceled-with-provenance per the
    caller's *excluded_canceled_wp_ids*, the "provenance override" shape). Such
    a lane's created branch may legitimately not even exist.
    """

    def _is_mixed(lane: ExecutionLane) -> bool:
        has_approved = _lane_is_approved(lane, work_packages)
        has_canceled = any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids)
        return has_approved and has_canceled and not lane_fully_canceled(lane, excluded_canceled_wp_ids)

    return sorted((lane for lane in lanes_manifest.lanes if _is_mixed(lane)), key=lambda lane: lane.lane_id)


def _attest_tail(wp_id: str) -> str:
    """The FR-012 override step, named in every REFUSE it can lift."""
    return f're-run spec-kitty consolidate with {ATTEST_FLAG} {wp_id} {ATTEST_REASON_FLAG} "<what you checked>"'


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
    at least one mixed lane exists (decided from ``lanes.json`` + the Lamport
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


@dataclass(frozen=True)
class _BoundVerdict:
    """The approved-bound outcome of one claim: a refusal, or the lane tips it validated."""

    refusal: str | None = None
    lane_tips: tuple[tuple[str, str], ...] = ()


def _bound_events_unreadable_text(lane_id: str) -> str:
    return (
        f"the status event log could not be read, so the approvals of lane {lane_id} cannot be bounded to what was reviewed. "
        "Recovery: repair or restore status.events.jsonl, then re-run"
    )


def _bound_claim_base_unresolved_text(claim_base: str) -> str:
    return (
        f"the commit the approved lanes are measured from ('{claim_base}') does not resolve, so their approvals cannot be bounded to what was reviewed. "
        "Recovery: restore that branch or commit, then re-run"
    )


def _bound_approved_wp_ids(
    lane: ExecutionLane,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[str]:
    """The work package ids of *lane* whose approval bounds it: approved membership, not canceled-with-provenance."""
    return [wp for wp in lane.wp_ids if wp not in excluded_canceled_wp_ids and str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES]


def _bound_lanes(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[ExecutionLane]:
    """The code lanes the approved bound covers, by lane id: not planning, not fully canceled, with an approved work package."""
    covered = [
        lane
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane)
        and not lane_fully_canceled(lane, excluded_canceled_wp_ids)
        and _bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids)
    ]
    return sorted(covered, key=lambda lane: lane.lane_id)


def _bound_claim_base(repo_root: Path, window_base: str | None, coord_base_ref: str) -> str:
    """What a lane's own range is measured from: the target's pre-mutation tip when it resolves, else *coord_base_ref*.

    The target's pre-mutation tip (persisted on a resume, the live tip on a fresh run)
    predates every commit this run merges, so a post-approval commit that the mission
    branch already carries is not reachable from it. A live mission-branch (or
    coordination) tip is not: on a resume it already holds what the interrupted run merged.
    """
    return window_base if window_base and resolves_commit(repo_root, window_base) else coord_base_ref


def approval_stamp_anchors(events: Sequence[Any], lanes: Sequence[ExecutionLane], work_packages: Mapping[str, Any], excluded: frozenset[str]) -> list[str]:
    """The approval stamps of every bounded lane: reviewed content the tool's own mission-branch merges bring into another lane."""
    stamps = (approval_stamp(events, wp_id) for lane in lanes for wp_id in _bound_approved_wp_ids(lane, work_packages, excluded))
    return [stamp for stamp in stamps if stamp is not None]


def _approved_bound_verdict(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
    *,
    coord_base_ref: str,
    window_base: str | None,
    planning_prefix: str | None,
    event_log: _ClaimEventLog,
) -> _BoundVerdict:
    """Check every covered code lane against its approval stamps (#5668); read the log once via *event_log*.

    A lane that also holds a canceled work package is checked like any other: no commit,
    status event or attestation of a canceled work package covers a commit (#5720).

    The refused lanes render as one text (:func:`~specify_cli.consolidation.approved_bound.render_refusals`),
    a line per lane in lane order. A lane tip is resolved once and both checked and recorded, so the gate re-check asks about
    exactly the commit this check validated.
    """
    lanes = _bound_lanes(lanes_manifest, work_packages, excluded_canceled_wp_ids)
    if not lanes:
        return _BoundVerdict()
    events = event_log.read()
    if events is None:
        return _BoundVerdict(refusal=_bound_events_unreadable_text(lanes[0].lane_id))
    claim_base = _bound_claim_base(repo_root, window_base, coord_base_ref)
    if not resolves_commit(repo_root, claim_base):
        return _BoundVerdict(refusal=_bound_claim_base_unresolved_text(claim_base))
    stamp_anchors = approval_stamp_anchors(events, lanes, work_packages, excluded_canceled_wp_ids)
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix)
    refusals: list[BoundRefusal] = []
    tips: list[tuple[str, str]] = []
    for lane in lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        try:
            tip = resolve_commit(repo_root, branch)
        except GitProbeError:
            continue  # an unresolvable lane tip reads as an empty lane, as the collectors read it (:func:`_lane_tip_commits`)
        found = check_lane(
            repo_root,
            events=events,
            lane_id=lane.lane_id,
            branch=branch,
            approved_wp_ids=_bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids),
            claim_base=claim_base,
            anchors=[*_closed_world_anchors(lanes_manifest, lane, window_base, excluded_canceled_wp_ids=excluded_canceled_wp_ids), *stamp_anchors],
            is_bookkeeping=is_bookkeeping,
            tip=tip,
        )
        if found is not None:
            refusals.append(found)
        tips.append((branch, tip))
    if refusals:
        return _BoundVerdict(refusal=render_refusals(refusals, lanes_manifest.mission_slug))
    return _BoundVerdict(lane_tips=tuple(tips))


def approved_bound_refusal(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    coord_base_ref: str,
    excluded_canceled_wp_ids: Iterable[str] = (),
    excluded_window_base: str | None = None,
    event_log: _ClaimEventLog | None = None,
) -> str | None:
    """Refusal text when a code lane holds content beyond what review approved, else ``None`` (#5668).

    The claim builder's approved-bound check as a public entry point for the one other
    caller, ``orchestrator-api consolidate-mission`` (``consolidate`` runs the same check
    inside :func:`build_approved_wp_set`, on a fresh run and on ``--resume``): the Lamport
    snapshot gives membership exactly as :func:`build_approved_wp_set` reads it, the
    status events come from *event_log* (one read per claim; a caller that passes none
    gets its own), and the refusal codes are rendered by
    :func:`~specify_cli.consolidation.approved_bound.render_refusals`. A snapshot
    that cannot be materialized raises, as it does for the claim builder's own caller.
    """
    from specify_cli.status import materialize_snapshot

    snapshot = materialize_snapshot(feature_dir)
    verdict = _approved_bound_verdict(
        repo_root,
        lanes_manifest,
        snapshot.work_packages or {},
        frozenset(excluded_canceled_wp_ids),
        coord_base_ref=coord_base_ref,
        window_base=excluded_window_base,
        planning_prefix=_planning_prefix(repo_root, feature_dir),
        event_log=event_log or _ClaimEventLog(feature_dir),
    )
    return verdict.refusal


def lane_tips_moved_refusal(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    *,
    validated_tips: Mapping[str, str],
    anchor_shas: Sequence[str],
    planning_prefix: str | None,
    approved_wp_ids: Mapping[str, Sequence[str]] | None = None,
) -> str | None:
    """Refusal text when content arrived on a lane after the claim-time check validated it, else ``None`` (#5668).

    For each lane branch in *validated_tips* that still exists: the commits reachable from
    the live tip and from none of the lane's own validated tip, any other lane's validated
    tip or any of *anchor_shas*, less merge commits and bookkeeping-only commits. Reads no
    status events: the stamps were checked at claim time and this asks only whether
    content arrived since. Every reference it excludes is a SHA captured before the run
    mutated anything, never a live branch name: at gate time the live mission branch
    already reaches every merged lane commit and would exempt the commit this exists to
    find. A lane is named with its manifest work packages, or with *approved_wp_ids*
    (lane id -> approved work package ids) for the lanes it lists, so the recovery
    command never names a canceled work package.
    """
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix)
    refusals: list[BoundRefusal] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda candidate: candidate.lane_id):
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        validated = validated_tips.get(branch)
        if validated is None or not branch_exists(repo_root, branch):
            continue
        others = [sha for other, sha in validated_tips.items() if other != branch]
        beyond = commits_beyond(repo_root, branch, [validated, *others, *anchor_shas])
        content = content_commits(repo_root, beyond, is_bookkeeping)
        if content:
            refusals.append(
                BoundRefusal(
                    BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
                    lane.lane_id,
                    branch,
                    tuple(sorted((approved_wp_ids or {}).get(lane.lane_id) or lane.wp_ids)),
                    commits=tuple(sha for sha, _path in content),
                    path=content[0][1],
                )
            )
    return render_refusals(refusals, lanes_manifest.mission_slug) if refusals else None


def _dependency_lane_ids(lanes_manifest: LanesManifest, lane: ExecutionLane) -> list[str]:
    """Every lane *lane* depends on, transitively (``lanes.json`` ``depends_on_lanes``)."""
    by_id = {candidate.lane_id: candidate for candidate in lanes_manifest.lanes}
    seen: list[str] = []
    pending = list(lane.depends_on_lanes)
    while pending:
        lane_id = pending.pop()
        if lane_id in seen or lane_id not in by_id:
            continue
        seen.append(lane_id)
        pending.extend(by_id[lane_id].depends_on_lanes)
    return sorted(seen)


def _closed_world_anchors(
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    target_base: str | None,
    *,
    excluded_canceled_wp_ids: frozenset[str],
) -> list[str]:
    """FR-013 anchors for *lane*: dependency-lane tips (the allocator merges them in
    without ``--no-ff``, also on its reuse path after work began) and the target's
    pre-consolidation tip (commits already on the target ship nothing new).

    A FULLY-canceled dependency lane is not an anchor (#5569): its tip carries
    canceled content, which must never be exempt as history that predates *lane*.
    Its commits before its own base are still covered by the anchors that reach
    them (the approved dependencies it was cut from, the target tip).

    A PLANNING dependency lane is not an anchor either: its branch name is the LIVE
    target branch, which on a ``--resume`` after the interrupted run advanced the target
    already reaches every merged lane commit and would exempt a late one. What a planning
    lane legitimately contributes is on the target's pre-consolidation tip, *target_base*.
    """
    by_id = {candidate.lane_id: candidate for candidate in lanes_manifest.lanes}
    anchors = [
        _lane_branch_for(lanes_manifest, dep)
        for dep in _dependency_lane_ids(lanes_manifest, lane)
        if not is_planning_lane(by_id[dep]) and not lane_fully_canceled(by_id[dep], excluded_canceled_wp_ids)
    ]
    if target_base:
        anchors.append(target_base)
    return anchors


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
    :func:`_lane_tip_commits` documents) — but only because
    :func:`_unreadable_canceled_dependency_lanes` has already refused the claim
    when a live lane depends on that lane; call this only after that check.
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


def _carried_dependency_content(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    carriers: Mapping[str, list[str]],
    canceled: frozenset[str],
) -> tuple[frozenset[str], frozenset[CanceledDependencyContent]]:
    """``(superseded commits, carried content)`` over every carrier lane's spine (#5613).

    A canceled commit counts as superseded only when it is superseded on EVERY
    carrier that holds it; then it stays in that lane's authorship (its content is
    not the lane's final state) and consolidation is not refused for it. A carrier
    whose spine cannot be read supersedes nothing and names nothing: every canceled
    commit on it stays subtracted, the stricter verdict.
    """
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=query.lanes_manifest.mission_slug, planning_prefix=query.planning_prefix)
    lane_of = {sha: lane_id for lane_id, own in own_by_lane.items() for sha in own}
    wps_of = {lane.lane_id: tuple(sorted(lane.wp_ids)) for lane in query.lanes_manifest.lanes}
    superseded: set[str] = set()
    live_commits: set[str] = set()
    content: set[CanceledDependencyContent] = set()
    for carrier_id, spine in carriers.items():
        on_spine = canceled.intersection(spine)
        try:
            lane_superseded, live = canceled_spine_content(query.repo_root, spine, canceled, is_bookkeeping)
        except GitProbeError:
            live_commits |= on_spine
            continue
        superseded |= lane_superseded
        live_commits |= on_spine - lane_superseded
        for path, (sha, state) in live.items():
            content.add(CanceledDependencyContent(wps_of[lane_of[sha]], lane_of[sha], carrier_id, path, state))
    return frozenset(superseded - live_commits), frozenset(content)


def _resolve_canceled_dependency_lanes(query: _CanceledLaneQuery, event_log: _ClaimEventLog | None = None) -> _CanceledDependencyResolution:
    """Resolve the fully-canceled lanes whose commits an approved lane carries (#5569, #5613).

    The base is :func:`_fully_canceled_lane_commits`: every such lane's own commits
    leave the approved claim. Three refinements, none of which runs (and no event
    log is read) for a mission where no approved lane carries such a commit:

    * a canceled WP without ``lane_head`` stamps REFUSEs with the override named,
      until the operator attests it (:func:`_unstamped_carried_refusal`). The
      attestation lifts that refusal only;
    * a canceled commit a later approved commit fully superseded on every carrier
      stays in the claim, so a superseded canceled dependency consolidates --
      whether its WP is stamped, or unstamped and attested;
    * the remaining live content is recorded so the verifier can name it with
      ``CANCELED_REACHABLE_VIA_DEPENDENCY``. It is computed over ALL of the lanes'
      own commits, attested or not: content that would ship always FAILs.
    """
    own_by_lane = _fully_canceled_lane_own_commits(query.repo_root, query.lanes_manifest, query.excluded_ids, query.coord_base_ref, query.target_base)
    own = frozenset().union(*own_by_lane.values())
    carriers = _carrier_spines(query, own) if own else {}
    if not carriers:
        return _CanceledDependencyResolution(unapproved_commits=own)
    refusal = _unstamped_carried_refusal(query, own_by_lane, carriers, event_log or _ClaimEventLog(query.feature_dir))
    if refusal is not None:
        return _CanceledDependencyResolution(refusal=refusal)
    superseded, content = _carried_dependency_content(query, own_by_lane, carriers, own)
    return _CanceledDependencyResolution(unapproved_commits=own - superseded, content=content)


def _unreadable_canceled_dependency_lanes(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
) -> list[tuple[str, str]]:
    """``(lane_id, branch)`` of every fully-canceled lane a live lane depends on whose tip is unreadable (#5569).

    :func:`_fully_canceled_lane_commits` tolerates a canceled lane whose branch is gone
    (or whose range git cannot read) and yields nothing for it. That is only safe while
    nobody inherited the lane's commits: the allocator fast-forwards a dependency lane
    into its dependent, so the canceled commits sit on the dependent lane's first-parent
    spine, and an empty set for the canceled lane leaves nothing to subtract — the
    canceled content would be attributed as approved authorship and ship. For such a
    dependency lane the unreadable tip must therefore refuse. A canceled lane nobody
    depends on stays tolerated (its commits are on no live lane's spine).
    """
    live_dependencies = {
        dep
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane) and not lane_fully_canceled(lane, excluded_canceled_wp_ids)
        for dep in _dependency_lane_ids(lanes_manifest, lane)
    }
    unreadable: list[tuple[str, str]] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda candidate: candidate.lane_id):
        if lane.lane_id not in live_dependencies or is_planning_lane(lane) or not lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        if not branch_exists(repo_root, branch):
            unreadable.append((lane.lane_id, branch))
            continue
        try:
            commits_in_range(repo_root, coord_base_ref, branch)
        except GitProbeError:
            unreadable.append((lane.lane_id, branch))
    return unreadable


def _unreadable_canceled_dependency_refusal_text(unreadable: list[tuple[str, str]]) -> str:
    """The #5569 fail-closed refusal for a canceled dependency lane whose tip cannot be read."""
    return "; ".join(
        f"fully-canceled lane {lane_id} (branch '{branch}') is a dependency of a live lane but its commits cannot be read "
        "(the branch is missing or its history is unreadable): its canceled content, which the dependent lane inherited, "
        f"cannot be told apart from approved work. Recovery: restore '{branch}' (for example "
        f"`git branch {branch} refs/spec-kitty/lane-tip/{branch}` when a lane-tip ref was recorded, or from `git reflog`), "
        "then re-run `spec-kitty consolidate`; if the branch was rebuilt, run `spec-kitty consolidate --abort` before re-running"
        for lane_id, branch in unreadable
    )


def claim_integrity_refusal(claim: ApprovedWpCommitSet) -> str | None:
    """Strategy-independent claim-integrity refusal (``verify()`` steps 1-3), or ``None``.

    #5338: the single claim-integrity authority for CLAIM time (acted on in
    ``_capture_reconciliation_claim`` before any mutation). It covers exactly the
    three strategy-independent checks: an explicit ``claim.refusal``, an
    unresolved coordination surface, and a claim that is empty while the manifest
    lists WPs. The squash "empty authored-blob set" REFUSE and every other
    content check stay gate-time (they need the post-merge target).

    ``MergeOutcomeVerifier.verify`` calls this same predicate for its steps 1-3,
    so claim time and gate time cannot drift.
    """
    reason = MergeOutcomeVerifier._refusal_reason(claim)
    if reason is not None:
        return reason
    if claim.is_vacuous_against_manifest:
        return f"derived claim is empty while the manifest lists {len(claim.manifest_wp_ids)} WP(s)"
    return None


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


def _planning_prefix(repo_root: Path, feature_dir: Path) -> str | None:
    """Repo-relative posix path of the mission planning dir (``kitty-specs/<slug>``).

    Returns ``None`` when *feature_dir* is not under *repo_root* — the closed-world
    content check then falls back to the toolchain-churn denylist alone.
    """
    try:
        relative = feature_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    return relative.as_posix()


def _lane_branch_for(lanes_manifest: LanesManifest, lane_id: str) -> str:
    """Resolve a lane's **created** branch name from the creation input (slug + lane id).

    Thin alias over the shared :func:`~specify_cli.lanes.compute.lane_created_branch`
    (single canonical home — see its docstring for the I-1/I-3 rationale this
    module and ``merge.executor`` previously duplicated under different names).
    """
    # Local annotation re-narrows to ``str``: the narrow-file mypy override
    # (``specify_cli.*`` follow_imports = "skip") erases the callee's own
    # ``-> str`` to ``Any`` here (same pattern as executor.py's
    # ``_created_lane_branch`` re-wrap it replaces).
    branch: str = lane_created_branch(lanes_manifest, lane_id)
    return branch


def _lane_tip_commits(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """Commits on a lane tip, TOLERATING an unresolvable range at claim-build time.

    Claim building has always tolerated a lane branch (or coord base) that does not
    resolve — a fully-canceled lane has no branch, and some topologies cut the
    branch after this read — yielding no commits for that lane rather than aborting
    the whole merge. The #5001 FOLD-3 fail-closed window-error signal
    (:class:`GitProbeError`) is scoped to the VERIFIER's window scan
    (:meth:`MergeOutcomeVerifier._reachable_excluded` /
    ``_unattributable_content``), where an unevaluable window must refuse; the claim
    BUILDER keeps its pre-existing tolerant behavior here so a legitimate merge
    (e.g. a canceled-lane survivor merge) is never turned into a spurious refusal.
    """
    try:
        commits: list[str] = commits_in_range(repo_root, coord_base_ref, branch)
    except GitProbeError:
        return []
    return commits


def _collect_approved_shas(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Approved WPs → their lane-tip commit SHAs (Lamport membership + git tips)."""
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


def _lane_is_approved(lane: object, work_packages: Mapping[str, Mapping[str, object]]) -> bool:
    """True when at least one of *lane*'s WPs is in an approved membership lane."""
    wp_ids = getattr(lane, "wp_ids", ())
    return any(str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES for wp in wp_ids)


def _lane_first_parent_spine(repo_root: Path, coord_base_ref: str, branch: str) -> list[str]:
    """First-parent SHAs (newest-first) for a lane, TOLERATING an unresolvable range.

    Mirrors :func:`_lane_tip_commits`' claim-build tolerance: an unresolvable lane
    branch / coord base (a fully-canceled lane has no branch; some topologies cut it
    after this read) yields no authorship rather than turning a legitimate merge into
    a spurious refusal. The #5013 F7 fail-closed ``GitProbeError`` signal is scoped to
    the VERIFIER's window scan, not the claim BUILDER.
    """
    try:
        spine: list[str] = first_parent_commits_in_range(repo_root, coord_base_ref, branch)
        return spine
    except GitProbeError:
        return []


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
class _LaneWalk:
    """One lane's authorship walk: its range base and branch, first-parent spine and FINAL blobs / deletions."""

    base: str
    branch: str
    spine: list[str]
    blobs: set[tuple[str, str]]
    deletions: set[str]


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
    return _PresenceScope(base=base, carried=carried, lane_bases=lane_bases, canceled=canceled)


def _commits_before(repo_root: Path, base: str, lane_base: str | None) -> frozenset[str] | None:
    """The commits after *base* that *lane_base* reaches (they predate the lane's own work), or ``None`` when unknown."""
    if lane_base is None:
        return None
    try:
        return frozenset(commits_in_range(repo_root, base, lane_base))
    except GitProbeError:
        return None


def _presence_spine(repo_root: Path, presence: _PresenceScope, lane_id: str, branch: str) -> list[str] | None:
    """*lane*'s presence spine: ``base..lane`` first-parent, less what the mission branch carried from before the lane's own base.

    A commit the mission branch carries is the lane's own only when the lane's own
    base does not reach it: the lane authored it after its first governed claim and
    an earlier attempt merged it (#5788). A mission-branch commit made outside every
    lane before the lane was cut is reached by that base and is never the lane's
    content (M1). With no readable lane base every carried commit is dropped, the
    pre-#5788 reading. ``None`` when the mission-branch range cannot be read: the
    caller keeps the authorship walk.
    """
    if presence.carried is None:
        return None
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
    spine = _presence_spine(repo_root, presence, lane.lane_id, walk.branch) if presence is not None else None
    if spine is None or presence is None:
        return _lane_content(repo_root, lanes_manifest, lane, work_packages, walk.spine, walk.blobs, walk.deletions)
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
        authored = [sha for sha in first_parent if sha not in canceled_lane_commits]
        for sha in authored:
            shas.add(sha)
            pid = patch_id_of(repo_root, sha)
            if pid:
                patch_ids.add(pid)
        lane_blobs, lane_deletions = _final_authored_walk(repo_root, authored)
        blobs |= lane_blobs
        deletions |= lane_deletions
        _record_lane_path_contribution(path_contributions, lane, lane_blobs, authored)
        if not is_planning_lane(lane):
            lane_contents.append(
                _presence_lane_content(
                    repo_root,
                    lanes_manifest,
                    lane,
                    work_packages,
                    _LaneWalk(base, branch, first_parent, lane_blobs, lane_deletions),
                    presence,
                    canceled_lane_commits,
                )
            )
    multi_lane_paths = {path: (contributions[0], contributions[1]) for path, contributions in path_contributions.items() if len(contributions) == 2}
    return _AuthoredClaim(frozenset(shas), frozenset(patch_ids), frozenset(blobs), frozenset(deletions), multi_lane_paths, _order_lane_content(lane_contents))


__all__ = [
    "ApprovedWpCommitSet",
    "Divergence",
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
