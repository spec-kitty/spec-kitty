"""Nag-cache for the upgrade-nag throttle subsystem.

Public surface
--------------
NagCacheRecord  -- frozen dataclass representing one persisted cache entry.
NagCache        -- class with ``default()`` classmethod and ``read`` / ``write`` methods.

Security properties enforced here
-----------------------------------
CHK006  File mode 0o600; parent dir 0o700.
CHK007  No PII in cache records (no paths, usernames, machine IDs).
CHK009  Symlink-resistant: every open is preceded by ``os.lstat``; symlinks at the
        file path or parent dir cause read/write to return ``None`` silently.
CHK010  Parent-dir symlink check mirrors the file-path check.
CHK023  File ownership validated against ``os.geteuid()`` on POSIX.
CHK044  Clock-skew: negative delta in ``is_fresh`` is treated as "expired".
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kernel.clock import UTC, datetime, parse_iso
from kernel.paths import is_windows

_LOG = logging.getLogger(__name__)

_MAX_FILE_BYTES: int = 65_536  # 64 KiB defensive bound
_CACHE_FILE_NAME: str = "upgrade-nag.json"
_VALID_LATEST_SOURCES: frozenset[str] = frozenset({"pypi", "simple_index", "none"})


# ---------------------------------------------------------------------------
# NagCacheRecord
# ---------------------------------------------------------------------------


SnoozeStep = Literal["24h", "48h", "7d"]
_VALID_SNOOZE_STEPS: frozenset[str] = frozenset({"24h", "48h", "7d"})


@dataclass(frozen=True)
class NagCacheRecord:
    """One persisted upgrade-nag cache entry.

    Attributes:
        cli_version_key: The installed CLI version string at the time this
            record was written.  Used to invalidate the cache when the CLI
            is upgraded (FR-025).
        latest_version: The latest version string returned by the provider,
            or ``None`` when the provider could not determine one.
        latest_source: Where ``latest_version`` came from.  ``"pypi"`` for a
            successful public-PyPI lookup; ``"simple_index"`` for a successful
            PEP 503 simple-index lookup; ``"none"`` otherwise.
        fetched_at: UTC datetime when the latest-version lookup completed.
        last_shown_at: UTC datetime when the nag was last displayed to the
            user, or ``None`` if it has never been shown.
        remote_version_seen: Remote version that anchors the snooze cadence.
            When this differs from the planner's current latest_version, the
            cadence resets.
        snooze_step: Current position in the cadence ladder
            (``"24h" → "48h" → "7d"``).  ``None`` means no snooze active.
        snoozed_until: UTC datetime; while ``now < snoozed_until`` the
            prompt is suppressed.  ``None`` means no snooze active.
        always_upgrade: User picked "Always keep me up to date".  When True
            the coordinator attempts auto-upgrade on every invocation iff
            the installer is on the safe whitelist.
        never_ask: User picked "Never ask again".  Suppresses the prompt
            indefinitely until a new ``remote_version_seen`` is observed.

    No PII is stored in this record (CHK007, CHK048, CHK050).  In particular,
    no user paths, project slugs, hostnames, or other user-identifying
    information is included.

    Backward read-compat (WS3 / mission upgrade-readiness-ux-01KS7PS4):
    The new fields (``remote_version_seen``, ``snooze_step``,
    ``snoozed_until``, ``always_upgrade``, ``never_ask``) are all optional
    at deserialisation time.  ``from_dict`` accepts legacy JSON that
    contains only the original five fields and assigns safe defaults
    (None / False).  Readers MUST NOT crash on legacy entries.
    """

    cli_version_key: str
    latest_version: str | None
    latest_source: Literal["pypi", "simple_index", "none"]
    fetched_at: datetime
    last_shown_at: datetime | None
    remote_version_seen: str | None = None
    snooze_step: SnoozeStep | None = None
    snoozed_until: datetime | None = None
    always_upgrade: bool = False
    never_ask: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialise the record to a JSON-compatible dict with ISO-8601 UTC strings."""
        return {
            "cli_version_key": self.cli_version_key,
            "latest_version": self.latest_version,
            "latest_source": self.latest_source,
            "fetched_at": _dt_to_iso(self.fetched_at),
            "last_shown_at": _dt_to_iso(self.last_shown_at) if self.last_shown_at is not None else None,
            "remote_version_seen": self.remote_version_seen,
            "snooze_step": self.snooze_step,
            "snoozed_until": _dt_to_iso(self.snoozed_until) if self.snoozed_until is not None else None,
            "always_upgrade": self.always_upgrade,
            "never_ask": self.never_ask,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> NagCacheRecord:
        """Deserialise a record from a JSON-compatible dict.

        Accepts legacy JSON that omits the WS3 fields and assigns defaults.

        Args:
            data: Mapping as returned by ``json.loads``.

        Returns:
            A new :class:`NagCacheRecord`.

        Raises:
            KeyError: If a required (legacy) field is absent.
            ValueError: If a field has an unexpected type or value.
        """
        cli_version_key = _require_str(data, "cli_version_key")
        latest_version = _optional_str(data, "latest_version")
        latest_source_raw = _require_str(data, "latest_source")
        if latest_source_raw not in _VALID_LATEST_SOURCES:
            raise ValueError(f"latest_source must be 'pypi', 'simple_index', or 'none', got {latest_source_raw!r}")
        latest_source = _coerce_latest_source(latest_source_raw)
        fetched_at = _iso_to_dt(_require_str(data, "fetched_at"))
        last_shown_at_raw = _optional_str(data, "last_shown_at")
        last_shown_at = _iso_to_dt(last_shown_at_raw) if last_shown_at_raw is not None else None

        # WS3 extensions — all optional with safe defaults for legacy files.
        remote_version_seen = _optional_str(data, "remote_version_seen")
        snooze_step = _parse_snooze_step(data.get("snooze_step"))
        snoozed_until_raw = _optional_str(data, "snoozed_until")
        snoozed_until = _iso_to_dt(snoozed_until_raw) if snoozed_until_raw is not None else None
        always_upgrade = _require_bool(data, "always_upgrade", default=False)
        never_ask = _require_bool(data, "never_ask", default=False)

        return cls(
            cli_version_key=cli_version_key,
            latest_version=latest_version,
            latest_source=latest_source,
            fetched_at=fetched_at,
            last_shown_at=last_shown_at,
            remote_version_seen=remote_version_seen,
            snooze_step=snooze_step,
            snoozed_until=snoozed_until,
            always_upgrade=always_upgrade,
            never_ask=never_ask,
        )


def _optional_str(data: dict[str, object], key: str) -> str | None:
    raw_value = data.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        return raw_value
    raise ValueError(f"{key} must be str or null, got {type(raw_value)}")


def _coerce_latest_source(raw: str) -> Literal["pypi", "simple_index", "none"]:
    """Map a validated source token to the Literal type."""
    if raw == "pypi":
        return "pypi"
    if raw == "simple_index":
        return "simple_index"
    return "none"


def _parse_snooze_step(raw_value: object) -> SnoozeStep | None:
    if raw_value is None:
        return None
    if raw_value not in _VALID_SNOOZE_STEPS:
        raise ValueError(f"snooze_step must be one of {sorted(_VALID_SNOOZE_STEPS)} or null, got {raw_value!r}")
    if raw_value == "24h":
        return "24h"
    if raw_value == "48h":
        return "48h"
    return "7d"


def _require_bool(data: dict[str, object], key: str, *, default: bool) -> bool:
    raw_value = data.get(key, default)
    if isinstance(raw_value, bool):
        return raw_value
    raise ValueError(f"{key} must be bool, got {type(raw_value)}")


# ---------------------------------------------------------------------------
# NagCache
# ---------------------------------------------------------------------------


class NagCache:
    """Persistent cache for the upgrade-nag throttle.

    Use :meth:`default` to obtain an instance pointed at the standard
    per-user cache location.  In tests, construct directly with a custom
    ``path`` to avoid touching the real user cache.

    Args:
        path: Full path to the JSON cache file (e.g. ``~/.cache/spec-kitty/upgrade-nag.json``).
    """

    def __init__(self, path: Path) -> None:
        """Initialise with a concrete file path."""
        self._path = path

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> NagCache:
        """Return a :class:`NagCache` pointed at the standard per-user cache location.

        Cache directory resolution (in order):
        1. ``platformdirs.user_cache_dir("spec-kitty")`` if *platformdirs* is importable.
        2. Manual XDG / OS-specific fallback:
           - Linux/other: ``$XDG_CACHE_HOME/spec-kitty`` (or ``~/.cache/spec-kitty``).
           - macOS: ``~/Library/Caches/spec-kitty``.
           - Windows: ``%LOCALAPPDATA%\\spec-kitty\\Cache``.

        Returns:
            A :class:`NagCache` instance.
        """
        cache_dir = _resolve_cache_dir()
        return cls(Path(cache_dir) / _CACHE_FILE_NAME)

    # ------------------------------------------------------------------
    # Instance methods
    # ------------------------------------------------------------------

    def read(self) -> NagCacheRecord | None:
        """Read and deserialise the cache record from disk.

        Security checks performed before any read (all refusals return ``None``):
        - Symlink at ``path`` or its parent → refuse (CHK009, CHK010).
        - File size > 64 KiB → refuse.
        - File ownership ≠ ``os.geteuid()`` on POSIX → refuse (CHK023).
        - Any JSON / field parse error → refuse.

        Returns:
            The :class:`NagCacheRecord` if present and valid, or ``None``.
        """
        path = self._path
        try:
            parent_st = os.lstat(path.parent)
        except OSError:
            return None  # parent doesn't exist → no cache

        if stat.S_ISLNK(parent_st.st_mode):
            _LOG.debug("NagCache.read: parent dir is a symlink — refusing (CHK010)")
            return None

        try:
            file_st = os.lstat(path)
        except OSError:
            return None  # file doesn't exist → no cache

        if stat.S_ISLNK(file_st.st_mode):
            _LOG.debug("NagCache.read: cache file is a symlink — refusing (CHK009)")
            return None

        if file_st.st_size > _MAX_FILE_BYTES:
            _LOG.debug("NagCache.read: cache file too large (%d bytes) — refusing", file_st.st_size)
            return None

        if sys.platform != "win32":
            euid = os.geteuid()
            if file_st.st_uid != euid:
                _LOG.debug(
                    "NagCache.read: file owned by uid %d, current euid %d — refusing (CHK023)",
                    file_st.st_uid,
                    euid,
                )
                return None
            # Check that mode is 0o600 (owner read+write only).
            file_mode = stat.S_IMODE(file_st.st_mode)
            if file_mode != 0o600:
                _LOG.debug(
                    "NagCache.read: file mode %04o != 0o600 — refusing (CHK006)",
                    file_mode,
                )
                return None

        try:
            with open(path, encoding="utf-8") as fh:  # noqa: PTH123
                raw = fh.read(_MAX_FILE_BYTES + 1)
        except OSError:
            return None

        if len(raw) > _MAX_FILE_BYTES:
            _LOG.debug("NagCache.read: read content too large — refusing")
            return None

        try:
            data: object = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            _LOG.debug("NagCache.read: JSON parse error — refusing")
            return None

        if not isinstance(data, dict):
            _LOG.debug("NagCache.read: top-level JSON is not an object — refusing")
            return None

        try:
            return NagCacheRecord.from_dict(data)
        except (KeyError, ValueError, TypeError):
            _LOG.debug("NagCache.read: field validation error — refusing", exc_info=True)
            return None

    def write(self, record: NagCacheRecord) -> None:
        """Serialise and persist a cache record to disk.

        Security properties:
        - Parent dir created with mode 0o700 if absent (CHK006).
        - Refuses to write if parent dir is a symlink (CHK010).
        - Refuses to write if the target path is a symlink (CHK009).
        - Writes are failure-atomic: payload is written to a same-directory
          temp file, flushed, then promoted with ``os.replace``.
        - On POSIX: temp file opened with mode 0o600.
        - On Windows: same-directory temp file + best-effort ``os.chmod(0o600)``.

        All refusals are silent (no exception raised); a debug-level log entry
        is emitted.

        Args:
            record: The :class:`NagCacheRecord` to persist.
        """
        path = self._path
        parent = path.parent

        # Ensure parent exists.
        try:
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            _LOG.debug("NagCache.write: could not create parent dir: %s", exc)
            return

        # Symlink check on parent.
        try:
            parent_st = os.lstat(parent)
        except OSError as exc:
            _LOG.debug("NagCache.write: lstat parent failed: %s", exc)
            return

        if stat.S_ISLNK(parent_st.st_mode):
            _LOG.debug("NagCache.write: parent dir is a symlink — refusing (CHK010)")
            return

        # Symlink check on the file itself (if it already exists).
        try:
            file_st = os.lstat(path)
            if stat.S_ISLNK(file_st.st_mode):
                _LOG.debug("NagCache.write: cache file is a symlink — refusing (CHK009)")
                return
        except OSError:
            pass  # File doesn't exist yet — that's fine.

        payload = json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=True)

        if is_windows():
            _write_windows(path, payload)
        else:
            _write_posix(path, payload)

    # ------------------------------------------------------------------
    # Pure predicates (no I/O)
    # ------------------------------------------------------------------

    @staticmethod
    def has_fresh_data(
        record: NagCacheRecord | None,
        *,
        throttle_seconds: int,
        now: datetime,
        current_cli_version: str,
    ) -> bool:
        """Return True iff the cached version data is recent enough to trust.

        Used by the planner to decide whether to skip the provider call.
        Distinct from :meth:`is_fresh`, which gates nag display via
        ``last_shown_at``.

        Cache data is considered fresh when:
        - ``record`` is not ``None``, AND
        - ``record.cli_version_key`` matches ``current_cli_version`` (FR-025
          invalidation when the CLI is upgraded), AND
        - ``(now - record.fetched_at)`` is in ``[0, throttle_seconds)``
          (negative delta treated as expired for clock-skew safety; CHK044).

        This predicate answers "should we skip the network call?", whereas
        :meth:`is_fresh` answers "should we suppress the nag display?".  The
        two are intentionally separate:

        * A user who is fully up-to-date has no nag to show and
          ``last_shown_at`` stays ``None`` forever — yet the version data
          is still fresh enough to skip the provider.
        * :meth:`has_fresh_data` checks ``fetched_at``; :meth:`is_fresh`
          checks ``last_shown_at``.

        This is a pure function: it performs no I/O.  Inject ``now`` for
        deterministic testing.

        Args:
            record: The cache record to evaluate, or ``None``.
            throttle_seconds: The configured throttle window in seconds.
            now: The current UTC datetime (caller-supplied for testability).
            current_cli_version: The currently installed CLI version string.

        Returns:
            ``True`` if the cached version data is fresh and the provider
            call can be skipped; ``False`` otherwise.
        """
        if record is None:
            return False
        if record.cli_version_key != current_cli_version:
            return False
        delta = (now - record.fetched_at).total_seconds()
        if delta < 0:
            # Clock skew — treat as expired (CHK044).
            return False
        return delta < throttle_seconds

    @staticmethod
    def is_fresh(
        record: NagCacheRecord | None,
        *,
        throttle_seconds: int,
        now: datetime,
        current_cli_version: str,
    ) -> bool:
        """Return ``True`` iff the cache is fresh and the nag should be suppressed.

        This is a pure function: it performs no I/O.  Inject ``now`` for
        deterministic testing.

        Logic (returns ``False`` at the first failing condition):
        1. ``record is None`` → ``False`` (no cache).
        2. ``record.cli_version_key != current_cli_version`` → ``False``
           (CLI was upgraded since the record was written; FR-025).
        3. ``record.last_shown_at is None`` → ``False`` (nag never shown yet).
        4. ``delta < 0`` → ``False`` (clock moved backward; CHK044).
        5. ``delta >= throttle_seconds`` → ``False`` (window elapsed; boundary is expired).
        6. Otherwise → ``True`` (fresh; suppress nag).

        Args:
            record: The cache record to evaluate, or ``None``.
            throttle_seconds: The configured throttle window in seconds.
            now: The current UTC datetime (caller-supplied for testability).
            current_cli_version: The currently installed CLI version string.

        Returns:
            ``True`` if the nag should be suppressed, ``False`` otherwise.
        """
        if record is None:
            return False
        if record.cli_version_key != current_cli_version:
            return False
        if record.last_shown_at is None:
            return False
        delta = (now - record.last_shown_at).total_seconds()
        if delta < 0:
            # Clock skew — treat as expired (CHK044).
            return False
        return delta < throttle_seconds


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_cache_dir() -> str:
    """Resolve the per-user cache directory for spec-kitty."""
    try:
        from platformdirs import user_cache_dir  # type: ignore[import-untyped,unused-ignore]

        return str(user_cache_dir("spec-kitty"))  # type: ignore[no-untyped-call,unused-ignore]
    except ImportError:
        pass

    # Manual XDG / OS-specific fallback.
    if sys.platform == "darwin":
        return str(Path.home() / "Library" / "Caches" / "spec-kitty")
    if is_windows():
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return str(Path(local_app_data) / "spec-kitty" / "Cache")
        return str(Path.home() / "AppData" / "Local" / "spec-kitty" / "Cache")
    # Linux / WSL / other POSIX.
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = xdg if xdg else str(Path.home() / ".cache")
    return str(Path(base) / "spec-kitty")


def _dt_to_iso(dt: datetime) -> str:
    """Serialise a datetime to an ISO-8601 UTC string."""
    if dt.tzinfo is None:
        # Assume UTC if naive.
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _iso_to_dt(s: str) -> datetime:
    """Parse an ISO-8601 UTC string to a timezone-aware datetime.

    Args:
        s: An ISO-8601 string (e.g. ``"2026-04-27T12:00:00+00:00"``).

    Returns:
        A timezone-aware :class:`datetime` in UTC.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    dt = parse_iso(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _require_str(data: dict[str, object], key: str) -> str:
    """Extract a required string field from a dict.

    Args:
        data: Source mapping.
        key: Field name.

    Returns:
        The string value.

    Raises:
        KeyError: If the key is absent.
        ValueError: If the value is not a ``str``.
    """
    val = data[key]
    if not isinstance(val, str):
        raise ValueError(f"Field {key!r} must be str, got {type(val)}")
    return val


def _write_posix(path: Path, payload: str) -> None:
    """Write *payload* to *path* on POSIX via same-directory atomic replace."""
    tmp_path: Path | None = None
    fd = -1
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        os.chmod(str(tmp_path), 0o600)
        _write_all(fd, payload.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(str(tmp_path), str(path))
        tmp_path = None
        _fsync_parent_dir(path.parent)
    except OSError as exc:
        _LOG.debug("NagCache.write: POSIX write failed: %s", exc)
    finally:
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def _write_windows(path: Path, payload: str) -> None:
    """Write *payload* to *path* on Windows via same-directory atomic replace."""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as fh:
            tmp_path = Path(fh.name)
            fh.write(payload)
            fh.flush()
            with contextlib.suppress(OSError):
                os.fsync(fh.fileno())
        with contextlib.suppress(OSError):
            os.chmod(str(tmp_path), 0o600)
        os.replace(str(tmp_path), str(path))
        tmp_path = None
    except OSError as exc:
        _LOG.debug("NagCache.write: Windows write failed: %s", exc)
    finally:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def _write_all(fd: int, data: bytes) -> None:
    """Write all bytes to ``fd`` or raise on zero-length/failed writes."""
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written == 0:
            raise OSError("short write")
        offset += written


def _fsync_parent_dir(parent: Path) -> None:
    """Best-effort directory fsync so the replace is durable on POSIX."""
    fd = -1
    try:
        fd = os.open(str(parent), os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
