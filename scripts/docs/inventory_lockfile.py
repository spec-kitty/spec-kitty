"""Frontmatter -> inventory lockfile generator (FR-006 / NFR-004 / SC-006).

Mission ``common-docs-consolidation`` ADR ``2026-06-27-1`` decision D1 makes
**in-file frontmatter the per-page metadata SSOT**. The page inventory
(``docs/development/page-inventory.yaml``) is no longer hand-maintained;
it is **regenerated FROM frontmatter** as a validated lockfile:

1. Walk ``docs/**/*.md``.
2. Parse each page's YAML frontmatter.
3. Map frontmatter -> :class:`~scripts.docs._inventory.PageInventoryEntry`
   (reusing the canonical schema — *not* a fork).
4. Emit a deterministic, byte-stable rollup (alphabetical by ``path``).

The freshness gate (``check_docs_freshness``) regenerates the rollup and
compares it against the committed file: any divergence is *drift*. In Mission
A this is **report-only** — the generator and the compare exist and run, but
exit ``0`` (a wired-but-off ``--strict`` flips drift to a non-zero exit so the
seam is symmetric with the other rulers). Mission B makes the gate blocking
and backfills frontmatter so the committed rollup converges to the generation.

The retired ``citation_refs`` field (decision D1) is **not** emitted; the
schema reuses :class:`PageInventoryEntry`, from which the field was removed.

This module never writes to ``docs/`` or to the inventory; it only reads the
tree and, optionally, writes a JSON report when ``--report`` is supplied.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from scripts.docs._inventory import (
    DivioType,
    LoadError,
    PageInventoryEntry,
    VersionTag,
    load_inventory,
    parse_frontmatter,
)

__all__ = [
    "DEFAULT_DOCS_ROOT",
    "DEFAULT_INVENTORY_PATH",
    "InventoryDrift",
    "build_parser",
    "compare_inventories",
    "entry_for_page",
    "generate_inventory",
    "main",
    "parse_frontmatter",
    "render_lockfile",
]


DEFAULT_INVENTORY_PATH: Final[str] = "docs/development/page-inventory.yaml"
DEFAULT_DOCS_ROOT: Final[str] = "docs/"

# Frontmatter key carrying the canonical version tier (decision D1). Absent
# today on most pages; Mission B backfills it. When absent the generator
# defaults to ``current`` so the rollup is total over the tree (report-only).
_FM_VERSION_TAG: Final[str] = "version_tag"
# The Divio axis lives under the existing ``type:`` frontmatter key.
_FM_DIVIO_TYPE: Final[str] = "type"
_FM_OWNING_WORKSTREAM: Final[str] = "owning_workstream"
_FM_NOTES: Final[str] = "notes"

_DEFAULT_OWNING_WORKSTREAM: Final[str] = "none"


# ---------------------------------------------------------------------------
# Drift result
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class InventoryDrift:
    """Structured difference between a fresh generation and the committed rollup.

    ``has_drift`` is the **returned RED signal** the linchpin self-test asserts
    on — distinct from the process exit code, which stays ``0`` in report-only
    mode. Each tuple holds repo-relative ``path`` values, alphabetically sorted
    for a deterministic, byte-stable diff.
    """

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def has_drift(self) -> bool:
        """True iff the generation diverges from the committed rollup."""
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        """One-line human summary of the drift."""
        return (
            f"added={len(self.added)} removed={len(self.removed)} "
            f"changed={len(self.changed)}"
        )


# ---------------------------------------------------------------------------
# Frontmatter -> entry mapping
# ---------------------------------------------------------------------------


def _coerce_version_tag(raw: object) -> VersionTag:
    """Map a frontmatter ``version_tag`` value to :class:`VersionTag`.

    Defaults to ``current`` when absent or unrecognized (report-only: the
    backfill that populates real tags is Mission B).
    """
    if isinstance(raw, str):
        try:
            return VersionTag(raw.strip())
        except ValueError:
            return VersionTag.CURRENT
    return VersionTag.CURRENT


def _coerce_divio_type(raw: object) -> DivioType:
    """Map a frontmatter ``type`` value to :class:`DivioType`."""
    if isinstance(raw, str):
        try:
            return DivioType(raw.strip())
        except ValueError:
            return DivioType.NONE
    return DivioType.NONE


def _coerce_notes(raw: object) -> str | None:
    """Coerce a frontmatter ``notes`` value to ``str | None``."""
    if isinstance(raw, str) and raw.strip():
        return raw
    return None


def entry_for_page(rel_path: str, frontmatter: Mapping[str, Any]) -> PageInventoryEntry:
    """Build a :class:`PageInventoryEntry` from one page's frontmatter.

    ``current_target`` is *derived* from the tag (``current`` -> ``True``,
    everything else -> ``False``) so the load-time cross-field invariants in
    :mod:`scripts.docs._inventory` always hold for a generated row.
    """
    tag = _coerce_version_tag(frontmatter.get(_FM_VERSION_TAG))
    divio_type = _coerce_divio_type(frontmatter.get(_FM_DIVIO_TYPE))

    owning_raw = frontmatter.get(_FM_OWNING_WORKSTREAM)
    owning_workstream = (
        owning_raw.strip()
        if isinstance(owning_raw, str) and owning_raw.strip()
        else _DEFAULT_OWNING_WORKSTREAM
    )

    return PageInventoryEntry(
        path=rel_path,
        tag=tag,
        divio_type=divio_type,
        owning_workstream=owning_workstream,
        current_target=tag is VersionTag.CURRENT,
        notes=_coerce_notes(frontmatter.get(_FM_NOTES)),
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_inventory(
    docs_root: Path, *, repo_root: Path | None = None
) -> list[PageInventoryEntry]:
    """Walk ``docs_root`` and emit a rollup of one entry per ``.md`` page.

    Entries are sorted alphabetically by repo-relative ``path`` for a
    deterministic, byte-stable diff. ``repo_root`` anchors the emitted path
    (defaults to ``docs_root``'s parent so ``docs/foo.md`` is emitted, not an
    absolute path).
    """
    anchor = (repo_root or docs_root.parent).resolve()
    entries: list[PageInventoryEntry] = []
    for md_path in sorted(docs_root.rglob("*.md")):
        rel_path = _relative_posix(md_path, anchor)
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        entries.append(entry_for_page(rel_path, parse_frontmatter(text)))
    entries.sort(key=lambda entry: entry.path)
    return entries


def _relative_posix(path: Path, anchor: Path) -> str:
    """Render ``path`` as a forward-slash repo-relative string under ``anchor``."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(anchor).as_posix()
    except ValueError:
        return resolved.as_posix()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_LOCKFILE_HEADER: Final[str] = (
    "# Page inventory — GENERATED LOCKFILE (do not hand-edit).\n"
    "# Regenerated from in-file frontmatter by scripts/docs/inventory_lockfile.py\n"
    "# (ADR 2026-06-27-1 decision D1). Sorted alphabetically by `path` for a\n"
    "# deterministic diff. The retired `citation_refs` field is not emitted.\n"
)


def _render_notes(notes: str | None) -> str:
    """Render a ``notes`` value as a YAML scalar (``null`` or JSON-quoted)."""
    if notes is None:
        return "null"
    return json.dumps(notes, ensure_ascii=False)


def render_lockfile(entries: Iterable[PageInventoryEntry]) -> str:
    """Render entries to a deterministic, byte-stable YAML lockfile string.

    Hand-rolled (rather than a YAML dumper) so the byte layout is fully under
    our control and stable across ``ruamel``/``PyYAML`` versions.
    """
    chunks: list[str] = [_LOCKFILE_HEADER]
    for entry in entries:
        chunks.append(
            f"- path: {entry.path}\n"
            f"  tag: {entry.tag.value}\n"
            f"  divio_type: {entry.divio_type.value}\n"
            f"  owning_workstream: {entry.owning_workstream}\n"
            f"  current_target: {str(entry.current_target).lower()}\n"
            f"  notes: {_render_notes(entry.notes)}\n"
        )
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _entry_fingerprint(entry: PageInventoryEntry) -> tuple[str, str, str, bool, str | None]:
    """Order-independent value fingerprint of an entry (excludes ``path``)."""
    return (
        entry.tag.value,
        entry.divio_type.value,
        entry.owning_workstream,
        entry.current_target,
        entry.notes,
    )


def compare_inventories(
    generated: Iterable[PageInventoryEntry],
    committed: Iterable[PageInventoryEntry],
) -> InventoryDrift:
    """Compare a fresh generation against the committed rollup.

    Returns an :class:`InventoryDrift` whose ``has_drift`` is the RED signal.
    A row is ``changed`` when the same ``path`` carries different metadata in
    each side — this is what catches a lockfile-only hand-edit whose frontmatter
    was left untouched.
    """
    gen_by_path = {entry.path: entry for entry in generated}
    com_by_path = {entry.path: entry for entry in committed}

    added = sorted(set(gen_by_path) - set(com_by_path))
    removed = sorted(set(com_by_path) - set(gen_by_path))
    changed = sorted(
        path
        for path in set(gen_by_path) & set(com_by_path)
        if _entry_fingerprint(gen_by_path[path])
        != _entry_fingerprint(com_by_path[path])
    )
    return InventoryDrift(
        added=tuple(added), removed=tuple(removed), changed=tuple(changed)
    )


# ---------------------------------------------------------------------------
# Report payload
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class LockfileReport:
    """JSON-serializable report of a generate-and-compare run."""

    docs_root: str
    inventory: str
    generated_rows: int
    committed_rows: int
    drift: InventoryDrift = field(default_factory=InventoryDrift)
    strict: bool = False
    exit_code: int = 0

    def to_payload(self) -> dict[str, Any]:
        """Render a deterministic JSON payload."""
        return {
            "docs_root": self.docs_root,
            "inventory": self.inventory,
            "generated_rows": self.generated_rows,
            "committed_rows": self.committed_rows,
            "has_drift": self.drift.has_drift,
            "added": list(self.drift.added),
            "removed": list(self.drift.removed),
            "changed": list(self.drift.changed),
            "strict": self.strict,
            "exit_code": self.exit_code,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the generate-and-compare CLI parser."""
    parser = argparse.ArgumentParser(
        prog="inventory_lockfile",
        description=(
            "Regenerate the page-inventory rollup from in-file frontmatter and "
            "compare it against the committed lockfile (ADR 2026-06-27-1 D1). "
            "Report-only by default (exit 0); --strict makes drift fail."
        ),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs root to walk (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(DEFAULT_INVENTORY_PATH),
        help=f"Committed inventory lockfile (default: {DEFAULT_INVENTORY_PATH}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root anchoring emitted paths (default: docs-root parent).",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Optional path to write the regenerated lockfile (never docs/).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the JSON drift report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Wired-but-off in Mission A: when set, drift exits 1. Default is "
            "report-only (exit 0)."
        ),
    )
    return parser


def run_generate_and_compare(
    *,
    docs_root: Path,
    inventory: Path,
    repo_root: Path | None,
    strict: bool,
) -> LockfileReport:
    """Generate from frontmatter, load the committed rollup, and diff them."""
    generated = generate_inventory(docs_root, repo_root=repo_root)
    try:
        committed = load_inventory(inventory)
    except LoadError:
        committed = []
    drift = compare_inventories(generated, committed)
    exit_code = 1 if (strict and drift.has_drift) else 0
    return LockfileReport(
        docs_root=str(docs_root),
        inventory=str(inventory),
        generated_rows=len(generated),
        committed_rows=len(committed),
        drift=drift,
        strict=strict,
        exit_code=exit_code,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    report = run_generate_and_compare(
        docs_root=args.docs_root,
        inventory=args.inventory,
        repo_root=args.repo_root,
        strict=args.strict,
    )

    if args.write is not None:
        generated = generate_inventory(args.docs_root, repo_root=args.repo_root)
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(render_lockfile(generated), encoding="utf-8")

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report.to_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _emit_summary(report)
    return report.exit_code


def _emit_summary(report: LockfileReport) -> None:
    """Print a deterministic one-line + per-path drift summary to stdout."""
    drift = report.drift
    for path in drift.added:
        sys.stdout.write(f"INVENTORY-LOCKFILE-DRIFT added {path}\n")
    for path in drift.removed:
        sys.stdout.write(f"INVENTORY-LOCKFILE-DRIFT removed {path}\n")
    for path in drift.changed:
        sys.stdout.write(f"INVENTORY-LOCKFILE-DRIFT changed {path}\n")
    sys.stdout.write(
        f"inventory_lockfile: exit={report.exit_code} "
        f"generated={report.generated_rows} committed={report.committed_rows} "
        f"drift={drift.has_drift} ({drift.summary()})\n"
    )


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
