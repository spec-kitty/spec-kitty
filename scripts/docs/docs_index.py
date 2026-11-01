"""Frontmatter/heading -> docs retrieval index generator (FR-001 / NFR-001).

Build-tooling half of the packaging split documented in ``data-model.md``
("Module layering"): the schema, deterministic renderer/parser, drift
comparator, and query store live in the **packaged**
``specify_cli.docs.index_model`` (imported *down* from here, ``scripts ->
src``, legal) so the installed CLI can load them without ``scripts`` on its
path (excluded from the wheel). This module owns everything that only
build-tooling/CI needs: walking ``docs/**/*.md``, parsing frontmatter,
scanning headings, and the ``--write``/``--strict`` CLI.

Mirrors the proven ``inventory_lockfile.py`` generate/render/compare/CLI
shape (C-004): the generator never re-implements ``parse_frontmatter`` or the
canonical ``slugify`` — both are imported, not forked (DIRECTIVE_044). This
module never widens or imports ``scripts.docs._inventory.PageInventoryEntry``
(C-001) — the retrieval index is a sibling artifact with its own schema.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from scripts.docs._inventory import parse_frontmatter
from scripts.docs.frontmatter_contract import KIND_TO_DIVIO_TYPE
from scripts.docs.bulk_ref_rewrite import split_frontmatter
from scripts.docs.generate_kitty_specs_docs import slugify

from specify_cli.docs.index_model import (
    DEFAULT_INDEX_PATH,
    Anchor,
    DivioType,
    DocsQueryEntry,
    IndexDrift,
    compare_index,
    parse_index,
    render_index,
)
from scripts.docs._page_scope import iter_docs_pages

__all__ = [
    "DEFAULT_DOCS_ROOT",
    "IndexReport",
    "build_parser",
    "generate_index",
    "main",
    "resolve_abstract",
    "resolve_title",
    "run_generate_and_compare",
    "scan_headings",
    "slug_for_headings",
]


DEFAULT_DOCS_ROOT: Final[str] = "docs/"

# Level-2/3 ATX headings only (``##``/``###``); a longer hash run (``####``)
# fails the required trailing-whitespace match once the 2-3 group backtracks,
# so level-4+ headings are correctly excluded without a separate check.
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^(#{2,3})\s+(\S.*)$")
_H1_RE: Final[re.Pattern[str]] = re.compile(r"^#\s+(\S.*)$")
_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*```")

_FM_TITLE: Final[str] = "title"
_FM_DESCRIPTION: Final[str] = "description"
# The Divio axis is read from doc-kitty's ``kind:`` key (#6931); ``type:`` names the
# *section* in doc-kitty (its ADR-0009), so the Divio meaning moved to ``kind``.
_FM_KIND: Final[str] = "kind"


# ---------------------------------------------------------------------------
# Pure body helpers (T003)
# ---------------------------------------------------------------------------


def _iter_unfenced_lines(body: str) -> Iterator[str]:
    """Yield ``body`` lines with fenced (``` ```) code blocks removed.

    A stray ``## `` inside a fenced code sample must never be read as a
    heading, title, or abstract source (see module risk note).
    """
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield line


def scan_headings(body: str) -> list[tuple[int, str]]:
    """Return ``(level, text)`` for each ``##``/``###`` heading, in document order."""
    headings: list[tuple[int, str]] = []
    for line in _iter_unfenced_lines(body):
        match = _HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def resolve_title(frontmatter: Mapping[str, Any], body: str, path: Path) -> str:
    """Total title precedence: frontmatter ``title`` -> first ``# H1`` -> path stem."""
    title = frontmatter.get(_FM_TITLE)
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in _iter_unfenced_lines(body):
        match = _H1_RE.match(line)
        if match:
            return match.group(1).strip()
    return path.stem


def resolve_abstract(frontmatter: Mapping[str, Any], body: str) -> str:
    """Total abstract precedence: frontmatter ``description`` -> first paragraph -> ``""``.

    "First paragraph" is the first run of non-blank, non-heading lines,
    joined with a single space. ADR/changelog pages with neither a
    ``description`` nor a leading prose paragraph resolve to ``""`` (the
    exemption ``description_length_check.py`` already carves out for
    ``docs/adr/``).
    """
    description = frontmatter.get(_FM_DESCRIPTION)
    if isinstance(description, str) and description.strip():
        return description.strip()

    paragraph: list[str] = []
    for line in _iter_unfenced_lines(body):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    return " ".join(paragraph)


def slug_for_headings(texts: list[str]) -> list[str]:
    """Slugify each heading text, disambiguating duplicates with an ordinal suffix.

    Mirrors the ``assign_anchor_ids`` pattern (``generate_kitty_specs_docs.py``):
    first occurrence keeps the bare slug, the 2nd/3rd/... duplicate gets a
    ``-2``/``-3``/... suffix, in the order the headings appear on the page.
    Uses the canonical ``slugify`` — never a re-implementation (DIRECTIVE_044).
    """
    seen: dict[str, int] = {}
    slugs: list[str] = []
    for text in texts:
        base = slugify(text, fallback="section")
        occurrence = seen.get(base, 0)
        slugs.append(base if occurrence == 0 else f"{base}-{occurrence + 1}")
        seen[base] = occurrence + 1
    return slugs


def _coerce_divio_type(raw: object) -> DivioType:
    """Map a frontmatter ``kind`` value to its Divio quadrant, defaulting to ``none``.

    Reads through the contract's :data:`KIND_TO_DIVIO_TYPE` so the retrieval index
    and the frontmatter-contract gate share one reading of ``kind``.
    """
    if isinstance(raw, str):
        return KIND_TO_DIVIO_TYPE.get(raw.strip(), DivioType.NONE)
    return DivioType.NONE


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _relative_posix(path: Path, anchor: Path) -> str:
    """Render ``path`` as a forward-slash repo-relative string under ``anchor``."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(anchor).as_posix()
    except ValueError:
        return resolved.as_posix()


def _entry_for_page(md_path: Path, rel_path: str, text: str) -> DocsQueryEntry:
    """Build one :class:`DocsQueryEntry` from a page's raw text."""
    frontmatter = parse_frontmatter(text)
    _, body = split_frontmatter(text)
    headings = scan_headings(body)
    slugs = slug_for_headings([heading_text for _level, heading_text in headings])
    anchors = tuple(
        Anchor(slug=slug, text=heading_text, level=level)
        for slug, (level, heading_text) in zip(slugs, headings, strict=True)
    )
    return DocsQueryEntry(
        path=rel_path,
        title=resolve_title(frontmatter, body, md_path),
        divio_type=_coerce_divio_type(frontmatter.get(_FM_KIND)).value,
        anchors=anchors,
        abstract=resolve_abstract(frontmatter, body),
    )


def generate_index(docs_root: Path, *, repo_root: Path | None = None) -> list[DocsQueryEntry]:
    """Walk ``docs_root`` and emit one entry per ``.md`` page.

    Entries are sorted alphabetically by repo-relative ``path`` (NFR-001).
    ``repo_root`` anchors the emitted path (defaults to ``docs_root``'s
    parent), mirroring ``inventory_lockfile.py::generate_inventory``.
    """
    anchor = (repo_root or docs_root.parent).resolve()
    entries: list[DocsQueryEntry] = []
    for md_path in iter_docs_pages(docs_root):
        rel_path = _relative_posix(md_path, anchor)
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        entries.append(_entry_for_page(md_path, rel_path, text))
    entries.sort(key=lambda entry: entry.path)
    return entries


# ---------------------------------------------------------------------------
# Generate-and-compare report + CLI
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class IndexReport:
    """Outcome of one generate-and-compare run."""

    docs_root: str
    index_path: str
    generated_rows: int
    committed_rows: int
    drift: IndexDrift
    strict: bool
    exit_code: int


def run_generate_and_compare(
    docs_root: Path,
    index_path: Path,
    *,
    write: bool,
    strict: bool,
) -> IndexReport:
    """Generate the index, optionally write it, and diff against the committed file.

    ``write=True`` refreshes ``index_path`` in place *before* the drift
    comparison, so an immediately-following ``--strict`` run (with
    ``write=False``) exits ``0`` iff the committed file matches the tree.
    """
    generated_entries = generate_index(docs_root)
    generated_text = render_index(generated_entries)

    if write:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(generated_text, encoding="utf-8")

    committed_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    drift = compare_index(committed_text, generated_text)
    exit_code = 1 if (strict and drift.has_drift) else 0

    return IndexReport(
        docs_root=str(docs_root),
        index_path=str(index_path),
        generated_rows=len(generated_entries),
        committed_rows=len(parse_index(committed_text)),
        drift=drift,
        strict=strict,
        exit_code=exit_code,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the generate-and-compare CLI parser."""
    parser = argparse.ArgumentParser(
        prog="docs_index",
        description=(
            "Generate the Common Docs retrieval index "
            f"({DEFAULT_INDEX_PATH}) from docs/**/*.md frontmatter + headings "
            "and compare it against the committed file. Report-only by "
            "default (exit 0); --strict makes drift fail; --write refreshes "
            "the committed file in place."
        ),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs root to walk (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path(DEFAULT_INDEX_PATH),
        help=f"Committed index file (default: {DEFAULT_INDEX_PATH}).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate and write the index file in place before comparing.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the committed index drifts from the tree.",
    )
    return parser


def _emit_summary(report: IndexReport) -> None:
    """Print a deterministic one-line + per-path drift summary to stdout."""
    drift = report.drift
    for path in drift.added:
        sys.stdout.write(f"DOCS-INDEX-DRIFT added {path}\n")
    for path in drift.removed:
        sys.stdout.write(f"DOCS-INDEX-DRIFT removed {path}\n")
    for path in drift.changed:
        sys.stdout.write(f"DOCS-INDEX-DRIFT changed {path}\n")
    sys.stdout.write(
        f"docs_index: exit={report.exit_code} generated={report.generated_rows} "
        f"committed={report.committed_rows} drift={drift.has_drift} "
        f"({drift.summary()})\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    report = run_generate_and_compare(
        docs_root=args.docs_root,
        index_path=args.index,
        write=args.write,
        strict=args.strict,
    )
    _emit_summary(report)
    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
