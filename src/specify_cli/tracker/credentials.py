"""Tracker credential storage in ~/.spec-kitty/credentials."""

from __future__ import annotations

import contextlib
import json
import os
import tomllib
from pathlib import Path
from typing import Any

from kernel.locks import machine_file_lock
from kernel.no_follow import open_no_follow
from kernel.paths import is_windows

try:  # pragma: no cover - optional dependency
    import toml
except Exception:  # pragma: no cover - optional dependency
    toml = None  # type: ignore[assignment]


class TrackerCredentialError(RuntimeError):
    """Raised when credentials cannot be loaded or stored."""


def _tracker_root() -> Path:
    """Return the tracker state directory for the current platform.

    Both branches resolve through the unified ``get_runtime_root().base``, which
    honors ``SPEC_KITTY_HOME``.

    On Windows: the nested ``base/tracker`` directory (``RuntimeRoot.tracker_dir``).
    On POSIX: ``base`` directly (flat layout — credentials land at
    ``base/credentials``). This preserves the historical
    ``~/.spec-kitty/credentials`` location when ``SPEC_KITTY_HOME`` is unset
    (NFR-001 / research.md D3); the POSIX-flat vs Windows-nested divergence is
    intentional.
    """
    from specify_cli.paths import get_runtime_root  # noqa: PLC0415

    root = get_runtime_root()
    # ``Path(...)`` re-narrows to ``Path`` because subdir mypy runs treat the
    # ``specify_cli.*`` lazy import as ``Any`` (``follow_imports = "skip"``).
    if is_windows():
        return Path(root.tracker_dir)
    return Path(root.base)


def _credentials_path() -> Path:
    return _tracker_root() / "credentials"


def _credentials_lock_path(path: Path) -> Path:
    """Return the dedicated SIDECAR lock path for the credentials payload.

    The lock is a separate lock-only file (kernel.locks G1) so the payload
    file itself is never opened under the OS lock -- reading/writing the
    credentials file happens as an ordinary unlocked open while this
    process holds the sidecar, structurally ruling out the #4703 "reading a
    payload through a held mandatory lock" hazard.
    """
    return path.with_name(path.name + ".lock")


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def _write_toml(payload: dict[str, Any]) -> str:
    if toml is not None:  # pragma: no branch
        return str(toml.dumps(payload))

    lines: list[str] = []

    def emit_table(prefix: str, table: dict[str, Any]) -> None:
        lines.append(f"[{prefix}]")
        scalar_keys = sorted(key for key, value in table.items() if not isinstance(value, dict))
        nested_keys = sorted(key for key, value in table.items() if isinstance(value, dict))

        for key in scalar_keys:
            lines.append(f"{key} = {_toml_scalar(table[key])}")

        for key in nested_keys:
            lines.append("")
            emit_table(f"{prefix}.{key}", table[key])

    root_scalar_keys = sorted(key for key, value in payload.items() if not isinstance(value, dict))
    root_table_keys = sorted(key for key, value in payload.items() if isinstance(value, dict))

    for key in root_scalar_keys:
        lines.append(f"{key} = {_toml_scalar(payload[key])}")

    for key in root_table_keys:
        if lines:
            lines.append("")
        emit_table(key, payload[key])

    return ("\n".join(lines).rstrip() + "\n") if lines else ""


def _write_credentials_file(path: Path, content: str) -> None:
    """Write *content* to *path*, owner-only from the moment it exists.

    Mission ``local-write-safety-01M2ZPZD`` WP06 / #4760: the previous
    ``Path.write_text`` + trailing ``os.chmod(0o600)`` left a window where
    the file briefly existed at whatever mode the process umask granted
    (measured ``0o644``) before the ``chmod`` narrowed it. A fresh,
    uniquely-named temp file is created here via ``O_CREAT|O_EXCL|O_WRONLY``
    at mode ``0o600`` through :func:`kernel.no_follow.open_no_follow` (WP01's
    canonical no-follow primitive) -- the mode applies atomically at
    creation, so there is no window and no trailing ``chmod`` call at all.
    ``Path.replace`` then swaps it onto *path* atomically; ``rename(2)``
    never dereferences a symlink at the destination, it replaces the
    directory entry itself, so a symlink planted at *path* is never written
    through.

    The temp name is unique per call (pid + random suffix, mirroring
    ``kernel.yaml_io.write_mapping_atomic``'s pattern) so ``O_EXCL`` never
    collides with a concurrent writer's own temp file or a leftover from an
    earlier crash.
    """
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{os.urandom(4).hex()}")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = open_no_follow(tmp_path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise
    tmp_path.replace(path)


class TrackerCredentialStore:
    """Store tracker provider credentials under the platform runtime root."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _credentials_path()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        try:
            with machine_file_lock(_credentials_lock_path(self.path), blocking=True):
                raw = self.path.read_text(encoding="utf-8")
            payload = tomllib.loads(raw) if raw.strip() else {}
        except Exception as exc:  # pragma: no cover - defensive
            raise TrackerCredentialError(f"Failed to load credentials: {exc}") from exc

        return payload if isinstance(payload, dict) else {}

    def save(self, payload: dict[str, Any]) -> None:
        try:
            if self.path == _credentials_path():
                # Only the default (production) location shares the
                # ``~/.spec-kitty``-rooted directory ``ensure_runtime_root``
                # owns -- an explicitly injected ``path`` (test isolation,
                # or any other caller-chosen location) is a directory this
                # store does not own and must not chmod/mkdir on its behalf.
                from specify_cli.paths import ensure_runtime_root  # noqa: PLC0415

                ensure_runtime_root()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            content = _write_toml(payload)
            with machine_file_lock(_credentials_lock_path(self.path), blocking=True):
                _write_credentials_file(self.path, content)
        except Exception as exc:  # pragma: no cover - defensive
            raise TrackerCredentialError(f"Failed to save credentials: {exc}") from exc

    def get_provider(self, provider: str) -> dict[str, Any]:
        payload = self.load()
        tracker = payload.get("tracker") if isinstance(payload, dict) else None
        providers = tracker.get("providers") if isinstance(tracker, dict) else None
        provider_payload = providers.get(provider) if isinstance(providers, dict) else None
        return dict(provider_payload) if isinstance(provider_payload, dict) else {}

    def set_provider(self, provider: str, values: dict[str, Any]) -> None:
        payload = self.load()
        tracker = payload.setdefault("tracker", {})
        if not isinstance(tracker, dict):
            tracker = {}
            payload["tracker"] = tracker

        providers = tracker.setdefault("providers", {})
        if not isinstance(providers, dict):
            providers = {}
            tracker["providers"] = providers

        providers[provider] = {str(key): value for key, value in values.items() if str(key).strip() and value is not None and str(value).strip()}
        self.save(payload)

    def clear_provider(self, provider: str) -> None:
        payload = self.load()
        tracker = payload.get("tracker") if isinstance(payload, dict) else None
        providers = tracker.get("providers") if isinstance(tracker, dict) else None
        if not isinstance(providers, dict) or provider not in providers:
            return

        del providers[provider]
        self.save(payload)
