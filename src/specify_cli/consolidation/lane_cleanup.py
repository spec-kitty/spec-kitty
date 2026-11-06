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

import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from specify_cli.git.destructive_guard import (
    DestructiveOpRefused,
    guarded_branch_delete,
    guarded_worktree_remove,
)
from specify_cli.git.ref_advance import ResidueClassifier
from specify_cli.lanes.compute import is_repo_root_lane, lane_created_branch
from specify_cli.lanes.models import LanesManifest
from specify_cli.workspace.process_probe import ProcessProbeResult, processes_with_cwd_under

__all__ = [
    "BACKSTOP_COMMAND",
    "COORDINATION_TEARDOWN_REFUSED",
    "LANE_CLEANUP_FAILED",
    "PROCESS_IN_WORKTREE",
    "PROCESS_PROOF_UNAVAILABLE",
    "LandingProof",
    "LaneCleanupItem",
    "LaneCleanupOutcome",
    "LaneCleanupReport",
    "LaneCleanupResult",
    "LaneRemover",
    "LaneRetention",
    "LocalTargetAtPass",
    "MainTodayRemover",
    "RemoteRef",
    "apply",
    "branch_exists",
    "kept_after_coordination_refusal",
    "plan_lane_cleanup",
]

#: The backstop every kept lane names (contracts/consolidate-cleanup-report.md).
BACKSTOP_COMMAND = "spec-kitty doctor workspaces --prune"
#: A process stands in the lane worktree.
PROCESS_IN_WORKTREE = "PROCESS_IN_WORKTREE"
#: Running processes cannot be checked on this platform (no ``/proc``).
PROCESS_PROOF_UNAVAILABLE = "PROCESS_PROOF_UNAVAILABLE"
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
        lines.append(f"            Remedy: {result.remedy}, then run: {result.command}")
        return lines
    branch = result.item.branch or ""
    suffix = f"   (recreate: {result.recreate})" if result.recreate else ""
    return [f"  Removed   {lane}  {branch}{suffix}".rstrip()]


@dataclass(frozen=True)
class LocalTargetAtPass:
    """Landing proof of ``consolidate``: the local target sat at the reconciliation PASS anchor."""

    target_ref: str
    passed_sha: str


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
            result = replace(result, outcome=LaneCleanupOutcome.RETAINED_BY_POLICY, detail=detail)
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


def _kept(item: LaneCleanupItem, code: str, remedy: str, *, detail: str | None) -> LaneCleanupResult:
    return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.KEPT, code=code, remedy=remedy, command=BACKSTOP_COMMAND, detail=detail)


ProcessProbe = Callable[[Sequence[Path]], ProcessProbeResult]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)


def _branch_tip(repo_root: Path, branch: str) -> str | None:
    probe = _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    return probe.stdout.strip() or None if probe.returncode == 0 else None


def branch_exists(repo_root: Path, branch: str) -> bool:
    """True when ``refs/heads/<branch>`` resolves."""
    return _branch_tip(repo_root, branch) is not None


def _registered(repo_root: Path, worktree: Path) -> bool:
    listing = _git(repo_root, "worktree", "list", "--porcelain")
    target = worktree.resolve()
    return any(line.startswith("worktree ") and Path(line[len("worktree ") :]).resolve() == target for line in listing.stdout.splitlines())


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
        if item.worktree is not None and item.worktree.exists():
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
        return LaneCleanupResult(item=item, outcome=LaneCleanupOutcome.REMOVED, recreate=f"git branch {branch} {tip}")


def _refusal_detail(refusal: DestructiveOpRefused, worktree: Path) -> str:
    if refusal.dirty_entries:
        return f"{worktree} has uncommitted changes."
    return f"{worktree} was not removed."
