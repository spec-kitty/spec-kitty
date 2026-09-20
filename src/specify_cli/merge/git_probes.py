"""Low-level git probes / primitives for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-03 / WP03.

Branch/tree/porcelain git primitives moved byte-for-byte out of the command
shim. Includes the PUBLIC :func:`path_is_under_worktrees` predicate consumed by
``doctor.py`` and ``agent/mission.py``; the shim re-exports it so those importers
need zero edits (FR-006). One-way imports (C-006/INV-2): this module never
imports the command shim.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from specify_cli.cli.console import console
from specify_cli.coordination.surface_resolver import is_under_worktrees_segment
from specify_cli.core.constants import KITTIFY_DIR
from specify_cli.core.git_ops import run_command
from specify_cli.git.destructive_guard import (
    DestructiveOpRefused,
    assert_checkout_on_target,
)
from specify_cli.merge._constants import LINEAR_HISTORY_REJECTION_TOKENS, logger


def _lane_already_integrated(
    repo_root: Path, lane_branch: str, mission_branch: str
) -> bool:
    """Return True when ``lane_branch`` carries no commits absent from ``mission_branch``.

    FR-037 (#1772 Bug 3): the lane-skip decision must gate on the ACTUAL lane
    tree state vs. the mission branch — never on a per-WP ``done`` status, which
    a prior aborted merge may have recorded before any code was integrated.
    Uses ``git rev-list <lane> ^<mission>``: an empty result means every lane
    commit is already reachable from the mission branch, so re-merging would be
    a genuine no-op. A non-empty result means real, un-integrated lane work
    remains and the lane MUST be merged.
    """
    ret, out, _err = run_command(
        ["git", "rev-list", "--count", lane_branch, f"^{mission_branch}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        # Unknown ref / git error — be conservative and do NOT treat as
        # integrated, so the lane merge runs and any real error surfaces there.
        return False
    return bool(out.strip() == "0")


def _branch_trees_equal(repo_root: Path, source_branch: str, target_branch: str) -> bool:
    """Return True when two refs currently expose identical trees.

    Squash merges do not preserve ancestry, so reachability is the wrong
    idempotency predicate for "the squash payload already landed". For that
    recovery path we need the content-level question: would merging source into
    target produce any tree changes?
    """
    ret, _out, _err = run_command(
        ["git", "diff", "--quiet", source_branch, target_branch],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return bool(ret == 0)


def path_is_under_worktrees(path: Path) -> bool:
    """Return True when ``path`` lies under the ``.worktrees/`` directory.

    FR-035 / #1772 Bug 0: nested-worktree paths (``.worktrees/<m>-coord/…``)
    must never be staged via ``git add`` from finalize/recovery/merge flows,
    and ``spec-kitty doctor`` flags such content when it is already tracked.
    This is the single reusable predicate for that decision (Randy Reducer:
    one guard, not per-call-site copies). It is path-shape based — it does not
    touch the filesystem — so it works for both real paths and committed-tree
    relative paths.

    Delegates to the blessed seam primitive
    :func:`coordination.surface_resolver.is_under_worktrees_segment` (C-SEAM-1):
    one shape-proposal predicate, not a per-module copy. The constants
    ``WORKTREES_DIR`` and the seam's ``_WORKTREES_SEGMENT`` are both
    ``".worktrees"``, so the membership check is identical.
    """
    return bool(is_under_worktrees_segment(path))


def _raw_porcelain_status(repo_root: Path) -> tuple[int, str]:
    """Return ``(returncode, raw_stdout)`` for ``git status --porcelain``.

    Reads stdout RAW (not via ``run_command``) so the leading status column of
    each porcelain line is preserved. Porcelain v1 emits ``XY<space>PATH`` (a
    fixed 3-char prefix); for a tracked file that is modified-but-not-staged X
    is a space (``" M path"``). ``run_command``'s whole-output ``.strip()`` would
    remove the leading space of the *first* line only, shifting its columns so
    ``_classify_porcelain_lines`` rejects it (``line[2] != " "``) and silently
    drops the first divergent path. The post-merge working-tree invariant MUST
    see every divergent line, so it reads porcelain via this helper instead.

    Mirrors the raw-read pattern documented in
    :func:`specify_cli.cli.commands.implement._feature_dir_status_entries`.
    """
    import subprocess as _subprocess

    result = _subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode, result.stdout


def _classify_porcelain_lines(
    lines: list[str],
    expected_paths: set[str],
    *,
    residue_predicate: Callable[[str], bool] | None = None,
) -> tuple[list[str], int]:
    """Classify ``git status --porcelain`` lines into offending vs ignored.

    Returns a 2-tuple ``(offending_lines, skipped_untracked_count)`` where:

    * ``offending_lines`` — lines that represent unexpected divergence from HEAD
      (tracked modifications, deletions, renames, …).
    * ``skipped_untracked_count`` — number of ``??`` (untracked) lines that were
      silently dropped because untracked files cannot diverge from HEAD.

    Lines whose path component is in *expected_paths* are dropped because the
    immediately-following safe_commit will persist those files and they are
    therefore expected to be dirty at this point in the flow.

    Lines whose path is recognized by *residue_predicate* are also dropped:
    these are coordination-owned planning/status artifacts whose stale primary
    copies are legitimate residue after a coordination-topology merge (FR-012 /
    #1878).  The predicate is the single residue authority
    (:func:`specify_cli.coordination.coherence.is_coord_residue_churn` — WP12
    retired the former ``mission_runtime`` predicate onto this owner leg) — no
    second residue literal is carried here.

    Lines whose path is recognized by
    :func:`specify_cli.coordination.coherence.is_self_bookkeeping_churn` are also
    dropped: these are spec-kitty's own bookkeeping files (``meta.json``,
    encoding-provenance JSONL, ``kitty-ops/<ULID>.jsonl`` Op-record orphans) that
    must not block dirty-tree gates (#2251 / FR-001 / G-5 invariant).  The
    delegation mirrors the ``residue_predicate`` pattern — no second literal here.
    (WP11 retired the former ``mission_runtime`` self-bookkeeping predicate onto
    this owner-module leg; only the self-bookkeeping check moved, not the residue
    leg — callers still supply their own topology-aware ``residue_predicate``.)

    Lines that do not match porcelain v1 shape (two status chars + space + path)
    are silently ignored to avoid false positives from mocked test output.
    """
    from specify_cli.coordination.coherence import is_self_bookkeeping_churn

    offending: list[str] = []
    skipped_untracked = 0
    for line in lines:
        if not line.strip():
            continue
        # Porcelain v1: two status chars + space + path (minimum 4 chars).
        if len(line) < 4 or line[2] != " ":
            continue
        status_code = line[:2]
        if status_code == "??":
            skipped_untracked += 1
            continue  # untracked files cannot diverge from HEAD
        path_part = line[3:].strip()
        if path_part in expected_paths:
            continue
        if residue_predicate is not None and residue_predicate(path_part):
            continue
        if is_self_bookkeeping_churn(path_part):
            continue
        offending.append(line)
    return offending, skipped_untracked


def _is_linear_history_rejection(stderr: str) -> bool:
    """Return True if git push stderr indicates a linear-history rejection.

    Case-insensitive substring match against the locked token list.
    Fail-open: returns False for unrecognised rejection messages.
    """
    haystack = stderr.lower()
    return any(token.lower() in haystack for token in LINEAR_HISTORY_REJECTION_TOKENS)


def _emit_remediation_hint(hint_console: Console) -> None:
    """Print a remediation hint for linear-history push rejections."""
    hint_console.print(
        "\n[yellow]Push rejected by linear-history protection.[/yellow]\n"
        "Try [cyan]spec-kitty merge --strategy squash[/cyan], or set "
        f"[cyan]merge.strategy: squash[/cyan] in [cyan]{KITTIFY_DIR}/config.yaml[/cyan].\n"
    )


def _refresh_primary_checkout_after_merge(
    repo_root: Path, expected_branch: str | None = None
) -> None:
    """Force the primary checkout's tracked files to match HEAD.

    The target ref is advanced from a detached merge worktree, so the primary
    checkout's index/worktree can lag behind the new HEAD. A path checkout does
    not remove rename sources in sparse-checkout repos; hard reset does.
    Merge preflight requires a clean tracked worktree before this point, so this
    must only discard stale tracked state created by the ref update.

    ``expected_branch`` (WP03/T011, #4752 defense-in-depth): when supplied,
    this refuses to run ``reset --hard`` unless ``repo_root`` is currently
    checked out on ``expected_branch``. The merge preflight
    (``_pre_mutation_safety_preflight``) already asserts this before any
    mutation runs, so on the normal path this check always passes and behavior
    is unchanged; it exists so that even a bypassed/skipped preflight cannot
    reach this ``reset --hard`` against an off-target checkout. ``None`` (the
    default — used by call sites that exercise this helper directly, e.g.
    targeted unit tests) preserves the pre-guard behavior exactly.
    """
    if expected_branch is not None:
        try:
            assert_checkout_on_target(repo_root, expected_branch)
        except DestructiveOpRefused:
            console.print(
                "[yellow]Warning:[/yellow] skipping post-merge working-tree "
                f"refresh: {repo_root} is not checked out on {expected_branch!r}."
            )
            return

    ret_reset, out_reset, err_reset = run_command(
        ["git", "reset", "--hard", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_reset != 0:
        console.print(
            f"[yellow]Warning:[/yellow] post-merge working-tree refresh failed: "
            f"{(err_reset or out_reset or '').strip()}"
        )
        return

    ret_refresh, out_refresh, err_refresh = run_command(
        ["git", "update-index", "--refresh"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_refresh != 0:
        # Non-zero is expected when files truly differ from HEAD. The invariant
        # check below is the contract; this refresh is just stat reconciliation.
        logger.debug(
            "post-merge index refresh reported divergence (this is informational): %s",
            (out_refresh or err_refresh or "").strip(),
        )


def _paths_have_status_changes(repo_root: Path, paths: list[Path]) -> bool:
    """Return True when any requested path differs from HEAD or is untracked."""
    normalized: list[str] = []
    for path in paths:
        candidate = path
        if candidate.is_absolute():
            with contextlib.suppress(ValueError):
                candidate = candidate.relative_to(repo_root)
        normalized.append(str(candidate))

    ret_status, out_status, err_status = run_command(
        ["git", "status", "--porcelain", "--", *normalized],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_status != 0:
        logger.warning(
            "Could not inspect post-merge bookkeeping paths before commit: %s",
            (err_status or "").strip(),
        )
        return True
    return bool((out_status or "").strip())


def _is_git_repo(path: Path) -> bool:
    """Return True when *path* is inside a git working tree."""
    import subprocess as _subprocess
    probe = _subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(path),
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def _has_branch_ref(repo_root: Path, ref_name: str) -> bool:
    """Return True when a local branch/ref resolves to a commit."""
    retcode, _stdout, _stderr = run_command(
        ["git", "rev-parse", "--verify", f"{ref_name}^{{commit}}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return bool(retcode == 0)


__all__ = [
    "_lane_already_integrated",
    "_branch_trees_equal",
    "path_is_under_worktrees",
    "_raw_porcelain_status",
    "_classify_porcelain_lines",
    "_is_linear_history_rejection",
    "_emit_remediation_hint",
    "_refresh_primary_checkout_after_merge",
    "_paths_have_status_changes",
    "_is_git_repo",
    "_has_branch_ref",
]
