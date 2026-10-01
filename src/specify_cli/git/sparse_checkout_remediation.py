"""Sparse-checkout remediation — disable sparse state across primary + lane worktrees.

This module implements the doctor-offered remediation described in R8 of the
research document for the legacy sparse-checkout hardening mission. It consumes
a :class:`SparseCheckoutScanReport` produced by WP02's detection primitive and,
for every active target (primary repo plus every lane worktree), runs a fixed
five-step sequence that disables sparse-checkout state and refreshes the
working tree.

The five steps per path are intentionally redundant with respect to
``git sparse-checkout disable`` to insulate us from version-specific git
behaviour (see the WP09 ADR for the rationale).

1. ``git sparse-checkout disable`` — cleanest path on modern git.
2. ``git config --unset core.sparseCheckout`` — belt-and-braces in case git
   versions leave the flag set after step 1.
3. Remove the resolved sparse-checkout pattern file (``missing_ok=True``).
4. ``git checkout HEAD -- .`` — hydrate any paths the sparse filter hid.
5. ``git status`` — assert the working tree is clean.

Public API
----------
- :class:`SparseCheckoutRemediationResult` — per-path outcome.
- :class:`SparseCheckoutRemediationReport` — aggregate over primary + worktrees.
- ``STEP_*`` step name constants.
- :func:`remediate` — orchestrating entry point.

Dirty-tree refusal is **all-or-nothing**: if any target has dirty changes
before remediation starts, no target is modified and every result in the
report is marked with ``dirty_before_remediation=True, success=False``. This
is the FR-005 contract: we never partially remediate over an operator's
uncommitted work.

This module is the mechanism. The CLI surface (``spec-kitty doctor --fix
sparse-checkout``) and the consent prompt live in WP04; WP03 has no other
production callers.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.git import GitCommandError, status_entries
from specify_cli.git.sparse_checkout import (
    SparseCheckoutScanReport,
    SparseCheckoutState,
)

__all__ = [
    "STEP_SPARSE_DISABLE",
    "STEP_UNSET_CONFIG",
    "STEP_REMOVE_PATTERN_FILE",
    "STEP_REFRESH_WORKING_TREE",
    "STEP_VERIFY_CLEAN",
    "STEP_USER_DECLINED",
    "SparseCheckoutRemediationResult",
    "SparseCheckoutRemediationReport",
    "remediate",
]


# ---------------------------------------------------------------------------
# Step name constants — future code (doctor, logs, tests) looks for these
# exact strings, so do not rename without coordinating with WP04 and WP09.
# ---------------------------------------------------------------------------

STEP_SPARSE_DISABLE = "sparse_disable"
STEP_UNSET_CONFIG = "unset_config"
STEP_REMOVE_PATTERN_FILE = "remove_pattern_file"
STEP_REFRESH_WORKING_TREE = "refresh_working_tree"
STEP_VERIFY_CLEAN = "verify_clean"

# Sentinel recorded in ``error_step`` when the operator declined an interactive
# confirm. Not part of the five-step sequence; lives alongside them so the
# reviewer can trivially spot "user aborted" vs "git failed".
STEP_USER_DECLINED = "user_declined"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SparseCheckoutRemediationResult:
    """Per-path outcome of running the five-step remediation sequence.

    Attributes:
        path: The primary repo or lane worktree that was (or would be)
            remediated.
        success: True iff all five steps completed cleanly at ``path``. A
            ``False`` success with ``dirty_before_remediation=True`` means the
            all-or-nothing pre-check refused; ``False`` with a concrete
            ``error_step`` means a specific step failed.
        steps_completed: Ordered tuple of step names that completed before the
            function returned (or stopped on error).
        error_step: Name of the step that failed, or ``None`` on success.
            Takes values from the ``STEP_*`` constants plus
            :data:`STEP_USER_DECLINED`.
        error_detail: Human-readable failure detail (git stderr, porcelain
            output, declined reason, etc.). ``None`` on success.
        dirty_before_remediation: True when the pre-remediation dirty-tree
            probe refused this path (all-or-nothing rule).
    """

    path: Path
    success: bool
    steps_completed: tuple[str, ...]
    error_step: str | None
    error_detail: str | None
    dirty_before_remediation: bool


@dataclass(frozen=True)
class SparseCheckoutRemediationReport:
    """Aggregate report for a remediation run over primary + worktrees."""

    primary_result: SparseCheckoutRemediationResult
    worktree_results: tuple[SparseCheckoutRemediationResult, ...]

    @property
    def overall_success(self) -> bool:
        """True iff every remediated path completed all five steps cleanly."""
        return self.primary_result.success and all(
            w.success for w in self.worktree_results
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_DIRTY_TREE_DETAIL = "dirty working tree detected; remediation refused to avoid clobbering uncommitted work. Commit or stash and retry."


def _dirty_refusal_detail(path: Path) -> str | None:
    """Why ``path`` blocks remediation, or ``None`` when it is clean.

    A path blocks when ``git status`` reports at least one entry. This guards
    the destructive ``git checkout HEAD -- .`` step, so a probe that *fails* on
    an existing path blocks too, with its own message: a failed read can never
    prove the tree clean (fail closed), and it must not be reported as a dirty
    tree the operator would then look for in vain. Only a path that does not
    exist is clean, because there is nothing to remediate there.
    """
    if not path.exists():
        return None
    try:
        dirty = bool(status_entries(path, untracked=None))
    except GitCommandError as exc:
        return (
            f"could not read git status in {path} ({exc}); remediation refused because "
            "an unreadable working tree cannot be proven clean. Fix the repository state and retry."
        )
    return _DIRTY_TREE_DETAIL if dirty else None


def _dirty_refusal_result(path: Path, detail: str) -> SparseCheckoutRemediationResult:
    """Build the refusal result used when any target is dirty or unreadable."""
    return SparseCheckoutRemediationResult(
        path=path,
        success=False,
        steps_completed=(),
        error_step=None,
        error_detail=detail,
        dirty_before_remediation=True,
    )


def _run_git(
    args: list[str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` at ``cwd`` returning the completed process.

    Does not raise on non-zero exit; callers inspect ``returncode`` / ``stderr``
    and translate into step-level errors themselves.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_pattern_file_for_state(
    state: SparseCheckoutState | None, path: Path, is_worktree: bool
) -> Path | None:
    """Return the sparse-checkout pattern file location for ``path``.

    Prefers the path already resolved by the scan report (which used the
    canonical ``git rev-parse --git-dir`` lookup for worktrees). Falls back
    to the primary-repo default when the state did not supply one.
    """
    if state is not None and state.pattern_file_path is not None:
        return state.pattern_file_path
    if not is_worktree:
        return path / ".git" / "info" / "sparse-checkout"
    # For worktrees without a pre-resolved path, do the same rev-parse probe
    # that WP02 performs. Keeping this logic identical avoids drift.
    proc = _run_git(["rev-parse", "--git-dir"], path)
    if proc.returncode != 0:
        return None
    git_dir_raw = proc.stdout.strip()
    if not git_dir_raw:
        return None
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = (path / git_dir).resolve()
    return git_dir / "info" / "sparse-checkout"


def _run_remediation_steps(
    path: Path,
    *,
    pattern_file: Path | None,
) -> SparseCheckoutRemediationResult:
    """Execute the five-step sequence on ``path`` and return the result.

    Each step is wrapped individually: any step that fails short-circuits and
    is captured in ``error_step`` / ``error_detail``. Step-1 success does NOT
    imply later steps can be skipped — the redundancy is intentional.
    """
    completed: list[str] = []

    # Step 1: git sparse-checkout disable.
    disable = _run_git(["sparse-checkout", "disable"], path)
    if disable.returncode != 0:
        return SparseCheckoutRemediationResult(
            path=path,
            success=False,
            steps_completed=tuple(completed),
            error_step=STEP_SPARSE_DISABLE,
            error_detail=(disable.stderr or disable.stdout).strip() or None,
            dirty_before_remediation=False,
        )
    completed.append(STEP_SPARSE_DISABLE)

    # Step 2: unset core.sparseCheckout. Git exits non-zero if the key does
    # not exist, which is the desired end-state, so we tolerate that.
    unset = _run_git(["config", "--unset", "core.sparseCheckout"], path)
    if unset.returncode not in (0, 5):  # 5 == "key not set"
        return SparseCheckoutRemediationResult(
            path=path,
            success=False,
            steps_completed=tuple(completed),
            error_step=STEP_UNSET_CONFIG,
            error_detail=(unset.stderr or unset.stdout).strip() or None,
            dirty_before_remediation=False,
        )
    completed.append(STEP_UNSET_CONFIG)

    # Step 3: remove pattern file (missing_ok). Absence is the desired state.
    if pattern_file is not None:
        try:
            pattern_file.unlink(missing_ok=True)
        except OSError as exc:
            return SparseCheckoutRemediationResult(
                path=path,
                success=False,
                steps_completed=tuple(completed),
                error_step=STEP_REMOVE_PATTERN_FILE,
                error_detail=f"{type(exc).__name__}: {exc}",
                dirty_before_remediation=False,
            )
    completed.append(STEP_REMOVE_PATTERN_FILE)

    # Step 4: git checkout HEAD -- . to rehydrate anything the sparse filter
    # previously hid.
    refresh = _run_git(["checkout", "HEAD", "--", "."], path)
    if refresh.returncode != 0:
        return SparseCheckoutRemediationResult(
            path=path,
            success=False,
            steps_completed=tuple(completed),
            error_step=STEP_REFRESH_WORKING_TREE,
            error_detail=(refresh.stderr or refresh.stdout).strip() or None,
            dirty_before_remediation=False,
        )
    completed.append(STEP_REFRESH_WORKING_TREE)

    # Step 5: verify clean. NFR-003 — 100% of successful remediations leave
    # the tree clean.
    try:
        leftover = status_entries(path, untracked=None)
        failure_detail = "\n".join(entry.display() for entry in leftover)
    except GitCommandError as exc:
        # Guard: a failing probe cannot prove the tree clean, so fail closed.
        leftover = ()
        failure_detail = exc.stderr or str(exc)
    if leftover or failure_detail:
        return SparseCheckoutRemediationResult(
            path=path,
            success=False,
            steps_completed=tuple(completed),
            error_step=STEP_VERIFY_CLEAN,
            error_detail=failure_detail.strip() or None,
            dirty_before_remediation=False,
        )
    completed.append(STEP_VERIFY_CLEAN)

    return SparseCheckoutRemediationResult(
        path=path,
        success=True,
        steps_completed=tuple(completed),
        error_step=None,
        error_detail=None,
        dirty_before_remediation=False,
    )


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def remediate(
    report: SparseCheckoutScanReport,
    *,
    interactive: bool,
    confirm: Callable[[str], bool] | None = None,
) -> SparseCheckoutRemediationReport:
    """Disable sparse-checkout state across primary + lane worktrees.

    Refuses if ANY target has a dirty working tree at the moment of call
    (all-or-nothing, per FR-005). When ``interactive`` is True and ``confirm``
    is provided, prompts once per affected path; a ``False`` return aborts
    remediation for that path but lets other paths proceed. In non-interactive
    mode the caller is responsible for having secured operator consent.

    Paths iterate primary FIRST, then worktrees in the order they appear in
    the scan report (WP02 sorts worktree children, so this is deterministic).

    Args:
        report: Scan report from :func:`specify_cli.git.sparse_checkout.scan_repo`
            identifying which paths are candidates for remediation.
        interactive: When True, the ``confirm`` callback is consulted per path
            before running step 1.
        confirm: Callback ``(target_path_str) -> bool``. Returning ``False``
            marks that path's result as ``error_step="user_declined"`` and
            skips its five-step sequence.

    Returns:
        :class:`SparseCheckoutRemediationReport` — one result per target. On
        the dirty-tree refusal path, every result carries
        ``dirty_before_remediation=True``.
    """
    # Build the ordered list of (path, state) pairs to process. We include
    # primary unconditionally because the scan report always carries a primary
    # state, even when inactive. Remediation on an inactive primary is a
    # harmless no-op: the five steps succeed against a repo that already has
    # sparse-checkout disabled.
    targets: list[tuple[Path, SparseCheckoutState | None, bool]] = [
        (report.primary.path, report.primary, False)
    ]
    for wt_state in report.worktrees:
        if wt_state.is_blocking:
            targets.append((wt_state.path, wt_state, True))

    # All-or-nothing dirty-tree pre-check. We probe EVERY target before
    # touching any of them.
    refusal_detail = next(
        (detail for path, _state, _is_wt in targets if (detail := _dirty_refusal_detail(path)) is not None),
        None,
    )

    if refusal_detail is not None:
        # FR-005: refuse on EVERY path, not just the dirty one, so operators
        # see the full scope that would have been touched.
        primary_refusal = _dirty_refusal_result(targets[0][0], refusal_detail)
        worktree_refusals = tuple(
            _dirty_refusal_result(p, refusal_detail) for p, _s, _w in targets[1:]
        )
        return SparseCheckoutRemediationReport(
            primary_result=primary_refusal,
            worktree_results=worktree_refusals,
        )

    # Per-path remediation loop. Failures on one path do NOT short-circuit
    # subsequent paths — the doctor surface (WP04) wants the full picture so
    # it can present the operator with a per-path diagnosis.
    primary_path, primary_state, _ = targets[0]
    primary_result = _remediate_single_target(
        primary_path,
        state=primary_state,
        is_worktree=False,
        interactive=interactive,
        confirm=confirm,
    )

    worktree_results: list[SparseCheckoutRemediationResult] = []
    for wt_path, maybe_wt_state, _is_wt in targets[1:]:
        if maybe_wt_state is None:
            continue
        wt_result = _remediate_single_target(
            wt_path,
            state=maybe_wt_state,
            is_worktree=True,
            interactive=interactive,
            confirm=confirm,
        )
        worktree_results.append(wt_result)

    return SparseCheckoutRemediationReport(
        primary_result=primary_result,
        worktree_results=tuple(worktree_results),
    )


def _remediate_single_target(
    path: Path,
    *,
    state: SparseCheckoutState | None,
    is_worktree: bool,
    interactive: bool,
    confirm: Callable[[str], bool] | None,
) -> SparseCheckoutRemediationResult:
    """Run interactive gate + five-step sequence for one path."""
    # Interactive consent gate. A ``False`` confirm aborts this path only;
    # the outer loop continues with the remaining targets.
    if interactive and confirm is not None:
        try:
            proceed = confirm(str(path))
        except Exception as exc:  # noqa: BLE001 — defensive: user-supplied callback
            return SparseCheckoutRemediationResult(
                path=path,
                success=False,
                steps_completed=(),
                error_step=STEP_USER_DECLINED,
                error_detail=f"confirm callback raised: {type(exc).__name__}: {exc}",
                dirty_before_remediation=False,
            )
        if not proceed:
            return SparseCheckoutRemediationResult(
                path=path,
                success=False,
                steps_completed=(),
                error_step=STEP_USER_DECLINED,
                error_detail="user declined interactive confirmation",
                dirty_before_remediation=False,
            )

    pattern_file = _resolve_pattern_file_for_state(state, path, is_worktree)
    return _run_remediation_steps(path, pattern_file=pattern_file)
