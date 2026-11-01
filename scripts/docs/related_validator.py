"""``related:`` frontmatter graph validator (IC-03 / FR-005).

Walks every ``docs/**/*.md`` page, reads its YAML frontmatter ``related:``
list, and resolves each entry — a repo-relative path — against the
repository root. A ``related:`` entry that does not resolve to an existing
file is a **dangling edge**.

Per ADR ``2026-06-27-1-common-docs-reconciliation`` the canonical ``related:``
form is a list of resolvable repo-relative ``.md`` paths. This validator is
**report-only** (exit ``0``; C-002): it prints what it finds and records a
baseline, but it does not fail CI. Mission B turns the wired ``--strict`` flag
on to flip the exit semantics to blocking.

The validator never mutates the docs tree (C-006) and depends only on the
standard library plus ``ruamel.yaml`` (already a project dependency).

``--changed-from BASE_REF`` (#3147, WP02) diff-scopes the walk to changed
``docs/**/*.md`` files instead of the whole tree. **B-WP02 (see
``kitty-specs/ci-scoping-gate-reliability-01KZP80D/investigate-squad-findings.md``):
fail-closed keys on git base RESOLVABILITY, never on an empty changed set** —
a resolved diff touching zero docs files (common: ``docs-freshness.yml`` also
triggers on ``src/specify_cli/**``, ``pyproject.toml``, etc.) is a clean PASS;
only an unresolvable/unfetched base ref errors.

Output shape (per the rulers contract)::

    { "checked_count": int, "dangling_edges": [ {"from": path, "to": path} ] }

where ``checked_count`` is the number of ``related:`` edges examined — so a
"0 dangling" result can never silently mean "0 checked".
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from scripts.docs._guards import GitDiffError, assert_examined_floor, resolve_changed_files
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._page_scope import iter_docs_pages

__all__ = [
    "DEFAULT_DOCS_ROOT",
    "DanglingEdge",
    "RelatedReport",
    "build_parser",
    "main",
    "validate_related",
    "validate_related_diff_scoped",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"


@dataclass(slots=True, frozen=True)
class DanglingEdge:
    """A ``related:`` edge whose target does not resolve to an existing file."""

    from_path: str
    to_path: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the contract's ``{from, to}`` shape."""
        return {"from": self.from_path, "to": self.to_path}


@dataclass(slots=True, frozen=True)
class RelatedReport:
    """Result of a ``related:`` graph walk."""

    checked_count: int = 0
    dangling_edges: list[DanglingEdge] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "dangling_edges": [edge.as_dict() for edge in self.dangling_edges],
        }


def _related_edges_in_file(md_path: Path, repo_root: Path) -> tuple[int, list[DanglingEdge]]:
    """Whole-file ``related:`` edge check for one docs page.

    Shared by the whole-tree walk (:func:`validate_related`) and the
    diff-scope walk (:func:`validate_related_diff_scoped`) so both check the
    SAME whole file (B-WP02: scope by *file*, never by hunk/line).

    Returns ``(edges_examined, dangling_edges)``.
    """
    related = _read_related(md_path)
    if not related:
        return 0, []
    from_rel = _repo_relative(md_path, repo_root)
    dangling = [DanglingEdge(from_path=from_rel, to_path=entry) for entry in related if not _resolves(entry, repo_root)]
    return len(related), dangling


def validate_related(*, docs_root: Path, repo_root: Path, min_files: int = 1) -> RelatedReport:
    """Walk ``docs_root`` and resolve every ``related:`` edge against ``repo_root``.

    Parameters
    ----------
    docs_root:
        Directory whose ``*.md`` files are scanned for frontmatter.
    repo_root:
        Base against which each repo-relative ``related:`` entry is resolved.
    min_files:
        Non-vacuity floor (#3264 / FR-008). The walk must examine at least this
        many ``related:`` edges; a scope-narrowing regression — a missing docs
        tree, an empty tree, or a frontmatter-parse breakage that stops matching
        edges — raises :class:`RuntimeError` rather than reporting "0 dangling"
        over 0 checked. Mirrors the sibling floor in
        :func:`scripts.docs.relative_link_fixer.check_dead_body_links`. This
        floor is intentionally NOT applied to the diff-scope walk
        (:func:`validate_related_diff_scoped`) — see B-WP02 there.

    Returns
    -------
    RelatedReport
        ``checked_count`` (total edges examined) and the dangling edges, in
        deterministic ``(from, to)`` order.

    Raises
    ------
    RuntimeError
        Fewer than ``min_files`` ``related:`` edges were examined (non-vacuity guard).
    """
    checked_count = 0
    dangling: list[DanglingEdge] = []

    if docs_root.exists() and docs_root.is_dir():
        for md_path in iter_docs_pages(docs_root):
            file_checked, file_dangling = _related_edges_in_file(md_path, repo_root)
            checked_count += file_checked
            dangling.extend(file_dangling)

    assert_examined_floor(
        checked_count,
        min_files,
        gate="related_validator",
        noun=f"related edge(s) examined under {docs_root}",
        fr_id="FR-008",
    )

    dangling.sort(key=lambda edge: (edge.from_path, edge.to_path))
    return RelatedReport(checked_count=checked_count, dangling_edges=dangling)


def validate_related_diff_scoped(*, docs_root: Path, repo_root: Path, changed_files: list[str]) -> RelatedReport:
    """Diff-scoped counterpart to :func:`validate_related` (#3147, B-WP02).

    Restricts the ``related:`` edge walk to *changed_files* intersected with
    ``docs_root``'s ``*.md`` files, instead of the whole-tree ``rglob`` walk.
    Each in-scope changed file is checked **whole-file** (via the shared
    :func:`_related_edges_in_file`) — never by hunk/line, mirroring
    :func:`scripts.docs.relative_link_fixer.check_dead_body_links_diff_scoped`.

    *changed_files* are repo-relative POSIX paths, e.g. from
    :func:`scripts.docs._guards.resolve_changed_files`. A changed path that no
    longer exists on disk (deleted) is skipped.

    **No non-vacuity floor is applied here (B-WP02, deliberate).** A
    successfully-resolved diff that intersects zero ``docs_root`` files —
    the common case for a non-docs-md PR — returns an empty report (clean
    PASS), not a :exc:`RuntimeError`. That floor stays reserved for
    :func:`validate_related`'s whole-tree/``push`` mode.
    """
    docs_root_rel = _repo_relative(docs_root, repo_root)
    checked_count = 0
    dangling: list[DanglingEdge] = []
    for rel in sorted(changed_files):
        if not (rel.startswith(f"{docs_root_rel}/") and rel.endswith(".md")):
            continue
        md_path = repo_root / rel
        if not md_path.is_file():
            continue  # deleted changed path — nothing to check
        file_checked, file_dangling = _related_edges_in_file(md_path, repo_root)
        checked_count += file_checked
        dangling.extend(file_dangling)

    dangling.sort(key=lambda edge: (edge.from_path, edge.to_path))
    return RelatedReport(checked_count=checked_count, dangling_edges=dangling)


def _read_related(md_path: Path) -> list[str]:
    """Return the ``related:`` list from a page's frontmatter (``[]`` if none)."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return []

    frontmatter = parse_frontmatter(text)
    raw = frontmatter.get("related")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if isinstance(item, str) and item.strip()]


def _resolves(entry: str, repo_root: Path) -> bool:
    """An entry resolves when its repo-relative path exists as a file."""
    candidate = (repo_root / entry).resolve()
    return candidate.is_file()


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Render ``path`` as a POSIX repo-relative string (best-effort)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    """Build the validator CLI parser."""
    parser = argparse.ArgumentParser(
        prog="related_validator",
        description=("Validate docs/ frontmatter 'related:' edges. Report-only (exit 0) unless --strict is passed."),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs tree to scan (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Base for resolving repo-relative 'related:' entries (default: cwd).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=("Exit non-zero when dangling edges are found. Wired but OFF by default in Mission A (report-only, C-002); Mission B turns it on."),
    )
    parser.add_argument(
        "--changed-from",
        metavar="BASE_REF",
        default=None,
        help=(
            "Diff-scope the walk to docs-root *.md files changed since "
            "BASE_REF (#3147). Fails closed (non-zero exit) only when "
            "BASE_REF cannot be resolved via git; a resolved diff with zero "
            "in-scope docs files is a clean pass — see B-WP02 in the mission "
            "findings."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.changed_from is not None:
        # Diff-scope mode (#3147, B-WP02): fail-closed ONLY on an unresolvable
        # git base — never on a resolved-but-empty changed set.
        try:
            changed = resolve_changed_files(args.repo_root, args.changed_from)
        except GitDiffError as exc:
            sys.stderr.write(f"related_validator: ERROR: {exc}\n")
            return 2
        report = validate_related_diff_scoped(docs_root=args.docs_root, repo_root=args.repo_root, changed_files=changed)
    else:
        report = validate_related(docs_root=args.docs_root, repo_root=args.repo_root)
    _emit(report, as_json=args.json)
    if args.strict and report.dangling_edges:
        return 1
    return 0


def _emit(report: RelatedReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(f"related_validator: checked {report.checked_count} edge(s); {len(report.dangling_edges)} dangling.\n")
    for edge in report.dangling_edges:
        sys.stdout.write(f"  DANGLING {edge.from_path} -> {edge.to_path}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
