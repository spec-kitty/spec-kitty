"""``related:`` frontmatter graph validator (IC-03 / FR-005; doc-kitty slugs, #6929).

Walks every ``docs/**/*.md`` page and resolves each ``related:`` entry the way
doc-kitty does (ADR ``2026-10-31-1`` D-7/D-8): an entry is a page **slug** (its
path under ``docs/`` without ``.md``, a trailing ``README``/``index`` removed;
the docs root page is ``""``) or a ``{ref, note}`` mapping. Two findings:

* a **dangling edge** — the slug names no page (a repository path such as
  ``docs/x.md`` is not a slug, so it dangles too);
* an **unpublished edge** — the slug names a page doc-kitty does not build when it
  builds the source: a published page naming a draft or excluded page, or a draft
  page naming an excluded page. doc-kitty fails the build on either. A page in an
  excluded folder is never built, so it may name any page.

Slug, publication and exclusion rules come from
:mod:`scripts.docs._dockitty_contract`. Paths outside ``docs/`` live in
``external_references``, which this validator does not read. Report-only (exit
``0``) unless ``--strict`` is passed.

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

    { "checked_count": int,
      "dangling_edges": [ {"from": path, "to": slug} ],
      "unpublished_edges": [ {"from": path, "to": slug} ] }

where ``checked_count`` is the number of ``related:`` edges examined — so a
"0 dangling" result can never silently mean "0 checked".
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from scripts.docs._dockitty_contract import is_excluded, is_published, page_for_slug
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
    """A ``related:`` edge (``to_path`` is the slug as written) that names no page, or an unbuilt one."""

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
    unpublished_edges: list[DanglingEdge] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        """True when ``--strict`` must exit non-zero."""
        return bool(self.dangling_edges or self.unpublished_edges)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "dangling_edges": [edge.as_dict() for edge in self.dangling_edges],
            "unpublished_edges": [edge.as_dict() for edge in self.unpublished_edges],
        }


def _related_edges_in_file(md_path: Path, docs_root: Path, repo_root: Path) -> tuple[int, list[DanglingEdge], list[DanglingEdge]]:
    """Whole-file ``related:`` edge check for one docs page.

    Shared by the whole-tree walk (:func:`validate_related`) and the
    diff-scope walk (:func:`validate_related_diff_scoped`) so both check the
    SAME whole file (B-WP02: scope by *file*, never by hunk/line).

    Returns ``(edges_examined, dangling_edges, unpublished_edges)``.
    """
    frontmatter = _read_frontmatter(md_path)
    refs = _related_refs(frontmatter)
    if not refs:
        return 0, [], []
    from_rel = _repo_relative(md_path, repo_root)
    source = _docs_relative(md_path, docs_root)
    dangling: list[DanglingEdge] = []
    unpublished: list[DanglingEdge] = []
    for ref in refs:
        target = page_for_slug(docs_root, ref) if not _looks_like_path(ref) else None
        if target is None:
            dangling.append(DanglingEdge(from_path=from_rel, to_path=ref))
        elif not _target_allowed(source, frontmatter, target, docs_root):
            unpublished.append(DanglingEdge(from_path=from_rel, to_path=ref))
    return len(refs), dangling, unpublished


def _looks_like_path(ref: str) -> bool:
    """A repository path (``docs/x.md``) is not a slug, even when the file exists."""
    return ref.endswith(".md") or ref.startswith("docs/")


def _target_allowed(source: str, frontmatter: dict[str, Any], target: Path, docs_root: Path) -> bool:
    """Whether doc-kitty resolves *target* whenever it builds *source* (see the module docstring)."""
    if is_excluded(source):
        return True
    target_rel = _docs_relative(target, docs_root)
    if not is_published(source, frontmatter):
        return not is_excluded(target_rel)
    return is_published(target_rel, _read_frontmatter(target))


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
    pages = iter_docs_pages(docs_root) if docs_root.is_dir() else []
    report = _check_pages(pages, docs_root, repo_root)

    assert_examined_floor(
        report.checked_count,
        min_files,
        gate="related_validator",
        noun=f"related edge(s) examined under {docs_root}",
        fr_id="FR-008",
    )
    return report


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
    pages = [
        repo_root / rel
        for rel in sorted(changed_files)
        # a deleted changed path no longer exists: nothing to check
        if rel.startswith(f"{docs_root_rel}/") and rel.endswith(".md") and (repo_root / rel).is_file()
    ]
    return _check_pages(pages, docs_root, repo_root)


def _check_pages(pages: list[Path], docs_root: Path, repo_root: Path) -> RelatedReport:
    checked_count = 0
    dangling: list[DanglingEdge] = []
    unpublished: list[DanglingEdge] = []
    for md_path in pages:
        file_checked, file_dangling, file_unpublished = _related_edges_in_file(md_path, docs_root, repo_root)
        checked_count += file_checked
        dangling.extend(file_dangling)
        unpublished.extend(file_unpublished)
    dangling.sort(key=lambda edge: (edge.from_path, edge.to_path))
    unpublished.sort(key=lambda edge: (edge.from_path, edge.to_path))
    return RelatedReport(checked_count=checked_count, dangling_edges=dangling, unpublished_edges=unpublished)


def _read_frontmatter(md_path: Path) -> dict[str, Any]:
    try:
        return parse_frontmatter(md_path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _related_refs(frontmatter: dict[str, Any]) -> list[str]:
    """The ``related:`` refs as written: bare slugs and the ``ref`` of ``{ref, note}`` entries."""
    raw = frontmatter.get("related")
    if not isinstance(raw, list):
        return []
    refs: list[str] = []
    for item in raw:
        ref = item.get("ref") if isinstance(item, dict) else item
        if isinstance(ref, str):
            refs.append(ref.strip())
    return refs


def _docs_relative(path: Path, docs_root: Path) -> str:
    """*path* (always a page under *docs_root*) as a POSIX path relative to it."""
    return path.resolve().relative_to(docs_root.resolve()).as_posix()


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
        help="Base for the repo-relative page paths in the report (default: cwd).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a dangling or unpublished edge is found.",
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
    if args.strict and report.failed:
        return 1
    return 0


def _emit(report: RelatedReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(
        f"related_validator: checked {report.checked_count} edge(s); {len(report.dangling_edges)} dangling, {len(report.unpublished_edges)} unpublished.\n"
    )
    for edge in report.dangling_edges:
        sys.stdout.write(f"  DANGLING {edge.from_path} -> {edge.to_path}\n")
    for edge in report.unpublished_edges:
        sys.stdout.write(f"  UNPUBLISHED {edge.from_path} -> {edge.to_path}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
