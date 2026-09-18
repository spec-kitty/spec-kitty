"""Upgrade-attempt history types and store for the history store (FR-013, FR-015).

Public surface
--------------
UpgradeAttemptOutcome   -- StrEnum with 3 outcome values.
UpgradeAttemptRecord    -- Frozen dataclass: one history entry.
UpgradeAttemptStore     -- SQLite-backed history store (FR-015).
default_history_db_path -- Resolve the default DB path (SPEC_KITTY_HISTORY_DB_PATH override).

NFR-007: No PII may be stored in attempt records. No user paths, project
slugs, hostnames, or machine IDs are present in any field of
``UpgradeAttemptRecord``. ``attempt_id`` is a ULID (time-sortable,
collision-resistant, no identity information).

NFR-006: WAL journal mode for concurrent-write safety.
NFR-005: INSERT OR IGNORE idempotency; retention trim to last 200 per install_method.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.clock import UTC, datetime, now_epoch, parse_iso
from kernel.paths import is_windows

if TYPE_CHECKING:
    from specify_cli.compat._detect.install_method import InstallMethod


# ---------------------------------------------------------------------------
# UpgradeAttemptOutcome enum
# ---------------------------------------------------------------------------


class UpgradeAttemptOutcome(StrEnum):
    """Outcome of a single upgrade attempt."""

    SUCCESS = "success"
    FAILURE = "failure"
    ABORTED = "aborted"


# ---------------------------------------------------------------------------
# UpgradeAttemptRecord dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpgradeAttemptRecord:
    """A single upgrade attempt entry persisted to the history store.

    NFR-007: No PII. No user paths, project slugs, hostnames, or machine IDs.
    ``attempt_id`` is a ULID (26 chars), used as idempotency key.
    """

    attempt_id: str  # ULID (26 chars), used as idempotency key
    timestamp: datetime  # UTC datetime of attempt completion
    install_method: InstallMethod  # which install method was used
    intent: str  # RemediationIntent value
    outcome: UpgradeAttemptOutcome
    exit_code: int | None  # subprocess exit code, or None if aborted
    target_version: str | None  # target version if known, else None


# ---------------------------------------------------------------------------
# DDL constants
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS upgrade_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id        TEXT    NOT NULL UNIQUE,
    timestamp_utc     TEXT    NOT NULL,
    install_method    TEXT    NOT NULL,
    intent            TEXT    NOT NULL,
    outcome           TEXT    NOT NULL,
    exit_code         INTEGER,
    target_version    TEXT,
    created_at        REAL    NOT NULL
)
"""

# NOTE: idx_upgrade_attempts_attempt_id is intentionally omitted.
# The UNIQUE constraint on attempt_id already creates an implicit index;
# adding a second explicit UNIQUE index would be redundant (WP01 reviewer note).
_CREATE_INDEX_METHOD_SQL = """\
CREATE INDEX IF NOT EXISTS idx_upgrade_attempts_method_created
    ON upgrade_attempts(install_method, created_at DESC)
"""

_RETENTION_SQL = """\
DELETE FROM upgrade_attempts
WHERE id NOT IN (
    SELECT id FROM upgrade_attempts
    WHERE install_method = ?
    ORDER BY created_at DESC
    LIMIT 200
)
AND install_method = ?
"""

_RETENTION_LIMIT = 200
_CONSECUTIVE_FAILURE_SCAN_LIMIT = 100


# ---------------------------------------------------------------------------
# default_history_db_path()
# ---------------------------------------------------------------------------


def default_history_db_path() -> Path:
    """Resolve the default history store path.

    Resolution order (contracts/history-store-query.md):
    1. ``SPEC_KITTY_HISTORY_DB_PATH`` env var, if set and non-empty.
    2. ``platformdirs.user_cache_dir("spec-kitty") / "upgrade-history.db"``.
    3. Manual XDG/OS fallback (same pattern as NagCache ``_resolve_cache_dir``).
    """
    env_override = os.environ.get("SPEC_KITTY_HISTORY_DB_PATH", "")
    if env_override:
        return Path(env_override)

    try:
        from platformdirs import user_cache_dir

        return Path(user_cache_dir("spec-kitty")) / "upgrade-history.db"
    except ImportError:
        pass

    # Manual XDG/OS fallback.
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / "spec-kitty"
    elif is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        base = Path(local_app_data) / "spec-kitty" / "Cache" if local_app_data else Path.home() / "AppData" / "Local" / "spec-kitty" / "Cache"
    else:
        # Linux / WSL / other POSIX
        xdg = os.environ.get("XDG_CACHE_HOME", "")
        cache_base = Path(xdg) if xdg else Path.home() / ".cache"
        base = cache_base / "spec-kitty"

    return base / "upgrade-history.db"


# ---------------------------------------------------------------------------
# UpgradeAttemptStore
# ---------------------------------------------------------------------------


class UpgradeAttemptStore:
    """Persistent history store for upgrade attempts.

    Thread-safe for concurrent reads. Writes use WAL mode for
    concurrent-write safety (NFR-006).

    All write operations are fail-safe (swallow all errors).
    All read operations are fail-open (return safe defaults on error).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialise. Uses ``default_history_db_path()`` when db_path is None."""
        self._db_path: Path = db_path if db_path is not None else default_history_db_path()

    def _connect(self) -> sqlite3.Connection:
        """Open (or create) the SQLite database with WAL mode and the schema.

        If schema initialisation raises (e.g. PRAGMA/CREATE on a locked or
        corrupt DB) the just-opened connection is closed before the error
        propagates — otherwise the fd leaks, since the caller's
        ``contextlib.closing`` only engages once this method returns.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(_CREATE_INDEX_METHOD_SQL)
            conn.commit()
        except Exception:
            conn.close()
            raise
        return conn

    def append(self, record: UpgradeAttemptRecord) -> None:
        """Append a record. Best-effort; swallows all errors (fail-safe).

        Uses INSERT OR IGNORE — duplicate ``attempt_id`` is a silent no-op.
        Runs retention trim after each successful write (both in one transaction).
        """
        try:
            ts = record.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            timestamp_utc = ts.astimezone(UTC).isoformat()
            created_at = ts.timestamp()
            install_method_str = str(record.install_method)

            with contextlib.closing(self._connect()) as conn, conn:
                conn.execute(
                    """\
                    INSERT OR IGNORE INTO upgrade_attempts
                        (attempt_id, timestamp_utc, install_method, intent,
                         outcome, exit_code, target_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.attempt_id,
                        timestamp_utc,
                        install_method_str,
                        record.intent,
                        str(record.outcome),
                        record.exit_code,
                        record.target_version,
                        created_at,
                    ),
                )
                conn.execute(_RETENTION_SQL, (install_method_str, install_method_str))
        except Exception:
            pass

    def is_idempotent(self, attempt: UpgradeAttemptRecord) -> bool:
        """Return True if a successful attempt with same install_method + target_version exists.

        Fail-open: returns False on any store error.

        Returns False when ``attempt.target_version`` is None (cannot deduplicate
        an unknown version).
        """
        if attempt.target_version is None:
            return False
        try:
            with contextlib.closing(self._connect()) as conn:
                cursor = conn.execute(
                    """\
                    SELECT 1 FROM upgrade_attempts
                    WHERE outcome = 'success'
                      AND install_method = ?
                      AND target_version = ?
                    LIMIT 1
                    """,
                    (str(attempt.install_method), attempt.target_version),
                )
                row = cursor.fetchone()
            return row is not None
        except Exception:
            return False

    def consecutive_failure_count(
        self,
        install_method: InstallMethod,
        *,
        window_seconds: int = 300,
    ) -> int:
        """Return the count of consecutive failures at the tail of recent history.

        Fail-open: returns 0 on any store error.

        Scans at most the last ``_CONSECUTIVE_FAILURE_SCAN_LIMIT`` (100) records
        for ``install_method`` within ``window_seconds`` of now, counting from the
        tail until the first non-failure record (contracts/history-store-query.md).
        """
        try:
            cutoff = now_epoch() - window_seconds
            with contextlib.closing(self._connect()) as conn:
                cursor = conn.execute(
                    """\
                    SELECT outcome FROM upgrade_attempts
                    WHERE install_method = ?
                      AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (str(install_method), cutoff, _CONSECUTIVE_FAILURE_SCAN_LIMIT),
                )
                rows = cursor.fetchall()

            count = 0
            for (outcome,) in rows:
                if outcome == UpgradeAttemptOutcome.FAILURE:
                    count += 1
                else:
                    break
            return count
        except Exception:
            return 0

    def last_success_timestamp(
        self,
        install_method: InstallMethod,
    ) -> datetime | None:
        """Return UTC datetime of the most recent successful attempt, or None.

        Fail-open: returns None on any store error.
        """
        try:
            with contextlib.closing(self._connect()) as conn:
                cursor = conn.execute(
                    """\
                    SELECT timestamp_utc FROM upgrade_attempts
                    WHERE outcome = 'success'
                      AND install_method = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (str(install_method),),
                )
                row = cursor.fetchone()
            if row is None:
                return None
            (timestamp_utc,) = row
            dt = parse_iso(timestamp_utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except Exception:
            return None
