"""Writer protocol — the interface all harness-specific writers must satisfy.

Using ``runtime_checkable`` enables ``isinstance(obj, Writer)`` in tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..content import SessionPresenceContent

__all__ = ["Writer"]


@runtime_checkable
class Writer(Protocol):
    """Protocol for harness-specific session presence writers.

    All harness writers (e.g. ``ClaudeCodeWriter``) must implement this interface.
    The ``runtime_checkable`` decorator allows ``isinstance(obj, Writer)`` checks
    in tests without requiring a concrete base class.
    """

    harness_key: str

    def owned_paths(self) -> tuple[str, ...]:
        """Project-relative files this writer writes (empty for a writer that writes nothing)."""
        ...

    def can_write(self, project_root: Path) -> bool:
        """Return ``True`` when the harness is installed in this project."""
        ...

    def has_presence(self, project_root: Path) -> bool:
        """Return ``True`` when session presence is already written for this harness."""
        ...

    def write(self, project_root: Path, content: SessionPresenceContent) -> None:
        """Write the orientation block.

        Idempotent — safe to call when already present.
        """
        ...

    def remove(self, project_root: Path) -> None:
        """Remove the orientation block.

        No-op if not present.
        """
        ...
