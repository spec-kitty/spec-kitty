"""The single consolidation rollback authority (#5318 / #5332).

One pre-mutation snapshot (short branch name -> sha) is captured ONCE, and one
compare-and-swap ref restore undoes an attempt's mutation. Operator decision
DM ``01M3PD3VP1YTQ4D17HT96JA0T2``: CAS ref restore, not ``git revert`` -- a
forward revert leaves lane tips ancestors of the mission/coordination branch,
so the next run's first-parent authored range stays empty and #5318 persists.

Guarantees (``contracts/rollback-authority.md``):

1. A branch that is not in ``state.pre_mutation_refs`` is never moved.
2. A branch whose live tip is not this attempt's recorded post-mutation tip is
   never moved (reported ``NOT_RESTORED``); a branch with no recorded post tip
   is ``UNCHANGED_BY_RUN`` (never restored, never blocks a full restore). Each
   branch is restored to its per-attempt restore target (:func:`begin_attempt`).
3. A landing verified by an EARLIER reconciliation
   (``reconciliation_passed_target_sha`` == live target tip) is never rolled
   back (FR-011); neither is anything when a snapshotted branch no longer
   exists (a possibly completed landing) -- reported on its own line.
4. Every worktree with a restored branch checked out is resynced, and refuses
   (``NOT_RESTORED``) when dirty -- via ``git.ref_advance``; no raw
   ``reset --hard`` lives here.
5. Bookkeeping is cleared only after a full restore; a second call is
   idempotent (``ALREADY_AT_SNAPSHOT`` everywhere).

This module takes primitives (repo root, ``ConsolidationState``, manifest) --
not the executor's run state -- so ``--abort`` can call it with only the
persisted record.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from specify_cli.consolidation.state import ConsolidationState, reconciliation_passed_for_tip, save_state
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefAdvanceError,
    RefRestoreError,
    restore_branch_ref,
)
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import LanesManifest

# Only the entry points other modules call. The report/outcome types and
# ``snapshot_branches`` stay public (tests and typed callers import them by name)
# but are implementation surface of these entry points, not a separate export.
__all__ = [
    "begin_attempt",
    "capture_pre_mutation_snapshot",
    "missing_snapshot_branches",
    "record_post_mutation_tips",
    "rollback_to_snapshot",
]

_SHORT = 7
_NO_SNAPSHOT_REASON = "no pre-mutation snapshot recorded (pre-fix record)"
_MOVED_BY_OTHER_REASON = "moved by another actor since this run"


class BranchOutcomeKind(StrEnum):
    """What the authority did (or declined to do) for one snapshotted branch."""

    RESTORED = "restored"
    ALREADY_AT_SNAPSHOT = "already_at_snapshot"
    UNCHANGED_BY_RUN = "unchanged_by_run"
    NOT_RESTORED = "not_restored"


@dataclass(frozen=True)
class BranchOutcome:
    """Per-branch rollback result."""

    branch: str
    kind: BranchOutcomeKind
    snapshot_sha: str
    observed_sha: str
    expected_sha: str | None = None
    reason: str | None = None
    # For RESTORED only: the commit the branch was moved to. It is the snapshot
    # unless someone else moved the branch between attempts (``begin_attempt``).
    restored_to_sha: str | None = None


_OK_KINDS = frozenset({BranchOutcomeKind.RESTORED, BranchOutcomeKind.ALREADY_AT_SNAPSHOT, BranchOutcomeKind.UNCHANGED_BY_RUN})


@dataclass(frozen=True)
class RollbackReport:
    """Aggregate rollback result; :meth:`render` is the ONLY source of rollback text (FR-009)."""

    outcomes: tuple[BranchOutcome, ...] = ()
    refused_verified_landing: bool = False
    reason: str | None = None

    @property
    def fully_restored(self) -> bool:
        """True when nothing was refused and every branch is restored or legitimately untouched."""
        return not self.refused_verified_landing and self.reason is None and all(o.kind in _OK_KINDS for o in self.outcomes)

    @property
    def advanced_branches(self) -> tuple[str, ...]:
        """Branches left advanced past their snapshot because they could not be restored."""
        return tuple(o.branch for o in self.outcomes if o.kind is BranchOutcomeKind.NOT_RESTORED)

    def render(self) -> str:
        """Operator-facing rollback text (never claims nothing was mutated)."""
        if self.refused_verified_landing:
            return f"Kept the landing verified by an earlier reconciliation; nothing was rolled back. {self.reason or ''}".rstrip()
        if self.reason is not None and not self.outcomes:
            return f"Nothing was rolled back: {self.reason}."
        lines = ["Rollback to the pre-consolidation snapshot:"]
        width = max((len(o.branch) for o in self.outcomes), default=0)
        lines.extend(_render_outcome(o, width) for o in self.outcomes)
        return "\n".join(lines)


def _short(sha: str | None) -> str:
    return (sha or "")[:_SHORT]


def _render_outcome(outcome: BranchOutcome, width: int) -> str:
    name = outcome.branch.ljust(width)
    kind = outcome.kind
    if kind is BranchOutcomeKind.RESTORED:
        return f"  restored   {name}  {_short(outcome.observed_sha)} -> {_short(outcome.restored_to_sha or outcome.snapshot_sha)}"
    if kind is BranchOutcomeKind.ALREADY_AT_SNAPSHOT:
        return f"  unchanged  {name}  (already at {_short(outcome.observed_sha)})"
    if kind is BranchOutcomeKind.UNCHANGED_BY_RUN:
        return f"  kept       {name}  (not moved by this run; at {_short(outcome.observed_sha)})"
    detail = f"observed {_short(outcome.observed_sha)}"
    if outcome.expected_sha:
        detail += f", expected {_short(outcome.expected_sha)}"
    return f"  NOT restored {name}  {detail} -- {outcome.reason or 'unknown'}"


# --------------------------------------------------------------------------- git


def _live_tip(repo_root: Path, branch: str) -> str | None:
    """Commit at ``refs/heads/<branch>`` or ``None`` when it does not resolve."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


# ---------------------------------------------------------------------- snapshot


def _candidate_branches(lanes_manifest: LanesManifest, coord_ref: str | None) -> list[str]:
    """Deduped short branch names in a stable order (target, mission, coord, every lane)."""
    ordered: list[str] = [lanes_manifest.target_branch, lanes_manifest.mission_branch]
    if coord_ref is not None:
        ordered.append(coord_ref)
    # ``lane-planning`` resolves to the target branch (deduped below).
    ordered.extend(lane_created_branch(lanes_manifest, lane.lane_id) for lane in lanes_manifest.lanes)
    return list(dict.fromkeys(b for b in ordered if b))


def snapshot_branches(repo_root: Path, lanes_manifest: LanesManifest, *, coord_ref: str | None) -> dict[str, str]:
    """Live tips of every branch a consolidation may move; unresolvable ones are skipped."""
    refs: dict[str, str] = {}
    for branch in _candidate_branches(lanes_manifest, coord_ref):
        tip = _live_tip(repo_root, branch)
        if tip is not None:
            refs[branch] = tip
    return refs


def missing_snapshot_branches(repo_root: Path, lanes_manifest: LanesManifest, *, coord_ref: str | None) -> list[str]:
    """Candidate branches that do not resolve (not snapshotted; the caller may warn)."""
    return [b for b in _candidate_branches(lanes_manifest, coord_ref) if _live_tip(repo_root, b) is None]


def capture_pre_mutation_snapshot(
    repo_root: Path,
    state: ConsolidationState,
    lanes_manifest: LanesManifest,
    *,
    coord_ref: str | None,
) -> dict[str, str]:
    """Capture (and persist) the pre-mutation snapshot ONCE; never recapture.

    The legacy anchors the executor persisted earlier
    (``pre_mutation_target_sha`` / ``pre_mutation_coord_sha``) seed the
    target/coord entries so a resume of an older record snapshots the true
    pre-run tips; this function is the single writer of ``pre_mutation_refs``.
    """
    if state.pre_mutation_refs:
        return dict(state.pre_mutation_refs)
    refs = snapshot_branches(repo_root, lanes_manifest, coord_ref=coord_ref)
    if state.pre_mutation_target_sha:
        refs[lanes_manifest.target_branch] = state.pre_mutation_target_sha
    if coord_ref is not None and state.pre_mutation_coord_sha and state.pre_mutation_coord_ref in (None, coord_ref):
        refs[coord_ref] = state.pre_mutation_coord_sha
    state.pre_mutation_refs = refs
    save_state(state, repo_root)
    return dict(refs)


# ---------------------------------------------------------------- attempt bookkeeping


def _restore_target(snapshot: str, previous_post: str | None, attempt_start: str) -> str:
    """Per-attempt restore commit: the snapshot, unless someone else moved the branch."""
    return snapshot if attempt_start in {snapshot, previous_post} else attempt_start


def begin_attempt(repo_root: Path, state: ConsolidationState) -> None:
    """Fix this attempt's per-branch restore targets and reset its post tips.

    Called at the end of every attempt's claim (fresh AND resume). An advance
    consolidation itself produced (live tip == snapshot or the previous
    attempt's post tip) is undone to the snapshot; a change someone else made
    between attempts (e.g. the operator fixing the carrier lane) is KEPT.
    """
    for branch, snapshot in state.pre_mutation_refs.items():
        live = _live_tip(repo_root, branch)
        if live is None:
            state.restore_targets.setdefault(branch, snapshot)
            continue
        state.restore_targets[branch] = _restore_target(snapshot, state.post_mutation_refs.get(branch), live)
    state.post_mutation_refs = {}
    save_state(state, repo_root)


def record_post_mutation_tips(repo_root: Path, state: ConsolidationState) -> None:
    """Persist the live tip of every snapshotted branch (the CAS expected values)."""
    post: dict[str, str] = {}
    for branch in state.pre_mutation_refs:
        live = _live_tip(repo_root, branch)
        if live is not None:
            post[branch] = live
    state.post_mutation_refs = post
    save_state(state, repo_root)


# -------------------------------------------------------------------------- rollback


def _refusal(state: ConsolidationState, repo_root: Path, target_branch: str) -> RollbackReport | None:
    """FR-011 guard: a verified landing, or a vanished snapshotted branch, is never rolled back."""
    live_target = _live_tip(repo_root, target_branch) or ""
    if reconciliation_passed_for_tip(state, live_target):
        return RollbackReport(
            refused_verified_landing=True,
            reason=f"target {target_branch} is at {_short(live_target)}, verified by an earlier reconciliation",
        )
    for branch in state.pre_mutation_refs:
        if _live_tip(repo_root, branch) is None:
            return RollbackReport(reason=f"snapshotted branch {branch!r} no longer exists")
    return None


def _restore_one(repo_root: Path, branch: str, snapshot: str, restore_to: str, live: str, expected: str) -> BranchOutcome:
    try:
        restore_branch_ref(
            repo_root,
            branch,
            restore_to,
            expected_current_sha=expected,
            resync_checkouts=True,
            is_residue=is_toolchain_generated_churn,
        )
    except (RefRestoreError, RefAdvanceDirtyWorktreeError, RefAdvanceError) as exc:
        return BranchOutcome(branch, BranchOutcomeKind.NOT_RESTORED, snapshot, live, expected, str(exc))
    return BranchOutcome(branch, BranchOutcomeKind.RESTORED, snapshot, live, expected, restored_to_sha=restore_to)


def _rollback_branch(repo_root: Path, state: ConsolidationState, branch: str, snapshot: str) -> BranchOutcome:
    live = _live_tip(repo_root, branch) or ""
    restore_to = state.restore_targets.get(branch, snapshot)
    post = state.post_mutation_refs.get(branch)
    if live == restore_to:
        return BranchOutcome(branch, BranchOutcomeKind.ALREADY_AT_SNAPSHOT, snapshot, live)
    if post is None:
        return BranchOutcome(branch, BranchOutcomeKind.UNCHANGED_BY_RUN, snapshot, live)
    if live != post:
        return BranchOutcome(branch, BranchOutcomeKind.NOT_RESTORED, snapshot, live, post, _MOVED_BY_OTHER_REASON)
    return _restore_one(repo_root, branch, snapshot, restore_to, live, post)


def _clear_bookkeeping(state: ConsolidationState, outcomes: Iterable[BranchOutcome]) -> None:
    """Reset per-attempt progress after a FULL restore; the snapshot and restore targets stay."""
    coord_ref = state.pre_mutation_coord_ref
    if any(o.branch == coord_ref and o.kind is BranchOutcomeKind.RESTORED for o in outcomes):
        state.pending_coord_reconcile = None
    state.mission_number_baked = False
    state.completed_wps = []
    state.reconciliation_passed_target_sha = None
    state.post_mutation_refs = {}


def rollback_to_snapshot(repo_root: Path, state: ConsolidationState, *, target_branch: str) -> RollbackReport:
    """Undo this attempt's mutation by CAS-restoring every snapshotted branch."""
    if not state.pre_mutation_refs:
        return RollbackReport(reason=_NO_SNAPSHOT_REASON)
    refused = _refusal(state, repo_root, target_branch)
    if refused is not None:
        return refused
    outcomes = tuple(_rollback_branch(repo_root, state, branch, snapshot) for branch, snapshot in state.pre_mutation_refs.items())
    report = RollbackReport(outcomes=outcomes)
    if report.fully_restored:
        _clear_bookkeeping(state, outcomes)
        save_state(state, repo_root)
    return report
