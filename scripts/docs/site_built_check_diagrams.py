"""The ``diagrams`` surface of the built-site check (#6936, #6100; ADR 2026-10-31-1 D-11).

The site renders every Mermaid and PlantUML diagram at build time to a static SVG
(``diagrams: true``, ``DK_DIAGRAM_BUILD_RENDER=build``). Two checks prove it on the
built output, one rule each:

* doc-kitty's ``dockitty-assert-diagrams dist`` (doc-kitty 1042a40,
  spec-kitty/doc-kitty#314), run by the docsite build before this check, owns the
  built-markup rules: every ``<figure class="dk-diagram">`` holds an ``<svg>``, and
  no raw diagram code block, client-rendered ``<pre class="mermaid">``,
  ``plantuml-error`` block or plantuml.com URL the page would load remains. This
  surface does not repeat them.
* this surface owns the per-route count the bin cannot know, because it never reads
  the source: every page the site publishes (``_dockitty_contract.unpublished_routes``
  is the one authority) holds exactly as many rendered figures as its source holds
  diagram fences. A short count is a fence that did not reach the page as a picture,
  whatever it became instead; an excess is a figure with no source diagram (a page
  with figures and no fence is reported too). A diagram fence is a ```` ```mermaid ````
  or ```` ```plantuml ```` fence, read as doc-kitty reads it (the first word of the
  info string, case-sensitive, ``lib/remark/diagram-meta.ts:51``,
  ``lib/remark/plantuml-meta.ts:77``). A rendered figure is doc-kitty's
  ``<figure class="dk-diagram">`` holding an ``<svg>``
  (``lib/rehype/diagram-figure.ts:191-202`` for Mermaid, ``:282-299`` for PlantUML),
  counted once however many ``<svg>`` it holds.

A published page with diagram fences and no built page is a finding, not a pass. A
legacy ``.html`` redirect stub shares its page's route and is skipped, as the bin
skips it. Standard library only (``html.parser``), like ``site_built_check.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Final

from scripts.docs._dockitty_contract import body_of, redirect_stub_target, route_of, unpublished_routes
from scripts.docs.site_built_check_render import own_url

if TYPE_CHECKING:
    from scripts.docs.site_built_check import Finding

__all__ = ["DIAGRAM_LANGUAGES", "SURFACE", "PageDiagrams", "expected_figures", "findings", "page_defects", "source_blocks", "surface"]

#: The surface name the findings carry (the key in ``site_built_check.SOURCE_SURFACES``).
SURFACE: Final[str] = "diagrams"

#: The fence languages doc-kitty renders as diagrams.
DIAGRAM_LANGUAGES: Final[frozenset[str]] = frozenset({"mermaid", "plantuml"})

_MD_SUFFIX: Final[str] = ".md"
_HTML_SUFFIX: Final[str] = ".html"
_INDEX_HTML: Final[str] = "index.html"
_FIGURE_CLASS: Final[str] = "dk-diagram"
_FENCE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")


def _opening(line: str) -> tuple[str, str] | None:
    """The fence and the language of an opening fence line, or ``None``."""
    match = _FENCE.match(line)
    if match is None:
        return None
    fence, info = match["fence"], match["info"].strip()
    if fence[0] == "`" and "`" in info:
        return None
    return fence, info.split()[0] if info else ""


def _closes(line: str, fence: str) -> bool:
    match = _FENCE.match(line)
    return match is not None and match["fence"][0] == fence[0] and len(match["fence"]) >= len(fence) and not match["info"].strip()


def source_blocks(markdown: str) -> int:
    """The number of top-level diagram fences in *markdown* (a fence inside another fence is content)."""
    count = 0
    open_fence: str | None = None
    for line in markdown.splitlines():
        if open_fence is not None:
            if _closes(line, open_fence):
                open_fence = None
            continue
        opening = _opening(line)
        if opening is not None:
            open_fence = opening[0]
            count += opening[1] in DIAGRAM_LANGUAGES
    return count


def expected_figures(docs: Path) -> dict[str, int]:
    """Route -> diagram fence count, for every published page under *docs* that has one."""
    unpublished = unpublished_routes(docs)
    expected: dict[str, int] = {}
    for path in sorted(docs.rglob(f"*{_MD_SUFFIX}")):
        route = route_of(path.relative_to(docs).as_posix())
        if route in unpublished:
            continue
        count = source_blocks(body_of(path.read_text(encoding="utf-8")))
        if count:
            expected[route] = expected.get(route, 0) + count
    return expected


@dataclass
class _Figure:
    """An open ``<figure>`` the parser is inside."""

    marked: bool
    done: bool = False


class PageDiagrams(HTMLParser):
    """The rendered diagram figures of one built page: ``dk-diagram`` figures holding an ``<svg>``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.figures = 0
        self._open: list[_Figure] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "figure":
            classes = next((value or "" for name, value in attrs if name == "class"), "").split()
            self._open.append(_Figure(_FIGURE_CLASS in classes))
        elif tag == "svg":
            self._svg()

    def handle_endtag(self, tag: str) -> None:
        if tag == "figure" and self._open:
            self._open.pop()

    def _svg(self) -> None:
        figure = self._open[-1] if self._open else None
        if figure is not None and figure.marked and not figure.done:
            figure.done = True
            self.figures += 1


def page_defects(html: str, expected: int) -> Iterator[str]:
    """The count defect of the built page *html* whose source holds *expected* diagram fences, if any."""
    page = PageDiagrams()
    page.feed(html)
    page.close()
    if page.figures != expected:
        yield f"{expected} diagram block(s) in the source, {page.figures} rendered figure(s)"


def _built_rel(route: str) -> str:
    clean = route.strip("/")
    return f"{clean}/{_INDEX_HTML}" if clean else _INDEX_HTML


def findings(dist: Path, *, docs: Path) -> Iterator[Finding]:
    """Every ``diagrams`` finding of the built site at *dist* built from the docs tree *docs*."""
    from scripts.docs.site_built_check import Finding  # noqa: PLC0415  (site_built_check registers this surface; a top-level import is a cycle)

    expected = expected_figures(docs)
    built: set[str] = set()
    for page in sorted(dist.rglob(f"*{_HTML_SUFFIX}")):
        html = page.read_text(encoding="utf-8", errors="replace")
        if redirect_stub_target(html) is not None:
            continue  # a legacy ``.html`` stub beside the page shares its route; it is a redirect, not the page (#6933)
        rel = page.relative_to(dist).as_posix()
        route = own_url(rel, "")
        built.add(route)
        for defect in page_defects(html, expected.get(route, 0)):
            yield Finding(SURFACE, route, f"{rel}: {defect}")
    for route, count in sorted(expected.items()):
        if route not in built:
            yield Finding(SURFACE, route, f"{_built_rel(route)}: {count} diagram block(s) in the source, no built page")


def surface(dist: Path, docs: Path) -> Iterator[Finding]:
    """The registered source surface: the built site at *dist* against the docs tree *docs*."""
    yield from findings(dist, docs=docs)
