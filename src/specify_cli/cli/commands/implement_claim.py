"""Claim recording for ``spec-kitty implement``: the pre-lane protected-branch refusal, the claim status
transition and the claimed->doing auto-commit. The auto-commit carries exactly the paths the claim wrote (#5673).

Stays in the command package because the claim commit imports
``cli.commands.agent.tasks._collect_status_artifacts`` (C-004).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import typer
from specify_cli.cli.console import console

from kernel.git import run_git
from specify_cli.core.git_ops import get_current_branch
from specify_cli.git import safe_commit
from specify_cli.git.commit_helpers import (
    SafeCommitHeadMismatch,
    SafeCommitPathPolicyError,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from mission_runtime import (
    ActionContextError,
    MissionArtifactKind,
    placement_seam,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.coherence import (
    is_status_state_path,
)
from specify_cli.coordination.surface_resolver import (
    StatusReadPathNotFound,
    resolve_status_surface_with_anchor,
)
from specify_cli.status import TransitionError
from specify_cli.status import (
    Lane,
    WorkPackageClaimConflict,
    claim_policy_metadata,
    read_events,
    reduce,
    start_implementation_status,
)

#: The lanes ``start_implementation_status`` moves a WP out of. Only such a claim
#: changes the WP's lane, and only a lane change ends in the claim commit
#: (``_commit_wp_claim_status`` returns early otherwise); an ``in_progress``
#: resume commits nothing.
_CLAIM_COMMITTING_LANES = frozenset({Lane.PLANNED, Lane.CLAIMED})

#: Printed when ``meta.json`` already differed from HEAD before the claim wrote the VCS lock into it (#5673).
_META_DIRTY_BEFORE_CLAIM_WARNING = (
    "[yellow]Warning:[/yellow] {meta} had uncommitted changes before the claim; the claim's VCS lock was left uncommitted with them -- commit meta.json yourself."
)
_WP_DIRTY_BEFORE_CLAIM_WARNING = (
    "[yellow]Warning:[/yellow] {wp} had uncommitted changes before the claim; the claim's workspace stamp was left "
    "uncommitted with them -- commit the WP prompt yourself."
)


def _protected_branch_status_commit_error(branch: str, repo_root: Path, mission_slug: str | None = None) -> str | None:
    # ProtectionPolicy.resolve_for_mission is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch+meta reads happen once; is_protected() is I/O-free. A mission-scoped
    # write also honours that mission's ``commit_to_target`` for its own target (#5100 FR-008).
    if not ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(branch):
        return None
    return (
        f"Refusing to start implementation status on protected branch '{branch}' "
        "before mutating status files. Run this status commit from an allowed "
        "coordination/lane branch, or rerun with --no-auto-commit when you "
        "intentionally want to handle the status artifact commit manually."
    )


def _status_commit_destination_branch(repo_root: Path, fallback_branch: str) -> str:
    """Return the branch that the pre-lane status commit would target."""
    return get_current_branch(repo_root) or fallback_branch


def _raise_if_status_commit_protected(repo_root: Path, planning_branch: str, auto_commit: bool | None, mission_slug: str | None = None) -> None:
    """Raise ``ValueError`` when auto-commit is on and the pre-lane status
    commit would target a protected branch."""
    if not auto_commit:
        return
    status_destination = _status_commit_destination_branch(repo_root, fallback_branch=planning_branch)
    protected_error = _protected_branch_status_commit_error(status_destination, repo_root, mission_slug)
    if protected_error is not None:
        raise ValueError(protected_error)


def _protected_destination_hint(destination_ref: str) -> str:
    """The way out of a #5738 refusal whose destination is a protected branch.

    The mismatch message tells the operator to check out the destination; for a
    protected destination that only leads to the protected-branch refusal of
    :func:`_raise_if_status_commit_protected`, so the refusal names the remedy that
    works.
    """
    return (
        f" '{destination_ref}' is a protected branch, so the claim's status commit cannot "
        "land there either: rerun with --no-auto-commit to stage the claim's changes and "
        "commit them yourself."
    )


def _raise_if_claim_commit_head_mismatch(repo_root: Path, mission_slug: str, wp_id: str, auto_commit: bool | None) -> None:
    """Refuse up front a claim whose auto-commit cannot land (#5738).

    The claim commit (``_commit_wp_claim_status``) targets the PRIMARY write home
    of ``WORK_PACKAGE_TASK`` from the repository root checkout, and ``safe_commit``
    asserts that checkout's HEAD is that branch. When auto-commit is on, the claim
    will move the WP's lane, and the checkout is on another branch (or detached),
    that commit can only fail -- after the lane worktree, the VCS lock and the
    status write already landed. Raise the very ``SafeCommitHeadMismatch`` the
    commit would raise, before any of them; when the destination is protected,
    its message also names ``--no-auto-commit`` (:func:`_protected_destination_hint`).
    Only that mismatch is decided here: a destination the resolver reports as
    unresolvable is left to the commit-time handling.
    """
    if not auto_commit:
        return
    status_dir = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    current_lane = reduce(read_events(status_dir)).work_packages.get(wp_id, {}).get("lane")
    if current_lane not in _CLAIM_COMMITTING_LANES:
        return
    try:
        destination_ref = placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref
    except (ActionContextError, StatusReadPathNotFound):
        # The resolver's typed "does not resolve" failures (``CoordinationBranchDeleted``
        # is a ``StatusReadPathNotFound``): only a resolved destination is judged here.
        # Such a destination (e.g. a merged mission whose coordination branch was torn
        # down) keeps its existing commit-time handling in ``commit_claim`` unchanged.
        return
    observed_head = get_current_branch(repo_root)
    if observed_head == destination_ref:
        return
    mismatch = SafeCommitHeadMismatch(
        destination_ref=destination_ref,
        observed_head=observed_head or "<detached>",
        worktree_root=repo_root,
    )
    if ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(destination_ref):
        # Same type and ``error_code``; only the message gains the working remedy.
        mismatch.message += _protected_destination_hint(destination_ref)
        mismatch.args = (mismatch.message,)
    raise mismatch


def _primary_surface_status_paths(artifacts: Iterable[Path], *, routes_through_coord: bool) -> list[Path]:
    """Filter collected status artifacts down to the status pair a PRIMARY-root claim commit may carry.

    Only the two STATUS_STATE files (``status.events.jsonl``, ``status.json``) are
    claim-written (#5673): ``tasks.md`` is collected beside them but the claim never
    rewrites it, so it never enters the bundle, on any topology.

    #2155 / #3784 invariant: NO ``.worktrees/``-nested path may enter a
    primary-root ``safe_commit`` bundle. On coord topology ``feature_dir`` is
    the coordination worktree, so every coord-owned artifact lives under
    ``.worktrees/`` and the transactional emitter already committed the status
    pair to the coordination branch: nothing is left for the primary claim commit.
    On flat/legacy missions the pair is canonical on PRIMARY and stays.
    """
    if routes_through_coord:
        return []
    return [path.resolve() for path in artifacts if is_status_state_path(path)]


def claim_commit_paths(
    *,
    feature_dir: Path,
    status_artifacts: Iterable[Path],
    routes_through_coord: bool,
    meta_written: bool,
    wp_file: Path | None = None,
    wp_stamped: bool = False,
) -> list[Path]:
    """Return the exact ordered list of paths the claim wrote, which the claim commit carries (#5673).

    Order: ``status.events.jsonl``, ``status.json``, the mission's ``meta.json`` iff ``meta_written``
    (the first claim's VCS lock changed it and it was clean before), then the claimed WP prompt iff
    ``wp_stamped`` (workspace allocation stamped ``base_branch``/``base_commit``/``created_at`` into it in
    this claim and it was clean before; lanes and coord topologies). Never another WP's prompt,
    ``tasks.md`` or ``.kittify/config.yaml`` (no claim path writes them). The caller decides both
    flags from what the claim observed, never from ``exists()``.
    """
    paths = _primary_surface_status_paths(status_artifacts, routes_through_coord=routes_through_coord)
    if meta_written:
        paths.append((feature_dir / "meta.json").resolve())
    if wp_stamped and wp_file is not None:
        paths.append(wp_file.resolve())
    return paths


def _stage_claim_writes(repo_root: Path, wp_id: str, collect_paths: Callable[[], Iterable[Path]]) -> None:
    """``--no-auto-commit``: stage the claim's own writes, so "staged only" is true (#3471).

    Stages the claim-commit list in the repository root
    checkout and commits nothing. ``git add --force`` matches ``safe_commit``'s
    staging, so a claim file a consumer repository ignores is staged like the auto-commit
    would commit it, and git never stages part of the bundle before refusing an ignored
    path. Gathering the bundle runs here too: the claim has already landed, so a
    failure to gather or stage it (git or not) is reported, never hidden and never
    worded as a failed status update; the message then says the changes were left
    unstaged.
    """
    try:
        resolved_root = repo_root.resolve()
        rel_paths = [path.relative_to(resolved_root).as_posix() for path in collect_paths() if path.is_relative_to(resolved_root) and path.exists()]
        if rel_paths:
            run_git(repo_root, "add", "--force", "--", *rel_paths)
    except Exception as exc:  # staging is best-effort: the claim's status write already landed
        console.print(f"[yellow]Warning:[/yellow] Could not stage the claim's changes: {exc}")
        console.print(f"[cyan]→ {wp_id} moved to 'doing' (auto-commit disabled, changes left unstaged)[/cyan]")
        return
    console.print(f"[cyan]→ {wp_id} moved to 'doing' (auto-commit disabled, changes staged only)[/cyan]")


def _commit_wp_claim_status(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    wp_file: Path | None = None,
    auto_commit: bool | None,
    status_result: Any,
    meta_written: bool = False,
    meta_dirty_before: bool = False,
    wp_stamped: bool = False,
    wp_dirty_before: bool = False,
) -> None:
    """Auto-commit (or staged-only) side effect for a WP's claimed->'doing'
    transition. A no-op when *status_result* shows no lane change occurred.

    The commit carries exactly what the claim wrote (#5673): the status pair, plus
    ``meta.json`` when ``meta_written`` and it was not ``meta_dirty_before`` (an
    operator-modified ``meta.json`` stays uncommitted and a warning names it).
    The claimed WP prompt (*wp_file*) joins it the same way when allocation stamped it in this claim
    (``wp_stamped``) and it was clean before; one that was ``wp_dirty_before`` stays uncommitted and a
    warning names it.

    Split out of ``implement()`` so the outer try/except there keeps its
    exact ``SafeCommitPathPolicyError`` / ``PlacementResolutionRequired`` /
    soft-warning shape (D11 -- see
    ``test_implement_placement_routing.py::test_structured_error_is_not_swallowed_as_soft_warning``,
    which asserts on ``implement()``'s own source).
    """
    if status_result is None or not status_result.status_changed:
        return
    from specify_cli.cli.commands.agent.tasks import _collect_status_artifacts

    # Decided from what the claim observed, never from ``exists()``: a ``meta.json``
    # the operator had already modified is left as it is (#5673).
    commit_meta = meta_written and not meta_dirty_before
    if meta_written and meta_dirty_before:
        console.print(_META_DIRTY_BEFORE_CLAIM_WARNING.format(meta=f"kitty-specs/{mission_slug}/meta.json"))

    commit_wp = wp_stamped and not wp_dirty_before and wp_file is not None
    if wp_stamped and wp_dirty_before and wp_file is not None:
        console.print(_WP_DIRTY_BEFORE_CLAIM_WARNING.format(wp=wp_file.name))

    def gather() -> list[Path]:
        return claim_commit_paths(
            feature_dir=feature_dir,
            status_artifacts=_collect_status_artifacts(feature_dir),
            routes_through_coord=routes_through_coordination(resolve_topology(repo_root, mission_slug)),
            meta_written=commit_meta,
            wp_file=wp_file,
            wp_stamped=commit_wp,
        )

    if not auto_commit:
        _stage_claim_writes(repo_root, wp_id, gather)
        return

    files_to_commit = gather()
    if not files_to_commit:
        # Coord topology: the transactional emitter already committed the status pair to the
        # coordination branch and the claim wrote nothing else; there is nothing to commit.
        console.print(f"[cyan]→ {wp_id} moved to 'doing'[/cyan]")
        return

    commit_msg = f"chore: {wp_id} claimed for implementation"
    # #2155 (FR-002 / T011) + #3784: the list holds ONLY primary-surface paths the claim wrote.
    # The status transition was already committed to the coordination branch by
    # ``start_implementation_status`` under coord topology, so ``claim_commit_paths``
    # returns no status path there; on a flat/legacy mission the pair is canonical on PRIMARY.

    # #610: every file gathered above is, by construction, primary-surface
    # (the coord-owned status pair is filtered out above under coord
    # topology; nothing coord-residue is ever collected here). The claim
    # commit therefore always targets the PRIMARY write home -- resolved
    # through the canonical seam (``placement_seam(...).write_target(kind)``,
    # never a hand-built ``CommitTarget``, per contracts/seam-api.md) --
    # never the seam-resolved ``placement_ref`` this function used to route
    # through (which names the COORDINATION branch under coord topology).
    # Targeting ``placement_ref`` here was the latent bug behind this call
    # site's ``SafeCommitHeadMismatch``: ``repo_root`` (the primary checkout)
    # is on the mission's target branch, not the coordination branch, so
    # asserting HEAD against the coord ref always mismatched -- previously
    # masked by the very swallow this issue removes. ``WORK_PACKAGE_TASK`` is
    # a ``_PRIMARY_ARTIFACT_KINDS`` member (like every other kind bundled
    # above), so its write target is the primary target branch under every
    # topology.
    claim_commit_target = placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.WORK_PACKAGE_TASK)
    try:
        safe_commit(
            repo_root=repo_root,
            worktree_root=repo_root,
            target=claim_commit_target,
            message=commit_msg,
            paths=tuple(files_to_commit),
        )
        console.print(f"[cyan]→ {wp_id} moved to 'doing'[/cyan]")
    except SafeCommitPathPolicyError:
        # #2155 (FR-002 / T011): a wrong-surface guard refusal is a real
        # defect, not an "Auto-commit skipped" warning — re-raise so it
        # surfaces instead of leaving the branch silently dirty. The
        # partition above prevents this on a correct bundle; reaching here
        # means a coord-owned path leaked into the primary commit and the
        # C-006 guard MUST stay authoritative (never swallowed).
        raise
    except SafeCommitHeadMismatch:
        # #610: a genuine branch-name mismatch is a real defect, not an
        # "Auto-commit skipped" warning either. The status/lane files above
        # were already written to disk by the caller before this commit was
        # attempted, so swallowing this here left the worktree dirty with no
        # commit to cover it -- exactly what later trips ref_advance.py's
        # dirty-worktree gate at merge time. Re-raise so the mismatch
        # surfaces immediately instead of being discovered downstream.
        raise
    except Exception as _commit_exc:  # noqa: BLE001 — non-policy git failures stay soft
        console.print(f"[yellow]Warning:[/yellow] Could not auto-commit lane change: {_commit_exc}")


def _start_wp_implementation_status(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    effective_actor: str,
    workspace_path: Path,
    status_execution_mode: str,
    repo_root: Path,
) -> Any:
    """Call ``start_implementation_status``, translating claim-conflict /
    transition failures into a printed error + ``typer.Exit(1)``."""
    import os as _os

    try:
        return start_implementation_status(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            actor=effective_actor,
            workspace_context=f"{status_execution_mode}:{workspace_path}",
            execution_mode=status_execution_mode,
            repo_root=repo_root,
            # WP07/T026 (FR-004/FR-014): the claim triple rides the
            # planned -> claimed transition's policy_metadata sidecar; the
            # frontmatter pre-write mirror was removed in the #2816 cutover.
            policy_metadata=claim_policy_metadata(_os.getppid(), effective_actor),
        )
    except WorkPackageClaimConflict as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except TransitionError as exc:
        console.print(f"[red]Error:[/red] Could not start implementation status: {exc}")
        raise typer.Exit(1) from exc
