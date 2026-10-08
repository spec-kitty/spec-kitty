"""Teardown phase: lane worktrees and branches, then the coordination triple.

Lane worktree removal (through the destructive-op guard) and lane branch deletion,
the topology-aware mission/coordination cleanup, the coordination triple
(worktree -> compare-and-swap branch delete -> marker flatten, INV-2 / #3926),
the projection teardown gate construction, and the late-landing projection of
coordination commits that arrived during teardown (#5570).

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

import functools
import time

from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.coordination.coherence import (
    is_toolchain_generated_churn,
)
from specify_cli.core.git_ops import run_command
from kernel.git import GitCommandError
from specify_cli.git.bookkeeping_commit import (
    commit_merge_bookkeeping,
)
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.git.ref_advance import (
    RefDeleteError,
    RefDeleteMismatchError,
    delete_branch_ref,
)
from specify_cli.git.destructive_guard import (
    guarded_worktree_remove,
)
from specify_cli.consolidation.git_probes import _paths_have_status_changes
from specify_cli.lanes.single_branch_landing import worktree_lanes

# Shared FR-004/FR-009 "fully canceled" predicate and lane-branch composer
# (single canonical home in ``lanes.compute`` — see its docstrings), imported
# under the historical private names this module's call sites use.
from specify_cli.lanes.compute import lane_created_branch as _created_lane_branch
from specify_cli.consolidation._constants import (
    COORD_MOVED_AFTER_LANDING_SUFFIX,
    logger,
)
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_commit_shas,
    _post_checkpoint_mission_paths,
    _project_status_bookkeeping_to_target,
    _resolve_ref_sha,
    assert_alias_events_preserved,
)
from specify_cli.consolidation.state import (
    save_state,
)
from specify_cli.consolidation.workspace import _worktree_removal_delay
from specify_cli.consolidation.run_state import (
    _created_lane_worktree,
    CoordMovedAfterLanding,
    CoordinationTeardownError,
    _MergeRunState,
    _is_coord_topology_mission,
    _stored_topology_for,
)


def _flatten_coordination_metadata_after_branch_delete(run: _MergeRunState) -> None:
    """issue #3086: clear the coordination marker once the coord branch is gone.

    ``spec-kitty consolidate --delete-branch`` (the default) deletes a Mission's
    coordination branch (``kitty/mission-<slug>``) from git but, before this fix,
    left the paired ``coordination_branch`` key in
    ``kitty-specs/<slug>/meta.json``. Every later command routing through
    ``resolve_status_surface_with_anchor`` then hit ``CoordState.DELETED`` and
    raised ``CoordinationBranchDeleted`` — the deliberate #1848 data-loss
    hard-fail — a 100% crash on merged coord missions.

    This mirrors the canonical flatten already performed by
    ``spec-kitty mission close --discard`` and ``doctor coordination --fix``:
    all three converge on the single
    :func:`~specify_cli.mission_metadata.flatten_coordination_metadata`
    primitive (#3219 / FR-015 / D-PLAN-17), rather than each call site
    inventing its own copy of the pop-``coordination_branch`` / pop-``topology``
    / set-``flattened`` mutation set.

    **Known residual (T054, verdict-seam-write-unification-01KZ9Q35 WP10):**
    this flatten (and its bookkeeping commit) runs in
    ``_phase_cleanup_worktrees_and_branches``, which executes AFTER
    ``_phase_push``. On a ``spec-kitty consolidate --push``, the flatten bookkeeping
    commit therefore lands LOCAL-ONLY -- it is never pushed to origin, so
    origin/target keeps the stale ``coordination_branch`` key even though the
    local target branch is correctly flattened. Verified as a real, pre-existing
    ordering gap (not introduced or regressed by WP10's convergence); fixing it
    would mean either re-ordering the two phases or pushing a second time after
    cleanup, both out of WP10's scope (a lane-owned convergence WP, not a merge
    phase-ordering change) -- tracked as a follow-up rather than silently
    expanded into here.

    Placement & ordering. This lives in the ``delete_branch`` gate, co-located
    with the branch deletion, so the marker is cleared **iff** the branch it
    names is deleted — the two mutations stay atomic. It is deliberately NOT
    folded into the earlier, unconditional ``_phase_commit_and_assert``: doing so
    would (a) require duplicating this gate's ``delete_branch`` guard into a phase
    that must stay unconditional, and (b) clear the marker *before* the branch is
    deleted, so a failed deletion would strand the inverse inconsistency (a
    cleared marker with a still-live branch). It still runs after the lane->target
    merge-driver reconciliation (which treats ``coordination_branch`` as a
    *theirs-authoritative* planning key, ``consolidation/drivers.py``), so the clear
    is the last writer regardless.

    The edit is persisted through the same protected-flow bookkeeping-commit seam
    the merge uses for its other meta.json mutations. A commit failure here is
    logged and swallowed (fail-open), never raised: this runs in the post-push
    cleanup phase, the on-disk flatten has already cleared ``coordination_branch``
    (so #3086 stays fixed), and aborting an otherwise-complete merge — or
    restoring the pre-flatten snapshot, which would re-strand the marker — is
    worse than a locally-dirty meta.json (recoverable via
    ``spec-kitty doctor coordination --fix``).

    A non-coord Mission (``SINGLE_BRANCH`` / ``LANES``) or an already-flattened
    one carries no ``coordination_branch`` key, so this is an idempotent no-op
    that leaves ``topology`` / ``flattened`` untouched.
    """
    from specify_cli.mission_metadata import flatten_coordination_metadata, load_meta_or_empty

    feature_dir = run.target_feature_dir
    meta = load_meta_or_empty(feature_dir)
    if "coordination_branch" not in meta:
        return

    # Canonical three-mutation flatten (#3219 / FR-015 / D-PLAN-17), converged
    # onto the ONE shared primitive -- parity with ``doctor coordination --fix``
    # / ``mission close --discard``, and closes the double-write window the
    # former two-call (clear + separate topology/flattened write) shape here
    # invited. ``coordination_branch`` presence above means meta.json exists,
    # so ``flatten_coordination_metadata`` cannot raise here.
    flatten_coordination_metadata(feature_dir)

    meta_path = feature_dir / "meta.json"
    if not _paths_have_status_changes(run.main_repo, [meta_path]):
        return

    # Fail-open, unlike ``_phase_commit_and_assert``'s restore-and-reraise: the
    # on-disk flatten already cleared ``coordination_branch`` (so #3086 stays
    # fixed even if the commit does not land), and restoring the pre-flatten
    # snapshot would re-strand the marker. A recovered commit (``commit_sha`` set)
    # actually landed and is a success; every other failure is logged, not raised.
    try:
        commit_merge_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=run.main_repo,
            mission_slug=run.mission_slug,
            branch=run.lanes_manifest.target_branch,
            message=(f"chore({run.mission_slug}): flatten coordination metadata after branch deletion (#3086)"),
            paths=(meta_path,),
        )
    except SafeCommitRecoveryFailed as exc:
        if exc.commit_sha is None:
            logger.warning(
                "Flatten bookkeeping commit did not land for %s (%s); meta.json is "
                "flattened on disk but may be uncommitted — recover with "
                "`spec-kitty doctor coordination --fix`",
                run.mission_slug,
                exc,
            )
    except Exception as exc:
        # Fail-open: never abort a completed merge for a bookkeeping-commit failure.
        logger.warning(
            "Flatten bookkeeping commit failed for %s (%s); meta.json is flattened "
            "on disk but may be uncommitted — recover with "
            "`spec-kitty doctor coordination --fix`",
            run.mission_slug,
            exc,
        )


def _mission_branch_tip(run: _MergeRunState) -> str | None:
    """The mission/coordination branch's current tip SHA, or ``None`` when it does not resolve."""
    return _resolve_ref_sha(run.main_repo, f"refs/heads/{run.lanes_manifest.mission_branch}") or None


def _tip_moved_teardown_error(branch: str, exc: RefDeleteMismatchError, *, coordination: bool = True) -> CoordMovedAfterLanding:
    """Operator-facing refusal for a mission branch that moved past the tip teardown approved (#5570).

    A coordination mission names the branch, the intact marker and the ``--resume`` that projects
    the late commit(s) and finishes teardown. A mission without coordination topology has no
    coordination branch, marker or projection to resume, so it is called the *mission branch* and
    the operator is told to land the commit(s) and delete the branch themselves.
    """
    moved = (exc.actual_sha or "")[:12]
    approved = exc.expected_sha[:12]
    review = f"Review the commit(s) with `git log {approved}..{branch}`"
    if not coordination:
        return CoordMovedAfterLanding(
            f"mission branch {branch!r} moved to {moved} while teardown was deleting it (it was at {approved}; "
            f"a commit landed during teardown); it was NOT deleted. {review}; if they belong on the target, "
            f"land them there, then delete the branch yourself.{COORD_MOVED_AFTER_LANDING_SUFFIX}"
        )
    return CoordMovedAfterLanding(
        f"coordination branch {branch!r} moved to {moved} after teardown approved "
        f"{approved} (a commit landed during teardown); it was NOT deleted and the mission's "
        f"coordination marker was left intact. {review}, then run `spec-kitty consolidate --resume`: it projects "
        "the late commit(s) onto the target, deletes the branch only if it has not moved again, and finishes teardown."
        f"{COORD_MOVED_AFTER_LANDING_SUFFIX}"
    )


def _delete_mission_branch(run: _MergeRunState, expected_tip: str | None = None) -> bool:
    """Delete the mission/coordination branch from git, if it exists.

    Returns whether the branch is gone afterwards — deleted now, or already
    absent. The delete is a compare-and-swap at ``expected_tip`` (#5570): the
    tip the teardown gate approved, or — when no gate ran — the tip read at the
    start of the teardown phase; ``None`` reads it now. A commit that landed
    after that tip survives (the branch is kept) and the refusal is raised as
    :class:`CoordinationTeardownError`, never restored or force-deleted here.

    Git refuses to drop a branch that is checked out in a worktree (#3926); the
    typed refusal is reported as ``False`` rather than assumed to be success,
    so the caller that couples this to the rest of the coord triple gets the
    answer.

    #5100 T020 safety fix: an UNPROTECTED single_branch mission's manifest
    carries ``mission_branch == target_branch`` (contracts/single-branch-
    execution.md's consolidate table -- bookkeeping only, no branch merge or
    deletion). Without this guard, the delete would remove the mission's
    TARGET branch itself (e.g. ``main``) the moment ``run.delete_branch`` is
    True -- the single most dangerous consequence of
    ``lanes_manifest.mission_branch`` being unconditionally derived
    ``kitty/mission-...`` for every other topology previously made
    unreachable. Returns ``True`` (nothing to delete, target is untouched)
    rather than attempting it.

    Raises:
        CoordinationTeardownError: the branch moved past ``expected_tip``.
    """
    lanes_manifest = run.lanes_manifest
    branch = lanes_manifest.mission_branch
    if branch == lanes_manifest.target_branch:
        return True
    tip = expected_tip or _mission_branch_tip(run)
    if tip is None:
        logger.debug("Mission branch %s does not exist, skipping deletion", branch)
        return True
    try:
        delete_branch_ref(run.main_repo, branch, tip)
    except RefDeleteMismatchError as exc:
        if exc.actual_sha is None:
            # The post-failure probe found no ref at all, so the branch IS gone and the
            # postcondition (absent) holds. If someone else removed it, that was not this
            # delete: it never ran against a moved or surviving tip.
            return True
        raise _tip_moved_teardown_error(branch, exc, coordination=_is_coord_topology_mission(run)) from exc
    except RefDeleteError as exc:
        logger.warning("Mission branch %s was not deleted: %s", branch, exc)
        return False
    return True


def _carry_pass_anchor_over_own_commit(run: _MergeRunState, commit_sha: str) -> None:
    """Carry the reconciliation PASS anchor over a target commit THIS run just made (#5570).

    The anchor (:func:`_resume_reconciliation_already_passed`) is an exact-tip compare-and-swap.
    Teardown's persist-before-destroy leg (retrospective) and the late coordination landing each
    add a bookkeeping commit to the target AFTER the gate passed, so without a carry a ``--resume``
    would no longer recognise the verified landing and re-run the claim against lane branches that
    are already gone.

    ``commit_sha`` is the SHA the commit step itself returned, never a fresh read of the target
    tip: a foreign commit landing next to ours must not be stamped verified. The anchor moves only
    when that commit is still the target tip AND its first parent is the current anchor (so it
    sits directly on the verified landing). Anything else leaves the anchor alone, and the next
    resume runs the full reconciliation (fail-closed).
    """
    anchor = run.state.reconciliation_passed_target_sha
    if not anchor or not commit_sha:
        return
    target = run.lanes_manifest.target_branch
    if _resolve_ref_sha(run.main_repo, target) != commit_sha or _resolve_ref_sha(run.main_repo, f"{commit_sha}^") != anchor:
        return
    run.state.reconciliation_passed_target_sha = commit_sha
    save_state(run.state, run.main_repo)


def _refuse_unbuildable_late_window(run: _MergeRunState) -> None:
    """Fail closed when a resumed teardown has no window to project a late commit from (#5570).

    The window is ``pre_mutation_coord_sha..branch``. Without the recorded tip (or the
    coordination checkpoint) there is nothing to compare the branch against, and the delete
    that follows would compare-and-swap at the LIVE tip, so a commit that landed after the
    gate would be destroyed at exit 0. Nothing to protect when the branch is already gone.

    Raises:
        CoordinationTeardownError: the branch exists, so it is kept for the operator to review.
    """
    branch = run.lanes_manifest.mission_branch
    target = run.lanes_manifest.target_branch
    if _mission_branch_tip(run) is None:
        return
    raise CoordinationTeardownError(
        f"cannot tell whether coordination commits landed on {branch!r} during teardown: the pre-mutation coordination tip "
        f"or the coordination checkpoint was not recorded, so there is no window to project them from; "
        f"branch {branch!r} was NOT deleted and the mission's coordination marker was left intact. "
        f"Review the branch with `git log {target}..{branch}`, land anything that belongs on {target}, "
        "then run `spec-kitty consolidate --resume` again."
    )


def _land_late_coordination_commits(run: _MergeRunState) -> None:
    """Project coordination commits that landed after the teardown gate onto the target (#5570).

    The recovery half of the tip-moved refusal (:func:`_tip_moved_teardown_error`): a
    ``--resume`` finishing teardown must not delete a coordination branch carrying a commit
    the target never received. Re-projects the window from the persisted pre-mutation
    coordination tip to the branch's live tip through the same seam the merge used
    (status union + non-status paths; idempotent for what already landed), commits what
    changed onto the target, and moves the PASS anchor over that commit. The delete that
    follows stays a compare-and-swap at the live tip, so a commit landing after THIS
    projection still refuses instead of being lost.

    A no-op on a fresh run (the teardown gate covers it) and when nothing landed late.
    A resume that cannot build the window (no recorded coordination checkpoint or
    pre-mutation tip) while the branch still exists FAILS CLOSED instead: it cannot tell
    whether a late commit sits on the branch, and the delete that follows reads the live tip.
    """
    checkpoint = run.coord_checkpoint
    base = run.state.pre_mutation_coord_sha
    branch = run.lanes_manifest.mission_branch
    if not run.is_resume:
        return
    if checkpoint is None or not base:
        _refuse_unbuildable_late_window(run)
        return
    if checkpoint.ref not in (branch, f"refs/heads/{branch}"):
        return
    target = run.lanes_manifest.target_branch
    try:
        if not _post_checkpoint_commit_shas(run.main_repo, base, checkpoint.ref):
            return
        events_path, status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
            checkpoint_sha=base,
            coord_ref=checkpoint.ref,
        )
        late_paths = [run.main_repo / rel for rel in _post_checkpoint_mission_paths(run.main_repo, run.mission_slug, base, checkpoint.ref)]
    except GitCommandError as exc:
        raise CoordinationTeardownError(
            f"the coordination commits that landed during teardown could not be read ({escape(str(exc))}); "
            f"branch {branch!r} was NOT deleted. Re-run `spec-kitty consolidate --resume` once the git error is fixed."
        ) from exc
    paths = [path for path in dict.fromkeys([events_path, status_path, *late_paths]) if path.exists()]
    if not _paths_have_status_changes(run.main_repo, paths):
        return
    landed = commit_merge_bookkeeping(
        repo_root=run.main_repo,
        worktree_root=run.main_repo,
        mission_slug=run.mission_slug,
        branch=target,
        destination_ref_override=target,
        message=f"chore({run.mission_slug}): project coordination commits that landed during teardown (#5570)",
        paths=tuple(paths),
    )
    _carry_pass_anchor_over_own_commit(run, landed.sha)
    console.print(f"  Projected the coordination commit(s) that landed during teardown onto {target}")


def _fold_coord_status_before_flatten(run: _MergeRunState) -> None:
    """Commit every coord status event to the primary corpus before deleting its branch."""
    source = run.feature_dir / "status.events.jsonl"
    target = run.target_feature_dir / "status.events.jsonl"
    if source == target or not source.is_file() or not source.read_bytes().strip():
        return
    try:
        events_path, status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
        )
        assert_alias_events_preserved(alias_events_path=source, primary_events_path=events_path)
        paths = [events_path, status_path]
        if _paths_have_status_changes(run.main_repo, paths):
            landed = commit_merge_bookkeeping(
                repo_root=run.main_repo,
                worktree_root=run.main_repo,
                mission_slug=run.mission_slug,
                branch=run.lanes_manifest.target_branch,
                destination_ref_override=run.lanes_manifest.target_branch,
                message=f"chore({run.mission_slug}): fold coordination status before flatten (#3272)",
                paths=tuple(paths),
            )
            _carry_pass_anchor_over_own_commit(run, landed.sha)
            console.print(f"  Folded the coordination status onto {run.lanes_manifest.target_branch} before teardown")
    except Exception as exc:
        raise CoordinationTeardownError(
            f"coordination status could not be folded onto {run.lanes_manifest.target_branch!r} ({escape(str(exc))}); "
            f"branch {run.lanes_manifest.mission_branch!r} was NOT deleted and the mission's coordination marker was left intact. "
            "Re-run `spec-kitty consolidate --resume` once the cause is fixed."
        ) from exc


def _teardown_coord_worktree(run: _MergeRunState) -> str | None:
    """Coordination worktree teardown (WP07/FR-016/SC-10).

    The shared ``teardown_coordination_topology`` seam (FR-004) persists the
    retrospective to its durable home BEFORE destroying the worktree
    (persist-before-destroy, FR-005), then performs the idempotent worktree
    removal that safely no-ops for legacy missions that never created a
    coordination worktree (FR-017, empty ``mid8``).

    Returns the mission-branch tip the projection teardown gate approved
    (#5570), so the later branch delete can compare-and-swap at it; ``None``
    when no CAS-protected gate ran (ungated, or the coordination ref is the
    target / not the mission branch).
    """
    from specify_cli.coordination.teardown import (
        ProjectionTeardownGate,
        teardown_coordination_topology,
    )
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    # FR-007 route: ``route-unwrapped`` census site -- a corrupt meta.json
    # surfaces the typed ``MissionMetaReadError`` (never a raw
    # ``ValueError``) and PROPAGATES, exactly as the raw read did before.
    # Identity (``mid8``) lives in the PRIMARY metadata, so read it from
    # ``target_feature_dir``: ``run.feature_dir`` is the status directory, which
    # under a bare-slug coordination Mission is a composed ``<slug>-<mid8>``
    # directory holding status files only and no ``meta.json`` (#5651).
    _meta_for_teardown = _load_meta(run.target_feature_dir)
    _mid8_for_teardown = str(_meta_for_teardown.get("mid8", "")).strip() if isinstance(_meta_for_teardown, dict) else ""
    # WP10 integration (S-B / FR-004 / T034): when the merge captured a
    # coordination checkpoint AND ran the reconciliation gate, build the
    # projection teardown gate so ``teardown_coordination_topology`` refuses
    # fail-closed unless (a) the reconciliation reachability check passed AND
    # (b) the coordination tip is unchanged since the projection captured its
    # window (compare-and-swap). A non-coord/legacy mission (no checkpoint)
    # keeps the ungated behaviour (``projection_gate=None``).
    #
    # The compare-and-swap protects a SEPARATE coordination branch from a
    # concurrent commit landing between projection and teardown (#4981). When the
    # coordination ref IS the target branch (a degenerate placement where the
    # STATUS_STATE surface resolves to the target itself), the merge's OWN final
    # bookkeeping commit legitimately advances that ref AFTER the projection
    # capture, so a fixed-SHA CAS would false-abort (#2804 regression) — and there
    # is no distinct coordination surface for it to protect anyway. In that case
    # enforce ONLY the reachability leg (a stable ``expected_coord_sha`` equal to
    # the ref's current tip makes the CAS a satisfied no-op) rather than skipping
    # the gate entirely.
    projection_gate: ProjectionTeardownGate | None = None
    approved_branch_tip: str | None = None
    checkpoint = run.coord_checkpoint
    if checkpoint is not None and run.reconciliation_result is not None:
        coord_is_distinct = _resolve_ref_sha(run.main_repo, checkpoint.ref) != _resolve_ref_sha(run.main_repo, run.lanes_manifest.target_branch)
        if coord_is_distinct:
            expected_coord_sha = run.coord_tip_after_projection or checkpoint.sha
            if checkpoint.ref in (run.lanes_manifest.mission_branch, f"refs/heads/{run.lanes_manifest.mission_branch}"):
                approved_branch_tip = expected_coord_sha
        else:
            # No separate coordination branch to CAS-protect; anchor on the ref's
            # current tip so the compare-and-swap is a satisfied no-op and only the
            # reachability leg gates teardown.
            expected_coord_sha = _resolve_ref_sha(run.main_repo, checkpoint.ref) or checkpoint.sha
        projection_gate = ProjectionTeardownGate(
            coord_ref=checkpoint.ref,
            expected_coord_sha=expected_coord_sha,
            reachability_ok=run.reconciliation_result.is_pass,
        )
    teardown_coordination_topology(
        run.main_repo,
        run.mission_slug,
        _mid8_for_teardown,
        projection_gate=projection_gate,
        on_persist_commit=functools.partial(_carry_pass_anchor_over_own_commit, run),
    )
    logger.debug(
        "Coordination topology teardown for %s-%s completed",
        run.mission_slug,
        _mid8_for_teardown,
    )
    return approved_branch_tip


def _teardown_coordination_triple(run: _MergeRunState) -> None:
    """Coord branch + marker-flatten + coord-worktree -- ONE atomic unit.

    #3131 INV-2 / T008: for a coord-topology mission these three resources
    must always be mutually consistent (all retained, or all torn down
    together) -- never a branch deleted while its marker/worktree survive
    (or vice versa), which reintroduces #3086 or strands a coord husk. Called
    only when ``run.teardown_coordination`` (``delete_branch AND
    remove_worktree``) is True.

    **Order matters (#3926).** The worktree goes first: ``git branch -D``
    refuses while the branch is checked out in the coord worktree
    (``cannot delete branch '...' used by worktree at '...'``), and with the
    branch-delete leg running first that refusal was swallowed
    (``check_return=False``) while the flatten ran anyway — leaving exactly
    the inverted #3086 shape the invariant forbids: marker flattened, branch
    and worktree both surviving, and a "Cleaned up" line printed over the
    git error. Removing the worktree first releases the checkout, so the
    delete can succeed; the flatten then runs only once the branch is
    actually gone, and a leg that fails raises instead of reporting success.
    """
    # #5570: the delete is a compare-and-swap at the tip approved BEFORE the
    # window opens -- the gate's tip when one ran, else the tip read now, ahead of
    # the persist/worktree-destroy legs. A commit landing in between survives.
    _land_late_coordination_commits(run)
    _fold_coord_status_before_flatten(run)
    pre_teardown_tip = _mission_branch_tip(run)
    approved_tip = _teardown_coord_worktree(run) or pre_teardown_tip
    if not _delete_mission_branch(run, approved_tip):
        raise CoordinationTeardownError(
            f"coordination branch {run.lanes_manifest.mission_branch!r} still exists after teardown; "
            "the mission's coordination marker was left intact so the branch, its worktree and the "
            "marker stay consistent. Remove whatever still references the branch "
            "(`git worktree list`), then re-run `spec-kitty consolidate --resume`."
        )
    _flatten_coordination_metadata_after_branch_delete(run)


def _clear_landed_single_branch_mission_branch(run: _MergeRunState) -> None:
    """#5100 B4: drop ``meta.mission_branch`` once the branch has been landed.

    A protected single_branch mission records its minted ``mission_branch`` in
    ``meta.json``. After landing it no longer is the write target whether the
    branch was deleted (it names a dead branch) or kept (``--keep-branch`` /
    ``retain_branches``; the write checkout is already back on the target, so a
    retained ``mission_branch`` would route the retrospective and every later
    status write to a branch the checkout is not on). Clearing it (mirroring the
    coord flatten) makes later writes resolve to ``target_branch``. No-op unless
    the mission lands a protected mission branch.
    """
    from specify_cli.lanes.single_branch_landing import lands_mission_branch
    from specify_cli.mission_metadata import load_meta_or_empty, write_meta

    if not lands_mission_branch(run.main_repo, run.lanes_manifest):
        return
    feature_dir = run.target_feature_dir
    meta = load_meta_or_empty(feature_dir)
    if "mission_branch" not in meta:
        return
    del meta["mission_branch"]
    write_meta(feature_dir, meta, validate=False)
    meta_path = feature_dir / "meta.json"
    try:
        commit_merge_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=run.main_repo,
            mission_slug=run.mission_slug,
            branch=run.lanes_manifest.target_branch,
            message=f"chore({run.mission_slug}): clear landed mission_branch (#5100)",
            paths=(meta_path,),
        )
    except Exception as exc:  # fail-open: never abort a completed merge for a bookkeeping commit
        logger.warning("mission_branch clear commit failed for %s (%s); meta.json is cleared on disk but may be uncommitted", run.mission_slug, exc)


def _cleanup_mission_branch_and_coordination(run: _MergeRunState) -> None:
    """Topology-aware mission/coordination cleanup (#3131 T008).

    A coord-topology mission couples its mission/coordination branch, marker,
    and worktree under the single ``teardown_coordination`` decision (INV-2)
    so a partial-retention request (only ``delete_branch`` or only
    ``remove_worktree``) never half-tears the coord triple. A non-coord
    mission (``single_branch``/``lanes``) has no coordination branch/marker/
    worktree, so its mission-branch deletion stays on the plain
    ``delete_branch`` gate exactly as before this change (no behavior
    change) -- and the (harmless, no-op) flatten + coord-worktree-teardown
    calls stay wired to their original standalone gates too.
    """
    if _is_coord_topology_mission(run):
        if run.teardown_coordination:
            _teardown_coordination_triple(run)
            console.print("  Cleaned up mission/coordination branch + worktree")
        return

    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    # Read BEFORE the clear below: ``lands_mission_branch`` keys on the recorded
    # ``meta.mission_branch``, which ``_clear_landed_single_branch_mission_branch`` drops.
    landed_single_branch = lands_mission_branch(run.main_repo, run.lanes_manifest)
    if run.delete_branch:
        _delete_mission_branch(run)
    # Landed => the branch is no longer the write target, kept or deleted.
    _clear_landed_single_branch_mission_branch(run)
    if run.delete_branch:
        # issue #3086: the coordination branch is now gone from git; flatten the
        # mission's meta.json in the SAME gate so we can never delete the branch
        # yet strand the paired ``coordination_branch`` marker. A no-op here
        # (non-coord mission carries no ``coordination_branch`` key).
        _flatten_coordination_metadata_after_branch_delete(run)
    # A landed protected single_branch mission has NO coordination worktree; its
    # checkpoint ref is the (now deleted) mission branch, so the projection
    # teardown gate would false-abort. Nothing to tear down.
    if run.remove_worktree and not landed_single_branch:
        _teardown_coord_worktree(run)


def _remove_lane_worktrees(run: _MergeRunState) -> None:
    """T005/T012 (#4753, C-003): remove every lane worktree + tombstone its context.

    Extracted (tidy-first, WP02/T034) out of
    :func:`_phase_cleanup_worktrees_and_branches`, behaviour-preserving. Routed
    through the shared :func:`~specify_cli.git.destructive_guard.guarded_worktree_remove`
    chokepoint instead of a raw ``git worktree remove --force``. The T010
    preflight has already fail-closed on any dirty lane worktree BEFORE any
    ref advance, so every worktree reaching this loop is known-clean; the
    guard call here is defense-in-depth against a race between preflight and
    cleanup, not the primary safety mechanism. ``retain=False`` because this
    function only runs when ``run.remove_worktree`` is True (removal
    requested) — ``--keep-worktree`` already makes ``run.remove_worktree``
    False and skips this function entirely (ADVISORY-3: do not map the
    operator retain flag onto the guard's ``retain`` parameter here).
    """
    from specify_cli.workspace import delete_context

    lanes_manifest = run.lanes_manifest
    delay = _worktree_removal_delay()
    # WP10 integration (C-3 / #4978): thread the STORED topology so the
    # coord-residue leg is topology-aware — a coord-partition-KIND artifact
    # on a LANES / SINGLE_BRANCH mission is real work, never reset as residue.
    is_residue = functools.partial(
        is_toolchain_generated_churn,
        mission_slug=run.mission_slug,
        topology=_stored_topology_for(run.target_feature_dir),
    )
    for idx, lane in enumerate(worktree_lanes(lanes_manifest)):
        # lane-branch-naming-authority-01M3EVC4 WP02 (T035): the CREATED
        # worktree (never keyed by ``run.baseline_mission_id``), so a
        # divergent-identity mission's worktree is never orphaned.
        wt_path = _created_lane_worktree(run.main_repo, lanes_manifest.mission_slug, lane.lane_id)
        if wt_path.exists():
            guarded_worktree_remove(wt_path, retain=False, is_residue=is_residue)
            console.print(f"  Removed worktree: {wt_path.name}")
            if delay > 0 and idx < len(worktree_lanes(lanes_manifest)) - 1:
                time.sleep(delay)
        else:
            logger.debug("Worktree %s does not exist, skipping removal", wt_path)

    # FR-005/LC-6 (#1842 WP03): tombstone each lane's workspace-context
    # JSON when its worktree is removed at merge completion. The tombstone
    # is deliberately nested under ``remove_worktree``: the context JSON
    # *describes* the worktree, so the two are torn down together — a
    # ``--no-remove-worktree`` merge intentionally keeps BOTH the worktree
    # and its context (never orphaning one from the other).
    # ``delete_context`` itself is a pure, order-independent unlink — it
    # targets the legacy ``<slug>-<lane>`` filename ``save_context`` always
    # writes, and silently no-ops for a lane that never saved a context
    # (e.g. a planning-artifact lane) or one already tombstoned. The
    # filename MUST equal ``_created_lane_worktree(...).name`` (the string
    # ``save_context`` wrote) — never independently composed.
    for lane in worktree_lanes(lanes_manifest):
        workspace_name = _created_lane_worktree(run.main_repo, lanes_manifest.mission_slug, lane.lane_id).name
        delete_context(run.main_repo, workspace_name)


def _delete_lane_branches(run: _MergeRunState) -> None:
    """T005/#3131 T008: delete every non-planning lane branch, retry-tolerant.

    Extracted (tidy-first, WP02/T034) out of
    :func:`_phase_cleanup_worktrees_and_branches`, behaviour-preserving. Lane
    branches stay keyed to the plain ``delete_branch`` gate regardless of
    topology — only the MISSION/coordination branch
    (:func:`_cleanup_mission_branch_and_coordination`) is topology-aware and
    coupled to ``teardown_coordination`` for a coord mission.
    """
    from specify_cli.lanes.compute import is_planning_lane
    from specify_cli.lanes.lane_tip import clear_tip

    lanes_manifest = run.lanes_manifest
    deleted = 0
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane):
            continue
        # lane-branch-naming-authority-01M3EVC4 WP02 (T035): the CREATED
        # branch (never a Mission-identity form).
        branch_name = _created_lane_branch(lanes_manifest, lane.lane_id)
        ret, _, _ = run_command(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
            capture=True,
            check_return=False,
            cwd=run.main_repo,
        )
        if ret == 0:
            run_command(
                ["git", "branch", "-D", branch_name],
                cwd=run.main_repo,
                check_return=False,
            )
            deleted += 1
        else:
            logger.debug("Branch %s does not exist, skipping deletion", branch_name)
        # #5115/WP07 (sibling-owned, one line): the lane-tip ref outlives the
        # branch it was keyed on -- clear it here too, or a future recut of
        # the SAME branch name would inherit a stale tip.
        clear_tip(run.main_repo, branch_name)
    if deleted:
        console.print(f"  Cleaned up {deleted} lane branch(es)")


def _phase_cleanup_worktrees_and_branches(run: _MergeRunState) -> None:
    """Worktree removal + lane/mission branch deletion + coordination teardown."""
    if run.remove_worktree:
        _remove_lane_worktrees(run)

    if run.delete_branch:
        _delete_lane_branches(run)

    # -- #3131 T008: MISSION/coordination branch + marker + worktree --
    # Topology-aware and (for coord) coupled under ``teardown_coordination``;
    # see ``_cleanup_mission_branch_and_coordination`` for the INV-2 rationale.
    _cleanup_mission_branch_and_coordination(run)
