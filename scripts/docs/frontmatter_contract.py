"""The doc-kitty frontmatter contract, stated once and checkable without doc-kitty.

Epic #6100 moves the docsite from DocFX to doc-kitty. ADR 2026-10-31-1 D-7 records
the frontmatter mapping; this module is where that mapping becomes executable.

Why a local contract at all
---------------------------
The issue that asked for this work (spec-kitty/spec-kitty#6931) names its gate as
``dockitty-validate-frontmatter --astro-config site/astro.config.mjs``. Neither the
binary nor ``site/`` exists on ``main`` — the site scaffold is #6930, unstarted. A
gate that cannot run cannot be satisfied, so the contract is *stated here* and
checked by a local gate that needs no Node, no build and no network. When doc-kitty
lands, its gate becomes the authority; until then this one has to be right on its
own terms, which is why every set below is **mirrored from doc-kitty's own source**
at the commit the #6100 spike pinned (``494f2d87``) rather than invented:

======================================  ==========================================
doc-kitty source                        what is mirrored here
======================================  ==========================================
``src/lib/vocabulary-core.mjs``         ``CANONICAL_REQUIRED``, ``KINDS``,
``STATUSES``, ``DOC_TYPES``, the instant
grammar and ``NOT_A_DATE_MESSAGE``
``src/scripts/validate-frontmatter.mjs``  the error/warning split (an absent
required field is an *error*; a value
outside an open vocabulary is a *warning*)
``docs/adr/0009-finalize-metadata-contract.md``
"``type`` names the section; ``kind``
names how to read the page"
======================================  ==========================================

Mirroring, not importing: the upstream is TypeScript/JavaScript in another
repository. ``tests/docs/test_frontmatter_contract_upstream_parity.py`` is what keeps
the mirror honest — it pins the three sets against the recorded upstream values, so a
silent drift here fails a test instead of shipping a contract doc-kitty disagrees
with.

Severity is upstream's, deliberately
------------------------------------
Promoting a warning to an error would invent a gate doc-kitty does not have (and
would block pages it publishes); demoting an error would fake green. So:

* **error** — an absent field in :data:`REQUIRED_FIELDS`; a page whose ``kind`` no
  rule can resolve; an unparseable/absent ``updated``; an ADR ``status`` outside the
  mapping; ``kind: Presentation`` outside ``presentations/``; ``kind: Persona``
  without its three attribute fields.
* **warning** — a ``kind``/``doc_status``/``type`` value outside its canonical set;
  a ``description`` over :data:`MAX_DESCRIPTION_LENGTH`.

D-7 rows this module owns
-------------------------
``kind`` (from the Divio ``type``, ``Hub`` for indexes, ``ADR`` for the ADR tree,
the remainder by path), ``doc_status`` normalisation, and ``updated`` as an instant.
The other D-7 rows — ``audience`` as a list, the excluded-tree schema minimum,
``related`` as slugs — belong to #6929 and are deliberately **not** validated here:
a gate that fails on a field its own mission does not migrate is a gate nobody can
turn green.

The two recorded judgement calls
--------------------------------
1. **D-8 beats the D-7 alias table for three subtrees.** D-7 maps ``point_in_time``
   and ``closeout`` to ``durable``; D-8 says ``plans/engineering-notes/``,
   ``plans/investigations/`` and ``plans/research/`` take ``doc_status: draft`` and
   are not published. For those paths the specific publication rule wins — applying
   D-7 literally would *publish* engineering notes the operator decided not to
   publish. See :data:`DRAFT_SECTIONS`.
2. **``kind: Persona`` is not applied to ``docs/context/audience/**``.** doc-kitty
   errors on a ``Persona`` page without ``role``/``goals``/``responsibilities``; the
   persona pages carry those attributes in a body table, not frontmatter. They take
   :data:`KIND_BY_PATH_PREFIX`'s ``Explanation``; the upstream gap is recorded for the
   PR.

Depends only on the standard library plus ``ruamel.yaml`` (via
:func:`scripts.docs._inventory.parse_frontmatter`). No new dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from scripts.docs._guards import GitDiffError, resolve_changed_files
from scripts.docs._inventory import DivioType, parse_frontmatter
from scripts.docs._published_pages import (
    MINIMUM_EXPECTED_PAGES,
    PublishedPageSet,
    resolve_published_pages,
)

__all__ = [
    "ADR_STATUS_TO_DOC_STATUS",
    "DEFAULT_DOCS_ROOT",
    "DIVIO_TYPE_TO_KIND",
    "DOC_STATUSES",
    "DOC_TYPES",
    "DRAFT_SECTIONS",
    "EXIT_COVERAGE_FAILURE",
    "FIELD_FLOOR",
    "INDEX_BASENAMES",
    "KIND_BY_PATH_PREFIX",
    "KINDS",
    "KIND_TO_DIVIO_TYPE",
    "MAX_DESCRIPTION_LENGTH",
    "MIN_DESCRIPTION_LENGTH",
    "REQUIRED_FIELDS",
    "UPDATED_INSTANT_INSTRUCTIONS",
    "CoverageError",
    "ContractReport",
    "InstantReading",
    "PageEdit",
    "PageVerdict",
    "Violation",
    "apply_plan",
    "body_of",
    "build_parser",
    "check_instant",
    "main",
    "normalise_doc_status",
    "normalise_updated",
    "plan_page",
    "read_instant",
    "resolve_kind",
    "validate_page",
    "validate_tree",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"

# ---------------------------------------------------------------------------
# Contract data — mirrored from doc-kitty 494f2d87 (see the module docstring)
# ---------------------------------------------------------------------------

#: ``CANONICAL_REQUIRED`` upstream. An absent member is a hard error.
REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "title",
    "description",
    "doc_status",
    "updated",
    "kind",
)

#: ``REQUIRED_FIELD_FLOOR`` upstream — never relaxable, always enforced.
FIELD_FLOOR: Final[tuple[str, ...]] = ("title",)

#: ``KINDS`` upstream (ADR-0009). Open vocabulary: a value outside it *warns*, and
#: the axis is what doc-kitty's per-kind layouts switch on. ``type`` names the
#: section; ``kind`` names how to read the page — which is why the corpus's Divio
#: ``type`` values fold into ``kind`` (ADR D-7).
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

#: ``STATUSES`` upstream. The five canonical lifecycle values. Deliberately a copy,
#: not an import: :class:`scripts.docs.frontmatter_backfill.DocStatus` is the repo's
#: enum and ``tests/docs/test_frontmatter_contract.py`` pins the two together, which
#: is the cross-source agreement check this repository already applies to
#: directive 042's vocabulary. Importing instead would make the two sources one and
#: remove the check.
DOC_STATUSES: Final[tuple[str, ...]] = (
    "draft",
    "active",
    "deprecated",
    "superseded",
    "durable",
)

#: ``DOC_TYPES`` upstream — the canonical *section* type values. Advisory only:
#: ``type`` has been optional upstream since doc-kitty #38, and an authored value
#: outside this set only warns.
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

#: ADR D-7's ``doc_status`` normalisation: the three legacy values the corpus still
#: carries, mapped to canonical ones. ``closeout``/``point_in_time`` are
#: lint-asset-owned markers, not lifecycle values; ``proposal`` means "not yet
#: accepted", i.e. a draft.
DOC_STATUS_ALIASES: Final[dict[str, str]] = {
    "closeout": "durable",
    "point_in_time": "durable",
    "proposal": "draft",
}

#: ADR D-7 + operator ruling 5: an ADR's MADR ``status`` becomes ``doc_status``.
#: ``Proposed`` maps to ``active`` so proposed ADRs stay indexed (ruling 5).
ADR_STATUS_TO_DOC_STATUS: Final[dict[str, str]] = {
    "Accepted": "active",
    "Proposed": "active",
    "Superseded": "superseded",
}

#: ADR D-7: the Divio ``type`` values the corpus carries, mapped to their doc-kitty
#: ``kind``. The mapping is what lets a page stop carrying a Divio value in a field
#: doc-kitty reads as a section name.
DIVIO_TYPE_TO_KIND: Final[dict[str, str]] = {
    "tutorial": "Tutorial",
    "how-to": "How-To",
    "reference": "Reference",
    "explanation": "Explanation",
}

#: The inverse map for the in-repo readers that keep the Divio axis for the retrieval
#: index and the page inventory (``scripts/docs/docs_index.py``,
#: ``scripts/docs/inventory_lockfile.py``). Total in the other direction: a kind that
#: has no Divio quadrant (``Hub``, ``ADR``, ``Planning``, …) reads as
#: :attr:`DivioType.NONE`, which is exactly what those artifacts recorded before the
#: Divio ``type`` existed for them.
KIND_TO_DIVIO_TYPE: Final[dict[str, DivioType]] = {
    "Tutorial": DivioType.TUTORIAL,
    "How-To": DivioType.HOW_TO,
    "Reference": DivioType.REFERENCE,
    "Explanation": DivioType.EXPLANATION,
}

#: D-7's "the rest are classified in the migration step". These are the pages with no
#: Divio ``type``, no index role and no ADR role (201 of 670 at migration time). Each
#: row is the nearest doc-kitty kind for a section whose reading is not in doubt;
#: the longest matching prefix wins, and a per-page authored ``kind`` always beats it.
#: A page that matches no row is a **hard error** ("any page left unclassified is a
#: migration failure", D-7) — never a guess.
KIND_BY_PATH_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("docs/adr/", "ADR"),
    ("docs/plans/", "Planning"),
    ("docs/changelog/", "Changelog"),
    ("docs/api/", "Reference"),
    ("docs/configuration/", "Reference"),
    ("docs/development/reference/", "Reference"),
    ("docs/guides/how-to/", "How-To"),
    ("docs/guides/tutorials/", "Tutorial"),
    ("docs/architecture/", "Explanation"),
    ("docs/context/", "Explanation"),
    ("docs/migrations/", "How-To"),
    ("docs/operations/", "How-To"),
)

#: D-8's unpublished subtrees, which take ``doc_status: draft`` and override the D-7
#: alias table (see the module docstring, judgement call 1).
DRAFT_SECTIONS: Final[tuple[str, ...]] = (
    "docs/plans/engineering-notes/",
    "docs/plans/investigations/",
    "docs/plans/research/",
)

#: Section-index basenames. ``indexBasename`` is ``['README', 'index']`` in the ADR's
#: site config for the parallel run, so both names are an index today.
INDEX_BASENAMES: Final[frozenset[str]] = frozenset({"index.md", "README.md"})

#: Inclusive description length band. The *lower* bound is this repository's SEO gate
#: (``scripts/docs/description_length_check.py``, NFR-003 of that mission); doc-kitty
#: only imposes the upper bound (``DESCRIPTION_MAX`` upstream) and only as a warning.
MIN_DESCRIPTION_LENGTH: Final[int] = 50
MAX_DESCRIPTION_LENGTH: Final[int] = 180

#: The canonical ``updated`` shape: an RFC3339 UTC instant with a literal ``Z``.
#: Any other *parseable* spelling is an advisory warning — upstream doc-kitty does the
#: same (``instantAdvisories``: "`updated: ...` is date-only; use a UTC instant"), and a
#: migration cannot be green while calling an input it is about to normalise an error.
#: An *unparseable* value is a hard error, matching upstream's ``NOT_A_DATE_MESSAGE``.
UPDATED_INSTANT_INSTRUCTIONS: Final[str] = (
    "not a date: write a UTC instant, YYYY-MM-DDTHH:MM:SSZ"
)

_INSTANT_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%SZ"
_DATE_FORMAT: Final[str] = "%Y-%m-%d"

#: Exit code for a coverage failure — the gate could not trust its page set. Shared
#: with the sibling gates so one CI wiring shape covers all of them.
EXIT_COVERAGE_FAILURE: Final[int] = 2


class CoverageError(RuntimeError):
    """The gate could not establish a trustworthy set of pages to check.

    Distinct from a content violation: nothing is wrong with any page, the *gate* is
    not in a position to assert anything. A gate that validates zero pages must fail,
    not pass — silently reporting "0 errors" from a collapsed page set is the defect
    class this repository has repaired more than once.
    """


# ---------------------------------------------------------------------------
# Pure resolution
# ---------------------------------------------------------------------------


def _frontmatter_str(frontmatter: Mapping[str, Any], key: str) -> str | None:
    """Return a non-empty string value for ``key``, else ``None``."""
    value = frontmatter.get(key)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def is_index_page(rel_path: str) -> bool:
    """Whether ``rel_path`` is a section index (``index.md``/``README.md``)."""
    return Path(rel_path).name in INDEX_BASENAMES


def is_adr_page(rel_path: str) -> bool:
    """Whether ``rel_path`` lives in the ADR tree (``docs/adr/**``)."""
    return rel_path.startswith("docs/adr/")


def _draft_section(rel_path: str) -> bool:
    """Whether ``rel_path`` is inside a D-8 draft-and-unpublished subtree."""
    return any(rel_path.startswith(prefix) for prefix in DRAFT_SECTIONS)


def resolve_kind(rel_path: str, frontmatter: Mapping[str, Any]) -> str | None:
    """Resolve a page's doc-kitty ``kind``; ``None`` means unclassified.

    Order, first match wins — each step is a narrower statement than the one after:

    1. an authored ``kind`` (a later migration or another PR may have set it);
    2. a section index (``index.md``/``README.md``) → ``Hub``;
    3. the ADR tree → ``ADR``;
    4. a Divio ``type`` → its doc-kitty kind (ADR D-7);
    5. the path-prefix table (:data:`KIND_BY_PATH_PREFIX`);
    6. otherwise ``None`` — a hard failure, never a guess. D-7: "any page left
       unclassified is a migration failure".

    An index page inside the ADR tree resolves to ``Hub``, not ``ADR``: it is a hub
    over ADRs, and doc-kitty's ``Hub`` layout is what lists them.
    """
    authored = _frontmatter_str(frontmatter, "kind")
    if authored is not None:
        return authored
    if is_index_page(rel_path):
        return "Hub"
    if is_adr_page(rel_path):
        return "ADR"
    divio_type = _frontmatter_str(frontmatter, "type")
    if divio_type is not None and divio_type in DIVIO_TYPE_TO_KIND:
        return DIVIO_TYPE_TO_KIND[divio_type]
    prefix_match: tuple[int, str] | None = None
    for prefix, kind in KIND_BY_PATH_PREFIX:
        if rel_path.startswith(prefix) and (prefix_match is None or len(prefix) > prefix_match[0]):
            prefix_match = (len(prefix), kind)
    return None if prefix_match is None else prefix_match[1]


def normalise_doc_status(rel_path: str, frontmatter: Mapping[str, Any]) -> str | None:
    """Resolve a page's canonical ``doc_status``; ``None`` if nothing determines it.

    Precedence:

    1. a canonical value passes unchanged (idempotence);
    2. the D-8 draft subtrees take ``draft`` — see the module docstring, judgement
       call 1, for why this beats the alias table;
    3. ADR D-7's alias table (``closeout``/``point_in_time`` → ``durable``,
       ``proposal`` → ``draft``);
    4. an ADR's MADR ``status`` via :data:`ADR_STATUS_TO_DOC_STATUS`;
    5. otherwise ``None`` — the caller reports it, this function does not guess.
    """
    current = _frontmatter_str(frontmatter, "doc_status")
    if current is not None and current in DOC_STATUSES:
        return current
    if _draft_section(rel_path):
        return "draft"
    if current is not None and current in DOC_STATUS_ALIASES:
        return DOC_STATUS_ALIASES[current]
    if is_adr_page(rel_path):
        adr_status = _frontmatter_str(frontmatter, "status")
        if adr_status is not None and adr_status in ADR_STATUS_TO_DOC_STATUS:
            return ADR_STATUS_TO_DOC_STATUS[adr_status]
    if current is not None:
        return current  # unknown to the alias table: report, do not rewrite
    return None


def check_instant(value: object) -> str | None:
    """Return ``None`` when ``value`` is a canonical instant, else the reason.

    Canonical means exactly ``YYYY-MM-DDTHH:MM:SSZ`` **and** a real calendar
    instant: ``2026-13-01T00:00:00Z`` matches the shape and is still rejected.
    """
    if not isinstance(value, str):
        return "not a string"
    try:
        parsed = datetime.strptime(value, _INSTANT_FORMAT)
    except ValueError:
        return UPDATED_INSTANT_INSTRUCTIONS
    # ``strptime`` accepts non-zero-padded components; the round trip does not.
    if parsed.strftime(_INSTANT_FORMAT) != value:
        return UPDATED_INSTANT_INSTRUCTIONS
    return None


@dataclass(slots=True, frozen=True)
class InstantReading:
    """What a raw ``updated``/``date`` value means, and how far it is from canonical.

    ``canonical`` is the value the contract wants in the frontmatter, or ``None`` when
    the raw value is not an instant at all. ``advisory`` is a non-fatal statement about
    a *parseable but non-canonical* spelling (date-only, non-UTC offset, no zone) —
    upstream doc-kitty raises exactly these as advisories, never as errors.
    """

    canonical: str | None = None
    advisory: str | None = None


def read_instant(raw: object) -> InstantReading:
    """Read a raw frontmatter value as an instant, without inventing precision.

    Accepts, in upstream ``normaliseInstant``'s order of generosity: a ``datetime``
    already parsed by the YAML loader (rendered as the canonical ``Z`` form), a
    canonical instant, a date-only value (midnight UTC, *advisory*), and an ISO instant
    with a non-``Z`` offset or no zone (converted to UTC, *advisory*). Anything else is
    unparseable — ``canonical`` is ``None`` and the caller reports an error, matching
    upstream's ``NOT_A_DATE_MESSAGE``.
    """
    if isinstance(raw, datetime):
        return InstantReading(canonical=raw.strftime(_INSTANT_FORMAT))
    if not isinstance(raw, str):
        return InstantReading()
    text = raw.strip()
    if not text:
        return InstantReading()
    if check_instant(text) is None:
        return InstantReading(canonical=text)
    try:
        date_only = datetime.strptime(text, _DATE_FORMAT)
    except ValueError:
        pass
    else:
        canonical = f"{date_only.strftime(_DATE_FORMAT)}T00:00:00Z"
        return InstantReading(
            canonical=canonical,
            advisory=f"date-only value; write a UTC instant ({canonical})",
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return InstantReading()
    if parsed.tzinfo is None:
        advisory = "no zone (read as UTC); write the instant with a `Z` offset"
        parsed = parsed.replace(tzinfo=UTC)
    else:
        advisory = "not UTC; write the instant with a `Z` offset"
    canonical = parsed.astimezone(UTC).strftime(_INSTANT_FORMAT)
    return InstantReading(canonical=canonical, advisory=f"{advisory} ({canonical})")


def normalise_updated(rel_path: str, frontmatter: Mapping[str, Any]) -> str | None:
    """Resolve a page's ``updated`` as a canonical instant; ``None`` if undeterminable.

    An existing value is normalised in place: a date-only value becomes
    ``<date>T00:00:00Z`` (ADR D-7), and a value that is already canonical is returned
    unchanged so the migration is idempotent. An ADR with no ``updated`` takes its
    ``date`` (D-7: "ADRs take theirs from ``date``") — an *explicit* ``updated`` always
    wins, because a later amendment is a real update and its date must not be
    overwritten by the decision date.
    """
    raw = frontmatter.get("updated")
    if raw is not None:
        return read_instant(raw).canonical
    if is_adr_page(rel_path):
        return read_instant(frontmatter.get("date")).canonical
    return None


def has_divio_type(frontmatter: Mapping[str, Any]) -> bool:
    """Whether the page's ``type`` carries a Divio value that must fold into ``kind``.

    doc-kitty reads ``type`` as the section (ADR-0009), so a Divio value there is a
    wrong section name rather than a harmless extra. A ``type`` that is already a
    canonical doc-kitty type is left alone: it carries the meaning doc-kitty gives it.
    """
    value = _frontmatter_str(frontmatter, "type")
    return value is not None and value in DIVIO_TYPE_TO_KIND


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Violation:
    """One contract violation, with the severity upstream doc-kitty gives it."""

    path: str
    field: str
    reason: str
    detail: str
    severity: str  # "error" | "warning"

    def as_dict(self) -> dict[str, object]:
        """Serialize to the gate's JSON shape."""
        return {
            "path": self.path,
            "field": self.field,
            "reason": self.reason,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass(slots=True, frozen=True)
class PageVerdict:
    """The verdict for one page: its errors, its warnings, and its resolved values."""

    path: str
    errors: tuple[Violation, ...] = ()
    warnings: tuple[Violation, ...] = ()
    kind: str | None = None
    doc_status: str | None = None
    updated: str | None = None


@dataclass(slots=True, frozen=True)
class ContractReport:
    """Result of one validation pass over a page set."""

    checked_count: int = 0
    errors: tuple[Violation, ...] = ()
    warnings: tuple[Violation, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether the report is clean (warnings allowed, errors not)."""
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        """Serialize to the gate's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [v.as_dict() for v in self.errors],
            "warnings": [v.as_dict() for v in self.warnings],
        }


def _violation(path: str, field_name: str, reason: str, detail: str, severity: str) -> Violation:
    """Build a :class:`Violation` (one constructor, so severity strings never drift)."""
    return Violation(path=path, field=field_name, reason=reason, detail=detail, severity=severity)


def _required_field_violations(
    rel_path: str, frontmatter: Mapping[str, Any]
) -> list[Violation]:
    """Every required field (and the immovable floor) must be present."""
    return [
        _violation(rel_path, field_name, "required", "contract requires this field", "error")
        for field_name in (*REQUIRED_FIELDS, *FIELD_FLOOR)
        if _frontmatter_str(frontmatter, field_name) is None
    ]


def _kind_violations(
    rel_path: str, frontmatter: Mapping[str, Any], kind: str | None
) -> tuple[list[Violation], list[Violation]]:
    """An unclassifiable page is an error; an unknown kind is an advisory warning."""
    errors: list[Violation] = []
    warnings: list[Violation] = []
    if _frontmatter_str(frontmatter, "kind") is None and kind is None:
        errors.append(
            _violation(
                rel_path,
                "kind",
                "unclassified",
                "no rule resolves a kind for this path (ADR D-7: an unclassified page is a migration failure)",
                "error",
            )
        )
    elif kind is not None and kind not in KINDS:
        warnings.append(
            _violation(
                rel_path,
                "kind",
                "outside_canonical_set",
                f"{kind!r} is not in the canonical set ({', '.join(KINDS)})",
                "warning",
            )
        )
    return errors, warnings


def _doc_status_violations(
    rel_path: str, frontmatter: Mapping[str, Any]
) -> list[Violation]:
    """A value outside the legal lifecycle set warns, matching the pinned gate."""
    doc_status = normalise_doc_status(rel_path, frontmatter)
    if doc_status is None or doc_status in DOC_STATUSES:
        return []
    return [
        _violation(
            rel_path,
            "doc_status",
            "outside_canonical_set",
            f"{doc_status!r} is not in the legal set ({', '.join(DOC_STATUSES)})",
            "warning",
        )
    ]


def _updated_violations(
    rel_path: str, frontmatter: Mapping[str, Any]
) -> tuple[list[Violation], list[Violation], str | None]:
    """An unparseable instant is an error; a non-canonical spelling is an advisory."""
    raw_updated = frontmatter.get("updated")
    errors: list[Violation] = []
    warnings: list[Violation] = []
    if raw_updated is None:
        updated = normalise_updated(rel_path, frontmatter)
        if updated is None:
            errors.append(
                _violation(rel_path, "updated", "unparseable", UPDATED_INSTANT_INSTRUCTIONS, "error")
            )
        return errors, warnings, updated
    reading = read_instant(raw_updated)
    if reading.canonical is None:
        errors.append(
            _violation(rel_path, "updated", "unparseable", UPDATED_INSTANT_INSTRUCTIONS, "error")
        )
    elif reading.advisory is not None:
        warnings.append(
            _violation(rel_path, "updated", "not_canonical", reading.advisory, "warning")
        )
    return errors, warnings, reading.canonical


def _path_and_kind_violations(
    rel_path: str, frontmatter: Mapping[str, Any], kind: str | None
) -> list[Violation]:
    """The ADR-status mapping and the two upstream path+kind invariants."""
    errors: list[Violation] = []

    # ADR D-7's ADR row: an ADR's MADR status must map. A new status value is a human
    # decision, not something this gate may guess at.
    if is_adr_page(rel_path) and not is_index_page(rel_path):
        adr_status = _frontmatter_str(frontmatter, "status")
        if adr_status is not None and adr_status not in ADR_STATUS_TO_DOC_STATUS:
            errors.append(
                _violation(
                    rel_path,
                    "status",
                    "unmapped_adr_status",
                    f"{adr_status!r} has no doc_status mapping "
                    f"({', '.join(ADR_STATUS_TO_DOC_STATUS)})",
                    "error",
                )
            )

    # Upstream's path+kind invariants, mirrored so this gate cannot call a page clean
    # that doc-kitty will reject.
    if kind == "Presentation" and not rel_path.startswith("presentations/"):
        errors.append(
            _violation(
                rel_path,
                "kind",
                "presentation_path",
                "`kind: Presentation` must live under `presentations/` (doc-kitty ADR-0021)",
                "error",
            )
        )
    if kind == "Persona":
        errors.extend(
            _violation(
                rel_path,
                field_name,
                "persona_requires_field",
                "`kind: Persona` requires this field (doc-kitty ADR-0019)",
                "error",
            )
            for field_name in ("role", "goals", "responsibilities")
            if frontmatter.get(field_name) in (None, "", [])
        )
    return errors


def _type_and_description_violations(
    rel_path: str, frontmatter: Mapping[str, Any]
) -> list[Violation]:
    """The two advisory checks: an unknown ``type`` and an over-long description."""
    warnings: list[Violation] = []
    type_value = _frontmatter_str(frontmatter, "type")
    if type_value is not None and type_value not in DOC_TYPES:
        warnings.append(
            _violation(
                rel_path,
                "type",
                "outside_canonical_set",
                f"{type_value!r} is not in the canonical set ({', '.join(DOC_TYPES)})",
                "warning",
            )
        )
    description = _frontmatter_str(frontmatter, "description")
    if description is not None and len(description) > MAX_DESCRIPTION_LENGTH:
        warnings.append(
            _violation(
                rel_path,
                "description",
                "too_long",
                f"{len(description)} characters, over the {MAX_DESCRIPTION_LENGTH} bound",
                "warning",
            )
        )
    return warnings


def validate_page(rel_path: str, frontmatter: Mapping[str, Any]) -> PageVerdict:
    """Validate one page's frontmatter against the contract.

    Pure: no filesystem, no published-set knowledge. The corpus gate
    (:func:`validate_tree`) decides *which* pages to pass in. Each rule lives in its
    own helper so the severity of every rule stays visible: an absent required field,
    an unclassifiable page, an unparseable instant, an unmapped ADR status and the two
    path+kind invariants are errors; an unknown ``kind``/``doc_status``/``type`` and a
    non-canonical instant are advisories, exactly as the pinned doc-kitty gate splits
    them.
    """
    kind = resolve_kind(rel_path, frontmatter)
    doc_status = normalise_doc_status(rel_path, frontmatter)

    kind_errors, kind_warnings = _kind_violations(rel_path, frontmatter, kind)
    updated_errors, updated_warnings, updated = _updated_violations(rel_path, frontmatter)

    errors = [
        *_required_field_violations(rel_path, frontmatter),
        *kind_errors,
        *updated_errors,
        *_path_and_kind_violations(rel_path, frontmatter, kind),
    ]
    warnings = [
        *kind_warnings,
        *_doc_status_violations(rel_path, frontmatter),
        *updated_warnings,
        *_type_and_description_violations(rel_path, frontmatter),
    ]

    return PageVerdict(
        path=rel_path,
        errors=tuple(errors),
        warnings=tuple(warnings),
        kind=kind,
        doc_status=doc_status,
        updated=updated,
    )


def _resolve_page_set(*, docs_root: Path, docfx_config: Path | None) -> PublishedPageSet:
    """Ask the single publication authority for the page set, translating refusals."""
    try:
        return resolve_published_pages(docs_root=docs_root, docfx_config=docfx_config)
    except (FileNotFoundError, ValueError) as exc:
        raise CoverageError(f"frontmatter contract gate could not resolve its published page set: {exc}") from exc


def validate_tree(
    *,
    docs_root: Path,
    repo_root: Path,
    docfx_config: Path | None = None,
    only_paths: Iterable[str] | None = None,
) -> ContractReport:
    """Validate every published page against the contract.

    Raises
    ------
    CoverageError
        The resolved page set is empty, or below
        :data:`scripts.docs._published_pages.MINIMUM_EXPECTED_PAGES`. Fails closed:
        the promise is "every published page was checked", and a vacuous or collapsed
        set makes that promise unfalsifiable.
    """
    # A relative docs root is resolved against the caller's repo root, so the CLI
    # default (`docs`) and a test's absolute path behave identically.
    docs_root = docs_root if docs_root.is_absolute() else repo_root / docs_root
    page_set = _resolve_page_set(docs_root=docs_root, docfx_config=docfx_config)
    observed = len(page_set.pages)
    if observed == 0:
        raise CoverageError(
            f"frontmatter contract gate resolved no published pages under {docs_root}; "
            f"source globs were {list(page_set.source_globs)}. A gate that validates zero pages must fail, not pass."
        )
    if observed < MINIMUM_EXPECTED_PAGES:
        raise CoverageError(
            f"frontmatter contract gate resolved {observed} published page(s) under {docs_root}, "
            f"below the required floor of {MINIMUM_EXPECTED_PAGES}. Either the globs under-collect "
            "or the tree has collapsed; both must fail loud."
        )

    scope = None if only_paths is None else {p.replace("\\", "/") for p in only_paths}
    errors: list[Violation] = []
    warnings: list[Violation] = []
    checked = 0
    tree_root = docs_root.parent
    for page in sorted(page_set.pages):
        rel_path = page.as_posix()
        if scope is not None and rel_path not in scope:
            continue
        absolute = tree_root / page
        try:
            text = absolute.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - a published page that cannot be read
            raise CoverageError(f"frontmatter contract gate could not read {rel_path}: {exc}") from exc
        verdict = validate_page(rel_path, parse_frontmatter(text))
        checked += 1
        errors.extend(verdict.errors)
        warnings.extend(verdict.warnings)

    errors.sort(key=lambda v: (v.path, v.field, v.reason))
    warnings.sort(key=lambda v: (v.path, v.field, v.reason))
    return ContractReport(checked_count=checked, errors=tuple(errors), warnings=tuple(warnings))


# ---------------------------------------------------------------------------
# Migration — frontmatter line surgery only
# ---------------------------------------------------------------------------

_FENCE: Final[str] = "---"

#: Keys the migration writes, in the order a missing one is appended to a block.
_WRITE_ORDER: Final[tuple[str, ...]] = ("doc_status", "kind", "updated")


@dataclass(slots=True, frozen=True)
class PageEdit:
    """The planned frontmatter change for one page. Nothing is written to plan it."""

    path: str
    set_values: dict[str, str] = field(default_factory=dict)
    drop_keys: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        """Whether the plan changes nothing."""
        return not self.set_values and not self.drop_keys

    def as_dict(self) -> dict[str, object]:
        """Serialize to the migration's JSON plan shape."""
        return {
            "path": self.path,
            "set": dict(sorted(self.set_values.items())),
            "drop": list(self.drop_keys),
        }


def plan_page(rel_path: str, text: str) -> PageEdit:
    """Compute the migration edit for one page (pure; writes nothing).

    Only keys this mission owns are planned: ``kind``, ``doc_status``, ``updated``,
    and the removal of a Divio ``type``. Every other key — including the ones #6929
    owns — is left exactly as authored.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise ValueError(f"{rel_path}: page has no frontmatter block; the migration cannot add one")
    frontmatter = parse_frontmatter(text)
    set_values: dict[str, str] = {}

    kind = resolve_kind(rel_path, frontmatter)
    if kind is None:
        raise ValueError(
            f"{rel_path}: unclassified page — no rule resolves a kind. "
            "ADR D-7: an unclassified page is a migration failure, not a guess."
        )
    if _frontmatter_str(frontmatter, "kind") != kind:
        set_values["kind"] = kind

    doc_status = normalise_doc_status(rel_path, frontmatter)
    if doc_status is not None and doc_status != _frontmatter_str(frontmatter, "doc_status"):
        set_values["doc_status"] = doc_status

    updated = normalise_updated(rel_path, frontmatter)
    if updated is None:
        raise ValueError(f"{rel_path}: no `updated` and no `date` to derive one from")
    raw_updated = frontmatter.get("updated")
    if isinstance(raw_updated, datetime) or (isinstance(raw_updated, str) and raw_updated.strip() != updated):
        # A date-only or non-Z spelling is rewritten to the canonical form; an already
        # canonical value is left byte-identical, which is what keeps the pass
        # idempotent (NFR-002).
        set_values["updated"] = updated
    elif raw_updated is None:
        set_values["updated"] = updated

    drop_keys: tuple[str, ...] = ("type",) if has_divio_type(frontmatter) else ()
    return PageEdit(path=rel_path, set_values=set_values, drop_keys=drop_keys)



def _closing_fence_index(lines: Sequence[str]) -> int | None:
    """Index of the frontmatter closing fence in ``lines``, or ``None``."""
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            return index
    return None


def body_of(text: str) -> str:
    """Return a page's body: everything from the closing fence onward.

    This is the one definition of "body" in the docs tooling: the immutable-corpus
    rule (ADR D-7) is stated about it, the migration is asserted not to touch it, and
    the body-hash baseline is computed over it. A page with no frontmatter block is
    all body.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return text
    closing = _closing_fence_index(lines)
    if closing is None:
        return text
    return "".join(lines[closing:])


def _render_scalar(key: str, value: str) -> str:
    """Render one ``key: value`` frontmatter line.

    Instants are single-quoted: unquoted, YAML 1.1 loaders hand back a ``datetime``
    rather than the string doc-kitty expects, and the corpus already quotes dates.
    Everything else (``kind``, ``doc_status``) is a plain scalar that survives
    unquoted.
    """
    if key == "updated":
        return f"{key}: '{value}'"
    return f"{key}: {value}"


def apply_edit(text: str, edit: PageEdit) -> str:
    """Apply ``edit`` to ``text`` by rewriting frontmatter lines only.

    The body — everything from the closing fence onward — is copied verbatim, which is
    what makes the immutable-corpus rule (ADR D-7) true by construction rather than by
    inspection. Re-serialising the block through ``ruamel`` would reformat every page
    and destroy the reviewability of a 670-file diff, so the edits are line surgery:

    * a key that exists is replaced in place (its line(s) removed, one line written);
    * a key that does not exist is appended at the end of the block in
      :data:`_WRITE_ORDER`;
    * a key in ``drop_keys`` is removed.

    Refuses (``ValueError``) when an owned key spans more than one line, because a
    block-scalar ``updated`` means a human wrote something this migration does not
    understand, and silently collapsing it would lose content.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        raise ValueError(f"{edit.path}: page has no frontmatter block")
    closing = _closing_fence_index(lines)
    if closing is None:
        raise ValueError(f"{edit.path}: unterminated frontmatter block")

    body_and_rest = "".join(lines[closing:])  # the closing fence and the body
    head = lines[1:closing]  # frontmatter lines only, without either fence

    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    owned = set(edit.set_values) | set(edit.drop_keys)
    kept: list[str] = []
    index = 0
    while index < len(head):
        line = head[index]
        key = _frontmatter_key(line)
        if key is None or key not in owned:
            kept.append(line)
            index += 1
            continue
        # Consume any continuation lines of this key, then decide.
        span = 1
        while index + span < len(head) and _is_continuation(head[index + span]):
            span += 1
        if span > 1:
            raise ValueError(
                f"{edit.path}: `{key}` spans {span} lines; the migration only rewrites "
                "single-line scalars and will not collapse an authored block scalar"
            )
        if key in edit.set_values:
            kept.append(_render_scalar(key, edit.set_values[key]) + newline)
        index += span

    appended = [
        _render_scalar(key, edit.set_values[key]) + newline
        for key in _WRITE_ORDER
        if key in edit.set_values and _frontmatter_key_present(head, key) is False
    ]
    return "".join([lines[0], *kept, *appended, body_and_rest])


def _frontmatter_key(line: str) -> str | None:
    """Return the YAML key a frontmatter line opens, or ``None``."""
    if not line.strip() or line.lstrip().startswith("#"):
        return None
    if line[:1] in (" ", "\t"):
        return None
    key, sep, _ = line.partition(":")
    if not sep:
        return None
    key = key.strip()
    return key or None


def _is_continuation(line: str) -> bool:
    """Whether ``line`` continues a YAML value started on the previous line."""
    stripped = line.strip()
    return bool(stripped) and (line[:1] in (" ", "\t") or stripped.startswith("- "))


def _frontmatter_key_present(head: Sequence[str], key: str) -> bool:
    """Whether ``head`` already carries ``key`` (a single-line scalar)."""
    return any(_frontmatter_key(line) == key for line in head)


def apply_plan(*, docs_root: Path, repo_root: Path, write: bool) -> list[PageEdit]:
    """Compute (and optionally write) the migration over every published page.

    The page set is the same publication authority the gate uses, so "the corpus" means
    one thing in both directions. Idempotent: a second pass over an already migrated
    tree produces no non-empty :class:`PageEdit`.
    """
    docs_root = docs_root if docs_root.is_absolute() else repo_root / docs_root
    page_set = _resolve_page_set(docs_root=docs_root, docfx_config=None)
    tree_root = docs_root.parent
    edits: list[PageEdit] = []
    for page in sorted(page_set.pages):
        absolute = tree_root / page
        text = absolute.read_text(encoding="utf-8")
        edit = plan_page(page.as_posix(), text)
        if edit.is_empty():
            continue
        edits.append(edit)
        if write:
            absolute.write_text(apply_edit(text, edit), encoding="utf-8")
    return edits


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the gate's CLI parser."""
    parser = argparse.ArgumentParser(
        prog="frontmatter_contract",
        description=(
            "Check (and, with --write, mechanically migrate) the docs frontmatter "
            "contract that doc-kitty requires: title, description, doc_status, "
            "updated, kind. Validates the published sections only."
        ),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs tree whose published subset is checked (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Base for rendering repo-relative page paths (default: cwd).",
    )
    parser.add_argument(
        "--docfx-config",
        type=Path,
        default=None,
        help="Explicit docfx.json declaring the published set (default: <docs-root>/docfx.json).",
    )
    parser.add_argument(
        "--changed-from",
        metavar="BASE_REF",
        default=None,
        help="Limit reported violations to published pages changed since BASE_REF.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print the migration plan for the published tree; write nothing.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the migration plan to the published tree (frontmatter lines only).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report or plan as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any hard contract error is reported (warnings never fail).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)

    if args.check or args.write:
        try:
            edits = apply_plan(docs_root=args.docs_root, repo_root=args.repo_root, write=args.write)
        except (CoverageError, ValueError) as exc:
            sys.stderr.write(f"frontmatter_contract: ERROR: {exc}\n")
            return EXIT_COVERAGE_FAILURE
        if args.json:
            sys.stdout.write(json.dumps([e.as_dict() for e in edits], indent=2, sort_keys=True) + "\n")
        else:
            verb = "applied" if args.write else "planned"
            sys.stdout.write(f"frontmatter_contract: {verb} {len(edits)} page edit(s).\n")
            for edit in edits:
                changes = ", ".join(
                    [f"{k}={v}" for k, v in sorted(edit.set_values.items())]
                    + [f"-{k}" for k in edit.drop_keys]
                )
                sys.stdout.write(f"  {edit.path}: {changes}\n")
        return 0

    only_paths: Iterable[str] | None = None
    if args.changed_from is not None:
        try:
            only_paths = resolve_changed_files(args.repo_root, args.changed_from)
        except GitDiffError as exc:
            sys.stderr.write(f"frontmatter_contract: ERROR: {exc}\n")
            return EXIT_COVERAGE_FAILURE

    try:
        report = validate_tree(
            docs_root=args.docs_root,
            repo_root=args.repo_root,
            docfx_config=args.docfx_config,
            only_paths=only_paths,
        )
    except CoverageError as exc:
        sys.stderr.write(f"frontmatter_contract: COVERAGE FAILURE: {exc}\n")
        return EXIT_COVERAGE_FAILURE

    if args.json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"frontmatter_contract: checked {report.checked_count} page(s); "
            f"{len(report.errors)} error(s); {len(report.warnings)} warning(s).\n"
        )
        for violation in report.errors:
            sys.stdout.write(f"  ERROR {violation.path} [{violation.field}] {violation.reason}: {violation.detail}\n")
        for violation in report.warnings:
            sys.stdout.write(f"  WARN  {violation.path} [{violation.field}] {violation.reason}: {violation.detail}\n")
    if args.strict and report.errors:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
