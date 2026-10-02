"""Mission-creation helpers for the per-mission coordination branch.

This module owns the **topology** half of issue #1348: every mission gets a
canonical coordination branch ``kitty/mission-<slug>-<mid8>`` parented off the
target branch at creation time. Later work packages (WP04, WP05) build on top
of this — they materialise the coordination *worktree* and the
``BookkeepingTransaction`` — but neither of those can do anything useful until
the branch ref exists. WP03 is the foundation.

Contract
--------

``ensure_coordination_branch()`` is idempotent and structural:

* The branch name is derived deterministically from ``mission_slug`` and the
  mission's ULID via :func:`specify_cli.lanes.branch_naming.mission_branch_name`.
  There is no per-call randomness; re-running mission-create on the same
  mission slug produces the same branch name.

* If the branch does not exist, it is created at the same commit as
  ``target_branch``.

* If the branch already exists *and* is an ancestor of ``target_branch`` (i.e.
  fast-forwardable / already up-to-date with the target), the helper is a
  silent no-op. This is what makes re-running ``agent mission create`` safe.

* If the branch already exists *and* has diverged from ``target_branch``,
  :class:`CoordinationBranchDiverged` is raised with a stable
  ``error_code`` so scripted callers (CI, doctor) can detect and act.

* The ``force_recreate`` flag is an explicit operator escape hatch: when set,
  any existing branch at the coordination name is deleted and re-created at
  ``target_branch``. This is **never** the default — the caller must opt in.

The structured error carries enough data for an operator to fix the situation
without guessing: ``coordination_branch``, ``target_branch``, divergence
point, and a ``next_step`` hint.
"""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from kernel.git import GitCommandError, commit_paths

from mission_runtime import MissionTopology

from specify_cli.lanes._git import branch_exists as _branch_exists
from specify_cli.lanes._git import ref_exists as _ref_resolves
from specify_cli.lanes.branch_naming import coord_branch_name as _seam_coord_branch_name

__all__ = [
    "CoordinationBranchDiverged",
    "CoordinationBranchResult",
    "coordination_branch_name",
    "ensure_coordination_branch",
    "is_expected_coordination_divergence",
    "topology_mints_coordination_branch",
]


# ---------------------------------------------------------------------------
# Create-time topology decision (WP03 / issue #2218)
# ---------------------------------------------------------------------------

#: The two coordination-bearing cells of the orthogonal coordination × lanes
#: grid. A mission in either shape gets a per-mission coordination branch at
#: creation; the branch-flat shapes (``SINGLE_BRANCH`` / ``LANES``) do not.
_COORDINATION_BEARING_TOPOLOGIES: frozenset[MissionTopology] = frozenset({MissionTopology.COORD, MissionTopology.LANES_WITH_COORD})


def topology_mints_coordination_branch(topology: MissionTopology) -> bool:
    """Return ``True`` when *topology* requires a per-mission coordination branch.

    Pure lookup over the operator's explicit create-time choice (#2218): the
    coordination-bearing cells (``COORD`` / ``LANES_WITH_COORD``) mint the
    branch; the branch-flat cells (``SINGLE_BRANCH`` / ``LANES``) skip it and
    leave ``coordination_branch`` out of ``meta.json`` entirely. The decision is
    NEVER re-derived from disk/git state — it is the stored choice, so a
    ``lanes`` selection (which ``classify_topology`` cannot reproduce
    pre-``finalize-tasks``) is honoured.
    """
    return topology in _COORDINATION_BEARING_TOPOLOGIES


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class CoordinationBranchDiverged(RuntimeError):
    """Raised when an existing coordination branch has diverged from the target.

    Carries a stable ``error_code`` (per NFR-007) plus the coordination branch
    name, the target branch name, and an operator-facing ``next_step`` hint.
    """

    error_code = "COORDINATION_BRANCH_DIVERGED"

    def __init__(
        self,
        *,
        coordination_branch: str,
        target_branch: str,
        next_step: str | None = None,
    ) -> None:
        self.coordination_branch = coordination_branch
        self.target_branch = target_branch
        self.next_step = next_step or (
            f"Either rebase '{coordination_branch}' onto '{target_branch}', "
            f"or re-run mission create with --force-recreate-coordination-branch "
            f"to reset the branch to the target."
        )
        super().__init__(f"Coordination branch '{coordination_branch}' has diverged from target '{target_branch}'. {self.next_step}")

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation for structured CLI output."""
        return {
            "error_code": self.error_code,
            "coordination_branch": self.coordination_branch,
            "target_branch": self.target_branch,
            "next_step": self.next_step,
        }


# ---------------------------------------------------------------------------
# Expected coordination-vs-target divergence (T034, D6 "divergence model")
# ---------------------------------------------------------------------------


def _rev_list(repo_root: Path, rev_range: str) -> list[str] | None:
    """Return the commits in *rev_range*, or ``None`` on a git failure (e.g. a shallow clone)."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-list", rev_range],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _merge_base_or_none(repo_root: Path, ref_a: str, ref_b: str) -> str | None:
    """Return the merge-base of two refs, or ``None`` when they share no history."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", ref_a, ref_b],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _changed_paths_for_commit(repo_root: Path, commit: str) -> list[str] | None:
    """Return the paths one commit changes, or ``None`` on a git failure.

    ``--first-parent -m`` (brownfield scout, T034 edge case): ``diff-tree``
    prints nothing for a merge commit without ``-m``, which would silently
    read as "touches nothing" -- a merge commit is diffed against its first
    parent instead of being skipped.
    """
    try:
        return [str(path) for path in commit_paths(repo_root, commit, first_parent=True)]
    except GitCommandError:
        return None


def _is_coord_only_path(path: str, *, mission_dir_name: str) -> bool:
    """True iff *path* is a COORD-partition file of THIS Mission (T034).

    ``kind_for_mission_file`` already returns ``None`` for a path outside
    ``kitty-specs/<mission_dir_name>/`` (when ``mission_slug`` is supplied)
    and for an unrecognised file under it -- both fail CLOSED here (treated
    as NOT a coord-only path), so an unexpected commit never slips through
    as "expected divergence" merely because its paths went unclassified.
    """
    from mission_runtime import is_primary_artifact_kind, kind_for_mission_file

    kind = kind_for_mission_file(path, mission_slug=mission_dir_name)
    if kind is None:
        return False
    return not is_primary_artifact_kind(kind)


def _commits_all_touch_only_coord_paths(repo_root: Path, rev_range: str, *, mission_dir_name: str) -> bool:
    """True iff every commit in *rev_range* changes ONLY this Mission's COORD paths."""
    commits = _rev_list(repo_root, rev_range)
    if commits is None:
        return False
    for commit in commits:
        changed = _changed_paths_for_commit(repo_root, commit)
        if changed is None:
            return False
        if any(not _is_coord_only_path(path, mission_dir_name=mission_dir_name) for path in changed):
            return False
    return True


def _commits_touch_any_coord_path(repo_root: Path, rev_range: str, *, mission_dir_name: str) -> bool:
    """True iff ANY commit in *rev_range* changes one of this Mission's COORD paths."""
    commits = _rev_list(repo_root, rev_range)
    if commits is None:
        # Fail toward reporting (treat as "does touch", i.e. NOT expected) --
        # an unreadable range must never silently pass the divergence check.
        return True
    for commit in commits:
        changed = _changed_paths_for_commit(repo_root, commit)
        if changed is None:
            return True
        if any(_is_coord_only_path(path, mission_dir_name=mission_dir_name) for path in changed):
            return True
    return False


def is_expected_coordination_divergence(
    repo_root: Path,
    *,
    coordination_branch: str,
    target_branch: str,
    mission_dir_name: str,
) -> bool:
    """Return whether *coordination_branch* is ahead of *target_branch* BY DESIGN (T034, D6).

    One predicate shared by :func:`ensure_coordination_branch` (below) and
    ``_coordination_doctor.py``'s staleness finding (T035) -- neither
    re-derives it (C-001 / DIRECTIVE_044). True iff ALL of:

    * ``merge-base(coordination_branch, target_branch)`` exists (a shallow
      clone, or genuinely unrelated histories, fails CLOSED to ``False`` --
      "fail toward reporting", T034 edge case);
    * every commit unique to the coordination branch (``target..coord``)
      changes only this Mission's COORD-partition paths (classified with
      :func:`mission_runtime.kind_for_mission_file`; a path outside
      ``kitty-specs/<mission_dir_name>/``, or an unrecognised one, is
      rejected);
    * the target's own commits since the merge base (``merge_base..target``)
      never touch those same COORD paths.

    Trivial/identical tips (``target..coord`` and ``merge_base..target`` both
    empty) are vacuously expected -- an unchanged coordination branch can
    never be a genuine divergence.
    """
    merge_base = _merge_base_or_none(repo_root, coordination_branch, target_branch)
    if merge_base is None:
        return False
    if not _commits_all_touch_only_coord_paths(repo_root, f"{target_branch}..{coordination_branch}", mission_dir_name=mission_dir_name):
        return False
    return not _commits_touch_any_coord_path(repo_root, f"{merge_base}..{target_branch}", mission_dir_name=mission_dir_name)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class CoordinationBranchResult:
    """Outcome of :func:`ensure_coordination_branch`.

    Attributes:
        branch_name: The full branch name (e.g. ``kitty/mission-foo-01ABCDEF``).
        created: ``True`` if the branch was newly created on this call,
            ``False`` if it already existed and was reused.
        force_recreated: ``True`` if the branch existed but was reset via the
            ``force_recreate`` flag.
        skipped_reason: When non-``None``, the branch was *not* materialised on
            disk because preconditions were not met (e.g. ``target_branch``
            does not exist as a local ref).  ``branch_name`` is still the
            canonical name the branch *would* carry, so downstream callers
            (``meta.json``, JSON output) remain self-describing.  WP04 / WP05
            will catch the missing branch at consumption time.
    """

    branch_name: str
    created: bool
    force_recreated: bool = False
    skipped_reason: str | None = None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def coordination_branch_name(mission_slug: str, mission_id: str) -> str:
    """Compute the deterministic coordination branch name for a mission.

    The branch name is ``kitty/mission-<human-slug>-<mid8>`` where ``mid8`` is
    the first 8 characters of ``mission_id`` (a ULID).  The function accepts
    either form of ``mission_slug``:

    * **Formatted** (the on-disk form already containing ``-<mid8>``, e.g.
      ``"my-feature-01KSPTVW"``) — used as-is.
    * **Bare** (no mid8 suffix, e.g. ``"my-feature"``, optionally with a
      legacy ``NNN-`` numeric prefix) — the prefix is stripped and the
      ``-<mid8>`` token is appended.

    This dual-mode keeps the helper safe regardless of whether callers hand it
    the ``meta["mission_slug"]`` (formatted) or a raw bare slug, and avoids
    the ``mission_branch_name`` double-mid8 trap when the formatted form is
    passed.  The ``-coord`` suffix is *not* applied at the branch level (it
    is reserved for the worktree path in WP04, per spec).

    Delegates to the canonical naming seam (``lanes.branch_naming.coord_branch_name``)
    so there is exactly ONE algorithm for the coord-branch grammar (FR-010). The
    seam strips a stale ``NNN-`` prefix and dedups an embedded ``-<mid8>`` exactly
    as the prior hand-rolled body did, so this LIVE ``mission create`` composer
    produces byte-identical branch names for embedded, bare, and legacy slugs.
    """
    # ``str(...)`` pins the return type: the seam is annotated loosely and
    # returns ``Any``; the value is always a branch-name string (Boy Scout fix,
    # DIR-025 — silences a pre-existing ``no-any-return`` without a suppression).
    return str(_seam_coord_branch_name(mission_slug, mission_id=mission_id))


def ensure_coordination_branch(
    *,
    repo_root: Path,
    mission_slug: str,
    mission_id: str,
    target_branch: str,
    force_recreate: bool = False,
) -> CoordinationBranchResult:
    """Mint or validate the coordination branch for a mission.

    Args:
        repo_root: Absolute path to the project root checkout.
        mission_slug: The mission slug (typically the on-disk
            ``<human-slug>-<mid8>`` directory name).
        mission_id: Full mission ULID (used to derive the ``mid8`` segment of
            the branch name).
        target_branch: The branch the coordination branch is parented off of
            (typically the operator's current branch at mission-create time).
        force_recreate: When ``True``, an existing coordination branch is
            deleted and re-created at ``target_branch``. Operator escape hatch.

    Returns:
        CoordinationBranchResult describing the outcome.

    Raises:
        CoordinationBranchDiverged: When the branch already exists, diverges
            from ``target_branch``, and ``force_recreate`` is ``False``.
        RuntimeError: When a git subprocess fails for an unexpected reason.
    """
    branch = coordination_branch_name(mission_slug, mission_id)

    # Guard: if ``target_branch`` does not resolve to a real ref, do not try to
    # create the coordination branch.  The canonical name is still returned
    # (so ``meta.json`` and ``--json`` output are self-describing), and the
    # downstream consumers (WP04 worktree, WP05 transaction) will surface the
    # missing branch when they actually try to use it.  This keeps mission
    # creation usable in synthetic / test contexts where the operator pins a
    # target like ``"2.x"`` that has no on-disk counterpart.
    if not _ref_resolves(repo_root, target_branch):
        return CoordinationBranchResult(
            branch_name=branch,
            created=False,
            skipped_reason=f"target_branch '{target_branch}' does not resolve to a ref",
        )

    existing = _branch_exists(repo_root, branch)

    if existing and force_recreate:
        # T031 (coord-artifact-single-home-01M3V4BE): create now eagerly
        # materializes the coordination worktree, so ``force_recreate`` can
        # meet a worktree checked out to the very branch it is about to
        # delete -- git refuses to delete a checked-out branch. Clear it
        # first; the operator escape hatch is for abandoning/re-forking a
        # mission's whole coordination history, so discarding a worktree it
        # left behind is sanctioned.
        _teardown_coordination_worktree_if_present(repo_root, mission_slug, mission_id)
        _delete_branch(repo_root, branch)
        _create_branch(repo_root, branch, target_branch)
        return CoordinationBranchResult(branch_name=branch, created=True, force_recreated=True)

    if existing:
        if _is_ancestor(repo_root, branch, target_branch):
            # Branch is already at-or-behind target → reusable as-is.
            return CoordinationBranchResult(branch_name=branch, created=False)
        # T034/D6: a coordination branch ahead of target by design (every
        # commit it carries past target seeds/records only this Mission's own
        # COORD-partition files, and target's own history since the fork
        # point never touches them) is reusable too -- it is NOT the genuine
        # divergence this guard exists to catch.
        if is_expected_coordination_divergence(
            repo_root,
            coordination_branch=branch,
            target_branch=target_branch,
            mission_dir_name=mission_slug,
        ):
            return CoordinationBranchResult(branch_name=branch, created=False)
        # Existing branch has genuinely diverged from the target.
        raise CoordinationBranchDiverged(
            coordination_branch=branch,
            target_branch=target_branch,
        )

    _create_branch(repo_root, branch, target_branch)
    return CoordinationBranchResult(branch_name=branch, created=True)


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


def _is_ancestor(repo_root: Path, candidate: str, descendant: str) -> bool:
    """Return True if ``candidate`` is an ancestor of (or equal to) ``descendant``.

    Used to decide whether an existing coordination branch is safely reusable
    without recreation: if the existing branch is at or behind the target, the
    next ``BookkeepingTransaction`` (WP05) will simply fast-forward it.
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "merge-base",
            "--is-ancestor",
            candidate,
            descendant,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _create_branch(repo_root: Path, branch: str, parent: str) -> None:
    """Create a new branch parented off ``parent``.

    The branch is created as a plain ref (no checkout). Callers that want a
    worktree on this branch will create it separately (WP04 territory).
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "branch", branch, parent],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create coordination branch '{branch}' off '{parent}': {result.stderr.strip() or result.stdout.strip()}")


def _delete_branch(repo_root: Path, branch: str) -> None:
    """Delete a local branch (force). Used by the --force-recreate path only."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "branch", "-D", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to delete coordination branch '{branch}': {result.stderr.strip() or result.stdout.strip()}")


def _teardown_coordination_worktree_if_present(repo_root: Path, mission_slug: str, mission_id: str) -> None:
    """Best-effort: remove a materialized coordination worktree before ``force_recreate`` deletes its branch.

    T031 (coord-artifact-single-home-01M3V4BE) eagerly materializes the
    coordination worktree at create time, so a later ``force_recreate`` can
    now meet a worktree checked out to the branch it is about to delete --
    ``git branch -D`` refuses that. Never raises: if teardown is refused
    (e.g. a genuinely dirty worktree) or the worktree never existed,
    ``_delete_branch`` still runs right after and raises its own clear,
    typed error if the branch truly cannot be deleted.
    """
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.lanes.branch_naming import resolve_mid8 as _seam_resolve_mid8

    mid8 = _seam_resolve_mid8("", mission_id=mission_id)
    with contextlib.suppress(Exception):
        # The single shared teardown seam; a force-recreated mission persists no retrospective here.
        teardown_coordination_topology(repo_root, mission_slug, mid8, persist=False)
