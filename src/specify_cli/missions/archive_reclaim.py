"""Reclaim the coordination triple an archived Mission still holds (#4041).

``archive create`` only records an archive (:mod:`specify_cli.missions._archive` never mutates
Mission state). A coordination Mission whose consolidation kept its triple (a retention policy, or
a teardown that refused) keeps a coordination worktree, branch and ``meta.json`` marker after it is
archived. ``spec-kitty archive reclaim <mission>`` releases them, in this order:

1. the Mission must be archived (``RECLAIM_NOT_ARCHIVED``) and must have, or have had, a
   coordination topology (``RECLAIM_NO_COORDINATION``);
2. while the coordination branch exists, it must be proved landed (``RECLAIM_UNABSORBED``): the
   Mission carries ``merged_at`` and the live coordination tip equals, or is an ancestor of, the
   tip the verified landing recorded in
   :mod:`specify_cli.consolidation.landed_coordination` (operator rulings
   ``01M78HNKEQPPZMY24JZVJG2MNF`` and ``01M78JC7ZBJM0CY442BKDGBP7V``: a tree proof cannot pass on
   the default squash landing, whose status files differ by byte order);
3. the coordination worktree is removed through the shared teardown seam (a dirty worktree is the
   seam's own refusal, and the triple is kept);
4. the branch is deleted bound to the proved tip (compare-and-swap; a tip held by no other branch is
   kept under ``refs/spec-kitty/discarded/``), then the landed-coordination ref goes with it;
5. the marker is flattened through the sole flatten primitive and committed.

Every step is skipped when already done, so a second run reports that nothing is left and a partial
state finishes the remaining steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.git import GitCommandError, status_entries
from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam, resolve_write_target_or_degrade
from specify_cli.consolidation.git_probes import GitProbeError, commit_in_clone, commits_in_range, is_ancestor_strict, resolve_commit
from specify_cli.consolidation.landed_coordination import clear_landed_coordination_tip, landed_coordination_tip
from specify_cli.coordination.teardown import CoordTeardownKeptOnlyCopy, ProjectionTeardownAbort, teardown_coordination_topology
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping
from specify_cli.git.commit_helpers import SafeCommitError, SafeCommitHeadMismatch, preflight_commit
from specify_cli.git.destructive_guard import LANDED_INTENT, DestructiveOpRefused, discarded_ref, guarded_branch_delete
from specify_cli.mission_metadata import flatten_coordination_metadata, load_meta, recorded_mid8
from specify_cli.missions._archive import CANCELED, is_mission_archived, resolve_terminal_state
from specify_cli.status import is_mission_merged

__all__ = [
    "ReclaimRefused",
    "ReclaimReport",
    "holds_coordination_marker",
    "primary_mission_dir",
    "reclaim_archived_mission",
    "reclaim_command",
]

RECLAIM_NOT_ARCHIVED = "RECLAIM_NOT_ARCHIVED"
RECLAIM_NO_COORDINATION = "RECLAIM_NO_COORDINATION"
RECLAIM_UNABSORBED = "RECLAIM_UNABSORBED"
RECLAIM_WORKTREE_KEPT = "RECLAIM_WORKTREE_KEPT"
RECLAIM_MARKER_NOT_COMMITTED = "RECLAIM_MARKER_NOT_COMMITTED"
RECLAIM_NOT_ON_TARGET = "RECLAIM_NOT_ON_TARGET"

_COORDINATION_BRANCH_KEY = "coordination_branch"
_FLATTENED_KEY = "flattened"
_META_FILE = "meta.json"
_DISCARD_COMMAND = "spec-kitty mission close --discard --mission {slug}"
_MAX_LISTED_COMMITS = 20
_CHECK_AND_RERUN = "Check the repository, then re-run."


def reclaim_command(mission_slug: str) -> str:
    """The command that reclaims *mission_slug*'s coordination triple (also printed by ``archive create``)."""
    return f"spec-kitty archive reclaim {mission_slug}"


@dataclass(frozen=True)
class ReclaimStep:
    """One reclaim step: what it acted on and what happened (``removed``, ``deleted``, ``committed``, ...)."""

    name: str
    outcome: str
    detail: str = ""


@dataclass(frozen=True)
class ReclaimReport:
    """What a reclaim did; ``nothing_left`` when every step was already done."""

    mission_slug: str
    steps: tuple[ReclaimStep, ...]
    nothing_left: bool


class ReclaimRefused(Exception):
    """A refusal that changed nothing it guards: carries a stable ``error_code`` and a ``remedy``."""

    def __init__(self, error_code: str, message: str, remedy: str) -> None:
        self.error_code = error_code
        self.remedy = remedy
        super().__init__(message)


@dataclass(frozen=True)
class _Coordination:
    repo_root: Path
    feature_dir: Path
    mission_slug: str
    mid8: str
    branch: str


def primary_mission_dir(repo_root: Path, mission_slug: str) -> Path:
    """The Mission's PRIMARY-partition directory, where ``meta.json`` (and its marker) live."""
    primary: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    return primary


def holds_coordination_marker(repo_root: Path, mission_slug: str) -> bool:
    """True while *mission_slug*'s ``meta.json`` still names a coordination branch (``archive create`` points at reclaim then)."""
    meta = load_meta(primary_mission_dir(repo_root, mission_slug), allow_missing=True, on_malformed="none")
    return isinstance(meta, dict) and bool(meta.get(_COORDINATION_BRANCH_KEY))


def reclaim_archived_mission(repo_root: Path, mission_slug: str) -> ReclaimReport:
    """Reclaim the coordination worktree, branch and marker of the archived Mission *mission_slug*.

    Raises:
        ReclaimRefused: the Mission is not archived, never had a coordination topology, its
            coordination branch is not proved landed, its coordination worktree holds the only copy
            of files, or the branch moved while it was being deleted. Nothing is changed by a
            refusal raised before the first step; a later one keeps what it did not reach.
    """
    feature_dir = primary_mission_dir(repo_root, mission_slug)
    meta = load_meta(feature_dir)
    if not isinstance(meta, dict):
        raise ReclaimRefused(RECLAIM_NO_COORDINATION, f"{feature_dir / _META_FILE} could not be read.", "Repair meta.json, then re-run.")
    if not is_mission_archived(repo_root, str(meta.get("mission_id") or "")):
        raise ReclaimRefused(
            RECLAIM_NOT_ARCHIVED,
            f"Mission {mission_slug} is not archived.",
            f"Archive it first: spec-kitty archive create {mission_slug} --by <operator> --reason <why>.",
        )
    if _COORDINATION_BRANCH_KEY not in meta:
        return _finish_without_marker(repo_root, feature_dir, mission_slug, meta)
    mid8 = recorded_mid8(meta)
    if not mid8:
        raise ReclaimRefused(
            RECLAIM_NO_COORDINATION,
            f"Mission {mission_slug} records a coordination branch but no mid8, so its coordination worktree cannot be named.",
            "Repair meta.json (spec-kitty doctor identity), then re-run.",
        )
    coordination = _Coordination(repo_root, feature_dir, mission_slug, mid8, CoordinationWorkspace.branch_name(mission_slug, mid8))
    live_tip = _live_tip(coordination)
    if live_tip is not None:
        _prove_landed(coordination, live_tip)
    _require_committable(repo_root, feature_dir, mission_slug)
    steps = (
        _remove_worktree(coordination),
        _delete_branch(coordination, live_tip),
        _flatten_marker(coordination),
    )
    return ReclaimReport(mission_slug=mission_slug, steps=steps, nothing_left=False)


def _finish_without_marker(repo_root: Path, feature_dir: Path, mission_slug: str, meta: dict[str, object]) -> ReclaimReport:
    """No marker: a flattened Mission has nothing left (bar an uncommitted flatten); any other never coordinated."""
    if meta.get(_FLATTENED_KEY) is not True:
        raise ReclaimRefused(
            RECLAIM_NO_COORDINATION,
            f"Mission {mission_slug} has no coordination topology, so there is no coordination worktree or branch to reclaim.",
            "Nothing to do for this Mission.",
        )
    steps: tuple[ReclaimStep, ...] = ()
    if _meta_uncommitted(repo_root, feature_dir):
        _require_committable(repo_root, feature_dir, mission_slug)
        steps = (_commit_marker(repo_root, feature_dir, mission_slug),)
    return ReclaimReport(mission_slug=mission_slug, steps=steps, nothing_left=not steps)


def _live_tip(coordination: _Coordination) -> str | None:
    branch_ref = f"refs/heads/{coordination.branch}"
    try:
        if not commit_in_clone(coordination.repo_root, branch_ref):
            return None
        tip: str = resolve_commit(coordination.repo_root, branch_ref)
    except GitProbeError as exc:
        raise ReclaimRefused(RECLAIM_UNABSORBED, f"The coordination branch {coordination.branch} could not be read: {exc}", _CHECK_AND_RERUN) from exc
    return tip


def _prove_landed(coordination: _Coordination, live_tip: str) -> None:
    """Refuse unless ``merged_at`` is recorded and *live_tip* is at or behind the recorded landed tip."""
    if not is_mission_merged(coordination.feature_dir):
        raise ReclaimRefused(
            RECLAIM_UNABSORBED,
            f"The coordination branch {coordination.branch} is not proved landed: Mission {coordination.mission_slug} records no landing (merged_at).",
            _unlanded_remedy(coordination),
        )
    try:
        landed = landed_coordination_tip(coordination.repo_root, coordination.branch)
        if landed is None:
            raise ReclaimRefused(
                RECLAIM_UNABSORBED,
                f"The coordination branch {coordination.branch} is not proved landed: no recorded landed coordination tip "
                "(the Mission landed before spec-kitty recorded one, or its landing was rolled back).",
                _unlanded_remedy(coordination),
            )
        if live_tip == landed or is_ancestor_strict(coordination.repo_root, live_tip, landed):
            return
        late = commits_in_range(coordination.repo_root, landed, live_tip)
    except GitProbeError as exc:
        raise ReclaimRefused(RECLAIM_UNABSORBED, f"The landing of {coordination.branch} could not be proved: {exc}", _CHECK_AND_RERUN) from exc
    raise ReclaimRefused(
        RECLAIM_UNABSORBED,
        _late_commits_message(coordination.branch, landed, late),
        f"See one with git show <sha>; land or move them, or keep the branch. {_unlanded_remedy(coordination)}",
    )


def _late_commits_message(branch: str, landed: str, late: list[str]) -> str:
    listed = "\n".join(f"  {sha[:12]}" for sha in late[:_MAX_LISTED_COMMITS])
    more = f"\n  ... and {len(late) - _MAX_LISTED_COMMITS} more" if len(late) > _MAX_LISTED_COMMITS else ""
    head = f"The coordination branch {branch} holds {len(late)} commit(s) not reachable from the recorded landing ({landed[:12]})"
    return f"{head}, which the target never received:\n{listed}{more}"


def _unlanded_remedy(coordination: _Coordination) -> str:
    """Kept-and-unchanged, plus a next step that works: inspect, and remove by hand only once confirmed (#7598 fold)."""
    branch = coordination.branch
    target = _target_branch(coordination.feature_dir) or "<target branch>"
    remedy = (
        f"The coordination branch is kept; nothing was changed. See what it holds that {target} lacks: "
        f"git log {target}..{branch}; remove it by hand (git branch -D {branch}) only after confirming {target} "
        f"has all of it, then re-run: {reclaim_command(coordination.mission_slug)}."
    )
    if resolve_terminal_state(coordination.feature_dir) == CANCELED:
        return f"{remedy} A canceled Mission is abandoned instead with: {_DISCARD_COMMAND.format(slug=coordination.mission_slug)}."
    return remedy


def _remove_worktree(coordination: _Coordination) -> ReclaimStep:
    """Run the teardown seam even when the worktree is gone: its ledger guard protects the branch deleted next."""
    was_present = CoordinationWorkspace.is_present(coordination.repo_root, coordination.mission_slug, coordination.mid8)
    try:
        teardown_coordination_topology(
            coordination.repo_root,
            coordination.mission_slug,
            coordination.mid8,
            follow_up_command=reclaim_command(coordination.mission_slug),
            # Reclaim requires merged_at, so consolidate already persisted the retrospective; never commit one here.
            persist=False,
        )
    except (CoordTeardownKeptOnlyCopy, ProjectionTeardownAbort) as exc:
        raise ReclaimRefused(exc.error_code, str(exc), "The coordination worktree, branch and marker were kept.") from exc
    except Exception as exc:  # noqa: BLE001 — any other seam failure is a named, re-runnable refusal, never a traceback
        raise ReclaimRefused(
            RECLAIM_WORKTREE_KEPT,
            f"The coordination worktree of {coordination.mission_slug} could not be torn down: {exc}",
            f"The coordination worktree, branch and marker were kept. Clear the cause above, then re-run: {reclaim_command(coordination.mission_slug)}.",
        ) from exc
    if CoordinationWorkspace.is_present(coordination.repo_root, coordination.mission_slug, coordination.mid8):
        raise ReclaimRefused(
            RECLAIM_WORKTREE_KEPT,
            f"The coordination worktree of {coordination.mission_slug} could not be removed.",
            f"Check git worktree list, then re-run: {reclaim_command(coordination.mission_slug)}.",
        )
    return ReclaimStep("coordination worktree", "removed" if was_present else "already gone")


def _delete_branch(coordination: _Coordination, live_tip: str | None) -> ReclaimStep:
    """Delete the proved branch at *live_tip*, then drop its landed-coordination ref."""
    if live_tip is None:
        clear_landed_coordination_tip(coordination.repo_root, coordination.branch)
        return ReclaimStep("coordination branch", "already gone", coordination.branch)
    try:
        kept = guarded_branch_delete(
            coordination.repo_root,
            coordination.branch,
            creation_base=None,
            operator_intent=LANDED_INTENT,
            expected_tip=live_tip,
        )
    except DestructiveOpRefused as exc:
        raise ReclaimRefused(
            exc.error_code, f"The coordination branch {coordination.branch} was kept: {exc}", f"Re-run: {reclaim_command(coordination.mission_slug)}."
        ) from exc
    clear_landed_coordination_tip(coordination.repo_root, coordination.branch)
    detail = f"{coordination.branch} (tip kept as {discarded_ref(coordination.repo_root, coordination.branch, kept)})" if kept else coordination.branch
    return ReclaimStep("coordination branch", "deleted", detail)


def _flatten_marker(coordination: _Coordination) -> ReclaimStep:
    try:
        flatten_coordination_metadata(coordination.feature_dir)
    except Exception as exc:  # noqa: BLE001 — the branch is already gone; any flatten failure (e.g. a held Mission write lock) is a named, re-runnable refusal
        raise ReclaimRefused(
            RECLAIM_MARKER_NOT_COMMITTED,
            f"The coordination worktree and branch are gone, but the marker in {coordination.feature_dir / _META_FILE} could not be flattened: {exc}",
            f"Re-run once the cause above is cleared; it flattens and commits the marker: {reclaim_command(coordination.mission_slug)}.",
        ) from exc
    return _commit_marker(coordination.repo_root, coordination.feature_dir, coordination.mission_slug)


def _commit_marker(repo_root: Path, feature_dir: Path, mission_slug: str) -> ReclaimStep:
    """Commit the flattened ``meta.json`` through the sanctioned bookkeeping commit (as ``mission close --discard`` does)."""
    meta_path = feature_dir / _META_FILE
    try:
        commit_merge_bookkeeping(
            repo_root=repo_root,
            worktree_root=repo_root,
            mission_slug=mission_slug,
            message=_marker_commit_message(mission_slug),
            paths=(meta_path,),
            branch=_target_branch(feature_dir),
        )
    except Exception as exc:  # noqa: BLE001 — any commit failure is rendered as a named refusal the operator can re-run
        raise ReclaimRefused(
            RECLAIM_MARKER_NOT_COMMITTED,
            f"The coordination marker was flattened but {meta_path} could not be committed: {exc}",
            "Clear the cause above (on a branch mismatch, check out the branch it names), then re-run; "
            f"the re-run commits the flattened marker: {reclaim_command(mission_slug)}.",
        ) from exc
    return ReclaimStep("coordination marker", "flattened and committed", str(meta_path.relative_to(repo_root)))


def _target_branch(feature_dir: Path) -> str | None:
    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none")
    return (str(meta.get("target_branch") or "").strip() if isinstance(meta, dict) else "") or None


def _marker_commit_message(mission_slug: str) -> str:
    return f"chore({mission_slug}): flatten reclaimed coordination metadata"


def _preflight_marker_commit(repo_root: Path, feature_dir: Path, mission_slug: str) -> None:
    """Validate the marker commit without mutating anything: the destination and capability ``commit_merge_bookkeeping`` uses.

    Raises whatever :func:`preflight_commit` or the placement resolution raises.
    """
    target = resolve_write_target_or_degrade(repo_root, mission_slug, kind=MissionArtifactKind.PRIMARY_METADATA, degrade_ref=_target_branch(feature_dir))
    preflight_commit(
        repo_root=repo_root,
        worktree_root=repo_root,
        target=target,
        message=_marker_commit_message(mission_slug),
        paths=(feature_dir / _META_FILE,),
        capability=GuardCapability.MERGE_BOOKKEEPING,
    )


def _require_committable(repo_root: Path, feature_dir: Path, mission_slug: str) -> None:
    """Refuse, with nothing changed, unless the flattened marker can be committed (review cycle 1, F1)."""
    try:
        _preflight_marker_commit(repo_root, feature_dir, mission_slug)
    except SafeCommitHeadMismatch as exc:
        raise ReclaimRefused(
            RECLAIM_NOT_ON_TARGET,
            f"The repository root checkout is on {exc.observed_head}, but the flattened marker of {mission_slug} "
            f"commits to {exc.destination_ref}; nothing was changed.",
            f"Run git checkout {exc.destination_ref}, then re-run; it then completes: {reclaim_command(mission_slug)}.",
        ) from exc
    except (SafeCommitError, ActionContextError) as exc:
        raise ReclaimRefused(
            RECLAIM_NOT_ON_TARGET,
            f"The flattened marker of {mission_slug} could not be committed (checked before any change; nothing was changed): {exc}",
            f"Clear the cause above, then re-run: {reclaim_command(mission_slug)}.",
        ) from exc


def _meta_uncommitted(repo_root: Path, feature_dir: Path) -> bool:
    """True when ``meta.json`` has uncommitted changes; a git error refuses (never reads as "nothing uncommitted")."""
    meta_path = feature_dir / _META_FILE
    try:
        return bool(status_entries(repo_root, untracked=None, pathspecs=[str(meta_path.relative_to(repo_root))]))
    except (GitCommandError, ValueError) as exc:
        raise ReclaimRefused(
            RECLAIM_MARKER_NOT_COMMITTED,
            f"Whether the flattened marker in {meta_path} is committed could not be read: {exc}",
            f"Check the repository (git status {meta_path}), then re-run spec-kitty archive reclaim for this Mission.",
        ) from exc
