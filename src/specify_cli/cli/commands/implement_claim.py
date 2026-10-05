"""Claim recording for ``spec-kitty implement``: the pre-lane protected-branch refusal, the claim status
transition and the claimed->doing auto-commit.

Stays in the command package because the claim commit imports
``cli.commands.agent.tasks._collect_status_artifacts`` (C-004).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import typer
from specify_cli.cli.console import console

from kernel.git import GitCommandError, run_git
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
    is_under_worktrees_segment,
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
    """Filter collected status artifacts for a PRIMARY-root claim-commit bundle.

    #2155 / #3784 invariant: NO ``.worktrees/``-nested path may enter a
    primary-root ``safe_commit`` bundle. On coord topology ``feature_dir`` is
    the coordination worktree, so every coord-owned artifact
    ``_collect_status_artifacts`` returns — ``status.events.jsonl``,
    ``status.json``, AND ``tasks.md`` — lives under ``.worktrees/``. The
    ``is_status_state_path`` check alone drops only the two STATUS_STATE files
    and lets the coord-worktree ``tasks.md`` (a ``TASKS_INDEX`` kind) survive,
    tripping the ``SafeCommitPathPolicyError`` guard (#3784). Excluding ANY
    ``is_under_worktrees_segment`` path keeps the invariant whole; dropping the
    coord ``tasks.md`` from the CLAIM commit is correct — at claim time it is
    unchanged and the primary copy was already committed at finalize. On
    flat/legacy missions these artifacts are canonical on PRIMARY and stay.
    """
    resolved = [path.resolve() for path in artifacts]
    if not routes_through_coord:
        return resolved
    return [path for path in resolved if not (is_status_state_path(path) or is_under_worktrees_segment(path))]


def claim_commit_paths(
    *,
    repo_root: Path,
    feature_dir: Path,
    wp_file: Path,
    status_artifacts: Iterable[Path],
    routes_through_coord: bool,
    include_config: bool = True,
) -> list[Path]:
    """Return the exact ordered bundle the claim commit stages.

    Order: the WP file, the primary-surface status artifacts, ``meta.json`` when
    it exists, then ``.kittify/config.yaml`` when it exists. Pure apart from the
    two ``exists()`` probes. #5673 (``config.yaml`` is bundled although the claim
    never changes it) is a one-line change here. ``include_config=False`` leaves
    ``config.yaml`` out: the ``--no-auto-commit`` staging never stages a file the
    claim did not write.
    """
    paths = [wp_file.resolve(), *_primary_surface_status_paths(status_artifacts, routes_through_coord=routes_through_coord)]
    meta_file = feature_dir / "meta.json"
    config_file = repo_root / ".kittify" / "config.yaml"
    if meta_file.exists():
        paths.append(meta_file.resolve())
    if include_config and config_file.exists():
        paths.append(config_file.resolve())
    return paths


def _stage_claim_writes(repo_root: Path, wp_id: str, paths: Iterable[Path]) -> None:
    """``--no-auto-commit``: stage the claim's own writes, so "staged only" is true (#3471).

    Stages the claim-commit bundle (less ``config.yaml``) in the repository root
    checkout and commits nothing. A failed ``git add`` is reported, never hidden:
    the message then says the changes were left unstaged.
    """
    resolved_root = repo_root.resolve()
    rel_paths = [path.relative_to(resolved_root).as_posix() for path in paths if path.is_relative_to(resolved_root) and path.exists()]
    try:
        run_git(repo_root, "add", "--", *rel_paths)
    except GitCommandError as exc:
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
    wp_file: Path,
    auto_commit: bool | None,
    status_result: Any,
) -> None:
    """Auto-commit (or staged-only) side effect for a WP's claimed->'doing'
    transition. A no-op when *status_result* shows no lane change occurred.

    Split out of ``implement()`` so the outer try/except there keeps its
    exact ``SafeCommitPathPolicyError`` / ``PlacementResolutionRequired`` /
    soft-warning shape (D11 -- see
    ``test_implement_placement_routing.py::test_structured_error_is_not_swallowed_as_soft_warning``,
    which asserts on ``implement()``'s own source).
    """
    if status_result is None or not status_result.status_changed:
        return
    from specify_cli.cli.commands.agent.tasks import _collect_status_artifacts

    if not auto_commit:
        _stage_claim_writes(
            repo_root,
            wp_id,
            claim_commit_paths(
                repo_root=repo_root,
                feature_dir=feature_dir,
                wp_file=wp_file,
                status_artifacts=_collect_status_artifacts(feature_dir),
                routes_through_coord=routes_through_coordination(resolve_topology(repo_root, mission_slug)),
                include_config=False,
            ),
        )
        return

    commit_msg = f"chore: {wp_id} claimed for implementation"
    # #2155 (FR-002 / T011) + #3784: bundle ONLY primary-surface artifacts
    # into the primary-root claim commit. The status transition was already
    # committed to the coordination branch by ``start_implementation_status``
    # (the transactional emitter); under coord topology every coord-owned
    # artifact ``_collect_status_artifacts`` returns (events.jsonl /
    # status.json / the coord-worktree ``tasks.md``) lives UNDER
    # ``.worktrees/``, so staging it from the primary root trips the #1887
    # ``SafeCommitPathPolicyError`` guard. ``claim_commit_paths`` drops ANY
    # ``.worktrees/``-nested path on coord topology (the
    # ``is_status_state_path`` check alone let ``tasks.md`` — a TASKS_INDEX
    # kind — survive, the #3784 residual); on a flat/legacy mission these
    # artifacts ARE canonical on PRIMARY and stay in the bundle.
    files_to_commit = claim_commit_paths(
        repo_root=repo_root,
        feature_dir=feature_dir,
        wp_file=wp_file,
        status_artifacts=_collect_status_artifacts(feature_dir),
        routes_through_coord=routes_through_coordination(resolve_topology(repo_root, mission_slug)),
    )

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
