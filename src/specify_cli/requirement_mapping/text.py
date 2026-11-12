"""Resolve the requirement IDs a work package cites to their declared text.

FR-010 / FR-011 / NFR-003. The review prompt shows each cited ID with the
text its Mission's ``spec.md`` declares, so a reviewer need not re-read the
spec. A citation is never dropped: an undeclared or malformed ID, a citation
of another Mission and an ambiguous declaration each get an explicit
:class:`Resolution`.

This module adds no declaration parser (#3481: the repository already has
two definitions of "declares", and a third is rejected). Where an ID is
declared, and in which shape, comes only from
:func:`specify_cli.requirement_mapping._declaration_occurrences`; ambiguity
comes only from :func:`specify_cli.requirement_mapping.duplicate_declared_ids`.
The code below reads the line it is pointed at and cleans its text up
(escaped pipes, markup, the success-criterion trailer); it never decides
what counts as declared.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from specify_cli.requirement_mapping import _declaration_occurrences, duplicate_declared_ids, grammar

__all__ = [
    "TEXT_LIMIT",
    "TRUNCATION_MARKER",
    "CitedRequirement",
    "Resolution",
    "resolve_requirement_texts",
]

#: Maximum characters of a resolved text, the ``ID — `` prefix included (NFR-003).
TEXT_LIMIT = 600

#: Appended to a text cut at :data:`TEXT_LIMIT`. One character (three UTF-8
#: bytes) so twenty maximum-length citations stay within 12 KiB (NFR-003).
TRUNCATION_MARKER = "…"

_SEPARATOR = " — "
_TITLE_SEPARATOR = ": "

#: Shape tags as ``_declaration_occurrences`` reports them.
_SHAPE_TABLE = "table"
_SHAPE_HEADING = "heading"

#: A cell boundary: a pipe not escaped with a backslash.
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")

#: The success-criterion trailer, ``— [build] · no-op passable: no`` and longer variants.
_SC_TRAILER = re.compile(r"\s+—\s+\[[a-z-]+\](?:\s*·.*)?$")

#: Markup and separator left right after the lead ID (``**: ``, `` — ``, ``~~ :``).
_LEAD_RESIDUE = re.compile(r"^(?:\*\*|~~)*\s*(?:[:—–-](?=\s|$))?\s*")

#: Bold and strike-through markers.
_EMPHASIS = re.compile(r"\*\*|~~")

#: A line that ends a paragraph: a heading, a table line or a new list item.
_BLOCK_BREAK = re.compile(r"^\s*(?:#|\||(?:[-*]|\d+\.)\s)")


class Resolution(StrEnum):
    """How a cited requirement ID resolved against the Mission's spec."""

    DECLARED = "declared"
    NOT_DECLARED = "not_declared"
    OTHER_MISSION = "other_mission"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CitedRequirement:
    """One cited ID and its resolution; ``text`` is set only when ``DECLARED``."""

    ref: str
    resolution: Resolution
    text: str | None = None

    def __post_init__(self) -> None:
        if self.text is not None and self.resolution is not Resolution.DECLARED:
            raise ValueError(f"text is only carried by a DECLARED citation, not {self.resolution.value}")


@dataclass(frozen=True)
class _SpecIndex:
    """The spec read once: first declaring site per ID, duplicates, blanked lines."""

    first_site: dict[str, tuple[int, str]]
    duplicates: frozenset[str]
    lines: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]


def resolve_requirement_texts(
    spec_text: str,
    refs: Iterable[str],
    *,
    mission_type: str = "software-dev",
) -> tuple[CitedRequirement, ...]:
    """Resolve each cited ref, in citation order, once per resolved ref."""
    index = _index_spec(spec_text, mission_type=mission_type)
    results: list[CitedRequirement] = []
    seen: set[str] = set()
    for token in refs:
        cited = _resolve_one(token, index, mission_type=mission_type)
        if cited.ref in seen:
            continue
        seen.add(cited.ref)
        results.append(cited)
    return tuple(results)


def _index_spec(spec_text: str, *, mission_type: str) -> _SpecIndex:
    first_site: dict[str, tuple[int, str]] = {}
    for req_id, line_no, shape, _block in _declaration_occurrences(spec_text, mission_type=mission_type):
        first_site.setdefault(req_id, (line_no, shape))
    return _SpecIndex(
        first_site=first_site,
        duplicates=frozenset(duplicate_declared_ids(spec_text, mission_type=mission_type)),
        lines=tuple(grammar.blank_html_comments(spec_text).splitlines()),
        patterns=grammar.declared_shape_patterns(mission_type),
    )


def _resolve_one(token: str, index: _SpecIndex, *, mission_type: str) -> CitedRequirement:
    rid = grammar.parse(token, mission_type=mission_type)
    if rid is None:
        return CitedRequirement(ref=token, resolution=Resolution.NOT_DECLARED)
    if rid.mission is not None:
        return CitedRequirement(ref=str(rid), resolution=Resolution.OTHER_MISSION)
    ref = rid.canonical
    if ref in index.duplicates:
        return CitedRequirement(ref=ref, resolution=Resolution.AMBIGUOUS)
    site = index.first_site.get(ref)
    if site is None:
        return CitedRequirement(ref=ref, resolution=Resolution.NOT_DECLARED)
    line_no, shape = site
    if shape == _SHAPE_TABLE:
        raw = _table_row_text(ref, index.lines[line_no - 1], index.patterns[0])
    else:
        raw = _block_text(ref, index.lines, line_no - 1, index.patterns, heading=shape == _SHAPE_HEADING)
    return CitedRequirement(ref=ref, resolution=Resolution.DECLARED, text=_truncate(" ".join(raw.split())))


def _table_row_text(ref: str, line: str, table_row: re.Pattern[str]) -> str:
    """``ID — Title: statement`` from the cells after the ID cell."""
    match = table_row.match(line)
    rest = line[match.end() :] if match is not None else ""
    cells = [cell.replace("\\|", "|").strip() for cell in _UNESCAPED_PIPE.split(rest)]
    while cells and not cells[-1]:
        cells.pop()
    if len(cells) >= 2:
        return f"{ref}{_SEPARATOR}{cells[0]}{_TITLE_SEPARATOR}{cells[1]}"
    return _join(ref, cells[0] if cells else "")


def _block_text(
    ref: str,
    lines: Sequence[str],
    start: int,
    patterns: Sequence[re.Pattern[str]],
    *,
    heading: bool,
) -> str:
    """The declaring line's statement plus its paragraph, trailer stripped."""
    lead = _after_lead_id(lines[start], patterns)
    if heading:
        body = " ".join(_paragraph(lines, _skip_blank(lines, start + 1)))
        if lead and body:
            return f"{ref}{_SEPARATOR}{lead}{_TITLE_SEPARATOR}{body}"
        return _join(ref, lead or body)
    statement = " ".join([lead, *_paragraph(lines, start + 1)])
    return _join(ref, _strip_trailer(_EMPHASIS.sub("", statement)))


def _after_lead_id(line: str, patterns: Sequence[re.Pattern[str]]) -> str:
    """The text after the lead ID the shape pattern matched, markup removed."""
    for pattern in patterns:
        match = pattern.match(line)
        if match is not None:
            rest = _LEAD_RESIDUE.sub("", line[match.end(1) :], count=1)
            return _EMPHASIS.sub("", rest).strip()
    return ""  # unreachable in practice: the index recorded this line because one of *patterns* matched it


def _skip_blank(lines: Sequence[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _paragraph(lines: Sequence[str], index: int) -> list[str]:
    """Lines from ``index`` until a blank line, heading, table line or list item."""
    collected: list[str] = []
    while index < len(lines) and lines[index].strip() and not _BLOCK_BREAK.match(lines[index]):
        collected.append(lines[index].strip())
        index += 1
    return collected


def _strip_trailer(text: str) -> str:
    return _SC_TRAILER.sub("", " ".join(text.split()))


def _join(ref: str, statement: str) -> str:
    statement = statement.strip()
    return f"{ref}{_SEPARATOR}{statement}" if statement else ref


def _truncate(text: str) -> str:
    if len(text) <= TEXT_LIMIT:
        return text
    return text[:TEXT_LIMIT] + TRUNCATION_MARKER
