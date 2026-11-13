"""Frontmatter migration that lets doc-kitty build ``docs/`` (#6929, ADR 2026-10-31-1 D-7/D-8).

Four rewrites, each frontmatter-only, each idempotent:

* **audience** — a persona path (``docs/context/audience/internal/maintainer.md``,
  scalar or list) becomes doc-kitty's profile list
  ``[{profile: internal/maintainer, guidance_text: …}]``. A free-text value keeps its
  text as the profile.
* **ADRs** — every dated ADR gains ``doc_status`` (``Accepted``/``Proposed`` ->
  ``active``, ``Superseded`` -> ``superseded``) and ``kind: ADR``; ``status``,
  ``date`` and ``superseded_by`` are untouched.
* **related** — an entry naming a published page becomes that page's slug. Anything
  else (a path outside ``docs/``, a non-Markdown file, a draft or excluded page) moves
  to ``external_references`` as a repository URL; an entry whose target no longer
  exists is dropped and reported.
* **D-7 fields** (#6931) — every page gains the ``kind`` doc-kitty requires
  (:func:`resolve_kind`: ``Hub`` for a section index, the Divio ``type`` folded in,
  else :data:`KIND_BY_PATH` / :data:`KIND_BY_PATH_PREFIX`; a page no rule classifies
  aborts the run); a Divio ``type`` line is removed, because doc-kitty reads ``type``
  as the section; a legacy ``doc_status`` is normalised (:func:`normalise_doc_status`);
  ``updated`` is written as a UTC instant, an ADR without one taking it from ``date``
  (:func:`normalise_updated`).

How it edits: only the ``audience``/``related`` blocks and the ``doc_status``/
``updated`` lines are replaced, the ``doc_status``/``kind``/``updated``/
``external_references`` lines inserted and a Divio ``type`` line removed; every other
line, and every character after the closing fence, is kept as it is. Each rewrite is
re-parsed and compared key by key, and any difference outside the intended keys aborts.

Usage::

    python -m scripts.docs.dockitty_frontmatter_migration --check
    python -m scripts.docs.dockitty_frontmatter_migration --apply
    python -m scripts.docs.dockitty_frontmatter_migration --verify-against origin/main
    python -m scripts.docs.dockitty_frontmatter_migration --validate

Kept for the migration and its re-runs (a later conflict with another docs PR is
resolved by re-running ``--apply``); dropped with the other migration-era tools once no
docs pull request needs a re-run (ADR D-6).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

from scripts.docs._dockitty_contract import (
    DRAFT_FOLDERS,
    INDEX_BASENAMES,
    FrontmatterFindings,
    body_of,
    format_instant,
    is_dated_adr,
    is_excluded,
    is_published,
    page_for_slug,
    parse_instant,
    persona_page,
    profile_of_persona_path,
    slug_of,
    split_frontmatter,
    validate_frontmatter,
)
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._page_scope import iter_docs_pages

__all__ = [
    "ADR_DOC_STATUS",
    "ADR_KIND",
    "DIVIO_TYPE_TO_KIND",
    "DOC_STATUS_ALIASES",
    "DRAFT_SECTIONS",
    "HUB_KIND",
    "KIND_BY_PATH",
    "KIND_BY_PATH_PREFIX",
    "Corpus",
    "MigrationError",
    "MigrationIntegrityError",
    "MigrationReport",
    "build_parser",
    "is_skipped",
    "main",
    "migrate_text",
    "migrate_tree",
    "normalise_doc_status",
    "normalise_updated",
    "resolve_kind",
    "validate_tree",
    "verify_against",
]

#: MADR ``status`` -> doc-kitty ``doc_status`` (ADR D-7; ruling 5: Proposed stays published).
ADR_DOC_STATUS: Final[Mapping[str, str]] = {"Accepted": "active", "Proposed": "active", "Superseded": "superseded"}
ADR_KIND: Final[str] = "ADR"

#: ADR D-7: a section index is a hub over its pages.
HUB_KIND: Final[str] = "Hub"

#: ADR D-7: the Divio ``type`` values fold into doc-kitty's ``kind`` (``type`` names the section there).
DIVIO_TYPE_TO_KIND: Final[Mapping[str, str]] = {
    "tutorial": "Tutorial",
    "how-to": "How-To",
    "reference": "Reference",
    "explanation": "Explanation",
}

#: ADR D-7, "the rest are classified in the migration step": pages with no Divio
#: ``type`` and no index or ADR role take the kind of their section. The longest
#: matching prefix wins; a page no row (and no :data:`KIND_BY_PATH` entry) matches
#: aborts the run instead of being guessed.
KIND_BY_PATH_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("plans/", "Planning"),
    ("changelog/", "Changelog"),
    ("api/", "Reference"),
    ("configuration/", "Reference"),
    ("contracts/", "Reference"),
    ("development/reference/", "Reference"),
    ("guides/how-to/", "How-To"),
    ("guides/tutorials/", "Tutorial"),
    ("architecture/", "Explanation"),
    ("context/", "Explanation"),
    ("migrations/", "How-To"),
    ("operations/", "How-To"),
)

#: Single pages outside every section of :data:`KIND_BY_PATH_PREFIX`.
#: ``retrospective-learning-loop.md`` is the redirect stub of an architecture page.
KIND_BY_PATH: Final[Mapping[str, str]] = {"retrospective-learning-loop.md": "Explanation"}

#: ADR D-7: the legacy ``doc_status`` values and their canonical replacements.
DOC_STATUS_ALIASES: Final[Mapping[str, str]] = {"closeout": "durable", "point_in_time": "durable", "proposal": "draft"}

#: ADR D-8: these subtrees take ``doc_status: draft`` and are not published. A legacy
#: value there becomes ``draft``, not the ``durable`` of :data:`DOC_STATUS_ALIASES`,
#: which would publish pages the operator ruled unpublished. Derived from the contract's
#: :data:`~scripts.docs._dockitty_contract.DRAFT_FOLDERS`, the one authority (#6932, C-002).
DRAFT_SECTIONS: Final[tuple[str, ...]] = tuple(f"{folder}/" for folder in DRAFT_FOLDERS)

_AUDIENCE: Final[str] = "audience"
_RELATED: Final[str] = "related"
_EXTERNAL: Final[str] = "external_references"
_DOC_STATUS: Final[str] = "doc_status"
_KIND: Final[str] = "kind"
_STATUS: Final[str] = "status"
_TITLE: Final[str] = "title"
_TYPE: Final[str] = "type"
_UPDATED: Final[str] = "updated"
_DATE: Final[str] = "date"
_DRAFT: Final[str] = "draft"
_ISO_DATE: Final[re.Pattern[str]] = re.compile(r"\d{4}-\d{2}-\d{2}")
_INDEX_BASENAMES_FOLDED: Final[frozenset[str]] = frozenset(f"{name.lower()}.md" for name in INDEX_BASENAMES)
_DOCS_PREFIX: Final[str] = "docs/"
_LEGACY_INDEX_FILE: Final[str] = "index.md"
_README_FILE: Final[str] = "README.md"
_REPO_URL: Final[str] = "https://github.com/spec-kitty/spec-kitty"
_PERSONA_TITLE_PREFIXES: Final[tuple[str, ...]] = ("Stakeholder Persona: ",)
_INTENDED_KEYS: Final[frozenset[str]] = frozenset({_AUDIENCE, _RELATED, _EXTERNAL, _DOC_STATUS, _KIND, _UPDATED, _TYPE})

#: The migration never edits the excluded folders
#: (:data:`scripts.docs._dockitty_contract.EXCLUDED_FOLDERS`): doc-kitty never reads them,
#: its gates skip them (ADR D-8), and they are immutable history, part of it byte-pinned
#: by ``tests/architectural/test_archive_root_byte_identical.py``. The four files #6928
#: resolved left the tree; their folders' ``README.md`` is the section index again since
#: #6939 and is migrated like any page.
#:
#: The ADR era ``README.md`` pages ARE migrated: their table rows are bot-owned, their
#: frontmatter is not (``check_generated_docs_untouched.py`` refuses only new table rows).


class MigrationError(RuntimeError):
    """A page cannot be migrated mechanically (fail closed)."""


class MigrationIntegrityError(MigrationError):
    """A rewrite changed something other than the intended frontmatter keys."""


@dataclass(slots=True)
class MigrationReport:
    """What a run changed (or would change)."""

    changed_files: list[str] = field(default_factory=list)
    audience_files: int = 0
    adr_files: int = 0
    related_files: int = 0
    external_references: int = 0
    kind_files: int = 0
    doc_status_files: int = 0
    updated_files: int = 0
    type_files: int = 0
    dropped_references: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """JSON shape of the report."""
        return {
            "changed_files": len(self.changed_files),
            "audience_files": self.audience_files,
            "adr_files": self.adr_files,
            "related_files": self.related_files,
            "external_references": self.external_references,
            "kind_files": self.kind_files,
            "doc_status_files": self.doc_status_files,
            "updated_files": self.updated_files,
            "type_files": self.type_files,
            "dropped_references": self.dropped_references,
        }


def _published_after_migration(rel: str, data: Mapping[str, Any]) -> bool:
    """Whether a page is published once the ADR rule has given an ADR its ``doc_status``."""
    if is_dated_adr(rel) and _DOC_STATUS not in data and isinstance(data.get(_STATUS), str):
        mapped = ADR_DOC_STATUS.get(data[_STATUS])
        if mapped is not None:
            return is_published(rel, {**data, _DOC_STATUS: mapped})
    return is_published(rel, data)


@dataclass(frozen=True, slots=True)
class _Source:
    """The page whose ``related`` list is being migrated, read from its own frontmatter."""

    rel: str
    published: bool

    @classmethod
    def of(cls, rel: str, data: Mapping[str, Any]) -> _Source:
        return cls(rel=rel, published=_published_after_migration(rel, data))


@dataclass(frozen=True, slots=True)
class Corpus:
    """The docs tree as the rules need it: every page's frontmatter, keyed by path under ``docs/``."""

    docs_root: Path
    repo_root: Path
    frontmatter: Mapping[str, Mapping[str, Any]]

    @classmethod
    def load(cls, *, docs_root: Path, repo_root: Path) -> Corpus:
        """Read every ``docs/**/*.md`` page's frontmatter."""
        pages: dict[str, Mapping[str, Any]] = {}
        for path in sorted(docs_root.rglob("*.md")):
            rel = path.relative_to(docs_root).as_posix()
            pages[rel] = parse_frontmatter(path.read_text(encoding="utf-8"))
        return cls(docs_root=docs_root, repo_root=repo_root, frontmatter=pages)

    def published(self, rel: str) -> bool:
        """Whether the page at *rel* is published once the migration has run."""
        return _published_after_migration(rel, self.frontmatter.get(rel, {}))

    def related_target_allowed(self, source: _Source, target: str) -> bool:
        """Whether *source* may name *target* in ``related`` (doc-kitty resolves it in every build that builds *source*).

        A draft source is built in a drafts-on preview, where draft targets exist but
        excluded ones never do. A published source is built with drafts off, so its
        target must be published. (Pages in excluded folders are never migrated.)
        """
        if not source.published:
            return not is_excluded(target)
        return self.published(target)

    def title(self, rel: str) -> str:
        """The page's title, or its path when it has none."""
        value = self.frontmatter.get(rel, {}).get(_TITLE)
        return value.strip() if isinstance(value, str) and value.strip() else f"docs/{rel}"

    def persona_name(self, profile: str) -> str | None:
        """The reader-facing persona name for *profile*, or ``None`` when no persona page exists."""
        page = persona_page(self.docs_root, profile)
        if page is None:
            return None
        title = self.title(page.relative_to(self.docs_root).as_posix())
        for prefix in _PERSONA_TITLE_PREFIXES:
            title = title.removeprefix(prefix)
        return title


# ---------------------------------------------------------------------------
# Rules: old value -> new value (pure, idempotent)
# ---------------------------------------------------------------------------


def _audience_entry(value: str, corpus: Corpus) -> dict[str, str]:
    text = value.strip()
    profile = profile_of_persona_path(text) or text
    name = corpus.persona_name(profile)
    guidance = f"Written for the {name} reader." if name else f"Written for {profile}."
    return {"profile": profile, "guidance_text": guidance}


def migrate_audience(value: object, corpus: Corpus) -> object:
    """Rule for ``audience``: path strings become ``{profile, guidance_text}`` entries."""
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list):
        raise MigrationError(f"audience is neither a string nor a list: {value!r}")
    entries: list[object] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            entries.append(_audience_entry(item, corpus))
        elif isinstance(item, Mapping):
            entries.append(dict(item))
        else:
            raise MigrationError(f"audience entry is not a persona path or profile: {item!r}")
    return entries


def adr_fields(rel: str, frontmatter: Mapping[str, Any]) -> dict[str, str]:
    """Rule for ADRs: the ``doc_status`` and ``kind`` a dated ADR must carry (empty for other pages)."""
    if not is_dated_adr(rel):
        return {}
    status = frontmatter.get(_STATUS)
    mapped = ADR_DOC_STATUS.get(status) if isinstance(status, str) else None
    if mapped is None:
        raise MigrationError(f"{rel}: ADR status {status!r} has no doc_status mapping")
    for key, wanted in ((_DOC_STATUS, mapped), (_KIND, ADR_KIND)):
        present = frontmatter.get(key)
        if present is not None and present != wanted:
            raise MigrationError(f"{rel}: {key} is {present!r}, expected {wanted!r} for status {status!r}")
    return {_DOC_STATUS: mapped, _KIND: ADR_KIND}


def _is_index(rel: str) -> bool:
    return rel.rsplit("/", 1)[-1].lower() in _INDEX_BASENAMES_FOLDED


def resolve_kind(rel: str, frontmatter: Mapping[str, Any]) -> str:
    """Rule for ``kind``: the authored value, else the first rule that classifies the page.

    Order: an authored ``kind``; a dated ADR (``ADR``); a section index (``Hub``); a
    Divio ``type`` (:data:`DIVIO_TYPE_TO_KIND`); :data:`KIND_BY_PATH`; the longest row
    of :data:`KIND_BY_PATH_PREFIX`. A page none of them classifies is refused (ADR D-7:
    "any page left unclassified is a migration failure").
    """
    authored = frontmatter.get(_KIND)
    if isinstance(authored, str) and authored:
        return authored
    if is_dated_adr(rel):
        return ADR_KIND
    if _is_index(rel):
        return HUB_KIND
    divio = frontmatter.get(_TYPE)
    if isinstance(divio, str) and divio in DIVIO_TYPE_TO_KIND:
        return DIVIO_TYPE_TO_KIND[divio]
    if rel in KIND_BY_PATH:
        return KIND_BY_PATH[rel]
    matches = [(len(prefix), kind) for prefix, kind in KIND_BY_PATH_PREFIX if rel.startswith(prefix)]
    if not matches:
        raise MigrationError(f"{rel}: no rule classifies this page's kind; add it to KIND_BY_PATH or KIND_BY_PATH_PREFIX")
    return max(matches)[1]


def normalise_doc_status(rel: str, frontmatter: Mapping[str, Any]) -> object:
    """Rule for a non-ADR ``doc_status``: a legacy value becomes canonical; anything else is kept.

    In a :data:`DRAFT_SECTIONS` subtree a legacy value becomes ``draft`` (ADR D-8);
    elsewhere it follows :data:`DOC_STATUS_ALIASES` (ADR D-7). A canonical value, an
    absent one and an unknown one are returned as they are (doc-kitty warns on the
    unknown one; the migration does not guess).
    """
    current = frontmatter.get(_DOC_STATUS)
    if not isinstance(current, str) or current not in DOC_STATUS_ALIASES:
        return current
    if rel.startswith(DRAFT_SECTIONS):
        return _DRAFT
    return DOC_STATUS_ALIASES[current]


def _instant_from_adr_date(rel: str, value: object) -> str:
    instant = parse_instant(value)
    if instant is not None:
        return format_instant(instant.moment)
    dates = _ISO_DATE.findall(value) if isinstance(value, str) else []
    named = [parse_instant(found) for found in dates]
    moments = [instant.moment for instant in named if instant is not None]
    if not moments:
        raise MigrationError(f"{rel}: ADR has no updated and its date {value!r} names no date")
    return format_instant(max(moments))


def normalise_updated(rel: str, frontmatter: Mapping[str, Any]) -> str | None:
    """Rule for ``updated``: the canonical UTC instant (``YYYY-MM-DDTHH:MM:SSZ``).

    A present value is respelled (a date-only value becomes midnight UTC); one that is
    not an instant is refused. A dated ADR with no ``updated`` takes its ``date``; a
    ``date`` holding prose with amendment dates takes the latest date it names (ADR
    D-7: "ADRs from ``date``"). Any other page without ``updated`` stays without one.
    """
    current = frontmatter.get(_UPDATED)
    if current is not None:
        instant = parse_instant(current)
        if instant is None:
            raise MigrationError(f"{rel}: updated {current!r} is not an instant")
        return format_instant(instant.moment)
    if is_dated_adr(rel):
        return _instant_from_adr_date(rel, frontmatter.get(_DATE))
    return None


def _d7_changes(rel: str, data: Mapping[str, Any], report: MigrationReport) -> dict[str, Any]:
    """The ``kind``/``doc_status``/``updated``/``type`` keys this page needs changed (#6931)."""
    intended: dict[str, Any] = {}
    if not is_dated_adr(rel):  # a dated ADR's kind and doc_status belong to adr_fields
        kind = resolve_kind(rel, data)
        if data.get(_KIND) != kind:
            intended[_KIND] = kind
            report.kind_files += 1
        status = normalise_doc_status(rel, data)
        if status != data.get(_DOC_STATUS):
            intended[_DOC_STATUS] = status
            report.doc_status_files += 1
    updated = normalise_updated(rel, data)
    if updated is not None and updated != data.get(_UPDATED):
        intended[_UPDATED] = updated
        report.updated_files += 1
    divio = data.get(_TYPE)
    if isinstance(divio, str) and divio in DIVIO_TYPE_TO_KIND:
        intended[_TYPE] = None
        report.type_files += 1
    return intended


def _repo_url(repo_root: Path, repo_path: str) -> str:
    kind = "tree" if (repo_root / repo_path).is_dir() else "blob"
    return f"{_REPO_URL}/{kind}/main/{repo_path}"


def _external(corpus: Corpus, repo_path: str, title: str) -> dict[str, str]:
    return {"url": _repo_url(corpus.repo_root, repo_path), "title": title}


@dataclass(slots=True)
class _RelatedOutcome:
    related: list[object] = field(default_factory=list)
    external: list[dict[str, str]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def _classify_docs_page(source: _Source, target: str, slug: str, corpus: Corpus, out: _RelatedOutcome) -> None:
    if corpus.related_target_allowed(source, target):
        out.related.append(slug)
    else:
        out.external.append(_external(corpus, f"{_DOCS_PREFIX}{target}", corpus.title(target)))


def _renamed_section_index(docs_root: Path, target: str) -> str:
    """An old-shape ``related`` path to a section ``index.md`` names its ``README.md`` since #6939.

    Old-shape paths predate the rename (ADR D-1), so ``x/index.md`` that no longer exists
    resolves to ``x/README.md`` when that is the folder's index. Any other path is returned as is.
    """
    head, _, name = target.rpartition("/")
    if name != _LEGACY_INDEX_FILE or (docs_root / target).is_file():
        return target
    readme = f"{head}/{_README_FILE}" if head else _README_FILE
    return readme if (docs_root / readme).is_file() else target


def _classify_entry(source: _Source, entry: str, corpus: Corpus, out: _RelatedOutcome) -> None:
    if entry.startswith(_DOCS_PREFIX):
        target = _renamed_section_index(corpus.docs_root, entry[len(_DOCS_PREFIX) :])
        if target.endswith(".md") and (corpus.docs_root / target).is_file():
            _classify_docs_page(source, target, slug_of(target), corpus, out)
            return
    else:
        page = page_for_slug(corpus.docs_root, entry)
        if page is not None:
            _classify_docs_page(source, page.relative_to(corpus.docs_root).as_posix(), entry, corpus, out)
            return
    if entry and (corpus.repo_root / entry).exists():
        out.external.append(_external(corpus, entry.rstrip("/"), entry.rstrip("/")))
    else:
        out.dropped.append(entry)


def _existing_external(value: object) -> list[dict[str, str]]:
    """The page's current ``external_references``; any shape the migration does not know fails closed."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise MigrationError(f"external_references is not a list of mappings: {value!r}")
    return [dict(item) for item in value]


def _classify_ref_entry(source: _Source, entry: Mapping[str, Any], corpus: Corpus, out: _RelatedOutcome) -> None:
    """A ``{ref, note}`` entry: classified by its ``ref``; kept as a mapping when it stays in ``related``."""
    ref = entry.get("ref")
    if not isinstance(ref, str):
        raise MigrationError(f"related entry has no string ref: {dict(entry)!r}")
    probe = _RelatedOutcome()
    _classify_entry(source, ref.strip(), corpus, probe)
    if probe.related:
        out.related.append({**dict(entry), "ref": probe.related[0]})
    note = entry.get("note")
    out.external.extend({**ext, "note": note} if isinstance(note, str) else ext for ext in probe.external)
    out.dropped.extend(probe.dropped)


def migrate_related(source: _Source, value: object, existing_external: object, corpus: Corpus) -> _RelatedOutcome:
    """Rule for ``related``: allowed pages by slug; everything else external or dropped.

    The docs root page's slug is the empty string (doc-kitty's ``slugFromEntryId``).
    """
    if not isinstance(value, list):
        raise MigrationError(f"related is not a list: {value!r}")
    out = _RelatedOutcome(external=_existing_external(existing_external))
    for entry in value:
        if isinstance(entry, Mapping):
            _classify_ref_entry(source, entry, corpus, out)
        elif isinstance(entry, str) and (entry == "" or entry.strip()):
            _classify_entry(source, entry.strip(), corpus, out)
        else:
            raise MigrationError(f"related entry is not a string or {{ref, note}}: {entry!r}")
    out.related = _dedupe(out.related)
    out.external = _dedupe(out.external)
    return out


def _dedupe(items: Sequence[object]) -> list[Any]:
    seen: list[object] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


# ---------------------------------------------------------------------------
# Line-level frontmatter editing
# ---------------------------------------------------------------------------


def _emit(key: str, value: object) -> list[str]:
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.width = 4096
    yaml.allow_unicode = True
    yaml.sort_base_mapping_type_on_output = False  # type: ignore[assignment]  # ruamel attribute missing from its stubs
    stream = io.StringIO()
    yaml.dump({key: value}, stream)
    return stream.getvalue().splitlines(keepends=True)


def _block_span(lines: Sequence[str], key: str) -> tuple[int, int] | None:
    """``(start, end)`` of the top-level block for *key* in frontmatter *lines* (fences excluded).

    A block holding a comment line is refused: replacing it would drop the comment.
    """
    for start, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            end = start + 1
            while end < len(lines) and lines[end][:1] in (" ", "\t", "-"):
                if lines[end].lstrip().startswith("#"):
                    raise MigrationError(f"the {key!r} block holds a comment line; migrate it by hand")
                end += 1
            return start, end
    return None


@dataclass(slots=True)
class _Editor:
    lines: list[str]

    def replace(self, key: str, value: object | None) -> None:
        span = _block_span(self.lines, key)
        new = [] if value is None else _emit(key, value)
        if span is None:
            self.lines.extend(new)
        else:
            self.lines[span[0] : span[1]] = new

    def insert_after(self, anchor: str, key: str, value: object) -> None:
        span = _block_span(self.lines, anchor)
        at = len(self.lines) if span is None else span[1]
        self.lines[at:at] = _emit(key, value)


def _check_integrity(rel: str, old: Mapping[str, Any], new: Mapping[str, Any], intended: Mapping[str, Any]) -> None:
    for key in set(old) | set(new):
        if key in _INTENDED_KEYS:
            expected = intended[key] if key in intended else old.get(key)
            if new.get(key) != expected:
                raise MigrationIntegrityError(f"{rel}: {key} is {new.get(key)!r}, intended {expected!r}")
        elif old.get(key) != new.get(key):
            raise MigrationIntegrityError(f"{rel}: frontmatter key {key!r} changed")


def is_skipped(rel: str) -> bool:
    """True for a page under ``docs/`` the migration never edits: one in an excluded folder."""
    return is_excluded(rel)


def _intended_changes(rel: str, data: Mapping[str, Any], corpus: Corpus, report: MigrationReport, *, d7: bool) -> dict[str, Any]:
    """The new value of every key this page needs changed (``None`` deletes the key)."""
    intended: dict[str, Any] = {}
    if _AUDIENCE in data:
        audience = migrate_audience(data[_AUDIENCE], corpus)
        if audience != data[_AUDIENCE]:
            intended[_AUDIENCE] = audience
            report.audience_files += 1
    adr = {k: v for k, v in adr_fields(rel, data).items() if data.get(k) != v}
    if adr:
        intended.update(adr)
        report.adr_files += 1
    if d7:
        intended.update(_d7_changes(rel, data, report))
    if _RELATED in data:
        outcome = migrate_related(_Source.of(rel, data), data[_RELATED], data.get(_EXTERNAL), corpus)
        report.dropped_references.extend({"from": f"{_DOCS_PREFIX}{rel}", "to": d} for d in outcome.dropped)
        new_related = outcome.related or None
        new_external = outcome.external or None
        if new_related != data[_RELATED] or new_external != data.get(_EXTERNAL):
            intended[_RELATED] = new_related
            intended[_EXTERNAL] = new_external
            report.related_files += 1
            report.external_references += len(outcome.external) - len(data.get(_EXTERNAL) or [])
    return intended


def _apply_edits(editor: _Editor, intended: Mapping[str, Any]) -> None:
    if _AUDIENCE in intended:
        editor.replace(_AUDIENCE, intended[_AUDIENCE])
    if _DOC_STATUS in intended:
        if _block_span(editor.lines, _DOC_STATUS) is None:
            editor.insert_after(_STATUS, _DOC_STATUS, intended[_DOC_STATUS])
        else:
            editor.replace(_DOC_STATUS, intended[_DOC_STATUS])
    if _KIND in intended:
        editor.insert_after(_DOC_STATUS, _KIND, intended[_KIND])
    if _UPDATED in intended:
        if _block_span(editor.lines, _UPDATED) is None:
            editor.insert_after(_DATE, _UPDATED, intended[_UPDATED])
        else:
            editor.replace(_UPDATED, intended[_UPDATED])
    if _TYPE in intended:
        editor.replace(_TYPE, None)
    if _RELATED in intended:
        external = intended.get(_EXTERNAL)
        if external is not None:
            editor.replace(_EXTERNAL, None)
            anchor = _RELATED if intended[_RELATED] is not None else None
            editor.replace(_RELATED, intended[_RELATED])
            if anchor is None:
                editor.lines.extend(_emit(_EXTERNAL, external))
            else:
                editor.insert_after(_RELATED, _EXTERNAL, external)
        else:
            editor.replace(_EXTERNAL, None)
            editor.replace(_RELATED, intended[_RELATED])


def migrate_text(rel: str, text: str, corpus: Corpus, report: MigrationReport | None = None, *, d7: bool = True) -> str:
    """Return *text* with its frontmatter migrated; the body is never touched.

    *rel* is the page's path under ``docs/``. Files the migration skips, and files
    without frontmatter, come back unchanged. ``d7=False`` runs only the #6929 rules
    (audience, ADRs, related), leaving out the D-7 fields of #6931.
    """
    report = report if report is not None else MigrationReport()
    parts = split_frontmatter(text)
    if parts is None or is_skipped(rel):
        return text
    block, body = parts
    data = parse_frontmatter(text)
    intended = _intended_changes(rel, data, corpus, report, d7=d7)
    if not intended:
        return text
    lines = block.splitlines(keepends=True)
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    if any(not line.endswith(newline) or (newline == "\n" and line.endswith("\r\n")) for line in lines[:-1]):
        raise MigrationError(f"{rel}: frontmatter mixes line endings; migrate it by hand")
    editor = _Editor(lines=[line.replace("\r\n", "\n") for line in lines[1:-1]])
    _apply_edits(editor, intended)
    fence_close = lines[-1]
    new_block = lines[0] + "".join(line.replace("\n", newline) for line in editor.lines) + fence_close
    migrated = new_block + body
    _check_integrity(rel, data, parse_frontmatter(migrated), intended)
    if body_of(migrated) != body:
        raise MigrationIntegrityError(f"{rel}: body changed")
    return migrated


def migrate_tree(*, docs_root: Path, repo_root: Path, write: bool, d7: bool = True) -> MigrationReport:
    """Migrate every page under *docs_root*; write only when *write* is true (``d7`` as in :func:`migrate_text`)."""
    corpus = Corpus.load(docs_root=docs_root, repo_root=repo_root)
    report = MigrationReport()
    pending: list[tuple[Path, str]] = []
    for path in sorted(docs_root.rglob("*.md")):
        rel = path.relative_to(docs_root).as_posix()
        before = path.read_text(encoding="utf-8")
        after = migrate_text(rel, before, corpus, report, d7=d7)
        if after != before:
            report.changed_files.append(f"{_DOCS_PREFIX}{rel}")
            pending.append((path, after))
    if write:  # every page migrated cleanly before the first write, so a failure leaves the tree untouched
        for path, after in pending:
            path.write_bytes(after.encode("utf-8"))
    return report


# ---------------------------------------------------------------------------
# Validate the tree against doc-kitty's frontmatter gate
# ---------------------------------------------------------------------------


def validate_tree(docs_root: Path) -> dict[str, FrontmatterFindings]:
    """doc-kitty's frontmatter verdict on every page it validates, keyed by ``docs/<rel>``.

    The page set is doc-kitty's: every page outside the excluded folders, drafts
    included, ``log.md`` left out (reserved and frontmatter-free upstream).
    """
    verdicts: dict[str, FrontmatterFindings] = {}
    for path in iter_docs_pages(docs_root):
        rel = path.relative_to(docs_root).as_posix()
        if is_excluded(rel) or path.name.lower() == "log.md":
            continue
        verdicts[f"{_DOCS_PREFIX}{rel}"] = validate_frontmatter(rel, parse_frontmatter(path.read_text(encoding="utf-8")))
    return verdicts


def _report_validation(verdicts: Mapping[str, FrontmatterFindings], *, show_warnings: bool) -> int:
    errors = sum(len(findings.errors) for findings in verdicts.values())
    warnings = sum(len(findings.warnings) for findings in verdicts.values())
    for page, findings in verdicts.items():
        for error in findings.errors:
            sys.stdout.write(f"  ERROR {page}: {error}\n")
        for warning in findings.warnings if show_warnings else ():
            sys.stdout.write(f"  WARN  {page}: {warning}\n")
    sys.stdout.write(f"validate: {len(verdicts)} page(s); {errors} error(s), {warnings} warning(s).\n")
    return 1 if errors else 0


# ---------------------------------------------------------------------------
# Verify a diff is frontmatter-only
# ---------------------------------------------------------------------------

_GitRunner = Callable[[Sequence[str]], str]


def _git(repo_root: Path) -> _GitRunner:
    def run(args: Sequence[str]) -> str:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True)
        return result.stdout

    return run


def verify_against(*, repo_root: Path, ref: str, docs_dir: str = "docs", git: _GitRunner | None = None) -> list[str]:
    """Every ``docs/**/*.md`` file changed or renamed since the merge-base with *ref* whose body differs there.

    Added files have no earlier body and are skipped.
    """
    run = git or _git(repo_root)
    base = run(["merge-base", ref, "HEAD"]).strip()  # where this branch left *ref*, so later commits on *ref* are not ours
    status = run(["diff", "--name-status", "-M", "--diff-filter=MR", base, "--", docs_dir]).splitlines()
    offenders: list[str] = []
    for old, new in sorted(_changed_pairs(status)):
        before = run(["show", f"{base}:{old}"])
        after = (repo_root / new).read_text(encoding="utf-8")
        if body_of(before) != body_of(after):
            offenders.append(new)
    return offenders


def _changed_pairs(status_lines: Iterable[str]) -> list[tuple[str, str]]:
    """``(path at ref, path now)`` for each modified or renamed Markdown file in ``git diff --name-status``."""
    pairs: list[tuple[str, str]] = []
    for line in status_lines:
        fields = line.split("\t")
        old, new = fields[1], fields[-1]
        if new.endswith(".md"):
            pairs.append((old, new))
    return pairs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The migration's command-line parser."""
    parser = argparse.ArgumentParser(prog="dockitty_frontmatter_migration", description=__doc__.splitlines()[0])
    parser.add_argument("--docs-root", type=Path, default=Path("docs"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report what would change; exit 1 when anything would.")
    mode.add_argument("--apply", action="store_true", help="Rewrite the frontmatter in place.")
    mode.add_argument("--verify-against", metavar="REF", help="Fail when a changed docs file's body differs from REF.")
    mode.add_argument("--validate", action="store_true", help="Run doc-kitty's frontmatter rules; exit 1 on any error.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    parser.add_argument("--warnings", action="store_true", help="With --validate, also list every warning.")
    return parser


def _emit_report(report: MigrationReport, *, as_json: bool, mode: str) -> None:
    if as_json:
        sys.stdout.write(json.dumps({"mode": mode, **report.as_dict()}, indent=2, sort_keys=True) + "\n")
        return
    sys.stdout.write(
        f"{mode}: {len(report.changed_files)} file(s); audience {report.audience_files}, "
        f"ADR {report.adr_files}, related {report.related_files} "
        f"({report.external_references} external reference(s), {len(report.dropped_references)} dropped), "
        f"kind {report.kind_files}, doc_status {report.doc_status_files}, updated {report.updated_files}, "
        f"type {report.type_files}.\n"
    )
    for dropped in report.dropped_references:
        sys.stdout.write(f"  DROPPED {dropped['from']} -> {dropped['to']}\n")


def _print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        sys.stdout.write(f"  {line}\n")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.validate:
        return _report_validation(validate_tree(args.docs_root), show_warnings=args.warnings)
    if args.verify_against:
        offenders = verify_against(repo_root=args.repo_root, ref=args.verify_against)
        sys.stdout.write(f"verify-against {args.verify_against}: {len(offenders)} body change(s).\n")
        _print_lines(offenders)
        return 1 if offenders else 0
    try:
        report = migrate_tree(docs_root=args.docs_root, repo_root=args.repo_root, write=args.apply)
    except MigrationError as exc:
        sys.stderr.write(f"dockitty_frontmatter_migration: ERROR: {exc}\n")
        return 2
    _emit_report(report, as_json=args.json, mode="apply" if args.apply else "check")
    return 1 if args.check and report.changed_files else 0


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
