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

The optional ``expected_parent_sha`` path is reserved for a caller that must
commit against one captured branch tip. It builds the commit from that parent
and advances the destination through the canonical ref-advance seam with a
compare-and-swap; the normal commit path is unchanged when the argument is
omitted.

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

``assert_staging_area_matches_expected`` (the whole-index staging-area probe,
Priivacy-ai/spec-kitty#588) is DELETED (mission ``fold-4946-stash-gate``,
#4915/#4946/#4936): ``safe_commit`` had already stopped calling it in its
default flow before this deletion, since an unscoped whole-index scan is
incompatible with leaving unrelated staged content in place, and the #470
dead-symbol gate confirmed it had zero remaining ``src/`` callers.
``SafeCommitBackstopError`` (and ``UnexpectedStagedPath``) are RETAINED
despite losing their only raise sites: ``tests/contract/test_orchestrator_api.py``
still asserts ``SafeCommitBackstopError.error_code`` stays within the
orchestrator-api ``allowed_error_codes`` contract, and
``cli/commands/safe_commit_cmd.py`` still imports/catches it. Deleting the
class would require updating that contract test too; left for an explicit
operator allowlist-or-delete call rather than silently folded in here.

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
import os
import shlex
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mission_runtime import CommitTarget
from specify_cli.core.commit_guard import GuardCapability, GuardVerdict, ProtectionState
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.commit_guard import evaluate as evaluate_commit_guard
from kernel.git import GitCommandError, changed_paths
from kernel.resolution import is_symlink_loop_error, resolve_commit_path
from kernel.git_topology import (
    GitTopologyError,
    git_common_dir,
    git_toplevel,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.git.ref_advance import RefAdvanceError, advance_branch_ref_for_commit

if TYPE_CHECKING:
    from mission_runtime import OwnedCheckout

    from specify_cli.core.owned_mission import OwnedCreateMission

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


class SafeCommitPathLoopRefused(SafeCommitError):
    """A requested path is (or sits under) a symlink loop (#5671 / #5251).

    Raised before any index mutation. Still a ``RuntimeError`` through
    :class:`SafeCommitError`, so callers that flatten ``RuntimeError`` keep working.
    """

    error_code = "SAFE_COMMIT_PATH_LOOP"

    def __init__(self, *, offending_path: Path, worktree_root: Path) -> None:
        super().__init__(
            f"safe_commit: refusing symlink loop at {offending_path}",
            worktree_root=worktree_root,
        )
        self.offending_path = offending_path

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["offending_path"] = str(self.offending_path)
        return payload


class SafeCommitIndexDeletionConflict(SafeCommitError):
    """A path was both requested for commit and listed in ``index_deletions`` (FR-022)."""

    error_code = "SAFE_COMMIT_INDEX_DELETION_CONFLICT"

    def __init__(self, *, conflicting_paths: Sequence[str], worktree_root: Path) -> None:
        super().__init__(
            f"safe_commit: path(s) both requested and listed as index deletions: {', '.join(conflicting_paths)}",
            worktree_root=worktree_root,
        )
        self.conflicting_paths = tuple(conflicting_paths)


class SafeCommitIndexResidue(SafeCommitRecoveryFailed):
    """An index-deletion commit landed but the real index still stages a committed path (FR-022).

    Raised only AFTER HEAD moved, so it is a :class:`SafeCommitRecoveryFailed` carrying
    ``commit_sha``: callers that flatten a plain ``SafeCommitError`` into "not committed"
    (``upgrade.autocommit.commit_touched_checkout``) re-raise it instead, and the upgrade
    renderer reports that the commit DID land. It keeps its own ``error_code``.
    """

    error_code = "SAFE_COMMIT_INDEX_RESIDUE"

    def __init__(
        self,
        *,
        residue: Sequence[str],
        commit_sha: str,
        worktree_root: Path,
        destination_ref: str | None = None,
    ) -> None:
        super().__init__(
            f"safe_commit: commit {commit_sha} landed, but the index still stages: {', '.join(residue)}",
            destination_ref=destination_ref,
            worktree_root=worktree_root,
            unrecovered_paths=residue,
            commit_sha=commit_sha,
        )
        self.residue = tuple(residue)


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
    diagnostic: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Render a JSON-serializable mapping (#1891 / FR-013).

        ``worktree_root`` is a :class:`~pathlib.Path`, which ``json.dumps`` cannot
        serialize directly; rendering it as a string lets callers emit a
        ``CommitResult`` in a ``--json`` payload without raising
        ``Object of type CommitResult is not JSON serializable``.
        """
        payload = {
            "sha": self.sha,
            "destination_ref": self.destination_ref,
            "worktree_root": str(self.worktree_root),
        }
        if self.diagnostic is not None:
            payload["diagnostic"] = self.diagnostic
        return payload


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


def _stage_requested_files(
    repo_path: Path,
    normalized_files: list[str],
    env: Mapping[str, str] | None = None,
) -> tuple[str, str] | None:
    """Stage each requested file via ``git add --force``.

    Returns ``None`` on success, else ``(path, git's stderr)`` for the first
    path git refused (#4722).
    """
    for file_path in normalized_files:
        add_result = subprocess.run(
            ["git", "add", "--force", "--", file_path],
            cwd=repo_path,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if add_result.returncode != 0:
            return file_path, add_result.stderr.strip()
    return None


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

    try:
        staged_requested = [str(path) for path in changed_paths(repo_path, cached=True, pathspecs=normalized_files)]
    except GitCommandError:
        # Best-effort recovery step (unchanged): when the probe fails there is
        # nothing safe to unstage, and the caller still re-applies its patch.
        return
    if not staged_requested:
        return

    has_head = _run_git_text(repo_path, ["rev-parse", "--verify", "HEAD"]) is not None
    if has_head:
        subprocess.run(
            ["git", "--literal-pathspecs", "restore", "--staged", "--", *staged_requested],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return

    subprocess.run(
        ["git", "--literal-pathspecs", "rm", "--cached", "--ignore-unmatch", "-q", "--", *staged_requested],
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


def _git_in(
    worktree_root: Path,
    args: list[str],
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=worktree_root,
        env=None if env is None else dict(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _temp_index_path(worktree_root: Path) -> Path:
    """A fresh index-file path under the worktree's own git dir (never inside the work tree).

    The location comes from ``--absolute-git-dir`` with ``GIT_INDEX_FILE`` scrubbed from the
    probe's env: ``--git-path index`` would follow an inherited ``GIT_INDEX_FILE`` and could
    place the temporary index beside it, inside the work tree.
    """
    # Defensive only: ``--absolute-git-dir`` does not read GIT_INDEX_FILE today, so this scrub is
    # behavior-neutral (an equivalent mutant). It is kept so the probe stays index-independent if
    # it is ever switched to an index-sensitive form such as ``--git-path index``.
    probe_env = {key: value for key, value in os.environ.items() if key != "GIT_INDEX_FILE"}
    probe = _git_in(worktree_root, ["rev-parse", "--absolute-git-dir"], probe_env)
    if probe.returncode != 0 or not probe.stdout.strip():
        raise RuntimeError(f"safe_commit: could not locate the git dir of {worktree_root}: {probe.stderr.strip()}")
    git_dir = Path(probe.stdout.strip())
    return git_dir / f"spec-kitty-index-deletions.{os.getpid()}.{os.urandom(4).hex()}.tmp"


def _discard_temp_index(temp_index: Path) -> None:
    for leftover in (temp_index, temp_index.with_name(temp_index.name + ".lock")):
        with contextlib.suppress(OSError):
            leftover.unlink()


def _build_index_deletion_tree(
    worktree_root: Path,
    temp_env: Mapping[str, str],
    requested: list[str],
    deletions: list[str],
) -> None:
    """Seed the temp index from HEAD (never the real index), then apply the requested adds and the deletions."""
    seeded = _git_in(worktree_root, ["read-tree", "HEAD"], temp_env)
    if seeded.returncode != 0:
        raise RuntimeError(f"safe_commit: could not seed the temporary index from HEAD in {worktree_root}: {seeded.stderr.strip()}")
    failure = _stage_requested_files(worktree_root, requested, temp_env)
    if failure is not None:
        bad_path, git_reason = failure
        raise RuntimeError(f"safe_commit: failed to stage requested files in {worktree_root}: {bad_path!r}: {git_reason}")
    if deletions:
        removed = _git_in(worktree_root, ["rm", "--cached", "--quiet", "--ignore-unmatch", "--", *deletions], temp_env)
        if removed.returncode != 0:
            raise RuntimeError(f"safe_commit: failed to drop index deletions in {worktree_root}: {removed.stderr.strip()}")


def _sync_real_index_after_commit(worktree_root: Path, destination_ref: str, sha: str, paths: list[str]) -> None:
    """Make the real index match the new HEAD for ``paths`` only; every other entry stays as the operator left it."""
    reset = _git_in(worktree_root, ["reset", "-q", "HEAD", "--", *paths])
    if reset.returncode != 0:
        raise SafeCommitRecoveryFailed(
            f"safe_commit: commit {sha} landed on {destination_ref}, but the index could not be synced for the committed paths: {reset.stderr.strip()}",
            destination_ref=destination_ref,
            worktree_root=worktree_root,
            unrecovered_paths=paths,
            commit_sha=sha,
        )
    try:
        leftover = [str(entry) for entry in changed_paths(worktree_root, cached=True, pathspecs=paths)]
    except GitCommandError:
        leftover = list(paths)  # an unreadable index is not proof that it is clean
    if leftover:
        raise SafeCommitIndexResidue(residue=leftover, commit_sha=sha, worktree_root=worktree_root, destination_ref=destination_ref)


def _commit_with_index_deletions(
    worktree_root: Path,
    destination_ref: str,
    message: str,
    requested: list[str],
    deletions: list[str],
) -> CommitResult:
    """Commit ``requested`` (added) and ``deletions`` (index-removed) from a temporary index (FR-022).

    ``git commit --only`` re-reads the working tree, so it would re-add a file the
    caller untracked on purpose (``git rm --cached``, file kept on disk). A commit from
    a temporary index seeded from HEAD records the removal without touching the work
    tree, and cannot see any entry the operator staged: the temp index is built from
    HEAD, not from the real index. Hooks run (no ``--no-verify``) and see exactly
    HEAD versus the temp index through the inherited ``GIT_INDEX_FILE``. The operator's
    own ``GIT_INDEX_FILE`` is overridden for these calls only and never written back.
    """
    temp_index = _temp_index_path(worktree_root)
    temp_env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
    try:
        _build_index_deletion_tree(worktree_root, temp_env, requested, deletions)
        if _git_in(worktree_root, ["diff", "--cached", "--quiet"], temp_env).returncode == 0:
            raise SafeCommitStagedTreeUnchanged(destination_ref=destination_ref)
        commit = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", message],
            cwd=worktree_root,
            env=temp_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if commit.returncode != 0:
            detail = f"{commit.stdout}\n{commit.stderr}".strip()
            raise RuntimeError(f"safe_commit: git commit failed in {worktree_root} for destination_ref={destination_ref!r}" + (f": {detail}" if detail else ""))
        sha = _run_git_text(worktree_root, ["rev-parse", "HEAD"])
        assert sha is not None
        if commit.stderr.strip():
            logger.warning("git commit in %s produced warnings on a successful commit: %s", worktree_root, commit.stderr.strip())
        _sync_real_index_after_commit(worktree_root, destination_ref, sha, [*requested, *deletions])
        return CommitResult(sha=sha, destination_ref=destination_ref, worktree_root=worktree_root)
    finally:
        _discard_temp_index(temp_index)


def _mission_scoped_policies(
    repo_root: Path,
    worktree_root: Path,
    mission_slug: str | None,
    *,
    owned: OwnedCheckout | OwnedCreateMission | None = None,
) -> tuple[ProtectionPolicy, ProtectionPolicy]:
    """Resolve the repo-root and worktree policies, folded to *mission_slug*'s ``commit_to_target``.

    #5100 FR-008 mission-scoped hatch: when every staged path lives under one
    mission's ``kitty-specs/<slug>/`` the commit is that mission's own write.

    * **Owned** (``owned`` set): ownership is the validated fact, never inferred
      from the filesystem shape of the two roots. The one owned authority,
      :meth:`ProtectionPolicy.resolve_for_owned`, folds the mission's
      ``meta.json`` held in the owned checkout (and the union of both roots'
      protection configs) -- it never re-derives the repository root.
    * **Non-owned**: :meth:`ProtectionPolicy.for_mission` folds the mission's
      primary ``meta.json`` for both roots (origin/main's rule, including its
      fail-closed ambiguous-selector arm).

    A commit that is not one mission's own write keeps both plain policies.
    """
    if not mission_slug:
        return ProtectionPolicy.resolve(repo_root), ProtectionPolicy.resolve(worktree_root)
    if owned is not None:
        owned_policy = ProtectionPolicy.resolve_for_owned(owned, mission_slug)
        return owned_policy, owned_policy
    return (
        ProtectionPolicy.resolve(repo_root).for_mission(repo_root, mission_slug),
        ProtectionPolicy.resolve(worktree_root).for_mission(repo_root, mission_slug),
    )


def _single_mission_slug(normalized_files: list[str]) -> str | None:
    """Return the mission slug when every path is under one ``kitty-specs/<slug>/``, else ``None``."""
    slugs: set[str] = set()
    for rel in normalized_files:
        parts = Path(rel).parts
        if len(parts) < 3 or parts[0] != KITTY_SPECS_DIR:
            return None
        slugs.add(parts[1])
    return next(iter(slugs)) if len(slugs) == 1 else None


def _run_git_for_commit(
    worktree_root: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one captured Git command for the expected-parent path."""
    return subprocess.run(
        ["git", *args],
        cwd=worktree_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run_expected_parent_hook(
    worktree_root: Path,
    hook_name: str,
    hook_args: list[str],
    *,
    env: dict[str, str],
) -> None:
    """Run a normal Git commit hook against the isolated candidate index."""
    command = ["hook", "run", "--ignore-missing", hook_name]
    if hook_args:
        command.extend(["--", *hook_args])
    result = _run_git_for_commit(worktree_root, command, env=env)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"safe_commit: {hook_name} hook rejected expected-parent commit: {detail or 'hook failed'}")


def _build_expected_parent_tree(
    worktree_root: Path,
    expected_parent_sha: str,
    normalized_files: list[str],
    message_file: Path,
    *,
    env: dict[str, str],
    expected_path_bytes: Mapping[str, bytes],
    index_only_removals: frozenset[str] = frozenset(),
) -> str:
    """Run commit-message hooks and build a tree containing only requested paths."""
    read_tree = _run_git_for_commit(worktree_root, ["read-tree", expected_parent_sha], env=env)
    if read_tree.returncode != 0:
        raise RuntimeError(f"safe_commit: could not seed expected-parent index: {read_tree.stderr.strip()}")
    for file_path in normalized_files:
        if Path(file_path).is_absolute() or ".." in Path(file_path).parts:
            raise RuntimeError(f"safe_commit: expected-parent path must be worktree-relative: {file_path!r}")
        operation = ["update-index", "--force-remove", "--", file_path] if file_path in index_only_removals else ["add", "--force", "--", file_path]
        staged = _run_git_for_commit(worktree_root, operation, env=env)
        if staged.returncode != 0:
            raise RuntimeError(f"safe_commit: failed to stage expected-parent path {file_path!r}: {staged.stderr.strip()}")

    intended_tree = _write_expected_parent_tree(worktree_root, env=env)
    _run_expected_parent_hook(worktree_root, "pre-commit", [], env=env)
    _run_expected_parent_hook(worktree_root, "prepare-commit-msg", [str(message_file), "message"], env=env)
    _run_expected_parent_hook(worktree_root, "commit-msg", [str(message_file)], env=env)

    reset_index = _run_git_for_commit(worktree_root, ["read-tree", expected_parent_sha], env=env)
    if reset_index.returncode != 0:
        raise RuntimeError(f"safe_commit: could not isolate expected-parent paths: {reset_index.stderr.strip()}")
    for file_path in normalized_files:
        operation = ["update-index", "--force-remove", "--", file_path] if file_path in index_only_removals else ["add", "--force", "--", file_path]
        staged = _run_git_for_commit(worktree_root, operation, env=env)
        if staged.returncode != 0:
            raise RuntimeError(f"safe_commit: failed to stage expected-parent path {file_path!r}: {staged.stderr.strip()}")

    tree = _write_expected_parent_tree(worktree_root, env=env)
    if tree != intended_tree:
        requested = ", ".join(normalized_files)
        raise RuntimeError(f"safe_commit: commit hook changed requested path contents after staging; refusing expected-parent commit for {requested}")
    _verify_expected_parent_tree_bytes(worktree_root, tree, expected_path_bytes, env=env)
    for removed_path in index_only_removals:
        if _run_git_for_commit(worktree_root, ["ls-tree", tree, "--", removed_path], env=env).stdout.strip():
            raise RuntimeError("safe_commit: decision runtime lock remains in candidate tree")
    return tree


def _write_expected_parent_tree(worktree_root: Path, *, env: dict[str, str]) -> str:
    """Write the candidate index tree or raise with Git's diagnostic."""
    tree = _run_git_for_commit(worktree_root, ["write-tree"], env=env)
    if tree.returncode != 0 or not tree.stdout.strip():
        raise RuntimeError(f"safe_commit: could not write expected-parent tree: {tree.stderr.strip()}")
    return tree.stdout.strip()


def _hash_raw_blob_bytes(worktree_root: Path, contents: bytes) -> str:
    """Return Git's object ID for exact bytes, without applying clean filters."""
    result = subprocess.run(
        ["git", "hash-object", "--stdin", "--no-filters"],
        cwd=worktree_root,
        input=contents,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"safe_commit: could not hash expected raw path bytes: {detail or 'git hash-object failed'}")
    return result.stdout.decode("ascii", errors="replace").strip()


def _verify_expected_parent_tree_bytes(
    worktree_root: Path,
    tree_sha: str,
    expected_path_bytes: Mapping[str, bytes],
    *,
    env: dict[str, str],
) -> None:
    """Refuse a candidate tree whose selected blobs differ from caller bytes."""
    for path, expected_bytes in expected_path_bytes.items():
        actual_blob = _run_git_for_commit(worktree_root, ["rev-parse", "--verify", f"{tree_sha}:{path}"], env=env)
        if actual_blob.returncode != 0:
            detail = (actual_blob.stderr or actual_blob.stdout).strip()
            raise RuntimeError(f"safe_commit: could not inspect staged blob for {path!r}: {detail or 'git rev-parse failed'}")
        expected_blob_sha = _hash_raw_blob_bytes(worktree_root, expected_bytes)
        if actual_blob.stdout.strip() != expected_blob_sha:
            raise RuntimeError(f"safe_commit: staged blob for {path!r} differs from expected raw bytes; refusing expected-parent commit")


def _resolve_commit_path_or_refuse(root: Path, candidate: Path, worktree_root: Path) -> Path:
    """``resolve_commit_path`` with a looping path raised as the typed refusal."""
    try:
        return resolve_commit_path(root, candidate)
    except OSError as exc:
        if is_symlink_loop_error(exc):
            raise SafeCommitPathLoopRefused(offending_path=candidate, worktree_root=worktree_root) from exc
        raise


def _normalize_expected_parent_path_bytes(
    worktree_root: Path,
    normalized_files: list[str],
    expected_path_bytes: Mapping[Path, bytes] | None,
) -> dict[str, bytes]:
    """Normalize exact-content assertions to the same paths used for staging."""
    if expected_path_bytes is None:
        return {}
    root = worktree_root.resolve()
    normalized: dict[str, bytes] = {}
    for requested_path, contents in expected_path_bytes.items():
        candidate = Path(requested_path)
        if candidate.is_absolute():
            try:
                candidate = _resolve_commit_path_or_refuse(root, candidate, worktree_root).relative_to(root)
            except ValueError as exc:
                raise RuntimeError(f"safe_commit: expected raw-bytes path must be inside the worktree: {requested_path}") from exc
        if candidate.is_absolute() or ".." in candidate.parts:
            raise RuntimeError(f"safe_commit: expected raw-bytes path must be worktree-relative: {requested_path}")
        relative_path = str(candidate)
        if relative_path not in normalized_files:
            raise RuntimeError(f"safe_commit: expected raw-bytes path was not requested for staging: {relative_path!r}")
        if relative_path in normalized:
            raise RuntimeError(f"safe_commit: duplicate expected raw-bytes path: {relative_path!r}")
        normalized[relative_path] = contents
    return normalized


def _create_expected_parent_commit(
    worktree_root: Path,
    tree_sha: str,
    expected_parent_sha: str,
    message_file: Path,
) -> str:
    """Create a commit object whose sole parent is the captured target tip."""
    signing = _expected_parent_signing_args(worktree_root)
    created = _run_git_for_commit(
        worktree_root,
        ["commit-tree", *signing, tree_sha, "-p", expected_parent_sha, "-F", str(message_file)],
    )
    if created.returncode != 0 or not created.stdout.strip():
        detail = (created.stderr or created.stdout).strip()
        raise RuntimeError(f"safe_commit: could not create expected-parent commit: {detail or 'git commit-tree failed'}")
    return created.stdout.strip()


def _expected_parent_signing_args(worktree_root: Path) -> list[str]:
    """Translate Git's commit.gpgsign setting to commit-tree's explicit option."""
    configured = _run_git_for_commit(worktree_root, ["config", "--bool", "--get", "commit.gpgsign"])
    if configured.returncode == 1:
        return []
    if configured.returncode != 0:
        detail = (configured.stderr or configured.stdout).strip()
        raise RuntimeError(f"safe_commit: could not read commit signing configuration: {detail or 'git config failed'}")
    return ["-S"] if configured.stdout.strip().lower() == "true" else []


def _compare_and_swap_commit_ref(
    repo_root: Path,
    worktree_root: Path,
    destination_ref: str,
    new_sha: str,
    expected_parent_sha: str,
    message: str,
) -> None:
    """Advance the target ref only while it still names the captured parent."""
    try:
        advance_branch_ref_for_commit(
            repo_root,
            worktree_root,
            destination_ref,
            new_sha,
            expected_old_sha=expected_parent_sha,
            message=message,
        )
    except RefAdvanceError as exc:
        raise RuntimeError(f"safe_commit: conditional advance of target {destination_ref!r} from expected parent {expected_parent_sha} failed: {exc}") from exc


def _expected_parent_index_repair_diagnostic(
    worktree_root: Path,
    destination_ref: str,
    new_sha: str,
    normalized_files: list[str],
    detail: str,
) -> str:
    """Describe how to repair the real index after a commit has landed."""
    repair = shlex.join(["git", "reset", "--quiet", new_sha, "--", *normalized_files])
    return (
        f"safe_commit: commit {new_sha} landed on {destination_ref}, but its requested index paths "
        f"could not be refreshed: {detail or 'git reset failed'}. Repair the index by running "
        f"{repair} from {worktree_root}."
    )


def _append_commit_diagnostic(current: str | None, addition: str) -> str:
    """Combine post-commit diagnostics without dropping earlier repair advice."""
    return f"{current}; {addition}" if current else addition


def _safe_commit_with_expected_parent(
    *,
    repo_root: Path,
    worktree_root: Path,
    destination_ref: str,
    expected_parent_sha: str,
    message: str,
    normalized_files: list[str],
    expected_path_bytes: Mapping[str, bytes],
    index_only_removals: frozenset[str] = frozenset(),
) -> CommitResult:
    """Create a hook-checked commit and atomically compare-and-swap its ref."""
    landed_sha: str | None = None
    result: CommitResult | None = None
    diagnostic: str | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="spec-kitty-pin-cas-") as temp_dir:
            temp_root = Path(temp_dir)
            index_path = temp_root / "index"
            message_file = temp_root / "COMMIT_EDITMSG"
            message_file.write_text(f"{message}\n", encoding="utf-8")
            candidate_env = os.environ.copy()
            candidate_env["GIT_INDEX_FILE"] = str(index_path)
            tree_sha = _build_expected_parent_tree(
                worktree_root,
                expected_parent_sha,
                normalized_files,
                message_file,
                env=candidate_env,
                expected_path_bytes=expected_path_bytes,
                index_only_removals=index_only_removals,
            )
            expected_tree = _run_git_text(worktree_root, ["show", "-s", "--format=%T", expected_parent_sha])
            if tree_sha == expected_tree:
                raise SafeCommitStagedTreeUnchanged(destination_ref=destination_ref)
            new_sha = _create_expected_parent_commit(worktree_root, tree_sha, expected_parent_sha, message_file)
            _compare_and_swap_commit_ref(
                repo_root,
                worktree_root,
                destination_ref,
                new_sha,
                expected_parent_sha,
                message,
            )
            landed_sha = new_sha

            try:
                index_update = _run_git_for_commit(worktree_root, ["reset", "--quiet", new_sha, "--", *normalized_files])
            except OSError as exc:
                diagnostic = _expected_parent_index_repair_diagnostic(
                    worktree_root,
                    destination_ref,
                    new_sha,
                    normalized_files,
                    str(exc),
                )
                logger.error(diagnostic)
            else:
                if index_update.returncode != 0:
                    detail = (index_update.stderr or index_update.stdout).strip()
                    diagnostic = _expected_parent_index_repair_diagnostic(
                        worktree_root,
                        destination_ref,
                        new_sha,
                        normalized_files,
                        detail,
                    )
                    logger.error(diagnostic)

            try:
                post_commit = _run_git_for_commit(worktree_root, ["hook", "run", "--ignore-missing", "post-commit"])
            except OSError as exc:
                hook_diagnostic = f"safe_commit: commit {new_sha} landed, but the post-commit hook could not run: {exc}"
                diagnostic = _append_commit_diagnostic(diagnostic, hook_diagnostic)
                logger.warning(hook_diagnostic)
            else:
                if post_commit.returncode != 0:
                    logger.warning("post-commit hook failed after expected-parent commit %s: %s", new_sha, (post_commit.stderr or post_commit.stdout).strip())
            result = CommitResult(sha=new_sha, destination_ref=destination_ref, worktree_root=worktree_root, diagnostic=diagnostic)
    except OSError as exc:
        if landed_sha is None:
            raise
        if result is None:
            diagnostic = _expected_parent_index_repair_diagnostic(
                worktree_root,
                destination_ref,
                landed_sha,
                normalized_files,
                str(exc),
            )
            logger.error(diagnostic)
        else:
            cleanup_diagnostic = f"safe_commit: commit {landed_sha} landed, but its temporary commit workspace cleanup failed: {exc}"
            diagnostic = _append_commit_diagnostic(diagnostic, cleanup_diagnostic)
            logger.warning(cleanup_diagnostic)
        return CommitResult(sha=landed_sha, destination_ref=destination_ref, worktree_root=worktree_root, diagnostic=diagnostic)

    if result is None:
        raise RuntimeError("safe_commit: expected-parent commit completed without a result")
    return result


def preflight_commit(
    *,
    repo_root: Path,
    worktree_root: Path,
    target: CommitTarget,
    message: str,
    paths: tuple[Path, ...],
    capability: GuardCapability = GuardCapability.STANDARD,
    owned: OwnedCheckout | OwnedCreateMission | None = None,
) -> list[str]:
    """Validate a commit destination and paths without mutating git or files.

    Creation can use the same policy before writing its scaffold. The actual
    commit repeats this validation so a preflight never grants stale authority.
    Return the paths normalized for staging in the selected worktree.

    ``owned`` is the validated owned-checkout fact (an owned lifecycle write's
    :class:`~mission_runtime.OwnedCheckout`, or an owned ``mission create``'s
    :class:`~specify_cli.core.owned_mission.OwnedCreateMission`); the
    mission-scoped ``commit_to_target`` fold then reads the mission from the
    fact (see :func:`_mission_scoped_policies`).
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
            # Parents resolved, final component kept: a symlink is committed as
            # the link, never its target (#5671). If the path is not under
            # worktree_root, pass as-is.
            with contextlib.suppress(ValueError):
                candidate = _resolve_commit_path_or_refuse(resolved_worktree_root, candidate, worktree_root).relative_to(resolved_worktree_root)
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
    #    Mission-scoped fold (#5100 FR-008): when EVERY staged path lives under one
    #    mission's ``kitty-specs/<slug>/``, the commit is that mission's own write
    #    and ``ProtectionPolicy.for_mission`` honours its persisted
    #    ``commit_to_target`` for its own target branch only. Any path outside a
    #    single mission dir (or no ``commit_to_target``) leaves the policy as-is.
    _policy_repo, _policy_wt = _mission_scoped_policies(repo_root, worktree_root, _single_mission_slug(normalized_files), owned=owned)
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


def _validate_runtime_lock_removal(
    worktree_root: Path,
    paths: tuple[Path, ...],
    expected_parent_sha: str | None,
    expected_path_bytes: Mapping[Path, bytes] | None,
    index_only_removals: tuple[Path, ...],
    owned: OwnedCheckout | OwnedCreateMission | None,
) -> frozenset[str]:
    """Restrict index-only deletion to the one validated decision lock owner."""
    from mission_runtime import OwnedCheckout
    from specify_cli.decisions.service import _decisions_lock_path

    if not index_only_removals:
        return frozenset()
    if expected_parent_sha is None or not isinstance(owned, OwnedCheckout):
        raise ValueError("index-only removal requires an owned decision runtime lock and expected parent")
    lock_path = _decisions_lock_path(owned.mission_dir)
    if worktree_root.resolve() != owned.owned_root or index_only_removals != (lock_path,) or lock_path not in paths:
        raise ValueError("index-only removal is restricted to the owned decision runtime lock")
    owned.files([lock_path])
    current = lock_path
    while current != owned.owned_root:
        if current.is_symlink():
            raise ValueError("decision runtime lock must not have a symlink ancestor")
        current = current.parent
    if expected_path_bytes and lock_path in expected_path_bytes:
        raise ValueError("decision runtime lock removal cannot assert a payload blob")
    return frozenset([str(lock_path.relative_to(owned.owned_root))])


def safe_commit(
    *,
    repo_root: Path,
    worktree_root: Path,
    destination_ref: str | None = None,
    target: CommitTarget | None = None,
    message: str,
    paths: tuple[Path, ...],
    capability: GuardCapability = GuardCapability.STANDARD,
    expected_parent_sha: str | None = None,
    expected_path_bytes: Mapping[Path, bytes] | None = None,
    index_only_removals: tuple[Path, ...] = (),
    owned: OwnedCheckout | OwnedCreateMission | None = None,
    index_deletions: Sequence[Path] = (),
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
        expected_parent_sha: Optional exact parent for a conditional ref update.
            When supplied, a commit is built against this SHA and the target
            branch advances only if it still points to that SHA.
        index_only_removals: Internal owner-bound decision lock removal; requires
            a validated owned fact and expected parent. Keeps physical files.
        expected_path_bytes: Optional exact raw bytes expected in selected
            staged blobs. Requires ``expected_parent_sha`` and refuses before
            ref update if a clean filter changes any asserted path.
        index_deletions: Paths whose INDEX deletion is committed while the file
            stays on disk (FR-022: a migration's ``git rm --cached``). Committed
            from a temporary index seeded from HEAD, so the work tree is never
            touched and no operator-staged entry can enter the commit; afterwards
            the real index is synced for these paths only. An untracked entry is
            a no-op; a path also in ``paths`` raises
            :class:`SafeCommitIndexDeletionConflict`. Incompatible with
            ``expected_parent_sha``.
        owned: The validated owned-checkout fact when this is an owned write
            (``None`` otherwise). The mission-scoped protection fold then reads
            the mission from the fact -- never inferred from the two roots'
            filesystem shape, never re-deriving the repository root.

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

    if index_deletions and expected_parent_sha is not None:
        raise ValueError("index_deletions cannot be combined with expected_parent_sha")
    removals = _validate_runtime_lock_removal(worktree_root, paths, expected_parent_sha, expected_path_bytes, index_only_removals, owned)

    normalized_files = preflight_commit(
        repo_root=repo_root,
        worktree_root=worktree_root,
        target=target,
        message=message,
        paths=(*paths, *index_deletions),
        capability=capability,
        owned=owned,
    )
    if index_deletions:
        requested_files = normalized_files[: len(paths)]
        deletion_files = normalized_files[len(paths) :]
        conflicts = sorted(set(requested_files) & set(deletion_files))
        if conflicts:
            raise SafeCommitIndexDeletionConflict(conflicting_paths=conflicts, worktree_root=worktree_root)
        return _commit_with_index_deletions(worktree_root, destination_ref, message, requested_files, deletion_files)

    if expected_parent_sha is not None:
        normalized_expected_path_bytes = _normalize_expected_parent_path_bytes(
            worktree_root,
            normalized_files,
            expected_path_bytes,
        )
        return _safe_commit_with_expected_parent(
            repo_root=repo_root,
            worktree_root=worktree_root,
            destination_ref=destination_ref,
            expected_parent_sha=expected_parent_sha,
            message=message,
            normalized_files=normalized_files,
            expected_path_bytes=normalized_expected_path_bytes,
            index_only_removals=removals,
        )
    if expected_path_bytes is not None:
        raise ValueError("expected_path_bytes requires expected_parent_sha")

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

    stage_failure = _stage_requested_files(worktree_root, normalized_files)
    if stage_failure is not None:
        _restore_staged_patch(worktree_root, normalized_files, requested_staged_patch, destination_ref=destination_ref)
        bad_path, git_reason = stage_failure
        raise RuntimeError(f"safe_commit: failed to stage requested files in {worktree_root}: {bad_path!r}: {git_reason}")

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
