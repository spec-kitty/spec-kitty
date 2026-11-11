"""Test-only path-read oracle for :class:`runtime.next.board_status.BoardStatus`.

Production builds a board only from a status read door surface
(:func:`runtime.next.board_status.board_status_from_surface`). The tests also need a board read
straight from a Mission directory, to prove the helpers' ``status_dir=`` Path forms and the
``board=`` form agree. That path read lives here, not in ``src``, so production keeps exactly
one way to build a board. It shares the production reduction (``_board_from_stream``) and parses
with the parser the door uses for a path source.
"""

from __future__ import annotations

from pathlib import Path

from runtime.next.board_status import BoardStatus, _board_from_stream
from specify_cli.status import read_event_stream

PATH_SOURCE = "path"
"""The ``source`` of a board built from a Mission directory (not a door source)."""


def board_status_from_dir(feature_dir: Path) -> BoardStatus:
    """Build the board from a Mission directory. Raises ``StoreError`` on a corrupt line."""
    return _board_from_stream(
        read_event_stream(feature_dir),
        has_log=(feature_dir / "status.events.jsonl").exists(),
        source=PATH_SOURCE,
        where=str(feature_dir),
    )
