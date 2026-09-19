"""Atomic filesystem I/O for the Decision Moment ledger.

Provides read/write helpers for ``index.json`` and ``DM-<id>.md`` artifacts
under ``kitty-specs/<mission-slug>/decisions/``.  All writes use the
``tempfile.NamedTemporaryFile`` + ``os.replace`` pattern (NFR-002).
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from kernel.errors import GuardedReadError
from kernel.meta_decode import MetaDecodeError, decode_meta
from specify_cli.decisions.models import (
    DecisionIndex,
    IndexEntry,
    OriginFlow,
)


__all__ = [
    "decisions_dir",
    "index_path",
    "artifact_path",
    "load_index",
    "save_index",
    "append_entry",
    "update_entry",
    "write_artifact",
    "find_by_logical_key",
    "DecisionIndexReadError",
]


class DecisionIndexReadError(GuardedReadError, RuntimeError):
    """Raised when ``decisions/index.json`` exists but cannot be decoded.

    Mirrors :class:`specify_cli.core.paths.MissionMetaReadError`: a
    fail-closed signal distinguishing a genuine *read failure* (malformed
    JSON, non-UTF-8 bytes, or a schema-invalid payload) from the benign
    *missing-file* case, which ``load_index`` still resolves to an empty
    :class:`~specify_cli.decisions.models.DecisionIndex`.

    Attributes:
        index_path: The path of the ``index.json`` that could not be decoded.
        cause: The underlying exception (``MetaDecodeError``, ``OSError``, or
            pydantic's ``ValidationError``).
    """

    def __init__(self, index_path: Path, cause: Exception) -> None:
        self.index_path = index_path
        self.cause = cause
        super().__init__(f"Cannot read {index_path}: {cause} — fail-closed (index.json exists but is corrupt or unreadable); run: spec-kitty doctor")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def decisions_dir(mission_dir: Path) -> Path:
    """Return the decisions sub-directory (does NOT create it)."""
    return mission_dir / "decisions"


def index_path(mission_dir: Path) -> Path:
    """Return the path to ``index.json``."""
    return decisions_dir(mission_dir) / "index.json"


def artifact_path(mission_dir: Path, decision_id: str) -> Path:
    """Return the path to ``DM-<decision_id>.md``."""
    return decisions_dir(mission_dir) / f"DM-{decision_id}.md"


# ---------------------------------------------------------------------------
# Index I/O
# ---------------------------------------------------------------------------


def load_index(mission_dir: Path) -> DecisionIndex:
    """Load and parse ``index.json``, returning an empty index if missing.

    Raises:
        DecisionIndexReadError: When ``index.json`` exists but is corrupt
            (malformed JSON, non-UTF-8 bytes, or schema-invalid) — fail-closed
            (FR-002/FR-004). Never raised for a missing file.
    """
    path = index_path(mission_dir)
    if not path.exists():
        return DecisionIndex(mission_id="", entries=())
    return _decode_index(path)


def _decode_index(path: Path) -> DecisionIndex:
    """Decode *path* into a :class:`DecisionIndex`, fail-closed on corruption.

    Reuses the canonical L1 kernel decoder (:func:`kernel.meta_decode.decode_meta`)
    for the bytes-to-JSON layer — malformed JSON and non-UTF-8 bytes both surface
    as :class:`~kernel.meta_decode.MetaDecodeError` there — and wraps pydantic's
    schema validation separately, so both failure classes present identically as
    :class:`DecisionIndexReadError`.
    """
    try:
        raw = decode_meta(path.read_bytes(), on_malformed="raise")
    except (MetaDecodeError, OSError) as exc:
        raise DecisionIndexReadError(path, exc) from exc

    try:
        return DecisionIndex.model_validate(raw)
    except ValidationError as exc:
        raise DecisionIndexReadError(path, exc) from exc


def save_index(mission_dir: Path, index: DecisionIndex) -> None:
    """Atomically write *index* to ``index.json``.

    Entries are sorted by ``(created_at, decision_id)`` ASC before serialization.
    Uses ``tmp-then-rename`` for atomicity.
    """
    d_dir = decisions_dir(mission_dir)
    d_dir.mkdir(parents=True, exist_ok=True)

    # Sort entries deterministically
    sorted_entries = sorted(
        index.entries,
        key=lambda e: (e.created_at.isoformat(), e.decision_id),
    )
    sorted_index = DecisionIndex(
        version=index.version,
        mission_id=index.mission_id,
        entries=tuple(sorted_entries),
    )

    payload = json.dumps(sorted_index.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"
    _atomic_write(d_dir, index_path(mission_dir), payload.encode("utf-8"))


def append_entry(mission_dir: Path, entry: IndexEntry) -> DecisionIndex:
    """Append *entry* to the index, sort, save, and return the updated index."""
    current = load_index(mission_dir)
    new_entries = tuple(current.entries) + (entry,)
    new_index = DecisionIndex(
        version=current.version,
        mission_id=entry.mission_id or current.mission_id,
        entries=new_entries,
    )
    save_index(mission_dir, new_index)
    return load_index(mission_dir)


def update_entry(mission_dir: Path, decision_id: str, **updates: object) -> DecisionIndex:
    """Replace the entry matching *decision_id* with updated fields.

    Raises ``KeyError`` if *decision_id* is not found.
    """
    current = load_index(mission_dir)
    matched = next((e for e in current.entries if e.decision_id == decision_id), None)
    if matched is None:
        raise KeyError(f"decision_id {decision_id!r} not found in index")

    replacement = matched.model_copy(update=updates)
    new_entries = tuple(replacement if e.decision_id == decision_id else e for e in current.entries)
    new_index = DecisionIndex(
        version=current.version,
        mission_id=current.mission_id,
        entries=new_entries,
    )
    save_index(mission_dir, new_index)
    return load_index(mission_dir)


# ---------------------------------------------------------------------------
# Artifact I/O
# ---------------------------------------------------------------------------


def write_artifact(mission_dir: Path, entry: IndexEntry) -> Path:
    """Render and atomically write ``DM-<decision_id>.md``.

    Returns the path to the written file.
    """
    d_dir = decisions_dir(mission_dir)
    d_dir.mkdir(parents=True, exist_ok=True)

    content = _render_artifact(entry)
    dest = artifact_path(mission_dir, entry.decision_id)
    _atomic_write(d_dir, dest, content.encode("utf-8"))
    return dest


def _render_artifact(entry: IndexEntry) -> str:
    """Render a DM markdown document for *entry*."""
    lines: list[str] = []

    lines.append(f"# Decision Moment `{entry.decision_id}`")
    lines.append("")
    lines.append(f"- **Mission:** `{entry.mission_slug}`")
    lines.append(f"- **Origin flow:** `{entry.origin_flow.value}`")
    if entry.step_id is not None:
        lines.append(f"- **Step id:** `{entry.step_id}`")
    if entry.slot_key is not None:
        lines.append(f"- **Slot key:** `{entry.slot_key}`")
    lines.append(f"- **Input key:** `{entry.input_key}`")
    lines.append(f"- **Status:** `{entry.status.value}`")
    lines.append(f"- **Created:** `{entry.created_at.isoformat()}`")
    if entry.resolved_at is not None:
        lines.append(f"- **Resolved:** `{entry.resolved_at.isoformat()}`")
    if entry.resolved_by is not None:
        lines.append(f"- **Resolved by:** `{entry.resolved_by}`")
    if entry.opened_by is not None:
        lines.append(f"- **Opened by:** `{entry.opened_by}`")
    lines.append(f"- **Other answer:** `{str(entry.other_answer).lower()}`")
    lines.append("")

    lines.append("## Question")
    lines.append("")
    lines.append(entry.question)
    lines.append("")

    lines.append("## Options")
    lines.append("")
    if entry.options:
        for opt in entry.options:
            lines.append(f"- {opt}")
    else:
        lines.append("_(none)_")
    lines.append("")

    lines.append("## Final answer")
    lines.append("")
    lines.append(entry.final_answer if entry.final_answer is not None else "_(none)_")
    lines.append("")

    lines.append("## Rationale")
    lines.append("")
    lines.append(entry.rationale if entry.rationale is not None else "_(none)_")
    lines.append("")

    lines.append("## Change log")
    lines.append("")
    lines.append(f"- `{entry.created_at.isoformat()}` — opened")
    if entry.resolved_at is not None and entry.status.value in ("resolved", "deferred", "canceled"):
        if entry.final_answer is not None:
            lines.append(f'- `{entry.resolved_at.isoformat()}` — {entry.status.value} (final_answer="{entry.final_answer}")')
        else:
            lines.append(f"- `{entry.resolved_at.isoformat()}` — {entry.status.value}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def find_by_logical_key(
    index: DecisionIndex,
    origin_flow: OriginFlow,
    step_id: str | None,
    slot_key: str | None,
    input_key: str,
) -> IndexEntry | None:
    """Return the most recent entry matching the logical key, or ``None``.

    The logical key is ``(origin_flow, step_id_or_slot_key, input_key)``.
    ``step_id`` is checked against ``entry.step_id``; ``slot_key`` against
    ``entry.slot_key``.  The caller should pass whichever one applies.
    """
    candidates: list[IndexEntry] = []
    for e in index.entries:
        if e.origin_flow != origin_flow:
            continue
        if e.input_key != input_key:
            continue
        # Match step_id path
        if step_id is not None and e.step_id == step_id:
            candidates.append(e)
            continue
        # Match slot_key path
        if slot_key is not None and e.slot_key == slot_key:
            candidates.append(e)

    if not candidates:
        return None
    return max(candidates, key=lambda e: (e.created_at.isoformat(), e.decision_id))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_write(directory: Path, dest: Path, data: bytes) -> None:
    """Write *data* to *dest* atomically via a temp file in *directory*."""
    fd, tmp_name = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, dest)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
