"""Single authority in core for doc-kitty's frontmatter rules (#6929, ADR 2026-10-31-1 D-7/D-8).

doc-kitty (``spec-kitty/doc-kitty``) builds ``docs/`` into the docsite. The
migration (``dockitty_frontmatter_migration.py``), the ported readers
(``audience_resolver.py``, ``touched_set_gates.py``, ``related_validator.py``) and
their tests all need the same answers to the same questions:

* which folders the site leaves out (:data:`EXCLUDED_FOLDERS`);
* what a page's slug is, and which page a slug names (:func:`slug_of`,
  :func:`page_for_slug`), mirroring doc-kitty's ``readmeToIndexId``;
* whether a page is published (:func:`is_published`), mirroring doc-kitty's
  ``isDraftStatus`` (an absent ``doc_status`` is a draft);
* which persona page an ``audience`` profile names (:func:`persona_page`),
  mirroring doc-kitty's ``resolveProfile`` (``context/audience/<profile>``);
* which files are immutable history whose body may never change
  (:func:`is_immutable`), and where a file's body starts (:func:`body_of`).

They are answered here once, so no reader re-derives a slug or a folder list.
:data:`EXCLUDED_FOLDERS` is the list the doc-kitty site's ``exclude`` option must
carry; the site scaffold (#6930) takes it from here rather than copying it.

Standard library only (plus the shared frontmatter parser).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DRAFT_STATUS",
    "EXCLUDED_FOLDERS",
    "INDEX_BASENAMES",
    "PERSONA_ROOT",
    "body_of",
    "is_dated_adr",
    "is_excluded",
    "is_immutable",
    "is_published",
    "page_for_slug",
    "persona_page",
    "profile_of_persona_path",
    "slug_of",
    "split_frontmatter",
]

#: Docs folders the doc-kitty site leaves out (``exclude`` on ``defineDocKittyIntegrations``).
#: ``changelog/unreleased`` holds per-PR changelog fragments, which are not pages.
EXCLUDED_FOLDERS: Final[tuple[str, ...]] = ("archive", "reports", "convergence", "changelog/unreleased")

#: Section index basenames during the DocFX parallel run (ADR D-1: ``['README', 'index']``).
INDEX_BASENAMES: Final[tuple[str, ...]] = ("README", "index")

#: Personas live under ``docs/context/audience/``; a profile is a path below it.
PERSONA_ROOT: Final[str] = "context/audience"

#: doc-kitty's draft status; an absent ``doc_status`` counts as a draft.
DRAFT_STATUS: Final[str] = "draft"

_MD_SUFFIX: Final[str] = ".md"
_FENCE: Final[str] = "---"
_DATED_ADR: Final[re.Pattern[str]] = re.compile(r"^adr/\d+\.x/\d{4}-\d{2}-\d{2}-[^/]+\.md$")
_IMMUTABLE_PREFIXES: Final[tuple[str, ...]] = ("plans/", "reports/", "changelog/", "archive/")
_PERSONA_PATH: Final[re.Pattern[str]] = re.compile(r"^(?:\./|(?:\.\./)+|docs/)?context/audience/(?P<profile>.+)\.md$")


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split *text* into ``(frontmatter_block, body)`` or return ``None`` when it has none.

    ``frontmatter_block`` runs from the opening fence through the closing fence line,
    newline included; ``body`` is every character after it, byte for byte.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        return None
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") == _FENCE:
            return text[:offset], text[offset:]
    return None


def body_of(text: str) -> str:
    """Everything after the closing frontmatter fence (the whole text when there is none)."""
    parts = split_frontmatter(text)
    return text if parts is None else parts[1]


def _strip_md(rel: str) -> str:
    return rel[: -len(_MD_SUFFIX)] if rel.endswith(_MD_SUFFIX) else rel


def slug_of(rel_under_docs: str) -> str:
    """The doc-kitty slug of a page at *rel_under_docs* (``guides/x.md`` -> ``guides/x``).

    A trailing index basename is removed (``adr/4.x/index.md`` -> ``adr/4.x``); the
    docs root index has the empty slug. Case is preserved.
    """
    stem = _strip_md(rel_under_docs)
    head, _, last = stem.rpartition("/")
    if last in INDEX_BASENAMES:
        return head
    return stem


def is_excluded(rel_under_docs: str) -> bool:
    """True when *rel_under_docs* lies in a folder the site leaves out."""
    return any(rel_under_docs == folder or rel_under_docs.startswith(f"{folder}/") for folder in EXCLUDED_FOLDERS)


def page_for_slug(docs_root: Path, slug: str) -> Path | None:
    """The page a slug names: ``<slug>.md``, else ``<slug>/README.md``, else ``<slug>/index.md``."""
    clean = slug.strip("/")
    candidates = [f"{clean}{_MD_SUFFIX}"] if clean else []
    prefix = f"{clean}/" if clean else ""
    candidates += [f"{prefix}{name}{_MD_SUFFIX}" for name in INDEX_BASENAMES]
    for candidate in candidates:
        path = docs_root / candidate
        if path.is_file():
            return path
    return None


def is_published(rel_under_docs: str, frontmatter: Mapping[str, Any]) -> bool:
    """True when doc-kitty builds the page with drafts off: not excluded and not a draft."""
    if is_excluded(rel_under_docs):
        return False
    status = frontmatter.get("doc_status")
    return isinstance(status, str) and bool(status.strip()) and status.strip() != DRAFT_STATUS


def profile_of_persona_path(value: str) -> str | None:
    """The profile a persona path names (``docs/context/audience/internal/maintainer.md`` -> ``internal/maintainer``)."""
    match = _PERSONA_PATH.match(value.strip())
    return match.group("profile") if match else None


def persona_page(docs_root: Path, profile: str) -> Path | None:
    """The persona page a profile names, under ``docs/context/audience/``, or ``None``."""
    clean = profile.strip().strip("/")
    if not clean or ".." in clean.split("/"):
        return None
    return page_for_slug(docs_root, f"{PERSONA_ROOT}/{clean}")


def is_dated_adr(rel_under_docs: str) -> bool:
    """True for a dated ADR file (``adr/<era>/YYYY-MM-DD-*.md``); era index files are not ADRs."""
    return bool(_DATED_ADR.match(rel_under_docs))


def is_immutable(rel_under_docs: str) -> bool:
    """True for history whose body never changes: ADRs, plans, reports, changelog, archive."""
    if not rel_under_docs.endswith(_MD_SUFFIX):
        return False
    return is_dated_adr(rel_under_docs) or rel_under_docs.startswith(_IMMUTABLE_PREFIXES)
