"""Packaged schema + query store for the Common Docs retrieval index.

Mission ``common-docs-query`` closes the retrieval gap for Common Docs
(``docs/``): the existing page-inventory (``docs/development/page-inventory.yaml``,
owned by ``scripts/docs/_inventory.py::PageInventoryEntry``) carries version/
ownership metadata but no title, heading-anchor, or abstract index, so agents
resort to globbing the tree.

This module is the **packaged half** of a deliberate two-module split
(``data-model.md`` "Module layering"): ``scripts/`` is not shipped in the
wheel (see ``pyproject.toml`` ``[tool.hatch.build.targets.wheel]``), so the
installed ``spec-kitty`` CLI cannot import ``scripts.*``. Every symbol the CLI
needs at runtime — the schema, the deterministic renderer/parser, the drift
comparator, and the in-memory query store — therefore lives here, in a
packaged module with **no import of anything under ``scripts``**. The build-
tooling generator (``scripts/docs/docs_index.py``) imports these symbols
*down* (``scripts -> src``, legal); the reverse direction is forbidden.

This module intentionally does **not** import or widen
``scripts.docs._inventory.PageInventoryEntry`` (C-001): the retrieval index is
a new, separate, sibling artifact with its own schema, not an enrichment of
the page-inventory lockfile.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

__all__ = [
    "Anchor",
    "DEFAULT_INDEX_PATH",
    "DivioType",
    "DocsIndexStore",
    "DocsQueryEntry",
    "IndexDrift",
    "compare_index",
    "parse_index",
    "render_index",
]


DEFAULT_INDEX_PATH: Final[str] = "docs/development/docs-retrieval-index.yaml"

_INDEX_HEADER: Final[str] = (
    "# GENERATED — do not edit by hand; run scripts/docs/docs_index.py --write "
    "to refresh.\n"
    "# Common Docs retrieval index: title / heading-anchor / abstract per page.\n"
    "# Sorted alphabetically by `path` for a deterministic, byte-stable diff.\n"
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class DivioType(StrEnum):
    """Divio documentation class for a Common Docs page.

    The canonical enum for the docs-retrieval subsystem, packaged so both the
    CLI (``spec-kitty docs query --divio-type``) and the generator
    (``scripts/docs/docs_index.py``) validate/coerce against one source. Its
    values intentionally mirror ``scripts/docs/_inventory.py::DivioType`` (the
    page-inventory's enum, left untouched under C-001); the docs-query subsystem
    keeps its own packaged copy because ``scripts/`` is not shipped in the wheel
    and ``src → scripts`` imports are forbidden.
    """

    TUTORIAL = "tutorial"
    HOW_TO = "how-to"
    REFERENCE = "reference"
    EXPLANATION = "explanation"
    NONE = "none"


@dataclass(slots=True, frozen=True)
class Anchor:
    """One heading (``##``/``###``) anchor within a docs page.

    ``slug`` is the canonical ``slugify`` output of ``text``, disambiguated
    with an ordinal suffix for duplicate headings within the same page (see
    ``scripts/docs/docs_index.py::slug_for_headings``). Anchors are source-
    heading slugs, not DocFX-exact rendered fragments (C-005).
    """

    slug: str
    text: str
    level: int


@dataclass(slots=True, frozen=True)
class DocsQueryEntry:
    """One row of the generated retrieval index — one per ``docs/**/*.md`` page.

    Deliberately a *separate* schema from ``PageInventoryEntry`` (C-001): the
    two artifacts are siblings, not variants of the same row.
    """

    path: str
    title: str
    divio_type: str
    anchors: tuple[Anchor, ...]
    abstract: str


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _quote(value: str) -> str:
    """Render ``value`` as a byte-stable, JSON-quoted YAML scalar.

    Docs titles/abstracts/heading text are arbitrary prose (colons, quotes,
    unicode) that would break a hand-rolled *unquoted* scalar. JSON is a
    syntactic subset of YAML, so this stays valid YAML while being immune to
    scalar-escaping ambiguity (mirrors ``inventory_lockfile.py::_render_notes``).
    """
    return json.dumps(value, ensure_ascii=False)


def _render_anchor(anchor: Anchor) -> str:
    return (
        f"{{slug: {_quote(anchor.slug)}, text: {_quote(anchor.text)}, "
        f"level: {anchor.level}}}"
    )


def _render_entry(entry: DocsQueryEntry) -> str:
    anchors_block = (
        " []"
        if not entry.anchors
        else "\n" + "\n".join(f"    - {_render_anchor(a)}" for a in entry.anchors)
    )
    return (
        f"  - path: {_quote(entry.path)}\n"
        f"    title: {_quote(entry.title)}\n"
        f"    divio_type: {_quote(entry.divio_type)}\n"
        f"    abstract: {_quote(entry.abstract)}\n"
        f"    anchors:{anchors_block}\n"
    )


def render_index(entries: Iterable[DocsQueryEntry]) -> str:
    """Render entries to a deterministic, byte-stable YAML index string.

    Hand-rolled (rather than a YAML dumper) so the byte layout is fully under
    our control and stable across ``ruamel``/``PyYAML`` versions — mirrors
    ``inventory_lockfile.py::render_lockfile``. Entries are (defensively)
    sorted by ``path`` regardless of input order (NFR-001).
    """
    ordered = sorted(entries, key=lambda entry: entry.path)
    chunks: list[str] = [_INDEX_HEADER, "pages:\n"]
    chunks.extend(_render_entry(entry) for entry in ordered)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _anchor_from_mapping(raw: Mapping[str, Any]) -> Anchor:
    level_raw = raw.get("level", 2)
    try:
        level = int(level_raw)
    except (TypeError, ValueError):
        level = 2
    return Anchor(
        slug=str(raw.get("slug", "")),
        text=str(raw.get("text", "")),
        level=level,
    )


def _entry_from_mapping(raw: Mapping[str, Any]) -> DocsQueryEntry:
    raw_anchors = raw.get("anchors") or []
    anchors = tuple(
        _anchor_from_mapping(raw_anchor)
        for raw_anchor in raw_anchors
        if isinstance(raw_anchor, Mapping)
    )
    return DocsQueryEntry(
        path=str(raw.get("path", "")),
        title=str(raw.get("title", "")),
        divio_type=str(raw.get("divio_type", "")),
        anchors=anchors,
        abstract=str(raw.get("abstract", "")),
    )


def parse_index(text: str) -> list[DocsQueryEntry]:
    """Parse a rendered index string back into ``DocsQueryEntry`` rows.

    Inverse of :func:`render_index`. Tolerant of a *structurally* degenerate
    document -- an empty string, a non-mapping root, a missing ``pages:`` key,
    or a non-list ``pages`` all yield ``[]`` rather than raising, so a stale or
    empty committed file cannot crash the drift check.

    A *syntactically* invalid YAML document (an unterminated scalar, leftover
    merge markers, a truncated write) is NOT swallowed -- ``ruamel`` raises a
    ``YAMLError``, which callers surface as a clean read/parse error (e.g. the
    ``docs query`` CLI reports it without a traceback). "Degenerate but valid"
    and "corrupt/unparseable" are deliberately different outcomes.
    """
    if not text.strip():
        return []
    yaml = YAML(typ="safe")
    loaded: Any = yaml.load(text)
    if not isinstance(loaded, Mapping):
        return []
    raw_pages = loaded.get("pages")
    if not isinstance(raw_pages, list):
        return []
    return [
        _entry_from_mapping(raw_entry)
        for raw_entry in raw_pages
        if isinstance(raw_entry, Mapping)
    ]


# ---------------------------------------------------------------------------
# Drift comparison
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class IndexDrift:
    """Structured difference between a committed index and a fresh regeneration.

    Mirrors ``inventory_lockfile.py::InventoryDrift``. ``has_drift`` is the
    RED signal the freshness gate (WP02) asserts on.
    """

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def has_drift(self) -> bool:
        """True iff the regeneration diverges from the committed index."""
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        """One-line human summary of the drift."""
        return (
            f"added={len(self.added)} removed={len(self.removed)} "
            f"changed={len(self.changed)}"
        )


def _entry_fingerprint(
    entry: DocsQueryEntry,
) -> tuple[str, str, str, tuple[tuple[str, str, int], ...]]:
    """Order-independent value fingerprint of an entry (excludes ``path``)."""
    return (
        entry.title,
        entry.divio_type,
        entry.abstract,
        tuple((anchor.slug, anchor.text, anchor.level) for anchor in entry.anchors),
    )


def compare_index(committed: str, regenerated: str) -> IndexDrift:
    """Compare a committed index string against a freshly regenerated one.

    Both arguments are rendered index text (not entry lists) per the WP01
    contract; each side is parsed independently before diffing by ``path``.
    """
    committed_by_path = {entry.path: entry for entry in parse_index(committed)}
    regenerated_by_path = {entry.path: entry for entry in parse_index(regenerated)}

    added = sorted(set(regenerated_by_path) - set(committed_by_path))
    removed = sorted(set(committed_by_path) - set(regenerated_by_path))
    changed = sorted(
        path
        for path in set(regenerated_by_path) & set(committed_by_path)
        if _entry_fingerprint(regenerated_by_path[path])
        != _entry_fingerprint(committed_by_path[path])
    )
    return IndexDrift(added=tuple(added), removed=tuple(removed), changed=tuple(changed))


# ---------------------------------------------------------------------------
# In-memory query store
# ---------------------------------------------------------------------------


def _matches_term(entry: DocsQueryEntry, normalized_term: str) -> bool:
    """True iff ``normalized_term`` appears in the entry's searchable text."""
    if normalized_term in entry.title.lower():
        return True
    if normalized_term in entry.abstract.lower():
        return True
    return any(
        normalized_term in anchor.text.lower() or normalized_term in anchor.slug.lower()
        for anchor in entry.anchors
    )


class DocsIndexStore:
    """In-memory, load-once query store over the generated retrieval index.

    Loaded once at CLI entry (``DocsIndexStore.load``); ``query`` filters the
    already-parsed entries in memory — no per-query filesystem walk (NFR-002).
    """

    __slots__ = ("_entries",)

    def __init__(self, entries: Sequence[DocsQueryEntry]) -> None:
        self._entries: tuple[DocsQueryEntry, ...] = tuple(entries)

    @property
    def entries(self) -> tuple[DocsQueryEntry, ...]:
        """The full, path-ordered set of loaded entries."""
        return self._entries

    @classmethod
    def load(cls, index_path: Path | None = None) -> DocsIndexStore:
        """Load and parse the generated index file at ``index_path``.

        Defaults to :data:`DEFAULT_INDEX_PATH` resolved against the current
        working directory (mirrors the inventory loader convention).
        """
        path = index_path if index_path is not None else Path(DEFAULT_INDEX_PATH)
        text = path.read_text(encoding="utf-8")
        return cls(parse_index(text))

    def query(
        self,
        term: str,
        *,
        divio_type: str | None = None,
        section: str | None = None,
    ) -> list[DocsQueryEntry]:
        """Return entries matching ``term`` (case-insensitive substring).

        ``term`` matches ``title`` OR any anchor ``text``/``slug`` OR
        ``abstract``. ``divio_type`` and ``section`` (an anchor slug) are
        optional AND-ed filters. Results preserve index (path-sorted) order.

        Raises ``ValueError`` for an empty/whitespace-only ``term`` — the CLI
        requires a non-empty search term.
        """
        normalized = term.strip().lower()
        if not normalized:
            raise ValueError("query term must not be empty")

        results: list[DocsQueryEntry] = []
        for entry in self._entries:
            if divio_type is not None and entry.divio_type != divio_type:
                continue
            if section is not None and not any(
                anchor.slug == section for anchor in entry.anchors
            ):
                continue
            if _matches_term(entry, normalized):
                results.append(entry)
        return results
