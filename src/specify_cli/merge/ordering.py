"""Merge ordering based on WP dependencies.

Implements FR-008 through FR-011: determining merge order via topological
sort of the dependency graph.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-07 / WP07 also relocated
the mission-number bake cluster here (it sits next to ``assign_next_mission_number``,
which it consumes). The git-worktree-heavy ``_write_mission_number_to_branch`` was
moved verbatim and the in-function (lazy) imports are kept lazy (C-007). One-way
import: this module never imports the command shim.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path

from specify_cli.cli.console import console
from specify_cli.core.constants import KITTY_SPECS_DIR, WORKTREES_DIR
from specify_cli.core.dependency_graph import (
    build_dependency_graph,
    detect_cycles,
    topological_sort,
)
from specify_cli.core.paths import (
    MissionMetaReadError,
    assert_safe_path_segment,
    load_meta_fail_closed,
)
from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.git.ref_advance import advance_branch_ref
from specify_cli.merge._constants import logger as _merge_logger
from specify_cli.merge.git_probes import _has_branch_ref, _is_git_repo, path_is_under_worktrees
from specify_cli.merge.state import MergeState
from specify_cli.mission_metadata import load_meta, write_meta

__all__ = [
    "get_merge_order",
    "MergeOrderError",
    "has_dependency_info",
    "display_merge_order",
    "assign_next_mission_number",
    "_already_baked",
    "_mark_mission_number_baked",
    "_is_assigned_mission_number",
    "_bake_mission_number_into_mission_branch",
    "_assign_planning_only_mission_number_if_needed",
]

logger = logging.getLogger(__name__)


class MergeOrderError(Exception):
    """Error determining merge order."""

    pass


def has_dependency_info(graph: dict[str, list[str]]) -> bool:
    """Check if any WP has declared dependencies.

    Args:
        graph: Dependency graph mapping WP ID to list of dependencies

    Returns:
        True if at least one WP has non-empty dependencies
    """
    return any(deps for deps in graph.values())


def get_merge_order(
    wp_workspaces: list[tuple[Path, str, str]],
    feature_dir: Path,
) -> list[tuple[Path, str, str]]:
    """Return WPs in dependency order (topological sort).

    Determines the optimal merge order based on WP dependencies declared
    in frontmatter. WPs with dependencies will be merged after their
    dependencies.

    Args:
        wp_workspaces: List of (worktree_path, wp_id, branch_name) tuples
        feature_dir: Path to feature directory containing tasks/

    Returns:
        Same tuples reordered by dependency (dependencies first)

    Raises:
        MergeOrderError: If circular dependency detected
    """
    if not wp_workspaces:
        return []

    # Build WP ID → workspace mapping
    wp_map = {wp_id: (path, wp_id, branch) for path, wp_id, branch in wp_workspaces}

    # Build dependency graph from task frontmatter
    graph = build_dependency_graph(feature_dir)

    # Check for missing WPs in graph (may have no frontmatter)
    for wp_id in wp_map:
        if wp_id not in graph:
            graph[wp_id] = []  # No dependencies

    # Check if we have any dependency info
    if not has_dependency_info(graph):
        # No dependency info - fall back to numerical order with warning
        logger.warning("No dependency information found in WP frontmatter. Falling back to numerical order (WP01, WP02, ...).")
        return sorted(wp_workspaces, key=lambda x: x[1])  # Sort by wp_id

    # Detect cycles - show full cycle path in error
    cycles = detect_cycles(graph)
    if cycles:
        # Format the cycle path clearly: WP01 → WP02 → WP03 → WP01
        cycle = cycles[0]
        cycle_str = " → ".join(cycle)
        raise MergeOrderError(f"Circular dependency detected: {cycle_str}\nFix the dependencies in the WP frontmatter to remove this cycle.")

    # Topological sort
    try:
        ordered_ids = topological_sort(graph)
    except ValueError as e:
        raise MergeOrderError(str(e)) from e

    # Filter to only WPs we have workspaces for, maintaining order
    result = []
    for wp_id in ordered_ids:
        if wp_id in wp_map:
            result.append(wp_map[wp_id])

    return result


def assign_next_mission_number(target_branch_path: Path, mission_specs_dir: Path) -> int:
    """Compute the next dense integer ``mission_number`` for the target branch.

    Walks ``mission_specs_dir`` (which should reflect the checked-out target
    branch's ``kitty-specs/`` view), reads every mission's ``meta.json`` via
    the canonical metadata loader, collects all non-null integer
    ``mission_number`` values, and returns ``max(collected) + 1`` -- or ``1``
    if no missions on the target branch have an integer assigned yet.

    **Locking invariant (FR-044, WP10/T052/T055):** This helper does **not**
    acquire any lock.  It assumes the caller is already holding the
    merge-state lock for the mission being merged, which provides
    single-writer semantics against the target branch.  Calling this without
    the lock is a race-condition bug.

    Args:
        target_branch_path: Path to the checked-out target branch worktree
            (e.g. the merge worktree at
            ``.kittify/runtime/merge/<mission_id>/workspace/``). Currently
            unused for I/O -- present in the signature so callers explicitly
            document which branch's view they are reading.  ``mission_specs_dir``
            must be a child of (or otherwise consistent with) this path.
        mission_specs_dir: Path to the ``kitty-specs/`` directory on the
            target branch worktree.  Each immediate subdirectory containing a
            ``meta.json`` is treated as a mission.

    Returns:
        The next available integer ``mission_number`` (>= 1).

    Notes:
        - Pre-merge missions (``mission_number: null``) are excluded from the
          max computation by virtue of being ``None`` after coercion.
        - Legacy string forms (``"042"``) are coerced to ``int`` by
          :func:`specify_cli.mission_metadata.resolve_mission_identity` and
          participate in the max.
        - Missions whose ``meta.json`` is missing or unreadable are skipped.
    """
    # Lazy import to keep merge.ordering import-cheap and avoid any
    # mission_metadata <-> merge cycles.
    from specify_cli.mission_metadata import resolve_mission_identity

    del target_branch_path  # Documentation only -- see docstring.

    if not mission_specs_dir.exists() or not mission_specs_dir.is_dir():
        return 1

    collected: list[int] = []
    for child in sorted(mission_specs_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "meta.json").exists():
            continue
        try:
            identity = resolve_mission_identity(child)
        except (ValueError, TypeError, MissionMetaReadError):
            # Malformed mission_number, or (landing-fold, PR #3155:
            # resolve_mission_identity now routes through
            # load_meta_fail_closed) a corrupt meta.json -- skip rather than
            # crash the merge either way.
            logger.warning(
                "Skipping mission %s during number assignment scan: malformed mission_number",
                child.name,
            )
            continue
        if identity.mission_number is not None:
            collected.append(identity.mission_number)

    if not collected:
        return 1
    return max(collected) + 1


def display_merge_order(
    ordered_workspaces: list[tuple[Path, str, str]],
    console,
) -> None:
    """Display the merge order to the user.

    Args:
        ordered_workspaces: Ordered list of (path, wp_id, branch) tuples
        console: Rich Console for output
    """
    if not ordered_workspaces:
        return

    console.print("\n[bold]Merge Order[/bold] (dependency-based):\n")
    for i, (_, wp_id, branch) in enumerate(ordered_workspaces, 1):
        console.print(f"  {i}. {wp_id} ({branch})")
    console.print()


# ---------------------------------------------------------------------------
# WP07 (#2057): mission-number bake cluster (relocated verbatim from the merge
# command shim). Uses the merge logger namespace so log records keep their
# historical name. Lazy imports are intentionally kept lazy (C-007/INV-7).
# ---------------------------------------------------------------------------


def _already_baked(merge_state: MergeState | None) -> bool:
    """Resume short-circuit predicate (T026 / FR-012).

    Returns True when a prior merge run successfully baked the mission_number
    and persisted the flag to state.json. Caller may skip the assignment
    step entirely with no I/O.
    """
    return merge_state is not None and merge_state.mission_number_baked


def _mark_mission_number_baked(
    merge_state: MergeState | None,
    main_repo: Path,
) -> None:
    """Persist ``mission_number_baked = True`` so a subsequent resume short-
    circuits via :func:`_already_baked` (T025 / FR-011)."""
    if merge_state is None:
        return
    merge_state.mission_number_baked = True
    from specify_cli.merge.state import save_state as _save_state

    _save_state(merge_state, main_repo)


def _is_assigned_mission_number(value: object) -> bool:
    """Return True when *value* is a real integer mission_number (not bool/None)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _compute_next_mission_number_or_none(
    main_repo: Path,
    mission_slug: str,
    target_branch: str,
) -> int | None:
    """Step 1: derive the next mission_number from the *target* branch.

    Returns:
        The next integer (``max + 1``, or ``1`` if empty), or ``None`` when
        the target branch already carries an integer for this mission (the
        no-op signal — the assignment already happened on a prior merge).
    """
    import subprocess as _subprocess
    import tempfile as _tempfile

    try:
        assert_safe_path_segment(mission_slug)
    except ValueError:
        _merge_logger.warning(
            "Refusing mission_number assignment for unsafe mission_slug %r (traversal guard).",
            mission_slug,
        )
        return None

    tmp_dir = _tempfile.mkdtemp(prefix="kitty-numassign-")
    tmp_path = Path(tmp_dir)
    try:
        result = _subprocess.run(
            ["git", "worktree", "add", "--detach", str(tmp_path), target_branch],
            cwd=str(main_repo),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _merge_logger.warning(
                "Could not create scan worktree for mission_number assignment: %s",
                result.stderr.strip(),
            )
            # Fall back to scanning main_repo's working tree. Best effort.
            scan_root = main_repo
            scan_specs = main_repo / KITTY_SPECS_DIR
        else:
            scan_root = tmp_path
            scan_specs = tmp_path / KITTY_SPECS_DIR

        target_meta_path = scan_specs / mission_slug / "meta.json"
        if target_meta_path.exists():
            # Canonical reader (FR-005/WP12): on_malformed="none" absorbs BOTH a
            # JSON-syntax error AND a non-dict top level to None -- this is a
            # best-effort idempotency peek (not a #2091 identity guard site), so
            # a corrupt/foreign meta.json on the target branch must not abort the
            # merge-time numbering step; it falls through to normal assignment
            # below, matching the pre-existing non-dict-tolerant branch.
            target_meta = load_meta(scan_specs / mission_slug, on_malformed="none")
            existing_on_target = target_meta.get("mission_number") if isinstance(target_meta, dict) else None
            if _is_assigned_mission_number(existing_on_target):
                _merge_logger.debug(
                    "Mission %s already has mission_number=%d on target branch %s; no-op",
                    mission_slug,
                    existing_on_target,
                    target_branch,
                )
                return None

        return assign_next_mission_number(scan_root, scan_specs)
    finally:
        _subprocess.run(
            ["git", "worktree", "remove", str(tmp_path), "--force"],
            cwd=str(main_repo),
            capture_output=True,
        )


def _surface_unbaked_mission_number(
    mission_slug: str,
    mission_branch: str,
    next_number: int,
    *,
    reason: str,
) -> None:
    """#4474 / FR-011: make an unbaked ``mission_number`` OBSERVABLE.

    A logger-only warning is not queryable by an operator scanning merge
    output. This prints a merge-summary line (the operator-visible transcript
    every merge run already emits progress through) in addition to an
    elevated logger record, so the genuinely-unreachable fallback never
    degrades to the historical silent ``return False``.
    """
    console.print(
        f"[red]Warning:[/red] mission_number={next_number} for mission "
        f"{mission_slug!r} could NOT be baked ({reason}). Re-run "
        "[bold]spec-kitty merge --resume[/bold] once the primary meta.json "
        "becomes reachable, or assign mission_number manually."
    )
    _merge_logger.warning(
        "mission_number=%d NOT baked for %s (mission_branch=%s): %s",
        next_number,
        mission_slug,
        mission_branch,
        reason,
    )


def _bake_mission_number_on_primary_tree(
    main_repo: Path,
    mission_slug: str,
    mission_branch: str,
    next_number: int,
    merge_state: MergeState | None,
) -> bool:
    """#4474 / FR-011 topology-aware fallback: write directly to the PRIMARY tree.

    Invoked only when the mission-branch (coordination, for a coord-topology
    "083+ layout" mission) detached worktree does not carry ``meta.json`` --
    on that topology it is a lifecycle-only branch and never will. The
    mission's ``meta.json`` is a PRIMARY-partition artifact and instead lives
    directly on ``main_repo``'s own on-disk checkout (the "primary checkout";
    see ``mission_runtime.resolution.read_dir_for``). This composes the SAME
    ``compose_meta_json_path`` helper used for the mission-branch write, but
    applied to ``main_repo`` itself -- never a detached worktree, and never
    resolving into ``.worktrees/`` (the ``path_is_under_worktrees`` guard is
    preserved here exactly as on the mission-branch write path).

    Returns:
        ``True`` when a fresh number was written and committed directly on
        ``main_repo``'s current checkout (PERSISTED -- the preferred
        outcome). ``False`` when the value was already present (idempotency
        hit -- still marks the baked flag) or when the primary tree is
        genuinely unreachable/unwritable, in which case the unbaked field is
        surfaced via :func:`_surface_unbaked_mission_number` instead of a
        silent skip.
    """
    import subprocess as _subprocess

    from specify_cli.missions._read_path_resolver import compose_meta_json_path as _compose_meta

    primary_meta_path = _compose_meta(main_repo, mission_slug)
    if path_is_under_worktrees(primary_meta_path):
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=f"resolved primary meta path is under {WORKTREES_DIR} ({primary_meta_path})",
        )
        return False

    if not primary_meta_path.exists():
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=(f"meta.json is unreachable on both the mission branch {mission_branch!r} and the primary checkout ({primary_meta_path})"),
        )
        return False

    # Canonical reader (FR-005/WP12): on_malformed="none" absorbs a JSON-syntax
    # error or non-dict top level to None, mirroring the mission-branch write's
    # own tolerance for a corrupt/foreign meta.json (merge-time best-effort,
    # not a #2091 identity guard site).
    meta_data = load_meta(primary_meta_path.parent, on_malformed="none")
    if not isinstance(meta_data, dict):
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=f"primary meta.json at {primary_meta_path} is not a JSON object",
        )
        return False

    existing_on_primary = meta_data.get("mission_number")
    if _is_assigned_mission_number(existing_on_primary) and existing_on_primary == next_number:
        _merge_logger.info(
            "mission_number=%d already present on primary meta.json for %s; skipping write (idempotency check)",
            next_number,
            mission_slug,
        )
        _mark_mission_number_baked(merge_state, main_repo)
        return False

    meta_data["mission_number"] = next_number
    write_meta(primary_meta_path.parent, meta_data, validate=False)

    rel_meta = primary_meta_path.relative_to(main_repo)
    if path_is_under_worktrees(rel_meta):
        # FR-035: never stage a path under .worktrees/ (defense in depth).
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=f"refusing to stage {rel_meta}: path is under {WORKTREES_DIR}",
        )
        return False

    add_result = _subprocess.run(
        ["git", "add", str(rel_meta)],
        cwd=str(main_repo),
        capture_output=True,
        text=True,
    )
    if add_result.returncode != 0:
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=f"git add failed on the primary checkout: {add_result.stderr.strip()}",
        )
        return False

    commit_msg = f"chore({mission_slug}): assign mission_number={next_number} (primary tree)"
    commit_result = _subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-m", commit_msg],
        cwd=str(main_repo),
        capture_output=True,
        text=True,
    )
    if commit_result.returncode != 0:
        _surface_unbaked_mission_number(
            mission_slug,
            mission_branch,
            next_number,
            reason=f"git commit failed on the primary checkout: {commit_result.stderr.strip()}",
        )
        return False

    _merge_logger.info(
        "Assigned mission_number=%d to mission %s via primary-tree write-back (coord-topology fallback, #4474/FR-011)",
        next_number,
        mission_slug,
    )
    return True


def _write_mission_number_to_branch(
    main_repo: Path,
    mission_branch: str,
    mission_slug: str,
    next_number: int,
    merge_state: MergeState | None,
) -> bool:
    """Step 2: write the integer into meta.json on the mission branch, commit,
    and fast-forward the branch ref.

    Returns:
        True when a fresh write + commit was applied; False when nothing was
        written because (a) the branch is missing, (b) the worktree could not
        be created, (c) meta.json is missing or malformed, or (d) the value
        was already equal (idempotency hit — still persists the baked flag).
    """
    import subprocess as _subprocess
    import tempfile as _tempfile

    try:
        assert_safe_path_segment(mission_slug)
    except ValueError:
        _merge_logger.warning(
            "Refusing to bake mission_number for unsafe mission_slug %r (traversal guard).",
            mission_slug,
        )
        return False

    if not _has_branch_ref(main_repo, mission_branch):
        _merge_logger.warning(
            "Skipping mission_number bake for %s: branch %s does not exist",
            mission_slug,
            mission_branch,
        )
        return False

    mission_tmp_dir = _tempfile.mkdtemp(prefix="kitty-numwrite-")
    mission_tmp_path = Path(mission_tmp_dir)
    try:
        result = _subprocess.run(
            ["git", "worktree", "add", "--detach", str(mission_tmp_path), mission_branch],
            cwd=str(main_repo),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _merge_logger.warning(
                "Skipping mission_number bake for %s: could not create mission worktree for %s (%s)",
                mission_slug,
                mission_branch,
                result.stderr.strip(),
            )
            return False

        # FR-037 (#1772 Bug 3, _write_mission_number_to_branch half): resolve the
        # IN-BRANCH feature dir for the detached mission-branch worktree, not a
        # nested-worktree meta.json. ``candidate_feature_dir_for_mission`` is
        # coord-aware and would return a tracked ``.worktrees/<m>-coord/…`` path
        # when the mission-branch tree carries that pollution — staging it via
        # ``git add`` then re-pollutes the tree. The mission-branch tree always
        # carries the canonical mission dir directly under ``kitty-specs/``, so
        # compose that path by hand and never resolve into ``.worktrees/``.
        from specify_cli.missions._read_path_resolver import compose_meta_json_path as _compose_meta

        meta_path = _compose_meta(mission_tmp_path, mission_slug)
        if path_is_under_worktrees(meta_path):
            _merge_logger.warning(
                "Refusing to bake mission_number for %s: resolved meta path is under %s (%s)",
                mission_slug,
                WORKTREES_DIR,
                meta_path,
            )
            return False
        if not meta_path.exists():
            # #4474 / FR-011: the mission-branch tree lacks meta.json -- on a
            # coord-topology mission (the "083+ layout" where
            # ``mission_branch == coordination_branch``, see
            # ``merge/executor.py``'s ``_capture_pre_mutation_coord_checkpoint``
            # docstring) that branch carries only lifecycle surfaces
            # (status/notes/trace); meta.json is a PRIMARY-partition artifact
            # that instead lives on the PRIMARY checkout (``main_repo``'s own
            # on-disk tree -- see ``mission_runtime.resolution.read_dir_for``'s
            # "repo_root: Absolute repository root (primary checkout)"
            # contract). Pre-fix this branch silently ``return False``d here,
            # losing the number forever. Make the write-back topology-aware:
            # fall through to the primary-tree fallback instead of failing
            # open.
            return _bake_mission_number_on_primary_tree(
                main_repo,
                mission_slug,
                mission_branch,
                next_number,
                merge_state,
            )

        # Canonical reader (FR-005/WP12): on_malformed="none" absorbs BOTH a
        # JSON-syntax error AND a non-dict top level to None, so a corrupt
        # meta.json degrades to the same "cannot bake mission_number" skip as
        # the pre-existing non-dict branch below, instead of crashing the merge
        # with an uncaught JSONDecodeError (not a #2091 identity guard site).
        meta_data = load_meta(meta_path.parent, on_malformed="none")
        if not isinstance(meta_data, dict):
            _merge_logger.warning(
                "meta.json for %s is not a JSON object; cannot bake mission_number",
                mission_slug,
            )
            return False

        # T025 / FR-010 — idempotency check INSIDE the merge-state lock.
        existing_on_mission = meta_data.get("mission_number")
        if _is_assigned_mission_number(existing_on_mission) and existing_on_mission == next_number:
            _merge_logger.info(
                "mission_number=%d already present on mission branch %s for %s; skipping write (idempotency check)",
                next_number,
                mission_branch,
                mission_slug,
            )
            _mark_mission_number_baked(merge_state, main_repo)
            return False

        meta_data["mission_number"] = next_number
        # Route all meta.json mutations through the canonical writer API.
        # validate=False preserves merge-time tolerance for legacy/partial mission
        # metadata while still enforcing atomic writes + standard format.
        write_meta(meta_path.parent, meta_data, validate=False)

        rel_meta = meta_path.relative_to(mission_tmp_path)
        if path_is_under_worktrees(rel_meta):
            # FR-035: never stage a path under .worktrees/ (defense in depth).
            _merge_logger.warning(
                "Refusing to stage %s for %s: path is under %s",
                rel_meta,
                mission_slug,
                WORKTREES_DIR,
            )
            return False
        _subprocess.run(
            ["git", "add", str(rel_meta)],
            cwd=str(mission_tmp_path),
            capture_output=True,
            check=True,
        )
        commit_msg = f"chore({mission_slug}): assign mission_number={next_number}"
        _subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", commit_msg],
            cwd=str(mission_tmp_path),
            capture_output=True,
            check=True,
        )

        new_sha = _subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(mission_tmp_path),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        # Fast-forward the mission branch ref, resyncing any worktree (e.g.
        # the coordination worktree) that has it checked out (#1826 / AC-B2).
        # Toolchain-generated churn (coordination status/matrix residue,
        # spec-kitty's own bookkeeping) on the primary checkout is legitimate,
        # so exclude it from the dirty gate via the single canonical churn
        # owner (#1878 / #2795 / FR-012 / WP13-IC-07c) rather than abort the
        # post-write ff-advance.
        advance_branch_ref(
            main_repo,
            mission_branch,
            new_sha,
            is_residue=functools.partial(is_toolchain_generated_churn, mission_slug=mission_slug),
        )
        return True
    finally:
        _subprocess.run(
            ["git", "worktree", "remove", str(mission_tmp_path), "--force"],
            cwd=str(main_repo),
            capture_output=True,
        )


def _bake_mission_number_into_mission_branch(
    main_repo: Path,
    mission_slug: str,
    mission_branch: str,
    target_branch: str,
    *,
    dry_run: bool = False,
    merge_state: MergeState | None = None,
) -> int | None:
    """Assign and persist a dense integer ``mission_number`` for a pre-merge mission.

    Implements WP10 / FR-044 / T053 plus WP04 (FR-010 / FR-011 / FR-012):

    1. T026 / FR-012 — Resume short-circuit (:func:`_already_baked`): if a
       prior run completed the assignment and persisted the flag, return
       immediately with no I/O.
    2. Step 1 (:func:`_compute_next_mission_number_or_none`): scan the
       *target* branch for the next available integer (``max + 1``). If the
       target already carries an integer for this mission, return ``None`` —
       the assignment landed in a prior successful merge.
    3. Dry-run short-circuit: log the value but do not write or commit.
    4. Step 2 (:func:`_write_mission_number_to_branch`): create a detached
       worktree at the mission-branch tip, update ``meta.json``, commit, and
       fast-forward the mission branch ref. The idempotency check inside
       Step 2 short-circuits with no write when the mission branch already
       carries exactly the computed value (T025 / FR-010).
    5. On a successful write, mark the baked flag for future resume calls.

    The caller MUST hold the global merge lock
    (``acquire_merge_lock("__global_merge__", ...)``) for the duration.

    NOTE: ``mission_number_baked`` is set after a successful idempotency hit
    OR a successful write. Operators who manually edit ``meta.json`` after a
    partial merge are responsible for clearing the flag (or running
    ``spec-kitty merge --abort``).

    **coord-write-placement-closure-01KYCF83 WP09 (IC-08 / FR-009) design note:**
    this function's detached-mission-branch-worktree mechanism was considered as
    the wiring point for the birth-time runtime cutover (:func:`~specify_cli
    .migration.runtime_state_cutover.cutover_mission`) — "the structural twin" —
    but is deliberately NOT used for it. ``cutover_mission``'s sole ``status_phase``
    writer (``_flip_phase``) resolves its write target via ``canonicalize_feature_dir``,
    which follows ANY real worktree's ``.git`` pointer back to the canonical
    main-repo root (confirmed via ``core.paths.resolve_canonical_root``). Because
    planning artifacts (``meta.json``) already live on the target branch from
    mission-creation time, that redirect would silently retarget the flip onto
    ``main_repo``'s STALE pre-merge ``meta.json`` instead of the detached
    mission-branch tip this function writes to — the exact same hazard this
    function itself avoids by using ``compose_meta_json_path`` + direct
    ``write_meta`` (never ``canonicalize_feature_dir``). The birth-cutover is
    wired POST-target instead, in ``executor._run_birth_cutover`` (called from
    ``_phase_record_done_and_project``); see ``tracers/design-decisions.md``
    (IC-08) for the full analysis.

    **Retry safety**: the assignment always re-derives from the target tip.
    If a prior run assigned a number from a stale target and the push failed,
    re-running after ``git fetch`` sees the updated target and computes the
    correct next value — the stale number in the mission branch's
    ``meta.json`` is overwritten.

    Returns:
        The assigned integer if a fresh number was written; ``None`` when
        the target branch already had one, when dry-run is set, when the
        idempotency check matched, or when any precondition (missing branch,
        missing meta.json, malformed JSON, git failure) caused a skip.
    """
    if _already_baked(merge_state):
        _merge_logger.debug(
            "mission_number_baked=True for %s; skipping assignment step (resume short-circuit)",
            mission_slug,
        )
        return None

    if not _is_git_repo(main_repo):
        _merge_logger.warning(
            "Skipping mission_number bake for %s: %s is not a git repository",
            mission_slug,
            main_repo,
        )
        return None

    next_number = _compute_next_mission_number_or_none(main_repo, mission_slug, target_branch)
    if next_number is None:
        return None

    if dry_run:
        console.print(f"[cyan]would assign[/cyan] mission_number={next_number} to mission {mission_slug}")
        return None

    if not _write_mission_number_to_branch(main_repo, mission_branch, mission_slug, next_number, merge_state):
        return None

    console.print(f"[green]Assigned[/green] mission_number={next_number} to mission {mission_slug}")
    _merge_logger.info("Assigned mission_number=%d to mission %s", next_number, mission_slug)
    _mark_mission_number_baked(merge_state, main_repo)

    return next_number


def _assign_planning_only_mission_number_if_needed(
    main_repo: Path,
    feature_dir: Path,
) -> Path | None:
    """Assign mission_number directly on target for planning-only closeout."""
    from specify_cli.merge.state import needs_number_assignment

    if not needs_number_assignment(feature_dir):
        return None

    next_number = assign_next_mission_number(
        main_repo,
        main_repo / KITTY_SPECS_DIR,
    )
    # FR-007 route: a corrupt meta.json surfaces the typed
    # ``MissionMetaReadError`` (never a raw ``ValueError``) and PROPAGATES --
    # this is a ``route-unwrapped`` census site, so swallowing corruption here
    # would silently overwrite an unreadable meta.json with a one-key dict.
    meta = load_meta_fail_closed(feature_dir) or {}
    meta["mission_number"] = next_number
    write_meta(feature_dir, meta, validate=False)
    console.print(f"  [green]✓[/green] Assigned mission_number={next_number} on target branch")
    return feature_dir / "meta.json"
