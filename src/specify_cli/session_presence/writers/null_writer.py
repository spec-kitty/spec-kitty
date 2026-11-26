"""NullWriter — no-op Writer for harnesses with no known orientation mechanism."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from specify_cli.session_presence.content import SessionPresenceContent

__all__ = ["NullWriter"]

_logger = logging.getLogger(__name__)


@dataclass
class NullWriter:
    """Writer stub for harnesses with no known orientation mechanism.

    Returned by ``get_writer()`` for any unregistered harness key.
    Logs at DEBUG level so callers can trace which keys fall through.
    """

    harness_key: str

    def owned_paths(self) -> tuple[str, ...]:
        """No files: NullWriter never writes anything."""
        return ()

    def can_write(self, _project_root: Path) -> bool:
        """Always returns ``False`` — NullWriter never writes anything."""
        return False

    def has_presence(self, _project_root: Path) -> bool:
        """Always returns ``False`` — NullWriter never writes anything."""
        return False

    def write(self, _project_root: Path, _content: SessionPresenceContent) -> None:
        """No-op — log at DEBUG and return."""
        _logger.debug(
            "NullWriter: no orientation mechanism for harness %s",
            self.harness_key,
        )

    def remove(self, _project_root: Path) -> None:
        """No-op."""
