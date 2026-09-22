"""Safe commit helper with destination-ref-aware HEAD assertion.

This module provides utilities for committing only specific files without
capturing unrelated staged changes, while structurally enforcing that the
commit lands on the branch the caller declared.

Contract (post-#1348 / mission ``mission-coordination-branch-atomic-event-log``)
-------------------------------------------------------------------------------

``safe_commit()`` requires a **keyword-only** ``destination_ref`` (the short
branch name, never ``refs/heads/<name>``) and a ``worktree_root`` path. Before
any staging or commit, the helper asserts that the worktree's ``HEAD`` matches
``destination_ref``. There is **no silent fallback** path that infers the
destination from the current working directory or HEAD --- a missing argument
fails ``mypy --strict``, and a mismatched HEAD raises ``SafeCommitHeadMismatch``.

This is the structural invariant that makes every caller correct-by-construction.
Policy can no longer drift from physical staging because policy and physical
target are checked against each other at the chokepoint.

Every exception below carries a stable ``error_code`` (NFR-007) for scripted
detection, plus ``destination_ref`` and (where relevant) ``observed_head`` and
``worktree_root`` so operators and CI tooling can act on structured data.

Operator-index preservation (FR-011/FR-012, #4888)
----------------------------------------------------

``safe_commit`` stages exactly the caller's ``paths`` into the real index
(``git add --force``) and commits ONLY those paths via ``git commit --only``.
It never stashes, unstages, or otherwise mutates anything outside ``paths`` ---
the operator's own staged work (including a file that is only *partially*
staged, e.g. mid ``git add -p``) is never read, moved, or restored, because it
is never touched in the first place. Before this fix, the helper stashed away
everything else with ``git stash push --staged`` and restored it with
``git stash pop --index``; that pop is refused by git whenever any stashed
path also carries an unstaged modification, which deterministically stranded
the operator's staging in an un-poppable stash. ``--only`` structurally cannot
sweep in unrelated content, so there is nothing left to strand.

``assert_staging_area_matches_expected``/``SafeCommitBackstopError`` remain in
this module as an independently-tested, whole-index staging-area probe (see
Priivacy-ai/spec-kitty#588) --- ``safe_commit`` itself no longer calls it in
its default flow, since an unscoped whole-index scan is incompatible with
leaving unrelated staged content in place.

Protected-branch authorization policy (FR-008)
----------------------------------------------

A commit may land on a protected branch ONLY when the caller asserts a
protected-flow :class:`~specify_cli.core.commit_guard.GuardCapability` at the
call site (``release_flow`` / ``upgrade_bookkeeping`` / ``merge_bookkeeping`` /
``test_mode``). The decision is made solely by ``commit_guard.evaluate`` —
authorization is asserted-at-the-surface, never derived from commit-message
text, committed-file content, or ambient environment.

WP03 DELETED the historical privilege channels that used to grant this implicitly:

- the message-prefix allowlist (``release: ``/``chore: …`` etc.) — the upgrade,
  release, and merge-bookkeeping flows now pass an explicit capability;
- the two ``allow_*`` protected-branch bool parameters and the op-record JSONL
  file-content exception — folded into ``GuardCapability.test_mode`` /
  ``merge_bookkeeping``;
- the ``SPEC_KITTY_TEST_MODE`` env privilege hatch.

The ONE retained operator escape hatch,
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` (for solo-fork operators who own
``main``), is consumed by the protected-branch pre-checks AND by
``safe_commit``'s ``ProtectionState`` input computation — the operator declares
the branch unprotected for this repo. ``commit_guard.evaluate`` itself never
reads the environment.

Spec-kitty-internal exceptions (planning-artifact prefixes such as
``"chore: planning artifacts for "``) were removed as part of #1348 (FR-013):
they constituted a silent bypass. New protected-branch flows require a
capability, not a message convention.
"""

from __future__ import annotations

from specify_cli.core.constants import WORKTREES_DIR
import contextlib
import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mission_runtime import CommitTarget
from kernel.paths import to_posix
from specify_cli.core.commit_guard import GuardCapability, GuardVerdict, ProtectionState
from specify_cli.core.commit_guard import evaluate as evaluate_commit_guard
from kernel.git_topology import (
    GitTopologyError,
    git_common_dir,
    git_toplevel,
)
from specify_cli.git.protection_policy import ProtectionPolicy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured error types (NFR-007: each carries a stable ``error_code``)
# ---------------------------------------------------------------------------


# Adopt-on-next-touch: this family predates the shared
# ``specify_cli.core.errors.StructuredError`` base (#1893). Reparent onto it
# (overriding ``to_dict`` for the extra contextual fields) the next time this
# class is materially edited.
class SafeCommitError(RuntimeError):
    """Base class for structured safe_commit errors.

    Subclasses set ``error_code`` to a stable identifier. Every instance
    exposes JSON-serializable fields via :meth:`to_dict` for CI / scripted
    detection (NFR-007).
    """

    error_code: str = "SAFE_COMMIT_GENERIC"

    def __init__(
        self,
        message: str,
        *,
        destination_ref: str | None = None,
        observed_head: str | None = None,
        worktree_root: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.destination_ref = destination_ref
        self.observed_head = observed_head
        self.worktree_root = worktree_root

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for tooling."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "destination_ref": self.destination_ref,
            "observed_head": self.observed_head,
            "worktree_root": str(self.worktree_root) if self.worktree_root is not None else None,
        }


class SafeCommitHeadMismatch(SafeCommitError):
    """Worktree HEAD does not match the declared ``destination_ref``."""

    error_code = "SAFE_COMMIT_HEAD_MISMATCH"

    def __init__(
        self,
        *,
        destination_ref: str,
        observed_head: str,
        worktree_root: Path,
    ) -> None:
        message = (
            f"safe_commit: worktree {worktree_root} HEAD is {observed_head!r}, "
            f"expected {destination_ref!r}. "
            f"Run `git -C {worktree_root} checkout {destination_ref}` first."
        )
        super().__init__(
            message,
            destination_ref=destination_ref,
            observed_head=observed_head,
            worktree_root=worktree_root,
        )


class SafeCommitDestinationRefShape(SafeCommitError):
    """``destination_ref`` was passed in fully-qualified form (``refs/heads/...``).

    The contract requires the **short** branch name. Callers must normalize at
    the boundary so the helper can do a single shape-agnostic comparison. Per
    C-016.
    """

    error_code = "SAFE_COMMIT_DESTINATION_REF_SHAPE"

    def __init__(self, *, destination_ref: str) -> None:
        message = (
            f"safe_commit: destination_ref must be a short branch name, "
            f"got fully-qualified ref {destination_ref!r}. "
            f"Strip the 'refs/heads/' prefix at the call boundary."
        )
        super().__init__(message, destination_ref=destination_ref)


class SafeCommitDestinationNotFound(SafeCommitError):
    """``destination_ref`` does not exist as a branch in the repository."""

    error_code = "SAFE_COMMIT_DESTINATION_NOT_FOUND"

    def __init__(
        self,
        *,
        destination_ref: str,
        worktree_root: Path,
    ) -> None:
        message = f"safe_commit: destination ref {destination_ref!r} does not exist in the repo. Create the branch first, or check the spelling."
        super().__init__(
            message,
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )


class SafeCommitEmptyChangeset(SafeCommitError):
    """The caller passed an empty ``paths`` tuple. Programming error."""

    error_code = "SAFE_COMMIT_EMPTY_CHANGESET"

    def __init__(self, *, destination_ref: str) -> None:
        message = "safe_commit: paths is empty. Pass at least one path to commit; an empty changeset is a programming error."
        super().__init__(message, destination_ref=destination_ref)


class SafeCommitStagedTreeUnchanged(SafeCommitError):
    """The staged tree matches HEAD: a genuine empty changeset (benign no-op).

    Raised ONLY on the index authority (``_staged_tree_is_empty``), never on
    git output text — a rejecting pre-commit hook can print a
    "nothing to commit"-shaped message while leaving a real staged change in
    the index, and that path raises the generic ``RuntimeError`` instead.
    Previously raised as a bare ``RuntimeError`` whose message downstream
    callers had to substring-match (#3861); the type is now the typed signal
    and the message is byte-identical for those prose-matching consumers.
    """

    error_code = "SAFE_COMMIT_STAGED_TREE_UNCHANGED"

    def __init__(self, *, destination_ref: str | None) -> None:
        message = f"safe_commit: nothing to commit for destination_ref={destination_ref!r} (empty changeset)"
        super().__init__(message, destination_ref=destination_ref)


class SafeCommitNotAWorktree(SafeCommitError):
    """``worktree_root`` is not a valid worktree of ``repo_root``."""

    error_code = "SAFE_COMMIT_NOT_A_WORKTREE"

    def __init__(
        self,
        *,
        destination_ref: str,
        worktree_root: Path,
    ) -> None:
        message = f"safe_commit: {worktree_root} is not a git worktree. Pass a resolved worktree path."
        super().__init__(
            message,
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )


class SafeCommitRecoveryFailed(SafeCommitError):
    """Caller staging could not be restored after a failed/successful commit path."""

    error_code = "SAFE_COMMIT_RECOVERY_FAILED"

    def __init__(
        self,
        message: str,
        *,
        destination_ref: str | None = None,
        worktree_root: Path | None = None,
        unrecovered_paths: Sequence[str] = (),
        orphan_stash_ref: str | None = None,
        commit_sha: str | None = None,
    ) -> None:
        super().__init__(
            message,
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )
        self.unrecovered_paths = tuple(unrecovered_paths)
        self.orphan_stash_ref = orphan_stash_ref
        self.commit_sha = commit_sha

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "unrecovered_paths": list(self.unrecovered_paths),
                "orphan_stash_ref": self.orphan_stash_ref,
                "commit_sha": self.commit_sha,
            }
        )
        return payload


class ProtectedBranchRefused(SafeCommitError):
    """``destination_ref`` is protected and ``capability`` authorizes no flow."""

    error_code = "SAFE_COMMIT_PROTECTED_BRANCH"

    def __init__(
        self,
        *,
        destination_ref: str,
        worktree_root: Path,
        commit_message: str,
    ) -> None:
        message = (
            # planning#261 (squad MINOR on #258): safe_commit takes no
            # mission_slug and is called from mission-agnostic sites
            # (core/mission_creation.py, git/bookkeeping_commit.py,
            # invocation/executor.py, cli/commands/next_cmd.py,
            # events/decision_log.py, cli/commands/safe_commit_cmd.py) as well
            # as from mission-aware ones, so this message states only what
            # safe_commit itself knows -- destination_ref is protected --
            # instead of asserting a mission cause or a mission-lifecycle
            # remedy. The mission-aware caller that has mission_slug in scope
            # (coordination/commit_router.py) builds its own diagnostic with
            # the finalize-tasks/mission-create remedy.
            f"safe_commit: refusing to commit to protected branch "
            f"{destination_ref!r} in {worktree_root}. "
            f"Retry against a non-protected feature branch, or set "
            f"SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1 if you own this "
            f"branch."
        )
        super().__init__(
            message,
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )
        self.commit_message = commit_message


class SafeCommitPathPolicyError(SafeCommitError):
    """A requested path violates the safe_commit path policy.

    FR-005 / Issue #1887: paths under ``.worktrees/`` must never be staged via
    ``git add`` from the primary repo root. They are coordination-worktree
    artefacts; committing them from the primary checkout leaks internal paths
    into ``origin/main``. This error fires BEFORE staging, so the index is
    never mutated.
    """

    error_code = "SAFE_COMMIT_PATH_POLICY"

    def __init__(self, *, offending_path: str, worktree_root: Path) -> None:
        message = (
            f"safe_commit: refusing to stage path under .worktrees/: {offending_path}. "
            "Planning artifacts must be committed from the coordination worktree, "
            "not the primary repo root."
        )
        super().__init__(message, worktree_root=worktree_root)
        self.offending_path = offending_path

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["offending_path"] = self.offending_path
        return payload


# ---------------------------------------------------------------------------
# Legacy / staging-area backstop error (preserved from prior implementation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnexpectedStagedPath:
    """A path that appeared in the staging area but was not on the caller's expected list."""

    path: str  # Path as reported by git porcelain (POSIX separators)
    status_code: str  # First two characters of git status --porcelain (e.g. "D ", "M ", "A ")


class SafeCommitBackstopError(RuntimeError):
    """Raised by safe_commit when staged paths do not match the requested paths.

    The backstop fires BEFORE the commit is created, so the commit does not exist.
    Callers should treat this as a data-loss-prevention signal and abort.
    """

    error_code = "SAFE_COMMIT_BACKSTOP"

    def __init__(
        self,
        unexpected: tuple[UnexpectedStagedPath, ...],
        requested: tuple[str, ...],
        *,
        worktree_root: Path | None = None,
        destination_ref: str | None = None,
        head_sha: str | None = None,
    ) -> None:
        self.unexpected = unexpected
        self.requested = requested
        self.worktree_root = worktree_root
        self.destination_ref = destination_ref
        self.head_sha = head_sha
        message_lines = [
            "Commit aborted: staging area contains unexpected paths.",
            "",
            "Requested paths (what safe_commit was told to commit):",
        ]
        for requested_path in requested:
            message_lines.append(f"  {requested_path}")
        message_lines.append("")
        message_lines.append("Unexpected paths staged (would have been committed):")
        for unexpected_path in unexpected:
            message_lines.append(f"  {unexpected_path.status_code} {unexpected_path.path}")
        message_lines.append("")
        # FR-012: name the diverged worktree/ref and the behind/ahead state
        # instead of the bare "working tree is behind HEAD" guess.
        has_phantom_deletions = any(entry.status_code.startswith("D") for entry in unexpected)
        where = str(worktree_root) if worktree_root is not None else "this worktree"
        ref_label = destination_ref if destination_ref is not None else "<unknown ref>"
        head_label = head_sha[:12] if head_sha else "<unknown>"
        message_lines.append(f"Diverged worktree: {where} (checked out: {ref_label}, HEAD {head_label}).")
        if has_phantom_deletions:
            message_lines.append("The index/working tree is BEHIND its own HEAD (the unexpected staged deletions are files HEAD carries but the checkout lacks).")
            message_lines.append(
                f"Most likely cause: the branch ref {ref_label!r} was advanced "
                "underneath this worktree (e.g. `git update-ref` during a merge "
                "while the branch was checked out here, #1826)."
            )
        else:
            message_lines.append(
                "The index/working tree is AHEAD of (or sideways from) HEAD: "
                "the unexpected entries are local additions/modifications that "
                "were never requested for this commit."
            )
        message_lines.append("Investigate before committing:")
        message_lines.append("  git diff --cached")
        message_lines.append("  git status")
        message_lines.append("  git checkout HEAD -- <unexpected-paths>")
        message_lines.append("")
        message_lines.append("The backstop cannot be bypassed by --force.")
        super().__init__("\n".join(message_lines))


class ProtectedBranchCommitError(RuntimeError):
    """Raised when a Spec Kitty status commit would land on a protected branch.

    Retained for backward compatibility with ``assert_not_protected_branch``
    callers. New code raising on a protected destination should use
    :class:`ProtectedBranchRefused` (which carries structured fields).
    """


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitResult:
    """The result of a successful safe_commit call."""

    sha: str
    destination_ref: str
    worktree_root: Path

    def to_dict(self) -> dict[str, str]:
        """Render a JSON-serializable mapping (#1891 / FR-013).

        ``worktree_root`` is a :class:`~pathlib.Path`, which ``json.dumps`` cannot
        serialize directly; rendering it as a string lets callers emit a
        ``CommitResult`` in a ``--json`` payload without raising
        ``Object of type CommitResult is not JSON serializable``.
        """
        return {
            "sha": self.sha,
            "destination_ref": self.destination_ref,
            "worktree_root": str(self.worktree_root),
        }


# ---------------------------------------------------------------------------
# Internal git plumbing helpers (preserved from prior implementation)
# ---------------------------------------------------------------------------


def _run_git_text(repo_path: Path, args: list[str]) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _is_spec_kitty_project(repo_path: Path) -> bool:
    return (repo_path / ".kittify").is_dir()


def _current_branch(repo_path: Path) -> str | None:
    branch = _run_git_text(repo_path, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch:
        return branch

    branch = _run_git_text(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch or branch == "HEAD":
        return None
    return branch


def protected_branches(repo_path: Path) -> frozenset[str]:
    """Return branch names that must not receive Spec Kitty status commits.

    This function is a **public delegate** of :meth:`ProtectionPolicy.resolve`
    (T002 / FR-010).  All resolution logic now lives in
    :mod:`specify_cli.git.protection_policy`; this entry point is kept public
    because :mod:`tests.git.protected_target_fixtures` and the FR-010 import
    allowlist depend on it as the one sanctioned delegate.

    For production code that needs the full policy (including the hatch state),
    prefer :class:`ProtectionPolicy` directly.
    """
    return ProtectionPolicy.resolve(repo_path).protected_branches


def assert_not_protected_branch(repo_path: Path, *, operation: str = "commit") -> None:
    """Fail loudly before a Spec Kitty status commit can pollute local main.

    The guard is bypassed only by the ONE documented operator escape hatch:
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` set to a truthy value
    (``1``, ``true``, ``yes``) — opt-in for solo-fork operators who own ``main``.

    The hatch and the protection set are resolved together via
    :meth:`ProtectionPolicy.resolve` (SF-1 / T002 / FR-009).  WP04's
    ``accept``/``acceptance`` callsites reach protected-branch provenance through
    this function without touching ``commit_helpers`` directly.

    The former ``SPEC_KITTY_TEST_MODE`` privilege hatch was a deleted bypass
    channel (WP03 / FR-008): tests now assert ``GuardCapability.TEST_MODE`` at
    the call site instead of ambient env. Privilege is asserted-at-the-surface,
    never derived from environment.
    """
    repo_path = repo_path.resolve()
    if not _is_spec_kitty_project(repo_path):
        return

    branch = _current_branch(repo_path)
    if branch:
        policy = ProtectionPolicy.resolve(repo_path)
        if policy.is_protected(branch):
            raise ProtectedBranchCommitError(
                f"Refusing to {operation} on protected branch '{branch}' in {repo_path}. Run status commit operations from the mission lane branch/worktree."
            )


def assert_staging_area_matches_expected(
    repo_path: Path,
    expected_paths: Sequence[str],
) -> None:
    """Compare staged paths to ``expected_paths``; raise on mismatch.

    Reads ``git diff --cached --name-status`` at ``repo_path`` and collects all
    currently-staged paths. Any path that is staged but not in
    ``expected_paths`` is a backstop violation and will raise
    ``SafeCommitBackstopError``.

    This function is pure (aside from the ``git`` subprocess probe) --- it does
    not mutate the staging area. It returns ``None`` on success.

    Args:
        repo_path: The repository the stage applies to (worktree root).
        expected_paths: The paths safe_commit was asked to commit, normalized
            to POSIX separators for the compare.

    Raises:
        SafeCommitBackstopError: When any staged path is not in
            ``expected_paths``, or when the ``git diff --cached`` probe fails.
    """
    # See prior history (mission 588) for the --no-renames rationale.
    result = subprocess.run(
        ["git", "diff", "--cached", "--no-renames", "--name-status", "-z"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise SafeCommitBackstopError(
            unexpected=(UnexpectedStagedPath(path="<probe-failed>", status_code="??"),),
            requested=tuple(expected_paths),
            worktree_root=repo_path,
            destination_ref=_current_branch(repo_path),
            head_sha=_run_git_text(repo_path, ["rev-parse", "HEAD"]),
        )

    expected_set = {to_posix(p) for p in expected_paths}
    unexpected: list[UnexpectedStagedPath] = []
    fields = result.stdout.split("\0")
    for index in range(0, len(fields) - 1, 2):
        status_code = fields[index]
        staged_path = fields[index + 1]
        if not status_code or not staged_path:
            continue
        normalized = to_posix(staged_path)
        if normalized not in expected_set:
            unexpected.append(
                UnexpectedStagedPath(path=normalized, status_code=f"{status_code} "),
            )

    if unexpected:
        raise SafeCommitBackstopError(
            unexpected=tuple(unexpected),
            requested=tuple(expected_set),
            worktree_root=repo_path,
            destination_ref=_current_branch(repo_path),
            head_sha=_run_git_text(repo_path, ["rev-parse", "HEAD"]),
        )


# ---------------------------------------------------------------------------
# Destination-ref-aware safe_commit
# ---------------------------------------------------------------------------


def _read_worktree_head(worktree_root: Path) -> str | None:
    """Return the short branch name at worktree HEAD, or ``None`` if detached."""
    raw = _run_git_text(worktree_root, ["symbolic-ref", "HEAD"])
    if raw is None:
        return None
    return raw.removeprefix("refs/heads/")


def _is_worktree_of(repo_root: Path, worktree_root: Path) -> bool:
    """Return ``True`` iff ``worktree_root`` is a worktree of ``repo_root``.

    Uses the unified :func:`~kernel.git_topology.git_toplevel` primitive
    to confirm ``worktree_root`` is the toplevel of *some* git working tree, then
    compares the common dir of ``worktree_root`` and ``repo_root`` — if they share
    a common ``.git`` repository, they are linked. A failing probe (the primitive
    raising :class:`GitTopologyError`) means ``worktree_root`` is not a git
    worktree at all (mission write-path-integrity-01KZZD69 WP01, #3373).
    """
    try:
        toplevel = git_toplevel(worktree_root)
    except GitTopologyError:
        return False
    resolved_worktree_root = worktree_root.resolve()
    # Toplevel guard (NESTED-preserving — do NOT delete, #3373 T005): a checkout
    # whose git toplevel is not itself is nested inside another working tree.
    # Folding it to "not a worktree" here is what keeps the ownership
    # comparator's NESTED refusal reachable — deleting this as "redundant with
    # the common-dir compare below" silently regresses NESTED (a nested checkout
    # shares its parent's common dir, so the compare alone would call it linked).
    if toplevel != resolved_worktree_root:
        return False
    # If worktree_root and repo_root resolve to the same directory, they are
    # trivially "the same" worktree.
    if resolved_worktree_root == repo_root.resolve():
        return True
    # Otherwise, they must share the same (canonicalized) common git dir.
    try:
        wt_common = git_common_dir(worktree_root)
        repo_common = git_common_dir(repo_root)
    except GitTopologyError:
        return False
    return wt_common == repo_common


def is_worktree_of(repo_root: Path, worktree_root: Path) -> bool:
    """Return whether ``worktree_root`` belongs to ``repo_root``'s repository.

    This public wrapper preserves the fail-closed comparator used internally by
    :func:`safe_commit` while allowing preflight validation to reuse the same
    git-topology authority.
    """
    return _is_worktree_of(repo_root, worktree_root)


def _destination_ref_exists(worktree_root: Path, destination_ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{destination_ref}"],
        cwd=worktree_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def _stage_requested_files(repo_path: Path, normalized_files: list[str]) -> bool:
    """Stage each requested file via ``git add --force``. Returns False on failure."""
    for file_path in normalized_files:
        add_result = subprocess.run(
            ["git", "add", "--force", "--", file_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if add_result.returncode != 0:
            return False
    return True


def _staged_patch_for_paths(repo_path: Path, normalized_files: list[str]) -> str | None:
    """Return an exact binary patch for currently-staged requested paths.

    Captured BEFORE ``_stage_requested_files`` mutates the index for these
    (and only these) paths, so a failed commit can revert exactly the
    caller's pre-existing staged state for ``normalized_files`` -- never
    anything outside that set (FR-011/FR-012: unrelated staged content, full
    or partial, is never captured, touched, or restored here).
    """
    if not normalized_files:
        return ""
    result = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--no-ext-diff", "--no-renames", "--", *normalized_files],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _unstage_requested_files(repo_path: Path, normalized_files: list[str]) -> None:
    """Remove ``normalized_files`` from the index, reverting them to HEAD (or
    fully unstaging a never-committed path). Scoped to exactly these paths."""
    if not normalized_files:
        return

    staged_result = subprocess.run(
        ["git", "diff", "--cached", "--no-renames", "--name-only", "-z", "--", *normalized_files],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if staged_result.returncode != 0:
        return
    staged_requested = [path for path in staged_result.stdout.split("\0") if path]
    if not staged_requested:
        return

    has_head = _run_git_text(repo_path, ["rev-parse", "--verify", "HEAD"]) is not None
    if has_head:
        subprocess.run(
            ["git", "restore", "--staged", "--", *staged_requested],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return

    subprocess.run(
        ["git", "rm", "--cached", "--ignore-unmatch", "-q", "--", *staged_requested],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _restore_staged_patch(
    repo_path: Path,
    normalized_files: list[str],
    patch: str | None,
    *,
    destination_ref: str | None = None,
) -> None:
    """Restore the caller's pre-existing staged ``normalized_files`` state
    after a failed commit. Never touches any path outside ``normalized_files``."""
    if patch is None:
        raise SafeCommitRecoveryFailed(
            f"safe_commit: failed to restore caller staging in {repo_path}; requested-file staged patch was not captured before index mutation.",
            destination_ref=destination_ref,
            worktree_root=repo_path,
            unrecovered_paths=normalized_files,
        )
    _unstage_requested_files(repo_path, normalized_files)
    if not patch:
        return
    result = subprocess.run(
        ["git", "apply", "--cached", "--whitespace=nowarn", "-"],
        cwd=repo_path,
        input=patch,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else "."
        raise SafeCommitRecoveryFailed(
            f"safe_commit: failed to restore caller staging in {repo_path}; git apply --cached rejected the requested-file patch{suffix}",
            destination_ref=destination_ref,
            worktree_root=repo_path,
            unrecovered_paths=normalized_files,
        )


_EMPTY_CHANGESET_MARKERS = (
    "nothing to commit",
    "nothing added to commit",
    "no changes added to commit",
)


def _commit_output_is_empty_changeset(output: str) -> bool:
    """True iff git's own output says the commit was a genuine empty changeset.

    Secondary signal only — see :func:`_staged_tree_is_empty` for the
    authoritative check. Output-text matching alone is unsound: a failing
    pre-commit hook can print one of these markers to its own stdout/stderr
    while rejecting a real staged change, which would misclassify a genuine
    failure as a benign no-op (audit finding, PR #3269). Kept as a fallback
    for callers that only have the combined text and no repo to probe.
    """
    low = output.lower()
    return any(marker in low for marker in _EMPTY_CHANGESET_MARKERS)


def _staged_tree_is_empty(repo_path: Path) -> bool:
    """True iff the index matches HEAD, i.e. there is genuinely nothing staged.

    This is the AUTHORITY for the empty-vs-failure decision after a failed
    ``git commit`` (audit BLOCK_MATERIAL, PR #3269): git's own combined
    stdout+stderr text is not a reliable signal, because a pre-commit hook
    that REJECTS a real staged change can still print a "nothing to commit"
    -shaped message on its own account. A hook failure always leaves the
    rejected files staged, so the index still differs from HEAD regardless of
    what strings the hook printed -- while a true no-op leaves the index
    identical to HEAD. Keying off staged state instead of output text makes
    the distinction structural rather than textual.

    Runs ``git diff --cached --quiet`` in ``repo_path``: exit code 0 means the
    staged tree matches HEAD (nothing to commit); exit code 1 means staged
    content differs from HEAD (a real, non-empty change is sitting in the
    index). Any other exit code is treated as "not empty" (fail closed --
    do not mask a genuine failure as a benign no-op just because the probe
    itself misbehaved).
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def _staged_tree_is_empty_for_paths(repo_path: Path, normalized_files: list[str]) -> bool:
    """Pathspec-scoped sibling of :func:`_staged_tree_is_empty` (FR-011/#4888).

    ``safe_commit`` no longer stashes away the operator's unrelated staged
    content before committing (see :func:`_run_commit_capture_sha`'s
    ``--only`` pathspec), so an unscoped ``git diff --cached --quiet`` would
    report "not empty" for ANY unrelated staged file — including one that is
    only partially staged — even when the requested ``normalized_files`` are
    themselves a genuine no-op. Scoping the probe to ``normalized_files``
    keeps the empty-changeset classification correct regardless of what else
    is sitting in the operator's index.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *normalized_files],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def _run_commit_capture_sha(
    repo_path: Path,
    commit_message: str,
    normalized_files: list[str],
) -> tuple[str | None, str, str]:
    """Run ``git commit --only -- <normalized_files>``.

    ``--only`` (git-commit(1)) commits exactly the given pathspec — "taking
    the updated working tree contents of the paths specified..., disregarding
    any contents that have been staged for other paths" — so this is the
    WHOLE fix for #4888/FR-011/FR-012: no stash is pushed, no caller staging
    is touched, and nothing needs restoring afterward, even when an unrelated
    file is only partially staged (the exact shape that made
    ``git stash pop --index`` fail deterministically before this fix).

    Returns ``(new_sha, stdout, stderr)``. ``new_sha`` is ``None`` on failure.
    ``stdout`` and ``stderr`` are kept SEPARATE rather than merged, because the
    two streams mean different things on the success path:

    - ``stdout`` carries git's own routine commit summary (``[branch sha]
      message``, ``N files changed``, ``create mode ...``) — printed on
      *every* successful commit, not a signal worth an operator's attention.
    - ``stderr`` is where the spec-kitty commit guard's warn-mode warning
      lands (``commit_guard_hook.py`` writes via
      ``print(..., file=sys.stderr)`` and exits 0, #3580).

    Merging both into ``combined`` and surfacing it on every successful commit
    (the #3580 fix as first landed) made the routine stdout summary look like
    a guard warning on every single commit — noise that defeats the fix's
    purpose. Keeping the streams separate lets the caller log stdout at DEBUG
    and reserve WARNING for non-empty stderr.

    The FAILURE path is unaffected by this split: callers still combine both
    streams for ``RuntimeError`` detail text, and ``_staged_tree_is_empty`` —
    not this output — remains the sole authority for the
    empty-changeset-vs-genuine-failure classification (audit BLOCK_MATERIAL,
    PR #3269).
    """
    commit_result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "--only", "-m", commit_message, "--", *normalized_files],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if commit_result.returncode != 0:
        return None, commit_result.stdout, commit_result.stderr
    sha = _run_git_text(repo_path, ["rev-parse", "HEAD"])
    return sha, commit_result.stdout, commit_result.stderr


def preflight_commit(
    *,
    repo_root: Path,
    worktree_root: Path,
    target: CommitTarget,
    message: str,
    paths: tuple[Path, ...],
    capability: GuardCapability = GuardCapability.STANDARD,
) -> list[str]:
    """Validate a commit destination and paths without mutating git or files.

    Creation can use the same policy before writing its scaffold. The actual
    commit repeats this validation so a preflight never grants stale authority.
    Return the paths normalized for staging in the selected worktree.
    """
    destination_ref = target.ref
    # 1. Shape: short branch name only.
    if destination_ref.startswith("refs/heads/"):
        raise SafeCommitDestinationRefShape(destination_ref=destination_ref)

    # 2. Non-empty paths.
    if not paths:
        raise SafeCommitEmptyChangeset(destination_ref=destination_ref)

    # 3. worktree_root is a worktree of repo_root.
    if not _is_worktree_of(repo_root, worktree_root):
        raise SafeCommitNotAWorktree(
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )

    # 4. HEAD assertion.
    observed_head = _read_worktree_head(worktree_root)
    if observed_head is None or observed_head != destination_ref:
        raise SafeCommitHeadMismatch(
            destination_ref=destination_ref,
            observed_head=observed_head if observed_head is not None else "<detached>",
            worktree_root=worktree_root,
        )

    # 5. destination_ref exists.
    if not _destination_ref_exists(worktree_root, destination_ref):
        raise SafeCommitDestinationNotFound(
            destination_ref=destination_ref,
            worktree_root=worktree_root,
        )

    resolved_worktree_root = worktree_root.resolve()
    normalized_files: list[str] = []
    for path in paths:
        candidate: Path = path
        if candidate.is_absolute():
            # If the path is not under worktree_root, pass as-is.
            with contextlib.suppress(ValueError):
                candidate = candidate.resolve().relative_to(resolved_worktree_root)
        normalized_files.append(str(candidate))

    # 6a. Path policy: reject any path under .worktrees/ before staging.
    # FR-005 / Issue #1887: .worktrees/ paths must never be staged from the
    # primary repo root. Fires before any index mutation so the index is clean.
    for _norm_path in normalized_files:
        if Path(_norm_path).parts and Path(_norm_path).parts[0] == WORKTREES_DIR:
            raise SafeCommitPathPolicyError(
                offending_path=_norm_path,
                worktree_root=worktree_root,
            )

    # 6. Protected-branch check. The protection DECISION is made SOLELY by the
    #    SK policy module (``commit_guard.evaluate``) — the ONE decision
    #    (C-GUARD-1). The legacy privilege channels (the message-prefix list,
    #    the two ``allow_*`` bools, the op-record file-content exception, the
    #    ``SPEC_KITTY_TEST_MODE`` env hatch) are deleted (WP03 / FR-008; the
    #    last surviving test-mode pre-check reads went with the PR #1850
    #    guard-bypass fix): the asserted-at-the-surface ``capability`` is now
    #    the only authorization, never derived from message text, file
    #    content, or environment.
    #
    #    The ONE retained operator escape hatch
    #    (``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` — solo-fork operators
    #    who own ``main``) is now folded into ``ProtectionPolicy.is_protected``
    #    (WP01 / T002): the policy is resolved at this boundary (FR-007) and the
    #    hatch + set membership are decided together.  ``evaluate`` itself never
    #    reads the environment — agent privilege stays capability-asserted (FR-008).
    #
    #    Both repo_root and worktree_root are checked (the worktree may be on a
    #    different branch when run from inside a lane worktree).  Each resolves
    #    its own ProtectionPolicy so the correct config is read for each root.
    _policy_repo = ProtectionPolicy.resolve(repo_root)
    _policy_wt = ProtectionPolicy.resolve(worktree_root)
    is_protected = _policy_repo.is_protected(destination_ref) or _policy_wt.is_protected(destination_ref)
    guard_verdict: GuardVerdict = evaluate_commit_guard(
        target,
        ProtectionState(is_protected=is_protected),
        capability,
    )
    if not guard_verdict.allowed:
        raise ProtectedBranchRefused(
            destination_ref=destination_ref,
            worktree_root=worktree_root,
            commit_message=message,
        )

    return normalized_files


def safe_commit(
    *,
    repo_root: Path,
    worktree_root: Path,
    destination_ref: str | None = None,
    target: CommitTarget | None = None,
    message: str,
    paths: tuple[Path, ...],
    capability: GuardCapability = GuardCapability.STANDARD,
    effective_root: Path | None = None,
) -> CommitResult:
    """Commit ``paths`` to ``destination_ref`` inside ``worktree_root``.

    This helper structurally enforces that the commit lands on the declared
    branch. The destination-ref-aware HEAD assertion runs **before** any
    staging or commit, so a mismatched HEAD aborts cleanly without touching
    the index.

    Validation order (every step short-circuits the rest):

    1. ``destination_ref`` shape: a fully-qualified ``refs/heads/...`` raises
       :class:`SafeCommitDestinationRefShape`.
    2. ``paths`` non-empty: empty raises :class:`SafeCommitEmptyChangeset`.
    3. ``worktree_root`` is a worktree of ``repo_root``: not a worktree raises
       :class:`SafeCommitNotAWorktree`.
    4. Worktree HEAD matches ``destination_ref`` (short form on both sides);
       mismatch raises :class:`SafeCommitHeadMismatch`.
    5. ``destination_ref`` exists in the repo (``git rev-parse --verify``);
       missing raises :class:`SafeCommitDestinationNotFound`.
    6. ``destination_ref`` is not protected unless ``capability`` authorizes a
       protected-branch flow (decided by ``commit_guard.evaluate``); an
       unauthorized protected destination raises :class:`ProtectedBranchRefused`.
    7. Stage ``paths`` via ``git -C <worktree_root> add --force -- <paths>``
       (mutates the index entries for exactly these paths — nothing else).
    8. Commit via ``git commit --only -- <paths>``, which disregards whatever
       else is staged (FR-011/FR-012/#4888: no stash is pushed, so the
       operator's index and worktree are never touched outside ``paths``,
       even when an unrelated file is only partially staged).
    9. Return the new SHA in :class:`CommitResult`.

    All parameters are keyword-only. Exactly one of ``target`` (preferred) or
    ``destination_ref`` (a destination-string compat shim retained for callers
    not yet converted to ``CommitTarget``) identifies the destination; passing
    neither or both is a programming error.

    Protection decision (ADR Step 7 / IC-02 / FR-008): step 6 below delegates
    the "is this destination allowed?" decision SOLELY to
    ``core.commit_guard.evaluate`` (C-GUARD-1). The legacy privilege channels
    (the message-prefix allowlist, the two ``allow_*`` bools, the op-record
    file-content exception, and the ``SPEC_KITTY_TEST_MODE`` env hatch) are
    deleted. ``capability`` is now the ONLY authorization — asserted at the
    call site and NEVER derived from message text, file content, or
    environment (C-GUARD-2). The single retained operator escape hatch,
    ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS``, is consumed by the
    protected-branch pre-checks and by this function's ``ProtectionState``
    input computation (step 6); ``evaluate`` itself never reads the
    environment.

    Args:
        repo_root: Path to the primary git repository.
        worktree_root: Path to the worktree the commit lands in. May equal
            ``repo_root`` when the primary checkout is the worktree.
        destination_ref: Short branch name (e.g. ``"kitty/mission-foo-01ABCDEF"``).
            Must NOT be fully-qualified. Compat shim — pass ``target`` in new code.
        target: The single resolved :class:`CommitTarget`
            (``mission_runtime.context``) the commit lands on. Preferred over
            ``destination_ref``; its ``ref`` is the destination authority.
        message: The commit message.
        paths: Tuple of file paths to commit. Absolute paths are resolved
            relative to ``worktree_root`` when possible.
        capability: Asserted-at-the-surface authorization passed to
            ``commit_guard.evaluate``. Defaults to ``GuardCapability.STANDARD``.

    Returns:
        :class:`CommitResult` carrying the new commit SHA, the declared
        ``destination_ref``, and the ``worktree_root`` it landed in.

    Raises:
        SafeCommitDestinationRefShape: ``destination_ref`` starts with ``refs/heads/``.
        SafeCommitEmptyChangeset: ``paths`` is empty.
        SafeCommitStagedTreeUnchanged: the staged tree matches HEAD (a genuine
            empty changeset — benign no-op, distinct from a rejecting hook).
        SafeCommitNotAWorktree: ``worktree_root`` is not a git worktree of ``repo_root``.
        SafeCommitHeadMismatch: worktree HEAD does not match ``destination_ref``.
        SafeCommitDestinationNotFound: ``destination_ref`` does not exist in the repo.
        ProtectedBranchRefused: ``destination_ref`` is protected and ``capability``
            authorizes no protected-branch flow.
        SafeCommitStagedTreeUnchanged: the staged tree (scoped to ``paths``)
            matches HEAD (a genuine empty changeset — benign no-op, distinct
            from a rejecting hook).
        SafeCommitRecoveryFailed: the pre-existing staged state of ``paths``
            (and ONLY ``paths`` — never unrelated content) could not be
            captured before mutation, or could not be restored after a
            failed commit.
        RuntimeError: a low-level ``git add`` or ``git commit`` failed.
    """
    # Compatibility-only routing hint after retirement of the ambient sync emitter.
    del effective_root
    # 0. Compat shim: accept either ``target`` (preferred) or the legacy
    #    ``destination_ref`` string. The CommitTarget's ``ref`` is the single
    #    destination authority; ``destination_ref`` mirrors it below so callers
    #    not yet migrated to CommitTarget keep working. (Retiring this shim
    #    requires converting the remaining string callers — out of WP03 scope.)
    if target is not None and destination_ref is not None and target.ref != destination_ref:
        raise SafeCommitDestinationRefShape(destination_ref=destination_ref)
    if target is None:
        if destination_ref is None:
            raise SafeCommitEmptyChangeset(destination_ref="<none>")
        target = CommitTarget(ref=destination_ref)
    destination_ref = target.ref

    normalized_files = preflight_commit(
        repo_root=repo_root,
        worktree_root=worktree_root,
        target=target,
        message=message,
        paths=paths,
        capability=capability,
    )

    # 7. Snapshot, then stage, EXACTLY the requested paths -- and ONLY these
    #    paths. `git add --force -- <path>` mutates the index entry for that
    #    single path alone; every other index entry (fully staged, partially
    #    staged, or untouched) is never read, moved, or written. The
    #    pre-mutation snapshot lets a FAILED commit revert `normalized_files`
    #    to exactly their pre-call staged state -- still scoped to
    #    `normalized_files` alone, so this restore path can never touch, let
    #    alone strand, unrelated content (FR-011/FR-012: contrast with the
    #    pre-fix `git stash push --staged` of EVERYTHING staged).
    requested_staged_patch = _staged_patch_for_paths(worktree_root, normalized_files)
    if requested_staged_patch is None:
        raise SafeCommitRecoveryFailed(
            f"safe_commit: refusing to mutate index in {worktree_root}; could not capture pre-existing staged requested-file state.",
            destination_ref=destination_ref,
            worktree_root=worktree_root,
            unrecovered_paths=normalized_files,
        )
    # Unstage `normalized_files` (scoped to exactly these paths, per above)
    # BEFORE re-staging them individually. This is NOT the removed stash step
    # -- it is load-bearing on its own: if the caller already staged some of
    # `normalized_files` as one half of a git-detected RENAME pair (e.g. a
    # prior `git mv old.py new.py` in the same working tree), git folds both
    # sides into a single `R old.py -> new.py` index entry, and a deleted
    # source path like `old.py` then has NO independently addressable index
    # entry -- `git add --force -- old.py` fails with "pathspec did not match
    # any files". Unstaging first (restoring `old.py` to match HEAD, i.e. a
    # plain unstaged deletion) makes each path in `normalized_files`
    # independently re-stageable, matching the pre-fix behavior for this case.
    _unstage_requested_files(worktree_root, normalized_files)

    if not _stage_requested_files(worktree_root, normalized_files):
        _restore_staged_patch(worktree_root, normalized_files, requested_staged_patch, destination_ref=destination_ref)
        raise RuntimeError(f"safe_commit: failed to stage requested files in {worktree_root}: {normalized_files!r}")

    # 8-9. Commit ONLY the requested paths via `git commit --only`
    # (FR-011/FR-012/#4888): this is the structural fix. `--only` commits
    # exactly the given pathspec and "disregard[s] any contents that have
    # been staged for other paths" (git-commit(1)) -- so unrelated content is
    # never included in the commit itself, on top of never being staged in
    # the first place. Before this fix, `git stash push --staged` followed by
    # `git stash pop --index` was used to hide-then-restore the operator's
    # unrelated staged content; that pop is refused by git whenever any
    # stashed path also has an unstaged modification (an everyday
    # `git add -p` partial stage), which stranded the operator's staging in
    # an un-poppable stash. `--only` never touches that content in the first
    # place, so there is nothing to strand.
    new_sha, commit_stdout, commit_stderr = _run_commit_capture_sha(worktree_root, message, normalized_files)
    commit_created = new_sha is not None
    if commit_created:
        # SUCCESS path: stdout is git's own routine commit summary
        # (`[branch sha] message`, `N files changed`, ...), printed on
        # every successful commit -- not operator-actionable, so it
        # goes to DEBUG rather than crowding the WARNING channel.
        if commit_stdout.strip():
            logger.debug(
                "git commit in %s: %s",
                worktree_root,
                commit_stdout.strip(),
            )
        # stderr is where a pre-commit hook writes (e.g. the
        # spec-kitty commit guard in warn mode, #3580, which prints
        # via `print(..., file=sys.stderr)` and exits 0). Non-empty
        # stderr on an otherwise-successful commit is the genuine
        # signal `capture_output=True` would otherwise swallow --
        # warn-mode still commits; only the discarded signal was the
        # defect. Gating on stderr (not "any output") keeps the
        # channel meaningful: it no longer fires on every commit.
        if commit_stderr.strip():
            logger.warning(
                "git commit in %s produced warnings on a successful commit: %s",
                worktree_root,
                commit_stderr.strip(),
            )
    else:
        # AUTHORITY: staged state (scoped to the requested paths), not git's
        # output text (audit BLOCK_MATERIAL, PR #3269). A rejecting
        # pre-commit hook can print a "nothing to commit"-shaped message on
        # its own account while leaving a real staged change in the index --
        # `_staged_tree_is_empty_for_paths` cannot be fooled by hook output:
        # it is only True when the requested paths genuinely match HEAD.
        commit_output = f"{commit_stdout}\n{commit_stderr}".strip()
        is_empty_changeset = _staged_tree_is_empty_for_paths(worktree_root, normalized_files)
        # A REJECTED commit (hook failure, lock, etc.) must not leave the
        # requested paths staged in the real index -- that would misreport
        # them as tracked (e.g. via `git ls-files`) despite the commit never
        # landing. Restore them to their pre-call state either way.
        _restore_staged_patch(worktree_root, normalized_files, requested_staged_patch, destination_ref=destination_ref)
        if is_empty_changeset:
            # Benign no-op: staged content already matched HEAD. The
            # commit router maps this distinct message to "unchanged".
            raise SafeCommitStagedTreeUnchanged(destination_ref=destination_ref)
        # Genuine failure (rejecting pre-commit hook, lock, etc.) — carry
        # git's own combined output so it is NOT mistaken for an empty
        # changeset (failure-path behavior unchanged: both streams).
        detail = f": {commit_output}" if commit_output else ""
        raise RuntimeError(f"safe_commit: git commit failed in {worktree_root} for destination_ref={destination_ref!r}{detail}")

    assert new_sha is not None  # type narrow: commit_created => new_sha set

    return CommitResult(
        sha=new_sha,
        destination_ref=destination_ref,
        worktree_root=worktree_root,
    )
