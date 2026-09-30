"""One-command ADR index + inventory-lockfile freshener.

Adding an ADR under ``docs/adr/<era>/`` (era = ``1.x`` | ``2.x`` | ``3.x`` | ``4.x``; new ADRs use ``4.x``)
requires two index updates the ``docs-freshness`` CI gate enforces:

1. A :class:`~scripts.docs._inventory.PageInventoryEntry` row in
   ``docs/development/3-2-page-inventory.yaml`` — a **generated lockfile**,
   regenerated from every page's frontmatter.
2. A table row ``| YYYY-MM-DD | [Title](filename.md) |`` in the era's
   ``docs/adr/<era>/index.md`` index (or its legacy ``README.md`` index).

Agents repeatedly trip the gate (``LEAK-MISSING-INVENTORY``,
``INVENTORY-INCOMPLETE``, ``INVENTORY-LOCKFILE-DRIFT``) by forgetting one of
these. This tool freshens **both** in one command, reusing the canonical
machinery in :mod:`scripts.docs.inventory_lockfile` and
:mod:`scripts.docs._inventory` — it never forks the inventory schema.

Usage::

    python scripts/docs/freshen_adr_inventory.py docs/adr/3.x/my-adr.md
    python scripts/docs/freshen_adr_inventory.py --all
    python scripts/docs/freshen_adr_inventory.py --check docs/adr/3.x/my-adr.md

* **Inventory:** the page inventory is regenerated wholesale from frontmatter
  (``render_lockfile(generate_inventory(...))``), so it auto-picks up every new
  doc — including new ADRs. On a clean tree this is a no-op.
* **ADR index rows:** for each target ADR the era landing page's index table gets a
  new row, inserted date-ascending, idempotently (a basename already linked
  **within the index table** is skipped; a prose link elsewhere does not count).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from scripts.docs._inventory import parse_frontmatter
from scripts.docs.inventory_lockfile import (
    DEFAULT_INVENTORY_PATH,
    generate_inventory,
    render_lockfile,
)

__all__ = [
    "AdrMeta",
    "FreshenResult",
    "build_parser",
    "detect_missing_adrs",
    "freshen",
    "main",
]


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_ADR_SUBDIR: Final[str] = "adr"
_INDEX_NAME: Final[str] = "index.md"
_README_NAME: Final[str] = "README.md"
_ERA_RE: Final[re.Pattern[str]] = re.compile(r"^\d+\.x$")
_TITLE_PREFIX: Final[str] = "ADR: "
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")

# ADR index table detection. The header carries both "Date" and "Title"; the
# next line is the markdown separator; data rows follow until the first
# non-pipe line.
_TABLE_HEADER_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*\|.*\bdate\b.*\|.*\btitle\b.*\|\s*$", re.IGNORECASE
)
_TABLE_SEP_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|[\s:|-]*-[\s:|-]*\|\s*$")
_TABLE_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\s*\|.*\|\s*$")
_INDEX_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*##\s+Index\s*$", re.IGNORECASE
)


class FreshenError(Exception):
    """Raised for an unrecoverable target/era-README problem."""


@dataclass(slots=True, frozen=True)
class AdrMeta:
    """Frontmatter-derived facts about one ADR needed for its README row."""

    basename: str
    title: str
    date: str

    def row(self) -> str:
        """Render the canonical era-README index row for this ADR."""
        return f"| {self.date} | [{self.title}]({self.basename}) |"


@dataclass(slots=True, frozen=True)
class FreshenResult:
    """Outcome of a freshen/check run (what changed, what's still stale)."""

    inventory_written: bool
    readme_rows_added: tuple[str, ...]
    missing_rows: tuple[str, ...]
    inventory_stale: bool

    @property
    def is_clean(self) -> bool:
        """True iff nothing is stale (safe ``--check`` exit)."""
        return not self.missing_rows and not self.inventory_stale


# --------------------------------------------------------------------------- #
# Era index resolution
# --------------------------------------------------------------------------- #


def _era_index_for(adr_path: Path, docs_root: Path) -> Path:
    """Resolve the era index for an ADR at ``docs/adr/<era>/<name>.md``.

    Validates the ADR lives **inside** ``docs_root`` at exactly
    ``adr/<era>/<file>.md`` (``<era>`` matching ``N.x``). Checking the directory
    *names* alone is not enough — an out-of-tree path like ``/tmp/adr/3.x/foo.md``
    would otherwise be accepted and the tool would edit ``/tmp/adr/3.x/README.md``.
    A path that escapes the docs root, or does not match the exact shape, is a
    hard error rather than a destructive guess.
    """
    try:
        rel_parts = adr_path.resolve().relative_to(docs_root.resolve()).parts
    except ValueError:  # adr_path is not inside docs_root
        rel_parts = ()
    if (
        len(rel_parts) != 3
        or rel_parts[0] != _ADR_SUBDIR
        or not _ERA_RE.match(rel_parts[1])
    ):
        raise FreshenError(
            f"{adr_path} is not under {docs_root.name}/{_ADR_SUBDIR}/<era>/<file>.md "
            f"(era must match N.x and the path must live inside the docs root)"
        )
    canonical_index = adr_path.parent / _INDEX_NAME
    if canonical_index.exists():
        return canonical_index
    return adr_path.parent / _README_NAME


# --------------------------------------------------------------------------- #
# ADR frontmatter -> row facts
# --------------------------------------------------------------------------- #


def _clean_title(raw: object) -> str:
    """Collapse whitespace and strip a leading ``ADR: `` prefix from a title."""
    text = str(raw) if raw is not None else ""
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if text.startswith(_TITLE_PREFIX):
        text = text[len(_TITLE_PREFIX) :].strip()
    return text


def _read_adr_meta(adr_path: Path) -> AdrMeta:
    """Parse an ADR's frontmatter into the facts its README row needs."""
    try:
        text = adr_path.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable target — surface, don't guess
        raise FreshenError(f"cannot read ADR {adr_path}: {exc}") from exc
    frontmatter = parse_frontmatter(text)
    title = _clean_title(frontmatter.get("title"))
    date = str(frontmatter.get("date", "")).strip()
    if not title or not date:
        raise FreshenError(
            f"{adr_path} frontmatter is missing a title and/or date "
            f"(title={title!r}, date={date!r})"
        )
    return AdrMeta(basename=adr_path.name, title=title, date=date)


# --------------------------------------------------------------------------- #
# README table editing
# --------------------------------------------------------------------------- #


def _find_adr_table(lines: list[str]) -> tuple[int, int]:
    """Return ``(data_start, data_end)`` for the ADR index table's data rows.

    ``data_start`` is the first data-row index (after the header + separator);
    ``data_end`` is one past the last contiguous data row. Raises if no
    ``| Date | Title |`` table exists.
    """
    for index in range(len(lines) - 1):
        if _TABLE_HEADER_RE.match(lines[index]) and _TABLE_SEP_RE.match(
            lines[index + 1]
        ):
            data_start = index + 2
            data_end = data_start
            while data_end < len(lines) and _TABLE_ROW_RE.match(lines[data_end]):
                data_end += 1
            return data_start, data_end
    raise FreshenError("no ADR index table (`| Date | Title |`) found")


def _declares_adr_index(lines: list[str]) -> bool:
    """True iff a landing page declares a maintained ADR index section."""
    return any(_INDEX_HEADING_RE.match(line) for line in lines)


def _row_date(row: str) -> str:
    """Extract the first (date) cell from a markdown table row."""
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    return cells[0] if cells else ""


def _insertion_index(rows: list[str], date: str) -> int:
    """Index at which a new row for ``date`` keeps the table date-ascending.

    Inserts after every existing row whose date is ``<= date`` (so a new row
    lands after same-date neighbours), preserving ascending order.
    """
    position = len(rows)
    for offset, row in enumerate(rows):
        if _row_date(row) > date:
            position = offset
            break
    return position


def _rows_link_basename(rows: list[str], basename: str) -> bool:
    """True iff any ADR-table *data row* links ``basename``.

    Table-scoped on purpose: a link to the ADR in README prose (outside the
    index table) must NOT count as "already in the table", or the index row
    would be wrongly skipped. Shared by write-mode (:func:`_insert_readme_row`)
    and check-mode (:func:`_readme_has_row`) so both agree.
    """
    needle = f"]({basename})"
    return any(needle in row for row in rows)


def _insert_readme_row(readme_text: str, meta: AdrMeta) -> tuple[str, bool]:
    """Insert ``meta``'s row into the ADR table, idempotent + date-ordered.

    Returns ``(new_text, changed)``. ``changed`` is ``False`` only when the
    ADR's basename is already linked **within the index table** (a prose link
    elsewhere does not count — see :func:`_rows_link_basename`).
    """
    trailing_newline = readme_text.endswith("\n")
    lines = readme_text.splitlines()
    data_start, data_end = _find_adr_table(lines)
    rows = lines[data_start:data_end]

    if _rows_link_basename(rows, meta.basename):
        return readme_text, False

    offset = _insertion_index(rows, meta.date)
    lines.insert(data_start + offset, meta.row())

    new_text = "\n".join(lines)
    if trailing_newline:
        new_text += "\n"
    return new_text, True


def _freshen_readme_row(adr_path: Path, docs_root: Path) -> str | None:
    """Add ``adr_path``'s row to its era index. Return basename if changed."""
    meta = _read_adr_meta(adr_path)
    era_index = _era_index_for(adr_path, docs_root)
    if not era_index.exists():
        raise FreshenError(f"era index not found: {era_index}")
    original = era_index.read_text(encoding="utf-8")
    updated, changed = _insert_readme_row(original, meta)
    if changed:
        era_index.write_text(updated, encoding="utf-8")
        return meta.basename
    return None


def _readme_has_row(adr_path: Path, docs_root: Path) -> bool:
    """True iff ``adr_path``'s basename is linked in its era index table.

    Table-aware (reuses :func:`_find_adr_table` + :func:`_rows_link_basename`) so
    ``--check`` agrees with write-mode: a prose link outside the table is not a
    row, and a README without a table has no row.
    """
    era_index = _era_index_for(adr_path, docs_root)
    if not era_index.exists():
        return False
    lines = era_index.read_text(encoding="utf-8").splitlines()
    try:
        data_start, data_end = _find_adr_table(lines)
    except FreshenError:
        if _declares_adr_index(lines):
            raise
        return False
    return _rows_link_basename(lines[data_start:data_end], adr_path.name)


# --------------------------------------------------------------------------- #
# Inventory regeneration
# --------------------------------------------------------------------------- #


def _inventory_path(repo_root: Path) -> Path:
    """Resolve the committed inventory lockfile under ``repo_root``."""
    return repo_root / DEFAULT_INVENTORY_PATH


def _rendered_inventory(docs_root: Path, repo_root: Path) -> str:
    """Render the fresh inventory lockfile string from frontmatter."""
    entries = generate_inventory(docs_root, repo_root=repo_root)
    return render_lockfile(entries)


def _regenerate_inventory(docs_root: Path, repo_root: Path) -> bool:
    """Rewrite the committed inventory from frontmatter. Return True if changed."""
    target = _inventory_path(repo_root)
    fresh = _rendered_inventory(docs_root, repo_root)
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current == fresh:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fresh, encoding="utf-8")
    return True


def _inventory_is_stale(docs_root: Path, repo_root: Path) -> bool:
    """True iff the committed inventory diverges from a fresh generation."""
    target = _inventory_path(repo_root)
    if not target.exists():
        return True
    return target.read_text(encoding="utf-8") != _rendered_inventory(
        docs_root, repo_root
    )


# --------------------------------------------------------------------------- #
# Target discovery
# --------------------------------------------------------------------------- #


def _era_has_table(era_index: Path) -> bool:
    """True iff ``era_index`` exists and contains an ADR index table."""
    if not era_index.exists():
        return False
    try:
        _find_adr_table(era_index.read_text(encoding="utf-8").splitlines())
    except FreshenError:
        return False
    return True


def detect_missing_adrs(docs_root: Path) -> list[Path]:
    """Every ADR under ``docs/adr/<era>/`` missing from its era index table.

    Only eras whose landing page actually maintains an index table are considered —
    legacy eras without a table (e.g. 1.x/2.x) are intentionally skipped rather
    than back-filled with a table they never carried.
    """
    adr_root = docs_root / _ADR_SUBDIR
    if not adr_root.is_dir():
        return []
    missing: list[Path] = []
    for era_dir in sorted(p for p in adr_root.iterdir() if p.is_dir()):
        if not _ERA_RE.match(era_dir.name):
            continue
        canonical_index = era_dir / _INDEX_NAME
        if canonical_index.exists() and not _era_has_table(canonical_index):
            canonical_lines = canonical_index.read_text(encoding="utf-8").splitlines()
            if _declares_adr_index(canonical_lines):
                raise FreshenError(
                    f"canonical era index has no ADR table: {canonical_index}"
                )
        era_index = canonical_index if canonical_index.exists() else era_dir / _README_NAME
        if not _era_has_table(era_index):
            continue
        for adr_path in sorted(era_dir.glob("*.md")):
            if adr_path.name in {_INDEX_NAME, _README_NAME}:
                continue
            if not _readme_has_row(adr_path, docs_root):
                missing.append(adr_path)
    return missing


def _targets_missing_rows(adr_paths: list[Path], docs_root: Path) -> list[str]:
    """Basenames of ``adr_paths`` that lack their era README row."""
    return [p.name for p in adr_paths if not _readme_has_row(p, docs_root)]


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def freshen(
    adr_paths: list[Path],
    *,
    docs_root: Path,
    repo_root: Path,
    check: bool,
) -> FreshenResult:
    """Freshen (or, in ``check`` mode, verify) both indexes.

    In write mode: add each ADR's README row, then regenerate the inventory.
    In check mode: never write — report which targeted ADRs miss their row and
    whether the committed inventory is stale.
    """
    if check:
        return FreshenResult(
            inventory_written=False,
            readme_rows_added=(),
            missing_rows=tuple(_targets_missing_rows(adr_paths, docs_root)),
            inventory_stale=_inventory_is_stale(docs_root, repo_root),
        )

    added: list[str] = []
    for adr_path in adr_paths:
        basename = _freshen_readme_row(adr_path, docs_root)
        if basename is not None:
            added.append(basename)
    inventory_written = _regenerate_inventory(docs_root, repo_root)
    return FreshenResult(
        inventory_written=inventory_written,
        readme_rows_added=tuple(added),
        missing_rows=(),
        inventory_stale=False,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    """Build the ``freshen_adr_inventory`` CLI parser."""
    parser = argparse.ArgumentParser(
        prog="freshen_adr_inventory",
        description=(
            "Freshen BOTH ADR indexes in one command: regenerate the "
            "page-inventory lockfile from frontmatter AND add each ADR's row "
            "to its era README table. Idempotent and date-ordered."
        ),
    )
    parser.add_argument(
        "adr_paths",
        nargs="*",
        type=Path,
        help="Explicit ADR .md paths under docs/adr/<era>/.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Auto-detect every ADR missing from its era README table.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify only (no writes): exit non-zero if the inventory is stale "
            "or any targeted ADR is missing its README row."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repo root (default: current working directory).",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Docs root (default: <repo-root>/docs).",
    )
    return parser


def _resolve_targets(args: argparse.Namespace, docs_root: Path) -> list[Path]:
    """Resolve the ADR targets from explicit paths and/or ``--all``."""
    targets: list[Path] = list(args.adr_paths)
    if args.all:
        known = {p.resolve() for p in targets}
        for detected in detect_missing_adrs(docs_root):
            if detected.resolve() not in known:
                targets.append(detected)
    return targets


def _emit_check(result: FreshenResult) -> int:
    """Print the check-mode summary and return the exit code."""
    for basename in result.missing_rows:
        sys.stdout.write(f"ADR-README-ROW-MISSING {basename}\n")
    if result.inventory_stale:
        sys.stdout.write("INVENTORY-LOCKFILE-DRIFT (committed inventory is stale)\n")
    status = "clean" if result.is_clean else "STALE"
    sys.stdout.write(
        f"freshen_adr_inventory --check: {status} "
        f"(missing_rows={len(result.missing_rows)} "
        f"inventory_stale={result.inventory_stale})\n"
    )
    return 0 if result.is_clean else 1


def _emit_write(result: FreshenResult) -> int:
    """Print the write-mode summary and return the exit code."""
    for basename in result.readme_rows_added:
        sys.stdout.write(f"README-ROW-ADDED {basename}\n")
    inv = "regenerated" if result.inventory_written else "unchanged"
    sys.stdout.write(
        f"freshen_adr_inventory: rows_added={len(result.readme_rows_added)} "
        f"inventory={inv}\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    repo_root: Path = args.repo_root
    docs_root: Path = args.docs_root if args.docs_root is not None else repo_root / "docs"

    try:
        targets = _resolve_targets(args, docs_root)
        result = freshen(
            targets, docs_root=docs_root, repo_root=repo_root, check=args.check
        )
    except FreshenError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    return _emit_check(result) if args.check else _emit_write(result)


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
