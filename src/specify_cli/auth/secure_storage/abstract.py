"""Abstract base class for secure auth session storage.

The only supported persisted backend is the encrypted local file store under
``~/.spec-kitty/auth/``. Windows keeps a tiny alias class for platform-focused
tests, but the underlying persistence model is the same on every OS.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..session import StoredSession


class SecureStorage(ABC):
    """Abstract storage backend for :class:`StoredSession`.

    Concrete backends must implement read/write/delete plus the
    ``backend_name`` property (used for diagnostic display and to populate
    ``StoredSession.storage_backend``).
    """

    @abstractmethod
    def read(self) -> StoredSession | None:
        """Return the persisted session, or ``None`` if no session exists."""

    @abstractmethod
    def write(self, session: StoredSession) -> None:
        """Persist ``session`` to the backend, overwriting any previous value."""

    @abstractmethod
    def delete(self) -> None:
        """Delete the persisted session if present. Must be idempotent."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the backend identifier (matches ``StoredSession.storage_backend``)."""

    @classmethod
    def from_environment(cls) -> SecureStorage:
        """Return the canonical encrypted file-backed storage backend."""
        from kernel.paths import is_windows  # noqa: PLC0415 — deferred so callers can monkeypatch kernel.paths.is_windows

        if is_windows():
            from .windows_storage import WindowsFileStorage  # noqa: PLC0415

            return WindowsFileStorage()

        from .file_fallback import FileFallbackStorage  # noqa: PLC0415

        return FileFallbackStorage()
