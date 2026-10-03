"""Hardened per-user Feedback Survey preferences (``feedback.json``).

The file lives in the per-user **config** directory (never in a project
repository, C-006) so clearing caches neither re-arms prompts nor forgets
"don't ask again". Every failure mode folds toward silence: a read that
cannot be trusted yields :class:`Unreadable`, which the eligibility check
treats as "no automatic offer"; a write that fails returns ``False``.

Hardening on read: the file and its parent directory must not be symlinks,
the file must be a regular file of at most 64 KiB, and on POSIX it must be
owned by the current user with mode ``0600``. The size/owner/mode checks run
on the already-open descriptor (``fstat``), so they cannot race a swap of
the path.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from kernel.atomic import atomic_write
from kernel.clock import UTC, datetime, parse_iso
from kernel.locks import machine_file_lock
from kernel.no_follow import NoFollowPathError, chmod_no_follow, open_no_follow
from kernel.paths import is_windows

__all__ = [
    "LOCK_FILENAME",
    "MAX_PREFERENCES_BYTES",
    "PREFERENCES_FILENAME",
    "SCHEMA_VERSION",
    "SurveyPreferences",
    "Unreadable",
    "load_preferences",
    "lock_path_for",
    "preferences_path",
    "resolve_config_dir",
    "save_preferences",
    "set_automatic_prompts",
]

_LOG = logging.getLogger(__name__)

SCHEMA_VERSION = 1
PREFERENCES_FILENAME = "feedback.json"
LOCK_FILENAME = "feedback.lock"
MAX_PREFERENCES_BYTES = 64 * 1024

_FILE_MODE = 0o600
_DIR_MODE = 0o700
_SET_PROMPTS_LOCK_TIMEOUT_S = 2.0

_KEY_SCHEMA_VERSION = "schema_version"
_KEY_AUTOMATIC_PROMPTS = "automatic_prompts"
_KEY_LAST_SHOWN_AT = "last_shown_at"
_KEY_ENDPOINT_OVERRIDE = "endpoint_override"


@dataclass(frozen=True)
class SurveyPreferences:
    """The persisted per-user Feedback Survey state."""

    schema_version: int = SCHEMA_VERSION
    automatic_prompts: bool = True
    last_shown_at: datetime | None = None
    endpoint_override: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict (``last_shown_at`` as ISO-8601 UTC)."""
        return {
            _KEY_SCHEMA_VERSION: self.schema_version,
            _KEY_AUTOMATIC_PROMPTS: self.automatic_prompts,
            _KEY_LAST_SHOWN_AT: self.last_shown_at.astimezone(UTC).isoformat() if self.last_shown_at is not None else None,
            _KEY_ENDPOINT_OVERRIDE: self.endpoint_override,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SurveyPreferences:
        """Deserialise with strict type checks; absent keys take their defaults.

        Raises:
            ValueError: A field has the wrong type or value, or
                ``schema_version`` is not a version this build understands.
        """
        schema_version = data.get(_KEY_SCHEMA_VERSION, SCHEMA_VERSION)
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ValueError(f"{_KEY_SCHEMA_VERSION} must be an integer")
        if not 1 <= schema_version <= SCHEMA_VERSION:
            raise ValueError(f"unsupported {_KEY_SCHEMA_VERSION} {schema_version}")

        automatic_prompts = data.get(_KEY_AUTOMATIC_PROMPTS, True)
        if not isinstance(automatic_prompts, bool):
            raise ValueError(f"{_KEY_AUTOMATIC_PROMPTS} must be a boolean")

        return cls(
            schema_version=schema_version,
            automatic_prompts=automatic_prompts,
            last_shown_at=_parse_timestamp(_optional_str(data, _KEY_LAST_SHOWN_AT)),
            endpoint_override=_optional_str(data, _KEY_ENDPOINT_OVERRIDE),
        )


@dataclass(frozen=True)
class Unreadable:
    """Sentinel: ``feedback.json`` exists but cannot be trusted.

    ``reason`` is a short human-readable explanation for ``--status``.
    """

    reason: str


def _optional_str(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _parse_timestamp(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    parsed = parse_iso(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def resolve_config_dir() -> Path:
    """Return the per-user spec-kitty config directory (shared with the upgrade config)."""
    from specify_cli.compat.config import _resolve_config_dir

    return Path(_resolve_config_dir())


def preferences_path(resolver: Callable[[], Path] | None = None) -> Path:
    """Return ``<user_config_dir>/feedback.json``; *resolver* overrides the config dir."""
    config_dir = resolver() if resolver is not None else resolve_config_dir()
    return config_dir / PREFERENCES_FILENAME


def lock_path_for(prefs_path: Path) -> Path:
    """Return the dedicated lock file that guards *prefs_path* (``feedback.lock`` beside it)."""
    return prefs_path.with_name(LOCK_FILENAME)


def _read_bounded(fd: int) -> bytes:
    chunks: list[bytes] = []
    remaining = MAX_PREFERENCES_BYTES + 1
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _stat_problem(st: os.stat_result) -> str | None:
    """Return why an open preferences file is untrustworthy, or ``None``."""
    if not stat.S_ISREG(st.st_mode):
        return "not a regular file"
    if st.st_size > MAX_PREFERENCES_BYTES:
        return "file too large"
    if is_windows():
        return None
    if st.st_uid != os.geteuid():
        return "not owned by the current user"
    if stat.S_IMODE(st.st_mode) != _FILE_MODE:
        return f"permissions are {stat.S_IMODE(st.st_mode):o}, expected {_FILE_MODE:o}"
    return None


def _read_trusted_bytes(path: Path) -> bytes | Unreadable | None:
    """Read *path* under the hardening rules; ``None`` means the file is absent."""
    if path.parent.is_symlink():
        return Unreadable("config directory is a symlink")
    try:
        fd = open_no_follow(path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    except NoFollowPathError:
        return Unreadable("preferences file is a symlink")
    except OSError as exc:
        return Unreadable(f"cannot open preferences file: {exc.strerror or exc}")
    try:
        problem = _stat_problem(os.fstat(fd))
        if problem is not None:
            return Unreadable(problem)
        raw = _read_bounded(fd)
    except OSError as exc:
        return Unreadable(f"cannot read preferences file: {exc.strerror or exc}")
    finally:
        os.close(fd)
    if len(raw) > MAX_PREFERENCES_BYTES:
        return Unreadable("file too large")
    return raw


def load_preferences(path: Path | None = None) -> SurveyPreferences | Unreadable:
    """Load ``feedback.json``; a missing file yields defaults. Never raises."""
    target = path if path is not None else preferences_path()
    raw = _read_trusted_bytes(target)
    if raw is None:
        return SurveyPreferences()
    if isinstance(raw, Unreadable):
        _LOG.debug("feedback preferences unreadable: %s", raw.reason)
        return raw
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("top-level value must be an object")
        return SurveyPreferences.from_dict(data)
    except (UnicodeDecodeError, ValueError) as exc:
        _LOG.debug("feedback preferences invalid: %s", exc)
        return Unreadable(f"invalid preferences file: {exc}")


def _ensure_private_dir(directory: Path) -> None:
    """Create *directory* as ``0700`` if missing; an existing directory keeps its mode.

    The config directory is shared with other per-user spec-kitty settings, so
    an existing one is not narrowed; the file-level ``0600`` protects this file.
    """
    try:
        directory.mkdir(parents=True, mode=_DIR_MODE)
    except FileExistsError:
        return
    if not is_windows():
        chmod_no_follow(directory, _DIR_MODE)


def save_preferences(path: Path, prefs: SurveyPreferences) -> bool:
    """Atomically persist *prefs* to *path* with owner-only permissions. Never raises.

    ``atomic_write`` stages the content in a ``tempfile.mkstemp`` file (created
    owner-only on POSIX) and renames it into place; the explicit
    ``chmod_no_follow(path, 0o600)`` afterwards pins the final mode regardless
    of platform defaults. On hosts where the staged file could briefly carry a
    wider mode, that window is acceptable because the file holds no personal
    data (only a flag, a timestamp, and an optional endpoint override).

    Returns:
        ``True`` on success; ``False`` if the parent or target is a symlink or
        any filesystem error occurs.
    """
    try:
        if path.parent.is_symlink() or path.is_symlink():
            _LOG.debug("refusing to write feedback preferences through a symlink")
            return False
        _ensure_private_dir(path.parent)
        atomic_write(path, json.dumps(prefs.to_dict(), sort_keys=True), mkdir=True)
        chmod_no_follow(path, _FILE_MODE)
    except (OSError, NoFollowPathError) as exc:
        _LOG.debug("feedback preferences write failed: %s", exc)
        return False
    return True


def set_automatic_prompts(enabled: bool, *, path: Path | None = None) -> bool:
    """Turn automatic Feedback Survey offers on or off. Never raises.

    Runs read-modify-write under the same machine lock as the offer claim. A
    short blocking wait is acceptable because this is an explicit user action,
    not a trigger. An unreadable file is replaced by fresh defaults plus the
    requested flag: the explicit user action repairs it.

    Returns:
        ``True`` when the new setting was persisted.
    """
    try:
        target = path if path is not None else preferences_path()
        with machine_file_lock(lock_path_for(target), blocking=True, timeout_s=_SET_PROMPTS_LOCK_TIMEOUT_S):
            current = load_preferences(target)
            base = SurveyPreferences() if isinstance(current, Unreadable) else current
            return save_preferences(target, replace(base, automatic_prompts=enabled))
    except Exception as exc:
        _LOG.debug("feedback set_automatic_prompts failed: %s", exc)
        return False
