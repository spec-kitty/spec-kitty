"""Concurrent review isolation via lock serialization.

Prevents concurrent review agents from colliding on shared test infrastructure.

Primary approach (80% effort): explicit serialization via a review lock.
When a second review agent tries to start in a worktree with an active review,
it blocks with an actionable message.

Secondary approach (20% effort): opt-in env-var isolation via config for
projects that want concurrent reviews. Only activated when
``review.concurrent_isolation.strategy == "env_var"`` is present in
``.kittify/config.yaml``.

Lock location: ``.spec-kitty/review-lock.json`` in the worktree
(git-ignored, ephemeral runtime state).
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.core.process_liveness import is_process_alive
from kernel.clock import now_utc_iso
from kernel.errors import GuardedReadError
from kernel.git import GitCommandError, blob_at, is_tracked, run_git
from kernel.guarded_read import read_guarded

logger = logging.getLogger(__name__)

LOCK_DIR = ".spec-kitty"
LOCK_FILE = "review-lock.json"
#: The lock's path relative to the worktree root, as git names it.
LOCK_REL_PATH = f"{LOCK_DIR}/{LOCK_FILE}"
#: Refusal code for a lock file the review cannot verify (#6386).
REVIEW_LOCK_UNREADABLE = "REVIEW_LOCK_UNREADABLE"
#: Refusal code for a lock file git tracks, whatever its content (#6386).
REVIEW_LOCK_COMMITTED = "REVIEW_LOCK_COMMITTED"

#: The on-disk record's fields and their JSON types (``ReviewLock`` field order).
_LOCK_FIELDS: dict[str, type] = {
    "worktree_path": str,
    "wp_id": str,
    "agent": str,
    "started_at": str,
    "pid": int,
}


class ReviewLockError(Exception):
    """Raised when a concurrent review lock prevents acquiring a new lock."""


class ReviewLockReadError(GuardedReadError, RuntimeError):
    """Raised when ``review-lock.json`` exists but cannot be decoded.

    Mission cli-error-surface-seam WP07/#4746: pre-fix, :meth:`ReviewLock.load`
    silently collapsed ``(json.JSONDecodeError, KeyError, TypeError)`` (and
    left non-UTF-8 bytes fully unguarded) into a ``None`` return --
    indistinguishable from "no active lock". A corrupt lock silently treated
    as absent is a stale-lock safety gap: :meth:`ReviewLock.acquire` would
    happily grant a second concurrent review despite a lock file it could not
    actually verify, the exact collision this module exists to prevent.
    Never raised when the lock file is simply absent (D5) -- ``load`` still
    returns ``None`` for that case.
    """


@dataclass
class ReviewLock:
    """Mutable runtime state representing an active review lock.

    NOTE: This is NOT a frozen dataclass — the lock represents live
    runtime state that may be updated.
    """

    worktree_path: str
    wp_id: str
    agent: str
    started_at: str  # ISO 8601 UTC
    pid: int

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "worktree_path": self.worktree_path,
            "wp_id": self.wp_id,
            "agent": self.agent,
            "started_at": self.started_at,
            "pid": self.pid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewLock:
        """Build a lock from its on-disk record.

        Raises:
            TypeError: When *data* is not an object, lacks a field, carries an
                unknown one, or holds a value of the wrong type. The message
                names the fields (#6386: ``cls(**data)`` on ``{}`` used to
                surface as an unattributed ``ReviewLock.__init__() missing 5
                required positional arguments``).
        """
        if not isinstance(data, dict):
            raise TypeError(f"expected a JSON object, found {type(data).__name__}")
        missing = [name for name in _LOCK_FIELDS if name not in data]
        unknown = sorted(set(data) - set(_LOCK_FIELDS))
        if missing or unknown:
            parts = ([f"missing field(s) {', '.join(missing)}"] if missing else []) + ([f"unknown field(s) {', '.join(unknown)}"] if unknown else [])
            raise TypeError("; ".join(parts))
        wrong = [name for name, kind in _LOCK_FIELDS.items() if not isinstance(data[name], kind) or isinstance(data[name], bool)]
        if wrong:
            raise TypeError(f"field(s) with the wrong type: {', '.join(wrong)}")
        return cls(**data)

    # ------------------------------------------------------------------
    # Staleness detection
    # ------------------------------------------------------------------

    def is_stale(self) -> bool:
        """Check if the lock's process is still alive.

        Delegates to the canonical :func:`is_process_alive` liveness check
        (C-003) instead of an improvised probe.

        Returns:
            True  — process is dead (stale lock)
            False — process is alive or exists but belongs to another user
        """
        return not is_process_alive(self.pid)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, worktree: Path) -> None:
        """Write lock to disk."""
        lock_dir = worktree / LOCK_DIR
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / LOCK_FILE
        lock_path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, worktree: Path) -> ReviewLock | None:
        """Load lock from disk.

        Returns:
            ``None`` only when the lock file does not exist.

        Raises:
            ReviewLockReadError: When the lock file exists but is corrupt
                (non-UTF-8 bytes, malformed JSON, or missing/invalid
                fields) -- fail-closed (FR-012/#4746): a corrupt lock must
                not be silently treated as "no lock" (see
                :class:`ReviewLockReadError`).
        """
        lock_path = worktree / LOCK_DIR / LOCK_FILE
        if not lock_path.exists():
            return None

        return read_guarded(
            lock_path,
            _parse_lock,
            errors=(json.JSONDecodeError, KeyError, TypeError),
            error_cls=ReviewLockReadError,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def acquire(cls, worktree: Path, wp_id: str, agent: str) -> ReviewLock:
        """Acquire a review lock.

        Raises ReviewLockError if a lock exists and its process is still alive.
        Silently overwrites stale locks (dead PID) with a warning.
        """
        lock_path = worktree / LOCK_DIR / LOCK_FILE
        if lock_path.exists():
            existing = cls.load(worktree)
            if existing is not None and not existing.is_stale():
                raise ReviewLockError(
                    f"Worktree {worktree} has an active review by agent "
                    f"'{existing.agent}' on {existing.wp_id} "
                    f"(PID {existing.pid}, started {existing.started_at}). "
                    f"Wait for that review to complete or use a different lane."
                )
            # Stale lock — overwrite with a warning.
            stale_pid = existing.pid if existing is not None else -1
            logger.warning("Removing stale review lock (PID %d is dead)", stale_pid)

        lock = cls(
            worktree_path=str(worktree),
            wp_id=wp_id,
            agent=agent,
            started_at=now_utc_iso(),
            pid=os.getpid(),
        )
        lock.save(worktree)
        return lock

    @staticmethod
    def release(worktree: Path) -> None:
        """Release the review lock.

        Remove the lock file and, if the parent ``.spec-kitty/`` directory is
        empty after removal, remove the directory too. This matters for
        FR-017/FR-018: leftover ``.spec-kitty/`` state in the worktree trips
        spec-kitty's own uncommitted-changes guard (issue #589), so reviewers
        that clean up after themselves must also clean up the parent directory
        when nothing else is storing state there.

        Idempotent: calling release() when no lock exists is a no-op. OSError
        from rmdir (non-empty, permission issues) is swallowed so that review
        cleanup never crashes the CLI command driving the transition.
        """
        lock_dir = worktree / LOCK_DIR
        lock_path = lock_dir / LOCK_FILE
        if lock_path.exists():
            lock_path.unlink()
        if lock_dir.exists() and lock_dir.is_dir():
            try:
                if not any(lock_dir.iterdir()):
                    lock_dir.rmdir()
            except OSError:
                # Non-empty directory or permission issue — leave in place.
                pass


def _parse_lock(content: bytes | str) -> ReviewLock:
    """Decode one lock record; the single parser for the lock file and its committed blob."""
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    return ReviewLock.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Pre-claim check (#6386)
# ---------------------------------------------------------------------------


def _git_stdout(repo: Path, *args: str) -> str | None:
    """``git -C <repo> <args>`` stdout, or ``None`` on a non-zero exit."""
    try:
        result = run_git(repo, *args, check=False)
    except GitCommandError:
        return None  # git could not start (missing binary, unusable directory)
    return result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None


def _git_unreadable(path: str, exc: GitCommandError) -> ReviewLockReadError:
    """A git failure while checking the lock, as an unreadable-lock error: fail closed, never "no lock"."""
    return ReviewLockReadError(path=path, reason=f"git could not check it: {exc}")


def _committed_lock(repo_root: Path, ref: str) -> tuple[bool, ReviewLockReadError | None]:
    """``(present, error)`` for the lock committed at *ref*.

    *error* is ``None`` when the lock is absent or readable. An absent *ref*
    (worktree creation reports that) and an absent path count as "no lock";
    any other git failure is an error, so it refuses instead of passing.
    """
    spec = f"{ref}:{LOCK_REL_PATH}"
    try:
        if run_git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).returncode == 1:
            return False, None
        content = blob_at(repo_root, ref, LOCK_REL_PATH)
    except GitCommandError as exc:
        return False, _git_unreadable(spec, exc)
    if content is None:
        return False, None
    try:
        _parse_lock(content)
    except (ValueError, TypeError) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return True, ReviewLockReadError(path=spec, reason=str(exc))
    return True, None


def _untrack_remedy(worktree: Path, *, exists: bool, branch: str | None, checkout_ref: str | None) -> list[str]:
    """Remedy lines for a lock git tracks: remove it from the branch that carries it.

    A missing workspace whose local branch is absent is cut from *checkout_ref*
    (a remote lane or HEAD); the lock is then fixed at that source, which this
    command cannot check out for you.
    """
    if exists:
        head = _git_stdout(worktree, "symbolic-ref", "--short", "-q", "HEAD")
        where = branch or (head.strip() if head else "") or "the checked-out branch"
    else:
        where = checkout_ref or "the branch"
    if not exists and checkout_ref != branch:
        return [f"  The lock is committed on {where}; it must not be. Remove {LOCK_REL_PATH} there, then re-run the review."]
    quoted = shlex.quote(str(worktree))
    return [
        f"  The lock is committed on {where}; it must not be. Remove it from the branch, then re-run the review:",
        *([f"    git worktree add {quoted} {shlex.quote(where)}"] if not exists else []),
        f"    git -C {quoted} rm -q {LOCK_REL_PATH}",
        f"    Then commit that deletion on {where}.",
    ]


def _lock_state(worktree: Path, *, exists: bool, repo_root: Path, checkout_ref: str | None) -> tuple[bool, ReviewLockReadError | None]:
    """``(committed, read_error)`` for the lock a review would acquire.

    *committed* is true when git tracks the lock in the existing workspace
    (even when a release deleted the file), or when the ref a new workspace
    checks out carries one.
    """
    if not exists:
        return _committed_lock(repo_root, checkout_ref) if checkout_ref else (False, None)
    try:
        ReviewLock.load(worktree)
        error = None
    except ReviewLockReadError as exc:
        error = exc
    # The index, not the file: a tracked lock deleted by a release (``D``) is still committed.
    try:
        return is_tracked(worktree, LOCK_REL_PATH), error
    except GitCommandError as exc:
        return False, error or _git_unreadable(str(worktree / LOCK_REL_PATH), exc)


def review_lock_refusal(
    worktree: Path,
    *,
    exists: bool,
    repo_root: Path,
    checkout_ref: str | None,
    branch: str | None,
    claimed: bool = False,
) -> str | None:
    """Refusal text when the lock a review would acquire is committed or unreadable; ``None`` otherwise.

    Run BEFORE the review claim, so a refusal mutates nothing and a re-run is
    safe (#6386: the lock used to be read only after the ``in_review`` claim
    and its commit, so an unreadable one crashed the command half-way and
    every re-run added another start-review commit). The lock is the file in
    *worktree* when the workspace *exists*; otherwise it is the blob the new
    workspace will check out from *checkout_ref*.

    * ``REVIEW_LOCK_COMMITTED``: git tracks the lock, whatever its content.
      A tracked lock is rewritten by every review and deleted by its release,
      which leaves the lane dirty and blocks consolidation.
    * ``REVIEW_LOCK_UNREADABLE``: an untracked lock that cannot be read.

    Never rewrites or removes the lock: an unverifiable lock may belong to a
    live review. *claimed* is ``True`` only on the fallback after the claim
    (a lock that changed between the check and its acquisition); the text
    then says the claim was recorded instead of claiming nothing changed.
    """
    committed, error = _lock_state(worktree, exists=exists, repo_root=repo_root, checkout_ref=checkout_ref)
    if committed:
        path = error.path if error is not None else (str(worktree / LOCK_REL_PATH) if exists else f"{checkout_ref}:{LOCK_REL_PATH}")
        unreadable = f" and cannot be read ({error.reason})" if error is not None else ""
        lines = [
            f"{REVIEW_LOCK_COMMITTED}: refusing to start the review; the review lock {path} is tracked by git{unreadable}.",
            "  The lock is runtime state: each review rewrites it and its release deletes it, so a tracked lock leaves the lane dirty.",
            _claim_line(claimed),
            *_untrack_remedy(worktree, exists=exists, branch=branch, checkout_ref=checkout_ref),
        ]
    elif error is not None:
        lines = [
            f"{REVIEW_LOCK_UNREADABLE}: refusing to start the review; the review lock {error.path} cannot be read ({error.reason}).",
            "  It was edited by hand, or a write of it was cut short.",
            _claim_line(claimed),
            f"  If no review is running in {worktree}, delete it (rm {shlex.quote(str(error.path))}) and re-run the review.",
        ]
    else:
        return None
    return "\n".join(lines)


def _claim_line(claimed: bool) -> str:
    """What the refusal says about the review claim (see :func:`review_lock_refusal`)."""
    if claimed:
        return "  The review claim was already recorded; once the lock is fixed, re-run the review to finish it."
    return "  The work package was not claimed for review."


# ---------------------------------------------------------------------------
# Opt-in env-var isolation (config-driven, 20% effort)
# ---------------------------------------------------------------------------


def _get_isolation_config(repo_root: Path) -> dict[str, str] | None:
    """Read concurrent_isolation config from .kittify/config.yaml.

    Returns a dict with ``strategy``, ``env_var``, and ``template`` keys,
    or None if not configured or if the strategy is not ``env_var``.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        from ruamel.yaml import YAML

        yaml = YAML()
        config = yaml.load(config_path)
    except Exception:
        return None
    if not isinstance(config, dict):
        return None
    review = config.get("review", {})
    if not isinstance(review, dict):
        return None
    isolation = review.get("concurrent_isolation", {})
    if not isinstance(isolation, dict):
        return None
    if isolation.get("strategy") == "env_var":
        env_var = isolation.get("env_var")
        template = isolation.get("template")
        if env_var and template:
            return {
                "strategy": "env_var",
                "env_var": str(env_var),
                "template": str(template),
            }
    return None


def _apply_env_var_isolation(config: dict[str, str], agent: str, wp_id: str) -> None:
    """Set env var for isolated test execution.

    Formats the configured template with ``agent`` and ``wp_id`` substitutions
    and exports the result as an environment variable.
    """
    value = config["template"].format(agent=agent, wp_id=wp_id)
    os.environ[config["env_var"]] = value
    logger.info("Set %s=%s for review isolation", config["env_var"], value)
