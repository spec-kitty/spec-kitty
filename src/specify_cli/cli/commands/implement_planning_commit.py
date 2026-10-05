"""Planning-commit adapter for ``spec-kitty implement``: prints, exits, and runs the BookkeepingTransaction."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import typer
from specify_cli.cli.console import console

from specify_cli.cli.commands._commit_recipes import PROTECTED_PRIMARY_HINT, safe_commit_recipe
from kernel.git import GitCommandError
from specify_cli.core.errors import PlacementResolutionRequired
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.coordination import planning_commit as coordination_planning_commit
from specify_cli.coordination.planning_commit import PlanningPlacement
from specify_cli.cli.commands import implement_cores

# Bare name on purpose: ``test_wp_integrity_partition_call_shape`` recognises the flat/legacy
# primary-target arm by a ``Name`` call to this helper (a pure function, never patched).
from specify_cli.cli.commands.implement_cores import _commit_target_ref_for
from specify_cli.lanes import implement_support


# WP03 / S1192: the rich-markup error prefix, repeated across the
# planning-artifact commit helper this WP touches -- hoisted to one constant
# rather than restated at each ``console.print`` call site.
_RED_ERROR_PREFIX = "[red]Error:[/red] "


def _print_uncommitted_planning_artifacts(files_to_commit: list[str]) -> None:
    console.print("\n[cyan]Planning artifacts not committed:[/cyan]")
    for file_path in files_to_commit:
        console.print(f"  {file_path}")


def _print_planning_artifact_commit_instructions(
    current_branch: str,
    planning_branch: str,
    auto_commit: bool,
    feature_dir: Path,
    mission_slug: str,
) -> None:
    if current_branch != planning_branch:
        console.print(f"\n[red]Error:[/red] Planning artifacts must be committed on {planning_branch}.")
        console.print(f"Current branch: {current_branch}")
        raise typer.Exit(1)

    if auto_commit:
        return

    console.print("\n[yellow]Auto-commit disabled.[/yellow] Commit planning artifacts first:")
    # WP03 review (cycle 1, #4) correction: safe-commit does NOT force-add
    # gitignored paths at the CLI level -- its candidate-changes check and
    # directory expansion both use ``git status`` without ignored files, so a
    # gitignored path yields "No requested changes to commit" rather than
    # being force-staged. Dropping the old `git add -f` step here is still
    # correct, but for a DIFFERENT reason: migration m_0_12_1 removes
    # kitty-specs/ from .gitignore, so feature_dir is never ignored and needs
    # no force-add to be picked up.
    console.print(f"  {safe_commit_recipe([str(feature_dir)], f'chore: planning artifacts for {mission_slug}', planning_branch)}")
    console.print(f"  {PROTECTED_PRIMARY_HINT}")
    raise typer.Exit(1)


def _print_structural_planning_refusal(structural: list[implement_cores._PorcelainEntry]) -> None:
    """Print the #1598 fail-closed refusal for structural planning-artifact
    changes (deletions/renames/copies) that cannot be auto-committed to the
    coordination branch.

    ``BookkeepingTransaction.write_artifact`` is a write-only API that cannot
    remove an old path from the coordination branch, so silently committing only
    the additions would leave the branch incoherent (stale deleted/renamed-from
    artifacts). The claim must refuse; the operator commits the structural change
    to the coordination branch out-of-band, then re-runs the claim.
    """
    console.print(f"\n{_RED_ERROR_PREFIX}Uncommitted structural planning-artifact changes (deletions/renames) cannot be auto-committed to the coordination branch:")
    for entry in structural:
        console.print(f"  {entry.xy.strip() or entry.xy} {entry.path}")
    console.print("\nCommit these structural changes to the coordination branch yourself (e.g. `git rm`/`git mv` + commit), then re-run the claim.")


def _refuse_if_meta_json_demotion(
    repo_root: Path,
    artifact_source_dir: Path,
    mission_slug: str,
    files_to_commit: list[str],
) -> None:
    """FR-005 (#4979): REFUSE -- never silently commit -- an uncommitted
    ``meta.json`` that demotes the mission off its coordination branch.

    Hooks the staging DECISION seam: ``meta.json`` is PRIMARY-partitioned and
    only matters here when it is itself part of the dirty set already
    resolved by :func:`implement_cores.resolve_planning_artifact_staging`. This is
    defense-in-depth alongside the structural-change refusal above -- not a
    parallel commit gate.
    """
    meta_rel_path = coordination_planning_commit.meta_json_repo_relative_path(repo_root, artifact_source_dir)
    if meta_rel_path is None or meta_rel_path not in files_to_commit:
        return
    refusal = coordination_planning_commit.meta_json_demotion_refusal(
        repo_root,
        mission_slug,
        artifact_source_dir / coordination_planning_commit.META_JSON_FILENAME,
        meta_rel_path,
    )
    if refusal is None:
        return
    console.print(f"\n{_RED_ERROR_PREFIX}{refusal}")
    raise typer.Exit(1)


@contextlib.contextmanager
def _refuse_on_unreadable_planning_status(artifact_source_dir: Path) -> Iterator[None]:
    """Turn a failed ``git status`` probe into an implement refusal (fail closed).

    The staging cores read planning-artifact status through the git port, which
    raises :class:`~kernel.git.GitCommandError` rather than reading a failed
    probe as "nothing to commit". This git executor is the boundary that turns
    it into the same printed ``Error:`` + ``typer.Exit(1)`` shape as the other
    implement refusals, instead of a traceback.
    """
    try:
        yield
    except GitCommandError as exc:
        console.print(f"\n{_RED_ERROR_PREFIX}Could not read git status for the planning artifacts in {artifact_source_dir}, so the claim is refused: {exc}")
        raise typer.Exit(1) from exc


def _ensure_planning_artifacts_committed_git(
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    planning_branch: str,
    *,
    auto_commit: bool,
    placement: PlanningPlacement,
) -> None:
    """Ensure planning artifacts are committed on the feature planning branch.

    ``placement`` is the seam-owned planning placement
    (:func:`~specify_cli.coordination.planning_commit.resolve_planning_placement`):
    the coordination filter the staging and the commit arms use comes from
    :func:`~specify_cli.coordination.planning_commit.coordination_filter`,
    asked lazily after the structural check, so implement-claim never
    reconciles a primary↔coord split (#1816) and never derives a placement
    from ``meta.json`` itself (#5232).
    """
    current_branch = implement_support.git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    artifact_source_dir = coordination_planning_commit.planning_artifact_source_dir(repo_root, feature_dir, mission_slug)

    # Squad-B1 (#2464): fail closed on structural planning-artifact changes
    # BEFORE resolving the coordination-branch filter below (which can raise on
    # a broken topology). This restores the pre-degod ordering so a topology
    # fault never preempts the tailored structural-refusal message under a
    # double fault (structural change present AND topology resolution raising).
    with _refuse_on_unreadable_planning_status(artifact_source_dir):
        structural = implement_cores.detect_structural_planning_changes(repo_root, artifact_source_dir)
    if structural:
        _print_structural_planning_refusal(structural)
        raise typer.Exit(1)

    # #5232 / R-1b: the coord/flattened/primary decision is the seam's (C-005),
    # asked here, after the structural check, never earlier: a resolved
    # placement filters on its topology-gated ref, an unresolved one on the
    # mission's declared coordination branch (no topology gate, no probe).
    coord_branch_for_filter = coordination_planning_commit.coordination_filter(repo_root, mission_slug, placement, feature_dir=feature_dir)

    # T016: the staging DECISION (structural fail-closed check, #2222
    # vcs-lock exclusion, dedup, idempotency filtering) is a pure core in
    # implement_cores.py; this function is the git EXECUTOR -- it turns a
    # non-empty ``plan.structural`` into the fail-closed print+exit below and
    # an empty ``plan.files_to_commit`` into a silent no-op return, then does
    # the actual BookkeepingTransaction I/O.
    extra_file_paths = coordination_planning_commit.feature_dir_file_paths(repo_root, artifact_source_dir) if coord_branch_for_filter else []
    # FIX-M2-08: no longer thread ``placement_ref.ref`` in as ``verbatim_ref``.
    # The "PR #2662 squad fix" this parameter implemented compared EVERY
    # candidate (PRIMARY and COORD-residue alike) against the coordination
    # ref -- but ``_commit_planning_artifacts_transaction`` below was later
    # made partition-aware (write-path-integrity WP02/T008/FR-001, closing
    # #3371: PRIMARY files commit to ``planning_branch``, only COORD-residue
    # files commit to the coordination ref). Leaving ``verbatim_ref`` wired
    # here left the STAGING check comparing PRIMARY planning artifacts
    # (spec.md/plan.md/tasks.md/lanes.json/the D1-excluded dossier snapshot)
    # against the coordination branch even though the COMMIT never lands them
    # there -- exactly the read=HEAD/write=coord divergence #2653 already
    # named, just reintroduced on the read side. A coordination branch that
    # has not yet received a mission's planning-artifact history (the normal
    # case: coord is materialised early, planning artifacts land on primary)
    # then makes every already-committed primary file look "changed",
    # inflating ``files_to_commit`` with files that need no commit at all —
    # confirmed via ``tests/e2e/test_cli_smoke.py::test_full_workflow_sequence``
    # (spec.md/plan.md/tasks.md/lanes.json all reported "not committed" while
    # ``git status`` on the primary checkout showed them clean). Passing no
    # ``verbatim_ref`` restores the partition-aware comparison
    # (:func:`resolve_precondition_ref`: PRIMARY vs ``HEAD``, COORD-residue vs
    # the coordination ref) the pinned staging-core tests already assert as
    # canonical (``test_meta_json_on_coord_mission_resolves_to_head``,
    # ``test_dirty_spec_md_still_staged_against_head_on_coord_mission``,
    # INV-5 / #2533 / BLOCKER-2).
    with _refuse_on_unreadable_planning_status(artifact_source_dir):
        plan = implement_cores.resolve_planning_artifact_staging(
            repo_root,
            artifact_source_dir,
            coord_branch_for_filter,
            extra_file_paths,
            auto_commit=auto_commit,
        )

    files_to_commit = plan.files_to_commit
    if not files_to_commit:
        return

    _refuse_if_meta_json_demotion(repo_root, artifact_source_dir, mission_slug, files_to_commit)

    if plan.status_paths_to_commit:
        _print_uncommitted_planning_artifacts(files_to_commit)
        _print_planning_artifact_commit_instructions(
            current_branch,
            planning_branch,
            auto_commit,
            artifact_source_dir,
            mission_slug,
        )

    commit_msg = f"chore: planning artifacts for {mission_slug}\n\nAuto-committed by spec-kitty before creating the lane worktree for {wp_id}"

    _commit_planning_artifacts_transaction(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        planning_branch=planning_branch,
        files_to_commit=files_to_commit,
        commit_msg=commit_msg,
        placement=placement,
    )


def _run_planning_artifact_commit(
    *,
    repo_root: Path,
    mission_id: str,
    mission_slug: str,
    mid8: str,
    destination_ref: str,
    files: list[str],
    commit_msg: str,
    commit_to_primary_target: bool = False,
    enforce_partition: bool = False,
) -> None:
    """Execute ONE ``BookkeepingTransaction`` commit of *files* to *destination_ref*.

    Extracted from :func:`_commit_planning_artifacts_transaction` (T007) so
    the partition-aware caller below can run this once per PRIMARY/COORD-
    residue group without duplicating the transaction I/O + exception
    handling.

    ``commit_to_primary_target`` (WP02 / FR-001): threaded to
    :meth:`BookkeepingTransaction.acquire` so a PRIMARY-partition commit lands on
    the mission's own ``destination_ref`` (primary target branch) instead of
    being redirected onto the coordination branch. See ``acquire``'s docstring.

    ``enforce_partition`` (WP02 / FR-002 / T011): apply the Seam-A guard. Set for
    the coordination-topology partition commits (PRIMARY and COORD groups) and
    left ``False`` for the flat/legacy single-branch collapse where a mixed batch
    legitimately shares one branch.

    ``commit_idempotent`` (WP02 / FR-001 / T009): crash-recovery re-drive. If the
    process dies between the PRIMARY and COORD commits, re-invoking ``implement``
    re-runs BOTH groups; the group that already committed finds its staged paths
    byte-identical to HEAD and no-ops instead of hard-failing on an empty
    changeset. Recovery is per-partition idempotent re-drive, NOT cross-ref
    atomicity.
    """
    from specify_cli.coordination.transaction import BookkeepingTransaction

    if enforce_partition:
        coordination_planning_commit.guard_planning_commit_partition(files, destination_is_coord=not commit_to_primary_target)

    with BookkeepingTransaction.acquire(
        repo_root=repo_root,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mid8=mid8,
        destination_ref=destination_ref,
        operation=f"planning artifacts for {mission_slug}",
        commit_to_primary_target=commit_to_primary_target,
    ) as txn:
        for path_str in files:
            repo_path = Path(path_str)
            source_path = (repo_root / repo_path).resolve()
            if not source_path.exists():
                continue
            txn.write_artifact(repo_path, source_path.read_bytes())
        try:
            txn.commit_idempotent(commit_msg)
        except Exception as exc:  # noqa: BLE001 — surface as exit-1
            console.print(f"{_RED_ERROR_PREFIX}Failed to commit planning artifacts to {destination_ref}: {exc}")
            raise typer.Exit(1) from exc


def _commit_planning_artifacts_transaction(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    planning_branch: str,
    files_to_commit: list[str],
    commit_msg: str,
    placement: PlanningPlacement,
) -> None:
    """T016 git-executor tail: run the BookkeepingTransaction commit(s).

    Split out of :func:`_ensure_planning_artifacts_committed_git` so that
    function's own complexity stays scoped to the staging decision it drives;
    this helper owns only the transaction I/O (identifier resolution,
    destination-ref selection, ``BookkeepingTransaction`` write+commit,
    legacy-vs-coordination status prints).

    WP06 T026: route planning-artifact commits through BookkeepingTransaction
    so the commit lands on the mission's coordination branch (FR-005) and any
    write of status events is atomically reversible (FR-010). Legacy missions
    (created pre-WP03) have no ``coordination_branch`` in meta.json; the
    transaction's built-in legacy fallback (``_is_legacy_mission`` +
    ``_resolve_legacy_lane_destination`` in ``coordination/transaction.py``)
    overrides ``destination_ref`` with the actual checked-out lane branch, so
    the pre-flight policy gate, surgical rollback, and feature-status lock
    apply uniformly to coordination-branch and legacy missions alike (FR-027).

    WP03 / T011 / D11: no inline ``coord_branch if coord_branch else
    planning_branch`` grammar (the forbidden pattern named in
    contracts/seam-api.md's consumer table). The destinations come from the
    seam-owned ``placement`` (#5232): a resolved placement's ``ref`` is the ONE
    :class:`CommitTarget` planning artifacts AND status events resolve to
    (C-PLACE-1), and the seam's ``coordination_filter`` is the single
    coordination value the arms and the console lines use (for an unresolved
    placement, the mission's declared coordination branch -- #5232 shape 2). ``meta.json`` feeds identity only
    (mission_id / mid8 / the effective ids), never the destination.

    WP02 / T007 / FR-003 / INV-1 and write-path-integrity WP02 / T008 / FR-001:
    a coordination-topology commit partitions ``files_to_commit``
    (:func:`coordination_planning_commit.partition_files_for_commit`) into a
    PRIMARY group (committed to ``planning_branch``, the mission's target
    branch, honoured via ``commit_to_primary_target=True``) and a
    COORD-residue group (committed to the coordination ref) -- two
    transactions when both groups are non-empty, mirroring
    ``commit_router._group_files_by_partition``'s own two-group split. This
    closes the #3371 P0 where a PRIMARY ``lanes.json`` was committed onto the
    coordination branch and add/add-conflicted at lane allocation.

    #2648 (WP01) narrow-triple fail-close: this function has exactly FOUR
    placement/protection outcomes, and only ONE of them raises --

    - ``placement.resolved`` -- partition-aware commit: PRIMARY group to the
      target branch, COORD-residue group to ``placement.ref.ref`` (T008).
    - unresolved and no declared coordination branch -- flat/legacy
      mission, single transaction to ``planning_branch``.
    - unresolved, a declared coordination branch and
      ``is_protected(planning_branch)`` -- the NARROW TRIPLE: raises
      :class:`PlacementResolutionRequired` with
      :func:`~specify_cli.coordination.planning_commit.placement_resolution_remedy`.
      A real mission's ``planning_branch`` is never main/master (it is the
      mission's dedicated branch), so this only fires for a degenerate or
      torn-down topology; loud fail-close beats silently diverting the whole
      dirty-PRIMARY batch to the coordination branch (D11).
    - unresolved, a declared coordination branch and an unprotected
      ``planning_branch`` -- partition-aware split, COORD-residue group to
      that declared branch (T007).

    Only the narrow triple raises; the other three outcomes still commit.
    """
    # The identifier tuple (C-006) feeds identity only: mission_id, mid8 and the
    # effective ids. The destination comes from the seam's coordination_filter
    # below, never from this tuple (#5232).
    (
        _declared_coord_branch,
        mission_id,
        mid8,
        effective_mission_id,
        effective_mid8,
    ) = coordination_planning_commit.resolve_bookkeeping_transaction_identifiers(feature_dir, mission_slug, repo_root)

    # WP06 / T019 / C-PLACE-1 / R-1b: the coordination value the arms and the
    # console lines share is the seam's coordination filter. Resolved: ``None``
    # under a flattened/primary topology (the commit lands on
    # ``planning_branch``), the coord ref under coordination topology.
    # Unresolved: the mission's declared coordination branch, unprobed -- the
    # value the identifier read above already holds, so meta.json is read once.
    coord_branch = coordination_planning_commit.coordination_filter_with_declared(
        repo_root, mission_slug, placement, declared_coordination_branch=_declared_coord_branch
    )
    placement_ref = placement.ref

    is_legacy = not (coord_branch and mission_id and mid8)
    if is_legacy:
        console.print(
            f"\n[cyan]Auto-committing planning artifacts to {planning_branch}...[/cyan] "
            f"[dim](legacy path -- mission has no coordination_branch; "
            f"routed through BookkeepingTransaction for FR-020/FR-027 atomicity)[/dim]"
        )

    if placement.resolved and placement_ref is not None:  # ``ref`` is set exactly when resolved
        # write-path-integrity WP02 / T008 / FR-001: the seam-resolved
        # ``placement_ref.ref`` is the COORD ref under coordination topology.
        # Pre-fix this arm committed the WHOLE batch (PRIMARY ``lanes.json`` /
        # ``spec.md`` included) VERBATIM to that coord ref -- the #3371 P0 that
        # landed PRIMARY ``lanes.json`` on the coordination branch and
        # add/add-conflicted at lane allocation. Post-fix this arm partitions
        # the batch exactly like the unresolved partition arm below: the
        # PRIMARY group commits to the mission's target branch
        # (``_commit_target_ref_for(planning_branch)``, honoured by
        # ``commit_to_primary_target=True`` so the transaction does not redirect
        # it to coord), and the COORD-residue group commits to the coordination
        # ref (``placement_ref.ref``). Only the non-empty group(s) run
        # (skip-empty caller guard, mirroring the unresolved partition arm -- no empty
        # transaction). The Seam-A guard (``enforce_partition=True``) fails loud on
        # any partition mis-route on either leg (FR-002 / T011).
        primary_files, coord_files = coordination_planning_commit.partition_files_for_commit(files_to_commit)
        if primary_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=_commit_target_ref_for(planning_branch),
                files=primary_files,
                commit_msg=commit_msg,
                commit_to_primary_target=True,
                enforce_partition=True,
            )
        if coord_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=placement_ref.ref,
                files=coord_files,
                commit_msg=commit_msg,
                enforce_partition=True,
            )
    elif not coord_branch:
        # Flattened/legacy mission: no coordination branch at all -- the
        # historical single transaction to ``planning_branch``, routed
        # through the shared ``implement_cores._commit_target_ref_for`` expression (FR-005 ref
        # half) so this write-side destination and the read-side idempotency
        # compare cannot silently diverge (#2650 / WP04).
        _run_planning_artifact_commit(
            repo_root=repo_root,
            mission_id=effective_mission_id,
            mission_slug=mission_slug,
            mid8=effective_mid8,
            destination_ref=_commit_target_ref_for(planning_branch),
            files=files_to_commit,
            commit_msg=commit_msg,
        )
    elif ProtectionPolicy.resolve_for_mission(repo_root, mission_slug).is_protected(planning_branch):
        # #2648 (WP01) narrow-triple fail-close: the placement is unresolved,
        # the mission declares a coordination branch, and ``planning_branch`` is protected.
        # Pre-fix, this arm silently diverted the WHOLE dirty-PRIMARY batch to
        # the coordination branch instead of the (protected) target branch --
        # a genuinely-dirty PRIMARY artifact would never reach
        # ``planning_branch``. Raising here (rather than falling back to a
        # coord-only commit) refuses to commit partially or silently when the
        # canonical write placement cannot be resolved for a protected
        # planning branch. FR-018: the remedy text has one definition.
        raise PlacementResolutionRequired(coordination_planning_commit.placement_resolution_remedy(mission_slug))
    else:
        # T007: unresolved coordination placement -- partition-aware commit.
        # A genuinely-dirty PRIMARY artifact lands on ``planning_branch``
        # (never coordination); COORD-residue artifacts still land on the
        # coordination branch. Only the group(s) that are non-empty run.
        primary_files, coord_files = coordination_planning_commit.partition_files_for_commit(files_to_commit)
        if primary_files:
            # FR-005 ref half (#2650 / WP04): the PRIMARY-group destination
            # is derived from the SAME ``implement_cores._commit_target_ref_for`` expression the
            # read-side idempotency compare uses -- one source of the
            # cli-side PRIMARY ref, not two independently-written literals.
            # WP02 / FR-001: ``commit_to_primary_target=True`` so the transaction
            # commits this group to the target branch from the primary checkout
            # instead of redirecting it onto the coordination branch.
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=_commit_target_ref_for(planning_branch),
                files=primary_files,
                commit_msg=commit_msg,
                commit_to_primary_target=True,
                enforce_partition=True,
            )
        if coord_files:
            _run_planning_artifact_commit(
                repo_root=repo_root,
                mission_id=effective_mission_id,
                mission_slug=mission_slug,
                mid8=effective_mid8,
                destination_ref=str(coord_branch),
                files=coord_files,
                commit_msg=commit_msg,
                enforce_partition=True,
            )

    if is_legacy:
        console.print(f"[green]✓[/green] Planning artifacts committed to {planning_branch}")
    else:
        console.print(f"[green]✓[/green] Planning artifacts committed to coordination branch {coord_branch}")


def _planning_commit_branch(repo_root: Path, mission_slug: str, target_branch: str) -> str:
    """The branch planning artifacts must be committed on.

    For a single_branch mission that minted a mission branch (protected target)
    this is ``meta.mission_branch`` -- never the protected target the operator is
    deliberately NOT on. Every other mission keeps the resolved target branch.
    The rule itself is :func:`mission_runtime.single_branch_write_ref` (the one
    authority every write-branch site shares); this only supplies the values.
    """
    from mission_runtime import single_branch_write_ref

    from specify_cli.migration.backfill_topology import stored_topology

    meta = coordination_planning_commit.load_primary_anchored_mission_meta(repo_root, mission_slug)
    if meta is None:
        return target_branch
    return single_branch_write_ref(stored_topology(meta), meta.get("mission_branch"), target_branch)
