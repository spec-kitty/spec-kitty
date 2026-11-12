"""Claim recording for ``spec-kitty implement``: the pre-lane protected-branch refusal, the claim status
transition and the claimed->doing auto-commit. The auto-commit carries exactly the paths the claim wrote (#5673).

Stays in the command package because the claim commit imports
``cli.commands.agent.tasks._collect_status_artifacts`` (C-004).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from specify_cli.cli.console import console

from kernel.git import run_git
from specify_cli.core.constants import WORKTREES_DIR
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
from specify_cli.coordination.surface_resolver import StatusReadPathNotFound
from specify_cli.status import TransitionError
from specify_cli.status import (
    Lane,
    WorkPackageClaimConflict,
    WPInnerStateDelta,
    claim_policy_metadata,
    start_implementation_status,
)


@dataclass(frozen=True)
class DispatchedClaimIdentity:
    """The dispatch-resolved identity ``agent action implement`` records on the claim (#7159).

    ``actor`` is the structured implementer actor (``build_status_actor``) and
    ``annotation_delta`` the resolved binding's claim annotation, both built by the
    caller from its dispatch context (``--agent``, ``--profile``, ``--invocation-id``).
    """

    actor: dict[str, str | None]
    annotation_delta: WPInnerStateDelta | None


#: Set only by :func:`dispatched_claim_identity`, around ``agent action implement``'s
#: call of the top-level ``implement`` command. A structured actor cannot travel
#: through that command's typer options, and the command's own ``--actor`` stays a
#: verbatim string for its direct callers.
_DISPATCHED_CLAIM_IDENTITY: ContextVar[DispatchedClaimIdentity | None] = ContextVar("dispatched_claim_identity", default=None)


#: ``False`` only inside :func:`no_auto_commit_not_offered`: ``agent action implement`` has no
#: ``--no-auto-commit``, so a refusal printed through it must not name that option (#7601,
#: SC-003). The top-level ``spec-kitty implement`` keeps the default and its remedy text.
_NO_AUTO_COMMIT_OFFERED: ContextVar[bool] = ContextVar("no_auto_commit_offered", default=True)


@contextmanager
def no_auto_commit_not_offered() -> Iterator[None]:
    """Withhold ``--no-auto-commit`` from every claim refusal printed inside this block (#7601).

    Entered by ``agent action implement`` around its call of the top-level ``implement``
    command: that entry point has no ``--no-auto-commit``, so its remedies name only ways
    out it can follow. The previous value is restored on exit, also on an exception.
    """
    token = _NO_AUTO_COMMIT_OFFERED.set(False)
    try:
        yield
    finally:
        _NO_AUTO_COMMIT_OFFERED.reset(token)


@contextmanager
def dispatched_claim_identity(identity: DispatchedClaimIdentity | None) -> Iterator[None]:
    """Record *identity* on any implement claim emitted inside this block (#7159).

    ``agent action implement`` creates a fresh code lane through the top-level
    ``implement`` command, which emits the claim. Without this, that claim recorded
    the bare ``--agent`` string and dropped ``--profile``, so the review-independence
    gate read the implementer as ``tool::``. ``None`` records nothing new: the claim
    keeps the command's own actor.
    """
    token = _DISPATCHED_CLAIM_IDENTITY.set(identity)
    try:
        yield
    finally:
        _DISPATCHED_CLAIM_IDENTITY.reset(token)


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


def _protected_branch_status_commit_error(
    branch: str,
    repo_root: Path,
    mission_slug: str | None = None,
    *,
    accepts_no_auto_commit: bool = True,
    checkout: Path | None = None,
) -> str | None:
    """The refusal for a claim status commit onto protected *branch*, else ``None``.

    *accepts_no_auto_commit* is ``False`` for ``agent action implement``, which has no
    ``--no-auto-commit``: its remedy then names the branch judged, the *checkout* it is
    checked out in, and only ways out that command can follow (#7601, SC-003). The
    top-level ``spec-kitty implement`` text is unchanged.
    """
    # ProtectionPolicy.resolve_for_mission is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch+meta reads happen once; is_protected() is I/O-free. A mission-scoped
    # write also honours that mission's ``commit_to_target`` for its own target (#5100 FR-008).
    if not ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(branch):
        return None
    if not accepts_no_auto_commit:
        where = f" (checked out in {checkout})" if checkout is not None else ""
        return (
            f"Refusing to start implementation status on protected branch '{branch}'{where} "
            "before mutating status files. Check out an allowed coordination/lane branch in "
            "that checkout and rerun, or claim the work package with the top-level "
            "`spec-kitty implement` command, which can leave the status commit to you."
        )
    return (
        f"Refusing to start implementation status on protected branch '{branch}' "
        "before mutating status files. Run this status commit from an allowed "
        "coordination/lane branch, or rerun with --no-auto-commit when you "
        "intentionally want to handle the status artifact commit manually."
    )


def checkout_branch_or_fallback(checkout: Path, fallback_branch: str) -> str:
    """The branch *checkout* has checked out, or *fallback_branch* when it is detached or unreadable.

    The one current-checkout HEAD read the protected-branch preflights share: the claim
    preflight (:func:`_claim_checkout_branch`) and move-task's WP-file holder
    (``tasks_shared._wp_file_commit_branch``) both judge the branch of the checkout the
    commit runs in (#7601, decision ``01M78JFMRQS6GE04BENPXGQX8J``). Tracked by #2453.
    """
    return get_current_branch(checkout) or fallback_branch


def _claim_checkout_branch(repo_root: Path, feature_dir: Path | None, mission_slug: str | None, fallback_branch: str) -> tuple[Path, str]:
    """The checkout the claim commit runs in and the branch it has checked out (#7601).

    The checkout is :func:`_claim_commit_checkout`'s answer -- the one the #5738 check
    (:func:`_raise_if_claim_commit_head_mismatch`) judges too: a default Mission's topic
    holder before its landing, else the repository root checkout. With no *feature_dir* or
    *mission_slug*, or when the placement does not resolve, it is *repo_root* (the check is
    never skipped).
    """
    checkout = repo_root
    if feature_dir is not None and mission_slug is not None:
        try:
            checkout = _claim_commit_checkout(repo_root, feature_dir, mission_slug)
        except (ActionContextError, StatusReadPathNotFound):
            checkout = repo_root
    return checkout, checkout_branch_or_fallback(checkout, fallback_branch)


def _raise_if_status_commit_protected(
    repo_root: Path,
    planning_branch: str,
    auto_commit: bool | None,
    mission_slug: str | None = None,
    feature_dir: Path | None = None,
) -> None:
    """Raise ``ValueError`` when auto-commit is on and the claim status commit would land on a protected branch.

    The branch judged is the one checked out in the checkout the claim commit runs in
    (:func:`_claim_checkout_branch`), *planning_branch* when that checkout is detached.
    """
    if not auto_commit:
        return
    checkout, status_destination = _claim_checkout_branch(repo_root, feature_dir, mission_slug, planning_branch)
    protected_error = _protected_branch_status_commit_error(
        status_destination,
        repo_root,
        mission_slug,
        accepts_no_auto_commit=_NO_AUTO_COMMIT_OFFERED.get(),
        checkout=checkout,
    )
    if protected_error is not None:
        raise ValueError(protected_error)


def _protected_destination_hint(destination_ref: str, *, accepts_no_auto_commit: bool = True) -> str:
    """The way out of a #5738 refusal whose destination is a protected branch.

    The mismatch message tells the operator to check out the destination; for a
    protected destination that only leads to the protected-branch refusal of
    :func:`_raise_if_status_commit_protected`, so the refusal names the remedy that
    works. ``agent action implement`` (*accepts_no_auto_commit* ``False``) has no
    ``--no-auto-commit``, so its remedy names the command that has it (#7601).
    """
    if not accepts_no_auto_commit:
        return (
            f" '{destination_ref}' is a protected branch, so the claim's status commit cannot "
            "land there either: claim the work package with the top-level `spec-kitty implement` "
            "command, which can stage the claim's changes for you to commit."
        )
    return (
        f" '{destination_ref}' is a protected branch, so the claim's status commit cannot "
        "land there either: rerun with --no-auto-commit to stage the claim's changes and "
        "commit them yourself."
    )


def _claim_commit_checkout(repo_root: Path, feature_dir: Path, mission_slug: str) -> Path:
    """The checkout the claim commit runs in: the repository root checkout, or (FR-061) the topic holder.

    Until a ``topology_source: default`` Mission lands, the PRIMARY write home of
    ``WORK_PACKAGE_TASK`` is its topic branch, held by the coordination worktree once the
    root checkout moved back to ``create_return_branch``; the claim-written files
    (``meta.json``, the stamped WP prompt) live in that checkout's Mission directory
    (#7372). Every other Mission keeps the repository root checkout. The one probe is
    :func:`~specify_cli.coordination.planning_commit.planning_checkout_root`, shared with
    the planning-artifact commit and (through ``primary_partition_checkout``) the
    bookkeeping transaction.
    """
    from specify_cli.coordination.planning_commit import planning_checkout_root

    checkout: Path = planning_checkout_root(repo_root, feature_dir, mission_slug)
    return checkout


def _raise_if_claim_commit_head_mismatch(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    auto_commit: bool | None,
    feature_dir: Path | None = None,
) -> None:
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

    *feature_dir* (#7372) is the claim's Mission directory: when the checkout holding
    the destination (a default Mission's topic holder) contains it, that checkout's
    HEAD is the one judged, as the commit runs there (:func:`_claim_commit_checkout`).
    """
    if not auto_commit:
        return
    # The one status read door (ADR 2026-11-06-2, WP05): the declared source, so an
    # unmaterialized coordination worktree reads the committed coordination branch.
    from specify_cli.status import materialize_status, resolve_status_read

    snapshot = materialize_status(resolve_status_read(repo_root, mission_slug))
    current_lane = snapshot.work_packages.get(wp_id, {}).get("lane")
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
    commit_checkout = repo_root if feature_dir is None else _claim_commit_checkout(repo_root, feature_dir, mission_slug)
    observed_head = get_current_branch(commit_checkout)
    if observed_head == destination_ref:
        return
    mismatch = SafeCommitHeadMismatch(
        destination_ref=destination_ref,
        observed_head=observed_head or "<detached>",
        worktree_root=commit_checkout,
    )
    if ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(destination_ref):
        # Same type and ``error_code``; only the message gains the working remedy.
        mismatch.message += _protected_destination_hint(destination_ref, accepts_no_auto_commit=_NO_AUTO_COMMIT_OFFERED.get())
        mismatch.args = (mismatch.message,)
    raise mismatch


def claim_status_pair_paths(artifacts: Iterable[Path]) -> list[Path]:
    """The claim-written status pair (``status.events.jsonl``, ``status.json``) among collected status artifacts (#5673).

    The one selection both claim entry points (``implement`` and ``agent action implement``) commit through:
    ``tasks.md`` is collected beside the pair but no claim rewrites it, and neither claim rewrites the WP prompt
    except where :func:`claim_commit_paths` is told allocation stamped it.
    """
    return [path.resolve() for path in artifacts if is_status_state_path(path)]


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
    return claim_status_pair_paths(artifacts)


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


def _stage_claim_writes(
    repo_root: Path,
    wp_id: str,
    collect_paths: Callable[[], Iterable[Path]],
    resolve_checkout: Callable[[], Path] | None = None,
) -> None:
    """``--no-auto-commit``: stage the claim's own writes, so "staged only" is true (#3471).

    Stages the claim-commit list in the checkout the claim commit would run in --
    *resolve_checkout*'s answer (:func:`_claim_commit_checkout`: the repository root
    checkout, or a default Mission's topic holder, #7372), else *repo_root* -- and
    commits nothing. Resolving that checkout happens inside the best-effort ``try``
    too, and a path under ``.worktrees/`` relative to it is never staged (#2155): it
    is left unstaged and named in a warning, and the rest is staged. ``git add --force`` matches ``safe_commit``'s
    staging, so a claim file a consumer repository ignores is staged like the auto-commit
    would commit it, and git never stages part of the bundle before refusing an ignored
    path. Gathering the bundle runs here too: the claim has already landed, so a
    failure to gather or stage it (git or not) is reported, never hidden and never
    worded as a failed status update; the message then says the changes were left
    unstaged.
    """
    try:
        checkout = resolve_checkout() if resolve_checkout is not None else repo_root
        resolved_root = checkout.resolve()
        rel_paths = [path.relative_to(resolved_root).as_posix() for path in collect_paths() if path.is_relative_to(resolved_root) and path.exists()]
        nested = [rel for rel in rel_paths if Path(rel).parts[0] == WORKTREES_DIR]
        if nested:
            console.print(f"[yellow]Warning:[/yellow] Not staging paths inside another checkout (#2155): {', '.join(nested)}")
            rel_paths = [rel for rel in rel_paths if rel not in nested]
        if rel_paths:
            run_git(checkout, "add", "--force", "--", *rel_paths)
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
        _stage_claim_writes(repo_root, wp_id, gather, lambda: _claim_commit_checkout(repo_root, feature_dir, mission_slug))
        return

    commit_checkout = _claim_commit_checkout(repo_root, feature_dir, mission_slug)

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
            worktree_root=commit_checkout,
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
    transition failures into a printed error + ``typer.Exit(1)``.

    Inside :func:`dispatched_claim_identity` the claim records the dispatched
    structured actor and binding annotation (#7159); otherwise *effective_actor*
    verbatim. The claim triple keeps the bare agent either way.
    """
    import os as _os

    dispatched = _DISPATCHED_CLAIM_IDENTITY.get()
    try:
        return start_implementation_status(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            actor=dispatched.actor if dispatched is not None else effective_actor,
            workspace_context=f"{status_execution_mode}:{workspace_path}",
            execution_mode=status_execution_mode,
            repo_root=repo_root,
            # WP07/T026 (FR-004/FR-014): the claim triple rides the
            # planned -> claimed transition's policy_metadata sidecar; the
            # frontmatter pre-write mirror was removed in the #2816 cutover.
            policy_metadata=claim_policy_metadata(_os.getppid(), effective_actor),
            annotation_delta=dispatched.annotation_delta if dispatched is not None else None,
        )
    except WorkPackageClaimConflict as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except TransitionError as exc:
        console.print(f"[red]Error:[/red] Could not start implementation status: {exc}")
        raise typer.Exit(1) from exc
