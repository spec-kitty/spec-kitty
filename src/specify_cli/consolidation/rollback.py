"""The single consolidation rollback authority (#5318 / #5332).

One pre-mutation snapshot (short branch name -> sha) is captured ONCE, and one
compare-and-swap ref restore undoes an attempt's mutation. Operator decision
DM ``01M3PD3VP1YTQ4D17HT96JA0T2``: CAS ref restore, not ``git revert`` -- a
forward revert leaves lane tips ancestors of the mission/coordination branch,
so the next run's first-parent authored range stays empty and #5318 persists.

Guarantees (``contracts/rollback-authority.md``; record-anchored since #5686):

1. A branch that is not in ``state.pre_mutation_refs`` is never moved.
2. Every restore target and every compare-and-swap expectation comes from the
   persisted record. A run-movable branch (target, mission, coordination) is
   restored only when its live tip is this run's *effective post tip*: the
   recorded post tip, or a tip a persisted advance intent proves this run wrote
   (:func:`note_advance_intent`; the chain's base must be the tip the record
   expected). Any other tip is ``NOT_RESTORED`` -- never restored and never
   reported untouched, so ``--abort`` keeps the record. Each branch is restored
   to its record restore target (:func:`begin_attempt`).
2a. Lane branches (``state.snapshot_lane_branches``) are REPORT-ONLY: consolidation
   never moves a lane branch, so a lane move is another actor's. Lanes are
   snapshotted for the report, never recorded, never restored
   (``UNCHANGED_BY_RUN`` / ``ALREADY_AT_SNAPSHOT``).
2b. A phase records a post tip only for a run-movable branch whose tip CHANGED
   during that phase AND whose tip at phase entry was the tip the record
   expected (:func:`movable_branch_tips` and :func:`expected_tips` at phase
   entry, :func:`phase_records_branch` applied by :func:`record_post_mutation_tips`
   at exit). A foreign commit landing on the target BETWEEN phases is therefore
   never attributed to this run, not even when the next phase commits on top of
   it (FR-011). Every branch that moved during the phase has its advance-intent
   chain cleared, whether it was recorded or rejected.
2c. The authority never adopts a live tip it cannot explain. :func:`begin_attempt`
   marks every run-movable branch *unsettled*; a restoring rollback outcome (or,
   for the target, a reconciliation PASS via :func:`settle_branch`) settles it.
   On an unsettled branch, a tip that is neither the restore target nor the
   effective post is *unexplained*: :func:`begin_attempt` returns it and changes
   nothing, and the caller refuses. Only a move on a SETTLED branch between
   attempts becomes the new restore target (ADR A2).
2d. An operator release (:func:`release_branch`) turns a would-be
   ``NOT_RESTORED`` branch still at the released SHA into ``KEPT_BY_OPERATOR``;
   a release never keeps a branch that would be restored or is already at its
   target.
3. A landing verified by an EARLIER reconciliation
   (``reconciliation_passed_target_sha`` == live target tip) is never rolled
   back (FR-011) -- reported on its own line. A snapshotted branch that no
   longer exists never blocks the rest (slice-10 F3): a missing lane branch is
   reported (``LANE_MISSING``, with a ``git branch <b> <sha>`` recreate hint); a
   missing target/mission/coordination branch is ``NOT_RESTORED`` with the same
   hint -- never recreated silently.
4. Every worktree with a restored branch checked out is resynced, and refuses
   (``NOT_RESTORED``) when dirty -- via ``git.ref_advance``; no raw
   ``reset --hard`` lives here.
5. Every rollback persists its settle/unsettle bookkeeping, and drops the PASS
   anchor whenever the target was RESTORED (even when another branch was not);
   per-attempt progress (and the intents, the unsettled set and the releases) is
   cleared only after a full restore; a second call is idempotent (``ALREADY_AT_SNAPSHOT`` everywhere).

Residuals (documented, not closed): a foreign commit that lands on a run-movable
branch INSIDE the same phase, after this run's own advance of that branch, is
indistinguishable from this run's own move at the phase exit and IS recorded, so
a later rollback restores over it. The window is one phase long and the forward
advances are compare-and-swap, so the foreign commit must land after our CAS and
before the phase's recorder. An in-span move made without an advance intent (a
plain commit) and killed before its recorder is unprovable: it is reported
``NOT_RESTORED`` and refused at the next attempt, never adopted.

This module takes primitives (repo root, ``ConsolidationState``, manifest) --
not the executor's run state -- so ``--abort`` can call it with only the
persisted record.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from specify_cli.consolidation.state import UNSETTLED_ALL, ConsolidationState, reconciliation_passed_for_tip, save_state
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefAdvanceError,
    RefRestoreError,
    restore_branch_ref,
    resync_checkouts_to_tip,
)
from specify_cli.lanes.compute import lane_created_branch
from specify_cli.lanes.models import LanesManifest

# Only the entry points other modules call. The report/outcome types and
# ``snapshot_branches`` stay public (tests and typed callers import them by name)
# but are implementation surface of these entry points, not a separate export.
__all__ = [
    "OwnMove",
    "begin_attempt",
    "branch_tips",
    "capture_pre_mutation_snapshot",
    "expected_tips",
    "missing_snapshot_branches",
    "movable_branch_tips",
    "note_advance_intent",
    "own_moves_across",
    "record_post_mutation_tips",
    "record_restore_target",
    "release_branch",
    "rollback_would_restore",
    "rollback_to_snapshot",
    "run_movable_branches",
    "settle_branch",
    "unexplained_branches",
]

_SHORT = 7
_NO_SNAPSHOT_REASON = "no pre-mutation snapshot recorded (pre-fix record)"
_MOVED_BY_OTHER_REASON = "moved by another actor since this run"
_SEEDED_NOTE = "snapshot taken when this record was resumed"
_SEEDED_HEADER = f"Rollback to the snapshot (pre-consolidation unless marked [{_SEEDED_NOTE}]):"
_SNAPSHOT_HEADER = "Rollback to the pre-consolidation snapshot:"
#: F5: at least one branch went to an ADR-A2 restore target, not its snapshot.
_RESTORE_TARGETS_HEADER = "Rollback, restored to the record's restore targets:"
_LANE_REPORT_ONLY_REASON = "lane branch: not moved by consolidation"
_UNRECORDED_MOVE_REASON = "moved since the snapshot but no post-mutation tip was recorded (interrupted phase?); inspect before re-running"
_KEPT_WARNING = "may contain this consolidation's unverified changes"
_ADOPTED_NOTE = "adopted interrupted advance"
_COORD_CHECKOUT_NOT_RESYNCED = "coordination checkout left as found (its status files may differ from the branch tip)"


class BranchOutcomeKind(StrEnum):
    """What the authority did (or declined to do) for one snapshotted branch."""

    RESTORED = "restored"
    ALREADY_AT_SNAPSHOT = "already_at_snapshot"
    UNCHANGED_BY_RUN = "unchanged_by_run"
    LANE_MISSING = "lane_missing"
    NOT_RESTORED = "not_restored"
    # An operator release (``--abort --release-branch``) kept a branch that would
    # otherwise be NOT_RESTORED at the released SHA. OK for the report, never a restore.
    KEPT_BY_OPERATOR = "kept_by_operator"


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
    # The snapshot entry was captured live when an older record was resumed (F8).
    resume_seeded: bool = False
    # For RESTORED only: the CAS expectation came from a persisted advance intent
    # (a kill-left advance of this run), not from a recorded post tip (FR-006).
    adopted_intent: bool = False


_OK_KINDS = frozenset(
    {
        BranchOutcomeKind.RESTORED,
        BranchOutcomeKind.ALREADY_AT_SNAPSHOT,
        BranchOutcomeKind.UNCHANGED_BY_RUN,
        BranchOutcomeKind.LANE_MISSING,
        BranchOutcomeKind.KEPT_BY_OPERATOR,
    }
)
#: Outcomes that settle a run-movable branch (FR-003).
_SETTLING_KINDS = frozenset({BranchOutcomeKind.RESTORED, BranchOutcomeKind.ALREADY_AT_SNAPSHOT, BranchOutcomeKind.KEPT_BY_OPERATOR})
#: #5638: a coordination branch the rollback did not move keeps its tip; its checkout must match it.
_COORD_KEPT_KINDS = frozenset({BranchOutcomeKind.NOT_RESTORED, BranchOutcomeKind.KEPT_BY_OPERATOR})


@dataclass(frozen=True)
class RollbackReport:
    """Aggregate rollback result; :meth:`render` is the ONLY source of rollback text (FR-009)."""

    outcomes: tuple[BranchOutcome, ...] = ()
    refused_verified_landing: bool = False
    reason: str | None = None
    # #5638: why the checkout of a coordination branch left in place could not be
    # brought back to that branch's tip (None when it was, or nothing needed it).
    coord_checkout_note: str | None = None

    @property
    def fully_restored(self) -> bool:
        """True when nothing was refused and every branch is restored or legitimately untouched."""
        return not self.refused_verified_landing and self.reason is None and all(o.kind in _OK_KINDS for o in self.outcomes)

    @property
    def advanced_branches(self) -> tuple[str, ...]:
        """Branches left advanced past their snapshot because they could not be restored."""
        return tuple(o.branch for o in self.outcomes if o.kind is BranchOutcomeKind.NOT_RESTORED)

    @property
    def restored_off_snapshot(self) -> bool:
        """True when some branch was restored to a record restore target that is not its snapshot (ADR A2)."""
        return any(o.kind is BranchOutcomeKind.RESTORED and o.restored_to_sha not in (None, o.snapshot_sha) for o in self.outcomes)

    def _header(self) -> str:
        if self.restored_off_snapshot:
            return _RESTORE_TARGETS_HEADER
        return _SEEDED_HEADER if any(o.resume_seeded for o in self.outcomes) else _SNAPSHOT_HEADER

    def render(self) -> str:
        """Operator-facing rollback text (never claims nothing was mutated)."""
        if self.refused_verified_landing:
            return f"Kept the landing verified by an earlier reconciliation; nothing was rolled back. {self.reason or ''}".rstrip()
        if self.reason is not None and not self.outcomes:
            return f"Nothing was rolled back: {self.reason}."
        lines = [self._header()]
        width = max((len(o.branch) for o in self.outcomes), default=0)
        lines.extend(_render_outcome(o, width) for o in self.outcomes)
        if self.coord_checkout_note:
            lines.append(f"  {_COORD_CHECKOUT_NOT_RESYNCED}: {self.coord_checkout_note}")
        return "\n".join(lines)


def _short(sha: str | None) -> str:
    return (sha or "")[:_SHORT]


def _render_outcome(outcome: BranchOutcome, width: int) -> str:
    line = _render_outcome_line(outcome, width)
    return f"{line} [{_SEEDED_NOTE}]" if outcome.resume_seeded else line


def _render_outcome_line(outcome: BranchOutcome, width: int) -> str:
    name = outcome.branch.ljust(width)
    kind = outcome.kind
    if kind is BranchOutcomeKind.RESTORED:
        line = f"  restored   {name}  {_short(outcome.observed_sha)} -> {_short(outcome.restored_to_sha or outcome.snapshot_sha)}"
        return f"{line} ({_ADOPTED_NOTE})" if outcome.adopted_intent else line
    if kind is BranchOutcomeKind.KEPT_BY_OPERATOR:
        return f"  kept       {name}  (released by operator: {outcome.reason or ''}; at {_short(outcome.observed_sha)}; {_KEPT_WARNING})"
    if kind is BranchOutcomeKind.ALREADY_AT_SNAPSHOT:
        return f"  unchanged  {name}  (already at {_short(outcome.observed_sha)})"
    if kind is BranchOutcomeKind.LANE_MISSING:
        return f"  missing    {name}  ({outcome.reason})"
    if kind is BranchOutcomeKind.UNCHANGED_BY_RUN:
        return f"  kept       {name}  ({outcome.reason or _LANE_REPORT_ONLY_REASON}; at {_short(outcome.observed_sha)})"
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


def _lane_branches(lanes_manifest: LanesManifest, coord_ref: str | None) -> list[str]:
    """Candidate branches that are LANE branches (never the target, mission or coordination branch)."""
    movable = {lanes_manifest.target_branch, lanes_manifest.mission_branch, coord_ref}
    return [b for b in _candidate_branches(lanes_manifest, coord_ref) if b not in movable]


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
    is_resume: bool = False,
) -> dict[str, str]:
    """Capture (and persist) the pre-mutation snapshot ONCE; never recapture.

    The legacy anchors the executor persisted earlier
    (``pre_mutation_target_sha`` / ``pre_mutation_coord_sha``) seed the
    target/coord entries so a resume of an older record snapshots the true
    pre-run tips; this function is the single writer of ``pre_mutation_refs``.
    On a resume (``is_resume``) every entry NOT seeded from those anchors was
    captured live, after the earlier attempt ran; it is listed in
    ``state.resume_seeded_refs`` so the report does not call it pre-consolidation.
    """
    if state.pre_mutation_refs:
        return dict(state.pre_mutation_refs)
    refs = snapshot_branches(repo_root, lanes_manifest, coord_ref=coord_ref)
    seeded: set[str] = set()
    if state.pre_mutation_target_sha:
        refs[lanes_manifest.target_branch] = state.pre_mutation_target_sha
        seeded.add(lanes_manifest.target_branch)
    if coord_ref is not None and state.pre_mutation_coord_sha and state.pre_mutation_coord_ref in (None, coord_ref):
        refs[coord_ref] = state.pre_mutation_coord_sha
        seeded.add(coord_ref)
    state.pre_mutation_refs = refs
    state.snapshot_lane_branches = [b for b in _lane_branches(lanes_manifest, coord_ref) if b in refs]
    state.resume_seeded_refs = [b for b in refs if b not in seeded] if is_resume else []
    save_state(state, repo_root)
    return dict(refs)


# ---------------------------------------------------------------- attempt bookkeeping


def run_movable_branches(state: ConsolidationState) -> list[str]:
    """Snapshotted branches this run can move (target, mission, coordination) -- never a lane branch."""
    lanes = set(state.snapshot_lane_branches)
    return [b for b in state.pre_mutation_refs if b not in lanes]


def _unsettled(state: ConsolidationState) -> set[str]:
    """The unsettled run-movable branches; the malformed-record sentinel expands to all of them."""
    if UNSETTLED_ALL in state.unsettled_refs:
        return set(run_movable_branches(state))
    return set(state.unsettled_refs)


def _set_unsettled(state: ConsolidationState, branches: set[str]) -> None:
    state.unsettled_refs = [b for b in run_movable_branches(state) if b in branches]


def _record_restore_target(state: ConsolidationState, branch: str) -> str:
    """The record's restore target: an earlier attempt's target, else the snapshot."""
    return state.restore_targets.get(branch, state.pre_mutation_refs[branch])


def record_restore_target(state: ConsolidationState, branch: str) -> str:
    """Public view of the record's restore target of ``branch`` (an earlier attempt's target, else the snapshot)."""
    return _record_restore_target(state, branch)


def rollback_would_restore(state: ConsolidationState, branch: str, live: str) -> bool:
    """True when :func:`rollback_to_snapshot` would restore ``branch`` from ``live`` or find it already at its restore target.

    The same predicate the rollback applies (:func:`_rollback_branch`): ``live`` is
    the restore target, or this run's effective post tip (the recorded post, or a
    tip a persisted advance intent proves this run wrote). Ignores a dirty
    checkout or a compare-and-swap race, which only a real restore can see.
    """
    return live in (_record_restore_target(state, branch), _effective_post(state, branch, live))


def _expected_tip(state: ConsolidationState, branch: str) -> str:
    """The tip the record expects the branch at: the recorded post tip, else the restore target."""
    post = state.post_mutation_refs.get(branch)
    return post if post is not None else _record_restore_target(state, branch)


def _effective_post(state: ConsolidationState, branch: str, live: str) -> str | None:
    """``live`` when a persisted intent chain based on the expected tip proves this run wrote it; else the recorded post."""
    chain = state.advance_intents.get(branch)
    if chain and chain[0] == _expected_tip(state, branch) and live in chain[1:]:
        return live
    return state.post_mutation_refs.get(branch)


def _classify(previous_target: str, effective_post: str | None, live: str, unsettled: bool) -> tuple[str, bool]:
    """Pure attempt-start classifier: ``(restore target, unexplained)`` for one run-movable branch.

    An explained tip (the restore target or this run's effective post) keeps the
    target. A move on a settled branch between attempts becomes the target (ADR
    A2). A move on an unsettled branch the record cannot explain keeps the
    target and is unexplained (FR-004).
    """
    if live in (previous_target, effective_post):
        return previous_target, False
    if not unsettled:
        return live, False
    return previous_target, True


@dataclass(frozen=True)
class _AttemptStart:
    """One snapshotted branch's classification at :func:`begin_attempt`."""

    live: str | None
    target: str
    post: str | None = None
    unexplained: bool = False


def _classify_live(state: ConsolidationState, branch: str, live: str, unsettled: bool) -> _AttemptStart:
    previous = _record_restore_target(state, branch)
    effective = _effective_post(state, branch, live)
    target, unexplained = _classify(previous, effective, live, unsettled)
    carried = live if not unexplained and live == effective else None
    return _AttemptStart(live, target, carried, unexplained)


def _classify_own_move(state: ConsolidationState, branch: str, origin: str, live: str, unsettled: bool) -> _AttemptStart:
    """A branch this process moved itself before the claim (heal, attestations), judged by its pre-move tip."""
    previous = _record_restore_target(state, branch)
    if origin == previous:
        return _AttemptStart(live, live)  # re-anchor: no run content under the own move
    if origin == _effective_post(state, branch, origin):
        return _AttemptStart(live, previous, live)  # keep the target; the run content stays restorable
    if not unsettled:
        return _AttemptStart(live, live)  # a settled branch's between-attempts move (ADR A2)
    return _AttemptStart(live, previous, unexplained=True)


@dataclass(frozen=True)
class OwnMove:
    """A run-movable branch this process moved itself before the claim: its tips immediately before and after those steps."""

    before: str
    after: str


def own_moves_across(
    own_moves: Mapping[str, OwnMove],
    before: Mapping[str, str | None],
    after: Mapping[str, str | None],
    *,
    writes: Iterable[str],
) -> dict[str, OwnMove]:
    """Fold one pre-claim step of this process into ``own_moves``: ``before`` / ``after`` are the tips around that step.

    Only the branches the step can write (``writes``: the status-surface branch
    for the operator attestations, the marker's coordination ref for the heal)
    are considered; a move on any other branch inside the window is never this
    process's. A branch counts as moved by the step only when its tip changed across it.
    A move that continues an earlier own move (the earlier ``after`` is this
    step's ``before``) keeps the earlier origin; any other move starts from this
    step's ``before`` (a move in between was not this process's).
    """
    merged = dict(own_moves)
    writable = set(writes)
    for branch, tip in after.items():
        if branch not in writable:
            continue
        start = before.get(branch)
        if tip is None or start is None or tip == start:
            continue
        prior = merged.get(branch)
        merged[branch] = OwnMove(prior.before if prior is not None and prior.after == start else start, tip)
    return merged


def _lane_attempt_start(state: ConsolidationState, branch: str, snapshot: str, live: str) -> _AttemptStart:
    """Lane branches keep the pre-#5686 rule: report-only, restore target for the report."""
    previous_post = state.post_mutation_refs.get(branch)
    target = snapshot if live in (snapshot, previous_post) else live
    return _AttemptStart(live, target, previous_post if live == previous_post else None)


def _attempt_starts(repo_root: Path, state: ConsolidationState, own_moves: Mapping[str, OwnMove]) -> dict[str, _AttemptStart]:
    unsettled = _unsettled(state)
    lanes = set(state.snapshot_lane_branches)
    starts: dict[str, _AttemptStart] = {}
    for branch, snapshot in state.pre_mutation_refs.items():
        live = _live_tip(repo_root, branch)
        own = own_moves.get(branch)
        if live is None:
            starts[branch] = _AttemptStart(None, state.restore_targets.get(branch, snapshot))
        elif branch in lanes:
            starts[branch] = _lane_attempt_start(state, branch, snapshot, live)
        elif own is not None and own.after == live:
            starts[branch] = _classify_own_move(state, branch, own.before, live, branch in unsettled)
        else:
            starts[branch] = _classify_live(state, branch, live, branch in unsettled)
    return starts


def unexplained_branches(repo_root: Path, state: ConsolidationState) -> list[tuple[str, str, str]]:
    """Read-only pre-check: ``(branch, restore target, live tip)`` of every unexplained run-movable branch.

    Uses the :func:`begin_attempt` classifier and mutates nothing (neither the
    record in memory nor on disk), so a caller can refuse before any step that
    could move a branch.
    """
    starts = _attempt_starts(repo_root, state, {})
    return [(b, s.target, s.live) for b, s in starts.items() if s.unexplained and s.live is not None]


def begin_attempt(repo_root: Path, state: ConsolidationState, *, own_moves: Mapping[str, OwnMove] | None = None) -> list[str]:
    """Open an attempt: fix every branch's restore target from the record; return the unexplained branches.

    Called at the end of every attempt's claim (fresh AND resume). A branch at
    its restore target or at this run's effective post tip keeps its target (and
    the post is carried, so a resumed attempt that re-moves nothing keeps its CAS
    expectation). A move between attempts on a SETTLED branch becomes the new
    restore target (ADR A2). A move on an UNSETTLED branch that the record cannot
    explain is returned: then NOTHING in the record changes and the caller
    refuses (``UNEXPLAINED_BRANCH_MOVE``). This function never raises for it.

    ``own_moves`` maps a branch to an :class:`OwnMove`: the tips immediately
    before and after this process's own pre-claim steps that moved it (the
    coord-strand heal, operator attestations; :func:`own_moves_across`). Only a
    branch whose claim-time tip still equals ``after`` is judged by ``before``:
    from its restore target it re-anchors; from this run's effective post it
    keeps the target and carries the live tip as the post (never laundering run
    content into the target); otherwise it is unexplained (on an unsettled
    branch). A branch that moved again since ``after`` (another actor) gets the
    ordinary classification.

    When every branch is explained: the restore targets and carried posts are
    written, every intent and release is cleared, every run-movable branch is
    marked unsettled, and the record is saved.
    """
    starts = _attempt_starts(repo_root, state, own_moves or {})
    unexplained = [b for b, s in starts.items() if s.unexplained]
    if unexplained:
        return unexplained
    state.restore_targets.update({b: s.target for b, s in starts.items()})
    state.post_mutation_refs = {b: s.post for b, s in starts.items() if s.post is not None}
    state.advance_intents = {}
    state.released_refs = {}
    state.release_reasons = {}
    state.unsettled_refs = run_movable_branches(state)
    save_state(state, repo_root)
    return []


def note_advance_intent(repo_root: Path, state: ConsolidationState, branch: str, old_sha: str, new_sha: str) -> None:
    """Persist, before a compare-and-swap advance, that this run is moving ``branch`` from ``old_sha`` to ``new_sha``.

    Only run-movable snapshotted branches are tracked. A new advance whose old
    SHA is the chain's last entry extends the chain; otherwise a new chain
    ``[old, new]`` starts. Fail closed: a save error propagates, so the caller
    never advances without a persisted intent.
    """
    if branch not in run_movable_branches(state):
        return
    chain = state.advance_intents.get(branch)
    state.advance_intents[branch] = [*chain, new_sha] if chain and chain[-1] == old_sha else [old_sha, new_sha]
    save_state(state, repo_root)


def clear_advance_intents(state: ConsolidationState, branches: Iterable[str]) -> None:
    """Drop the intent chains of ``branches`` (the caller saves the record)."""
    for branch in branches:
        state.advance_intents.pop(branch, None)


def release_branch(state: ConsolidationState, branch: str, live_sha: str, reason: str) -> None:
    """Record an operator release of ``branch`` at ``live_sha`` (the caller validates and saves)."""
    state.released_refs[branch] = live_sha
    state.release_reasons[branch] = reason


def settle_branch(repo_root: Path, state: ConsolidationState, branch: str) -> None:
    """Mark ``branch`` settled (e.g. the target after a reconciliation PASS) and save the record.

    The branch's intent chain is spent with it, like a settling rollback outcome
    (:func:`_settle_outcomes`): a stale chain must never adopt a later move.
    """
    unsettled = _unsettled(state)
    unsettled.discard(branch)
    _set_unsettled(state, unsettled)
    state.advance_intents.pop(branch, None)
    save_state(state, repo_root)


def branch_tips(repo_root: Path, branches: Iterable[str]) -> dict[str, str | None]:
    """Live tips of ``branches`` (``None`` for a branch that does not resolve)."""
    return {branch: _live_tip(repo_root, branch) for branch in branches}


def movable_branch_tips(repo_root: Path, state: ConsolidationState) -> dict[str, str | None]:
    """Live tips of the run-movable snapshotted branches (a phase's entry tips for :func:`record_post_mutation_tips`)."""
    return branch_tips(repo_root, run_movable_branches(state))


def expected_tips(state: ConsolidationState) -> dict[str, str]:
    """The tip the record expects each run-movable branch at: its recorded post tip, else its restore target."""
    return {branch: _expected_tip(state, branch) for branch in run_movable_branches(state)}


def phase_records_branch(entry: str | None, expected: str | None, live: str | None) -> bool:
    """FR-011: record ``live`` as this run's post tip only when it moved during the phase and the phase entered at ``expected``.

    A phase that entered at any other tip started on top of a move the record
    cannot explain (a foreign commit between phases), so its exit tip is never
    attributed to this run.
    """
    return live is not None and live != entry and entry == expected


def _phase_exit_tips(
    repo_root: Path,
    state: ConsolidationState,
    entry_tips: Mapping[str, str | None],
    expected: Mapping[str, str] | None,
) -> tuple[dict[str, str], list[str]]:
    """``(post tips to record, branches that moved during the phase)`` at a recorded phase's exit."""
    post: dict[str, str] = {}
    moved: list[str] = []
    for branch in run_movable_branches(state):
        live = _live_tip(repo_root, branch)
        entry = entry_tips.get(branch)
        if live == entry:
            continue
        moved.append(branch)
        if live is not None and (expected is None or phase_records_branch(entry, expected.get(branch), live)):
            post[branch] = live
    return post, moved


def record_post_mutation_tips(
    repo_root: Path,
    state: ConsolidationState,
    *,
    entry_tips: Mapping[str, str | None] | None = None,
    expected_tips: Mapping[str, str] | None = None,
) -> None:
    """Persist this run's post-mutation tips (the CAS expected values); never a lane branch.

    With ``entry_tips`` (the phase recorder), only a branch whose live tip differs
    from its tip at phase entry is (re)recorded; every other recorded tip is kept,
    and every branch that moved has its advance-intent chain cleared. With
    ``expected_tips`` too (the tips the record expected at phase entry), a moved
    branch is recorded only per :func:`phase_records_branch`. Without
    ``entry_tips``, every run-movable branch's live tip is recorded afresh.
    """
    if entry_tips is None:
        state.post_mutation_refs = {b: live for b in run_movable_branches(state) if (live := _live_tip(repo_root, b)) is not None}
    else:
        recorded, moved = _phase_exit_tips(repo_root, state, entry_tips, expected_tips)
        state.post_mutation_refs = {**state.post_mutation_refs, **recorded}
        clear_advance_intents(state, moved)
    save_state(state, repo_root)


# -------------------------------------------------------------------------- rollback


def _refusal(state: ConsolidationState, repo_root: Path, target_branch: str) -> RollbackReport | None:
    """FR-011 guard: a landing verified by an earlier reconciliation is never rolled back."""
    live_target = _live_tip(repo_root, target_branch) or ""
    if reconciliation_passed_for_tip(state, live_target):
        return RollbackReport(
            refused_verified_landing=True,
            reason=f"target {target_branch} is at {_short(live_target)}, verified by an earlier reconciliation",
        )
    return None


def _missing_branch_outcome(state: ConsolidationState, branch: str, snapshot: str) -> BranchOutcome:
    """A snapshotted branch that no longer exists: report it with a recreate hint, never block the rest (F3)."""
    hint = f"no longer exists; snapshot {snapshot}; recreate with `git branch {branch} {snapshot}` if you still need it"
    if branch in state.snapshot_lane_branches:
        return BranchOutcome(branch, BranchOutcomeKind.LANE_MISSING, snapshot, "", reason=f"lane branch {branch} {hint}")
    return BranchOutcome(branch, BranchOutcomeKind.NOT_RESTORED, snapshot, "", reason=f"branch {branch} {hint}")


def _restore_one(repo_root: Path, branch: str, snapshot: str, restore_to: str, live: str, expected: str, *, adopted: bool) -> BranchOutcome:
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
    return BranchOutcome(branch, BranchOutcomeKind.RESTORED, snapshot, live, expected, restored_to_sha=restore_to, adopted_intent=adopted)


def _kept_if_released(state: ConsolidationState, refused: BranchOutcome) -> BranchOutcome:
    """A would-be NOT_RESTORED branch still at the SHA the operator released it at is KEPT_BY_OPERATOR (FR-008)."""
    if state.released_refs.get(refused.branch) != refused.observed_sha:
        return refused
    reason = state.release_reasons.get(refused.branch, "")
    return replace(refused, kind=BranchOutcomeKind.KEPT_BY_OPERATOR, expected_sha=None, reason=reason)


def _rollback_branch(repo_root: Path, state: ConsolidationState, branch: str, snapshot: str) -> BranchOutcome:
    live = _live_tip(repo_root, branch)
    if live is None:
        return _missing_branch_outcome(state, branch, snapshot)
    restore_to = state.restore_targets.get(branch, snapshot)
    if live == restore_to:
        return BranchOutcome(branch, BranchOutcomeKind.ALREADY_AT_SNAPSHOT, snapshot, live)
    if branch in state.snapshot_lane_branches:
        return BranchOutcome(branch, BranchOutcomeKind.UNCHANGED_BY_RUN, snapshot, live, reason=_LANE_REPORT_ONLY_REASON)
    post = _effective_post(state, branch, live)
    if not rollback_would_restore(state, branch, live) or post is None:  # ``post is None`` only narrows the type
        reason = _UNRECORDED_MOVE_REASON if post is None else _MOVED_BY_OTHER_REASON
        return _kept_if_released(state, BranchOutcome(branch, BranchOutcomeKind.NOT_RESTORED, snapshot, live, post, reason))
    adopted = post != state.post_mutation_refs.get(branch)
    return _restore_one(repo_root, branch, snapshot, restore_to, live, post, adopted=adopted)


def _settle_outcomes(state: ConsolidationState, outcomes: Iterable[BranchOutcome]) -> None:
    """FR-003: settle every restored / already-at-target / kept branch; keep every NOT_RESTORED one unsettled.

    A settled branch's intent chain is dropped too: its proof is spent, and a
    stale chain must never adopt a later move by another actor.
    """
    movable = set(run_movable_branches(state))
    unsettled = _unsettled(state)
    for outcome in outcomes:
        if outcome.branch not in movable:
            continue
        if outcome.kind in _SETTLING_KINDS:
            unsettled.discard(outcome.branch)
            state.advance_intents.pop(outcome.branch, None)
        elif outcome.kind is BranchOutcomeKind.NOT_RESTORED:
            unsettled.add(outcome.branch)
    _set_unsettled(state, unsettled)


def _clear_bookkeeping(state: ConsolidationState, outcomes: Iterable[BranchOutcome]) -> None:
    """Reset per-attempt progress after a FULL restore; the snapshot and restore targets stay."""
    coord_ref = state.pre_mutation_coord_ref
    if any(o.branch == coord_ref and o.kind is BranchOutcomeKind.RESTORED for o in outcomes):
        state.pending_coord_reconcile = None
    state.mission_number_baked = False
    state.completed_wps = []
    state.reconciliation_passed_target_sha = None
    state.post_mutation_refs = {}
    state.advance_intents = {}
    state.unsettled_refs = []
    state.released_refs = {}
    state.release_reasons = {}


def _resync_kept_coord_checkout(repo_root: Path, state: ConsolidationState, outcomes: Iterable[BranchOutcome]) -> str | None:
    """Bring the checkout of a coordination branch the rollback left in place back to its tip (#5638).

    The bookkeeping byte-restore writes the pre-``done`` status bytes into the
    coordination worktree. A RESTORED coordination branch is resynced by its
    restore; one left in place (NOT_RESTORED, or kept by the operator) still
    carries the committed ``done``, so its checkout would stay dirty against its
    own HEAD and every later status write would refuse. Only toolchain residue
    is discarded; any other change refuses the resync and the checkout is left
    as found. The committed strand stays, recorded by the reconcile marker.

    Residue is decided by ``is_toolchain_generated_churn``, which counts
    ``kitty-specs/*/status.events.jsonl`` and ``status.json`` as residue. An
    uncommitted status-log line in the checkout (for example from an interrupted
    write) is therefore reset with the rest. Those bytes were already overwritten
    by the rollback's own byte-restore, so no operator-authored work is lost, but
    the reset is silent. The predicate is deliberately unchanged.

    Returns the reason the checkout was left as found, or ``None``.
    """
    coord_ref = state.pre_mutation_coord_ref
    if not coord_ref or not any(o.branch == coord_ref and o.kind in _COORD_KEPT_KINDS and o.observed_sha for o in outcomes):
        return None
    try:
        resync_checkouts_to_tip(repo_root, coord_ref, is_residue=is_toolchain_generated_churn)
    except (RefAdvanceDirtyWorktreeError, RefAdvanceError) as exc:
        return str(exc)
    return None


def rollback_to_snapshot(repo_root: Path, state: ConsolidationState, *, target_branch: str) -> RollbackReport:
    """Undo this attempt's mutation by CAS-restoring every snapshotted branch; persist the settle bookkeeping."""
    if not state.pre_mutation_refs:
        return RollbackReport(reason=_NO_SNAPSHOT_REASON)
    refused = _refusal(state, repo_root, target_branch)
    if refused is not None:
        return refused
    seeded = set(state.resume_seeded_refs)
    outcomes = tuple(
        replace(outcome, resume_seeded=outcome.branch in seeded)
        for outcome in (_rollback_branch(repo_root, state, branch, snapshot) for branch, snapshot in state.pre_mutation_refs.items())
    )
    report = RollbackReport(outcomes=outcomes, coord_checkout_note=_resync_kept_coord_checkout(repo_root, state, outcomes))
    _settle_outcomes(state, outcomes)
    if any(o.branch == target_branch and o.kind is BranchOutcomeKind.RESTORED for o in outcomes):
        # F4: the target left the landing the PASS anchor verified; never keep a stale anchor.
        state.reconciliation_passed_target_sha = None
    if report.fully_restored:
        _clear_bookkeeping(state, outcomes)
    save_state(state, repo_root)
    return report
