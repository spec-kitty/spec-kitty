"""The checked-in migration execution-order manifest (ADR 2026-10-17-1 §2).

``migrations/order_manifest.txt`` is the single authority for execution order.
Each content line is a ``migration_id``; blank lines and ``#``-only lines are
ignored. A trailing ``# tie: <reason>`` marks an intentional equal-
``target_version`` adjacency; a trailing ``# runs-first: <reason>`` marks the
one entry that leads regardless of its version. The build-time gate
(``tests/architectural/test_migration_order_manifest.py``) enforces the rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The canonical manifest path, beside the migration modules it orders.
MANIFEST_PATH = Path(__file__).parent / "migrations" / "order_manifest.txt"

_TIE_PREFIX = "tie:"
_RUNS_FIRST_PREFIX = "runs-first:"


@dataclass(frozen=True)
class ManifestEntry:
    """One parsed manifest line."""

    id: str
    tie_reason: str | None
    runs_first_reason: str | None
    line_no: int


def _split_comment(line: str) -> tuple[str, str | None]:
    """Split a line into (code, comment) on the first ``#``; comment is sans ``#``, stripped."""
    code, sep, comment = line.partition("#")
    return code.strip(), (comment.strip() if sep else None)


def _annotation(comment: str | None, prefix: str) -> str | None:
    if comment is None or not comment.startswith(prefix):
        return None
    return comment[len(prefix) :].strip()


def parse_entry(line: str, line_no: int) -> ManifestEntry | None:
    """Parse one line into a :class:`ManifestEntry`, or ``None`` for blank/comment lines."""
    code, comment = _split_comment(line)
    if not code:
        return None
    return ManifestEntry(
        id=code,
        tie_reason=_annotation(comment, _TIE_PREFIX),
        runs_first_reason=_annotation(comment, _RUNS_FIRST_PREFIX),
        line_no=line_no,
    )


def load_manifest_entries(path: Path | None = None) -> list[ManifestEntry]:
    """Parse the manifest into ordered :class:`ManifestEntry` rows."""
    text = (path or MANIFEST_PATH).read_text(encoding="utf-8")
    entries: list[ManifestEntry] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        entry = parse_entry(line, line_no)
        if entry is not None:
            entries.append(entry)
    return entries


def load_order_manifest(path: Path | None = None) -> list[str]:
    """The ordered ``migration_id`` list (annotations stripped)."""
    return [entry.id for entry in load_manifest_entries(path)]
