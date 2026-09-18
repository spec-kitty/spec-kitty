"""Windows runtime state migration module.

Implements idempotent, one-directional migration of legacy Windows state roots
(~/.spec-kitty, ~/.kittify, ~/.config/spec-kitty) to the canonical
%LOCALAPPDATA%\\spec-kitty\\ location.

Destination-wins semantics: if the canonical root already contains state, the
legacy tree is preserved by renaming to a timestamped *.bak-<ISO-UTC> name.

This module is **pure** with respect to I/O side effects: it emits no CLI
output and imports no rich/console modules.  CLI wiring lives in WP04.

Platform guard: all migration logic is skipped on non-Windows platforms
(``sys.platform != "win32"`` -- the unbanned negative-comparison idiom;
FR-012 only bans the ``==`` form). Locking routes through
``kernel.locks.machine_file_lock`` (FR-010); no raw ``msvcrt``/``fcntl``
call remains in this module.

Spec IDs: FR-006, FR-007, FR-008, NFR-003, NFR-004, C-006, C-007
"""

from __future__ import annotations

import errno
import os
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from kernel.clock import now_utc_compact_stamp
from kernel.locks import LockAcquireTimeout, machine_file_lock
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyWindowsRoot:
    """A known legacy state root and its canonical migration destination.

    Attributes
    ----------
    id:
        Stable identifier used in outcome records and log messages.
    path:
        Absolute path of the legacy root on this machine.
    dest:
        Canonical destination path, or ``None`` for messaging-only roots
        (e.g. ``~/.kittify``) where there is no state to move.
    """

    id: Literal["spec_kitty_home", "kittify_localappdata", "kittify_home", "auth_xdg_home"]
    path: Path
    dest: Path | None  # None == messaging-only, no state to move


@dataclass(frozen=True)
class MigrationOutcome:
    """Structured result for a single legacy-root migration attempt.

    Attributes
    ----------
    legacy_id:
        Matches ``LegacyWindowsRoot.id``.
    status:
        ``"absent"``      — legacy path was not present; no action taken.
        ``"moved"``       — legacy tree moved to dest via os.replace.
        ``"quarantined"`` — dest was non-empty; legacy renamed to *.bak-<ts>.
        ``"error"``       — an OSError or permission failure occurred.
    legacy_path:
        String representation of the legacy root path.
    dest_path:
        String representation of the destination path, or ``None`` if not
        applicable (absent / messaging-only root).
    quarantine_path:
        String representation of the timestamped backup path when status is
        ``"quarantined"``, else ``None``.
    timestamp_utc:
        ISO-UTC timestamp string (``YYYYMMDDTHHMMSSz``) of when this outcome
        was computed.
    error:
        Human-readable error description when status is ``"error"``, else
        ``None``.
    """

    legacy_id: str
    status: Literal["absent", "moved", "quarantined", "error"]
    legacy_path: str
    dest_path: str | None
    quarantine_path: str | None
    timestamp_utc: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    """Return a compact UTC timestamp string: YYYYMMDDTHHMMSSz."""
    return now_utc_compact_stamp()


def _is_non_empty_dir(p: Path) -> bool:
    """Return True if *p* is a directory with at least one child."""
    try:
        return p.is_dir() and any(p.iterdir())
    except OSError:
        return False


def _unique_quarantine_path(parent: Path, name: str, ts: str) -> Path:
    """Return a quarantine path that does not yet exist on the filesystem.

    Base name is ``{name}.bak-{ts}``.  If that already exists (two migrations
    in the same UTC second), appends ``_1``, ``_2``, … until unique.
    """
    candidate = parent / f"{name}.bak-{ts}"
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        candidate = parent / f"{name}.bak-{ts}_{n}"
        if not candidate.exists():
            return candidate
        n += 1


def _known_legacy_roots(root_base: Path, auth_dir: Path) -> list[LegacyWindowsRoot]:
    """Build the list of legacy roots resolved against the current home dir.

    Deferred call (not module-level) so that tests can monkeypatch Path.home()
    before calling migrate_windows_state().
    """
    home = Path.home()
    # On Windows, runtime/home.py historically used platformdirs.user_data_dir("kittify"),
    # which resolves to %LOCALAPPDATA%\kittify\ — the real legacy root that upgraded
    # Windows users have on disk.  Include it as a migration source so upgrade moves
    # that tree to the unified %LOCALAPPDATA%\spec-kitty\ root per Q3=C.
    from platformdirs import user_data_dir  # noqa: PLC0415

    kittify_localappdata = Path(user_data_dir("kittify"))
    return [
        LegacyWindowsRoot(
            id="spec_kitty_home",
            path=home / ".spec-kitty",
            dest=root_base,
        ),
        LegacyWindowsRoot(
            id="kittify_localappdata",
            path=kittify_localappdata,
            dest=root_base,
        ),
        LegacyWindowsRoot(
            id="kittify_home",
            path=home / ".kittify",
            dest=root_base,
        ),
        LegacyWindowsRoot(
            id="auth_xdg_home",
            path=home / ".config" / "spec-kitty",
            dest=auth_dir,
        ),
    ]


# ---------------------------------------------------------------------------
# Contention lock (Windows-only)
# ---------------------------------------------------------------------------


@contextmanager
def _migration_lock(root_base: Path, timeout_s: float = 3.0) -> Iterator[None]:
    """Serialize concurrent migration attempts via the canonical lock primitive.

    On non-Windows platforms this is a no-op context manager that never
    touches the filesystem. The ``sys.platform != "win32"`` guard is the
    unbanned negative-comparison idiom (tests/architectural/
    test_os_detection_ban.py's own over-fire boundary only bans the ``==``
    form; this WP does not additionally route it through ``is_windows()``,
    since it was never seeded in os-detect-ban-wp04.txt and doing so would
    only add churn without shrinking any gate).

    Raises
    ------
    TimeoutError
        When the lock cannot be acquired within *timeout_s* seconds.
    """
    if sys.platform != "win32":
        yield
        return

    root_base.mkdir(parents=True, exist_ok=True)
    lock_path = root_base / ".migrate.lock"
    try:
        with machine_file_lock(lock_path, blocking=True, timeout_s=timeout_s):
            yield
    except LockAcquireTimeout as exc:
        raise TimeoutError("Another Spec Kitty CLI instance is migrating runtime state. Please retry in a moment.") from exc


# ---------------------------------------------------------------------------
# Migration core
# ---------------------------------------------------------------------------


def _migrate_one(
    root: LegacyWindowsRoot,
    ts: str,
    *,
    dry_run: bool,
) -> MigrationOutcome:
    """Attempt to migrate a single legacy root and return a structured outcome.

    Guarantees:
    - Never calls os.unlink, shutil.rmtree, or os.remove on any path.
    - On cross-volume EXDEV: uses shutil.copytree + rename to quarantine.
    - On any OSError: returns status="error" with a descriptive message.
    """
    legacy_path_str = str(root.path)

    # Absent: legacy path does not exist
    if not root.path.exists():
        return MigrationOutcome(
            legacy_id=root.id,
            status="absent",
            legacy_path=legacy_path_str,
            dest_path=str(root.dest) if root.dest is not None else None,
            quarantine_path=None,
            timestamp_utc=ts,
        )

    # Self-migration guard: if legacy path is (or resolves to) the destination,
    # there is nothing to move.  Can happen when platformdirs returns the same
    # path for both app names (unlikely in production; defensive for tests that
    # mock user_data_dir to a single tmp_path).
    if root.dest is not None:
        try:
            if root.path.resolve() == root.dest.resolve():
                return MigrationOutcome(
                    legacy_id=root.id,
                    status="absent",
                    legacy_path=legacy_path_str,
                    dest_path=str(root.dest),
                    quarantine_path=None,
                    timestamp_utc=ts,
                )
        except OSError:
            pass  # resolve() can fail on weird paths; fall through to normal migration

    # Messaging-only root: exists but no state to move (retained as a safety
    # hatch; no entry currently uses dest=None after the DRIFT-3 fix)
    if root.dest is None:
        return MigrationOutcome(
            legacy_id=root.id,
            status="absent",
            legacy_path=legacy_path_str,
            dest_path=None,
            quarantine_path=None,
            timestamp_utc=ts,
        )

    dest_path_str = str(root.dest)

    # Destination is non-empty: quarantine the legacy tree (destination wins)
    if _is_non_empty_dir(root.dest):
        quarantine = _unique_quarantine_path(root.path.parent, root.path.name, ts)
        quarantine_path_str = str(quarantine)

        if dry_run:
            return MigrationOutcome(
                legacy_id=root.id,
                status="quarantined",
                legacy_path=legacy_path_str,
                dest_path=dest_path_str,
                quarantine_path=quarantine_path_str,
                timestamp_utc=ts,
            )

        try:
            os.replace(str(root.path), str(quarantine))
        except OSError as exc:
            return MigrationOutcome(
                legacy_id=root.id,
                status="error",
                legacy_path=legacy_path_str,
                dest_path=dest_path_str,
                quarantine_path=quarantine_path_str,
                timestamp_utc=ts,
                error=(f"Could not quarantine {root.path} → {quarantine}: {exc}"),
            )

        return MigrationOutcome(
            legacy_id=root.id,
            status="quarantined",
            legacy_path=legacy_path_str,
            dest_path=dest_path_str,
            quarantine_path=quarantine_path_str,
            timestamp_utc=ts,
        )

    # Destination is empty (or absent): move the legacy tree
    if dry_run:
        return MigrationOutcome(
            legacy_id=root.id,
            status="moved",
            legacy_path=legacy_path_str,
            dest_path=dest_path_str,
            quarantine_path=None,
            timestamp_utc=ts,
        )

    try:
        root.dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(root.path), str(root.dest))
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            # Cross-volume: copy then quarantine source (never delete)
            quarantine = _unique_quarantine_path(root.path.parent, root.path.name, ts)
            quarantine_path_str = str(quarantine)
            try:
                shutil.copytree(str(root.path), str(root.dest))
                os.replace(str(root.path), str(quarantine))
            except OSError as inner_exc:
                return MigrationOutcome(
                    legacy_id=root.id,
                    status="error",
                    legacy_path=legacy_path_str,
                    dest_path=dest_path_str,
                    quarantine_path=quarantine_path_str,
                    timestamp_utc=ts,
                    error=(f"Cross-volume copy of {root.path} → {root.dest} failed: {inner_exc}"),
                )
            return MigrationOutcome(
                legacy_id=root.id,
                status="moved",
                legacy_path=legacy_path_str,
                dest_path=dest_path_str,
                quarantine_path=quarantine_path_str,
                timestamp_utc=ts,
            )

        return MigrationOutcome(
            legacy_id=root.id,
            status="error",
            legacy_path=legacy_path_str,
            dest_path=dest_path_str,
            quarantine_path=None,
            timestamp_utc=ts,
            error=f"Could not move {root.path} → {root.dest}: {exc}",
        )

    return MigrationOutcome(
        legacy_id=root.id,
        status="moved",
        legacy_path=legacy_path_str,
        dest_path=dest_path_str,
        quarantine_path=None,
        timestamp_utc=ts,
    )


def migrate_windows_state(dry_run: bool = False) -> list[MigrationOutcome]:
    """One-time, idempotent migration of legacy Windows state.

    Moves legacy state roots (~/.spec-kitty, ~/.kittify, ~/.config/spec-kitty)
    to the canonical %LOCALAPPDATA%\\spec-kitty\\ location.

    No-op on non-Windows platforms (returns ``[]`` immediately without
    importing platformdirs or msvcrt).

    Parameters
    ----------
    dry_run:
        When ``True``, computes what *would* happen without touching the
        filesystem.  Returned outcomes reflect the intended operations.

    Returns
    -------
    list[MigrationOutcome]
        One outcome per known legacy root.  Empty list on non-Windows.

    Raises
    ------
    TimeoutError
        Propagated from ``_migration_lock`` when another process holds the
        lock for longer than 3 seconds.  Caller should convert to an
        ``status="error"`` outcome with exit code 69.
    """
    if sys.platform != "win32":
        return []

    from specify_cli.paths import get_runtime_root  # noqa: PLC0415

    root = get_runtime_root()
    legacy_roots = _known_legacy_roots(root.base, root.auth_dir)

    ts = _utc_timestamp()
    outcomes: list[MigrationOutcome] = []

    # TimeoutError from _migration_lock is intentionally NOT caught here; it
    # propagates to the CLI caller so `spec-kitty migrate` can exit with code
    # 69 (EX_UNAVAILABLE) under lock contention, per FR-007/FR-008 and
    # contracts/cli-migrate.md.  Per-root OSError / EXDEV etc. are still
    # captured as status="error" outcomes inside _migrate_one().
    with _migration_lock(root.base):
        for legacy in legacy_roots:
            outcome = _migrate_one(legacy, ts, dry_run=dry_run)
            outcomes.append(outcome)

    return outcomes
