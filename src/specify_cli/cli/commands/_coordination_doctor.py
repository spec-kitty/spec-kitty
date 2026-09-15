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
import sys
from dataclasses import dataclass, field
from pathlib import Path

import typer

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import locate_project_root
from specify_cli.core.utils import safe_is_dir
from specify_cli.mission_metadata import load_meta

from ._doctor_shared import _emit_not_in_project, console

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

#: Stable error code for a coord strand that survives a rollback (#2786 / #2367-B,
#: FR-007). Emitted only when the committed coordination ref *still* reduces a
#: this-merge ``done`` WP to ``DONE`` — a marker whose ref re-derives coherent is
#: stale and yields NO finding (US2-S5 negative AC). Downstream tooling keys off
#: this constant, so it must stay stable.
_STRANDED_COORD_REVERT_CODE = "COORDINATION_STRANDED_COORD_REVERT"

#: Recovery hint for a live strand — points at the ``--fix`` repair path.
_STRANDED_COORD_REVERT_HINT = (
    "Run `spec-kitty doctor coordination --fix` to revert the stranded coordination "
    "`done` commit(s) and clear the reconcile marker."
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
    from specify_cli.cli.commands.merge import path_is_under_worktrees
    from specify_cli.core.constants import WORKTREES_DIR

    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "ls-files", "--", WORKTREES_DIR],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        # Not a git repo / git error — nothing to report here.
        return []

    tracked = [
        line
        for line in out.splitlines()
        if line.strip() and path_is_under_worktrees(Path(line.strip()))
    ]
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


def _coord_worktree_head_finding(
    worktree: Path, coord_branch: str
) -> DoctorFinding | None:
    """Return a finding if the coord worktree HEAD is off the coord branch."""

    try:
        actual_head = subprocess.check_output(
            ["git", "-C", str(worktree), "symbolic-ref", "HEAD"], text=True,
        ).strip()
    except subprocess.CalledProcessError:
        actual_head = "<detached>"
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
            f"Inspect the worktree manually; then run `{_WORKSPACE_RECOVERY_CMD}` "
            "to restore."
        ),
        error_code="COORDINATION_WORKTREE_BRANCH_MISMATCH",
    )


def _coord_worktree_dirty_finding(worktree: Path) -> DoctorFinding | None:
    """Return a finding if the coord worktree has uncommitted changes."""

    try:
        dirty = subprocess.check_output(
            ["git", "-C", str(worktree), "status", "--porcelain"], text=True,
        ).strip()
    except subprocess.CalledProcessError:
        dirty = ""
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
        from specify_cli.coordination.surface_resolver import _coord_branch_exists

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
        # Provide a real `git worktree add` command — NOT `doctor workspaces --fix`
        # which only removes husks and cannot CREATE a worktree (#2240).
        _recovery_args = [
            "git", "-C", str(repo_root), "worktree", "add",
            str(worktree), coord_branch,
        ]
        return [DoctorFinding(
            severity="warning",
            message=(
                f"Coordination worktree {worktree} is missing for mission "
                f"{mission_slug!r} (the branch {coord_branch!r} exists)."
            ),
            next_step=(
                f"Run: `git -C {repo_root} worktree add {worktree} {coord_branch}`"
            ),
            error_code="COORDINATION_WORKTREE_MISSING",
            extra={"recovery_args": _recovery_args},
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
    "Inspect and reconcile manually; `spec-kitty doctor coordination --fix` "
    "will refuse to mutate a diverged coordination branch."
)


def _coord_branch_stale_vs_target_finding(
    repo_root: Path, coord_branch: str, target_branch: str,
) -> DoctorFinding | None:
    """FR-008 (Gap-1): compare the coord branch TIP against ``target_branch``.

    * Strict ancestor (coord tip behind target, cleanly fast-forwardable) ->
      a non-blocking ``warning``, coded so ``--fix`` knows it may act
      (FR-009).
    * SHAs differ but are NOT a strict-ancestor pair -> diverged -> a
      distinct non-blocking ``warning`` that ``--fix`` refuses to touch
      (C-005 warn-first).
    * SHAs equal, or either ref is unreadable -> ``None`` (nothing to report).
    """
    coord_sha = _rev_parse(repo_root, f"refs/heads/{coord_branch}")
    target_sha = _rev_parse(repo_root, f"refs/heads/{target_branch}")
    if not coord_sha or not target_sha or coord_sha == target_sha:
        return None
    stale = _fast_forward_finding(
        subject_sha=coord_sha, tip_sha=target_sha, repo_root=repo_root,
        message=(
            f"Coordination branch {coord_branch!r} is behind target branch "
            f"{target_branch!r} (fast-forward available)."
        ),
        next_step="Run `spec-kitty doctor coordination --fix` to fast-forward it.",
        error_code=_COORD_STALE_VS_TARGET_CODE,
    )
    if stale is not None:
        return stale
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
    finding = _coord_branch_stale_vs_target_finding(repo_root, coord_branch, target_branch)
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
        # Only inspect lane worktrees for THIS mission (slug prefix + "-lane-").
        if not lane_dir.name.startswith(f"{mission_slug}-lane-"):
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
    silently dropped).
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not safe_is_dir(specs_dir):
        return []
    if mission_filter is not None:
        from specify_cli.context.mission_resolver import resolve_mission

        return [resolve_mission(mission_filter, repo_root).feature_dir]
    return [
        mission_dir
        for mission_dir in sorted(specs_dir.iterdir())
        if safe_is_dir(mission_dir)
    ]


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

    ``mission_filter`` (FR-012, ``--mission``) scopes the per-mission
    kitty-specs iteration to a single mission via the shared resolver; the
    repo-level checks (git version, tracked-worktrees hygiene, stranded-revert
    re-verification) always run. Unresolvable / ambiguous handles raise (see
    :func:`_resolve_mission_dirs`).
    """
    findings: list[DoctorFinding] = []
    findings.extend(_check_git_version())
    # FR-035 (#1772 Bug 0): repo-level tracked-.worktrees/ hygiene check.
    findings.extend(_check_tracked_worktrees_content(repo_root))
    # FR-007 (#2786 / #2367-B): repo-level stranded-coord-revert re-verification.
    findings.extend(_check_stranded_coord_revert(repo_root))

    for mission_dir in _resolve_mission_dirs(repo_root, mission_filter):
        meta = load_meta(mission_dir, on_malformed="none")
        if meta is None:
            continue
        coord_findings = _check_coordination_worktree_health(repo_root, meta)
        for f in coord_findings:
            if f.error_code == "COORDINATION_WORKTREE_NEVER_CREATED":
                f.extra["meta_path"] = str(mission_dir / "meta.json")
        findings.extend(coord_findings)
        findings.extend(_check_lane_sparse_checkout_drift(repo_root, meta))
        if check_staleness:
            findings.extend(_check_coord_branch_staleness(repo_root, meta))
    return findings


def _fix_never_created_branches(findings: list[DoctorFinding]) -> list[str]:
    """Remove stale ``coordination_branch`` keys from meta.json.

    Targets only ``COORDINATION_WORKTREE_NEVER_CREATED`` findings that carry
    a ``meta_path`` in their ``extra`` dict (populated by
    :func:`_collect_coordination_findings`). After removal, call
    :func:`~specify_cli.migration.backfill_topology.backfill_topology_repo` so
    topology is re-derived from the now-absent key.

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
        if "coordination_branch" not in meta:
            continue
        # Canonical three-mutation flatten (#3219 / FR-015 / D-PLAN-17), converged
        # onto the ONE shared primitive: clears `coordination_branch`, pops the
        # stale `topology` so `backfill_topology_repo` re-derives it (backfill
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
    return {
        "mission_id": getattr(state, "mission_id", None),
        "mission_slug": getattr(state, "mission_slug", None),
        "coord_ref": coord_ref,
        "captured_sha": captured_sha,
        "coord_worktree": coord_worktree,
        "candidate_wps": candidate_wps,
        "stranded_wp_ids": remaining,
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
        next_step=_STRANDED_COORD_REVERT_HINT,
        error_code=_STRANDED_COORD_REVERT_CODE,
        extra=extra,
    )


def _check_stranded_coord_revert(repo_root: Path) -> list[DoctorFinding]:
    """FR-007: re-verify each reconcile marker against the **committed** coord ref.

    Enumerate ``pending_coord_reconcile`` markers via WP02's
    :func:`~specify_cli.merge.state.iter_pending_coord_reconcile_markers` — NOT
    ``load_state(mission_id=None)`` (it *raises* ``MergeAmbiguousStateError`` on
    >=2 markers) and NOT a re-implemented runtime-path scan (a second path
    authority / DIR-044 breach). Each marker is re-verified by
    :func:`_finding_for_reconcile_marker`, which re-derives the strand **from the
    committed ref** (never from marker-presence) and returns exactly one finding —
    ``error`` for a healable live strand, ``warning`` for a pruned-worktree STUCK
    strand or an un-parseable/unresolvable marker, and ``None`` only for a
    genuinely-stale marker (US2-S5, the load-bearing negative AC).
    """
    from specify_cli.merge.state import iter_pending_coord_reconcile_markers

    findings: list[DoctorFinding] = []
    for state in iter_pending_coord_reconcile_markers(repo_root):
        finding = _finding_for_reconcile_marker(state, repo_root)
        if finding is not None:
            findings.append(finding)
    return findings


def _clear_pending_marker(repo_root: Path, mission_id: str) -> None:
    """Atomically clear a mission's ``pending_coord_reconcile`` marker after a heal."""
    from specify_cli.merge.state import load_state, save_state

    state = load_state(repo_root, mission_id=mission_id)
    if state is None:
        return
    state.pending_coord_reconcile = None
    save_state(state, repo_root)


def _heal_one_strand(
    f: DoctorFinding, repo_root: Path
) -> tuple[str | None, DoctorFinding | None]:
    """Attempt to heal one live-strand finding.

    Returns ``(healed_slug, warning)``: at most one is non-``None``. A genuine heal
    yields ``(slug, None)`` (and clears the marker); an un-parseable marker, an
    unresolvable mission, or a repair that reports a pruned worktree yields
    ``(None, warning)`` — a safety-net fixer must never silently drop a marker.
    ``head_advanced`` / revert-error outcomes yield ``(None, None)``: the strand is
    intentionally left for the next pass and the check's persistent ``error``
    finding still surfaces it.
    """
    from mission_runtime import MissionArtifactKind

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
    )
    if outcome.healed:
        _clear_pending_marker(repo_root, mission_id)
        return mission_slug, None
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
    """Flatten missions with a stale ``coordination_branch`` key, then re-backfill topology."""
    fixable = [f for f in findings if f.error_code == "COORDINATION_WORKTREE_NEVER_CREATED"]
    if not fixable:
        return
    fixed_slugs = _fix_never_created_branches(fixable)
    for slug in fixed_slugs:
        console.print(
            f"[green]Flattened:[/green] removed coordination_branch from {slug}/meta.json"
        )
    if fixed_slugs:
        from specify_cli.migration.backfill_topology import backfill_topology_repo
        backfill_topology_repo(repo_root)
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


def _apply_coordination_fixes(
    findings: list[DoctorFinding], repo_root: Path
) -> list[DoctorFinding]:
    """Run every registered ``--fix`` handler over the collected findings.

    Extracted so adding a fixer keeps the caller (:func:`run_coordination_health`)
    and this dispatch each well under the CC-15 ceiling. Each handler is
    error-code-scoped and idempotent, so the order is irrelevant. Returns any
    ``warning`` findings the fixers raised (e.g. a strand whose coord worktree is
    pruned) so the entrypoint surfaces them in the post-fix output.

    The WP06 Gap-1 fast-forward (:func:`_apply_coord_staleness_fixes`) is
    deliberately NOT dispatched from here: unlike every other fixer above, an
    unsafe per-mission precondition surfaces as its own ``error`` finding
    rather than folding into this function's return, so it runs as its own
    step in :func:`run_coordination_health` — AFTER these idempotent,
    order-irrelevant fixers have already applied.
    """
    _apply_never_created_fix(findings, repo_root)
    return _apply_stranded_revert_fix(findings, repo_root)


# ---------------------------------------------------------------------------
# WP06 (FR-009, Gap-1, C-003 MINIMIZED): the ONE `--fix` behaviour for coord-
# branch-vs-target staleness -- a fast-forward, and ONLY when unambiguously
# safe. Never grows into a general "repair arbitrary drifted content" command.
# ---------------------------------------------------------------------------


def _unified_diff(repo_root: Path, ref_a: str, ref_b: str) -> str:
    """Return ``git diff ref_a ref_b`` output, or ``""`` when git is unreadable."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "diff", ref_a, ref_b],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return ""
    return result.stdout


#: Blocked Gap-1 fix (diverged coord branch, or a dirty coord worktree): a
#: surfaced ``error`` finding rather than an abort (renata LOW, see
#: :func:`_coord_staleness_fix_blocked_finding`).
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
    ``coord_branch..target_branch``.
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
            "mutate a diverged or dirty coordination branch."
        ),
        error_code=_COORD_STALE_FIX_BLOCKED_CODE,
    )


def _fix_one_mission_coord_staleness(
    repo_root: Path, mission_meta: dict[str, object],
) -> DoctorFinding | None:
    """Attempt the Gap-1 fast-forward for a single mission.

    Skips silently (nothing to fix, returns ``None``) when the mission is not
    coordinated, its identity/``target_branch`` is incomplete, either ref is
    unreadable, the SHAs already match, or the coord worktree does not exist
    (the existing ``COORDINATION_WORKTREE_MISSING``/``NEVER_CREATED`` findings
    already cover that case). Otherwise: strict-ancestor + clean coord
    worktree fast-forwards the coord worktree onto ``target_branch`` (``git
    merge --ff-only``, itself belt-and-braces safe) and returns ``None``;
    anything else returns a blocked-fix ``error`` finding via
    :func:`_coord_staleness_fix_blocked_finding` instead of raising, mutating
    nothing (renata LOW: a single mission's unsafe precondition must not
    abort ``--fix`` for every OTHER mission in the same run).
    """
    shas = _coord_vs_target_shas(repo_root, mission_meta)
    if shas is None:
        return None
    coord_branch, target_branch, coord_sha, target_sha = shas
    if coord_sha == target_sha:
        return None  # nothing to fix: already in sync

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

    if _coord_worktree_dirty_finding(worktree) is not None:
        return _coord_staleness_fix_blocked_finding(
            repo_root, coord_branch, target_branch, reason="not cleanly fast-forwardable vs",
        )

    subprocess.run(
        ["git", "-C", str(worktree), "merge", "--ff-only", target_branch],
        check=True, capture_output=True, text=True,
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
    for mission_dir in _resolve_mission_dirs(repo_root, mission_filter):
        meta = load_meta(mission_dir, on_malformed="none")
        if meta is None:
            continue
        finding = _fix_one_mission_coord_staleness(repo_root, meta)
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
    """Emit a mission-resolver failure with ``doctor mission-state`` parity.

    JSON surface: a ``{"error": <code>, "handle": <handle>}`` envelope to stdout
    (mirrors ``_mission_state_doctor._emit_json_error``). Human surface: a red
    one-liner. The caller raises ``typer.Exit(1)``.
    """
    if json_output:
        json.dump({"error": error_code, "handle": handle}, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        label = "Mission not found" if error_code == "MISSION_NOT_FOUND" else "Ambiguous handle"
        console.print(f"[red]Error:[/red] {label}: {handle!r}")


def run_coordination_health(
    json_output: bool,
    fix: bool = False,
    check_staleness: bool = False,
    mission: str | None = None,
) -> None:
    """Entry point for ``doctor coordination`` (exit 1 iff any ``error`` finding).

    When *fix* is ``True``, automatically removes stale ``coordination_branch``
    keys from ``meta.json`` for any ``COORDINATION_WORKTREE_NEVER_CREATED``
    findings, re-runs :func:`~specify_cli.migration.backfill_topology.backfill_topology_repo`
    to re-derive topology from the now-absent key, then attempts the WP06
    Gap-1 coord-vs-target fast-forward (:func:`_apply_coord_staleness_fixes`)
    for every coordinated mission. A per-mission unsafe precondition (diverged
    coord branch, or a dirty coord worktree) surfaces as an ``error`` finding
    rather than raising (renata LOW, coord-commit-integrity squad) -- the
    command still exits 1 overall for that mission, but no longer aborts
    fixing every OTHER mission in the same run. FR-009/C-005 hold either way:
    nothing is ever mutated for the blocked mission.

    ``check_staleness`` (FR-008, ``--check-staleness``) additionally reports
    Gap-1 coord-branch-vs-``target_branch`` staleness findings; it is purely a
    reporting toggle -- the Gap-1 ``--fix`` fast-forward above always runs
    when *fix* is set, independent of this flag.

    ``mission`` (FR-012, ``--mission``) scopes every per-mission check (and the
    ``--fix`` Gap-1 fast-forward) to the single mission the shared resolver maps
    the handle to — the SAME resolver ``doctor mission-state`` uses. An
    unresolvable or ambiguous handle fails closed with exit 1 and a
    mission-state-parity error (no silent fallback).
    """
    try:
        repo_root = locate_project_root()
    except Exception as exc:
        _emit_not_in_project(json_output)
        raise typer.Exit(1) from exc
    if repo_root is None:
        _emit_not_in_project(json_output)
        raise typer.Exit(1)

    from specify_cli.context.mission_resolver import (
        AmbiguousHandleError,
        MissionNotFoundError,
    )

    try:
        findings = _collect_coordination_findings(
            repo_root, check_staleness=check_staleness, mission_filter=mission
        )

        if fix:
            fix_warnings = _apply_coordination_fixes(findings, repo_root)
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
