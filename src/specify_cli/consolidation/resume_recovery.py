"""Resume recovery for a checkout that only lags its own HEAD (#4997/#5571).

Classifies a pre-mutation dirty refusal (repository root checkout or coordination
worktree), prints lag-aware advice instead of the generic "commit" remedy, and on
``--resume`` repairs a provably pure behind-own-HEAD lag with ``git reset --hard
HEAD``. :func:`_pre_mutation_safety_preflight_with_recovery` wraps the entry
preflight with that one recovery attempt.

Moved from ``consolidation/executor.py`` by epic #2026 with no logic change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.markup import escape

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

from specify_cli.cli.console import console
from specify_cli.core.git_ops import run_command
from specify_cli.core.paths import (
    MissionMetaReadError,
    RetentionDecision,
)
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    DestructiveOpRefused,
)
from specify_cli.git.ref_advance import RefAdvanceError

from specify_cli.consolidation.state import (
    ConsolidationState,
    ConsolidationStateReadError,
    load_state,
)
from specify_cli.consolidation.entry_preflight import (
    _pre_mutation_safety_preflight,
    _resolve_coord_worktree_for_preflight,
)


@dataclass(frozen=True)
class _LagCheckout:
    """The checkout a pre-mutation dirty-guard refusal names, as a candidate behind-own-HEAD lag (#4997 / #5571 / #5613).

    The fields select which persisted anchor proves the lag: the repository root checkout
    is proven against ``pre_mutation_target_sha``, the coordination worktree against
    ``pre_mutation_coord_sha``, and any other worktree (``branch`` set: a mission worktree,
    or a lane worktree when ``lane``) against its own branch's entry in the pre-mutation
    snapshot (``pre_mutation_refs``). One shape, so the advice and the in-place recovery
    share a single classifier instead of a per-checkout copy.
    """

    path: Path
    coordination: bool
    branch: str | None = None
    lane: bool = False

    def __post_init__(self) -> None:
        """Reject a checkout that claims two roles: each role is proven against a different anchor."""
        if self.coordination and (self.branch is not None or self.lane):
            raise ValueError("a coordination worktree is anchored on pre_mutation_coord_sha: it takes no branch and is never a lane")
        if self.lane and self.branch is None:
            raise ValueError("a lane worktree is anchored on its own branch: branch is required")

    @property
    def is_root(self) -> bool:
        return not self.coordination and self.branch is None

    @property
    def label(self) -> str:
        if self.coordination:
            return "coordination worktree"
        if self.branch is None:
            return "primary checkout"
        return "lane worktree" if self.lane else "mission worktree"

    def base_sha(self, state: ConsolidationState | None) -> str | None:
        """The persisted pre-mutation tip this checkout's lag is proven against (``None`` on a fresh merge)."""
        if state is None:
            return None
        anchor: str | None
        if self.coordination:
            anchor = state.pre_mutation_coord_sha
        elif self.branch is None:
            anchor = state.pre_mutation_target_sha
        else:
            anchor = state.pre_mutation_refs.get(self.branch)
        return anchor

    def lane_branch(self, mission_branch: str) -> str:
        """The branch whose ancestry classifies this checkout's dirt (``classify_resume_dirty_remedy``).

        The root and the coordination worktree classify on the mission branch, as before.
        Any other worktree classifies on the branch it has checked out: that is trivially an
        ancestor of its own HEAD, so the content proof against :meth:`base_sha` is the only
        real gate there (a branch absent from the snapshot has no anchor and is never a lag).
        """
        return self.branch or mission_branch


def _lag_checkout_for_refusal(
    exc: DestructiveOpRefused,
    main_repo: Path,
    coord_worktree: Path | None,
    *,
    mission_branch: str | None = None,
) -> _LagCheckout | None:
    """Map a pre-mutation dirty refusal onto the checkout that may merely lag its HEAD, else ``None``.

    ``MERGE_UNSAFE_PRIMARY_DIRTY`` is the repository root checkout. The generic
    ``MERGE_UNSAFE_WORKTREE_DIRTY`` maps to the coordination worktree when the refusal's
    own ``worktree_path`` IS the resolved coordination worktree. With ``mission_branch``
    given (#5613), any other refused worktree maps to the branch it has checked out: a
    mission worktree when that is the mission branch, else a lane worktree. Without it,
    or when the path has no branch checked out, there is no candidate.
    """
    code = getattr(exc, "error_code", None)
    if code == MERGE_UNSAFE_PRIMARY_DIRTY:
        return _LagCheckout(main_repo, coordination=False)
    refused = getattr(exc, "worktree_path", None)
    if code != MERGE_UNSAFE_WORKTREE_DIRTY or refused is None:
        return None
    if coord_worktree is not None and Path(refused).resolve() == coord_worktree.resolve():
        return _LagCheckout(coord_worktree, coordination=True)
    if mission_branch is None:
        return None
    from specify_cli.consolidation.preflight import checked_out_branch

    branch = checked_out_branch(Path(refused))
    if branch is None:
        return None
    return _LagCheckout(Path(refused), coordination=False, branch=branch, lane=branch != mission_branch)


def _coord_worktree_for_refusal(
    exc: DestructiveOpRefused,
    main_repo: Path,
    mission_slug: str,
    primary_meta_dir: Path,
) -> Path | None:
    """The mission's coordination worktree when ``exc`` is a generic worktree-dirty refusal, else ``None``.

    Resolved lazily (only for ``MERGE_UNSAFE_WORKTREE_DIRTY``) through the SAME resolver
    the preflight guard used, so refusal handling never disagrees with the guard about
    which worktree is the coordination worktree. An unreadable ``meta.json`` yields
    ``None`` (no lag candidate; the original refusal stands).
    """
    if getattr(exc, "error_code", None) != MERGE_UNSAFE_WORKTREE_DIRTY:
        return None
    try:
        candidate = _resolve_coord_worktree_for_preflight(main_repo, mission_slug, primary_meta_dir)
    except MissionMetaReadError:
        return None
    return candidate if candidate is not None and candidate.exists() else None


_LAG_GUIDANCE_HEADING = "[yellow]Resume recovery guidance (behind-own-HEAD / interrupted reset detected):[/yellow]"
_FOLD_GUIDANCE_HEADING = "[yellow]Recovery guidance (an earlier run was interrupted inside the one-directory fold):[/yellow]"
_MERGE_ABORTED_NOTE = "[yellow]Merge aborted before any state change.[/yellow] Resolve the reported condition, then re-run [bold]spec-kitty consolidate[/bold]."


def _refusal_deferring_to_guidance(exc: DestructiveOpRefused) -> DestructiveOpRefused:
    """``exc`` with its generic "commit, stash, or revert" remedy replaced by a pointer to the guidance (#5613).

    For a checkout that lags its own HEAD (or whose reset was interrupted), committing
    records the staged deletions and reverts the integrated lanes. The refusal keeps its
    code, worktree and dirty entries; only the remedy line changes. Advisory only.
    """
    return DestructiveOpRefused(
        error_code=exc.error_code,
        worktree_path=exc.worktree_path,
        current_branch=exc.current_branch,
        expected_branch=exc.expected_branch,
        dirty_entries=exc.dirty_entries,
        remediation="follow the resume recovery guidance below.",
    )


def _lag_guidance(checkout: _LagCheckout, *, mission_branch: str, base_sha: str | None) -> tuple[list[str], bool] | None:
    """``(guidance lines, checkout carries an operator edit)`` for a lagging / lock-blocked checkout, else ``None``.

    ``None`` means the stock remedy already in the refusal stands (genuine local work, or
    no persisted anchor proving a lag -- #4933). A lag carrying an operator edit gets the
    save-the-edit-first guidance for every worktree; the repository root keeps its stock
    remedy there (#4933 pin).
    """
    from specify_cli.consolidation.preflight import (
        ResumeRemedyKind,
        classify_resume_dirty_remedy,
        has_unrefreshed_head_advance,
        is_pure_behind_head_lag,
        lag_with_edit_guidance,
    )

    remedy = classify_resume_dirty_remedy(checkout.path, lane_branch=checkout.lane_branch(mission_branch))
    proven_behind_head = remedy.kind is ResumeRemedyKind.BEHIND_OWN_HEAD and is_pure_behind_head_lag(checkout.path, base_sha=base_sha)
    if remedy.kind is ResumeRemedyKind.BLOCKED_INDEX_LOCK or proven_behind_head:
        return remedy.remediation, False
    if base_sha and not checkout.is_root and has_unrefreshed_head_advance(checkout.path, base_sha=base_sha):
        return lag_with_edit_guidance(checkout.path, label=checkout.label, base_sha=base_sha), True
    return None


def _report_interrupted_alias_fold(exc: DestructiveOpRefused, main_repo: Path, mission_slug: str | None) -> bool:
    """Print the abort-and-restart guidance when ``exc`` is the state an interrupted fold leaves (#5748); say whether it did.

    Only a ``MERGE_UNSAFE_PRIMARY_DIRTY`` refusal can be that state (the fold unlinks the
    composed directory's coordination files in the repository root checkout), and only
    deletions of exactly those files qualify
    (:func:`~specify_cli.consolidation.preflight.interrupted_alias_fold_guidance`); the
    refusal keeps its code and entries, and its generic "commit, stash, or revert" remedy
    line is replaced by a pointer to the guidance, as for a lagging checkout.
    """
    if mission_slug is None or exc.error_code != MERGE_UNSAFE_PRIMARY_DIRTY:
        return False
    from specify_cli.consolidation.preflight import interrupted_alias_fold_guidance

    lines = interrupted_alias_fold_guidance(exc.dirty_entries, main_repo=main_repo, mission_slug=mission_slug)
    if lines is None:
        return False
    console.print(f"[red]Error:[/red] {_refusal_deferring_to_guidance(exc)}")
    console.print(_FOLD_GUIDANCE_HEADING)
    for line in lines:
        console.print(f"  • {line}", markup=False)
    return True


def _report_pre_mutation_refusal(
    exc: DestructiveOpRefused,
    main_repo: Path,
    *,
    mission_branch: str,
    base_sha: str | None = None,
    coord_worktree: Path | None = None,
    mission_slug: str | None = None,
) -> None:
    """Print the pre-mutation refusal, upgrading a behind-own-HEAD remedy (WP05 / #4982/#4997/#5571/#5613).

    WP10 integration: a dirty-PRIMARY refusal may actually be the checkout sitting
    BEHIND ITS OWN HEAD — a prior terminus advanced the target ref but the
    ``reset --hard`` that refreshes the checkout never ran, so the already-integrated
    lane's files read as local changes. The generic "commit/stash/revert" remedy is
    DANGEROUS there (recording them reverts the merge). Route a
    ``MERGE_UNSAFE_PRIMARY_DIRTY`` refusal through
    :func:`~specify_cli.consolidation.preflight.classify_resume_dirty_remedy` so a
    behind-own-HEAD (or interrupted-``reset``) state gets the safe reset-to-HEAD
    remedy instead. Advisory only — the refusal still aborts fail-closed BEFORE any
    mutation (NFR-001); this only changes the printed guidance.

    #5571 / #5613: every worktree a consolidation advances lags the same way (its branch
    advanced, its refresh never ran), so a ``MERGE_UNSAFE_WORKTREE_DIRTY`` refusal naming
    the coordination worktree, a mission worktree or a lane worktree takes the same path,
    proven against that checkout's own persisted anchor (``base_sha``). Whenever lag
    guidance is printed the refusal's generic "commit" remedy line is replaced
    (:func:`_refusal_deferring_to_guidance`), so a lagging or lock-blocked checkout is
    never told to commit. A worktree that is behind its HEAD but NOT a provably pure lag
    (a genuine edit is mixed in) is never reset; it gets save-the-edit-first guidance
    (:func:`~specify_cli.consolidation.preflight.lag_with_edit_guidance`).

    #4933: on a FRESH consolidation the mission branch is created off the target
    and never advances until the lanes merge, so it is trivially "already an
    ancestor of HEAD" — the lane-ancestry-only ``BEHIND_OWN_HEAD`` classification
    misfires on every dirty refusal, not just a genuinely interrupted terminus.
    Printing the reset-to-HEAD guidance there tells the operator to run
    ``git reset --hard HEAD``, which destroys the very user edit (e.g. a dirty
    ``src/app/meta.json``) the refusal protects. The upgraded guidance is now gated on
    :func:`~specify_cli.consolidation.preflight.is_pure_behind_head_lag`, the
    content proof #4997 already uses for the ``--resume`` auto-recovery path
    (:func:`_recover_behind_head_primary_on_resume`): it needs a persisted
    ``ConsolidationState.pre_mutation_target_sha`` (``base_sha``) that is a STRICT
    ancestor of HEAD with a byte-identical tree/index and no obstructing untracked
    path. A fresh consolidation has no persisted state (``base_sha=None``), so the
    predicate is fail-closed False and this always falls through to the safe
    commit/stash/revert remedy already present in ``str(exc)``. ``BLOCKED_INDEX_LOCK``
    is unaffected -- it never claims a specific working-tree state to reset into, so
    it carries no #4933 hazard and stays gated on classification alone.
    """
    checkout = _lag_checkout_for_refusal(exc, main_repo, coord_worktree, mission_branch=mission_branch)
    guidance = _lag_guidance(checkout, mission_branch=mission_branch, base_sha=base_sha) if checkout is not None else None
    if guidance is None and _report_interrupted_alias_fold(exc, main_repo, mission_slug):
        return
    if guidance is None:
        console.print(f"[red]Error:[/red] {exc}")
        console.print(_MERGE_ABORTED_NOTE)
        return
    lines, carries_edit = guidance
    console.print(f"[red]Error:[/red] {_refusal_deferring_to_guidance(exc)}")
    console.print(_LAG_GUIDANCE_HEADING)
    for line in lines:
        console.print(f"  • {line}")
    if carries_edit:
        console.print(_MERGE_ABORTED_NOTE)


def _load_state_on_refusal_path(main_repo: Path, canonical_id: str) -> ConsolidationState | None:
    """Read the persisted merge state on a pre-mutation REFUSAL path, fail-closed (N6).

    A corrupt ``state.json`` raises :class:`ConsolidationStateReadError`; on the
    refusal path that exception would REPLACE the dirty-tree refusal the operator
    needs to see. Treat it as "no provable resume state" instead: ``None`` means no
    auto-recovery and no reset-to-HEAD guidance (the safe commit/stash/revert remedy
    already in the refusal message stands). The corruption is still surfaced as a
    warning so it is not silently lost; a later ``--resume`` hits the loud
    fail-closed read on its own normal path.
    """
    try:
        return load_state(main_repo, canonical_id)
    except ConsolidationStateReadError as exc:
        console.print(f"[yellow]Warning:[/yellow] ignoring unreadable merge state while reporting the refusal: {exc}")
        return None


def _recover_behind_head_primary_on_resume(
    exc: DestructiveOpRefused,
    main_repo: Path,
    canonical_id: str,
    *,
    mission_branch: str,
    coord_worktree: Path | None = None,
) -> bool:
    """Recover a provably-pure behind-own-HEAD checkout in place, ON A RESUME (#4997 / #5571 / #5613).

    Despite its name (kept for its callers), this recovers every checkout a consolidation
    advances: the repository root checkout, the coordination worktree, a mission worktree
    and a lane worktree. :class:`_LagCheckout` selects the anchor each is proven against.

    The pre-mutation primary dirty guard refuses ``MERGE_UNSAFE_PRIMARY_DIRTY`` when the
    checkout carries staged deletions. After an interrupted terminus that advanced the
    target ref but never ran the checkout's ``reset --hard`` (#1826), those deletions are
    the mission's already-integrated files read in reverse — a pure lag, NOT genuine local
    work. Instead of aborting (which strands the merge, or invites the catastrophic
    "Commit" mis-remedy), a ``--resume`` repairs it here: ``git reset --hard HEAD``.

    #5571: the coordination worktree lags identically when the mission branch advanced but
    its worktree refresh never ran, so a ``MERGE_UNSAFE_WORKTREE_DIRTY`` refusal naming
    ``coord_worktree`` is recovered by the SAME proof (parametrised by checkout, not
    copied), against ``pre_mutation_coord_sha`` instead of ``pre_mutation_target_sha``.

    #5613: a mission worktree (a worktree with the mission branch checked out on a
    ``lanes`` mission) and a lane worktree lag the same way and are recovered by the same
    proof, each against its own branch's ``pre_mutation_refs`` entry. A worktree whose
    branch is absent from that snapshot has no anchor and is never reset.

    Fail-closed, and NEVER on a fresh merge:

    * only on a ``--resume`` (a persisted :class:`ConsolidationState` exists);
    * only when :func:`~specify_cli.consolidation.preflight.classify_resume_dirty_remedy` reports
      ``BEHIND_OWN_HEAD`` (lane-ancestry) AND
      :func:`~specify_cli.consolidation.preflight.is_pure_behind_head_lag` proves the working tree
      AND index are byte-identical to the persisted pre-mutation base with no
      untracked file obstructing a restored path (so the reset destroys nothing genuine —
      the data-loss hole a lane-ancestry-only gate would leave).

    Returns ``True`` iff it reset the checkout (the caller re-runs the preflight once and
    continues); ``False`` for every non-recoverable refusal (the caller aborts unchanged).
    """
    checkout = _lag_checkout_for_refusal(exc, main_repo, coord_worktree, mission_branch=mission_branch)
    if checkout is None:
        return False
    state = _load_state_on_refusal_path(main_repo, canonical_id)
    if state is None:
        return False  # fresh merge (or unreadable state): a dirty checkout is genuine, never auto-reset.
    from specify_cli.consolidation.preflight import (
        ResumeRemedyKind,
        classify_resume_dirty_remedy,
        is_pure_behind_head_lag,
    )

    remedy = classify_resume_dirty_remedy(checkout.path, lane_branch=checkout.lane_branch(mission_branch))
    if remedy.kind is not ResumeRemedyKind.BEHIND_OWN_HEAD:
        return False
    if not is_pure_behind_head_lag(checkout.path, base_sha=checkout.base_sha(state)):
        return False
    reset_ret, _out, reset_err = run_command(
        ["git", "reset", "--hard", "HEAD"],
        capture=True,
        check_return=False,
        cwd=checkout.path,
    )
    if reset_ret != 0:
        console.print(f"[red]Error:[/red] behind-own-HEAD recovery `git reset --hard HEAD` failed in {checkout.path}: {reset_err.strip()}")
        return False
    console.print(f"[yellow]Recovered a behind-own-HEAD {checkout.label} (git reset --hard HEAD over phantom staged deletions); continuing resume.[/yellow]")
    return True


def _pre_mutation_safety_preflight_with_recovery(
    main_repo: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest,
    canonical_id: str,
    primary_meta_dir: Path,
    retention: RetentionDecision,
) -> None:
    """Run the pre-mutation safety preflight, with #4997 / #5613 behind-own-HEAD resume recovery.

    On a ``DestructiveOpRefused``, a ``--resume`` first tries to recover a provably-pure
    behind-own-HEAD checkout (:func:`_recover_behind_head_primary_on_resume`: the primary,
    the coordination worktree, a mission worktree or a lane worktree) and re-runs the
    preflight. Each checkout is recovered at most once, so the loop ends after at most one
    pass per checkout; every non-recoverable refusal (and every fresh-merge refusal) aborts
    fail-closed with the reported remediation. Kept as one helper so the outer
    :func:`_run_lane_based_consolidation` stays within the complexity ceiling.
    """
    # A readable persisted merge record is what makes this run a resume: the one fail-closed
    # read the recovery and the refusal report use (an unreadable record is no proof of a lag).
    resume_state = _load_state_on_refusal_path(main_repo, canonical_id)

    def _run() -> None:
        _pre_mutation_safety_preflight(
            main_repo,
            mission_slug,
            lanes_manifest.target_branch,
            lanes_manifest,
            primary_meta_dir,
            remove_worktree=retention.remove_worktree,
            teardown_coordination=retention.teardown_coordination,
            resume_state=resume_state,
        )

    def _refuse(refusal: DestructiveOpRefused, coord_worktree: Path | None) -> typer.Exit:
        # #4933: the persisted pre-mutation base (absent on a fresh consolidation) is the
        # only proof `_report_pre_mutation_refusal` will accept for the reset-to-HEAD
        # guidance -- see its docstring. Each checkout is proven against its own anchor
        # (#5571 / #5613): the coordination worktree against ``pre_mutation_coord_sha``, a
        # mission or lane worktree against its branch's snapshot, the root against the target tip.
        state = resume_state
        checkout = _lag_checkout_for_refusal(refusal, main_repo, coord_worktree, mission_branch=lanes_manifest.mission_branch)
        base_sha = checkout.base_sha(state) if checkout is not None else (state.pre_mutation_target_sha if state else None)
        _report_pre_mutation_refusal(
            refusal,
            main_repo,
            mission_branch=lanes_manifest.mission_branch,
            base_sha=base_sha,
            coord_worktree=coord_worktree,
            mission_slug=mission_slug,
        )
        return typer.Exit(1)

    recovered: set[Path] = set()
    while True:
        try:
            _run()
            return
        except RefAdvanceError as exc:
            # The resume leg could not enumerate the worktrees on the mission branch: nothing
            # was inspected or changed, so refuse like any other pre-mutation condition.
            console.print(f"[red]Error:[/red] Cannot inspect the worktrees on mission branch {lanes_manifest.mission_branch!r}: {escape(str(exc))}")
            console.print(_MERGE_ABORTED_NOTE)
            raise typer.Exit(1) from exc
        except DestructiveOpRefused as exc:
            coord_worktree = _coord_worktree_for_refusal(exc, main_repo, mission_slug, primary_meta_dir)
            refused = Path(exc.worktree_path or main_repo)
            if refused in recovered or not _recover_behind_head_primary_on_resume(
                exc,
                main_repo,
                canonical_id,
                mission_branch=lanes_manifest.mission_branch,
                coord_worktree=coord_worktree,
            ):
                raise _refuse(exc, coord_worktree) from exc
            recovered.add(refused)
