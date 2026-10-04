"""Unlocked entry preflight: everything that refuses before the lock is taken.

Resolves the run's status directory and the lanes manifest (including the
``--skip-lanes`` synthesis), refuses a protected status target before any branch
moves (``PROTECTED_BRANCH_REFUSED``), and runs the refuse-before-destroy
working-tree preflight (#4752/#4753). Nothing here mutates the repository (NFR-001).

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from collections.abc import Callable
import functools
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

from specify_cli.cli.console import console
from specify_cli.coordination.coherence import (
    is_toolchain_generated_churn,
)
from specify_cli.coordination.coord_seed import CoordSeedForkRefused
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from kernel.clock import now_utc_iso
from specify_cli.core.paths import (
    MissionMetaReadError,
    resolve_merge_target_branch,
)
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    DestructiveOpRefused,
    assert_checkout_on_target,
    assert_worktree_clean,
)
from specify_cli.git.ref_advance import worktrees_with_branch_checked_out
from specify_cli.consolidation.git_probes import (
    _has_branch_ref,
    _lane_already_integrated,
)
from specify_cli.lanes.compute import lane_created_branch as _created_lane_branch
from specify_cli.lanes.single_branch_landing import worktree_lanes

from specify_cli.lanes.persistence import require_lanes_json
from specify_cli.consolidation.preflight import (
    refuse_protected_status_target,
)
from specify_cli.consolidation.state import (
    ConsolidationState,
    get_state_path,
)
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.status import FeatureStatusLockTimeoutError
from mission_runtime import (
    ActionContextError,
    MissionArtifactKind,
    PlacementSeam,
)
from specify_cli.consolidation.run_state import (
    _created_lane_worktree,
    _stored_topology_for,
)


def _resolve_coord_worktree_for_preflight(
    main_repo: Path,
    mission_slug: str,
    primary_meta_dir: Path,
) -> Path | None:
    """Resolve the coordination worktree path for the T010 preflight, purely.

    Mirrors ``_is_coord_topology_mission``'s ``coordination_branch``-presence
    signal (rather than inventing a second coord-topology detector) so
    preflight and cleanup never disagree about whether a coordination
    worktree is in play (INV-2). Returns ``None`` for a non-coord-topology
    mission, or a coord mission with no recorded ``mid8`` (legacy/never
    created) — in either case there is no coordination worktree to guard.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(primary_meta_dir) or {}
    if "coordination_branch" not in meta:
        return None
    mid8 = str(meta.get("mid8", "")).strip()
    if not mid8:
        return None
    # ``coordination.workspace`` sits behind a repo-wide ``follow_imports =
    # "skip"`` mypy override (pyproject.toml), so the imported staticmethod's
    # declared ``Path`` return type is erased to ``Any`` at this call site.
    # Re-wrapping in ``Path(...)`` (a real, idempotent no-op on the already-
    # ``Path`` runtime value) restores a concrete static type instead of
    # suppressing the check.
    return Path(CoordinationWorkspace.worktree_path(main_repo, mission_slug, mid8))


def _pre_mutation_safety_preflight(
    main_repo: Path,
    mission_slug: str,
    target_branch: str,
    lanes_manifest: LanesManifest,
    primary_meta_dir: Path,
    *,
    remove_worktree: bool,
    teardown_coordination: bool,
    resume_state: ConsolidationState | None = None,
) -> None:
    """Refuse-before-destroy preflight for #4752/#4753 (WP03/T010).

    Called from the OUTER :func:`_run_lane_based_consolidation`, BEFORE
    :func:`_run_lane_based_consolidation_locked` runs its phase list — in particular
    before ``_phase_merge_lanes`` (which git-merges lanes into the mission
    branch) and ``_phase_bake_and_pre_target_done`` (which commits a
    done-event on the coord branch). This is the only placement where a
    refusal is byte-identical to pre-invocation (NFR-001): nothing in the
    locked flow has mutated anything yet. Because both a fresh merge and a
    ``--resume`` merge route through the same outer function, ``--resume``
    honors this preflight identically (US1 AC4) with no separate wiring.

    Checks, in order:

    1. The primary checkout is on ``target_branch`` and clean
       (``MERGE_UNSAFE_PRIMARY_OFF_TARGET`` / ``MERGE_UNSAFE_PRIMARY_DIRTY`` —
       FR-001/FR-002/US1 AC1-2).
    2. Every lane worktree is clean (FR-003/US2 AC1) — unless
       ``remove_worktree`` is False (worktree retention in effect), in which
       case a dirty lane worktree is the existing retention path's concern
       (kept, never force-removed) rather than a preflight refusal (US2 AC2).
       This mirrors exactly the gate ``_phase_cleanup_worktrees_and_branches``
       already applies to its own removal loop.
    3. The coordination worktree, when the mission is coord-topology AND the
       coupled coord teardown is actually going to run (``teardown_coordination``
       — ``delete_branch AND remove_worktree``, #3131 INV-2), is clean
       (FR-004/US2 AC4). Gating on ``teardown_coordination`` rather than
       ``remove_worktree`` alone matches ``_cleanup_mission_branch_and_coordination``'s
       real gate for a coord mission, so a partial-retention merge that will
       never touch the coord triple is never refused for a dirty coord
       worktree it was never going to disturb (NFR-002 no-regression).
    4. On a ``--resume`` (``resume_state`` is the persisted merge record, #5613), no
       OTHER worktree that has the mission branch checked out is dirty in a way this run
       would trip over (:func:`_assert_mission_checkouts_clean`): any dirt while a lane
       remains to merge, else only dirt that reads an unrefreshed advance in reverse.
       Runs right after the primary checkout leg, independent of retention; a retained
       worktree that is dirty but does not lag still passes (NFR-002, as in leg 3).

    Any :class:`~specify_cli.git.destructive_guard.DestructiveOpRefused` raised
    here propagates to the caller, which aborts the merge fail-closed before
    the lock is acquired and before any mutation.
    """
    # WP10 integration (C-3 / #4978): thread the STORED topology so the pre-mutation
    # dirty gate never resets a coord-partition-KIND artifact as residue on a
    # LANES / SINGLE_BRANCH mission.
    is_residue = functools.partial(
        is_toolchain_generated_churn,
        mission_slug=mission_slug,
        topology=_stored_topology_for(primary_meta_dir),
    )

    from specify_cli.lanes.single_branch_landing import expected_consolidate_checkout

    assert_checkout_on_target(main_repo, expected_consolidate_checkout(main_repo, lanes_manifest, target_branch))
    assert_worktree_clean(
        main_repo,
        is_residue=is_residue,
        error_code=MERGE_UNSAFE_PRIMARY_DIRTY,
    )

    if resume_state is not None:
        _assert_mission_checkouts_clean(main_repo, lanes_manifest, resume_state, is_residue=is_residue)

    if not remove_worktree:
        return

    for lane in worktree_lanes(lanes_manifest):
        # lane-branch-naming-authority-01M3EVC4 WP02 (T033): the CREATED
        # worktree (never a Mission-identity form) — the same placement
        # ``_phase_cleanup_worktrees_and_branches`` removes.
        wt_path = _created_lane_worktree(main_repo, mission_slug, lane.lane_id)
        if wt_path.exists():
            # #4753 Finding A: this worktree is removal-destined, so an
            # untracked-only operator file must block just as a tracked edit
            # does — the obstruction-only default is correct for a
            # ``reset --hard`` (``advance_branch_ref``), not a
            # ``git worktree remove --force``.
            assert_worktree_clean(wt_path, is_residue=is_residue, treat_untracked_as_dirty=True)

    if not teardown_coordination:
        return

    # WP17 (FR-009c, #5023): refuse BEFORE any mutation (NFR-001) when the
    # decisions ledger exists only on the coordination branch this merge is
    # about to tear down -- the bookkeeping projection excludes PRIMARY
    # kinds, so it would otherwise be silently lost.
    _refuse_if_coordination_ledger_unrepaired(main_repo, mission_slug)

    coord_worktree = _resolve_coord_worktree_for_preflight(main_repo, mission_slug, primary_meta_dir)
    if coord_worktree is not None and coord_worktree.exists():
        assert_worktree_clean(coord_worktree, is_residue=is_residue, treat_untracked_as_dirty=True)


def _assert_mission_checkouts_clean(
    main_repo: Path,
    lanes_manifest: LanesManifest,
    state: ConsolidationState,
    *,
    is_residue: Callable[[str], bool],
) -> None:
    """Resume leg of :func:`_pre_mutation_safety_preflight`: no worktree on the mission branch blocks the resume (#5613).

    Lane consolidation advances the mission branch and resyncs every worktree that has it
    checked out (the coordination worktree, or a mission worktree on a ``lanes`` mission);
    ``advance_branch_ref`` refuses a dirty one MID-RUN, after the lock and the merge record
    exist. A run interrupted between that ref advance and the resync leaves such a worktree
    behind its own HEAD, so a resume must see it here, before any mutation, where the lag
    can be recovered in place or refused with lag-aware advice. The repository root checkout
    has its own leg and is skipped. Obstruction-only untracked semantics: this worktree is
    reset, not removed.

    A dirty worktree is refused when a lane still remains to merge (the advance would
    refuse it mid-run) or when its dirt reads an unrefreshed advance in reverse
    (:func:`~specify_cli.consolidation.preflight.has_unrefreshed_head_advance` against the
    persisted pre-mutation tips). Otherwise it is genuine local work in a worktree this
    resume no longer advances, so it passes exactly as on a fresh merge (NFR-002). With no
    recorded tip the absence of a lag cannot be proven and the dirt is refused.

    Raises:
        DestructiveOpRefused: a worktree on the mission branch is dirty as described.
        RefAdvanceError: the worktrees could not be enumerated.
    """
    from specify_cli.consolidation.preflight import has_unrefreshed_head_advance

    mission_branch = lanes_manifest.mission_branch
    root = main_repo.resolve()
    anchors = {sha for sha in (state.pre_mutation_refs.get(mission_branch), state.pre_mutation_coord_sha) if sha}
    for checkout in worktrees_with_branch_checked_out(main_repo, mission_branch):
        if checkout.resolve() == root:
            continue
        try:
            assert_worktree_clean(checkout, is_residue=is_residue)
        except DestructiveOpRefused:
            lags = not anchors or any(has_unrefreshed_head_advance(checkout, base_sha=sha) for sha in anchors)
            if lags or _lane_remains_to_merge(main_repo, lanes_manifest, state):
                raise


def _lane_remains_to_merge(main_repo: Path, lanes_manifest: LanesManifest, state: ConsolidationState) -> bool:
    """True iff the resumed run may still advance the mission branch by merging a lane (#5613).

    The same skip rule ``_phase_merge_lanes`` applies, read before the lock: a lane is done
    when its branch is already integrated into the mission branch, or its branch is gone and
    every WP it carries is recorded complete. Anything else counts as remaining, including a
    lane whose branch cannot be read and a fully-canceled lane with no branch (the canceled
    set is not resolved this early), so the answer errs toward the stricter refusal.
    """
    completed = set(state.completed_wps)
    for lane in worktree_lanes(lanes_manifest):
        branch = _created_lane_branch(lanes_manifest, lane.lane_id)
        if _lane_already_integrated(main_repo, branch, lanes_manifest.mission_branch):
            continue
        if _has_branch_ref(main_repo, f"refs/heads/{branch}") or not lane.wp_ids or not completed.issuperset(lane.wp_ids):
            return True
    return False


def _refuse_if_coordination_ledger_unrepaired(main_repo: Path, mission_slug: str) -> None:
    """WP17 preflight leg of :func:`_pre_mutation_safety_preflight` (FR-009c).

    Raises :class:`DestructiveOpRefused` with ``error_code=
    "COORDINATION_LEDGER_UNREPAIRED"`` -- the SAME code
    ``coordination/teardown.py`` raises for the coupled discard/close/abort
    paths (NFR-004 single authority over the detection; this is a distinct
    refusal family/exception type for the consolidation preflight's own
    established fail-closed mechanism). Late-imported so the heavy
    ``decisions.fork`` dependency chain is paid only when this leg actually
    runs (``teardown_coordination`` true).
    """
    from specify_cli.decisions.fork import coordination_only_ledger, ledger_is_coordination_only  # noqa: PLC0415

    ledger = coordination_only_ledger(main_repo, mission_slug)
    if not ledger_is_coordination_only(ledger):
        return
    raise DestructiveOpRefused(
        error_code="COORDINATION_LEDGER_UNREPAIRED",
        remediation=(
            f"Mission {mission_slug!r}'s decisions ledger (decisions/index.json / DM-*.md) exists only "
            f"on the coordination branch. Run `spec-kitty doctor decisions --mission {mission_slug} "
            "--repair` to copy it into the PRIMARY ledger, then retry."
        ),
    )


def _synthesize_no_lane_manifest(
    *,
    main_repo: Path,
    mission_slug: str,
    status_feature_dir: Path,
    primary_meta_dir: Path,
    target_override: str | None,
) -> LanesManifest:
    """T021 (FR-012, FOLD 1): synthesize a NO-LANE manifest for a direct-on-
    target mission under ``--skip-lanes`` when ``lanes.json`` is genuinely
    absent.

    Reuses the existing, well-tested ``is_planning_artifact_only`` skip-the-
    branch-merge machinery rather than inventing a parallel phase-skip path:
    the target branch already carries the WPs' deliverables (the sanctioned
    direct-on-target fallback — no separate mission branch was ever created),
    which is exactly the precondition ``is_planning_artifact_only`` recognizes.
    The synthesized manifest's single lane uses the canonical planning-lane id
    (:data:`~specify_cli.lanes.compute.PLANNING_LANE_ID`) so every downstream
    phase that already special-cases a planning-artifact-only mission
    (``_phase_merge_lanes``, ``_phase_mission_to_target``,
    ``_phase_bake_and_pre_target_done``) takes its proven already-on-target
    branch, instead of attempting to merge the target branch into itself.

    ``mission_branch`` is set equal to the resolved target branch — there is
    no separate mission branch to merge FROM on this path. WP ids are read off
    the mission's reduced status snapshot (the same mission's WPs the T007
    precondition will evaluate), never re-derived from a different source.
    """
    from specify_cli.lanes.compute import PLANNING_LANE_ID
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.status import read_events, reduce

    identity = resolve_mission_identity(primary_meta_dir)
    target_branch, _source = resolve_merge_target_branch(main_repo, mission_slug, target_override)
    snapshot = reduce(read_events(status_feature_dir))
    work_packages = snapshot.work_packages if hasattr(snapshot, "work_packages") else {}
    wp_ids = tuple(sorted(work_packages.keys()))
    lane = ExecutionLane(
        lane_id=PLANNING_LANE_ID,
        wp_ids=wp_ids,
        write_scope=(),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=identity.mission_id,
        mission_branch=target_branch,
        target_branch=target_branch,
        lanes=[lane],
        computed_at=now_utc_iso(),
        computed_from="skip-lanes direct-on-target synthesis (T021, FR-012)",
    )


def _refuse_protected_status_target_or_continue(main_repo: Path, mission_slug: str, lanes_manifest: LanesManifest, canonical_id: str) -> None:
    """#5385: refuse, before any branch moves, a consolidation whose ``done`` bookkeeping the policy refuses.

    Pre-lock, so a refusal writes no merge record (NFR-001). The verdict is the
    workflow mutation policy's own (``refuse_protected_status_target``), rendered
    with its ``error_code``, message and ``next_step``.

    When a merge record for this mission already exists (a ``--resume``, or a
    re-run after a crash), THIS run moved nothing, but an earlier attempt may
    have: the refusal then points at ``consolidate --abort`` (which restores the
    recorded snapshot) instead of claiming no branch moved.
    """
    try:
        verdict = refuse_protected_status_target(main_repo, mission_slug, lanes_manifest)
    except (ActionContextError, MissionMetaReadError) as exc:
        console.print(f"[red]Error:[/red] Cannot probe the done bookkeeping policy: {exc}. Fix the mission's meta.json / status surface before merging.")
        raise typer.Exit(1) from exc
    if verdict is None:
        return
    console.print(f"[red]Error:[/red] {verdict.error_code}: {verdict.message}")
    console.print(f"  Next step: {verdict.next_step}")
    console.print(_protected_refusal_footer(get_state_path(main_repo, canonical_id).exists()), markup=False)
    raise typer.Exit(1)


_REFUSED_BEFORE_ANY_MOVE = "Consolidation refused before any branch moved."


_REFUSED_WITH_EARLIER_RECORD = (
    "Consolidation refused; this run moved no branch, but an earlier attempt may have. Run `spec-kitty consolidate --abort` to restore the branches it recorded."
)


def _protected_refusal_footer(merge_record_exists: bool) -> str:
    """The last line of an up-front protected-target refusal (#5385)."""
    return _REFUSED_WITH_EARLIER_RECORD if merge_record_exists else _REFUSED_BEFORE_ANY_MOVE


def _require_lanes_json_naming_mission_branch(main_repo: Path, lanes_read_dir: Path) -> LanesManifest:
    """``require_lanes_json``, but a missing manifest names the branch that holds the mission.

    A protected single_branch mission's files exist only on its minted branch; from
    the target (or any other checkout) the stock remedy -- ``finalize-tasks`` /
    ``doctor mission-state --fix`` -- is wrong. When some ``kitty/*`` branch
    carries the manifest, say so.
    """
    from specify_cli.lanes.persistence import MissingLanesError
    from specify_cli.lanes.single_branch_landing import branch_holding_path

    try:
        return require_lanes_json(lanes_read_dir)
    except MissingLanesError as exc:
        try:
            rel = (lanes_read_dir / "lanes.json").relative_to(main_repo).as_posix()
        except ValueError:
            raise exc from None
        holder = branch_holding_path(main_repo, rel)
        if holder is None:
            raise
        raise MissingLanesError(
            f"lanes.json is not on the current checkout, but branch {holder!r} carries this mission "
            f"(a protected single_branch mission lives on its mission branch). Run `git checkout {holder}` "
            "and re-run `spec-kitty consolidate` from there."
        ) from exc


_MERGE_ABORT_NOTICE = "[yellow]Merge aborted before any state change.[/yellow]"


def _abort_before_state_change(exc: Exception, hint: str) -> typer.Exit:
    """Render *exc*'s own remediation plus a clean-no-op notice; return the ``Exit(1)`` to raise."""
    console.print(f"[red]Error:[/red] {exc}")
    console.print(f"{_MERGE_ABORT_NOTICE} {hint}")
    return typer.Exit(1)


def _resolve_run_status_dir(seam: PlacementSeam) -> Path:
    """The Mission dir the run's status writes and reads land in (ruling Q4, FR-003).

    Resolved through the WRITE accessor, so the single authority also
    establishes the surface: a pre-fix EMPTY coordination surface is seeded
    once and an UNMATERIALIZED surface with a local head is materialized. This
    runs in the UNLOCKED pre-phase of ``_run_lane_based_consolidation``, before
    the global merge lock and before both pre-mutation captures
    (``_resolve_pre_mutation_coord_sha`` and
    ``rollback.capture_pre_mutation_snapshot``), so a seed commit is part of the
    pre-mutation state and a later FAIL/REFUSE rollback never undoes it. The
    seed takes the status lock outside the merge lock, so lock ordering has no
    inversion (the locked driver's status writes re-enter the reentrant lock).

    Fail closed, but NOT with a traceback, for every write-location refusal:
    nothing has been mutated, so each one is a clean no-op abort that renders
    the exception's own remediation (its ``next_step``, already in ``str(exc)``).
    """
    try:
        return seam.write_dir(MissionArtifactKind.STATUS_STATE).path
    except CoordinationBranchDeleted as exc:
        raise _abort_before_state_change(
            exc,
            "Recover the mission's status authority, then re-run [bold]spec-kitty consolidate[/bold].",
        ) from exc
    except CoordinationWorktreeUnmaterialized as exc:
        # Raised only for a REMOTE-ONLY coordination branch (#4970): a local head is
        # materialized by ``write_dir`` itself.
        raise _abort_before_state_change(
            exc,
            "Create the local coordination branch from its remote "
            "(for example [bold]git branch <coordination-branch> <remote>/<coordination-branch>[/bold]), "
            "then re-run [bold]spec-kitty consolidate[/bold].",
        ) from exc
    except CoordSeedForkRefused as exc:
        raise _abort_before_state_change(
            exc,
            "Inspect the diverged event logs with [bold]spec-kitty doctor decisions[/bold], then re-run [bold]spec-kitty consolidate[/bold].",
        ) from exc
    except FeatureStatusLockTimeoutError as exc:
        raise _abort_before_state_change(
            exc,
            "Wait for the other status writer to finish, then re-run [bold]spec-kitty consolidate[/bold].",
        ) from exc
