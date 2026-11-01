"""``audience:`` frontmatter resolver (IC-01 / FR-002 / FR-003).

Walks every ``docs/**/*.md`` page, reads its YAML frontmatter ``audience:``
value — a scalar **or** a list — and resolves each *reference* entry against
the repository root. Per the audience-resolution contract the canonical
``audience:`` form is one (or more) resolvable repo-relative ``.md`` path(s)
targeting a persona under ``docs/context/audience/``.

Two value shapes coexist during the Common Docs convergence:

* **Reference** — a value ending in ``.md``. It MUST resolve to an existing
  file under ``docs/context/audience/``; a value that does not is a **dangling
  reference** and reds ``--strict``.
* **Free-text** — any other value (e.g. ``end-users``, ``packagers``). These
  are pages whose ``audience:`` has not yet been migrated to a persona path by
  the mover WPs. They are examined (they count toward the non-vacuity floor)
  but are *not* treated as dangling — migrating them is out of scope here.

Non-vacuity (#3264-family / FR-003): the walk reuses
:func:`scripts.docs._guards.assert_examined_floor` so a scope-narrowing
regression — a missing docs tree, an empty tree, or a frontmatter-parse
breakage that stops matching ``audience:`` values — goes **RED** rather than
silently reporting "0 dangling" over 0 examined. ``checked_count`` is emitted
so a "0 dangling" result can never mean "0 checked".

``--changed-from BASE_REF`` restricts the walk to changed ``docs/**/*.md``
files on PRs. That mode intentionally skips the non-vacuity floor for a
resolved empty docs diff and fails closed only when the Git base cannot be
resolved. Without the flag, the whole-tree behavior and floor are unchanged.

The resolver never mutates the docs tree and depends only on the standard
library plus ``ruamel.yaml`` (already a project dependency). It is wired
``--strict`` on PR in ``docs-freshness.yml``; exit ``1`` on any dangling
reference.

Output shape (parallels the ``related_validator`` rulers contract)::

    { "checked_count": int, "dangling_references": [ {"from": path, "to": path} ] }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from scripts.docs._guards import (
    GitDiffError,
    assert_examined_floor,
    resolve_changed_files,
)
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._page_scope import iter_docs_pages

__all__ = [
    "AudienceReport",
    "DEFAULT_CATALOG_ROOT",
    "DEFAULT_DOCS_ROOT",
    "DanglingReference",
    "build_parser",
    "main",
    "resolve_audiences",
    "resolve_audiences_diff_scoped",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"
DEFAULT_CATALOG_ROOT: Final[str] = "docs/context/audience"
_REFERENCE_SUFFIX: Final[str] = ".md"
_GATE_NAME: Final[str] = "audience_resolver"


@dataclass(slots=True, frozen=True)
class DanglingReference:
    """An ``audience:`` reference whose target is not a catalog persona file."""

    from_path: str
    to_path: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the contract's ``{from, to}`` shape."""
        return {"from": self.from_path, "to": self.to_path}


@dataclass(slots=True, frozen=True)
class AudienceReport:
    """Result of an ``audience:`` resolution walk."""

    checked_count: int = 0
    dangling_references: list[DanglingReference] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "dangling_references": [ref.as_dict() for ref in self.dangling_references],
        }


def resolve_audiences(
    *,
    docs_root: Path,
    repo_root: Path,
    catalog_root: Path | None = None,
    min_files: int = 1,
) -> AudienceReport:
    """Walk ``docs_root`` and resolve every ``audience:`` reference.

    Parameters
    ----------
    docs_root:
        Directory whose ``*.md`` files are scanned for frontmatter.
    repo_root:
        Base against which each repo-relative ``audience:`` reference resolves.
    catalog_root:
        Directory a resolved reference must live under to be valid (default:
        ``repo_root / docs/context/audience``). References that resolve to a
        file outside this tree are dangling (mis-targeted).
    min_files:
        Non-vacuity floor (FR-003). The walk must examine at least this many
        ``audience:`` values; an empty/missing tree or a parse breakage raises
        :class:`RuntimeError` rather than reporting "0 dangling" over 0 checked.

    Returns
    -------
    AudienceReport
        ``checked_count`` (total ``audience:`` values examined — references and
        not-yet-migrated free-text alike) and the dangling references, in
        deterministic ``(from, to)`` order.

    Raises
    ------
    RuntimeError
        Fewer than ``min_files`` ``audience:`` values were examined.
    """
    catalog = (catalog_root or repo_root / DEFAULT_CATALOG_ROOT).resolve()
    checked_count = 0
    dangling: list[DanglingReference] = []

    if docs_root.exists() and docs_root.is_dir():
        for md_path in iter_docs_pages(docs_root):
            file_checked, file_dangling = _audiences_in_file(
                md_path, repo_root, catalog
            )
            checked_count += file_checked
            dangling.extend(file_dangling)

    assert_examined_floor(
        checked_count,
        min_files,
        gate=_GATE_NAME,
        noun=f"audience: value(s) examined under {docs_root}",
        fr_id="FR-003",
    )

    dangling.sort(key=lambda ref: (ref.from_path, ref.to_path))
    return AudienceReport(checked_count=checked_count, dangling_references=dangling)


def resolve_audiences_diff_scoped(
    *,
    docs_root: Path,
    repo_root: Path,
    changed_files: list[str],
    catalog_root: Path | None = None,
) -> AudienceReport:
    """Resolve ``audience:`` values only in changed ``docs_root`` Markdown.

    Each in-scope page is checked whole-file. Deleted paths and changed files
    outside ``docs_root/**/*.md`` are skipped. Unlike the whole-tree walk, this
    mode deliberately has no non-vacuity floor: a successfully resolved diff
    with no in-scope docs is a clean pass.

    Accepted limitation (same as #3312): a PR that deletes or renames a persona
    under ``docs/context/audience/`` without touching any referring page passes
    this PR-scoped gate, because no referrer is in the diff. The ``push:main``
    whole-tree run (:func:`resolve_audiences`) is the backstop that catches the
    newly dangling references.
    """
    catalog = (catalog_root or repo_root / DEFAULT_CATALOG_ROOT).resolve()
    docs_root_rel = _repo_relative(docs_root, repo_root)
    checked_count = 0
    dangling: list[DanglingReference] = []

    for rel in sorted(changed_files):
        if not (rel.startswith(f"{docs_root_rel}/") and rel.endswith(".md")):
            continue
        md_path = repo_root / rel
        if not md_path.is_file():
            continue
        file_checked, file_dangling = _audiences_in_file(md_path, repo_root, catalog)
        checked_count += file_checked
        dangling.extend(file_dangling)

    dangling.sort(key=lambda ref: (ref.from_path, ref.to_path))
    return AudienceReport(checked_count=checked_count, dangling_references=dangling)


def _audiences_in_file(
    md_path: Path, repo_root: Path, catalog: Path
) -> tuple[int, list[DanglingReference]]:
    """Check all ``audience:`` values in one Markdown page."""
    values = _read_audience(md_path)
    if not values:
        return 0, []
    from_rel = _repo_relative(md_path, repo_root)
    dangling = [
        DanglingReference(from_path=from_rel, to_path=value)
        for value in values
        if _is_reference(value) and not _resolves(value, repo_root, catalog)
    ]
    return len(values), dangling


def _read_audience(md_path: Path) -> list[str]:
    """Return a page's ``audience:`` values (scalar or list) as a string list."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return []

    frontmatter = parse_frontmatter(text)
    raw = frontmatter.get("audience")
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str) and item.strip()]
    return []


def _is_reference(value: str) -> bool:
    """A value is a persona *reference* when it points at a ``.md`` path."""
    return value.strip().endswith(_REFERENCE_SUFFIX)


def _resolves(value: str, repo_root: Path, catalog: Path) -> bool:
    """A reference resolves when it is a file under the persona catalog."""
    candidate = (repo_root / value.strip()).resolve()
    return candidate.is_file() and candidate.is_relative_to(catalog)


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Render ``path`` as a POSIX repo-relative string (best-effort)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    """Build the resolver CLI parser."""
    parser = argparse.ArgumentParser(
        prog=_GATE_NAME,
        description=(
            "Validate docs/ frontmatter 'audience:' references (scalar or "
            "list) against the persona catalog. Report-only (exit 0) unless "
            "--strict is passed."
        ),
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
        help="Base for resolving repo-relative 'audience:' references (default: cwd).",
    )
    parser.add_argument(
        "--catalog-root",
        type=Path,
        default=None,
        help=(
            "Directory a resolved reference must live under "
            f"(default: <repo-root>/{DEFAULT_CATALOG_ROOT})."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any dangling 'audience:' reference is found.",
    )
    parser.add_argument(
        "--changed-from",
        metavar="BASE_REF",
        default=None,
        help=(
            "Diff-scope the walk to docs-root *.md files changed since "
            "BASE_REF. Fails closed only when BASE_REF cannot be resolved; "
            "a resolved diff with zero in-scope docs files is a clean pass."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.changed_from is not None:
        try:
            changed = resolve_changed_files(args.repo_root, args.changed_from)
        except GitDiffError as exc:
            sys.stderr.write(f"{_GATE_NAME}: ERROR: {exc}\n")
            return 2
        report = resolve_audiences_diff_scoped(
            docs_root=args.docs_root,
            repo_root=args.repo_root,
            changed_files=changed,
            catalog_root=args.catalog_root,
        )
    else:
        report = resolve_audiences(
            docs_root=args.docs_root,
            repo_root=args.repo_root,
            catalog_root=args.catalog_root,
        )
    _emit(report, as_json=args.json)
    if args.strict and report.dangling_references:
        return 1
    return 0


def _emit(report: AudienceReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(
        f"{_GATE_NAME}: checked {report.checked_count} audience value(s); "
        f"{len(report.dangling_references)} dangling.\n"
    )
    for ref in report.dangling_references:
        sys.stdout.write(f"  DANGLING {ref.from_path} -> {ref.to_path}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
