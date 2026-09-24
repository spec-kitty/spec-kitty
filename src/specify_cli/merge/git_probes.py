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
]
