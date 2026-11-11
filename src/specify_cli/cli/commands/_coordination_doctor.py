"""Coordination + git-health cluster for ``doctor`` (WP07, #2059).

Extracts Cluster K out of ``doctor.py``: the git-version (RR-01) check, the
tracked-``.worktrees/`` hygiene check, the coordination-worktree health check,
and the lane sparse-checkout drift check. The ``_check_lane_sparse_checkout_drift``
CC19 monolith is decomposed into <=15-CC sub-helpers (per-lane scan + finding
assembly).

H2 / I-6 — CRITICAL: ``merge.path_is_under_worktrees`` is imported FUNCTION-LOCAL
inside :func:`_check_tracked_worktrees_content`. Hoisting it to module scope
reintroduces the ``doctor <-> merge`` module-load cycle. It must stay local.

Import discipline (one-way, I-2): imports shared infra from
:mod:`._doctor_shared`; never imports the CLI ``doctor`` module at module scope.

WP06 (coord-commit-integrity-01KY5JS8, FR-008/FR-009, Gap-1): adds the
coord-BRANCH-vs-``target_branch`` staleness detector
(:func:`_coord_branch_stale_vs_target_finding`), the ``--check-staleness``
doctor mode, and the minimized ``--fix`` fast-forward
(:func:`_apply_coord_staleness_fixes`). This is distinct from the existing
``_coord_worktree_stale_finding`` (worktree HEAD vs its OWN coord branch) —
Gap-1 is the residual case where the coord branch itself falls behind the
branch it publishes onto. ``--fix`` stays MINIMIZED (C-003): it performs ONLY
this fast-forward, and FAILS LOUD (unified diff, zero mutation) on anything
short of strict-ancestor + a clean coord worktree (C-005 warn-first).
:func:`check_and_warn_coord_staleness` is the public one-liner hook consumed
by ``agent/tasks_finalize.py`` (DIRECTIVE_024 declared out-of-map call — that
module is outside this WP's ``owned_files``).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from kernel.git import GitCommandError, status_entries, tracked_paths
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import locate_project_root
from specify_cli.core.utils import safe_is_dir
from specify_cli.mission_metadata import load_meta

from . import _doctor_shared
from ._doctor_shared import console

if TYPE_CHECKING:
    from specify_cli.coordination.coherence import CoordRepairOutcome
    from specify_cli.missions._read_path_resolver import BranchOnlyMission

# ``__all__`` lists this sibling's cross-module contract: the entrypoint +
# ``DoctorFinding`` + the health-check helpers ``doctor.py`` re-exports, plus
# the WP06 finalize-tasks hook. The remaining helpers (``_detect_git_version``,
# ``_check_tracked_worktrees_content``) are intra-module (used here + by this
# module's own unit tests) and are deliberately NOT exported — listing them
# would register orphan public symbols under the dead-symbol gate
# (tests/architectural/test_no_dead_symbols).
__all__ = [
    "DoctorFinding",
    "run_coordination_health",
    "check_and_warn_coord_staleness",
    "_check_git_version",
    "_check_coordination_worktree_health",
    "_check_lane_sparse_checkout_drift",
]


@dataclass
class DoctorFinding:
    """A single doctor finding emitted by a WP04 health check.

    Stable shape so that downstream tools (and tests) can rely on it.
    """

    severity: str  # "ok" | "warning" | "error"
    message: str
    next_step: str | None = None
    error_code: str | None = None
    extra: dict[str, object] = field(default_factory=dict)


_MIN_GIT_VERSION: tuple[int, int] = (2, 25)
_LANE_DRIFT_CODE = "LANE_SPARSE_CHECKOUT_DRIFT"

#: Recovery command for workspace / worktree issues (SC-005 / FR-007 / #1890).
#: The former worktree-repair subcommand was removed post-#2135; the real
#: recovery surface is ``doctor workspaces --fix``.
_WORKSPACE_RECOVERY_CMD = "spec-kitty doctor workspaces --fix"

#: Hint for the never-created coordination branch case (FR-003 / #2240).
#: The coord branch was never created (or was deleted). The correct recovery is
#: to flatten the mission by removing the `coordination_branch` key from meta.json.
_COORD_BRANCH_ABSENT_HINT = (
    "Flatten the mission: remove the `coordination_branch` key from meta.json "
    "(the coordination topology was never activated). Then run "
    "`spec-kitty migrate backfill-topology` to re-derive and persist the topology."
)

#: Belt-and-suspenders re-verify guard at the destructive flatten site itself
#: (FR-004 / #4979). The CHECK site (`_coord_branch_exists`) already stops
#: emitting `COORDINATION_WORKTREE_NEVER_CREATED` for a remote-only branch
#: after WP01 -- these hints cover the independent case where the FIX is
#: reached anyway (a future probe regression, a race). Fail-closed toward
#: "do not destroy": HIT and ERROR both skip the flatten.
_COORD_BRANCH_REMOTE_HIT_SKIP_HINT = (
    "still exists on a remote; run `git fetch` to materialize it locally -- not flattened"
)
_COORD_BRANCH_REMOTE_ERROR_SKIP_HINT = (
    "could not be verified against the remote (network error or timeout); "
    "leaving meta.json unchanged until connectivity is restored -- not flattened"
)

#: Stable error code for a coord strand that survives a rollback (#2786 / #2367-B,
#: FR-007). Emitted only when the committed coordination ref *still* reduces a
#: this-merge ``done`` WP to ``DONE`` — a marker whose ref re-derives coherent is
#: stale and yields NO finding (US2-S5 negative AC). Downstream tooling keys off
#: this constant, so it must stay stable.
_STRANDED_COORD_REVERT_CODE = "COORDINATION_STRANDED_COORD_REVERT"

#: #7552 (FR-001): ``--fix`` with no named scope refuses, mutating nothing. A repair
#: is destructive (a flatten, a strand revert), so its blast radius is never implicit.
_FIX_SCOPE_REQUIRED_CODE = "COORDINATION_FIX_SCOPE_REQUIRED"
_FIX_SCOPE_REQUIRED_MESSAGE = (
    "`doctor coordination --fix` repairs only the Missions you name. Pass "
    "`--mission <handle>` to repair one Mission, or `--all-missions` to repair every "
    "Mission in this repository. Nothing was changed."
)
#: #7552 (FR-004): ``--mission`` and ``--all-missions`` name conflicting scopes.
_FIX_SCOPE_CONFLICT_CODE = "COORDINATION_FIX_SCOPE_CONFLICT"
_FIX_SCOPE_CONFLICT_MESSAGE = (
    "`--mission` and `--all-missions` cannot be combined: name one Mission, or all of them. Nothing was changed."
)
#: #7552 (FR-006): a Mission branch whose ``meta.json`` could not be read.
_BRANCH_META_UNREADABLE_CODE = "COORDINATION_BRANCH_META_UNREADABLE"

#: Recovery hint for a live strand — points at the ``--fix`` repair path.
_STRANDED_COORD_REVERT_HINT = (
    "Run `spec-kitty doctor coordination --fix --mission <mission>` to revert the stranded "
    "coordination `done` commit(s) and clear the reconcile marker."
)

#: STUCK variant (FR-007): a live strand whose recorded coordination worktree no
#: longer exists. It is STILL a committed-ref split-brain, so it stays an
#: ``error`` (exit 1 — the coord branch carries a wrong ``done``; the doctor must
#: NOT report the mission healthy). ``--fix`` cannot revert it (nothing to run the
#: revert in), so it carries a distinct code + a *manual-recovery* ``next_step``
#: instead of looping the user back to ``--fix`` (debugger-debbie HIGH: a
#: ``warning`` here would exit 0 and hide the split-brain).
_STRANDED_COORD_REVERT_STUCK_CODE = "COORDINATION_STRANDED_COORD_REVERT_STUCK"
_STRANDED_COORD_REVERT_STUCK_HINT = (
    "The coordination worktree recorded for this strand no longer exists, so "
    "`--fix` cannot revert it. Recreate the coordination worktree (see the "
    "worktree hints from `spec-kitty doctor coordination`) then re-run `--fix`, or "
    "clear the stale `pending_coord_reconcile` marker after manually reconciling "
    "the coordination ref."
)

#: BRANCH_MISMATCH variant (sibling of #4920/#4950, FR-007): a live strand
#: whose recorded coordination worktree exists but is checked out on a branch
#: other than the coord ref (`CoordRepairOutcome.branch_mismatch`,
#: `coordination/coherence.py`). `repair_coord_strand` refuses to run the
#: revert there rather than mutate whatever foreign branch happens to be
#: checked out. It is STILL a committed-ref split-brain, so it stays an
#: ``error`` (exit 1); `--fix` cannot heal it without first putting the
#: worktree back on the coord branch, so this carries a distinct code + a
#: manual-recovery `next_step` instead of looping the operator back to
#: `_STRANDED_COORD_REVERT_HINT`'s "run `--fix`", which can never succeed
#: while the worktree stays off the coord branch.
_STRANDED_COORD_REVERT_BRANCH_MISMATCH_CODE = "COORDINATION_STRANDED_COORD_REVERT_BRANCH_MISMATCH"
_STRANDED_COORD_REVERT_BRANCH_MISMATCH_HINT = (
    "The coordination worktree recorded for this strand is checked out on the "
    "wrong branch, so `--fix` refuses to revert there (it would mutate the "
    "wrong branch instead of the coordination ref). Switch the worktree back "
    f"to the coordination branch (see `{_WORKSPACE_RECOVERY_CMD}`), then "
    "re-run `--fix`."
)

#: UNRECORDED_STRAND variant (#5572): a live strand whose reconcile marker either
#: recorded no strand commit SHAs (written by an older release, or the range was
#: unreadable when it was written) or no longer matches the status
#: log in ``captured_sha..HEAD`` (a reviewer's reopen or another status event landed
#: after the strand). `repair_coord_strand` reverts ONLY the commits the marker
#: recorded, so it refuses rather than guess — a revert would erase the later status
#: event. It is STILL a committed-ref split-brain, so it stays an ``error`` (exit 1)
#: and carries a manual-reconcile `next_step`, never the "run `--fix`" loop.
_STRANDED_COORD_REVERT_UNRECORDED_CODE = "COORDINATION_STRANDED_COORD_REVERT_UNRECORDED"
_STRANDED_COORD_REVERT_UNRECORDED_HINT_TEMPLATE = (
    "`--fix` reverts only the strand commits recorded when the failed consolidation "
    "wrote its marker, and will not guess. Reconcile the coordination status log "
    "manually: list the status-log commits in the recorded range, revert only the "
    "stranded `done` commit(s) yourself (keeping any later reopen), then clear the "
    "stale `pending_coord_reconcile` marker in "
    "`.kittify/runtime/merge/{mission_id}/state.json`."
)

#: An enumerated ``pending_coord_reconcile`` marker that cannot be parsed into
#: repair inputs (missing ref/sha/worktree or an empty strand). A safety-net
#: checker must NOT silently drop it — surface a ``warning`` (reviewer-renata LOW).
_MARKER_UNPARSEABLE_CODE = "COORDINATION_RECONCILE_MARKER_UNPARSEABLE"
_MARKER_UNPARSEABLE_HINT = (
    "A `pending_coord_reconcile` marker could not be parsed into repair inputs "
    "(missing coord_ref/captured_sha/coord_worktree or an empty strand). Inspect "
    "`.kittify/runtime/merge/<mission_id>/state.json` and clear or repair the marker."
)

#: A marker whose mission slug cannot be resolved to a planning directory
#: (unsafe/ambiguous handle). Surface a ``warning`` rather than a silent skip.
_MARKER_UNRESOLVABLE_MISSION_CODE = "COORDINATION_RECONCILE_MISSION_UNRESOLVABLE"
_MARKER_UNRESOLVABLE_MISSION_HINT = (
    "A `pending_coord_reconcile` marker names a mission that could not be resolved "
    "to a planning directory (unsafe or ambiguous handle). Run "
    "`spec-kitty doctor identity --json` and disambiguate before re-running `--fix`."
)


def _detect_git_version() -> tuple[int, int] | None:
    """Return ``(major, minor)`` of the local git binary, or ``None`` on failure."""
    try:
        out = subprocess.check_output(
            ["git", "--version"], text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    # Output shape: "git version 2.45.1.windows.1" — take the first two numbers.
    parts = out.split()
    if len(parts) < 3:
        return None
    nums = parts[2].split(".")
    try:
        return int(nums[0]), int(nums[1])
    except (ValueError, IndexError):
        return None


def _check_git_version(
    detected: tuple[int, int] | None = None,
) -> list[DoctorFinding]:
    """RR-01: refuse to operate on git older than ``_MIN_GIT_VERSION``.

    ``detected`` is injectable for tests; production callers pass
    ``None`` and the function detects from the live binary.
    """
    version = detected if detected is not None else _detect_git_version()
    if version is None:
        return [DoctorFinding(
            severity="error",
            message="Could not detect git version. spec-kitty requires git >= 2.25.",
            next_step="Install or upgrade git to >= 2.25.",
            error_code="GIT_VERSION_UNDETECTABLE",
        )]
    if version < _MIN_GIT_VERSION:
        return [DoctorFinding(
            severity="error",
            message=(
                f"git {version[0]}.{version[1]} is older than the required "
                f"{_MIN_GIT_VERSION[0]}.{_MIN_GIT_VERSION[1]}. "
                "Sparse-checkout exclusion of status files requires the "
                "modern non-cone surface."
            ),
            next_step=(
                "Upgrade git to >= 2.25 — see https://git-scm.com/downloads."
            ),
            error_code="GIT_VERSION_TOO_OLD",
            extra={"detected": f"{version[0]}.{version[1]}"},
        )]
    return [DoctorFinding(
        severity="ok",
        message=f"git {version[0]}.{version[1]} satisfies the >= 2.25 requirement.",
    )]


def _check_tracked_worktrees_content(repo_root: Path) -> list[DoctorFinding]:
    """FR-035 (#1772 Bug 0): flag any TRACKED content under ``.worktrees/``.

    ``.worktrees/`` is execution scratch space and must never be committed.
    Tracked content there (e.g. ``.worktrees/<m>-coord/…`` junk) is the
    precondition for the #1772 merge-staging failures: finalize/recovery/merge
    flows could re-stage it, and post-merge validation could try to read it from
    a branch tree. This check uses ``git ls-files`` to surface such content with
    a remediation hint. It reuses the single ``.worktrees/`` predicate that the
    merge staging guards use (Randy Reducer: one predicate, no copies).
    """

    # H2 / I-6: keep this import FUNCTION-LOCAL — hoisting it to module scope
    # reintroduces the doctor <-> merge module-load cycle.
    from specify_cli.cli.commands.consolidate import path_is_under_worktrees
    from specify_cli.core.constants import WORKTREES_DIR

    try:
        listed = tracked_paths(repo_root, pathspecs=[WORKTREES_DIR])
    except GitCommandError:
        # Advisory doctor check: not a git repo / git error -- nothing to report here.
        return []

    tracked = [str(path) for path in listed if path_is_under_worktrees(Path(str(path)))]
    if not tracked:
        return [DoctorFinding(
            severity="ok",
            message=f"No tracked content under {WORKTREES_DIR}/.",
        )]

    preview = tracked[:10]
    more = "" if len(tracked) <= 10 else f" (+{len(tracked) - 10} more)"
    return [DoctorFinding(
        severity="error",
        message=(
            f"{len(tracked)} tracked file(s) under {WORKTREES_DIR}/ — this is "
            "execution scratch space and must never be committed. Tracked "
            "content here drives the #1772 merge-staging failures."
        ),
        next_step=(
            f"Remove it from version control: "
            f"`git rm -r --cached {WORKTREES_DIR}/` then commit, and ensure "
            f"`{WORKTREES_DIR}/` is gitignored."
        ),
        error_code="TRACKED_WORKTREES_CONTENT",
        extra={"tracked": preview, "tracked_count": len(tracked), "truncated": more != ""},
    )]


def _coordination_identity(
    mission_meta: dict[str, object],
) -> tuple[str, str, str] | None:
    """Return ``(coord_branch, mission_slug, mission_id)`` or None for legacy/incomplete.

    Returns None when the mission is legacy (no coordination_branch). A tuple of
    empty strings is never returned; an incomplete-but-coordinated mission yields
    ``("", "", "")`` so callers can distinguish "skip" (None) from "warn".
    """
    coord_branch = mission_meta.get("coordination_branch")
    mission_slug = mission_meta.get("mission_slug") or mission_meta.get("slug")
    mission_id = mission_meta.get("mission_id")
    if not isinstance(coord_branch, str) or not coord_branch:
        return None
    if not isinstance(mission_slug, str) or not isinstance(mission_id, str):
        return ("", "", "")
    return (coord_branch, mission_slug, mission_id)


def _coord_worktree_actual_head(worktree: Path) -> str:
    """Return the coord worktree's checked-out ref, or ``"<detached>"``.

    Shared by :func:`_coord_worktree_head_finding` (the general health-check
    warning) and :func:`_coord_worktree_mismatch_fix_blocked_finding` (the
    dedicated ``--fix`` refusal, #4950 second-opinion follow-up) so both read
    the same single git call's shape.
    """
    try:
        return subprocess.check_output(
            ["git", "-C", str(worktree), "symbolic-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return "<detached>"


def _coord_worktree_head_finding(
    worktree: Path, coord_branch: str
) -> DoctorFinding | None:
    """Return a finding if the coord worktree HEAD is off the coord branch."""

    actual_head = _coord_worktree_actual_head(worktree)
    expected = f"refs/heads/{coord_branch}"
    if actual_head == expected or actual_head.removeprefix("refs/heads/") == coord_branch:
        return None
    return DoctorFinding(
        severity="warning",
        message=(
            f"Coordination worktree {worktree} is on {actual_head!r}, "
            f"expected {coord_branch!r}."
        ),
        next_step=(
            "Inspect the worktree, then check out the coordination branch there: "
            f"`git -C {worktree} checkout {coord_branch}`."
        ),
        error_code="COORDINATION_WORKTREE_BRANCH_MISMATCH",
    )


def _coord_worktree_dirty_finding(worktree: Path) -> DoctorFinding | None:
    """Return a finding if the coord worktree has uncommitted changes."""

    try:
        dirty = status_entries(worktree, untracked=None)
    except GitCommandError:
        # Advisory doctor check: an unreadable worktree yields no dirty finding (other checks cover it).
        dirty = ()
    if not dirty:
        return None
    return DoctorFinding(
        severity="warning",
        message=f"Coordination worktree {worktree} has uncommitted changes.",
        next_step=(
            "Commit or discard the changes inside the coord worktree "
            "before next implement/review."
        ),
        error_code="COORDINATION_WORKTREE_DIRTY",
    )


def _rev_parse(cwd: Path, ref: str) -> str:
    """Return the SHA ``ref`` resolves to in ``cwd``, or ``""`` when unreadable.

    Shared by every stale/FF-candidate check in this module (worktree-vs-branch
    and, per WP06, branch-vs-target) so there is exactly one "resolve a git ref
    to a SHA, tolerate failure" seam.
    """
    try:
        return subprocess.check_output(
            ["git", "-C", str(cwd), "rev-parse", ref],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _is_ff_candidate(repo_root: Path, ancestor_sha: str, descendant_sha: str) -> bool:
    """True iff ``ancestor_sha`` is a STRICT ancestor of ``descendant_sha``.

    Uses ``git merge-base --is-ancestor`` scoped at ``repo_root`` (readable
    regardless of which worktree/branch resolved either SHA). Equal SHAs,
    blank input, or a genuinely-diverged pair all return ``False`` — never
    raises.
    """
    if not ancestor_sha or not descendant_sha or ancestor_sha == descendant_sha:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor",
             ancestor_sha, descendant_sha],
            capture_output=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _fast_forward_finding(
    *,
    subject_sha: str,
    tip_sha: str,
    repo_root: Path,
    message: str,
    next_step: str,
    error_code: str,
) -> DoctorFinding | None:
    """Return a stale/FF-candidate finding, or ``None`` when in sync or diverged.

    Pure predicate — NEVER mutates (C-005 warn-first). ``subject_sha`` is the
    ref that may be behind; ``tip_sha`` is the ref it would fast-forward to.
    Returns ``None`` when the SHAs match (nothing to report) or ``subject_sha``
    is not a strict ancestor of ``tip_sha`` (diverged — the caller decides how,
    or whether, to surface that separately).
    """
    if not subject_sha or not tip_sha or subject_sha == tip_sha:
        return None
    if not _is_ff_candidate(repo_root, subject_sha, tip_sha):
        return None
    return DoctorFinding(
        severity="warning", message=message, next_step=next_step, error_code=error_code,
    )


def _coord_worktree_stale_finding(
    worktree: Path, repo_root: Path, coord_branch: str,
) -> DoctorFinding | None:
    """Return a finding if the coord worktree HEAD is behind the coord branch tip.

    Compares the worktree HEAD SHA with the coord branch tip via
    :func:`_fast_forward_finding` (merge-base --is-ancestor under the hood).
    Returns None when SHAs match, when the worktree has diverged (not a clean
    fast-forward candidate), or when git is unreadable.
    """
    worktree_head = _rev_parse(worktree, "HEAD")
    branch_tip = _rev_parse(repo_root, f"refs/heads/{coord_branch}")
    return _fast_forward_finding(
        subject_sha=worktree_head, tip_sha=branch_tip, repo_root=repo_root,
        message=(
            f"Coordination worktree {worktree} is behind the coord branch "
            f"{coord_branch!r} tip (fast-forward available)."
        ),
        next_step=(
            f"Run `{_WORKSPACE_RECOVERY_CMD}` to refresh it "
            "(fast-forwards stale coord worktrees)."
        ),
        error_code="COORDINATION_WORKTREE_STALE",
    )


def _resolve_coord_short(mission_slug: str, mission_id: str) -> str:
    """Resolve the mid8 short-id used to derive coord worktree/branch paths.

    Routes through the authoritative :func:`~specify_cli.lanes.branch_naming.resolve_mid8`
    resolver (WP03 / FR-009), which never raises (it declines to ``""``). The
    ``or mission_id[:8]`` fallback consciously PRESERVES the prior short-id
    tolerance. Shared by every call site that needs to derive a coord
    worktree/branch path from mission identity (campsite: was duplicated in
    :func:`_check_coordination_worktree_health` and
    :func:`_check_lane_sparse_checkout_drift`).
    """
    from specify_cli.lanes.branch_naming import resolve_mid8

    return resolve_mid8(mission_slug, mission_id=mission_id) or mission_id[:8]


def _coord_worktree_missing_remote_only_steps(
    repo_root: Path, mission_slug: str, coord_branch: str,
) -> str:
    """#5113 / FR-014: the truthful ordered remedy
    for a coordination branch that exists ONLY as a remote-tracking ref (a
    fresh clone / CI checkout where the lane exists solely on
    ``origin/<branch>``).

    ``spec-kitty doctor coordination --fix`` alone REFUSES this state
    (``materialize_coord_surface_for_write`` never auto-materializes a
    remote-only branch) -- naming it as the LEADING remedy loops the operator
    back to a command that just refused. The single construction site
    (S1192): both the ``COORDINATION_WORKTREE_MISSING`` finding builder
    (:func:`_check_coordination_worktree_health`) and the ``--fix`` fixer's
    warning (:func:`_apply_missing_worktree_fix`) call this so the two
    truthful texts can never drift apart. Mirrors
    :func:`~mission_runtime.write_target_degrade.assert_coord_write_materialized`'s
    remote-only arm (T040) in shape, though that site cannot import this one
    (runtime/mission_runtime -> specify_cli is a one-way ledger).
    """
    return (
        f"Run in order: `git -C {repo_root} fetch`, then "
        f"`git -C {repo_root} branch {coord_branch} origin/{coord_branch}`, "
        f"then `spec-kitty doctor coordination --mission {mission_slug} --fix`."
    )


def _check_coordination_worktree_health(
    repo_root: Path, mission_meta: dict[str, object],
) -> list[DoctorFinding]:
    """Verify the coordination worktree exists and is healthy.

    Returns one finding per discovered problem (or one ``ok`` finding if
    everything is fine). Skips silently for legacy missions (no
    ``coordination_branch`` field) because the coordination worktree
    concept does not apply there.
    """
    from specify_cli.coordination import CoordinationWorkspace

    identity = _coordination_identity(mission_meta)
    if identity is None:
        return []
    coord_branch, mission_slug, mission_id = identity
    if not mission_slug or not mission_id:
        return [DoctorFinding(
            severity="warning",
            message=(
                "meta.json carries coordination_branch but is missing "
                "mission_slug/mission_id; coord worktree health cannot be verified."
            ),
            next_step="Run `spec-kitty doctor identity --json` for details.",
            error_code="COORDINATION_META_INCOMPLETE",
        )]

    short = _resolve_coord_short(mission_slug, mission_id)
    worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, short)

    if not worktree.exists():
        # Reuse the canonical branch-existence probe (WP02 seam: _coord_branch_exists
        # in surface_resolver) to distinguish never-created from merely missing.
        # Function-local import keeps the one-way I-2 discipline intact.
        from specify_cli.coordination.surface_resolver import (
            _coord_branch_exists,
            _coord_branch_is_local_head,
        )

        if not _coord_branch_exists(repo_root, coord_branch):
            # Branch was never created or has been deleted.  Flatten is the
            # correct recovery, consistent with WP02 / CoordinationBranchDeleted.
            return [DoctorFinding(
                severity="warning",
                message=(
                    f"Coordination worktree {worktree} is missing for mission "
                    f"{mission_slug!r} and the declared coordination branch "
                    f"{coord_branch!r} does not exist in git "
                    "(never created or deleted)."
                ),
                next_step=_COORD_BRANCH_ABSENT_HINT,
                error_code="COORDINATION_WORKTREE_NEVER_CREATED",
            )]

        # Branch exists but the worktree has not been materialised yet.
        # #5113/FR-014: lead with the doctor `--fix` command, which actually
        # materializes the worktree (via `materialize_coord_surface_for_write`,
        # the canonical materializer) — not `doctor workspaces --fix`, which only
        # removes husks and cannot CREATE a worktree (#2240). The raw
        # `git worktree add` is kept as a manual fallback, and `recovery_args`
        # (still the raw git command) stays pinned for callers that shell out
        # to it directly -- it also works for the remote-only sub-case below
        # via git's own remote-tracking DWIM.
        _recovery_args = [
            "git", "-C", str(repo_root), "worktree", "add",
            str(worktree), coord_branch,
        ]
        # #5113: a branch that exists ONLY as a
        # remote-tracking ref (a fresh clone / CI checkout) is never
        # auto-materialized by `--fix` (materialize_coord_surface_for_write
        # refuses it) -- leading with the bare `--fix` command there is a
        # remedy that refuses and loops the operator back to itself. Classify
        # it here and lead with the truthful ordered steps instead.
        is_local_head = _coord_branch_is_local_head(repo_root, coord_branch)
        if is_local_head:
            next_step = (
                f"Run: `spec-kitty doctor coordination --mission {mission_slug} --fix` "
                f"(or, manually: `git -C {repo_root} worktree add {worktree} {coord_branch}`)"
            )
        else:
            next_step = _coord_worktree_missing_remote_only_steps(
                repo_root, mission_slug, coord_branch,
            )
        return [DoctorFinding(
            severity="warning",
            message=(
                f"Coordination worktree {worktree} is missing for mission "
                f"{mission_slug!r} (the branch {coord_branch!r} exists)."
            ),
            next_step=next_step,
            error_code="COORDINATION_WORKTREE_MISSING",
            extra={
                "recovery_args": _recovery_args,
                "mission_slug": mission_slug,
                "mid8": short,
                "coord_branch": coord_branch,
            },
        )]

    findings: list[DoctorFinding] = []
    head_finding = _coord_worktree_head_finding(worktree, coord_branch)
    if head_finding is not None:
        findings.append(head_finding)
    dirty_finding = _coord_worktree_dirty_finding(worktree)
    if dirty_finding is not None:
        findings.append(dirty_finding)
    stale_finding = _coord_worktree_stale_finding(worktree, repo_root, coord_branch)
    if stale_finding is not None:
        findings.append(stale_finding)

    if not findings:
        findings.append(DoctorFinding(
            severity="ok",
            message=f"Coordination worktree {worktree} is healthy.",
        ))
    return findings


# ---------------------------------------------------------------------------
# WP06 (coord-commit-integrity-01KY5JS8, FR-008/FR-009, Gap-1): coord BRANCH
# vs `target_branch` staleness. Distinct from `_coord_worktree_stale_finding`
# above (worktree HEAD vs its OWN coord branch) -- this is the residual case
# where the coord branch itself has fallen behind (or diverged from) the
# branch it publishes onto.
# ---------------------------------------------------------------------------

#: `--fix`-eligible: coord tip is a strict ancestor of target (clean FF).
_COORD_STALE_VS_TARGET_CODE = "COORDINATION_BRANCH_STALE_VS_TARGET"
#: NOT `--fix`-eligible: coord and target have diverged.
_COORD_DIVERGED_VS_TARGET_CODE = "COORDINATION_BRANCH_DIVERGED_VS_TARGET"
_COORD_DIVERGED_VS_TARGET_HINT = (
    "Inspect and reconcile manually; `spec-kitty doctor coordination --fix --mission <mission>` "
    "will refuse to mutate a diverged coordination branch."
)


def _coord_branch_stale_vs_target_finding(
    repo_root: Path, coord_branch: str, target_branch: str, *, mission_dir_name: str | None = None,
) -> DoctorFinding | None:
    """FR-008 (Gap-1): compare the coord branch TIP against ``target_branch``.

    * Strict ancestor (coord tip behind target, cleanly fast-forwardable) ->
      a non-blocking ``warning``, coded so ``--fix`` knows it may act
      (FR-009).
    * Ahead of target BY DESIGN (T034/D6, ``mission_dir_name`` supplied and
      :func:`~specify_cli.missions._create.is_expected_coordination_divergence`
      holds) -> ``None`` (FR-002b): a freshly seeded Mission's coordination
      branch is expected to carry COORD-only commits past target, and that is
      not the genuine divergence this finding exists to catch.
    * SHAs differ but are NOT a strict-ancestor pair (and not an expected
      divergence) -> diverged -> a distinct non-blocking ``warning`` that
      ``--fix`` refuses to touch (C-005 warn-first).
    * SHAs equal, or either ref is unreadable -> ``None`` (nothing to report).

    ``mission_dir_name`` is keyword-only with a default (brownfield scout,
    T035): existing callers that pass only the three positionals, or a test
    double that monkeypatches this function with ``lambda *a``, keep working
    unchanged -- they simply never see the FR-002b exemption (every genuine
    staleness/divergence finding they exercise is unaffected by it).
    """
    coord_sha = _rev_parse(repo_root, f"refs/heads/{coord_branch}")
    target_sha = _rev_parse(repo_root, f"refs/heads/{target_branch}")
    if not coord_sha or not target_sha or coord_sha == target_sha:
        return None
    if _is_ff_candidate(repo_root, target_sha, coord_sha):
        # Coord branch strictly AHEAD of target: it carries only its own
        # coordination commits (e.g. the status log a create seeds, #5440).
        return None
    stale = _fast_forward_finding(
        subject_sha=coord_sha, tip_sha=target_sha, repo_root=repo_root,
        message=(
            f"Coordination branch {coord_branch!r} is behind target branch "
            f"{target_branch!r} (fast-forward available)."
        ),
        next_step=f"Run `spec-kitty doctor coordination --fix --mission {mission_dir_name or '<mission>'}` to fast-forward it.",
        error_code=_COORD_STALE_VS_TARGET_CODE,
    )
    if stale is not None:
        return stale
    if mission_dir_name is not None:
        from specify_cli.missions._create import is_expected_coordination_divergence

        if is_expected_coordination_divergence(
            repo_root,
            coordination_branch=coord_branch,
            target_branch=target_branch,
            mission_dir_name=mission_dir_name,
        ):
            return None
    return DoctorFinding(
        severity="warning",
        message=(
            f"Coordination branch {coord_branch!r} has diverged from target "
            f"branch {target_branch!r} and cannot be fast-forwarded automatically."
        ),
        next_step=_COORD_DIVERGED_VS_TARGET_HINT,
        error_code=_COORD_DIVERGED_VS_TARGET_CODE,
    )


def _coord_vs_target_shas(
    repo_root: Path, mission_meta: dict[str, object],
) -> tuple[str, str, str, str] | None:
    """Resolve ``(coord_branch, target_branch, coord_sha, target_sha)`` for one mission.

    Shared identity + ``target_branch`` + SHA-resolution preamble (A-3,
    coord-commit-integrity squad) for every Gap-1 coord-vs-target call site
    (:func:`_check_coord_branch_staleness`, :func:`_fix_one_mission_coord_staleness`).
    Returns ``None`` when the mission is legacy/non-coordinated, its
    slug/mission_id/``target_branch`` identity is incomplete, or either ref is
    unreadable. Deliberately does NOT compare the two SHAs for equality --
    "already in sync" means something different to each caller (a
    non-finding vs. nothing-to-fix), so that decision stays with them.
    """
    identity = _coordination_identity(mission_meta)
    if identity is None:
        return None
    coord_branch, mission_slug, mission_id = identity
    if not mission_slug or not mission_id:
        return None
    target_branch = mission_meta.get("target_branch")
    if not isinstance(target_branch, str) or not target_branch:
        return None
    coord_sha = _rev_parse(repo_root, f"refs/heads/{coord_branch}")
    target_sha = _rev_parse(repo_root, f"refs/heads/{target_branch}")
    if not coord_sha or not target_sha:
        return None
    return coord_branch, target_branch, coord_sha, target_sha


def _check_coord_branch_staleness(
    repo_root: Path, mission_meta: dict[str, object],
) -> list[DoctorFinding]:
    """FR-008 entry: coord-branch-vs-target staleness for one mission (Gap-1).

    Skips silently for legacy (non-coordinated) missions, incomplete
    identity, a missing/blank ``target_branch``, or an unreadable ref.
    """
    shas = _coord_vs_target_shas(repo_root, mission_meta)
    if shas is None:
        return []
    coord_branch, target_branch, _coord_sha, _target_sha = shas
    mission_dir_name = mission_meta.get("mission_slug") or mission_meta.get("slug")
    finding = _coord_branch_stale_vs_target_finding(
        repo_root,
        coord_branch,
        target_branch,
        mission_dir_name=mission_dir_name if isinstance(mission_dir_name, str) and mission_dir_name else None,
    )
    return [finding] if finding is not None else []


def check_and_warn_coord_staleness(feature_dir: Path, repo_root: Path) -> None:
    """Non-blocking WARN hook for ``finalize-tasks`` (FR-008 declared one-liner).

    ``finalize_tasks`` (``agent/tasks.py`` / ``agent/tasks_finalize.py``,
    DIRECTIVE_024 declared out-of-map call -- those modules sit outside this
    WP's ``owned_files``) calls this immediately after resolving
    ``feature_dir``/``repo_root`` to surface Gap-1 coord-vs-target staleness.
    Purely advisory: swallows a missing/malformed ``meta.json`` or a
    non-coordinated mission by returning silently, and NEVER raises -- it
    must not block finalize-tasks.
    """
    meta = load_meta(feature_dir, on_malformed="none")
    if meta is None:
        return
    for finding in _check_coord_branch_staleness(repo_root, meta):
        colour = {"warning": "yellow", "error": "red"}.get(finding.severity, "white")
        console.print(f"[{colour}]{finding.severity}[/{colour}]: {finding.message}")
        if finding.next_step:
            console.print(f"  → {finding.next_step}")


def _lane_sparse_file(lane_dir: Path) -> Path | None:
    """Resolve the lane's ``info/sparse-checkout`` path, or None if unresolvable."""

    try:
        raw = subprocess.check_output(
            ["git", "-C", str(lane_dir), "rev-parse",
             "--git-path", "info/sparse-checkout"],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None
    sparse_file = Path(raw)
    if not sparse_file.is_absolute():
        sparse_file = lane_dir / sparse_file
    return sparse_file


def _scan_lane_sparse_drift(
    lane_dir: Path, expected: set[str]
) -> DoctorFinding | None:
    """Return a drift finding for one lane worktree, or None when it is healthy."""
    repair_hint = f"Run `{_WORKSPACE_RECOVERY_CMD}` to restore."
    sparse_file = _lane_sparse_file(lane_dir)
    if sparse_file is None:
        return DoctorFinding(
            severity="warning",
            message=f"Could not resolve sparse-checkout path for {lane_dir}.",
            next_step=f"Run `{_WORKSPACE_RECOVERY_CMD}`.",
            error_code=_LANE_DRIFT_CODE,
        )
    if not sparse_file.exists():
        return DoctorFinding(
            severity="warning",
            message=(
                f"Lane worktree {lane_dir} is missing the sparse-checkout "
                "policy that excludes status files."
            ),
            next_step=repair_hint,
            error_code=_LANE_DRIFT_CODE,
        )
    present = {
        line.strip()
        for line in sparse_file.read_text().splitlines()
        if line.strip()
    }
    missing = expected - present
    if not missing:
        return None
    return DoctorFinding(
        severity="warning",
        message=(
            f"Lane worktree {lane_dir} sparse-checkout is missing "
            f"{len(missing)} expected pattern(s): {sorted(missing)}."
        ),
        next_step=repair_hint,
        error_code=_LANE_DRIFT_CODE,
        extra={"missing_patterns": sorted(missing)},
    )


def _check_lane_sparse_checkout_drift(
    repo_root: Path, mission_meta: dict[str, object],
) -> list[DoctorFinding]:
    """Verify every lane worktree carries the expected sparse-checkout patterns.

    Skips silently for legacy missions.
    """
    from specify_cli.coordination import lane_sparse_checkout_patterns
    from specify_cli.lanes.branch_naming import lane_id_for_worktree_dir

    identity = _coordination_identity(mission_meta)
    if identity is None:
        return []
    _coord_branch, mission_slug, mission_id = identity
    if not mission_slug or not mission_id:
        return []

    short = _resolve_coord_short(mission_slug, mission_id)
    expected = set(lane_sparse_checkout_patterns(mission_slug, short))

    worktrees_dir = repo_root / ".worktrees"
    if not worktrees_dir.exists():
        return []

    # Cache `git worktree list --porcelain` so we don't shell out per lane.
    try:
        wt_list = subprocess.check_output(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            text=True,
        )
    except subprocess.CalledProcessError:
        wt_list = ""

    findings: list[DoctorFinding] = []
    for lane_dir in sorted(worktrees_dir.iterdir()):
        # Only inspect lane worktrees for THIS mission. Recognition is by
        # recomposition (WP11, PD-12), not by prefix: a ``startswith`` check
        # over-matches a same-prefix impostor (e.g. a ``057-foobar-lane-a``
        # dir is not ``057-foo``'s), so the worktree dir name is confirmed by
        # re-composing it from ``mission_slug`` via the naming seam instead.
        if lane_id_for_worktree_dir(lane_dir.name, mission_slug) is None:
            continue
        if str(lane_dir.resolve()) not in wt_list:
            # Not a registered git worktree; skip silently.
            continue
        finding = _scan_lane_sparse_drift(lane_dir, expected)
        if finding is not None:
            findings.append(finding)

    if not findings:
        findings.append(DoctorFinding(
            severity="ok",
            message="All lane worktrees carry the expected sparse-checkout policy.",
        ))
    return findings


def _resolve_mission_dirs(repo_root: Path, mission_filter: str | None) -> list[Path]:
    """Return the ``kitty-specs/`` mission directories to scan.

    Without a filter: every direct child of ``kitty-specs/`` (the existing
    whole-repo scan). With a ``mission_filter`` handle (FR-012): the single
    directory the shared mission resolver
    (:func:`specify_cli.context.mission_resolver.resolve_mission` — the SAME
    resolver ``doctor mission-state`` uses) maps the handle to.
    :class:`~specify_cli.context.mission_resolver.MissionNotFoundError` /
    :class:`~specify_cli.context.mission_resolver.AmbiguousHandleError` propagate
    to the caller for mission-state-parity error handling — there is no silent
    fallback.

    ``safe_is_dir`` is evaluated per candidate exactly as the previous inline
    loop did (``#3194``: an unstattable candidate RAISES rather than being
    silently dropped), then the shared read-side Mission rule (#6758) decides:
    a child that
    :func:`~specify_cli.context.mission_resolver.is_selectable_mission_dir`
    rejects is read-side residue, so no finding is reported for a folder that is
    not a Mission. One ``TrackedMissionPaths`` memo per call keeps the git probe
    to at most one.
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not safe_is_dir(specs_dir):
        return []
    if mission_filter is not None:
        from specify_cli.context.mission_resolver import resolve_mission

        return [resolve_mission(mission_filter, repo_root).feature_dir]
    from specify_cli.context.mission_resolver import TrackedMissionPaths, is_selectable_mission_dir

    tracked = TrackedMissionPaths(repo_root)
    return [
        mission_dir
        for mission_dir in sorted(specs_dir.iterdir())
        if safe_is_dir(mission_dir)
        and is_selectable_mission_dir(mission_dir, repo_root=repo_root, tracked=tracked)
    ]


@dataclass(frozen=True)
class _ScannedMission:
    """One Mission the per-Mission checks run over (#7552).

    ``mission_dir`` is set only for a Mission directory in the repository root
    checkout: it is the one copy the ``NEVER_CREATED`` flatten may edit. A Mission
    read from a coordination worktree or straight from its Mission branch carries
    ``None`` and is never flattened.
    """

    meta: dict[str, object]
    mission_dir: Path | None
    #: True for a Mission only its own Mission branch carries (no checkout holds it).
    branch_only: bool = False


@dataclass(frozen=True)
class _MissionScan:
    """The Missions a run covers, the warnings their discovery raised, and the scope."""

    missions: list[_ScannedMission]
    warnings: list[DoctorFinding]
    scoped_mission_id: str | None
    scoped_mission_slug: str | None = None


#: #7552: marks a ``COORDINATION_WORKTREE_MISSING`` finding for a Mission only its
#: Mission branch carries. ``--fix`` materializes it only under ``--mission``:
#: ``consolidate --abort`` removes a coordination worktree on purpose and keeps the
#: branch, so ``--all-missions`` must not bring such worktrees back unasked.
_BRANCH_ONLY_EXTRA = "branch_only"
_META_UNREADABLE_CODE = "COORDINATION_META_UNREADABLE"
#: The skip notice an unscoped ``--fix`` emits for such a Mission (distinct from the
#: re-collected ``COORDINATION_WORKTREE_MISSING`` finding it explains).
_BRANCH_ONLY_NOT_RESTORED_CODE = "COORDINATION_WORKTREE_NOT_RESTORED"


def _read_scanned_meta(mission_dir: Path) -> dict[str, object] | None:
    """The scan's one ``meta.json`` reader: an unreadable or malformed file skips the Mission.

    Silent by contract, as the scan always was: a broken ``meta.json`` is reported by
    ``doctor identity`` / ``doctor mission-state``, not here.
    """
    meta = load_meta(mission_dir, on_malformed="none")
    return meta if isinstance(meta, dict) else None


def _branch_only_warning(found: BranchOnlyMission) -> DoctorFinding:
    """A Mission branch whose ``meta.json`` could not be read: reported, never repaired."""
    return DoctorFinding(
        severity="warning",
        message=(
            f"Could not read kitty-specs/{found.dir_name}/meta.json from Mission branch "
            f"{found.branch!r}: {found.error}"
        ),
        next_step=f"Inspect it with `git show {found.branch}:kitty-specs/{found.dir_name}/meta.json`.",
        error_code=_BRANCH_META_UNREADABLE_CODE,
        extra={"branch": found.branch, "mission_dir_name": found.dir_name},
    )


def _off_root_missions(repo_root: Path, root_names: frozenset[str]) -> tuple[list[_ScannedMission], list[DoctorFinding]]:
    """Missions no root-checkout directory carries: coordination-worktree copies, then branch-only ones.

    Both come from the placement seam (``missions._read_path_resolver``): a settled
    default Mission's PRIMARY partition lives in its coordination worktree (FR-061),
    and once that worktree is gone only its Mission branch carries it (FR-006).
    """
    from specify_cli.missions._read_path_resolver import (
        _coord_worktree_mission_dir,
        branch_only_mission_metas,
        coord_worktree_mission_names,
    )

    missions: list[_ScannedMission] = []
    seen = set(root_names)
    for name in coord_worktree_mission_names(repo_root):
        held = None if name in seen else _coord_worktree_mission_dir(repo_root, name)
        meta = _read_scanned_meta(held) if held is not None else None
        if meta is not None:
            missions.append(_ScannedMission(meta=meta, mission_dir=None))
            seen.add(name)
    warnings: list[DoctorFinding] = []
    for found in branch_only_mission_metas(repo_root, known_dir_names=frozenset(seen)):
        if found.meta is None:
            warnings.append(_branch_only_warning(found))
        else:
            missions.append(_ScannedMission(meta=dict(found.meta), mission_dir=None, branch_only=True))
    return missions, warnings


def _matches_handle(meta: dict[str, object], handle: str) -> bool:
    """Exact ``mission_id`` / mid8 / ``mission_slug`` match (the canonical ladder's keys).

    The mid8 comes from the one sanctioned cascade
    (:func:`~specify_cli.coordination.surface_resolver.resolve_declared_mid8`), never a re-slice.
    """
    from specify_cli.coordination.surface_resolver import resolve_declared_mid8

    slug = meta.get("mission_slug")
    if handle in (meta.get("mission_id"), slug):
        return True
    return isinstance(slug, str) and bool(slug) and resolve_declared_mid8(meta, slug) == handle


def _scan_scoped(repo_root: Path, handle: str) -> _MissionScan:
    """The one Mission *handle* names: the canonical resolver first, then the off-root records.

    The off-root records are consulted only when the resolver finds nothing (a Mission
    no checkout carries); more than one match there is ambiguous. No fallback to "all".
    """
    from specify_cli.context.mission_resolver import MissionNotFoundError

    try:
        resolved = _resolve_mission_dirs(repo_root, handle)
    except MissionNotFoundError:
        resolved = []
    if not resolved:  # no root ``kitty-specs/`` at all also lands here
        return _scan_off_root_handle(repo_root, handle)
    mission_dir = resolved[0]
    meta = _read_scanned_meta(mission_dir)
    if meta is None:
        # Named, but unreadable: say so rather than report a healthy Mission (exit 0).
        unreadable = DoctorFinding(
            severity="error",
            message=f"Mission {handle!r} resolved to {mission_dir}, but its meta.json could not be read; nothing was checked or repaired.",
            next_step=f"Run `spec-kitty doctor mission-state --mission {handle}` for details.",
            error_code=_META_UNREADABLE_CODE,
            extra={"mission_dir": str(mission_dir)},
        )
        return _MissionScan(missions=[], warnings=[unreadable], scoped_mission_id=None, scoped_mission_slug=mission_dir.name)
    scanned = _ScannedMission(meta=meta, mission_dir=_root_dir_or_none(repo_root, mission_dir))
    return _MissionScan(
        missions=[scanned],
        warnings=[],
        scoped_mission_id=_str_or_none(meta.get("mission_id")),
        scoped_mission_slug=_str_or_none(meta.get("mission_slug")) or mission_dir.name,
    )


def _scan_off_root_handle(repo_root: Path, handle: str) -> _MissionScan:
    """*handle* among the Missions no root-checkout directory carries; none or several fail closed."""
    from specify_cli.context.mission_resolver import AmbiguousHandleError, MissionNotFoundError, iter_kitty_specs_children

    # The resolver already covered the root checkout's directories: skip re-reading them on
    # every Mission branch (a branch cut from the target inherits all of them).
    root_names = frozenset(child.name for child in iter_kitty_specs_children(repo_root))
    off_root, _warnings = _off_root_missions(repo_root, root_names)
    matches = [m for m in off_root if _matches_handle(m.meta, handle)]
    if len(matches) > 1:
        raise AmbiguousHandleError(handle, [])
    if not matches:
        raise MissionNotFoundError(handle)
    meta = matches[0].meta
    return _MissionScan(
        missions=matches,
        warnings=[],
        scoped_mission_id=_str_or_none(meta.get("mission_id")),
        scoped_mission_slug=_str_or_none(meta.get("mission_slug")),
    )


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _root_dir_or_none(repo_root: Path, mission_dir: Path) -> Path | None:
    """*mission_dir* when it is the repository root checkout's own copy, else ``None``."""
    root_specs = (repo_root / KITTY_SPECS_DIR).resolve()
    return mission_dir if mission_dir.resolve().parent == root_specs else None


def _scan_missions(repo_root: Path, mission_filter: str | None) -> _MissionScan:
    """Every Mission a run covers (#7552): the root checkout's, then off-root ones; or the one named."""
    if mission_filter is not None:
        return _scan_scoped(repo_root, mission_filter)
    missions: list[_ScannedMission] = []
    root_names: set[str] = set()
    for mission_dir in _resolve_mission_dirs(repo_root, None):
        root_names.add(mission_dir.name)
        meta = _read_scanned_meta(mission_dir)
        if meta is not None:
            missions.append(_ScannedMission(meta=meta, mission_dir=mission_dir))
    off_root, warnings = _off_root_missions(repo_root, frozenset(root_names))
    return _MissionScan(missions=missions + off_root, warnings=warnings, scoped_mission_id=None)


def _strands_in_scope(findings: list[DoctorFinding], scan: _MissionScan, mission_filter: str | None) -> list[DoctorFinding]:
    """FR-003: under ``--mission`` keep only that Mission's reconcile-marker findings.

    A marker finding that names no Mission (unparseable) belongs to no scope, so only
    an unscoped run reports (and may act on) it.
    """
    if mission_filter is None:
        return findings
    return [f for f in findings if _strand_belongs_to(f, scan)]


def _strand_belongs_to(finding: DoctorFinding, scan: _MissionScan) -> bool:
    """A marker finding is the scoped Mission's by ``mission_id``, else (no id on either side) by slug."""
    marker_id = finding.extra.get("mission_id")
    if scan.scoped_mission_id is not None and marker_id is not None:
        return bool(marker_id == scan.scoped_mission_id)
    return scan.scoped_mission_slug is not None and finding.extra.get("mission_slug") == scan.scoped_mission_slug


def _mission_findings(repo_root: Path, scanned: _ScannedMission, check_staleness: bool) -> list[DoctorFinding]:
    """The per-Mission checks for one scanned Mission."""
    meta = scanned.meta
    coord_findings = _check_coordination_worktree_health(repo_root, meta)
    for f in coord_findings:
        if f.error_code == "COORDINATION_WORKTREE_NEVER_CREATED" and scanned.mission_dir is not None:
            f.extra["meta_path"] = str(scanned.mission_dir / "meta.json")
        if f.error_code == "COORDINATION_WORKTREE_MISSING" and scanned.branch_only:
            f.extra[_BRANCH_ONLY_EXTRA] = True
    findings = [*coord_findings, *_check_lane_sparse_checkout_drift(repo_root, meta)]
    if check_staleness:
        findings.extend(_check_coord_branch_staleness(repo_root, meta))
    return findings


def _collect_coordination_findings(
    repo_root: Path,
    check_staleness: bool = False,
    mission_filter: str | None = None,
) -> list[DoctorFinding]:
    """Run all coordination + git-health checks and return the aggregated findings.

    ``check_staleness`` (FR-008, ``--check-staleness``) additionally folds in
    the Gap-1 coord-branch-vs-``target_branch`` staleness finding for every
    coordinated mission. Off by default so the baseline ``doctor
    coordination`` output stays unchanged.

    ``mission_filter`` (FR-012, ``--mission``) scopes the per-Mission checks AND
    the stranded-revert markers (#7552, FR-003) to the single Mission the handle
    names; the read-only repo-level checks (git version, tracked-worktrees
    hygiene) always run. Without a filter the scan covers the root checkout's
    Missions plus the Missions only a coordination worktree or a Mission branch
    carries (#7552, FR-005/FR-006). Unresolvable / ambiguous handles raise (see
    :func:`_scan_scoped`).
    """
    scan = _scan_missions(repo_root, mission_filter)
    findings: list[DoctorFinding] = []
    findings.extend(_check_git_version())
    # FR-035 (#1772 Bug 0): repo-level tracked-.worktrees/ hygiene check.
    findings.extend(_check_tracked_worktrees_content(repo_root))
    # FR-007 (#2786 / #2367-B): stranded-coord-revert re-verification, scoped (#7552).
    findings.extend(_strands_in_scope(_check_stranded_coord_revert(repo_root), scan, mission_filter))
    findings.extend(scan.warnings)
    for scanned in scan.missions:
        findings.extend(_mission_findings(repo_root, scanned, check_staleness))
    return findings


def _coord_branch_remote_skip_reason(repo_root: Path, coord_branch: str) -> str | None:
    """Re-verify *coord_branch* against the remote before a destructive flatten.

    Returns ``None`` when the flatten may proceed (the WP01 shared
    :func:`~specify_cli.git.remote_probes.remote_branch_lookup` primitive
    answered ``CLEAN_MISS`` -- a reachable remote genuinely does not have the
    branch -- or ``NO_REMOTE`` -- there is no remote authority to consult, so
    local-only authority is retained). Returns an actionable skip-reason
    string when the flatten must NOT proceed: ``HIT`` (the branch is still
    genuinely present on a remote) or ``ERROR`` (fail-closed -- an
    inconclusive network condition must never be read as "safe to destroy",
    NFR-002). C-001: consumes the ONE shared primitive, never a second
    hand-rolled remote check.
    """
    from specify_cli.git.remote_probes import RemoteLookup, remote_branch_lookup

    outcome = remote_branch_lookup(repo_root, coord_branch)
    if outcome is RemoteLookup.HIT:
        return _COORD_BRANCH_REMOTE_HIT_SKIP_HINT
    if outcome is RemoteLookup.ERROR:
        return _COORD_BRANCH_REMOTE_ERROR_SKIP_HINT
    return None


def _fix_never_created_branches(
    findings: list[DoctorFinding], repo_root: Path | None = None
) -> list[str]:
    """Remove stale ``coordination_branch`` keys from meta.json.

    Targets only ``COORDINATION_WORKTREE_NEVER_CREATED`` findings that carry
    a ``meta_path`` in their ``extra`` dict (populated by
    :func:`_collect_coordination_findings`). After removal, call
    :func:`~specify_cli.migration.backfill_topology.backfill_topology_repo` with
    ``runtime_reading=True`` so topology is re-stamped with its RUNTIME reading
    (never a derived ``single_branch``) from the now-absent key.

    When *repo_root* is given (the real ``--fix`` dispatch path always passes
    it, via :func:`_apply_never_created_fix`), each finding's coordination
    branch is independently re-verified against the remote
    (:func:`_coord_branch_remote_skip_reason`, FR-004 / #4979) BEFORE the
    destructive flatten runs -- a last line of defence behind WP01's fix at
    the CHECK site, so a remote-present branch is never flattened even if a
    ``NEVER_CREATED`` finding is somehow reached. *repo_root* defaults to
    ``None`` so every pre-existing caller that predates this guard keeps its
    original unconditional-flatten behaviour unchanged.

    Returns a list of mission slugs that were modified.
    """
    from specify_cli.mission_metadata import flatten_coordination_metadata, load_meta_or_empty

    fixed: list[str] = []
    for f in findings:
        if f.error_code != "COORDINATION_WORKTREE_NEVER_CREATED":
            continue
        meta_path_str = f.extra.get("meta_path")
        if not meta_path_str:
            continue
        mission_dir = Path(str(meta_path_str)).parent
        meta = load_meta_or_empty(mission_dir)
        coord_branch = meta.get("coordination_branch")
        if not coord_branch:
            continue
        if repo_root is not None:
            skip_reason = _coord_branch_remote_skip_reason(repo_root, str(coord_branch))
            if skip_reason is not None:
                console.print(
                    f"[yellow]Skipped:[/yellow] {mission_dir.name}/meta.json -- "
                    f"coordination branch {coord_branch!r} {skip_reason}"
                )
                continue
        # Canonical three-mutation flatten (#3219 / FR-015 / D-PLAN-17), converged
        # onto the ONE shared primitive: clears `coordination_branch`, pops the
        # stale `topology` so the caller re-stamps it (backfill
        # never overwrites an existing topology, and every mission minted
        # post-#2069 stores `topology` at create time -- leaving it would keep
        # the mission routed through coordination, a false-green flatten), and
        # records the flatten via `flattened=True` (#2614 adversarial-squad
        # remediation).
        flatten_coordination_metadata(mission_dir)
        fixed.append(mission_dir.name)
    return fixed


def _parse_reconcile_marker(
    marker: dict[str, object] | None,
) -> tuple[str, str, str, list[str]] | None:
    """Validate a ``pending_coord_reconcile`` marker into repair inputs.

    Returns ``(coord_ref, captured_sha, coord_worktree, stranded_wp_ids)`` or
    ``None`` when the marker is malformed (missing ref/sha/worktree or an empty
    strand — an empty strand is not a strand, per the data-model derivation
    contract). ``coord_worktree`` stays a ``str`` so the finding's ``extra`` dict
    remains JSON-serializable; the fixer rehydrates it to a ``Path``.
    """
    if not marker:
        return None
    coord_ref = marker.get("coord_ref")
    captured_sha = marker.get("captured_sha")
    coord_worktree = marker.get("coord_worktree")
    stranded = marker.get("stranded_wp_ids")
    if not (isinstance(coord_ref, str) and coord_ref):
        return None
    if not (isinstance(captured_sha, str) and captured_sha):
        return None
    if not (isinstance(coord_worktree, str) and coord_worktree):
        return None
    if not (isinstance(stranded, list) and stranded):
        return None
    return coord_ref, captured_sha, coord_worktree, [str(w) for w in stranded]


def _marker_extra(state: object, coord_ref: str, captured_sha: str,
                  coord_worktree: str, candidate_wps: list[str],
                  remaining: list[str]) -> dict[str, object]:
    """Assemble the stable ``extra`` payload shared by the strand findings."""
    from specify_cli.consolidation.state import STRAND_SHAS_KEY, marker_strand_shas

    return {
        "mission_id": getattr(state, "mission_id", None),
        "mission_slug": getattr(state, "mission_slug", None),
        "coord_ref": coord_ref,
        "captured_sha": captured_sha,
        "coord_worktree": coord_worktree,
        "candidate_wps": candidate_wps,
        "stranded_wp_ids": remaining,
        STRAND_SHAS_KEY: marker_strand_shas(getattr(state, "pending_coord_reconcile", None)),
    }


def _finding_for_reconcile_marker(
    state: object, repo_root: Path
) -> DoctorFinding | None:
    """Re-verify one ``pending_coord_reconcile`` marker → a single finding (or None).

    Returns ``None`` only for a genuinely-stale marker (the committed ref
    re-derives coherent, US2-S5). Every other terminal path yields a finding — a
    safety-net checker must never silently drop a marker (reviewer-renata LOW):

    * un-parseable marker → ``warning`` (:data:`_MARKER_UNPARSEABLE_CODE`);
    * unresolvable/ambiguous mission slug → ``warning``
      (:data:`_MARKER_UNRESOLVABLE_MISSION_CODE`);
    * live strand whose coord worktree is pruned → ``warning`` STUCK
      (:data:`_STRANDED_COORD_REVERT_STUCK_CODE`) — ``--fix`` cannot revert it;
    * live strand with an intact worktree → ``error``
      (:data:`_STRANDED_COORD_REVERT_CODE`), healable by ``--fix``.
    """
    from mission_runtime import MissionArtifactKind

    from specify_cli.coordination.coherence import coord_incoherent_done_wps
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        resolve_planning_read_dir,
    )

    mission_slug = getattr(state, "mission_slug", None)
    mission_id = getattr(state, "mission_id", None)
    base_extra: dict[str, object] = {"mission_id": mission_id, "mission_slug": mission_slug}

    parsed = _parse_reconcile_marker(getattr(state, "pending_coord_reconcile", None))
    if parsed is None:
        return DoctorFinding(
            severity="warning",
            message=(
                f"Mission {mission_slug!r} carries a `pending_coord_reconcile` marker "
                "that could not be parsed into repair inputs."
            ),
            next_step=_MARKER_UNPARSEABLE_HINT,
            error_code=_MARKER_UNPARSEABLE_CODE,
            extra=base_extra,
        )
    coord_ref, captured_sha, coord_worktree, candidate_wps = parsed
    if mission_slug is None:
        # No slug to resolve a planning directory — surface a warning rather
        # than passing None into the read seam and crashing the doctor sweep.
        return DoctorFinding(
            severity="warning",
            message=(
                "A `pending_coord_reconcile` marker is present but its mission "
                "carries no `mission_slug` to resolve a planning directory."
            ),
            next_step=_MARKER_UNRESOLVABLE_MISSION_HINT,
            error_code=_MARKER_UNRESOLVABLE_MISSION_CODE,
            extra=base_extra,
        )
    try:
        # Same canonicalizing WORK_PACKAGE_TASK read seam the executor's mark/heal
        # use (folds a bare handle → `<slug>-<mid8>`), so all three strand sites
        # resolve the identical feature_dir — a raw resolver here would read a
        # divergent path on a non-canonical slug and silently miss the strand.
        feature_dir = resolve_planning_read_dir(
            repo_root, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )
    except (ValueError, MissionSelectorAmbiguous):
        # Unsafe/ambiguous mission_slug — surface a warning rather than silently drop.
        return DoctorFinding(
            severity="warning",
            message=(
                f"Mission {mission_slug!r} on a `pending_coord_reconcile` marker "
                "could not be resolved to a planning directory."
            ),
            next_step=_MARKER_UNRESOLVABLE_MISSION_HINT,
            error_code=_MARKER_UNRESOLVABLE_MISSION_CODE,
            extra=base_extra,
        )
    remaining = coord_incoherent_done_wps(
        coord_ref, candidate_wps, repo_root=repo_root, feature_dir=feature_dir,
    )
    if not remaining:
        # Stale marker: the committed ref re-derives coherent (US2-S5). No finding.
        return None
    extra = _marker_extra(state, coord_ref, captured_sha, coord_worktree, candidate_wps, remaining)
    if not Path(coord_worktree).exists():
        # Live strand, but the coord worktree is pruned — `--fix` cannot revert it.
        # It is STILL a committed-ref split-brain, so it stays an `error` (exit 1):
        # the coord branch carries a wrong `done` and the mission is NOT healthy.
        # Only the `next_step` changes — a manual-recovery hint instead of looping
        # the user back to `--fix` (debugger-debbie HIGH: a `warning` here exits 0
        # and hides the split-brain).
        return DoctorFinding(
            severity="error",
            message=(
                f"Coordination ref {coord_ref!r} for mission {mission_slug!r} still "
                f"strands WP(s) {remaining} at `done`, but its coordination worktree "
                f"{coord_worktree!r} no longer exists — `--fix` cannot revert it."
            ),
            next_step=_STRANDED_COORD_REVERT_STUCK_HINT,
            error_code=_STRANDED_COORD_REVERT_STUCK_CODE,
            extra=extra,
        )
    return DoctorFinding(
        severity="error",
        message=(
            f"Coordination ref {coord_ref!r} for mission "
            f"{mission_slug!r} still reduces WP(s) {remaining} to "
            "`done` after a merge rollback (expected `approved`)."
        ),
        next_step=_STRANDED_COORD_REVERT_HINT.replace("<mission>", mission_slug or mission_id or "<mission>"),
        error_code=_STRANDED_COORD_REVERT_CODE,
        extra=extra,
    )


def _check_stranded_coord_revert(repo_root: Path) -> list[DoctorFinding]:
    """FR-007: re-verify each reconcile marker against the **committed** coord ref.

    Enumerate ``pending_coord_reconcile`` markers via WP02's
    :func:`~specify_cli.consolidation.state.iter_pending_coord_reconcile_markers` — NOT
    ``load_state(mission_id=None)`` (it *raises* ``MergeAmbiguousStateError`` on
    >=2 markers) and NOT a re-implemented runtime-path scan (a second path
    authority / DIR-044 breach). Each marker is re-verified by
    :func:`_finding_for_reconcile_marker`, which re-derives the strand **from the
    committed ref** (never from marker-presence) and returns exactly one finding —
    ``error`` for a healable live strand, ``warning`` for a pruned-worktree STUCK
    strand or an un-parseable/unresolvable marker, and ``None`` only for a
    genuinely-stale marker (US2-S5, the load-bearing negative AC).
    """
    from specify_cli.consolidation.state import iter_pending_coord_reconcile_markers

    findings: list[DoctorFinding] = []
    for state in iter_pending_coord_reconcile_markers(repo_root):
        finding = _finding_for_reconcile_marker(state, repo_root)
        if finding is not None:
            findings.append(finding)
    return findings


def _clear_pending_marker(repo_root: Path, mission_id: str) -> None:
    """Atomically clear a mission's ``pending_coord_reconcile`` marker after a heal."""
    from specify_cli.consolidation.state import load_state, save_state

    state = load_state(repo_root, mission_id=mission_id)
    if state is None:
        return
    state.pending_coord_reconcile = None
    save_state(state, repo_root)


def _unrecorded_strand_finding(
    outcome: CoordRepairOutcome, mission_id: str, mission_slug: str, coord_ref: str
) -> DoctorFinding:
    """#5572: the honest ``error`` for a heal refused over unrecorded status commits.

    Never a success claim: nothing was reverted and the marker is kept. A marker that
    recorded no strand commits is named as such; otherwise the foreign commits are listed so the operator
    can see what a revert would have erased.
    """
    if outcome.legacy_marker:
        detail = "its reconcile marker recorded no strand commits (written by an older release, or the range was unreadable when it was written)"
    elif outcome.foreign_status_commits:
        foreign = ", ".join(sha[:12] for sha in outcome.foreign_status_commits)
        detail = f"the status log holds commit(s) the marker did not record ({foreign}), e.g. a later reopen"
    else:
        detail = "the status log no longer matches the commits the marker recorded"
    return DoctorFinding(
        severity="error",
        message=(
            f"Refusing to revert the stranded `done` on {coord_ref!r} for mission "
            f"{mission_slug!r}: {detail}. Nothing was reverted; the marker is kept."
        ),
        next_step=_STRANDED_COORD_REVERT_UNRECORDED_HINT_TEMPLATE.format(mission_id=mission_id),
        error_code=_STRANDED_COORD_REVERT_UNRECORDED_CODE,
        extra={"mission_id": mission_id, "mission_slug": mission_slug},
    )


def _heal_one_strand(
    f: DoctorFinding, repo_root: Path
) -> tuple[str | None, DoctorFinding | None]:
    """Attempt to heal one live-strand finding.

    Returns ``(healed_slug, warning)``: at most one is non-``None``. A genuine heal
    yields ``(slug, None)`` (and clears the marker); an un-parseable marker, an
    unresolvable mission, a repair that reports a pruned worktree
    (``worktree_missing``), or a repair refused because the coordination
    worktree is checked out on the wrong branch (``branch_mismatch``, sibling
    of #4920/#4950) all yield ``(None, warning)`` — a safety-net fixer must
    never silently drop a marker, and neither refusal is one simply re-running
    ``--fix`` can resolve on its own. ``head_advanced`` / generic revert-error
    outcomes yield ``(None, None)``: the strand is intentionally left for the
    next pass and the check's persistent ``error`` finding still surfaces it.
    """
    from mission_runtime import MissionArtifactKind

    from specify_cli.consolidation.state import marker_strand_shas
    from specify_cli.coordination.coherence import repair_coord_strand
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        resolve_planning_read_dir,
    )

    parsed = _parse_reconcile_marker(f.extra)
    mission_id = f.extra.get("mission_id")
    mission_slug = f.extra.get("mission_slug")
    if parsed is None or not isinstance(mission_id, str) or not isinstance(mission_slug, str):
        return None, DoctorFinding(
            severity="warning",
            message="A live-strand finding carried an unparseable reconcile marker.",
            next_step=_MARKER_UNPARSEABLE_HINT,
            error_code=_MARKER_UNPARSEABLE_CODE,
            extra={"mission_id": mission_id, "mission_slug": mission_slug},
        )
    coord_ref, captured_sha, coord_worktree, candidate_wps = parsed
    try:
        # Mirror the check + the executor: the canonicalizing WORK_PACKAGE_TASK
        # read seam (one feature_dir authority across all three strand sites).
        feature_dir = resolve_planning_read_dir(
            repo_root, mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )
    except (ValueError, MissionSelectorAmbiguous):
        return None, DoctorFinding(
            severity="warning",
            message=(
                f"Mission {mission_slug!r} on a live-strand finding could not be "
                "resolved to a planning directory; skipping its heal."
            ),
            next_step=_MARKER_UNRESOLVABLE_MISSION_HINT,
            error_code=_MARKER_UNRESOLVABLE_MISSION_CODE,
            extra={"mission_id": mission_id, "mission_slug": mission_slug},
        )
    outcome = repair_coord_strand(
        coord_ref=coord_ref,
        captured_sha=captured_sha,
        coord_worktree=Path(coord_worktree),
        candidate_wps=candidate_wps,
        repo_root=repo_root,
        feature_dir=feature_dir,
        strand_shas=marker_strand_shas(f.extra),
    )
    if outcome.healed:
        _clear_pending_marker(repo_root, mission_id)
        return mission_slug, None
    if outcome.legacy_marker or outcome.strand_mismatch:
        return None, _unrecorded_strand_finding(outcome, mission_id, mission_slug, coord_ref)
    if outcome.worktree_missing:
        # Still a committed-ref split-brain `--fix` couldn't heal — stays `error`
        # (exit 1) with a manual-recovery hint; a `warning` would exit 0 and hide it.
        return None, DoctorFinding(
            severity="error",
            message=(
                f"Coordination worktree {coord_worktree!r} for mission "
                f"{mission_slug!r} no longer exists — `--fix` cannot revert its strand."
            ),
            next_step=_STRANDED_COORD_REVERT_STUCK_HINT,
            error_code=_STRANDED_COORD_REVERT_STUCK_CODE,
            extra={"mission_id": mission_id, "mission_slug": mission_slug},
        )
    if outcome.branch_mismatch:
        # Sibling of #4920/#4950: the repair refused to run the revert because
        # the coord worktree is on a foreign branch — `--fix` re-run alone
        # can never succeed, so this must not fall through to the silent
        # `(None, None)` "leave it for the next pass" case below (that case
        # is for outcomes the CHECK's own persistent `error` finding still
        # surfaces; a branch-mismatch refusal needs its own actionable
        # `next_step`, not the generic "run `--fix`" hint, which would keep
        # telling the operator to do the one thing that cannot work).
        actual = _coord_worktree_actual_head(Path(coord_worktree)).removeprefix("refs/heads/")
        return None, DoctorFinding(
            severity="error",
            message=(
                f"Coordination worktree {coord_worktree!r} for mission "
                f"{mission_slug!r} is on {actual!r}, not {coord_ref!r} — `--fix` "
                "refuses to revert its strand there."
            ),
            next_step=_STRANDED_COORD_REVERT_BRANCH_MISMATCH_HINT,
            error_code=_STRANDED_COORD_REVERT_BRANCH_MISMATCH_CODE,
            extra={"mission_id": mission_id, "mission_slug": mission_slug},
        )
    return None, None


def _fix_stranded_reverts(
    findings: list[DoctorFinding], repo_root: Path
) -> tuple[list[str], list[DoctorFinding]]:
    """Heal every live-strand finding via WP02's shared repair primitive.

    Delegates to
    :func:`~specify_cli.coordination.coherence.repair_coord_strand` (strand-gated +
    self-sufficient: it re-derives the strand from the committed ref, HEAD-freshness
    guards the concurrency TOCTOU, and it performs the scoped clean-to-HEAD so the
    forward revert applies over the byte-restored dirty tree) and clears the marker
    only on a genuine heal — so ``--fix`` run twice is byte-stable and the marker is
    cleared exactly once. Never re-implements the revert.

    Returns ``(healed_slugs, warnings)``: the mission slugs healed on this call, and
    ``warning``-severity findings for markers that could not be healed and would
    otherwise be silently dropped (unparseable marker, unresolvable mission, pruned
    coord worktree).
    """
    healed: list[str] = []
    warnings: list[DoctorFinding] = []
    for f in findings:
        if f.error_code != _STRANDED_COORD_REVERT_CODE:
            continue
        slug, warning = _heal_one_strand(f, repo_root)
        if slug is not None:
            healed.append(slug)
        if warning is not None:
            warnings.append(warning)
    return healed, warnings


def _apply_never_created_fix(findings: list[DoctorFinding], repo_root: Path) -> None:
    """Flatten missions with a stale ``coordination_branch`` key, then re-backfill topology.

    Passes *repo_root* through to :func:`_fix_never_created_branches` so every
    finding is re-verified against the remote before it is flattened (FR-004).
    """
    fixable = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_NEVER_CREATED"]
    if not fixable:
        return
    fixed_slugs = _fix_never_created_branches(fixable, repo_root)
    for slug in fixed_slugs:
        console.print(
            f"[green]Flattened:[/green] removed coordination_branch from {slug}/meta.json"
        )
    if fixed_slugs:
        from specify_cli.migration.backfill_topology import backfill_topology_repo

        # runtime_reading (#5100): an unattended --fix must never opt a
        # flattened mission into single_branch; a derived single_branch cell is
        # stamped as lanes, which is how the unstamped mission already ran.
        for slug in fixed_slugs:
            backfill_topology_repo(repo_root, mission_slug=slug, runtime_reading=True)
        console.print(
            "[green]Topology backfilled.[/green] "
            "Run `spec-kitty doctor coordination` to verify."
        )


def _apply_stranded_revert_fix(
    findings: list[DoctorFinding], repo_root: Path
) -> list[DoctorFinding]:
    """Heal live coord strands (FR-007) via the shared repair primitive.

    Returns the ``warning`` findings for strands that could not be healed (pruned
    worktree / unparseable / unresolvable) so the caller can fold them into the
    post-fix findings — a safety-net fixer never silently drops a marker.
    """
    healed, warnings = _fix_stranded_reverts(findings, repo_root)
    for slug in healed:
        console.print(
            f"[green]Healed:[/green] reverted the stranded coordination `done` and "
            f"cleared the reconcile marker for {slug}."
        )
    return warnings


def _branch_only_skip_warning(mission_slug: str) -> DoctorFinding:
    """#7552: an unscoped ``--fix`` leaves a branch-only Mission's worktree alone, and says how to restore it."""
    return DoctorFinding(
        severity="warning",
        message=(
            f"Mission {mission_slug!r} exists only on its Mission branch; its coordination worktree was not "
            "restored, because `--all-missions` does not bring back worktrees removed on purpose "
            "(for example by `consolidate --abort`)."
        ),
        next_step=f"Run `spec-kitty doctor coordination --fix --mission {mission_slug}` to restore it.",
        error_code=_BRANCH_ONLY_NOT_RESTORED_CODE,
        extra={"mission_slug": mission_slug, _BRANCH_ONLY_EXTRA: True},
    )


def _branch_only_identity(f: DoctorFinding) -> dict[str, str]:
    """The finding's resolved coordination branch and mid8, for a branch-only Mission only.

    The materializer otherwise re-reads ``meta.json`` from a checkout, and a Mission only
    its branch carries has none there (a silent no-op). An on-disk Mission keeps the
    materializer's own derivation, so its worktree path is the one decision writes use.
    """
    branch, mid8 = f.extra.get("coord_branch"), f.extra.get("mid8")
    if f.extra.get(_BRANCH_ONLY_EXTRA) and isinstance(branch, str) and branch and isinstance(mid8, str) and mid8:
        return {"coordination_branch": branch, "mid8": mid8}
    return {}


def _apply_missing_worktree_fix(
    findings: list[DoctorFinding], repo_root: Path, *, scoped: bool = False
) -> list[DoctorFinding]:
    """#5113 / FR-014: materialize a missing coordination worktree (branch present).

    Error-code-scoped and idempotent. Materializes through the canonical
    coordination-layer helper (never a raw ``git worktree add``), so stale
    registrations and remote-only refusal behave exactly as for a decision
    write.

    #5113: a remote-only branch refusal here must
    NOT relay :class:`CoordinationWorktreeUnmaterialized`'s generic
    ``next_step`` verbatim -- that text itself says "run `doctor coordination
    --fix`", which is exactly the command that just refused, looping the
    operator. Reclassify it here (the same local-head check the finding
    builder already applies) and emit the truthful ordered fetch/branch/fix
    steps via the ONE shared :func:`_coord_worktree_missing_remote_only_steps`
    builder instead.
    """
    from specify_cli.coordination.surface_resolver import (
        CoordinationWorktreeUnmaterialized,
        _coord_branch_is_local_head,
        materialize_coord_surface_for_write,
    )

    warnings: list[DoctorFinding] = []
    for f in findings:
        if f.error_code != "COORDINATION_WORKTREE_MISSING":
            continue
        mission_slug = f.extra.get("mission_slug")
        if not isinstance(mission_slug, str) or not mission_slug:
            # Defensive: a finding without the mission_slug extra (e.g. an older
            # producer) is skipped rather than crashing the whole `--fix` run.
            continue
        extra_branch = f.extra.get("coord_branch")
        if f.extra.get(_BRANCH_ONLY_EXTRA) and not scoped:
            warnings.append(_branch_only_skip_warning(mission_slug))
            continue
        try:
            materialize_coord_surface_for_write(repo_root, mission_slug, **_branch_only_identity(f))
        except CoordinationWorktreeUnmaterialized as exc:
            # #5258: classify on the branch the refusal itself names when the
            # finding carries no ``coord_branch`` extra -- relaying the
            # exception's remote-only text would name ``--fix`` again (the loop
            # #5113 exists to prevent) and omit the ``git branch`` step.
            coord_branch = (
                extra_branch
                if isinstance(extra_branch, str) and extra_branch
                else exc.coordination_branch
            )
            if coord_branch and not _coord_branch_is_local_head(repo_root, coord_branch):
                next_step = _coord_worktree_missing_remote_only_steps(
                    repo_root, mission_slug, coord_branch,
                )
                message = (
                    f"Could not materialize the coordination worktree for "
                    f"mission {mission_slug!r}: the coordination branch "
                    f"{coord_branch!r} exists only as a remote-tracking ref. "
                    f"{next_step}"
                )
            else:
                next_step = exc.next_step
                message = (
                    f"Could not materialize the coordination worktree for "
                    f"mission {mission_slug!r}: {exc.next_step}"
                )
            warnings.append(DoctorFinding(
                severity="warning",
                message=message,
                next_step=next_step,
                error_code=f.error_code,
                extra={"mission_slug": mission_slug},
            ))
            continue
        console.print(
            f"[green]Materialized:[/green] coordination worktree for mission "
            f"{mission_slug!r}."
        )
    return warnings


def _apply_coordination_fixes(
    findings: list[DoctorFinding], repo_root: Path, *, scoped: bool = False
) -> list[DoctorFinding]:
    """Run every registered ``--fix`` handler over the collected findings.

    Extracted so adding a fixer keeps the caller (:func:`run_coordination_health`)
    and this dispatch each well under the CC-15 ceiling. Each handler is
    error-code-scoped and idempotent, so the order is irrelevant. Returns any
    ``warning`` findings the fixers raised (e.g. a strand whose coord worktree is
    pruned, or a remote-only branch the missing-worktree fixer refused to
    auto-materialize) so the entrypoint surfaces them in the post-fix output.

    The WP06 Gap-1 fast-forward (:func:`_apply_coord_staleness_fixes`) is
    deliberately NOT dispatched from here: unlike every other fixer above, an
    unsafe per-mission precondition surfaces as its own ``error`` finding
    rather than folding into this function's return, so it runs as its own
    step in :func:`run_coordination_health` — AFTER these idempotent,
    order-irrelevant fixers have already applied.
    """
    _apply_never_created_fix(findings, repo_root)
    warnings = _apply_missing_worktree_fix(findings, repo_root, scoped=scoped)
    return warnings + _apply_stranded_revert_fix(findings, repo_root)


# ---------------------------------------------------------------------------
# WP06 (FR-009, Gap-1, C-003 MINIMIZED): the ONE `--fix` behaviour for coord-
# branch-vs-target staleness -- a fast-forward, and ONLY when unambiguously
# safe. Never grows into a general "repair arbitrary drifted content" command.
# ---------------------------------------------------------------------------


def _unified_diff(repo_root: Path, ref_a: str, ref_b: str) -> str:
    """Return ``git diff ref_a ref_b`` output, or ``""`` when git is unreadable.

    The refs come from ``meta.json``: ``--end-of-options`` stops one such as
    ``--output=<path>`` being read as an option, and the closing ``--`` stops
    git reading a branch name as a path.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--end-of-options", ref_a, ref_b, "--"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return result.stdout


#: Blocked Gap-1 fix: a surfaced ``error`` finding rather than an abort
#: (renata LOW). Shared by every "nothing was mutated" refusal --
#: :func:`_coord_staleness_fix_blocked_finding` (diverged coord branch, or a
#: dirty coord worktree), :func:`_coord_worktree_foreign_repo_finding` (coord
#: worktree does not belong to this repository), and
#: :func:`_coord_staleness_fix_merge_failed_finding` (the ``--ff-only`` merge
#: itself failed). :func:`_coord_worktree_mismatch_fix_blocked_finding` (coord
#: worktree on the wrong branch) also reuses this code, even though its
#: dedicated diff-free message differs from the others.
_COORD_STALE_FIX_BLOCKED_CODE = "COORDINATION_BRANCH_STALE_FIX_BLOCKED"


def _coord_staleness_fix_blocked_finding(
    repo_root: Path, coord_branch: str, target_branch: str, *, reason: str,
) -> DoctorFinding:
    """FR-009: an unsafe Gap-1 fast-forward precondition, as a surfaced ``error``.

    Renata LOW (coord-commit-integrity squad): a per-mission unsafe
    precondition (diverged coord branch, or a dirty coord worktree) must not
    raise and abort the entire ``--fix`` run -- doing so let one mission's
    Gap-1 problem block the flatten-cleanup fix for every OTHER mission
    processed in the same run. Returning an ``error`` finding instead keeps
    C-005 warn-first (the caller never attempts the merge -- mutates
    NOTHING) and FR-009's fail-loud-with-diff contract (the diff is embedded
    in the message, exactly as it was previously printed to the console),
    while letting :func:`_apply_coord_staleness_fixes` continue to the next
    mission. ``reason`` shapes the message (e.g. ``"diverged from"`` /
    ``"not cleanly fast-forwardable vs"``); the diff itself is always
    ``coord_branch..target_branch``. The wrong-branch/detached-HEAD case has
    its own dedicated, diff-free finding -- see
    :func:`_coord_worktree_mismatch_fix_blocked_finding`.
    """
    diff_text = _unified_diff(repo_root, coord_branch, target_branch)
    message = (
        f"Refusing to fast-forward: coordination branch {coord_branch!r} "
        f"is {reason} target branch {target_branch!r} — `--fix` mutates nothing."
    )
    if diff_text:
        message = f"{message}\n{diff_text}"
    return DoctorFinding(
        severity="error",
        message=message,
        next_step=(
            "Inspect the diff above and reconcile manually; `--fix` will not "
            "mutate a diverged, dirty, or mismatched coordination worktree."
        ),
        error_code=_COORD_STALE_FIX_BLOCKED_CODE,
    )


def _git_rev_parse_query(cwd: Path, *args: str) -> str:
    """Return stripped stdout of ``git -C cwd rev-parse *args``, or ``""``.

    Distinct from :func:`_rev_parse` (which resolves exactly one ``ref`` to
    a SHA): this passes arbitrary ``rev-parse`` flags (``--git-common-dir``,
    ``--show-toplevel``) used by :func:`_coord_worktree_foreign_repo_finding`.
    """
    try:
        return subprocess.check_output(
            ["git", "-C", str(cwd), "rev-parse", *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _resolved_git_rev_parse_path(cwd: Path, *args: str) -> Path | None:
    """Run :func:`_git_rev_parse_query` and resolve its output against ``cwd``.

    Deliberately does NOT pass ``--path-format=absolute`` -- that flag needs
    git >= 2.31, newer than this module's declared ``_MIN_GIT_VERSION`` (2,
    25). On an older git the flag is echoed back as a literal (unrecognised)
    argument rather than rejected, and ``--git-common-dir``/``--show-toplevel``
    come back relative to ``cwd`` (e.g. ``.git`` in the main checkout) instead
    of absolute -- comparing that against an absolute worktree-side path would
    always mismatch, refusing every legitimate ``--fix``. ``Path(cwd) / out``
    is a no-op when ``out`` is already absolute (git returns an absolute path
    for a linked worktree's common dir), so this single join+resolve handles
    both an old-git relative result and a normal absolute one. Returns
    ``None`` when the underlying git call failed.
    """
    out = _git_rev_parse_query(cwd, *args)
    if not out:
        return None
    return (cwd / out).resolve()


def _coord_worktree_foreign_repo_finding(
    repo_root: Path, worktree: Path, coord_branch: str,
) -> DoctorFinding | None:
    """FR-009 (#4950 second-opinion follow-up): refuse a coord worktree that
    does not belong to THIS repository.

    Branch-NAME equality alone (:func:`_coord_worktree_head_finding`) passes
    for a foreign clone -- or a plain directory under ``.worktrees/`` that
    ``git -C`` silently walks up from to the main checkout -- that happens
    to have a branch named the same as the coord branch (see the
    postcondition repro this closes: a recorded worktree that is a separate
    ``git clone`` genuinely fast-forwards *inside the clone* while the
    declared branch in ``repo_root`` never moves). Before any mutation,
    additionally require the worktree's git-common-dir to match
    ``repo_root``'s (same repository) AND its toplevel to resolve to the
    worktree path itself (a genuine linked worktree, not a subdirectory git
    walked up from). Both sides are resolved via
    :func:`_resolved_git_rev_parse_path` (no ``--path-format=absolute`` --
    see its docstring) and compared as ``Path`` objects rather than raw
    strings. A kept-as-a-separate-helper check (complexity ceiling).
    """
    repo_common_dir = _resolved_git_rev_parse_path(repo_root, "--git-common-dir")
    wt_common_dir = _resolved_git_rev_parse_path(worktree, "--git-common-dir")
    wt_toplevel = _resolved_git_rev_parse_path(worktree, "--show-toplevel")
    same_repo = repo_common_dir is not None and wt_common_dir == repo_common_dir
    is_worktree_root = wt_toplevel is not None and wt_toplevel == worktree.resolve()
    if same_repo and is_worktree_root:
        return None
    return DoctorFinding(
        severity="error",
        message=(
            f"Refusing to fast-forward coordination branch {coord_branch!r}: "
            f"coordination worktree {worktree} does not belong to this "
            "repository (git-common-dir/toplevel mismatch). `--fix` mutates "
            "nothing."
        ),
        next_step=(
            f"Inspect the worktree manually; then run `{_WORKSPACE_RECOVERY_CMD}` "
            "to restore."
        ),
        error_code=_COORD_STALE_FIX_BLOCKED_CODE,
    )


def _coord_worktree_mismatch_fix_blocked_finding(
    worktree: Path, coord_branch: str, head_finding: DoctorFinding,
) -> DoctorFinding:
    """FR-009: a dedicated refusal for a coord worktree off the coord branch.

    #4950 second-opinion follow-up: the mismatch path used to feed
    :func:`_coord_staleness_fix_blocked_finding`, whose message embeds a
    ``coord_branch..target_branch`` diff and "inspect the diff above"
    guidance -- both irrelevant here, since the problem is which branch (or
    no branch, if detached) is checked out in the worktree, not branch
    content. Reuses ``head_finding.next_step`` (the workspaces recovery
    command) so the general health-check warning
    (:func:`_coord_worktree_head_finding`) and this fix-blocked error point
    to the same recovery action.
    """
    actual = _coord_worktree_actual_head(worktree).removeprefix("refs/heads/")
    return DoctorFinding(
        severity="error",
        message=(
            f"Refusing to fast-forward coordination branch {coord_branch!r}: "
            f"coordination worktree {worktree} is on {actual!r}, not "
            f"{coord_branch!r}. `--fix` mutates nothing."
        ),
        next_step=head_finding.next_step,
        error_code=_COORD_STALE_FIX_BLOCKED_CODE,
    )


def _coord_staleness_fix_merge_failed_finding(
    coord_branch: str, target_branch: str, stderr: str,
) -> DoctorFinding:
    """FR-009: a failed ``--ff-only`` merge, as a surfaced ``error`` finding.

    #4950 second-opinion follow-up: every precondition above (divergence,
    dirty worktree, branch mismatch) is checked before the merge runs, so in
    principle the merge itself should never fail -- but ``check=True``
    turning a real-world failure into an uncaught ``CalledProcessError``
    would crash ``run_coordination_health`` (no JSON, no exit code, and
    every OTHER mission's fix in the same run aborted) instead of reporting
    it. A failed ``--ff-only`` mutates nothing, so this reuses
    ``_COORD_STALE_FIX_BLOCKED_CODE`` -- same "nothing was mutated"
    invariant as the other blocked-fix findings.
    """
    message = (
        f"Refusing to fast-forward: coordination branch {coord_branch!r} "
        f"failed to fast-forward to target branch {target_branch!r} — "
        "`--fix` mutates nothing."
    )
    if stderr:
        message = f"{message}\n{stderr.strip()}"
    return DoctorFinding(
        severity="error",
        message=message,
        next_step=(
            "Inspect the coordination worktree and git's error above; "
            "`--fix` did not attempt anything further."
        ),
        error_code=_COORD_STALE_FIX_BLOCKED_CODE,
    )


#: Postcondition failure (#4950 second-opinion follow-up): distinct from
#: ``_COORD_STALE_FIX_BLOCKED_CODE``, whose documented meaning is "nothing
#: was mutated." That is FALSE here -- a fast-forward genuinely ran inside
#: the coord worktree; only the declared ref this run reads back from
#: ``repo_root`` failed to reflect it. The original motivating example (the
#: recorded worktree path is a separate repository/clone, so the merge
#: landed there instead of on the branch `--fix` reports against) is now
#: refused earlier, before any mutation, by
#: :func:`_coord_worktree_foreign_repo_finding`'s git-common-dir/toplevel
#: check -- so this postcondition is defence in depth against whatever can
#: still move the declared ref between the merge and this readback (e.g. a
#: concurrent process advancing/deleting the coord branch), not the primary
#: guard against a foreign repository.
_COORD_STALE_FIX_POSTCONDITION_CODE = "COORDINATION_BRANCH_STALE_FIX_POSTCONDITION_FAILED"


def _coord_staleness_fix_postcondition_finding(
    worktree: Path,
    coord_branch: str,
    target_branch: str,
    expected_sha: str,
    actual_sha: str,
) -> DoctorFinding:
    """Return a fail-loud finding when repair did not update the declared ref."""

    actual = actual_sha[:8] if actual_sha else "unreadable"
    return DoctorFinding(
        severity="error",
        message=(
            "Coordination repair failed its postcondition: a fast-forward "
            f"ran in {worktree} but declared branch {coord_branch!r} is at "
            f"{actual}, expected {expected_sha[:8]} to match target "
            f"{target_branch!r}."
        ),
        next_step=(
            "Inspect the recorded coordination worktree and declared branch; "
            "`--fix` did not report success."
        ),
        error_code=_COORD_STALE_FIX_POSTCONDITION_CODE,
    )


def _fix_one_mission_coord_staleness(
    repo_root: Path, mission_meta: dict[str, object],
) -> DoctorFinding | None:
    """Attempt the Gap-1 fast-forward for a single mission.

    Skips silently (nothing to fix, returns ``None``) when the mission is not
    coordinated, its identity/``target_branch`` is incomplete, either ref is
    unreadable, the SHAs already match, or the coord worktree does not exist
    (the existing ``COORDINATION_WORKTREE_MISSING``/``NEVER_CREATED`` findings
    already cover that case). Otherwise every precondition must hold before
    any mutation: strict-ancestor, the coord worktree genuinely belongs to
    this repository (:func:`_coord_worktree_foreign_repo_finding`), the
    worktree is on the coord branch (:func:`_coord_worktree_head_finding`),
    and the worktree is clean. Only then does the fast-forward run (``git
    merge --ff-only``, itself belt-and-braces safe), followed by a postcondition
    re-read (:func:`_coord_staleness_fix_postcondition_finding`). A refused
    or failed precondition/postcondition returns an ``error`` finding instead
    of raising, mutating nothing -- most route through
    :func:`_coord_staleness_fix_blocked_finding`, but the foreign-repo,
    branch-mismatch, merge-failure, and postcondition guards each return
    their own dedicated finding instead (renata LOW: a single mission's
    unsafe precondition must not abort ``--fix`` for every OTHER mission in
    the same run).
    """
    shas = _coord_vs_target_shas(repo_root, mission_meta)
    if shas is None:
        return None
    coord_branch, target_branch, coord_sha, target_sha = shas
    if coord_sha == target_sha:
        return None  # nothing to fix: already in sync
    if _is_ff_candidate(repo_root, target_sha, coord_sha):
        return None  # coord strictly ahead: only its own coordination commits (#5440)

    if not _is_ff_candidate(repo_root, coord_sha, target_sha):
        return _coord_staleness_fix_blocked_finding(
            repo_root, coord_branch, target_branch, reason="diverged from",
        )

    # `shas` only proves coordination_branch/target_branch/slug/id are all
    # present and non-blank (see _coord_vs_target_shas); re-resolving here is
    # cheap (dict lookups, no I/O) and keeps this function's own inputs
    # explicit rather than threading slug/id back out of the shared helper.
    identity = _coordination_identity(mission_meta)
    if identity is None:
        return None  # unreachable in practice -- defensive, not an assert
    _coord_branch_unused, mission_slug, mission_id = identity

    from specify_cli.coordination import CoordinationWorkspace

    short = _resolve_coord_short(mission_slug, mission_id)
    worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, short)
    if not worktree.exists():
        return None  # no coord worktree to fast-forward into; worktree-health check covers this

    foreign_repo_finding = _coord_worktree_foreign_repo_finding(repo_root, worktree, coord_branch)
    if foreign_repo_finding is not None:
        return foreign_repo_finding

    head_finding = _coord_worktree_head_finding(worktree, coord_branch)
    if head_finding is not None:
        return _coord_worktree_mismatch_fix_blocked_finding(worktree, coord_branch, head_finding)

    if _coord_worktree_dirty_finding(worktree) is not None:
        return _coord_staleness_fix_blocked_finding(
            repo_root, coord_branch, target_branch, reason="not cleanly fast-forwardable vs",
        )

    # Merge the SHA the postcondition below checks against (not the branch
    # name) so the move and the check refer to the exact same commit --
    # `target_branch` can advance between resolving `target_sha` above and
    # running this merge (#4950 second-opinion follow-up).
    #
    # `check=False`: a failed `--ff-only` must surface as a finding, not
    # raise `CalledProcessError` out of `run_coordination_health` (which
    # would abort every OTHER mission's fix in the same run, and skip the
    # JSON emission entirely) -- see `_coord_staleness_fix_merge_failed_finding`.
    merge_result = subprocess.run(
        ["git", "-C", str(worktree), "merge", "--ff-only", target_sha],
        check=False, capture_output=True, text=True,
    )
    if merge_result.returncode != 0:
        return _coord_staleness_fix_merge_failed_finding(
            coord_branch, target_branch, merge_result.stderr,
        )
    repaired_coord_sha = _rev_parse(repo_root, f"refs/heads/{coord_branch}")
    if repaired_coord_sha != target_sha:
        return _coord_staleness_fix_postcondition_finding(
            worktree, coord_branch, target_branch, target_sha, repaired_coord_sha,
        )
    console.print(
        f"[green]Fast-forwarded:[/green] coordination branch {coord_branch!r} "
        f"({coord_sha[:8]} -> {target_sha[:8]}) to match target {target_branch!r}."
    )
    return None


def _apply_coord_staleness_fixes(
    repo_root: Path, mission_filter: str | None = None
) -> list[DoctorFinding]:
    """FR-009 (Gap-1, C-003 minimized): fast-forward every coordinated mission's
    coord branch to ``target_branch`` -- and ONLY when that is unambiguously safe.

    Iterates every mission under ``kitty-specs/`` (or the single ``mission_filter``
    handle, FR-012) and delegates to :func:`_fix_one_mission_coord_staleness`.
    Stays the ONLY ``--fix`` behaviour for Gap-1 (C-003): it never attempts a
    general repair of arbitrary drifted coordination content. Returns the
    blocked-fix ``error`` findings for any mission whose Gap-1 precondition was
    unsafe (renata LOW) so the caller can fold them into the post-fix findings --
    one such mission no longer aborts fixing every OTHER mission in the same run.
    """
    blocked: list[DoctorFinding] = []
    for scanned in _scan_missions(repo_root, mission_filter).missions:
        finding = _fix_one_mission_coord_staleness(repo_root, scanned.meta)
        if finding is not None:
            blocked.append(finding)
    return blocked


def _emit_coordination_findings(findings: list[DoctorFinding], json_output: bool) -> None:
    """Render coordination findings as JSON or coloured human output."""
    if json_output:
        payload = [
            {
                "severity": f.severity,
                "message": f.message,
                "next_step": f.next_step,
                "error_code": f.error_code,
                "extra": f.extra,
            }
            for f in findings
        ]
        console.print_json(json.dumps(payload, indent=2))
        return
    for f in findings:
        colour = {
            "ok": "green", "warning": "yellow", "error": "red",
        }.get(f.severity, "white")
        console.print(f"[{colour}]{f.severity}[/{colour}]: {f.message}")
        if f.next_step:
            console.print(f"  → {f.next_step}")


def _emit_mission_resolver_error(
    error_code: str, handle: str | None, json_output: bool
) -> None:
    """Emit the canonical error with its stable code and mission handle context."""
    label = "Mission not found" if error_code == "MISSION_NOT_FOUND" else "Ambiguous handle"
    message = f"{label}: {handle!r}"
    if json_output:
        payload = _doctor_shared._json_error(error_code, message)
        payload["handle"] = handle
        console.emit_json(payload)
    else:
        console.print(f"[red]Error:[/red] {message}")


def _refuse_unscoped_fix(fix: bool, mission: str | None, all_missions: bool, json_output: bool) -> None:
    """#7552 (FR-001 / FR-004): refuse before any check runs when the repair scope is missing or ambiguous."""
    if mission is not None and all_missions:
        code, message = _FIX_SCOPE_CONFLICT_CODE, _FIX_SCOPE_CONFLICT_MESSAGE
    elif fix and mission is None and not all_missions:
        code, message = _FIX_SCOPE_REQUIRED_CODE, _FIX_SCOPE_REQUIRED_MESSAGE
    else:
        return
    if json_output:
        console.emit_json(_doctor_shared._json_error(code, message))
    else:
        console.print(f"[red]{code}:[/red] {message}")
    raise typer.Exit(1)


def run_coordination_health(
    json_output: bool,
    fix: bool = False,
    check_staleness: bool = False,
    mission: str | None = None,
    all_missions: bool = False,
) -> None:
    """Entry point for ``doctor coordination`` (exit 1 iff any ``error`` finding).

    When *fix* is ``True``, automatically materializes a missing coordination
    worktree for any ``COORDINATION_WORKTREE_MISSING`` finding (branch exists,
    worktree absent — #5113 / FR-014) via :func:`_apply_missing_worktree_fix`,
    which routes through the canonical
    :func:`~specify_cli.coordination.surface_resolver.materialize_coord_surface_for_write`
    materializer (idempotent; refuses with a ``warning`` finding, never a crash,
    when the branch is remote-only). It also removes stale ``coordination_branch``
    keys from ``meta.json`` for any ``COORDINATION_WORKTREE_NEVER_CREATED``
    findings, re-runs :func:`~specify_cli.migration.backfill_topology.backfill_topology_repo`
    with ``runtime_reading=True`` (never a derived ``single_branch``), then attempts the WP06
    Gap-1 coord-vs-target fast-forward (:func:`_apply_coord_staleness_fixes`)
    for every coordinated mission. A per-mission unsafe precondition -- a
    diverged coord branch, a dirty coord worktree, a coord worktree that does
    not belong to this repository (:func:`_coord_worktree_foreign_repo_finding`),
    or one checked out on the wrong branch
    (:func:`_coord_worktree_mismatch_fix_blocked_finding`) -- surfaces as an
    ``error`` finding rather than raising (renata LOW, coord-commit-integrity
    squad) -- the command still exits 1 overall for that mission, but no
    longer aborts fixing every OTHER mission in the same run. FR-009/C-005
    hold for every one of those *blocked* preconditions: nothing is mutated
    for that mission. The one exception is the postcondition re-read
    (:func:`_coord_staleness_fix_postcondition_finding`): by the time it can
    fire, the fast-forward has already genuinely run in the coord worktree --
    only the declared ref this run reads back from ``repo_root`` failed to
    reflect it -- so that specific ``error`` reports a real (if incomplete)
    mutation, not a refusal.

    ``check_staleness`` (FR-008, ``--check-staleness``) additionally reports
    Gap-1 coord-branch-vs-``target_branch`` staleness findings; it is purely a
    reporting toggle -- the Gap-1 ``--fix`` fast-forward above always runs
    when *fix* is set, independent of this flag.

    ``mission`` (FR-012, ``--mission``) scopes every per-mission check (and the
    ``--fix`` Gap-1 fast-forward) to the single mission the shared resolver maps
    the handle to — the SAME resolver ``doctor mission-state`` uses. An
    unresolvable or ambiguous handle fails closed with exit 1 and a
    mission-state-parity error (no silent fallback).

    ``all_missions`` (#7552): ``--fix`` needs a named scope -- ``mission`` or
    ``all_missions`` -- and refuses (``COORDINATION_FIX_SCOPE_REQUIRED``, exit 1,
    nothing changed) without one; naming both refuses as
    ``COORDINATION_FIX_SCOPE_CONFLICT``. The read-only report needs no scope.
    """
    _refuse_unscoped_fix(fix, mission, all_missions, json_output)
    repo_root = _doctor_shared.resolve_project_root_or_exit(locate_project_root, json_output)

    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
    )

    try:
        findings = _collect_coordination_findings(
            repo_root, check_staleness=check_staleness, mission_filter=mission
        )

        if fix:
            fix_warnings = _apply_coordination_fixes(findings, repo_root, scoped=mission is not None)
            # FR-009 Gap-1: a per-mission unsafe precondition (diverged / dirty)
            # now returns a blocked-fix `error` finding (renata LOW) instead of
            # raising, so one mission's Gap-1 problem no longer aborts fixing
            # every OTHER mission processed in this run.
            staleness_blocked = _apply_coord_staleness_fixes(repo_root, mission_filter=mission)
            # Re-collect findings after fix so the exit code reflects the new state,
            # then fold in any warnings/blocked-fix findings the fixers raised for
            # issues they could not heal (pruned worktree / unparseable /
            # unresolvable / unsafe Gap-1 precondition) — these must not be
            # silently dropped by the re-collect.
            findings = _collect_coordination_findings(
                repo_root, check_staleness=check_staleness, mission_filter=mission
            )
            findings.extend(fix_warnings)
            findings.extend(staleness_blocked)
    except MissionNotFoundError as exc:
        _emit_mission_resolver_error("MISSION_NOT_FOUND", mission, json_output)
        raise typer.Exit(1) from exc
    except AmbiguousHandleError as exc:
        _emit_mission_resolver_error("AMBIGUOUS_HANDLE", mission, json_output)
        raise typer.Exit(1) from exc

    _emit_coordination_findings(findings, json_output)
    raise typer.Exit(1 if any(f.severity == "error" for f in findings) else 0)
