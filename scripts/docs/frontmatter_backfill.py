"""Frontmatter backfill tooling (FR-010 / NFR-004).

Mission B inverts the page-metadata SSOT: in-file frontmatter becomes the
authority and ``docs/development/page-inventory.yaml`` is a *generated*
rollup derived FROM it (directive 042, ADR ``2026-06-27-1`` decision D1). The
live inventory snapshot carries **0** ``doc_status``, **0** ``description`` and
**0** ``related`` values, so FR-010 is **derivation + authoring**, not a
mechanical drift-close — there is nothing to "sync", it must be authored.

This module is the **tooling** half of that work (IC-05e-1):

* a deterministic ``tag -> doc_status`` mapping table (:data:`TAG_DOC_STATUS`
  plus :func:`derive_doc_status` for the ``internal`` disambiguation), so the
  page lifecycle is *derived* from the live version tier, never guessed per
  page;
* an idempotent backfill planner/writer (:func:`plan_backfill`,
  :func:`render_page`, :func:`apply_backfill`) that derives ``doc_status`` and
  carries the inventory fields (``version_tag`` / ``type`` / ``owning_workstream``)
  plus an ``updated`` freshness date onto each page; and
* a ``related:`` edge derivation (:func:`derive_related`) that emits **only
  resolvable** cross-page edges (NFR-004 = 0 dangling) and flags the remainder
  for WP12 authoring.

The tool **never invents a ``description``** — per-page ``description`` (and the
non-derivable ``related`` remainder) are authored in WP12; the 50-180 length
gate lives in :mod:`scripts.docs.description_length_check`. Running this module
over the ~580-page tree at scale is WP12's job; WP11 only builds and tests it.

Depends only on the standard library plus ``ruamel.yaml`` (already a project
dependency). No new dependency is introduced.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

from scripts.docs._inventory import (
    DivioType,
    PageInventoryEntry,
    VersionTag,
    load_inventory,
    parse_frontmatter,
)

__all__ = [
    "TAG_DOC_STATUS",
    "DocStatus",
    "PageBackfill",
    "RelatedDerivation",
    "apply_backfill",
    "build_backfill",
    "build_parser",
    "derive_doc_status",
    "derive_related",
    "main",
    "plan_backfill",
    "render_page",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"
DEFAULT_INVENTORY: Final[str] = "docs/development/page-inventory.yaml"

# Frontmatter key names shared with ``scripts.docs.inventory_lockfile`` — the
# divio axis lives under the existing ``type:`` key, not ``divio_type:``.
_FM_TITLE: Final[str] = "title"
_FM_DESCRIPTION: Final[str] = "description"
_FM_DOC_STATUS: Final[str] = "doc_status"
_FM_UPDATED: Final[str] = "updated"
_FM_VERSION_TAG: Final[str] = "version_tag"
_FM_DIVIO_TYPE: Final[str] = "type"
_FM_OWNING_WORKSTREAM: Final[str] = "owning_workstream"
_FM_RELATED: Final[str] = "related"
_FM_NOTES: Final[str] = "notes"

# Deterministic frontmatter key order for idempotent serialization. Any key not
# listed here is appended afterwards in sorted order, so re-running the writer
# on its own output reproduces it byte-for-byte.
_KEY_ORDER: Final[tuple[str, ...]] = (
    _FM_TITLE,
    _FM_DESCRIPTION,
    _FM_DOC_STATUS,
    _FM_UPDATED,
    _FM_VERSION_TAG,
    _FM_DIVIO_TYPE,
    _FM_OWNING_WORKSTREAM,
    _FM_NOTES,
    _FM_RELATED,
)

_FRONTMATTER_FENCE: Final[str] = "---"

# Inline markdown link: ``[text](target)``. Reference-style and bare autolinks
# are intentionally out of scope — only explicit inline links seed ``related``.
_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


class DocStatus(StrEnum):
    """Documentation *lifecycle* vocabulary (directive 042, key ``doc_status``).

    Distinct from FR-003's bare ADR ``status`` (MADR decision status). Bare
    ``status`` is prohibited for pages because it collides with the WP-lane
    status model.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    # Reserved never-retire value for domain throughlines, mirroring directive
    # 042. Authored by hand only — no version tag derives to it (absent from
    # TAG_DOC_STATUS / derive_doc_status).
    DURABLE = "durable"


# T065 — the explicit, deterministic ``tag -> doc_status`` mapping.
#
# Live tag counts in the 580-row snapshot: internal 419 / current 133 /
# archival 14 / migration 14.
#
#   current   -> active     a current page is a live, published doc.
#   migration -> active     migration guides are live aids for the cutover.
#   archival  -> deprecated archived/historical content is retired-in-place.
#   supported -> active     a still-supported older version is a live doc
#                           (0 such rows today; mapped for completeness).
#   internal  -> active|draft  disambiguated by signal — see derive_doc_status.
#
# ``internal`` is intentionally absent from this static table: it is the one
# tag whose lifecycle is not a pure function of the tag, so it is resolved by
# :func:`derive_doc_status` from the page's ``current_target`` signal.
TAG_DOC_STATUS: Final[dict[VersionTag, DocStatus]] = {
    VersionTag.CURRENT: DocStatus.ACTIVE,
    VersionTag.MIGRATION: DocStatus.ACTIVE,
    VersionTag.ARCHIVAL: DocStatus.DEPRECATED,
    VersionTag.SUPPORTED: DocStatus.ACTIVE,
}


def derive_doc_status(tag: VersionTag, *, current_target: bool) -> DocStatus:
    """Derive a page's ``doc_status`` from its live ``tag`` (T065).

    The four published tiers map straight through :data:`TAG_DOC_STATUS`. The
    ``internal`` tier is disambiguated by the **``current_target`` signal**: an
    internal page still designated a current target is a live engineering doc
    (``active``); an internal page that is *not* a current target is provisional
    and pending curation under the delete-stale policy (``draft``).

    This is a deterministic one-time derivation, not a per-page guess.
    """
    if tag is VersionTag.INTERNAL:
        return DocStatus.ACTIVE if current_target else DocStatus.DRAFT
    return TAG_DOC_STATUS[tag]


@dataclass(slots=True, frozen=True)
class RelatedDerivation:
    """Outcome of deriving ``related:`` edges from a page's in-body links.

    ``resolved`` edges are repo-relative ``.md`` paths that exist under the docs
    root — only these are written to frontmatter (NFR-004 = 0 dangling).
    ``unresolved`` are in-body links that look like docs pages but do not
    resolve; they are flagged for WP12 authoring rather than emitted.
    """

    resolved: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PageBackfill:
    """The derived frontmatter plan for a single page.

    ``description`` is *preserved* (never invented here — WP12 authors it), so
    a value of ``None`` means "needs authoring". ``updated`` is the derived or
    preserved freshness date.
    """

    path: str
    doc_status: DocStatus
    version_tag: VersionTag
    divio_type: DivioType
    owning_workstream: str
    updated: str | None
    related: list[str]
    related_unresolved: list[str]
    description: str | None
    notes: str | None

    def as_dict(self) -> dict[str, object]:
        """Serialize to a deterministic JSON-friendly mapping."""
        return {
            "path": self.path,
            "doc_status": self.doc_status.value,
            "version_tag": self.version_tag.value,
            "divio_type": self.divio_type.value,
            "owning_workstream": self.owning_workstream,
            "updated": self.updated,
            "related": list(self.related),
            "related_unresolved": list(self.related_unresolved),
            "description": self.description,
            "description_needs_authoring": self.description is None,
            "notes": self.notes,
        }


def _strip_anchor(target: str) -> str:
    """Drop a ``#anchor`` / ``?query`` suffix from a link target."""
    for sep in ("#", "?"):
        index = target.find(sep)
        if index != -1:
            target = target[:index]
    return target


def _is_docs_link(target: str) -> bool:
    """A candidate in-body link to another docs page (relative ``.md``)."""
    if not target or target.startswith(("http://", "https://", "mailto:", "/")):
        return False
    return _strip_anchor(target).endswith(".md")


def _page_body(text: str) -> str:
    """Return a page's body (everything after the frontmatter block)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return text
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            return "\n".join(lines[index + 1 :])
    return ""


def derive_related(
    page_path: Path, *, repo_root: Path, docs_root: Path
) -> RelatedDerivation:
    """Derive ``related:`` edges from a page's in-body markdown links (T068).

    Each inline ``[text](target.md)`` link is resolved relative to the page's
    own directory. A target that resolves to an existing ``.md`` file under the
    docs root becomes a repo-relative *resolved* edge; a docs-shaped link that
    does not resolve is recorded as *unresolved* (flagged for WP12). The page's
    own path is never emitted as a self-edge.
    """
    try:
        text = page_path.read_text(encoding="utf-8")
    except OSError:
        return RelatedDerivation()

    repo = repo_root.resolve()
    docs = docs_root.resolve()
    page_dir = page_path.resolve().parent
    self_rel = _repo_relative(page_path, repo)

    resolved: set[str] = set()
    unresolved: set[str] = set()
    for raw_target in _LINK_RE.findall(_page_body(text)):
        if not _is_docs_link(raw_target):
            continue
        clean = _strip_anchor(raw_target)
        candidate = (page_dir / clean).resolve()
        rel = _repo_relative(candidate, repo)
        if rel == self_rel:
            continue
        if candidate.is_file() and _is_under(candidate, docs):
            resolved.add(rel)
        else:
            unresolved.add(clean)

    return RelatedDerivation(
        resolved=sorted(resolved), unresolved=sorted(unresolved)
    )


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` is located within ``root``."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Render ``path`` as a POSIX repo-relative string (best-effort)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git_last_updated(rel_path: str, *, repo_root: Path) -> str | None:
    """Return a page's last-commit date (``YYYY-MM-DD``) via git, or ``None``.

    The inventory snapshot carries no ``updated`` field, so the freshness date
    is derived from the file's last commit. Best-effort: returns ``None`` when
    git is unavailable or the file is untracked, leaving the date for authoring.
    """
    try:
        completed = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    date = completed.stdout.strip()
    return date or None


UpdatedResolver = Callable[[str], "str | None"]


def build_backfill(
    entry: PageInventoryEntry,
    *,
    repo_root: Path,
    docs_root: Path,
    updated_resolver: UpdatedResolver | None = None,
) -> PageBackfill:
    """Build the :class:`PageBackfill` plan for one inventory entry.

    ``doc_status`` is derived (T065); ``version_tag`` / ``type`` /
    ``owning_workstream`` are carried from the inventory row; ``related`` is
    derived from in-body links (T068); ``description`` and ``updated`` are
    *preserved* from any existing frontmatter (the tool never authors a
    description), with ``updated`` falling back to ``updated_resolver``.
    """
    page_path = (repo_root / entry.path).resolve()
    existing = _existing_frontmatter(page_path)

    related = derive_related(page_path, repo_root=repo_root, docs_root=docs_root)

    updated = _coerce_str(existing.get(_FM_UPDATED))
    if updated is None:
        resolver = updated_resolver or (
            lambda rel: _git_last_updated(rel, repo_root=repo_root)
        )
        updated = resolver(entry.path)

    return PageBackfill(
        path=entry.path,
        doc_status=derive_doc_status(entry.tag, current_target=entry.current_target),
        version_tag=entry.tag,
        divio_type=entry.divio_type,
        owning_workstream=entry.owning_workstream,
        updated=updated,
        related=related.resolved,
        related_unresolved=related.unresolved,
        description=_coerce_str(existing.get(_FM_DESCRIPTION)),
        notes=entry.notes,
    )


def _existing_frontmatter(page_path: Path) -> Mapping[str, Any]:
    """Return a page's existing frontmatter (empty mapping when absent)."""
    try:
        text = page_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_frontmatter(text)


def _coerce_str(value: object) -> str | None:
    """Coerce a frontmatter scalar to a non-empty string, else ``None``."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def plan_backfill(
    *,
    inventory_path: Path,
    repo_root: Path,
    docs_root: Path,
    updated_resolver: UpdatedResolver | None = None,
) -> list[PageBackfill]:
    """Plan the backfill for every inventoried page (no writes)."""
    entries = load_inventory(inventory_path)
    return [
        build_backfill(
            entry,
            repo_root=repo_root,
            docs_root=docs_root,
            updated_resolver=updated_resolver,
        )
        for entry in entries
    ]


def render_page(existing_text: str, backfill: PageBackfill) -> str:
    """Render a page's new text with backfilled frontmatter (idempotent).

    Existing frontmatter keys are preserved; the derived/carried keys are
    merged over them in a deterministic order, so re-rendering the output
    reproduces it byte-for-byte. The body is left untouched.
    """
    existing = dict(parse_frontmatter(existing_text))
    body = _page_body(existing_text)

    merged: dict[str, Any] = dict(existing)
    merged[_FM_DOC_STATUS] = backfill.doc_status.value
    merged[_FM_VERSION_TAG] = backfill.version_tag.value
    merged[_FM_DIVIO_TYPE] = backfill.divio_type.value
    merged[_FM_OWNING_WORKSTREAM] = backfill.owning_workstream
    if backfill.updated is not None:
        merged[_FM_UPDATED] = backfill.updated
    if backfill.description is not None:
        merged[_FM_DESCRIPTION] = backfill.description
    if backfill.notes is not None:
        merged[_FM_NOTES] = backfill.notes
    if backfill.related:
        merged[_FM_RELATED] = list(backfill.related)

    frontmatter = _serialize_frontmatter(merged)
    return f"{_FRONTMATTER_FENCE}\n{frontmatter}{_FRONTMATTER_FENCE}\n{body.lstrip(chr(10))}"


def _serialize_frontmatter(data: Mapping[str, Any]) -> str:
    """Serialize a frontmatter mapping deterministically (canonical key order)."""
    ordered: dict[str, Any] = {}
    for key in _KEY_ORDER:
        if key in data:
            ordered[key] = data[key]
    for key in sorted(data):
        if key not in ordered:
            ordered[key] = data[key]

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    stream = io.StringIO()
    yaml.dump(ordered, stream)
    return stream.getvalue()


def apply_backfill(page_path: Path, backfill: PageBackfill) -> bool:
    """Write the backfilled frontmatter to ``page_path``. Returns True if changed.

    Idempotent: applying an already-backfilled page is a no-op (returns False).
    """
    try:
        existing_text = page_path.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text = render_page(existing_text, backfill)
    if new_text == existing_text:
        return False
    page_path.write_text(new_text, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    """Build the backfill CLI parser."""
    parser = argparse.ArgumentParser(
        prog="frontmatter_backfill",
        description=(
            "Derive doc_status + carry inventory frontmatter fields onto docs "
            "pages. Dry-run by default (prints the plan); pass --write to apply."
        ),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(DEFAULT_INVENTORY),
        help=f"Inventory snapshot to plan from (default: {DEFAULT_INVENTORY}).",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs tree the pages live under (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Base for resolving page paths and related: edges (default: cwd).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply the backfill to pages (default: dry-run, plan only).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the plan as JSON instead of a human summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    plan = plan_backfill(
        inventory_path=args.inventory,
        repo_root=args.repo_root,
        docs_root=args.docs_root,
    )
    if args.write:
        changed = sum(
            apply_backfill((args.repo_root / bf.path).resolve(), bf) for bf in plan
        )
        sys.stdout.write(
            f"frontmatter_backfill: applied to {changed}/{len(plan)} page(s).\n"
        )
        return 0
    _emit_plan(plan, as_json=args.json)
    return 0


def _emit_plan(plan: list[PageBackfill], *, as_json: bool) -> None:
    """Print the backfill plan — JSON payload or a human-readable summary."""
    if as_json:
        payload = [bf.as_dict() for bf in plan]
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return
    needs_desc = sum(1 for bf in plan if bf.description is None)
    edges = sum(len(bf.related) for bf in plan)
    sys.stdout.write(
        f"frontmatter_backfill: planned {len(plan)} page(s); "
        f"{needs_desc} need a description (WP12); {edges} related edge(s) derived.\n"
    )


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
