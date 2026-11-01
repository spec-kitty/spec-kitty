"""The ``docs/`` corpus carries doc-kitty's frontmatter shapes (#6929, FR-009).

doc-kitty refuses to build a page whose ``audience`` is not a profile list, whose
``related`` names something it cannot resolve, or (in effect) an ADR without a
``doc_status``: it treats that ADR as a draft and drops it from the site. The
readers that used to guard these fields are not wired into any workflow, so this
test is what keeps a new page from bringing the old shapes back.

Rules (ADR ``2026-10-31-1`` D-7/D-8, spec FR-006 as amended):

* ``audience`` is a list of ``{profile, guidance_text}`` mappings.
* ``related`` entries are slugs (or ``{ref, note}``) of existing pages; a published
  page names only published pages; a draft page names no excluded page; an
  excluded page (never built) may name any page.
* ``external_references`` entries carry ``url`` and ``title``.
* Every dated ADR carries ``kind: ADR`` and the ``doc_status`` its ``status`` maps to.

The four files #6928 resolves (the dual-index ``README.md`` stubs and the
architecture landing page) are skipped by the migration and here, through the
migration's own skip predicate; they leave the tree with #6928.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any, Final

import pytest

from scripts.docs._dockitty_contract import is_dated_adr, is_excluded, is_published, page_for_slug
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._page_scope import iter_docs_pages
from scripts.docs.dockitty_frontmatter_migration import ADR_DOC_STATUS, ADR_KIND, is_skipped

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_DOCS_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "docs"

#: Non-vacuity floors, well below today's counts (344 audience pages, 228 ADRs, 413 related pages).
_MIN_AUDIENCE_PAGES: Final[int] = 300
_MIN_ADRS: Final[int] = 200
_MIN_RELATED_PAGES: Final[int] = 300

Page = tuple[str, Mapping[str, Any]]


def _pages(docs_root: Path) -> Iterator[Page]:
    for path in iter_docs_pages(docs_root):
        rel = path.relative_to(docs_root).as_posix()
        if not is_skipped(rel):
            yield rel, parse_frontmatter(path.read_text(encoding="utf-8"))


def audience_problems(rel: str, data: Mapping[str, Any]) -> list[str]:
    raw = data.get("audience")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [f"{rel}: audience is not a list"]
    return [
        f"{rel}: audience entry {entry!r} is not {{profile, guidance_text}}"
        for entry in raw
        if not (isinstance(entry, dict) and all(isinstance(entry.get(k), str) and entry[k].strip() for k in ("profile", "guidance_text")))
    ]


def _target_problem(docs_root: Path, rel: str, data: Mapping[str, Any], ref: str) -> str | None:
    if ref.startswith(("docs/", "/")) or ref.endswith(".md"):
        return f"{rel}: related {ref!r} is a path, not a slug"
    page = page_for_slug(docs_root, ref)
    if page is None:
        return f"{rel}: related {ref!r} names no page"
    target = page.relative_to(docs_root).as_posix()
    if is_excluded(rel):
        return None
    if not is_published(rel, data):
        return f"{rel}: draft page's related {ref!r} names an excluded page" if is_excluded(target) else None
    if not is_published(target, parse_frontmatter(page.read_text(encoding="utf-8"))):
        return f"{rel}: published page's related {ref!r} names an unpublished page"
    return None


def _external_problems(rel: str, data: Mapping[str, Any]) -> list[str]:
    return [
        f"{rel}: external_references entry {entry!r} lacks url/title"
        for entry in data.get("external_references") or []
        if not (isinstance(entry, dict) and isinstance(entry.get("url"), str) and isinstance(entry.get("title"), str))
    ]


def related_problems(docs_root: Path, rel: str, data: Mapping[str, Any]) -> list[str]:
    problems = _external_problems(rel, data)
    raw = data.get("related")
    if raw is None:
        return problems
    if not isinstance(raw, list):
        return [*problems, f"{rel}: related is not a list"]
    for entry in raw:
        ref = entry.get("ref") if isinstance(entry, dict) else entry
        if not isinstance(ref, str):
            problems.append(f"{rel}: related entry {entry!r} is not a slug or {{ref, note}}")
            continue
        problem = _target_problem(docs_root, rel, data, ref)
        if problem:
            problems.append(problem)
    return problems


def adr_problems(rel: str, data: Mapping[str, Any]) -> list[str]:
    if not is_dated_adr(rel):
        return []
    expected = ADR_DOC_STATUS.get(str(data.get("status")))
    problems = []
    if data.get("doc_status") != expected:
        problems.append(f"{rel}: doc_status {data.get('doc_status')!r}, expected {expected!r} for status {data.get('status')!r}")
    if data.get("kind") != ADR_KIND:
        problems.append(f"{rel}: kind {data.get('kind')!r}, expected {ADR_KIND!r}")
    return problems


def _collect(check: Callable[[str, Mapping[str, Any]], list[str]], key: str) -> tuple[int, list[str]]:
    examined, problems = 0, []
    for rel, data in _pages(_DOCS_ROOT):
        if key in data:
            examined += 1
            problems.extend(check(rel, data))
    return examined, problems


def test_every_audience_is_a_profile_list() -> None:
    examined, problems = _collect(audience_problems, "audience")
    assert examined >= _MIN_AUDIENCE_PAGES, f"non-vacuity: only {examined} pages carry audience"
    assert problems == [], "\n".join(problems)


def test_every_related_entry_is_a_slug_doc_kitty_resolves() -> None:
    examined, problems = _collect(lambda rel, data: related_problems(_DOCS_ROOT, rel, data), "related")
    assert examined >= _MIN_RELATED_PAGES, f"non-vacuity: only {examined} pages carry related"
    assert problems == [], "\n".join(problems)


def test_every_adr_carries_doc_status_and_kind() -> None:
    adrs = [(rel, data) for rel, data in _pages(_DOCS_ROOT) if is_dated_adr(rel)]
    assert len(adrs) >= _MIN_ADRS, f"non-vacuity: only {len(adrs)} ADRs found"
    problems = [problem for rel, data in adrs for problem in adr_problems(rel, data)]
    assert problems == [], "\n".join(problems)


# --- negative controls: each rule names an old-shape page -------------------


def _tree(tmp_path: Path, pages: Mapping[str, str]) -> Path:
    for rel, frontmatter in pages.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{frontmatter}---\nbody\n", encoding="utf-8")
    return tmp_path


def test_controls_name_each_old_shape(tmp_path: Path) -> None:
    docs = _tree(
        tmp_path,
        {
            "index.md": "doc_status: active\n",
            "a.md": "doc_status: active\n",
            "draft.md": "doc_status: draft\n",
            "archive/old.md": "doc_status: active\n",
            "p.md": "doc_status: active\n",
        },
    )
    assert audience_problems("p.md", {"audience": "docs/context/audience/internal/maintainer.md"}) == ["p.md: audience is not a list"]
    assert audience_problems("p.md", {"audience": [{"profile": "x"}]})
    assert related_problems(docs, "p.md", {"doc_status": "active", "related": ["docs/a.md"]}) == ["p.md: related 'docs/a.md' is a path, not a slug"]
    assert related_problems(docs, "p.md", {"doc_status": "active", "related": ["gone"]}) == ["p.md: related 'gone' names no page"]
    assert related_problems(docs, "p.md", {"doc_status": "active", "related": ["draft"]})
    assert related_problems(docs, "d.md", {"doc_status": "draft", "related": ["archive/old"]})
    assert related_problems(docs, "d.md", {"doc_status": "draft", "related": ["draft"]}) == []
    assert related_problems(docs, "archive/x.md", {"related": ["draft", "archive/old"]}) == []
    assert related_problems(docs, "p.md", {"doc_status": "active", "related": [{"ref": "a", "note": "n"}, ""]}) == []
    assert related_problems(docs, "p.md", {"related": "a"}) == ["p.md: related is not a list"]
    assert related_problems(docs, "p.md", {"related": [3]})
    assert related_problems(docs, "p.md", {"external_references": [{"url": "u"}]})
    assert adr_problems("adr/4.x/2026-01-01-1-x.md", {"status": "Accepted"}) == [
        "adr/4.x/2026-01-01-1-x.md: doc_status None, expected 'active' for status 'Accepted'",
        "adr/4.x/2026-01-01-1-x.md: kind None, expected 'ADR'",
    ]
    assert adr_problems("adr/4.x/index.md", {}) == []
