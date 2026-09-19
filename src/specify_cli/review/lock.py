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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.core.process_liveness import is_process_alive
from kernel.clock import now_utc_iso
from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded

logger = logging.getLogger(__name__)

LOCK_DIR = ".spec-kitty"
LOCK_FILE = "review-lock.json"


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

        def _parse(content: bytes | str) -> ReviewLock:
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            return cls.from_dict(json.loads(text))

        return read_guarded(
            lock_path,
            _parse,
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
