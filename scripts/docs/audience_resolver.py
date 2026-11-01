"""``audience:`` frontmatter resolver (IC-01 / FR-002 / FR-003; doc-kitty shape, #6929).

Walks every ``docs/**/*.md`` page and checks its ``audience:`` frontmatter, which
is doc-kitty's list of ``{profile, guidance_text}`` entries (ADR
``2026-10-31-1`` D-7)::

    audience:
    - profile: internal/maintainer
      guidance_text: Written for the Maintainer reader.

A ``profile`` is a persona path under ``docs/context/audience/`` without ``.md``,
resolved by :func:`scripts.docs._dockitty_contract.persona_page` exactly as
doc-kitty's ``resolveProfile`` does. Two kinds of profile:

* **Catalog** — first segment ``internal`` or ``external``. It MUST name a
  persona page; one that does not is a **dangling reference** and reds
  ``--strict``.
* **Free text** — anything else (e.g. ``end-users``). Examined (it counts toward
  the non-vacuity floor) but never dangling; doc-kitty renders it as a soft miss.

An ``audience:`` that is not a list, or an entry that is not a mapping with a
non-empty ``profile`` and ``guidance_text`` (for example the retired path-string
form), is **malformed**: doc-kitty's build schema rejects it, so it reds
``--strict`` too.

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
library plus ``ruamel.yaml`` (already a project dependency). No workflow
runs it today; ``tests/docs/test_dockitty_frontmatter_shape.py`` holds the
shape over the whole tree. With ``--strict`` it exits ``1`` on any dangling or
malformed entry.

Output shape (parallels the ``related_validator`` rulers contract)::

    { "checked_count": int,
      "dangling_references": [ {"from": path, "to": profile} ],
      "malformed_entries": [ {"from": path, "detail": str} ] }
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from scripts.docs._dockitty_contract import persona_page
from scripts.docs._guards import (
    GitDiffError,
    assert_examined_floor,
    resolve_changed_files,
)
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._page_scope import iter_docs_pages

__all__ = [
    "AudienceReport",
    "DEFAULT_DOCS_ROOT",
    "DanglingReference",
    "MalformedAudience",
    "build_parser",
    "main",
    "resolve_audiences",
    "resolve_audiences_diff_scoped",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"
_CATALOG_SEGMENTS: Final[frozenset[str]] = frozenset({"internal", "external"})
_PROFILE: Final[str] = "profile"
_GUIDANCE: Final[str] = "guidance_text"
_GATE_NAME: Final[str] = "audience_resolver"


@dataclass(slots=True, frozen=True)
class DanglingReference:
    """An ``audience:`` catalog profile that names no persona page (``to_path`` is the profile)."""

    from_path: str
    to_path: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the contract's ``{from, to}`` shape."""
        return {"from": self.from_path, "to": self.to_path}


@dataclass(slots=True, frozen=True)
class MalformedAudience:
    """An ``audience:`` value doc-kitty's build schema rejects."""

    from_path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the contract's ``{from, detail}`` shape."""
        return {"from": self.from_path, "detail": self.detail}


@dataclass(slots=True, frozen=True)
class AudienceReport:
    """Result of an ``audience:`` resolution walk."""

    checked_count: int = 0
    dangling_references: list[DanglingReference] = field(default_factory=list)
    malformed_entries: list[MalformedAudience] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        """True when ``--strict`` must exit non-zero."""
        return bool(self.dangling_references or self.malformed_entries)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "dangling_references": [ref.as_dict() for ref in self.dangling_references],
            "malformed_entries": [entry.as_dict() for entry in self.malformed_entries],
        }


def resolve_audiences(
    *,
    docs_root: Path,
    repo_root: Path,
    min_files: int = 1,
) -> AudienceReport:
    """Walk ``docs_root`` and check every ``audience:`` entry.

    Parameters
    ----------
    docs_root:
        Directory whose ``*.md`` files are scanned; personas resolve under its
        ``context/audience/`` folder.
    repo_root:
        Base for the repo-relative page paths in the report.
    min_files:
        Non-vacuity floor (FR-003). The walk must examine at least this many
        ``audience:`` entries; an empty/missing tree or a parse breakage raises
        :class:`RuntimeError` rather than reporting "0 dangling" over 0 checked.

    Returns
    -------
    AudienceReport
        ``checked_count`` (entries examined, catalog and free-text alike), the
        dangling catalog profiles and the malformed values, in deterministic order.

    Raises
    ------
    RuntimeError
        Fewer than ``min_files`` ``audience:`` entries were examined.
    """
    pages = iter_docs_pages(docs_root) if docs_root.is_dir() else []
    report = _check_pages(pages, docs_root, repo_root)
    assert_examined_floor(
        report.checked_count,
        min_files,
        gate=_GATE_NAME,
        noun=f"audience: value(s) examined under {docs_root}",
        fr_id="FR-003",
    )
    return report


def resolve_audiences_diff_scoped(
    *,
    docs_root: Path,
    repo_root: Path,
    changed_files: list[str],
) -> AudienceReport:
    """Check ``audience:`` entries only in changed ``docs_root`` Markdown.

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
    docs_root_rel = _repo_relative(docs_root, repo_root)
    pages = [
        repo_root / rel
        for rel in sorted(changed_files)
        if rel.startswith(f"{docs_root_rel}/") and rel.endswith(".md") and (repo_root / rel).is_file()
    ]
    return _check_pages(pages, docs_root, repo_root)


def _check_pages(pages: list[Path], docs_root: Path, repo_root: Path) -> AudienceReport:
    checked_count = 0
    dangling: list[DanglingReference] = []
    malformed: list[MalformedAudience] = []
    for md_path in pages:
        from_rel = _repo_relative(md_path, repo_root)
        checked, file_dangling, file_malformed = _audiences_in_file(md_path, from_rel, docs_root)
        checked_count += checked
        dangling.extend(file_dangling)
        malformed.extend(file_malformed)
    dangling.sort(key=lambda ref: (ref.from_path, ref.to_path))
    malformed.sort(key=lambda entry: (entry.from_path, entry.detail))
    return AudienceReport(checked_count=checked_count, dangling_references=dangling, malformed_entries=malformed)


def _audiences_in_file(
    md_path: Path, from_rel: str, docs_root: Path
) -> tuple[int, list[DanglingReference], list[MalformedAudience]]:
    """Check every ``audience:`` entry of one page: ``(examined, dangling, malformed)``."""
    try:
        raw = parse_frontmatter(md_path.read_text(encoding="utf-8")).get("audience")
    except OSError:
        return 0, [], []
    if raw is None:
        return 0, [], []
    if not isinstance(raw, list):
        return 1, [], [MalformedAudience(from_path=from_rel, detail="not a list")]
    dangling: list[DanglingReference] = []
    malformed: list[MalformedAudience] = []
    for entry in raw:
        problem = _entry_problem(entry)
        if problem is not None:
            malformed.append(MalformedAudience(from_path=from_rel, detail=problem))
            continue
        profile = str(entry[_PROFILE]).strip()
        if _is_catalog_profile(profile) and persona_page(docs_root, profile) is None:
            dangling.append(DanglingReference(from_path=from_rel, to_path=profile))
    return len(raw), dangling, malformed


def _entry_problem(entry: Any) -> str | None:
    """Why *entry* is not a valid ``{profile, guidance_text}`` mapping, or ``None``."""
    if not isinstance(entry, dict):
        return "not a {profile, guidance_text} mapping"
    for key in (_PROFILE, _GUIDANCE):
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            return f"missing {key}"
    return None


def _is_catalog_profile(profile: str) -> bool:
    """A profile whose first segment is a persona catalog (``internal``/``external``)."""
    return profile.split("/", 1)[0].lower() in _CATALOG_SEGMENTS


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
            "Validate docs/ frontmatter 'audience:' profile lists against the "
            "persona catalog. Report-only (exit 0) unless "
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
        help="Exit non-zero when any dangling or malformed 'audience:' entry is found.",
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
        )
    else:
        report = resolve_audiences(
            docs_root=args.docs_root,
            repo_root=args.repo_root,
        )
    _emit(report, as_json=args.json)
    if args.strict and report.failed:
        return 1
    return 0


def _emit(report: AudienceReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(
        f"{_GATE_NAME}: checked {report.checked_count} audience value(s); "
        f"{len(report.dangling_references)} dangling, {len(report.malformed_entries)} malformed.\n"
    )
    for ref in report.dangling_references:
        sys.stdout.write(f"  DANGLING {ref.from_path} -> {ref.to_path}\n")
    for entry in report.malformed_entries:
        sys.stdout.write(f"  MALFORMED {entry.from_path}: {entry.detail}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
