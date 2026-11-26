"""One lane-cleanup module behind a remover port (S5, #7280, FR-030 to FR-035, FR-039a).

The consolidate executor (``phase_teardown``), ``orchestrator-api consolidate-mission`` and
``mission close --discard`` each used to carry their own lane teardown, and they disagreed on the
lane branch name (``lanes.compute.lane_created_branch`` against a caller-held handle passed to
``branch_naming.code_lane_branch_name``). They now share this module:

* :func:`plan_lane_cleanup` is pure: one :class:`LaneCleanupItem` per code lane, named from the
  manifest's recorded Mission slug through the one placement authority
  (``worktree_allocator.predict_lane_worktree``), never from a caller-held handle.
* :func:`apply` runs each item through a :class:`LaneRemover` and NEVER raises: a lane the remover
  cannot remove is ``kept`` with its code, remedy and the backstop command, a lane the retention
  policy keeps is ``retained_by_policy`` (FR-033, distinct from ``kept``), the rest are
  ``removed``. After a verified landing a kept lane is a report line, never a traceback (FR-032).
* :class:`MainTodayRemover` binds the port to today's guarded primitives exactly
  (``guarded_worktree_remove`` / ``guarded_branch_delete``; no new raw ``git worktree remove``,
  ``branch -D`` or ``--force``: C-004 and its recorded interim exception, DM
  ``01M6QY4B7P4T68TE7JE30FRJV6``). A lane-tip ref is cleared only after the branch delete is
  confirmed, so a branch that is already missing keeps its tip ref (FR-034). A removal backed by
  a landing proof needs a process proof first: where the probe is unavailable (off Linux) or a
  process stands in the worktree, the lane is kept (NFR-008).

The port is shaped so the S5 guard binding (WP16, after #7275) can bind
``guarded_landed_removal(LandedRemoval(worktree, branch, tip, remote, landing_ref))``: an item
carries the worktree, the branch and the claim-validated tip, and :data:`LandingProof` names the
landing (a local target at its PASS anchor, or a remote ref).
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from specify_cli.core.utils import safe_is_dir
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_WORKTREE_DIRTY,
    PROCESS_IN_WORKTREE,
    WORKTREE_TIP_MOVED,
    DestructiveOpRefused,
    LandedRemoval,
    guarded_branch_delete,
    guarded_landed_removal,
    guarded_worktree_remove,
)
from specify_cli.git.ref_advance import ResidueClassifier
from specify_cli.lanes import auto_rebase_record
from specify_cli.lanes.compute import is_repo_root_lane, lane_created_branch
from specify_cli.lanes.models import LanesManifest
from specify_cli.workspace.process_probe import ProcessProbeResult, processes_with_cwd_under

__all__ = [
    "LANE_CLEANUP_FAILED",
    "GuardedLaneRemover",
    "LaneCleanupOutcome",
    "LaneCleanupReport",
    "LaneRetention",
    "LocalTargetAtPass",
    "MainTodayRemover",
    "MissionBranchProjection",
    "apply",
    "branch_exists",
    "branch_tip",
    "cleanup_expected_tips",
    "kept_after_coordination_refusal",
    "mission_branch_projection",
    "own_auto_rebase_move",
    "plan_lane_cleanup",
    "projection_tips",
]

#: The backstop every kept lane names (contracts/consolidate-cleanup-report.md).
BACKSTOP_COMMAND = "spec-kitty doctor workspaces --prune"
#: Running processes cannot be checked on this platform (no ``/proc``).
PROCESS_PROOF_UNAVAILABLE = "PROCESS_PROOF_UNAVAILABLE"
#: Cleanup had no usable landing proof for the lane (#7325): it is kept, worktree and branch as they are.
_LANDING_PROOF_UNAVAILABLE = "LANDING_PROOF_UNAVAILABLE"
#: The remover itself failed unexpectedly; the lane is kept and nothing more is attempted.
LANE_CLEANUP_FAILED = "LANE_CLEANUP_FAILED"
#: ``git branch -D`` itself refused (for example the branch is checked out elsewhere).
BRANCH_DELETE_REFUSED_BY_GIT = "BRANCH_DELETE_REFUSED_BY_GIT"
_WORKTREE_REMOVE_REFUSED_BY_GIT = "WORKTREE_REMOVE_REFUSED_BY_GIT"


class LaneCleanupOutcome(StrEnum):
    REMOVED = "removed"
    KEPT = "kept"  # the remover could not prove removal safe
    RETAINED_BY_POLICY = "retained_by_policy"


@dataclass(frozen=True)
class LaneCleanupItem:
    """One code lane to clean up.

    ``worktree`` / ``branch`` are ``None`` when that leg is not to be run (retained by policy, or
    a lane with no worktree of its own). ``expected_tip`` is the claim-validated lane tip.
    """

    lane_id: str
    worktree: Path | None
    branch: str | None
    expected_tip: str | None = None


@dataclass(frozen=True)
class LaneCleanupResult:
    item: LaneCleanupItem
    outcome: LaneCleanupOutcome
    code: str | None = None  # guard code when KEPT
    remedy: str | None = None
    command: str | None = None  # e.g. "spec-kitty doctor workspaces --prune"
    recreate: str | None = None  # e.g. "git branch <b> <sha>"
    detail: str | None = None  # e.g. the retention key that kept the lane
    recoverable: str | None = None  # the lane-tip ref kept for a lane removed on the Mission-branch proof

    def to_json(self, repo_root: Path | None = None) -> dict[str, str | None]:
        """The contract object (``contracts/consolidate-cleanup-report.md``)."""
        worktree = self.item.worktree
        if worktree is not None and repo_root is not None and worktree.is_relative_to(repo_root):
            worktree = worktree.relative_to(repo_root)
        return {
            "lane_id": self.item.lane_id,
            "branch": self.item.branch,
            "worktree": worktree.as_posix() if worktree is not None else None,
            "outcome": self.outcome.value,
            "code": self.code,
            "remedy": self.remedy,
            "command": self.command,
            "recreate": self.recreate,
        }


@dataclass(frozen=True)
class LaneCleanupReport:
    results: tuple[LaneCleanupResult, ...]

    @property
    def kept(self) -> tuple[LaneCleanupResult, ...]:
        return tuple(result for result in self.results if result.outcome is LaneCleanupOutcome.KEPT)

    def to_json(self, repo_root: Path | None = None) -> list[dict[str, str | None]]:
        return [result.to_json(repo_root) for result in self.results]

    def render_lines(self) -> list[str]:
        """The plain-text "Lane cleanup" block (no markup), empty when there is no lane."""
        if not self.results:
            return []
        lines = ["Lane cleanup"]
        for result in self.results:
            lines.extend(_render_result(result))
        return lines


def _render_result(result: LaneCleanupResult) -> list[str]:
    lane = result.item.lane_id
    if result.outcome is LaneCleanupOutcome.RETAINED_BY_POLICY:
        return [f"  Retained  {lane}  retained by policy ({result.detail})"]
    if result.outcome is LaneCleanupOutcome.KEPT:
        lines = [f"  Kept      {lane}  {result.code}  {result.detail or ''}".rstrip()]
        then_run = f", then run: {result.command}" if result.command else ""
        lines.append(f"            Remedy: {result.remedy}{then_run}")
        return lines
    branch = result.item.branch or ""
    suffix = f"   (recreate: {result.recreate})" if result.recreate else ""
    if result.recoverable:
        suffix += f"   (recoverable: {result.recoverable})"
    return [f"  Removed   {lane}  {branch}{suffix}".rstrip()]


@dataclass(frozen=True)
class MissionBranchProjection:
    """The lane tips the Mission branch proved landed, read before its teardown (#7747, operator ruling 2026-11-24, A).

    ``mission_tip`` is the Mission branch tip read before the coordination teardown; ``proven_tips``
    are the lane tips :func:`specify_cli.lanes.lane_tip.is_landed_through_mission_branch` proved
    against it and ``anchor_sha``, the reconciliation PASS anchor. The guard uses the proof only for
    a landing whose PASS anchor is that SHA or was carried from it.
    """

    mission_tip: str
    proven_tips: frozenset[str]
    anchor_sha: str


@dataclass(frozen=True)
class LocalTargetAtPass:
    """Landing proof of ``consolidate``: the local target sat at the reconciliation PASS anchor.

    ``projection`` adds the lane tips the Mission branch proved landed (#7747, A); the guard accepts
    them as O3 evidence besides the content proof.
    """

    target_ref: str
    passed_sha: str
    projection: MissionBranchProjection | None = None


@dataclass(frozen=True)
class RemoteRef:
    """Landing proof of ``accept --mode pr`` / ``--push``: a named remote ref (bound by WP16)."""

    remote: str
    ref: str


LandingProof = LocalTargetAtPass | RemoteRef


@dataclass(frozen=True)
class LaneRetention:
    """Which lane legs the resolved retention decision lets run (C-017 precedence is the caller's)."""

    remove_worktree: bool = True
    delete_branch: bool = True


class LaneRemover(Protocol):
    def remove(self, item: LaneCleanupItem, *, landing: LandingProof | None) -> LaneCleanupResult: ...


def plan_lane_cleanup(
    manifest: LanesManifest,
    *,
    repo_root: Path,
    expected_tips: Mapping[str, str] | None = None,
) -> tuple[LaneCleanupItem, ...]:
    """One item per code lane, named from the manifest's recorded Mission slug (pure)."""
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    tips = expected_tips or {}
    items: list[LaneCleanupItem] = []
    for lane in manifest.lanes:
        if is_repo_root_lane(lane):
            continue
        worktree, _ = predict_lane_worktree(repo_root, manifest.mission_slug, lane.lane_id)
        branch = lane_created_branch(manifest, lane.lane_id)
        items.append(LaneCleanupItem(lane_id=lane.lane_id, worktree=Path(worktree), branch=branch, expected_tip=tips.get(branch)))
    return tuple(items)


def own_auto_rebase_move(repo_root: Path, branch: str, *, before: str | None, mission_before: str | None) -> list[str] | None:
    """``[before, after]`` when ``branch`` moved by exactly the run's own auto-rebase merge, else ``None`` (#6736).

    A stale lane is auto-rebased while it is consolidated (``lanes.auto_rebase``): a ``--no-ff``
    merge of the mission branch into the lane worktree, so the lane tip moves past the tip the
    claim validated. The move is accepted only in that exact shape: the live tip is a commit with
    two parents, the first ``before`` (the lane tip read just before this lane was consolidated)
    and the second ``mission_before`` (the mission branch tip read at that same moment). Any other
    move (a foreign commit, a second merge, a rewrite) is not this run's, and returns ``None``:
    cleanup then keeps checking against the claim-validated tip and refuses (fail closed).
    """
    if not before or not mission_before:
        return None
    after = _branch_tip(repo_root, branch)
    if after is None or after == before:
        return None
    probe = _git(repo_root, "rev-list", "--parents", "-n", "1", after)
    if probe.returncode != 0 or probe.stdout.split() != [after, before, mission_before]:
        return None
    return [before, after]


def cleanup_expected_tips(pre_mutation_refs: Mapping[str, str], rebase_moves: Mapping[str, Sequence[str]] | None = None) -> dict[str, str]:
    """The tip each lane's cleanup expects: the claim-validated tip, advanced over the run's own auto-rebase (#6736).

    A recorded move ``[from, to]`` is followed only while ``from`` is still the expected tip, so a
    move recorded by an earlier attempt whose snapshot was since re-captured is ignored.
    """
    tips = dict(pre_mutation_refs)
    for branch, move in (rebase_moves or {}).items():
        if len(move) >= 2 and tips.get(branch) == move[0]:
            tips[branch] = move[-1]
    return tips


def _retained_detail(retention: LaneRetention) -> str | None:
    """The retention key that keeps this lane in place, or ``None`` when every leg runs."""
    keys = []
    if not retention.remove_worktree:
        keys.append("retain_worktrees")
    if not retention.delete_branch:
        keys.append("retain_branches")
    return ", ".join(keys) or None


def _legs_to_run(item: LaneCleanupItem, retention: LaneRetention) -> LaneCleanupItem:
    """The item with the retained legs dropped.

    A retained worktree that still exists holds its branch checked out, so the branch stays with
    it (git cannot delete a checked-out branch; attempting it would read as a refusal).
    """
    worktree_kept = not retention.remove_worktree and item.worktree is not None and item.worktree.exists()
    return replace(
        item,
        worktree=item.worktree if retention.remove_worktree else None,
        branch=item.branch if retention.delete_branch and not worktree_kept else None,
    )


def _partial_detail(legs: LaneCleanupItem, detail: str) -> str:
    """The detail for a lane where some legs ran and the rest were retained, naming both."""
    ran = [name for name, leg in (("worktree", legs.worktree), ("branch", legs.branch)) if leg is not None]
    kept = [name for name in ("worktree", "branch") if name not in ran]
    return f"{' and '.join(ran)} removed; {' and '.join(kept)} retained, {detail}"


def apply(
    items: Iterable[LaneCleanupItem],
    remover: LaneRemover,
    *,
    landing: LandingProof | None,
    retention: LaneRetention,
) -> LaneCleanupReport:
    """Run every lane through ``remover``; never raises (FR-032)."""
    results: list[LaneCleanupResult] = []
    for item in items:
        legs = _legs_to_run(item, retention)
        detail = _retained_detail(retention)
        if legs.worktree is None and legs.branch is None:
            results.append(LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.RETAINED_BY_POLICY, detail=detail))
            continue
        result = _remove_one(remover, legs, landing)
        result = replace(result, item=item)
        if result.outcome is LaneCleanupOutcome.REMOVED and detail is not None:
            result = replace(result, outcome=LaneCleanupOutcome.RETAINED_BY_POLICY, detail=_partial_detail(legs, detail))
        results.append(result)
    return LaneCleanupReport(results=tuple(results))


def _remove_one(remover: LaneRemover, item: LaneCleanupItem, landing: LandingProof | None) -> LaneCleanupResult:
    try:
        return remover.remove(item, landing=landing)
    except Exception as exc:  # FR-032: after a verified landing a lane is a report line, never a traceback
        return _kept(item, LANE_CLEANUP_FAILED, f"lane cleanup failed unexpectedly ({exc})", detail=None)


#: Every lane is left in place when the coordination teardown before it refused (FR-031).
COORDINATION_TEARDOWN_REFUSED = "COORDINATION_TEARDOWN_REFUSED"
_RESUME_COMMAND = "spec-kitty consolidate --resume"


def kept_after_coordination_refusal(items: Iterable[LaneCleanupItem]) -> LaneCleanupReport:
    """The report for lanes the run did not touch because the coordination teardown refused."""
    results = tuple(
        LaneCleanupResult(
            item=item,
            outcome=LaneCleanupOutcome.KEPT,
            code=COORDINATION_TEARDOWN_REFUSED,
            remedy="resolve the coordination teardown refusal above",
            command=_RESUME_COMMAND,
            detail="left in place as evidence.",
        )
        for item in items
    )
    return LaneCleanupReport(results=results)


def _kept(item: LaneCleanupItem, code: str, remedy: str, *, detail: str | None, command: str | None = BACKSTOP_COMMAND) -> LaneCleanupResult:
    return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.KEPT, code=code, remedy=remedy, command=command, detail=detail)


ProcessProbe = Callable[[Sequence[Path]], ProcessProbeResult]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)


def _branch_tip(repo_root: Path, branch: str) -> str | None:
    probe = _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return probe.stdout.strip() or None if probe.returncode == 0 else None


def branch_tip(repo_root: Path, branch: str) -> str | None:
    """The SHA ``refs/heads/<branch>`` resolves to, or ``None``."""
    return _branch_tip(repo_root, branch)


def _anchor_carried_to(repo_root: Path, anchor: str, passed: str) -> bool:
    """The landing's PASS anchor is the one the projection was proven against, or carried from it.

    Consolidate advances the PASS anchor only over its own post-landing commits (FR-035), so a
    landing anchor that descends from the proven one is the same landing.
    """
    if not anchor or not passed:
        return False
    return anchor == passed or _git(repo_root, "merge-base", "--is-ancestor", anchor, passed).returncode == 0


def mission_branch_projection(
    repo_root: Path,
    mission_branch: str,
    landing: LocalTargetAtPass,
    tips: Iterable[str],
    mission_slug: str,
) -> MissionBranchProjection | None:
    """Prove each lane tip landed through the Mission branch, before that branch is torn down (#7747, A).

    ``tips`` are the consolidated lanes' tips. A lane's path superseded by another of them counts
    only through that lane's commits on the Mission branch (approved work the run merged; a fully
    canceled lane is never merged). ``None`` when there is no PASS anchor or no Mission branch to
    read: the lanes are then judged by the content proof alone.
    """
    from specify_cli.lanes.lane_tip import is_landed_through_mission_branch

    passed = landing.passed_sha.strip()
    mission_tip = _branch_tip(repo_root, mission_branch)
    if not passed or mission_tip is None:
        return None
    approved = tuple(tips)
    proven = frozenset(tip for tip in approved if is_landed_through_mission_branch(repo_root, tip, mission_tip, passed, mission_slug, approved_tips=approved))
    return MissionBranchProjection(mission_tip=mission_tip, proven_tips=proven, anchor_sha=passed)


def projection_tips(items: Iterable[LaneCleanupItem], repo_root: Path) -> list[str]:
    """The tip each lane's cleanup will judge: the claim-validated one, else the live branch tip."""
    tips = []
    for item in items:
        tip = item.expected_tip or (_branch_tip(repo_root, item.branch) if item.branch else None)
        if tip:
            tips.append(tip)
    return tips


def branch_exists(repo_root: Path, branch: str) -> bool:
    """True when ``refs/heads/<branch>`` resolves."""
    return _branch_tip(repo_root, branch) is not None


def _registered(repo_root: Path, worktree: Path) -> bool:
    listing = _git(repo_root, "worktree", "list", "--porcelain")
    target = worktree.resolve()
    return any(line.startswith("worktree ") and Path(line[len("worktree ") :]).resolve() == target for line in listing.stdout.splitlines())


_LOG = logging.getLogger(__name__)


def _clear_lane_records(repo_root: Path, branch: str) -> None:
    """Drop the lane's auto-rebase records once its branch is deleted (FR-005).

    Called only after a confirmed branch delete: a missing, kept or retained branch keeps its
    records (FR-034 parity). Best effort like the lane-tip clear: the branch is already gone and
    the records only keep tool merges reachable, so a failure is logged, never a kept lane. A
    ``BookkeepingRefError`` (a namespace bug) is not caught.
    """
    try:
        remaining = auto_rebase_record.delete_for_lane(repo_root, branch)
    except auto_rebase_record.AutoRebaseRecordError as exc:
        _LOG.debug("The auto-rebase records of %s could not be listed: %s", branch, exc)
        return
    if remaining:
        _LOG.debug("Auto-rebase records of the removed lane %s remain: %s", branch, ", ".join(remaining))


class MainTodayRemover:
    """The interim remover: today's guarded primitives, unchanged (C-004 interim exception).

    ``creation_base`` is the base a lane branch is judged against when its item carries no
    claim-validated tip (``mission close --discard`` passes the mission branch or the target).
    """

    def __init__(
        self,
        repo_root: Path,
        *,
        context: ResidueClassifier,
        creation_base: str | None = None,
        probe: ProcessProbe = processes_with_cwd_under,
        after_worktree_removed: Callable[[], None] | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._context = context
        self._creation_base = creation_base
        self._probe = probe
        self._after_worktree_removed = after_worktree_removed

    def remove(self, item: LaneCleanupItem, *, landing: LandingProof | None) -> LaneCleanupResult:
        # ``safe_is_dir`` (#3194): an unstattable worktree raises on every interpreter, so it
        # is never silently read as absent; ``apply`` turns the raise into a kept lane.
        if item.worktree is not None and safe_is_dir(item.worktree):
            refused = self._remove_worktree(item, item.worktree, landing)
            if refused is not None:
                return refused
        if item.branch is None:
            return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED)
        return self._delete_branch(item, item.branch)

    def _process_refusal(self, item: LaneCleanupItem, worktree: Path) -> LaneCleanupResult | None:
        probe = self._probe([worktree])
        if not probe.available:
            remedy = f"{probe.detail or 'running processes cannot be checked'}; close anything using {worktree} and remove it yourself"
            return _kept(item, PROCESS_PROOF_UNAVAILABLE, remedy, detail=f"{worktree} was not proven idle.")
        if probe.busy:
            return _kept(item, PROCESS_IN_WORKTREE, f"close the shell, editor or process standing in {worktree}", detail=f"{worktree} is in use.")
        return None

    def _remove_worktree(self, item: LaneCleanupItem, worktree: Path, landing: LandingProof | None) -> LaneCleanupResult | None:
        """Remove the worktree; a result only when the lane is kept."""
        if landing is not None:
            refused = self._process_refusal(item, worktree)
            if refused is not None:
                return refused
        try:
            guarded_worktree_remove(worktree, retain=False, context=self._context)
        except DestructiveOpRefused as refusal:
            return _kept(item, refusal.error_code, refusal.remediation, detail=_refusal_detail(refusal, worktree))
        except RuntimeError as exc:
            if _registered(self._repo_root, worktree):
                return _kept(item, _WORKTREE_REMOVE_REFUSED_BY_GIT, f"git refused to remove {worktree} ({exc})", detail=None)
            # Not a registered worktree: nothing the guard can prove, nothing removed (the old contract).
            return None
        if self._after_worktree_removed is not None:
            self._after_worktree_removed()  # e.g. let Windows release file handles before the next removal
        return None

    def _delete_branch(self, item: LaneCleanupItem, branch: str) -> LaneCleanupResult:
        from specify_cli.lanes import lane_tip

        tip = _branch_tip(self._repo_root, branch)
        if tip is None:
            # FR-034: a missing branch keeps its lane-tip ref, the last reference to the lane.
            return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED)
        try:
            guarded_branch_delete(self._repo_root, branch, creation_base=item.expected_tip or self._creation_base)
        except DestructiveOpRefused as refusal:
            return _kept(item, refusal.error_code, refusal.remediation, detail=f"{branch} holds commits no other ref reaches.")
        except RuntimeError as exc:
            return _kept(item, BRANCH_DELETE_REFUSED_BY_GIT, f"git refused to delete {branch} ({exc})", detail=None)
        if _branch_tip(self._repo_root, branch) is not None:
            return _kept(item, BRANCH_DELETE_REFUSED_BY_GIT, f"{branch} still exists after its delete", detail=None)
        lane_tip.clear_tip(self._repo_root, branch)
        _clear_lane_records(self._repo_root, branch)
        return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED, recreate=f"git branch {branch} {tip}")


def _refusal_detail(refusal: DestructiveOpRefused, worktree: Path) -> str:
    """The report line's detail; "uncommitted changes" only for the clean-check refusal (#7382).

    Other refusals carry entries too (a moved tip, a unique commit, an unreadable reflog), and
    naming those as uncommitted changes sent operators looking for edits that did not exist.
    """
    if refusal.error_code == MERGE_UNSAFE_WORKTREE_DIRTY and refusal.dirty_entries:
        return f"{worktree} has uncommitted changes."
    if refusal.error_code == WORKTREE_TIP_MOVED:
        now = f" (now at {refusal.dirty_entries[0]})" if refusal.dirty_entries else ""
        return f"{worktree} moved after its tip was validated{now}."
    if refusal.dirty_entries:
        return f"{worktree} was not removed: {', '.join(refusal.dirty_entries)}."
    return f"{worktree} was not removed."


class GuardedLaneRemover:
    """The lane remover bound to the landed-removal guard (WP16, FR-037, C-004, ADR 2026-11-06-1).

    A lane with a worktree, a branch and a landing proof is handed to ``guarded_landed_removal``:
    consolidate's :class:`LocalTargetAtPass` becomes the O3-local proof (the local target at the
    reconciliation PASS tip), pr-mode's :class:`RemoteRef` the named-remote proof. The tip is the
    claim-validated ``expected_tip`` (else the live branch tip, which the guard still proves landed
    and checks the worktree against). A guard refusal keeps the lane with the guard's code; the guard
    never forces a removal. A lane with no usable landing proof (none given, an empty PASS anchor, its
    worktree gone while its branch remains, or no tip to name) is kept with
    ``LANDING_PROOF_UNAVAILABLE``, its branch untouched (#7325); a lane whose worktree and branch are
    both gone is removed (nothing remains). Only the retained-branch leg (the worktree goes, no branch
    is deleted) still goes to :class:`MainTodayRemover` (plan decision PD-1, operator ruling
    2026-11-23).

    ``mission_slug`` (consolidate and ``orchestrator-api consolidate-mission``) makes the absorption
    proof :func:`specify_cli.lanes.lane_tip.is_absorbed_but_for_mission_bookkeeping`, which sets aside
    the Mission bookkeeping a ``lanes_with_coord`` lane carries from its syncs and never authored
    (#6736, #7747); without it the proof is the plain ``is_absorbed``.
    """

    def __init__(
        self,
        repo_root: Path,
        *,
        context: ResidueClassifier,
        creation_base: str | None = None,
        probe: ProcessProbe = processes_with_cwd_under,
        after_worktree_removed: Callable[[], None] | None = None,
        mission_slug: str | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._context = context
        self._mission_slug = mission_slug
        self._probe = probe
        self._after_worktree_removed = after_worktree_removed
        self._fallback = MainTodayRemover(repo_root, context=context, creation_base=creation_base, probe=probe, after_worktree_removed=after_worktree_removed)
        self._superseded_tips: set[str] = set()

    def remove(self, item: LaneCleanupItem, *, landing: LandingProof | None) -> LaneCleanupResult:
        if item.branch is None:
            # PD-1 (operator ruling 2026-11-23): the retained-branch leg removes the worktree only.
            return self._fallback.remove(item, landing=landing)
        unavailable = self._proof_unavailable(item, item.branch, landing)
        if unavailable is not None:
            return unavailable
        removal = _guarded_removal(self._repo_root, item, landing)
        if removal is None or landing is None or item.worktree is None:  # unreachable after the check above
            return _kept(item, _LANDING_PROOF_UNAVAILABLE, "no landing proof could be built", detail=None)
        prior_tip = self._name_tip_before_removal(item.branch, removal.tip)
        try:
            result = guarded_landed_removal(
                self._repo_root,
                removal,
                context=self._context,
                processes_in=self._busy,
                absorbed=self._absorption_proof(landing),
            )
        except DestructiveOpRefused as refusal:
            # A lane consolidate did not land (all its WPs canceled, or absorption unprovable) is kept
            # with the guard's code: falling back to the older remover deleted its only copy (#7316 landing).
            self._restore_tip(item.branch, prior_tip)
            return _kept(item, refusal.error_code, refusal.remediation, detail=_refusal_detail(refusal, item.worktree))
        if self._after_worktree_removed is not None:
            self._after_worktree_removed()
        if not result.branch_deleted:
            self._restore_tip(item.branch, prior_tip)
        if result.refusal is not None:
            return replace(_kept(item, result.refusal, f"the worktree was removed but {item.branch} was kept", detail=None), recreate=result.recreate)
        if result.branch_deleted:
            return self._after_branch_deleted(item, item.branch, removal.tip, recreate=result.recreate)
        return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED, recreate=result.recreate)

    def _name_tip_before_removal(self, branch: str, tip: str) -> str | None:
        """Write the lane-tip ref at ``tip`` before the guard may delete the branch; return the ref's earlier value.

        Tier R confirm 4: a failed write keeps the lane (nothing is removed yet), and an interruption
        after the branch delete still leaves its tip named.
        """
        from specify_cli.lanes import lane_tip

        prior: str | None = lane_tip.read_tip(self._repo_root, branch)
        lane_tip.record_tip(self._repo_root, branch, tip)
        return prior

    def _restore_tip(self, branch: str, prior: str | None) -> None:
        """Put back the lane-tip ref a kept lane had before :meth:`_name_tip_before_removal` wrote it."""
        from specify_cli.lanes import lane_tip

        if prior is None:
            lane_tip.clear_tip(self._repo_root, branch)
        else:
            lane_tip.record_tip(self._repo_root, branch, prior)

    def _after_branch_deleted(self, item: LaneCleanupItem, branch: str, tip: str, *, recreate: str | None) -> LaneCleanupResult:
        """Clear the lane-tip ref, except for a lane removed on the Mission-branch proof alone.

        Operator ruling 2026-11-24: such a lane's exact work is not on the target (later approved work
        superseded it, judged per path), so its ref, written before the removal, stays at the removed
        tip and is named in the report. A lane the content proof discharged has its work on the target:
        nothing to recover, so its ref is cleared.
        """
        from specify_cli.lanes import lane_tip

        # FR-005: the branch is gone, so its auto-rebase records go too (the lane-tip ref, when
        # kept below, still names the removed tip and keeps it reachable).
        _clear_lane_records(self._repo_root, branch)
        if tip not in self._superseded_tips:
            lane_tip.clear_tip(self._repo_root, branch)
            return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED, recreate=recreate)
        return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED, recreate=recreate, recoverable=lane_tip.tip_ref(branch))

    def _proof_unavailable(self, item: LaneCleanupItem, branch: str, landing: LandingProof | None) -> LaneCleanupResult | None:
        """A result when the guard cannot be given a landing proof for this lane, else ``None`` (#7325)."""
        worktree_present = item.worktree is not None and safe_is_dir(item.worktree)
        branch_tip = _branch_tip(self._repo_root, branch)
        if not worktree_present and branch_tip is None:
            # Nothing is left to remove; a missing branch keeps its lane-tip ref (FR-034).
            return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED)
        reason = _proof_unavailable_reason(landing, worktree_present=worktree_present, tip=item.expected_tip or branch_tip)
        if reason is None:
            return None
        remedy = _proof_unavailable_remedy(reason, branch, landing, branch_present=branch_tip is not None, worktree=item.worktree)
        return _kept(item, _LANDING_PROOF_UNAVAILABLE, remedy, detail=None, command=BACKSTOP_COMMAND if worktree_present else None)

    def _busy(self, path: Path) -> bool | None:
        """O2: ``None`` when the probe cannot tell (off Linux): the guard then keeps the lane (NFR-008)."""
        probe = self._probe([path])
        return (path in probe.busy) if probe.available else None

    def _absorption_proof(self, landing: LandingProof) -> Callable[[str, str], bool]:
        """O3: the content proof, else a tip the Mission branch proved landed (#7747, A).

        The content proof runs first so that a tip discharged only by the Mission branch is known: its
        lane-tip ref is kept after the removal (operator ruling 2026-11-24).
        """
        if not isinstance(landing, LocalTargetAtPass) or landing.projection is None:
            return self._absorbed
        projection = landing.projection
        if not _anchor_carried_to(self._repo_root, projection.anchor_sha, landing.passed_sha.strip()):
            return self._absorbed
        proven = projection.proven_tips

        def absorbed(tip: str, landing_ref: str) -> bool:
            if self._absorbed(tip, landing_ref):
                self._superseded_tips.discard(tip)
                return True
            if tip in proven:
                self._superseded_tips.add(tip)
                return True
            return False

        return absorbed

    def _absorbed(self, tip: str, landing_ref: str) -> bool:
        from specify_cli.lanes.lane_tip import AbsorptionUnsupported, is_absorbed, is_absorbed_but_for_mission_bookkeeping

        if self._mission_slug is not None:
            # #7747: never the plain proof first; its merge can hide a lane's Mission-file edit.
            proven: bool = is_absorbed_but_for_mission_bookkeeping(self._repo_root, tip, landing_ref, self._mission_slug)
            return proven
        try:
            plain: bool = is_absorbed(self._repo_root, tip, landing_ref, base=None)
            return plain
        except AbsorptionUnsupported:
            return False


def _proof_unavailable_reason(landing: LandingProof | None, *, worktree_present: bool, tip: str | None) -> str | None:
    """Why no landing proof can be handed to the guard, or ``None`` when one can (#7325)."""
    if landing is None:
        return "no landing proof was given"
    if isinstance(landing, LocalTargetAtPass) and not landing.passed_sha.strip():
        return "no reconciliation PASS anchor was recorded"
    if not worktree_present:
        return "its worktree is gone, so the landing cannot be proven here"
    if not tip:
        return "no tip can be named for it"
    return None


def _proof_unavailable_remedy(reason: str, branch: str, landing: LandingProof | None, *, branch_present: bool, worktree: Path | None) -> str:
    """A remedy whose commands run as printed (#7325): it names a revision only when one exists."""
    if landing is None:
        return f"{reason}; delete {branch} by hand only once you have checked that its work is on the target branch"
    ref = _landing_ref_name(landing)
    # A squash landing rewrites the lane's commits, so `git log <ref>..<lane>` lists them even when
    # their content landed: the remedy compares content instead.
    if branch_present:
        return f"{reason}; compare {branch} with {ref} (`git diff {ref} {branch}`) and delete it by hand only if its work is on {ref}"
    # The branch ref is gone: name the lane's recorded work tip, then compare it.
    return (
        f"{reason}; its last commit is `git rev-parse refs/spec-kitty/lane-tip/{branch}` (if that ref is missing, look in "
        f"`git fsck --lost-found`); compare it with {ref} (`git diff {ref} <sha>`) and remove {worktree} by hand only if that work is on {ref}"
    )


def _landing_ref_name(landing: LandingProof) -> str:
    if isinstance(landing, LocalTargetAtPass):
        return landing.target_ref
    return landing.ref


def _guarded_removal(repo_root: Path, item: LaneCleanupItem, landing: LandingProof | None) -> LandedRemoval | None:
    """The guard's removal for a worktree on its branch with a usable landing proof, else ``None`` (fallback).

    A local proof needs a recorded PASS tip; the tip is the claim-validated one, else the live branch tip.
    """
    if landing is None or item.branch is None or item.worktree is None or not safe_is_dir(item.worktree):
        return None
    if isinstance(landing, LocalTargetAtPass) and not landing.passed_sha.strip():
        return None
    tip = item.expected_tip or _branch_tip(repo_root, item.branch)
    return _landed_removal(item.worktree, item.branch, tip, landing) if tip else None


def _landed_removal(worktree: Path, branch: str, tip: str, landing: LandingProof) -> LandedRemoval:
    if isinstance(landing, LocalTargetAtPass):
        ref = landing.target_ref if landing.target_ref.startswith("refs/") else f"refs/heads/{landing.target_ref}"
        return LandedRemoval(worktree=worktree, branch=branch, tip=tip, remote="", landing_ref=ref, passed_sha=landing.passed_sha)
    return LandedRemoval(worktree=worktree, branch=branch, tip=tip, remote=landing.remote, landing_ref=landing.ref)
