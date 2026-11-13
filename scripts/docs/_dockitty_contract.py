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
* which routes the site must not publish (:func:`unpublished_routes`): excluded
  folders, the working-note folders that are drafts only (:data:`DRAFT_FOLDERS`)
  and every page that is not published (#6932), and its complement, the pages it
  publishes (:func:`published_pages`, #6943);
* which persona page an ``audience`` profile names (:func:`persona_page`),
  mirroring doc-kitty's ``resolveProfile`` (``context/audience/<profile>``);
* which files are immutable history whose body may never change
  (:func:`is_immutable`), and where a file's body starts (:func:`body_of`);
* whether a page's frontmatter passes doc-kitty's frontmatter gate
  (:func:`validate_frontmatter`), with doc-kitty's error/warning split.

They are answered here once, so no reader re-derives a slug or a folder list.
:data:`EXCLUDED_FOLDERS` is the list the doc-kitty site's ``exclude`` option must
carry; the site scaffold (#6930) takes it from here rather than copying it.

The frontmatter rules (#6931) are mirrored from doc-kitty's
``dockitty-validate-frontmatter`` (``src/scripts/validate-frontmatter.mjs``) and its
vocabulary (``src/lib/vocabulary-core.mjs``) at :data:`DOCKITTY_PIN`, the commit
``site/package.json`` installs. They are a copy, not an invention: a required field
that is absent, an ``updated`` that is not an instant, an over-long ``description``
and the two kind invariants are errors there and here; a value outside an open
vocabulary, a short ``description`` and an instant that is not written as a UTC
``Z`` instant are warnings there and here. ``tests/docs/test_dockitty_contract.py``
fails when ``site/package.json`` moves off :data:`DOCKITTY_PIN`, so a toolkit bump
re-checks this copy. Not mirrored (they need inputs core does not have, or only
add advisories): the charter overrides (core has no ``docs/_meta/charter.yaml``), the
path-derived ``type`` advisory, the generated-page exemptions (core has no generated
pages), the OKF advisories (``okf_version``, actor shapes), and the written-out
date forms upstream still accepts for old pages (``October 1, 2026``), which this
copy reports as not a date.

Standard library plus the ``kernel.clock`` door (dates go through it, as the clock
import ban requires): callers parse the frontmatter (``scripts.docs._inventory``) and
pass the mapping in, so ``site_contract.py`` keeps running on a bare ``python3`` with
``PYTHONPATH=.:src``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from kernel.clock import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DESCRIPTION_MAX",
    "DESCRIPTION_SOFT_MIN",
    "DOCKITTY_PIN",
    "DOC_STATUSES",
    "DOC_TYPES",
    "DRAFT_FOLDERS",
    "DRAFT_STATUS",
    "EXCLUDED_FOLDERS",
    "INDEX_BASENAMES",
    "KINDS",
    "LLMS_STANCE",
    "NOT_A_DATE_MESSAGE",
    "PERSONA_ROOT",
    "REQUIRED_FIELDS",
    "REQUIRED_FIELD_FLOOR",
    "FrontmatterFindings",
    "Instant",
    "body_of",
    "format_instant",
    "is_dated_adr",
    "is_excluded",
    "is_immutable",
    "is_in_draft_folder",
    "is_published",
    "page_for_slug",
    "parse_instant",
    "published_pages",
    "persona_page",
    "profile_of_persona_path",
    "redirect_stub_target",
    "route_of",
    "slug_of",
    "split_frontmatter",
    "unpublished_routes",
    "validate_frontmatter",
]

#: Docs folders the doc-kitty site leaves out (``exclude`` on ``defineDocKittyIntegrations``).
#: ``changelog/unreleased`` holds per-PR changelog fragments, which are not pages.
EXCLUDED_FOLDERS: Final[tuple[str, ...]] = ("archive", "reports", "convergence", "changelog/unreleased")

#: The section index basename (ADR D-1): ``README`` only since the rename of every
#: ``index.md`` (#6939); ``tests/docs/test_section_index_basename.py`` keeps ``index.md`` out.
INDEX_BASENAMES: Final[tuple[str, ...]] = ("README",)

#: Personas live under ``docs/context/audience/``; a profile is a path below it.
PERSONA_ROOT: Final[str] = "context/audience"

#: doc-kitty's draft status; an absent ``doc_status`` counts as a draft.
DRAFT_STATUS: Final[str] = "draft"

#: Working-note folders whose pages are all drafts (#6932, FR-001): never published.
#: doc-kitty's ``exclude`` would also drop them from the frontmatter and link gates, so they
#: stay in the tree as drafts instead of an excluded folder.
DRAFT_FOLDERS: Final[tuple[str, ...]] = ("plans/engineering-notes", "plans/investigations", "plans/research")

#: The version stance the generated ``llms.txt`` carries (ADR 2026-10-31-1 D-9). Projected to
#: ``site/dockitty-contract.json`` (``llmsStance``). This is the only copy: the hand-written
#: ``docs/llms.txt`` was deleted at cutover (#6938), and ``tests/docs/test_dockitty_contract.py``
#: keeps it from coming back.
LLMS_STANCE: Final[str] = (
    "## Current Version Stance\n"
    "\n"
    "- Current docs: https://docs.spec-kitty.ai/\n"
    "- Current overview: https://docs.spec-kitty.ai/context/\n"
    "- Current runtime model: Charter-era Spec Kitty\n"
    "- Current project governance source: `.kittify/charter/charter.md`\n"
    "- Current mission loop command: `spec-kitty next --agent <name> --mission <slug>`\n"
    "- Historical 1.x and 2.x pages are archived under `/changelog/1x/` and `/changelog/2x/`"
    " and are not the starting point for new projects.\n"
)

_INDEX_BASENAMES_FOLDED: Final[frozenset[str]] = frozenset(name.lower() for name in INDEX_BASENAMES)
_MD_SUFFIX: Final[str] = ".md"
_FENCE: Final[str] = "---"
_DATED_ADR: Final[re.Pattern[str]] = re.compile(r"^adr/\d+\.x/\d{4}-\d{2}-\d{2}-[^/]+\.md$")
_IMMUTABLE_PREFIXES: Final[tuple[str, ...]] = ("plans/", "reports/", "changelog/", "archive/")
_DOC_STATUS_LINE: Final[re.Pattern[str]] = re.compile(r"""^doc_status:[ \t]*(?P<value>[^\s#]*)""", re.MULTILINE)
#: doc-kitty's redirect stub (``renderLegacyStub``, ``lib/legacy-html-redirects.mjs``): the same
#: two-part shape its coverage gate reads (``REDIRECT_STUB_RE``, ``scripts/check-redirect-coverage.mjs``),
#: a ``Redirecting to:`` title AND a ``meta refresh``, so a page that merely uses a refresh tag is not one.
_REDIRECT_STUB: Final[re.Pattern[str]] = re.compile(
    r'<title>Redirecting to: [^<]*</title>[\s\S]*?<meta http-equiv="refresh" content="\d+;\s*url=([^"]*)"',
    re.IGNORECASE,
)
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
    if last.lower() in _INDEX_BASENAMES_FOLDED:
        return head
    return stem


def is_excluded(rel_under_docs: str) -> bool:
    """True when *rel_under_docs* lies in a folder the site leaves out."""
    return any(rel_under_docs == folder or rel_under_docs.startswith(f"{folder}/") for folder in EXCLUDED_FOLDERS)


def is_in_draft_folder(rel_under_docs: str) -> bool:
    """True when *rel_under_docs* lies in a working-note folder whose pages are drafts (:data:`DRAFT_FOLDERS`)."""
    return any(rel_under_docs.startswith(f"{folder}/") for folder in DRAFT_FOLDERS)


def route_of(rel_under_docs: str) -> str:
    """The built directory route of the page at *rel_under_docs* (``guides/x.md`` -> ``/guides/x/``)."""
    slug = slug_of(rel_under_docs)
    return f"/{slug}/" if slug else "/"


def page_for_slug(docs_root: Path, slug: str) -> Path | None:
    """The page a slug names: ``<slug>.md``, else the folder's index (``README``/``index``, any case)."""
    clean = slug.strip("/")
    if clean:
        page = docs_root / f"{clean}{_MD_SUFFIX}"
        if page.is_file():
            return page
    folder = docs_root / clean if clean else docs_root
    if not folder.is_dir():
        return None
    indexes = sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix == _MD_SUFFIX and path.stem.lower() in _INDEX_BASENAMES_FOLDED),
        key=lambda path: [name.lower() for name in INDEX_BASENAMES].index(path.stem.lower()),
    )
    return indexes[0] if indexes else None


def is_published(rel_under_docs: str, frontmatter: Mapping[str, Any]) -> bool:
    """True when doc-kitty builds the page with drafts off: not excluded and not a draft."""
    if is_excluded(rel_under_docs):
        return False
    status = frontmatter.get("doc_status")
    return (DRAFT_STATUS if status is None else status) != DRAFT_STATUS


def _doc_status_of(text: str) -> str | None:
    """The top-level ``doc_status`` scalar of a page's frontmatter, or ``None`` when absent.

    A narrow standard-library reader (no YAML parser, so the built-site check runs on a
    bare ``python3``): a top-level ``doc_status:`` line, its value unquoted.
    """
    parts = split_frontmatter(text)
    match = _DOC_STATUS_LINE.search(parts[0]) if parts else None
    value = match["value"].strip("'\"") if match else ""
    return value or None


def unpublished_routes(docs_root: Path) -> frozenset[str]:
    """The routes of every page under *docs_root* the site must not publish (#6932, FR-003).

    A page is unpublished when it lies in an excluded folder, in a draft-only working-note
    folder (:data:`DRAFT_FOLDERS`, whatever its frontmatter says) or is not
    :func:`is_published`. This is the one derivation the built-site check and the
    redirect generator (#6933) read; routes are in :func:`route_of` form.
    """
    return frozenset(route_of(rel) for rel, published in _page_publication(docs_root) if not published)


def published_pages(docs_root: Path) -> frozenset[str]:
    """The pages under *docs_root* the site publishes, as paths relative to it (#6943).

    The complement of :func:`unpublished_routes` over the tree's pages, from the same
    per-page predicate, so the two never disagree. It is the published set the docs tests
    read (titles, descriptions).
    """
    return frozenset(rel for rel, published in _page_publication(docs_root) if published)


def _page_publication(docs_root: Path) -> Iterator[tuple[str, bool]]:
    """Each page under *docs_root*, relative to it, with whether the site publishes it."""
    for path in docs_root.rglob(f"*{_MD_SUFFIX}"):
        rel = path.relative_to(docs_root).as_posix()
        if is_excluded(rel) or is_in_draft_folder(rel):
            yield rel, False
            continue
        status = _doc_status_of(path.read_text(encoding="utf-8"))
        yield rel, is_published(rel, {} if status is None else {"doc_status": status})


def redirect_stub_target(html: str) -> str | None:
    """The target of the redirect stub *html*, or ``None`` when *html* is not a stub (#6933).

    A stub is a redirect, not a publication: the built-site check skips it as a page and
    as a page to render, while its ``<a href>`` still meets the ``link`` surface, so a stub
    pointing at an unpublished route is still reported. The one predicate every reader uses.
    """
    match = _REDIRECT_STUB.search(html)
    return match.group(1) if match else None


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


# ---------------------------------------------------------------------------
# Frontmatter rules, mirrored from doc-kitty at DOCKITTY_PIN (#6931)
# ---------------------------------------------------------------------------

#: The doc-kitty commit the rules below are copied from; ``site/package.json`` pins the same one.
DOCKITTY_PIN: Final[str] = "1042a40792b47df4339b4511e2107c55854adce1"

#: ``CANONICAL_REQUIRED``: an absent (or empty) member is an error.
REQUIRED_FIELDS: Final[tuple[str, ...]] = ("title", "description", "doc_status", "updated", "kind")

#: ``REQUIRED_FIELD_FLOOR``: required whatever a charter relaxes.
REQUIRED_FIELD_FLOOR: Final[tuple[str, ...]] = ("title",)

#: ``STATUSES``: a ``doc_status`` outside it is a warning.
DOC_STATUSES: Final[tuple[str, ...]] = ("draft", "active", "deprecated", "superseded", "durable")

#: ``KINDS`` (how to read a page): a ``kind`` outside it is a warning.
KINDS: Final[tuple[str, ...]] = (
    "Tutorial",
    "How-To",
    "Reference",
    "Explanation",
    "Hub",
    "ADR",
    "Changelog",
    "Glossary",
    "Presentation",
    "Persona",
    "Planning",
    "Feature",
    "User-Journey",
    "Specification",
    "Schematic",
)

#: ``DOC_TYPES`` (the section a page belongs to): an authored ``type`` outside it is a warning.
DOC_TYPES: Final[tuple[str, ...]] = (
    "Context",
    "Architecture",
    "ADR",
    "Template",
    "Plan",
    "Epic",
    "Feature",
    "API",
    "Configuration",
    "Integration",
    "Security",
    "Guide",
    "Operations",
    "Runbook",
    "Migration",
    "Changelog",
    "Presentation",
    "Specification",
)

#: ``DESCRIPTION_MAX`` (an error above it) and ``DESCRIPTION_SOFT_MIN`` (a warning below it).
DESCRIPTION_MAX: Final[int] = 180
DESCRIPTION_SOFT_MIN: Final[int] = 50

#: The rejection message for a value that is not an instant.
NOT_A_DATE_MESSAGE: Final[str] = "not a date: write a UTC instant, YYYY-MM-DDTHH:MM:SSZ"

_INSTANT_FIELDS: Final[tuple[str, ...]] = ("updated", "stale_after")
_STRING_FIELDS: Final[tuple[str, ...]] = ("title", "description", "doc_status", "kind", "type")
_PRESENTATION_SECTION: Final[str] = "presentations"
_PERSONA_LIST_FIELDS: Final[tuple[str, ...]] = ("goals", "responsibilities")
_INSTANT: Final[re.Pattern[str]] = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?([Zz]|[+-]\d{2}(?::?\d{2})?)?)?$")


@dataclass(frozen=True, slots=True)
class Instant:
    """A parsed instant and the advisories upstream raises on its spelling (``normaliseInstant``)."""

    moment: datetime
    date_only: bool = False
    non_utc: bool = False
    no_zone: bool = False
    rolled_over: bool = False


def format_instant(moment: datetime) -> str:
    """The canonical spelling of *moment*: ``YYYY-MM-DDTHH:MM:SSZ`` in UTC, whole seconds."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _offset_minutes(zone: str) -> int | None:
    sign = -1 if zone[0] == "-" else 1
    hours = int(zone[1:3])
    minutes = int(zone[3:].replace(":", "") or 0)
    return None if hours > 14 or minutes >= 60 else sign * (hours * 60 + minutes)


def _utc_rolled(year: int, month: int, day: int, hour: int, minute: int, second: int) -> datetime:
    """``Date.UTC`` arithmetic: out-of-range components roll into the next unit, as JavaScript does."""
    first = datetime(year + (month - 1) // 12, (month - 1) % 12 + 1, 1, tzinfo=UTC)
    return first + timedelta(days=day - 1, hours=hour, minutes=minute, seconds=second)


def _parse_instant_text(text: str) -> Instant | None:
    match = _INSTANT.match(text.strip())
    if match is None:
        return None
    year, month, day, hour, minute, second, frac, zone = match.groups()
    parts = (int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
    try:
        moment = _utc_rolled(*parts)
    except (ValueError, OverflowError):  # year 0 or past 9999: outside what a datetime holds
        return None
    rolled_over = (moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second) != parts
    non_utc = zone is not None and zone not in ("Z", "z")
    offset = _offset_minutes(zone) if non_utc and zone is not None else 0
    if offset is None:
        return None
    if frac:
        moment += timedelta(milliseconds=round(float(f"0{frac}") * 1000))
    return Instant(
        moment=moment - timedelta(minutes=offset),
        date_only=hour is None,
        non_utc=non_utc,
        no_zone=hour is not None and zone is None,
        rolled_over=rolled_over,
    )


def parse_instant(value: object) -> Instant | None:
    """Read *value* as doc-kitty reads an instant, or ``None`` when it is not one.

    A YAML-parsed ``datetime`` is an instant (a naive one is read as UTC); a YAML-parsed
    ``date`` is a date-only instant (upstream restores the date-only scalar for the same
    advisory). A string must be ISO-8601 (``YYYY-MM-DD``, optionally a time with seconds,
    fractions and a ``Z``/``+HH:MM``/``+HHMM``/``+HH`` zone). Anything else is not an
    instant.
    """
    if isinstance(value, datetime):
        return Instant(moment=value if value.tzinfo else value.replace(tzinfo=UTC))
    if isinstance(value, date):
        return Instant(moment=datetime(value.year, value.month, value.day, tzinfo=UTC), date_only=True)
    if isinstance(value, str):
        return _parse_instant_text(value)
    return None


def _instant_advisories(field: str, value: object, instant: Instant) -> list[str]:
    advisories: list[str] = []
    if instant.non_utc:
        advisories.append(f"`{field}: {value}` is not UTC; write the instant with a `Z` offset")
    if instant.no_zone:
        advisories.append(f"`{field}: {value}` has no zone (read as UTC); write the instant with a `Z` offset")
    if instant.rolled_over:
        advisories.append(f"`{field}: {value}` is not a real calendar date; read as {format_instant(instant.moment)}")
    if field == "updated" and instant.date_only:
        advisories.append(f"`updated: {value}` is date-only; use a UTC instant (YYYY-MM-DDTHH:MM:SSZ)")
    return advisories


@dataclass(frozen=True, slots=True)
class FrontmatterFindings:
    """doc-kitty's verdict on one page: ``errors`` fail its gate, ``warnings`` never do."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _absent(value: object) -> bool:
    return value is None or value == ""


def _shape_findings(data: Mapping[str, Any], errors: list[str], warnings: list[str]) -> None:
    for field in _STRING_FIELDS:
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"`{field}`: must be a string")
    description = data.get("description")
    if isinstance(description, str) and len(description) > DESCRIPTION_MAX:
        errors.append(f"`description`: must be at most {DESCRIPTION_MAX} characters")
    for field in _INSTANT_FIELDS:
        value = data.get(field)
        if _absent(value):
            continue
        instant = parse_instant(value)
        if instant is None:
            errors.append(f"`{field}`: {NOT_A_DATE_MESSAGE}")
        else:
            warnings.extend(_instant_advisories(field, value, instant))


def _vocabulary_findings(data: Mapping[str, Any], warnings: list[str]) -> None:
    for field, legal, noun in (
        ("doc_status", DOC_STATUSES, "legal set"),
        ("type", DOC_TYPES, "canonical set"),
        ("kind", KINDS, "canonical set"),
    ):
        value = data.get(field)
        if isinstance(value, str) and value and value not in legal:
            warnings.append(f"`{field}: {value}` is not in the {noun} ({', '.join(legal)})")
    description = data.get("description")
    if isinstance(description, str) and 0 < len(description.strip()) < DESCRIPTION_SOFT_MIN:
        length = len(description.strip())
        warnings.append(f"description is {length} chars; convention suggests {DESCRIPTION_SOFT_MIN}–{DESCRIPTION_MAX}")


def _non_empty_strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def _kind_findings(rel_under_docs: str, data: Mapping[str, Any], errors: list[str]) -> None:
    kind = data.get("kind")
    if kind == "Presentation" and rel_under_docs.split("/")[0] != _PRESENTATION_SECTION:
        errors.append("`kind: Presentation` must live under `presentations/` (ADR-0021 path+kind invariant, FR-022)")
    if kind != "Persona":
        return
    role = data.get("role")
    if not (isinstance(role, str) and role.strip()):
        errors.append("`role`: persona requires a non-empty string")
    for field in _PERSONA_LIST_FIELDS:
        if not _non_empty_strings(data.get(field)):
            errors.append(f"`{field}`: persona requires a non-empty list of non-empty strings")


def validate_frontmatter(rel_under_docs: str, data: Mapping[str, Any]) -> FrontmatterFindings:
    """doc-kitty's frontmatter verdict on the page at *rel_under_docs* (``validate()`` upstream).

    Errors: a field of :data:`REQUIRED_FIELDS` absent or empty; a string field holding
    another type; a ``description`` over :data:`DESCRIPTION_MAX`; an ``updated`` or
    ``stale_after`` that is not an instant (:data:`NOT_A_DATE_MESSAGE`); ``kind:
    Presentation`` outside ``presentations/``; ``kind: Persona`` without ``role``,
    ``goals`` and ``responsibilities``. Warnings: a ``doc_status``, ``type`` or ``kind``
    outside its vocabulary; a ``description`` under :data:`DESCRIPTION_SOFT_MIN`; an
    instant that is date-only, has no zone, a non-UTC zone or a rolled-over date.
    """
    errors: list[str] = []
    warnings: list[str] = []
    _shape_findings(data, errors, warnings)
    errors.extend(f"`{field}`: required" for field in dict.fromkeys((*REQUIRED_FIELDS, *REQUIRED_FIELD_FLOOR)) if _absent(data.get(field)))
    _vocabulary_findings(data, warnings)
    _kind_findings(rel_under_docs, data, errors)
    return FrontmatterFindings(errors=tuple(errors), warnings=tuple(warnings))
