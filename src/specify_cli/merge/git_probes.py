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
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

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


def _lane_already_integrated(repo_root: Path, lane_branch: str, mission_branch: str) -> bool:
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


def _refresh_primary_checkout_after_merge(repo_root: Path, expected_branch: str | None = None) -> None:
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
            console.print(f"[yellow]Warning:[/yellow] skipping post-merge working-tree refresh: {repo_root} is not checked out on {expected_branch!r}.")
            return

    ret_reset, out_reset, err_reset = run_command(
        ["git", "reset", "--hard", "HEAD"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret_reset != 0:
        console.print(f"[yellow]Warning:[/yellow] post-merge working-tree refresh failed: {(err_reset or out_reset or '').strip()}")
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


# ---------------------------------------------------------------------------
# Reconciliation-gate probes (S-D / #5001) — reachability + patch-id equivalence.
#
# These are the ONLY git authority the Terminus Reconciliation Gate
# (:mod:`specify_cli.merge.reconciliation`) consults: the tree at the target ref
# cannot be faked by the bookkeeping that is itself wrong (D3). Every probe here
# is bounded — a single ``merge-base --is-ancestor`` per commit, or a
# ``rev-list``/``patch-id`` over the small ``base..tip`` post-merge window — so
# the verifier is O(#approved-WP-commits), never O(repo history) (NFR-003).
# ---------------------------------------------------------------------------


class GitProbeError(RuntimeError):
    """A window probe could NOT be evaluated because the underlying git command errored.

    #5001 pre-merge FOLD-3: the window probes (:func:`commits_in_range`,
    :func:`patch_ids_in_range`) must distinguish a *genuinely empty* range from a
    *git error* (an unresolvable ref, a corrupt object store, a transient
    failure). Collapsing an error to ``[]`` reads to the verifier as "no
    excluded/unattributable content" and passes vacuously (fail-OPEN). Raising
    this instead lets the caller REFUSE (fail-closed), matching the
    :func:`sha_reachable_from` discipline where an error counts against the tree,
    never for it.
    """


def sha_reachable_from(repo_root: Path, sha: str, ref: str) -> bool:
    """Return True iff *sha* is an ancestor of (reachable from) *ref*.

    Uses ``git merge-base --is-ancestor`` (exit 0 ⇒ reachable, exit 1 ⇒ not).
    An empty *sha*, a git error, or an unknown ref is treated as NOT reachable
    (fail-closed for the approved-reachability check: a commit we cannot prove
    reachable is treated as missing, never as present).
    """
    if not sha:
        return False
    ret, _out, _err = run_command(
        ["git", "merge-base", "--is-ancestor", sha, ref],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return bool(ret == 0)


def commits_in_range(repo_root: Path, base: str, tip: str) -> list[str]:
    """Return the SHAs reachable from *tip* but not *base* (``git rev-list base..tip``).

    The bounded window the reconciliation claim + excluded-check operate over.
    A successful ``rev-list`` with no output is a *genuinely empty* range and
    returns ``[]``. A git ERROR (an unresolvable ref, corrupt store, …) is NOT an
    empty range — it means the window could not be evaluated — so it raises
    :class:`GitProbeError` (fail-closed; #5001 FOLD-3). Callers that build the
    claim translate that into a REFUSE-shaped claim; the verifier translates it
    into a REFUSE result — never a vacuous PASS.
    """
    ret, out, err = run_command(
        ["git", "rev-list", f"{base}..{tip}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        raise GitProbeError(f"git rev-list {base}..{tip} failed (exit {ret}): {(err or '').strip()}")
    return [line for line in out.splitlines() if line.strip()]


def patch_id_of(repo_root: Path, sha: str) -> str:
    """Return the stable patch-id of *sha* — the identity of the CHANGE, not the commit.

    Patch-id equivalence lets the excluded-commit check catch cherry-picked,
    rebased, or re-lettered copies of canceled code: the same diff under a new
    SHA maps to the same patch-id (#4945 / #4977 / contract postcondition 1).
    Returns ``""`` when the commit has a genuinely empty diff (e.g. a merge
    commit) — a successful ``git show`` with nothing for ``git patch-id`` to
    hash — so an empty patch-id is never matched and a merge commit can never
    be mistaken for excluded content.

    Raises :class:`GitProbeError` when ``git show`` itself ERRORS (non-zero
    exit — an unresolvable sha, a corrupt object store, …). #5001 FOLD-3-lite:
    a git error is NOT a legitimate empty patch-id — collapsing it to ``""``
    reads to callers (``patch_ids_in_range``, the closed-world content scan,
    the excluded/authored claim collectors) as "no content" and lets an
    un-attributable content commit whose probe transiently errored ship
    undetected (fail-OPEN). Raising here lets those callers REFUSE/propagate
    instead, matching the :func:`commits_in_range` discipline.

    ``git show <sha> | git patch-id --stable`` needs stdin piping, which
    :func:`run_command` does not expose, so this uses ``subprocess`` directly
    (mirrors :func:`_raw_porcelain_status`).
    """
    import subprocess as _subprocess

    if not sha:
        return ""
    show = _subprocess.run(
        ["git", "show", sha],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if show.returncode != 0:
        raise GitProbeError(
            f"git show {sha} failed (exit {show.returncode}): {(show.stderr or '').strip()}"
        )
    pid = _subprocess.run(
        ["git", "patch-id", "--stable"],
        input=show.stdout,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    fields = pid.stdout.split()
    return fields[0] if fields else ""


def patch_ids_in_range(repo_root: Path, base: str, tip: str) -> set[str]:
    """Patch-ids of every non-empty-diff commit in ``base..tip`` (bounded window).

    O(#commits in the window), never O(repo history) (NFR-003). Merge commits
    (empty patch-id) are dropped so they never masquerade as excluded content.
    Propagates :class:`GitProbeError` from :func:`commits_in_range` when the
    window cannot be evaluated (fail-closed; #5001 FOLD-3) — never a silent empty
    set on a git error.
    """
    ids: set[str] = set()
    for sha in commits_in_range(repo_root, base, tip):
        pid = patch_id_of(repo_root, sha)
        if pid:
            ids.add(pid)
    return ids


def first_parent_commits_in_range(repo_root: Path, base: str, tip: str) -> list[str]:
    """Return the FIRST-PARENT SHAs reachable from *tip* but not *base* (newest-first).

    ``git rev-list --first-parent base..tip`` — the lane's OWN authorship spine.
    A commit that a lane *merged in* from another branch (a second parent of a
    merge commit) is NOT on the first-parent spine, so it is excluded. This is the
    structural signal the closed-world excluded check (S-D / #4945/#4977/#4981)
    relies on to distinguish a lane's genuinely-authored work from a removed WP's
    commit smuggled into a carrier lane's history via a merge: the smuggled commit
    rides a second-parent branch and is never counted as approved authorship.

    A successful ``rev-list`` with no output is a *genuinely empty* range and
    returns ``[]``. A git ERROR (an unresolvable ref, corrupt store, …) is NOT an
    empty range — it means the spine could not be evaluated — so it raises
    :class:`GitProbeError` (fail-closed; #5013 F7). This mirrors
    :func:`commits_in_range`: collapsing an error to ``[]`` reads as "no authored
    content" and lets an unattributable blob PASS vacuously (fail-OPEN). Callers
    that build the claim tolerate the raise (an unresolvable lane yields no
    authorship, never a spurious refusal); the verifier's window scan translates it
    into a REFUSE.
    """
    ret, out, err = run_command(
        ["git", "rev-list", "--first-parent", f"{base}..{tip}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        raise GitProbeError(f"git rev-list --first-parent {base}..{tip} failed (exit {ret}): {(err or '').strip()}")
    return [line for line in out.splitlines() if line.strip()]


def blob_id_at(repo_root: Path, ref: str, path: str) -> str:
    """Return the blob object id of *path* in the tree at *ref* (``git rev-parse ref:path``).

    The CONTENT identity of a file — squash-sound, since a squash merge preserves
    tree/blob content while destroying lane-tip SHAs and per-commit patch-ids
    (#5013). Raises :class:`GitProbeError` on any git error, INCLUDING an absent
    path: the squash content axis only ever calls this for an Added/Modified path
    (a Deleted path is skipped before the call), so an "unexpected empty" blob for
    an A/M path is a genuine probe failure that must REFUSE, never be inferred as a
    deletion (#5013 F1). The caller therefore distinguishes "A/M path but the probe
    errored" (→ REFUSE) from "D path" (skipped) purely by which paths it feeds here.
    """
    ret, out, err = run_command(
        ["git", "rev-parse", f"{ref}:{path}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        raise GitProbeError(f"git rev-parse {ref}:{path} failed (exit {ret}): {(err or '').strip()}")
    blob: str = (out or "").strip()
    if not blob:
        raise GitProbeError(f"git rev-parse {ref}:{path} returned no blob id")
    return blob


def changed_paths_in_range(repo_root: Path, base: str, tip: str) -> list[tuple[str, str]]:
    """Return ``(status, path)`` pairs for the aggregate diff ``base..tip``.

    ``git diff --name-status --no-renames base..tip`` — the paths whose content
    differs between the two trees, each tagged with its status letter (``A`` added,
    ``M`` modified, ``D`` deleted, ``T`` type-changed, …). Net-unchanged paths never
    appear, so the caller needs no separate base-blob comparison. ``--no-renames``
    matches :func:`changed_paths_of`'s own flag (#5013 F6): a rename surfaces as a
    delete + an add, so the added side is attributed by content like any other new
    blob rather than hidden behind an ``R`` status. Raises :class:`GitProbeError` on
    any git error (fail-closed; mirrors :func:`commits_in_range`), so the squash
    content axis REFUSEs on an unevaluable window rather than passing vacuously.
    """
    ret, out, err = run_command(
        ["git", "diff", "--name-status", "--no-renames", f"{base}..{tip}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        raise GitProbeError(f"git diff --name-status {base}..{tip} failed (exit {ret}): {(err or '').strip()}")
    changes: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts[0].strip(), parts[1].strip()
        if status and path:
            changes.append((status, path))
    return changes


def changed_paths_of(repo_root: Path, sha: str) -> list[str]:
    """Return the repo-relative paths a single (non-merge) commit changed.

    ``git show --name-only --format= --no-renames <sha>`` — the files whose
    content the commit authored. Used by the closed-world content check to decide
    whether a window commit is real content (touches a path outside the mission's
    bookkeeping surface) or pure spec-kitty housekeeping (status/meta/matrix/
    retrospective projections). Returns ``[]`` for a commit that genuinely
    changed no files (a successful, empty ``git show``).

    Raises :class:`GitProbeError` when ``git show`` itself ERRORS (non-zero
    exit). #5001 FOLD-3-lite: a git error is NOT the same as "this commit
    touched nothing" — collapsing it to ``[]`` lets the closed-world scan
    (:meth:`MergeOutcomeVerifier._commit_is_content`) read an errored probe as
    pure housekeeping and SKIP an un-attributable content commit undetected
    (fail-OPEN). Raising here routes the caller into the existing
    ``GitProbeError`` REFUSE path instead.
    """
    import subprocess as _subprocess

    if not sha:
        return []
    result = _subprocess.run(
        ["git", "show", "--name-only", "--format=", "--no-renames", sha],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise GitProbeError(
            f"git show --name-only {sha} failed (exit {result.returncode}): "
            f"{(result.stderr or '').strip()}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Merge-resolution-aware Seam A attribution probes (terminus-merge-resolution-
# attribution / #5051-adjacent). ``git merge-tree --write-tree`` (git>=2.38)
# derives the common ancestor of the two lane commits itself (never a caller-
# supplied guess) and honors ``.gitattributes``, faithfully modeling the
# resolution a real squash of those two lanes would have produced (Seam A
# Decision 1, ``research.md``).
# ---------------------------------------------------------------------------

_GIT_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
_MERGE_TREE_WRITE_TREE_MIN_VERSION: tuple[int, int] = (2, 38)


def merge_tree_write_tree_available(repo_root: Path) -> bool:
    """Return True iff the installed git supports ``git merge-tree --write-tree`` (git>=2.38).

    Probed via ``git --version`` rather than by invoking the flag itself, so a
    caller can gate the (more expensive, per-path) :func:`three_way_merge_blob`
    call without paying for a doomed invocation on old git. A failing
    ``git --version``, or output that does not contain a recognizable
    ``X.Y[.Z]`` version, is treated as unavailable — fail-closed: the caller
    then leaves the path unattributable rather than attempting an unsupported
    flag (Decision 3, ``research.md`` — old-git users keep today's false-FAIL
    until they upgrade; no unsound raw-``merge-file`` fallback).
    """
    ret, out, _err = run_command(["git", "--version"], capture=True, check_return=False, cwd=repo_root)
    if ret != 0:
        return False
    match = _GIT_VERSION_PATTERN.search(out or "")
    if not match:
        return False
    version = (int(match.group(1)), int(match.group(2)))
    return version >= _MERGE_TREE_WRITE_TREE_MIN_VERSION


def three_way_merge_blob(repo_root: Path, lane_a_commit: str, lane_b_commit: str, path: str) -> str | None:
    """Simulate the 2-way merge of two lane commits; return *path*'s resulting blob id.

    Uses ``git merge-tree --write-tree <lane_a_commit> <lane_b_commit>``
    (git>=2.38 — gate with :func:`merge_tree_write_tree_available` first): git
    derives the common ancestor itself and honors ``.gitattributes``. The ONLY
    inputs are the two lane commits (and the ancestor git derives from them) —
    no third input (e.g. a canceled/removed hunk) can ever be smuggled into the
    simulation, so a target blob equal to this result is, by construction,
    legitimate approved-lane content.

    * Exit code 0 — a clean merge. The new tree's oid is printed on stdout's
      first line; this reads *path*'s blob id from that tree
      (:func:`blob_id_at`). A path absent from the clean-merged tree (e.g. both
      sides deleted it) is treated as unattributable — returns ``None``.
    * Exit code 1 — a genuine merge conflict (including a binary-file
      conflict). The tree is still written (with higher-stage conflict info),
      but the resolution is NOT a deterministic function of the two parents —
      :func:`is_legitimate_three_way_resolution`'s caller must fail closed, so
      this returns ``None`` without inspecting the conflicted tree.
    * Any OTHER exit code is an unexpected git failure (an unresolvable commit
      ref, a corrupt object store, …) and raises :class:`GitProbeError` so the
      caller REFUSEs rather than silently treating it as either a clean merge
      or a conflict.
    """
    ret, out, err = run_command(
        ["git", "merge-tree", "--write-tree", lane_a_commit, lane_b_commit],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret not in (0, 1):
        raise GitProbeError(f"git merge-tree --write-tree {lane_a_commit} {lane_b_commit} failed (exit {ret}): {(err or '').strip()}")
    if ret == 1:
        return None  # genuine conflict — not a deterministic resolution
    lines = (out or "").splitlines()
    tree_oid = lines[0].strip() if lines else ""
    if not tree_oid:
        raise GitProbeError(f"git merge-tree --write-tree {lane_a_commit} {lane_b_commit} reported a clean merge but printed no tree id")
    try:
        return blob_id_at(repo_root, tree_oid, path)
    except GitProbeError:
        return None  # path absent (or otherwise unreadable) in the clean-merged tree


def lane_integrated_by_tree_or_ancestry(repo_root: Path, lane_branch: str, mission_branch: str) -> bool:
    """Return True when ``lane_branch``'s payload has already landed on ``mission_branch``.

    Upgrades the ancestry-only :func:`_lane_already_integrated` with the
    content/identity axis the reconciliation gate needs (DEBRIEF #4982/#4997): a
    squash merge does not preserve ancestry, so ``rev-list`` alone reports a
    squashed-but-already-landed lane as un-integrated. This probe answers the
    integration question on EITHER axis:

    * ancestry — the lane carries no commits absent from the mission branch
      (:func:`_lane_already_integrated`), OR
    * tree equality — merging the lane into the mission branch would produce no
      tree change (:func:`_branch_trees_equal`), i.e. the squash payload is
      already present byte-for-byte.

    Either being true means re-integrating the lane is a genuine no-op; both
    being false means real, un-integrated lane work remains.
    """
    if _lane_already_integrated(repo_root, lane_branch, mission_branch):
        return True
    return _branch_trees_equal(repo_root, lane_branch, mission_branch)


_DRIVER_COMMAND_PATTERN = re.compile(r"^spec-kitty (merge-driver-[a-z0-9-]+) %O %A %B$")


def _read_git_blob_bytes(repo_root: Path, ref: str, repo_rel_path: str) -> bytes | None:
    """Return the exact bytes of ``ref:repo_rel_path``, or ``None`` when absent.

    Byte-exact (``subprocess`` directly, not :func:`~specify_cli.core.git_ops.run_command`,
    which decodes to text) -- mirrors ``bookkeeping_projection._git_show_blob_bytes``'s same
    raw-read pattern; a JSONL/YAML/Markdown bookkeeping blob must be compared byte-for-byte,
    never re-encoded through a text decode/encode round trip.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{repo_rel_path}"],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _resolve_merge_driver_config_key(repo_root: Path, ref: str, repo_rel_path: str) -> str | None:
    """Resolve the ``merge=<config_key>`` ``.gitattributes`` mapping for *repo_rel_path* at *ref*.

    ``git check-attr --source=<ref>`` reads the tree's own committed ``.gitattributes``
    files AND the repo-global ``$GIT_COMMON_DIR/info/attributes`` (the ephemeral seeding
    ``lanes.merge._ensure_info_attributes`` writes for a repo with no committed mapping),
    so the caller MUST activate the driver registry first -- see
    :func:`driver_replay_expected_bytes`, which wraps this call in
    ``lanes.merge._ephemeral_merge_driver_activation`` because, by the time the squash
    projection proof runs, ``_merge_branch_into``'s own ephemeral activation has already
    been torn down. Returns ``None`` for the three non-value attribute states
    (``unspecified``/``unset``/``set``) -- i.e. no registered driver -- or a genuine probe
    failure (non-zero ``git check-attr`` exit).
    """
    result = subprocess.run(
        ["git", "check-attr", "--source", ref, "merge", "--", repo_rel_path],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    line = (result.stdout or "").strip()
    if not line:
        return None
    _prefix, _sep, value = line.rpartition(": ")
    value = value.strip()
    if value in {"", "unspecified", "unset", "set"}:
        return None
    return value


def _resolve_registered_driver_callable(config_key: str) -> Callable[[str, str, str], None]:
    """Map a resolved ``config_key`` to its ``cli.commands.merge_driver`` implementation.

    Reuses the canonical registry (``lanes.merge._MERGE_DRIVERS``) instead of a second,
    hand-maintained table: a driver's ``command`` field (e.g. ``"spec-kitty
    merge-driver-traces %O %A %B"``) names the exact ``merge_driver_<name>`` function this
    derives and calls, so the two can never silently drift apart (C-006). Function-local
    import: avoids paying the ``cli.commands`` package ``__init__`` import cost (and any
    load-order risk) unless a caller actually needs to replay a driver.
    """
    from specify_cli.cli.commands import merge_driver as _merge_driver_module
    from specify_cli.lanes.merge import _MERGE_DRIVERS

    spec = next((candidate for candidate in _MERGE_DRIVERS if candidate.config_key == config_key), None)
    if spec is None:
        raise GitProbeError(f"no merge-driver registry entry for config key {config_key!r}")
    match = _DRIVER_COMMAND_PATTERN.match(spec.command)
    if match is None:
        raise GitProbeError(f"unrecognized merge-driver command shape: {spec.command!r}")
    driver = getattr(_merge_driver_module, match.group(1).replace("-", "_"), None)
    if driver is None or not callable(driver):
        raise GitProbeError(f"no merge-driver implementation for config key {config_key!r}")
    return cast("Callable[[str, str, str], None]", driver)


def driver_replay_expected_bytes(
    repo_root: Path,
    repo_rel_path: str,
    *,
    base_ref: str,
    ours_ref: str,
    theirs_ref: str,
) -> bytes:
    """Replay *repo_rel_path*'s registered merge driver on ``(base, ours, theirs)``.

    The squash-projection driver-replay attribution proof (#5038): a diverged
    coord-partition bookkeeping path is legitimately reconciled by git invoking its
    registered custom driver DURING the real squash. This replays the SAME driver,
    in-process, on the three blobs git would have passed it as ``%O``/``%A``/``%B``,
    so the caller can prove the landed target blob equals the driver's own
    deterministic output rather than demanding raw byte equality with either
    parent (which false-REFUSEs a legitimate union).

    Raises :class:`GitProbeError` (fail-closed; never silently fabricates a result)
    when: the path has no registered merge driver at *ours_ref*
    (:func:`_resolve_merge_driver_config_key`), the ``ours`` or ``theirs`` blob
    cannot be read (a diverged path's two live sides must exist), or the driver
    itself errors while reconciling the materialized blobs. ``base`` may
    legitimately be absent (a path newly added on both sides) -- materialized as
    an empty file, mirroring git's own ``%O`` behavior for a brand-new path.
    """
    from specify_cli.lanes.merge import _ephemeral_merge_driver_activation

    with _ephemeral_merge_driver_activation(repo_root, restore_config=True):
        config_key = _resolve_merge_driver_config_key(repo_root, ours_ref, repo_rel_path)
    if config_key is None:
        raise GitProbeError(f"driver replay for {repo_rel_path!r}: no registered merge driver at {ours_ref}")
    driver = _resolve_registered_driver_callable(config_key)

    ours_bytes = _read_git_blob_bytes(repo_root, ours_ref, repo_rel_path)
    theirs_bytes = _read_git_blob_bytes(repo_root, theirs_ref, repo_rel_path)
    if ours_bytes is None or theirs_bytes is None:
        raise GitProbeError(
            f"driver replay for {repo_rel_path!r}: missing ours ({ours_ref}) or theirs ({theirs_ref}) blob"
        )
    base_bytes = _read_git_blob_bytes(repo_root, base_ref, repo_rel_path) or b""

    with tempfile.TemporaryDirectory(prefix="kitty-driver-replay-") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        base_path = tmp_dir / "O"
        ours_path = tmp_dir / "A"
        theirs_path = tmp_dir / "B"
        base_path.write_bytes(base_bytes)
        ours_path.write_bytes(ours_bytes)
        theirs_path.write_bytes(theirs_bytes)
        try:
            driver(str(base_path), str(ours_path), str(theirs_path))
        except Exception as exc:
            # Any driver failure (typer.Exit, RowMatrixMergeError, ...) REFUSEs
            # fail-closed (FR-003) rather than escaping as an unhandled crash.
            raise GitProbeError(f"driver replay for {repo_rel_path!r} ({config_key}) failed: {exc}") from exc
        return ours_path.read_bytes()


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
    "GitProbeError",
    "sha_reachable_from",
    "commits_in_range",
    "patch_id_of",
    "patch_ids_in_range",
    "first_parent_commits_in_range",
    "blob_id_at",
    "changed_paths_in_range",
    "changed_paths_of",
    "lane_integrated_by_tree_or_ancestry",
    "driver_replay_expected_bytes",
    "merge_tree_write_tree_available",
    "three_way_merge_blob",
]
