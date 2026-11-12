"""Teardown phase: the coordination triple, then the lane legs (S5, FR-031).

The lane legs (worktrees and branches) go through the one lane-cleanup module
(``consolidation.lane_cleanup``) and are reported, never raised, after the verified landing; the
topology-aware mission/coordination cleanup, the coordination triple
(worktree -> compare-and-swap branch delete -> marker flatten, INV-2 / #3926),
the projection teardown gate construction, and the late-landing projection of
coordination commits that arrived during teardown (#5570) -- on a resumed run
(everything the coordination branch changed since the merge began) and on a first
run (what landed after the tip this run captured, #6871).

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

import functools
import time
from typing import Any
from pathlib import Path

from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.coordination.coherence import CheckoutRole, residue_context_or_strictest
from specify_cli.core.git_ops import run_command
from specify_cli.core.vcs.git import git_merge_base
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.missions._read_path_resolver import mission_dir_aliases
from specify_cli.status import EventLogMergeError, StoreError
from kernel.git import GitCommandError
from kernel.git import changed_paths as git_changed_paths
from specify_cli.git.bookkeeping_commit import (
    commit_merge_bookkeeping,
)
from specify_cli.git.commit_helpers import (
    ProtectedBranchCommitError,
    SafeCommitBackstopError,
    SafeCommitError,
    SafeCommitRecoveryFailed,
)
from specify_cli.git.ref_advance import (
    RefAdvanceError,
    RefDeleteError,
    RefDeleteMismatchError,
    delete_branch_ref,
    worktrees_with_branch_checked_out,
)
from specify_cli.consolidation.git_probes import GitProbeError, _paths_have_status_changes, is_ancestor_strict
from specify_cli.consolidation.landed_coordination import LandedCoordinationRefError, record_landed_coordination_tip
from specify_cli.consolidation import lane_cleanup
from specify_cli.consolidation.lane_cleanup import (
    LaneCleanupReport,
    LaneRetention,
    LocalTargetAtPass,
    GuardedLaneRemover,
    cleanup_expected_tips,
    plan_lane_cleanup,
)
from specify_cli.consolidation._constants import (
    COORD_LATE_PROJECTION_REFUSED_SUFFIX,
    COORD_MOVED_AFTER_LANDING_SUFFIX,
    logger,
)
from specify_cli.consolidation.bookkeeping_projection import (
    _post_checkpoint_commit_shas,
    _post_checkpoint_mission_paths,
    _project_status_bookkeeping_to_target,
    _resolve_ref_sha,
    AliasStatusEventsNotPreserved,
    LateProjectionRefusalKind,
    LateProjectionRefused,
    assert_alias_events_preserved,
    assert_late_window_landed,
    project_late_gate_matrix_commits,
    unlanded_topic_primary_paths,
)
from specify_cli.consolidation.state import (
    save_state,
)
from specify_cli.consolidation.workspace import _worktree_removal_delay
from specify_cli.consolidation.run_state import (
    CoordMovedAfterLanding,
    CoordinationTeardownError,
    _MergeRunState,
    _is_coord_topology_mission,
    landing_verified_for_resume,
)


# What ``commit_merge_bookkeeping`` (via ``safe_commit``) raises when a commit cannot land.
_BOOKKEEPING_COMMIT_ERRORS = (SafeCommitError, SafeCommitBackstopError, ProtectedBranchCommitError, GitCommandError, OSError)


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

    **Publishing.** This flatten (and its bookkeeping commit) runs in
    ``_phase_cleanup_worktrees_and_branches``, AFTER ``_phase_push``; on a
    ``--push`` run the executor therefore pushes once more after cleanup
    (``_phase_push_cleanup_commits``, warn-only), so the flatten commit is not
    left local-only.

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
    from specify_cli.mission_metadata import flatten_coordination_metadata

    feature_dir = run.target_feature_dir
    if not (feature_dir / "meta.json").exists():
        return

    # Canonical three-mutation flatten (#3219 / FR-015 / D-PLAN-17), converged
    # onto the ONE shared primitive -- parity with ``doctor coordination --fix``
    # / ``mission close --discard``, and closes the double-write window the
    # former two-call (clear + separate topology/flattened write) shape here
    # invited. The primitive decides under the Mission write lock whether
    # there is anything to flatten (an empty snapshot means a non-coord or
    # already-flattened Mission), so no unlocked pre-read gates the write.
    try:
        if not flatten_coordination_metadata(feature_dir):
            return
    except MissionMetaReadError:
        return  # unreadable meta.json: nothing to flatten, and a completed merge is never aborted for it

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
                "`spec-kitty doctor coordination --fix --mission %s`",
                run.mission_slug,
                exc,
                run.mission_slug,
            )
    except Exception as exc:
        # Fail-open: never abort a completed merge for a bookkeeping-commit failure.
        logger.warning(
            "Flatten bookkeeping commit failed for %s (%s); meta.json is flattened "
            "on disk but may be uncommitted — recover with "
            "`spec-kitty doctor coordination --fix --mission %s`",
            run.mission_slug,
            exc,
            run.mission_slug,
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
    """Delete the mission/coordination branch; ``True`` when it is gone afterwards (see :func:`_refused_mission_branch_delete`)."""
    return _refused_mission_branch_delete(run, expected_tip) is None


def _refused_mission_branch_delete(run: _MergeRunState, expected_tip: str | None = None) -> str | None:
    """Delete the mission/coordination branch from git, if it exists.

    Returns ``None`` when the branch is gone afterwards — deleted now, or already
    absent — else git's refusal text (#4380 item 2: the caller puts it in its
    refusal instead of pointing at a log line). The delete is a compare-and-swap at ``expected_tip`` (#5570): the
    tip the teardown gate approved, or — when no gate ran — the tip read at the
    start of the teardown phase; ``None`` reads it now. A commit that landed
    after that tip survives (the branch is kept) and the refusal is raised as
    :class:`CoordinationTeardownError`, never restored or force-deleted here.

    Git refuses to drop a branch that is checked out in a worktree (#3926); the
    typed refusal is reported (its text) rather than assumed to be success,
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
        return None
    tip = expected_tip or _mission_branch_tip(run)
    if tip is None:
        logger.debug("Mission branch %s does not exist, skipping deletion", branch)
        return None
    try:
        delete_branch_ref(run.main_repo, branch, tip)
    except RefDeleteMismatchError as exc:
        if exc.actual_sha is None:
            # The post-failure probe found no ref at all, so the branch IS gone and the
            # postcondition (absent) holds. If someone else removed it, that was not this
            # delete: it never ran against a moved or surviving tip.
            return None
        raise _tip_moved_teardown_error(branch, exc, coordination=_is_coord_topology_mission(run)) from exc
    except RefDeleteError as exc:
        logger.warning("Mission branch %s was not deleted: %s", branch, exc)
        return str(exc) or type(exc).__name__
    return None


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


def _commit_projection_and_carry(run: _MergeRunState, paths: list[Path], message: str) -> None:
    """Commit *paths* onto the target and move the PASS anchor over that commit."""
    target = run.lanes_manifest.target_branch
    landed = commit_merge_bookkeeping(
        repo_root=run.main_repo,
        worktree_root=run.main_repo,
        mission_slug=run.mission_slug,
        branch=target,
        destination_ref_override=target,
        message=message,
        paths=tuple(paths),
    )
    _carry_pass_anchor_over_own_commit(run, landed.sha)


def _unlanded_paths_outside_mission_dir(run: _MergeRunState, base: str, coord_ref: str) -> list[str]:
    """Paths a coordination commit in ``base..coord_ref`` changed OUTSIDE the Mission directory whose content is not on the target (#5965, D4).

    The late projection carries only ``kitty-specs/<slug>/`` paths, so such a commit would be destroyed
    with the coordination branch. A path whose blob on ``coord_ref`` equals the target's is already
    landed (the lane code the run itself merged into the coordination branch) and is not reported.
    """
    target = run.lanes_manifest.target_branch
    # A bare-slug coordination Mission keeps its coordination directory under the
    # composed ``<slug>-<mid8>`` name; its status pair is landed by the fold, not
    # stranded. Recognise that directory through the ONE canonical authority that
    # pairs a bare-slug primary with its composed coord dir (#5651), the same
    # resolver ``interrupted_alias_fold_guidance`` uses — else a resume teardown
    # misreads the composed-dir status files as "outside the Mission directory"
    # (#6071 / regressed by #5965/#5966).
    own_names = {run.mission_slug, run.target_feature_dir.name} | mission_dir_aliases(run.main_repo, run.mission_slug)
    own_prefixes = tuple(f"{KITTY_SPECS_DIR}/{name}/" for name in own_names)
    unlanded: list[str] = []
    for changed in git_changed_paths(run.main_repo, base, coord_ref, renames=True):
        path = str(changed)
        if path.startswith(own_prefixes):
            continue
        if _resolve_ref_sha(run.main_repo, f"{coord_ref}:{path}") != _resolve_ref_sha(run.main_repo, f"{target}:{path}"):
            unlanded.append(path)
    return sorted(set(unlanded))


def _mission_dir_names(run: _MergeRunState) -> list[str]:
    """Every directory of THIS Mission the late-window proof judges, the Mission's own name first (#7271).

    A bare-slug coordination Mission keeps its coordination directory under the composed ``<slug>-<mid8>``
    name (#5651), and :func:`_unlanded_paths_outside_mission_dir` skips that directory as the Mission's own,
    so a change there has to be proved here or it dies with the branch.
    """
    others = ({run.target_feature_dir.name} | mission_dir_aliases(run.main_repo, run.mission_slug)) - {run.mission_slug}
    return [run.mission_slug, *sorted(others)]


def _assert_window_landed_in_every_mission_dir(run: _MergeRunState, *, base: str, projected_tip: str, branch: str, target: str) -> None:
    """Refuse the teardown unless the window is proved in every directory of this Mission (#7198, #7271)."""
    try:
        for window_dir in _mission_dir_names(run):
            assert_late_window_landed(
                main_repo=run.main_repo,
                mission_slug=run.mission_slug,
                coord_ref=projected_tip,
                checkpoint_sha=base,
                target_feature_dir=run.target_feature_dir,
                target_ref=target,
                window_dir=window_dir,
            )
    except LateProjectionRefused as exc:
        raise CoordinationTeardownError(_late_projection_refusal(branch, target, exc)) from exc
    except GitCommandError as exc:
        # #7198 review: the assertion reads blobs through the failure-distinguishing reader, so a git
        # failure is an ERROR, never a verdict. Fail closed with the triple kept -- the same recovery as
        # the projection leg above -- instead of letting a failed read look like a landed blob.
        raise CoordinationTeardownError(
            f"the late window's blobs could not be read ({escape(str(exc))}); "
            f"branch {branch!r} was NOT deleted and the mission's coordination marker was left intact. "
            "Re-run `spec-kitty consolidate --resume` once the git error is fixed."
        ) from exc


def _advance_approved_tip(run: _MergeRunState, coord_ref: str, projected_tip: str) -> None:
    """Record ``projected_tip`` (T) as the tip teardown approves, once the window is proven (#6871/#7199/#7265).

    The projection teardown gate and the compare-and-swap branch delete anchor on
    ``coord_tip_after_projection``; leaving it at the anchor this run captured earlier would refuse the very
    commit this window just landed, on EITHER run kind. The advance is a guarded read on T: a commit that
    lands DURING the projection leaves the ref somewhere else, the anchor stays put, and the gate's own
    compare-and-swap refuses (fail-closed): a commit landing during the projection is never stamped approved.
    """
    if _resolve_ref_sha(run.main_repo, coord_ref) == projected_tip:
        run.coord_tip_after_projection = projected_tip
        _persist_proven_coordination_tip(run, projected_tip)


def _persist_proven_coordination_tip(run: _MergeRunState, proven_tip: str) -> None:
    """Keep the persisted coordination tip (#7491) current with a late window just proven landed.

    Only while the record carries a PASS anchor: the tip is written with that anchor and is only
    sound beside it. The window was proven landed before this advance, so a narrower resume base
    is still sound. The landed-coordination ref follows (#4041).
    """
    if not run.state.reconciliation_passed_target_sha or run.state.coord_tip_after_projection == proven_tip:
        return
    run.state.coord_tip_after_projection = proven_tip
    save_state(run.state, run.main_repo)
    record_landed_coordination_ref(run, proven_tip)


def record_landed_coordination_ref(run: _MergeRunState, tip: str | None) -> None:
    """Best effort: record *tip* as the landed coordination tip of this run's coordination branch (#4041).

    Written only for a coordination topology (the checkpoint ref names a coordination branch, not the
    target). A failure never fails the landing: the ref only enables a later reclaim, which refuses
    without it, so it is logged at warning and the run goes on.
    """
    checkpoint = run.coord_checkpoint
    if not tip or checkpoint is None:
        return
    branch = checkpoint.ref.removeprefix("refs/heads/")
    if branch in ("", run.lanes_manifest.target_branch) or branch != run.lanes_manifest.mission_branch:
        return
    try:
        record_landed_coordination_tip(run.main_repo, branch, tip)
    except (LandedCoordinationRefError, GitProbeError, ValueError) as exc:
        logger.warning("Could not record the landed coordination tip of %s at %s: %s", branch, tip[:12], exc)


def _verified_resume_base(run: _MergeRunState) -> str | None:
    """The persisted post-projection coordination tip, when a resume may start its late window there (#7491).

    Sound only when the landing is verified (``landing_verified_for_resume``: exactly the resume that
    skips the phases, so no attempt re-ran past the tip) AND the tip is still an ancestor of the live
    coordination branch (a rewritten branch falls back). A git failure falls back too: the wider
    ``pre_mutation_coord_sha`` base refuses rather than passes what it cannot prove.
    """
    tip = run.state.coord_tip_after_projection
    if not tip or not landing_verified_for_resume(run.main_repo, run.state):
        return None
    try:
        on_branch = is_ancestor_strict(run.main_repo, tip, f"refs/heads/{run.lanes_manifest.mission_branch}")
    except GitProbeError:
        return None
    return str(tip) if on_branch else None


def _late_window_base(run: _MergeRunState) -> str | None:
    """The coordination tip the late-teardown window starts at, per RUN KIND (#6871).

    A ``--resume`` has no in-memory record of what the interrupted merge verified. When the record
    proves the landing was verified (``landing_verified_for_resume``) and carries the coordination
    tip persisted with that PASS anchor, still an ancestor of the live coordination branch, the
    window starts there, exactly like the first run's (#7491): everything at or before it was
    covered by the verified landing. Otherwise it anchors on the persisted PRE-mutation coordination
    snapshot (``state.pre_mutation_coord_sha``): that window spans everything the coordination
    branch changed since the merge began, which is what a second attempt must not drop
    (#5570/#6791).

    A first run does have that record. ``run.coord_tip_after_projection`` is captured at the end of
    the bookkeeping phase, after every merge-owned coordination write, and is the tip the
    projection teardown gate compare-and-swaps against: everything at or before it was projected by
    the merge itself, so a commit AFTER it is exactly "landed between the gate and teardown".
    Anchoring the first run here keeps a clean run a provable no-op; reusing the resume base instead
    would re-walk the whole merge and re-project primary artifacts the target authored for itself.

    The base decides only WHERE the window starts. It does not decide whether teardown may approve
    the proven tip: that advance applies to both run kinds (#7199), because either base is at or
    before the anchor the run captured and every record in the window is proven landed before the
    advance.

    ``None`` means the run recorded no anchor at all (a coordination placement that did not resolve),
    so no window can be built — see :func:`_land_late_coordination_commits`.
    """
    # Typed locals: the ``specify_cli.*`` ``follow_imports=skip`` override resolves these
    # cross-module attributes as ``Any``, and returning ``Any`` trips ``no-any-return``.
    if run.is_resume:
        verified = _verified_resume_base(run)
        resume_base: str | None = verified if verified is not None else run.state.pre_mutation_coord_sha
        return resume_base
    first_run_base: str | None = run.coord_tip_after_projection
    return first_run_base


def _land_late_coordination_commits(run: _MergeRunState) -> None:
    """Project the coordination commits the target never received, before teardown deletes them (#5570).

    The recovery half of the tip-moved refusal (:func:`_tip_moved_teardown_error`): a
    ``--resume`` finishing teardown must not delete a coordination branch carrying a commit
    the target never received. Re-projects the window from the persisted pre-mutation
    coordination tip to the branch's live tip through the same seam the merge used
    (status union + non-status paths; idempotent for what already landed), commits what
    changed onto the target, and moves the PASS anchor over that commit. The delete that
    follows stays a compare-and-swap at the live tip, so a commit landing after THIS
    projection still refuses instead of being lost.

    A no-op when nothing landed late, and on a first run that recorded no anchor of its own.
    A resume that cannot build the window (no recorded coordination checkpoint or
    pre-mutation tip) while the branch still exists FAILS CLOSED instead: it cannot tell
    whether a late commit sits on the branch, and the delete that follows reads the live tip.

    #6871 — the FIRST run gets the same projection and the same proof, over a narrower window. Its
    base is the tip THIS run captured (:func:`_late_window_base`), so only a commit made after the
    merge captured it is carried; a clean run projects nothing. Without this, a first run that HAD
    a coordination checkpoint refused such a commit at the projection teardown gate's compare-and-
    swap, leaving an operator to hand-assemble a landing that was already complete. A first run
    with no recorded coordination tip still builds no window and can lose the commit with the
    branch (#7121).

    #7199 — after the window is proven landed, the run records that tip as the one teardown approved,
    on EITHER run kind, so the gate and the branch delete anchor on a tip whose coordination records
    are on the target, never on one that was merely read. A resume window starts at or before its own
    captured anchor (:func:`_late_window_base`), so it covers at least the first-run window and the
    same proof justifies the same advance; without it a resume refused the very commit its window had
    just landed, because the gate still compared against the anchor captured earlier (#7124 reviewer
    finding B5).

    #6791 widens WHICH records this window carries and adds the proof that it carried them: a
    gate matrix committed here (``agent issue-verdict`` after the refusal's own instruction to
    commit on the coordination branch) is projected too -- the general path selector excludes
    those kinds for the MID-merge window only, where the coord ref can hold a stale placeholder
    -- and after the projection commit every coordination record changed in the window must be
    byte-identical on the target, or the teardown REFUSES (branch, worktree and marker kept)
    instead of deleting a commit it did not land.

    On a resume whose landing is not verified (or whose record has no persisted coordination tip)
    the window starts at the PRE-mutation coordination snapshot (``state.pre_mutation_coord_sha``),
    so it spans everything the coordination branch changed SINCE THE MERGE BEGAN: it also carries
    commits made while the merge ran. After a verified landing it starts at the coordination tip
    persisted with the PASS anchor, like a first run (#7491), so the merge's own lane merges of
    PRIMARY artifacts the target later changed are not re-judged. The refusal is reachable on an
    ordinary resume, not just one that follows a refused teardown -- a window that deletes a record
    the target holds REFUSES (exit 1) where this path used to exit 0 and drop the deletion with the
    branch (see :func:`assert_late_window_landed`).

    #7198: the proof above covers EVERY change in the window, not only coordination-kind records. The
    two exemptions it used to carry -- the status byte-sets and every non-coordination path -- were
    what let a branch-only ``status.events.jsonl`` append (the union stage folds the coordination
    worktree's working tree, not the branch's commits) or a late ``meta.json`` edit be approved and
    deleted at exit 0. Each is now landed, proved, or refused by its own rule; see
    :func:`~specify_cli.consolidation.bookkeeping_projection.assert_late_window_landed`.
    """
    checkpoint = run.coord_checkpoint
    base = _late_window_base(run)
    branch = run.lanes_manifest.mission_branch
    if run.is_resume and (checkpoint is None or not base):
        _refuse_unbuildable_late_window(run)
        return
    if not base:
        # A first run with no recorded post-projection tip cannot prove what the coordination branch
        # held when the merge captured it, so there is no window to build. Refusing would strand a
        # Mission whose coordination placement did not resolve, because no `--resume` could clear it
        # either (`_refuse_unbuildable_late_window` refuses for the same reason). The loss is REAL and
        # still reachable in that corner: filed as #7121.
        return
    if checkpoint is None:
        # Unproducible in a current release (``coord_tip_after_projection`` is only ever captured from
        # the checkpoint ref), and unsound if it ever happened: the window would be read from a ref the
        # tip was not captured on. Leave such a run to the delete's own compare-and-swap.
        return
    coord_ref = checkpoint.ref
    if coord_ref not in (branch, f"refs/heads/{branch}"):
        return
    # Resolve the tip with the exit code kept: ``_resolve_ref_sha`` collapses "absent" and "unreadable"
    # into ``""``, which would let a git failure skip the window silently (and then flatten the marker
    # over a live branch). Only exit 1 -- the ref is absent or unresolvable, and the gate and the delete
    # read the ref directly -- is a no-op (#6871 review).
    probe, probe_out, _probe_err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"{coord_ref}^{{commit}}"],
        capture=True,
        check_return=False,
        cwd=run.main_repo,
    )
    if probe == 1:
        return
    projected_tip = probe_out.strip() if probe == 0 else ""
    if not projected_tip:
        raise CoordinationTeardownError(
            f"the coordination tip of {branch!r} could not be read (git rev-parse exited {probe}); "
            f"branch {branch!r} was NOT deleted and the mission's coordination marker was left intact. "
            "Re-run `spec-kitty consolidate --resume` once the git error is fixed."
        )
    # #7265: the window is read ONCE, at ``projected_tip`` (T). The projection and the proof below read
    # that SHA, never the live branch name, so a commit landing on the coordination branch mid-window is
    # neither partly projected nor judged under the wrong refusal kind: it is simply not in ``base..T``,
    # the guarded advance below sees the live ref != T, and the projection teardown gate refuses.
    target = run.lanes_manifest.target_branch
    try:
        if not _post_checkpoint_commit_shas(run.main_repo, base, projected_tip):
            return
        stranded = _unlanded_paths_outside_mission_dir(run, base, projected_tip)
        if stranded:
            raise CoordinationTeardownError(
                f"a commit on coordination branch {branch!r} changes files outside kitty-specs/{run.target_feature_dir.name}/ "
                f"that the target {target!r} does not have, and only Mission-directory files are landed during teardown: "
                f"{', '.join(stranded[:20])}{f' (and {len(stranded) - 20} more)' if len(stranded) > 20 else ''}. "
                f"Branch {branch!r} was NOT deleted. Move those files into the Mission directory, or land them on {target!r} yourself, "
                "then run `spec-kitty consolidate --resume` again."
            )
        events_path, status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
            checkpoint_sha=base,
            coord_ref=projected_tip,
        )
        late_paths = [run.main_repo / rel for rel in _post_checkpoint_mission_paths(run.main_repo, run.mission_slug, base, projected_tip)]
        # #6791: a gate matrix changed in this window is projected too. On a resume without a
        # verified landing the window starts at the PRE-mutation snapshot, so it reaches back to the
        # start of the merge (a first run, and a verified resume (#7491), start at the post-projection
        # coordination tip); a matrix in it is newer than the
        # checkpoint but not necessarily newer than the target's accept-time fill, so the
        # projection is guarded -- it never loses or overturns a judgement the target already holds.
        gate_matrix_paths = list(
            project_late_gate_matrix_commits(
                main_repo=run.main_repo,
                mission_slug=run.mission_slug,
                coord_ref=projected_tip,
                checkpoint_sha=base,
            )
        )
    except (EventLogMergeError, StoreError, UnicodeDecodeError) as exc:
        # An ordinary place to commit: a log the union cannot read must get the refusal and its
        # remedy, not a traceback.
        raise CoordinationTeardownError(
            f"the coordination branch's status event log cannot be merged with the target's ({escape(str(exc))}); "
            f"branch {branch!r} was NOT deleted and the mission's coordination marker was left intact. "
            "Repair or remove the line it names in the coordination worktree's status.events.jsonl and commit it, "
            f"then run `spec-kitty consolidate --resume`.{COORD_LATE_PROJECTION_REFUSED_SUFFIX}"
        ) from exc
    except GitCommandError as exc:
        raise CoordinationTeardownError(
            f"the coordination commits this teardown has to land could not be read ({escape(str(exc))}); "
            f"branch {branch!r} was NOT deleted. Re-run `spec-kitty consolidate --resume` once the git error is fixed."
        ) from exc
    except LateProjectionRefused as exc:
        raise CoordinationTeardownError(_late_projection_refusal(branch, target, exc)) from exc
    paths = [path for path in dict.fromkeys([events_path, status_path, *late_paths, *gate_matrix_paths]) if path.exists()]
    if paths and _paths_have_status_changes(run.main_repo, paths):
        late = "landed after the merge captured the coordination tip"
        _commit_projection_and_carry(run, paths, f"chore({run.mission_slug}): project coordination commits that {late} (#5570)")
        console.print(f"  Projected the coordination commit(s) that {late} onto {target}")
    # #6791: whatever the seams above could not carry is REFUSED here, before the branch
    # delete, instead of dying with the branch at exit 0.
    _assert_window_landed_in_every_mission_dir(run, base=base, projected_tip=projected_tip, branch=branch, target=target)
    _advance_approved_tip(run, coord_ref, projected_tip)


#: Printed by the repairs that ask the operator to commit ON the target (#7198 review). A commit there
#: moves the target off the verified landing, so the next `--resume` can stop at the branch-move guard --
#: the same continuation the unreadable-target remedy already spells out (TARGET_GATE_DOCUMENT_UNREADABLE).
_TARGET_COMMIT_BRANCH_MOVE_CAVEAT = (
    "Committing on {target!r} yourself moves it off the verified landing, so the next resume may stop at the "
    "branch-move guard. Its message prints a release command; run what each message names until the record clears, "
    "which can take a release for the coordination branch and for {target!r}. `--abort` removes that branch's "
    "worktree and keeps the branch, and `spec-kitty doctor coordination --fix --mission <mission>` clears a stale marker. Review "
    "`git log {target}..<coordination branch>` before you delete the branch by hand; after a squash it also lists "
    "the merge's own commits."
)


def _late_projection_remedy(refused: LateProjectionRefused, branch: str, target: str) -> str:
    """The action that actually CLEARS one late-projection refusal (#6791), per encoded kind.

    The single instruction this refusal used to give -- "land the file on the target yourself,
    then resume" -- is wrong for every case it can fire in: a coord-side deletion already HAS its
    content on the target (the projection cannot express the deletion, and the same refusal just
    repeats), and for an overturn that instruction writes the STALE coordination bytes over the
    established verdict the guard just protected. So each kind names its own repair, and the one
    that would overwrite evidence says explicitly not to do it.

    #7198 added two kinds on the same principle: a status event is proved by EVENT containment and the
    union stage reads the coordination WORKTREE's working tree (:func:`_status_event_ids_missing_from_target`),
    so its repair is about that copy; a non-coordination (primary) document is deliberately never
    projected (#5460), so only the target can author the change or the coordination branch can take it back.
    """
    if refused.kind is LateProjectionRefusalKind.EVIDENCE_WOULD_BE_LOST:
        return (
            f"change the coordination copy, not {target!r}: commit the newer judgement on {branch!r} "
            "(for an issue-matrix row, `spec-kitty agent issue-verdict --mission <handle> --issue <#NNN> "
            "--verdict <verdict> --actor <actor>`), or revert the coordination commit that regressed it. "
            f"Do NOT copy it onto {target!r}: that would write the stale bytes over the judgement this "
            "refusal just protected."
        )
    if refused.kind is LateProjectionRefusalKind.DELETION_CANNOT_BE_EXPRESSED:
        return (
            f"restore the deleted file on {branch!r} -- revert the commit that removed it, or "
            f"`git checkout <sha-before-the-deletion> -- <path>` there -- because a projection can only bring "
            f"content forward and {target!r} still holds the record."
        )
    if refused.kind is LateProjectionRefusalKind.COORD_GATE_DOCUMENT_UNREADABLE:
        return (
            f"rewrite the file on {branch!r} as the document its own writer produces (`spec-kitty agent "
            "issue-verdict` for issue-matrix.json, `spec-kitty accept` for acceptance-matrix.json), or revert the "
            "coordination commit that corrupted it."
        )
    if refused.kind is LateProjectionRefusalKind.TARGET_GATE_DOCUMENT_UNREADABLE:
        # Probed end to end: the reachable shape is a target document that is already unreadable when the
        # landing is verified, and repairing it is necessarily a commit ON the target -- which moves the
        # target off the verified landing, so the resume's branch-move guard is the next stop. Saying
        # "restore it from the target branch" would hand back the same unreadable bytes and repeat this
        # refusal, which is the broken remedy this branch exists to avoid.
        return (
            f"repair the target's copy and commit it on {target!r}: the guard will not overwrite the target's "
            "acceptance evidence until it can prove what that copy holds. That commit moves "
            f"{target!r} off the verified landing, so the next resume stops at the branch-move guard, whose "
            "message prints the command that releases the move and clears the record; delete the coordination "
            "branch by hand afterwards."
        )
    if refused.kind is LateProjectionRefusalKind.STATUS_EVENTS_NOT_LANDED:
        # #7198: the log is proved by EVENT containment, so the repair is about the copy the union stage
        # actually reads: the coordination worktree's WORKING-TREE log. That copy can hold events nobody has
        # committed yet, which the fold lands too (#7265 squad), so the repair ADDS the missing lines and never
        # replaces the file -- neither the worktree's copy nor the target's.
        return (
            f"add the missing events to the coordination worktree's working-tree status.events.jsonl, then re-run: "
            f"the union stage folds that working-tree copy, not the coordination branch's commits, which is how the "
            f"events came to be missing. Save a copy of that file first, then append each line of `git show "
            f"{branch}:<the log named above>` whose event_id it does not already hold, and keep every line it has. "
            f"Do NOT overwrite it with the branch file or check the branch file out over it: the working-tree log can "
            f"hold events not committed anywhere yet. Do NOT overwrite {target!r}'s log either: that would drop the "
            f"events {target!r} already holds. To land them on {target!r} yourself instead, append them to its log "
            f"the same way, rematerialize status.json from the union and commit. "
            f"{_TARGET_COMMIT_BRANCH_MOVE_CAVEAT.format(target=target)}"
        )
    if refused.kind is LateProjectionRefusalKind.STATUS_LOG_NOT_RECONCILABLE:
        # #7198 review: an unparseable log and two payloads for one event id are NOT the missing-event case.
        # Checking the same bytes out into the worktree would hand the union the same corruption, so the repair
        # is on the branch itself, and it is a revert or a rewrite -- not a checkout.
        return (
            f"repair the coordination branch's status.events.jsonl, then re-run: it must parse as JSONL events and it "
            f"must not carry an event id with different bytes than {target!r}'s log, because the canonical union "
            f"refuses that pair. Revert the commit that corrupted or forked it, or rewrite the event on {branch!r} so "
            f"the two agree."
        )
    if refused.kind is LateProjectionRefusalKind.NON_COORDINATION_RECORD_NOT_LANDED:
        # #7198: a primary/unclassified document is never projected (#5460) -- the target authors its own copy
        # after the checkpoint (mission-number bake, baseline stamp), so the repairs are "merge your change into
        # the target's copy" and "revert the coordination copy". A whole-file checkout would overwrite exactly the
        # fields the projection refuses to touch (#7198 review).
        return (
            f"land the change on {target!r} yourself, or revert it on {branch!r}: the projection cannot carry "
            f"{target!r}'s own files, because the merge authors them there after the checkpoint. Merge your intended "
            f"change into {target!r}'s copy BY HAND and commit it -- a whole-file `git checkout {branch} -- <path>` "
            f"would overwrite the mission number, baseline stamp and marker {target!r} owns. If the change was never "
            f"meant to exist, revert the coordination commit that made it. A path under a composed `<slug>-<mid8>` "
            f"directory is judged against the same relative path under {target!r}'s own Mission directory. "
            f"{_TARGET_COMMIT_BRANCH_MOVE_CAVEAT.format(target=target)}"
        )
    # LateProjectionRefusalKind.RECORD_NOT_LANDED -- the one case the old instruction was written for:
    # the record exists on the coordination branch and the target does not have it.
    return (
        f"land the named record on {target!r} from {branch!r} (`git checkout {branch} -- <path>` in the {target!r} "
        "checkout, then commit it), or, if it must not exist at all, delete it on both branches. A record under a "
        "composed `<slug>-<mid8>` directory is judged against the same relative path under the target's own Mission "
        f"directory, so copy it there instead, or revert it on {branch!r}."
    )


def _late_projection_refusal(branch: str, target: str, refused: LateProjectionRefused) -> str:
    """Operator-facing refusal for a late coordination commit that cannot be landed (#6791).

    The coordination triple stays together -- branch, worktree and marker -- and the landing
    is NOT rolled back (teardown runs after the rollback door), so the operator's work is
    still there to repair. The repair is spelled out per KIND (:func:`_late_projection_remedy`),
    and ``spec-kitty consolidate --abort`` is ruled out by name: the landing is already verified,
    so an abort keeps it and refuses too. Exit code is 1.
    """
    return (
        f"a coordination commit on {branch!r} cannot be landed on {target!r}: {refused}. "
        f"Branch {branch!r} was NOT deleted, its worktree and the mission's coordination marker were left intact, "
        "and the verified landing was not rolled back. `spec-kitty consolidate` exits 1 for this refusal, and "
        "`spec-kitty consolidate --abort` does not clear it (the landing is already verified, so an abort keeps it "
        f"and refuses). To clear it: {_late_projection_remedy(refused, branch, target)} "
        f"Then run `spec-kitty consolidate --resume` again.{COORD_LATE_PROJECTION_REFUSED_SUFFIX}"
    )


COORD_STATUS_FOLD_SUBJECT = "chore({slug}): fold coordination status before flatten (#3272)"


def _fold_coord_status_before_flatten(run: _MergeRunState) -> None:
    """Commit every coord status event to the primary corpus before deleting its branch.

    Reads the coordination worktree's WORKING-TREE log (``run.feature_dir``), not the
    committed coordination tip, so uncommitted seed events are folded too. A git, alias-proof or
    I/O failure is wrapped as :class:`CoordinationTeardownError` (branch kept);
    any other error, notably a workflow-mutation policy refusal, propagates unchanged.
    """
    source = run.feature_dir / "status.events.jsonl"
    target = run.target_feature_dir / "status.events.jsonl"
    if source == target or not source.is_file() or not source.read_bytes().strip():
        return
    target_branch = run.lanes_manifest.target_branch
    try:
        events_path, status_path = _project_status_bookkeeping_to_target(
            main_repo=run.main_repo,
            mission_slug=run.mission_slug,
            status_feature_dir=run.feature_dir,
        )
        assert_alias_events_preserved(alias_events_path=source, primary_events_path=events_path)
        paths = [events_path, status_path]
        if _paths_have_status_changes(run.main_repo, paths):
            _commit_projection_and_carry(run, paths, COORD_STATUS_FOLD_SUBJECT.format(slug=run.mission_slug))
            console.print(f"  Folded the coordination status onto {target_branch} before teardown")
    except (GitCommandError, AliasStatusEventsNotPreserved, OSError) as exc:
        raise CoordinationTeardownError(
            f"coordination status could not be folded onto {target_branch!r} ({escape(str(exc))}); "
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
        # #7201: the persist leg commits the retrospective BEFORE the worktree is
        # destroyed, so it must target the branch this run actually landed on.
        # Placement resolution would read the mission's `meta.json`
        # `target_branch`, which is STALE for a `--target <branch>` consolidation:
        # the checkout's HEAD is the resolved target, so the destination and HEAD
        # disagree and `safe_commit` correctly refuses (`SafeCommitHeadMismatch`),
        # leaving both artifacts uncommitted. Same authoritative override the
        # housekeeping commit above already threads.
        destination_ref=run.lanes_manifest.target_branch,
    )
    logger.debug(
        "Coordination topology teardown for %s-%s completed",
        run.mission_slug,
        _mid8_for_teardown,
    )
    return approved_branch_tip


def _topic_primary_window(run: _MergeRunState) -> tuple[str, str, str] | None:
    """``(base, topic_ref, target)`` for a default Mission whose topic branch still exists, else ``None``.

    With no recorded anchor (no checkpoint on a fresh run, no persisted pre-mutation tip on a
    ``--resume``) the window starts at ``merge-base(topic, target)`` instead of being skipped;
    no merge base refuses (:class:`CoordinationTeardownError`, branch kept) rather than failing open.
    """
    from specify_cli.lanes.single_branch_landing import lands_topic_branch

    branch = run.lanes_manifest.mission_branch
    target = run.lanes_manifest.target_branch
    if not lands_topic_branch(run.main_repo, run.lanes_manifest):
        return None
    if not _resolve_ref_sha(run.main_repo, f"refs/heads/{branch}"):
        return None
    base = _topic_primary_window_base(run) or git_merge_base(run.main_repo, f"refs/heads/{branch}", target)
    if base is None:
        raise CoordinationTeardownError(
            f"topic branch {branch!r} has no recorded anchor and no merge base with {target!r}, so its PRIMARY changes cannot be "
            f"compared; the branch was NOT deleted. Review `git diff {target} {branch}`, land them on {target!r}, then run "
            "`spec-kitty consolidate --resume`."
        )
    return base, f"refs/heads/{branch}", target


def _topic_primary_window_base(run: _MergeRunState) -> str | None:
    """The topic tip the PRIMARY comparison starts at: the checkpoint, or on a ``--resume`` the persisted pre-mutation tip.

    A resume's in-memory checkpoint is read at resume start, after the interrupted run's late
    commits, so it would hide them; the persisted ``state.pre_mutation_coord_sha`` does not.
    """
    if run.is_resume:
        resume_base: str | None = run.state.pre_mutation_coord_sha
        return resume_base
    checkpoint = run.coord_checkpoint
    return None if checkpoint is None else str(checkpoint.sha)


def _unlanded_topic_primary(run: _MergeRunState, window: tuple[str, str, str]) -> list[str]:
    """The window's unlanded PRIMARY paths; an unreadable diff refuses (branch kept)."""
    base, topic_ref, target = window
    try:
        unlanded: list[str] = unlanded_topic_primary_paths(run.main_repo, run.mission_slug, base=base, topic_ref=topic_ref, target_ref=target)
    except GitCommandError as exc:
        raise CoordinationTeardownError(
            f"the PRIMARY changes on topic branch {run.lanes_manifest.mission_branch!r} could not be compared with {target!r} "
            f"({escape(str(exc))}); the branch was NOT deleted. Re-run `spec-kitty consolidate --resume` once the git error is fixed."
        ) from exc
    return unlanded


def _refuse_unlanded_topic_primary(run: _MergeRunState) -> None:
    """FR-062: refuse the coordination teardown while a default Mission's topic branch holds unlanded PRIMARY changes.

    A ``topology_source: default`` Mission settled to ``lanes_with_coord`` keeps its PRIMARY
    partition on its topic branch, which is also the coordination branch this teardown deletes.
    The landing (``integrate_mission_into_target``, the one landing authority) carried the topic
    tip it read; a PRIMARY commit made after that read is excluded from the coordination
    projection (G2) and used to die with the branch at exit 0. This is a pure check: anything
    unlanded REFUSES through :class:`CoordinationTeardownError` (exit 1) with the coordination
    triple kept, and nothing is written. Explicit and legacy Missions are unchanged.
    """
    window = _topic_primary_window(run)
    if window is None:
        return
    unlanded = _unlanded_topic_primary(run, window)
    if not unlanded:
        return
    target = window[2]
    branch = run.lanes_manifest.mission_branch
    raise CoordinationTeardownError(
        f"topic branch {branch!r} still holds PRIMARY change(s) the target {target!r} does not carry: {', '.join(unlanded[:20])}. "
        f"Branch {branch!r}, its worktree and the coordination marker were NOT removed. "
        f"Review them with `git diff {target} {branch}`, land them on {target!r}, then run `spec-kitty consolidate --resume`."
    )


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
    _refuse_unlanded_topic_primary(run)
    _land_late_coordination_commits(run)
    _fold_coord_status_before_flatten(run)
    pre_teardown_tip = _mission_branch_tip(run)
    approved_tip = _teardown_coord_worktree(run) or pre_teardown_tip
    refusal = _refused_mission_branch_delete(run, approved_tip)
    if refusal is not None:
        raise CoordinationTeardownError(_branch_kept_after_teardown_message(run, refusal))
    _flatten_coordination_metadata_after_branch_delete(run)


def _branch_kept_after_teardown_message(run: _MergeRunState, refusal: str) -> str:
    """Describe a coordination branch the teardown could not delete, from what is true now (#4380 item 2).

    The worktree leg ran first, so the coordination worktree is usually gone already. The text names
    the worktrees that still have the branch checked out (read through the one checkout authority,
    :func:`~specify_cli.git.ref_advance.worktrees_with_branch_checked_out`), or says that none does
    and the compare-and-swap delete itself refused, quoting *refusal* (git's own text) so the
    operator sees it whatever the logging setup.
    """
    branch = run.lanes_manifest.mission_branch
    kept = f"coordination branch {branch!r} still exists after teardown; it and the mission's coordination marker were kept."
    try:
        holders = worktrees_with_branch_checked_out(run.main_repo, branch)
    except RefAdvanceError as exc:
        return f"{kept} Its worktrees could not be listed ({escape(str(exc))}); check `git worktree list`, then re-run `spec-kitty consolidate --resume`."
    if holders:
        where = ", ".join(str(path) for path in holders)
        return f"{kept} It is still checked out in {where}. Remove that worktree (`git worktree list`), then re-run `spec-kitty consolidate --resume`."
    return (
        f"{kept} No worktree has it checked out any more: the compare-and-swap delete of the branch refused "
        f"({escape(refusal)}). Re-run `spec-kitty consolidate --resume`."
    )


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
    from specify_cli.mission_metadata import locked_update_meta

    if not lands_mission_branch(run.main_repo, run.lanes_manifest):
        return
    feature_dir = run.target_feature_dir
    if not (feature_dir / "meta.json").exists():
        return
    cleared = False

    def drop_mission_branch(meta: dict[str, Any]) -> bool:
        nonlocal cleared
        if "mission_branch" not in meta:
            return False
        del meta["mission_branch"]
        cleared = True
        return True

    try:
        locked_update_meta(feature_dir, drop_mission_branch, validate=False)
    except MissionMetaReadError:
        return  # unreadable meta.json: nothing to clear, and a completed merge is never aborted for it
    if not cleared:
        return
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


def _tombstone_removed_lane_contexts(run: _MergeRunState, report: LaneCleanupReport) -> None:
    """FR-005/LC-6 (#1842 WP03): tombstone the workspace context of each lane whose worktree is gone.

    Nested under ``remove_worktree`` as before: the context JSON *describes* the worktree, so a
    retained worktree keeps it, and so does a KEPT lane (its worktree survived). The filename
    is the created worktree's name, the string ``save_context`` wrote.
    """
    from specify_cli.workspace import delete_context, get_context_path

    if not run.remove_worktree:
        return
    tombstoned: list[Path] = []
    for result in report.results:
        worktree = result.item.worktree
        if worktree is None or worktree.exists():
            continue
        context_path = get_context_path(run.main_repo, worktree.name)
        if delete_context(run.main_repo, worktree.name):
            tombstoned.append(context_path)
    _commit_tombstoned_workspace_contexts(run, tombstoned)


def _commit_tombstoned_workspace_contexts(run: _MergeRunState, tombstoned: list[Path]) -> None:
    """Persist the workspace-context tombstones this cleanup phase just made (#6450).

    This phase runs AFTER ``_phase_commit_and_assert`` — the run's only
    bookkeeping commit — so a tombstoned context that the project TRACKS
    (``.kittify/workspaces/*.json`` is tracked in some consumer projects,
    ignored in this repository) would otherwise leave a tracked-file deletion
    in the working tree of a merge that reported success. The deletion is
    concluded in its own scoped bookkeeping commit through the ONE sanctioned
    protected-flow seam.

    Only paths whose removal git actually sees as a change are committed: a
    deletion of an untracked context is not a content change, so it must not
    create an empty commit (``_paths_have_status_changes`` is the same
    predicate ``_phase_commit_and_assert`` uses). Nothing tracked removed
    means no commit at all.

    A failure here must not fail an already-landed merge; it is reported and
    the run keeps its existing teardown behaviour. Publishing the commit on a
    ``--push`` run is not done here: ``_phase_push_cleanup_commits`` pushes once
    after the whole cleanup phase, warn-only.
    """
    if not tombstoned:
        return
    deleted = [path for path in tombstoned if _paths_have_status_changes(run.main_repo, [path])]
    if not deleted:
        return
    try:
        landed = commit_merge_bookkeeping(
            repo_root=run.main_repo,
            worktree_root=run.main_repo,
            mission_slug=run.mission_slug,
            branch=run.lanes_manifest.target_branch,
            destination_ref_override=run.lanes_manifest.target_branch,
            message=f"chore({run.mission_slug}): tombstone lane workspace contexts",
            paths=tuple(deleted),
        )
    except _BOOKKEEPING_COMMIT_ERRORS as exc:  # teardown is post-landing; warn, never fail the merge
        names = ", ".join(str(path.relative_to(run.main_repo)) for path in deleted)
        logger.warning("Could not commit tombstoned workspace contexts (%s): %s", names, exc)
        console.print(f"  [yellow]Warning:[/yellow] tombstoned workspace context(s) {escape(names)} were not committed: {escape(str(exc))}")
        return
    # FR-035: a ``--resume`` after a kill here must still recognise the verified landing.
    _carry_pass_anchor_over_own_commit(run, landed.sha)


def _mark_cleanup_started(run: _MergeRunState) -> None:
    """FR-035: persisted before the first lane leg, so a ``--resume`` after a kill goes straight to cleanup."""
    if not run.state.cleanup_started:
        run.state.cleanup_started = True
        save_state(run.state, run.main_repo)


def _lane_cleanup_report(run: _MergeRunState) -> LaneCleanupReport:
    """The lane legs (S5): one module, kept lanes reported, never raised after the verified landing."""
    lanes_manifest = run.lanes_manifest
    expected = cleanup_expected_tips(run.state.pre_mutation_refs, run.state.lane_rebase_moves)  # #6736
    items = plan_lane_cleanup(lanes_manifest, repo_root=run.main_repo, expected_tips=expected)
    retention = LaneRetention(remove_worktree=run.remove_worktree, delete_branch=run.delete_branch)
    if not items:
        return LaneCleanupReport(results=())
    _mark_cleanup_started(run)
    delay = _worktree_removal_delay()
    # #5965 / #5966: the guard decides disposability from the checkout ROLE and the Mission's
    # STORED topology, so a lane worktree holding uncommitted rework is kept, not destroyed.
    context = residue_context_or_strictest(run.main_repo, run.target_feature_dir.name, CheckoutRole.LANE)
    remover = GuardedLaneRemover(
        run.main_repo,
        context=context,
        after_worktree_removed=(lambda: time.sleep(delay)) if delay > 0 else None,
        mission_slug=lanes_manifest.mission_slug,
    )
    landing = LocalTargetAtPass(target_ref=lanes_manifest.target_branch, passed_sha=run.state.reconciliation_passed_target_sha or "")
    report = lane_cleanup.apply(items, remover, landing=landing, retention=retention)
    _tombstone_removed_lane_contexts(run, report)
    return report


def _print_lane_cleanup(report: LaneCleanupReport) -> None:
    for line in report.render_lines():
        console.print(line, markup=False, soft_wrap=True)


def _coordination_refused_report(run: _MergeRunState) -> LaneCleanupReport:
    """Every lane, untouched, after a coordination teardown refusal (FR-031: lanes stay as evidence)."""
    items = plan_lane_cleanup(run.lanes_manifest, repo_root=run.main_repo)
    return lane_cleanup.kept_after_coordination_refusal(items)


def _phase_cleanup_worktrees_and_branches(run: _MergeRunState) -> None:
    """Coordination teardown first, then the lane legs (FR-031); the record is cleared after this phase.

    A coordination refusal keeps its own exception and exit code (S10 owns them); every lane is
    then left in place and reported as kept. After the coordination triple came down, the lane
    legs never raise: a lane the remover cannot remove is kept and reported (FR-032).
    """
    # -- #3131 T008: MISSION/coordination branch + marker + worktree --
    # Topology-aware and (for coord) coupled under ``teardown_coordination``;
    # see ``_cleanup_mission_branch_and_coordination`` for the INV-2 rationale.
    try:
        _cleanup_mission_branch_and_coordination(run)
    except Exception:
        _print_lane_cleanup(_coordination_refused_report(run))
        raise
    run.lane_cleanup = _lane_cleanup_report(run)
    _print_lane_cleanup(run.lane_cleanup)
